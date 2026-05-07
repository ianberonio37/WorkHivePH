"""CMMS Importer -- Phase 3: Reference Import Implementation.

Normalizes a CMMSDataset into WorkHive's external_sync table.
This is both the seeder's test harness AND the reference implementation
for the WorkHive Tier 1 import wizard.

When the WorkHive import wizard is built, it should produce the same
external_sync rows that this function produces for the same input data.
"""

from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_row(row: dict) -> str | None:
    """Return error string if invalid, None if the row is safe to upsert."""
    if not row.get("external_id"):
        return "missing external_id"
    if not row.get("system_type"):
        return "missing system_type"
    if not row.get("entity_type"):
        return "missing entity_type"
    return None


# ---------------------------------------------------------------------------
# Normalization helpers (CMMS-format -> external_sync row)
# ---------------------------------------------------------------------------

def _row_from_expected(expected: dict, entity_type: str, workhive_table: str,
                       hive_id) -> dict:
    """Build an external_sync row from an already-normalized expected record."""
    payload = {k: v for k, v in expected.items() if not k.startswith("_")}
    return {
        "hive_id":       hive_id,
        "system_type":   expected["_system_type"],
        "external_id":   expected["_external_id"],
        "entity_type":   entity_type,
        "workhive_table": workhive_table,
        "status":        expected.get("status") or expected.get("is_overdue") or None,
        "sync_payload":  payload,
        "last_synced_at": datetime.now(timezone.utc).isoformat(),
        "sync_status":   "active",
    }


# ---------------------------------------------------------------------------
# Main import function
# ---------------------------------------------------------------------------

ENTITY_CONFIG = {
    "work_order":  ("expected_logbook",    "logbook"),
    "asset":       ("expected_assets",     "assets"),
    "pm_schedule": ("expected_pm",         "pm_assets"),
    "inventory":   ("expected_inventory",  "inventory_items"),
}


def import_from_dataset(
    client,
    ds,
    hive_id=None,
    entities: list[str] | None = None,
    chunk: int = 200,
    log=None,
) -> dict:
    """Import a CMMSDataset into external_sync.

    Args:
        client:   Supabase Python client.
        ds:       CMMSDataset (must be generated).
        hive_id:  UUID string of the target hive (None for test/no-hive runs).
        entities: Which entity types to import. Defaults to all four.
        chunk:    Batch size for upserts.
        log:      Optional callable(str) for progress messages.

    Returns:
        {
          "total":    total rows processed,
          "valid":    rows passed validation,
          "failed":   rows rejected by validation,
          "upserted": rows actually sent to Supabase,
          "errors":   list of {external_id, error} for failed rows,
          "by_entity": {entity_type: count},
        }
    """
    if not ds._generated:
        ds.generate()

    entities = entities or list(ENTITY_CONFIG.keys())

    all_valid:  list[dict] = []
    all_failed: list[dict] = []
    by_entity:  dict[str, int] = {}

    for entity_type in entities:
        attr, workhive_table = ENTITY_CONFIG[entity_type]
        source_rows = getattr(ds, attr, [])

        valid_for_entity = 0
        for expected in source_rows:
            row = _row_from_expected(expected, entity_type, workhive_table, hive_id)
            err = _validate_row(row)
            if err:
                all_failed.append({"external_id": row.get("external_id"), "error": err})
            else:
                all_valid.append(row)
                valid_for_entity += 1

        by_entity[entity_type] = valid_for_entity
        if log:
            log(f"  {entity_type}: {valid_for_entity} rows prepared")

    # Deduplicate by unique key before batch insert.
    # A single upsert statement cannot target the same row twice (PostgreSQL 21000).
    # This happens when e.g. work_order.created + work_order.completed arrive
    # for the same AUFNR in one batch -- keep the last occurrence (latest state wins).
    deduped: dict = {}
    for row in all_valid:
        key = (row.get("system_type"), row.get("external_id"), row.get("entity_type"))
        deduped[key] = row
    all_valid = list(deduped.values())

    # Batch upsert valid rows
    upserted = 0
    upsert_errors = []
    for i in range(0, len(all_valid), chunk):
        batch = all_valid[i : i + chunk]
        try:
            client.table("external_sync").upsert(
                batch,
                on_conflict="system_type,external_id,entity_type",
            ).execute()
            upserted += len(batch)
        except Exception as e:
            # Batch failed -- retry one-by-one to isolate bad rows
            for row in batch:
                try:
                    client.table("external_sync").upsert(
                        [row],
                        on_conflict="system_type,external_id,entity_type",
                    ).execute()
                    upserted += 1
                except Exception as row_e:
                    upsert_errors.append({
                        "external_id": row.get("external_id"),
                        "error":       str(row_e),
                    })

    total_failed = len(all_failed) + len(upsert_errors)
    if log:
        log(f"  Upserted {upserted} rows, {total_failed} failed")

    return {
        "total":     len(all_valid) + len(all_failed),
        "valid":     len(all_valid),
        "failed":    total_failed,
        "upserted":  upserted,
        "errors":    all_failed + upsert_errors,
        "by_entity": by_entity,
    }


def import_raw_rows(
    client,
    rows: list[dict],
    chunk: int = 200,
) -> dict:
    """Import pre-built external_sync rows (for bad-data tests).

    Validates each row and upserts the valid ones. Returns the same
    result shape as import_from_dataset.
    """
    valid, failed = [], []
    for row in rows:
        err = _validate_row(row)
        if err:
            failed.append({"external_id": row.get("external_id"), "error": err})
        else:
            valid.append(row)

    # Deduplicate to avoid PostgreSQL 21000 (same row targeted twice in one statement)
    deduped: dict = {}
    for row in valid:
        key = (row.get("system_type"), row.get("external_id"), row.get("entity_type"))
        deduped[key] = row
    valid = list(deduped.values())

    upserted = 0
    upsert_errors = []
    for i in range(0, len(valid), chunk):
        batch = valid[i : i + chunk]
        try:
            client.table("external_sync").upsert(
                batch,
                on_conflict="system_type,external_id,entity_type",
            ).execute()
            upserted += len(batch)
        except Exception as e:
            # Retry individually to isolate the bad row
            for row in batch:
                try:
                    client.table("external_sync").upsert(
                        [row],
                        on_conflict="system_type,external_id,entity_type",
                    ).execute()
                    upserted += 1
                except Exception as row_e:
                    upsert_errors.append({
                        "external_id": row.get("external_id"),
                        "error":       str(row_e),
                    })

    return {
        "total":    len(rows),
        "valid":    len(valid),
        "failed":   len(failed) + len(upsert_errors),
        "upserted": upserted,
        "errors":   failed + upsert_errors,
    }


def count_in_db(client, system_type: str, entity_type: str,
                hive_id=None) -> int:
    """Count external_sync rows for a given system_type + entity_type."""
    q = (
        client.table("external_sync")
        .select("id", count="exact")
        .eq("system_type", system_type)
        .eq("entity_type", entity_type)
        .limit(1)
    )
    if hive_id is not None:
        q = q.eq("hive_id", hive_id)
    else:
        q = q.is_("hive_id", "null")
    return q.execute().count or 0


def cleanup(client, system_type: str, hive_id=None):
    """Delete all external_sync rows for a given system_type (test teardown)."""
    q = client.table("external_sync").delete().eq("system_type", system_type)
    if hive_id is not None:
        q = q.eq("hive_id", hive_id)
    else:
        q = q.is_("hive_id", "null")
    q.execute()
