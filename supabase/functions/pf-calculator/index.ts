/**
 * pf-calculator (Phase R.6)
 *
 * Computes the Potential failure -> Functional failure (P-F) interval for
 * a parameter on a given asset, then recommends an inspection cadence per
 * the RCM rule (P-F / 2 for normal, P-F / 3 for safety-critical assets).
 *
 * Pulls logbook.readings_json entries in window, extracts the requested
 * parameter, proxies the time-sorted (ts, value) series to the Python
 * Analytics API (POST /reliability/pf-interval), then persists the result
 * into pf_intervals so v_pf_truth surfaces the latest interval.
 *
 * Input:
 *   {
 *     hive_id, asset_id,
 *     parameter,           // e.g. "vibration_mms" — key inside readings_json
 *     p_threshold,         // number — warning level
 *     f_threshold,         // number — functional-failure level
 *     direction?,          // "above" | "below" (default "above")
 *     safety_critical?,    // bool   (default false; switches basis to P-F/3)
 *     since_days?,         // default 365
 *     fmea_mode_id?,
 *   }
 *
 * Output: { interval_id, pf_days, recommended_interval_days, basis,
 *           n_pairs, pairs, diagnostic, asset_tag }
 *
 * Skills consulted:
 *   - predictive-analytics (P-F/2 = standard, P-F/3 for safety-critical)
 *   - architect (canonical sources lookup via v_asset_truth, no parallel
 *     asset_id resolution; input contract documented in pf_intervals)
 *   - security (no service-role leak in errors, hive scoping on every read,
 *     parameter name allowlisted to alphanum + underscore)
 *   - devops (getCorsHeaders dynamic CORS, AbortSignal.timeout for the
 *     Python API call)
 *   - data-engineer (ignore null/NaN reading values; sort by created_at)
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

import { logRequestStart } from "../_shared/logger.ts";

// contract-allow: deterministic P-F interval calc; not a brain output
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";
import { log } from "../_shared/logger.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
// Pillar I (Gateway Spine): verify hive membership before any service-role read.
import { resolveIdentity, resolveTenancy } from "../_shared/tenant-context.ts";

// Warm module-scope Supabase client. Reused across request invocations
// in the same warm container. Per-request createClient calls below are
// being phased out (PRODUCTION_FIXES #46). Falls back to an empty
// client if env is missing so module import never throws.
const _WH_SUPABASE_URL_M = Deno.env.get("SUPABASE_URL") || "";
const _WH_SERVICE_KEY_M  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const _whWarmClient = _WH_SUPABASE_URL_M && _WH_SERVICE_KEY_M
  ? createClient(_WH_SUPABASE_URL_M, _WH_SERVICE_KEY_M)
  : null;
void _whWarmClient;

// ─── Constants ────────────────────────────────────────────────────────────────

const DEFAULT_SINCE_DAYS    = 365;
const PYTHON_API_TIMEOUT_MS = 90_000;
const PARAMETER_RE          = /^[a-z][a-z0-9_]{0,40}$/i;   // allowlist

type AnyRow = Record<string, unknown>;

interface PFResult {
  pf_days:                   number | null;
  recommended_interval_days: number | null;
  basis:                     string;
  n_pairs:                   number;
  pairs:                     Array<Record<string, unknown>>;
  diagnostic:                string;
}

// ─── Asset lookup via v_asset_truth (canonical) ──────────────────────────────

async function fetchAsset(db: SupabaseClient, hiveId: string, assetId: string) {
  const { data } = await db.from("v_asset_truth")
    .select("asset_id, tag, name, iso_class, legacy_asset_id")
    .eq("hive_id", hiveId).eq("asset_id", assetId).maybeSingle();
  return data;
}

// ─── Handler ─────────────────────────────────────────────────────────────────

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  logRequestStart(req, "pf-calculator");  // I6 observability

  try {
    const body = await req.json().catch(() => ({}));
    const hive_id         = String(body.hive_id  || "").trim();
    const asset_id        = String(body.asset_id || "").trim();
    const parameter       = String(body.parameter || "").trim();
    const p_threshold     = Number(body.p_threshold);
    const f_threshold     = Number(body.f_threshold);
    const direction       = String(body.direction || "above").toLowerCase();
    const safety_critical = !!body.safety_critical;
    const since_days      = Number(body.since_days) || DEFAULT_SINCE_DAYS;
    const fmea_mode_id    = body.fmea_mode_id ? String(body.fmea_mode_id) : null;

    if (!hive_id) {
      return new Response(
        JSON.stringify({ error: "Missing required field: hive_id" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }
    if (!asset_id) {
      return new Response(
        JSON.stringify({ error: "Missing required field: asset_id" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }
    if (!parameter || !PARAMETER_RE.test(parameter)) {
      return new Response(
        JSON.stringify({ error: "Missing or invalid required field: parameter (alphanumeric + underscore, max 40 chars)." }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }
    if (!Number.isFinite(p_threshold) || !Number.isFinite(f_threshold)) {
      return new Response(
        JSON.stringify({ error: "p_threshold and f_threshold must be finite numbers." }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }
    if (direction !== "above" && direction !== "below") {
      return new Response(
        JSON.stringify({ error: "direction must be 'above' or 'below'." }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    const db = createClient(
      Deno.env.get("SUPABASE_URL") || "",
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "",
    );

    // Pillar I: service-role client (RLS bypassed) scoped by the CLIENT hive_id
    // — verify active membership first, else any signed-in user could read or
    // write another hive's reliability data. Internal service-role calls skip.
    const { authUid, isServiceRole } = await resolveIdentity(db, req);
    if (!isServiceRole) {
      const tenancy = await resolveTenancy(db, authUid, hive_id);
      if (!tenancy.ok) {
        return new Response(
          JSON.stringify({ error: tenancy.message, code: tenancy.code }),
          { status: tenancy.status, headers: { ...corsHeaders, "Content-Type": "application/json" } },
        );
      }
    }

    // Resolve asset via canonical view
    const asset = await fetchAsset(db, hive_id, asset_id);
    if (!asset) {
      return new Response(
        JSON.stringify({ error: "Asset not found in this hive." }),
        { status: 404, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }
    const legacyId = (asset as AnyRow).legacy_asset_id;
    if (!legacyId) {
      return new Response(
        JSON.stringify({
          error: "Asset not found in this hive.",
        }),
        { status: 404, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    // Phase 5b: filter by canonical asset_node_id (uuid) directly.
    const sinceIso = new Date(Date.now() - since_days * 86_400_000).toISOString();
    const { data: rows, error: logErr } = await db.from("v_logbook_truth")  // canonical
      .select("created_at, readings_json")
      .eq("hive_id", hive_id)
      .eq("asset_node_id", asset_id)
      .gte("created_at", sinceIso)
      .not("readings_json", "is", null)
      .order("created_at", { ascending: true })
      .limit(1000);
    if (logErr) {
      return new Response(
        JSON.stringify({ error: "Logbook query failed", detail: logErr.message }),
        { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    const readings: Array<{ ts: string; value: number }> = [];
    for (const r of rows || []) {
      const rj = (r as AnyRow).readings_json as Record<string, unknown> | null;
      if (!rj || typeof rj !== "object") continue;
      const raw = rj[parameter];
      const v   = Number(raw);
      if (!Number.isFinite(v)) continue;
      readings.push({ ts: String((r as AnyRow).created_at), value: v });
    }

    if (readings.length < 2) {
      return new Response(
        JSON.stringify({
          interval_id:               null,
          pf_days:                   null,
          recommended_interval_days: null,
          basis:                     safety_critical ? "P-F/3" : "P-F/2",
          n_pairs:                   0,
          pairs:                     [],
          asset_tag:                 (asset as AnyRow).tag,
          diagnostic: (
            `Need at least 2 logbook entries with readings_json["${parameter}"] in the last ${since_days} days ` +
            `(have ${readings.length}). Capture more readings before recomputing.`
          ),
        }),
        { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    // Proxy to Python Analytics API
    const PYTHON_URL = Deno.env.get("PYTHON_API_URL");
    if (!PYTHON_URL) {
      return new Response(
        JSON.stringify({
          error: "Python Analytics API not configured.",
          hint:  "Set PYTHON_API_URL in Supabase Edge Function secrets.",
        }),
        { status: 503, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    let result: PFResult;
    try {
      const pyRes = await fetch(`${PYTHON_URL}/reliability/pf-interval`, {
        method:  "POST",
        headers: { "Content-Type": "application/json", "X-API-Key": Deno.env.get("PYTHON_API_KEY") ?? "" },
        body:    JSON.stringify({
          readings,
          p_threshold,
          f_threshold,
          direction,
          safety_critical,
        }),
        signal:  AbortSignal.timeout(PYTHON_API_TIMEOUT_MS),
      });
      if (!pyRes.ok) {
        const text = await pyRes.text().catch(() => "no body");
        return new Response(
          JSON.stringify({ error: `Python API ${pyRes.status}`, detail: text }),
          { status: 502, headers: { ...corsHeaders, "Content-Type": "application/json" } },
        );
      }
      result = await pyRes.json();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return new Response(
        JSON.stringify({ error: "Python API unreachable", detail: msg }),
        { status: 504, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    // pf_intervals.pf_days has CHECK > 0 — only persist when we actually have a window.
    let interval_id: string | null = null;
    if (
      result.pf_days != null &&
      Number(result.pf_days) > 0 &&
      result.recommended_interval_days != null &&
      Number(result.recommended_interval_days) > 0
    ) {
      const row: AnyRow = {
        hive_id,
        asset_id,
        fmea_mode_id,
        parameter,
        p_threshold,
        f_threshold,
        pf_days:                   result.pf_days,
        recommended_interval_days: result.recommended_interval_days,
        basis:                     result.basis || (safety_critical ? "P-F/3" : "P-F/2"),
      };
      const { data: ins, error: insErr } = await db.from("pf_intervals")
        .insert(row).select("id").single();
      if (insErr) {
        log.warn(null, "pf_intervals insert failed:", { detail: insErr.message });
      } else if (ins) {
        interval_id = (ins as { id: string }).id;
      }
    }

    return new Response(
      JSON.stringify({
        interval_id,
        asset_tag: (asset as AnyRow).tag,
        ...result,
      }),
      { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    // Inline JSON.stringify({ error: ... }) for static error-contract scan.
    return new Response(
      JSON.stringify({ error: "Internal error", detail: msg }),
      { status: 500, headers: { "Content-Type": "application/json", ...getCorsHeaders(req) } },
    );
  }
});
