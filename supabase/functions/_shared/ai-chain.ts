// Multi-provider AI fallback chain for WorkHive edge functions.
// All providers use OpenAI-compatible chat completions format.
// Each API key is read from env — missing keys are silently skipped.
// Order: fastest / most generous limits first, deeper fallbacks last.
// Only permanently free tiers — no credits that expire.
//
// AI_ASSET_VERSION: 2
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
  // Llama 4 Scout: 30K TPM (highest on Groq free tier), 500K TPD, multimodal (Llama 4 family supports vision).
  { provider: "groq", baseUrl: "https://api.groq.com/openai/v1", model: "meta-llama/llama-4-scout-17b-16e-instruct", envKey: "GROQ_API_KEY", vision: true },
  // Llama 3.3 70B: proven quality, 6K TPM
  { provider: "groq", baseUrl: "https://api.groq.com/openai/v1", model: "llama-3.3-70b-versatile",                   envKey: "GROQ_API_KEY" },
  // Qwen3 32B: 60 RPM, 500K TPD
  { provider: "groq", baseUrl: "https://api.groq.com/openai/v1", model: "qwen/qwen3-32b",                            envKey: "GROQ_API_KEY" },
  // Llama 3.1 8B: fastest, 500K TPD, high TPM
  { provider: "groq", baseUrl: "https://api.groq.com/openai/v1", model: "llama-3.1-8b-instant",                      envKey: "GROQ_API_KEY" },
  // GPT-OSS 20B: strict JSON schema adherence, 8K TPM — after high-TPM models
  { provider: "groq", baseUrl: "https://api.groq.com/openai/v1", model: "openai/gpt-oss-20b",                        envKey: "GROQ_API_KEY" },
  // GPT-OSS 120B: largest model on Groq free tier, 8K TPM — last Groq resort
  { provider: "groq", baseUrl: "https://api.groq.com/openai/v1", model: "openai/gpt-oss-120b",                       envKey: "GROQ_API_KEY" },

  // ── Tier 2: Cerebras — 1M tokens/day free, 8K total context cap ─────────────
  // NOTE 2026-05-18: the first two entries 404'd on accounts without access.
  // Fallback `llama3.1-8b` is broadly available on free tier. Mirror with
  // Python tools/ai_chain.py.
  { provider: "cerebras", baseUrl: "https://api.cerebras.ai/v1", model: "llama-3.3-70b", envKey: "CEREBRAS_API_KEY", maxTokensCap: 4096, contextCap: 8192 },
  { provider: "cerebras", baseUrl: "https://api.cerebras.ai/v1", model: "qwen-3-32b",    envKey: "CEREBRAS_API_KEY", maxTokensCap: 4096, contextCap: 8192 },
  { provider: "cerebras", baseUrl: "https://api.cerebras.ai/v1", model: "llama3.1-8b",   envKey: "CEREBRAS_API_KEY", maxTokensCap: 4096, contextCap: 8192 },

  // NOTE: SambaNova was evaluated (FreeLLMAPI lists it) but REJECTED — its free
  // tier is $5 of credits that expire in 30 days, not a permanently-free tier.
  // Violates the no-expiring-credits rule (validate_groq_fallback.py L4).

  // ── Tier 3: Google Gemini — OpenAI-compat endpoint, 250K TPM, vision ────────
  // Low RPD on the free tier so it sits mid-chain; high quality + multimodal.
  // Use an AI Studio key (aistudio.google.com), NOT a GCP Console key (limit:0).
  { provider: "google", baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai", model: "gemini-2.5-flash",      envKey: "GEMINI_API_KEY", vision: true },
  { provider: "google", baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai", model: "gemini-2.5-flash-lite", envKey: "GEMINI_API_KEY", vision: true },

  // ── Tier 4: Mistral — 500K TPM but only 2 RPM, OpenAI-compatible ────────────
  // Codestral is strong for code / SQL generation (see TASK_PROFILES).
  { provider: "mistral", baseUrl: "https://api.mistral.ai/v1", model: "mistral-large-latest", envKey: "MISTRAL_API_KEY" },
  { provider: "mistral", baseUrl: "https://api.mistral.ai/v1", model: "codestral-latest",     envKey: "MISTRAL_API_KEY" },

  // ── Tier 5: OpenRouter — :free models, $0/token, 200 req/day ────────────────
  // Gemma 3/4 family supports vision via OpenAI-compatible image_url blocks.
  { provider: "openrouter", baseUrl: "https://openrouter.ai/api/v1", model: "nvidia/nemotron-3-super-120b-a12b:free",    envKey: "OPENROUTER_API_KEY", extraHeaders: { "HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive" } },
  { provider: "openrouter", baseUrl: "https://openrouter.ai/api/v1", model: "google/gemma-4-31b-it:free",                envKey: "OPENROUTER_API_KEY", extraHeaders: { "HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive" }, vision: true },
  { provider: "openrouter", baseUrl: "https://openrouter.ai/api/v1", model: "openai/gpt-oss-120b:free",                  envKey: "OPENROUTER_API_KEY", extraHeaders: { "HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive" } },
  { provider: "openrouter", baseUrl: "https://openrouter.ai/api/v1", model: "google/gemma-4-26b-a4b-it:free",            envKey: "OPENROUTER_API_KEY", extraHeaders: { "HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive" }, vision: true },
  { provider: "openrouter", baseUrl: "https://openrouter.ai/api/v1", model: "meta-llama/llama-3.3-70b-instruct:free",    envKey: "OPENROUTER_API_KEY", extraHeaders: { "HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive" } },
  { provider: "openrouter", baseUrl: "https://openrouter.ai/api/v1", model: "google/gemma-3-27b-it:free",                envKey: "OPENROUTER_API_KEY", extraHeaders: { "HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive" }, vision: true },
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
export const TASK_PROFILES: Record<string, string[]> = {
  // Cheap, fast tasks → prefer the 8B model
  intent_classification:   ["llama-3.1-8b-instant"],
  slot_extraction:         ["llama-3.1-8b-instant"],
  single_fact_retrieval:   ["llama-3.1-8b-instant"],
  orchestrator_router:     ["llama-3.1-8b-instant"],
  chunk_grader:            ["llama-3.1-8b-instant"],
  hallucination_checker:   ["llama-3.1-8b-instant"],
  // Mid-tier reasoning
  multi_step_orchestration: ["llama-3.3-70b-versatile", "qwen/qwen3-32b"],
  // Heavy synthesis / long output — prefer Scout-17B (30K TPM)
  synthesis_long_output:   ["llama-4-scout-17b-16e-instruct", "llama-3.3-70b-versatile"],
  temporal_fold:           ["llama-4-scout-17b-16e-instruct", "llama-3.3-70b-versatile"],
  temporal_subagent:       ["llama-3.1-8b-instant"],
  // Specialised
  code_or_sql_generation:  ["qwen/qwen3-32b", "llama-3.3-70b-versatile"],
  narrative_report:        ["llama-4-scout-17b-16e-instruct", "llama-3.1-8b-instant"],
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
  ordered.sort((a, b) => entryPen.get(a)! - entryPen.get(b)!);

  // ── Step 3: herd-spread (P1, 2026-06-14) ─────────────────────────────────────
  // Shuffle WITHIN equal-penalty groups so N concurrent calls don't all stampede the exact
  // same head entry and 429 in lockstep — the thundering-herd the 10-worker stress sweep
  // exposed (every call reorders identically -> all hit prov[0] -> all 429 -> all march to
  // prov[1] together). The chain is "good enough + free", so spreading the head across
  // equally-healthy entries buys far more usable throughput under burst than strict order.
  // OFF by default (deterministic order preserved for the Node port test + non-burst callers);
  // callAI opts in with spread=true. A flaky/parked entry has a higher penalty so it's in a
  // later group and never shuffles up ahead of a healthy one.
  if (spread) {
    let i = 0;
    while (i < ordered.length) {
      let j = i + 1;
      const p = entryPen.get(ordered[i])!;
      while (j < ordered.length && entryPen.get(ordered[j])! === p) j++;
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
  return out;
}

// W4 fault-injection (LOCAL-ONLY). The faultInject option simulates provider
// 429/413/down WITHOUT a network call so the wiring battery can prove M1 (fallback),
// M2 (all-down graceful degrade -> "{}"), M4 (413 skip). It is honored ONLY when the
// runtime is local (SUPABASE_URL host kong/localhost/127.0.0.1; prod is *.supabase.co),
// so it is dead in production even if a faultInject option somehow reaches callAI.
const _AI_CHAIN_LOCAL = /\/\/(kong|localhost|127\.0\.0\.1)(:|\/|$)/.test(Deno.env.get("SUPABASE_URL") || "");

export interface FaultInject {
  fail?: string[];      // provider names to force-fail (e.g. ["groq"])
  failAll?: boolean;    // force EVERY provider to fail (all-down degrade -> "{}")
  mode?: "429" | "413" | "down";
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
  } = {}
): Promise<string> {
  const { systemPrompt, temperature = 0.2, maxTokens = 1024, jsonMode = true, taskProfile, sessionKey, faultInject } = options;

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

  // One pass down a chain: returns the answer on the first success, or null if every entry
  // was skipped/failed (so the caller can run the P3 retry pass before degrading to "{}").
  const attemptChain = async (chainArr: ProviderEntry[]): Promise<string | null> => {
    for (const entry of chainArr) {
      const apiKey = Deno.env.get(entry.envKey);
      if (!apiKey) continue;
      const modelSlot = `${entry.provider}:${entry.model}`;
      // P1 roadmap 2026-05-27 turn 7 + P4 2026-06-14 — skip a parked PROVIDER or this parked MODEL.
      if (isSlotBlocked(entry.provider) || isSlotBlocked(modelSlot)) continue;

      // W4 fault-injection (LOCAL-ONLY): simulate this provider failing (429/413/down)
      // without a network call, so the next provider is tried (M1), all-down degrades
      // to "{}" (M2), and 413 is skipped (M4). Honored only locally; dead in prod.
      if (faultInject && _AI_CHAIN_LOCAL &&
          (faultInject.failAll === true || (faultInject.fail || []).includes(entry.provider))) {
        console.warn(`[ai-chain] FAULT-INJECT ${entry.provider}/${entry.model} (${faultInject.mode || "429"}) — simulated skip`);
        recordSlotFailure(entry.provider);
        continue;
      }

      const effectiveMaxTokens = entry.maxTokensCap
        ? Math.min(maxTokens, entry.maxTokensCap)
        : maxTokens;

      // Token-aware pre-skip (FreeLLMAPI canUseTokens idea, 2026-05-30): if this
      // model's total context window provably can't fit prompt + output, skip it
      // here instead of wasting a round-trip to discover the 413. Only applies to
      // entries that declare a contextCap (small-context models like Cerebras);
      // no-op for everything else. 256t margin covers chat-template overhead.
      if (entry.contextCap) {
        const estPromptTokens = estimateTokens((systemPrompt ?? "") + prompt);
        if (estPromptTokens + effectiveMaxTokens + 256 > entry.contextCap) {
          console.warn(`[ai-chain] ${entry.provider}/${entry.model} pre-skipped (prompt ~${estPromptTokens}t + ${effectiveMaxTokens}t out > ${entry.contextCap}t context)`);
          continue;
        }
      }

      try {
        const res = await fetch(`${entry.baseUrl}/chat/completions`, {
          method: "POST",
          signal: AbortSignal.timeout(60000),
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
          }),
        });

        // Rate-limited / payload too large / unavailable: try next. P2: honor Retry-After for
        // the cooldown window. 429+413 are per-MODEL (TPM / prompt size) -> park just this
        // model so its siblings stay usable; 503 is provider-wide -> park the whole provider.
        if (res.status === 429 || res.status === 413 || res.status === 503) {
          const raMs = parseRetryAfter(res.headers.get("retry-after"));
          console.warn(`[ai-chain] ${entry.provider}/${entry.model} skipped (HTTP ${res.status}${raMs ? `, retry-after ${Math.round(raMs / 1000)}s` : ""})`);
          recordSlotFailure(modelSlot, raMs);
          if (res.status === 503) recordSlotFailure(entry.provider, raMs);
          continue;
        }

        if (!res.ok) {
          const errSnippet = (await res.text()).slice(0, 120);
          console.warn(`[ai-chain] ${entry.provider}/${entry.model} error ${res.status}: ${errSnippet} — trying next`);
          recordSlotFailure(entry.provider);   // auth/5xx/other = provider-wide
          continue;
        }

        const data = await res.json();
        const content: string | undefined = data?.choices?.[0]?.message?.content;
        if (content) {
          // Strip <think>...</think> reasoning blocks (Qwen3-32B et al.) so
          // chain-of-thought doesn't leak. V4 caught Qwen3 leaking
          // "worker_profiles" inside a think block while reasoning about
          // refusing a prompt-injection probe.
          const stripped = stripReasoningBlocks(content);
          if (stripped) {
            console.log(`[ai-chain] served by ${entry.provider} / ${entry.model}`);
            recordSlotSuccess(entry.provider);
            recordSlotSuccess(modelSlot);
            // Pin this conversation to the model that just served it so the next
            // turn stays on the same model (no-op when sessionKey is absent).
            if (sessionKey) setStickyModel(sessionKey, entry.provider, entry.model);
            return stripped;
          }
          // Reasoning model emitted only a think block with no usable answer —
          // fall through to the next provider rather than return empty.
          console.warn(`[ai-chain] ${entry.provider}/${entry.model} returned only reasoning, no answer — trying next`);
        } else {
          console.warn(`[ai-chain] ${entry.provider}/${entry.model} returned empty content — trying next`);
        }
      } catch (err) {
        console.warn(`[ai-chain] ${entry.provider}/${entry.model} threw: ${String(err).slice(0, 80)}`);
        recordSlotFailure(entry.provider);   // network/abort = provider-wide
        recordSlotFailure(modelSlot);
      }
    }
    return null;
  };

  // Pass 1 — herd-spread chain (P1), sticky pin first.
  const first = await attemptChain(applySticky(reorderChain(taskProfile, true)));
  if (first !== null) return first;

  // P3 (2026-06-14): one bounded jittered-retry pass before degrading to "{}". A concurrent
  // burst can 429 every slot on pass 1; a short randomized backoff (300-1200ms) lets per-second
  // token buckets refill AND de-synchronizes this call from the herd, then we re-spread and try
  // once more. Skipped for the all-down fault-injection (M2) so that test still degrades to "{}"
  // immediately, and capped at exactly one extra pass so a call can never hang.
  if (!(faultInject?.failAll)) {
    await new Promise((r) => setTimeout(r, 300 + Math.floor(Math.random() * 900)));
    const second = await attemptChain(applySticky(reorderChain(taskProfile, true)));
    if (second !== null) return second;
  }

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

  if (!imageDataUrl) return "{}";

  // OpenAI-compatible vision content: text block + image_url block.
  const userContent = [
    { type: "text",      text: prompt },
    { type: "image_url", image_url: { url: imageDataUrl, detail } },
  ];

  const messages = systemPrompt
    ? [{ role: "system", content: systemPrompt }, { role: "user", content: userContent }]
    : [{ role: "user", content: userContent }];

  for (const entry of PROVIDER_CHAIN) {
    if (!entry.vision) continue;
    const apiKey = Deno.env.get(entry.envKey);
    if (!apiKey) continue;

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
        }),
      });

      if (res.status === 429 || res.status === 413 || res.status === 503) {
        console.warn(`[ai-chain:vision] ${entry.provider}/${entry.model} skipped (HTTP ${res.status})`);
        continue;
      }

      if (!res.ok) {
        const errSnippet = (await res.text()).slice(0, 120);
        console.warn(`[ai-chain:vision] ${entry.provider}/${entry.model} error ${res.status}: ${errSnippet} — trying next`);
        continue;
      }

      const data = await res.json();
      const content: string | undefined = data?.choices?.[0]?.message?.content;
      if (content) {
        console.log(`[ai-chain:vision] served by ${entry.provider} / ${entry.model}`);
        return stripReasoningBlocks(content);
      }
      console.warn(`[ai-chain:vision] ${entry.provider}/${entry.model} returned empty content — trying next`);
    } catch (err) {
      console.warn(`[ai-chain:vision] ${entry.provider}/${entry.model} threw: ${String(err).slice(0, 80)}`);
    }
  }

  return "{}";
}
