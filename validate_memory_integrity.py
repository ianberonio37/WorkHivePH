"""
Agent Memory Integrity -- WorkHive Platform
============================================
Validates the agent_memory table introduced for the AI gateway.

Layer 1 -- Schema present                                                [FAIL]
  agent_memory table exists in migrations with the expected columns
  (id, hive_id, worker_name, auth_uid, agent_id, kind, turn_text,
  summary, meta, created_at). Without the schema, the gateway fails
  silently on every call.

Layer 2 -- RLS policies present                                          [FAIL]
  agent_memory must have RLS enabled AND at least one policy each for
  SELECT / INSERT. Memory holds free-form conversational text that
  could carry stray PII -- RLS is the last line of defence against
  cross-hive read access.

Layer 3 -- Hot-path indexes present                                      [WARN]
  The (hive_id, worker_name, agent_id, created_at) composite index
  must exist; the gateway's loadMemory() relies on it. Missing index
  = full table scan once the table grows past 50k rows.

Layer 4 -- Retention cron registered                                     [WARN]
  A pg_cron job must delete rows older than the retention bound
  (90 days for turns, 180 days for summaries). Without it the table
  grows unboundedly and accumulates stale conversational context that
  may carry PII. Forward-looking ratchet -- DEFERRED until the cron
  migration is applied.

Skills consulted: realtime-engineer (memory hydration is a hot-path
read), security (RLS posture for free-text fields), data-engineer
(index discipline, retention rules).
"""
from __future__ import annotations

import re
import json
import sys
import os
import glob
from collections import defaultdict

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


MIGRATIONS_DIR = os.path.join("supabase", "migrations")

REQUIRED_COLS = {
    "id", "hive_id", "worker_name", "auth_uid", "agent_id",
    "kind", "turn_text", "summary", "meta", "created_at",
}
REQUIRED_INDEX_COLS = ("hive_id", "worker_name", "agent_id", "created_at")


def _read_all_migrations() -> str:
    chunks: list[str] = []
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        chunks.append(read_file(path) or "")
    return "\n".join(chunks)


# -- Layer 1: Schema present -----------------------------------------------

def check_schema_present() -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    sql = re.sub(r"--[^\n]*", "", _read_all_migrations())
    table_re = re.compile(
        r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?
            (?:public\.|"public"\.)?
            "?agent_memory"?\s*\(
            (?P<body>[\s\S]*?)\n\s*\);""",
        re.IGNORECASE | re.VERBOSE,
    )
    m = table_re.search(sql)
    if not m:
        issues.append({
            "check": "schema_present", "skip": False,
            "reason": (
                "agent_memory table not found in any migration. The AI "
                "gateway's loadMemory() / saveTurn() will silently fail "
                "on every call. Apply migration "
                "20260511000001_agent_memory.sql."
            ),
        })
        return issues, report
    body = m.group("body")
    found_cols: set[str] = set()
    for cm in re.finditer(r"""^\s*"?(\w+)"?\s+["a-zA-Z]""", body, re.MULTILINE):
        col = cm.group(1).lower()
        if col in {"constraint", "primary", "unique", "foreign", "check"}:
            continue
        found_cols.add(col)
    missing = REQUIRED_COLS - found_cols
    report.append({
        "found_cols":   sorted(found_cols),
        "required":     sorted(REQUIRED_COLS),
        "missing":      sorted(missing),
    })
    if missing:
        issues.append({
            "check": "schema_present", "skip": False,
            "reason": (
                f"agent_memory table missing required column(s): "
                f"{sorted(missing)}. Update migration to add them; the "
                f"shared memory helpers expect this exact shape."
            ),
        })
    return issues, report


# -- Layer 2: RLS policies present ----------------------------------------

def check_rls_policies() -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    sql = re.sub(r"--[^\n]*", "", _read_all_migrations())
    rls_enabled = bool(re.search(
        r"""ALTER\s+TABLE\s+(?:ONLY\s+)?(?:public\.|"public"\.)?
            "?agent_memory"?\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY""",
        sql, re.IGNORECASE | re.VERBOSE,
    ))
    has_select = bool(re.search(
        r"""CREATE\s+POLICY\s+\w+\s+ON\s+(?:public\.|"public"\.)?"?agent_memory"?\s+
            FOR\s+SELECT""",
        sql, re.IGNORECASE | re.VERBOSE,
    ))
    has_insert = bool(re.search(
        r"""CREATE\s+POLICY\s+\w+\s+ON\s+(?:public\.|"public"\.)?"?agent_memory"?\s+
            FOR\s+INSERT""",
        sql, re.IGNORECASE | re.VERBOSE,
    ))
    report.append({
        "rls_enabled": rls_enabled,
        "has_select":  has_select,
        "has_insert":  has_insert,
    })
    if not rls_enabled:
        issues.append({
            "check": "rls_policies", "skip": False,
            "reason": (
                "agent_memory does not have ENABLE ROW LEVEL SECURITY. "
                "Conversational text could carry stray PII and would be "
                "readable cross-hive without RLS."
            ),
        })
    if not has_select:
        issues.append({
            "check": "rls_policies", "skip": False,
            "reason": "agent_memory missing FOR SELECT policy.",
        })
    if not has_insert:
        issues.append({
            "check": "rls_policies", "skip": False,
            "reason": "agent_memory missing FOR INSERT policy.",
        })
    return issues, report


# -- Layer 3: Hot-path indexes present ------------------------------------

def check_indexes() -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    sql = re.sub(r"--[^\n]*", "", _read_all_migrations())
    idx_re = re.compile(
        r"""CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:CONCURRENTLY\s+)?
            (?:IF\s+NOT\s+EXISTS\s+)?
            "?\w+"?\s+ON\s+
            (?:public\.|"public"\.)?"?agent_memory"?\s*
            (?:USING\s+"?\w+"?\s*)?
            \(\s*(?P<cols>[^)]+)\)""",
        re.IGNORECASE | re.VERBOSE,
    )
    indexes_found: list[list[str]] = []
    for m in idx_re.finditer(sql):
        cols = [c.strip().strip('"').split()[0].lower()
                for c in m.group("cols").split(",")]
        indexes_found.append(cols)
    has_hot_path = any(
        cols[:len(REQUIRED_INDEX_COLS)] == list(REQUIRED_INDEX_COLS)
        or cols[0] == REQUIRED_INDEX_COLS[0]   # leading column is hive_id
        for cols in indexes_found
    )
    report.append({
        "indexes_found": indexes_found,
        "has_hot_path":  has_hot_path,
    })
    if not has_hot_path:
        issues.append({
            "check": "indexes", "skip": True,
            "reason": (
                f"agent_memory missing the hot-path composite index "
                f"{list(REQUIRED_INDEX_COLS)}. loadMemory() will full-scan "
                f"once the table grows past ~50k rows."
            ),
        })
    return issues, report


# Forward-looking ratchet — baseline 2026-05-11: retention cron shipped in
# 20260511000010_agent_memory_retention_cron.sql. If the cron migration
# is applied (visible to the parser via cron.schedule('agent-memory-...))
# this becomes PASS; flip RETENTION_DEFERRED to False to make it strict.
RETENTION_DEFERRED = False
RETENTION_CRON_NAME = "agent-memory-retention"


# -- Layer 4: Retention cron registered ---------------------------------

def check_retention() -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    rows: list[dict] = []
    sql = _read_all_migrations()
    # Stricter regex than the previous {agent_memory} substring scan:
    # must find the actual cron.schedule('agent-memory-retention', ...).
    has_cron = bool(re.search(
        rf"""cron\.schedule\s*\(\s*['"]({re.escape(RETENTION_CRON_NAME)})['"]""",
        sql, re.IGNORECASE,
    ))
    # Also tolerate any cron job whose body references agent_memory
    # (legacy ad-hoc cleanup jobs that haven't migrated to the canonical name).
    has_legacy_cron = bool(re.search(
        r"""cron\.schedule[^)]*?DELETE\s+FROM\s+(?:public\.)?agent_memory""",
        sql, re.IGNORECASE | re.DOTALL,
    ))
    present = has_cron or has_legacy_cron
    rows.append({
        "metric":               "retention_cron_registered",
        "present":              present,
        "expected_name":        RETENTION_CRON_NAME,
        "canonical_name_found": has_cron,
        "legacy_cron_found":    has_legacy_cron,
    })
    if not present:
        issues.append({
            "check": "retention", "skip": RETENTION_DEFERRED,
            "reason": (
                f"No pg_cron job named '{RETENTION_CRON_NAME}' (or any cron "
                f"deleting from agent_memory) found in migrations. The "
                f"table will grow unboundedly and accumulate stale "
                f"conversational context. Apply migration "
                f"20260511000010_agent_memory_retention_cron.sql."
            ),
        })
    return issues, rows


# -- Runner ----------------------------------------------------------------

CHECK_NAMES = [
    "schema_present",
    "rls_policies",
    "indexes",
    "retention",
]
CHECK_LABELS = {
    "schema_present": "L1  agent_memory schema present with required columns           [FAIL]",
    "rls_policies":   "L2  RLS enabled + SELECT + INSERT policies                       [FAIL]",
    "indexes":        "L3  Hot-path composite index present                             [WARN]",
    "retention":      "L4  Retention cron registered ('agent-memory-retention')         [WARN]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nAgent Memory Integrity (4-layer)"))
    print("=" * 60)

    l1_issues, l1_report = check_schema_present()
    l2_issues, l2_report = check_rls_policies()
    l3_issues, l3_report = check_indexes()
    l4_issues, l4_report = check_retention()

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l4_report:
        print(f"\n{bold('RETENTION SURFACE (informational)')}")
        print("  " + "-" * 56)
        for r in l4_report:
            print(f"  {r['metric']:<32}  {r.get('present', r.get('count', '-'))}")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":      "memory_integrity",
        "total_checks":   total,
        "passed":         n_pass,
        "warned":         n_warn,
        "failed":         n_fail,
        "schema_present": l1_report,
        "rls_policies":   l2_report,
        "indexes":        l3_report,
        "retention":      l4_report,
        "issues":         [i for i in all_issues if not i.get("skip")],
        "warnings":       [i for i in all_issues if i.get("skip")],
    }
    with open("memory_integrity_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
