"""
Sitemap Sync Validator — WorkHive Platform
===========================================
Keeps sitemap.xml in lockstep with the actual filesystem. When a /learn/
article is added but sitemap forgotten, Google never indexes it. When a
page is deleted but sitemap not updated, Google sees a stale URL and
serves 404s.

Layer 1: Every <loc> in sitemap.xml resolves to an actual file on disk
         (resolve /learn/foo/ -> learn/foo/index.html)
Layer 2: Every public-facing HTML file is referenced in sitemap.xml
         (catches the "forgot to add to sitemap" case)
Layer 3: The sitemap declares lastmod, changefreq, priority for every URL
         (Google ranking-signal hygiene)

Usage:  python validate_sitemap_sync.py
Output: sitemap_sync_report.json
"""
import re, json, sys, os
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from validator_utils import read_file, format_result

SITEMAP_PATH = "sitemap.xml"
SITE_PREFIX  = "https://workhiveph.com"

# Public files that should appear in sitemap.xml (sans the site prefix).
# Auto-derived to avoid drift: index, all /learn/, all stubs, the learn hub.
EXPECTED_SITEMAP_URLS = [
    "/",
    "/learn/",
    "/about/",
    "/privacy-policy/",
    "/terms-of-service/",
] + [f"/learn/{slug}/" for slug in [
    "start-digital-logbook-philippine-factory",
    "what-is-oee-how-to-calculate",
    "mtbf-vs-mttr-for-supervisors",
    "maintenance-shift-handover-template",
    "spare-parts-inventory-philippine-plants",
    "free-pm-checklist-templates",
    "skill-matrix-for-maintenance-technicians",
    "dilo-wilo-day-planner-supervisors",
    "free-engineering-calculators-philippine-plants",
    "ai-work-assistant-maintenance-technicians",
    "predictive-maintenance-on-a-budget-philippines",
    "connecting-workhive-to-sap-maximo-cmms",
    "voice-to-text-maintenance-philippine-plant-floor",
    "building-asset-register-zero-budget",
    "maintenance-project-planning-template",
    "joining-and-growing-your-hive",
    "industrial-community-of-practice-philippines",
    "gamifying-maintenance-for-engagement",
    "industrial-marketplace-philippine-specialists",
    "predictive-alert-thresholds-plants",
    "dole-iso-audit-trail-from-logbook",
    "ai-quality-and-roi-stage-2-plants",
    "sensor-cmms-gateway-operations",
    "ph-industrial-benchmarks-intelligence",
]]

LOC_RE        = re.compile(r"<loc>([^<]+)</loc>", re.IGNORECASE)
LASTMOD_RE    = re.compile(r"<lastmod>([^<]+)</lastmod>", re.IGNORECASE)
CHANGEFREQ_RE = re.compile(r"<changefreq>([^<]+)</changefreq>", re.IGNORECASE)
PRIORITY_RE   = re.compile(r"<priority>([^<]+)</priority>", re.IGNORECASE)
URL_BLOCK_RE  = re.compile(r"<url>(.*?)</url>", re.DOTALL | re.IGNORECASE)


def _url_to_file_path(url: str) -> str:
    """Convert a sitemap URL to a relative on-disk path.
       https://workhiveph.com/        -> index.html
       https://workhiveph.com/learn/  -> learn/index.html
       https://workhiveph.com/learn/foo/ -> learn/foo/index.html
       https://workhiveph.com/foo.html  -> foo.html"""
    path = url.replace(SITE_PREFIX, "").lstrip("/")
    if not path:
        return "index.html"
    if path.endswith("/"):
        return path + "index.html"
    return path


def _parse_sitemap():
    content = read_file(SITEMAP_PATH)
    if content is None:
        return None, []
    return content, LOC_RE.findall(content)


def check_loc_resolves():
    """Every <loc> in sitemap must point to a real file on disk."""
    issues = []
    content, locs = _parse_sitemap()
    if content is None:
        return [{"check": "loc_resolves", "page": SITEMAP_PATH,
                 "reason": "sitemap.xml not found"}]
    for url in locs:
        rel = _url_to_file_path(url.strip())
        if not os.path.isfile(rel):
            issues.append({"check": "loc_resolves", "page": SITEMAP_PATH,
                           "reason": (f"<loc>{url}</loc> resolves to "
                                      f"{rel} but that file doesn't exist. "
                                      f"Google will get a 404 when it crawls "
                                      f"this URL. Either restore the file or "
                                      f"remove this entry from sitemap.xml.")})
    return issues


def check_expected_urls_present():
    """Every expected public URL must have an entry in sitemap.xml."""
    issues = []
    content, locs = _parse_sitemap()
    if content is None:
        return []   # already flagged by check_loc_resolves
    have = {url.replace(SITE_PREFIX, "") or "/" for url in locs}
    for expected in EXPECTED_SITEMAP_URLS:
        if expected not in have:
            full_url = f"{SITE_PREFIX}{expected}"
            issues.append({"check": "expected_urls_present",
                           "page": SITEMAP_PATH,
                           "reason": (f"sitemap.xml missing <url><loc>"
                                      f"{full_url}</loc></url>. Google "
                                      f"won't crawl this page on the next "
                                      f"sitemap refresh. Add the entry "
                                      f"with lastmod, changefreq, and "
                                      f"priority.")})
    return issues


def check_metadata_complete():
    """Every <url> block in sitemap must declare lastmod + changefreq + priority."""
    issues = []
    content, locs = _parse_sitemap()
    if content is None:
        return []
    blocks = URL_BLOCK_RE.findall(content)
    for block in blocks:
        loc_m = LOC_RE.search(block)
        url   = loc_m.group(1).strip() if loc_m else "(unknown)"
        missing = []
        if not LASTMOD_RE.search(block):
            missing.append("lastmod")
        if not CHANGEFREQ_RE.search(block):
            missing.append("changefreq")
        if not PRIORITY_RE.search(block):
            missing.append("priority")
        if missing:
            issues.append({"check": "metadata_complete", "page": SITEMAP_PATH,
                           "reason": (f"<url> block for {url} missing: "
                                      f"{', '.join(missing)}. Google ranking "
                                      f"signal degraded without these.")})
    return issues


CHECK_NAMES  = ["loc_resolves", "expected_urls_present", "metadata_complete"]
CHECK_LABELS = {
    "loc_resolves":          "L1  Every <loc> in sitemap.xml resolves to an existing file",
    "expected_urls_present": "L2  Every expected public URL has a sitemap.xml entry",
    "metadata_complete":     "L3  Every <url> block has lastmod + changefreq + priority",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nSitemap Sync Validator (3-layer)"))
    print("=" * 55)

    all_issues = []
    all_issues += check_loc_resolves()
    all_issues += check_expected_urls_present()
    all_issues += check_metadata_complete()

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    _, locs = _parse_sitemap()
    print(f"\n  sitemap.xml lists {len(locs)} URL(s); expected {len(EXPECTED_SITEMAP_URLS)}.")
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m  All {len(CHECK_NAMES)} checks passed.\033[0m")
    else:
        color = "91" if n_fail else "93"
        print(f"\033[{color}m  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "sitemap_sync",
        "total_checks": len(CHECK_NAMES),
        "sitemap_urls": len(locs),
        "expected_urls": len(EXPECTED_SITEMAP_URLS),
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("sitemap_sync_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
