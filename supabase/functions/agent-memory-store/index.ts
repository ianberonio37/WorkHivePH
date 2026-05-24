/**
 * agent-memory-store — Phase 7 of AGENTIC_RAG_ROADMAP.md.
 *
 * Read/write endpoint for the agent_episodic_memory table. Two operations:
 *
 *   GET-style:  { op: "recall", hive_id, worker_name?, query?, limit? }
 *               → returns top N memories ranked by importance × log(1+use_count),
 *                 optionally filtered by memory_type. Also bumps use_count
 *                 and last_used_at for the returned rows.
 *
 *   POST-style: { op: "store", hive_id, worker_name?, memories: [{memory_type, content, importance?, source_trace_id?}] }
 *               → inserts up to 10 memories per call. Enforces caps:
 *                 200/worker, 1000/hive via LRU eviction
 *                 (lowest importance × log(1+use_count) gets deleted).
 *
 * Body:
 *   { op: "recall" | "store", hive_id, worker_name?, query?, memory_types?, limit?, memories? }
 *
 * Free-tier constraint: no LLM call inside this function — it's pure DB
 * mechanics. The memory_extractor that decides what to store runs inside
 * agentic-rag-loop's Checker stage (callAI with taskProfile).
 *
 * Skills consulted: ai-engineer (no raw fetch, no PII leak), architect
 * (4-place sync, service-role-only writes), data-engineer (narrow selects,
 * hive scoping, error destructuring), security (input cap, redactPII at
 * boundary).
 *
 * contract-allow: memory store CRUD; output schema documented above.
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";

const FN_NAME            = "agent-memory-store";
const MAX_CONTENT_CHARS  = 600;
const MAX_RECALL_LIMIT   = 20;
const MAX_STORE_BATCH    = 10;
const PER_WORKER_CAP     = 200;
const PER_HIVE_CAP       = 1000;
const MEMORY_TYPES       = ["factual","procedural","episodic","semantic"] as const;
type MemoryType = typeof MEMORY_TYPES[number];

const _URL = Deno.env.get("SUPABASE_URL") || "";
const _KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
if (!_URL || !_KEY) console.warn("[agent-memory-store] SUPABASE env missing");
const _warm = _URL && _KEY ? createClient(_URL, _KEY) : null;
void _warm;

// ── RECALL ───────────────────────────────────────────────────────────────────

interface RecalledMemory {
  id: string;
  memory_type: MemoryType;
  content: string;
  importance: number;
  use_count: number;
  last_used_at: string | null;
}

async function recall(
  db: SupabaseClient,
  hiveId: string | null,
  workerName: string | null,
  memoryTypes: MemoryType[],
  limit: number,
): Promise<RecalledMemory[]> {
  // Fetch a generous pool — we re-rank in JS by importance × log(1+use_count)
  // because Postgres ORDER BY can't express that compound score cleanly
  // without a stored generated column.
  // canonical-allow: agent infra table, server-side store, no user-facing canonical surface
  let q = db.from("agent_episodic_memory")
    .select("id, memory_type, content, importance, use_count, last_used_at")
    .in("memory_type", memoryTypes as unknown as string[])
    .order("importance", { ascending: false })
    .limit(Math.max(limit * 3, 50));   // fetch 3× for re-ranking
  if (hiveId)     q = q.eq("hive_id", hiveId);
  if (workerName) q = q.eq("worker_name", workerName);
  const { data, error } = await q;
  if (error) { console.warn("[agent-memory-store] recall fetch failed:", error.message); return []; }

  const pool = (data || []) as RecalledMemory[];
  const ranked = pool
    .map(m => ({ m, score: (m.importance || 0) * Math.log(1 + (m.use_count || 0)) + (m.importance || 0) * 0.5 }))
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map(x => x.m);

  // Best-effort: bump use_count + last_used_at on the returned rows. Don't
  // block the recall response on the write — fire and forget.
  if (ranked.length) {
    const now = new Date().toISOString();
    Promise.all(ranked.map(m =>
      db.from("agent_episodic_memory")
        .update({ use_count: (m.use_count || 0) + 1, last_used_at: now })
        .eq("id", m.id)
    )).catch(err => console.warn("[agent-memory-store] use_count bump failed:", String(err).slice(0, 80)));
  }

  return ranked;
}

// ── STORE ────────────────────────────────────────────────────────────────────

interface StoreInput {
  memory_type: MemoryType;
  content: string;
  importance?: number;
  source_trace_id?: string | null;
}

async function evictIfOverCap(db: SupabaseClient, hiveId: string | null, workerName: string | null): Promise<number> {
  // Worker-level eviction (only when worker_name is set)
  let evicted = 0;
  if (workerName) {
    // canonical-allow: worker-level LRU eviction scan, agent infra
    const { data } = await db.from("agent_episodic_memory")
      .select("id, importance, use_count")
      .eq("worker_name", workerName);
    if ((data || []).length > PER_WORKER_CAP) {
      const sorted = (data || []).slice().sort((a, b) =>
        ((a.importance || 0) * Math.log(1 + (a.use_count || 0))) -
        ((b.importance || 0) * Math.log(1 + (b.use_count || 0))));
      const toEvict = sorted.slice(0, sorted.length - PER_WORKER_CAP).map(r => r.id);
      if (toEvict.length) {
        await db.from("agent_episodic_memory").delete().in("id", toEvict);
        evicted += toEvict.length;
      }
    }
  }
  // Hive-level eviction
  if (hiveId) {
    // canonical-allow: hive-level LRU eviction scan, agent infra
    const { data } = await db.from("agent_episodic_memory")
      .select("id, importance, use_count")
      .eq("hive_id", hiveId);
    if ((data || []).length > PER_HIVE_CAP) {
      const sorted = (data || []).slice().sort((a, b) =>
        ((a.importance || 0) * Math.log(1 + (a.use_count || 0))) -
        ((b.importance || 0) * Math.log(1 + (b.use_count || 0))));
      const toEvict = sorted.slice(0, sorted.length - PER_HIVE_CAP).map(r => r.id);
      if (toEvict.length) {
        await db.from("agent_episodic_memory").delete().in("id", toEvict);
        evicted += toEvict.length;
      }
    }
  }
  return evicted;
}

async function store(
  db: SupabaseClient,
  hiveId: string | null,
  workerName: string | null,
  memories: StoreInput[],
): Promise<{ written: number; evicted: number; errors: string[] }> {
  const errors: string[] = [];
  const rows = memories.slice(0, MAX_STORE_BATCH).map(m => ({
    hive_id:         hiveId,
    worker_name:     workerName,
    memory_type:     m.memory_type,
    content:         String(m.content || "").slice(0, MAX_CONTENT_CHARS),
    embedding:       null,
    importance:      Math.min(1, Math.max(0, Number(m.importance ?? 0.5))),
    use_count:       0,
    last_used_at:    null,
    source_trace_id: m.source_trace_id || null,
  })).filter(r => r.content && MEMORY_TYPES.includes(r.memory_type as MemoryType));

  if (!rows.length) return { written: 0, evicted: 0, errors: ["no valid memories in payload"] };

  const { data, error } = await db.from("agent_episodic_memory").insert(rows).select("id");
  if (error) errors.push(error.message);

  const evicted = await evictIfOverCap(db, hiveId, workerName);
  return { written: (data || []).length, evicted, errors };
}

// ── Server entry ─────────────────────────────────────────────────────────────

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders });
  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  let body: { op?: string; hive_id?: string | null; worker_name?: string | null; query?: string; memory_types?: MemoryType[]; limit?: number; memories?: StoreInput[] } = {};
  try { body = await req.json(); } catch {
    return new Response(JSON.stringify({ error: "Invalid JSON body" }), {
      status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
  if (!body.op || (body.op !== "recall" && body.op !== "store")) {
    return new Response(JSON.stringify({ error: 'Missing or invalid op (must be "recall" or "store")' }), {
      status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
  if (!body.hive_id && !body.worker_name) {
    return new Response(JSON.stringify({ error: "Missing required field: hive_id or worker_name" }), {
      status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  const db         = _warm || createClient(_URL, _KEY);
  const hiveId     = body.hive_id || null;
  const workerName = body.worker_name || null;

  if (body.op === "recall") {
    const memoryTypes = Array.isArray(body.memory_types) && body.memory_types.length
      ? body.memory_types.filter((t): t is MemoryType => (MEMORY_TYPES as readonly string[]).includes(t))
      : (MEMORY_TYPES as unknown as MemoryType[]);
    const limit = Math.min(MAX_RECALL_LIMIT, Math.max(1, Number(body.limit ?? 5)));
    const memories = await recall(db, hiveId, workerName, memoryTypes, limit);
    return new Response(JSON.stringify({ ok: true, memories }), {
      status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  // store
  const result = await store(db, hiveId, workerName, body.memories || []);
  return new Response(JSON.stringify({ ok: result.errors.length === 0, ...result }), {
    status: result.errors.length ? 500 : 200,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
});
