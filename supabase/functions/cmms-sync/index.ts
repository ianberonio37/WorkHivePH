/**
 * cmms-sync — Phase 3.1: Tier 2 API Sync
 *
 * Polls configured CMMS endpoints (SAP OData, Maximo OSLC, or Generic REST)
 * and syncs new/updated records into external_sync + logbook + fault_knowledge.
 *
 * Supports delta sync: only fetches records updated since last_sync_at.
 *
 * POST body:
 *   hive_id    — sync one hive's configs (omit for all active hives)
 *   config_id  — sync a single config by ID
 *   test       — if true, fetch first page only, do not write to DB (dry run)
 */

import { serveObserved, failTracked } from "../_shared/observability.ts";
import { handleHealth } from "../_shared/health.ts";
import { logRequestStart } from "../_shared/logger.ts";

import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";
import { log } from "../_shared/logger.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
// Pillar I (Gateway Spine): verify hive membership on the manual sync path.
import { resolveIdentity, resolveTenancy } from "../_shared/tenant-context.ts";
// A5 (FULLSTACK_COMPONENT_LIBRARY Layer A): per-person rate limit on the browser path.
import { checkSoloRateLimit, soloRateLimitKey, soloRateLimitedResponse } from "../_shared/rate-limit.ts";
import { STATUS_MAP, TYPE_MAP, FieldMap } from "../_shared/mappings.ts";
// Arc R (A10): tenant-controlled endpoint_url must be SSRF-guarded before fetch.
import { safeFetch } from "../_shared/ssrf-guard.ts";
// Arc S F-lens (F-010): circuit-break the external CMMS dependency so a dead/slow
// CMMS endpoint stops being hammered (escalating cooldown) and fails fast.
import { isSlotBlocked, recordSlotFailure, recordSlotSuccess } from "../_shared/provider-health.ts";

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
// Response envelope parsers
// ---------------------------------------------------------------------------

function parseRows(systemType: string, json: Record<string, unknown>): unknown[] {
  if (systemType === "sap_pm") {
    return (json?.d as Record<string, unknown>)?.results as unknown[] ?? [];
  } else if (systemType === "maximo") {
    return json?.["rdfs:member"] as unknown[] ?? [];
  }
  return (json?.data as unknown[]) ?? (Array.isArray(json) ? json : []);
}

// ---------------------------------------------------------------------------
// Status normalization
// ---------------------------------------------------------------------------

// STATUS_MAP, TYPE_MAP, FieldMap — all imported from _shared/mappings.ts

// ---------------------------------------------------------------------------
// Row normalization using field_map from integration_configs
// ---------------------------------------------------------------------------

function normalizeRow(
  raw: Record<string, unknown>,
  systemType: string,
  fieldMap: FieldMap,
  hiveId: string,
  workerName: string,
) {
  const get = (col?: string) => (col ? String(raw[col] ?? "") : "");

  const rawStatus = get(fieldMap.status);
  const normStatus = STATUS_MAP[systemType]?.[rawStatus] ?? rawStatus ?? "Open";
  const rawType   = get(fieldMap.maintenance_type);
  const normType  = TYPE_MAP[systemType]?.[rawType] ?? rawType ?? "Breakdown / Corrective";
  const extId     = get(fieldMap.external_id);
  const machine   = get(fieldMap.machine);

  if (!extId) return null;

  const syncRow = {
    hive_id:        hiveId,
    system_type:    systemType,
    external_id:    extId,
    entity_type:    "work_order",
    workhive_table: "logbook",
    status:         normStatus,
    sync_payload:   {
      machine, problem: get(fieldMap.problem), root_cause: get(fieldMap.root_cause),
      action: get(fieldMap.action), maintenance_type: normType,
      actual_hours: parseFloat(get(fieldMap.actual_hours)) || 0,
      created_at: get(fieldMap.created_at), closed_at: get(fieldMap.closed_at) || null,
    },
    sync_status:    "active",
    last_synced_at: new Date().toISOString(),
  };

  const now = new Date().toISOString();
  // F1002: logbook.id is text NOT NULL with NO DB default — the old id-less insert threw a
  // NOT NULL violation that was swallowed by .then(({error})=>log.warn), so NO CMMS work
  // order ever reached the logbook (while the UI claimed "new work orders in Logbook").
  // Supply the id exactly like cmms-webhook-receiver does.
  const logId = crypto.randomUUID();
  const logRow = {
    id:               logId,
    worker_name:      workerName,
    date:             get(fieldMap.created_at) || now,
    machine,
    category:         normType === "Preventive Maintenance" ? "Mechanical" : "Mechanical",
    problem:          get(fieldMap.problem) || "Synced from CMMS",
    action:           get(fieldMap.action) || "",
    knowledge:        get(fieldMap.root_cause) || "",
    status:           normStatus,
    created_at:       get(fieldMap.created_at) || now,
    maintenance_type: normType,
    root_cause:       get(fieldMap.root_cause) || "",
    downtime_hours:   parseFloat(get(fieldMap.actual_hours)) || 0,
    hive_id:          hiveId,
    closed_at:        normStatus === "Closed" ? (get(fieldMap.closed_at) || now) : null,
    parts_used:       [],
  };

  const fkRow = (get(fieldMap.problem) || get(fieldMap.root_cause)) ? {
    hive_id:    hiveId,
    logbook_id: logId,   // F1011: the REAL logbook row id (was the external_id string → broken FK)
    machine,
    problem:    get(fieldMap.problem) || null,
    root_cause: get(fieldMap.root_cause) || null,
    action:     get(fieldMap.action) || null,
    knowledge:  null,
    worker_name: workerName,
  } : null;

  return { extId, syncRow, logRow, fkRow };
}

// ---------------------------------------------------------------------------
// Fetch one page from the CMMS API
// ---------------------------------------------------------------------------

async function fetchPage(
  systemType: string,
  endpointUrl: string,
  authToken: string | null,
  cursor: string | null,
  top = 200,
  skip = 0,
): Promise<{ rows: unknown[]; hasMore: boolean }> {
  const headers: Record<string, string> = { "Accept": "application/json" };
  if (authToken) headers["Authorization"] = authToken.startsWith("Bearer ") ? authToken : `Bearer ${authToken}`;

  let url = endpointUrl;
  const params = new URLSearchParams();

  if (systemType === "sap_pm") {
    params.set("$top",  String(top));
    params.set("$skip", String(skip));
    if (cursor) params.set("$filter", `ERDAT ge '${cursor.slice(0, 10)}'`);
  } else if (systemType === "maximo") {
    params.set("oslc.pageSize",  String(top));
    params.set("oslc.pageIndex", String(Math.floor(skip / top) + 1));
    if (cursor) params.set("oslc.where", `reportdate>="${cursor.slice(0, 10)}"`);
  } else {
    params.set("limit",  String(top));
    params.set("offset", String(skip));
    if (cursor) params.set("updated_after", cursor.slice(0, 10));
  }

  const sep = url.includes("?") ? "&" : "?";
  url += sep + params.toString();

  // Arc R (A10): endpoint_url is tenant-controlled — SSRF-guard the fetch so it can't be
  // pointed at metadata/RFC1918/internal hosts (which would also leak the Bearer authToken).
  // Arc S F-lens (F-010): circuit-breaker keyed per CMMS system — a dead endpoint
  // sheds fast (escalating cooldown) instead of being retried into the ground.
  const _slot = `cmms-${systemType}`;
  if (isSlotBlocked(_slot)) throw new Error("CMMS temporarily unavailable (circuit-breaker open)");
  const resp = await safeFetch(url, { headers, signal: AbortSignal.timeout(30000) });
  if (!resp.ok) {
    const _ra = Number(resp.headers.get("retry-after"));
    recordSlotFailure(_slot, Number.isFinite(_ra) && _ra > 0 ? _ra * 1000 : undefined);
    throw new Error(`CMMS API ${resp.status}`); // do not echo upstream body
  }
  recordSlotSuccess(_slot);

  const json = await resp.json();
  const rows = parseRows(systemType, json);
  return { rows, hasMore: rows.length === top };
}

// ---------------------------------------------------------------------------
// Sync one config
// ---------------------------------------------------------------------------

async function syncConfig(
  db: SupabaseClient,
  config: Record<string, unknown>,
  testMode: boolean,
): Promise<{ synced: number; failed: number; error: string | null }> {
  const hiveId     = config.hive_id    as string;
  const systemType = config.system_type as string;
  const endpoint   = config.endpoint_url as string;
  const authToken  = config.auth_token  as string | null;
  const fieldMap   = (config.field_map  as FieldMap) || {};
  const cursor     = config.delta_cursor as string | null;

  if (!endpoint) return { synced: 0, failed: 0, error: "No endpoint_url configured" };

  // Get a supervisor worker_name for the hive (for logbook attribution)
  const { data: members } = await db.from("v_worker_truth")
    .select("worker_name").eq("hive_id", hiveId).eq("role", "supervisor").limit(1);
  const workerName = members?.[0]?.worker_name || "CMMS Sync";

  let synced = 0, failed = 0, skip = 0;
  let hasMore = true;

  while (hasMore) {
    const { rows, hasMore: more } = await fetchPage(systemType, endpoint, authToken, cursor, 200, skip);
    hasMore = more;
    skip   += rows.length;

    if (!rows.length) break;
    if (testMode) { synced = rows.length; break; } // dry run: count only

    const norms: { extId: string; syncRow: Record<string, unknown>; logRow: Record<string, unknown>; fkRow: Record<string, unknown> | null }[] = [];
    const syncRows: Record<string, unknown>[] = [];

    for (const raw of rows) {
      const norm = normalizeRow(raw as Record<string, unknown>, systemType, fieldMap, hiveId, workerName);
      if (!norm) { failed++; continue; }
      norms.push(norm);
      syncRows.push(norm.syncRow);
    }

    // F1006 idempotency: which external_ids were ALREADY synced BEFORE this run? Check first
    // — the upsert below makes every row look pre-existing, so this must precede it. The
    // external_sync upsert is idempotent, but logbook/fault_knowledge have no natural dedup
    // key, and the delta cursor filters at DATE granularity (cursor.slice(0,10)) so a re-run
    // re-fetches the same day's rows. Without this, each re-sync duplicates the derived rows.
    const extIds = norms.map(n => n.extId);
    let known = new Set<string>();
    if (extIds.length) {
      // canonical-allow: idempotency dedup on the engine's OWN external_sync table before batch upsert
      // (F2). v_external_sync_truth is the display view; the sync engine reads its raw tracking rows.
      const { data: existing } = await db.from("external_sync")
        .select("external_id").eq("hive_id", hiveId).eq("system_type", systemType).in("external_id", extIds);
      known = new Set((existing || []).map(e => String((e as Record<string, unknown>).external_id)));
    }

    // Batch upsert external_sync (idempotent on system_type,external_id,entity_type)
    if (syncRows.length) {
      const { error } = await db.from("external_sync")
        .upsert(syncRows, { onConflict: "system_type,external_id,entity_type" });
      if (error) { failed += syncRows.length; continue; }
    }

    // Insert logbook + fault_knowledge ONLY for genuinely-new external_ids (idempotent replay).
    const newLogRows = norms.filter(n => !known.has(n.extId)).map(n => n.logRow);
    const newFkRows  = norms.filter(n => !known.has(n.extId) && n.fkRow).map(n => n.fkRow as Record<string, unknown>);
    if (newLogRows.length) {
      const { error } = await db.from("logbook").insert(newLogRows);
      if (error) log.warn(null, "logbook insert error:", { detail: error.message });
    }
    if (newFkRows.length) {
      const { error } = await db.from("fault_knowledge").insert(newFkRows);
      if (error) log.warn(null, "fault_knowledge insert error:", { detail: error.message });
    }

    // F1005: link each NEWLY-created logbook row to its external_sync WO (workhive_id) so
    // cmms-push-completion pushes completion to the CORRECT work order, not machine+newest.
    // Only for new rows — a re-sync must not overwrite an existing link with an uninserted id.
    for (const n of norms) {
      if (known.has(n.extId)) continue;
      await db.from("external_sync")
        .update({ workhive_id: (n.logRow as Record<string, unknown>).id })
        .eq("hive_id", hiveId).eq("system_type", systemType)
        .eq("external_id", n.extId).eq("entity_type", "work_order");
    }

    synced += syncRows.length;
    if (skip > 5000) break; // safety cap per run — avoid runaway syncs
  }

  return { synced, failed, error: null };
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

serveObserved("cmms-sync", async (req) => {
  // Arc T/T1: standard liveness /health (fn up + DB creds reachable).
  const _health = await handleHealth(req, "cmms-sync", async () => ({
    deps: [{ name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) }],
  }));
  if (_health) return _health;
  const cors = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  logRequestStart(req, "cmms-sync");  // I6 observability

  try {
    const db = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    );

    const body      = await req.json().catch(() => ({}));
    const testMode  = Boolean(body.test);
    const now       = new Date().toISOString();

    // Pillar I: the manual (integrations.html) path scopes the CMMS sync by the
    // client hive_id on a service-role client — verify membership. The cron path
    // (no hive_id → all enabled configs) is reached only by service-role and skips.
    let callerIsServiceRole = false;
    if (body.hive_id) {
      const { authUid, isServiceRole } = await resolveIdentity(db, req);
      callerIsServiceRole = isServiceRole;
      if (!isServiceRole) {
        const t = await resolveTenancy(db, authUid, String(body.hive_id));
        if (!t.ok) {
          return new Response(
            JSON.stringify({ error: t.message, code: t.code }),
            { status: t.status, headers: { ...cors, "Content-Type": "application/json" } },
          );
        }
      
        // A5: rate-limit the browser path (service-role/internal callers skip) — reference: voice-model-call/embed-entry.
        const _ip = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim();
        const _rl = await checkSoloRateLimit(db, soloRateLimitKey(authUid, _ip), undefined, undefined, _ip);
        if (!_rl.allowed) return soloRateLimitedResponse(getCorsHeaders(req));
      }
    } else {
      // Arc R (A01): no hive_id = the all-hives cron path. The old comment CLAIMED this was
      // "reached only by service-role" but never ENFORCED it — an anon caller POSTing {}
      // fanned out a sync across EVERY hive (cross-tenant writes + SSRF amplification via
      // each hive's endpoint_url). Require service_role for the no-hive_id fan-out.
      const { isServiceRole } = await resolveIdentity(db, req);
      callerIsServiceRole = isServiceRole;
      if (!isServiceRole) {
        return new Response(
          JSON.stringify({ error: "service_role required for all-hives sync", code: "forbidden" }),
          { status: 403, headers: { ...cors, "Content-Type": "application/json" } },
        );
      }
    }

    // Fetch configs to sync
    // unbounded-query-allow: enabled integration configs (one row per hive max); full fetch required
    let configQuery = db.from("integration_configs").select("*");
    if (body.config_id) {
      // A specific config_id is an EXPLICIT target (Run Now / Test Connection). Do NOT filter
      // on enabled — F1003: the old unconditional .eq("enabled",true) excluded the temp
      // enabled:false test config, so cmms-sync returned "no active configs" and the client
      // rendered a FAKE "Connected: found 0 records" even for a garbage endpoint (never fetched).
      configQuery = configQuery.eq("id", body.config_id);
      // CMMS-INTEGRATIONS PDDA I1 (BOLA fix): config_id is semi-public — it is rendered
      // into the inbound webhook URL and shared with CMMS admins. The membership gate above
      // only proved the caller belongs to body.hive_id; without ALSO scoping the config
      // lookup to that verified hive, a member of hive A could pass {hive_id:A, config_id:<B's>}
      // and sync hive B's config (B's endpoint_url + auth_token) into B's data. A non-service
      // caller may only sync a config that belongs to the hive they were authorized for.
      if (!callerIsServiceRole) configQuery = configQuery.eq("hive_id", String(body.hive_id));
    } else if (body.hive_id) {
      configQuery = configQuery.eq("hive_id", body.hive_id).eq("enabled", true);
    } else {
      configQuery = configQuery.eq("enabled", true);  // cron all-hives fan-out
    }

    const { data: configs, error: cfgErr } = await configQuery;
    if (cfgErr) throw new Error(cfgErr.message);
    if (!configs?.length) {
      return new Response(JSON.stringify({ ok: true, message: "No active configs found." }),
        { status: 200, headers: { ...cors, "Content-Type": "application/json" } });
    }

    const results: Record<string, unknown>[] = [];

    for (const config of configs) {
      let syncResult = { synced: 0, failed: 0, error: null as string | null };
      try {
        syncResult = await syncConfig(db, config, testMode);
      } catch (e) {
        syncResult.error = e instanceof Error ? e.message : String(e);
      }

      if (!testMode) {
        // Update config with sync result
        await db.from("integration_configs").update({
          last_sync_at:     now,
          last_sync_count:  syncResult.synced,
          last_sync_status: syncResult.error ? "failed" : "success",
          last_sync_error:  syncResult.error,
          delta_cursor:     now,  // next run fetches only records after this
        }).eq("id", config.id);

        // Log to automation_log
        await db.from("automation_log").insert({
          job_name: "cmms-sync",
          hive_id:  config.hive_id,
          status:   syncResult.error ? "failed" : "success",
          detail:   `${config.system_type} sync: ${syncResult.synced} records. ${syncResult.error || ""}`,
        });

        // Log to cmms_audit_log for reconciliation and impact tracking
        await db.from("cmms_audit_log").insert({
          hive_id:        config.hive_id,
          batch_id:       `sync-${config.id}-${now.slice(0,19)}`,
          operation:      "live_sync",
          entity_type:    "work_order",
          system_type:    config.system_type,
          rows_attempted: syncResult.synced + syncResult.failed,
          rows_written:   syncResult.synced,
          rows_failed:    syncResult.failed,
          triggered_by:   "cmms-sync",
        }).then(() => {}).catch((e: Error) => log.warn(null, "cmms_audit_log write failed:", { detail: e.message }));
      }

      results.push({
        config_id:   config.id,
        hive_id:     config.hive_id,
        system_type: config.system_type,
        ...syncResult,
        test_mode:   testMode,
      });
    }

    return new Response(JSON.stringify({ ok: true, results }),
      { status: 200, headers: { ...cors, "Content-Type": "application/json" } });

  } catch (err) {
    // T2b: aggregate this HANDLED failure to wh_traces + non-leaky 500.
    return await failTracked(req, "cmms-sync", "cmms_sync_error", err);
  }
});
