"""
JSON.parse Safety Validator (L0, ratcheted).
================================================
Every `JSON.parse(x)` MUST be inside a `try {}` block (or use a safe
wrapper like `safeJsonParse`/`tryParse`). Naked `JSON.parse()` on
external data throws SyntaxError on malformed input, crashes the
function, and — in async paths — leaves a rejected promise that
either silently fails or surfaces as "[object Object]" in a toast.

Common sources of bad JSON:
  - localStorage values from a previous app version (schema drift)
  - PostgREST error responses (HTML when proxy is down)
  - Edge function responses on cold start failures
  - User-pasted clipboard content

Exemptions: inline marker `json-parse-allow` within ±200 chars.

Output: json_parse_safety_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "json_parse_safety_report.json"
BASELINE_PATH = ROOT / "json_parse_safety_baseline.json"

PARSE_RE = re.compile(r"\bJSON\.parse\s*\(", re.IGNORECASE)


# Sentinel binding: name the L2 test `test('json_parse_safety: ...')` for coverage credit.
CHECK_NAMES = ["json_parse_safety"]


def _is_in_try(src: str, idx: int) -> bool:
    """Heuristic: scan backward up to 800 chars; if a `try {` appears
    without a matching `}` before the parse call, we're inside a try."""
    window = src[max(0, idx-800): idx]
    # Walk forward through the window tracking depth
    depth = 0
    in_try_depths = []
    i = 0
    while i < len(window):
        # try {
        m = re.match(r"\btry\s*\{", window[i:])
        if m:
            in_try_depths.append(depth)
            i += m.end()
            depth += 1
            continue
        c = window[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            # If we just closed the depth at which a try started, pop it
            in_try_depths = [d for d in in_try_depths if d < depth]
        i += 1
    return bool(in_try_depths)


def _check_file(path: Path) -> list:
    issues = []
    body = path.read_text(encoding="utf-8", errors="replace")
    # Track every JSON.parse position in the ORIGINAL body so reported line
    # numbers match the file the developer reads.
    for m in PARSE_RE.finditer(body):
        if "json-parse-allow" in body[max(0, m.start()-300):m.end()+200]:
            continue
        if _is_in_try(body, m.start()):
            continue
        line_no = body.count("\n", 0, m.start()) + 1
        issues.append({"file": str(path.relative_to(ROOT)).replace("\\", "/"), "line": line_no})
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
        if path.name == "sw.js": continue
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

    print(f"\nJSON.parse Safety Validator (L0)")
    print("=" * 56)
    print(f"  files scanned:    {scanned}")
    print(f"  drift:            {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — every JSON.parse() is guarded by a try block.")
        return 0
    for i in issues[:25]:
        print(f"  {i['file']}:{i['line']}")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
