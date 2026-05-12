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
    # Cross-cutting infra
    "hive_audit_log", "cmms_audit_log", "automation_log",
    "ai_rate_limits", "ai_audit_log",
    "external_sync", "integration_configs",
    "report_contacts",
    # Catalog / definition tables
    "achievement_definitions", "equipment_reading_templates",
    # Memory / brain tooling
    "agent_memory",
    # Migration metadata
    "schema_migrations",
    # Cache tables (no domain truth, just performance layers)
    "hive_analytics_cache",
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
    # Parse VALUES rows after the INSERT statement. The block may span many
    # lines and contain multiple tuples; capture each contract_id (first col).
    has_table = False
    for path in list_migrations():
        sql = read_file(path) or ""
        if "canonical_agent_contracts" not in sql: continue
        has_table = True
        m_insert = re.search(
            r"INSERT\s+INTO\s+(?:public\.)?canonical_agent_contracts[^;]*?VALUES\s*([\s\S]*?);",
            sql, re.IGNORECASE)
        if m_insert:
            for tup in re.finditer(r"\(\s*'([a-z_][a-z0-9_]*)'", m_insert.group(1)):
                registered_contracts.add(tup.group(1).lower())
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
        m_insert = re.search(
            r"INSERT\s+INTO\s+(?:public\.)?canonical_formulas[^;]*?VALUES\s*([\s\S]*?);",
            sql, re.IGNORECASE)
        if m_insert:
            for tup in re.finditer(r"\(\s*'([a-z_][a-z0-9_]*)'", m_insert.group(1)):
                registered_formulas.add(tup.group(1).lower())
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
        m_insert = re.search(
            r"INSERT\s+INTO\s+(?:public\.)?canonical_standards[^;]*?VALUES\s*([\s\S]*?);",
            sql, re.IGNORECASE)
        if m_insert:
            for tup in re.finditer(r"\(\s*'([a-z_0-9]+)'", m_insert.group(1)):
                registered_standards.add(tup.group(1).lower())

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
]

CHECK_LABELS = {
    "fuel_anchor":      "L1  Fuel: every new table registered in canonical_sources",
    "engine_anchor":    "L2  Engine: every v_*_truth + get_* RPC registered",
    "tier_a_anchor":    "L3  Tier A: worker_truth / skill_truth / assignment_truth anchor",
    "tier_c_anchor":    "L4  Tier C: brain output JSON Schemas (canonical_agent_contracts)",
    "formula_anchor":   "L5  Tier D formula: canonical_formulas registry",
    "standard_anchor":  "L6  Tier D standard: canonical_standards registry",
    "dashboard_anchor": "L7  Dashboard: canonical-consuming pages render a source chip",
}


def main():
    update_baseline = "--update-baseline" in sys.argv

    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nCanonical Anchor Gate (7-layer forward-anchor audit)"))
    print("=" * 60)

    layers = [
        check_fuel_anchor(),
        check_engine_anchor(),
        check_tier_a_anchor(),
        check_tier_c_anchor(),
        check_formula_anchor(),
        check_standard_anchor(),
        check_dashboard_anchor(),
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
