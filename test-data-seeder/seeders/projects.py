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


# X-keystone (PROJECT_MANAGER_DEEP_ARC Phase 3): which source systems each project
# flavour BUNDLES via project_links, so the seeded WORKED state actually demonstrates
# the connectivity fabric instead of an island. (link_type, count) per flavour type.
# Mirrors the schema's design intent (the WO WBS literally says "link logbook entries").
FLAVOUR_BUNDLE = {
    "workorder":  [("logbook", 2), ("inventory_item", 1), ("pm_completion", 1)],  # reactive/breakdown bundle
    "shutdown":   [("pm_completion", 1), ("logbook", 1), ("inventory_item", 2)],  # outage: PM campaign + parts
    "capex":      [("engineering_calc", 1), ("inventory_item", 2)],               # design basis + BOM
    "contractor": [("engineering_calc", 1), ("inventory_item", 2)],               # vendor scope + BOM
}


def _hive_sample(client, table: str, hive_id, cols: list, limit: int, log) -> list:
    """Fetch up to `limit` rows of a source system for one hive (for project_links).
    Fail-soft: a missing table / empty system just yields no links, never a crash."""
    try:
        res = client.table(table).select(",".join(cols)).eq("hive_id", hive_id).limit(limit).execute()
        return res.data or []
    except Exception as e:
        log(f"  warn: could not sample {table} for hive ({e})")
        return []


def _link_label(link_type: str, row: dict) -> str:
    if link_type == "logbook":
        return f"{row.get('machine') or '?'}: {(row.get('problem') or '')[:50]}"
    if link_type == "pm_completion":
        d = (row.get("completed_at") or "")[:10]
        return f"PM {d}".strip()
    if link_type == "inventory_item":
        return row.get("part_name") or row.get("part_number") or "part"
    if link_type == "engineering_calc":
        return f"{row.get('calc_type') or 'calc'}: {row.get('project_name') or ''}".strip().rstrip(":")
    return str(row.get("id"))


_SYS_COLS = {
    "logbook":         ("logbook", ["id", "machine", "problem"]),
    "pm_completion":   ("pm_completions", ["id", "asset_id", "completed_at"]),
    "inventory_item":  ("inventory_items", ["id", "part_name", "part_number"]),
    "engineering_calc":("engineering_calcs", ["id", "calc_type", "project_name"]),
}


def seed_projects(client, log, ctx: dict) -> dict:
    hives = ctx["hives"]
    workers = ctx["workers"]
    assets = ctx.get("assets", []) or []
    today = datetime.now(timezone.utc)

    log(f"Seeding {len(PROJECT_FLAVOURS)} projects per hive across {len(hives)} hive(s)...")

    # Find max existing seq per hive + per code_prefix so re-runs don't collide
    # with codes the user already created via the wizard. Start the seeder
    # numbering one above the highest existing.
    existing_max: dict[tuple, int] = {}
    try:
        existing_res = client.table("projects").select("hive_id, project_code").execute()
        import re as _re
        for row in (existing_res.data or []):
            code = row.get("project_code") or ""
            m = _re.match(r"^([A-Z]+)-\d{4}-(\d+)$", code)
            if m:
                key = (row.get("hive_id"), m.group(1))
                num = int(m.group(2))
                existing_max[key] = max(existing_max.get(key, 0), num)
    except Exception as e:
        log(f"  warn: could not preload existing project codes ({e})")

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
        # X-keystone: sample each source system ONCE per hive so projects can BUNDLE
        # real logbook/PM/inventory/eng-design rows (not just an asset).
        hive_sys = {}
        for _lt, (_tbl, _cols) in _SYS_COLS.items():
            hive_sys[_lt] = _hive_sample(client, _tbl, hive["id"], _cols, 6, log)

        for idx, flavour in enumerate(PROJECT_FLAVOURS):
            project_id = str(uuid.uuid4())
            start = today - timedelta(days=int(flavour["duration_days"] * 0.6))
            end   = start + timedelta(days=flavour["duration_days"])
            # Next free number for this hive + this prefix (avoids re-run collisions)
            prefix = flavour["code_prefix"]
            next_seq = existing_max.get((hive["id"], prefix), 0) + 1
            existing_max[(hive["id"], prefix)] = next_seq
            code = f"{prefix}-{today.year}-{next_seq:03d}"
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

            # Link a sample asset + BUNDLE the flavour's source systems (the X fabric):
            # logbook (reactive), pm_completions (preventive), inventory_items (BOM),
            # engineering_calcs (design basis). This is the connective tissue Ian's arc targets.
            links_this_project = []
            # The asset link must point at a REAL asset_nodes row.
            #
            # PJ11 (2026-07-28): this used to take the id straight off ctx["assets"], which is an
            # IN-MEMORY payload whose ids are minted by text_id("asset") — "asset-9fbe0f6f4022" —
            # and which assets.py deliberately never writes to the database (asset_brain.py inserts
            # the real rows into asset_nodes, with UUIDs). So every seeded asset link pointed at an
            # id that existed in NO table. Measured: 12 of 12 asset links dangling, while all 42
            # links of the other four types resolved.
            #
            # It looked healthy on the page because the link pill renders `label || link_id`, and
            # the label was correct — "Atlas Copco GA75+ VSD" — so a dead reference displayed as a
            # working one. The asset link is the first item in what this seeder's own comment calls
            # "the connective tissue Ian's arc targets"; it was the one strand not connected.
            hive_nodes = _hive_sample(client, "asset_nodes", hive["id"], ["id", "name"], 6, log)
            if hive_nodes:
                node = random.choice(hive_nodes)
                links_this_project.append(("asset", str(node["id"]),
                    node.get("name") or "linked asset"))
            elif hive_assets:
                # No asset_nodes for this hive: skip rather than write a link to a synthetic id.
                log("  warn: hive has ctx assets but no asset_nodes rows — asset link skipped "
                    "(a link to an id that resolves to nothing is worse than no link)")
            for link_type, n in FLAVOUR_BUNDLE.get(flavour["type"], []):
                for row in hive_sys.get(link_type, [])[:n]:
                    links_this_project.append((link_type, str(row["id"]), _link_label(link_type, row)))
            for _lt, _lid, _label in links_this_project:
                link_rows.append({
                    "id": str(uuid.uuid4()),
                    "project_id": project_id,
                    "hive_id": hive["id"],
                    "link_type": _lt,
                    "link_id": _lid,
                    "label": _label,
                    "created_at": to_iso(start),
                })

            # Daily progress logs — 3-6 per project, with one blocker if defined.
            # Spread evenly across the project span using float math (integer
            # division collapsed all 6 logs onto day 0 when duration < n_logs).
            n_logs = random.randint(3, 6)
            for li in range(n_logs):
                day_offset = (li * flavour["duration_days"]) / max(1, n_logs)
                log_date = (start + timedelta(days=day_offset)).date()
                if log_date > today.date():
                    log_date = today.date()
                blocker = None
                if flavour.get("blocker_examples") and li < len(flavour["blocker_examples"]):
                    blocker = flavour["blocker_examples"][li]
                # PJ17: pick the worker ONCE so reported_by and auth_uid describe the same person.
                # The seeder runs as service_role, so bind_progress_log_submitter (which pins both
                # for a browser write) correctly leaves these rows alone — which means the seeder
                # has to attribute them itself, exactly as assets.py and the other seeders do.
                # Without this every seeded report carries a NAME and no identity, and the
                # attribution features built on it have nothing to exercise.
                _reporter = random.choice(hive_workers) if hive_workers else None
                log_rows.append({
                    "id": str(uuid.uuid4()),
                    "project_id": project_id,
                    "hive_id": hive["id"],
                    "log_date": log_date.isoformat(),
                    "reported_by": _reporter["worker_name"] if _reporter else owner,
                    "auth_uid": (_reporter or {}).get("auth_uid"),
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

    co_rows   = _seed_change_orders(client, log, project_rows, workers)
    role_rows = _seed_project_roles(client, log, project_rows, workers)

    return {
        "projects": project_rows,
        "project_items": item_rows,
        "project_links": link_rows,
        "project_progress_logs": log_rows,
        "project_change_orders": co_rows,
        "project_roles": role_rows,
    }


# PJK1 / G5 (Project Manager deepwalk, 2026-07-28): project_change_orders had ZERO rows
# platform-wide, and project_roles too — two tables with policies, triggers and a complete UI
# (openNewCO, approveCO, rejectCO, cancelCO, openAddRole, removeRole) that no walk could reach.
# A change order is a CONTRACT AMENDMENT carrying cost_impact_php and schedule_impact_days, so
# "approve" here is a money decision, and it had never once been exercised against real data.
#
# The four statuses are generated with their companion fields TOGETHER so no row is fiction —
# the same discipline the Asset Hub arc used after the logbook arc produced 78 "skipped" PMs
# carrying completion notes. Specifically:
#   pending   -> no approver, no approved_at, no rejection_reason
#   approved  -> an approver AND a timestamp, never a rejection_reason
#   rejected  -> a REASON and no approved_at (the submitter has to learn something from it)
#   cancelled -> withdrawn by the requester before review: no approver, no reason
_CO_TEMPLATES = [
    ("Additional foundation reinforcement",
     "Soil test at pier 3 returned lower bearing capacity than the geotech report assumed; add "
     "rebar cage and 0.4 m of mass concrete.", 185000, 6),
    ("Upgrade switchgear to 630 A",
     "Client added two extrusion lines after design freeze; existing 400 A board would trip on "
     "simultaneous start.", 420000, 9),
    ("Relocate compressed-air header",
     "Header as drawn clashes with the new mezzanine beam at grid C.", 62000, 3),
    ("Substitute imported bearings with local equivalent",
     "12-week lead time on the specified SKF units; proposed NSK equivalent meets the same "
     "ISO 281 L10 rating.", -38000, -14),
    ("Extend commissioning window",
     "Client requested night-shift-only commissioning to avoid production loss.", 95000, 11),
]

_CO_REJECTION_REASONS = [
    "Cost impact exceeds the remaining contingency; resubmit with a value-engineered option.",
    "No client sign-off attached - this changes the contract sum and needs their approval first.",
    "The schedule impact pushes past the turnover date; propose a recovery plan alongside it.",
]


def _seed_change_orders(client, log, project_rows: list, workers: list) -> list:
    if not project_rows:
        return []
    rows = []
    per_hive_seq: dict = {}
    for proj in project_rows:
        # Not every project has a change order; a clean job that ran to plan is a real state too.
        if random.random() >= 0.55:
            continue
        hive_workers = [w for w in workers if w["hive_id"] == proj["hive_id"]]
        if not hive_workers:
            continue
        supervisors = [w for w in hive_workers if w["role"] == "supervisor"]
        for _ in range(random.randint(1, 3)):
            title, scope, cost, days = random.choice(_CO_TEMPLATES)
            requester = random.choice(hive_workers)
            seq = per_hive_seq.get(proj["hive_id"], 0) + 1
            per_hive_seq[proj["hive_id"]] = seq

            roll = random.random()
            if roll < 0.45:
                status, approver, approved_at, reject = "approved", (
                    supervisors[0]["worker_name"] if supervisors else requester["worker_name"]
                ), to_iso(datetime.now(timezone.utc) - timedelta(days=random.randint(1, 20))), None
            elif roll < 0.70:
                status, approver, approved_at, reject = "pending", None, None, None
            elif roll < 0.90:
                # A refusal must SAY WHY (the AH3 lesson, and the schema already has the column).
                status, approver, approved_at, reject = (
                    "rejected", None, None, random.choice(_CO_REJECTION_REASONS))
            else:
                status, approver, approved_at, reject = "cancelled", None, None, None

            rows.append({
                "project_id":           proj["id"],
                "hive_id":              proj["hive_id"],
                "co_number":            f"CO-{seq:03d}",
                "title":                title,
                "scope_change":         scope,
                "reason":               scope,
                "cost_impact_php":      cost,
                "schedule_impact_days": days,
                "status":               status,
                # NOTE (G1): requested_by / approved_by are TEXT NAMES. There is no auth_uid on
                # this table, so nothing here can prove WHO amended a contract — that is the
                # defect PJK1 exists to close, and the fixture must not paper over it.
                "requested_by":         requester["worker_name"],
                "requested_at":         to_iso(datetime.now(timezone.utc)
                                               - timedelta(days=random.randint(21, 60))),
                "approved_by":          approver,
                "approved_at":          approved_at,
                "rejection_reason":     reject,
            })

    if rows:
        try:
            client.table("project_change_orders").insert(rows).execute()
            by = {}
            for r in rows:
                by[r["status"]] = by.get(r["status"], 0) + 1
            log(f"  inserted {len(rows)} project_change_orders ({by})")
        except Exception as e:  # pragma: no cover — never crash the seed on a fixture table
            log(f"  WARN: project_change_orders insert failed: {type(e).__name__}: {e}")
            return []
    return rows


def _seed_project_roles(client, log, project_rows: list, workers: list) -> list:
    """G5: project_roles was also empty, so 'what a role actually gates' had nothing to test."""
    if not project_rows:
        return []
    rows = []
    for proj in project_rows:
        hive_workers = [w for w in workers if w["hive_id"] == proj["hive_id"]]
        if not hive_workers:
            continue
        picked = random.sample(hive_workers, k=min(len(hive_workers), random.randint(2, 3)))
        supervisors = [w for w in hive_workers if w["role"] == "supervisor"]
        assigner = supervisors[0]["worker_name"] if supervisors else picked[0]["worker_name"]
        for i, w in enumerate(picked):
            rows.append({
                "project_id":  proj["id"],
                "hive_id":     proj["hive_id"],
                "worker_name": w["worker_name"],
                # The CHECK allows exactly owner | planner | safety_officer | cost_engineer |
                # reviewer. Verified against pg_constraint rather than guessed — a first draft
                # here used 'lead'/'member', which the constraint would have rejected at runtime
                # while the seeder's try/except logged a WARN and returned an EMPTY list, leaving
                # the table exactly as empty as it started and looking like it had been seeded.
                # That is the same shape as the is_anomaly defect: writing a value the CHECK
                # forbids, and the failure being quiet.
                "role":        "owner" if i == 0 else random.choice(
                    ["planner", "safety_officer", "cost_engineer", "reviewer"]),
                "assigned_by": assigner,
            })
    if rows:
        try:
            client.table("project_roles").insert(rows).execute()
            log(f"  inserted {len(rows)} project_roles")
        except Exception as e:  # pragma: no cover
            log(f"  WARN: project_roles insert failed: {type(e).__name__}: {e}")
            return []
    return rows
