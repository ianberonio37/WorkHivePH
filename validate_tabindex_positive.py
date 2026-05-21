"""
Positive tabindex Validator (L0, ratcheted).
============================================
Any `tabindex` value greater than 0 is a WCAG 2.1 anti-pattern:
  - It overrides the natural DOM tab order, breaking expected flow.
  - It promotes the element ahead of every other focusable on the page,
    confusing screen-reader users and keyboard navigators.
  - It is fragile: adding a new positive tabindex anywhere else shuffles
    the entire page's tab order in non-obvious ways.

Only two values are correct:
  - `tabindex="0"` to make a non-natively-focusable element focusable.
  - `tabindex="-1"` to make it focusable only via .focus(), not Tab.

Forward-only ratchet: baseline current count, never allow growth.

Output: tabindex_positive_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "tabindex_positive_report.json"
BASELINE_PATH = ROOT / "tabindex_positive_baseline.json"

# tabindex="N" where N starts with 1-9 (matches 1, 2, ..., 10, 99, etc).
# Excludes the only-allowed values 0 and -1.
TABINDEX_POS_RE = re.compile(
    r"""tabindex\s*=\s*['"][1-9]\d*['"]""",
)

CHECK_NAMES = ["tabindex_positive"]


def _check_file(path: Path) -> list:
    issues = []
    body = path.read_text(encoding="utf-8", errors="replace")
    for m in TABINDEX_POS_RE.finditer(body):
        window = body[max(0, m.start()-200): m.end()+200]
        if "tabindex-positive-allow" in window:
            continue
        line_no = body.count("\n", 0, m.start()) + 1
        issues.append({
            "file": str(path.relative_to(ROOT)).replace("\\", "/"),
            "line": line_no,
            "match": m.group(0),
        })
    return issues


def main() -> int:
    issues = []
    files_scanned = 0
    for path in sorted(ROOT.glob("*.html")):
        if path.name.startswith("_"): continue
        if ".backup." in path.name or path.name.endswith("-test.html"): continue
        files_scanned += 1
        issues.extend(_check_file(path))

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
        "summary": {"files_scanned": files_scanned, "drift": drift, "baseline": baseline},
        "issues": issues,
    }, indent=2), encoding="utf-8")

    print(f"\nPositive tabindex Validator (L0)")
    print("=" * 56)
    print(f"  files scanned:    {files_scanned}")
    print(f"  drift:            {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — no positive tabindex values.")
        return 0
    for i in issues[:25]:
        print(f"  {i['file']}:{i['line']}  {i['match']}")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
