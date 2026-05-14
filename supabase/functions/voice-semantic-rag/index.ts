import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.38.4";

/**
 * Voice Semantic RAG Edge Function (Phase 1 + Phase 1.5)
 *
 * Performs semantic similarity search over a worker's voice journal.
 * Called by voice-handler.js to find semantically similar past entries.
 *
 * Phase 1: Recency-based RAG (last 5 turns, last 30 days)
 * Phase 1.5: Optional semantic search via pgvector + embeddings
 *
 * Input:
 *   - auth_uid: worker's UUID
 *   - query_text: current transcript or question
 *   - limit: number of results (default 5)
 *
 * Output:
 *   - results: array of { transcript, reply, created_at, similarity }
 *   - method: "semantic" (pgvector) | "recency" (time-based) | "error"
 *   - count: number of results returned
 */

serve(async (req) => {
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  try {
    const { auth_uid, query_text, limit = 5 } = await req.json();

    if (!auth_uid || !query_text) {
      return new Response(
        JSON.stringify({ error: "Missing auth_uid or query_text" }),
        { status: 400, headers: { "Content-Type": "application/json" } }
      );
    }

    const db = createClient(
      Deno.env.get("SUPABASE_URL") || "",
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || ""
    );

    // Phase 1.5: Try semantic search via pgvector if embeddings are available
    let results: any[] = [];
    let method = "recency";

    try {
      // Step 1: Try to get embedding for the query_text
      // For now, this is a stub. When ai-gateway embeds transcripts,
      // we can call a local embedding endpoint or use Jina API here.
      const queryEmbedding = await _getEmbedding(query_text);

      if (queryEmbedding && queryEmbedding.length > 0) {
        // Step 2: Call search_voice_journal_entries RPC with the embedding vector
        const { data: semanticResults, error: semanticError } = await db.rpc(
          "search_voice_journal_entries",
          {
            query_embedding: queryEmbedding,
            match_auth_uid: auth_uid,
            match_count: limit,
          }
        );

        if (!semanticError && semanticResults && semanticResults.length > 0) {
          results = semanticResults.map((row: any) => ({
            transcript: row.transcript,
            reply: row.reply,
            created_at: row.created_at,
            similarity: row.similarity || 0,
          }));
          method = "semantic";
        }
      }
    } catch (err) {
      console.warn("Semantic search failed, falling back to recency:", err);
      // Fall through to recency fallback
    }

    // Fallback: recency-based search (Phase 1)
    if (results.length === 0) {
      try {
        const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)
          .toISOString();

        const { data: recencyResults, error: recencyError } = await db
          .from("voice_journal_entries")
          .select("transcript, reply, created_at")
          .eq("auth_uid", auth_uid)
          .gt("created_at", thirtyDaysAgo)
          .order("created_at", { ascending: false })
          .limit(limit)
          .execute();

        if (!recencyError && recencyResults && recencyResults.length > 0) {
          results = recencyResults.map((row: any) => ({
            transcript: row.transcript,
            reply: row.reply,
            created_at: row.created_at,
            similarity: 0.5, // No similarity score for recency
          }));
          method = "recency";
        }
      } catch (err) {
        console.error("Recency fallback failed:", err);
      }
    }

    return new Response(
      JSON.stringify({
        results,
        method,
        count: results.length,
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }
    );
  } catch (err) {
    console.error("Unexpected error:", err);
    return new Response(
      JSON.stringify({
        error: "Internal server error",
        results: [],
        method: "error",
        count: 0,
      }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }
    );
  }
});

// Helper: Get embedding for query text (Phase 1.5)
// When Jina API is configured, this calls out to generate embeddings.
// For now, returns null (fallback to recency).
async function _getEmbedding(text: string): Promise<number[] | null> {
  const jina_key = Deno.env.get("JINA_API_KEY");
  if (!jina_key) {
    // No embedding API configured, use recency fallback
    return null;
  }

  try {
    const resp = await fetch("https://api.jina.ai/v1/embeddings", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${jina_key}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "jina-embeddings-v2-base-en",
        input: [text],
      }),
    });

    if (resp.status !== 200) {
      console.warn("Jina API failed:", resp.status);
      return null;
    }

    const data = await resp.json();
    const embeddings = data.data || [];
    if (embeddings.length > 0) {
      return embeddings[0].embedding || null;
    }
  } catch (err) {
    console.warn("Embedding fetch failed:", err);
  }

  return null;
}
