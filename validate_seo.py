"""
SEO and Page Metadata Validator — WorkHive Platform
====================================================
SEO affects every potential customer finding WorkHive through search.
Bad metadata means: app pages indexed instead of the landing page,
social links sharing a blank card, Google not knowing what the site does.

This validator enforces the rules from the SEO/Content skill file.

Four things checked:

  1. App pages have noindex             — every internal app page must tell
                                         search engines not to index it.
                                         Without it, Google indexes logbook.html,
                                         inventory.html etc. instead of the landing
                                         page, splitting SEO value and confusing
                                         workers who find tool pages via search.

  2. All live pages have a title tag    — every page must have a unique,
                                         descriptive <title> containing the WorkHive
                                         brand name. Empty or bare titles appear as
                                         "Untitled" in browser tabs and search results.

  3. All live pages have meta description — required for social sharing previews,
                                         Google rich results, and AI summaries.
                                         Missing descriptions = blank preview cards.

  4. index.html has complete OG tag set — the landing page is the entry point for
                                         all social sharing. It must have og:title,
                                         og:description, og:image, og:url so that
                                         sharing on LinkedIn, WhatsApp, and Facebook
                                         produces a proper card with image and text.

Usage:  python validate_seo.py
Output: seo_report.json
"""
import re, json, sys

# Live pages that are publicly reachable (index.html is the landing page)
LANDING_PAGE = "index.html"

# Internal app pages — workers use these, but they should not be indexed
# by search engines (index.html is the SEO entry point)
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

ALL_PAGES = [LANDING_PAGE] + APP_PAGES

# Minimum title length to be considered descriptive (not just "WorkHive")
MIN_TITLE_LENGTH = 15

# Required OG properties on the landing page
REQUIRED_OG = ["og:title", "og:description", "og:image", "og:url"]


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


# ── Check 1: App pages have noindex ──────────────────────────────────────────

def check_noindex(pages):
    """
    Every internal app page must declare:
      <meta name="robots" content="noindex, follow">

    Without it, Google crawls and indexes these pages. This has two problems:
    1. It splits the domain's SEO equity across many thin pages instead of
       concentrating it on the landing page.
    2. Workers searching 'WorkHive logbook' may land directly on the app
       page (which requires login setup) instead of the landing page
       (which explains the product and helps them get started).

    'noindex' tells crawlers: don't list this page in search results.
    'follow' tells crawlers: still follow links on this page.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        if not re.search(
            r'<meta[^>]+name=["\']robots["\'][^>]*content=["\'][^"\']*noindex',
            content, re.IGNORECASE
        ) and not re.search(
            r'<meta[^>]+content=["\'][^"\']*noindex[^"\']*["\'][^>]*name=["\']robots["\']',
            content, re.IGNORECASE
        ):
            issues.append({
                "page": page,
                "reason": (
                    f"{page} is missing <meta name=\"robots\" content=\"noindex, follow\"> "
                    f"— search engines will index this app page instead of the landing page"
                ),
            })
    return issues


# ── Check 2: All live pages have a descriptive title tag ─────────────────────

def check_title_tags(pages):
    """
    Every live page must have a <title> tag that is:
    - Present (not missing)
    - Descriptive (at least MIN_TITLE_LENGTH characters)
    - Contains 'WorkHive' (brand consistency in browser tabs and search)

    The SEO skill specifies: 'pipe separator for title tags' — titles should
    use format 'Page Name | WorkHive' or 'Page Name: WorkHive', not em dashes.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue

        m = re.search(r"<title>([^<]*)</title>", content, re.IGNORECASE)
        if not m:
            issues.append({
                "page": page,
                "reason": f"{page} is missing a <title> tag",
            })
            continue

        title = m.group(1).strip()
        if len(title) < MIN_TITLE_LENGTH:
            issues.append({
                "page":  page,
                "title": title,
                "reason": (
                    f"{page} title is too short ({len(title)} chars, minimum "
                    f"{MIN_TITLE_LENGTH}): '{title}' — not descriptive enough "
                    f"for search results or browser tabs"
                ),
            })
            continue

        if "workhive" not in title.lower():
            issues.append({
                "page":  page,
                "title": title,
                "reason": (
                    f"{page} title does not include 'WorkHive': '{title}' — "
                    f"brand name should appear in every page title for recognition "
                    f"in search results and browser tabs"
                ),
            })

        # Check for em dash in title (SEO skill: use pipe, not em dash)
        if "—" in title or " -- " in title:
            issues.append({
                "page":  page,
                "title": title,
                "reason": (
                    f"{page} title uses an em dash instead of pipe separator: "
                    f"'{title}' — use 'Page Name | WorkHive' format"
                ),
            })

    return issues


# ── Check 3: All live pages have meta description ────────────────────────────

def check_meta_descriptions(pages):
    """
    Every live page must have:
      <meta name="description" content="...">

    Meta descriptions appear in:
    - Google/Bing search result snippets
    - Social media link previews (WhatsApp, Telegram, LinkedIn)
    - AI assistant summaries when the site is cited

    Missing descriptions result in blank or auto-generated snippets that
    are typically the first line of visible text — often a nav item or
    a generic 'WorkHive' mention that tells the user nothing useful.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue

        has_desc = bool(re.search(
            r'<meta[^>]+name=["\']description["\'][^>]*content=["\'][^"\']{10,}',
            content, re.IGNORECASE
        ) or re.search(
            r'<meta[^>]+content=["\'][^"\']{10,}["\'][^>]*name=["\']description["\']',
            content, re.IGNORECASE
        ))

        if not has_desc:
            issues.append({
                "page": page,
                "reason": (
                    f"{page} is missing <meta name=\"description\" content=\"...\"> "
                    f"— search results and social share cards will show a blank or "
                    f"auto-generated description"
                ),
            })
    return issues


# ── Check 4: Landing page has complete OG tag set ────────────────────────────

def check_og_tags(page):
    """
    The landing page (index.html) is shared on LinkedIn, WhatsApp, and
    social media when promoting WorkHive. It must have a complete Open Graph
    tag set so sharing produces a rich card with title, description, and image.

    Required tags:
    - og:title       — the page title shown in the share card
    - og:description — the snippet text shown below the title
    - og:image       — the preview image (logo or hero image)
    - og:url         — the canonical URL of the page
    """
    issues = []
    content = read_file(page)
    if content is None:
        return [{"page": page, "reason": f"{page} not found"}]

    for prop in REQUIRED_OG:
        if not re.search(
            rf'<meta[^>]+property=["\'][^"\']*{re.escape(prop)}["\']',
            content, re.IGNORECASE
        ):
            issues.append({
                "page": page,
                "prop": prop,
                "reason": (
                    f"{page} missing Open Graph tag '{prop}' — "
                    f"social share cards will be incomplete or broken"
                ),
            })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("SEO and Page Metadata Validator")
print("=" * 70)

fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        "[1] App pages have <meta name=robots content=noindex>",
        check_noindex(APP_PAGES),
        "FAIL",
    ),
    (
        "[2] All live pages have a descriptive <title> tag",
        check_title_tags(ALL_PAGES),
        "FAIL",
    ),
    (
        "[3] All live pages have <meta name=description>",
        check_meta_descriptions(ALL_PAGES),
        "FAIL",
    ),
    (
        "[4] index.html has complete Open Graph tag set",
        check_og_tags(LANDING_PAGE),
        "FAIL",
    ),
]

for label, issues, severity in checks:
    print(f"\n{label}\n")
    if not issues:
        print("  PASS")
    else:
        for iss in issues:
            print(f"  {severity}  {iss.get('page', '?')}")
            print(f"        {iss['reason']}")
        if severity == "FAIL":
            fail_count += len(issues)
        else:
            warn_count += len(issues)
    report[label] = issues

print(f"\n{'=' * 70}")
print(f"Result: {fail_count} FAIL  {warn_count} WARN")

with open("seo_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved seo_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll SEO checks PASS.")
