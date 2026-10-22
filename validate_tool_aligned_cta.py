"""
Tool-Aligned CTA Validator — WorkHive Platform
===============================================
Enforces [[feedback-articles-tool-aligned]]: every /learn/ article must
include at least one mid-article CTA linking to a real WorkHive tool page
(e.g., /logbook.html, /pm-scheduler.html), NOT a generic /#join CTA.

The article-to-tool map is the funnel that turns search traffic into
platform usage. Generic /#join CTAs collapse this funnel.

Also enforces: every article must NAME its target tool in the article body
at least once (so the article actually teaches the tool's purpose, not just
links to it as an afterthought).

Layer 1: Every /learn/<slug>/index.html has at least 1 anchor to a
         /<tool>.html URL (where <tool> is a real WorkHive tool)
Layer 2: The article body mentions the WorkHive tool by name at least once
Layer 3: The mid-article CTA is NOT just a generic /#join (which would
         indicate the tool-alignment was skipped)

Usage:  python validate_tool_aligned_cta.py
Output: tool_aligned_cta_report.json
"""
import re, json, sys
if sys.platform == "win32":
    try:   # reconfigure, not a new TextIOWrapper: tools/enhancement_inventory.py imports this module
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import glob, os
from validator_utils import read_file, format_result
from wh_pages import article_tool_map
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))
from cta_gate import body_region

# slug -> (tool_url, tool_name) sourced from wh_pages.LEARN_ARTICLES so the
# article catalog and CTA validation never drift apart.
ARTICLE_TOOL_MAP = article_tool_map()

# Any /<tool>.html anchor counts as tool-aligned (we don't require it to be
# the EXACT tool from the map — switching tool focus over time is fine).
# Matches both relative root-absolute (`/logbook.html`) and full URL forms.
# A DEEP LINK IS STILL A LINK (ENH-L, 2026-10-23): the personas guide's button opens
# /index.html?companion=1, and a pattern that wanted the quote right after .html read it as
# no link at all - the cta_gate lesson of 2026-08-17, repeated here. The query is captured.
TOOL_ANCHOR_RE = re.compile(
    r'<a[^>]+href=["\'](?:https?://workhiveph\.com)?(/[a-z0-9-]+\.html(?:\?[^"\'#]*)?)(?:#[^"\']*)?["\']',
    re.IGNORECASE,
)

# Pages that are NOT tools (these don't count as a tool-aligned CTA)
NON_TOOL_PAGES = {
    "/index.html", "/about/index.html", "/privacy-policy/index.html",
    "/terms-of-service/index.html", "/learn/index.html",
}

# A guide about WorkHive itself (the overview, the platform comparisons) declares the landing
# page, and its next step is the platform: sign-up or the landing page, never a bare "/" (every
# breadcrumb's Home link would pass that).
PLATFORM_CTA_RE = re.compile(
    r'<a[^>]+href=["\'](?:https?://workhiveph\.com)?/(?:\?signup=1|index\.html)[^"\']*["\']', re.IGNORECASE)


def _path(href: str) -> str:
    return href.split("?", 1)[0]


def reaches_declared_tool(html: str, declared: str) -> bool:
    """Does the article BODY send its reader to the tool the catalog declares for it? Header and
    footer chrome are excluded (cta_gate.body_region): "from the guide itself" means the article.
    A declared deep link (/index.html?companion=1) must be linked as declared; a plain declared
    path is reached by any link to it, query or not."""
    body = body_region(html)
    want = declared if declared.startswith("/") else "/" + declared
    if want == "/index.html":
        return bool(PLATFORM_CTA_RE.search(body))
    hrefs = {m.group(1) for m in TOOL_ANCHOR_RE.finditer(body)}
    return want in hrefs or ("?" not in want and want in {_path(h) for h in hrefs})


def shipped_guides() -> list:
    """Every guide a reader can open: learn/<slug>/index.html on disk (the hub is learn/index.html)."""
    return sorted(os.path.basename(os.path.dirname(p))
                  for p in glob.glob(os.path.join("learn", "*", "index.html")))


def check_catalog_covers_disk(articles, on_disk=None):
    """L0: every shipped guide is IN the catalog. Nine were not (2026-10-23): the pillar, problem and
    comparison generators and one hand-made page wrote guides that no catalog reader ever graded, so
    every check below ran over 45 of the 54 guides a reader can open."""
    issues = []
    for slug in (shipped_guides() if on_disk is None else on_disk):
        if slug not in articles:
            issues.append({"check": "catalog_covers_disk", "page": f"learn/{slug}/index.html",
                           "reason": (f"learn/{slug}/index.html ships but is not in wh_pages.LEARN_ARTICLES, so "
                                      f"no check here (or in the six other catalog readers) ever reads it. Add its "
                                      f"tuple with the tool its own button opens.")})
    return issues

# A bare /#join or href="#join" in place of a real tool CTA is the
# anti-pattern this validator catches.
JOIN_ONLY_CTA_RE = re.compile(
    r'class=["\'][^"\']*(?:btn|cta|button)[^"\']*["\'][^>]*href=["\']#?/?#join["\']',
    re.IGNORECASE,
)


def check_has_tool_anchor(articles, read=read_file):
    """Every /learn/ article must have at least one anchor to a /<tool>.html in its body - or, for a
    guide about WorkHive itself (declared /index.html), a link to the platform."""
    issues = []
    for slug, (expected_tool, _) in articles.items():
        page = f"learn/{slug}/index.html"
        content = read(page)
        if content is None:
            continue
        if _path(expected_tool) == "/index.html" and "?" not in expected_tool:
            if not PLATFORM_CTA_RE.search(body_region(content)):
                issues.append({"check": "has_tool_anchor", "page": page,
                               "reason": (f"{page} is about WorkHive itself (declared /index.html) and its body "
                                          f"links neither sign-up nor the landing page - nowhere to go next.")})
            continue
        tool_anchors = [m.group(1) for m in TOOL_ANCHOR_RE.finditer(body_region(content))
                        if _path(m.group(1)) not in NON_TOOL_PAGES
                        and not m.group(1).startswith("/learn/")]
        if not tool_anchors:
            issues.append({"check": "has_tool_anchor", "page": page,
                           "reason": (f"{page} has no anchor to a "
                                      f"/<tool>.html page. Expected at "
                                      f"least one CTA to {expected_tool} "
                                      f"per feedback_articles_tool_aligned.")})
    return issues


def check_names_target_tool(articles):
    """The article body must mention the target tool by its name at least
    once, so the article actually teaches the tool's purpose."""
    issues = []
    for slug, (_, tool_name) in articles.items():
        page = f"learn/{slug}/index.html"
        content = read_file(page)
        if content is None:
            continue
        # Case-insensitive search. WorkHive tools often appear as exact phrase.
        if tool_name.lower() not in content.lower():
            issues.append({"check": "names_target_tool", "page": page,
                           "reason": (f"{page} does not mention '{tool_name}' "
                                      f"by name. Article must teach the tool "
                                      f"it's funneling readers toward.")})
    return issues


def check_no_join_only_cta(articles):
    """Catch the legacy anti-pattern of a generic /#join CTA in place of
    a real tool CTA. (Note: footer Join links are fine; this targets
    PROMINENT button-styled CTAs.)"""
    issues = []
    for slug in articles:
        page = f"learn/{slug}/index.html"
        content = read_file(page)
        if content is None:
            continue
        if JOIN_ONLY_CTA_RE.search(content):
            issues.append({"check": "no_join_only_cta", "page": page,
                           "reason": (f"{page} has a button-styled CTA "
                                      f"pointing only to #join. Replace "
                                      f"with a CTA to the article's target "
                                      f"WorkHive tool (e.g., /logbook.html).")})
    return issues



def check_cta_matches_declared_tool(articles, read=read_file):
    """L4: the article's OWN CTA must point at the tool its registry entry DECLARES.

    ★THE THREE CHECKS ABOVE ALL PASSED WHILE AN ARTICLE POINTED SOMEWHERE ELSE (T174, 2026-08-28).
    learn/maintenance-project-planning-template declared tool_path='/hive.html' in wh_pages.py while
    naming "Project Manager" fourteen times and carrying <a href="/project-manager.html">Open Project
    Manager</a>. L1 was satisfied (it anchors to SOME tool), L2 was satisfied (it names A tool), L3
    was satisfied - and the article and its registry entry disagreed about what it is for.

    That is not cosmetic: learn-link.js keys the page-guide chip off tool_path, so the project-
    planning guide was offered on the HIVE BOARD while project-manager.html had no guide at all. A
    mis-declared tool silently moves a page's help to a different page.

    An article may legitimately link several tools; the rule is that its DECLARED tool is among the
    ones its BODY links. It FAILS: format_result counts every issue without skip=True, so the "warn"
    this once claimed to be never existed. It is also the check that holds ENH-L - a guide sends its
    reader to the tool it is about - so the body is what it reads (reaches_declared_tool).
    """
    issues = []
    for slug, (expected_tool, _) in articles.items():
        page = f"learn/{slug}/index.html"
        content = read(page)
        if content is None:
            continue
        anchors = {m.group(1) for m in TOOL_ANCHOR_RE.finditer(body_region(content))}
        if not anchors:
            continue                      # L1 already reports the no-anchor case
        want = expected_tool if expected_tool.startswith("/") else "/" + expected_tool
        # ★AN ARTICLE DECLARING A NON-TOOL TARGET IS OUT OF SCOPE, NOT IN VIOLATION. The platform
        # OVERVIEW declares /index.html and links all 26 tools; the landing page is not a tool
        # anchor, so "is the declared tool among the anchors" has no meaning for it. Flagging it
        # would be the check misreading its own denominator - the same shape as counting a vendored
        # library's .range() as a pagination defect. (L1 holds those: sign-up or the landing page.)
        if want.lstrip("/") in NON_TOOL_PAGES or want == "/index.html":
            continue
        if not reaches_declared_tool(content, want):
            issues.append({"check": "cta_matches_declared_tool", "page": page,
                           "reason": (f"{page} declares tool_path {want} in wh_pages.LEARN_ARTICLES "
                                      f"but its body links {sorted(anchors)} - the article and the "
                                      f"registry disagree about what it is for, and learn-link.js "
                                      f"puts the page-guide chip on the DECLARED page, so the guide "
                                      f"lands somewhere the article is not about.")})
    return issues


CHECK_NAMES  = ["catalog_covers_disk", "has_tool_anchor", "names_target_tool", "no_join_only_cta",
                "cta_matches_declared_tool"]
CHECK_LABELS = {
    "catalog_covers_disk": "L0  Every shipped /learn/ guide is in the catalog the checks below read",
    "has_tool_anchor":   "L1  Every /learn/ article body links a /<tool>.html page (a WorkHive guide: sign-up)",
    "names_target_tool": "L2  Article body names the target WorkHive tool at least once",
    "no_join_only_cta":  "L3  No button-styled CTA points only to /#join (anti-pattern)",
    "cta_matches_declared_tool": "L4  Article body links the tool its registry entry DECLARES",
}


def self_test() -> int:
    """Mutants against synthetic guides: each defect must be named, each honest page must pass."""
    def page(body):
        return f'<html><header><a href="/logbook.html">nav</a></header><main>{body}</main><footer></footer></html>'
    pages = {
        "learn/ok/index.html": page('<a href="/logbook.html" class="cta-btn">Open the Logbook</a> Logbook'),
        "learn/deep/index.html": page('<a href="/index.html?companion=1" class="cta-btn">Open</a> AI Companion'),
        "learn/elsewhere/index.html": page('<a href="/hive.html" class="cta-btn">Open the Hive</a> Logbook'),
        "learn/chrome-only/index.html": page('No link in the article. Logbook'),
        "learn/platform/index.html": page('<a href="/?signup=1" class="cta-btn">Try WorkHive free</a> WorkHive'),
        "learn/platform-home/index.html": page('<a href="/">Home</a> WorkHive'),
    }
    read = pages.get
    arts = {"ok": ("/logbook.html", "Logbook"), "deep": ("/index.html?companion=1", "AI Companion"),
            "elsewhere": ("/logbook.html", "Logbook"), "chrome-only": ("/logbook.html", "Logbook"),
            "platform": ("/index.html", "WorkHive"), "platform-home": ("/index.html", "WorkHive")}
    l0 = {i["page"] for i in check_catalog_covers_disk(arts, on_disk=list(arts) + ["orphan"])}
    l1 = {i["page"] for i in check_has_tool_anchor(arts, read)}
    l4 = {i["page"] for i in check_cta_matches_declared_tool(arts, read)}
    cases = [
        ("an uncatalogued guide fails L0", l0 == {"learn/orphan/index.html"}),
        ("a link only in the header chrome fails L1", "learn/chrome-only/index.html" in l1),
        ("a WorkHive guide with only a Home link fails L1", "learn/platform-home/index.html" in l1),
        ("a WorkHive guide ending on sign-up passes L1", "learn/platform/index.html" not in l1),
        ("a body link to another tool fails L4", "learn/elsewhere/index.html" in l4),
        ("a deep link to the declared target passes L4", "learn/deep/index.html" not in l4),
        ("the honest guide passes L1 and L4", "learn/ok/index.html" not in l1 | l4),
    ]
    bad = [n for n, ok in cases if not ok]
    for n, ok in cases:
        print(f"  {'ok  ' if ok else 'FAIL'} {n}")
    print(f"  self-test: {len(cases) - len(bad)}/{len(cases)}")
    return 1 if bad else 0


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    print(bold("\nTool-Aligned CTA Validator (5-layer)"))
    print("=" * 55)

    all_issues = []
    all_issues += check_catalog_covers_disk(ARTICLE_TOOL_MAP)
    all_issues += check_has_tool_anchor(ARTICLE_TOOL_MAP)
    all_issues += check_names_target_tool(ARTICLE_TOOL_MAP)
    all_issues += check_no_join_only_cta(ARTICLE_TOOL_MAP)
    all_issues += check_cta_matches_declared_tool(ARTICLE_TOOL_MAP)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {len(CHECK_NAMES)} checks passed across "
              f"{len(ARTICLE_TOOL_MAP)} /learn/ articles.\033[0m")
    else:
        color = "91" if n_fail else "93"
        print(f"\033[{color}m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":     "tool_aligned_cta",
        "total_checks":  len(CHECK_NAMES),
        "articles_scanned": len(ARTICLE_TOOL_MAP),
        "passed":        n_pass,
        "warned":        n_warn,
        "failed":        n_fail,
        "issues":        [i for i in all_issues if not i.get("skip")],
        "warnings":      [i for i in all_issues if i.get("skip")],
    }
    with open("tool_aligned_cta_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
