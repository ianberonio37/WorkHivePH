"""
Silo Monitor -- WorkHive Platform
=================================
Architectural validator that ensures the platform's interconnected web of
functions and tools converges on canonical sources rather than splintering
into parallel implementations.

The complementary validator validate_canonical_sources.py checks REGISTRY
HEALTH (L1: table declared, writes locked, seeds present). This one checks
CONSUMER ALIGNMENT: every system that needs a domain reads it from the same
place, and every registered canonical actually has a consumer.

Layer 1 -- Canonical drift                                                [WARN]
  For each registered v_*_truth view, identify HTML pages and edge fns
  that read an underlying table (rcm_fmea_modes, asset_risk_scores, etc.)
  when the canonical view exists for that domain. Drift sites get listed
  but not failed -- some are legitimate writers/owners that need raw access.
  The signal is the RATIO: drift_readers > canonical_readers means the
  canonical is being bypassed by most consumers.

Layer 2 -- Orphan canonicals                                              [WARN]
  Registered canonicals with zero consumers across the platform. Either the
  consumer was never wired (the silo we just identified for Reliability) or
  the canonical is dead and should be retired from the registry.

Layer 3 -- Unregistered hotspots                                          [WARN]
  Underlying tables read by 8+ distinct files with no canonical entry.
  Truth-scattering candidates -- adding a v_X_truth view + canonical_sources
  registration for these would prevent the next Reliability-style silo.

Layer 4 -- Cross-system coverage matrix                                   [INFO]
  For each canonical: which platform layer reads it? (HTML page / edge fn /
  python-api). Highlights "data only one layer can see" -- the silo pattern
  the canonical_sources initiative was built to prevent.

Skills consulted: architect (canonical pattern + drift defence), data-engineer
(narrow lookups + canonical view convention), codebase-integrity (whole-platform
sweep, registry-style audits), platform-guardian (non-blocking informational
report -- silo issues are architectural, not production-blocking).

Usage:  python validate_silo_monitor.py
Output: silo_monitor_report.json (full matrix + drift sites for human review)
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

MIGRATIONS_DIR  = os.path.join("supabase", "migrations")
FUNCTIONS_DIR   = os.path.join("supabase", "functions")
PYTHON_API_DIR  = "python-api"

# Files we treat as consumers (i.e., places where reading from a table or view
# represents production code-path, not a definition or seeder).
EXCLUDED_HTML_PATTERNS = ("-test.html", ".backup.html", "_backup.html", ".backup")

# A table read in any of these dirs/files is NOT a consumer -- it's
# definition / seeding / validation infrastructure. We exclude them.
EXCLUDED_PATH_PARTS = (
    os.sep + "test-data-seeder" + os.sep,
    os.sep + "tools" + os.sep,
    os.sep + "video_marketing_app" + os.sep,
    os.sep + ".git" + os.sep,
    os.sep + "node_modules" + os.sep,
)

# Registry migrations are auto-discovered: any *.sql under MIGRATIONS_DIR
# that contains an INSERT INTO canonical_sources block contributes
# registrations. Hardcoding the list here would silently miss new ones.

# Tables that are widely read for legitimate reasons unrelated to canonical
# domains -- excluding them from the unregistered-hotspot scan keeps the signal
# focused on truth-scattering candidates.
HOTSPOT_IGNORE_TABLES = {
    "hives", "hive_members", "worker_profiles", "auth", "users",
    "ai_rate_limits",        # registered as ai_rate_limit; alias in seed
    "ai_reports",            # report storage, not a domain truth
    "automation_log",        # registered domain
    "hive_audit_log",        # registered domain
    "cmms_audit_log",        # registered domain
    "report_contacts",       # config table
    "external_sync",         # CMMS link metadata
    "integration_configs",
    "achievement_definitions",
    "equipment_reading_templates",
    "canonical_sources",     # the registry itself
}

UNREGISTERED_HOTSPOT_THRESHOLD = 8   # files reading the same table

# Domains that are LEGITIMATELY consumed by exactly one platform layer.
# Declaring them here removes the L4 WARN; the monitor still tracks the
# coverage matrix so a future change can prove the exception is still valid.
# Each entry should include a one-sentence justification so a future maintainer
# can decide whether the exception still holds.
ACCEPTED_SINGLE_LAYER_DOMAINS = {
    "community_thread":   "Pure UI surface — community feed reads/writes are HTML-driven. Will gain an edge consumer when the deferred B2 weekly digest email lands.",
    "hive_audit_log":     "Audit trail viewer is HTML-only by design; edge fns write to it but don't read back.",
    "ai_rate_limit":      "Internal rate-limit infrastructure for AI edge fns — no UI use case.",
}


# ── Discovery: load registered canonicals from migrations ─────────────────────

def load_registered_canonicals() -> list[dict]:
    """Parse INSERT INTO canonical_sources blocks across ALL migrations.

    Returns list of {domain, kind, source_name, owner_skill, freshness}.
    Scans the migrations directory dynamically so new canonical
    registrations are picked up without code changes here.
    """
    out: list[dict] = []
    # Block-bounded matching is unreliable because description text in
    # canonical_sources INSERTs contains literal semicolons (e.g. "approved
    # rows only; joins asset_nodes for ..."). Instead, when we see a
    # canonical_sources mention in a migration, we scan the WHOLE file for
    # VALUES tuples whose first column is a kind ('view'|'table'|'rpc').
    KINDS = ("view", "table", "rpc")
    TUPLE_RE = re.compile(
        r"\(\s*'([a-z_][a-z0-9_]*)'\s*,\s*'(view|table|rpc)'\s*,"
        r"\s*'([a-z_][a-z0-9_]*)'\s*,\s*'([a-z0-9_\-]+)'\s*,\s*'([a-z0-9_]+)'",
        re.IGNORECASE,
    )
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = read_file(path) or ""
        if "canonical_sources" not in sql:
            continue
        for m in TUPLE_RE.finditer(sql):
            out.append({
                "domain":      m.group(1),
                "kind":        m.group(2),
                "source_name": m.group(3),
                "owner_skill": m.group(4),
                "freshness":   m.group(5),
            })
    # Dedupe by domain (later migrations override earlier ones if they UPSERT
    # a redefinition; the registry table itself is keyed on domain).
    by_domain: dict[str, dict] = {}
    for r in out:
        by_domain[r["domain"]] = r
    return list(by_domain.values())


# ── Discovery: parse view definitions to find underlying tables ───────────────

def _depth_at(body: str, idx: int) -> int:
    """Return paren depth at position idx within body (top-level = 0)."""
    depth = 0
    for ch in body[:idx]:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
    return depth


def load_view_definitions() -> dict[str, dict[str, set[str]]]:
    """Returns { view_name: {"primary": set(...), "joined": set(...)} }.

    The PRIMARY table is the one in the OUTERMOST FROM clause — i.e., the
    FROM at paren depth 0. Scalar subqueries like
    `(SELECT count(*) FROM logbook ...)` appear early in many of our views
    (v_asset_truth has 4) but they are paren-depth 1+; we exclude them from
    primary candidates and treat them as joined.

    JOINed tables (or any FROM/JOIN at depth > 0) are joined-only: they
    contribute columns but reading them directly is not drift — they belong
    to a different domain.

    Skips chained views (FROM v_other_view) so we land on leaf tables.
    """
    views: dict[str, dict[str, set[str]]] = {}
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = read_file(path) or ""
        sql = re.sub(r"--[^\n]*", "", sql)
        for m in re.finditer(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+(?:public\.)?(\w+)\s+AS"
            r"([\s\S]*?)(?=;\s*(?:CREATE|GRANT|COMMENT|ALTER|INSERT|--|\Z))",
            sql, re.IGNORECASE,
        ):
            view_name = m.group(1).lower()
            body      = m.group(2)
            primary: set[str] = set()
            joined:  set[str] = set()
            for tm in re.finditer(
                r"\b(FROM|JOIN)\s+(?:public\.)?(\w+)\b",
                body, re.IGNORECASE,
            ):
                kw    = tm.group(1).upper()
                t     = tm.group(2).lower()
                depth = _depth_at(body, tm.start())
                if t.startswith("v_") or t in ("select", "values", "lateral"):
                    continue
                if kw == "FROM" and depth == 0 and not primary:
                    primary.add(t)
                else:
                    joined.add(t)
            views[view_name] = {"primary": primary, "joined": joined}
    return views


# ── Discovery: walk consumer files and collect db.from('table') references ────

# Captures both db.from('name') and db.from("name") in HTML/JS, edge fn TS,
# and supabase-py client.table("name") in Python files. Keeps the alphanumeric
# table-name guard so we don't match dynamic identifiers.
TABLE_REF_RE_JSTS = re.compile(r"""\.from\s*\(\s*['"`]([a-z_][a-z0-9_]*)['"`]""", re.IGNORECASE)
TABLE_REF_RE_PY   = re.compile(r"""\.table\s*\(\s*['"]([a-z_][a-z0-9_]*)['"]""", re.IGNORECASE)


def _path_excluded(path: str) -> bool:
    for part in EXCLUDED_PATH_PARTS:
        if part in path:
            return True
    return False


def list_consumer_files() -> list[tuple[str, str]]:
    """Returns list of (file_path, layer) tuples where layer is one of
    'html', 'edge', 'python_api', 'shared_js'."""
    out: list[tuple[str, str]] = []
    # HTML pages at project root
    for path in sorted(glob.glob("*.html")):
        name = os.path.basename(path).lower()
        if any(p in name for p in EXCLUDED_HTML_PATTERNS):
            continue
        out.append((path, "html"))
    # Shared JS at project root (excluding minified / vendor)
    for path in sorted(glob.glob("*.js")):
        if path.endswith(".min.js"):
            continue
        out.append((path, "shared_js"))
    # Edge functions
    if os.path.isdir(FUNCTIONS_DIR):
        for d in sorted(os.listdir(FUNCTIONS_DIR)):
            idx = os.path.join(FUNCTIONS_DIR, d, "index.ts")
            if os.path.isfile(idx):
                out.append((idx, "edge"))
    # Python API (excluding __init__ and tests)
    for path in sorted(glob.glob(os.path.join(PYTHON_API_DIR, "**", "*.py"), recursive=True)):
        if "__init__" in path or _path_excluded(path):
            continue
        out.append((path, "python_api"))
    return out


def file_table_refs(path: str) -> set[str]:
    content = read_file(path) or ""
    refs = set()
    if path.endswith(".py"):
        refs |= set(m.group(1).lower() for m in TABLE_REF_RE_PY.finditer(content))
    else:
        refs |= set(m.group(1).lower() for m in TABLE_REF_RE_JSTS.finditer(content))
    return refs


# ── Layer assemblers ─────────────────────────────────────────────────────────

def build_consumer_index(files: list[tuple[str, str]]) -> dict[str, dict]:
    """Returns { table_name: {"readers": [(path, layer)], "layers": {layer: count}} }"""
    idx: dict[str, dict] = defaultdict(lambda: {"readers": [], "layers": defaultdict(int)})
    for path, layer in files:
        for table in file_table_refs(path):
            idx[table]["readers"].append((path, layer))
            idx[table]["layers"][layer] += 1
    # Convert defaultdicts to plain dicts for JSON safety
    return {k: {"readers": v["readers"], "layers": dict(v["layers"])} for k, v in idx.items()}


# ── Layer 1: drift ────────────────────────────────────────────────────────────

def check_canonical_drift(
    canonicals: list[dict],
    views: dict[str, dict[str, set[str]]],
    consumer_idx: dict[str, dict],
) -> tuple[list[dict], list[dict]]:
    """For each view-backed canonical, count canonical readers vs PRIMARY-
    table readers. Joined-only tables are excluded from drift (they belong
    to a different domain — reading them is not necessarily wrong).

    Issue WARN if drift outweighs canonical 2:1 OR if canonical readers = 0.
    """
    issues: list[dict] = []
    domain_report: list[dict] = []
    for c in canonicals:
        if c["kind"] != "view":
            continue
        view = c["source_name"].lower()
        view_def = views.get(view) or {"primary": set(), "joined": set()}
        primary = view_def["primary"]
        if not primary:
            continue
        canonical_readers = consumer_idx.get(view, {}).get("readers", [])
        # Only count drift from the PRIMARY backing table(s). JOINed tables
        # like pm_assets (under v_pm_compliance_truth) or asset_nodes (under
        # v_asset_truth) belong to other domains and have their own readers.
        drift_sites: list[tuple[str, str]] = []
        for ut in sorted(primary):
            for (path, _layer) in consumer_idx.get(ut, {}).get("readers", []):
                drift_sites.append((path, ut))
        drift_sites = sorted(set(drift_sites))
        domain_report.append({
            "domain":            c["domain"],
            "view":              view,
            "primary":           sorted(primary),
            "joined":            sorted(view_def["joined"]),
            "canonical_readers": len(canonical_readers),
            "drift_readers":     len(drift_sites),
            "drift_sites":       drift_sites[:8],
        })
        if len(canonical_readers) == 0 and len(drift_sites) >= 1:
            issues.append({
                "check": "canonical_drift", "skip": True,
                "reason": (
                    f"Domain '{c['domain']}' (view {view}) has ZERO consumers reading the canonical view, "
                    f"but {len(drift_sites)} site(s) read primary table(s) {sorted(primary)} directly. "
                    f"Migrate at least one consumer to {view} or retire the canonical."
                ),
            })
        elif len(drift_sites) > 2 * max(len(canonical_readers), 1):
            issues.append({
                "check": "canonical_drift", "skip": True,
                "reason": (
                    f"Domain '{c['domain']}' (view {view}) has {len(canonical_readers)} canonical reader(s) "
                    f"vs {len(drift_sites)} primary-table reader(s). Drift outweighs canonical; "
                    f"first 3 drift sites: {[f'{p}:{t}' for p, t in drift_sites[:3]]}."
                ),
            })
    return issues, domain_report


# ── Layer 2: orphan canonicals ────────────────────────────────────────────────

def check_orphan_canonicals(
    canonicals: list[dict],
    consumer_idx: dict[str, dict],
) -> tuple[list[dict], list[dict]]:
    """Registered canonical with zero consumers across all consumer files."""
    issues: list[dict] = []
    orphans: list[dict] = []
    for c in canonicals:
        name = c["source_name"].lower()
        n = len(consumer_idx.get(name, {}).get("readers", []))
        if n == 0:
            orphans.append({
                "domain":      c["domain"],
                "source":      c["source_name"],
                "kind":        c["kind"],
                "owner_skill": c["owner_skill"],
            })
            issues.append({
                "check": "orphan_canonicals", "skip": True,
                "reason": (
                    f"Registered canonical '{c['domain']}' -> {c['source_name']} ({c['kind']}, "
                    f"owner_skill={c['owner_skill']}) has ZERO consumers. Either the consumer was "
                    f"never wired (silo) or the canonical is dead and should be removed from the registry."
                ),
            })
    return issues, orphans


# ── Layer 3: unregistered hotspots ────────────────────────────────────────────

def check_unregistered_hotspots(
    canonicals: list[dict],
    consumer_idx: dict[str, dict],
    views: dict[str, dict[str, set[str]]],
) -> tuple[list[dict], list[dict]]:
    """Tables read by N+ files with no canonical registered. Truth-scattering
    candidates -- registering them prevents future silos.
    """
    registered_names = {c["source_name"].lower() for c in canonicals}
    # Tables that already serve as the underlying (primary OR joined) for a
    # registered view are implicitly canonical-backed.
    backed_tables = set()
    for c in canonicals:
        if c["kind"] != "view":
            continue
        vd = views.get(c["source_name"].lower()) or {}
        backed_tables |= vd.get("primary", set())
        backed_tables |= vd.get("joined",  set())

    issues: list[dict] = []
    hotspots: list[dict] = []
    for table, info in consumer_idx.items():
        if table in registered_names or table in backed_tables:
            continue
        if table in HOTSPOT_IGNORE_TABLES:
            continue
        n_readers = len(info["readers"])
        if n_readers >= UNREGISTERED_HOTSPOT_THRESHOLD:
            hotspots.append({
                "table":     table,
                "n_readers": n_readers,
                "layers":    info["layers"],
                "sample":    [p for p, _ in info["readers"][:5]],
            })
    hotspots.sort(key=lambda h: -h["n_readers"])
    if hotspots:
        for h in hotspots[:8]:
            issues.append({
                "check": "unregistered_hotspots", "skip": True,
                "reason": (
                    f"Table '{h['table']}' is read by {h['n_readers']} consumer file(s) "
                    f"({dict(h['layers'])}) with no canonical entry. Candidate for a v_{h['table']}_truth "
                    f"view + canonical_sources registration. First 3 readers: {h['sample'][:3]}."
                ),
            })
    return issues, hotspots


# ── Layer 4: cross-system coverage matrix ─────────────────────────────────────

def build_coverage_matrix(
    canonicals: list[dict],
    consumer_idx: dict[str, dict],
) -> list[dict]:
    """For each canonical, who reads it? (counts per layer + sample paths)."""
    matrix: list[dict] = []
    for c in canonicals:
        name = c["source_name"].lower()
        info = consumer_idx.get(name, {"readers": [], "layers": {}})
        readers_by_layer: dict[str, list[str]] = defaultdict(list)
        for path, layer in info["readers"]:
            readers_by_layer[layer].append(path)
        matrix.append({
            "domain":      c["domain"],
            "source":      c["source_name"],
            "kind":        c["kind"],
            "owner_skill": c["owner_skill"],
            "freshness":   c["freshness"],
            "n_readers":   len(info["readers"]),
            "by_layer":    {k: len(v) for k, v in readers_by_layer.items()},
            "samples":     {k: v[:3] for k, v in readers_by_layer.items()},
        })
    matrix.sort(key=lambda m: (m["n_readers"], m["domain"]))
    return matrix


def check_cross_system_gaps(
    matrix: list[dict],
) -> list[dict]:
    """WARN when a canonical is consumed by exactly one platform layer.
    These are silos in plain sight: data only one part of the platform sees.
    Domains in ACCEPTED_SINGLE_LAYER_DOMAINS are skipped (they have a
    documented justification — the matrix still shows them so a future
    consumer change can prove the exception is still valid).
    """
    issues: list[dict] = []
    for entry in matrix:
        n_layers = sum(1 for v in entry["by_layer"].values() if v > 0)
        if entry["n_readers"] >= 1 and n_layers == 1:
            if entry["domain"] in ACCEPTED_SINGLE_LAYER_DOMAINS:
                # Documented exception — do not raise WARN
                continue
            (only_layer, _) = next(iter(entry["by_layer"].items()))
            issues.append({
                "check": "cross_system_gaps", "skip": True,
                "reason": (
                    f"Canonical '{entry['domain']}' ({entry['source']}) is consumed only by '{only_layer}' "
                    f"({entry['by_layer'][only_layer]} files). Other platform layers do not read this "
                    f"truth -- silo unless intentional. If intentional, add to "
                    f"ACCEPTED_SINGLE_LAYER_DOMAINS in validate_silo_monitor.py with a justification."
                ),
            })
    return issues


# ── Runner ────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "canonical_drift",
    "orphan_canonicals",
    "unregistered_hotspots",
    "cross_system_gaps",
]

CHECK_LABELS = {
    "canonical_drift":       "L1  No drift between canonical view and underlying-table consumers   [WARN]",
    "orphan_canonicals":     "L2  No registered canonical lacks a consumer                         [WARN]",
    "unregistered_hotspots": "L3  No 8+ readers of an unregistered table (truth-scatter candidate) [WARN]",
    "cross_system_gaps":     "L4  No canonical is read by only one platform layer (silo in plain sight) [WARN]",
}


def main():
    def bold(s):
        return f"\033[1m{s}\033[0m"

    print(bold("\nSilo Monitor (4-layer architectural audit)"))
    print("=" * 60)

    canonicals    = load_registered_canonicals()
    views         = load_view_definitions()
    consumer_files = list_consumer_files()
    consumer_idx  = build_consumer_index(consumer_files)

    print(f"  {len(canonicals)} canonicals registered, {len(views)} views defined, "
          f"{len(consumer_files)} consumer files scanned.\n")

    drift_issues,   drift_report   = check_canonical_drift(canonicals, views, consumer_idx)
    orphan_issues,  orphan_list    = check_orphan_canonicals(canonicals, consumer_idx)
    hotspot_issues, hotspot_list   = check_unregistered_hotspots(canonicals, consumer_idx, views)
    coverage_matrix                 = build_coverage_matrix(canonicals, consumer_idx)
    cross_issues                    = check_cross_system_gaps(coverage_matrix)

    all_issues = drift_issues + orphan_issues + hotspot_issues + cross_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    # Always print the matrix as a quick readable summary, regardless of pass state.
    print(f"\n{bold('CANONICAL COVERAGE MATRIX')}")
    print("  " + "-" * 56)
    print("  {:<28}  {:>4}  {:<24}".format("domain", "n", "by layer"))
    print("  " + "-" * 56)
    for m in coverage_matrix:
        layer_str = ", ".join(f"{k}={v}" for k, v in sorted(m["by_layer"].items())) or "-"
        print("  {:<28}  {:>4}  {:<24}".format(m["domain"][:28], m["n_readers"], layer_str[:24]))

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":           "silo_monitor",
        "total_checks":        total,
        "passed":              n_pass,
        "warned":              n_warn,
        "failed":              n_fail,
        "n_canonicals":        len(canonicals),
        "n_views_defined":     len(views),
        "n_consumer_files":    len(consumer_files),
        "drift_per_domain":    drift_report,
        "orphans":             orphan_list,
        "unregistered_hotspots": hotspot_list,
        "coverage_matrix":     coverage_matrix,
        "issues":              [i for i in all_issues if not i.get("skip")],
        "warnings":            [i for i in all_issues if i.get("skip")],
    }
    with open("silo_monitor_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
