"""
fetch() Error Handling Validator (L0, ratcheted).
====================================================
Every `fetch(...)` call MUST have at least one of:
  - A surrounding `try { ... } catch` (await-style)
  - A `.catch(` somewhere on the same/next 3 chained .then()
  - Inside a helper named *Safe* / *try* / wrapped by `safeFetch`

Naked fetch().then().json() chains silently fail on:
  - Network errors (offline / DNS)
  - HTTP status errors (fetch resolves 4xx/5xx without rejecting)
  - Malformed JSON in the body (the .json() promise rejects)
The user sees a button click that does nothing. The dev sees no log.

Note: this is a STATIC heuristic — it can't prove flow-of-control.
But across 60+ pages it surfaces the obvious naked-fetch patterns.

Exemptions: `fetch-error-allow` within ±200 chars.

Output: fetch_error_handling_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "fetch_error_handling_report.json"
BASELINE_PATH = ROOT / "fetch_error_handling_baseline.json"

# Match `fetch(` as a function call — NOT `prefetch(`, `safeFetch(`, etc.
FETCH_RE = re.compile(r"(?<![\w$])fetch\s*\(", re.MULTILINE)


# Sentinel binding: name the L2 test `test('fetch_error_handling: ...')` for coverage credit.
CHECK_NAMES = ["fetch_error_handling"]


def _is_in_try(src: str, idx: int) -> bool:
    window = src[max(0, idx-1200): idx]
    depth = 0
    in_try = []
    i = 0
    while i < len(window):
        m = re.match(r"\btry\s*\{", window[i:])
        if m:
            in_try.append(depth); i += m.end(); depth += 1; continue
        c = window[i]
        if c == "{": depth += 1
        elif c == "}":
            depth -= 1
            in_try = [d for d in in_try if d < depth]
        i += 1
    return bool(in_try)


def _has_followup_catch(src: str, idx: int) -> bool:
    """Look ahead until the next standalone `fetch(` or end-of-function for
    `.catch(`. Long .then() chains can push the .catch past 1k chars."""
    window = src[idx: idx+3000]
    # Truncate at the next sibling fetch() call so we don't claim a later
    # chain's .catch covers this one.
    next_fetch = re.search(r"(?<![\w$])fetch\s*\(", window[10:])
    if next_fetch:
        window = window[: next_fetch.end() + 10]
    return ".catch(" in window


def _strip_comments_keep_lines(src: str) -> str:
    """Replace JS line + block comments with the same number of newlines so
    line numbers in matches remain accurate against the original file."""
    def _block_rep(m):
        return "\n" * m.group(0).count("\n")
    out = re.sub(r"/\*.*?\*/", _block_rep, src, flags=re.DOTALL)
    out = re.sub(r"//[^\n]*", "", out)
    # Strip HTML comments too (line-count preserving)
    out = re.sub(r"<!--.*?-->", _block_rep, out, flags=re.DOTALL)
    return out


SCRIPT_BLOCK_RE = re.compile(r"<script\b[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE)


def _scan_positions(body: str, path: Path) -> list:
    """For .html: return (line_no, match) only for fetch() inside <script>
    blocks (skips literal 'fetch(' in HTML text/prose). For .js: scan all."""
    src = _strip_comments_keep_lines(body)
    if path.suffix.lower() == ".html":
        regions = [(m.start(1), m.end(1)) for m in SCRIPT_BLOCK_RE.finditer(src)]
    else:
        regions = [(0, len(src))]
    out = []
    for m in FETCH_RE.finditer(src):
        idx = m.start()
        if not any(s <= idx < e for s, e in regions):
            continue
        out.append((idx, m.end()))
    return out


def _check_file(path: Path) -> list:
    issues = []
    body = path.read_text(encoding="utf-8", errors="replace")
    src = _strip_comments_keep_lines(body)
    for start, end in _scan_positions(body, path):
        if "fetch-error-allow" in body[max(0, start-300): end+200]:
            continue
        if _is_in_try(src, start):
            continue
        if _has_followup_catch(src, end):
            continue
        line_no = src.count("\n", 0, start) + 1
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

    print(f"\nfetch() Error Handling Validator (L0)")
    print("=" * 56)
    print(f"  files scanned:    {scanned}")
    print(f"  drift:            {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — every fetch() is in a try block or chained to .catch.")
        return 0
    for i in issues[:30]:
        print(f"  {i['file']}:{i['line']}")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
