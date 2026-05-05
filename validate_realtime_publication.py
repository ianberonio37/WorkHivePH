"""
Realtime Publication Coverage Validator — WorkHive Platform
============================================================
Catches the silent-failure bug where a postgres_changes subscription is
declared in HTML but the underlying table was never added to Supabase's
`supabase_realtime` publication.

Root cause of the May 2026 community page bug:
  feedChannel = db.channel(...).on('postgres_changes', { table: 'community_reactions', ... }, ...)
  But community_reactions was never published.
  → no errors, no warnings — listener compiles, page loads
  → optimistic UI on the originating client hides the gap
  → cross-client realtime simply doesn't fan out
  → discovered only when two windows are opened side by side

Approach:
  This validator can't introspect the Supabase publication directly (no DB
  access from CI). Instead it greps every postgres_changes subscription
  across all HTML files and compares the set against an explicit
  EXPECTED_PUBLISHED_TABLES allowlist that has to be kept in sync by hand.
  If a new table appears in a subscription without being added to the list,
  this validator FAILs with the exact SQL the developer must run.

  Layer 1 — Subscription coverage
    1.  Every table subscribed in HTML is in EXPECTED_PUBLISHED_TABLES  [FAIL]

Usage:  python validate_realtime_publication.py
Output: realtime_publication_report.json
"""
import re, json, sys, os, glob

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import format_result

# Tables explicitly added to supabase_realtime via:
#   ALTER PUBLICATION supabase_realtime ADD TABLE <name>;
# Verify the live state with:
#   SELECT tablename FROM pg_publication_tables WHERE pubname='supabase_realtime';
#
# IMPORTANT: this list is HAND-CURATED to reflect tables you have CONFIRMED are
# in the publication. The validator's job is to FAIL when a new subscription is
# added in HTML without the corresponding SQL having been run. Only add a table
# here AFTER you've run the diagnostic and verified it's in the publication.
#
# To grow this list correctly:
#   1. Run the diagnostic SQL.
#   2. For each subscribed table this validator FLAGS as missing, decide:
#      a. Add it to the publication (ALTER PUBLICATION ... ADD TABLE ...) AND
#         add it here, OR
#      b. Remove the dead subscription from HTML if realtime isn't needed.
EXPECTED_PUBLISHED_TABLES = {
    # Confirmed via diagnostic SQL on 2026-05-02:
    "community_posts",
    "community_replies",
    "community_reactions",
    "pm_completions",
    # Added to publication on 2026-05-02 after silent-realtime gaps were
    # discovered and the corresponding ALTER PUBLICATION statements ran:
    "assets",
    "inventory_items",
    "logbook",
    "marketplace_listings",
    # Added to publication on 2026-05-05 with the project_manager migration:
    "projects",
    "project_items",
    "project_progress_logs",
    # Phase 5 additions (Advanced features):
    "project_roles",
    "project_change_orders",
}

CHECKS = {
    "subscriptions_published": "L1  Every subscribed table is in supabase_realtime publication",
}
CHECK_LABELS = CHECKS
CHECK_NAMES  = list(CHECKS.keys())

# Test/dev/backup HTML files — their subscriptions don't need to be in the
# production publication. Pattern-match by filename suffix or substring.
EXCLUDED_FILE_PATTERNS = (
    "-test.html",
    ".backup.html",
    ".backup",
    "_backup.html",
)

# Match: postgres_changes subscriptions with a table name.
# Captures the table identifier from patterns like:
#   .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'community_posts', ... })
SUBSCRIPTION_RE = re.compile(
    r"on\(\s*['\"]postgres_changes['\"][^}]*?table\s*:\s*['\"]([a-zA-Z_][a-zA-Z0-9_]*)['\"]",
    re.DOTALL
)


def _is_excluded(path):
    name = os.path.basename(path).lower()
    return any(pat in name for pat in EXCLUDED_FILE_PATTERNS)


def collect_subscribed_tables():
    """Walk every production .html file in cwd, return {table_name: [(file, line), ...]}.
    Skips test, backup, and dev copies (filenames ending in -test.html, .backup.html, etc)."""
    found = {}
    for path in sorted(glob.glob("*.html")):
        if _is_excluded(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            continue
        for m in SUBSCRIPTION_RE.finditer(content):
            table = m.group(1)
            line  = content[:m.start()].count("\n") + 1
            found.setdefault(table, []).append((path, line))
    return found


def check_subscriptions_published(found):
    issues = []
    missing = sorted(t for t in found.keys() if t not in EXPECTED_PUBLISHED_TABLES)
    for table in missing:
        sites = found[table][:3]  # cap to first 3 to keep output readable
        site_str = "; ".join(f"{p}:{ln}" for p, ln in sites)
        sql = f"ALTER PUBLICATION supabase_realtime ADD TABLE {table};"
        issues.append({
            "check": "subscriptions_published",
            "reason": (
                f"'{table}' is subscribed via postgres_changes ({site_str}) "
                f"but is NOT in EXPECTED_PUBLISHED_TABLES. Either run "
                f"`{sql}` in the Supabase SQL Editor and add the table to "
                f"this validator's allowlist, or remove the subscription."
            )
        })
    return issues


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nRealtime Publication Coverage Validator (1-layer)"))
    print("=" * 55)

    found = collect_subscribed_tables()
    all_issues = check_subscriptions_published(found)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)
    total = len(CHECK_NAMES)

    if n_fail == 0:
        print(f"\033[92m\n  All {total} checks passed. ({len(found)} subscribed tables, all in publication)\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
        print(f"\n  Tip: verify live state with this SQL in Supabase:")
        print(f"    SELECT tablename FROM pg_publication_tables WHERE pubname='supabase_realtime';")

    report = {
        "validator":            "realtime_publication",
        "subscribed_tables":    sorted(found.keys()),
        "expected_published":   sorted(EXPECTED_PUBLISHED_TABLES),
        "total_checks":         total,
        "passed":               n_pass,
        "skipped":              n_skip,
        "failed":               n_fail,
        "issues":               [i for i in all_issues if not i.get("skip")],
    }
    with open("realtime_publication_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
