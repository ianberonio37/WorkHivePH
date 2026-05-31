// _shared/followups.ts
//
// Prospective layer (layer 06 of the AI Agent Memory Stack): the per-(hive,
// worker) DEFERRED FOLLOW-UP QUEUE. This is the agent's prospective memory -
// "remember to check back on X later." A specialist emits followups[] in its
// envelope ("recheck pump P-204 vibration in 7 days"); the gateway ENQUEUES
// them, and on a later turn (once due) RECALLS and surfaces them back into the
// agent's context, marking them surfaced so they don't repeat forever.
//
// No dedicated substrate existed before Turn 6 (prospective was not even a
// memory_type). The store is agent_followups (20260531000002). Writes are
// service-role only (the gateway uses an admin client).
//
// Pure helpers (clampDueDays, normalizeFollowup, formatFollowups) are split out
// so they Node-probe without a DB; enqueue/recall do the IO. Best-effort
// throughout: a DB miss returns {written:0,...} / [] / "" and never throws into
// the user-facing path.

import { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";

export const MAX_ENQUEUE_BATCH        = 5;
export const MAX_PENDING_PER_WORKER   = 50;   // cap the queue so it can't grow unbounded
export const FOLLOWUP_RECALL_LIMIT    = 5;
export const MAX_TOPIC_CHARS          = 160;
export const MAX_DETAIL_CHARS         = 600;
export const MIN_DUE_DAYS             = 1;
export const MAX_DUE_DAYS             = 180;   // no follow-up further out than ~6 months
export const DEFAULT_DUE_DAYS         = 7;
export const FOLLOWUP_CHARS           = 240;   // per-item cap when formatting

export interface RawFollowup {
  topic?:       unknown;
  detail?:      unknown;
  due_in_days?: unknown;
  importance?:  unknown;
}

export interface NormalizedFollowup {
  topic:      string;
  detail:     string | null;
  due_at:     string;   // ISO timestamp
  importance: number;
}

export interface DueFollowup {
  id:         string;
  topic:      string;
  detail:     string | null;
  due_at:     string;
  importance: number;
}

/** Clamp a "days from now" value to a sane integer window; default on garbage. */
export function clampDueDays(v: unknown): number {
  const n = Math.round(Number(v));
  if (!Number.isFinite(n)) return DEFAULT_DUE_DAYS;
  return Math.min(MAX_DUE_DAYS, Math.max(MIN_DUE_DAYS, n));
}

/**
 * Validate + normalize one raw follow-up emitted by a specialist. Returns null
 * (drop it) when there is no topic. `now` is injected for testability; due_at =
 * now + clamped(due_in_days). Pure — no IO.
 */
export function normalizeFollowup(raw: RawFollowup, now: number = Date.now()): NormalizedFollowup | null {
  const topic = String(raw?.topic ?? "").replace(/\s+/g, " ").trim().slice(0, MAX_TOPIC_CHARS);
  if (!topic) return null;
  const detailRaw = String(raw?.detail ?? "").replace(/\s+/g, " ").trim().slice(0, MAX_DETAIL_CHARS);
  const days = clampDueDays(raw?.due_in_days);
  const importance = (() => {
    const x = Number(raw?.importance);
    return Number.isFinite(x) ? Math.min(1, Math.max(0, x)) : 0.5;
  })();
  return {
    topic,
    detail:     detailRaw || null,
    due_at:     new Date(now + days * 86400000).toISOString(),
    importance,
  };
}

/**
 * Enqueue a batch of deferred follow-ups (service-role insert). Validates +
 * caps the batch, refuses to grow a worker's pending queue past
 * MAX_PENDING_PER_WORKER, and never throws. Returns counts + errors[].
 */
export async function enqueueFollowups(
  db: SupabaseClient,
  hiveId: string | null,
  workerName: string | null,
  items: RawFollowup[],
  sourceTraceId: string | null = null,
): Promise<{ written: number; skipped: number; errors: string[] }> {
  const errors: string[] = [];
  if (!hiveId && !workerName) return { written: 0, skipped: 0, errors: ["no scope (hive_id/worker_name)"] };

  const now = Date.now();
  const normalized = (items || [])
    .slice(0, MAX_ENQUEUE_BATCH)
    .map((it) => normalizeFollowup(it, now))
    .filter((n): n is NormalizedFollowup => n !== null);
  if (!normalized.length) return { written: 0, skipped: 0, errors: ["no valid follow-ups in payload"] };

  // Pending-cap guard: don't let the queue grow without bound for one worker.
  try {
    // canonical-allow: agent-infra prospective queue, server-side only, no user-facing v_*_truth surface
    let q = db.from("agent_followups").select("id", { count: "exact", head: true }).eq("status", "pending");
    if (hiveId)     q = q.eq("hive_id", hiveId);
    if (workerName) q = q.eq("worker_name", workerName);
    const { count } = await q;
    const pending = count ?? 0;
    const room = Math.max(0, MAX_PENDING_PER_WORKER - pending);
    if (room <= 0) return { written: 0, skipped: normalized.length, errors: ["pending follow-up cap reached"] };
    if (normalized.length > room) normalized.length = room;
  } catch (err) {
    console.warn("[followups] pending-cap check failed (continuing):", err instanceof Error ? err.message : String(err));
  }

  const rows = normalized.map((n) => ({
    hive_id:         hiveId,
    worker_name:     workerName,
    topic:           n.topic,
    detail:          n.detail,
    due_at:          n.due_at,
    importance:      n.importance,
    status:          "pending",
    source_trace_id: sourceTraceId,
    created_by:      "ai-gateway",
  }));

  const { data, error } = await db.from("agent_followups").insert(rows).select("id");
  if (error) errors.push(error.message);
  return { written: (data || []).length, skipped: rows.length - (data || []).length, errors };
}

/**
 * Recall the worker's follow-ups that are now DUE (pending + due_at <= now),
 * soonest first, capped. Best-effort marks the returned rows 'surfaced' (fire-
 * and-forget) so they are raised once, not every turn. Returns [] on any miss.
 */
export async function recallDueFollowups(
  db: SupabaseClient,
  hiveId: string | null,
  workerName: string | null,
  opts: { limit?: number } = {},
): Promise<DueFollowup[]> {
  if (!hiveId && !workerName) return [];
  const limit = Math.min(20, Math.max(1, Number(opts.limit ?? FOLLOWUP_RECALL_LIMIT)));

  // canonical-allow: agent-infra prospective queue, server-side only, no user-facing v_*_truth surface
  let q = db.from("agent_followups")
    .select("id, topic, detail, due_at, importance")
    .eq("status", "pending")
    .lte("due_at", new Date().toISOString())
    .order("due_at", { ascending: true })
    .limit(limit);
  if (hiveId)     q = q.eq("hive_id", hiveId);
  if (workerName) q = q.eq("worker_name", workerName);

  const { data, error } = await q;
  if (error) { console.warn("[followups] recall failed (non-fatal):", error.message); return []; }
  const rows = (data || []) as DueFollowup[];

  if (rows.length) {
    const ids = rows.map((r) => r.id);
    const nowIso = new Date().toISOString();
    db.from("agent_followups").update({ status: "surfaced", surfaced_at: nowIso }).in("id", ids)
      .then(({ error: upErr }) => { if (upErr) console.warn("[followups] mark-surfaced failed:", upErr.message); });
  }
  return rows;
}

/**
 * Render due follow-ups into a prompt block. Pure (no IO) - Node-probeable.
 * Returns "" when empty so the caller can concatenate safely.
 */
export function formatFollowups(rows: DueFollowup[]): string {
  if (!rows || !rows.length) return "";
  const lines = ["Deferred follow-ups now due (you set these earlier - raise them with the worker if still relevant):"];
  for (const r of rows) {
    const topic  = String(r.topic || "").replace(/\s+/g, " ").trim().slice(0, FOLLOWUP_CHARS);
    if (!topic) continue;
    const detail = String(r.detail || "").replace(/\s+/g, " ").trim().slice(0, FOLLOWUP_CHARS);
    lines.push(detail ? `- ${topic} (${detail})` : `- ${topic}`);
  }
  return lines.length > 1 ? lines.join("\n") : "";
}
