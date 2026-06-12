// _shared/persona-knowledge.ts
//
// Persona-Knowledge layer (L08 — the 8th memory layer, companion wiring W7). The
// READ/matcher side of the curated DOMAIN knowledge base built by
// tools/ingest_persona_knowledge.py: per-persona SKILL.md sources + free external
// standards, contextually chunked (Anthropic Contextual Retrieval) and embedded
// 384-dim into persona_knowledge.
//
// Closes the gap that persona.ts DOMAIN_LENS only NAMES each persona's knowledge
// wells but never RETRIEVES them. Given the user's turn, embed it and fetch the top
// PERSONA-SCOPED chunks via match_persona_knowledge: Hezekiah pulls technical+shared,
// Zaniah pulls strategic+shared. The scope filter is enforced SERVER-SIDE in the RPC,
// so a strategist can never receive a technical-scope chunk (the O10 isolation wire).
//
// Best-effort, identical contract to skill-library.ts / verified-state.ts: any miss
// (no query, embed unavailable, RPC error, nothing above threshold) returns [] / ""
// so the gateway proceeds with no DOMAIN KNOWLEDGE block (graceful degrade — O12).

import { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { generateEmbeddingCached } from "./embedding-chain.ts";

export const PK_MATCH_LIMIT     = 3;
export const PK_MIN_SIMILARITY  = 0.30;   // cosine; domain-doc chunks, below this is off-topic noise (O8)
export const PK_CHUNK_CHARS     = 320;    // per-chunk cap when formatting
export const PK_BLOCK_CHARS     = 950;    // total block cap — respects the ~2,081-tok static-prompt budget (O9)

// The model persona_knowledge was INGESTED with — the query MUST embed with the
// same model or cosine is noise (the W7 trap). Decoupled from the global Voyage
// default so this corpus can run on a generous free tier (gemini) without
// touching the rest of the platform's Voyage corpora. Flip this AND re-ingest
// with tools/ingest_persona_knowledge.py --embed-model <same> in lock-step
// (e.g. "cloudflare" once a Cloudflare token + bge-small ingest are in place).
const _PK_IS_LOCAL = /(kong|localhost|127\.0\.0\.1)(:|\/|$)/.test(Deno.env.get("SUPABASE_URL") || "");
export const PK_EMBED_MODEL = (Deno.env.get("PERSONA_KNOWLEDGE_EMBED_MODEL")
  || (_PK_IS_LOCAL ? "bge-local" : "gemini")).toLowerCase();

export interface PersonaChunk {
  id:            string;
  persona_scope: string;
  source:        string;
  section:       string | null;
  content:       string;
  similarity:    number;
}

/**
 * Map a resolved persona to the knowledge SCOPES it may retrieve. This IS the O6
 * (same Q -> different corpus) + O10 (isolation) wire. Unknown persona gets only
 * `shared` (a safe default — never technical/strategic without an explicit persona).
 */
export function scopesForPersona(persona: string | null | undefined): string[] {
  const p = String(persona || "").toLowerCase();
  if (p === "hezekiah") return ["technical", "shared"];
  if (p === "zaniah")   return ["strategic", "shared"];
  return ["shared"];
}

/**
 * Retrieve the top persona-scoped domain chunks for the current turn. Returns []
 * on any miss so the caller treats it as "no domain knowledge to add".
 */
export async function loadPersonaKnowledge(
  db: SupabaseClient,
  persona: string | null | undefined,
  query: string,
  opts: { limit?: number; minSimilarity?: number } = {},
): Promise<PersonaChunk[]> {
  if (!query || !query.trim()) return [];
  const scopes = scopesForPersona(persona);

  let embedding: number[];
  try {
    // Pin to the model the corpus was ingested with (the W7 same-model trap), via the
    // (query, model) cache so repeated questions don't re-hit the embed API (scale lever).
    const tagged = await generateEmbeddingCached(db, query.slice(0, 2000), PK_EMBED_MODEL);
    // If the pinned model was rate-limited and we fell back to a DIFFERENT provider, the
    // query vector is in a foreign space vs this corpus -> the RPC would return confident-
    // looking CROSS-SPACE NOISE (an unrelated chunk at ~0.6). That is worse than nothing,
    // so skip retrieval and degrade gracefully (same empty contract as O12). The capacity
    // fix is a higher-limit pinned model (bge-small via Cloudflare/self-host).
    if (tagged.provider !== PK_EMBED_MODEL) {
      console.warn(`[persona-knowledge] embed fell back to '${tagged.provider}' != pinned '${PK_EMBED_MODEL}'; skipping retrieval (cross-space noise guard)`);
      return [];
    }
    embedding = tagged.vector;
  } catch (err) {
    console.warn("[persona-knowledge] embed failed (non-fatal):", err instanceof Error ? err.message : String(err));
    return [];
  }
  if (!embedding || !embedding.length) return [];

  const limit = Math.min(10, Math.max(1, Number(opts.limit ?? PK_MATCH_LIMIT)));
  const minSim = Math.min(1, Math.max(0, Number(opts.minSimilarity ?? PK_MIN_SIMILARITY)));

  const { data, error } = await db.rpc("match_persona_knowledge", {
    query_embedding: embedding,
    scopes,
    match_count:     limit,
    min_similarity:  minSim,
  });
  if (error) {
    console.warn("[persona-knowledge] match_persona_knowledge failed (non-fatal):", error.message);
    return [];
  }
  return (data || []) as PersonaChunk[];
}

/**
 * Render matched domain chunks into a tight, TOKEN-CAPPED prompt block. Pure (no IO)
 * — Node-probeable. Returns "" when empty so the caller concatenates safely. Caps
 * both per-chunk (PK_CHUNK_CHARS) and total (PK_BLOCK_CHARS) so a fat retrieval can
 * never blow the small-model context window (O9).
 */
export function formatPersonaKnowledge(rows: PersonaChunk[]): string {
  if (!rows || !rows.length) return "";
  const lines = ["DOMAIN KNOWLEDGE (authoritative references for your specialty — ground your answer in these, cite the source):"];
  let budget = PK_BLOCK_CHARS;
  for (const r of rows) {
    const pct = Math.round(Math.max(0, Math.min(1, Number(r.similarity) || 0)) * 100);
    const src = String(r.source || "").replace(/\s+/g, " ").trim();
    const text = String(r.content || "").replace(/\s+/g, " ").trim().slice(0, PK_CHUNK_CHARS);
    if (!text) continue;
    const line = `- [${pct}% · ${src}] ${text}`;
    if (line.length > budget) break;   // total cap — stop before overflowing the budget
    lines.push(line);
    budget -= line.length;
  }
  return lines.length > 1 ? lines.join("\n") : "";
}
