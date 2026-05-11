"""
Platform Gateway Audit Completeness -- WorkHive Platform
==========================================================
Phase 2.3 of the roadmap. ISO 27001 / SOC 2 require "every API touch
by user X over time window Y" auditable. The platform-gateway is the
natural choke point. This validator checks that:

  (a) gateway_audit_log table exists with required columns,
  (b) the gateway writes to it after every routed call,
  (c) RLS scopes reads to hive members,
  (d) a retention cron is registered.

Layer 1 -- gateway_audit_log schema present                              [FAIL]
  Migration declares the table with the columns the gateway writes.

Layer 2 -- platform-gateway writes audit rows                            [WARN]
  The gateway source must contain at least one
  .from('gateway_audit_log').insert call. Forward-looking ratchet.

Layer 3 -- RLS posture: read scoped to hive, insert via service role    [WARN]
  Compliance-meaningful audit table must have RLS so cross-hive reads
  are impossible; inserts must be locked to service role only.

Layer 4 -- Retention cron registered                                     [WARN]
  pg_cron job that prunes rows past the retention window (365 days
  by default; configurable).

Skills consulted: enterprise-compliance (audit log retention windows),
security (RLS posture for compliance tables), data-engineer (cron-based
retention).
"""
from __future__ import annotations

import re
import json
import sys
import os
import glob

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


MIGRATIONS_DIR    = os.path.join("supabase", "migrations")
PLATFORM_GATEWAY  = os.path.join("supabase", "functions", "platform-gateway", "index.ts")

REQUIRED_COLS = {
    "id", "hive_id", "worker_name", "auth_uid", "route",
    "method", "status_code", "latency_ms", "created_at",
}
RETENTION_CRON = "gateway-audit-retention"

# Forward-looking ratchet
AUDIT_DEFERRED = False  # 2026-05-11: audit_log + gateway write site shipped together


def _all_migrations_sql() -> str:
    chunks = []
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        chunks.append(read_file(path) or "")
    return "\n".join(chunks)


# -- Layer 1: Schema present --------------------------------------------

def check_schema():
    issues, report = [], []
    sql = re.sub(r"--[^\n]*", "", _all_migrations_sql())
    m = re.search(
        r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?
            (?:public\.|"public"\.)?"?gateway_audit_log"?\s*\(
            (?P<body>[\s\S]*?)\n\s*\);""",
        sql, re.IGNORECASE | re.VERBOSE,
    )
    if not m:
        issues.append({
            "check": "schema", "skip": False,
            "reason": "gateway_audit_log table not declared in any migration.",
        })
        return issues, [{"present": False}]
    body = m.group("body")
    cols: set[str] = set()
    for cm in re.finditer(r"""^\s*"?(\w+)"?\s+[a-zA-Z]""", body, re.MULTILINE):
        c = cm.group(1).lower()
        if c not in {"constraint", "primary", "unique", "foreign", "check"}:
            cols.add(c)
    missing = REQUIRED_COLS - cols
    report.append({"present": True, "cols": sorted(cols), "missing": sorted(missing)})
    if missing:
        issues.append({
            "check": "schema", "skip": False,
            "reason": f"gateway_audit_log missing required column(s): {sorted(missing)}",
        })
    return issues, report


# -- Layer 2: Gateway writes to audit log -----------------------------

def check_gateway_writes():
    issues, report = [], []
    src = read_file(PLATFORM_GATEWAY) or ""
    if not src:
        issues.append({
            "check": "gateway_writes", "skip": AUDIT_DEFERRED,
            "reason": "platform-gateway/index.ts missing -- cannot verify audit writes",
        })
        return issues, [{"gateway_present": False}]
    has_write = bool(re.search(
        r"""\.from\(\s*['"]gateway_audit_log['"]\s*\)\s*\.insert""",
        src,
    ))
    report.append({"gateway_present": True, "writes_audit": has_write})
    if not has_write:
        issues.append({
            "check": "gateway_writes", "skip": AUDIT_DEFERRED,
            "reason": (
                "platform-gateway does not call "
                ".from('gateway_audit_log').insert. Audit trail is empty "
                "even when the gateway runs."
            ),
        })
    return issues, report


# -- Layer 3: RLS posture --------------------------------------------

def check_rls():
    issues, report = [], []
    sql = re.sub(r"--[^\n]*", "", _all_migrations_sql())
    rls_enabled = bool(re.search(
        r"""ALTER\s+TABLE\s+(?:ONLY\s+)?(?:public\.|"public"\.)?
            "?gateway_audit_log"?\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY""",
        sql, re.IGNORECASE | re.VERBOSE,
    ))
    # Insert policy must be USING (false) / WITH CHECK (false) (service-role-only).
    insert_locked = bool(re.search(
        r"""CREATE\s+POLICY\s+\w+\s+ON\s+(?:public\.|"public"\.)?"?gateway_audit_log"?\s+
            FOR\s+INSERT\s+WITH\s+CHECK\s*\(\s*false\s*\)""",
        sql, re.IGNORECASE | re.VERBOSE,
    ))
    select_present = bool(re.search(
        r"""CREATE\s+POLICY\s+\w+\s+ON\s+(?:public\.|"public"\.)?"?gateway_audit_log"?\s+
            FOR\s+SELECT""",
        sql, re.IGNORECASE | re.VERBOSE,
    ))
    report.append({
        "rls_enabled":    rls_enabled,
        "insert_locked":  insert_locked,
        "select_policy":  select_present,
    })
    if not rls_enabled:
        issues.append({
            "check": "rls", "skip": False,
            "reason": "gateway_audit_log missing ENABLE ROW LEVEL SECURITY",
        })
    if not insert_locked:
        issues.append({
            "check": "rls", "skip": True,
            "reason": (
                "gateway_audit_log INSERT policy not locked to service "
                "role (FOR INSERT WITH CHECK (false))"
            ),
        })
    if not select_present:
        issues.append({
            "check": "rls", "skip": True,
            "reason": "gateway_audit_log has no FOR SELECT policy",
        })
    return issues, report


# -- Layer 4: Retention cron -----------------------------------------

def check_retention():
    issues, report = [], []
    sql = _all_migrations_sql()
    has_cron = bool(re.search(
        rf"""cron\.schedule\s*\(\s*['"]({re.escape(RETENTION_CRON)})['"]""",
        sql, re.IGNORECASE,
    ))
    report.append({
        "metric":  "audit_retention_cron",
        "present": has_cron,
        "name":    RETENTION_CRON,
    })
    if not has_cron:
        issues.append({
            "check": "retention", "skip": True,
            "reason": (
                f"No pg_cron job named '{RETENTION_CRON}' found. Audit log "
                f"grows unboundedly without retention enforcement."
            ),
        })
    return issues, report


# -- Runner ---------------------------------------------------------------

CHECK_NAMES = ["schema", "gateway_writes", "rls", "retention"]
CHECK_LABELS = {
    "schema":         "L1  gateway_audit_log schema present with required columns    [FAIL]",
    "gateway_writes": "L2  platform-gateway writes audit rows                        [WARN]",
    "rls":            "L3  RLS posture: locked-down insert, hive-scoped reads         [WARN]",
    "retention":      "L4  Retention cron 'gateway-audit-retention' registered       [WARN]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nPlatform Gateway Audit Completeness (4-layer)"))
    print("=" * 60)

    l1_issues, l1_report = check_schema()
    l2_issues, l2_report = check_gateway_writes()
    l3_issues, l3_report = check_rls()
    l4_issues, l4_report = check_retention()

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":      "gateway_audit",
        "total_checks":   total,
        "passed":         n_pass,
        "warned":         n_warn,
        "failed":         n_fail,
        "schema":         l1_report,
        "gateway_writes": l2_report,
        "rls":            l3_report,
        "retention":      l4_report,
    }
    try:
        with open("gateway_audit_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    except Exception:
        pass

    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()
