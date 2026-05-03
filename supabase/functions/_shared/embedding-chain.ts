// Multi-provider embedding fallback chain for WorkHive RAG.
// All providers output 384-dim vectors compatible with the existing
// vector(384) schema on *_knowledge tables.
//
// Order of attempt (free-tier sustainability):
//   1. Voyage AI (200M tokens/month free, voyage-3-lite truncated to 384)
//   2. Jina AI (100M tokens/month free, jina-embeddings-v3 with dim=384)
//
// If a provider returns 401/403/429/503, the next is tried.
// If a provider's key is not set, that provider is skipped.

const TARGET_DIM = 384;

type EmbeddingProvider = {
  name: string;
  envKey: string;
  call: (text: string, apiKey: string) => Promise<number[]>;
};

// ── Voyage AI ────────────────────────────────────────────────────────────
// voyage-3.5-lite supports {256, 512, 1024, 2048} as native dims — 384 is not
// in that set. Request 512 (smallest >= 384) then truncate to 384. The model
// is Matryoshka-trained, so the first 384 dims preserve quality.
async function voyageEmbed(text: string, apiKey: string): Promise<number[]> {
  const res = await fetch("https://api.voyageai.com/v1/embeddings", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      input: [text],
      model: "voyage-3.5-lite",
      output_dimension: 512,
      input_type: "document",
    }),
  });
  if (!res.ok) {
    const err = (await res.text()).slice(0, 160);
    throw new Error(`voyage ${res.status}: ${err}`);
  }
  const data = await res.json();
  const vec = data?.data?.[0]?.embedding;
  if (!Array.isArray(vec) || vec.length < TARGET_DIM) {
    throw new Error(`voyage returned bad shape: ${typeof vec === "object" ? (vec as unknown[])?.length : typeof vec}`);
  }
  return vec.slice(0, TARGET_DIM);
}

// ── Jina AI ──────────────────────────────────────────────────────────────
async function jinaEmbed(text: string, apiKey: string): Promise<number[]> {
  const res = await fetch("https://api.jina.ai/v1/embeddings", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: "jina-embeddings-v3",
      input: [text],
      task: "retrieval.passage",
      dimensions: TARGET_DIM,
    }),
  });
  if (!res.ok) {
    const err = (await res.text()).slice(0, 160);
    throw new Error(`jina ${res.status}: ${err}`);
  }
  const data = await res.json();
  const vec = data?.data?.[0]?.embedding;
  if (!Array.isArray(vec) || vec.length !== TARGET_DIM) {
    throw new Error(`jina returned bad shape: ${typeof vec === "object" ? (vec as unknown[])?.length : typeof vec}`);
  }
  return vec;
}

const PROVIDERS: EmbeddingProvider[] = [
  { name: "voyage", envKey: "VOYAGE_API_KEY", call: voyageEmbed },
  { name: "jina",   envKey: "JINA_API_KEY",   call: jinaEmbed },
];

/**
 * Generate a 384-dim embedding by trying each provider in order.
 * Throws if no provider has a valid key OR if every configured provider failed.
 */
export async function generateEmbedding(text: string): Promise<number[]> {
  if (!text || !text.trim()) {
    throw new Error("Cannot embed empty text");
  }

  const errors: string[] = [];
  for (const provider of PROVIDERS) {
    const apiKey = Deno.env.get(provider.envKey);
    if (!apiKey || apiKey.startsWith("PASTE_")) {
      continue; // not configured
    }
    try {
      const vec = await provider.call(text, apiKey);
      // Tag which provider succeeded for observability
      console.log(`[embedding] ok via ${provider.name} (${vec.length} dims)`);
      return vec;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.warn(`[embedding] ${provider.name} failed: ${msg} — trying next`);
      errors.push(`${provider.name}: ${msg}`);
    }
  }

  if (errors.length === 0) {
    throw new Error(
      "No embedding provider configured. Set VOYAGE_API_KEY or JINA_API_KEY."
    );
  }
  throw new Error(`All embedding providers failed: ${errors.join(" | ")}`);
}
