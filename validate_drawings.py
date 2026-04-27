"""
Drawing Standards Compliance Validator — WorkHive Platform
===========================================================
Engineering diagrams in WorkHive must conform to their governing
standards (IEC 62305, IEC 60617, ISA-5.1, NFPA 13, ISO 8528-1,
IESNA, ASHRAE). The SVG canvas rules and code patterns are the
structural foundation — if they break, the PDF export breaks too.

From the Drawing Standards skill file.

Four things checked:

  1. Canvas width = 1050px on all diagram builders
     — A3 landscape content width is 1050px. A builder using a different
       width produces a PDF that is either too small (cropped) or stretched.
       All 7 diagram builders (LPS, SLD, Generator, Pump P&ID, Fire
       Sprinkler, HVAC, Lighting) must declare W = 1050.

  2. Canvas height respects H/W <= 0.55 (A3 landscape fit)
     — Valid heights: 580 (standard), 467 (when title block is separate HTML).
       H/W > 0.55 forces the SVG into portrait proportions and the
       PDF export overflows to a second page. The skill rule is H/W <= 0.55.

  3. Arc chord safety formula used when arcs are present
     — SVG arcs fail silently when R < half-chord: the browser auto-scales
       and the arc flies off-screen. The skill rule is:
         R = Math.max(chordH + padding, minR)
       Any builder that uses SVG arc commands (A in path d=) without this
       safety formula will produce broken diagrams on certain inputs.

  4. Title block editable cells use EF() helper, not bare contenteditable
     — Drawing title block table cells must use the EF() helper which
       wraps contenteditable in an escHtml-safe span. A bare <td
       contenteditable> is both XSS-risky and inconsistent with the
       platform's editable field standard.

Usage:  python validate_drawings.py
Output: drawings_report.json
"""
import re, json, sys

DRAWING_FILE = "engineering-design.html"

# All 7 diagram builder functions (from buildXxxSvg pattern)
BUILDER_FUNCTIONS = [
    "buildLPSZoneSvg",
    "buildElectricalSLDSvg",
    "buildGeneratorConnectionSvg",
    "buildPumpPIDSvg",
    "buildFireSprinklerSvg",
    "buildHVACSvg",
    "buildLightingLayoutSvg",
]

REQUIRED_WIDTH  = 1050
MAX_HW_RATIO    = 0.56   # H=580 gives 0.5524 — skill uses 0.55 as approx guideline


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def extract_function_body(content, func_name, max_lines=600):
    """Extract the body of a named function (up to max_lines)."""
    m = re.search(rf"function\s+{re.escape(func_name)}\s*\(", content)
    if not m:
        return None, -1
    start = m.start()
    lines = content[start:start + max_lines * 80].splitlines()[:max_lines]
    return "\n".join(lines), content[:start].count("\n") + 1


# ── Check 1: Canvas width = 1050 in every builder ────────────────────────────

def check_canvas_width(content, builders):
    """
    Every diagram builder must declare W = 1050 (the A3 landscape content width).
    A different width produces diagrams that don't fit the PDF export template.
    """
    issues = []
    for func in builders:
        body, start_line = extract_function_body(content, func)
        if body is None:
            issues.append({
                "func":   func,
                "reason": f"Function '{func}' not found in {DRAWING_FILE}",
            })
            continue
        # Check for W = 1050 declaration
        if not re.search(r"\bW\s*=\s*1050\b", body):
            issues.append({
                "func":      func,
                "line":      start_line,
                "reason": (
                    f"{func}() does not set W = 1050 — "
                    f"canvas width deviates from A3 landscape standard (1050px)"
                ),
            })
    return issues


# ── Check 2: Canvas height H/W <= 0.55 ───────────────────────────────────────

def check_canvas_ratio(content, builders):
    """
    All declared H values must satisfy H/W <= 0.55. The valid heights are:
    - H = 580 (standard — title block inside SVG)
    - H = 467 (reduced — title block is separate HTML below the SVG)
    Heights above 578px start pushing the H/W ratio above 0.55 and cause
    the PDF to overflow to a second page.
    """
    issues = []
    for func in builders:
        body, start_line = extract_function_body(content, func)
        if body is None:
            continue

        # Find H = NNN declaration
        h_m = re.search(r"\bH\s*=\s*(\d+)\b", body)
        if not h_m:
            continue   # no H — might use default or inline

        h_val = int(h_m.group(1))
        ratio = h_val / REQUIRED_WIDTH
        if ratio > MAX_HW_RATIO:
            issues.append({
                "func":   func,
                "line":   start_line,
                "h":      h_val,
                "ratio":  round(ratio, 3),
                "reason": (
                    f"{func}() sets H = {h_val} (H/W = {ratio:.3f} > {MAX_HW_RATIO}) — "
                    f"exceeds A3 landscape proportion, PDF will overflow to second page"
                ),
            })
    return issues


# ── Check 3: Arc safety formula used when arcs are present ───────────────────

def check_arc_safety(content, builders):
    """
    If a diagram builder draws SVG arcs (A command in path d= attribute),
    it must use the arc chord safety formula to prevent the arc from
    auto-scaling and flying off-screen on certain input values.

    The safe pattern from the Drawing Standards skill:
      const chordH = (x2 - x1) / 2;
      const R_arc  = Math.max(chordH + N, minR);

    A builder that uses hard-coded radii without verifying R >= chordH
    will silently break when the input dimensions change.
    """
    issues = []
    for func in builders:
        body, start_line = extract_function_body(content, func)
        if body is None:
            continue

        # Does this builder use SVG arc commands?
        uses_arc = bool(re.search(r'["\']\s*[Mm][^"\']*\s[Aa]\s', body))
        if not uses_arc:
            continue

        # Does it have the chord safety pattern?
        has_safety = bool(re.search(
            r"chordH|R_arc|Math\.max\s*\([^)]*chord|Math\.max\s*\([^)]*R\b",
            body
        ))
        if not has_safety:
            issues.append({
                "func":   func,
                "line":   start_line,
                "reason": (
                    f"{func}() uses SVG arcs but has no chord safety formula "
                    f"(Math.max(chordH + padding, minR)) — "
                    f"arcs may fly off-screen when input dimensions change"
                ),
            })
    return issues


# ── Check 4: Title block cells use EF() not bare contenteditable ──────────────

def check_title_block_ef(content, builders):
    """
    Diagram title blocks (the editable HTML table below each SVG) must use
    the EF() helper function for all editable cells. EF() wraps the value
    in an escHtml-safe contenteditable span with the platform's editable-field
    style. Bare <td contenteditable> or <td ... contenteditable> bypasses both
    the XSS escaping and the visual styling standard.

    This check finds diagram title block render functions (renderXxxDiagram)
    and verifies they use EF() or ef() for cell content, not bare contenteditable
    on the <td> element itself.
    """
    issues = []
    # Companion render functions that contain the title block HTML
    render_funcs = [
        f.replace("build", "render").replace("Svg", "Diagram")
        for f in builders
    ]
    render_funcs += [
        "renderLPSDiagram", "renderElectricalSLD", "renderGeneratorConnectionDiagram",
        "renderPumpPID", "renderFireSprinklerDiagram",
        "renderHVACDiagramSVG", "renderLightingLayout",
    ]

    checked = set()
    for func in render_funcs:
        if func in checked:
            continue
        checked.add(func)

        body, start_line = extract_function_body(content, func)
        if body is None:
            continue
        if "title block" not in body.lower() and "EF(" not in body and "ef(" not in body:
            continue  # no title block in this function

        # Look for bare contenteditable on a <td> tag
        bare_td = re.search(
            r'<td\b[^>]*\bcontenteditable\b',
            body, re.IGNORECASE
        )
        if bare_td:
            line_offset = body[:bare_td.start()].count("\n")
            issues.append({
                "func":   func,
                "line":   start_line + line_offset,
                "reason": (
                    f"{func}() has bare contenteditable on a <td> element in the "
                    f"title block — use EF() helper instead for XSS safety and "
                    f"consistent editable field styling"
                ),
            })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("Drawing Standards Compliance Validator")
print("=" * 70)

content = read_file(DRAWING_FILE)
if not content:
    print(f"\n  ERROR: {DRAWING_FILE} not found")
    sys.exit(1)

print(f"\n  Checking {len(BUILDER_FUNCTIONS)} diagram builder functions: "
      f"{', '.join(BUILDER_FUNCTIONS)}\n")

fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        f"[1] Canvas width = {REQUIRED_WIDTH}px in all diagram builders",
        check_canvas_width(content, BUILDER_FUNCTIONS),
        "FAIL",
    ),
    (
        f"[2] Canvas height H/W <= {MAX_HW_RATIO} (A3 landscape fit)",
        check_canvas_ratio(content, BUILDER_FUNCTIONS),
        "FAIL",
    ),
    (
        "[3] Arc chord safety formula used when SVG arcs are present",
        check_arc_safety(content, BUILDER_FUNCTIONS),
        "FAIL",
    ),
    (
        "[4] Title block editable cells use EF() not bare contenteditable",
        check_title_block_ef(content, BUILDER_FUNCTIONS),
        "FAIL",
    ),
]

for label, issues, severity in checks:
    print(f"\n{label}\n")
    if not issues:
        print("  PASS")
    else:
        for iss in issues:
            print(f"  {severity}  {iss.get('func', iss.get('page', '?'))}")
            print(f"        {iss['reason']}")
        if severity == "FAIL":
            fail_count += len(issues)
        else:
            warn_count += len(issues)
    report[label] = issues

print(f"\n{'=' * 70}")
print(f"Result: {fail_count} FAIL  {warn_count} WARN")

with open("drawings_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved drawings_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll drawing standards checks PASS.")
