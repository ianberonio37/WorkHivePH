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
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from validator_utils import read_file, format_result
from wh_pages import article_tool_map

# slug -> (tool_url, tool_name) sourced from wh_pages.LEARN_ARTICLES so the
# article catalog and CTA validation never drift apart.
ARTICLE_TOOL_MAP = article_tool_map()

# Any /<tool>.html anchor counts as tool-aligned (we don't require it to be
# the EXACT tool from the map — switching tool focus over time is fine).
# Matches both relative root-absolute (`/logbook.html`) and full URL forms.
TOOL_ANCHOR_RE = re.compile(
    r'<a[^>]+href=["\'](?:https?://workhiveph\.com)?(/[a-z0-9-]+\.html)["\']',
    re.IGNORECASE,
)

# Pages that are NOT tools (these don't count as a tool-aligned CTA)
NON_TOOL_PAGES = {
    "/index.html", "/about/index.html", "/privacy-policy/index.html",
    "/terms-of-service/index.html", "/learn/index.html",
}

# A bare /#join or href="#join" in place of a real tool CTA is the
# anti-pattern this validator catches.
JOIN_ONLY_CTA_RE = re.compile(
    r'class=["\'][^"\']*(?:btn|cta|button)[^"\']*["\'][^>]*href=["\']#?/?#join["\']',
    re.IGNORECASE,
)


def check_has_tool_anchor(articles):
    """Every /learn/ article must have at least one anchor to a /<tool>.html."""
    issues = []
    for slug, (expected_tool, _) in articles.items():
        page = f"learn/{slug}/index.html"
        content = read_file(page)
        if content is None:
            continue
        tool_anchors = [m.group(1) for m in TOOL_ANCHOR_RE.finditer(content)
                        if m.group(1) not in NON_TOOL_PAGES
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


CHECK_NAMES  = ["has_tool_anchor", "names_target_tool", "no_join_only_cta"]
CHECK_LABELS = {
    "has_tool_anchor":   "L1  Every /learn/ article has ≥1 anchor to a /<tool>.html page",
    "names_target_tool": "L2  Article body names the target WorkHive tool at least once",
    "no_join_only_cta":  "L3  No button-styled CTA points only to /#join (anti-pattern)",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nTool-Aligned CTA Validator (3-layer)"))
    print("=" * 55)

    all_issues = []
    all_issues += check_has_tool_anchor(ARTICLE_TOOL_MAP)
    all_issues += check_names_target_tool(ARTICLE_TOOL_MAP)
    all_issues += check_no_join_only_cta(ARTICLE_TOOL_MAP)

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
