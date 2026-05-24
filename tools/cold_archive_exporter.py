"""
Cold Archive Exporter (Phase 6 of AGENTIC_RAG_ROADMAP.md, SCAFFOLDING)
======================================================================
Quarterly Parquet export of >18-month-old data per hive, uploaded to
Supabase Storage at supabase://archive-{hive_id}/{year}-Q{n}/{table}.parquet.

After verified upload + checksum, the archived rows are DELETED from the
hot Postgres tables to keep the warm path lean. The cold-archive-query
edge fn reads these Parquet files when the agentic-rag-loop Router
promotes a query to route='cold_archive'.

**STATUS: SCAFFOLDING ONLY.** Dry-run mode is the default. Production
runs require:
  - HIVE_IDS env var (or --hive-ids flag) listing hives to archive
  - --commit flag (otherwise dry-run prints what WOULD be exported)
  - DuckDB + pyarrow installed locally (this script imports them lazily)

Trigger: pg_cron quarterly (1st of Jan/Apr/Jul/Oct, 03:00 PHT). The cron
job calls a thin HTTP wrapper around this script — for now run manually:

  python tools/cold_archive_exporter.py --hive-ids <UUID> --quarter 2024-Q1 --commit

Free-tier note: Supabase Storage costs ~$0.021/GB/month. 1M logbook rows
≈ 100MB Parquet. Negligible at platform scale.
"""

from __future__ import annotations
import os
import sys
import argparse
from typing import List, Dict, Any

# Lazy imports — pyarrow + duckdb only needed when --commit is set
def _lazy_imports():
    try:
        import pyarrow  # noqa: F401
        import pyarrow.parquet  # noqa: F401
    except ImportError:
        print("FAIL: pyarrow required (pip install pyarrow). Skipping export.")
        sys.exit(2)
    try:
        from supabase import create_client  # noqa: F401
    except ImportError:
        print("FAIL: supabase-py required (pip install supabase). Skipping export.")
        sys.exit(2)


SUPPORTED_TABLES = ["logbook", "pm_completions", "unified_events", "voice_journal_entries"]
ARCHIVE_AGE_MONTHS = 18    # rows older than this become eligible for archive
BUCKET = "archive"


def quarter_to_range(quarter: str) -> tuple[str, str]:
    """Parse '2024-Q1' → ('2024-01-01', '2024-03-31')."""
    year, q = quarter.split("-Q")
    y = int(year)
    qn = int(q)
    starts = {1: ("01", "01"), 2: ("04", "01"), 3: ("07", "01"), 4: ("10", "01")}
    ends   = {1: ("03", "31"), 2: ("06", "30"), 3: ("09", "30"), 4: ("12", "31")}
    s = starts[qn]
    e = ends[qn]
    return f"{y}-{s[0]}-{s[1]}", f"{y}-{e[0]}-{e[1]}"


def export_table_for_hive(
    db, hive_id: str, table: str, q_from: str, q_to: str, commit: bool
) -> Dict[str, Any]:
    """Fetch rows from hot Postgres for this (hive, table, quarter) range
    and write a Parquet file to the archive bucket. Returns row count."""
    _lazy_imports()
    import pyarrow as pa
    import pyarrow.parquet as pq
    import io

    # Hive-scoped narrow select. Caller already verified table is in SUPPORTED.
    # Use created_at as the universal time column.
    res = (
        db.table(table)
        .select("*")
        .eq("hive_id", hive_id)
        .gte("created_at", f"{q_from}T00:00:00")
        .lte("created_at", f"{q_to}T23:59:59")
        .limit(100_000)   # safety cap per quarter per table
        .execute()
    )
    rows = res.data or []
    if not rows:
        return {"hive_id": hive_id, "table": table, "rows": 0, "skipped": True, "reason": "no rows in range"}

    # Convert to Arrow table, write Parquet to bytes
    pa_table = pa.Table.from_pylist(rows)
    buf = io.BytesIO()
    pq.write_table(pa_table, buf, compression="snappy")
    buf.seek(0)

    object_path = f"{hive_id}/{q_from[:4]}-Q{int((int(q_from[5:7]) - 1) / 3) + 1}/{table}.parquet"

    if not commit:
        return {"hive_id": hive_id, "table": table, "rows": len(rows), "object_path": object_path, "dry_run": True}

    # Upload to Supabase Storage
    db.storage.from_(BUCKET).upload(
        object_path, buf.getvalue(),
        {"contentType": "application/octet-stream", "upsert": "true"},
    )

    # NOTE: actual hot-table delete deferred — must be a separate explicit step
    # because deleting irrecoverable rows is the highest-risk operation in this
    # whole pipeline. The scaffolding does NOT auto-delete.
    return {
        "hive_id": hive_id, "table": table, "rows": len(rows),
        "object_path": object_path, "uploaded": True,
        "warn": "rows uploaded to archive but NOT deleted from hot table; review then delete manually.",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Cold Archive Exporter (Phase 6 of AGENTIC_RAG_ROADMAP.md)")
    ap.add_argument("--hive-ids", required=True, help="Comma-separated hive UUIDs to archive")
    ap.add_argument("--quarter", required=True, help="Quarter to archive, e.g. 2024-Q1")
    ap.add_argument("--tables", default=",".join(SUPPORTED_TABLES), help="Comma-separated tables (default: all supported)")
    ap.add_argument("--commit", action="store_true", help="Actually upload (default: dry-run)")
    args = ap.parse_args()

    q_from, q_to = quarter_to_range(args.quarter)
    print(f"Archive window: {q_from} to {q_to}")
    print(f"Commit mode: {'YES — uploads will occur' if args.commit else 'NO — dry run only'}")
    print()

    if args.commit:
        from supabase import create_client
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            print("FAIL: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in env.")
            return 2
        db = create_client(url, key)
    else:
        db = None

    hive_ids = [h.strip() for h in args.hive_ids.split(",") if h.strip()]
    tables   = [t.strip() for t in args.tables.split(",") if t.strip() in SUPPORTED_TABLES]
    summary: List[Dict[str, Any]] = []

    for hive_id in hive_ids:
        for table in tables:
            print(f"  - hive={hive_id[:8]}... table={table} ...", end=" ")
            try:
                if args.commit:
                    res = export_table_for_hive(db, hive_id, table, q_from, q_to, commit=True)
                else:
                    # Dry-run: report what would be exported without DB access
                    res = {"hive_id": hive_id, "table": table, "dry_run": True, "would_export_window": (q_from, q_to)}
                print(res)
                summary.append(res)
            except Exception as err:
                print(f"ERROR: {err}")
                summary.append({"hive_id": hive_id, "table": table, "error": str(err)})

    print()
    print(f"Done. {len(summary)} operations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
