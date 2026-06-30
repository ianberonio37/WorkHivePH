// _shared/trace-store.ts
// Pillar O (Observability & SLO): the trace AGGREGATION layer.
//
// The trace STORE already exists — `wh_traces` gets one row per gateway request
// (trace_id, route, hive_id, user_id, status, latency_ms, model_chain,
// error_code, created_at; threaded by the envelope's beginRequest). What was
// missing is the rollup that turns those rows into the SLIs declared in
// GATEWAY_SLO.md: availability, error-rate, and latency percentiles. This helper
// is that rollup — a single source of truth a status page / SLO endpoint reads.
//
// SLO alignment (GATEWAY_SLO.md §1-2):
//   availability = % of requests that did NOT 5xx (and reached the edge)
//   error-rate   = % that 5xx'd OR carried an error_code, EXCLUDING the
//                  intended policy rejections 401/403/429 (those are Pillars
//                  I/P working as designed, tracked separately, not failures)
//   latency      = p50/p95/p99 over latency_ms
//
// Bounded by design (performance doctrine): never scan more than ROW_CAP recent
// rows; the created_at DESC index makes the windowed read cheap.

import { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";

const ROW_CAP = 5000;                 // hard ceiling per rollup (recent window)
const POLICY_REJECTIONS = new Set([401, 403, 429]); // intended, excluded from error-rate

export interface TraceRow {
  route:       string;
  status:      number | null;
  latency_ms:  number | null;
  error_code:  string | null;
  created_at:  string;
}

export interface TraceSummary {
  window_minutes:   number;
  total:            number;
  availability_pct: number | null;   // null when total === 0 (no data, not 0%)
  error_rate_pct:   number | null;
  policy_rejections: number;         // 401/403/429 count (informational)
  p50_ms:           number | null;
  p95_ms:           number | null;
  p99_ms:           number | null;
  by_route:         Record<string, { total: number; errors: number; p95_ms: number | null }>;
  generated_at:     string;
}

function percentile(sorted: number[], p: number): number | null {
  if (!sorted.length) return null;
  // nearest-rank (matches Postgres percentile_disc); sorted ascending.
  const idx = Math.min(sorted.length - 1, Math.max(0, Math.ceil(p * sorted.length) - 1));
  return sorted[idx];
}

/** True when a trace row counts as an error for the error-rate SLI:
 *  a 5xx, OR an error_code present — but NOT an intended policy rejection. */
export function isError(row: { status: number | null; error_code: string | null }): boolean {
  const s = row.status ?? 0;
  if (POLICY_REJECTIONS.has(s)) return false;     // intended rejection, not a failure
  if (s >= 500) return true;
  if (row.error_code) return true;
  return false;
}

/** Roll up the recent `wh_traces` window into the GATEWAY_SLO.md SLIs.
 *  Reads with the caller's client (service-role for a global view; an authed
 *  client is RLS-scoped to its own hive). Returns zeros-safe nulls on no data. */
export async function summarizeTraces(
  db: SupabaseClient,
  opts: { windowMinutes?: number; route?: string } = {},
): Promise<TraceSummary> {
  const windowMinutes = opts.windowMinutes ?? 60;
  const sinceIso = new Date(Date.now() - windowMinutes * 60_000).toISOString();

  // unbounded-ok: capped at ROW_CAP recent rows via the created_at DESC index;
  // a rollup over the newest window, not a full-table scan.
  // canonical-allow: wh_traces is the observability trace store's OWN table; this SLI rollup is control-plane telemetry, not a user-facing cross-surface KPI value — no v_*_truth wrapper applies.
  let q = db.from("wh_traces")
    .select("route, status, latency_ms, error_code, created_at")
    .gte("created_at", sinceIso)
    .order("created_at", { ascending: false })
    .limit(ROW_CAP);
  if (opts.route) q = q.eq("route", opts.route);

  const { data, error } = await q;
  const rows = (error || !data ? [] : data) as TraceRow[];

  const total = rows.length;
  let errors = 0, policyRej = 0;
  const latencies: number[] = [];
  const byRoute: Record<string, { total: number; errors: number; lat: number[] }> = {};

  for (const r of rows) {
    const s = r.status ?? 0;
    if (POLICY_REJECTIONS.has(s)) policyRej++;
    const err = isError(r);
    if (err) errors++;
    if (typeof r.latency_ms === "number") latencies.push(r.latency_ms);
    const br = (byRoute[r.route] ||= { total: 0, errors: 0, lat: [] });
    br.total++; if (err) br.errors++;
    if (typeof r.latency_ms === "number") br.lat.push(r.latency_ms);
  }

  latencies.sort((a, b) => a - b);
  const avail = total ? Number((100 * (total - countServerDown(rows)) / total).toFixed(2)) : null;
  const errRate = total ? Number((100 * errors / total).toFixed(2)) : null;

  const by_route: TraceSummary["by_route"] = {};
  for (const [route, v] of Object.entries(byRoute)) {
    v.lat.sort((a, b) => a - b);
    by_route[route] = { total: v.total, errors: v.errors, p95_ms: percentile(v.lat, 0.95) };
  }

  return {
    window_minutes:   windowMinutes,
    total,
    availability_pct: avail,
    error_rate_pct:   errRate,
    policy_rejections: policyRej,
    p50_ms:           percentile(latencies, 0.50),
    p95_ms:           percentile(latencies, 0.95),
    p99_ms:           percentile(latencies, 0.99),
    by_route,
    generated_at:     new Date().toISOString(),
  };
}

/** Availability counts a request as UP unless it 5xx'd or never reached the edge
 *  (status 0). Policy rejections (401/403/429) are UP (the gateway responded). */
function countServerDown(rows: { status: number | null }[]): number {
  return rows.filter((r) => { const s = r.status ?? 0; return s >= 500 || s === 0; }).length;
}
