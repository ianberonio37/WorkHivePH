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
# These files are HTML, and an HTML comment is not code either. alert-hub.html was reported for the
# prose "every control names ITS alert (ledger C33...)" inside <!-- ... -->, which no browser executes.
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


# Sentinel binding: name the L2 test `test('native_dialog_calls: ...')` for coverage credit.
CHECK_NAMES = ["native_dialog_calls"]


def _blank(m: "re.Match[str]") -> str:
    """Replace a comment with spaces, KEEPING its newlines, so offsets and line numbers survive."""
    return "".join("\n" if ch == "\n" else " " for ch in m.group(0))


def _strip(src: str) -> str:
    # ★OFFSET-PRESERVING, AND THAT IS THE WHOLE FIX (2026-09-28). This used to DELETE comment text
    # (sub("")), which shifted every offset after the first comment. Two things broke as a result and
    # both were silent:
    #   1. `line_no` came from the stripped text, so reported lines drifted from the real file - the
    #      run that found these sites pointed at index.html:3828, a line reading
    #      `errEl.classList.remove('hidden')`.
    #   2. The documented `// native-dialog-allow: <reason>` exemption COULD NEVER FIRE for any call
    #      that had a comment above it: the lookup did `body.find(stripped[start-30:end])`, and those
    #      30 leading characters contained the collapsed comment, so `find` returned -1, `approx_idx`
    #      fell back to 0, and the marker window became the first 200 bytes of the FILE. The mechanism
    #      the module docstring advertises was dead on arrival for exactly the sites that need it.
    # Blanking to spaces keeps every index identical to the original, so the match position IS the
    # original position and the window around it is the real neighbourhood.
    out = HTML_COMMENT_RE.sub(_blank, src)
    out = BLOCK_COMMENT_RE.sub(_blank, out)
    return LINE_COMMENT_RE.sub(_blank, out)


def _check_file(path: Path) -> list:
    issues = []
    body = path.read_text(encoding="utf-8", errors="replace")
    stripped = _strip(body)
    assert len(stripped) == len(body), "the stripper must preserve offsets"
    for m in CALL_RE.finditer(stripped):
        fn = m.group(2)
        line_no = body.count("\n", 0, m.start()) + 1
        # the allow marker, within the real neighbourhood of the real position
        window = body[max(0, m.start() - 300): m.start() + 200]
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
