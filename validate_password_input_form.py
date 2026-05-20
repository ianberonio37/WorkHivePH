"""
<input type="password"> Form Wrapper Validator (L0, ratcheted).
==================================================================
Every `<input type="password">` MUST be inside a `<form>` (with a
matching username/email input nearby). Browsers attach autofill +
password manager save flow ONLY when the password input is in a form
context. Without it:
  - User's password manager can't suggest/save credentials.
  - Browser warns "this form is not secure" in some modes.
  - Some mobile browsers won't show the password reveal toggle.

Exemption: `password-input-allow` marker (for things like profile
"change password" flows that POST via JS without a real form).

Output: password_input_form_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "password_input_form_report.json"
BASELINE_PATH = ROOT / "password_input_form_baseline.json"

PW_INPUT_RE = re.compile(r"""<input\b[^>]*\btype\s*=\s*['"]password['"][^>]*>""", re.IGNORECASE)
FORM_BLOCK_RE = re.compile(r"<form\b[^>]*>(.*?)</form>", re.IGNORECASE | re.DOTALL)


# Sentinel binding: name the L2 test `test('password_input_form: ...')` for coverage credit.
CHECK_NAMES = ["password_input_form"]


def _check_page(path: Path) -> list:
    body = path.read_text(encoding="utf-8", errors="replace")
    # Keep an unstripped body for allow-marker proximity checks (comments
    # carry the marker but get stripped from body_clean).
    body_clean = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    issues = []
    form_ranges = [(m.start(), m.end()) for m in FORM_BLOCK_RE.finditer(body_clean)]
    for m in PW_INPUT_RE.finditer(body_clean):
        pos = m.start()
        if any(s <= pos < e for s, e in form_ranges):
            continue
        # Allow marker within ±300 chars in ORIGINAL body (search by tag text
        # since stripped positions don't map 1:1 to original positions).
        tag = m.group(0)
        anchor = body.find(tag[:60])
        if anchor >= 0:
            window = body[max(0, anchor-400): anchor+200]
            if "password-input-allow" in window:
                continue
        line_no = body_clean.count("\n", 0, pos) + 1
        issues.append({"page": path.name, "line": line_no, "tag": tag[:160]})
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

    print(f"\n<input type=password> Form Wrapper Validator (L0)")
    print("=" * 56)
    print(f"  pages scanned:    {scanned}")
    print(f"  drift:            {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — every <input type=password> is inside a <form>.")
        return 0
    for i in issues[:25]:
        print(f"  {i['page']}:{i['line']}  {i['tag']}")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
