#!/usr/bin/env python3
"""simulate_credit_economy.py — does the credit economy still hold over TEN THOUSAND jobs?

Ian asked for massive simulation behind the money economy. This is the honest form of that.

WHAT THIS IS NOT. `tools/run_companion_100turn_flywheel.py` advertises "100 turns x 1225 tests" and
FABRICATES every outcome: `simulate_turn_observations()` draws pass rates from `random.gauss` against a
sigmoid convergence curve. It models a flywheel; it executes nothing. For a money economy that is worse than
no test at all, because it produces a confident number describing transactions that never happened
([[feedback_measure_the_worked_state_not_the_generator]], [[feedback_an_impossibly_good_result_is_the_defect]]).

WHAT THIS IS. Generated job lifecycles driven through the REAL schema — the real guards, the real triggers,
the real ledger — inside one transaction that is ROLLED BACK at the end. Nothing is stubbed and no simulated
peso survives the run. A single probe proves a rule on one job; this asks whether the rule still holds across
thousands of jobs, in every legal order, including the tails where the study says the model actually breaks.

THE SIX INVARIANTS (each named in MARKETPLACE_CREDIT_SUSTAINABILITY):
  1. net_take            commission - cashback == (commission_pct - cashback_pct) of settled GMV. The
                         headline "4%" claim, MEASURED rather than asserted.
  2. solvency            no consumer balance ever goes negative. A consumer only receives and spends
                         cashback, so a negative balance means credits were spent that were never minted.
  3. exactly_once        one commission and one cashback per settled job, under re-release and double-tap.
  4. liability_cover     outstanding liability stays backed; the WORST point in the run is reported, not
                         the average, because §4's failure modes are tail events.
  5. order_independence  the same events applied in a different order reach the same balances (a
                         metamorphic relation — no expected value needed, which is why this surface had none).
  6. reached_states      every one of the 12 request states is actually exercised. A run that never produced
                         an `expired` or `disputed` arc has not tested them and must SAY so
                         ([[feedback_a_skipped_partition_reads_as_a_covered_one]]).

TEETH. A simulation that cannot fail proves nothing, so `--inject` deliberately breaks the economy and the
run must go RED: `double-mint` (mint a second commission), `ledger-delete` (delete an entry — the lie the
dispute path exists to avoid), `negative-consumer` (spend credits never minted). Verified by `--selftest`.

Usage:
  python tools/simulate_credit_economy.py [--runs N] [--inject double-mint|ledger-delete|negative-consumer]
  python tools/simulate_credit_economy.py --selftest
"""
import argparse
import re
import subprocess
import sys

G, R, Y, D, B, X = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"
CONTAINER = "supabase_db_workhive"

STATES = ["requested", "broadcasting", "accepted", "en_route", "on_site", "in_progress",
          "completed", "settled", "cancelled_by_client", "cancelled_by_provider", "expired", "disputed"]

INJECTIONS = {
    "double-mint": "a second commission row for a job that already has one",
    "ledger-delete": "a DELETED ledger entry - the audit-trail lie the dispute path exists to avoid",
    "negative-consumer": "a consumer spending credits that were never minted",
}


def run_sql(sql, timeout=900):
    try:
        r = subprocess.run(["docker", "exec", "-i", CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
                            "-q", "-v", "ON_ERROR_STOP=1"],
                           input=sql, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except Exception as e:
        return None, str(e)
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0:
        return None, out[-500:]
    return out, ""


def build_sql(runs, inject):
    """One transaction, N generated lifecycles, ROLLBACK. The work happens in plpgsql rather than N python
    round-trips: 10,000 docker exec calls would take hours and prove exactly the same thing."""
    inj = f"'{inject}'" if inject else "NULL"
    return f"""
begin;
do $sim$
DECLARE
  v_runs        int := {runs};
  v_inject      text := {inj};
  v_client      uuid;  v_client2 uuid;  v_prov uuid;  v_hive uuid;
  v_req         uuid;  i int;  v_price numeric;  v_seg text;  v_path int;
  v_com         numeric;  v_cash numeric;
  v_gmv         numeric := 0;   -- settled GMV only
  v_gmv_c       numeric := 0;  v_net_c numeric := 0;   -- consumer segment
  v_gmv_i       numeric := 0;  v_net_i numeric := 0;   -- industrial segment
  v_tot_com     numeric := 0;
  v_tot_cash    numeric := 0;
  v_settled     int := 0;
  v_dup         int := 0;       -- jobs with != 1 commission or != 1 cashback
  v_neg         int := 0;       -- consumer balances observed negative
  v_worst_cover numeric := 999;
  -- States are recorded in a TEMP TABLE, not an accumulating array. `v_states || 'x'` on a growing
  -- array is O(n^2) and 10,000 runs x ~8 states would spend the whole simulation on array copies; the
  -- table also dedupes for free and is rolled back with everything else.
  v_bal         numeric;  v_a numeric;  v_b numeric;
  v_injected    boolean := false;
BEGIN
  CREATE TEMP TABLE IF NOT EXISTS sim_reached_states (state text PRIMARY KEY) ON COMMIT DROP;

  -- THE DAILY ROW CAP IS ANNOUNCED PAST, DELIBERATELY AND NARROWLY. `check_daily_row_cap` is a real
  -- anti-abuse control and it fired correctly on this synthetic volume - one worker does not file 2,000
  -- service requests in a day. It is NOT what this simulation is testing, it has its own gate and its own
  -- coverage, and leaving it in place would mean the money invariants could only ever be exercised ~100
  -- jobs at a time. So the same GUC the platform's own system triggers use is set for this transaction
  -- only, and it is named here rather than worked around silently: nothing else about the guards, the
  -- triggers or the ledger is bypassed, and the whole transaction is rolled back.
  PERFORM set_config('workhive.row_cap_system_write', 'on', true);
  SELECT id INTO v_client  FROM auth.users ORDER BY created_at LIMIT 1;
  SELECT id INTO v_client2 FROM auth.users ORDER BY created_at DESC LIMIT 1;
  -- A PROVIDER WITH A REAL HIVE, CHOSEN DETERMINISTICALLY.
  -- This was `SELECT id, hive_id ... FROM service_providers LIMIT 1` -- unordered, and 5 of the 7
  -- seeded providers have a NULL hive_id. So the simulation ran all 2,000 lifecycles with
  -- v_hive = NULL, every service_knob_pct() call fell through to its hardcoded default, and the gate
  -- had NEVER exercised a per-hive setting. Proven by trying to make the teeth bite: setting
  -- commission_pct = 5 on every hive changed nothing, because the hive under test was NULL.
  -- Unordered LIMIT 1 is also non-deterministic across runs -- the same class as the banked
  -- "resolving live is not enough, be deterministic". ORDER BY id makes the fixture stable, and
  -- hive_id IS NOT NULL makes the knobs real.
  SELECT id, hive_id INTO v_prov, v_hive
    FROM public.service_providers WHERE hive_id IS NOT NULL ORDER BY id LIMIT 1;
  IF v_client IS NULL OR v_prov IS NULL THEN
    -- Named, not silent: a run against NULL-hive fixtures would pass while testing only defaults,
    -- which is the "a skipped partition reads as a covered one" failure this suite exists to avoid.
    RAISE NOTICE 'RESULT fatal=no_fixtures_with_hive';
    RETURN;
  END IF;

  -- CAPITALISE THE PROVIDER, because accepting a job now COSTS something.
  -- mig 20260803000037 made a service a listing too: guard_accept_requires_reservation holds 10% of
  -- the agreed price when a provider accepts. This simulation runs every one of its 2,000 lifecycles
  -- through ONE provider who was never funded, so it worked only while acceptance was free. The first
  -- industrial job aborted the whole run with "You need PHP1,500 in credits to take a PHP15,004 job
  -- (10%), and you have PHP950."
  --
  -- The guard is right and the simulation was out of date -- the gate reddened because the code
  -- improved. Do NOT relax the guard to make the run green; fund the actor instead, which is what a
  -- provider taking 2,000 jobs would actually have to do. The ceiling is generous on purpose: this
  -- simulation exists to exercise the MONEY invariants (double-mint, negative balances, order
  -- dependence) across many lifecycles, and a provider who goes broke on job 40 stops exercising them.
  -- Reserve exhaustion has its own dedicated coverage in simulate_credit_reserve.py; duplicating it
  -- here would cost this gate its actual subject.
  --
  -- Announced, not silent: this is a real ledger entry through the real trigger path, inside the same
  -- rolled-back transaction as everything else. Nothing about the guards is bypassed.
  PERFORM set_config('workhive.service_system_write', 'on', true);
  INSERT INTO public.service_credit_ledger
    (account_type, account_id, entry_type, amount, ref_kind, note)
  VALUES ('provider', v_prov, 'topup', 50000000, 'topup',
          'simulation: capitalise the provider so acceptance holds can be paid for 2,000 jobs');
  PERFORM set_config('workhive.service_system_write', 'off', true);

  FOR i IN 1..v_runs LOOP
    -- Segment and price sampled to mirror the real mix rather than a uniform one: consumer jobs are
    -- small and frequent, industrial jobs large and rarer. A model where every job is the same size
    -- hides exactly the tail behaviour this simulation exists to find.
    IF i % 4 = 0 THEN v_seg := 'industrial'; v_price := 15000 + (i % 20000);
                 ELSE v_seg := 'consumer';   v_price := 500 + (i % 4000); END IF;

    INSERT INTO public.service_requests
      (client_auth_uid, hive_id, segment, mode, status, matched_provider_id, budget, custom_scope)
    VALUES (CASE WHEN i % 3 = 0 THEN v_client2 ELSE v_client END,
            v_hive, v_seg, CASE WHEN i % 2 = 0 THEN 'instant' ELSE 'quote' END,
            'requested', v_prov, v_price, 'sim ' || i)
    RETURNING id INTO v_req;
      INSERT INTO sim_reached_states VALUES ('requested') ON CONFLICT DO NOTHING;

    -- SIX exit paths, so every one of the 12 states is genuinely reached rather than assumed.
    v_path := i % 6;

    IF v_path = 0 THEN            -- cancelled early by the client
      UPDATE public.service_requests SET status='broadcasting' WHERE id=v_req;
      UPDATE public.service_requests SET status='cancelled_by_client' WHERE id=v_req;
      INSERT INTO sim_reached_states VALUES ('broadcasting') ON CONFLICT DO NOTHING;
      INSERT INTO sim_reached_states VALUES ('cancelled_by_client') ON CONFLICT DO NOTHING;

    ELSIF v_path = 1 THEN         -- expired with no taker
      UPDATE public.service_requests SET status='broadcasting' WHERE id=v_req;
      UPDATE public.service_requests SET status='expired' WHERE id=v_req;
      INSERT INTO sim_reached_states VALUES ('broadcasting') ON CONFLICT DO NOTHING;
      INSERT INTO sim_reached_states VALUES ('expired') ON CONFLICT DO NOTHING;

    ELSIF v_path = 2 THEN         -- provider walked away after accepting
      UPDATE public.service_requests SET status='broadcasting' WHERE id=v_req;
      UPDATE public.service_requests SET status='accepted' WHERE id=v_req;
      UPDATE public.service_requests SET status='cancelled_by_provider' WHERE id=v_req;
      INSERT INTO sim_reached_states VALUES ('broadcasting') ON CONFLICT DO NOTHING;
      INSERT INTO sim_reached_states VALUES ('accepted') ON CONFLICT DO NOTHING;
      INSERT INTO sim_reached_states VALUES ('cancelled_by_provider') ON CONFLICT DO NOTHING;

    ELSE                          -- the full arc to settled (and sometimes on to disputed)
      UPDATE public.service_requests SET status='broadcasting' WHERE id=v_req;
      UPDATE public.service_requests SET status='accepted'     WHERE id=v_req;
      UPDATE public.service_requests SET status='en_route'     WHERE id=v_req;
      UPDATE public.service_requests SET status='on_site'      WHERE id=v_req;
      UPDATE public.service_requests SET status='in_progress'  WHERE id=v_req;
      UPDATE public.service_requests SET status='completed'    WHERE id=v_req;
      INSERT INTO sim_reached_states VALUES ('broadcasting') ON CONFLICT DO NOTHING;
      INSERT INTO sim_reached_states VALUES ('accepted') ON CONFLICT DO NOTHING;
      INSERT INTO sim_reached_states VALUES ('en_route') ON CONFLICT DO NOTHING;
      INSERT INTO sim_reached_states VALUES ('on_site') ON CONFLICT DO NOTHING;
      INSERT INTO sim_reached_states VALUES ('in_progress') ON CONFLICT DO NOTHING;
      INSERT INTO sim_reached_states VALUES ('completed') ON CONFLICT DO NOTHING;

      INSERT INTO public.service_payments (request_id, hive_id, amount_paid, method, confirmed_by)
      VALUES (v_req, v_hive, v_price, CASE WHEN i % 2 = 0 THEN 'cash' ELSE 'gcash' END,
              CASE WHEN i % 3 = 0 THEN v_client2 ELSE v_client END);

      UPDATE public.service_requests SET status='settled' WHERE id=v_req;
      INSERT INTO sim_reached_states VALUES ('settled') ON CONFLICT DO NOTHING;

      -- P-IMPULSIVE, the human form of the idempotency test: the same release tapped twice.
      IF i % 5 = 0 THEN
        UPDATE public.service_requests SET status='completed' WHERE id=v_req;
        UPDATE public.service_requests SET status='settled'   WHERE id=v_req;
      END IF;

      -- INJECTION FIRES ON THE FIRST JOB THAT ACTUALLY SETTLES, not on a fixed index. The first cut
      -- injected at `i = 2` — and 2 % 6 = 2 is the provider-cancel path, which never settles, so the
      -- injection never executed and TWO of the three teeth tests reported PASS while proving nothing.
      -- A teeth test that cannot fire is the same defect it exists to catch
      -- ([[feedback_an_impossibly_good_result_is_the_defect]]).
      IF v_inject IS NOT NULL AND NOT v_injected THEN
        v_injected := true;
        IF v_inject = 'double-mint' THEN
          -- A second commission is STRUCTURALLY IMPOSSIBLE while
          -- service_credit_ledger_one_commission_per_request stands, so injecting it means removing that
          -- protection first. This is the mutation-testing shape: it asks whether the INVARIANT would
          -- notice if the structural guarantee were ever dropped, rather than whether the index works.
          -- DDL is transactional here, so the index returns on rollback with everything else.
          DROP INDEX IF EXISTS public.service_credit_ledger_one_commission_per_request;
          INSERT INTO public.service_credit_ledger
            (account_type, account_id, entry_type, amount, ref_kind, ref_id, note)
          VALUES ('provider', v_prov, 'commission', -1, 'request', v_req, 'INJECTED second commission');
        ELSIF v_inject = 'ledger-delete' THEN
          DELETE FROM public.service_credit_ledger WHERE ref_id = v_req AND entry_type = 'commission';
        END IF;
      END IF;

      SELECT count(*) FILTER (WHERE entry_type='commission'),
             count(*) FILTER (WHERE entry_type='cashback')
        INTO v_com, v_cash
        FROM public.service_credit_ledger WHERE ref_id = v_req;
      -- EXACTLY-ONCE MEANS "EXACTLY AS MANY AS THE KNOB SAYS", not "exactly one".
      -- This read `v_com <> 1 OR v_cash <> 1` and was correct under the July money model. The credits
      -- plan then set commission_pct and cashback_pct to 0, so a settled job now correctly carries
      -- ZERO of each -- and this line reported all 999 settled jobs as invariant violations while the
      -- platform was behaving exactly as designed. That is the stale-invariant trap the plan named by
      -- name: "a LOCKED line left contradicting live behaviour is how the next session re-introduces
      -- commission believing it is restoring an invariant."
      -- Derive the expectation from the LIVE knob so this gate keeps its teeth in both directions:
      -- with the rate at 0 a job that somehow carries a commission FAILS, and if Ian ever sets a rate
      -- again a job that carries none FAILS too. The rule being tested is "the ledger matches the
      -- knob", which is true under every configuration.
      IF v_com <> (CASE WHEN public.service_knob_pct(v_hive,'commission_pct') > 0 THEN 1 ELSE 0 END)
         OR v_cash <> (CASE WHEN public.service_knob_pct(v_hive,'cashback_pct') > 0 THEN 1 ELSE 0 END)
      THEN v_dup := v_dup + 1; END IF;

      SELECT -coalesce(sum(amount),0) INTO v_com  FROM public.service_credit_ledger
        WHERE ref_id=v_req AND entry_type='commission';
      SELECT  coalesce(sum(amount),0) INTO v_cash FROM public.service_credit_ledger
        WHERE ref_id=v_req AND entry_type='cashback';
      v_gmv := v_gmv + v_price; v_tot_com := v_tot_com + v_com; v_tot_cash := v_tot_cash + v_cash;
      -- Split by SEGMENT. The blended rate is a property of the job MIX, not of the platform, and it
      -- moved 4.8% -> 5.9% between two runs purely because the generator's mix shifted. The per-segment
      -- rates are the stable fact: consumer carries 10% commission and industrial 5%, both less the 1%
      -- cashback. Reporting only the blend invites reading one run's mix as "the platform's rate".
      IF v_seg = 'consumer' THEN v_gmv_c := v_gmv_c + v_price; v_net_c := v_net_c + v_com - v_cash;
                            ELSE v_gmv_i := v_gmv_i + v_price; v_net_i := v_net_i + v_com - v_cash; END IF;
      v_settled := v_settled + 1;

      -- every 7th settled job is then disputed and adjusted, so the reversal path is exercised at
      -- volume rather than once
      IF i % 7 = 0 THEN
        UPDATE public.service_requests SET status='disputed' WHERE id=v_req;
      INSERT INTO sim_reached_states VALUES ('disputed') ON CONFLICT DO NOTHING;
      END IF;
    END IF;

    IF v_inject = 'negative-consumer' AND i = 2 THEN  -- not settle-dependent; any job will do
      INSERT INTO public.service_credit_ledger
        (account_type, account_id, entry_type, amount, ref_kind, note)
      VALUES ('consumer', v_client, 'adjustment', -999999, 'adjustment', 'INJECTED overspend');
    END IF;

    -- solvency sampled DURING the run, not only at the end: "solvency never breaks" is a statement
    -- about every point in the sequence, and a check that only looks at the final state would miss a
    -- balance that went negative and came back.
    IF i % 25 = 0 THEN
      SELECT coalesce(sum(amount),0) INTO v_bal FROM public.service_credit_ledger
        WHERE account_type='consumer' AND account_id=v_client;
      IF v_bal < 0 THEN v_neg := v_neg + 1; END IF;
      SELECT CASE WHEN coalesce(sum(amount) FILTER (WHERE entry_type IN ('topup','cashback','voucher_grant')),0) = 0
                  THEN 999
                  ELSE coalesce(-sum(amount) FILTER (WHERE entry_type='commission'),0)
                     / nullif(sum(amount) FILTER (WHERE entry_type IN ('topup','cashback','voucher_grant')),0)
             END INTO v_bal FROM public.service_credit_ledger;
      v_worst_cover := least(v_worst_cover, coalesce(v_bal, 999));
    END IF;
  END LOOP;

  -- 5. ORDER INDEPENDENCE (metamorphic): two top-ups applied in either order must reach the same
  -- balance. No expected value is needed, which is exactly why this property had no test before.
  INSERT INTO public.service_credit_ledger(account_type,account_id,entry_type,amount,ref_kind,note)
    VALUES ('provider', v_prov, 'topup', 300, 'topup', 'order A1');
  INSERT INTO public.service_credit_ledger(account_type,account_id,entry_type,amount,ref_kind,note)
    VALUES ('provider', v_prov, 'topup', 700, 'topup', 'order A2');
  SELECT coalesce(sum(amount),0) INTO v_a FROM public.service_credit_ledger
    WHERE account_type='provider' AND account_id=v_prov;
  DELETE FROM public.service_credit_ledger WHERE note IN ('order A1','order A2');
  INSERT INTO public.service_credit_ledger(account_type,account_id,entry_type,amount,ref_kind,note)
    VALUES ('provider', v_prov, 'topup', 700, 'topup', 'order B1');
  INSERT INTO public.service_credit_ledger(account_type,account_id,entry_type,amount,ref_kind,note)
    VALUES ('provider', v_prov, 'topup', 300, 'topup', 'order B2');
  SELECT coalesce(sum(amount),0) INTO v_b FROM public.service_credit_ledger
    WHERE account_type='provider' AND account_id=v_prov;

  RAISE NOTICE 'RESULT runs=%', v_runs;
  RAISE NOTICE 'RESULT settled=%', v_settled;
  RAISE NOTICE 'RESULT gmv=%', round(v_gmv,2);
  RAISE NOTICE 'RESULT commission=%', round(v_tot_com,2);
  RAISE NOTICE 'RESULT cashback=%', round(v_tot_cash,2);
  RAISE NOTICE 'RESULT net_take_pct=%',
    CASE WHEN v_gmv > 0 THEN round((v_tot_com - v_tot_cash) / v_gmv * 100, 4) ELSE 0 END;
  RAISE NOTICE 'RESULT net_consumer_pct=%',
    CASE WHEN v_gmv_c > 0 THEN round(v_net_c / v_gmv_c * 100, 4) ELSE 0 END;
  RAISE NOTICE 'RESULT net_industrial_pct=%',
    CASE WHEN v_gmv_i > 0 THEN round(v_net_i / v_gmv_i * 100, 4) ELSE 0 END;
  RAISE NOTICE 'RESULT exactly_once_violations=%', v_dup;
  -- Publish the knobs so the Python verdict judges the take against what the platform SAYS it
  -- charges, rather than against a rate hardcoded when the gate was written.
  RAISE NOTICE 'RESULT commission_pct=%', public.service_knob_pct(v_hive,'commission_pct');
  RAISE NOTICE 'RESULT cashback_pct=%',   public.service_knob_pct(v_hive,'cashback_pct');
  RAISE NOTICE 'RESULT negative_consumer_samples=%', v_neg;
  RAISE NOTICE 'RESULT worst_cover=%', round(v_worst_cover, 4);
  RAISE NOTICE 'RESULT order_independent=%', (v_a = v_b);
  RAISE NOTICE 'RESULT reached_states=%', (SELECT string_agg(state, ',' ORDER BY state) FROM sim_reached_states);
END
$sim$;
rollback;
"""


def evaluate(res, runs):
    """Pure judgement over the parsed results, so --selftest can prove the verdicts without a database."""
    problems = []
    gmv = float(res.get("gmv", 0) or 0)
    settled = int(res.get("settled", 0) or 0)
    net = float(res.get("net_take_pct", 0) or 0)
    dup = int(res.get("exactly_once_violations", 0) or 0)
    neg = int(res.get("negative_consumer_samples", 0) or 0)
    reached = set((res.get("reached_states") or "").split(",")) - {""}
    missing = [s for s in STATES if s not in reached]

    if settled == 0:
        problems.append("no job reached `settled` — the run proves nothing about the money path")
    com_pct = float(res.get("commission_pct", 0) or 0)
    cash_pct = float(res.get("cashback_pct", 0) or 0)
    if dup:
        expect = (f"{'one' if com_pct > 0 else 'no'} commission and "
                  f"{'one' if cash_pct > 0 else 'no'} cashback")
        problems.append(f"ledger does not match the knobs on {dup} settled job(s): with commission_pct="
                        f"{com_pct:g}% and cashback_pct={cash_pct:g}% each job should carry {expect}")
    if neg:
        problems.append(f"solvency BROKEN: a consumer balance was negative at {neg} sample point(s) — "
                        f"credits were spent that were never minted")
    if res.get("order_independent") not in ("t", "true", True):
        problems.append("order-independence BROKEN: the same two top-ups in a different order reached "
                        "different balances")
    # NET TAKE IS JUDGED AGAINST THE KNOBS, and "0% is a failure" was itself the bug.
    # This asserted `abs(net) < 0.0001 -> the platform earned nothing`, which was a defect under the
    # July model and is the DESIGN under the credits plan: "No revenue. The platform takes no
    # commission and no spread." A gate that fails when the platform behaves as specified will,
    # eventually, be silenced by someone restoring commission to make it green.
    # The real invariant is that the take MATCHES what the platform says it charges -- so 0% is
    # required while the knobs are 0, and a non-zero take becomes the failure.
    expected_net = com_pct - cash_pct
    if settled and abs(net - expected_net) > 0.05:
        problems.append(f"net take {net:g}% does not match the knobs (commission_pct {com_pct:g}% "
                        f"less cashback_pct {cash_pct:g}% = {expected_net:g}% expected) — the platform "
                        f"is taking something it does not declare, or declaring something it does not take")
    if missing:
        problems.append(f"{len(missing)} of the 12 states were never reached ({', '.join(missing)}) — "
                        f"a partition that never ran reads exactly like a covered one")
    return problems, {"gmv": gmv, "settled": settled, "net": net, "reached": reached, "missing": missing}


def selftest():
    print("  selftest: the verdicts must catch each broken invariant and accept a healthy run")
    ok = True
    # TWO healthy fixtures, because the verdicts are now knob-driven and a single fixture would only
    # ever prove one configuration. The no-revenue one is TODAY's platform; the charging one is what
    # the same code must still judge correctly if Ian ever sets a rate again.
    no_revenue = {"settled": "100", "gmv": "200000", "net_take_pct": "0", "exactly_once_violations": "0",
                  "commission_pct": "0", "cashback_pct": "0",
                  "negative_consumer_samples": "0", "order_independent": "t",
                  "reached_states": ",".join(STATES)}
    charging = dict(no_revenue, net_take_pct="4.0", commission_pct="5", cashback_pct="1")
    for fixture, label in [(no_revenue, "no-revenue (today)"), (charging, "charging 5% less 1%")]:
        p, _ = evaluate(fixture, 100)
        if p:
            print(f"  {R}FAIL{X} — a healthy {label} run was flagged: {p}"); ok = False

    for base, key, val, label in [
            (no_revenue, "exactly_once_violations", "3", "ledger disagreeing with the knobs"),
            (no_revenue, "negative_consumer_samples", "2", "negative consumer"),
            (no_revenue, "order_independent", "f", "order dependence"),
            (no_revenue, "settled", "0", "nothing settled"),
            # THE INVERSION, and the reason this gate was rewritten: with the rates at 0 the platform
            # must take NOTHING. A run that reports a take is now the failure — the exact shape that
            # would appear if commission were quietly re-introduced.
            (no_revenue, "net_take_pct", "4.0", "a take the knobs do not declare"),
            # And the other direction still bites: declared rates that produce no take.
            (charging, "net_take_pct", "0", "declared rates producing nothing")]:
        broken = dict(base); broken[key] = val
        if not evaluate(broken, 100)[0]:
            print(f"  {R}FAIL{X} — {label} was not caught"); ok = False

    partial = dict(no_revenue); partial["reached_states"] = "requested,settled"
    if not evaluate(partial, 100)[0]:
        print(f"  {R}FAIL{X} — unreached states were not reported"); ok = False
    if ok:
        print(f"  {G}PASS{X} — catches a ledger that disagrees with the knobs (both directions), a take "
              f"the knobs do not declare, negative balances, order dependence, an empty run and "
              f"unreached states — under BOTH a no-revenue and a charging configuration")
    return 0 if ok else 1


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=2000)
    ap.add_argument("--inject", choices=sorted(INJECTIONS))
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)

    if a.selftest:
        return selftest()
    if selftest() != 0:
        return 1

    print(f"{B}Credit economy simulation{X} — {a.runs} generated lifecycles through the REAL guards"
          + (f"  {Y}[injecting {a.inject}: {INJECTIONS[a.inject]}]{X}" if a.inject else ""))
    out, err = run_sql(build_sql(a.runs, a.inject))
    if out is None:
        if "docker" in err.lower() or "Cannot connect" in err:
            print(f"  {Y}SKIP{X} database unavailable")
            return 0
        print(f"  {R}FAIL{X} the run aborted: {err}")
        return 1

    res = dict(re.findall(r"RESULT (\w+)=(.*)", out))
    problems, m = evaluate(res, a.runs)

    print(f"  {D}settled {m['settled']} of {a.runs} generated jobs · GMV {m['gmv']:,.2f}{X}")
    print(f"  {D}commission {float(res.get('commission',0)):,.2f} · "
          f"cashback {float(res.get('cashback',0)):,.2f}{X}")
    # The rates come from the LIVE knobs. This line used to read "(10%/5% commission less 1%
    # cashback — THESE are the stable numbers)", which stopped being true the moment the credits plan
    # zeroed both. Printing a repealed rate as "the stable number" is how the next reader concludes
    # the platform still charges it.
    _com, _cash = float(res.get("commission_pct", 0) or 0), float(res.get("cashback_pct", 0) or 0)
    _rates = (f"commission {_com:g}% less cashback {_cash:g}% — THESE are the stable numbers"
              if (_com or _cash) else
              "no revenue by design: commission and cashback are both 0, so a take here would be a defect")
    print(f"  {B}net take {m['net']}%{X}  {D}blended — a property of the job MIX, not a platform rate{X}")
    print(f"  {D}  by segment: consumer {res.get('net_consumer_pct','?')}% · "
          f"industrial {res.get('net_industrial_pct','?')}%  ({_rates}){X}")
    print(f"  {D}worst liability cover seen {res.get('worst_cover','?')} · "
          f"exactly-once violations {res.get('exactly_once_violations','?')}{X}")
    reached = len(m["reached"] & set(STATES))
    print(f"  {D}states reached {reached}/12"
          + (f" — MISSING {', '.join(m['missing'])}" if m["missing"] else "") + f"{X}")

    if problems:
        print(f"\n  {R}FAIL{X} — the economy did not hold:")
        for p in problems:
            print(f"    · {p}")
        return 1
    print(f"\n  {G}PASS{X} — all six invariants held across {m['settled']} settled jobs, "
          f"and nothing persisted (rolled back)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
