import { serveObserved, failTracked } from "../_shared/observability.ts";
// capability: voice_to_action_router

// contract-allow: intent classification only
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { callAI } from "../_shared/ai-chain.ts";
import { loadMemory, saveTurn, formatMemoryContext } from "../_shared/memory.ts";
import { logAICost, estimateTokens } from "../_shared/cost-log.ts";
// P2 Pillar C (Compute & Resilience): cache the deterministic intent classifier.
import { cached } from "../_shared/cache.ts";
import { getCorsHeaders } from "../_shared/cors.ts";
// Pillar O (Observability): expose a /health probe for the gateway status page.
import { handleHealth } from "../_shared/health.ts";
import { log } from "../_shared/logger.ts";
// Pillar I (Gateway Spine): verify hive membership on the direct call path.
import { resolveIdentity, resolveTenancy } from "../_shared/tenant-context.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
import { checkAIRateLimit, rateLimitedResponse, checkRouteRateLimit, routeRateLimitedResponse } from "../_shared/rate-limit.ts";

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

serveObserved("voice-report-intent", async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  // Pillar O: /health probe (short-circuits before auth/body parsing).
  const healthResp = await handleHealth(req, "voice-report-intent", async () => ({
    deps: [
      { name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) },
      { name: "ai-chain", ok: Boolean(Deno.env.get("GROQ_API_KEY") || Deno.env.get("CEREBRAS_API_KEY")) },
    ],
  }));
  if (healthResp) return healthResp;

  const _logCtx = beginRequest(req, { route: "voice-report-intent" });
  log.info(_logCtx, "request_start", { method: req.method });

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

    // Rate-gate FIRST per ai-engineer skill — voice flows are high-cost.
    const db = createClient(
      Deno.env.get("SUPABASE_URL") || "",
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "",
    );
    // Pillar I: the direct (report-sender.html) path scopes by the client
    // hive_id on a service-role client — verify membership. The ai-gateway
    // forward is service-role and skips. Verify when a hive is claimed.
    if (hive_id) {
      const { authUid, isServiceRole } = await resolveIdentity(db, req);
      if (!isServiceRole) {
        const t = await resolveTenancy(db, authUid, hive_id);
        if (!t.ok) {
          return new Response(
            JSON.stringify({ error: t.message, code: t.code }),
            { status: t.status, headers: { ...corsHeaders, "Content-Type": "application/json" } },
          );
        }
      }
    }
    // D12 per-SURFACE quota, OBSERVE-mode (mirrors the shared gateway pattern). Always counts into
    // (hive, route, hour) via hive_route_calls so per-surface AI pressure is VISIBLE - the
    // hive-wide cap alone cannot show which surface is burning the budget. It does NOT deny:
    // checkRouteRateLimit only enforces when an explicit hive_route_quotas row exists, and
    // none do, so this is a no-op behaviour change. Wrapped: quota bookkeeping must never
    // fail a real request.
    try {
      const _rq = await checkRouteRateLimit(db, hive_id || "" || "", "voice-report-intent");
      // Denies ONLY when an explicit hive_route_quotas row exists (rq.per_route), so this stays
      // a no-op until an admin sets a cap - while always counting for attribution.
      if (_rq.per_route && !_rq.allowed) return routeRateLimitedResponse(corsHeaders, "voice-report-intent", _rq.cap);
    } catch { /* empty-catch-allow: per-surface quota bookkeeping must never fail a real request */ }
    const rl = await checkAIRateLimit(db, hive_id || "");
    if (!rl.allowed) return rateLimitedResponse(corsHeaders);

    // P2 Pillar C: cache the intent classifier. The report-intent JSON is
    // determined by the transcript ALONE (INTENT_SYSTEM is a const; no persona,
    // hive, or asset data in the prompt — memory is loaded around this call, not
    // into it), so the cached value is hive-independent: the same spoken report
    // request across hives is a cache hit with zero cross-hive leakage. Hive
    // scoping (membership verify + rate gate) runs upstream of the cache. 6h TTL.
    const intentCacheKey = `voiceintent:${safeTranscript}`;
    const cr = await cached<string>(
      db, "voice-report-intent", intentCacheKey,
      async () => {
        const out = await callAI(safeTranscript, {
          systemPrompt: INTENT_SYSTEM,
          temperature:  0.1,
          maxTokens:    256,
          jsonMode:     true,
        });
        return {
          data:      out,
          tokensIn:  estimateTokens(safeTranscript) + estimateTokens(INTENT_SYSTEM),
          tokensOut: estimateTokens(out),
        };
      },
      6 * 60 * 60,
    );
    const raw = cr.data;
    if (cr.hit) console.log("[voice-report-intent] intent cache hit");

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
    // T2b: aggregate this HANDLED failure to wh_traces + non-leaky 500.
    return await failTracked(req, "voice-report-intent", "voice_report_intent_error", err);
  }
});
