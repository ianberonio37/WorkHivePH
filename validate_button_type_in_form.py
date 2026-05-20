"""
Button Type In Form Validator (L0, ratcheted).
================================================
Every `<button>` inside a `<form>` MUST declare `type="button"` (or
`type="submit"` / `type="reset"` explicitly). HTML default is `submit`
— a stray "Cancel" button inside a form submits the form. Catches
the class of bugs where clicking an icon/cancel/secondary button
inside a form posts unrelated data and triggers full-page navigation.

Output: button_type_in_form_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "button_type_in_form_report.json"
BASELINE_PATH = ROOT / "button_type_in_form_baseline.json"

FORM_BLOCK_RE = re.compile(r"<form\b[^>]*>(.*?)</form>", re.IGNORECASE | re.DOTALL)
BUTTON_OPEN_RE = re.compile(r"<button\b[^>]*>", re.IGNORECASE)
TYPE_ATTR_RE   = re.compile(r"""\btype\s*=\s*['"]?(button|submit|reset)['"]?""", re.IGNORECASE)


# Sentinel binding: name the L2 test `test('button_type_in_form: ...')` for coverage credit.
CHECK_NAMES = ["button_type_in_form"]


def _check_page(path: Path) -> list:
    issues = []
    body = path.read_text(encoding="utf-8", errors="replace")
    for form_match in FORM_BLOCK_RE.finditer(body):
        inner = form_match.group(1)
        for btn_match in BUTTON_OPEN_RE.finditer(inner):
            tag = btn_match.group(0)
            if "button-type-allow" in inner[max(0, btn_match.start()-200):btn_match.end()+200]:
                continue
            if not TYPE_ATTR_RE.search(tag):
                issues.append({"page": path.name, "tag": tag[:160]})
    return issues


def main() -> int:
    issues = []
    pages = sorted(ROOT.glob("*.html"))
    for path in pages:
        if path.name.startswith("_"):
            continue
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
        "summary": {"pages_scanned": len(pages), "drift": drift, "baseline": baseline},
        "issues": issues,
    }, indent=2), encoding="utf-8")

    print(f"\nButton Type In Form Validator (L0)")
    print("=" * 56)
    print(f"  pages scanned:    {len(pages)}")
    print(f"  drift:            {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — every <button> inside a <form> declares its type.")
        return 0
    for i in issues[:15]:
        print(f"  {i['page']}  → {i['tag']}")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
