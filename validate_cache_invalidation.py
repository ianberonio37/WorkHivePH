"""
Cache Invalidation Detector -- WorkHive Platform
=================================================
Catches the silent service-worker cache-staleness bug. WorkHive's
`sw.js` declares a `CACHE_NAME` constant + a `SHELL_FILES` array of
PWA shell assets. When any shell file changes, the developer must
bump `CACHE_NAME` (e.g., `v27` -> `v28`) so existing users discard the
old cache on next visit. Forget the bump, and users browse a cached
stale shell forever (until manual hard-reload).

Layer 1 -- SHELL_FILES references a file that doesn't exist             [WARN]
  Catches typos / deleted files still listed in the shell array.
  Cache install fails silently in the browser; PWA stops working.

Layer 2 -- Shell file edited after last sw.js bump                      [WARN]
  Per-shell-file: git log shows a commit newer than the most recent
  sw.js commit. Indicates the shell was changed without a CACHE_NAME
  bump in the same commit / merge.

Layer 3 -- CACHE_NAME version inventory (informational)                 [INFO]
  Current version + count of historical bumps. Helps spot whether
  bumps happen on a healthy cadence (every 3-5 shell edits) or stay
  pinned for too long.

Layer 4 -- Shell file count and freshness (informational)               [INFO]
  Inventory of SHELL_FILES, age of each since last commit. Useful
  for spotting an outsized shell that should be split.

Skills consulted: devops (cache versioning, deploy hygiene),
performance (cold reload vs cached shell, PWA semantics), mobile-
maestro (PWA discipline; iOS/Android both honour CACHE_NAME).
"""
from __future__ import annotations

import re
import json
import sys
import os
import subprocess
from collections import defaultdict

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


SW_FILE = "sw.js"

CACHE_NAME_RE = re.compile(
    r"""const\s+CACHE_NAME\s*=\s*['"`](?P<name>[^'"`]+)['"`]""",
)
SHELL_ARRAY_RE = re.compile(
    r"""const\s+SHELL_FILES\s*=\s*\[(?P<body>[\s\S]*?)\];""",
)
SHELL_FILE_RE = re.compile(r"""['"`](?P<file>[^'"`]+)['"`]""")


def parse_sw() -> dict:
    src = read_file(SW_FILE) or ""
    name_m  = CACHE_NAME_RE.search(src)
    shell_m = SHELL_ARRAY_RE.search(src)
    files: list[str] = []
    if shell_m:
        for fm in SHELL_FILE_RE.finditer(shell_m.group("body")):
            files.append(fm.group("file"))
    return {
        "cache_name": name_m.group("name") if name_m else None,
        "shell":      files,
    }


def _git_last_commit_date(path: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=format:%ad", "--date=iso-strict", "--", path],
            capture_output=True, text=True, timeout=15,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    out = result.stdout.strip()
    return out or None


# -- Layer 1: shell file doesn't exist -------------------------------------

def check_shell_missing(parsed: dict) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for f in parsed["shell"]:
        # Strip leading slash for filesystem lookup.
        local = f.lstrip("/")
        if os.path.isfile(local):
            continue
        # Try project-root variant (some entries are CDN-style absolute).
        if "://" in f:
            continue
        report.append({"shell_file": f})
        issues.append({
            "check": "shell_missing", "skip": True,
            "reason": (
                f"sw.js SHELL_FILES references `{f}` which does not exist "
                f"on disk. The browser will fail the cache.addAll() call "
                f"silently and the PWA shell will not work offline. "
                f"Either fix the path or remove it from SHELL_FILES."
            ),
        })
    return issues, report


# -- Layer 2: shell file edited after last sw.js bump ---------------------

def check_drift(parsed: dict) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    sw_date = _git_last_commit_date(SW_FILE)
    if not sw_date:
        return [], []
    for f in parsed["shell"]:
        local = f.lstrip("/")
        if not os.path.isfile(local):
            continue
        f_date = _git_last_commit_date(local)
        if not f_date:
            continue
        # Compare ISO strings (lex-sortable).
        if f_date <= sw_date:
            continue
        report.append({
            "shell_file":   f,
            "shell_date":   f_date,
            "sw_date":      sw_date,
            "cache_name":   parsed["cache_name"],
        })
        issues.append({
            "check": "shell_drift", "skip": True,
            "reason": (
                f"`{f}` was last committed at {f_date}, but sw.js "
                f"(CACHE_NAME='{parsed['cache_name']}') was last committed "
                f"at {sw_date}. Existing users browse the OLD cached "
                f"version of `{f}` forever. Bump CACHE_NAME (e.g., "
                f"-v{int_increment(parsed['cache_name'])}) and commit "
                f"sw.js together with the shell change."
            ),
        })
    return issues, report


def int_increment(name: str | None) -> str:
    """Return suggested next version label."""
    if not name:
        return "v1"
    m = re.search(r"v(\d+)$", name)
    if not m:
        return name + "-next"
    return str(int(m.group(1)) + 1)


# -- Layer 3: cache version inventory (informational) ---------------------

def check_version_history() -> tuple[list[dict], list[dict]]:
    """Use git log to count CACHE_NAME bumps over the project's history."""
    rows: list[dict] = []
    try:
        result = subprocess.run(
            ["git", "log", "-G", "CACHE_NAME", "--pretty=format:%H|%ad", "--date=iso-strict", "--", SW_FILE],
            capture_output=True, text=True, timeout=20,
        )
    except Exception:
        return [], []
    n = len([line for line in result.stdout.splitlines() if "|" in line])
    rows.append({"metric": "CACHE_NAME bump events", "count": n})
    return [], rows


# -- Layer 4: Shell file inventory (informational) -----------------------

def check_shell_inventory(parsed: dict) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    for f in parsed["shell"]:
        local = f.lstrip("/")
        rows.append({
            "shell_file": f,
            "exists":     os.path.isfile(local),
            "last_date":  _git_last_commit_date(local) or "n/a",
        })
    return [], rows


# -- Runner ----------------------------------------------------------------

CHECK_NAMES = [
    "shell_missing",
    "shell_drift",
    "version_history",
    "shell_inventory",
]
CHECK_LABELS = {
    "shell_missing":   "L1  Every SHELL_FILES entry exists on disk                       [WARN]",
    "shell_drift":     "L2  No shell file edited after last CACHE_NAME bump              [WARN]",
    "version_history": "L3  CACHE_NAME bump cadence (informational)                      [INFO]",
    "shell_inventory": "L4  SHELL_FILES + last-modified inventory (informational)        [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nCache Invalidation Detector (4-layer)"))
    print("=" * 60)

    if not os.path.isfile(SW_FILE):
        print(f"  No {SW_FILE} found; nothing to check.\n")
        sys.exit(0)

    parsed = parse_sw()
    print(f"  CACHE_NAME='{parsed['cache_name']}', "
          f"{len(parsed['shell'])} SHELL_FILES entries.\n")

    l1_issues, l1_report = check_shell_missing(parsed)
    l2_issues, l2_report = check_drift(parsed)
    l3_issues, l3_report = check_version_history()
    l4_issues, l4_report = check_shell_inventory(parsed)

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l4_report:
        print(f"\n{bold('SHELL FILE INVENTORY (informational)')}")
        print("  " + "-" * 56)
        for r in l4_report[:8]:
            mark = "OK" if r["exists"] else "MISSING"
            print(f"  {r['shell_file']:<40}  {mark:<8} last={r['last_date'][:10]}")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":       "cache_invalidation",
        "total_checks":    total,
        "passed":          n_pass,
        "warned":          n_warn,
        "failed":          n_fail,
        "cache_name":      parsed["cache_name"],
        "n_shell_files":   len(parsed["shell"]),
        "shell_missing":   l1_report,
        "shell_drift":     l2_report,
        "version_history": l3_report,
        "shell_inventory": l4_report,
        "issues":          [i for i in all_issues if not i.get("skip")],
        "warnings":        [i for i in all_issues if i.get("skip")],
    }
    with open("cache_invalidation_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
