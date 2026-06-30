// _shared/episodic-memory.ts
//
// Durable EPISODIC-memory recall + persist over the agent_episodic_memory
// table (Phase 7 of AGENTIC_RAG_ROADMAP.md). This is the LONG-TERM memory
// layer — distinct from _shared/memory.ts (working memory = last-N verbatim
// turns + a rolling summary, 90-day retention) and from journal-recall.ts
// (voice-journal's per-user semantic store).
//
// Memory-stack mapping (AI Agent Memory Stack, layer 02 "Episodic"):
//   embedder -> vector store -> top-K episodes -> context assembly.
//   Recall here ranks by importance x log(1+use_count) rather than cosine
//   similarity (embeddings on this table are nullable / enrichment-filled),
//   which is the documented Phase-7 ranking. Query relevance is applied as a
//   cheap keyword pre-filter when a query string is supplied.
//
// SINGLE SOURCE OF TRUTH: both agent-memory-store/index.ts (the standalone
// CRUD edge fn) and ai-gateway/index.ts import THIS module so the ranking +
// LRU-eviction logic lives in exactly one place (architect 4-place-sync
// doctrine — the Phase-7 store/recall logic previously lived only inside
// agent-memory-store and was unreachable from the gateway).
//
// Recall (the hot path) is pure DB mechanics, no network. WRITE (persistEpisodic,
// post-response) additionally EMBEDS procedural memories best-effort (Turn 5) so
// the skill library is semantically matchable by _shared/skill-library.ts; that
// is the only network call here and it never blocks recall.

import { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { generateEmbedding } from "./embedding-chain.ts";

export const MEMORY_TYPES = ["factual", "procedural", "episodic", "semantic"] as const;
export type MemoryType = typeof MEMORY_TYPES[number];

export const MAX_CONTENT_CHARS = 600;
export const MAX_RECALL_LIMIT  = 20;
export const MAX_STORE_BATCH   = 10;
export const PER_WORKER_CAP    = 200;
export const PER_HIVE_CAP      = 1000;
export const RECALL_CHARS      = 280;   // per-memory cap when formatting a block

// C2.1: a memory whose `superseded_by` is set (it was corrected/replaced) is
// down-ranked by this factor at recall so its replacement surfaces above it and
// an obsolete fact/procedure cannot present as current. GUARDED: a row with
// superseded_by NULL is multiplied by 1.0 — byte-identical to pre-C2.1 ranking.
export const SUPERSEDE_PENALTY = 0.4;

// C2.2: write-side semantic dedup. Before inserting an EMBEDDED procedural memory, cosine-search the
// worker/hive's existing procedural library; a near-duplicate at or above this similarity is MERGED
// (bump use_count, keep the higher importance) instead of accumulating a paraphrase row. High by design
// — only a true restatement of the SAME procedure merges, never a merely-related one. Best-effort
// (only for rows that actually got an embedding); a miss or RPC error just inserts normally.
export const DEDUP_SIMILARITY = 0.95;

export interface RecalledMemory {
  id:           string;
  memory_type:  MemoryType;
  content:      string;
  importance:   number;
  use_count:    number;
  last_used_at: string | null;
  superseded_by?: string | null;   // C2.1: set => obsolete => down-ranked at recall
}

export interface StoreInput {
  memory_type:      MemoryType;
  content:          string;
  importance?:      number;
  source_trace_id?: string | null;
}

/**
 * Compound recall score. importance x log(1+use_count) rewards memories that
 * have proven useful (recalled often) while the +importance*0.5 floor keeps a
 * brand-new high-importance memory (use_count 0 -> log term 0) competitive.
 * Mirrors the Phase-7 eviction weight so recall and eviction agree on "value".
 */
function memScore(m: { importance?: number; use_count?: number }): number {
  return (m.importance || 0) * Math.log(1 + (m.use_count || 0)) + (m.importance || 0) * 0.5;
}

/** Lowercase token set for the cheap keyword pre-filter. */
function tokens(s: string): string[] {
  return (s.toLowerCase().match(/[a-z0-9][a-z0-9\-]{2,}/g) || []);
}

/**
 * Recall the top-N most valuable durable memories for (hive, worker).
 *
 * Fetches a 3x pool ordered by importance, re-ranks in JS by the compound
 * score, and (best-effort, fire-and-forget) bumps use_count + last_used_at on
 * the returned rows so frequently-recalled memories rise over time.
 *
 * When `query` is supplied, memories sharing >=1 token with the query are
 * boosted ahead of equal-score memories that don't — a cheap relevance nudge
 * that needs no embedding call. Memories never get filtered OUT by the query
 * (a high-importance hive fact stays recallable even on an unrelated turn).
 *
 * Best-effort: any DB error returns []. The caller still has working memory.
 */
export async function recallEpisodic(
  db: SupabaseClient,
  hiveId: string | null,
  workerName: string | null,
  opts: { memoryTypes?: MemoryType[]; limit?: number; query?: string; bump?: boolean } = {},
): Promise<RecalledMemory[]> {
  if (!hiveId && !workerName) return [];

  const memoryTypes = (opts.memoryTypes && opts.memoryTypes.length
    ? opts.memoryTypes.filter((t): t is MemoryType => (MEMORY_TYPES as readonly string[]).includes(t))
    : (MEMORY_TYPES as unknown as MemoryType[]));
  const limit = Math.min(MAX_RECALL_LIMIT, Math.max(1, Number(opts.limit ?? 5)));
  const bump  = opts.bump !== false;

  // canonical-allow: agent infra table, server-side store, no user-facing canonical surface
  let q = db.from("agent_episodic_memory")
    .select("id, memory_type, content, importance, use_count, last_used_at, superseded_by")
    .in("memory_type", memoryTypes as unknown as string[])
    .order("importance", { ascending: false })
    .limit(Math.max(limit * 3, 50));
  if (hiveId)     q = q.eq("hive_id", hiveId);
  if (workerName) q = q.eq("worker_name", workerName);

  const { data, error } = await q;
  if (error) { console.warn("[episodic-memory] recall fetch failed:", error.message); return []; }

  const qTokens = opts.query ? new Set(tokens(opts.query)) : null;
  const pool = (data || []) as RecalledMemory[];
  const ranked = pool
    .map((m) => {
      const overlap = qTokens
        ? tokens(m.content).some((t) => qTokens.has(t)) ? 0.25 : 0
        : 0;
      // C2.1: down-rank a superseded (corrected/replaced) memory so its
      // replacement ranks above it. Guarded: superseded_by NULL -> ×1 (no-op,
      // pre-C2.1 ranking is byte-identical when nothing is superseded).
      const penalty = m.superseded_by ? SUPERSEDE_PENALTY : 1;
      return { m, score: (memScore(m) + overlap) * penalty };
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map((x) => x.m);

  if (bump && ranked.length) {
    const now = new Date().toISOString();
    Promise.all(ranked.map((m) =>
      db.from("agent_episodic_memory")
        .update({ use_count: (m.use_count || 0) + 1, last_used_at: now })
        .eq("id", m.id)
    )).catch((err) => console.warn("[episodic-memory] use_count bump failed:", String(err).slice(0, 80)));
  }

  return ranked;
}

/**
 * LRU eviction by compound score. Worker-cap first, then hive-cap. Deletes the
 * lowest-value rows once a scope crosses its cap. Returns count evicted.
 */
export async function evictIfOverCap(
  db: SupabaseClient,
  hiveId: string | null,
  workerName: string | null,
): Promise<number> {
  let evicted = 0;
  const scopes: Array<{ col: "worker_name" | "hive_id"; val: string; cap: number }> = [];
  if (workerName) scopes.push({ col: "worker_name", val: workerName, cap: PER_WORKER_CAP });
  if (hiveId)     scopes.push({ col: "hive_id",     val: hiveId,     cap: PER_HIVE_CAP });

  for (const s of scopes) {
    // canonical-allow: LRU eviction scan, agent infra. The full-scope scan is
    // intentional (must see all in-scope rows to evict the lowest-value ones);
    // the table is self-capped at PER_*_CAP by this very eviction.
    const { data } = await db.from("agent_episodic_memory")  // unbounded-query-allow: LRU eviction full scan, self-capped
      .select("id, importance, use_count")
      .eq(s.col, s.val);
    const rows = data || [];
    if (rows.length > s.cap) {
      const toEvict = rows
        .slice()
        .sort((a, b) => memScore(a) - memScore(b))
        .slice(0, rows.length - s.cap)
        .map((r) => r.id);
      if (toEvict.length) {
        await db.from("agent_episodic_memory").delete().in("id", toEvict);
        evicted += toEvict.length;
      }
    }
  }
  return evicted;
}

/**
 * Persist a batch of durable memories (service-role insert — caller must pass
 * an admin client; RLS blocks anon/auth INSERT by design). Clamps content
 * length + importance, drops invalid memory_types, caps the batch, then runs
 * LRU eviction. Best-effort: returns errors[] rather than throwing so a
 * persist failure never breaks the user-facing response.
 */
export async function persistEpisodic(
  db: SupabaseClient,
  hiveId: string | null,
  workerName: string | null,
  memories: StoreInput[],
): Promise<{ written: number; merged: number; evicted: number; errors: string[] }> {
  const errors: string[] = [];
  const rows = (memories || []).slice(0, MAX_STORE_BATCH).map((m) => ({
    hive_id:         hiveId,
    worker_name:     workerName,
    memory_type:     m.memory_type,
    content:         String(m.content || "").slice(0, MAX_CONTENT_CHARS),
    embedding:       null as number[] | null,
    importance:      Math.min(1, Math.max(0, Number(m.importance ?? 0.5))),
    use_count:       0,
    last_used_at:    null,
    source_trace_id: m.source_trace_id || null,
  })).filter((r) => r.content && (MEMORY_TYPES as readonly string[]).includes(r.memory_type));

  if (!rows.length) return { written: 0, evicted: 0, errors: ["no valid memories in payload"] };

  // Turn 5 (Procedural layer): embed PROCEDURAL memories so the skill library is
  // semantically matchable via match_procedural_memories. Procedural-only to
  // bound cost (other types recall by importance/keyword, no embedding needed);
  // best-effort, so an embedding-provider miss just leaves embedding=null (a
  // later store of the same lesson can fill it). Never throws.
  await Promise.all(rows.map(async (r) => {
    if (r.memory_type === "procedural" && r.content) {
      try { r.embedding = await generateEmbedding(r.content); }
      catch (_err) { /* leave null; enrichment / a later store can fill it */ }
    }
  }));

  // C2.2: write-side semantic dedup — MERGE a near-duplicate procedural memory (bump use_count, keep
  // the higher importance) instead of inserting a paraphrase row, so the skill library doesn't bloat
  // with restatements of the same fix. Only EMBEDDED procedural rows are checked (others carry no
  // vector to compare); best-effort, so any RPC error falls through to a normal insert.
  const toInsert: typeof rows = [];
  let merged = 0;
  for (const r of rows) {
    if (r.memory_type === "procedural" && Array.isArray(r.embedding)) {
      try {
        const { data: near } = await db.rpc("match_procedural_memories", {
          p_query_embedding: r.embedding,
          p_hive_id: hiveId,
          p_worker_name: workerName,
          p_match_count: 1,
          p_min_similarity: DEDUP_SIMILARITY,
        });
        const dup = (near as Array<{ id: string; importance: number; use_count: number }> | null)?.[0];
        if (dup?.id) {
          await db.from("agent_episodic_memory").update({
            use_count:    (dup.use_count || 0) + 1,
            importance:   Math.max(dup.importance || 0, r.importance),
            last_used_at: new Date().toISOString(),
          }).eq("id", dup.id);
          merged++;
          continue;   // near-dup merged — do NOT insert a paraphrase row
        }
      } catch (_err) { /* dedup is best-effort — fall through to a normal insert */ }
    }
    toInsert.push(r);
  }

  let written = 0;
  if (toInsert.length) {
    const { data, error } = await db.from("agent_episodic_memory").insert(toInsert).select("id");
    if (error) errors.push(error.message);
    written = (data || []).length;
  }

  const evicted = await evictIfOverCap(db, hiveId, workerName);
  return { written, merged, evicted, errors };
}

/**
 * C2.1: mark `oldId` as superseded by `newId` (a correction / replacement). The
 * obsolete row is then down-ranked at recall (SUPERSEDE_PENALTY) in BOTH
 * recallEpisodic and the match_procedural_memories RPC, so a corrected fact or
 * procedure cannot co-surface as current with its reversal (a maintenance-safety
 * guard). Service-role only — the aem_update RLS policy blocks anon/auth UPDATE.
 * Best-effort: returns false on any error rather than throwing.
 */
export async function supersedeEpisodic(
  db: SupabaseClient,
  oldId: string,
  newId: string,
): Promise<boolean> {
  if (!oldId || !newId || oldId === newId) return false;
  const { error } = await db.from("agent_episodic_memory")
    .update({ superseded_by: newId, superseded_at: new Date().toISOString() })
    .eq("id", oldId);
  if (error) { console.warn("[episodic-memory] supersede failed:", error.message); return false; }
  return true;
}

/**
 * Render recalled memories into a plain-text block to prepend to the agent's
 * prompt. Grouped by type so the LLM can tell a standing fact from a one-off
 * episode. Returns "" when there is nothing to add (caller concatenates).
 */
export function formatEpisodicContext(rows: RecalledMemory[]): string {
  if (!rows || !rows.length) return "";
  const order: MemoryType[] = ["semantic", "factual", "procedural", "episodic"];
  const label: Record<MemoryType, string> = {
    semantic:   "What I know about this operation",
    factual:    "Facts worth remembering",
    procedural: "How fixes have been done before",
    episodic:   "Past incidents",
  };
  const lines: string[] = ["Long-term memory (durable, from earlier sessions):"];
  for (const t of order) {
    const ofType = rows.filter((r) => r.memory_type === t);
    if (!ofType.length) continue;
    lines.push(`${label[t]}:`);
    for (const r of ofType) {
      lines.push(`- ${(r.content || "").replace(/\s+/g, " ").trim().slice(0, RECALL_CHARS)}`);
    }
  }
  return lines.join("\n");
}
