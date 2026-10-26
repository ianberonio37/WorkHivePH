/**
// capability: voice_to_logbook
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

import { serveObserved, failTracked } from "../_shared/observability.ts";
import { tracedReply } from "../_shared/trace-reply.ts";  // LM-E: one trace id per request, returned on every reply
import { handleHealth } from "../_shared/health.ts";

import { log } from "../_shared/logger.ts";

// contract-allow: voice -> logbook entry write
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.110.0";
import { callAI, aiAnswered } from "../_shared/ai-chain.ts";
import { loadMemory, saveTurn, formatMemoryContext } from "../_shared/memory.ts";
import { logAICost, estimateTokens } from "../_shared/cost-log.ts";
import { getCorsHeaders } from "../_shared/cors.ts";
// Pillar I (Gateway Spine): verify hive membership on the direct call path.
import { resolveIdentity, resolveTenancy } from "../_shared/tenant-context.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
import {
  checkAIRateLimit, rateLimitedResponse, checkRouteRateLimit, routeRateLimitedResponse,
  checkSoloRateLimit, soloRateLimitKey, soloRateLimitedResponse, soloUnidentifiedResponse, DEFAULT_RATE_LIMIT_PER_HOUR, DEFAULT_RATE_LIMIT_PER_DAY,
} from "../_shared/rate-limit.ts";
// The hive bucket is skipped ONLY for a call ai-gateway provably forwarded (it counted that bucket already).
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

const LOGBOOK_SYSTEM = `You are a maintenance work order parser for a Philippine industrial plant.
A technician just described a maintenance situation by voice. Extract everything into a structured logbook entry.

Respond ONLY in JSON — no markdown, no explanation.

Output format:
{
  "machine":           <string — equipment tag or name as spoken, null if not mentioned>,
  "problem":           <string — clear description of what was observed/reported>,
  "root_cause":        <the diagnosed cause if one was mentioned, as EXACTLY one of: "Wear" | "Lubrication Failure" | "Vibration / Fatigue" | "Misalignment" | "Overload" | "Contamination / Dirt" | "Corrosion" | "Electrical Fault" | "Mechanical Damage" | "Human Error" | "Design Issue" | "Unknown" — "Unknown" when a cause was mentioned but none of these fits; null when no cause was mentioned>,
  "root_cause_note":   <string — the cause in the technician's own words when a cause was mentioned, otherwise null>,
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
→ machine:"CT-01", problem:"Fan blade position 3 cracked with visible shaft vibration", root_cause:null, action:"Equipment tagged out pending spare blade replacement", maintenance_type:"Breakdown / Corrective", status:"Open", downtime_hours:0, loto_detected:true, loto_note:"Tagged out pending spare blade", parts_mentioned:["fan blade"], is_breakdown:true, urgency:"high", supervisor_alert:"CT-01 fan blade cracked and tagged out. Spare blade needed before restart."

"Done the monthly greasing on pump P-003 bearing, used NLGI 2 grease, all readings normal"
→ machine:"P-003", problem:"Monthly bearing greasing scheduled", root_cause:null, action:"Bearing greased using NLGI 2 grease, readings normal", maintenance_type:"Preventive Maintenance", status:"Closed", downtime_hours:0, loto_detected:false, loto_note:null, parts_mentioned:["NLGI 2 grease"], is_breakdown:false, urgency:"normal", supervisor_alert:null`;


// Gateway-adoption fallback: when called via ai-gateway, body.worker_name
// is `<redacted>` for PII compliance. Derive the real identity from the
// JWT + worker_profiles. Closes PRODUCTION_FIXES #49 JWT-derive track.
async function deriveWorkerFromJWT(
  authedClient: SupabaseClient,
  adminClient: SupabaseClient,
): Promise<string | null> {
  try {
    const { data: { user } } = await authedClient.auth.getUser();
    if (!user) return null;
    const { data: profile } = await adminClient
      .from("v_worker_truth")
      .select("worker_name")
      .eq("auth_uid", user.id)
      .maybeSingle();
    return profile?.worker_name || user.email || null;
  } catch {
    return null;
  }
}

serveObserved("voice-logbook-entry", tracedReply("voice-logbook-entry", async (req, trace) => {
  // the trace id beginRequest minted is the one every JSON reply of this function returns (tracedReply, LM-E)
  // Arc T/T1: standard liveness /health (fn up + DB creds reachable).
  const _health = await handleHealth(req, "voice-logbook-entry", async () => ({
    deps: [{ name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) }],
  }));
  if (_health) return _health;
  const cors = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  log.info(trace, "request_start", { method: req.method });  // I6 observability

  try {
    // ★A CALLER'S MISTAKE IS NOT A SERVER ERROR (live-walk wave, 2026-09-06). tools/prove_edge_contract.mjs asked this
  // function with a broken JSON body and with GET; both reached `await req.json()` and came back 500, so a typo in a
  // client read as "the platform is broken". These are the same two guards every function that passed already had.
    if (req.method !== "POST") {
      return new Response(JSON.stringify({ error: "That action is not allowed here. Reload the page and try again." }),
        { status: 405, headers: { ...cors, "Content-Type": "application/json" } });
    }
    let _whBody;
    try { _whBody = await req.json(); } catch {
      return new Response(JSON.stringify({ error: "That request could not be read. Reload the page and try again." }),
        { status: 400, headers: { ...cors, "Content-Type": "application/json" } });
    }
    const { transcript, hive_id, worker_name } = _whBody;

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
    // Pillar I: the direct (logbook.html) path scopes the entry write by the
    // client hive_id on a service-role client — verify membership. The
    // ai-gateway forward is service-role and skips. Verify when hive claimed.
    let _verifiedHiveId: string | null = null;   // the hive the limiters count on: proven below, or a service caller's
    if (hive_id) {
      const { authUid, isServiceRole } = await resolveIdentity(db, req);
      if (!isServiceRole) {
        const t = await resolveTenancy(db, authUid, hive_id);
        if (!t.ok) {
          return new Response(
            JSON.stringify({ error: t.message, code: t.code }),
            { status: t.status, headers: { ...cors, "Content-Type": "application/json" } },
          );
        }
        _verifiedHiveId = t.hive_id || hive_id;
      } else {
        _verifiedHiveId = hive_id;
      }
    }
    // D12 per-SURFACE quota, OBSERVE-mode (mirrors the shared gateway pattern). Always counts into
    // (hive, route, hour) via hive_route_calls so per-surface AI pressure is VISIBLE - the
    // hive-wide cap alone cannot show which surface is burning the budget. It does NOT deny:
    // checkRouteRateLimit only enforces when an explicit hive_route_quotas row exists, and
    // none do, so this is a no-op behaviour change. Wrapped: quota bookkeeping must never
    // fail a real request.
    try {
      const _rq = await checkRouteRateLimit(db, _verifiedHiveId || "", "voice-logbook-entry");
      // Denies ONLY when an explicit hive_route_quotas row exists (rq.per_route), so this stays
      // a no-op until an admin sets a cap - while always counting for attribution.
      if (_rq.per_route && !_rq.allowed) return routeRateLimitedResponse(cors, "voice-logbook-entry", _rq.cap, _rq.retry_after_seconds, _rq.scope);
    } catch { /* empty-catch-allow: per-surface quota bookkeeping must never fail a real request */ }
    // ai-gateway already counted a forwarded call on THIS hive's ai_rate_limits row (checkUserRateLimit); counting it
    // again here halved the hive's rate on the logbook-voice route (2026-10-08). The per-surface quota above is kept on
    // both doors: it is keyed on this function's name, a bucket the gateway never touches.
    const viaGateway = await isTrustedGatewayForward(req);
    if (!viaGateway && _verifiedHiveId) {
      const rl = await checkAIRateLimit(db, _verifiedHiveId);
      if (!rl.allowed) return rateLimitedResponse(cors, rl.scope ?? "hour", rl.retry_after_seconds);
    } else if (!viaGateway) {
      // ★A CALLER WITH NO HIVE WAS NEVER COUNTED (2026-10-08). checkAIRateLimit(db, "") admits without tracking,
      // and with verify_jwt = false and no hive claimed nobody was even identified - anyone, with no token at all,
      // reached the model unmetered. A person is limited on their own bucket (the verified uid) with the budget a
      // single-person hive gets, an anonymous caller on the IP floor, and a caller with neither is refused.
      const { authUid: _soloUid, isServiceRole: _soloSvc } = await resolveIdentity(db, req);
      if (!_soloSvc) {
        const _ip = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim();
        const _srl = await checkSoloRateLimit(db, soloRateLimitKey(_soloUid, _ip), DEFAULT_RATE_LIMIT_PER_HOUR,
          DEFAULT_RATE_LIMIT_PER_DAY, _ip || null, true);
        if (!_srl.allowed) {
          return _srl.scope === "unidentified"
            ? soloUnidentifiedResponse(cors)
            : soloRateLimitedResponse(cors, _srl.retry_after_seconds, _srl.scope);
        }
      }
    }

    const raw = await callAI(safe, {
      systemPrompt: LOGBOOK_SYSTEM,
      temperature:  0.1,
      maxTokens:    512,
      jsonMode:     true,
    });

    // ★NO MODEL ANSWERED AND THE FORM WAS FILLED ANYWAY (2026-10-12, UFAI edge walk W4421). The chain's "{}" parsed as
    // an empty object, so the reply was ok:true with the person's raw words as the problem, "Breakdown / Corrective"
    // and "Open" - defaults no model chose - and the page filled them in marked as AI-filled. It is a refusal with
    // the cause; the page says its fields are unchanged.
    if (!aiAnswered(raw)) {
      return new Response(
        JSON.stringify({ error: "The voice assistant is not answering just now, so nothing was filled in.", code: "FILL_UNAVAILABLE" }),
        { status: 503, headers: { ...cors, "Content-Type": "application/json" } },
      );
    }
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(raw);
    } catch {
      return new Response(
        JSON.stringify({ error: "AI parsing failed. Try again.", raw }),
        { status: 500, headers: { ...cors, "Content-Type": "application/json" } },
      );
    }

    // Sanitize output: guarantee expected keys exist with safe defaults
    const result = {
      machine:          parsed.machine          ?? null,
      problem:          parsed.problem          ?? safe,
      root_cause:       parsed.root_cause       ?? null,
      // BRH.10 AI: the words beside the listed cause - analytics group by the list, the person keeps what they said
      root_cause_note:  parsed.root_cause_note  ?? null,
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
    // T2b: aggregate this HANDLED failure to wh_traces + non-leaky 500.
    return await failTracked(req, "voice-logbook-entry", "voice_logbook_entry_error", err);
  }
}));
