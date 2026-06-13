// _shared/memory.ts
// Agent-memory layer for the AI gateway. Implements load + persist for
// the `agent_memory` table introduced in migration 20260511000001.
//
// Two recall surfaces per (hive_id, worker_name, agent_id):
//   * last N turns       -- most-recent verbatim user/agent exchanges
//   * latest summary     -- LLM-compressed paragraph covering older history
//
// The gateway calls loadMemory(...) before dispatching to the agent and
// saveTurn(...) after the agent responds. summariseIfNeeded(...) collapses
// the oldest turns when the live tail crosses RECENT_TURNS.

import { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";

export const RECENT_TURNS = 10;        // raw turns kept verbatim
export const SUMMARISE_AT = 12;        // collapse oldest 5 once buffer hits this
export const SUMMARISE_BATCH = 5;

export interface MemoryHandle {
  hive_id:     string | null;
  worker_name: string;
  auth_uid:    string | null;
  agent_id:    string;
}

export interface MemoryTurn {
  role:    "user" | "agent";
  text:    string;
  created_at?: string;
}

export interface LoadedMemory {
  recent_turns: MemoryTurn[];
  summary:      string | null;
}

/**
 * Load the recall surface for a memory handle. Both the last N turns and
 * the latest summary in a single round-trip via Promise.all.
 */
export async function loadMemory(
  db: SupabaseClient,
  h: MemoryHandle,
): Promise<LoadedMemory> {
  if (!h.worker_name || !h.agent_id) {
    return { recent_turns: [], summary: null };
  }

  let recentQuery = db.from("agent_memory")
    .select("turn_text, meta, created_at")
    .eq("worker_name", h.worker_name)
    .eq("agent_id",    h.agent_id)
    .eq("kind",        "turn")
    .order("created_at", { ascending: false })
    .limit(RECENT_TURNS);

  let summaryQuery = db.from("agent_memory")
    .select("summary, created_at")
    .eq("worker_name", h.worker_name)
    .eq("agent_id",    h.agent_id)
    .eq("kind",        "summary")
    .order("created_at", { ascending: false })
    .limit(1);

  if (h.hive_id) {
    recentQuery  = recentQuery.eq("hive_id",  h.hive_id);
    summaryQuery = summaryQuery.eq("hive_id", h.hive_id);
  } else {
    recentQuery  = recentQuery.is("hive_id",  null);
    summaryQuery = summaryQuery.is("hive_id", null);
  }

  const [recentRes, summaryRes] = await Promise.all([recentQuery, summaryQuery]);

  const recent_turns: MemoryTurn[] = [];
  for (const row of (recentRes.data || []).reverse()) {   // chronological
    const text = row.turn_text || "";
    // role-allow: LLM chat-message role ("user" | "agent"), not a platform auth role
    const role = (row.meta as Record<string, unknown> | null)?.role === "agent"
      ? "agent" as const : "user" as const;
    recent_turns.push({ role, text, created_at: row.created_at });
  }

  const summary = summaryRes.data?.[0]?.summary ?? null;

  return { recent_turns, summary };
}

/**
 * Persist a new (user, agent) exchange as two turn rows. Uses service-role
 * insert via the supplied client (so callers must pass an admin client).
 */
export async function saveTurn(
  db: SupabaseClient,
  h: MemoryHandle,
  user_text: string,
  agent_text: string,
  meta_extra: Record<string, unknown> = {},
): Promise<void> {
  if (!h.worker_name || !h.agent_id) return;
  const baseMeta = {
    ...meta_extra,
    saved_via: "ai-gateway",
  };
  const rows = [
    {
      hive_id:     h.hive_id,
      worker_name: h.worker_name,
      auth_uid:    h.auth_uid,
      agent_id:    h.agent_id,
      kind:        "turn",
      turn_text:   user_text,
      meta:        { ...baseMeta, role: "user" },
    },
    {
      hive_id:     h.hive_id,
      worker_name: h.worker_name,
      auth_uid:    h.auth_uid,
      agent_id:    h.agent_id,
      kind:        "turn",
      turn_text:   agent_text,
      meta:        { ...baseMeta, role: "agent" },
    },
  ];
  const { error } = await db.from("agent_memory").insert(rows);
  if (error) {
    console.warn("memory.saveTurn failed:", error.message);
  }
}

/**
 * Summarise the oldest SUMMARISE_BATCH turns into a single summary row
 * once the live buffer crosses SUMMARISE_AT. Caller passes the LLM-summary
 * already (the gateway uses callAI to produce it before calling here).
 */
export async function persistSummary(
  db: SupabaseClient,
  h: MemoryHandle,
  summary_text: string,
  collapsed_turn_ids: string[],
): Promise<void> {
  if (!h.worker_name || !h.agent_id) return;
  const { error: insErr } = await db.from("agent_memory").insert({
    hive_id:     h.hive_id,
    worker_name: h.worker_name,
    auth_uid:    h.auth_uid,
    agent_id:    h.agent_id,
    kind:        "summary",
    summary:     summary_text,
    meta:        { collapsed: collapsed_turn_ids.length, source: "ai-gateway" },
  });
  if (insErr) {
    console.warn("memory.persistSummary failed:", insErr.message);
    return;
  }
  if (collapsed_turn_ids.length) {
    const { error: delErr } = await db.from("agent_memory")
      .delete()
      .in("id", collapsed_turn_ids);
    if (delErr) {
      console.warn("memory.persistSummary delete failed:", delErr.message);
    }
  }
}

/**
 * Collapse the oldest SUMMARISE_BATCH turns into one summary row once the live
 * turn buffer crosses SUMMARISE_AT. Keeps memory.ts LLM-FREE: the caller passes a
 * `summarise(transcript) => Promise<string>` callback (the gateway wraps callAI),
 * so the persistence layer never imports ai-chain. Best-effort — returns null
 * (no-op) when the buffer is short, the summary is empty, or anything throws.
 * Wires the previously-dead persistSummary primitive (W2 finding 2026-06-12).
 */
export async function summariseIfNeeded(
  db: SupabaseClient,
  h: MemoryHandle,
  summarise: (transcript: string) => Promise<string>,
): Promise<{ collapsed: number } | null> {
  if (!h.worker_name || !h.agent_id) return null;
  try {
    let countQ = db.from("agent_memory")
      .select("id", { count: "exact", head: true })
      .eq("worker_name", h.worker_name)
      .eq("agent_id",    h.agent_id)
      .eq("kind",        "turn");
    countQ = h.hive_id ? countQ.eq("hive_id", h.hive_id) : countQ.is("hive_id", null);
    const { count } = await countQ;
    if (!count || count <= SUMMARISE_AT) return null;

    let oldestQ = db.from("agent_memory")
      .select("id, turn_text, meta")
      .eq("worker_name", h.worker_name)
      .eq("agent_id",    h.agent_id)
      .eq("kind",        "turn")
      .order("created_at", { ascending: true })
      .limit(SUMMARISE_BATCH);
    oldestQ = h.hive_id ? oldestQ.eq("hive_id", h.hive_id) : oldestQ.is("hive_id", null);
    const { data: oldest } = await oldestQ;
    if (!oldest || !oldest.length) return null;

    const transcript = oldest.map((r) => {
      const role = (r.meta as Record<string, unknown> | null)?.role === "agent" ? "Assistant" : "User";
      return `${role}: ${r.turn_text || ""}`;
    }).join("\n");

    const summary_text = (await summarise(transcript) || "").trim();
    if (!summary_text) return null;

    await persistSummary(db, h, summary_text, oldest.map((r) => r.id as string));
    return { collapsed: oldest.length };
  } catch (err) {
    console.warn("memory.summariseIfNeeded failed:", err instanceof Error ? err.message : String(err));
    return null;
  }
}

/**
 * Build a compact context block to prepend to the user's prompt.
 * Order: long-term summary first, then recent turns oldest-to-newest.
 */
export function formatMemoryContext(loaded: LoadedMemory): string {
  if (!loaded.recent_turns.length && !loaded.summary) return "";
  const parts: string[] = [];
  if (loaded.summary) {
    parts.push(`Conversation so far (summary):\n${loaded.summary}`);
  }
  if (loaded.recent_turns.length) {
    parts.push("Recent turns:");
    for (const t of loaded.recent_turns) {
      const tag = t.role === "user" ? "Worker" : "Agent"; // role-allow: LLM chat-message role
      parts.push(`${tag}: ${t.text}`);
    }
  }
  return parts.join("\n");
}
