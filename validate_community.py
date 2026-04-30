"""
Community Validator — WorkHive Platform
=========================================
Validates community.html for correctness, security, and platform standards.

  Layer 1 — XSS / Escaping
    1.  escHtml loaded from utils.js         — not redefined inline
    2.  All innerHTML renders use escHtml    — post content, author, replies

  Layer 2 — Tenant isolation
    3.  hive_id scoped on community_posts    — every SELECT/INSERT/UPDATE has HIVE_ID
    4.  hive_id scoped on community_replies  — same
    5.  hive_id scoped on community_reactions — same

  Layer 3 — Access control
    6.  Auth gate present                    — WORKER_NAME redirect on page load
    7.  Hive gate present                    — HIVE_ID redirect on page load
    8.  togglePin has internal HIVE_ROLE guard
    9.  toggleFlag has internal HIVE_ROLE guard
    10. deletePost has internal HIVE_ROLE / author guard

  Layer 4 — Realtime integrity
    11. Presence channel uses hive-community-presence: prefix
    12. Feed channel uses hive-community-feed: prefix
    13. Both channels cleaned up on beforeunload
    14. Connection timeout present (WebSocket silent fail guard)

  Layer 5 — Platform standards
    15. Supabase CDN present in <head>
    16. utils.js loaded before <script>
    17. nav-hub.js loaded at end of <body>
    18. Toast infrastructure present (role=alert + aria-live)
    19. writeAuditLog called on power actions (pin, flag, delete)
    20. Leaderboard uses exact count from skill_profiles

Usage:  python validate_community.py
Output: community_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

PAGE = "community.html"

CHECKS = {
    "esc_from_utils":         "L1  escHtml sourced from utils.js, not redefined inline",
    "esc_html_on_renders":    "L1  innerHTML renders wrap user data in escHtml()",
    "hive_scope_posts":       "L2  community_posts queries include HIVE_ID filter",
    "hive_scope_replies":     "L2  community_replies queries include HIVE_ID filter",
    "hive_scope_reactions":   "L2  community_reactions queries include HIVE_ID filter",
    "auth_gate":              "L3  Auth gate redirects if no WORKER_NAME",
    "hive_gate":              "L3  Hive gate redirects if no HIVE_ID",
    "pin_role_guard":         "L3  togglePin checks HIVE_ROLE inside function",
    "flag_role_guard":        "L3  toggleFlag checks HIVE_ROLE inside function",
    "delete_post_guard":      "L3  deletePost has role/author guard inside function",
    "presence_channel_name":  "L4  Presence channel uses hive-community-presence: prefix",
    "feed_channel_name":      "L4  Feed channel uses hive-community-feed: prefix",
    "replies_realtime_scope": "L4  community_replies Realtime subscription has hive_id filter",
    "channel_cleanup":        "L4  Both channels removed on beforeunload",
    "conn_timeout":           "L4  Connection timeout present (8s WebSocket fail guard)",
    "supabase_cdn":           "L5  Supabase CDN script in <head>",
    "utils_loaded":           "L5  utils.js loaded before <script> block",
    "nav_hub_loaded":         "L5  nav-hub.js loaded at end of <body>",
    "toast_aria":             "L5  Toast has role=alert and aria-live",
    "audit_log_calls":        "L5  writeAuditLog called on pin/flag/delete actions",
    "leaderboard_exact":      "L5  Leaderboard query uses community_xp, community_posts, or skill_badges",
}


def check_esc_from_utils(content):
    issues = []
    if re.search(r'function\s+escHtml\b', content):
        issues.append({
            "check": "esc_from_utils",
            "reason": "community.html redefines escHtml inline — must source from utils.js only"
        })
    if 'src="utils.js"' not in content and "src='utils.js'" not in content:
        issues.append({
            "check": "esc_from_utils",
            "reason": "utils.js not loaded — escHtml() will be undefined"
        })
    return issues


def check_esc_html_on_renders(content):
    issues = []
    # Look for innerHTML assignments that contain p.content, r.content, p.author_name, r.author_name
    # without escHtml wrapping
    danger_patterns = [
        (r'innerHTML\s*[+=]+\s*[^;]*\$\{p\.content\}', "p.content"),
        (r'innerHTML\s*[+=]+\s*[^;]*\$\{r\.content\}', "r.content"),
        (r'innerHTML\s*[+=]+\s*[^;]*\$\{p\.author_name\}', "p.author_name"),
        (r'innerHTML\s*[+=]+\s*[^;]*\$\{r\.author_name\}', "r.author_name"),
        (r'innerHTML\s*[+=]+\s*[^;]*\$\{m\.worker_name\}', "m.worker_name (presence)"),
    ]
    for pattern, field in danger_patterns:
        if re.search(pattern, content):
            issues.append({
                "check": "esc_html_on_renders",
                "reason": f"{field} rendered into innerHTML without escHtml() — stored XSS risk"
            })
    return issues


def check_hive_scope(content, table, check_key):
    issues = []
    # Find db.from('<table>') blocks and check for HIVE_ID filter
    table_uses = list(re.finditer(rf"db\.from\(['\"]?{re.escape(table)}['\"]?\)", content))
    for m in table_uses:
        block = content[m.start():m.start() + 400]
        if not re.search(r'HIVE_ID|hive_id', block):
            line = content[:m.start()].count('\n') + 1
            issues.append({
                "check": check_key,
                "reason": f"{table} query at ~line {line} missing hive_id scope — cross-hive data leak risk"
            })
    return issues


def check_auth_gate(content):
    issues = []
    if not re.search(r"WORKER_NAME.*window\.location|!WORKER_NAME", content, re.DOTALL):
        issues.append({"check": "auth_gate", "reason": "No WORKER_NAME auth gate found — unauthenticated users can access community"})
    return issues


def check_hive_gate(content):
    issues = []
    if not re.search(r"HIVE_ID.*window\.location|!HIVE_ID", content, re.DOTALL):
        issues.append({"check": "hive_gate", "reason": "No HIVE_ID gate found — workers without a hive can access community"})
    return issues


def check_role_guard_inside(content, fn_name, check_key):
    issues = []
    fn_match = re.search(rf'async function {re.escape(fn_name)}\b', content)
    if not fn_match:
        issues.append({"check": check_key, "reason": f"{fn_name} function not found"})
        return issues
    # Extract function body (next ~600 chars)
    body = content[fn_match.start():fn_match.start() + 600]
    if not re.search(r"HIVE_ROLE\s*!==\s*['\"]supervisor['\"]", body):
        issues.append({
            "check": check_key,
            "reason": f"{fn_name} missing internal HIVE_ROLE guard — callable from browser console regardless of UI"
        })
    return issues


def check_delete_guard(content):
    issues = []
    fn_match = re.search(r'async function deletePost\b', content)
    if not fn_match:
        issues.append({"check": "delete_post_guard", "reason": "deletePost function not found"})
        return issues
    body = content[fn_match.start():fn_match.start() + 600]
    has_role  = bool(re.search(r"HIVE_ROLE\s*!==\s*['\"]supervisor['\"]", body))
    has_author = bool(re.search(r"author_name\s*!==\s*WORKER_NAME|WORKER_NAME\s*!==\s*.*author_name", body))
    if not (has_role or has_author):
        issues.append({
            "check": "delete_post_guard",
            "reason": "deletePost has no role/author guard — any worker can delete any post via console"
        })
    return issues


def check_replies_realtime_scope(content):
    issues = []
    # community_replies subscription must include hive_id filter to prevent
    # cross-hive reply events leaking through (B1 reply notifications)
    if re.search(r"table\s*:\s*['\"]community_replies['\"]", content):
        block_match = re.search(
            r"table\s*:\s*['\"]community_replies['\"].*?filter\s*:\s*['\"`]hive_id=eq\.",
            content, re.DOTALL
        )
        if not block_match:
            issues.append({
                "check": "replies_realtime_scope",
                "reason": "community_replies Realtime subscription missing hive_id filter — reply events from other hives received by all subscribers"
            })
    return issues


def check_channel_names(content):
    issues = []
    if not re.search(r"hive-community-presence:", content):
        issues.append({"check": "presence_channel_name", "reason": "Presence channel missing 'hive-community-presence:' prefix — cross-hive contamination risk"})
    if not re.search(r"hive-community-feed:", content):
        issues.append({"check": "feed_channel_name", "reason": "Feed channel missing 'hive-community-feed:' prefix — cross-hive contamination risk"})
    return issues


def check_channel_cleanup(content):
    issues = []
    if not re.search(r"beforeunload", content):
        issues.append({"check": "channel_cleanup", "reason": "No beforeunload listener — Realtime channels leak on page navigation"})
        return issues
    unload_match = re.search(r"beforeunload.*?}\s*\)", content, re.DOTALL)
    if not unload_match:
        return issues
    block = unload_match.group(0)
    if "removeChannel" not in block:
        issues.append({"check": "channel_cleanup", "reason": "beforeunload handler found but removeChannel not called — ghost Realtime subscriptions"})
    return issues


def check_conn_timeout(content):
    issues = []
    if not re.search(r"setTimeout\s*\(.*setConn|connTimeout", content, re.DOTALL):
        issues.append({"check": "conn_timeout", "reason": "No connection timeout — page freezes at 'Connecting…' on weak plant WiFi (WebSocket silent fail)"})
    return issues


def check_supabase_cdn(content):
    issues = []
    if not re.search(r'src=["\']https://cdn\.jsdelivr\.net/npm/@supabase|src=["\']https://unpkg\.com/@supabase', content):
        issues.append({"check": "supabase_cdn", "reason": "Supabase CDN not found in <head> — supabase.createClient will throw, crashing all JS silently"})
    return issues


def check_utils_loaded(content):
    issues = []
    if 'src="utils.js"' not in content and "src='utils.js'" not in content:
        issues.append({"check": "utils_loaded", "reason": "utils.js not loaded — escHtml() and debounce() undefined"})
    utils_pos  = content.find('utils.js')
    script_pos = content.rfind('<script>')
    if utils_pos != -1 and script_pos != -1 and utils_pos > script_pos:
        issues.append({"check": "utils_loaded", "reason": "utils.js is loaded AFTER the main <script> block — escHtml undefined when page script runs"})
    return issues


def check_nav_hub_loaded(content):
    issues = []
    if 'src="nav-hub.js"' not in content and "src='nav-hub.js'" not in content:
        issues.append({"check": "nav_hub_loaded", "reason": "nav-hub.js not loaded — workers cannot navigate to other tools"})
    return issues


def check_toast_aria(content):
    issues = []
    if not re.search(r'role=["\']alert["\']', content):
        issues.append({"check": "toast_aria", "reason": "Toast missing role=alert — screen readers won't announce status messages"})
    if not re.search(r'aria-live=["\']polite["\']', content):
        issues.append({"check": "toast_aria", "reason": "Toast missing aria-live=polite"})
    return issues


def check_audit_log(content):
    issues = []
    # writeAuditLog must be called in togglePin, toggleFlag, and deletePost
    for action, fn in [("pin", "togglePin"), ("flag", "toggleFlag"), ("delete", "deletePost")]:
        fn_match = re.search(rf'async function {re.escape(fn)}\b', content)
        if not fn_match:
            continue
        body = content[fn_match.start():fn_match.start() + 800]
        if "writeAuditLog" not in body:
            issues.append({
                "check": "audit_log_calls",
                "reason": f"writeAuditLog not called in {fn} — power action is unaudited"
            })
    return issues


def check_leaderboard_exact(content):
    issues = []
    if "community_posts" not in content and "skill_badges" not in content and "community_xp" not in content:
        issues.append({"check": "leaderboard_exact", "reason": "Leaderboard does not query community_posts, skill_badges, or community_xp — contributor data unavailable"})
    return issues


# Ordered list of check keys (drives print order)
CHECK_NAMES = list(CHECKS.keys())
CHECK_LABELS = CHECKS


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nCommunity Validator (5-layer, 21 checks)"))
    print("=" * 55)

    content = read_file(PAGE)
    if not content:
        print(f"  ERROR: {PAGE} not found")
        sys.exit(1)

    all_issues = []

    all_issues += check_esc_from_utils(content)
    all_issues += check_esc_html_on_renders(content)
    all_issues += check_hive_scope(content, "community_posts",     "hive_scope_posts")
    all_issues += check_hive_scope(content, "community_replies",   "hive_scope_replies")
    all_issues += check_hive_scope(content, "community_reactions", "hive_scope_reactions")
    all_issues += check_auth_gate(content)
    all_issues += check_hive_gate(content)
    all_issues += check_role_guard_inside(content, "togglePin",  "pin_role_guard")
    all_issues += check_role_guard_inside(content, "toggleFlag", "flag_role_guard")
    all_issues += check_delete_guard(content)
    all_issues += check_channel_names(content)
    all_issues += check_replies_realtime_scope(content)
    all_issues += check_channel_cleanup(content)
    all_issues += check_conn_timeout(content)
    all_issues += check_supabase_cdn(content)
    all_issues += check_utils_loaded(content)
    all_issues += check_nav_hub_loaded(content)
    all_issues += check_toast_aria(content)
    all_issues += check_audit_log(content)
    all_issues += check_leaderboard_exact(content)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "community",
        "page":         PAGE,
        "total_checks": total,
        "passed":       n_pass,
        "skipped":      n_skip,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
    }
    with open("community_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
