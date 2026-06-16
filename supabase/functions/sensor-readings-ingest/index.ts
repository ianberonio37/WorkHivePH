/**
// capability: sensor_ingest
 * sensor-readings-ingest - HTTP-side of the plant MQTT/OPC-UA bridge.
 *
 * The persistent subscriber runs at the plant (Pi, plant gateway, or any
 * always-on machine) because Render free tier sleeps after 15 min of idle
 * HTTP. The subscriber batches readings and POSTs them here. This function
 * validates each reading, applies hive scoping, and bulk-inserts via the
 * UNIQUE external_key dedup so a re-send is a no-op.
 *
 * Input (single OR batch shape both accepted):
 *   {
 *     hive_id: string,
 *     readings: [
 *       {
 *         asset_id:    string (uuid),
 *         parameter:   string (^[a-z][a-z0-9_]{0,40}$),
 *         value:       number,
 *         recorded_at: string (ISO 8601),
 *         source?:     "mqtt"|"opc_ua"|"manual"|"edge_ai"|"sensor_test",
 *         meta?:       object
 *       },
 *       ...
 *     ]
 *   }
 *
 * Output:
 *   {
 *     inserted:    number,
 *     skipped_dup: number,
 *     rejected:    number,
 *     errors:      Array<{ index: number, reason: string }>
 *   }
 *
 * Skills consulted:
 *   integration-engineer (idempotent via external_key UNIQUE, bulk insert
 *     to keep per-row cost flat, sensor_test source distinct so production
 *     dashboards filter it out)
 *   security (hive scope enforced server-side regardless of payload claim;
 *     parameter allowlist regex on every row; value finite check)
 *   data-engineer (200-row batch cap to keep edge runtime under 30s on the
 *     worst-case path; ON CONFLICT (external_key) DO NOTHING)
 *   architect (validates asset_id belongs to hive via asset_nodes lookup
 *     before insert - cross-hive smuggling defense)
 *   devops (getCorsHeaders dynamic CORS, warm module-scope client)
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";
// Pillar I: machine-ingest gate — only trusted (service-role) callers may write.
import { requireServiceRole } from "../_shared/tenant-context.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";

// Warm module-scope client.
const _WH_SUPABASE_URL_M = Deno.env.get("SUPABASE_URL") || "";
const _WH_SERVICE_KEY_M  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const _whWarmClient = _WH_SUPABASE_URL_M && _WH_SERVICE_KEY_M
  ? createClient(_WH_SUPABASE_URL_M, _WH_SERVICE_KEY_M)
  : null;
void _whWarmClient;

const MAX_READINGS_PER_REQUEST = 200;
const PARAMETER_RE             = /^[a-z][a-z0-9_]{0,40}$/;
const ALLOWED_SOURCES          = new Set(["mqtt", "opc_ua", "manual", "edge_ai", "sensor_test"]);
const UUID_RE                  = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type AnyRow = Record<string, unknown>;

interface ReadingInput {
  asset_id:    string;
  parameter:   string;
  value:       number;
  recorded_at: string;
  source?:     string;
  meta?:       Record<string, unknown>;
}

interface ReadingRow {
  hive_id:     string;
  asset_id:    string;
  parameter:   string;
  value:       number;
  recorded_at: string;
  source:      string;
  meta:        Record<string, unknown>;
}

function validateReading(
  r: AnyRow, hive_id: string, idx: number,
): { ok: true; row: ReadingRow } | { ok: false; reason: string; index: number } {
  if (!r || typeof r !== "object") return { ok: false, index: idx, reason: "row is not an object" };

  const asset_id = String(r.asset_id || "").trim();
  if (!UUID_RE.test(asset_id)) return { ok: false, index: idx, reason: "asset_id is not a uuid" };

  const parameter = String(r.parameter || "").trim().toLowerCase();
  if (!PARAMETER_RE.test(parameter)) return { ok: false, index: idx, reason: "parameter fails allowlist regex" };

  const valueNum = Number(r.value);
  if (!Number.isFinite(valueNum)) return { ok: false, index: idx, reason: "value is not a finite number" };

  const recordedRaw = String(r.recorded_at || "").trim();
  const recordedDate = new Date(recordedRaw);
  if (!recordedRaw || Number.isNaN(recordedDate.getTime())) {
    return { ok: false, index: idx, reason: "recorded_at is not a valid ISO 8601 timestamp" };
  }
  // Reject readings more than 24h in the future (clock skew) and >365d old.
  const ageMs = Date.now() - recordedDate.getTime();
  if (ageMs < -24 * 3600 * 1000) return { ok: false, index: idx, reason: "recorded_at is too far in the future" };
  if (ageMs > 365 * 86400 * 1000) return { ok: false, index: idx, reason: "recorded_at is older than 365 days" };

  const source = r.source ? String(r.source).toLowerCase() : "mqtt";
  if (!ALLOWED_SOURCES.has(source)) return { ok: false, index: idx, reason: `source '${source}' not allowed` };

  const meta = (r.meta && typeof r.meta === "object" && !Array.isArray(r.meta))
    ? (r.meta as Record<string, unknown>)
    : {};

  return {
    ok: true,
    row: {
      hive_id,
      asset_id,
      parameter,
      value:       valueNum,
      recorded_at: recordedDate.toISOString(),
      source,
      meta,
    },
  };
}

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });

  try {
    const body = await req.json().catch(() => ({}));
    const hive_id = String(body.hive_id || "").trim();

    if (!UUID_RE.test(hive_id)) {
      return new Response(
        JSON.stringify({ error: "Missing or invalid hive_id (must be uuid)" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    // Accept both single and batch shape.
    const rawReadings: AnyRow[] = Array.isArray(body.readings)
      ? body.readings as AnyRow[]
      : (body.reading ? [body.reading as AnyRow] : []);

    if (!rawReadings.length) {
      return new Response(
        JSON.stringify({ error: "Missing readings array (or single reading object)" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }
    if (rawReadings.length > MAX_READINGS_PER_REQUEST) {
      return new Response(
        JSON.stringify({ error: `Batch too large: max ${MAX_READINGS_PER_REQUEST} readings per request` }),
        { status: 413, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    const db = _whWarmClient || createClient(
      Deno.env.get("SUPABASE_URL") || "",
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "",
    );

    // Pillar I: machine-ingest gate. This endpoint writes sensor_readings scoped
    // by the CLIENT hive_id on a service-role client and has no auth_uid to
    // membership-check (a plant bridge is not a logged-in worker). Require a
    // trusted (service-role) caller so a browser/anon user can't inject readings
    // into another hive. (Device-facing per-hive ingest key = tracked follow-up.)
    const _gate = await requireServiceRole(db, req);
    if (!_gate.ok) {
      return new Response(
        JSON.stringify({ error: _gate.message, code: _gate.code }),
        { status: _gate.status, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    // Validate every row up front.
    const validated: ReadingRow[] = [];
    const errors: Array<{ index: number; reason: string }> = [];
    rawReadings.forEach((r, i) => {
      const result = validateReading(r, hive_id, i);
      if (result.ok) validated.push(result.row);
      else errors.push({ index: result.index, reason: result.reason });
    });

    if (!validated.length) {
      return new Response(
        JSON.stringify({ inserted: 0, skipped_dup: 0, rejected: errors.length, errors }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    // Hive-scope check: every asset_id must belong to this hive. Reject any
    // that don't to prevent cross-hive injection through a compromised plant
    // bridge.
    const uniqueAssetIds = Array.from(new Set(validated.map(v => v.asset_id)));
    const { data: validAssets } = await db.from("v_asset_truth")
      .select("id:asset_id")
      .eq("hive_id", hive_id)
      .in("asset_id", uniqueAssetIds);
    const validSet = new Set((validAssets || []).map(a => String(a.id)));

    const cleanedRows: ReadingRow[] = [];
    validated.forEach((row, vi) => {
      if (validSet.has(row.asset_id)) {
        cleanedRows.push(row);
      } else {
        // Find original index for error reporting.
        const originalIdx = rawReadings.findIndex(r => r && (r as AnyRow).asset_id === row.asset_id && (r as AnyRow).parameter === row.parameter && (r as AnyRow).recorded_at === row.recorded_at);
        errors.push({ index: originalIdx >= 0 ? originalIdx : vi, reason: "asset_id not in this hive" });
      }
    });

    if (!cleanedRows.length) {
      return new Response(
        JSON.stringify({ inserted: 0, skipped_dup: 0, rejected: errors.length, errors }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    // Bulk insert with conflict ignore on external_key (generated column).
    const { data: ins, error: insErr } = await db.from("sensor_readings")
      .upsert(cleanedRows as unknown as AnyRow[], {
        onConflict: "external_key",
        ignoreDuplicates: true,
      })
      .select("id");

    if (insErr) {
      return new Response(
        JSON.stringify({ error: "Bulk insert failed", detail: insErr.message }),
        { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    const inserted    = ins ? ins.length : 0;
    const skipped_dup = cleanedRows.length - inserted;

    return new Response(
      JSON.stringify({
        inserted,
        skipped_dup,
        rejected: errors.length,
        errors,
      }),
      { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    // Inline JSON.stringify({ error: ... }) for static error-contract scan.
    return new Response(
      JSON.stringify({ error: "Internal error", detail: msg }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  }
});
