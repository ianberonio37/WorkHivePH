/**
 * weibull-fitter (Phase R.5)
 *
 * Pulls corrective logbook entries for an asset over a lookback window,
 * computes time-between-failures (TBF) plus a right-censored tail
 * (asset has survived from the last failure to today without breakdown),
 * proxies the durations to the Python Analytics API
 * (POST /reliability/weibull → lifelines.WeibullFitter), and persists
 * the result into weibull_fits so v_weibull_truth surfaces the latest fit.
 *
 * Input:  { hive_id, asset_id, since_days?, fmea_mode_id? }
 * Output: { fit_id, beta, eta_days, failure_pattern, n_failures,
 *           n_censored, log_likelihood, diagnostic, asset_tag }
 *
 * Skills consulted:
 *  - predictive-analytics (lifelines preferred over hand-rolled MLE for
 *    censored support; insufficient_data threshold = 4 failures per IEC 61649)
 *  - architect (canonical sources lookup via v_asset_truth, no parallel
 *    asset_id resolution)
 *  - security (no service-role leak in errors, hive scoping on every read)
 *  - devops (getCorsHeaders dynamic CORS, AbortSignal.timeout for the
 *    Python API call so a stalled cold-start does not hang the Edge runtime)
 *  - data-engineer (TBF math + right-censoring at end of window)
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";

// ─── Constants ────────────────────────────────────────────────────────────────

const DEFAULT_SINCE_DAYS = 730;     // 2 years — enough events for a defensible fit
const MIN_FAILURES_FOR_FIT = 4;     // mirror the Python module's IEC 61649 threshold
const PYTHON_API_TIMEOUT_MS = 90_000; // Render free tier cold start

const CORRECTIVE_RE = /corrective|breakdown/i;

type AnyRow = Record<string, unknown>;

interface WeibullFit {
  beta:            number | null;
  eta_days:        number | null;
  failure_pattern: string;
  n_failures:      number;
  n_censored:      number;
  log_likelihood:  number | null;
  fit_method:      string;
  diagnostic:      string;
}

// ─── Asset lookup via v_asset_truth (canonical) ──────────────────────────────

async function fetchAsset(db: SupabaseClient, hiveId: string, assetId: string) {
  const { data } = await db.from("v_asset_truth")
    .select("asset_id, tag, name, iso_class, legacy_asset_id")
    .eq("hive_id", hiveId).eq("asset_id", assetId).maybeSingle();
  return data;
}

// ─── TBF + right-censored tail computation ──────────────────────────────────

/**
 * Sort events ascending, take time-between-successive-failures in days, then
 * append a single right-censored survival from the last failure timestamp to
 * NOW. Censored data is treated as a survival observation (asset has lived at
 * least this long without failing again), which is the standard lifelines
 * convention.
 */
function computeDurations(timestamps: string[]): { failures: number[]; censored: number[] } {
  const stamps = timestamps
    .map(t => new Date(t).getTime())
    .filter(n => Number.isFinite(n))
    .sort((a, b) => a - b);

  if (stamps.length < 2) return { failures: [], censored: [] };

  const failures: number[] = [];
  for (let i = 1; i < stamps.length; i++) {
    const days = (stamps[i] - stamps[i - 1]) / 86_400_000;
    if (days > 0) failures.push(days);
  }

  // Right-censored tail: NOW - last_failure_ts
  const tailDays = (Date.now() - stamps[stamps.length - 1]) / 86_400_000;
  const censored: number[] = (tailDays > 0) ? [tailDays] : [];

  return { failures, censored };
}

// ─── Handler ─────────────────────────────────────────────────────────────────

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });

  try {
    const body = await req.json().catch(() => ({}));
    const hive_id      = String(body.hive_id || "").trim();
    const asset_id     = String(body.asset_id || "").trim();
    const fmea_mode_id = body.fmea_mode_id ? String(body.fmea_mode_id) : null;
    const since_days   = Number(body.since_days) || DEFAULT_SINCE_DAYS;

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

    const db = createClient(
      Deno.env.get("SUPABASE_URL") || "",
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "",
    );

    // Resolve asset via the canonical view
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
          error: "Asset has no legacy_asset_id bridge. Register or backfill the asset before fitting Weibull.",
        }),
        { status: 422, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    // Pull corrective logbook entries in window. asset_ref_id (text) joins legacy_asset_id.
    const sinceIso = new Date(Date.now() - since_days * 86_400_000).toISOString();
    const { data: rows, error: logErr } = await db.from("v_logbook_truth")   // canonical
      .select("id, created_at, maintenance_type")
      .eq("hive_id", hive_id)
      .eq("asset_ref_id", legacyId)
      .gte("created_at", sinceIso)
      .order("created_at", { ascending: true })
      .limit(500);
    if (logErr) {
      return new Response(
        JSON.stringify({ error: "Logbook query failed", detail: logErr.message }),
        { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }
    const corrective = (rows || []).filter(r => CORRECTIVE_RE.test(String(r.maintenance_type || "")));
    const stamps = corrective.map(r => String(r.created_at));
    const { failures, censored } = computeDurations(stamps);

    // Insufficient data shortcut — skip the Python call, persist a stub row so
    // the UI can show "need more data" without a 5xx round-trip.
    if (failures.length < MIN_FAILURES_FOR_FIT) {
      const stub: WeibullFit = {
        beta:            null,
        eta_days:        null,
        failure_pattern: "insufficient_data",
        n_failures:      failures.length,
        n_censored:      censored.length,
        log_likelihood:  null,
        fit_method:      "mle_lifelines",
        diagnostic:      `Need at least ${MIN_FAILURES_FOR_FIT} corrective events in the lookback window (have ${failures.length}). Log more breakdowns or widen since_days before refitting.`,
      };
      const inserted = await persistFit(db, hive_id, asset_id, fmea_mode_id, since_days, stub);
      return new Response(
        JSON.stringify({
          fit_id:          inserted?.id || null,
          asset_tag:       (asset as AnyRow).tag,
          ...stub,
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

    let fit: WeibullFit;
    try {
      const pyRes = await fetch(`${PYTHON_URL}/reliability/weibull`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ failures, censored }),
        signal:  AbortSignal.timeout(PYTHON_API_TIMEOUT_MS),
      });
      if (!pyRes.ok) {
        const text = await pyRes.text().catch(() => "no body");
        return new Response(
          JSON.stringify({ error: `Python API ${pyRes.status}`, detail: text }),
          { status: 502, headers: { ...corsHeaders, "Content-Type": "application/json" } },
        );
      }
      fit = await pyRes.json();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return new Response(
        JSON.stringify({ error: "Python API unreachable", detail: msg }),
        { status: 504, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    // Persist into weibull_fits and return the canonical row.
    const inserted = await persistFit(db, hive_id, asset_id, fmea_mode_id, since_days, fit);

    return new Response(
      JSON.stringify({
        fit_id:    inserted?.id || null,
        asset_tag: (asset as AnyRow).tag,
        ...fit,
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

// ─── Persistence ──────────────────────────────────────────────────────────────

async function persistFit(
  db: SupabaseClient,
  hiveId: string,
  assetId: string,
  fmeaModeId: string | null,
  sinceDays: number,
  fit: WeibullFit,
): Promise<{ id: string } | null> {
  const row: AnyRow = {
    hive_id:            hiveId,
    asset_id:           assetId,
    fmea_mode_id:       fmeaModeId,
    beta:               fit.beta,
    eta_days:           fit.eta_days,
    failure_pattern:    fit.failure_pattern,
    n_failures:         fit.n_failures,
    n_censored:         fit.n_censored,
    fit_method:         fit.fit_method || "mle_lifelines",
    log_likelihood:     fit.log_likelihood,
    source_window_days: sinceDays,
  };
  const { data, error } = await db.from("weibull_fits")
    .insert(row).select("id").single();
  if (error) {
    console.warn("weibull_fits insert failed:", error.message);
    return null;
  }
  return data as { id: string };
}
