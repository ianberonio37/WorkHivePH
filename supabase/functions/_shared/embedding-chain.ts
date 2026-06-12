// Multi-provider embedding fallback chain for WorkHive RAG.
// All providers output 384-dim vectors compatible with the existing
// vector(384) schema on *_knowledge tables.
//
// Order of attempt (free-tier sustainability):
//   1. Voyage AI (200M tokens/month free, voyage-3-lite truncated to 384)
//   2. Jina AI (100M tokens/month free, jina-embeddings-v3 with dim=384)
//   3. Google Gemini (gemini-embedding-001, output dim=384, L2-normalized)
//
// If a provider returns 401/403/429/503, the next is tried.
// If a provider's key is not set, that provider is skipped.

const TARGET_DIM = 384;

import { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";

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

// ── Google Gemini ──────────────────────────────────────────────────────────
// OpenAI-compatible embeddings endpoint. gemini-embedding-001 supports a
// configurable output dimension via `dimensions`; we request 384 to match the
// vector(384) schema. IMPORTANT: Gemini does NOT unit-normalize outputs below
// 3072 dims (Voyage and Jina return normalized vectors), so we L2-normalize
// here to keep all three providers in a comparable space for cosine search.
async function geminiEmbed(text: string, apiKey: string): Promise<number[]> {
  const res = await fetch("https://generativelanguage.googleapis.com/v1beta/openai/embeddings", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: "gemini-embedding-001",
      input: [text],
      dimensions: TARGET_DIM,
    }),
  });
  if (!res.ok) {
    const err = (await res.text()).slice(0, 160);
    throw new Error(`gemini ${res.status}: ${err}`);
  }
  const data = await res.json();
  const vec = data?.data?.[0]?.embedding;
  if (!Array.isArray(vec) || vec.length !== TARGET_DIM) {
    throw new Error(`gemini returned bad shape: ${typeof vec === "object" ? (vec as unknown[])?.length : typeof vec}`);
  }
  const norm = Math.sqrt(vec.reduce((s: number, x: number) => s + x * x, 0)) || 1;
  return vec.map((x: number) => x / norm);
}

// ── Cloudflare Workers AI · bge-small-en-v1.5 (384-dim NATIVE) ──────────────
// The durable free option (Ian, 2026-06-12): ~10k neurons/day ≈ thousands of
// embeds/day, no credit card, 384-dim native (no slicing). SAME model as the
// self-host sentence-transformers `BAAI/bge-small-en-v1.5` used by the ingest
// tool, so local-ingest and edge-query land in ONE space. Activates when both
// CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN are set; skipped otherwise.
async function cloudflareEmbed(text: string, apiToken: string): Promise<number[]> {
  const acct = Deno.env.get("CLOUDFLARE_ACCOUNT_ID");
  if (!acct) throw new Error("CLOUDFLARE_ACCOUNT_ID not set");
  const res = await fetch(
    `https://api.cloudflare.com/client/v4/accounts/${acct}/ai/run/@cf/baai/bge-small-en-v1.5`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": `Bearer ${apiToken}` },
      body: JSON.stringify({ text: [text] }),
    },
  );
  if (!res.ok) {
    throw new Error(`cloudflare ${res.status}: ${(await res.text()).slice(0, 160)}`);
  }
  const data = await res.json();
  const vec = data?.result?.data?.[0];
  if (!Array.isArray(vec) || vec.length !== TARGET_DIM) {
    throw new Error(`cloudflare returned bad shape: ${Array.isArray(vec) ? vec.length : typeof vec}`);
  }
  const norm = Math.sqrt(vec.reduce((s: number, x: number) => s + x * x, 0)) || 1;
  return vec.map((x: number) => x / norm);
}

// ── Self-host bge-small-en-v1.5 via the local embed_server (NO rate limit) ──
// The durable capacity fix for many concurrent users: free embedding APIs all
// rate-limit, a self-hosted model does not. Calls tools/embed_server.py over the
// docker network (BGE_EMBED_URL, e.g. http://host.docker.internal:8901/embed). SAME
// model as the fastembed ingest path -> one vector space. The provider's "apiKey" IS
// the URL (envKey BGE_EMBED_URL), so it activates only when that env is set.
async function bgeLocalEmbed(_text: string, url: string): Promise<number[]> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ texts: [_text] }),
  });
  if (!res.ok) {
    throw new Error(`bge-local ${res.status}: ${(await res.text()).slice(0, 160)}`);
  }
  const data = await res.json();
  const vec = data?.embeddings?.[0];
  if (!Array.isArray(vec) || vec.length !== TARGET_DIM) {
    throw new Error(`bge-local returned bad shape: ${Array.isArray(vec) ? vec.length : typeof vec}`);
  }
  return vec;
}

// The full roster. A provider with no key is skipped, so listing all is safe.
const ALL_PROVIDERS: EmbeddingProvider[] = [
  { name: "bge-local",  envKey: "BGE_EMBED_URL",        call: bgeLocalEmbed },
  { name: "voyage",     envKey: "VOYAGE_API_KEY",       call: voyageEmbed },
  { name: "gemini",     envKey: "GEMINI_API_KEY",       call: geminiEmbed },
  { name: "cloudflare", envKey: "CLOUDFLARE_API_TOKEN", call: cloudflareEmbed },
  { name: "jina",       envKey: "JINA_API_KEY",         call: jinaEmbed },
  // NOTE: Mistral is intentionally absent — mistral-embed is 1024-dim, not 384,
  // so it cannot join a vector(384) chain without corrupting the space.
];

// ── Per-corpus pinned primary (the 2026-06-12 revamp) ──────────────────────
// A blind fallback chain is a CORRECTNESS bug for pgvector retrieval: a corpus
// embedded with provider A but queried with provider B lands in a DIFFERENT
// vector space, so cosine similarity is noise and retrieval silently returns
// nothing (proven live — persona_knowledge had split across Voyage+Jina spaces).
//
// The embedding MODEL is a property of the CORPUS. So the primary is pinned and
// can be overridden PER CALL: every existing platform corpus (fault_knowledge,
// pm_knowledge, asset-brain, semantic-search) was embedded with Voyage, so the
// GLOBAL default stays 'voyage' and nothing regresses. A corpus that re-embeds
// with another model (persona_knowledge -> gemini, or -> cloudflare/bge-small)
// passes its own model to generateEmbedding(text, model). Failover still happens
// so an outage doesn't 500 the request, but a non-primary answer is logged
// LOUDLY because it may not match the corpus space. Keep ingest + query in
// lock-step: re-embed a corpus AND flip its pin together.
const EMBEDDING_PRIMARY = (Deno.env.get("EMBEDDING_PRIMARY") || "voyage").toLowerCase();

// The local edge runtime is NOT launched with functions/.env, so vars added there aren't
// in Deno.env without a full `supabase start`. Default the self-host bge server URL when
// running locally (SUPABASE_URL host = kong/localhost/127); prod sets BGE_EMBED_URL
// explicitly (or leaves it empty -> bge-local skipped). Same precedent as the rate-limit
// override's code default.
const _IS_LOCAL_EMBED = /(kong|localhost|127\.0\.0\.1)(:|\/|$)/.test(Deno.env.get("SUPABASE_URL") || "");
const BGE_EMBED_URL = Deno.env.get("BGE_EMBED_URL") || (_IS_LOCAL_EMBED ? "http://host.docker.internal:8901/embed" : "");

function orderedProviders(primary: string): EmbeddingProvider[] {
  const head = ALL_PROVIDERS.filter((p) => p.name === primary);
  const rest = ALL_PROVIDERS.filter((p) => p.name !== primary);
  return [...head, ...rest];
}

/**
 * Generate a 384-dim embedding using the pinned primary first, falling back to
 * the others only on failure. Pass `pin` to query a corpus embedded with a
 * specific model (e.g. "gemini" for persona_knowledge); omit it for the global
 * default. Throws if no provider has a valid key OR every configured one failed.
 */
export async function generateEmbedding(text: string, pin?: string): Promise<number[]> {
  return (await generateEmbeddingTagged(text, pin)).vector;
}

/** Like generateEmbedding but also returns the provider that answered, so a
 *  caller can detect a space-diverging fallback. */
export async function generateEmbeddingTagged(
  text: string,
  pin?: string,
): Promise<{ vector: number[]; provider: string }> {
  if (!text || !text.trim()) {
    throw new Error("Cannot embed empty text");
  }
  const wanted = (pin || EMBEDDING_PRIMARY).toLowerCase();

  const errors: string[] = [];
  for (const provider of orderedProviders(wanted)) {
    // bge-local's "key" is its URL (env or local default), not a secret in Deno.env.
    const apiKey = provider.name === "bge-local" ? BGE_EMBED_URL : Deno.env.get(provider.envKey);
    if (!apiKey || apiKey.startsWith("PASTE_")) {
      continue; // not configured
    }
    try {
      const vec = await provider.call(text, apiKey);
      if (provider.name === wanted) {
        console.log(`[embedding] ok via ${provider.name} (${vec.length} dims, pinned)`);
      } else {
        // A non-primary answer means the corpus (embedded with `wanted`) and this
        // query vector may be in DIFFERENT spaces — retrieval can degrade.
        console.warn(
          `[embedding] SPACE-DIVERGENCE: wanted '${wanted}' unavailable, answered via ` +
          `'${provider.name}' — retrieval against a ${wanted}-embedded corpus may be ` +
          `degraded until '${wanted}' recovers.`,
        );
      }
      return { vector: vec, provider: provider.name };
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.warn(`[embedding] ${provider.name} failed: ${msg} — trying next`);
      errors.push(`${provider.name}: ${msg}`);
    }
  }

  if (errors.length === 0) {
    throw new Error(
      "No embedding provider configured. Set BGE_EMBED_URL, VOYAGE_API_KEY, GEMINI_API_KEY, CLOUDFLARE_API_TOKEN or JINA_API_KEY.",
    );
  }
  throw new Error(`All embedding providers failed: ${errors.join(" | ")}`);
}

// ── Query-embedding cache (the "many users" lever) ─────────────────────────
async function _sha256(s: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function _normQuery(s: string): string {
  return s.toLowerCase().replace(/\s+/g, " ").trim().slice(0, 2000);
}

/**
 * Embed with a persistent (query, model) cache. At scale many users ask SIMILAR
 * questions, so the cache makes embed-API load scale with UNIQUE queries, not total — a
 * repeat is a DB read, not an API call. Caches ONLY same-space vectors (the answering
 * provider must equal `pin`); a foreign-space fallback is returned but never cached, so
 * the cache can't be poisoned. Fully best-effort: any cache error falls through to a live
 * embed. Returns { vector, provider, cached }.
 */
export async function generateEmbeddingCached(
  db: SupabaseClient | null,
  text: string,
  pin?: string,
): Promise<{ vector: number[]; provider: string; cached: boolean }> {
  const wanted = (pin || EMBEDDING_PRIMARY).toLowerCase();
  let hash = "";
  if (db && text && text.trim()) {
    try {
      hash = await _sha256(_normQuery(text));
      const { data } = await db.from("embedding_cache")
        .select("embedding").eq("query_hash", hash).eq("model", wanted).maybeSingle();
      const raw = (data as { embedding?: unknown } | null)?.embedding;
      if (raw) {
        const vec = typeof raw === "string" ? JSON.parse(raw) : raw;
        if (Array.isArray(vec) && vec.length === TARGET_DIM) {
          db.from("embedding_cache").update({ last_used: new Date().toISOString() })
            .eq("query_hash", hash).eq("model", wanted).then(() => {}, () => {});
          return { vector: vec as number[], provider: wanted, cached: true };
        }
      }
    } catch (_e) { /* cache miss/unavailable -> live embed */ }
  }
  const tagged = await generateEmbeddingTagged(text, wanted);
  if (db && hash && tagged.provider === wanted) {
    try {
      const lit = "[" + tagged.vector.map((x) => x.toFixed(6)).join(",") + "]";
      await db.from("embedding_cache").upsert(
        { query_hash: hash, model: wanted, embedding: lit, last_used: new Date().toISOString() },
        { onConflict: "query_hash,model" },
      );
    } catch (_e) { /* best-effort */ }
  }
  return { vector: tagged.vector, provider: tagged.provider, cached: false };
}


// ── Reranker ─────────────────────────────────────────────────────────────
//
// Cosine distance over embeddings returns "vector neighbors", which is
// fast but lossy. A reranker takes the top-K cosine candidates and
// re-orders them by true semantic relevance, lifting answer quality
// without changing the embedding model. Use whenever a callAI prompt
// will reason over retrieved chunks.
//
// Voyage AI offers `rerank-2-lite` on a generous free tier. Falls back
// to identity (no-op reorder) if the API key is missing or the call
// fails -- relevance ranking is observability-tier, never the critical
// path.

export interface RerankCandidate {
  /** Original cosine score (higher = closer). Optional, used for tie-break. */
  score?:   number;
  /** Free-form text to rerank. The reranker reads this. */
  text:     string;
  /** Anything else the caller wants to keep paired with the text. */
  meta?:    Record<string, unknown>;
}

export interface RerankResult {
  text:           string;
  /** Rerank score, 0..1 from Voyage. */
  relevance:      number;
  /** Caller's meta is passed through. */
  meta?:          Record<string, unknown>;
  /** Original cosine score if the caller supplied one. */
  cosine_score?:  number;
}

const VOYAGE_RERANK_URL   = "https://api.voyageai.com/v1/rerank";
const VOYAGE_RERANK_MODEL = "rerank-2-lite";

export async function rerank(
  query:      string,
  candidates: RerankCandidate[],
  topN:       number = 5,
): Promise<RerankResult[]> {
  if (!candidates.length) return [];
  // Identity fallback: caller still gets the array back, just without re-ordering.
  const identity = (): RerankResult[] => candidates.slice(0, topN).map((c) => ({
    text:         c.text,
    relevance:    c.score ?? 0,
    meta:         c.meta,
    cosine_score: c.score,
  }));

  const apiKey = Deno.env.get("VOYAGE_API_KEY");
  if (!apiKey) {
    console.warn("[rerank] VOYAGE_API_KEY missing — returning identity order");
    return identity();
  }

  try {
    const res = await fetch(VOYAGE_RERANK_URL, {
      method: "POST",
      headers: {
        "Content-Type":  "application/json",
        "Authorization": `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model:     VOYAGE_RERANK_MODEL,
        query:     query.slice(0, 4000),
        documents: candidates.map((c) => c.text.slice(0, 4000)),
        top_k:     topN,
      }),
    });
    if (!res.ok) {
      const err = (await res.text()).slice(0, 200);
      console.warn(`[rerank] voyage ${res.status}: ${err} — identity fallback`);
      return identity();
    }
    const data = await res.json();
    const ranked = data?.data;
    if (!Array.isArray(ranked)) return identity();
    return ranked.map((r: { index: number; relevance_score: number }) => {
      const src = candidates[r.index];
      return {
        text:         src.text,
        relevance:    Number(r.relevance_score) || 0,
        meta:         src.meta,
        cosine_score: src.score,
      };
    });
  } catch (err) {
    console.warn(`[rerank] threw: ${err instanceof Error ? err.message : String(err)} — identity fallback`);
    return identity();
  }
}
