"""
Viewport user-scalable=no Validator (L0, ratcheted).
=====================================================
`<meta name="viewport" content="... user-scalable=no ...">` (also
`maximum-scale=1`) disables pinch-zoom on mobile, which is a WCAG 2.1
Success Criterion 1.4.4 violation:
  - Low-vision users (the platform's core demographic includes 50+
    veteran maintenance engineers) cannot zoom small UI to read it.
  - iOS still grants zoom by default, masking the bug on Apple devices
    while Android workers lose access.
  - Common cause is copy-pasted boilerplate that nobody ever revisits.

Modern responsive layouts have no reason to disable zoom. If a specific
canvas / WebGL / map surface genuinely needs it, scope the lock to that
element rather than the whole document, and tag the meta with
`<!-- viewport-scale-allow: <reason> -->`.

Forward-only ratchet: baseline current count, never allow growth.

Output: viewport_user_scalable_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "viewport_user_scalable_report.json"
BASELINE_PATH = ROOT / "viewport_user_scalable_baseline.json"

# Match viewport meta with user-scalable=no/0 or maximum-scale=1
# (both deny pinch-zoom). Permissive on whitespace + quoting.
VIEWPORT_RE = re.compile(
    r"""<meta\b[^>]*name\s*=\s*['"]viewport['"][^>]*content\s*=\s*['"]([^'"]+)['"]""",
    re.IGNORECASE,
)
BLOCKS_ZOOM_RE = re.compile(
    r"user-scalable\s*=\s*(?:no|0)|maximum-scale\s*=\s*1(?:\.0+)?(?!\d)",
    re.IGNORECASE,
)

CHECK_NAMES = ["viewport_user_scalable"]


def _check_file(path: Path) -> list:
    issues = []
    body = path.read_text(encoding="utf-8", errors="replace")
    for m in VIEWPORT_RE.finditer(body):
        content = m.group(1)
        if not BLOCKS_ZOOM_RE.search(content):
            continue
        window = body[max(0, m.start()-200): m.end()+200]
        if "viewport-scale-allow" in window:
            continue
        line_no = body.count("\n", 0, m.start()) + 1
        issues.append({
            "file": str(path.relative_to(ROOT)).replace("\\", "/"),
            "line": line_no,
            "content": content,
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

    print(f"\nViewport user-scalable=no Validator (L0)")
    print("=" * 56)
    print(f"  files scanned:    {files_scanned}")
    print(f"  drift:            {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — viewport allows pinch-zoom everywhere.")
        return 0
    for i in issues[:25]:
        print(f"  {i['file']}:{i['line']}  {i['content']}")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
