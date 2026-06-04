"""
Canonical Anchor Gate -- WorkHive Platform
==========================================
The forward-anchor counterpart to validate_silo_monitor.py.

The Silo Monitor catches drift AFTER it ships. This validator catches the
moment a new thing is INTRODUCED and asks: "which canonical layer does it
anchor into?" -- before it becomes a silo.

Fuel -> Engine -> Brain -> Dashboard -> Driver. Every layer has an anchor:

  Fuel        - raw tables, registered in canonical_sources
  Engine      - v_*_truth views / get_* RPCs, registered in canonical_sources
  Brain  A    - worker identity / skill / assignment canonicals (Tier A)
  Brain  C    - canonical_agent_contracts (Tier C, JSON Schema registry)
  Brain  D-f  - canonical_formulas registry (Tier D)
  Brain  D-s  - canonical_standards registry (Tier D)
  Dashboard   - renderSourceChip + formula_id/contract_id comment

This validator runs 7 layered checks, one per anchor point. Each check is
forward-only and pre-existing-debt allowlisted via a baseline lockfile:

  canonical_anchor_baseline.json

The baseline records the count of un-anchored items per layer at the time
of the last clean run. New commits can only REDUCE the counts -- the gate
FAILs if a layer's count goes up.

This is the same forward-only ratchet pattern used by
validate_validator_self_coverage and validate_ai_eval_coverage.

When Tier A, C, D registries don't exist yet (today), their layers are
SKIPped with a WARN and the registry filename is recorded. When the
registry lands, the layer flips to active and starts ratcheting from
baseline = current count.

Usage:  python validate_canonical_anchor.py
        python validate_canonical_anchor.py --update-baseline  (only after
        you have explicitly reduced an un-anchored count and want to lock
        the new ceiling in)

Output: canonical_anchor_report.json (per-layer counts, un-anchored items,
        recommendations).

Skills consulted: architect (anchor pattern), codebase-integrity (whole-
platform sweep), platform-guardian (forward-only ratchet, baseline
lockfile, non-blocking WARN on missing-registry layers).
"""
from __future__ import annotations

import json
import os
import re
import sys
import glob
from collections import defaultdict

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


# -- Paths ---------------------------------------------------------------------

MIGRATIONS_DIR = os.path.join("supabase", "migrations")
FUNCTIONS_DIR  = os.path.join("supabase", "functions")
PYTHON_API_DIR = "python-api"
BASELINE_FILE  = "canonical_anchor_baseline.json"

EXCLUDED_HTML_PATTERNS = ("-test.html", ".backup.html", "_backup.html", ".backup")
EXCLUDED_PATH_PARTS = (
    os.sep + "test-data-seeder" + os.sep,
    os.sep + "tools" + os.sep,
    os.sep + "video_marketing_app" + os.sep,
    os.sep + ".git" + os.sep,
    os.sep + "node_modules" + os.sep,
)


# -- Allowlist patterns --------------------------------------------------------
#
# Any source line carrying one of these comments is excused from the layer's
# count. The reason is required and shows up in code review, so the
# allowlist is self-policing (same pattern as // canonical-allow:).

ALLOW_PATTERNS = {
    "fuel":      re.compile(r"(?://|--|#)\s*canonical-allow:\s*(.+)"),
    "engine":    re.compile(r"(?://|--|#)\s*canonical-allow:\s*(.+)"),
    "tier_a":    re.compile(r"//\s*tier-a-allow:\s*(.+)"),
    "contract":  re.compile(r"//\s*contract-allow:\s*(.+)"),
    "formula":   re.compile(r"(?://|#)\s*formula-allow:\s*(.+)"),
    "standard":  re.compile(r"(?://|#)\s*standard-allow:\s*(.+)"),
    "dashboard": re.compile(r"//\s*dashboard-allow:\s*(.+)"),
    "capture":   re.compile(r"(?://|<!--)\s*capture-allow:\s*(.+)"),
}


# -- Tables that are NEVER expected to anchor as fuel canonicals ---------------
#
# Auth tables, config tables, audit logs that ARE already canonical etc.
# Same shape as silo_monitor's HOTSPOT_IGNORE_TABLES but for the
# fuel-registration check.

FUEL_ANCHOR_IGNORE_TABLES = {
    # Auth / Supabase internals
    "auth", "users", "auth_users", "auth_sessions",
    # The registry tables themselves
    "canonical_sources", "canonical_formulas",
    "canonical_standards", "canonical_agent_contracts",
    "canonical_capture_contracts",
    "canonical_capabilities",
    # Cross-cutting infra
    "hive_audit_log", "cmms_audit_log", "automation_log",
    "ai_rate_limits", "ai_audit_log",
    "external_sync", "integration_configs",
    "report_contacts",
    # Catalog / definition tables
    "achievement_definitions", "equipment_reading_templates",
    # Memory / brain tooling
    "agent_memory",
    "agent_followups",   # agent prospective-memory queue (server-side scheduler state; no fuel canonical)
    # Migration metadata
    "schema_migrations",
    # Cache tables (no domain truth, just performance layers)
    "hive_analytics_cache",
    # Personal owner-scoped documents (auth.uid-gated, NOT hive KPI/truth sources)
    "resume_documents", "resume_versions",
}


# -- Discovery helpers ---------------------------------------------------------

def list_html_pages() -> list[str]:
    out = []
    for path in sorted(glob.glob("*.html")):
        name = os.path.basename(path).lower()
        if any(p in name for p in EXCLUDED_HTML_PATTERNS):
            continue
        out.append(path)
    return out


def list_edge_functions() -> list[str]:
    out = []
    if os.path.isdir(FUNCTIONS_DIR):
        for d in sorted(os.listdir(FUNCTIONS_DIR)):
            idx = os.path.join(FUNCTIONS_DIR, d, "index.ts")
            if os.path.isfile(idx):
                out.append(idx)
    return out


def list_python_api_files() -> list[str]:
    out = []
    for path in sorted(glob.glob(os.path.join(PYTHON_API_DIR, "**", "*.py"), recursive=True)):
        if "__init__" in path:
            continue
        skip = False
        for part in EXCLUDED_PATH_PARTS:
            if part in path:
                skip = True; break
        if skip: continue
        out.append(path)
    return out


def list_migrations() -> list[str]:
    return sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")))


def line_is_allowed(line: str, layer_key: str) -> bool:
    """Return True if this line carries an explicit allowlist comment for
    the given layer."""
    pat = ALLOW_PATTERNS.get(layer_key)
    if not pat:
        return False
    return bool(pat.search(line))


def _extract_insert_pk_ids(sql: str, table_name: str) -> set[str]:
    """For each INSERT INTO {table_name} block in `sql`, extract the
    first quoted string of every VALUES tuple. This is the PK
    (capture_id / contract_id / formula_id / standard_id etc.).

    SQL-quote-aware: walks the text byte by byte tracking paren depth +
    whether we're inside a single-quoted string. SQL doubles single
    quotes inside strings ('' -> '). Semicolons / parens inside strings
    are ignored (the previous regex-based parser was broken by exactly
    this case).
    """
    out: set[str] = set()
    # Strip SQL comments first — apostrophes inside `--` line comments
    # (e.g. "doesn't") confuse the quote tracker downstream.
    sql = re.sub(r"--[^\n]*", "", sql)
    sql = re.sub(r"/\*[\s\S]*?\*/", "", sql)
    # Find every INSERT INTO {table_name} ... VALUES start
    start_re = re.compile(
        rf"INSERT\s+INTO\s+(?:public\.)?{re.escape(table_name)}\b[^;]*?\bVALUES\b",
        re.IGNORECASE,
    )
    for start_match in start_re.finditer(sql):
        i = start_match.end()
        n = len(sql)
        in_str = False
        # Walk forward, capturing the first '...' inside each top-level tuple.
        while i < n:
            ch = sql[i]
            if in_str:
                # Handle '' escape
                if ch == "'" and i + 1 < n and sql[i + 1] == "'":
                    i += 2; continue
                if ch == "'":
                    in_str = False
                i += 1; continue
            if ch == "'":
                in_str = True; i += 1; continue
            if ch == "(":
                # Parse one tuple: skip whitespace, expect '...'
                j = i + 1
                while j < n and sql[j] in " \t\n\r":
                    j += 1
                if j < n and sql[j] == "'":
                    k = j + 1
                    while k < n:
                        if sql[k] == "'" and k + 1 < n and sql[k + 1] == "'":
                            k += 2; continue
                        if sql[k] == "'": break
                        k += 1
                    pk = sql[j + 1:k]
                    if re.match(r"^[a-z_][a-z0-9_]*$", pk):
                        out.add(pk)
                # Skip past this tuple's closing paren, respecting strings inside.
                depth = 1
                k = i + 1
                in_s2 = False
                while k < n and depth > 0:
                    c2 = sql[k]
                    if in_s2:
                        if c2 == "'" and k + 1 < n and sql[k + 1] == "'":
                            k += 2; continue
                        if c2 == "'": in_s2 = False
                        k += 1; continue
                    if c2 == "'":  in_s2 = True;  k += 1; continue
                    if c2 == "(": depth += 1
                    elif c2 == ")": depth -= 1
                    k += 1
                i = k
                continue
            if ch == ";":
                # End of statement reached — done with this INSERT
                break
            # ON CONFLICT or other terminator keyword? Continue scanning for ;.
            i += 1
    return out


def has_allow_in_context(content: str, idx: int, layer_key: str, context_lines: int = 3) -> bool:
    """Return True if any of the surrounding context_lines (before or after
    idx) carries an allowlist comment for the layer.

    This lets you put `// formula-allow: ...` on the line above or below
    the offending line, not just on the same line.
    """
    # Walk back/forward N newlines from idx
    start = idx
    for _ in range(context_lines):
        prev = content.rfind("\n", 0, start)
        if prev < 0: break
        start = prev
    end = idx
    for _ in range(context_lines):
        nxt = content.find("\n", end + 1)
        if nxt < 0: break
        end = nxt
    return bool(ALLOW_PATTERNS[layer_key].search(content[start:end]))


# -- Layer 1: Fuel anchor -------------------------------------------------------

def check_fuel_anchor() -> dict:
    """Every new table in a migration should either:
      (a) be registered in canonical_sources, OR
      (b) carry a `-- canonical-allow: <reason>` line within 4 lines of the
          CREATE TABLE statement.

    Counts un-anchored tables. The baseline locks the maximum.
    """
    # Build the set of tables registered in canonical_sources (kind='table')
    registered_tables: set[str] = set()
    TUPLE_RE = re.compile(
        r"\(\s*'([a-z_][a-z0-9_]*)'\s*,\s*'(view|table|rpc)'\s*,"
        r"\s*'([a-z_][a-z0-9_]*)'\s*",
        re.IGNORECASE,
    )
    for path in list_migrations():
        sql = read_file(path) or ""
        if "canonical_sources" not in sql:
            continue
        for m in TUPLE_RE.finditer(sql):
            if m.group(2).lower() == "table":
                registered_tables.add(m.group(3).lower())

    # Build set of dropped tables (legacy retirees) — they shouldn't be
    # required to anchor since they no longer exist in production schema.
    dropped_tables: set[str] = set()
    DROP_RE = re.compile(
        r"DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:\"?public\"?\s*\.\s*)?\"?([a-z_][a-z0-9_]*)\"?",
        re.IGNORECASE,
    )
    for path in list_migrations():
        sql = read_file(path) or ""
        sql_stripped = re.sub(r"--[^\n]*", "", sql)
        sql_stripped = re.sub(r"/\*[\s\S]*?\*/", "", sql_stripped)
        for m in DROP_RE.finditer(sql_stripped):
            dropped_tables.add(m.group(1).lower())

    # Walk every migration for CREATE TABLE statements.
    # Handles: CREATE TABLE [IF NOT EXISTS] [["]public["]\.]["]table_name["]
    CREATE_RE = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:\"?public\"?\s*\.\s*)?\"?([a-z_][a-z0-9_]*)\"?",
        re.IGNORECASE,
    )
    # SQL keywords that can never be table names but might slip through if
    # regex partially matches. Defence in depth.
    SQL_KEYWORDS_DENY = {"if", "not", "exists", "above", "below",
                         "public", "table", "and", "or", "where", "select"}
    unanchored: list[dict] = []
    seen_tables: set[str] = set()
    for path in list_migrations():
        sql = read_file(path) or ""
        # Strip line comments + block comments so commentary like
        # "-- The CREATE TABLE above is safe" doesn't false-positive.
        sql_stripped = re.sub(r"--[^\n]*", "", sql)
        sql_stripped = re.sub(r"/\*[\s\S]*?\*/", "", sql_stripped)
        for m in CREATE_RE.finditer(sql_stripped):
            table = m.group(1).lower()
            if table in SQL_KEYWORDS_DENY: continue
            if table in seen_tables: continue
            seen_tables.add(table)
            if table in FUEL_ANCHOR_IGNORE_TABLES: continue
            if table in dropped_tables: continue
            if table in registered_tables: continue
            if has_allow_in_context(sql_stripped, m.start(), "fuel", context_lines=4): continue
            unanchored.append({
                "table":     table,
                "migration": os.path.basename(path),
            })
    return {
        "layer":           "fuel",
        "label":           "L1  Fuel anchor: every new table registered in canonical_sources",
        "n_registered":    len(registered_tables),
        "n_seen":          len(seen_tables),
        "n_unanchored":    len(unanchored),
        "unanchored":      unanchored,
    }


# -- Layer 2: Engine anchor ----------------------------------------------------

def check_engine_anchor() -> dict:
    """Every new view (CREATE VIEW) and every new RPC function (CREATE
    FUNCTION) should either:
      (a) follow the v_*_truth or get_* convention AND be registered in
          canonical_sources, OR
      (b) carry a `-- canonical-allow: <reason>` line within 4 lines of the
          definition.

    Reports the count of un-anchored engine objects.
    """
    registered_engine_names: set[str] = set()
    TUPLE_RE = re.compile(
        r"\(\s*'([a-z_][a-z0-9_]*)'\s*,\s*'(view|table|rpc)'\s*,"
        r"\s*'([a-z_][a-z0-9_]*)'\s*",
        re.IGNORECASE,
    )
    for path in list_migrations():
        sql = read_file(path) or ""
        if "canonical_sources" not in sql:
            continue
        for m in TUPLE_RE.finditer(sql):
            if m.group(2).lower() in ("view", "rpc"):
                registered_engine_names.add(m.group(3).lower())

    # Build set of dropped views (retired engine objects) — same pattern as
    # the fuel layer's dropped-tables exclusion.
    dropped_engine: set[str] = set()
    DROP_DEF_RE = re.compile(
        r"DROP\s+(VIEW|FUNCTION)\s+(?:IF\s+EXISTS\s+)?(?:\"?public\"?\s*\.\s*)?\"?([a-z_][a-z0-9_]*)\"?",
        re.IGNORECASE,
    )
    for path in list_migrations():
        sql = read_file(path) or ""
        sql_stripped = re.sub(r"--[^\n]*", "", sql)
        sql_stripped = re.sub(r"/\*[\s\S]*?\*/", "", sql_stripped)
        for m in DROP_DEF_RE.finditer(sql_stripped):
            dropped_engine.add(f"{m.group(1).lower()}:{m.group(2).lower()}")

    # CREATE VIEW and CREATE FUNCTION
    DEF_RE = re.compile(
        r"CREATE\s+(?:OR\s+REPLACE\s+)?(VIEW|FUNCTION)\s+(?:\"?public\"?\s*\.\s*)?\"?([a-z_][a-z0-9_]*)\"?",
        re.IGNORECASE,
    )
    unanchored: list[dict] = []
    seen: set[str] = set()
    for path in list_migrations():
        sql = read_file(path) or ""
        sql = re.sub(r"--[^\n]*", "", sql)
        sql = re.sub(r"/\*[\s\S]*?\*/", "", sql)
        for m in DEF_RE.finditer(sql):
            kind = m.group(1).lower()
            name = m.group(2).lower()
            key  = f"{kind}:{name}"
            if key in seen: continue
            seen.add(key)
            # Skip helper / trigger / internal fns -- they aren't engine reads
            if kind == "function":
                # Trigger fns end with _touch_updated_at / handle_* etc.
                # Engine reads are get_*, calc_*, v_*_truth.
                if not (name.startswith("get_") or name.startswith("calc_") or
                        name.startswith("compute_") or name.startswith("v_")):
                    continue
            if name in registered_engine_names: continue
            if key in dropped_engine: continue   # retired in a later migration
            # Trigger / internal-only views skipped via allowlist
            if has_allow_in_context(sql, m.start(), "engine", context_lines=4): continue
            unanchored.append({
                "kind":      kind,
                "name":      name,
                "migration": os.path.basename(path),
            })
    return {
        "layer":           "engine",
        "label":           "L2  Engine anchor: every v_*_truth view + get_* RPC registered",
        "n_registered":    len(registered_engine_names),
        "n_unanchored":    len(unanchored),
        "unanchored":      unanchored,
    }


# -- Layer 3: Tier A anchor (worker truths) ------------------------------------

def check_tier_a_anchor() -> dict:
    """Tier A introduces v_worker_truth + v_worker_skill_truth +
    v_worker_assignment_truth. Until the migrations land, this layer
    SKIPs with a note. Once any of the three is registered, the layer
    starts counting "code that should anchor into it but doesn't".

    Detection heuristic for code that should anchor into Tier A:
      - HTML/JS that joins worker_profiles + skill_badges (best-tech logic)
      - Python that combines workers + skills in a single derivation
      - Edge fns that read both tables
    """
    # Check whether any Tier A canonical is registered yet.
    # Accept both schema-qualified (public.) and unqualified CREATE VIEW.
    TIER_A_NAMES = ("v_worker_truth", "v_worker_skill_truth", "v_worker_assignment_truth")
    registered: set[str] = set()
    for path in list_migrations():
        sql = read_file(path) or ""
        for n in TIER_A_NAMES:
            if re.search(
                rf"CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+(?:public\.)?{n}\b",
                sql, re.IGNORECASE,
            ):
                registered.add(n)
    if not registered:
        return {
            "layer":           "tier_a",
            "label":           "L3  Tier A anchor: worker_truth / worker_skill_truth / worker_assignment_truth",
            "status":          "registry_missing",
            "note":            "Tier A canonicals not yet shipped. Layer is dormant until first migration.",
            "n_unanchored":    None,
            "unanchored":      [],
        }

    # If registered, count files that combine worker_profiles + skill_badges
    # without reading the Tier A view. Search files for both tokens.
    unanchored: list[dict] = []
    for path in list_html_pages() + list_edge_functions() + list_python_api_files():
        content = read_file(path) or ""
        has_workers = ("worker_profiles" in content) or ("skill_badges" in content)
        has_tier_a  = any(n in content for n in TIER_A_NAMES)
        # Heuristic: both tables referenced AND no Tier A view reference
        if "worker_profiles" in content and "skill_badges" in content and not has_tier_a:
            if "tier-a-allow:" in content: continue
            unanchored.append({
                "file": path,
            })
    return {
        "layer":           "tier_a",
        "label":           "L3  Tier A anchor: worker_truth / worker_skill_truth / worker_assignment_truth",
        "n_registered":    len(registered),
        "n_unanchored":    len(unanchored),
        "unanchored":      unanchored,
    }


# -- Layer 4: Tier C anchor (agent contracts) ----------------------------------

def check_tier_c_anchor() -> dict:
    """Tier C introduces canonical_agent_contracts (JSON Schema registry
    for brain outputs). Until the migration lands, this layer SKIPs.

    Once registered, the layer counts edge fns that return JSON to a
    consumer (HTML page) without a registered contract_id.

    Detection: edge fn returns `new Response(JSON.stringify({...}))` AND
    the response contains keys consumed elsewhere -- but no
    `// contract:<id>` comment in the file.
    """
    registered_contracts: set[str] = set()
    has_table = False
    for path in list_migrations():
        sql = read_file(path) or ""
        if "canonical_agent_contracts" not in sql: continue
        has_table = True
        registered_contracts |= _extract_insert_pk_ids(sql, "canonical_agent_contracts")
    if not has_table:
        return {
            "layer":           "tier_c",
            "label":           "L4  Tier C anchor: canonical_agent_contracts (brain output JSON Schemas)",
            "status":          "registry_missing",
            "note":            "Tier C registry not yet shipped. Layer is dormant until canonical_agent_contracts table lands.",
            "n_unanchored":    None,
            "unanchored":      [],
        }

    # Walk edge fns that produce JSON responses without a contract comment
    unanchored: list[dict] = []
    for path in list_edge_functions():
        content = read_file(path) or ""
        if "JSON.stringify" not in content: continue
        if "// contract:" in content or "contract-allow:" in content: continue
        # Heuristic: AI / orchestrator / brain output fn
        ai_signals = ("groq", "openai", "anthropic", "ai-gateway", "narrative",
                      "synthesis", "prescriptive", "predictive", "diagnostic")
        if any(s in content.lower() for s in ai_signals):
            unanchored.append({"file": path})
    return {
        "layer":           "tier_c",
        "label":           "L4  Tier C anchor: canonical_agent_contracts (brain output JSON Schemas)",
        "n_registered":    len(registered_contracts),
        "n_unanchored":    len(unanchored),
        "unanchored":      unanchored,
    }


# -- Layer 5: Tier D-f anchor (formula registry) -------------------------------

def check_formula_anchor() -> dict:
    """Tier D introduces canonical_formulas. Until it lands, this layer
    SKIPs. Once registered, counts every Python calc_* function that
    isn't tagged with a formula_id."""
    registered_formulas: set[str] = set()
    has_table = False
    for path in list_migrations():
        sql = read_file(path) or ""
        if "canonical_formulas" not in sql: continue
        has_table = True
        registered_formulas |= _extract_insert_pk_ids(sql, "canonical_formulas")
    # Always report the count of calc_* functions (whether tier D is shipped or not)
    CALC_RE = re.compile(r"^def\s+(calc_[a-z_0-9]+)\s*\(", re.MULTILINE)
    seen_funcs: list[tuple[str, str]] = []  # (fn_name, file_path)
    for path in list_python_api_files():
        content = read_file(path) or ""
        for m in CALC_RE.finditer(content):
            fn = m.group(1)
            seen_funcs.append((fn, path))

    if not has_table:
        return {
            "layer":           "tier_d_formula",
            "label":           "L5  Tier D formula anchor: canonical_formulas registry",
            "status":          "registry_missing",
            "note":            f"Tier D formula registry not yet shipped. {len(seen_funcs)} calc_* functions would need anchors when it does.",
            "n_calc_funcs":    len(seen_funcs),
            "n_unanchored":    None,
            "unanchored":      [],
        }
    # If registered: walk Python sources and count calc_* without a
    # `# formula: <id>` comment within 4 lines above the def
    unanchored: list[dict] = []
    for path in list_python_api_files():
        content = read_file(path) or ""
        for m in CALC_RE.finditer(content):
            fn = m.group(1)
            # Look at 4 lines preceding the def for `# formula: <id>`
            start = m.start()
            window_start = start
            for _ in range(4):
                prev = content.rfind("\n", 0, window_start)
                if prev < 0: break
                window_start = prev
            window = content[window_start:start]
            if re.search(r"#\s*formula:\s*([a-z_][a-z0-9_]*)", window):
                continue
            if "formula-allow:" in window:
                continue
            unanchored.append({"fn": fn, "file": path})
    return {
        "layer":           "tier_d_formula",
        "label":           "L5  Tier D formula anchor: canonical_formulas registry",
        "n_registered":    len(registered_formulas),
        "n_calc_funcs":    len(seen_funcs),
        "n_unanchored":    len(unanchored),
        "unanchored":      unanchored,
    }


# -- Layer 6: Tier D-s anchor (standards registry) -----------------------------

def check_standard_anchor() -> dict:
    """Tier D introduces canonical_standards. Until it lands, this layer
    SKIPs but reports the count of standards-string references the
    platform makes today, so we know how many will need anchors."""
    registered_standards: set[str] = set()
    has_table = False
    for path in list_migrations():
        sql = read_file(path) or ""
        if "canonical_standards" not in sql: continue
        has_table = True
        registered_standards |= _extract_insert_pk_ids(sql, "canonical_standards")

    # Reference scan: any of {ISO , SMRP, SAE JA, NFPA, ASME, ASTM, ANSI, IEC,
    # IESNA, ASHRAE, NEC, OSHA} followed by a number/code.
    STANDARD_REF_RE = re.compile(
        r"\b(ISO|SMRP|SAE\s+JA|NFPA|ASME|ASTM|ANSI|IEC|IESNA|ASHRAE|NEC|OSHA)\s*[\-:]?\s*(\d{2,5}(?:[\-:][\d\.]+)?)",
        re.IGNORECASE,
    )
    refs: dict[str, list[str]] = defaultdict(list)
    for path in list_html_pages() + list_edge_functions() + list_python_api_files():
        content = read_file(path) or ""
        for m in STANDARD_REF_RE.finditer(content):
            body = m.group(1).upper().replace(' ', '')
            num  = m.group(2).replace(':', '-').rstrip('.')
            # Normalise the same way canonical_standards.standard_id is built:
            # lowercase body + number, dashes/dots -> underscores.
            key = f"{body}_{num}".lower().replace('-', '_').replace('.', '_')
            if path not in refs[key]:
                refs[key].append(path)

    if not has_table:
        return {
            "layer":           "tier_d_standard",
            "label":           "L6  Tier D standard anchor: canonical_standards registry",
            "status":          "registry_missing",
            "note":            f"Tier D standards registry not yet shipped. {len(refs)} distinct standards already cited across {sum(len(v) for v in refs.values())} file-references.",
            "n_distinct_refs": len(refs),
            "n_total_refs":    sum(len(v) for v in refs.values()),
            "top_references":  sorted(
                [{"standard": k, "n_files": len(v), "sample_files": v[:3]} for k, v in refs.items()],
                key=lambda x: -x["n_files"],
            )[:10],
            "n_unanchored":    None,
            "unanchored":      [],
        }
    # If registered: count refs that don't match a registered_standards key
    unanchored: list[dict] = []
    for key, files in refs.items():
        if key in registered_standards: continue
        unanchored.append({"standard": key, "n_files": len(files), "sample_files": files[:3]})
    return {
        "layer":           "tier_d_standard",
        "label":           "L6  Tier D standard anchor: canonical_standards registry",
        "n_registered":    len(registered_standards),
        "n_unanchored":    len(unanchored),
        "unanchored":      unanchored,
    }


# -- Layer 7: Dashboard anchor (source chip + formula_id comment) --------------

def check_dashboard_anchor() -> dict:
    """Every render* function in an HTML page that consumes a canonical
    metric should either:
      (a) render a source chip via renderSourceChip(), OR
      (b) be inside a page that has a page-level #wh-source-chip, OR
      (c) carry a `// dashboard-allow: <reason>` comment.

    This piggy-backs on validate_kpi_chip_coverage but at a more granular
    (per-render-function) level for the canonical anchor study.
    """
    # Page-level: does the page have ANY source chip / renderSourceChip call?
    unanchored_pages: list[dict] = []
    for path in list_html_pages():
        content = read_file(path) or ""
        # Look for tile-rendering pattern indicators (render*, KPI tiles)
        if not re.search(r"\bfunction\s+render[A-Z]\w+\s*\(", content):
            continue
        # Does the page render any canonical view OR call an analytics RPC?
        consumes_canonical = (
            re.search(r"\.from\(['\"`]v_\w+_truth['\"`]\)", content) or
            re.search(r"\.rpc\(['\"`]get_\w+['\"`]\)", content) or
            "analytics-orchestrator" in content
        )
        if not consumes_canonical: continue
        # Does it render a source chip?
        has_chip = (
            "renderSourceChip(" in content or
            'id="wh-source-chip"' in content or
            "dashboard-allow:" in content
        )
        if has_chip: continue
        # Count render* functions in this page (the "n tiles missing anchor")
        n_render = len(re.findall(r"\bfunction\s+render[A-Z]\w+\s*\(", content))
        unanchored_pages.append({"page": path, "n_render_fns": n_render})

    return {
        "layer":           "dashboard",
        "label":           "L7  Dashboard anchor: canonical-consuming pages render a source chip",
        "n_unanchored":    len(unanchored_pages),
        "unanchored":      unanchored_pages,
    }


# -- Layer 8: Capture anchor (Tier F / Layer 0) -------------------------------

def check_capture_anchor() -> dict:
    """Tier F introduces canonical_capture_contracts — the registry of every
    input surface (form, voice, qr, import, upload, sensor, webhook, chat)
    that produces data landing in a fuel table.

    Until the migration lands, this layer SKIPs. Once registered, the
    layer counts HTML capture surfaces that look like they capture data
    but have no registered capture_id anchor in code.

    Detection heuristic — a page has a "capture surface" if it contains
    any of:
      - <form id="..."> with at least one <input>/<select>/<textarea>
      - getUserMedia / MediaRecorder (voice capture)
      - <video autoplay> or BarcodeDetector (qr / camera scan)
      - file upload <input type="file">
      - large textarea bound to a fetch insert

    A page is anchored if it carries any of:
      - // capture: <capture_id> or <!-- capture: <capture_id> -->
      - // capture-allow: <reason>
      - The page is in CAPTURE_ALLOW_PAGES (read-only dashboards etc.)
    """
    # Check whether the registry table is shipped yet
    registered_captures: set[str] = set()
    has_table = False
    for path in list_migrations():
        sql = read_file(path) or ""
        if "canonical_capture_contracts" not in sql: continue
        has_table = True
        registered_captures |= _extract_insert_pk_ids(sql, "canonical_capture_contracts")

    # Pages that legitimately have no captures (read-only / display-only)
    CAPTURE_ALLOW_PAGES = {
        "predictive.html",     # display-only risk dashboard
        "shift-brain.html",    # read-only top-of-shift summary
        "alert-hub.html",      # alerts list, no inputs
        "analytics-report.html",  # print-ready PDF
        "ph-intelligence.html",   # PH report viewer
        "platform-health.html",   # retired dev tooling
        "architecture.html",      # RETIRED 2026-05-13 — archival
        "symbol-gallery.html",    # RETIRED 2026-05-13 — archival
        "public-feed.html",       # read-only feed
        "project-report.html",    # print-ready PDF
        "audit-log.html",         # read-only audit trail viewer
        "achievements.html",      # display badges, no captures
    }

    if not has_table:
        return {
            "layer":           "capture",
            "label":           "L8  Capture anchor: canonical_capture_contracts (input surfaces)",
            "status":          "registry_missing",
            "note":            "Tier F capture registry not yet shipped. Layer is dormant until canonical_capture_contracts table lands.",
            "n_unanchored":    None,
            "unanchored":      [],
        }

    # Walk live HTML pages + voice/AI edge fns looking for capture surfaces
    unanchored: list[dict] = []
    for path in list_html_pages():
        name = os.path.basename(path)
        if name in CAPTURE_ALLOW_PAGES: continue

        content = read_file(path) or ""

        # Detect capture surfaces
        has_form = bool(re.search(r'<form\b[^>]*>', content, re.IGNORECASE))
        # Count <input> tags. Pages with >=10 inputs but no <form> wrapper
        # (e.g. engineering-design.html with 382 inputs across 74 calc forms
        # rendered by JS) are still capture surfaces — flag them.
        input_count = len(re.findall(r'<(input|select|textarea)\b', content, re.IGNORECASE))
        has_input = input_count > 0
        many_inputs_no_form = (input_count >= 10) and not has_form
        has_voice = bool(re.search(r'getUserMedia|MediaRecorder', content))
        has_qr = bool(re.search(r'BarcodeDetector|<video\s+[^>]*autoplay|jsqr|html5-qrcode', content, re.IGNORECASE))
        has_upload = bool(re.search(r'type=["\']file["\']', content, re.IGNORECASE))
        has_capture_surface = (has_form and has_input) or many_inputs_no_form or has_voice or has_qr or has_upload

        if not has_capture_surface: continue

        # Anchored if the page carries any capture-anchor marker
        has_anchor = (
            "// capture:" in content or
            "<!-- capture:" in content or
            "capture-allow:" in content
        )
        if has_anchor: continue

        # Build short list of which surfaces this page has (so the issue
        # message is actionable)
        surfaces = []
        if has_form and has_input: surfaces.append("form")
        if has_voice:              surfaces.append("voice")
        if has_qr:                 surfaces.append("qr")
        if has_upload:             surfaces.append("upload")

        unanchored.append({"page": name, "surfaces": surfaces})

    return {
        "layer":           "capture",
        "label":           "L8  Capture anchor: every input surface anchored to a capture_id",
        "n_registered":    len(registered_captures),
        "n_unanchored":    len(unanchored),
        "unanchored":      unanchored,
    }


# ─────────────────────────────────────────────────────────────────────
# L9 — Seed-to-Render Contract
# ─────────────────────────────────────────────────────────────────────
# Canonical anchoring (L1-L8) verifies that every formula has a registered
# standard + formula_id, every page has a source chip, etc. It does NOT
# verify the inputs the formula consumes are actually populated by any
# seeder. Walkthrough 2026-05-13 caught the OEE panel rendering empty for
# 6 months because:
#   - calc_oee reads production_output.quality_pct
#   - seeders/logbook.py writes production_output.{good_units, total_units}
#   - panel showed "No data" forever; canonical-anchor gate was green.
#
# L9 closes the loop. For each (KPI render fn ↔ formula ↔ seeder file),
# declare the inner-key paths the calc actually reads and the seeder must
# write. Static check: every required path string appears as a dict key
# inside the seeder file. Catches both top-level fields and nested JSONB
# keys (since calc fns access them by literal string).

SEED_RENDER_CONTRACT = [
    {
        "kpi":       "OEE",
        "formula":   "oee_iso_22400",
        "render_fn": "renderOEE",
        "seeder":    "test-data-seeder/seeders/logbook.py",
        # Each entry: a string the seeder MUST write SOMEWHERE as a dict key.
        # For nested JSONB shapes (production_output → {quality_pct OR
        # good_units/total_units}), use alt-groups: any key in the tuple
        # satisfies the contract (the calc has fallback derivation logic).
        "required": [
            ("downtime_hours",),
            ("quality_pct", "good_units"),  # quality OR raw counts
        ],
    },
    {
        "kpi":       "MTBF",
        "formula":   "mtbf_iso_14224",
        "render_fn": "renderMTBF",
        "seeder":    "test-data-seeder/seeders/logbook.py",
        "required": [
            ("maintenance_type",),
            ("created_at",),
            ("machine",),
        ],
    },
    {
        "kpi":       "MTTR",
        "formula":   "mttr_iso_14224",
        "render_fn": "renderMTTR",
        "seeder":    "test-data-seeder/seeders/logbook.py",
        "required": [
            ("downtime_hours",),
            ("closed_at",),
        ],
    },
    {
        "kpi":       "PM Compliance",
        "formula":   "pm_compliance_smrp",
        "render_fn": "renderPMCompliance",
        "seeder":    "test-data-seeder/seeders/pm.py",
        "required": [
            ("scope_item_id",),
            ("frequency",),
            ("completed_at",),
        ],
    },
    {
        "kpi":       "Parts consumption",
        "formula":   "parts_consumption_smrp",
        "render_fn": "renderPartsConsumption",
        "seeder":    "test-data-seeder/seeders/inventory.py",
        "required": [
            ("qty_change",),
        ],
    },
]


# ─────────────────────────────────────────────────────────────────────
# L10 — Header-strip ↔ Plain-Read Coverage Contract
# ─────────────────────────────────────────────────────────────────────
# Some pages declare a multi-fuel source chip at the top of the page
# (e.g. hive.html: "Open Work / PM overdue / Low stock" anchored to
# v_logbook_truth + v_pm_compliance_truth + v_inventory_items_truth)
# but their Plain-Read renderer only reads ONE of the declared fuels —
# so the verdict and the open-issues card silently ignore the others.
#
# Walkthrough 2026-05-13 caught the hive.html case: Card 3 "Open Issues"
# said "0" even though 18 work orders were open and another stat block
# on the same page showed them. The renderer was reading PM overdue
# only.  L9 catches "anchored but never seeded" — this is the sibling
# class: "anchored but never rolled up into the renderer."
#
# Registry-driven, same shape as L9: per-page, declare the canonical
# fuel names the source chip exposes and the Plain-Read renderer is
# expected to consume. Static check: every declared fuel name appears
# inside the renderer function's body (brace-balanced extraction).

HEADER_STRIP_CONTRACT = [
    {
        "page":      "hive.html",
        "renderer":  "loadSupervisorSummary",
        "fuels":     [
            "v_logbook_truth",          # open work orders
            "v_pm_compliance_truth",    # PM overdue   (via _pmOverdueCount, written by loadPMHealth from v_pm_compliance_truth → pm_scope_items_truth)
            "v_inventory_items_truth",  # low stock
        ],
        # An alternate fuel name accepted in lieu of the canonical view
        # (e.g. the page reads from a derived module-scope variable that
        # was filled by another fn that itself reads the canonical view).
        "alts": {
            "v_pm_compliance_truth": ["_pmOverdueCount"],
            "v_logbook_truth":       ["stat-open"],
        },
    },
]


def _extract_fn_body(src: str, fn_name: str) -> str:
    """Return the brace-balanced body of a JS function named fn_name.

    Handles `function NAME(`, `async function NAME(`, and
    `const NAME = (` declarations. Returns "" if not found.
    """
    patterns = [
        re.compile(rf"\basync\s+function\s+{re.escape(fn_name)}\s*\("),
        re.compile(rf"\bfunction\s+{re.escape(fn_name)}\s*\("),
        re.compile(rf"\bconst\s+{re.escape(fn_name)}\s*=\s*(?:async\s*)?\("),
    ]
    for pat in patterns:
        m = pat.search(src)
        if not m:
            continue
        idx = src.find("{", m.end())
        if idx < 0:
            continue
        depth = 0
        i = idx
        while i < len(src):
            c = src[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return src[idx:i+1]
            i += 1
    return ""


# ─────────────────────────────────────────────────────────────────────
# L11 — Insight Panel Anchor Coverage Contract
# ─────────────────────────────────────────────────────────────────────
# Sibling of L10. L10 catches "the page's top-level source chip declares
# a fuel that the Plain-Read renderer never reads." L11 catches the
# inverse: "a panel renders confident derived output (AI alerts,
# patterns, rollups) but the panel itself has no source chip, so the
# supervisor can't trace what triggered it."
#
# Walkthrough 2026-05-13 caught the Pattern Alerts panel on hive.html
# rendering cards labelled "4× repeat failure on MILL-001" with
# thresholds the supervisor couldn't see. The cards came from
# failure_signature_alerts (registered fuel ✓) but the panel had no
# source chip linking the rendered text to the 4 detection-rule
# formulas. Three of the four rules were also missing from
# canonical_formulas — fixed in migration 20260513000030.
#
# Registry-driven, same shape as L9 and L10. Each entry declares:
#   - page          : the HTML file
#   - panel_id      : the DOM id of the panel container
#   - chip_target_id: where the source chip is rendered (may equal
#                     panel_id when the chip is inline in the panel)
#   - required_chip_tokens: literal substrings that MUST appear in either
#                     the HTML around the chip element OR inside the
#                     populator JS function that fills it. Typically the
#                     canonical fuel name + a rule/standard label.
#   - populator     : (optional) JS fn name that fills the chip; checked
#                     for the chip tokens via brace-balanced extraction.

INSIGHT_PANEL_CONTRACT = [
    {
        "page":             "hive.html",
        "panel_id":         "pattern-alerts-panel",
        "chip_target_id":   "pattern-alerts-source-chip",
        "populator":        "loadPatternAlerts",
        "required_chip_tokens": [
            "failure_signature_alerts",   # canonical fuel
            "repeat_failure",              # rule formula
            "escalating_frequency",        # rule formula
            "multi_symptom",               # rule formula
            "missed_pm",                   # rule formula
            "ISO 14224",                   # standard
        ],
    },
    {
        "page":             "hive.html",
        "panel_id":         "maturity-stairway-card",
        "chip_target_id":   "stair-source-chip",
        "populator":        "renderMaturityStairway",
        "required_chip_tokens": [
            "v_maturity_truth",            # canonical view
            "compute_hive_readiness",      # RPC
            "Process",                     # one of the 5 dimensions
            "Resilience",                  # one of the 5 dimensions
        ],
    },
    {
        "page":             "hive.html",
        "panel_id":         "adoption-card",
        "chip_target_id":   "adoption-source-chip",
        "populator":        "loadAdoptionCard",
        "required_chip_tokens": [
            "hive_adoption_score",         # canonical fuel
            "compute_adoption_risk",       # RPC
            "healthy",                     # tier label
            "at_risk",                     # tier label
            "critical",                    # tier label
        ],
    },
    {
        "page":             "hive.html",
        "panel_id":         "benchmark-panel",
        "chip_target_id":   "benchmark-source-chip",
        "populator":        "loadBenchmarks",
        "required_chip_tokens": [
            "hive_benchmarks",             # own-hive feed
            "network_benchmarks",          # cross-hive feed
            "benchmark-compute",           # edge fn that recomputes
            "MTBF",                        # metric label
        ],
    },
    {
        "page":             "hive.html",
        "panel_id":         "kpipe-card",
        "chip_target_id":   "kpipe-source-chip",
        "populator":        "loadKnowledgePipeline",
        "required_chip_tokens": [
            "v_knowledge_freshness_truth", # canonical view
            "fault_knowledge",             # corpus
            "skill_knowledge",             # corpus
            "pm_knowledge",                # corpus
        ],
    },
    {
        "page":             "hive.html",
        "panel_id":         "todays-brief-panel",
        "chip_target_id":   "todays-brief-source-chip",
        "populator":        "loadTodaysBrief",
        "required_chip_tokens": [
            "ai_reports",                  # canonical fuel
            "failure_digest",              # report type
            "predictive",                  # report type
            "pm_overdue",                  # report type
        ],
    },
    {
        "page":             "hive.html",
        "panel_id":         "reliability-coach-panel",
        "chip_target_id":   "coach-source-chip",
        "populator":        "askCoach",
        "required_chip_tokens": [
            "ai-orchestrator",             # edge fn
            "v_logbook_truth",             # data slice
            "v_pm_compliance_truth",       # data slice
            "v_inventory_items_truth",     # data slice
            "canonical_agent_contracts",   # schema registry
        ],
    },
    {
        "page":             "hive.html",
        "panel_id":         "team-pulse-panel",
        "chip_target_id":   "team-pulse-source-chip",
        "populator":        "loadTeamPulse",
        "required_chip_tokens": [
            "v_logbook_truth",             # jobs today
            "v_pm_compliance_truth",       # PMs overdue (via _pmOverdueCount)
            "v_inventory_items_truth",     # stock issues
        ],
    },
    {
        "page":             "hive.html",
        "panel_id":         "handover-panel",
        "chip_target_id":   "handover-source-chip",
        "populator":        "generateHandover",
        "required_chip_tokens": [
            "v_logbook_truth",             # primary feed
            "v_pm_compliance_truth",       # PM context
            "since8h",                     # window literal
            "LOTO",                        # scan rule
        ],
    },
    # ── Page-level source chips (10-page sweep, 2026-05-14) ─────────────────
    # These gate the top-of-page source chip that the walkthrough found
    # missing on 10 of 16 pages. Same contract shape as insight panels —
    # the only difference is the chip_target_id is a page-level element
    # rather than a panel-level element.
    {
        "page":             "pm-scheduler.html",
        "panel_id":         "pm-source-chip",
        "chip_target_id":   "pm-source-chip",
        "populator":        "init",
        "required_chip_tokens": [
            "pm_assets", "pm_scope_items", "pm_completions",
            "Stair 2",
        ],
    },
    {
        "page":             "inventory.html",
        "panel_id":         "inventory-source-chip",
        "chip_target_id":   "inventory-source-chip",
        "populator":        "initData",
        "required_chip_tokens": [
            "inventory_items", "inventory_transactions",
            "qty_on_hand", "min_qty",
        ],
    },
    {
        "page":             "shift-brain.html",
        "panel_id":         "shift-source-chip",
        "chip_target_id":   "shift-source-chip",
        "populator":        "init",
        "required_chip_tokens": [
            "shift_plans", "v_risk_truth", "pm_scope_items",
        ],
    },
    {
        "page":             "dayplanner.html",
        "panel_id":         "dayplanner-source-chip",
        "chip_target_id":   "dayplanner-source-chip",
        "populator":        None,   # chip call is in anonymous DOMContentLoaded block
        "required_chip_tokens": [
            "schedule_items", "v_logbook_truth",
            "DILO",
        ],
    },
    {
        "page":             "skillmatrix.html",
        "panel_id":         "skillmatrix-source-chip",
        "chip_target_id":   "skillmatrix-source-chip",
        "populator":        "init",
        "required_chip_tokens": [
            "skill_profiles", "skill_badges",
            "Level 1-5",
        ],
    },
    {
        "page":             "achievements.html",
        "panel_id":         "achievements-source-chip",
        "chip_target_id":   "achievements-source-chip",
        "populator":        "init",
        "required_chip_tokens": [
            "worker_achievements", "achievement_xp_log",
            "XP this week",
        ],
    },
    {
        "page":             "project-manager.html",
        "panel_id":         "pm-mgr-source-chip",
        "chip_target_id":   "pm-mgr-source-chip",
        "populator":        None,   # chip call is in anonymous boot block before loadProjects
        "required_chip_tokens": [
            "projects", "project_items",
            "Active", "On Hold",
        ],
    },
    {
        "page":             "integrations.html",
        "panel_id":         "integrations-source-chip",
        "chip_target_id":   "integrations-source-chip",
        "populator":        "loadSyncConfigs",
        "required_chip_tokens": [
            "integration_configs", "external_sync",
            "SAP", "Maximo",
        ],
    },
    {
        "page":             "marketplace.html",
        "panel_id":         "marketplace-source-chip",
        "chip_target_id":   "marketplace-source-chip",
        "populator":        None,   # chip call is in anonymous DOMContentLoaded block
        "required_chip_tokens": [
            "marketplace_listings", "v_marketplace_sellers_truth",
            "KYB",
        ],
    },
    {
        "page":             "report-sender.html",
        "panel_id":         "report-sender-source-chip",
        "chip_target_id":   "report-sender-source-chip",
        "populator":        None,   # chip call is in anonymous DOMContentLoaded boot block
        "required_chip_tokens": [
            "ai_reports", "report_contacts",
            "Resend",
        ],
    },
]


def check_insight_panel_contract() -> dict:
    """L11 — every registered insight panel renders a source chip whose
    contents reference the panel's anchored fuel + rule/standard names.
    Catches "rendered confidently but unanchored" — the user-trust
    sibling of L9/L10."""
    unanchored: list[dict] = []
    for entry in INSIGHT_PANEL_CONTRACT:
        page = entry["page"]
        src  = read_file(page) or ""
        if not src:
            unanchored.append({
                "page":     page,
                "panel_id": entry["panel_id"],
                "reason":   f"Page file not found: {page}",
            })
            continue
        # 1. The panel container must exist.
        if f'id="{entry["panel_id"]}"' not in src:
            unanchored.append({
                "page":     page,
                "panel_id": entry["panel_id"],
                "reason":   f"Panel container `#{entry['panel_id']}` not found in {page}.",
            })
            continue
        # 2. The chip target slot must exist.
        if f'id="{entry["chip_target_id"]}"' not in src:
            unanchored.append({
                "page":     page,
                "panel_id": entry["panel_id"],
                "reason":   (
                    f"Source-chip slot `#{entry['chip_target_id']}` not found in "
                    f"{page}. Add a `<p id=\"{entry['chip_target_id']}\">` inside "
                    f"the panel and call renderSourceChip() in the populator."
                ),
            })
            continue
        # 3. The required chip tokens must appear inside the populator
        #    function (where renderSourceChip is called) or in the HTML
        #    if the chip is rendered inline. When populator is None the
        #    whole page source is searched (for chips wired in anonymous
        #    DOMContentLoaded blocks with no extractable function name).
        populator = entry.get("populator")
        haystack  = src
        if populator is not None:
            body = _extract_fn_body(src, populator)
            if not body:
                unanchored.append({
                    "page":      page,
                    "panel_id":  entry["panel_id"],
                    "populator": populator,
                    "reason":    f"Populator function `{populator}` not found in {page}.",
                })
                continue
            haystack = body
        # 4. renderSourceChip must actually be called.
        if "renderSourceChip" not in haystack:
            unanchored.append({
                "page":      page,
                "panel_id":  entry["panel_id"],
                "populator": populator,
                "reason":    (
                    f"`{populator or '(page-wide search of ' + page + ')'}` does not call renderSourceChip(). The "
                    f"panel container exists and the chip slot exists, but nothing "
                    f"populates the slot — supervisors see derived output with no "
                    f"trace to its fuel or rules."
                ),
            })
            continue
        # 5. Every required token must appear in the populator/HTML.
        missing = [t for t in entry["required_chip_tokens"] if t not in haystack]
        if missing:
            unanchored.append({
                "page":      page,
                "panel_id":  entry["panel_id"],
                "populator": populator,
                "missing":   missing,
                "reason":    (
                    f"Panel `#{entry['panel_id']}` chip on {page} is missing "
                    f"required anchor token(s): {missing}. The supervisor cannot "
                    f"trace rendered cards back to the fuel + rules that "
                    f"produced them. Add the missing tokens to the renderSourceChip "
                    f"call inside `{populator}` (notes/source/freshness fields)."
                ),
            })
    return {
        "layer":         "insight_panel",
        "label":         "L11 Insight panel: every registered panel renders an anchor chip",
        "n_contracts":   len(INSIGHT_PANEL_CONTRACT),
        "n_unanchored":  len(unanchored),
        "n_registered":  sum(len(e["required_chip_tokens"]) for e in INSIGHT_PANEL_CONTRACT),
        "unanchored":    unanchored,
    }


# ─────────────────────────────────────────────────────────────────────
# L12 — Journey Test Coverage
# ─────────────────────────────────────────────────────────────────────
# Every interactive tool page in LIVE_TOOL_PAGES should have a
# corresponding tests/journey-<slug>.spec.ts. Without it, a full
# end-to-end regression can go undetected — the smoke test only checks
# that the page loads; the journey test checks the actual user flow.
#
# Coverage audit 2026-05-14 found 7 of 21 LIVE_TOOL_PAGES with no
# journey test. This layer gates that gap going forward:
#   NEW pages added to LIVE_TOOL_PAGES → FAIL until a journey spec lands
#   EXEMPT list covers pages where a separate spec IS the journey test
#   (e.g. alert-hub is covered by journey-alerts.spec.ts).
#
# Mapping: some page slugs differ from the spec file name (pm-scheduler
# → journey-pm.spec.ts). JOURNEY_TEST_MAP resolves the alias.

JOURNEY_SLUG_MAP = {
    # page-slug (from LIVE_TOOL_PAGES) → journey spec stem
    "logbook":            "journey-logbook",
    "dayplanner":         "journey-dayplanner",
    "pm-scheduler":       "journey-pm",
    "hive":               "journey-hive",
    "inventory":          "journey-inventory",
    "skillmatrix":        "journey-skillmatrix",
    "engineering-design": "journey-engineering-design",
    "analytics":          "journey-analytics",
    "report-sender":      "journey-report-sender",
    "community":          "journey-community",
    "marketplace":        "journey-marketplace",
    "project-manager":    "journey-project-manager",
    "integrations":       "journey-marketplace",  # integrated in marketplace flow
    "ph-intelligence":    "journey-predictive",    # covered by predictive flow
    "predictive":         "journey-predictive",
    "ai-quality":         "journey-ai-quality",
    "plant-connections":  "journey-plant-connections",
    "achievements":       "journey-achievements",
    "asset-hub":          "journey-asset-hub",
    "shift-brain":        "journey-shift-brain",
    "alert-hub":          "journey-alerts",
    "voice-journal":      "journey-voice-journal",
    # Print/static views — journey not required (no interactive user flow)
    "analytics-report":   "__exempt__",
    "project-report":     "__exempt__",
    "assistant":          "__exempt__",  # AI chat covered by voice-journal pattern
    "audit-log":          "journey-audit-log",
}

TESTS_DIR = "tests"


def check_journey_coverage() -> dict:
    """L12 — every LIVE_TOOL_PAGE has a journey test spec. Catches the
    coverage gap where only smoke tests exist. New pages added to
    LIVE_TOOL_PAGES FAIL until a journey-<slug>.spec.ts lands."""
    # Load LIVE_TOOL_PAGES from validate_assistant.py dynamically so
    # the two registries stay in sync.
    assistant_src = read_file("validate_assistant.py") or ""
    m = re.search(r"LIVE_TOOL_PAGES\s*=\s*\[([^\]]*)\]", assistant_src, re.DOTALL)
    live_pages: list[str] = []
    if m:
        live_pages = re.findall(r"[\"']([\w-]+)[\"']", m.group(1))

    unanchored: list[dict] = []
    for slug in live_pages:
        spec_stem = JOURNEY_SLUG_MAP.get(slug)
        if spec_stem == "__exempt__":
            continue   # print/static view — no journey required

        if spec_stem is None:
            # Known TODO — flag as un-anchored (forces a decision)
            spec_path = os.path.join(TESTS_DIR, f"journey-{slug}.spec.ts")
            unanchored.append({
                "page":  f"{slug}.html",
                "spec":  spec_path,
                "reason": (
                    f"No journey test for '{slug}.html' — "
                    f"add tests/{spec_path} covering the main user flow. "
                    f"Smoke tests only catch load errors; journey tests catch "
                    f"silent-fail regressions in the write / read path."
                ),
            })
            continue

        spec_path = os.path.join(TESTS_DIR, f"{spec_stem}.spec.ts")
        if not os.path.isfile(spec_path):
            unanchored.append({
                "page":  f"{slug}.html",
                "spec":  spec_path,
                "reason": (
                    f"Journey spec '{spec_path}' registered but file not found. "
                    f"Create the spec or update JOURNEY_SLUG_MAP."
                ),
            })

    return {
        "layer":        "journey_coverage",
        "label":        "L12 Journey: every LIVE_TOOL_PAGE has a journey-*.spec.ts",
        "n_pages":      len(live_pages),
        "n_unanchored": len(unanchored),
        "n_registered": len(live_pages) - len(unanchored),
        "unanchored":   unanchored,
    }


def check_header_strip_contract() -> dict:
    """L10 — every fuel declared in a page's source chip is referenced
    by the page's Plain-Read renderer function. Catches "anchored but
    not rolled up" — the verdict/card sibling of the L9 bug class."""
    unanchored: list[dict] = []
    for entry in HEADER_STRIP_CONTRACT:
        page    = entry["page"]
        rfn     = entry["renderer"]
        fuels   = entry["fuels"]
        alts    = entry.get("alts", {})
        src     = read_file(page) or ""
        if not src:
            unanchored.append({
                "page":     page,
                "renderer": rfn,
                "reason":   f"Page file not found: {page}",
            })
            continue
        body = _extract_fn_body(src, rfn)
        if not body:
            unanchored.append({
                "page":     page,
                "renderer": rfn,
                "reason":   f"Renderer function `{rfn}` not found in {page}",
            })
            continue
        missing: list[str] = []
        for fuel in fuels:
            if fuel in body:
                continue
            # Alt names (derived state) — accept any one of them.
            alt_list = alts.get(fuel, [])
            if any(a in body for a in alt_list):
                continue
            missing.append(fuel)
        if missing:
            unanchored.append({
                "page":     page,
                "renderer": rfn,
                "missing":  missing,
                "reason":   (
                    f"`{page}` source chip declares fuel(s) {missing} but "
                    f"renderer `{rfn}()` does not reference them (directly or "
                    f"via a registered alt). The verdict and Plain-Read cards "
                    f"will silently ignore those fuels — same bug class as "
                    f"L9 but on the render side. Either roll the fuel into "
                    f"the renderer, drop it from the source chip, or "
                    f"register an alt in HEADER_STRIP_CONTRACT['alts']."
                ),
            })
    return {
        "layer":         "header_strip",
        "label":         "L10 Header-strip: every source-chip fuel referenced by Plain-Read renderer",
        "n_contracts":   len(HEADER_STRIP_CONTRACT),
        "n_unanchored":  len(unanchored),
        "n_registered":  sum(len(e["fuels"]) for e in HEADER_STRIP_CONTRACT),
        "unanchored":    unanchored,
    }


def check_seed_render_contract() -> dict:
    """L9 — every KPI render path's required inputs are actually written
    by the named seeder file. Catches the bug class where the calc and
    seeder disagree on field names (e.g. quality_pct vs good_units)."""
    unanchored: list[dict] = []
    for entry in SEED_RENDER_CONTRACT:
        # Relative path off the repo root (cwd convention used elsewhere
        # in this file — see MIGRATIONS_DIR / FUNCTIONS_DIR).
        seeder_src = read_file(entry["seeder"]) or ""
        if not seeder_src:
            unanchored.append({
                "kpi":    entry["kpi"],
                "seeder": entry["seeder"],
                "reason": "Seeder file not found.",
            })
            continue
        missing_paths: list[str] = []
        for alt_group in entry["required"]:
            # alt_group is a tuple of strings — any one of them in the seeder
            # source as a dict key (quoted) satisfies the requirement.
            satisfied = False
            for key in alt_group:
                if (f'"{key}"' in seeder_src) or (f"'{key}'" in seeder_src):
                    satisfied = True
                    break
            if not satisfied:
                missing_paths.append(" OR ".join(alt_group))
        if missing_paths:
            unanchored.append({
                "kpi":     entry["kpi"],
                "formula": entry["formula"],
                "seeder":  entry["seeder"],
                "missing": missing_paths,
                "reason":  (
                    f"`{entry['kpi']}` panel renders formula `{entry['formula']}` "
                    f"but `{entry['seeder']}` does not write required field(s): "
                    f"{', '.join(missing_paths)}. The panel will render an empty "
                    f"state forever even though the formula is anchored. Update the "
                    f"seeder OR update the SEED_RENDER_CONTRACT alt-group if the "
                    f"calc has a fallback shape."
                ),
            })
    return {
        "layer":         "seed_render",
        "label":         "L9  Seed-Render: every KPI's required inputs are seeded",
        "n_contracts":   len(SEED_RENDER_CONTRACT),
        "n_unanchored":  len(unanchored),
        "unanchored":    unanchored,
    }


# -- Baseline ratchet ---------------------------------------------------------

def load_baseline() -> dict:
    if not os.path.exists(BASELINE_FILE):
        return {}
    try:
        with open(BASELINE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_baseline(baseline: dict):
    with open(BASELINE_FILE, "w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2, default=str)


# -- Main ----------------------------------------------------------------------

CHECK_NAMES = [
    "fuel_anchor",
    "engine_anchor",
    "tier_a_anchor",
    "tier_c_anchor",
    "formula_anchor",
    "standard_anchor",
    "dashboard_anchor",
    "capture_anchor",
    "seed_render_anchor",
    "header_strip_anchor",
    "insight_panel_anchor",
    "journey_coverage",
]

CHECK_LABELS = {
    "fuel_anchor":      "L1  Fuel: every new table registered in canonical_sources",
    "engine_anchor":    "L2  Engine: every v_*_truth + get_* RPC registered",
    "tier_a_anchor":    "L3  Tier A: worker_truth / skill_truth / assignment_truth anchor",
    "tier_c_anchor":    "L4  Tier C: brain output JSON Schemas (canonical_agent_contracts)",
    "formula_anchor":   "L5  Tier D formula: canonical_formulas registry",
    "standard_anchor":  "L6  Tier D standard: canonical_standards registry",
    "dashboard_anchor": "L7  Dashboard: canonical-consuming pages render a source chip",
    "capture_anchor":   "L8  Capture: every input surface anchored to canonical_capture_contracts",
    "seed_render_anchor":   "L9  Seed-Render: every KPI's required inputs are seeded",
    "header_strip_anchor":  "L10 Header-strip: every source-chip fuel rolled up by Plain-Read renderer",
    "insight_panel_anchor": "L11 Insight panel: every registered panel renders an anchor chip",
    "journey_coverage":     "L12 Journey: every LIVE_TOOL_PAGE has a journey-*.spec.ts",
}


def main():
    update_baseline = "--update-baseline" in sys.argv

    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nCanonical Anchor Gate (12-layer forward-anchor audit)"))
    print("=" * 60)

    layers = [
        check_fuel_anchor(),
        check_engine_anchor(),
        check_tier_a_anchor(),
        check_tier_c_anchor(),
        check_formula_anchor(),
        check_standard_anchor(),
        check_dashboard_anchor(),
        check_capture_anchor(),
        check_seed_render_contract(),
        check_header_strip_contract(),
        check_insight_panel_contract(),
        check_journey_coverage(),
    ]

    baseline = load_baseline()
    issues: list[dict] = []

    print(f"  Layers checked: {len(layers)}\n")

    # Per-layer status row + ratchet check
    for L in layers:
        layer_key = L["layer"]
        check_name = (
            "fuel_anchor" if layer_key == "fuel" else
            "engine_anchor" if layer_key == "engine" else
            "tier_a_anchor" if layer_key == "tier_a" else
            "tier_c_anchor" if layer_key == "tier_c" else
            "formula_anchor" if layer_key == "tier_d_formula" else
            "standard_anchor" if layer_key == "tier_d_standard" else
            "capture_anchor" if layer_key == "capture" else
            "seed_render_anchor" if layer_key == "seed_render" else
            "header_strip_anchor" if layer_key == "header_strip" else
            "insight_panel_anchor" if layer_key == "insight_panel" else
            "journey_coverage"     if layer_key == "journey_coverage" else
            "dashboard_anchor"
        )
        if L.get("status") == "registry_missing":
            # Layer dormant -- SKIP with note
            issues.append({
                "check": check_name, "skip": True,
                "reason": f"[{layer_key}] {L['note']}",
            })
            continue
        n_un = L["n_unanchored"]
        prior = baseline.get(check_name, n_un)  # First run: baseline = current count
        if n_un > prior:
            issues.append({
                "check": check_name, "skip": False,
                "reason": (
                    f"[{layer_key}] count went UP: {prior} -> {n_un} un-anchored items. "
                    f"New items: {[u for u in L['unanchored'] if u not in baseline.get('details', {}).get(check_name, [])][:3]}"
                ),
            })
        # baseline.json gets updated only with --update-baseline
        if update_baseline or check_name not in baseline:
            baseline[check_name] = n_un
            baseline.setdefault("details", {})[check_name] = L["unanchored"][:50]

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)

    # Scoreboard
    print(f"\n{bold('CANONICAL ANCHOR SCOREBOARD')}")
    print("  " + "-" * 60)
    print("  {:<30}  {:>10}  {:>10}".format("layer", "registered", "un-anchored"))
    print("  " + "-" * 60)
    for L in layers:
        reg = L.get("n_registered", "-")
        un  = L.get("n_unanchored")
        if un is None:
            un_str = "(dormant)"
        else:
            un_str = str(un)
        extra = ""
        if L["layer"] == "tier_d_formula" and "n_calc_funcs" in L:
            extra = f"  ({L['n_calc_funcs']} calc_* fns)"
        if L["layer"] == "tier_d_standard" and "n_total_refs" in L:
            extra = f"  ({L['n_total_refs']} refs)"
        print("  {:<30}  {:>10}  {:>10}{}".format(L["layer"][:30], str(reg), un_str, extra))

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    # Persist baseline + report
    save_baseline(baseline)
    report = {
        "validator":     "canonical_anchor",
        "total_checks":  total,
        "passed":        n_pass,
        "warned":        n_warn,
        "failed":        n_fail,
        "layers":        layers,
        "issues":        [i for i in issues if not i.get("skip")],
        "warnings":      [i for i in issues if i.get("skip")],
    }
    with open("canonical_anchor_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
