"""
javascript:void(0) Anti-Pattern Validator (L0, ratcheted).
=============================================================
Production HTML SHOULD NOT use `<a href="javascript:void(0)">` or
`<a href="javascript:...">`. The anti-patterns it covers:
  - `<a href="javascript:void(0)">` — clickable element that "is not"
    a link; use `<button type="button">` instead (correct semantics +
    keyboard + screen reader)
  - `<a href="#">` with `onclick="return false"` — also flagged; same
    "fake link" anti-pattern (the URL hash leaks into history)
  - `<a href="javascript:doThing()">` — XSS vector if doThing's args
    are user-controlled; URL parsers also choke on the inline JS

Use `<button>` for actions; reserve `<a href>` for navigation.

Exemption: `javascript-href-allow` marker within ±200 chars.

Output: javascript_href_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "javascript_href_report.json"
BASELINE_PATH = ROOT / "javascript_href_baseline.json"

JS_HREF_RE = re.compile(
    r"""<a\b[^>]*\bhref\s*=\s*['"]javascript:[^'"]*['"][^>]*>""",
    re.IGNORECASE,
)
HASH_HREF_RE = re.compile(
    r"""<a\b[^>]*\bhref\s*=\s*['"]#['"][^>]*\bonclick\s*=\s*['"][^'"]*return\s+false[^'"]*['"][^>]*>""",
    re.IGNORECASE,
)


# Sentinel binding: name the L2 test `test('javascript_href: ...')` for coverage credit.
CHECK_NAMES = ["javascript_href"]


def _check_page(path: Path) -> list:
    body = path.read_text(encoding="utf-8", errors="replace")
    body_clean = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    issues = []
    for pat, kind in ((JS_HREF_RE, "javascript:"), (HASH_HREF_RE, "href=# + return false")):
        for m in pat.finditer(body_clean):
            if "javascript-href-allow" in body_clean[max(0, m.start()-200): m.end()+100]:
                continue
            line_no = body_clean.count("\n", 0, m.start()) + 1
            issues.append({"page": path.name, "line": line_no, "kind": kind,
                           "tag": m.group(0)[:160]})
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

    print(f"\njavascript:void(0) Anti-Pattern Validator (L0)")
    print("=" * 56)
    print(f"  pages scanned:    {scanned}")
    print(f"  drift:            {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — no <a href='javascript:...'> or href=#+return false fake-link patterns.")
        return 0
    for i in issues[:20]:
        print(f"  {i['page']}:{i['line']}  ({i['kind']}) {i['tag']}")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
