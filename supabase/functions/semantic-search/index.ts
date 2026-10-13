// contract-allow: retrieval, not generation - returns the hive's own records ranked by similarity; no model writes the reply
import { serveObserved, failTracked } from "../_shared/observability.ts";
import { tracedReply } from "../_shared/trace-reply.ts";  // LM-O: one trace id per request
import { handleHealth } from "../_shared/health.ts";

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.110.0";
import { getCorsHeaders } from "../_shared/cors.ts";
import { log } from "../_shared/logger.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
import { generateEmbedding } from "../_shared/embedding-chain.ts";
// Pillar I (Gateway Spine): verify hive membership before service-role search.
import { resolveIdentity, resolveTenancy } from "../_shared/tenant-context.ts";
// A5 (FULLSTACK_COMPONENT_LIBRARY Layer A): per-person rate limit on the browser path.
import { checkSoloRateLimit, soloRateLimitKey, soloRateLimitedResponse } from "../_shared/rate-limit.ts";
// A hive-less person's OWN knowledge: the one owner-scoped search, shared with ai-gateway's solo path.
import { searchOwnFaultKnowledge } from "../_shared/own-knowledge.ts";
// A turn ai-gateway forwarded has already counted this person's solo bucket (ai-orchestrator relays the proof).
import { isTrustedGatewayForward } from "../_shared/gateway-trust.ts";

// Warm module-scope Supabase client. Reused across request invocations
// in the same warm container. Per-request createClient calls below are
// being phased out (PRODUCTION_FIXES #46). Falls back to an empty
// client if env is missing so module import never throws.
const _WH_SUPABASE_URL_M = Deno.env.get("SUPABASE_URL") || "";
const _WH_SERVICE_KEY_M  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const _whWarmClient = _WH_SUPABASE_URL_M && _WH_SERVICE_KEY_M
  ? createClient(_WH_SUPABASE_URL_M, _WH_SERVICE_KEY_M)
  : null;
void _whWarmClient;

// ── Entry point ───────────────────────────────────────────────────────────────

serveObserved("semantic-search", tracedReply("semantic-search", async (req, _trace) => {  // LM-O: one trace id per request; its model-call rows carry the id this reply returns
  // Arc T/T1: standard liveness /health (fn up + DB creds reachable).
  const _health = await handleHealth(req, "semantic-search", async () => ({
    deps: [{ name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) }],
  }));
  if (_health) return _health;
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  log.info(_trace, "request_start", { method: req.method });  // I6 observability, under the id this reply returns (tracedReply hands it in; R8: never a second id)

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
    const { query, hive_id, sources, match_count } = _whBody;

    if (!query) {
      return new Response(
        JSON.stringify({ error: "Missing required field: query" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const db = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    // Who is asking is settled BEFORE the embedding is spent, so a refused or anonymous caller costs nothing.
    // Pillar I: knowledge search scoped by the client hive_id on a service-role
    // client. Verify membership when a hive is claimed. Internal service-role calls skip.
    // ★A SOLO OWNER'S SEARCH RETURNED NOTHING (2026-10-08). With no hive, this searched with match_hive_id NULL on
    // the service-role client and no owner: the own scope (20261007000014) keys on auth.uid(), which is NULL here,
    // so it named nobody and a signed-in person with no hive never got their own fault history back. The owner is
    // now the caller's VERIFIED auth uid (resolveIdentity on their own JWT) - never a field from the body. Anonymous
    // and internal service-role callers with no hive have no owner and get the same empty answer as before.
    let ownerUid: string | null = null;
    if (hive_id) {
      const { authUid, isServiceRole } = await resolveIdentity(db, req);
      if (!isServiceRole) {
        const tenancy = await resolveTenancy(db, authUid, hive_id);
        if (!tenancy.ok) {
          return new Response(
            JSON.stringify({ error: tenancy.message, code: tenancy.code }),
            { status: tenancy.status, headers: { ...corsHeaders, "Content-Type": "application/json" } },
          );
        }
      
        // A5: rate-limit the browser path (service-role/internal callers skip) — reference: voice-model-call/embed-entry.
        const _ip = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim();
        const _rl = await checkSoloRateLimit(db, soloRateLimitKey(authUid, _ip), undefined, undefined, _ip);
        if (!_rl.allowed) return soloRateLimitedResponse(corsHeaders, _rl.retry_after_seconds, _rl.scope);
      }
    } else {
      const { authUid, isServiceRole } = await resolveIdentity(db, req);
      if (!isServiceRole && authUid) {
        // A5: the own-scope search is a browser path too - same per-person bucket as the hive path.
        // ★EXCEPT A TURN AI-GATEWAY ALREADY COUNTED (2026-10-08). ai-orchestrator now asks this search with the solo
        // person's OWN token (it used to send the service-role key, which named nobody - see below), and on an
        // assistant turn the gateway had already counted that person's solo bucket - the same key soloRateLimitKey
        // builds here. Counting it again would halve a solo owner's hourly budget. The skip is decided ONLY by the
        // header ai-gateway mints over this exact bearer (_shared/gateway-trust.ts), never by a body field.
        const _ssViaGateway = await isTrustedGatewayForward(req);
        if (!_ssViaGateway) {
          const _ip = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim();
          const _rl = await checkSoloRateLimit(db, soloRateLimitKey(authUid, _ip), undefined, undefined, _ip);
          if (!_rl.allowed) return soloRateLimitedResponse(corsHeaders, _rl.retry_after_seconds, _rl.scope);
        }
        ownerUid = authUid;
      }
    }

    const count = match_count || 3;

    // Determine which sources to search
    // sources = ["fault", "skill", "pm"] or omit for all three
    const searchSources: string[] = sources || ["fault", "skill", "pm"];

    const results: Record<string, unknown[]> = {};

    // No hive and no verified person: nothing can be searched. The same empty answer as before, unspent.
    if (!hive_id && !ownerUid) {
      if (searchSources.includes("fault")) results.faults = [];
      if (searchSources.includes("skill")) results.skills = [];
      if (searchSources.includes("pm")) results.pm = [];
      return new Response(
        JSON.stringify({ results, context: "No relevant history found in knowledge base yet." }),
        { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Generate embedding for the user's query. RAG retrieval is an ENHANCEMENT,
    // never the critical path (mirrors the reranker doctrine in embedding-chain.ts):
    // if every embedding provider is unconfigured/down/rate-limited, degrade to
    // "no context" with HTTP 200 instead of 500'ing the whole assistant turn.
    // (2026-05-30: discovered semantic-search 500'ing on every chat because the
    // embedding keys were never deployed as secrets — generateEmbedding threw.)
    let embedding: number[];
    try {
      embedding = await generateEmbedding(query);
    } catch (err) {
      log.warn(null, `[semantic-search] embedding unavailable — returning empty RAG context: ${err instanceof Error ? err.message : String(err)}`);
      return new Response(
        JSON.stringify({ results: {}, context: "No relevant history found in knowledge base yet." }),
        { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // ── Search fault_knowledge ────────────────────────────────────────────────
    if (searchSources.includes("fault")) {
      if (hive_id) {
        const { data, error } = await db.rpc("search_fault_knowledge", {
          query_embedding: embedding,
          match_hive_id:   hive_id,
          match_count:     count,
        });
        if (error) log.error(null, "search_fault_knowledge error:", { detail: error.message });
        results.faults = data || [];
      } else {
        // the person's OWN hive-less rows: match_hive_id NULL + match_owner = the verified uid, each row re-read as theirs
        const own = await searchOwnFaultKnowledge(db, embedding, ownerUid, count);
        if (own === null) log.error(null, "search_fault_knowledge (own scope) error");
        results.faults = own || [];
      }
    }

    // skill_knowledge and pm_knowledge carry no owner column - they hold hive rows only, so with no hive there is
    // nothing of the person's to find (and a NULL hive never matched a row there).
    // ── Search skill_knowledge ────────────────────────────────────────────────
    if (searchSources.includes("skill")) {
      if (hive_id) {
        const { data, error } = await db.rpc("search_skill_knowledge", {
          query_embedding: embedding,
          match_hive_id:   hive_id,
          match_count:     count,
        });
        if (error) log.error(null, "search_skill_knowledge error:", { detail: error.message });
        results.skills = data || [];
      } else {
        results.skills = [];
      }
    }

    // ── Search pm_knowledge ───────────────────────────────────────────────────
    if (searchSources.includes("pm")) {
      if (hive_id) {
        const { data, error } = await db.rpc("search_pm_knowledge", {
          query_embedding: embedding,
          match_hive_id:   hive_id,
          match_count:     count,
        });
        if (error) log.error(null, "search_pm_knowledge error:", { detail: error.message });
        results.pm = data || [];
      } else {
        results.pm = [];
      }
    }

    // ── Build context string for the AI assistant ─────────────────────────────
    // This is what gets injected into the assistant's system prompt
    const contextParts: string[] = [];

    if (results.faults?.length) {
      const faultLines = (results.faults as Record<string, unknown>[]).map(f =>
        `- ${f.machine}: problem="${f.problem}", root cause="${f.root_cause}", fix="${f.action}"${f.knowledge ? `, lesson="${f.knowledge}"` : ""}`
      );
      contextParts.push(`RELEVANT FAULT HISTORY:\n${faultLines.join("\n")}`);
    }

    if (results.skills?.length) {
      const skillLines = (results.skills as Record<string, unknown>[]).map(s =>
        `- ${s.worker_name}: ${s.discipline} Level ${s.level}${s.primary_skill ? ` (primary: ${s.primary_skill})` : ""}`
      );
      contextParts.push(`RELEVANT SKILL PROFILES:\n${skillLines.join("\n")}`);
    }

    if (results.pm?.length) {
      const pmLines = (results.pm as Record<string, unknown>[]).map(p =>
        `- ${p.asset_name} (${p.category}): ${p.health_summary}`
      );
      contextParts.push(`RELEVANT PM HEALTH:\n${pmLines.join("\n")}`);
    }

    const context = contextParts.length > 0
      ? contextParts.join("\n\n")
      : "No relevant history found in knowledge base yet.";

    return new Response(
      JSON.stringify({ results, context }),
      { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );

  } catch (err) {
    // T2b: aggregate this HANDLED failure into wh_traces + return a non-leaky
    // 500 (was leaking err.message to the client). trace_id lets support correlate.
    return await failTracked(req, "semantic-search", "semantic_search_error", err);
  }
}));
