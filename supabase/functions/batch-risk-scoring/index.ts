import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";

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
  const [logRes, assetsRes, txnsRes, invRes] = await Promise.allSettled([
    db.from("logbook")
      .select("machine, maintenance_type, category, root_cause, downtime_hours, created_at, status")
      .eq("hive_id", hiveId)
      .order("created_at", { ascending: false })
      .limit(2000),

    db.from("pm_assets")
      .select("id, asset_name, tag_id, category")
      .eq("hive_id", hiveId),

    db.from("inventory_transactions")
      .select("part_name, qty_change, type, created_at")
      .eq("hive_id", hiveId)
      .order("created_at", { ascending: false })
      .limit(1000),

    db.from("inventory_items")
      .select("part_name, qty_on_hand, reorder_point")
      .eq("hive_id", hiveId)
      .limit(500),
  ]);

  const logbook     = logRes.status === "fulfilled" ? (logRes.value.data || []) : [];
  const assets      = assetsRes.status === "fulfilled" ? (assetsRes.value.data || []) : [];
  const assetIds    = assets.map((a: Record<string, string>) => a.id);

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
      ? db.from("pm_scope_items")
          .select("id, asset_id, frequency, item_text")
          .in("asset_id", assetIds)
          .limit(500)
      : Promise.resolve({ data: [] }),
  ]);

  const pm_completions = compsRes.status === "fulfilled" ? (compsRes.value.data || []) : [];
  const pm_scope_items = scopeRes.status === "fulfilled" ? (scopeRes.value.data || []) : [];
  const inv_txns       = txnsRes.status === "fulfilled" ? (txnsRes.value.data || []) : [];
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

  // ── 3. Fallback: inline rules if Python API unavailable ───────────────────────
  if (!healthScores.length) {
    healthScores = buildInlineScores(logbook);
    modelVersion = "rules-v1";
  }

  if (!healthScores.length) return { hive_id: hiveId, skipped: true, reason: "No assets to score" };

  // ── 4. Map health scores to risk score rows ───────────────────────────────────
  const now  = new Date().toISOString();
  const rows = healthScores.map((s) => {
    const health = typeof s.health_score === "number" ? s.health_score : 50;
    // Convert 0-100 health score to 0-1 risk score (inverse)
    const risk_score = Math.round((1 - health / 100) * 1000) / 1000;

    let risk_level: string;
    if (risk_score >= 0.85)      risk_level = "critical";
    else if (risk_score >= 0.70) risk_level = "high";
    else if (risk_score >= 0.40) risk_level = "medium";
    else                         risk_level = "low";

    const top_factors: string[] = [];
    const comp = (s.components ?? {}) as Record<string, number>;
    if ((s.pm_overdue_factor as number) > 1.5) top_factors.push("pm_overdue");
    if ((s.recent_failures  as number) > 2)    top_factors.push("high_fault_freq");
    if ((s.repeat_faults    as number) > 0)    top_factors.push("repeat_fault");
    if (comp.time_score < 30)                  top_factors.push("mtbf_approaching");

    return {
      hive_id:            hiveId,
      asset_name:         String(s.machine ?? "Unknown"),
      risk_score,
      risk_level,
      health_score:       health,
      mtbf_days:          typeof s.mtbf_days === "number" ? s.mtbf_days : null,
      days_until_failure: typeof s.days_until_failure === "number" ? s.days_until_failure : null,
      top_factors,
      components:         comp,
      model_version:      modelVersion,
      generated_at:       now,
    };
  });

  // ── 5. Write to asset_risk_scores (insert, not upsert — keep history) ─────────
  const { error: insertErr } = await db.from("asset_risk_scores").insert(rows);
  if (insertErr) throw new Error(`Insert failed for hive ${hiveId}: ${insertErr.message}`);

  return { hive_id: hiveId, scored: rows.length, model_version: modelVersion };
}

// ── Inline rules engine (fallback when Python API is down) ────────────────────
// Mirrors the 4-component formula from python-api/analytics/predictive.py.
// Not as precise as Python (no PM data), but keeps scores flowing.
function buildInlineScores(logbook: Array<Record<string, unknown>>) {
  const now     = Date.now();
  const groups: Record<string, Array<Record<string, unknown>>> = {};

  for (const entry of logbook) {
    const mtype = String(entry.maintenance_type ?? "");
    if (!/corrective|breakdown/i.test(mtype)) continue;
    const m = String(entry.machine ?? "Unknown");
    (groups[m] = groups[m] || []).push(entry);
  }

  return Object.entries(groups).map(([machine, entries]) => {
    const dates = entries
      .map((e) => new Date(String(e.created_at ?? "")).getTime())
      .filter((d) => !isNaN(d))
      .sort((a, b) => a - b);

    const n = dates.length;
    if (n === 0) return null;

    const daysSinceLast = (now - dates[dates.length - 1]) / 86400000;
    const count30d = dates.filter((d) => d >= now - 30 * 86400000).length;
    const count90d = dates.filter((d) => d >= now - 90 * 86400000).length;

    let mtbf_days: number | null = null;
    if (n >= 2) {
      const intervals = [];
      for (let i = 1; i < dates.length; i++) {
        intervals.push((dates[i] - dates[i - 1]) / 86400000);
      }
      mtbf_days = intervals.reduce((a, b) => a + b, 0) / intervals.length;
    }

    // Fault frequency score: fewer recent faults vs MTBF expectation = healthier
    const faultScore = mtbf_days
      ? Math.max(0, Math.min(100, (1 - (count90d / Math.max(90 / mtbf_days, 1))) * 100))
      : Math.max(0, 100 - count30d * 15);

    // Time-to-failure score (neutral 50 if no MTBF)
    const timeScore = mtbf_days
      ? Math.max(0, Math.min(100, ((mtbf_days - daysSinceLast) / mtbf_days) * 100))
      : 50;

    // No PM data available here — use neutral PM score
    const health_score = Math.round(0.30 * 50 + 0.30 * faultScore + 0.20 * timeScore + 0.20 * 100);

    return {
      machine,
      health_score: Math.max(0, Math.min(100, health_score)),
      recent_failures: count30d,
      repeat_faults: 0,
      pm_overdue_factor: 1.0,
      mtbf_days,
      days_until_failure: mtbf_days ? mtbf_days - daysSinceLast : null,
      components: { pm_score: 50, fault_score: faultScore, time_score: timeScore, repeat_score: 100 },
    };
  }).filter(Boolean);
}
