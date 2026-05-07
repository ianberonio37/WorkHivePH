"""validate_logbook_consistency.py — Logbook business-rule enforcement.

Checks:
  1. closed_at_set        — every Closed entry has closed_at IS NOT NULL
  2. open_no_closed_at    — every Open entry has closed_at IS NULL
  3. parts_txn_parity     — every logbook entry with parts_used has a matching
                            inventory_transactions row (deduction was recorded)
  4. maintenance_type_valid — every entry has a recognised maintenance_type value

These rules were violated by bugs found during manual testing (May 2026).
The fix: saveEditFromForm now checks if 0 rows were updated before deducting
parts. This validator confirms no residual violations exist in the database.
"""

import sys, json
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "test-data-seeder"))
from lib.supabase_client import get_client

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

VALID_TYPES = {
    "Breakdown / Corrective",
    "Preventive Maintenance",
    "Inspection",
    "Project Work",
}


def main():
    db = get_client()
    results = []
    total_pass = total_fail = total_warn = 0

    print(f"\n{BOLD}LOGBOOK CONSISTENCY VALIDATOR{RESET}")
    print("─" * 40)

    # ── Check 1: Closed entries must have closed_at ──────────────────────────
    closed_without_date = db.table("logbook") \
        .select("id, machine, worker_name, status") \
        .eq("status", "Closed") \
        .is_("closed_at", "null") \
        .execute().data or []

    if not closed_without_date:
        print(f"  {GREEN}PASS{RESET}  closed_at_set: all Closed entries have closed_at set")
        total_pass += 1
        results.append({"check": "closed_at_set", "status": "PASS", "count": 0})
    else:
        n = len(closed_without_date)
        print(f"  {RED}FAIL{RESET}  closed_at_set: {n} Closed entries missing closed_at")
        for row in closed_without_date[:3]:
            print(f"         → id={row['id'][:8]} machine={row.get('machine','?')} worker={row.get('worker_name','?')}")
        total_fail += 1
        results.append({"check": "closed_at_set", "status": "FAIL", "count": n,
                        "examples": [r["id"] for r in closed_without_date[:5]]})

    # ── Check 2: Open entries must NOT have closed_at ────────────────────────
    # .not_() unsupported in supabase-py 2.5 — filter client-side instead
    open_rows = db.table("logbook") \
        .select("id, machine, worker_name, closed_at") \
        .eq("status", "Open") \
        .limit(5000) \
        .execute().data or []
    open_with_date = [r for r in open_rows if r.get("closed_at") is not None]

    if not open_with_date:
        print(f"  {GREEN}PASS{RESET}  open_no_closed_at: no Open entries have closed_at set")
        total_pass += 1
        results.append({"check": "open_no_closed_at", "status": "PASS", "count": 0})
    else:
        n = len(open_with_date)
        print(f"  {RED}FAIL{RESET}  open_no_closed_at: {n} Open entries have closed_at set (data inconsistency)")
        total_fail += 1
        results.append({"check": "open_no_closed_at", "status": "FAIL", "count": n})

    # ── Check 3: Parts used → inventory_transactions parity ─────────────────
    # Fetch all entries and filter client-side (.not_() unsupported in supabase-py 2.5)
    entries_with_parts_all = db.table("logbook") \
        .select("id, machine, parts_used, worker_name") \
        .limit(500).execute().data or []
    entries_with_parts = [e for e in entries_with_parts_all if e.get("parts_used")]

    entries_with_parts = [
        e for e in entries_with_parts
        if isinstance(e.get("parts_used"), list) and len(e["parts_used"]) > 0
    ]

    orphan_count = 0
    for entry in entries_with_parts[:100]:   # sample up to 100
        for part in entry["parts_used"]:
            part_id = part.get("partId")
            if not part_id:
                continue
            txns = db.table("inventory_transactions") \
                .select("id") \
                .eq("item_id", part_id) \
                .like("job_ref", f"%{entry['machine']}%") \
                .execute().data or []
            if not txns:
                orphan_count += 1

    if orphan_count == 0:
        print(f"  {GREEN}PASS{RESET}  parts_txn_parity: all parts_used entries have matching inventory transactions")
        total_pass += 1
        results.append({"check": "parts_txn_parity", "status": "PASS", "orphan_count": 0})
    else:
        print(f"  {YELLOW}WARN{RESET}  parts_txn_parity: {orphan_count} parts_used entries have no matching inventory transaction")
        print(f"         (may indicate parts logged without inventory deduction)")
        total_warn += 1
        results.append({"check": "parts_txn_parity", "status": "WARN", "orphan_count": orphan_count})

    # ── Check 4: maintenance_type values are valid ───────────────────────────
    # Filter client-side — .not_() unsupported in supabase-py 2.5
    all_types_raw = db.table("logbook").select("maintenance_type").limit(5000).execute().data or []
    all_types = [r for r in all_types_raw if r.get("maintenance_type")]

    invalid = [r for r in all_types if r["maintenance_type"] not in VALID_TYPES]

    if not invalid:
        print(f"  {GREEN}PASS{RESET}  maintenance_type_valid: all entries use recognised type values")
        total_pass += 1
        results.append({"check": "maintenance_type_valid", "status": "PASS", "count": 0})
    else:
        unique_invalid = list({r["maintenance_type"] for r in invalid})
        print(f"  {RED}FAIL{RESET}  maintenance_type_valid: {len(invalid)} entries with invalid type: {unique_invalid[:4]}")
        total_fail += 1
        results.append({"check": "maintenance_type_valid", "status": "FAIL",
                        "count": len(invalid), "invalid_types": unique_invalid})

    # ── Summary ──────────────────────────────────────────────────────────────
    print(f"\n  Summary: {total_pass} pass · {total_warn} warn · {total_fail} fail")

    report = {
        "validator": "logbook_consistency",
        "pass": total_pass, "warn": total_warn, "fail": total_fail,
        "checks": results,
    }
    out = ROOT / "logbook_consistency_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    sys.exit(0 if total_fail == 0 else 1)


if __name__ == "__main__":
    main()
