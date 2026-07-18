import { serveObserved, failTracked } from "../_shared/observability.ts";
import { handleHealth } from "../_shared/health.ts";
import { logRequestStart } from "../_shared/logger.ts";

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.38.4";
import { getCorsHeaders } from "../_shared/cors.ts";
import { log } from "../_shared/logger.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
// Pillar R/I (2026-06-15): the one governed identity resolver (getUser(bearer),
// proven in Pillar I) — used to derive the VERIFIED caller for the personal
// voice-journal scope instead of trusting the client body auth_uid.
import { resolveIdentity } from "../_shared/tenant-context.ts";
import { checkUserRateLimit, userRateLimitedResponse } from "../_shared/rate-limit.ts";

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

serveObserved("voice-semantic-rag", async (req) => {
  // Arc T/T1: standard liveness /health (fn up + DB creds reachable).
  const _health = await handleHealth(req, "voice-semantic-rag", async () => ({
    deps: [{ name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) }],
  }));
  if (_health) return _health;
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders });
  logRequestStart(req, "voice-semantic-rag");  // I6 observability
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  try {
    const { auth_uid: _bodyAuthUid, query_text, limit = 5 } = await req.json();

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
    if (!_rl.allowed) return userRateLimitedResponse(corsHeaders, _rl.user_cap);

    // Phase 1.5: Try semantic search via pgvector if embeddings are available
    let results: any[] = [];
    let method = "recency";

    try {
      // Step 1: Try to get embedding for the query_text
      // For now, this is a stub. When ai-gateway embeds transcripts,
      // we can call a local embedding endpoint or use Jina API here.
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

        const { data: recencyResults, error: recencyError } = await db
          .from("voice_journal_entries")
          .select("transcript, reply, created_at")
          .eq("auth_uid", auth_uid)
          .gt("created_at", thirtyDaysAgo)
          .order("created_at", { ascending: false })
          .limit(limit)
          .execute();

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
});

// Helper: Get embedding for query text (Phase 1.5)
// When Jina API is configured, this calls out to generate embeddings.
// For now, returns null (fallback to recency).
async function _getEmbedding(text: string): Promise<number[] | null> {
  const jina_key = Deno.env.get("JINA_API_KEY");
  if (!jina_key) {
    // No embedding API configured, use recency fallback
    return null;
  }

  try {
    const resp = await fetch("https://api.jina.ai/v1/embeddings", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${jina_key}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "jina-embeddings-v2-base-en",
        input: [text],
      }),
    });

    if (resp.status !== 200) {
      log.warn(null, "Jina API failed:", { detail: resp.status });
      return null;
    }

    const data = await resp.json();
    const embeddings = data.data || [];
    if (embeddings.length > 0) {
      return embeddings[0].embedding || null;
    }
  } catch (err) {
    log.warn(null, "Embedding fetch failed:", { detail: err });
  }

  return null;
}
