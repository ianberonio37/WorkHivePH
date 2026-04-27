"""
Data Governance Validator — WorkHive Platform
==============================================
Governance means: data belongs to someone, only the right people can
touch it, and nothing sensitive leaks where it shouldn't.

Without it:
  - A worker saves data with no owner tag — impossible to filter by hive later.
  - A delete operation only scopes by 'id' — any row could be deleted by ID.
  - A privileged action (approve, kick) has no role check — any worker executes it.
  - An API key or email address leaks into the AI system prompt context.

Four things checked:

  1. Owner tag on inserts      — worker_name must be in every insert/upsert
                                 payload for worker-owned tables (logbook,
                                 inventory_items, assets, pm_assets). Without it,
                                 data orphans that can't be scoped to a worker.

  2. Delete scope              — every .delete() on a shared table must filter
                                 by worker_name OR hive_id, not just by 'id'.
                                 An id-only delete is a WARN (JS-level guards exist,
                                 but DB-level scope is missing until RLS ships).

  3. Sensitive data in AI      — the floating-ai.js system prompt must not contain
                                 email addresses, raw API keys, phone numbers, or
                                 password patterns. These would be visible to anyone
                                 who reads the network request.

  4. Privileged op role gates  — functions that approve, reject, or kick members
                                 in hive.html must check HIVE_ROLE before executing.
                                 Missing gate = any worker can perform supervisor actions.

Usage:  python validate_governance.py
Output: governance_report.json
"""
import re, json, sys

FLOAT_JS = "floating-ai.js"

# Tables whose rows are owned by a specific worker
WORKER_OWNED_TABLES = ["logbook", "inventory_items", "assets", "pm_assets"]

# Pages that contain write operations to worker-owned tables
WRITE_PAGES = [
    "logbook.html",
    "inventory.html",
    "pm-scheduler.html",
    "hive.html",
]

# Privileged functions in hive.html that MUST have a role check
PRIVILEGED_FUNCTIONS = [
    ("removeMember",  "kick / remove hive member"),
    ("approveItem",   "approve submitted item"),
    ("rejectItem",    "reject submitted item"),
]


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


# ── Check 1: worker_name in worker-owned inserts ──────────────────────────────

def check_owner_tag(pages, tables):
    """
    Every insert/upsert into a worker-owned table must include worker_name
    in the payload. Without it, data cannot be filtered back to its owner —
    it orphans in the database with no owner context.

    Note: spread syntax (...item, ...asset) may carry worker_name implicitly.
    This check looks for worker_name anywhere within 25 lines of the insert call
    to account for both explicit and spread-based inclusion.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()

        for i, line in enumerate(lines):
            # Is this line a DB insert or upsert on a worker-owned table?
            m = re.search(
                r"db\.from\(['\"](" + "|".join(re.escape(t) for t in tables) + r")['\"]"
                r"\)[^.]*\.(insert|upsert)\s*\(",
                line
            )
            if not m:
                continue

            table = m.group(1)
            # Scan 20 lines before (payload build) + 10 lines after (spread vars)
            window = "\n".join(lines[max(0, i - 20):min(len(lines), i + 10)])
            if "worker_name" not in window and "WORKER_NAME" not in window:
                issues.append({
                    "page":  page,
                    "table": table,
                    "line":  i + 1,
                    "reason": (
                        f"{page}:{i + 1} — insert/upsert into '{table}' has no "
                        f"worker_name in the next 25 lines — "
                        f"rows will have no owner tag (unscoped data)"
                    ),
                })
    return issues


# ── Check 2: Delete operations scoped to owner or hive ───────────────────────

def check_delete_scope(pages):
    """
    Every .delete() call on a shared table must filter by worker_name OR
    hive_id, not just by 'id'. Filtering by id only means any row in the
    table can be targeted — no ownership boundary at the DB level.

    This is a WARN (not FAIL) because JavaScript-level role checks provide
    a first line of defence while RLS is pending.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()

        for i, line in enumerate(lines):
            if ".delete()" not in line and ".delete( )" not in line:
                continue
            if "db.from(" not in line:
                continue

            # Check if this line OR the next 3 lines have an owner scope
            window = "\n".join(lines[i:min(len(lines), i + 4)])
            has_owner_scope = (
                "worker_name" in window or
                "hive_id"     in window or
                "WORKER_NAME" in window or
                "HIVE_ID"     in window
            )
            if not has_owner_scope:
                issues.append({
                    "page": page,
                    "line": i + 1,
                    "code": line.strip()[:80],
                    "reason": (
                        f"{page}:{i + 1} — delete scoped only by 'id' with no "
                        f"worker_name or hive_id filter — "
                        f"DB-level ownership boundary missing (RLS pending): "
                        f"`{line.strip()[:60]}`"
                    ),
                })
    return issues


# ── Check 3: No sensitive data in AI system prompt ───────────────────────────

def check_sensitive_in_prompt(path):
    """
    The floating-ai.js system prompt is sent to the AI API on every message.
    It must not contain email addresses, API keys, phone numbers, or passwords.
    If it did, these would appear in plain text in every network request.
    """
    issues = []
    content = read_file(path)
    if content is None:
        return [{"page": path, "reason": f"{path} not found"}]

    # Find the system prompt string
    sys_m = re.search(
        r"const system\s*=\s*`([\s\S]{0,5000}?)`",
        content
    )
    if not sys_m:
        return []

    prompt_text = sys_m.group(1)

    checks = [
        (r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", "email address"),
        (r"\b(?:password|passwd)\s*[:=]\s*\S+",                 "password value"),
        (r"\b(?:api[_-]?key|apikey)\s*[:=]\s*['\"]?\w{10,}",   "API key value"),
        (r"\+?[0-9]{7,15}\b",                                   "phone number"),
    ]

    for pattern, label in checks:
        m = re.search(pattern, prompt_text, re.IGNORECASE)
        if m:
            issues.append({
                "page":  path,
                "found": label,
                "reason": (
                    f"{path} — system prompt contains a {label}: "
                    f"`{m.group(0)[:40]}` — "
                    f"this appears in plain text in every AI API request"
                ),
            })
    return issues


# ── Check 4: Privileged operations have role gate ────────────────────────────

def check_role_gates(page, functions):
    """
    Supervisor-only functions (approve, reject, kick) must check HIVE_ROLE
    before executing. A missing gate means any logged-in worker can call the
    function from the browser console and perform a supervisor action.
    """
    issues = []
    content = read_file(page)
    if content is None:
        return [{"page": page, "reason": f"{page} not found"}]

    for func_name, description in functions:
        # Find the function definition
        func_m = re.search(
            rf"(?:async\s+)?function\s+{re.escape(func_name)}\s*\(",
            content
        )
        if not func_m:
            continue

        # Extract the function body (next 30 lines)
        start = func_m.start()
        body  = "\n".join(content[start:start + 1500].splitlines()[:30])

        if "HIVE_ROLE" not in body:
            issues.append({
                "page":     page,
                "function": func_name,
                "reason": (
                    f"{page} — `{func_name}()` ({description}) has no HIVE_ROLE "
                    f"check in first 30 lines — any worker can execute this action"
                ),
            })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("Data Governance Validator")
print("=" * 70)

fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        "[1] worker_name present in all worker-owned inserts",
        check_owner_tag(WRITE_PAGES, WORKER_OWNED_TABLES),
        "FAIL",
    ),
    (
        "[2] Delete operations scoped to owner or hive (not id-only)",
        check_delete_scope(WRITE_PAGES),
        "WARN",
    ),
    (
        "[3] No sensitive data (email / key / password) in AI system prompt",
        check_sensitive_in_prompt(FLOAT_JS),
        "FAIL",
    ),
    (
        "[4] Privileged hive operations gated by HIVE_ROLE check",
        check_role_gates("hive.html", PRIVILEGED_FUNCTIONS),
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

with open("governance_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved governance_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll governance checks PASS.")
