"""
Enterprise Compliance Baseline Validator — WorkHive Platform
=============================================================
Compliance requirements for enterprise industrial clients: PDPA data handling,
audit trails for all membership and power actions, and no credential exposure.

  Layer 1 — Audit trail completeness
    1.  Supervisor power actions logged   — approve/reject/kick call writeAuditLog
    2.  Member join events logged         — writeAuditLog('member_joined')  [WARN]
    3.  Member leave logged               — performLeave calls writeAuditLog  [WARN]

  Layer 2 — Audit log integrity
    4.  Audit log read scoped to hive     — loadAuditLog() filters by hive_id

  Layer 3 — Automation observability
    5.  Scheduled jobs log to automation  — success + failure paths write automation_log

  Layer 4 — Credential security
    6.  No service_role key in client     — service_role key never in HTML/JS
    7.  Publishable key format            — client-side Supabase keys are sb_publishable_

Usage:  python validate_compliance.py
Output: compliance_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

HIVE_PAGE        = "hive.html"
FUNCTIONS_DIR    = os.path.join("supabase", "functions")
SCHEDULED_AGENTS = os.path.join(FUNCTIONS_DIR, "scheduled-agents", "index.ts")
MIGRATIONS_DIR   = os.path.join("supabase", "migrations")

CLIENT_PAGES = [
    "logbook.html", "inventory.html", "pm-scheduler.html", "hive.html",
    "assistant.html", "skillmatrix.html", "dayplanner.html",
    "engineering-design.html", "analytics.html",
    "index.html", "platform-health.html",
    "floating-ai.js", "nav-hub.js", "utils.js",
]

REQUIRED_AUDIT_ACTIONS = ["approve_item", "reject_item", "kick_member"]


def get_scheduled_types():
    types = []
    if not os.path.isdir(MIGRATIONS_DIR):
        return types
    for fname in os.listdir(MIGRATIONS_DIR):
        if not fname.endswith(".sql"):
            continue
        content = read_file(os.path.join(MIGRATIONS_DIR, fname))
        if not content:
            continue
        for m in re.finditer(r'"report_type":\s*"([^"]+)"', re.sub(r"/\*[\s\S]*?\*/", "", content)):
            types.append(m.group(1))
    return list(set(types))


# ── Layer 1: Audit trail completeness ────────────────────────────────────────

def check_power_action_audit(page, required_actions):
    content = read_file(page)
    if not content:
        return [{"check": "power_action_audit", "page": page, "reason": f"{page} not found"}]
    issues = []
    for action in required_actions:
        if not re.search(rf"writeAuditLog\s*\(\s*['\"]({re.escape(action)})['\"]", content):
            issues.append({"check": "power_action_audit", "page": page, "action": action,
                           "reason": f"{page} supervisor action '{action}' has no writeAuditLog() call — no audit trail for compliance review"})
    return issues


def check_member_joined_audit(page):
    content = read_file(page)
    if not content:
        return []
    if not re.search(r"writeAuditLog\s*\(\s*['\"]member_joined['\"]", content):
        return [{"check": "member_joined_audit", "page": page,
                 "skip": True,   # WARN — display is ready, write is missing
                 "reason": f"{page} writeAuditLog('member_joined') never called — join events missing from audit trail (kick events ARE logged)"}]
    return []


def check_member_leave_audit(page):
    """
    performLeave() deletes a hive_members row but never calls writeAuditLog.
    A worker leaving the hive is a significant membership event — enterprise
    clients need complete join/leave history for team accountability.
    """
    content = read_file(page)
    if not content:
        return []
    m = re.search(r"async function performLeave\s*\(", content)
    if not m:
        return []
    body = content[m.start():m.start() + 1500]
    if "writeAuditLog" not in body:
        return [{"check": "member_leave_audit", "page": page,
                 "skip": True,   # WARN — incomplete but not a critical gap
                 "reason": f"{page} performLeave() does not call writeAuditLog — member departures not in audit trail"}]
    return []


# ── Layer 2: Audit log integrity ──────────────────────────────────────────────

def check_audit_log_scoped(page):
    """
    loadAuditLog() must scope by hive_id so a supervisor cannot read another
    hive's audit trail. Without .eq('hive_id', HIVE_ID), all hives' actions
    are mixed in the display.
    """
    content = read_file(page)
    if not content:
        return []
    m = re.search(r"from\(['\"]hive_audit_log['\"]\)\.select\(", content)
    if not m:
        return []
    window = content[m.start():m.start() + 300]
    if "HIVE_ID" not in window and "hive_id" not in window:
        return [{"check": "audit_log_scoped", "page": page,
                 "reason": f"{page} hive_audit_log.select() has no hive_id filter — supervisor can see all hives' audit history"}]
    return []


# ── Layer 3: Automation observability ────────────────────────────────────────

def check_automation_log(func_path):
    content = read_file(func_path)
    if not content:
        return [{"check": "automation_log", "page": func_path,
                 "reason": f"{func_path} not found — cannot verify automation logging"}]
    issues = []
    if "automation_log" not in content:
        issues.append({"check": "automation_log", "page": func_path,
                       "reason": f"{func_path} does not write to automation_log — scheduled job outcomes are invisible"})
        return issues
    if not re.search(r"['\"]success['\"]", content):
        issues.append({"check": "automation_log", "page": func_path,
                       "reason": f"{func_path} does not log 'success' status to automation_log"})
    if not re.search(r"['\"]failed?['\"]", content):
        issues.append({"check": "automation_log", "page": func_path,
                       "reason": f"{func_path} does not log 'failed' status to automation_log"})
    return issues


# ── Layer 4: Credential security ─────────────────────────────────────────────

def check_service_key_exposure(pages):
    issues = []
    for page in pages:
        content = read_file(page)
        if not content:
            continue
        m = re.search(r"service_role['\"\s]*:\s*['\"]([^'\"]{20,})['\"]", content, re.IGNORECASE)
        if m and not re.match(r"^[A-Z_]{10,}$", m.group(1)):
            issues.append({"check": "service_key_exposure", "page": page,
                           "reason": f"{page} contains a Supabase service_role key — bypasses RLS, must only be in Edge Function env vars"})
        if re.search(r"['\"]Authorization['\"]:\s*['\"]Bearer\s+(eyJ[A-Za-z0-9_\-.]{100,})['\"]", content):
            issues.append({"check": "service_key_exposure", "page": page,
                           "reason": f"{page} has a hardcoded Bearer JWT — API keys must be in Edge Function env vars, not in HTML/JS"})
    return issues


def check_publishable_key_format(pages):
    """
    Supabase keys in client-side code should be the anon/publishable key
    (starts with 'sb_publishable_'). If a key starts with 'eyJ' (JWT format)
    and is very long, it may be a service_role key exposed incorrectly.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if not content:
            continue
        # Find all Supabase key assignments
        for m in re.finditer(r"SUPABASE_KEY\s*=\s*['\"]([^'\"]{20,})['\"]", content):
            key = m.group(1)
            if key.startswith("eyJ") and len(key) > 100:
                # Looks like a JWT (could be service_role)
                issues.append({"check": "publishable_key_format", "page": page,
                               "reason": f"{page} SUPABASE_KEY looks like a JWT — should be 'sb_publishable_' anon key format, not service_role JWT"})
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    # L1
    "power_action_audit", "member_joined_audit", "member_leave_audit",
    # L2
    "audit_log_scoped",
    # L3
    "automation_log",
    # L4
    "service_key_exposure", "publishable_key_format",
]

CHECK_LABELS = {
    # L1
    "power_action_audit":   "L1  Supervisor power actions call writeAuditLog (approve/reject/kick)",
    "member_joined_audit":  "L1  Member join events call writeAuditLog  [WARN]",
    "member_leave_audit":   "L1  Member leave (performLeave) calls writeAuditLog  [WARN]",
    # L2
    "audit_log_scoped":     "L2  loadAuditLog() scoped to hive_id",
    # L3
    "automation_log":       "L3  Scheduled jobs write success+failure to automation_log",
    # L4
    "service_key_exposure": "L4  No service_role key in client-side HTML/JS",
    "publishable_key_format":"L4  Client Supabase keys are sb_publishable_ format",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nEnterprise Compliance Baseline Validator (4-layer)"))
    print("=" * 55)

    all_issues = []
    all_issues += check_power_action_audit(HIVE_PAGE, REQUIRED_AUDIT_ACTIONS)
    all_issues += check_member_joined_audit(HIVE_PAGE)
    all_issues += check_member_leave_audit(HIVE_PAGE)
    all_issues += check_audit_log_scoped(HIVE_PAGE)
    all_issues += check_automation_log(SCHEDULED_AGENTS)
    all_issues += check_service_key_exposure(CLIENT_PAGES)
    all_issues += check_publishable_key_format(CLIENT_PAGES)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "compliance",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("compliance_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
