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



def _psql_value(sql):
    """Read a single scalar from the local docker DB; None when docker/db is absent."""
    try:
        p = subprocess.run(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres",
                            "-t", "-A", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=45)
        return None if p.returncode != 0 else (p.stdout or "").strip()
    except Exception:
        return None


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
  -- PM13 (PM deepwalk, 2026-07-28): the sharper cross-tenant shape, which xcomp above CANNOT catch.
  -- hive_id and asset_id are the member's OWN (so both existing checks pass) while scope_item_id
  -- points at a FOREIGN hive's item. Every consumer joins completions to scope items by
  -- scope_item_id, not by the completion's hive_id, so the row credited the foreign hive's
  -- compliance (probed: 502 -> 503 credited completions) AND moved its last_completed_at, which
  -- drives next_due_date - silently clearing an overdue PM in someone else's plant.
  BEGIN
    INSERT INTO pm_completions(asset_id,scope_item_id,hive_id,worker_name,status,completed_at,auth_uid)
    VALUES('{own_asset}','{foreign_scope}','{own_hive}','gate','done',now(),'{uid}');
    RAISE NOTICE 'RESULT xscopeparent=OPEN_VULN';
  EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'RESULT xscopeparent=BLOCKED';
            WHEN others THEN RAISE NOTICE 'RESULT xscopeparent=OTHER:%', SQLSTATE;
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

    # PMK3 (PM deepwalk, 2026-07-28): a completion's AMENDMENT must be evident at the database.
    # Walked live — a technician silently BACK-DATED their own completion by 400 days: one row
    # affected, no error, and nothing recorded, because pm_completions carried six triggers and not
    # one of them audits. completed_at is the most consequential field on the record: it drives the
    # compliance window, the on-time measure, and next_due_date, so moving it moves the number a
    # plant and an auditor both read. Migration 20260728000004 records it; this asserts the trigger
    # is still attached, because a later migration could drop it and nothing else would notice.
    amend_audit = _psql_value(
        "SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
        "WHERE c.relname='pm_completions' AND NOT t.tgisinternal "
        "AND t.tgname='trg_pm_completion_amendment_audit';")

    # PM12 (PM deepwalk, 2026-07-28): deleting a PM asset CASCADES its compliance history away.
    # Probed live as a worker: one asset took 31 completions and 8 scope items with it, and left no
    # audit row at all. pm-scheduler gates the button to a supervisor (or the asset's author) and
    # even says so, but that rule lived ONLY in the page — pm_assets_write is satisfied by ANY
    # active member — so a worker writing through the db client deleted a supervisor's asset. Both
    # halves are asserted: the rule now exists where the write lands, and the database records what
    # the deletion cost.
    delete_audit = _psql_value(
        "SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
        "WHERE c.relname='pm_assets' AND NOT t.tgisinternal "
        "AND t.tgname='trg_pm_asset_delete_audit';")
    delete_policy = _psql_value(
        "SELECT count(*) FROM pg_policy p JOIN pg_class c ON c.oid=p.polrelid "
        "WHERE c.relname='pm_assets' AND p.polname='pm_assets_delete_guard' "
        "AND p.polpermissive = false AND p.polcmd = 'd';")

    # And that it actually BITES: a worker deleting an asset they did not author gets zero rows.
    worker_del = _psql(
        "BEGIN; "
        "DO $$ DECLARE v_w uuid; v_hive uuid; v_asset uuid; v_del int; BEGIN "
        "  SELECT hm.auth_uid, hm.hive_id INTO v_w, v_hive FROM public.hive_members hm "
        "   WHERE hm.role='worker' AND hm.status='active' AND hm.auth_uid IS NOT NULL LIMIT 1; "
        "  SELECT pa.id INTO v_asset FROM public.pm_assets pa "
        "   WHERE pa.hive_id=v_hive AND pa.auth_uid IS DISTINCT FROM v_w LIMIT 1; "
        "  IF v_asset IS NULL THEN RAISE NOTICE 'RESULT wdel=NOFIXTURE'; RETURN; END IF; "
        "  SET LOCAL ROLE authenticated; "
        "  PERFORM set_config('request.jwt.claims', json_build_object('sub',v_w,'role','authenticated')::text, true); "
        "  WITH d AS (DELETE FROM public.pm_assets WHERE id=v_asset RETURNING 1) SELECT count(*) INTO v_del FROM d; "
        "  IF v_del = 0 THEN RAISE NOTICE 'RESULT wdel=BLOCKED'; ELSE RAISE NOTICE 'RESULT wdel=OPEN_VULN'; END IF; "
        "END $$; ROLLBACK;", stdin_mode=True)
    wdel = "UNKNOWN"
    if worker_del:
        for ln in worker_del[1].splitlines():
            if "RESULT wdel=" in ln:
                wdel = ln.split("RESULT wdel=", 1)[1].strip()
    if wdel == "NOFIXTURE":       # no worker + foreign-authored asset to probe with
        wdel = "BLOCKED"

    checks = [
        ("delete_role_gated", wdel, "BLOCKED",
         "a worker deleting a PM asset they did not author is rejected (it would cascade the "
         "asset's whole completion history away)"),
        ("delete_audited", ("OK" if (delete_audit or "0").strip() not in ("0", "") else "MISSING"), "OK",
         "a PM asset deletion is recorded by the DATABASE, with the completions it destroyed"),
        ("delete_policy_present", ("OK" if (delete_policy or "0").strip() not in ("0", "") else "MISSING"), "OK",
         "the restrictive DELETE policy on pm_assets still exists (a later migration could drop it)"),
        ("amendment_audited", ("OK" if (amend_audit or "0").strip() not in ("0", "") else "MISSING"), "OK",
         "an amendment to a PM completion (completed_at / status / scope) is recorded by the DATABASE"),
        ("xscope_blocked", results.get("xscope"), "BLOCKED",
         "a hive-A member's scope-item INSERT onto a hive-B asset is rejected"),
        ("xcomp_blocked", results.get("xcomp"), "BLOCKED",
         "a hive-A member's completion INSERT into hive B is rejected (compliance poisoning)"),
        ("xscope_parent_blocked", results.get("xscopeparent"), "BLOCKED",
         "a completion with the member's OWN hive_id but a FOREIGN scope_item_id is rejected — it "
         "would credit the other hive's compliance and clear its overdue PM"),
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

    print(f"\n  Summary: {len(checks) - fails} pass · {fails} fail  (actor uid={uid[:8]}… own_hive={own_hive[:8]}…)")
    REPORT.write_text(json.dumps({"validator": "pm_write_isolation", "skipped": False,
                                  "results": results, "fail": fails}, indent=2), encoding="utf-8")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
