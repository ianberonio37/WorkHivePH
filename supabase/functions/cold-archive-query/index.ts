/**
 * cold-archive-query — Phase 6 of AGENTIC_RAG_ROADMAP.md / Hierarchical layer
 * (Turn 3 of the AI Agent Memory Stack flywheel).
 *
 * Read endpoint for historical data archived to Supabase Storage as Parquet.
 * The agentic-rag-loop Router promotes a query to route="cold_archive" when
 * its time_scope.from is older than 18 months; this fn answers from the
 * archived Parquet snapshots instead of the hot Postgres `v_logbook_truth`.
 *
 * **STATUS: WIRED (hyparquet, pure-JS, in-process).** `tools/cold_archive_exporter.py`
 * writes per-hive snapshots to archive/{hive_id}/{YYYY-Qn}/{table}.parquet
 * (snappy). This fn lists the hive's quarters, keeps the ones overlapping the
 * requested range, downloads + decodes only those Parquet files with
 * hyparquet, filters by date (+ optional asset_tag), and returns the rows.
 * See COLD_ARCHIVE_SCALEUP_ROADMAP.md for the graduation path beyond pure-JS
 * (column/row-group pushdown -> DuckDB micro-service) when data volume warrants.
 *
 * Body:
 *   { hive_id, table: 'logbook'|'pm_completions'|'unified_events'|'voice_journal',
 *     time_range: { from: ISO-date, to: ISO-date }, asset_tag?, limit? }
 *
 * Response (200) — every successful read path is ok:true:
 *   has-rows : { ok: true, rows: [...], row_count, quarters_read, available_quarters, ... }
 *   empty    : { ok: true, rows: [],    row_count: 0, reason, available_quarters, ... }
 * Errors (>=400): { error } for bad method / JSON / missing fields.
 *
 * ok:false is deliberately NOT used: per the Edge Status/Body Consistency
 * contract, ok:false must pair with status >= 400. An empty cold-archive result
 * is a successful (200) empty set, not an error. Non-envelope by design: returns
 * a bulk rows[] payload, exempt from the Envelope Conformance gate.
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { logRequestStart } from "../_shared/logger.ts";

import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { parquetReadObjects } from "https://esm.sh/hyparquet@1.26.0";
import { compressors } from "https://esm.sh/hyparquet-compressors@1.1.1";
import { getCorsHeaders } from "../_shared/cors.ts";
import { log } from "../_shared/logger.ts";
// Pillar I (Gateway Spine): verify hive membership before service-role archive reads.
import { resolveIdentity, resolveTenancy } from "../_shared/tenant-context.ts";
import { selectRelevantQuarters, type DateRange } from "../_shared/cold-archive.ts";

const FN_NAME = "cold-archive-query";
const SUPPORTED_TABLES = ["logbook","pm_completions","unified_events","voice_journal"] as const;
type ArchivedTable = typeof SUPPORTED_TABLES[number];

// Logical table name -> on-disk Parquet basename. The exporter writes the
// voice journal as `voice_journal_entries.parquet` (its real table name);
// every other table's file matches its logical name.
const TABLE_FILE: Record<ArchivedTable, string> = {
  logbook:        "logbook",
  pm_completions: "pm_completions",
  unified_events: "unified_events",
  voice_journal:  "voice_journal_entries",
};

const BUCKET = "archive";
const MAX_QUARTERS = 40;     // fan-out bound — never read more than this many Parquet files per request
const DEFAULT_LIMIT = 500;
const LIMIT_CAP = 1000;      // hard ceiling on rows returned to the caller

// Columns we try, in order, when locating a row's timestamp / asset identifier.
// Archives are snapshots of heterogeneous tables, so we probe a few names.
const DATE_COLS = ["created_at", "logged_at", "occurred_at"];
const ASSET_COLS = ["asset_tag", "machine", "asset", "equipment"];

const _URL = Deno.env.get("SUPABASE_URL") || "";
const _KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
if (!_URL || !_KEY) log.warn(null, `[${FN_NAME}] SUPABASE env missing`);
const _warm = _URL && _KEY ? createClient(_URL, _KEY) : null;

async function listAvailableQuarters(db: SupabaseClient, hiveId: string): Promise<string[]> {
  // Discovery: list objects under `archive/{hive_id}/` in the archive bucket.
  // Returns quarter labels like "2022-Q3", "2023-Q1". Empty array if no archive exists.
  try {
    const { data } = await db.storage.from(BUCKET).list(`${hiveId}/`, { limit: 100 });
    return (data || []).map(o => o.name).filter(n => /^\d{4}-Q[1-4]$/.test(n));
  } catch (err) {
    log.warn(null, `[${FN_NAME}] bucket list failed:`, { detail: String(err).slice(0, 80) });
    return [];
  }
}

/** Date prefix (YYYY-MM-DD) of a row's timestamp, or "" if none of the known columns are set. */
function rowDate(row: Record<string, unknown>): string {
  for (const c of DATE_COLS) {
    const v = row[c];
    if (v != null && v !== "") return String(v).slice(0, 10);
  }
  return "";
}

/** A row's asset identifier (first matching column), lowercased, or "". */
function rowAsset(row: Record<string, unknown>): string {
  for (const c of ASSET_COLS) {
    const v = row[c];
    if (v != null && v !== "") return String(v).toLowerCase();
  }
  return "";
}

/**
 * Download + decode one quarter's Parquet file, returning the rows that fall
 * within [from, to] (inclusive, date-granular) and match assetTag if given.
 * A missing/corrupt file is logged and treated as zero rows (never fatal).
 * Returns null when the object does not exist (so the caller can tell
 * "read 0 quarters" from "read a quarter that had 0 matches").
 */
async function readQuarter(
  db: SupabaseClient,
  hiveId: string,
  quarter: string,
  fileBase: string,
  range: DateRange,
  assetTag: string | null,
): Promise<Record<string, unknown>[] | null> {
  const path = `${hiveId}/${quarter}/${fileBase}.parquet`;
  let ab: ArrayBuffer;
  try {
    const { data: blob, error } = await db.storage.from(BUCKET).download(path);
    if (error || !blob) return null;          // object not present for this quarter
    ab = await blob.arrayBuffer();
  } catch (err) {
    log.warn(null, `[${FN_NAME}] download failed ${path}:`, { detail: String(err).slice(0, 80) });
    return null;
  }

  let rows: Record<string, unknown>[];
  try {
    // hyparquet accepts the raw ArrayBuffer directly as `file` (it satisfies
    // AsyncBuffer). `compressors` supplies the snappy codec the exporter uses.
    rows = await parquetReadObjects({ file: ab, compressors }) as Record<string, unknown>[];
  } catch (err) {
    log.warn(null, `[${FN_NAME}] parquet decode failed ${path}:`, { detail: String(err).slice(0, 120) });
    return [];                                  // file existed but was unreadable
  }

  const fromDay = range.from.slice(0, 10);
  const toDay = range.to.slice(0, 10);
  const wantAsset = assetTag ? assetTag.toLowerCase() : null;

  return rows.filter(r => {
    const d = rowDate(r);
    if (d && (d < fromDay || d > toDay)) return false;   // outside range (keep rows with no date col)
    if (wantAsset && rowAsset(r) !== wantAsset) return false;
    return true;
  });
}

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders });
  logRequestStart(req, "cold-archive-query");  // I6 observability
  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  let body: { hive_id?: string; table?: ArchivedTable; time_range?: { from: string; to: string }; asset_tag?: string | null; limit?: number } = {};
  try { body = await req.json(); } catch {
    return new Response(JSON.stringify({ error: "Invalid JSON body" }), {
      status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
  if (!body.hive_id) {
    return new Response(JSON.stringify({ error: "Missing required field: hive_id" }), {
      status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
  if (!body.table || !(SUPPORTED_TABLES as readonly string[]).includes(body.table)) {
    return new Response(JSON.stringify({ error: `Missing or invalid table (must be one of ${SUPPORTED_TABLES.join(", ")})` }), {
      status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
  if (!body.time_range || !body.time_range.from || !body.time_range.to) {
    return new Response(JSON.stringify({ error: "Missing required field: time_range.{from, to}" }), {
      status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  const db = _warm || createClient(_URL, _KEY);

  // Pillar I: queries a hive's cold-archive snapshots scoped by the client
  // hive_id on a service-role client — verify membership. Internal callers
  // (agentic-rag-loop) use service-role and skip.
  {
    const { authUid, isServiceRole } = await resolveIdentity(db, req);
    if (!isServiceRole) {
      const t = await resolveTenancy(db, authUid, body.hive_id);
      if (!t.ok) {
        return new Response(
          JSON.stringify({ error: t.message, code: t.code }),
          { status: t.status, headers: { ...corsHeaders, "Content-Type": "application/json" } },
        );
      }
    }
  }

  const table = body.table as ArchivedTable;
  const range: DateRange = { from: body.time_range.from, to: body.time_range.to };
  const assetTag = body.asset_tag ?? null;
  const limit = Math.min(Math.max(1, Number(body.limit) || DEFAULT_LIMIT), LIMIT_CAP);

  const available = await listAvailableQuarters(db, body.hive_id);
  const relevant = selectRelevantQuarters(available, range).slice(0, MAX_QUARTERS);

  if (relevant.length === 0) {
    // Nothing archived overlaps the window: a successful empty result (200,
    // ok:true, rows:[]). ok:false is reserved for >=400 per the Edge
    // Status/Body Consistency contract, so we never pair 200 with ok:false.
    return new Response(JSON.stringify({
      ok: true,
      rows: [],
      row_count: 0,
      reason: available.length
        ? `no archived quarters overlap ${range.from}..${range.to} (have ${available.length} quarters)`
        : "cold_archive not yet provisioned for this hive (no Parquet snapshots in archive bucket)",
      available_quarters: available,
      table,
      time_range: range,
    }), { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } });
  }

  const fileBase = TABLE_FILE[table];
  const collected: Record<string, unknown>[] = [];
  let quartersRead = 0;

  // Sequential read keeps peak memory at one decoded Parquet at a time; the
  // fan-out is already bounded to MAX_QUARTERS. Stop early once the cap is hit.
  for (const q of relevant) {
    const matched = await readQuarter(db, body.hive_id, q, fileBase, range, assetTag);
    if (matched === null) continue;            // no file for this quarter/table
    quartersRead++;
    for (const row of matched) {
      collected.push(row);
      if (collected.length >= limit) break;
    }
    if (collected.length >= limit) break;
  }

  if (quartersRead === 0) {
    // Quarters were listed but none held a Parquet for this table: also a
    // successful empty result (200, ok:true) per the status/body contract.
    return new Response(JSON.stringify({
      ok: true,
      rows: [],
      row_count: 0,
      reason: `no ${table} Parquet found in the ${relevant.length} overlapping quarter(s)`,
      available_quarters: available,
      table,
      time_range: range,
    }), { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } });
  }

  return new Response(JSON.stringify({
    ok: true,
    rows: collected,
    row_count: collected.length,
    truncated: collected.length >= limit,
    quarters_read: quartersRead,
    available_quarters: available,
    table,
    time_range: range,
  }), { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } });
});
