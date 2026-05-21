"""
Empty catch{} Validator (L0, ratcheted).
========================================
A `catch` clause whose body is empty (or contains only comments) silently
swallows every error in the try-block. Real-world consequences:
  - Fetches that quietly fail leave the UI stuck in a loading state.
  - JSON.parse errors hide schema drift until the bug looks unrelated.
  - localStorage quota / private-browsing failures vanish without a toast.
  - getElementById misses don't surface as "this feature is broken".

Rule: catch blocks must do *something* — log, surface a toast, fall back,
or rethrow. If swallowing is genuinely intentional, attach an
`// empty-catch-allow: <reason>` marker within +-200 chars of the catch.

Forward-only ratchet: baseline today's count, never let it grow. Fixes
that remove silent swallows tighten the baseline automatically.

Output: empty_catch_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "empty_catch_report.json"
BASELINE_PATH = ROOT / "empty_catch_baseline.json"

# Catch body that is empty OR contains only whitespace and JS line/block comments.
# Matches both `catch (e) {}` and binding-free `catch {}` (ES2019).
EMPTY_OR_COMMENT_ONLY_CATCH_RE = re.compile(
    r"catch\s*(?:\([^)]*\))?\s*\{"
    r"(?:\s*(?://[^\n]*|/\*[^*]*\*+(?:[^/*][^*]*\*+)*/))*"
    r"\s*\}",
    re.DOTALL,
)

# Sentinel binding: name the L2 test `test('empty_catch: ...')` for coverage credit.
CHECK_NAMES = ["empty_catch"]


def _check_file(path: Path) -> list:
    issues = []
    body = path.read_text(encoding="utf-8", errors="replace")
    for m in EMPTY_OR_COMMENT_ONLY_CATCH_RE.finditer(body):
        # +-200 char window around the match to look for the opt-out marker.
        window = body[max(0, m.start()-200): m.end()+200]
        if "empty-catch-allow" in window:
            continue
        line_no = body.count("\n", 0, m.start()) + 1
        issues.append({
            "file": str(path.relative_to(ROOT)).replace("\\", "/"),
            "line": line_no,
        })
    return issues


def main() -> int:
    issues = []
    files_scanned = 0
    # HTML inline scripts + linked .js at project root.
    for path in sorted(ROOT.glob("*.html")):
        if path.name.startswith("_"): continue
        if ".backup." in path.name or path.name.endswith("-test.html"): continue
        files_scanned += 1
        issues.extend(_check_file(path))
    for path in sorted(ROOT.glob("*.js")):
        if path.name == "sw.js": continue  # minified-ish service worker
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

    print(f"\nEmpty catch{{}} Validator (L0)")
    print("=" * 56)
    print(f"  files scanned:    {files_scanned}")
    print(f"  drift:            {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — no empty catch blocks.")
        return 0
    for i in issues[:25]:
        print(f"  {i['file']}:{i['line']}")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
