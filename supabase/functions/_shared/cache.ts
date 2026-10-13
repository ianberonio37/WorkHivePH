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

import { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2.110.0";
// aiAnswered is the one definition of "a model replied" (the chain answers "{}" when none did). ai-chain.ts imports
// nothing from this file, and every function that imports this one already imports ai-chain.ts.
import { aiAnswered } from "./ai-chain.ts";

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

/** The chain's "no model answered" (or an empty reply): text that must never be filed as an answer. */
export function isNoAnswer(data: unknown): boolean {
  return typeof data === "string" && !aiAnswered(data);
}

/** Convenience wrapper: lookup → on miss run fn → store + return. A no-answer is returned, never stored. */
export async function cached<T>(
  db:     SupabaseClient,
  model:  string,
  prompt: string,
  fn:     () => Promise<{ data: T; tokensIn?: number; tokensOut?: number }>,
  ttlSeconds?: number,
): Promise<{ data: T; hit: boolean }> {
  const lookup = await cacheLookup<T>(db, model, prompt);
  // ★A NO-ANSWER IS NOT AN ANSWER TO KEEP (2026-10-12, found walking report-sender's spoken request). This stored
  // whatever the fetcher returned, and when every provider failed callAI returns "{}" - so a minute-long outage was
  // filed as THE answer to the prompt for the whole TTL (2-6h at the five callers), served to everyone who repeated
  // it after the providers came back. A no-answer is never stored, and one already stored (local ai_cache held an
  // agentic-rag-router "{}" from 2026-09-07) is read as a miss, so it is asked again instead of served.
  if (lookup.hit && !isNoAnswer(lookup.data)) return { data: lookup.data as T, hit: true };
  const fresh = await fn();
  if (isNoAnswer(fresh.data)) return { data: fresh.data, hit: false };
  await cacheStore(db, lookup.key, model, fresh.data, {
    ttlSeconds,
    tokensIn:  fresh.tokensIn,
    tokensOut: fresh.tokensOut,
  });
  return { data: fresh.data, hit: false };
}

// ── ANSWER caches: keyed on the VERIFIED tenant ──────────────────────────────
// ★AN ANSWER IS ONE TENANT'S RECORDS IN SENTENCES (2026-10-07, found by the eval-bench work). ai-gateway's adaptive
// cache - served instead of a 429 when a person is rate-limited or the org budget is spent - was keyed on
// `gateway:<agent>:<message>` ONLY. Every answer it stores is grounded in the asker's own hive (the live ops snapshot,
// the machine history, the team), or for a hive-less person in their own logbook, journal and memory. So a
// rate-limited person in hive B who asked the same words as someone in hive A was served hive A's answer: another
// plant's machines, failures and people. An anonymous voice-journal caller could be served a signed-in person's.
// A routing or classification cache is different: its prompt is a constant system prompt plus the caller's own words,
// so its output holds nothing the caller did not send (tools/validate_answer_cache_is_tenant_keyed.py keeps that
// distinction explicit for every ai_cache call site).
//
// The tenant is the hive the gateway PROVED membership of, together with the verified auth uid - not the hive alone:
// a companion answer also carries the person's own journal, memory, role and persona, so a hive-mate asking "what did
// I log yesterday?" must not be served someone else's. Never a client-sent id. No verified identity, no answer cache.
export const ANSWER_CACHE_MODEL = "ai-gateway-adaptive";

export function answerCacheTenant(
  verifiedHiveId: string | null | undefined,
  verifiedAuthUid: string | null | undefined,
): string | null {
  const uid = String(verifiedAuthUid ?? "").trim().toLowerCase();
  if (!uid) return null;
  const hive = String(verifiedHiveId ?? "").trim().toLowerCase();
  return hive ? `hive:${hive}|user:${uid}` : `user:${uid}`;
}

// v2: the tenant is part of the key. A v1 key (agent + message only) can never equal a v2 one, and the read below also
// requires the stored row to NAME the tenant, so a row written before this change is never served.
function answerCachePrompt(tenant: string, agent: string, message: string): string {
  return `gateway:v2:${tenant}:${agent}:${normalize(message)}`;
}

/** The ai_cache key one tenant's answer is filed under (read and write use this same normalised hash). */
export function answerCacheKey(tenant: string, agent: string, message: string): Promise<string> {
  return hashKey(ANSWER_CACHE_MODEL, answerCachePrompt(tenant, agent, message));
}

/** This tenant's cached answer to this question, or null. Never a row filed without (or under another) tenant. */
export async function answerCacheLookup(
  db: SupabaseClient, tenant: string | null, agent: string, message: string,
): Promise<string | null> {
  if (!tenant) return null;
  const hit = await cacheLookup<{ answer?: unknown; tenant?: unknown }>(
    db, ANSWER_CACHE_MODEL, answerCachePrompt(tenant, agent, message));
  if (!hit.hit || !hit.data || hit.data.tenant !== tenant) return null;
  const answer = hit.data.answer;
  return typeof answer === "string" && answer ? answer : null;
}

/** File this tenant's answer. A caller with no verified tenant caches nothing. */
export async function answerCacheStore(
  db: SupabaseClient, tenant: string | null, agent: string, message: string, answer: string, ttlSeconds: number,
): Promise<void> {
  if (!tenant || !answer) return;
  await cacheStore(db, await answerCacheKey(tenant, agent, message), ANSWER_CACHE_MODEL, { answer, tenant }, { ttlSeconds });
}
