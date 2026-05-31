# Cold Archive — Scale-Up Roadmap

Hierarchical layer (layer 05) of the AI Agent Memory Stack. This documents the
trigger conditions, the current implementation, and the graduation path so the
cold tier can scale without a rewrite.

## What is wired today (Turn 3, 2026-05-31)

- **Read:** `supabase/functions/cold-archive-query/index.ts` reads per-hive
  Parquet snapshots **in-process with [hyparquet](https://github.com/hyparam/hyparquet)**
  (`hyparquet@1.26.0` + `hyparquet-compressors@1.1.1`, snappy). Pure JS, no
  native deps, runs inside the Deno edge runtime.
- **Layout:** `archive/{hive_id}/{YYYY-Qn}/{table}.parquet` in the `archive`
  Storage bucket. Logical `voice_journal` -> file `voice_journal_entries.parquet`;
  all other tables identity (`TABLE_FILE` map in the edge fn).
- **Query path:** list the hive's quarters -> `selectRelevantQuarters()` keeps
  only quarters overlapping the requested range -> download + decode only those
  files -> filter by date (+ optional `asset_tag`) -> return rows.
- **Write:** `tools/cold_archive_exporter.py` (dry-run by default; `--commit`
  to upload). `ARCHIVE_AGE_MONTHS = 18`. **Never auto-deletes hot rows.**
- **Helpers:** `supabase/functions/_shared/cold-archive.ts` (quarter math /
  range overlap — pure, unit-testable).

### Guard rails in the current read path
- `MAX_QUARTERS = 40` — hard fan-out bound (max Parquet files read per request).
- `LIMIT_CAP = 1000` — hard ceiling on rows returned (default 500).
- Sequential decode (one Parquet in memory at a time); early stop once the cap
  is hit. A missing/corrupt file is logged and skipped, never fatal.
- Returns **200** always: `ok:true` (rows found) or `ok:false` (no archive / no
  overlapping data). The old 503 scaffold is gone.

## Go-live / trigger

The exporter activates **per hive** when that hive crosses ~18 months of data
in `logbook` / `pm_completions` / `unified_events` / `voice_journal_entries`.
Until then the read path simply answers `ok:false` ("not yet provisioned").

Go-live steps when the first hive crosses the boundary:
1. Run the exporter dry-run for that hive + quarter; review the row counts.
2. Re-run with `--commit` to upload Parquet to the `archive` bucket.
3. (Separate, deliberate, gated step) delete the now-archived hot rows — see
   "Gated hot-row delete" below. Never bundle this with the upload.
4. Schedule the exporter quarterly via pg_cron (1st of Jan/Apr/Jul/Oct).

> **Router note:** `agentic-rag-loop` already promotes a query to
> `route="cold_archive"` when `time_scope.from` is older than 18 months, but it
> does **not yet call** this edge fn — auto-delegation is deferred. Nothing in
> production invokes cold-archive-query today, so the 200/`ok:false` contract is
> a safe default. Wiring the Router call is a follow-up.

## Graduation path (scale without rewrite)

The read path is intentionally staged. Move to the next stage only when the
prior stage's guard rails (MAX_QUARTERS / LIMIT_CAP / latency) actually bind.

| Stage | Trigger | Change | Why |
|---|---|---|---|
| **1. Pure-JS (now)** | any hive over 18mo | hyparquet reads whole Parquet, filters in JS | zero infra; fine for a few quarters of a single table |
| **2. Column + row-group pushdown** | requests routinely read full files / latency climbs | pass `columns:[...]` to `parquetReadObjects` and prune row-groups by min/max stats before decode | cut bytes decoded; hyparquet supports both natively |
| **3. DuckDB micro-service** | cross-table joins, multi-year scans, or fan-out hits MAX_QUARTERS | stand up a small DuckDB service (Render/Railway) that reads Parquet from Storage over HTTP range; edge fn proxies to it | predicate/aggregate pushdown + SQL over many files; keeps heavy work off the edge runtime |

**Explicitly NOT duckdb-wasm in the edge runtime** — the wasm build is large,
cold-starts slowly, and the memory ceiling in the edge runtime makes multi-file
scans unreliable. When pure-JS is outgrown, go straight to an out-of-process
DuckDB micro-service (stage 3), not duckdb-wasm.

## Gated hot-row delete (highest-risk operation)

Deleting archived rows from hot Postgres is the one irreversible step in this
pipeline. It is deliberately **not** automated by the exporter.

Before any delete:
1. Verify the Parquet object exists in Storage and its row count matches the
   source query count for that (hive, quarter, table).
2. Verify the read path can return those rows (`cold-archive-query` `ok:true`).
3. Only then delete the hot rows, in a single explicit, reviewed migration/script
   scoped to exactly that (hive, quarter, table) window.

`validate_cold_archive.py` C09 enforces that the exporter never calls `.delete()`
/ `DELETE FROM` — the guard that keeps this step manual.
