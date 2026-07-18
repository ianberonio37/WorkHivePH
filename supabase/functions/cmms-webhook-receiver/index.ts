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

import { serveObserved, failTracked } from "../_shared/observability.ts";
import { handleHealth } from "../_shared/health.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";
import { log } from "../_shared/logger.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
import { STATUS_MAP, TYPE_MAP, DEFAULT_INVENTORY_FIELD_MAPS } from "../_shared/mappings.ts";

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

  // CMMS-INTEGRATIONS PDDA I6: constant-time compare. Both sides are fixed-length
  // 64-char SHA-256 hex, so `expected.length` leaks nothing; the XOR loop avoids the
  // early-exit timing side-channel of `===` on the signature.
  if (expected.length !== provided.length) return false;
  let diff = 0;
  for (let i = 0; i < expected.length; i++) diff |= expected.charCodeAt(i) ^ provided.charCodeAt(i);
  return diff === 0;
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
    id:               crypto.randomUUID(),   // logbook.id has no DB default — must be supplied
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

// asset.updated — track the external asset in external_sync (entity_type='asset').
function extractAsset(payload: Record<string, unknown>, systemType: string, hiveId: string, now: string) {
  let extId = "", name = "";
  if (systemType === "sap_pm")      { extId = String(payload.EQUNR ?? ""); name = String(payload.EQKTX ?? payload.SHTXT ?? ""); }
  else if (systemType === "maximo") { extId = String(payload.ASSETNUM ?? ""); name = String(payload.DESCRIPTION ?? ""); }
  else                              { extId = String(payload.asset_tag ?? payload.asset_id ?? ""); name = String(payload.name ?? payload.description ?? ""); }
  if (!extId) return null;
  return {
    hive_id: hiveId, system_type: systemType, external_id: extId, entity_type: "asset",
    workhive_table: "assets", status: "Open",
    sync_payload: { machine: extId, name }, sync_status: "active", last_synced_at: now,
  };
}

// inventory.updated — map SAP MM (MATNR/MENGE/MINBE/MAKTX) into external_sync + inventory_items.
function extractInventory(payload: Record<string, unknown>, systemType: string, hiveId: string, now: string) {
  const m = DEFAULT_INVENTORY_FIELD_MAPS[systemType] ?? DEFAULT_INVENTORY_FIELD_MAPS.generic;
  const partNo = String(payload[m.part_number as string] ?? "");
  if (!partNo) return null;
  const qty  = parseFloat(String(payload[m.qty_on_hand as string] ?? "0")) || 0;
  const minQ = parseFloat(String(payload[m.min_qty as string] ?? "0")) || 0;
  const name = String(payload[m.name as string] ?? partNo);
  const syncRow = {
    hive_id: hiveId, system_type: systemType, external_id: partNo, entity_type: "inventory",
    workhive_table: "inventory_items", status: "Open",
    sync_payload: { part_number: partNo, qty_on_hand: qty, min_qty: minQ, name },
    sync_status: "active", last_synced_at: now,
  };
  return { partNo, qty, minQ, name, syncRow };
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

serveObserved("cmms-webhook-receiver", async (req) => {
  // Arc T/T1: standard liveness /health (fn up + DB creds reachable).
  const _health = await handleHealth(req, "cmms-webhook-receiver", async () => ({
    deps: [{ name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) }],
  }));
  if (_health) return _health;
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

    // Arc R (A07/A08): FAIL CLOSED. The old code only verified the signature when
    // config.auth_token was set — a config with a null/empty token skipped verification
    // entirely, so anyone who learned the config_id could POST forged work-order/logbook
    // events into the hive. A webhook receiver with no shared secret cannot authenticate
    // its caller, so reject rather than accept unsigned events.
    if (!config.auth_token) {
      return new Response(JSON.stringify({ error: "Webhook signature not configured" }),
        { status: 401, headers: { ...cors, "Content-Type": "application/json" } });
    }
    // CMMS-INTEGRATIONS PDDA F1: oversized-payload guard (bound memory; malformed
    // handling below). A legit CMMS event is well under 1 MB.
    if (rawBody.length > 1_000_000) {
      return new Response(JSON.stringify({ error: "Payload too large", code: "payload_too_large" }),
        { status: 413, headers: { ...cors, "Content-Type": "application/json" } });
    }
    const valid = await verifySignature(rawBody, sigHeader, tsHeader, config.auth_token);
    if (!valid) {
      return new Response(JSON.stringify({ error: "Invalid signature" }),
        { status: 401, headers: { ...cors, "Content-Type": "application/json" } });
    }

    // CMMS-INTEGRATIONS PDDA F1004/I6: replay / timestamp window. The timestamp is signed
    // (so it can't be forged) but was never checked for freshness — a captured valid
    // (sig+ts+body) triple replayed forever (live-proven 2026-07-10: 1h-old, 30d-old, AND
    // far-future all accepted 200). Idempotency dedups a replayed .created but .updated /
    // .completed re-apply on every replay (status flip / re-close). Reject deliveries whose
    // signed timestamp is outside a ±300s tolerance.
    const tsNum = Number(tsHeader);
    if (!Number.isFinite(tsNum) || Math.abs(Date.now() / 1000 - tsNum) > 300) {
      return new Response(JSON.stringify({ error: "Stale or invalid timestamp", code: "stale_timestamp" }),
        { status: 401, headers: { ...cors, "Content-Type": "application/json" } });
    }

    // F1-b: a valid-signature-but-malformed body must be a graceful 400, not a 500 from an
    // unguarded JSON.parse falling into the outer catch → failTracked.
    let body: Record<string, unknown>;
    try {
      body = JSON.parse(rawBody) as Record<string, unknown>;
    } catch {
      return new Response(JSON.stringify({ error: "Malformed JSON body", code: "bad_request" }),
        { status: 400, headers: { ...cors, "Content-Type": "application/json" } });
    }
    const eventType  = String(body.event ?? "");
    const payload    = (body.payload ?? body) as Record<string, unknown>;
    const systemType = String(body.cmms_type ?? config.system_type);
    const hiveId     = config.hive_id;
    const now        = new Date().toISOString();

    // Get a worker to attribute events to
    const { data: members } = await db.from("v_worker_truth")
      .select("worker_name").eq("hive_id", hiveId).eq("role", "supervisor").limit(1);
    const workerName = members?.[0]?.worker_name || "CMMS Webhook";

    // Process based on event type
    if (["work_order.created", "work_order.updated", "work_order.completed"].includes(eventType)) {
      const extracted = extractWorkOrder(payload, systemType, hiveId, workerName, now);
      if (!extracted) {
        // edge-status-allow: webhook delivered + accepted; payload had no
        // external_id so nothing to sync. Caller checks resp.ok flag.
        return new Response(JSON.stringify({ ok: false, reason: "No external_id in payload" }),
          { status: 200, headers: { ...cors, "Content-Type": "application/json" } });
      }

      const { syncRow, logRow } = extracted;

      // Was this external_id already synced BEFORE this event? Check FIRST — the upsert
      // below would otherwise make the row always look pre-existing, so the logbook
      // insert was structurally dead (CMMS work orders never reached the logbook).
      // Checking before the upsert keeps the logbook write exactly-once: a genuinely new
      // work_order.created writes one logbook row; an at-least-once REPLAY finds the row
      // already present and skips it (idempotent).
      let alreadySynced = false;
      if (eventType === "work_order.created") {
        const { data: existing } = await db.from("v_external_sync_truth")
          .select("id").eq("external_id", extracted.extId).eq("hive_id", hiveId).limit(1);
        alreadySynced = !!existing?.length;
      }

      // Upsert to external_sync
      await db.from("external_sync")
        .upsert(syncRow, { onConflict: "system_type,external_id,entity_type" });

      // Insert to logbook only for a genuinely new work_order.created (idempotent on replay).
      if (eventType === "work_order.created" && !alreadySynced) {
        await db.from("logbook").insert(logRow);
        // F1005: link the external_sync WO to this logbook row so cmms-push-completion
        // pushes completion to the CORRECT work order (not machine+newest).
        await db.from("external_sync")
          .update({ workhive_id: logRow.id })
          .eq("hive_id", hiveId).eq("system_type", systemType)
          .eq("external_id", extracted.extId).eq("entity_type", "work_order");
      } else if (eventType === "work_order.updated" || eventType === "work_order.completed") {
        // F6 cross-surface consistency: a .updated/.completed event must also update the
        // LINKED logbook row's status, else a CMMS-completed order still reads "Open" in the
        // logbook (the header contract promises "work_order.completed -> close in ... logbook").
        // canonical-allow: engine resolves its own link row (external_id -> workhive_id) to cascade
        // the completion; v_external_sync_truth is the display view, this needs the raw FK link.
        const { data: link } = await db.from("external_sync")
          .select("workhive_id")
          .eq("hive_id", hiveId).eq("system_type", systemType)
          .eq("external_id", extracted.extId).eq("entity_type", "work_order").limit(1);
        const lbId = (link?.[0] as Record<string, unknown> | undefined)?.workhive_id as string | undefined;
        if (lbId) {
          const closedAt = (syncRow.sync_payload as Record<string, unknown> | undefined)?.closed_at as string | null | undefined;
          await db.from("logbook")
            .update({ status: syncRow.status, closed_at: syncRow.status === "Closed" ? (closedAt || now) : null })
            .eq("id", lbId);
        }
      }

    } else if (eventType === "asset.updated") {
      // F1: was a silent no-op contradicting the header contract. Track the external asset in
      // external_sync (idempotent upsert on system_type,external_id,entity_type).
      const a = extractAsset(payload, systemType, hiveId, now);
      if (a) await db.from("external_sync").upsert(a, { onConflict: "system_type,external_id,entity_type" });

    } else if (eventType === "inventory.updated") {
      // F2: SAP MM / material-master sync (MATNR->part_number). external_sync is the idempotent
      // tracking; inventory_items has only PK(id), so existence-check on (hive_id,part_number)
      // then update-or-insert (with a supplied id — inventory_items.id has no DB default).
      const inv = extractInventory(payload, systemType, hiveId, now);
      if (inv) {
        await db.from("external_sync").upsert(inv.syncRow, { onConflict: "system_type,external_id,entity_type" });
        // canonical-allow: existence-check for update-or-insert of an inbound SAP material — needs the raw
        // PK (inventory_items has PK(id) only, no natural key); v_inventory_items_truth is a display view.
        const { data: existing } = await db.from("inventory_items")
          .select("id").eq("hive_id", hiveId).eq("part_number", inv.partNo).limit(1);
        if (existing?.length) {
          await db.from("inventory_items")
            .update({ qty_on_hand: inv.qty, min_qty: inv.minQ, part_name: inv.name, updated_at: now })
            .eq("id", (existing[0] as Record<string, unknown>).id as string);
        } else {
          await db.from("inventory_items").insert({
            id: crypto.randomUUID(), worker_name: workerName, part_number: inv.partNo,
            part_name: inv.name, qty_on_hand: inv.qty, min_qty: inv.minQ, hive_id: hiveId,
            status: "approved", // CMMS material master is authoritative (status_check: approved|pending|rejected)
          });
        }
      }

    } else if (eventType === "pm.overdue") {
      // F1: was a silent no-op. Record the overdue PM durably in external_sync (entity_type
      // 'pm_schedule') so it is tracked/queryable, not only logged.
      const pmId = String(payload.AUFNR ?? payload.WONUM ?? payload.pm_id ?? payload.asset_tag ?? "");
      if (pmId) {
        await db.from("external_sync").upsert({
          hive_id: hiveId, system_type: systemType, external_id: pmId, entity_type: "pm_schedule",
          workhive_table: "pm_assets", status: "Open",
          sync_payload: { overdue: true, machine: String(payload.EQUNR ?? payload.ASSETNUM ?? "") },
          sync_status: "active", last_synced_at: now,
        }, { onConflict: "system_type,external_id,entity_type" });
      }
      log.info(null, `Recorded pm.overdue for ${pmId} hive ${hiveId}`);
    }

    return new Response(
      JSON.stringify({ ok: true, event: eventType, hive_id: hiveId }),
      { status: 200, headers: { ...cors, "Content-Type": "application/json" } },
    );

  } catch (err) {
    // T2b: aggregate this HANDLED failure to wh_traces + non-leaky 500.
    return await failTracked(req, "cmms-webhook-receiver", "cmms_webhook_receiver_error", err);
  }
});
