"""
setTimeout / setInterval Cleanup Validator (L0, ratcheted).
=============================================================
A page that calls `setInterval(...)` MUST also call `clearInterval(...)`
somewhere on the same page (or use a `clear-interval-allow` marker).
Otherwise the timer keeps firing forever — leaking memory, hammering
the DB on each tick, or sending duplicate notifications after the user
navigates away.

setTimeout is held to a softer rule: a page that calls setTimeout AT
LEAST 10 times must also have at least one clearTimeout call. Most
setTimeouts are short-lived and self-completing, but a high count
suggests workflow-driven timers (debounce, polling) that should be
cancellable.

Output: timer_cleanup_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "timer_cleanup_report.json"
BASELINE_PATH = ROOT / "timer_cleanup_baseline.json"

SET_INTERVAL_RE   = re.compile(r"(?<![\w$])setInterval\s*\(")
CLEAR_INTERVAL_RE = re.compile(r"(?<![\w$])clearInterval\s*\(")
SET_TIMEOUT_RE    = re.compile(r"(?<![\w$])setTimeout\s*\(")
CLEAR_TIMEOUT_RE  = re.compile(r"(?<![\w$])clearTimeout\s*\(")


# Sentinel binding: name the L2 test `test('timer_cleanup: ...')` for coverage credit.
CHECK_NAMES = ["timer_cleanup"]


SCRIPT_BLOCK_RE = re.compile(r"<script\b[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE)


def _script_text(body: str) -> str:
    """For .html files, only count timer calls inside <script> blocks."""
    return "\n".join(m.group(1) for m in SCRIPT_BLOCK_RE.finditer(body))


def _check_file(path: Path) -> list:
    body = path.read_text(encoding="utf-8", errors="replace")
    if "timer-cleanup-allow" in body:
        return []
    if path.suffix.lower() == ".html":
        src = _script_text(body)
    else:
        src = body
    # Strip line/block comments
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    src = re.sub(r"//[^\n]*", "", src)

    n_interval   = len(SET_INTERVAL_RE.findall(src))
    n_clear_int  = len(CLEAR_INTERVAL_RE.findall(src))
    n_timeout    = len(SET_TIMEOUT_RE.findall(src))
    n_clear_to   = len(CLEAR_TIMEOUT_RE.findall(src))

    issues = []
    if n_interval > 0 and n_clear_int == 0:
        issues.append({"file": str(path.relative_to(ROOT)).replace("\\", "/"),
                       "kind": "setInterval", "calls": n_interval, "clears": 0})
    if n_timeout >= 10 and n_clear_to == 0:
        issues.append({"file": str(path.relative_to(ROOT)).replace("\\", "/"),
                       "kind": "setTimeout", "calls": n_timeout, "clears": 0})
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

    print(f"\nTimer Cleanup Validator (L0)")
    print("=" * 56)
    print(f"  files scanned:    {scanned}")
    print(f"  drift:            {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — every setInterval has a matching clearInterval (and high-count setTimeout has clearTimeout).")
        return 0
    for i in issues[:20]:
        print(f"  {i['file']}  ({i['kind']}: {i['calls']} calls, {i['clears']} clears)")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
