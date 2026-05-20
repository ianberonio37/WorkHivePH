"""
<select> Placeholder Option Validator (L0, ratcheted).
=========================================================
A `<select>` element MUST have either:
  - a first `<option value="">` placeholder option ("Choose...", "Select...")
  - a `[selected]` attribute on one of its options
  - a `<option disabled selected hidden>` placeholder

Without one, the FIRST option becomes the implicit default — which
means:
  - Submitting the form silently sends that first value even if the
    user never looked at the field. Common bug: type defaults to
    "alpha" because that's the first option, user thought it was
    blank, submits wrong category.
  - Mobile browsers show no visual cue that the field is interactive
    until tapped.

Exemption: `select-placeholder-allow` on the same line.

Output: select_placeholder_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "select_placeholder_report.json"
BASELINE_PATH = ROOT / "select_placeholder_baseline.json"

SELECT_BLOCK_RE = re.compile(r"<select\b([^>]*)>(.*?)</select>", re.IGNORECASE | re.DOTALL)
FIRST_OPTION_RE = re.compile(r"<option\b([^>]*)>", re.IGNORECASE)
SELECTED_ATTR_RE = re.compile(r"""\bselected\b""", re.IGNORECASE)
EMPTY_VALUE_RE   = re.compile(r"""\bvalue\s*=\s*['"]\s*['"]""", re.IGNORECASE)
DISABLED_ATTR_RE = re.compile(r"""\bdisabled\b""", re.IGNORECASE)


# Sentinel binding: name the L2 test `test('select_placeholder: ...')` for coverage credit.
CHECK_NAMES = ["select_placeholder"]


def _check_page(path: Path) -> list:
    body = path.read_text(encoding="utf-8", errors="replace")
    issues = []
    body_clean = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    for sm in SELECT_BLOCK_RE.finditer(body_clean):
        attrs = sm.group(1)
        inner = sm.group(2)
        # Skip multi-select (different UX semantics)
        if re.search(r"\bmultiple\b", attrs, re.IGNORECASE):
            continue
        if "select-placeholder-allow" in body_clean[max(0, sm.start()-200): sm.end()+50]:
            continue
        first = FIRST_OPTION_RE.search(inner)
        if not first:
            continue
        first_attrs = first.group(1)
        # OK if first option has value="" or is selected/disabled placeholder
        if EMPTY_VALUE_RE.search(first_attrs):
            continue
        if SELECTED_ATTR_RE.search(first_attrs) and DISABLED_ATTR_RE.search(first_attrs):
            continue
        # OK if ANY option in the whole select has [selected]
        if SELECTED_ATTR_RE.search(inner):
            continue
        line_no = body_clean.count("\n", 0, sm.start()) + 1
        # Get a useful preview
        preview = sm.group(0)[:160].replace("\n", " ")
        issues.append({"page": path.name, "line": line_no, "preview": preview})
    return issues


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

    print(f"\n<select> Placeholder Validator (L0)")
    print("=" * 56)
    print(f"  pages scanned:    {scanned}")
    print(f"  drift:            {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — every <select> has placeholder/selected/empty-value first option.")
        return 0
    for i in issues[:25]:
        print(f"  {i['page']}:{i['line']}  {i['preview']}")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
