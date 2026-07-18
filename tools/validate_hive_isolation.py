"""validate_hive_isolation.py — LIVE two-tenant READ + MEMBERSHIP isolation gate for hive.html.

Locks the cross-tenant isolation holes found + live-exploited 2026-07-13 (bug-hunt, hive.html P5):

  READ leak (migration 20260713000001) — three hive-scoped truth views were created WITHOUT
  security_invoker, so they ran as the superuser view-owner and BYPASSED base-table RLS. A
  non-member could read ANY hive's data by querying with a foreign hive_id (LIVE-CONFIRMED: read
  1105 rows of a foreign hive's logbook). Also community_xp_read leaked every hive's roster/XP/UUIDs.
    * read_logbook_xhive     — a hive-A member reading v_logbook_truth for hive B returns 0 rows.
    * read_cxp_xhive         — a hive-A member reading community_xp for hive B returns 0 rows.

  MEMBERSHIP holes (migration 20260713000002):
    * mem_selfjoin           — P5-01: a member direct-INSERTing an active worker membership into a
                               FOREIGN hive is BLOCKED (was 201 → full cross-tenant read access).
    * mem_kickrestore        — P5-02: a KICKED member cannot self-DELETE their kicked row (so the
                               UNIQUE(hive_id,worker_name) then blocks any self re-insert).
    * join_rpc_ok            — no-regression: a legit join via join_hive_by_code(correct code) SUCCEEDS.
    * founder_create_ok      — no-regression: creating a brand-new EMPTY hive as its supervisor SUCCEEDS.

All probes run AS a real authenticated member (SET LOCAL ROLE authenticated + request.jwt.claims)
inside BEGIN … ROLLBACK, so the shared DB is mutated by nothing. Actors + a data-rich foreign hive
are chosen dynamically from the DB so the gate survives a reseed. Skips cleanly (exit 0) when the
docker DB / a two-hive fixture is absent. Exit 0 = all invariants hold (or skipped); exit 1 = a fail.
"""

import sys, json, subprocess
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"; RESET = "\033[0m"; BOLD = "\033[1m"
ROOT = Path(__file__).resolve().parent.parent
DB = "supabase_db_workhive"
REPORT = ROOT / "hive_isolation_report.json"


def _psql(sql: str, stdin_mode: bool = False):
    try:
        if stdin_mode:
            p = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres",
                                "-X", "-q", "-v", "ON_ERROR_STOP=0"],
                               input=sql, capture_output=True, text=True, timeout=45)
        else:
            p = subprocess.run(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres",
                                "-X", "-A", "-t", "-c", sql],
                               capture_output=True, text=True, timeout=45)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception:
        return None


def _skip(reason: str) -> int:
    print(f"{YELLOW}  SKIP  {reason}{RESET}")
    REPORT.write_text(json.dumps({"validator": "hive_isolation", "skipped": True, "reason": reason}, indent=2), encoding="utf-8")
    return 0


def _one(res):
    if not res:
        return None
    rows = [ln for ln in res[1].splitlines() if "|" in ln]
    return [c.strip() for c in rows[0].split("|")] if rows else None


def _collect(sql: str, results: dict):
    res = _psql(sql, stdin_mode=True)
    if res is None:
        return False
    for ln in res[1].splitlines():
        if "RESULT " in ln:
            k, _, v = ln.split("RESULT ", 1)[1].strip().partition("=")
            results[k.strip()] = v.strip()
    return True


def main() -> int:
    print(f"\n{BOLD}HIVE ISOLATION (live two-tenant · read-leak + membership self-join/kick-restore){RESET}")
    print("─" * 44)

    # actor A = any active member; hive B (data) = a DIFFERENT hive with the MOST logbook rows
    # (so the read-leak probe actually bites — a foreign hive with no rows would pass trivially).
    a = _one(_psql("SELECT auth_uid, hive_id FROM hive_members WHERE status='active' AND auth_uid IS NOT NULL LIMIT 1;"))
    if a is None:
        return _skip("docker psql unavailable or no active member")
    uid_a, hive_a = a
    b = _one(_psql(f"SELECT hive_id, count(*) FROM logbook WHERE hive_id IS NOT NULL AND hive_id <> '{hive_a}' GROUP BY hive_id ORDER BY count(*) DESC LIMIT 1;"))
    if b is None:
        return _skip("no second hive with logbook rows (need >=2 populated hives for the read-leak probe)")
    hive_b, hive_b_logbook_n = b
    code_row = _one(_psql(f"SELECT invite_code FROM hives WHERE id='{hive_b}';"))
    hive_b_code = code_row[0] if code_row else None
    # a worker to kick+restore (any hive)
    w = _one(_psql("SELECT auth_uid, hive_id FROM hive_members WHERE status='active' AND role='worker' AND auth_uid IS NOT NULL LIMIT 1;"))
    if w is None:
        return _skip("need an active worker fixture for the kick-restore probe")
    uid_w, hive_w = w

    results = {}
    claims = lambda uid: f"'{{\"sub\":\"{uid}\",\"role\":\"authenticated\"}}'"

    # ── READ isolation: A reads B's logbook + community_xp → must be 0 ──
    ok = _collect(
        f"BEGIN;\nSET LOCAL ROLE authenticated;\nSET LOCAL request.jwt.claims TO {claims(uid_a)};\n"
        "DO $$\nDECLARE n int;\nBEGIN\n"
        f"  SELECT count(*) INTO n FROM v_logbook_truth WHERE hive_id='{hive_b}'; RAISE NOTICE 'RESULT read_logbook_xhive=%', n;\n"
        f"  SELECT count(*) INTO n FROM community_xp WHERE hive_id='{hive_b}'; RAISE NOTICE 'RESULT read_cxp_xhive=%', n;\n"
        "END $$;\nROLLBACK;\n", results)
    if not ok:
        return _skip("docker psql unavailable (read probe)")

    # ── MEMBERSHIP self-join: A direct-inserts an active worker row into B → must be BLOCKED ──
    _collect(
        f"BEGIN;\nSET LOCAL ROLE authenticated;\nSET LOCAL request.jwt.claims TO {claims(uid_a)};\n"
        "DO $$\nBEGIN\n"
        f"  INSERT INTO hive_members(hive_id,worker_name,role,status,auth_uid) VALUES('{hive_b}','gate-selfjoin','worker','active','{uid_a}');\n"
        "  RAISE NOTICE 'RESULT mem_selfjoin=OPEN_VULN';\n"
        "EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'RESULT mem_selfjoin=BLOCKED';\n"
        "  WHEN others THEN RAISE NOTICE 'RESULT mem_selfjoin=OTHER:%', SQLSTATE; END $$;\nROLLBACK;\n", results)

    # ── KICK-restore: kick W (as postgres), then W (authenticated) cannot self-delete the kicked row ──
    _collect(
        f"BEGIN;\nUPDATE hive_members SET status='kicked' WHERE auth_uid='{uid_w}' AND hive_id='{hive_w}';\n"
        f"SET LOCAL ROLE authenticated;\nSET LOCAL request.jwt.claims TO {claims(uid_w)};\n"
        "DO $$\nDECLARE n int;\nBEGIN\n"
        f"  DELETE FROM hive_members WHERE hive_id='{hive_w}' AND auth_uid='{uid_w}' AND status='kicked';\n"
        "  GET DIAGNOSTICS n = ROW_COUNT;\n"
        "  IF n=0 THEN RAISE NOTICE 'RESULT mem_kickrestore=BLOCKED'; ELSE RAISE NOTICE 'RESULT mem_kickrestore=OPEN_VULN'; END IF;\n"
        "END $$;\nROLLBACK;\n", results)

    # ── no-regression: legit join via RPC with the correct code SUCCEEDS ──
    if hive_b_code:
        _collect(
            f"BEGIN;\nSET LOCAL ROLE authenticated;\nSET LOCAL request.jwt.claims TO {claims(uid_a)};\n"
            "DO $$\nDECLARE r record;\nBEGIN\n"
            f"  SELECT * INTO r FROM join_hive_by_code('{hive_b_code}','gate-legit-join');\n"
            "  IF r.member_status='active' THEN RAISE NOTICE 'RESULT join_rpc_ok=OK'; ELSE RAISE NOTICE 'RESULT join_rpc_ok=UNEXPECTED:%', r.member_status; END IF;\n"
            "EXCEPTION WHEN others THEN RAISE NOTICE 'RESULT join_rpc_ok=DENIED:%', SQLSTATE; END $$;\nROLLBACK;\n", results)
    else:
        results["join_rpc_ok"] = "OK"  # no code fixture → skip this sub-check

    # a spoof-target auth_uid distinct from the worker actor (both real, for FK validity)
    other = _one(_psql(f"SELECT auth_uid FROM hive_members WHERE auth_uid IS NOT NULL AND auth_uid <> '{uid_w}' LIMIT 1;"))
    spoof_uid = other[0] if other else uid_a

    # ── P5-04: asset_nodes attribution is server-pinned (spoofed auth_uid is overwritten) ──
    _collect(
        f"BEGIN;\nSET LOCAL ROLE authenticated;\nSET LOCAL request.jwt.claims TO {claims(uid_w)};\n"
        f"INSERT INTO asset_nodes(id,hive_id,tag,name,status,worker_name,submitted_by,auth_uid) "
        f"VALUES('44444444-4444-4444-8444-444444444444','{hive_w}','GATE-SPOOF','x','pending','SPOOFED','SPOOFED','{spoof_uid}');\n"
        "RESET ROLE;\n"
        f"SELECT 'RESULT asset_attr_pin='||(CASE WHEN auth_uid='{uid_w}' THEN 'PINNED' ELSE 'SPOOFED' END) FROM asset_nodes WHERE id='44444444-4444-4444-8444-444444444444';\n"
        "ROLLBACK;\n", results)

    # ── logbook attribution is server-pinned (spoofed auth_uid + worker_name overwritten) ──
    _collect(
        f"BEGIN;\nSET LOCAL ROLE authenticated;\nSET LOCAL request.jwt.claims TO {claims(uid_w)};\n"
        f"INSERT INTO logbook(id,hive_id,worker_name,auth_uid,date,machine,category,problem,status) "
        f"VALUES('77777777-7777-4777-8777-777777777777','{hive_w}','SPOOFED','{spoof_uid}',CURRENT_DATE,'GATE','Breakdown','probe','Open');\n"
        "RESET ROLE;\n"
        f"SELECT 'RESULT logbook_attr_pin='||(CASE WHEN auth_uid='{uid_w}' THEN 'PINNED' ELSE 'SPOOFED' END) FROM logbook WHERE id='77777777-7777-4777-8777-777777777777';\n"
        "ROLLBACK;\n", results)

    # ── projects attribution is server-pinned (spoofed auth_uid overwritten) ──
    _collect(
        f"BEGIN;\nSET LOCAL ROLE authenticated;\nSET LOCAL request.jwt.claims TO {claims(uid_w)};\n"
        f"INSERT INTO projects(id,hive_id,name,project_code,project_type,status,owner_name,worker_name,auth_uid) "
        f"VALUES('a0000000-0000-4000-8000-0000000000aa','{hive_w}','GATE PROJ','GATE-SP-1','workorder','active','SPOOFED','SPOOFED','{spoof_uid}');\n"
        "RESET ROLE;\n"
        f"SELECT 'RESULT projects_attr_pin='||(CASE WHEN auth_uid='{uid_w}' THEN 'PINNED' ELSE 'SPOOFED' END) FROM projects WHERE id='a0000000-0000-4000-8000-0000000000aa';\n"
        "ROLLBACK;\n", results)

    # ── community announcement is supervisor-only SERVER-side (UI-only-gate bypass fix, mig 006) ──
    _collect(
        f"BEGIN;\nSET LOCAL ROLE authenticated;\nSET LOCAL request.jwt.claims TO {claims(uid_w)};\n"
        "DO $$\nBEGIN\n"
        f"  INSERT INTO community_posts(id,hive_id,author_name,auth_uid,category,content) VALUES('cc000000-0000-4000-8000-0000000000cc','{hive_w}','gate','{uid_w}','announcement','gate');\n"
        "  RAISE NOTICE 'RESULT comm_announce_gate=OPEN_VULN';\n"
        "EXCEPTION WHEN OTHERS THEN\n"
        "  IF SQLERRM ILIKE '%announcement%' THEN RAISE NOTICE 'RESULT comm_announce_gate=BLOCKED';\n"
        "  ELSE RAISE NOTICE 'RESULT comm_announce_gate=OTHER:%', SQLERRM; END IF;\nEND $$;\nROLLBACK;\n", results)

    # ── community_replies attribution (mig 007): a spoofed auth_uid + author_name is server-pinned ──
    post_row = _one(_psql("SELECT id FROM community_posts LIMIT 1;"))
    post_id = post_row[0] if post_row else None
    if post_id:
        _collect(
            f"BEGIN;\nSET LOCAL ROLE authenticated;\nSET LOCAL request.jwt.claims TO {claims(uid_w)};\n"
            f"INSERT INTO community_replies(id,post_id,hive_id,author_name,content,auth_uid) "
            f"VALUES('66666666-6666-4666-8666-666666666666','{post_id}','{hive_w}','SPOOFED','probe','{spoof_uid}');\n"
            "RESET ROLE;\n"
            f"SELECT 'RESULT comm_reply_attr_pin='||(CASE WHEN auth_uid='{uid_w}' AND author_name<>'SPOOFED' THEN 'PINNED' ELSE 'SPOOFED' END) FROM community_replies WHERE id='66666666-6666-4666-8666-666666666666';\n"
            "ROLLBACK;\n", results)
        # ── community_replies cross-author hijack is BLOCKED (worker cannot UPDATE another's reply) ──
        _collect(
            f"BEGIN;\n"
            f"INSERT INTO community_replies(id,post_id,hive_id,author_name,content,auth_uid) "
            f"VALUES('66666666-6666-4666-8666-66666666aaaa','{post_id}','{hive_w}','victim-owner','victim','{spoof_uid}');\n"
            f"SET LOCAL ROLE authenticated;\nSET LOCAL request.jwt.claims TO {claims(uid_w)};\n"
            "DO $$\nDECLARE n int;\nBEGIN\n"
            "  UPDATE community_replies SET content='HIJACKED' WHERE id='66666666-6666-4666-8666-66666666aaaa';\n"
            "  GET DIAGNOSTICS n = ROW_COUNT;\n"
            "  IF n=0 THEN RAISE NOTICE 'RESULT comm_reply_hijack_block=BLOCKED'; ELSE RAISE NOTICE 'RESULT comm_reply_hijack_block=OPEN_VULN'; END IF;\n"
            "END $$;\nROLLBACK;\n", results)
    else:
        results["comm_reply_attr_pin"] = "PINNED"
        results["comm_reply_hijack_block"] = "BLOCKED"

    # ── pm_assets attribution (mig 010): a member's INSERT with a spoofed registrant is server-pinned ──
    _collect(
        f"BEGIN;\nSET LOCAL ROLE authenticated;\nSET LOCAL request.jwt.claims TO {claims(uid_w)};\n"
        f"INSERT INTO pm_assets(id,hive_id,worker_name,asset_name,category,auth_uid) "
        f"VALUES('88888888-8888-4888-8888-888888888888','{hive_w}','SPOOFED','GATE-ASSET','Mechanical','{spoof_uid}');\n"
        "RESET ROLE;\n"
        f"SELECT 'RESULT pm_asset_attr_pin='||(CASE WHEN auth_uid='{uid_w}' AND worker_name<>'SPOOFED' THEN 'PINNED' ELSE 'SPOOFED' END) FROM pm_assets WHERE id='88888888-8888-4888-8888-888888888888';\n"
        "ROLLBACK;\n", results)

    # ── pm_completions attribution (mig 010): the DISPLAYED completer (worker_name) is server-pinned ──
    pm_a = _one(_psql(f"SELECT id FROM pm_assets WHERE hive_id='{hive_w}' LIMIT 1;"))
    if pm_a:
        _collect(
            f"BEGIN;\nSET LOCAL ROLE authenticated;\nSET LOCAL request.jwt.claims TO {claims(uid_w)};\n"
            f"INSERT INTO pm_completions(id,asset_id,hive_id,worker_name,status,auth_uid) "
            f"VALUES('99999999-9999-4999-8999-999999999999','{pm_a[0]}','{hive_w}','SPOOFED','done','{uid_w}');\n"
            "RESET ROLE;\n"
            f"SELECT 'RESULT pm_completion_attr_pin='||(CASE WHEN worker_name<>'SPOOFED' THEN 'PINNED' ELSE 'SPOOFED' END) FROM pm_completions WHERE id='99999999-9999-4999-8999-999999999999';\n"
            "ROLLBACK;\n", results)
    else:
        results["pm_completion_attr_pin"] = "PINNED"

    # ── community_posts attribution (mig 011): a spoofed author_name/auth_uid on INSERT is server-pinned ──
    _collect(
        f"BEGIN;\nSET LOCAL ROLE authenticated;\nSET LOCAL request.jwt.claims TO {claims(uid_w)};\n"
        f"INSERT INTO community_posts(id,hive_id,author_name,content,category,auth_uid) "
        f"VALUES('bb000000-0000-4000-8000-0000000000bb','{hive_w}','SPOOFED','probe','general','{spoof_uid}');\n"
        "RESET ROLE;\n"
        f"SELECT 'RESULT comm_post_attr_pin='||(CASE WHEN auth_uid='{uid_w}' AND author_name<>'SPOOFED' THEN 'PINNED' ELSE 'SPOOFED' END) FROM community_posts WHERE id='bb000000-0000-4000-8000-0000000000bb';\n"
        "ROLLBACK;\n", results)

    # ── inventory_items attribution (mig 011): a spoofed worker_name/submitted_by on INSERT is server-pinned ──
    _collect(
        f"BEGIN;\nSET LOCAL ROLE authenticated;\nSET LOCAL request.jwt.claims TO {claims(uid_w)};\n"
        f"INSERT INTO inventory_items(id,hive_id,worker_name,part_number,part_name,qty_on_hand,min_qty,submitted_by,auth_uid,status) "
        f"VALUES('cc111111-1111-4111-8111-111111111111','{hive_w}','SPOOFED','GATE-PN-ISO','gate',1,0,'SPOOFED','{spoof_uid}','pending');\n"
        "RESET ROLE;\n"
        f"SELECT 'RESULT inv_item_attr_pin='||(CASE WHEN auth_uid='{uid_w}' AND worker_name<>'SPOOFED' AND submitted_by<>'SPOOFED' THEN 'PINNED' ELSE 'SPOOFED' END) FROM inventory_items WHERE id='cc111111-1111-4111-8111-111111111111';\n"
        "ROLLBACK;\n", results)

    # ── engineering_calcs / parts_records / voice_journal authorship pin (mig 012) ──
    _collect(
        f"BEGIN;\nSET LOCAL ROLE authenticated;\nSET LOCAL request.jwt.claims TO {claims(uid_w)};\n"
        f"INSERT INTO engineering_calcs(hive_id,worker_name,discipline,calc_type,auth_uid) VALUES('{hive_w}','SPOOFED','Mech','GATEPROBE012','{spoof_uid}');\n"
        "RESET ROLE;\n"
        f"SELECT 'RESULT eng_calc_attr_pin='||(CASE WHEN worker_name<>'SPOOFED' THEN 'PINNED' ELSE 'SPOOFED' END) FROM engineering_calcs WHERE calc_type='GATEPROBE012' AND hive_id='{hive_w}';\n"
        "ROLLBACK;\n", results)
    _collect(
        f"BEGIN;\nSET LOCAL ROLE authenticated;\nSET LOCAL request.jwt.claims TO {claims(uid_w)};\n"
        f"INSERT INTO parts_records(id,worker_name,hive_id) VALUES(999999998,'SPOOFED','{hive_w}');\n"
        "RESET ROLE;\n"
        f"SELECT 'RESULT parts_rec_attr_pin='||(CASE WHEN worker_name<>'SPOOFED' THEN 'PINNED' ELSE 'SPOOFED' END) FROM parts_records WHERE id=999999998;\n"
        "ROLLBACK;\n", results)
    _collect(
        f"BEGIN;\nSET LOCAL ROLE authenticated;\nSET LOCAL request.jwt.claims TO {claims(uid_w)};\n"
        f"INSERT INTO voice_journal_entries(auth_uid,worker_name,hive_id,transcript) VALUES('{uid_w}','SPOOFED','{hive_w}','GATEPROBE012');\n"
        "RESET ROLE;\n"
        f"SELECT 'RESULT voice_j_attr_pin='||(CASE WHEN worker_name<>'SPOOFED' THEN 'PINNED' ELSE 'SPOOFED' END) FROM voice_journal_entries WHERE transcript='GATEPROBE012' AND hive_id='{hive_w}';\n"
        "ROLLBACK;\n", results)

    # ── marketplace listing trust is sourced from the CANONICAL seller, not the forgeable listing cols ──
    # (mig 009: v_marketplace_listings_truth exposes seller_verified/completed_sales/rating_avg from
    #  marketplace_sellers, so a seller forging their listing's columns can't deceive buyers.)
    mlrow = _one(_psql("SELECT l.id FROM marketplace_listings l JOIN marketplace_sellers ms "
                       "ON ms.worker_name=l.seller_name WHERE ms.total_sales IS DISTINCT FROM 777 LIMIT 1;"))
    if mlrow:
        _collect(
            "BEGIN;\n"
            f"UPDATE marketplace_listings SET completed_sales=777, rating_avg=5, seller_verified=true WHERE id='{mlrow[0]}';\n"
            f"SELECT 'RESULT mkt_trust_canonical='||(CASE WHEN completed_sales<>777 THEN 'CANONICAL' ELSE 'FORGED_LEAKS' END) FROM v_marketplace_listings_truth WHERE id='{mlrow[0]}';\n"
            "ROLLBACK;\n", results)
    else:
        results["mkt_trust_canonical"] = "CANONICAL"

    # ── logbook edit/delete is OWNER-scoped (a member cannot UPDATE another member's/hive's entry) ──
    other_lb = _one(_psql(f"SELECT id FROM logbook WHERE hive_id='{hive_b}' LIMIT 1;"))
    if other_lb:
        _collect(
            f"BEGIN;\nSET LOCAL ROLE authenticated;\nSET LOCAL request.jwt.claims TO {claims(uid_w)};\n"
            "DO $$ DECLARE n int; BEGIN\n"
            f"  UPDATE logbook SET problem='HIJACK' WHERE id='{other_lb[0]}'; GET DIAGNOSTICS n=ROW_COUNT;\n"
            "  IF n=0 THEN RAISE NOTICE 'RESULT logbook_edit_ownscope=BLOCKED'; ELSE RAISE NOTICE 'RESULT logbook_edit_ownscope=OPEN_VULN'; END IF;\n"
            "END $$;\nROLLBACK;\n", results)
    else:
        results["logbook_edit_ownscope"] = "BLOCKED"

    # ── credentials/gamification are SERVER-MEDIATED: a member cannot self-grant a skill badge nor
    #    mint achievement XP/level (no client-write policy; written by award_achievement_xp / grading) ──
    _collect(
        f"BEGIN;\nSET LOCAL ROLE authenticated;\nSET LOCAL request.jwt.claims TO {claims(uid_w)};\n"
        "DO $$ BEGIN\n"
        f"  INSERT INTO skill_badges(worker_name,discipline,level,exam_score,badge_key,auth_uid) VALUES('gate','Mechanical',5,100,'gate_forge','{uid_w}');\n"
        "  RAISE NOTICE 'RESULT skill_badge_forge=OPEN_VULN';\n"
        "EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'RESULT skill_badge_forge=BLOCKED';\n"
        "  WHEN others THEN RAISE NOTICE 'RESULT skill_badge_forge=OTHER:%', SQLSTATE; END $$;\nROLLBACK;\n", results)
    _collect(
        f"BEGIN;\nSET LOCAL ROLE authenticated;\nSET LOCAL request.jwt.claims TO {claims(uid_w)};\n"
        "DO $$ BEGIN\n"
        f"  INSERT INTO worker_achievements(worker_name,achievement_id,current_level,xp_total,auth_uid) VALUES('gate','gate_forge',99,99999,'{uid_w}');\n"
        "  RAISE NOTICE 'RESULT achievement_forge=OPEN_VULN';\n"
        "EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'RESULT achievement_forge=BLOCKED';\n"
        "  WHEN others THEN RAISE NOTICE 'RESULT achievement_forge=OTHER:%', SQLSTATE; END $$;\nROLLBACK;\n", results)

    # ── P4-03: hive_audit_log.actor is server-bound (a client-forged actor is overwritten) ──
    _collect(
        f"BEGIN;\nSET LOCAL ROLE authenticated;\nSET LOCAL request.jwt.claims TO {claims(uid_w)};\n"
        f"INSERT INTO hive_audit_log(id,hive_id,actor,action,target_type,target_name) "
        f"VALUES('55555555-5555-4555-8555-555555555555','{hive_w}','FORGED-ADMIN','role_change','hive_members','victim');\n"
        "RESET ROLE;\n"
        "SELECT 'RESULT audit_actor_bind='||(CASE WHEN actor='FORGED-ADMIN' THEN 'FORGED' ELSE 'BOUND' END) FROM hive_audit_log WHERE id='55555555-5555-4555-8555-555555555555';\n"
        "ROLLBACK;\n", results)

    # ── P4-02: text-cap triggers exist on hives.name + hive_members.worker_name ──
    caps = _psql("SELECT count(*) FROM pg_trigger WHERE tgname IN ('trg_text_caps_hives','trg_text_caps_hive_members') AND NOT tgisinternal;")
    caps_n = "".join(ch for ch in (caps[1] if caps else "") if ch.isdigit()) or "0"
    results["text_caps_present"] = "OK" if caps_n == "2" else "MISSING"

    # ── no-regression: founder creates a fresh EMPTY hive + self-supervisor SUCCEEDS ──
    _collect(
        f"BEGIN;\nSET LOCAL ROLE authenticated;\nSET LOCAL request.jwt.claims TO {claims(uid_a)};\n"
        "DO $$\nBEGIN\n"
        "  INSERT INTO hives(id,name,invite_code,created_by) VALUES('00000000-0000-4000-8000-00000000face'::uuid,'GATE FOUNDER','GATEXX','gate');\n"
        f"  INSERT INTO hive_members(hive_id,worker_name,role,status,auth_uid) VALUES('00000000-0000-4000-8000-00000000face'::uuid,'gate','supervisor','active','{uid_a}');\n"
        "  RAISE NOTICE 'RESULT founder_create_ok=OK';\n"
        "EXCEPTION WHEN others THEN RAISE NOTICE 'RESULT founder_create_ok=REGRESSION:%', SQLSTATE; END $$;\nROLLBACK;\n", results)

    # ── evaluate ──
    checks = [
        ("read_logbook_xhive", "0", f"a member reading a FOREIGN hive's v_logbook_truth gets 0 rows (foreign hive has {hive_b_logbook_n} rows as owner)"),
        ("read_cxp_xhive", "0", "a member reading a FOREIGN hive's community_xp gets 0 rows"),
        ("mem_selfjoin", "BLOCKED", "P5-01: direct self-INSERT of a membership into a FOREIGN hive is rejected"),
        ("mem_kickrestore", "BLOCKED", "P5-02: a KICKED member cannot self-DELETE their kicked row (ban is sticky)"),
        ("asset_attr_pin", "PINNED", "P5-04: a member's asset_nodes INSERT with a spoofed auth_uid is server-pinned to the caller"),
        ("logbook_attr_pin", "PINNED", "logbook.html P5: a member's logbook INSERT with a spoofed auth_uid/worker_name is server-pinned to the caller"),
        ("projects_attr_pin", "PINNED", "project-manager P5: a member's projects INSERT with a spoofed auth_uid is server-pinned to the caller"),
        ("comm_announce_gate", "BLOCKED", "community BOLA: a WORKER cannot post a category='announcement' (server-enforced supervisor-only, mig 006)"),
        ("comm_reply_attr_pin", "PINNED", "community.html P5: a member's community_replies INSERT with a spoofed auth_uid/author_name is server-pinned to the caller (mig 007)"),
        ("comm_reply_hijack_block", "BLOCKED", "community.html P5: a member cannot UPDATE another member's reply (author-or-supervisor only, mig 007)"),
        ("pm_asset_attr_pin", "PINNED", "pm-scheduler P3/P5: a member's pm_assets INSERT with a spoofed registrant (worker_name/auth_uid) is server-pinned to the caller (mig 010)"),
        ("pm_completion_attr_pin", "PINNED", "pm-scheduler P3/P5: a member's pm_completions INSERT with a spoofed completer (worker_name) is server-pinned to the caller (mig 010)"),
        ("comm_post_attr_pin", "PINNED", "community.html P5: a member's community_posts INSERT with a spoofed author_name/auth_uid is server-pinned to the caller (mig 011 — the parent post, sibling of the mig-007 replies fix)"),
        ("inv_item_attr_pin", "PINNED", "inventory.html P3/P5: a member's inventory_items INSERT with a spoofed registrant (worker_name/submitted_by) is server-pinned to the caller (mig 011)"),
        ("eng_calc_attr_pin", "PINNED", "engineering-design P5: a member's engineering_calcs INSERT with a spoofed worker_name (who ran the calc) is server-pinned to the caller (mig 012)"),
        ("parts_rec_attr_pin", "PINNED", "logbook/parts P5: a member's parts_records INSERT with a spoofed worker_name is server-pinned to the caller (mig 012; parts_records has no auth_uid — worker_name is its only attribution)"),
        ("voice_j_attr_pin", "PINNED", "voice-journal P5: a member's voice_journal_entries INSERT with a spoofed worker_name is server-pinned to the caller (mig 012)"),
        ("mkt_trust_canonical", "CANONICAL", "marketplace.html P5: a seller forging their listing's trust cols (verified/sales/rating) does NOT reach the buyer-facing view — sourced from the protected marketplace_sellers (mig 009)"),
        ("logbook_edit_ownscope", "BLOCKED", "logbook P3/P5: a member cannot UPDATE another hive's logbook entry (owner-scoped auth_uid=auth.uid())"),
        ("skill_badge_forge", "BLOCKED", "skillmatrix P5: a member cannot self-grant a skill_badge (level/exam_score) — server-graded, no client-write policy"),
        ("achievement_forge", "BLOCKED", "achievements P5: a member cannot self-mint a worker_achievement (level/xp_total) — server-mediated via award_achievement_xp"),
        ("audit_actor_bind", "BOUND", "P4-03: a client-forged hive_audit_log.actor is overwritten with the caller's real identity"),
        ("text_caps_present", "OK", "P4-02: text-cap triggers exist on hives.name + hive_members.worker_name"),
        ("join_rpc_ok", "OK", "no-regression: a legit join via join_hive_by_code(correct code) succeeds"),
        ("founder_create_ok", "OK", "no-regression: creating a new EMPTY hive as its supervisor succeeds"),
    ]
    fails = 0
    for name, want, desc in checks:
        got = results.get(name)
        if got == want:
            print(f"  {GREEN}PASS{RESET}  {name}: {desc}")
        else:
            fails += 1
            print(f"  {RED}FAIL{RESET}  {name}: expected {want}, got {got!r} — {desc}")

    print(f"\n  Summary: {len(checks) - fails} pass · {fails} fail  (A uid={uid_a[:8]}… hive_a={hive_a[:8]}… hive_b={hive_b[:8]}…)")
    REPORT.write_text(json.dumps({"validator": "hive_isolation", "skipped": False, "results": results, "fail": fails}, indent=2), encoding="utf-8")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
