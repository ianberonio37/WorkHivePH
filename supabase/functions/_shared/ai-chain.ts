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
}

const PROVIDER_CHAIN: ProviderEntry[] = [
  // ── Tier 1: Groq — custom LPU hardware, fastest inference ──────────────────
  // Llama 4 Scout: 30K TPM (highest on Groq free tier), 500K TPD
  { provider: "groq", baseUrl: "https://api.groq.com/openai/v1", model: "meta-llama/llama-4-scout-17b-16e-instruct", envKey: "GROQ_API_KEY" },
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
  { provider: "cerebras", baseUrl: "https://api.cerebras.ai/v1", model: "llama-3.3-70b", envKey: "CEREBRAS_API_KEY", maxTokensCap: 4096 },
  { provider: "cerebras", baseUrl: "https://api.cerebras.ai/v1", model: "qwen-3-32b",    envKey: "CEREBRAS_API_KEY", maxTokensCap: 4096 },

  // ── Tier 3: OpenRouter — :free models, $0/token, 200 req/day ────────────────
  { provider: "openrouter", baseUrl: "https://openrouter.ai/api/v1", model: "nvidia/nemotron-3-super-120b-a12b:free",    envKey: "OPENROUTER_API_KEY", extraHeaders: { "HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive" } },
  { provider: "openrouter", baseUrl: "https://openrouter.ai/api/v1", model: "google/gemma-4-31b-it:free",                envKey: "OPENROUTER_API_KEY", extraHeaders: { "HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive" } },
  { provider: "openrouter", baseUrl: "https://openrouter.ai/api/v1", model: "openai/gpt-oss-120b:free",                  envKey: "OPENROUTER_API_KEY", extraHeaders: { "HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive" } },
  { provider: "openrouter", baseUrl: "https://openrouter.ai/api/v1", model: "google/gemma-4-26b-a4b-it:free",            envKey: "OPENROUTER_API_KEY", extraHeaders: { "HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive" } },
  { provider: "openrouter", baseUrl: "https://openrouter.ai/api/v1", model: "meta-llama/llama-3.3-70b-instruct:free",    envKey: "OPENROUTER_API_KEY", extraHeaders: { "HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive" } },
  { provider: "openrouter", baseUrl: "https://openrouter.ai/api/v1", model: "google/gemma-3-27b-it:free",                envKey: "OPENROUTER_API_KEY", extraHeaders: { "HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive" } },
];

export async function callAI(
  prompt: string,
  options: {
    systemPrompt?: string;
    temperature?: number;
    maxTokens?: number;
    jsonMode?: boolean;
  } = {}
): Promise<string> {
  const { systemPrompt, temperature = 0.2, maxTokens = 1024, jsonMode = true } = options;

  const messages = systemPrompt
    ? [{ role: "system", content: systemPrompt }, { role: "user", content: prompt }]
    : [{ role: "user", content: prompt }];

  for (const entry of PROVIDER_CHAIN) {
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
