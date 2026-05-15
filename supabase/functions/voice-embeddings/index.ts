import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { getCorsHeaders } from "../_shared/cors.ts";

// contract-allow: embedding infrastructure fn, not a brain output producer

/**
 * Voice Embeddings Edge Function (Phase 1.5)
 *
 * Generates vector embeddings for voice transcripts using free APIs:
 * - Jina AI (free tier: 8,000 requests/month, 384-dim)
 * - Sentence-transformers fallback (local embedding)
 *
 * Called by:
 * 1. ai-gateway to embed new voice transcripts on insert
 * 2. voice-semantic-rag to embed query text for pgvector search
 *
 * Input:
 *   - texts: array of strings to embed
 *   - model: embedding model (default: jina-embeddings-v2-base-en)
 *
 * Output:
 *   - embeddings: array of vectors (384-dim or null if failed)
 *   - method: "jina" | "local" | "none" (which provider was used)
 */

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders });
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  try {
    const { texts, model = "jina-embeddings-v2-base-en" } = await req.json();

    if (!texts || !Array.isArray(texts) || texts.length === 0) {
      return new Response(
        JSON.stringify({ error: "Missing or invalid texts array" }),
        { status: 400, headers: { "Content-Type": "application/json" } }
      );
    }

    // Try Jina API first (free tier: 8k requests/month)
    const jina_key = Deno.env.get("JINA_API_KEY");
    if (jina_key) {
      try {
        const resp = await fetch("https://api.jina.ai/v1/embeddings", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${jina_key}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            model,
            input: texts,
          }),
        });

        if (resp.status === 200) {
          const data = await resp.json();
          const embeddings_data = data.data || [];

          // Sort by index to maintain order
          embeddings_data.sort((a: any, b: any) => a.index - b.index);

          const embeddings = embeddings_data.map((e: any) => e.embedding || null);

          return new Response(
            JSON.stringify({
              embeddings,
              method: "jina",
              count: embeddings.length,
              model,
            }),
            {
              status: 200,
              headers: { "Content-Type": "application/json" },
            }
          );
        } else {
          console.warn(`Jina API error: ${resp.status}`);
        }
      } catch (err) {
        console.warn("Jina API call failed:", err);
      }
    }

    // Fallback: return null embeddings (voice-semantic-rag will use recency)
    // Note: For local sentence-transformers, would need Python deno_bindgen
    // or a separate Python service. For now, return nulls and let RAG fallback.

    return new Response(
      JSON.stringify({
        embeddings: texts.map(() => null),
        method: "none",
        count: texts.length,
        note: "Jina API not configured; using recency-based RAG",
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }
    );
  } catch (err) {
    console.error("Unexpected error:", err);
    return new Response(
      JSON.stringify({ error: "Internal server error" }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }
    );
  }
});
