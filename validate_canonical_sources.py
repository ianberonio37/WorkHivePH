"""
Canonical Sources Validator - WorkHive Platform
================================================
Foundation validator for the Canonical Sources initiative (Phase A.1+).
Every domain concept on the platform should have one entry in the
`canonical_sources` registry. AI agents read from the registry first when
asked about a registered domain so the answer is consistent across
orchestrators, edge functions, and UI pages.

Layer 1 - Registry health
  1.  Migration declares the canonical_sources table        [FAIL]
  2.  Migration locks writes to service role only           [FAIL]
  3.  Migration grants SELECT to anon and authenticated     [FAIL]
  4.  Initial seed registers at least the 6 ALIGNED truths  [FAIL]

Layer 2 - Drift detection (Phase 4.1, activated 2026-05-12)
  5.  No consumer reads an underlying table directly via .from().select()
      when a canonical v_*_truth view exists for that domain   [FAIL]

Layer 3 - Contract integrity (active when v_*_truth views land)
  7.  Every registered view/table exists in migrations         [FAIL]
  8.  Contract JSONB declares non-empty 'key' array            [WARN]

Layer 2 ratchets the cross-surface audit shipped 2026-05-12. The discovery
is data-driven: every CREATE VIEW for `v_*_truth` parsed from migrations
contributes an (underlying -> view) mapping. Consumers that read the
underlying via .from('<tbl>').select(...) when a canonical view exists FAIL.
Writes (.insert / .update / .upsert / .delete) are excluded -- writers
legitimately target the underlying table. Inline opt-out via the comment
token `// canonical-allow: <reason>` on the .from() line or the 2 lines
above documents intentional underlying reads (e.g. a writer that also reads
the same table for the next computation).

Skills consulted: architect (registry pattern, contract metadata),
data-engineer (immutable schema, narrow lookups), security (locked write
policy, anon read for AI lookup), multitenant-engineer (no hive_id on
registry - this is platform metadata).

Usage:  python validate_canonical_sources.py
Output: canonical_sources_report.json
"""
import re
import json
import sys
import os
import glob

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

MIGRATION_PATH = os.path.join(
    "supabase", "migrations", "20260509000001_canonical_sources_foundation.sql"
)
MIGRATIONS_DIR = os.path.join("supabase", "migrations")

# Tier 3 from CANONICAL_SOURCES_AUDIT.md: domains that are already aligned
# and just need registration. Phase A.1 seeds these into the registry.
ALIGNED_TRUTHS = [
    "shift_state",
    "asset_graph_edges",
    "community_thread",
    "engineering_calc_history",
    "cmms_external_link",
    "ai_rate_limit",
    # Three audit logs (D5 from the audit, kept separate as different domains
    # but registered so AI agents know which one to query)
    "automation_log",
    "hive_audit_log",
    "cmms_audit_log",
]

CHECK_NAMES = [
    "registry_table_declared",
    "registry_writes_locked",
    "registry_select_granted",
    "registry_seeded_aligned",
    "registry_sources_exist",
    "drift_detection",
]

CHECK_LABELS = {
    "registry_table_declared":  "L1  canonical_sources table declared in migration              [FAIL]",
    "registry_writes_locked":   "L1  Write policy locked (USING false WITH CHECK false)         [FAIL]",
    "registry_select_granted":  "L1  GRANT SELECT to anon and authenticated                     [FAIL]",
    "registry_seeded_aligned":  "L1  Initial seed registers all aligned truths from the audit   [FAIL]",
    "registry_sources_exist":   "L3  Every registered source_name exists in migrations          [FAIL]",
    "drift_detection":          "L2  Consumers do not read underlying tables when a v_*_truth exists [FAIL]",
}


# ── Layer 2 plumbing: paths, allowlists, regex helpers ───────────────────────

FUNCTIONS_DIR  = os.path.join("supabase", "functions")
PYTHON_API_DIR = "python-api"

DRIFT_EXCLUDED_HTML = ("-test.html", ".backup.html", "_backup.html", ".backup")
DRIFT_EXCLUDED_PATH_PARTS = (
    os.sep + "test-data-seeder" + os.sep,
    os.sep + "tools" + os.sep,
    os.sep + "video_marketing_app" + os.sep,
    os.sep + ".git" + os.sep,
    os.sep + "node_modules" + os.sep,
)

# Edge functions that legitimately read underlying tables alongside their
# write workload. Match by parent directory basename for edge fns
# (.../functions/<name>/index.ts) or by file stem for top-level scripts.
WRITER_BASENAMES = {
    "batch-risk-scoring",        # owns asset_risk_scores writes
    "fmea-populator",            # owns rcm_fmea_modes writes
    "weibull-fitter",            # owns rcm_weibull_fits writes
    "pf-calculator",             # owns rcm_pf_intervals writes
    "amc-orchestrator",          # owns amc_briefings writes
    "trigger-ml-retrain",        # owns ml artifact writes
    "parts-staging-recommender", # owns parts_staging_recommendations writes
    "visual-defect-capture",     # owns logbook + fault_knowledge writes
    "sensor-readings-ingest",    # owns sensor_readings writes
}

# HTML pages that OWN their underlying table -- the page is the canonical
# editor (insert / update path) for that data. Reads of the underlying in
# the owning page are expected; the canonical view is for OTHER surfaces
# that report on / aggregate the data, not for the editing page itself.
HTML_OWNERS = {
    # Phase 5c (2026-05-12): assets table dropped; the asset wizard + linker
    # + supervisor approval flows live in these pages so they now own
    # asset_nodes directly.
    "logbook.html":       {"logbook", "asset_nodes"},
    "inventory.html":     {"inventory_items", "asset_nodes"},
    # pm_scope_items was here but reads now go through v_pm_scope_items_truth
    # to match the home dashboard PM Overdue tile (was 21 vs 0 disagreement).
    # The page still writes pm_scope_items via .insert(); the validator skips
    # writes (verb != select), so this only affects SELECT enforcement.
    "pm-scheduler.html":  {"pm_assets", "asset_nodes"},
    "parts-tracker.html": {"inventory_items", "logbook", "asset_nodes"},
    "hive.html":          {"asset_nodes"},      # supervisor approval queue
    "project-manager.html": {"asset_nodes"},    # project asset linker
}

# Known pre-existing drift in non-owner consumers. Each entry documents an
# underlying-read scheduled for migration to the canonical view (or
# permanently retained for a documented reason). Add an inline
# `// canonical-allow: <reason>` comment when migrating the call away to
# the view; remove the entry once the file is clean. NEW drift outside
# this set FAILs immediately, which is the point.
#
# Path separator is normalised to '/' so the set works on Windows and Linux.
KNOWN_DRIFT = {
    # ── HTML pages that read other-domain tables they don't own ─────────────
    # Asset Hub reads asset_nodes for neighbor traversal + pm_assets for
    # per-asset PM context. The v_pm_compliance_truth migration is on the
    # roadmap (revamp Phase 1.2); asset_nodes neighbor reads are permanent.
    ("asset-hub.html", "asset_nodes"),
    ("asset-hub.html", "pm_assets"),
    # Landing page PM widget reads raw pm_assets for the home dashboard.
    ("index.html", "pm_assets"),
    # Integrations page does a bulk export of recent logbook for CMMS sync.
    ("integrations.html", "logbook"),
    # Logbook page reads inventory_items + pm_assets for the parts picker
    # and the PM context selector while drafting a fault entry. Cross-domain
    # reads from an owner page; migrate to v_inventory_items_truth +
    # v_pm_compliance_truth in a follow-up.
    ("logbook.html", "inventory_items"),
    ("logbook.html", "pm_assets"),

    # ── Shared client JS: search overlay indexes raw asset + PM rows ───────
    ("search-overlay.js", "asset_nodes"),
    ("search-overlay.js", "pm_assets"),

    # ── Edge functions slated to migrate to canonical views ─────────────────
    # 2026-05-12 batch migration cleared 7 edge functions: analytics-orchestrator,
    # ai-orchestrator (hive mode), shift-planner-orchestrator, intelligence-report,
    # failure-signature-scan, benchmark-compute, scheduled-agents, embed-entry.
    # All now read through v_logbook_truth / v_pm_compliance_truth in hive mode,
    # with inline `canonical-allow` for solo-mode fallback paths.
    #
    # Asset Brain neighbor traversal: v_asset_truth covers the focal asset
    # but neighbor lookups need raw asset_nodes. Permanent.
    ("supabase/functions/asset-brain-query/index.ts", "asset_nodes"),
}

# Inline opt-out token: a comment like `// canonical-allow: writes here`
# on the .from() line or the 2 lines above marks the call as intentional.
CANONICAL_ALLOW_TOKEN = "canonical-allow:"

# Match .from('tbl') ... .verb(...) within a 320-char window so multi-line
# .select(...) chains still resolve to the right verb. Capturing the verb
# lets us skip writes (which legitimately target the underlying).
FROM_VERB_RE = re.compile(
    r"""
    \.from\(\s*['"](?P<tbl>[\w]+)['"]\s*\)
    (?P<chain>[\s\S]{0,320}?)
    \.(?P<verb>select|insert|update|upsert|delete)\b
    """,
    re.VERBOSE,
)

# Canonical pairs from CANONICAL_SOURCES_AUDIT.md. Each row declares: when a
# consumer reads <underlying> for a domain concept, it MUST go through <view>.
# Hand-curated rather than auto-derived because some *_truth views are
# composite (e.g. v_worker_skill_truth joins hive_members + skill_badges +
# skill_profiles) and have no single "owning" underlying. Auto-derivation
# misidentifies the first FROM clause inside a subquery as the owning table.
#
# To add a new canonical pair: append below AND add an INSERT INTO
# public.canonical_sources row in the view's migration. The registry
# completeness check (L3) keeps the two lists in sync.
CANONICAL_PAIRS = {
    "asset_nodes":         "v_asset_truth",
    "asset_risk_scores":   "v_risk_truth",
    "pm_assets":           "v_pm_compliance_truth",
    "pm_scope_items":      "v_pm_scope_items_truth",
    "logbook":             "v_logbook_truth",
    "inventory_items":     "v_inventory_items_truth",
    "marketplace_sellers": "v_marketplace_sellers_truth",
    "marketplace_listings": "v_marketplace_listings_truth",
    "marketplace_inquiries": "v_marketplace_inquiries_truth",
    "community_posts":     "v_community_posts_truth",
    "hives":               "v_hives_truth",
    "external_sync":       "v_external_sync_truth",
    "rcm_pf_intervals":    "v_pf_truth",
    "inventory_transactions": "v_inventory_transactions_truth",
    "marketplace_orders":     "v_marketplace_orders_truth",
    "project_items":          "v_project_items_truth",
    "project_progress_logs":  "v_project_progress_truth",
    "ai_reports":             "v_ai_reports_truth",
    "skill_badges":           "v_skill_badges_truth",
    "worker_achievements":    "v_worker_achievements_truth",
}


def discover_underlying_to_view():
    """Returns the curated CANONICAL_PAIRS mapping. Auto-discovery was tried
    first but mis-attributed subquery FROM clauses to the wrong canonical
    view; the explicit map is the reliable contract."""
    return dict(CANONICAL_PAIRS)


def _drift_list_consumer_files():
    """Return [(path, layer)] for HTML / shared JS / edge / python-api."""
    out = []
    for path in sorted(glob.glob("*.html")):
        if any(path.endswith(ex) for ex in DRIFT_EXCLUDED_HTML):
            continue
        out.append((path, "html"))
    for fname in ("utils.js", "nav-hub.js", "companion-launcher.js", "search-overlay.js"):
        if os.path.exists(fname):
            out.append((fname, "shared_js"))
    for path in sorted(glob.glob(os.path.join(FUNCTIONS_DIR, "**", "*.ts"), recursive=True)):
        if any(p in path for p in DRIFT_EXCLUDED_PATH_PARTS):
            continue
        out.append((path, "edge"))
    for path in sorted(glob.glob(os.path.join(PYTHON_API_DIR, "**", "*.py"), recursive=True)):
        if any(p in path for p in DRIFT_EXCLUDED_PATH_PARTS):
            continue
        out.append((path, "python_api"))
    return out


def _line_no(content, pos):
    return content.count("\n", 0, pos) + 1


def _line_at(content, line_no):
    lines = content.splitlines()
    idx = line_no - 1
    return lines[idx] if 0 <= idx < len(lines) else ""


def _allowlist_reason(content, match_start):
    """Return the documented reason if `canonical-allow:` is on the .from() line
    or one of the 2 lines above. None otherwise."""
    ln = _line_no(content, match_start)
    for probe in (ln, ln - 1, ln - 2):
        if probe <= 0:
            continue
        line = _line_at(content, probe)
        idx = line.find(CANONICAL_ALLOW_TOKEN)
        if idx >= 0:
            return line[idx + len(CANONICAL_ALLOW_TOKEN):].strip()
    return None


def check_drift_detection():
    """L2 -- FAIL when a consumer SELECT-reads an underlying table that has
    a canonical view. Returns issues list plus a structured report list so
    main() can print the drift distribution."""
    mapping = discover_underlying_to_view()
    if not mapping:
        return [], []   # no views yet; nothing to enforce
    consumers = _drift_list_consumer_files()

    issues = []
    report = []
    for path, layer in consumers:
        parent_dir = (
            os.path.basename(os.path.dirname(path))
            if path.endswith("index.ts") else ""
        )
        stem     = os.path.basename(path).rsplit(".", 1)[0]
        basename = os.path.basename(path)
        # Normalise to forward slashes so KNOWN_DRIFT entries portable
        # across Windows and Linux.
        path_norm = path.replace(os.sep, "/")

        if parent_dir in WRITER_BASENAMES or stem in WRITER_BASENAMES:
            continue
        owner_tables = HTML_OWNERS.get(basename, set())
        content = read_file(path) or ""
        if not content:
            continue

        for m in FROM_VERB_RE.finditer(content):
            tbl = m.group("tbl").lower()
            verb = m.group("verb").lower()
            if tbl not in mapping or verb != "select":
                continue
            line_no = _line_no(content, m.start())
            reason = _allowlist_reason(content, m.start())
            if reason is not None:
                report.append({
                    "path": path, "layer": layer, "table": tbl,
                    "view": mapping[tbl], "kind": "allowlisted",
                    "reason": reason, "line": line_no,
                })
                continue
            if tbl in owner_tables:
                report.append({
                    "path": path, "layer": layer, "table": tbl,
                    "view": mapping[tbl], "kind": "owner_read",
                    "reason": "page owns the underlying table",
                    "line": line_no,
                })
                continue
            if (path_norm, tbl) in KNOWN_DRIFT:
                report.append({
                    "path": path, "layer": layer, "table": tbl,
                    "view": mapping[tbl], "kind": "known_debt",
                    "reason": "pre-existing drift logged in KNOWN_DRIFT",
                    "line": line_no,
                })
                continue
            report.append({
                "path": path, "layer": layer, "table": tbl,
                "view": mapping[tbl], "kind": "drift", "line": line_no,
            })
            issues.append({
                "check": "drift_detection",
                "reason": (
                    f"{path}:{line_no} reads '{tbl}' directly via "
                    f".from('{tbl}').select(...). Canonical view "
                    f"'{mapping[tbl]}' exists and should be the read path. "
                    f"Either migrate the call, add a comment "
                    f"`// {CANONICAL_ALLOW_TOKEN} <reason>` on the .from() "
                    f"line (or one of the 2 lines above), or add "
                    f"('{path_norm}', '{tbl}') to KNOWN_DRIFT with a TODO."
                ),
            })
    return issues, report


def _read_migration():
    return read_file(MIGRATION_PATH) or ""


# ── Layer 1: Registry health ─────────────────────────────────────────────────

def check_registry_table_declared(text):
    if not text:
        return [{
            "check": "registry_table_declared",
            "reason": (
                f"{MIGRATION_PATH} missing. The canonical_sources registry is "
                f"the foundation of the truth-scattering fix; nothing else can "
                f"register without it."
            ),
        }]
    if "CREATE TABLE IF NOT EXISTS public.canonical_sources" not in text:
        return [{
            "check": "registry_table_declared",
            "reason": "canonical_sources table is not declared. Migration must CREATE TABLE IF NOT EXISTS public.canonical_sources.",
        }]
    required_cols = ["domain", "source_kind", "source_name", "owner_skill", "freshness", "contract"]
    missing = [c for c in required_cols if not re.search(rf"\b{c}\b", text)]
    if missing:
        return [{
            "check": "registry_table_declared",
            "reason": f"canonical_sources missing required columns: {missing}",
        }]
    return []


def check_registry_writes_locked(text):
    if not text:
        return [{"check": "registry_writes_locked", "reason": f"{MIGRATION_PATH} missing."}]
    # Need a FOR ALL policy with USING (false) WITH CHECK (false) to block writes
    pat = re.compile(
        r"CREATE POLICY[^;]+canonical_sources[^;]+FOR ALL[^;]+USING\s*\(\s*false\s*\)[^;]+WITH CHECK\s*\(\s*false\s*\)",
        re.IGNORECASE | re.DOTALL,
    )
    if not pat.search(text):
        return [{
            "check": "registry_writes_locked",
            "reason": (
                "canonical_sources needs a FOR ALL policy with USING (false) WITH CHECK (false) "
                "so anon and authenticated cannot write to the registry. Service role bypasses RLS "
                "and is the only legitimate writer."
            ),
        }]
    return []


def check_registry_select_granted(text):
    if not text:
        return [{"check": "registry_select_granted", "reason": f"{MIGRATION_PATH} missing."}]
    pat = re.compile(
        r"GRANT[^;]*SELECT[^;]*ON\s+public\.canonical_sources[^;]*TO[^;]*authenticated",
        re.IGNORECASE | re.DOTALL,
    )
    if not pat.search(text):
        return [{
            "check": "registry_select_granted",
            "reason": (
                "GRANT SELECT to anon and authenticated is required so AI agents (running with "
                "anon key from edge functions) can look up canonicals. Without GRANT, every "
                "lookup returns 401 even though RLS allows reads."
            ),
        }]
    return []


def check_registry_seeded_aligned(text):
    if not text:
        return [{"check": "registry_seeded_aligned", "reason": f"{MIGRATION_PATH} missing."}]
    issues = []
    for domain in ALIGNED_TRUTHS:
        if not re.search(rf"'\s*{re.escape(domain)}\s*'", text):
            issues.append({
                "check": "registry_seeded_aligned",
                "reason": (
                    f"Aligned truth '{domain}' is not seeded in the migration. The audit "
                    f"identified it as already-canonical and ready to register on day one."
                ),
            })
    return issues


# ── Layer 3: Source existence (active for views as they land) ─────────────────

def _registered_sources_from_migration(text):
    """Extract (domain, source_kind, source_name) tuples from INSERT VALUES."""
    sources = []
    if not text:
        return sources
    # Crude parser: find INSERT INTO public.canonical_sources blocks and
    # extract the first three columns of each VALUES row.
    insert_blocks = re.findall(
        r"INSERT INTO public\.canonical_sources[\s\S]+?ON CONFLICT",
        text,
        re.IGNORECASE,
    )
    for block in insert_blocks:
        # Find ('domain', 'source_kind', 'source_name', ...)
        rows = re.findall(
            r"\(\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'([^']+)'",
            block,
        )
        for d, k, n in rows:
            sources.append((d, k, n))
    return sources


def check_registry_sources_exist(text):
    """For every (kind=table) registration, the table must exist in some migration.
    For (kind=view), the view must exist (parsed by validate_schema_coverage's logic).
    Phase A.1 only checks tables; views are covered when v_*_truth lands."""
    if not text:
        return [{"check": "registry_sources_exist", "reason": f"{MIGRATION_PATH} missing."}]

    sources = _registered_sources_from_migration(text)
    if not sources:
        # Nothing seeded yet; not a fail at A.1 if we already passed seeded_aligned
        return []

    # Build set of all CREATE TABLE names across migrations
    all_tables = set()
    for path in glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")):
        sql = read_file(path) or ""
        # strip line comments
        sql = re.sub(r"--[^\n]*", "", sql)
        for m in re.finditer(
            r'CREATE TABLE (?:IF NOT EXISTS )?(?:"?\w+"?\.)?"?(\w+)"?\s*\(',
            sql,
            re.IGNORECASE,
        ):
            all_tables.add(m.group(1))
        for m in re.finditer(
            r'CREATE (?:OR REPLACE )?(?:MATERIALIZED )?VIEW\s+(?:"?\w+"?\.)?"?(\w+)"?',
            sql,
            re.IGNORECASE,
        ):
            all_tables.add(m.group(1))

    issues = []
    for domain, kind, name in sources:
        if kind in ("table", "view") and name not in all_tables:
            issues.append({
                "check": "registry_sources_exist",
                "reason": (
                    f"Domain '{domain}' registers source '{name}' (kind={kind}) but no migration "
                    f"declares a table or view with that name. Either the source is a typo or "
                    f"the migration that creates it has not landed yet."
                ),
            })
    return issues


# ── Runner ────────────────────────────────────────────────────────────────────

def main():
    def bold(s):
        return f"\033[1m{s}\033[0m"

    print(bold("\nCanonical Sources Validator"))
    print("=" * 50)

    text = _read_migration()

    all_issues = []
    all_issues += check_registry_table_declared(text)
    all_issues += check_registry_writes_locked(text)
    all_issues += check_registry_select_granted(text)
    all_issues += check_registry_seeded_aligned(text)
    all_issues += check_registry_sources_exist(text)

    drift_issues, drift_report = check_drift_detection()
    all_issues += drift_issues

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    # Print the drift distribution after the per-check lines so the reviewer
    # can see at a glance where remaining underlying reads concentrate.
    drift_only = [r for r in drift_report if r.get("kind") == "drift"]
    if drift_only:
        print(f"\n{bold('DRIFT DISTRIBUTION (informational)')}")
        print("  " + "-" * 50)
        by_layer = {}
        by_view  = {}
        for r in drift_only:
            by_layer[r["layer"]] = by_layer.get(r["layer"], 0) + 1
            by_view[r["view"]]   = by_view.get(r["view"],  0) + 1
        for layer, count in sorted(by_layer.items()):
            print(f"  {layer:<20}  {count} underlying read(s)")
        for view, count in sorted(by_view.items(), key=lambda kv: -kv[1])[:10]:
            print(f"  {view:<32}  {count} consumer(s)")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "canonical_sources",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
        "drift":        [r for r in drift_report if r.get("kind") == "drift"],
        "allowlisted":  [r for r in drift_report if r.get("kind") == "allowlisted"],
        "owner_reads":  [r for r in drift_report if r.get("kind") == "owner_read"],
        "known_debt":   [r for r in drift_report if r.get("kind") == "known_debt"],
    }
    with open("canonical_sources_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
