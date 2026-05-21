"""
<table> Accessible Name Validator (L0, ratcheted).
=====================================================
Every `<table>` (data table, not layout table) MUST have an
accessible name via one of:
  - `<caption>` element as first child
  - `aria-label="..."` on the table tag
  - `aria-labelledby="<id>"` pointing to a heading
  - `role="presentation"` (only valid for layout tables — explicit
    opt-out)

Without one, screen readers announce "table, N columns, M rows"
with no idea what data the table contains.

Exemption: `table-name-allow` marker within ±200 chars (e.g. for
table tags that are clearly purely-decorative grid layouts in
inline templates that don't render the actual table).

Output: table_accessible_name_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "table_accessible_name_report.json"
BASELINE_PATH = ROOT / "table_accessible_name_baseline.json"

TABLE_RE = re.compile(r"<table\b([^>]*)>(.*?)</table>", re.IGNORECASE | re.DOTALL)
CAPTION_RE = re.compile(r"<caption\b", re.IGNORECASE)
ARIA_NAME_RE = re.compile(r"""\baria-label(?:ledby)?\s*=\s*['"][^'"]+['"]""", re.IGNORECASE)
ROLE_PRES_RE = re.compile(r"""\brole\s*=\s*['"]presentation['"]""", re.IGNORECASE)
ROLE_NONE_RE = re.compile(r"""\brole\s*=\s*['"]none['"]""", re.IGNORECASE)


# Sentinel binding: name the L2 test `test('table_accessible_name: ...')` for coverage credit.
CHECK_NAMES = ["table_accessible_name"]


def _check_page(path: Path) -> list:
    body = path.read_text(encoding="utf-8", errors="replace")
    # Replace HTML comments with same-length spaces so offsets line up with body.
    body_clean = re.sub(r"<!--.*?-->",
                        lambda m: " " * len(m.group(0)),
                        body, flags=re.DOTALL)
    issues = []
    for m in TABLE_RE.finditer(body_clean):
        attrs = m.group(1)
        inner = m.group(2)
        if ARIA_NAME_RE.search(attrs):
            continue
        if ROLE_PRES_RE.search(attrs) or ROLE_NONE_RE.search(attrs):
            continue
        if CAPTION_RE.search(inner[:500]):
            continue
        # Search RAW body for the marker (comments stripped from body_clean).
        if "table-name-allow" in body[max(0, m.start()-200): m.end()+100]:
            continue
        line_no = body_clean.count("\n", 0, m.start()) + 1
        issues.append({"page": path.name, "line": line_no,
                       "preview": m.group(0)[:120].replace("\n", " ")})
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

    print(f"\n<table> Accessible Name Validator (L0)")
    print("=" * 56)
    print(f"  pages scanned:    {scanned}")
    print(f"  drift:            {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — every <table> has caption/aria-label/role=presentation.")
        return 0
    for i in issues[:25]:
        print(f"  {i['page']}:{i['line']}  {i['preview']}")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
