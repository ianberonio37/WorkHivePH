"""
State Machine Integrity Monitor -- WorkHive Platform
=====================================================
Tables with `status` columns are state machines. Every write must use a
value from the allowed set (defined by a CHECK constraint), and every
allowed value should be reachable from at least one writer. Status drift
between writers ('Done' vs 'Closed', 'open' vs 'Open') is the #1 source
of "this entity is in an impossible state" bugs that the existing 71
validators don't catch.

Layer 1 -- Invalid status writes                                          [WARN]
  For each table with a CHECK constraint listing allowed status values,
  every literal `.update({ status: 'X' })` and `.insert({ ..., status:
  'X' })` must use a value within the allowed set. Catches typos
  ('Compleed' vs 'Completed'), case drift ('open' vs 'Open'), and
  forgotten state additions.

Layer 2 -- Unreachable states                                             [WARN]
  Every value in a CHECK constraint should be reachable from at least
  one literal write somewhere in the codebase. States defined but never
  written are dead — either remove them from the CHECK or wire the
  missing writer.

Layer 3 -- Unconstrained status columns                                   [WARN]
  Tables that declare a `status` column but do NOT have a CHECK
  constraint listing the allowed values. Without the CHECK, any string
  is accepted; state drift is inevitable.

Layer 4 -- Writer-layer concentration                                     [INFO]
  For each table's status field, who can write to it? (HTML / edge fn /
  python_api). Single-layer writers are documented as expected; this
  layer is informational so a future cross-layer write isn't blindsided.

Skills consulted: architect (state-machine ownership pattern), data-engineer
(CHECK constraint as the canonical contract), security (an entity in an
impossible state can bypass downstream guards), platform-guardian
(non-blocking informational tier).
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

# Tables we don't enforce CHECK constraints on. Either status is intentionally
# free-form (chat-style threads) or the CHECK lives elsewhere (in a trigger).
STATUS_COLUMN_IGNORE_TABLES = {
    "schedule_items",     # itemStatus is a free-form ad-hoc planner state
}

# Domains where we accept that allowed states intentionally exceed the active
# code paths (deprecated values kept for back-compat history reads).
ACCEPTED_UNREACHABLE_STATES: dict[str, set[str]] = {
    # marketplace_orders is partly state-machine, partly observability
    # ('refunded' is reachable only from the Stripe webhook path which is
    # already proven). The allowlist is empty until we surface a real one.
}


# ── Discovery ────────────────────────────────────────────────────────────────

def _path_excluded(path: str) -> bool:
    return any(part in path for part in EXCLUDED_PATH_PARTS)


def list_writer_files() -> list[tuple[str, str]]:
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


# ── Schema discovery: status CHECK constraints + status columns ──────────────

# Match `CHECK (status IN ('a', 'b', ...))` or `status text CHECK (status IN (...))`
# inside a CREATE TABLE body, plus the ALTER TABLE ADD CONSTRAINT form.
CHECK_IN_RE = re.compile(
    r"""(?:status|"status")\s+(?:text|"text")[^,)]*?
        CHECK\s*\(\s*(?:status|"status")\s+(?:=\s*ANY\s*\(\s*ARRAY)?
        \s*[\(\[]?\s*((?:'[^']+'\s*,?\s*)+)""",
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)
CHECK_INDEPENDENT_RE = re.compile(
    r"""CHECK\s*\(\s*(?:status|"status")\s+IN\s*\(\s*((?:'[^']+'\s*,?\s*)+)\s*\)\s*\)""",
    re.IGNORECASE | re.DOTALL,
)
# Match `ALTER TABLE <name> ADD CONSTRAINT <name> CHECK (...)` — the body must
# stay within a single SQL statement so multi-statement migrations don't bleed
# the regex match across tables. We use [^;]* so anything spanning a `;` cuts
# the match. Also accept either `status IN (...)` or `status IS NULL OR
# status IN (...)` form (PostgreSQL passes NULL automatically, but writers
# may include the redundant guard).
ALTER_ADD_CHECK_RE = re.compile(
    r"""ALTER\s+TABLE\s+(?:public\.|"public"\.)?"?(?P<table>\w+)"?\s+
        ADD\s+CONSTRAINT\s+[\w_]+\s+
        CHECK\s*\(\s*
        (?:(?:status|"status")\s+IS\s+NULL\s+OR\s+)?
        (?:status|"status")\s+IN\s*\(\s*
        ((?:'[^']+'\s*,?\s*)+)\s*\)\s*\)""",
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)
CREATE_TABLE_RE = re.compile(
    r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?
        (?:public\.|"public"\.)?
        "?(?P<name>\w+)"?\s*\((?P<body>[\s\S]*?)\n\s*\);""",
    re.IGNORECASE | re.VERBOSE,
)
STATUS_COL_RE = re.compile(
    r"""^\s*"?status"?\s+(?:text|"text")""",
    re.IGNORECASE | re.MULTILINE,
)

# Capture `"status" "text" DEFAULT 'value'::text` and similar — the
# DEFAULT value is a state that's reachable by every insert that omits
# the status field (which is the common pattern).
STATUS_DEFAULT_RE = re.compile(
    r"""^\s*"?status"?\s+(?:text|"text")[^,)]*?DEFAULT\s+'(?P<value>[^']+)'""",
    re.IGNORECASE | re.MULTILINE,
)


def _parse_state_literals(blob: str) -> set[str]:
    return {m.group(1) for m in re.finditer(r"'([^']+)'", blob)}


def load_status_constraints() -> tuple[dict[str, set[str]], set[str], dict[str, str]]:
    """Returns (
      { table: {allowed_status_values} },   # tables with CHECK
      { table: ... },                        # tables with status col but no CHECK
      { table: default_status_value },       # tables whose insert defaults set status
    )"""
    with_check: dict[str, set[str]] = {}
    has_status_col: set[str] = set()
    defaults: dict[str, str] = {}

    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = re.sub(r"--[^\n]*", "", read_file(path) or "")

        for m in CREATE_TABLE_RE.finditer(sql):
            table = m.group("name").lower()
            body  = m.group("body")
            if STATUS_COL_RE.search(body):
                has_status_col.add(table)
                # In-body CHECK constraint forms
                for cm in CHECK_IN_RE.finditer(body):
                    states = _parse_state_literals(cm.group(1))
                    if states:
                        with_check[table] = with_check.get(table, set()) | states
                for cm in CHECK_INDEPENDENT_RE.finditer(body):
                    states = _parse_state_literals(cm.group(1))
                    if states:
                        with_check[table] = with_check.get(table, set()) | states
                # DEFAULT clause — the column default value is reachable by
                # every insert that omits the status field (common pattern).
                dm = STATUS_DEFAULT_RE.search(body)
                if dm:
                    defaults[table] = dm.group("value")

        # ALTER TABLE ADD CONSTRAINT form (later migrations sometimes add
        # the CHECK in a separate statement)
        for m in ALTER_ADD_CHECK_RE.finditer(sql):
            table = m.group("table").lower()
            states = _parse_state_literals(m.group(2))
            if states:
                with_check[table] = with_check.get(table, set()) | states
                has_status_col.add(table)

    return with_check, has_status_col, defaults


# ── Consumer scan: find every literal status write ───────────────────────────

# Match .from('TABLE').(insert|upsert)({...status: 'literal'...})
# or chained .update({...status: 'literal'...}). Keep it best-effort: literal
# string only — variable values like { status: someVar } are skipped.
WRITE_OBJ_RE_JSTS = re.compile(
    r"""\.from\s*\(\s*['"`](?P<table>[a-z_][a-z0-9_]*)['"`]\s*\)
        (?:\s*\.\s*[a-zA-Z_]\w*\s*\([^)]*\))*?
        \s*\.\s*(?P<op>insert|upsert|update)\s*\(\s*\{(?P<body>[^{}]*)\}""",
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)
STATUS_KEY_RE = re.compile(
    r"""(?<![a-zA-Z_])status\s*:\s*['"`](?P<value>[^'"`]+)['"`]""",
)


def file_status_writes(path: str, layer: str) -> list[dict]:
    """Return [{table, op, status_value, layer, path}] for every literal
    status write in this file."""
    content = read_file(path) or ""
    if path.endswith(".py"):
        return []   # Python writers rarely use literal status objects
    out: list[dict] = []
    for m in WRITE_OBJ_RE_JSTS.finditer(content):
        table = m.group("table").lower()
        op    = m.group("op").lower()
        body  = m.group("body")
        for sm in STATUS_KEY_RE.finditer(body):
            out.append({
                "path": path, "layer": layer, "table": table,
                "op": op, "status_value": sm.group("value"),
            })
    return out


# ── Layer 1: Invalid status writes ───────────────────────────────────────────

def check_invalid_writes(writes: list[dict], constraints: dict[str, set[str]]) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    invalid: list[dict] = []
    for w in writes:
        table = w["table"]
        if table not in constraints:
            continue   # No CHECK to enforce against
        allowed = constraints[table]
        if w["status_value"] not in allowed:
            invalid.append(w)
            issues.append({
                "check": "invalid_writes", "skip": True,
                "reason": (
                    f"{w['path']}: writes status='{w['status_value']}' to '{table}' "
                    f"but the CHECK constraint only allows {sorted(allowed)}. "
                    f"This insert/update will fail at the DB level OR drift if "
                    f"the constraint is later relaxed."
                ),
            })
    return issues, invalid


# ── Layer 2: Unreachable states ──────────────────────────────────────────────

# Inline pattern: .from(X).insert/upsert/update({ ..., status: someVar, ... })
VAR_STATUS_INLINE_RE = re.compile(
    r"""\.from\s*\(\s*['"`](?P<table>[a-z_][a-z0-9_]*)['"`]\s*\)
        (?:\s*\.\s*[a-zA-Z_]\w*\s*\([^)]*\))*?
        \s*\.\s*(?:insert|upsert|update)\s*\(\s*\{[^{}]*\bstatus\s*:\s*[a-zA-Z_]\w*""",
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)
# Payload pattern: .from(X).insert(payload) / .update(payload) where payload
# is a separate variable. We can't tell if payload contains status without
# a JS parser, so we treat ANY .insert/update(<identifier>) as wildcard for
# tables that have a status column. Conservative — false negatives prefer to
# stay quiet rather than spam.
VAR_STATUS_PAYLOAD_RE = re.compile(
    r"""\.from\s*\(\s*['"`](?P<table>[a-z_][a-z0-9_]*)['"`]\s*\)
        (?:\s*\.\s*[a-zA-Z_]\w*\s*\([^)]*\))*?
        \s*\.\s*(?:insert|upsert|update)\s*\(\s*[a-zA-Z_]\w*\s*[,)]""",
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)


def find_variable_status_writes(files: list[tuple[str, str]], has_status_col: set[str]) -> set[str]:
    """Tables where SOME write uses a variable for status (either inline
    `{status: someVar}` or a payload-variable insert/update). For these
    tables, the L2 check treats all allowed states as reachable — we
    cannot prove otherwise without a JS parser.
    """
    out: set[str] = set()
    for path, _ in files:
        if path.endswith(".py"): continue
        content = read_file(path) or ""
        for m in VAR_STATUS_INLINE_RE.finditer(content):
            out.add(m.group("table").lower())
        # Payload pattern only counts if the table has a status column —
        # otherwise the payload definitely doesn't include status.
        for m in VAR_STATUS_PAYLOAD_RE.finditer(content):
            t = m.group("table").lower()
            if t in has_status_col:
                out.add(t)
    return out


def check_unreachable_states(
    writes: list[dict],
    constraints: dict[str, set[str]],
    defaults: dict[str, str],
    variable_writers: set[str],
) -> tuple[list[dict], list[dict]]:
    """Every CHECK-allowed status should be reachable from at least one of:
    (a) a literal write, (b) the column DEFAULT, or (c) any variable write
    (which could supply any allowed value)."""
    written_per_table: dict[str, set[str]] = defaultdict(set)
    for w in writes:
        written_per_table[w["table"]].add(w["status_value"])
    # Add DEFAULTs as reachable
    for table, value in defaults.items():
        written_per_table[table].add(value)

    issues: list[dict] = []
    unreachable_report: list[dict] = []
    for table, allowed in constraints.items():
        # Variable writers = wildcard reachability; skip the check
        if table in variable_writers:
            continue
        unreachable = sorted(allowed - written_per_table.get(table, set())
                              - ACCEPTED_UNREACHABLE_STATES.get(table, set()))
        if unreachable:
            unreachable_report.append({
                "table":            table,
                "allowed_states":   sorted(allowed),
                "unreachable":      unreachable,
                "reachable_via":    sorted(written_per_table.get(table, set())),
            })
            issues.append({
                "check": "unreachable_states", "skip": True,
                "reason": (
                    f"Table '{table}' allows status values {unreachable} via CHECK "
                    f"constraint, but no consumer writes them (no literal, no DEFAULT, "
                    f"no variable update). Either remove from CHECK, wire the missing "
                    f"writer, or add to ACCEPTED_UNREACHABLE_STATES. "
                    f"Reachable via: {sorted(written_per_table.get(table, set()))}."
                ),
            })
    return issues, unreachable_report


# ── Layer 3: Unconstrained status columns ────────────────────────────────────

def check_unconstrained_status(constraints: dict[str, set[str]], has_status_col: set[str]) -> tuple[list[dict], list[dict]]:
    """Tables with a `status` column but no CHECK constraint allow any string."""
    unconstrained = sorted(has_status_col - set(constraints.keys()) - STATUS_COLUMN_IGNORE_TABLES)
    issues: list[dict] = []
    for table in unconstrained:
        issues.append({
            "check": "unconstrained_status", "skip": True,
            "reason": (
                f"Table '{table}' has a status column but no CHECK constraint listing "
                f"allowed values. Any string is accepted; state drift is inevitable. "
                f"Add `CHECK (status IN ('a', 'b', ...))` to the column definition or "
                f"as ALTER TABLE ... ADD CONSTRAINT."
            ),
        })
    return issues, unconstrained


# ── Layer 4: Writer-layer concentration (informational) ──────────────────────

def check_writer_concentration(writes: list[dict]) -> tuple[list[dict], list[dict]]:
    """For each table's status writes, count writers per platform layer.
    Pure information — no WARN."""
    by_table: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for w in writes:
        by_table[w["table"]][w["layer"]].add(w["path"])
    matrix: list[dict] = []
    for table, by_layer in by_table.items():
        matrix.append({
            "table":     table,
            "by_layer":  {k: len(v) for k, v in by_layer.items()},
            "total":     sum(len(v) for v in by_layer.values()),
        })
    matrix.sort(key=lambda m: -m["total"])
    return [], matrix


# ── Runner ────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "invalid_writes",
    "unreachable_states",
    "unconstrained_status",
    "writer_concentration",
]
CHECK_LABELS = {
    "invalid_writes":       "L1  Every literal status write matches the CHECK constraint        [WARN]",
    "unreachable_states":   "L2  Every CHECK-allowed status value is reachable from a writer    [WARN]",
    "unconstrained_status": "L3  Every table with a status column has a CHECK constraint        [WARN]",
    "writer_concentration": "L4  Status writers spread across platform layers (informational)   [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nState Machine Integrity (4-layer)"))
    print("=" * 60)

    constraints, has_status_col, defaults = load_status_constraints()
    files = list_writer_files()
    writes: list[dict] = []
    for path, layer in files:
        writes.extend(file_status_writes(path, layer))
    var_writers = find_variable_status_writes(files, has_status_col)

    print(f"  {len(constraints)} tables with status CHECK, "
          f"{len(has_status_col)} tables with a status column, "
          f"{len(defaults)} tables with status DEFAULT, "
          f"{len(var_writers)} tables with variable status updates, "
          f"{len(files)} writer files scanned, "
          f"{len(writes)} literal status writes found.\n")

    invalid_issues,    invalid_list   = check_invalid_writes(writes, constraints)
    unreachable_issues, unreachable_list = check_unreachable_states(
        writes, constraints, defaults, var_writers,
    )
    uncons_issues,     uncons_list    = check_unconstrained_status(constraints, has_status_col)
    layer_issues,      layer_matrix   = check_writer_concentration(writes)

    all_issues = invalid_issues + unreachable_issues + uncons_issues + layer_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if layer_matrix:
        print(f"\n{bold('STATUS WRITER MATRIX (per table)')}")
        print("  " + "-" * 56)
        for entry in layer_matrix[:12]:
            ls = ", ".join(f"{k}={v}" for k, v in sorted(entry["by_layer"].items()))
            print(f"  {entry['table']:<30}  total={entry['total']:<3}  {ls}")

    print(f"\n{bold('CHECK CONSTRAINTS DETECTED')}")
    print("  " + "-" * 56)
    for table in sorted(constraints.keys()):
        print(f"  {table:<30}  {sorted(constraints[table])}")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":           "state_machine_integrity",
        "total_checks":        total,
        "passed":              n_pass,
        "warned":              n_warn,
        "failed":              n_fail,
        "n_constraints":       len(constraints),
        "n_status_tables":     len(has_status_col),
        "n_literal_writes":    len(writes),
        "constraints":         {k: sorted(v) for k, v in constraints.items()},
        "invalid_writes":      invalid_list,
        "unreachable_states":  unreachable_list,
        "unconstrained":       uncons_list,
        "writer_matrix":       layer_matrix,
        "issues":              [i for i in all_issues if not i.get("skip")],
        "warnings":            [i for i in all_issues if i.get("skip")],
    }
    with open("state_machine_integrity_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
