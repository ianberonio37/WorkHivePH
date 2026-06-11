"""
Truth-View Consumer-Column Validator -- WorkHive Platform Guardian (forward-only ratchet)
=========================================================================================
Catches the PROJ-DRIFT bug class (2026-06-10 deep walk): a consumer SELECTs / filters a
column that the canonical `v_*_truth` VIEW does not expose. `v_project_truth` aliases
`p.id AS project_id` and `p.end_date AS target_end_date` and pre-filters deleted_at
internally -- so it has NO id/end_date/deleted_at. FIVE consumers (project-progress,
project-report.html, project-orchestrator x2, scheduled-agents x2) still queried the old
base-table names -> PostgREST 400 -> the WHOLE project vertical 404'd/emptied SILENTLY
(service-role reads returned "not found", front-end leaked the raw error). The existing
`audit_phantom_columns.py` is the INVERSE (registry columns with zero consumers) and
canNOT catch this; `seeder_insert_columns` guards WRITE payloads, this guards READS.

For every `.from('v_<x>_truth')` in HTML / JS / edge TS, it parses the chained
`.select(...)` column list (alias-aware: `alias:realcol` -> checks realcol, `col::cast`
-> checks col) plus `.eq/.neq/.gt/.gte/.lt/.lte/.like/.ilike/.is/.in/.contains/.filter/
.order('<col>', ...)` first-arg columns, and verifies each referenced column EXISTS on
that view. Source of truth = the LIVE DB (information_schema, which includes views), NOT
the registry -- `canonical_registry.json` views[].columns is EMPTY (the miner doesn't
parse CREATE VIEW select lists). Degrades to SKIP (pass) if the DB is unreachable.

FORWARD-ONLY RATCHET (Mega Gate Rule B): baseline the current mismatch count; FAIL only
when it RISES (a NEW drift). The baseline auto-tightens as the backlog is paid down.

Self-test:  python validate_truth_view_consumer_columns.py --self-test
Baseline:   truth_view_consumer_columns_baseline.json
Output:     truth_view_consumer_columns_report.json
Sentinel binding: name the L2 test "test('truth_view_consumer_columns: ...')".
"""
import re, json, sys, os, glob, subprocess
from pathlib import Path

from validator_utils import format_result  # noqa: E402

ROOT = Path(__file__).resolve().parent
BASELINE = ROOT / "truth_view_consumer_columns_baseline.json"
DB_CONTAINER = "supabase_db_workhive"

CHECK_NAMES = ["truth_view_consumers_use_real_columns"]
CHECK_LABELS = {
    "truth_view_consumers_use_real_columns":
        "L0  No NEW consumer reads a column absent from the v_*_truth view it queries "
        "(forward-only; catches canonical-view column drift like PROJ-DRIFT)",
}

# Chained filter/order methods whose FIRST string arg is a column name.
COL_ARG_METHODS = ("eq", "neq", "gt", "gte", "lt", "lte", "like", "ilike",
                   "is", "in", "contains", "containedBy", "filter", "order")
RE_FROM_TRUTH = re.compile(r"\.from\(\s*['\"](v_[a-z0-9_]+_truth)['\"]\s*\)")
RE_FROM_ANY = re.compile(r"\.from\(")  # ANY relation -> bounds each query so a later non-truth query can't bleed its .eq() onto a prior truth view
RE_SELECT = re.compile(r"\.select\(\s*(['\"`])(.*?)\1", re.S)
RE_COLARG = re.compile(
    r"\.(?:" + "|".join(COL_ARG_METHODS) + r")\(\s*(['\"])([A-Za-z_][A-Za-z0-9_]*)\1"
)
# PostgREST select tokens we never resolve to a single view column.
_SKIP_SELECT_TOKENS = {"*", "count", ""}


def live_view_schema():
    """{view_or_table: set(columns)} from the live DB (information_schema includes
    views), or None if unreachable."""
    try:
        r = subprocess.run(
            ["docker", "exec", DB_CONTAINER, "psql", "-U", "postgres", "-d", "postgres", "-tAc",
             "select table_name||'|'||column_name from information_schema.columns "
             "where table_schema='public';"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0 or not r.stdout.strip():
            return None
    except Exception:
        return None
    schema = {}
    for line in r.stdout.splitlines():
        if "|" in line:
            t, c = line.split("|", 1)
            schema.setdefault(t.strip(), set()).add(c.strip())
    return schema or None


def _strip_comments(text, kind):
    if kind == "html":
        text = re.sub(r"<!--[\s\S]*?-->", "", text)
    # JS/TS line + block comments (safe enough for our scan; also covers <script> bodies)
    text = re.sub(r"/\*[\s\S]*?\*/", "", text)
    text = re.sub(r"^[ \t]*//[^\n]*$", "", text, flags=re.MULTILINE)
    return text


def _split_top_level(s):
    """Comma-split a PostgREST select list, respecting (...) embeds."""
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(":
            depth += 1; cur += ch
        elif ch == ")":
            depth -= 1; cur += ch
        elif ch == "," and depth == 0:
            out.append(cur); cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return out


def _real_col(token):
    """Resolve a select token to the underlying view column, or None to skip.
    `alias:realcol` -> realcol ; `col::cast` -> col ; embeds (with `(`) -> None."""
    t = token.strip()
    if not t or "(" in t:           # embedded resource / function -> skip
        return None
    if t in _SKIP_SELECT_TOKENS:
        return None
    if "::" in t:                   # cast: col::type -> col
        t = t.split("::", 1)[0].strip()
    if ":" in t:                    # rename: alias:source -> source (the real column)
        t = t.split(":", 1)[1].strip()
    return t if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", t) else None


def _refs_in_query(window):
    """Columns referenced by a single .from(...) query window: select list + filter args."""
    cols = set()
    msel = RE_SELECT.search(window)
    if msel:
        # template literal with ${...} interpolation -> can't statically resolve; skip select
        sel = msel.group(2)
        if "${" not in sel:
            for tok in _split_top_level(sel):
                rc = _real_col(tok)
                if rc:
                    cols.add(rc)
    for m in RE_COLARG.finditer(window):
        cols.add(m.group(2))
    return cols


def _iter_query_windows(src):
    """Yield (view, window) for each `.from('v_*_truth')` query. The window is
    bounded at the NEAREST of (next `.from(` of ANY relation, next `;`):
      - the `.from(` bound keeps Promise.all array items (comma-separated, no `;`
        between them) from bleeding one query's filters onto the prior view;
      - the `;` bound stops a DOM/array method call AFTER the query statement
        (e.g. `el.classList.contains('open')`, `arr.filter('x')`) from being
        misattributed to the view -- those collide with PostgREST filter method
        names (contains/filter/is/in) and caused the dayplanner `open` FP.
    """
    any_from = [a.start() for a in RE_FROM_ANY.finditer(src)]
    for m in RE_FROM_TRUTH.finditer(src):
        nxt = next((a for a in any_from if a > m.start()), len(src))
        semi = src.find(";", m.end())
        if semi != -1:
            nxt = min(nxt, semi)
        yield m.group(1), src[m.end():nxt]


def find_mismatches(schema):
    """Returns sorted list of 'file:view.col' for referenced columns absent from the view."""
    blobs = {}
    for p in sorted(ROOT.glob("*.html")):
        if re.search(r"\.backup\d*\.html$|-test\.html$", p.name):
            continue
        blobs[p.name] = _strip_comments(p.read_text(encoding="utf-8", errors="replace"), "html")
    for sub in ("learn", "feedback", "about"):
        for p in sorted((ROOT / sub).rglob("*.html")) if (ROOT / sub).exists() else []:
            blobs[p.relative_to(ROOT).as_posix()] = _strip_comments(
                p.read_text(encoding="utf-8", errors="replace"), "html")
    for p in sorted(ROOT.glob("*.js")):
        if p.name == "sw.js":
            continue
        blobs[p.name] = _strip_comments(p.read_text(encoding="utf-8", errors="replace"), "js")
    fns = ROOT / "supabase" / "functions"
    if fns.exists():
        for ts in sorted(fns.rglob("*.ts")):
            blobs[f"edge:{ts.relative_to(fns).as_posix()}"] = _strip_comments(
                ts.read_text(encoding="utf-8", errors="replace"), "js")

    mismatches = []
    for fname, src in blobs.items():
        for view, window in _iter_query_windows(src):
            cols = schema.get(view)
            if cols is None:        # view not in live DB (typo / not-yet-applied) -> separate concern
                continue
            for ref in _refs_in_query(window):
                if ref not in cols:
                    mismatches.append(f"{fname}:{view}.{ref}")
    return sorted(set(mismatches))


# ---------------------------------------------------------------------------
# Self-test -- proves the parser discriminates the PROJ-DRIFT pattern without
# needing the (now-fixed) live bug.
# ---------------------------------------------------------------------------
def _self_test():
    schema = {"v_project_truth": {"project_id", "hive_id", "project_type", "status",
                                  "start_date", "target_end_date", "budget_php", "created_at",
                                  "name", "project_code", "owner_name"}}

    def refs(window):
        return _refs_in_query(window)

    ok = True
    # 1) BAD (pre-fix): selects id + end_date, filters on id + deleted_at -> all flagged
    bad = ".from('v_project_truth').select('id, hive_id, project_type, status, start_date, " \
          "end_date, budget_php, created_at').eq('id', x).is('deleted_at', null)"
    bad_refs = refs(bad)
    bad_missing = {c for c in bad_refs if c not in schema["v_project_truth"]}
    want_bad = {"id", "end_date", "deleted_at"}
    if bad_missing != want_bad:
        print(f"  FAIL self-test 1 (bad pattern): expected missing {want_bad}, got {bad_missing}")
        ok = False
    else:
        print(f"  PASS self-test 1: pre-fix pattern flags {sorted(want_bad)}")

    # 2) GOOD (post-fix): alias id:project_id + end_date:target_end_date, filter on project_id
    good = ".from('v_project_truth').select('id:project_id, hive_id, project_type, status, " \
           "start_date, end_date:target_end_date, budget_php, created_at').eq('project_id', x)"
    good_missing = {c for c in refs(good) if c not in schema["v_project_truth"]}
    if good_missing:
        print(f"  FAIL self-test 2 (good pattern): expected 0 missing, got {good_missing}")
        ok = False
    else:
        print("  PASS self-test 2: post-fix alias pattern flags nothing")

    # 3) select('*') + embed must not false-flag; cast col::text resolves to col
    edge = ".from('v_project_truth').select('*, items:project_items(id,title), budget_php::text')"
    edge_missing = {c for c in refs(edge) if c not in schema["v_project_truth"]}
    if edge_missing:
        print(f"  FAIL self-test 3 (star/embed/cast): expected 0 missing, got {edge_missing}")
        ok = False
    else:
        print("  PASS self-test 3: *, embed, and ::cast handled (no false positives)")

    # 4) a genuinely wrong column on a good query IS caught
    wrong = ".from('v_project_truth').select('project_id, bogus_col').eq('project_id', x)"
    wrong_missing = {c for c in refs(wrong) if c not in schema["v_project_truth"]}
    if wrong_missing != {"bogus_col"}:
        print(f"  FAIL self-test 4 (real typo): expected {{'bogus_col'}}, got {wrong_missing}")
        ok = False
    else:
        print("  PASS self-test 4: a real bogus column is caught")

    # 5) FP guard: a DOM/array method call AFTER the query statement (`;`) must
    #    not be attributed to the view. This is the dayplanner `open` FP:
    #    `.from('v_logbook_truth').select('*')...;  el.classList.contains('open')`.
    lb_schema = {"v_logbook_truth": {"worker_name", "date", "status", "problem"}}
    fp_src = (
        "const { data } = await db.from('v_logbook_truth').select('*')"
        ".eq('worker_name', w).order('date', { ascending: false });\n"
        "  const isOpen = body.classList.contains('open');\n"
        "  rows.filter('open');\n"
    )
    fp_hits = []
    for view, window in _iter_query_windows(fp_src):
        for ref in _refs_in_query(window):
            if ref not in lb_schema.get(view, set()):
                fp_hits.append(f"{view}.{ref}")
    if fp_hits:
        print(f"  FAIL self-test 5 (DOM-method FP): expected 0, got {fp_hits}")
        ok = False
    else:
        print("  PASS self-test 5: post-statement .contains('open')/.filter() not misattributed")

    # 6) ...but a REAL bad column still inside the query statement IS caught
    #    (proves the `;` bound didn't blind us to genuine drift).
    real_src = "await db.from('v_logbook_truth').select('worker_name, bogus').eq('status', s);"
    real_hits = []
    for view, window in _iter_query_windows(real_src):
        for ref in _refs_in_query(window):
            if ref not in lb_schema.get(view, set()):
                real_hits.append(f"{view}.{ref}")
    if real_hits != ["v_logbook_truth.bogus"]:
        print(f"  FAIL self-test 6 (real drift still caught): expected ['v_logbook_truth.bogus'], got {real_hits}")
        ok = False
    else:
        print("  PASS self-test 6: real in-statement drift still caught after `;` bound")

    print("\nSelf-test:", "ALL PASS" if ok else "FAILURES")
    sys.exit(0 if ok else 1)


def main():
    if "--self-test" in sys.argv:
        _self_test()

    print("Truth-View Consumer-Column Validator (forward-only ratchet)")
    print("==========================================================")
    schema = live_view_schema()
    if schema is None:
        print("  live DB unreachable -> SKIP (DB-dependent validator; no false alarms offline)")
        format_result(CHECK_NAMES, CHECK_LABELS,
                      [{"check": "truth_view_consumers_use_real_columns", "skip": True}])
        json.dump({"skipped": True}, open("truth_view_consumer_columns_report.json", "w"))
        sys.exit(0)

    mismatches = find_mismatches(schema)
    cur = len(mismatches)
    base = None
    if BASELINE.exists():
        try:
            base = json.load(open(BASELINE, encoding="utf-8")).get("count")
        except Exception:
            base = None

    issues = []
    if base is None:
        json.dump({"count": cur, "mismatches": mismatches}, open(BASELINE, "w", encoding="utf-8"), indent=2)
        print(f"  baseline SEEDED at {cur} pre-existing mismatch(es). First run PASS.")
    elif cur > base:
        new = [m for m in mismatches]
        issues.append({"check": "truth_view_consumers_use_real_columns",
                       "reason": f"NEW v_*_truth consumer-column drift: count rose {base} -> {cur}. "
                                 f"A consumer reads a column absent from the view (PostgREST 400 -> "
                                 f"silent empty/404). Offenders: {', '.join(new)}"})
    elif cur < base:
        json.dump({"count": cur, "mismatches": mismatches}, open(BASELINE, "w", encoding="utf-8"), indent=2)
        print(f"  backlog fell {base} -> {cur}; baseline auto-tightened (Rule B).")
    else:
        print(f"  at baseline ({cur} known pre-existing mismatch(es)).")

    if mismatches:
        print(f"  current backlog ({cur}): {', '.join(mismatches[:12])}{' ...' if cur > 12 else ''}")
    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)
    print(f"\nTruth-view consumer columns: {n_pass} PASS, {n_fail} FAIL, {n_skip} SKIP")
    json.dump({"count": cur, "baseline": base, "mismatches": mismatches, "n_fail": n_fail},
              open("truth_view_consumer_columns_report.json", "w", encoding="utf-8"), indent=2)
    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
