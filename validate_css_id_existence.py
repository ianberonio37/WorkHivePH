"""
CSS Selector ID Existence Validator (L0, ratcheted).
=======================================================
Every CSS selector `#X` MUST reference an `id="X"` that exists
somewhere on the same page (either static markup OR a dynamically
rendered element with a stable id). Dead CSS rules:
  - Confuse refactors (developers preserve "important" rules that do
    nothing).
  - Bloat the CSSOM and slow render slightly.
  - Often indicate a refactor that renamed an id but forgot the CSS.

Heuristic: scan inline <style> blocks per page; for each `#id` selector,
verify a matching `id="id"` exists either in static markup or appears as
a string literal in a <script> block (template-rendered ids).

Output: css_id_existence_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "css_id_existence_report.json"
BASELINE_PATH = ROOT / "css_id_existence_baseline.json"

STYLE_RE  = re.compile(r"<style\b[^>]*>(.*?)</style>", re.DOTALL | re.IGNORECASE)
ID_SEL_RE = re.compile(r"#([\w-]+)")
HTML_ID_RE = re.compile(r"""\sid\s*=\s*['"]([\w-]+)['"]""", re.IGNORECASE)
JS_ID_LITERAL_RE = re.compile(r"""['"]([\w-]+)['"]""")


# Sentinel binding: name the L2 test `test('css_id_existence: ...')` for coverage credit.
CHECK_NAMES = ["css_id_existence"]


def _selectors_in_style(css: str) -> set:
    """Return the set of #id tokens used as CSS SELECTORS (the text before
    each `{` brace). Avoids hex color false positives by skipping the
    declaration block (between `{` and `}`)."""
    # Strip CSS block comments + attribute selectors + url()
    css_clean = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    css_clean = re.sub(r"url\([^)]*\)", "", css_clean)
    css_clean = re.sub(r"\[[^\]]*\]", "", css_clean)
    # Walk rule-by-rule: each chunk before `{` is a selector list.
    out = set()
    depth = 0
    selector_buf = []
    for c in css_clean:
        if c == "{":
            if depth == 0:
                sel_text = "".join(selector_buf)
                for m in ID_SEL_RE.finditer(sel_text):
                    val = m.group(1)
                    # Hex colors are 3, 4, 6, or 8 chars of [0-9a-fA-F].
                    # CSS IDs allowed to start with a digit are unusual.
                    # Skip if value is a pure hex color length.
                    if re.fullmatch(r"[0-9a-fA-F]{3,8}", val) and len(val) in (3,4,6,8):
                        continue
                    out.add(val)
                selector_buf = []
            depth += 1
        elif c == "}":
            depth -= 1
            if depth < 0: depth = 0
            selector_buf = []
        elif depth == 0:
            selector_buf.append(c)
    return out


def _ids_in_body(body: str) -> set:
    """Every id attribute value declared statically OR appearing as a string
    literal inside <script> blocks (covers dynamic templates that emit
    `<div id="X">`)."""
    ids = set(HTML_ID_RE.findall(body))
    # Also gather literals inside <script> blocks — heuristic accepts any
    # string literal as a possible id, which over-accepts but eliminates
    # false positives for template-built DOMs.
    SCRIPT_RE = re.compile(r"<script\b[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE)
    for m in SCRIPT_RE.finditer(body):
        ids.update(JS_ID_LITERAL_RE.findall(m.group(1)))
    # Cross-page shared injected elements (nav-hub.js, ai-widget.js,
    # voice button, search FAB) attach IDs at runtime that don't appear
    # in this page's static markup. Whitelist the known shared set.
    ids.update({
        "wh-ai-widget", "wh-nav-hub-fab", "wh-navhub",
        "wh-search-fab", "wh-voice-btn", "wh-companion",
        "wh-toast", "wh-modal-root",
    })
    return ids


def _check_page(path: Path) -> list:
    body = path.read_text(encoding="utf-8", errors="replace")
    # Page-bundle pairing (Arc L / L1): engineering-design.html keeps its <style> #id
    # selectors, but the JS that creates those ids dynamically (e.g. `el.id='_svg_rb'`)
    # was extracted to engineering-design.js — re-attach it (wrapped as a script block so
    # _ids_in_body harvests its id literals) or every dynamic-id selector reads as orphan.
    if path.name == "engineering-design.html":
        _bundle = path.parent / "engineering-design.js"
        if _bundle.exists():
            body += f"\n<script>\n{_bundle.read_text(encoding='utf-8', errors='replace')}\n</script>\n"
    if "css-id-allow" in body:
        return []
    declared_ids = _ids_in_body(body)
    css_selectors: set = set()
    for sm in STYLE_RE.finditer(body):
        css_selectors |= _selectors_in_style(sm.group(1))
    missing = sorted(css_selectors - declared_ids)
    return [{"page": path.name, "selector": f"#{m}"} for m in missing]


def main() -> int:
    issues = []
    pages = sorted(ROOT.glob("*.html"))
    scanned = 0
    for path in pages:
        if path.name.startswith("_"): continue
        if ".backup." in path.name or path.name.endswith("-test.html"): continue
        scanned += 1
        issues.extend(_check_page(path))

    drift = len(issues)
    baseline = 0
    if BASELINE_PATH.exists():
        try: baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("drift", 0)
        except Exception: baseline = 0
    else:
        baseline = drift
        BASELINE_PATH.write_text(json.dumps({"drift": baseline, "established": True}, indent=2), encoding="utf-8")
    if drift < baseline:
        baseline = drift
        BASELINE_PATH.write_text(json.dumps({"drift": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"pages_scanned": scanned, "drift": drift, "baseline": baseline},
        "issues": issues,
    }, indent=2), encoding="utf-8")

    print(f"\nCSS Selector ID Existence Validator (L0)")
    print("=" * 56)
    print(f"  pages scanned:    {scanned}")
    print(f"  drift:            {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — every #id CSS selector matches a declared id on the page.")
        return 0
    for i in issues[:30]:
        print(f"  {i['page']}  → {i['selector']}")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
