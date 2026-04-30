import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";

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

function buildEmailHtml(
  hiveName: string,
  reports: Array<{ type: string; summary: string }>,
  sentAt: string
): string {
  const cards = reports.map(r => {
    const meta  = REPORT_META[r.type] ?? { label: r.type, color: "#F7A21B", link: "https://workhiveph.com" };
    // Escape for HTML context — prevent stored XSS from summary content
    const safeSummary = r.summary
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
    return `
      <div style="background:#1a2a3d;border-left:3px solid ${meta.color};padding:16px 20px;margin-bottom:8px;border-radius:0 8px 8px 0;">
        <div style="font-size:10px;font-weight:700;color:${meta.color};text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px;">${meta.label}</div>
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
      <p style="color:#7B8794;font-size:12px;margin:0;">${hiveName} &middot; ${sentAt}</p>
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

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

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

    // Hive lookup — optional. If hive_id is null (e.g. worker cleared cache),
    // skip verification and rate limiting; use "WorkHive" as display name.
    let hiveName = "WorkHive";
    if (hive_id) {
      const { data: hive } = await db
        .from("hives").select("id, name").eq("id", hive_id).single();
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
    const emailRes = await fetch("https://api.resend.com/emails", {
      method: "POST",
      signal: AbortSignal.timeout(30000),
      headers: {
        "Authorization": `Bearer ${resendKey}`,
        "Content-Type": "application/json",
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
    console.error("send-report-email error:", err);
    return new Response(
      JSON.stringify({ error: err instanceof Error ? err.message : String(err) }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
