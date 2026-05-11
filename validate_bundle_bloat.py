"""
Edge Function Bundle Bloat -- WorkHive Platform
=================================================
Catches edge functions that have grown disproportionately large.
Supabase edge fns are bundled per-fn and ship to the runtime on
first cold-start; size is roughly proportional to (LOC + imports).
Beyond ~2000 LOC the cold-start latency becomes user-visible.

Layer 1 -- Fn over hard LOC ceiling                                     [WARN]
  Any edge fn whose index.ts is > MAX_LOC lines.

Layer 2 -- Fn over hard import-count ceiling                            [WARN]
  Any edge fn with > MAX_IMPORTS top-level `import` statements.

Layer 3 -- Top fns by bundle proxy (informational)                      [INFO]
  Ranked LOC + import count per fn.

Layer 4 -- Dynamic-import drift (informational)                         [INFO]
  Count of `await import(...)` and `import('...')` dynamic calls per
  fn. Adoption signal -- modular boot beats single-bundle bloat.

Skills consulted: devops (cold-start latency), performance (bundle
size affects every cold dispatch).
"""
from __future__ import annotations

import re
import json
import sys
import os
from collections import defaultdict

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


FUNCTIONS_DIR = os.path.join("supabase", "functions")
MAX_LOC = 2000
MAX_IMPORTS = 20

BLOAT_OK: dict[str, str] = {
    "engineering-calc-agent": "DEFERRED -- monolithic calc handler (5364 LOC); split into per-discipline modules",
    "engineering-bom-sow":    "DEFERRED -- monolithic BOM/SOW renderer (3986 LOC); split per-discipline",
}


def list_edge_fns() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if os.path.isdir(FUNCTIONS_DIR):
        for d in sorted(os.listdir(FUNCTIONS_DIR)):
            idx = os.path.join(FUNCTIONS_DIR, d, "index.ts")
            if os.path.isfile(idx):
                out.append((d, idx))
    return out


IMPORT_RE = re.compile(r"^\s*import\s+", re.MULTILINE)
DYNAMIC_IMPORT_RE = re.compile(r"""(?:await\s+)?import\s*\(\s*['"`]""")


def metrics(path: str) -> dict:
    src = read_file(path) or ""
    loc = len([l for l in src.split("\n") if l.strip()])
    imports = len(IMPORT_RE.findall(src))
    dynamic = len(DYNAMIC_IMPORT_RE.findall(src))
    return {"loc": loc, "imports": imports, "dynamic": dynamic}


def check_loc(fns: list[tuple[str, str]]) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for name, path in fns:
        if name in BLOAT_OK:
            continue
        m = metrics(path)
        if m["loc"] <= MAX_LOC:
            continue
        report.append({"fn": name, "loc": m["loc"]})
        issues.append({
            "check": "loc_ceiling", "skip": True,
            "reason": (
                f"{name}/index.ts is {m['loc']} lines (ceiling {MAX_LOC}). "
                f"Cold-start latency is user-visible; consider splitting "
                f"into helper modules or moving to a streamed/dynamic-"
                f"import shape. Add '{name}' to BLOAT_OK with a reason "
                f"if the size is intentional."
            ),
        })
    return issues, report


def check_imports(fns: list[tuple[str, str]]) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for name, path in fns:
        if name in BLOAT_OK:
            continue
        m = metrics(path)
        if m["imports"] <= MAX_IMPORTS:
            continue
        report.append({"fn": name, "imports": m["imports"]})
        issues.append({
            "check": "import_ceiling", "skip": True,
            "reason": (
                f"{name}/index.ts has {m['imports']} top-level imports "
                f"(ceiling {MAX_IMPORTS}). Each import inflates the cold-"
                f"start bundle. Audit for unused imports or move rare-"
                f"path deps to dynamic imports."
            ),
        })
    return issues, report


def check_distribution(fns: list[tuple[str, str]]) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    for name, path in fns:
        m = metrics(path)
        rows.append({"fn": name, "loc": m["loc"], "imports": m["imports"]})
    rows.sort(key=lambda r: -r["loc"])
    return [], rows


def check_dynamic_adoption(fns: list[tuple[str, str]]) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    for name, path in fns:
        m = metrics(path)
        if m["dynamic"] == 0:
            continue
        rows.append({"fn": name, "dynamic_imports": m["dynamic"]})
    return [], rows


CHECK_NAMES = ["loc_ceiling", "import_ceiling", "distribution", "dynamic_adoption"]
CHECK_LABELS = {
    "loc_ceiling":      f"L1  No edge fn exceeds {MAX_LOC} LOC                              [WARN]",
    "import_ceiling":   f"L2  No edge fn exceeds {MAX_IMPORTS} top-level imports             [WARN]",
    "distribution":     "L3  Top fns by bundle proxy (informational)                     [INFO]",
    "dynamic_adoption": "L4  Dynamic-import adoption count (informational)               [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nEdge Function Bundle Bloat (4-layer)"))
    print("=" * 60)
    fns = list_edge_fns()
    print(f"  {len(fns)} edge fn(s) scanned.\n")
    l1_i, l1_r = check_loc(fns)
    l2_i, l2_r = check_imports(fns)
    l3_i, l3_r = check_distribution(fns)
    l4_i, l4_r = check_dynamic_adoption(fns)
    all_issues = l1_i + l2_i + l3_i + l4_i
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)
    if l3_r:
        print(f"\n{bold('TOP FNS BY LOC')}")
        print("  " + "-" * 56)
        for r in l3_r[:8]:
            print(f"  {r['fn']:<32}  loc={r['loc']:<5} imports={r['imports']}")
    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")
    report = {"validator": "bundle_bloat", "total_checks": total,
              "passed": n_pass, "warned": n_warn, "failed": n_fail,
              "loc": l1_r, "imports": l2_r,
              "distribution": l3_r, "dynamic_adoption": l4_r,
              "issues": [i for i in all_issues if not i.get("skip")],
              "warnings": [i for i in all_issues if i.get("skip")]}
    with open("bundle_bloat_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
