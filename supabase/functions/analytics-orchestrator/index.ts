import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

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
  const since = new Date(Date.now() - periodDays * 86400000).toISOString();

  // 1. Logbook — corrective entries for MTBF/MTTR/Pareto/Frequency/Repeat
  // Assume max 15 corrective entries/day for a busy hive → scales with period
  const logbookQ = db.from("logbook")
    .select("machine, maintenance_type, category, root_cause, downtime_hours, status, created_at, closed_at, worker_name, failure_consequence, readings_json, production_output")
    .eq("maintenance_type", "Breakdown / Corrective")
    .gte("created_at", since)
    .order("created_at", { ascending: true })
    .limit(dynLimit(periodDays, 15)); // was hardcoded 500

  if (hiveId) logbookQ.eq("hive_id", hiveId);
  else if (workerName) logbookQ.eq("worker_name", workerName);

  // 2. PM assets — for compliance calculation
  const assetsQ = db.from("pm_assets")
    .select("id, asset_name, category");
  if (hiveId) assetsQ.eq("hive_id", hiveId);
  else if (workerName) assetsQ.eq("worker_name", workerName);

  // 3. PM completions — for compliance and last-done dates
  const { data: assets } = await assetsQ;
  const assetIds = (assets || []).map((a: Record<string, string>) => a.id);

  // Completions: enough to cover the full period per asset (5 tasks/asset/month)
  const completionsLimit = dynLimit(periodDays, 5 * Math.max(assetIds.length, 1) / 30, 5000);
  const completionsQ = db.from("pm_completions")
    .select("asset_id, scope_item_id, completed_at, status, worker_name")
    .eq("status", "done")
    .order("completed_at", { ascending: false })
    .limit(completionsLimit); // was hardcoded 1000
  if (assetIds.length) completionsQ.in("asset_id", assetIds);

  // 4. PM scope items — all tasks for the assets (no period filter needed)
  const scopeQ = db.from("pm_scope_items")
    .select("id, asset_id, frequency, item_text");
  if (assetIds.length) scopeQ.in("asset_id", assetIds);

  // 5. Inventory transactions — for parts consumption rate
  // Assume max 20 use transactions/day across all parts
  const txnQ = db.from("inventory_transactions")
    .select("part_name, qty_change, type, created_at")
    .eq("type", "use")
    .gte("created_at", since)
    .limit(dynLimit(periodDays, 20)); // was hardcoded 500
  if (hiveId) txnQ.eq("hive_id", hiveId);
  else if (workerName) txnQ.eq("worker_name", workerName);

  // Run all queries in parallel
  const [logbookRes, completionsRes, scopeRes, txnRes] = await Promise.allSettled([
    logbookQ, completionsQ, scopeQ, txnQ,
  ]);

  // Enrich scope items with asset_name from assets list
  const assetMap = Object.fromEntries((assets || []).map((a: Record<string, string>) => [a.id, a.asset_name]));
  const rawScope = (scopeRes.status === "fulfilled" ? scopeRes.value.data : null) || [];
  const enrichedScope = rawScope.map((s: Record<string, string>) => ({
    ...s,
    asset_name: assetMap[s.asset_id] || s.asset_id,
  }));

  return {
    logbook_entries:   (logbookRes.status === "fulfilled" ? logbookRes.value.data : null) || [],
    pm_completions:    (completionsRes.status === "fulfilled" ? completionsRes.value.data : null) || [],
    pm_scope_items:    enrichedScope,
    inv_transactions:  (txnRes.status === "fulfilled" ? txnRes.value.data : null) || [],
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

  const invQ = db.from("inventory_items")
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

  // pm_assets — fetch all (no reasonable hive has > 500 assets)
  const assetsQ = db.from("pm_assets")
    .select("id, asset_name, category, criticality")
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

async function callGroqSynthesis(pythonResult: Record<string, unknown>, hiveMembers: string[]): Promise<string> {
  const GROQ_KEY = Deno.env.get("GROQ_API_KEY");
  if (!GROQ_KEY) return "Groq not configured — showing raw analysis results.";

  const GROQ_CHAIN = [
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-3.1-8b-instant",
  ];

  const memberList = hiveMembers.length > 0
    ? `Your actual team members are: ${hiveMembers.join(", ")}. ONLY use these names — never invent names like John, Bob, or any other person not in this list.`
    : "You do not know the team member names — do not invent names. Refer to workers by their discipline (e.g. 'the Mechanical technician').";

  const systemPrompt = `You are a senior maintenance manager. Based on the analytics results provided, write a concise action plan for the maintenance team this week.
${memberList}
Only reference machines, parts, and workers that appear in the data. Never invent names or equipment not mentioned.
Use bullet points. Maximum 200 words.
Format as JSON: { "summary": "one sentence overview", "this_week": ["action 1", "action 2", ...], "watch_list": ["machine or part to monitor"] }`;

  const assignments = (pythonResult.technician_assignment as Record<string, unknown>)?.assignments as Record<string, unknown>[] | undefined;

  const prompt = `Analytics results:\n${JSON.stringify({
    top_priority: (pythonResult.priority_ranking as Record<string, unknown>)?.ranking?.slice?.(0,3),
    pm_optimizations: (pythonResult.pm_interval_optimization as Record<string, unknown>)?.recommendations?.slice?.(0,3),
    open_assignments: assignments?.slice?.(0,3),
    reorder_critical: (pythonResult.parts_reorder as Record<string, unknown>)?.reorder?.filter?.((r: Record<string, unknown>) => r.urgency === "CRITICAL")?.slice?.(0,3),
    training_gaps: (pythonResult.training_gaps as Record<string, unknown>)?.gaps?.slice?.(0,2),
    team_members: hiveMembers,
  }, null, 2)}`;

  for (const model of GROQ_CHAIN) {
    try {
      const res = await fetch("https://api.groq.com/openai/v1/chat/completions", {
        method: "POST",
        headers: { "Authorization": `Bearer ${GROQ_KEY}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          model, temperature: 0.3, max_tokens: 512,
          response_format: { type: "json_object" },
          messages: [
            { role: "system", content: systemPrompt },
            { role: "user",   content: prompt },
          ],
        }),
      });
      if (res.status === 429 || res.status === 413) continue;
      if (!res.ok) break;
      const data = await res.json();
      const text = data.choices?.[0]?.message?.content || "{}";
      const parsed = JSON.parse(text);
      return JSON.stringify(parsed);
    } catch { continue; }
  }
  return "{}";
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
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const { phase, hive_id, worker_name, period_days } = await req.json();

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

    // Send to Python API for computation
    const results = await callPythonAnalytics(phase, {
      ...data,
      period_days: periodDays,
    });

    // For prescriptive phase — add Groq synthesis as action plan
    let groqSynthesis = null;
    if (phase === "prescriptive" && !results.error) {
      // Fetch actual hive member names to prevent Groq from hallucinating worker names
      let hiveMembers: string[] = [];
      if (hive_id) {
        const { data: members } = await db.from("hive_members")
          .select("worker_name").eq("hive_id", hive_id).eq("status", "active");
        hiveMembers = (members || []).map((m: Record<string, string>) => m.worker_name).filter(Boolean);
      } else if (worker_name) {
        hiveMembers = [worker_name];
      }
      const raw = await callGroqSynthesis(results, hiveMembers);
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
