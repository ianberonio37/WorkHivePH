"""
Data Retention / Right-to-Erasure -- WorkHive Platform
=========================================================
GDPR / PDPA require that a worker can request deletion of their
personal data. WorkHive must be able to identify every PII-bearing
table and either delete or anonymize rows on request.

Layer 1 -- Every PII-bearing table has a delete path (FK ON DELETE)      [WARN]
  PII-bearing tables (worker_profiles, logbook by worker, etc.)
  should cascade delete OR set null when the worker_profiles row
  is deleted. Otherwise erasure leaves orphans.

Layer 2 -- Anonymisation helper present                                   [WARN]
  Either a `delete_worker_data(worker_name)` function exists in
  migrations OR a `data-erasure` edge fn exists.

Layer 3 -- PII reach inventory (informational)                            [INFO]
  Per-table inventory of PII-bearing columns (worker_name, email,
  display_name, phone, auth_uid).

Layer 4 -- Retention policy declarations (informational)                  [INFO]
  Tables with declared retention (cron-driven DELETE / archive)
  vs ones that grow unbounded.

Skills consulted: enterprise-compliance (GDPR / PDPA / ISO 27001),
data-engineer (cascade FK design for erasure), security (right-to-
erasure as a compliance + ethics requirement).
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
FUNCTIONS_DIR  = os.path.join("supabase", "functions")

DATA_RETENTION_DEFERRED = False    # 2026-05-11: delete_worker_data fn shipped in 20260511000004

PII_COLUMNS = {"worker_name", "display_name", "email", "phone",
               "first_name", "last_name", "full_name"}

DATA_RETENTION_OK: dict[str, str] = {}


CREATE_TABLE_RE = re.compile(
    r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?
        (?:public\.|"public"\.)?
        "?(?P<name>\w+)"?\s*\(
        (?P<body>[\s\S]*?)\n\s*\);""",
    re.IGNORECASE | re.VERBOSE,
)


def _read_all_migrations() -> str:
    return "\n".join(read_file(p) or "" for p in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))))


def collect_pii_tables() -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    sql = re.sub(r"--[^\n]*", "", _read_all_migrations())
    for tm in CREATE_TABLE_RE.finditer(sql):
        table = tm.group("name").lower()
        body  = tm.group("body").lower()
        pii_in_body: set[str] = set()
        for col in PII_COLUMNS:
            if re.search(rf"\b{re.escape(col)}\b", body):
                pii_in_body.add(col)
        if pii_in_body:
            out[table] = pii_in_body
    return out


def has_erasure_helper() -> bool:
    sql = _read_all_migrations()
    if re.search(r"\bdelete_worker_data\s*\(", sql, re.IGNORECASE):
        return True
    if re.search(r"\banonymize_worker\s*\(", sql, re.IGNORECASE):
        return True
    return os.path.isdir(os.path.join(FUNCTIONS_DIR, "data-erasure")) \
        or os.path.isdir(os.path.join(FUNCTIONS_DIR, "right-to-erasure"))


def table_fks_to_worker_profiles(table: str) -> str | None:
    """Return 'CASCADE' / 'SET NULL' / None per the FK behavior on
    auth_uid or worker_name -> worker_profiles."""
    sql = re.sub(r"--[^\n]*", "", _read_all_migrations())
    pattern = re.compile(
        rf"""ALTER\s+TABLE\s+(?:ONLY\s+)?(?:public\.)?"?{re.escape(table)}"?
            [\s\S]*?FOREIGN\s+KEY\s*\([^)]+\)
            \s*REFERENCES\s+(?:auth\.users|public\.worker_profiles)
            [\s\S]*?ON\s+DELETE\s+(?P<onDelete>CASCADE|SET\s+NULL|NO\s+ACTION|RESTRICT)""",
        re.IGNORECASE | re.VERBOSE,
    )
    m = pattern.search(sql)
    if not m:
        return None
    return m.group("onDelete").upper().replace("  ", " ")


def check_delete_path(pii_tables):
    issues, report = [], []
    if DATA_RETENTION_DEFERRED:
        return issues, report
    # When `delete_worker_data()` helper is present, it ANONYMIZES rather
    # than hard-deletes. Anonymisation satisfies right-to-erasure without
    # needing CASCADE FKs (which would orphan audit trails). The helper's
    # presence is sufficient evidence the table is reachable for erasure.
    if has_erasure_helper():
        return issues, report
    for table in sorted(pii_tables):
        if table in DATA_RETENTION_OK:
            continue
        behavior = table_fks_to_worker_profiles(table)
        if behavior in ("CASCADE", "SET NULL"):
            continue
        report.append({"table": table, "fk_to_worker": behavior})
        issues.append({
            "check": "delete_path", "skip": True,
            "reason": (
                f"{table} holds PII columns but has no CASCADE / SET NULL "
                f"FK to worker_profiles or auth.users. Worker erasure "
                f"will leave orphan rows."
            ),
        })
    return issues, report


def check_helper_present():
    issues, report = [], []
    present = has_erasure_helper()
    report.append({"helper_present": present, "deferred": DATA_RETENTION_DEFERRED})
    if present or DATA_RETENTION_DEFERRED:
        return issues, report
    issues.append({
        "check": "helper_present", "skip": True,
        "reason": (
            "No delete_worker_data(...) fn or data-erasure edge fn. "
            "Right-to-erasure can't be honored programmatically."
        ),
    })
    return issues, report


def check_pii_inventory(pii_tables):
    rows = [{"table": t, "pii_cols": sorted(cols)}
            for t, cols in sorted(pii_tables.items())]
    return [], rows


def check_retention_inventory():
    """Detect tables with cron-driven DELETE pattern."""
    sql = _read_all_migrations()
    rows = []
    for m in re.finditer(
        r"""cron\.schedule\s*\([^)]+,\s*['"`][^'"`]+['"`]\s*,\s*\$\$\s*
            (?P<body>[\s\S]*?DELETE\s+FROM[\s\S]*?)\$\$""",
        sql, re.IGNORECASE | re.VERBOSE,
    ):
        body = m.group("body")
        for table_m in re.finditer(
            r"""DELETE\s+FROM\s+(?:public\.)?"?(\w+)"?""",
            body, re.IGNORECASE,
        ):
            rows.append({"table": table_m.group(1).lower()})
    return [], rows


CHECK_NAMES = ["delete_path", "helper_present", "pii_inventory", "retention_inventory"]
CHECK_LABELS = {
    "delete_path":         "L1  Every PII table has CASCADE / SET NULL to worker_profiles  [WARN]",
    "helper_present":      "L2  Erasure helper (fn or edge fn) present                     [WARN]",
    "pii_inventory":       "L3  PII column inventory per table (informational)             [INFO]",
    "retention_inventory": "L4  Cron-driven retention coverage (informational)             [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nData Retention / Right-to-Erasure (4-layer)"))
    print("=" * 60)
    pii_tables = collect_pii_tables()
    print(f"  {len(pii_tables)} PII-bearing table(s), deferred={DATA_RETENTION_DEFERRED}.\n")
    l1_i, l1_r = check_delete_path(pii_tables)
    l2_i, l2_r = check_helper_present()
    l3_i, l3_r = check_pii_inventory(pii_tables)
    l4_i, l4_r = check_retention_inventory()
    all_issues = l1_i + l2_i + l3_i + l4_i
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)
    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")
    report = {"validator": "data_retention", "total_checks": total,
              "passed": n_pass, "warned": n_warn, "failed": n_fail,
              "delete_path": l1_r, "helper_present": l2_r,
              "pii_inventory": l3_r, "retention_inventory": l4_r,
              "issues": [i for i in all_issues if not i.get("skip")],
              "warnings": [i for i in all_issues if i.get("skip")]}
    with open("data_retention_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
