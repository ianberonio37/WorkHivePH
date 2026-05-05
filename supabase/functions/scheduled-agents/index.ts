import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { callAI } from "../_shared/ai-chain.ts";
import { getCorsHeaders } from "../_shared/cors.ts";

function callGroq(prompt: string, systemPrompt: string): Promise<string> {
  return callAI(prompt, { systemPrompt, temperature: 0.2, maxTokens: 1024, jsonMode: true });
}

// ── Log result to automation_log ──────────────────────────────────────────────

async function logRun(db: SupabaseClient, jobName: string, hiveId: string | null, status: string, detail: string) {
  await db.from("automation_log").insert({ job_name: jobName, hive_id: hiveId, status, detail });
}

// ── Save report to ai_reports ─────────────────────────────────────────────────

async function saveReport(db: SupabaseClient, hiveId: string, reportType: string, reportJson: unknown, summary: string) {
  await db.from("ai_reports").insert({ hive_id: hiveId, report_type: reportType, report_json: reportJson, summary });
}

// ── REPORT: PM Overdue ────────────────────────────────────────────────────────

const PM_OVERDUE_SYSTEM = `You are a PM health analyst. Analyze asset PM data and produce a daily overdue report.
Identify assets with no PM in 30+ days as overdue, 15-29 days as at-risk.
Respond only in JSON: { "overdue_count": number, "at_risk_count": number, "overdue_assets": [{"asset_name","days_since_pm","risk":"CRITICAL|HIGH"}], "summary": "one sentence for supervisor" }`;

async function runPMOverdue(db: SupabaseClient, hiveId: string, voiceContext?: string): Promise<string> {
  const { data: assets } = await db.from("pm_assets").select("id, asset_name, category").eq("hive_id", hiveId);
  if (!assets?.length) return "No assets found.";

  const assetIds = assets.map(a => a.id);
  const { data: completions } = await db.from("pm_completions")
    .select("asset_id, completed_at")
    .in("asset_id", assetIds)
    .order("completed_at", { ascending: false });

  const lastDone: Record<string, string> = {};
  (completions || []).forEach(c => { if (!lastDone[c.asset_id]) lastDone[c.asset_id] = c.completed_at; });

  const now = Date.now();
  const summary = assets.map(a => {
    const last = lastDone[a.id];
    const days = last ? Math.floor((now - new Date(last).getTime()) / 86400000) : 999;
    return `${a.asset_name}|${a.category}|${last ? `${days} days ago` : "never"}`;
  }).join("\n");

  const ctx = voiceContext ? `\n\nUser context: "${voiceContext}"` : "";
  const raw = await callGroq(`Assets (name|category|last_pm):\n${summary}${ctx}`, PM_OVERDUE_SYSTEM);
  const result = JSON.parse(raw);
  await saveReport(db, hiveId, "pm_overdue", result, result.summary || "PM overdue check complete.");
  return result.summary || "PM check done.";
}

// ── REPORT: Failure Digest ────────────────────────────────────────────────────

const FAILURE_DIGEST_SYSTEM = `You are a weekly maintenance risk analyst. Analyze this week's failure records.
Respond only in JSON: { "top_risk_machines": [{"machine","failure_count","total_downtime_h"}], "repeat_failures": [{"machine","root_cause","times"}], "week_summary": "two sentence executive summary for the supervisor" }`;

async function runFailureDigest(db: SupabaseClient, hiveId: string, voiceContext?: string): Promise<string> {
  const since = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString();
  const { data } = await db.from("logbook")
    .select("machine, category, root_cause, downtime_hours, created_at")
    .eq("hive_id", hiveId)
    .eq("maintenance_type", "Breakdown / Corrective")
    .gte("created_at", since)
    .limit(100);

  if (!data?.length) return "No failures this week.";

  const summary = data.map(e =>
    `${e.machine}|${e.category}|${e.root_cause || "unknown"}|${e.downtime_hours || 0}h`
  ).join("\n");

  const ctx = voiceContext ? `\n\nUser context: "${voiceContext}"` : "";
  const raw = await callGroq(`This week's failures (machine|category|root_cause|downtime):\n${summary}${ctx}`, FAILURE_DIGEST_SYSTEM);
  const result = JSON.parse(raw);
  await saveReport(db, hiveId, "failure_digest", result, result.week_summary || "Failure digest complete.");
  return result.week_summary || "Failure digest done.";
}

// ── REPORT: Shift Handover ────────────────────────────────────────────────────

const HANDOVER_SYSTEM = `You are a shift handover report generator. Summarize the last 8 hours of maintenance activity.
Respond only in JSON: { "open_jobs": [{"machine","problem","priority":"HIGH|MEDIUM|LOW"}], "completed_jobs": [{"machine","action"}], "critical_alerts": ["alert"], "handover_note": "one paragraph for the next shift" }`;

async function runShiftHandover(db: SupabaseClient, hiveId: string, voiceContext?: string): Promise<string> {
  const since = new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString();
  const { data } = await db.from("logbook")
    .select("machine, category, problem, action, status, worker_name, created_at")
    .eq("hive_id", hiveId)
    .gte("created_at", since)
    .order("created_at", { ascending: false })
    .limit(50);

  if (!data?.length) return "No activity in the last 8 hours.";

  const summary = data.map(e =>
    `${e.machine}|${e.status}|${e.problem || ""}|${e.action || ""}|${e.worker_name}`
  ).join("\n");

  const ctx = voiceContext ? `\n\nUser context: "${voiceContext}"` : "";
  const raw = await callGroq(`Last 8h records (machine|status|problem|action|worker):\n${summary}${ctx}`, HANDOVER_SYSTEM);
  const result = JSON.parse(raw);
  await saveReport(db, hiveId, "shift_handover", result, result.handover_note || "Shift handover report saved.");
  return result.handover_note || "Handover done.";
}

// ── REPORT: Predictive ────────────────────────────────────────────────────────

const PREDICTIVE_SYSTEM = `You are a predictive maintenance analyst. Calculate MTBF per machine and predict next failures.
Respond only in JSON: { "predictions": [{"machine","mtbf_days":number,"last_failure":"YYYY-MM-DD","predicted_next":"YYYY-MM-DD","risk":"HIGH|MEDIUM|LOW"}], "highest_risk_machine": "machine name", "summary": "one sentence for supervisor" }`;

async function runPredictive(db: SupabaseClient, hiveId: string, voiceContext?: string): Promise<string> {
  const { data } = await db.from("logbook")
    .select("machine, created_at")
    .eq("hive_id", hiveId)
    .eq("maintenance_type", "Breakdown / Corrective")
    .order("machine", { ascending: true })
    .order("created_at", { ascending: true })
    .limit(200);

  if (!data?.length) return "Not enough failure history for predictions yet.";

  const summary = data.map(e => `${e.machine}|${e.created_at?.slice(0, 10)}`).join("\n");
  const today = new Date().toISOString().slice(0, 10);

  const ctx = voiceContext ? `\n\nUser context: "${voiceContext}"` : "";
  const raw = await callGroq(`Today: ${today}\nFailure history (machine|date):\n${summary}${ctx}`, PREDICTIVE_SYSTEM);
  const result = JSON.parse(raw);
  await saveReport(db, hiveId, "predictive", result, result.summary || "Predictive analysis complete.");
  return result.summary || "Predictive done.";
}

// ── REPORT: Project Suggestions (Phase 6B) ───────────────────────────────────
// Scans last 90d of logbook for repeat-failure patterns per asset and suggests
// bundling into a Reliability Study or Breakdown Repair Bundle project. Skips
// hives that already have an active project for the candidate asset.

const PROJECT_SUGGESTIONS_SYSTEM = `You are a maintenance reliability analyst. From a list of assets with high recent breakdown counts in the last 90 days, suggest which deserve a formal project (Reliability Study for >=5 breakdowns, Breakdown Repair Bundle for repeated same root cause).

Respond only in JSON:
{
  "suggestions": [
    {
      "asset_name": "string",
      "breakdown_count": number,
      "dominant_root_cause": "string or null",
      "suggested_project_type": "workorder|shutdown|capex",
      "suggested_template_id": "reliability_study|breakdown_bundle|pump_overhaul|...",
      "rationale": "1 sentence why this asset deserves a project"
    }
  ],
  "summary": "one sentence executive summary for supervisor"
}

Suggest at most 5 assets. If no clear candidates, return empty suggestions array.`;

async function runProjectSuggestions(db: SupabaseClient, hiveId: string, voiceContext?: string): Promise<string> {
  const since = new Date(Date.now() - 90 * 86400000).toISOString();
  const { data: logs } = await db.from("logbook")
    .select("machine, root_cause, maintenance_type, created_at")
    .eq("hive_id", hiveId).eq("maintenance_type", "Breakdown / Corrective")
    .gte("created_at", since).limit(500);
  if (!logs?.length) return "No breakdown history in the last 90 days.";

  // Skip assets already covered by an active project
  const { data: activeProjects } = await db.from("projects")
    .select("id").eq("hive_id", hiveId).in("status", ["planning", "active"]).is("deleted_at", null);
  const activeProjectIds = (activeProjects || []).map(p => p.id);
  let coveredAssets: string[] = [];
  if (activeProjectIds.length) {
    const { data: links } = await db.from("project_links")
      .select("label").in("project_id", activeProjectIds).eq("link_type", "asset");
    coveredAssets = (links || []).map(l => (l as Record<string, string>).label || "").filter(Boolean);
  }

  // Group breakdowns by machine, count + dominant root cause
  const byMachine: Record<string, { count: number; causes: Record<string, number> }> = {};
  for (const l of logs) {
    const m = (l as Record<string, string>).machine;
    if (!m || coveredAssets.includes(m)) continue;
    if (!byMachine[m]) byMachine[m] = { count: 0, causes: {} };
    byMachine[m].count += 1;
    const rc = (l as Record<string, string>).root_cause;
    if (rc) byMachine[m].causes[rc] = (byMachine[m].causes[rc] || 0) + 1;
  }

  const candidates = Object.entries(byMachine)
    .filter(([_, v]) => v.count >= 3)
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, 10)
    .map(([m, v]) => {
      const dominant = Object.entries(v.causes).sort((a, b) => b[1] - a[1])[0]?.[0] || null;
      return `${m}|${v.count}|${dominant || "various"}`;
    });
  if (!candidates.length) return "No assets with 3+ breakdowns. No project suggestions.";

  const ctx = voiceContext ? `\n\nUser context: "${voiceContext}"` : "";
  const raw = await callGroq(`Assets with breakdown counts last 90d (machine|count|dominant_root_cause):\n${candidates.join("\n")}${ctx}`, PROJECT_SUGGESTIONS_SYSTEM);
  const result = JSON.parse(raw);
  await saveReport(db, hiveId, "project_suggestions", result, result.summary || "Project suggestions ready.");
  return result.summary || `${(result.suggestions || []).length} project suggestion(s).`;
}

// ── REPORT: Project Risk Flagging (Phase 6C) ─────────────────────────────────
// Scans recent project_progress_logs blockers across active projects, classifies
// into themes (parts, permits, scope, weather, resources) and counts hot themes.

const PROJECT_RISK_SYSTEM = `You are a project risk analyst. Classify maintenance project blockers from progress logs into recurring themes and surface the top risks for the supervisor.

Themes to use (consistent across all reports):
- "parts_unavailable" — waiting on parts, supplier delay, vendor lead time
- "permit_delay"      — PTW issue, LOTO not ready, regulatory hold
- "scope_creep"       — additional work discovered, change order needed
- "weather"           — rain, typhoon, heat
- "resource"          — crew unavailable, contractor no-show, skill gap
- "safety"            — incident, near miss, equipment hazard
- "other"             — anything that doesn't fit above

Respond only in JSON:
{
  "theme_counts": { "parts_unavailable": n, "permit_delay": n, ... },
  "top_risks": [
    {
      "theme": "string",
      "project_codes": ["SHD-2026-001", ...],
      "example_blocker": "verbatim quote ≤120 chars",
      "recommendation": "1 sentence actionable next step"
    }
  ],
  "summary": "one sentence executive summary"
}

Top 3 risks max. Use only the data provided — never invent.`;

async function runProjectRisk(db: SupabaseClient, hiveId: string, voiceContext?: string): Promise<string> {
  const since = new Date(Date.now() - 30 * 86400000).toISOString();
  // Get active projects + their blockers from last 30d
  const { data: projects } = await db.from("projects")
    .select("id, project_code").eq("hive_id", hiveId)
    .in("status", ["planning", "active"]).is("deleted_at", null);
  if (!projects?.length) return "No active projects with blockers to analyse.";

  const projectIds = projects.map(p => p.id);
  const { data: logs } = await db.from("project_progress_logs")
    .select("project_id, blockers, log_date")
    .in("project_id", projectIds).gte("log_date", since.slice(0, 10));
  const withBlockers = (logs || []).filter(l => ((l as Record<string, string>).blockers || "").trim());
  if (!withBlockers.length) return "No blockers reported in active projects last 30 days.";

  const projCodeById: Record<string, string> = {};
  projects.forEach(p => { projCodeById[p.id] = p.project_code; });

  const blockerLines = withBlockers.slice(0, 50).map(l => {
    const code = projCodeById[(l as Record<string, string>).project_id] || "?";
    return `${code}|${(l as Record<string, string>).log_date}|${(l as Record<string, string>).blockers.slice(0, 200)}`;
  });

  const ctx = voiceContext ? `\n\nUser context: "${voiceContext}"` : "";
  const raw = await callGroq(`Project blockers last 30d (project_code|date|text):\n${blockerLines.join("\n")}${ctx}`, PROJECT_RISK_SYSTEM);
  const result = JSON.parse(raw);
  await saveReport(db, hiveId, "project_risk", result, result.summary || "Project risk analysis complete.");
  return result.summary || `${(result.top_risks || []).length} risk theme(s) flagged.`;
}

// ── Entry point ───────────────────────────────────────────────────────────────

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    // hive_id is optional — when provided, runs for that hive only (on-demand from Report Sender).
    // When omitted, runs for all hives (cron path — unchanged behaviour).
    const { report_type, hive_id, voice_context } = await req.json();

    if (!report_type) {
      return new Response(
        JSON.stringify({ error: "Missing required field: report_type" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const db = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    // TODO Phase 3: add per-hive AI rate limit check here before running reports.

    let hives: { id: string; name: string }[];

    if (hive_id) {
      // On-demand: run for a single hive (called from Report Sender page)
      const { data, error: hiveErr } = await db
        .from("hives").select("id, name").eq("id", hive_id).single();
      if (hiveErr || !data) {
        return new Response(
          JSON.stringify({ status: "skipped", reason: "Hive not found" }),
          { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
      hives = [data];
    } else {
      // Cron path: run for all active hives
      const { data, error: hivesErr } = await db.from("hives").select("id, name");
      if (hivesErr || !data?.length) {
        return new Response(
          JSON.stringify({ status: "skipped", reason: "No hives found" }),
          { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
      hives = data;
    }

    const runners: Record<string, (db: SupabaseClient, hiveId: string, voiceContext?: string) => Promise<string>> = {
      pm_overdue:           runPMOverdue,
      failure_digest:       runFailureDigest,
      shift_handover:       runShiftHandover,
      predictive:           runPredictive,
      project_suggestions:  runProjectSuggestions,   // Phase 6B
      project_risk:         runProjectRisk,          // Phase 6C
    };

    const runner = runners[report_type];
    if (!runner) {
      return new Response(
        JSON.stringify({ error: `Unknown report_type: ${report_type}` }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Run report for all hives in parallel
    const results = await Promise.allSettled(
      hives.map(async (hive) => {
        try {
          const summary = await runner(db, hive.id, voice_context);
          await logRun(db, report_type, hive.id, "success", summary);
          return { hive: hive.name, status: "success", summary };
        } catch (err) {
          const detail = err instanceof Error ? err.message : String(err);
          await logRun(db, report_type, hive.id, "failed", detail);
          return { hive: hive.name, status: "failed", detail };
        }
      })
    );

    const output = results.map(r =>
      r.status === "fulfilled" ? r.value : { status: "failed", detail: String(r.reason) }
    );

    return new Response(
      JSON.stringify({ report_type, hives_processed: hives.length, results: output }),
      { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );

  } catch (err) {
    console.error("scheduled-agents error:", err);
    return new Response(
      JSON.stringify({ error: err instanceof Error ? err.message : String(err) }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
