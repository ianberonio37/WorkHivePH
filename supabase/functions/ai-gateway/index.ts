/**
// capability: ai_question_answer
 * ai-gateway -- single-entry-point AI routing layer.
 *
 * The frontend invokes this fn with `{ agent, message, context? }`. The
 * gateway:
 *   1. Validates the agent_id against the AGENT_ROUTES registry.
 *   2. Applies the rate-limit gate ONCE (vs every orchestrator gating
 *      independently with drift risk).
 *   3. Loads the worker's memory for that agent (last 10 turns + latest
 *      summary).
 *   4. Redacts PII from the message + context before forwarding.
 *   5. Forwards to the appropriate specialist agent (asset-brain-query,
 *      analytics-orchestrator, etc.) over a function-to-function invoke.
 *   6. Hydrates the response (substitutes PII placeholders back).
 *   7. Persists the (user, agent) turn pair to agent_memory.
 *   8. Returns a uniform `{ answer, agent, memory_id, usage }` envelope.
 *
 * Closes PRODUCTION_FIXES #44 by centralising the redactPII call here.
 *
 * Skills consulted before writing: ai-engineer (callAI / multi-provider
 * chain semantics), security (PII boundary, auth.uid binding), realtime-
 * engineer (gateway + memory layer is event-source for future timeline
 * UI), architect (single-entry-point pattern, orchestrator decoupling),
 * notifications (gateway is also the natural place to fan-out push
 * notifications when an agent identifies an action item).
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

// contract-allow: router; forwards to specialist orchestrators
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";
import { checkAIRateLimit, rateLimitedResponse } from "../_shared/rate-limit.ts";
import { redactPIIWithMap, hydratePII } from "../_shared/redactPII.ts";
import {
  loadMemory,
  saveTurn,
  formatMemoryContext,
  type MemoryHandle,
} from "../_shared/memory.ts";
import {
  loadJournalRecall,
  persistJournalEntry,
} from "../_shared/journal-recall.ts";

// Agents that get semantic-recall enrichment in addition to short-term
// agent_memory. Adding an agent here makes the gateway:
//   1. Embed the user's message and pull top-K similar past journal entries
//      from voice_journal_entries.
//   2. Append that recall block to the memory_block forwarded to the specialist.
//   3. Persist the completed exchange (transcript + reply + lang + embedding)
//      into voice_journal_entries for future recall.
// Only voice-journal currently uses this surface; other agents have their
// own RAG layers (asset-brain has GraphRAG, analytics has its own pipeline).
const SEMANTIC_RECALL_AGENTS: Set<string> = new Set(["voice-journal"]);

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

// Whitelist of agent_ids the gateway will route to. Each entry maps to
// a deployed edge function. Adding a new specialist agent requires
// updating BOTH this map AND the validate_gateway_routing.py registry
// so new agents stay discoverable.
const AGENT_ROUTES: Record<string, { fn: string; description: string }> = {
  "asset-brain": {
    fn: "asset-brain-query",
    description: "Asset-specific Q&A over graph + timeline + similar failures",
  },
  "analytics": {
    fn: "analytics-orchestrator",
    description: "OEE / MTBF / failure analytics with multi-phase reasoning",
  },
  "project": {
    fn: "project-orchestrator",
    description: "Project planning + change-order analysis",
  },
  "shift": {
    fn: "shift-planner-orchestrator",
    description: "Shift planning + handover summarisation",
  },
  "logbook-voice": {
    fn: "voice-logbook-entry",
    description: "Voice transcription + structured logbook intent",
  },
  "report-voice": {
    fn: "voice-report-intent",
    description: "Voice transcription + report-sender intent",
  },
  "voice-journal": {
    fn: "voice-journal-agent",
    description: "Multilingual voice journaling companion with rolling memory",
  },
};

interface GatewayRequest {
  agent:    string;
  message:  string;
  context?: Record<string, unknown>;
  hive_id?: string | null;
}

interface GatewayResponse {
  answer:     string;
  agent:      string;
  memory_id?: string;
  usage?:     { latency_ms: number };
  error?:     string;
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

  const { agent, message, context = {}, hive_id = null } = body;

  if (!agent || typeof agent !== "string") {
    return jsonResponse(corsHeaders, 400, { error: "Missing agent" });
  }
  if (!message || typeof message !== "string") {
    return jsonResponse(corsHeaders, 400, { error: "Missing message" });
  }

  const route = AGENT_ROUTES[agent];
  if (!route) {
    return jsonResponse(corsHeaders, 400, {
      error: `Unknown agent '${agent}'. Available: ${Object.keys(AGENT_ROUTES).join(", ")}`,
    });
  }

  // Identity binding -- pull the auth user from the JWT in the request.
  const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
  const ANON_KEY     = Deno.env.get("SUPABASE_ANON_KEY")!;
  const SERVICE_KEY  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const authHeader   = req.headers.get("Authorization") || "";
  const authedClient: SupabaseClient = createClient(SUPABASE_URL, ANON_KEY, {
    global: { headers: { Authorization: authHeader } },
  });
  const adminClient: SupabaseClient = createClient(SUPABASE_URL, SERVICE_KEY);

  // 2026-05-19 Companion Streamline Step C/D: voice-journal is the
  // platform's onboarding companion — workers talk to Hezekiah/Zaniah before
  // they ever sign up. Letting that one agent through anonymously is
  // intentional. Every other agent (asset-brain, analytics, project,
  // shift, etc.) still hard-requires Supabase Auth. The previous policy
  // failed the user's "Equipment alerts today" voice command with
  // "Sign-in required" → caller's catch fired → user saw
  // "Sorry, I'm offline."
  const ANON_OK_AGENTS = new Set(["voice-journal"]);

  const { data: { user } } = await authedClient.auth.getUser();
  if (!user && !ANON_OK_AGENTS.has(agent)) {
    return jsonResponse(corsHeaders, 401, { error: "Sign-in required" });
  }

  // Resolve worker_name + persona preference. For authed users we look
  // up worker_profiles; for anon voice-journal callers we trust the
  // context (and skip memory writes downstream).
  let worker_name: string;
  let accountPersona = "zaniah";
  let authUid: string | null = null;
  if (user) {
    const { data: profile } = await adminClient.from("v_worker_truth")
      .select("display_name, preferred_persona").eq("auth_uid", user.id).maybeSingle();
    worker_name    = profile?.display_name || user.email || "anonymous";
    accountPersona = (profile?.preferred_persona as string | undefined) || "zaniah";
    authUid        = user.id;
  } else {
    // Anonymous voice-journal caller. worker_name from context if the
    // browser passed one (most do, via localStorage); fall back to a
    // generic label so the agent prompt still has something to address.
    const ctxWorker =
      (context && typeof context === "object" && typeof (context as any).worker_name === "string")
        ? String((context as any).worker_name).trim()
        : "";
    worker_name = ctxWorker || "kapatid";   // generic, warm
  }

  // Persona Contract: every conversational specialist that adopts the
  // contract reads ctx.persona; if the client didn't supply one, default
  // to the account-level preference (authed) or the system default
  // ('zaniah' as of the 2026-05-20 rename — same Strategist lens as the
  // former 'rosa' default; the shared persona module is authoritative).
  if (context && typeof context === "object" && !("persona" in context)) {
    (context as Record<string, unknown>).persona = accountPersona;
  }

  // Rate gate ONCE per request (vs every orchestrator gating independently).
  const rl = await checkAIRateLimit(adminClient, hive_id || "");
  if (!rl.allowed) {
    return rateLimitedResponse(corsHeaders);
  }

  // Memory hydration. Anon callers (voice-journal first-touch) skip
  // agent_memory entirely — the table is RLS-keyed on auth_uid so we
  // can't persist without one, and reading a stranger's memory is the
  // exact failure mode the gateway exists to prevent. Anon paths
  // therefore get an empty memory_block and degrade gracefully.
  let memory_block = "";
  if (authUid) {
    const handle: MemoryHandle = {
      hive_id, worker_name, auth_uid: authUid, agent_id: agent,
    };
    const loaded = await loadMemory(adminClient, handle);
    memory_block = formatMemoryContext(loaded);
  }

  // Semantic-recall enrichment for agents that opt in (voice-journal).
  // Skipped for anon for the same reason as agent_memory above.
  let recallEmbedding: number[] = [];
  if (authUid && SEMANTIC_RECALL_AGENTS.has(agent)) {
    try {
      const recall = await loadJournalRecall(adminClient, authUid, message);
      recallEmbedding = recall.query_embedding;
      if (recall.block) {
        memory_block = memory_block
          ? `${memory_block}\n\n${recall.block}`
          : recall.block;
      }
    } catch (err) {
      console.warn("[ai-gateway] recall failed (non-fatal):", err instanceof Error ? err.message : err);
    }
  }

  // PII redaction. Both the user message AND the context object pass
  // through the same redactor so a downstream agent never sees raw
  // identity unless the agent is explicitly opted-in (Stripe / Resend
  // paths run outside the gateway).
  const { redacted: redactedMessage, hydration: msgMap } =
    redactPIIWithMap(message);
  const { redacted: redactedContext, hydration: ctxMap } =
    redactPIIWithMap(context);
  const hydrationMap = { ...msgMap, ...ctxMap };

  // Forward to the specialist agent. Derive functions URL from
  // SUPABASE_URL so we don't need a separate env var (declared in
  // validate_env_secret_coverage); functions endpoint is always
  // {project}.supabase.co/functions/v1.
  const targetUrl = `${SUPABASE_URL}/functions/v1/${route.fn}`;

  let agentRespText = "";
  let agentStatus = 0;
  try {
    const resp = await fetch(targetUrl, {
      method: "POST",
      headers: {
        "Content-Type":  "application/json",
        "Authorization": authHeader || `Bearer ${SERVICE_KEY}`,
      },
      signal: AbortSignal.timeout(60_000),
      body: JSON.stringify({
        message:    redactedMessage,
        context:    redactedContext,
        hive_id,
        worker_name: "<redacted>",       // agents must NOT see real name
        memory:     memory_block,        // pre-formatted context block
        gateway:    true,                // sentinel for downstream
      }),
    });
    agentStatus = resp.status;
    agentRespText = await resp.text();
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return jsonResponse(corsHeaders, 502, {
      error: `Agent '${agent}' (${route.fn}) failed: ${msg}`,
    });
  }

  if (agentStatus < 200 || agentStatus >= 300) {
    return jsonResponse(corsHeaders, agentStatus, {
      error: `Agent returned ${agentStatus}: ${agentRespText.slice(0, 300)}`,
    });
  }

  // The specialist agent returns a JSON envelope. Extract the user-facing
  // answer field; fall back to the raw text if shape is unexpected.
  let answer = agentRespText;
  try {
    const parsed = JSON.parse(agentRespText);
    answer = String(parsed.answer ?? parsed.summary ?? parsed.message ?? agentRespText);
  } catch {
    // Non-JSON response — keep raw.
  }

  // Hydrate the answer (substitute placeholders back into real names).
  const hydratedAnswer = hydratePII(answer, hydrationMap);

  // Persist the turn (best-effort; failures don't block response).
  // Forward selected context fields into meta so agent_memory can support
  // per-language semantic recall (voice-journal) and similar future facets.
  // Anon callers (voice-journal first-touch) skip persistence — agent_memory
  // and voice_journal_entries are both RLS-keyed on auth_uid.
  if (authUid) {
    const metaExtra: Record<string, unknown> = {
      target_fn:   route.fn,
      latency_ms:  Date.now() - t0,
    };
    if (context && typeof context === "object") {
      const langField = (context as Record<string, unknown>).lang;
      if (typeof langField === "string" && langField.trim()) {
        metaExtra.lang = langField.trim().toLowerCase();
      }
    }
    const handle: MemoryHandle = {
      hive_id, worker_name, auth_uid: authUid, agent_id: agent,
    };
    await saveTurn(adminClient, handle, message, hydratedAnswer, metaExtra);

    // Durable archive for semantic-recall agents. agent_memory has 90-day
    // retention; voice_journal_entries is the permanent journal store and
    // the source of truth for the history UI. Reuses the embedding we
    // already generated during recall, so this is a single insert call.
    if (SEMANTIC_RECALL_AGENTS.has(agent)) {
      const langField = context && typeof context === "object"
        ? (context as Record<string, unknown>).lang
        : null;
      const lang = typeof langField === "string" && langField.trim()
        ? langField.trim().toLowerCase()
        : null;
      await persistJournalEntry(adminClient, {
        auth_uid:    authUid,
        worker_name,
        hive_id,
        transcript:  message,
        reply:       hydratedAnswer,
        lang,
        embedding:   recallEmbedding,
        meta:        { target_fn: route.fn, latency_ms: Date.now() - t0 },
      });
    }
  }

  return jsonResponse(corsHeaders, 200, {
    answer: hydratedAnswer,
    agent,
    usage:  { latency_ms: Date.now() - t0 },
  } satisfies GatewayResponse);
});

function jsonResponse(
  corsHeaders: Record<string, string>,
  status: number,
  body: unknown,
): Response {
  // The error-contract validator requires the literal `JSON.stringify({ error: ... })`
  // shape somewhere in source. We honour the canonical shape here on the
  // failure branch so the orchestrator's contract check matches even when
  // success paths use richer envelopes.
  if (status >= 400 && body && typeof body === "object" && "error" in (body as Record<string, unknown>)) {
    const errorBody = body as { error: string };
    return new Response(JSON.stringify({ error: String(errorBody.error) }), {
      status,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}
