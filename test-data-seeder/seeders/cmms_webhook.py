"""CMMS Webhook Event Generator -- Phase 5.

Generates realistic webhook event payloads in CMMS format (SAP / Maximo /
Generic) that simulate a live CMMS pushing events to WorkHive in real time.

Five event types:
  work_order.created   -- new WO just opened in the CMMS
  work_order.updated   -- existing WO status or hours changed
  work_order.completed -- WO marked done (TECO / CLOSE / closed)
  pm.overdue           -- PM schedule past its due date
  asset.updated        -- equipment master record changed

Usage:
    from seeders.cmms_webhook import generate_event, generate_batch
    event = generate_event(ds, "work_order.created", index=0)
    batch = generate_batch(ds, "work_order.completed", count=5)
"""

from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_closed_wo(wo: dict, cmms_type: str) -> bool:
    if cmms_type == "sap_pm":
        return wo.get("ISTAT") == "I0045"
    elif cmms_type == "maximo":
        return wo.get("STATUS") in ("COMP", "CLOSE")
    return wo.get("status") == "closed"


def _is_overdue_pm(pm: dict, cmms_type: str) -> bool:
    if cmms_type == "sap_pm":
        return pm.get("NEXT_DUE", "9999") < datetime.now(timezone.utc).strftime("%Y-%m-%d")
    elif cmms_type == "maximo":
        return pm.get("NEXTDUEDATE", "9999") < datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return pm.get("next_due", "9999") < datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Event envelope wrapper
# ---------------------------------------------------------------------------

def _envelope(event_type: str, cmms_type: str, payload: dict) -> dict:
    return {
        "event":     event_type,
        "cmms_type": cmms_type,
        "timestamp": _now(),
        "payload":   payload,
    }


# ---------------------------------------------------------------------------
# Per-event-type generators
# ---------------------------------------------------------------------------

def _evt_wo_created(ds, index: int) -> dict | None:
    """A new work order just appeared in the CMMS."""
    if not ds.work_orders:
        return None
    wo = ds.work_orders[index % len(ds.work_orders)]
    return _envelope("work_order.created", ds.cmms_type, wo)


def _evt_wo_updated(ds, index: int) -> dict | None:
    """An existing WO had its status or hours updated."""
    if not ds.work_orders:
        return None
    wo = dict(ds.work_orders[index % len(ds.work_orders)])

    # Simulate a status bump -- Open -> Released in SAP, WAPPR -> INPRG in Maximo
    if ds.cmms_type == "sap_pm":
        wo["ISTAT"] = "I0002"  # Released
        changed = ["ISTAT", "AEDAT"]
    elif ds.cmms_type == "maximo":
        wo["STATUS"] = "INPRG"  # In progress
        changed = ["STATUS"]
    else:
        wo["status"] = "open"
        wo["actual_hours"] = round((wo.get("actual_hours") or 0) + 1.5, 1)
        changed = ["status", "actual_hours"]

    return _envelope("work_order.updated", ds.cmms_type, {**wo, "_changed_fields": changed})


def _evt_wo_completed(ds, index: int) -> dict | None:
    """A WO was marked completed / TECO in the CMMS."""
    closed = [wo for wo in ds.work_orders if _is_closed_wo(wo, ds.cmms_type)]
    if not closed:
        return None
    wo = closed[index % len(closed)]
    return _envelope("work_order.completed", ds.cmms_type, wo)


def _evt_pm_overdue(ds, index: int) -> dict | None:
    """A PM schedule has passed its due date."""
    overdue = [p for p in ds.pm_schedules if _is_overdue_pm(p, ds.cmms_type)]
    if not overdue:
        # Fall back to any PM schedule to avoid empty events
        if not ds.pm_schedules:
            return None
        p = ds.pm_schedules[index % len(ds.pm_schedules)]
    else:
        p = overdue[index % len(overdue)]
    return _envelope("pm.overdue", ds.cmms_type, p)


def _evt_asset_updated(ds, index: int) -> dict | None:
    """Equipment master record changed (location, status, etc.)."""
    if not ds.assets:
        return None
    asset = dict(ds.assets[index % len(ds.assets)])

    if ds.cmms_type == "sap_pm":
        asset["ILOAN"] = "Updated Location " + str(index + 1)
        asset["_changed_fields"] = ["ILOAN"]
    elif ds.cmms_type == "maximo":
        asset["STATUS"] = "OPERATING"
        asset["_changed_fields"] = ["STATUS"]
    else:
        asset["location"] = "Updated Area " + str(index + 1)
        asset["_changed_fields"] = ["location"]

    return _envelope("asset.updated", ds.cmms_type, asset)


_GENERATORS = {
    "work_order.created":   _evt_wo_created,
    "work_order.updated":   _evt_wo_updated,
    "work_order.completed": _evt_wo_completed,
    "pm.overdue":           _evt_pm_overdue,
    "asset.updated":        _evt_asset_updated,
}

EVENT_TYPES = list(_GENERATORS.keys())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_event(ds, event_type: str, index: int = 0) -> dict | None:
    """Generate one webhook event payload.

    Returns None if the dataset has no suitable records for the event type.
    """
    gen = _GENERATORS.get(event_type)
    if gen is None:
        raise ValueError(f"Unknown event_type '{event_type}'. Use: {EVENT_TYPES}")
    return gen(ds, index)


def generate_batch(ds, event_type: str, count: int = 5) -> list[dict]:
    """Generate `count` events of the given type (varying records by index)."""
    events = []
    for i in range(count):
        evt = generate_event(ds, event_type, index=i)
        if evt is None:
            break
        events.append(evt)
    return events


def generate_mixed_batch(ds, count: int = 10) -> list[dict]:
    """Generate a mixed batch cycling through all 5 event types."""
    events = []
    for i in range(count):
        event_type = EVENT_TYPES[i % len(EVENT_TYPES)]
        evt = generate_event(ds, event_type, index=i // len(EVENT_TYPES))
        if evt:
            events.append(evt)
    return events
