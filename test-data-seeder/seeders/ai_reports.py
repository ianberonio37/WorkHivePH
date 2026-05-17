"""Seed sample ai_reports rows so test_cron_jobs.py validates cleanly.

The platform's pg_cron jobs (scheduled-agents edge fn) write to ai_reports
per (hive_id, report_type). Locally we don't run pg_cron, so this seeder
writes plausible sample reports for each (hive, type) combination that the
cron-job validator (tools/test_cron_jobs.py) queries.

Report types covered:
  - pm_overdue          (daily)
  - failure_digest      (weekly)
  - shift_handover      (3x daily — morning/afternoon/night, same row)
  - predictive          (weekly)
"""

import datetime
import uuid


REPORT_TEMPLATES = {
    "pm_overdue": {
        "summary": "3 overdue PMs and 5 due-this-week. 1 critical asset slipping.",
        "report_json": lambda hive_id: {
            "overdue_count": 3,
            "critical_pm": [
                {
                    "asset_name": "Compressor AC-77",
                    "scope_item": "Visual + amp draw check",
                    "days_overdue": 12,
                    "severity": "critical",
                },
            ],
            "hive_id": str(hive_id),
            "due_this_week": 5,
            "generated_window": "last_24h",
        },
    },
    "failure_digest": {
        "summary": "Top failure cause this week: filter clog (3 incidents).",
        "report_json": lambda hive_id: {
            "failure_summary": "3 corrective events, 1 repeat asset.",
            "top_failures": [
                {"asset": "Compressor AC-77", "count": 2, "root_cause": "filter clogged"},
                {"asset": "Mill MILL-001", "count": 1, "root_cause": "bearing wear"},
            ],
            "trend": "flat (compared to prior week)",
            "hive_id": str(hive_id),
            "generated_window": "last_7d",
        },
    },
    "shift_handover": {
        "summary": "Morning shift handover: 2 carry-forwards, 1 critical alert.",
        "report_json": lambda hive_id: {
            "shift_id": f"shift-{datetime.date.today().isoformat()}-morning",
            "critical_items": [
                {"asset": "Compressor AC-77", "issue": "trending hot", "action": "monitor"},
            ],
            "handover_notes": [
                "Night shift left PRV replacement pending parts arrival.",
                "AC-77 amperage trending up 4% over baseline.",
            ],
            "hive_id": str(hive_id),
        },
    },
    "predictive": {
        "summary": "Weekly risk calendar: 2 hot assets, 4 watch.",
        "report_json": lambda hive_id: {
            "risk_score": 0.62,
            "risk_level": "elevated",
            "forecast_items": [
                {"asset": "Compressor AC-77", "predicted_failure_in_days": 18, "confidence": 0.74},
                {"asset": "Pump P-203", "predicted_failure_in_days": 31, "confidence": 0.62},
            ],
            "hive_id": str(hive_id),
            "generated_window": "next_30d_forecast",
        },
    },
}


def run(db, log=print):
    """Seed sample ai_reports for every active hive × every report_type."""
    hives = db.table("hives").select("id, name").execute()
    if not hives.data:
        log("  no hives found — skipping ai_reports seed")
        return {"seeded": 0, "hives_processed": 0}

    seeded = 0
    now = datetime.datetime.now(datetime.timezone.utc)

    for hive in hives.data:
        hive_id = hive["id"]
        for report_type, template in REPORT_TEMPLATES.items():
            # Upsert: keep one row per (hive_id, report_type)
            row = {
                "id": str(uuid.uuid4()),
                "hive_id": hive_id,
                "report_type": report_type,
                "generated_at": now.isoformat(),
                "summary": template["summary"],
                "report_json": template["report_json"](hive_id),
            }
            try:
                # Delete prior row for this (hive, type) so we always have fresh sample
                db.table("ai_reports").delete().eq("hive_id", hive_id).eq("report_type", report_type).execute()
                db.table("ai_reports").insert(row).execute()
                seeded += 1
            except Exception as e:
                log(f"  ai_reports insert {report_type} for {hive['name']}: {e}")

    log(f"  ai_reports seeded: {seeded} rows across {len(hives.data)} hive(s)")
    return {"seeded": seeded, "hives_processed": len(hives.data)}


if __name__ == "__main__":
    # Standalone invocation: connect to local Supabase and seed
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from lib.supabase_client import get_client
    db = get_client()
    result = run(db)
    print(f"\nDone: {result}")
