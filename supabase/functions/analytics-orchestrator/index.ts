import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
// capability: ai_analytics_synthesis
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { callAI } from "../_shared/ai-chain.ts";
import { logAICost, estimateTokens } from "../_shared/cost-log.ts";
import { redactPII } from "../_shared/redactPII.ts";
import { getCorsHeaders } from "../_shared/cors.ts";
import { checkAIRateLimit, rateLimitedResponse } from "../_shared/rate-limit.ts";
import { validateContract } from "../_shared/validate-contract.ts";

// ── Canonical agent contracts produced by this orchestrator ─────────────────
// All response shapes below are registered in canonical_agent_contracts
// (Tier C). Consumers can read the JSON Schema from there.
// contract: analytics_action_plan_v1     (Phase 4 action plan synthesis)
// contract: next_failure_forecast_v1     (Phase 3 next failure dates)
// contract: parts_stockout_v1            (Phase 3 parts stockout)
// contract: anomaly_baseline_v1          (Phase 3 anomaly baseline)
// contract: parts_spike_v1               (Phase 3 parts consumption spike)
// contract: priority_ranking_v1          (Phase 4 priority ranking)
// (health_score_v1 is produced by batch-risk-scoring, consumed here.)

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

// ── Fetch data from Supabase for the requested phase ─────────────────────────

// ── Dynamic limits — scale with period and team size ─────────────────────────
// Prevents silent data truncation as the hive grows.
// Rule (Performance skill): any metric aggregating >200 rows needs a limit
// that accounts for growth, not a hardcoded cap.


// Gateway-adoption fallback: when called via ai-gateway, body.worker_name
// is `<redacted>` for PII compliance. Derive the real identity from the
// JWT + worker_profiles. Closes PRODUCTION_FIXES #49 JWT-derive track.
async function deriveWorkerFromJWT(
  authedClient: SupabaseClient,
  adminClient: SupabaseClient,
): Promise<string | null> {
  try {
    const { data: { user } } = await authedClient.auth.getUser();
    if (!user) return null;
    const { data: profile } = await adminClient
      .from("worker_profiles")
      .select("display_name")
      .eq("auth_uid", user.id)
      .maybeSingle();
    return profile?.display_name || user.email || null;
  } catch {
    return null;
  }
}

function dynLimit(periodDays: number, maxPerDay: number, hardCap = 5000): number {
  return Math.min(hardCap, Math.max(200, periodDays * maxPerDay));
}

async function fetchDescriptiveData(
  db: ReturnType<typeof createClient>,
  hiveId: string | null,
  workerName: string | null,
  periodDays: number
) {
  const rpc = { p_hive_id: hiveId, p_worker: workerName, p_period_days: periodDays };

  // ── FAST PATH: 5 metrics via Postgres RPC (indexed, instant, no Python needed) ──
  // These replace Python in-memory computation for MTBF/MTTR/Pareto/Frequency/Repeat.
  // Run all 5 in parallel — each executes directly on indexed Postgres.
  const [mtbfRes, mttrRes, freqRes, paretoRes, repeatRes] = await Promise.allSettled([
    db.rpc("get_mtbf_by_machine",   rpc),
    db.rpc("get_mttr_by_machine",   rpc),
    db.rpc("get_failure_frequency", rpc),
    db.rpc("get_downtime_pareto",   rpc),
    db.rpc("get_repeat_failures",   rpc),
  ]);

  // ── RAW DATA: still needed for PM compliance, OEE, parts consumption ─────────
  // These require JSONB access or complex period math — handled by Python.

  // PM assets -> PM completions -> PM scope items (sequential: need asset IDs first).
  // Include `tag_id` (the human asset code, e.g. "PMP-001") because logbook.machine
  // stores that same code. Without tag_id, downstream calcs that join PM data with
  // logbook entries can't bridge the two (PRODUCTION_FIXES #17).
  //
  // Phase 1.2 engine consolidation: hive-mode reads now go through
  // v_pm_compliance_truth (the canonical PM read path), so Analytics and
  // Alert Hub agree on the per-asset PM contract. Solo mode falls back to
  // raw pm_assets because the canonical view is hive-scoped and has no
  // worker_name filter -- the canonical-allow comment documents that.
  let assets: Array<Record<string, string>> = [];
  if (hiveId) {
    const { data } = await db.from("v_pm_compliance_truth")
      .select("pm_asset_id, asset_name, tag_id, category")
      .eq("hive_id", hiveId);
    assets = (data || []).map((a: Record<string, string>) => ({
      id: a.pm_asset_id,
      asset_name: a.asset_name,
      tag_id:     a.tag_id,
      category:   a.category,
    }));
  } else if (workerName) {
    // canonical-allow: solo mode (no hive_id) cannot use hive-scoped v_pm_compliance_truth
    const { data } = await db.from("pm_assets")
      .select("id, asset_name, tag_id, category")
      .eq("worker_name", workerName);
    assets = (data || []) as Array<Record<string, string>>;
  }
  const assetIds = (assets || []).map((a: Record<string, string>) => a.id);

  const completionsLimit = dynLimit(periodDays, 5 * Math.max(assetIds.length, 1) / 30, 5000);
  const completionsQ = db.from("pm_completions")
    .select("asset_id, scope_item_id, completed_at, status, worker_name")
    .eq("status", "done").order("completed_at", { ascending: false })
    .limit(completionsLimit);
  if (assetIds.length) completionsQ.in("asset_id", assetIds);

  const scopeQ = db.from("v_pm_scope_items_truth").select("id, asset_id, frequency, item_text");   // canonical
  if (assetIds.length) scopeQ.in("asset_id", assetIds);

  // OEE: only needs production_output + downtime_hours (small select)
  const oeeQ = db.from("v_logbook_truth")     // canonical: logbook_truth
    .select("machine, maintenance_type, category, problem, root_cause, downtime_hours, status, created_at, closed_at, worker_name, failure_consequence, readings_json, production_output")
    .eq("maintenance_type", "Breakdown / Corrective")
    .gte("created_at", new Date(Date.now() - periodDays * 86400000).toISOString())
    .limit(dynLimit(periodDays, 15));
  if (hiveId) oeeQ.eq("hive_id", hiveId);
  else if (workerName) oeeQ.eq("worker_name", workerName);

  // Transactions: 2× period for spike detection.
  // inventory_transactions has item_id, NOT part_name — embed the part_name
  // from inventory_items via PostgREST so the Python calc finds it directly.
  const sincePrev = new Date(Date.now() - periodDays * 2 * 86400000).toISOString();
  const txnQ = db.from("inventory_transactions")
    .select("qty_change, type, created_at, item:inventory_items(part_name)")
    .eq("type", "use")
    .gte("created_at", sincePrev).limit(dynLimit(periodDays * 2, 20));
  if (hiveId) txnQ.eq("hive_id", hiveId);
  else if (workerName) txnQ.eq("worker_name", workerName);

  const [completionsRes, scopeRes, oeeRes, txnRes] = await Promise.allSettled([
    completionsQ, scopeQ, oeeQ, txnQ,
  ]);

  // Build two lookup maps from the pm_assets fetch:
  //  - assetMap:    UUID → readable asset_name ("Centrifugal Pump 50HP")
  //  - tagIdMap:    UUID → human asset code ("PMP-001") — matches logbook.machine
  const assetMap = Object.fromEntries((assets || []).map((a: Record<string, string>) => [a.id, a.asset_name]));
  const tagIdMap = Object.fromEntries((assets || []).map((a: Record<string, string>) => [a.id, a.tag_id || ""]));

  const rawScope = (scopeRes.status === "fulfilled" ? scopeRes.value.data : null) || [];
  const enrichedScope = rawScope.map((s: Record<string, string>) => ({
    ...s,
    asset_name:   assetMap[s.asset_id] || s.asset_id,
    machine_code: tagIdMap[s.asset_id] || "",
  }));

  // Same enrichment on completions so Python can join completions to logbook by machine_code.
  const rawCompletions = (completionsRes.status === "fulfilled" ? completionsRes.value.data : null) || [];
  const enrichedCompletions = rawCompletions.map((c: Record<string, string>) => ({
    ...c,
    asset_name:   assetMap[c.asset_id] || c.asset_id,
    machine_code: tagIdMap[c.asset_id] || "",
  }));

  // Flatten the embedded part_name so the Python API gets a flat shape it expects.
  const rawTxns = (txnRes.status === "fulfilled" ? txnRes.value.data : null) || [];
  const flatTxns = rawTxns.map((t: Record<string, unknown>) => ({
    qty_change: t.qty_change,
    type:       t.type,
    created_at: t.created_at,
    part_name:  (t.item as Record<string, string> | null)?.part_name || "(unknown part)",
  }));

  return {
    // Pre-computed by Postgres — Python formats these, no heavy computation needed
    precomputed: {
      mtbf:             (mtbfRes.status   === "fulfilled" ? mtbfRes.value.data   : null) || [],
      mttr:             (mttrRes.status   === "fulfilled" ? mttrRes.value.data   : null) || [],
      failure_frequency:(freqRes.status   === "fulfilled" ? freqRes.value.data   : null) || [],
      downtime_pareto:  (paretoRes.status === "fulfilled" ? paretoRes.value.data : null) || [],
      repeat_failures:  (repeatRes.status === "fulfilled" ? repeatRes.value.data : null) || [],
    },
    // Raw data for Python to compute remaining metrics (PM compliance, OEE, parts)
    logbook_entries:   (oeeRes.status === "fulfilled" ? oeeRes.value.data : null) || [],
    pm_completions:    enrichedCompletions,   // includes machine_code
    pm_scope_items:    enrichedScope,         // includes machine_code
    inv_transactions:  flatTxns,
  };
}

async function fetchDiagnosticData(
  db: ReturnType<typeof createClient>,
  hiveId: string | null,
  workerName: string | null,
  periodDays: number
) {
  // Reuse all descriptive data sources plus two new ones
  const base = await fetchDescriptiveData(db, hiveId, workerName, periodDays);

  // Worker skill canonical (Tier A) — one row per (worker, discipline) with
  // MAX(level) aliased as `level` so the Python diagnostic/prescriptive
  // contract stays unchanged. v_worker_skill_truth is hive-scoped, so the
  // separate hive_members lookup is no longer needed.
  const badgesQ = db.from("v_worker_skill_truth")    // canonical: worker_skill_truth
    .select("worker_name, discipline, level:current_level")
    .not("discipline", "is", null)
    .limit(2000);
  if (hiveId) badgesQ.eq("hive_id", hiveId);
  else if (workerName) badgesQ.eq("worker_name", workerName);

  // Engineering calcs — enough to match against all machines (no period filter)
  const calcsQ = db.from("engineering_calcs")
    .select("calc_type, project_name, inputs, results, created_at, worker_name")
    .order("created_at", { ascending: false })
    .limit(1000); // was hardcoded 200 — a hive may have hundreds of calcs
  if (hiveId) calcsQ.eq("hive_id", hiveId);
  else if (workerName) calcsQ.eq("worker_name", workerName);

  const [badgesRes, calcsRes] = await Promise.allSettled([badgesQ, calcsQ]);

  return {
    ...base,
    skill_badges:      (badgesRes.status === "fulfilled" ? badgesRes.value.data : null) || [],
    engineering_calcs: (calcsRes.status  === "fulfilled" ? calcsRes.value.data  : null) || [],
  };
}

async function fetchPredictiveData(
  db: ReturnType<typeof createClient>,
  hiveId: string | null,
  workerName: string | null,
  periodDays: number
) {
  // Reuse descriptive data + add inventory_items for stockout prediction
  const base = await fetchDescriptiveData(db, hiveId, workerName, periodDays);

  // Canonical: inventory_items_truth — bakes in the reorder_point alias the
  // Python analytics code expects, so the PostgREST `:min_qty` rename trick
  // is no longer needed at every call site.
  const invQ = db.from("v_inventory_items_truth")
    .select("part_name, qty_on_hand, reorder_point, unit")
    .limit(2000); // was hardcoded 300 — large warehouses have 500-1000+ parts
  if (hiveId) invQ.eq("hive_id", hiveId).eq("status", "approved");
  else if (workerName) invQ.eq("worker_name", workerName);

  const [invRes] = await Promise.allSettled([invQ]);

  return {
    ...base,
    inventory_items: (invRes.status === "fulfilled" ? invRes.value.data : null) || [],
  };
}

async function fetchPrescriptiveData(
  db: ReturnType<typeof createClient>,
  hiveId: string | null,
  workerName: string | null,
  periodDays: number
) {
  const base = await fetchPredictiveData(db, hiveId, workerName, periodDays);

  // pm_assets -- fetch all (no reasonable hive has > 500 assets).
  // tag_id is the human asset code (e.g. "PMP-001") that logbook.machine
  // stores; needed for the priority calc to look up criticality per machine.
  //
  // Phase 1.2 engine consolidation: hive-mode goes through v_pm_compliance_truth.
  // The view exposes the same columns but keys on pm_asset_id; we remap to
  // `id` so the downstream Python prescriptive payload shape stays stable.
  // Solo mode falls back to raw pm_assets (canonical-allow documented inline).
  const assetsPromise: Promise<Array<Record<string, string>>> = (async () => {
    if (hiveId) {
      const { data } = await db.from("v_pm_compliance_truth")
        .select("pm_asset_id, asset_name, tag_id, category, criticality")
        .eq("hive_id", hiveId)
        .limit(500);
      return (data || []).map((a: Record<string, string>) => ({
        id:          a.pm_asset_id,
        asset_name:  a.asset_name,
        tag_id:      a.tag_id,
        category:    a.category,
        criticality: a.criticality,
      }));
    }
    // canonical-allow: solo mode (no hive_id) cannot use hive-scoped v_pm_compliance_truth
    const q = db.from("pm_assets")
      .select("id, asset_name, tag_id, category, criticality")
      .limit(500);
    if (workerName) q.eq("worker_name", workerName);
    const { data } = await q;
    return (data || []) as Array<Record<string, string>>;
  })();

  // Worker skill canonical (Tier A) — same canonical as Phase 2.
  // v_worker_skill_truth pre-aggregates per (worker, discipline) so
  // calc_technician_assignment + calc_training_gaps see one row per pair.
  const badgesQ = db.from("v_worker_skill_truth")    // canonical: worker_skill_truth
    .select("worker_name, discipline, level:current_level")
    .not("discipline", "is", null)
    .limit(2000);
  if (hiveId) badgesQ.eq("hive_id", hiveId);
  else if (workerName) badgesQ.eq("worker_name", workerName);

  const [assetsRes, badgesRes] = await Promise.allSettled([assetsPromise, badgesQ]);

  return {
    ...base,
    pm_assets:   (assetsRes.status === "fulfilled" ? assetsRes.value : []),
    skill_badges:(badgesRes.status === "fulfilled" ? badgesRes.value.data : null) || [],
  };
}

// ── Canonical risk lookup (Phase 2.2 — Brain reads Engine, not raw data) ─────
// Pulls the top-N at-risk assets from v_risk_truth so the action_plan synthesis
// cites the same risk numbers that Predictive Maintenance, Alert Hub, and
// Asset Hub display. Without this, the AI re-derives "top at-risk" from
// per-phase MTTR / Pareto signals and disagrees with the dashboards.

async function fetchCanonicalRiskTop(
  db: ReturnType<typeof createClient>,
  hiveId: string | null,
  limit = 5,
): Promise<Array<Record<string, unknown>>> {
  if (!hiveId) return [];
  const { data } = await db.from("v_risk_truth")
    .select("asset_name, risk_score, risk_level, mtbf_days, days_until_failure, top_factors, generated_at")
    .eq("hive_id", hiveId)
    .order("risk_score", { ascending: false })
    .limit(limit);
  return (data || []) as Array<Record<string, unknown>>;
}

// Compact serialiser for top_factors so the prompt payload stays cheap.
// Structured factors collapse to "factor (contribution%): explanation",
// legacy string factors pass through. Caps at 3 factors per asset.
function summariseRiskFactors(factors: unknown): string[] {
  if (!Array.isArray(factors)) return [];
  return factors.slice(0, 3).map((f) => {
    if (f && typeof f === "object") {
      const fo = f as Record<string, unknown>;
      const label = String(fo.factor || "").replace(/_/g, " ");
      const pct   = Math.round(((Number(fo.contribution) || 0)) * 100);
      const exp   = fo.explanation ? String(fo.explanation) : "";
      return `${label} (${pct}%)${exp ? ": " + exp : ""}`;
    }
    return String(f).replace(/_/g, " ");
  });
}

// ── Groq synthesis for Prescriptive phase ─────────────────────────────────────

async function callGroqSynthesis(
  fullContext: Record<string, unknown>,
  hiveMembers: string[],
  canonicalRisk: Array<Record<string, unknown>>,
  db: SupabaseClient,
): Promise<string> {
  const memberList = hiveMembers.length > 0
    ? `Your actual team members are: ${hiveMembers.join(", ")}. ONLY use these names — never invent names like John, Bob, or any other person not in this list.`
    : "You do not know the team member names — do not invent names. Refer to workers by their discipline (e.g. 'the Mechanical technician').";

  const systemPrompt = `You are a senior maintenance manager writing a weekly action plan for an industrial team.

Cite the same standards the platform's deterministic calcs use:
  • MTBF / MTTR / Availability → ISO 14224:2016 §9.2-9.4 (note: platform MTBF/MTTR are partial variants — MTBF uses calendar time, MTTR uses total downtime — declare partial when discussing them)
  • OEE → ISO 22400-2:2014 §5.5 (platform ships partial A × Q until ideal cycle time captured per asset)
  • PM compliance → SMRP Best Practices v5.0 Metric 2.1.1 (platform 30-day floor is a coarser approximation)
  • Risk score → SAE JA1011 §5.4 + IEC 60812 (platform-calibrated composite)
  • Sensor anomaly → Z-Score 3-sigma rule

The analytics data covers all 4 ISO/SMRP phases:
  • Descriptive: what happened. MTBF, MTTR, OEE, Pareto of downtime causes
  • Diagnostic: why. failure mode distribution, repeat failures, PM-failure correlation, skill-MTTR correlation
  • Predictive: what's coming. forecasted next failure dates, anomaly readings, stockout risk
  • Prescriptive: what to do. priority ranking, PM optimisation, technician assignment, parts reorder, training gaps

Write a connected plan that DRAWS FROM ALL 4 PHASES, not just prescriptive recommendations. Examples of phase-linked reasoning:
  • "Pump P-103 has the highest failure rate (descriptive) AND its top root cause is bearing wear (diagnostic), so tighten its quarterly bearing inspection (prescriptive)."
  • "Compressor AC-002 is forecast to fail by next Tuesday (predictive), and we have only 1 spare seal kit (prescriptive reorder), so order 2 more this week."
  • "Mechanical category has 3.2h higher MTTR than the team average (diagnostic), so schedule the L4 mechanical tech to mentor L1-L2 workers on bearing replacement procedures."

CANONICAL RISK RULE (Phase 2.2): When the input has a non-empty canonical_risk
array, that array IS the platform's source of truth for "which assets are at
risk and why" — the same list shown on Predictive Maintenance and Alert Hub.
Always anchor at-risk references to canonical_risk[].asset_name and quote a
factor's "explanation" verbatim. Do NOT re-rank assets by MTTR / Pareto /
priority_ranking when canonical_risk disagrees. Cite canonical_risk first;
descriptive / diagnostic / prescriptive top-Ns are corroborating context.

${memberList}
Only reference machines, parts, and workers that appear in the data. Never invent names or equipment not mentioned. Be specific: cite the machine codes (e.g. PMP-001, AC-002), KPI numbers, dates.

Use bullet points. Maximum 250 words.
// contract: analytics_action_plan_v1 (canonical_agent_contracts; consumers: analytics.html, shift-brain.html, hive.html)
Format as JSON:
{
  "summary": "one sentence overview tying together the most important phase signal",
  "this_week": ["action 1 with phase-linked reasoning", "action 2", ...],
  "watch_list": ["machine or part to monitor + WHY (which phase signal flagged it)"]
}`;

  const desc = fullContext.descriptive  as Record<string, unknown> | null;
  const diag = fullContext.diagnostic   as Record<string, unknown> | null;
  const pred = fullContext.predictive   as Record<string, unknown> | null;
  const pres = fullContext.prescriptive as Record<string, unknown> | null;

  // Slim each phase down to its top signals — we don't need the full payload,
  // just the headline data the AI should reason about.
  const promptPayload = {
    // Canonical risk snapshot from v_risk_truth — the same rows Predictive
    // Maintenance and Alert Hub render. Highest priority in the prompt so the
    // model anchors at-risk references here, not on per-phase top-Ns.
    canonical_risk: (canonicalRisk || []).map((r) => ({
      asset_name:         r.asset_name,
      risk_score:         r.risk_score,
      risk_level:         r.risk_level,
      mtbf_days:          r.mtbf_days,
      days_until_failure: r.days_until_failure,
      top_factors:        summariseRiskFactors(r.top_factors),
    })),
    descriptive: desc ? {
      top_downtime: (desc.downtime_pareto as Record<string, unknown>)?.pareto?.slice?.(0,3),
      top_mtbf:     (desc.mtbf as Record<string, unknown>)?.mtbf_by_asset?.slice?.(0,3),
      top_mttr:     (desc.mttr as Record<string, unknown>)?.mttr_by_asset?.slice?.(0,3),
      oee_avg:      (desc.oee  as Record<string, unknown>)?.note ? null
                  : ((desc.oee as Record<string, unknown>)?.average_oee_pct),
    } : null,
    diagnostic: diag ? {
      top_failure_modes: (diag.failure_mode_distribution as Record<string, unknown>)?.distribution?.slice?.(0,3),
      pm_failure_corr:   diag.pm_failure_correlation,
      repeat_failures:   (diag.repeat_failures as Record<string, unknown>)?.repeat_failures?.slice?.(0,3),
      skill_mttr:        (diag.skill_mttr_correlation as Record<string, unknown>)?.by_discipline?.slice?.(0,3),
    } : null,
    predictive: pred ? {
      next_failures:    (pred.next_failure_forecast as Record<string, unknown>)?.predictions?.slice?.(0,3)
                     ?? (pred.failure_forecast       as Record<string, unknown>)?.forecasts?.slice?.(0,3),
      anomalies:        (pred.anomaly_detection as Record<string, unknown>)?.anomalies?.slice?.(0,3),
      stockout_risk:    (pred.stockout_forecast as Record<string, unknown>)?.at_risk?.slice?.(0,3),
    } : null,
    prescriptive: pres ? {
      top_priority:      (pres.priority_ranking as Record<string, unknown>)?.ranking?.slice?.(0,3),
      pm_optimizations:  (pres.pm_interval_optimization as Record<string, unknown>)?.recommendations?.slice?.(0,3),
      open_assignments:  (pres.technician_assignment as Record<string, unknown>)?.assignments?.slice?.(0,3),
      reorder_critical:  (pres.parts_reorder as Record<string, unknown>)?.reorder?.filter?.((r: Record<string, unknown>) => r.urgency === "CRITICAL")?.slice?.(0,3),
      training_gaps:     (pres.training_gaps as Record<string, unknown>)?.gaps?.slice?.(0,2),
    } : null,
    team_members: hiveMembers,
  };

  // Redact worker_name in team_members + open_assignments before the
  // payload leaves the platform. Closes PRODUCTION_FIXES #44 for this fn.
  const prompt = `4-phase analytics results:\n${JSON.stringify(redactPII(promptPayload), null, 2)}`;

  try {
    const raw = await callAI(prompt, { systemPrompt, temperature: 0.3, maxTokens: 800, jsonMode: true });
    if (raw && raw !== "{}") {
      const parsed = JSON.parse(raw);
      // Tier C contract enforcement — refuse to ship action plan with the
      // wrong shape rather than silently render wrong fields on the dashboard.
      const v = await validateContract(db, "analytics_action_plan_v1", parsed);
      if (!v.ok) {
        console.error("[analytics-orchestrator] action_plan_v1 contract violation:", v.errors);
        // One LLM retry with the error as a steering hint — cheap, often
        // recovers from a single hallucinated key rename.
        const fixPrompt =
          `Previous response failed the analytics_action_plan_v1 contract: ${JSON.stringify(v.errors)}\n` +
          `Re-emit valid JSON matching exactly: { "summary": string, "this_week": string[], "watch_list": string[] }\n` +
          `Same data, corrected shape only.`;
        try {
          const retry = await callAI(fixPrompt, { systemPrompt, temperature: 0.1, maxTokens: 800, jsonMode: true });
          const retryParsed = JSON.parse(retry);
          const v2 = await validateContract(db, "analytics_action_plan_v1", retryParsed);
          if (v2.ok) return JSON.stringify(retryParsed);
          // Second strike — log and return empty so the dashboard tile
          // shows "no action plan" instead of a malformed render.
          console.error("[analytics-orchestrator] action_plan_v1 retry also failed:", v2.errors);
          return "{}";
        } catch { return "{}"; }
      }
      return JSON.stringify(parsed);
    }
  } catch { /* fall through */ }
  return "{}";
}

// ── Global filters (criticality, discipline) ─────────────────────────────────
// Applied at the orchestrator level AFTER fetching the raw data. We narrow
// every asset-keyed array (logbook entries, pm_completions, pm_scope_items,
// precomputed RPC results) so downstream Python calcs see a smaller dataset
// and produce filtered output naturally.

function applyFilters(
  data: Record<string, unknown>,
  filters: { criticality?: string | null; discipline?: string | null },
): Record<string, unknown> {
  const crit = (filters.criticality || "all").trim();
  const disc = (filters.discipline  || "all").trim();
  if (crit === "all" && disc === "all") return data;

  // Step 1: build allowedCodes from criticality (machine_code lookup set).
  // Both filters end up contributing to the same set so that asset-keyed
  // arrays (MTBF, MTTR, PM data) are narrowed even when only `discipline`
  // is selected (which is normally a logbook-only field).
  let allowedCodes: Set<string> | null = null;
  if (crit !== "all") {
    const assets = (data.pm_assets as Array<Record<string, unknown>>) || [];
    allowedCodes = new Set(
      assets
        .filter((a) => String(a.criticality || "") === crit)
        .map((a) => String(a.tag_id || "").toLowerCase())
        .filter(Boolean),
    );
  }

  // Step 2: filter logbook by machine code AND/OR discipline
  let logbook = ((data.logbook_entries as Array<Record<string, unknown>>) || []);
  if (allowedCodes) {
    logbook = logbook.filter((l) => allowedCodes!.has(String(l.machine || "").toLowerCase()));
  }
  if (disc !== "all") {
    logbook = logbook.filter((l) => String(l.category || "") === disc);
  }

  // If discipline narrowed the logbook, also restrict allowedCodes to the
  // machine codes that actually appear in the filtered logbook. Without this,
  // precomputed RPCs (MTBF/MTTR/etc) wouldn't be narrowed by discipline.
  if (disc !== "all") {
    const codesFromLogbook = new Set(
      logbook.map((l) => String(l.machine || "").toLowerCase()).filter(Boolean),
    );
    allowedCodes = allowedCodes
      ? new Set([...allowedCodes].filter((c) => codesFromLogbook.has(c)))
      : codesFromLogbook;
  }

  // Step 3: filter PM data by machine_code (criticality only — PM doesn't have discipline)
  const filterByCode = (arr: Array<Record<string, unknown>>) =>
    allowedCodes
      ? arr.filter((r) => allowedCodes!.has(String(r.machine_code || "").toLowerCase()))
      : arr;

  // Step 4: filter precomputed RPCs (they expose `machine` = human code)
  const precomputed = { ...((data.precomputed as Record<string, unknown>) || {}) };
  if (allowedCodes) {
    for (const key of ["mtbf", "mttr", "failure_frequency", "downtime_pareto", "repeat_failures"]) {
      const val = precomputed[key];
      if (Array.isArray(val)) {
        precomputed[key] = val.filter((r: Record<string, unknown>) =>
          allowedCodes!.has(String(r.machine || r.machine_code || "").toLowerCase()),
        );
      }
    }
  }

  // Step 5: filter pm_assets by criticality (so prescriptive priority calc sees narrowed set)
  const pmAssets = crit !== "all"
    ? ((data.pm_assets as Array<Record<string, unknown>>) || []).filter(
        (a) => String(a.criticality || "") === crit,
      )
    : data.pm_assets;

  return {
    ...data,
    logbook_entries: logbook,
    pm_completions:  filterByCode((data.pm_completions  as Array<Record<string, unknown>>) || []),
    pm_scope_items:  filterByCode((data.pm_scope_items  as Array<Record<string, unknown>>) || []),
    pm_assets:       pmAssets,
    precomputed,
  };
}

// ── Call the Python Analytics API ────────────────────────────────────────────

async function callPythonAnalytics(phase: string, inputs: Record<string, unknown>): Promise<Record<string, unknown>> {
  const PYTHON_URL = Deno.env.get("PYTHON_API_URL");

  if (!PYTHON_URL) {
    // Python API not configured — return a structured "unavailable" response
    return {
      error: "Python Analytics API not configured.",
      hint: "Set PYTHON_API_URL in Supabase Edge Function secrets.",
      phase,
    };
  }

  const res = await fetch(`${PYTHON_URL}/analytics`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phase, inputs }),
    signal: AbortSignal.timeout(90000), // 90s timeout — Render free tier cold start can take 50s+
  });

  if (res.status === 404) {
    return { error: `Phase '${phase}' not yet available. The Python API needs to be redeployed with the latest analytics modules.`, phase };
  }
  if (!res.ok) {
    const body = await res.text().catch(() => "no body");
    throw new Error(`Python API ${res.status}: ${body}`);
  }

  return await res.json();
}

// ── Entry point ───────────────────────────────────────────────────────────────

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const { phase, hive_id, worker_name, period_days, criticality, discipline } = await req.json();

    if (!phase) {
      return new Response(
        JSON.stringify({ error: "Missing required field: phase" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const db = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    // Rate-gate FIRST per ai-engineer skill — analytics report path triggers
    // a Groq synthesis call; without the gate a button-mash burns budget.
    const rl = await checkAIRateLimit(db, hive_id || "");
    if (!rl.allowed) return rateLimitedResponse(corsHeaders);

    const periodDays = Number(period_days) || 90;

    // ── phase=report: fan out all 4 phases in parallel + Groq synthesis ──
    // Returns a single bundled payload shaped as
    //   { descriptive:{...}, diagnostic:{...}, predictive:{...}, prescriptive:{...}, action_plan:{...} }
    // Used by analytics-report.html which renders all 4 in one print-ready document.
    if (phase === "report") {
      const [descData, diagData, predData, prescData] = await Promise.all([
        fetchDescriptiveData(db,  hive_id || null, worker_name || null, periodDays),
        fetchDiagnosticData(db,   hive_id || null, worker_name || null, periodDays),
        fetchPredictiveData(db,   hive_id || null, worker_name || null, periodDays),
        fetchPrescriptiveData(db, hive_id || null, worker_name || null, periodDays),
      ]);

      const fp = { criticality, discipline };
      const descIn  = applyFilters(descData,  fp);
      const diagIn  = applyFilters(diagData,  fp);
      const predIn  = applyFilters(predData,  fp);
      const prescIn = applyFilters(prescData, fp);

      const [descR, diagR, predR, prescR] = await Promise.allSettled([
        callPythonAnalytics("descriptive",  { ...descIn,  period_days: periodDays }),
        callPythonAnalytics("diagnostic",   { ...diagIn,  period_days: periodDays }),
        callPythonAnalytics("predictive",   { ...predIn,  period_days: periodDays }),
        callPythonAnalytics("prescriptive", { ...prescIn, period_days: periodDays }),
      ]);

      const descriptive  = descR.status  === "fulfilled" ? descR.value  : { error: String(descR.reason) };
      const diagnostic   = diagR.status  === "fulfilled" ? diagR.value  : { error: String(diagR.reason) };
      const predictive   = predR.status  === "fulfilled" ? predR.value  : { error: String(predR.reason) };
      const prescriptive = prescR.status === "fulfilled" ? prescR.value : { error: String(prescR.reason) };

      // Tier E canonical OEE: hive-scoped reads come from get_oee_by_machine RPC
      // (formula oee_iso_22400 / oee_iso_22400_partial). RPC returns one row
      // per machine with availability_pct / performance_pct / quality_pct /
      // oee_pct / is_partial. Override the Python silo result so analytics +
      // asset-hub + reliability workbench all see the same number. Solo mode
      // keeps the Python calc since the RPC is hive-scoped.
      if (hive_id && descriptive && typeof descriptive === "object" && !(descriptive as { error?: unknown }).error) {
        try {
          const { data: oeeRows, error: oeeErr } = await db.rpc("get_oee_by_machine", {
            p_hive_id:     hive_id,
            p_period_days: periodDays,
          });
          if (!oeeErr && Array.isArray(oeeRows)) {
            const validOee = oeeRows.filter((r: Record<string, unknown>) => r.oee_pct !== null);
            const avgOee = validOee.length
              ? validOee.reduce((s: number, r: Record<string, unknown>) => s + Number(r.oee_pct), 0) / validOee.length
              : null;
            const isPartialAny = oeeRows.some((r: Record<string, unknown>) => r.is_partial === true);
            (descriptive as Record<string, unknown>).oee = {
              oee_by_asset:    oeeRows,
              assets_tracked:  oeeRows.length,
              average_oee_pct: avgOee !== null ? Math.round(avgOee * 10) / 10 : null,
              standard:        isPartialAny
                ? "ISO 22400-2:2014 — partial (Availability × Quality) where ideal cycle time not captured"
                : "ISO 22400-2:2014 — full (Availability × Performance × Quality)",
              formula_id:      isPartialAny ? "oee_iso_22400_partial" : "oee_iso_22400",
              source:          "RPC get_oee_by_machine",
            };
          }
        } catch (_e) { /* RPC failure: keep Python calc as fallback */ }
      }

      // Optional Groq synthesis — only if prescriptive succeeded
      let actionPlan = null;
      if (prescR.status === "fulfilled" && !(prescriptive as { error?: unknown }).error) {
        let hiveMembers: string[] = [];
        if (hive_id) {
          const { data: members } = await db.from("hive_members")
            .select("worker_name").eq("hive_id", hive_id).eq("status", "active");
          hiveMembers = (members || []).map((m: Record<string, string>) => m.worker_name).filter(Boolean);
        } else if (worker_name) {
          hiveMembers = [worker_name];
        }
        try {
          const canonicalRisk = await fetchCanonicalRiskTop(db, hive_id || null, 5);
          const raw = await callGroqSynthesis(
            { descriptive, diagnostic, predictive, prescriptive },
            hiveMembers,
            canonicalRisk,
            db,
          );
          actionPlan = JSON.parse(raw);
        } catch (_e) { actionPlan = null; }
      }

      // Tier C contract enforcement on Python-sourced brain outputs.
      // Each phase carries its own top-level contract; we validate the
      // payload and log violations but do not fail the report so a single
      // contract drift doesn't black out the whole 4-phase render.
      // Map: phase key -> { sub_key -> contract_id }. Sub_keys are the
      // exact field names the Python phase returns at top level.
      const PHASE_CONTRACTS: Record<string, Record<string, string>> = {
        predictive: {
          next_failure_dates:        "next_failure_forecast_v1",
          parts_stockout:            "parts_stockout_v1",
          anomaly_baseline:          "anomaly_baseline_v1",
          parts_consumption_spike:   "parts_spike_v1",
        },
        prescriptive: {
          priority_ranking:          "priority_ranking_v1",
        },
      };
      for (const [phaseKey, contracts] of Object.entries(PHASE_CONTRACTS)) {
        const phaseObj = (phaseKey === "predictive" ? predictive : prescriptive) as Record<string, unknown> | null;
        if (!phaseObj) continue;
        for (const [subKey, contractId] of Object.entries(contracts)) {
          const sub = phaseObj[subKey];
          if (!sub) continue;
          const v = await validateContract(db, contractId, sub);
          if (!v.ok) {
            console.error(`[analytics-orchestrator] ${contractId} contract violation on ${phaseKey}.${subKey}:`, v.errors);
            (phaseObj[subKey] as Record<string, unknown>)._contract_violation = v.errors;
          }
        }
      }

      const bundled = {
        phase: "report",
        hive_id:     hive_id || null,
        worker_name: worker_name || null,
        period_days: periodDays,
        generated_at: new Date().toISOString(),
        descriptive,
        diagnostic,
        predictive,
        prescriptive,
        ...(actionPlan ? { action_plan: actionPlan } : {}),
      };

      return new Response(
        JSON.stringify(bundled),
        { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Fetch the right data for the requested phase
    let data: Record<string, unknown> = {};

    if (phase === "descriptive") {
      data = await fetchDescriptiveData(db, hive_id || null, worker_name || null, periodDays);
    } else if (phase === "diagnostic") {
      data = await fetchDiagnosticData(db, hive_id || null, worker_name || null, periodDays);
    } else if (phase === "predictive") {
      data = await fetchPredictiveData(db, hive_id || null, worker_name || null, periodDays);
    } else if (phase === "prescriptive") {
      data = await fetchPrescriptiveData(db, hive_id || null, worker_name || null, periodDays);
    }

    // Apply optional global filters (criticality + discipline) before sending
    // to Python. Narrows every asset-keyed array consistently.
    data = applyFilters(data, { criticality, discipline });

    // Send to Python API for computation
    const results = await callPythonAnalytics(phase, {
      ...data,
      period_days: periodDays,
    });

    // For prescriptive phase — add Groq synthesis as action plan.
    // The synthesis now reasons across ALL 4 phases (descriptive/diagnostic/
    // predictive/prescriptive), not just prescriptive recommendations. We
    // already have the loaded `data` in scope; fan out to Python for the
    // other 3 phases in parallel using the same input shape.
    let groqSynthesis = null;
    if (phase === "prescriptive" && !results.error) {
      let hiveMembers: string[] = [];
      if (hive_id) {
        const { data: members } = await db.from("hive_members")
          .select("worker_name").eq("hive_id", hive_id).eq("status", "active");
        hiveMembers = (members || []).map((m: Record<string, string>) => m.worker_name).filter(Boolean);
      } else if (worker_name) {
        hiveMembers = [worker_name];
      }

      const [descRes, diagRes, predRes] = await Promise.allSettled([
        callPythonAnalytics("descriptive", data),
        callPythonAnalytics("diagnostic",  data),
        callPythonAnalytics("predictive",  data),
      ]);
      const fullContext = {
        descriptive:  descRes.status === "fulfilled" ? descRes.value : null,
        diagnostic:   diagRes.status === "fulfilled" ? diagRes.value : null,
        predictive:   predRes.status === "fulfilled" ? predRes.value : null,
        prescriptive: results,
      };

      const canonicalRisk = await fetchCanonicalRiskTop(db, hive_id || null, 5);
      const raw = await callGroqSynthesis(fullContext, hiveMembers, canonicalRisk, db);
      try { groqSynthesis = JSON.parse(raw); } catch { groqSynthesis = null; }
    }

    // Tier C: validate Python-sourced contracts on the requested phase.
    // Same map as the bundled report path; non-blocking — annotate the
    // sub-payload with a _contract_violation key so consumers can detect
    // and the dashboard can fall back to a safe render.
    const PHASE_CONTRACT_MAP: Record<string, Record<string, string>> = {
      predictive: {
        next_failure_dates:      "next_failure_forecast_v1",
        parts_stockout:          "parts_stockout_v1",
        anomaly_baseline:        "anomaly_baseline_v1",
        parts_consumption_spike: "parts_spike_v1",
      },
      prescriptive: {
        priority_ranking:        "priority_ranking_v1",
      },
    };
    const phaseContracts = PHASE_CONTRACT_MAP[phase];
    if (phaseContracts) {
      for (const [subKey, contractId] of Object.entries(phaseContracts)) {
        const sub = (results as Record<string, unknown>)[subKey];
        if (!sub) continue;
        const v = await validateContract(db, contractId, sub);
        if (!v.ok) {
          console.error(`[analytics-orchestrator] ${contractId} violation on ${phase}.${subKey}:`, v.errors);
          (sub as Record<string, unknown>)._contract_violation = v.errors;
        }
      }
    }

    // Attach metadata
    const response = {
      phase,
      hive_id:     hive_id || null,
      worker_name: worker_name || null,
      period_days: periodDays,
      generated_at: new Date().toISOString(),
      ...results,
      ...(groqSynthesis ? { action_plan: groqSynthesis } : {}),
    };

    return new Response(
      JSON.stringify(response),
      { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );

  } catch (err) {
    console.error("analytics-orchestrator error:", err);
    return new Response(
      JSON.stringify({ error: err instanceof Error ? err.message : String(err) }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
