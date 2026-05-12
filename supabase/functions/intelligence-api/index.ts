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

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

// contract-allow: PH intelligence data fetcher
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";

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

  if (category) query = query.ilike("equipment_category", `%${category}%`);
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

  const { data: faults } = await db.from("fault_knowledge")
    .select("root_cause, category")
    .not("root_cause", "is", null)
    .gte("created_at", since)
    .limit(2000);

  const counts: Record<string, { count: number; categories: Set<string> }> = {};
  (faults || []).forEach((f: Record<string, string>) => {
    const rc = (f.root_cause || "").trim();
    if (rc.length < 4) return;
    if (!counts[rc]) counts[rc] = { count: 0, categories: new Set() };
    counts[rc].count++;
    if (f.category) counts[rc].categories.add(f.category);
  });

  const total = faults?.length || 1;
  const topModes = Object.entries(counts)
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
  return { report: data };
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

serve(async (req) => {
  const cors = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });

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
    const msg = err instanceof Error ? err.message : String(err);
    return new Response(JSON.stringify({ error: msg }),
      { status: 500, headers: { ...cors, "Content-Type": "application/json" } });
  }
});
