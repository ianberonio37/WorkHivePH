"""
Test Page Drift -- WorkHive Platform
======================================
WorkHive has *-test.html files (engineering-design-test, hive-test,
etc.) that historically served as scratch copies for risky UI work.
Over time these drift from their production counterparts -- a fix
lands on prod but the test page doesn't update, or vice versa.

Layer 1 -- Test page much smaller than prod                             [WARN]
  `<base>-test.html` whose LOC is <50% of `<base>.html` -- likely
  abandoned or stub.

Layer 2 -- Test page much larger than prod                              [WARN]
  `<base>-test.html` whose LOC is >120% of `<base>.html` -- experimental
  feature on the test page that never landed in prod.

Layer 3 -- Test page lacks a production counterpart (informational)     [INFO]
  Orphan test pages -- candidates for cleanup.

Layer 4 -- Drift inventory (informational)                              [INFO]
  Per-pair LOC delta, last-modified delta.

Skills consulted: qa-tester (test copy discipline), devops (cleanup of
stale UI scratch).
"""
from __future__ import annotations

import json
import sys
import os
import glob

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


TEST_PAGE_OK: dict[str, str] = {
    # 2026-05-11: hive-test.html DELETED (closes PRODUCTION_FIXES #59).
    # File was 10-day-stale experimental drift (137% of hive.html LOC).
    # Git history retains the experimental features if needed.
}


def list_test_pages() -> list[str]:
    return sorted(glob.glob("*-test.html"))


def loc(path: str) -> int:
    src = read_file(path) or ""
    return len([l for l in src.split("\n") if l.strip()])


def prod_counterpart(test_path: str) -> str | None:
    # strip the trailing -test (or -*-test etc.). For simplicity, handle
    # `<base>-test.html` shape and let multi-token variants go to orphan.
    base = os.path.basename(test_path).replace("-test.html", ".html")
    return base if os.path.isfile(base) else None


def check_smaller(pages):
    issues, report = [], []
    for tp in pages:
        if tp in TEST_PAGE_OK:
            continue
        prod = prod_counterpart(tp)
        if not prod:
            continue
        t = loc(tp); p = loc(prod)
        if p == 0:
            continue
        ratio = t / p
        if ratio >= 0.5:
            continue
        report.append({"test": tp, "prod": prod, "test_loc": t, "prod_loc": p, "ratio": round(ratio, 2)})
        issues.append({
            "check": "test_smaller", "skip": True,
            "reason": (
                f"{tp} is {t} LOC vs {prod} at {p} LOC (ratio {ratio:.2f}). "
                f"Likely abandoned/stub. Either bring up to date OR delete "
                f"if no longer needed."
            ),
        })
    return issues, report


def check_larger(pages):
    issues, report = [], []
    for tp in pages:
        if tp in TEST_PAGE_OK:
            continue
        prod = prod_counterpart(tp)
        if not prod:
            continue
        t = loc(tp); p = loc(prod)
        if p == 0:
            continue
        ratio = t / p
        if ratio <= 1.2:
            continue
        report.append({"test": tp, "prod": prod, "test_loc": t, "prod_loc": p, "ratio": round(ratio, 2)})
        issues.append({
            "check": "test_larger", "skip": True,
            "reason": (
                f"{tp} is {t} LOC vs {prod} at {p} LOC (ratio {ratio:.2f}). "
                f"Test page has features not yet in prod -- either land "
                f"them or prune the experimental code."
            ),
        })
    return issues, report


def check_orphans(pages):
    rows = []
    for tp in pages:
        if not prod_counterpart(tp):
            rows.append({"test": tp})
    return [], rows


def check_inventory(pages):
    rows = []
    for tp in pages:
        prod = prod_counterpart(tp)
        if not prod:
            continue
        t = loc(tp); p = loc(prod)
        rows.append({
            "test": tp, "prod": prod,
            "test_loc": t, "prod_loc": p,
            "diff_pct": round((t - p) / p * 100, 1) if p else None,
        })
    return [], rows


CHECK_NAMES = ["test_smaller", "test_larger", "orphans", "inventory"]
CHECK_LABELS = {
    "test_smaller": "L1  Every test page is >=50% of prod LOC                   [WARN]",
    "test_larger":  "L2  No test page is >120% of prod LOC                      [WARN]",
    "orphans":      "L3  Orphan test pages without prod counterpart (informational) [INFO]",
    "inventory":    "L4  Per-pair LOC delta inventory (informational)            [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nTest Page Drift (4-layer)"))
    print("=" * 60)
    pages = list_test_pages()
    print(f"  {len(pages)} test page(s) found.\n")
    l1_i, l1_r = check_smaller(pages)
    l2_i, l2_r = check_larger(pages)
    l3_i, l3_r = check_orphans(pages)
    l4_i, l4_r = check_inventory(pages)
    all_issues = l1_i + l2_i + l3_i + l4_i
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)
    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")
    report = {"validator": "test_page_drift", "total_checks": total,
              "passed": n_pass, "warned": n_warn, "failed": n_fail,
              "test_smaller": l1_r, "test_larger": l2_r,
              "orphans": l3_r, "inventory": l4_r,
              "issues": [i for i in all_issues if not i.get("skip")],
              "warnings": [i for i in all_issues if i.get("skip")]}
    with open("test_page_drift_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
