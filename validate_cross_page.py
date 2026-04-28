"""
Cross-Page Flow Validator — WorkHive Platform
==============================================
Checks that every page inserting into a shared Supabase table includes
all columns the primary-owning page writes. Missing columns default to
null in the DB and silently break filters, displays, and balance tracking
on the receiving page.

  Layer 1 — INSERT payload completeness
    1.  pm-scheduler -> logbook         — PM auto-log includes critical logbook fields
    2.  logbook -> pm_completions        — logbook PM checkbox creates completion records
    3.  logbook -> inventory_transactions — parts deduction includes all required columns

  Layer 2 — Schema health
    4.  hive_id critical in all tables   — every hive-aware table has hive_id as critical
    5.  New logbook fields in CANONICAL  — failure_consequence/readings_json/production_output

  Layer 3 — Cross-page consistency
    6.  closed_at consistency            — every logbook insert with status='Closed' sets closed_at
    7.  Source page writes own criticals — canonical source page includes all its own critical fields

Usage:  python validate_cross_page.py
Output: cross_page_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

# ── CANONICAL: what the primary page writes to each table ─────────────────────
# critical = must be present in every cross-page insert (FAIL if missing)
# optional = present in the source page but legitimately omitted in some flows

CANONICAL = {
    "logbook": {
        "source_page": "logbook.html",
        "critical":    ["worker_name", "date", "machine", "maintenance_type",
                        "category", "problem", "action", "status",
                        "closed_at", "hive_id"],
        "optional":    ["root_cause", "downtime_hours", "photo", "knowledge",
                        "parts_used", "asset_ref_id", "tasklist_acknowledged",
                        "tasklist_note", "pm_completion_id", "id",
                        "failure_consequence", "readings_json", "production_output"],
    },
    "pm_completions": {
        "source_page": "pm-scheduler.html",
        "critical":    ["asset_id", "scope_item_id", "hive_id",
                        "worker_name", "status", "completed_at"],
        "optional":    ["notes", "id"],
    },
    "inventory_transactions": {
        "source_page": "logbook.html",
        "critical":    ["item_id", "type", "qty_change", "qty_after",
                        "worker_name", "hive_id"],
        "optional":    ["note", "created_at", "id", "job_ref"],
    },
}

FLOWS = [
    {
        "id":          "pm-scheduler->logbook",
        "description": "PM Scheduler auto-creates logbook entry when PM marked done",
        "source":      "pm-scheduler.html",
        "table":       "logbook",
        "anchor":      "logPayload",
        "check":       "flow_pm_scheduler_logbook",
    },
    {
        "id":          "logbook->pm_completions",
        "description": "Logbook creates PM completion records when PM task checkboxes ticked",
        "source":      "logbook.html",
        "table":       "pm_completions",
        "anchor":      "pmPayloads",
        "check":       "flow_logbook_pm_completions",
    },
    {
        "id":          "logbook->inventory_transactions",
        "description": "Logbook deducts parts inventory when entry saved/updated",
        "source":      "logbook.html",
        "table":       "inventory_transactions",
        "anchor":      "inventory_transactions",
        "check":       "flow_logbook_inventory_transactions",
    },
]

PAGES = ["logbook.html", "pm-scheduler.html", "inventory.html", "hive.html"]

JS_NOISE = {"const", "let", "var", "return", "if", "else", "true", "false",
            "null", "undefined", "await", "async", "function"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def strip_string_literals(text):
    """Remove single-line quoted string content to avoid matching words inside values."""
    text = re.sub(r"'[^'\n]*'", "''", text)
    text = re.sub(r'"[^"\n]*"', '""', text)
    text = re.sub(r'`[^`\n]*`', '``', text)  # backtick template literals (single-line)
    return text


def strip_template_literals(text):
    return re.sub(r'\$\{[^}]*\}', '__INTERP__', text)


def extract_object_body(text, start):
    """Extract the content of { ... } starting at `start` using bracket depth."""
    depth = 0
    i = start
    while i < len(text):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return text[start + 1:i]
        i += 1
    return ""


def _extract_and_clean_keys(raw_body):
    """Strip string values from a body and extract field keys."""
    body = strip_string_literals(strip_template_literals(raw_body))
    keys = re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*:', body)
    return set(keys) - JS_NOISE


def extract_payload_fields(content, anchor, table):
    """
    Extract field names from JS object literals inserted into `table`.
    Uses original content for all searches (avoids position mismatch with stripped content).
    Strips string literals only on the extracted body, not the full file.
    """
    fields = set()

    # Strategy A: named variable `anchor = { ... }` (direct object, not .map)
    if anchor != table:
        for pat in [
            rf'{re.escape(anchor)}\s*=\s*\{{',
            rf'{re.escape(anchor)}\s*:\s*\{{',
        ]:
            for m in re.finditer(pat, content):
                brace_start = content.find('{', m.start())
                body = extract_object_body(content, brace_start)
                fields.update(_extract_and_clean_keys(body))
            if fields:
                break

    # Strategy B: inline .from('table').insert({ ... })
    for search_str in (f"from('{table}')", f'from("{table}")'):
        pos = 0
        while True:
            idx = content.find(search_str, pos)
            if idx == -1:
                break
            insert_pos = content.find('.insert(', idx)
            if insert_pos == -1 or insert_pos > idx + 100:
                pos = idx + 1; continue
            brace_start = content.find('{', insert_pos)
            if brace_start == -1:
                pos = idx + 1; continue
            body = extract_object_body(content, brace_start)
            fields.update(_extract_and_clean_keys(body))
            pos = idx + 1

    # Strategy C: const anchor = arr.map(x => ({ ... }))
    for pat in [rf'const\s+{re.escape(anchor)}\s*=\s*\w+\.map\s*\(']:
        for m in re.finditer(pat, content):
            brace_start = content.find('{', m.end())
            if brace_start == -1:
                continue
            body = extract_object_body(content, brace_start)
            fields.update(_extract_and_clean_keys(body))

    # Strategy C2: .from('table').insert(arr.map(...))
    for search_str in (f"from('{table}')", f'from("{table}")'):
        pos = 0
        while True:
            idx = content.find(search_str, pos)
            if idx == -1:
                break
            insert_pos = content.find('.insert(', idx)
            if insert_pos == -1 or insert_pos > idx + 100:
                pos = idx + 1; continue
            map_pos = content.find('.map(', insert_pos)
            if map_pos == -1 or map_pos > insert_pos + 50:
                pos = idx + 1; continue
            brace_start = content.find('{', map_pos)
            if brace_start == -1:
                pos = idx + 1; continue
            body = extract_object_body(content, brace_start)
            fields.update(_extract_and_clean_keys(body))
            pos = idx + 1

    return fields - JS_NOISE


# ── Layer 1: INSERT payload completeness ──────────────────────────────────────

def check_flow(flow, contents):
    table   = flow["table"]
    canon   = CANONICAL[table]
    source  = flow["source"]
    content = contents.get(source, "")
    if not content:
        return None, [{"check": flow["check"],
                       "reason": f"{source} not found — cannot check this flow"}]

    fields           = extract_payload_fields(content, flow["anchor"], table)
    if not fields:
        return None, [{"check": flow["check"],
                       "reason": f"Could not extract payload fields from {source} for table {table}",
                       "skip": True}]

    all_known        = set(canon["critical"]) | set(canon["optional"]) | {"hive_id"}
    missing_critical = [c for c in canon["critical"] if c not in fields]
    issues           = []
    for f in missing_critical:
        issues.append({"check": flow["check"], "field": f,
                       "reason": f"{flow['id']}: critical field '{f}' missing from {source} insert into {table} — null value on receiving page"})
    return fields, issues


# ── Layer 2: Schema health ────────────────────────────────────────────────────

def check_hive_id_critical():
    """Every CANONICAL table must have hive_id in its critical list."""
    issues = []
    for table, canon in CANONICAL.items():
        if "hive_id" not in canon["critical"]:
            issues.append({"check": "hive_id_critical",
                           "reason": f"CANONICAL for '{table}' does not list hive_id as critical — cross-page inserts may omit it without failing"})
    return issues


def check_new_logbook_fields_in_canonical():
    """
    The 3 new logbook fields (failure_consequence, readings_json, production_output)
    must be in the logbook CANONICAL optional list so cross-page flows don't
    incorrectly flag PM-scheduler's logbook insert as having unknown fields.
    """
    issues = []
    logbook_optional = set(CANONICAL["logbook"]["optional"])
    for field in ["failure_consequence", "readings_json", "production_output"]:
        if field not in logbook_optional:
            issues.append({"check": "new_logbook_fields_canonical",
                           "reason": f"New logbook field '{field}' not in CANONICAL optional list — cross-page validator will flag PM-created logbook entries incorrectly"})
    return issues


# ── Layer 3: Cross-page consistency ──────────────────────────────────────────

def check_closed_at_consistency(contents):
    issues = []
    for page, content in contents.items():
        if not content:
            continue
        # strip string literals before checking so 'Closed' inside strings doesn't confuse
        clean = strip_string_literals(strip_template_literals(content))
        for m in re.finditer(
            r"from\(['\"]logbook['\"]\)\.insert\(({[^}]+})\)", clean, re.DOTALL
        ):
            block = m.group(1)
            if re.search(r"status\s*:\s*['\"]Closed['\"]", block) and \
               not re.search(r"closed_at\s*:", block):
                line = content[:m.start()].count('\n') + 1
                issues.append({"check": "closed_at_consistency",
                               "reason": f"{page}:{line} logbook.insert() sets status='Closed' but missing closed_at"})
    return issues


def check_source_writes_own_criticals(contents):
    """
    The canonical source page for each table should itself include all critical fields
    when inserting. If logbook.html's own logbook inserts miss a critical column,
    the canonical definition is wrong or there's a bug in the source.
    """
    issues = []
    for table, canon in CANONICAL.items():
        source  = canon["source_page"]
        content = contents.get(source, "")
        if not content:
            continue
        fields = extract_payload_fields(content, table, table)
        if not fields:
            continue
        for crit in canon["critical"]:
            if crit not in fields:
                issues.append({"check": "source_writes_criticals",
                               "reason": f"{source} (canonical source for '{table}') does not write critical field '{crit}' — either the CANONICAL is wrong or there is a bug in the source page"})
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    # L1 — flow completeness
    "flow_pm_scheduler_logbook",
    "flow_logbook_pm_completions",
    "flow_logbook_inventory_transactions",
    # L2 — schema health
    "hive_id_critical",
    "new_logbook_fields_canonical",
    # L3 — consistency
    "closed_at_consistency",
    "source_writes_criticals",
]

CHECK_LABELS = {
    # L1
    "flow_pm_scheduler_logbook":             "L1  pm-scheduler->logbook critical fields",
    "flow_logbook_pm_completions":           "L1  logbook->pm_completions critical fields",
    "flow_logbook_inventory_transactions":   "L1  logbook->inventory_transactions critical fields",
    # L2
    "hive_id_critical":                      "L2  hive_id listed as critical in all CANONICAL tables",
    "new_logbook_fields_canonical":          "L2  New logbook fields in CANONICAL optional list",
    # L3
    "closed_at_consistency":                 "L3  closed_at set when status='Closed' in all inserts",
    "source_writes_criticals":               "L3  Canonical source pages write their own critical fields",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nCross-Page Flow Validator (4-layer)"))
    print("=" * 55)

    contents   = {p: read_file(p) for p in PAGES}
    all_issues = []

    # L1 — flow checks
    for flow in FLOWS:
        _, issues = check_flow(flow, contents)
        all_issues += issues

    # L2 — schema health
    all_issues += check_hive_id_critical()
    all_issues += check_new_logbook_fields_in_canonical()

    # L3 — consistency
    all_issues += check_closed_at_consistency(contents)
    all_issues += check_source_writes_own_criticals(contents)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")

    # Also print flow detail for context
    if any(i.get("skip") for i in all_issues):
        print("\n  Flow detail:")
        for flow in FLOWS:
            fields, _ = check_flow(flow, contents)
            if fields:
                print(f"    {flow['id']}: {sorted(fields)}")

    report = {
        "validator":    "cross_page",
        "total_checks": total,
        "passed":       n_pass,
        "skipped":      n_skip,
        "failed":       n_fail,
        "canonical":    {t: {"critical": c["critical"], "optional": c["optional"]}
                         for t, c in CANONICAL.items()},
        "issues":       [i for i in all_issues if not i.get("skip")],
    }
    with open("cross_page_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
