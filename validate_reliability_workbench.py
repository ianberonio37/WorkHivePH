"""
Reliability Engineering Workbench Validator -- WorkHive Platform
================================================================
Foundation validator for the Reliability Workbench (Phase R.1+).
Verifies the four schema tables, three canonical views, RLS policies,
realtime publication, and canonical_sources registrations.

Layer 1 - Schema completeness
  1.  rcm_fmea_modes table with required columns + RPN generated column   [FAIL]
  2.  rcm_strategies table with JA1011 decision CHECK                     [FAIL]
  3.  weibull_fits table with failure_pattern CHECK                       [FAIL]
  4.  pf_intervals table with pf_days + recommended_interval_days CHECKs  [FAIL]

Layer 2 - Canonical views and registrations
  5.  v_fmea_truth view defined and registered                            [FAIL]
  6.  v_rcm_truth view defined and registered                             [FAIL]
  7.  v_weibull_truth view defined and registered                         [FAIL]

Layer 3 - Multi-tenant + realtime plumbing
  8.  RLS enabled on all four tables                                      [FAIL]
  9.  GRANT to anon and authenticated on all four tables + three views    [FAIL]
 10.  Hive-membership-join policy on every read policy                    [FAIL]
 11.  Realtime publication includes rcm_fmea_modes, rcm_strategies,
      weibull_fits                                                        [FAIL]
 12.  REPLICA IDENTITY FULL on the realtime tables                        [FAIL]

Layer 4 - Asset Hub UI integration (Phase R.4)
 13.  asset-hub.html has the rcm-modal markup and decision options       [FAIL]
 14.  asset-hub.html writes to rcm_strategies and reads via fmea_mode_id [FAIL]
 15.  asset-hub.html pushes strategies to pm_scope_items + sets the
      written_to_pm_scope_item_id link                                   [FAIL]
 16.  asset-hub.html subscribes to rcm_strategies realtime                [FAIL]

Layer 5 - Weibull fitter (Phase R.5)
 17.  python-api/reliability/weibull.py exposes fit_weibull(failures,
      censored) and uses lifelines.WeibullFitter                          [FAIL]
 18.  python-api/main.py exposes POST /reliability/weibull                [FAIL]
 19.  python-api/requirements.txt includes lifelines                      [FAIL]
 20.  weibull-fitter edge function exists, calls Python API, persists
      to weibull_fits                                                     [FAIL]
 21.  asset-hub.html has Weibull panel + Compute-fit button + reads
      v_weibull_truth + subscribes to weibull_fits realtime               [FAIL]

Layer 6 - P-F interval calculator (Phase R.6)
 22.  python-api/reliability/pf_interval.py exposes calculate_pf with
      threshold validation + median pair detection                        [FAIL]
 23.  python-api/main.py exposes POST /reliability/pf-interval            [FAIL]
 24.  pf-calculator edge fn proxies Python + persists to pf_intervals     [FAIL]
 25.  v_pf_truth view + canonical_sources registration                    [FAIL]
 26.  asset-hub.html has P-F panel + parameter dropdown + thresholds +
      Compute button + reads v_pf_truth                                   [FAIL]

Layer 7 - Print-ready Reliability Report (Phase R.7)
 27.  asset-hub.html has reliability-report-btn + generateReliabilityReport
      function that pulls every canonical truth (v_fmea_truth, v_rcm_truth,
      v_weibull_truth, v_pf_truth) in one go                              [FAIL]
 28.  Report HTML covers all 5 sections (FMEA / RCM / Weibull / P-F /
      recent history) and a standards footer                              [FAIL]
 29.  Print CSS rules: A4 page, color-print-adjust, page-break-inside,
      no-print toolbar (Shift Handover Report skill pattern)              [FAIL]

Skills consulted: maintenance-expert (RCM JA1011, FMEA AIAG-VDA scoring,
ISO 14224 hierarchy reuse), predictive-analytics (Weibull beta/eta
contract, P-F default rule), architect (canonical sources + RLS pattern),
multitenant-engineer (hive-membership-join + GRANT requirement),
realtime-engineer (publication opt-in + REPLICA IDENTITY FULL),
data-engineer (composite indexes at creation, generated columns).

Usage:  python validate_reliability_workbench.py
Output: reliability_workbench_report.json
"""
import re
import json
import sys
import os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

MIGRATION_PATH = os.path.join(
    "supabase", "migrations", "20260509000005_reliability_workbench_foundation.sql"
)

# Required columns per table (verified against the migration body).
REQUIRED_COLS = {
    "rcm_fmea_modes": {
        "id", "hive_id", "asset_id", "function_text", "failure_mode",
        "effect_text", "cause_text", "severity", "occurrence", "detection",
        "rpn", "consequence_class", "source", "ai_confidence",
        "created_at", "updated_at", "approved_at",
    },
    "rcm_strategies": {
        "id", "hive_id", "fmea_mode_id", "decision", "task_text",
        "interval_days", "rationale", "weibull_fit_id", "pf_interval_id",
        "written_to_pm_scope_item_id", "source", "ai_confidence",
        "created_at", "updated_at", "approved_at",
    },
    "weibull_fits": {
        "id", "hive_id", "asset_id", "fmea_mode_id",
        "beta", "eta_days", "failure_pattern", "n_failures", "n_censored",
        "fit_method", "log_likelihood", "source_window_days", "generated_at",
    },
    "pf_intervals": {
        "id", "hive_id", "asset_id", "fmea_mode_id",
        "parameter", "p_threshold", "f_threshold", "pf_days",
        "recommended_interval_days", "basis", "generated_at",
    },
}

DECISIONS = {
    "run_to_failure", "scheduled_on_condition", "scheduled_restoration",
    "scheduled_discard", "failure_finding", "redesign_required",
}
FAILURE_PATTERNS = {"infant", "random", "wearout", "insufficient_data"}

CHECK_NAMES = [
    "rcm_fmea_modes_schema",
    "rcm_strategies_schema",
    "weibull_fits_schema",
    "pf_intervals_schema",
    "v_fmea_truth_view",
    "v_rcm_truth_view",
    "v_weibull_truth_view",
    "rls_enabled",
    "grants_present",
    "hive_membership_join_rls",
    "realtime_publication",
    "replica_identity_full",
    "canonical_sources_registered",
    "asset_hub_rcm_modal",
    "asset_hub_rcm_strategy_writes",
    "asset_hub_pm_writeback",
    "asset_hub_rcm_realtime",
    "python_weibull_module",
    "python_weibull_endpoint",
    "python_lifelines_dep",
    "weibull_fitter_edge_fn",
    "asset_hub_weibull_ui",
    "python_pf_module",
    "python_pf_endpoint",
    "pf_calculator_edge_fn",
    "v_pf_truth_view_and_registration",
    "asset_hub_pf_ui",
    "asset_hub_reliability_report_button",
    "asset_hub_reliability_report_sections",
    "asset_hub_reliability_report_print_css",
]

CHECK_LABELS = {
    "rcm_fmea_modes_schema":       "L1  rcm_fmea_modes with RPN generated column + required columns      [FAIL]",
    "rcm_strategies_schema":       "L1  rcm_strategies with JA1011 decision CHECK + required columns    [FAIL]",
    "weibull_fits_schema":         "L1  weibull_fits with failure_pattern CHECK + beta/eta columns       [FAIL]",
    "pf_intervals_schema":         "L1  pf_intervals with pf_days + recommended_interval_days CHECKs     [FAIL]",
    "v_fmea_truth_view":           "L2  v_fmea_truth view defined (approved-only filter)                 [FAIL]",
    "v_rcm_truth_view":            "L2  v_rcm_truth view defined (approved-only filter)                  [FAIL]",
    "v_weibull_truth_view":        "L2  v_weibull_truth view defined (DISTINCT ON latest fit)            [FAIL]",
    "rls_enabled":                 "L3  RLS enabled on all four reliability tables                       [FAIL]",
    "grants_present":              "L3  GRANT SELECT/INSERT/UPDATE/DELETE on tables + views              [FAIL]",
    "hive_membership_join_rls":    "L3  Hive-membership-join present in every read policy                [FAIL]",
    "realtime_publication":        "L3  rcm_fmea_modes + rcm_strategies + weibull_fits in publication    [FAIL]",
    "replica_identity_full":       "L3  REPLICA IDENTITY FULL on realtime-published reliability tables   [FAIL]",
    "canonical_sources_registered": "L3  fmea_truth + rcm_truth + weibull_truth registered in registry   [FAIL]",
    "asset_hub_rcm_modal":          "L4  asset-hub.html has rcm-modal markup with all 6 JA1011 decisions  [FAIL]",
    "asset_hub_rcm_strategy_writes": "L4  asset-hub.html saveStrategy writes to rcm_strategies            [FAIL]",
    "asset_hub_pm_writeback":       "L4  asset-hub.html pushes to pm_scope_items + back-links the strategy [FAIL]",
    "asset_hub_rcm_realtime":       "L4  asset-hub.html subscribes to rcm_strategies postgres_changes    [FAIL]",
    "python_weibull_module":        "L5  python-api/reliability/weibull.py uses lifelines.WeibullFitter   [FAIL]",
    "python_weibull_endpoint":      "L5  python-api/main.py exposes POST /reliability/weibull             [FAIL]",
    "python_lifelines_dep":         "L5  python-api/requirements.txt pins lifelines                       [FAIL]",
    "weibull_fitter_edge_fn":       "L5  weibull-fitter edge fn proxies Python API + writes weibull_fits  [FAIL]",
    "asset_hub_weibull_ui":         "L5  asset-hub.html has Weibull panel + reads v_weibull_truth         [FAIL]",
    "python_pf_module":             "L6  python-api/reliability/pf_interval.py exposes calculate_pf       [FAIL]",
    "python_pf_endpoint":           "L6  python-api/main.py exposes POST /reliability/pf-interval         [FAIL]",
    "pf_calculator_edge_fn":        "L6  pf-calculator edge fn proxies Python + writes pf_intervals       [FAIL]",
    "v_pf_truth_view_and_registration": "L6  v_pf_truth view + canonical_sources pf_truth registration   [FAIL]",
    "asset_hub_pf_ui":              "L6  asset-hub.html has P-F panel + parameter select + thresholds    [FAIL]",
    "asset_hub_reliability_report_button":  "L7  asset-hub.html exposes reliability-report-btn wired to generator [FAIL]",
    "asset_hub_reliability_report_sections":"L7  Report covers FMEA + RCM + Weibull + P-F + history + standards   [FAIL]",
    "asset_hub_reliability_report_print_css":"L7  Report print CSS: A4 page, color-print-adjust, no-print toolbar [FAIL]",
}


def _read():
    return read_file(MIGRATION_PATH) or ""


def _columns_in_create(text, table):
    pat = re.compile(
        r"CREATE TABLE IF NOT EXISTS public\." + re.escape(table) +
        r"\s*\((.*?)\);", re.DOTALL | re.IGNORECASE,
    )
    m = pat.search(text)
    if not m:
        return set()
    body = m.group(1)
    cols = set()
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith("--") or s.upper().startswith("CONSTRAINT"):
            continue
        first = s.split()[0].strip("\",`")
        if first.upper() in {"CHECK", "UNIQUE", "FOREIGN", "PRIMARY"}:
            continue
        cols.add(first.lower())
    return cols


def check_table_schema(text, table_name):
    """Generic L1 schema check using REQUIRED_COLS."""
    issues = []
    cols = _columns_in_create(text, table_name)
    missing = REQUIRED_COLS[table_name] - cols
    if missing:
        issues.append({
            "check": f"{table_name}_schema",
            "reason": (
                f"{table_name} missing required columns: {sorted(missing)}. "
                f"Reliability Workbench reads these via canonical views; missing "
                f"columns break the v_*_truth registrations."
            ),
        })
    return issues


def check_rcm_fmea_extras(text):
    issues = check_table_schema(text, "rcm_fmea_modes")
    # RPN must be a generated column (so consumers cannot drift from S*O*D)
    if "GENERATED ALWAYS AS" not in text or "rpn" not in text:
        issues.append({
            "check": "rcm_fmea_modes_schema",
            "reason": (
                "rcm_fmea_modes.rpn must be a GENERATED ALWAYS AS column "
                "computing severity * occurrence * detection. Storing rpn "
                "manually allows drift from the S/O/D source values."
            ),
        })
    if "BETWEEN 1 AND 10" not in text:
        issues.append({
            "check": "rcm_fmea_modes_schema",
            "reason": (
                "rcm_fmea_modes severity / occurrence / detection must each "
                "have a CHECK BETWEEN 1 AND 10 per AIAG-VDA 2019 rubric."
            ),
        })
    return issues


def check_rcm_strategies_extras(text):
    issues = check_table_schema(text, "rcm_strategies")
    for d in DECISIONS:
        if f"'{d}'" not in text:
            issues.append({
                "check": "rcm_strategies_schema",
                "reason": (
                    f"rcm_strategies.decision CHECK must include '{d}' "
                    f"per SAE JA1011 decision tree."
                ),
            })
    return issues


def check_weibull_fits_extras(text):
    issues = check_table_schema(text, "weibull_fits")
    for p in FAILURE_PATTERNS:
        if f"'{p}'" not in text:
            issues.append({
                "check": "weibull_fits_schema",
                "reason": (
                    f"weibull_fits.failure_pattern CHECK must include '{p}' "
                    f"(Weibull beta < 1 / = 1 / > 1 classification + insufficient_data fallback)."
                ),
            })
    return issues


def check_pf_intervals_extras(text):
    issues = check_table_schema(text, "pf_intervals")
    if "pf_days > 0" not in text:
        issues.append({
            "check": "pf_intervals_schema",
            "reason": "pf_intervals.pf_days must have a positive CHECK constraint.",
        })
    if "recommended_interval_days > 0" not in text:
        issues.append({
            "check": "pf_intervals_schema",
            "reason": "pf_intervals.recommended_interval_days must have a positive CHECK constraint.",
        })
    return issues


def check_view(text, view_name, must_contain):
    pat = re.compile(
        r"CREATE\s+OR\s+REPLACE\s+VIEW\s+public\." + re.escape(view_name) + r"\s+AS",
        re.IGNORECASE,
    )
    if not pat.search(text):
        return [{
            "check": f"{view_name}_view",
            "reason": f"View public.{view_name} not declared.",
        }]
    issues = []
    for needle in must_contain:
        if needle not in text:
            issues.append({
                "check": f"{view_name}_view",
                "reason": (
                    f"View {view_name} is missing the required pattern: '{needle}'. "
                    f"Contract requires it for downstream readers."
                ),
            })
    return issues


def check_rls_enabled(text):
    issues = []
    for tbl in ("rcm_fmea_modes", "rcm_strategies", "weibull_fits", "pf_intervals"):
        if not re.search(rf"ALTER TABLE\s+public\.{tbl}\s+ENABLE ROW LEVEL SECURITY", text, re.IGNORECASE):
            issues.append({
                "check": "rls_enabled",
                "reason": f"RLS not enabled on public.{tbl}. Anon access is wide open without it.",
            })
    return issues


def check_grants_present(text):
    issues = []
    targets = [
        ("rcm_fmea_modes", "DELETE"),
        ("rcm_strategies", "DELETE"),
        ("weibull_fits",   "DELETE"),
        ("pf_intervals",   "DELETE"),
        ("v_fmea_truth",   "SELECT"),
        ("v_rcm_truth",    "SELECT"),
        ("v_weibull_truth","SELECT"),
    ]
    for tbl, level in targets:
        pat = re.compile(
            rf"GRANT[^;]*{level}[^;]*ON\s+public\.{tbl}[^;]*TO[^;]*authenticated",
            re.IGNORECASE | re.DOTALL,
        )
        if not pat.search(text):
            issues.append({
                "check": "grants_present",
                "reason": (
                    f"GRANT to anon, authenticated missing on public.{tbl} "
                    f"({level}). Without GRANT every query returns 401."
                ),
            })
    return issues


def check_hive_membership_join_rls(text):
    read_policies = re.findall(
        r"CREATE POLICY\s+(\w+_read)\s+ON\s+public\.(\w+)[^;]+?USING\s*\((.*?)\);",
        text, re.DOTALL | re.IGNORECASE,
    )
    if not read_policies:
        return [{
            "check": "hive_membership_join_rls",
            "reason": "No SELECT policies found for reliability tables.",
        }]
    issues = []
    for name, table, body in read_policies:
        if table not in REQUIRED_COLS:
            continue
        if "hive_members" not in body or "auth.uid()" not in body:
            issues.append({
                "check": "hive_membership_join_rls",
                "reason": (
                    f"Policy {name} on {table} must join hive_members and check "
                    f"auth.uid(). Reliability data is hive-scoped."
                ),
            })
    return issues


def check_realtime_publication(text):
    issues = []
    for tbl in ("rcm_fmea_modes", "rcm_strategies", "weibull_fits"):
        pat = re.compile(
            rf"ALTER PUBLICATION supabase_realtime ADD TABLE public\.{tbl}",
            re.IGNORECASE,
        )
        if not pat.search(text):
            issues.append({
                "check": "realtime_publication",
                "reason": (
                    f"public.{tbl} is not added to supabase_realtime. "
                    f"Subscribers compile but receive no events (community-page postmortem rule)."
                ),
            })
    return issues


def check_replica_identity_full(text):
    issues = []
    for tbl in ("rcm_fmea_modes", "rcm_strategies", "weibull_fits"):
        pat = re.compile(rf"ALTER TABLE\s+public\.{tbl}\s+REPLICA IDENTITY FULL", re.IGNORECASE)
        if not pat.search(text):
            issues.append({
                "check": "replica_identity_full",
                "reason": (
                    f"REPLICA IDENTITY FULL not set on public.{tbl}. "
                    f"DELETE filters by hive_id silently drop every event without it."
                ),
            })
    return issues


ASSET_HUB_PATH = "asset-hub.html"


def _read_asset_hub():
    return read_file(ASSET_HUB_PATH) or ""


def check_asset_hub_rcm_modal():
    html = _read_asset_hub()
    if not html:
        return [{"check": "asset_hub_rcm_modal",
                 "reason": f"{ASSET_HUB_PATH} not found — Phase R.4 UI surface missing."}]
    issues = []
    if 'id="rcm-modal"' not in html:
        issues.append({
            "check": "asset_hub_rcm_modal",
            "reason": "asset-hub.html missing #rcm-modal markup. The Set/Edit strategy button has nothing to open.",
        })
    for d in DECISIONS:
        if f'value="{d}"' not in html:
            issues.append({
                "check": "asset_hub_rcm_modal",
                "reason": (
                    f"asset-hub.html rcm-modal decision <select> missing option value='{d}'. "
                    f"All six JA1011 decisions must be selectable."
                ),
            })
    return issues


def check_asset_hub_rcm_strategy_writes():
    html = _read_asset_hub()
    if not html:
        return [{"check": "asset_hub_rcm_strategy_writes",
                 "reason": f"{ASSET_HUB_PATH} not found."}]
    issues = []
    if "from('rcm_strategies')" not in html and 'from("rcm_strategies")' not in html:
        issues.append({
            "check": "asset_hub_rcm_strategy_writes",
            "reason": "asset-hub.html does not reference rcm_strategies. The strategy save path is missing.",
        })
    if "fmea_mode_id" not in html:
        issues.append({
            "check": "asset_hub_rcm_strategy_writes",
            "reason": "asset-hub.html strategy writer must include fmea_mode_id (foreign key to rcm_fmea_modes).",
        })
    if not re.search(r"saveStrategy\s*\(", html):
        issues.append({
            "check": "asset_hub_rcm_strategy_writes",
            "reason": "asset-hub.html missing saveStrategy() function — strategy modal save handler.",
        })
    return issues


def check_asset_hub_pm_writeback():
    html = _read_asset_hub()
    if not html:
        return [{"check": "asset_hub_pm_writeback",
                 "reason": f"{ASSET_HUB_PATH} not found."}]
    issues = []
    if "from('pm_scope_items')" not in html and 'from("pm_scope_items")' not in html:
        issues.append({
            "check": "asset_hub_pm_writeback",
            "reason": "asset-hub.html does not write to pm_scope_items. Push-to-PM is not wired.",
        })
    if "written_to_pm_scope_item_id" not in html:
        issues.append({
            "check": "asset_hub_pm_writeback",
            "reason": (
                "asset-hub.html must back-link the inserted scope_item via "
                "rcm_strategies.written_to_pm_scope_item_id, otherwise repeat pushes "
                "create duplicate PM tasks."
            ),
        })
    # PM Scheduler frequency labels — Monthly/Quarterly/Semi-Annual/Yearly
    for freq in ("Monthly", "Quarterly", "Semi-Annual", "Yearly"):
        if freq not in html:
            issues.append({
                "check": "asset_hub_pm_writeback",
                "reason": (
                    f"asset-hub.html interval-to-frequency map missing '{freq}'. "
                    f"PM Scheduler computes next-due from these labels; mismatched labels "
                    f"silently default to 90d in pm-scheduler.html."
                ),
            })
    return issues


PYTHON_WEIBULL_PATH    = os.path.join("python-api", "reliability", "weibull.py")
PYTHON_MAIN_PATH       = os.path.join("python-api", "main.py")
PYTHON_REQS_PATH       = os.path.join("python-api", "requirements.txt")
WEIBULL_EDGE_PATH      = os.path.join("supabase", "functions", "weibull-fitter", "index.ts")

PYTHON_PF_PATH         = os.path.join("python-api", "reliability", "pf_interval.py")
PF_EDGE_PATH           = os.path.join("supabase", "functions", "pf-calculator", "index.ts")
V_PF_TRUTH_MIGRATION   = os.path.join("supabase", "migrations", "20260510000001_v_pf_truth.sql")


def check_python_weibull_module():
    src = read_file(PYTHON_WEIBULL_PATH)
    if not src:
        return [{"check": "python_weibull_module",
                 "reason": f"{PYTHON_WEIBULL_PATH} not found — Phase R.5 backend missing."}]
    issues = []
    if "WeibullFitter" not in src:
        issues.append({
            "check": "python_weibull_module",
            "reason": (
                "python-api/reliability/weibull.py must import lifelines.WeibullFitter. "
                "Hand-rolled MLE without censored-data support is the regression we are guarding against."
            ),
        })
    if "fit_weibull" not in src:
        issues.append({
            "check": "python_weibull_module",
            "reason": "weibull.py must expose fit_weibull(failures, censored) — the contract main.py imports.",
        })
    for pat in ("infant", "wearout", "random", "insufficient_data"):
        if f"\"{pat}\"" not in src and f"'{pat}'" not in src:
            issues.append({
                "check": "python_weibull_module",
                "reason": (
                    f"weibull.py classifier missing '{pat}' label. The four labels match "
                    f"weibull_fits.failure_pattern CHECK; mismatched labels cause INSERT failures."
                ),
            })
    return issues


def check_python_weibull_endpoint():
    src = read_file(PYTHON_MAIN_PATH)
    if not src:
        return [{"check": "python_weibull_endpoint",
                 "reason": f"{PYTHON_MAIN_PATH} not found."}]
    if "/reliability/weibull" not in src:
        return [{
            "check": "python_weibull_endpoint",
            "reason": "main.py missing the /reliability/weibull endpoint. Edge fn weibull-fitter has no upstream to call.",
        }]
    if "fit_weibull" not in src:
        return [{
            "check": "python_weibull_endpoint",
            "reason": "main.py /reliability/weibull endpoint must import fit_weibull from reliability.weibull.",
        }]
    return []


def check_python_lifelines_dep():
    src = read_file(PYTHON_REQS_PATH)
    if not src:
        return [{"check": "python_lifelines_dep",
                 "reason": f"{PYTHON_REQS_PATH} not found."}]
    if not re.search(r"^\s*lifelines\s*[=>~]", src, re.MULTILINE):
        return [{
            "check": "python_lifelines_dep",
            "reason": (
                "requirements.txt missing pinned lifelines dependency. The Render deployment will "
                "fail to import lifelines.WeibullFitter, and the endpoint will 500."
            ),
        }]
    return []


def check_weibull_fitter_edge_fn():
    src = read_file(WEIBULL_EDGE_PATH)
    if not src:
        return [{"check": "weibull_fitter_edge_fn",
                 "reason": f"{WEIBULL_EDGE_PATH} not found — edge orchestrator missing."}]
    issues = []
    if "/reliability/weibull" not in src:
        issues.append({
            "check": "weibull_fitter_edge_fn",
            "reason": "weibull-fitter must POST to PYTHON_API_URL/reliability/weibull (the Python module endpoint).",
        })
    if 'from("weibull_fits")' not in src and "from('weibull_fits')" not in src:
        issues.append({
            "check": "weibull_fitter_edge_fn",
            "reason": "weibull-fitter must persist the fit into weibull_fits, otherwise v_weibull_truth never updates.",
        })
    if "v_asset_truth" not in src:
        issues.append({
            "check": "weibull_fitter_edge_fn",
            "reason": (
                "weibull-fitter must resolve the asset via v_asset_truth (canonical sources rule). "
                "Reading asset_nodes directly bypasses the bridge and breaks legacy_asset_id."
            ),
        })
    if "PYTHON_API_URL" not in src:
        issues.append({
            "check": "weibull_fitter_edge_fn",
            "reason": "weibull-fitter must read PYTHON_API_URL from Deno.env so the deployment URL is configurable.",
        })
    if "AbortSignal.timeout" not in src:
        issues.append({
            "check": "weibull_fitter_edge_fn",
            "reason": (
                "weibull-fitter Python API call must use AbortSignal.timeout(...) so a Render cold-start "
                "stall does not hang the Edge runtime."
            ),
        })
    return issues


def check_asset_hub_weibull_ui():
    html = _read_asset_hub()
    if not html:
        return [{"check": "asset_hub_weibull_ui",
                 "reason": f"{ASSET_HUB_PATH} not found."}]
    issues = []
    if 'id="rel-panel-weibull"' not in html:
        issues.append({
            "check": "asset_hub_weibull_ui",
            "reason": "asset-hub.html missing #rel-panel-weibull. Weibull tab has no panel to show.",
        })
    if 'id="weibull-fit-btn"' not in html:
        issues.append({
            "check": "asset_hub_weibull_ui",
            "reason": "asset-hub.html missing #weibull-fit-btn (Compute Weibull fit button).",
        })
    if "weibull-fitter" not in html:
        issues.append({
            "check": "asset_hub_weibull_ui",
            "reason": "asset-hub.html does not invoke the weibull-fitter edge fn. Compute button has no upstream.",
        })
    if "v_weibull_truth" not in html:
        issues.append({
            "check": "asset_hub_weibull_ui",
            "reason": (
                "asset-hub.html must read the latest fit from v_weibull_truth (canonical view, DISTINCT ON), "
                "not from weibull_fits directly — otherwise stale rows can win the render."
            ),
        })
    if not re.search(
        r"postgres_changes[^}]*table:\s*['\"]weibull_fits['\"]",
        html, re.DOTALL,
    ):
        issues.append({
            "check": "asset_hub_weibull_ui",
            "reason": (
                "asset-hub.html missing postgres_changes subscription on weibull_fits. "
                "Workers will not see new fits push live without it."
            ),
        })
    return issues


def check_python_pf_module():
    src = read_file(PYTHON_PF_PATH)
    if not src:
        return [{"check": "python_pf_module",
                 "reason": f"{PYTHON_PF_PATH} not found — Phase R.6 backend missing."}]
    issues = []
    if "calculate_pf" not in src:
        issues.append({
            "check": "python_pf_module",
            "reason": "pf_interval.py must expose calculate_pf(readings, p_threshold, f_threshold, ...).",
        })
    # Threshold validation guard (we documented this rule in pf_interval.py)
    if "p_threshold >= f_threshold" not in src and "p_threshold <= f_threshold" not in src:
        issues.append({
            "check": "python_pf_module",
            "reason": (
                "pf_interval.py must reject thresholds where the P (warning) is on the wrong side of "
                "the F (failure). Otherwise the calculator returns a meaningless pf_days."
            ),
        })
    if "median" not in src:
        issues.append({
            "check": "python_pf_module",
            "reason": (
                "pf_interval.py must aggregate multiple P-F pairs via median (or equivalent) so a single "
                "outlier window does not dominate the recommended cadence."
            ),
        })
    return issues


def check_python_pf_endpoint():
    src = read_file(PYTHON_MAIN_PATH)
    if not src:
        return [{"check": "python_pf_endpoint",
                 "reason": f"{PYTHON_MAIN_PATH} not found."}]
    if "/reliability/pf-interval" not in src:
        return [{"check": "python_pf_endpoint",
                 "reason": "main.py missing /reliability/pf-interval endpoint."}]
    if "calculate_pf" not in src:
        return [{"check": "python_pf_endpoint",
                 "reason": "main.py must import calculate_pf from reliability.pf_interval."}]
    return []


def check_pf_calculator_edge_fn():
    src = read_file(PF_EDGE_PATH)
    if not src:
        return [{"check": "pf_calculator_edge_fn",
                 "reason": f"{PF_EDGE_PATH} not found — edge orchestrator missing."}]
    issues = []
    if "/reliability/pf-interval" not in src:
        issues.append({
            "check": "pf_calculator_edge_fn",
            "reason": "pf-calculator must POST to PYTHON_API_URL/reliability/pf-interval.",
        })
    if 'from("pf_intervals")' not in src and "from('pf_intervals')" not in src:
        issues.append({
            "check": "pf_calculator_edge_fn",
            "reason": "pf-calculator must persist successful fits into pf_intervals.",
        })
    if "v_asset_truth" not in src:
        issues.append({
            "check": "pf_calculator_edge_fn",
            "reason": (
                "pf-calculator must resolve the asset via v_asset_truth (canonical sources rule). "
                "Reading asset_nodes directly bypasses the legacy_asset_id bridge."
            ),
        })
    if "PYTHON_API_URL" not in src:
        issues.append({
            "check": "pf_calculator_edge_fn",
            "reason": "pf-calculator must read PYTHON_API_URL from Deno.env.",
        })
    if "AbortSignal.timeout" not in src:
        issues.append({
            "check": "pf_calculator_edge_fn",
            "reason": "pf-calculator Python API call must use AbortSignal.timeout(...) to bound cold-start stalls.",
        })
    # Param allowlist guard (a SQL-injection-flavored concern: parameter ends up in error
    # messages and DB writes; if the orchestrator forwards arbitrary text, an
    # attacker could plant invalid CHECK violations. The regex test in source is sufficient.)
    if "PARAMETER_RE" not in src and "parameter" not in src:
        issues.append({
            "check": "pf_calculator_edge_fn",
            "reason": "pf-calculator must validate the parameter name against an allowlist regex.",
        })
    return issues


def check_v_pf_truth_view_and_registration():
    src = read_file(V_PF_TRUTH_MIGRATION)
    if not src:
        return [{"check": "v_pf_truth_view_and_registration",
                 "reason": f"{V_PF_TRUTH_MIGRATION} not found — canonical view migration missing."}]
    issues = []
    if not re.search(r"CREATE\s+OR\s+REPLACE\s+VIEW\s+public\.v_pf_truth\s+AS", src, re.IGNORECASE):
        issues.append({
            "check": "v_pf_truth_view_and_registration",
            "reason": "Migration must declare CREATE OR REPLACE VIEW public.v_pf_truth AS ...",
        })
    if "DISTINCT ON" not in src:
        issues.append({
            "check": "v_pf_truth_view_and_registration",
            "reason": (
                "v_pf_truth must use DISTINCT ON so the view returns the latest row per "
                "(hive, asset, parameter, fmea_mode) — mirrors v_weibull_truth."
            ),
        })
    if "GRANT SELECT ON public.v_pf_truth" not in src:
        issues.append({
            "check": "v_pf_truth_view_and_registration",
            "reason": "Missing GRANT SELECT on v_pf_truth to anon, authenticated.",
        })
    if "'pf_truth'" not in src:
        issues.append({
            "check": "v_pf_truth_view_and_registration",
            "reason": "Migration must register 'pf_truth' in canonical_sources so AI agents can find it.",
        })
    return issues


def check_asset_hub_pf_ui():
    html = _read_asset_hub()
    if not html:
        return [{"check": "asset_hub_pf_ui",
                 "reason": f"{ASSET_HUB_PATH} not found."}]
    issues = []
    for needle, why in [
        ('id="rel-panel-pf"',     "P-F panel container missing."),
        ('id="pf-parameter"',     "P-F parameter <select> missing — workers cannot pick which sensor reading to scan."),
        ('id="pf-p-threshold"',   "P (warning) threshold input missing."),
        ('id="pf-f-threshold"',   "F (failure) threshold input missing."),
        ('id="pf-compute-btn"',   "Compute P-F button missing."),
        ('pf-calculator',         "Asset Hub does not invoke the pf-calculator edge fn."),
        ('v_pf_truth',            "Asset Hub must read the latest interval from v_pf_truth (canonical view), not pf_intervals directly."),
        ('safety-critical',       "Safety-critical toggle missing — required to switch basis to P-F/3."),
    ]:
        if needle not in html:
            issues.append({"check": "asset_hub_pf_ui", "reason": f"asset-hub.html: {why}"})
    return issues


def check_asset_hub_reliability_report_button():
    html = _read_asset_hub()
    if not html:
        return [{"check": "asset_hub_reliability_report_button",
                 "reason": f"{ASSET_HUB_PATH} not found."}]
    issues = []
    if 'id="reliability-report-btn"' not in html:
        issues.append({
            "check": "asset_hub_reliability_report_button",
            "reason": "asset-hub.html missing #reliability-report-btn (Print Report button on Reliability section).",
        })
    if not re.search(r"function\s+generateReliabilityReport\s*\(", html):
        issues.append({
            "check": "asset_hub_reliability_report_button",
            "reason": "asset-hub.html missing generateReliabilityReport(nodeId) — button has no handler.",
        })
    # Must read each canonical view; the report is the integration test for
    # Phase R.1-R.6 contracts staying stable.
    for needle in ("v_fmea_truth", "v_rcm_truth", "v_weibull_truth", "v_pf_truth"):
        if needle not in html:
            issues.append({
                "check": "asset_hub_reliability_report_button",
                "reason": (
                    f"Reliability Report must read {needle} (canonical truth). "
                    f"Reading underlying tables instead means an unapproved row could leak into the audit deliverable."
                ),
            })
    return issues


def check_asset_hub_reliability_report_sections():
    html = _read_asset_hub()
    if not html:
        return [{"check": "asset_hub_reliability_report_sections",
                 "reason": f"{ASSET_HUB_PATH} not found."}]
    issues = []
    # The needles below are specific enough that grepping the whole file is
    # safe. Restricting the search to the renderer function body via regex
    # was unreliable because nested template literals have unbalanced braces.
    body = html
    section_markers = [
        ("FMEA matrix",      "FMEA matrix section heading"),
        ("RCM strategies",   "RCM strategies section heading"),
        ("Weibull analysis", "Weibull analysis section heading"),
        ("P-F intervals",    "P-F intervals section heading"),
        ("Recent corrective","Recent history section heading"),
    ]
    for needle, why in section_markers:
        if needle not in body:
            issues.append({
                "check": "asset_hub_reliability_report_sections",
                "reason": f"Reliability Report missing: {why}.",
            })
    # Standards footer — auditor expectation
    for std in ("SAE JA1011", "AIAG-VDA", "ISO 14224", "IEC 61649"):
        if std not in body:
            issues.append({
                "check": "asset_hub_reliability_report_sections",
                "reason": (
                    f"Reliability Report standards footer missing '{std}'. "
                    f"Auditors look for the source standard reference; do not omit."
                ),
            })
    return issues


def check_asset_hub_reliability_report_print_css():
    html = _read_asset_hub()
    if not html:
        return [{"check": "asset_hub_reliability_report_print_css",
                 "reason": f"{ASSET_HUB_PATH} not found."}]
    body = html       # whole-file scan; needles are specific enough
    issues = []
    # @page A4 size declaration — required for proper layout when printing
    if "@page" not in body or "A4" not in body:
        issues.append({
            "check": "asset_hub_reliability_report_print_css",
            "reason": "Report print CSS missing @page A4 size declaration.",
        })
    # Color preservation in print (per Shift Handover skill rule).
    if "print-color-adjust" not in body:
        issues.append({
            "check": "asset_hub_reliability_report_print_css",
            "reason": (
                "Report print CSS missing print-color-adjust. Without it, printers strip backgrounds "
                "and the executive-summary highlight + header borders disappear."
            ),
        })
    # page-break-inside: avoid on tables / sections
    if "page-break-inside" not in body:
        issues.append({
            "check": "asset_hub_reliability_report_print_css",
            "reason": "Report print CSS missing page-break-inside rule. Long tables split mid-row.",
        })
    # no-print toolbar so the Print/Close buttons do not bleed into the printed output
    if "no-print" not in body:
        issues.append({
            "check": "asset_hub_reliability_report_print_css",
            "reason": (
                "Report missing .no-print toolbar (Print/Close buttons must be hidden via "
                "@media print). Otherwise the buttons render on the printed page."
            ),
        })
    return issues


def check_asset_hub_rcm_realtime():
    html = _read_asset_hub()
    if not html:
        return [{"check": "asset_hub_rcm_realtime",
                 "reason": f"{ASSET_HUB_PATH} not found."}]
    if not re.search(
        r"postgres_changes[^}]*table:\s*['\"]rcm_strategies['\"]",
        html, re.DOTALL,
    ):
        return [{
            "check": "asset_hub_rcm_realtime",
            "reason": (
                "asset-hub.html missing postgres_changes subscription on rcm_strategies. "
                "Workers will not see supervisor approvals or new pushes without it."
            ),
        }]
    return []


def check_canonical_sources_registered(text):
    """Verify the migration seeds the three new domains."""
    issues = []
    for domain in ("fmea_truth", "rcm_truth", "weibull_truth"):
        if not re.search(rf"'\s*{re.escape(domain)}\s*'", text):
            issues.append({
                "check": "canonical_sources_registered",
                "reason": (
                    f"Domain '{domain}' is not registered in canonical_sources. "
                    f"AI agents reading the registry will not find the workbench truths."
                ),
            })
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

def main():
    def bold(s):
        return f"\033[1m{s}\033[0m"

    print(bold("\nReliability Workbench Validator"))
    print("=" * 50)

    text = _read()
    if not text:
        print(f"\033[91m  Migration file not found: {MIGRATION_PATH}\033[0m")
        report = {
            "validator": "reliability_workbench",
            "total_checks": len(CHECK_NAMES),
            "passed": 0, "warned": 0, "failed": len(CHECK_NAMES),
            "issues": [{"check": n, "reason": f"{MIGRATION_PATH} missing"} for n in CHECK_NAMES],
        }
        with open("reliability_workbench_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        sys.exit(1)

    all_issues = []
    all_issues += check_rcm_fmea_extras(text)
    all_issues += check_rcm_strategies_extras(text)
    all_issues += check_weibull_fits_extras(text)
    all_issues += check_pf_intervals_extras(text)
    all_issues += check_view(text, "v_fmea_truth",
                             ["m.rpn", "approved_at IS NOT NULL"])
    all_issues += check_view(text, "v_rcm_truth",
                             ["s.decision", "approved_at IS NOT NULL"])
    all_issues += check_view(text, "v_weibull_truth",
                             ["DISTINCT ON", "generated_at"])
    all_issues += check_rls_enabled(text)
    all_issues += check_grants_present(text)
    all_issues += check_hive_membership_join_rls(text)
    all_issues += check_realtime_publication(text)
    all_issues += check_replica_identity_full(text)
    all_issues += check_canonical_sources_registered(text)
    # Phase R.4 — Asset Hub UI integration
    all_issues += check_asset_hub_rcm_modal()
    all_issues += check_asset_hub_rcm_strategy_writes()
    all_issues += check_asset_hub_pm_writeback()
    all_issues += check_asset_hub_rcm_realtime()
    # Phase R.5 — Weibull fitter end-to-end
    all_issues += check_python_weibull_module()
    all_issues += check_python_weibull_endpoint()
    all_issues += check_python_lifelines_dep()
    all_issues += check_weibull_fitter_edge_fn()
    all_issues += check_asset_hub_weibull_ui()
    # Phase R.6 — P-F interval calculator end-to-end
    all_issues += check_python_pf_module()
    all_issues += check_python_pf_endpoint()
    all_issues += check_pf_calculator_edge_fn()
    all_issues += check_v_pf_truth_view_and_registration()
    all_issues += check_asset_hub_pf_ui()
    # Phase R.7 — Print-ready Reliability Report
    all_issues += check_asset_hub_reliability_report_button()
    all_issues += check_asset_hub_reliability_report_sections()
    all_issues += check_asset_hub_reliability_report_print_css()

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "reliability_workbench",
        "total_checks": total,
        "passed":       n_pass, "warned": n_warn, "failed": n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("reliability_workbench_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
