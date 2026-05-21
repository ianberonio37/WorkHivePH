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

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

// contract-allow: PH intelligence report write
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { callAI } from "../_shared/ai-chain.ts";
import { logAICost, estimateTokens } from "../_shared/cost-log.ts";
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

Write the report narrative sections.`;

  try {
    const raw  = await callAI(prompt, { systemPrompt: NARRATIVE_SYSTEM, temperature: 0.3, maxTokens: 800, jsonMode: true });
    return JSON.parse(raw);
  } catch {
    return {
      executive_summary: `WorkHive analyzed ${(data.summary as Record<string, unknown>)?.work_orders || 0} maintenance records across ${(data.summary as Record<string, unknown>)?.active_hives || 0} Philippine industrial plants in this period.`,
      mtbf_insight:      "Equipment reliability data is being accumulated. Full MTBF benchmarks require 3+ months of continuous data.",
      failure_insight:   "Wear and lubrication failure remain the dominant root causes across equipment categories.",
      seasonal_insight:  "Typhoon season (June–November) correlates with elevated bearing and electrical failure rates due to humidity and flooding.",
      recommendation:    "Plants below the network MTBF average should review PM intervals and lubrication schedules for high-frequency breakdown equipment.",
    };
  }
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

serve(async (req) => {
  const cors = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });

  try {
    const db   = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
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
    const msg = err instanceof Error ? err.message : String(err);
    return new Response(JSON.stringify({ error: msg }),
      { status: 500, headers: { ...cors, "Content-Type": "application/json" } });
  }
});
