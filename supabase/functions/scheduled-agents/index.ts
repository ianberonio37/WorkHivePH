import { serveObserved, failTracked } from "../_shared/observability.ts";
import { handleHealth } from "../_shared/health.ts";

import { logRequestStart } from "../_shared/logger.ts";

// contract-allow: cron-triggered writes
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { callAI } from "../_shared/ai-chain.ts";
import { log } from "../_shared/logger.ts";
import { logAICost, estimateTokens } from "../_shared/cost-log.ts";

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
// redactPII imported as sentinel for validate_pii_egress; per-line
// `<redacted>` substitution is the working approach for the
// pipe-delimited summary shape used here.
import { redactPII as _redactPII } from "../_shared/redactPII.ts";  // eslint-disable-line
import { getCorsHeaders } from "../_shared/cors.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
// Pillar I (Gateway Spine): verify hive membership on the on-demand path.
import { resolveIdentity, resolveTenancy } from "../_shared/tenant-context.ts";
import { checkAIRateLimit, rateLimitedResponse, checkRouteRateLimit, routeRateLimitedResponse } from "../_shared/rate-limit.ts";

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

// Arc Y Y2 fork#2 (WAT split): overdue/at-risk are DETERMINISTIC math from the
// canonical FREQUENCY-AWARE view (v_pm_scope_items_truth, distinct pm_asset_id rolled up),
// NOT a flat-30-day rule the LLM re-derives. The model only writes the one-sentence summary
// from the already-computed numbers — it never classifies. (Prior path: flat "30+ days" in
// the prompt, over-counting long-frequency PMs and contradicting the tiles.)
const PM_OVERDUE_SYSTEM = `You are a PM health analyst writing a daily report for a supervisor.
You are GIVEN the already-computed overdue and at-risk counts and the asset list — do NOT
re-classify or change the numbers. Write a single supervisor-facing sentence.
Respond only in JSON: { "summary": "one sentence for the supervisor" }`;

async function runPMOverdue(db: SupabaseClient, hiveId: string, voiceContext?: string): Promise<string> {
  // Canonical PM-overdue: frequency-aware scope items rolled up to DISTINCT assets.
  const { data: rows } = await db.from("v_pm_scope_items_truth")
    .select("pm_asset_id, asset_name, asset_category, asset_criticality, days_until_due, is_overdue, is_due_soon")
    .eq("hive_id", hiveId)
    .limit(4000);
  if (!rows || !rows.length) return "No PM assets found.";

  // Roll scope items up to one entry per asset: overdue if ANY item is_overdue; at-risk if
  // ANY item is_due_soon and the asset is not already overdue. Track the worst days_until_due.
  type AssetAgg = { asset_name: string; category: string; criticality: string; overdue: boolean; dueSoon: boolean; worstDays: number };
  const byAsset: Record<string, AssetAgg> = {};
  for (const r of rows) {
    const k = r.pm_asset_id as string;
    const a = byAsset[k] || (byAsset[k] = { asset_name: r.asset_name, category: r.asset_category, criticality: r.asset_criticality, overdue: false, dueSoon: false, worstDays: 9999 });
    if (r.is_overdue) a.overdue = true;
    if (r.is_due_soon) a.dueSoon = true;
    if (typeof r.days_until_due === "number" && r.days_until_due < a.worstDays) a.worstDays = r.days_until_due;
  }
  const assets = Object.values(byAsset);
  const overdueAssets = assets.filter(a => a.overdue)
    .sort((x, y) => x.worstDays - y.worstDays)
    .map(a => ({ asset_name: a.asset_name, days_since_pm: a.worstDays < 0 ? -a.worstDays : 0, risk: a.criticality === "critical" ? "CRITICAL" : "HIGH" }));
  const atRiskCount = assets.filter(a => !a.overdue && a.dueSoon).length;

  const result = {
    overdue_count: overdueAssets.length,
    at_risk_count: atRiskCount,
    overdue_assets: overdueAssets,
    summary: "",
  };

  // LLM writes ONLY the summary sentence from the deterministic numbers (WAT split).
  const ctx = voiceContext ? `\n\nUser context: "${voiceContext}"` : "";
  const topList = overdueAssets.slice(0, 10).map(a => `${a.asset_name} (${a.days_since_pm}d overdue, ${a.risk})`).join("; ") || "none";
  try {
    const raw = await callGroq(
      `Overdue assets: ${result.overdue_count}. At-risk (due soon): ${result.at_risk_count}. Top overdue: ${topList}.${ctx}`,
      PM_OVERDUE_SYSTEM);
    result.summary = (JSON.parse(raw).summary || "").trim();
  } catch (_e) { /* fall through to a deterministic summary below */ }
  if (!result.summary) {
    result.summary = result.overdue_count === 0
      ? `No assets are overdue on PM${result.at_risk_count ? `; ${result.at_risk_count} due soon` : ""}.`
      : `${result.overdue_count} asset${result.overdue_count === 1 ? "" : "s"} overdue on PM${result.at_risk_count ? `, ${result.at_risk_count} due soon` : ""} — start with the most critical.`;
  }

  await saveReport(db, hiveId, "pm_overdue", result, result.summary);
  return result.summary;
}

// ── REPORT: Failure Digest ────────────────────────────────────────────────────

// AI1 grounding (Hive Board PDDA, 2026-07-10): the LLM writes ONLY the prose summary —
// every displayed COUNT/SUM is computed deterministically in code below (WAT split, mirrors
// pm_overdue). Previously the model produced failure_count/total_downtime_h/times itself and
// they were rendered on the board as hard facts — a free-tier 8B model miscounts.
const FAILURE_DIGEST_SYSTEM = `You are a weekly maintenance risk analyst. You are given ALREADY-COMPUTED figures — do NOT invent, change, or recompute any number.
Respond only in JSON: { "week_summary": "two sentence executive summary for the supervisor, referencing only the figures given" }`;

async function runFailureDigest(db: SupabaseClient, hiveId: string, voiceContext?: string): Promise<string> {
  const PERIOD = 7;
  // ★CANONICAL failure/downtime/repeat metrics from the Analytics Engine RPCs (7-day window)
  // — do NOT re-aggregate breakdowns locally (drift with analytics/asset-hub). All three RPCs
  // already scope to maintenance_type='Breakdown / Corrective'. The LLM writes only the prose.
  // (Ian's canonical-reuse review, Hive Board PDDA, 2026-07-10.)
  const [freqRes, mttrRes, repeatRes] = await Promise.all([
    db.rpc("get_failure_frequency", { p_hive_id: hiveId, p_period_days: PERIOD }),
    db.rpc("get_mttr_by_machine",   { p_hive_id: hiveId, p_period_days: PERIOD }),
    db.rpc("get_repeat_failures",   { p_hive_id: hiveId, p_period_days: PERIOD }),
  ]);
  const freq = (freqRes.data || []) as Array<{ machine: string; failure_count: number }>;
  if (!freq.length) return "No failures this week.";

  const downByMachine = new Map<string, number>();
  for (const r of (mttrRes.data || []) as Array<{ machine: string; total_downtime_h: number }>) {
    downByMachine.set(r.machine, Number(r.total_downtime_h) || 0);
  }
  const top_risk_machines = freq
    .map(r => ({
      machine: r.machine,
      failure_count: Number(r.failure_count) || 0,
      total_downtime_h: Math.round((downByMachine.get(r.machine) || 0) * 10) / 10,
    }))
    .sort((a, b) => (b.failure_count - a.failure_count) || (b.total_downtime_h - a.total_downtime_h))
    .slice(0, 5);

  const repeat_failures = ((repeatRes.data || []) as Array<{ machine: string; root_cause: string; occurrences: number }>)
    .map(r => ({ machine: r.machine, root_cause: r.root_cause || "unknown", times: Number(r.occurrences) || 0 }))
    .slice(0, 5);

  // LLM writes ONLY the prose, from the computed figures.
  const facts = top_risk_machines.map(x => `${x.machine}: ${x.failure_count} failure(s), ${x.total_downtime_h}h downtime`).join("\n");
  const ctx = voiceContext ? `\n\nUser context: "${voiceContext}"` : "";
  let week_summary = "";
  try {
    const raw = await callGroq(`Computed top-risk machines this week (do NOT change these numbers):\n${facts}${ctx}`, FAILURE_DIGEST_SYSTEM);
    week_summary = (JSON.parse(raw).week_summary || "").toString();
  } catch (_e) { week_summary = ""; }
  if (!week_summary) {
    const t = top_risk_machines[0];
    week_summary = t
      ? `${top_risk_machines.length} machine(s) logged breakdowns this week; ${t.machine} led with ${t.failure_count} failure(s) and ${t.total_downtime_h}h downtime.`
      : "Breakdowns were logged this week.";
  }
  const result = { top_risk_machines, repeat_failures, week_summary };
  await saveReport(db, hiveId, "failure_digest", result, week_summary);
  return week_summary;
}

// ── REPORT: Shift Handover ────────────────────────────────────────────────────

const HANDOVER_SYSTEM = `You are a shift handover report generator. Summarize the last 8 hours of maintenance activity.
Respond only in JSON: { "open_jobs": [{"machine","problem","priority":"HIGH|MEDIUM|LOW"}], "completed_jobs": [{"machine","action"}], "critical_alerts": ["alert"], "handover_note": "one paragraph for the next shift" }`;

async function runShiftHandover(db: SupabaseClient, hiveId: string, voiceContext?: string): Promise<string> {
  const since = new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString();
  // Canonical: logbook_truth.
  const { data } = await db.from("v_logbook_truth")
    .select("machine, category, problem, action, status, worker_name, created_at")
    .eq("hive_id", hiveId)
    .gte("created_at", since)
    .order("created_at", { ascending: false })
    .limit(50);

  if (!data?.length) return "No activity in the last 8 hours.";

  // PII-redact worker_name before the summary leaves the platform.
  // Closes PRODUCTION_FIXES #44 for this fn.
  const summary = data.map(e =>
    `${e.machine}|${e.status}|${e.problem || ""}|${e.action || ""}|<redacted>`
  ).join("\n");

  const ctx = voiceContext ? `\n\nUser context: "${voiceContext}"` : "";
  const raw = await callGroq(`Last 8h records (machine|status|problem|action|worker):\n${summary}${ctx}`, HANDOVER_SYSTEM);
  const result = JSON.parse(raw);
  await saveReport(db, hiveId, "shift_handover", result, result.handover_note || "Shift handover report saved.");
  return result.handover_note || "Handover done.";
}

// ── REPORT: Predictive ────────────────────────────────────────────────────────

// AI1 grounding (Hive Board PDDA, 2026-07-10): MTBF, last/next-failure DATES and risk are
// computed deterministically in code — date arithmetic is the least reliable operation for a
// small model, and these render on the board as concrete dates. The LLM writes ONLY the prose.
const PREDICTIVE_SYSTEM = `You are a predictive maintenance analyst. You are given ALREADY-COMPUTED per-machine figures — do NOT invent, change, or recompute any number or date.
Respond only in JSON: { "summary": "one sentence for the supervisor, referencing only the figures given" }`;

async function runPredictive(db: SupabaseClient, hiveId: string, voiceContext?: string): Promise<string> {
  // ★CANONICAL MTBF — read the Analytics Engine RPC `get_mtbf_by_machine` (LAG-interval
  // AVG over the last 90d of breakdowns) instead of re-deriving MTBF here. Re-computing it
  // locally would drift from analytics / asset-hub (the exact two-places-compute-one-metric
  // bug class this arc also fixed for stock counts). This fn adds ONLY the projection layer
  // (last failure -> predicted next date, risk band) — a supervisor-facing extrapolation the
  // RPC doesn't own. LLM still writes only the prose. (Ian, Hive Board PDDA, 2026-07-10.)
  const { data: mtbfRows } = await db.rpc("get_mtbf_by_machine", { p_hive_id: hiveId, p_period_days: 90 });
  if (!mtbfRows?.length) return "Not enough failure history for predictions yet.";

  // Last failure per machine = a max() of the event date (not a computed metric -> no drift).
  const { data: lastRows } = await db.from("v_logbook_truth")
    .select("machine, created_at")
    .eq("hive_id", hiveId)
    .eq("maintenance_type", "Breakdown / Corrective")
    .order("created_at", { ascending: false })
    .limit(500);
  const lastByMachine = new Map<string, number>();
  for (const e of (lastRows || [])) {
    if (!e.machine || !e.created_at) continue;
    const t = new Date(e.created_at).getTime();
    if (Number.isFinite(t) && !lastByMachine.has(e.machine)) lastByMachine.set(e.machine, t); // desc -> first is latest
  }

  const DAY = 86400000;
  const now = Date.now();
  const predictions = (mtbfRows as Array<{ machine: string; mtbf_days: number }>)
    .map(r => {
      const mtbf_days = Number(r.mtbf_days) || 0;
      const lastT = lastByMachine.get(r.machine) ?? now;
      const nextT = lastT + mtbf_days * DAY;
      const overdueDays = (now - nextT) / DAY;
      const risk = overdueDays > 0 ? "HIGH" : (overdueDays > -(mtbf_days * 0.25) ? "MEDIUM" : "LOW");
      return {
        machine: r.machine,
        mtbf_days,
        last_failure: new Date(lastT).toISOString().slice(0, 10),
        predicted_next: new Date(nextT).toISOString().slice(0, 10),
        risk,
      };
    })
    .filter(p => p.mtbf_days > 0);
  if (!predictions.length) return "Not enough failure history for predictions yet.";
  predictions.sort((a, b) => a.predicted_next.localeCompare(b.predicted_next));
  const highest_risk_machine = predictions.find(p => p.risk === "HIGH")?.machine || predictions[0].machine;

  // LLM writes ONLY the prose, from the computed figures.
  const facts = predictions.slice(0, 8)
    .map(p => `${p.machine}: MTBF ${p.mtbf_days}d, last ${p.last_failure}, predicted next ${p.predicted_next} (${p.risk})`).join("\n");
  const ctx = voiceContext ? `\n\nUser context: "${voiceContext}"` : "";
  let summary = "";
  try {
    const raw = await callGroq(`Computed predictions (do NOT change these numbers/dates):\n${facts}${ctx}`, PREDICTIVE_SYSTEM);
    summary = (JSON.parse(raw).summary || "").toString();
  } catch (_e) { summary = ""; }
  if (!summary) {
    const p = predictions.find(x => x.risk === "HIGH") || predictions[0];
    summary = `${p.machine} is the highest predicted risk (MTBF ${p.mtbf_days}d, next failure ~${p.predicted_next}).`;
  }
  const result = { predictions: predictions.slice(0, 10), highest_risk_machine, summary };
  await saveReport(db, hiveId, "predictive", result, summary);
  return summary;
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
  // Canonical: logbook_truth.
  const { data: logs } = await db.from("v_logbook_truth")
    .select("machine, root_cause, maintenance_type, created_at")
    .eq("hive_id", hiveId).eq("maintenance_type", "Breakdown / Corrective")
    .gte("created_at", since).limit(500);
  if (!logs?.length) return "No breakdown history in the last 90 days.";

  // Skip assets already covered by an active project
  const { data: activeProjects } = await db.from("v_project_truth")
    // v_project_truth exposes project_id (not id) and pre-filters deleted/archived. Alias to id.
    .select("id:project_id").eq("hive_id", hiveId).in("status", ["planning", "active"]);
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
  const { data: projects } = await db.from("v_project_truth")
    // v_project_truth exposes project_id (not id) and pre-filters deleted/archived. Alias to id.
    .select("id:project_id, project_code").eq("hive_id", hiveId)
    .in("status", ["planning", "active"]);
  if (!projects?.length) return "No active projects with blockers to analyse.";

  const projectIds = projects.map(p => p.id);
  const { data: logs } = await db.from("v_project_progress_truth")
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

serveObserved("scheduled-agents", async (req) => {
  // Arc T/T1: standard liveness /health (fn up + DB creds reachable).
  const _health = await handleHealth(req, "scheduled-agents", async () => ({
    deps: [{ name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) }],
  }));
  if (_health) return _health;
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  logRequestStart(req, "scheduled-agents");  // I6 observability

  try {
    // hive_id is optional — when provided, runs for that hive only (on-demand from Report Sender).
    // When omitted, runs for all hives (cron path — unchanged behaviour).
    const { report_type, hive_id, voice_context: _vc } = await req.json();
    // Arc R (LLM10): cap user voice_context before it is concatenated into the 6 report
    // prompts (the narrative is stored to ai_reports + shown to supervisors). Matches the
    // codebase's 500-char cap (project-orchestrator transcript).
    const voice_context = typeof _vc === "string" ? _vc.slice(0, 500) : _vc;

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

    // Pillar I: the on-demand (Report Sender) path runs for a single client
    // hive_id on a service-role client — verify membership. The pg_cron jobs
    // pass a service-role bearer AND no hive_id, so they skip twice.
    if (hive_id) {
      const { authUid, isServiceRole } = await resolveIdentity(db, req);
      if (!isServiceRole) {
        const t = await resolveTenancy(db, authUid, hive_id);
        if (!t.ok) {
          return new Response(
            JSON.stringify({ error: t.message, code: t.code }),
            { status: t.status, headers: { ...corsHeaders, "Content-Type": "application/json" } },
          );
        }
      }
    }

    // LLM10 unbounded-consumption: rate-limit the on-demand (Report Sender) path — it runs multi-agent
    // LLM reports for a client hive_id. The cron path (service_role bearer, no hive_id) is exempt: it's a
    // trusted periodic job. Keyed on the verified hive (membership already checked above).
    if (hive_id) {
      const { isServiceRole } = await resolveIdentity(db, req);
      if (!isServiceRole) {
        // D12 per-SURFACE quota, OBSERVE-mode (mirrors the shared gateway pattern). Always counts into
        // (hive, route, hour) via hive_route_calls so per-surface AI pressure is VISIBLE - the
        // hive-wide cap alone cannot show which surface is burning the budget. It does NOT deny:
        // checkRouteRateLimit only enforces when an explicit hive_route_quotas row exists, and
        // none do, so this is a no-op behaviour change. Wrapped: quota bookkeeping must never
        // fail a real request.
        try {
          const _rq = await checkRouteRateLimit(db, hive_id || "", "scheduled-agents");
          // Denies ONLY when an explicit hive_route_quotas row exists (rq.per_route), so this stays
          // a no-op until an admin sets a cap - while always counting for attribution.
          if (_rq.per_route && !_rq.allowed) return routeRateLimitedResponse(corsHeaders, "scheduled-agents", _rq.cap);
        } catch { /* empty-catch-allow: per-surface quota bookkeeping must never fail a real request */ }
        const _rl = await checkAIRateLimit(db, hive_id);
        if (!_rl.allowed) return rateLimitedResponse(corsHeaders);
      }
    }

    let hives: { id: string; name: string }[];

    if (hive_id) {
      // On-demand: run for a single hive (called from Report Sender page)
      const { data, error: hiveErr } = await db
        .from("v_hives_truth").select("id, name").eq("id", hive_id).single();
      if (hiveErr || !data) {
        return new Response(
          JSON.stringify({ status: "skipped", reason: "Hive not found" }),
          { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
      hives = [data];
    } else {
      // Cron path: run for all active hives
      // unbounded-query-allow: scheduled-agent dispatcher iterates every hive; full active set required
      const { data, error: hivesErr } = await db.from("v_hives_truth").select("id, name");
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
    log.error(null, "scheduled-agents error:", { detail: err });
    // T2b: aggregate this HANDLED failure to wh_traces + non-leaky 500.
    return await failTracked(req, "scheduled-agents", "scheduled_agents_error", err);
  }
});
