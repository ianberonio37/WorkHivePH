// _shared/skill-library.ts
//
// Procedural layer (layer 04 of the AI Agent Memory Stack): the runtime SKILL
// LIBRARY + MATCHER. The "procedural" rows in agent_episodic_memory are the
// distilled, reusable fix procedures ("P-204 bearing fix: replace SKF 6205-2RS")
// that the agentic-rag-loop Checker writes and ai-gateway recalls. Until Turn 5
// they were only recalled by importance x log(use_count) + keyword overlap
// (recallEpisodic) and stored with embedding=null, so a procedure phrased
// differently from the current fault was never surfaced.
//
// This module is the READ/matcher side: given the current problem, embed it and
// fetch the top semantically-matched procedures via the match_procedural_memories
// RPC (20260531000001). The WRITE side is _shared/episodic-memory.ts persistEpisodic,
// which (as of Turn 5) embeds procedural memories at store time so they are
// matchable here.
//
// Best-effort throughout: an embedding-provider miss or RPC error returns [] /
// "" so the gateway just proceeds without a procedures block (graceful degrade,
// same contract as episodic recall + verified-state).

import { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { generateEmbedding } from "./embedding-chain.ts";

export const PROCEDURE_MATCH_LIMIT   = 4;
export const PROCEDURE_MIN_SIMILARITY = 0.6;   // cosine; below this is noise
export const PROCEDURE_CHARS         = 240;    // per-procedure cap when formatting

export interface MatchedProcedure {
  id:         string;
  content:    string;
  importance: number;
  use_count:  number;
  similarity: number;
}

/**
 * Semantically match the current problem against the hive's procedural skill
 * library. Hive-scoped by default (a teammate's proven fix helps anyone); pass
 * workerName to narrow to one worker's procedures.
 *
 * Returns [] on any miss (no query, no scope, embedding unavailable, RPC error)
 * — the caller treats an empty list as "no proven procedure to suggest".
 */
export async function matchProcedures(
  db: SupabaseClient,
  hiveId: string | null,
  workerName: string | null,
  query: string,
  opts: { limit?: number; minSimilarity?: number } = {},
): Promise<MatchedProcedure[]> {
  if (!query || !query.trim()) return [];
  if (!hiveId && !workerName) return [];

  let embedding: number[];
  try {
    embedding = await generateEmbedding(query.slice(0, 2000));
  } catch (err) {
    console.warn("[skill-library] embed failed (non-fatal):", err instanceof Error ? err.message : String(err));
    return [];
  }

  const limit = Math.min(20, Math.max(1, Number(opts.limit ?? PROCEDURE_MATCH_LIMIT)));
  const minSim = Math.min(1, Math.max(0, Number(opts.minSimilarity ?? PROCEDURE_MIN_SIMILARITY)));

  const { data, error } = await db.rpc("match_procedural_memories", {
    p_query_embedding: embedding,
    p_hive_id:         hiveId,
    p_worker_name:     workerName,
    p_match_count:     limit,
    p_min_similarity:  minSim,
  });
  if (error) {
    console.warn("[skill-library] match_procedural_memories failed (non-fatal):", error.message);
    return [];
  }
  return (data || []) as MatchedProcedure[];
}

/**
 * Render matched procedures into a prompt block. Pure (no IO) — Node-probeable.
 * Returns "" when there is nothing to add so the caller can concatenate safely.
 * Ordered by similarity (the RPC already does), each tagged with a match %.
 */
export function formatProcedures(rows: MatchedProcedure[]): string {
  if (!rows || !rows.length) return "";
  const lines = ["Proven procedures for this kind of task (from the hive's solved cases, apply with judgment):"];
  for (const r of rows) {
    const pct = Math.round(Math.max(0, Math.min(1, Number(r.similarity) || 0)) * 100);
    const text = String(r.content || "").replace(/\s+/g, " ").trim().slice(0, PROCEDURE_CHARS);
    if (text) lines.push(`- [${pct}% match] ${text}`);
  }
  return lines.length > 1 ? lines.join("\n") : "";
}
