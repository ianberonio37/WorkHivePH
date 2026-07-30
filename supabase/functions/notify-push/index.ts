// capability: service_hailing_push_notify
/**
 * notify-push (SERVICE_HAILING_ROADMAP.md P5 / G3) — Web Push job-offer delivery so a
 * provider hears a hail with the tab CLOSED (without this, hailing fails on mobile).
 *
 * AUTH: service-role ONLY (requireServiceRole — the L6 edge-fn gate). Callers are
 * backend: the broadcast fan-out (DB webhook/cron, future), test harnesses. A raw
 * JWT client may NOT push to arbitrary users.
 *
 * Body: { auth_uids?: string[], provider_ids?: string[], title: string, body: string, url?: string }
 *   provider_ids resolve to auth_uids: freelancer → its auth_uid; hive company → the
 *   hive's ACTIVE SUPERVISORS (they dispatch the crew).
 * Sends VAPID Web Push to every push_subscriptions row for those uids; a 404/410
 * endpoint is PRUNED (the harvested recipe: dead subscriptions must not accumulate);
 * a delivered endpoint stamps last_ok_at.
 *
 * Skills consulted: notifications (dead-endpoint hygiene), security (service-role gate,
 * no client-directed fan-out), multitenant-engineer (hive provider → supervisors only).
 * contract-allow: push fan-out; response = envelope { sent, pruned, failed, targets }.
 */
import { serveObserved } from "../_shared/observability.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";
import { requireServiceRole } from "../_shared/tenant-context.ts";
import { beginRequest, ok, fail } from "../_shared/envelope.ts";
import { handleHealth } from "../_shared/health.ts";
import { log } from "../_shared/logger.ts";
import webpush from "npm:web-push@3.6.7";

const FN_NAME = "notify-push";

const db = createClient(
  Deno.env.get("SUPABASE_URL") ?? "",
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "",
);

const VAPID_PUBLIC = Deno.env.get("WH_VAPID_PUBLIC_KEY") ?? "";
const VAPID_PRIVATE = Deno.env.get("WH_VAPID_PRIVATE_KEY") ?? "";
const VAPID_SUBJECT = Deno.env.get("WH_VAPID_SUBJECT") ?? "mailto:ops@workhiveph.com";

serveObserved(FN_NAME, async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders });

  const healthResp = await handleHealth(req, FN_NAME, async () => ({
    deps: [
      { name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) },
      { name: "vapid", ok: Boolean(VAPID_PUBLIC && VAPID_PRIVATE) },
    ],
  }));
  if (healthResp) return healthResp;

  const ctx = beginRequest(req, { route: FN_NAME });

  if (req.method !== "POST") {
    return fail(ctx, "method_not_allowed", "POST only.", { status: 405 });
  }

  const gate = await requireServiceRole(db, req);
  if (!gate.ok) return fail(ctx, gate.code, gate.message, { status: gate.status });

  if (!VAPID_PUBLIC || !VAPID_PRIVATE) {
    return fail(ctx, "vapid_unconfigured", "WH_VAPID_* env not set.", { status: 503 });
  }
  webpush.setVapidDetails(VAPID_SUBJECT, VAPID_PUBLIC, VAPID_PRIVATE);

  let body: { auth_uids?: string[]; provider_ids?: string[]; title?: string; body?: string; url?: string };
  try { body = await req.json(); } catch {
    return fail(ctx, "bad_json", "Body must be JSON.", { status: 400 });
  }
  if (!body.title || !body.body) {
    return fail(ctx, "missing_title_or_body", "Missing required field: title and body are both required.", { status: 400 });
  }

  // resolve targets
  const uids = new Set<string>((body.auth_uids ?? []).filter(Boolean));
  if (body.provider_ids && body.provider_ids.length) {
    // canonical-allow: dispatch target-resolution (provider_id -> deliverable auth_uids), identity plumbing not a KPI read
    const { data: provs } = await db.from("service_providers")
      .select("id, provider_type, auth_uid, hive_id").in("id", body.provider_ids).limit(100);
    const hiveIds: string[] = [];
    for (const p of provs ?? []) {
      if (p.auth_uid) uids.add(p.auth_uid);
      if (p.provider_type === "hive" && p.hive_id) hiveIds.push(p.hive_id);
    }
    if (hiveIds.length) {
      // canonical-allow: this is an AUDIENCE read, not a KPI read — "who are the active supervisors of
      // these hive providers?", so the push reaches a human who can actually accept the job. It renders
      // no metric anywhere; it resolves recipients. hive_members is the authority on membership, and it
      // is what auth_worker_names() / my_service_provider_ids() read for the same question. Sending a
      // notification to an audience computed from an analytics view would make delivery depend on a
      // reporting surface's refresh semantics.
      const { data: sups } = await db.from("hive_members")
        .select("auth_uid").in("hive_id", hiveIds).eq("role", "supervisor").eq("status", "active").limit(200);
      for (const s of sups ?? []) if (s.auth_uid) uids.add(s.auth_uid);
    }
  }
  if (!uids.size) return ok(ctx, { sent: 0, pruned: 0, failed: 0, targets: 0, note: "no target uids" });

  // canonical-allow: the fn's OWN delivery table (service-role send/prune mechanics, not a KPI read)
  const { data: subs } = await db.from("push_subscriptions")
    .select("*").in("auth_uid", [...uids]).limit(500);
  if (!subs || !subs.length) {
    return ok(ctx, { sent: 0, pruned: 0, failed: 0, targets: uids.size, note: "no subscriptions" });
  }

  const payload = JSON.stringify({
    title: body.title,
    body: body.body,
    url: body.url || "/workhive/marketplace-seller.html?tab=services",
  });
  let sent = 0, pruned = 0, failed = 0;
  for (const s of subs) {
    try {
      await webpush.sendNotification(
        { endpoint: s.endpoint, keys: { p256dh: s.p256dh, auth: s.auth } },
        payload,
      );
      sent++;
      await db.from("push_subscriptions").update({ last_ok_at: new Date().toISOString() }).eq("id", s.id);
    } catch (err) {
      const code = (err as { statusCode?: number }).statusCode;
      if (code === 404 || code === 410) { // dead endpoint — prune, never accumulate
        await db.from("push_subscriptions").delete().eq("id", s.id);
        pruned++;
      } else {
        failed++;
        // L-layer: a delivery that fails for a reason we do NOT prune on (VAPID mismatch,
        // push-service 5xx, payload too large) is otherwise invisible - the caller only ever
        // sees an aggregate count. Structured so it is greppable per endpoint.
        log.warn(ctx, "push_send_failed", { subscription_id: s.id, status_code: code });
      }
    }
  }
  log.info(ctx, "push_fanout_complete", { sent, pruned, failed, targets: uids.size });
  return ok(ctx, { sent, pruned, failed, targets: uids.size });
});
