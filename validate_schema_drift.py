"""
Schema Drift Validator — WorkHive Platform
============================================
Catches HTML→DB column drift: code references a column that doesn't exist
in the Supabase schema (because the corresponding ALTER TABLE migration
was never run, or rolled back).

Root cause this catches (May 2026):
  community.html SELECTs included a `mentions` column. The validator
  enforced internal consistency — every SELECT used the same column list
  — but no validator confirmed `mentions` actually existed in Supabase.
  The user thought they ran the ALTER, but the migration didn't land.
  Result: SELECT returns 400 in production. Caught only by user opening
  the page and watching DevTools.

Approach:
  Maintain a hand-curated EXPECTED_SCHEMA dict per table. For every
  `.from('X').select('a, b, c')` in HTML, parse the column list and FAIL
  if any column isn't in EXPECTED_SCHEMA['X']. Only tables explicitly in
  the dict are checked — unknown tables are skipped so the validator
  starts narrow and grows over time as features are validated.

  Layer 1 — Column existence
    1.  Every column referenced in HTML SELECT exists in EXPECTED_SCHEMA  [FAIL]

After every ALTER TABLE migration:
  1. Run the diagnostic: SELECT column_name FROM information_schema.columns
     WHERE table_name = 'X';
  2. Confirm the new column appears in the result.
  3. Add it to EXPECTED_SCHEMA[X] below.
  4. Re-run this validator — should return to PASS.

Usage:  python validate_schema_drift.py
Output: schema_drift_report.json
"""
import re, json, sys, os, glob

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import format_result

# Hand-curated source of truth for what columns code is allowed to reference.
# Every entry should reflect a column CONFIRMED in Supabase via:
#   SELECT column_name FROM information_schema.columns WHERE table_name = '<X>';
#
# After every ALTER TABLE migration, run that diagnostic, confirm the new
# column shows, then add it here. Tables NOT in this dict are skipped (no
# enforcement) — that's intentional; the validator grows incrementally as
# you confirm each table's schema.
EXPECTED_SCHEMA = {
    # Confirmed via diagnostic SQL on 2026-05-02
    "community_posts": {
        "id", "hive_id", "author_name", "content", "category",
        "pinned", "flagged", "public",
        "created_at", "edited_at", "deleted_at",
        "mentions", "auth_uid",
    },
    "community_replies": {
        "id", "post_id", "hive_id", "author_name", "content", "created_at",
    },
    "community_reactions": {
        "post_id", "hive_id", "worker_name", "emoji",
    },
    "community_xp": {
        "worker_name", "hive_id", "xp_total",
    },
}

CHECKS = {
    "columns_exist_in_schema": "L1  Every column in HTML SELECT exists in EXPECTED_SCHEMA",
}
CHECK_LABELS = CHECKS
CHECK_NAMES  = list(CHECKS.keys())

# Test/dev/backup HTML files to exclude
EXCLUDED_FILE_PATTERNS = ("-test.html", ".backup.html", ".backup", "_backup.html")

# Match: db.from('TABLE').select('COLS') chains.
SELECT_RE = re.compile(
    r"\.from\(\s*['\"]([a-zA-Z_][a-zA-Z0-9_]*)['\"]\s*\)\s*\.select\(\s*['\"]([^'\"]+)['\"]",
    re.DOTALL
)


def _is_excluded(path):
    name = os.path.basename(path).lower()
    return any(pat in name for pat in EXCLUDED_FILE_PATTERNS)


def parse_columns(cols_str):
    """Split a Supabase select string on top-level commas, ignoring commas inside
    parens (which are joined-table column lists like 'hives(name)').
    Returns the list of column tokens at the top level only."""
    out = []
    depth = 0
    buf = []
    for ch in cols_str:
        if ch == "(":
            depth += 1
            buf.append(ch)
        elif ch == ")":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            out.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        out.append("".join(buf).strip())
    return [c for c in out if c]


def column_name_only(token):
    """Strip aliases and join syntax. 'hives(name)' -> 'hives' (treat as nested
    table reference, skip). 'col_name' -> 'col_name'. '*' -> '*'."""
    token = token.strip()
    if "(" in token:
        return None  # nested join — skip
    if "::" in token:
        token = token.split("::", 1)[0]
    return token


def check_columns_exist(file_path, content):
    issues = []
    for m in SELECT_RE.finditer(content):
        table = m.group(1)
        if table not in EXPECTED_SCHEMA:
            continue  # unknown table — skip enforcement
        cols_str = m.group(2)
        line = content[:m.start()].count("\n") + 1
        for token in parse_columns(cols_str):
            col = column_name_only(token)
            if col is None or col == "*":
                continue
            if col not in EXPECTED_SCHEMA[table]:
                issues.append({
                    "check": "columns_exist_in_schema",
                    "reason": (
                        f"{file_path}:{line} SELECT on '{table}' references column "
                        f"'{col}' which is NOT in EXPECTED_SCHEMA. Either: "
                        f"(a) run ALTER TABLE {table} ADD COLUMN {col} ... in Supabase, "
                        f"confirm with `SELECT column_name FROM information_schema.columns "
                        f"WHERE table_name='{table}';`, then add '{col}' to EXPECTED_SCHEMA, "
                        f"or (b) remove the column from this SELECT."
                    )
                })
    return issues


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nSchema Drift Validator (1-layer)"))
    print("=" * 55)

    all_issues = []
    files_checked = 0
    selects_checked = 0

    for path in sorted(glob.glob("*.html")):
        if _is_excluded(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            continue
        files_checked += 1
        page_issues = check_columns_exist(path, content)
        all_issues += page_issues
        selects_checked += sum(
            1 for m in SELECT_RE.finditer(content)
            if m.group(1) in EXPECTED_SCHEMA
        )

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)
    total = len(CHECK_NAMES)

    if n_fail == 0:
        print(f"\033[92m\n  All {total} checks passed. ({files_checked} files, {selects_checked} guarded SELECTs against {len(EXPECTED_SCHEMA)} known tables)\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
        print(f"\n  Tip: confirm any new column exists with:")
        print(f"    SELECT column_name FROM information_schema.columns WHERE table_name = '<table>';")

    report = {
        "validator":         "schema_drift",
        "tables_guarded":    sorted(EXPECTED_SCHEMA.keys()),
        "files_checked":     files_checked,
        "selects_checked":   selects_checked,
        "total_checks":      total,
        "passed":            n_pass,
        "skipped":           n_skip,
        "failed":            n_fail,
        "issues":            [i for i in all_issues if not i.get("skip")],
    }
    with open("schema_drift_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
