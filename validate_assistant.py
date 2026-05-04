"""
Assistant Validator — WorkHive Platform
========================================
Four-layer validation of floating-ai.js + assistant.html:

  Layer 1 — Page coverage
    1.  Page context entries          — every live tool has path.includes() in floating-ai.js
    2.  PLATFORM TOOLS completeness   — every live tool mentioned in system prompt
    3.  assistant.html completeness   — assistant.html system prompt covers all live tools
    4.  Retired pages not active      — parts-tracker/checklist not listed as active tools

  Layer 2 — AI config correctness
    5.  API key not exposed           — no hardcoded key string in source
    6.  API routed through Worker     — fetch uses workerUrl, not direct Groq endpoint
    7.  isTyping double-submit guard  — concurrent request prevention in handleSend
    8.  History slice bounded         — slice sent to API is <= maxHistory/2

  Layer 3 — Content accuracy
    9.  Skill Matrix disciplines      — discipline names match actual DISCIPLINES constant
    10. Calc count accuracy           — engineering-design description says 46 calc types
    11. System prompt word limit      — "under X words" instruction present

  Layer 4 — XSS / output safety
    12. renderMarkdown wraps AI output — AI replies pass through renderMarkdown before innerHTML
    13. AI cannot-access disclaimer   — widget states it has no DB access to worker records

Usage:  python validate_assistant.py
Output: assistant_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, extract_js_array, format_result

FLOAT_JS       = "floating-ai.js"
ASSISTANT_PAGE = "assistant.html"
CONTENT_FILE   = "skill-content.js"

# All live tool pages — must be covered in both floating-ai.js and assistant.html
LIVE_TOOL_PAGES = [
    "logbook", "assistant", "dayplanner", "pm-scheduler",
    "hive", "inventory", "skillmatrix", "engineering-design", "analytics",
    "analytics-report",
    "report-sender", "community", "marketplace",
]

RETIRED_PAGES = ["parts-tracker", "checklist"]

PAGE_ALIASES = {
    "engineering-design": ["engineering-design", "Engineering Design", "Engineering Calculator", "Engineering Design Calculator"],
    "pm-scheduler":       ["pm-scheduler", "PM Scheduler"],
    "skillmatrix":        ["skillmatrix", "Skill Matrix"],
    "analytics":          ["analytics", "Analytics Engine"],
    "analytics-report":   ["analytics-report", "Analytics Report"],
}


# ── Layer 1: Page coverage ────────────────────────────────────────────────────

def check_page_context_entries(content, page):
    if not content:
        return [{"check": "page_context_entries", "page": page, "reason": f"{page} not found"}]
    issues = []
    for tool in LIVE_TOOL_PAGES:
        if not re.search(rf"path\.includes\(['\"]({re.escape(tool)})['\"]", content):
            issues.append({"check": "page_context_entries", "page": page, "tool": tool,
                           "reason": f"path.includes('{tool}') missing — users on {tool}.html get generic hints"})
    return issues


def check_platform_tools_completeness(content, page):
    if not content:
        return []
    start = content.find("PLATFORM TOOLS")
    if start == -1:
        return [{"check": "platform_tools_completeness", "page": page,
                 "reason": "PLATFORM TOOLS section not found in system prompt"}]
    # Window must cover the entire PLATFORM TOOLS list. 3000 was too tight
    # — bumping to 5000 leaves headroom for new tool blurbs without cascade
    # failures on adjacent tools that drift past the cutoff.
    block = content[start:start + 5000]
    issues = []
    for tool in LIVE_TOOL_PAGES:
        aliases = PAGE_ALIASES.get(tool, [tool])
        if not any(a in block for a in aliases):
            issues.append({"check": "platform_tools_completeness", "page": page, "tool": tool,
                           "reason": f"'{tool}' not in PLATFORM TOOLS — AI cannot answer 'where do I find {tool}?'"})
    return issues


def check_assistant_page_completeness(content, page):
    """assistant.html has its own system prompt — must also cover all live tools."""
    if not content:
        return [{"check": "assistant_page_completeness", "page": page,
                 "reason": f"{page} not found"}]
    issues = []
    for tool in LIVE_TOOL_PAGES:
        aliases = PAGE_ALIASES.get(tool, [tool])
        if not any(a in content for a in aliases):
            issues.append({"check": "assistant_page_completeness", "page": page, "tool": tool,
                           "reason": f"'{tool}' not mentioned in assistant.html system context — full assistant gives incomplete answers"})
    return issues


def check_retired_pages(content, page):
    if not content:
        return []
    issues = []
    for retired in RETIRED_PAGES:
        for mention in re.findall(
            rf".{{0,50}}{re.escape(retired)}\.html.{{0,100}}|.{{0,10}}-\s*{re.escape(retired).title()}\s*[(\-].{{0,100}}",
            content, re.IGNORECASE
        ):
            if not any(w in mention.lower() for w in ["retired", "removed", "no longer", "deprecated", "replaced"]):
                issues.append({"check": "retired_pages", "page": page, "retired_page": retired,
                               "context": mention.strip(),
                               "reason": f"'{retired}.html' referenced as active — AI may direct users to a non-existent page"})
    return issues


# ── Layer 2: AI config correctness ────────────────────────────────────────────

def check_api_key_not_exposed(content, page):
    if not content:
        return []
    # Check apiKey field — should be '' (empty) since key is in the Worker
    m = re.search(r"apiKey\s*:\s*['\"]([^'\"]{8,})['\"]", content)
    if m:
        return [{"check": "api_key_not_exposed", "page": page,
                 "reason": f"apiKey appears to contain a non-empty value — API key should never be in client-side source"}]
    return []


def check_api_routed_through_worker(content, page):
    if not content:
        return []
    # API call must use workerUrl, not a direct Groq/OpenAI endpoint
    if re.search(r"fetch\s*\(\s*['\"]https://api\.groq\.com", content):
        return [{"check": "api_routed_through_worker", "page": page,
                 "reason": "Direct fetch to api.groq.com found — API calls should route through the Cloudflare Worker to keep the key server-side"}]
    if not re.search(r"fetch\s*\(\s*config\.workerUrl", content):
        return [{"check": "api_routed_through_worker", "page": page,
                 "reason": "fetch(config.workerUrl) not found — API routing pattern may have changed"}]
    return []


def check_is_typing_guard(content, page):
    if not content:
        return []
    if "isTyping" not in content:
        return [{"check": "is_typing_guard", "page": page,
                 "reason": "isTyping guard not found — user can fire multiple concurrent API requests"}]
    # Confirm it's used in handleSend as a guard
    m = re.search(r"async function handleSend\s*\(", content)
    if m:
        body = content[m.start():m.start() + 200]
        if "isTyping" not in body:
            return [{"check": "is_typing_guard", "page": page,
                     "reason": "isTyping not checked at start of handleSend — double-submit possible"}]
    return []


def check_history_slice_bounded(content, page):
    """
    The messages sent to the AI API must be a bounded slice of history.
    history.slice(-N) where N should be <= maxHistory/2 to prevent token overflow.
    """
    if not content:
        return []
    # Find maxHistory value
    max_hist_m = re.search(r"maxHistory\s*:\s*(\d+)", content)
    max_hist = int(max_hist_m.group(1)) if max_hist_m else None

    # Find history.slice(-N)
    slice_m = re.search(r"history\.slice\s*\(-\s*(\d+)\)", content)
    if not slice_m:
        # Also check Math.floor pattern
        floor_m = re.search(r"history\.slice\s*\(-\s*Math\.floor\s*\([^)]+\)\s*\)", content)
        if not floor_m:
            return [{"check": "history_slice_bounded", "page": page,
                     "reason": "history.slice(-N) not found — all history may be sent to API causing token overflow"}]
        return []

    slice_n = int(slice_m.group(1))
    if max_hist and slice_n > max_hist / 2:
        return [{"check": "history_slice_bounded", "page": page,
                 "found_slice": slice_n, "max_history": max_hist,
                 "reason": f"history.slice(-{slice_n}) sends more than half of maxHistory ({max_hist}) — risk of token overflow"}]
    return []


# ── Layer 3: Content accuracy ─────────────────────────────────────────────────

def check_skillmatrix_disciplines(float_content, skill_content, page):
    if not float_content or not skill_content:
        return []
    actual = extract_js_array(skill_content, "DISCIPLINES")
    if not actual:
        return [{"check": "skillmatrix_disciplines", "page": CONTENT_FILE,
                 "reason": "DISCIPLINES not found in skill-content.js"}]
    start = float_content.find("PLATFORM TOOLS")
    if start == -1:
        return [{"check": "skillmatrix_disciplines", "page": page,
                 "reason": "PLATFORM TOOLS section not found"}]
    block = float_content[start:start + 3000]
    sm_m  = re.search(r"[Ss]kill [Mm]atrix[\s\S]{0,400}?(?=\n-|\Z)", block)
    if not sm_m:
        return [{"check": "skillmatrix_disciplines", "page": page,
                 "reason": "Skill Matrix description not found in PLATFORM TOOLS"}]
    sm_line = sm_m.group(0)
    return [{"check": "skillmatrix_disciplines", "page": page, "discipline": d,
             "reason": f"Skill Matrix description missing discipline '{d}' — AI gives wrong answer about available disciplines"}
            for d in actual if d not in sm_line]


def check_calc_count_accuracy(content, page):
    if not content:
        return [{"check": "calc_count_accuracy", "page": page, "reason": f"{page} not found"}]
    m = re.search(r"engineering.design[\s\S]{0,500}?(\d+)\s*calc(?:ulation)?\s*type", content, re.IGNORECASE)
    if not m:
        return [{"check": "calc_count_accuracy", "page": page,
                 "reason": "Calc type count not found in engineering-design description"}]
    count = int(m.group(1))
    if count < 46:
        return [{"check": "calc_count_accuracy", "page": page, "found_count": count,
                 "reason": f"Says '{count} calculation types' but platform has 46 — stale count"}]
    return []


def check_system_prompt_word_limit(content, page):
    if not content:
        return []
    if not re.search(r"under\s+\d+\s+words", content, re.IGNORECASE):
        return [{"check": "system_prompt_word_limit", "page": page,
                 "reason": "'Keep responses under N words' instruction missing — AI may give excessively long replies"}]
    return []


# ── Layer 4: XSS / output safety ─────────────────────────────────────────────

def check_render_markdown_used(content, page):
    """AI replies must pass through renderMarkdown (which sanitises output) before innerHTML."""
    if not content:
        return []
    # addMessage should use renderMarkdown
    m = re.search(r"function addMessage\s*\(", content)
    if not m:
        return [{"check": "render_markdown_used", "page": page,
                 "reason": "addMessage() not found — cannot verify AI output sanitisation"}]
    body = content[m.start():m.start() + 300]
    if "renderMarkdown" not in body:
        return [{"check": "render_markdown_used", "page": page,
                 "reason": "addMessage() does not call renderMarkdown — AI output inserted as raw HTML"}]
    return []


def check_no_db_access_disclaimer(content, page):
    """Floating AI widget must tell users it has no access to their work records."""
    if not content:
        return []
    if not re.search(r"not connected|no access|don.t have access", content, re.IGNORECASE):
        return [{"check": "no_db_access_disclaimer", "page": page,
                 "reason": "No 'not connected to database' disclaimer in system prompt — users may expect the widget to know their work history"}]
    return []


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    # L1
    "page_context_entries", "platform_tools_completeness",
    "assistant_page_completeness", "retired_pages",
    # L2
    "api_key_not_exposed", "api_routed_through_worker",
    "is_typing_guard", "history_slice_bounded",
    # L3
    "skillmatrix_disciplines", "calc_count_accuracy", "system_prompt_word_limit",
    # L4
    "render_markdown_used", "no_db_access_disclaimer",
]

CHECK_LABELS = {
    # L1
    "page_context_entries":        "L1  path.includes() entry for every live tool",
    "platform_tools_completeness": "L1  PLATFORM TOOLS covers all live tools",
    "assistant_page_completeness": "L1  assistant.html context covers all live tools",
    "retired_pages":               "L1  Retired pages not listed as active",
    # L2
    "api_key_not_exposed":         "L2  API key not hardcoded in source",
    "api_routed_through_worker":   "L2  API calls routed through Cloudflare Worker",
    "is_typing_guard":             "L2  isTyping guard prevents double-submit",
    "history_slice_bounded":       "L2  history.slice(-N) bounded to <= maxHistory/2",
    # L3
    "skillmatrix_disciplines":     "L3  Skill Matrix disciplines match DISCIPLINES constant",
    "calc_count_accuracy":         "L3  Engineering design says 46 calc types",
    "system_prompt_word_limit":    "L3  System prompt has word limit instruction",
    # L4
    "render_markdown_used":        "L4  AI output passes through renderMarkdown",
    "no_db_access_disclaimer":     "L4  Widget disclaims no DB access to worker records",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nAssistant Validator (4-layer)"))
    print("=" * 55)

    float_js   = read_file(FLOAT_JS)
    assistant  = read_file(ASSISTANT_PAGE)
    skill_cont = read_file(CONTENT_FILE)

    if not float_js:
        print(f"  ERROR: {FLOAT_JS} not found")
        sys.exit(1)

    all_issues = []

    # L1
    all_issues += check_page_context_entries(float_js, FLOAT_JS)
    all_issues += check_platform_tools_completeness(float_js, FLOAT_JS)
    all_issues += check_assistant_page_completeness(assistant, ASSISTANT_PAGE)
    all_issues += check_retired_pages(float_js, FLOAT_JS)

    # L2
    all_issues += check_api_key_not_exposed(float_js, FLOAT_JS)
    all_issues += check_api_routed_through_worker(float_js, FLOAT_JS)
    all_issues += check_is_typing_guard(float_js, FLOAT_JS)
    all_issues += check_history_slice_bounded(float_js, FLOAT_JS)

    # L3
    all_issues += check_skillmatrix_disciplines(float_js, skill_cont, FLOAT_JS)
    all_issues += check_calc_count_accuracy(assistant, ASSISTANT_PAGE)
    all_issues += check_system_prompt_word_limit(float_js, FLOAT_JS)

    # L4
    all_issues += check_render_markdown_used(float_js, FLOAT_JS)
    all_issues += check_no_db_access_disclaimer(float_js, FLOAT_JS)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "assistant",
        "total_checks": total,
        "passed":       n_pass,
        "skipped":      n_skip,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
    }
    with open("assistant_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
