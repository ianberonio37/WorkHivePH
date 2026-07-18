import { serveObserved, failTracked } from "../_shared/observability.ts";
import { handleHealth } from "../_shared/health.ts";
import { logRequestStart } from "../_shared/logger.ts";

import { getCorsHeaders } from "../_shared/cors.ts";
import { log } from "../_shared/logger.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
// Arc R (LLM01/LLM10): this verify_jwt=false fn was a live OPEN LLM proxy — bound it.
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { resolveIdentity } from "../_shared/tenant-context.ts";
import { checkSoloRateLimit, soloRateLimitKey, soloRateLimitedResponse } from "../_shared/rate-limit.ts";

// contract: voice-model-call (registered in canonical_agent_contracts migration)

/**
 * Voice Model Call Edge Function (Phase 2)
 *
 * ⚠️ DEPRECATED / ORPHANED (verified 2026-07-12, AI Companion arc): this fn is
 * invoked by NO page and NO runtime caller. The header once said "Called by
 * voice-handler.js" but that caller does not exist — conversational replies now
 * route through the canonical `ai-gateway` (tenancy + PII + memory + rate-limit)
 * → the specialist agents, and the model fallback lives in the shared 19-model
 * `_shared/ai-chain.ts` PROVIDER_CHAIN. Kept (not deleted) so a deliberate
 * retirement can drop it + its `canonical_agent_contracts` row together; do NOT
 * wire new callers here — use ai-gateway.
 *
 * Multi-model orchestrator with free-tier fallback chain:
 * - Groq Scout (primary): meta-llama/llama-4-scout-17b-16e-instruct
 * - Cerebras Qwen (fallback 1): qwen2.5-7b-instruct
 * - Voyage AI (fallback 2): mistral-large-2411
 * - Jina AI (fallback 3): jina-ai/reader or similar
 *
 * Automatically falls back to next model if primary is rate-limited or down.
 *
 * Input:
 *   - messages: OpenAI-format messages array
 *   - model_strategy: "scout" (default) | "qwen" | "voyage" | "jina" | "round-robin"
 *   - max_tokens: response token limit (default 280)
 *   - temperature: sampling temperature (default 0.7)
 *
 * Output:
 *   - answer: model's response text
 *   - model_used: which model actually generated the response
 *   - latency_ms: how long the call took
 */

serveObserved("voice-model-call", async (req) => {
  // Arc T/T1: standard liveness /health (fn up + DB creds reachable).
  const _health = await handleHealth(req, "voice-model-call", async () => ({
    deps: [{ name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) }],
  }));
  if (_health) return _health;
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders });
  logRequestStart(req, "voice-model-call");  // I6 observability
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  const startTime = Date.now();

  try {
    const {
      messages,
      model_strategy = "scout",
      max_tokens = 280,
      temperature = 0.7,
    } = await req.json();

    if (!messages || !Array.isArray(messages)) {
      return new Response(
        JSON.stringify({ error: "Missing or invalid messages array" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Arc R (LLM01/LLM10): this fn ran verify_jwt=false with NO auth, NO rate-limit and
    // NO caps — a live, anonymous OPEN LLM proxy over the platform's provider keys (quota
    // theft + companion DoS + full attacker prompt control). Bind it by identity-or-IP
    // (solo bucket; service_role exempt), exactly like the equipment-label-ocr sibling.
    {
      const _rlDb = createClient(Deno.env.get("SUPABASE_URL") || "", Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "");
      const _id   = await resolveIdentity(_rlDb, req);
      if (!_id.isServiceRole) {
        const _ip = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim();
        const _rl = await checkSoloRateLimit(_rlDb, soloRateLimitKey(_id.authUid, _ip));
        if (!_rl.allowed) return soloRateLimitedResponse(corsHeaders);
      }
    }

    // Clamp the cost knobs + cap total prompt size (LLM10 unbounded consumption /
    // cost amplification). max_tokens server cap 512; total message content cap 8000 chars.
    const safeMaxTokens = Math.min(Math.max(1, Number(max_tokens) || 280), 512);
    const safeTemperature = Math.min(Math.max(0, Number(temperature) || 0.7), 2);
    const _totalChars = messages.reduce(
      (n: number, m: any) => n + (typeof m?.content === "string" ? m.content.length : 0), 0);
    if (_totalChars > 8000) {
      return new Response(
        JSON.stringify({ error: "messages payload too large (cap 8000 chars)" }),
        { status: 413, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Strategy determines which model(s) to try
    let strategies: string[] = [];
    if (model_strategy === "round-robin") {
      // Round-robin: try all four in order
      strategies = ["scout", "qwen", "voyage", "jina"];
    } else {
      // Named strategy + fallbacks
      strategies = [model_strategy, "qwen", "voyage", "jina"].filter(
        (s, idx, arr) => arr.indexOf(s) === idx
      );
    }

    // Try each strategy in order
    for (const strategy of strategies) {
      const { model, api_url, api_key } = _getModelConfig(strategy);

      if (!api_key) {
        log.warn(null, `Model ${strategy} not configured, skipping`);
        continue;
      }

      try {
        const resp = await _callModel(
          api_url,
          api_key,
          model,
          messages,
          safeMaxTokens,
          safeTemperature,
          5000 // 5s timeout
        );

        if (resp) {
          const latency = Date.now() - startTime;
          return new Response(
            JSON.stringify({
              answer: resp,
              model_used: strategy,
              latency_ms: latency,
            }),
            {
              status: 200,
              headers: { "Content-Type": "application/json" },
            }
          );
        }
      } catch (err) {
        log.warn(null, `Model ${strategy} failed:`, { detail: err });
        continue; // Try next strategy
      }
    }

    // All strategies failed
    return new Response(
      JSON.stringify({
        error: "All models failed (rate limited or down)",
        model_used: "none",
      }),
      {
        status: 503,
        headers: { "Content-Type": "application/json" },
      }
    );
  } catch (err) {
    // T2b: aggregate this HANDLED failure to wh_traces + non-leaky 500.
    return await failTracked(req, "voice-model-call", "voice_model_call_error", err);
  }
});

// Get model configuration (name, API URL, API key)
function _getModelConfig(
  strategy: string
): { model: string; api_url: string; api_key: string } {
  switch (strategy.toLowerCase()) {
    case "qwen":
      return {
        model: "qwen2.5-7b-instruct",
        api_url: "https://api.cerebras.ai/v1/chat/completions",
        api_key: Deno.env.get("CEREBRAS_API_KEY") || "",
      };
    case "voyage":
      return {
        model: "mistral-large-2411",
        api_url: "https://api.voyage.ai/v1/chat/completions",
        api_key: Deno.env.get("VOYAGE_API_KEY") || "",
      };
    case "jina":
      return {
        model: "jina-ai/reader",
        api_url: "https://api.jina.ai/v1/chat/completions",
        api_key: Deno.env.get("JINA_API_KEY") || "",
      };
    default: // scout
      return {
        model: "meta-llama/llama-4-scout-17b-16e-instruct",
        api_url: "https://api.groq.com/openai/v1/chat/completions",
        api_key: Deno.env.get("GROQ_API_KEY") || "",
      };
  }
}

// Call model via OpenAI-compatible API
async function _callModel(
  api_url: string,
  api_key: string,
  model: string,
  messages: any[],
  max_tokens: number,
  temperature: number,
  timeout_ms: number
): Promise<string | null> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeout_ms);

    const resp = await fetch(api_url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${api_key}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model,
        messages,
        max_tokens,
        temperature,
      }),
      signal: controller.signal,
    });

    clearTimeout(timeout);

    if (resp.status === 429) {
      // Rate limited
      throw new Error("Rate limited (429)");
    }

    if (resp.status !== 200) {
      throw new Error(`API error: ${resp.status}`);
    }

    const data = await resp.json();
    const answer = data.choices?.[0]?.message?.content || "";

    return answer.trim() || null;
  } catch (err) {
    throw err;
  }
}
