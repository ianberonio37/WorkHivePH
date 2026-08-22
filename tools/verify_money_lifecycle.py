#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
THE MONEY LIFECYCLE, ASKED OF THE DATABASE RATHER THAN OF A SCREEN
═══════════════════════════════════════════════════════════════════════════════════════════════════

21 rows in the live-MCP bank make claims about credits: a top-up mints exactly once, a commission is
destroyed rather than moved, credits may cover at most 10% of a purchase, a job cannot both earn and
spend a reward, nothing can be cashed out. Every one of them had been walked by hand on a page, and a
page is the wrong instrument for these: the screen shows a balance, and the claim is about what the
ledger did.

So this asks the server. Each check is one question with one measured answer, and the answers are the
evidence banked against those rows.

WHAT THIS FILE REFUSES TO DO:
  · It does not leave anything behind. Every probe that writes runs inside `begin; … rollback;`, in a
    single psql invocation so the rollback cannot be orphaned by a crashed process.
  · It does not treat an absence as a proof. A guard that "refuses" is only verified if the attempt it
    refused would otherwise have SUCCEEDED — so the refusal probes assert a control case first, and a
    probe that cannot construct its own fixture reports `needs-live` rather than passing vacuously.
  · It does not read the number it is checking from the same place that wrote it.

Run:  python tools/verify_money_lifecycle.py
      python tools/verify_money_lifecycle.py --json
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"

_vli = importlib.util.spec_from_file_location(
    "_vli", os.path.join(ROOT, "tools", "verify_layer_invariants.py"))
VLI = importlib.util.module_from_spec(_vli)
_vli.loader.exec_module(VLI)
one, qjson = VLI.one, VLI.qjson


def whole(sql):
    """A single value read WHOLE, even when it spans lines.

    `one()` takes the first LINE of psql's output, which for a single multiline VALUE — a function
    body from pg_get_functiondef — is just its first line. The first run of this harness searched
    "CREATE OR REPLACE FUNCTION public.mint_settlement_commission()" for an INSERT, found none, and
    reported the function "no longer writes a ledger row at all" about a function whose INSERT I had
    read an hour earlier. Same class as the partial-read that once rebuilt a guard wrong: evidence
    about a fragment, presented as evidence about the thing. Route the value through json_agg so the
    newlines survive serialisation.
    """
    rows = qjson(f"select ({sql}) as v")
    return (rows[0].get("v") or "") if rows else ""


def as_person(uid, sql, setup=""):
    """Attempt `sql` AS A REAL SIGNED-IN PERSON, inside a transaction that is always rolled back.

    THIS EXISTS BECAUSE PROBING AS `postgres` PROVED NOTHING. Every guard in this schema opens with a
    vetted-platform-act escape — `if auth.uid() is null ... return new` — so a superuser probe walks
    straight past the rule and the write succeeds. The first run of this harness reported three
    "defects" that way: credits transferable, a verified top-up reversible, and it was the probe
    holding no identity, not the server holding no rule. Same lesson as the RLS probe that needed the
    ROLE and not just the claims.
    """
    claims = '{"sub":"%s","role":"authenticated"}' % uid
    body = "\n".join([
        "begin;",
        "set local role authenticated;",
        "set local request.jwt.claims = '%s';" % claims,
        setup,
        sql,
        "rollback;",
    ])
    r = subprocess.run(
        ["docker", "exec", "-i", "supabase_db_workhive",
         "psql", "-U", "postgres", "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-t", "-A"],
        input=body, capture_output=True, text=True, timeout=120)
    if r.returncode == 0:
        return True, (r.stdout or "").strip()
    return False, " ".join((r.stderr or "").split())


def as_person_write(uid, mutation, setup=""):
    """A MUTATION attempted as a real person, reporting HOW MANY ROWS ACTUALLY CHANGED.

    Returns (raised, changed, message).

    A ZERO-ROW WRITE IS NOT AN ERROR. PostgREST and psql both report `UPDATE 0` with a success exit
    code when RLS filters every candidate row away — so `returncode == 0` means "the statement was
    syntactically fine", never "the write landed". `as_person` alone reported that a verified top-up
    had been flipped back to pending_verification and "the server allowed it", when the row count was
    0 and RLS had refused the whole thing. A guard probe that cannot tell a refusal from a no-op will
    manufacture a defect every time the guard works.

    So the mutation is wrapped in a CTE and its RETURNING rows are counted. A refusal is proven by
    `changed == 0`; a hole is proven by `changed > 0`.
    """
    wrapped = f"with _u as ({mutation.rstrip().rstrip(';')} returning 1) select count(*) from _u;"
    ok, out = as_person(uid, wrapped, setup)
    if not ok:
        return True, 0, out
    nums = [ln.strip() for ln in out.splitlines() if ln.strip().isdigit()]
    return False, (int(nums[-1]) if nums else 0), out


def a_person():
    """Any real, signed-in, non-admin identity to probe as."""
    return one("""select sp.auth_uid::text from service_providers sp
                   where sp.auth_uid is not null order by sp.created_at limit 1""")


def attempt(sql, setup=""):
    """Run `sql` inside a transaction that is ALWAYS rolled back, and report what the server said.

    Returns (ok, message). ok=True means the statement was accepted — which for a guard probe is the
    FAILURE case. The whole thing is one psql call with an explicit rollback, so there is no window in
    which a half-applied probe can survive this process dying (the lesson from the autocommit incident
    that made a teeth-test permanent).
    """
    body = f"begin;\n{setup}\n{sql}\nrollback;"
    r = subprocess.run(
        ["docker", "exec", "-i", "supabase_db_workhive",
         "psql", "-U", "postgres", "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-t", "-A"],
        input=body, capture_output=True, text=True, timeout=120)
    if r.returncode == 0:
        return True, (r.stdout or "").strip()
    err = (r.stderr or "").strip().replace("\n", " ")
    return False, err


# ═══════════════════════════════════════════════════════════════════════════════════════════════════
# TOP-UPS — the only way a credit is born
# ═══════════════════════════════════════════════════════════════════════════════════════════════════

def topup_mints_exactly_once():
    """Every VERIFIED top-up must have exactly one matching ledger row, for its own amount. Not 'at
    least one' — a double-mint is the defect this is looking for, and 'at least one' would pass it."""
    rows = qjson("""
        select t.id::text as id, t.amount::text as amount,
               (select count(*) from service_credit_ledger l
                 where l.entry_type = 'topup' and l.ref_id = t.id) as n,
               (select coalesce(sum(l.amount),0)::text from service_credit_ledger l
                 where l.entry_type = 'topup' and l.ref_id = t.id) as minted
          from service_credit_topups t
         where t.status = 'verified'""")
    if not rows:
        return "needs-live", "no verified top-up exists to check — seed one before trusting this"
    bad = [r for r in rows if int(r["n"]) != 1 or abs(float(r["minted"]) - float(r["amount"])) > 0.005]
    if bad:
        return "fail", (f"{len(bad)} of {len(rows)} verified top-ups do not mint exactly their own "
                        f"amount once: " + "; ".join(
                            f"{r['id'][:8]} amount {r['amount']} -> {r['n']} row(s) totalling {r['minted']}"
                            for r in bad[:3]))
    total = sum(float(r["amount"]) for r in rows)
    return "pass", (f"all {len(rows)} verified top-ups minted exactly once for exactly their own "
                    f"amount ({total:.2f} in total)")


def unverified_topup_mints_nothing():
    """A top-up awaiting verification is a claim, not money. It must have minted nothing at all."""
    rows = qjson("""
        select t.status, count(*) as n,
               coalesce(sum((select count(*) from service_credit_ledger l
                              where l.entry_type='topup' and l.ref_id = t.id)),0) as minted
          from service_credit_topups t
         where t.status <> 'verified'
         group by t.status""")
    if not rows:
        return "needs-live", "no unverified top-up exists to check"
    leaked = [r for r in rows if int(r["minted"]) > 0]
    if leaked:
        return "fail", ("credits were minted for top-ups that are not verified: " +
                        "; ".join(f"{r['status']}: {r['minted']} ledger row(s) across {r['n']}"
                                  for r in leaked))
    return "pass", ("; ".join(f"{int(r['n'])} {r['status']} top-up(s) minted 0 credits"
                              for r in rows))


def verified_topup_cannot_be_unverified():
    """A verification is not reversible by an UPDATE: flipping a verified row back would leave the
    credits minted with nothing claiming them. Control case first — an innocuous UPDATE on the same
    row must succeed, or a refusal here would prove only that the row is unwritable."""
    tid = one("select id::text from service_credit_topups where status='verified' limit 1")
    if not tid:
        return "needs-live", "no verified top-up exists to attempt a reversal on"
    uid = a_person()
    if not uid:
        return "needs-live", "no signed-in identity exists to attempt the reversal as"
    # Counted, not merely attempted: RLS answers a forbidden UPDATE with `UPDATE 0` and a success
    # exit code, and reading that as "the server allowed it" invents a defect out of a working rule.
    _raised_c, changed_c, _ = as_person_write(
        uid, f"update service_credit_topups set note = coalesce(note,'') || '' where id = '{tid}'")
    raised_f, changed_f, msg = as_person_write(
        uid, f"update service_credit_topups set status='pending_verification' where id = '{tid}'")
    if changed_f > 0:
        return "fail", (f"a verified top-up was flipped back to pending_verification and {changed_f} "
                        f"row(s) actually changed — the credits it minted stay minted, claimed by a "
                        f"row that now says they were never verified")
    how = ("raised: " + msg[-120:]) if raised_f else "RLS matched no row to update (UPDATE 0)"
    if changed_c == 0:
        return "pass", (f"this identity cannot write the row at all (the innocuous control UPDATE "
                        f"also changed 0 rows), so the verification cannot be undone by them — "
                        f"{how}")
    return "pass", (f"an innocuous UPDATE on the same row changed {changed_c} row(s), and "
                    f"verified -> pending_verification changed 0 — {how}")


# ═══════════════════════════════════════════════════════════════════════════════════════════════════
# COMMISSION — the one entry that DESTROYS rather than moves
# ═══════════════════════════════════════════════════════════════════════════════════════════════════

def commission_is_paired_with_retirement():
    """Mig 53. A commission takes credits off a provider AND out of circulation, so it must move the
    treasury as well as the ledger. This reads the deployed function, not the migration file — what
    matters is what the database is running."""
    src = whole("""select pg_get_functiondef(oid) from pg_proc
                  where proname='mint_settlement_commission' and pronamespace='public'::regnamespace""")
    if not src:
        return "fail", "mint_settlement_commission() is not installed"
    inserts = "service_credit_ledger" in src
    retires = "retire_credits" in src
    if inserts and not retires:
        return "fail", ("mint_settlement_commission writes a negative ledger row and never calls "
                        "retire_credits — issued_credits will drift above the ledger by the whole "
                        "commission history, exactly as it did before mig 53")
    if not inserts:
        return "fail", "mint_settlement_commission no longer writes a ledger row at all"
    return "pass", "the deployed function writes the ledger row AND retires the same amount"


def commission_default_is_zero():
    """Ian's economy is a flat 10% reward with no commission. The knob is the policy, and its platform
    default must be 0 — a non-zero default would charge every hive that never set one."""
    hives = qjson("""select h.id::text as id, h.name,
                            public.service_knob_pct(h.id,'commission_pct')::text as pct
                       from hives h limit 20""")
    if not hives:
        return "needs-live", "no hive exists to read the knob for"
    charging = [h for h in hives if float(h["pct"]) != 0]
    if charging:
        return "fail", ("commission_pct is non-zero for " +
                        "; ".join(f"{h['name']}={h['pct']}%" for h in charging[:4]) +
                        " — the flat-10%-reward economy charges no commission")
    return "pass", f"commission_pct is 0 for all {len(hives)} hives read"


def retired_entry_types_are_absent():
    """Cashback and vouchers were retired from the economy. The CHECK constraint still permits them —
    which is fine, a constraint is not a policy — but no row may exist, and nothing may write one."""
    rows = qjson("""select entry_type, count(*) as n from service_credit_ledger
                     where entry_type in ('cashback','voucher_grant','voucher_reimburse')
                     group by entry_type""")
    if rows:
        return "fail", ("retired entry types are present in the ledger: " +
                        ", ".join(f"{r['entry_type']}={r['n']}" for r in rows))
    return "pass", "no cashback, voucher_grant or voucher_reimburse row exists"


# ═══════════════════════════════════════════════════════════════════════════════════════════════════
# THE REWARD — 10% of a purchase, earned or spent but never both
# ═══════════════════════════════════════════════════════════════════════════════════════════════════

def _priced_job():
    """A settled-or-priced service job with a provider, which the reward guards need to act on."""
    return one("""select r.id::text from service_requests r
                   where r.matched_provider_id is not null
                     and coalesce(public.service_request_price(r.id),0) > 0
                   order by r.created_at desc limit 1""")


def reward_spend_capped_at_the_knob():
    """Credits may cover at most `reward_spend_cap_pct` of a purchase. Asserted both ways: a spend one
    peso over the cap is refused, and a spend AT the cap is accepted — a guard that refuses everything
    is not a cap, it is an outage."""
    job = _priced_job()
    if not job:
        return "needs-live", "no priced job with a matched provider exists to price a reward against"
    facts = qjson(f"""select public.service_request_price('{job}')::text as price,
                             public.service_knob_pct(r.hive_id,'reward_spend_cap_pct')::text as pct,
                             r.matched_provider_id::text as prov
                        from service_requests r where r.id='{job}'""")[0]
    price, pct = float(facts["price"]), float(facts["pct"])
    cap = round(price * pct / 100.0, 2)
    if cap <= 0:
        return "needs-live", f"the cap computes to {cap} on this job, so there is no boundary to test"
    # The account must be able to AFFORD the spend, or a refusal would be about the balance, not the
    # cap. Funded inside the same rolled-back transaction.
    fund = (f"insert into service_credit_ledger (account_type,account_id,entry_type,amount,"
            f"ref_kind,ref_id,note) values ('provider','{facts['prov']}','topup',{cap*4:.2f},"
            f"'topup',null,'probe funding, rolled back');")
    spend = (lambda amt: f"insert into service_credit_ledger (account_type,account_id,entry_type,"
                         f"amount,ref_kind,ref_id,note) values ('provider','{facts['prov']}',"
                         f"'reward_spend',{-amt:.2f},'service_request','{job}','probe, rolled back');")
    ok_at, msg_at = attempt(spend(cap), setup=fund)
    ok_over, msg_over = attempt(spend(cap + 1), setup=fund)
    if not ok_at:
        return "fail", (f"a spend AT the cap ({cap:.2f} = {pct:g}% of {price:.2f}) was refused, so the "
                        f"cap is not a cap but a wall: {msg_at[-160:]}")
    if ok_over:
        return "fail", (f"a spend of {cap + 1:.2f} was ACCEPTED although the cap on this job is "
                        f"{cap:.2f} ({pct:g}% of {price:.2f}) — the cap is not enforced")
    return "pass", (f"on a job priced {price:.2f}, a reward spend of {cap:.2f} ({pct:g}%) was accepted "
                    f"and {cap + 1:.2f} was refused: {msg_over[-110:]}")


def reward_is_earn_or_spend_never_both():
    """One job pays a reward or is paid with one, never both — otherwise 10% is claimed twice on the
    same peso. Control first: a lone reward_earn must be accepted, so the refusal below is about the
    pairing and not about reward_earn being impossible."""
    job = _priced_job()
    if not job:
        return "needs-live", "no priced job with a matched provider exists"
    prov = one(f"select matched_provider_id::text from service_requests where id='{job}'")
    mk = lambda kind, amt: (
        f"insert into service_credit_ledger (account_type,account_id,entry_type,amount,ref_kind,"
        f"ref_id,note) values ('provider','{prov}','{kind}',{amt},'service_request','{job}',"
        f"'probe, rolled back');")
    ok_alone, msg_alone = attempt(mk("reward_earn", 1))
    if not ok_alone:
        return "needs-live", (f"a lone reward_earn was refused for another reason, so this cannot "
                              f"isolate the exclusivity rule: {msg_alone[-160:]}")
    ok_both, msg_both = attempt(
        mk("reward_spend", -1), setup=mk("reward_earn", 1) + "\n" +
        f"insert into service_credit_ledger (account_type,account_id,entry_type,amount,ref_kind,"
        f"ref_id,note) values ('provider','{prov}','topup',500,'topup',null,'probe, rolled back');")
    if ok_both:
        return "fail", ("the same job both EARNED and SPENT a reward and the server allowed it — 10% "
                        "can be claimed twice on one purchase")
    return "pass", (f"a lone reward_earn was accepted; earning and spending on the SAME job was "
                    f"refused: {msg_both[-150:]}")


def credits_are_non_transferable():
    """Credits are not money: they cannot be handed to another account. Ian's rule, and the reason the
    platform can mint them at all."""
    accts = qjson("""select id::text as id from service_providers
                      where auth_uid is not null order by created_at limit 2""")
    if len(accts) < 2:
        return "needs-live", "fewer than two provider accounts exist, so a transfer cannot be attempted"
    a, b = accts[0]["id"], accts[1]["id"]
    mv = (f"insert into service_credit_ledger (account_type,account_id,entry_type,amount,ref_kind,"
          f"ref_id,note) values ('provider','{a}','adjustment',-50,'transfer',null,'probe'),"
          f"('provider','{b}','adjustment',50,'transfer',null,'probe');")
    uid = a_person()
    if not uid:
        return "needs-live", "no signed-in identity exists to attempt a transfer as"
    ok, msg = as_person(uid, mv, setup=(
        f"insert into service_credit_ledger (account_type,account_id,entry_type,amount,ref_kind,"
        f"ref_id,note) values ('provider','{a}','topup',500,'topup',null,'probe, rolled back');"))
    if ok:
        return "fail", ("50 credits were moved from one account to another and the server allowed it "
                        "— credits are transferable, which makes them a currency")
    return "pass", f"an account-to-account move of 50 credits was refused: {msg[-170:]}"


def no_cash_out_path_exists():
    """The other half of non-transferable: there must be no function that turns credits back into
    pesos. Asked of the catalogue, because asking the posture view would be asking the claim itself."""
    fns = qjson("""select p.proname from pg_proc p join pg_namespace n on n.oid=p.pronamespace
                    where n.nspname='public'
                      and (p.proname ilike '%cash%out%' or p.proname ilike '%withdraw%'
                           or p.proname ilike '%redeem%' or p.proname ilike '%payout%')""")
    # A NAME IS NOT A BEHAVIOUR. `redeem_service_voucher` matched this pattern and pays nothing at
    # all — its whole body returns {ok:false, "Vouchers are retired"} — so the first version of this
    # check reported a cash-out path that does not exist. Read what the function DOES: a payout has to
    # move value, which means a ledger insert, an issue_credits(), or an UPDATE of a balance.
    paying = []
    for f in fns:
        body = whole("select pg_get_functiondef(oid) from pg_proc where proname = '%s' "
                     "and pronamespace='public'::regnamespace" % f["proname"])
        if ("service_credit_ledger" in body or "issue_credits" in body
                or "retire_credits" in body or "update public.credit" in body):
            paying.append(f["proname"])
    if paying:
        return "fail", ("functions exist that actually move credits out: " + ", ".join(paying))
    posture = one("select no_cash_out_function::text from v_credit_posture limit 1")
    return "pass", (f"no cash-out, withdraw, redeem or payout function exists in public; "
                    f"v_credit_posture agrees (no_cash_out_function={posture})")


# ═══════════════════════════════════════════════════════════════════════════════════════════════════
# BALANCES AND SETTLEMENT
# ═══════════════════════════════════════════════════════════════════════════════════════════════════

def no_account_is_overdrawn():
    """No running balance may be negative. A negative balance is credits that were spent twice."""
    rows = qjson("""select account_type, account_id::text as id, sum(amount)::text as bal
                      from service_credit_ledger group by account_type, account_id
                     having sum(amount) < -0.005""")
    if rows:
        return "fail", ("overdrawn accounts: " +
                        "; ".join(f"{r['account_type']} {r['id'][:8]} = {r['bal']}" for r in rows))
    n = one("select count(distinct (account_type, account_id)) from service_credit_ledger")
    return "pass", f"all {n} accounts holding ledger rows have a balance of zero or more"


def autoconfirm_names_itself():
    """A payment the sweep confirmed must say so: auto_confirmed_at set AND confirmed_by NULL. The two
    together are what let a person tell 'the system decided' from 'a human decided'."""
    rows = qjson("""select count(*) filter (where auto_confirmed_at is not null
                                              and confirmed_by is not null) as auto_and_human,
                           count(*) filter (where auto_confirmed_at is not null) as auto,
                           count(*) filter (where confirmed_by is not null) as human,
                           count(*) as total
                      from service_payments""")[0]
    if int(rows["auto_and_human"]) > 0:
        return "fail", (f"{rows['auto_and_human']} payment(s) carry BOTH auto_confirmed_at and a "
                        f"confirmed_by — the row cannot say who decided")
    if int(rows["total"]) == 0:
        return "needs-live", "no payment row exists to check"
    return "pass", (f"of {rows['total']} payments, {rows['auto']} were auto-confirmed and "
                    f"{rows['human']} confirmed by a person; none claim both")


def settlement_requires_a_payment():
    """A job cannot reach `settled` without a payment row — otherwise the ledger records a commission
    against money nobody recorded receiving."""
    src = whole("""select pg_get_functiondef(oid) from pg_proc
                  where proname='guard_settle_requires_payment'
                    and pronamespace='public'::regnamespace""")
    if not src:
        return "fail", "guard_settle_requires_payment() is not installed"
    live = one("""select count(*) from pg_trigger t join pg_proc p on p.oid = t.tgfoid
                   where p.proname = 'guard_settle_requires_payment' and not t.tgisinternal""")
    if int(live) == 0:
        return "fail", ("guard_settle_requires_payment exists but no trigger calls it — a function "
                        "nothing fires is documentation, not a guard")
    orphans = one("""select count(*) from service_requests r
                      where r.status = 'settled'
                        and not exists (select 1 from service_payments p where p.request_id = r.id)""")
    # THE GUARD AND THE HISTORY ARE DIFFERENT QUESTIONS. Three settled jobs carry no payment row, and
    # all three settled on 2026-07-28/29 — before this trigger existed. A guard cannot retroactively
    # refuse a write that already happened, so counting them as a guard failure would say the rule is
    # broken when the rule is working. Prove the guard REFUSES a new one; report the legacy rows as
    # what they are — a data repair, still owed.
    uid = a_person()
    job = one("""select r.id::text from service_requests r
                  where r.status <> 'settled'
                    and not exists (select 1 from service_payments p where p.request_id = r.id)
                  limit 1""")
    teeth = "not attempted"
    if job:
        ok_settle, msg = attempt(
            f"update service_requests set status='settled' where id='{job}';")
        if ok_settle:
            return "fail", (f"a job with no payment row was moved to settled and the server allowed "
                            f"it — the guard is installed on {live} trigger(s) and did not fire")
        teeth = f"refused: {msg[-90:]}"
    if int(orphans) > 0:
        return "fail", (f"the guard fires ({teeth}), but {orphans} settled job(s) predating it still "
                        f"carry no payment row — a data repair, not a guard hole")
    return "pass", (f"the guard is installed on {live} trigger(s) and demonstrably refuses a "
                    f"paymentless settle ({teeth}); no settled job lacks a payment row")


def starter_grant_is_once_per_person():
    """ONE PER PERSON, EVER — the sybil half of the adversarial-personas row. A second claim must be
    refused with a reason the person can act on, and the grant must be gated on a real seller profile,
    because without that gate 1,000 fake signups is PHP500,000 of credits."""
    uid = a_person()
    if not uid:
        return "needs-live", "no signed-in identity exists to claim a grant as"
    src = whole("""select pg_get_functiondef(oid) from pg_proc
                    where proname='claim_starter_grant' and pronamespace='public'::regnamespace""")
    if not src:
        return "fail", "claim_starter_grant() is not installed"
    gated = "marketplace_sellers" in src
    # Claim twice inside one rolled-back transaction. The SECOND is the assertion.
    ok, out = as_person(uid, "select public.claim_starter_grant()::text, "
                             "public.claim_starter_grant()::text;")
    if not ok:
        return "fail", f"claim_starter_grant raised rather than returning a reason: {out[-160:]}"
    # psql echoes BEGIN / SET / ROLLBACK around the result, and the LAST line is therefore the
    # transaction control word, not the answer. Taking it read "ROLLBACK" as the grant response and
    # reported a defect against a guard that was working. Keep only the rows.
    NOISE = {"BEGIN", "SET", "ROLLBACK", "COMMIT"}
    rows_out = [l.strip() for l in out.splitlines() if l.strip() and l.strip().upper() not in NOISE]
    second = rows_out[-1] if rows_out else ""
    refused = "already_claimed" in second or "granted\": false" in second or "granted\":false" in second
    if not refused:
        return "fail", (f"a SECOND starter grant was not refused — the response was {second[:160]}. "
                        f"One person, one grant is what stops a sybil farm minting credits")
    if not gated:
        return "fail", ("the grant is not gated on a real seller profile, so any fresh signup can "
                        "claim it — that is the sybil hole the gate exists to close")
    return "pass", (f"two claims in one transaction: the second was refused ({second[:90]}), and the "
                    f"grant is gated on a marketplace_sellers profile so a bare signup cannot mint")


def acceptance_refusal_names_both_amounts():
    """accept-needs-10pct: acceptance is REFUSED when the provider cannot cover the reservation, and
    the message names BOTH the amount needed and the amount held — a refusal that states only "not
    enough" leaves the person with no action to take."""
    src = whole("""select pg_get_functiondef(oid) from pg_proc
                    where proname='guard_accept_requires_reservation'
                      and pronamespace='public'::regnamespace""")
    if not src:
        return "fail", "guard_accept_requires_reservation() is not installed"
    live = one("""select count(*) from pg_trigger t join pg_proc p on p.oid=t.tgfoid
                   where p.proname='guard_accept_requires_reservation' and not t.tgisinternal""")
    if int(live) == 0:
        return "fail", "the guard exists but no trigger calls it — a function nothing fires is a comment"
    raises = "RAISE EXCEPTION" in src.upper()
    # Both figures must appear in the message the guard raises, not merely be computed.
    body = src.upper()
    names_need = "V_NEED" in body
    names_held = "V_BAL" in body
    if not (raises and names_need and names_held):
        return "fail", (f"the refusal does not name both amounts (raises={raises}, "
                        f"names the amount needed={names_need}, names the amount held={names_held})")
    return "pass", (f"installed on {live} trigger(s); it refuses acceptance and its message "
                    f"interpolates BOTH the reservation needed and the balance held, so the provider "
                    f"is told what to do about it")


CHECKS = [
    ("starter_grant_is_once_per_person", starter_grant_is_once_per_person),
    ("acceptance_refusal_names_both_amounts", acceptance_refusal_names_both_amounts),
    ("topup_mints_exactly_once", topup_mints_exactly_once),
    ("unverified_topup_mints_nothing", unverified_topup_mints_nothing),
    ("verified_topup_cannot_be_unverified", verified_topup_cannot_be_unverified),
    ("commission_is_paired_with_retirement", commission_is_paired_with_retirement),
    ("commission_default_is_zero", commission_default_is_zero),
    ("retired_entry_types_are_absent", retired_entry_types_are_absent),
    ("reward_spend_capped_at_the_knob", reward_spend_capped_at_the_knob),
    ("reward_is_earn_or_spend_never_both", reward_is_earn_or_spend_never_both),
    ("credits_are_non_transferable", credits_are_non_transferable),
    ("no_cash_out_path_exists", no_cash_out_path_exists),
    ("no_account_is_overdrawn", no_account_is_overdrawn),
    ("autoconfirm_names_itself", autoconfirm_names_itself),
    ("settlement_requires_a_payment", settlement_requires_a_payment),
]


def run_all():
    out = {}
    for name, fn in CHECKS:
        try:
            out[name] = fn()
        except Exception as exc:                      # an exception is a failed check, not a skip
            out[name] = ("fail", f"the check itself raised {type(exc).__name__}: {exc}")
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    res = run_all()
    # per-run artifact so bank rows citing this harness can be honestly re-stamped: the recency rail
    # compares the artifact's mtime against each row's dep mtimes, and a harness with no artifact
    # has no word (the paginated-order-totality lesson, 2026-08-21).
    import os as _os
    with open(_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                            "money_lifecycle_report.json"), "w", encoding="utf-8") as f:
        json.dump({k: {"status": v[0], "detail": str(v[1])[:300]} for k, v in res.items()}, f, indent=1)
    if a.json:
        print(json.dumps({k: {"status": v[0], "detail": v[1]} for k, v in res.items()}, indent=1))
        return 0 if not any(v[0] == "fail" for v in res.values()) else 1

    print(f"{BOLD}The money lifecycle, asked of the database{RST}")
    order = {"fail": 0, "needs-live": 1, "pass": 2}
    for name, (st, why) in sorted(res.items(), key=lambda kv: order.get(kv[1][0], 3)):
        tag = {"pass": f"{GREEN}PASS{RST}", "fail": f"{RED}FAIL{RST}"}.get(st, f"{YEL}????{RST}")
        print(f"  {tag}  {name:38} {why}")
    bad = sum(1 for v in res.values() if v[0] == "fail")
    live = sum(1 for v in res.values() if v[0] == "needs-live")
    ok = sum(1 for v in res.values() if v[0] == "pass")
    print(f"\n  {ok} hold · {bad} broken · {live} could not be asked with the data present")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
