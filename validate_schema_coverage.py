"""
Schema Coverage Validator — WorkHive Platform
==============================================
Auto-derives the database schema from supabase/migrations/ and checks
that every db.from('TABLE').select('a, b, c') in HTML/JS code references
real tables and columns.

Complementary to validate_schema_drift.py (which uses a hand-curated
EXPECTED_SCHEMA for 4 community tables, deep enforcement). This
validator covers all tables but with a more conservative match: only
plain identifier columns are checked, embeds/aliases/aggregates are
skipped to avoid false positives.

Two layers:

  Layer 1 — Table existence
    Every db.from('TABLE') reference must resolve to a table in
    migrations or be a known Supabase built-in (auth.users, etc).

  Layer 2 — Column existence in simple SELECTs
    For each db.from('TABLE').select('a, b, c'), every plain-name
    column must exist on TABLE per the latest migration state. Embeds,
    aliases, '*', and aggregates are skipped.

Recent bugs this would have caught:
  - assistant.html SELECTed skill_badges.badge_type (column was badge_key)
  - skill_badges.badge_key insert before the column existed in any
    migration

Usage:  python validate_schema_coverage.py
Output: schema_coverage_report.json
"""
import os
import re
import sys
import json
import glob

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))
MIGRATIONS_DIR = os.path.join(ROOT, "supabase", "migrations")

SCAN_GLOBS = [
    os.path.join(ROOT, "*.html"),
    os.path.join(ROOT, "*.js"),
    # Edge functions: db.from() patterns appear here too. Without scanning
    # these, schema drift in supabase/functions/<name>/index.ts goes
    # undetected (caught by user 2026-05-03 in analytics-orchestrator —
    # PRODUCTION_FIXES #16/17).
    os.path.join(ROOT, "supabase", "functions", "*", "index.ts"),
    os.path.join(ROOT, "supabase", "functions", "_shared", "*.ts"),
]

# Test/dev/backup file patterns to skip
EXCLUDED_FILE_PATTERNS = ("-test.html", ".backup.html", ".backup2.html", "_backup.html")

# Supabase built-ins not defined in our migrations
KNOWN_BUILTIN_TABLES = {
    "auth.users", "auth.identities",
    "storage.objects", "storage.buckets",
}

# Tokens that appear in select() strings but are not column names
IMPLICIT_COLUMNS = {"count", "*", "head"}


# ── Migration parser ──────────────────────────────────────────────────────────

RE_CREATE_TABLE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r'(?:"?(\w+)"?\.)?"?(\w+)"?\s*\((.*?)\)\s*(?:WITH\s|TABLESPACE\s|;|$)',
    re.IGNORECASE | re.DOTALL,
)
RE_ALTER_ADD_COLUMN = re.compile(
    r"ALTER\s+TABLE\s+(?:ONLY\s+)?(?:IF\s+EXISTS\s+)?"
    r'(?:"?(\w+)"?\.)?"?(\w+)"?\s+ADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?"?(\w+)"?',
    re.IGNORECASE,
)
RE_ALTER_RENAME_COLUMN = re.compile(
    r"ALTER\s+TABLE\s+(?:ONLY\s+)?(?:IF\s+EXISTS\s+)?"
    r'(?:"?(\w+)"?\.)?"?(\w+)"?\s+RENAME\s+COLUMN\s+"?(\w+)"?\s+TO\s+"?(\w+)"?',
    re.IGNORECASE,
)
RE_ALTER_DROP_COLUMN = re.compile(
    r"ALTER\s+TABLE\s+(?:ONLY\s+)?(?:IF\s+EXISTS\s+)?"
    r'(?:"?(\w+)"?\.)?"?(\w+)"?\s+DROP\s+COLUMN\s+(?:IF\s+EXISTS\s+)?"?(\w+)"?',
    re.IGNORECASE,
)


def _strip_sql_comments(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", "", sql)
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    return sql


def _parse_columns_from_create(body: str) -> set:
    """Extract column names from a CREATE TABLE body. Skips constraints."""
    columns = set()
    depth = 0
    parts = []
    buf = []
    for ch in body:
        if ch == "(":
            depth += 1
            buf.append(ch)
        elif ch == ")":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf).strip())

    for part in parts:
        if not part:
            continue
        first = part.split()[0].upper()
        if first in {"CONSTRAINT", "PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "EXCLUDE", "LIKE"}:
            continue
        m = re.match(r'\s*"?([a-zA-Z_]\w*)"?', part)
        if m:
            columns.add(m.group(1))
    return columns


def build_schema() -> dict:
    """Walk migrations chronologically. Return {table: set(columns)}."""
    schema = {}
    if not os.path.isdir(MIGRATIONS_DIR):
        return schema
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        try:
            with open(path, "r", encoding="utf-8") as f:
                sql = _strip_sql_comments(f.read())
        except Exception:
            continue

        for m in RE_CREATE_TABLE.finditer(sql):
            schema_name = (m.group(1) or "public").lower()
            if schema_name not in {"public", ""}:
                continue
            table = m.group(2)
            schema.setdefault(table, set()).update(_parse_columns_from_create(m.group(3)))

        for m in RE_ALTER_ADD_COLUMN.finditer(sql):
            schema.setdefault(m.group(2), set()).add(m.group(3))

        for m in RE_ALTER_RENAME_COLUMN.finditer(sql):
            cols = schema.setdefault(m.group(2), set())
            cols.discard(m.group(3))
            cols.add(m.group(4))

        for m in RE_ALTER_DROP_COLUMN.finditer(sql):
            cols = schema.get(m.group(2))
            if cols:
                cols.discard(m.group(3))

    return schema


# ── Code scanner ──────────────────────────────────────────────────────────────

RE_FROM_SELECT = re.compile(
    r"(?:[\w$]+)\.from\(\s*['\"]([\w.]+)['\"]\s*\)"
    r"\s*\.select\(\s*['\"]([^'\"]*)['\"]",
    re.IGNORECASE | re.DOTALL,
)
RE_FROM_ANY = re.compile(
    r"(?:[\w$]+)\.from\(\s*['\"]([\w.]+)['\"]\s*\)",
    re.IGNORECASE,
)


def _is_excluded(path: str) -> bool:
    name = os.path.basename(path).lower()
    return any(pat in name for pat in EXCLUDED_FILE_PATTERNS)


def _extract_simple_columns(select_str: str) -> list:
    """Plain identifier columns only. Skip embeds, aliases, aggregates, *."""
    plain = []
    for raw in select_str.split(","):
        token = raw.strip()
        if not token or token == "*":
            continue
        if "(" in token or ")" in token or ":" in token:
            continue
        if token in IMPLICIT_COLUMNS:
            continue
        if not re.match(r"^[a-zA-Z_]\w*$", token):
            continue
        plain.append(token)
    return plain


def _line_at(text: str, idx: int) -> int:
    return text[:idx].count("\n") + 1


def scan_code() -> list:
    findings = []
    for pat in SCAN_GLOBS:
        for path in glob.glob(pat):
            if _is_excluded(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
            except Exception:
                continue
            seen_offsets = set()
            for m in RE_FROM_SELECT.finditer(text):
                seen_offsets.add(m.start())
                findings.append({
                    "file":   os.path.basename(path),
                    "line":   _line_at(text, m.start()),
                    "table":  m.group(1),
                    "columns": _extract_simple_columns(m.group(2)),
                    "_from_only": False,
                })
            for m in RE_FROM_ANY.finditer(text):
                if m.start() in seen_offsets:
                    continue
                findings.append({
                    "file":   os.path.basename(path),
                    "line":   _line_at(text, m.start()),
                    "table":  m.group(1),
                    "columns": [],
                    "_from_only": True,
                })
    return findings


# ── Checks ────────────────────────────────────────────────────────────────────

def check_table_existence(schema: dict, findings: list) -> dict:
    unknown = {}
    for f in findings:
        table = f["table"]
        if table in schema or table in KNOWN_BUILTIN_TABLES:
            continue
        if "." in table:
            # Schema-prefixed and not a known built-in: skip (out of scope)
            continue
        unknown.setdefault(table, []).append((f["file"], f["line"]))

    if not unknown:
        return {
            "id": "table_exists",
            "status": "PASS",
            "message": f"every db.from() references a known table ({len(schema)} in migrations)",
            "details": [],
        }
    msgs = []
    for table, refs in sorted(unknown.items()):
        first = refs[0]
        more = f" (+{len(refs)-1} more)" if len(refs) > 1 else ""
        msgs.append(f"{table} ({first[0]}:{first[1]}{more})")
    return {
        "id": "table_exists",
        "status": "FAIL",
        "message": f"{len(unknown)} unknown table(s): {', '.join(msgs)}",
        "details": [{"table": t, "refs": [{"file": r[0], "line": r[1]} for r in refs]} for t, refs in sorted(unknown.items())],
    }


def check_column_existence(schema: dict, findings: list) -> dict:
    bad = []
    for f in findings:
        if f["_from_only"]:
            continue
        table = f["table"]
        cols = schema.get(table)
        if cols is None:
            continue   # table missing is reported separately
        for c in f["columns"]:
            if c not in cols:
                bad.append({"file": f["file"], "line": f["line"], "table": table, "column": c})

    if not bad:
        return {
            "id": "column_exists",
            "status": "PASS",
            "message": "every plain column in db.from().select() exists in migrations",
            "details": [],
        }
    by_pair = {}
    for b in bad:
        key = f"{b['table']}.{b['column']}"
        by_pair.setdefault(key, []).append(f"{b['file']}:{b['line']}")
    msgs = []
    for key, locs in sorted(by_pair.items()):
        first = locs[0]
        more = f" (+{len(locs)-1} more)" if len(locs) > 1 else ""
        msgs.append(f"{key} ({first}{more})")
    return {
        "id": "column_exists",
        "status": "FAIL",
        "message": f"{len(by_pair)} unknown column reference(s): {', '.join(msgs)}",
        "details": [{"key": k, "locations": v} for k, v in sorted(by_pair.items())],
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    schema = build_schema()
    findings = scan_code()
    selects = [f for f in findings if not f["_from_only"]]
    from_only = [f for f in findings if f["_from_only"]]

    checks = [
        check_table_existence(schema, findings),
        check_column_existence(schema, findings),
    ]

    fails = [c for c in checks if c["status"] == "FAIL"]
    warns = [c for c in checks if c["status"] == "WARN"]
    passes = [c for c in checks if c["status"] == "PASS"]

    print("=" * 70)
    print("SCHEMA COVERAGE VALIDATOR")
    print("=" * 70)
    total_cols = sum(len(c) for c in schema.values())
    print(f"  Loaded {len(schema)} tables, {total_cols} columns from migrations.")
    print(f"  Found {len(selects)} db.from().select() calls, {len(from_only)} other db.from() calls.")
    print()
    for c in checks:
        icon = {"PASS": "[OK]", "WARN": "[WARN]", "FAIL": "[FAIL]"}[c["status"]]
        print(f"  {icon} {c['id']:18} {c['message']}")
    print()
    print(f"  Summary: {len(passes)} pass · {len(warns)} warn · {len(fails)} fail")

    report = {
        "ok": len(fails) == 0,
        "summary": {"pass": len(passes), "warn": len(warns), "fail": len(fails)},
        "schema_table_count": len(schema),
        "schema_column_count": total_cols,
        "selects_scanned": len(selects),
        "checks": checks,
    }
    with open(os.path.join(ROOT, "schema_coverage_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
