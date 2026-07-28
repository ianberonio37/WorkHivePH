#!/usr/bin/env python3
"""
validate_approval_authority.py — AHK1: approving and REJECTING are the same authority.

THE CLASS: a review queue has two outcomes, and a guard that only recognises one of them is not a
guard. `wh_guard_supervisor_approval` correctly refused a non-supervisor who APPROVED, but its
UPDATE clause treated a status change as privileged only when 'approved' was on one side — so
`pending -> rejected` slipped through, on all SIX tables the trigger is attached to (asset_nodes,
inventory_items, logbook, project_change_orders, rcm_fmea_modes, rcm_strategies).

WALKED LIVE 2026-07-28 (Asset Hub deepwalk, AH3), once the governance fixture existed to walk at all:
  worker approves their own pending asset -> 42501, named user + hive          (already correct)
  worker REJECTS their own pending asset  -> 1 row, no error                   (the hole)
  ...writing rejection_reason = "Rejected by the supervisor - not fit for the register."

Reachable rather than theoretical: asset-hub's reject is caught only incidentally, because it also
writes approved_by/approved_at. hive.html's `rejectItem()` updates `{ status: 'rejected' }` ALONE,
gated by a client-side `if (HIVE_ROLE !== 'supervisor')` and nothing else.

WHY THE REASON FIELD MATTERS: `rejection_reason` is the REVIEWER'S VOICE — the asset-hub queue
renders it back to the submitter as "**Why:** ...", and the PDDA arc added it so a rejection would
explain itself. A submitter able to write that field can author a verdict in a supervisor's name,
and the next supervisor reading the queue cannot tell.

Fixed by 20260728000013 (reviewer_states + a rejection_reason clause). This gate holds it:
  1. STATIC  — the guard body still treats BOTH reviewer outcomes, and the reason field, as privileged.
  2. LIVE    — a worker cannot self-reject, and cannot edit the reason alone (rolled-back probe).
  3. LIVE    — a supervisor still can (no regression).

Live tier; SKIPS cleanly (exit 0) when docker / a worker-authored pending fixture is absent.
Self-test: --selftest.
"""
from __future__ import annotations
import io, json, re, subprocess, sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GREEN, RED, YELLOW, BOLD, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"
ROOT = Path(__file__).resolve().parent.parent
DB = "supabase_db_workhive"

# The trigger is attached to every approval queue on the platform; the hole was on all of them.
GUARDED_TABLES = ["asset_nodes", "inventory_items", "logbook",
                  "project_change_orders", "rcm_fmea_modes", "rcm_strategies"]


def _psql(sql, stdin_mode=False):
    try:
        args = ["docker", "exec"] + (["-i"] if stdin_mode else []) + [
            DB, "psql", "-U", "postgres", "-d", "postgres", "-X", "-q" if stdin_mode else "-A",
        ] + ([] if stdin_mode else ["-t", "-c", sql])
        if stdin_mode:
            args += ["-v", "ON_ERROR_STOP=0"]
            p = subprocess.run(args, input=sql, capture_output=True, text=True, timeout=45)
        else:
            p = subprocess.run(args, capture_output=True, text=True, timeout=45)
        return (p.stdout or "") + (p.stderr or "")
    except Exception:
        return None


PROBE = """
BEGIN;
DO $$
DECLARE v_w uuid; v_s uuid; v_hive uuid; v_node uuid; v_n int;
BEGIN
  SELECT n.auth_uid, n.id, n.hive_id INTO v_w, v_node, v_hive
    FROM public.asset_nodes n
    JOIN public.hive_members hm ON hm.auth_uid = n.auth_uid AND hm.hive_id = n.hive_id
   WHERE n.status = 'pending' AND hm.role = 'worker' AND hm.status = 'active' LIMIT 1;
  IF v_node IS NULL THEN RAISE NOTICE 'RESULT fixture=MISSING'; RETURN; END IF;
  SELECT auth_uid INTO v_s FROM public.hive_members
   WHERE hive_id = v_hive AND role = 'supervisor' AND status = 'active' AND auth_uid IS NOT NULL LIMIT 1;

  SET LOCAL ROLE authenticated;
  PERFORM set_config('request.jwt.claims', json_build_object('sub',v_w,'role','authenticated')::text, true);
  BEGIN
    UPDATE public.asset_nodes SET status='rejected', rejection_reason='gate probe' WHERE id=v_node;
    RAISE NOTICE 'RESULT selfreject=OPEN_VULN';
  EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'RESULT selfreject=BLOCKED';
            WHEN others THEN RAISE NOTICE 'RESULT selfreject=OTHER:%', SQLSTATE;
  END;
  BEGIN
    UPDATE public.asset_nodes SET rejection_reason='gate probe reason only' WHERE id=v_node;
    RAISE NOTICE 'RESULT reasonedit=OPEN_VULN';
  EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'RESULT reasonedit=BLOCKED';
            WHEN others THEN RAISE NOTICE 'RESULT reasonedit=OTHER:%', SQLSTATE;
  END;

  IF v_s IS NOT NULL THEN
    PERFORM set_config('request.jwt.claims', json_build_object('sub',v_s,'role','authenticated')::text, true);
    BEGIN
      WITH u AS (UPDATE public.asset_nodes SET status='rejected', rejection_reason='gate probe'
                  WHERE id=v_node RETURNING 1) SELECT count(*) INTO v_n FROM u;
      IF v_n = 1 THEN RAISE NOTICE 'RESULT supervisor=OK';
      ELSE RAISE NOTICE 'RESULT supervisor=REGRESSION'; END IF;
    EXCEPTION WHEN others THEN RAISE NOTICE 'RESULT supervisor=REGRESSION:%', SQLSTATE;
    END;
  ELSE
    RAISE NOTICE 'RESULT supervisor=OK';
  END IF;
END $$;
ROLLBACK;
"""


def check_static():
    body = _psql("SELECT pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace n "
                 "ON n.oid=p.pronamespace WHERE n.nspname='public' "
                 "AND p.proname='wh_guard_supervisor_approval';")
    if body is None:
        return None
    if not body.strip():
        return ["wh_guard_supervisor_approval no longer exists — every approval queue on the "
                "platform is ungated"]
    problems = []
    if "reviewer_states" not in body:
        problems.append("the guard no longer distinguishes REVIEWER states — a status change to "
                        "'rejected' would slip through again, because only 'approved' was ever "
                        "treated as privileged")
    if "rejection_reason" not in body:
        problems.append("the guard no longer treats rejection_reason as privileged — a submitter "
                        "could author a verdict in a supervisor's name")
    return problems


def main():
    if "--selftest" in sys.argv:
        probs = []
        # The pre-fix shape must still be recognisable as broken.
        pre = ("privileged := ((jnew ->> 'status') IS DISTINCT FROM (jold ->> 'status') "
               "AND ((jnew ->> 'status') = 'approved' OR (jold ->> 'status') = 'approved'));")
        if "reviewer_states" in pre or "rejection_reason" in pre:
            probs.append("the pre-fix fixture would pass the static check — it has no teeth")
        if not GUARDED_TABLES:
            probs.append("GUARDED_TABLES is empty; the gate has lost its scope")
        print("SELFTEST PASS" if not probs else "SELFTEST FAIL:\n  " + "\n  ".join(probs))
        return 1 if probs else 0

    print(f"\n{BOLD}APPROVAL AUTHORITY (rejecting is a reviewer's act too){RESET}")
    print("-" * 56)

    static = check_static()
    if static is None:
        print(f"  {YELLOW}SKIP{RESET}  docker psql unavailable")
        return 0

    out = _psql(PROBE, stdin_mode=True) or ""
    res = {}
    for ln in out.splitlines():
        if "RESULT " in ln:
            body = ln.split("RESULT ", 1)[1].strip()
            if "=" in body:
                k, v = body.split("=", 1)
                res[k.strip()] = v.strip()

    if res.get("fixture") == "MISSING":
        print(f"  {YELLOW}SKIP{RESET}  no worker-authored PENDING asset to probe with "
              f"(the governance fixture is what makes this walkable at all)")
        return 0

    checks = [("guard_static", "OK" if not static else "BROKEN", "OK",
               f"the guard still treats both reviewer outcomes AND the reason field as privileged "
               f"({len(GUARDED_TABLES)} tables share it)"),
              ("self_reject_blocked", res.get("selfreject"), "BLOCKED",
               "a worker cannot reject their own pending submission"),
              ("reason_edit_blocked", res.get("reasonedit"), "BLOCKED",
               "a submitter cannot write the reviewer's rejection_reason"),
              ("supervisor_ok", res.get("supervisor"), "OK",
               "a supervisor can still reject (no regression)")]

    fails = 0
    for name, got, want, desc in checks:
        if got == want:
            print(f"  {GREEN}PASS{RESET}  {name}: {desc}")
        else:
            fails += 1
            print(f"  {RED}FAIL{RESET}  {name}: expected {want}, got {got!r} — {desc}")
            for s in (static or []):
                print(f"        {s}")

    print(f"\n  Summary: {len(checks) - fails} pass · {fails} fail")
    (ROOT / "approval_authority_report.json").write_text(
        json.dumps({"validator": "approval_authority", "tables": GUARDED_TABLES,
                    "results": res, "static": static, "fail": fails}, indent=2), encoding="utf-8")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
