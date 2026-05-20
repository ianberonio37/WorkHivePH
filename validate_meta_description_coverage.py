"""
Meta Description Coverage Validator (L0, ratcheted).
======================================================
Every public page should have:
  - <meta name="description" content="...">
  - <meta property="og:title" content="...">
  - <meta property="og:image" content="...">
  - <link rel="canonical" href="...">

Missing these silently degrades SEO/AEO and social-share previews.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "meta_description_coverage_report.json"
BASELINE_PATH = ROOT / "meta_description_coverage_baseline.json"

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

CHECKS = [
    ("description", re.compile(r"""<meta\s+name=['"]description['"]\s+content=['"][^'"]+['"]""", re.IGNORECASE)),
    ("og:title",    re.compile(r"""<meta\s+property=['"]og:title['"]""", re.IGNORECASE)),
    ("og:image",    re.compile(r"""<meta\s+property=['"]og:image['"]""", re.IGNORECASE)),
    ("canonical",   re.compile(r"""<link\s+rel=['"]canonical['"]""", re.IGNORECASE)),
]


def main() -> int:
    per_page = []
    total_missing = 0
    for name in PAGES:
        page = ROOT / name
        if not page.exists(): continue
        body = page.read_text(encoding="utf-8", errors="replace")
        missing = []
        for label, pat in CHECKS:
            if not pat.search(body):
                missing.append(label)
        per_page.append({"page": name, "missing": missing})
        total_missing += len(missing)

    baseline = 0
    if BASELINE_PATH.exists():
        try: baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("missing", 0)
        except Exception: baseline = 0
    else:
        baseline = total_missing
        BASELINE_PATH.write_text(json.dumps({"missing": baseline, "established": True}, indent=2), encoding="utf-8")
    if total_missing < baseline:
        baseline = total_missing
        BASELINE_PATH.write_text(json.dumps({"missing": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"pages_scanned": len(per_page), "total_missing": total_missing, "baseline": baseline},
        "per_page": per_page,
    }, indent=2), encoding="utf-8")

    print(f"\nMeta Description Coverage Validator (L0)")
    print("=" * 56)
    print(f"  pages scanned:    {len(per_page)}")
    print(f"  missing tags:     {total_missing}  (baseline: {baseline})")
    if not total_missing:
        print("\n  PASS — every page has description + og:title + og:image + canonical.")
        return 0
    shown = 0
    for entry in per_page:
        if not entry["missing"]: continue
        print(f"  {entry['page']}  missing: {', '.join(entry['missing'])}")
        shown += 1
        if shown >= 30: break
    return 1 if total_missing > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
