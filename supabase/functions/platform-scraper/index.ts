import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { logRequestStart } from "../_shared/logger.ts";

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.38.4";
import { getCorsHeaders } from "../_shared/cors.ts";
import { log } from "../_shared/logger.ts";
// Pillar I (Gateway Spine): verify hive membership before scraping a hive's KPIs.
import { resolveIdentity, resolveTenancy } from "../_shared/tenant-context.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";

// contract: platform-scraper (registered in canonical_agent_contracts migration)

/**
 * Platform Scraper Agent Edge Function (Phase 1)
 *
 * Fetches real-time KPI surface data for voice companion:
 * - Equipment status (running/idle/maintenance/down)
 * - Risk assets (top 3 by failure risk)
 * - PM status (due this week, overdue)
 * - Inventory alerts (low stock, out of stock)
 * - Adoption metrics (active workers, adoption score)
 *
 * Called from voice-handler.js when semantic router classifies
 * a question as "platform" route (status queries).
 *
 * Input:
 *   - hive_id: worker's hive ID
 *   - worker_name: worker name (for logs)
 *
 * Output:
 *   - Prose-friendly summary suitable for voice
 *   - Or error message if query fails (non-fatal)
 */

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders });
  logRequestStart(req, "platform-scraper");  // I6 observability
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  try {
    const { hive_id, worker_name } = await req.json();
    if (!worker_name) {
      return new Response(
        JSON.stringify({ error: "Missing required field: worker_name" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    if (!hive_id) {
      return new Response(
        JSON.stringify({ error: "Missing hive_id" }),
        { status: 400, headers: { "Content-Type": "application/json" } }
      );
    }

    const db = createClient(
      Deno.env.get("SUPABASE_URL") || "",
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || ""
    );

    // Pillar I: scrapes a hive's KPI snapshot scoped by the client hive_id on a
    // service-role client — verify membership. Service-role (internal) skips.
    {
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

    // Fetch all KPI data in parallel
    const [eqStatus, riskAssets, pmStatus, invAlerts, adoption] = await Promise.all([
      _fetchEquipmentStatus(db, hive_id),
      _fetchRiskAssets(db, hive_id),
      _fetchPMStatus(db, hive_id),
      _fetchInventoryAlerts(db, hive_id),
      _fetchAdoption(db, hive_id),
    ]);

    // Build prose-friendly summary
    const parts = [];
    if (eqStatus) parts.push(eqStatus);
    if (riskAssets) parts.push(riskAssets);
    if (pmStatus) parts.push(pmStatus);
    if (invAlerts) parts.push(invAlerts);
    if (adoption) parts.push(adoption);

    const summary = parts.length
      ? parts.join(" ")
      : "No KPI data available right now.";

    return new Response(
      JSON.stringify({
        summary,
        timestamp: new Date().toISOString(),
        hive_id,
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }
    );
  } catch (err) {
    log.error(null, "Platform scraper error:", { detail: err });
    return new Response(
      JSON.stringify({
        error: "Platform scraper failed",
        summary: "I couldn't fetch the latest platform data. Check Analytics for details.",
      }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }
    );
  }
});

// Helper: equipment status (running/idle/maintenance/down)
async function _fetchEquipmentStatus(
  db: any,
  hive_id: string
): Promise<string> {
  try {
    // Group assets by status from v_asset_truth. PostgREST has no server-side
    // GROUP BY/COUNT in select(); the canonical column is `status` (not the
    // never-existed `state`). Fetch the status column and tally client-side.
    const { data, error } = await db
      .from("v_asset_truth")
      .select("status")
      .eq("hive_id", hive_id)
      .not("status", "is", null)
      .limit(500);

    if (error || !data || data.length === 0) return "";

    // Build a summary: "3 running, 1 maintenance, 0 down"
    const stateCounts = data.reduce(
      (acc: Record<string, number>, row: any) => {
        const k = row.status || "unknown";
        acc[k] = (acc[k] || 0) + 1;
        return acc;
      },
      {}
    );

    const parts = [];
    const states = ["running", "idle", "maintenance", "down"];
    for (const state of states) {
      if (stateCounts[state]) {
        parts.push(`${stateCounts[state]} ${state}`);
      }
    }

    return parts.length ? `Equipment right now: ${parts.join(", ")}.` : "";
  } catch (_) {
    return "";
  }
}

// Helper: top 3 assets by risk
async function _fetchRiskAssets(db: any, hive_id: string): Promise<string> {
  try {
    const { data, error } = await db
      .from("v_risk_truth")
      .select("asset_name, risk_level")
      .eq("hive_id", hive_id)
      .order("risk_score", { ascending: false })
      .limit(2);

    if (error || !data || data.length === 0) return "";

    const assets = data.map((r: any) => `${r.asset_name} (${r.risk_level})`);
    return `At-risk assets: ${assets.join(", ")}.`;
  } catch (_) {
    return "";
  }
}

// Helper: PM status (due this week, overdue)
async function _fetchPMStatus(db: any, hive_id: string): Promise<string> {
  // Canonical view: v_pm_scope_items_truth (defined 2026-05-10). Exposes
  // pre-computed is_due_soon (next 14 days) and is_overdue booleans, plus
  // hive_id for scoping. Replaces stale references to v_pm_truth (renamed
  // away during the 2026-05-09/10 PM data-model split; never had a `status`
  // column or `next_due_date` at the PM-asset grain).
  try {
    const [dueSoon, overdue] = await Promise.all([
      db
        .from("v_pm_scope_items_truth")
        .select("scope_item_id", { count: "exact", head: true })
        .eq("hive_id", hive_id)
        .eq("is_due_soon", true),
      db
        .from("v_pm_scope_items_truth")
        .select("scope_item_id", { count: "exact", head: true })
        .eq("hive_id", hive_id)
        .eq("is_overdue", true),
    ]);

    const dueCount    = dueSoon.count ?? 0;
    const overdueCount = overdue.count ?? 0;

    if (dueCount + overdueCount === 0) return "";

    let msg = "";
    if (dueCount > 0) msg += `${dueCount} due this week`;
    if (overdueCount > 0)
      msg += (msg ? ", " : "") + `${overdueCount} overdue`;
    return msg ? `PMs: ${msg}.` : "";
  } catch (_) {
    return "";
  }
}

// Helper: inventory alerts (low, out of stock)
async function _fetchInventoryAlerts(db: any, hive_id: string): Promise<string> {
  try {
    // Canonical view: v_inventory_items_truth (defined 2026-05-10). Exposes
    // pre-computed is_low_stock and is_out_of_stock booleans plus hive_id
    // for scoping. Replaces stale references to v_inventory_truth (never
    // existed under that name; the canonical bakes in the threshold math
    // that was duplicated across consumers).
    const [low, out] = await Promise.all([
      db
        .from("v_inventory_items_truth")
        .select("id", { count: "exact", head: true })
        .eq("hive_id", hive_id)
        .eq("is_low_stock", true),
      db
        .from("v_inventory_items_truth")
        .select("id", { count: "exact", head: true })
        .eq("hive_id", hive_id)
        .eq("is_out_of_stock", true),
    ]);

    const lowCount = low.count ?? 0;
    const outCount = out.count ?? 0;

    if (lowCount + outCount === 0) return "";

    let msg = "";
    if (lowCount > 0) msg += `${lowCount} low`;
    if (outCount > 0) msg += (msg ? " + " : "") + `${outCount} out`;
    return msg ? `Inventory alerts: ${msg}.` : "";
  } catch (_) {
    return "";
  }
}

// Helper: adoption signal. v_adoption_truth models adoption as RISK
// (risk_tier/risk_score) — there is no active-worker count anywhere in the
// schema, so the old active_workers_week/adoption_score reads always 400'd.
// Surface the latest adoption-risk tier instead.
async function _fetchAdoption(db: any, hive_id: string): Promise<string> {
  try {
    const { data, error } = await db
      .from("v_adoption_truth")
      .select("risk_tier, risk_score, snapshot_date")
      .eq("hive_id", hive_id)
      .order("snapshot_date", { ascending: false })
      .limit(1);

    const row = Array.isArray(data) && data.length ? data[0] : null;
    if (error || !row || !row.risk_tier) return "";

    return `Adoption risk: ${row.risk_tier}.`;
  } catch (_) {
    return "";
  }
}
