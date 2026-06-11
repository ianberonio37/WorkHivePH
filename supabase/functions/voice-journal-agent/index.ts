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
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
import { logAICost, estimateTokens } from "../_shared/cost-log.ts";
import { redactPII } from "../_shared/redactPII.ts";
// Persona Contract: one shared module across every conversational AI
// surface. See WORKHIVE_PERSONA_CONTRACT.md. Voice Journal runs in the
// "conversational" mode — full persona, freeform prose.
import { clampPersona, buildPersonaBlock } from "../_shared/persona.ts";

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

// Persona Contract: tone/voice/name come from the shared module so every
// conversational surface (voice-journal, floating-AI, assistant) feels
// like one companion. Voice Journal extends the shared "conversational"
// block with two Voice-Journal-only rules below (memory recall behavior
// + journal-finality guidance).
const VOICE_JOURNAL_EXTRA_RULES = `
Voice-Journal-specific rules:
- The memory block may include a "Past journal entries that look related to today's voice note" section. If the worker mentioned the same person, asset, feeling, or goal before, name it gently in one short sentence. Paraphrase only — never invent.
- If the memory shows a recent recurring theme, naming it is fine, but prefer the most relevant signal.
- GROUNDING: you cannot look up this worker's SAVED records from this surface (their logbook entries, PM history, KPI numbers, recurrence rates, OEE) - those live in the database, not in this conversation. If they ask about a stored record or a KPI you were never told, say plainly you cannot see their records from this voice surface and point them to the Work Assistant page, which can pull them. BUT a value the worker told you earlier in THIS conversation lives in your memory block, not the database - recall it and quote it back directly (see the Conversation memory rule above); that is never a record lookup. NEVER make up a record, a count, an OEE, an MTBF, or any KPI value, and never name an internal database view.

You will be given:
- The worker's latest spoken message
- The detected language code (ISO-639-1)
- A memory block with their recent turns, a rolling summary, and optionally a "Past journal entries" section

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

  // Persona Contract: ctx.persona wins (per-call override from the chip
  // picker); falls back to worker_profiles.preferred_persona via the
  // gateway-side identity layer (already in ctx if provided). Unknown
  // values clamp to DEFAULT_PERSONA.
  const personaKey = clampPersona(ctx.persona);
  const systemPrompt =
    buildPersonaBlock(personaKey, "conversational") +
    VOICE_JOURNAL_EXTRA_RULES;

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
      systemPrompt: systemPrompt,
      temperature:  0.55,
      maxTokens:    MAX_TOKENS_OUT,
      jsonMode:     false,
      // Sticky session (set by ai-gateway): keep this companion thread on one model.
      sessionKey:   typeof body.session_key === "string" ? body.session_key : undefined,
    });

    const trimmed = String(answer || "").trim();
    // Deterministic no-em-dash enforcement (OPT-PERSONA-04). The conversational persona rule bans em
    // dashes, but the LLM violates it probabilistically run-to-run; WAT says enforce a must-be-exact
    // output rule in CODE, not by re-asking the model. Em dash (U+2014) only -> ", " (a natural spoken
    // pause); en dash (U+2013) is left alone so numeric ranges like "3-6 months" survive.
    const clean = trimmed.replace(/\s*—\s*/g, ", ").replace(/,\s*,/g, ",").trim();
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
        prompt_tokens: estimateTokens(userBlock) + estimateTokens(systemPrompt),
        output_tokens: estimateTokens(trimmed),
        latency_ms:    latency,
        status:        trimmed ? "success" : "fallback",
      });
    }

    if (!trimmed) {
      return json(corsHeaders, 502, { error: "Empty answer from AI chain" });
    }

    return json(corsHeaders, 200, { answer: clean, lang } satisfies AgentResponse);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (_whWarmClient) {
      void logAICost(_whWarmClient, {
        fn:            "voice-journal-agent",
        hive_id:       typeof body.hive_id === "string" ? body.hive_id : null,
        worker_name:   null,
        model:         MODEL_VERSION,
        provider:      "chain",
        prompt_tokens: estimateTokens(userBlock) + estimateTokens(systemPrompt),
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
