import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

// ── Generate embedding via Groq (nomic-embed-text-v1.5, 384 dimensions, free) ─

async function generateEmbedding(text: string): Promise<number[]> {
  const GROQ_KEY = Deno.env.get("GROQ_API_KEY");
  if (!GROQ_KEY) throw new Error("GROQ_API_KEY not set");

  const res = await fetch("https://api.groq.com/openai/v1/embeddings", {
    method: "POST",
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
    const body = await req.json();
    const { type, hive_id, entry } = body;

    // type must be one of: "fault" | "skill" | "pm"
    if (!type || !entry) {
      return new Response(
        JSON.stringify({ error: "Missing required fields: type, entry" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const db = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    let embedding: number[];
    let table: string;
    let row: Record<string, unknown>;

    // ── FAULT (from Logbook save) ────────────────────────────────────────────
    if (type === "fault") {
      // Combine the most meaningful fields into one searchable string
      const text = [
        entry.machine       && `Equipment: ${entry.machine}`,
        entry.problem       && `Problem: ${entry.problem}`,
        entry.root_cause    && `Root cause: ${entry.root_cause}`,
        entry.action        && `Action taken: ${entry.action}`,
        entry.knowledge     && `Lesson learned: ${entry.knowledge}`,
        entry.category      && `Category: ${entry.category}`,
      ].filter(Boolean).join(". ");

      embedding = await generateEmbedding(text);
      table = "fault_knowledge";
      row = {
        hive_id:     hive_id || null,
        logbook_id:  entry.id || null,
        machine:     entry.machine || null,
        category:    entry.category || null,
        problem:     entry.problem || null,
        root_cause:  entry.root_cause || null,
        action:      entry.action || null,
        knowledge:   entry.knowledge || null,
        worker_name: entry.worker_name || null,
        embedding,
      };
    }

    // ── SKILL (from Skill Matrix save) ──────────────────────────────────────
    else if (type === "skill") {
      const text = [
        entry.worker_name   && `Technician: ${entry.worker_name}`,
        entry.discipline    && `Discipline: ${entry.discipline}`,
        entry.level         && `Skill level: ${entry.level} out of 5`,
        entry.primary_skill && `Primary expertise: ${entry.primary_skill}`,
      ].filter(Boolean).join(". ");

      embedding = await generateEmbedding(text);
      table = "skill_knowledge";
      row = {
        hive_id:       hive_id || null,
        worker_name:   entry.worker_name || null,
        discipline:    entry.discipline || null,
        level:         entry.level || null,
        primary_skill: entry.primary_skill || null,
        embedding,
        updated_at:    new Date().toISOString(),
      };
    }

    // ── PM HEALTH (from PM Scheduler save) ──────────────────────────────────
    else if (type === "pm") {
      const overdueText = entry.overdue_count > 0
        ? `${entry.overdue_count} overdue PM tasks`
        : "all PM tasks up to date";

      const lastText = entry.last_completed
        ? `Last PM completed: ${new Date(entry.last_completed).toLocaleDateString()}`
        : "no PM completions recorded";

      const healthSummary = `${overdueText}. ${lastText}.`;

      const text = [
        entry.asset_name && `Asset: ${entry.asset_name}`,
        entry.category   && `Category: ${entry.category}`,
        healthSummary,
      ].filter(Boolean).join(". ");

      embedding = await generateEmbedding(text);
      table = "pm_knowledge";
      row = {
        hive_id:        hive_id || null,
        asset_id:       entry.asset_id || null,
        asset_name:     entry.asset_name || null,
        category:       entry.category || null,
        overdue_count:  entry.overdue_count || 0,
        last_completed: entry.last_completed || null,
        health_summary: healthSummary,
        embedding,
        updated_at:     new Date().toISOString(),
      };
    }

    else {
      return new Response(
        JSON.stringify({ error: `Unknown type: ${type}. Use "fault", "skill", or "pm".` }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // ── Save to the correct knowledge table ──────────────────────────────────
    const { error } = await db.from(table).insert(row);

    if (error) {
      console.error(`DB insert error (${table}):`, error.message);
      return new Response(
        JSON.stringify({ error: error.message }),
        { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    return new Response(
      JSON.stringify({ success: true, type, table }),
      { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );

  } catch (err) {
    console.error("embed-entry error:", err);
    return new Response(
      JSON.stringify({ error: err instanceof Error ? err.message : String(err) }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
