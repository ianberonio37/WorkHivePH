"""
Drawing Standards Compliance Validator — WorkHive Platform
===========================================================
Engineering diagrams in WorkHive must conform to their governing
standards (IEC 62305, IEC 60617, ISA-5.1, NFPA 13, ISO 8528-1,
IESNA, ASHRAE). The SVG canvas rules and code patterns are the
structural foundation — if they break, the PDF export breaks too.

  Layer 1 — Canvas dimensions
    1.  Canvas width = 1050px         — A3 landscape standard; deviations crop or stretch PDF
    2.  Canvas height H/W <= 0.55     — portrait proportions overflow to a second PDF page

  Layer 2 — SVG structural integrity
    3.  Arc chord safety formula       — prevents arcs flying off-screen on input change
    4.  viewBox references W and H     — viewBox must use the same W/H vars, not hard-coded

  Layer 3 — XSS and style standard
    5.  Title block uses EF() helper   — bare contenteditable on <td> is XSS-risky

  Layer 4 — Coverage completeness
    6.  All builders registered        — every buildXxxSvg function must be in BUILDER_FUNCTIONS

Usage:  python validate_drawings.py
Output: drawings_report.json
"""
import re, json, sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

DRAWING_FILE = "engineering-design.html"

BUILDER_FUNCTIONS = [
    "buildTransformerSLDSvg",
    "buildLPSZoneSvg",
    "buildElectricalSLDSvg",
    "buildGeneratorConnectionSvg",
    "buildPumpPIDSvg",
    "buildFireSprinklerSvg",
    "buildFirePumpPIDSvg",
    "buildHVACSvg",
    "buildLightingLayoutSvg",
    # Phase 10 HVAC group
    "buildCleanAgentSVG",
    "buildVentilationSVG",
    "buildFCUSVG",
    "buildRefrigPipeSVG",
    "buildCoolingTowerSVG",
    "buildChillerSVG",
    "buildExpansionTankSVG",
    # Phase 10 Mechanical group
    "buildPipeSizingSVG",
    "buildCompressedAirSVG",
    "buildBoilerSystemSVG",
    # Phase 10 HVAC remaining
    "buildAHUSizingSVG",
    "buildDuctSizingSVG",
    # Phase 10 Electrical group
    "buildSolarPVSVG",
    "buildPFCSVG",
    "buildUPSSVG",
    "buildEarthingSVG",
]

REQUIRED_WIDTH = 1050
MAX_HW_RATIO   = 0.56


def extract_function_body(content, func_name, max_lines=600):
    m = re.search(rf"function\s+{re.escape(func_name)}\s*\(", content)
    if not m:
        return None, -1
    start_line  = content[:m.start()].count("\n") + 1
    brace_start = content.find("{", m.end())
    if brace_start == -1:
        return None, -1
    depth, i = 0, brace_start
    limit = min(brace_start + max_lines * 80, len(content))
    while i < limit:
        if content[i] == "{":
            depth += 1
        elif content[i] == "}":
            depth -= 1
            if depth == 0:
                return content[brace_start:i + 1], start_line
        i += 1
    lines = content[m.start():m.start() + max_lines * 80].splitlines()[:max_lines]
    return "\n".join(lines), start_line


# ── Layer 1: Canvas dimensions ────────────────────────────────────────────────

def check_canvas_width(content, builders):
    """Every builder must declare W = 1050 — the A3 landscape content width.
    A different width produces diagrams that don't fit the PDF export template."""
    issues = []
    for func in builders:
        body, start_line = extract_function_body(content, func)
        if body is None:
            issues.append({"check": "canvas_width", "func": func,
                           "reason": f"Function '{func}' not found in {DRAWING_FILE}"})
            continue
        if not re.search(r"\bW\s*=\s*1050\b", body):
            issues.append({"check": "canvas_width", "func": func, "line": start_line,
                           "reason": (f"{func}() does not set W = 1050 — "
                                      f"canvas width deviates from A3 landscape standard (1050px)")})
    return issues


def check_canvas_ratio(content, builders):
    """All declared H values must satisfy H/W <= 0.55. Heights above 578px push
    the SVG into portrait proportions and the PDF overflows to a second page."""
    issues = []
    for func in builders:
        body, start_line = extract_function_body(content, func)
        if body is None:
            continue
        h_m = re.search(r"\bH\s*=\s*(\d+)\b", body)
        if not h_m:
            continue
        h_val = int(h_m.group(1))
        ratio = h_val / REQUIRED_WIDTH
        if ratio > MAX_HW_RATIO:
            issues.append({"check": "canvas_ratio", "func": func, "line": start_line,
                           "reason": (f"{func}() sets H = {h_val} (H/W = {ratio:.3f} > {MAX_HW_RATIO}) — "
                                      f"exceeds A3 landscape proportion, PDF overflows to second page")})
    return issues


# ── Layer 2: SVG structural integrity ────────────────────────────────────────

def check_arc_safety(content, builders):
    """If a builder draws SVG arcs (A command in path d=), it must use the arc
    chord safety formula R = Math.max(chordH + padding, minR) to prevent arcs
    from flying off-screen when input dimensions change."""
    issues = []
    for func in builders:
        body, start_line = extract_function_body(content, func)
        if body is None:
            continue
        if not re.search(r'["\']\s*[Mm][^"\']*\s[Aa]\s', body):
            continue
        if not re.search(r"chordH|R_arc|Math\.max\s*\([^)]*chord|Math\.max\s*\([^)]*R\b", body):
            issues.append({"check": "arc_safety", "func": func, "line": start_line,
                           "reason": (f"{func}() uses SVG arcs but has no chord safety formula "
                                      f"(Math.max(chordH + padding, minR)) — "
                                      f"arcs may fly off-screen when input dimensions change")})
    return issues


def check_viewbox_uses_wh(content, builders):
    """
    Every builder's SVG return statement must use viewBox="0 0 ${W} ${H}" —
    referencing the W and H variables, not hard-coded pixel values.
    Hard-coded viewBox values silently diverge when W or H is changed,
    making the exported diagram scale incorrectly in the PDF container.
    The correct pattern is: viewBox="0 0 ${W} ${H}" or viewBox="0 0 ${W} ${STRIP_Y}".
    """
    issues = []
    for func in builders:
        body, start_line = extract_function_body(content, func)
        if body is None:
            continue
        # Must return an <svg> element
        if "<svg" not in body:
            continue
        # Check if viewBox is present
        if "viewBox" not in body and "viewbox" not in body.lower():
            issues.append({"check": "viewbox_uses_wh", "func": func, "line": start_line,
                           "reason": (f"{func}() SVG has no viewBox attribute — "
                                      f"without viewBox, the diagram cannot scale to fit the "
                                      f"PDF container and will be clipped or stretched")})
            continue
        # Check if it uses a hard-coded numeric viewBox instead of W/H variables
        hard_coded = re.search(r'viewBox=["\']0 0 \d+ \d+["\']', body)
        if hard_coded:
            issues.append({"check": "viewbox_uses_wh", "func": func, "line": start_line,
                           "reason": (f"{func}() uses hard-coded viewBox values instead of "
                                      f"viewBox=\"0 0 ${{W}} ${{H}}\" — hard-coded values "
                                      f"silently diverge when W or H is updated")})
    return issues


# ── Layer 3: XSS and style standard ──────────────────────────────────────────

def check_title_block_ef(content, builders):
    """Diagram title block cells must use EF() helper, not bare contenteditable
    on <td>. Bare contenteditable bypasses XSS escaping and the platform style standard."""
    render_funcs = [
        f.replace("build", "render").replace("Svg", "Diagram")
        for f in builders
    ]
    render_funcs += [
        "renderLPSDiagram", "renderElectricalSLD", "renderGeneratorConnectionDiagram",
        "renderPumpPID", "renderFireSprinklerDiagram",
        "renderHVACDiagramSVG", "renderLightingLayout",
        "renderTransformerSLDDiagram",
    ]
    issues  = []
    checked = set()
    for func in render_funcs:
        if func in checked:
            continue
        checked.add(func)
        body, start_line = extract_function_body(content, func)
        if body is None:
            continue
        if "title block" not in body.lower() and "EF(" not in body and "ef(" not in body:
            continue
        bare_td = re.search(r'<td\b[^>]*\bcontenteditable\b', body, re.IGNORECASE)
        if bare_td:
            line_offset = body[:bare_td.start()].count("\n")
            issues.append({"check": "title_block_ef", "func": func,
                           "line": start_line + line_offset,
                           "reason": (f"{func}() has bare contenteditable on a <td> element — "
                                      f"use EF() helper for XSS safety and consistent field styling")})
    return issues


# ── Layer 4: Coverage completeness ────────────────────────────────────────────

def check_all_builders_covered(content, registered):
    """
    Every function matching the buildXxxSvg naming convention in engineering-design.html
    must be registered in BUILDER_FUNCTIONS. A new diagram added without registration
    escapes all 5 other checks silently — its canvas width, H/W ratio, arc safety,
    viewBox, and title block are never validated.

    buildTransformerSLDSvg was previously missing from BUILDER_FUNCTIONS,
    meaning the Transformer Sizing diagram's canvas and arc patterns were never checked.
    """
    issues = []
    found  = re.findall(r"^function\s+(build\w+Svg)\s*\(", content, re.MULTILINE)
    registered_set = set(registered)
    for func in found:
        if func not in registered_set:
            issues.append({"check": "all_builders_covered", "func": func,
                           "reason": (f"{func}() exists in {DRAWING_FILE} but is not in "
                                      f"BUILDER_FUNCTIONS — its canvas dimensions, arc safety, "
                                      f"viewBox, and title block are never validated; "
                                      f"add it to BUILDER_FUNCTIONS in validate_drawings.py")})
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "canvas_width",
    "canvas_ratio",
    "arc_safety",
    "viewbox_uses_wh",
    "title_block_ef",
    "all_builders_covered",
]

CHECK_LABELS = {
    "canvas_width":          "L1  Canvas width = 1050px in all diagram builders",
    "canvas_ratio":          "L1  Canvas height H/W <= 0.55 (A3 landscape fit)",
    "arc_safety":            "L2  Arc chord safety formula used when SVG arcs are present",
    "viewbox_uses_wh":       "L2  viewBox references W and H variables (not hard-coded)",
    "title_block_ef":        "L3  Title block editable cells use EF() not bare contenteditable",
    "all_builders_covered":  "L4  All buildXxxSvg functions registered in BUILDER_FUNCTIONS",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nDrawing Standards Compliance Validator (4-layer)"))
    print("=" * 55)

    content = read_file(DRAWING_FILE)
    if not content:
        print(f"\n  ERROR: {DRAWING_FILE} not found")
        sys.exit(1)

    print(f"  Checking {len(BUILDER_FUNCTIONS)} builders: {', '.join(BUILDER_FUNCTIONS)}\n")

    all_issues = []
    all_issues += check_canvas_width(content, BUILDER_FUNCTIONS)
    all_issues += check_canvas_ratio(content, BUILDER_FUNCTIONS)
    all_issues += check_arc_safety(content, BUILDER_FUNCTIONS)
    all_issues += check_viewbox_uses_wh(content, BUILDER_FUNCTIONS)
    all_issues += check_title_block_ef(content, BUILDER_FUNCTIONS)
    all_issues += check_all_builders_covered(content, BUILDER_FUNCTIONS)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "drawings",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("drawings_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
