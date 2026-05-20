"""
External Link rel="noopener noreferrer" Validator (L0, ratcheted).
====================================================================
Every `<a target="_blank">` MUST set `rel="noopener noreferrer"` (or
at minimum `rel="noopener"`). Without it, the opened page can hijack
window.opener and rewrite the original tab's URL — classic reverse
tabnabbing. Modern browsers default to noopener for `target=_blank`,
but only for top-level `<a>` clicks; programmatic window.open() and
older browsers still need the explicit attribute. Lighthouse and
Mozilla MDN both flag this as a security issue.

Output: external_link_rel_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "external_link_rel_report.json"
BASELINE_PATH = ROOT / "external_link_rel_baseline.json"

# Match <a ...target="_blank"...> with any attribute order
A_TARGET_BLANK_RE = re.compile(
    r"""<a\b[^>]*\btarget\s*=\s*['"]_blank['"][^>]*>""", re.IGNORECASE
)
REL_RE = re.compile(r"""\brel\s*=\s*['"]([^'"]+)['"]""", re.IGNORECASE)


# Sentinel binding: name the L2 test `test('external_link_rel: ...')` for coverage credit.
CHECK_NAMES = ["external_link_rel"]


def _check_page(path: Path) -> list:
    issues = []
    body = path.read_text(encoding="utf-8", errors="replace")
    for m in A_TARGET_BLANK_RE.finditer(body):
        tag = m.group(0)
        # Allow inline marker
        if "noopener-allow" in body[max(0, m.start()-200):m.end()+200]:
            continue
        rel_match = REL_RE.search(tag)
        if not rel_match:
            issues.append({"page": path.name, "tag": tag[:160], "reason": "no rel attribute"})
            continue
        tokens = set(rel_match.group(1).lower().split())
        if "noopener" not in tokens and "noreferrer" not in tokens:
            issues.append({"page": path.name, "tag": tag[:160], "reason": f"rel='{rel_match.group(1)}' missing noopener/noreferrer"})
    return issues


def main() -> int:
    issues = []
    pages = sorted(ROOT.glob("*.html"))
    for path in pages:
        # Skip vendor / generated
        if path.name.startswith("_") or "node_modules" in str(path):
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

    print(f"\nExternal Link rel=noopener Validator (L0)")
    print("=" * 56)
    print(f"  pages scanned:    {len(pages)}")
    print(f"  drift:            {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — every <a target=_blank> has rel=noopener/noreferrer.")
        return 0
    for i in issues[:20]:
        print(f"  {i['page']}  {i['reason']}")
        print(f"     {i['tag']}")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
