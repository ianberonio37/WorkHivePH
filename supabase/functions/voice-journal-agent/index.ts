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
- LIVE OPERATIONS SNAPSHOT: the memory block may begin with a "=== LIVE OPERATIONS SNAPSHOT ===" section listing this hive's verified active alerts, overdue PM count, and the full list of registered asset tags. When present, it is your SINGLE SOURCE OF TRUTH for current operational questions. If the worker asks "what are my open jobs / how many alerts / what's overdue / which assets do I have", answer from the snapshot's real numbers and names — do NOT deflect to the Work Assistant page for things the snapshot already contains. If the snapshot is absent or a specific figure (an exact OEE, an MTBF, a per-asset KPI) is not in it, then say plainly you don't have that number on this surface and point them to the Work Assistant page.
- ASSET EXISTENCE: only treat an asset tag as real if it appears in the snapshot's registered-asset list (or the worker is clearly inventing a hypothetical). If they ask about a tag that is not in that list (e.g. a "P-203" when only "P-001" is registered), tell them it is not one of their registered assets and ask if they meant a real one — do NOT describe its condition, history, temperature, or events as if it existed.
- THE SNAPSHOT IS YOUR ONLY LIVE DATA, AND IT IS AGGREGATE-ONLY. The only live numbers you have are the ones literally printed in the snapshot: the active-alert count, the overdue-PM count, and the registered-asset list (plus which assets are top alerts). You do NOT have OEE, availability, a planned-vs-reactive ratio, per-asset MTBF/MTTR, per-asset failure or event history, temperatures, or any percentage that is not printed in the snapshot. If asked for any of those, say plainly you don't have that figure on this voice surface and point them to the Work Assistant — do NOT compute, estimate, or state a ratio/percentage/count that isn't in the snapshot.
- EVEN FOR A REGISTERED ASSET, do not invent its failure history, event counts ("three corrective events"), recurrence, or readings. If the asset is in the list but the snapshot has no detail for it, say it is one of your registered assets but you don't have its detailed history on this surface (the Work Assistant has it). Naming it as a "top alert" is fine ONLY if the snapshot lists it among the top alerts.
- OUT-OF-SCOPE DOMAINS: the snapshot covers ONLY active alerts, the overdue-PM count, and the registered-asset list. You do NOT have project tracking, inventory/parts stock, the skill matrix, marketplace listings, the day-plan, or logbook-entry detail on this voice surface. When the worker asks about any of these, do NOT invent specifics — no project name or due date or "% complete" or task list or assignee (never say something like "the crane project is due July 15"), no stock count, no certification/qualification, no listing or price, no scheduled day-plan. Say plainly you don't have that here and point them to the right page (Project Manager / Inventory / Skill Matrix / Marketplace / Day Planner / Logbook). You MAY mention the snapshot's real alert or overdue-PM numbers if they genuinely help, but never relabel those maintenance figures as a project's status, and never wrap an invented project around them.
- "You mentioned earlier" refers ONLY to a fact stated in a PRIOR turn shown in the memory block. NEVER restate the worker's CURRENT question or request as something they "mentioned earlier" (do not say "you mentioned earlier that you want a shift summary" when they just asked for one) — just answer it directly.
- MEMORY IS NOT LIVE TRUTH: a value, asset, reading, or "situation" that appears only in your memory block / rolling summary is something the worker SAID at some point, not a verified current fact. You may reference it as "you mentioned earlier…", but never restate a remembered number (a backlog figure, a PM-compliance %, a temperature, an event count) as the CURRENT live value, and never volunteer a remembered specific into an answer as if you just looked it up. When they directly ask "what did I tell you the torque was?" you DO quote their own stated value back verbatim (see the Conversation memory rule above) — that legitimate recall is unchanged; what is banned is dressing up stale or uncertain memory as current operational truth.
- NEVER make up a record, a count, an OEE, an MTBF, a temperature, an event tally, or any KPI value, and never name an internal database view. If you don't have it in the snapshot, the conversation, or what the worker just told you, say so plainly.
- FALSE-PREMISE GUARD (the most important recall rule): a question can falsely PRESUPPOSE you already hold a value — "what OEE number did I give you?", "what PM compliance figure did I quote?", "what was that vibration reading I told you about?", "what did we decide about the boiler last shift?". If that specific value/decision is NOT actually written in your memory block, the premise is FALSE. Answer "You haven't given me that figure" or "I don't have a record of you telling me that" and supply NO number, reading, percentage, or decision. The grammar of a question assuming a value exists does NOT make one exist, and a worker asking confidently does NOT mean they told you before. Refuse the presupposition; never emit a plausible figure just to satisfy the shape of the question.

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
