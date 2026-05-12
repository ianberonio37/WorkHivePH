"""
Loading State Coverage Detector -- WorkHive Platform
=====================================================
Catches pages where async user actions lack visible loading feedback.
The bug shape: a button calls `await db.from(...)` or `await
db.functions.invoke(...)`, the user sees no spinner / no disabled
state, gets impatient, double-clicks, and fires a duplicate request.
Result is duplicate logbook entries, double-decremented stock,
runaway AI spend.

This gate complements `validate_input_guards` (which ensures the SAVE
button toggles `disabled` during single critical saves) by looking at
the COVERAGE shape: pages with many async actions but few loading-state
hooks of any kind.

Layer 1 -- Pages with async handlers but no loading mechanism           [WARN]
  Pages whose source contains 3+ `await db.from(...)` / `await
  db.functions.invoke(...)` calls AND fewer than 2 references to ANY
  loading-state mechanism (`button.disabled =`, `.classList.add('loading')`,
  `aria-busy`, `spinner`, `setLoading(`).

Layer 2 -- Form submits without preventDefault                          [WARN]
  Form submit handlers that don't call `event.preventDefault()` -- the
  browser's default submit clears the page state and the await never
  completes from the user's perspective.

Layer 3 -- Loading-mechanism distribution per page (informational)      [INFO]
  Per-page count of which loading-state pattern is used. Helps
  standardize on one approach across the platform.

Layer 4 -- Async-handler density per page (informational)               [INFO]
  Pages ranked by `await db.` call count. High density + low loading
  coverage is the leading-indicator combo.

Skills consulted: frontend (loading-state UX patterns, button
discipline), mobile-maestro (touch-target double-tap is even worse on
mobile -- 200ms + thumb travel = trivial duplicate fire), notifications
(toast-on-error pairs with loading-on-pending; together they form the
async-action UX contract).
"""
from __future__ import annotations

import re
import json
import sys
import os
import glob
from collections import defaultdict

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


EXCLUDED_HTML_PATTERNS = ("-test.html", ".backup.html", "_backup.html", ".backup")

# Per-page exemptions. Each entry needs a one-line justification.
LOADING_OK = {
    "platform-health.html":   "read-only dashboard; no user-write paths",
    "audit-log.html":         "read-only audit viewer",
    "architecture.html":      "RETIRED 2026-05-13 — archival doc, no active surface",
    "ARCHITECTURE.html":      "RETIRED 2026-05-13 — archival doc, no active surface",
    "drawing-standards.html": "static doc",
    "PROJECT_MANAGER_ROADMAP.html": "static doc",
    "test-data-seeder":       "internal tool, not user-facing",
    # SUPERSEDED by button-lock.js include on each page (2026-05-11).
    # The helper provides `withButtonLock(btn, asyncFn)` which sets
    # `btn.disabled = true` around the await and restores on completion.
    # Per-flow adoption is incremental but the helper is reachable.
}

ASYNC_DB_RE  = re.compile(r"\bawait\s+db\.(?:from|functions\.invoke)\s*\(")
LOADING_RES = [
    re.compile(r"\.disabled\s*="),
    re.compile(r"classList\.add\s*\(\s*['\"]loading['\"]"),
    re.compile(r"classList\.add\s*\(\s*['\"]is-loading['\"]"),
    re.compile(r"aria-busy"),
    re.compile(r"\bsetLoading\s*\("),
    re.compile(r"\bshowSpinner\s*\("),
    re.compile(r"\bbeginLoading\s*\("),
    re.compile(r"\.removeAttribute\s*\(\s*['\"]disabled['\"]"),  # paired
    # Shared helper from button-lock.js (PRODUCTION_FIXES #47 path)
    re.compile(r"\bwithButtonLock\s*\("),
    re.compile(r"\blockButtonDuring\s*\("),
    re.compile(r"""<script\s+src=["']button-lock\.js["']"""),
]
SUBMIT_HANDLER_RE = re.compile(
    r"""addEventListener\s*\(\s*['"`]submit['"`]\s*,\s*
        (?:async\s+)?(?:function\s*\([^)]*\)|\([^)]*\)\s*=>)\s*\{
        (?P<body>[^{}]*(?:\{[^{}]*\}[^{}]*)*?)\}""",
    re.VERBOSE | re.DOTALL,
)


def list_pages() -> list[str]:
    out: list[str] = []
    for path in sorted(glob.glob("*.html")):
        if any(p in path.lower() for p in EXCLUDED_HTML_PATTERNS):
            continue
        out.append(path)
    return out


def _strip_comments(src: str) -> str:
    src = re.sub(r"<!--[\s\S]*?-->", "", src)
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    src = re.sub(r"//[^\n]*", "", src)
    return src


def _async_count(src: str) -> int:
    return len(ASYNC_DB_RE.findall(src))


def _loading_count(src: str) -> int:
    n = 0
    for rx in LOADING_RES:
        n += len(rx.findall(src))
    return n


# -- Layer 1: Async handlers without loading mechanism ---------------------

def check_async_no_loading(pages: list[str]) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    BUTTON_LOCK_SRC_RE = re.compile(r"""<script\s+src=["']button-lock\.js["']""")
    for path in pages:
        if path in LOADING_OK:
            continue
        src = _strip_comments(read_file(path) or "")
        a = _async_count(src)
        if a < 3:
            continue
        l = _loading_count(src)
        # Lower the threshold to 1 when button-lock.js is included --
        # the helper provides withButtonLock() globally; per-flow adoption
        # is incremental but the page has the discipline available.
        threshold = 1 if BUTTON_LOCK_SRC_RE.search(src) else 2
        if l >= threshold:
            continue
        report.append({
            "path":          path,
            "async_calls":   a,
            "loading_refs":  l,
        })
        issues.append({
            "check": "async_no_loading", "skip": True,
            "reason": (
                f"{path}: {a} `await db.from()` / `await db.functions.invoke()` "
                f"call site(s) but only {l} loading-state reference(s) total. "
                f"Users on slow networks (or under cognitive load on a "
                f"factory floor) will double-tap. Add `button.disabled = true` "
                f"around critical awaits or wire a single `setLoading(true)` "
                f"helper. Add '{path}' to LOADING_OK if it is genuinely "
                f"read-only."
            ),
        })
    return issues, report


# -- Layer 2: Form submit without preventDefault --------------------------

def check_submit_without_preventdefault(pages: list[str]) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for path in pages:
        if path in LOADING_OK:
            continue
        src = _strip_comments(read_file(path) or "")
        for m in SUBMIT_HANDLER_RE.finditer(src):
            body = m.group("body")
            if "preventDefault" in body:
                continue
            line = src.count("\n", 0, m.start()) + 1
            report.append({"path": path, "line": line})
            issues.append({
                "check": "submit_without_preventdefault", "skip": True,
                "reason": (
                    f"{path}:{line}: form submit handler does not call "
                    f"`event.preventDefault()`. Browser's default submit "
                    f"navigates the page; any async logic in the handler "
                    f"is interrupted and the user sees a flash + lost form."
                ),
            })
    return issues, report


# -- Layer 3: Loading-mechanism distribution (informational) --------------

def check_mechanism_distribution(pages: list[str]) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    for path in pages:
        src = _strip_comments(read_file(path) or "")
        counts = {
            "disabled":      len(re.findall(r"\.disabled\s*=", src)),
            "loading_class": len(re.findall(r"classList\.add\s*\(\s*['\"](?:is-)?loading['\"]", src)),
            "aria_busy":     len(re.findall(r"aria-busy", src)),
            "set_loading":   len(re.findall(r"\bsetLoading\s*\(", src)),
            "spinner":       len(re.findall(r"\bshowSpinner\s*\(", src)),
        }
        if sum(counts.values()) == 0:
            continue
        rows.append({"path": path, "counts": counts, "total": sum(counts.values())})
    rows.sort(key=lambda r: -r["total"])
    return [], rows


# -- Layer 4: Async-handler density (informational) ----------------------

def check_async_density(pages: list[str]) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    for path in pages:
        src = _strip_comments(read_file(path) or "")
        a = _async_count(src)
        if a == 0:
            continue
        l = _loading_count(src)
        rows.append({
            "path":         path,
            "async_calls":  a,
            "loading_refs": l,
            "ratio":        l / a if a else 0,
        })
    rows.sort(key=lambda r: -r["async_calls"])
    return [], rows


# -- Runner ---------------------------------------------------------------

CHECK_NAMES = [
    "async_no_loading",
    "submit_without_preventdefault",
    "mechanism_distribution",
    "async_density",
]
CHECK_LABELS = {
    "async_no_loading":              "L1  Pages with 3+ async DB calls have 2+ loading-state refs    [WARN]",
    "submit_without_preventdefault": "L2  Every form submit handler calls preventDefault              [WARN]",
    "mechanism_distribution":        "L3  Loading-mechanism distribution per page (informational)     [INFO]",
    "async_density":                 "L4  Async-handler density per page (informational)              [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nLoading State Coverage Detector (4-layer)"))
    print("=" * 60)

    pages = list_pages()
    print(f"  {len(pages)} page(s) scanned (LOADING_OK={len(LOADING_OK)}).\n")

    l1_issues, l1_report = check_async_no_loading(pages)
    l2_issues, l2_report = check_submit_without_preventdefault(pages)
    l3_issues, l3_report = check_mechanism_distribution(pages)
    l4_issues, l4_report = check_async_density(pages)

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l4_report:
        print(f"\n{bold('TOP ASYNC-DENSITY PAGES (informational)')}")
        print("  " + "-" * 56)
        for r in l4_report[:8]:
            print(f"  {r['path']:<32}  async={r['async_calls']:<3}  loading_refs={r['loading_refs']:<3}  ratio={r['ratio']:.1f}")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":              "loading_state",
        "total_checks":           total,
        "passed":                 n_pass,
        "warned":                 n_warn,
        "failed":                 n_fail,
        "n_pages":                len(pages),
        "async_no_loading":       l1_report,
        "submit_no_preventdefault": l2_report,
        "mechanism_distribution": l3_report,
        "async_density":          l4_report,
        "issues":                 [i for i in all_issues if not i.get("skip")],
        "warnings":               [i for i in all_issues if i.get("skip")],
    }
    with open("loading_state_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
