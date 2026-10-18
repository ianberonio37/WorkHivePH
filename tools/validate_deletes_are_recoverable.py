#!/usr/bin/env python3
"""validate_deletes_are_recoverable.py - SL D3 (Ian, 2026-10-16: "30-day recoverable"): what a page deletes stays
recoverable for 30 days, and a deleted row is gone from every read in the meantime.

WHY. Seven page paths deleted rows outright - a logbook entry ("This cannot be undone"), an asset with its FMEA modes,
Weibull fits and sensor readings, a part with its stock ledger, a day-plan item, a PM asset with its completions, a
project link and a project role. 20261016000001 made each a soft delete (deleted_at, wh_trash / wh_restore / the
Recently deleted list, a 30-day purge) and hid deleted rows from every read that runs as the person with one
restrictive policy per table. 20261016000002 and the edge functions covered the readers that bypass that policy.
Every half of that can regress silently: a new `.from('logbook').delete()` loses work for good again; a new
security-definer function or service-role read shows deleted rows to a supervisor's dashboard or to the AI.

STATIC (always):
  S1  no shipped page or script calls .delete() on a D3 table - deletes go through whTrash (wh_trash)
  S2  every page that trashes a table also opens Recently deleted for it - an Undo toast lasts ten seconds
  S3  every service-role edge-function SELECT of a D3 table carries .is('deleted_at', null) (one allowlisted read)
  S4  an offline queue on a D3 table drains its deletes through wh_trash (cfg trash: true)
LIVE (skipped when the local database is down):
  L1  each D3 table has deleted_at and its restrictive <table>_hides_deleted SELECT policy
  L2  wh_trash / wh_restore / wh_recently_deleted exist, run as the caller (security invoker), and anon cannot call them
  L3  every security-definer function and every truth view that reads a D3 table says deleted_at (allowlist below)
  L4  the retention purge removes expired rows from every D3 table

  python tools/validate_deletes_are_recoverable.py
  python tools/validate_deletes_are_recoverable.py --self-test
"""
from __future__ import annotations

import glob
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TABLES = ("logbook", "inventory_items", "schedule_items", "asset_nodes", "pm_assets", "project_links", "project_roles",
          "community_posts")
T_RX = "|".join(TABLES)
CONTAINER = "supabase_db_workhive"

# S3: a read that must keep seeing a deleted row, and why.
EDGE_ALLOW = {
    ("cmms-webhook-receiver", "inventory_items"):
        "decides update-vs-insert by part number: a sync must keep landing on a deleted part (it stays deleted) "
        "rather than collide with the part number the deleted row still holds",
}
# L3: definer functions that read a D3 table and must count or touch deleted rows too, and why.
FN_ALLOW = {
    "check_logbook_rate_limit": "a deleted entry still counts toward the abuse rate limit",
    "check_hive_quota_logbook": "a deleted entry occupies the hive until the purge",
    "photo_attach_stats": "storage telemetry - a deleted row's photo is still stored",
    "export_hive_data": "a data export carries every row, deleted_at included",
    "delete_worker_data": "erasure removes deleted rows too",
    "sync_auth_uid_on_signup": "identity binding applies to every row",
    "sync_asset_identity": "keeps asset and PM-asset identity consistent whether or not either is deleted",
    "sync_pm_asset_identity": "same as sync_asset_identity",
    "guard_staged_stock": "reads one item's quantity by id for a staging guard",
    "roll_vehicle_odometer": "writes the odometer of the asset a new entry names",
    "notify_submission_decided": "notifies about one row by id, on its own decision",
    "notify_wo_assigned": "notifies about one entry by id, on its own assignment",
    "guard_and_audit_project_removal": "counts a project's links for its own audit row",
    "audit_asset_node_delete": "audit trigger on the purge",
    "audit_pm_asset_delete": "audit trigger on the purge",
    "audit_asset_approval_decision": "audit trigger on a decision",
    "audit_logbook_post_close_amendment": "audit trigger on an amendment",
    "audit_project_role_change": "audit trigger on insert/delete",
    "cleanup_project_links_on_target_delete": "runs on the purge",
    "hard_delete_expired_soft_deletes": "the purge itself",
    "guard_name_held_by_deleted": "looks for the deleted row on purpose",
    "replace_deleted_pairing": "looks for the deleted row on purpose",
    "bring_personal_history_into_hive": "moves every personal row, deleted ones included, so a restore lands in the hive",
    "writeback_service_job_to_logbook": "writes a new entry",
    "land_accepted_job_on_dayplan": "writes a new plan item",
    "ensure_pm_asset_for_node": None,     # must filter - listed so a missing filter names it
    "get_pm_compliance_smrp": "reads PM scope through v_pm_scope_items_truth, which hides a deleted PM asset's scope; "
                              "its pm_assets lookup is by the id that view returned",
    "sweep_pm_auto_hail": "reads due PM scope through v_pm_scope_items_truth (deleted PM assets hidden); its pm_assets "
                          "lookup is the owner of a scope item that view returned",
    "community_post_rate_limit": "a deleted post still counts toward the 30-second limit (delete-and-repost must not buy a slot)",
    "check_hive_quota_community": "a deleted post occupies the hive until the purge",
    "report_community_post": "acts on one post by id, from a feed that already hides deleted posts",
    "set_community_best_answer": "acts on one post by id, from a thread that already hides deleted posts",
    "handle_community_reaction_xp": "reaction trigger on one post by id",
}


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def shipped_sources() -> list[Path]:
    out = [p for p in ROOT.glob("*.html")] + [p for p in ROOT.glob("*.js")]
    return [p for p in out if not p.name.startswith(("_", "."))]


def s1_no_hard_delete(files: dict[str, str]) -> list[str]:
    bad = []
    rx = re.compile(r"from\(\s*(['\"])(" + T_RX + r")\1\s*\)\s*\.delete\(")
    for name, src in files.items():
        for m in rx.finditer(src):
            line = src[:m.start()].count("\n") + 1
            eol = src.find("\n", m.end())
            if re.search(r"//\s*d3-allow:\s*\S", src[m.end():eol if eol >= 0 else None]):
                continue      # a reasoned exception on the same line (a wizard taking back its own fresh rows)
            bad.append(f"S1 {name}:{line} deletes {m.group(2)} outright - use whTrash(db, '{m.group(2)}', id, ...)")
    return bad


def s2_offers_recently_deleted(files: dict[str, str]) -> list[str]:
    bad = []
    for name, src in files.items():
        if name == "utils.js":
            continue
        trashed = set(re.findall(r"whTrash\(\s*db\s*,\s*['\"](" + T_RX + r")['\"]", src))
        offered = set(re.findall(r"whRecentlyDeleted\(\s*db\s*,\s*['\"](" + T_RX + r")['\"]", src))
        offered |= set(re.findall(r"data-table=['\"](" + T_RX + r")['\"]", src))
        for t in sorted(trashed - offered):
            bad.append(f"S2 {name} trashes {t} but never opens Recently deleted for it - the Undo toast lasts ten seconds")
    return bad


def s3_edge_reads(fn_files: dict[str, str]) -> list[str]:
    bad = []
    rx = re.compile(r"from\(\s*(['\"])(" + T_RX + r")\1\s*\)")
    for rel, src in fn_files.items():
        fn = rel.replace("\\", "/").split("/")[0]
        for m in rx.finditer(src):
            sm = re.match(r"\s*\.select\(", src[m.end():])
            if not sm:
                continue
            if (fn, m.group(2)) in EDGE_ALLOW:
                continue
            i = m.end() + sm.end()
            depth, j = 1, i
            while depth and j < len(src):
                depth += {"(": 1, ")": -1}.get(src[j], 0)
                j += 1
            chain = src[j:j + 400]
            end = re.search(r";|\n\s*\n|await\s", chain)
            chain = chain[:end.start()] if end else chain
            if not re.search(r"\.is\(\s*['\"]deleted_at['\"]\s*,\s*null\s*\)", chain):
                line = src[:m.start()].count("\n") + 1
                bad.append(f"S3 supabase/functions/{rel}:{line} reads {m.group(2)} without .is('deleted_at', null) - "
                           "a service-role read bypasses the hide policy")
    return bad


def s4_offline_queue(files: dict[str, str]) -> list[str]:
    bad = []
    q = files.get("offline-queue.js", "")
    if "cfg.trash" not in q or "wh_trash" not in q:
        bad.append("S4 offline-queue.js no longer drains a cfg.trash table's delete through wh_trash")
    for name, src in files.items():
        for m in re.finditer(r"whCreateQueue\(\{([\s\S]{0,600}?)\}\)", src):
            body = m.group(1)
            t = re.search(r"table:\s*['\"](" + T_RX + r")['\"]", body)
            if t and re.search(r"op:\s*['\"]delete['\"]", src) and not re.search(r"trash:\s*true", body):
                bad.append(f"S4 {name}: its offline queue on {t.group(1)} queues deletes but is not trash: true - the "
                           "drain would delete for good")
    return bad


def psql(sql: str) -> list[list[str]] | None:
    try:
        r = subprocess.run(["docker", "exec", CONTAINER, "psql", "-U", "postgres", "-d", "postgres", "-At", "-F", "\x1f",
                            "-c", sql], capture_output=True, text=True, encoding="utf-8", timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    return [ln.split("\x1f") for ln in r.stdout.splitlines() if ln.strip()]


def live() -> tuple[list[str], str]:
    ping = psql("select 1")
    if not ping:
        return [], "local database not reachable - live checks skipped"
    bad = []
    tl = ",".join(f"'{t}'" for t in TABLES)
    cols = {r[0] for r in psql(f"select table_name from information_schema.columns where table_schema='public' "
                                 f"and column_name='deleted_at' and table_name in ({tl})") or []}
    pols = {r[0] for r in psql(f"select tablename from pg_policies where schemaname='public' and permissive='RESTRICTIVE' "
                                 f"and cmd='SELECT' and policyname = tablename || '_hides_deleted' and tablename in ({tl})") or []}
    for t in TABLES:
        if t not in cols:
            bad.append(f"L1 {t} has no deleted_at column")
        if t not in pols:
            bad.append(f"L1 {t} has no restrictive {t}_hides_deleted SELECT policy - deleted rows show on every page")
    fns = psql("select p.proname, p.prosecdef, has_function_privilege('anon', p.oid, 'execute') from pg_proc p "
               "where p.pronamespace='public'::regnamespace and p.proname in ('wh_trash','wh_restore','wh_recently_deleted')") or []
    seen = {r[0]: r for r in fns}
    for f in ("wh_trash", "wh_restore", "wh_recently_deleted"):
        r = seen.get(f)
        if not r:
            bad.append(f"L2 {f} is missing")
            continue
        if r[1] == "t":
            bad.append(f"L2 {f} is SECURITY DEFINER - it must run as the caller so each table's own permission decides")
        if r[2] == "t":
            bad.append(f"L2 anon can execute {f}")
    rows = psql("select p.proname, replace(replace(p.prosrc, chr(10), ' '), chr(13), ' ') from pg_proc p where p.pronamespace='public'::regnamespace and p.prosecdef "
                "and p.proname not like 'wh\\_%' and p.prosrc ~* '(from|join)\\s+(public\\.)?(" + T_RX + ")\\M'") or []
    for name, src in [(r[0], "\x1f".join(r[1:])) for r in rows]:
        if FN_ALLOW.get(name):
            continue
        if not re.search(r"deleted_at", src):
            bad.append(f"L3 definer function {name} reads a D3 table and never says deleted_at - it bypasses the hide "
                       "policy, so a deleted row shows wherever it is used (or allowlist it with a reason)")
    views = psql("select v.view_name, replace(pg_get_viewdef(('public.'||v.view_name)::regclass, true), chr(10), ' ') from "
                 "(select distinct view_name from information_schema.view_table_usage where view_schema='public' "
                 f"and table_name in ({tl})) v") or []
    for r in views:
        name, d = r[0], "\x1f".join(r[1:])
        if "deleted_at" not in d:
            bad.append(f"L3 view {name} reads a D3 table and never says deleted_at - a definer or service-role reader of "
                       "it bypasses the hide policy")
    purge = psql("select replace(prosrc, chr(10), ' ') from pg_proc where proname='hard_delete_expired_soft_deletes'") or []
    src = "\x1f".join(purge[0]) if purge else ""
    for t in TABLES:
        if not re.search(r"(?:'|public\.)" + t + r"\b", src):
            bad.append(f"L4 the retention purge never removes expired {t} rows - a deleted row would be kept forever")
    return bad, f"live: {len(TABLES)} tables, {len(rows)} definer readers, {len(views)} views read"


def collect() -> tuple[dict[str, str], dict[str, str]]:
    files = {p.name: _read(p) for p in shipped_sources()}
    fn_files = {}
    base = ROOT / "supabase" / "functions"
    for f in glob.glob(str(base / "**" / "*.ts"), recursive=True):
        if ".test." in f or "_test" in f:
            continue
        fn_files[os.path.relpath(f, base)] = _read(Path(f))
    return files, fn_files


def static(files, fn_files) -> list[str]:
    return s1_no_hard_delete(files) + s2_offers_recently_deleted(files) + s3_edge_reads(fn_files) + s4_offline_queue(files)


def self_test() -> int:
    ok = True
    page_bad = {"x.html": "await db.from('logbook').delete().eq('id', id)"}
    page_good = {"x.html": "await whTrash(db, 'logbook', id, {}); whRecentlyDeleted(db, 'logbook', {})"}
    page_noview = {"x.html": "await whTrash(db, 'inventory_items', id, {})"}
    edge_bad = {"ai-gateway/index.ts": "const r = await db.from('asset_nodes').select('tag').eq('hive_id', h);"}
    edge_good = {"ai-gateway/index.ts": "const r = await db.from('asset_nodes').select('tag').is('deleted_at', null).eq('hive_id', h);"}
    edge_allow = {"cmms-webhook-receiver/index.ts": "await db.from('inventory_items').select('id').eq('hive_id', h);"}
    q_good = {"offline-queue.js": "if (op === 'delete' && cfg.trash) { supabase.rpc('wh_trash', {}) }"}
    q_bad = {"offline-queue.js": "if (op === 'delete') {}"}
    page_allow = {"x.html": "await db.from('asset_nodes').delete().eq('id', n);   // d3-allow: wizard rollback of its own rows"}
    page_bare_allow = {"x.html": "await db.from('asset_nodes').delete().eq('id', n);   // d3-allow:"}
    cases = [
        ("hard delete is caught", s1_no_hard_delete(page_bad), True),
        ("a reasoned d3-allow passes", s1_no_hard_delete(page_allow), False),
        ("a d3-allow with no reason is caught", s1_no_hard_delete(page_bare_allow), True),
        ("whTrash passes", s1_no_hard_delete(page_good) + s2_offers_recently_deleted(page_good), False),
        ("trash without Recently deleted is caught", s2_offers_recently_deleted(page_noview), True),
        ("unfiltered service-role read is caught", s3_edge_reads(edge_bad), True),
        ("filtered read passes", s3_edge_reads(edge_good), False),
        ("allowlisted read passes", s3_edge_reads(edge_allow), False),
        ("queue drains through wh_trash", s4_offline_queue(q_good), False),
        ("queue that deletes for good is caught", s4_offline_queue(q_bad), True),
    ]
    for label, got, want_bad in cases:
        hit = bool(got)
        print(f"  {'ok ' if hit == want_bad else 'BAD'} {label}" + (f"  -> {got[0][:90]}" if got else ""))
        ok &= hit == want_bad
    print("SELF-TEST " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--self-test" in sys.argv:
        return self_test()
    files, fn_files = collect()
    bad = static(files, fn_files)
    lbad, note = live()
    bad += lbad
    for b in bad:
        print("  " + b)
    if bad:
        print(f"FAIL deletes-are-recoverable - {len(bad)} problem(s); {note}")
        return 1
    print(f"PASS deletes-are-recoverable - no page deletes a D3 table for good; every page that trashes one opens Recently "
          f"deleted; every service-role read filters deleted rows; the offline queue drains into the trash; {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
