"""CMMS Bridge -- maps a CMMSDataset into WorkHive's native tables.

Takes the already-normalized expected_* lists from a CMMSDataset and
writes them into the real WorkHive tables so every page in the platform
shows the client's CMMS data in production format.

  expected_assets    -> assets
  expected_logbook   -> logbook
  expected_inventory -> inventory_items
  expected_pm        -> pm_assets + pm_scope_items

Called by client_hive.py after the hive and workers are created.
"""

import random
from datetime import datetime, timezone

from data.ph_equipment import EQUIPMENT_CATALOG
from .utils import text_id, random_timestamp_in_last_n_days, to_iso, batch_insert

# Equipment category -> WorkHive discipline (matches logbook.html dropdowns)
_CAT_TO_DISCIPLINE = {e["category"]: e["discipline"] for e in EQUIPMENT_CATALOG}

# CMMS unit -> WorkHive unit
_UNIT_MAP = {"EA": "pcs", "L": "L", "KG": "kg", "M": "m", "SET": "set",
             "each": "pcs", "litre": "L", "kg": "kg", "metre": "m"}

# PM interval days -> WorkHive frequency label
_FREQ_MAP = [(7, "Weekly"), (30, "Monthly"), (90, "Quarterly"),
             (180, "Semi-annual"), (365, "Annual")]


def _days_to_freq(days: int) -> str:
    for threshold, label in _FREQ_MAP:
        if days <= threshold:
            return label
    return "Annual"


def _pick_crit() -> str:
    return random.choices(
        ["Critical", "High", "Medium", "Low"],
        weights=[1, 2, 4, 1],
    )[0]


# ---------------------------------------------------------------------------
# Main bridge function
# ---------------------------------------------------------------------------

def bridge_to_workhive(client, ds, hive_id: str, workers: list,
                       log=None) -> dict:
    """Write a CMMSDataset into WorkHive's native tables under hive_id.

    Args:
        client:   Supabase Python client.
        ds:       CMMSDataset (must be generated).
        hive_id:  UUID of the target hive.
        workers:  List of {worker_name, role, hive_id, auth_uid}.
        log:      Optional callable(str) for streaming progress.

    Returns:
        {assets, logbook, inventory, pm_assets, pm_scope_items}
    """
    if not ds._generated:
        ds.generate()

    def _log(msg):
        if log:
            log(msg)

    hive_workers   = [w for w in workers if w["hive_id"] == hive_id]
    supervisor     = next((w for w in hive_workers if w["role"] == "supervisor"),
                          hive_workers[0] if hive_workers else None)
    if not supervisor:
        raise ValueError("No supervisor found for hive")

    # ── 1. Assets ────────────────────────────────────────────────────────────
    _log(f"  bridging {len(ds.expected_assets)} assets...")
    asset_rows: list[dict]   = []
    tag_to_uuid: dict[str, str] = {}   # tag_id -> assets.id (UUID)
    tag_to_type: dict[str, str] = {}   # tag_id -> category string

    for exp in ds.expected_assets:
        tag   = exp["_external_id"]
        row_id = text_id("asset")
        tag_to_uuid[tag] = row_id
        tag_to_type[tag] = exp.get("category", "General")

        worker = random.choice(hive_workers)
        ts     = random_timestamp_in_last_n_days(180)

        asset_rows.append({
            "id":           row_id,
            "worker_name":  worker["worker_name"],
            "asset_id":     tag,
            "name":         exp.get("name", tag),
            "type":         exp.get("category", "General"),
            "location":     exp.get("location", "Plant"),
            "criticality":  _pick_crit(),
            "registered_at": to_iso(ts),
            "created_at":   to_iso(ts),
            "status":       "approved",
            "hive_id":      hive_id,
            "submitted_by": worker["worker_name"],
            "approved_by":  supervisor["worker_name"],
            "approved_at":  to_iso(ts),
            "auth_uid":     worker.get("auth_uid"),
        })

    batch_insert(client, "assets", asset_rows, chunk=200)
    _log(f"    inserted {len(asset_rows)} assets")

    # ── 2. Logbook ───────────────────────────────────────────────────────────
    _log(f"  bridging {len(ds.expected_logbook)} logbook entries...")
    logbook_rows: list[dict] = []

    for exp in ds.expected_logbook:
        machine  = exp.get("machine", "")
        cat_type = tag_to_type.get(machine, "")
        discipline = _CAT_TO_DISCIPLINE.get(cat_type, "Mechanical")

        worker   = random.choice(hive_workers)
        created  = exp.get("created_at", to_iso(datetime.now(timezone.utc)))
        status   = exp.get("status", "Closed")
        is_bd    = exp.get("maintenance_type") == "Breakdown / Corrective"

        logbook_rows.append({
            "id":                  text_id("log"),
            "worker_name":         worker["worker_name"],
            "date":                created,
            "machine":             machine,
            "category":            discipline,
            "problem":             exp.get("problem", "Maintenance performed"),
            "action":              exp.get("action", "Work completed"),
            "knowledge":           exp.get("root_cause", ""),
            "status":              status,
            "created_at":          created,
            "maintenance_type":    exp.get("maintenance_type", "Breakdown / Corrective"),
            "root_cause":          exp.get("root_cause", "Wear"),
            "downtime_hours":      float(exp.get("downtime_hours") or 0),
            "hive_id":             hive_id,
            "asset_ref_id":        tag_to_uuid.get(machine),
            "parts_used":          [],
            "closed_at":           exp.get("closed_at"),
            "failure_consequence": "Running reduced" if is_bd else None,
            "readings_json":       None,
            "production_output":   None,
            "auth_uid":            worker.get("auth_uid"),
        })

    batch_insert(client, "logbook", logbook_rows, chunk=500)
    _log(f"    inserted {len(logbook_rows)} logbook entries")

    # ── Write to fault_knowledge for Machine History Surface ──────────────────
    # No embeddings — the machine history panel queries by machine field directly.
    # embed-entry does not fire on direct DB inserts (bypasses the webhook).
    fk_rows: list[dict] = []
    for lr in logbook_rows:
        if lr.get("problem") or lr.get("action") or lr.get("knowledge"):
            fk_rows.append({
                "hive_id":    hive_id,
                "logbook_id": lr.get("id"),
                "machine":    lr.get("machine"),
                "category":   lr.get("category"),
                "problem":    lr.get("problem")   or None,
                "root_cause": lr.get("root_cause") or None,
                "action":     lr.get("action")    or None,
                "knowledge":  lr.get("knowledge") or None,
                "worker_name": lr.get("worker_name"),
            })
    if fk_rows:
        batch_insert(client, "fault_knowledge", fk_rows, chunk=200)
        _log(f"    inserted {len(fk_rows)} fault_knowledge rows (no embeddings — machine history ready)")

    # ── 3. Inventory ─────────────────────────────────────────────────────────
    _log(f"  bridging {len(ds.expected_inventory)} inventory items...")
    inv_rows: list[dict] = []

    for exp in ds.expected_inventory:
        worker = random.choice(hive_workers)
        ts     = random_timestamp_in_last_n_days(120)
        unit   = _UNIT_MAP.get(str(exp.get("unit", "pcs")).upper(),
                               str(exp.get("unit", "pcs")).lower())

        inv_rows.append({
            "id":              text_id("inv"),
            "worker_name":     worker["worker_name"],
            "part_number":     str(exp.get("_external_id", text_id("prt"))),
            "part_name":       exp.get("name", "Part"),
            "category":        "General",
            "unit":            unit,
            "qty_on_hand":     int(exp.get("qty_on_hand", 0)),
            "min_qty":         int(exp.get("reorder_point", 2)),
            "bin_location":    f"Bin {random.randint(1,12)}-{random.choice(['A','B','C'])}",
            "linked_asset_ids": [],
            "notes":           "Imported from CMMS",
            "status":          "approved",
            "hive_id":         hive_id,
            "submitted_by":    worker["worker_name"],
            "approved_by":     supervisor["worker_name"],
            "approved_at":     to_iso(ts),
            "auth_uid":        worker.get("auth_uid"),
        })

    batch_insert(client, "inventory_items", inv_rows, chunk=200)
    _log(f"    inserted {len(inv_rows)} inventory items")

    # ── 4. PM Assets + Scope Items ───────────────────────────────────────────
    _log(f"  bridging {len(ds.expected_pm)} PM schedules...")
    pm_asset_rows: list[dict] = []

    for exp_pm in ds.expected_pm:
        tag    = exp_pm.get("asset_tag", "")
        worker = random.choice(hive_workers)
        exp_a  = next((a for a in ds.expected_assets
                       if a.get("_external_id") == tag), None)

        pm_asset_rows.append({
            "hive_id":          hive_id,
            "worker_name":      worker["worker_name"],
            "asset_name":       exp_a.get("name", tag) if exp_a else tag,
            "tag_id":           tag,
            "location":         exp_a.get("location", "Plant") if exp_a else "Plant",
            "category":         exp_a.get("category", "General") if exp_a else "General",
            "criticality":      "Major",
            "last_anchor_date": exp_pm.get("last_done",
                                datetime.now(timezone.utc).strftime("%Y-%m-%d")),
            "auth_uid":         worker.get("auth_uid"),
        })

    if pm_asset_rows:
        res           = client.table("pm_assets").insert(pm_asset_rows).execute()
        pm_inserted   = res.data or []
        _log(f"    inserted {len(pm_inserted)} pm_assets")

        scope_rows: list[dict] = []
        for pm_row, exp_pm in zip(pm_inserted, ds.expected_pm):
            scope_rows.append({
                "asset_id":    pm_row["id"],
                "hive_id":     hive_id,
                "item_text":   exp_pm.get("task", "Routine maintenance"),
                "frequency":   _days_to_freq(exp_pm.get("interval_days", 30)),
                "anchor_date": exp_pm.get("last_done",
                               datetime.now(timezone.utc).strftime("%Y-%m-%d")),
                "is_custom":   False,
            })

        if scope_rows:
            client.table("pm_scope_items").insert(scope_rows).execute()
            _log(f"    inserted {len(scope_rows)} pm_scope_items")
    else:
        pm_inserted = []
        scope_rows  = []

    return {
        "assets":        len(asset_rows),
        "logbook":       len(logbook_rows),
        "inventory":     len(inv_rows),
        "pm_assets":     len(pm_inserted),
        "pm_scope_items": len(scope_rows),
    }
