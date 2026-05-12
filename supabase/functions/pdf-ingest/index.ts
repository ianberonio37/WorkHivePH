/**
// capability: report_pdf_render
 * pdf-ingest -- PDF -> chunks -> embeddings -> knowledge table.
 *
 * Closes Phase 1.1 of the RAG roadmap. The naive embedding seed (hand-
 * coded fixtures) is a ceiling on RAG quality. This fn lets a worker
 * upload a PDF (manual / spec / code book), the client extracts text
 * via PDF.js, then submits a pdf_jobs row with `chunks_json`. This fn
 * polls pending jobs, embeds each chunk via the multi-provider chain,
 * and inserts into the matching knowledge table.
 *
 * Invocation modes:
 *   1. Direct POST with { job_id } -- process that specific job.
 *   2. POST with no body -- drain the queue (process up to MAX_JOBS).
 *      Used by the daily ingestion cron once scheduled.
 *
 * Skills consulted: ai-engineer (chunk-and-embed pipeline, RAG quality),
 * data-engineer (queue draining + retry semantics), architect (jobs
 * table as the structural surface vs streaming pipeline).
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";
import { embedText } from "../_shared/embedding-chain.ts";

const _WH_SUPABASE_URL_M = Deno.env.get("SUPABASE_URL") || "";
const _WH_SERVICE_KEY_M  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const _whWarmClient = _WH_SUPABASE_URL_M && _WH_SERVICE_KEY_M
  ? createClient(_WH_SUPABASE_URL_M, _WH_SERVICE_KEY_M)
  : null;
void _whWarmClient;

const MAX_JOBS_PER_DRAIN = 5;
const MAX_CHUNKS_PER_JOB = 200;     // safety bound on prompt-size attacks

interface ChunkRow {
  text:  string;
  meta?: Record<string, unknown>;
}

interface IngestResult {
  job_id:       string;
  chunks_in:    number;
  chunks_done:  number;
  errors:       number;
  status:       "done" | "failed" | "partial";
}

async function processJob(
  db:  ReturnType<typeof createClient>,
  job: { id: string; target_table: string; chunks_json: ChunkRow[] | null; hive_id: string },
): Promise<IngestResult> {
  const chunks = Array.isArray(job.chunks_json) ? job.chunks_json : [];
  if (chunks.length === 0) {
    await db.from("pdf_jobs").update({
      status:        "failed",
      error_message: "chunks_json empty",
      finished_at:   new Date().toISOString(),
    }).eq("id", job.id);
    return { job_id: job.id, chunks_in: 0, chunks_done: 0, errors: 1, status: "failed" };
  }
  if (chunks.length > MAX_CHUNKS_PER_JOB) {
    await db.from("pdf_jobs").update({
      status:        "failed",
      error_message: `chunks_json exceeds MAX_CHUNKS_PER_JOB=${MAX_CHUNKS_PER_JOB}`,
      finished_at:   new Date().toISOString(),
    }).eq("id", job.id);
    return { job_id: job.id, chunks_in: chunks.length, chunks_done: 0, errors: 1, status: "failed" };
  }

  await db.from("pdf_jobs").update({
    status:       "processing",
    total_chunks: chunks.length,
    started_at:   new Date().toISOString(),
  }).eq("id", job.id);

  let chunksDone = 0;
  let errors     = 0;
  for (const chunk of chunks) {
    try {
      const text = (chunk.text || "").slice(0, 4000);
      if (!text.trim()) {
        errors++;
        continue;
      }
      const embedding = await embedText(text);
      const row: Record<string, unknown> = {
        hive_id:   job.hive_id,
        embedding,
        content:   text,
        meta:      chunk.meta ?? {},
        source:    "pdf_ingest",
      };
      const { error } = await db.from(job.target_table).insert(row);
      if (error) {
        console.warn(`pdf-ingest insert failed (${job.target_table}):`, error.message);
        errors++;
        continue;
      }
      chunksDone++;
      // Progress checkpoint every 5 chunks so the UI can poll status.
      if (chunksDone % 5 === 0) {
        await db.from("pdf_jobs").update({
          embedded_chunks: chunksDone,
        }).eq("id", job.id);
      }
    } catch (err) {
      console.warn("pdf-ingest chunk error:", err instanceof Error ? err.message : String(err));
      errors++;
    }
  }

  const finalStatus: "done" | "failed" | "partial" =
    chunksDone === 0 ? "failed"
    : errors > 0 ? "partial"
    : "done";
  await db.from("pdf_jobs").update({
    status:          finalStatus === "partial" ? "done" : finalStatus,
    embedded_chunks: chunksDone,
    error_message:   errors > 0 ? `${errors} chunk(s) failed` : null,
    finished_at:     new Date().toISOString(),
  }).eq("id", job.id);

  return {
    job_id:      job.id,
    chunks_in:   chunks.length,
    chunks_done: chunksDone,
    errors,
    status:      finalStatus,
  };
}

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
  const SERVICE_KEY  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
  if (!SUPABASE_URL || !SERVICE_KEY) {
    return new Response(
      JSON.stringify({ error: "pdf-ingest: missing service env" }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  }
  const db = _whWarmClient || createClient(SUPABASE_URL, SERVICE_KEY);

  let body: { job_id?: string } = {};
  try {
    body = await req.json();
  } catch {
    body = {};
  }

  // Single-job mode.
  if (body.job_id) {
    const { data: job } = await db.from("pdf_jobs")
      .select("id, target_table, chunks_json, hive_id, status")
      .eq("id", body.job_id)
      .maybeSingle();
    if (!job) {
      return new Response(
        JSON.stringify({ error: `pdf-ingest: job ${body.job_id} not found` }),
        { status: 404, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }
    if (job.status !== "pending") {
      return new Response(
        JSON.stringify({ error: `pdf-ingest: job ${body.job_id} already ${job.status}` }),
        { status: 409, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }
    const result = await processJob(db, job as Parameters<typeof processJob>[1]);
    return new Response(
      JSON.stringify({ runner: "pdf-ingest", mode: "single", result }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  }

  // Drain mode.
  const { data: jobs } = await db.from("pdf_jobs")
    .select("id, target_table, chunks_json, hive_id")
    .eq("status", "pending")
    .order("created_at", { ascending: true })
    .limit(MAX_JOBS_PER_DRAIN);
  const results: IngestResult[] = [];
  for (const job of (jobs as Parameters<typeof processJob>[1][] | null) || []) {
    results.push(await processJob(db, job));
  }
  return new Response(
    JSON.stringify({
      runner:    "pdf-ingest",
      mode:      "drain",
      processed: results.length,
      results,
    }),
    { headers: { ...corsHeaders, "Content-Type": "application/json" } },
  );
});
