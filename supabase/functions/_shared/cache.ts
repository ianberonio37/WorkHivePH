// _shared/cache.ts
// Hash-keyed LLM response cache for deterministic prompts (routers, intent
// classifiers, canonical extractors). RAG flywheel showed ~30-40% of
// companion traffic is repeated classification calls — caching these cuts
// TPM burn proportionally.
//
// Backing store: ai_cache table. Schema (created by migration in P1):
//   key TEXT PRIMARY KEY,           -- sha256(model + ":" + prompt_normalized)
//   model TEXT NOT NULL,
//   response_json JSONB NOT NULL,
//   tokens_in INT, tokens_out INT,
//   created_at TIMESTAMPTZ DEFAULT now(),
//   expires_at TIMESTAMPTZ NOT NULL,
//   hit_count INT NOT NULL DEFAULT 0
//
// Default TTL = 24h. Caller picks deterministic-ness; cache.skip() any prompt
// with timestamp or user free-text where repeat-rate is low.

import { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";

const DEFAULT_TTL_SECONDS = 24 * 60 * 60;

function normalize(prompt: string): string {
  // Collapse runs of whitespace, trim. Do NOT lowercase — case can change
  // model output for code/SQL prompts.
  return prompt.replace(/\s+/g, " ").trim();
}

async function hashKey(model: string, prompt: string): Promise<string> {
  const data = new TextEncoder().encode(`${model}:${normalize(prompt)}`);
  const buf  = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, "0")).join("");
}

export interface CacheLookup<T> {
  hit:   boolean;
  data?: T;
  key:   string;
}

export async function cacheLookup<T>(
  db:     SupabaseClient,
  model:  string,
  prompt: string,
): Promise<CacheLookup<T>> {
  const key = await hashKey(model, prompt);
  // canonical-allow: ai_cache is an infrastructure table (hash-keyed LLM response cache); not a user-facing KPI source. Registered in canonical_sources as domain='ai_cache_infra'.
  const { data } = await db
    .from("ai_cache")
    .select("response_json, expires_at")
    .eq("key", key)
    .maybeSingle();
  if (!data) return { hit: false, key };
  if (new Date(data.expires_at).getTime() < Date.now()) return { hit: false, key };
  // Fire-and-forget hit count bump; never block the response.
  db.rpc("ai_cache_bump", { p_key: key }).then(() => {}, () => {});
  return { hit: true, key, data: data.response_json as T };
}

export async function cacheStore<T>(
  db:        SupabaseClient,
  key:       string,
  model:     string,
  response:  T,
  opts: { ttlSeconds?: number; tokensIn?: number; tokensOut?: number } = {},
): Promise<void> {
  const ttl = opts.ttlSeconds ?? DEFAULT_TTL_SECONDS;
  const expiresAt = new Date(Date.now() + ttl * 1000).toISOString();
  // Upsert so we never error on race; conflict on PRIMARY KEY is the expected
  // path under concurrent same-prompt traffic.
  // canonical-allow: ai_cache is an infrastructure table (see lookup site).
  await db.from("ai_cache").upsert({
    key,
    model,
    response_json: response,
    tokens_in:     opts.tokensIn  ?? null,
    tokens_out:    opts.tokensOut ?? null,
    expires_at:    expiresAt,
  }, { onConflict: "key" });
}

/** Convenience wrapper: lookup → on miss run fn → store + return. */
export async function cached<T>(
  db:     SupabaseClient,
  model:  string,
  prompt: string,
  fn:     () => Promise<{ data: T; tokensIn?: number; tokensOut?: number }>,
  ttlSeconds?: number,
): Promise<{ data: T; hit: boolean }> {
  const lookup = await cacheLookup<T>(db, model, prompt);
  if (lookup.hit) return { data: lookup.data as T, hit: true };
  const fresh = await fn();
  await cacheStore(db, lookup.key, model, fresh.data, {
    ttlSeconds,
    tokensIn:  fresh.tokensIn,
    tokensOut: fresh.tokensOut,
  });
  return { data: fresh.data, hit: false };
}
