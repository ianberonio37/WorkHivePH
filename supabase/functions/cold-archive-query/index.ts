/**
 * cold-archive-query — Phase 6 of AGENTIC_RAG_ROADMAP.md (SCAFFOLDING).
 *
 * Read endpoint for historical data archived to Supabase Storage as Parquet.
 * The agentic-rag-loop Router promotes a query to route="cold_archive" when
 * its time_scope.from is older than 18 months; this fn answers from the
 * archived Parquet snapshots instead of the hot Postgres `v_logbook_truth`.
 *
 * **STATUS: SCAFFOLDING ONLY.** This fn returns 503 with a clear message
 * until:
 *   (a) `tools/cold_archive_exporter.py` runs quarterly via pg_cron,
 *       writing per-hive Parquet snapshots to supabase://archive-{hive_id}/.
 *   (b) DuckDB-in-Deno is wired up to read those Parquet files (planned via
 *       deno.land/x/duckdb_wasm or a Render/Railway DuckDB micro-service
 *       which the fn proxies to).
 *
 * Today this fn answers the contract (validates inputs, returns a
 * well-formed 503 with reason). The downstream wiring lands when a hive
 * actually crosses the 18-month boundary.
 *
 * Body:
 *   { hive_id, table: 'logbook'|'pm_completions'|'unified_events'|'voice_journal',
 *     time_range: { from: ISO-date, to: ISO-date }, asset_tag?, limit? }
 *
 * Response (scaffolding):
 *   { ok: false, rows: [], reason: "cold_archive not yet provisioned for this hive", available_quarters: [] }
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";

const FN_NAME = "cold-archive-query";
const SUPPORTED_TABLES = ["logbook","pm_completions","unified_events","voice_journal"] as const;
type ArchivedTable = typeof SUPPORTED_TABLES[number];

const _URL = Deno.env.get("SUPABASE_URL") || "";
const _KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
if (!_URL || !_KEY) console.warn("[cold-archive-query] SUPABASE env missing");
const _warm = _URL && _KEY ? createClient(_URL, _KEY) : null;
void _warm;

async function listAvailableQuarters(db: SupabaseClient, hiveId: string): Promise<string[]> {
  // Discovery: list objects under `archive-{hive_id}/` in the archive bucket.
  // Returns quarter labels like "2022-Q3", "2023-Q1". Empty array if no archive exists.
  try {
    const bucket = "archive";
    const { data } = await db.storage.from(bucket).list(`${hiveId}/`, { limit: 100 });
    return (data || []).map(o => o.name).filter(n => /^\d{4}-Q[1-4]$/.test(n));
  } catch (err) {
    console.warn("[cold-archive-query] bucket list failed:", String(err).slice(0, 80));
    return [];
  }
}

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders });
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
  const available = await listAvailableQuarters(db, body.hive_id);

  // Scaffolding response: always returns 503 with discovery info so the
  // agentic-rag-loop Router can gracefully degrade ("answering from hot data
  // only — cold archive not provisioned").
  return new Response(JSON.stringify({
    ok:                 false,
    rows:               [],
    reason:             available.length
                          ? `cold_archive scaffolding active — DuckDB read of Parquet not yet wired (have ${available.length} archived quarters)`
                          : "cold_archive not yet provisioned for this hive (no Parquet snapshots in archive bucket)",
    available_quarters: available,
    table:              body.table,
    time_range:         body.time_range,
  }), {
    status: 503, headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
});
