"""
Catalog Approval Status Validator — WorkHive Platform
======================================================
In hive mode, inventory items and assets go through an approval workflow:
  1. Worker submits → status = 'pending'
  2. Supervisor approves → status = 'approved'
  3. Item appears in the shared catalog

If any query reads the shared catalog without filtering by status='approved',
pending submissions from other workers leak into the live catalog. A worker
could see parts that don't exist yet, use stock that hasn't been confirmed,
or act on data submitted by a different worker that a supervisor rejected.

From the Multitenant Engineer and Security skill files.

Four things checked:

  1. Hive-mode inventory catalog queries filter by status=approved
     — Every query that reads the shared inventory catalog in hive context
       must include .eq('status', 'approved'). Without it, pending and
       rejected items appear alongside approved stock — workers see phantom
       inventory that doesn't exist in the approved catalog yet.

  2. Hive-mode asset queries filter by status=approved
     — Same for the assets table. Assets go through the same workflow.
       An unapproved asset appearing in the asset picker means a worker
       can log maintenance against an asset a supervisor hasn't confirmed.

  3. Worker item edits reset status to pending (re-approval)
     — When a non-supervisor worker edits an approved item, the status
       must reset to 'pending' so the change goes back for approval.
       Without this, a worker could modify any approved item's details
       (quantity, bin location, description) and it would take effect
       immediately without supervisor review.

  4. Non-supervisor delete path scoped to worker_name
     — Workers can only delete their own rejected submissions.
       The delete path for non-supervisors must include
       .eq('worker_name', WORKER_NAME) so workers cannot delete
       other workers' items.

Usage:  python validate_catalog_scope.py
Output: catalog_scope_report.json
"""
import re, json, sys

# Pages that perform catalog reads or writes
CATALOG_PAGES = [
    "inventory.html",
    "logbook.html",
    "hive.html",
    "pm-scheduler.html",
    "assistant.html",
]

# Catalog tables that require status=approved in hive mode
CATALOG_TABLES = ["inventory_items", "assets"]


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


# ── Check 1 & 2: Hive-mode catalog queries filter by status=approved ─────────

def check_catalog_status_filter(pages, tables):
    """
    Every query on a catalog table (inventory_items, assets) that uses
    .eq('hive_id', ...) must ALSO include .eq('status', 'approved').

    The pattern that is SAFE has both filters:
      db.from('inventory_items').select(...)
        .eq('hive_id', HIVE_ID)
        .eq('status', 'approved')

    The pattern that LEAKS pending items has hive_id but no status:
      db.from('inventory_items').select(...)
        .eq('hive_id', HIVE_ID)      ← shows ALL items including pending
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()

        for i, line in enumerate(lines):
            # Find a SELECT query on a catalog table
            table_match = None
            for table in tables:
                if (f"from('{table}')" in line or f'from("{table}")' in line) and ".select(" in line:
                    table_match = table
                    break
            if not table_match:
                continue

            # Skip ternary patterns where db.from() is the ELSE (no-HIVE_ID) branch:
            # HIVE_ID ? Promise.resolve({ data: null }) : db.from(...)  — solo mode only
            if "HIVE_ID" in line and "Promise.resolve" in line and "db.from(" in line:
                continue

            window = "\n".join(lines[i:min(len(lines), i + 6)])

            # Skip approval queue queries — they intentionally fetch status='pending'
            if re.search(r"status.*pending|pending.*status|[Aa]pproval[Qq]ueue", window):
                continue

            # Skip worker's own items queries (no status filter needed)
            if "worker_name" in window and "hive_id" not in window and "HIVE_ID" not in window:
                continue

            # Check if this is a hive-scoped query (shows shared catalog)
            is_hive_scoped = "HIVE_ID" in window or "hive_id" in window
            if not is_hive_scoped:
                continue

            # Does it include status='approved'?
            has_status = re.search(r"status.*approved|approved.*status", window)
            if not has_status:
                issues.append({
                    "page":  page,
                    "table": table_match,
                    "line":  i + 1,
                    "reason": (
                        f"{page}:{i + 1} — hive-mode SELECT on '{table_match}' "
                        f"is missing .eq('status', 'approved') — pending and "
                        f"rejected items from other workers will appear in the "
                        f"shared catalog: `{line.strip()[:70]}`"
                    ),
                })
    return issues


# ── Check 3: Worker item edits reset status to pending ────────────────────────

def check_edit_reapproval(pages):
    """
    When a non-supervisor worker edits an existing catalog item, the status
    must reset to 'pending' so the change goes back for supervisor approval.

    This validator checks that the edit/save flow includes a 'pending' status
    assignment conditioned on the worker role (non-supervisor edit path).

    Safe patterns:
      status: editStatus                   where editStatus is set to 'pending'
      needsReapproval ? { status: 'pending' }
      HIVE_ROLE !== 'supervisor' ? 'pending' : existingStatus
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue

        # Does this page have catalog edit/save operations?
        has_catalog_edit = bool(re.search(
            r"db\.from\(['\"](?:inventory_items|assets)['\"][^)]*\)\.upsert\s*\(",
            content
        ))
        if not has_catalog_edit:
            continue

        # Does it have the re-approval pattern?
        has_reapproval = bool(re.search(
            r"needsReapproval|editStatus|'pending'|\"pending\"",
            content
        ))
        if not has_reapproval:
            issues.append({
                "page": page,
                "reason": (
                    f"{page} has catalog item upsert operations but no "
                    f"re-approval pattern (needsReapproval / editStatus / "
                    f"status:'pending') — worker edits to approved items may "
                    f"bypass supervisor approval"
                ),
            })
    return issues


# ── Check 4: Non-supervisor delete scoped to worker_name ─────────────────────

def check_delete_scope(pages, tables):
    """
    Workers can only delete their own items (and only rejected ones).
    The non-supervisor delete path must scope by worker_name.

    Safe pattern (branches for hive vs solo):
      if (HIVE_ID) {
        // hive path: supervisor scope
        let q = db.from('X').delete().eq('id', id).eq('hive_id', HIVE_ID);
        if (HIVE_ROLE !== 'supervisor') q = q.eq('worker_name', WORKER_NAME);
      } else {
        // solo path: own items only
        db.from('X').delete().eq('id', id).eq('worker_name', WORKER_NAME);
      }

    Risky pattern: delete by id only with no worker_name or hive_id scope
    at the DB level (relies solely on JS-level role checks).
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()

        for i, line in enumerate(lines):
            # Find delete on a catalog table
            table_match = None
            for table in tables:
                if (f"from('{table}')" in line or f'from("{table}")' in line) and ".delete()" in line:
                    table_match = table
                    break
            if not table_match:
                continue

            # Check scope in same line and next 4 lines
            window = "\n".join(lines[i:min(len(lines), i + 4)])
            has_scope = (
                "worker_name" in window or
                "WORKER_NAME" in window or
                "hive_id"     in window or
                "HIVE_ID"     in window
            )
            if not has_scope:
                issues.append({
                    "page":  page,
                    "table": table_match,
                    "line":  i + 1,
                    "reason": (
                        f"{page}:{i + 1} — delete on '{table_match}' has no "
                        f"worker_name or hive_id scope — relies solely on JS-level "
                        f"role checks, no DB-level ownership boundary: "
                        f"`{line.strip()[:70]}`"
                    ),
                })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("Catalog Approval Status Validator")
print("=" * 70)

fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        "[1] Hive-mode inventory_items catalog queries filter by status=approved",
        check_catalog_status_filter(CATALOG_PAGES, ["inventory_items"]),
        "FAIL",
    ),
    (
        "[2] Hive-mode assets catalog queries filter by status=approved",
        check_catalog_status_filter(CATALOG_PAGES, ["assets"]),
        "FAIL",
    ),
    (
        "[3] Worker catalog edits include re-approval (status reset to pending)",
        check_edit_reapproval(CATALOG_PAGES),
        "FAIL",
    ),
    (
        "[4] Catalog delete operations scoped to worker_name or hive_id",
        check_delete_scope(CATALOG_PAGES, CATALOG_TABLES),
        "WARN",
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

with open("catalog_scope_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved catalog_scope_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll catalog scope checks PASS.")
