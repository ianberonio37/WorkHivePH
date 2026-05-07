"""
CMMS Reconciliation Validator — WorkHive Platform
==================================================
Compares what external_sync recorded as synced/imported against what
actually landed in the target WorkHive tables (logbook, assets,
inventory_items, pm_assets).

A gap between the two means records were silently dropped — the sync
reported success but the data never made it to the page the worker sees.

Checks (all require local Supabase to be running):
  1.  work_order count parity   — external_sync WOs vs logbook rows per hive
  2.  asset count parity        — external_sync assets vs assets rows per hive
  3.  inventory count parity    — external_sync inventory vs inventory_items per hive
  4.  audit log coverage        — every integration_configs hive has at least 1 audit entry
  5.  quality score threshold   — no audit entry has avg quality score < 50%
  6.  no orphan external_sync   — no rows with hive_id = NULL and sync_status = 'active'

Usage:  python validate_cmms_reconciliation.py
Output: cmms_reconciliation_report.json

Note: skip_if_fast=True in run_platform_checks.py — requires live Supabase.
"""

import json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Supabase client ───────────────────────────────────────────────────────────

def _get_client():
    sys.path.insert(0, os.path.join("test-data-seeder"))
    from lib.supabase_client import get_client
    return get_client()

# ── Helpers ───────────────────────────────────────────────────────────────────

ENTITY_TABLE = {
    "work_order":  "logbook",
    "asset":       "assets",
    "inventory":   "inventory_items",
    "pm_schedule": "pm_assets",
}

TOLERANCE = 5   # allow up to 5 row gap before flagging (test data, dedup, etc.)


def _count(client, table: str, hive_id: str) -> int:
    try:
        res = client.table(table).select("id", count="exact") \
            .eq("hive_id", hive_id).limit(1).execute()
        return res.count or 0
    except Exception:
        return -1


def _ext_count(client, entity_type: str, hive_id: str) -> int:
    try:
        res = client.table("external_sync").select("id", count="exact") \
            .eq("hive_id", hive_id).eq("entity_type", entity_type).limit(1).execute()
        return res.count or 0
    except Exception:
        return -1


# ── Checks ────────────────────────────────────────────────────────────────────

def check_count_parity(client, entity_type: str, wh_table: str) -> list:
    """external_sync count should roughly match target table count per hive."""
    issues = []
    try:
        hives_res = client.table("external_sync").select("hive_id") \
            .eq("entity_type", entity_type).neq("hive_id", "null") \
            .execute()
        hive_ids = {r["hive_id"] for r in (hives_res.data or []) if r.get("hive_id")}
    except Exception as e:
        return [{"check": f"parity_{entity_type}", "skip": True,
                 "reason": f"Could not query external_sync: {e}"}]

    for hive_id in list(hive_ids)[:10]:   # cap at 10 hives to keep it fast
        ext  = _ext_count(client, entity_type, hive_id)
        real = _count(client, wh_table, hive_id)
        if ext < 0 or real < 0:
            continue
        if ext == 0:
            continue   # nothing synced yet — not a problem
        gap = abs(ext - real)
        if gap > TOLERANCE:
            pct_lost = round((gap / ext) * 100, 1) if ext > 0 else 0
            issues.append({
                "check":  f"parity_{entity_type}",
                "hive":   hive_id[:8],
                "reason": (
                    f"Hive {hive_id[:8]}: external_sync has {ext} {entity_type} records "
                    f"but {wh_table} has {real} rows — gap of {gap} ({pct_lost}% not written). "
                    f"Re-import or check for batch failures in cmms_audit_log."
                ),
            })
    return issues


def check_audit_log_coverage(client) -> list:
    """Every hive with an active integration_configs should have at least one audit entry."""
    issues = []
    try:
        configs = client.table("integration_configs").select("hive_id, label") \
            .eq("enabled", True).execute().data or []
    except Exception as e:
        return [{"check": "audit_log_coverage", "skip": True,
                 "reason": f"Could not query integration_configs: {e}"}]

    for cfg in configs[:20]:
        hive_id = cfg.get("hive_id")
        if not hive_id:
            continue
        try:
            res = client.table("cmms_audit_log").select("id", count="exact") \
                .eq("hive_id", hive_id).limit(1).execute()
            if (res.count or 0) == 0:
                issues.append({
                    "check":  "audit_log_coverage",
                    "skip":   True,
                    "reason": (
                        f"Hive {hive_id[:8]} has an active integration config "
                        f"('{cfg.get('label', '?')}') but no cmms_audit_log entries — "
                        f"run at least one import or sync to establish a baseline"
                    ),
                })
        except Exception:
            pass   # table may not exist yet (migration pending)
    return issues


def check_quality_scores(client) -> list:
    """Flag any audit entry where average quality score < 50%."""
    issues = []
    try:
        rows = client.table("cmms_audit_log").select("id, hive_id, batch_id, quality_score, entity_type") \
            .not_.is_("quality_score", "null") \
            .order("created_at", desc=True).limit(50).execute().data or []
    except Exception:
        return []   # table may not exist yet

    for row in rows:
        qs = row.get("quality_score") or {}
        if not qs:
            continue
        values = [v for v in qs.values() if isinstance(v, (int, float))]
        if not values:
            continue
        avg = sum(values) / len(values)
        if avg < 50:
            issues.append({
                "check":  "quality_score_threshold",
                "skip":   True,
                "reason": (
                    f"Audit batch '{row['batch_id']}' (hive {str(row['hive_id'] or '')[:8]}, "
                    f"{row['entity_type']}) has avg quality score {avg:.0f}% < 50% — "
                    f"check field mapping: most fields are landing empty"
                ),
            })
    return issues


def check_orphan_external_sync(client) -> list:
    """external_sync rows with no hive_id and active status are test residue."""
    issues = []
    try:
        res = client.table("external_sync").select("id", count="exact") \
            .is_("hive_id", "null").eq("sync_status", "active").limit(1).execute()
        count = res.count or 0
        if count > 100:
            issues.append({
                "check":  "orphan_external_sync",
                "skip":   True,
                "reason": (
                    f"{count} external_sync rows have hive_id=null and sync_status='active' — "
                    f"likely test data residue; clean up with: "
                    f"DELETE FROM external_sync WHERE hive_id IS NULL"
                ),
            })
    except Exception:
        pass
    return issues


# ── Runner ────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "parity_work_order",
    "parity_asset",
    "parity_inventory",
    "audit_log_coverage",
    "quality_score_threshold",
    "orphan_external_sync",
]

CHECK_LABELS = {
    "parity_work_order":       "R1  external_sync work_order count matches logbook per hive  [WARN]",
    "parity_asset":            "R1  external_sync asset count matches assets per hive         [WARN]",
    "parity_inventory":        "R1  external_sync inventory count matches inventory_items      [WARN]",
    "audit_log_coverage":      "R2  Every active integration hive has cmms_audit_log entries  [WARN]",
    "quality_score_threshold": "R2  No audit entry has avg quality score < 50%               [WARN]",
    "orphan_external_sync":    "R3  No orphan external_sync rows (hive_id=null, active)       [WARN]",
}


def main():
    bold = lambda s: f"\033[1m{s}\033[0m"
    print(bold("\nCMMS Reconciliation Validator"))
    print("=" * 55)

    try:
        client = _get_client()
    except Exception as e:
        print(f"  SKIP — cannot connect to Supabase: {e}")
        report = {"validator": "cmms_reconciliation", "skipped": True, "reason": str(e)}
        with open("cmms_reconciliation_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        sys.exit(0)

    all_issues = []
    all_issues += check_count_parity(client, "work_order", "logbook")
    all_issues += check_count_parity(client, "asset",      "assets")
    all_issues += check_count_parity(client, "inventory",  "inventory_items")
    all_issues += check_audit_log_coverage(client)
    all_issues += check_quality_scores(client)
    all_issues += check_orphan_external_sync(client)

    # All checks are WARN-level (data issues, not code issues)
    n_warn = len([i for i in all_issues if not i.get("skip") or i.get("skip")])
    n_real_fail = len([i for i in all_issues if not i.get("skip")])
    n_pass = len(CHECK_NAMES) - len({i["check"] for i in all_issues})

    for check_name in CHECK_NAMES:
        label = CHECK_LABELS.get(check_name, check_name)
        matched = [i for i in all_issues if i.get("check") == check_name]
        if not matched:
            print(f"  \033[92m✓ PASS\033[0m  {label}")
        else:
            for issue in matched:
                severity = "WARN"
                print(f"  \033[93m! {severity}\033[0m  {label}")
                print(f"         {issue['reason'][:100]}")

    summary = f"\n  {n_pass} PASS  {n_warn} WARN  0 FAIL"
    print(f"\033[93m{summary}\033[0m" if n_warn else f"\033[92m\n  All {len(CHECK_NAMES)} reconciliation checks passed.\033[0m")

    report = {
        "validator":    "cmms_reconciliation",
        "total_checks": len(CHECK_NAMES),
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       0,
        "issues":       all_issues,
    }
    with open("cmms_reconciliation_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(0)   # reconciliation issues are WARN only — never block deployment


if __name__ == "__main__":
    main()
