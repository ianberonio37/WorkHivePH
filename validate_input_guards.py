"""
Input Guards Validator — WorkHive Platform
==========================================
Checks that forms and database writes are properly guarded before they
reach Supabase. Missing guards mean bad data gets written silently —
no error shown to the worker, no clue anything went wrong.

Four things checked:

  1. showToast present       — every page that writes to the DB must be able
                               to show errors to the worker. No showToast = silent failures.

  2. Required field guards   — critical save functions must validate inputs before
                               writing. Regression check — these guards must never disappear.

  3. No bare inserts         — every .insert() call must capture the error response
                               OR be chained with .then() or .catch(). Uncaptured = ignored.

  4. Error handler coverage  — ratio of error checks to DB write calls per page.
                               If a page has many writes but few checks, something is unguarded.

Usage:  python validate_input_guards.py
Output: input_guards_report.json
"""
import re, json, sys

# Pages that write to the database — all must pass every check
TARGET_PAGES = [
    "logbook.html",
    "inventory.html",
    "pm-scheduler.html",
    "hive.html",
]

# Minimum ratio of error-check lines to DB-write lines before we warn
# e.g. 0.6 means: for every 10 inserts/upserts, at least 6 must have a visible error check
MIN_COVERAGE_RATIO = 0.6

# Required field guards: each entry is (page, guard_pattern, description)
# These are regression checks — if the guard disappears, catch it immediately
REQUIRED_GUARDS = [
    (
        "logbook.html",
        r"if\s*\(\s*!machine\b",
        "logbook save must validate machine/equipment field before writing to DB",
    ),
    (
        "inventory.html",
        r"if\s*\(\s*!partNumber\b",
        "inventory add must validate part number before writing to DB",
    ),
    (
        "inventory.html",
        r"if\s*\(\s*!partName\b",
        "inventory add must validate part name before writing to DB",
    ),
    (
        "pm-scheduler.html",
        r"if\s*\(\s*!name\b",
        "PM asset save must validate asset name before writing to DB",
    ),
    (
        "pm-scheduler.html",
        r"if\s*\(\s*!cat\b",
        "PM asset save must validate category before writing to DB",
    ),
]

# Inventory items must use upsert (not raw insert) to prevent duplicate parts
UPSERT_RULES = [
    (
        "inventory.html",
        "inventory_items",
        "inventory_items must use .upsert() to prevent duplicate part entries",
    ),
]


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


# ── Check 1: showToast defined on all data-writing pages ─────────────────────

def check_show_toast_present(pages):
    """
    Every page that writes to the database must define showToast().
    If showToast is missing, DB errors are completely invisible to workers.
    They click Save, nothing happens, no feedback — they don't know it failed.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            issues.append({
                "page": page,
                "reason": f"{page} not found — cannot verify input guards",
            })
            continue
        if "function showToast" not in content:
            issues.append({
                "page":   page,
                "reason": (
                    f"{page} has no showToast function — DB write errors will be "
                    f"invisible to workers (no error message shown on failure)"
                ),
            })
    return issues


# ── Check 2: Required field guards present ────────────────────────────────────

def check_required_guards(guards):
    """
    Critical save functions must validate required inputs before writing.
    These guards were added deliberately — if they disappear (e.g. during
    a refactor), bad data starts entering the database silently.
    """
    issues = []
    for page, pattern, description in guards:
        content = read_file(page)
        if content is None:
            continue
        if not re.search(pattern, content):
            issues.append({
                "page":    page,
                "pattern": pattern,
                "reason": (
                    f"Missing guard in {page}: {description}"
                ),
            })
    return issues


# ── Check 3: No bare inserts (every insert captures the error) ────────────────

def check_no_bare_inserts(pages):
    """
    Every .insert() call must capture the result so the error can be checked.

    SAFE patterns:
      const { error } = await db.from('X').insert(...)      ← captures error
      await db.from('X').insert(...).catch(e => ...)        ← has catch chain
      await db.from('X').insert(...).then(({ error }) => .) ← has then chain

    UNSAFE pattern:
      await db.from('X').insert(payload);                   ← result ignored

    An ignored error means the write could fail and the worker sees nothing.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue

        lines = content.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()

            # Is this line a DB insert call?
            if not re.search(r"\.insert\(", stripped):
                continue
            # Skip HTML attribute values (not JS code)
            if stripped.startswith("<") or stripped.startswith("//"):
                continue

            # Check if it's a safe pattern
            is_safe = any([
                re.search(r"^\s*const\s*\{", line),          # const { error } = await ...
                re.search(r"\.then\s*\(", stripped),          # .then({ error } => ...)
                re.search(r"\.catch\s*\(", stripped),         # .catch(e => ...)
                re.search(r"^\s*\.from\(", line),             # chain continuation (starts with .from)
                "select()" in stripped,                        # .insert(...).select() chain
                not stripped.startswith("await"),             # not an await call (e.g. part of a chain)
            ])

            if not is_safe and "await" in stripped:
                issues.append({
                    "page":   page,
                    "line":   i + 1,
                    "reason": (
                        f"{page}:{i + 1} — bare insert with no error capture: "
                        f"`{stripped[:80]}`"
                    ),
                })
    return issues


# ── Check 4: Error handler coverage ratio ────────────────────────────────────

def check_error_coverage(pages):
    """
    Counts DB write calls vs error-handling patterns per page.
    If a page has many writes but few error checks, some writes are unguarded.

    DB writes:  .insert(  .upsert(
    Error checks: if (error)  if (err)  } catch  .catch(

    A ratio below MIN_COVERAGE_RATIO (60%) means too many unguarded writes.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue

        write_calls = len(re.findall(r"\.(insert|upsert)\(", content))
        error_checks = len(re.findall(
            r"if\s*\(\s*(error|err)\b|}\s*catch\s*\(|\.(catch)\s*\(|"
            r"if\s*\(\w+Err\b|if\s*\(\w+Error\b",
            content
        ))

        if write_calls == 0:
            continue

        ratio = error_checks / write_calls
        if ratio < MIN_COVERAGE_RATIO:
            issues.append({
                "page":         page,
                "write_calls":  write_calls,
                "error_checks": error_checks,
                "ratio":        round(ratio, 2),
                "minimum":      MIN_COVERAGE_RATIO,
                "reason": (
                    f"{page} has {write_calls} DB write calls but only "
                    f"{error_checks} error checks (ratio {ratio:.0%}, "
                    f"minimum {MIN_COVERAGE_RATIO:.0%}) — some writes may be unguarded"
                ),
            })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("Input Guards Validator")
print("=" * 70)

fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        "[1] showToast present on all data-writing pages",
        check_show_toast_present(TARGET_PAGES),
    ),
    (
        "[2] Required field guards present before critical saves",
        check_required_guards(REQUIRED_GUARDS),
    ),
    (
        "[3] No bare inserts (every .insert() captures the error)",
        check_no_bare_inserts(TARGET_PAGES),
    ),
    (
        f"[4] Error handler coverage ratio >= {MIN_COVERAGE_RATIO:.0%} per page",
        check_error_coverage(TARGET_PAGES),
    ),
]

for label, issues in checks:
    print(f"\n{label}\n")
    if not issues:
        print("  PASS")
    else:
        for iss in issues:
            print(f"  FAIL  {iss.get('page', '?')}")
            print(f"        {iss['reason']}")
        fail_count += len(issues)
    report[label] = issues

print(f"\n{'=' * 70}")
print(f"Result: {fail_count} FAIL  {warn_count} WARN")

with open("input_guards_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved input_guards_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll input guard checks PASS.")
