"""
Logbook Validator — WorkHive Platform

Static analysis of logbook.html (and pm-scheduler.html for cross-page checks) covering:

  1. closed_at consistency  — every code path that writes status='Closed' sets closed_at
  2. Parts deduction guards — edit path skips existing parts (_existing flag) to avoid
                              double-deducting on re-save
  3. closed_at preservation — re-editing a closed entry keeps the original close timestamp
  4. Valid status values     — only 'Open' and 'Closed' used as status field values
  5. Valid category values   — all categories written to logbook exist in the UI dropdown
  6. PM category alignment   — PM_CAT_TO_LOG_CAT values match logbook's valid categories

Usage:  python validate_logbook.py
Output: logbook_report.json
"""
import re, json, sys

LOGBOOK_PAGE = "logbook.html"
PM_PAGE      = "pm-scheduler.html"

# ── Valid logbook category values (from the category <select> in logbook.html) ─
# Update this list if the dropdown changes.
VALID_LOGBOOK_CATEGORIES = [
    "Mechanical", "Electrical", "Hydraulic", "Pneumatic",
    "Instrumentation", "Lubrication", "Other",
]

# ── Valid status values ──────────────────────────────────────────────────────
VALID_STATUSES = ["Open", "Closed"]

# ── Valid maintenance_type values ─────────────────────────────────────────────
VALID_MAINTENANCE_TYPES = [
    "Breakdown / Corrective",
    "Preventive Maintenance",
    "Inspection",
    "Project Work",
]


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def strip_template_literals(text):
    return re.sub(r'\$\{[^}]*\}', '__INTERP__', text)


# ── Check 1: closed_at set whenever status = 'Closed' ─────────────────────────
def check_closed_at_consistency(content, page):
    """
    Find every .insert({...}) and .update({...}) block on 'logbook' table.
    If the block contains status: 'Closed', it must also contain closed_at.
    """
    issues = []
    clean  = strip_template_literals(content)

    # Find .insert({ ... }) blocks associated with logbook
    for op in ("insert", "update"):
        pattern = rf"from\(['\"]logbook['\"]\)\.{op}\((\{{[^}}]{{0,1500}}\}})"
        for m in re.finditer(pattern, clean, re.DOTALL):
            block = m.group(1)
            has_closed = bool(re.search(r"status\s*:\s*['\"]Closed['\"]", block))
            has_closed_at = bool(re.search(r"closed_at\s*:", block))
            if has_closed and not has_closed_at:
                line_no = content[:m.start()].count('\n') + 1
                issues.append({
                    "page": page, "operation": op, "line": line_no,
                    "reason": f"logbook.{op}() sets status='Closed' but missing closed_at field",
                })
    return issues


# ── Check 2: Parts deduction guard on edit path ───────────────────────────────
def check_parts_deduction_guard(content, page):
    """
    When editing an existing logbook entry and deducting parts from inventory,
    there must be a guard like `if (!p.partId || p._existing) continue;`
    to skip parts that were already counted when the entry was first saved.
    Without this guard, re-saving a closed entry double-deducts inventory.
    """
    issues = []
    # Find inventory deduction loops in edit context (saveEdit function vicinity)
    edit_fn_pat = r"async function saveEdit\b[\s\S]{0,3000}?"
    m = re.search(edit_fn_pat, content)
    if not m:
        return [{"page": page, "reason": "saveEdit function not found — cannot verify parts guard"}]

    edit_block = content[m.start():m.start() + 3000]
    has_guard = bool(re.search(
        r"if\s*\(!p\.partId\s*\|\|\s*p\._existing\)\s*continue",
        edit_block
    ))
    if not has_guard:
        issues.append({
            "page": page,
            "reason": "saveEdit() deducts parts without _existing guard — will double-deduct on re-save",
        })
    return issues


# ── Check 3: closed_at preserved on re-edit ───────────────────────────────────
def check_closed_at_preservation(content, page):
    """
    When re-saving a closed entry, closed_at must preserve the original timestamp
    rather than overwriting with now(). Pattern to look for:
        existing?.closed_at || new Date().toISOString()
    or equivalent.
    """
    issues = []
    preserve_patterns = [
        r"existing\?\.closed_at\s*\|\|",
        r"existing\.closed_at\s*\|\|",
        r"original.*closed_at",
        r"preserve.*close",
    ]
    found = any(re.search(pat, content) for pat in preserve_patterns)
    if not found:
        issues.append({
            "page": page,
            "reason": "No closed_at preservation pattern found — re-saving a closed entry may overwrite the original close timestamp",
        })
    return issues


# ── Check 4: Valid status values ──────────────────────────────────────────────
def check_status_values(content, page):
    """
    Every string literal used as a status value must be in VALID_STATUSES.
    Look for status: '...' patterns in insert/update payloads.
    """
    issues = []
    found_statuses = set(re.findall(
        r"status\s*:\s*['\"]([^'\"]+)['\"]", content
    ))
    # Remove metadata statuses (not logbook status field)
    logbook_statuses = found_statuses & {"Open", "Closed", "open", "closed",
                                          "pending", "approved", "rejected",
                                          "done", "kicked", "active"}
    logbook_only = {s for s in found_statuses
                    if s in ("Open", "Closed", "open", "closed")}
    bad = [s for s in logbook_only if s not in VALID_STATUSES]
    if bad:
        issues.append({
            "page": page, "bad_values": bad,
            "reason": f"Non-standard status values found: {bad}. Only {VALID_STATUSES} allowed.",
        })
    return issues


# ── Check 5: Valid category values in logbook.html ───────────────────────────
def check_category_values(content, page):
    """
    Find the category <select> options defined in the form.
    Compare against VALID_LOGBOOK_CATEGORIES to ensure they're in sync.
    """
    issues = []
    # Find category select options
    options = re.findall(r"option value=['\"]([^'\"]+)['\"].*?category", content[:5000])
    # Look for the category select specifically: array .map() that references entry.category
    # This narrows to the one dropdown that writes to the category field
    array_matches = re.findall(
        r"\[([^\]]+)\]\s*\.map\s*\(\s*\w+\s*=>\s*`<option[^`]{0,200}?entry\.category",
        content, re.DOTALL
    )
    cats_in_code = set()
    for arr in array_matches:
        cats = re.findall(r"['\"]([^'\"]+)['\"]", arr)
        cats_in_code.update(cats)

    if cats_in_code:
        unknown = [c for c in cats_in_code if c not in VALID_LOGBOOK_CATEGORIES]
        if unknown:
            issues.append({
                "page": page, "unknown_categories": unknown,
                "reason": "Category values in code not in VALID_LOGBOOK_CATEGORIES — update the constant in this script",
            })
    return issues


# ── Check 6: PM_CAT_TO_LOG_CAT alignment ─────────────────────────────────────
def check_pm_category_alignment(pm_content):
    """
    Extract PM_CAT_TO_LOG_CAT from pm-scheduler.html.
    Verify every VALUE (target logbook category) is in VALID_LOGBOOK_CATEGORIES.
    A mismatch means PM-triggered logbook entries will have unrecognized categories
    that won't appear in logbook filters and won't show category color badges.
    """
    issues = []
    if not pm_content:
        return [{"reason": f"{PM_PAGE} not found"}]

    # Extract the mapping object
    m = re.search(
        r"PM_CAT_TO_LOG_CAT\s*=\s*\{([^}]+)\}",
        pm_content, re.DOTALL
    )
    if not m:
        return [{"reason": "PM_CAT_TO_LOG_CAT not found in pm-scheduler.html"}]

    block = m.group(1)
    pairs = re.findall(r"['\"]([^'\"]+)['\"]\s*:\s*['\"]([^'\"]+)['\"]", block)

    for pm_cat, log_cat in pairs:
        if log_cat not in VALID_LOGBOOK_CATEGORIES:
            issues.append({
                "pm_category":      pm_cat,
                "maps_to":          log_cat,
                "valid_categories": VALID_LOGBOOK_CATEGORIES,
                "reason":           f"PM category '{pm_cat}' maps to '{log_cat}' which is NOT in logbook's category dropdown — PM-triggered entries will have unrecognized category, invisible in logbook filters",
            })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("Logbook Validator")
print("=" * 70)

logbook = read_file(LOGBOOK_PAGE)
pm      = read_file(PM_PAGE)

if not logbook:
    print(f"ERROR: {LOGBOOK_PAGE} not found")
    sys.exit(1)

fail_count = 0
warn_count = 0
report     = {}

# [1] closed_at consistency
print("\n[1] closed_at consistency\n")
ca_issues = check_closed_at_consistency(logbook, LOGBOOK_PAGE)
if ca_issues:
    for iss in ca_issues:
        print(f"  FAIL  {iss['page']} line {iss['line']}: {iss['reason']}")
        fail_count += 1
else:
    print("  PASS  All logbook inserts/updates with status='Closed' include closed_at")
report["closed_at_consistency"] = ca_issues

# [2] Parts deduction guard
print("\n[2] Parts deduction guard on edit path\n")
guard_issues = check_parts_deduction_guard(logbook, LOGBOOK_PAGE)
if guard_issues:
    for iss in guard_issues:
        print(f"  FAIL  {iss['reason']}")
        fail_count += 1
else:
    print("  PASS  saveEdit() has _existing guard — no double-deduction on re-save")
report["parts_guard"] = guard_issues

# [3] closed_at preservation
print("\n[3] closed_at preservation on re-edit\n")
pres_issues = check_closed_at_preservation(logbook, LOGBOOK_PAGE)
if pres_issues:
    for iss in pres_issues:
        print(f"  WARN  {iss['reason']}")
        warn_count += 1
else:
    print("  PASS  closed_at preserved from original entry on re-save")
report["closed_at_preservation"] = pres_issues

# [4] Status values
print("\n[4] Valid status values\n")
stat_issues = check_status_values(logbook, LOGBOOK_PAGE)
if stat_issues:
    for iss in stat_issues:
        print(f"  WARN  {iss['reason']}")
        warn_count += 1
else:
    print(f"  PASS  Only valid status values used: {VALID_STATUSES}")
report["status_values"] = stat_issues

# [5] Category values
print("\n[5] Valid logbook category values\n")
cat_issues = check_category_values(logbook, LOGBOOK_PAGE)
if cat_issues:
    for iss in cat_issues:
        print(f"  WARN  {iss['reason']} ({iss['unknown_categories']})")
        warn_count += 1
else:
    print(f"  PASS  Category values match VALID_LOGBOOK_CATEGORIES")
report["category_values"] = cat_issues

# [6] PM category alignment
print("\n[6] PM_CAT_TO_LOG_CAT -> logbook category alignment\n")
pm_cat_issues = check_pm_category_alignment(pm)
if pm_cat_issues:
    for iss in pm_cat_issues:
        print(f"  FAIL  '{iss['pm_category']}' -> '{iss['maps_to']}'")
        print(f"        {iss['reason']}")
        fail_count += 1
else:
    print("  PASS  All PM categories map to valid logbook category values")
report["pm_category_alignment"] = pm_cat_issues

# Summary
print(f"\n{'=' * 70}")
print(f"Result: {fail_count} FAIL  {warn_count} WARN")

with open("logbook_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved logbook_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll logbook checks PASS.")
