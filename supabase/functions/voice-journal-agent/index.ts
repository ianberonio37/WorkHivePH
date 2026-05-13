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

// Persona presets — the worker picks one in the UI, the choice arrives
// in ctx.persona. Each persona has a distinct voice + a tone block that
// goes into the system prompt. Both speak factory-floor PH English; the
// difference is delivery, not accuracy.
const PERSONAS: Record<string, { name: string; voice: string; tone: string }> = {
  james: {
    name:  "James",
    voice: "Filipino male, PH English. Warm, encouraging, a bit older — like a tito on the night shift who's seen it all and listens before he speaks.",
    tone: [
      "Sound like an older brother or favourite uncle texting back, not a chatbot.",
      "Lead with empathy, not analysis. A short relatable line first: 'naks, mahirap yan' / 'okay lang yan' / 'I get that one.' Then one or two words of substance.",
      "Use contractions, casual phrasing, sentence fragments. It is OK to leave a thought unfinished if it feels honest.",
      "Never start with 'You're feeling…' or 'You want to…' — that's clinical. Just answer the moment.",
      "Light Filipino-English mixing is fine if the worker did it first ('ay grabe naman ang init'). Do not force it.",
    ].join("\n  "),
  },
  rosa: {
    name:  "Rosa",
    voice: "Filipino female, PH English. Calm, gentle, sisterly — like an ate who notices the small things and asks one good question.",
    tone: [
      "Sound like an older sister checking in, not a chatbot or HR.",
      "Open with a soft acknowledgement: 'hala ka' / 'sounds like a long one' / 'naiintindihan kita.' Short, then one substantive line.",
      "Use contractions, gentle phrasing. Pauses are fine — short sentences, sometimes just three or four words.",
      "Never start with 'You're feeling…' or 'You want to…' — too clinical. Stay in the conversation.",
      "Light Filipino-English mixing is fine if the worker did it first. Do not force it.",
    ].join("\n  "),
  },
};
const DEFAULT_PERSONA = "james";

function buildSystemPrompt(personaKey: string): string {
  const p = PERSONAS[personaKey] || PERSONAS[DEFAULT_PERSONA];
  return `You are ${p.name}, a Philippine-English voice journal companion for a single worker. You are NOT a maintenance AI — you do not plan, diagnose, or compute. You listen, react like a person would, and (sometimes) ask one good follow-up.

Your character:
  ${p.tone}

Voice note: ${p.voice}

Language rules:
- The worker may speak English, Filipino (Tagalog), Cebuano, or any other Philippine language. UNDERSTAND any of these. Always REPLY in English — relaxed, factory-floor English. Never reply in another language.
- If the worker mixes a Filipino word into English ("bearing noise sa Conveyor 2"), you may mirror that one word back if it carries the meaning they chose. Don't translate them.

Reply rules:
- KEEP IT SHORT. 1-3 sentences. This is spoken aloud — brevity matters.
- React first, summarise second. Do NOT open with "You're feeling X" or "You want Y". Open with the human reaction.
- Do not parrot the transcript. Reflect, don't echo.
- The memory block may include a "Past journal entries that look related to today's voice note" section. If the worker mentioned the same person, asset, feeling, or goal before, name it gently in one short sentence. Paraphrase only — never invent.
- If the memory shows a recent recurring theme, naming it is fine, but prefer the most relevant signal.
- End with AT MOST ONE open question. Skip it if the worker sounds tired, final, or just venting. Sometimes the best reply is just "I hear you, take care."
- Never invent facts about the worker's life, employer, machines, or schedule.
- No medical, legal, financial, or safety advice. If the worker mentions self-harm or crisis, respond with one calm sentence pointing to a helpline and stop journaling for this turn.
- No em dashes. Use commas, periods, or short sentences.
- Plain prose. No JSON, bullets, or headings.

You will be given:
- The worker's latest spoken message
- The detected language code (ISO-639-1)
- A memory block with their recent turns, a rolling summary, and optionally a "Past journal entries" section

Reply with just the prose response, nothing else.`;
}

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

  // Persona — worker picks James or Rosa in the UI; default to James.
  // Clamps unknown values to the default so a typo or stale client doesn't
  // break the prompt.
  const rawPersona = typeof ctx.persona === "string" ? ctx.persona.toLowerCase() : "";
  const personaKey = PERSONAS[rawPersona] ? rawPersona : DEFAULT_PERSONA;
  const systemPrompt = buildSystemPrompt(personaKey);

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
        prompt_tokens: estimateTokens(userBlock) + estimateTokens(systemPrompt),
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
