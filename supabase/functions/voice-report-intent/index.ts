import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { callAI } from "../_shared/ai-chain.ts";
import { getCorsHeaders } from "../_shared/cors.ts";

// ── Intent parser system prompt ───────────────────────────────────────────────
// Kept static for prompt caching eligibility when upgraded to Claude.

const INTENT_SYSTEM = `You are a voice command parser for a maintenance reporting tool.
A maintenance worker spoke a command. Extract their COMPLETE intent in one pass.
Respond ONLY in JSON — no explanation, no markdown.

Available report types: pm_overdue, failure_digest, shift_handover, predictive

Output format:
{
  "report_types": <array of report IDs to select, empty array [] if none mentioned>,
  "recipient_hint": <string or null — name or role the worker said to send to>,
  "period_days": <integer or null — time period>,
  "machine_filter": <string or null — specific machine/equipment>,
  "urgency": <"high" or "normal">,
  "notes": <string — one plain sentence summary of everything the worker wants>
}

Report type mapping (be generous with synonyms):
- "pm", "pm overdue", "preventive", "overdue", "maintenance due" → "pm_overdue"
- "failure", "failures", "breakdown", "digest", "corrective" → "failure_digest"
- "shift", "handover", "turnover", "handoff", "next shift" → "shift_handover"
- "predictive", "predict", "prediction", "forecast", "mtbf", "next failure" → "predictive"
- "everything", "all", "all reports", "complete report" → all four types

Recipient hint — preserve exactly as spoken:
- A person's name: "Ian", "Juan", "Maria" → use that name
- A role: "supervisor", "engineer", "manager", "team" → use that role word
- "everyone" or "all" → "everyone"
- Not mentioned → null

IMPORTANT: Always look for "to [name/role]" in the command and extract it as recipient_hint.
"send X to Ian" → recipient_hint: "Ian"
"send X to supervisor" → recipient_hint: "supervisor"
"send to everyone" → recipient_hint: "everyone"

Examples:
- "Send PM Overdue and Shift Handover to Ian, focus on pump 3"
  → {"report_types":["pm_overdue","shift_handover"],"recipient_hint":"Ian","machine_filter":"Pump 3","period_days":null,"urgency":"normal","notes":"PM Overdue and Shift Handover for Pump 3, send to Ian"}
- "all predictive analytics to Ian"
  → {"report_types":["predictive"],"recipient_hint":"Ian","machine_filter":null,"period_days":null,"urgency":"normal","notes":"Predictive analytics, send to Ian"}
- "send predictive to Juan"
  → {"report_types":["predictive"],"recipient_hint":"Juan","machine_filter":null,"period_days":null,"urgency":"normal","notes":"Predictive report, send to Juan"}
- "send everything to supervisor this week"
  → {"report_types":["pm_overdue","failure_digest","shift_handover","predictive"],"recipient_hint":"supervisor","period_days":7,"machine_filter":null,"urgency":"normal","notes":"All reports for last 7 days, send to supervisor"}
- "urgent failure digest to everyone"
  → {"report_types":["failure_digest"],"recipient_hint":"everyone","period_days":null,"machine_filter":null,"urgency":"high","notes":"Urgent failure digest to all contacts"}
- "focus on conveyor line, this week"
  → {"report_types":[],"recipient_hint":null,"machine_filter":"conveyor line","period_days":7,"urgency":"normal","notes":"Focus on conveyor line for last 7 days"}
- "just send it"
  → {"report_types":[],"recipient_hint":null,"machine_filter":null,"period_days":null,"urgency":"normal","notes":"Standard report, no specific context"}`;

// ── Entry point ───────────────────────────────────────────────────────────────

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
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

    const VALID_TYPES = new Set(["pm_overdue","failure_digest","shift_handover","predictive"]);

    let parsed: {
      report_types:   string[];
      recipient_hint: string | null;
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
        report_types:   [],
        recipient_hint: null,
        period_days:    null,
        machine_filter: null,
        urgency:        "normal",
        notes:          safeTranscript,
      };
    }

    // Sanitise — enforce expected types and filter invalid values
    parsed.report_types   = Array.isArray(parsed.report_types)
                              ? parsed.report_types.filter((t: unknown) => typeof t === "string" && VALID_TYPES.has(t))
                              : [];
    parsed.recipient_hint = typeof parsed.recipient_hint === "string" && parsed.recipient_hint.length > 0
                              ? parsed.recipient_hint.slice(0, 80)
                              : null;
    parsed.period_days    = typeof parsed.period_days === "number"    ? parsed.period_days    : null;
    parsed.machine_filter = typeof parsed.machine_filter === "string"  ? parsed.machine_filter : null;
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
