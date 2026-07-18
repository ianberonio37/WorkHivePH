/**
 * intelligence-api — Phase 5.3: WorkHive Intelligence API
 *
 * Public REST API for third-party developers to access WorkHive's
 * anonymized benchmark data and intelligence reports.
 *
 * Authentication: API key in Authorization header (Bearer wh_...)
 * Rate limiting: 100 calls/hour per key
 *
 * Endpoints (path via ?endpoint=... query param):
 *   benchmarks    — MTBF by equipment category + industry
 *   failure-modes — Top failure causes (anonymized)
 *   report        — Latest intelligence report
 *   ping          — Health check (no auth required)
 */

import { serveObserved, failTracked } from "../_shared/observability.ts";
import { handleHealth } from "../_shared/health.ts";

import { logRequestStart } from "../_shared/logger.ts";

// contract-allow: PH intelligence data fetcher
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";

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

const RATE_LIMIT_PER_HOUR = 100;

// ---------------------------------------------------------------------------
// API key authentication + rate limiting
// ---------------------------------------------------------------------------

async function authenticate(
  db:         SupabaseClient,
  authHeader: string | null,
): Promise<{ ok: boolean; key_id?: string; hive_id?: string; error?: string }> {
  if (!authHeader?.startsWith("Bearer wh_")) {
    return { ok: false, error: "Missing or invalid API key. Use: Authorization: Bearer wh_..." };
  }

  const rawKey = authHeader.replace("Bearer ", "").trim();

  // Hash the key to compare against stored hash
  const hash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(rawKey));
  const keyHash = Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, "0")).join("");

  const { data: key } = await db.from("api_keys")
    .select("id, hive_id, enabled, call_count, last_used_at")
    .eq("key_hash", keyHash)
    .single();

  if (!key)          return { ok: false, error: "Invalid API key" };
  if (!key.enabled)  return { ok: false, error: "API key is disabled" };

  // Rate limiting: check calls in the last hour
  const hourAgo = new Date(Date.now() - 3600000).toISOString();
  if (key.last_used_at && key.last_used_at > hourAgo && key.call_count >= RATE_LIMIT_PER_HOUR) {
    return { ok: false, error: `Rate limit exceeded: ${RATE_LIMIT_PER_HOUR} calls/hour` };
  }

  // Increment counter (fire-and-forget)
  db.from("api_keys").update({
    call_count:  key.last_used_at && key.last_used_at > hourAgo ? key.call_count + 1 : 1,
    last_used_at: new Date().toISOString(),
  }).eq("id", key.id).then(() => {});

  return { ok: true, key_id: key.id, hive_id: key.hive_id };
}

// ---------------------------------------------------------------------------
// Endpoint handlers
// ---------------------------------------------------------------------------

async function handleBenchmarks(db: SupabaseClient, params: URLSearchParams) {
  const category = params.get("category");
  const industry = params.get("industry");

  let query = db.from("network_benchmarks")
    .select("equipment_category, industry, avg_mtbf_days, p25_mtbf_days, p75_mtbf_days, sample_hives, period_days, computed_at")
    .gte("sample_hives", 3)
    .order("avg_mtbf_days", { ascending: false })
    .limit(50);

  if (category) {
    // Escape SQL LIKE wildcards in user-controlled query param.
    const safeCategory = category.replace(/%/g, "\\%").replace(/_/g, "\\_").slice(0, 100);
    query = query.ilike("equipment_category", `%${safeCategory}%`);
  }
  if (industry) query = query.eq("industry", industry);

  const { data, error } = await query;
  if (error) throw new Error(error.message);

  return {
    benchmarks: data || [],
    meta: {
      description:  "Mean Time Between Failures (MTBF) in days by equipment category. Higher = more reliable.",
      unit:         "days",
      minimum_hives: 3,
      source:       "WorkHive Philippine Industrial Network",
    },
  };
}

async function handleFailureModes(db: SupabaseClient, params: URLSearchParams) {
  const period = parseInt(params.get("period") || "90");
  const since  = new Date(Date.now() - period * 86400000).toISOString();
  // AI grounding floors (mirror handleBenchmarks' gte sample_hives 3): a public "top failure
  // mode across the network" must not be published off a handful of rows, or a single root
  // cause surfaces as a "50-100% top mode" at an inflated, ungrounded percentage.
  const MIN_TOTAL      = 20;  // suppress the whole insight below a credible network sample
  const MIN_MODE_COUNT = 3;   // a root cause seen < 3x is not a "top failure mode"

  const { data: faults } = await db.from("fault_knowledge")
    .select("root_cause, category")
    .not("root_cause", "is", null)
    .gte("created_at", since)
    .limit(2000);

  const total = faults?.length || 0;
  if (total < MIN_TOTAL) {
    return {
      failure_modes: [],
      meta: {
        period_days: period, total_records: total, minimum_records: MIN_TOTAL,
        source: "WorkHive Philippine Industrial Network (anonymized)",
        note: `Insufficient network data (${total} records; need ${MIN_TOTAL}+) to publish failure modes.`,
      },
    };
  }

  const counts: Record<string, { count: number; categories: Set<string> }> = {};
  (faults || []).forEach((f: Record<string, string>) => {
    const rc = (f.root_cause || "").trim();
    if (rc.length < 4) return;
    if (!counts[rc]) counts[rc] = { count: 0, categories: new Set() };
    counts[rc].count++;
    if (f.category) counts[rc].categories.add(f.category);
  });

  const topModes = Object.entries(counts)
    .filter(([, { count }]) => count >= MIN_MODE_COUNT)   // per-mode floor
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, 10)
    .map(([cause, { count, categories }]) => ({
      cause,
      count,
      percentage:  Math.round(count / total * 100),
      categories:  Array.from(categories).slice(0, 3),
    }));

  return {
    failure_modes: topModes,
    meta: {
      period_days: period,
      total_records: total,
      minimum_records: MIN_TOTAL,
      minimum_mode_count: MIN_MODE_COUNT,
      source: "WorkHive Philippine Industrial Network (anonymized)",
    },
  };
}

async function handleReport(db: SupabaseClient) {
  const { data } = await db.from("ph_intelligence_reports")
    .select("period, period_type, hive_count, wo_count, equipment_count, report_json, narrative, generated_at")
    .order("generated_at", { ascending: false })
    .limit(1)
    .single();

  if (!data) return { error: "No report generated yet. Reports are produced monthly." };
  // AI grounding: flag a STALE report. The old code served the newest row as "the latest
  // report" with no freshness check, so a months-old narrative surfaced as current. A monthly
  // report older than this window means the generator likely hasn't run.
  const STALE_DAYS = 45;
  const ageDays = Math.floor((Date.now() - new Date(data.generated_at).getTime()) / 86400000);
  const stale   = ageDays > STALE_DAYS;
  return {
    report: data,
    stale,
    age_days: ageDays,
    ...(stale ? { note: `This report is ${ageDays} days old; a fresh monthly report may not have generated.` } : {}),
  };
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

serveObserved("intelligence-api", async (req) => {
  // Arc T/T1: standard liveness /health (fn up + DB creds reachable).
  const _health = await handleHealth(req, "intelligence-api", async () => ({
    deps: [{ name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) }],
  }));
  if (_health) return _health;
  const cors = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  logRequestStart(req, "intelligence-api");  // I6 observability

  const db     = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
  const url    = new URL(req.url);
  const ep     = url.searchParams.get("endpoint") || "ping";

  try {
    // Ping — no auth required
    if (ep === "ping") {
      return new Response(JSON.stringify({ ok: true, version: "1.0", docs: "WorkHive Intelligence API" }),
        { status: 200, headers: { ...cors, "Content-Type": "application/json" } });
    }

    // All other endpoints require authentication
    const auth = await authenticate(db, req.headers.get("Authorization"));
    if (!auth.ok) {
      return new Response(JSON.stringify({ error: auth.error }),
        { status: 401, headers: { ...cors, "Content-Type": "application/json" } });
    }

    let result: unknown;
    if (ep === "benchmarks")    result = await handleBenchmarks(db, url.searchParams);
    else if (ep === "failure-modes") result = await handleFailureModes(db, url.searchParams);
    else if (ep === "report")   result = await handleReport(db);
    else {
      return new Response(JSON.stringify({ error: `Unknown endpoint '${ep}'. Use: benchmarks, failure-modes, report, ping` }),
        { status: 404, headers: { ...cors, "Content-Type": "application/json" } });
    }

    return new Response(JSON.stringify(result),
      { status: 200, headers: { ...cors, "Content-Type": "application/json" } });

  } catch (err) {
    // T2b: aggregate this HANDLED failure to wh_traces + non-leaky 500.
    return await failTracked(req, "intelligence-api", "intelligence_api_error", err);
  }
});
