"""
Heading Hierarchy Validator (L0, ratcheted).
==============================================
Pages should descend through heading levels without skipping
(h1 → h2 → h3, never h1 → h3). Screen readers and SEO crawlers
parse heading structure to build a document outline; skipped
levels confuse both.

Detection
  Walk each page's heading sequence in document order. Flag any
  level jump > 1 (e.g. h1 then h3). Multiple h1 also flagged (most
  pages should have exactly one).

Output: heading_hierarchy_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "heading_hierarchy_report.json"
BASELINE_PATH = ROOT / "heading_hierarchy_baseline.json"

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

HEADING_RE = re.compile(r"""<h([1-6])\b[^>]*>""", re.IGNORECASE)
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
# A `<!-- heading-allow: <reason> -->` within 200 chars BEFORE a heading
# tag exempts that heading from both multiple_h1 and skip detection.
# Useful for popup/PDF templates that emit a separate document's h1.
ALLOW_RE = re.compile(r"heading-allow", re.IGNORECASE)


# Sentinel binding: name the L2 test `test('heading_hierarchy: ...')` for coverage credit.
CHECK_NAMES = ["heading_hierarchy"]


def main() -> int:
    per_page = []
    total_issues = 0
    for name in PAGES:
        page = ROOT / name
        if not page.exists(): continue
        raw  = page.read_text(encoding="utf-8", errors="replace")
        body = HTML_COMMENT_RE.sub(lambda m: " " * len(m.group(0)), raw)  # preserve offsets
        levels = []
        for m in HEADING_RE.finditer(body):
            # Check the RAW source (before comment strip) for the allow marker
            # within 300 chars before the heading.
            window = raw[max(0, m.start()-300): m.start()]
            if ALLOW_RE.search(window):
                continue
            levels.append(int(m.group(1)))
        issues = []
        # Multiple h1
        h1_count = sum(1 for l in levels if l == 1)
        if h1_count > 1:
            issues.append({"kind": "multiple_h1", "count": h1_count})
        # Level jumps > 1
        prev = 0
        for i, lvl in enumerate(levels):
            if prev > 0 and lvl > prev + 1:
                issues.append({"kind": "skip", "from": prev, "to": lvl, "idx": i})
            prev = lvl
        per_page.append({"page": name, "levels": levels, "issues": issues})
        total_issues += len(issues)

    baseline = 0
    if BASELINE_PATH.exists():
        try: baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("issues", 0)
        except Exception: baseline = 0
    else:
        baseline = total_issues
        BASELINE_PATH.write_text(json.dumps({"issues": baseline, "established": True}, indent=2), encoding="utf-8")
    if total_issues < baseline:
        baseline = total_issues
        BASELINE_PATH.write_text(json.dumps({"issues": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"pages_scanned": len(per_page), "total_issues": total_issues, "baseline": baseline},
        "per_page": per_page,
    }, indent=2), encoding="utf-8")

    print(f"\nHeading Hierarchy Validator (L0)")
    print("=" * 56)
    print(f"  pages scanned:    {len(per_page)}")
    print(f"  hierarchy issues: {total_issues}  (baseline: {baseline})")
    if not total_issues:
        print("\n  PASS — every page has a clean heading hierarchy.")
        return 0
    shown = 0
    for entry in per_page:
        if not entry["issues"]: continue
        sample = []
        for i in entry["issues"][:3]:
            if i["kind"] == "multiple_h1": sample.append(f"{i['count']}× h1")
            else: sample.append(f"h{i['from']}→h{i['to']}")
        print(f"  {entry['page']}  {', '.join(sample)}")
        shown += 1
        if shown >= 25: break
    return 1 if total_issues > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
