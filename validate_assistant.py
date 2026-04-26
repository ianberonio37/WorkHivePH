"""
Assistant Validator — WorkHive Platform

Static analysis of floating-ai.js (the AI widget on every page) and assistant.html
(the full AI assistant page) covering:

  1. Page context coverage   — every live tool page has a path.includes() entry in floating-ai.js
  2. Platform tools list     — every live tool page mentioned in the PLATFORM TOOLS system prompt
  3. Skill Matrix disciplines — discipline names in system prompt match actual DISCIPLINES constant
  4. Retired page status     — parts-tracker noted as retired, not as active tool
  5. Cal count accuracy      — engineering-design.html description mentions correct calc count
  6. No live links to retired pages — system prompt doesn't direct users to retired pages

Usage:  python validate_assistant.py
Output: assistant_report.json
"""
import re, json, sys

FLOAT_JS       = "floating-ai.js"
ASSISTANT_PAGE = "assistant.html"
CONTENT_FILE   = "skill-content.js"

# Live tool pages (non-home, non-utility) that must have page context entries
LIVE_TOOL_PAGES = [
    "logbook",
    "assistant",
    "dayplanner",
    "pm-scheduler",
    "hive",
    "inventory",
    "skillmatrix",
    "engineering-design",
]

# Retired pages — must NOT be listed as active tools
RETIRED_PAGES = ["parts-tracker", "checklist"]


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def extract_array(content, var_name):
    m = re.search(
        rf"(?:const|var|let)\s+{re.escape(var_name)}\s*=\s*\[([^\]]+)\]",
        content, re.DOTALL
    )
    if not m:
        return []
    return re.findall(r"['\"]([^'\"]+)['\"]", m.group(1))


# ── Check 1: path.includes() coverage for all live pages ─────────────────────
def check_page_context_entries(float_content, page):
    """Every live tool page must have a path.includes('page-name') entry."""
    issues = []
    if not float_content:
        return [{"page": page, "reason": f"{page} not found"}]

    for tool in LIVE_TOOL_PAGES:
        pattern = rf"path\.includes\(['\"]({re.escape(tool)})['\"]"
        if not re.search(pattern, float_content):
            issues.append({
                "page": page, "tool": tool,
                "reason": f"path.includes('{tool}') missing — users on {tool}.html get generic AI hints instead of page-specific help",
            })
    return issues


# ── Check 2: PLATFORM TOOLS mentions all live pages ───────────────────────────
def check_platform_tools_list(float_content, page):
    """
    The PLATFORM TOOLS section in the system prompt must mention every live page.
    If a page is missing, the AI can't answer 'where do I find X?' correctly.
    """
    issues = []
    if not float_content:
        return [{"page": page, "reason": f"{page} not found"}]

    # Find the PLATFORM TOOLS block
    tools_m = re.search(r"PLATFORM TOOLS[\s\S]{0,3000}?^You handle", float_content, re.MULTILINE)
    if not tools_m:
        # Try without the ending anchor
        tools_block = float_content[float_content.find("PLATFORM TOOLS"):float_content.find("PLATFORM TOOLS") + 2000]
    else:
        tools_block = tools_m.group(0)

    for tool in LIVE_TOOL_PAGES:
        # Check page filename or well-known alias mentioned
        aliases = {
            "engineering-design": ["engineering-design", "Engineering Design", "Engineering Calculator"],
            "pm-scheduler":       ["pm-scheduler", "PM Scheduler"],
            "skillmatrix":        ["skillmatrix", "Skill Matrix"],
        }
        checks = aliases.get(tool, [tool])
        if not any(c in tools_block for c in checks):
            issues.append({
                "page": page, "tool": tool,
                "reason": f"'{tool}' not mentioned in PLATFORM TOOLS — AI cannot direct users to this page",
            })
    return issues


# ── Check 3: Skill Matrix discipline names match actual DISCIPLINES ────────────
def check_skillmatrix_disciplines(float_content, skill_content, page):
    """
    The discipline names mentioned in the floating AI system prompt must match
    the actual DISCIPLINES array in skill-content.js.
    """
    issues = []
    if not float_content or not skill_content:
        return []

    actual_disciplines = extract_array(skill_content, "DISCIPLINES")
    if not actual_disciplines:
        return [{"page": CONTENT_FILE, "reason": "DISCIPLINES not found in skill-content.js"}]

    # Find the Skill Matrix entry specifically in the PLATFORM TOOLS block
    # (not in the detectPageContext hint which doesn't list disciplines)
    tools_start = float_content.find("PLATFORM TOOLS")
    if tools_start == -1:
        return [{"page": page, "reason": "PLATFORM TOOLS section not found"}]
    tools_block = float_content[tools_start:tools_start + 3000]

    sm_pat = re.search(r"[Ss]kill [Mm]atrix[\s\S]{0,400}?(?=\n-|\Z)", tools_block)
    if not sm_pat:
        return [{"page": page, "reason": "Skill Matrix description not found in PLATFORM TOOLS section"}]

    sm_line = sm_pat.group(0)

    for disc in actual_disciplines:
        if disc not in sm_line:
            issues.append({
                "page": page, "discipline": disc,
                "actual_disciplines": actual_disciplines,
                "reason": f"Skill Matrix description does not mention actual discipline '{disc}' — AI will give wrong answer about available disciplines",
            })
    return issues


# ── Check 4: Retired pages not listed as active ───────────────────────────────
def check_retired_pages(float_content, page):
    """
    Retired pages (parts-tracker, checklist) must be marked as retired,
    not as active tools that users are directed to.
    """
    issues = []
    if not float_content:
        return []

    for retired in RETIRED_PAGES:
        # Look specifically for .html reference or a tool listing (not generic word use)
        # e.g. "checklist.html" or "- Checklist (" but NOT "scope checklists"
        mentions = re.findall(
            rf".{{0,50}}{re.escape(retired)}\.html.{{0,100}}|"
            rf".{{0,10}}-\s*{re.escape(retired).title()}\s*[(\-].{{0,100}}",
            float_content, re.IGNORECASE
        )
        for mention in mentions:
            is_retired_note = any(w in mention.lower() for w in
                                  ["retired", "removed", "no longer", "deprecated", "replaced"])
            if not is_retired_note:
                issues.append({
                    "page": page, "retired_page": retired,
                    "context": mention.strip(),
                    "reason": f"'{retired}.html' referenced as an active tool — AI may direct users to a non-existent page",
                })
    return issues


# ── Check 5: Engineering design calc count in assistant.html ──────────────────
def check_calc_count_accuracy(assistant_content, page):
    """
    assistant.html platform context must reference 46 calculation types
    (not the old count of 36). Stale count gives wrong information.
    """
    issues = []
    if not assistant_content:
        return [{"page": page, "reason": f"{page} not found"}]

    # Find calc count mention near engineering-design description
    m = re.search(
        r"engineering.design[\s\S]{0,500}?(\d+)\s*calc(?:ulation)?\s*type",
        assistant_content, re.IGNORECASE
    )
    if not m:
        issues.append({
            "page": page,
            "reason": "Calc type count not found in engineering-design description in assistant.html",
        })
        return issues

    count = int(m.group(1))
    if count < 46:
        issues.append({
            "page": page, "found_count": count,
            "reason": f"assistant.html says '{count} calculation types' but platform now has 46 — stale count gives wrong information",
        })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("Assistant Validator")
print("=" * 70)

float_js    = read_file(FLOAT_JS)
assistant   = read_file(ASSISTANT_PAGE)
skill_cont  = read_file(CONTENT_FILE)

fail_count = 0
warn_count = 0
report     = {}

checks = [
    ("[1] Page context entries (path.includes) for all live tools",
     check_page_context_entries(float_js, FLOAT_JS)),
    ("[2] PLATFORM TOOLS mentions all live pages",
     check_platform_tools_list(float_js, FLOAT_JS)),
    ("[3] Skill Matrix discipline names match actual DISCIPLINES",
     check_skillmatrix_disciplines(float_js, skill_cont, FLOAT_JS)),
    ("[4] Retired pages not listed as active",
     check_retired_pages(float_js, FLOAT_JS)),
    ("[5] Engineering design calc count is current (46)",
     check_calc_count_accuracy(assistant, ASSISTANT_PAGE)),
]

for label, issues in checks:
    print(f"\n{label}\n")
    if not issues:
        print("  PASS")
    else:
        for iss in issues:
            print(f"  FAIL  {iss.get('page', '?')}")
            print(f"        {iss['reason']}")
            if "context" in iss:
                print(f"        context: ...{iss['context']}...")
            fail_count += 1
    report[label] = issues

print(f"\n{'=' * 70}")
print(f"Result: {fail_count} FAIL  {warn_count} WARN")

with open("assistant_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved assistant_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll assistant checks PASS.")
