/**
// capability: voice_to_journal
 * voice-journal-agent - Specialist behind the gateway's "voice-journal" route.
 *
 * The voice journal is the worker's private spoken log. Each turn:
 *   1. Browser records audio, hits voice-transcribe (Whisper auto-language).
 *   2. Browser hits ai-gateway with { agent: "voice-journal", message, context: { lang } }.
 *   3. Gateway redacts PII, loads memory (last 10 turns + rolling summary),
 *      forwards to THIS function with { message, context, memory, gateway: true }.
 *   4. This function builds a journal companion prompt that:
 *        - Speaks back in the same language the user used.
 *        - Acknowledges what was shared in 1-3 sentences.
 *        - Asks at most one gentle follow-up to keep the journal flowing.
 *        - Surfaces a recurring theme when the memory block shows one.
 *   5. Returns { answer, lang } envelope. Gateway saves the turn pair to
 *      agent_memory with meta.lang for per-language semantic recall later.
 *
 * Notes:
 *  - No DB queries here. The journal is purely conversational; recall is
 *    already injected via the memory block built by the gateway.
 *  - jsonMode is off because the answer is freeform prose, not a schema.
 *  - The system prompt is a `const` for future prompt-cache compatibility.
 *
 * Skills consulted: ai-engineer (callAI defaults, 500-char transcript cap
 * already enforced upstream, system prompt as const), security (no PII
 * leak: worker_name comes in already redacted as "<redacted>"), mobile-
 * maestro (response targets browser speechSynthesis, so keep replies short).
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

// contract-allow: voice journal write + retrieval
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { callAI } from "../_shared/ai-chain.ts";
import { getCorsHeaders } from "../_shared/cors.ts";
import { logAICost, estimateTokens } from "../_shared/cost-log.ts";
import { redactPII } from "../_shared/redactPII.ts";

// Warm module-scope client (PRODUCTION_FIXES #46 pattern). Cost log writes
// service-role, RLS-bypass; no per-request createClient cost on warm cold-start.
const _WH_SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const _WH_SERVICE_KEY  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const _whWarmClient: SupabaseClient | null =
  _WH_SUPABASE_URL && _WH_SERVICE_KEY
    ? createClient(_WH_SUPABASE_URL, _WH_SERVICE_KEY)
    : null;
void _whWarmClient;

const MODEL_VERSION     = "voice-journal-v1";
const MAX_MESSAGE_CHARS = 500;        // matches gateway-side cap, prompt-injection safety
const MAX_TOKENS_OUT    = 280;        // keep TTS-friendly: ~30s spoken reply max

const LANGUAGE_NAMES: Record<string, string> = {
  en:  "English",
  tl:  "Filipino (Tagalog)",
  fil: "Filipino (Tagalog)",
  ceb: "Cebuano",
  ilo: "Ilocano",
  hil: "Hiligaynon",
  pam: "Kapampangan",
  war: "Waray",
  bik: "Bikol",
  pag: "Pangasinan",
};

const SYSTEM_PROMPT = `You are WorkHive Voice Journal, a private journaling companion for a single worker.

The worker speaks freely about their day, work, thoughts, lessons, frustrations, or wins. You are NOT a maintenance assistant in this mode and you do NOT diagnose, plan, or compute. Your job is to receive what they said, reflect briefly, and (optionally) ask one gentle follow-up.

Rules:
1. The worker may speak in English, Filipino (Tagalog), Cebuano, or any other Philippine language. UNDERSTAND any of these. Always REPLY in English — short, plain, factory-floor English. Never reply in any other language even if the detected language code says otherwise.
   - If the worker mixes English with a Philippine word (e.g. "bearing noise sa Conveyor 2"), still reply in English; you may mirror the Filipino word once if it carries meaning the worker chose deliberately.
   - Do not translate the worker's words back at them — reflect, don't echo.
2. Keep replies SHORT: 1 to 3 sentences. This will be spoken aloud, so brevity matters.
3. Acknowledge what was shared in your own words. Do not parrot the transcript verbatim.
4. The memory block may include a section titled "Past journal entries that look related to today's voice note". When it does, use those as semantic recall: if the worker mentioned the same person, asset, feeling, or goal before, gently name the connection in one short sentence. Quote at most a short paraphrase, never invent details that are not in the recalled text.
5. If the memory block also shows a recent recurring theme (last few turns), naming it is fine, but prioritize the more relevant signal between recent turns and the semantically recalled entries.
6. End with at most ONE open question to keep the journal flowing. Skip the question if the worker sounds final or tired.
7. Never invent facts about the worker's life, employer, machines, or schedule. Only reflect what is in the message or memory.
8. Never give medical, legal, financial, or safety advice. If the worker mentions self-harm or a crisis, respond with one calm sentence pointing to a real helpline and stop the journaling flow for this turn.
9. No em dashes. Use commas, colons, or split sentences.
10. Output plain prose. No JSON, no bullet points, no headings.

You will be given:
- The worker's latest spoken message
- The detected language code (ISO-639-1 or close)
- A memory block with their recent turns, a rolling summary, and optionally a "Past journal entries" section retrieved by semantic similarity

Reply with just the prose response, nothing else.`;

interface AgentRequest {
  message?:     string;
  context?:     Record<string, unknown>;
  memory?:      string;
  hive_id?:     string | null;
  worker_name?: string;
  gateway?:     boolean;
}

interface AgentResponse {
  answer: string;
  lang:   string;
  error?: string;
}

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);

  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders });
  }

  if (req.method !== "POST") {
    return json(corsHeaders, 405, { error: "POST only" });
  }

  let body: AgentRequest;
  try {
    body = await req.json();
  } catch {
    return json(corsHeaders, 400, { error: "Invalid JSON" });
  }

  const rawMessage = typeof body.message === "string" ? body.message.trim() : "";
  if (!rawMessage) {
    return json(corsHeaders, 400, { error: "Missing message" });
  }
  // Defence-in-depth: even when called via the gateway (which already redacts),
  // run redactPII again so a direct-from-cron or test caller cannot leak emails
  // or phone numbers to the LLM provider. The gateway-redacted "<redacted>"
  // tokens pass through unchanged.
  const message = redactPII(rawMessage.slice(0, MAX_MESSAGE_CHARS));

  const ctx = body.context && typeof body.context === "object" ? body.context : {};
  const rawLang = typeof ctx.lang === "string" ? ctx.lang.trim().toLowerCase() : "";
  // Clamp to supported languages. Whisper occasionally mis-tags short
  // multilingual phrases (e.g. an English sentence starting with "Hai"
  // gets tagged Indonesian). The voice journal only supports English +
  // Philippine languages; everything else falls back to English so the
  // user-facing lang chip stays meaningful and the prompt's "reply in
  // English" rule is consistent with the displayed detection.
  const lang     = LANGUAGE_NAMES[rawLang] ? rawLang : "en";
  const langName = LANGUAGE_NAMES[lang];

  // Memory block can contain raw worker_name slips if the gateway memory layer
  // wrote them; redact again here at the LLM boundary.
  const rawMemory = typeof body.memory === "string" && body.memory.trim()
    ? body.memory.trim()
    : "";
  const memoryBlock = rawMemory ? redactPII(rawMemory) : "(no prior journal entries yet)";

  const userBlock = [
    `Detected language: ${langName} (code: ${lang})`,
    `Memory block:`,
    memoryBlock,
    `---`,
    `Latest voice entry:`,
    message,
  ].join("\n");

  const t0 = Date.now();
  try {
    const answer = await callAI(userBlock, {
      systemPrompt: SYSTEM_PROMPT,
      temperature:  0.55,
      maxTokens:    MAX_TOKENS_OUT,
      jsonMode:     false,
    });

    const trimmed = String(answer || "").trim();
    const latency = Date.now() - t0;
    const hiveIdForLog =
      typeof body.hive_id === "string" && body.hive_id ? body.hive_id : null;

    if (_whWarmClient) {
      void logAICost(_whWarmClient, {
        fn:            "voice-journal-agent",
        hive_id:       hiveIdForLog,
        worker_name:   null,                // redacted upstream
        model:         MODEL_VERSION,
        provider:      "chain",
        prompt_tokens: estimateTokens(userBlock) + estimateTokens(SYSTEM_PROMPT),
        output_tokens: estimateTokens(trimmed),
        latency_ms:    latency,
        status:        trimmed ? "success" : "fallback",
      });
    }

    if (!trimmed) {
      return json(corsHeaders, 502, { error: "Empty answer from AI chain" });
    }

    return json(corsHeaders, 200, { answer: trimmed, lang } satisfies AgentResponse);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (_whWarmClient) {
      void logAICost(_whWarmClient, {
        fn:            "voice-journal-agent",
        hive_id:       typeof body.hive_id === "string" ? body.hive_id : null,
        worker_name:   null,
        model:         MODEL_VERSION,
        provider:      "chain",
        prompt_tokens: estimateTokens(userBlock) + estimateTokens(SYSTEM_PROMPT),
        latency_ms:    Date.now() - t0,
        status:        "failed",
      });
    }
    console.error("voice-journal-agent error:", msg);
    return json(corsHeaders, 502, { error: `Journal agent failed: ${msg}` });
  }
});

function json(
  corsHeaders: Record<string, string>,
  status: number,
  body: unknown,
): Response {
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
