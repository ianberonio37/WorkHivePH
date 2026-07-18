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

  Layer 6 — Feature schema completeness (May 2026)
    21. All community_posts SELECTs include the optional columns when present
        in the schema: mentions, edited_at, deleted_at
    22. Soft-delete UI uses showUndoToast (not showToast) on deletePost
    23. parseMentions exists and is called from submitPost when @mention UI
        is present in the composer

  Layer 7 — DB trigger column safety (latent crash guard)
    24. badge_trigger_column_match — handle_community_post_xp INSERT into
        skill_badges only references columns that exist in the table schema.
        The 10th-post milestone badge insert will crash in production if
        badge_key (or any other column) is referenced but not defined on the
        table. ON CONFLICT clause is also checked against the schema.

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
    "select_includes_optional_cols": "L6  community_posts SELECTs include mentions/edited_at/deleted_at if any do",
    "soft_delete_uses_undo":  "L6  deletePost uses showUndoToast (soft-delete recovery window)",
    "mention_parser_wired":   "L6  parseMentions defined and called in submitPost when @mention UI exists",
    "badge_trigger_column_match": "L7  handle_community_post_xp INSERT columns all exist in skill_badges schema",
    "supervisor_edit_additive":   "L7  Supervisor action panel includes isMine edit button (not replacing it)",
    "community_xp_write_lockdown": "L3  community_xp has NO client write policy (XP is DEFINER-trigger-only)",
    "marketplace_bridge_present":  "L8  Community<->Marketplace X-bridge wired (person card + author links + seller link)",
    "best_answer_authz":           "L8  Best-answer/solved is DEFINER-gated (post-author/supervisor), never a client write",
    "nav_hub_activity_badge":      "L8  Cross-page community unread badge wired (nav-hub.js counts new activity; community.html stamps last-seen)",
    "trade_peers_present":         "L8  'My people' same-trade discovery wired (get_hive_trade_peers DEFINER RPC + authz + client card)",
    "ai_context_piisafe":          "L8  Community AI context fed to the companion is PII-safe + opt-in transmitted (no worker names / post free-text to the LLM)",
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


def check_select_includes_optional_cols(content):
    """If ANY community_posts SELECT mentions one of {mentions, edited_at, deleted_at},
    EVERY community_posts SELECT should include all three. The community page added
    these columns in May 2026; missing them on a single call site means deleted rows
    leak (deleted_at), edit indicator disappears (edited_at), or @mentions don't
    render (mentions)."""
    issues = []
    optional_cols = ["mentions", "edited_at", "deleted_at"]
    # Find every .from('community_posts').select('...') block
    selects = re.findall(
        r"\.from\(\s*['\"]community_posts['\"]\s*\)\s*\.select\(\s*['\"]([^'\"]+)['\"]",
        content
    )
    if not selects:
        return issues
    # The "head:true" count selects don't have full column lists — exclude them.
    real_selects = [s for s in selects if "," in s and "count" not in s.replace(" ", "")]
    # If none of them mentions any optional column, the schema may simply not have
    # added them yet — skip silently.
    any_uses = any(any(c in s for c in optional_cols) for s in real_selects)
    if not any_uses:
        return issues
    # At least one SELECT uses an optional column → enforce on all.
    for idx, s in enumerate(real_selects):
        missing = [c for c in optional_cols if c not in s]
        if missing:
            line = content[:content.find(s)].count("\n") + 1
            issues.append({
                "check": "select_includes_optional_cols",
                "reason": f"community_posts SELECT at ~line {line} is missing {', '.join(missing)} — other SELECTs include these; inconsistency hides edit/delete/mention state"
            })
    return issues


def check_soft_delete_uses_undo(content):
    """If deletePost is implemented as a soft-delete (UPDATE on deleted_at),
    it should pair with showUndoToast for the 5-second recovery window. Hard-delete
    via .delete() means the row is gone — undo toast wouldn't help. So the rule
    only applies when deletePost is soft-delete shaped."""
    issues = []
    fn_match = re.search(r'async function deletePost\b', content)
    if not fn_match:
        return issues
    body = content[fn_match.start():fn_match.start() + 1500]
    is_soft_delete = bool(re.search(r"deleted_at\s*:", body) or
                          re.search(r"update\(\s*\{[^}]*deleted_at", body))
    if not is_soft_delete:
        return issues  # hard-delete shape, no undo expected
    if "showUndoToast" not in body:
        issues.append({
            "check": "soft_delete_uses_undo",
            "reason": "deletePost is soft-delete (sets deleted_at) but does not call showUndoToast — users have no recovery window"
        })
    return issues


def check_mention_parser_wired(content):
    """If the composer has @mention UI (mention-dropdown element or @ trigger
    handler), parseMentions must be defined and called from submitPost. Otherwise
    the dropdown sets up names but the insert doesn't store them."""
    issues = []
    has_mention_ui = bool(re.search(r"mention-dropdown|_maybeOpenMentionDropdown|selectMention", content))
    if not has_mention_ui:
        return issues
    if not re.search(r"function\s+parseMentions\b", content):
        issues.append({
            "check": "mention_parser_wired",
            "reason": "Composer has @mention UI but parseMentions() is not defined — selected names won't be stored on the post row"
        })
        return issues
    fn_match = re.search(r'async function submitPost\b', content)
    if not fn_match:
        return issues
    body = content[fn_match.start():fn_match.start() + 3000]
    if "parseMentions" not in body:
        issues.append({
            "check": "mention_parser_wired",
            "reason": "parseMentions exists but submitPost does not call it — mentions array would be empty on insert"
        })
    return issues


def check_badge_trigger_column_match():
    """
    handle_community_post_xp inserts into skill_badges with an explicit column
    list. If any column in that INSERT (or its ON CONFLICT clause) doesn't exist
    in the skill_badges table definition, PostgreSQL raises a column-not-found
    error — crashing silently for any worker who hits their 10th post per hive.

    Root cause of May 2026 latent bug: badge_key was added to the INSERT and
    ON CONFLICT but the skill_badges table was never given that column.
    """
    import glob as _glob
    issues = []

    migrations_dir = "supabase/migrations"
    if not os.path.isdir(migrations_dir):
        return issues

    migration_files = sorted(_glob.glob(os.path.join(migrations_dir, "*.sql")))
    full_sql = "\n".join(read_file(f) or "" for f in migration_files)

    # Extract skill_badges table column names from the CREATE TABLE block.
    # Match "skill_badges" followed immediately by the opening paren to avoid
    # matching the CONSTRAINT name "skill_badges_level_check" inside the body.
    table_match = re.search(
        r'"skill_badges"\s*\(([\s\S]*?)\n\s*\);',
        full_sql
    )
    if not table_match:
        return issues

    table_body = table_match.group(1)
    # Match: "col_name" followed by whitespace + either a quoted type ("text") or bare type (integer)
    schema_cols = set(re.findall(r'"(\w+)"\s+["\w]', table_body))
    schema_cols -= {"CONSTRAINT", "PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "EXCLUDE", "NOT"}

    # Also pick up columns added via later migrations (ALTER TABLE skill_badges ADD COLUMN ...)
    # Without this, the validator flags valid trigger columns as missing — e.g. badge_key
    # was added in 20260504000000_skill_badges_badge_key.sql via ALTER TABLE.
    for m in re.finditer(
        r'ALTER\s+TABLE\s+(?:"public"\.)?"?skill_badges"?\s+ADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?["]?(\w+)["]?',
        full_sql, re.IGNORECASE
    ):
        schema_cols.add(m.group(1))

    # Find the last definition of handle_community_post_xp (newest migration wins)
    fn_matches = list(re.finditer(
        r'CREATE OR REPLACE FUNCTION[^(]*handle_community_post_xp\s*\(\)',
        full_sql
    ))
    if not fn_matches:
        return issues

    fn_body = full_sql[fn_matches[-1].start():fn_matches[-1].start() + 3000]

    # Check INSERT column list
    insert_match = re.search(r'INSERT INTO skill_badges\s*\(([^)]+)\)', fn_body)
    if insert_match:
        insert_cols = [c.strip() for c in insert_match.group(1).split(",")]
        missing = [c for c in insert_cols if c not in schema_cols]
        if missing:
            issues.append({
                "check": "badge_trigger_column_match",
                "reason": (
                    f"handle_community_post_xp INSERT INTO skill_badges uses "
                    f"column(s) {missing} that don't exist in the skill_badges "
                    f"table definition — trigger crashes on every worker's 10th post"
                )
            })

    # Check ON CONFLICT column list
    conflict_match = re.search(r'ON CONFLICT\s*\(([^)]+)\)', fn_body)
    if conflict_match:
        conflict_cols = [c.strip() for c in conflict_match.group(1).split(",")]
        missing_cc = [c for c in conflict_cols if c not in schema_cols]
        if missing_cc:
            issues.append({
                "check": "badge_trigger_column_match",
                "reason": (
                    f"handle_community_post_xp ON CONFLICT references "
                    f"column(s) {missing_cc} not in skill_badges schema — "
                    f"PostgreSQL will reject the trigger (no such column or constraint)"
                )
            })

    return issues


def check_supervisor_edit_additive(content):
    """Supervisor action panel must include the isMine edit button, not replace it.

    Pattern: HIVE_ROLE === 'supervisor' ? `...` : (isMine ? `...edit...` : ...)
    Bug: if the supervisor branch completely replaces isMine edit actions, supervisors
    cannot edit their own posts.  Fix: add isMine check inside the supervisor branch.

    Detection: find the supervisor ternary block and verify 'openEditor' appears
    inside the supervisor branch (before the ternary fallback).
    """
    issues = []
    # Find supervisor ternary block
    sup_match = re.search(
        r"HIVE_ROLE\s*===\s*['\"]supervisor['\"].*?\?(.+?):\s*\(isMine",
        content, re.DOTALL
    )
    if not sup_match:
        return issues  # pattern not found — community.html may use different structure

    supervisor_branch = sup_match.group(1)
    if "openEditor" not in supervisor_branch:
        issues.append({
            "check": "supervisor_edit_additive",
            "reason": (
                "community.html supervisor action panel does not include openEditor — "
                "supervisors cannot edit their own posts; "
                "add isMine-conditional edit button inside the supervisor branch"
            ),
        })
    return issues


# Ordered list of check keys (drives print order)
def check_marketplace_bridge_present(content):
    """
    L8 — X-axis (Community PDDA 7th): community.html and marketplace-seller-profile.html must
    stay connected. The baseline was 0 cross-references either way (two islands); community builds
    TRUST, the free marketplace realizes it as jobs/trades. This gate freezes the bridge so it
    can't silently regress to 0: (a) the clickable person card exists, (b) post/reply/leaderboard
    authors are wired to it (author-link), (c) the person card links out to the seller profile,
    and (d) the reverse link (seller profile -> community forum) is present. Security-shaped:
    author names flow through escJsAttr in the onclick and the seller URL uses encodeURIComponent.
    """
    issues = []
    checks = [
        ("openPersonCard",            "community.html missing openPersonCard() — the clickable person-card identity"),
        ("class=\"author-link\"",     "community.html post/reply/leaderboard authors are not wired to the person card (author-link)"),
        ("marketplace-seller-profile.html?worker=", "person card does not link out to the seller's marketplace profile (Community->Marketplace X-nav)"),
        ("get_community_reputation",  "person card does not read portable reputation via get_community_reputation RPC"),
    ]
    for needle, reason in checks:
        if needle not in content:
            issues.append({"check": "marketplace_bridge_present", "reason": reason})
    # escJsAttr must guard the inline openPersonCard handler (name -> JS string)
    if "openPersonCard('${escJsAttr(" not in content:
        issues.append({"check": "marketplace_bridge_present",
                       "reason": "openPersonCard inline handler must escJsAttr the author name (breakout-XSS guard)"})
    # the reverse leg lives on the seller profile
    prof = read_file("marketplace-seller-profile.html") or ""
    if prof and "community.html?person=" not in prof:
        issues.append({"check": "marketplace_bridge_present",
                       "reason": "marketplace-seller-profile.html missing the reverse 'View in forum' link (Marketplace->Community X-nav)"})
    # browse-grid "Community-trusted" chip MUST batch via the DEFINER RPC — reading
    # skill_badges directly is RLS-dead (auth_uid=self, so a viewer can't see OTHER
    # sellers' badges → the chip silently never lit up).
    mkt = read_file("marketplace.html") or ""
    if mkt:
        if "get_marketplace_trust_badges" not in mkt:
            issues.append({"check": "marketplace_bridge_present",
                           "reason": "marketplace.html browse-grid trust chip must use the get_marketplace_trust_badges DEFINER RPC (a direct skill_badges read is RLS-dead)"})
        if re.search(r"from\('skill_badges'\)[^;]*voice_of_the_hive[^;]*\.in\('worker_name'", mkt):
            issues.append({"check": "marketplace_bridge_present",
                           "reason": "marketplace.html reads skill_badges directly for the grid chip (RLS-dead: auth_uid=self) — route through get_marketplace_trust_badges"})
    # the seeder must create community-LINKED sellers (profiles + a voice-of-hive grant),
    # else the whole bridge is dead on a fresh reset (marketplace_sellers was never seeded).
    seeder = read_file("test-data-seeder/seeders/marketplace.py") or ""
    orch   = read_file("test-data-seeder/seeders/orchestrator.py") or ""
    if seeder and ("seed_marketplace_sellers" not in seeder or "voice_of_the_hive" not in seeder):
        issues.append({"check": "marketplace_bridge_present",
                       "reason": "seeder must seed community-linked sellers (seed_marketplace_sellers + voice_of_the_hive grant) so the bridge is live on a fresh reset"})
    if orch and "seed_marketplace_sellers" not in orch:
        issues.append({"check": "marketplace_bridge_present",
                       "reason": "orchestrator.py must call seed_marketplace_sellers (after community + achievements)"})
    return issues


def check_best_answer_authz(content):
    """
    L8 — the best-answer / "solved" primitive turns the ephemeral feed into durable knowledge, but marking
    an answer is an AUTHORITY action: only the person who ASKED (post author) or a hive supervisor may do
    it, and there must be at most ONE accepted answer per post. That authority + the one-per-post rule must
    live in a SECURITY DEFINER RPC (never a client UPDATE that any member could forge), backed by a
    partial unique index. This gate freezes that: the client calls the RPC (no direct is_accepted write),
    the migration defines the DEFINER fn with an auth check + the one-accepted index.
    """
    issues = []
    if "markAnswer" in content or "is_accepted" in content or "best answer" in content.lower():
        if "set_community_best_answer" not in content:
            issues.append({"check": "best_answer_authz",
                           "reason": "community.html marks answers without the DEFINER RPC set_community_best_answer (client-forgeable)"})
        # a raw client UPDATE of is_accepted would bypass the authority gate
        if re.search(r"\.update\(\s*\{[^}]*is_accepted", content):
            issues.append({"check": "best_answer_authz",
                           "reason": "community.html writes is_accepted via a client .update() — must go through set_community_best_answer RPC"})
    # migration side: DEFINER fn with an authz check + one-accepted-per-post index
    import glob as _glob
    mig = "\n".join(read_file(f) or "" for f in sorted(_glob.glob("supabase/migrations/*community_best_answer*.sql")))
    if mig:
        if "SECURITY DEFINER" not in mig:
            issues.append({"check": "best_answer_authz", "reason": "set_community_best_answer must be SECURITY DEFINER"})
        if "role = 'supervisor'" not in mig and "role='supervisor'" not in mig:
            issues.append({"check": "best_answer_authz", "reason": "best-answer RPC missing the post-author/supervisor authority check"})
        if "WHERE is_accepted" not in mig and "WHERE (is_accepted" not in mig:
            issues.append({"check": "best_answer_authz", "reason": "missing the one-accepted-per-post partial unique index"})
    return issues


def check_ai_context_piisafe(content):
    """
    L8 — AI axis: community.html grounds the floating companion via WHAssistant.setContext so it can
    answer board questions. That summary is TRANSMITTED to the LLM gateway, so it must be PII-free BY
    CONSTRUCTION (the platform's ops-snapshot rule) AND transmission must be opt-in (piiSafe) so an
    un-audited page never leaks. This gate freezes: (a) the builder exists + marks piiSafe:true,
    (b) the builder does NOT interpolate a raw post body or another worker's name into the summary,
    (c) companion-launcher only sends page_context when piiSafe === true.
    """
    issues = []
    if "_setCommunityAiContext" not in content:
        issues.append({"check": "ai_context_piisafe", "reason": "community.html missing _setCommunityAiContext (AI-axis grounding)"})
        return issues
    # isolate the builder body so the PII check targets the summary, not the whole file
    m = re.search(r"function _setCommunityAiContext\(\)\s*\{.*?\n  \}", content, re.S)
    body = m.group(0) if m else ""
    if "setContext" not in body or "piiSafe: true" not in body:
        issues.append({"check": "ai_context_piisafe",
                       "reason": "_setCommunityAiContext must call WHAssistant.setContext with piiSafe: true"})
    # PII-safety: the transmitted summary must not interpolate raw post content or other-worker names.
    # (own-standing count is fine; the guard is against p.content / author_name flowing into the LLM text.)
    for bad in ("${p.content", "p.content ||", "author_name}", "${_aiTopContributors", "shared_disciplines.map(x => x.discipline).join"):
        if bad in body:
            issues.append({"check": "ai_context_piisafe",
                           "reason": f"_setCommunityAiContext summary interpolates PII into the LLM context ({bad}) — counts/disciplines only"})
    # launcher must gate transmission on the opt-in flag
    launcher = read_file("companion-launcher.js") or ""
    if launcher and "page_context" in launcher and "piiSafe === true" not in launcher:
        issues.append({"check": "ai_context_piisafe",
                       "reason": "companion-launcher.js transmits page_context without gating on _ragContext.piiSafe === true (PII opt-in)"})
    # 3rd leg: the gateway must FOLD context.page_context into the forwarded memory_block
    # (BEFORE the name-redaction, so it's scrubbed too) — else it's transmitted-but-unconsumed.
    gw = read_file("supabase/functions/ai-gateway/index.ts") or ""
    if gw:
        if ".page_context" not in gw or "memorySections.page_context" not in gw:
            issues.append({"check": "ai_context_piisafe",
                           "reason": "ai-gateway/index.ts must fold context.page_context into memory_block + set memorySections.page_context (else the client context is transmitted but never grounds the agent)"})
        # the fold must be BEFORE redactKnownNames(memory_block) so page_context is name-redacted too
        i_fold = gw.find("memorySections.page_context")
        i_redact = gw.find("redactKnownNames(memory_block")
        if i_fold != -1 and i_redact != -1 and i_fold > i_redact:
            issues.append({"check": "ai_context_piisafe",
                           "reason": "ai-gateway folds page_context AFTER redactKnownNames — must fold before so the block is PII-redacted (defense-in-depth)"})
    return issues


def check_nav_hub_activity_badge(content):
    """
    L8 — U/X retention: a community-of-practice retains members because something
    HAPPENED while they were away — so the global nav must surface unread community
    activity from every other page (mirrors the companion FAB nudge). This gate
    freezes the two halves of that loop so it can't silently regress:
      (a) nav-hub.js resolves a real Supabase client, fails closed on no session
          (never a console 401), counts NEW posts + replies BY OTHERS since the
          per-hive last-seen stamp, and paints the FAB dot + Community-tile pill.
      (b) community.html stamps the per-hive last-seen key so the badge clears on
          visit. The two sides must agree on the exact localStorage key.
    """
    issues = []
    KEY = "wh_community_last_seen:"
    nav = read_file("nav-hub.js") or ""
    if not nav:
        issues.append({"check": "nav_hub_activity_badge", "reason": "nav-hub.js not found"})
        return issues
    nav_needles = [
        ("checkCommunityActivity",  "nav-hub.js missing checkCommunityActivity() — the cross-page unread counter"),
        ("_paintCommunityBadges",   "nav-hub.js missing _paintCommunityBadges() — FAB dot + Community-tile pill painter"),
        (KEY,                       "nav-hub.js does not read the per-hive last-seen key (wh_community_last_seen:<hive>)"),
        ("v_community_posts_truth", "nav-hub.js activity count must read the canonical v_community_posts_truth view"),
        ("community_replies",       "nav-hub.js activity count must also include community_replies"),
        (".neq('author_name'",      "nav-hub.js must exclude the worker's OWN activity from the unread count (self-badge guard)"),
        ("getSession",              "nav-hub.js must fail closed on no auth session (no RLS-gated read / console 401 when signed out)"),
    ]
    for needle, reason in nav_needles:
        if needle not in nav:
            issues.append({"check": "nav_hub_activity_badge", "reason": reason})
    # community.html side: the seen-marker must be stamped so the badge clears on visit.
    if "_markCommunitySeen" not in content or KEY not in content:
        issues.append({"check": "nav_hub_activity_badge",
                       "reason": "community.html must stamp the last-seen marker (_markCommunitySeen → wh_community_last_seen:<hive>) so the nav badge clears on visit"})
    return issues


def check_trade_peers_present(content):
    """
    L8 — U-axis belonging (Community PDDA 7th): "my people" same-trade discovery. A new member
    must find hive-mates who share their trade. Because skill_badges RLS is auth_uid=self, peers'
    levels are unreadable client-side — so the match runs through a SECURITY DEFINER RPC
    (get_hive_trade_peers) that is authz-gated to active hive members and returns only the shared
    trades. This gate freezes: (a) the client calls the RPC + renders the card + reuses the person
    card, (b) the migration defines the DEFINER fn WITH the member-authz gate + a GRANT.
    """
    issues = []
    client_needles = [
        ("get_hive_trade_peers", "community.html does not call the get_hive_trade_peers RPC"),
        ("loadTradePeers",       "community.html missing loadTradePeers() — the 'my people' loader"),
        ("trade-peers-card",     "community.html missing the #trade-peers-card container"),
    ]
    for needle, reason in client_needles:
        if needle not in content:
            issues.append({"check": "trade_peers_present", "reason": reason})
    # the card must reuse the clickable person card (identity is the unit of trust), escJsAttr-guarded
    if "trade-peers" in content and "openPersonCard('${escJsAttr(" not in content:
        issues.append({"check": "trade_peers_present",
                       "reason": "trade-peers card must open the person card via escJsAttr-guarded openPersonCard (breakout-XSS guard)"})
    # migration side: DEFINER fn + member-authz gate + grant
    import glob as _glob
    mig = "\n".join(read_file(f) or "" for f in sorted(_glob.glob("supabase/migrations/*community_trade_peers*.sql")))
    if not mig:
        issues.append({"check": "trade_peers_present", "reason": "missing migration supabase/migrations/*community_trade_peers*.sql"})
    else:
        if "SECURITY DEFINER" not in mig:
            issues.append({"check": "trade_peers_present", "reason": "get_hive_trade_peers must be SECURITY DEFINER (skill_badges RLS is self-only)"})
        if "auth_uid = auth.uid()" not in mig:
            issues.append({"check": "trade_peers_present", "reason": "get_hive_trade_peers missing the active-member authz gate (auth_uid = auth.uid()) — fail-closed"})
        if "GRANT EXECUTE" not in mig:
            issues.append({"check": "trade_peers_present", "reason": "get_hive_trade_peers missing GRANT EXECUTE to anon/authenticated"})
    return issues


def check_community_xp_write_lockdown():
    """
    L3 — community_xp is written ONLY by SECURITY DEFINER code (increment_community_xp
    + the trg_community_post/reply/reaction_xp triggers, prosecdef=true). A client-role
    write policy (INSERT/UPDATE/DELETE/ALL granted to public/authenticated/anon) lets any
    logged-in user mint arbitrary Community XP — PROVEN exploitable 2026-07-11: a regular
    member set another member's xp_total to 999999. That tops the leaderboard AND, once the
    Community->Marketplace reputation bridge ships, spoofs the "Community-trusted" seller
    badge. The community skill's rule: "All XP is awarded by DB triggers, never from client
    JS." Live-DB assertion; SKIPs cleanly if the local DB is unreachable (e.g. CI without db).
    Fixed in 20260711000000_community_xp_write_lockdown.sql.
    """
    import subprocess
    issues = []
    sql = (
        "SELECT p.polname, p.polcmd, "
        "COALESCE((SELECT string_agg(CASE WHEN pr=0 THEN 'public' ELSE r.rolname END, ',') "
        "FROM unnest(p.polroles) AS pr LEFT JOIN pg_roles r ON r.oid=pr), '') "
        "FROM pg_policy p JOIN pg_class c ON c.oid=p.polrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' AND c.relname='community_xp' AND p.polcmd IN ('a','w','d','*');"
    )
    try:
        p = subprocess.run(
            ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres", "-tA", "-F", "\t", "-c", sql],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        )
        if p.returncode != 0:
            issues.append({"check": "community_xp_write_lockdown", "skip": True,
                           "reason": "local DB unreachable — skipped live community_xp policy assertion"})
            return issues
    except Exception:
        issues.append({"check": "community_xp_write_lockdown", "skip": True,
                       "reason": "docker/psql unavailable — skipped live community_xp policy assertion"})
        return issues

    CLIENT_ROLES = {"public", "authenticated", "anon"}
    for line in (l for l in p.stdout.splitlines() if l.strip()):
        parts = line.split("\t")
        polname = parts[0] if parts else "?"
        roles = set((parts[2] if len(parts) > 2 else "").split(","))
        if roles & CLIENT_ROLES:
            issues.append({
                "check": "community_xp_write_lockdown",
                "reason": (f"community_xp has a CLIENT-role write policy '{polname}' "
                           f"(roles: {','.join(sorted(roles & CLIENT_ROLES))}) — any logged-in user can "
                           f"mint arbitrary XP + spoof the Community-trusted badge. XP must be DEFINER-trigger-only.")
            })
    return issues


CHECK_NAMES = list(CHECKS.keys())
CHECK_LABELS = CHECKS


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold(f"\nCommunity Validator (8-layer, {len(CHECKS)} checks)"))
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
    all_issues += check_select_includes_optional_cols(content)
    all_issues += check_soft_delete_uses_undo(content)
    all_issues += check_mention_parser_wired(content)
    all_issues += check_badge_trigger_column_match()
    all_issues += check_supervisor_edit_additive(content)
    all_issues += check_community_xp_write_lockdown()
    all_issues += check_marketplace_bridge_present(content)
    all_issues += check_best_answer_authz(content)
    all_issues += check_nav_hub_activity_badge(content)
    all_issues += check_trade_peers_present(content)
    all_issues += check_ai_context_piisafe(content)

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
