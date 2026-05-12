"""
Seed -> Consumer Contract Validator -- WorkHive Platform
=========================================================
Catches the regression class "seeder writes data that the consumer page
can't actually see / render." Found during the 2026-05-13 walkthrough:

  Case A (timezone-shift): seeders/amc.py used datetime.now(timezone.utc)
    for shift_date but amc_briefings.shift_date has a DEFAULT of
    `timezone('Asia/Manila', now())::date` and the alert-hub page filters
    by todayPhtIso(). Result: when the seed ran at PHT 2026-05-13 (which
    was UTC 2026-05-12), today's brief never landed.

  Case B (jsonb-shape-drift): seeders/amc.py wrote brief.top_assets[].name
    but alert-hub renderAmcCard reads brief.top_assets[].asset_name. The
    AMC card rendered but every row showed "? -- ?" placeholders.

This validator is generic. It scans:

  L1 -- Date columns with non-UTC DEFAULT: any seeder that explicitly sets
        such a column must use the same timezone. The PHT convention is
        `timezone('Asia/Manila', now())`; any seeder writing the column
        with `datetime.now(timezone.utc).date()` or `datetime.utcnow()`
        is flagged.

  L2 -- JSONB column key set: for every JSONB column written by a seeder
        as a structured dict (brief / payload / meta), extract the key set
        written + the key set consumed by HTML pages reading `<col>.<key>`.
        FAIL on consumer-side keys NOT seeded (broken render).
        WARN on seeded keys not consumed (dead-key drift, may be intended).

Usage:  python validate_seed_consumer_contract.py
Output: seed_consumer_contract_report.json
"""
from __future__ import annotations

import os
import re
import json
import sys
import glob
from collections import defaultdict

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


MIGRATIONS_DIR = os.path.join("supabase", "migrations")
SEEDERS_DIR    = os.path.join("test-data-seeder", "seeders")

# Pages that consume the seeded JSONB shapes. We don't scan every HTML
# file (~40 of them) on every JSONB column because L2 is a coarse cross-
# reference; instead we accept a curated map below.
HTML_GLOB = "*.html"


# ── Layer 1: Timezone consistency ─────────────────────────────────────────────
#
# A column has a non-UTC default if its DEFAULT clause invokes
# timezone('<tz>', now()) for any TZ other than 'utc'. PHT is the dominant
# WorkHive convention (timezone('Asia/Manila', now())).

TZ_DEFAULT_RE = re.compile(
    r"(?P<col>\w+)\s+(?:date|timestamp(?:tz)?)\b[^,\n;]*?"
    r"DEFAULT\s+\(?\s*timezone\s*\(\s*'(?P<tz>[^']+)'",
    re.IGNORECASE,
)

# Python seeder-side UTC patterns we want to FLAG when writing one of those cols.
# We focus on the .date() call because that's what produces a `date` value
# the DB would compare against a PHT-defaulted date column.
UTC_PYTHON_PATTERNS = (
    re.compile(r"datetime\.now\s*\(\s*timezone\.utc\s*\)\s*\.date\s*\(\s*\)"),
    re.compile(r"datetime\.utcnow\s*\(\s*\)\s*\.date\s*\(\s*\)"),
)


def find_all_columns_by_table() -> dict[str, set[str]]:
    """Return {table_name: {col_name, ...}} for every CREATE TABLE."""
    by_table: dict[str, set[str]] = defaultdict(set)
    create_re = re.compile(
        r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?
            (?:public\.|"public"\.)?
            "?(?P<name>\w+)"?\s*\(
            (?P<body>[\s\S]*?)\n\s*\);""",
        re.IGNORECASE | re.VERBOSE,
    )
    col_re = re.compile(r"^\s*\"?(?P<col>[a-z_][a-z0-9_]*)\"?\s+(?:date|timestamptz|timestamp|text|uuid|jsonb|numeric|integer|bigint|boolean|smallint|vector)\b", re.IGNORECASE | re.MULTILINE)
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = read_file(path) or ""
        sql_clean = re.sub(r"--[^\n]*", "", sql)
        for m in create_re.finditer(sql_clean):
            table = m.group("name")
            body  = m.group("body")
            for col_m in col_re.finditer(body):
                by_table[table].add(col_m.group("col"))
        # Also pick up ALTER TABLE ADD COLUMN
        for am in re.finditer(
            r"ALTER\s+TABLE\s+(?:ONLY\s+)?(?:public\.|\"public\"\.)?\"?(?P<t>\w+)\"?\s+"
            r"ADD\s+COLUMN(?:\s+IF\s+NOT\s+EXISTS)?\s+\"?(?P<c>\w+)\"?",
            sql_clean, re.IGNORECASE,
        ):
            by_table[am.group("t")].add(am.group("c"))
    return by_table


def find_non_utc_date_columns() -> dict[str, list[dict]]:
    """Return {table_name: [{col, tz, migration}]} for every column whose
    DEFAULT clause uses a non-UTC timezone. Parsed from migrations."""
    by_table: dict[str, list[dict]] = defaultdict(list)
    create_re = re.compile(
        r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?
            (?:public\.|"public"\.)?
            "?(?P<name>\w+)"?\s*\(
            (?P<body>[\s\S]*?)\n\s*\);""",
        re.IGNORECASE | re.VERBOSE,
    )
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = read_file(path) or ""
        # Strip line comments so we don't match DEFAULT inside a comment.
        sql_clean = re.sub(r"--[^\n]*", "", sql)
        for m in create_re.finditer(sql_clean):
            table = m.group("name")
            body  = m.group("body")
            for col_m in TZ_DEFAULT_RE.finditer(body):
                tz = col_m.group("tz")
                if tz.lower() == "utc":
                    continue
                by_table[table].append({
                    "col":       col_m.group("col"),
                    "tz":        tz,
                    "migration": os.path.basename(path),
                })
    return by_table


def check_seeder_timezone(non_utc_cols: dict[str, list[dict]]) -> list[dict]:
    """For each seeder that .insert()s into one of the flagged tables and
    explicitly sets a flagged column, FAIL if the same function body uses
    a UTC date pattern."""
    issues: list[dict] = []
    if not non_utc_cols:
        return issues

    for path in sorted(glob.glob(os.path.join(SEEDERS_DIR, "*.py"))):
        src = read_file(path) or ""
        if not src.strip():
            continue
        # For each seeder, check every table it inserts into and pair with
        # the columns it writes.
        insert_re = re.compile(
            r"""client\.table\s*\(\s*['"](?P<table>\w+)['"]\s*\)
                \s*\.\s*(?:insert|upsert)""",
            re.VERBOSE,
        )
        # Cheaper: scan once for tables referenced in seeder
        tables_seen = set(m.group("table") for m in insert_re.finditer(src))
        # Plus the older batch_insert(client, "<table>", rows) pattern
        for bm in re.finditer(r"batch_insert\s*\(\s*\w+\s*,\s*['\"](?P<table>\w+)['\"]", src):
            tables_seen.add(bm.group("table"))

        for table in tables_seen:
            flagged = non_utc_cols.get(table)
            if not flagged:
                continue
            # Does the seeder write any of those columns by explicit key?
            for col_info in flagged:
                col = col_info["col"]
                key_re = re.compile(rf"['\"]({re.escape(col)})['\"]\s*:")
                if not key_re.search(src):
                    continue
                # The seeder writes col explicitly. Does the seeder use a
                # UTC date pattern anywhere?
                for p in UTC_PYTHON_PATTERNS:
                    for m in p.finditer(src):
                        line_no = src.count("\n", 0, m.start()) + 1
                        issues.append({
                            "check":   "seeder_timezone",
                            "skip":    False,
                            "reason": (
                                f"{os.path.basename(path)}:{line_no} uses {m.group(0).strip()} "
                                f"but writes '{col}' on table '{table}' which has a "
                                f"DEFAULT of timezone('{col_info['tz']}',...). "
                                f"Page-side queries on this column use the DB's TZ, so "
                                f"the seeded row's date will be a day off in the late-UTC "
                                f"hours. Use the table's TZ (e.g. "
                                f"`datetime.now(timezone(timedelta(hours=8))).date()` for PHT)."
                            ),
                        })
                        # one issue per seeder per column is enough
                        break
                    else:
                        continue
                    break
    return issues


# ── Layer 2: JSONB key contract --------------------------------------------------
#
# Curated map of (table, jsonb_col) -> set of HTML pages that render it.
# Keys are kept narrow so the cross-ref is reliable; add a row here when a
# new structured JSONB blob is added.

JSONB_CONTRACTS = [
    # (table, jsonb_col, consumer_pages, alias_in_page)
    # alias_in_page is the JS variable the page binds the JSONB to before
    # reading keys -- e.g. `const b = brief.brief; ... b.top_assets`.
    ("amc_briefings", "brief", ["alert-hub.html"], "b"),
]


def _extract_seeder_jsonb_keys(seeder_src: str, table: str, col: str) -> set[str]:
    """Return the top-level key set written into `col` by inserts on `table`
    inside `seeder_src`. Looks for `<col>` dict-literal assignments and
    helpers that return a dict assigned to <col>.

    Heuristic: scan for `"<col>": { ... }` AND for `return { "<keyname>": ... }`
    in helper functions called from row-builder. We only handle the dict-literal
    inline shape robustly.
    """
    keys: set[str] = set()
    # Pattern 1: inline literal -> "<col>": {<...nested...>}
    # Brace-balance walk.
    cursor = 0
    needle = f'"{col}":'
    while True:
        idx = seeder_src.find(needle, cursor)
        if idx < 0:
            break
        # Find the next '{' after the colon, then walk braces.
        brace_start = seeder_src.find("{", idx)
        if brace_start < 0:
            cursor = idx + len(needle); continue
        depth = 0
        i = brace_start
        while i < len(seeder_src):
            ch = seeder_src[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        snippet = seeder_src[brace_start + 1:i]
        # Top-level keys only: those whose `"<key>":` is at depth 0 in snippet.
        d = 0
        for km in re.finditer(r'"(?P<k>[a-zA-Z_][\w]*)"\s*:', snippet):
            # count braces between start of snippet and km.start()
            prefix = snippet[:km.start()]
            d = prefix.count("{") - prefix.count("}")
            if d == 0:
                keys.add(km.group("k"))
        cursor = i + 1

    # Pattern 2: helper builder returning a dict.
    # Heuristic: find `def _build_*` returning {...} and union top-level keys.
    helper_re = re.compile(
        r"def\s+(_?build_\w+|build_\w+|_build_\w+)\s*\([^)]*\)\s*->\s*dict[^:]*:\s*\n"
        r"([\s\S]*?)(?=\n(?:def|class)\s|\Z)",
    )
    for hm in helper_re.finditer(seeder_src):
        body = hm.group(2)
        # find `return {...}` block (last one wins) with brace-walk.
        ret_idx = body.rfind("return {")
        if ret_idx < 0:
            continue
        brace_start = body.find("{", ret_idx)
        depth = 0
        i = brace_start
        while i < len(body):
            ch = body[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        snippet = body[brace_start + 1:i]
        # Top-level keys
        for km in re.finditer(r'"(?P<k>[a-zA-Z_][\w]*)"\s*:', snippet):
            prefix = snippet[:km.start()]
            if prefix.count("{") - prefix.count("}") == 0:
                keys.add(km.group("k"))

    return keys


def _extract_consumer_keys(html_src: str, alias: str) -> set[str]:
    """Return the set of keys the page reads off `<alias>.<key>` references."""
    keys: set[str] = set()
    # Match alias.key or alias["key"] / alias['key']
    pat = re.compile(
        rf"\b{re.escape(alias)}\s*\.\s*(?P<k>[a-zA-Z_][\w]*)"
        rf"|\b{re.escape(alias)}\s*\[\s*['\"](?P<k2>[a-zA-Z_][\w]*)['\"]\s*\]"
    )
    # Exclude common JS noise keys that are obviously not data fields.
    NOISE = {"length", "map", "filter", "reduce", "forEach", "join", "slice",
             "splice", "push", "pop", "shift", "unshift", "concat", "indexOf",
             "includes", "find", "some", "every", "sort", "reverse", "constructor",
             "prototype", "toString", "valueOf"}
    for m in pat.finditer(html_src):
        k = m.group("k") or m.group("k2")
        if k and k not in NOISE:
            keys.add(k)
    return keys


def check_jsonb_contract() -> list[dict]:
    issues: list[dict] = []
    # Aggregate the union of seeder-written keys for each (table, col)
    seeder_keys: dict[tuple[str, str], set[str]] = defaultdict(set)
    consumer_keys: dict[tuple[str, str], set[str]] = defaultdict(set)

    # Pages often reuse alias names like `b` for both row + JSONB in
    # different scopes. Excluding the table's column names from the consumer
    # key set prevents counting `b.shift_date` (row column) as a missing
    # JSONB key. Also add a few JS-stdlib noise tokens.
    all_cols = find_all_columns_by_table()
    extra_noise = {"time", "id", "msg", "title", "head"}

    for table, col, pages, alias in JSONB_CONTRACTS:
        # Seeder side
        for path in sorted(glob.glob(os.path.join(SEEDERS_DIR, "*.py"))):
            src = read_file(path) or ""
            if not src.strip():
                continue
            # Only consider seeders that mention the table by name
            if f'"{table}"' not in src and f"'{table}'" not in src:
                continue
            seeder_keys[(table, col)] |= _extract_seeder_jsonb_keys(src, table, col)
        # Consumer side
        for page in pages:
            if not os.path.exists(page):
                continue
            html_src = read_file(page) or ""
            consumer_keys[(table, col)] |= _extract_consumer_keys(html_src, alias)

    for (table, col, pages, alias) in [(c[0], c[1], c[2], c[3]) for c in JSONB_CONTRACTS]:
        sk = seeder_keys[(table, col)]
        ck = consumer_keys[(table, col)]
        # Strip table column names + extra noise from the consumer key set —
        # the same alias is often reused for row vs JSONB in different scopes.
        ck = ck - all_cols.get(table, set()) - extra_noise
        # Consumer-only (FAIL): page reads keys the seeder never writes
        missing = ck - sk
        # Seeder-only (WARN): keys written that no consumer reads
        dead    = sk - ck
        # Heuristic noise filter: consumer code reads many local-variable
        # properties under the same alias. We narrow to keys ALSO mentioned
        # as JSON keys in the seeder side or as JSONB col names anywhere.
        # In practice this still produces too many WARNs without a curated
        # known-shape list. We report only the FAILs (missing-on-seeder).
        if missing:
            issues.append({
                "check":   "jsonb_contract",
                "skip":    False,
                "reason": (
                    f"Consumer page(s) {pages} read keys from {table}.{col} "
                    f"that no seeder writes: "
                    f"{sorted(missing)[:8]}{'...' if len(missing) > 8 else ''}. "
                    f"Either update the seeder to write these keys "
                    f"(use the production output schema from the producing "
                    f"edge function), or accept the render-side fallback as "
                    f"the expected empty state."
                ),
            })
    return issues


# ── Runner -----------------------------------------------------------------------

CHECK_NAMES = ["seeder_timezone", "jsonb_contract"]
CHECK_LABELS = {
    "seeder_timezone": "L1  Seeders writing non-UTC date columns use matching TZ",
    "jsonb_contract":  "L2  Consumer pages can read every key the seeder writes for known JSONB blobs",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nSeed -> Consumer Contract Validator (2-layer)"))
    print("=" * 60)

    non_utc_cols = find_non_utc_date_columns()
    print(f"  {sum(len(v) for v in non_utc_cols.values())} non-UTC date column(s) discovered across "
          f"{len(non_utc_cols)} table(s).\n")

    issues = []
    issues += check_seeder_timezone(non_utc_cols)
    issues += check_jsonb_contract()

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)

    with open("seed_consumer_contract_report.json", "w", encoding="utf-8") as f:
        json.dump({
            "validator":       "seed_consumer_contract",
            "non_utc_columns": non_utc_cols,
            "issues":          [i for i in issues if not i.get("skip")],
            "passed":          n_pass,
            "warned":          n_warn,
            "failed":          n_fail,
        }, f, indent=2, default=str)

    if n_fail == 0 and n_warn == 0:
        print(f"\n  \033[92mAll {len(CHECK_NAMES)} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\n  \033[93m{n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\n  \033[91m{n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
