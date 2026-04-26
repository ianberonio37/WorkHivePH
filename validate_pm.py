"""
PM Validator — WorkHive Platform

Static analysis of pm-scheduler.html covering:

  1. FREQ_DAYS alignment      — FREQ_DAYS keys match frequency dropdown options
  2. PM template coverage     — every PM_TEMPLATES category has a PM_CAT_TO_LOG_CAT entry
  3. PM_CAT_TO_LOG_CAT values — all target categories are valid logbook categories
  4. compPayload required fields — pm_completions insert has all required columns
  5. scopePayload required fields — pm_scope_items insert has item_text and frequency
  6. Due date midnight check  — getItemStatus() normalises today to midnight (no time-of-day bias)
  7. Frequency fallback awareness — calcNextDue fallback value is documented

Usage:  python validate_pm.py
Output: pm_report.json
"""
import re, json, sys

PM_PAGE = "pm-scheduler.html"

# Valid logbook categories (must match VALID_LOGBOOK_CATEGORIES in validate_logbook.py)
VALID_LOGBOOK_CATEGORIES = [
    "Mechanical", "Electrical", "Hydraulic", "Pneumatic",
    "Instrumentation", "Lubrication", "Other",
]

# Required columns for pm_completions (from pm-scheduler canonical insert)
PM_COMPLETION_REQUIRED = ["asset_id", "scope_item_id", "hive_id", "worker_name", "status", "completed_at"]

# Required fields in pm_scope_items insert
SCOPE_ITEM_REQUIRED = ["asset_id", "hive_id", "item_text", "frequency"]


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def extract_dict_keys_and_values(content, const_name):
    """Extract a JS object literal { 'key': 'value', ... } by name."""
    m = re.search(
        rf"(?:const|var|let)\s+{re.escape(const_name)}\s*=\s*\{{([^}}]+)\}}",
        content, re.DOTALL
    )
    if not m:
        return {}
    block = m.group(1)
    pairs = re.findall(r"['\"]([^'\"]+)['\"]\s*:\s*['\"]([^'\"]+)['\"]", block)
    return {k: v for k, v in pairs}


def extract_array_values(content, var_name):
    """Extract a JS array literal ['a', 'b', ...] by variable name or inline."""
    m = re.search(
        rf"(?:const|var|let)\s+{re.escape(var_name)}\s*=\s*\[([^\]]+)\]",
        content, re.DOTALL
    )
    if not m:
        return []
    block = m.group(1)
    return re.findall(r"['\"]([^'\"]+)['\"]", block)


def extract_object_top_level_keys(content, const_name):
    """Get top-level keys from a const object (single or multi-level)."""
    m = re.search(
        rf"(?:const|var|let)\s+{re.escape(const_name)}\s*=\s*\{{",
        content
    )
    if not m:
        return []
    start = m.end() - 1  # position of opening {
    depth = 0
    block_start = start
    for i in range(start, min(start + 20000, len(content))):
        if content[i] == '{':
            depth += 1
        elif content[i] == '}':
            depth -= 1
            if depth == 0:
                block = content[block_start + 1:i]
                keys = re.findall(r"^\s*['\"]([^'\"]+)['\"]\s*:", block, re.MULTILINE)
                return keys
    return []


def extract_freq_days_keys(content):
    """Extract keys from FREQ_DAYS = { 'Key': number, ... }"""
    m = re.search(r"FREQ_DAYS\s*=\s*\{([^}]+)\}", content)
    if not m:
        return set()
    block = m.group(1)
    return set(re.findall(r"['\"]([^'\"]+)['\"]\s*:", block))


def check_freq_days_alignment(content, page):
    """FREQ_DAYS keys must exactly match the frequency dropdown options."""
    issues = []

    freq_days_keys = extract_freq_days_keys(content)
    freq_order = extract_array_values(content, "freqOrder")

    if not freq_days_keys:
        return [{"page": page, "reason": "FREQ_DAYS constant not found"}]
    if not freq_order:
        m2 = re.search(r"freqOrder\s*=\s*\[([^\]]+)\]", content)
        if m2:
            freq_order = re.findall(r"['\"]([^'\"]+)['\"]", m2.group(1))

    freq_order_set = set(freq_order)

    in_days_not_order = freq_days_keys - freq_order_set
    in_order_not_days = freq_order_set - freq_days_keys

    if in_days_not_order:
        issues.append({
            "page": page,
            "reason": f"FREQ_DAYS has keys not in freqOrder: {sorted(in_days_not_order)} — items with these frequencies will show label only, not compute due date correctly",
        })
    if in_order_not_days:
        issues.append({
            "page": page,
            "reason": f"freqOrder has values not in FREQ_DAYS: {sorted(in_order_not_days)} — these frequencies will fall back to 90-day default silently",
        })

    if not issues:
        # Verify fallback value is explicitly coded
        fallback_pat = re.search(r"FREQ_DAYS\[freq\]\s*\|\|\s*(\d+)", content)
        if fallback_pat and fallback_pat.group(1) != "90":
            issues.append({
                "page": page,
                "reason": f"calcNextDue fallback is {fallback_pat.group(1)} days (not 90/Quarterly) — unexpected default",
            })

    return issues


def check_pm_template_coverage(content, page):
    """Every PM_TEMPLATES category must exist in PM_CAT_TO_LOG_CAT."""
    issues = []

    template_cats  = extract_object_top_level_keys(content, "PM_TEMPLATES")
    cat_to_log     = extract_dict_keys_and_values(content, "PM_CAT_TO_LOG_CAT")

    if not template_cats:
        return [{"page": page, "reason": "PM_TEMPLATES not found"}]
    if not cat_to_log:
        return [{"page": page, "reason": "PM_CAT_TO_LOG_CAT not found"}]

    for cat in template_cats:
        if cat not in cat_to_log:
            issues.append({
                "page": page,
                "category": cat,
                "reason": f"PM_TEMPLATES has category '{cat}' but PM_CAT_TO_LOG_CAT has no mapping for it — PM completions for this category will use fallback or 'Mechanical'",
            })

    return issues


def check_pm_cat_to_log_values(content, page):
    """All PM_CAT_TO_LOG_CAT values must be in VALID_LOGBOOK_CATEGORIES."""
    issues = []
    cat_to_log = extract_dict_keys_and_values(content, "PM_CAT_TO_LOG_CAT")

    if not cat_to_log:
        return [{"page": page, "reason": "PM_CAT_TO_LOG_CAT not found"}]

    for pm_cat, log_cat in cat_to_log.items():
        if log_cat not in VALID_LOGBOOK_CATEGORIES:
            issues.append({
                "page": page,
                "pm_category": pm_cat,
                "maps_to": log_cat,
                "reason": f"'{pm_cat}' maps to '{log_cat}' — not in logbook category dropdown, entries will be invisible in filters",
            })

    return issues


def check_comp_payload_fields(content, page):
    """compPayload must include all required pm_completions columns."""
    issues = []
    m = re.search(r"const compPayload\s*=\s*\{([^}]+)\}", content, re.DOTALL)
    if not m:
        return [{"page": page, "reason": "compPayload not found"}]

    block  = re.sub(r'\$\{[^}]*\}', '', m.group(1))
    fields = set(re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*:', block))

    missing = [f for f in PM_COMPLETION_REQUIRED if f not in fields]
    if missing:
        for f in missing:
            issues.append({
                "page": page,
                "missing_field": f,
                "reason": f"compPayload missing '{f}' — pm_completions record will have null {f}",
            })

    return issues


def check_scope_payload_fields(content, page):
    """scopePayload (pm_scope_items insert) must have item_text, frequency, hive_id, asset_id."""
    issues = []
    m = re.search(
        r"const scopePayload\s*=\s*items\.map\([^{]*\{([^}]+)\}",
        content, re.DOTALL
    )
    if not m:
        return [{"page": page, "reason": "scopePayload not found"}]

    block  = re.sub(r'\$\{[^}]*\}', '', m.group(1))
    fields = set(re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*:', block))

    missing = [f for f in SCOPE_ITEM_REQUIRED if f not in fields]
    if missing:
        for f in missing:
            issues.append({
                "page": page,
                "missing_field": f,
                "reason": f"scopePayload missing '{f}' — pm_scope_items record will have null {f}",
            })

    return issues


def check_midnight_normalization(content, page):
    """getItemStatus must normalise today to midnight to avoid time-of-day bias."""
    issues = []
    # Look for today.setHours(0,0,0,0) in getItemStatus context
    m = re.search(r"function getItemStatus\b[\s\S]{0,300}?today\.setHours\(0", content)
    if not m:
        issues.append({
            "page": page,
            "reason": "getItemStatus() does not call today.setHours(0,0,0,0) — overdue status varies by time of day: tasks may flip between overdue/ontrack during the day",
        })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("PM Scheduler Validator")
print("=" * 70)

content = read_file(PM_PAGE)
if not content:
    print(f"ERROR: {PM_PAGE} not found")
    sys.exit(1)

fail_count = 0
warn_count = 0
report     = {}

checks = [
    ("[1] FREQ_DAYS alignment with frequency options",       check_freq_days_alignment(content, PM_PAGE)),
    ("[2] PM_TEMPLATES coverage in PM_CAT_TO_LOG_CAT",       check_pm_template_coverage(content, PM_PAGE)),
    ("[3] PM_CAT_TO_LOG_CAT values are valid logbook cats",  check_pm_cat_to_log_values(content, PM_PAGE)),
    ("[4] compPayload required fields",                      check_comp_payload_fields(content, PM_PAGE)),
    ("[5] scopePayload required fields",                     check_scope_payload_fields(content, PM_PAGE)),
    ("[6] Due date midnight normalisation",                  check_midnight_normalization(content, PM_PAGE)),
]

for label, issues in checks:
    print(f"\n{label}\n")
    if not issues:
        print("  PASS")
    else:
        for iss in issues:
            print(f"  FAIL  {iss.get('page', PM_PAGE)}")
            print(f"        {iss['reason']}")
            fail_count += 1
    report[label] = issues

print(f"\n{'=' * 70}")
print(f"Result: {fail_count} FAIL  {warn_count} WARN")

with open("pm_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved pm_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll PM checks PASS.")
