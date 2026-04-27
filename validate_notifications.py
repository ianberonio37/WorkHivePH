"""
Notification and Alert Health Validator — WorkHive Platform
============================================================
WorkHive uses two notification layers:
  1. In-app toasts — immediate feedback on actions (showToast)
  2. Supabase Realtime — live updates across all team members

If either layer breaks, workers miss critical events:
  - A supervisor approves a part but the worker's screen never updates
  - A new submission arrives in the approval queue but the supervisor
    isn't notified via the bell
  - A channel variable leaks because it was declared inside a function
    and can't be cleaned up on page unload

From the Notifications skill file.

Four things checked:

  1. Approval channel subscribes to both INSERT and UPDATE
     — The hive-approval Realtime channel must listen for INSERT
       (new worker submissions entering the queue) AND UPDATE
       (status changes when supervisor approves or rejects).
       INSERT-only: supervisor never sees status changes reflected live.
       UPDATE-only: new submissions don't appear in real time.

  2. All Realtime channel variables declared at module level
     — Channel variables must be declared at the top of the script,
       not inside functions. A channel declared inside a function
       cannot be accessed in the beforeunload cleanup handler —
       it leaks as a ghost subscription consuming Supabase quota.

  3. Worker approval notifications fire for both approved and rejected
     — When a supervisor approves or rejects a worker's submission,
       the worker must receive a toast notification immediately via
       the worker-approval Realtime channel. Missing 'approved' or
       'rejected' toast means workers don't know their submission
       was acted on — they keep waiting or wonder why it disappeared.

  4. Notification bell shown when hive is active
     — The notif-wrapper element starts hidden (display:none).
       When a hive board initialises, it must be made visible so
       workers can see and interact with the notification bell.
       A permanently hidden bell means workers miss all alerts.

Usage:  python validate_notifications.py
Output: notifications_report.json
"""
import re, json, sys

HIVE_PAGE = "hive.html"

# Channel names that must subscribe to both INSERT and UPDATE
REQUIRED_INSERT_UPDATE_CHANNELS = [
    "hive-approval",    # supervisor approval queue — needs both
]

# Channel variables that must be at module level (not inside functions)
REQUIRED_MODULE_LEVEL = [
    "presenceChannel",
    "feedChannel",
    "approvalChannel",
    "workerApprovalCh",
    "inventoryChannel",
]


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


# ── Check 1: Approval channel subscribes to INSERT and UPDATE ─────────────────

def check_approval_channel_events(page, channel_names):
    """
    The hive-approval Realtime channel must subscribe to both INSERT and UPDATE
    postgres_changes events.

    INSERT: fires when a worker submits a new item — appears in approval queue.
    UPDATE: fires when status changes (approved/rejected) — removes from queue.

    Missing INSERT: supervisor's queue misses new submissions in real time.
    Missing UPDATE: queue items don't disappear when actioned live.
    """
    issues = []
    content = read_file(page)
    if content is None:
        return [{"page": page, "reason": f"{page} not found"}]

    for channel_name in channel_names:
        # Find the channel setup block
        ch_m = re.search(
            rf"db\.channel\s*\(['\"]({re.escape(channel_name)}[^'\"]*)['\"]",
            content
        )
        if not ch_m:
            issues.append({
                "page":    page,
                "channel": channel_name,
                "reason": (
                    f"{page} — channel '{channel_name}' not found — "
                    f"approval queue Realtime subscription is missing entirely"
                ),
            })
            continue

        # Extract the channel setup block (200 lines after channel creation)
        start = ch_m.start()
        block = "\n".join(content[start:start + 8000].splitlines()[:100])

        has_insert = bool(re.search(r"event:\s*['\"]INSERT['\"]", block))
        has_update = bool(re.search(r"event:\s*['\"]UPDATE['\"]", block))

        if not has_insert:
            issues.append({
                "page":    page,
                "channel": channel_name,
                "reason": (
                    f"{page} — channel '{channel_name}' has no INSERT subscription — "
                    f"new worker submissions won't appear in the approval queue in real time"
                ),
            })
        if not has_update:
            issues.append({
                "page":    page,
                "channel": channel_name,
                "reason": (
                    f"{page} — channel '{channel_name}' has no UPDATE subscription — "
                    f"status changes (approved/rejected) won't reflect in the queue live"
                ),
            })
    return issues


# ── Check 2: Channel variables declared at module level ───────────────────────

def check_module_level_channels(page, channel_vars):
    """
    Realtime channel variables must be declared at the top of the script
    scope (module level), not inside functions. This ensures they can be
    accessed by the beforeunload handler to clean up on page navigation.

    A channel variable declared inside a function:
      async function initBoard() {
        let feedChannel = db.channel(...);  // ← invisible to beforeunload
      }

    Cannot be cleaned up. It runs as a ghost subscription until the tab closes.
    """
    issues = []
    content = read_file(page)
    if content is None:
        return [{"page": page, "reason": f"{page} not found"}]

    for var in channel_vars:
        # Find ALL declarations of this variable
        declarations = list(re.finditer(
            rf"(?:let|const|var)\s+{re.escape(var)}\b",
            content
        ))
        if not declarations:
            issues.append({
                "page": page,
                "var":  var,
                "reason": (
                    f"{page} — channel variable '{var}' is never declared — "
                    f"this channel cannot be managed or cleaned up"
                ),
            })
            continue

        # Check if ANY declaration is at module level (low indentation)
        has_module_level = False
        for decl in declarations:
            line_start = content.rfind("\n", 0, decl.start()) + 1
            indent = len(content[line_start:decl.start()]) - len(content[line_start:decl.start()].lstrip())
            if indent <= 2:  # 0 or 2 spaces = module level
                has_module_level = True
                break

        if not has_module_level:
            issues.append({
                "page": page,
                "var":  var,
                "reason": (
                    f"{page} — channel variable '{var}' is only declared inside "
                    f"a function — it cannot be accessed by the beforeunload "
                    f"cleanup handler and will leak as a ghost subscription"
                ),
            })
    return issues


# ── Check 3: Worker approval toasts fire for approved AND rejected ─────────────

def check_worker_approval_toasts(page):
    """
    Workers must receive a toast notification when their item is approved
    or rejected. This is delivered via the worker-approval Realtime channel
    which listens for UPDATE events on the worker's own items.

    Missing 'approved' toast: worker submits a part, supervisor approves it,
    worker never knows — they might resubmit or check with the supervisor.

    Missing 'rejected' toast: worker's submission is silently rejected —
    they have no idea their submission was refused and why.
    """
    issues = []
    content = read_file(page)
    if content is None:
        return [{"page": page, "reason": f"{page} not found"}]

    # Find the worker approval channel block
    worker_ch_m = re.search(
        r"channel\s*\(['\"]worker-appr['\"\:]",
        content
    )
    if not worker_ch_m:
        return [{
            "page": page,
            "reason": (
                f"{page} — worker approval channel ('worker-appr') not found — "
                f"workers will never receive approved/rejected notifications"
            ),
        }]

    # Extract channel block (next 100 lines)
    start = worker_ch_m.start()
    block = "\n".join(content[start:start + 5000].splitlines()[:100])

    has_approved_toast = bool(re.search(
        r"approved.*showToast|showToast.*approved",
        block, re.DOTALL
    ))
    has_rejected_toast = bool(re.search(
        r"rejected.*showToast|showToast.*rejected",
        block, re.DOTALL
    ))

    if not has_approved_toast:
        issues.append({
            "page": page,
            "reason": (
                f"{page} — worker approval channel has no showToast for 'approved' "
                f"status — workers won't know when their submission is approved"
            ),
        })
    if not has_rejected_toast:
        issues.append({
            "page": page,
            "reason": (
                f"{page} — worker approval channel has no showToast for 'rejected' "
                f"status — workers won't know when their submission is rejected"
            ),
        })
    return issues


# ── Check 4: Notification bell shown when hive is active ─────────────────────

def check_notification_bell(page):
    """
    The notification bell (#notif-wrapper) starts as display:none.
    When the hive board initialises with an active HIVE_ID, it must be
    made visible (display:flex or display:block).

    A permanently hidden bell means workers can never see or interact
    with notifications — alerts accumulate silently.
    """
    issues = []
    content = read_file(page)
    if content is None:
        return [{"page": page, "reason": f"{page} not found"}]

    # Is the bell present and initially hidden?
    has_bell = bool(re.search(
        r'id=["\']notif-wrapper["\'][^>]*display\s*:\s*none',
        content, re.IGNORECASE
    ))
    if not has_bell:
        return []  # no bell to check

    # Is there code to show it?
    has_show = bool(re.search(
        r"notif-wrapper.*style\.display|getElementById\(['\"]notif-wrapper['\"\)][^;]*display",
        content, re.IGNORECASE
    ))
    if not has_show:
        issues.append({
            "page": page,
            "reason": (
                f"{page} — #notif-wrapper starts hidden but is never made visible "
                f"— notification bell is permanently hidden from workers in hive mode"
            ),
        })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("Notification and Alert Health Validator")
print("=" * 70)

fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        "[1] Approval channel subscribes to both INSERT and UPDATE events",
        check_approval_channel_events(HIVE_PAGE, REQUIRED_INSERT_UPDATE_CHANNELS),
        "FAIL",
    ),
    (
        "[2] Realtime channel variables declared at module level",
        check_module_level_channels(HIVE_PAGE, REQUIRED_MODULE_LEVEL),
        "FAIL",
    ),
    (
        "[3] Worker approval toasts fire for both approved and rejected",
        check_worker_approval_toasts(HIVE_PAGE),
        "FAIL",
    ),
    (
        "[4] Notification bell visible when hive is active",
        check_notification_bell(HIVE_PAGE),
        "FAIL",
    ),
]

for label, issues, severity in checks:
    print(f"\n{label}\n")
    if not issues:
        print("  PASS")
    else:
        for iss in issues:
            print(f"  {severity}  {iss.get('page', iss.get('func', '?'))}")
            print(f"        {iss['reason']}")
        if severity == "FAIL":
            fail_count += len(issues)
        else:
            warn_count += len(issues)
    report[label] = issues

print(f"\n{'=' * 70}")
print(f"Result: {fail_count} FAIL  {warn_count} WARN")

with open("notifications_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved notifications_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll notification health checks PASS.")
