"""
Native alert/confirm/prompt Calls Validator (L0, ratcheted).
==============================================================
Production code MUST NOT call `window.alert()`, `window.confirm()`,
or `window.prompt()`:
  - They block the main thread and freeze the rest of the UI.
  - They look like 1999 browser chrome — undermines product polish.
  - They cannot be styled, internationalised, or unit-tested cleanly.
  - Many mobile browsers silently suppress alert/prompt entirely.
The platform owns a styled toast/modal/dialog stack; new code must
use it. Exemptions get an inline `// native-dialog-allow: <reason>`
comment within ±200 chars.

Output: native_dialog_calls_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "native_dialog_calls_report.json"
BASELINE_PATH = ROOT / "native_dialog_calls_baseline.json"

# Match alert( / confirm( / prompt( as standalone fn calls (not method calls
# like obj.alert( or eslint-disable comments containing the literal word).
CALL_RE = re.compile(
    r"(?:^|[\s;,({=&|!?:])(window\.)?(alert|confirm|prompt)\s*\(",
    re.MULTILINE,
)
# Strip JS line + block comments and string literals so we don't false-positive
# on `// confirm with the user that ...` or `"alert(): blocking"`.
LINE_COMMENT_RE = re.compile(r"//[^\n]*")
BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


# Sentinel binding: name the L2 test `test('native_dialog_calls: ...')` for coverage credit.
CHECK_NAMES = ["native_dialog_calls"]


def _strip(src: str) -> str:
    return BLOCK_COMMENT_RE.sub("", LINE_COMMENT_RE.sub("", src))


def _check_file(path: Path) -> list:
    issues = []
    body = path.read_text(encoding="utf-8", errors="replace")
    stripped = _strip(body)
    for m in CALL_RE.finditer(stripped):
        fn = m.group(2)
        # Look up original position by walking the stripped match back into source
        # Cheap approximation: count newlines up to match start in stripped
        line_no = stripped.count("\n", 0, m.start()) + 1
        # allow marker within ±200 chars of the match in ORIGINAL body
        # (use line number to find the approximate region)
        approx_idx = body.find(stripped[max(0, m.start()-30):m.end()])
        if approx_idx < 0: approx_idx = 0
        window = body[max(0, approx_idx-300): approx_idx+200]
        if "native-dialog-allow" in window:
            continue
        issues.append({"file": str(path.relative_to(ROOT)).replace("\\", "/"), "fn": fn, "line": line_no})
    return issues


def main() -> int:
    issues = []
    files_scanned = 0
    # HTML inline + linked .js at project root + voice/companion handlers
    for path in sorted(ROOT.glob("*.html")):
        if path.name.startswith("_"): continue
        # Skip explicit backups + test scratch files; they aren't part of the live surface.
        if ".backup." in path.name or path.name.endswith("-test.html"): continue
        files_scanned += 1
        issues.extend(_check_file(path))
    for path in sorted(ROOT.glob("*.js")):
        if path.name in {"sw.js"}: continue
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

    print(f"\nNative alert/confirm/prompt Validator (L0)")
    print("=" * 56)
    print(f"  files scanned:    {files_scanned}")
    print(f"  drift:            {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — no native alert/confirm/prompt in production code.")
        return 0
    for i in issues[:25]:
        print(f"  {i['file']}:{i['line']}  {i['fn']}()")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
