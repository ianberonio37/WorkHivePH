"""
SQL LIKE / ILIKE Escape Validator (L0, ratcheted).
=====================================================
Every PostgREST `.ilike()` / `.like()` filter that interpolates a
user-controlled value MUST escape the SQL `LIKE` wildcards (`%` and
`_`) BEFORE concatenating into the pattern. Otherwise:
  - A search for `"a%"` matches everything starting with `a` (user
    expected a literal `a%`).
  - A username containing `_` matches any character at that position
    (privacy leak in user-listing queries).
  - On full-text searches across many rows the wildcard explosion
    can DoS the database.

Heuristic: flag `.ilike(\`%${X}%\`)` patterns where X is a JS
expression. The PostgREST library does NOT auto-escape; the caller
must. Acceptable forms:
  - `.ilike(\`%${X.replace(/[%_]/g, m => '\\\\' + m)}%\`)`
  - Helper `escapeLikePattern(X)` / `likeEscape(X)`
  - `like-escape-allow` marker for known-safe constants

Output: like_escape_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "like_escape_report.json"
BASELINE_PATH = ROOT / "like_escape_baseline.json"

# .ilike(<arg>) or .like(<arg>)
LIKE_CALL_RE = re.compile(
    r"\.(?:i?like)\s*\(\s*['\"`]([^'\"`]*\$\{[^}]+\}[^'\"`]*)['\"`]\s*\)",
    re.IGNORECASE,
)
# Also catch the 2-arg variant: .ilike('col', `%${x}%`)
LIKE_2ARG_RE = re.compile(
    r"\.(?:i?like)\s*\(\s*['\"][^'\"]+['\"]\s*,\s*['\"`]([^'\"`]*\$\{[^}]+\}[^'\"`]*)['\"`]\s*\)",
    re.IGNORECASE,
)

ESCAPE_HINT_RE = re.compile(
    r"(escapeLike|likeEscape|escapeLikePattern"
    r"|\.replace\s*\(\s*/\[%_\]/"     # combined char-class form
    r"|\.replace\s*\(\s*/%/[\w]*\s*,\s*['\"]\\\\%['\"]"  # .replace(/%/g, '\\%')
    r")",
    re.IGNORECASE,
)


# Sentinel binding: name the L2 test `test('like_escape: ...')` for coverage credit.
CHECK_NAMES = ["like_escape"]


def _check_file(path: Path) -> list:
    body = path.read_text(encoding="utf-8", errors="replace")
    issues = []
    # Pre-pass: find every variable defined by an escape helper anywhere
    # in this file. A LIKE call whose interpolation root matches one of
    # these names is considered escaped regardless of distance.
    escaped_vars: set[str] = set()
    var_def_re = re.compile(
        r"(?:const|let|var)\s+(\w+)\s*=\s*[^\n;]*?"
        r"(?:escapeLike|likeEscape|escapeLikePattern"
        r"|\.replace\s*\(\s*/\[%_\]/"
        r"|\.replace\s*\(\s*/%/[\w]*\s*,\s*['\"]\\\\%['\"])",
        re.IGNORECASE | re.DOTALL,
    )
    for vm in var_def_re.finditer(body):
        escaped_vars.add(vm.group(1))

    for pat in (LIKE_CALL_RE, LIKE_2ARG_RE):
        for m in pat.finditer(body):
            if "like-escape-allow" in body[max(0, m.start()-300): m.end()+100]:
                continue
            interp = m.group(1)
            inner = re.search(r"\$\{\s*([^}]+?)\s*\}", interp)
            if inner and ESCAPE_HINT_RE.search(inner.group(1)):
                continue
            # If interpolation root matches a file-level escape-helper var, accept.
            if inner:
                root_var = inner.group(1).split(".")[0].strip()
                if root_var in escaped_vars:
                    continue
            line_no = body.count("\n", 0, m.start()) + 1
            issues.append({"file": str(path.relative_to(ROOT)).replace("\\", "/"),
                           "line": line_no, "pattern": interp[:120]})
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
    # Also scan edge fns
    fn_dir = ROOT / "supabase" / "functions"
    if fn_dir.exists():
        for path in sorted(fn_dir.rglob("*.ts")):
            if "_archive" in path.parts: continue
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

    print(f"\nSQL LIKE Escape Validator (L0)")
    print("=" * 56)
    print(f"  files scanned:    {scanned}")
    print(f"  drift:            {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — every .ilike()/.like() with template interpolation escapes wildcards.")
        return 0
    for i in issues[:20]:
        print(f"  {i['file']}:{i['line']}  pattern={i['pattern']}")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
