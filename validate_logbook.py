"""
Logbook Validator — WorkHive Platform
======================================
Four-layer validation of logbook.html + pm-scheduler.html:

  Layer 1 — Data integrity rules
    1.  closed_at consistency         — every write with status='Closed' sets closed_at
    2.  Parts deduction guard         — saveEdit skips _existing parts (no double-deduct)
    3.  closed_at preservation        — re-editing a closed entry keeps original timestamp
    4.  Valid status values           — only 'Open' and 'Closed' used
    5.  Valid category values         — categories match the dropdown
    6.  PM category alignment         — PM_CAT_TO_LOG_CAT maps to valid logbook categories

  Layer 2 — Tenant isolation
    7.  hive_id in txn insert         — inventory_transactions.insert includes hive_id
    8.  delete scoped by worker       — deleteEntry uses .eq('worker_name', WORKER_NAME)
    9.  update scoped by worker       — saveEdit update uses .eq('worker_name', WORKER_NAME)

  Layer 3 — Logic correctness
    10. Auth gate present             — WORKER_NAME redirect before any DB access
    11. maintenance_type values       — types used match VALID_MAINTENANCE_TYPES
    12. qty_after floor               — inventory deduction uses Math.max(0, ...) guard

  Layer 4 — XSS / JS correctness
    13. highlight() calls escHtml     — search highlight function escapes before rendering
    14. No await in non-async cb      — await in regular function() crashes ALL JS on page load

Usage:  python validate_logbook.py
Output: logbook_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

LOGBOOK_PAGE = "logbook.html"
PM_PAGE      = "pm-scheduler.html"

VALID_LOGBOOK_CATEGORIES = [
    "Mechanical", "Electrical", "Hydraulic", "Pneumatic",
    "Instrumentation", "Lubrication", "Other",
]
VALID_STATUSES = ["Open", "Closed"]
VALID_MAINTENANCE_TYPES = [
    "Breakdown / Corrective",
    "Preventive Maintenance",
    "Inspection",
    "Project Work",
]


def strip_template_literals(text):
    return re.sub(r'\$\{[^}]*\}', '__INTERP__', text)


# ── Layer 1: Data integrity ───────────────────────────────────────────────────

def check_closed_at_consistency(content, page):
    issues = []
    clean = strip_template_literals(content)
    for op in ("insert", "update"):
        pattern = rf"from\(['\"]logbook['\"]\)\.{op}\((\{{[^}}]{{0,1500}}\}})"
        for m in re.finditer(pattern, clean, re.DOTALL):
            block = m.group(1)
            if re.search(r"status\s*:\s*['\"]Closed['\"]", block) and \
               not re.search(r"closed_at\s*:", block):
                line_no = content[:m.start()].count('\n') + 1
                issues.append({"check": "closed_at_consistency", "page": page,
                               "operation": op, "line": line_no,
                               "reason": f"logbook.{op}() sets status='Closed' but missing closed_at field"})
    return issues


def check_parts_deduction_guard(content, page):
    m = re.search(r"async function saveEdit\b", content)
    if not m:
        return [{"check": "parts_deduction_guard", "page": page,
                 "reason": "saveEdit() function not found — cannot verify parts deduction guard"}]
    edit_block = content[m.start():m.start() + 3000]
    if not re.search(r"if\s*\(!p\.partId\s*\|\|\s*p\._existing\)\s*continue", edit_block):
        return [{"check": "parts_deduction_guard", "page": page,
                 "reason": "saveEdit() deducts parts without _existing guard — will double-deduct inventory on re-save"}]
    return []


def check_closed_at_preservation(content, page):
    patterns = [
        r"existing\?\.closed_at\s*\|\|",
        r"existing\.closed_at\s*\|\|",
        r"original.*closed_at",
        r"preserve.*close",
    ]
    if not any(re.search(p, content) for p in patterns):
        return [{"check": "closed_at_preservation", "page": page,
                 "reason": "No closed_at preservation pattern found — re-saving a closed entry may overwrite the original close timestamp"}]
    return []


def check_status_values(content, page):
    logbook_only = {s for s in re.findall(r"status\s*:\s*['\"]([^'\"]+)['\"]", content)
                    if s in ("Open", "Closed", "open", "closed")}
    bad = [s for s in logbook_only if s not in VALID_STATUSES]
    if bad:
        return [{"check": "status_values", "page": page, "bad_values": bad,
                 "reason": f"Non-standard status values found: {bad} — only {VALID_STATUSES} allowed"}]
    return []


def check_category_values(content, page):
    array_matches = re.findall(
        r"\[([^\]]+)\]\s*\.map\s*\(\s*\w+\s*=>\s*`<option[^`]{0,200}?entry\.category",
        content, re.DOTALL
    )
    cats = set()
    for arr in array_matches:
        cats.update(re.findall(r"['\"]([^'\"]+)['\"]", arr))
    unknown = [c for c in cats if c not in VALID_LOGBOOK_CATEGORIES]
    if unknown:
        return [{"check": "category_values", "page": page, "unknown": unknown,
                 "reason": f"Category values {unknown} not in VALID_LOGBOOK_CATEGORIES — update the constant in this validator"}]
    return []


def check_pm_category_alignment(pm_content):
    if not pm_content:
        return [{"check": "pm_category_alignment", "page": PM_PAGE,
                 "reason": f"{PM_PAGE} not found"}]
    m = re.search(r"PM_CAT_TO_LOG_CAT\s*=\s*\{([^}]+)\}", pm_content, re.DOTALL)
    if not m:
        return [{"check": "pm_category_alignment", "page": PM_PAGE,
                 "reason": "PM_CAT_TO_LOG_CAT not found in pm-scheduler.html"}]
    issues = []
    for pm_cat, log_cat in re.findall(r"['\"]([^'\"]+)['\"]\s*:\s*['\"]([^'\"]+)['\"]", m.group(1)):
        if log_cat not in VALID_LOGBOOK_CATEGORIES:
            issues.append({"check": "pm_category_alignment", "page": PM_PAGE,
                           "pm_category": pm_cat, "maps_to": log_cat,
                           "reason": f"PM category '{pm_cat}' maps to '{log_cat}' which is not in logbook's category dropdown — PM entries will have unrecognized category"})
    return issues


# ── Layer 2: Tenant isolation ─────────────────────────────────────────────────

def check_hive_id_in_txn_insert(content, page):
    """
    Both saveEntry and saveEdit insert to inventory_transactions when parts are used.
    Each insert must include hive_id: HIVE_ID so transactions are tenant-scoped.
    """
    issues = []
    for m in re.finditer(r"from\(['\"]inventory_transactions['\"]\)\.insert\((\{[^}]{0,600}\})", content, re.DOTALL):
        block = m.group(1)
        if "hive_id" not in block:
            line = content[:m.start()].count('\n') + 1
            issues.append({"check": "hive_id_in_txn_insert", "page": page, "line": line,
                           "reason": f"inventory_transactions.insert() at line {line} missing hive_id — transactions not tenant-scoped in hive mode"})
    return issues


def check_delete_scoped_by_worker(content, page):
    m = re.search(r"async function deleteEntry\s*\(", content)
    if not m:
        return [{"check": "delete_scoped_by_worker", "page": page,
                 "reason": "deleteEntry() function not found"}]
    body = content[m.start():m.start() + 400]
    if not re.search(r"\.eq\s*\(['\"]worker_name['\"],\s*WORKER_NAME\s*\)", body):
        return [{"check": "delete_scoped_by_worker", "page": page,
                 "reason": "deleteEntry() does not scope delete by worker_name — users could delete other workers' entries"}]
    return []


def check_update_scoped_by_worker(content, page):
    m = re.search(r"async function saveEdit\s*\(", content)
    if not m:
        return [{"check": "update_scoped_by_worker", "page": page,
                 "reason": "saveEdit() function not found"}]
    body = content[m.start():m.start() + 3000]
    update_m = re.search(r"from\(['\"]logbook['\"]\)\.update\(", body)
    if not update_m:
        return [{"check": "update_scoped_by_worker", "page": page,
                 "reason": "saveEdit() logbook.update() call not found"}]
    after = body[update_m.start():update_m.start() + 200]
    if not re.search(r"\.eq\s*\(['\"]worker_name['\"],\s*WORKER_NAME\s*\)", after):
        return [{"check": "update_scoped_by_worker", "page": page,
                 "reason": "saveEdit() logbook.update() not scoped by worker_name — users could overwrite other workers' entries"}]
    return []


# ── Layer 3: Logic correctness ────────────────────────────────────────────────

def check_auth_gate(content, page):
    if not re.search(r"if\s*\(\s*!\s*WORKER_NAME\s*\)", content):
        return [{"check": "auth_gate", "page": page,
                 "reason": "WORKER_NAME auth gate missing — unauthenticated users can access the logbook"}]
    return []


def check_maintenance_type_values(content, page):
    """
    Find maintenance_type values written to the DB in insert/update payloads.
    They should match VALID_MAINTENANCE_TYPES exactly.
    """
    found = set(re.findall(r"maintenance_type\s*:\s*['\"]([^'\"]+)['\"]", content))
    # Exclude field selector references (short strings or UI labels)
    bad = [v for v in found if len(v) > 3 and v not in VALID_MAINTENANCE_TYPES]
    if bad:
        return [{"check": "maintenance_type_values", "page": page, "bad_values": bad,
                 "reason": f"maintenance_type values {bad} not in VALID_MAINTENANCE_TYPES — entries may have unrecognized types"}]
    return []


def check_qty_after_floor(content, page):
    """
    Every inventory deduction in logbook must use Math.max(0, ...) to prevent
    qty_after going negative.
    """
    for m in re.finditer(r"from\(['\"]inventory_transactions['\"]\)\.insert\(", content):
        # Check within 500 chars before the insert for Math.max
        context = content[max(0, m.start() - 500):m.start()]
        if "Math.max(0," not in context and "Math.max( 0," not in context:
            line = content[:m.start()].count('\n') + 1
            return [{"check": "qty_after_floor", "page": page, "line": line,
                     "reason": f"inventory_transactions.insert() near line {line}: no Math.max(0,...) guard found — qty_after may go negative"}]
    return []


# ── Layer 3 (cont): New field sync ───────────────────────────────────────────

NEW_LOGBOOK_FIELDS = ["failure_consequence", "readings_json", "production_output"]

def check_new_fields_in_add_entry(content, page):
    """
    addEntry() must include all new fields in its Supabase insert.
    Missing = new entries saved without the data.
    """
    m = re.search(r"async function addEntry\s*\(", content)
    if not m:
        return [{"check": "new_fields_in_add_entry", "page": page,
                 "reason": "addEntry() not found"}]
    body = content[m.start():m.start() + 1500]
    issues = []
    for field in NEW_LOGBOOK_FIELDS:
        if field not in body:
            issues.append({"check": "new_fields_in_add_entry", "page": page, "field": field,
                           "reason": f"addEntry() missing '{field}' in Supabase insert — new entries lose this data"})
    return issues


def check_new_fields_in_save_edit(content, page):
    """
    saveEdit() updates object must include or preserve the new fields.
    Missing = editing an entry silently wipes failure_consequence, readings, production data.
    """
    m = re.search(r"async function saveEdit\s*\(", content)
    if not m:
        return [{"check": "new_fields_in_save_edit", "page": page,
                 "reason": "saveEdit() not found"}]
    body = content[m.start():m.start() + 3000]
    issues = []
    for field in NEW_LOGBOOK_FIELDS:
        if field not in body:
            issues.append({"check": "new_fields_in_save_edit", "page": page, "field": field,
                           "reason": f"saveEdit() updates object missing '{field}' — editing an entry wipes this field to null"})
    return issues


def check_new_fields_in_load_entries(content, page):
    """
    loadEntries() data.map() must include the new fields in the cached entry shape.
    Missing = fields are dropped from the local cache, openEditModal can't read them.
    """
    m = re.search(r"_allEntries\s*=\s*data\.map\s*\(", content)
    if not m:
        return [{"check": "new_fields_in_load_entries", "page": page,
                 "reason": "_allEntries = data.map() not found"}]
    body = content[m.start():m.start() + 800]
    issues = []
    for field in NEW_LOGBOOK_FIELDS:
        if field not in body:
            issues.append({"check": "new_fields_in_load_entries", "page": page, "field": field,
                           "reason": f"loadEntries() cache missing '{field}' — field dropped from local state, saveEdit reads null instead of DB value"})
    return issues


# ── Layer 4: XSS / security ───────────────────────────────────────────────────

def check_await_in_non_async(content, page):
    """
    An `await` inside a regular function() callback (not async function) is a
    SyntaxError that crashes the entire JS engine on page load — ALL entries
    disappear because no code after the crash runs. This happened on 2026-04-28
    when a category change listener used await without async.
    """
    issues = []
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if "await " not in line:
            continue
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue
        # Look back up to 5 lines for the enclosing function definition
        window_back = "\n".join(lines[max(0, i - 5):i])
        # If a non-async function() starts in the look-back window and no async function
        has_plain_fn  = bool(re.search(r"\bfunction\s*\(", window_back))
        has_async_fn  = bool(re.search(r"\basync\s+function\s*\(", window_back))
        # Also flag arrow functions like .then(e => { ... await ... })
        has_plain_arrow = bool(re.search(r"(?<!=>)\b\w+\s*=>\s*\{", window_back))
        has_async_arrow = bool(re.search(r"\basync\s*\w*\s*=>\s*\{|\basync\s*\([^)]*\)\s*=>\s*\{", window_back))
        if has_plain_fn and not has_async_fn:
            issues.append({"check": "await_in_non_async", "page": page, "line": i + 1,
                           "reason": (f"{page}:{i+1} — `await` inside a non-async function() callback. "
                                      f"This is a SyntaxError that crashes ALL JS on the page — "
                                      f"entries never load. Fix: add `async` to the function keyword.")})
    return issues


def check_highlight_escapes(content, page):
    m = re.search(r"function highlight\s*\(", content)
    if not m:
        return [{"check": "highlight_escapes", "page": page,
                 "reason": "highlight() function not found — logbook entries may render unsanitized HTML"}]
    body = content[m.start():m.start() + 300]
    if "escHtml" not in body:
        return [{"check": "highlight_escapes", "page": page,
                 "reason": "highlight() function does not call escHtml — search results render raw DB content as HTML"}]
    return []


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    # L1 — data integrity
    "closed_at_consistency", "parts_deduction_guard", "closed_at_preservation",
    "status_values", "category_values", "pm_category_alignment",
    # L2 — tenant isolation
    "hive_id_in_txn_insert", "delete_scoped_by_worker", "update_scoped_by_worker",
    # L3 — logic + new field sync
    "auth_gate", "maintenance_type_values", "qty_after_floor",
    "new_fields_in_add_entry", "new_fields_in_save_edit", "new_fields_in_load_entries",
    # L4 — XSS / JS correctness
    "highlight_escapes", "await_in_non_async",
]

CHECK_LABELS = {
    # L1
    "closed_at_consistency":        "L1  closed_at set when status='Closed'",
    "parts_deduction_guard":        "L1  saveEdit: _existing guard (no double-deduct)",
    "closed_at_preservation":       "L1  closed_at preserved on re-edit",
    "status_values":                "L1  Only Open/Closed used as status values",
    "category_values":              "L1  Category values match dropdown",
    "pm_category_alignment":        "L1  PM_CAT_TO_LOG_CAT maps to valid categories",
    # L2
    "hive_id_in_txn_insert":        "L2  hive_id in inventory_transactions insert",
    "delete_scoped_by_worker":      "L2  deleteEntry scoped by worker_name",
    "update_scoped_by_worker":      "L2  saveEdit update scoped by worker_name",
    # L3
    "auth_gate":                    "L3  WORKER_NAME auth gate present",
    "maintenance_type_values":      "L3  maintenance_type values match valid list",
    "qty_after_floor":         "L3  Math.max(0,...) guard on qty_after",
    # L3 (new field sync)
    "new_fields_in_add_entry":      "L3  New fields in addEntry insert (consequence/readings/production)",
    "new_fields_in_save_edit":      "L3  New fields preserved in saveEdit update",
    "new_fields_in_load_entries":   "L3  New fields included in loadEntries cache shape",
    # L4
    "highlight_escapes":            "L4  highlight() calls escHtml before rendering",
    "await_in_non_async":           "L4  No await inside non-async callback (JS crash guard)",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nLogbook Validator (4-layer)"))
    print("=" * 55)

    logbook = read_file(LOGBOOK_PAGE)
    pm      = read_file(PM_PAGE)

    if not logbook:
        print(f"  ERROR: {LOGBOOK_PAGE} not found")
        sys.exit(1)

    all_issues = []

    # L1
    all_issues += check_closed_at_consistency(logbook, LOGBOOK_PAGE)
    all_issues += check_parts_deduction_guard(logbook, LOGBOOK_PAGE)
    all_issues += check_closed_at_preservation(logbook, LOGBOOK_PAGE)
    all_issues += check_status_values(logbook, LOGBOOK_PAGE)
    all_issues += check_category_values(logbook, LOGBOOK_PAGE)
    all_issues += check_pm_category_alignment(pm)

    # L2
    all_issues += check_hive_id_in_txn_insert(logbook, LOGBOOK_PAGE)
    all_issues += check_delete_scoped_by_worker(logbook, LOGBOOK_PAGE)
    all_issues += check_update_scoped_by_worker(logbook, LOGBOOK_PAGE)

    # L3
    all_issues += check_auth_gate(logbook, LOGBOOK_PAGE)
    all_issues += check_maintenance_type_values(logbook, LOGBOOK_PAGE)
    all_issues += check_qty_after_floor(logbook, LOGBOOK_PAGE)
    all_issues += check_new_fields_in_add_entry(logbook, LOGBOOK_PAGE)
    all_issues += check_new_fields_in_save_edit(logbook, LOGBOOK_PAGE)
    all_issues += check_new_fields_in_load_entries(logbook, LOGBOOK_PAGE)

    # L4
    all_issues += check_highlight_escapes(logbook, LOGBOOK_PAGE)
    all_issues += check_await_in_non_async(logbook, LOGBOOK_PAGE)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "logbook",
        "total_checks": total,
        "passed":       n_pass,
        "skipped":      n_skip,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
    }
    with open("logbook_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
