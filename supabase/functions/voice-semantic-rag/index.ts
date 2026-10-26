import { serveObserved, failTracked } from "../_shared/observability.ts";
import { tracedReply } from "../_shared/trace-reply.ts";  // LM-O: one trace id per request
import { handleHealth } from "../_shared/health.ts";

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.110.0";
import { getCorsHeaders } from "../_shared/cors.ts";
import { log } from "../_shared/logger.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
// Pillar R/I (2026-06-15): the one governed identity resolver (getUser(bearer),
// proven in Pillar I) — used to derive the VERIFIED caller for the personal
// voice-journal scope instead of trusting the client body auth_uid.
import { resolveIdentity } from "../_shared/tenant-context.ts";
import { checkUserRateLimit, userRateLimitedResponse } from "../_shared/rate-limit.ts";
// LM-O (2026-10-08): this function calls an embedding provider itself, so it reports the call itself
import { generateEmbeddingTagged } from "../_shared/embedding-chain.ts";

// contract-allow: RAG retrieval fn, not a brain output producer

/**
 * Voice Semantic RAG Edge Function (Phase 1 + Phase 1.5)
 *
 * Performs semantic similarity search over a worker's voice journal.
 * Called by voice-handler.js to find semantically similar past entries.
 *
 * Phase 1: Recency-based RAG (last 5 turns, last 30 days)
 * Phase 1.5: Optional semantic search via pgvector + embeddings
 *
 * Input:
 *   - auth_uid: worker's UUID
 *   - query_text: current transcript or question
 *   - limit: number of results (default 5)
 *
 * Output:
 *   - results: array of { transcript, reply, created_at, similarity }
 *   - method: "semantic" (pgvector) | "recency" (time-based) | "error"
 *   - count: number of results returned
 *
 * ✅ SECURITY FIX (2026-06-15, Gateway Pillar R) — per-user IDOR CLOSED:
 *   Previously scoped the per-worker voice-journal read by the CLIENT-SUPPLIED
 *   `auth_uid` (body) on a SERVICE-ROLE client (RLS bypassed), called with the
 *   anon key — so any caller could read another worker's journal by passing their
 *   auth_uid (the auth_uid analogue of the Pillar-I hive_id hole). NOW: auth_uid
 *   is derived from the JWT via getUser(); the client body value is ignored; a
 *   caller with no real user JWT (anon key) gets an empty result set. voice-handler.js
 *   sends the signed-in user's access token. See FULLSTACK_SAAS_GATEWAY_ROADMAP.md §6e.
 */

serveObserved("voice-semantic-rag", tracedReply("voice-semantic-rag", async (req, _trace) => {  // LM-O: one trace id per request; its model-call rows carry the id this reply returns
  // Arc T/T1: standard liveness /health (fn up + DB creds reachable).
  const _health = await handleHealth(req, "voice-semantic-rag", async () => ({
    deps: [{ name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) }],
  }));
  if (_health) return _health;
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders });
  log.info(_trace, "request_start", { method: req.method });  // I6 observability, under the id this reply returns (tracedReply hands it in; R8: never a second id)
  if (req.method !== "POST") {
    return new Response("That action is not allowed here. Reload the page and try again.", { status: 405 });
  }

  try {
    // ★A CALLER'S MISTAKE IS NOT A SERVER ERROR (live-walk wave, 2026-09-06). tools/prove_edge_contract.mjs asked this
  // function with a broken JSON body and with GET; both reached `await req.json()` and came back 500, so a typo in a
  // client read as "the platform is broken". These are the same two guards every function that passed already had.
    if (req.method !== "POST") {
      return new Response(JSON.stringify({ error: "That action is not allowed here. Reload the page and try again." }),
        { status: 405, headers: { ...corsHeaders, "Content-Type": "application/json" } });
    }
    let _whBody;
    try { _whBody = await req.json(); } catch {
      return new Response(JSON.stringify({ error: "That request could not be read. Reload the page and try again." }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } });
    }
    const { auth_uid: _bodyAuthUid, query_text, limit = 5 } = _whBody;

    if (!query_text) {
      return new Response(
        JSON.stringify({ error: "Missing query_text" }),
        { status: 400, headers: { "Content-Type": "application/json" } }
      );
    }

    const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";

    const db = createClient(
      SUPABASE_URL,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || ""
    );

    // Pillar R/I auth_uid IDOR fix (2026-06-15): the voice journal is PERSONAL.
    // Scope it ONLY by the JWT-VERIFIED caller (resolveIdentity → getUser(bearer),
    // the proven Pillar-I resolver) — NEVER the client-supplied body `auth_uid`,
    // which let any caller read another worker's journal by passing their id (this
    // fn uses a service-role client = RLS bypassed). A caller with no real user JWT
    // (anon key / no token) has no verified identity → no journal to read. A
    // machine/service-role caller likewise has no personal journal here.
    const _id = await resolveIdentity(db, req);
    const auth_uid: string | null = (!_id.isServiceRole && _id.authUid) ? _id.authUid : null;
    if (!auth_uid) {
      return new Response(
        JSON.stringify({ results: [], method: "unauthenticated", count: 0 }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }
    void _bodyAuthUid; // intentionally ignored — the verified uid is authoritative

    // LLM10 unbounded-consumption: per-user rate-limit (personal voice search; embed + RPC are not free).
    // Identity-keyed (no hive context); the verified auth_uid is the bucket.
    const _rl = await checkUserRateLimit(db, "", auth_uid);
    if (!_rl.allowed) return userRateLimitedResponse(corsHeaders, _rl.user_cap, _rl.retry_after_seconds, _rl.scope);

    // Phase 1.5: Try semantic search via pgvector if embeddings are available
    let results: any[] = [];
    let method = "recency";

    try {
      // Step 1: the query's embedding in the corpus's own space (see _getEmbedding)
      const queryEmbedding = await _getEmbedding(query_text);

      if (queryEmbedding && queryEmbedding.length > 0) {
        // Step 2: Call search_voice_journal_entries RPC with the embedding vector
        const { data: semanticResults, error: semanticError } = await db.rpc(
          "search_voice_journal_entries",
          {
            query_embedding: queryEmbedding,
            match_auth_uid: auth_uid,
            match_count: limit,
          }
        );

        if (!semanticError && semanticResults && semanticResults.length > 0) {
          results = semanticResults.map((row: any) => ({
            transcript: row.transcript,
            reply: row.reply,
            created_at: row.created_at,
            similarity: row.similarity || 0,
          }));
          method = "semantic";
        }
      }
    } catch (err) {
      log.warn(null, "Semantic search failed, falling back to recency:", { detail: err });
      // Fall through to recency fallback
    }

    // Fallback: recency-based search (Phase 1)
    if (results.length === 0) {
      try {
        const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)
          .toISOString();

        // ★THIS FALLBACK HAD NEVER RUN (OWN55 walk, 2026-10-27): it ended in `.execute()`, which supabase-js v2's builders
        // do not have (the Python client's idiom). The TypeError was caught below and logged, so every turn the semantic
        // half missed - which, with its 768-dim query, was every turn - returned no journal at all. A builder is awaited.
        const { data: recencyResults, error: recencyError } = await db
          .from("voice_journal_entries")
          .select("transcript, reply, created_at")
          .eq("auth_uid", auth_uid)
          .gt("created_at", thirtyDaysAgo)
          .order("created_at", { ascending: false })
          .limit(limit);

        if (!recencyError && recencyResults && recencyResults.length > 0) {
          results = recencyResults.map((row: any) => ({
            transcript: row.transcript,
            reply: row.reply,
            created_at: row.created_at,
            similarity: 0.5, // No similarity score for recency
          }));
          method = "recency";
        }
      } catch (err) {
        log.error(null, "Recency fallback failed:", { detail: err });
      }
    }

    return new Response(
      JSON.stringify({
        results,
        method,
        count: results.length,
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }
    );
  } catch (err) {
    // T2b: aggregate this HANDLED failure to wh_traces + non-leaky 500.
    return await failTracked(req, "voice-semantic-rag", "voice_semantic_rag_error", err);
  }
}));

// Helper: the query's embedding, in the space voice_journal_entries lives in.
// ★IT ASKED A MODEL WHOSE VECTORS COULD NOT SEARCH THIS CORPUS (OWN55 walk, 2026-10-27). This called Jina directly for
// jina-embeddings-v2-base-en - 768 dimensions - while voice_journal_entries.embedding is vector(384), written by the shared
// chain's pinned embedder (journal-recall.ts persists with strict). A 768-dim query cannot be compared with a 384-dim
// column, so semantic recall never returned a row and every turn fell to recency after paying a Jina call; and a slow
// Jina held this function 15 s behind a page fetch that gives up at 5 s (voice-handler.js), so the person waited 5 s for
// no recall at all. Production carries JINA_API_KEY, so this was its path there. Now: the shared chain, STRICT (only the
// corpus's own embedder - a fallback's vector is another space) within 3 s, recorded by the chain like every embedding.
const QUERY_EMBED = { strict: true, budgetMs: 3000 };
async function _getEmbedding(text: string): Promise<number[] | null> {
  try {
    return (await generateEmbeddingTagged(text, undefined, QUERY_EMBED)).vector;
  } catch (err) {
    log.warn(null, "Embedding unavailable, recency recall this turn:", { detail: String(err).slice(0, 160) });
    return null;
  }
}
