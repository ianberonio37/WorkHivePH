"""Seed projects — one of each project_type per hive, with scope items,
progress logs, links to assets, and a few blockers so AI features have
realistic input to chew on."""
import random
import uuid
from datetime import datetime, timezone, timedelta

from .utils import to_iso


PROJECT_FLAVOURS = [
    {
        "type": "shutdown", "code_prefix": "SHD",
        "name": "Centrifugal Pump Annual Overhaul",
        "duration_days": 5,
        "items": [
            ("Issue PTW + LOTO isolation; verify zero energy", 2, "pre"),
            ("Decouple driver, drain casing, tag flanges", 4, "execute"),
            ("Disassemble pump; NDT/visual inspection", 8, "execute"),
            ("Replace mechanical seal + bearings", 6, "execute"),
            ("Reassemble; shaft alignment to <0.05 mm", 8, "execute"),
            ("Vibration baseline + run-in test", 4, "commission"),
            ("Update equipment history card", 1, "close"),
        ],
        "lessons": "What went well: Pre-staged parts saved a half-day vs prior overhaul.\nWhat to fix: Alignment took 2x estimated — review crew technique on cold alignment.\nWatch next time: Bearing housing was scored — order spare housing in advance.",
        "blocker_examples": [
            "Waiting on replacement seal — vendor says 2 more days",
            "Crane scheduling conflict with adjacent shutdown",
        ],
    },
    {
        "type": "capex", "code_prefix": "CAP",
        "name": "Compressor Replacement (FEL Stage Gates)",
        "duration_days": 90, "budget_php": 1850000,
        "items": [
            ("FEL-1 Concept Study (AACE Class 5)", 40, "fel1"),
            ("Stage Gate 1 — go/hold/kill", 4, "gate"),
            ("FEL-2 Feasibility Study (Class 4)", 80, "fel2"),
            ("Stage Gate 2 — approve to FEED", 4, "gate"),
            ("FEL-3 FEED / Basic Engineering", 120, "fel3"),
            ("Stage Gate 3 — Final Investment Decision", 4, "gate"),
            ("Procurement + civil works", 80, "execute"),
            ("Equipment delivery + install", 40, "execute"),
            ("Commissioning + SAT", 16, "commission"),
            ("Handover + lessons learned", 8, "close"),
        ],
        "lessons": "What went well: FEL gating caught a sizing error at FEL-2 before procurement; saved ~₱200k.\nWhat to fix: Crane lift permit submitted late — pre-submit at FEL-3 next time.",
        "blocker_examples": [
            "Vendor quote pending — held in procurement queue",
            "Site soil test results delayed by typhoon",
        ],
    },
    {
        "type": "contractor", "code_prefix": "CON",
        "name": "Cooling Tower Cleaning Contract",
        "duration_days": 14, "budget_php": 280000,
        "items": [
            ("Issue scope of work + BOM to bidders", 4, "pre"),
            ("Solicit 3 quotes; technical eval", 8, "pre"),
            ("Award PO; mobilise contractor", 4, "pre"),
            ("Pre-job safety briefing + PTW", 2, "pre"),
            ("Daily progress + QA inspection", 16, "execute"),
            ("Punchlist walk-down", 4, "commission"),
            ("Final acceptance certificate", 2, "close"),
        ],
        "lessons": "What went well: Contractor finished 1 day early; punchlist short.\nWatch next time: Insist on pre-job demo of chemical mixing — caught two errors during execution.",
        "blocker_examples": [
            "Contractor missing valid PEZA gate pass — held at security 4h",
        ],
    },
    {
        "type": "workorder", "code_prefix": "WO",
        "name": "Recurring Compressor Breakdown Bundle",
        "duration_days": 3,
        "items": [
            ("Confirm root cause from logbook", 1, "pre"),
            ("Verify parts + check inventory", 1, "pre"),
            ("Schedule + assign technicians", 1, "pre"),
            ("Execute repairs (link logbook entries)", 4, "execute"),
            ("Test + verify fix", 1, "commission"),
            ("Lessons learned entry", 1, "close"),
        ],
        "lessons": "Pattern detected: 4 of 5 breakdowns had the same root cause (dirty intake filter). Recommend monthly filter PM rather than quarterly.",
        "blocker_examples": [],
    },
]


def seed_projects(client, log, ctx: dict) -> dict:
    hives = ctx["hives"]
    workers = ctx["workers"]
    assets = ctx.get("assets", []) or []
    today = datetime.now(timezone.utc)

    log(f"Seeding {len(PROJECT_FLAVOURS)} projects per hive across {len(hives)} hive(s)...")

    project_rows = []
    item_rows = []
    link_rows = []
    log_rows = []

    for hive in hives:
        hive_workers = [w for w in workers if w["hive_id"] == hive["id"]]
        if not hive_workers:
            continue
        supervisors = [w for w in hive_workers if w["role"] == "supervisor"]
        owner = supervisors[0]["worker_name"] if supervisors else hive_workers[0]["worker_name"]
        hive_assets = [a for a in assets if a.get("hive_id") == hive["id"]]

        for idx, flavour in enumerate(PROJECT_FLAVOURS):
            project_id = str(uuid.uuid4())
            start = today - timedelta(days=int(flavour["duration_days"] * 0.6))
            end   = start + timedelta(days=flavour["duration_days"])
            code  = f"{flavour['code_prefix']}-{today.year}-{(idx + 1):03d}"
            project_rows.append({
                "id": project_id,
                "hive_id": hive["id"],
                "worker_name": owner,
                "auth_uid": next((w.get("auth_uid") for w in hive_workers if w["worker_name"] == owner), None),
                "project_code": code,
                "name": flavour["name"],
                "project_type": flavour["type"],
                "status": "active",
                "priority": random.choice(["medium", "high"]),
                "owner_name": owner,
                "description": f"Seeded project for AI testing in WorkHive Tester. Type: {flavour['type']}. Standards: PMBOK 7th, AACE 17R-97 / IDCON 6-Phase as applicable.",
                "start_date": start.date().isoformat(),
                "end_date":   end.date().isoformat(),
                "budget_php": flavour.get("budget_php"),
                "meta": {"lessons_learned": flavour["lessons"]} if flavour.get("lessons") else {},
                "created_at": to_iso(start),
                "updated_at": to_iso(today),
            })

            # Scope items — sequential predecessors, dates distributed by hours
            total_h = sum(h for _, h, _ in flavour["items"]) or 1
            cum_h = 0
            prev_id = None
            ids = [str(uuid.uuid4()) for _ in flavour["items"]]
            for i_idx, (title, est_h, freq_phase) in enumerate(flavour["items"]):
                # Roll status by position: earliest items more likely done
                pos = i_idx / max(1, len(flavour["items"]) - 1)
                if pos < 0.4:
                    status, pct = "done", 100
                elif pos < 0.6:
                    status, pct = random.choice([("in_progress", 50), ("done", 100), ("blocked", 25)])
                else:
                    status, pct = "pending", 0
                # Date span proportional to hours
                day_start = start + timedelta(days=int(cum_h / total_h * flavour["duration_days"]))
                day_end   = start + timedelta(days=int((cum_h + est_h) / total_h * flavour["duration_days"]))
                cum_h += est_h
                item_rows.append({
                    "id": ids[i_idx],
                    "project_id": project_id,
                    "hive_id": hive["id"],
                    "wbs_code": f"{i_idx + 1}.0",
                    "title": title,
                    "owner_name": random.choice(hive_workers)["worker_name"] if hive_workers else owner,
                    "status": status,
                    "pct_complete": pct,
                    "planned_start": day_start.date().isoformat(),
                    "planned_end":   day_end.date().isoformat(),
                    "actual_start":  day_start.date().isoformat() if status != "pending" else None,
                    "actual_end":    day_end.date().isoformat()   if status == "done" else None,
                    "predecessors": [prev_id] if prev_id else [],
                    "estimated_hours": est_h,
                    "actual_hours":    est_h * (1.1 if status == "done" else 0.5 if status == "in_progress" else 0),
                    "notes": f"phase: {freq_phase}",
                    "sort_order": i_idx,
                    "created_at": to_iso(start),
                    "updated_at": to_iso(today),
                })
                prev_id = ids[i_idx]

            # Link to a sample asset
            if hive_assets:
                asset = random.choice(hive_assets)
                link_rows.append({
                    "id": str(uuid.uuid4()),
                    "project_id": project_id,
                    "hive_id": hive["id"],
                    "link_type": "asset",
                    "link_id": asset["id"],
                    "label": asset.get("name") or asset.get("asset_id") or "linked asset",
                    "created_at": to_iso(start),
                })

            # Daily progress logs — 3-6 per project, with one blocker if defined
            n_logs = random.randint(3, 6)
            for li in range(n_logs):
                log_date = (start + timedelta(days=li * (flavour["duration_days"] // max(1, n_logs)))).date()
                if log_date > today.date():
                    log_date = today.date()
                blocker = None
                if flavour.get("blocker_examples") and li < len(flavour["blocker_examples"]):
                    blocker = flavour["blocker_examples"][li]
                log_rows.append({
                    "id": str(uuid.uuid4()),
                    "project_id": project_id,
                    "hive_id": hive["id"],
                    "log_date": log_date.isoformat(),
                    "reported_by": random.choice(hive_workers)["worker_name"] if hive_workers else owner,
                    "pct_complete": min(100, int(li * 100 / max(1, n_logs - 1))),
                    "hours_worked": round(random.uniform(4, 9), 1),
                    "notes": random.choice([
                        "Crew on-site, isolation complete, work ongoing.",
                        "Inspection done, parts staged for tomorrow.",
                        "Re-assembly proceeding to plan.",
                        "Completed today's milestone, on track.",
                    ]),
                    "blockers": blocker,
                    "created_at": to_iso(start + timedelta(days=li)),
                })

    if project_rows:
        client.table("projects").insert(project_rows).execute()
        log(f"  inserted {len(project_rows)} project(s)")
    if item_rows:
        client.table("project_items").insert(item_rows).execute()
        log(f"  inserted {len(item_rows)} project_items")
    if link_rows:
        client.table("project_links").insert(link_rows).execute()
        log(f"  inserted {len(link_rows)} project_links")
    if log_rows:
        client.table("project_progress_logs").insert(log_rows).execute()
        log(f"  inserted {len(log_rows)} project_progress_logs")

    return {
        "projects": project_rows,
        "project_items": item_rows,
        "project_links": link_rows,
        "project_progress_logs": log_rows,
    }
