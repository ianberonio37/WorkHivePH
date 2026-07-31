#!/usr/bin/env python3
"""validate_paginated_order_totality.py — is every PAGINATED query's ORDER a TOTAL order?

THE BUG CLASS, found live 2026-07-31 by metamorphic relation MR4 (rank stability) and proven before it was
fixed. `marketplace.html` browsed listings with:

    .order('created_at', { ascending: false }).limit(PAGE_SIZE)

`created_at` alone is NOT a total order. A bulk import inserts many rows inside ONE transaction, where `now()`
is fixed, so they share an identical timestamp. Postgres promises nothing about the order of tied rows, and it
genuinely moves: touching an UNRELATED column on one tied row (an ordinary edit — MVCC appends a new tuple at
the end of the heap) made 4 of 12 rows come back at a DIFFERENT RANK while the row SET was identical.

Under `.limit()` / `.range()` that is user-visible: a row can be shown TWICE across a refresh, or SKIPPED
between pages. Under `.limit(1)` it is worse and quieter — "the most recent X" silently picks an ARBITRARY row
among the ties, which is the shape that once resolved the wrong hive for a signed-in worker
([[feedback_resolving_live_is_not_enough_be_deterministic]]). So `.limit(1)` is IN scope, not exempt.

THE RULE: a query that pages or truncates must end its ORDER BY with a column that is unique per row, so the
sort is total and the result deterministic. Adding `.order('id')` last is the whole fix.

Detection is deliberately conservative — it reports a chain only when it can see the whole shape:
  * a `.from(...)` binds the chain (so a stray `.order()`/`.limit()` on a plain JS array is not flagged), and
  * at least one `.order('col')`, and
  * a `.limit(` or `.range(` in the same chain.
A chain whose LAST ordering column is unique-by-construction is TOTAL and passes. Everything else is a
violation, listed with file:line and the exact ordering it used.

Usage:  python tools/validate_paginated_order_totality.py [--selftest] [--verbose] [--update-baseline]
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(ROOT, "paginated_order_baseline.json")

GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"

# Columns that are unique PER ROW of the relation being ordered, so ending an ORDER BY with one makes the
# order TOTAL. `id` is the primary key on every table and view in this schema. The rest are declared here
# with the reason they are unique, because a WRONG entry silently converts a real violation into a pass —
# the same "an exclusion must name its mechanism" discipline the mutation harness uses.
UNIQUE_COLUMNS = {
    "id":           "primary key on every table/view in this schema",
    "uuid":         "synonym for the primary key where a view renames it",
    # v_service_area_presence is one row per service area (verified: 4 rows / 4 distinct service_area)
    "service_area": "v_service_area_presence is one row PER AREA, so the area names the row",
    # a natural key that is UNIQUE by constraint
    "co_number":    "project_change_orders.co_number is the amendment's unique identity on the trail",
    # The v_*_truth views RENAME the primary key rather than dropping it, so each carries a unique column
    # under its own name. Every one below was MEASURED against the live view (count(*) == count(distinct k)),
    # not inferred from the name — the same check caught v_risk_truth, whose asset_id looks like a key and is
    # NOT one (97 rows, 74 distinct, because 23 rows carry a NULL asset_id).
    "alert_id":     "v_alert_truth: 128 rows / 128 distinct",
    "amc_id":       "v_amc_truth: 8 / 8",
    "fmea_mode_id": "v_fmea_truth: 245 / 245",
    "pm_asset_id":  "v_pm_compliance_truth: 91 / 91 (one row per PM asset)",
    "project_id":   "v_project_truth: 12 / 12",
    "reading_id":   "v_sensor_truth: 54 / 54",
    "request_id":   "v_service_open_broadcasts selects service_requests.id AS request_id — the PK carried "
                    "through a lookup join, so unique by construction (the view is empty today, so this one "
                    "is structural rather than measured)",
    "worker_name":  "community_xp: 10 rows / 10 distinct worker_name (PK is worker_name+hive_id, and the "
                    "name is unique within the hive a page is scoped to)",
    "hive_id":      "v_adoption_truth: one snapshot per hive per date, so hive_id closes the tie under the "
                    "snapshot_date ordering these callers use (2 rows / 2 distinct)",
    # READING THE VIEW BEAT GUESSING FROM THE COLUMN NAMES, and this entry is the proof. v_risk_truth was
    # first recorded here as UNORDERABLE — "97 rows, no unique combination, needs a migration" — because
    # every id-shaped candidate failed (asset_id 74, asset+model 76, asset+hive 77, asset+generated_at 80).
    # That premise was WRONG. The view is `SELECT DISTINCT ON (rs.hive_id, rs.asset_name) n.id AS asset_id,
    # ...`, so (hive_id, asset_name) is its key BY CONSTRUCTION — verified 97 rows / 97 distinct — while
    # `asset_id` is a LEFT JOIN column that is NULL for the 23 rows with no approved asset node, which is
    # exactly why it looked keyless. All five callers are .eq('hive_id', ...)-scoped, so asset_name alone is
    # total for them (it is 64/97 platform-wide, unique only WITHIN a hive). No migration needed
    # ([[feedback_check_the_premise_before_building_the_pattern]] — a structural blocker I nearly recorded
    # as real).
    "asset_name":   "v_risk_truth is DISTINCT ON (hive_id, asset_name): 97 rows / 97 distinct on that pair, "
                    "so asset_name is unique within the hive every caller scopes to",
}

# Files that are not product surfaces (fixtures, vendored, build output).
SKIP_DIRS = {"node_modules", ".git", "substrate", "tests", "remotion_scenes", ".tmp", "dist", "build"}

CHAIN_RE = re.compile(
    r"\.from\(\s*['\"][a-zA-Z0-9_]+['\"]\s*\)"      # the relation binds the chain
    r"(?P<body>(?:[^;]{0,900}?))"                    # the rest of the chain, bounded (no statement break)
    r"\.(?P<pager>limit|range)\(",
    re.S,
)
ORDER_RE = re.compile(r"\.order\(\s*['\"](?P<col>[a-zA-Z0-9_]+)['\"]")
FROM_RE = re.compile(r"\.from\(\s*['\"](?P<rel>[a-zA-Z0-9_]+)['\"]\s*\)")


def iter_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            if fn.endswith((".html", ".js")) and not fn.endswith(".min.js"):
                yield os.path.join(dirpath, fn)


BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT_RE = re.compile(r"(?m)^[ \t]*//[^\n]*")


def strip_comments(text):
    """Remove comments while PRESERVING line numbers, so reported lines still point at real code.

    This is not cosmetic — it fixed a false positive the gate produced on its own first run. The MR4 fix at
    marketplace.html put a six-line explanatory comment BETWEEN `.order('created_at')` and `.order('id')`,
    which pushed the tiebreaker outside the chain window, so the gate flagged the very query that had just
    been fixed. A gate that reddens on a CORRECT fix teaches the wrong lesson and gets worked around
    ([[feedback_teach_the_gate_not_bend_the_code]]), so the detector reads CODE, not prose. A commented-out
    `.order('id')` correctly stops counting as a tiebreaker too.
    """
    text = BLOCK_COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    return LINE_COMMENT_RE.sub("", text)


def scan_text(text, path):
    """-> (violations, total_chains). A violation is a paginated chain with a non-total order."""
    violations, chains = [], 0
    text = strip_comments(text)
    for m in CHAIN_RE.finditer(text):
        body = m.group("body")
        # An `.order()` must exist for this to be an ORDERING question at all. A paginated query with NO
        # order is a different (also real) defect owned by the unbounded-query gate, not this one.
        cols = ORDER_RE.findall(body)
        if not cols:
            continue
        chains += 1
        if cols[-1] in UNIQUE_COLUMNS:
            continue                                  # total order — deterministic
        line = text.count("\n", 0, m.start()) + 1
        rel = FROM_RE.search(m.group(0))
        violations.append({
            "file": os.path.relpath(path, ROOT).replace("\\", "/"),
            "line": line,
            "relation": rel.group("rel") if rel else "?",
            "order_by": cols,
            "pager": m.group("pager"),
        })
    return violations, chains


def scan_all():
    violations, chains = [], 0
    for path in iter_files():
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            continue
        v, c = scan_text(text, path)
        violations.extend(v)
        chains += c
    violations.sort(key=lambda v: (v["file"], v["line"]))
    return violations, chains


def selftest():
    """Prove the detector has TEETH: a known-bad chain must be caught and a known-good one must not.

    Without this the gate could report zero violations because its regex stopped matching — a detector that
    silently stops detecting is the exact false-green this platform keeps finding
    ([[feedback_an_impossibly_good_result_is_the_defect]]).
    """
    print("  selftest: a non-total paginated order must be CAUGHT, a total one must PASS")
    bad = """
      const { data } = await db.from('marketplace_listings')
        .select('id,title').eq('status','published')
        .order('created_at', { ascending: false })
        .limit(PAGE_SIZE);
    """
    good = """
      const { data } = await db.from('marketplace_listings')
        .select('id,title').eq('status','published')
        .order('created_at', { ascending: false })
        .order('id', { ascending: false })
        .limit(PAGE_SIZE);
    """
    single = """
      const { data } = await db.from('service_requests').select('*')
        .order('created_at', { ascending: false }).limit(1);
    """
    # The real MR4 fix carries a long comment between the two .order() calls. The gate must still see the
    # tiebreaker — it flagged this exact shape as a violation on its first run.
    commented = """
      const { data } = await db.from('v_marketplace_listings_truth')
        .select('id,title,description,section,category,condition,price,location,seller_name')
        .eq('status','published').eq('section', _section)
        .order('created_at', { ascending: false })
        // TIEBREAKER (MR4 rank stability). created_at alone is NOT a total order: a bulk import inserts
        // many listings inside ONE transaction, where now() is fixed, so they share an identical timestamp.
        // Postgres promises nothing about the order of tied rows, and it genuinely changes.
        .order('id', { ascending: false })
        .limit(PAGE_SIZE);
    """
    v_bad, _ = scan_text(bad, "selftest-bad.html")
    v_good, _ = scan_text(good, "selftest-good.html")
    v_single, _ = scan_text(single, "selftest-single.html")
    v_comm, _ = scan_text(commented, "selftest-commented.html")
    ok = True
    if v_comm:
        print(f"  {RED}FAIL{RST} — a tiebreaker separated from its .order() by a COMMENT was missed, so the "
              f"gate reddens on a correct fix.")
        ok = False
    if len(v_bad) != 1:
        print(f"  {RED}FAIL{RST} — the known-BAD chain was not caught ({len(v_bad)} found). The detector is blind.")
        ok = False
    if v_good:
        print(f"  {RED}FAIL{RST} — the known-GOOD chain (id tiebreaker) was flagged. The gate would punish the fix.")
        ok = False
    if len(v_single) != 1:
        print(f"  {RED}FAIL{RST} — `.limit(1)` was not treated as pagination. 'the most recent row' among ties "
              f"is exactly the ambiguity this gate exists to catch.")
        ok = False
    if ok:
        print(f"  {GREEN}PASS{RST} — catches the non-total order, accepts the tiebreaker, and covers limit(1)")
        return 0
    return 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    print(f"{BOLD}Paginated order totality{RST} — does every paged/truncated query sort deterministically?")
    if selftest() != 0:
        print(f"  {RED}FAIL{RST} — the detector failed its own self-test, so its count means nothing.")
        return 1
    violations, chains = scan_all()
    n = len(violations)
    by_file = {}
    for v in violations:
        by_file.setdefault(v["file"], []).append(v)

    if "--verbose" in argv:
        for fn, vs in sorted(by_file.items()):
            print(f"  {DIM}{fn}{RST}")
            for v in vs:
                print(f"    {RED}line {v['line']:<5}{RST} {v['relation']:<34} "
                      f"{DIM}order({', '.join(v['order_by'])}) + {v['pager']}(){RST}")
    else:
        for fn, vs in sorted(by_file.items(), key=lambda kv: -len(kv[1]))[:12]:
            worst = vs[0]
            print(f"  {RED}{len(vs):>3}{RST}  {fn:<44} {DIM}e.g. line {worst['line']}: "
                  f"order({', '.join(worst['order_by'])}){RST}")

    print(f"\n  {n} non-total paginated orders across {len(by_file)} files "
          f"({chains} paginated+ordered chains scanned)")


    base = None
    if os.path.exists(BASELINE):
        try:
            base = json.load(open(BASELINE, encoding="utf-8")).get("violations")
        except Exception:
            base = None

    def write_baseline():
        with open(BASELINE, "w", encoding="utf-8") as f:
            json.dump({"violations": n,
                       "_doc": "FORWARD-ONLY: the count of paginated queries whose ORDER BY is not a total "
                               "order. It may only FALL. Every one is a row that can be shown twice or "
                               "skipped across a page boundary (or, at limit(1), an arbitrary pick among "
                               "ties). The fix is always the same: end the ordering with a unique column, "
                               "normally .order('id')."}, f, indent=2)

    if "--update-baseline" in argv or base is None:
        write_baseline()
        print(f"  {DIM}baseline set to {n}{RST}")
        return 0
    if n > base:
        print(f"  {RED}FAIL{RST} — non-total paginated orders ROSE {base} -> {n}. A new paged query sorts "
              f"ambiguously: end its ordering with a unique column (normally `.order('id')`).")
        return 1
    if n < base:
        write_baseline()
        print(f"  {GREEN}PASS{RST} — ratcheted {base} -> {n}")
        return 0
    print(f"  {GREEN}PASS{RST} — holds at {n} (forward-only)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
