"""
Date Arithmetic Safety -- WorkHive Platform
=============================================
Catches subtle date-handling bugs that show up only across timezones
or DST boundaries. The platform is Philippine-targeted (UTC+8) and
ships maintenance schedules tied to specific shift windows -- date
arithmetic mistakes cause "PM due today" to flip a day off, alerts
to fire at the wrong shift handover etc.

Layer 1 -- new Date(stringInput) parsing without ISO normalization     [WARN]
  `new Date(s)` accepts non-ISO strings non-portably (Chrome vs
  Safari parse "2026-05-11 10:00" differently). Code should use
  ISO strings only: `new Date(s.replace(' ', 'T'))` or explicit
  `Date.parse()`.

Layer 2 -- Mixing Date.parse vs toISOString comparisons                [WARN]
  Comparing a `Date.parse()` numeric to a `toISOString()` string
  silently returns false. Pick one shape per code site.

Layer 3 -- Hardcoded millisecond literals (informational)              [INFO]
  Magic numbers like `86400000` / `3600000` / `604800000` --
  prefer named constants for readability.

Layer 4 -- Timezone-naive helpers (informational)                      [INFO]
  Functions named *_at / *Date that call `new Date()` without an
  explicit TZ qualifier (`toLocaleString('en-PH', ...)` etc).

Skills consulted: data-engineer (timestamp consistency across reads
and writes), performance (date arithmetic on hot paths), mobile-
maestro (device TZ varies on factory floor).
"""
from __future__ import annotations

import re
import json
import sys
import os
import glob

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


EXCLUDED_HTML_PATTERNS = ("-test.html", ".backup.html", "_backup.html", ".backup")
FUNCTIONS_DIR = os.path.join("supabase", "functions")

DATE_ARITHMETIC_OK: dict[tuple[str, int], str] = {
    # (path, line): "reason"
}

# Heuristic patterns.
SPACE_DATE_RE = re.compile(
    r"""\bnew\s+Date\s*\(\s*['"`][^'"`]*\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}""",
)
DATE_PARSE_VS_ISO_RE = re.compile(
    r"""Date\.parse\s*\([^)]+\)\s*[<>=!]+\s*['"`]\d{4}-\d{2}-\d{2}T""",
)
MS_LITERAL_RE = re.compile(
    r"""\b(86400000|3600000|604800000|2592000000|31536000000)\b""",
)


def list_files() -> list[str]:
    out: list[str] = []
    for p in sorted(glob.glob("*.html")):
        if any(x in p.lower() for x in EXCLUDED_HTML_PATTERNS):
            continue
        out.append(p)
    for p in sorted(glob.glob("*.js")):
        if p.endswith(".min.js"):
            continue
        out.append(p)
    for p in sorted(glob.glob(os.path.join(FUNCTIONS_DIR, "**", "*.ts"), recursive=True)):
        out.append(p)
    return out


def _strip(src: str) -> str:
    src = re.sub(r"<!--[\s\S]*?-->", "", src)
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    src = re.sub(r"//[^\n]*", "", src)
    return src


def check_space_date(files):
    issues, report = [], []
    for path in files:
        src = _strip(read_file(path) or "")
        for m in SPACE_DATE_RE.finditer(src):
            line = src.count("\n", 0, m.start()) + 1
            if (path, line) in DATE_ARITHMETIC_OK:
                continue
            report.append({"path": path, "line": line})
            issues.append({
                "check": "space_date", "skip": True,
                "reason": (
                    f"{path}:{line}: `new Date(...)` parsing a "
                    f"space-separated date string. Chrome and Safari "
                    f"parse this non-portably. Use ISO form: "
                    f"`new Date(s.replace(' ', 'T'))` or "
                    f"`new Date(Date.parse(s))`."
                ),
            })
    return issues, report


def check_parse_vs_iso(files):
    issues, report = [], []
    for path in files:
        src = _strip(read_file(path) or "")
        for m in DATE_PARSE_VS_ISO_RE.finditer(src):
            line = src.count("\n", 0, m.start()) + 1
            report.append({"path": path, "line": line})
            issues.append({
                "check": "parse_vs_iso", "skip": True,
                "reason": (
                    f"{path}:{line}: comparing `Date.parse(...)` (number) "
                    f"to an ISO string literal. Pick one shape; "
                    f"Date.parse returns NaN on invalid input which "
                    f"silently fails comparisons."
                ),
            })
    return issues, report


def check_ms_literals(files):
    rows = []
    for path in files:
        src = _strip(read_file(path) or "")
        n = len(MS_LITERAL_RE.findall(src))
        if n == 0:
            continue
        rows.append({"path": path, "n_literals": n})
    rows.sort(key=lambda r: -r["n_literals"])
    return [], rows


def check_tz_naive_helpers(files):
    rows = []
    fn_decl_re = re.compile(r"""function\s+(\w*_at|\w*Date)\s*\(""")
    for path in files:
        src = _strip(read_file(path) or "")
        for m in fn_decl_re.finditer(src):
            name = m.group(1)
            # Look at next 500 chars for new Date(); flag if there's no
            # toLocaleString / TZ marker nearby.
            window = src[m.start():m.start() + 500]
            has_new_date = bool(re.search(r"\bnew\s+Date\s*\(", window))
            has_tz_marker = bool(re.search(
                r"toLocaleString|toLocaleDateString|toISOString|getTimezoneOffset",
                window,
            ))
            if has_new_date and not has_tz_marker:
                rows.append({"path": path, "fn": name})
    return [], rows


CHECK_NAMES = ["space_date", "parse_vs_iso", "ms_literals", "tz_naive_helpers"]
CHECK_LABELS = {
    "space_date":       "L1  No `new Date('YYYY-MM-DD HH:MM')` non-ISO parsing               [WARN]",
    "parse_vs_iso":     "L2  No Date.parse() compared to ISO string literal                  [WARN]",
    "ms_literals":      "L3  Magic millisecond literal inventory (informational)             [INFO]",
    "tz_naive_helpers": "L4  Date-named helpers without TZ marker (informational)            [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nDate Arithmetic Safety (4-layer)"))
    print("=" * 60)
    files = list_files()
    print(f"  {len(files)} file(s) scanned.\n")
    l1_i, l1_r = check_space_date(files)
    l2_i, l2_r = check_parse_vs_iso(files)
    l3_i, l3_r = check_ms_literals(files)
    l4_i, l4_r = check_tz_naive_helpers(files)
    all_issues = l1_i + l2_i + l3_i + l4_i
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)
    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")
    report = {"validator": "date_arithmetic", "total_checks": total,
              "passed": n_pass, "warned": n_warn, "failed": n_fail,
              "space_date": l1_r, "parse_vs_iso": l2_r,
              "ms_literals": l3_r, "tz_naive_helpers": l4_r,
              "issues": [i for i in all_issues if not i.get("skip")],
              "warnings": [i for i in all_issues if i.get("skip")]}
    with open("date_arithmetic_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
