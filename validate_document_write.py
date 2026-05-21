"""
document.write() Top-level Validator (L0, ratcheted).
======================================================
Top-level `document.write()` is a parser-blocking anti-pattern:
  - It synchronously rewrites the live DOM, blocking the parser.
  - Chrome intervention strips it for cross-origin sync <script src=...>.
  - It is incompatible with XHTML, async/defer loading, and SSR rehydration.
  - It silently wipes the current document if called after parsing completes.

The ONLY legitimate pattern is writing into a freshly-opened popup,
e.g. `const w = window.open(...); w.document.write(html); w.document.close();`
That target is a different document object and is not parser-blocking
for the current page. This validator allows that form.

Forward-only ratchet: baseline current count, never allow growth.

Output: document_write_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "document_write_report.json"
BASELINE_PATH = ROOT / "document_write_baseline.json"

# Capture the character (or start-of-line) immediately before `document` so we
# can distinguish bare `document.write(...)` (current document — forbidden)
# from `popup.document.write(...)` / `w.document.write(...)` (popup — allowed).
# A preceding `.` means it's a method call on something else, which we skip.
DOC_WRITE_RE = re.compile(
    r"(^|[^.\w$])document\.write(?:ln)?\s*\(",
    re.MULTILINE,
)
LINE_COMMENT_RE = re.compile(r"//[^\n]*")
BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)

# Sentinel binding: name the L2 test `test('document_write_top_level: ...')`.
CHECK_NAMES = ["document_write_top_level"]


def _strip(src: str) -> str:
    return BLOCK_COMMENT_RE.sub("", LINE_COMMENT_RE.sub("", src))


def _check_file(path: Path) -> list:
    issues = []
    body = path.read_text(encoding="utf-8", errors="replace")
    stripped = _strip(body)
    for m in DOC_WRITE_RE.finditer(stripped):
        line_no = stripped.count("\n", 0, m.start()) + 1
        window = body[max(0, m.start()-200): m.end()+200]
        if "document-write-allow" in window:
            continue
        issues.append({
            "file": str(path.relative_to(ROOT)).replace("\\", "/"),
            "line": line_no,
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
    for path in sorted(ROOT.glob("*.js")):
        if path.name == "sw.js": continue
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

    print(f"\ndocument.write() Top-level Validator (L0)")
    print("=" * 56)
    print(f"  files scanned:    {files_scanned}")
    print(f"  drift:            {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — no top-level document.write() calls.")
        return 0
    for i in issues[:25]:
        print(f"  {i['file']}:{i['line']}")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
