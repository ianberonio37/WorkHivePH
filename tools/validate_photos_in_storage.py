#!/usr/bin/env python3
"""photos-in-storage - BRH 9 AB (2026-10-21): a photo lives in Supabase Storage, never inside its row.

WHAT WAS WRONG (production, read-only, 2026-10-21): logbook.photo held 22 photos (4.35 MB) and inventory_items.photo 5
(0.54 MB) as base64 text. The free 500 MB database grew by every photo while the 1 GB of file storage sat unused, and
nine list reads shipped every photo in free egress (the dayplanner's thousand logbook rows with select *, the
inventory's 2,000 parts, logbook's two feeds naming photo); both tables are in the realtime publication, so every
change to a row with a photo also sent the photo to every subscriber.

WHAT THIS HOLDS
  S1 READS   no list read of logbook / inventory_items / v_logbook_truth / v_inventory_items_truth ships the picture
             (free_plan_evidence.photo_reads: select * or a list naming photo; whRowCols('<the same source>') is safe)
  S2 COLUMNS utils.js WH_ROW_COLS names each of the four sources, never photo, always photo_path + photo_thumb_path
  S3 SCHEMA  (live) each WH_ROW_COLS list is exactly the source's live columns minus photo - a column added to the
             table that the list lacks would silently go missing from every page that read it with *
  S4 WRITES  every path that writes a picked photo uploads it first (whPhotoSettle): logbook's new entry, edit and
             offline drain; inventory's part form, offline queue (offline-queue.js prepare, run before the write) and
             old-device migration. The whole-row inventory sync never carries the photo columns. The list cards and
             details draw a photo by name (data-wh-photo) and fill it (whPhotoHydrate).
  S5 SERVER  (live) the bucket entry-photos is private, <= 1 MB, images only; uploads go only into the uploader's
             folder; a read needs the uploader or a row the reader can see (wh_entry_photo_visible, SECURITY INVOKER);
             a delete needs the owner and no row naming it; the photo-name CHECKs stand; and the server REFUSES new
             inline image data - probed as a signed-in member inside a transaction that is rolled back.
  S6 DATA    (live) no row of the local stack holds inline image data.

    python tools/validate_photos_in_storage.py            # the gate
    python tools/validate_photos_in_storage.py --self-test
The live proof as the real cast (old read shape vs new, refusal, privacy, delete rules, the one-time move) is
tools/prove_photos_in_storage.py; the move itself is tools/move_inline_photos_to_storage.py.
"""
from __future__ import annotations

import io
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
CHECK_NAMES = ["photos-in-storage"]
DB = "supabase_db_workhive"
SOURCES = ("logbook", "inventory_items", "v_logbook_truth", "v_inventory_items_truth")

# (file, a function or region the call must sit in, what must be in it, why)
WRITES = [
    ("logbook.html", "async function addEntry(", r"whPhotoSettle\(db, _authUid, payload\)", "a new entry uploads its photo before the insert"),
    ("logbook.html", "async function _drainOfflineQueue(", r"whPhotoSettle\(db, _authUid, _photoOf\)", "the offline drain uploads a queued photo before the write"),
    ("logbook.html", "async function saveEditFromForm(", r"whPhotoSettle\(db, _authUid, updates\)", "an edit uploads a picked photo before the update"),
    ("logbook.html", "async function saveEditFromForm(", r"if \(_lbPhotoChanged\) \{", "an edit sends the photo columns only when the photo changed"),
    ("inventory.html", "async function submitPart(", r"whPhotoSettle\(db, _authUid, payload\)", "the part form uploads its photo before any write"),
    ("inventory.html", "function _ensureInvQueue(", r"prepare: async \(item, sb\) =>[\s\S]{0,400}?whPhotoSettle\(sb, _authUid, q\)", "a part queued offline uploads its photo on reconnect"),
    ("inventory.html", "function saveInventory(", r"photo, photo_path, photo_thumb_path, \.\.\.row\b", "the whole-row sync never carries the photo columns"),
    ("offline-queue.js", "async function drain(", r"cfg\.prepare\(item, supabase\)[\s\S]{0,300}?s\.put\(item\)[\s\S]{0,200}?if \(op === 'insert'\)", "the queue runs prepare and stores its result before the write"),
]
# (file, pattern that must be present, why) - drawing a stored photo by name
DRAWS = [
    ("logbook.html", r"data-wh-photo=\"\$\{escHtml\(name\)\}\"", "logbook draws a stored photo by name"),
    ("logbook.html", r"whPhotoHydrate\(db, list\)", "logbook fills the list's thumbnails"),
    ("logbook.html", r"whPhotoHydrate\(db, document\.getElementById\('modal-content'\)\)", "logbook fills the detail's photo"),
    ("inventory.html", r"data-wh-photo=\"\$\{escHtml\(name\)\}\"", "inventory draws a stored photo by name"),
    ("inventory.html", r"whPhotoHydrate\(db, list\)", "inventory fills the list's thumbnails"),
    ("inventory.html", r"whPhotoHydrate\(db, document\.getElementById\('detail-content'\)\)", "inventory fills the detail's photo"),
]
# an inline write that must never come back
FORBIDDEN = [
    ("inventory.html", r"\.update\(\{ \.\.\.detail, photo:", "the part edit re-sent the cached photo"),
    ("logbook.html", r"photo:\s+currentPhotoData,", "the logbook edit wrote whatever the form held into photo"),
    ("inventory.html", r"photo:\s+currentPhotoData,", "the part form wrote the picked data: URL into photo"),
]


def _region(src: str, start: str) -> str:
    """The body of the function that opens at `start` (braces balanced; strings and comments are not special-cased -
    a quoted brace in these bodies would only widen the region)."""
    i = src.find(start)
    if i < 0:
        return ""
    j = src.find("{", i)
    depth = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            depth += 1
        elif src[k] == "}":
            depth -= 1
            if depth == 0:
                return src[j:k + 1]
    return src[j:]


def row_cols(utils: str) -> dict[str, list[str]]:
    out = {}
    m = re.search(r"var WH_ROW_COLS = \{(.*?)\n\};", utils, re.S)
    if not m:
        return out
    for e in re.finditer(r"\b([a-z_]+):\s*((?:'[^']*'\s*\+?\s*)+)", m.group(1)):
        out[e.group(1)] = [c for c in "".join(re.findall(r"'([^']*)'", e.group(2))).split(",") if c]
    return out


def check_static(files: dict[str, str]) -> list[str]:
    from free_plan_evidence import photo_reads
    issues = []
    pages = {k: v for k, v in files.items() if k.endswith(".html")}
    for r in photo_reads(pages):
        issues.append(f"S1 {r['page']}:{r['line']} a list read of {r['src']} ships the picture ({r['cols']}) - read "
                      f"whRowCols('{r['src']}') or the columns the list shows")
    cols = row_cols(files.get("utils.js", ""))
    for s in SOURCES:
        c = cols.get(s)
        if not c:
            issues.append(f"S2 utils.js WH_ROW_COLS has no list for {s}")
            continue
        if "photo" in c or "*" in c:
            issues.append(f"S2 WH_ROW_COLS.{s} names the picture ({'photo' if 'photo' in c else '*'})")
        for need in ("photo_path", "photo_thumb_path"):
            if need not in c:
                issues.append(f"S2 WH_ROW_COLS.{s} lacks {need} - a list could not draw the photo")
    for f, start, pat, why in WRITES:
        body = _region(files.get(f, ""), start)
        if not body:
            issues.append(f"S4 {f}: {start.strip('( ')} not found - {why}")
        elif not re.search(pat, body):
            issues.append(f"S4 {f}: {why} - not held in {start.strip('( ')}")
    for f, pat, why in DRAWS:
        if not re.search(pat, files.get(f, "")):
            issues.append(f"S4 {f}: {why} - missing")
    for f, pat, why in FORBIDDEN:
        if re.search(pat, files.get(f, "")):
            issues.append(f"S4 {f}: {why} - an inline photo write is back")
    return issues


def psql(sql: str) -> str | None:
    """stdout, or None when the database cannot be reached. A query that FAILS raises: a broken live check must turn
    the gate red, never quietly skip the rows it could not read (ON_ERROR_STOP)."""
    try:
        r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-At", "-v",
                            "ON_ERROR_STOP=1", "-f", "-"], input=sql, capture_output=True, text=True, encoding="utf-8",
                           timeout=60)
    except Exception:
        return None
    if r.returncode == 0:
        return r.stdout
    if "could not connect" in (r.stderr or "") or "No such container" in (r.stderr or "") or "is not running" in (r.stderr or ""):
        return None
    raise RuntimeError("the live query failed: " + (r.stderr or "").strip()[-300:])


def live_state() -> dict | None:
    q = """
select 'col|' || table_name || '|' || string_agg(column_name, ',' order by ordinal_position) from information_schema.columns
 where table_schema = 'public' and table_name in ('logbook','inventory_items','v_logbook_truth','v_inventory_items_truth')
   and column_name <> 'photo' group by table_name;
select 'bucket|' || case when public then 't' else 'f' end || '|' || coalesce(file_size_limit, 0) || '|'
       || array_to_string(allowed_mime_types, ',')
  from storage.buckets where id = 'entry-photos';
select 'pol|' || polcmd::text || '|' || regexp_replace(coalesce(pg_get_expr(polqual, polrelid), '') || ' '
       || coalesce(pg_get_expr(polwithcheck, polrelid), ''), '[[:space:]]+', ' ', 'g')
  from pg_policy where polrelid = 'storage.objects'::regclass and polname like 'entry-photos%';
select 'definer|' || proname || '|' || case when prosecdef then 't' else 'f' end from pg_proc
 where proname in ('wh_entry_photo_visible', 'wh_entry_photo_named');
select 'check|' || conname from pg_constraint where conname in ('logbook_photo_names_are_object_names', 'inventory_items_photo_names_are_object_names');
select 'inline|' || (select count(*) from public.logbook where photo like 'data:%') || '|' || (select count(*) from public.inventory_items where photo like 'data:%');
"""
    out = psql(q)
    if out is None:
        return None
    st = {"cols": {}, "bucket": None, "pols": [], "definer": {}, "checks": [], "inline": None}
    for ln in out.splitlines():
        k, _, rest = ln.partition("|")
        if k == "col":
            t, _, c = rest.partition("|")
            st["cols"][t] = c.split(",")
        elif k == "bucket":
            st["bucket"] = rest.split("|")
        elif k == "pol":
            st["pols"].append(rest.split("|", 1))
        elif k == "definer":
            n, _, d = rest.partition("|")
            st["definer"][n] = d == "t"
        elif k == "check":
            st["checks"].append(rest)
        elif k == "inline":
            st["inline"] = [int(x) for x in rest.split("|")]
    # the refusal, as a signed-in member, rolled back: a new inline photo must not land
    uid = (psql("select hm.auth_uid from public.hive_members hm where hm.status = 'active' and hm.auth_uid is not null limit 1;") or "").strip()
    # the NOTICE says which way it went (psql writes notices to stderr)
    r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-At", "-f", "-"],
                       input=f"""begin;
set local role authenticated;
set local request.jwt.claims = '{{"sub":"{uid}","role":"authenticated"}}';
do $$ begin
  insert into public.logbook (id, worker_name, date, machine, problem, status, auth_uid, photo)
  values ('photos-in-storage-probe', 'probe', now(), 'probe', 'probe', 'Open', '{uid}', 'data:image/jpeg;base64,/9j/4AAQ');
  raise notice 'PROBE accepted';
exception when others then raise notice 'PROBE refused %', sqlerrm;
end $$;
rollback;""", capture_output=True, text=True, encoding="utf-8", timeout=60)
    m = re.search(r"PROBE (accepted|refused)(.*)", r.stderr or "")
    st["probe"] = (m.group(1) + m.group(2)).strip() if m else "no answer"
    return st


def check_live(st: dict, cols: dict[str, list[str]]) -> list[str]:
    issues = []
    for s in SOURCES:
        live, mine = st["cols"].get(s), cols.get(s)
        if live is None:
            issues.append(f"S3 {s} is not in the live schema")
            continue
        if mine is not None and sorted(live) != sorted(mine):
            missing, extra = sorted(set(live) - set(mine)), sorted(set(mine) - set(live))
            issues.append(f"S3 WH_ROW_COLS.{s} differs from the live columns: missing {missing}, not in the table {extra}")
    b = st.get("bucket")
    if not b:
        issues.append("S5 the bucket entry-photos does not exist")
    else:
        if b[0] != "f":
            issues.append("S5 entry-photos is PUBLIC - every photo would be served to anyone holding its URL")
        if not (0 < int(b[1] or 0) <= 1048576):
            issues.append(f"S5 entry-photos allows objects of {b[1]} bytes (at most 1 MB: the pages send <= 700 KB)")
        if not set((b[2] or "").split(",")) <= {"image/jpeg", "image/png", "image/webp"} or not b[2]:
            issues.append(f"S5 entry-photos accepts {b[2] or 'any type'} - images only")
    by = {}
    for cmd, expr in st.get("pols", []):
        by.setdefault(cmd, []).append(expr)
    ins, sel, dele = " ".join(by.get("a", [])), " ".join(by.get("r", [])), " ".join(by.get("d", []))
    if not ("foldername" in ins and "auth.uid()" in ins):
        issues.append("S5 the upload policy does not keep an upload in the uploader's own folder")
    if not ("wh_entry_photo_visible" in sel and "owner_id" in sel) or " true " in f" {sel} ":
        issues.append("S5 the read policy is not 'the uploader, or whoever can read a row naming it'")
    if not ("owner_id" in dele and "wh_entry_photo_named" in dele):
        issues.append("S5 the delete policy lets a client remove an object a row still names, or someone else's")
    if "w" in by or "*" in by:
        issues.append("S5 a policy lets a client overwrite an object (objects are written once, never updated)")
    if st.get("definer", {}).get("wh_entry_photo_visible") is not False:
        issues.append("S5 wh_entry_photo_visible must run as the reader (SECURITY INVOKER) - as definer it sees every row")
    if len(st.get("checks", [])) != 2:
        issues.append("S5 the photo-name CHECKs are missing - image data could go into photo_path under a new name")
    if not str(st.get("probe", "")).startswith("refused"):
        issues.append(f"S5 a signed-in member's new inline photo was not refused ({st.get('probe')})")
    elif "saved separately" not in str(st.get("probe")):
        issues.append(f"S5 the refusal does not tell the person what to do ({st.get('probe')})")
    inl = st.get("inline") or [0, 0]
    if any(inl):
        issues.append(f"S6 rows still hold inline image data: logbook {inl[0]}, inventory_items {inl[1]} - "
                      "tools/move_inline_photos_to_storage.py, then --clear")
    return issues


def tree() -> dict[str, str]:
    files = {p.relative_to(ROOT).as_posix(): p.read_text(encoding="utf-8", errors="replace")
             for p in sorted(set(ROOT.glob("*.html")) | set(ROOT.glob("*/index.html")))}
    for f in ("utils.js", "offline-queue.js"):
        files[f] = (ROOT / f).read_text(encoding="utf-8", errors="replace")
    return files


def main() -> int:
    print("Photos in Storage (BRH 9 AB): a photo lives in the private bucket, its row keeps only the object's names")
    files = tree()
    issues = check_static(files)
    try:
        st = live_state()
    except RuntimeError as e:
        st, issues = {}, issues + [f"S5 {e}"]
    if st == {}:
        pass
    elif st is None:
        print("  SKIP live (S3, S5, S6) - the local database is unreachable; the static checks still decide")
    else:
        issues += check_live(st, row_cols(files["utils.js"]))
    for i in issues:
        print("  [FAIL] " + i)
    if issues:
        print(f"  FAIL - {len(issues)} problem(s)")
        return 1
    print("  PASS - no list read ships a photo; WH_ROW_COLS is every live column but photo; every write uploads first; "
          + ("the bucket is private and row-scoped and the server refuses a new inline photo" if st else "live part skipped"))
    return 0


def self_test() -> int:
    files = tree()
    fails = []
    if check_static(files):
        fails.append("the tree should pass the static checks: " + "; ".join(check_static(files))[:300])

    def mut(name: str, f: str, old: str, new: str, prefix: str) -> None:
        m = dict(files)
        if old not in m[f]:
            fails.append(f"mutant '{name}': its anchor is gone from {f}")
            return
        m[f] = m[f].replace(old, new, 1)
        if not any(i.startswith(prefix) for i in check_static(m)):
            fails.append(f"mutant '{name}' was not caught")

    mut("the dayplanner reads select * again", "dayplanner.html",
        "select(typeof whRowCols === 'function' ? whRowCols('v_logbook_truth') : '*')", "select('*')", "S1")
    mut("a logbook feed names photo again", "logbook.html", "downtime_hours, photo_path, photo_thumb_path, status",
        "downtime_hours, photo, status", "S1")
    mut("a read asks whRowCols for another source", "hive.html", "whRowCols('v_inventory_items_truth')",
        "whRowCols('v_logbook_truth')", "S1")
    mut("the insert reads its whole row back", "logbook.html", ".insert(payload).select('id')", ".insert(payload).select()", "S1")
    mut("WH_ROW_COLS lists photo", "utils.js", "'rejection_reason,deleted_at,deleted_by,photo_path,photo_thumb_path',",
        "'rejection_reason,deleted_at,deleted_by,photo,photo_path,photo_thumb_path',", "S2")
    mut("WH_ROW_COLS drops the thumbnail name", "utils.js", "is_out_of_stock,is_low_stock,is_critical_low,lead_time_days,rejection_reason,auth_uid,photo_path,photo_thumb_path'",
        "is_out_of_stock,is_low_stock,is_critical_low,lead_time_days,rejection_reason,auth_uid,photo_path'", "S2")
    mut("a new entry writes its photo inline", "logbook.html", "try { _photoNames = await whPhotoSettle(db, _authUid, payload); }",
        "try { _photoNames = []; }", "S4")
    mut("the drain inserts before uploading", "logbook.html", "const _up = await whPhotoSettle(db, _authUid, _photoOf);",
        "const _up = [];", "S4")
    mut("an edit sends the form's photo every time", "logbook.html", "    status:                newStatus,\n    // Phase 5b",
        "    photo:                 currentPhotoData,\n    status:                newStatus,\n    // Phase 5b", "S4")
    mut("the whole-row sync carries the photo", "inventory.html", "reorder_point, photo, photo_path, photo_thumb_path, ...row }",
        "reorder_point, ...row }", "S4")
    mut("the queue writes before prepare", "offline-queue.js", "const prepared = await cfg.prepare(item, supabase);",
        "const prepared = null;", "S4")
    mut("the part edit re-sends the cached photo", "inventory.html", ".update(detail)\n", ".update({ ...detail, photo: updated.photo })\n", "S4")
    mut("the logbook list stops filling its thumbnails", "logbook.html", "whPhotoHydrate(db, list)", "void 0", "S4")

    good = {"cols": {s: list(c) for s, c in row_cols(files["utils.js"]).items()}, "bucket": ["f", "1048576", "image/jpeg,image/png,image/webp"],
            "pols": [["a", " ((bucket_id = 'entry-photos'::text) AND ((storage.foldername(name))[1] = (auth.uid())::text))"],
                     ["r", "((bucket_id = 'entry-photos'::text) AND ((owner_id = (auth.uid())::text) OR wh_entry_photo_visible(name))) "],
                     ["d", "((bucket_id = 'entry-photos'::text) AND (owner_id = (auth.uid())::text) AND (NOT wh_entry_photo_named(name))) "]],
            "definer": {"wh_entry_photo_visible": False, "wh_entry_photo_named": True},
            "checks": ["logbook_photo_names_are_object_names", "inventory_items_photo_names_are_object_names"],
            "inline": [0, 0], "probe": "refused Photos are now saved separately from the entry."}
    cols = row_cols(files["utils.js"])
    if check_live(good, cols):
        fails.append("the good live posture should pass: " + "; ".join(check_live(good, cols)))

    def lmut(name: str, change, prefix: str) -> None:
        import copy
        st = copy.deepcopy(good)
        change(st)
        if not any(i.startswith(prefix) for i in check_live(st, cols)):
            fails.append(f"mutant '{name}' was not caught")

    lmut("a column added to logbook that WH_ROW_COLS lacks", lambda st: st["cols"]["logbook"].append("new_column"), "S3")
    lmut("the bucket made public", lambda st: st["bucket"].__setitem__(0, "t"), "S5")
    lmut("the read policy opened to everyone", lambda st: st["pols"].__setitem__(1, ["r", "true"]), "S5")
    lmut("the delete policy without the named check", lambda st: st["pols"].__setitem__(2, ["d", "(owner_id = (auth.uid())::text)"]), "S5")
    lmut("an update policy added", lambda st: st["pols"].append(["w", "true"]), "S5")
    lmut("the visibility function as definer", lambda st: st["definer"].__setitem__("wh_entry_photo_visible", True), "S5")
    lmut("the server accepts an inline photo", lambda st: st.__setitem__("probe", "accepted"), "S5")
    lmut("a row still holds inline image data", lambda st: st.__setitem__("inline", [1, 0]), "S6")
    if fails:
        print("SELF-TEST FAIL:\n  " + "\n  ".join(fails))
        return 1
    print("SELF-TEST PASS (21 mutants caught; the clean tree and the good posture are green)")
    return 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else main())
