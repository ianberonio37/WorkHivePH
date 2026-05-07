"""Mock CMMS API Server -- Phase 2.

Serves the active CMMS_STATE dataset as HTTP endpoints mimicking:
  SAP PM OData v4     at  /mock/sap/odata/...
  IBM Maximo OSLC     at  /mock/maximo/oslc/...
  Generic REST        at  /mock/generic/api/...

Every inbound request is appended to REQUEST_LOG.
Every push from WorkHive back to the CMMS is appended to PUSH_LOG.

Both logs are accessible via /api/cmms/mock/log and cleared by
POST /api/cmms/mock/reset.
"""

import hashlib
import hmac
import re
import time
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request

# Shared HMAC secret for webhook signing tests (Phase 6).
# In production this lives in Supabase Vault; here it is a fixed test constant.
WEBHOOK_SECRET = "test-webhook-secret-workhive-2026"

mock_cmms_bp = Blueprint("mock_cmms", __name__)

# ---------------------------------------------------------------------------
# Shared logs (module-level -- survive between requests, cleared on reset)
# ---------------------------------------------------------------------------

REQUEST_LOG: list[dict] = []
PUSH_LOG:    list[dict] = []


def _log_req(cmms_type: str):
    """Append the current request to REQUEST_LOG."""
    REQUEST_LOG.append({
        "ts":        datetime.now(timezone.utc).isoformat(),
        "cmms_type": cmms_type,
        "method":    request.method,
        "path":      request.path,
        "params":    dict(request.args),
        "body":      request.get_json(silent=True) or {},
    })


def _log_push(cmms_type: str, entity: str, payload: dict):
    """Append an inbound push to PUSH_LOG."""
    PUSH_LOG.append({
        "ts":        datetime.now(timezone.utc).isoformat(),
        "cmms_type": cmms_type,
        "entity":    entity,
        "payload":   payload,
    })


def _dataset():
    """Return the current CMMSDataset (or None).

    Searches sys.modules for CMMS_STATE to handle both run modes:
      - `python app.py`  → app loaded as __main__, not as 'app'
      - imported by tests → app loaded as 'app'
    Without this, `from app import CMMS_STATE` would import a SECOND copy
    of app.py as a different module, giving an always-empty dict.
    """
    import sys
    for mod_name in ("__main__", "app"):
        mod = sys.modules.get(mod_name)
        if mod and hasattr(mod, "CMMS_STATE"):
            ds = mod.CMMS_STATE.get("dataset")
            if ds is not None:
                return ds
    return None


def _require_dataset(cmms_type: str):
    """Return (dataset, None) or (None, error_response)."""
    ds = _dataset()
    if ds is None:
        return None, (
            jsonify({"error": "No dataset generated. POST /api/cmms/generate first."}),
            503,
        )
    if ds.cmms_type != cmms_type:
        return None, (
            jsonify({
                "error": (
                    "Active dataset is '" + ds.cmms_type + "', not '" + cmms_type + "'. "
                    "Regenerate with the correct CMMS type."
                )
            }),
            409,
        )
    return ds, None


# ---------------------------------------------------------------------------
# Response envelope helpers
# ---------------------------------------------------------------------------

def _odata(rows: list, count: int | None = None) -> dict:
    """SAP OData v4 response envelope."""
    return {"d": {"results": rows, "__count": str(count if count is not None else len(rows))}}


def _oslc(rows: list) -> dict:
    """Maximo OSLC response envelope."""
    return {
        "rdfs:member":    rows,
        "oslc:totalCount": len(rows),
        "rdf:type":       "oslc:ResourceShape",
    }


def _generic(rows: list, total: int | None = None) -> dict:
    """Generic REST response envelope."""
    return {"data": rows, "count": len(rows), "total": total if total is not None else len(rows)}


# ---------------------------------------------------------------------------
# Delta / pagination helpers
# ---------------------------------------------------------------------------

def _sap_apply_filter(rows: list, filter_str: str) -> list:
    """Apply a minimal SAP OData $filter (date ge/gt/le/lt on ERDAT or AEDAT)."""
    if not filter_str:
        return rows
    m = re.search(r"(ERDAT|AEDAT)\s+(ge|gt|le|lt)\s+'(\d{4}-\d{2}-\d{2})'", filter_str)
    if not m:
        return rows
    field, op, date_val = m.group(1), m.group(2), m.group(3)
    ops = {
        "ge": lambda a, b: a >= b,
        "gt": lambda a, b: a > b,
        "le": lambda a, b: a <= b,
        "lt": lambda a, b: a < b,
    }
    cmp = ops.get(op, lambda a, b: True)
    return [r for r in rows if cmp(str(r.get(field, "")), date_val)]


def _sap_paginate(rows: list) -> list:
    """Apply SAP OData $top / $skip pagination."""
    top  = int(request.args.get("$top",  len(rows)))
    skip = int(request.args.get("$skip", 0))
    return rows[skip : skip + top]


def _maximo_apply_filter(rows: list, where_str: str, date_field: str) -> list:
    """Apply a minimal Maximo oslc.where date filter."""
    if not where_str:
        return rows
    m = re.search(r'(\w+)\s*>=\s*"?(\d{4}-\d{2}-\d{2})', where_str)
    if not m:
        return rows
    _, date_val = m.group(1), m.group(2)
    return [r for r in rows if str(r.get(date_field, ""))[:10] >= date_val]


def _maximo_paginate(rows: list) -> list:
    """Apply Maximo oslc.pageSize / oslc.pageIndex pagination."""
    page_size  = int(request.args.get("oslc.pageSize",  len(rows)))
    page_index = int(request.args.get("oslc.pageIndex", 1))
    skip = (page_index - 1) * page_size
    return rows[skip : skip + page_size]


def _generic_apply_filter(rows: list, date_field: str) -> list:
    """Apply Generic REST updated_after filter."""
    after = request.args.get("updated_after", "")
    if not after:
        return rows
    cutoff = after[:10]  # compare on date part only
    return [r for r in rows if str(r.get(date_field, ""))[:10] >= cutoff]


def _generic_paginate(rows: list) -> list:
    """Apply Generic REST limit / offset pagination."""
    limit  = int(request.args.get("limit",  len(rows)))
    offset = int(request.args.get("offset", 0))
    return rows[offset : offset + limit]


# ---------------------------------------------------------------------------
# SAP PM OData endpoints
# ---------------------------------------------------------------------------

@mock_cmms_bp.route("/mock/sap/odata/WorkOrders")
def sap_work_orders():
    _log_req("sap_pm")
    ds, err = _require_dataset("sap_pm")
    if err:
        return err
    rows = _sap_apply_filter(ds.work_orders, request.args.get("$filter", ""))
    total = len(rows)
    rows = _sap_paginate(rows)
    return jsonify(_odata(rows, total))


@mock_cmms_bp.route("/mock/sap/odata/Assets")
def sap_assets():
    _log_req("sap_pm")
    ds, err = _require_dataset("sap_pm")
    if err:
        return err
    rows = _sap_paginate(ds.assets)
    return jsonify(_odata(rows, len(ds.assets)))


@mock_cmms_bp.route("/mock/sap/odata/PMSchedules")
def sap_pm_schedules():
    _log_req("sap_pm")
    ds, err = _require_dataset("sap_pm")
    if err:
        return err
    active = [p for p in ds.pm_schedules if p.get("STATUS") == "ACTIVE"]
    rows = _sap_paginate(active)
    return jsonify(_odata(rows, len(active)))


@mock_cmms_bp.route("/mock/sap/odata/InventoryItems")
def sap_inventory():
    _log_req("sap_pm")
    ds, err = _require_dataset("sap_pm")
    if err:
        return err
    rows = _sap_paginate(ds.inventory)
    return jsonify(_odata(rows, len(ds.inventory)))


@mock_cmms_bp.route("/mock/sap/odata/WorkOrders/<aufnr>/complete", methods=["POST"])
def sap_receive_completion(aufnr):
    """WorkHive pushes a completed work order back to SAP."""
    _log_req("sap_pm")
    payload = request.get_json(silent=True) or {}
    _log_push("sap_pm", "work_order_completion", {"AUFNR": aufnr, **payload})
    return jsonify({"d": {"AUFNR": aufnr, "result": "success"}}), 200


@mock_cmms_bp.route("/mock/sap/odata/InventoryItems/<matnr>", methods=["PATCH"])
def sap_receive_inventory_update(matnr):
    """WorkHive pushes updated stock levels back to SAP MM."""
    _log_req("sap_pm")
    payload = request.get_json(silent=True) or {}
    _log_push("sap_pm", "inventory_update", {"MATNR": matnr, **payload})
    return jsonify({"d": {"MATNR": matnr, "result": "success"}}), 200


@mock_cmms_bp.route("/mock/sap/odata/PMOrders", methods=["POST"])
def sap_receive_pm_order():
    """WorkHive AI creates a new PM order in SAP (intelligence flows back)."""
    _log_req("sap_pm")
    payload = request.get_json(silent=True) or {}
    _log_push("sap_pm", "new_pm_order", payload)
    new_aufnr = "000099" + str(len(PUSH_LOG)).zfill(6)
    return jsonify({"d": {"AUFNR": new_aufnr, "result": "created"}}), 201


# ---------------------------------------------------------------------------
# IBM Maximo OSLC endpoints
# ---------------------------------------------------------------------------

@mock_cmms_bp.route("/mock/maximo/oslc/os/mxwo")
def maximo_work_orders():
    _log_req("maximo")
    ds, err = _require_dataset("maximo")
    if err:
        return err
    where = request.args.get("oslc.where", "")
    rows = _maximo_apply_filter(ds.work_orders, where, "REPORTDATE")
    total = len(rows)
    rows = _maximo_paginate(rows)
    return jsonify(_oslc(rows))


@mock_cmms_bp.route("/mock/maximo/oslc/os/mxasset")
def maximo_assets():
    _log_req("maximo")
    ds, err = _require_dataset("maximo")
    if err:
        return err
    rows = _maximo_paginate(ds.assets)
    return jsonify(_oslc(rows))


@mock_cmms_bp.route("/mock/maximo/oslc/os/mxpm")
def maximo_pm():
    _log_req("maximo")
    ds, err = _require_dataset("maximo")
    if err:
        return err
    active = [p for p in ds.pm_schedules if p.get("STATUS") == "ACTIVE"]
    rows = _maximo_paginate(active)
    return jsonify(_oslc(rows))


@mock_cmms_bp.route("/mock/maximo/oslc/os/mxinventory")
def maximo_inventory():
    _log_req("maximo")
    ds, err = _require_dataset("maximo")
    if err:
        return err
    rows = _maximo_paginate(ds.inventory)
    return jsonify(_oslc(rows))


@mock_cmms_bp.route("/mock/maximo/oslc/os/mxwo", methods=["POST"])
def maximo_receive_completion():
    """WorkHive pushes a completed work order back to Maximo."""
    _log_req("maximo")
    payload = request.get_json(silent=True) or {}
    _log_push("maximo", "work_order_completion", payload)
    return jsonify({"wonum": payload.get("WONUM", "?"), "result": "success"}), 200


# ---------------------------------------------------------------------------
# Generic REST endpoints
# ---------------------------------------------------------------------------

@mock_cmms_bp.route("/mock/generic/api/work-orders")
def generic_work_orders():
    _log_req("generic")
    ds, err = _require_dataset("generic")
    if err:
        return err
    rows = _generic_apply_filter(ds.work_orders, "created_date")
    total = len(rows)
    rows = _generic_paginate(rows)
    return jsonify(_generic(rows, total))


@mock_cmms_bp.route("/mock/generic/api/assets")
def generic_assets():
    _log_req("generic")
    ds, err = _require_dataset("generic")
    if err:
        return err
    rows = _generic_paginate(ds.assets)
    return jsonify(_generic(rows))


@mock_cmms_bp.route("/mock/generic/api/pm-schedules")
def generic_pm_schedules():
    _log_req("generic")
    ds, err = _require_dataset("generic")
    if err:
        return err
    active = [p for p in ds.pm_schedules if p.get("status") == "active"]
    rows = _generic_paginate(active)
    return jsonify(_generic(rows))


@mock_cmms_bp.route("/mock/generic/api/inventory")
def generic_inventory():
    _log_req("generic")
    ds, err = _require_dataset("generic")
    if err:
        return err
    rows = _generic_paginate(ds.inventory)
    return jsonify(_generic(rows))


@mock_cmms_bp.route("/mock/generic/api/work-orders/complete", methods=["POST"])
def generic_receive_completion():
    """WorkHive pushes completed work orders back to the generic CMMS."""
    _log_req("generic")
    payload = request.get_json(silent=True) or {}
    _log_push("generic", "work_order_completion", payload)
    return jsonify({"result": "success", "id": payload.get("work_order_no", "?")}), 200


@mock_cmms_bp.route("/mock/generic/api/inventory/update", methods=["POST"])
def generic_receive_inventory():
    """WorkHive pushes inventory updates back to the generic CMMS."""
    _log_req("generic")
    payload = request.get_json(silent=True) or {}
    _log_push("generic", "inventory_update", payload)
    return jsonify({"result": "success"}), 200


# ---------------------------------------------------------------------------
# Log management endpoints
# ---------------------------------------------------------------------------

@mock_cmms_bp.route("/api/cmms/mock/log")
def api_mock_log():
    """Return the request log and push log for test verification."""
    n = int(request.args.get("n", 50))
    return jsonify({
        "request_log": REQUEST_LOG[-n:],
        "push_log":    PUSH_LOG[-n:],
        "request_count": len(REQUEST_LOG),
        "push_count":    len(PUSH_LOG),
    })


@mock_cmms_bp.route("/api/cmms/mock/reset", methods=["POST"])
def api_mock_reset():
    """Clear request log, push log, and webhook event log between test runs."""
    REQUEST_LOG.clear()
    PUSH_LOG.clear()
    WEBHOOK_EVENT_LOG.clear()
    return jsonify({"ok": True, "message": "All mock logs cleared."})


# ---------------------------------------------------------------------------
# Webhook target (Phase 5) -- stand-in for WorkHive's cmms-webhook-receiver
# ---------------------------------------------------------------------------
# When WorkHive's real Edge Function is built, point the sender at its URL
# instead. This endpoint lets the webhook sender be tested immediately.

WEBHOOK_EVENT_LOG: list[dict] = []


@mock_cmms_bp.route("/mock/webhook-target/receive", methods=["POST"])
def mock_webhook_receive():
    """Stand-in for WorkHive's cmms-webhook-receiver Edge Function.

    Accepts CMMS webhook events, logs them, and returns a 200 ack.
    Replace this URL with the real Edge Function URL once built.
    """
    payload = request.get_json(silent=True) or {}
    WEBHOOK_EVENT_LOG.append({
        "ts":        datetime.now(timezone.utc).isoformat(),
        "event":     payload.get("event", "unknown"),
        "cmms_type": payload.get("cmms_type", "unknown"),
        "payload":   payload,
    })
    return jsonify({"ok": True, "received": payload.get("event", "unknown")}), 200


@mock_cmms_bp.route("/mock/webhook-target/receive-verified", methods=["POST"])
def mock_webhook_receive_verified():
    """HMAC-verified receiver -- rejects requests with a missing or wrong signature.

    Expected headers:
      X-CMMS-Signature: sha256=<hex>
      X-CMMS-Timestamp: <unix seconds>

    Signed payload = f"{timestamp}.{raw_body}"
    """
    sig_header = request.headers.get("X-CMMS-Signature", "")
    ts_header  = request.headers.get("X-CMMS-Timestamp",  "")

    if not sig_header or not ts_header:
        return jsonify({"error": "Missing signature headers"}), 401

    raw_body = request.get_data(as_text=True)
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        f"{ts_header}.{raw_body}".encode(),
        hashlib.sha256,
    ).hexdigest()
    provided = sig_header.replace("sha256=", "").strip()

    if not hmac.compare_digest(expected, provided):
        return jsonify({"error": "Invalid signature"}), 401

    payload = request.get_json(silent=True) or {}
    WEBHOOK_EVENT_LOG.append({
        "ts":        datetime.now(timezone.utc).isoformat(),
        "event":     payload.get("event", "unknown"),
        "cmms_type": payload.get("cmms_type", "unknown"),
        "payload":   payload,
        "signed":    True,
    })
    return jsonify({"ok": True, "received": payload.get("event"), "signed": True}), 200


@mock_cmms_bp.route("/api/cmms/mock/webhook-log")
def api_webhook_log():
    """Return the inbound webhook event log (CMMS -> WorkHive direction)."""
    n = int(request.args.get("n", 50))
    return jsonify({
        "events":      WEBHOOK_EVENT_LOG[-n:],
        "event_count": len(WEBHOOK_EVENT_LOG),
    })


@mock_cmms_bp.route("/api/cmms/mock/webhook-reset", methods=["POST"])
def api_webhook_reset():
    """Clear the inbound webhook event log."""
    WEBHOOK_EVENT_LOG.clear()
    return jsonify({"ok": True})


@mock_cmms_bp.route("/api/cmms/mock/endpoints")
def api_mock_endpoints():
    """Return the base URLs for each CMMS type (for configuring WorkHive sync)."""
    base = request.host_url.rstrip("/")
    return jsonify({
        "sap_pm": {
            "work_orders":  base + "/mock/sap/odata/WorkOrders",
            "assets":       base + "/mock/sap/odata/Assets",
            "pm_schedules": base + "/mock/sap/odata/PMSchedules",
            "inventory":    base + "/mock/sap/odata/InventoryItems",
            "push_complete": base + "/mock/sap/odata/WorkOrders/{AUFNR}/complete",
            "push_pm_order": base + "/mock/sap/odata/PMOrders",
        },
        "maximo": {
            "work_orders":  base + "/mock/maximo/oslc/os/mxwo",
            "assets":       base + "/mock/maximo/oslc/os/mxasset",
            "pm_schedules": base + "/mock/maximo/oslc/os/mxpm",
            "inventory":    base + "/mock/maximo/oslc/os/mxinventory",
            "push_complete": base + "/mock/maximo/oslc/os/mxwo (POST)",
        },
        "generic": {
            "work_orders":  base + "/mock/generic/api/work-orders",
            "assets":       base + "/mock/generic/api/assets",
            "pm_schedules": base + "/mock/generic/api/pm-schedules",
            "inventory":    base + "/mock/generic/api/inventory",
            "push_complete": base + "/mock/generic/api/work-orders/complete",
            "push_inventory": base + "/mock/generic/api/inventory/update",
        },
    })
