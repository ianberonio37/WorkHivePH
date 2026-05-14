#!/usr/bin/env python3
"""
Platform Scraper Agent for Voice Companion

Fetches real-time KPI surface data from WorkHive dashboard views:
- Equipment status (running / idle / maintenance / down)
- Risk scores (top 3 assets by risk, failure probability %)
- PM status (due tasks this week, overdue count)
- Inventory alerts (low stock items, out-of-stock count)
- Adoption metrics (active workers this week, hive intent)

Called by voice-handler.js when worker asks for platform-level data.
Queries canonical views (v_*_truth) to ensure consistency with dashboard.
"""

import json
import sys
from datetime import datetime, timedelta
from typing import Optional

def scrape_platform_data(
    supabase_url: str,
    supabase_key: str,
    hive_id: str,
    worker_name: str,
) -> dict:
    """
    Fetch surface-level KPI data for the worker's hive.

    Args:
        supabase_url: Supabase project URL
        supabase_key: Supabase public key
        hive_id: Worker's hive ID
        worker_name: Worker name (for personalization)

    Returns:
        dict with keys: equipment_status, risk_assets, pm_status, inventory_alerts, adoption
    """
    from supabase import create_client

    client = create_client(supabase_url, supabase_key)

    result = {
        "timestamp": datetime.utcnow().isoformat(),
        "hive_id": hive_id,
        "worker": worker_name,
        "equipment_status": {},
        "risk_assets": [],
        "pm_status": {},
        "inventory_alerts": {},
        "adoption": {},
        "errors": []
    }

    try:
        # 1. Equipment Status — count by state (running / idle / maintenance / down)
        eq_resp = client.rpc(
            "get_equipment_status_summary",
            {"hive_id_param": hive_id}
        ).execute()
        if eq_resp.data:
            for row in eq_resp.data:
                result["equipment_status"][row["state"]] = row["count"]
    except Exception as e:
        result["errors"].append(f"Equipment status fetch failed: {str(e)}")

    try:
        # 2. Risk Assets — top 3 by failure risk score
        risk_resp = client.from_("v_risk_truth").select(
            "asset_name, asset_id, risk_score, mtbf_days"
        ).eq("hive_id", hive_id).order(
            "risk_score", desc=True
        ).limit(3).execute()

        if risk_resp.data:
            for row in risk_resp.data:
                result["risk_assets"].append({
                    "asset": row["asset_name"],
                    "asset_id": row["asset_id"],
                    "risk_score": round(float(row["risk_score"] or 0), 1),
                    "mtbf_days": row["mtbf_days"]
                })
    except Exception as e:
        result["errors"].append(f"Risk assets fetch failed: {str(e)}")

    try:
        # 3. PM Status — due this week + overdue count
        today = datetime.utcnow().date()
        week_end = today + timedelta(days=7)

        pm_due = client.from_("v_pm_truth").select("asset_id").eq(
            "hive_id", hive_id
        ).eq("status", "due").gte(
            "next_due_date", today.isoformat()
        ).lt(
            "next_due_date", week_end.isoformat()
        ).execute()

        pm_overdue = client.from_("v_pm_truth").select("asset_id").eq(
            "hive_id", hive_id
        ).eq("status", "overdue").execute()

        result["pm_status"]["due_this_week"] = len(pm_due.data or [])
        result["pm_status"]["overdue"] = len(pm_overdue.data or [])
    except Exception as e:
        result["errors"].append(f"PM status fetch failed: {str(e)}")

    try:
        # 4. Inventory Alerts — low stock + out of stock
        low_stock = client.from_("v_inventory_truth").select("part_name").eq(
            "hive_id", hive_id
        ).eq("stock_level", "low").execute()

        out_of_stock = client.from_("v_inventory_truth").select("part_name").eq(
            "hive_id", hive_id
        ).eq("stock_level", "out").execute()

        result["inventory_alerts"]["low_stock_count"] = len(low_stock.data or [])
        result["inventory_alerts"]["out_of_stock_count"] = len(out_of_stock.data or [])
        if low_stock.data:
            result["inventory_alerts"]["low_stock_items"] = [
                row["part_name"] for row in low_stock.data[:3]
            ]
    except Exception as e:
        result["errors"].append(f"Inventory alerts fetch failed: {str(e)}")

    try:
        # 5. Adoption — active workers this week + hive intent
        adoption = client.from_("v_adoption_truth").select(
            "active_workers_week, adoption_score, hive_intent"
        ).eq("hive_id", hive_id).single().execute()

        if adoption.data:
            result["adoption"]["active_workers"] = adoption.data.get("active_workers_week", 0)
            result["adoption"]["adoption_score"] = round(
                float(adoption.data.get("adoption_score", 0)), 1
            )
            result["adoption"]["intent"] = adoption.data.get("hive_intent", "unknown")
    except Exception as e:
        result["errors"].append(f"Adoption metrics fetch failed: {str(e)}")

    return result


def format_for_voice(data: dict) -> str:
    """
    Convert scraper output to natural voice-friendly summary.

    Returns a brief prose summary suitable for reading aloud.
    """
    lines = []

    # Equipment status
    if data["equipment_status"]:
        status_parts = []
        for state, count in data["equipment_status"].items():
            if count > 0:
                status_parts.append(f"{count} {state}")
        if status_parts:
            lines.append(f"Right now, you have {', '.join(status_parts)}.")

    # Risk assets
    if data["risk_assets"]:
        risk_list = [f"{a['asset']}" for a in data["risk_assets"][:2]]
        lines.append(f"The assets at highest risk are {' and '.join(risk_list)}.")

    # PM status
    if data["pm_status"]:
        due = data["pm_status"].get("due_this_week", 0)
        overdue = data["pm_status"].get("overdue", 0)
        if due or overdue:
            pm_msg = f"You have {due} PMs due this week"
            if overdue:
                pm_msg += f" and {overdue} overdue"
            lines.append(pm_msg + ".")

    # Inventory
    if data["inventory_alerts"]:
        low = data["inventory_alerts"].get("low_stock_count", 0)
        out = data["inventory_alerts"].get("out_of_stock_count", 0)
        if low or out:
            inv_msg = []
            if low:
                inv_msg.append(f"{low} parts low on stock")
            if out:
                inv_msg.append(f"{out} out of stock")
            lines.append(f"Inventory: {', '.join(inv_msg)}.")

    # Adoption
    if data["adoption"]:
        workers = data["adoption"].get("active_workers", 0)
        if workers:
            lines.append(f"You have {workers} active workers this week.")

    return " ".join(lines) if lines else "No data available right now."


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    hive_id = sys.argv[1] if len(sys.argv) > 1 else "test-hive"
    worker = sys.argv[2] if len(sys.argv) > 2 else "test-worker"

    data = scrape_platform_data(url, key, hive_id, worker)
    print(json.dumps(data, indent=2))
