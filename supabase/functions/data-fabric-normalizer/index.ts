/**
 * data-fabric-normalizer — Phase 5 of AGENTIC_RAG_ROADMAP.md (SCAFFOLDING).
 *
 * Accepts events from any source (SAP PM, Maximo, OPC-UA, MQTT, CMMS, voice,
 * photo OCR, sensor, email ingest, manual log) and normalizes them into the
 * canonical unified_events shape. Idempotent via sha256 hash of
 * source+source_id+occurred_at.
 *
 * Adapters per source map foreign field names to the canonical schema.
 * This scaffolding ships 3 adapters (sap_pm, opc_ua, generic). Adding a
 * new source = add a function + extend SOURCES + add migration CHECK.
 *
 * Body:
 *   { source, source_id, hive_id, asset_tag?, occurred_at, payload, event_type? }
 *   - source must be in the migration CHECK list
 *   - source_id required (foreign system PK)
 *   - hash computed inside the fn from source+source_id+occurred_at
 *
 * Response: { ok, written, deduped, errors }
 *
 * Free-tier constraint: no LLM call inside this function (pure normalization).
 * Embedding enrichment is a separate pass that runs via the existing
 * voice-embeddings edge fn — not invoked here.
 */

import { serveObserved, trackHandled } from "../_shared/observability.ts";
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";
import { log } from "../_shared/logger.ts";
// Pillar I: machine-ingest gate — only trusted (service-role) callers may write.
import { requireServiceRole } from "../_shared/tenant-context.ts";
// P1 roadmap 2026-05-26: adoption of envelope + /health.
import { beginRequest, ok } from "../_shared/envelope.ts";
import { handleHealth } from "../_shared/health.ts";

const FN_NAME = "data-fabric-normalizer";
const SOURCES = ["sap_pm","maximo","opc_ua","mqtt","cmms_webhook","voice","photo_ocr","manual_log","sensor","email_ingest"] as const;
type Source = typeof SOURCES[number];

const EVENT_TYPES: Record<Source, string> = {
  sap_pm:       "work_order",
  maximo:       "work_order",
  opc_ua:       "sensor_reading",
  mqtt:         "sensor_reading",
  cmms_webhook: "work_order",
  voice:        "note",
  photo_ocr:    "image",
  manual_log:   "note",
  sensor:       "sensor_reading",
  email_ingest: "note",
};

const _URL = Deno.env.get("SUPABASE_URL") || "";
const _KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
if (!_URL || !_KEY) log.warn(null, "[data-fabric-normalizer] SUPABASE env missing");
const _warm = _URL && _KEY ? createClient(_URL, _KEY) : null;
void _warm;

// ── Hashing (sha256 via Web Crypto) ──────────────────────────────────────────

async function sha256(s: string): Promise<string> {
  const enc = new TextEncoder().encode(s);
  const buf = await crypto.subtle.digest("SHA-256", enc);
  return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, "0")).join("");
}

// ── Adapter: SAP PM ──────────────────────────────────────────────────────────
// Maps SAP PM01-PM04 order types into the canonical event_type.

function adaptSapPm(payload: Record<string, unknown>): { event_type: string; payload_text: string; asset_tag: string | null } {
  const orderType = String(payload["AUART"] || payload["order_type"] || "PM01");
  const equipment = String(payload["EQUNR"] || payload["equipment"] || "") || null;
  const desc      = String(payload["KTEXT"] || payload["description"] || "");
  const event_type = ["PM01", "PM02", "PM03", "PM04"].includes(orderType) ? "work_order" : "work_order";
  const payload_text = `[SAP ${orderType}] ${desc}${equipment ? ` (${equipment})` : ""}`.slice(0, 800);
  return { event_type, payload_text, asset_tag: equipment };
}

// ── Adapter: OPC-UA tag ──────────────────────────────────────────────────────
// Maps tag names like Plant1.P203.Vibration_RMS into asset_tag=P-203 + metric.

function adaptOpcUa(payload: Record<string, unknown>): { event_type: string; payload_text: string; asset_tag: string | null } {
  const tag   = String(payload["tag"] || payload["node_id"] || "");
  const value = payload["value"];
  const parts = tag.split(".");
  // Best-effort: take the middle part as asset, the last as metric.
  const assetRaw = parts.length >= 2 ? parts[parts.length - 2] : "";
  const metric   = parts.length >= 1 ? parts[parts.length - 1] : "";
  const asset_tag = assetRaw ? assetRaw.replace(/^([A-Z])(\d)/, "$1-$2") : null;
  const payload_text = `[OPC-UA ${tag}] ${metric} = ${value}`.slice(0, 400);
  return { event_type: "sensor_reading", payload_text, asset_tag };
}

// ── Adapter: generic fallback ────────────────────────────────────────────────

function adaptGeneric(source: Source, payload: Record<string, unknown>): { event_type: string; payload_text: string; asset_tag: string | null } {
  const event_type = EVENT_TYPES[source] || "note";
  // Best-effort flatten for embedding: shallow key=value join, cap 800 chars.
  const flat = Object.entries(payload).slice(0, 12)
    .map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
    .join(" | ").slice(0, 800);
  const asset_tag = (payload["asset_tag"] || payload["machine"] || payload["equipment"]) as string | undefined;
  return { event_type, payload_text: flat, asset_tag: asset_tag || null };
}

// ── Server entry ─────────────────────────────────────────────────────────────

serveObserved("data-fabric-normalizer", async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders });

  // /health probe.
  const healthResp = await handleHealth(req, "data-fabric-normalizer", async () => ({
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

  let body: { source?: Source; source_id?: string; hive_id?: string; asset_tag?: string | null; occurred_at?: string; payload?: Record<string, unknown>; event_type?: string } = {};
  try { body = await req.json(); } catch {
    return new Response(JSON.stringify({ error: "Invalid JSON body" }), {
      status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
  if (!body.source || !(SOURCES as readonly string[]).includes(body.source)) {
    return new Response(JSON.stringify({ error: `Missing or invalid source (must be one of ${SOURCES.join(", ")})` }), {
      status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
  if (!body.source_id) {
    return new Response(JSON.stringify({ error: "Missing required field: source_id" }), {
      status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
  if (!body.hive_id) {
    return new Response(JSON.stringify({ error: "Missing required field: hive_id" }), {
      status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
  if (!body.payload || typeof body.payload !== "object") {
    return new Response(JSON.stringify({ error: "Missing required field: payload (object)" }), {
      status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  const db        = _warm || createClient(_URL, _KEY);

  // Pillar I: machine-ingest gate. Normalizes external events into a hive
  // scoped by the CLIENT hive_id on a service-role client, with no auth_uid to
  // membership-check (an external bridge is not a logged-in worker). Require a
  // trusted (service-role) caller so a browser/anon user can't inject events
  // into another hive. (Device-facing per-hive ingest key = tracked follow-up.)
  const _gate = await requireServiceRole(db, req);
  if (!_gate.ok) {
    return new Response(
      JSON.stringify({ error: _gate.message, code: _gate.code }),
      { status: _gate.status, headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  }

  const occurred  = body.occurred_at ? new Date(body.occurred_at) : new Date();
  const occurredIso = occurred.toISOString();
  const hash      = await sha256(`${body.source}|${body.source_id}|${occurredIso}`);

  // Route to source-specific adapter
  let adapted;
  if      (body.source === "sap_pm") adapted = adaptSapPm(body.payload);
  else if (body.source === "opc_ua") adapted = adaptOpcUa(body.payload);
  else                                 adapted = adaptGeneric(body.source as Source, body.payload);

  const row = {
    hive_id:      body.hive_id,
    asset_tag:    body.asset_tag || adapted.asset_tag,
    source:       body.source,
    source_id:    body.source_id,
    event_type:   body.event_type || adapted.event_type,
    occurred_at:  occurredIso,
    payload:      body.payload,
    payload_text: adapted.payload_text,
    embedding:    null,    // enrichment pass fills later
    hash,
  };

  // Idempotent insert: unique constraint on (source, source_id, hash) will
  // raise an error on duplicate which we treat as deduped.
  const { error } = await db.from("unified_events").insert(row);
  if (error) {
    // Postgres unique-violation code = 23505 → deduped, not an error
    const isDup = (error as { code?: string }).code === "23505" || String(error.message || "").includes("duplicate");
    if (isDup) {
      return new Response(JSON.stringify({ ok: true, written: 0, deduped: 1, errors: [] }), {
        status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }
    // T2b (shape-preserving): aggregate this HANDLED failure to wh_traces, keep the batch-result shape.
    await trackHandled(req, "data-fabric-normalizer", "normalize_error", error);
    return new Response(JSON.stringify({ ok: false, written: 0, deduped: 0, errors: [error.message] }), {
      status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  return new Response(JSON.stringify({ ok: true, written: 1, deduped: 0, errors: [] }), {
    status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
});
