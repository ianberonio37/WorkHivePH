"""Seed schedule_items (Day Planner tasks).

Each worker gets ~5 tasks for today and yesterday, mix of pending/done so the
DILO/WILO views and completion checks have data to render. Without this the
tester logs WARN: 'no tasks for today in DB'.
"""
import random
from datetime import date, timedelta

from .utils import text_id, batch_insert

CATEGORIES = ["PM", "CM", "Inspection", "Training", "Admin", "Meeting", "Other"]

TASK_TITLES = {
    "PM":         ["Weekly vibration check", "Monthly lube round", "Quarterly alignment", "Filter inspection", "Belt tension check"],
    "CM":         ["Bearing replacement", "Seal leak repair", "Coupling re-fit", "VFD parameter restore", "Sensor recalibration"],
    "Inspection": ["Walk-down inspection", "Thermography sweep", "Vibration trend review", "Daily log review"],
    "Training":   ["Toolbox talk: hot work", "PLC training session", "Vibration analysis review", "Safety refresher"],
    "Admin":      ["Update SOPs", "Spare parts review", "Shift handover prep", "Permit-to-work review"],
    "Meeting":    ["Daily standup", "Outage planning", "Vendor call", "Reliability review"],
    "Other":      ["Site round", "Tool calibration", "Cleanup checklist"],
}

START_TIMES = ["07:00", "08:00", "09:00", "10:30", "13:00", "14:30", "15:00"]


def _task_for(cat: str) -> str:
    return random.choice(TASK_TITLES.get(cat, TASK_TITLES["Other"]))


def seed_dayplanner(client, log, ctx: dict) -> dict:
    workers = ctx["workers"]
    log(f"Seeding schedule_items (Day Planner tasks) for {len(workers)} workers...")

    today = date.today()
    yesterday = today - timedelta(days=1)
    rows = []

    for w in workers:
        # 4 tasks today: 1 done, 1 in progress, 2 pending — guarantees the
        # completion check + filter test see a mix.
        for slot, status in enumerate(["done", "in_progress", "pending", "pending"]):
            cat = random.choice(CATEGORIES)
            start = START_TIMES[slot]
            rows.append({
                "id": text_id("sched"),
                "worker_name": w["worker_name"],
                "auth_uid": w.get("auth_uid"),
                "title": _task_for(cat),
                "date": today.isoformat(),
                "start_time": start,
                "end_time": None,
                "category": cat,
                "notes": "",
                "logbook_ref": None,
                "item_status": status,
            })
        # 2 tasks yesterday, both done
        for slot in range(2):
            cat = random.choice(CATEGORIES)
            rows.append({
                "id": text_id("sched"),
                "worker_name": w["worker_name"],
                "auth_uid": w.get("auth_uid"),
                "title": _task_for(cat),
                "date": yesterday.isoformat(),
                "start_time": START_TIMES[slot],
                "end_time": None,
                "category": cat,
                "notes": "",
                "logbook_ref": None,
                "item_status": "done",
            })

    inserted = batch_insert(client, "schedule_items", rows, chunk=500)
    log(f"  inserted {inserted} schedule_items (today + yesterday)")
    return {"schedule_items_count": inserted}
