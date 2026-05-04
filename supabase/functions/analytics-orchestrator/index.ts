import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { callAI } from "../_shared/ai-chain.ts";
import { getCorsHeaders } from "../_shared/cors.ts";

// ── Fetch data from Supabase for the requested phase ─────────────────────────

// ── Dynamic limits — scale with period and team size ─────────────────────────
// Prevents silent data truncation as the hive grows.
// Rule (Performance skill): any metric aggregating >200 rows needs a limit
// that accounts for growth, not a hardcoded cap.

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

  // PM assets → PM completions → PM scope items (sequential: need asset IDs first).
  // Include `tag_id` (the human asset code, e.g. "PMP-001") because logbook.machine
  // stores that same code. Without tag_id, downstream calcs that join PM data with
  // logbook entries can't bridge the two (PRODUCTION_FIXES #17).
  const assetsQ = db.from("pm_assets").select("id, asset_name, tag_id, category");
  if (hiveId) assetsQ.eq("hive_id", hiveId);
  else if (workerName) assetsQ.eq("worker_name", workerName);
  const { data: assets } = await assetsQ;
  const assetIds = (assets || []).map((a: Record<string, string>) => a.id);

  const completionsLimit = dynLimit(periodDays, 5 * Math.max(assetIds.length, 1) / 30, 5000);
  const completionsQ = db.from("pm_completions")
    .select("asset_id, scope_item_id, completed_at, status, worker_name")
    .eq("status", "done").order("completed_at", { ascending: false })
    .limit(completionsLimit);
  if (assetIds.length) completionsQ.in("asset_id", assetIds);

  const scopeQ = db.from("pm_scope_items").select("id, asset_id, frequency, item_text");
  if (assetIds.length) scopeQ.in("asset_id", assetIds);

  // OEE: only needs production_output + downtime_hours (small select)
  const oeeQ = db.from("logbook")
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

  // Skill badges — scales with team size (5 disciplines × 5 levels × N workers)
  const badgesQ = db.from("skill_badges")
    .select("worker_name, discipline, level")
    .limit(2000); // 5 disciplines × 5 levels × 80 workers = 2000 max
  if (hiveId) {
    // Get hive member names first, then fetch their badges
    const { data: members } = await db.from("hive_members")
      .select("worker_name")
      .eq("hive_id", hiveId)
      .eq("status", "active");
    const memberNames = (members || []).map((m: Record<string, string>) => m.worker_name).filter(Boolean);
    if (memberNames.length) badgesQ.in("worker_name", memberNames);
  } else if (workerName) {
    badgesQ.eq("worker_name", workerName);
  }

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

  // The DB column is `min_qty`, but the Python analytics code uses
  // `reorder_point` semantically. Alias min_qty as reorder_point in the
  // PostgREST response so the Python side doesn't have to change.
  const invQ = db.from("inventory_items")
    .select("part_name, qty_on_hand, reorder_point:min_qty, unit")
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

  // pm_assets — fetch all (no reasonable hive has > 500 assets).
  // tag_id is the human asset code (e.g. "PMP-001") that logbook.machine
  // stores; needed for the priority calc to look up criticality per machine.
  const assetsQ = db.from("pm_assets")
    .select("id, asset_name, tag_id, category, criticality")
    .limit(500); // was hardcoded 200
  if (hiveId) assetsQ.eq("hive_id", hiveId);
  else if (workerName) assetsQ.eq("worker_name", workerName);

  // skill_badges — scales with team (5 disciplines × 5 levels × N workers)
  const badgesQ = db.from("skill_badges")
    .select("worker_name, discipline, level")
    .limit(2000); // was hardcoded 500
  if (hiveId) {
    const { data: members } = await db.from("hive_members")
      .select("worker_name").eq("hive_id", hiveId).eq("status", "active");
    const names = (members || []).map((m: Record<string, string>) => m.worker_name).filter(Boolean);
    if (names.length) badgesQ.in("worker_name", names);
  } else if (workerName) {
    badgesQ.eq("worker_name", workerName);
  }

  const [assetsRes, badgesRes] = await Promise.allSettled([assetsQ, badgesQ]);

  return {
    ...base,
    pm_assets:   (assetsRes.status === "fulfilled" ? assetsRes.value.data : null) || [],
    skill_badges:(badgesRes.status === "fulfilled" ? badgesRes.value.data : null) || [],
  };
}

// ── Groq synthesis for Prescriptive phase ─────────────────────────────────────

async function callGroqSynthesis(fullContext: Record<string, unknown>, hiveMembers: string[]): Promise<string> {
  const memberList = hiveMembers.length > 0
    ? `Your actual team members are: ${hiveMembers.join(", ")}. ONLY use these names — never invent names like John, Bob, or any other person not in this list.`
    : "You do not know the team member names — do not invent names. Refer to workers by their discipline (e.g. 'the Mechanical technician').";

  const systemPrompt = `You are a senior maintenance manager writing a weekly action plan for an industrial team.

The analytics data covers all 4 ISO/SMRP phases:
  • Descriptive  — what happened: MTBF, MTTR, OEE, Pareto of downtime causes
  • Diagnostic   — why: failure mode distribution, repeat failures, PM-failure correlation, skill-MTTR correlation
  • Predictive   — what's coming: forecasted next failure dates, anomaly readings, stockout risk
  • Prescriptive — what to do: priority ranking, PM optimisation, technician assignment, parts reorder, training gaps

Write a connected plan that DRAWS FROM ALL 4 PHASES, not just prescriptive recommendations. Examples of phase-linked reasoning:
  • "Pump P-103 has the highest failure rate (descriptive) AND its top root cause is bearing wear (diagnostic), so tighten its quarterly bearing inspection (prescriptive)."
  • "Compressor AC-002 is forecast to fail by next Tuesday (predictive), and we have only 1 spare seal kit (prescriptive reorder), so order 2 more this week."
  • "Mechanical category has 3.2h higher MTTR than the team average (diagnostic) — schedule the L4 mechanical tech to mentor L1-L2 workers on bearing replacement procedures."

${memberList}
Only reference machines, parts, and workers that appear in the data. Never invent names or equipment not mentioned. Be specific: cite the machine codes (e.g. PMP-001, AC-002), KPI numbers, dates.

Use bullet points. Maximum 250 words.
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

  const prompt = `4-phase analytics results:\n${JSON.stringify(promptPayload, null, 2)}`;

  try {
    const raw = await callAI(prompt, { systemPrompt, temperature: 0.3, maxTokens: 800, jsonMode: true });
    if (raw && raw !== "{}") return JSON.stringify(JSON.parse(raw));
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
          const raw = await callGroqSynthesis(
            { descriptive, diagnostic, predictive, prescriptive },
            hiveMembers,
          );
          actionPlan = JSON.parse(raw);
        } catch (_e) { actionPlan = null; }
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

      const raw = await callGroqSynthesis(fullContext, hiveMembers);
      try { groqSynthesis = JSON.parse(raw); } catch { groqSynthesis = null; }
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
