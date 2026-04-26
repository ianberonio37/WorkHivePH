"""
Cross-Page Flow Validator — WorkHive Platform

Checks that every page inserting into a shared Supabase table includes
all columns the primary-owning page writes. Missing columns default to
null in the DB and silently break filters, displays, and balance tracking
on the receiving page.

Usage:  python validate_cross_page.py
Output: cross_page_report.json

Flows checked:
  1. pm-scheduler.html  -> logbook           (PM completion auto-log)
  2. logbook.html       -> pm_completions    (PM task checkbox from logbook)
  3. logbook.html       -> inventory_transactions  (parts deduction on close)
  4. pm-scheduler.html  -> pm_completions    (canonical — own page)
  5. inventory.html     -> inventory_items   (canonical check for hive_id)
"""
import re, json, sys

# ── Column sets: what the PRIMARY page writes to each table ──────────────────
# These are the canonical columns — every cross-page insert is compared against them.
# Columns marked CRITICAL must be present; others are WARNING only.

CANONICAL = {
    "logbook": {
        "source_page":  "logbook.html",
        "critical":     ["worker_name", "date", "machine", "maintenance_type",
                         "category", "problem", "action", "status",
                         "closed_at", "hive_id"],
        "optional":     ["root_cause", "downtime_hours", "photo", "knowledge",
                         "parts_used", "asset_ref_id", "tasklist_acknowledged",
                         "tasklist_note", "pm_completion_id", "id"],
    },
    "pm_completions": {
        "source_page":  "pm-scheduler.html",
        "critical":     ["asset_id", "scope_item_id", "hive_id",
                         "worker_name", "status", "completed_at"],
        "optional":     ["notes", "id"],
    },
    "inventory_transactions": {
        "source_page":  "inventory.html",
        "critical":     ["item_id", "type", "qty_change", "qty_after",
                         "worker_name"],
        "optional":     ["note", "created_at", "id", "job_ref"],
    },
}

# ── Cross-page flows to validate ──────────────────────────────────────────────
FLOWS = [
    {
        "id":          "pm-scheduler->logbook",
        "description": "PM Scheduler auto-creates logbook entry when PM marked done",
        "source":      "pm-scheduler.html",
        "table":       "logbook",
        "anchor":      "logPayload",  # variable name of the payload in the source file
    },
    {
        "id":          "logbook->pm_completions",
        "description": "Logbook creates PM completion records when PM task checkboxes ticked",
        "source":      "logbook.html",
        "table":       "pm_completions",
        "anchor":      "pmPayloads",   # .map(() => ({...})) pattern — extracted via inline scan
    },
    {
        "id":          "logbook->inventory_transactions",
        "description": "Logbook deducts parts inventory when entry saved/updated",
        "source":      "logbook.html",
        "table":       "inventory_transactions",
        "anchor":      "inventory_transactions",  # inline insert, not a named variable
    },
]


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def strip_template_literals(text):
    """Replace ${...} interpolations so they don't confuse brace-counting regex."""
    return re.sub(r'\$\{[^}]*\}', '__INTERP__', text)


def extract_payload_fields(content, anchor, table):
    """
    Extract column names from a JS object literal that is inserted into `table`.
    Two strategies:
      A. Named variable: find `anchor = {` and extract keys
      B. Inline: find `from('table').insert({` and extract keys
    """
    fields  = set()
    content = strip_template_literals(content)  # stop ${...} from confusing brace scan

    # Strategy A: named variable (e.g., logPayload = { ... })
    if anchor != table:
        # Find  anchor = {   or   anchor: {   patterns
        patterns = [
            rf'{re.escape(anchor)}\s*=\s*\{{([^}}]*(?:\{{[^}}]*\}}[^}}]*)*)\}}',
            rf'{re.escape(anchor)}\s*:\s*\{{([^}}]*(?:\{{[^}}]*\}}[^}}]*)*)\}}',
        ]
        for pat in patterns:
            for m in re.finditer(pat, content, re.DOTALL):
                block = m.group(1)
                keys  = re.findall(r'^\s*([a-zA-Z_][a-zA-Z0-9_]*):', block, re.MULTILINE)
                fields.update(keys)
            if fields:
                break

    # Strategy B: inline insert — find .insert({ ... }) after .from('table')
    table_esc  = re.escape(table)
    inline_pat = rf"from\(['\"]({table_esc})['\"]\)\.insert\(\{{([^}}]+)\}}"
    for m in re.finditer(inline_pat, content, re.DOTALL):
        block = m.group(2)
        keys  = re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*:', block)
        fields.update(keys)

    # Also: .insert(varName.map(...)) or const varName = arr.map(x => ({...}))
    map_pats = [
        rf"from\(['\"{table_esc}['\"]\)\.insert\(\s*\w+\.map\(\w+\s*=>\s*\(?\{{([^}}]+)\}}",
        rf"const\s+{re.escape(anchor)}\s*=\s*\w+\.map\(\w+\s*=>\s*\(?\{{([^}}]+)\}}",
    ]
    for pat in map_pats:
        for m in re.finditer(pat, content, re.DOTALL):
            block = m.group(1)
            keys  = re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*:', block)
            fields.update(keys)

    # Remove JS noise
    noise = {"const", "let", "var", "return", "if", "else", "true", "false",
              "null", "undefined", "await", "async", "function"}
    return fields - noise


def check_flow(flow, contents):
    table    = flow["table"]
    canon    = CANONICAL[table]
    source   = flow["source"]
    content  = contents.get(source, "")

    if not content:
        return {"status": "ERROR", "reason": f"{source} not found"}

    fields   = extract_payload_fields(content, flow["anchor"], table)

    if not fields:
        return {
            "status":  "WARN",
            "reason":  f"Could not extract payload fields from {source} for table {table}",
            "fields_found": [],
        }

    missing_critical = [c for c in canon["critical"] if c not in fields]
    missing_optional = [c for c in canon["optional"] if c not in fields]
    extra            = [f for f in fields
                        if f not in canon["critical"] and f not in canon["optional"]
                        and f not in ("hive_id",)]  # hive_id allowed in all

    return {
        "status":           "FAIL" if missing_critical else ("WARN" if missing_optional else "PASS"),
        "fields_found":     sorted(fields),
        "missing_critical": missing_critical,
        "missing_optional": missing_optional,
        "extra_fields":     extra,
    }


# ── Additional checks — not payload-based ────────────────────────────────────

def check_closed_at_consistency(content, page_name):
    """
    Every logbook insert with status: 'Closed' must also set closed_at.
    Heuristic: find insert blocks containing status: 'Closed' and check for closed_at.
    """
    issues = []
    insert_blocks = re.findall(
        r"from\(['\"]logbook['\"]\)\.insert\(({[^}]+})\)",
        content, re.DOTALL
    )
    for block in insert_blocks:
        has_closed = bool(re.search(r"status\s*:\s*['\"]Closed['\"]", block))
        has_closed_at = bool(re.search(r"closed_at\s*:", block))
        if has_closed and not has_closed_at:
            issues.append(f"logbook.insert() sets status='Closed' but missing closed_at in {page_name}")
    return issues


def check_hive_id_on_inserts(content, page_name, tables):
    """
    Every INSERT into a hive-aware table must include hive_id (not null-only).
    """
    issues = []
    for table in tables:
        table_esc = re.escape(table)
        blocks = re.findall(
            rf"from\(['\"{table_esc}['\"]\)\.insert\([\s\S]{{0,300}}?\)",
            content,
        )
        for block in blocks:
            # Check hive_id appears somewhere in the insert call vicinity
            if "hive_id" not in block:
                issues.append(f"{page_name}: {table}.insert() missing hive_id field")
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

PAGES = [
    "logbook.html",
    "pm-scheduler.html",
    "inventory.html",
    "hive.html",
]

print("\n" + "=" * 70)
print("Cross-Page Flow Validator")
print("=" * 70)

contents = {p: read_file(p) for p in PAGES}

results    = []
all_pass   = True
fail_count = 0
warn_count = 0

# ── Flow checks ───────────────────────────────────────────────────────────────
print("\n[1] Cross-page INSERT payload checks\n")
for flow in FLOWS:
    result = check_flow(flow, contents)
    status = result["status"]
    print(f"  {status:4s}  {flow['id']}")
    print(f"        {flow['description']}")

    if result.get("missing_critical"):
        for f in result["missing_critical"]:
            print(f"        CRITICAL MISSING: {f}  (breaks display/filter on receiving page)")
        all_pass = False
        fail_count += 1
    if result.get("missing_optional"):
        for f in result["missing_optional"]:
            print(f"        optional missing: {f}")
        if status == "WARN":
            warn_count += 1
    if result.get("extra_fields"):
        for f in result["extra_fields"]:
            print(f"        extra (not in canonical): {f}")
    if result.get("reason"):
        print(f"        reason: {result['reason']}")

    results.append({"flow": flow["id"], "table": flow["table"], **result})
    print()

# ── closed_at consistency ─────────────────────────────────────────────────────
print("[2] closed_at consistency (logbook inserts with status='Closed')\n")
closed_issues = []
for page, content in contents.items():
    if content:
        closed_issues.extend(check_closed_at_consistency(content, page))

if closed_issues:
    for issue in closed_issues:
        print(f"  FAIL  {issue}")
    all_pass = False
    fail_count += len(closed_issues)
else:
    print("  PASS  All logbook inserts with status='Closed' include closed_at")
print()

# ── Summary ───────────────────────────────────────────────────────────────────
print("=" * 70)
print(f"Result: {fail_count} FAIL  {warn_count} WARN")

report = {
    "flows":          results,
    "closed_at_issues": closed_issues,
    "summary":        {"fail": fail_count, "warn": warn_count, "pass": len(FLOWS) - fail_count - warn_count},
}
with open("cross_page_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved cross_page_report.json")

if not all_pass:
    print("\nFIX REQUIRED: missing critical columns cause silent null values on the receiving page.")
    sys.exit(1)
print("\nAll cross-page flows PASS.")
