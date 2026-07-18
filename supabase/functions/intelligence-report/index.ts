/**
 * intelligence-report — Phase 5.1: Philippine Industrial Intelligence Report
 *
 * Aggregates anonymized maintenance data across all WorkHive hives and
 * generates the "State of Philippine Industrial Maintenance" report.
 *
 * Called monthly via pg_cron or manually via POST {}.
 * Stores in ph_intelligence_reports (one row per period, upserted).
 *
 * Report sections:
 *   summary        — key statistics across all hives
 *   mtbf_rankings  — top/bottom equipment categories by MTBF
 *   failure_modes  — most common root causes (anonymized)
 *   parts_risk     — parts chronically low across multiple hives
 *   seasonal       — failure rate variance by month (typhoon season flag)
 *   narrative      — AI-written executive summary + section insights
 */

import { serveObserved, failTracked } from "../_shared/observability.ts";
import { handleHealth } from "../_shared/health.ts";

import { logRequestStart } from "../_shared/logger.ts";

// contract-allow: PH intelligence report write
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { callAI } from "../_shared/ai-chain.ts";
import { logAICost, estimateTokens } from "../_shared/cost-log.ts";
import { getCorsHeaders } from "../_shared/cors.ts";
import { resolveIdentity } from "../_shared/tenant-context.ts";
import { checkUserRateLimit, userRateLimitedResponse } from "../_shared/rate-limit.ts";
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

// ---------------------------------------------------------------------------
// Period helpers
// ---------------------------------------------------------------------------

function currentPeriod(type: "monthly" | "quarterly"): string {
  const now = new Date();
  const y   = now.getFullYear();
  const m   = now.getMonth() + 1;
  if (type === "quarterly") {
    const q = Math.ceil(m / 3);
    return `${y}-Q${q}`;
  }
  return `${y}-${String(m).padStart(2, "0")}`;
}

// ---------------------------------------------------------------------------
// Data aggregation
// ---------------------------------------------------------------------------

async function gatherData(db: SupabaseClient) {
  const now   = new Date();
  const since = new Date(now.getTime() - 90 * 86400000).toISOString(); // time-window-allow: 90d = standard intelligence-rollup window across canonical truth views

  // Total hives with recent activity. Canonical: logbook_truth (drop-in for all 3 reads).
  // unbounded-query-allow: server-side intelligence rollup — full recent-activity scan for hive ranking
  const { data: activeHives } = await db.from("v_logbook_truth")
    .select("hive_id")
    .gte("created_at", since)
    .not("hive_id", "is", null);
  const uniqueHives = new Set((activeHives || []).map((r: Record<string, string>) => r.hive_id));

  // Total work orders
  const { count: woCount } = await db.from("v_logbook_truth")
    .select("id", { count: "exact", head: true })
    .gte("created_at", since);

  // Total unique machines
  // unbounded-query-allow: unique-machines count for intelligence rollup; full recent set required
  const { data: machineRows } = await db.from("v_logbook_truth")
    .select("machine")
    .gte("created_at", since)
    .not("machine", "is", null);
  const uniqueMachines = new Set((machineRows || []).map((r: Record<string, string>) => r.machine));

  // MTBF rankings from network_benchmarks
  const { data: benchmarks } = await db.from("network_benchmarks")
    .select("equipment_category, avg_mtbf_days, p75_mtbf_days, sample_hives")
    .gte("sample_hives", 2)
    .order("avg_mtbf_days", { ascending: false })
    .limit(10);

  // Top failure modes (anonymized — just root_cause, no machine IDs)
  const { data: faults } = await db.from("fault_knowledge")
    .select("root_cause, category")
    .not("root_cause", "is", null)
    .gte("created_at", since)
    .limit(1000);

  const rootCauseCount: Record<string, number> = {};
  (faults || []).forEach((f: Record<string, string>) => {
    const rc = (f.root_cause || "").trim();
    if (rc.length > 3) rootCauseCount[rc] = (rootCauseCount[rc] || 0) + 1;
  });
  const topFailureModes = Object.entries(rootCauseCount)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([cause, count]) => ({ cause, count, pct: Math.round(count / (faults?.length || 1) * 100) }));

  // Low stock parts across multiple hives. Canonical view exposes the
  // is_low_stock derived flag so the threshold rule lives in one place.
  // unbounded-query-allow: cross-hive low-stock scan for intelligence rollup
  const { data: lowStock } = await db.from("v_inventory_items_truth")
    .select("part_name, hive_id")
    .eq("is_low_stock", true)
    .not("hive_id", "is", null);

  const partRisk: Record<string, number> = {};
  (lowStock || []).forEach((i: Record<string, string>) => {
    const name = i.part_name || "";
    partRisk[name] = (partRisk[name] || 0) + 1;
  });
  const chronicLowStock = Object.entries(partRisk)
    .filter(([, n]) => n >= 2)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([part, hiveCount]) => ({ part, hive_count: hiveCount }));

  // Seasonal: failure count by month (last 12 months). Canonical: logbook_truth.
  // unbounded-query-allow: 12-month seasonal faults read for intelligence rollup
  const { data: monthlyFaults } = await db.from("v_logbook_truth")
    .select("created_at")
    .eq("maintenance_type", "Breakdown / Corrective")
    .gte("created_at", new Date(now.getTime() - 365 * 86400000).toISOString());

  const monthCount: Record<string, number> = {};
  (monthlyFaults || []).forEach((r: Record<string, string>) => {
    const m = r.created_at?.slice(0, 7) ?? "";
    monthCount[m] = (monthCount[m] || 0) + 1;
  });
  const seasonal = Object.entries(monthCount)
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([month, count]) => ({ month, count, typhoon_season: ["06","07","08","09","10","11"].includes(month.slice(5)) }));

  return {
    summary: {
      active_hives:    uniqueHives.size,
      work_orders:     woCount || 0,
      unique_machines: uniqueMachines.size,
      period_days:     90,
    },
    mtbf_rankings:    benchmarks || [],
    failure_modes:    topFailureModes,
    chronic_low_stock: chronicLowStock,
    seasonal,
  };
}

// ---------------------------------------------------------------------------
// AI narrative generation
// ---------------------------------------------------------------------------

const NARRATIVE_SYSTEM =
  `You are an industrial maintenance analyst writing the executive summary for the
Philippine Industrial Maintenance Intelligence Report — a quarterly industry benchmarking
report covering manufacturing plants across the Philippines that use WorkHive.

Write in clear, professional English. Be specific with numbers. Use Philippine context.
Keep each section under 80 words. Do not use bullet points — write flowing paragraphs.

Respond only in JSON:
{
  "executive_summary": "...",
  "mtbf_insight": "...",
  "failure_insight": "...",
  "seasonal_insight": "...",
  "recommendation": "..."
}`;

async function generateNarrative(data: Record<string, unknown>): Promise<Record<string, string>> {
  const prompt = `Data for the Philippine Industrial Intelligence Report:

Active plants: ${(data.summary as Record<string, unknown>)?.active_hives}
Work orders analyzed: ${(data.summary as Record<string, unknown>)?.work_orders}
Unique equipment monitored: ${(data.summary as Record<string, unknown>)?.unique_machines}

Top MTBF (ISO 14224:2016 §9.3, days between failures — platform variant uses CALENDAR time, not operating time): ${JSON.stringify((data.mtbf_rankings as unknown[])?.slice(0, 5))}

Most common failure causes (ISO 14224:2016 failure mode taxonomy): ${JSON.stringify((data.failure_modes as unknown[])?.slice(0, 5))}

Parts chronically low across multiple plants: ${JSON.stringify(data.chronic_low_stock)}

Monthly corrective-failure counts over the last 12 months (typhoon_season flags Jun-Nov): ${JSON.stringify((data.seasonal as unknown[])?.slice(-12))}

Write the report narrative sections. For seasonal_insight, ground every month/number in the monthly counts above — do NOT assert a seasonal pattern the data does not show.`;

  try {
    const raw  = await callAI(prompt, { systemPrompt: NARRATIVE_SYSTEM, temperature: 0.3, maxTokens: 800, jsonMode: true });
    // Arc S F-lens (F-005): when ALL AI providers are down, callAI() degrades to the
    // bare string "{}". JSON.parse("{}") succeeds, so without this guard the report
    // would silently store an EMPTY narrative (no executive_summary) instead of
    // falling through to the deterministic fallback below. Treat empty/"{}"/missing
    // required fields as "AI unavailable" so the catch produces a real narrative.
    if (!raw || raw.trim() === "" || raw.trim() === "{}") throw new Error("ai_unavailable");
    const parsed = JSON.parse(raw);
    if (!parsed || !parsed.executive_summary) throw new Error("ai_empty_narrative");
    return parsed;
  } catch {
    // Deterministic fallback when every AI provider is down. Every claim must still be
    // TRUE for THIS dataset — don't hardcode a seasonal/failure assertion the data may
    // not show (arc AI2b/AI3). Derive the seasonal + failure lines from the real inputs.
    const seas = (data.seasonal as Array<{ month: string; count: number; typhoon_season: boolean }>) || [];
    const peak = seas.slice().sort((a, b) => b.count - a.count)[0];
    const modes = (data.failure_modes as Array<Record<string, unknown>>) || [];
    const topMode = modes[0]?.root_cause ?? modes[0]?.mode ?? null;
    return {
      executive_summary: `WorkHive analyzed ${(data.summary as Record<string, unknown>)?.work_orders || 0} maintenance records across ${(data.summary as Record<string, unknown>)?.active_hives || 0} Philippine industrial plants in this period.`,
      mtbf_insight:      "Equipment reliability data is being accumulated. Full MTBF benchmarks require 3+ months of continuous data.",
      failure_insight:   topMode
        ? `The most frequently logged root cause across the network this period is ${topMode}.`
        : "Root-cause data is still being accumulated across the network.",
      seasonal_insight:  peak
        ? `Corrective failures peaked in ${peak.month} (${peak.count} across the network)${peak.typhoon_season ? ", within the Jun-Nov typhoon season" : ""}. Continue tracking monthly to confirm any seasonal pattern.`
        : "Not enough monthly history yet to identify a seasonal failure pattern; continue logging to build the 12-month trend.",
      recommendation:    "Plants below the network MTBF average should review PM intervals and lubrication schedules for high-frequency breakdown equipment.",
    };
  }
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

serveObserved("intelligence-report", async (req) => {
  // Arc T/T1: standard liveness /health (fn up + DB creds reachable).
  const _health = await handleHealth(req, "intelligence-report", async () => ({
    deps: [{ name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) }],
  }));
  if (_health) return _health;
  const cors = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  logRequestStart(req, "intelligence-report");  // I6 observability

  try {
    const db   = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);

    // LLM10 unbounded-consumption + authZ: this is a HEAVY cross-hive aggregation + LLM narrative,
    // user-triggered from ph-intelligence.html. Require a logged-in caller and cap per-user (low cap —
    // it's expensive). The scheduled/cron path uses service_role and is exempt (trusted, periodic).
    const _id = await resolveIdentity(db, req);
    if (!_id.isServiceRole) {
      if (!_id.authUid) {
        return new Response(JSON.stringify({ error: "Authentication required" }),
          { status: 401, headers: { ...cors, "Content-Type": "application/json" } });
      }
      const _rl = await checkUserRateLimit(db, "", _id.authUid, 50, 6);
      if (!_rl.allowed) return userRateLimitedResponse(cors, _rl.user_cap);
    }

    const body = await req.json().catch(() => ({}));
    const type = (body.period_type || "monthly") as "monthly" | "quarterly";
    const period = body.period || currentPeriod(type);

    const data      = await gatherData(db);
    const narrative = await generateNarrative(data);

    const report = {
      period,
      period_type:     type,
      hive_count:      data.summary.active_hives,
      wo_count:        data.summary.work_orders,
      equipment_count: data.summary.unique_machines,
      report_json:     data,
      narrative,
      generated_at:    new Date().toISOString(),
    };

    await db.from("ph_intelligence_reports")
      .upsert(report, { onConflict: "period" });

    await db.from("automation_log").insert({
      job_name: "intelligence-report",
      hive_id:  null,
      status:   "success",
      detail:   `Intelligence report for ${period} generated. ${data.summary.active_hives} hives, ${data.summary.work_orders} WOs.`,
    });

    return new Response(JSON.stringify({ ok: true, period, report }),
      { status: 200, headers: { ...cors, "Content-Type": "application/json" } });

  } catch (err) {
    // T2b: aggregate this HANDLED failure to wh_traces + non-leaky 500.
    return await failTracked(req, "intelligence-report", "intelligence_report_error", err);
  }
});
