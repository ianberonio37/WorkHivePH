"""validate_pm_write_isolation.py — LIVE two-tenant PM-write isolation gate.

Locks the THREE cross-hive PM write holes found + live-exploited in the PM Scheduler PDDA
arc (2026-07-12), all of the same child/ledger-table WITH-CHECK class as the Inventory
ledger-tamper ([[reference_inventory_txn_crosshive_tamper]]):
  1. `pm_scope_items_write` WITH CHECK was `(auth.uid() IS NOT NULL)` only → inject a PM
     scope item onto a FOREIGN hive's asset.
  2. `pm_completions_write` WITH CHECK was NULL → fell back to USING (`auth_uid=self`), no
     hive gate → self-attributed completion into a FOREIGN hive's compliance (poisons
     v_pm_compliance_truth → analytics %, shift-planner PMs-due, hive PM-Health, predictive).
  3. `pm_assets_write` WITH CHECK was NULL → fell back to USING (`auth_uid=self OR member`,
     an OR) → phantom asset injected into a FOREIGN hive's PM list.
Fixed by 20260712000012_pm_hive_scope_write_guard.sql (WITH CHECK membership-joins the
parent / own hive on all three; USING tightened to hive-member-OR-solo-owner).

This gate runs a ROLLED-BACK live probe against the running DB (docker psql) AS a real
authenticated member, and asserts FOUR invariants — catching a reverted migration a static
file-parse would miss:
  1. XSCOPE — a hive-A member inserting a scope item onto a hive-B asset is BLOCKED (42501).
  2. XCOMP  — a hive-A member inserting a completion into hive B is BLOCKED (42501).
  3. XASSET — a hive-A member inserting an asset into hive B is BLOCKED (42501).
  4. LEGIT  — a legit in-hive completion on the member's own asset still SUCCEEDS (no regression).

Actors (member uid/hive, own asset+scope, foreign asset+scope) are chosen dynamically from
the DB, so the gate survives a reseed (which rotates auth_uids). Skips cleanly (exit 0) when
the local docker DB / a two-hive PM fixture is absent, matching the other *_live gates.

Exit 0 = all four invariants hold (or skipped, env absent).  Exit 1 = an invariant failed.
"""

import sys, json, subprocess
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"; RESET = "\033[0m"; BOLD = "\033[1m"
ROOT = Path(__file__).resolve().parent.parent
DB = "supabase_db_workhive"
REPORT = ROOT / "pm_write_isolation_report.json"


def _psql(sql: str, stdin_mode: bool = False):
    """Run SQL in the local docker Postgres. Returns (rc, stdout+stderr) or None if docker/db absent."""
    try:
        if stdin_mode:
            p = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres",
                                "-X", "-q", "-v", "ON_ERROR_STOP=0"],
                               input=sql, capture_output=True, text=True, timeout=40)
        else:
            p = subprocess.run(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres",
                                "-X", "-A", "-t", "-c", sql],
                               capture_output=True, text=True, timeout=40)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception:
        return None


def _skip(reason: str) -> int:
    print(f"{YELLOW}  SKIP  {reason}{RESET}")
    REPORT.write_text(json.dumps({"validator": "pm_write_isolation", "skipped": True,
                                  "reason": reason}, indent=2), encoding="utf-8")
    return 0


def main() -> int:
    print(f"\n{BOLD}PM WRITE ISOLATION (live two-tenant){RESET}")
    print("─" * 44)

    # ── Pick actors as the superuser (BYPASSRLS): an active member's auth_uid + hive, an
    #    asset+scope in THAT hive (legit target), and an asset+scope in a DIFFERENT hive. ──
    pick = _psql(
        "SELECT hm.auth_uid, own_a.id, own_s.id, hm.hive_id, fa.id, fs.id "
        "FROM hive_members hm "
        "JOIN pm_assets own_a      ON own_a.hive_id = hm.hive_id "
        "JOIN pm_scope_items own_s ON own_s.asset_id = own_a.id "
        "JOIN pm_assets fa         ON fa.hive_id <> hm.hive_id "
        "JOIN pm_scope_items fs    ON fs.asset_id = fa.id "
        "WHERE hm.status='active' AND hm.auth_uid IS NOT NULL "
        "LIMIT 1;")
    if pick is None:
        return _skip("docker psql unavailable")
    rc, out = pick
    row = [ln for ln in out.splitlines() if "|" in ln]
    if not row:
        return _skip("no two-hive PM fixture (need ≥2 hives with pm_assets+scope_items + an active member)")
    uid, own_asset, own_scope, own_hive, foreign_asset, foreign_scope = [c.strip() for c in row[0].split("|")]

    # Foreign hive_id (for the asset/completion inject targets) — resolve from the foreign asset.
    fh = _psql(f"SELECT hive_id FROM pm_assets WHERE id='{foreign_asset}';")
    foreign_hive = (fh[1].strip().splitlines() or [""])[0].strip() if fh else ""

    # ── The rolled-back probe, run AS the authenticated member ────────────────────────────
    probe = f"""
BEGIN;
SET LOCAL ROLE authenticated;
SET LOCAL request.jwt.claims TO '{{"sub":"{uid}","role":"authenticated"}}';
DO $$
BEGIN
  BEGIN
    INSERT INTO pm_scope_items(asset_id,hive_id,item_text,frequency)
    VALUES('{foreign_asset}','{foreign_hive}','GATE-XSCOPE','Monthly');
    RAISE NOTICE 'RESULT xscope=OPEN_VULN';
  EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'RESULT xscope=BLOCKED';
            WHEN others THEN RAISE NOTICE 'RESULT xscope=OTHER:%', SQLSTATE;
  END;
  BEGIN
    INSERT INTO pm_completions(asset_id,scope_item_id,hive_id,worker_name,status,completed_at,auth_uid)
    VALUES('{foreign_asset}','{foreign_scope}','{foreign_hive}','gate','done',now(),'{uid}');
    RAISE NOTICE 'RESULT xcomp=OPEN_VULN';
  EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'RESULT xcomp=BLOCKED';
            WHEN others THEN RAISE NOTICE 'RESULT xcomp=OTHER:%', SQLSTATE;
  END;
  BEGIN
    INSERT INTO pm_assets(hive_id,asset_name,category,criticality,auth_uid,worker_name)
    VALUES('{foreign_hive}','GATE-XASSET','Electrical','High','{uid}','gate');
    RAISE NOTICE 'RESULT xasset=OPEN_VULN';
  EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'RESULT xasset=BLOCKED';
            WHEN others THEN RAISE NOTICE 'RESULT xasset=OTHER:%', SQLSTATE;
  END;
  BEGIN
    INSERT INTO pm_completions(asset_id,scope_item_id,hive_id,worker_name,status,completed_at,auth_uid)
    VALUES('{own_asset}','{own_scope}','{own_hive}','gate','done',now(),'{uid}');
    RAISE NOTICE 'RESULT legit=OK';
  EXCEPTION WHEN others THEN RAISE NOTICE 'RESULT legit=REGRESSION:%', SQLSTATE;
  END;
END $$;
ROLLBACK;
"""
    res = _psql(probe, stdin_mode=True)
    if res is None:
        return _skip("docker psql unavailable (probe)")
    _, pout = res
    results = {}
    for ln in pout.splitlines():
        if "RESULT " in ln:
            body = ln.split("RESULT ", 1)[1].strip()
            if "=" in body:
                k, v = body.split("=", 1)
                results[k.strip()] = v.strip()

    checks = [
        ("xscope_blocked", results.get("xscope"), "BLOCKED",
         "a hive-A member's scope-item INSERT onto a hive-B asset is rejected"),
        ("xcomp_blocked", results.get("xcomp"), "BLOCKED",
         "a hive-A member's completion INSERT into hive B is rejected (compliance poisoning)"),
        ("xasset_blocked", results.get("xasset"), "BLOCKED",
         "a hive-A member's asset INSERT into hive B is rejected (phantom asset)"),
        ("legit_ok", results.get("legit"), "OK",
         "a legit in-hive completion still succeeds (no regression)"),
    ]
    fails = 0
    for name, got, want, desc in checks:
        if got == want:
            print(f"  {GREEN}PASS{RESET}  {name}: {desc}")
        else:
            fails += 1
            print(f"  {RED}FAIL{RESET}  {name}: expected {want}, got {got!r} — {desc}")

    print(f"\n  Summary: {4 - fails} pass · {fails} fail  (actor uid={uid[:8]}… own_hive={own_hive[:8]}…)")
    REPORT.write_text(json.dumps({"validator": "pm_write_isolation", "skipped": False,
                                  "results": results, "fail": fails}, indent=2), encoding="utf-8")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
