import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";
import { log } from "../_shared/logger.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
import { generateEmbedding } from "../_shared/embedding-chain.ts";
// Pillar I (Gateway Spine): verify hive membership before service-role search.
import { resolveIdentity, resolveTenancy } from "../_shared/tenant-context.ts";

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

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const { query, hive_id, sources, match_count } = await req.json();

    if (!query) {
      return new Response(
        JSON.stringify({ error: "Missing required field: query" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
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

    const db = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    // Pillar I: knowledge search scoped by the client hive_id on a service-role
    // client. Verify membership when a hive is claimed (solo/global search has
    // no tenant to protect). Internal service-role calls skip.
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
      }
    }

    const count = match_count || 3;

    // Determine which sources to search
    // sources = ["fault", "skill", "pm"] or omit for all three
    const searchSources: string[] = sources || ["fault", "skill", "pm"];

    const results: Record<string, unknown[]> = {};

    // ── Search fault_knowledge ────────────────────────────────────────────────
    if (searchSources.includes("fault")) {
      const { data, error } = await db.rpc("search_fault_knowledge", {
        query_embedding: embedding,
        match_hive_id:   hive_id || null,
        match_count:     count,
      });
      if (error) log.error(null, "search_fault_knowledge error:", { detail: error.message });
      results.faults = data || [];
    }

    // ── Search skill_knowledge ────────────────────────────────────────────────
    if (searchSources.includes("skill")) {
      const { data, error } = await db.rpc("search_skill_knowledge", {
        query_embedding: embedding,
        match_hive_id:   hive_id || null,
        match_count:     count,
      });
      if (error) log.error(null, "search_skill_knowledge error:", { detail: error.message });
      results.skills = data || [];
    }

    // ── Search pm_knowledge ───────────────────────────────────────────────────
    if (searchSources.includes("pm")) {
      const { data, error } = await db.rpc("search_pm_knowledge", {
        query_embedding: embedding,
        match_hive_id:   hive_id || null,
        match_count:     count,
      });
      if (error) log.error(null, "search_pm_knowledge error:", { detail: error.message });
      results.pm = data || [];
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
    log.error(null, "semantic-search error:", { detail: err });
    return new Response(
      JSON.stringify({ error: err instanceof Error ? err.message : String(err) }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
