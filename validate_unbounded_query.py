"""
Unbounded Query Detection Validator (L0, ratcheted).
=====================================================
Every `db.from('table').select(...)` chain on a page should END WITH
one of:
  - .limit(N)
  - .single() / .maybeSingle()
  - { count: 'exact', head: true } (count-only query)
  - .range(low, high) (explicit pagination)
  - .eq('id', ID) on a primary-key column (intent is one row)

Without a limit, a page can fetch arbitrarily many rows. After data
grows, it OOMs the browser or freezes the UI.

Output: unbounded_query_report.json. Exit 1 on regression.
Allow with `// unbounded-query-allow: <reason>` near the call.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "unbounded_query_report.json"
BASELINE_PATH = ROOT / "unbounded_query_baseline.json"

PAGES = [
    "index.html", "hive.html", "logbook.html", "inventory.html",
    "pm-scheduler.html", "analytics.html", "analytics-report.html",
    "skillmatrix.html", "community.html", "public-feed.html",
    "marketplace.html", "marketplace-seller.html", "dayplanner.html",
    "engineering-design.html", "assistant.html", "report-sender.html",
    "platform-health.html", "project-manager.html", "integrations.html",
    "ph-intelligence.html", "project-report.html", "predictive.html",
    "ai-quality.html", "plant-connections.html", "achievements.html",
    "asset-hub.html", "shift-brain.html", "alert-hub.html",
    "audit-log.html", "voice-journal.html",
]

FROM_RE = re.compile(r"""\.from\(\s*['"`](?P<t>[a-z_][\w]*)['"`]\s*\)""")
ALLOW_RE = re.compile(r"unbounded-query-allow", re.IGNORECASE)
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")

# Markers that indicate the query is bounded.
# - explicit `.limit/.single/.maybeSingle/.range` are direct bounds
# - `head: true` count-only queries return no rows
# - hive/worker/asset scoping `.eq()` are soft bounds — limit to one tenant's
#   rows (typically <500)
# - `.insert/.update/.upsert/.delete` are WRITES, not reads — bounded by intent
SCOPING_COLS = (
    "id|hive_id|worker_name|auth_uid|user_id|asset_id|seller_name|"
    "project_id|pm_asset_id|scope_item_id|table|target_id|actor|name|tag|"
    "slug|feedback_id|listing_id|order_id|completion_id|post_id|topic_id|"
    "asset_node_id|parent_id|fault_id|kind|category"
)
BOUNDED_MARKERS = re.compile(
    r"""\.(?:limit|single|maybeSingle|range|insert|update|upsert|delete)\(|head:\s*true|"""
    r"""\.(?:eq|in)\(\s*['"`](?:""" + SCOPING_COLS + r""")['"`]"""
)


def main() -> int:
    per_page = []
    total_calls = 0
    total_unbounded = 0
    seen = set()

    files = [(n, ROOT / n) for n in PAGES]
    edge = ROOT / "supabase" / "functions"
    if edge.exists():
        for ts in sorted(edge.rglob("*.ts")):
            files.append((ts.relative_to(ROOT).as_posix(), ts))

    chain_end_re = re.compile(r"""\.from\(|;\s*\n|^\s*\}""", re.MULTILINE)

    for name, path in files:
        if not path.exists(): continue
        body = HTML_COMMENT_RE.sub("", path.read_text(encoding="utf-8", errors="replace"))
        issues = []
        for m in FROM_RE.finditer(body):
            total_calls += 1
            t = m.group("t")
            # Chain window: from .from() to the next chain-boundary
            search_window = body[m.end(): m.end() + 1200]
            cend = chain_end_re.search(search_window)
            tail = search_window[:cend.start()] if cend else search_window

            win = body[max(0, m.start() - 200):m.end() + 200]
            if ALLOW_RE.search(win): continue
            if BOUNDED_MARKERS.search(tail): continue

            key = (name, t, m.start())
            if key in seen: continue
            seen.add(key)
            issues.append({"table": t, "offset": m.start()})
        per_page.append({"file": name, "issues": issues})
        total_unbounded += len(issues)

    baseline = 0
    if BASELINE_PATH.exists():
        try: baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("unbounded", 0)
        except Exception: baseline = 0
    else:
        baseline = total_unbounded
        BASELINE_PATH.write_text(json.dumps({"unbounded": baseline, "established": True}, indent=2), encoding="utf-8")
    if total_unbounded < baseline:
        baseline = total_unbounded
        BASELINE_PATH.write_text(json.dumps({"unbounded": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"files_scanned": len(per_page), "total_calls": total_calls,
                    "total_unbounded": total_unbounded, "baseline": baseline},
        "per_file": per_page,
    }, indent=2), encoding="utf-8")

    print(f"\nUnbounded Query Detection Validator (L0)")
    print("=" * 56)
    print(f"  files scanned:    {len(per_page)}")
    print(f"  .from() calls:    {total_calls}")
    print(f"  unbounded:        {total_unbounded}  (baseline: {baseline})")
    if not total_unbounded:
        print("\n  PASS — every .from() chain has a bounded marker.")
        return 0
    shown = 0
    for entry in per_page:
        if not entry["issues"]: continue
        print(f"  {entry['file']}")
        for i in entry["issues"]:
            print(f"    → from('{i['table']}')...  (no .limit/.single/.range/.eq-on-id)")
            shown += 1
            if shown >= 20:
                print("    ... (more in report)")
                break
        if shown >= 20: break
    return 1 if total_unbounded > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
