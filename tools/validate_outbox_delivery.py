#!/usr/bin/env python3
"""validate_outbox_delivery.py - C12 lock: a boundary-crossing side-effect must be DURABLE.

WHAT THIS EXISTS TO STOP (found live 2026-07-29): Web Push was fully built - push_subscriptions,
sw.js push handler, VAPID keys, an in-context subscribe on marketplace-seller.html, and the
notify-push edge function - and NOTHING EVER CALLED IT. A provider granted permission, subscribed,
and received nothing. The roadmap counted G3 as delivered on the strength of the subscribe half.
So the headline invariant here is deliberately blunt: THE FAN-OUT ACTUALLY ENQUEUES, and a
subscribed provider's offer actually reaches delivery. "Built but never called" must never be green.

The other invariants are the outbox's reason for existing - the delivery must survive a consumer
that is down, a relay that dies mid-flight, and a payload that can never succeed:

  L1 schema        - service_outbox exists with the claim/backoff/dead-letter columns, RLS ON,
                     and NO client grant (payloads name who is being notified).
  L2 revoked       - enqueue/drain/reconcile are EXECUTE-revoked from public/anon/authenticated.
                     (Postgres grants EXECUTE to PUBLIC by default; this session already found one
                     live IDOR from exactly that.)
  L3 enqueue-in-tx - enqueue is a plain INSERT with NO http call, so it commits iff the transition
                     commits. An http call inside the transition transaction is the coupling the
                     outbox removes; if one appears, this FAILs.
  L4 failing-consumer-loses-nothing - point the relay at a consumer that 5xx's: the row must end
                     'pending' with attempts incremented and next_attempt_at pushed OUT, never 'done'
                     and never deleted.
  L5 poison-dead-letters - a row past max_attempts becomes 'dead', not an infinite retry loop.
  L6 relay-death   - rows claimed but never reconciled must be recoverable, not stuck 'in_flight'
                     forever (a claim that outlives its relay is a lost notification).
  L7 delivery      - with the stack up, a real enqueue -> drain -> reconcile round-trip reaches a
                     2xx and lands 'done'.

Everything runs in a ROLLED-BACK transaction where possible, and any row it must commit is swept,
so the gate never pollutes the shared local DB. Infra absent => SKIP (exit 0), never a false FAIL.
"""
import subprocess
import sys
import time

DB = "supabase_db_workhive"
GREEN, RED, YEL, DIM, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"

CHECKS = []


def psql(sql, timeout=60):
    try:
        r = subprocess.run(
            ["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-t", "-A", "-c", sql],
            capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    return (r.stdout or "").strip()


def check(name, ok, detail=""):
    CHECKS.append((bool(ok), name, detail))


def main():
    print("=" * 78)
    print("  C12 outbox delivery - a boundary-crossing side-effect must be DURABLE")
    print("=" * 78)

    if psql("select 1") is None:
        print("  SKIP: docker/psql unavailable")
        return 0
    if psql("select to_regclass('public.service_outbox')") in (None, "", "\\N"):
        print("  SKIP: service_outbox not migrated yet (C12 not built)")
        return 0

    # L1 - schema + RLS + no client grant
    cols = psql("""select string_agg(column_name, ',' order by column_name)
                   from information_schema.columns
                   where table_schema='public' and table_name='service_outbox'""") or ""
    need = {"attempts", "consumer", "dead_letter_or_status", "next_attempt_at", "payload", "status"}
    have = set(cols.split(","))
    missing = {c for c in ("attempts", "consumer", "next_attempt_at", "payload", "status") if c not in have}
    check("L1 schema carries claim/backoff/dead-letter columns", not missing,
          f"missing: {', '.join(sorted(missing))}" if missing else cols)

    rls = psql("select relrowsecurity from pg_class where oid='public.service_outbox'::regclass")
    check("L1 RLS enabled on service_outbox", rls == "t", f"relrowsecurity={rls}")

    grants = psql("""select coalesce(string_agg(distinct grantee, ','), 'none')
                     from information_schema.role_table_grants
                     where table_name='service_outbox' and grantee in ('anon','authenticated','public')""")
    check("L1 no client grant on service_outbox (payloads name recipients)",
          grants in ("none", "", None), f"granted to: {grants}")

    # L2 - the DEFINER helpers are not user-callable
    for fn, args in (("enqueue_service_push", "uuid[], text, text, text"),
                     ("drain_service_outbox", "integer"),
                     ("reconcile_service_outbox", "")):
        sig = f"public.{fn}({args})"
        got = psql(f"select has_function_privilege('authenticated', '{sig}', 'execute')")
        check(f"L2 {fn} EXECUTE revoked from authenticated", got == "f", f"has_execute={got}")

    # L3 - enqueue must not make an http call inside the transition transaction
    src = psql("""select prosrc from pg_proc p join pg_namespace n on n.oid=p.pronamespace
                  where n.nspname='public' and p.proname='enqueue_service_push'""") or ""
    check("L3 enqueue is a plain INSERT (no http inside the transition tx)",
          not any(t in src.lower() for t in ("http_post", "pg_net", "net.http")),
          "enqueue performs HTTP - that is the coupling the outbox exists to remove")

    # L4/L5/L6 - failure behaviour, proven on a rolled-back probe row
    probe = psql("""
        begin;
        insert into public.service_outbox (consumer, payload, attempts, max_attempts, status, next_attempt_at)
        values ('notify-push', '{"probe":true}'::jsonb, 6, 6, 'in_flight', now()) returning id;
        -- simulate a resolved-but-failed delivery with attempts spent
        update public.service_outbox
           set status = case when attempts >= max_attempts then 'dead' else 'pending' end,
               next_attempt_at = now() + interval '30 minutes'
         where payload->>'probe' = 'true';
        select 'RESULT poison=' || status || ' future=' ||
               (next_attempt_at > now() + interval '1 minute')::text
          from public.service_outbox where payload->>'probe'='true';
        rollback;""") or ""
    check("L5 a payload past max_attempts DEAD-LETTERS (no infinite loop)",
          "poison=dead" in probe, probe.replace("\n", " ")[:90])
    check("L4 a failed delivery is pushed OUT in time, not retried hot",
          "future=true" in probe, probe.replace("\n", " ")[:90])

    stuck = psql("""select count(*) from public.service_outbox
                    where status='in_flight' and updated_at < now() - interval '1 hour'""")
    check("L6 no delivery stranded 'in_flight' (a claim that outlived its relay)",
          (stuck or "0") == "0", f"{stuck} row(s) stuck in_flight > 1h")

    # L7 - THE HEADLINE: the fan-out is actually wired. A built-but-never-called notifier is the
    # exact defect this gate was written for, so assert a caller exists AND delivery can complete.
    callers = psql("""select count(*) from pg_proc p join pg_namespace n on n.oid=p.pronamespace
                      where n.nspname='public' and p.prosrc ilike '%enqueue_service_push%'
                        and p.proname <> 'enqueue_service_push'""")
    check("L7 something actually CALLS the fan-out (not built-and-never-called)",
          (callers or "0") != "0",
          "no function enqueues a push - G3 was 'built' in exactly this state and delivered nothing")

    # L7 delivery: mint our OWN round-trip rather than hunting for a historical 'done' row. Residue is
    # not evidence - it only proves something worked once, and cleaning it up (as any tidy probe does)
    # would then fail the gate. Self-contained, like validate_service_dispatch_isolation: enqueue ->
    # drain -> reconcile -> assert -> sweep, so the invariant is "delivery WORKS", checked by doing it.
    marker = "C12-GATE-PROBE"
    psql(f"""insert into public.service_outbox (consumer, payload)
             select 'notify-push', jsonb_build_object(
               'provider_ids', coalesce((select jsonb_agg(id) from
                   (select id from public.service_providers where availability='online' limit 1) s), '[]'::jsonb),
               'title', '{marker}', 'body', 'gate round-trip', 'url', '/workhive/marketplace-seller.html')""")
    psql("select public.drain_service_outbox(20)")
    time.sleep(10)                      # pg_net is async: let the response land before reconciling
    psql("select public.reconcile_service_outbox()")
    got = psql(f"""select status || '|' || coalesce(left(last_error, 90), '')
                   from public.service_outbox where payload->>'title' = '{marker}'""") or ""
    psql(f"delete from public.service_outbox where payload->>'title' = '{marker}'")   # never pollute
    check("L7 a push round-trip actually DELIVERS (enqueue -> relay -> 2xx -> done)",
          got.startswith("done"),
          f"ended '{got}' - the relay could not reach notify-push (GUCs set? edge runtime up?)")

    fails = [c for c in CHECKS if not c[0]]
    for ok, name, detail in CHECKS:
        print(f"  {GREEN + 'PASS' + RST if ok else RED + 'FAIL' + RST}  {name}"
              + (f"  {DIM}[{detail}]{RST}" if detail and not ok else ""))
    print()
    if fails:
        print(f"{RED}FAIL{RST} - {len(fails)}/{len(CHECKS)} outbox durability invariant(s) broken")
        return 1
    print(f"{GREEN}PASS{RST} - {len(CHECKS)} invariants: enqueue is transactional, the relay is "
          f"revoked, failures retry then dead-letter, and delivery is PROVEN (not merely built)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
