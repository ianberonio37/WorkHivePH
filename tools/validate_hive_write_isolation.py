"""validate_hive_write_isolation.py — LIVE two-tenant write-isolation gate for the
sibling tables the 2026-07-12 hardening sweep MISSED (found + live-exploited 2026-07-13).

Same child/parent WITH-CHECK class as validate_pm_write_isolation.py, on tables that had
NO write-isolation gate and so regressed silently:

  1. inventory_items  — WITH CHECK owner branch (`auth_uid = self`) had no hive gate → a
     member INSERTed a phantom part into a FOREIGN hive (status<>'approved' dodges the
     supervisor-approval trigger). LIVE-CONFIRMED 201 pre-fix. Fixed 20260712000019.
  2. report_contacts  — WITH CHECK was `(auth.uid() IS NOT NULL)` only → any member injects
     a recipient into a FOREIGN hive's report-sender contact list (cross-tenant exfil).
     LIVE-CONFIRMED 201 pre-fix. Fixed 20260712000019.
  3. api_keys         — member-RW (no role gate) → a WORKER minted a programmatic hive-data
     credential. LIVE-CONFIRMED 201 pre-fix. Fixed 20260712000020 (supervisor-only).
     (project_roles / project_change_orders got the same-shape fix in 000020; not probed
     separately here — they are empty + need project FKs — but share this policy pattern.)

Rolled-back live probe (BEGIN … ROLLBACK; mutates nothing) AS a real authenticated member,
asserting FIVE invariants; catches a reverted migration a static file-parse would miss:
  1. INV_XHIVE   — a hive-A member inserting a part into hive B is BLOCKED.
  2. RC_XHIVE    — a hive-A member inserting a report_contact into hive B is BLOCKED.
  3. AK_WORKER   — a WORKER minting an api_key in their own hive is BLOCKED (supervisor-only).
  4. AK_SUPER    — a SUPERVISOR minting an api_key in their own hive SUCCEEDS (no regression).
  5. INV_LEGIT   — a member adding their own part to their own hive SUCCEEDS (no regression).

Actors are chosen dynamically from the DB so the gate survives a reseed. Skips cleanly
(exit 0) when the local docker DB / a two-hive+role fixture is absent.
Exit 0 = all invariants hold (or skipped). Exit 1 = an invariant failed.
"""

import sys, json, subprocess
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"; RESET = "\033[0m"; BOLD = "\033[1m"
ROOT = Path(__file__).resolve().parent.parent
DB = "supabase_db_workhive"
REPORT = ROOT / "hive_write_isolation_report.json"


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
    REPORT.write_text(json.dumps({"validator": "hive_write_isolation", "skipped": True,
                                  "reason": reason}, indent=2), encoding="utf-8")
    return 0


def main() -> int:
    print(f"\n{BOLD}HIVE WRITE ISOLATION (live two-tenant · inventory/report_contacts/api_keys){RESET}")
    print("─" * 44)

    # actor A = any active member with a DIFFERENT hive B in existence (cross-hive probes)
    pick = _psql(
        "SELECT hm.auth_uid, hm.hive_id, (SELECT h2.id FROM hives h2 WHERE h2.id <> hm.hive_id LIMIT 1) "
        "FROM hive_members hm WHERE hm.status='active' AND hm.auth_uid IS NOT NULL "
        "AND EXISTS (SELECT 1 FROM hives h2 WHERE h2.id <> hm.hive_id) LIMIT 1;")
    if pick is None:
        return _skip("docker psql unavailable")
    rowsA = [ln for ln in pick[1].splitlines() if "|" in ln]
    if not rowsA:
        return _skip("no two-hive fixture (need >=2 hives with an active member)")
    uid_a, hive_a, hive_b = [c.strip() for c in rowsA[0].split("|")]

    # a WORKER and a SUPERVISOR (any hive) for the api_keys role-gate probes
    w = _psql("SELECT auth_uid, hive_id FROM hive_members WHERE status='active' AND role='worker' AND auth_uid IS NOT NULL LIMIT 1;")
    s = _psql("SELECT auth_uid, hive_id FROM hive_members WHERE status='active' AND role='supervisor' AND auth_uid IS NOT NULL LIMIT 1;")
    wrow = [ln for ln in (w[1].splitlines() if w else []) if "|" in ln]
    srow = [ln for ln in (s[1].splitlines() if s else []) if "|" in ln]
    if not wrow or not srow:
        return _skip("need an active worker AND supervisor fixture for the api_keys role probes")
    uid_w, hive_w = [c.strip() for c in wrow[0].split("|")]
    uid_s, hive_s = [c.strip() for c in srow[0].split("|")]

    def probe(uid: str, body: str) -> str:
        return (f"BEGIN;\nSET LOCAL ROLE authenticated;\n"
                f"SET LOCAL request.jwt.claims TO '{{\"sub\":\"{uid}\",\"role\":\"authenticated\"}}';\n"
                f"DO $$\nBEGIN\n{body}\nEND $$;\nROLLBACK;\n")

    inv_id = "gate-inv-xhive"
    body_a = f"""
  BEGIN
    INSERT INTO inventory_items(id,worker_name,part_name,category,unit,qty_on_hand,min_qty,status,hive_id,auth_uid)
    VALUES('{inv_id}','gate','GATE-XHIVE','Test','pcs',1,1,'pending','{hive_b}','{uid_a}');
    RAISE NOTICE 'RESULT inv_xhive=OPEN_VULN';
  EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'RESULT inv_xhive=BLOCKED';
            WHEN others THEN RAISE NOTICE 'RESULT inv_xhive=OTHER:%', SQLSTATE; END;
  BEGIN
    INSERT INTO report_contacts(id,hive_id,name,email,label)
    VALUES(gen_random_uuid(),'{hive_b}','GATE','x@gate.example','GATE');
    RAISE NOTICE 'RESULT rc_xhive=OPEN_VULN';
  EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'RESULT rc_xhive=BLOCKED';
            WHEN others THEN RAISE NOTICE 'RESULT rc_xhive=OTHER:%', SQLSTATE; END;
  BEGIN
    INSERT INTO inventory_items(id,worker_name,part_name,category,unit,qty_on_hand,min_qty,status,hive_id,auth_uid)
    VALUES('gate-inv-legit','gate','GATE-LEGIT','Test','pcs',1,1,'pending','{hive_a}','{uid_a}');
    RAISE NOTICE 'RESULT inv_legit=OK';
  EXCEPTION WHEN others THEN RAISE NOTICE 'RESULT inv_legit=REGRESSION:%', SQLSTATE; END;
"""
    body_w = f"""
  BEGIN
    INSERT INTO api_keys(id,hive_id,key_prefix,key_hash,label,enabled)
    VALUES(gen_random_uuid(),'{hive_w}','gk','deadbeef','GATE-WORKER',true);
    RAISE NOTICE 'RESULT ak_worker=OPEN_VULN';
  EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'RESULT ak_worker=BLOCKED';
            WHEN others THEN RAISE NOTICE 'RESULT ak_worker=OTHER:%', SQLSTATE; END;
"""
    body_s = f"""
  BEGIN
    INSERT INTO api_keys(id,hive_id,key_prefix,key_hash,label,enabled)
    VALUES(gen_random_uuid(),'{hive_s}','gk','deadbeef','GATE-SUPER',true);
    RAISE NOTICE 'RESULT ak_super=OK';
  EXCEPTION WHEN others THEN RAISE NOTICE 'RESULT ak_super=DENIED:%', SQLSTATE; END;
"""
    # cmms_audit_log must be APPEND-ONLY: a member may INSERT + SELECT but a client
    # UPDATE/DELETE must be a no-op (no update/delete policy => 0 rows), so the row a member
    # just logged survives a tamper attempt unchanged (mig 20260712000021).
    body_cmms = f"""
  BEGIN
    INSERT INTO cmms_audit_log(id,hive_id,batch_id,operation,entity_type,rows_written,created_at)
      VALUES(gen_random_uuid(),'{hive_w}',gen_random_uuid(),'GATE_CMMS','asset',5,now());
    UPDATE cmms_audit_log SET rows_written=999 WHERE operation='GATE_CMMS';
    DELETE FROM cmms_audit_log WHERE operation='GATE_CMMS';
    IF EXISTS(SELECT 1 FROM cmms_audit_log WHERE operation='GATE_CMMS' AND rows_written=5)
      THEN RAISE NOTICE 'RESULT cmms_appendonly=BLOCKED';
      ELSE RAISE NOTICE 'RESULT cmms_appendonly=OPEN_VULN'; END IF;
  EXCEPTION WHEN others THEN RAISE NOTICE 'RESULT cmms_appendonly=OTHER:%', SQLSTATE; END;
"""
    results = {}
    for uid, body in ((uid_a, body_a), (uid_w, body_w), (uid_s, body_s), (uid_w, body_cmms)):
        res = _psql(probe(uid, body), stdin_mode=True)
        if res is None:
            return _skip("docker psql unavailable (probe)")
        for ln in res[1].splitlines():
            if "RESULT " in ln:
                k, _, v = ln.split("RESULT ", 1)[1].strip().partition("=")
                results[k.strip()] = v.strip()

    checks = [
        ("inv_xhive", "BLOCKED", "member inserting a part into a FOREIGN hive is rejected"),
        ("rc_xhive", "BLOCKED", "member inserting a report_contact into a FOREIGN hive is rejected"),
        ("ak_worker", "BLOCKED", "a WORKER minting a hive api_key is rejected (supervisor-only)"),
        ("ak_super", "OK", "a SUPERVISOR minting a hive api_key still succeeds (no regression)"),
        ("inv_legit", "OK", "a member's own in-hive part add still succeeds (no regression)"),
        ("cmms_appendonly", "BLOCKED", "a member's UPDATE/DELETE of a cmms_audit_log row is a no-op (append-only trail)"),
    ]
    fails = 0
    for name, want, desc in checks:
        got = results.get(name)
        if got == want:
            print(f"  {GREEN}PASS{RESET}  {name}: {desc}")
        else:
            fails += 1
            print(f"  {RED}FAIL{RESET}  {name}: expected {want}, got {got!r} — {desc}")

    print(f"\n  Summary: {len(checks) - fails} pass · {fails} fail  (A uid={uid_a[:8]}… worker={uid_w[:8]}… super={uid_s[:8]}…)")
    REPORT.write_text(json.dumps({"validator": "hive_write_isolation", "skipped": False,
                                  "results": results, "fail": fails}, indent=2), encoding="utf-8")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
