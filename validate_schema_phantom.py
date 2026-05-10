"""
Schema Phantom Column Detector -- WorkHive Platform
====================================================
Catches the `reorder_point` bug class: queries that ask for a column the
underlying table doesn't have, returning silent nulls forever.

The four bug classes this catches:
  - phantom reads (column referenced in .select(...) does not exist)
  - dead columns (defined on tables but no consumer reads them — schema bloat)
  - alias drift (PostgREST `alias:underlying` rewrites concentrated; the right
    fix is usually a canonical view alias, not 5 ad-hoc renames)
  - column-by-layer concentration (a column read by only one platform layer
    when it should be cross-cutting)

Layer 1 -- Phantom column reads                                           [WARN]
  For every .select('a, b, c') in production code, every column should
  exist somewhere in the migrations as either:
    - a real column on the queried table OR a related canonical view
    - an aliased PostgREST rewrite (`alias:underlying`)
    - an embedded foreign-key shape (`asset_name(name)`)
    - a wildcard ('*') select
    - a count/aggregate (`id`, '*', `count`)
  Otherwise it is a phantom — the read returns null silently.

Layer 2 -- Dead columns                                                   [WARN]
  Columns defined in CREATE TABLE blocks that NO consumer file selects.
  Either the column is unused (candidate for removal) or every reader
  uses '*' (which is also a code smell).

Layer 3 -- Alias drift                                                    [WARN]
  PostgREST `alias:underlying` rewrites where the same alias is applied
  to the same column from 3+ different files. Means the underlying name
  is "wrong" for all of them — bake the alias into a canonical view once.

Layer 4 -- Column-by-layer concentration                                  [INFO]
  Frequently-selected columns read by only one platform layer when they
  carry domain meaning. Surfaces lopsided reads that suggest cross-cutting
  data is being trapped in one place.

Skills consulted: data-engineer (schema integrity), architect (canonical
view alias pattern, the reorder_point production fix), security (phantom
columns silently return null, which can mask validation failures).
"""
from __future__ import annotations

import re
import json
import sys
import os
import glob
from collections import defaultdict

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


# ── Paths ─────────────────────────────────────────────────────────────────────

MIGRATIONS_DIR = os.path.join("supabase", "migrations")
FUNCTIONS_DIR  = os.path.join("supabase", "functions")
PYTHON_API_DIR = "python-api"

EXCLUDED_HTML_PATTERNS = ("-test.html", ".backup.html", "_backup.html", ".backup")
EXCLUDED_PATH_PARTS = (
    os.sep + "test-data-seeder" + os.sep,
    os.sep + "tools" + os.sep,
    os.sep + "video_marketing_app" + os.sep,
    os.sep + ".git" + os.sep,
    os.sep + "node_modules" + os.sep,
)

# Tables we treat as opaque — third-party (Stripe, Supabase auth, postgres
# system catalogs) or generated. We don't have CREATE TABLE statements for
# them so we can't compute phantom-column lists.
OPAQUE_TABLES = {
    "auth", "users", "objects",   # supabase storage / auth
    "pg_publication_tables",
    "information_schema",
}

# Column tokens that are always valid in SELECT regardless of table:
#  '*' / 'id' (PK convention) / 'count' (aggregate keyword passed in
#  PostgREST options like { count: 'exact' }).
ALWAYS_VALID_TOKENS = {"*", "id", "count"}

ALIAS_DRIFT_THRESHOLD = 3   # files using same alias before WARN
DEAD_COLUMN_REPORT_TOP_N = 12  # cap the dead-column report for readability


# ── Schema discovery ─────────────────────────────────────────────────────────

# Match CREATE TABLE blocks across all migrations and capture column names.
# We rely on the same `read_file` shared helper as the other validators.

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
# Match a column-definition line. Accepts:
#   col_name TYPE ...
#   "col_name" "TYPE" ...           (Supabase pg_dump baseline format)
#   "col_name" timestamp with ...   (multi-word unquoted types)
# We just need the column name; the type can be anything that follows.
COLUMN_LINE_RE = re.compile(
    r"""^\s*"?(?P<col>\w+)"?\s+["a-zA-Z]""",
    re.MULTILINE,
)
COL_KEYWORDS = {
    "constraint", "primary", "unique", "foreign", "check", "exclude",
    "like", "create", "alter",
    # NOTE: 'comment' is intentionally NOT excluded — it's a valid column
    # name used by marketplace_reviews and others. The few COMMENT-statement
    # false positives don't cause phantoms in practice.
}


def load_table_columns() -> dict[str, set[str]]:
    """Return { table_name: set(column_names) } across all migrations.

    Handles:
      - CREATE TABLE [IF NOT EXISTS] ...
      - ALTER TABLE ... ADD COLUMN [IF NOT EXISTS] ...
      - CREATE [OR REPLACE] VIEW ... AS SELECT col_a [AS alias_a], ...
        (view columns are derived from the SELECT list — best-effort)
    """
    cols: dict[str, set[str]] = defaultdict(set)
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = re.sub(r"--[^\n]*", "", read_file(path) or "")
        # CREATE TABLE
        for m in CREATE_TABLE_RE.finditer(sql):
            name = m.group("name").lower()
            body = m.group("body")
            for cm in COLUMN_LINE_RE.finditer(body):
                col = cm.group("col").lower()
                if col in COL_KEYWORDS:
                    continue
                cols[name].add(col)
        # ALTER TABLE ADD COLUMN
        for m in ALTER_ADD_RE.finditer(sql):
            cols[m.group("name").lower()].add(m.group("col").lower())
        # CREATE VIEW with SELECT list. v_asset_truth has scalar subqueries
        # like `(SELECT count(*) FROM logbook ...) AS lifetime_logbook_entries`
        # that contain inner FROMs. We must capture the SELECT body up to the
        # OUTERMOST FROM (paren depth 0), not the first FROM the regex finds.
        for m in re.finditer(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+(?:public\.)?(\w+)\s+AS\s+",
            sql, re.IGNORECASE,
        ):
            view = m.group(1).lower()
            start = m.end()
            # Walk forward from `start` to find the outermost FROM
            depth = 0
            i = start
            select_end = -1
            while i < len(sql):
                ch = sql[i]
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                elif depth == 0 and ch in "Ff":
                    # Look for FROM token at depth 0
                    if sql[i:i+5].upper() == "FROM ":
                        select_end = i
                        break
                # Stop at end of statement
                if depth == 0 and ch == ";":
                    break
                i += 1
            if select_end < 0:
                continue
            # Need to also strip the leading SELECT
            sel_body = sql[start:select_end]
            sel_body = re.sub(r"^\s*SELECT\b", "", sel_body, flags=re.IGNORECASE).strip()
            # Now strip contents of parens (subqueries, function calls) so commas
            # inside them don't split column boundaries
            depth = 0
            cleaned: list[str] = []
            for ch in sel_body:
                if   ch == "(": depth += 1
                elif ch == ")": depth -= 1
                elif depth == 0: cleaned.append(ch)
            select_list = "".join(cleaned)
            for piece in select_list.split(","):
                piece = piece.strip()
                if not piece:
                    continue
                # AS alias OR last identifier wins
                m2 = re.search(r"\bAS\s+\"?(\w+)\"?\s*$", piece, re.IGNORECASE)
                if m2:
                    cols[view].add(m2.group(1).lower())
                    continue
                last = re.search(r"(\w+)\s*$", piece)
                if last:
                    name = last.group(1).lower()
                    if name not in COL_KEYWORDS:
                        cols[view].add(name)
    return {k: v for k, v in cols.items()}


# ── Consumer scan ────────────────────────────────────────────────────────────

# Match `db.from('TABLE').select('col_a, col_b, ...')` in JS/TS/HTML.
# Capture the SELECT body up to the closing quote.
# Capture .from('TABLE')...select('COLUMNS') in JS/TS/HTML.
# IMPORTANT: the sel body negation must NOT include `)` — embed shapes like
# `marketplace_listings(title)` legitimately contain parens inside the
# select string. Excluding `)` would terminate the match early and cause
# false dead-column reports.
SELECT_RE_JSTS = re.compile(
    r"""\.from\s*\(\s*['"`](?P<table>[a-z_][a-z0-9_]*)['"`]\s*\)
        (?:\s*\.\s*[a-zA-Z_]\w*\s*\([^)]*\))*?
        \s*\.\s*select\s*\(\s*['"`](?P<sel>[^'"`]+)['"`]""",
    re.IGNORECASE | re.VERBOSE,
)
SELECT_RE_PY = re.compile(
    r"""\.table\s*\(\s*['"](?P<table>[a-z_][a-z0-9_]*)['"]\s*\)
        \s*\.\s*select\s*\(\s*['"](?P<sel>[^'"]+)['"]""",
    re.IGNORECASE | re.VERBOSE,
)
ALIAS_RE = re.compile(r"^([a-zA-Z_]\w*)\s*:\s*([a-zA-Z_]\w*)$")
EMBED_RE = re.compile(r"^([a-zA-Z_]\w*)\s*\(")


def _path_excluded(path: str) -> bool:
    return any(part in path for part in EXCLUDED_PATH_PARTS)


def list_consumer_files() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for path in sorted(glob.glob("*.html")):
        if any(p in path.lower() for p in EXCLUDED_HTML_PATTERNS): continue
        out.append((path, "html"))
    for path in sorted(glob.glob("*.js")):
        if path.endswith(".min.js"): continue
        out.append((path, "shared_js"))
    if os.path.isdir(FUNCTIONS_DIR):
        for d in sorted(os.listdir(FUNCTIONS_DIR)):
            idx = os.path.join(FUNCTIONS_DIR, d, "index.ts")
            if os.path.isfile(idx):
                out.append((idx, "edge"))
    for path in sorted(glob.glob(os.path.join(PYTHON_API_DIR, "**", "*.py"), recursive=True)):
        if "__init__" in path or _path_excluded(path): continue
        out.append((path, "python_api"))
    return out


def file_select_clauses(path: str) -> list[tuple[str, str]]:
    """Return [(table, select_body)] for every .from(table).select('...') in file."""
    content = read_file(path) or ""
    rx = SELECT_RE_PY if path.endswith(".py") else SELECT_RE_JSTS
    return [(m.group("table").lower(), m.group("sel")) for m in rx.finditer(content)]


def parse_select_columns(sel: str) -> tuple[set[str], list[tuple[str, str]]]:
    """Return ({col_or_alias_token}, [(alias, underlying)] for PostgREST renames).

    Handles:
      - bare columns: `part_name`
      - PostgREST renames: `alias:underlying`
      - FK embed shapes (skipped — both `table(cols)` and `alias:table(cols)`
        are FK relationship references, not column references on the parent;
        validating them would require the foreign-key metadata.
    """
    cols: set[str] = set()
    aliases: list[tuple[str, str]] = []
    # Split on commas BUT respect parentheses (so embed shapes don't split)
    pieces: list[str] = []
    depth = 0
    buf = ""
    for ch in sel:
        if ch == "(": depth += 1; buf += ch
        elif ch == ")": depth -= 1; buf += ch
        elif ch == "," and depth == 0:
            pieces.append(buf); buf = ""
        else:
            buf += ch
    if buf: pieces.append(buf)

    for piece in pieces:
        piece = piece.strip()
        if not piece: continue
        # Aliased FK embed: `alias:table(cols)` — skip entirely, FK relationship.
        if re.match(r"^[a-zA-Z_]\w*\s*:\s*[a-zA-Z_]\w*\s*\(", piece):
            continue
        # Plain FK embed: `table(cols)` — skip entirely, FK relationship name
        # is not a column on the parent table.
        em = EMBED_RE.match(piece)
        if em:
            continue
        # `alias:underlying` PostgREST rename (no parens after)
        am = ALIAS_RE.match(piece)
        if am:
            cols.add(am.group(2).lower())     # the underlying column must exist
            aliases.append((am.group(1).lower(), am.group(2).lower()))
            continue
        # Bare column
        token = piece.strip()
        if token:
            cols.add(token.lower())
    return cols, aliases


# ── Layer 1: Phantom column reads ────────────────────────────────────────────

def check_phantom_reads(
    consumer_files: list[tuple[str, str]],
    table_cols: dict[str, set[str]],
) -> tuple[list[dict], list[dict]]:
    """Each .select column must exist on the table (or a related view, or
    be an always-valid token like '*'/'id')."""
    issues: list[dict] = []
    phantom_report: list[dict] = []
    for path, _layer in consumer_files:
        for table, sel in file_select_clauses(path):
            if table in OPAQUE_TABLES:
                continue
            cols, _aliases = parse_select_columns(sel)
            known = table_cols.get(table)
            if known is None:
                # Table is opaque to us — no migration declares it; skip
                # silently rather than spam.
                continue
            phantoms: list[str] = []
            for col in cols:
                if col in ALWAYS_VALID_TOKENS:
                    continue
                if col in known:
                    continue
                phantoms.append(col)
            if phantoms:
                phantom_report.append({
                    "path":     path,
                    "table":    table,
                    "phantoms": phantoms[:5],
                    "select":   sel[:120],
                })
                issues.append({
                    "check": "phantom_reads", "skip": True,
                    "reason": (
                        f"{path}: .from('{table}').select('{sel[:80]}{'...' if len(sel) > 80 else ''}')"
                        f" references column(s) {phantoms[:5]} that do not exist on the underlying "
                        f"table or any related view. The query returns null silently — fix the "
                        f"column name or alias it via a canonical view."
                    ),
                })
    return issues, phantom_report


# ── Layer 2: Dead columns ────────────────────────────────────────────────────

def _backed_by_canonical_view(table: str, view_primaries: set[str]) -> bool:
    """Suppress dead-column WARNs for tables that back any canonical view.

    Walks the FROM clause of every CREATE VIEW in migrations and checks if
    the table appears as a primary backing table. Naming convention does not
    matter (asset_nodes is read via v_asset_truth, not v_asset_nodes_truth).
    """
    return table in view_primaries


def _load_canonical_view_primaries() -> set[str]:
    """Return the set of underlying tables used as the outermost FROM in any
    CREATE VIEW. Mirrors the silo monitor's depth-aware parser."""
    primaries: set[str] = set()
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = re.sub(r"--[^\n]*", "", read_file(path) or "")
        for m in re.finditer(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+(?:public\.)?\w+\s+AS\s+",
            sql, re.IGNORECASE,
        ):
            start = m.end()
            depth = 0
            i = start
            while i < len(sql):
                ch = sql[i]
                if   ch == "(": depth += 1
                elif ch == ")": depth -= 1
                elif depth == 0 and ch in "Ff" and sql[i:i+5].upper() == "FROM ":
                    # Find table name after FROM
                    rest = sql[i+5:i+200]
                    tm = re.match(r"\s*(?:public\.)?(\w+)", rest)
                    if tm:
                        t = tm.group(1).lower()
                        if not t.startswith("v_") and t not in ("select", "values", "lateral"):
                            primaries.add(t)
                    break
                if depth == 0 and ch == ";":
                    break
                i += 1
    return primaries


def check_dead_columns(
    consumer_files: list[tuple[str, str]],
    table_cols: dict[str, set[str]],
) -> tuple[list[dict], list[dict]]:
    """Columns defined on tables that no consumer SELECTs explicitly."""
    # Build {table: {selected_columns}} across all consumers
    selected: dict[str, set[str]] = defaultdict(set)
    for path, _layer in consumer_files:
        for table, sel in file_select_clauses(path):
            cols, _ = parse_select_columns(sel)
            # `*` selects everything; treat it as "covered all"
            if "*" in cols:
                selected[table] |= table_cols.get(table, set())
                continue
            selected[table] |= cols

    # Tables we intentionally don't audit for dead columns (system / metadata
    # tables, audit logs that are written but not selectively read, etc.).
    DEAD_IGNORE_TABLES = {
        "canonical_sources", "ai_rate_limits", "automation_log",
        "hive_audit_log", "cmms_audit_log", "achievement_definitions",
        "equipment_reading_templates", "schedule_items",
        "engineering_calc_history", "early_access_emails",
    }
    # Columns commonly present but not read directly. These come in three flavours:
    #   A. AUDIT / OWNERSHIP — stamped on insert, never displayed
    #   B. FILTER ONLY — used in .eq() / .in() / WHERE but never SELECTed
    #   C. WRITE-ONLY — set on update, never read back as a value
    SILENT_COLUMNS = {
        # Audit / ownership (Category A)
        "auth_uid", "submitted_by", "approved_by", "approved_at",
        "registered_at", "last_validated", "owner",
        # Filter-only (Category B) — universal scoping/lookup keys
        "id", "hive_id", "worker_name", "status", "updated_at", "created_at",
        # Write-only (Category C) — state transitions stamped on update
        "acknowledged_at", "acknowledged_by",
        "consumed_at", "released_at", "reserved_at",
        "buyer_confirmed_at", "kyb_verified_at", "cert_verified_at",
        "expires_at",
        # FK / reference columns set at insert, used in joins not SELECTs
        "recommendation_id", "scope_item_id", "asset_id", "pm_asset_id",
        "fmea_mode_id", "weibull_fit_id", "pf_interval_id",
    }

    view_primaries = _load_canonical_view_primaries()
    dead: list[dict] = []
    for table, cols in table_cols.items():
        if table in DEAD_IGNORE_TABLES: continue
        if not cols: continue
        # Skip views — they are consumption shapes, not backing tables. Their
        # "unused" columns are an unrelated signal.
        if table.startswith("v_") or table == "asset_brain_overview": continue
        # Skip tables that back any canonical view (regardless of naming
        # convention). asset_nodes is read via v_asset_truth, not via
        # v_asset_nodes_truth — checking name only would miss this.
        if _backed_by_canonical_view(table, view_primaries): continue
        # Result-of-compute tables (insert-only, read via DISTINCT-ON view)
        # rarely have direct selectors; skip if the canonical pattern applies.
        if table in {"asset_risk_scores", "weibull_fits", "pf_intervals",
                     "shift_plans", "parts_staging_recommendations",
                     "ph_intelligence_reports", "ai_reports",
                     "hive_benchmarks", "network_benchmarks"}:
            continue
        # Knowledge / RAG tables: consumed via vector similarity RPC, not
        # column-by-column SELECT — most columns will look "dead".
        if table.endswith("_knowledge") or table.endswith("_embeddings"):
            continue
        unused = sorted((cols - selected.get(table, set())) - SILENT_COLUMNS)
        if not unused: continue
        dead.append({
            "table":         table,
            "n_unused":      len(unused),
            "unused_sample": unused[:8],
        })
    dead.sort(key=lambda d: -d["n_unused"])
    issues: list[dict] = []
    for d in dead[:DEAD_COLUMN_REPORT_TOP_N]:
        if d["n_unused"] >= 5:
            issues.append({
                "check": "dead_columns", "skip": True,
                "reason": (
                    f"Table '{d['table']}' has {d['n_unused']} column(s) that no consumer "
                    f"selects explicitly. Sample: {d['unused_sample']}. Either remove the "
                    f"unused columns or wrap them in '*' selectors if intentional."
                ),
            })
    return issues, dead


# ── Layer 3: Alias drift ─────────────────────────────────────────────────────

def check_alias_drift(consumer_files: list[tuple[str, str]]) -> tuple[list[dict], list[dict]]:
    """Aliases (alias:underlying) used across N+ files for the same column."""
    alias_use: dict[tuple[str, str], list[str]] = defaultdict(list)  # (alias, underlying) -> [paths]
    for path, _layer in consumer_files:
        for table, sel in file_select_clauses(path):
            _cols, aliases = parse_select_columns(sel)
            for (alias, underlying) in aliases:
                alias_use[(alias, underlying)].append(path)
    issues: list[dict] = []
    drifts: list[dict] = []
    for (alias, underlying), paths in alias_use.items():
        if len(set(paths)) >= ALIAS_DRIFT_THRESHOLD:
            drifts.append({
                "alias": alias, "underlying": underlying,
                "n_files": len(set(paths)), "sample": sorted(set(paths))[:5],
            })
            issues.append({
                "check": "alias_drift", "skip": True,
                "reason": (
                    f"Alias '{alias}:{underlying}' is used in {len(set(paths))} files. "
                    f"This means the underlying column name is 'wrong' for all of them — "
                    f"bake '{alias}' into a canonical view's column list instead of repeating "
                    f"the rename at every call site. Sample: {sorted(set(paths))[:3]}."
                ),
            })
    return issues, drifts


# ── Layer 4: Column-by-layer concentration ───────────────────────────────────

def check_column_layer_concentration(
    consumer_files: list[tuple[str, str]],
) -> tuple[list[dict], list[dict]]:
    """Column-by-layer matrix is informational. We surface columns selected
    20+ times that appear in only one platform layer — likely candidates for
    promoting to canonical or for cross-system wiring."""
    # { (table, col): {layer: count} }
    counter: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for path, layer in consumer_files:
        for table, sel in file_select_clauses(path):
            cols, _ = parse_select_columns(sel)
            for c in cols:
                if c in ALWAYS_VALID_TOKENS: continue
                counter[(table, c)][layer] += 1
    concentrated: list[dict] = []
    for (table, col), layers in counter.items():
        total = sum(layers.values())
        if total < 5: continue
        n_layers = len([l for l, n in layers.items() if n > 0])
        if n_layers != 1: continue
        only = next(iter(layers.keys()))
        if total < 8: continue   # require some volume before complaining
        concentrated.append({
            "table": table, "column": col,
            "only_layer": only, "n_uses": total,
        })
    concentrated.sort(key=lambda c: -c["n_uses"])
    return [], concentrated   # informational only — no WARNs


# ── Runner ────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "phantom_reads",
    "dead_columns",
    "alias_drift",
    "column_layer_concentration",
]
CHECK_LABELS = {
    "phantom_reads":              "L1  No .select() references a column that does not exist          [WARN]",
    "dead_columns":               "L2  No table has 5+ columns that nothing selects (dead schema)    [WARN]",
    "alias_drift":                "L3  No alias:underlying rewrite is repeated in 3+ files (canonical-view candidate) [WARN]",
    "column_layer_concentration": "L4  Column reads spread across platform layers (informational)    [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nSchema Phantom Column Detector (4-layer)"))
    print("=" * 60)

    table_cols     = load_table_columns()
    consumer_files = list_consumer_files()

    print(f"  {len(table_cols)} tables/views with declared columns, "
          f"{len(consumer_files)} consumer files scanned.\n")

    phantom_issues, phantom_report     = check_phantom_reads(consumer_files, table_cols)
    dead_issues,    dead_report        = check_dead_columns(consumer_files, table_cols)
    alias_issues,   alias_report       = check_alias_drift(consumer_files)
    layer_issues,   layer_report       = check_column_layer_concentration(consumer_files)

    all_issues = phantom_issues + dead_issues + alias_issues + layer_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if layer_report:
        print(f"\n{bold('SINGLE-LAYER COLUMN HOTSPOTS (informational)')}")
        print("  " + "-" * 56)
        for c in layer_report[:8]:
            print(f"  {c['table']}.{c['column']:<22} only {c['only_layer']:<8}  uses={c['n_uses']}")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "schema_phantom",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "n_tables":     len(table_cols),
        "n_consumers":  len(consumer_files),
        "phantom_reads": phantom_report,
        "dead_columns":  dead_report,
        "alias_drift":   alias_report,
        "column_layer_hotspots": layer_report,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("schema_phantom_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
