import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

// Allow specific origin in production; use env var ALLOWED_ORIGIN to override (e.g. for local dev)
const ORIGIN = Deno.env.get("ALLOWED_ORIGIN") || "https://workhiveph.com";
const corsHeaders = {
  "Access-Control-Allow-Origin": ORIGIN,
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

// ── Generate embedding via Groq (same model as embed-entry) ───────────────────

async function generateEmbedding(text: string): Promise<number[]> {
  const GROQ_KEY = Deno.env.get("GROQ_API_KEY");
  if (!GROQ_KEY) throw new Error("GROQ_API_KEY not set");

  const res = await fetch("https://api.groq.com/openai/v1/embeddings", {
    method: "POST",
    signal: AbortSignal.timeout(30000),
    headers: {
      "Authorization": `Bearer ${GROQ_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "nomic-embed-text-v1_5",
      input: text,
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Groq embedding error ${res.status}: ${err}`);
  }

  const data = await res.json();
  return data.data[0].embedding;
}

// ── Entry point ───────────────────────────────────────────────────────────────

serve(async (req) => {
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

    // Generate embedding for the user's query
    const embedding = await generateEmbedding(query);

    const db = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

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
      if (error) console.error("search_fault_knowledge error:", error.message);
      results.faults = data || [];
    }

    // ── Search skill_knowledge ────────────────────────────────────────────────
    if (searchSources.includes("skill")) {
      const { data, error } = await db.rpc("search_skill_knowledge", {
        query_embedding: embedding,
        match_hive_id:   hive_id || null,
        match_count:     count,
      });
      if (error) console.error("search_skill_knowledge error:", error.message);
      results.skills = data || [];
    }

    // ── Search pm_knowledge ───────────────────────────────────────────────────
    if (searchSources.includes("pm")) {
      const { data, error } = await db.rpc("search_pm_knowledge", {
        query_embedding: embedding,
        match_hive_id:   hive_id || null,
        match_count:     count,
      });
      if (error) console.error("search_pm_knowledge error:", error.message);
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
    console.error("semantic-search error:", err);
    return new Response(
      JSON.stringify({ error: err instanceof Error ? err.message : String(err) }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
