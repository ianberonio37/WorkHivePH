"""
<img> alt Coverage Validator (L0, ratcheted).
================================================
Every `<img>` MUST have an `alt` attribute (empty `alt=""` is fine
for decorative images — that's the explicit "no caption" signal to
screen readers). Without `alt`:
  - Screen readers fall back to reading the file name ("IMG_2347.jpg")
  - Lighthouse a11y score drops
  - Search engines lose the alt text signal for image search
  - When the image fails to load, the user sees nothing (alt would
    render in its place)

Exemptions: inline marker `alt-allow` within ±200 chars of the tag.

Output: img_alt_coverage_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "img_alt_coverage_report.json"
BASELINE_PATH = ROOT / "img_alt_coverage_baseline.json"

IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
ALT_RE = re.compile(r"""\balt\s*=\s*['"]""", re.IGNORECASE)


# Sentinel binding: name the L2 test `test('img_alt_coverage: ...')` for coverage credit.
CHECK_NAMES = ["img_alt_coverage"]


def _check_page(path: Path) -> list:
    issues = []
    body = path.read_text(encoding="utf-8", errors="replace")
    # Strip HTML comments
    body_uncommented = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    for m in IMG_RE.finditer(body_uncommented):
        tag = m.group(0)
        if "alt-allow" in body_uncommented[max(0, m.start()-200):m.end()+200]:
            continue
        if not ALT_RE.search(tag):
            issues.append({"page": path.name, "tag": tag[:160]})
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

    print(f"\n<img> alt Coverage Validator (L0)")
    print("=" * 56)
    print(f"  pages scanned:    {scanned}")
    print(f"  drift:            {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — every <img> declares an alt attribute.")
        return 0
    for i in issues[:25]:
        print(f"  {i['page']}  → {i['tag']}")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
