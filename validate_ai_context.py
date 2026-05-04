"""
AI Context Quality Validator — WorkHive Platform
=================================================
The AI assistant answers questions based entirely on the context baked into it.
Stale facts, thin descriptions, or missing features mean wrong or useless answers
to workers — silently, with no error.

  Layer 1 — Accuracy
    1.  Stale numeric facts        — detectPageContext hint has correct calc count (46)
    2.  Calc count consistency     — floating-ai.js and assistant.html agree on calc count
    3.  System prompt types        — all 3 conversation types defined (WORK/PLATFORM/PERSONAL)

  Layer 2 — Richness
    4.  PLATFORM TOOLS richness    — each tool description >= 15 words
    5.  Hint quality               — each page-specific hint >= 12 words

  Layer 3 — New feature coverage
    6.  Analytics OEE mentioned    — analytics PLATFORM TOOLS entry mentions OEE
    7.  Logbook new fields context — logbook entry mentions failure consequence / production

  Layer 4 — Engineering-design completeness
    8.  Eng-design context         — mentions BOM/SOW, diagrams, and Philippine standards

Usage:  python validate_ai_context.py
Output: ai_context_report.json
"""
import re, json, sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

FLOAT_JS        = "floating-ai.js"
ASSISTANT_HTML  = "assistant.html"
MIN_WORDS       = 15
MIN_HINT        = 12
CORRECT_CALC_COUNT = 46


def word_count(text):
    return len(text.split())


def get_platform_tools_block(content):
    start = content.find("PLATFORM TOOLS")
    # Bumped 3500 -> 6000 on 2026-05-05 after Project Manager was added — the
    # bullet sat at the tail of the section and the previous window cut it
    # mid-line, so word_count saw only the leading 10 words instead of the
    # full description. Same regression pattern as validate_assistant.py
    # check_platform_tools_completeness (3000 -> 5000 in May 2026).
    return content[start:start + 6000] if start != -1 else ""


# ── Layer 1: Accuracy ─────────────────────────────────────────────────────────

def check_stale_hints(content, page):
    """engineering-design detectPageContext hint must say the correct calc count."""
    if not content:
        return [{"check": "stale_hints", "page": page, "reason": f"{page} not found"}]
    m = re.search(
        r"path\.includes\(['\"]engineering-design['\"][^}]+hint:\s*['\"]([^'\"]+)['\"]",
        content
    )
    if not m:
        return []
    hint_text = m.group(1)
    count_m = re.search(r"(\d+)\s*calc\s*type", hint_text, re.IGNORECASE)
    if count_m:
        found = int(count_m.group(1))
        if found != CORRECT_CALC_COUNT:
            return [{"check": "stale_hints", "page": page,
                     "found": found, "expected": CORRECT_CALC_COUNT,
                     "reason": f"engineering-design hint says '{found} calc types' but platform has {CORRECT_CALC_COUNT} — workers get wrong count from AI"}]
    return []


def check_calc_count_consistency(float_content, assistant_content):
    """Both floating-ai.js and assistant.html must agree on the calc count."""
    if not float_content or not assistant_content:
        return []
    counts = {}
    for name, content in [("floating-ai.js", float_content), ("assistant.html", assistant_content)]:
        m = re.search(r"(\d+)\s*calc(?:ulation)?\s*type", content, re.IGNORECASE)
        if m:
            counts[name] = int(m.group(1))
    if len(counts) == 2:
        vals = list(counts.values())
        if vals[0] != vals[1]:
            return [{"check": "calc_count_consistency",
                     "reason": f"Calc count mismatch: floating-ai.js says {counts.get('floating-ai.js')}, assistant.html says {counts.get('assistant.html')} — workers get contradictory information"}]
    return []


def check_conversation_types(content, page):
    """All 3 conversation type handlers must be defined in the system prompt."""
    if not content:
        return []
    issues = []
    for ctype in ["WORK QUESTIONS", "PLATFORM QUESTIONS", "PERSONAL"]:
        if ctype not in content:
            issues.append({"check": "conversation_types", "page": page, "missing": ctype,
                           "reason": f"System prompt missing '{ctype}' conversation type — AI may not handle that category of worker questions correctly"})
    return issues


# ── Layer 2: Richness ─────────────────────────────────────────────────────────

def check_platform_tools_richness(content, page):
    if not content:
        return [{"check": "tools_richness", "page": page, "reason": f"{page} not found"}]
    block = get_platform_tools_block(content)
    if not block:
        return [{"check": "tools_richness", "page": page, "reason": "PLATFORM TOOLS section not found"}]
    issues = []
    for entry in re.findall(r"^- ([^\n]+)", block, re.MULTILINE):
        if "retired" in entry.lower():
            continue
        wc = word_count(entry)
        if wc < MIN_WORDS:
            tool = entry.split("(")[0].strip().split(":")[0].strip()
            issues.append({"check": "tools_richness", "page": page, "tool": tool,
                           "word_count": wc,
                           "reason": f"'{tool}' PLATFORM TOOLS description has only {wc} words (min {MIN_WORDS}) — AI has too little context to answer questions about this tool"})
    return issues


def check_hint_quality(content, page):
    if not content:
        return []
    issues = []
    for tool, hint_text in re.findall(
        r"path\.includes\(['\"]([^'\"]+)['\"][^}]+hint:\s*['\"]([^'\"]+)['\"]", content
    ):
        wc = word_count(hint_text)
        if wc < MIN_HINT:
            issues.append({"check": "hint_quality", "page": page, "tool": tool,
                           "word_count": wc,
                           "reason": f"'{tool}' hint has only {wc} words (min {MIN_HINT}) — AI gets minimal context on this page"})
    return issues


# ── Layer 3: New feature coverage ────────────────────────────────────────────

def check_analytics_oee_mentioned(content, page):
    """
    The Analytics Engine PLATFORM TOOLS entry and detectPageContext hint must
    mention OEE since it was added as a new analytics output. Workers asking
    about OEE from the analytics page will get wrong/no answer without it.
    """
    if not content:
        return []
    issues = []
    block = get_platform_tools_block(content)
    analytics_entry_m = re.search(r"- Analytics Engine[\s\S]{0,600}?(?=\n-|\Z)", block)
    if analytics_entry_m and "OEE" not in analytics_entry_m.group(0):
        issues.append({"check": "analytics_oee", "page": page,
                       "reason": "Analytics Engine PLATFORM TOOLS entry does not mention OEE — workers asking 'where do I see my OEE?' will not be directed correctly"})
    # Also check the page hint
    hint_m = re.search(
        r"path\.includes\(['\"]analytics['\"][^}]+hint:\s*['\"]([^'\"]+)['\"]", content
    )
    if hint_m and "OEE" not in hint_m.group(1) and "oee" not in hint_m.group(1).lower():
        issues.append({"check": "analytics_oee", "page": page,
                       "reason": "analytics detectPageContext hint does not mention OEE — AI on the Analytics page won't proactively explain OEE results"})
    return issues


def check_logbook_new_fields_context(content, page):
    """
    The logbook PLATFORM TOOLS entry should mention failure consequence
    and production output — features added in the recent logbook update.
    Without them, the AI won't know to tell workers about these fields.
    """
    if not content:
        return []
    block = get_platform_tools_block(content)
    logbook_m = re.search(r"- Digital Logbook[\s\S]{0,400}?(?=\n-|\Z)", block)
    if not logbook_m:
        return []
    lb_text = logbook_m.group(0)
    issues = []
    if not re.search(r"consequence|impact|failure.*category", lb_text, re.IGNORECASE):
        issues.append({"check": "logbook_new_fields", "page": page,
                       "reason": "Logbook PLATFORM TOOLS entry does not mention failure consequence field — AI can't tell workers how to classify breakdown impact"})
    if not re.search(r"production|OEE|quality|good units", lb_text, re.IGNORECASE):
        issues.append({"check": "logbook_new_fields", "page": page,
                       "reason": "Logbook PLATFORM TOOLS entry does not mention production output / OEE quality field — AI won't tell workers about this new data capture"})
    return issues


# ── Layer 4: Engineering-design completeness ──────────────────────────────────

def check_engineering_design_context(content, page):
    if not content:
        return []
    block = get_platform_tools_block(content)
    ed_m = re.search(r"Engineering Design Calculator[\s\S]{0,600}?(?=\n-|\Z)", block)
    if not ed_m:
        return [{"check": "eng_design_context", "page": page,
                 "reason": "Engineering Design Calculator not found in PLATFORM TOOLS"}]
    ed_text = ed_m.group(0)
    required = {
        "BOM / Bill of Materials":  ["BOM", "Bill of Materials"],
        "SOW / Scope of Works":     ["SOW", "Scope of Works"],
        "diagram / drawing output": ["diagram", "drawing", "Drawing"],
        "Philippine standard":      ["PEC", "ASHRAE", "NFPA", "PSME", "NSCP"],
    }
    issues = []
    for concept, terms in required.items():
        if not any(t in ed_text for t in terms):
            issues.append({"check": "eng_design_context", "page": page, "missing": concept,
                           "reason": f"Engineering Design entry missing '{concept}' — AI won't mention this feature when workers ask about the calculator"})
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    # L1
    "stale_hints", "calc_count_consistency", "conversation_types",
    # L2
    "tools_richness", "hint_quality",
    # L3
    "analytics_oee", "logbook_new_fields",
    # L4
    "eng_design_context",
]

CHECK_LABELS = {
    # L1
    "stale_hints":           "L1  Correct calc count in engineering-design hint",
    "calc_count_consistency":"L1  Calc count consistent between widget and assistant",
    "conversation_types":    "L1  All 3 conversation types in system prompt",
    # L2
    "tools_richness":        "L2  PLATFORM TOOLS descriptions >= 15 words each",
    "hint_quality":          "L2  Page-specific hints >= 12 words each",
    # L3
    "analytics_oee":         "L3  Analytics entry mentions OEE",
    "logbook_new_fields":    "L3  Logbook entry mentions failure consequence + production",
    # L4
    "eng_design_context":    "L4  Eng-design mentions BOM/SOW/diagrams/standards",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nAI Context Quality Validator (4-layer)"))
    print("=" * 55)

    float_js   = read_file(FLOAT_JS)
    assistant  = read_file(ASSISTANT_HTML)

    all_issues = []
    all_issues += check_stale_hints(float_js, FLOAT_JS)
    all_issues += check_calc_count_consistency(float_js, assistant)
    all_issues += check_conversation_types(float_js, FLOAT_JS)
    all_issues += check_platform_tools_richness(float_js, FLOAT_JS)
    all_issues += check_hint_quality(float_js, FLOAT_JS)
    all_issues += check_analytics_oee_mentioned(float_js, FLOAT_JS)
    all_issues += check_logbook_new_fields_context(float_js, FLOAT_JS)
    all_issues += check_engineering_design_context(float_js, FLOAT_JS)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "ai_context",
        "total_checks": total,
        "passed":       n_pass,
        "skipped":      n_skip,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
    }
    with open("ai_context_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
