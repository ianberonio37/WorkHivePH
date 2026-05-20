"""
Icon-Only Button aria-label Validator (L0, ratcheted).
==========================================================
A `<button>` whose visible content is ONLY a `<svg>` (icon-only)
MUST have an `aria-label` or `aria-labelledby` attribute. Screen
readers otherwise read it as "button" with no context — the user
has no idea what clicking it does.

Heuristic: button is icon-only if its inner content (after stripping
nested whitespace + comments) is exactly one `<svg>` element with no
sibling text nodes.

Exemption: `icon-button-label-allow` marker within ±200 chars.

Output: icon_button_label_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "icon_button_label_report.json"
BASELINE_PATH = ROOT / "icon_button_label_baseline.json"

BUTTON_RE = re.compile(r"<button\b([^>]*)>(.*?)</button>", re.IGNORECASE | re.DOTALL)
SVG_BLOCK_RE = re.compile(r"<svg\b[^>]*>.*?</svg>", re.IGNORECASE | re.DOTALL)
ARIA_ATTR_RE = re.compile(r"""\baria-label(?:ledby)?\s*=\s*['"][^'"]+['"]""", re.IGNORECASE)
TITLE_ATTR_RE = re.compile(r"""\btitle\s*=\s*['"][^'"]+['"]""", re.IGNORECASE)


# Sentinel binding: name the L2 test `test('icon_button_label: ...')` for coverage credit.
CHECK_NAMES = ["icon_button_label"]


def _check_page(path: Path) -> list:
    body = path.read_text(encoding="utf-8", errors="replace")
    body_clean = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    issues = []
    for m in BUTTON_RE.finditer(body_clean):
        attrs = m.group(1)
        inner = m.group(2)
        # Strip nested SVGs and whitespace from inner; if NOTHING remains,
        # it's icon-only.
        stripped = SVG_BLOCK_RE.sub("", inner).strip()
        # Also strip <span class="sr-only">...</span> screen-reader text
        # (which IS a valid accessibility hint, equivalent to aria-label).
        sr_only_re = re.compile(
            r"<span\b[^>]*\bclass\s*=\s*['\"][^'\"]*sr-only[^'\"]*['\"][^>]*>.*?</span>",
            re.IGNORECASE | re.DOTALL,
        )
        # Does the inner have sr-only span? If so, accept (it's the
        # accessible name).
        if sr_only_re.search(inner):
            continue
        if stripped:
            # Has text content — not icon-only, skip
            continue
        # Icon-only: must have aria-label / aria-labelledby
        if ARIA_ATTR_RE.search(attrs):
            continue
        # title="..." is also accepted as a fallback (less ideal but used)
        if TITLE_ATTR_RE.search(attrs):
            continue
        if "icon-button-label-allow" in body_clean[max(0, m.start()-200): m.end()+100]:
            continue
        line_no = body_clean.count("\n", 0, m.start()) + 1
        issues.append({"page": path.name, "line": line_no,
                       "preview": m.group(0)[:140].replace("\n", " ")})
    return issues


def main() -> int:
    issues = []
    pages = sorted(ROOT.glob("*.html"))
    scanned = 0
    for path in pages:
        if path.name.startswith("_"): continue
        if ".backup." in path.name or ".backup2." in path.name or path.name.endswith("-test.html"): continue
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

    print(f"\nIcon-Only Button aria-label Validator (L0)")
    print("=" * 56)
    print(f"  pages scanned:    {scanned}")
    print(f"  drift:            {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — every icon-only <button> has aria-label/title/sr-only.")
        return 0
    for i in issues[:20]:
        print(f"  {i['page']}:{i['line']}  {i['preview']}")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
