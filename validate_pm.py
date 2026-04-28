"""
PM Scheduler Validator — WorkHive Platform
===========================================
Four-layer validation of pm-scheduler.html:

  Layer 1 — Config alignment
    1.  FREQ_DAYS alignment         — FREQ_DAYS keys match freqOrder dropdown options
    2.  PM template coverage        — every PM_TEMPLATES category has a PM_CAT_TO_LOG_CAT entry
    3.  PM_CAT_TO_LOG_CAT values    — all target categories are valid logbook categories

  Layer 2 — Payload completeness
    4.  compPayload required fields — pm_completions insert has all required columns
    5.  scopePayload required fields — pm_scope_items insert has item_text, frequency, hive_id
    6.  logbook PM fields           — logbook insert from PM has pm_completion_id, closed_at, hive_id

  Layer 3 — Logic correctness
    7.  Due date midnight norm      — getItemStatus() sets today to midnight (no time-of-day bias)
    8.  Auth gate present           — WORKER_NAME redirect before any DB access
    9.  Supervisor gate asset edit  — saveEditPMAsset checks HIVE_ROLE !== 'supervisor'
    10. Supervisor gate asset add   — addPMAsset checks HIVE_ROLE in hive mode
    11. deleteAsset scoped          — delete uses hive_id or worker_name guard, not bare id only

  Layer 4 — Security / XSS
    12. escHtml in render           — renderAssetCard and task rows use escHtml on user fields
    13. Realtime hive filter        — subscribeRealtime scopes to hive_id=eq. filter

Usage:  python validate_pm.py
Output: pm_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, extract_js_object_keys, format_result

PM_PAGE = "pm-scheduler.html"

VALID_LOGBOOK_CATEGORIES = [
    "Mechanical", "Electrical", "Hydraulic", "Pneumatic",
    "Instrumentation", "Lubrication", "Other",
]

PM_COMPLETION_REQUIRED = ["asset_id", "scope_item_id", "hive_id", "worker_name", "status", "completed_at"]
SCOPE_ITEM_REQUIRED    = ["asset_id", "hive_id", "item_text", "frequency"]
LOGBOOK_PM_REQUIRED    = ["pm_completion_id", "closed_at", "hive_id", "worker_name", "status"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_dict_kv(content, const_name):
    m = re.search(rf"(?:const|var|let)\s+{re.escape(const_name)}\s*=\s*\{{([^}}]+)\}}", content, re.DOTALL)
    if not m:
        return {}
    return {k: v for k, v in re.findall(r"['\"]([^'\"]+)['\"]\s*:\s*['\"]([^'\"]+)['\"]", m.group(1))}


def extract_array_values(content, var_name):
    m = re.search(rf"(?:const|var|let)\s+{re.escape(var_name)}\s*=\s*\[([^\]]+)\]", content, re.DOTALL)
    if not m:
        # Also try inline assignment (no const/var/let)
        m = re.search(rf"{re.escape(var_name)}\s*=\s*\[([^\]]+)\]", content, re.DOTALL)
    if not m:
        return []
    return re.findall(r"['\"]([^'\"]+)['\"]", m.group(1))


def extract_object_top_level_keys(content, const_name):
    m = re.search(rf"(?:const|var|let)\s+{re.escape(const_name)}\s*=\s*\{{", content)
    if not m:
        return []
    start = m.end() - 1
    depth = 0
    for i in range(start, min(start + 20000, len(content))):
        if content[i] == '{':
            depth += 1
        elif content[i] == '}':
            depth -= 1
            if depth == 0:
                block = content[start + 1:i]
                return re.findall(r"^\s*['\"]([^'\"]+)['\"]\s*:", block, re.MULTILINE)
    return []


def extract_freq_days_keys(content):
    m = re.search(r"FREQ_DAYS\s*=\s*\{([^}]+)\}", content)
    if not m:
        return set()
    return set(re.findall(r"['\"]([^'\"]+)['\"]\s*:", m.group(1)))


def extract_payload_fields(content, payload_name, pattern_override=None):
    pattern = pattern_override or rf"const {re.escape(payload_name)}\s*=\s*\{{([^}}]{{0,1000}})\}}"
    m = re.search(pattern, content, re.DOTALL)
    if not m:
        return set()
    block = re.sub(r'\$\{[^}]*\}', '', m.group(1))
    return set(re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*:', block))


# ── Layer 1: Config alignment ─────────────────────────────────────────────────

def check_freq_days_alignment(content, page):
    freq_days_keys = extract_freq_days_keys(content)
    freq_order     = extract_array_values(content, "freqOrder")
    if not freq_days_keys:
        return [{"check": "freq_days_alignment", "page": page,
                 "reason": "FREQ_DAYS constant not found"}]
    freq_set = set(freq_order)
    issues   = []
    extra    = freq_days_keys - freq_set
    missing  = freq_set - freq_days_keys
    if extra:
        issues.append({"check": "freq_days_alignment", "page": page,
                       "reason": f"FREQ_DAYS has keys not in freqOrder: {sorted(extra)} — due dates compute but UI never shows these frequencies"})
    if missing:
        issues.append({"check": "freq_days_alignment", "page": page,
                       "reason": f"freqOrder has values not in FREQ_DAYS: {sorted(missing)} — items with these frequencies fall back to 90-day default silently"})
    return issues


def check_pm_template_coverage(content, page):
    template_cats = extract_object_top_level_keys(content, "PM_TEMPLATES")
    cat_to_log    = extract_dict_kv(content, "PM_CAT_TO_LOG_CAT")
    if not template_cats:
        return [{"check": "pm_template_coverage", "page": page, "reason": "PM_TEMPLATES not found"}]
    if not cat_to_log:
        return [{"check": "pm_template_coverage", "page": page, "reason": "PM_CAT_TO_LOG_CAT not found"}]
    issues = []
    for cat in template_cats:
        if cat not in cat_to_log:
            issues.append({"check": "pm_template_coverage", "page": page, "category": cat,
                           "reason": f"PM_TEMPLATES has '{cat}' but PM_CAT_TO_LOG_CAT has no mapping — PM completions for this category use fallback 'Mechanical'"})
    return issues


def check_pm_cat_to_log_values(content, page):
    cat_to_log = extract_dict_kv(content, "PM_CAT_TO_LOG_CAT")
    if not cat_to_log:
        return [{"check": "pm_cat_to_log_values", "page": page, "reason": "PM_CAT_TO_LOG_CAT not found"}]
    issues = []
    for pm_cat, log_cat in cat_to_log.items():
        if log_cat not in VALID_LOGBOOK_CATEGORIES:
            issues.append({"check": "pm_cat_to_log_values", "page": page,
                           "pm_category": pm_cat, "maps_to": log_cat,
                           "reason": f"'{pm_cat}' maps to '{log_cat}' — not in logbook category dropdown, entries invisible in filters"})
    return issues


# ── Layer 2: Payload completeness ─────────────────────────────────────────────

def check_comp_payload_fields(content, page):
    fields = extract_payload_fields(content, "compPayload")
    if not fields:
        return [{"check": "comp_payload_fields", "page": page, "reason": "compPayload not found"}]
    missing = [f for f in PM_COMPLETION_REQUIRED if f not in fields]
    return [{"check": "comp_payload_fields", "page": page, "missing_field": f,
             "reason": f"compPayload missing '{f}' — pm_completions record will have null {f}"}
            for f in missing]


def check_scope_payload_fields(content, page):
    m = re.search(r"const scopePayload\s*=\s*items\.map\([^{]*\{([^}]+)\}", content, re.DOTALL)
    if not m:
        return [{"check": "scope_payload_fields", "page": page, "reason": "scopePayload not found"}]
    block  = re.sub(r'\$\{[^}]*\}', '', m.group(1))
    fields = set(re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*:', block))
    missing = [f for f in SCOPE_ITEM_REQUIRED if f not in fields]
    return [{"check": "scope_payload_fields", "page": page, "missing_field": f,
             "reason": f"scopePayload missing '{f}' — pm_scope_items record will have null {f}"}
            for f in missing]


def check_logbook_pm_fields(content, page):
    """
    When submitCompletion saves a logbook entry (logAlso path),
    the logPayload must include pm_completion_id, closed_at, hive_id, worker_name, status.
    pm_completion_id links the logbook entry back to the PM record for analytics.
    """
    m = re.search(r"const logPayload\s*=\s*\{([^}]{0,800})\}", content, re.DOTALL)
    if not m:
        return [{"check": "logbook_pm_fields", "page": page,
                 "reason": "logPayload not found in submitCompletion — PM-to-logbook cross-reference cannot be verified"}]
    block  = re.sub(r'\$\{[^}]*\}', '', m.group(1))
    fields = set(re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*:', block))
    missing = [f for f in LOGBOOK_PM_REQUIRED if f not in fields]
    return [{"check": "logbook_pm_fields", "page": page, "missing_field": f,
             "reason": f"logPayload missing '{f}' — PM-created logbook entry will have null {f}"}
            for f in missing]


# ── Layer 3: Logic correctness ────────────────────────────────────────────────

def check_midnight_normalization(content, page):
    if not re.search(r"function getItemStatus\b[\s\S]{0,300}?today\.setHours\(0", content):
        return [{"check": "midnight_normalization", "page": page,
                 "reason": "getItemStatus() does not call today.setHours(0,0,0,0) — overdue status varies by time of day"}]
    return []


def check_auth_gate(content, page):
    if not re.search(r"if\s*\(\s*!\s*WORKER_NAME\s*\)", content):
        return [{"check": "auth_gate", "page": page,
                 "reason": "WORKER_NAME auth gate missing — unauthenticated users can access PM scheduler"}]
    return []


def check_supervisor_gate_edit(content, page):
    m = re.search(r"async function saveEditPMAsset\s*\(", content)
    if not m:
        return [{"check": "supervisor_gate_edit", "page": page,
                 "reason": "saveEditPMAsset() not found"}]
    body = content[m.start():m.start() + 500]
    if not re.search(r"HIVE_ROLE\s*!==?\s*['\"]supervisor['\"]", body):
        return [{"check": "supervisor_gate_edit", "page": page,
                 "reason": "saveEditPMAsset() missing HIVE_ROLE supervisor check — workers can edit PM assets in hive mode"}]
    return []


def check_supervisor_gate_add(content, page):
    """addPMAsset or the asset registration path must check HIVE_ROLE in hive mode."""
    add_pattern = re.search(r"HIVE_ID\s*&&\s*HIVE_ROLE\s*!==?\s*['\"]supervisor['\"][\s\S]{0,100}?add|add[\s\S]{0,100}?HIVE_ID\s*&&\s*HIVE_ROLE\s*!==?\s*['\"]supervisor['\"]", content)
    if not add_pattern:
        # Try the specific pattern: showToast for supervisors only in add context
        if not re.search(r"Only supervisors can add PM", content):
            return [{"check": "supervisor_gate_add", "page": page,
                     "reason": "No supervisor role check found for adding PM assets — workers may add assets directly in hive mode"}]
    return []


def check_delete_asset_scoped(content, page):
    m = re.search(r"async function deleteAsset\s*\(", content)
    if not m:
        return [{"check": "delete_asset_scoped", "page": page,
                 "reason": "deleteAsset() function not found"}]
    body = content[m.start():m.start() + 400]
    has_hive_scope   = bool(re.search(r"\.eq\s*\(['\"]hive_id['\"]", body))
    has_worker_scope = bool(re.search(r"\.eq\s*\(['\"]worker_name['\"]", body))
    if not has_hive_scope and not has_worker_scope:
        return [{"check": "delete_asset_scoped", "page": page,
                 "reason": "deleteAsset() does not scope by hive_id or worker_name — bare eq('id',...) allows deleting any asset by UUID"}]
    return []


# ── Layer 4: Security / XSS ───────────────────────────────────────────────────

def check_esc_html_in_render(content, page):
    if "escHtml" not in content:
        return [{"check": "esc_html_render", "page": page,
                 "reason": "escHtml not found in pm-scheduler.html — asset names and task text render as raw HTML"}]
    # Check that escHtml is used near asset_name and item_text rendering
    issues = []
    if not re.search(r"escHtml\s*\(\s*asset\.asset_name", content):
        issues.append({"check": "esc_html_render", "page": page,
                       "reason": "escHtml not applied to asset.asset_name in render — malicious asset names can inject HTML"})
    if not re.search(r"escHtml\s*\(\s*item\.item_text", content):
        issues.append({"check": "esc_html_render", "page": page,
                       "reason": "escHtml not applied to item.item_text in render — malicious task text can inject HTML"})
    return issues


def check_realtime_hive_filter(content, page):
    m = re.search(r"function subscribeRealtime\s*\(", content)
    if not m:
        return [{"check": "realtime_hive_filter", "page": page,
                 "reason": "subscribeRealtime() not found — cannot verify hive filter on realtime channel"}]
    body = content[m.start():m.start() + 600]
    if not re.search(r"hive_id\s*=\s*eq\.", body):
        return [{"check": "realtime_hive_filter", "page": page,
                 "reason": "subscribeRealtime() does not use 'hive_id=eq.' filter — all hives receive each other's PM completion events"}]
    return []


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    # L1
    "freq_days_alignment", "pm_template_coverage", "pm_cat_to_log_values",
    # L2
    "comp_payload_fields", "scope_payload_fields", "logbook_pm_fields",
    # L3
    "midnight_normalization", "auth_gate",
    "supervisor_gate_edit", "supervisor_gate_add", "delete_asset_scoped",
    # L4
    "esc_html_render", "realtime_hive_filter",
]

CHECK_LABELS = {
    # L1
    "freq_days_alignment":   "L1  FREQ_DAYS keys match freqOrder dropdown",
    "pm_template_coverage":  "L1  PM_TEMPLATES categories in PM_CAT_TO_LOG_CAT",
    "pm_cat_to_log_values":  "L1  PM_CAT_TO_LOG_CAT maps to valid logbook categories",
    # L2
    "comp_payload_fields":   "L2  compPayload has all required pm_completions fields",
    "scope_payload_fields":  "L2  scopePayload has all required pm_scope_items fields",
    "logbook_pm_fields":     "L2  logPayload has pm_completion_id + closed_at + hive_id",
    # L3
    "midnight_normalization":"L3  getItemStatus() normalises today to midnight",
    "auth_gate":             "L3  WORKER_NAME auth gate present",
    "supervisor_gate_edit":  "L3  saveEditPMAsset checks HIVE_ROLE supervisor",
    "supervisor_gate_add":   "L3  addPMAsset checks HIVE_ROLE supervisor",
    "delete_asset_scoped":   "L3  deleteAsset scoped by hive_id or worker_name",
    # L4
    "esc_html_render":       "L4  escHtml on asset_name and item_text in render",
    "realtime_hive_filter":  "L4  subscribeRealtime uses hive_id=eq. filter",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nPM Scheduler Validator (4-layer)"))
    print("=" * 55)

    content = read_file(PM_PAGE)
    if not content:
        print(f"  ERROR: {PM_PAGE} not found")
        sys.exit(1)

    all_issues = []

    # L1
    all_issues += check_freq_days_alignment(content, PM_PAGE)
    all_issues += check_pm_template_coverage(content, PM_PAGE)
    all_issues += check_pm_cat_to_log_values(content, PM_PAGE)

    # L2
    all_issues += check_comp_payload_fields(content, PM_PAGE)
    all_issues += check_scope_payload_fields(content, PM_PAGE)
    all_issues += check_logbook_pm_fields(content, PM_PAGE)

    # L3
    all_issues += check_midnight_normalization(content, PM_PAGE)
    all_issues += check_auth_gate(content, PM_PAGE)
    all_issues += check_supervisor_gate_edit(content, PM_PAGE)
    all_issues += check_supervisor_gate_add(content, PM_PAGE)
    all_issues += check_delete_asset_scoped(content, PM_PAGE)

    # L4
    all_issues += check_esc_html_in_render(content, PM_PAGE)
    all_issues += check_realtime_hive_filter(content, PM_PAGE)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "pm",
        "total_checks": total,
        "passed":       n_pass,
        "skipped":      n_skip,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
    }
    with open("pm_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
