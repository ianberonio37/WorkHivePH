"""
console.log Production Drift Validator (L0, ratcheted).
==========================================================
Production HTML/JS SHOULD NOT contain naked `console.log(...)` calls
in non-error paths. Acceptable:
  - `console.error(...)` / `console.warn(...)` — legitimate problem signals
  - `console.log` inside a catch block, behind `if (DEBUG)`, or marked
    `console-log-allow`
  - `console.info(...)` — context-dependent, accepted with marker only

Drift forms tracked:
  - `console.log(` calls outside try { ... } catch
  - NOT preceded by `if (DEBUG)` / `if (_DEBUG)` / `if (window.DEBUG)`

Output: console_log_drift_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "console_log_drift_report.json"
BASELINE_PATH = ROOT / "console_log_drift_baseline.json"

CONSOLE_LOG_RE = re.compile(r"(?<![\w$])console\.log\s*\(")
DEBUG_GUARD_RE = re.compile(r"\bif\s*\(\s*(?:window\.)?(?:_?DEBUG|VERBOSE|TRACE)\b", re.IGNORECASE)

SCRIPT_BLOCK_RE = re.compile(r"<script\b[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE)


# Sentinel binding: name the L2 test `test('console_log_drift: ...')` for coverage credit.
CHECK_NAMES = ["console_log_drift"]


def _strip_comments_keep_lines(src: str) -> str:
    # Preserve character offsets so downstream marker checks that index
    # into the RAW body using offsets from this stripped body line up.
    # Replace each character with a space (except newlines).
    def _block_rep(m):
        return "".join(c if c == "\n" else " " for c in m.group(0))
    out = re.sub(r"/\*.*?\*/", _block_rep, src, flags=re.DOTALL)
    out = re.sub(r"//[^\n]*", _block_rep, out)
    out = re.sub(r"<!--.*?-->", _block_rep, out, flags=re.DOTALL)
    return out


def _is_in_catch_block(src: str, idx: int) -> bool:
    """A console.log inside a catch{} block is legitimate (error logging).
    Detection: walk backward through the window. If we encounter a `catch
    (...)` `{` before an unmatched `}` or `try {`, the call is inside catch."""
    window = src[max(0, idx-1500): idx]
    depth = 0
    in_catch = []
    i = 0
    while i < len(window):
        m = re.match(r"\bcatch\s*(?:\(\s*[^)]*\))?\s*\{", window[i:])
        if m:
            in_catch.append(depth); i += m.end(); depth += 1; continue
        c = window[i]
        if c == "{": depth += 1
        elif c == "}":
            depth -= 1
            in_catch = [d for d in in_catch if d < depth]
        i += 1
    return bool(in_catch)


def _check_file(path: Path) -> list:
    issues = []
    body = path.read_text(encoding="utf-8", errors="replace")
    src = _strip_comments_keep_lines(body)
    if path.suffix.lower() == ".html":
        regions = [(m.start(1), m.end(1)) for m in SCRIPT_BLOCK_RE.finditer(src)]
    else:
        regions = [(0, len(src))]
    for m in CONSOLE_LOG_RE.finditer(src):
        idx = m.start()
        if not any(s <= idx < e for s, e in regions):
            continue
        # Window +400 so trailing markers on long lines (typical for booted-as
        # diagnostics) still match. body has full chars; src has chars stripped
        # in-place so offsets line up.
        if "console-log-allow" in body[max(0, idx-300): idx+400]:
            continue
        # Allow inside catch blocks
        if _is_in_catch_block(src, idx):
            continue
        # Allow under DEBUG guard (within preceding 200 chars)
        if DEBUG_GUARD_RE.search(src[max(0, idx-300): idx]):
            continue
        line_no = src.count("\n", 0, idx) + 1
        issues.append({"file": str(path.relative_to(ROOT)).replace("\\", "/"),
                       "line": line_no})
    return issues


def main() -> int:
    issues = []
    scanned = 0
    for path in sorted(ROOT.glob("*.html")):
        if path.name.startswith("_"): continue
        if ".backup." in path.name or path.name.endswith("-test.html"): continue
        scanned += 1
        issues.extend(_check_file(path))
    for path in sorted(ROOT.glob("*.js")):
        if path.name in {"sw.js"}: continue
        scanned += 1
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
        "summary": {"files_scanned": scanned, "drift": drift, "baseline": baseline},
        "issues": issues,
    }, indent=2), encoding="utf-8")

    print(f"\nconsole.log Production Drift Validator (L0)")
    print("=" * 56)
    print(f"  files scanned:    {scanned}")
    print(f"  drift:            {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — no console.log in production paths (catch blocks + DEBUG guards excluded).")
        return 0
    for i in issues[:15]:
        print(f"  {i['file']}:{i['line']}")
    if len(issues) > 15:
        print(f"  ... and {len(issues)-15} more")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
