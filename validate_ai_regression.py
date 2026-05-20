"""
AI Prompt Regression Validator — WorkHive Platform
===================================================
WorkHive has two AI surfaces that both describe the platform:
  1. companion-launcher.js  — the floating widget on every page
  2. assistant.html  — the full work assistant page

As the platform grows, these prompts drift apart. A worker on the logbook
page gets a different answer about what WorkHive can do than a worker using
the full assistant. This validator catches that drift before it reaches users.

  Layer 1 — Structural consistency
    1.  Discipline names match          — DISCIPLINES in skill-content.js == both prompts
    2.  Tool list consistent            — all active tools in companion-launcher.js in assistant.html too
    3.  Calc count consistent           — both surfaces agree on engineering calc count (46)

  Layer 2 — Content quality
    4.  No draft artifacts              — no TODO/FIXME/placeholder in either prompt

  Layer 3 — Feature parity (new features must land in both surfaces)
    5.  Analytics feature parity        — OEE, RCM consequence, anomaly in both
    6.  Logbook feature parity          — failure consequence, production output in both

Usage:  python validate_ai_regression.py
Output: ai_regression_report.json
"""
import re, json, sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, extract_js_array, format_result

FLOAT_JS       = "companion-launcher.js"
ASSISTANT_HTML = "assistant.html"
SKILL_CONTENT  = "skill-content.js"

CORRECT_CALC_COUNT = 46

DRAFT_ARTIFACTS = [
    "TODO", "FIXME", "[PLACEHOLDER]", "[INSERT",
    "your company name", "example.com", "your-company",
]

# Feature terms that must appear in BOTH surfaces once added to either one.
# Format: (check_id, surface_anchor, feature_terms, description)
FEATURE_PARITY_CHECKS = [
    (
        "analytics_feature_parity",
        "analytics.html",
        ["OEE", "consequence", "anomaly"],
        "Analytics Engine — new features (OEE, RCM consequence, anomaly detection)",
    ),
    (
        "logbook_feature_parity",
        "logbook.html",
        ["consequence", "production"],
        "Digital Logbook — new fields (failure consequence, production output/OEE)",
    ),
]


def get_platform_tools_block(content):
    # Support both "PLATFORM TOOLS" (companion-launcher.js) and "PLATFORM CONTEXT" (assistant.html)
    for marker in ("PLATFORM TOOLS", "PLATFORM CONTEXT"):
        start = content.find(marker)
        if start != -1:
            return content[start:start + 6000]
    return ""


def get_tool_entry(content, tool_anchor):
    """Extract the paragraph in PLATFORM TOOLS for a given tool keyword."""
    block = get_platform_tools_block(content)
    if not block:
        block = content
    # Search for the tool entry — allow the last entry to have no trailing \n-
    m = re.search(rf"-\s*[^\n]*{re.escape(tool_anchor)}[\s\S]{{0,800}}?(?=\n-|\n\n|\Z)", block, re.IGNORECASE)
    if not m:
        # Fallback: just find the line containing the anchor and grab 600 chars
        m2 = re.search(rf".{{0,5}}{re.escape(tool_anchor)}.{{0,800}}", block, re.IGNORECASE)
        return m2.group(0) if m2 else ""
    return m.group(0)


# ── Layer 1: Structural consistency ──────────────────────────────────────────

def check_discipline_consistency(float_content, assistant_content, skill_content):
    if not skill_content:
        return [{"check": "discipline_names", "page": SKILL_CONTENT,
                 "reason": f"{SKILL_CONTENT} not found"}]
    disciplines = extract_js_array(skill_content, "DISCIPLINES")
    if not disciplines:
        return [{"check": "discipline_names", "page": SKILL_CONTENT,
                 "reason": "DISCIPLINES array not found in skill-content.js"}]
    issues = []
    for page, content in [(FLOAT_JS, float_content), (ASSISTANT_HTML, assistant_content)]:
        if not content:
            issues.append({"check": "discipline_names", "page": page,
                           "reason": f"{page} not found"})
            continue
        for disc in disciplines:
            if disc not in content:
                issues.append({"check": "discipline_names", "page": page,
                               "discipline": disc,
                               "reason": f"{page} missing Skill Matrix discipline '{disc}' — AI gives wrong answers about available disciplines"})
    return issues


def check_tool_consistency(float_content, assistant_content):
    if not float_content or not assistant_content:
        return []
    pt_block = get_platform_tools_block(float_content)
    if not pt_block:
        return [{"check": "tool_consistency", "page": FLOAT_JS,
                 "reason": "PLATFORM TOOLS section not found"}]
    issues = []
    for m in re.finditer(r"- [^(]+\((\w[\w.-]+\.html)\)", pt_block):
        filename = m.group(1)
        line_start = pt_block.rfind("\n", 0, m.start()) + 1
        line_end   = pt_block.find("\n", m.end())
        line_text  = pt_block[line_start:line_end if line_end != -1 else len(pt_block)]
        if "retired" in line_text.lower():
            continue
        if filename not in assistant_content:
            issues.append({"check": "tool_consistency", "page": ASSISTANT_HTML,
                           "tool": filename,
                           "reason": f"{ASSISTANT_HTML} missing '{filename}' — tool is in companion-launcher.js PLATFORM TOOLS but not in full assistant context"})
    return issues


def check_calc_count_consistency(float_content, assistant_content):
    issues = []
    counts = {}
    for page, content in [(FLOAT_JS, float_content), (ASSISTANT_HTML, assistant_content)]:
        if not content:
            continue
        m = re.search(r"(\d+)\s*calc(?:ulation)?\s*type", content, re.IGNORECASE)
        if m:
            counts[page] = int(m.group(1))
    for page, count in counts.items():
        if count != CORRECT_CALC_COUNT:
            issues.append({"check": "calc_count_consistent", "page": page,
                           "found": count, "expected": CORRECT_CALC_COUNT,
                           "reason": f"{page} says '{count} calc types' but platform has {CORRECT_CALC_COUNT} — contradictory AI answers across surfaces"})
    if len(counts) == 2:
        vals = list(counts.values())
        if vals[0] != vals[1]:
            issues.append({"check": "calc_count_consistent",
                           "reason": f"Calc count mismatch: {FLOAT_JS}={counts[FLOAT_JS]}, {ASSISTANT_HTML}={counts[ASSISTANT_HTML]}"})
    return issues


# ── Layer 2: Content quality ──────────────────────────────────────────────────

def check_draft_artifacts(float_content, assistant_content):
    issues = []
    for page, content in [(FLOAT_JS, float_content), (ASSISTANT_HTML, assistant_content)]:
        if not content:
            continue
        for artifact in DRAFT_ARTIFACTS:
            if artifact in content:
                issues.append({"check": "draft_artifacts", "page": page,
                               "artifact": artifact,
                               "reason": f"{page} system prompt contains draft artifact '{artifact}' — remove before shipping"})
    return issues


# ── Layer 3: Feature parity ───────────────────────────────────────────────────

def check_feature_parity(float_content, assistant_content):
    """
    When a new feature is added to a tool description in companion-launcher.js,
    the same feature must appear in assistant.html's description of that tool.
    Otherwise workers get contradictory answers depending on which AI surface
    they use.

    Strategy: for each tool, extract its entry from both surfaces and compare
    the presence of key feature terms. If companion-launcher.js mentions a term but
    assistant.html does not, flag it.
    """
    issues = []
    if not float_content or not assistant_content:
        return issues

    for check_id, tool_anchor, feature_terms, description in FEATURE_PARITY_CHECKS:
        float_entry     = get_tool_entry(float_content, tool_anchor)
        assistant_entry = get_tool_entry(assistant_content, tool_anchor)

        for term in feature_terms:
            in_float     = bool(re.search(re.escape(term), float_entry, re.IGNORECASE))
            in_assistant = bool(re.search(re.escape(term), assistant_entry, re.IGNORECASE))

            if in_float and not in_assistant:
                issues.append({"check": check_id, "page": ASSISTANT_HTML,
                               "term": term, "tool": tool_anchor,
                               "reason": f"{ASSISTANT_HTML} {description}: missing '{term}' — floating widget mentions it but full assistant doesn't, causing contradictory answers"})
            elif in_assistant and not in_float:
                issues.append({"check": check_id, "page": FLOAT_JS,
                               "term": term, "tool": tool_anchor,
                               "reason": f"{FLOAT_JS} {description}: missing '{term}' — full assistant mentions it but widget doesn't"})
    return issues


# ── Layer 4: Tier-S citation in AI surfaces ─────────────────────────────────

def check_tier_s_citations(float_content, assistant_content):
    """Both AI surfaces must mention the metrics they reason about WITH the
    Tier-S standard short_name when those metrics have a registered formula.

    Without this guard, a worker asking 'what does MTBF mean here?' gets the
    name but not the standard — and we can no longer prove the platform's
    answer matches ISO 14224. The audit_ai_prompt_standards.py validator
    already enforces this for edge functions; this layer extends the same
    contract to the two user-facing AI surfaces (floating widget + assistant).

    For each metric → standard mapping derived from canonical/formula_contracts.json
    + canonical/standards.json: if the surface mentions the metric (e.g. 'MTBF',
    'OEE', 'RPN'), it MUST also mention the registered short_name (e.g.
    'ISO 14224', 'ISO 22400', 'IEC 60812'). Otherwise the AI answer drifts
    away from the platform's standards-anchored math.
    """
    issues = []
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parent
    try:
        stds = {s["standard_id"]: s for s in
                json.loads((root / "canonical" / "standards.json").read_text(encoding="utf-8"))["standards"]}
        formulas = json.loads((root / "canonical" / "formula_contracts.json").read_text(encoding="utf-8"))["formulas"]
    except Exception:
        return issues  # registries missing — skip (covered by other gates)

    # Map metric name keywords -> short_name to assert citation when the
    # metric is mentioned. Only include metrics likely to surface in
    # natural-language AI prompts (not raw formula IDs).
    METRIC_TO_CITATION = []
    for f in formulas:
        short = (stds.get(f.get("standard_id"), {}) or {}).get("short_name", "")
        if not short:
            continue
        # Derive a metric keyword from the formula's display name (first 1-2 words)
        name = (f.get("name", "") or "").lower()
        for keyword in ["mtbf", "mttr", "oee", "pm compliance", "rpn",
                        "bearing l10", "pump head", "motor power",
                        "anomaly", "weibull", "darcy", "schedule performance",
                        "cost performance"]:
            if keyword in name and (keyword, short) not in METRIC_TO_CITATION:
                METRIC_TO_CITATION.append((keyword, short))

    # Build a frequency map of bodies registered in standards.json so body-alone
    # citations are accepted only for unambiguous bodies (e.g. 'SMRP' is unique;
    # 'ISO' covers 5+ standards so body-alone is ambiguous for ISO standards).
    body_freq: dict[str, int] = {}
    for s in stds.values():
        b = (s.get("short_name", "").split() or [""])[0]
        body_freq[b] = body_freq.get(b, 0) + 1

    def _accepted_citations(short_name: str) -> list[str]:
        """Return all acceptable citation strings for a Tier-S short_name.
        Accepts the full short_name, the body+number prefix (e.g. 'ISO 14224'
        for 'ISO 14224:2016'), and the body alone ONLY for unambiguous bodies
        (those covering one standard in the registry, e.g. 'SMRP'). Body alone
        is rejected for multi-standard bodies like 'ISO' to avoid false-positive
        matches against unrelated ISO standards in the same prompt.
        """
        out = [short_name]
        if ":" in short_name:
            out.append(short_name.split(":")[0].strip())  # 'ISO 14224:2016' -> 'ISO 14224'
        toks = short_name.split()
        if len(toks) >= 2 and toks[0].isupper():
            out.append(" ".join(toks[:2]).rstrip(":"))  # 'ISO 22400-2:2014' -> 'ISO 22400-2'
        first = toks[0] if toks else ""
        if first.isupper() and len(first) >= 3 and body_freq.get(first, 99) <= 1:
            out.append(first)  # body alone — only for unambiguous bodies
        return out

    for page, content in [(FLOAT_JS, float_content), (ASSISTANT_HTML, assistant_content)]:
        if not content:
            continue
        low = content.lower()
        for keyword, short in METRIC_TO_CITATION:
            # Surface mentions the metric (case-insensitive keyword present)
            mentions_metric = keyword in low
            if not mentions_metric:
                continue
            # Accept any of the canonical citation forms (full short_name,
            # body+number, or body acronym for single-org standards).
            accepted = _accepted_citations(short)
            cited = any(c.lower() in low for c in accepted)
            if not cited:
                issues.append({
                    "check":  "tier_s_citation",
                    "page":   page,
                    "metric": keyword,
                    "standard": short,
                    "reason": (
                        f"{page} mentions '{keyword}' but does not cite any of "
                        f"{accepted!r} — AI answer about this metric won't be standards-anchored"
                    ),
                })
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    # L1
    "discipline_names", "tool_consistency", "calc_count_consistent",
    # L2
    "draft_artifacts",
    # L3
    "analytics_feature_parity", "logbook_feature_parity",
    # L4
    "tier_s_citation",
]

CHECK_LABELS = {
    # L1
    "discipline_names":         "L1  Skill Matrix disciplines match across both AI surfaces",
    "tool_consistency":         "L1  All active tools in companion-launcher.js also in assistant.html",
    "calc_count_consistent":    "L1  Calc count consistent across both surfaces (46)",
    # L2
    "draft_artifacts":          "L2  No TODO/FIXME/placeholder in either prompt",
    # L3
    "analytics_feature_parity": "L3  Analytics features (OEE, consequence, anomaly) in both surfaces",
    "logbook_feature_parity":   "L3  Logbook new fields (consequence, production) in both surfaces",
    # L4
    "tier_s_citation":          "L4  Every metric mentioned in an AI prompt cites its Tier-S standard short_name",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nAI Prompt Regression Validator (4-layer)"))
    print("=" * 55)

    float_js      = read_file(FLOAT_JS)
    assistant     = read_file(ASSISTANT_HTML)
    skill_content = read_file(SKILL_CONTENT)

    all_issues = []
    all_issues += check_discipline_consistency(float_js, assistant, skill_content)
    all_issues += check_tool_consistency(float_js, assistant)
    all_issues += check_calc_count_consistency(float_js, assistant)
    all_issues += check_draft_artifacts(float_js, assistant)
    all_issues += check_feature_parity(float_js, assistant)
    all_issues += check_tier_s_citations(float_js, assistant)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "ai_regression",
        "total_checks": total,
        "passed":       n_pass,
        "skipped":      n_skip,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
    }
    with open("ai_regression_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
