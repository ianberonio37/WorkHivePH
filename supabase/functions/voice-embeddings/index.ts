import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { logRequestStart } from "../_shared/logger.ts";

import { getCorsHeaders } from "../_shared/cors.ts";
import { log } from "../_shared/logger.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
// Arc R (A01/LLM10): verify_jwt=false + paid embedding API — bound external anon abuse.
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { resolveIdentity } from "../_shared/tenant-context.ts";
import { checkSoloRateLimit, soloRateLimitKey, soloRateLimitedResponse } from "../_shared/rate-limit.ts";

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
  logRequestStart(req, "voice-embeddings");  // I6 observability
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

    // Arc R (A01/LLM10): verify_jwt=false + a paid embedding API = quota-theft surface for an
    // external anon caller. Bound by identity/IP (service_role + server-to-server callers with
    // no forwarded IP fail open, so the voice-semantic-rag/ai-gateway paths are unaffected).
    {
      const _rlDb = createClient(Deno.env.get("SUPABASE_URL") || "", Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "");
      const _id   = await resolveIdentity(_rlDb, req);
      if (!_id.isServiceRole) {
        const _ip = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim();
        if (_ip) {  // only bucket when there is a real client IP (external caller)
          const _rl = await checkSoloRateLimit(_rlDb, soloRateLimitKey(_id.authUid, _ip));
          if (!_rl.allowed) return soloRateLimitedResponse(corsHeaders);
        }
      }
    }
    // Cap batch size + per-text length (bound provider cost per call).
    if (texts.length > 64) {
      return new Response(
        JSON.stringify({ error: "too many texts (cap 64)" }),
        { status: 413, headers: { ...corsHeaders, "Content-Type": "application/json" } }
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
          log.warn(null, `Jina API error: ${resp.status}`);
        }
      } catch (err) {
        log.warn(null, "Jina API call failed:", { detail: err });
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
    log.error(null, "Unexpected error:", { detail: err });
    return new Response(
      JSON.stringify({ error: "Internal server error" }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }
    );
  }
});
