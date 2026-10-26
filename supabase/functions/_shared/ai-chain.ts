// Multi-provider AI fallback chain for WorkHive edge functions.
// All providers use OpenAI-compatible chat completions format.
// Each API key is read from env — missing keys are silently skipped.
// Order: fastest / most generous limits first, deeper fallbacks last.
// Only permanently free tiers — no credits that expire.
//
// AI_ASSET_VERSION: 13
// v12 (2026-10-09): no model or order change. Exports aiAnswered(): the chain's "{}" (every provider failed, or a
// local walk asked for no model) is not an answer, so free-text callers stop printing "{}" as a reply or a summary.
// v11 (2026-10-08, LM-O follow-up): no model or order change. Every SERVED call is reported to the request's model-call
// collector (reportModelCall - one ai_cost_log row per call, written by serveObserved), and now a walk that EXHAUSTS
// every slot is reported too (reportModelCallFailed: one failed row naming each slot asked and how it answered, and the
// time the caller waited). Each served row also carries the slots asked before it (providers_tried).
// v10 (2026-10-08, same day): Cerebras is OUT of the platform - not parked, removed from every chain copy, caller and
// health check (validate_ai_chain_models_snapshot fails if a Cerebras entry comes back). Its lost slots: Google's
// gemini-3.1-flash-lite (a separate per-model free quota from the 2.5 pair; answered the distiller's JSON request 200
// in 3.3 s on this key) beside v9's mistral-small-latest. And callAIMultimodal now fails over like callAI: parked slots
// skipped, failures classified and parked per model, successes recorded, last-resort entries kept last.
// v9 (2026-10-08, grounding eval re-run): nearly every answer came from mistral codestral-latest, the LAST resort.
// Four causes, each measured. (1) Cerebras answered 402 payment_required to every call since 2026-09-10 (480 in the
// runtime log, not one answer) - both entries removed, gpt-oss-120b's slot re-filled by mistral-small-latest.
// (2) Groq gpt-oss answered 400 json_validate_failed with failed_generation "" - its default reasoning spent the whole
// max_tokens budget (320 on the memory distiller) and left no JSON; reasoning_effort "low" -> 200, 37 reasoning tokens.
// (3) every non-429 error parked the WHOLE provider, so one model's bad JSON parked all of Groq. Failures are now
// classified (classifyProviderFailure): permanent ones park for hours and are skipped for the rest of the call, and a
// model's own failure parks only that model. (4) reorderChain's penalty sort ran across the whole chain and lifted a
// never-tried last resort (penalty 0) above every general model that had failed once (penalty 3), and the herd-spread
// then shuffled it among them - so under load codestral led. Last-resort entries now stay behind every general entry,
// and the spread never crosses a task profile's preferred set.
// v8 (2026-10-07, same walk, LM151): under the walk's load Groq and Gemini rate-limited and a person's maintenance
// question fell through to mistral codestral-latest - a CODE model - which denied a machine listed two lines up in its
// own grounding. Code-specialist entries (codestral, laguna) are now LAST RESORTS for every task except code/SQL: the
// general order tries every conversational model first, and the code_or_sql_generation profile still puts codestral
// first. Nothing is removed - when everything else is down a code model's answer is still better than none.
// AI_ASSET_VERSION history continues below.
// v13 (2026-10-26, OWN dependency lens): a provider that times out is dead for the rest of the call (a slow Google was
// asked once per model - 75 s, the answer arriving after the request had failed); the walk has a 50 s budget and
// degrades to the honest sentence; an unusable 200 is not re-asked. Each served call reports its record (LM-O).
// v7 (2026-10-07, the LLM layer's live Grounding walk, §LM.2): three repairs, each measured by tools/ping_ai_chain.py or
// a live walk. (1) openrouter qwen3.8-27b:free is gone (404) -> dots-3-note-preview:free, the only live :free model that
// reports an image input and answers through the API. (2) nemotron-3.5-lightning:free answered with its own reasoning
// trace as the content ("Here's a thinking process: 1. Analyz...") and took 96 s on a one-word reply - replaced by
// laguna-s-2.1:free, and the router's long-synthesis rows now prefer nemotron-3-ultra (1M context, clean answers).
// (3) gemini-2.5-flash THINKS by default and its hidden reasoning spends max_tokens: at a 120-token budget it returned
// "A pump" (2 visible tokens, finish_reason length), and on the hive board a companion answer reached the person as
// "ZQX 9471 is still not one". Its entry now asks for no thinking, and ANY entry whose answer ran out of budget almost
// at once is skipped to the next provider instead of served half-written. Each served line also logs the provider's
// own token count - callAI writes nothing to ai_cost_log, so until it does that line is the only record of the spend.
// v6 (2026-09-28): FOUR more entries had gone dead since v5 (groq qwen3.6-27b + compound-mini,
// cerebras gemma-4-31b, openrouter nex-n2.5-mini) - and, one screen down, ALL TWELVE TASK_PROFILES
// still named the v4 model IDs, so the tiered router had been silently reordering nothing since v5.
// Three of the four dead entries had no live equivalent at their provider and were removed rather
// than back-filled with a model built for another job; the fourth (the chain's last vision slot)
// was replaced from OpenRouter's live :free list by reported input_modalities. 15 entries now
// (counted by validate_ai_chain_mirror.py, not by hand).
// v5 (2026-09-10): ELEVEN of the eighteen entries named models their providers no longer serve -
// 4 of 6 Groq, all 3 Cerebras, 1 Mistral, 3 of 6 OpenRouter - measured against each provider's own
// /models endpoint. Every AI call collected four 404s before one answered; the first entry now
// answers in 0.44s. Replacements are all permanently-free tiers, and `vision` is placed from the
// providers' reported `input_modalities` rather than inferred from a family name.
// C5 (Self-Improving Gate) — bump this integer whenever the model chain,
// provider order, judge model, or any other content the eval gate scores
// against changes. The ai-asset-versioning validator FAILs if the file
// hash moves without this bumping. Owner: AI Engineer.

interface ProviderEntry {
  provider: string;
  baseUrl: string;
  model: string;
  envKey: string;
  maxTokensCap?: number;        // hard cap on OUTPUT tokens for providers with small context
  contextCap?: number;          // TOTAL context window (in + out). Used for the pre-skip below. Omit = effectively unlimited.
  extraHeaders?: Record<string, string>;
  vision?: boolean;             // true if this model accepts image_url content blocks
  extraBody?: Record<string, unknown>;   // provider-specific request fields (e.g. reasoning_effort for a thinking model)
  lastResort?: boolean;         // a specialist (code) model: tried after every general model unless the task asks for it
}

// Rough token estimate (~4 chars/token, the standard heuristic for English +
// light JSON). Used only for the context-fit pre-skip — it never needs to be
// exact, just conservative enough to catch a prompt that provably won't fit a
// small-context model before we waste a round-trip discovering the 413.
export function estimateTokens(text: string): number {
  if (!text) return 0;
  return Math.ceil(text.length / 4);
}

const PROVIDER_CHAIN: ProviderEntry[] = [
  // ── Tier 1: Groq — custom LPU hardware, fastest inference ──────────────────
  // ★SEVEN OF THE FIRST NINE ENTRIES WERE MODELS THAT NO LONGER EXIST (measured 2026-09-10 against
  // each provider's own /models endpoint, with this platform's own working keys). The four Groq
  // names below were `meta-llama/llama-4-scout-17b-16e-instruct`, `llama-3.3-70b-versatile`,
  // `qwen/qwen3-32b` and `llama-3.1-8b-instant`, and ALL THREE Cerebras names were dead too - so
  // every AI call on the platform spent four round-trips collecting 404s before `openai/gpt-oss-20b`
  // answered, and the whole Cerebras tier was decoration. Nothing reported it: the gate that exists
  // to forbid deprecated model IDs read the key as `"model"` while this file writes it bare, so it
  // had been checking its 14-name deny-list against ZERO models for its entire life. A deny-list is
  // the wrong shape anyway - it only catches a name someone remembered to add - so
  // `validate_groq_fallback.check_models_are_live` now ASKS each provider and fails on any name it
  // does not serve. Every model below was present in that live list when written.
  // Vision is no longer a guess either: the provider reports `input_modalities`, and only the two
  // qwen entries accept images, so `vision: true` sits exactly where the provider says it belongs.
  // Qwen3.8 27B: 131K context, accepts text AND image, tools + json_mode.
  { provider: "groq", baseUrl: "https://api.groq.com/openai/v1", model: "qwen/qwen3.8-27b",                          envKey: "GROQ_API_KEY", vision: true },
  // v6 (2026-09-28): `qwen/qwen3.6-27b` sat here as "the vision fallback" and Groq had stopped
  // serving it. Asked today, Groq's /models returns ELEVEN ids and only ONE of them accepts images
  // (qwen3.8-27b, above) — the rest are the two gpt-oss chat models, a safeguard classifier, an
  // Arabic 4K model, and TTS/ASR/prompt-guard endpoints that are not chat at all. So Groq has no
  // second vision model to fall back to, and inventing one here is what produced this 404 in the
  // first place. The vision fallback is now carried by the providers that actually report an image
  // modality: gemini-2.5-flash, gemma-4-31b-it:free, gemma-4-26b-a4b-it:free and dots-3-note-preview:free.
  // GPT-OSS 20B: strict JSON schema adherence (structured_outputs), 131K context, cheapest per token.
  // ★v9 (2026-10-08): reasoning_effort "low" on BOTH gpt-oss entries. gpt-oss reasons before it answers and Groq counts
  // that reasoning inside max_tokens, so at the memory distiller's 320-token budget the default effort spent all of it on
  // thinking and Groq answered 400 json_validate_failed with failed_generation "" - 71 times in 30 h of runtime log, on
  // analytics-orchestrator and ai-gateway alike. Reproduced with one request; the SAME request at "low" answered 200 with
  // 37 reasoning tokens and valid JSON. The prompt was never the problem: it already says "Respond JSON only".
  { provider: "groq", baseUrl: "https://api.groq.com/openai/v1", model: "openai/gpt-oss-20b",                        envKey: "GROQ_API_KEY", extraBody: { reasoning_effort: "low" } },
  // GPT-OSS 120B: largest on the Groq free tier, also structured_outputs — last quality resort.
  { provider: "groq", baseUrl: "https://api.groq.com/openai/v1", model: "openai/gpt-oss-120b",                       envKey: "GROQ_API_KEY", extraBody: { reasoning_effort: "low" } },
  // v6 (2026-09-28): `groq/compound-mini` was here and Groq no longer serves it either. Of the
  // eleven ids Groq returns today the only general chat models are qwen3.8-27b and the two gpt-oss
  // entries — all three already above — so there is nothing smaller to fall back to. Substituting
  // `allam-2-7b` (Arabic, 4K context) or `gpt-oss-safeguard-20b` (a safety classifier) would keep
  // the entry count up while sending WorkHive's prompts to a model built for another job.

  // ── (Tier 2 was Cerebras: REMOVED from the platform, v9/v10, 2026-10-08) ─────────────────────────────
  // Every chat call with the platform's key answered 402 payment_required from 2026-09-10 on - 480 in the runtime log,
  // not one answer - so the tier was two wasted round-trips per call. The provider is gone from every chain copy and
  // caller, and tools/validate_ai_chain_models_snapshot.py FAILS if a Cerebras entry returns. Its slots were re-filled
  // by gemini-3.1-flash-lite (Google tier) and mistral-small-latest (Mistral tier).

  // NOTE: SambaNova was evaluated (FreeLLMAPI lists it) but REJECTED — its free
  // tier is $5 of credits that expire in 30 days, not a permanently-free tier.
  // Violates the no-expiring-credits rule (validate_groq_fallback.py L4).

  // ── Tier 3: Google Gemini — OpenAI-compat endpoint, 250K TPM, vision ────────
  // Low RPD on the free tier so it sits mid-chain; high quality + multimodal.
  // Use an AI Studio key (aistudio.google.com), NOT a GCP Console key (limit:0).
  { provider: "google", baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai", model: "gemini-2.5-flash",      envKey: "GEMINI_API_KEY", vision: true, extraBody: { reasoning_effort: "none" } },
  // v10 (2026-10-08): replaces lost Cerebras capacity. Google's free quotas are PER MODEL, so this is a pool the two
  // 2.5 entries do not drain (both were 429 that day while this answered). It thinks by default - "low" kept the
  // memory distiller's 320-token JSON answer whole (136 visible tokens, finish stop, 3.3 s). gemini-3.5-flash was the
  // larger candidate and answered 503 "high demand" twice, so it is not here. vision left off until an image call is
  // measured on it.
  { provider: "google", baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai", model: "gemini-3.1-flash-lite", envKey: "GEMINI_API_KEY", extraBody: { reasoning_effort: "low" } },
  { provider: "google", baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai", model: "gemini-2.5-flash-lite", envKey: "GEMINI_API_KEY", vision: true },

  // ── Tier 4: Mistral — 500K TPM but only 2 RPM, OpenAI-compatible ────────────
  // Codestral is strong for code / SQL generation (see TASK_PROFILES).
  { provider: "mistral", baseUrl: "https://api.mistral.ai/v1", model: "mistral-medium-latest", envKey: "MISTRAL_API_KEY" },
  // v9 (2026-10-08): fills a slot Cerebras held. Mistral's free tier lists mistral-small-latest (= mistral-
  // small-2603, which magistral-small-latest also resolves to: the general model with reasoning) with completion_chat
  // and a 262K context. MEASURED STATE (2026-10-08, three times that day incl. a paced `ping_ai_chain.py --only mistral`):
  // 429 "Rate limit exceeded" (code 1300), as was mistral-medium-latest, while codestral-latest answered 200 on the same
  // key - so Mistral's free limits are at least partly per model, and this entry has not yet been seen answering. It
  // stays because it is listed and free and its 429 costs ~0.4 s before the chain moves on (and parks the model).
  { provider: "mistral", baseUrl: "https://api.mistral.ai/v1", model: "mistral-small-latest",  envKey: "MISTRAL_API_KEY" },
  { provider: "mistral", baseUrl: "https://api.mistral.ai/v1", model: "codestral-latest",     envKey: "MISTRAL_API_KEY", lastResort: true },

  // ── Tier 5: OpenRouter — :free models, $0/token, 200 req/day ────────────────
  // Gemma 3/4 family supports vision via OpenAI-compatible image_url blocks.
  { provider: "openrouter", baseUrl: "https://openrouter.ai/api/v1", model: "nvidia/nemotron-3-super-120b-a12b:free",    envKey: "OPENROUTER_API_KEY", extraHeaders: { "HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive" } },
  { provider: "openrouter", baseUrl: "https://openrouter.ai/api/v1", model: "google/gemma-4-31b-it:free",                envKey: "OPENROUTER_API_KEY", extraHeaders: { "HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive" }, vision: true },
  // 2026-10-07: was nvidia/nemotron-3.5-lightning:free, which answers with its reasoning trace as the content and
  // took 96 s on a one-word reply. poolside/laguna-s-2.1:free answered "OK." in 3.8 s (code-leaning, text only).
  { provider: "openrouter", baseUrl: "https://openrouter.ai/api/v1", model: "poolside/laguna-s-2.1:free",                          envKey: "OPENROUTER_API_KEY", extraHeaders: { "HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive" }, lastResort: true },
  { provider: "openrouter", baseUrl: "https://openrouter.ai/api/v1", model: "google/gemma-4-26b-a4b-it:free",            envKey: "OPENROUTER_API_KEY", extraHeaders: { "HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive" }, vision: true },
  { provider: "openrouter", baseUrl: "https://openrouter.ai/api/v1", model: "nvidia/nemotron-3-ultra-550b-a55b:free",    envKey: "OPENROUTER_API_KEY", extraHeaders: { "HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive" } },
  // v6 (2026-09-28): was `nex-agi/nex-n2.5-mini:free`, which OpenRouter has stopped serving. This
  // slot is the chain's last vision entry, so the replacement is picked from the live :free list by
  // its REPORTED input_modalities (text,image,video), not by family name: qwen3.8-27b:free, 262K.
  // v7 (2026-10-07): qwen3.8-27b:free is gone too (check_models_are_live: 404). Of the live :free models that
  // report an image input, thinkingmachines/inkling(-small) answer 403 "only available on agentic harnesses",
  // nemotron-3.5-content-safety is a classifier, and nemotron-3-nano-omni-...-reasoning returned no content at 96
  // tokens. dots-3-note-preview answered "OK" in 3.3 s (text,image; 512K). A PREVIEW can vanish - the liveness
  // check will say so the day it does.
  { provider: "openrouter", baseUrl: "https://openrouter.ai/api/v1", model: "dots-studio/dots-3-note-preview:free",     envKey: "OPENROUTER_API_KEY", extraHeaders: { "HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive" }, vision: true },
];

// ── Phase 4 (AGENTIC_RAG_ROADMAP.md): Tiered Model Router ──────────────────
//
// TASK_PROFILES maps a task profile name to an ordered list of model
// substrings that should be tried first. The base PROVIDER_CHAIN is
// reordered so models matching the profile are tried first, then the
// remaining chain follows as fallback. All profiles map to free-tier
// models only — there is no paid-tier escalation, ever.
//
// When taskProfile is omitted, callAI behaves exactly as before (Scout-17B
// primary). Existing edge functions need no changes.
//
// Match is by SUBSTRING in entry.model (case-insensitive) so we don't have
// to keep two parallel lists in sync with PROVIDER_CHAIN.
//
// See AGENTIC_RAG_ROADMAP.md §5 Phase 4 and feedback_free_tier_only_models.md
// for the canonical task → model map.
// ★EVERY PROFILE BELOW NAMED A MODEL THE CHAIN NO LONGER HELD, SO THE WHOLE ROUTER WAS A NO-OP
// (2026-09-28). The v5 pass removed eleven retired model names from PROVIDER_CHAIN and did not look
// one screen further down, where the SAME eleven names were the entire vocabulary of TASK_PROFILES:
// `llama-3.1-8b-instant`, `llama-3.3-70b-versatile`, `qwen/qwen3-32b`, `llama-4-scout-17b-16e-instruct`.
// reorderChain matches these as substrings of entry.model, so `matched` came back EMPTY for all
// twelve profiles and `ordered` was just the base chain — every caller that carefully passed a
// taskProfile got the default order, silently, and had done since v5. Nothing failed: the router is
// a reordering, so when it does nothing the calls still succeed, just on the wrong tier.
// validate_model_router.py reported 9/9 PASS throughout, because M03 checked these values against
// its OWN hand-maintained ALLOWED_MODEL_SUBSTRINGS list — which still listed the dead names. Two
// stale lists agreeing with each other is not a check. M03 now derives the allowed set from
// PROVIDER_CHAIN itself and M11 fails when any profile value matches no live entry, so a profile
// cannot outlive the model it names again. Every substring below was matched against the chain by
// that gate. Kin: feedback_a_declared_mechanism_is_not_a_mechanism, feedback_seven_of_nine_models_did_not_exist.
export const TASK_PROFILES: Record<string, string[]> = {
  // Cheap, fast tasks → the smallest general chat model the chain actually holds (Groq LPU, 131K),
  // then Gemini Flash-Lite. "gpt-oss-20b" cannot collide with "gpt-oss-120b": the char after
  // "gpt-oss-" is "1" there, so the substring does not occur.
  intent_classification:   ["gpt-oss-20b", "gemini-2.5-flash-lite"],
  slot_extraction:         ["gpt-oss-20b", "gemini-2.5-flash-lite"],
  single_fact_retrieval:   ["gpt-oss-20b", "gemini-2.5-flash-lite"],
  orchestrator_router:     ["gpt-oss-20b", "gemini-2.5-flash-lite"],
  chunk_grader:            ["gpt-oss-20b", "gemini-2.5-flash-lite"],
  hallucination_checker:   ["gpt-oss-20b", "gemini-2.5-flash-lite"],
  temporal_subagent:       ["gpt-oss-20b", "gemini-2.5-flash-lite"],
  // Mid-tier reasoning. "3.8-27b" matches Groq's qwen/qwen3.8-27b.
  multi_step_orchestration: ["gpt-oss-120b", "3.8-27b"],
  // Heavy synthesis / long output → the largest context the free tiers offer: gpt-oss-120b is 131K,
  // nemotron-3-ultra is 1M. (2026-10-07: was nemotron-3.5-lightning, also 1M - but it returns its reasoning AS the
  // answer, "Here's a thinking process: 1. Analyz...", and took 96 s on a one-word reply. Measured by
  // tools/ping_ai_chain.py; ultra answered "OK" in 1.3-1.8 s.)
  synthesis_long_output:   ["gpt-oss-120b", "nemotron-3-ultra"],
  temporal_fold:           ["gpt-oss-120b", "nemotron-3-ultra"],
  narrative_report:        ["gpt-oss-120b", "gemini-2.5-flash"],
  // Specialised — Codestral is Mistral's code/SQL model (see the Tier 4 note above).
  code_or_sql_generation:  ["codestral-latest", "gpt-oss-120b"],
};

// Provider Health Autoswitch logic lives in _shared/provider-health.ts.
// Extracted from this file because validate_groq_fallback.py's regex
// (`{ ... provider ... }`) mis-parses helper function bodies as chain
// entries. The autoswitch wraps callAI's per-iteration logic below.
import {
  recordSlotFailure,
  recordSlotSuccess,
  isSlotBlocked,
  getSlotPenalty,
  getStickyModel,
  setStickyModel,
} from "./provider-health.ts";
// LM-O (2026-10-08): every SERVED call is handed to the request's model-call collector (_shared/model-calls.ts);
// serveObserved writes its one ai_cost_log row with fn, hive, user, provider, model, tokens, latency and trace id.
// A walk that exhausts every slot is handed over too (reportModelCallFailed): one failed row, never none.
import { reportModelCall, reportModelCallFailed, modelCallsRefused } from "./model-calls.ts";


export function reorderChain(taskProfile?: string, spread = false): ProviderEntry[] {
  // ── Step 1: task-profile ordering (or the static chain) ──────────────────
  // Always build a NEW array — never return/mutate the PROVIDER_CHAIN const.
  let ordered: ProviderEntry[];
  const preferred = taskProfile ? TASK_PROFILES[taskProfile] : undefined;
  if (!preferred || !preferred.length) {
    ordered = [...PROVIDER_CHAIN];
  } else {
    const matched: ProviderEntry[] = [];
    const rest:    ProviderEntry[] = [];
    for (const entry of PROVIDER_CHAIN) {
      const isPreferred = preferred.some(p => entry.model.toLowerCase().includes(p.toLowerCase()));
      if (isPreferred) matched.push(entry); else rest.push(entry);
    }
    // Within matched: keep the order specified in `preferred` (most preferred first).
    matched.sort((a, b) => {
      const ai = preferred.findIndex(p => a.model.toLowerCase().includes(p.toLowerCase()));
      const bi = preferred.findIndex(p => b.model.toLowerCase().includes(p.toLowerCase()));
      return ai - bi;
    });
    ordered = [...matched, ...rest];
  }
  // ── Step 1b: specialists last (v8) - a code model is a last resort for every task that did not ask for it ──
  {
    const pref = taskProfile ? (TASK_PROFILES[taskProfile] || []) : [];
    const asked = (e: ProviderEntry) => pref.some((p) => e.model.toLowerCase().includes(p.toLowerCase()));
    ordered = [...ordered.filter((e) => !e.lastResort || asked(e)), ...ordered.filter((e) => e.lastResort && !asked(e))];
  }

  // ── Step 2: live demotion by slot penalty (FreeLLMAPI dynamic-priority) ───
  // Stable-sort by current slot penalty so a recently-429'd provider sinks in
  // the order WITHOUT being hard-skipped (hard skip is isSlotBlocked's job).
  // Snapshot the penalty once per slot first, because getSlotPenalty applies
  // time-decay on read — calling it inside the comparator would make the sort
  // comparator non-deterministic. Array.prototype.sort is stable in V8/Deno,
  // so when every slot is healthy (penalty 0) the order is byte-identical to
  // step 1 — this layer is a no-op until something actually fails.
  // P4 (2026-06-14): per-ENTRY penalty = max(provider-wide, this specific model). A model's
  // own TPM 429 is recorded at the "provider:model" slot, so it sinks JUST that model; a
  // provider-wide failure (auth/5xx/network) sinks all the provider's models together. Keyed
  // by entry, not provider, so sibling models can differ. Snapshot once (getSlotPenalty applies
  // time-decay on read) so the comparator stays deterministic. No model-slot penalties exist
  // until callAI records them, so this is byte-identical to the old provider-only behavior for
  // any caller (e.g. the Node port test) that only ever set provider-level penalties.
  const entryPen = new Map<ProviderEntry, number>();
  for (const e of ordered) {
    entryPen.set(e, Math.max(getSlotPenalty(e.provider), getSlotPenalty(`${e.provider}:${e.model}`)));
  }
  // ★v9 (2026-10-08): THIS SORT UNDID STEP 1b. Run across the whole chain, it lifted a last-resort entry that had never
  // been tried (penalty 0) above every general model that had failed once (penalty 3) - and under a burst every general
  // model fails once - so mistral codestral-latest answered nearly every question of a grounding eval. It now sorts
  // inside two bands: general entries (and any specialist the task profile asked for) first, unasked specialists after,
  // whatever the penalties say.
  const profilePref = taskProfile ? (TASK_PROFILES[taskProfile] || []) : [];
  const askedByProfile = (e: ProviderEntry) => profilePref.some((p) => e.model.toLowerCase().includes(p.toLowerCase()));
  const bandOf = (e: ProviderEntry) => (e.lastResort && !askedByProfile(e) ? 1 : 0);
  ordered.sort((a, b) => (bandOf(a) - bandOf(b)) || (entryPen.get(a)! - entryPen.get(b)!));

  // ── Step 3: herd-spread (P1, 2026-06-14) ─────────────────────────────────────
  // Shuffle WITHIN equal-penalty groups so N concurrent calls don't all stampede the exact
  // same head entry and 429 in lockstep — the thundering-herd the 10-worker stress sweep
  // exposed (every call reorders identically -> all hit prov[0] -> all 429 -> all march to
  // prov[1] together). The chain is "good enough + free", so spreading the head across
  // equally-healthy entries buys far more usable throughput under burst than strict order.
  // OFF by default (deterministic order preserved for the Node port test + non-burst callers);
  // callAI opts in with spread=true. A flaky/parked entry has a higher penalty so it's in a
  // later group and never shuffles up ahead of a healthy one.
  // v9: a group is a run of equal penalty AND equal band AND equal profile-preference. Before, an all-healthy chain was
  // ONE group, so the shuffle could put codestral first and scatter a task profile's preferred models into the rest.
  const groupOf = (e: ProviderEntry) => `${entryPen.get(e)}|${bandOf(e)}|${askedByProfile(e) ? 1 : 0}`;
  if (spread) {
    let i = 0;
    while (i < ordered.length) {
      let j = i + 1;
      const g = groupOf(ordered[i]);
      while (j < ordered.length && groupOf(ordered[j]) === g) j++;
      for (let k = j - 1; k > i; k--) {            // Fisher-Yates within the equal-penalty group [i, j)
        const r = i + Math.floor(Math.random() * (k - i + 1));
        [ordered[k], ordered[r]] = [ordered[r], ordered[k]];
      }
      i = j;
    }
  }
  return ordered;
}

// P2 helper (2026-06-14): parse a 429 `Retry-After` header — either delta-seconds
// ("12") or an HTTP-date — into milliseconds-from-now. Returns undefined if absent/unparseable.
function parseRetryAfter(h: string | null): number | undefined {
  if (!h) return undefined;
  const secs = Number(h);
  if (!isNaN(secs)) return Math.max(0, secs * 1000);
  const when = Date.parse(h);
  if (!isNaN(when)) return Math.max(0, when - Date.now());
  return undefined;
}

// ★PERMANENT vs TRANSIENT (v9, 2026-10-08). Every non-2xx other than 429/413/503 used to be recorded the same way - one
// provider-wide failure, asked again on the retry pass and on the next call. That treated a key the provider will never
// serve (402 payment_required: Cerebras, 480 times in a month), a model that no longer exists (404) and one model's bad
// JSON (Groq 400 json_validate_failed) as the same event - and the third parked ALL of Groq for one model's mistake.
//   permanent - the answer will not change on retry: 401 (key rejected: the whole provider), 402 (payment required),
//               403 (refused for this key), 404 (model gone or not free), a 400 that names the MODEL as invalid.
//               Parked PERMANENT_PARK_MS and never asked again by the same call.
//   request   - any other 4xx: this request's shape is refused by this model (a context limit, a parameter it does
//               not take). Skipped for the rest of the call; a different request may succeed, so no long park.
//   transient - the model's OUTPUT failed (Groq json_validate_failed / json_generate_failed) or the provider broke (5xx):
//               retried on the next pass exactly as before. A model's own failure parks only that model.
export const PERMANENT_PARK_MS = 6 * 60 * 60 * 1000;
export function classifyProviderFailure(status: number, body: string):
  { kind: "permanent" | "request" | "transient"; scope: "model" | "provider"; reason: string } {
  const b = (body || "").toLowerCase();
  if (status >= 500) return { kind: "transient", scope: "provider", reason: "provider error" };
  if (status === 401) return { kind: "permanent", scope: "provider", reason: "key rejected" };
  if (status === 402) return { kind: "permanent", scope: "model", reason: "payment required - not free on this key" };
  if (status === 403) return { kind: "permanent", scope: "model", reason: "refused for this key" };
  if (status === 404) return { kind: "permanent", scope: "model", reason: "model not found or not free" };
  if (/json_validate_failed|json_generate_failed|failed to (validate|generate) json/.test(b)) {
    return { kind: "transient", scope: "model", reason: "the model's output failed JSON validation" };
  }
  if (status === 400 && /model_not_found|model_decommissioned|decommissioned|does not exist|no such model|unknown model|invalid model|model not found|not a valid model/.test(b)) {
    return { kind: "permanent", scope: "model", reason: "invalid model" };
  }
  return { kind: "request", scope: "model", reason: "request refused by this model" };
}

/**
 * Strip reasoning-model thinking blocks from LLM output so they don't leak
 * to end users. Qwen3-32B and similar reasoning models wrap their internal
 * deliberation in `<think>...</think>`. The 2026-05-26 V3 flywheel run
 * caught Qwen3 mentioning a real DB table name ("worker_profiles") inside
 * a think block while reasoning about how to refuse a prompt-injection
 * probe. The refusal itself was correct, but the think block was visible.
 *
 * V4 lesson: an over-greedy second pass (`^[\s\S]*?<\/think>`) wiped real
 * user content when a response happened to contain `</think>` as a literal
 * (e.g. example text in user transcripts). Now: only strip when the
 * response clearly LOOKS like reasoning-model output.
 *
 * V5 (2026-07-13): some free-tier models narrate their PLAN as bare prose with
 * NO <think> tags ("We need to respond as Zaniah, strategist, in English, short
 * 1-3 sentences... The worker says:...") and often run out of tokens mid-plan,
 * so no clean answer follows. voice_family_probe caught this leaking the persona
 * scaffold verbatim into the companion reply. Case 3 detects that untagged leak
 * with a STRONG two-part signature and returns "" so callAI falls to the next model.
 */
export function stripReasoningBlocks(text: string): string {
  if (!text) return text;
  // Case 1 — well-formed pair: remove <think>...</think> blocks anywhere.
  let out = text.replace(/<think[\s>][\s\S]*?<\/think>/gi, "").trim();
  // Case 2 — leading unclosed <think> with no close tag (truncated). Only
  // strip when the string STARTS with `<think` so we don't eat innocent
  // content that contains `</think>` as a literal mid-string.
  if (/^\s*<think[\s>]/i.test(out)) {
    const closeIdx = out.toLowerCase().indexOf("</think>");
    if (closeIdx !== -1) {
      out = out.slice(closeIdx + "</think>".length).trim();
    } else {
      // Unclosed and starts with <think — no usable content remained.
      return "";
    }
  }
  // Case 3 — UNTAGGED reasoning-model leak. Fires ONLY when BOTH hold, so a real
  // answer that merely discusses strategy can never trip it:
  //   (a) the string STARTS with a first-person planning verb about RESPONDING, and
  //   (b) it references internal instruction/persona scaffold no user answer contains.
  // When both match, the reply IS scaffold (not an answer) -> "" -> caller tries next model.
  const startsWithPlan =
    /^\s*(?:okay,?\s*|so,?\s*|alright,?\s*|well,?\s*)?(?:we|i|let(?:'s| us| me))\b[^.!?\n]{0,60}?(?:\b(?:need(?:s)? to|should|must|will|have to|'ll|'re going to|going to|want to)\b[^.!?\n]{0,60}?)?\b(?:respond|reply|answer|say|be|act|write|give|frame|craft|address|produce|consider)\b/i;
  const hasScaffoldMeta =
    /\b(?:as\s+(?:zaniah|hezekiah)|as\s+the\s+(?:strategist|technician)|1\s*-\s*3\s+sentences|short\s+1-3|kpis?\s+verbatim|sisterly\s+ph\s+english|\bpersona\b|system\s+prompt|the\s+worker\s+(?:says|said)|snapshot\s+data|memory\s+block)\b/i;
  if (startsWithPlan.test(out) && hasScaffoldMeta.test(out)) {
    return "";
  }
  return out;
}

// W4 fault-injection (LOCAL-ONLY). The faultInject option simulates provider
// 429/413/down WITHOUT a network call so the wiring battery can prove M1 (fallback),
// M2 (all-down graceful degrade -> "{}"), M4 (413 skip). It is honored ONLY when the
// runtime is local (SUPABASE_URL host kong/localhost/127.0.0.1; prod is *.supabase.co),
// so it is dead in production even if a faultInject option somehow reaches callAI.
const _AI_CHAIN_LOCAL = /\/\/(kong|localhost|127\.0\.0\.1)(:|\/|$)/.test(Deno.env.get("SUPABASE_URL") || "");

// The whole text walk's budget (OWN dependency lens, 2026-10-26): under the ~60 s a request can wait at the gateway, with room
// for the reply to travel. Each attempt gets min(25 s, what is left).
const WALK_BUDGET_MS = 50000;

export interface FaultInject {
  fail?: string[];      // provider names to force-fail (e.g. ["groq"])
  failAll?: boolean;    // force EVERY provider to fail (all-down degrade -> "{}")
  mode?: "429" | "413" | "down" | "slow" | "changed";
  // OWN dependency lens (2026-10-26): with `fake` (a LOCAL fake provider's base URL, tools/fake_ai_provider.py) the named
  // providers are NOT skipped by simulation - the chain's REAL fetch, timeout and parse code runs against the fake, which
  // answers per mode (slow: past the 25 s ceiling; 429: rate-limited; changed: a 200 with no choices; down: a closed port).
  // The simulated skip proves the wiring; this proves the code that meets a misbehaving provider. Local-only like the rest.
  fake?: string;
}

/**
 * ★"{}" IS THE CHAIN SAYING NO MODEL ANSWERED - IN TEXT MODE IT IS NOT AN ANSWER (2026-10-09, found walking
 * shift-brain under the walk's no-model switch, which returns exactly what an exhausted chain returns).
 * callAI answers "{}" when every provider failed (and when a local walk asks for no model). JSON callers read that
 * as an empty object and take their fallback; the four FREE-TEXT callers used it verbatim: the shift plan's
 * briefing read "{}" above its signature, the voice journal replied "{}", a failure signature's detail became "{}"
 * marked source "ai" - and the conversation summariser kept "{}" as the summary and DELETED the worker's turns it
 * summarised. True only for a real reply: not empty, not the chain's "{}".
 */
export function aiAnswered(raw: string | null | undefined): boolean {
  const t = String(raw ?? "").trim();
  return t !== "" && t !== "{}";
}

export async function callAI(
  prompt: string,
  options: {
    systemPrompt?: string;
    temperature?: number;
    maxTokens?: number;
    jsonMode?: boolean;
    taskProfile?: string;
    sessionKey?: string;   // multi-turn affinity — pin this conversation to one model (~30min)
    faultInject?: FaultInject;  // LOCAL-ONLY test hook (W4); ignored in prod
    /** Q6 chain-depth telemetry hook. Fired (best-effort) when a model serves, with the
     *  winning model's index in the canonical PROVIDER_CHAIN (0=primary) + which pass.
     *  Optional + fully isolated in try/catch — existing callers pass nothing and are
     *  unaffected; a throwing hook can never break the answer. */
    onServed?: (meta: { providerName: string; modelName: string; depth: number; pass: number }) => void;
  } = {}
): Promise<string> {
  const { systemPrompt, temperature = 0.2, maxTokens = 1024, jsonMode = true, taskProfile, sessionKey, faultInject, onServed } = options;
  // ★A WALK SPENDS NO MODEL CALL (model-calls.ts ModelCallScope.no_model): asked for on the LOCAL runtime only, it
  // answers "{}" before any provider - the local LLM included - is asked, parks nothing and reports nothing, so the
  // caller's own degraded path runs exactly as it would when every provider is down.
  if (_AI_CHAIN_LOCAL && modelCallsRefused()) {
    console.warn("[ai-chain] no model call: the request asked for none (x-wh-walk-no-model, local runtime)");
    return "{}";
  }
  const _callT0 = performance.now();   // LM-O: the per-call record's latency (the whole chain walk the caller waited on)
  // LM-O: every slot this call actually asks, in order, with how it answered ("groq/llama-3.3-70b-versatile=429") -
  // the record's providers_tried, on a served row and on an exhausted one alike
  const tried: string[] = [];

  const messages = systemPrompt
    ? [{ role: "system", content: systemPrompt }, { role: "user", content: prompt }]
    : [{ role: "user", content: prompt }];

  // Sticky session: if this conversation already has a pinned model and it is still in the
  // chain, try it FIRST (applied per-pass). isSlotBlocked still wins, so a parked pin falls
  // through and the conversation re-pins on the next success. No-op when sessionKey is absent.
  const applySticky = (chainArr: ProviderEntry[]): ProviderEntry[] => {
    if (!sessionKey) return chainArr;
    const sticky = getStickyModel(sessionKey);
    if (!sticky) return chainArr;
    const idx = chainArr.findIndex(e => e.provider === sticky.provider && e.model === sticky.model);
    if (idx > 0) { const c = chainArr.slice(); const [pinned] = c.splice(idx, 1); c.unshift(pinned); return c; }
    return chainArr;
  };

  // v9: slots this call has already seen fail for good (permanent) or refuse this request (request) - the retry pass
  // must not ask them again. Request-local; the cross-call memory is provider-health's park.
  const deadThisCall = new Set<string>();

  // One pass down a chain: returns the answer on the first success, or null if every entry
  // was skipped/failed (so the caller can run the P3 retry pass before degrading to "{}").
  const attemptChain = async (chainArr: ProviderEntry[], passNum: number): Promise<string | null> => {
    for (const entry of chainArr) {
      const apiKey = Deno.env.get(entry.envKey);
      if (!apiKey) continue;
      const modelSlot = `${entry.provider}:${entry.model}`;
      if (deadThisCall.has(entry.provider) || deadThisCall.has(modelSlot)) continue;
      // P1 roadmap 2026-05-27 turn 7 + P4 2026-06-14 — skip a parked PROVIDER or this parked MODEL.
      if (isSlotBlocked(entry.provider) || isSlotBlocked(modelSlot)) continue;

      // W4 fault-injection (LOCAL-ONLY): simulate this provider failing (429/413/down)
      // without a network call, so the next provider is tried (M1), all-down degrades
      // to "{}" (M2), and 413 is skipped (M4). Honored only locally; dead in prod.
      const _faulted = !!(faultInject && _AI_CHAIN_LOCAL &&
          (faultInject.failAll === true || (faultInject.fail || []).includes(entry.provider)));
      // a fake provider stands in: the real request goes to it (closed port for "down"), and the real code meets the answer
      const _fakeBase = (_faulted && faultInject!.fake)
        ? (faultInject!.mode === "down" ? faultInject!.fake.replace(/:\d+(\/.*)?$/, ":9") : `${faultInject!.fake.replace(/\/+$/, "")}/${faultInject!.mode || "429"}`)
        : "";
      if (_faulted && !_fakeBase) {
        console.warn(`[ai-chain] FAULT-INJECT ${entry.provider}/${entry.model} (${faultInject.mode || "429"}) — simulated skip`);
        tried.push(`${entry.provider}/${entry.model}=fault-inject`);
        recordSlotFailure(entry.provider);
        continue;
      }

      const effectiveMaxTokens = entry.maxTokensCap
        ? Math.min(maxTokens, entry.maxTokensCap)
        : maxTokens;

      // Token-aware pre-skip (FreeLLMAPI canUseTokens idea, 2026-05-30): if this
      // model's total context window provably can't fit prompt + output, skip it
      // here instead of wasting a round-trip to discover the 413. Only applies to
      // entries that declare a contextCap (a small-context model; none does today);
      // no-op for everything else. 256t margin covers chat-template overhead.
      if (entry.contextCap) {
        const estPromptTokens = estimateTokens((systemPrompt ?? "") + prompt);
        if (estPromptTokens + effectiveMaxTokens + 256 > entry.contextCap) {
          console.warn(`[ai-chain] ${entry.provider}/${entry.model} pre-skipped (prompt ~${estPromptTokens}t + ${effectiveMaxTokens}t out > ${entry.contextCap}t context)`);
          continue;
        }
      }

      // ★THE WALK HAS A BUDGET, NOT ONLY EACH STEP (OWN dependency lens, 2026-10-26). Measured with a slow provider: the
      // chain waited 25 s on each of Google's three models in turn and found an answer at 77 s - after the request had
      // already failed for the person ("Failed to send a request to the Edge Function"). Each attempt now gets what is
      // left of a 50 s walk, and a spent walk stops and degrades honestly rather than answering no one.
      const _left = WALK_BUDGET_MS - (performance.now() - _callT0);
      if (_left < 3000) {
        // not the next provider's failure: the WALK ran out of time (the console shows it as 'chain')
        if (!tried.includes("chain/walk=budget")) tried.push("chain/walk=budget");
        return null;
      }
      try {
        const res = await fetch(`${_fakeBase || entry.baseUrl}/chat/completions`, {
          method: "POST",
          // 25 s per attempt (was 60 s): a free-tier text answer arrives in seconds, and one stalled provider used to
          // hold a person's question for a full minute before the chain moved on (LM-R, LM109, 2026-10-07)
          signal: AbortSignal.timeout(Math.min(25000, _left)),
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${apiKey}`,
            ...(entry.extraHeaders ?? {}),
          },
          body: JSON.stringify({
            model: entry.model,
            messages,
            temperature,
            max_tokens: effectiveMaxTokens,
            ...(jsonMode ? { response_format: { type: "json_object" } } : {}),
            ...(entry.extraBody ?? {}),
          }),
        });

        // Rate-limited / payload too large / unavailable: try next. P2: honor Retry-After for
        // the cooldown window. 429+413 are per-MODEL (TPM / prompt size) -> park just this
        // model so its siblings stay usable; 503 is provider-wide -> park the whole provider.
        if (res.status === 429 || res.status === 413 || res.status === 503) {
          const raMs = parseRetryAfter(res.headers.get("retry-after"));
          console.warn(`[ai-chain] ${entry.provider}/${entry.model} skipped (HTTP ${res.status}${raMs ? `, retry-after ${Math.round(raMs / 1000)}s` : ""})`);
          tried.push(`${entry.provider}/${entry.model}=${res.status}`);
          recordSlotFailure(modelSlot, raMs);
          if (res.status === 503) recordSlotFailure(entry.provider, raMs);
          continue;
        }

        if (!res.ok) {
          const errBody = await res.text();
          const f = classifyProviderFailure(res.status, errBody);
          const slot = f.scope === "provider" ? entry.provider : modelSlot;
          tried.push(`${entry.provider}/${entry.model}=${res.status}`);
          console.warn(`[ai-chain] ${entry.provider}/${entry.model} error ${res.status} (${f.kind}: ${f.reason}): ${errBody.slice(0, 120)} — trying next`);
          if (f.kind === "permanent") {
            recordSlotFailure(slot, PERMANENT_PARK_MS);   // parked for hours, not the ladder's 1-minute first rung
            deadThisCall.add(slot);
          } else {
            recordSlotFailure(slot);                      // 5xx = provider-wide (unchanged); a model's own failure = that model
            if (f.kind === "request") deadThisCall.add(modelSlot);
          }
          continue;
        }

        const data = await res.json();
        const content: string | undefined = data?.choices?.[0]?.message?.content;
        // ★A HALF-WRITTEN ANSWER IS NOT AN ANSWER (v7, 2026-10-07). A thinking model spends max_tokens on reasoning
        // the caller never sees: gemini-2.5-flash returned "A pump" at a 120-token budget, and a companion answer
        // reached a person as "ZQX 9471 is still not one". finish_reason "length" with almost nothing visible means the
        // budget went to thinking - skip to the next provider. A long answer that merely reached its cap (most of the
        // budget visible) is still served: that is a full answer, cut at the length the caller asked for.
        if (data?.choices?.[0]?.finish_reason === "length" && (content || "").trim().length < effectiveMaxTokens * 0.8) {
          console.warn(`[ai-chain] ${entry.provider}/${entry.model} ran out of budget after ${(content || "").trim().length} visible chars (finish_reason length) — trying next`);
          tried.push(`${entry.provider}/${entry.model}=length`);
          recordSlotFailure(modelSlot);
          continue;
        }
        if (content) {
          // Strip <think>...</think> reasoning blocks (Qwen3-32B et al.) so
          // chain-of-thought doesn't leak. V4 caught Qwen3 leaking
          // "worker_profiles" inside a think block while reasoning about
          // refusing a prompt-injection probe.
          const stripped = stripReasoningBlocks(content);
          if (stripped) {
            // the durable record of this call is reportModelCall's ai_cost_log row below; this line is the stdout echo
            console.log(`[ai-chain] served by ${entry.provider} / ${entry.model} (tokens ${data?.usage?.total_tokens ?? "unreported"})`);
            recordSlotSuccess(entry.provider);
            recordSlotSuccess(modelSlot);
            tried.push(`${entry.provider}/${entry.model}=${res.status}`);
            reportModelCall({ providerName: entry.provider, modelName: entry.model, usage: data?.usage, input: messages, output: stripped, started_at: _callT0, tried });
            // Q6 chain-depth telemetry: report the winning model's CANONICAL depth (its
            // index in PROVIDER_CHAIN, 0=primary), not its position in the reordered pass —
            // so "served deep" reliably means "primary providers exhausted / quality decaying".
            // Best-effort: a throwing hook must never break the answer.
            if (onServed) {
              try {
                const depth = PROVIDER_CHAIN.findIndex(e => e.provider === entry.provider && e.model === entry.model);
                onServed({ providerName: entry.provider, modelName: entry.model, depth: depth < 0 ? 0 : depth, pass: passNum });
              } catch { /* empty-catch-allow: telemetry must never break the answer path */ }
            }
            // Pin this conversation to the model that just served it so the next
            // turn stays on the same model (no-op when sessionKey is absent).
            if (sessionKey) setStickyModel(sessionKey, entry.provider, entry.model);
            return stripped;
          }
          // Reasoning model emitted only a think block with no usable answer —
          // fall through to the next provider rather than return empty.
          console.warn(`[ai-chain] ${entry.provider}/${entry.model} returned only reasoning, no answer — trying next`);
          tried.push(`${entry.provider}/${entry.model}=reasoning-only`);
          deadThisCall.add(modelSlot);   // the retry pass would get the same unusable answer
        } else {
          console.warn(`[ai-chain] ${entry.provider}/${entry.model} returned empty content — trying next`);
          tried.push(`${entry.provider}/${entry.model}=empty`);
          // an answer this model could not shape (a changed API, an empty reply) is not asked again by the retry pass of the
          // same call: measured 2026-10-26, every model asked twice for the same unusable 200
          deadThisCall.add(modelSlot);
        }
      } catch (err) {
        console.warn(`[ai-chain] ${entry.provider}/${entry.model} threw: ${String(err).slice(0, 80)}`);
        tried.push(`${entry.provider}/${entry.model}=${/timeout|abort/i.test(String(err)) ? "timeout" : "threw"}`);
        recordSlotFailure(entry.provider);   // network/abort = provider-wide
        recordSlotFailure(modelSlot);
        // ...and provider-wide for THIS call too: the cross-call park needs strikes, so a slow provider's next model was
        // asked anyway and timed out again (three Google models, 75 s, measured 2026-10-26)
        deadThisCall.add(entry.provider);
      }
    }
    return null;
  };

  // Sovereign local LLM (NATIVE_AI_ROADMAP.md #2b, V-axis): when a plant sets WH_LLM_URL to its own
  // OpenAI-compatible endpoint (Ollama / llama.cpp / vLLM), try it FIRST so inference AND the worker's
  // data stay in-plant. Env-gated + additive exactly like WH_ASR_URL / BGE_EMBED_URL / WH_TTS_URL:
  // unset in production today, so this returns null and the free-tier chain below runs UNCHANGED. Fails
  // OPEN (any non-2xx / empty / throw -> null -> the cloud chain serves), so a local-server outage or a
  // model hiccup never dead-ends the worker (the "fallback-to-cloud hedge is the correct default" rule).
  const tryLocalLLM = async (): Promise<string | null> => {
    const base = (Deno.env.get("WH_LLM_URL") || "").replace(/\/+$/, "");
    if (!base) return null;
    const model = Deno.env.get("WH_LLM_MODEL") || "llama3.1";
    const key = Deno.env.get("WH_LLM_API_KEY");
    try {
      const res = await fetch(`${base}/chat/completions`, {
        method: "POST",
        signal: AbortSignal.timeout(60000),
        headers: {
          "Content-Type": "application/json",
          ...(key ? { "Authorization": `Bearer ${key}` } : {}),
        },
        body: JSON.stringify({
          model, messages, temperature, max_tokens: maxTokens,
          ...(jsonMode ? { response_format: { type: "json_object" } } : {}),
        }),
      });
      if (!res.ok) {
        console.warn(`[ai-chain] WH_LLM_URL ${res.status} (sovereign) falling back to cloud chain`);
        tried.push(`wh-llm-local/${model}=${res.status}`);
        return null;
      }
      const data = await res.json();
      const content: string | undefined = data?.choices?.[0]?.message?.content;
      const stripped = content ? stripReasoningBlocks(content) : "";
      if (stripped) {
        console.log(`[ai-chain] served by WH_LLM_URL (sovereign local) / ${model}`);
        tried.push(`wh-llm-local/${model}=${res.status}`);
        reportModelCall({ providerName: "wh-llm-local", modelName: model, usage: data?.usage, input: messages, output: stripped, started_at: _callT0, tried });
        if (onServed) {
          try { onServed({ providerName: "wh-llm-local", modelName: model, depth: 0, pass: 0 }); }
          catch { /* empty-catch-allow: telemetry must never break the answer path */ }
        }
        return stripped;
      }
      tried.push(`wh-llm-local/${model}=empty`);
      return null;
    } catch (err) {
      console.warn(`[ai-chain] WH_LLM_URL threw: ${String(err).slice(0, 80)} falling back to cloud chain`);
      tried.push(`wh-llm-local/${model}=threw`);
      return null;
    }
  };
  const sovereign = await tryLocalLLM();
  if (sovereign !== null) return sovereign;

  // Pass 1 — herd-spread chain (P1), sticky pin first.
  const first = await attemptChain(applySticky(reorderChain(taskProfile, true)), 1);
  if (first !== null) return first;

  // P3 (2026-06-14): one bounded jittered-retry pass before degrading to "{}". A concurrent
  // burst can 429 every slot on pass 1; a short randomized backoff (300-1200ms) lets per-second
  // token buckets refill AND de-synchronizes this call from the herd, then we re-spread and try
  // once more. Skipped for the all-down fault-injection (M2) so that test still degrades to "{}"
  // immediately, and capped at exactly one extra pass so a call can never hang.
  if (!(faultInject?.failAll)) {
    await new Promise((r) => setTimeout(r, 300 + Math.floor(Math.random() * 900)));
    const second = await attemptChain(applySticky(reorderChain(taskProfile, true)), 2);
    if (second !== null) return second;
  }

  // ★NOTHING SERVED, AND THAT IS A RECORD TOO (LM-O, 2026-10-08). The person gets the caller's degraded path; the
  // operator gets one failed row with every slot asked and how it answered (none asked = no slot was available).
  console.warn(`[ai-chain] exhausted: no provider served (${tried.length} asked)`);
  reportModelCallFailed({ providerName: "chain", modelName: "exhausted", tried, started_at: _callT0 });
  return "{}";
}

// ─── Multimodal (image + text) variant ───────────────────────────────────────
//
// Same fallback chain pattern, but iterates only providers with vision:true.
// Uses the OpenAI-compatible vision format: the user `content` field becomes
// an array of `{type:"text"}` and `{type:"image_url"}` blocks.
//
// `imageDataUrl` must be either a `data:image/...;base64,...` URL or a fully
// resolvable HTTPS URL the model can fetch. We accept both because some hive
// flows upload to Supabase Storage first (HTTPS) and others post the bytes
// directly (data URL).
//
// `prompt` is the system instruction OR the user-facing question depending
// on whether `systemPrompt` is also supplied.
//
// Returns "{}" if no provider in the chain succeeds, mirroring callAI() so
// callers have one error branch.
//
// Skills consulted: ai-engineer (system prompt as const, JSON output for
// structured classification, prompt-injection-via-OCR safety in the caller),
// security (image bytes never logged, MIME whitelist enforced upstream).
export async function callAIMultimodal(
  prompt: string,
  imageDataUrl: string,
  options: {
    systemPrompt?: string;
    temperature?: number;
    maxTokens?: number;
    jsonMode?: boolean;
    detail?: "low" | "high" | "auto";
  } = {},
): Promise<string> {
  const {
    systemPrompt,
    temperature = 0.2,
    maxTokens   = 1024,
    jsonMode    = true,
    detail      = "auto",
  } = options;
  const _callT0 = performance.now();   // LM-O: the per-call record's latency
  const tried: string[] = [];          // LM-O: the record's providers_tried

  if (!imageDataUrl) return "{}";      // no image, no call - nothing to record
  if (_AI_CHAIN_LOCAL && modelCallsRefused()) {   // a walk spends no model call (see callAI)
    console.warn("[ai-chain] no model call (vision): the request asked for none (x-wh-walk-no-model, local runtime)");
    return "{}";
  }

  // OpenAI-compatible vision content: text block + image_url block.
  const userContent = [
    { type: "text",      text: prompt },
    { type: "image_url", image_url: { url: imageDataUrl, detail } },
  ];

  const messages = systemPrompt
    ? [{ role: "system", content: systemPrompt }, { role: "user", content: userContent }]
    : [{ role: "user", content: userContent }];

  // ★v10 (2026-10-08): THE IMAGE PATH NOW FAILS OVER LIKE THE TEXT PATH. It used to ask every vision entry on every
  // photo with no memory at all - a model answering 402/404 was asked again on the next photo and the next, a 429 parked
  // nothing, and a success re-opened nothing. Now: a parked provider or model is skipped; each failure is classified by
  // classifyProviderFailure (permanent = parked PERMANENT_PARK_MS and skipped for the rest of the call; a model's own
  // failure parks only that model; 5xx/network = the provider, as before); 429/413 park the model and 503 the provider,
  // honouring Retry-After; a half-written answer is skipped; and a last-resort (code) entry stays behind every general
  // one. No vision entry is a code model today, so that last rule is a guard, not a reorder. Same provider-health state
  // as callAI: a model the text path parked is parked here too - it is the same model and the same quota.
  const visionChain = [
    ...PROVIDER_CHAIN.filter((e) => e.vision && !e.lastResort),
    ...PROVIDER_CHAIN.filter((e) => e.vision && e.lastResort),
  ];
  const deadThisCall = new Set<string>();
  for (const entry of visionChain) {
    const apiKey = Deno.env.get(entry.envKey);
    if (!apiKey) continue;
    const modelSlot = `${entry.provider}:${entry.model}`;
    if (deadThisCall.has(entry.provider) || deadThisCall.has(modelSlot)) continue;
    if (isSlotBlocked(entry.provider) || isSlotBlocked(modelSlot)) continue;

    const effectiveMaxTokens = entry.maxTokensCap
      ? Math.min(maxTokens, entry.maxTokensCap)
      : maxTokens;

    try {
      const res = await fetch(`${entry.baseUrl}/chat/completions`, {
        method: "POST",
        signal: AbortSignal.timeout(90_000),    // images take longer than text
        headers: {
          "Content-Type":  "application/json",
          "Authorization": `Bearer ${apiKey}`,
          ...(entry.extraHeaders ?? {}),
        },
        body: JSON.stringify({
          model: entry.model,
          messages,
          temperature,
          max_tokens: effectiveMaxTokens,
          ...(jsonMode ? { response_format: { type: "json_object" } } : {}),
          ...(entry.extraBody ?? {}),
        }),
      });

      if (res.status === 429 || res.status === 413 || res.status === 503) {
        const raMs = parseRetryAfter(res.headers.get("retry-after"));
        console.warn(`[ai-chain:vision] ${entry.provider}/${entry.model} skipped (HTTP ${res.status}${raMs ? `, retry-after ${Math.round(raMs / 1000)}s` : ""})`);
        tried.push(`${entry.provider}/${entry.model}=${res.status}`);
        recordSlotFailure(modelSlot, raMs);
        if (res.status === 503) recordSlotFailure(entry.provider, raMs);
        continue;
      }

      if (!res.ok) {
        const errBody = await res.text();
        const f = classifyProviderFailure(res.status, errBody);
        const slot = f.scope === "provider" ? entry.provider : modelSlot;
        console.warn(`[ai-chain:vision] ${entry.provider}/${entry.model} error ${res.status} (${f.kind}: ${f.reason}): ${errBody.slice(0, 120)} — trying next`);
        tried.push(`${entry.provider}/${entry.model}=${res.status}`);
        if (f.kind === "permanent") {
          recordSlotFailure(slot, PERMANENT_PARK_MS);
          deadThisCall.add(slot);
        } else {
          recordSlotFailure(slot);
          if (f.kind === "request") deadThisCall.add(modelSlot);
        }
        continue;
      }

      const data = await res.json();
      const content: string | undefined = data?.choices?.[0]?.message?.content;
      if (data?.choices?.[0]?.finish_reason === "length" && (content || "").trim().length < effectiveMaxTokens * 0.8) {
        console.warn(`[ai-chain:vision] ${entry.provider}/${entry.model} ran out of budget after ${(content || "").trim().length} visible chars (finish_reason length) — trying next`);
        tried.push(`${entry.provider}/${entry.model}=length`);
        recordSlotFailure(modelSlot);
        continue;
      }
      if (content) {
        const stripped = stripReasoningBlocks(content);
        if (stripped) {
          console.log(`[ai-chain:vision] served by ${entry.provider} / ${entry.model} (tokens ${data?.usage?.total_tokens ?? "unreported"})`);
          recordSlotSuccess(entry.provider);
          recordSlotSuccess(modelSlot);
          tried.push(`${entry.provider}/${entry.model}=${res.status}`);
          reportModelCall({ providerName: entry.provider, modelName: entry.model, usage: data?.usage, input: messages, output: stripped, started_at: _callT0, tried });
          return stripped;
        }
        // Reasoning-only (tagged or untagged scaffold leak), no usable answer — try next.
        console.warn(`[ai-chain:vision] ${entry.provider}/${entry.model} returned only reasoning — trying next`);
        tried.push(`${entry.provider}/${entry.model}=reasoning-only`);
        continue;
      }
      console.warn(`[ai-chain:vision] ${entry.provider}/${entry.model} returned empty content — trying next`);
      tried.push(`${entry.provider}/${entry.model}=empty`);
    } catch (err) {
      console.warn(`[ai-chain:vision] ${entry.provider}/${entry.model} threw: ${String(err).slice(0, 80)}`);
      tried.push(`${entry.provider}/${entry.model}=${/timeout|abort/i.test(String(err)) ? "timeout" : "threw"}`);
      recordSlotFailure(entry.provider);   // network/abort = provider-wide, as in callAI
      recordSlotFailure(modelSlot);
    }
  }

  // nothing served: one failed record, as callAI's (LM-O, 2026-10-08)
  console.warn(`[ai-chain:vision] exhausted: no provider served (${tried.length} asked)`);
  reportModelCallFailed({ providerName: "chain", modelName: "exhausted", tried, started_at: _callT0 });
  return "{}";
}
