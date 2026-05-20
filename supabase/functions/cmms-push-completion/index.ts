/**
 * cmms-push-completion — Phase 4.1: Outbound push when a job is closed
 *
 * Called fire-and-forget from logbook.html when a worker closes a work order.
 * Finds the matching external_sync record (by hive + machine) and pushes
 * the completion back to the configured CMMS endpoint.
 *
 * POST body: { hive_id, machine, worker_name, actual_hours, closed_at, logbook_id }
 */

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

serve(async (req) => {
  const cors = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });

  try {
    const body = await req.json();
    const { hive_id, machine, worker_name, actual_hours, closed_at, logbook_id } = body;

    if (!hive_id || !machine) {
      return new Response(JSON.stringify({ error: "hive_id and machine are required" }),
        { status: 400, headers: { ...cors, "Content-Type": "application/json" } });
    }

    const db = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    );

    // Find enabled integration config for this hive
    const { data: configs } = await db.from("integration_configs")
      .select("id, system_type, endpoint_url, auth_token")
      .eq("hive_id", hive_id)
      .eq("enabled", true)
      .limit(1);

    if (!configs?.length) {
      return new Response(JSON.stringify({ ok: false, reason: "No active integration config" }),
        { status: 200, headers: { ...cors, "Content-Type": "application/json" } });
    }

    const config     = configs[0];
    const systemType = config.system_type as string;
    const endpoint   = config.endpoint_url as string;
    const authToken  = config.auth_token as string | null;

    if (!endpoint) {
      return new Response(JSON.stringify({ ok: false, reason: "No endpoint_url configured" }),
        { status: 200, headers: { ...cors, "Content-Type": "application/json" } });
    }

    // Find the external_sync row for this machine (most recent work order)
    const { data: syncRows } = await db.from("v_external_sync_truth")
      .select("external_id, status")
      .eq("hive_id", hive_id)
      .eq("entity_type", "work_order")
      .contains("sync_payload", { machine })
      .order("last_synced_at", { ascending: false })
      .limit(1);

    const extId = syncRows?.[0]?.external_id;
    if (!extId) {
      return new Response(JSON.stringify({ ok: false, reason: "No external_sync record found for machine " + machine }),
        { status: 200, headers: { ...cors, "Content-Type": "application/json" } });
    }

    // Build push payload
    const pushPayload = {
      WH_STATUS:        "Closed",
      WH_ACTUAL_HOURS:  actual_hours ?? 0,
      WH_CLOSED_AT:     closed_at ?? new Date().toISOString(),
      WH_COMPLETED_BY:  worker_name ?? "WorkHive",
      WH_LOGBOOK_ID:    logbook_id ?? null,
    };

    // Build the push URL based on system type
    let pushUrl: string;
    if (systemType === "sap_pm") {
      pushUrl = `${endpoint.replace(/\/WorkOrders.*/, "")}/WorkOrders('${extId}')/complete`;
    } else if (systemType === "maximo") {
      pushUrl = endpoint; // Maximo: POST to same OSLC endpoint with updated status
    } else {
      pushUrl = endpoint.replace(/\/work-orders.*/, "") + "/work-orders/complete";
    }

    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (authToken) headers["Authorization"] = authToken.startsWith("Bearer ") ? authToken : `Bearer ${authToken}`;

    const pushRes = await fetch(pushUrl, {
      method: "POST",
      headers,
      body:   JSON.stringify({ ...pushPayload, external_id: extId }),
      signal: AbortSignal.timeout(15000),
    });

    const pushOk = pushRes.ok;

    // Mark external_sync as completed
    if (pushOk) {
      await db.from("external_sync")
        .update({ status: "Closed", last_synced_at: new Date().toISOString(), sync_status: "active" })
        .eq("hive_id", hive_id)
        .eq("external_id", extId);
    }

    // Log to automation_log
    await db.from("automation_log").insert({
      job_name: "cmms-push-completion",
      hive_id,
      status:   pushOk ? "success" : "failed",
      detail:   `Pushed completion for ${extId} (${machine}) to ${systemType}. HTTP ${pushRes.status}.`,
    });

    return new Response(
      JSON.stringify({ ok: pushOk, external_id: extId, system_type: systemType, http_status: pushRes.status }),
      { status: 200, headers: { ...cors, "Content-Type": "application/json" } },
    );

  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return new Response(JSON.stringify({ error: msg }),
      { status: 500, headers: { ...cors, "Content-Type": "application/json" } });
  }
});
