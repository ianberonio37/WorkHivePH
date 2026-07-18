/**
 * benchmark-compute — Phase 3.2: Cross-Hive Benchmark Network
 *
 * Computes MTBF and MTTR per equipment category across all hives.
 * Writes two tables:
 *   hive_benchmarks    — each hive's own metrics (hive can see this)
 *   network_benchmarks — anonymized aggregate (min 3 hives to publish)
 *
 * Run weekly via pg_cron. Also callable manually via POST { hive_id } for one hive.
 * No AI calls — pure SQL aggregation, deterministic and free.
 */

import { serveObserved, failTracked } from "../_shared/observability.ts";
import { handleHealth } from "../_shared/health.ts";
import { logRequestStart } from "../_shared/logger.ts";

import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";
import { log } from "../_shared/logger.ts";
// Pillar I (Gateway Spine): verify hive membership on the single-hive path.
import { resolveIdentity, resolveTenancy } from "../_shared/tenant-context.ts";
// A5 (FULLSTACK_COMPONENT_LIBRARY Layer A): per-person rate limit on the browser path.
import { checkSoloRateLimit, soloRateLimitKey, soloRateLimitedResponse } from "../_shared/rate-limit.ts";
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

const PERIOD_DAYS = 90;

// ---------------------------------------------------------------------------
// Category extraction from logbook category/maintenance_type
// ---------------------------------------------------------------------------

const CATEGORY_KEYWORDS: Record<string, string[]> = {
  "Centrifugal Pump":      ["pump", "centrifugal", "P-", "SP-", "SUB-"],
  "AC Motor":              ["motor", "M-", "winding", "stator"],
  "Air Compressor":        ["compressor", "AC-", "compressed air"],
  "Genset":                ["genset", "generator", "GEN-", "engine"],
  "Chiller":               ["chiller", "CH-", "refriger"],
  "VFD":                   ["vfd", "drive", "inverter", "VFD-"],
  "Cooling Tower":         ["cooling tower", "CT-"],
  "Belt Conveyor":         ["conveyor", "belt", "BC-"],
  "Steam Boiler":          ["boiler", "BLR-", "steam"],
  "Transformer":           ["transformer", "TX-"],
};

function extractCategory(machine: string, category: string): string {
  const combined = (machine + " " + category).toLowerCase();
  for (const [cat, keywords] of Object.entries(CATEGORY_KEYWORDS)) {
    if (keywords.some(kw => combined.includes(kw.toLowerCase()))) return cat;
  }
  return "General";
}

// ---------------------------------------------------------------------------
// Per-hive MTBF computation
// ---------------------------------------------------------------------------

interface LogbookRow {
  machine: string;
  category: string;
  maintenance_type: string;
  downtime_hours: number | null;
  created_at: string;
}

function computeHiveMetrics(
  rows: LogbookRow[],
  hiveId: string,
): Record<string, { mtbf: number | null; mttr: number | null; count: number; machines: Set<string> }> {
  const byCategory: Record<string, {
    breakdowns: { machine: string; date: Date }[];
    repairHours: number[];
    machines: Set<string>;
  }> = {};

  for (const r of rows) {
    const cat = extractCategory(r.machine || "", r.category || "");
    if (!byCategory[cat]) byCategory[cat] = { breakdowns: [], repairHours: [], machines: new Set() };
    byCategory[cat].machines.add(r.machine);

    if (r.maintenance_type === "Breakdown / Corrective") {
      byCategory[cat].breakdowns.push({ machine: r.machine, date: new Date(r.created_at) });
      if (r.downtime_hours && r.downtime_hours > 0) {
        byCategory[cat].repairHours.push(r.downtime_hours);
      }
    }
  }

  const metrics: Record<string, { mtbf: number | null; mttr: number | null; count: number; machines: Set<string> }> = {};

  for (const [cat, data] of Object.entries(byCategory)) {
    const { breakdowns, repairHours, machines } = data;
    let mtbf: number | null = null;
    let mttr: number | null = null;

    if (breakdowns.length >= 2) {
      // Sort by date and compute intervals between consecutive failures
      const sorted = [...breakdowns].sort((a, b) => a.date.getTime() - b.date.getTime());
      const intervals: number[] = [];
      for (let i = 1; i < sorted.length; i++) {
        const days = (sorted[i].date.getTime() - sorted[i-1].date.getTime()) / 86400000;
        if (days > 0) intervals.push(days);
      }
      if (intervals.length) {
        mtbf = Math.round(intervals.reduce((a, b) => a + b, 0) / intervals.length * 10) / 10;
      }
    } else if (breakdowns.length === 1) {
      // Only one failure — MTBF = period length (optimistic estimate)
      mtbf = PERIOD_DAYS;
    }

    if (repairHours.length) {
      mttr = Math.round(repairHours.reduce((a, b) => a + b, 0) / repairHours.length * 10) / 10;
    }

    metrics[cat] = { mtbf, mttr, count: breakdowns.length, machines };
  }

  return metrics;
}

// ---------------------------------------------------------------------------
// Main computation
// ---------------------------------------------------------------------------

async function computeForHive(db: SupabaseClient, hiveId: string, now: Date) {
  const since = new Date(now.getTime() - PERIOD_DAYS * 86400000).toISOString();

  // Canonical: logbook_truth (drop-in column-compatible with logbook).
  const { data: rows } = await db.from("v_logbook_truth")
    .select("machine, category, maintenance_type, downtime_hours, created_at")
    .eq("hive_id", hiveId)
    .gte("created_at", since)
    .limit(5000);

  if (!rows?.length) return [];

  const metrics = computeHiveMetrics(rows as LogbookRow[], hiveId);
  const hiveRows: Record<string, unknown>[] = [];

  for (const [cat, m] of Object.entries(metrics)) {
    hiveRows.push({
      hive_id:           hiveId,
      equipment_category: cat,
      mtbf_days:         m.mtbf,
      mttr_hours:        m.mttr,
      failure_count:     m.count,
      sample_machines:   m.machines.size,
      period_days:       PERIOD_DAYS,
      computed_at:       now.toISOString(),
    });
  }

  if (hiveRows.length) {
    // unbounded-query-allow: benchmark aggregator reads the full benchmark table for percentile compute
    await db.from("hive_benchmarks")
      .upsert(hiveRows, { onConflict: "hive_id,equipment_category" });
  }

  return hiveRows;
}

async function computeNetwork(db: SupabaseClient, now: Date) {
  // Pull all recent hive_benchmarks
  // unbounded-query-allow: network percentile compute — full recent-benchmark scan required
  const { data: allHive } = await db.from("hive_benchmarks")
    .select("hive_id, equipment_category, mtbf_days, failure_count")
    .gte("computed_at", new Date(now.getTime() - 8 * 86400000).toISOString()) // last 8 days
    .not("mtbf_days", "is", null);

  if (!allHive?.length) return;

  // Group by category
  const byCat: Record<string, number[]> = {};
  for (const row of allHive) {
    const cat = row.equipment_category;
    if (!byCat[cat]) byCat[cat] = [];
    if (row.mtbf_days) byCat[cat].push(row.mtbf_days);
  }

  const networkRows: Record<string, unknown>[] = [];
  for (const [cat, values] of Object.entries(byCat)) {
    if (values.length < 3) continue; // minimum 3 hives to publish (privacy)
    const sorted = [...values].sort((a, b) => a - b);
    const avg    = sorted.reduce((a, b) => a + b, 0) / sorted.length;
    const p25idx = Math.floor(sorted.length * 0.25);
    const p75idx = Math.floor(sorted.length * 0.75);

    networkRows.push({
      equipment_category: cat,
      industry:           "",   // '' (not null) — keyed by the composite UNIQUE (cat, industry)
      avg_mtbf_days:      Math.round(avg * 10) / 10,
      p25_mtbf_days:      sorted[p25idx] ?? null,
      p75_mtbf_days:      sorted[p75idx] ?? null,
      sample_hives:       values.length,
      period_days:        PERIOD_DAYS,
      computed_at:        now.toISOString(),
    });
  }

  if (networkRows.length) {
    // on_conflict targets the plain composite UNIQUE (equipment_category, industry).
    // The previous expression-index target ("...,COALESCE(industry,'')") made
    // PostgREST throw `column "COALESCE" does not exist` — and the error was never
    // checked, so the whole network table silently never populated. Check it now.
    const { error } = await db.from("network_benchmarks")
      .upsert(networkRows, { onConflict: "equipment_category,industry" });
    if (error) {
      log.error(null, "network_benchmarks upsert failed", { err: error.message, rows: networkRows.length });
      throw new Error(`network_benchmarks upsert failed: ${error.message}`);
    }
  }
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

serveObserved("benchmark-compute", async (req) => {
  // Arc T/T1: standard liveness /health (fn up + DB creds reachable).
  const _health = await handleHealth(req, "benchmark-compute", async () => ({
    deps: [{ name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) }],
  }));
  if (_health) return _health;
  const cors = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  logRequestStart(req, "benchmark-compute");  // I6 observability

  try {
    const db  = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
    const body = await req.json().catch(() => ({}));
    const now  = new Date();

    // Pillar I: single-hive (browser, from hive.html) path scopes benchmark
    // reads/writes by the client hive_id on a service-role client — verify
    // membership. The no-hive_id path fans out over ALL hives (cron,
    // service-role) and is left untouched. Service-role callers skip.
    if (body.hive_id) {
      const { authUid, isServiceRole } = await resolveIdentity(db, req);
      if (!isServiceRole) {
        const t = await resolveTenancy(db, authUid, String(body.hive_id));
        if (!t.ok) {
          return new Response(
            JSON.stringify({ error: t.message, code: t.code }),
            { status: t.status, headers: { ...cors, "Content-Type": "application/json" } },
          );
        }
      
        // A5: rate-limit the browser path (service-role/internal callers skip) — reference: voice-model-call/embed-entry.
        const _ip = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim();
        const _rl = await checkSoloRateLimit(db, soloRateLimitKey(authUid, _ip), undefined, undefined, _ip);
        if (!_rl.allowed) return soloRateLimitedResponse(getCorsHeaders(req));
      }
    }

    let hiveIds: string[] = [];
    if (body.hive_id) {
      hiveIds = [body.hive_id];
    } else {
      const { data: hives } = await db.from("v_hives_truth").select("id").limit(500);
      hiveIds = (hives || []).map((h: { id: string }) => h.id);
    }

    let totalHives = 0;
    for (const hiveId of hiveIds) {
      try {
        await computeForHive(db, hiveId, now);
        totalHives++;
      } catch (e) {
        log.error(null, "benchmark-compute error", { hive_id: hiveId, err: String(e) });
      }
    }

    // Compute network aggregate after all hives are updated
    if (!body.hive_id) {
      await computeNetwork(db, now);
    }

    await db.from("automation_log").insert({
      job_name: "benchmark-compute",
      hive_id:  body.hive_id || null,
      status:   "success",
      detail:   `Computed benchmarks for ${totalHives} hive(s).`,
    });

    return new Response(JSON.stringify({ ok: true, hives_computed: totalHives }),
      { status: 200, headers: { ...cors, "Content-Type": "application/json" } });

  } catch (err) {
    // T2b: aggregate this HANDLED failure to wh_traces + non-leaky 500.
    return await failTracked(req, "benchmark-compute", "benchmark_compute_error", err);
  }
});
