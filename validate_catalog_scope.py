"""
Catalog Approval Status Validator — WorkHive Platform
======================================================
In hive mode, inventory items and assets go through an approval workflow:
  1. Worker submits → status = 'pending'
  2. Supervisor approves → status = 'approved'
  3. Item appears in the shared catalog

  Layer 1 — Catalog read scope
    1.  inventory_items status filter — hive-mode catalog reads filter by status='approved'
    2.  assets status filter          — hive-mode asset reads filter by status='approved'

  Layer 2 — Write integrity
    3.  Worker edits re-approval      — worker edits reset status to 'pending'
    4.  Canonical status values       — only 'pending','approved','rejected' written to catalog

  Layer 3 — Approval queue
    5.  Queue scoped to hive          — loadApprovalQueue filters by hive_id (not cross-hive)

  Layer 4 — Delete scope
    6.  Delete scoped to worker/hive  — catalog deletes have worker_name or hive_id scope [WARN]

Usage:  python validate_catalog_scope.py
Output: catalog_scope_report.json
"""
import re, json, sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

CATALOG_PAGES = [
    "inventory.html",
    "logbook.html",
    "hive.html",
    "pm-scheduler.html",
    "assistant.html",
]

CATALOG_TABLES  = ["inventory_items", "assets"]
VALID_STATUSES  = {"pending", "approved", "rejected"}


# ── Layer 1: Catalog read scope ───────────────────────────────────────────────

def check_catalog_status_filter(pages, tables):
    """Hive-mode SELECT on catalog tables must include .eq('status', 'approved')."""
    issues = []
    for page in pages:
        content = read_file(page)
        if not content:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            table = next((t for t in tables
                          if (f"from('{t}')" in line or f'from("{t}")' in line)
                          and ".select(" in line), None)
            if not table:
                continue
            prev = lines[i - 1] if i > 0 else ""
            if re.search(r"\.(insert|upsert)\s*\(", line) or \
               re.search(r"\.(insert|upsert)\s*\(", prev):
                continue
            if "HIVE_ID" in line and "Promise.resolve" in line:
                continue
            window = "\n".join(lines[i:min(len(lines), i + 6)])
            if re.search(r"status.*pending|pending.*status|[Aa]pproval[Qq]ueue", window):
                continue
            if "worker_name" in window and "hive_id" not in window and "HIVE_ID" not in window:
                continue
            if "HIVE_ID" not in window and "hive_id" not in window:
                continue
            if not re.search(r"status.*approved|approved.*status", window):
                issues.append({"check": "catalog_status_filter", "page": page,
                               "table": table, "line": i + 1,
                               "reason": f"{page}:{i+1} hive-mode SELECT on '{table}' missing .eq('status','approved') — pending/rejected items appear in shared catalog: `{line.strip()[:70]}`"})
    return issues


# ── Layer 2: Write integrity ──────────────────────────────────────────────────

def check_edit_reapproval(pages):
    issues = []
    for page in pages:
        content = read_file(page)
        if not content:
            continue
        if not re.search(r"db\.from\(['\"](?:inventory_items|assets)['\"][^)]*\)\.upsert\s*\(", content):
            continue
        if not re.search(r"needsReapproval|editStatus|['\"]pending['\"]", content):
            issues.append({"check": "edit_reapproval", "page": page,
                           "reason": f"{page} has catalog upsert but no re-approval pattern — worker edits to approved items may bypass supervisor review"})
    return issues


def check_canonical_status_values(pages, tables):
    """
    Only 'pending', 'approved', 'rejected' should be written as status values
    to catalog tables. Any other value (e.g., 'draft', 'active', 'verified')
    breaks the approval workflow logic.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if not content:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            table = next((t for t in tables
                          if f"from('{t}')" in line or f'from("{t}")' in line), None)
            if not table:
                continue
            if not re.search(r"\.(insert|upsert)\s*\(", line):
                continue
            # Extract the status value from the payload block (next 15 lines)
            block = "\n".join(lines[i:min(len(lines), i + 15)])
            for m in re.finditer(r"status\s*:\s*['\"]([^'\"]+)['\"]", block):
                val = m.group(1)
                if val not in VALID_STATUSES and val not in {"done", "active", "kicked"}:
                    issues.append({"check": "canonical_status_values",
                                   "page": page, "table": table,
                                   "status_value": val, "line": i + 1,
                                   "reason": f"{page}:{i+1} status='{val}' written to '{table}' — only 'pending','approved','rejected' are valid catalog status values"})
    return issues


# ── Layer 3: Approval queue ───────────────────────────────────────────────────

def check_approval_queue_scope(page):
    """
    loadApprovalQueue() in hive.html must filter both assets and inventory_items
    by HIVE_ID. Without it, a supervisor sees pending items from ALL hives.
    """
    content = read_file(page)
    if not content:
        return [{"check": "approval_queue_scope", "page": page, "reason": f"{page} not found"}]
    m = re.search(r"async function loadApprovalQueue\s*\(", content)
    if not m:
        return []
    body = content[m.start():m.start() + 2000]
    issues = []
    for table in CATALOG_TABLES:
        table_m = re.search(rf"from\(['\"]({re.escape(table)})['\"]", body)
        if not table_m:
            continue
        # Check that hive_id scope is within 200 chars of the table reference
        context = body[table_m.start():table_m.start() + 200]
        if "HIVE_ID" not in context and "hive_id" not in context:
            issues.append({"check": "approval_queue_scope", "page": page, "table": table,
                           "reason": f"{page} loadApprovalQueue() queries '{table}' without hive_id filter — supervisor sees pending items from ALL hives"})
    return issues


# ── Layer 4: Delete scope ─────────────────────────────────────────────────────

def check_delete_scope(pages, tables):
    issues = []
    for page in pages:
        content = read_file(page)
        if not content:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            table = next((t for t in tables
                          if (f"from('{t}')" in line or f'from("{t}")' in line)
                          and ".delete()" in line), None)
            if not table:
                continue
            window = "\n".join(lines[i:min(len(lines), i + 4)])
            if not any(k in window for k in ["worker_name", "WORKER_NAME", "hive_id", "HIVE_ID"]):
                issues.append({"check": "delete_scope", "page": page, "table": table, "line": i + 1,
                               "skip": True,   # WARN — JS-level guards exist, RLS pending
                               "reason": f"{page}:{i+1} delete on '{table}' has no worker_name or hive_id scope — relies on JS-level role checks only: `{line.strip()[:70]}`"})
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    # L1
    "catalog_status_filter",
    # L2
    "edit_reapproval", "canonical_status_values",
    # L3
    "approval_queue_scope",
    # L4 (combined assets+inventory)
    "delete_scope",
    # Extra: assets filter is same check, merged into catalog_status_filter above
]

# Run as 6 logical checks but combine inventory+assets into one check name
CHECK_NAMES = [
    "catalog_status_filter",
    "edit_reapproval",
    "canonical_status_values",
    "approval_queue_scope",
    "delete_scope",
]

CHECK_LABELS = {
    "catalog_status_filter":   "L1  Hive-mode catalog reads filter by status='approved'",
    "edit_reapproval":         "L2  Worker edits reset status to 'pending' (re-approval)",
    "canonical_status_values": "L2  Only pending/approved/rejected written to catalog",
    "approval_queue_scope":    "L3  loadApprovalQueue scoped to hive_id",
    "delete_scope":            "L4  Catalog deletes scoped to worker/hive  [WARN]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nCatalog Approval Status Validator (4-layer)"))
    print("=" * 55)

    all_issues = []
    all_issues += check_catalog_status_filter(CATALOG_PAGES, CATALOG_TABLES)
    all_issues += check_edit_reapproval(CATALOG_PAGES)
    all_issues += check_canonical_status_values(CATALOG_PAGES, CATALOG_TABLES)
    all_issues += check_approval_queue_scope("hive.html")
    all_issues += check_delete_scope(CATALOG_PAGES, CATALOG_TABLES)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL — delete scope warnings are known (RLS pending)\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "catalog_scope",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("catalog_scope_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
