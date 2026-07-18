import { serveObserved, failTracked } from "../_shared/observability.ts";
import { handleHealth } from "../_shared/health.ts";

import { logRequestStart } from "../_shared/logger.ts";

// contract-allow: produces parts staging plan; future Tier C: parts_staging_plan_v1
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";
import { log } from "../_shared/logger.ts";
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

// ── Predictive Parts Auto-Staging Recommender ────────────────────────────────
// Runs daily after batch-risk-scoring (06:00 UTC). For each high-risk asset
// (risk_score >= 0.7), looks at historical parts_used patterns from logbook
// and recommends parts to pre-stage from inventory.
//
// Rule-based v1: a part is recommended when it appears in >= MIN_HISTORY_HITS
// past corrective records for the same asset AND inventory has stock on hand.
// Confidence = hits / total corrective records for the asset.
//
// Recommendations expire after EXPIRY_DAYS so stale ones do not accumulate.
// Only one active recommendation per (hive, asset) is kept — older pending
// recs for the same pair are marked 'expired' before the new insert.

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

const RISK_FLOOR        = 0.7;     // only flag assets at or above this risk
const MIN_HISTORY_HITS  = 3;       // part must appear in 3+ corrective records
const MIN_CONFIDENCE    = 0.4;     // 40% of historical fixes used this part
const HISTORY_DAYS      = 365;
const EXPIRY_DAYS       = 7;
const MAX_PARTS_PER_REC = 5;       // cap recommendation breadth

serveObserved("parts-staging-recommender", async (req) => {
  // Arc T/T1: standard liveness /health (fn up + DB creds reachable).
  const _health = await handleHealth(req, "parts-staging-recommender", async () => ({
    deps: [{ name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) }],
  }));
  if (_health) return _health;
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  logRequestStart(req, "parts-staging-recommender");  // I6 observability

  // CRON-ONLY: this is a daily all-hives batch (no client hive_id). It must NOT be
  // triggerable by a user — that is an unauthorized expensive all-hives compute
  // (cost-abuse), the same class fixed for batch-risk-scoring. The pg_cron caller
  // sends the service-role key as bearer; any user sends their own JWT.
  const bearer = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "");
  const isService = !!(bearer && SERVICE_KEY && bearer === SERVICE_KEY);
  if (!isService) {
    return new Response(JSON.stringify({ error: "Forbidden: cron-only batch" }), {
      status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  try {
    const db = createClient(SUPABASE_URL, SERVICE_KEY);

    // unbounded-query-allow: parts recommender runs per-hive on schedule; full active-hive set required
    const { data: hives, error: hivesErr } = await db.from("v_hives_truth").select("id, name");
    if (hivesErr) throw new Error(`Hives fetch: ${hivesErr.message}`);
    if (!hives?.length) {
      return new Response(JSON.stringify({ recommended: 0, note: "No hives" }), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const results = await Promise.allSettled(hives.map((h) => recommendForHive(db, h)));
    const ok      = results.filter((r) => r.status === "fulfilled");
    const failed  = results.filter((r) => r.status === "rejected").length;
    const total   = ok.reduce((acc, r) => acc + ((r as PromiseFulfilledResult<{ count: number }>).value.count || 0), 0);

    await db.from("automation_log").insert({
      job_name: "parts-staging-recommender",
      status:   failed === 0 ? "success" : "failed",
      detail:   `Generated ${total} recommendations across ${ok.length}/${hives.length} hives. Failures: ${failed}`,
    }).then(({ error }) => { if (error) log.warn(null, "audit log:", { detail: error.message }); });

    return new Response(
      JSON.stringify({ recommended: total, hives_processed: ok.length, failed }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  } catch (err) {
    // T2b: aggregate this HANDLED failure to wh_traces + non-leaky 500.
    return await failTracked(req, "parts-staging-recommender", "parts_staging_recommender_error", err);
  }
});

async function recommendForHive(
  db: ReturnType<typeof createClient>,
  hive: { id: string; name: string }
) {
  const hiveId = hive.id;
  const cutoff = new Date(Date.now() - HISTORY_DAYS * 86400000).toISOString();

  // ── 1. Top-risk assets (canonical: v_risk_truth, latest per asset already deduped) ──
  const { data: riskRows, error: riskErr } = await db
    .from("v_risk_truth")
    .select("asset_id, asset_name, risk_score, top_factors, generated_at")
    .eq("hive_id", hiveId)
    .gte("risk_score", RISK_FLOOR);

  if (riskErr) throw new Error(`risk scores: ${riskErr.message}`);
  if (!riskRows?.length) return { hive_id: hiveId, count: 0, note: "No high-risk assets" };

  // View is DISTINCT ON (hive_id, asset_name) so no dedup needed.
  const targets = riskRows;

  // ── 2. Historical corrective records for those assets ──────────────────────
  const machineNames = targets.map((t) => t.asset_name);
  const { data: logbook, error: logErr } = await db
    .from("v_logbook_truth")
    .select("machine, maintenance_type, root_cause, parts_used, created_at")
    .eq("hive_id", hiveId)
    .in("machine", machineNames)
    .gte("created_at", cutoff);

  if (logErr) throw new Error(`logbook: ${logErr.message}`);

  // ── 3. Current inventory (canonical: inventory_items_truth) ────────────────
  const { data: inventory, error: invErr } = await db
    .from("v_inventory_items_truth")
    .select("id, part_name, part_number, qty_on_hand, status")
    .eq("hive_id", hiveId)
    .eq("status", "approved");

  if (invErr) throw new Error(`inventory: ${invErr.message}`);

  const invByName = new Map<string, { id: string; part_name: string; qty_on_hand: number }>();
  for (const item of inventory || []) {
    const key = String(item.part_name || "").trim().toLowerCase();
    if (key) invByName.set(key, item);
  }

  // ── 4. For each target asset, build recommendations ────────────────────────
  const newRecs: Array<Record<string, unknown>> = [];
  const expirePairs: Array<{ asset: string }> = [];

  for (const target of targets) {
    const assetLogs = (logbook || []).filter(
      (e) => e.machine === target.asset_name &&
             /corrective|breakdown/i.test(String(e.maintenance_type || ""))
    );
    if (assetLogs.length < MIN_HISTORY_HITS) continue;

    // Aggregate parts_used across all corrective logs
    const partHits = new Map<string, { hits: number; qtyTotal: number; sample: string }>();
    for (const log of assetLogs) {
      const parts = Array.isArray(log.parts_used) ? log.parts_used : [];
      for (const p of parts) {
        const name = String(p?.name || p?.part_name || "").trim();
        if (!name) continue;
        const key = name.toLowerCase();
        const qty = Number(p?.qty || p?.quantity || 1) || 1;
        const cur = partHits.get(key) || { hits: 0, qtyTotal: 0, sample: name };
        cur.hits += 1;
        cur.qtyTotal += qty;
        partHits.set(key, cur);
      }
    }

    // Filter by frequency + inventory availability
    const candidates: Array<{ item_id: string; part_name: string; qty_avg: number; confidence: number; in_stock: number }> = [];
    for (const [key, stat] of partHits.entries()) {
      const confidence = stat.hits / assetLogs.length;
      if (stat.hits < MIN_HISTORY_HITS) continue;
      if (confidence < MIN_CONFIDENCE) continue;
      const inv = invByName.get(key);
      if (!inv) continue;                   // not in inventory — skip
      if (Number(inv.qty_on_hand) <= 0) continue;
      candidates.push({
        item_id: inv.id,
        part_name: inv.part_name,
        qty_avg: Math.max(1, Math.round(stat.qtyTotal / stat.hits)),
        confidence: Math.round(confidence * 100) / 100,
        in_stock: Number(inv.qty_on_hand),
      });
    }
    if (!candidates.length) continue;

    candidates.sort((a, b) => b.confidence - a.confidence);
    const picked = candidates.slice(0, MAX_PARTS_PER_REC);

    // Most-frequent failure mode (rough — pick mode of root_cause across the assetLogs)
    const causeCount = new Map<string, number>();
    for (const log of assetLogs) {
      const c = String(log.root_cause || "").trim();
      if (!c) continue;
      causeCount.set(c, (causeCount.get(c) || 0) + 1);
    }
    const failureMode = Array.from(causeCount.entries()).sort((a, b) => b[1] - a[1])[0]?.[0] || null;

    const overallConf = Math.round((picked.reduce((s, p) => s + p.confidence, 0) / picked.length) * 100) / 100;

    const rationale =
      `Risk score ${target.risk_score.toFixed(2)} on ${target.asset_name}. ` +
      `${assetLogs.length} corrective records in last ${HISTORY_DAYS}d. ` +
      `${picked.length} parts appear in ${(MIN_CONFIDENCE * 100).toFixed(0)}%+ of past fixes` +
      (failureMode ? ` for failure mode "${failureMode}".` : ".");

    newRecs.push({
      hive_id:       hiveId,
      asset_name:    target.asset_name,
      risk_score:    target.risk_score,
      failure_mode:  failureMode,
      parts:         picked,
      rationale,
      confidence:    overallConf,
      status:        "pending",
      generated_at:  new Date().toISOString(),
      expires_at:    new Date(Date.now() + EXPIRY_DAYS * 86400000).toISOString(),
      model_version: "rules-v1",
    });
    expirePairs.push({ asset: target.asset_name });
  }

  if (!newRecs.length) return { hive_id: hiveId, count: 0, note: "No actionable recs" };

  // ── 5. Expire previous pending recs for the same (hive, asset) pairs ───────
  // Use a single UPDATE with .in() rather than per-row to keep query count low.
  const assetsToExpire = expirePairs.map((p) => p.asset);
  if (assetsToExpire.length) {
    const { error: expErr } = await db
      .from("parts_staging_recommendations")
      .update({ status: "expired" })
      .eq("hive_id", hiveId)
      .eq("status", "pending")
      .in("asset_name", assetsToExpire);
    if (expErr) log.warn(null, `expire prev recs: ${expErr.message}`);
  }

  // ── 6. Insert new recommendations ──────────────────────────────────────────
  const { error: insErr } = await db.from("parts_staging_recommendations").insert(newRecs);
  if (insErr) throw new Error(`insert recs: ${insErr.message}`);

  return { hive_id: hiveId, count: newRecs.length };
}
