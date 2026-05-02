"""
Soft-Delete Read-Path Discipline Validator — WorkHive Platform
===============================================================
For every table that's been soft-delete-enabled (an UPDATE somewhere sets
`deleted_at`), assert that every SELECT against that table chains
`.is('deleted_at', null)` so deleted rows never leak into the UI.

Root cause this catches:
  Adding a `deleted_at` column to a table is the easy part. The
  discipline is updating EVERY SELECT call site. For the May 2026
  community page soft-delete that meant 6 sites in community.html alone
  (hive feed, pinned, global feed, more-global, deep-link fallback,
  realtime helper). Missing one means deleted rows leak into mod queues,
  profile counters, deep-links, or cross-hive views.

Approach:
  1. Walk every HTML file. For each, find tables where any UPDATE call
     sets `deleted_at` — these are the soft-delete-enabled tables.
  2. For each such table, find every `.from('<table>').select(...)` call.
  3. Within ~600 chars of each SELECT, assert `.is('deleted_at', null)`
     appears in the query chain. If not, FAIL with the call site.

  Layer 1 — Read-path coverage
    1.  Every SELECT on a soft-delete table includes .is('deleted_at', null)  [FAIL]

Usage:  python validate_soft_delete.py
Output: soft_delete_report.json
"""
import re, json, sys, os, glob

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import format_result

CHECKS = {
    "select_filters_deleted":  "L1  Every SELECT on a soft-delete table chains .is('deleted_at', null)",
}
CHECK_LABELS = CHECKS
CHECK_NAMES  = list(CHECKS.keys())

# Detect tables that have soft-delete enabled by spotting an UPDATE that sets
# deleted_at (either to a timestamp or back to null for restore).
SOFT_DELETE_UPDATE_RE = re.compile(
    r"\.from\(\s*['\"]([a-zA-Z_][a-zA-Z0-9_]*)['\"]\s*\)"
    r"\s*\.update\(\s*\{[^}]*deleted_at",
    re.DOTALL
)

# A SELECT on a particular table — captures the whole .from(...).select(...) chain
# up to ~700 chars so the chained .is/.eq/.lt calls fall inside the window.
def select_block_re(table):
    return re.compile(
        r"\.from\(\s*['\"]" + re.escape(table) + r"['\"]\s*\)\s*\.select\([^)]*\)([^;]{0,700})",
        re.DOTALL
    )


def find_soft_delete_tables(content):
    """Return the set of table names this file marks as soft-delete-enabled."""
    return set(SOFT_DELETE_UPDATE_RE.findall(content))


def check_select_filters_deleted(file_path, content, tables):
    issues = []
    for table in sorted(tables):
        for m in select_block_re(table).finditer(content):
            chain = m.group(0)
            # `count: 'exact', head: true` calls are aggregate counts and may
            # also need filtering — but only flag if the chain doesn't filter.
            # The same rule applies: count of "active" rows should exclude deleted.
            if ".is('deleted_at', null)" in chain or '.is("deleted_at", null)' in chain:
                continue
            line = content[:m.start()].count("\n") + 1
            issues.append({
                "check": "select_filters_deleted",
                "reason": (
                    f"{file_path}:{line} SELECT on soft-delete table '{table}' "
                    f"is missing .is('deleted_at', null). Add the filter or this "
                    f"query will leak deleted rows into the UI."
                )
            })
    return issues


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nSoft-Delete Read-Path Validator (1-layer)"))
    print("=" * 55)

    all_issues = []
    soft_delete_table_count = 0
    inspected_files = 0

    for path in sorted(glob.glob("*.html")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            continue
        tables = find_soft_delete_tables(content)
        if not tables:
            continue
        inspected_files += 1
        soft_delete_table_count += len(tables)
        all_issues += check_select_filters_deleted(path, content, tables)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)
    total = len(CHECK_NAMES)

    if n_fail == 0:
        print(f"\033[92m\n  All {total} checks passed. ({inspected_files} files, {soft_delete_table_count} soft-delete tables)\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")

    report = {
        "validator":              "soft_delete",
        "soft_delete_files":      inspected_files,
        "soft_delete_tables":     soft_delete_table_count,
        "total_checks":           total,
        "passed":                 n_pass,
        "skipped":                n_skip,
        "failed":                 n_fail,
        "issues":                 [i for i in all_issues if not i.get("skip")],
    }
    with open("soft_delete_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
