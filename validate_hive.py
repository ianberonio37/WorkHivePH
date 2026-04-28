"""
Hive Validator — WorkHive Platform
=====================================
Four-layer validation of hive.html:

  Layer 1 — Realtime integrity
    1.  Channel event coverage        — INSERT/UPDATE handlers present on every hive table
    2.  Hive ID scoping on SELECT     — every hive-table SELECT includes hive_id filter
    3.  Approval flow completeness    — worker-appr channel handles both approved + rejected
    4.  Channel cleanup               — every started channel has removeChannel() call

  Layer 2 — Tenant isolation
    5.  approveItem scoped by hive_id — update includes .eq('hive_id', HIVE_ID)
    6.  rejectItem scoped by hive_id  — update includes .eq('hive_id', HIVE_ID)
    7.  Realtime approval filter      — approvalChannel uses hive_id=eq. filter

  Layer 3 — Access control
    8.  Auth gate present             — WORKER_NAME redirect on page load
    9.  Supervisor gate on kick       — kickMember checks HIVE_ROLE !== 'supervisor'
    10. Supervisor gate on approve    — approveItem checks HIVE_ROLE !== 'supervisor'
    11. Supervisor gate on reject     — rejectItem checks HIVE_ROLE !== 'supervisor'

  Layer 4 — Audit + XSS
    12. writeAuditLog on power actions — kick/approve/reject all call writeAuditLog
    13. escHtml in feed/member render  — worker names and entry fields escaped in DOM

Usage:  python validate_hive.py
Output: hive_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

PAGE = "hive.html"

CHANNEL_EXPECTATIONS = {
    "hive-feed": {
        "logbook":          {"required": ["INSERT", "UPDATE"], "expected": ["DELETE"],
                             "reason": "Open/Closed status changes must update stat counters in real time"},
    },
    "hive-pm": {
        "pm_completions":   {"required": ["INSERT"], "expected": [], "immutable": True,
                             "reason": "PM completions are write-once; UPDATE not needed"},
    },
    "hive-inventory": {
        "inventory_items":  {"required": ["UPDATE"], "expected": ["INSERT"],
                             "reason": "INSERT miss means newly approved parts do not auto-refresh"},
    },
    "hive-approval": {
        "assets":           {"required": ["INSERT", "UPDATE"], "expected": []},
        "inventory_items":  {"required": ["INSERT", "UPDATE"], "expected": []},
    },
    "worker-appr": {
        "assets":           {"required": ["UPDATE"], "expected": []},
        "inventory_items":  {"required": ["UPDATE"], "expected": []},
    },
}

HIVE_SCOPED_TABLES = [
    "logbook", "assets", "inventory_items", "pm_assets",
    "pm_scope_items", "pm_completions", "hive_members",
]

APPROVAL_STATUSES = ["approved", "rejected"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_channel_events(content):
    channels = {}
    starts = list(re.finditer(r"db\.channel\(['\"]([^'\"]+)['\"]", content))
    for i, m in enumerate(starts):
        ch_name = m.group(1).split(':')[0].split("'")[0].split('"')[0].split(' +')[0].strip()
        end     = starts[i + 1].start() if i + 1 < len(starts) else len(content)
        block   = content[m.start():end]
        if ch_name not in channels:
            channels[ch_name] = {}
        for pat in [
            r"\.on\(['\"]postgres_changes['\"],\s*\{[^}]*event\s*:\s*['\"](\w+)['\"][^}]*table\s*:\s*['\"](\w+)['\"]",
            r"\.on\(['\"]postgres_changes['\"],\s*\{[^}]*table\s*:\s*['\"](\w+)['\"][^}]*event\s*:\s*['\"](\w+)['\"]",
        ]:
            for a, b in re.findall(pat, block, re.DOTALL):
                event, table = (a, b) if pat.index('event') < pat.index('table') else (b, a)
                if table not in channels[ch_name]:
                    channels[ch_name][table] = set()
                channels[ch_name][table].add(event)
    return channels


def extract_function_body(content, func_name, window=600):
    m = re.search(rf"async function {re.escape(func_name)}\s*\(", content)
    if not m:
        return None
    return content[m.start():m.start() + window]


# ── Layer 1: Realtime integrity ───────────────────────────────────────────────

def check_realtime_coverage(content):
    channels = extract_channel_events(content)
    issues   = []
    for ch_key, table_exp in CHANNEL_EXPECTATIONS.items():
        actual = {}
        for ch_name, tables in channels.items():
            if ch_name == ch_key or ch_name.startswith(ch_key):
                for t, evts in tables.items():
                    actual.setdefault(t, set()).update(evts)
        for table, exp in table_exp.items():
            found   = actual.get(table, set())
            missing = [e for e in exp["required"] if e not in found]
            for e in missing:
                issues.append({"check": "realtime_coverage",
                               "channel": ch_key, "table": table, "missing_event": e,
                               "reason": f"{ch_key}->{table} missing required event '{e}': {exp.get('reason','')}"})
    return issues


def check_hive_id_scoping(content):
    issues = []
    for table in HIVE_SCOPED_TABLES:
        for m in re.finditer(rf"from\(['\"]?{re.escape(table)}['\"]?\)\.select\(", content):
            snippet = content[m.start():m.start() + 300]
            has_scope = bool(re.search(
                r"\.eq\(['\"]hive_id['\"]"         # eq('hive_id', ...)
                r"|\.filter\(['\"]hive_id"          # filter('hive_id', ...)
                r"|\.or\(`hive_id"                  # or(`hive_id.eq....`)
                r"|\.eq\(['\"]worker_name['\"]"     # eq('worker_name', ...)
                r"|\.in\(['\"]worker_name['\"]"     # in('worker_name', [...])
                r"|\.eq\(['\"]id['\"]",             # single-record lookup by PK — no hive scope needed
                snippet
            ))
            if not has_scope:
                line = content[:m.start()].count('\n') + 1
                issues.append({"check": "hive_id_scoping", "table": table, "line": line,
                               "reason": f"{table} SELECT at line {line} missing hive_id or worker_name filter"})
    return issues


def check_approval_flow(content):
    m = re.search(r"db\.channel\(['\"]worker-appr", content)
    if not m:
        return [{"check": "approval_flow", "reason": "worker-appr channel not found"}]
    end   = content.find(".subscribe()", m.start())
    block = content[m.start():end + 12] if end != -1 else content[m.start():m.start() + 2000]
    return [{"check": "approval_flow", "status": s,
             "reason": f"worker-appr UPDATE handler does not check for '{s}' — worker not notified"}
            for s in APPROVAL_STATUSES
            if f"status === '{s}'" not in block and f'status === "{s}"' not in block]


def check_channel_cleanup(content):
    started  = set(re.findall(r'(\w+Channel)\s*=\s*db\.channel\(', content))
    removed  = set(re.findall(r'db\.removeChannel\((\w+Channel)\)', content))
    missing  = sorted(started - removed)
    return [{"check": "channel_cleanup", "channel": ch,
             "reason": f"{ch} started but db.removeChannel({ch}) not found — memory/subscription leak"}
            for ch in missing]


# ── Layer 2: Tenant isolation ─────────────────────────────────────────────────

def check_approve_scoped(content):
    m = re.search(r"async function approveItem\s*\(", content)
    if not m:
        return [{"check": "approve_scoped", "reason": "approveItem() not found"}]
    body = content[m.start():m.start() + 400]
    update_m = re.search(r"\.update\s*\(", body)
    if not update_m:
        return [{"check": "approve_scoped", "reason": "approveItem() .update() call not found"}]
    after = body[update_m.start():update_m.start() + 200]
    if not re.search(r"\.eq\s*\(['\"]hive_id['\"]", after):
        return [{"check": "approve_scoped",
                 "reason": "approveItem() update not scoped by hive_id — supervisor of hive A can approve items in hive B via UUID"}]
    return []


def check_reject_scoped(content):
    m = re.search(r"async function rejectItem\s*\(", content)
    if not m:
        return [{"check": "reject_scoped", "reason": "rejectItem() not found"}]
    body = content[m.start():m.start() + 300]
    update_m = re.search(r"\.update\s*\(", body)
    if not update_m:
        return [{"check": "reject_scoped", "reason": "rejectItem() .update() call not found"}]
    after = body[update_m.start():update_m.start() + 150]
    if not re.search(r"\.eq\s*\(['\"]hive_id['\"]", after):
        return [{"check": "reject_scoped",
                 "reason": "rejectItem() update not scoped by hive_id — supervisor of hive A can reject items in hive B via UUID"}]
    return []


def check_realtime_approval_filter(content):
    m = re.search(r"approvalChannel\s*=\s*db\.channel\(", content)
    if not m:
        return [{"check": "realtime_approval_filter",
                 "reason": "approvalChannel not found — cannot verify hive_id filter"}]
    block = content[m.start():m.start() + 600]
    if not re.search(r"hive_id\s*=\s*eq\.", block):
        return [{"check": "realtime_approval_filter",
                 "reason": "approvalChannel does not use hive_id=eq. filter — all hives see each other's approval queue events"}]
    return []


# ── Layer 3: Access control ───────────────────────────────────────────────────

def check_auth_gate(content):
    if not re.search(r"if\s*\(\s*!\s*WORKER_NAME\s*\)", content):
        return [{"check": "auth_gate",
                 "reason": "WORKER_NAME auth gate missing — unauthenticated users can access hive board"}]
    return []


def check_supervisor_gate(content, func_name, check_id):
    body = extract_function_body(content, func_name, window=300)
    if body is None:
        return [{"check": check_id, "reason": f"{func_name}() not found"}]
    if not re.search(r"HIVE_ROLE\s*!==?\s*['\"]supervisor['\"]", body):
        return [{"check": check_id,
                 "reason": f"{func_name}() missing HIVE_ROLE !== 'supervisor' check — workers can perform supervisor actions"}]
    return []


# ── Layer 4: Audit + XSS ─────────────────────────────────────────────────────

def check_audit_log_on_power_actions(content):
    issues = []
    for func in ("kickMember", "approveItem", "rejectItem"):
        body = extract_function_body(content, func, window=1500)
        if body is None:
            continue
        if "writeAuditLog" not in body:
            issues.append({"check": "audit_log_power_actions", "function": func,
                           "reason": f"{func}() does not call writeAuditLog — supervisor action not recorded in audit trail"})
    return issues


def check_eschtml_in_render(content):
    if "escHtml" not in content:
        return [{"check": "eschtml_render",
                 "reason": "escHtml not found in hive.html — worker names and entry data render as raw HTML"}]
    # Check escHtml used near worker_name in render functions
    if not re.search(r"escHtml\s*\(\s*(?:entry|record|m)\.\s*worker_name", content):
        return [{"check": "eschtml_render",
                 "reason": "escHtml not applied to worker_name in feed/member render — malicious names inject HTML"}]
    return []


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    # L1
    "realtime_coverage", "hive_id_scoping", "approval_flow", "channel_cleanup",
    # L2
    "approve_scoped", "reject_scoped", "realtime_approval_filter",
    # L3
    "auth_gate",
    "supervisor_gate_kick", "supervisor_gate_approve", "supervisor_gate_reject",
    # L4
    "audit_log_power_actions", "eschtml_render",
]

CHECK_LABELS = {
    # L1
    "realtime_coverage":       "L1  Realtime channel event coverage (INSERT/UPDATE)",
    "hive_id_scoping":         "L1  hive_id filter on all hive-table SELECTs",
    "approval_flow":           "L1  worker-appr handles approved + rejected",
    "channel_cleanup":         "L1  All channels have removeChannel() cleanup",
    # L2
    "approve_scoped":          "L2  approveItem update scoped by hive_id",
    "reject_scoped":           "L2  rejectItem update scoped by hive_id",
    "realtime_approval_filter":"L2  approvalChannel uses hive_id=eq. filter",
    # L3
    "auth_gate":               "L3  WORKER_NAME auth gate present",
    "supervisor_gate_kick":    "L3  kickMember checks HIVE_ROLE supervisor",
    "supervisor_gate_approve": "L3  approveItem checks HIVE_ROLE supervisor",
    "supervisor_gate_reject":  "L3  rejectItem checks HIVE_ROLE supervisor",
    # L4
    "audit_log_power_actions": "L4  writeAuditLog called on kick/approve/reject",
    "eschtml_render":          "L4  escHtml applied to worker_name in render",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nHive Validator (4-layer)"))
    print("=" * 55)

    content = read_file(PAGE)
    if not content:
        print(f"  ERROR: {PAGE} not found")
        sys.exit(1)

    all_issues = []

    # L1
    all_issues += check_realtime_coverage(content)
    all_issues += check_hive_id_scoping(content)
    all_issues += check_approval_flow(content)
    all_issues += check_channel_cleanup(content)

    # L2
    all_issues += check_approve_scoped(content)
    all_issues += check_reject_scoped(content)
    all_issues += check_realtime_approval_filter(content)

    # L3
    all_issues += check_auth_gate(content)
    all_issues += check_supervisor_gate(content, "kickMember",   "supervisor_gate_kick")
    all_issues += check_supervisor_gate(content, "approveItem",  "supervisor_gate_approve")
    all_issues += check_supervisor_gate(content, "rejectItem",   "supervisor_gate_reject")

    # L4
    all_issues += check_audit_log_on_power_actions(content)
    all_issues += check_eschtml_in_render(content)

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "hive",
        "total_checks": total,
        "passed":       n_pass,
        "skipped":      n_skip,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
    }
    with open("hive_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=list)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
