"""
Inventory Validator — WorkHive Platform
========================================
Four-layer validation of inventory.html + hive.html:

  Layer 1 — Workflow integrity
    1.  Status transition logic       — new/edit sets pending vs approved correctly
    2.  Use/Restock guards            — pending AND rejected block stock operations
    3.  Transaction on qty change     — every qty_on_hand change calls addTransaction
    4.  qty_after in addTransaction   — balance tracking has the 4th param

  Layer 2 — Tenant isolation
    5.  hive_id on save payload       — inventory_items insert includes hive_id
    6.  hive_id in addTransaction     — transaction object includes hive_id before Supabase sync
    7.  saveTransactions Supabase sync — transactions write to DB, not just localStorage
    8.  deleteItem scoped             — delete uses hive_id or worker_name guard

  Layer 3 — Logic / access control
    9.  Use blocked when qty exceeded — qty > qty_on_hand returns before deducting
    10. Supervisor approval writes    — approveItem writes 'approved', rejectItem writes 'rejected'
    11. Supervisor gate on delete     — workers can only delete their own rejected items
    12. Auth gate present             — WORKER_NAME redirect before any DB access

  Layer 4 — XSS / security
    13. escHtml in highlight          — highlight() calls escHtml before inserting into DOM

Usage:  python validate_inventory.py
Output: inventory_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

INVENTORY_PAGE = "inventory.html"
HIVE_PAGE      = "hive.html"


# ── Layer 1: Workflow integrity ───────────────────────────────────────────────

def check_status_transitions(content, page):
    issues = []
    if not re.search(
        r"editStatus\s*=\s*existingItem\s*&&\s*HIVE_ID\s*&&\s*HIVE_ROLE\s*!==\s*['\"]supervisor['\"]\s*\?\s*['\"]pending['\"]",
        content
    ):
        issues.append({"check": "status_transitions", "page": page,
                       "reason": "editStatus logic not found — edits may not route back through approval correctly"})
    if not re.search(
        r"HIVE_ID\s*&&\s*HIVE_ROLE\s*!==\s*['\"]supervisor['\"]\s*\?\s*['\"]pending['\"]\s*:\s*['\"]approved['\"]",
        content
    ):
        issues.append({"check": "status_transitions", "page": page,
                       "reason": "New item status logic not found — new items may bypass approval in hive mode"})
    return issues


def check_use_restock_guards(content, page):
    issues = []
    for fn_name in ["useStock", "restockItem", "saveUse", "saveRestock"]:
        m = re.search(rf"(?:async\s+)?function\s+{fn_name}\s*\(", content)
        if not m:
            continue
        block = content[m.start():m.start() + 600]
        for status in ("pending", "rejected"):
            if f"status === '{status}'" not in block and f'status === "{status}"' not in block:
                issues.append({"check": "use_restock_guards", "page": page,
                               "function": fn_name, "missing_guard": status,
                               "reason": f"{fn_name}() missing guard for status='{status}' — workers can operate on {status} parts"})
    return issues


def check_transaction_logging(content, page):
    issues = []
    for pat, label in [(r"qty_on_hand\s*-=\s*\w+", "deduction"), (r"qty_on_hand\s*\+=\s*\w+", "restock")]:
        for m in re.finditer(pat, content):
            snippet = content[m.start():m.start() + 300]
            if "addTransaction" not in snippet:
                line = content[:m.start()].count('\n') + 1
                issues.append({"check": "transaction_logging", "page": page, "line": line,
                               "reason": f"qty_on_hand {label} at line {line} has no addTransaction() call — stock change unlogged"})
    return issues


def check_qty_after_in_transactions(content, page):
    m = re.search(r"function addTransaction\s*\(([^)]+)\)", content)
    if not m:
        return [{"check": "qty_after_in_transactions", "page": page,
                 "reason": "addTransaction function not found"}]
    params = [p.strip() for p in m.group(1).split(',')]
    if len(params) < 4:
        return [{"check": "qty_after_in_transactions", "page": page,
                 "reason": f"addTransaction has {len(params)} params — qty_after (4th) missing from signature"}]
    fn_body = content[m.start():m.start() + 400]
    if "qty_after" not in fn_body:
        return [{"check": "qty_after_in_transactions", "page": page,
                 "reason": "addTransaction() body does not set qty_after — running balance tracking broken"}]
    return []


# ── Layer 2: Tenant isolation ─────────────────────────────────────────────────

def check_hive_id_on_save_payload(content, page):
    m = re.search(r"const payload\s*=\s*\{([^}]+)\}", content, re.DOTALL)
    if not m:
        return [{"check": "hive_id_on_save_payload", "page": page,
                 "reason": "Inventory save payload not found"}]
    if "hive_id" not in m.group(1):
        return [{"check": "hive_id_on_save_payload", "page": page,
                 "reason": "hive_id not in inventory save payload — supervisor cannot see new items in approval queue"}]
    return []


def check_hive_id_in_add_transaction(content, page):
    """
    addTransaction() builds the transaction object and passes it to saveTransactions,
    which inserts it to inventory_transactions. The object must include hive_id so
    transactions are queryable by hive.
    """
    m = re.search(r"function addTransaction\s*\(", content)
    if not m:
        return []
    # Extract the object literal pushed to txns
    fn_body = content[m.start():m.start() + 600]
    push_m = re.search(r"txns\.push\s*\(\{([^}]+)\}\)", fn_body, re.DOTALL)
    if not push_m:
        return [{"check": "hive_id_in_add_transaction", "page": page,
                 "reason": "txns.push({}) not found inside addTransaction — cannot verify hive_id"}]
    obj_body = push_m.group(1)
    if "hive_id" not in obj_body:
        return [{"check": "hive_id_in_add_transaction", "page": page,
                 "reason": "addTransaction() push object missing hive_id — inventory_transactions rows have null hive_id in hive mode"}]
    return []


def check_txn_syncs_to_supabase(content, page):
    m = re.search(r"function saveTransactions\s*\(", content)
    if not m:
        return [{"check": "txn_syncs_to_supabase", "page": page,
                 "reason": "saveTransactions() not found — cannot verify Supabase sync"}]
    body = content[m.start():m.start() + 400]
    if "inventory_transactions" not in body or ".insert(" not in body:
        return [{"check": "txn_syncs_to_supabase", "page": page,
                 "reason": "saveTransactions() does not call db.from('inventory_transactions').insert — transactions stay in localStorage only"}]
    return []


def check_delete_scoped(content, page):
    m = re.search(r"async function confirmDeleteItem\s*\(|async function deleteItem\s*\(", content)
    if not m:
        if not re.search(r"\.delete\(\)\.eq\(['\"]id['\"]", content):
            return [{"check": "delete_scoped", "page": page,
                     "reason": "confirmDeleteItem / deleteItem not found — cannot verify delete scope"}]
        return []
    # Use up to 2000 chars — function body with confirm dialog can be long
    body = content[m.start():m.start() + 2000]
    has_hive   = bool(re.search(r"\.eq\s*\(['\"]hive_id['\"]", body))
    has_worker = bool(re.search(r"\.eq\s*\(['\"]worker_name['\"]", body))
    if not has_hive and not has_worker:
        return [{"check": "delete_scoped", "page": page,
                 "reason": "confirmDeleteItem scopes by id only — any UUID can delete any item without hive/worker scope"}]
    return []


# ── Layer 3: Logic / access control ──────────────────────────────────────────

def check_use_stock_qty_guard(content, page):
    if not re.search(r"if\s*\(\s*qty\s*>\s*\w+\[?\w*\]?\.qty_on_hand\s*\)", content):
        return [{"check": "use_stock_qty_guard", "page": page,
                 "reason": "useStock() does not guard against qty > qty_on_hand — negative inventory possible"}]
    return []


def check_supervisor_approval_writes(hive_content, page):
    if not hive_content:
        return [{"check": "supervisor_approval_writes", "page": page,
                 "reason": f"{HIVE_PAGE} not found"}]
    issues = []
    if not re.search(r"async function approveItem\b[\s\S]{0,500}?status\s*:\s*['\"]approved['\"]", hive_content, re.DOTALL):
        issues.append({"check": "supervisor_approval_writes", "page": page,
                       "reason": "approveItem() in hive.html does not write status='approved'"})
    if not re.search(r"async function rejectItem\b[\s\S]{0,500}?status\s*:\s*['\"]rejected['\"]", hive_content, re.DOTALL):
        issues.append({"check": "supervisor_approval_writes", "page": page,
                       "reason": "rejectItem() in hive.html does not write status='rejected'"})
    return issues


def check_supervisor_gate_delete(content, page):
    """
    Workers in hive mode can only delete their own REJECTED items.
    Approved and pending items require supervisor role.
    """
    # Look for: HIVE_ROLE !== 'supervisor' + status !== 'rejected' combination near delete
    if not re.search(r"HIVE_ROLE\s*!==?\s*['\"]supervisor['\"][\s\S]{0,200}?status\s*!==?\s*['\"]rejected['\"]|Supervisors only", content):
        return [{"check": "supervisor_gate_delete", "page": page,
                 "reason": "No supervisor gate found on delete — workers may be able to delete approved or pending items"}]
    return []


def check_auth_gate(content, page):
    if not re.search(r"if\s*\(\s*!\s*WORKER_NAME\s*\)|!WORKER_NAME\s*\)", content):
        return [{"check": "auth_gate", "page": page,
                 "reason": "WORKER_NAME auth gate missing — unauthenticated users can access inventory"}]
    return []


# ── Layer 4: XSS / security ───────────────────────────────────────────────────

def check_highlight_escapes(content, page):
    m = re.search(r"function highlight\s*\(", content)
    if not m:
        return [{"check": "highlight_escapes", "page": page,
                 "reason": "highlight() not found — inventory render may insert raw DB strings as HTML"}]
    body = content[m.start():m.start() + 300]
    if "escHtml" not in body:
        return [{"check": "highlight_escapes", "page": page,
                 "reason": "highlight() does not call escHtml — search highlights render raw part names as HTML"}]
    return []


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    # L1
    "status_transitions", "use_restock_guards",
    "transaction_logging", "qty_after_in_transactions",
    # L2
    "hive_id_on_save_payload", "hive_id_in_add_transaction",
    "txn_syncs_to_supabase", "delete_scoped",
    # L3
    "use_stock_qty_guard", "supervisor_approval_writes",
    "supervisor_gate_delete", "auth_gate",
    # L4
    "highlight_escapes",
]

CHECK_LABELS = {
    # L1
    "status_transitions":        "L1  Status transitions (pending vs approved logic)",
    "use_restock_guards":        "L1  Use/Restock blocked for pending + rejected",
    "transaction_logging":       "L1  addTransaction called on every qty change",
    "qty_after_in_transactions": "L1  qty_after present in addTransaction",
    # L2
    "hive_id_on_save_payload":   "L2  hive_id in inventory_items save payload",
    "hive_id_in_add_transaction":"L2  hive_id in addTransaction push object",
    "txn_syncs_to_supabase":     "L2  saveTransactions syncs to Supabase",
    "delete_scoped":             "L2  deleteItem scoped by hive_id or worker_name",
    # L3
    "use_stock_qty_guard":       "L3  Use blocked when qty > qty_on_hand",
    "supervisor_approval_writes":"L3  approveItem='approved', rejectItem='rejected'",
    "supervisor_gate_delete":    "L3  Workers can only delete their own rejected items",
    "auth_gate":                 "L3  WORKER_NAME auth gate present",
    # L4
    "highlight_escapes":         "L4  highlight() calls escHtml before rendering",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nInventory Validator (4-layer)"))
    print("=" * 55)

    inventory = read_file(INVENTORY_PAGE)
    hive      = read_file(HIVE_PAGE)

    if not inventory:
        print(f"  ERROR: {INVENTORY_PAGE} not found")
        sys.exit(1)

    all_issues = []

    # L1
    all_issues += check_status_transitions(inventory, INVENTORY_PAGE)
    all_issues += check_use_restock_guards(inventory, INVENTORY_PAGE)
    all_issues += check_transaction_logging(inventory, INVENTORY_PAGE)
    all_issues += check_qty_after_in_transactions(inventory, INVENTORY_PAGE)

    # L2
    all_issues += check_hive_id_on_save_payload(inventory, INVENTORY_PAGE)
    all_issues += check_hive_id_in_add_transaction(inventory, INVENTORY_PAGE)
    all_issues += check_txn_syncs_to_supabase(inventory, INVENTORY_PAGE)
    all_issues += check_delete_scoped(inventory, INVENTORY_PAGE)

    # L3
    all_issues += check_use_stock_qty_guard(inventory, INVENTORY_PAGE)
    all_issues += check_supervisor_approval_writes(hive, HIVE_PAGE)
    all_issues += check_supervisor_gate_delete(inventory, INVENTORY_PAGE)
    all_issues += check_auth_gate(inventory, INVENTORY_PAGE)

    # L4
    all_issues += check_highlight_escapes(inventory, INVENTORY_PAGE)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "inventory",
        "total_checks": total,
        "passed":       n_pass,
        "skipped":      n_skip,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
    }
    with open("inventory_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
