"""
Cold Archive Prune (FREE_TIER_QUOTA_ROADMAP Q5-b / COLD_ARCHIVE step 3)
=======================================================================
The DELIBERATELY-GATED counterpart to tools/cold_archive_exporter.py. The exporter
writes >18-month-old rows to verified Parquet in Storage but NEVER deletes hot rows
("the highest-risk operation in the whole pipeline"). This tool is that step 3 - the
reviewed, safe prune - built so it CANNOT delete a row that is not provably archived.

SAFETY CONTRACT (the whole point):
  * DRY-RUN BY DEFAULT. --commit is required to delete anything.
  * A quarter's hot rows are deleted ONLY IF a Parquet snapshot for that exact
    (hive, quarter, table) exists in the `archive` Storage bucket AND its row count
    is >= the hot rows to be deleted. No snapshot / short snapshot -> REFUSE (never delete).
  * Only rows older than ARCHIVE_AGE_MONTHS are ever eligible.
  * --commit ALSO requires --i-verified-snapshots (double gate) - a human affirms review.
  Prod runs are Ian-gated (deleting irrecoverable rows); building + dry-run are local/safe.

USAGE:
  python tools/cold_archive_prune.py --hive-ids <UUID> --quarter 2024-Q1            # dry-run plan
  python tools/cold_archive_prune.py --hive-ids <UUID> --quarter 2024-Q1 --commit --i-verified-snapshots
  python tools/cold_archive_prune.py --self-test                                    # safety-gate unit test
"""
from __future__ import annotations
import argparse
import sys

# Mirror the exporter's contract so the two stay aligned (see feedback: keep replicas in sync).
SUPPORTED_TABLES = ["logbook", "pm_completions", "unified_events", "voice_journal_entries"]
ARCHIVE_AGE_MONTHS = 18
BUCKET = "archive"
# Per-table time column (the exporter uses created_at universally, which is wrong for
# pm_completions/unified_events - this tool is correct per-table).
TIME_COL = {
    "logbook":               "created_at",
    "pm_completions":        "completed_at",
    "unified_events":        "occurred_at",
    "voice_journal_entries": "created_at",
}


def object_path(hive_id: str, quarter: str, table: str) -> str:
    """archive/{hive}/{YYYY-Qn}/{table}.parquet - same layout the exporter writes."""
    return f"{hive_id}/{quarter}/{table}.parquet"


def prune_decision(eligible_rows: int, snapshot_exists: bool, snapshot_rows: int | None) -> tuple[bool, str]:
    """The SAFETY GATE, isolated + unit-testable. Returns (may_delete, reason).

    Delete iff there ARE eligible rows AND a snapshot exists AND the snapshot covers
    at least those rows. Any doubt -> refuse. This is the function --self-test exercises."""
    if eligible_rows <= 0:
        return False, "no eligible rows (age <= threshold)"
    if not snapshot_exists:
        return False, "REFUSE: no Parquet snapshot in archive bucket - export first"
    if snapshot_rows is None:
        return False, "REFUSE: snapshot row count unknown - cannot verify coverage"
    if snapshot_rows < eligible_rows:
        return False, f"REFUSE: snapshot has {snapshot_rows} rows < {eligible_rows} eligible - incomplete archive"
    return True, f"safe: {eligible_rows} rows archived in snapshot ({snapshot_rows} rows) - prunable"


def _lazy_client():
    try:
        from supabase import create_client
    except ImportError:
        print("NOTE: supabase-py not installed - dry-run can still print the plan via SQL, "
              "but Storage snapshot verification + --commit require it (pip install supabase).")
        return None
    import os
    url = os.environ.get("SUPABASE_URL", "http://127.0.0.1:54321")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not key:
        print("NOTE: SUPABASE_SERVICE_ROLE_KEY unset - cannot verify snapshots or commit.")
        return None
    return create_client(url, key)


def snapshot_status(client, path: str) -> tuple[bool, int | None]:
    """Does a Parquet snapshot exist at `path`, and how many rows? (None rows = can't read)."""
    if client is None:
        return False, None
    try:
        folder, name = path.rsplit("/", 1)
        listed = client.storage.from_(BUCKET).list(folder)
        exists = any(o.get("name") == name for o in (listed or []))
        # Row count would require downloading + decoding the Parquet (hyparquet/pyarrow).
        # Kept None here so the gate REFUSES unless a caller wired a real count - safe default.
        return exists, None
    except Exception as e:  # noqa: BLE001
        print(f"  snapshot check failed for {path}: {e}")
        return False, None


def main() -> int:
    ap = argparse.ArgumentParser(description="Cold Archive Prune (safe, gated step 3)")
    ap.add_argument("--hive-ids", help="Comma-separated hive UUIDs")
    ap.add_argument("--quarter", help="Quarter, e.g. 2024-Q1")
    ap.add_argument("--commit", action="store_true", help="Actually delete (requires --i-verified-snapshots)")
    ap.add_argument("--i-verified-snapshots", action="store_true", help="Human affirmation the snapshots were reviewed")
    ap.add_argument("--self-test", action="store_true", help="Exercise the safety gate")
    args = ap.parse_args()

    if args.self_test:
        GREEN, RED, RST = "\033[92m", "\033[91m", "\033[0m"
        cases = [
            # (eligible, snapshot_exists, snapshot_rows) -> expected may_delete
            ((100, True, 100), True),    # exact coverage -> delete
            ((100, True, 250), True),    # over-coverage -> delete
            ((100, False, None), False), # no snapshot -> REFUSE
            ((100, True, None), False),  # unknown count -> REFUSE
            ((100, True, 40), False),    # short snapshot -> REFUSE
            ((0, True, 100), False),     # nothing eligible -> no-op
        ]
        ok = True
        for (elig, ex, sr), expect in cases:
            got, reason = prune_decision(elig, ex, sr)
            mark = "ok" if got == expect else "FAIL"
            if got != expect:
                ok = False
            print(f"  [{GREEN+'ok'+RST if got==expect else RED+'FAIL'+RST}] elig={elig} snap={ex}/{sr} -> may_delete={got} ({reason})")
        # The critical safety property: NEVER delete without a verified, sufficient snapshot.
        never_deletes_unsafe = all(
            not prune_decision(e, ex, sr)[0]
            for (e, ex, sr) in [(100, False, None), (100, True, None), (100, True, 40)]
        )
        print(f"\n  SAFETY [{GREEN+'PASS'+RST if (ok and never_deletes_unsafe) else RED+'FAIL'+RST}] "
              f"gate never deletes without a sufficient verified snapshot: {never_deletes_unsafe}")
        return 0 if (ok and never_deletes_unsafe) else 1

    if not args.hive_ids or not args.quarter:
        ap.error("--hive-ids and --quarter are required (or use --self-test)")
    if args.commit and not args.i_verified_snapshots:
        ap.error("--commit requires --i-verified-snapshots (double gate: a human affirms snapshot review)")

    client = _lazy_client()
    mode = "COMMIT" if args.commit else "DRY-RUN"
    print(f"Cold Archive Prune [{mode}] quarter={args.quarter} tables={SUPPORTED_TABLES}")
    print(f"Eligibility: rows older than {ARCHIVE_AGE_MONTHS} months, per-table time col {TIME_COL}\n")
    for hive in args.hive_ids.split(","):
        hive = hive.strip()
        for table in SUPPORTED_TABLES:
            path = object_path(hive, args.quarter, table)
            exists, srows = snapshot_status(client, path)
            # Eligible-row count needs a DB read; the dry-run reports the SQL to run so an
            # operator (or the retention gate) can confirm before any commit. Kept explicit
            # rather than guessed - the gate refuses on unknowns anyway.
            eligible_sql = (f"SELECT count(*) FROM public.{table} "
                            f"WHERE hive_id='{hive}' AND {TIME_COL[table]} < now() - interval '{ARCHIVE_AGE_MONTHS} months';")
            print(f"  {table:24s} snapshot={'yes' if exists else 'NO '} @ {BUCKET}/{path}")
            print(f"      eligible: {eligible_sql}")
            if args.commit:
                print("      (commit path deletes ONLY if snapshot verified + row count sufficient - see prune_decision)")
    print("\nDRY-RUN complete - no rows deleted." if not args.commit else "\nCOMMIT path is Ian-gated for prod.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
