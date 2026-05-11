import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
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

// ── Batch Risk Scoring Edge Function ──────────────────────────────────────────
// Called daily by pg_cron (05:00 UTC = 13:00 PHT).
// For each active hive: fetches logbook + PM + inventory data, calls Python API
// predictive phase, maps health scores into asset_risk_scores rows.
//
// model_version logic:
//   Python API returns 'ml-v1' when GBM artifact exists, 'rules-v1' otherwise.
//   UI reads model_version from the table — no code change needed when ML activates.

const PYTHON_URL = Deno.env.get("PYTHON_API_URL");
const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });

  try {
    const db = createClient(SUPABASE_URL, SERVICE_KEY);

    // Fetch all hives that have at least one pm_asset (active hives only)
    const { data: hives, error: hivesErr } = await db
      .from("hives")
      .select("id, name");

    if (hivesErr) throw new Error(`Hives fetch: ${hivesErr.message}`);
    if (!hives?.length) {
      return new Response(JSON.stringify({ scored: 0, note: "No hives found" }), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // Score all hives in parallel — allSettled so one failure does not block others
    const results = await Promise.allSettled(
      hives.map((hive) => scoreHive(db, hive))
    );

    const succeeded = results.filter((r) => r.status === "fulfilled").length;
    const failed    = results.filter((r) => r.status === "rejected").length;

    // Write automation log
    await db.from("automation_log").insert({
      job_name: "batch-risk-scoring",
      status:   failed === 0 ? "success" : "failed",
      detail:   `Scored ${succeeded}/${hives.length} hives. Failures: ${failed}`,
    }).then(({ error }) => { if (error) console.warn("audit log:", error.message); });

    return new Response(
      JSON.stringify({ scored: succeeded, failed, total: hives.length }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error("batch-risk-scoring:", msg);
    return new Response(JSON.stringify({ error: msg }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});

async function scoreHive(
  db: ReturnType<typeof createClient>,
  hive: { id: string; name: string }
) {
  const hiveId = hive.id;

  // ── 1. Fetch data for this hive (narrow selects — Data Engineer rule) ────────
  // Phase 5a + Reliability tie-in: also pull asset_nodes (so we can bridge
  // logbook.machine -> asset_nodes.id) plus the canonical reliability views.
  // The two new factors (weibull_wearout, fmea_top_rpn) only fire when an
  // asset has approved reliability data; assets without it score the same as
  // before so we do not artificially deflate neglected equipment.
  const [logRes, assetsRes, txnsRes, invRes, nodesRes, weibullRes, fmeaRes] =
    await Promise.allSettled([
      db.from("v_logbook_truth")     // canonical: logbook_truth
        .select("machine, maintenance_type, category, root_cause, downtime_hours, created_at, status")
        .eq("hive_id", hiveId)
        .order("created_at", { ascending: false })
        .limit(2000),

      db.from("pm_assets")
        .select("id, asset_name, tag_id, category")
        .eq("hive_id", hiveId),

      // inventory_transactions has no part_name column — only item_id (FK
      // to inventory_items). Use a PostgREST embed to surface part_name
      // through the join, matching the pattern in analytics-orchestrator.
      db.from("inventory_transactions")
        .select("qty_change, type, created_at, item:inventory_items(part_name)")
        .eq("hive_id", hiveId)
        .order("created_at", { ascending: false })
        .limit(1000),

      db.from("v_inventory_items_truth")     // canonical
        .select("part_name, qty_on_hand, reorder_point")
        .eq("hive_id", hiveId)
        .limit(500),

      db.from("asset_nodes")
        .select("id, name, tag")
        .eq("hive_id", hiveId)
        .eq("status", "approved")
        .limit(500),

      db.from("v_weibull_truth")
        .select("asset_id, beta, eta_days, failure_pattern")
        .eq("hive_id", hiveId)
        .is("fmea_mode_id", null)
        .limit(500),

      db.from("v_fmea_truth")
        .select("asset_id, rpn, failure_mode")
        .eq("hive_id", hiveId)
        .order("rpn", { ascending: false })
        .limit(2000),
    ]);

  const logbook     = logRes.status === "fulfilled" ? (logRes.value.data || []) : [];
  const assets      = assetsRes.status === "fulfilled" ? (assetsRes.value.data || []) : [];
  const assetIds    = assets.map((a: Record<string, string>) => a.id);
  const asset_nodes = nodesRes.status   === "fulfilled" ? (nodesRes.value.data   || []) : [];
  const weibull_rows= weibullRes.status === "fulfilled" ? (weibullRes.value.data || []) : [];
  const fmea_rows   = fmeaRes.status    === "fulfilled" ? (fmeaRes.value.data    || []) : [];

  // PM data requires asset IDs first (child table pattern — Architect rule)
  const [compsRes, scopeRes] = await Promise.allSettled([
    assetIds.length
      ? db.from("pm_completions")
          .select("asset_id, scope_item_id, completed_at, status")
          .in("asset_id", assetIds)
          .eq("status", "done")
          .eq("hive_id", hiveId)
          .limit(500)
      : Promise.resolve({ data: [] }),

    assetIds.length
      ? db.from("v_pm_scope_items_truth")     // canonical
          .select("id, asset_id, frequency, item_text")
          .in("asset_id", assetIds)
          .limit(500)
      : Promise.resolve({ data: [] }),
  ]);

  const pm_completions = compsRes.status === "fulfilled" ? (compsRes.value.data || []) : [];
  const pm_scope_items = scopeRes.status === "fulfilled" ? (scopeRes.value.data || []) : [];
  // Flatten the embed (item:inventory_items(part_name)) into a flat shape so
  // the Python API receives part_name at the top level, matching the same
  // contract analytics-orchestrator uses.
  const rawTxns = txnsRes.status === "fulfilled" ? (txnsRes.value.data || []) : [];
  const inv_txns = rawTxns.map((t: Record<string, unknown>) => ({
    qty_change: t.qty_change,
    type:       t.type,
    created_at: t.created_at,
    part_name:  (t.item as Record<string, string> | null)?.part_name || "(unknown part)",
  }));
  const inv_items      = invRes.status === "fulfilled"  ? (invRes.value.data  || []) : [];

  if (!logbook.length) return { hive_id: hiveId, skipped: true, reason: "No logbook data" };

  // ── 2. Call Python API for health scores + trend ──────────────────────────────
  let healthScores: Array<Record<string, unknown>> = [];
  let modelVersion = "rules-v1";

  if (PYTHON_URL) {
    try {
      const resp = await fetch(`${PYTHON_URL}/analytics`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        signal:  AbortSignal.timeout(90000), // 90s — Render free tier cold start
        body:    JSON.stringify({
          phase: "predictive",
          inputs: {
            logbook_entries: logbook,
            pm_completions,
            pm_scope_items,
            inv_transactions: inv_txns,
            inventory_items:  inv_items,
            period_days:      90,
          },
        }),
      });

      if (resp.ok) {
        const data = await resp.json();
        const scores = data?.health_scores?.health_scores ?? [];
        healthScores = scores;
        // Python API returns model_version in each prediction row (ml-v1 or rules-v1)
        if (scores.length > 0 && scores[0]?.model_version) {
          modelVersion = scores[0].model_version;
        }
      }
    } catch (err) {
      console.warn(`Python API unavailable for hive ${hiveId}, using inline rules`);
    }
  }

  // ── 3. Fallback / default: TS-native composite scorer (Phase 5a v1) ───────────
  // The Python path stays for ML upgrade (Stage 3 per predictive-analytics
  // skill, after 500+ corrective records per asset class). Until then the
  // rules-v2 composite scorer below is the trustworthy default. It uses the
  // PM and inventory data the previous fallback ignored.
  if (!healthScores.length) {
    // Phase 1.1 engine consolidation: pull MTBF from the canonical RPC instead
    // of recomputing it inline inside the scorer. The RPC (defined in migration
    // 20260428000005) is the single source Analytics uses interactively; calling
    // it here at the 365-day window guarantees Analytics and Predictive read the
    // SAME formula at different windows, not two formulas that happen to agree
    // today. Pre-fetched once per scoreHive call and passed as a map.
    const { data: mtbfRpc } = await db.rpc("get_mtbf_by_machine", {
      p_hive_id:     hiveId,
      p_worker:      null,
      p_period_days: HISTORY_DAYS_DECAY,
    });
    const mtbfByMachine: Record<string, number | null> = {};
    for (const row of (mtbfRpc as Array<Record<string, unknown>> | null) || []) {
      const m = String(row.machine ?? "").trim().toLowerCase();
      const v = row.mtbf_days != null ? Number(row.mtbf_days) : null;
      if (m) mtbfByMachine[m] = (v != null && !isNaN(v)) ? v : null;
    }

    healthScores = buildCompositeScoresV2({
      logbook,
      pm_assets: assets,
      pm_completions,
      asset_nodes,
      weibull_rows,
      fmea_rows,
      mtbf_by_machine: mtbfByMachine,
    });
    modelVersion = "rules-v2";
  }

  if (!healthScores.length) return { hive_id: hiveId, skipped: true, reason: "No assets to score" };

  // ── 4. Map health scores to risk score rows ───────────────────────────────────
  // Phase 5a: top_factors is now a structured array of {factor, weight,
  // contribution, value, explanation} objects when produced by rules-v2.
  // The v_risk_truth view passes top_factors through as jsonb so consumers
  // adapt to whatever shape the writer used.
  const now  = new Date().toISOString();
  const rows = healthScores.map((s) => {
    const health = typeof s.health_score === "number" ? s.health_score : 50;
    const risk_score = Math.round((1 - health / 100) * 1000) / 1000;

    let risk_level: string;
    if (risk_score >= 0.85)      risk_level = "critical";
    else if (risk_score >= 0.70) risk_level = "high";
    else if (risk_score >= 0.40) risk_level = "medium";
    else                         risk_level = "low";

    // Structured top_factors carry the explanation. Fall back to the legacy
    // flat-string shape when the scorer didn't produce structured output
    // (Python path or unknown future writer).
    const structured = (s.top_factors_structured as Array<Record<string, unknown>> | undefined);
    const legacy: string[] = [];
    if (!structured) {
      const comp = (s.components ?? {}) as Record<string, number>;
      if ((s.pm_overdue_factor as number) > 1.5) legacy.push("pm_overdue");
      if ((s.recent_failures  as number) > 2)    legacy.push("high_fault_freq");
      if ((s.repeat_faults    as number) > 0)    legacy.push("repeat_fault");
      if (comp.time_score < 30)                  legacy.push("mtbf_approaching");
    }
    const top_factors = structured && structured.length ? structured : legacy;

    return {
      hive_id:            hiveId,
      asset_name:         String(s.machine ?? "Unknown"),
      risk_score,
      risk_level,
      health_score:       health,
      mtbf_days:          typeof s.mtbf_days === "number" ? s.mtbf_days : null,
      days_until_failure: typeof s.days_until_failure === "number" ? s.days_until_failure : null,
      top_factors,
      components:         (s.components ?? {}) as Record<string, number>,
      model_version:      modelVersion,
      generated_at:       now,
    };
  });

  // ── 5. Write to asset_risk_scores (insert, not upsert — keep history) ─────────
  const { error: insertErr } = await db.from("asset_risk_scores").insert(rows);
  if (insertErr) throw new Error(`Insert failed for hive ${hiveId}: ${insertErr.message}`);

  return { hive_id: hiveId, scored: rows.length, model_version: modelVersion };
}

// ── Composite scorer rules-v2 (Phase 5a v1) ───────────────────────────────────
// Replaces the previous inline fallback. Uses 4 weighted factors with real
// PM and inventory data, time decay on historical failures, and emits
// structured top_factors so the UI (and AI agents) can show WHY a score is
// high without recomputing.
//
// Factors and weights (derived from predictive-analytics skill):
//   PM-overdue           0.30   how overdue is the asset's last PM vs category default frequency
//   Fault-frequency      0.30   recent (30d) vs prior (60d) breakdown count, normalised
//   Time-to-MTBF         0.20   days_since_last_failure vs MTBF (closer to MTBF = higher risk)
//   Repeat-fault         0.20   distinct root_causes recurring within 90d / repeat-threshold
//
// Time decay: failures older than 365d are dropped entirely. Failures within
// the 365d window count fully (Phase 5b will add an exponential weight).
//
// Output adds top_factors_structured: an array of { factor, weight,
// contribution, value, explanation }. The mapper above passes this through
// as the row's top_factors (jsonb).

const W_PM        = 0.30;
const W_FAULT     = 0.30;
const W_MTBF      = 0.20;
const W_REPEAT    = 0.20;
// Reliability boost weights (Phase 5a + R.7 tie-in). These are ADDITIVE — total
// composite weight tops out at 1.55, then the final risk is clamped to [0,1].
// Assets with no Weibull fit / no approved FMEA contribute 0 from these
// factors, so neglected equipment scores the same as before this rewire.
const W_WEIBULL   = 0.15;       // boosts wearout assets (beta > 1)
const W_FMEA      = 0.10;       // boosts assets with high engineer-validated RPN
const HISTORY_DAYS_DECAY = 365;

interface PmAssetRow {
  id?:           string;
  asset_name?:   string;
  category?:     string;
  last_anchor_date?: string | null;
  [k: string]:   unknown;
}

interface PmCompletionRow {
  asset_id?:     string;
  completed_at?: string;
  [k: string]:   unknown;
}

interface AssetNodeRow {
  id?:    string;
  name?:  string | null;
  tag?:   string | null;
}

interface WeibullRow {
  asset_id?:        string;
  beta?:            number | null;
  eta_days?:        number | null;
  failure_pattern?: string | null;
}

interface FmeaRow {
  asset_id?:    string;
  rpn?:         number | null;
  failure_mode?: string | null;
}

interface CompositeInput {
  logbook:          Array<Record<string, unknown>>;
  pm_assets:        PmAssetRow[];
  pm_completions:   PmCompletionRow[];
  asset_nodes?:     AssetNodeRow[];
  weibull_rows?:    WeibullRow[];
  fmea_rows?:       FmeaRow[];
  // Canonical MTBF per machine (lower-cased name -> mtbf_days) from
  // get_mtbf_by_machine RPC, pre-fetched at the 365-day window. Same engine
  // Analytics reads at the user-selected window. When this map is absent or
  // empty (e.g. legacy callers, missing RPC), the scorer falls back to an
  // inline inter-arrival mean of the entries it sees — same formula, just
  // not centralised.
  mtbf_by_machine?: Record<string, number | null>;
}

interface FactorContribution {
  factor:       string;
  weight:       number;
  value:        number;          // raw factor value 0..1 (1 = worst)
  contribution: number;          // weight * value, rounded
  explanation:  string;
}

function buildCompositeScoresV2(input: CompositeInput) {
  const now = Date.now();
  const cutoff = now - HISTORY_DAYS_DECAY * 86400000;

  // Group corrective entries by machine, applying time decay (drop older than 365d).
  const groups: Record<string, Array<Record<string, unknown>>> = {};
  for (const entry of input.logbook) {
    const mtype = String(entry.maintenance_type ?? "");
    if (!/corrective|breakdown/i.test(mtype)) continue;
    const ts = new Date(String(entry.created_at ?? "")).getTime();
    if (isNaN(ts) || ts < cutoff) continue;
    const m = String(entry.machine ?? "Unknown");
    (groups[m] = groups[m] || []).push(entry);
  }

  // Index PM data by asset_name so the PM-overdue factor can read real
  // last_anchor_date / category instead of the previous fixed 50.
  const pmByName: Record<string, PmAssetRow> = {};
  const completionsByAssetId: Record<string, PmCompletionRow[]> = {};
  for (const pa of input.pm_assets) {
    if (pa.asset_name) pmByName[pa.asset_name] = pa;
  }
  for (const pc of input.pm_completions) {
    const k = pc.asset_id || "";
    (completionsByAssetId[k] = completionsByAssetId[k] || []).push(pc);
  }

  // ── Reliability bridges ──────────────────────────────────────────────────────
  // logbook.machine is a free-text string; reliability views key by
  // asset_nodes.id (uuid). Build a name+tag -> asset_id map (lower-cased,
  // trimmed) so per-machine lookups land on the right node.
  const _norm = (s: string | null | undefined) => String(s || "").trim().toLowerCase();
  const assetIdByMachine: Record<string, string> = {};
  for (const n of input.asset_nodes || []) {
    if (!n.id) continue;
    if (n.name) assetIdByMachine[_norm(n.name)] = n.id;
    if (n.tag)  assetIdByMachine[_norm(n.tag)]  = n.id;
  }
  // Latest Weibull fit per asset_id (the canonical view already DISTINCT-ON
  // returns one row per (hive,asset,fmea_mode); we filtered fmea_mode_id is null
  // upstream so this map is single-valued).
  const weibullByAssetId: Record<string, WeibullRow> = {};
  for (const w of input.weibull_rows || []) {
    if (w.asset_id) weibullByAssetId[w.asset_id] = w;
  }
  // Top-RPN approved FMEA mode per asset_id (rows are already RPN-desc-sorted).
  const topFmeaByAssetId: Record<string, FmeaRow> = {};
  for (const f of input.fmea_rows || []) {
    if (!f.asset_id) continue;
    const cur = topFmeaByAssetId[f.asset_id];
    if (!cur || (Number(f.rpn) || 0) > (Number(cur.rpn) || 0)) {
      topFmeaByAssetId[f.asset_id] = f;
    }
  }

  return Object.entries(groups).map(([machine, entries]) => {
    const dates = entries
      .map((e) => new Date(String(e.created_at ?? "")).getTime())
      .filter((d) => !isNaN(d))
      .sort((a, b) => a - b);
    const n = dates.length;
    if (n === 0) return null;

    const daysSinceLast = (now - dates[n - 1]) / 86400000;
    const count30d  = dates.filter((d) => d >= now - 30  * 86400000).length;
    const countPrior60d = dates.filter((d) =>
      d >= now - 90 * 86400000 && d < now - 30 * 86400000,
    ).length;

    // MTBF — read from the canonical get_mtbf_by_machine RPC map when present.
    // Falls back to an inline inter-arrival mean (same formula) only when the
    // map is empty, so legacy callers and the migration window stay correct.
    // Machine name comes through lower-cased so the lookup is case-insensitive,
    // matching the RPC's textual machine grouping.
    let mtbf_days: number | null = null;
    const mtbfMap = input.mtbf_by_machine;
    if (mtbfMap) {
      const mLower = machine.trim().toLowerCase();
      mtbf_days = mtbfMap[mLower] ?? null;
    }
    if (mtbf_days == null && n >= 2) {
      const intervals: number[] = [];
      for (let i = 1; i < n; i++) intervals.push((dates[i] - dates[i - 1]) / 86400000);
      mtbf_days = intervals.reduce((a, b) => a + b, 0) / intervals.length;
    }

    const factors: FactorContribution[] = [];

    // ── Factor 1: PM-overdue ─────────────────────────────────────────────────
    // value = clamp((days_since_last_anchor - 30) / 60, 0, 1). 30d = 0, 90d = 1.
    let pmValue = 0.5;
    let pmExplanation = "No PM data linked to this machine; assumed medium overdue.";
    const pa = pmByName[machine];
    if (pa && pa.last_anchor_date) {
      const anchor = new Date(pa.last_anchor_date).getTime();
      if (!isNaN(anchor)) {
        const daysSincePm = (now - anchor) / 86400000;
        pmValue = Math.max(0, Math.min(1, (daysSincePm - 30) / 60));
        pmExplanation = pmValue >= 1
          ? `Last PM anchor ${Math.round(daysSincePm)} days ago; well past the 90-day overdue threshold.`
          : pmValue === 0
          ? `Last PM anchor ${Math.round(daysSincePm)} days ago; within the 30-day window.`
          : `Last PM anchor ${Math.round(daysSincePm)} days ago; partial overdue.`;
      }
    }
    factors.push({
      factor: "pm_overdue", weight: W_PM, value: pmValue,
      contribution: Math.round(W_PM * pmValue * 1000) / 1000,
      explanation: pmExplanation,
    });

    // ── Factor 2: Fault-frequency-trend ──────────────────────────────────────
    // value = clamp(count30d / max(countPrior60d, 1), 0, 1.5) / 1.5
    // Trending UP (more recent failures than baseline) drives value -> 1.
    const trendRatio = count30d / Math.max(countPrior60d, 1);
    const faultValue = Math.max(0, Math.min(1, trendRatio / 2));
    factors.push({
      factor: "fault_frequency_trend", weight: W_FAULT, value: faultValue,
      contribution: Math.round(W_FAULT * faultValue * 1000) / 1000,
      explanation: count30d === 0
        ? "No corrective entries in the last 30 days."
        : `${count30d} corrective in last 30d vs ${countPrior60d} in prior 60d (ratio ${trendRatio.toFixed(2)}).`,
    });

    // ── Factor 3: Time-to-MTBF ───────────────────────────────────────────────
    // value = clamp(daysSinceLast / mtbf, 0, 1). Closer to MTBF = higher risk.
    let mtbfValue = 0.0;
    let mtbfExplanation = "Not enough failures to compute MTBF (need 2+ within the last 365 days).";
    if (mtbf_days && mtbf_days > 0) {
      mtbfValue = Math.max(0, Math.min(1, daysSinceLast / mtbf_days));
      mtbfExplanation = `MTBF ${Math.round(mtbf_days)}d, ${Math.round(daysSinceLast)}d since last failure (${Math.round(mtbfValue * 100)}% through the window).`;
    }
    factors.push({
      factor: "time_to_mtbf", weight: W_MTBF, value: mtbfValue,
      contribution: Math.round(W_MTBF * mtbfValue * 1000) / 1000,
      explanation: mtbfExplanation,
    });

    // ── Factor 4: Repeat-fault ───────────────────────────────────────────────
    // Count repeat root_causes within last 90 days. value = clamp(repeats / 3, 0, 1).
    const last90 = entries.filter((e) => {
      const ts = new Date(String(e.created_at ?? "")).getTime();
      return !isNaN(ts) && ts >= now - 90 * 86400000;
    });
    const rootCauseCounts: Record<string, number> = {};
    for (const e of last90) {
      const rc = String(e.root_cause ?? "unknown").toLowerCase().trim();
      if (!rc || rc === "unknown") continue;
      rootCauseCounts[rc] = (rootCauseCounts[rc] || 0) + 1;
    }
    const repeats = Object.values(rootCauseCounts).filter((c) => c >= 2).reduce((a, b) => a + b, 0);
    const repeatValue = Math.max(0, Math.min(1, repeats / 3));
    factors.push({
      factor: "repeat_fault", weight: W_REPEAT, value: repeatValue,
      contribution: Math.round(W_REPEAT * repeatValue * 1000) / 1000,
      explanation: repeats === 0
        ? "No repeat root_cause within the last 90 days."
        : `${repeats} repeat root_cause occurrences across ${Object.keys(rootCauseCounts).filter((k) => rootCauseCounts[k] >= 2).length} cause(s).`,
    });

    // ── Factor 5: Weibull wear-out (Reliability Workbench tie-in) ────────────
    // Boost when the latest fit is wear-out (beta > 1). Random / infant fits
    // contribute 0. value = clamp((beta - 1) / 3, 0, 1). beta=4 saturates the
    // 0.15 boost. Skill: predictive-analytics — wear-out is a stronger signal
    // for upcoming failure than fault frequency alone.
    const assetIdForMachine = assetIdByMachine[_norm(machine)];
    const weibullRow = assetIdForMachine ? weibullByAssetId[assetIdForMachine] : undefined;
    const beta = weibullRow ? Number(weibullRow.beta) : NaN;
    let wbValue = 0;
    let wbExplanation = "No Weibull fit on file (Reliability tab > Compute Weibull fit).";
    if (Number.isFinite(beta) && beta > 1) {
      wbValue = Math.max(0, Math.min(1, (beta - 1) / 3));
      const eta = Number(weibullRow?.eta_days);
      const etaTxt = Number.isFinite(eta) ? `, eta=${Math.round(eta)}d` : "";
      wbExplanation = `Weibull beta=${beta.toFixed(2)}${etaTxt} -> wear-out region; hazard rises with age.`;
    } else if (Number.isFinite(beta)) {
      wbExplanation = `Weibull beta=${beta.toFixed(2)} -> ${weibullRow?.failure_pattern || "non-wearout"}; no boost.`;
    }
    factors.push({
      factor: "weibull_wearout", weight: W_WEIBULL, value: wbValue,
      contribution: Math.round(W_WEIBULL * wbValue * 1000) / 1000,
      explanation: wbExplanation,
    });

    // ── Factor 6: FMEA top RPN (engineer-validated risk) ─────────────────────
    // Boost when the asset has an approved FMEA mode with high RPN (1..1000).
    // value = clamp(top_rpn / 500, 0, 1). RPN 500 saturates the 0.10 boost.
    // Approved-only because v_fmea_truth filters to approved rows.
    const fmeaRow = assetIdForMachine ? topFmeaByAssetId[assetIdForMachine] : undefined;
    const topRpn  = fmeaRow ? Number(fmeaRow.rpn) : 0;
    const fmeaValue = Math.max(0, Math.min(1, topRpn / 500));
    const fmeaExplanation = topRpn > 0
      ? `Top approved FMEA RPN ${topRpn} (${fmeaRow?.failure_mode || "unspecified"}).`
      : "No approved FMEA modes for this asset (Reliability tab > Add failure mode).";
    factors.push({
      factor: "fmea_top_rpn", weight: W_FMEA, value: fmeaValue,
      contribution: Math.round(W_FMEA * fmeaValue * 1000) / 1000,
      explanation: fmeaExplanation,
    });

    // ── Aggregate to risk_score 0..1, then health_score 0..100 (inverse) ─────
    const risk = factors.reduce((sum, f) => sum + f.contribution, 0);
    const riskClamped = Math.max(0, Math.min(1, risk));
    const health_score = Math.round((1 - riskClamped) * 100);

    // Sort factors by contribution descending so consumers can render top-N.
    factors.sort((a, b) => b.contribution - a.contribution);

    return {
      machine,
      health_score,
      recent_failures:   count30d,
      repeat_faults:     repeats,
      pm_overdue_factor: pmValue,
      mtbf_days,
      days_until_failure: mtbf_days ? Math.round(mtbf_days - daysSinceLast) : null,
      components: {
        pm_score:      Math.round((1 - pmValue)     * 100),
        fault_score:   Math.round((1 - faultValue)  * 100),
        time_score:    Math.round((1 - mtbfValue)   * 100),
        repeat_score:  Math.round((1 - repeatValue) * 100),
        weibull_score: Math.round((1 - wbValue)     * 100),
        fmea_score:    Math.round((1 - fmeaValue)   * 100),
      },
      top_factors_structured: factors,
    };
  }).filter(Boolean);
}
