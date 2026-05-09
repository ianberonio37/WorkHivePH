"""Seed one failure_signature_alerts row per hive so the Alert Hub Pattern
filter has data without waiting for the failure-signature-scan edge fn run.

Schema has UNIQUE (hive_id, machine, rule_id) so we pick a different machine
per row (first asset in each hive's list).
"""
import datetime, json
from .utils import batch_insert


def seed_failure_alerts(client, log, ctx: dict) -> dict:
    log("Seeding one demo failure_signature_alert per hive...")
    assets_by_hive = ctx.get("assets_by_hive") or {}
    if not assets_by_hive:
        log("  no assets in ctx — failure alerts skipped")
        return {"failure_alerts_count": 0}

    now = datetime.datetime.utcnow().isoformat() + "Z"
    expires = (datetime.datetime.utcnow() + datetime.timedelta(days=14)).isoformat() + "Z"

    rows = []
    for hive_id, assets in assets_by_hive.items():
        if not assets:
            continue
        machine = assets[0].get("asset_id") or assets[0].get("name") or "Unknown"
        rows.append({
            "hive_id":      hive_id,
            "machine":      machine,
            "category":     assets[0].get("type") or "Mechanical",
            "rule_id":      "repeat_failure",
            "alert_title":  f"{machine}: same fault pattern detected 3 times in 14 days",
            "alert_detail": "Repeat failure signature: bearing seal replacement followed "
                            "by lubrication issue across 3 corrective records in 14 days. "
                            "Recommend root-cause investigation before next PM cycle.",
            "evidence":     json.dumps({
                "occurrences":   3,
                "window_days":   14,
                "root_causes":   ["bearing wear", "contamination", "lubrication failure"],
            }),
            "days_to_failure": 21.0,
            "severity":     "warning",
            "status":       "active",
            "detected_at":  now,
            "expires_at":   expires,
        })

    inserted = batch_insert(client, "failure_signature_alerts", rows, chunk=500)
    log(f"  inserted {inserted} failure_signature_alerts")
    return {"failure_alerts_count": inserted}
