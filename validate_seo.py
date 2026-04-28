"""
SEO and Page Metadata Validator — WorkHive Platform
====================================================
SEO affects every potential customer finding WorkHive through search.
Bad metadata means: app pages indexed instead of the landing page,
social links sharing a blank card, Google not knowing what the site does.

  Layer 1 — Indexing control
    1.  App pages have noindex        — internal pages must not appear in search results

  Layer 2 — Page identity
    2.  Descriptive title tags        — every page has a WorkHive-branded title
    3.  Canonical tags on all pages   — prevents duplicate content across staging/prod URLs

  Layer 3 — Discovery metadata
    4.  Meta descriptions             — required for search snippets and share cards

  Layer 4 — Social sharing
    5.  Complete OG tag set           — index.html has og:title/description/image/url

  Layer 5 — Structured data
    6.  JSON-LD on landing page       — SoftwareApplication schema for Google rich results

Usage:  python validate_seo.py
Output: seo_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

LANDING_PAGE = "index.html"

APP_PAGES = [
    "logbook.html",
    "inventory.html",
    "pm-scheduler.html",
    "hive.html",
    "assistant.html",
    "skillmatrix.html",
    "dayplanner.html",
    "engineering-design.html",
    "platform-health.html",
]

ALL_PAGES      = [LANDING_PAGE] + APP_PAGES
MIN_TITLE_LEN  = 15
REQUIRED_OG    = ["og:title", "og:description", "og:image", "og:url"]


# ── Layer 1: Indexing control ─────────────────────────────────────────────────

def check_noindex(pages):
    """Every internal app page must declare noindex — without it, Google indexes
    logbook.html, hive.html etc., splitting SEO equity away from the landing page."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        has = re.search(r'<meta[^>]+name=["\']robots["\'][^>]*content=["\'][^"\']*noindex', content, re.IGNORECASE) or \
              re.search(r'<meta[^>]+content=["\'][^"\']*noindex[^"\']*["\'][^>]*name=["\']robots["\']', content, re.IGNORECASE)
        if not has:
            issues.append({"check": "noindex", "page": page,
                           "reason": (f"{page} missing <meta name=\"robots\" content=\"noindex, follow\"> "
                                      f"— search engines will index this app page instead of the landing page")})
    return issues


# ── Layer 2: Page identity ────────────────────────────────────────────────────

def check_title_tags(pages):
    """Every page must have a descriptive <title> containing 'WorkHive'."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        m = re.search(r"<title>([^<]*)</title>", content, re.IGNORECASE)
        if not m:
            issues.append({"check": "title_tags", "page": page,
                           "reason": f"{page} is missing a <title> tag"})
            continue
        title = m.group(1).strip()
        if len(title) < MIN_TITLE_LEN:
            issues.append({"check": "title_tags", "page": page,
                           "reason": (f"{page} title too short ({len(title)} chars): '{title}' "
                                      f"— not descriptive enough for search results or browser tabs")})
        elif "workhive" not in title.lower():
            issues.append({"check": "title_tags", "page": page,
                           "reason": (f"{page} title missing 'WorkHive': '{title}' "
                                      f"— brand name must appear in every page title")})
        elif "—" in title or " -- " in title:
            issues.append({"check": "title_tags", "page": page,
                           "reason": (f"{page} title uses em dash: '{title}' "
                                      f"— use 'Page Name | WorkHive' pipe format instead")})
    return issues


def check_canonical_tags(pages):
    """
    Every page must have <link rel="canonical" href="https://workhiveph.com/page.html">.
    Without canonical tags, Google treats staging and production as duplicate content
    and may index the wrong version, or split link equity between URLs. App pages
    missing canonical tags also make it harder to track canonical indexing in
    Google Search Console.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        if not re.search(r'<link[^>]+rel=["\']canonical["\']', content, re.IGNORECASE):
            issues.append({"check": "canonical_tags", "page": page,
                           "reason": (f"{page} missing <link rel=\"canonical\" href=\"...\"> "
                                      f"— Google may index staging URLs or split link equity "
                                      f"across duplicate content; add canonical pointing to "
                                      f"https://workhiveph.com/{page}")})
    return issues


# ── Layer 3: Discovery metadata ───────────────────────────────────────────────

def check_meta_descriptions(pages):
    """Every live page must have a meta description for search snippets and
    social share card text."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        has = re.search(r'<meta[^>]+name=["\']description["\'][^>]*content=["\'][^"\']{10,}', content, re.IGNORECASE) or \
              re.search(r'<meta[^>]+content=["\'][^"\']{10,}["\'][^>]*name=["\']description["\']', content, re.IGNORECASE)
        if not has:
            issues.append({"check": "meta_descriptions", "page": page,
                           "reason": (f"{page} missing <meta name=\"description\" content=\"...\"> "
                                      f"— search results and social share cards will show a blank or "
                                      f"auto-generated description")})
    return issues


# ── Layer 4: Social sharing ───────────────────────────────────────────────────

def check_og_tags(page):
    """index.html must have complete Open Graph tags so LinkedIn, WhatsApp, and
    Facebook sharing produces a rich card with title, description, and image."""
    issues = []
    content = read_file(page)
    if content is None:
        return [{"check": "og_tags", "page": page, "reason": f"{page} not found"}]
    for prop in REQUIRED_OG:
        if not re.search(rf'<meta[^>]+property=["\'][^"\']*{re.escape(prop)}["\']', content, re.IGNORECASE):
            issues.append({"check": "og_tags", "page": page,
                           "reason": (f"{page} missing Open Graph tag '{prop}' "
                                      f"— social share cards will be incomplete or broken")})
    return issues


# ── Layer 5: Structured data ──────────────────────────────────────────────────

def check_structured_data(page):
    """
    index.html must have JSON-LD structured data with @type SoftwareApplication
    (or Organization). Structured data enables Google rich results, AI-generated
    summaries, and appears in knowledge graph panels when someone searches for
    WorkHive. A missing JSON-LD block is invisible to regular testing but quietly
    removes WorkHive from Google's structured results.
    """
    content = read_file(page)
    if content is None:
        return [{"check": "structured_data", "page": page, "reason": f"{page} not found"}]
    if 'application/ld+json' not in content:
        return [{"check": "structured_data", "page": page,
                 "reason": (f"{page} has no <script type=\"application/ld+json\"> block — "
                             f"missing structured data means WorkHive won't appear in "
                             f"Google rich results, knowledge panels, or AI-generated summaries")}]
    if not re.search(r'"@type"\s*:\s*"(?:SoftwareApplication|Organization|WebSite)"', content):
        return [{"check": "structured_data", "page": page,
                 "reason": (f"{page} JSON-LD block missing recognised @type "
                             f"(SoftwareApplication, Organization, or WebSite) — "
                             f"Google won't extract structured data without a known type")}]
    return []


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "noindex",
    "title_tags",
    "canonical_tags",
    "meta_descriptions",
    "og_tags",
    "structured_data",
]

CHECK_LABELS = {
    "noindex":          "L1  App pages have <meta name=robots content=noindex>",
    "title_tags":       "L2  All pages have a descriptive WorkHive title tag",
    "canonical_tags":   "L2  All pages have <link rel=canonical>",
    "meta_descriptions":"L3  All pages have <meta name=description>",
    "og_tags":          "L4  index.html has complete Open Graph tag set",
    "structured_data":  "L5  index.html has JSON-LD structured data (SoftwareApplication)",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nSEO and Page Metadata Validator (5-layer)"))
    print("=" * 55)

    all_issues = []
    all_issues += check_noindex(APP_PAGES)
    all_issues += check_title_tags(ALL_PAGES)
    all_issues += check_canonical_tags(ALL_PAGES)
    all_issues += check_meta_descriptions(ALL_PAGES)
    all_issues += check_og_tags(LANDING_PAGE)
    all_issues += check_structured_data(LANDING_PAGE)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "seo",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("seo_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
