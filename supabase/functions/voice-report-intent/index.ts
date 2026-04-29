import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { callAI } from "../_shared/ai-chain.ts";

const ORIGIN = Deno.env.get("ALLOWED_ORIGIN") || "https://workhiveph.com";
const corsHeaders = {
  "Access-Control-Allow-Origin": ORIGIN,
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

// ── Intent parser system prompt ───────────────────────────────────────────────
// Kept static for prompt caching eligibility when upgraded to Claude.

const INTENT_SYSTEM = `You are a voice command parser for a maintenance reporting tool.
A maintenance worker spoke a command while selecting reports to send.
Extract their intent. Respond ONLY in JSON — no explanation, no markdown.

Output format:
{
  "period_days": <integer or null — extract time period: "today"=1, "this week"=7, "last week"=7, "this month"=30, "last month"=30, "last quarter"=90, "last 3 months"=90, null if not mentioned>,
  "machine_filter": <string or null — exact machine or equipment name mentioned, preserve original wording, null if not mentioned>,
  "urgency": <"high" or "normal" — "urgent", "ASAP", "critical", "emergency" maps to high, otherwise normal>,
  "notes": <string — one plain English sentence summarising what the user wants>
}

Examples:
- "focus on pump 3 this week" → {"period_days":7,"machine_filter":"Pump 3","urgency":"normal","notes":"Focus on Pump 3 for the last 7 days"}
- "urgent report for conveyor line A" → {"period_days":null,"machine_filter":"Conveyor Line A","urgency":"high","notes":"Urgent report focusing on Conveyor Line A"}
- "send everything for this month" → {"period_days":30,"machine_filter":null,"urgency":"normal","notes":"All reports for the last 30 days"}
- "just send it" → {"period_days":null,"machine_filter":null,"urgency":"normal","notes":"Standard report, no specific context"}`;

// ── Entry point ───────────────────────────────────────────────────────────────

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const { transcript, hive_id } = await req.json();

    if (!transcript || typeof transcript !== "string" || transcript.trim().length === 0) {
      return new Response(
        JSON.stringify({ error: "Missing or empty transcript" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Cap transcript length — prevents prompt injection via very long speech
    const safeTranscript = transcript.trim().slice(0, 500);

    const raw = await callAI(safeTranscript, {
      systemPrompt: INTENT_SYSTEM,
      temperature:  0.1,
      maxTokens:    256,
      jsonMode:     true,
    });

    let parsed: {
      period_days:    number | null;
      machine_filter: string | null;
      urgency:        "high" | "normal";
      notes:          string;
    };

    try {
      parsed = JSON.parse(raw);
    } catch {
      // AI returned non-JSON — fall back to raw transcript as notes
      parsed = {
        period_days:    null,
        machine_filter: null,
        urgency:        "normal",
        notes:          safeTranscript,
      };
    }

    // Sanitise — enforce expected types
    parsed.period_days    = typeof parsed.period_days === "number"   ? parsed.period_days    : null;
    parsed.machine_filter = typeof parsed.machine_filter === "string" ? parsed.machine_filter : null;
    parsed.urgency        = parsed.urgency === "high" ? "high" : "normal";
    parsed.notes          = typeof parsed.notes === "string" && parsed.notes.length > 0
                              ? parsed.notes.slice(0, 200)
                              : safeTranscript;

    return new Response(
      JSON.stringify(parsed),
      { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );

  } catch (err) {
    console.error("voice-report-intent error:", err);
    return new Response(
      JSON.stringify({ error: err instanceof Error ? err.message : String(err) }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
