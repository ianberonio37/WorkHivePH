"""
Feedback Widget Validator — WorkHive Platform
==============================================
Enforces the universal feedback contract from migration
20260519000002_platform_feedback.sql and wh-feedback-fab.js:

  Layer 1 — Script wiring
    1.  widget_renders         — every public + app page reaches wh-feedback-fab.js
                                  (either via nav-hub.js auto-include or a direct
                                  <script src="...wh-feedback-fab.js"> tag).
    2.  widget_submits         — wh-feedback-fab.js POSTs to /rest/v1/platform_feedback

  Layer 2 — Form integrity
    3.  widget_rating          — the script declares rating logic gated on kind=review
    4.  widget_rate_limit      — the script handles the 23P01 rate-limit response code

  Layer 3 — Schema-side enforcement
    5.  schema_rls_enabled     — platform_feedback migration enables RLS
    6.  schema_rate_limit_trigger — rate-limit trigger present in migration
    7.  schema_resolved_at_trigger — resolved_at auto-stamp trigger present

Usage:  python validate_feedback_widget.py
Output: feedback_widget_report.json

Skills consulted: security (RLS + rate-limit), notifications (Realtime
contract honored by admin inbox), platform-guardian (sentinel-bindable
check names matching the Playwright spec tests/feedback.spec.ts).
"""
from __future__ import annotations

import os, re, json, sys
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

ROOT = Path(__file__).resolve().parent
WIDGET_FILE   = ROOT / "wh-feedback-fab.js"
NAV_HUB_FILE  = ROOT / "nav-hub.js"
MIGRATION     = ROOT / "supabase" / "migrations" / "20260519000002_platform_feedback.sql"
VOTES_MIGRATION = ROOT / "supabase" / "migrations" / "20260519000003_platform_feedback_votes.sql"
ROADMAP_PAGE  = ROOT / "feedback" / "index.html"
FOUNDER_PAGE  = ROOT / "founder-console.html"

# Public pages that don't load nav-hub.js — they must reference the FAB
# script directly. The 36 /learn/<slug>/ articles are also in scope but
# enumerated via glob to auto-include new articles as they ship.
PUBLIC_LEAF_PAGES = [
    "about/index.html",
    "privacy-policy/index.html",
    "terms-of-service/index.html",
    "learn/index.html",
]

CHECK_NAMES = [
    "widget_renders",
    "widget_submits",
    "widget_rating",
    "widget_rate_limit",
    "schema_rls_enabled",
    "schema_rate_limit_trigger",
    "schema_resolved_at_trigger",
    # Phase 2 — public roadmap + upvoting
    "roadmap_page_exists",
    "roadmap_uses_toggle_rpc",
    "schema_votes_table",
    "schema_toggle_rpc",
    "founder_console_publish_toggle",
]
CHECK_LABELS = {
    "widget_renders":            "L1  FAB script reachable from every public + app page",
    "widget_submits":            "L1  Widget POSTs to /rest/v1/platform_feedback",
    "widget_rating":             "L2  Rating block gated on kind=review",
    "widget_rate_limit":         "L2  23P01 rate-limit code handled with friendly message",
    "schema_rls_enabled":        "L3  platform_feedback RLS enabled in migration",
    "schema_rate_limit_trigger": "L3  Rate-limit trigger declared in migration",
    "schema_resolved_at_trigger":"L3  resolved_at auto-stamp trigger declared in migration",
    "roadmap_page_exists":       "L4  /feedback/index.html public roadmap page exists",
    "roadmap_uses_toggle_rpc":   "L4  Roadmap page calls toggle_feedback_upvote RPC",
    "schema_votes_table":        "L4  platform_feedback_votes table declared in migration",
    "schema_toggle_rpc":         "L4  toggle_feedback_upvote RPC declared in migration",
    "founder_console_publish_toggle": "L4  Founder Console drawer has 'Make public' toggle",
}


def check_widget_renders():
    """Every public + app page either loads nav-hub.js (which lazy-loads
    the FAB) OR includes wh-feedback-fab.js directly."""
    issues = []
    nav_hub_src = read_file(str(NAV_HUB_FILE)) or ""
    if "wh-feedback-fab.js" not in nav_hub_src:
        issues.append({
            "check": "widget_renders",
            "page":  "nav-hub.js",
            "reason": "nav-hub.js does not lazy-load wh-feedback-fab.js. Every "
                      "page that loads nav-hub.js depends on this to mount the "
                      "feedback FAB. Restore the createElement('script') block.",
        })

    pages = list(PUBLIC_LEAF_PAGES)
    # Add every learn article (glob auto-extends as new ones ship)
    for art in sorted((ROOT / "learn").glob("*/index.html")):
        rel = art.relative_to(ROOT).as_posix()
        if rel != "learn/index.html":
            pages.append(rel)

    for page in pages:
        src = read_file(str(ROOT / page)) or ""
        if not src:
            continue
        has_direct  = "wh-feedback-fab.js" in src
        has_navhub  = "nav-hub.js" in src
        if not (has_direct or has_navhub):
            issues.append({
                "check":  "widget_renders",
                "page":   page,
                "reason": f"{page} loads neither nav-hub.js (which lazy-loads the "
                          f"FAB) nor wh-feedback-fab.js directly. Users on this "
                          f"page have no way to send feedback. Add "
                          f"<script defer src=\"/workhive/wh-feedback-fab.js\"></script> "
                          f"before </body>.",
            })
    return issues


def check_widget_submits():
    """wh-feedback-fab.js must POST to /rest/v1/platform_feedback. Accepts
    either a literal URL or a template literal built from a TABLE constant."""
    issues = []
    src = read_file(str(WIDGET_FILE)) or ""

    # Direct literal OR a template wired to a TABLE = 'platform_feedback' constant
    has_literal = "/rest/v1/platform_feedback" in src
    has_table_const = bool(re.search(
        r"""(?:const|let|var)\s+TABLE\s*=\s*['"`]platform_feedback['"`]""", src
    ))
    has_rest_template = "/rest/v1/${TABLE}" in src or "/rest/v1/${ TABLE }" in src

    if not (has_literal or (has_table_const and has_rest_template)):
        issues.append({
            "check":  "widget_submits",
            "page":   "wh-feedback-fab.js",
            "reason": "wh-feedback-fab.js does not target /rest/v1/platform_feedback. "
                      "Schema (migration 20260519000002) is wired but the widget "
                      "cannot reach it. Either use the literal URL or set "
                      "const TABLE = 'platform_feedback' + fetch('${SUPABASE_URL}/rest/v1/${TABLE}').",
        })
    if "method: 'POST'" not in src and 'method: "POST"' not in src:
        issues.append({
            "check":  "widget_submits",
            "page":   "wh-feedback-fab.js",
            "reason": "wh-feedback-fab.js fetch call missing method: 'POST'.",
        })
    return issues


def check_widget_rating():
    """The widget should only show the rating block when kind=review."""
    src = read_file(str(WIDGET_FILE)) or ""
    if "wh-fb-rating-block" not in src:
        return [{
            "check":  "widget_rating",
            "page":   "wh-feedback-fab.js",
            "reason": "wh-fb-rating-block element missing from the widget. Reviews "
                      "cannot collect a 1-5 star rating.",
        }]
    # Rating must be conditionally displayed based on kind === 'review'
    # (selectKind toggles display style); not a regex perfectionism, just
    # confirm the linkage exists in source.
    if "review" not in src or "selectKind" not in src:
        return [{
            "check":  "widget_rating",
            "page":   "wh-feedback-fab.js",
            "reason": "Rating-block visibility not gated on kind === 'review' in selectKind().",
        }]
    return []


def check_widget_rate_limit():
    """The widget must surface a friendly message when the DB trigger
    raises 23P01 (exclusion_violation) for rate limiting."""
    src = read_file(str(WIDGET_FILE)) or ""
    if "23P01" not in src:
        return [{
            "check":  "widget_rate_limit",
            "page":   "wh-feedback-fab.js",
            "reason": "Widget does not branch on PostgREST error code 23P01. "
                      "Users hitting the 5/hour limit will see a generic "
                      "'could not send' message instead of a friendly retry.",
        }]
    return []


def check_schema_rls_enabled():
    """Migration must enable RLS on platform_feedback."""
    src = read_file(str(MIGRATION)) or ""
    if "ENABLE ROW LEVEL SECURITY" not in src.upper():
        return [{
            "check":  "schema_rls_enabled",
            "page":   str(MIGRATION.relative_to(ROOT)),
            "reason": "platform_feedback migration does not ENABLE ROW LEVEL SECURITY. "
                      "Without RLS, anon clients can read everyone's submissions.",
        }]
    return []


def check_schema_rate_limit_trigger():
    """The rate-limit trigger function + trigger must exist in the migration."""
    src = read_file(str(MIGRATION)) or ""
    issues = []
    if "check_platform_feedback_rate_limit" not in src:
        issues.append({
            "check":  "schema_rate_limit_trigger",
            "page":   str(MIGRATION.relative_to(ROOT)),
            "reason": "check_platform_feedback_rate_limit() function missing from migration. "
                      "Rate limit is the only spam guard.",
        })
    if "trg_platform_feedback_rate_limit" not in src:
        issues.append({
            "check":  "schema_rate_limit_trigger",
            "page":   str(MIGRATION.relative_to(ROOT)),
            "reason": "trg_platform_feedback_rate_limit trigger missing from migration. "
                      "Function exists but isn't wired to BEFORE INSERT.",
        })
    return issues


def check_schema_resolved_at_trigger():
    """The resolved_at auto-stamp trigger function + trigger must exist."""
    src = read_file(str(MIGRATION)) or ""
    issues = []
    if "platform_feedback_stamp_resolved" not in src:
        issues.append({
            "check":  "schema_resolved_at_trigger",
            "page":   str(MIGRATION.relative_to(ROOT)),
            "reason": "platform_feedback_stamp_resolved() function missing. "
                      "Admin inbox cannot show 'resolved 3d ago' without it.",
        })
    if "trg_platform_feedback_stamp_resolved" not in src:
        issues.append({
            "check":  "schema_resolved_at_trigger",
            "page":   str(MIGRATION.relative_to(ROOT)),
            "reason": "trg_platform_feedback_stamp_resolved trigger missing — function exists but "
                      "isn't wired to BEFORE UPDATE OF status.",
        })
    return issues


def check_roadmap_page_exists():
    """Public /feedback/index.html roadmap page must exist."""
    if not ROADMAP_PAGE.exists():
        return [{
            "check":  "roadmap_page_exists",
            "page":   str(ROADMAP_PAGE.relative_to(ROOT)),
            "reason": "Public roadmap page missing. Visitors have no place to vote on or browse public submissions.",
        }]
    return []


def check_roadmap_uses_toggle_rpc():
    """Roadmap page must call the toggle_feedback_upvote RPC for voting."""
    if not ROADMAP_PAGE.exists():
        return []   # already flagged by roadmap_page_exists
    src = read_file(str(ROADMAP_PAGE)) or ""
    if "toggle_feedback_upvote" not in src:
        return [{
            "check":  "roadmap_uses_toggle_rpc",
            "page":   str(ROADMAP_PAGE.relative_to(ROOT)),
            "reason": "Roadmap page does not call toggle_feedback_upvote RPC. Voting must go through "
                      "the RPC (not direct upvotes UPDATEs) so the (feedback_id, voter_token) PK "
                      "blocks double-voting + the is_public guard runs server-side.",
        }]
    return []


def check_schema_votes_table():
    """Votes migration must declare platform_feedback_votes with the composite PK."""
    if not VOTES_MIGRATION.exists():
        return [{
            "check":  "schema_votes_table",
            "page":   str(VOTES_MIGRATION.relative_to(ROOT)),
            "reason": "Phase 2 migration 20260519000003_platform_feedback_votes.sql missing. "
                      "Without the votes table, double-voting is unblocked.",
        }]
    src = read_file(str(VOTES_MIGRATION)) or ""
    if "platform_feedback_votes" not in src:
        return [{
            "check":  "schema_votes_table",
            "page":   str(VOTES_MIGRATION.relative_to(ROOT)),
            "reason": "platform_feedback_votes table missing from Phase 2 migration.",
        }]
    if "PRIMARY KEY (feedback_id, voter_token)" not in src:
        return [{
            "check":  "schema_votes_table",
            "page":   str(VOTES_MIGRATION.relative_to(ROOT)),
            "reason": "platform_feedback_votes missing the composite (feedback_id, voter_token) "
                      "primary key. Without it, double-voting is unblocked.",
        }]
    return []


def check_schema_toggle_rpc():
    """toggle_feedback_upvote RPC must be declared in the votes migration."""
    if not VOTES_MIGRATION.exists():
        return []
    src = read_file(str(VOTES_MIGRATION)) or ""
    issues = []
    if "FUNCTION public.toggle_feedback_upvote" not in src:
        issues.append({
            "check":  "schema_toggle_rpc",
            "page":   str(VOTES_MIGRATION.relative_to(ROOT)),
            "reason": "toggle_feedback_upvote RPC function missing from Phase 2 migration.",
        })
    if "is_public" not in src or "RAISE EXCEPTION" not in src:
        issues.append({
            "check":  "schema_toggle_rpc",
            "page":   str(VOTES_MIGRATION.relative_to(ROOT)),
            "reason": "RPC does not enforce 'item must be public' guard. Without it, visitors could "
                      "vote on private items the admin hasn't approved.",
        })
    return issues


def check_founder_console_publish_toggle():
    """Founder Console drawer must expose the 'Make public' checkbox so admin can promote items."""
    src = read_file(str(FOUNDER_PAGE)) or ""
    if "fb-d-public" not in src or "is_public" not in src:
        return [{
            "check":  "founder_console_publish_toggle",
            "page":   str(FOUNDER_PAGE.relative_to(ROOT)),
            "reason": "Drawer missing 'Make public' checkbox (#fb-d-public). Admin has no way to "
                      "promote a submission to the public /feedback/ roadmap.",
        }]
    return []


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold(f"\nFeedback Widget Validator ({len(CHECK_NAMES)} checks)"))
    print("=" * 55)

    all_issues = []
    all_issues += check_widget_renders()
    all_issues += check_widget_submits()
    all_issues += check_widget_rating()
    all_issues += check_widget_rate_limit()
    all_issues += check_schema_rls_enabled()
    all_issues += check_schema_rate_limit_trigger()
    all_issues += check_schema_resolved_at_trigger()
    all_issues += check_roadmap_page_exists()
    all_issues += check_roadmap_uses_toggle_rpc()
    all_issues += check_schema_votes_table()
    all_issues += check_schema_toggle_rpc()
    all_issues += check_founder_console_publish_toggle()

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {len(CHECK_NAMES)} checks passed.\033[0m")
    else:
        color = "91" if n_fail else "93"
        print(f"\033[{color}m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "feedback_widget",
        "total_checks": len(CHECK_NAMES),
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("feedback_widget_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
