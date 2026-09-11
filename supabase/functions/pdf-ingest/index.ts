/**
// capability: report_pdf_render
 * pdf-ingest -- PDF -> chunks -> embeddings -> knowledge table.
 *
 * ⚠️ THE WORKER NOW WORKS; NOTHING STILL CREATES THE WORK (W3-FN row W31154 - diagnosed 2026-09-05,
 * half of it FIXED 2026-09-10). Two independent facts were measured against the live database, and
 * exactly one of them has been repaired. Both are stated because the difference is the whole status:
 *
 *   1. NOTHING CREATES THE WORK - STILL TRUE. A repo-wide search finds no page, script or tool that
 *      ever inserts into `pdf_jobs` - only the migration that creates the table and the seeder's reset
 *      list. The table holds 0 rows and always has. The "client extracts text via PDF.js, then submits
 *      a pdf_jobs row" step described below was never built, and is not built here: that is a product
 *      feature (an upload surface), not a defect in this worker.
 *   2. THE WORKER COULD NOT FINISH IF ANYTHING DID - FIXED. The insert wrote `content` and `meta` into
 *      whatever `target_table` named, constrained by a database-level CHECK to six knowledge tables.
 *      All six were queried: NOT ONE has a `content` column and NOT ONE has `meta`, so every insert it
 *      could attempt failed on every permitted destination - after the embedding call, which succeeds
 *      first, so each attempt spent embedding budget to produce a row that could not land.
 *      The fix needed no migration and no per-target field mapping, because the premise under that
 *      idea was wrong: five of the six are DERIVED SUMMARY tables, one row per asset / per worker /
 *      per calculation, so a page of a manual was never a row any of them could hold under ANY column
 *      name. The platform already has the store this wants - kb_documents + kb_chunks(doc_id,
 *      chunk_num, text, embedding vector(384), the same dimension the chain emits) - so a job now
 *      opens one document and files its chunks under it, and `target_table` is recorded as that
 *      document's content_type: still the job's declared domain, no longer asked to be a destination.
 *      PROVEN END TO END (2026-09-10). First in the database, with the old shape as a CONTROL: against
 *      fault_knowledge the old insert still raises `column "content" of relation "fault_knowledge"
 *      does not exist`, while the new pair - kb_documents then kb_chunks with a 384-dim vector -
 *      returns INSERT 0 1 twice and the chunk reads back through the join. Then through the function
 *      itself: a seeded pdf_jobs row invoked as the service caller returned
 *      `{chunks_in:1, chunks_done:1, errors:0, status:"done"}` where it used to return
 *      `{chunks_done:0, errors:1, status:"failed"}`, leaving one kb_documents row
 *      (content_type='fault_knowledge', embedding_status='done') with one embedded chunk under it and
 *      the job at `done | embedded=1`. Reversed afterwards: 3 deletes, residue audited at 0 in all
 *      three tables, and the six pre-existing kb_chunks left untouched.
 *      ★AND THE THING THAT NEARLY STOPPED THIS BEING TESTED WAS A CONTAINER STATUS, NOT THE STACK.
 *      `supabase_edge_runtime_workhive` reads "Exited (137) 14 hours ago" and I wrote in this very
 *      header that the invoke could not be run because the edge tier was down. It was not: functions
 *      are served here by `wh_edge_resend`, and one POST proved it - pdf-ingest answered with its own
 *      403 refusal, which is a FUNCTION talking, not a dead port. Read the port, never the container
 *      list; and the service-role bearer this gate compares against is the one in the SERVING
 *      container's env, not Kong's.
 *
 * So the honest state is: this function does its documented job the moment a job row exists, and no
 * caller creates one. Kept rather than deleted, on the same principle as voice-model-call's deprecation
 * note - a retirement can still drop the function, its `pdf_jobs` table and its contract row together;
 * a completion now only needs the upload half.
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

import { serveObserved } from "../_shared/observability.ts";
import { handleHealth } from "../_shared/health.ts";
import { logRequestStart } from "../_shared/logger.ts";

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";
import { log } from "../_shared/logger.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
import { generateEmbedding } from "../_shared/embedding-chain.ts";

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

/* ★A JOB'S STATUS IS THE ONLY THING THAT STOPS IT BEING RUN AGAIN (2026-09-09, found by the
   unchecked-writes sweep after cmms-webhook-receiver taught the class). All four pdf_jobs updates below
   discarded their result, and each failure has its own way of going wrong quietly:
     - "processing" not landing  -> the job stays queued, the next invocation picks up the SAME job, and
                                    the document is ingested twice
     - "failed" not landing      -> a job that can never succeed is retried for ever
     - the final status          -> finished work reads as stuck, and nobody can tell which
   None of it would appear in a log. This helper makes the write speak; the caller decides what to do,
   because a status write failing does not always mean the WORK failed. */
async function setJobStatus(
  db: ReturnType<typeof createClient>,
  jobId: string,
  patch: Record<string, unknown>,
  what: string,
): Promise<boolean> {
  const { error } = await db.from("pdf_jobs").update(patch).eq("id", jobId);
  if (error) {
    console.error(`pdf-ingest: could not mark job ${jobId} as ${what} -`, error.message,
      "- the job may be picked up again");
    return false;
  }
  return true;
}

async function processJob(
  db:  ReturnType<typeof createClient>,
  job: { id: string; target_table: string; chunks_json: ChunkRow[] | null; hive_id: string;
         source_name?: string | null },
): Promise<IngestResult> {
  const chunks = Array.isArray(job.chunks_json) ? job.chunks_json : [];
  if (chunks.length === 0) {
    await setJobStatus(db, job.id, {
      status:        "failed",
      error_message: "chunks_json empty",
      finished_at:   new Date().toISOString(),
    }, "failed (empty chunks)");
    return { job_id: job.id, chunks_in: 0, chunks_done: 0, errors: 1, status: "failed" };
  }
  if (chunks.length > MAX_CHUNKS_PER_JOB) {
    await setJobStatus(db, job.id, {
      status:        "failed",
      error_message: `chunks_json exceeds MAX_CHUNKS_PER_JOB=${MAX_CHUNKS_PER_JOB}`,
      finished_at:   new Date().toISOString(),
    }, "failed (too many chunks)");
    return { job_id: job.id, chunks_in: chunks.length, chunks_done: 0, errors: 1, status: "failed" };
  }

  // ...and if THIS one does not land the job stays queued and will be ingested a second time, so it is
  // the one worth refusing to continue on
  if (!await setJobStatus(db, job.id, {
    status:       "processing",
    total_chunks: chunks.length,
    started_at:   new Date().toISOString(),
  }, "processing")) {
    return { job_id: job.id, chunks_in: chunks.length, chunks_done: 0, errors: 1, status: "failed" };
  }

  // ★THE CHUNKS GO TO THE DOCUMENT STORE, NOT INTO SIX SUMMARY TABLES (2026-09-10, W3-FN W31154).
  // This used to build one generic row - { hive_id, embedding, content, meta, source } - and insert it
  // into whatever `target_table` named. Every one of those inserts failed, on every permitted
  // destination, because NOT ONE of the six has a `content` column or a `meta` column; the embedding
  // call runs first, so each attempt spent embedding budget to produce a row that could not land.
  // The deeper reason it could never work: five of those six are DERIVED SUMMARY tables - one row per
  // asset (pm_knowledge: asset_id, overdue_count, last_completed), per worker (skill_knowledge: level,
  // primary_skill), per calculation (calc_knowledge: key_inputs, key_outputs) - so a page of a manual
  // was never a row any of them could hold, whatever it was called. The platform already has the store
  // this needs and it needed no migration: kb_documents (hive_id, title, content_type,
  // embedding_status) with kb_chunks (doc_id, chunk_num, text, embedding vector(384) - the same
  // dimension the chain emits and the same the knowledge tables use). So a job now opens ONE document
  // and files its chunks under it, which is also what makes a re-ingested PDF traceable to its source
  // instead of scattered across a domain table. `target_table` is kept and recorded as the document's
  // content_type: it stays the job's declared domain (its CHECK allowlist is still the right place for
  // that) without being asked to be an insert destination it never fit.
  const { data: doc, error: docErr } = await db.from("kb_documents").insert({
    hive_id:          job.hive_id,
    title:            (job.source_name || "").trim() || `PDF import ${job.id}`,
    content_type:     job.target_table,
    embedding_status: "processing",
  }).select("id").single();
  if (docErr || !doc) {
    // no document, no destination: fail the job LOUDLY rather than embed chunks with nowhere to put them
    //
    // ★A PERSON READS error_message, SO IT HAS TO BE WRITTEN FOR THEM (2026-09-10, critic E4). This said
    // `could not open a kb_documents row: <driver text>` - a sentence I wrote earlier the same day, which
    // names an internal table, hands over a driver string, and tells the person nothing they can do. The
    // CAUSE still matters and still has a reader, so it goes to the log where a maintainer looks; the row
    // carries the sentence the person needs. setJobStatus's `what` argument is not a general log - it is
    // only printed when the status update ITSELF fails - so without this line the detail would be lost.
    console.error(`pdf-ingest: could not open a kb_documents row for job ${job.id} -`,
      docErr?.message || "no row returned");
    await setJobStatus(db, job.id, {
      status:        "failed",
      error_message: "This document could not be filed, so nothing was indexed. Upload it again, or tell your supervisor.",
      finished_at:   new Date().toISOString(),
    }, "failed (no document)");
    return { job_id: job.id, chunks_in: chunks.length, chunks_done: 0, errors: 1, status: "failed" };
  }

  let chunksDone = 0;
  let errors     = 0;
  for (const [i, chunk] of chunks.entries()) {
    try {
      const text = (chunk.text || "").slice(0, 4000);
      if (!text.trim()) {
        errors++;
        continue;
      }
      const embedding = await generateEmbedding(text);
      const { error } = await db.from("kb_chunks").insert({
        doc_id:    doc.id,
        chunk_num: i + 1,
        text,
        embedding,
      });
      if (error) {
        log.warn(null, "pdf-ingest insert failed (kb_chunks):", { detail: error.message });
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
      log.warn(null, "pdf-ingest chunk error:", { detail: err instanceof Error ? err.message : String(err) });
      errors++;
    }
  }

  const finalStatus: "done" | "failed" | "partial" =
    chunksDone === 0 ? "failed"
    : errors > 0 ? "partial"
    : "done";
  // The document must say what actually landed under it. A kb_documents row left at 'processing'
  // forever is the same lie in a different table: a reader (and the RAG retriever) would treat a
  // half-embedded manual as one still on its way, and a failed one as pending rather than absent.
  // ★AND THIS WRITE DISCARDED ITS ERROR, WHICH IS THE LIE THE COMMENT ABOVE DESCRIBES (2026-09-11,
  // caught by validate_unchecked_writes against a 0 baseline). If the update fails, the row stays at
  // 'processing' — exactly the "still on its way" state the comment warns about — while this function
  // returns status:"done" and the caller, the RAG retriever and any reader all believe the document is
  // ready. A write whose result nobody reads can fail while the function answers ok; that is how
  // cmms-webhook-receiver once told a CMMS its work orders had landed while persisting nothing.
  // The failure is now carried in BOTH places someone could look: the job's error_message and the
  // returned payload. It is deliberately NOT thrown — the chunks really did embed, and discarding that
  // truth to report this one would be a second lie.
  const { error: docStatusErr } = await db.from("kb_documents").update({
    embedding_status: finalStatus === "failed" ? "failed" : finalStatus === "partial" ? "partial" : "done",
    updated_at:       new Date().toISOString(),
  }).eq("id", doc.id);
  const failureNotes = [
    errors > 0 ? `${errors} chunk(s) failed` : null,
    docStatusErr ? `document status not written: ${docStatusErr.message}` : null,
  ].filter(Boolean).join("; ");
  await setJobStatus(db, job.id, {
    status:          finalStatus === "partial" ? "done" : finalStatus,
    embedded_chunks: chunksDone,
    error_message:   failureNotes || null,
    finished_at:     new Date().toISOString(),
  }, finalStatus);

  return {
    job_id:      job.id,
    chunks_in:   chunks.length,
    chunks_done: chunksDone,
    errors,
    status:      finalStatus,
    // false means the chunks landed but the DOCUMENT's own status did not — the caller must not read
    // `status` as the document's state in that case
    doc_status_written: !docStatusErr,
  };
}

serveObserved("pdf-ingest", async (req) => {
  // Arc T/T1: standard liveness /health (fn up + DB creds reachable).
  const _health = await handleHealth(req, "pdf-ingest", async () => ({
    deps: [{ name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) }],
  }));
  if (_health) return _health;
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  logRequestStart(req, "pdf-ingest");  // I6 observability

  const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
  const SERVICE_KEY  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
  if (!SUPABASE_URL || !SERVICE_KEY) {
    return new Response(
      JSON.stringify({ error: "pdf-ingest: missing service env" }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  }

  // BFLA / cost-abuse gate (Arc R R2, OWASP A01): pdf-ingest is a SERVICE-ROLE background drainer
  // that processes pending pdf_jobs across ALL hives (embedding + cross-table inserts into
  // job.target_table). It runs verify_jwt=false, so WITHOUT this check any anonymous caller could
  // POST {} (drain mode) to force an unauthorized, unbounded all-hives compute — the same
  // "unenforced cron-only" class already gated in batch-risk-scoring / parts-staging-recommender /
  // trigger-ml-retrain. Only the cron/service-role caller (which sends the service-role key as the
  // bearer) may trigger it; a user JWT or anon caller is refused.
  const bearer = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "");
  if (!(bearer && bearer === SERVICE_KEY)) {
    return new Response(
      JSON.stringify({ error: "Forbidden: service-role only (background drainer)" }),
      { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } },
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
      .select("id, target_table, chunks_json, hive_id, status, source_name")
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
    .select("id, target_table, chunks_json, hive_id, source_name")
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
