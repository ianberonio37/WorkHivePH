"""
setTimeout/setInterval String Argument Validator (L0, ratcheted).
=================================================================
`setTimeout("code", ms)` and `setInterval("code", ms)` with a string
first argument are eval-equivalent:
  - The string is parsed + executed in the global scope at fire time.
  - CSP `script-src 'unsafe-eval'` is required for them to run.
  - No closures, no captured variables, no static analysis.
  - Indistinguishable from `eval(s)` for a security review.

Always pass a function reference instead:
  setTimeout(() => doThing(), 1000);
  setInterval(refreshUI, 5000);

Forward-only ratchet: baseline current count, never allow growth.

Output: settimeout_string_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "settimeout_string_report.json"
BASELINE_PATH = ROOT / "settimeout_string_baseline.json"

# Match `setTimeout(` / `setInterval(` followed by optional whitespace then a
# string literal (single or double or backtick). Skip a method-call form like
# `obj.setTimeout(...)` since those are uncommon and not the standard global.
TIMER_STRING_RE = re.compile(
    r"(^|[^.\w$])(setTimeout|setInterval)\s*\(\s*(['\"`])",
    re.MULTILINE,
)
LINE_COMMENT_RE = re.compile(r"//[^\n]*")
BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)

CHECK_NAMES = ["settimeout_string_arg"]


def _strip(src: str) -> str:
    return BLOCK_COMMENT_RE.sub("", LINE_COMMENT_RE.sub("", src))


def _check_file(path: Path) -> list:
    issues = []
    body = path.read_text(encoding="utf-8", errors="replace")
    stripped = _strip(body)
    for m in TIMER_STRING_RE.finditer(stripped):
        line_no = stripped.count("\n", 0, m.start()) + 1
        window = body[max(0, m.start()-200): m.end()+200]
        if "settimeout-string-allow" in window:
            continue
        issues.append({
            "file": str(path.relative_to(ROOT)).replace("\\", "/"),
            "fn": m.group(2),
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

    print(f"\nsetTimeout/setInterval String Arg Validator (L0)")
    print("=" * 56)
    print(f"  files scanned:    {files_scanned}")
    print(f"  drift:            {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — no string-argument timer calls.")
        return 0
    for i in issues[:25]:
        print(f"  {i['file']}:{i['line']}  {i['fn']}()")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
