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

From the Gartner "Model Validator", "AI Ethicist", and "AI Risk/Governance
Specialist" roles. These are the humans who validate AI output quality and
ensure users know when they're reading AI-generated content.

Four things checked:

  1. AI narrative sections use the narrative-block CSS class
     — Report renderers must wrap AI-generated narrative text in a
       <div class="narrative-block"> container. This visually distinguishes
       AI-generated prose (objective, assumptions, recommendations) from
       deterministic calculation results (numbers, tables, formulas).
       Without this class, AI content is indistinguishable from verified
       engineering data in printed reports.

  2. Safety-critical calc recommendations require PRC sign-off
     — For regulated engineering work (Electrical, Fire Protection,
       Mechanical design), the AI-generated recommendation text in
       engineering-calc-agent must include a statement requiring a
       PRC-licensed professional engineer to sign and seal the document.
       This prevents workers from treating the AI narrative as sufficient
       for building permit submission without licensed engineer sign-off.

  3. Floating AI explicitly states it is not connected to work history
     — The floating widget system prompt must include the statement that
       it has NO access to the worker's logbook records, inventory, or
       work history. Without this, workers may believe the widget is
       answering from their actual data and make decisions based on
       fabricated "records" the widget invents to seem helpful.

  4. Full assistant states which records it has access to
     — The assistant.html system prompt must explicitly limit itself to
       only the records shown in the prompt. Workers must not be misled
       into thinking the AI assistant can see ALL their records — only
       the 10 most recent entries per category are included.

Usage:  python validate_ai_attribution.py
Output: ai_attribution_report.json
"""
import re, json, sys, os

ENGINEERING_PAGE  = "engineering-design.html"
FLOATING_AI       = "floating-ai.js"
ASSISTANT_PAGE    = "assistant.html"
CALC_AGENT        = os.path.join("supabase", "functions",
                                 "engineering-calc-agent", "index.ts")

# CSS class used to visually mark AI-generated narrative blocks in reports
NARRATIVE_CSS_CLASS = "narrative-block"

# Safety-critical calc types that require PRC sign-off in recommendations
SAFETY_CRITICAL_TYPES = [
    "Lightning Protection System",   # Electrical / IEC 62305 / BFP
    "Earthing / Grounding",          # Electrical / PEC / IEEE 80
    "Short Circuit",                 # Electrical / fault interrupting capacity
    "Fire Pump",                     # Fire Protection / NFPA 20 / BFP
    "Fire Sprinkler",                # Fire Protection / NFPA 13 / BFP
    "Generator Sizing",              # Electrical / ISO 8528 / PEC
    "Wire Sizing",                   # Electrical / PEC 2017
    "Shaft Design",                  # Mechanical / ASME
    "Elevator Traffic",              # Mechanical / ASME A17.1 / DOLE
]


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


# ── Check 1: AI narrative sections use narrative-block CSS class ──────────────

def check_narrative_class(page):
    """
    AI-generated narrative content in engineering reports must use the
    class="narrative-block" container. This creates a visual distinction
    between AI prose and verified engineering numbers.

    Without this class, a printed BOM+SOW report contains AI-generated
    text that looks identical to the deterministic calculation output —
    a worker or supervisor cannot tell which parts are AI-generated and
    which parts are results of verified formulas.
    """
    issues = []
    content = read_file(page)
    if content is None:
        return [{"page": page, "reason": f"{page} not found"}]

    count = len(re.findall(rf'class="{NARRATIVE_CSS_CLASS}"', content))
    if count == 0:
        issues.append({
            "page":  page,
            "reason": (
                f"{page} has no elements with class='{NARRATIVE_CSS_CLASS}' — "
                f"AI-generated narrative sections are visually indistinguishable "
                f"from deterministic engineering results in printed reports"
            ),
        })
    return issues


# ── Check 2: Safety-critical cals include PRC sign-off requirement ────────────

def check_prc_disclaimer(func_path, calc_types):
    """
    For regulated engineering work, AI-generated recommendation text must
    explicitly require a PRC-licensed professional engineer to sign and seal
    the document before it can be used for building permit submission.

    Without this, a field technician could print the AI calc report and
    submit it to the BFP or LGU building official as if it were a licensed
    engineer's sealed document — this is both illegal and dangerous.

    The check looks for 'PRC-licensed' or 'sign and seal' within the
    recommendations text for each safety-critical calc type.
    """
    issues = []
    content = read_file(func_path)
    if content is None:
        return [{"source": func_path, "reason": f"{func_path} not found"}]

    for calc_type in calc_types:
        # Find the code block handling this calc type
        m = re.search(
            rf"{re.escape(calc_type)}[\s\S]{{0,800}}?(?:recommendations|narrative)\s*=",
            content, re.IGNORECASE
        )
        if not m:
            continue

        block = content[m.start():m.start() + 1200]
        has_prc = bool(re.search(
            r"PRC-licensed|sign and seal|sign & seal|sign.*seal",
            block, re.IGNORECASE
        ))
        if not has_prc:
            issues.append({
                "calc_type": calc_type,
                "reason": (
                    f"Calc type '{calc_type}' in {func_path} has no "
                    f"'PRC-licensed' or 'sign and seal' requirement in its "
                    f"recommendation text — workers may submit this AI-generated "
                    f"report to regulators without licensed engineer sign-off"
                ),
            })
    return issues


# ── Check 3: Floating AI states it is not connected to work history ───────────

def check_floating_ai_disclaimer(page):
    """
    The floating widget system prompt must explicitly state that it has
    NO access to the worker's actual records. This prevents two failure modes:
    1. Workers trust answers about 'their last job' when the AI is hallucinating
    2. Workers believe the widget is smarter than it is and over-rely on it

    Required statement:
      'NOT connected to any database or work history'
      or equivalent phrasing
    """
    issues = []
    content = read_file(page)
    if content is None:
        return [{"page": page, "reason": f"{page} not found"}]

    has_disclaimer = bool(re.search(
        r"NOT connected.*(?:database|work history|records)"
        r"|no access.*(?:records|history|database)"
        r"|don.t have access.*records",
        content, re.IGNORECASE
    ))
    if not has_disclaimer:
        issues.append({
            "page": page,
            "reason": (
                f"{page} system prompt does not explicitly state that the "
                f"floating AI has no access to work records — workers may "
                f"believe AI answers are based on their actual logbook data "
                f"and make maintenance decisions on fabricated information"
            ),
        })
    return issues


# ── Check 4: Full assistant states which records it can access ────────────────

def check_assistant_scope(page):
    """
    The assistant.html sends the worker's last 10 logbook entries to the AI.
    The system prompt must explicitly limit the AI to ONLY reference records
    that are shown in the prompt — not claim to know about all records ever.

    Required statement:
      'ONLY reference records that are explicitly listed'
      or equivalent scope limitation
    """
    issues = []
    content = read_file(page)
    if content is None:
        return [{"page": page, "reason": f"{page} not found"}]

    has_scope_limit = bool(re.search(
        r"ONLY reference records|only.*reference.*listed|only.*records.*listed"
        r"|explicitly listed below|records that are explicitly",
        content, re.IGNORECASE
    ))
    if not has_scope_limit:
        issues.append({
            "page": page,
            "reason": (
                f"{page} system prompt does not limit the AI to only the "
                f"records shown in the prompt — the AI may claim to know about "
                f"records outside the 10 most recent entries that are actually sent"
            ),
        })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("AI Output Attribution Validator")
print("=" * 70)

fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        f"[1] AI narrative sections use class='{NARRATIVE_CSS_CLASS}' in report renderers",
        check_narrative_class(ENGINEERING_PAGE),
        "FAIL",
    ),
    (
        "[2] Safety-critical calc recommendations include PRC sign-off requirement",
        check_prc_disclaimer(CALC_AGENT, SAFETY_CRITICAL_TYPES),
        "WARN",
    ),
    (
        "[3] Floating AI system prompt states it is not connected to work history",
        check_floating_ai_disclaimer(FLOATING_AI),
        "FAIL",
    ),
    (
        "[4] Assistant page system prompt limits AI to only the records shown",
        check_assistant_scope(ASSISTANT_PAGE),
        "FAIL",
    ),
]

for label, issues, severity in checks:
    print(f"\n{label}\n")
    if not issues:
        print("  PASS")
    else:
        for iss in issues:
            print(f"  {severity}  {iss.get('page', iss.get('calc_type', iss.get('source', '?')))}")
            print(f"        {iss['reason']}")
        if severity == "FAIL":
            fail_count += len(issues)
        else:
            warn_count += len(issues)
    report[label] = issues

print(f"\n{'=' * 70}")
print(f"Result: {fail_count} FAIL  {warn_count} WARN")

with open("ai_attribution_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved ai_attribution_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll AI attribution checks PASS.")
