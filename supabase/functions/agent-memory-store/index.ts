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
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";
// Pillar I (Gateway Spine): verify hive membership before service-role memory ops.
import { resolveIdentity, resolveTenancy } from "../_shared/tenant-context.ts";
// P1 roadmap 2026-05-26: adoption of envelope + /health.
import { beginRequest, ok } from "../_shared/envelope.ts";
import { handleHealth } from "../_shared/health.ts";
import { log } from "../_shared/logger.ts";
// 2026-05-30 memory-stack flywheel Turn 1: recall/persist/eviction logic moved
// to _shared/episodic-memory.ts so ai-gateway can share it (architect
// 4-place-sync). This fn is now a thin HTTP wrapper over those primitives.
import {
  recallEpisodic,
  persistEpisodic,
  MEMORY_TYPES,
  MAX_RECALL_LIMIT,
  type MemoryType,
  type StoreInput,
} from "../_shared/episodic-memory.ts";

const FN_NAME = "agent-memory-store";

const _URL = Deno.env.get("SUPABASE_URL") || "";
const _KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
if (!_URL || !_KEY) console.warn("[agent-memory-store] SUPABASE env missing");
const _warm = _URL && _KEY ? createClient(_URL, _KEY) : null;
void _warm;

// RECALL / STORE / EVICTION primitives now live in _shared/episodic-memory.ts
// (recallEpisodic, persistEpisodic, evictIfOverCap). This fn is the HTTP face.

// ── Server entry ─────────────────────────────────────────────────────────────

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders });

  // /health probe.
  const healthResp = await handleHealth(req, "agent-memory-store", async () => ({
    deps: [
      { name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) },
    ],
  }));
  if (healthResp) return healthResp;

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

  // Pillar I: agent_memory is scoped by the client hive_id on a service-role
  // client — verify membership so a direct caller can't read/write another
  // hive's memory. Internal callers (ai-gateway, agentic-rag-loop) use
  // service-role and skip. Verify only when a hive is claimed.
  if (hiveId) {
    const _id = await resolveIdentity(db, req);
    if (!_id.isServiceRole) {
      const t = await resolveTenancy(db, _id.authUid, hiveId);
      if (!t.ok) {
        return new Response(
          JSON.stringify({ error: t.message, code: t.code }),
          { status: t.status, headers: { ...corsHeaders, "Content-Type": "application/json" } },
        );
      }
    }
  }

  if (body.op === "recall") {
    const memoryTypes = Array.isArray(body.memory_types) && body.memory_types.length
      ? body.memory_types.filter((t): t is MemoryType => (MEMORY_TYPES as readonly string[]).includes(t))
      : (MEMORY_TYPES as unknown as MemoryType[]);
    const limit = Math.min(MAX_RECALL_LIMIT, Math.max(1, Number(body.limit ?? 5)));
    const memories = await recallEpisodic(db, hiveId, workerName, { memoryTypes, limit, query: body.query });
    return new Response(JSON.stringify({ ok: true, memories }), {
      status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  // store
  const result = await persistEpisodic(db, hiveId, workerName, body.memories || []);
  return new Response(JSON.stringify({ ok: result.errors.length === 0, ...result }), {
    status: result.errors.length ? 500 : 200,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
});
