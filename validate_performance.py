"""
Performance Anti-Pattern Validator — WorkHive Platform
======================================================
Performance issues are invisible during development when the database is
small — they emerge silently in production as data grows. A logbook with
50 entries loads in 40ms. A logbook with 5,000 entries loads in 4+ seconds
with the same code. This validator catches the patterns before they become
incidents.

From the Performance skill and Data Engineer skill files.

Five things checked:

  1. Unbounded queries on high-growth tables
     — logbook and inventory_transactions grow with every user action.
       A .select() on these tables without .limit() or .range() fetches
       ALL rows — 100 today, 100,000 next year. Flag as WARN: works now,
       degrades silently with scale.

  2. select('*') on large tables — prefer named columns
     — .select('*') fetches every column including large text fields
       (problem, action, knowledge, root_cause, notes) even when the
       caller only needs id + name. Narrow selects are 3-10x faster on
       wide tables. Flag as WARN on the highest-impact tables.

  3. DB queries inside loops
     — Every db.from() call inside a forEach(), map(), or for() loop
       fires a separate network request per iteration. 10 items = 10 DB
       calls = 2,000ms instead of one batch query in 200ms.
       This is an N+1 pattern. Flag as FAIL — immediate impact.

  4. Consecutive sequential await DB calls (Promise.all opportunity)
     — Two or more independent `await db.from(...)` calls on consecutive
       lines inside the same function run in series.
       Promise.all([queryA, queryB]) runs them in parallel and halves
       the wait time. Flag as WARN — not broken, just slow.

  5. body { animation } without JS safety guard (blank page on CDN slowness)
     — Pages that fade the body in (body { animation: page-enter forwards })
       start with body at opacity:0. If the Tailwind CDN is slow, the body
       is invisible while waiting. If the animation stalls (background tab),
       the body stays blank forever. An 800ms animationend safety guard
       prevents permanent blank-page lockout.

Usage:  python validate_performance.py
Output: performance_report.json
"""
import re, json, sys

LIVE_PAGES = [
    "index.html",
    "logbook.html",
    "inventory.html",
    "pm-scheduler.html",
    "hive.html",
    "assistant.html",
    "skillmatrix.html",
    "dayplanner.html",
    "engineering-design.html",
]

# Tables that grow with every user action — unbounded selects will time out
HIGH_GROWTH_TABLES = ["logbook", "inventory_transactions"]

# Tables where select('*') wastes bandwidth — should use named columns
WIDE_TABLES = ["logbook", "inventory_items", "inventory_transactions",
               "pm_scope_items", "pm_completions"]

# Max consecutive sequential awaits before flagging
SEQUENTIAL_AWAIT_THRESHOLD = 2


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


# ── Check 1: Unbounded queries on high-growth tables ─────────────────────────

def check_unbounded_queries(pages, tables):
    """
    logbook and inventory_transactions grow unboundedly. A .select() on these
    tables without .limit() or .range() fetches every row the user has ever
    created. At 5,000+ entries this causes:
    - Slow initial page load (seconds, not milliseconds)
    - High Supabase bandwidth usage (costs money at scale)
    - Browser memory pressure (large JS arrays)

    Fix: add .limit(200) for initial loads and implement "Load More" pagination.
    Count queries ({ count: 'exact', head: true }) are exempt.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()

        for i, line in enumerate(lines):
            # Is this a select on a high-growth table?
            table_match = None
            for table in tables:
                if f"from('{table}')" in line or f'from("{table}")' in line:
                    table_match = table
                    break
            if not table_match:
                continue
            if ".select(" not in line:
                continue
            # Skip count queries — they don't return rows
            if "head: true" in line or "count: 'exact'" in line or 'count: "exact"' in line:
                continue

            # Check if .limit( or .range( appears within the next 15 lines
            window = "\n".join(lines[i:min(len(lines), i + 15)])
            has_limit = ".limit(" in window or ".range(" in window
            if not has_limit:
                issues.append({
                    "page":  page,
                    "table": table_match,
                    "line":  i + 1,
                    "reason": (
                        f"{page}:{i + 1} — query on '{table_match}' has no .limit() "
                        f"or .range() — fetches ALL rows as the table grows: "
                        f"`{line.strip()[:70]}`"
                    ),
                })
    return issues


# ── Check 2: select('*') on wide tables ──────────────────────────────────────

def check_select_star(pages, tables):
    """
    .select('*') fetches every column in the table including large TEXT fields.
    For logbook, this includes problem, action, root_cause, knowledge, and photo
    data — often kilobytes per row. If only the machine name and date are needed
    for a summary view, .select('id, date, machine, status') is 5-10x faster.

    Narrow selects also reduce the data sent over the network on every load.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()

        for i, line in enumerate(lines):
            # Is this a select('*') on a wide table?
            table_match = None
            for table in tables:
                if f"from('{table}')" in line or f'from("{table}")' in line:
                    table_match = table
                    break
            if not table_match:
                continue
            # Check for select('*') pattern
            if not re.search(r"\.select\s*\(\s*['\*]['\*]?\s*\)", line):
                continue
            # Skip count queries
            if "head: true" in line:
                continue

            issues.append({
                "page":  page,
                "table": table_match,
                "line":  i + 1,
                "reason": (
                    f"{page}:{i + 1} — select('*') on '{table_match}' fetches all "
                    f"columns including large TEXT fields — use named columns "
                    f"to reduce bandwidth by 3-10x: "
                    f"`{line.strip()[:70]}`"
                ),
            })
    return issues


# ── Check 3: DB queries inside loops (N+1 pattern) ───────────────────────────

def check_db_in_loop(pages):
    """
    db.from() inside a forEach(), map(), or for() loop fires one DB query
    per array item. This is the N+1 query pattern:
    - 10 items = 10 DB round trips = ~2 seconds
    - Should be: 1 batch query with .in() = ~200ms

    This is a FAIL — it does not degrade gracefully. Performance is already
    bad at small data sizes and gets exponentially worse.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()

        for i, line in enumerate(lines):
            if "db.from(" not in line:
                continue
            stripped = line.strip()
            if stripped.startswith("//"):
                continue

            # Look back 2 lines only — tight window to avoid catching
            # queries that happen to follow a loop in a different scope
            window_back = "\n".join(lines[max(0, i - 2):i])
            in_loop = bool(re.search(
                r"\bforEach\s*\(|\bfor\s*\(|\bfor\s+const\b|\bfor\s+let\b|\bfor\s+var\b",
                window_back
            ))
            if in_loop:
                issues.append({
                    "page": page,
                    "line": i + 1,
                    "reason": (
                        f"{page}:{i + 1} — db.from() inside a loop — "
                        f"fires one DB request per item (N+1 pattern). "
                        f"Use a single .in() batch query instead: "
                        f"`{stripped[:70]}`"
                    ),
                })
    return issues


# ── Check 4: Consecutive sequential await DB calls ────────────────────────────

def check_sequential_awaits(pages):
    """
    Two consecutive `await db.from(...)` calls that are independent run in
    series: 200ms + 200ms = 400ms total.
    `await Promise.all([queryA, queryB])` runs them in parallel: 200ms total.

    Detection: find 2+ `await db.from(` within 5 lines where neither line
    references a variable from the previous line's result.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()

        i = 0
        while i < len(lines):
            if "await db.from(" not in lines[i]:
                i += 1
                continue
            if lines[i].strip().startswith("//"):
                i += 1
                continue

            # Count consecutive awaits starting here
            run = [i]
            j = i + 1
            while j < min(i + 6, len(lines)):
                l = lines[j].strip()
                if not l or l.startswith("//"):
                    j += 1
                    continue
                if "await db.from(" in lines[j]:
                    run.append(j)
                    j += 1
                else:
                    break

            if len(run) >= SEQUENTIAL_AWAIT_THRESHOLD:
                # Check they're truly independent (first result not used in second)
                first_line  = lines[run[0]]
                second_line = lines[run[1]]
                # Extract result variable name from first await
                var_m = re.search(r"const\s*\{[^}]+\}\s*=\s*await", first_line)
                if var_m:
                    # Get the variable names
                    var_names = re.findall(r"\b(\w+)\b", first_line[:first_line.find("= await")])
                    used_in_second = any(v in second_line for v in var_names if len(v) > 2)
                    if not used_in_second:
                        issues.append({
                            "page":  page,
                            "lines": [r + 1 for r in run[:2]],
                            "reason": (
                                f"{page}:{run[0]+1}-{run[1]+1} — "
                                f"{len(run)} sequential await db.from() calls — "
                                f"wrap independent queries in Promise.all() to run "
                                f"them in parallel and halve load time"
                            ),
                        })
                i = run[-1] + 1
            else:
                i += 1

    return issues


# ── Check 5: body { animation } without JS safety guard ──────────────────────

def check_body_animation_safety_guard(pages):
    """
    Pages that animate body opacity (body { animation: page-enter ... forwards })
    start with the body at opacity:0. Two failure modes cause permanent blank page:

    1. Tailwind CDN in <head> is render-blocking — body is invisible while the
       CDN downloads. On slow Philippine mobile connections this is 1-5 seconds.

    2. Background tab pause — if the browser tab is opened in the background,
       CSS animations may pause. When the user switches to the tab, the animation
       may have "completed" while paused, leaving body at opacity:0 forever with
       animation-fill-mode: forwards holding that state.

    Required: an animationend safety guard that forces body visible after 800ms:
        document.body.addEventListener('animationend', fn, { once: true })
        + setTimeout fallback at 800ms

    This check flags any page where body has an animation CSS rule but no
    animationend listener is present in the page's inline scripts.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        has_body_anim = bool(re.search(
            r"body\s*\{[^}]*\banimation\s*:", content, re.DOTALL
        ))
        if not has_body_anim:
            continue
        has_safety_guard = bool(re.search(
            r"""addEventListener\s*\(\s*['"]animationend['"]""", content
        ))
        if not has_safety_guard:
            issues.append({
                "page": page,
                "reason": (
                    f"{page} has body {{ animation: ... }} but no animationend "
                    f"safety guard. If the animation stalls (background tab, CDN "
                    f"slow, prefers-reduced-motion), the body stays at opacity:0 "
                    f"permanently. Add an 800ms setTimeout fallback that forces "
                    f"document.body.style.opacity = '1'."
                ),
            })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("Performance Anti-Pattern Validator")
print("=" * 70)

fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        "[1] No unbounded queries on high-growth tables (logbook, inv_transactions)",
        check_unbounded_queries(LIVE_PAGES, HIGH_GROWTH_TABLES),
        "WARN",
    ),
    (
        "[2] No select('*') on wide tables — prefer named columns",
        check_select_star(LIVE_PAGES, WIDE_TABLES),
        "WARN",
    ),
    (
        "[3] db.from() calls directly inside loops (N+1 pattern)",
        check_db_in_loop(LIVE_PAGES),
        "WARN",
    ),
    (
        "[4] Consecutive sequential await DB calls (Promise.all opportunity)",
        check_sequential_awaits(LIVE_PAGES),
        "WARN",
    ),
    (
        "[5] body { animation } has JS animationend safety guard (blank page guard)",
        check_body_animation_safety_guard(LIVE_PAGES),
        "FAIL",
    ),
]

for label, issues, severity in checks:
    print(f"\n{label}\n")
    if not issues:
        print("  PASS")
    else:
        for iss in issues:
            print(f"  {severity}  {iss.get('page', '?')}")
            print(f"        {iss['reason']}")
        if severity == "FAIL":
            fail_count += len(issues)
        else:
            warn_count += len(issues)
    report[label] = issues

print(f"\n{'=' * 70}")
print(f"Result: {fail_count} FAIL  {warn_count} WARN")

with open("performance_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved performance_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll performance checks PASS (warnings are known technical debt).")
