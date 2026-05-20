"""
<meta http-equiv="refresh"> Anti-Pattern Validator (L0, ratcheted).
=====================================================================
Production HTML SHOULD NOT use `<meta http-equiv="refresh" content="...">`.
Reasons:
  - Page jumps that disorient users (especially screen readers).
  - WCAG 2.2.1 violation — auto-redirect with no user control.
  - Bots and SEO crawlers de-rank these.
  - Refresh-counters cancel out user clicks on dynamic UI.

Use JavaScript `location.href = '...'` (controlled, cancellable) or
server-side 30x redirects instead.

Exemption: `meta-refresh-allow` marker.

Output: meta_refresh_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "meta_refresh_report.json"
BASELINE_PATH = ROOT / "meta_refresh_baseline.json"

META_REFRESH_RE = re.compile(
    r"""<meta\b[^>]*\bhttp-equiv\s*=\s*['"]refresh['"][^>]*>""",
    re.IGNORECASE,
)


# Sentinel binding: name the L2 test `test('meta_refresh: ...')` for coverage credit.
CHECK_NAMES = ["meta_refresh"]


def _check_page(path: Path) -> list:
    body = path.read_text(encoding="utf-8", errors="replace")
    body_clean = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    issues = []
    for m in META_REFRESH_RE.finditer(body_clean):
        # Allow markers commonly live INSIDE HTML comments above the tag,
        # so check the ORIGINAL body (which still has the comments).
        tag = m.group(0)
        orig_idx = body.find(tag[:60])
        if orig_idx < 0: orig_idx = 0
        if "meta-refresh-allow" in body[max(0, orig_idx-400): orig_idx+200]:
            continue
        line_no = body_clean.count("\n", 0, m.start()) + 1
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

    print(f"\n<meta http-equiv=refresh> Validator (L0)")
    print("=" * 56)
    print(f"  pages scanned:    {scanned}")
    print(f"  drift:            {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — no <meta http-equiv=refresh> auto-redirects.")
        return 0
    for i in issues[:20]:
        print(f"  {i['page']}:{i['line']}  {i['tag']}")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
