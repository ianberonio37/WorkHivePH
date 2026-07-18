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

const REPORT_META: Record<string, { label: string; color: string; link: string }> = {
  pm_overdue:     { label: "PM Overdue",          color: "#F7A21B", link: "https://workhiveph.com/pm-scheduler.html" },
  failure_digest: { label: "Failure Digest",      color: "#ef4444", link: "https://workhiveph.com/logbook.html"      },
  shift_handover: { label: "Shift Handover",      color: "#29B6D9", link: "https://workhiveph.com/logbook.html"      },
  predictive:     { label: "Predictive Analysis", color: "#a78bfa", link: "https://workhiveph.com/analytics.html"    },
  oee:            { label: "OEE Summary",          color: "#22c55e", link: "https://workhiveph.com/analytics.html"    },
  descriptive:    { label: "Weekly Analytics",    color: "#6366f1", link: "https://workhiveph.com/analytics.html"    },
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
  sentAt: string
): string {
  const cards = reports.map(r => {
    const meta  = REPORT_META[r.type] ?? { label: r.type, color: "#F7A21B", link: "https://workhiveph.com" };
    const safeSummary = esc(r.summary);
    const safeLabel   = esc(meta.label);   // r.type on the unknown-type fallback = client-controlled
    return `
      <div style="background:#1a2a3d;border-left:3px solid ${meta.color};padding:16px 20px;margin-bottom:8px;border-radius:0 8px 8px 0;">
        <div style="font-size:10px;font-weight:700;color:${meta.color};text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px;">${safeLabel}</div>
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
        Sent via <a href="https://workhiveph.com" style="color:#F7A21B;text-decoration:none;">WorkHive</a> Report Sender
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
    const { hive_id, recipient_email, reports, sent_at } = await req.json();

    // Input validation — hive_id is optional (workers without hive context can still send)
    if (!recipient_email || !Array.isArray(reports) || reports.length === 0) {
      return new Response(
        JSON.stringify({ error: "Missing required fields: recipient_email, reports" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    if (!isValidEmail(recipient_email)) {
      return new Response(
        JSON.stringify({ error: "Invalid recipient email address" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const resendKey = Deno.env.get("RESEND_API_KEY");
    if (!resendKey) {
      return new Response(
        JSON.stringify({ error: "Email service not configured — set RESEND_API_KEY in secrets" }),
        { status: 503, headers: { ...corsHeaders, "Content-Type": "application/json" } }
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
        if (!_rl.allowed) return soloRateLimitedResponse(corsHeaders);
      }
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
    const sentAt = new Date(sent_at || Date.now()).toLocaleDateString("en-PH", {
      month: "short", day: "numeric", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });

    const reportLabels = reports
      .map((r: { type: string }) => REPORT_META[r.type]?.label ?? r.type)
      .join(" + ");
    const subject = `[WorkHive] ${reportLabels} - ${sentAt}`;
    const html    = buildEmailHtml(hiveName, reports, sentAt);

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
      await db.from("automation_log").insert({
        job_name: "send_report_email", hive_id, status: "deferred",
        detail: "Resend circuit-breaker open (recent failures) — not attempted",
      });
      return new Response(
        JSON.stringify({ error: "Email service temporarily unavailable — please try again shortly." }),
        { status: 503, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }
    const emailRes = await fetch("https://api.resend.com/emails", {
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
    await db.from("automation_log").insert({
      job_name: "send_report_email",
      hive_id,
      status:   "success",
      detail:   `Sent ${reports.length} report(s) to ${recipient_email}`,
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
