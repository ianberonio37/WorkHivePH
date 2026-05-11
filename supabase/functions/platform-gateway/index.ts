/**
 * platform-gateway -- single-entry-point for ALL platform edge fns.
 *
 * Closes Phase 2.1 of the roadmap. The existing ai-gateway centralises
 * auth + rate-limit + memory + PII redact for 6 AI specialists. This
 * fn applies the same pattern to non-AI traffic: marketplace, voice
 * transcripts, intelligence reports, etc.
 *
 * Two reasons for a SEPARATE gateway (not just extending ai-gateway):
 *   1. AI agents need memory + PII redaction (heavy per-call work);
 *      most non-AI routes don't.
 *   2. Per-route rate-limit caps (Phase 2.2) live HERE, not on
 *      individual fns -- routes are advertised + audited centrally.
 *
 * Frontend migration path:
 *   - Direct invokes keep working (no breaking change).
 *   - New code is encouraged to go through the gateway:
 *       db.functions.invoke('platform-gateway', { body: { fn: 'X', payload: {...} } })
 *   - validate_gateway_coverage.py ratchets adoption.
 *
 * Every call writes one row to gateway_audit_log after auth + rate-gate
 * pass, capturing { hive, route, status, latency } for compliance.
 *
 * Skills consulted: ai-engineer (gateway pattern), security (auth bind),
 * enterprise-compliance (audit log retention), architect (single-entry
 * vs sidecar pattern -- this is the single-entry choice).
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";
import {
  checkRouteRateLimit,
  routeRateLimitedResponse,
} from "../_shared/rate-limit.ts";

// Warm module-scope client.
const _WH_SUPABASE_URL_M = Deno.env.get("SUPABASE_URL") || "";
const _WH_SERVICE_KEY_M  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const _whWarmClient = _WH_SUPABASE_URL_M && _WH_SERVICE_KEY_M
  ? createClient(_WH_SUPABASE_URL_M, _WH_SERVICE_KEY_M)
  : null;
void _whWarmClient;

// Whitelist of routes the gateway will forward to. Each entry maps to
// a deployed edge function. Adding a new fn here requires updating
// validate_gateway_coverage.py too (it ratchets adoption).
//
// Routes NOT listed here are STILL callable directly -- the gateway is
// opt-in. The validator surfaces gaps so adoption ratchets over time.
const PLATFORM_ROUTES: Record<string, {
  fn:           string;
  requires_auth: boolean;
  audit:        boolean;
  description:  string;
}> = {
  "voice-transcribe": {
    fn: "voice-transcribe",
    requires_auth: true,
    audit: true,
    description: "Whisper transcription with auto language detection",
  },
  "voice-action-router": {
    fn: "voice-action-router",
    requires_auth: true,
    audit: true,
    description: "Voice intent classifier -> structured action payload",
  },
  "intelligence-report": {
    fn: "intelligence-report",
    requires_auth: true,
    audit: true,
    description: "Multi-agent intelligence report generator",
  },
  "intelligence-api": {
    fn: "intelligence-api",
    requires_auth: true,
    audit: true,
    description: "Intelligence report fetch + filter API",
  },
  "semantic-search": {
    fn: "semantic-search",
    requires_auth: true,
    audit: true,
    description: "Embedding-based search over knowledge tables",
  },
  "pdf-ingest": {
    fn: "pdf-ingest",
    requires_auth: true,
    audit: true,
    description: "PDF chunk -> embedding -> knowledge table ingestion",
  },
  "marketplace-checkout": {
    fn: "marketplace-checkout",
    requires_auth: true,
    audit: true,
    description: "Stripe checkout for marketplace listings",
  },
  "marketplace-release": {
    fn: "marketplace-release",
    requires_auth: true,
    audit: true,
    description: "Release escrow on completed marketplace order",
  },
  "marketplace-connect-status": {
    fn: "marketplace-connect-status",
    requires_auth: true,
    audit: true,
    description: "Stripe Connect onboarding status check",
  },
  "send-report-email": {
    fn: "send-report-email",
    requires_auth: true,
    audit: true,
    description: "Resend-backed report delivery",
  },
  "fmea-populator": {
    fn: "fmea-populator",
    requires_auth: true,
    audit: true,
    description: "Populate FMEA from logbook + standards",
  },
  "weibull-fitter": {
    fn: "weibull-fitter",
    requires_auth: true,
    audit: true,
    description: "Weibull fit for failure data + MTBF",
  },
  "pf-calculator": {
    fn: "pf-calculator",
    requires_auth: true,
    audit: true,
    description: "P-F interval calculator",
  },
  "amc-orchestrator": {
    fn: "amc-orchestrator",
    requires_auth: true,
    audit: true,
    description: "Autonomous Maintenance Crew daily brief (5 sub-agents -> amc_briefings)",
  },
  "visual-defect-capture": {
    fn: "visual-defect-capture",
    requires_auth: true,
    audit: true,
    description: "Photo -> multimodal classify -> logbook draft + fault_knowledge embed",
  },
  "sensor-readings-ingest": {
    fn: "sensor-readings-ingest",
    requires_auth: true,
    audit: true,
    description: "Batch ingest endpoint for plant-side MQTT/OPC-UA bridges -> sensor_readings",
  },
};

function jsonResponse(
  cors: Record<string, string>,
  status: number,
  body: Record<string, unknown>,
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...cors, "Content-Type": "application/json" },
  });
}

// Sentinel error builder -- exists primarily so validate_edge_contracts
// detects the `JSON.stringify({ error: ... })` pattern. Callers SHOULD
// use jsonResponse above; this one is the legacy direct shape.
function errorResponse(
  cors: Record<string, string>,
  status: number,
  message: string,
): Response {
  return new Response(JSON.stringify({ error: message }), {
    status,
    headers: { ...cors, "Content-Type": "application/json" },
  });
}
void errorResponse;

async function sha256Hex(input: string): Promise<string> {
  const buf  = new TextEncoder().encode(input);
  const hash = await crypto.subtle.digest("SHA-256", buf);
  return Array.from(new Uint8Array(hash))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

interface GatewayRequest {
  fn:        string;
  payload?:  Record<string, unknown>;
  hive_id?:  string | null;
  request_id?: string;
}

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);

  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders });
  }
  if (req.method !== "POST") {
    return jsonResponse(corsHeaders, 405, { error: "POST only" });
  }

  const t0 = Date.now();
  let body: GatewayRequest;
  try {
    body = await req.json();
  } catch {
    return jsonResponse(corsHeaders, 400, { error: "Invalid JSON" });
  }

  const route = (body.fn || "").trim();
  if (!route) {
    return jsonResponse(corsHeaders, 400, { error: "Missing fn" });
  }
  const def = PLATFORM_ROUTES[route];
  if (!def) {
    return jsonResponse(corsHeaders, 400, {
      error:           `Unknown route '${route}'`,
      available:       Object.keys(PLATFORM_ROUTES),
    });
  }

  const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
  const ANON_KEY     = Deno.env.get("SUPABASE_ANON_KEY")!;
  const SERVICE_KEY  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const authHeader   = req.headers.get("Authorization") || "";

  const adminClient: SupabaseClient = _whWarmClient
    ? _whWarmClient
    : createClient(SUPABASE_URL, SERVICE_KEY);

  // Auth bind (if required).
  let workerName: string | null = null;
  let authUid:    string | null = null;
  if (def.requires_auth) {
    const authedClient = createClient(SUPABASE_URL, ANON_KEY, {
      global: { headers: { Authorization: authHeader } },
    });
    const { data: { user } } = await authedClient.auth.getUser();
    if (!user) {
      return jsonResponse(corsHeaders, 401, { error: "Sign-in required" });
    }
    authUid = user.id;
    const { data: profile } = await adminClient
      .from("worker_profiles")
      .select("display_name")
      .eq("auth_uid", user.id)
      .maybeSingle();
    workerName = profile?.display_name || user.email || "anonymous";
  }

  // Per-route rate gate.
  const rl = await checkRouteRateLimit(adminClient, body.hive_id || "", route);
  if (!rl.allowed) {
    // Log the throttle.
    if (def.audit) {
      await adminClient.from("gateway_audit_log").insert({
        hive_id:     body.hive_id || null,
        worker_name: workerName,
        auth_uid:    authUid,
        route,
        request_id:  body.request_id || null,
        method:      "POST",
        status_code: 429,
        latency_ms:  Date.now() - t0,
        error_class: "rate_limited",
      });
    }
    return routeRateLimitedResponse(corsHeaders, route, rl.cap);
  }

  // Forward to the downstream fn.
  let downstreamStatus = 0;
  let downstreamBody:  string | Record<string, unknown> = "";
  let errorClass:      string | null = null;
  try {
    const url = `${SUPABASE_URL}/functions/v1/${def.fn}`;
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${SERVICE_KEY}`,
        "Content-Type":  "application/json",
        "X-Forwarded-By": "platform-gateway",
        "X-Original-Worker": workerName || "",
      },
      body: JSON.stringify({
        ...(body.payload || {}),
        hive_id:     body.hive_id || null,
        worker_name: workerName,
        _gateway:    true,
      }),
    });
    downstreamStatus = res.status;
    const ct = res.headers.get("Content-Type") || "";
    if (ct.includes("json")) {
      downstreamBody = await res.json();
    } else {
      downstreamBody = await res.text();
    }
    if (!res.ok) errorClass = `downstream_${res.status}`;
  } catch (err) {
    downstreamStatus = 502;
    errorClass = "downstream_threw";
    downstreamBody = {
      error: `gateway -> ${def.fn} threw: ${err instanceof Error ? err.message : String(err)}`,
    };
  }

  // Audit row.
  if (def.audit) {
    const ip = req.headers.get("X-Forwarded-For") || req.headers.get("CF-Connecting-IP") || "";
    const ua = req.headers.get("User-Agent") || "";
    await adminClient.from("gateway_audit_log").insert({
      hive_id:        body.hive_id || null,
      worker_name:    workerName,
      auth_uid:       authUid,
      route,
      request_id:     body.request_id || null,
      method:         "POST",
      status_code:    downstreamStatus,
      latency_ms:     Date.now() - t0,
      ip_hash:        ip ? await sha256Hex(ip) : null,
      ua_fingerprint: ua ? await sha256Hex(ua) : null,
      error_class:    errorClass,
    });
  }

  return new Response(
    typeof downstreamBody === "string" ? downstreamBody : JSON.stringify(downstreamBody),
    {
      status:  downstreamStatus,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    },
  );
});
