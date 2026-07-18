/**
 * semantic-fact-extractor — Semantic layer (layer 03) of the AI Agent Memory
 * Stack. Per-hive entity extractor: turns a hive's own logbook entries into
 * typed subject -> predicate -> object triples and writes them to
 * knowledge_graph_facts (source_type='ai_extraction').
 *
 * Why this exists (Turn 4 of the memory-stack flywheel):
 *   knowledge_graph_facts was built in phase6 for per-hive claims like
 *   "Motor M-3 has failed 4 times this quarter" but was NEVER populated: only
 *   the day5 STANDARDS extractor wrote KG facts and those went to the platform
 *   sibling (platform_knowledge_graph_facts). The hive table sat empty (0 rows,
 *   verified 2026-05-31). voice-handler.js::_fetchKGContext already READS this
 *   store via semantic_search_kg_facts -> this function supplies the missing
 *   WRITES, closing the semantic loop end to end.
 *
 * Architecture (deterministic-engine + light-LLM principle, same as
 * hierarchical-summarizer):
 *   1. Read v_logbook_truth for the hive (SQL, canonical view, narrow + capped).
 *   2. Skip entries already extracted (idempotent re-runs; source_ref carries
 *      "logbook:<entry_id>").
 *   3. callAI extracts triples per small batch (free-tier chain, JSON).
 *   4. Validate + sanitize each triple against the CHECK vocabulary (pure
 *      helpers in _shared/semantic-facts.ts, Node-probeable).
 *   5. Best-effort embed claim_text (384-dim via _shared/embedding-chain.ts) so
 *      the fact is retrievable by semantic_search_kg_facts; null on failure
 *      (fact still lands; a later run / enrichment pass can embed it).
 *   6. Idempotent upsert ON CONFLICT against uq_kgf_triple_source
 *      (20260531000000_knowledge_graph_facts_dedup.sql).
 *
 * Trigger: pg_cron, e.g. weekly per hive after hierarchical-summarizer. Spread
 * off-peak to avoid TPM contention with live agentic-rag-loop traffic.
 *
 * Body: { hive_id (required), since?: ISO-date, limit?: int, max_groups?: int }
 * Response: { ok, written, skipped, facts_extracted, embedded, groups, errors }
 *   - Empty logbook / nothing new is a SUCCESS: 200 + ok:true + written:0
 *     (NOT 200+ok:false — that violates validate_edge_status_body_consistency,
 *     baseline 0: ok:false <=> status >= 400. Turn 3 lesson.)
 *
 * Skills consulted: ai-engineer (callAI, system prompt const, JSON output, no
 * em dashes, hive scoping, row caps, embedding chain), architect (4-place sync,
 * dedupe-key migration, service-role writes), data-engineer (canonical view
 * reads, narrow selects, idempotent NOT-already-extracted filter), performance
 * (batch the LLM calls, cap fan-out, no per-row inserts).
 *
 * contract-allow: scheduled extractor writer; output schema documented above.
 */

import { serveObserved, trackHandled } from "../_shared/observability.ts";
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { callAI } from "../_shared/ai-chain.ts";
import { log } from "../_shared/logger.ts";
import { generateEmbedding } from "../_shared/embedding-chain.ts";
import { logAICost, estimateTokens } from "../_shared/cost-log.ts";
import { getCorsHeaders } from "../_shared/cors.ts";
// Pillar I (Gateway Spine): verify hive membership before service-role logbook reads.
import { resolveIdentity, resolveTenancy } from "../_shared/tenant-context.ts";
import { checkAIRateLimit } from "../_shared/rate-limit.ts"; // Arc L: per-hive AI cap (member-spam hardening; service-role exempt; envelope fail() for 429)
import { beginRequest, ok, fail } from "../_shared/envelope.ts";
import { handleHealth } from "../_shared/health.ts";
import {
  parseTriples, validateTriple, formatEntriesForPrompt,
  type LogbookEntry, type NormalizedTriple,
} from "../_shared/semantic-facts.ts";

const FN_NAME      = "semantic-fact-extractor";
const GROUP_SIZE   = 18;     // logbook entries per LLM call (token-minimal batches)
const MAX_GROUPS   = 6;      // fan-out cap per invocation (<= MAX_GROUPS LLM calls)
const ROW_CAP      = GROUP_SIZE * MAX_GROUPS;  // never fetch more logbook rows than we can process
const TRIPLE_CAP   = 200;    // hard ceiling on facts written per run
const EMBED_CAP    = 120;    // best-effort embeddings per run (rest land with embedding=null)
const MAX_TOKENS   = 1500;   // per extraction call

const EXTRACTION_SYSTEM = `You extract subject/predicate/object knowledge-graph triples from one industrial maintenance team's OWN logbook entries. These triples are stored per-hive and later retrieved by a maintenance AI assistant, so capture durable, operation-specific facts (this asset, this failure pattern, this fix), NOT generic textbook knowledge.

You receive a list of logbook entries, one per line, each starting with id=<uuid>.

RULES:
1. Output STRICT JSON only: { "triples": [ ... ] }. No markdown, no commentary.
2. Each triple has keys: subject_type, subject_ref, predicate, object_type, object_ref, claim_text, confidence, entry_id.
3. entry_id MUST be copied verbatim from the id= of the line the fact came from. Never invent an id.
4. subject_type / object_type: one of asset, failure_mode, part, sop, worker, lesson, system, control, hazard, process.
5. predicate: one of causes, detects, requires, mitigates, related_to, prevents, monitors, uses, applies_to, documents, warns_against.
6. subject_ref / object_ref: short noun phrases as they appear (e.g. "Pump P-204", "shaft seal leak", "mechanical seal kit").
7. claim_text: one short plain-English sentence stating the fact.
8. confidence: 0.9 if explicit in the entry, 0.7 if reasonably implied, 0.5 if speculative.
9. Extract 1 to 5 triples per entry. Skip entries with no durable fact (return fewer triples). Do not pad.
10. No em dashes. Use hyphens, colons, or commas.

Good examples:
- asset "Pump P-204" -> causes -> failure_mode "shaft seal leak"  (claim: "Pump P-204 has repeatedly developed shaft seal leaks.")
- failure_mode "bearing overheating" -> requires -> part "SKF 6204 bearing"
- lesson "torque flange bolts in a star pattern" -> mitigates -> failure_mode "gasket blowout"`;

const _URL = Deno.env.get("SUPABASE_URL") || "";
const _KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
if (!_URL || !_KEY) log.warn(null, "[semantic-fact-extractor] SUPABASE env vars missing");
const _warm = _URL && _KEY ? createClient(_URL, _KEY) : null;
void _warm;

// ── Helpers ──────────────────────────────────────────────────────────────────

function chunk<T>(arr: T[], size: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size));
  return out;
}

/** Source-refs of entries already extracted for this hive (idempotent re-runs). */
async function alreadyExtracted(db: SupabaseClient, hiveId: string): Promise<Set<string>> {
  // canonical-allow: agent-infra semantic store (KG triples), server-side write+read
  // by this extractor only; not a user-facing KPI surface (no v_*_truth wrapper needed).
  const { data, error } = await db.from("knowledge_graph_facts")
    .select("source_ref")
    .eq("hive_id", hiveId)
    .eq("created_by", FN_NAME)
    .like("source_ref", "logbook:%")
    .limit(5000);
  if (error) { log.warn(null, "[semantic-fact-extractor] prior-facts lookup failed:", { detail: error.message }); return new Set(); }
  return new Set((data || []).map((r: { source_ref: string }) => r.source_ref));
}

// ── Server entry ──────────────────────────────────────────────────────────────

serveObserved("semantic-fact-extractor", async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders });

  // /health probe.
  const healthResp = await handleHealth(req, FN_NAME, async () => ({
    deps: [
      { name: "supabase",  ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) },
      { name: "ai-chain",  ok: Boolean(Deno.env.get("GROQ_API_KEY") || Deno.env.get("CEREBRAS_API_KEY")) },
      { name: "embedding", ok: Boolean(Deno.env.get("VOYAGE_API_KEY") || Deno.env.get("JINA_API_KEY") || Deno.env.get("GEMINI_API_KEY")) },
    ],
  }));
  if (healthResp) return healthResp;

  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  const ctx = beginRequest(req, { route: FN_NAME });
  log.info(ctx, "request_start", { method: req.method });

  let body: { hive_id?: string; since?: string; limit?: number; max_groups?: number } = {};
  try { body = await req.json(); } catch {
    return fail(ctx, "bad_request", "Invalid JSON body", { status: 400 });
  }
  if (!body.hive_id) {
    return fail(ctx, "bad_request", "Missing required field: hive_id", { status: 400 });
  }

  const hiveId    = body.hive_id;
  ctx.hive_id     = hiveId;
  const rowLimit  = Math.min(ROW_CAP, Math.max(1, Number(body.limit ?? ROW_CAP)));
  const maxGroups = Math.min(MAX_GROUPS, Math.max(1, Number(body.max_groups ?? MAX_GROUPS)));
  const db        = _warm || createClient(_URL, _KEY);

  // Pillar I: extracts facts from a hive's logbook scoped by the client hive_id
  // on a service-role client — verify membership. Internal callers (the RAG
  // Checker stage / cron) use service-role and skip.
  {
    const { authUid, isServiceRole } = await resolveIdentity(db, req);
    if (!isServiceRole) {
      const t = await resolveTenancy(db, authUid, hiveId);
      if (!t.ok) return fail(ctx, t.code, t.message, { status: t.status });
      // Arc L free-tier B-hardening: per-hive AI cap so an authenticated member cannot
      // spam this generative extractor and drain the hive's free-tier LLM budget.
      const _rl = await checkAIRateLimit(db, hiveId);
      if (!_rl.allowed) return fail(ctx, "rate_limited", "AI call limit reached for this hive. Try again in an hour.", { status: 429 });
    }
  }
  const errors: string[] = [];

  // 1. Fetch candidate logbook entries (hive-scoped, narrow, capped). Prefer
  //    entries that carry a durable fact (root_cause / knowledge / problem).
  let q = db.from("v_logbook_truth")
    .select("id, machine, problem, action, root_cause, failure_consequence, knowledge, maintenance_type, created_at")
    .eq("hive_id", hiveId)
    .order("created_at", { ascending: false })
    .limit(rowLimit);
  if (body.since) q = q.gte("created_at", body.since);

  const { data: rows, error: fetchErr } = await q;
  if (fetchErr) {
    await trackHandled(req, "semantic-fact-extractor", "logbook_fetch_failed", fetchErr);
    return fail(ctx, "logbook_fetch_failed", fetchErr.message, { status: 500 });
  }

  // Keep only entries with at least one substantive field, and not already done.
  const done = await alreadyExtracted(db, hiveId);
  const candidates = ((rows || []) as LogbookEntry[])
    .filter((e) => e.id && (e.root_cause || e.knowledge || e.problem || e.action))
    .filter((e) => !done.has(`logbook:${e.id}`));

  if (!candidates.length) {
    // SUCCESS: nothing new to extract. ok() -> 200 + ok:true (NOT ok:false).
    return ok(ctx, {
      written: 0, skipped: 0, facts_extracted: 0, embedded: 0, groups: 0,
      reason: "no new logbook entries to extract", errors: [],
    });
  }

  // 2. Extract triples per batch.
  const groups = chunk(candidates, GROUP_SIZE).slice(0, maxGroups);
  let factsExtracted = 0;
  const t0 = Date.now();
  const collected: NormalizedTriple[] = [];

  for (const group of groups) {
    if (collected.length >= TRIPLE_CAP) break;
    const validIds = new Set(group.map((e) => e.id));
    let raw = "";
    try {
      raw = await callAI(formatEntriesForPrompt(group), {
        systemPrompt: EXTRACTION_SYSTEM,
        temperature:  0.1,
        maxTokens:    MAX_TOKENS,
        jsonMode:     true,
      });
    } catch (err) {
      errors.push(`extraction batch failed: ${String(err).slice(0, 120)}`);
      continue;
    }
    for (const rt of parseTriples(raw)) {
      const norm = validateTriple(rt, validIds);
      if (norm) { collected.push(norm); factsExtracted++; }
      if (collected.length >= TRIPLE_CAP) break;
    }
  }

  await logAICost(db, {
    fn: FN_NAME, hive_id: hiveId, worker_name: null,
    model: "chain:auto", provider: "groq",
    prompt_tokens: estimateTokens(EXTRACTION_SYSTEM) * groups.length,
    output_tokens: estimateTokens(JSON.stringify(collected)),
    latency_ms: Date.now() - t0,
    status: factsExtracted > 0 ? "success" : "fallback",
    schema_compliance: factsExtracted > 0,
  });

  // 3. Best-effort embed + build rows.
  let embeddingDisabled = false;
  let embedded = 0;
  const nowIso = new Date().toISOString();
  const rowsToWrite: Record<string, unknown>[] = [];
  for (const tr of collected) {
    let embedding: number[] | null = null;
    if (!embeddingDisabled && embedded < EMBED_CAP) {
      const text = tr.claim_text || `${tr.subject_ref} ${tr.predicate} ${tr.object_ref}`;
      try {
        embedding = await generateEmbedding(text);
        embedded++;
      } catch (err) {
        const msg = String(err);
        // "No embedding provider configured" is terminal for this run — stop retrying.
        if (msg.includes("No embedding provider")) embeddingDisabled = true;
        embedding = null;
      }
    }
    rowsToWrite.push({
      hive_id:      hiveId,
      subject_type: tr.subject_type,
      subject_ref:  tr.subject_ref,
      predicate:    tr.predicate,
      object_type:  tr.object_type,
      object_ref:   tr.object_ref,
      claim_text:   tr.claim_text || null,
      confidence:   tr.confidence,
      source_type:  "ai_extraction",
      source_ref:   `logbook:${tr.entry_id}`,
      embedding,
      active:       true,
      created_by:   FN_NAME,
    });
  }

  // 4. Idempotent upsert against uq_kgf_triple_source.
  let written = 0;
  if (rowsToWrite.length) {
    const { data: ins, error: upErr } = await db.from("knowledge_graph_facts")
      .upsert(rowsToWrite, { onConflict: "hive_id,subject_ref,predicate,object_ref,source_ref", ignoreDuplicates: true })
      .select("id");
    if (upErr) {
      await trackHandled(req, "semantic-fact-extractor", "upsert_failed", upErr);
      return fail(ctx, "upsert_failed", upErr.message, {
        status: 500, detail: { facts_extracted: factsExtracted, embedded },
      });
    }
    written = (ins || []).length;
  }

  return ok(ctx, {
    written,
    skipped: rowsToWrite.length - written,
    facts_extracted: factsExtracted,
    embedded,
    groups: groups.length,
    errors,
  });
});
