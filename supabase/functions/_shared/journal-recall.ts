// _shared/journal-recall.ts
//
// Semantic recall layer for the voice-journal route in ai-gateway.
//
// Two surfaces:
//   * loadJournalRecall(): embed the worker's current spoken turn, then
//     query voice_journal_entries (cosine similarity, scoped by auth_uid)
//     for the top-K most relevant past entries. Returns a pre-formatted
//     text block ready to append to the gateway memory context.
//   * persistJournalEntry(): after the agent has responded, embed the
//     transcript again (cheap, idempotent) and write a durable row to
//     voice_journal_entries via the service-role client. Returns the
//     new row's id so the gateway can include it in the response envelope.
//
// Why per-turn vs per-message embedding:
//   We embed the user's transcript only (not the reply). The user
//   searches "what did I say about X" by paraphrase; the reply is
//   typically a reflection, not the substance. One embed call per turn.
//
// Privacy boundary:
//   This module is journal-only. RLS on voice_journal_entries locks
//   reads to auth.uid() = auth_uid. The service-role client used by
//   the gateway is the only writer; agent code never sees the table.

import { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { generateEmbedding } from "./embedding-chain.ts";

export const JOURNAL_RECALL_K = 5;            // top-K to retrieve per turn
export const JOURNAL_SIM_FLOOR = 0.30;        // drop matches below this cosine sim
export const JOURNAL_RECALL_CHARS = 280;      // per-entry character cap when formatting

export interface JournalRecallRow {
  id:          string;
  transcript:  string;
  reply:       string | null;
  lang:        string | null;
  created_at:  string;
  similarity:  number;
}

export interface JournalRecallResult {
  rows:           JournalRecallRow[];
  query_embedding: number[];   // returned so the caller can reuse on persist (one embed call per turn)
  block:          string;      // pre-formatted text ready to append to memory
}

/**
 * Embed the worker's current transcript and pull the top-K most similar
 * past journal entries for the same auth_uid. Returns rows + the query
 * embedding (so the caller can reuse it on persistJournalEntry without
 * paying a second embedding call) + a pre-formatted block.
 *
 * Best-effort: any failure returns empty rows + empty block. The agent
 * still gets the conversational memory from agent_memory, just without
 * semantic recall for this turn.
 */
export async function loadJournalRecall(
  db: SupabaseClient,
  authUid: string,
  transcript: string,
): Promise<JournalRecallResult> {
  const empty: JournalRecallResult = { rows: [], query_embedding: [], block: "" };
  if (!authUid || !transcript.trim()) return empty;

  let queryEmbedding: number[];
  try {
    queryEmbedding = await generateEmbedding(transcript);
  } catch (err) {
    console.warn("[journal-recall] embed failed:", err instanceof Error ? err.message : err);
    return empty;
  }

  const { data, error } = await db.rpc("search_voice_journal_entries", {
    query_embedding: queryEmbedding,
    match_auth_uid:  authUid,
    match_count:     JOURNAL_RECALL_K,
  });

  if (error) {
    console.warn("[journal-recall] rpc failed:", error.message);
    return { rows: [], query_embedding: queryEmbedding, block: "" };
  }

  const rows: JournalRecallRow[] = (data || []).filter(
    (r: JournalRecallRow) => typeof r.similarity === "number" && r.similarity >= JOURNAL_SIM_FLOOR,
  );

  return { rows, query_embedding: queryEmbedding, block: formatJournalRecall(rows) };
}

/**
 * Render the recall rows into a plain-text block the LLM can read.
 * Newest first. Truncate per-entry to keep the block budget tight.
 */
export function formatJournalRecall(rows: JournalRecallRow[]): string {
  if (!rows || !rows.length) return "";
  const lines: string[] = ["Past journal entries that look related to today's voice note (most similar first):"];
  rows.forEach((r, i) => {
    const when = new Date(r.created_at).toISOString().slice(0, 10);
    const langTag = r.lang ? ` [${r.lang}]` : "";
    const sim = (r.similarity * 100).toFixed(0);
    const t = (r.transcript || "").replace(/\s+/g, " ").trim().slice(0, JOURNAL_RECALL_CHARS);
    lines.push(`#${i + 1} (${when}${langTag}, ${sim}% similar): "${t}"`);
  });
  return lines.join("\n");
}

/**
 * Persist a completed journal exchange. Reuses the embedding from
 * loadJournalRecall when provided to avoid a second embed call. Falls
 * back to embedding here if the caller didn't run recall first.
 *
 * Service-role insert: caller must pass an admin client. Returns the
 * new row id or null on failure (failures are non-fatal -- the user-
 * facing reply has already been delivered).
 */
export async function persistJournalEntry(
  db: SupabaseClient,
  args: {
    auth_uid:    string;
    worker_name: string;
    hive_id:     string | null;
    transcript:  string;
    reply:       string;
    lang:        string | null;
    embedding?:  number[];
    meta?:       Record<string, unknown>;
  },
): Promise<string | null> {
  if (!args.auth_uid || !args.transcript.trim()) return null;

  let embedding = args.embedding;
  if (!embedding || embedding.length !== 384) {
    try {
      embedding = await generateEmbedding(args.transcript);
    } catch (err) {
      console.warn("[journal-recall] persist embed failed:", err instanceof Error ? err.message : err);
      embedding = undefined;
    }
  }

  const row = {
    auth_uid:    args.auth_uid,
    worker_name: args.worker_name,
    hive_id:     args.hive_id,
    transcript:  args.transcript,
    reply:       args.reply,
    lang:        args.lang,
    embedding:   embedding ?? null,
    meta:        args.meta ?? {},
  };

  const { data, error } = await db
    .from("voice_journal_entries")
    .insert(row)
    .select("id")
    .maybeSingle();

  if (error) {
    console.warn("[journal-recall] insert failed:", error.message);
    return null;
  }
  return data?.id ?? null;
}
