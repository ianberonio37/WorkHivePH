"""
<form> Submission Target Validator (L0, ratcheted).
====================================================
Every `<form>` MUST have at least one of:
  - action="..." attribute (server-side POST target)
  - onsubmit="..." handler
  - addEventListener('submit', ...) wiring discoverable in the page

Otherwise, pressing Enter inside any input submits the form to its
parent URL with no handler — full-page reload, query string appended,
user loses all unsaved input. Classic "why did my page just blank
out" symptom.

Heuristic: a form is OK if any of (a) action= attribute present,
(b) onsubmit= attribute, (c) the page contains
`document.getElementById('<form-id>').addEventListener('submit', ...)`
or `addEventListener('submit'`, or `data-no-submit` marker.

Output: form_submission_target_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "form_submission_target_report.json"
BASELINE_PATH = ROOT / "form_submission_target_baseline.json"

FORM_OPEN_RE = re.compile(r"<form\b([^>]*)>", re.IGNORECASE)
ATTR_RE = lambda name: re.compile(rf"""\b{name}\s*=\s*['"]([^'"]+)['"]""", re.IGNORECASE)


# Sentinel binding: name the L2 test `test('form_submission_target: ...')` for coverage credit.
CHECK_NAMES = ["form_submission_target"]


def _check_page(path: Path) -> list:
    body = path.read_text(encoding="utf-8", errors="replace")
    if "form-submit-allow" in body:
        return []
    issues = []
    for m in FORM_OPEN_RE.finditer(body):
        attrs = m.group(1)
        if ATTR_RE("action").search(attrs):
            continue
        if ATTR_RE("onsubmit").search(attrs):
            continue
        if re.search(r"""data-no-submit""", attrs, re.IGNORECASE):
            continue
        # Check global page-level submit listener wiring
        form_id_match = ATTR_RE("id").search(attrs)
        if form_id_match:
            form_id = form_id_match.group(1)
            # Look for getElementById('<id>').addEventListener('submit'
            pat = re.compile(
                rf"""['"]{re.escape(form_id)}['"]\s*\)?\.?[\s\S]{{0,80}}?addEventListener\s*\(\s*['"]submit['"]""",
                re.IGNORECASE,
            )
            if pat.search(body):
                continue
        # Fallback: ANY addEventListener('submit', ...) on the page
        if re.search(r"""addEventListener\s*\(\s*['"]submit['"]""", body):
            continue
        line_no = body.count("\n", 0, m.start()) + 1
        issues.append({"page": path.name, "line": line_no, "attrs": attrs.strip()[:120]})
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

    print(f"\n<form> Submission Target Validator (L0)")
    print("=" * 56)
    print(f"  pages scanned:    {scanned}")
    print(f"  drift:            {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — every <form> has action/onsubmit/submit listener.")
        return 0
    for i in issues[:25]:
        print(f"  {i['page']}:{i['line']}  <form {i['attrs']}>")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
