"""
Optimistic Concurrency Detector -- WorkHive Platform
=====================================================
Catches the silent-overwrite bug class. Two workers open the same logbook
entry at 14:00. Worker A edits the notes field and saves at 14:02.
Worker B (still on the 14:00 read) edits the same notes and saves at
14:03. B's save overwrites A's, no error, no warning. A's change is gone.

The defence is OPTIMISTIC CONCURRENCY: include the row's `updated_at` (or
a `version` counter) in the UPDATE filter chain. If the row was modified
between read and write, the filter doesn't match, no rows are updated,
and the writer can show "row was modified by someone else, refresh".

Layer 1 -- Content updates without guard                                [WARN]
  `.update({...})` calls that set "concurrent-content" keys (notes,
  action, problem, body, comments, item_text) and only filter on `id` --
  no `updated_at` / `version` / `if-match` guard.

Layer 2 -- Race-prone tables without defence available                  [WARN]
  Tables that get UPDATEd by 3+ distinct writer files but have NO
  `updated_at` column in their schema. Without the column, optimistic
  concurrency cannot even be implemented -- the migration needs to add
  it before the application code can defend.

Layer 3 -- Writer concentration matrix (informational)                  [INFO]
  Per-table count of UI writer files. High counts on content tables are
  a leading indicator of race risk.

Layer 4 -- Defensive pattern adoption (informational)                   [INFO]
  Count of `.eq('updated_at', ...)` / `.eq('version', ...)` /
  `.match({updated_at: ...})` patterns platform-wide. Should grow over
  time as tables migrate to OC.

Skills consulted: data-engineer (silent overwrites are a class of
schema/query alignment bug), architect (multi-writer coordination,
read-then-update patterns), realtime-engineer (concurrent edits over
realtime channels need OC at the persistence layer too).
"""
from __future__ import annotations

import re
import json
import sys
import os
import glob
from collections import defaultdict

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


MIGRATIONS_DIR = os.path.join("supabase", "migrations")
FUNCTIONS_DIR  = os.path.join("supabase", "functions")
PYTHON_API_DIR = "python-api"

EXCLUDED_HTML_PATTERNS = ("-test.html", ".backup.html", "_backup.html", ".backup")

# Body keys that, when present in an UPDATE, indicate "user-authored
# content" -- the kind of edit where silent overwrite destroys work.
CONTENT_KEYS = {
    "notes", "note", "action", "problem", "comment", "comments", "body",
    "content", "description", "remark", "remarks", "message", "summary",
    "item_text", "display_name", "ph_signature", "shift_handover",
    "qty_on_hand",   # inventory counts -- two workers stocking races silently
}

# Tables where overwrite IS the intended semantic (status flips, audit
# stamping, queue advance). Each entry needs a one-line justification.
OVERWRITE_OK_TABLES = {
    "ai_rate_limits":              "rate-limit counters; latest count IS the truth",
    "automation_log":              "audit stamp; field updates from cron",
    "asset_risk_scores":           "scoring is service-role-only and idempotent",
    "weibull_fits":                "stats history; INSERT-only emit",
    "ph_intelligence_reports":     "snapshot append-only",
    "hive_benchmarks":             "snapshot stamping",
    "network_benchmarks":          "snapshot stamping",
    "achievement_definitions":     "platform catalog; admin-only edits",
    "equipment_reading_templates": "platform catalog; admin-only edits",
    "canonical_sources":           "service-role-only registry",
    "schedule_items":              "internal scheduler config",
    "early_access_emails":         "lead capture; latest email overwrites old",
}

# Tables where OC is genuinely needed but not yet wired -- ratchet target.
# Each entry pins the existing state so the gate runs green; remove the
# entry when the writer file adopts the .eq('updated_at',...) guard.
OC_GUARD_DEFERRED = {
    # 2026-05-11 slimmed: 30 of the original 34 entries were single-writer
    # / append-only / auto-incremented patterns where OC adds no value
    # (the original allowlist was proactive, not based on real validator
    # findings). Closes PRODUCTION_FIXES #43 for those tables.
    #
    # The 3 remaining entries are genuinely contended; pages have
    # adopted `oc-helper.js` (inventory.html + marketplace.html) which
    # the validator now recognises as adoption-in-progress.
    # logbook gets `updated_at` via 20260511000008_logbook_updated_at.sql.
    "logbook":              "DEFERRED -- updated_at column landed; pages use oc-helper.js incrementally",
    "inventory_items":      "DEFERRED -- inventory.html includes oc-helper.js; updateWithOC adopted per save flow",
    "marketplace_listings": "DEFERRED -- marketplace.html includes oc-helper.js; listing edits use updateWithOC",
}


# -- Schema discovery ---------------------------------------------------------

CREATE_TABLE_RE = re.compile(
    r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?
        (?:public\.|"public"\.)?
        "?(?P<name>\w+)"?\s*\(
        (?P<body>[\s\S]*?)\n\s*\);""",
    re.IGNORECASE | re.VERBOSE,
)
ALTER_ADD_RE = re.compile(
    r"""ALTER\s+TABLE\s+(?:public\.|"public"\.|IF\s+EXISTS\s+)?
        "?(?P<name>\w+)"?\s+ADD\s+COLUMN(?:\s+IF\s+NOT\s+EXISTS)?\s+
        "?(?P<col>\w+)"?""",
    re.IGNORECASE | re.VERBOSE,
)
COLUMN_LINE_RE = re.compile(r"""^\s*"?(?P<col>\w+)"?\s+["a-zA-Z]""", re.MULTILINE)


def load_table_columns() -> dict[str, set[str]]:
    cols: dict[str, set[str]] = defaultdict(set)
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = re.sub(r"--[^\n]*", "", read_file(path) or "")
        for m in CREATE_TABLE_RE.finditer(sql):
            name = m.group("name").lower()
            for cm in COLUMN_LINE_RE.finditer(m.group("body")):
                col = cm.group("col").lower()
                if col not in {"constraint", "primary", "unique", "foreign", "check"}:
                    cols[name].add(col)
        for m in ALTER_ADD_RE.finditer(sql):
            cols[m.group("name").lower()].add(m.group("col").lower())
    return dict(cols)


# -- Update-call discovery ----------------------------------------------------

# Match `db.from('TABLE').update({...}).eq('col', ...)` in JS/TS/HTML.
UPDATE_CALL_RE = re.compile(
    r"""\.from\s*\(\s*['"`](?P<table>[a-z_][a-z0-9_]*)['"`]\s*\)
        \s*\.\s*update\s*\(\s*\{(?P<body>[^}]*)\}
        (?P<chain>(?:\s*\.\s*\w+\s*\([^)]*\))*)""",
    re.IGNORECASE | re.VERBOSE,
)
EQ_FILTER_RE = re.compile(r"""\.eq\s*\(\s*['"`](\w+)['"`]""")
MATCH_FILTER_RE = re.compile(r"""\.match\s*\(\s*\{([^}]*)\}""")


def list_consumer_files() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for path in sorted(glob.glob("*.html")):
        if any(p in path.lower() for p in EXCLUDED_HTML_PATTERNS):
            continue
        out.append((path, "html"))
    for path in sorted(glob.glob("*.js")):
        if path.endswith(".min.js"):
            continue
        out.append((path, "shared_js"))
    if os.path.isdir(FUNCTIONS_DIR):
        for d in sorted(os.listdir(FUNCTIONS_DIR)):
            idx = os.path.join(FUNCTIONS_DIR, d, "index.ts")
            if os.path.isfile(idx):
                out.append((idx, "edge"))
    return out


def find_updates(consumer_files: list[tuple[str, str]]) -> list[dict]:
    updates: list[dict] = []
    for path, layer in consumer_files:
        src = read_file(path) or ""
        for m in UPDATE_CALL_RE.finditer(src):
            table = m.group("table").lower()
            body  = m.group("body")
            chain = m.group("chain")
            # Extract body keys (left of the first ':' before each comma).
            keys: set[str] = set()
            depth = 0
            field_buf = ""
            collecting_key = True
            for ch in body:
                if ch in "([{":
                    depth += 1
                    field_buf += ch
                elif ch in ")]}":
                    depth -= 1
                    field_buf += ch
                elif ch == "," and depth == 0:
                    field_buf = ""
                    collecting_key = True
                elif ch == ":" and depth == 0 and collecting_key:
                    key = field_buf.strip().strip("'\"`")
                    if re.match(r"^\w+$", key):
                        keys.add(key.lower())
                    collecting_key = False
                else:
                    if collecting_key:
                        field_buf += ch
            # Extract filter chain columns.
            filter_cols: set[str] = set()
            for em in EQ_FILTER_RE.finditer(chain):
                filter_cols.add(em.group(1).lower())
            for mm in MATCH_FILTER_RE.finditer(chain):
                for piece in mm.group(1).split(","):
                    if ":" in piece:
                        col = piece.split(":", 1)[0].strip().strip("'\"`").lower()
                        if col:
                            filter_cols.add(col)
            updates.append({
                "path":        path,
                "layer":       layer,
                "table":       table,
                "body_keys":   keys,
                "filter_cols": filter_cols,
                "has_oc_guard": bool(filter_cols & {"updated_at", "version", "if_match"}),
            })
    return updates


# -- Layer 1: Content updates without guard ----------------------------------

def check_content_without_guard(updates: list[dict]) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    # Pages that include oc-helper.js have the OC pattern available; treat
    # their content-key updates as adoption-in-progress.
    OC_HELPER_PAGES: set[str] = set()
    for p in {u["path"] for u in updates}:
        src = read_file(p) or ""
        if 'src="oc-helper.js"' in src or "updateWithOC(" in src:
            OC_HELPER_PAGES.add(p)
    for u in updates:
        if u["table"] in OVERWRITE_OK_TABLES:
            continue
        if u["table"] in OC_GUARD_DEFERRED:
            continue
        if u["path"] in OC_HELPER_PAGES:
            continue
        content_keys = u["body_keys"] & CONTENT_KEYS
        if not content_keys:
            continue
        if u["has_oc_guard"]:
            continue
        report.append({
            "path":         u["path"],
            "table":        u["table"],
            "content_keys": sorted(content_keys),
            "filter_cols":  sorted(u["filter_cols"]),
        })
        issues.append({
            "check": "content_without_guard", "skip": True,
            "reason": (
                f"{u['path']}: .from('{u['table']}').update({{ {sorted(content_keys)} }}) "
                f"writes content keys but filter chain only matches "
                f"{sorted(u['filter_cols'])} -- no `updated_at` / `version` "
                f"guard. Two concurrent edits silently overwrite. Add to "
                f"OVERWRITE_OK_TABLES if intentional, or OC_GUARD_DEFERRED "
                f"if it's tracked debt; otherwise add an `.eq('updated_at', "
                f"oldStamp)` guard."
            ),
        })
    return issues, report


# -- Layer 2: Race-prone tables without defence available --------------------

def check_no_defence_available(
    updates: list[dict],
    table_cols: dict[str, set[str]],
) -> tuple[list[dict], list[dict]]:
    """Tables with 3+ distinct writer files where the schema doesn't even
    have an `updated_at` column. Without the column, OC cannot be wired."""
    writers_per_table: dict[str, set[str]] = defaultdict(set)
    for u in updates:
        writers_per_table[u["table"]].add(u["path"])
    issues: list[dict] = []
    report: list[dict] = []
    for table, writers in writers_per_table.items():
        if len(writers) < 3:
            continue
        if table in OVERWRITE_OK_TABLES:
            continue
        # OC_GUARD_DEFERRED already documents the table's OC debt; the
        # missing schema column is part of that same migration item.
        if table in OC_GUARD_DEFERRED:
            continue
        cols = table_cols.get(table, set())
        if "updated_at" in cols or "version" in cols:
            continue
        report.append({
            "table":     table,
            "n_writers": len(writers),
            "writers":   sorted(writers)[:5],
        })
        issues.append({
            "check": "no_defence_available", "skip": True,
            "reason": (
                f"Table '{table}' has UPDATEs in {len(writers)} writer files "
                f"but the schema lacks `updated_at` / `version`. Add a "
                f"timestamp column via migration before any writer can "
                f"adopt optimistic concurrency."
            ),
        })
    return issues, report


# -- Layer 3: Writer concentration matrix (informational) --------------------

def check_writer_matrix(updates: list[dict]) -> tuple[list[dict], list[dict]]:
    counter: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for u in updates:
        counter[u["table"]][u["layer"]] += 1
    rows: list[dict] = []
    for table, layers in counter.items():
        rows.append({
            "table":  table,
            "total":  sum(layers.values()),
            "layers": dict(layers),
        })
    rows.sort(key=lambda r: -r["total"])
    return [], rows


# -- Layer 4: Defensive pattern adoption (informational) --------------------

def check_oc_adoption(updates: list[dict]) -> tuple[list[dict], list[dict]]:
    n_total   = len(updates)
    n_guarded = sum(1 for u in updates if u["has_oc_guard"])
    return [], [{"total_updates": n_total, "guarded": n_guarded}]


# -- Runner ------------------------------------------------------------------

CHECK_NAMES = [
    "content_without_guard",
    "no_defence_available",
    "writer_matrix",
    "oc_adoption",
]
CHECK_LABELS = {
    "content_without_guard": "L1  Content UPDATEs include OC guard (or are allowlisted)         [WARN]",
    "no_defence_available":  "L2  Race-prone tables (3+ writers) have updated_at column         [WARN]",
    "writer_matrix":         "L3  Writer concentration matrix per table (informational)         [INFO]",
    "oc_adoption":           "L4  Optimistic-concurrency adoption count (informational)         [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nOptimistic Concurrency Detector (4-layer)"))
    print("=" * 60)

    table_cols     = load_table_columns()
    consumer_files = list_consumer_files()
    updates        = find_updates(consumer_files)
    print(f"  {len(updates)} UPDATE call(s) across "
          f"{len({u['path'] for u in updates})} writer file(s).\n")

    l1_issues, l1_report = check_content_without_guard(updates)
    l2_issues, l2_report = check_no_defence_available(updates, table_cols)
    l3_issues, l3_report = check_writer_matrix(updates)
    l4_issues, l4_report = check_oc_adoption(updates)

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l3_report:
        print(f"\n{bold('UPDATE WRITER CONCENTRATION (informational)')}")
        print("  " + "-" * 56)
        for r in l3_report[:10]:
            layers = ", ".join(f"{k}={v}" for k, v in r["layers"].items())
            print(f"  {r['table']:<32}  total={r['total']:<3}  ({layers})")

    if l4_report:
        adoption = l4_report[0]
        pct = (adoption["guarded"] / adoption["total_updates"] * 100
               if adoption["total_updates"] else 0)
        print(f"\n{bold('OPTIMISTIC CONCURRENCY ADOPTION')}")
        print("  " + "-" * 56)
        print(f"  {adoption['guarded']} of {adoption['total_updates']} UPDATEs "
              f"use a guard ({pct:.1f}%)")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":             "optimistic_concurrency",
        "total_checks":          total,
        "passed":                n_pass,
        "warned":                n_warn,
        "failed":                n_fail,
        "n_updates":             len(updates),
        "content_without_guard": l1_report,
        "no_defence_available":  l2_report,
        "writer_matrix":         l3_report,
        "oc_adoption":           l4_report,
        "issues":                [i for i in all_issues if not i.get("skip")],
        "warnings":              [i for i in all_issues if i.get("skip")],
    }
    with open("optimistic_concurrency_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
