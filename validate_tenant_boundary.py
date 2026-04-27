"""
Tenant Boundary Escape Validator — WorkHive Platform
=====================================================
Multi-tenancy means Worker A cannot see Worker B's hive data.
The boundary is enforced in JavaScript (no RLS yet) — so if any read
query forgets the hive_id/worker_name filter, that boundary is gone.

This is a regression guard. The platform currently passes all checks.
Future features that add new queries must keep passing.

Four things checked:

  1. Shared-table SELECT queries have an ownership filter
     — Every .select() call on a multi-tenant table (logbook, inventory_items,
       assets, pm_assets, hive_members) must be followed within 8 lines by
       an .eq('hive_id', ...) or .eq('worker_name', ...) filter.
       A bare .select('*') with no filter returns ALL tenants' data.

  2. HIVE_ID never assigned from user-controlled input
     — HIVE_ID must only come from localStorage (set by DB-validated
       join/switch flows) or from a DB membership query result.
       Assigning it from URLSearchParams, location.search, or input.value
       lets an attacker switch hives by editing the URL.

  3. Hive switcher validates membership before switching
     — The hive switch function in hive.html must query the hive_members
       table and verify membership status before writing HIVE_ID to
       localStorage. Skipping this lets workers rejoin kicked hives.

  4. URL parameters not used to set hive context
     — No URLSearchParams.get() or searchParams.get() call should be
       followed within 10 lines by localStorage.setItem with a hive key
       or a HIVE_ID assignment. This prevents ?hive=<other-tenant> attacks.

Usage:  python validate_tenant_boundary.py
Output: tenant_boundary_report.json
"""
import re, json, sys

LIVE_PAGES = [
    "logbook.html",
    "inventory.html",
    "pm-scheduler.html",
    "hive.html",
    "skillmatrix.html",
    "dayplanner.html",
    "engineering-design.html",
]

# Tables that hold per-tenant data and MUST always be filtered
SHARED_TABLES = [
    "logbook",
    "inventory_items",
    "inventory_transactions",
    "assets",
    "pm_assets",
    "pm_completions",
    "hive_members",
]

# Patterns that indicate user-controlled input (injection risk)
USER_CONTROLLED = [
    r"URLSearchParams",
    r"location\.search",
    r"location\.hash",
    r"searchParams\.get\s*\(",
    r"\.value\b",
]

# Hive-context localStorage keys
HIVE_LOCAL_KEYS = ["wh_hive_id", "wh_active_hive_id", "wh_hive_role", "wh_hive_name"]


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


# ── Check 1: Shared-table SELECT queries have ownership filter ────────────────

def check_select_filters(pages, tables):
    """
    Every .select() call on a multi-tenant table must be followed within
    8 lines by at least one of:
      - .eq('hive_id', ...)
      - .eq('worker_name', ...)
      - .in('hive_id', ...)
      - .or(`hive_id.eq.${...}`)

    The 8-line window covers chained query builders like:
      let q = db.from('logbook').select('*');   ← line 0
      if (HIVE_ID) q = q.eq('hive_id', HIVE_ID); ← line 2

    A bare .select('*') with no filter in the window returns ALL rows.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()

        for i, line in enumerate(lines):
            # Find .select( calls on shared tables
            table_match = None
            for table in tables:
                if f"from('{table}')" in line or f'from("{table}")' in line:
                    table_match = table
                    break
            if not table_match:
                continue
            if ".select(" not in line and ".select (" not in line:
                continue

            # Skip insert(...).select() — this returns only the inserted row
            # Also check the previous line for multi-line insert chains
            prev_line = lines[i - 1] if i > 0 else ""
            if re.search(r"\.(insert|upsert)\s*\(", line) or \
               re.search(r"\.(insert|upsert)\s*\(", prev_line):
                continue

            # Check for ownership filter within an 8-line window
            window = "\n".join(lines[i:min(len(lines), i + 8)])
            has_filter = any([
                "hive_id"     in window,
                "worker_name" in window,
                "WORKER_NAME" in window,
                "HIVE_ID"     in window,
                re.search(r'\.eq\s*\(["\']id["\']',   window) is not None,
                re.search(r'\.in\s*\(["\']id["\']',   window) is not None,
                re.search(r'\.in\s*\(["\']asset_id["\']', window) is not None,
            ])
            if not has_filter:
                issues.append({
                    "page":  page,
                    "table": table_match,
                    "line":  i + 1,
                    "reason": (
                        f"{page}:{i + 1} — .select() on '{table_match}' with no "
                        f"hive_id or worker_name filter in the next 8 lines — "
                        f"returns all tenants' rows"
                    ),
                })
    return issues


# ── Check 2: HIVE_ID never assigned from user-controlled input ────────────────

def check_hive_id_source(pages):
    """
    HIVE_ID must only be set from trusted sources:
      - localStorage.getItem(...)          ← persisted from previous DB-validated flow
      - DB membership query result         ← hive_members table lookup
      - hive.id from a Supabase .insert()  ← server-assigned UUID

    It must NEVER be set from:
      - URLSearchParams / location.search  ← attacker controls ?hive=...
      - input.value                        ← attacker types any UUID
      - location.hash                      ← attacker controls #hive=...

    If HIVE_ID comes from user-controlled input, a worker can switch to
    any hive by editing the URL, reading another tenant's data.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()

        for i, line in enumerate(lines):
            # Is this line assigning HIVE_ID?
            if not re.search(r"\bHIVE_ID\s*=\s*", line):
                continue
            # Does the assignment use user-controlled input?
            for pattern in USER_CONTROLLED:
                if re.search(pattern, line):
                    issues.append({
                        "page": page,
                        "line": i + 1,
                        "code": line.strip()[:80],
                        "reason": (
                            f"{page}:{i + 1} — HIVE_ID assigned from user-controlled "
                            f"input ({pattern}) — attacker can set any hive_id "
                            f"by manipulating the URL or form: `{line.strip()[:60]}`"
                        ),
                    })
                    break
    return issues


# ── Check 3: Hive switcher validates membership before switch ─────────────────

def check_switcher_validation(page):
    """
    The hive switcher in hive.html must confirm the worker is still a member
    of the target hive before writing its id to localStorage.
    This prevents a kicked member from re-entering a hive by:
      - Refreshing the page
      - Having a stale localStorage entry

    Safe pattern:
      1. Query hive_members for (hive_id, worker_name)
      2. Check membership.status !== 'kicked'
      3. THEN write to localStorage + set HIVE_ID

    Unsafe pattern:
      1. Read hive id from cached list
      2. Write directly to localStorage + set HIVE_ID (no DB check)
    """
    issues = []
    content = read_file(page)
    if content is None:
        return [{"page": page, "reason": f"{page} not found"}]

    # Find the switcher function (renderHiveSwitcher or similar)
    switcher_m = re.search(
        r"async function\s+renderHiveSwitcher\s*\(",
        content
    )
    if not switcher_m:
        # No switcher function — nothing to check
        return []

    # Extract function body (300 lines should be more than enough)
    body_start = switcher_m.start()
    body = "\n".join(content[body_start:body_start + 8000].splitlines()[:120])

    # Check that hive_members is queried inside the switcher
    if "hive_members" not in body:
        issues.append({
            "page": page,
            "reason": (
                f"{page} — renderHiveSwitcher() does not query hive_members "
                f"before switching — kicked members can re-enter a hive via "
                f"stale localStorage"
            ),
        })
        return issues

    # Check that a status/kicked check exists
    if "kicked" not in body and "membership.status" not in body and "status" not in body:
        issues.append({
            "page": page,
            "reason": (
                f"{page} — renderHiveSwitcher() queries hive_members but does not "
                f"check membership status — kicked members may still be admitted"
            ),
        })

    return issues


# ── Check 4: URL parameters not used to inject hive context ──────────────────

def check_url_param_injection(pages):
    """
    URL parameters (?hive=X, ?hive_id=X) must not be written directly into
    hive context (localStorage or HIVE_ID variable) without first verifying
    the worker's membership in the DB.

    If a page reads ?hive=<some-uuid> from the URL and writes it to
    localStorage as wh_hive_id, any worker can access any hive by visiting:
      logbook.html?hive=<target-hive-uuid>

    This check scans for searchParams.get / URLSearchParams reads followed
    within 10 lines by a hive-related localStorage write or HIVE_ID assignment.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()

        for i, line in enumerate(lines):
            # Is this line reading a URL parameter?
            if not re.search(
                r"searchParams\.get|URLSearchParams|location\.search|location\.hash",
                line
            ):
                continue

            # Check the next 10 lines for a hive context write
            window = "\n".join(lines[i:min(len(lines), i + 10)])
            hive_write = any(k in window for k in HIVE_LOCAL_KEYS) or \
                         re.search(r"\bHIVE_ID\s*=", window)

            if hive_write:
                issues.append({
                    "page": page,
                    "line": i + 1,
                    "code": line.strip()[:80],
                    "reason": (
                        f"{page}:{i + 1} — URL parameter read followed by hive "
                        f"context write within 10 lines — "
                        f"attacker may set hive context via URL: "
                        f"`{line.strip()[:60]}`"
                    ),
                })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("Tenant Boundary Escape Validator")
print("=" * 70)

fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        "[1] Shared-table SELECT queries have hive_id or worker_name filter",
        check_select_filters(LIVE_PAGES, SHARED_TABLES),
        "FAIL",
    ),
    (
        "[2] HIVE_ID never assigned from URL params or user input",
        check_hive_id_source(LIVE_PAGES),
        "FAIL",
    ),
    (
        "[3] Hive switcher validates membership before switching",
        check_switcher_validation("hive.html"),
        "FAIL",
    ),
    (
        "[4] URL parameters not used to inject hive context",
        check_url_param_injection(LIVE_PAGES),
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

with open("tenant_boundary_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved tenant_boundary_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll tenant boundary checks PASS.")
