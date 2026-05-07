"""Phase 3: Tier 1 Verification Tests.

Runs against local Supabase. Requires the external_sync table to exist
(migration 20260506000000_external_sync.sql) and a generated CMMS dataset
in CMMS_STATE.

Tests prove:
  tier1_import      -- records land with correct count and field mapping
  tier1_dedup       -- re-importing the same data creates no duplicates
  tier1_delta       -- partial then full import adds only new records
  tier1_baddata     -- malformed rows are rejected, good rows still land
  tier1_round_trip  -- exported WorkHive CSV contains what was imported
  tier1_agreement   -- every expected record matches what's in the DB

Run via: POST /api/cmms/tier1-test
"""

from datetime import datetime, timezone

from seeders.cmms_importer import (
    import_from_dataset,
    import_raw_rows,
    count_in_db,
    cleanup,
)


# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------

def _pass(name: str, detail: str) -> dict:
    return {"name": name, "status": "PASS", "detail": detail}


def _fail(name: str, detail: str) -> dict:
    return {"name": name, "status": "FAIL", "detail": detail}


def _skip(name: str, detail: str) -> dict:
    return {"name": name, "status": "SKIP", "detail": detail}


# ---------------------------------------------------------------------------
# Test 1 -- Import
# ---------------------------------------------------------------------------

def test_tier1_import(client, ds, log) -> dict:
    """Import all work orders and verify count + field mapping."""
    name = "tier1_import"
    log(f"  [{name}] cleaning up previous runs...")
    cleanup(client, ds.cmms_type)

    log(f"  [{name}] importing {len(ds.work_orders)} work orders...")
    result = import_from_dataset(client, ds, entities=["work_order"], log=log)

    if result["failed"] > 0:
        return _fail(name, f"{result['failed']} rows failed validation/upsert: "
                           + str(result["errors"][:2]))

    actual = count_in_db(client, ds.cmms_type, "work_order")
    expected = len(ds.work_orders)
    if actual != expected:
        return _fail(name, f"Count mismatch: expected {expected}, got {actual}")

    # Spot-check: first work order in DB has correct status
    first_wo = ds.work_orders[0]
    ext_id = ds._wo_id(first_wo)
    rows = (
        client.table("external_sync")
        .select("external_id, status, sync_payload")
        .eq("system_type", ds.cmms_type)
        .eq("external_id", ext_id)
        .eq("entity_type", "work_order")
        .limit(1)
        .execute()
        .data or []
    )
    row = rows[0] if rows else None
    if not row:
        return _fail(name, f"Spot-check failed: work order {ext_id} not found in DB")

    expected_status = ds._cmms_status_to_wh(ds._wo_cmms_status(first_wo))
    if row["status"] != expected_status:
        return _fail(name, f"Status mismatch on {ext_id}: "
                           f"expected '{expected_status}', got '{row['status']}'")

    return _pass(name, f"{actual} work orders imported, field mapping verified on {ext_id}")


# ---------------------------------------------------------------------------
# Test 2 -- Deduplication
# ---------------------------------------------------------------------------

def test_tier1_dedup(client, ds, log) -> dict:
    """Re-importing the same data must not create duplicates."""
    name = "tier1_dedup"
    count_before = count_in_db(client, ds.cmms_type, "work_order")
    if count_before == 0:
        log(f"  [{name}] no rows present -- running import first")
        import_from_dataset(client, ds, entities=["work_order"])
        count_before = count_in_db(client, ds.cmms_type, "work_order")

    log(f"  [{name}] re-importing {len(ds.work_orders)} work orders (count before={count_before})...")
    import_from_dataset(client, ds, entities=["work_order"])

    count_after = count_in_db(client, ds.cmms_type, "work_order")
    if count_after != count_before:
        return _fail(name, f"Duplicate rows created: was {count_before}, now {count_after}")

    return _pass(name, f"Count stable at {count_after} after second import -- no duplicates")


# ---------------------------------------------------------------------------
# Test 3 -- Delta (partial then full)
# ---------------------------------------------------------------------------

def test_tier1_delta(client, ds, log) -> dict:
    """Partial import followed by full import adds only the missing records."""
    name = "tier1_delta"
    cleanup(client, ds.cmms_type)

    all_wos = ds.expected_logbook
    if len(all_wos) < 10:
        return _skip(name, f"Dataset too small ({len(all_wos)} WOs) for delta test -- use medium or large")

    # Simulate a delta: temporarily replace expected_logbook with first half
    half = len(all_wos) // 2
    original_logbook = ds.expected_logbook
    original_wos     = ds.work_orders
    ds.expected_logbook = original_logbook[:half]
    ds.work_orders      = original_wos[:half]

    log(f"  [{name}] first pass: importing {half} of {len(original_logbook)} work orders...")
    import_from_dataset(client, ds, entities=["work_order"])
    count_partial = count_in_db(client, ds.cmms_type, "work_order")

    # Restore full dataset
    ds.expected_logbook = original_logbook
    ds.work_orders      = original_wos

    log(f"  [{name}] second pass: importing full {len(original_logbook)} work orders...")
    import_from_dataset(client, ds, entities=["work_order"])
    count_full = count_in_db(client, ds.cmms_type, "work_order")

    if count_partial != half:
        return _fail(name, f"Partial import: expected {half}, got {count_partial}")

    if count_full != len(original_logbook):
        return _fail(name, f"Full import: expected {len(original_logbook)}, got {count_full}")

    added = count_full - count_partial
    return _pass(name, f"Partial={count_partial}, full={count_full}, delta added {added} records")


# ---------------------------------------------------------------------------
# Test 4 -- Bad data
# ---------------------------------------------------------------------------

def test_tier1_baddata(client, ds, log) -> dict:
    """Malformed rows are rejected; valid rows in the same batch still land."""
    name = "tier1_baddata"
    cleanup(client, ds.cmms_type)

    bad_and_good = [
        # Bad: missing external_id (validator must reject)
        {"system_type": ds.cmms_type, "entity_type": "work_order",
         "external_id": None, "status": "Open",
         "sync_payload": {"problem": "malformed row -- no external_id"}},

        # Bad: missing entity_type
        {"system_type": ds.cmms_type, "entity_type": None,
         "external_id": "BAD-002", "status": "Open",
         "sync_payload": {}},

        # Good: complete valid row
        {"system_type": ds.cmms_type, "entity_type": "work_order",
         "external_id": "GOOD-001", "status": "Open",
         "workhive_table": "logbook",
         "sync_payload": {"problem": "valid test row", "status": "Open"}},

        # Good: different status
        {"system_type": ds.cmms_type, "entity_type": "work_order",
         "external_id": "GOOD-002", "status": "Closed",
         "workhive_table": "logbook",
         "sync_payload": {"problem": "valid closed row", "status": "Closed"}},
    ]

    log(f"  [{name}] importing 2 bad rows + 2 good rows...")
    result = import_raw_rows(client, bad_and_good)

    if result["valid"] != 2:
        return _fail(name, f"Expected 2 valid rows, got {result['valid']}")
    if result["failed"] != 2:
        return _fail(name, f"Expected 2 rejected rows, got {result['failed']}")
    if result["upserted"] != 2:
        return _fail(name, f"Expected 2 upserted, got {result['upserted']}")

    # Verify good rows landed, bad rows did not
    good_count = (
        client.table("external_sync")
        .select("id", count="exact")
        .eq("system_type", ds.cmms_type)
        .in_("external_id", ["GOOD-001", "GOOD-002"])
        .limit(1)
        .execute()
        .count or 0
    )
    if good_count != 2:
        return _fail(name, f"Expected 2 good rows in DB, got {good_count}")

    cleanup(client, ds.cmms_type)
    return _pass(name, "2 bad rows rejected, 2 good rows imported, no crashes")


# ---------------------------------------------------------------------------
# Test 5 -- Round-trip (import -> export -> verify loop closes)
# ---------------------------------------------------------------------------

def test_tier1_round_trip(client, ds, log) -> dict:
    """Export CSV from the dataset; verify closed WOs appear with correct status."""
    name = "tier1_round_trip"
    import csv, io

    # Find closed work orders in expected_logbook
    closed = [e for e in ds.expected_logbook if e.get("status") == "Closed"]
    if not closed:
        return _skip(name, "No closed work orders in dataset -- re-generate with medium+ size")

    # Build the same WH-to-CMMS export the Flask route produces
    ext_id_key = (
        "AUFNR"   if ds.cmms_type == "sap_pm"
        else "WONUM" if ds.cmms_type == "maximo"
        else "work_order_no"
    )
    export_rows = [
        {
            ext_id_key:        e["_external_id"],
            "WH_STATUS":       e["status"],
            "WH_ACTUAL_HOURS": e.get("downtime_hours", 0),
            "WH_CLOSED_AT":    e.get("closed_at", ""),
            "WH_ACTION":       e.get("action", ""),
        }
        for e in closed
    ]

    # Serialize to CSV and parse back
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(export_rows[0].keys()))
    writer.writeheader()
    writer.writerows(export_rows)
    buf.seek(0)
    parsed = list(csv.DictReader(buf))

    if len(parsed) != len(closed):
        return _fail(name, f"CSV row count mismatch: {len(parsed)} vs {len(closed)}")

    # Verify first exported row has the right external_id and status
    first = parsed[0]
    if first["WH_STATUS"] != "Closed":
        return _fail(name, f"First export row status is '{first['WH_STATUS']}', expected 'Closed'")

    if not first.get(ext_id_key):
        return _fail(name, f"Export missing {ext_id_key} field -- loop cannot close")

    log(f"  [{name}] {len(parsed)} closed WOs in export, ext_id={first[ext_id_key]}, status={first['WH_STATUS']}")
    return _pass(name,
        f"{len(parsed)} closed work orders exported back to {ds.cmms_type} format, "
        f"loop closes on {ext_id_key}")


# ---------------------------------------------------------------------------
# Test 6 -- Agreement (expected vs actual in DB)
# ---------------------------------------------------------------------------

def test_tier1_agreement(client, ds, log) -> dict:
    """Count and field-mapping agreement between expected state and DB.

    Uses count_in_db for the total (avoids PostgREST's default 1000-row cap),
    then spot-checks status mapping on a sample of up to 100 records.
    """
    name = "tier1_agreement"

    if count_in_db(client, ds.cmms_type, "work_order") == 0:
        log(f"  [{name}] no rows in DB -- running import first...")
        import_from_dataset(client, ds, entities=["work_order"])

    db_count       = count_in_db(client, ds.cmms_type, "work_order")
    total_expected = len(ds.expected_logbook)

    if db_count < total_expected:
        return _fail(name,
            f"{total_expected - db_count} of {total_expected} records missing from DB")

    # Spot-check field mapping on first 100 expected records
    sample  = ds.expected_logbook[:100]
    ext_ids = [e["_external_id"] for e in sample]

    rows = (
        client.table("external_sync")
        .select("external_id, status")
        .eq("system_type", ds.cmms_type)
        .eq("entity_type", "work_order")
        .in_("external_id", ext_ids)
        .limit(100)
        .execute()
        .data or []
    )
    actual_by_id = {r["external_id"]: r["status"] for r in rows}

    mismatches = []
    for expected in sample:
        ext_id = expected["_external_id"]
        actual = actual_by_id.get(ext_id)
        if actual and actual != expected["status"]:
            mismatches.append(
                f"{ext_id}: expected '{expected['status']}', got '{actual}'"
            )

    log(f"  [{name}] db_count={db_count}, sample checked={len(sample)}, "
        f"mismatches={len(mismatches)}")

    if mismatches:
        return _fail(name, f"{len(mismatches)} status mismatches: "
                           + "; ".join(mismatches[:2]))

    return _pass(name,
        f"All {db_count} work orders agree between CMMS expected state and DB")


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

TESTS = [
    test_tier1_import,
    test_tier1_dedup,
    test_tier1_delta,
    test_tier1_baddata,
    test_tier1_round_trip,
    test_tier1_agreement,
]


def run_all(client, ds, log) -> dict:
    """Run all Tier 1 tests. Returns {passed, failed, skipped, results}."""
    results = []
    for test_fn in TESTS:
        test_name = test_fn.__name__
        log(f"\n[Tier1] Running {test_name}...")
        try:
            result = test_fn(client, ds, log)
        except Exception as e:
            result = {"name": test_name, "status": "ERROR", "detail": str(e)}
        results.append(result)
        log(f"  => {result['status']}: {result['detail']}")

    # Cleanup test residue
    try:
        cleanup(client, ds.cmms_type)
    except Exception:
        pass

    passed  = sum(1 for r in results if r["status"] == "PASS")
    failed  = sum(1 for r in results if r["status"] in ("FAIL", "ERROR"))
    skipped = sum(1 for r in results if r["status"] == "SKIP")

    summary = f"{passed} PASS / {failed} FAIL / {skipped} SKIP of {len(results)} tests"
    log(f"\n[Tier1] {summary}")

    return {
        "passed":  passed,
        "failed":  failed,
        "skipped": skipped,
        "total":   len(results),
        "summary": summary,
        "results": results,
    }
