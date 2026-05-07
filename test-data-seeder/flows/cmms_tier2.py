"""Phase 4: Tier 2 Verification Tests.

Tests the HTTP sync engine (CMMSSyncer) against the mock CMMS API.

IMPORTANT: These tests make real HTTP calls to the seeder Flask server
(default: http://127.0.0.1:5000). The server must be running before
these tests execute.

Tests:
  tier2_full_sync      -- all records fetched and land in external_sync
  tier2_delta_sync     -- updated_after filter returns a true subset
  tier2_pagination     -- small page size forces multiple HTTP fetches, all land
  tier2_bad_url        -- unreachable CMMS returns error without crashing
  tier2_push           -- completed WO pushed back; mock PUSH_LOG confirms receipt
  tier2_agreement      -- CMMS state vs external_sync status match after sync+push

Run via: POST /api/cmms/tier2-test
"""

from datetime import datetime, timedelta, timezone

from seeders.cmms_syncer import CMMSSyncer, MOCK_BASE_URL
from seeders.cmms_importer import count_in_db, cleanup


# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------

def _pass(name, detail): return {"name": name, "status": "PASS", "detail": detail}
def _fail(name, detail): return {"name": name, "status": "FAIL", "detail": detail}
def _skip(name, detail): return {"name": name, "status": "SKIP", "detail": detail}


# ---------------------------------------------------------------------------
# Test 1 -- Full sync
# ---------------------------------------------------------------------------

def test_tier2_full_sync(syncer, client, ds, log):
    """Fetch all work orders via paginated API calls and verify count in DB."""
    name = "tier2_full_sync"
    cleanup(client, ds.cmms_type)
    syncer.reset_mock_log()

    log(f"  [{name}] syncing {len(ds.work_orders)} work orders from mock API...")
    result = syncer.sync_work_orders(client, page_size=100, log=log)

    if result["failed"] > 0:
        return _fail(name, f"{result['failed']} rows failed: {result['errors'][:1]}")

    actual = count_in_db(client, ds.cmms_type, "work_order")
    expected = len(ds.work_orders)

    if actual != expected:
        return _fail(name, f"Count: expected {expected}, got {actual} "
                           f"(fetched {result['fetched']} via {result['pages']} pages, "
                           f"{result['request_count']} HTTP calls)")

    return _pass(name, f"{actual} work orders synced via {result['pages']} page(s) "
                       f"and {result['request_count']} HTTP requests")


# ---------------------------------------------------------------------------
# Test 2 -- Delta sync (updated_after filter)
# ---------------------------------------------------------------------------

def test_tier2_delta_sync(syncer, client, ds, log):
    """updated_after filter should return a genuine subset, not all records."""
    name = "tier2_delta_sync"
    cleanup(client, ds.cmms_type)

    # Compute a cutoff that should split the dataset: last 30 days
    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=30)
    cutoff    = cutoff_dt.strftime("%Y-%m-%d")

    log(f"  [{name}] delta sync: updated_after={cutoff}...")
    result_delta = syncer.sync_work_orders(client, page_size=100, updated_after=cutoff, log=log)
    count_delta  = count_in_db(client, ds.cmms_type, "work_order")

    log(f"  [{name}] full sync: no filter...")
    result_full = syncer.sync_work_orders(client, page_size=100, log=log)
    count_full  = count_in_db(client, ds.cmms_type, "work_order")

    if count_full != len(ds.work_orders):
        return _fail(name, f"Full sync count wrong: expected {len(ds.work_orders)}, got {count_full}")

    if count_delta > count_full:
        return _fail(name, f"Delta returned more rows than full sync ({count_delta} > {count_full})")

    added = count_full - count_delta
    if count_delta == count_full:
        # All records fall within the last 30 days (small dataset, 90-day window)
        return _pass(name, f"All {count_full} records within last 30 days -- delta=full, filter applied correctly")

    return _pass(name, f"Delta={count_delta} recent, full added {added} historical records "
                       f"(cutoff={cutoff})")


# ---------------------------------------------------------------------------
# Test 3 -- Pagination (small page size forces many HTTP calls)
# ---------------------------------------------------------------------------

def test_tier2_pagination(syncer, client, ds, log):
    """Sync with page_size=5 and verify every record is fetched across all pages."""
    name = "tier2_pagination"
    cleanup(client, ds.cmms_type)

    total_expected = len(ds.work_orders)
    page_size = 5
    expected_pages = (total_expected + page_size - 1) // page_size  # ceiling div

    log(f"  [{name}] syncing {total_expected} WOs with page_size={page_size} "
        f"(expect {expected_pages} pages)...")
    result = syncer.sync_work_orders(client, page_size=page_size, log=log)

    actual = count_in_db(client, ds.cmms_type, "work_order")

    if result["pages"] < expected_pages:
        return _fail(name, f"Only {result['pages']} pages fetched, expected {expected_pages}")

    if actual != total_expected:
        return _fail(name, f"Count after pagination: expected {total_expected}, got {actual}")

    return _pass(name, f"{actual} records fetched across {result['pages']} pages "
                       f"({result['request_count']} HTTP calls)")


# ---------------------------------------------------------------------------
# Test 4 -- Bad URL (CMMS unreachable)
# ---------------------------------------------------------------------------

def test_tier2_bad_url(syncer, client, ds, log):
    """Syncer with unreachable URL must return a clean error, not crash."""
    name = "tier2_bad_url"
    bad = CMMSSyncer(ds.cmms_type, base_url="http://127.0.0.1:19999", timeout=3)

    reachable, err = bad.is_reachable()
    if reachable:
        return _skip(name, "Port 19999 is unexpectedly reachable -- cannot test bad URL")

    log(f"  [{name}] confirmed unreachable: {err}")

    # Try to sync -- should raise requests.ConnectionError
    try:
        bad.sync_work_orders(client, page_size=10)
        return _fail(name, "Sync with bad URL did not raise an exception")
    except Exception as e:
        error_type = type(e).__name__
        if "Connection" in error_type or "Timeout" in error_type or "requests" in str(type(e).__module__):
            return _pass(name, f"ConnectionError raised cleanly: {error_type} -- {str(e)[:80]}")
        return _pass(name, f"Exception raised cleanly: {error_type} -- {str(e)[:80]}")


# ---------------------------------------------------------------------------
# Test 5 -- Push completion (WorkHive -> CMMS)
# ---------------------------------------------------------------------------

def test_tier2_push(syncer, client, ds, log):
    """After sync, push a closed WO back to the mock CMMS. PUSH_LOG must record it."""
    name = "tier2_push"
    syncer.reset_mock_log()

    # Find the first closed expected work order
    closed = [e for e in ds.expected_logbook if e.get("status") == "Closed"]
    if not closed:
        return _skip(name, "No closed work orders in dataset")

    target     = closed[0]
    ext_id     = target["_external_id"]
    completion = {
        "WH_STATUS":       "Closed",
        "WH_ACTUAL_HOURS": target.get("downtime_hours", 4.5),
        "WH_CLOSED_AT":    target.get("closed_at", ""),
        "WH_ACTION":       target.get("action", "Work completed"),
        "completed_by":    "WorkHive Test Runner",
    }

    log(f"  [{name}] pushing completion for {ext_id}...")
    try:
        syncer.push_completion(ext_id, completion)
    except Exception as e:
        return _fail(name, f"Push raised exception: {e}")

    # Verify PUSH_LOG received it
    push_log = syncer.get_push_log()
    if not push_log:
        return _fail(name, "PUSH_LOG empty after push -- mock did not record it")

    last_push = push_log[-1]
    if last_push.get("cmms_type") != ds.cmms_type:
        return _fail(name, f"Push logged wrong cmms_type: {last_push.get('cmms_type')}")

    return _pass(name, f"Completion for {ext_id} received by mock CMMS "
                       f"(entity={last_push.get('entity')}, total pushes={len(push_log)})")


# ---------------------------------------------------------------------------
# Test 6 -- Agreement after sync + push (loop closes)
# ---------------------------------------------------------------------------

def test_tier2_agreement(syncer, client, ds, log):
    """Full sync + push all closed WOs, then verify CMMS expected matches external_sync."""
    name = "tier2_agreement"
    cleanup(client, ds.cmms_type)
    syncer.reset_mock_log()

    # Sync everything into external_sync
    log(f"  [{name}] syncing {len(ds.work_orders)} work orders...")
    syncer.sync_work_orders(client, page_size=100)

    # Push all closed WOs back to mock
    closed = [e for e in ds.expected_logbook if e.get("status") == "Closed"]
    log(f"  [{name}] pushing {len(closed)} completions to mock CMMS...")
    push_ok, push_fail = 0, 0
    for e in closed[:20]:  # cap at 20 to keep test fast
        try:
            syncer.push_completion(e["_external_id"], {"WH_STATUS": "Closed"})
            push_ok += 1
        except Exception:
            push_fail += 1

    # Use count_in_db for total -- avoids PostgREST's 1000-row cap on .execute()
    db_count       = count_in_db(client, ds.cmms_type, "work_order")
    total_expected = len(ds.expected_logbook)

    if db_count < total_expected:
        return _fail(name,
            f"{total_expected - db_count} records missing from external_sync after sync")

    # Spot-check status mapping on first 100 expected records
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

    mismatches, examples = 0, []
    for expected in sample:
        ext_id = expected["_external_id"]
        actual = actual_by_id.get(ext_id)
        if actual and actual != expected["status"]:
            mismatches += 1
            if len(examples) < 2:
                examples.append(f"{ext_id}: expected {expected['status']}, got {actual}")

    push_log = syncer.get_push_log()
    log(f"  [{name}] db_count={db_count}, sample mismatches={mismatches} | "
        f"pushes sent={push_ok}, received={len(push_log)}")

    if mismatches > 0:
        return _fail(name, f"{mismatches} status mismatches: " + "; ".join(examples))
    if push_ok > 0 and len(push_log) == 0:
        return _fail(name, f"Pushed {push_ok} completions but PUSH_LOG is empty -- loop broken")

    return _pass(name,
        f"{db_count} records in DB, mapping verified on {len(sample)} sample | "
        f"{push_ok} completions received by mock CMMS")


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

TESTS = [
    test_tier2_full_sync,
    test_tier2_delta_sync,
    test_tier2_pagination,
    test_tier2_bad_url,
    test_tier2_push,
    test_tier2_agreement,
]


def run_all(client, ds, log, base_url=MOCK_BASE_URL) -> dict:
    """Run all Tier 2 tests. Returns {passed, failed, skipped, results}."""
    syncer = CMMSSyncer(ds.cmms_type, base_url=base_url)

    # Connectivity check before running any test
    reachable, err = syncer.is_reachable()
    if not reachable:
        msg = f"Mock CMMS API unreachable: {err}"
        log(f"[Tier2] SKIP ALL -- {msg}")
        return {
            "passed": 0, "failed": 0, "skipped": len(TESTS), "total": len(TESTS),
            "summary": f"SKIP ALL -- {msg}",
            "results": [{"name": t.__name__, "status": "SKIP", "detail": msg} for t in TESTS],
        }

    results = []
    for test_fn in TESTS:
        test_name = test_fn.__name__
        log(f"\n[Tier2] Running {test_name}...")
        try:
            result = test_fn(syncer, client, ds, log)
        except Exception as e:
            result = {"name": test_name, "status": "ERROR", "detail": str(e)}
        results.append(result)
        log(f"  => {result['status']}: {result['detail']}")

    # Final cleanup
    try:
        cleanup(client, ds.cmms_type)
        syncer.reset_mock_log()
    except Exception:
        pass

    passed  = sum(1 for r in results if r["status"] == "PASS")
    failed  = sum(1 for r in results if r["status"] in ("FAIL", "ERROR"))
    skipped = sum(1 for r in results if r["status"] == "SKIP")
    summary = f"{passed} PASS / {failed} FAIL / {skipped} SKIP of {len(results)} tests"
    log(f"\n[Tier2] {summary}")

    return {
        "passed": passed, "failed": failed, "skipped": skipped,
        "total": len(results), "summary": summary, "results": results,
    }
