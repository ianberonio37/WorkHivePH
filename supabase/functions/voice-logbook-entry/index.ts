/**
 * voice-logbook-entry — Phase 2.2: Voice-First Complete Work Order
 *
 * Takes a technician's spoken description of a maintenance situation and
 * returns a fully structured logbook entry + detected side effects.
 *
 * One voice command fills the entire form:
 *   Problem · Root cause · Action taken · Maintenance type · Status
 *   + LOTO detection · Parts mentioned · Breakdown flag · Supervisor alert text
 *
 * POST body: { transcript: string, hive_id?: string, worker_name?: string }
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { callAI } from "../_shared/ai-chain.ts";
import { getCorsHeaders } from "../_shared/cors.ts";
import { checkAIRateLimit, rateLimitedResponse } from "../_shared/rate-limit.ts";

const LOGBOOK_SYSTEM = `You are a maintenance work order parser for a Philippine industrial plant.
A technician just described a maintenance situation by voice. Extract everything into a structured logbook entry.

Respond ONLY in JSON — no markdown, no explanation.

Output format:
{
  "machine":           <string — equipment tag or name as spoken, null if not mentioned>,
  "problem":           <string — clear description of what was observed/reported>,
  "root_cause":        <string — diagnosed cause if mentioned, otherwise null>,
  "action":            <string — what was done or what needs to be done>,
  "maintenance_type":  <"Breakdown / Corrective" | "Preventive Maintenance" | "Inspection" | "Project Work">,
  "status":            <"Open" | "Closed">,
  "downtime_hours":    <number — hours of downtime if mentioned, else 0>,
  "loto_detected":     <boolean — true if isolation, lockout, tagout, or permit-to-work was mentioned>,
  "loto_note":         <string — specific LOTO note if detected, else null>,
  "parts_mentioned":   <array of strings — any parts, materials, or spares mentioned>,
  "is_breakdown":      <boolean — true if this is a failure/breakdown requiring corrective work>,
  "urgency":           <"critical" | "high" | "normal" | "low">,
  "supervisor_alert":  <string — one sentence summary for the supervisor, or null if routine>
}

Classification rules:
- "Breakdown / Corrective" if failure, fault, trip, leak, broken, cracked, seized, no power, stopped
- "Preventive Maintenance" if PM, lubrication, greasing, scheduled, interval, inspection, routine
- "Inspection" if check, walkthrough, reading, inspection, audit, survey
- Status is "Closed" only if the technician says the work is DONE/COMPLETED/FIXED/RESOLVED
- LOTO/Isolation: detect words like lock, tag, isolate, de-energize, permit, LOTO, PTW, electrical isolation, valve closed, breaker off
- Urgency "critical" if: fire, explosion, injury, safety risk, production stopped, critical equipment down
- supervisor_alert is null for routine PM tasks; fill it for breakdowns, LOTO, or critical urgency

Examples:
"Cooling tower CT-01, fan blade position 3 cracked, visible shaft vibration, I've tagged it out, waiting for spare blade"
→ machine:"CT-01", problem:"Fan blade position 3 cracked with visible shaft vibration", root_cause:"Fatigue fracture on blade", action:"Equipment tagged out pending spare blade replacement", maintenance_type:"Breakdown / Corrective", status:"Open", downtime_hours:0, loto_detected:true, loto_note:"Tagged out pending spare blade", parts_mentioned:["fan blade"], is_breakdown:true, urgency:"high", supervisor_alert:"CT-01 fan blade cracked and tagged out. Spare blade needed before restart."

"Done the monthly greasing on pump P-003 bearing, used NLGI 2 grease, all readings normal"
→ machine:"P-003", problem:"Monthly bearing greasing scheduled", root_cause:null, action:"Bearing greased per OEM spec using NLGI 2 grease, readings normal", maintenance_type:"Preventive Maintenance", status:"Closed", downtime_hours:0, loto_detected:false, loto_note:null, parts_mentioned:["NLGI 2 grease"], is_breakdown:false, urgency:"normal", supervisor_alert:null`;

serve(async (req) => {
  const cors = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });

  try {
    const { transcript, hive_id, worker_name } = await req.json();

    if (!transcript || typeof transcript !== "string" || transcript.trim().length < 5) {
      return new Response(
        JSON.stringify({ error: "Missing or too short transcript" }),
        { status: 400, headers: { ...cors, "Content-Type": "application/json" } },
      );
    }

    // Cap length — prevents prompt injection
    const safe = transcript.trim().slice(0, 500);

    // Rate-gate FIRST per ai-engineer skill (voice is high-cost,
    // high-frequency — no gate = a buggy mic burns the AI budget).
    const db = createClient(
      Deno.env.get("SUPABASE_URL") || "",
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "",
    );
    const rl = await checkAIRateLimit(db, hive_id || "");
    if (!rl.allowed) return rateLimitedResponse(cors);

    const raw = await callAI(safe, {
      systemPrompt: LOGBOOK_SYSTEM,
      temperature:  0.1,
      maxTokens:    512,
      jsonMode:     true,
    });

    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(raw);
    } catch {
      return new Response(
        JSON.stringify({ error: "AI parsing failed — try again", raw }),
        { status: 500, headers: { ...cors, "Content-Type": "application/json" } },
      );
    }

    // Sanitize output — guarantee expected keys exist with safe defaults
    const result = {
      machine:          parsed.machine          ?? null,
      problem:          parsed.problem          ?? safe,
      root_cause:       parsed.root_cause       ?? null,
      action:           parsed.action           ?? null,
      maintenance_type: parsed.maintenance_type ?? "Breakdown / Corrective",
      status:           parsed.status           ?? "Open",
      downtime_hours:   Number(parsed.downtime_hours) || 0,
      loto_detected:    Boolean(parsed.loto_detected),
      loto_note:        parsed.loto_note        ?? null,
      parts_mentioned:  Array.isArray(parsed.parts_mentioned) ? parsed.parts_mentioned : [],
      is_breakdown:     Boolean(parsed.is_breakdown),
      urgency:          parsed.urgency          ?? "normal",
      supervisor_alert: parsed.supervisor_alert ?? null,
    };

    return new Response(
      JSON.stringify({ ok: true, entry: result }),
      { status: 200, headers: { ...cors, "Content-Type": "application/json" } },
    );

  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return new Response(
      JSON.stringify({ error: msg }),
      { status: 500, headers: { ...cors, "Content-Type": "application/json" } },
    );
  }
});
