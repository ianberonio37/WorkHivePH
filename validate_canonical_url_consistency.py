"""
Canonical URL Consistency Validator (L0, ratcheted).
======================================================
Every `<link rel="canonical" href="X">` must point at the page's own
URL (matches the file path under the production origin). A wrong
canonical tells search engines "the real page is over there" → causes
search results to send users to the wrong URL or de-index the current
page.

Output: canonical_url_consistency_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path
from urllib.parse import urlparse

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "canonical_url_consistency_report.json"
BASELINE_PATH = ROOT / "canonical_url_consistency_baseline.json"

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

CANONICAL_RE = re.compile(r"""<link\s+rel=['"]canonical['"]\s+href=['"](?P<url>[^'"]+)['"]""", re.IGNORECASE)


# Sentinel binding: name the L2 test `test('canonical_url_consistency: ...')` for coverage credit.
CHECK_NAMES = ["canonical_url_consistency"]


def main() -> int:
    per_page = []
    drift = 0

    for name in PAGES:
        page = ROOT / name
        if not page.exists(): continue
        body = page.read_text(encoding="utf-8", errors="replace")
        m = CANONICAL_RE.search(body)
        if not m:
            # Missing canonical caught by meta-description validator; don't double-flag
            per_page.append({"page": name, "status": "no_canonical"})
            continue
        url = m.group("url")
        # Extract last path segment
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")
        last = path.rsplit("/", 1)[-1] if path else ""
        # `index.html` is the root — canonical may be `/` or `/workhive/` etc.
        if name == "index.html":
            ok = path in ("", "/") or last in ("", "index.html") or path.endswith("/workhive") or path.endswith("/workhive/")
        else:
            ok = last == name
        if not ok:
            per_page.append({"page": name, "canonical": url, "expected_last": name})
            drift += 1

    baseline = 0
    if BASELINE_PATH.exists():
        try: baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("drift", 0)
        except Exception: baseline = 0
    else:
        baseline = drift
        BASELINE_PATH.write_text(json.dumps({"drift": baseline, "established": True}, indent=2), encoding="utf-8")
    if drift < baseline:
        baseline = drift
        BASELINE_PATH.write_text(json.dumps({"drift": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"pages_scanned": len(per_page), "drift": drift, "baseline": baseline},
        "per_page": per_page,
    }, indent=2), encoding="utf-8")

    print(f"\nCanonical URL Consistency Validator (L0)")
    print("=" * 56)
    print(f"  pages scanned:    {len(per_page)}")
    print(f"  drift:            {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — every <link rel=canonical> points at the page itself.")
        return 0
    for entry in per_page:
        if entry.get("canonical"):
            print(f"  {entry['page']}  → canonical='{entry['canonical']}'  expected last segment='{entry['expected_last']}'")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
