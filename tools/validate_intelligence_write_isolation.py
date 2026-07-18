"""validate_intelligence_write_isolation.py — LIVE write-integrity gate for the
intelligence/aggregation layer (Asset Hub · Alert Hub · Shift Brain).

Locks the I-axis holes found + live-probed in the Asset/Alert/Shift PDDA arc (2026-07-12,
ASSET_ALERT_SHIFT_DEEP_ARC.md), fixed by 20260712000013_intelligence_write_guard.sql:

  F11 (live-exploited): `asset_risk_scores` was a FOR ALL policy open to ANY active member
  of the row's hive — a real authenticated WORKER could INSERT a fabricated risk row and
  UPDATE an existing row's risk_score/risk_level. That table is the nightly-batch-owned cache
  feeding asset-hub risk chips, alert-hub risk alerts, shift-brain top-risk, and analytics, so
  a member could fabricate a phantom "critical" or bury a real "critical" as "low". Now locked
  to service-role writes (INSERT WITH CHECK false, UPDATE/DELETE USING false), matching the
  sibling caches sensor_readings / anomaly_signals.

  F10 (defense-in-depth): `asset_nodes_write` USING owner-branch was `auth_uid = auth.uid()`
  with no hive gate, so a DEPARTED member could still act (esp. DELETE, authorized by USING
  alone) on their own non-approved authored rows. USING owner-branch now also requires active
  membership of the row's hive.

Runs a ROLLED-BACK probe against the running DB (docker psql) AS a real authenticated member
and asserts:
  1. ARS_INSERT_BLOCKED — a member's INSERT of a fabricated asset_risk_scores row is rejected.
  2. ARS_UPDATE_BLOCKED — a member's UPDATE of an existing risk row affects 0 rows (USING false).
  3. ARS_READ_OK        — the member can still SELECT their hive's risk rows (no read regression).
  4. AN_XHIVE_INSERT_BLOCKED — a member's asset_nodes INSERT into a FOREIGN hive is rejected.

Actors (member uid+hive, a foreign hive) are chosen dynamically from the DB, so the gate
survives a reseed. Skips cleanly (exit 0) when docker/db is absent or no ≥2-hive fixture
exists, matching the other *_live gates.

Exit 0 = all invariants hold (or skipped).  Exit 1 = an invariant failed (a reverted migration).
"""

import sys, json, subprocess
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"; RESET = "\033[0m"; BOLD = "\033[1m"
ROOT = Path(__file__).resolve().parent.parent
DB = "supabase_db_workhive"
REPORT = ROOT / "intelligence_write_isolation_report.json"


def _psql(sql: str, stdin_mode: bool = False):
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
    REPORT.write_text(json.dumps({"validator": "intelligence_write_isolation", "skipped": True,
                                  "reason": reason}, indent=2), encoding="utf-8")
    return 0


def main() -> int:
    print(f"\n{BOLD}INTELLIGENCE WRITE ISOLATION (live two-tenant){RESET}")
    print("─" * 46)

    # Pick an active member (their auth_uid + hive) and a DIFFERENT hive that has an asset_node.
    pick = _psql(
        "SELECT hm.auth_uid, hm.hive_id, fh.hive_id "
        "FROM hive_members hm "
        "JOIN (SELECT DISTINCT hive_id FROM asset_nodes) fh ON fh.hive_id <> hm.hive_id "
        "WHERE hm.status='active' AND hm.auth_uid IS NOT NULL "
        "LIMIT 1;")
    if pick is None:
        return _skip("docker psql unavailable")
    _, out = pick
    row = [ln for ln in out.splitlines() if "|" in ln]
    if not row:
        return _skip("no two-hive fixture (need ≥2 hives, one with asset_nodes, + an active member)")
    uid, own_hive, foreign_hive = [c.strip() for c in row[0].split("|")]

    probe = f"""
BEGIN;
SET LOCAL ROLE authenticated;
SET LOCAL request.jwt.claims TO '{{"sub":"{uid}","role":"authenticated"}}';
DO $$
DECLARE n int;
BEGIN
  BEGIN
    INSERT INTO asset_risk_scores(hive_id, asset_name, risk_score, risk_level)
    VALUES('{own_hive}','GATE-FAKE-RISK',0.99,'critical');
    RAISE NOTICE 'RESULT ars_insert=OPEN_VULN';
  EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'RESULT ars_insert=BLOCKED';
            WHEN others THEN RAISE NOTICE 'RESULT ars_insert=OTHER:%', SQLSTATE; END;

  BEGIN
    UPDATE asset_risk_scores SET risk_score=0.01, risk_level='low' WHERE hive_id='{own_hive}';
    GET DIAGNOSTICS n = ROW_COUNT;
    IF n>0 THEN RAISE NOTICE 'RESULT ars_update=OPEN_VULN'; ELSE RAISE NOTICE 'RESULT ars_update=BLOCKED'; END IF;
  EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'RESULT ars_update=BLOCKED';
            WHEN others THEN RAISE NOTICE 'RESULT ars_update=OTHER:%', SQLSTATE; END;

  BEGIN
    SELECT count(*) INTO n FROM asset_risk_scores WHERE hive_id='{own_hive}';
    RAISE NOTICE 'RESULT ars_read=OK';
  EXCEPTION WHEN others THEN RAISE NOTICE 'RESULT ars_read=FAIL:%', SQLSTATE; END;

  BEGIN
    INSERT INTO asset_nodes(hive_id, tag, name, level, criticality, auth_uid, status)
    VALUES('{foreign_hive}','GATE-XNODE','gate','equipment','high','{uid}','pending');
    RAISE NOTICE 'RESULT an_xhive_insert=OPEN_VULN';
  EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'RESULT an_xhive_insert=BLOCKED';
            WHEN others THEN RAISE NOTICE 'RESULT an_xhive_insert=OTHER:%', SQLSTATE; END;
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
        ("ars_insert_blocked", results.get("ars_insert"), "BLOCKED",
         "a member CANNOT fabricate an asset_risk_scores row (risk-cache poisoning)"),
        ("ars_update_blocked", results.get("ars_update"), "BLOCKED",
         "a member CANNOT overwrite an existing risk_score/risk_level"),
        ("ars_read_ok", results.get("ars_read"), "OK",
         "a member can still SELECT their hive's risk rows (no read regression)"),
        ("an_xhive_insert_blocked", results.get("an_xhive_insert"), "BLOCKED",
         "a member CANNOT insert an asset_node into a foreign hive"),
    ]
    fails = 0
    for name, got, want, desc in checks:
        if got == want:
            print(f"  {GREEN}PASS{RESET}  {name}: {desc}")
        else:
            fails += 1
            print(f"  {RED}FAIL{RESET}  {name}: expected {want}, got {got!r} — {desc}")

    print(f"\n  Summary: {4 - fails} pass · {fails} fail  (actor uid={uid[:8]}… own_hive={own_hive[:8]}…)")
    REPORT.write_text(json.dumps({"validator": "intelligence_write_isolation", "skipped": False,
                                  "results": results, "fail": fails}, indent=2), encoding="utf-8")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
