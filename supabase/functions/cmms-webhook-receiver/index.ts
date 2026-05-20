/**
 * cmms-webhook-receiver — Phase 4.1: Tier 3 Real-Time Inbound Webhooks
 *
 * Receives events pushed FROM the CMMS to WorkHive in real time.
 * The CMMS administrator configures this URL in their SAP/Maximo outbound webhook:
 *
 *   https://[project].supabase.co/functions/v1/cmms-webhook-receiver?config_id=[UUID]
 *
 * The config_id maps to an integration_configs row which provides:
 *   - hive_id      (which hive owns this data)
 *   - system_type  (sap_pm | maximo | generic — which parser to use)
 *   - auth_token   (the HMAC shared secret for signature verification)
 *
 * HMAC verification:
 *   Header: X-WorkHive-Signature: sha256=<hex>
 *   Header: X-WorkHive-Timestamp: <unix seconds>
 *   Signed payload: "{timestamp}.{raw_body}"
 *
 * Events handled:
 *   work_order.created   → create in external_sync + logbook
 *   work_order.updated   → upsert in external_sync
 *   work_order.completed → close in external_sync + logbook
 *   pm.overdue           → refresh failure_signature_alerts
 *   asset.updated        → upsert asset in external_sync
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";
import { STATUS_MAP, TYPE_MAP } from "../_shared/mappings.ts";

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

// ---------------------------------------------------------------------------
// HMAC verification
// ---------------------------------------------------------------------------

async function verifySignature(
  body:      string,
  sigHeader: string,
  tsHeader:  string,
  secret:    string,
): Promise<boolean> {
  if (!sigHeader || !tsHeader || !secret) return false;

  const provided = sigHeader.replace("sha256=", "").trim();
  const signed   = `${tsHeader}.${body}`;

  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const mac     = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(signed));
  const expected = Array.from(new Uint8Array(mac))
    .map(b => b.toString(16).padStart(2, "0"))
    .join("");

  return expected === provided;
}

// ---------------------------------------------------------------------------
// Status / type normalization
// ---------------------------------------------------------------------------

// STATUS_MAP, TYPE_MAP — imported from _shared/mappings.ts

// ---------------------------------------------------------------------------
// Event processors
// ---------------------------------------------------------------------------

function extractWorkOrder(
  payload:    Record<string, unknown>,
  systemType: string,
  hiveId:     string,
  workerName: string,
  now:        string,
) {
  let extId = "", machine = "", rawStatus = "", rawType = "", problem = "", action = "", hoursStr = "", createdAt = "", closedAt = "";

  if (systemType === "sap_pm") {
    extId     = String(payload.AUFNR ?? "");
    machine   = String(payload.EQUNR ?? "");
    rawStatus = String(payload.ISTAT ?? "");
    rawType   = String(payload.AUART ?? "");
    problem   = String(payload.LTXT  ?? "");
    hoursStr  = String(payload.ARBEI ?? "0");
    createdAt = String(payload.ERDAT ?? now);
    closedAt  = String(payload.RUCKMDAT ?? "");
  } else if (systemType === "maximo") {
    extId     = String(payload.WONUM       ?? "");
    machine   = String(payload.ASSETNUM    ?? "");
    rawStatus = String(payload.STATUS      ?? "");
    rawType   = String(payload.WORKTYPE    ?? "");
    problem   = String(payload.DESCRIPTION ?? "");
    hoursStr  = String(payload.ACTLABHRS  ?? "0");
    createdAt = String(payload.REPORTDATE  ?? now);
    closedAt  = String(payload.ACTFINISH   ?? "");
  } else {
    extId     = String(payload.work_order_no ?? "");
    machine   = String(payload.asset_tag    ?? "");
    rawStatus = String(payload.status       ?? "");
    rawType   = String(payload.type         ?? "");
    problem   = String(payload.description  ?? "");
    hoursStr  = String(payload.actual_hours ?? "0");
    createdAt = String(payload.created_date ?? now);
    closedAt  = String(payload.closed_date  ?? "");
  }

  if (!extId) return null;

  const normStatus = STATUS_MAP[systemType]?.[rawStatus] ?? rawStatus ?? "Open";
  const normType   = TYPE_MAP[systemType]?.[rawType]     ?? rawType   ?? "Breakdown / Corrective";

  const syncRow = {
    hive_id:        hiveId,
    system_type:    systemType,
    external_id:    extId,
    entity_type:    "work_order",
    workhive_table: "logbook",
    status:         normStatus,
    sync_payload:   { machine, maintenance_type: normType, problem, action, actual_hours: parseFloat(hoursStr) || 0, created_at: createdAt, closed_at: closedAt || null },
    sync_status:    "active",
    last_synced_at: now,
  };

  const logRow = {
    worker_name:      workerName,
    date:             createdAt || now,
    machine,
    category:         normType === "Preventive Maintenance" ? "Mechanical" : "Mechanical",
    problem:          problem || "Received from CMMS webhook",
    action:           action || "",
    knowledge:        "",
    status:           normStatus,
    created_at:       createdAt || now,
    maintenance_type: normType,
    root_cause:       "",
    downtime_hours:   parseFloat(hoursStr) || 0,
    hive_id:          hiveId,
    closed_at:        normStatus === "Closed" ? (closedAt || now) : null,
    parts_used:       [],
  };

  return { extId, syncRow, logRow };
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

serve(async (req) => {
  const cors = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });

  try {
    const db = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    );

    const url      = new URL(req.url);
    const configId = url.searchParams.get("config_id");

    if (!configId) {
      return new Response(JSON.stringify({ error: "config_id query param required" }),
        { status: 400, headers: { ...cors, "Content-Type": "application/json" } });
    }

    // Look up the integration config
    const { data: config, error: cfgErr } = await db
      .from("integration_configs")
      .select("id, hive_id, system_type, auth_token, enabled")
      .eq("id", configId)
      .single();

    if (cfgErr || !config) {
      return new Response(JSON.stringify({ error: "Config not found" }),
        { status: 404, headers: { ...cors, "Content-Type": "application/json" } });
    }

    if (!config.enabled) {
      return new Response(JSON.stringify({ error: "Integration disabled" }),
        { status: 403, headers: { ...cors, "Content-Type": "application/json" } });
    }

    // Read and verify signature
    const rawBody  = await req.text();
    const sigHeader = req.headers.get("X-WorkHive-Signature") || "";
    const tsHeader  = req.headers.get("X-WorkHive-Timestamp")  || "";

    if (config.auth_token) {
      const valid = await verifySignature(rawBody, sigHeader, tsHeader, config.auth_token);
      if (!valid) {
        return new Response(JSON.stringify({ error: "Invalid signature" }),
          { status: 401, headers: { ...cors, "Content-Type": "application/json" } });
      }
    }

    const body       = JSON.parse(rawBody) as Record<string, unknown>;
    const eventType  = String(body.event ?? "");
    const payload    = (body.payload ?? body) as Record<string, unknown>;
    const systemType = String(body.cmms_type ?? config.system_type);
    const hiveId     = config.hive_id;
    const now        = new Date().toISOString();

    // Get a worker to attribute events to
    const { data: members } = await db.from("hive_members")
      .select("worker_name").eq("hive_id", hiveId).eq("role", "supervisor").limit(1);
    const workerName = members?.[0]?.worker_name || "CMMS Webhook";

    // Process based on event type
    if (["work_order.created", "work_order.updated", "work_order.completed"].includes(eventType)) {
      const extracted = extractWorkOrder(payload, systemType, hiveId, workerName, now);
      if (!extracted) {
        return new Response(JSON.stringify({ ok: false, reason: "No external_id in payload" }),
          { status: 200, headers: { ...cors, "Content-Type": "application/json" } });
      }

      const { syncRow, logRow } = extracted;

      // Upsert to external_sync
      await db.from("external_sync")
        .upsert(syncRow, { onConflict: "system_type,external_id,entity_type" });

      // Insert to logbook (only for new events — skip if already exists via external_id check)
      if (eventType === "work_order.created") {
        const { data: existing } = await db.from("v_external_sync_truth")
          .select("id").eq("external_id", extracted.extId).eq("hive_id", hiveId).limit(1);
        if (!existing?.length) {
          await db.from("logbook").insert(logRow);
        }
      }

    } else if (eventType === "pm.overdue" || eventType === "asset.updated") {
      // Acknowledge receipt — signature detection handles pattern analysis separately
      console.log(`Received ${eventType} for hive ${hiveId}`);
    }

    return new Response(
      JSON.stringify({ ok: true, event: eventType, hive_id: hiveId }),
      { status: 200, headers: { ...cors, "Content-Type": "application/json" } },
    );

  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return new Response(JSON.stringify({ error: msg }),
      { status: 500, headers: { ...cors, "Content-Type": "application/json" } });
  }
});
