import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";

// ── Generate embedding via Groq (nomic-embed-text-v1.5, 384 dimensions, free) ─

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
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const body = await req.json();

    const db = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    let type: string;
    let hive_id: string | null;
    let entry: Record<string, unknown>;

    // ── Auto-detect: Supabase DB webhook vs manual call ──────────────────────
    if (body.type === "INSERT" && body.record) {
      const record = body.record;

      if (body.table === "logbook") {
        type = "fault";
        hive_id = record.hive_id || null;
        entry = record;

      } else if (body.table === "skill_badges") {
        type = "skill";
        hive_id = record.hive_id || null;
        entry = record;

      } else if (body.table === "pm_completions") {
        type = "pm";
        const { data: asset } = await db.from("pm_assets")
          .select("asset_name, category, hive_id")
          .eq("id", record.asset_id)
          .single();
        hive_id = asset?.hive_id || null;
        entry = {
          asset_id:       record.asset_id,
          asset_name:     asset?.asset_name || "Unknown",
          category:       asset?.category   || "Unknown",
          overdue_count:  0,
          last_completed: record.completed_at,
        };

      } else {
        // Table not handled: skip silently (don't error)
        return new Response(
          JSON.stringify({ skipped: true, reason: `Table ${body.table} not handled` }),
          { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

    } else {
      // ── Manual call format (existing API contract unchanged) ──────────────
      type    = body.type;
      hive_id = body.hive_id;
      entry   = body.entry;

      if (!type || !entry) {
        return new Response(
          JSON.stringify({ error: "Missing required fields: type, entry" }),
          { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
    }

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

      // Content quality guard: skip near-empty entries that would create useless embeddings
      if (text.trim().length < 50) {
        console.warn('embed-entry: skipping near-empty fault entry (' + text.length + ' chars) — insufficient context for semantic retrieval');
        return new Response(JSON.stringify({ skipped: true, reason: 'insufficient_content', text_length: text.length }), { status: 200, headers: { ...corsHeaders, 'Content-Type': 'application/json' } });
      }
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
