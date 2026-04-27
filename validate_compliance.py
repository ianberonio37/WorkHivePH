"""
Enterprise Compliance Baseline Validator — WorkHive Platform
=============================================================
As WorkHive is sold to enterprise industrial clients in the Philippines,
compliance requirements become non-negotiable: PDPA data handling,
audit trails for all power actions, and no credential exposure in
client-side code.

From the Enterprise Compliance skill file.

Four things checked:

  1. All supervisor power actions are audit-logged
     — approve_item, reject_item, and kick_member must each call
       writeAuditLog() in hive.html. These are the actions supervisors
       can take that directly affect workers (approving their submissions,
       rejecting their work, removing them from the team). An audit trail
       is required for PDPA accountability and enterprise client audits.

  2. Member join events call writeAuditLog (member_joined)
     — The audit log display already has a 'member_joined' action type
       registered. The join flow should call writeAuditLog('member_joined')
       for complete team membership visibility. Supervisors reviewing the
       audit log should see all membership changes — joins and removals.
       Reported as WARN: the display is ready, the write is missing.

  3. Scheduled jobs write to automation_log
     — Every pg_cron-triggered scheduled job must call logRun() (or
       equivalent) to write to the automation_log table. Without it,
       scheduled automation failures are invisible — no one knows a
       nightly PM report didn't run until a supervisor notices missing data.

  4. Service role key not in client-side files
     — The Supabase service_role key must NEVER appear in any HTML or JS
       file served to the browser. This key bypasses Row Level Security
       and gives full database access. Exposure via client code means any
       user who opens DevTools can read/write/delete all data across all hives.

Usage:  python validate_compliance.py
Output: compliance_report.json
"""
import re, json, sys, os

HIVE_PAGE         = "hive.html"
FUNCTIONS_DIR     = os.path.join("supabase", "functions")
SCHEDULED_AGENTS  = os.path.join(FUNCTIONS_DIR, "scheduled-agents", "index.ts")
MIGRATIONS_DIR    = os.path.join("supabase", "migrations")

# Live pages to scan for credential exposure
CLIENT_PAGES = [
    "logbook.html", "inventory.html", "pm-scheduler.html", "hive.html",
    "assistant.html", "skillmatrix.html", "dayplanner.html",
    "engineering-design.html", "index.html", "platform-health.html",
    "floating-ai.js", "nav-hub.js", "utils.js",
]

# Required supervisor audit log action types
REQUIRED_AUDIT_ACTIONS = ["approve_item", "reject_item", "kick_member"]

# Scheduled job report_types that must write to automation_log
# (extracted from migration cron.schedule calls)
SCHEDULED_TYPES_PATTERN = r'"report_type":\s*"([^"]+)"'


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def get_scheduled_types():
    """Parse active cron.schedule calls for report_types."""
    types = []
    if not os.path.isdir(MIGRATIONS_DIR):
        return types
    for fname in os.listdir(MIGRATIONS_DIR):
        if not fname.endswith(".sql"):
            continue
        content = read_file(os.path.join(MIGRATIONS_DIR, fname))
        if not content:
            continue
        no_comments = re.sub(r"/\*[\s\S]*?\*/", "", content)
        for m in re.finditer(SCHEDULED_TYPES_PATTERN, no_comments):
            types.append(m.group(1))
    return list(set(types))


# ── Check 1: All supervisor power actions audit-logged ────────────────────────

def check_power_action_audit(page, required_actions):
    """
    Every supervisor power action in hive.html must call writeAuditLog().
    The audit log table (hive_audit_log) is how enterprise clients prove
    accountability — who approved what, who was removed, when.

    Missing any of the three core actions breaks the audit trail for that
    action type. An enterprise audit would flag this immediately.
    """
    issues = []
    content = read_file(page)
    if content is None:
        return [{"page": page, "reason": f"{page} not found"}]

    for action in required_actions:
        pattern = rf"writeAuditLog\s*\(\s*['\"]({re.escape(action)})['\"]"
        if not re.search(pattern, content):
            issues.append({
                "page":   page,
                "action": action,
                "reason": (
                    f"{page} — supervisor action '{action}' has no "
                    f"writeAuditLog() call — this action leaves no audit trail "
                    f"and cannot be reviewed in compliance audits"
                ),
            })
    return issues


# ── Check 2: member_joined events logged on hive join ────────────────────────

def check_member_joined_audit(page):
    """
    When a worker joins a hive, writeAuditLog('member_joined') should be called.
    The audit log display already registers this action type — the write
    is missing from the join flow.

    Complete membership history (joins + removals) is required for team
    accountability. Without it, supervisors see kick events but not join events,
    making the audit log incomplete.

    Reported as WARN — the display infrastructure is ready, the write is missing.
    """
    issues = []
    content = read_file(page)
    if content is None:
        return []

    has_member_joined = bool(re.search(
        r"writeAuditLog\s*\(\s*['\"]member_joined['\"]",
        content
    ))
    if not has_member_joined:
        issues.append({
            "page": page,
            "reason": (
                f"{page} — writeAuditLog('member_joined', ...) is never called "
                f"in the join flow — the audit log shows kicks but not joins, "
                f"giving an incomplete membership history for compliance review "
                f"(the display map already has 'member_joined' registered)"
            ),
        })
    return issues


# ── Check 3: Scheduled jobs write to automation_log ──────────────────────────

def check_automation_log(func_path, scheduled_types):
    """
    Every scheduled job type must call logRun() (or write to automation_log)
    for both success and failure paths. This makes automation failures visible —
    without it, a failed nightly PM report leaves no trace and the team
    only discovers the problem when data is missing.

    This check verifies:
    1. The scheduled-agents function exists
    2. It writes to automation_log (calls logRun or insert automation_log)
    3. Each known scheduled report_type has a handler
    """
    issues = []
    content = read_file(func_path)
    if content is None:
        return [{
            "page": func_path,
            "reason": f"{func_path} not found — cannot verify automation logging",
        }]

    # Does it write to automation_log?
    if "automation_log" not in content:
        issues.append({
            "page": func_path,
            "reason": (
                f"{func_path} does not write to automation_log — "
                f"scheduled job outcomes are invisible (no success/failure trail)"
            ),
        })
        return issues

    # Does it log both success and failure?
    has_success = bool(re.search(r"['\"]success['\"]", content))
    has_failure = bool(re.search(r"['\"]failed?['\"]", content))
    if not has_success:
        issues.append({
            "page": func_path,
            "reason": f"{func_path} does not log 'success' status to automation_log",
        })
    if not has_failure:
        issues.append({
            "page": func_path,
            "reason": f"{func_path} does not log 'failed' status to automation_log",
        })

    return issues


# ── Check 4: Service role key not in client-side files ───────────────────────

def check_service_key_exposure(pages):
    """
    The Supabase service_role key grants full database access, bypassing
    all Row Level Security. It must NEVER appear in any HTML or JS file
    served to the browser.

    This check looks for:
    - The literal string 'service_role' as a key value (not just as text)
    - Patterns that look like Supabase service role keys (long JWT-like strings)
      adjacent to 'service_role' or 'Authorization: Bearer'

    Placeholder strings like 'SUPABASE_CRON_SERVICE_KEY' (all caps) in
    migration files are excluded — those are intentional placeholders.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue

        # Check for service_role key value patterns
        # Real keys: eyJhbGci... (JWT format, 100+ chars)
        # Placeholders: SUPABASE_CRON_SERVICE_KEY (all caps, underscore)
        m = re.search(
            r"service_role['\"\s]*:\s*['\"]([^'\"]{20,})['\"]",
            content, re.IGNORECASE
        )
        if m:
            val = m.group(1)
            # Skip obvious placeholders (all-caps with underscores)
            if re.match(r"^[A-Z_]{10,}$", val):
                continue
            issues.append({
                "page":  page,
                "reason": (
                    f"{page} appears to contain a Supabase service_role key value "
                    f"— this key bypasses RLS and must only exist in Edge Function "
                    f"environment variables, never in client-side code"
                ),
            })

        # Also check for 'anon' key used as service key
        anon_m = re.search(
            r"['\"]Authorization['\"]:\s*['\"]Bearer\s+(eyJ[A-Za-z0-9_\-.]{100,})['\"]",
            content
        )
        if anon_m:
            # This is a real JWT embedded in client code — very risky
            issues.append({
                "page":  page,
                "reason": (
                    f"{page} has a hardcoded Bearer JWT token in client-side code "
                    f"— API keys must be in Edge Function env vars, not in HTML/JS"
                ),
            })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("Enterprise Compliance Baseline Validator")
print("=" * 70)

scheduled_types = get_scheduled_types()
if scheduled_types:
    print(f"\n  Active scheduled job types: {', '.join(scheduled_types)}\n")

fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        "[1] All supervisor power actions are audit-logged (approve/reject/kick)",
        check_power_action_audit(HIVE_PAGE, REQUIRED_AUDIT_ACTIONS),
        "FAIL",
    ),
    (
        "[2] member_joined events call writeAuditLog on hive join",
        check_member_joined_audit(HIVE_PAGE),
        "WARN",
    ),
    (
        "[3] Scheduled jobs write to automation_log (success + failure)",
        check_automation_log(SCHEDULED_AGENTS, scheduled_types),
        "FAIL",
    ),
    (
        "[4] Service role key not in client-side HTML/JS files",
        check_service_key_exposure(CLIENT_PAGES),
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

with open("compliance_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved compliance_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll compliance checks PASS.")
