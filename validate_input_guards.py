"""
Input Guards Validator — WorkHive Platform
==========================================
Checks that forms and database writes are properly guarded before they
reach Supabase. Missing guards mean bad data gets written silently.

  Layer 1 — Error visibility
    1.  showToast on all DB pages  — every page that writes to DB can show errors
    2.  Bare inserts caught        — every .insert() captures the error response

  Layer 2 — Input validation
    3.  Required field guards      — critical save functions validate before writing
    4.  NaN guard on numeric input — parseFloat() on user input checks for NaN

  Layer 3 — UX protection
    5.  Save button disabled       — critical save functions disable button during operation
    6.  Error handler coverage     — ratio of error checks to DB write calls >= 60%

  Layer 4 — Schema enforcement
    7.  Upsert rules               — tables that must use upsert (not raw insert)
    8.  Pages in scope             — all DB-writing pages included in TARGET_PAGES

Usage:  python validate_input_guards.py
Output: input_guards_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

TARGET_PAGES = [
    "logbook.html",
    "inventory.html",
    "pm-scheduler.html",
    "hive.html",
    "skillmatrix.html",
    "dayplanner.html",
    "engineering-design.html",
    "report-sender.html",
]

MIN_COVERAGE_RATIO = 0.6

# Required field guards — regression checks: if these disappear, catch it immediately
REQUIRED_GUARDS = [
    (
        "logbook.html",
        r"if\s*\(\s*!machine\b",
        "logbook save must validate machine/equipment field before writing",
    ),
    (
        "inventory.html",
        r"if\s*\(\s*!partNumber\b",
        "inventory add must validate part number before writing",
    ),
    (
        "inventory.html",
        r"if\s*\(\s*!partName\b",
        "inventory add must validate part name before writing",
    ),
    (
        "pm-scheduler.html",
        r"if\s*\(\s*!name\b",
        "PM asset save must validate asset name before writing",
    ),
    (
        "pm-scheduler.html",
        r"if\s*\(\s*!cat\b",
        "PM asset save must validate category before writing",
    ),
    (
        "skillmatrix.html",
        r"submitExam\b",
        "skillmatrix must have submitExam() function to gate badge writes",
    ),
    (
        "skillmatrix.html",
        r"passed\s*=\s*score\s*>=",
        "skillmatrix exam pass threshold must be checked before writing badge",
    ),
]

# Tables that must use .upsert() — not raw .insert() — to prevent duplicates
UPSERT_RULES = [
    (
        "inventory.html",
        "inventory_items",
        "inventory_items must use .upsert() to prevent duplicate part entries",
    ),
    (
        "skillmatrix.html",
        "skill_badges",
        "skill_badges must use .upsert() to update existing badges — raw insert creates duplicates",
    ),
]

# Save functions that must disable the submit button during operation
SAVE_BUTTON_GUARDS = [
    (
        "logbook.html",
        r"saveBtn\.disabled\s*=\s*true",
        "logbook saveEntry must disable button during operation to prevent double-submit",
    ),
    (
        "inventory.html",
        r"showFormError|errEl\.classList",
        "inventory submitPart must show inline form errors on validation failure",
    ),
    (
        "pm-scheduler.html",
        r"btn\.disabled\s*=\s*true",
        "PM asset save must disable button during operation",
    ),
    (
        "skillmatrix.html",
        r"disabled\s*=\s*true",
        "skillmatrix submitExam must disable button during operation",
    ),
]

# Numeric input fields that should guard against NaN
NAN_GUARD_PATTERNS = [
    (
        "logbook.html",
        r"parseFloat\s*\(\s*\w+\s*\)",
        r"isNaN\s*\(|!==\s*''\s*\?\s*parseFloat|parseFloat.*\|\|\s*null",
        "logbook numeric inputs (downtime, good units) should guard against NaN with isNaN() or empty string check",
    ),
]


# ── Layer 1: Error visibility ─────────────────────────────────────────────────

def check_show_toast(pages):
    issues = []
    for page in pages:
        content = read_file(page)
        if not content:
            issues.append({"check": "show_toast", "page": page,
                           "reason": f"{page} not found"})
            continue
        if "function showToast" not in content and "showToast" not in content:
            issues.append({"check": "show_toast", "page": page,
                           "reason": f"{page} has no showToast — DB write errors are invisible to workers"})
    return issues


def check_bare_inserts(pages):
    issues = []
    for page in pages:
        content = read_file(page)
        if not content:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not re.search(r"\.insert\(", stripped):
                continue
            if stripped.startswith("<") or stripped.startswith("//"):
                continue
            is_safe = any([
                re.search(r"^\s*const\s*\{", line),
                re.search(r"\.then\s*\(", stripped),
                re.search(r"\.catch\s*\(", stripped),
                re.search(r"^\s*\.", line),
                "select()" in stripped,
                not stripped.startswith("await"),
            ])
            if not is_safe and "await" in stripped:
                issues.append({"check": "bare_inserts", "page": page, "line": i + 1,
                               "reason": f"{page}:{i+1} bare insert — result ignored, errors silent: `{stripped[:80]}`"})
    return issues


# ── Layer 2: Input validation ─────────────────────────────────────────────────

def check_required_guards(guards):
    issues = []
    for page, pattern, desc in guards:
        content = read_file(page)
        if not content:
            continue
        if not re.search(pattern, content):
            issues.append({"check": "required_guards", "page": page,
                           "reason": f"Missing guard in {page}: {desc}"})
    return issues


def check_nan_guards(rules):
    """
    Pages that use parseFloat() on user input should either:
    a) check for NaN with isNaN(), or
    b) guard with `value !== '' ? parseFloat(value) : null`
    If parseFloat returns NaN and it gets saved to DB, numeric fields silently break.
    """
    issues = []
    for page, parse_pattern, safe_pattern, desc in rules:
        content = read_file(page)
        if not content:
            continue
        has_parse = re.search(parse_pattern, content)
        if not has_parse:
            continue
        has_guard = re.search(safe_pattern, content)
        if not has_guard:
            issues.append({"check": "nan_guard", "page": page,
                           "reason": f"{page}: {desc}"})
    return issues


# ── Layer 3: UX protection ────────────────────────────────────────────────────

def check_save_button_disabled(rules):
    """
    Critical save functions must disable the submit button during the async operation
    to prevent workers from double-clicking and creating duplicate entries.
    """
    issues = []
    for page, pattern, desc in rules:
        content = read_file(page)
        if not content:
            continue
        if not re.search(pattern, content):
            issues.append({"check": "save_btn_disabled", "page": page,
                           "reason": f"Missing button guard in {page}: {desc}"})
    return issues


def check_error_coverage(pages):
    issues = []
    for page in pages:
        content = read_file(page)
        if not content:
            continue
        write_calls  = len(re.findall(r"\.(insert|upsert)\(", content))
        error_checks = len(re.findall(
            r"if\s*\(\s*(error|err)\b|}\s*catch\s*\(|\.(catch)\s*\(|"
            r"if\s*\(\w+Err\b|if\s*\(\w+Error\b",
            content
        ))
        if write_calls == 0:
            continue
        ratio = error_checks / write_calls
        if ratio < MIN_COVERAGE_RATIO:
            issues.append({"check": "error_coverage", "page": page,
                           "write_calls": write_calls, "error_checks": error_checks,
                           "ratio": round(ratio, 2),
                           "reason": f"{page}: {write_calls} DB writes but only {error_checks} error checks ({ratio:.0%}, min {MIN_COVERAGE_RATIO:.0%})"})
    return issues


# ── Layer 4: Schema enforcement ───────────────────────────────────────────────

def check_upsert_rules(rules):
    """
    Tables that must use .upsert() to prevent duplicates.
    A raw .insert() on these tables creates multiple rows on re-save.
    """
    issues = []
    for page, table, desc in rules:
        content = read_file(page)
        if not content:
            continue
        # Check that the table is accessed with .upsert() somewhere
        if not re.search(rf"from\(['\"]({re.escape(table)})['\"].*?\.upsert\(", content, re.DOTALL):
            issues.append({"check": "upsert_rules", "page": page, "table": table,
                           "reason": f"{page}: {desc}"})
    return issues


def check_dom_ordering(pages):
    """
    Elements referenced by addEventListener at the TOP LEVEL of a <script> block
    (i.e. in the init section, not inside function bodies) must exist in the DOM
    before that script tag. A null reference there crashes the entire script.

    Root cause of report-sender.html chips disappearing (April 2026):
    #cancel-contact-btn was declared AFTER the script block, returned null,
    TypeError on .addEventListener() crashed everything including renderChips().

    Scope: only pages in DOM_ORDER_CHECK_PAGES — existing pages use the
    same pattern safely (addEventListener inside functions, called after load).
    Add new pages here when they have top-level init addEventListener calls.
    """
    # Only check pages where top-level addEventListener is used at init time.
    # Existing pages (logbook, inventory, hive, etc.) reference elements inside
    # function bodies that run after DOMContentLoaded — different pattern, safe.
    DOM_ORDER_CHECK_PAGES = [
        "report-sender.html",
    ]

    issues = []
    for page in DOM_ORDER_CHECK_PAGES:
        if page not in pages:
            continue
        content = read_file(page)
        if not content:
            continue

        script_match = re.search(r'<script>\s*\n', content)
        if not script_match:
            continue
        script_pos   = script_match.start()
        html_before  = content[:script_pos]
        script_block = content[script_pos:]

        refs = re.findall(
            r"document\.getElementById\(['\"]([^'\"]+)['\"]\)\.addEventListener",
            script_block
        )

        for el_id in set(refs):
            if f'id="{el_id}"' not in html_before and f"id='{el_id}'" not in html_before:
                issues.append({
                    "check": "dom_ordering",
                    "page":  page,
                    "reason": (
                        f"{page}: #{el_id} has top-level .addEventListener() in <script> "
                        f"but element is declared AFTER the script — null crash on load"
                    )
                })
    return issues


def check_pages_in_scope():
    """All .html pages that write to the DB should be in TARGET_PAGES."""
    import glob
    live_set = set(TARGET_PAGES)
    issues   = []
    for path in glob.glob("*.html"):
        fname = os.path.basename(path)
        if fname in live_set:
            continue
        if any(s in fname for s in ["-test", ".backup", "platform-health", "guardian",
                                     "parts-tracker", "symbol-gallery", "architecture"]) or fname == "index.html":
            continue
        content = read_file(fname)
        if content and re.search(r"\.insert\(|\.upsert\(", content):
            issues.append({"check": "pages_in_scope", "page": fname,
                           "reason": f"{fname} writes to DB but is not in validate_input_guards.py TARGET_PAGES"})
    return issues


# ── Layer 6: Async result inspection ─────────────────────────────────────────

def check_allsettled_inspection(pages):
    """
    Promise.allSettled() results must be inspected — not silently ignored.

    Bug pattern: fire allSettled then unconditionally mark as success.
    Root cause of report-sender email issue (April 2026):
    email sends used allSettled but never checked results — UI showed
    green checkmark even when Resend returned HTTP 500.

    Looks for .status / 'fulfilled' / 'rejected' within 600 chars
    of each allSettled call.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if not content:
            continue
        for m in re.finditer(r'Promise\.allSettled\s*\(', content):
            # Only check allSettled(collection.map(...)) — these process external requests.
            # allSettled([func1(), func2()]) is a background parallel-run pattern — skip it.
            call_start = content[m.start():m.start() + 50]
            if not re.search(r'\.map\s*\(', call_start):
                continue  # array literal — background refresh, result check not required

            # 1200 chars covers async map() bodies before the result variable is used
            window = content[m.start():m.start() + 1200]
            has_inspection = any(re.search(p, window) for p in [
                r'\.status\b', r"['\"]fulfilled['\"]", r"['\"]rejected['\"]",
                r'\.filter\s*\(', r'\br\.status\b',
            ])
            if not has_inspection:
                line = content[:m.start()].count('\n') + 1
                issues.append({
                    "check": "allsettled_inspection",
                    "page":  page,
                    "reason": (
                        f"{page}:{line} Promise.allSettled(collection.map(...)) called but "
                        f"results not inspected — HTTP failures silently treated as success; "
                        f"check r.status === 'fulfilled'/'rejected' on each result"
                    )
                })
    return issues


def check_fetch_error_handling(pages):
    """
    fetch() calls to Supabase edge functions must check resp.ok or resp.status.
    A fetch that ignores the HTTP response will show success even on 500 errors.

    Scoped to calls containing SUPABASE_URL — avoids false positives on
    third-party CDN fetches (fonts, Supabase JS, etc.).

    FIRE_AND_FORGET: embed-entry calls are intentionally silent (AI Engineer skill) —
    they update the knowledge base in the background without blocking the main save.
    Failures are caught by try/catch with console.warn, not surfaced to the user.
    """
    FIRE_AND_FORGET_FUNCTIONS = ['embed-entry']  # background ops — silence is intentional

    issues = []
    for page in pages:
        content = read_file(page)
        if not content:
            continue
        for m in re.finditer(r'\bfetch\s*\(`?\$\{SUPABASE_URL\}', content):
            # Skip fire-and-forget edge functions
            call_snippet = content[m.start():m.start() + 100]
            if any(fn in call_snippet for fn in FIRE_AND_FORGET_FUNCTIONS):
                continue
            # Look at next 700 chars for response check (covers large request bodies)
            window = content[m.start():m.start() + 700]
            has_check = any(p in window for p in [
                'resp.ok', 'response.ok', '.ok)', '.ok\n', '.ok ',
                'resp.status', 'response.status',
                'if (!resp', 'if (!response',
            ])
            if not has_check:
                line = content[:m.start()].count('\n') + 1
                issues.append({
                    "check": "fetch_error_handling",
                    "page":  page,
                    "reason": (
                        f"{page}:{line} fetch() to edge function doesn't check resp.ok — "
                        f"HTTP 4xx/5xx errors silently ignored; add if (!resp.ok) handling"
                    )
                })
    return issues


def check_localstorage_backup(pages):
    """
    Pages that save critical data to Supabase AND display it as a list
    should also write to localStorage as fallback. Without this, a Supabase
    failure or missing HIVE_ID causes the data to vanish on next page load.

    Root cause of report-sender contacts disappearing (April 2026):
    contacts written to Supabase only — localStorage fallback missing.
    """
    # Map: page → (supabase table, expected localStorage key pattern)
    BACKUP_REQUIRED = {
        "report-sender.html": ("report_contacts", "LS_CONTACTS"),
    }

    issues = []
    for page, (table, ls_key) in BACKUP_REQUIRED.items():
        if page not in pages:
            continue
        content = read_file(page)
        if not content:
            continue
        if table in content and ls_key not in content:
            issues.append({
                "check": "localstorage_backup",
                "page":  page,
                "reason": (
                    f"{page}: writes to '{table}' but has no localStorage backup ({ls_key}) "
                    f"— data disappears on navigation when Supabase is unavailable or HIVE_ID is null"
                )
            })
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    # L1
    "show_toast", "bare_inserts",
    # L2
    "required_guards", "nan_guard",
    # L3
    "save_btn_disabled", "error_coverage",
    # L4
    "upsert_rules", "pages_in_scope",
    # L5
    "dom_ordering",
    # L6
    "allsettled_inspection", "fetch_error_handling", "localstorage_backup",
]

CHECK_LABELS = {
    # L1
    "show_toast":            "L1  showToast present on all DB-writing pages",
    "bare_inserts":          "L1  No bare inserts (every .insert() captures error)",
    # L2
    "required_guards":       "L2  Required field guards before critical saves",
    "nan_guard":             "L2  NaN guard on parseFloat() from user input",
    # L3
    "save_btn_disabled":     "L3  Save button disabled during async operation",
    "error_coverage":        "L3  Error handler coverage >= 60% of DB writes",
    # L4
    "upsert_rules":          "L4  Tables that must use upsert (not raw insert)",
    "pages_in_scope":        "L4  All DB-writing pages in TARGET_PAGES",
    # L5
    "dom_ordering":          "L5  All addEventListener targets exist in DOM before <script> block",
    # L6
    "allsettled_inspection": "L6  Promise.allSettled() results inspected — not silently ignored",
    "fetch_error_handling":  "L6  fetch() to edge functions checks resp.ok",
    "localstorage_backup":   "L6  Critical Supabase data has localStorage backup",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nInput Guards Validator (4-layer)"))
    print("=" * 55)

    all_issues = []
    all_issues += check_show_toast(TARGET_PAGES)
    all_issues += check_bare_inserts(TARGET_PAGES)
    all_issues += check_required_guards(REQUIRED_GUARDS)
    all_issues += check_nan_guards(NAN_GUARD_PATTERNS)
    all_issues += check_save_button_disabled(SAVE_BUTTON_GUARDS)
    all_issues += check_error_coverage(TARGET_PAGES)
    all_issues += check_upsert_rules(UPSERT_RULES)
    all_issues += check_pages_in_scope()
    all_issues += check_dom_ordering(TARGET_PAGES)
    all_issues += check_allsettled_inspection(TARGET_PAGES)
    all_issues += check_fetch_error_handling(TARGET_PAGES)
    all_issues += check_localstorage_backup(TARGET_PAGES)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "input_guards",
        "total_checks": total,
        "passed":       n_pass,
        "skipped":      n_skip,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
    }
    with open("input_guards_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
