#!/usr/bin/env python3
"""
Validator: engineering_calcs WRITE-side tenant isolation (deep-arc P2 / I-2 + I-4), LIVE.

The two-tenant read prover (validate_rls_tenant_isolation.py) proves a hive-A member cannot
READ hive-B rows. It does NOT test the WRITE side. engineering_calcs_write used to be
`FOR ALL WITH CHECK (auth.uid() IS NOT NULL)` — so any authed user could INSERT a row
attributed to ANOTHER user or into ANOTHER hive. The P2 migration split it into
INSERT/UPDATE/DELETE policies that each require `auth_uid = auth.uid()` (+ hive membership).

This gate proves the ACTUAL running DB enforces it (not just that a migration file has the
text — a later migration could drop the policy). Inside ONE transaction, ROLLBACK at the end:
  - act as an active member u_a (SET LOCAL role authenticated + request.jwt.claims sub=u_a)
  - INSERT with auth_uid = SOME OTHER user  -> MUST be rejected (RLS WITH CHECK)   [I-2]
  - INSERT with auth_uid = u_a (solo row)   -> MUST succeed                         [regression]
A foreign-attribution insert that SUCCEEDS = a write-side isolation LEAK.

Live (needs the local supabase_db_workhive container). Mutates nothing (ROLLBACK).

Run:        python tools/validate_engdesign_write_isolation.py
Self-test:  python tools/validate_engdesign_write_isolation.py --self-test
"""
import subprocess
import sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

DB = "supabase_db_workhive"

PROBE_SQL = r"""
BEGIN;
DO $do$
DECLARE u_a uuid; u_other uuid; v_stored uuid;
BEGIN
  SELECT auth_uid INTO u_a FROM public.hive_members
    WHERE auth_uid IS NOT NULL AND status='active' LIMIT 1;
  SELECT id INTO u_other FROM auth.users WHERE id <> u_a LIMIT 1;
  IF u_a IS NULL OR u_other IS NULL THEN RAISE NOTICE 'SKIP|need >=2 users'; RETURN; END IF;

  SET LOCAL role authenticated;
  PERFORM set_config('request.jwt.claims', json_build_object('sub', u_a, 'role','authenticated')::text, true);

  -- (1) foreign attribution: auth_uid = another user. The row MUST NOT be STORED with the foreign
  -- auth_uid. Isolation is SAFE via EITHER mechanism: the WITH CHECK rejects the write, OR the
  -- trg_bind_submitter_engineering_calc BEFORE-INSERT trigger overwrites auth_uid := auth.uid() (the
  -- platform's attribution-pin pattern, added in the migs-010/011/012 sweep). A LEAK is ONLY a row
  -- ACTUALLY STORED with the foreign auth_uid, verified via RETURNING, not by insert-success alone.
  -- (2026-07-18: the test predated the bind trigger and false-failed on the safe correct-and-succeed
  -- path; empirically re-proven that the forged auth_uid is pinned to the caller, never stored.)
  BEGIN
    INSERT INTO public.engineering_calcs (auth_uid, hive_id, calc_type, project_name)
      VALUES (u_other, NULL, 'probe', 'WRITE-ISO PROBE')
      RETURNING auth_uid INTO v_stored;
    IF v_stored = u_other THEN
      RAISE NOTICE 'LEAK|foreign-auth_uid-STORED';
    ELSIF v_stored = u_a THEN
      RAISE NOTICE 'OK|foreign-attribution-pinned-to-caller';
    ELSE
      RAISE NOTICE 'LEAK|foreign-auth_uid-unexpected|%', v_stored;
    END IF;
  EXCEPTION WHEN others THEN RAISE NOTICE 'OK|foreign-insert-blocked';
  END;

  -- (2) self attribution (solo row): auth_uid = self, hive null -> must succeed
  BEGIN
    INSERT INTO public.engineering_calcs (auth_uid, hive_id, calc_type, project_name)
      VALUES (u_a, NULL, 'probe', 'WRITE-ISO PROBE');
    RAISE NOTICE 'OK|self-insert-allowed';
  EXCEPTION WHEN others THEN RAISE NOTICE 'FAIL|self-insert-blocked|%', SQLERRM;
  END;
END $do$;
ROLLBACK;
"""


def _psql(sql):
    p = subprocess.run(
        ["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-v", "ON_ERROR_STOP=0"],
        input=sql, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return (p.stdout or "") + (p.stderr or "")


def run():
    out = _psql(PROBE_SQL)
    notices = [ln.split("NOTICE:")[1].strip() for ln in out.splitlines() if "NOTICE:" in ln]
    print("=" * 60)
    print("engineering_calcs WRITE-side isolation (deep-arc P2 / I-2)")
    print("=" * 60)
    for n in notices:
        print("  psql:", n)

    if any(n.startswith("SKIP") for n in notices):
        print("\nSKIP — insufficient users to prove isolation (not a failure).")
        return 0
    foreign_blocked = any("foreign-insert-blocked" in n for n in notices)
    foreign_pinned  = any("foreign-attribution-pinned" in n for n in notices)
    leak            = any(n.startswith("LEAK") for n in notices)
    self_ok         = any("self-insert-allowed" in n for n in notices)

    problems = []
    # Isolation is SAFE if the foreign-auth_uid write was REJECTED (WITH CHECK) OR the stored auth_uid
    # was PINNED to the caller by the bind trigger. A LEAK notice (a row actually STORED with the
    # foreign auth_uid) is always a failure.
    if leak or not (foreign_blocked or foreign_pinned):
        problems.append("WRITE-ISOLATION LEAK: an authed user CAN store a row attributed to another user (auth_uid neither rejected nor pinned to the caller)")
    if not self_ok:
        problems.append("REGRESSION: a legitimate self-attributed insert was blocked (policy too strict)")

    if problems:
        print("\nFAIL:")
        for p in problems:
            print("  x", p)
        return 1
    print("\nPASS - foreign auth_uid rejected OR pinned to the caller (no foreign-attributed row stored); self insert allowed.")
    return 0


def self_test():
    """Prove teeth: a real LEAK (foreign auth_uid STORED) is a failure; the safe bind-trigger
    correction (auth_uid pinned to the caller) is a pass; a hard WITH-CHECK reject is a pass."""
    def is_fail(notices):
        foreign_blocked = any("foreign-insert-blocked" in n for n in notices)
        foreign_pinned  = any("foreign-attribution-pinned" in n for n in notices)
        leak            = any(n.startswith("LEAK") for n in notices)
        self_ok         = any("self-insert-allowed" in n for n in notices)
        return (leak or not (foreign_blocked or foreign_pinned)) or (not self_ok)
    leak_case   = is_fail(["LEAK|foreign-auth_uid-STORED", "OK|self-insert-allowed"])            # MUST fail
    pinned_case = is_fail(["OK|foreign-attribution-pinned-to-caller", "OK|self-insert-allowed"])  # MUST pass
    reject_case = is_fail(["OK|foreign-insert-blocked", "OK|self-insert-allowed"])                # MUST pass
    ok = leak_case and (not pinned_case) and (not reject_case)
    print("SELF-TEST", "PASS" if ok else "FAIL", "(LEAK stored=fail · pinned-to-caller=pass · reject=pass)")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    sys.exit(run())
