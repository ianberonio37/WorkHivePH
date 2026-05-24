// Multi-provider AI fallback chain for WorkHive edge functions.
// All providers use OpenAI-compatible chat completions format.
// Each API key is read from env — missing keys are silently skipped.
// Order: fastest / most generous limits first, deeper fallbacks last.
// Only permanently free tiers — no credits that expire.

interface ProviderEntry {
  provider: string;
  baseUrl: string;
  model: string;
  envKey: string;
  maxTokensCap?: number;        // hard cap for providers with context limits
  extraHeaders?: Record<string, string>;
  vision?: boolean;             // true if this model accepts image_url content blocks
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
  { provider: "cerebras", baseUrl: "https://api.cerebras.ai/v1", model: "llama-3.3-70b", envKey: "CEREBRAS_API_KEY", maxTokensCap: 4096 },
  { provider: "cerebras", baseUrl: "https://api.cerebras.ai/v1", model: "qwen-3-32b",    envKey: "CEREBRAS_API_KEY", maxTokensCap: 4096 },
  { provider: "cerebras", baseUrl: "https://api.cerebras.ai/v1", model: "llama3.1-8b",   envKey: "CEREBRAS_API_KEY", maxTokensCap: 4096 },

  // ── Tier 3: OpenRouter — :free models, $0/token, 200 req/day ────────────────
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

export function reorderChain(taskProfile?: string): ProviderEntry[] {
  if (!taskProfile) return PROVIDER_CHAIN;
  const preferred = TASK_PROFILES[taskProfile];
  if (!preferred || !preferred.length) return PROVIDER_CHAIN;

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
  return [...matched, ...rest];
}

export async function callAI(
  prompt: string,
  options: {
    systemPrompt?: string;
    temperature?: number;
    maxTokens?: number;
    jsonMode?: boolean;
    taskProfile?: string;
  } = {}
): Promise<string> {
  const { systemPrompt, temperature = 0.2, maxTokens = 1024, jsonMode = true, taskProfile } = options;

  const messages = systemPrompt
    ? [{ role: "system", content: systemPrompt }, { role: "user", content: prompt }]
    : [{ role: "user", content: prompt }];

  for (const entry of reorderChain(taskProfile)) {
    const apiKey = Deno.env.get(entry.envKey);
    if (!apiKey) continue;

    const effectiveMaxTokens = entry.maxTokensCap
      ? Math.min(maxTokens, entry.maxTokensCap)
      : maxTokens;

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

      // Rate-limited, payload too large, or service unavailable: try next
      if (res.status === 429 || res.status === 413 || res.status === 503) {
        console.warn(`[ai-chain] ${entry.provider}/${entry.model} skipped (HTTP ${res.status})`);
        continue;
      }

      if (!res.ok) {
        const errSnippet = (await res.text()).slice(0, 120);
        console.warn(`[ai-chain] ${entry.provider}/${entry.model} error ${res.status}: ${errSnippet} — trying next`);
        continue;
      }

      const data = await res.json();
      const content: string | undefined = data?.choices?.[0]?.message?.content;
      if (content) {
        console.log(`[ai-chain] served by ${entry.provider} / ${entry.model}`);
        return content;
      }

      console.warn(`[ai-chain] ${entry.provider}/${entry.model} returned empty content — trying next`);
    } catch (err) {
      console.warn(`[ai-chain] ${entry.provider}/${entry.model} threw: ${String(err).slice(0, 80)}`);
    }
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
        return content;
      }
      console.warn(`[ai-chain:vision] ${entry.provider}/${entry.model} returned empty content — trying next`);
    } catch (err) {
      console.warn(`[ai-chain:vision] ${entry.provider}/${entry.model} threw: ${String(err).slice(0, 80)}`);
    }
  }

  return "{}";
}
