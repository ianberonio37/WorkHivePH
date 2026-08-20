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

import { serveObserved, failTracked } from "../_shared/observability.ts";
import { handleHealth } from "../_shared/health.ts";
import { logRequestStart } from "../_shared/logger.ts";

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
  unit:        string | null;
  meta:        Record<string, unknown>;
  is_anomaly?: boolean;
}

// ── Z-score anomaly, formula z_score_anomaly_3sigma ──────────────────────────
// AH16 (2026-07-28): formula_contracts.json has claimed since 2026-05-20 that THIS function
// "sets quality_flag='ANOMALY' when |z|>3", and it did no such thing — the string appeared
// nowhere in this file. Meanwhile v_sensor_truth.is_anomaly tested for that same 'ANOMALY'
// value, which the sensor_readings CHECK constraint forbids, so the flag four surfaces read
// (the asset-hub banner, index.html's Today ranker, get_hive_dashboard, the Companion registry)
// could never be true. Migration 20260728000018 gave the anomaly its own boolean column; this
// is the writer that was documented but never built.
const ANOMALY_SIGMA        = 3;      // |z| > 3 — the contract's threshold
const BASELINE_MIN_SAMPLES = 12;     // below this, sigma is not worth trusting; flag nothing
const BASELINE_WINDOW_DAYS = 30;
const BASELINE_MAX_ROWS    = 500;

/** Population mean + sample stddev. Returns null when the baseline is too thin to judge. */
function baselineOf(values: number[]): { mean: number; std: number } | null {
  const xs = values.filter(v => Number.isFinite(v));
  if (xs.length < BASELINE_MIN_SAMPLES) return null;
  const mean = xs.reduce((a, b) => a + b, 0) / xs.length;
  const std  = Math.sqrt(xs.reduce((a, b) => a + (b - mean) ** 2, 0) / (xs.length - 1));
  // A perfectly flat baseline gives sigma 0, and every deviation would divide to Infinity.
  // A constant signal has no anomalies to speak of, so say so rather than flagging everything.
  if (!(std > 0)) return null;
  return { mean, std };
}

// ── unit resolution ──────────────────────────────────────────────────────────
// v_sensor_recent EXPOSES `unit` so asset-hub can render telemetry WITH its unit (migration
// ...068). Nothing filled it: `unit` appeared nowhere in this function and nowhere in its payload
// contract, so every reading the plant bridge ever wrote had unit NULL. Measured 2026-08-20:
// 77,814 SEEDED rows carry a unit, and the only 3 rows from this live path carry none — so the
// telemetry panel would render `2.7` with nothing saying mm/s, which is precisely the bare-number
// defect the units_declared oracle exists to catch.
//
// A bridge that KNOWS its unit is authoritative (a US plant may publish degF or in/s), so `unit`
// is accepted from the payload. When absent we derive from the parameter, using the mapping the
// 25,938-rows-per-parameter seed already established — and stamp meta.unit_source so a derived
// unit is never mistaken for one the plant asserted. An UNKNOWN parameter is left NULL rather
// than guessed: a wrong unit is worse than a missing one on a maintenance surface.
const DERIVED_UNIT: Record<string, string> = {
  vibration:    'mm/s',
  temperature:  'celsius',
  current_draw: 'ampere',
};
// Free text is never accepted: a unit is a label a person reads, so keep it short and printable.
const UNIT_RE = /^[A-Za-z°][A-Za-z0-9°\/%._-]{0,15}$/;

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

  // Payload wins; derivation is the fallback. A malformed unit is REJECTED rather than silently
  // dropped — a bridge sending garbage should learn, not have its label quietly replaced.
  let unit: string | null = null;
  let unitDerived = false;
  if (r.unit !== undefined && r.unit !== null && String(r.unit).trim() !== "") {
    const u = String(r.unit).trim();
    if (!UNIT_RE.test(u)) return { ok: false, index: idx, reason: "unit fails allowlist regex" };
    unit = u;
  } else if (DERIVED_UNIT[parameter]) {
    unit = DERIVED_UNIT[parameter];
    unitDerived = true;
  }
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
      unit,
      // Provenance, not decoration: a DERIVED unit is this platform's inference from the
      // parameter name, while a payload unit is what the plant asserted. Anything reading these
      // rows later can tell the two apart instead of trusting a label whose origin is unknowable.
      meta: unitDerived ? { ...meta, unit_source: 'derived' } : meta,
    },
  };
}

serveObserved("sensor-readings-ingest", async (req) => {
  // Arc T/T1: standard liveness /health (fn up + DB creds reachable).
  const _health = await handleHealth(req, "sensor-readings-ingest", async () => ({
    deps: [{ name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) }],
  }));
  if (_health) return _health;
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  logRequestStart(req, "sensor-readings-ingest");  // I6 observability

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

    // ── Flag anomalies before writing (formula z_score_anomaly_3sigma) ───────
    // One baseline query per (asset, parameter) actually present in this batch, not per row.
    // Baseline is the PRIOR history only — the incoming rows are judged against what came
    // before them, never against themselves, or a batch of identical faulty readings would
    // establish its own normal and flag nothing.
    //
    // NOTE (CANONICAL_SOURCES_AUDIT #6): the Brain's statistical baseline and this one are
    // meant to share a definition rather than drift apart. There was nothing to share with
    // until now — this is the first baseline this function has ever computed — so the window,
    // minimum-sample and sigma constants live at the top of this file as the single place to
    // reconcile them when that unification happens.
    try {
      const sinceIso = new Date(Date.now() - BASELINE_WINDOW_DAYS * 86400000).toISOString();
      const pairs = Array.from(new Set(cleanedRows.map(r => `${r.asset_id} ${r.parameter}`)));
      for (const key of pairs) {
        const [assetId, parameter] = key.split(" ");
        // canonical-allow: the baseline needs the parameter's HISTORY, and v_sensor_truth is
        // DISTINCT ON (hive, asset, parameter) — exactly ONE row, the latest. Reading it here
        // would give a 1-sample baseline that BASELINE_MIN_SAMPLES rejects, so the anomaly flag
        // would silently never fire again. The raw table is the correct source for a rolling
        // statistic; v_sensor_truth remains correct for "what is this sensor reading now".
        const { data: hist } = await db.from("sensor_readings")
          .select("value")
          .eq("hive_id", hive_id)
          .eq("asset_id", assetId)
          .eq("parameter", parameter)
          .gte("recorded_at", sinceIso)
          .order("recorded_at", { ascending: false })
          .limit(BASELINE_MAX_ROWS);
        const base = baselineOf((hist || []).map(h => Number(h.value)));
        if (!base) continue;   // too little history to judge — leave the default false
        for (const row of cleanedRows) {
          if (row.asset_id !== assetId || row.parameter !== parameter) continue;
          row.is_anomaly = Math.abs(row.value - base.mean) / base.std > ANOMALY_SIGMA;
        }
      }
    } catch (_) {
      // An anomaly flag is an enrichment, never a reason to drop a plant bridge's readings on
      // the floor. If the baseline pass fails the rows still land, is_anomaly stays false.
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
    const anomalies   = cleanedRows.filter(r => r.is_anomaly).length;

    return new Response(
      JSON.stringify({
        inserted,
        skipped_dup,
        rejected: errors.length,
        // Reported so a plant bridge can see the flag was applied, and so a caller that
        // suddenly starts flagging everything notices before the dashboards do.
        anomalies,
        errors,
      }),
      { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  } catch (err) {
    // T2b: aggregate this HANDLED failure to wh_traces + non-leaky 500.
    return await failTracked(req, "sensor-readings-ingest", "sensor_readings_ingest_error", err);
  }
});
