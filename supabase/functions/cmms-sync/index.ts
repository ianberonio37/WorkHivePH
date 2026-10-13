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

import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2.110.0";
import { getCorsHeaders } from "../_shared/cors.ts";
import { log } from "../_shared/logger.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
// Pillar I (Gateway Spine): verify hive membership on the manual sync path.
import { resolveIdentity, resolveTenancy } from "../_shared/tenant-context.ts";
// A5 (FULLSTACK_COMPONENT_LIBRARY Layer A): per-person rate limit on the browser path.
import { checkSoloRateLimit, soloRateLimitKey, soloRateLimitedResponse } from "../_shared/rate-limit.ts";
import { FieldMap, normaliseStatus, normaliseType, effectiveFieldMap } from "../_shared/mappings.ts";
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

// ★THE LOCAL MOCK CMMS, AND ONLY ON THE LOCAL RUNTIME (2026-10-12, UFAI edge walk W4331). The SSRF guard refuses http and
// host.docker.internal - rightly - which left the seeder's mock CMMS (test-data-seeder/mock_cmms) unreachable, so no
// local run could prove a sync end to end. The same local test as observability.ts's _OBS_LOCAL (a local stack's
// functions reach postgres through kong; prod is *.supabase.co, where this is always false), and only the mock's own
// path. validate_ssrf_egress.py fails any guard allowance that is not behind a local-runtime test.
const _CMMS_LOCAL = /\/\/(kong|localhost|127\.0\.0\.1)(:|\/|$)/.test(Deno.env.get("SUPABASE_URL") || "");
const _LOCAL_MOCK_PREFIX = "http://host.docker.internal:5000/mock/";

// ★THE GUARD'S OWN WORDS REACHED A SUPERVISOR (2026-10-12, W4331). Test Connection, Run Now and the connector list all
// show this error, and they showed "SSRF: scheme 'http:' not allowed (https only)" - accurate, and no use to the person
// who typed the address. Each refusal says what to change; anything unrecognised passes through unchanged.
function cmmsFailureSentence(msg: string): string {
  const m = String(msg || "");
  if (/^SSRF: scheme/.test(m)) return "This address does not start with https://. WorkHive connects to a CMMS only over https, so use your CMMS's https address.";
  if (/^SSRF: credentials in URL/.test(m)) return "This address has a username or password in it. Take them out and put the token in the API token field instead.";
  if (/^SSRF: (internal hostname|private\/reserved IP|'.*' resolves to private)/.test(m)) return "This address points inside a private network, which WorkHive cannot reach. Use the address your CMMS publishes on the internet.";
  if (/^SSRF: '.*' did not resolve/.test(m)) return "WorkHive could not find this address. Check the spelling of the endpoint URL.";
  if (/^SSRF: invalid URL/.test(m)) return "This is not a valid web address. Check the endpoint URL.";
  if (/^SSRF: too many redirects/.test(m)) return "Your CMMS sent WorkHive on to too many other addresses. Use the final address of its API.";
  const api = m.match(/^CMMS API (\d{3})/);
  if (api) {
    const c = Number(api[1]);
    if (c === 401 || c === 403) return `Your CMMS refused the API token (${c}). Check the token and try again.`;
    if (c === 404) return "Your CMMS answered that this address does not exist (404). Check the endpoint URL.";
    if (c === 429) return "Your CMMS asked WorkHive to slow down (429). The next run will try again.";
    if (c >= 500) return `Your CMMS had a problem answering (${c}). The next run will try again.`;
    return `Your CMMS refused the request (${c}). Check the endpoint URL and token.`;
  }
  if (/circuit-breaker open/.test(m)) return "Your CMMS failed several times in a row, so WorkHive is waiting before it tries again. The next run will retry.";
  if (/timed? ?out|TimeoutError|aborted/i.test(m)) return "Your CMMS did not answer in time. The next run will try again.";
  return m;
}

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

// normaliseStatus, normaliseType, effectiveFieldMap, FieldMap — all from _shared/mappings.ts (the code tables + clamp)

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
  const normStatus = normaliseStatus(systemType, rawStatus);   // always Open/Closed/Cancelled (mappings.ts)
  const rawType   = get(fieldMap.maintenance_type);
  const normType  = normaliseType(systemType, rawType);
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
      // what the sender actually said, whenever the clamp changed it
      status_raw: rawStatus || null, type_raw: rawType || null,
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
  // ★ONE HIVE'S DEAD ENDPOINT BLOCKED EVERY HIVE'S SYNC (2026-10-12). The breaker was keyed per SYSTEM TYPE
  // ("cmms-sap_pm") and the cron fan-out runs every hive's config in one request, so one hive's unreachable SAP host
  // opened it and every other hive's healthy SAP sync failed "circuit-breaker open". A dead endpoint is dead for the
  // host it is on: the breaker is keyed by that host.
  let _host = "invalid";
  try { _host = new URL(endpointUrl).host.toLowerCase(); } catch { /* empty-catch-allow: an invalid URL is refused by the guard below */ }
  const _slot = `cmms-${systemType}-${_host}`;
  if (isSlotBlocked(_slot)) throw new Error("CMMS temporarily unavailable (circuit-breaker open)");
  const _mock = _CMMS_LOCAL && url.startsWith(_LOCAL_MOCK_PREFIX);
  const resp = await safeFetch(url, { headers, signal: AbortSignal.timeout(30000) },
    _mock ? { allowHttp: true, allowHosts: ["host.docker.internal"] } : {});
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
): Promise<{ synced: number; failed: number; unusable: number; error: string | null }> {
  const hiveId     = config.hive_id    as string;
  const systemType = config.system_type as string;
  const endpoint   = config.endpoint_url as string;
  const authToken  = config.auth_token  as string | null;
  const fieldMap   = effectiveFieldMap(systemType, config.field_map);   // the defaults, overridden per hive (mappings.ts)
  const cursor     = config.delta_cursor as string | null;

  if (!endpoint) return { synced: 0, failed: 0, unusable: 0, error: "No endpoint URL is set for this connector. Add one and save." };

  // Get a supervisor worker_name for the hive (for logbook attribution)
  const { data: members } = await db.from("v_worker_truth")
    .select("worker_name").eq("hive_id", hiveId).eq("role", "supervisor").limit(1);
  const workerName = members?.[0]?.worker_name || "CMMS Sync";

  let synced = 0, failed = 0, skip = 0, unusable = 0;
  let failWhy = "";
  let hasMore = true;

  while (hasMore) {
    const { rows, hasMore: more } = await fetchPage(systemType, endpoint, authToken, cursor, 200, skip);
    hasMore = more;
    skip   += rows.length;

    if (!rows.length) break;
    // dry run: count what a real run would KEEP. It counted every row fetched, so Test Connection said "found 50 records.
    // Ready to sync." for a connector whose field map could key none of them - and Run Now then synced 0 (2026-10-12).
    if (testMode) {
      for (const raw of rows) {
        if (normalizeRow(raw as Record<string, unknown>, systemType, fieldMap, hiveId, workerName)) synced++;
        else unusable++;
      }
      break;
    }

    const norms: { extId: string; syncRow: Record<string, unknown>; logRow: Record<string, unknown>; fkRow: Record<string, unknown> | null }[] = [];
    const syncRows: Record<string, unknown>[] = [];

    for (const raw of rows) {
      const norm = normalizeRow(raw as Record<string, unknown>, systemType, fieldMap, hiveId, workerName);
      if (!norm) { unusable++; continue; }   // no external id: nothing to key it by - reported, and fetching again cannot fix it
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

    // Batch upsert external_sync (idempotent on hive_id,system_type,external_id,entity_type - per hive since 2026-10-12)
    if (syncRows.length) {
      const { error } = await db.from("external_sync")
        .upsert(syncRows, { onConflict: "hive_id,system_type,external_id,entity_type" });
      if (error) {
        console.error("cmms-sync: external_sync upsert failed -", error.message);
        failed += syncRows.length; failWhy = failWhy || "WorkHive could not save them";
        continue;
      }
    }

    // Insert logbook + fault_knowledge ONLY for genuinely-new external_ids (idempotent replay).
    const newLogRows = norms.filter(n => !known.has(n.extId)).map(n => n.logRow);
    const newFkRows  = norms.filter(n => !known.has(n.extId) && n.fkRow).map(n => n.fkRow as Record<string, unknown>);
    // ★IN THE SYNC TABLE AND NEVER IN THE LOGBOOK (2026-10-12). A failed logbook insert was only warned about, and the
    // external_sync rows above were already written - so the next run counted those ids as KNOWN and never inserted
    // them again: the order existed for the integration and never for a person. The webhook throws here; a batch
    // takes its new ids back out of external_sync, so the next run (the cursor does not move) fetches and retries them.
    let logFailed = 0;
    if (newLogRows.length) {
      const { error } = await db.from("logbook").insert(newLogRows);
      if (error) {
        console.error("cmms-sync: logbook insert failed -", error.message);
        logFailed = newLogRows.length;
        failed += logFailed; failWhy = failWhy || "the logbook did not accept them";
        const newIds = norms.filter(n => !known.has(n.extId)).map(n => n.extId);
        const { error: undoErr } = await db.from("external_sync").delete()
          .eq("hive_id", hiveId).eq("system_type", systemType).eq("entity_type", "work_order").in("external_id", newIds);
        if (undoErr) console.error("cmms-sync: could not take back the external_sync rows the logbook refused -", undoErr.message);
      }
    }
    if (newFkRows.length && !logFailed) {
      // AI6: fault_knowledge.source defaults to 'manual' (a human wrote it). These rows came from
      // an EXTERNAL CMMS, not from a WorkHive human, so stamp them explicitly - otherwise the
      // default would launder imported records as first-party field experience in RAG + reports.
      for (const r of newFkRows) r.source = "cmms_import";
      const { error } = await db.from("fault_knowledge").insert(newFkRows);
      if (error) log.warn(null, "fault_knowledge insert error:", { detail: error.message });
    }

    // F1005: link each NEWLY-created logbook row to its external_sync WO (workhive_id) so
    // cmms-push-completion pushes completion to the CORRECT work order, not machine+newest.
    // Only for new rows — a re-sync must not overwrite an existing link with an uninserted id.
    for (const n of norms) {
      if (known.has(n.extId) || logFailed) continue;
      /* ★THE SAME F1005 LINK THE WEBHOOK PATH CARRIES (2026-09-09). Without it, cmms-push-completion
         falls back to machine+newest and can close the WRONG work order in the customer's CMMS - which
         is precisely why F1005 exists. Logged rather than thrown: both rows are written and the sync is
         sound, so failing the whole run would be the larger harm; but it must not be silent. */
      const { error: linkErr } = await db.from("external_sync")
        .update({ workhive_id: (n.logRow as Record<string, unknown>).id })
        .eq("hive_id", hiveId).eq("system_type", systemType)
        .eq("external_id", n.extId).eq("entity_type", "work_order");
      if (linkErr) {
        console.error(`cmms-sync: F1005 link failed for ${n.extId} -`, linkErr.message,
          "- a later completion push may target the wrong work order");
      }
    }

    synced += syncRows.length - logFailed;
    if (skip > 5000) break; // safety cap per run — avoid runaway syncs
  }

  // a write the database refused is an ERROR the person reads and the cursor respects (the run was not clean); a row
  // with no external id is reported but does not hold the cursor, because fetching it again cannot fix it
  return {
    synced, failed, unusable,
    error: failed
      ? `${failed} work order${failed === 1 ? "" : "s"} could not be recorded (${failWhy}). They will be fetched again on the next run.`
      : null,
  };
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
        if (!_rl.allowed) return soloRateLimitedResponse(getCorsHeaders(req), _rl.retry_after_seconds, _rl.scope);
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
      let syncResult = { synced: 0, failed: 0, unusable: 0, error: null as string | null };
      try {
        syncResult = await syncConfig(db, config, testMode);
      } catch (e) {
        syncResult.error = cmmsFailureSentence(e instanceof Error ? e.message : String(e));
      }

      if (!testMode) {
        // Update config with sync result
        /* ★THIS ROW IS WHAT integrations.html READS TO SAY A CONNECTOR IS HEALTHY (2026-09-09,
           unchecked-writes sweep). The page's three tiles - ACTIVE, STALE, DISABLED - are computed from
           last_sync_at; if this write is lost, a connector that just synced successfully reads as never
           having synced, and a supervisor is told an integration is stale when it is not. The result is
           checked below rather than thrown, because the SYNC itself already succeeded and failing the
           request would misreport the more important half. */
        // ★A FAILED RUN MOVED THE CURSOR PAST WHAT IT NEVER FETCHED (2026-10-12, W4331 - measured: a refused run wrote
        // delta_cursor = now beside last_sync_status 'failed'). The next run asks only for records after the cursor, so an
        // outage window, or a batch the database refused, was skipped for good. The cursor moves on a clean run only.
        const _clean = !syncResult.error && !syncResult.failed;
        const { error: cfgErr } = await db.from("integration_configs").update({
          last_sync_at:     now,
          last_sync_count:  syncResult.synced,
          last_sync_status: syncResult.error ? "failed" : "success",
          last_sync_error:  syncResult.error,
          ...(_clean ? { delta_cursor: now } : {}),  // next run fetches only records after this - after a CLEAN run
        }).eq("id", config.id);
        if (cfgErr) {
          console.error("cmms-sync: the sync succeeded but its result could not be recorded on the config -",
            cfgErr.message, "- integrations.html will read this connector as never having synced, and the "
            + "delta cursor did not advance, so the next run will re-fetch the same window");
        }

        // Log to automation_log
  // unchecked-write-allow: a telemetry row. Its failure must not change the caller's outcome - refusing real work because a log line did not land would be the worse bug.
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
          rows_attempted: syncResult.synced + syncResult.failed + syncResult.unusable,
          rows_written:   syncResult.synced,
          rows_failed:    syncResult.failed + syncResult.unusable,
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
