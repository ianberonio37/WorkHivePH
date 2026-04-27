"""
AI Prompt Regression Validator — WorkHive Platform
===================================================
WorkHive has two AI surfaces that both describe the platform:
  1. floating-ai.js  — the floating widget on every page
  2. assistant.html  — the full work assistant page

As the platform grows (new tools, renamed disciplines, updated calc counts),
these prompts will drift apart. A worker on the logbook page gets a different
answer about what WorkHive can do than a worker using the full assistant.
This validator catches that drift before it reaches users.

Four things checked:

  1. Skill Matrix discipline names match across surfaces
     — The discipline names in both prompts must match the actual DISCIPLINES
       constant in skill-content.js. Stale discipline names cause the AI to
       give wrong answers about what competencies are tracked.

  2. Tool list consistent across both surfaces
     — Every tool active in floating-ai.js PLATFORM TOOLS must also be
       mentioned in assistant.html PLATFORM CONTEXT. A tool added to one
       but not the other means split answers about what WorkHive can do.

  3. No draft artifacts in either prompt
     — System prompts must not contain TODO, FIXME, [PLACEHOLDER], or
       "your company name". These are development leftovers that expose
       the AI's incompleteness to workers asking real questions.

  4. Engineering calc count consistent across surfaces
     — Both prompts must agree on the number of calc types. The correct
       count is 46. A mismatch means the AI gives different answers to
       "how many calc types does the Engineering Design Calculator have?"
       depending on which surface the worker uses.

Usage:  python validate_ai_regression.py
Output: ai_regression_report.json
"""
import re, json, sys

FLOAT_JS       = "floating-ai.js"
ASSISTANT_HTML = "assistant.html"
SKILL_CONTENT  = "skill-content.js"

CORRECT_CALC_COUNT = 46

DRAFT_ARTIFACTS = [
    "TODO", "FIXME", "[PLACEHOLDER]", "[INSERT",
    "your company name", "example.com", "your-company",
]


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def extract_disciplines(skill_content):
    """Extract the DISCIPLINES array from skill-content.js."""
    m = re.search(
        r"(?:const|var|let)\s+DISCIPLINES\s*=\s*\[([^\]]+)\]",
        skill_content, re.DOTALL
    )
    if not m:
        return []
    return re.findall(r"['\"]([^'\"]+)['\"]", m.group(1))


def extract_prompt_block(content, markers):
    """Extract a block of text between two markers."""
    for start_marker in markers["start"]:
        idx = content.find(start_marker)
        if idx != -1:
            end_idx = len(content)
            for end_marker in markers.get("end", []):
                ei = content.find(end_marker, idx + len(start_marker))
                if ei != -1:
                    end_idx = min(end_idx, ei)
            return content[idx:end_idx]
    return ""


# ── Check 1: Skill Matrix disciplines consistent across surfaces ──────────────

def check_discipline_consistency(float_content, assistant_content, skill_content):
    """
    The discipline names in both AI surfaces must match the actual DISCIPLINES
    constant in skill-content.js. These names are used by the AI to answer
    questions about what competencies are tracked in the Skill Matrix.

    If floating-ai.js says "Facilities Management" but assistant.html still
    says "HVAC", workers on different pages get contradictory answers.
    """
    issues = []
    if not skill_content:
        return [{"page": SKILL_CONTENT, "reason": f"{SKILL_CONTENT} not found"}]

    disciplines = extract_disciplines(skill_content)
    if not disciplines:
        return [{"page": SKILL_CONTENT, "reason": "DISCIPLINES array not found in skill-content.js"}]

    surfaces = {
        FLOAT_JS:       float_content or "",
        ASSISTANT_HTML: assistant_content or "",
    }

    for page, content in surfaces.items():
        if not content:
            issues.append({"page": page, "reason": f"{page} not found"})
            continue
        for disc in disciplines:
            if disc not in content:
                issues.append({
                    "page":       page,
                    "discipline": disc,
                    "reason": (
                        f"{page} does not mention actual Skill Matrix discipline "
                        f"'{disc}' — AI will give wrong answers about available "
                        f"disciplines to workers using this surface"
                    ),
                })
    return issues


# ── Check 2: Tool list consistent across both surfaces ───────────────────────

def check_tool_consistency(float_content, assistant_content):
    """
    Every active tool in floating-ai.js PLATFORM TOOLS must also be mentioned
    in assistant.html PLATFORM CONTEXT. Workers using the full assistant page
    must get the same platform knowledge as the floating widget.

    Active tools are detected as lines starting with "- ToolName (filename.html)"
    in the floating-ai.js PLATFORM TOOLS section.
    Retired tools (containing "Retired") are excluded.
    """
    issues = []
    if not float_content or not assistant_content:
        return issues

    # Extract PLATFORM TOOLS block from floating-ai.js
    pt_start = float_content.find("PLATFORM TOOLS")
    if pt_start == -1:
        return [{"page": FLOAT_JS, "reason": "PLATFORM TOOLS section not found"}]
    pt_block = float_content[pt_start:pt_start + 3000]

    # Extract active tool filenames from the block
    active_tools = []
    for m in re.finditer(r"- [^(]+\((\w[\w.-]+\.html)\)", pt_block):
        filename = m.group(1)
        # Get the surrounding text to check if retired
        line_start = pt_block.rfind("\n", 0, m.start()) + 1
        line_end   = pt_block.find("\n", m.end())
        line_text  = pt_block[line_start:line_end if line_end != -1 else len(pt_block)]
        if "retired" not in line_text.lower():
            active_tools.append(filename)

    # Check each active tool appears in assistant.html
    for tool_file in active_tools:
        if tool_file not in assistant_content:
            issues.append({
                "page":  ASSISTANT_HTML,
                "tool":  tool_file,
                "reason": (
                    f"{ASSISTANT_HTML} does not mention '{tool_file}' — "
                    f"this tool is in floating-ai.js PLATFORM TOOLS but missing "
                    f"from the full assistant page context"
                ),
            })
    return issues


# ── Check 3: No draft artifacts in either prompt ─────────────────────────────

def check_draft_artifacts(pages_content):
    """
    System prompts that ship with TODO, FIXME, or placeholder text expose
    the AI's incompleteness to workers. When a worker asks a question that
    touches the placeholder section, the AI returns a confused or broken answer.
    """
    issues = []
    for page, content in pages_content.items():
        if not content:
            continue
        for artifact in DRAFT_ARTIFACTS:
            if artifact in content:
                issues.append({
                    "page":     page,
                    "artifact": artifact,
                    "reason": (
                        f"{page} system prompt contains draft artifact '{artifact}' — "
                        f"remove or replace before shipping"
                    ),
                })
    return issues


# ── Check 4: Engineering calc count consistent across surfaces ────────────────

def check_calc_count_consistency(pages_content):
    """
    Both AI surfaces must agree on the number of engineering calc types.
    A worker on the logbook page asking 'how many calcs does the engineering
    calculator have?' should get the same answer as one using the full assistant.
    """
    issues = []
    for page, content in pages_content.items():
        if not content:
            continue
        m = re.search(r"(\d+)\s*calc(?:ulation)?\s*type", content, re.IGNORECASE)
        if not m:
            # Not all surfaces need to mention calc count
            continue
        count = int(m.group(1))
        if count != CORRECT_CALC_COUNT:
            issues.append({
                "page":     page,
                "found":    count,
                "expected": CORRECT_CALC_COUNT,
                "reason": (
                    f"{page} says '{count} calc types' but the platform has "
                    f"{CORRECT_CALC_COUNT} — divergent counts give inconsistent "
                    f"answers across AI surfaces"
                ),
            })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("AI Prompt Regression Validator")
print("=" * 70)

float_js      = read_file(FLOAT_JS)
assistant     = read_file(ASSISTANT_HTML)
skill_content = read_file(SKILL_CONTENT)

fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        "[1] Skill Matrix discipline names match across all AI surfaces",
        check_discipline_consistency(float_js, assistant, skill_content),
        "FAIL",
    ),
    (
        "[2] Tool list consistent between floating-ai.js and assistant.html",
        check_tool_consistency(float_js, assistant),
        "FAIL",
    ),
    (
        "[3] No draft artifacts (TODO / FIXME / placeholder) in prompts",
        check_draft_artifacts({FLOAT_JS: float_js, ASSISTANT_HTML: assistant}),
        "FAIL",
    ),
    (
        f"[4] Engineering calc count consistent across surfaces ({CORRECT_CALC_COUNT})",
        check_calc_count_consistency({FLOAT_JS: float_js, ASSISTANT_HTML: assistant}),
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

with open("ai_regression_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved ai_regression_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll AI regression checks PASS.")
