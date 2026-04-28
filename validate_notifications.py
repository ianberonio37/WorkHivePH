"""
Notification and Alert Health Validator — WorkHive Platform
============================================================
WorkHive uses two notification layers:
  1. In-app toasts — immediate feedback on actions (showToast)
  2. Notification bell + pushNotif — persistent alert center on hive board

  Layer 1 — Realtime channel events
    1.  Approval channel: INSERT + UPDATE   — both event types required
    2.  Channel vars at module level        — not inside functions (can't clean up)

  Layer 2 — Worker feedback
    3.  Worker approval toasts: approved + rejected — both statuses notified

  Layer 3 — Alert completeness
    4.  Notification bell visible when active — bell shown when hive initialised
    5.  Stock alerts: out + low              — both thresholds pushed in checkStockAlert
    6.  PM alerts: overdue + due-soon        — both pushed in PM health function

  Layer 4 — Init integration
    7.  buildNotifications called on init    — notifications loaded at board startup

Usage:  python validate_notifications.py
Output: notifications_report.json
"""
import re, json, sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

HIVE_PAGE = "hive.html"

REQUIRED_INSERT_UPDATE_CHANNELS = ["hive-approval"]

REQUIRED_MODULE_LEVEL = [
    "presenceChannel",
    "feedChannel",
    "approvalChannel",
    "workerApprovalCh",
    "inventoryChannel",
]


# ── Layer 1: Realtime channel events ──────────────────────────────────────────

def check_approval_channel_events(page, channel_names):
    content = read_file(page)
    if not content:
        return [{"check": "approval_channel_events", "page": page, "reason": f"{page} not found"}]
    issues = []
    for channel_name in channel_names:
        m = re.search(rf"db\.channel\s*\(['\"]({re.escape(channel_name)}[^'\"]*)['\"]", content)
        if not m:
            issues.append({"check": "approval_channel_events", "page": page,
                           "reason": f"{page} channel '{channel_name}' not found — approval queue Realtime missing entirely"})
            continue
        block = "\n".join(content[m.start():m.start() + 8000].splitlines()[:100])
        if not re.search(r"event:\s*['\"]INSERT['\"]", block):
            issues.append({"check": "approval_channel_events", "page": page, "channel": channel_name,
                           "reason": f"{page} channel '{channel_name}' has no INSERT subscription — new submissions won't appear live"})
        if not re.search(r"event:\s*['\"]UPDATE['\"]", block):
            issues.append({"check": "approval_channel_events", "page": page, "channel": channel_name,
                           "reason": f"{page} channel '{channel_name}' has no UPDATE subscription — status changes won't reflect live"})
    return issues


def check_module_level_channels(page, channel_vars):
    content = read_file(page)
    if not content:
        return [{"check": "module_level_channels", "page": page, "reason": f"{page} not found"}]
    issues = []
    for var in channel_vars:
        declarations = list(re.finditer(rf"(?:let|const|var)\s+{re.escape(var)}\b", content))
        if not declarations:
            issues.append({"check": "module_level_channels", "page": page, "var": var,
                           "reason": f"{page} channel variable '{var}' never declared — cannot be managed or cleaned up"})
            continue
        has_module_level = any(
            len(content[content.rfind("\n", 0, d.start()) + 1:d.start()])
            - len(content[content.rfind("\n", 0, d.start()) + 1:d.start()].lstrip()) <= 2
            for d in declarations
        )
        if not has_module_level:
            issues.append({"check": "module_level_channels", "page": page, "var": var,
                           "reason": f"{page} channel variable '{var}' only declared inside a function — cannot be cleaned up in beforeunload"})
    return issues


# ── Layer 2: Worker feedback ──────────────────────────────────────────────────

def check_worker_approval_toasts(page):
    content = read_file(page)
    if not content:
        return [{"check": "worker_approval_toasts", "page": page, "reason": f"{page} not found"}]
    m = re.search(r"channel\s*\(['\"]worker-appr['\"\:]", content)
    if not m:
        return [{"check": "worker_approval_toasts", "page": page,
                 "reason": f"{page} worker approval channel ('worker-appr') not found — workers never receive approved/rejected notifications"}]
    block = "\n".join(content[m.start():m.start() + 5000].splitlines()[:100])
    issues = []
    if not re.search(r"approved.*showToast|showToast.*approved", block, re.DOTALL):
        issues.append({"check": "worker_approval_toasts", "page": page,
                       "reason": f"{page} worker-appr channel has no showToast for 'approved' — workers won't know when their submission is approved"})
    if not re.search(r"rejected.*showToast|showToast.*rejected", block, re.DOTALL):
        issues.append({"check": "worker_approval_toasts", "page": page,
                       "reason": f"{page} worker-appr channel has no showToast for 'rejected' — workers won't know when their submission is rejected"})
    return issues


# ── Layer 3: Alert completeness ───────────────────────────────────────────────

def check_notification_bell(page):
    content = read_file(page)
    if not content:
        return []
    if not re.search(r'id=["\']notif-wrapper["\'][^>]*display\s*:\s*none', content, re.IGNORECASE):
        return []
    if not re.search(r"notif-wrapper.*style\.display|getElementById\(['\"]notif-wrapper", content, re.IGNORECASE):
        return [{"check": "notification_bell", "page": page,
                 "reason": f"{page} #notif-wrapper starts hidden but is never made visible — bell permanently hidden"}]
    return []


def check_stock_alert_completeness(page):
    """
    checkStockAlert() must push BOTH stock-out AND stock-low notifications.
    If only one threshold is pushed, supervisors only see partial inventory health.
    """
    content = read_file(page)
    if not content:
        return []
    m = re.search(r"(?:async\s+)?function\s+checkStockAlert\s*\(", content)
    if not m:
        return [{"check": "stock_alert_completeness", "page": page,
                 "reason": f"{page} checkStockAlert() function not found — no stock notifications"}]
    body = content[m.start():m.start() + 2000]
    issues = []
    if "stock-out" not in body:
        issues.append({"check": "stock_alert_completeness", "page": page,
                       "reason": f"{page} checkStockAlert() does not push 'stock-out' notification — out-of-stock items go unnoticed"})
    if "stock-low" not in body:
        issues.append({"check": "stock_alert_completeness", "page": page,
                       "reason": f"{page} checkStockAlert() does not push 'stock-low' notification — low-stock warnings missing"})
    return issues


def check_pm_alert_completeness(page):
    """
    PM health function must push both 'pm-overdue' AND 'pm-duesoon' notifications.
    """
    content = read_file(page)
    if not content:
        return []
    # Find the PM health / PM notifications function
    m = re.search(r"(?:async\s+)?function\s+(?:loadPMHealth|buildPMNotif|checkPMAlerts)\s*\(", content)
    if not m:
        return [{"check": "pm_alert_completeness", "page": page,
                 "reason": f"{page} PM alert function (loadPMHealth) not found — no PM overdue/due-soon notifications"}]
    body = content[m.start():m.start() + 8000]   # function can be 100+ lines
    issues = []
    if "pm-overdue" not in body:
        issues.append({"check": "pm_alert_completeness", "page": page,
                       "reason": f"{page} PM alert function does not push 'pm-overdue' — overdue PM tasks go unnoticed"})
    if "pm-duesoon" not in body:
        issues.append({"check": "pm_alert_completeness", "page": page,
                       "reason": f"{page} PM alert function does not push 'pm-duesoon' — due-soon tasks go unnoticed"})
    return issues


# ── Layer 4: Init integration ─────────────────────────────────────────────────

def check_build_notifications_on_init(page):
    """
    buildNotifications() or checkStockAlert() must be called during board
    initialization so workers see alerts immediately when they open the hive.
    """
    content = read_file(page)
    if not content:
        return []
    # Find the main init function (initBoard, init, or DOMContentLoaded handler)
    init_m = re.search(r"async function\s+initBoard\s*\(", content)
    if not init_m:
        return []
    body = content[init_m.start():init_m.start() + 3000]
    if "buildNotifications" not in body and "checkStockAlert" not in body:
        return [{"check": "build_notifications_init", "page": page,
                 "reason": f"{page} initBoard() does not call buildNotifications() or checkStockAlert() — workers see no notifications on board load"}]
    return []


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    # L1
    "approval_channel_events", "module_level_channels",
    # L2
    "worker_approval_toasts",
    # L3
    "notification_bell", "stock_alert_completeness", "pm_alert_completeness",
    # L4
    "build_notifications_init",
]

CHECK_LABELS = {
    # L1
    "approval_channel_events": "L1  Approval channel subscribes to INSERT + UPDATE",
    "module_level_channels":   "L1  Channel variables declared at module level",
    # L2
    "worker_approval_toasts":  "L2  Worker toasts for both approved + rejected",
    # L3
    "notification_bell":       "L3  Notification bell made visible on hive init",
    "stock_alert_completeness":"L3  checkStockAlert pushes stock-out + stock-low",
    "pm_alert_completeness":   "L3  PM health pushes pm-overdue + pm-duesoon",
    # L4
    "build_notifications_init":"L4  buildNotifications called in initBoard()",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nNotification and Alert Health Validator (4-layer)"))
    print("=" * 55)

    all_issues = []
    all_issues += check_approval_channel_events(HIVE_PAGE, REQUIRED_INSERT_UPDATE_CHANNELS)
    all_issues += check_module_level_channels(HIVE_PAGE, REQUIRED_MODULE_LEVEL)
    all_issues += check_worker_approval_toasts(HIVE_PAGE)
    all_issues += check_notification_bell(HIVE_PAGE)
    all_issues += check_stock_alert_completeness(HIVE_PAGE)
    all_issues += check_pm_alert_completeness(HIVE_PAGE)
    all_issues += check_build_notifications_on_init(HIVE_PAGE)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "notifications",
        "total_checks": total,
        "passed":       n_pass,
        "skipped":      n_skip,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
    }
    with open("notifications_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
