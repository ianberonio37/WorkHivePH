"""
Per-Hive Resource Quota -- WorkHive Platform
==============================================
Beyond rate-limit (calls per hour), track per-hive resource caps:
row counts on high-volume tables, storage usage, cron job count.
Without quotas, one heavy hive can degrade performance for everyone.

Layer 1 -- Quota table present                                          [WARN]
  `hive_quotas` table with per-hive row-count + storage caps.
  Forward-looking ratchet via QUOTA_DEFERRED.

Layer 2 -- High-volume tables have a quota enforcement trigger          [WARN]
  Tables like logbook, inventory_transactions, ai_reports should
  have a BEFORE INSERT trigger that checks against hive_quotas.

Layer 3 -- Per-table row volume estimate (informational)                 [INFO]
  Heuristic: tables likely to grow unbounded.

Layer 4 -- Quota enforcement coverage (informational)                    [INFO]
  Inventory of triggers + their quota check shape.

Skills consulted: data-engineer (quota semantics), architect (when
quotas matter vs premature optimization), enterprise-compliance
(SOC 2 capacity controls).
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


MIGRATIONS_DIR = os.path.join("supabase", "migrations")

QUOTA_DEFERRED = False    # 2026-05-11: hive_quotas table + triggers shipped in 20260511000003

HIGH_VOLUME_TABLES = {
    "logbook",
    "inventory_transactions",
    "pm_completions",
    "ai_reports",
    "automation_log",
    "asset_risk_scores",
    "community_posts",
    "community_replies",
    "achievement_xp_log",
    "agent_memory",
}

QUOTA_OK: dict[str, str] = {
    # v1 (logbook + inventory_transactions) + v2 (pm_completions + ai_reports
    # + community_posts) triggers SHIPPED across 20260511000003 + 20260511000007.
    # The 5 remaining tables (automation_log, asset_risk_scores, community_replies,
    # achievement_xp_log, agent_memory) are append-only event records bounded
    # by cron-driven retention rather than per-hive quotas. Keep listed for
    # validator's awareness; no migration owed.
    "automation_log":       "OK -- cron-driven append; retention cron handles cap",
    "asset_risk_scores":    "OK -- snapshot history; retention cron handles cap",
    "community_replies":    "OK -- enforced via community_posts cap (parent table)",
    "achievement_xp_log":   "OK -- bounded by achievement set size",
    "agent_memory":         "OK -- 90-day retention handles cap (memory layer)",
}


def has_quota_table() -> bool:
    table_re = re.compile(
        r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?
            (?:public\.|"public"\.)?
            "?hive_quotas"?\s*\(""",
        re.IGNORECASE | re.VERBOSE,
    )
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        if table_re.search(read_file(path) or ""):
            return True
    return False


def has_quota_trigger_on(table: str) -> bool:
    """Heuristic: a trigger on `table` that references `hive_quotas`."""
    trig_re = re.compile(
        rf"""CREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER\s+\w+\s+BEFORE\s+INSERT[\s\S]*?
            ON\s+(?:public\.)?"?{re.escape(table)}"?[\s\S]*?
            EXECUTE\s+(?:PROCEDURE|FUNCTION)\s+(?:public\.)?(?P<fn>\w+)""",
        re.IGNORECASE | re.VERBOSE,
    )
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = read_file(path) or ""
        m = trig_re.search(sql)
        if not m:
            continue
        fn_name = m.group("fn")
        # Look for the fn body to confirm it touches hive_quotas
        fn_re = re.compile(
            rf"""CREATE(?:\s+OR\s+REPLACE)?\s+FUNCTION\s+(?:public\.)?"?{re.escape(fn_name)}"?
                [\s\S]*?(?:\$\$[\s\S]*?\$\$|;)""",
            re.IGNORECASE | re.VERBOSE,
        )
        for path2 in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
            sql2 = read_file(path2) or ""
            fnm = fn_re.search(sql2)
            if fnm and "hive_quotas" in fnm.group(0):
                return True
    return False


def check_quota_table():
    issues, report = [], []
    present = has_quota_table()
    report.append({"present": present, "deferred": QUOTA_DEFERRED})
    if present or QUOTA_DEFERRED:
        return issues, report
    issues.append({
        "check": "quota_table", "skip": True,
        "reason": (
            "No `hive_quotas` table in migrations. Per-hive caps cannot "
            "be enforced. Either ship the table or flip QUOTA_DEFERRED."
        ),
    })
    return issues, report


def check_trigger_coverage():
    issues, report = [], []
    if QUOTA_DEFERRED:
        return issues, report
    for table in sorted(HIGH_VOLUME_TABLES):
        if table in QUOTA_OK:
            continue
        if has_quota_trigger_on(table):
            continue
        report.append({"table": table})
        issues.append({
            "check": "trigger_coverage", "skip": True,
            "reason": (
                f"{table} is a high-volume table but has no BEFORE "
                f"INSERT trigger that consults hive_quotas. Add a "
                f"quota enforcement trigger."
            ),
        })
    return issues, report


def check_table_inventory():
    rows = [{"table": t, "covered": has_quota_trigger_on(t)}
            for t in sorted(HIGH_VOLUME_TABLES)]
    return [], rows


def check_quota_adoption_inventory():
    sql = "\n".join(read_file(p) or "" for p in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))))
    n_refs = len(re.findall(r"\bhive_quotas\b", sql))
    return [], [{"hive_quotas_references": n_refs}]


CHECK_NAMES = ["quota_table", "trigger_coverage", "table_inventory", "adoption_inventory"]
CHECK_LABELS = {
    "quota_table":         "L1  hive_quotas table present (or DEFERRED)                     [WARN]",
    "trigger_coverage":    "L2  High-volume tables have quota enforcement triggers          [WARN]",
    "table_inventory":     "L3  Per-table quota coverage (informational)                    [INFO]",
    "adoption_inventory":  "L4  hive_quotas reference count (informational)                 [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nPer-Hive Resource Quota (4-layer)"))
    print("=" * 60)
    print(f"  {len(HIGH_VOLUME_TABLES)} high-volume tables, quota_deferred={QUOTA_DEFERRED}.\n")
    l1_i, l1_r = check_quota_table()
    l2_i, l2_r = check_trigger_coverage()
    l3_i, l3_r = check_table_inventory()
    l4_i, l4_r = check_quota_adoption_inventory()
    all_issues = l1_i + l2_i + l3_i + l4_i
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)
    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")
    report = {"validator": "hive_quota", "total_checks": total,
              "passed": n_pass, "warned": n_warn, "failed": n_fail,
              "quota_table": l1_r, "trigger_coverage": l2_r,
              "table_inventory": l3_r, "adoption_inventory": l4_r,
              "issues": [i for i in all_issues if not i.get("skip")],
              "warnings": [i for i in all_issues if i.get("skip")]}
    with open("hive_quota_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
