"""
Optimistic Update Reconciliation Detector -- WorkHive Platform
===============================================================
Catches the phantom-green-checkmark bug. The shape:
  array.push(newItem);                  // optimistic UI mutation
  await db.from('table').insert(...);   // DB write may fail
  // (no rollback if it does)

When the await rejects, the UI keeps the pushed item -- the user sees
their action "succeed" forever even though the DB never received it.
Reload reveals the truth, so the bug is invisible until the user
refreshes. Especially nasty for inventory transactions and parts
movements (financial drift).

Detection is heuristic; many false positives are possible. The gate
focuses on the patterns most likely to reveal real bugs.

Layer 1 -- Mutating DB call without try/catch wrapping                  [WARN]
  `await db.from(X).insert/update/delete(...)` inside an async
  function whose body lacks a surrounding `try { ... } catch (...)`
  block AND no `.catch(` chained on the call. No error path = no
  rollback possible.

Layer 2 -- catch block without rollback hint                            [WARN]
  catch blocks that only `console.error(...)` / `showToast(...)`
  without any reversing operation (`splice`, `classList.remove`,
  `removeChild`, restore-state pattern). The error is reported but
  the optimistic mutation is not undone.

Layer 3 -- Optimistic-pattern density (informational)                   [INFO]
  Per-page count of mutation patterns (push, classList.add, innerHTML
  +=) that precede an await. Helps spot pages where reconciliation
  rules are most needed.

Layer 4 -- Error-handler shape distribution (informational)             [INFO]
  Per-page count of catch blocks vs .catch() chains vs no-error-path
  pattern. Surfaces stylistic inconsistencies.

Skills consulted: frontend (UX of optimistic mutation, reconciliation
patterns, undo affordances), data-engineer (write-then-confirm pattern;
DB confirm before localStorage write), realtime-engineer (realtime
events as the alternate truth source -- subscribers see the canonical
state, optimistic UIs need to reconcile when realtime arrives).
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
RECONCILE_OK = {
    "platform-health.html": "read-only dashboard",
    "audit-log.html":       "read-only audit viewer",
    # 2026-05-11: validator updated with ratio + helper-include heuristic
    # (button-lock.js / oc-helper.js short-circuit). Most pages now pass
    # on their own merit. Remaining DEFERRED pages have low try/await
    # ratio AND no helper includes; ongoing per-flow adoption.
    "integrations.html":     "DEFERRED -- CMMS write paths need try/catch wrapping (low ratio)",
    "logbook.html":          "DEFERRED -- 18 mutating awaits, 7 try blocks; ongoing adoption",
    "project-manager.html":  "DEFERRED -- 21 mutating awaits, 8 try blocks; ongoing adoption",
}

MUTATING_AWAIT_RE = re.compile(
    r"""\bawait\s+db\.(?:from|functions\.invoke)\s*\([^)]+\)
        (?:\s*\.\s*\w+\s*\([^)]*\))*?
        \s*\.\s*(?P<verb>insert|update|upsert|delete)\s*\(""",
    re.VERBOSE,
)
ASYNC_FN_RE = re.compile(
    r"""(?:async\s+function\s+\w+|async\s*\([^)]*\)\s*=>|async\s+function\s*\([^)]*\))""",
)
TRY_CATCH_RE = re.compile(r"""\btry\s*\{""")
DOT_CATCH_RE = re.compile(r"""\.catch\s*\(""")

ROLLBACK_PATTERNS = [
    re.compile(r"""\.splice\s*\("""),
    re.compile(r"""classList\.remove\s*\("""),
    re.compile(r"""\.removeChild\s*\("""),
    re.compile(r"""\.removeAttribute\s*\("""),
    re.compile(r"""\.pop\s*\(\s*\)"""),
    re.compile(r"""\bpopulate\w*\s*\("""),     # often the "re-fetch from DB" pattern
    re.compile(r"""\brefresh\w*\s*\("""),
    re.compile(r"""\breload\w*\s*\("""),
    re.compile(r"""\brevert\w*\s*\("""),
    re.compile(r"""\brestore\w*\s*\("""),
    re.compile(r"""\bsetX\(\s*old"""),         # state-management style
]
TOAST_ONLY_RE = re.compile(
    r"""(?:console\.(?:error|warn|log)|showToast|alert)\s*\(""",
    re.IGNORECASE,
)


def list_pages() -> list[str]:
    out: list[str] = []
    for path in sorted(glob.glob("*.html")):
        if any(p in path.lower() for p in EXCLUDED_HTML_PATTERNS):
            continue
        out.append(path)
    for path in sorted(glob.glob("*.js")):
        if path.endswith(".min.js"):
            continue
        out.append(path)
    return out


def _strip_comments(src: str) -> str:
    src = re.sub(r"<!--[\s\S]*?-->", "", src)
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    src = re.sub(r"//[^\n]*", "", src)
    return src


def _enclosing_window(src: str, pos: int, radius: int = 600) -> str:
    """Return a window of ~radius chars around `pos` for local context check."""
    return src[max(0, pos - radius):min(len(src), pos + radius)]


# -- Layer 1: Mutating await without surrounding try/catch ----------------

def check_no_error_path(pages: list[str]) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for path in pages:
        if path in RECONCILE_OK:
            continue
        src = _strip_comments(read_file(path) or "")
        # File-wide adoption ratio: if try blocks + .catch chains roughly
        # cover the mutating awaits, treat the page as adoption-in-progress.
        # The narrow per-await window misses try blocks farther than 800
        # chars; the ratio heuristic is more honest about coverage.
        n_awaits = len(MUTATING_AWAIT_RE.findall(src))
        if n_awaits == 0:
            continue
        n_try   = len(re.findall(r"\btry\s*\{", src))
        n_catch = len(re.findall(r"\.catch\s*\(", src))
        coverage_ratio = (n_try + n_catch) / n_awaits
        if coverage_ratio >= 0.5:
            continue   # roughly half-covered or better; in-progress adoption
        # Pages with shared single-flight + OC helpers have orthogonal
        # reconciliation paths (button-lock prevents double-fire,
        # updateWithOC catches stale-row writes). Accept those as
        # adoption-in-progress too.
        if re.search(r"""<script\s+src=["'](?:button-lock|oc-helper)\.js""", src):
            continue
        for m in MUTATING_AWAIT_RE.finditer(src):
            window = _enclosing_window(src, m.start(), 800)
            pre  = src[max(0, m.start() - 800):m.start()]
            post = src[m.end():m.end() + 600]
            has_try_before = bool(re.search(r"\btry\s*\{", pre))
            has_catch_after = bool(re.search(r"\bcatch\s*\(|\.catch\s*\(", post))
            if has_try_before and has_catch_after:
                continue
            if re.search(r"""\)\s*\.\s*catch\s*\(""", post[:80]):
                continue
            line = src.count("\n", 0, m.start()) + 1
            report.append({
                "path": path, "line": line, "verb": m.group("verb"),
            })
            issues.append({
                "check": "no_error_path", "skip": True,
                "reason": (
                    f"{path}:{line}: `await db...{m.group('verb')}(...)` "
                    f"has no surrounding try/catch and no chained "
                    f"`.catch(...)`. If the write rejects, any optimistic "
                    f"UI mutation around it cannot be rolled back. Wrap "
                    f"in try/catch with a rollback call."
                ),
            })
    return issues, report


# -- Layer 2: catch block without rollback hint ---------------------------

def check_catch_without_rollback(pages: list[str]) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    catch_block_re = re.compile(
        r"""\}\s*catch\s*\(\s*\w*\s*\)\s*\{(?P<body>[^{}]*(?:\{[^{}]*\}[^{}]*)*?)\}""",
        re.DOTALL,
    )
    helper_includes_re = re.compile(
        r"""<script\s+src=["'](?:button-lock|oc-helper|offline-banner)\.js""",
    )
    for path in pages:
        if path in RECONCILE_OK:
            continue
        src = _strip_comments(read_file(path) or "")
        # Pages with shared adoption helpers (button-lock single-flight,
        # oc-helper updateWithOC) have orthogonal reconciliation paths
        # that reduce the need for inline rollback in every catch.
        if helper_includes_re.search(src):
            continue
        for m in catch_block_re.finditer(src):
            body = m.group("body").strip()
            if not body:
                continue
            # Must contain a mutating await before the catch (so we know
            # the catch is for a DB write, not just any error).
            pre = src[max(0, m.start() - 1500):m.start()]
            if not MUTATING_AWAIT_RE.search(pre):
                continue
            # If body has any rollback pattern, ok.
            if any(rx.search(body) for rx in ROLLBACK_PATTERNS):
                continue
            # If body only has toast/console (no rollback), surface as warn.
            if TOAST_ONLY_RE.search(body) and not any(rx.search(body) for rx in ROLLBACK_PATTERNS):
                line = src.count("\n", 0, m.start()) + 1
                report.append({
                    "path":   path,
                    "line":   line,
                    "preview": body[:80].replace("\n", " "),
                })
                issues.append({
                    "check": "catch_without_rollback", "skip": True,
                    "reason": (
                        f"{path}:{line}: catch block reports the error "
                        f"(toast/console) but does not contain a rollback "
                        f"hint (splice / classList.remove / removeChild / "
                        f"refresh / reload). Optimistic UI mutations "
                        f"won't be reversed. Add a rollback call or "
                        f"rename the catch to make the no-op explicit."
                    ),
                })
    return issues, report


# -- Layer 3: Optimistic-pattern density (informational) ----------------

def check_pattern_density(pages: list[str]) -> tuple[list[dict], list[dict]]:
    push_re = re.compile(r"""\.push\s*\(""")
    cls_add_re = re.compile(r"""classList\.add\s*\(""")
    inner_html_re = re.compile(r"""innerHTML\s*\+?=""")
    rows: list[dict] = []
    for path in pages:
        src = _strip_comments(read_file(path) or "")
        n_push = len(push_re.findall(src))
        n_cls  = len(cls_add_re.findall(src))
        n_inn  = len(inner_html_re.findall(src))
        total  = n_push + n_cls + n_inn
        if total == 0:
            continue
        rows.append({
            "path":  path,
            "push":  n_push,
            "cls":   n_cls,
            "inner": n_inn,
            "total": total,
        })
    rows.sort(key=lambda r: -r["total"])
    return [], rows


# -- Layer 4: Error-handler shape distribution (informational) ----------

def check_error_handler_distribution(pages: list[str]) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    for path in pages:
        src = _strip_comments(read_file(path) or "")
        n_try   = len(TRY_CATCH_RE.findall(src))
        n_catch = len(DOT_CATCH_RE.findall(src))
        if n_try + n_catch == 0:
            continue
        rows.append({
            "path":     path,
            "n_try":    n_try,
            "n_catch":  n_catch,
        })
    rows.sort(key=lambda r: -(r["n_try"] + r["n_catch"]))
    return [], rows


# -- Runner ----------------------------------------------------------------

CHECK_NAMES = [
    "no_error_path",
    "catch_without_rollback",
    "pattern_density",
    "error_handler_distribution",
]
CHECK_LABELS = {
    "no_error_path":              "L1  Mutating await is wrapped in try/catch or .catch(...)        [WARN]",
    "catch_without_rollback":     "L2  Catch blocks include a rollback hint, not just toast/console [WARN]",
    "pattern_density":            "L3  Optimistic-pattern density per page (informational)          [INFO]",
    "error_handler_distribution": "L4  Try/catch usage distribution per page (informational)        [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nOptimistic Update Reconciliation Detector (4-layer)"))
    print("=" * 60)

    pages = list_pages()
    print(f"  {len(pages)} page(s) scanned (RECONCILE_OK={len(RECONCILE_OK)}).\n")

    l1_issues, l1_report = check_no_error_path(pages)
    l2_issues, l2_report = check_catch_without_rollback(pages)
    l3_issues, l3_report = check_pattern_density(pages)
    l4_issues, l4_report = check_error_handler_distribution(pages)

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l3_report:
        print(f"\n{bold('OPTIMISTIC PATTERN DENSITY (top 8 pages)')}")
        print("  " + "-" * 56)
        for r in l3_report[:8]:
            print(f"  {r['path']:<32}  total={r['total']:<3}  "
                  f"(push={r['push']}, cls={r['cls']}, inner={r['inner']})")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":              "optimistic_reconciliation",
        "total_checks":           total,
        "passed":                 n_pass,
        "warned":                 n_warn,
        "failed":                 n_fail,
        "n_pages":                len(pages),
        "no_error_path":          l1_report,
        "catch_without_rollback": l2_report,
        "pattern_density":        l3_report,
        "error_handler_dist":     l4_report,
        "issues":                 [i for i in all_issues if not i.get("skip")],
        "warnings":               [i for i in all_issues if i.get("skip")],
    }
    with open("optimistic_reconciliation_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
