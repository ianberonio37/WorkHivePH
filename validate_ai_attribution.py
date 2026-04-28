"""
AI Output Attribution Validator — WorkHive Platform
====================================================
WorkHive generates AI content in three contexts:
  1. Engineering calc narratives (in PDF reports)
  2. The floating AI widget (answers platform questions)
  3. The full AI assistant page (answers from personal work records)

Each context has different attribution requirements. A calc narrative is
used for actual engineering decisions — it must include a professional
engineer sign-off requirement. The floating widget must be transparent
about what it doesn't know. The assistant must be explicit about which
records it has access to.

  Layer 1 — Report attribution
    1.  narrative-block CSS class       — AI prose visually distinct from calc numbers
    2.  Safety-critical PRC sign-off    — regulated calcs must require licensed engineer  [WARN]

  Layer 2 — Widget transparency
    3.  Floating AI no-records disclaimer — widget must state it has no work history access
    4.  Assistant scope limitation        — assistant must limit itself to shown records

  Layer 3 — AI identity clarity
    5.  Narrative prompt AI identity      — prompt must not claim AI is a licensed human engineer  [WARN]
    6.  Per-message AI attribution        — assistant chat bubbles need AI label, not just page footer  [WARN]

Usage:  python validate_ai_attribution.py
Output: ai_attribution_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

ENGINEERING_PAGE = "engineering-design.html"
FLOATING_AI      = "floating-ai.js"
ASSISTANT_PAGE   = "assistant.html"
CALC_AGENT       = os.path.join("supabase", "functions", "engineering-calc-agent", "index.ts")

NARRATIVE_CSS_CLASS = "narrative-block"

SAFETY_CRITICAL_TYPES = [
    "Lightning Protection System",
    "Earthing / Grounding",
    "Short Circuit",
    "Fire Pump",
    "Fire Sprinkler",
    "Generator Sizing",
    "Wire Sizing",
    "Shaft Design",
    "Elevator Traffic",
]


# ── Layer 1: Report attribution ───────────────────────────────────────────────

def check_narrative_class(page):
    """AI-generated narrative sections must use class='narrative-block' to visually
    distinguish them from deterministic engineering results in printed reports."""
    content = read_file(page)
    if content is None:
        return [{"check": "narrative_class", "page": page,
                 "reason": f"{page} not found"}]
    if not re.search(rf'class="{NARRATIVE_CSS_CLASS}"', content):
        return [{"check": "narrative_class", "page": page,
                 "reason": (f"{page} has no elements with class='{NARRATIVE_CSS_CLASS}' — "
                            f"AI-generated narrative is visually indistinguishable from "
                            f"deterministic engineering results in printed reports")}]
    return []


def check_prc_disclaimer(func_path, calc_types):
    """For regulated engineering work, AI-generated recommendation text must
    require PRC-licensed sign-off before the report is used for permit submission."""
    issues = []
    content = read_file(func_path)
    if content is None:
        return [{"check": "prc_disclaimer", "source": func_path,
                 "reason": f"{func_path} not found"}]
    for calc_type in calc_types:
        m = re.search(
            rf"{re.escape(calc_type)}[\s\S]{{0,800}}?(?:recommendations|narrative)\s*=",
            content, re.IGNORECASE
        )
        if not m:
            continue
        block = content[m.start():m.start() + 1200]
        if not re.search(r"PRC-licensed|sign and seal|sign & seal|sign.*seal", block, re.IGNORECASE):
            issues.append({"check": "prc_disclaimer", "calc_type": calc_type, "skip": True,
                           "reason": (f"Calc '{calc_type}' has no 'PRC-licensed' or 'sign and seal' "
                                      f"requirement in its recommendation text — workers may submit "
                                      f"AI-generated reports to regulators without licensed sign-off")})
    return issues


# ── Layer 2: Widget transparency ──────────────────────────────────────────────

def check_floating_ai_disclaimer(page):
    """The floating widget system prompt must explicitly state it has NO access
    to the worker's work records — without this, workers may trust fabricated 'data'."""
    content = read_file(page)
    if content is None:
        return [{"check": "floating_ai_disclaimer", "page": page,
                 "reason": f"{page} not found"}]
    if not re.search(
        r"NOT connected.*(?:database|work history|records)"
        r"|no access.*(?:records|history|database)"
        r"|don.t have access.*records",
        content, re.IGNORECASE
    ):
        return [{"check": "floating_ai_disclaimer", "page": page,
                 "reason": (f"{page} system prompt does not state that the floating AI has "
                            f"no access to work records — workers may trust fabricated data")}]
    return []


def check_assistant_scope(page):
    """The assistant.html system prompt must limit the AI to ONLY reference the
    records shown in the prompt — not claim to know about all records ever."""
    content = read_file(page)
    if content is None:
        return [{"check": "assistant_scope", "page": page,
                 "reason": f"{page} not found"}]
    if not re.search(
        r"ONLY reference records|only.*reference.*listed|only.*records.*listed"
        r"|explicitly listed below|records that are explicitly",
        content, re.IGNORECASE
    ):
        return [{"check": "assistant_scope", "page": page,
                 "reason": (f"{page} system prompt does not limit the AI to only the records "
                            f"shown — AI may claim to know about records outside those sent")}]
    return []


# ── Layer 3: AI identity clarity ─────────────────────────────────────────────

def check_narrative_prompt_ai_identity(func_path):
    """
    The engineering-calc-agent narrative generation prompt says 'You are a licensed
    Mechanical Engineer in the Philippines' — this frames the AI as a human licensed
    professional, not as an AI assistant. A worker reading the generated narrative
    cannot distinguish AI-written prose from a human engineer's professional opinion.

    The prompt should identify the AI as an AI assistant helping interpret engineering
    calculation results, not as a licensed human engineer. The PRC sign-off check
    (L1) guards the PDF output, but the source prompt itself misrepresents AI as human.

    Correct framing: 'You are an AI assistant helping write an engineering report
    narrative based on calculation results. These results are from a verified Python
    calculation engine, not AI computation.'
    Reported as WARN — the PDF has narrative-block visual distinction as a guard.
    """
    content = read_file(func_path)
    if content is None:
        return []
    # Find the narrative generation prompt
    m = re.search(r"const prompt\s*=\s*`You are a licensed", content)
    if not m:
        return []   # Pattern changed or not found — no issue
    # Check if the prompt clarifies AI identity near the framing statement
    block = content[m.start():m.start() + 600]
    has_ai_clarification = bool(re.search(
        r"AI|artificial intelligence|language model|generated by|not a human",
        block, re.IGNORECASE
    ))
    if not has_ai_clarification:
        return [{"check": "narrative_prompt_ai_identity", "source": func_path,
                 "skip": True,
                 "reason": (f"engineering-calc-agent narrative prompt says 'You are a licensed "
                            f"Mechanical Engineer' without clarifying this is AI-generated text — "
                            f"workers and regulators cannot tell if the narrative was written by "
                            f"a human engineer or AI; add 'AI-generated narrative' framing to the prompt")}]
    return []


def check_ai_label_per_message(page):
    """
    assistant.html AI response bubbles use class='bubble-assistant' for visual
    distinction (different color) but have no explicit 'AI' badge or label per
    message. The page has 'Powered by WorkHive AI' only in the sidebar footer —
    a worker scrolling through a long conversation history cannot easily identify
    which messages are AI-generated without reading the color context.

    The floating-ai.js correctly shows 'WorkHive AI' in the persistent panel header.
    The full assistant.html should similarly include a persistent AI attribution
    label near or inside the chat message area, not only in the sidebar footer.
    Reported as WARN — visual styling provides partial attribution.
    """
    content = read_file(page)
    if content is None:
        return []
    # Check if AI messages have an explicit label inside the bubble or near the chat area
    has_per_message_label = bool(re.search(
        r'bubble-assistant[^`]*WorkHive AI'
        r'|addMessage.*assistant.*AI'
        r'|ai-badge\|data-sender.*ai',
        content, re.IGNORECASE | re.DOTALL
    ))
    # Check if there's a persistent label near the chat container (not just footer)
    chat_area = re.search(r'id=["\']chat-messages["\']', content)
    has_chat_area_label = False
    if chat_area:
        # Look for AI attribution within 500 chars before the chat container
        nearby = content[max(0, chat_area.start() - 500):chat_area.start()]
        has_chat_area_label = bool(re.search(r"WorkHive AI|AI Assistant", nearby, re.IGNORECASE))
    if not has_per_message_label and not has_chat_area_label:
        return [{"check": "ai_label_per_message", "page": page, "skip": True,
                 "reason": (f"{page} AI response bubbles (bubble-assistant) have no explicit "
                            f"'AI' label near the chat area — 'Powered by WorkHive AI' only "
                            f"appears in the sidebar footer; add a persistent AI attribution "
                            f"label near the chat message container so workers always know "
                            f"they're reading AI-generated responses")}]
    return []


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "narrative_class",
    "prc_disclaimer",
    "floating_ai_disclaimer",
    "assistant_scope",
    "narrative_prompt_ai_identity",
    "ai_label_per_message",
]

CHECK_LABELS = {
    "narrative_class":             "L1  AI narrative sections use class='narrative-block'",
    "prc_disclaimer":              "L1  Safety-critical calcs require PRC sign-off in recommendations  [WARN]",
    "floating_ai_disclaimer":      "L2  Floating AI states it is not connected to work history",
    "assistant_scope":             "L2  Assistant limits itself to only the records shown",
    "narrative_prompt_ai_identity":"L3  Narrative prompt identifies AI as AI, not licensed engineer  [WARN]",
    "ai_label_per_message":        "L3  Assistant chat area has persistent AI attribution label  [WARN]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nAI Output Attribution Validator (3-layer)"))
    print("=" * 55)

    all_issues = []
    all_issues += check_narrative_class(ENGINEERING_PAGE)
    all_issues += check_prc_disclaimer(CALC_AGENT, SAFETY_CRITICAL_TYPES)
    all_issues += check_floating_ai_disclaimer(FLOATING_AI)
    all_issues += check_assistant_scope(ASSISTANT_PAGE)
    all_issues += check_narrative_prompt_ai_identity(CALC_AGENT)
    all_issues += check_ai_label_per_message(ASSISTANT_PAGE)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "ai_attribution",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("ai_attribution_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
