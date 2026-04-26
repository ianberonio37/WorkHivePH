"""
Inventory Validator — WorkHive Platform

Static analysis of inventory.html (and hive.html for supervisor approval) covering:

  1. Status transition logic  — new/edit correctly sets pending vs approved
  2. Use/Restock guards        — both pending AND rejected block stock operations
  3. Transaction logging       — every qty_on_hand change logs a transaction
  4. qty_after in transactions — balance tracking requires qty_after
  5. hive_id on inserts        — new parts always carry hive_id
  6. Use insufficient stock    — use blocked when qty requested > qty_on_hand
  7. Approval/rejection writes — supervisor writes correct status to DB

Usage:  python validate_inventory.py
Output: inventory_report.json
"""
import re, json, sys

INVENTORY_PAGE = "inventory.html"
HIVE_PAGE      = "hive.html"


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


# ── Check 1: Status transition logic ─────────────────────────────────────────
def check_status_transitions(content, page):
    """
    editStatus must follow:
      - Worker editing pending/rejected item in hive → 'pending' (resubmit)
      - New item by non-supervisor in hive → 'pending'
      - New item by supervisor or solo → 'approved'
    Verify the editStatus variable uses 'pending' for non-supervisor edits
    and new item status line covers both cases.
    """
    issues = []

    # Check editStatus assigned to 'pending' for non-supervisor edits
    edit_status_pat = re.search(
        r"editStatus\s*=\s*existingItem\s*&&\s*HIVE_ID\s*&&\s*HIVE_ROLE\s*!==\s*['\"]supervisor['\"]\s*\?\s*['\"]pending['\"]",
        content
    )
    if not edit_status_pat:
        issues.append({
            "page": page,
            "reason": "editStatus logic not found or changed — may not correctly resubmit edits for approval",
        })

    # Check new item status: pending for non-supervisor, approved otherwise
    new_status_pat = re.search(
        r"HIVE_ID\s*&&\s*HIVE_ROLE\s*!==\s*['\"]supervisor['\"]\s*\?\s*['\"]pending['\"]\s*:\s*['\"]approved['\"]",
        content
    )
    if not new_status_pat:
        issues.append({
            "page": page,
            "reason": "New item status logic not found — may not route new items through approval in hive mode",
        })

    return issues


# ── Check 2: Use/Restock guarded against pending AND rejected ─────────────────
def check_use_restock_guards(content, page):
    """
    Both the Use Stock and Restock functions must guard against:
      - status === 'pending'  (locked until approved)
      - status === 'rejected' (locked until resubmitted and approved)
    Missing either guard means workers can consume unapproved/rejected parts.
    """
    issues = []
    status_values = ["pending", "rejected"]

    # Find useStock and restockItem function bodies
    for fn_name in ["useStock", "restockItem", "saveUse", "saveRestock"]:
        m = re.search(rf"(?:async\s+)?function\s+{fn_name}\s*\(", content)
        if not m:
            continue
        # Get ~500 chars of function body
        block = content[m.start():m.start() + 600]
        for status in status_values:
            if f"status === '{status}'" not in block and f'status === "{status}"' not in block:
                issues.append({
                    "page": page,
                    "function": fn_name,
                    "missing_guard": status,
                    "reason": f"{fn_name}() does not guard against status='{status}' — workers can operate on {status} parts",
                })
    return issues


# ── Check 3: Transaction logged on every qty_on_hand change ──────────────────
def check_transaction_logging(content, page):
    """
    Every code path that changes qty_on_hand must call addTransaction().
    Heuristic: find += and -= on qty_on_hand; verify addTransaction appears nearby.
    """
    issues = []
    qty_changes = [
        (r"qty_on_hand\s*-=\s*\w+", "use/deduction"),
        (r"qty_on_hand\s*\+=\s*\w+", "add/restock"),
    ]
    for pat, label in qty_changes:
        for m in re.finditer(pat, content):
            snippet = content[m.start():m.start() + 300]
            if "addTransaction" not in snippet:
                line_no = content[:m.start()].count('\n') + 1
                issues.append({
                    "page": page,
                    "line": line_no,
                    "operation": label,
                    "reason": f"qty_on_hand change ({label}) at line {line_no} has no addTransaction() call nearby — stock change unlogged",
                })
    return issues


# ── Check 4: qty_after in addTransaction calls ────────────────────────────────
def check_qty_after_in_transactions(content, page):
    """
    addTransaction() must always be called with 4 args, the 4th being the new qty_after.
    Pattern: addTransaction(itemId, type, qtyChange, qtyAfter, ...)
    Verify the function definition stores qty_after in the transaction object.
    """
    issues = []
    # Find addTransaction definition
    m = re.search(r"function addTransaction\s*\(([^)]+)\)", content)
    if not m:
        return [{"page": page, "reason": "addTransaction function not found"}]

    params = [p.strip() for p in m.group(1).split(',')]
    if len(params) < 4:
        issues.append({
            "page": page,
            "reason": f"addTransaction has only {len(params)} params — qty_after (4th param) missing from signature",
        })
        return issues

    # Check function body stores qty_after
    fn_start = m.start()
    fn_body  = content[fn_start:fn_start + 400]
    if "qty_after" not in fn_body:
        issues.append({
            "page": page,
            "reason": "addTransaction() body does not set qty_after on the transaction object — balance tracking broken",
        })
    return issues


# ── Check 5: hive_id on inventory_items inserts ───────────────────────────────
def check_hive_id_on_inserts(content, page):
    """
    The inventory item save payload must include hive_id so the supervisor
    can see it in the approval queue.
    """
    issues = []
    # Find the main save payload (const payload = {...})
    m = re.search(r"const payload\s*=\s*\{([^}]+)\}", content, re.DOTALL)
    if not m:
        return [{"page": page, "reason": "Inventory save payload not found"}]

    block = m.group(1)
    if "hive_id" not in block:
        issues.append({
            "page": page,
            "reason": "hive_id not in inventory save payload — supervisor cannot see new items in approval queue",
        })
    return issues


# ── Check 6: Use blocked when qty > qty_on_hand ───────────────────────────────
def check_use_stock_guard(content, page):
    """
    useStock() must block the operation when requested qty exceeds qty_on_hand.
    Pattern: if (qty > items[idx].qty_on_hand) { ... return; }
    """
    issues = []
    guard = re.search(
        r"if\s*\(\s*qty\s*>\s*\w+\[?\w*\]?\.qty_on_hand\s*\)",
        content
    )
    if not guard:
        issues.append({
            "page": page,
            "reason": "useStock() does not guard against qty > qty_on_hand — may allow negative inventory",
        })
    return issues


# ── Check 7: Supervisor writes correct status ─────────────────────────────────
def check_supervisor_approval_writes(hive_content, page):
    """
    hive.html approveItem() must write status='approved'.
    hive.html rejectItem()  must write status='rejected'.
    """
    issues = []
    if not hive_content:
        return [{"page": page, "reason": f"{HIVE_PAGE} not found"}]

    # approveItem writes 'approved'
    approve_pat = re.search(
        r"async function approveItem\b[\s\S]{0,500}?status\s*:\s*['\"]approved['\"]",
        hive_content, re.DOTALL
    )
    if not approve_pat:
        issues.append({
            "page": HIVE_PAGE,
            "reason": "approveItem() in hive.html does not write status='approved'",
        })

    # rejectItem writes 'rejected'
    reject_pat = re.search(
        r"async function rejectItem\b[\s\S]{0,500}?status\s*:\s*['\"]rejected['\"]",
        hive_content, re.DOTALL
    )
    if not reject_pat:
        issues.append({
            "page": HIVE_PAGE,
            "reason": "rejectItem() in hive.html does not write status='rejected'",
        })

    return issues


# ── Main ──────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("Inventory Validator")
print("=" * 70)

inventory = read_file(INVENTORY_PAGE)
hive      = read_file(HIVE_PAGE)

if not inventory:
    print(f"ERROR: {INVENTORY_PAGE} not found")
    sys.exit(1)

fail_count = 0
warn_count = 0
report     = {}

checks = [
    ("[1] Status transition logic",          check_status_transitions(inventory, INVENTORY_PAGE)),
    ("[2] Use/Restock guards (pending+rejected)", check_use_restock_guards(inventory, INVENTORY_PAGE)),
    ("[3] Transaction on every qty change",   check_transaction_logging(inventory, INVENTORY_PAGE)),
    ("[4] qty_after in addTransaction",       check_qty_after_in_transactions(inventory, INVENTORY_PAGE)),
    ("[5] hive_id on save payload",           check_hive_id_on_inserts(inventory, INVENTORY_PAGE)),
    ("[6] Use blocked when qty exceeds stock",check_use_stock_guard(inventory, INVENTORY_PAGE)),
    ("[7] Supervisor approval/rejection writes", check_supervisor_approval_writes(hive, HIVE_PAGE)),
]

for label, issues in checks:
    print(f"\n{label}\n")
    if not issues:
        print(f"  PASS")
    else:
        for iss in issues:
            severity = "WARN" if iss.get("warn") else "FAIL"
            print(f"  {severity}  {iss.get('page','?')} {('line ' + str(iss['line'])) if 'line' in iss else ''}")
            print(f"        {iss['reason']}")
            if severity == "FAIL":
                fail_count += 1
            else:
                warn_count += 1
    report[label] = issues

print(f"\n{'=' * 70}")
print(f"Result: {fail_count} FAIL  {warn_count} WARN")

with open("inventory_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved inventory_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll inventory checks PASS.")
