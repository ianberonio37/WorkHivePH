import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { callAI } from "../_shared/ai-chain.ts";

// Allow specific origin in production; use env var ALLOWED_ORIGIN to override (e.g. for local dev)
const ORIGIN = Deno.env.get("ALLOWED_ORIGIN") || "https://workhiveph.com";
const corsHeaders = {
  "Access-Control-Allow-Origin": ORIGIN,
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

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

async function runPMOverdue(db: SupabaseClient, hiveId: string): Promise<string> {
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

  const raw = await callGroq(`Assets (name|category|last_pm):\n${summary}`, PM_OVERDUE_SYSTEM);
  const result = JSON.parse(raw);
  await saveReport(db, hiveId, "pm_overdue", result, result.summary || "PM overdue check complete.");
  return result.summary || "PM check done.";
}

// ── REPORT: Failure Digest ────────────────────────────────────────────────────

const FAILURE_DIGEST_SYSTEM = `You are a weekly maintenance risk analyst. Analyze this week's failure records.
Respond only in JSON: { "top_risk_machines": [{"machine","failure_count","total_downtime_h"}], "repeat_failures": [{"machine","root_cause","times"}], "week_summary": "two sentence executive summary for the supervisor" }`;

async function runFailureDigest(db: SupabaseClient, hiveId: string): Promise<string> {
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

  const raw = await callGroq(`This week's failures (machine|category|root_cause|downtime):\n${summary}`, FAILURE_DIGEST_SYSTEM);
  const result = JSON.parse(raw);
  await saveReport(db, hiveId, "failure_digest", result, result.week_summary || "Failure digest complete.");
  return result.week_summary || "Failure digest done.";
}

// ── REPORT: Shift Handover ────────────────────────────────────────────────────

const HANDOVER_SYSTEM = `You are a shift handover report generator. Summarize the last 8 hours of maintenance activity.
Respond only in JSON: { "open_jobs": [{"machine","problem","priority":"HIGH|MEDIUM|LOW"}], "completed_jobs": [{"machine","action"}], "critical_alerts": ["alert"], "handover_note": "one paragraph for the next shift" }`;

async function runShiftHandover(db: SupabaseClient, hiveId: string): Promise<string> {
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

  const raw = await callGroq(`Last 8h records (machine|status|problem|action|worker):\n${summary}`, HANDOVER_SYSTEM);
  const result = JSON.parse(raw);
  await saveReport(db, hiveId, "shift_handover", result, result.handover_note || "Shift handover report saved.");
  return result.handover_note || "Handover done.";
}

// ── REPORT: Predictive ────────────────────────────────────────────────────────

const PREDICTIVE_SYSTEM = `You are a predictive maintenance analyst. Calculate MTBF per machine and predict next failures.
Respond only in JSON: { "predictions": [{"machine","mtbf_days":number,"last_failure":"YYYY-MM-DD","predicted_next":"YYYY-MM-DD","risk":"HIGH|MEDIUM|LOW"}], "highest_risk_machine": "machine name", "summary": "one sentence for supervisor" }`;

async function runPredictive(db: SupabaseClient, hiveId: string): Promise<string> {
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

  const raw = await callGroq(`Today: ${today}\nFailure history (machine|date):\n${summary}`, PREDICTIVE_SYSTEM);
  const result = JSON.parse(raw);
  await saveReport(db, hiveId, "predictive", result, result.summary || "Predictive analysis complete.");
  return result.summary || "Predictive done.";
}

// ── Entry point ───────────────────────────────────────────────────────────────

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    // hive_id is optional — when provided, runs for that hive only (on-demand from Report Sender).
    // When omitted, runs for all hives (cron path — unchanged behaviour).
    const { report_type, hive_id } = await req.json();

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

    const runners: Record<string, (db: SupabaseClient, hiveId: string) => Promise<string>> = {
      pm_overdue:      runPMOverdue,
      failure_digest:  runFailureDigest,
      shift_handover:  runShiftHandover,
      predictive:      runPredictive,
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
          const summary = await runner(db, hive.id);
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
