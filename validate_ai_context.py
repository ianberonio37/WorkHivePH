"""
AI Context Quality Validator — WorkHive Platform
=================================================
The AI assistant (floating-ai.js) answers questions based entirely on the
context baked into it. Stale facts, thin descriptions, or missing features
mean wrong or useless answers to workers — silently, with no error.

This validator catches those problems before they reach users.

Checks:
  1. Stale numeric facts     — hint numbers must match the real platform state
  2. PLATFORM TOOLS richness — each tool description must be >= MIN_WORDS words
  3. Engineering-design      — must mention BOM/SOW, diagrams, and standards
  4. Hint quality            — page-specific hints must be >= MIN_HINT_WORDS words

Usage:  python validate_ai_context.py
Output: ai_context_report.json
"""
import re, json, sys

FLOAT_JS   = "floating-ai.js"
MIN_WORDS  = 15   # minimum words per PLATFORM TOOLS tool description
MIN_HINT   = 12   # minimum words per page-specific hint in detectPageContext()

CORRECT_CALC_COUNT = 46   # current number of calc types in engineering-design.html


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def word_count(text):
    return len(text.split())


# ── Check 1: Stale numeric facts in detectPageContext hints ───────────────────

def check_stale_hints(content, page):
    """
    Page hints in detectPageContext() must not contain outdated numbers.
    If the hint says '36 calc types' but the platform has 46, every worker
    on that page gets wrong information from the AI.
    """
    issues = []
    if not content:
        return [{"page": page, "reason": f"{page} not found"}]

    # Find the engineering-design hint
    m = re.search(
        r'path\.includes\([\'"]engineering-design[\'"][^}]+hint:\s*[\'"]([^\'"]+)[\'"]',
        content
    )
    if not m:
        return []

    hint_text = m.group(1)
    count_m = re.search(r"(\d+)\s*calc\s*type", hint_text, re.IGNORECASE)
    if count_m:
        found = int(count_m.group(1))
        if found != CORRECT_CALC_COUNT:
            issues.append({
                "page":     page,
                "found":    found,
                "expected": CORRECT_CALC_COUNT,
                "reason": (
                    f"engineering-design hint says '{found} calc types' but platform "
                    f"has {CORRECT_CALC_COUNT} — workers on this page get a wrong count "
                    f"from the AI"
                ),
            })
    return issues


# ── Check 2: PLATFORM TOOLS description richness ─────────────────────────────

def check_platform_tools_richness(content, page):
    """
    Each tool entry in PLATFORM TOOLS must have enough words for the AI
    to answer questions about it. A short description = thin AI knowledge.
    Example of too-thin: 'Day Planner: Plan your day.' (5 words)
    Example of good:     'Day Planner: DILO/WILO multi-resolution scheduler...' (30+ words)
    """
    issues = []
    if not content:
        return [{"page": page, "reason": f"{page} not found"}]

    pt_start = content.find("PLATFORM TOOLS")
    if pt_start == -1:
        return [{"page": page, "reason": "PLATFORM TOOLS section not found in floating-ai.js"}]
    pt_block = content[pt_start:pt_start + 3000]

    entries = re.findall(r"^- ([^\n]+)", pt_block, re.MULTILINE)
    for entry in entries:
        if "retired" in entry.lower():
            continue   # retired entries are intentionally short
        wc = word_count(entry)
        if wc < MIN_WORDS:
            tool_name = entry.split("(")[0].strip().split(":")[0].strip()
            issues.append({
                "page":       page,
                "tool":       tool_name,
                "word_count": wc,
                "minimum":    MIN_WORDS,
                "reason": (
                    f"'{tool_name}' PLATFORM TOOLS description has only {wc} words "
                    f"(minimum {MIN_WORDS}) — AI has too little context to answer "
                    f"questions about this tool"
                ),
            })
    return issues


# ── Check 3: Engineering-design context completeness ─────────────────────────

def check_engineering_design_context(content, page):
    """
    The engineering-design entry in PLATFORM TOOLS must mention the platform's
    key output features. If 'diagram' is missing, the AI won't tell users
    they can generate drawings from their calc results.
    """
    issues = []
    if not content:
        return [{"page": page, "reason": f"{page} not found"}]

    pt_start = content.find("PLATFORM TOOLS")
    if pt_start == -1:
        return []
    pt_block = content[pt_start:pt_start + 3000]

    ed_m = re.search(
        r"Engineering Design Calculator[\s\S]{0,500}?(?=\n-|\Z)",
        pt_block
    )
    if not ed_m:
        return [{"page": page, "reason": "Engineering Design Calculator not found in PLATFORM TOOLS"}]

    ed_text = ed_m.group(0)

    required = {
        "BOM / Bill of Materials":  ["BOM", "Bill of Materials"],
        "SOW / Scope of Works":     ["SOW", "Scope of Works"],
        "diagram / drawing output": ["diagram", "drawing", "Drawing"],
        "Philippine standard":      ["PEC", "ASHRAE", "NFPA", "PSME", "NSCP"],
    }

    for concept, terms in required.items():
        if not any(t in ed_text for t in terms):
            issues.append({
                "page":    page,
                "missing": concept,
                "reason": (
                    f"Engineering Design PLATFORM TOOLS entry is missing '{concept}' — "
                    f"AI won't mention this feature when workers ask about the calculator"
                ),
            })
    return issues


# ── Check 4: Page-specific hint minimum quality ───────────────────────────────

def check_hint_quality(content, page):
    """
    Each page hint in detectPageContext() tells the AI what the worker is
    likely asking about on that specific page. Too-short hints force the AI
    to give generic responses instead of page-relevant help.
    """
    issues = []
    if not content:
        return [{"page": page, "reason": f"{page} not found"}]

    hints = re.findall(
        r"path\.includes\(['\"]([^'\"]+)['\"][^}]+hint:\s*['\"]([^'\"]+)['\"]",
        content
    )

    for tool, hint_text in hints:
        wc = word_count(hint_text)
        if wc < MIN_HINT:
            issues.append({
                "page":       page,
                "tool":       tool,
                "word_count": wc,
                "minimum":    MIN_HINT,
                "reason": (
                    f"'{tool}' hint has only {wc} words (minimum {MIN_HINT}) — "
                    f"AI gets minimal context when the worker is on this page"
                ),
            })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("AI Context Quality Validator")
print("=" * 70)

float_js   = read_file(FLOAT_JS)
fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        "[1] Stale numeric facts in detectPageContext hints",
        check_stale_hints(float_js, FLOAT_JS),
    ),
    (
        "[2] PLATFORM TOOLS description richness (>= 15 words each)",
        check_platform_tools_richness(float_js, FLOAT_JS),
    ),
    (
        "[3] Engineering-design completeness (BOM / SOW / diagrams / standards)",
        check_engineering_design_context(float_js, FLOAT_JS),
    ),
    (
        "[4] Page-specific hint quality (>= 12 words each)",
        check_hint_quality(float_js, FLOAT_JS),
    ),
]

for label, issues in checks:
    print(f"\n{label}\n")
    if not issues:
        print("  PASS")
    else:
        for iss in issues:
            print(f"  FAIL  {iss.get('page', '?')}")
            print(f"        {iss['reason']}")
        fail_count += len(issues)
    report[label] = issues

print(f"\n{'=' * 70}")
print(f"Result: {fail_count} FAIL  {warn_count} WARN")

with open("ai_context_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved ai_context_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll AI context checks PASS.")
