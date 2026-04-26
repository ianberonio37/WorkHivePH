"""
Hive Validator — WorkHive Platform

Static analysis of hive.html covering:
  1. Realtime channel event coverage (INSERT + UPDATE for tables where both matter)
  2. Hive ID scoping — every SELECT on a hive table must include .eq('hive_id', ...)
  3. Approval flow completeness — worker-appr channel handles both 'approved' and 'rejected'
  4. Channel cleanup — every channel started must have a removeChannel() call

Usage:  python validate_hive.py
Output: hive_report.json
"""
import re, json, sys

PAGE = "hive.html"

# ── Expected realtime coverage per table ─────────────────────────────────────
# "required": events that MUST be handled (missing = FAIL)
# "expected": events that SHOULD be handled (missing = WARN)
# "immutable": True means the table is write-once, so UPDATE is not needed
CHANNEL_EXPECTATIONS = {
    "hive-feed": {
        "logbook": {
            "required": ["INSERT", "UPDATE"],
            "expected": ["DELETE"],
            "reason":   "Open/Closed status changes must update stat-open counter in real time",
        },
    },
    "hive-pm": {
        "pm_completions": {
            "required": ["INSERT"],
            "expected": [],
            "immutable": True,
            "reason":   "PM completions are write-once; UPDATE not needed",
        },
    },
    "hive-inventory": {
        "inventory_items": {
            "required": ["UPDATE"],
            "expected": ["INSERT"],
            "reason":   "INSERT miss means newly approved parts do not auto-refresh panel",
        },
    },
    "hive-approval": {
        "assets":          {"required": ["INSERT", "UPDATE"], "expected": []},
        "inventory_items": {"required": ["INSERT", "UPDATE"], "expected": []},
    },
    "worker-appr": {
        "assets":          {"required": ["UPDATE"], "expected": []},
        "inventory_items": {"required": ["UPDATE"], "expected": []},
    },
}

# ── Tables that must always have hive_id in their SELECT queries ──────────────
HIVE_SCOPED_TABLES = [
    "logbook", "assets", "inventory_items", "pm_assets",
    "pm_scope_items", "pm_completions", "hive_members",
]

# ── Approval status values worker notification must handle ────────────────────
APPROVAL_STATUSES = ["approved", "rejected"]


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def extract_channel_events(content):
    """
    Parse every db.channel(...).on('postgres_changes', {event: X, table: Y}, ...) pattern.
    Returns: { channel_name: { table_name: set(events) } }
    """
    channels = {}

    # Find each channel block: db.channel('name') ... .subscribe()
    channel_starts = list(re.finditer(
        r"db\.channel\(['\"]([^'\"]+)['\"]", content  # no closing ) — handles 'name:' + VAR form
    ))

    for i, m in enumerate(channel_starts):
        ch_name_raw = m.group(1)
        # Strip the dynamic part (e.g., 'hive-feed:' + HIVE_ID -> 'hive-feed')
        ch_name = ch_name_raw.split(':')[0].split("'")[0].split('"')[0].split(' +')[0].strip()

        # Get the text until the next channel definition or end of string
        end = channel_starts[i + 1].start() if i + 1 < len(channel_starts) else len(content)
        block = content[m.start():end]

        if ch_name not in channels:
            channels[ch_name] = {}

        # Find all .on('postgres_changes', { event: X, table: Y }) in this block
        on_pats = re.findall(
            r"\.on\(['\"]postgres_changes['\"],\s*\{[^}]*event\s*:\s*['\"](\w+)['\"][^}]*table\s*:\s*['\"](\w+)['\"]",
            block,
            re.DOTALL,
        )
        for event, table in on_pats:
            if table not in channels[ch_name]:
                channels[ch_name][table] = set()
            channels[ch_name][table].add(event)

        # Also match reversed order: table then event
        on_pats2 = re.findall(
            r"\.on\(['\"]postgres_changes['\"],\s*\{[^}]*table\s*:\s*['\"](\w+)['\"][^}]*event\s*:\s*['\"](\w+)['\"]",
            block,
            re.DOTALL,
        )
        for table, event in on_pats2:
            if table not in channels[ch_name]:
                channels[ch_name][table] = set()
            channels[ch_name][table].add(event)

    return channels


def check_realtime_coverage(content):
    """Check every channel has the required INSERT/UPDATE handlers."""
    channels = extract_channel_events(content)
    issues   = []
    warnings = []
    passed   = []

    for ch_key, table_expectations in CHANNEL_EXPECTATIONS.items():
        # Match channel by prefix (hive-feed matches hive-feed:HIVE_ID)
        actual = {}
        for ch_name, tables in channels.items():
            if ch_name == ch_key or ch_name.startswith(ch_key):
                for t, evts in tables.items():
                    if t not in actual:
                        actual[t] = set()
                    actual[t].update(evts)

        for table, exp in table_expectations.items():
            found     = actual.get(table, set())
            missing_r = [e for e in exp["required"] if e not in found]
            missing_w = [e for e in exp.get("expected", []) if e not in found]

            label = f"{ch_key} -> {table}"
            if missing_r:
                issues.append({
                    "channel": ch_key, "table": table,
                    "missing_required": missing_r,
                    "found_events": sorted(found),
                    "reason": exp.get("reason", ""),
                })
            elif missing_w:
                warnings.append({
                    "channel": ch_key, "table": table,
                    "missing_expected": missing_w,
                    "found_events": sorted(found),
                    "reason": exp.get("reason", ""),
                })
            else:
                passed.append(label)

    return issues, warnings, passed


def check_hive_id_scoping(content):
    """
    Every db.from('table').select() on a hive-scoped table must include hive_id filter.
    Heuristic: find .select() calls on hive tables; check if .eq('hive_id'...) or
    .filter('hive_id'...) appears nearby (within 200 chars).
    """
    issues = []
    for table in HIVE_SCOPED_TABLES:
        pattern = rf"from\(['\"{table}['\"]\)\.select\("
        for m in re.finditer(pattern, content):
            snippet = content[m.start():m.start() + 300]
            has_hive = bool(re.search(
                r"\.eq\(['\"]hive_id['\"]|\.filter\(['\"]hive_id|\.or\(`hive_id",
                snippet
            ))
            has_worker = bool(re.search(r"\.eq\(['\"]worker_name['\"]", snippet))
            if not has_hive and not has_worker:
                line_no = content[:m.start()].count('\n') + 1
                issues.append({
                    "table":   table,
                    "line":    line_no,
                    "snippet": snippet[:80].replace('\n', ' ').strip(),
                    "reason":  "SELECT without hive_id or worker_name filter — may leak cross-hive data",
                })
    return issues


def check_approval_flow(content):
    """
    worker-appr channel UPDATE handlers must notify for both 'approved' and 'rejected'.
    """
    issues = []
    # Find the worker-appr channel block
    m = re.search(r"db\.channel\(['\"]worker-appr", content)
    if not m:
        return [{"reason": "worker-appr channel not found"}]

    end = content.find(".subscribe()", m.start())
    block = content[m.start():end + 12] if end != -1 else content[m.start():m.start() + 2000]

    for status in APPROVAL_STATUSES:
        if f"status === '{status}'" not in block and f'status === "{status}"' not in block:
            issues.append({
                "status": status,
                "reason": f"worker-appr UPDATE handler does not check for '{status}' status — worker will not be notified",
            })
    return issues


def check_channel_cleanup(content):
    """
    Every channel variable that is started must also have a db.removeChannel() call.
    """
    started  = set(re.findall(r'(\w+Channel)\s*=\s*db\.channel\(', content))
    removed  = set(re.findall(r'db\.removeChannel\((\w+Channel)\)', content))
    missing  = started - removed
    return sorted(missing)


# ── Main ──────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("Hive Validator")
print("=" * 70)

content = read_file(PAGE)
if not content:
    print(f"ERROR: {PAGE} not found")
    sys.exit(1)

fail_count = 0
warn_count = 0

# [1] Realtime coverage
print("\n[1] Realtime channel event coverage\n")
rt_issues, rt_warns, rt_passed = check_realtime_coverage(content)

for p in rt_passed:
    print(f"  PASS  {p}")
for w in rt_warns:
    ch, tbl = w["channel"], w["table"]
    print(f"  WARN  {ch} -> {tbl}")
    for e in w["missing_expected"]:
        print(f"        missing expected event: {e}  ({w['reason']})")
    warn_count += 1
for issue in rt_issues:
    ch, tbl = issue["channel"], issue["table"]
    print(f"  FAIL  {ch} -> {tbl}")
    for e in issue["missing_required"]:
        print(f"        MISSING REQUIRED: {e}  ({issue['reason']})")
    fail_count += 1

# [2] Hive ID scoping
print("\n[2] Hive ID scoping on SELECT queries\n")
scope_issues = check_hive_id_scoping(content)
if scope_issues:
    for iss in scope_issues:
        print(f"  WARN  {iss['table']} (line {iss['line']}): {iss['reason']}")
        warn_count += 1
else:
    print("  PASS  All hive-table SELECTs include hive_id or worker_name filter")

# [3] Approval flow
print("\n[3] Approval notification coverage\n")
appr_issues = check_approval_flow(content)
if appr_issues:
    for iss in appr_issues:
        print(f"  FAIL  {iss['reason']}")
        fail_count += 1
else:
    print("  PASS  worker-appr channel handles both 'approved' and 'rejected'")

# [4] Channel cleanup
print("\n[4] Channel cleanup (removeChannel on every started channel)\n")
uncleaned = check_channel_cleanup(content)
if uncleaned:
    for ch in uncleaned:
        print(f"  WARN  {ch}: started but no db.removeChannel({ch}) call found")
        warn_count += 1
else:
    print("  PASS  All channel variables have removeChannel() cleanup")

# Summary
print(f"\n{'=' * 70}")
print(f"Result: {fail_count} FAIL  {warn_count} WARN")

report = {
    "realtime": {
        "issues":   rt_issues,
        "warnings": rt_warns,
        "passed":   rt_passed,
    },
    "scoping_issues":  scope_issues,
    "approval_issues": appr_issues,
    "uncleaned_channels": uncleaned,
    "summary": {"fail": fail_count, "warn": warn_count},
}
with open("hive_report.json", "w") as f:
    json.dump(report, f, indent=2, default=list)
print("Saved hive_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll hive checks PASS (review WARNs for known gaps).")
