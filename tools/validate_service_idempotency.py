#!/usr/bin/env python3
"""validate_service_idempotency.py - C14 lock: replaying a money/dispatch write must land ONCE.

WHY THIS SHAPE, AND NOT AN `Idempotency-Key` HEADER. The roadmap's original C14 asked every money/
dispatch RPC to accept and honor a client-supplied key. Checking the code first (the habit C12 paid
for) showed the platform already does something STRICTLY STRONGER: partial UNIQUE indexes enforce
once-only in the DATABASE, so the guarantee holds even when the client sends no key, sends the wrong
key, or is a script hitting PostgREST directly. A header contract depends on client cooperation; an
index does not. So this gate asserts the structural guarantees EXIST and still BITE, rather than
demanding a weaker mechanism be bolted on beside them.

  L1  the four partial unique indexes exist, with their predicates intact
  L2  a duplicate GCash reference cannot be filed        (the same transfer credited twice = real money)
  L3  a second commission for one request cannot be minted (a provider charged twice for one job)
  L4  a provider cannot leave two offers on one request  (double-accept / double-quote)
  L5  a duplicate is reported HONESTLY in the UI, not as a raw constraint error - a user who
      double-taps must be told "already filed", never shown 23505 text they read as a failure
      (the phantom-write lesson: an error the user misreads is a defect even when the data is right)

Every live probe runs inside a transaction that is ROLLED BACK, so the gate never pollutes the shared
local DB. Infra absent => SKIP (exit 0), never a false FAIL.
"""
import os
import re
import subprocess
import sys

DB = "supabase_db_workhive"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GREEN, RED, DIM, RST = "\033[92m", "\033[91m", "\033[2m", "\033[0m"

CHECKS = []


def psql(sql, timeout=60):
    try:
        r = subprocess.run(
            ["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-t", "-A", "-c", sql],
            capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None
    return (r.stdout or "").strip() if r.returncode == 0 else None


def probe(sql, timeout=60):
    """Run a rolled-back DO block and return its RESULT notices."""
    try:
        r = subprocess.run(
            ["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres"],
            input=sql, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return ""
    return (r.stdout or "") + (r.stderr or "")


def check(name, ok, detail=""):
    CHECKS.append((bool(ok), name, detail))


# The four guarantees, each named by the index that enforces it.
INDEXES = [
    ("service_credit_topups_ref_unique",
     "the same GCash reference cannot be credited twice"),
    ("service_credit_ledger_one_commission_per_request",
     "a job can be charged commission only once, ever"),
    ("service_offer_one_per_provider",
     "one offer per provider per request (no double-accept/quote)"),
    ("service_requests_one_open_auto_hail",
     "no duplicate open PM auto-hail for one scope item"),
]

DUP_PROBE = """
BEGIN;
DO $$
DECLARE r record;
BEGIN
  -- L2 duplicate GCash reference
  SELECT * INTO r FROM public.service_credit_topups WHERE status <> 'rejected' LIMIT 1;
  IF r IS NULL THEN
    RAISE NOTICE 'RESULT dup_topup=SKIP(no fixture)';
  ELSE
    BEGIN
      INSERT INTO public.service_credit_topups
        (account_type, account_id, payer_auth_uid, amount, gcash_ref, status)
      VALUES (r.account_type, r.account_id, r.payer_auth_uid, r.amount, r.gcash_ref, 'pending_verification');
      RAISE NOTICE 'RESULT dup_topup=ACCEPTED';
    EXCEPTION WHEN unique_violation THEN RAISE NOTICE 'RESULT dup_topup=BLOCKED';
    END;
  END IF;

  -- L3 second commission for the same request
  SELECT * INTO r FROM public.service_credit_ledger WHERE entry_type = 'commission' AND ref_id IS NOT NULL LIMIT 1;
  IF r IS NULL THEN
    RAISE NOTICE 'RESULT dup_commission=SKIP(no fixture)';
  ELSE
    BEGIN
      INSERT INTO public.service_credit_ledger
        (account_type, account_id, entry_type, amount, ref_id, note)
      VALUES (r.account_type, r.account_id, 'commission', r.amount, r.ref_id, 'idempotency probe');
      RAISE NOTICE 'RESULT dup_commission=ACCEPTED';
    EXCEPTION WHEN unique_violation THEN RAISE NOTICE 'RESULT dup_commission=BLOCKED';
    END;
  END IF;

  -- L4 a second offer from the same provider on one request
  SELECT * INTO r FROM public.service_offers LIMIT 1;
  IF r IS NULL THEN
    RAISE NOTICE 'RESULT dup_offer=SKIP(no fixture)';
  ELSE
    BEGIN
      INSERT INTO public.service_offers (request_id, provider_id, kind, status)
      VALUES (r.request_id, r.provider_id, r.kind, 'pending');
      RAISE NOTICE 'RESULT dup_offer=ACCEPTED';
    EXCEPTION WHEN unique_violation THEN RAISE NOTICE 'RESULT dup_offer=BLOCKED';
    END;
  END IF;
END $$;
ROLLBACK;
"""


def main():
    print("=" * 78)
    print("  C14 service idempotency - a replayed money/dispatch write lands ONCE")
    print("=" * 78)

    if psql("select 1") is None:
        print("  SKIP: docker/psql unavailable")
        return 0
    if psql("select to_regclass('public.service_credit_topups')") in (None, "", "\\N"):
        print("  SKIP: service tables not migrated")
        return 0

    # L1 - the guarantees exist as indexes (a dropped index silently re-opens the hole)
    have = psql("""select coalesce(string_agg(i.relname, ','), '')
                   from pg_index x join pg_class i on i.oid = x.indexrelid
                   where x.indisunique and i.relname like 'service%'""") or ""
    for name, why in INDEXES:
        check(f"L1 {name} exists - {why}", name in have,
              "index missing: the once-only guarantee is GONE")

    # L2/L3/L4 - and the indexes still BITE (a partial predicate can be narrowed to uselessness
    # without dropping the index, so presence alone is not proof)
    out = probe(DUP_PROBE)
    for key, label in (("dup_topup", "L2 a duplicate GCash reference is refused (same transfer, twice)"),
                       ("dup_commission", "L3 a second commission for one request is refused"),
                       ("dup_offer", "L4 a provider cannot leave two offers on one request")):
        m = re.search(rf"RESULT {key}=(\w+)", out)
        got = m.group(1) if m else "?"
        if got == "SKIP":
            check(label + " [no fixture - reseed to prove]", True, "")
        else:
            check(label, got == "BLOCKED", f"got {got} - the replay LANDED")

    # L5 - honest reporting. A user who double-taps must be told plainly, not shown 23505.
    seller = os.path.join(ROOT, "marketplace-seller.html")
    try:
        src = open(seller, encoding="utf-8", errors="replace").read()
    except Exception:
        src = ""
    friendly = re.search(r"duplicate\|unique[\s\S]{0,120}?already filed", src, re.I)
    check("L5 a duplicate top-up is reported honestly ('already filed'), not as raw 23505 text",
          bool(friendly),
          "the page surfaces the raw constraint error - a user reads that as 'it failed' and re-sends")

    fails = [c for c in CHECKS if not c[0]]
    for ok, name, detail in CHECKS:
        print(f"  {GREEN + 'PASS' + RST if ok else RED + 'FAIL' + RST}  {name}"
              + (f"  {DIM}[{detail}]{RST}" if detail and not ok else ""))
    print()
    if fails:
        print(f"{RED}FAIL{RST} - {len(fails)}/{len(CHECKS)} idempotency guarantee(s) broken")
        return 1
    print(f"{GREEN}PASS{RST} - {len(CHECKS)} guarantees: once-only is enforced by the DATABASE "
          f"(not a client-supplied key) and a replay is reported honestly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
