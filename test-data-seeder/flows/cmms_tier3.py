"""Phase 6: Tier 3 Verification Tests.

Tests the real-time bidirectional loop:
  CMMS pushes events -> WorkHive processes them -> WorkHive pushes back to CMMS.

Tests 1-2 and 4-5 require the seeder server running on port 5000 (HTTP calls).
Test 3 (ordering) runs without HTTP -- direct DB upserts only.

Tests:
  tier3_scenario_a   -- full loop: webhook in -> processed -> completion out
  tier3_scenario_b   -- intelligence back to SAP: pm.overdue -> push PM order
  tier3_ordering     -- 5 status updates for same WO -> final state is correct
  tier3_no_drift     -- 30 mixed events processed; external_sync count matches
  tier3_signature    -- HMAC-signed event accepted; unsigned rejected with 401

Run via: POST /api/cmms/tier3-test
"""

import hashlib
import hmac
import json
import time
from datetime import datetime, timezone

import requests as _req

from seeders.cmms_webhook import generate_event, generate_batch, generate_mixed_batch
from seeders.cmms_syncer   import CMMSSyncer, MOCK_BASE_URL
from seeders.cmms_importer import import_raw_rows, count_in_db, cleanup, _validate_row

LOCAL_MOCK_TARGET     = "http://127.0.0.1:5000/mock/webhook-target/receive"
VERIFIED_MOCK_TARGET  = "http://127.0.0.1:5000/mock/webhook-target/receive-verified"
WEBHOOK_SECRET        = "test-webhook-secret-workhive-2026"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pass(n, d): return {"name": n, "status": "PASS", "detail": d}
def _fail(n, d): return {"name": n, "status": "FAIL", "detail": d}
def _skip(n, d): return {"name": n, "status": "SKIP", "detail": d}


def _send(target: str, event: dict, sign: bool = False) -> tuple[int, dict]:
    """POST one event to target. Returns (status_code, response_json)."""
    body_str = json.dumps(event)
    headers  = {"Content-Type": "application/json"}
    if sign:
        ts  = str(int(time.time()))
        sig = hmac.new(WEBHOOK_SECRET.encode(),
                       f"{ts}.{body_str}".encode(), hashlib.sha256).hexdigest()
        headers["X-CMMS-Signature"] = f"sha256={sig}"
        headers["X-CMMS-Timestamp"] = ts
    resp = _req.post(target, data=body_str, headers=headers, timeout=10)
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


def _webhook_log(base_url: str, n: int = 50) -> list:
    """Fetch the WEBHOOK_EVENT_LOG from the mock server."""
    try:
        r = _req.get(base_url + "/api/cmms/mock/webhook-log", params={"n": n}, timeout=5)
        return r.json().get("events", [])
    except Exception:
        return []


def _reset_logs(base_url: str):
    try:
        _req.post(base_url + "/api/cmms/mock/reset",         timeout=5)
        _req.post(base_url + "/api/cmms/mock/webhook-reset", timeout=5)
    except Exception:
        pass


def _normalize_event_to_row(event: dict, cmms_type: str) -> dict | None:
    """Convert a webhook event payload to an external_sync row."""
    payload = event.get("payload", {})
    if cmms_type == "sap_pm":
        ext_id = payload.get("AUFNR")
        status_raw = payload.get("ISTAT", "I0001")
        from data.cmms_templates import SAP_ISTAT_TO_STATUS
        status = SAP_ISTAT_TO_STATUS.get(status_raw, "Open")
    elif cmms_type == "maximo":
        ext_id = payload.get("WONUM")
        from data.cmms_templates import MAXIMO_STATUS_TO_STATUS
        status = MAXIMO_STATUS_TO_STATUS.get(payload.get("STATUS", ""), "Open")
    else:
        ext_id = payload.get("work_order_no")
        from data.cmms_templates import GENERIC_STATUS_TO_STATUS
        status = GENERIC_STATUS_TO_STATUS.get(payload.get("status", ""), "Open")

    if not ext_id:
        return None
    return {
        "system_type":    cmms_type,
        "external_id":    ext_id,
        "entity_type":    "work_order",
        "workhive_table": "logbook",
        "status":         status,
        "sync_payload":   {"description": payload.get("LTXT") or payload.get("DESCRIPTION")
                           or payload.get("description", "")},
        "sync_status":    "active",
    }


# ---------------------------------------------------------------------------
# Test 1 -- Scenario A: Full loop (send -> receive -> process -> push back)
# ---------------------------------------------------------------------------

def test_tier3_scenario_a(syncer, client, ds, log):
    """CMMS creates WO -> webhook received -> imported to external_sync -> completion pushed back."""
    name = "tier3_scenario_a"
    _reset_logs(syncer.base_url)
    cleanup(client, ds.cmms_type)

    # Step 1: CMMS sends work_order.created webhook
    evt = generate_event(ds, "work_order.created", index=0)
    if not evt:
        return _skip(name, "No work_order.created event could be generated")

    log(f"  [{name}] sending work_order.created to mock target...")
    status_code, _ = _send(LOCAL_MOCK_TARGET, evt)
    if status_code != 200:
        return _fail(name, f"Mock target returned {status_code}")

    # Step 2: Verify mock received it
    events = _webhook_log(syncer.base_url)
    received = [e for e in events if e.get("event") == "work_order.created"]
    if not received:
        return _fail(name, "WEBHOOK_EVENT_LOG empty -- event not logged by mock target")

    # Step 3: Process -- simulate WorkHive Edge Function importing the event
    row = _normalize_event_to_row(evt, ds.cmms_type)
    if not row:
        return _fail(name, "Could not normalize event to external_sync row")
    import_raw_rows(client, [row])
    count = count_in_db(client, ds.cmms_type, "work_order")
    if count == 0:
        return _fail(name, "Record not found in external_sync after processing event")

    # Step 4: Push completion back to mock CMMS
    ext_id = row["external_id"]
    log(f"  [{name}] pushing completion for {ext_id} back to mock CMMS...")
    try:
        syncer.push_completion(ext_id, {"WH_STATUS": "Closed", "WH_ACTUAL_HOURS": 6.0})
    except Exception as e:
        return _fail(name, f"Push completion raised: {e}")

    push_log = syncer.get_push_log()
    if not push_log:
        return _fail(name, "PUSH_LOG empty -- loop not closed")

    return _pass(name,
        f"Loop closed: webhook received ({received[0]['event']}) -> "
        f"external_sync row created -> completion in PUSH_LOG ({len(push_log)} entries)")


# ---------------------------------------------------------------------------
# Test 2 -- Scenario B: Intelligence back to SAP (pm.overdue -> new PM order)
# ---------------------------------------------------------------------------

def test_tier3_scenario_b(syncer, client, ds, log):
    """pm.overdue webhook -> AI generates PM order -> SAP receives it."""
    name = "tier3_scenario_b"
    _reset_logs(syncer.base_url)

    # Send pm.overdue webhook
    evt = generate_event(ds, "pm.overdue", index=0)
    if not evt:
        return _skip(name, "No pm.overdue event (no overdue PM schedules in dataset)")

    log(f"  [{name}] sending pm.overdue webhook...")
    status_code, _ = _send(LOCAL_MOCK_TARGET, evt)
    if status_code != 200:
        return _fail(name, f"Mock target returned {status_code}")

    # Simulate WorkHive AI responding by creating a new PM order in SAP
    pm_payload = evt.get("payload", {})
    equnr = (pm_payload.get("EQUNR") or pm_payload.get("ASSETNUM")
             or pm_payload.get("asset_tag") or "UNKNOWN")
    task  = (pm_payload.get("TASK_DESC") or pm_payload.get("DESCRIPTION")
             or pm_payload.get("task") or "AI-recommended PM")

    log(f"  [{name}] pushing AI PM order for {equnr} to mock SAP...")
    try:
        result = syncer.push_pm_order({"EQUNR": equnr, "TASK_DESC": task, "source": "workhive_ai"})
    except Exception as e:
        if ds.cmms_type != "sap_pm":
            return _skip(name, f"push_pm_order not supported for {ds.cmms_type}")
        return _fail(name, f"push_pm_order raised: {e}")

    if ds.cmms_type != "sap_pm":
        return _skip(name, "push_pm_order only implemented for SAP PM")

    push_log = syncer.get_push_log()
    pm_orders = [p for p in push_log if p.get("entity") == "new_pm_order"]
    if not pm_orders:
        return _fail(name, "No new_pm_order in PUSH_LOG -- intelligence did not reach SAP")

    return _pass(name,
        f"pm.overdue received -> AI generated PM order for {equnr} -> "
        f"PUSH_LOG confirms SAP received it (AUFNR={result.get('d', {}).get('AUFNR', '?')})")


# ---------------------------------------------------------------------------
# Test 3 -- Ordering: same WO updated 5 times, final state correct
# ---------------------------------------------------------------------------

def test_tier3_ordering(syncer, client, ds, log):
    """5 status updates for the same work order -- final upsert must win."""
    name = "tier3_ordering"
    cleanup(client, ds.cmms_type)

    # Build 5 rows for the same external_id with escalating statuses
    test_ext_id = "ORDERING-TEST-001"
    statuses    = ["Open", "Open", "Open", "Open", "Closed"]

    log(f"  [{name}] importing 5 status updates for {test_ext_id}...")
    for i, status in enumerate(statuses):
        row = {
            "system_type":    ds.cmms_type,
            "external_id":    test_ext_id,
            "entity_type":    "work_order",
            "workhive_table": "logbook",
            "status":         status,
            "sync_payload":   {"description": f"Update {i+1}", "status": status},
            "sync_status":    "active",
        }
        import_raw_rows(client, [row])
        log(f"    upsert {i+1}/5: status={status}")

    # Verify final state
    rows = (
        client.table("external_sync")
        .select("external_id, status")
        .eq("system_type", ds.cmms_type)
        .eq("external_id", test_ext_id)
        .eq("entity_type", "work_order")
        .limit(1)
        .execute()
        .data or []
    )
    row = rows[0] if rows else None
    if not row:
        return _fail(name, f"{test_ext_id} not found in external_sync after 5 upserts")

    if row["status"] != "Closed":
        return _fail(name, f"Final status is '{row['status']}', expected 'Closed' -- ordering wrong")

    # Cleanup
    client.table("external_sync").delete().eq("external_id", test_ext_id).execute()
    return _pass(name, f"5 updates applied in order; final status=Closed (upsert resolves correctly)")


# ---------------------------------------------------------------------------
# Test 4 -- No drift: 30 events processed, external_sync count matches
# ---------------------------------------------------------------------------

def test_tier3_no_drift(syncer, client, ds, log):
    """Send 30 events; process all work_order events; verify no orphans or phantom rows."""
    name = "tier3_no_drift"
    _reset_logs(syncer.base_url)
    cleanup(client, ds.cmms_type)

    # Send 30 mixed events to local mock
    from seeders.cmms_webhook import generate_mixed_batch
    events = generate_mixed_batch(ds, count=30)
    log(f"  [{name}] sending {len(events)} mixed events to mock target...")
    sent_ok = 0
    for evt in events:
        code, _ = _send(LOCAL_MOCK_TARGET, evt)
        if code == 200:
            sent_ok += 1

    if sent_ok < len(events):
        return _fail(name, f"Only {sent_ok}/{len(events)} events delivered to mock")

    # Process all work_order events: normalize and import
    log_entries = _webhook_log(syncer.base_url, n=60)
    wo_events   = [e for e in log_entries
                   if e.get("event") in ("work_order.created", "work_order.updated",
                                         "work_order.completed")]

    rows = []
    for e in wo_events:
        row = _normalize_event_to_row(e["payload"], ds.cmms_type)
        if row and not _validate_row(row):
            rows.append(row)

    log(f"  [{name}] importing {len(rows)} work_order rows from {len(wo_events)} events...")
    upserted = 0
    if rows:
        import_result = import_raw_rows(client, rows)
        upserted = import_result.get("upserted", 0)
        if import_result.get("failed", 0) > 0:
            return _fail(name,
                f"import_raw_rows had {import_result['failed']} failures: "
                + str(import_result.get("errors", [])[:1]))

    # Count unique external_ids expected (events may repeat same WO -- upsert deduplicates)
    unique_ids = {r["external_id"] for r in rows}
    db_count   = count_in_db(client, ds.cmms_type, "work_order")

    if upserted == 0 and len(rows) > 0:
        return _fail(name,
            f"import_raw_rows upserted 0 of {len(rows)} rows -- check DB connection or constraints")

    if db_count != len(unique_ids):
        return _fail(name,
            f"Drift detected: {len(unique_ids)} unique WOs in events, "
            f"{db_count} rows in external_sync")

    return _pass(name,
        f"{sent_ok} events sent, {len(wo_events)} work_order events, "
        f"{len(unique_ids)} unique IDs, {db_count} DB rows -- no drift")


# ---------------------------------------------------------------------------
# Test 5 -- Signature: signed events accepted, unsigned rejected
# ---------------------------------------------------------------------------

def test_tier3_signature(syncer, client, ds, log):
    """Signed event -> 200. Unsigned event -> 401 from verified endpoint."""
    name = "tier3_signature"

    evt = generate_event(ds, "work_order.created", index=0)
    if not evt:
        return _skip(name, "No work_order.created event for signature test")

    # Test 1: unsigned -> must be rejected
    log(f"  [{name}] sending unsigned event to verified endpoint...")
    code_unsigned, body_unsigned = _send(VERIFIED_MOCK_TARGET, evt, sign=False)
    if code_unsigned != 401:
        return _fail(name, f"Unsigned event returned {code_unsigned}, expected 401")

    # Test 2: signed with correct secret -> must be accepted
    log(f"  [{name}] sending HMAC-signed event...")
    code_signed, body_signed = _send(VERIFIED_MOCK_TARGET, evt, sign=True)
    if code_signed != 200:
        return _fail(name, f"Signed event returned {code_signed}, expected 200 "
                           f"(body={body_signed})")

    # Test 3: signed with WRONG secret -> must be rejected
    log(f"  [{name}] sending event signed with wrong secret...")
    body_str = json.dumps(evt)
    ts  = str(int(time.time()))
    bad_sig = hmac.new(
        b"wrong-secret",
        f"{ts}.{body_str}".encode(),
        hashlib.sha256,
    ).hexdigest()
    headers = {
        "Content-Type":      "application/json",
        "X-CMMS-Signature":  f"sha256={bad_sig}",
        "X-CMMS-Timestamp":  ts,
    }
    resp = _req.post(VERIFIED_MOCK_TARGET, data=body_str, headers=headers, timeout=10)
    if resp.status_code != 401:
        return _fail(name, f"Wrong-secret event returned {resp.status_code}, expected 401")

    return _pass(name,
        f"unsigned=401, wrong_secret=401, correct_secret=200 -- "
        f"HMAC gate works correctly")


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

TESTS = [
    test_tier3_scenario_a,
    test_tier3_scenario_b,
    test_tier3_ordering,
    test_tier3_no_drift,
    test_tier3_signature,
]


def run_all(client, ds, log, base_url=MOCK_BASE_URL) -> dict:
    """Run all Tier 3 tests. Returns {passed, failed, skipped, results}."""
    syncer = CMMSSyncer(ds.cmms_type, base_url=base_url)

    reachable, err = syncer.is_reachable()
    if not reachable:
        msg = f"Server unreachable: {err}"
        log(f"[Tier3] SKIP ALL -- {msg}")
        return {
            "passed": 0, "failed": 0, "skipped": len(TESTS), "total": len(TESTS),
            "summary": f"SKIP ALL -- {msg}",
            "results": [{"name": t.__name__, "status": "SKIP", "detail": msg} for t in TESTS],
        }

    results = []
    for test_fn in TESTS:
        test_name = test_fn.__name__
        log(f"\n[Tier3] Running {test_name}...")
        try:
            result = test_fn(syncer, client, ds, log)
        except Exception as e:
            result = {"name": test_name, "status": "ERROR", "detail": str(e)}
        results.append(result)
        log(f"  => {result['status']}: {result['detail']}")

    try:
        cleanup(client, ds.cmms_type)
        _reset_logs(base_url)
    except Exception:
        pass

    passed  = sum(1 for r in results if r["status"] == "PASS")
    failed  = sum(1 for r in results if r["status"] in ("FAIL", "ERROR"))
    skipped = sum(1 for r in results if r["status"] == "SKIP")
    summary = f"{passed} PASS / {failed} FAIL / {skipped} SKIP of {len(results)} tests"
    log(f"\n[Tier3] {summary}")

    return {
        "passed": passed, "failed": failed, "skipped": skipped,
        "total": len(results), "summary": summary, "results": results,
    }
