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

# Extra columns for tables whose baseline migration has encoding issues
# (20260420000000_baseline.sql uses non-UTF-8 bytes — validator skips it,
# so these well-known columns need an explicit override to avoid false positives).
EXTRA_COLUMNS: dict[str, set] = {
    "inventory_items": {
        "id", "hive_id", "worker_name", "part_name", "part_number", "category",
        "qty_on_hand", "reorder_point", "unit", "location", "notes",
        "status", "submitted_by", "approved_by", "approved_at", "created_at", "updated_at",
    },
    "inventory_transactions": {
        "id", "hive_id", "worker_name", "part_name", "part_number", "item_id",
        "qty_change", "qty_after", "type", "reference", "notes", "created_at",
    },
    "logbook": {
        "id", "hive_id", "worker_name", "machine", "maintenance_type", "category",
        "failure_mode", "root_cause", "problem", "action", "knowledge", "downtime_hours",
        "status", "closed_at", "created_at", "logged_at", "parts_used", "readings_json",
        "pm_completion_id", "asset_id", "tag_id", "asset_ref_id",
        # Phase E.4 (2026-05-08): Work Order state machine columns.
        "wo_state", "wo_assigned_to",
    },
    # Asset Brain Phase 0 (2026-05-08) — graph schema for the Asset Hub.
    # Migration 20260508000009_asset_brain_foundation.sql.
    "asset_nodes": {
        "id", "hive_id", "auth_uid", "worker_name", "parent_id", "level", "tag", "name",
        "iso_class", "criticality", "location", "manufacturer", "model", "serial_no",
        "install_date", "external_ids", "legacy_asset_id", "pm_asset_id",
        "status", "submitted_by", "approved_by", "approved_at",
        "created_at", "updated_at",
    },
    "asset_edges": {
        "id", "hive_id", "auth_uid", "from_node_id", "to_node_id",
        "edge_type", "properties", "created_at",
    },
    "asset_embeddings": {
        "node_id", "hive_id", "summary", "embedding", "refreshed_at",
    },
    "asset_brain_overview": {
        "node_id", "hive_id", "tag", "name", "level", "iso_class", "criticality",
        "location", "parent_id", "legacy_asset_id", "pm_asset_id",
        "lifetime_logbook_entries", "last_failure_at", "pm_completed_count", "edge_count",
    },
    # Shift Brain Phase 4 (2026-05-08) — shift planner output.
    # Migration 20260508000011_shift_brain_foundation.sql.
    "shift_plans": {
        "id", "hive_id", "shift_window", "shift_date", "status",
        "generated_at", "generated_by", "published_at", "published_by",
        "briefing", "payload", "created_at", "updated_at",
    },
    # Shared AI infra (2026-05-08).
    "ai_rate_limits": {
        "hive_id", "call_count", "window_start",
    },
    # Failure signature pattern alerts (older migration, baseline encoding issue).
    "failure_signature_alerts": {
        "id", "hive_id", "machine", "signature_kind", "message", "severity",
        "created_at", "resolved_at", "resolved_by",
    },
}


# ── Migration parser ──────────────────────────────────────────────────────────

RE_CREATE_TABLE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r'(?:"?(\w+)"?\.)?"?(\w+)"?\s*\((.*?)\)\s*(?:WITH\s|TABLESPACE\s|;|$)',
    re.IGNORECASE | re.DOTALL,
)
RE_CREATE_VIEW = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:MATERIALIZED\s+)?VIEW\s+"
    r'(?:"?(\w+)"?\.)?"?(\w+)"?\s+AS\b',
    re.IGNORECASE,
)
# Sentinel: register views with this column so the table_exists check passes
# but the column_exists check skips (views have computed columns we don't parse).
VIEW_SENTINEL_COL = "__view__"
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

        # Views: register the name so table_exists passes; mark with sentinel so
        # column_exists skips (we don't parse SELECT lists).
        for m in RE_CREATE_VIEW.finditer(sql):
            schema_name = (m.group(1) or "public").lower()
            if schema_name not in {"public", ""}:
                continue
            view = m.group(2)
            schema.setdefault(view, set()).add(VIEW_SENTINEL_COL)

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

    # Apply EXTRA_COLUMNS for tables whose migration files have encoding issues
    for table, cols in EXTRA_COLUMNS.items():
        schema.setdefault(table, set()).update(cols)

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
        if VIEW_SENTINEL_COL in cols:
            continue   # view: column list is computed from SELECT, skip
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
