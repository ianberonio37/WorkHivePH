import { serveObserved, failTracked } from "../_shared/observability.ts";
import { handleHealth } from "../_shared/health.ts";
import { logRequestStart } from "../_shared/logger.ts";

// capability: report_email_dispatch

// contract-allow: email sender
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";
import { log } from "../_shared/logger.ts";
// Pillar I (Gateway Spine): verify hive membership before emailing a hive's report.
import { resolveIdentity, resolveTenancy } from "../_shared/tenant-context.ts";
// Arc R (A01/spam): bound the no-hive_id (solo) email path by identity/IP.
import { checkSoloRateLimit, soloRateLimitKey, soloRateLimitedResponse } from "../_shared/rate-limit.ts";
// Arc S F-lens (F-010): reuse the AI provider-health circuit-breaker for the
// external Resend dependency so a sustained outage stops hammering it (escalating
// cooldown) and fails fast with a clear "temporarily unavailable" instead of a
// per-call 502 on every attempt.
import { isSlotBlocked, recordSlotFailure, recordSlotSuccess } from "../_shared/provider-health.ts";
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

// ── Report metadata ───────────────────────────────────────────────────────────

// ★EVERY FIGURE CARRIES ITS WINDOW. The recipient sees a number and a date and has no way to know
// whether "failures" means 7 days or 90 - and these report types genuinely disagree: the failure
// digest asks the RPCs for 7 days (scheduled-agents PERIOD=7), predictive asks for 90
// (get_mtbf_by_machine p_period_days:90), handover reads the last 8 hours, and PM Overdue is not a
// window at all - it is current scope state, true only as of the moment it ran. A date alone reads
// as "this is the news today" for all four, which is wrong for three of them. `window` is the
// qualifier, rendered NEXT TO the label rather than in a footer, because a qualifier that sits far
// from its figure is one the reader has already passed.
// T106 (2026-08-26): THE LINK DROPPED WHAT THE REPORT WAS ABOUT. Every "View in WorkHive" pointed
// at a bare page root, so a PM Overdue report - a document whose entire subject is the overdue set -
// landed the reader on the unfiltered schedule, and both logbook reports landed on the page's
// default MINE view while the report itself is hive-wide (T19's two-windows-one-metric mismatch,
// arriving by email this time). Measured before changing anything: ?filter=overdue is a real
// accepted value on pm-scheduler (chips all/mine/overdue/duesoon/ontrack) and it genuinely filters -
// live reading gave ontrack 0 rows, duesoon 2, overdue 10 against 10 for bare, so the parameter
// does work rather than merely highlighting a chip. ?view=team on logbook is T19's own deep link.
// The remaining five point at analytics.html and project-manager.html, which read NO query params
// at all (param_route_registry), so their links are already as specific as those pages allow -
// recorded here so a future reader knows it is a page limit, not an oversight.
const REPORT_META: Record<string, { label: string; color: string; link: string; window: string }> = {
  pm_overdue:     { label: "PM Overdue",          color: "#F7A21B", link: "https://workhiveph.com/pm-scheduler.html?filter=overdue" , window: "current status as of this report"},
  failure_digest: { label: "Failure Digest",      color: "#ef4444", link: "https://workhiveph.com/logbook.html?view=team"      , window: "last 7 days"},
  shift_handover: { label: "Shift Handover",      color: "#29B6D9", link: "https://workhiveph.com/logbook.html?view=team"      , window: "last 8 hours"},
  predictive:     { label: "Predictive Analysis", color: "#a78bfa", link: "https://workhiveph.com/analytics.html"    , window: "last 90 days"},
  oee:            { label: "OEE Summary",          color: "#22c55e", link: "https://workhiveph.com/analytics.html"    , window: ""},
  descriptive:    { label: "Weekly Analytics",    color: "#6366f1", link: "https://workhiveph.com/analytics.html"    , window: ""},
  project_risk:   { label: "Project Risk",         color: "#f97316", link: "https://workhiveph.com/project-manager.html", window: "last 30 days"},
  project_suggestions: { label: "Project Suggestions", color: "#14b8a6", link: "https://workhiveph.com/project-manager.html", window: "last 90 days"},
};

// ── Email helpers ─────────────────────────────────────────────────────────────

function isValidEmail(e: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e.trim());
}

// HTML-escape for any string rendered into the email body. EVERY dynamic sink
// must pass through this — not just `summary`. `r.type` (→ meta.label on the
// unknown-type fallback) is client-controlled and `hiveName` is stored DB text;
// both are attacker-influenceable → HTML/link-injection in an authed, branded
// email relay if left raw. (Analytics Engine arc, I3/I6, 2026-07-10.)
function esc(s: unknown): string {
  return String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function buildEmailHtml(
  hiveName: string,
  reports: Array<{ type: string; summary: string }>,
  sentAt: string,
  senderName = "",
): string {
  const cards = reports.map(r => {
    const meta  = REPORT_META[r.type] ?? { label: r.type, color: "#F7A21B", link: "https://workhiveph.com", window: "" };
    const safeSummary = esc(r.summary);
    const safeLabel   = esc(meta.label);   // r.type on the unknown-type fallback = client-controlled
    return `
      <div style="background:#1a2a3d;border-left:3px solid ${meta.color};padding:16px 20px;margin-bottom:8px;border-radius:0 8px 8px 0;">
        <div style="font-size:10px;font-weight:700;color:${meta.color};text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px;">${safeLabel}${meta.window ? ` <span style="font-weight:600;color:#8fa3bd;text-transform:none;letter-spacing:0;">&middot; ${esc(meta.window)}</span>` : ""}</div>
        <p style="color:#d4dce8;font-size:14px;line-height:1.55;margin:0 0 10px;">${safeSummary}</p>
        <a href="${meta.link}" style="font-size:11px;font-weight:600;color:${meta.color};text-decoration:none;">View in WorkHive &rarr;</a>
      </div>`;
  }).join("");

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>WorkHive Report</title>
</head>
<body style="margin:0;padding:0;background:#0f1923;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
  <div style="max-width:560px;margin:0 auto;padding:24px 16px;">

    <div style="background:#162032;border-radius:12px 12px 0 0;padding:24px 28px;border-bottom:1px solid rgba(247,162,27,0.2);">
      <div style="font-size:10px;font-weight:700;color:#F7A21B;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:8px;">WorkHive</div>
      <h1 style="color:#ffffff;font-size:20px;font-weight:800;margin:0 0 4px;line-height:1.2;">Maintenance Report</h1>
      <p style="color:#7B8794;font-size:12px;margin:0;">${esc(hiveName)} &middot; ${esc(sentAt)}</p>
    </div>

    <div style="background:#111e2d;padding:20px 28px;">
      ${cards}
    </div>

    <div style="background:#0d1820;border-radius:0 0 12px 12px;padding:16px 28px;border-top:1px solid rgba(255,255,255,0.05);text-align:center;">
      <p style="color:#4a5568;font-size:11px;margin:0;">
        Sent by ${esc(senderName || "a WorkHive supervisor")} &middot; ${esc(hiveName)} via <a href="https://workhiveph.com" style="color:#F7A21B;text-decoration:none;">WorkHive</a> Report Sender.<br/>
        To stop receiving these reports, ask the sender to remove you from their recipient list.
      </p>
    </div>

  </div>
</body>
</html>`;
}

// ── Entry point ───────────────────────────────────────────────────────────────

serveObserved("send-report-email", async (req) => {
  // Arc T/T1: standard liveness /health (fn up + DB creds reachable).
  const _health = await handleHealth(req, "send-report-email", async () => ({
    deps: [{ name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) }],
  }));
  if (_health) return _health;
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  logRequestStart(req, "send-report-email");  // I6 observability

  try {
    // T111 (2026-08-25): sender_name is optional and display-only — the recipient of an
    // outward, irreversible send deserves to know WHICH person sent it and how to stop it;
    // auth still gates the send (authUid below), so a spoofed name cannot send mail.
    // ★A CALLER'S MISTAKE IS NOT A SERVER ERROR (live-walk wave, 2026-09-06): a broken body and a GET both
    // reached `await req.json()` and came back 500.
    if (req.method !== "POST") {
      return new Response(JSON.stringify({ error: "That action is not allowed here. Reload the page and try again." }),
        { status: 405, headers: { ...corsHeaders, "Content-Type": "application/json" } });
    }
    let _whBody;
    try { _whBody = await req.json(); } catch {
      return new Response(JSON.stringify({ error: "That request could not be read. Reload the page and try again." }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } });
    }
    const { hive_id, recipient_email, reports, sent_at, sender_name } = _whBody;

    // Input validation — hive_id is optional (workers without hive context can still send)
    if (!recipient_email || !Array.isArray(reports) || reports.length === 0) {
      return new Response(
        JSON.stringify({ error: "Missing required fields: recipient_email, reports" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    if (!isValidEmail(recipient_email)) {
      return new Response(
        JSON.stringify({ error: "That recipient email address is not valid. Check it and try again." }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const db = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    // Pillar I: emailing a hive's report is scoped by the client hive_id on a
    // service-role client — verify membership so a worker can't email another
    // hive's data. hive_id is optional (solo); verify only when claimed.
    if (hive_id) {
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
    } else {
      // Arc R (A01/spam): no hive_id = solo send. The old code skipped BOTH membership
      // and rate-limit, leaving an unauthenticated branded-email relay (phishing/spam) —
      // anyone could POST {recipient_email, reports} and send mail from the WorkHive domain.
      // Require a real identity (a solo worker still has a session) + a solo rate-limit.
      const { authUid, isServiceRole } = await resolveIdentity(db, req);
      if (!isServiceRole) {
        if (!authUid) {
          return new Response(
            JSON.stringify({ error: "Authentication required to send email", code: "unauthorized" }),
            { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } },
          );
        }
        const _ip = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim();
        const _rl = await checkSoloRateLimit(db, soloRateLimitKey(authUid, _ip));
        if (!_rl.allowed) return soloRateLimitedResponse(corsHeaders, _rl.retry_after_seconds);
      }
    }

    /* W3-FN (2026-09-09): this check used to sit ABOVE the two branches you just passed, so the FIRST
       thing anyone learned - member, stranger or unauthenticated caller alike - was the state of the
       platform's mail configuration. Authorize first, then talk about the system: a caller with no
       relationship to this hive should be told they are not a member, not handed a fact about how
       finished the platform is. Nothing was ever SENT out of order (the send is far below), so this is
       about what the refusal says rather than about a leaked action - but "who are you" is the question
       that belongs first, and answering it first is also what makes the refusal contract PROVABLE:
       while the 503 came first, a foreign-hive request and an own-hive request were indistinguishable,
       so no probe could show this function refuses a stranger at all. */
    const resendKey = Deno.env.get("RESEND_API_KEY");
    if (!resendKey) {
      console.error("misconfigured: RESEND_API_KEY is not set");   // the operator detail stays in the log (2026-09-06)
      return new Response(
        JSON.stringify({ error: "Email sending is not set up yet. Ask the platform owner to finish it." }),
        { status: 503, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Hive lookup — optional. If hive_id is null (e.g. worker cleared cache),
    // skip verification and rate limiting; use "WorkHive" as display name.
    let hiveName = "WorkHive";
    if (hive_id) {
      const { data: hive } = await db
        .from("v_hives_truth").select("id, name").eq("id", hive_id).single();
      if (hive) hiveName = hive.name;

      // Rate limit: max 20 successful email sends per hive per hour
      const windowStart = new Date(Date.now() - 60 * 60 * 1000).toISOString();
      const { count: recentSends } = await db
        .from("automation_log")
        .select("*", { count: "exact", head: true })
        .eq("hive_id", hive_id)
        .eq("job_name", "send_report_email")
        .eq("status", "success")
        .gte("triggered_at", windowStart);

      if ((recentSends ?? 0) >= 20) {
        return new Response(
          JSON.stringify({ error: "Email rate limit reached (20/hour per hive). Try again later." }),
          { status: 429, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
    }

    // Build subject and HTML
    // ★"en-PH" IS A FORMAT, NOT A CLOCK (T109, 2026-09-07). The locale decides the ORDER and the wording;
    // without an explicit timeZone the value is rendered in whatever zone the runtime is in, which on
    // Supabase Edge is UTC. So this subject line carried a Philippine label on a UTC time and read eight
    // hours early for every recipient - "Sep 6, 04:00 PM" on an email that arrived at midnight on the
    // 7th in Manila. The label made it look considered, which is what made it hard to notice.
    const sentAt = new Date(sent_at || Date.now()).toLocaleDateString("en-PH", {
      timeZone: "Asia/Manila",
      month: "short", day: "numeric", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });

    const reportLabels = reports
      .map((r: { type: string }) => REPORT_META[r.type]?.label ?? r.type)
      .join(" + ");
    const subject = `[WorkHive] ${reportLabels} - ${sentAt}`;
    const html    = buildEmailHtml(hiveName, reports, sentAt, typeof sender_name === 'string' ? sender_name.slice(0, 80) : '');

    // Send via Resend
    // Note: verify workhiveph.com in your Resend dashboard before going live.
    // For testing, replace from with "onboarding@resend.dev".
    //
    // Idempotency-Key derived from recipient + report types + hour-precision
    // timestamp so a retry within the hour collapses to the same Resend send,
    // preventing the recipient from receiving the same digest twice. Resend
    // honors the standard Idempotency-Key header (24h dedup window).
    const reportTypesKey = reports
      .map((r: { type: string }) => r.type)
      .sort().join("+") || "none";
    const hourBucket = new Date(sent_at || Date.now()).toISOString().slice(0, 13); // YYYY-MM-DDTHH
    const recipientSlug = recipient_email.trim().toLowerCase().replace(/[^a-z0-9._@-]/g, "_");
    const emailIdemKey = `report-${hive_id || "anon"}-${recipientSlug}-${reportTypesKey}-${hourBucket}`;
    // Arc S F-lens (F-010): circuit-breaker — if Resend has been failing, fail fast
    // with a clear "temporarily unavailable" instead of attempting + 502-ing again.
    if (isSlotBlocked("resend")) {
      // T112 (2026-08-26): this row was never stored. automation_log's CHECK allows
      // success|failed|skipped|warning, "deferred" matched none, and the insert error was not
      // read — so the circuit-breaker's own audit trail was refused with 23514 and discarded in
      // silence. Nobody could learn the breaker had tripped, which is precisely the moment an
      // operator needs the log. "skipped" is not a compromise here: the breaker's meaning IS
      // "we did not attempt this", and that word already exists for it.
      const { error: _brkLogErr } = await db.from("automation_log").insert({
        job_name: "send_report_email", hive_id, status: "skipped",
        detail: "Email is paused for now. Try again in a few minutes.",
      });
      if (_brkLogErr) console.error("automation_log write failed:", _brkLogErr.message);
      return new Response(
        JSON.stringify({ error: "Email service temporarily unavailable — please try again shortly." }),
        { status: 503, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }
    /* W3-FN (2026-09-09): the send endpoint is configurable so the send PATH can be walked without mail
       leaving the machine. PRODUCTION IS UNCHANGED - with RESEND_BASE_URL unset this is byte-identical
       to the hardcoded https://api.resend.com it replaces. Two sessions in a row recorded the same
       ceiling ("end-to-end confirmation needs RESEND_API_KEY, and I did not set one, because a
       successful call sends real email"), and that ceiling was real as long as the only way to open the
       config gate was to point a probe at the live Resend account. A base URL is the local substitute:
       set it at a capture sink and every branch below - the ok path, the !ok path, the breaker, the
       automation_log write and what the function persists - runs exactly as it does in production,
       against something that cannot deliver to a human. */
    const resendBase = (Deno.env.get("RESEND_BASE_URL") || "https://api.resend.com").replace(/\/+$/, "");
    const emailRes = await fetch(`${resendBase}/emails`, {
      method: "POST",
      signal: AbortSignal.timeout(30000),
      headers: {
        "Authorization":   `Bearer ${resendKey}`,
        "Content-Type":    "application/json",
        "Idempotency-Key": emailIdemKey,
      },
      body: JSON.stringify({
        from:    "WorkHive <reports@workhiveph.com>",
        to:      [recipient_email.trim()],
        subject,
        html,
      }),
    });

    const emailData = await emailRes.json();

    if (!emailRes.ok) {
      // Arc S F-lens (F-010): record the failure so the breaker escalates its cooldown
      // (honor Retry-After when Resend supplies it on a 429/503).
      const _ra = Number(emailRes.headers.get("retry-after"));
      recordSlotFailure("resend", Number.isFinite(_ra) && _ra > 0 ? _ra * 1000 : undefined);
  // unchecked-write-allow: a telemetry row. Its failure must not change the caller's outcome - refusing real work because a log line did not land would be the worse bug.
      await db.from("automation_log").insert({
        job_name: "send_report_email",
        hive_id,
        status:   "failed",
        detail:   emailData.message ?? `Resend HTTP ${emailRes.status}`,
      });
      return new Response(
        JSON.stringify({ error: emailData.message ?? "Email send failed" }),
        { status: 502, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    recordSlotSuccess("resend"); // Arc S F-lens (F-010): a good send resets the breaker
  // unchecked-write-allow: a telemetry row. Its failure must not change the caller's outcome - refusing real work because a log line did not land would be the worse bug.
    await db.from("automation_log").insert({
      job_name: "send_report_email",
      hive_id,
      status:   "success",
      // The provider's message id is the only key an asynchronous bounce can be joined back to.
      // It was previously returned to the caller and then dropped, so a bounce arriving minutes
      // later had nothing to match against. resend-webhook-receiver greps this detail for it.
      detail:   `Sent ${reports.length} report(s) to ${recipient_email} [resend_id=${emailData.id}]`,
    });

    return new Response(
      JSON.stringify({ sent: true, message_id: emailData.id }),
      { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );

  } catch (err) {
    log.error(null, "send-report-email error:", { detail: err });
    // T2b: aggregate this HANDLED failure to wh_traces + non-leaky 500.
    return await failTracked(req, "send-report-email", "send_report_email_error", err);
  }
});
