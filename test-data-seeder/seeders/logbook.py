"""Seed logbook entries with values matching the platform's actual form fields."""
import random
from datetime import timedelta

from data.ph_equipment import EQUIPMENT_CATALOG
from data.ph_faults import FAULTS_BY_CATEGORY, get_faults_for_category
from .utils import text_id, random_timestamp_in_last_n_days, to_iso, batch_insert

# ── Platform's exact dropdown values ──────────────────────────────────────

MAINTENANCE_TYPES = [
    ("Breakdown / Corrective", 30),
    ("Preventive Maintenance", 45),
    ("Inspection", 18),
    ("Project Work", 7),
]

DISCIPLINES = [
    "Mechanical", "Electrical", "Hydraulic", "Pneumatic",
    "Instrumentation", "Lubrication", "Other",
]

ROOT_CAUSES = [
    ("Wear", 18),
    ("Lubrication Failure", 12),
    ("Contamination / Dirt", 12),
    ("Vibration / Fatigue", 10),
    ("Electrical Fault", 10),
    ("Mechanical Damage", 9),
    ("Misalignment", 8),
    ("Overload", 7),
    ("Corrosion", 5),
    ("Human Error", 4),
    ("Design Issue", 3),
    ("Unknown", 2),
]

FAILURE_CONSEQUENCES = [
    ("Running reduced", 35),
    ("Stopped production", 30),
    ("Hidden", 25),
    ("Safety risk", 10),
]

# Equipment.category → discipline (uses the catalog as source of truth)
CATEGORY_TO_DISCIPLINE: dict[str, str] = {}
for _arch in EQUIPMENT_CATALOG:
    CATEGORY_TO_DISCIPLINE[_arch["category"]] = _arch["discipline"]

# Reading templates per discipline (matches READINGS_FALLBACK in logbook.html)
READINGS_BY_DISCIPLINE = {
    "Mechanical": [
        ("temperature_c", 50.0, 95.0, 1),
        ("vibration_mms", 1.5, 12.0, 1),
        ("pressure_bar", 1.0, 10.0, 1),
    ],
    "Electrical": [
        ("voltage_v", 380.0, 440.0, 0),
        ("current_a", 5.0, 200.0, 1),
        ("temperature_c", 40.0, 90.0, 1),
    ],
    "Hydraulic": [
        ("pressure_bar", 80.0, 220.0, 0),
        ("flow_lpm", 15.0, 90.0, 1),
        ("temperature_c", 40.0, 80.0, 1),
    ],
    "Pneumatic": [
        ("pressure_bar", 4.0, 8.5, 1),
        ("temperature_c", 30.0, 60.0, 1),
    ],
    "Instrumentation": [
        ("signal_ma", 4.0, 20.0, 2),
        ("temperature_c", 25.0, 50.0, 1),
    ],
    "Lubrication": [
        ("temperature_c", 50.0, 80.0, 1),
        ("pressure_bar", 2.0, 5.0, 1),
    ],
}

PREVENTIVE_NOTES = [
    {"problem": "Routine PM as scheduled", "action": "Cleaned, lubricated, checked tightness, recorded readings", "knowledge": "All readings within normal range"},
    {"problem": "Weekly inspection round", "action": "Visual inspection, no abnormalities; topped up grease points", "knowledge": "No further action"},
    {"problem": "Monthly oil change due", "action": "Drained, flushed, refilled; replaced filter", "knowledge": "Oil sample sent for analysis"},
    {"problem": "Quarterly thermal scan", "action": "Thermography survey of MCC; no hot spots above 60°C", "knowledge": "Report filed"},
    {"problem": "Vibration trending check", "action": "Recorded ISO 10816 readings; trend stable", "knowledge": "Re-check in 30 days"},
    {"problem": "Greasing per OEM schedule", "action": "Purged old grease, refilled per spec", "knowledge": "Next service in 30 days"},
]

INSPECTION_NOTES = [
    {"problem": "Pre-shift walkdown", "action": "Visual + audible check, no findings", "knowledge": "Normal"},
    {"problem": "Permit-to-work area inspection", "action": "Verified isolation, gas test passed, signed permit", "knowledge": "Cleared for hot work"},
    {"problem": "Spare parts shelf audit", "action": "Counted critical spares vs min levels", "knowledge": "2 items below min, raised PR"},
    {"problem": "Boundary inspection (visual)", "action": "Walked perimeter, all guards in place", "knowledge": "OK"},
]

PROJECT_NOTES = [
    {"problem": "Install new VFD on Conveyor BC-201", "action": "Mounted, wired, parameterized, commissioned", "knowledge": "Set ramp 8s; document P-codes"},
    {"problem": "Re-pipe cooling water to new chiller bay", "action": "Hydrostatic test passed at 1.5x design", "knowledge": "Use SCH40 ASTM A53 from now on"},
    {"problem": "Vibration baseline survey", "action": "Recorded ISO 10816 readings on all critical pumps", "knowledge": "Baseline filed for trending"},
    {"problem": "Energy audit lighting upgrade", "action": "Replaced 24 HBay fixtures with LED", "knowledge": "Lux levels +18%, kWh -55%"},
]


def _weighted_choice(pairs):
    pool = []
    for value, weight in pairs:
        pool.extend([value] * weight)
    return random.choice(pool)


def _discipline_for_asset(asset_type: str) -> str:
    return CATEGORY_TO_DISCIPLINE.get(asset_type, "Mechanical")


def _readings_for(discipline: str, abnormal: bool = False) -> dict | None:
    spec = READINGS_BY_DISCIPLINE.get(discipline)
    if not spec:
        return None
    out = {}
    for key, lo, hi, decimals in spec:
        if abnormal and random.random() < 0.5:
            # Push 20% of readings outside the normal band
            value = hi * random.uniform(1.05, 1.25)
        else:
            value = random.uniform(lo, hi)
        out[key] = round(value, decimals)
    return out


def seed_logbook(client, log, ctx: dict) -> dict:
    workers = ctx["workers"]
    assets_by_hive = ctx["assets_by_hive"]

    target_total = sum(w["logbook_target"] for w in workers)
    log(f"Generating ~{target_total} logbook entries with platform-correct field values...")

    rows = []
    for w in workers:
        hive_assets = assets_by_hive.get(w["hive_id"], [])
        if not hive_assets:
            continue

        for _ in range(w["logbook_target"]):
            asset = random.choice(hive_assets)
            asset_type = asset.get("type") or "AC Motor"
            discipline = _discipline_for_asset(asset_type)
            maint_type = _weighted_choice(MAINTENANCE_TYPES)
            ts = random_timestamp_in_last_n_days(90)
            entry_id = text_id("log")

            problem = action = knowledge = ""
            root_cause = ""
            failure_consequence = None
            readings_json = None
            production_output = None
            loto_applied = False
            permit_reference = None
            downtime = 0
            parts: list = []

            if maint_type == "Breakdown / Corrective":
                fault = random.choice(get_faults_for_category(asset_type))
                problem = fault["problem"]
                action = fault["action"]
                knowledge = fault["root_cause"]
                root_cause = _weighted_choice(ROOT_CAUSES)
                failure_consequence = _weighted_choice(FAILURE_CONSEQUENCES)
                downtime = round(random.uniform(0.5, 8.0), 1)
                parts = [{"name": p, "qty": 1} for p in fault.get("parts_used", [])]
                readings_json = _readings_for(discipline, abnormal=True)
                # Production output only when the consequence stopped production (sometimes)
                if failure_consequence == "Stopped production" and random.random() < 0.6:
                    total = random.randint(800, 2400)
                    good = int(total * random.uniform(0.85, 0.99))
                    production_output = {"good_units": good, "total_units": total}
                # LOTO / Permit-to-Work (Extension 3): high-consequence repairs require energy
                # isolation (RA 11058 / DOLE DO 198-18). Deliberate safety record, not regex-inferred.
                if failure_consequence in ("Safety risk", "Stopped production"):
                    loto_applied = True
                    permit_reference = f"PTW-{ts:%Y}-{random.randint(1000, 9999)}"
            elif maint_type == "Preventive Maintenance":
                note = random.choice(PREVENTIVE_NOTES)
                problem, action, knowledge = note["problem"], note["action"], note["knowledge"]
                # Some PMs record readings too (no abnormal bias)
                if random.random() < 0.4:
                    readings_json = _readings_for(discipline, abnormal=False)
            elif maint_type == "Inspection":
                note = random.choice(INSPECTION_NOTES)
                problem, action, knowledge = note["problem"], note["action"], note["knowledge"]
            else:  # Project Work
                note = random.choice(PROJECT_NOTES)
                problem, action, knowledge = note["problem"], note["action"], note["knowledge"]
                downtime = round(random.uniform(0.0, 4.0), 1)

            # ~5% of breakdowns left open
            is_open = (maint_type == "Breakdown / Corrective" and random.random() < 0.05)
            status = "Open" if is_open else "Closed"
            closed_at = None if is_open else to_iso(ts + timedelta(hours=max(0.5, downtime)))

            rows.append({
                "id": entry_id,
                "worker_name": w["worker_name"],
                "date": to_iso(ts),
                # Match production format: logbook.html stores assets.asset_id
                # (the human code like "PMP-001"), not "{name} (asset_id)".
                # Misalignment broke analytics joins (PRODUCTION_FIXES #17).
                "machine": asset["asset_id"],
                "category": discipline,                  # ← discipline goes here
                "problem": problem,
                "action": action,
                "knowledge": knowledge,
                "status": status,
                "created_at": to_iso(ts),
                "maintenance_type": maint_type,          # ← Breakdown/PM/Inspection/Project
                "root_cause": root_cause,
                "downtime_hours": downtime,
                "hive_id": w["hive_id"],
                # asset_ref_id (text) was dropped in Phase 5b.1 (2026-05-12)
                # in favour of asset_node_id (uuid). asset_node_id is left
                # NULL here because asset_nodes is populated AFTER logbook in
                # the orchestrator; the post-seed bridge resolves the linkage
                # via the machine text -> asset_nodes.tag lookup.
                "parts_used": parts,
                "closed_at": closed_at,
                "failure_consequence": failure_consequence,
                "readings_json": readings_json,
                "production_output": production_output,
                "loto_applied": loto_applied,
                "permit_reference": permit_reference,
                "auth_uid": w.get("auth_uid"),
            })

    inserted = batch_insert(client, "logbook", rows, chunk=500)
    log(f"  inserted {inserted} logbook entries")
    log(f"  → discipline values: {sorted(set(r['category'] for r in rows))}")
    log(f"  → maintenance types: {sorted(set(r['maintenance_type'] for r in rows))}")
    return {"logbook_count": inserted}


def link_logbook_to_asset_nodes(client, log, ctx: dict) -> dict:
    """Post-seed bridge: backfill logbook.asset_node_id from the machine text
    field using the (hive_id, tag) -> asset_nodes.id lookup.

    Runs AFTER asset_brain.py inserts asset_nodes. Without this, the Asset Hub
    detail panel shows "No history rows tied to this asset yet." because the
    page joins logbook to asset_nodes via asset_node_id (Phase 5b.1 dropped the
    legacy asset_ref_id text column).
    """
    log("Linking logbook entries to asset_nodes via (hive_id, machine -> tag)...")
    nodes = client.table("asset_nodes").select("id, hive_id, tag").execute().data or []
    by_hive_tag = {(n["hive_id"], n["tag"]): n["id"] for n in nodes}
    if not by_hive_tag:
        log("  no asset_nodes yet — link step skipped")
        return {"logbook_linked": 0}

    # 2026-05-19 Mega Gate fix: 3700 logbook rows used to issue 3700
    # individual UPDATE round-trips, which on PG 17 + supabase-py would
    # blow past the 60s statement_timeout when the index hadn't warmed.
    # New strategy: bucket all rows by their target asset_node_id, then
    # do ONE update per bucket via .in_("id", [...]). That collapses
    # 3700 calls down to ~90 (one per distinct asset_node_id).
    total = 0
    buckets: dict[str, list[str]] = {}
    # Bucket EVERY currently-unlinked row, not just the first PostgREST page. The
    # previous version pulled `.limit(1000)` then broke after one page, so with
    # >1000 logbook rows it linked only the first 1000 and left the rest NULL --
    # re-opening the 2700-entry asset-history undercount (v_asset_truth.
    # lifetime_logbook_entries) on EVERY reseed (the cross-session seesaw
    # validate_logbook_asset_linkage guards). We do NOT update inside this loop,
    # so the unlinked set is stable and OFFSET pagination over it is safe.
    PAGE = 1000
    offset = 0
    while True:
        batch = (
            client.table("logbook")
            .select("id, hive_id, machine")
            .is_("asset_node_id", "null")
            .order("id")
            .range(offset, offset + PAGE - 1)
            .execute()
            .data
            or []
        )
        if not batch:
            break
        for r in batch:
            nid = by_hive_tag.get((r["hive_id"], r["machine"]))
            if nid:
                buckets.setdefault(nid, []).append(r["id"])
        if len(batch) < PAGE:
            break
        offset += PAGE

    # Chunk each bucket into ~500-id slices so the SQL `IN ($1, $2, ...)`
    # stays within Postgres's parameter limit.
    CHUNK = 500
    for nid, ids in buckets.items():
        for i in range(0, len(ids), CHUNK):
            chunk = ids[i:i + CHUNK]
            client.table("logbook").update({"asset_node_id": nid}).in_("id", chunk).execute()
            total += len(chunk)
    log(f"  linked {total} logbook entries to asset_nodes (in {len(buckets)} buckets)")
    return {"logbook_linked": total}
