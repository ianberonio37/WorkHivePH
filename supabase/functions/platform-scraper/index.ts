import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.38.4";

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
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  try {
    const { hive_id, worker_name } = await req.json();

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
    console.error("Platform scraper error:", err);
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
    // Group assets by state from v_asset_truth
    const { data, error } = await db
      .from("v_asset_truth")
      .select("state, COUNT(*) as count")
      .eq("hive_id", hive_id)
      .not("state", "is", null)
      .group_by("state")
      .execute();

    if (error || !data || data.length === 0) return "";

    // Build a summary: "3 running, 1 maintenance, 0 down"
    const stateCounts = data.reduce(
      (acc: Record<string, number>, row: any) => {
        acc[row.state] = row.count;
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
      .limit(2)
      .execute();

    if (error || !data || data.length === 0) return "";

    const assets = data.map((r: any) => `${r.asset_name} (${r.risk_level})`);
    return `At-risk assets: ${assets.join(", ")}.`;
  } catch (_) {
    return "";
  }
}

// Helper: PM status (due this week, overdue)
async function _fetchPMStatus(db: any, hive_id: string): Promise<string> {
  try {
    const today = new Date().toISOString().slice(0, 10);
    const weekEnd = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000)
      .toISOString()
      .slice(0, 10);

    const [dueSoon, overdue] = await Promise.all([
      db
        .from("v_pm_truth")
        .select("COUNT(*)")
        .eq("hive_id", hive_id)
        .eq("status", "due")
        .gte("next_due_date", today)
        .lt("next_due_date", weekEnd)
        .execute(),
      db
        .from("v_pm_truth")
        .select("COUNT(*)")
        .eq("hive_id", hive_id)
        .eq("status", "overdue")
        .execute(),
    ]);

    const dueCount = dueSoon.data?.[0]?.count || 0;
    const overdueCount = overdue.data?.[0]?.count || 0;

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
    const [low, out] = await Promise.all([
      db
        .from("v_inventory_truth")
        .select("COUNT(*)")
        .eq("hive_id", hive_id)
        .eq("stock_level", "low")
        .execute(),
      db
        .from("v_inventory_truth")
        .select("COUNT(*)")
        .eq("hive_id", hive_id)
        .eq("stock_level", "out")
        .execute(),
    ]);

    const lowCount = low.data?.[0]?.count || 0;
    const outCount = out.data?.[0]?.count || 0;

    if (lowCount + outCount === 0) return "";

    let msg = "";
    if (lowCount > 0) msg += `${lowCount} low`;
    if (outCount > 0) msg += (msg ? " + " : "") + `${outCount} out`;
    return msg ? `Inventory alerts: ${msg}.` : "";
  } catch (_) {
    return "";
  }
}

// Helper: adoption metrics (active workers, score)
async function _fetchAdoption(db: any, hive_id: string): Promise<string> {
  try {
    const { data, error } = await db
      .from("v_adoption_truth")
      .select("active_workers_week, adoption_score")
      .eq("hive_id", hive_id)
      .single()
      .execute();

    if (error || !data) return "";

    const workers = data.active_workers_week || 0;
    if (workers === 0) return "";

    return `Active this week: ${workers} worker${workers !== 1 ? "s" : ""}.`;
  } catch (_) {
    return "";
  }
}
