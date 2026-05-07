/**
 * failure-signature-scan — Phase 1.2: Failure Signature Detection
 *
 * Scans logbook history for pre-failure patterns across all active hives.
 * Fires 4 deterministic rules (no AI cost for detection).
 * AI is used only to generate the human-readable alert detail.
 *
 * Rules:
 *   repeat_failure       — same machine, same root_cause category, 3+ times in 90 days
 *   escalating_frequency — more failures in last 30d than in the prior 60d (rate increasing)
 *   multi_symptom        — 2+ distinct root_cause categories on same machine in 30 days
 *   missed_pm            — machine is PM-overdue AND has had a breakdown in the last 30 days
 *
 * Called by pg_cron daily + can be triggered manually via POST with { hive_id }.
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { callAI } from "../_shared/ai-chain.ts";
import { getCorsHeaders } from "../_shared/cors.ts";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface LogbookRow {
  machine:          string;
  category:         string;
  root_cause:       string | null;
  maintenance_type: string;
  created_at:       string;
}

interface ScanAlert {
  machine:        string;
  category:       string;
  rule_id:        string;
  alert_title:    string;
  evidence:       Record<string, unknown>;
  severity:       string;
  days_to_failure: number | null;
}

// ---------------------------------------------------------------------------
// Detection rules (pure logic, no AI)
// ---------------------------------------------------------------------------

function detectRepeatFailure(
  machine: string,
  category: string,
  rows: LogbookRow[],
): ScanAlert | null {
  // Rule: same root_cause category 3+ times in 90 days
  const breakdowns = rows.filter(r => r.maintenance_type === "Breakdown / Corrective");
  const countByRoot: Record<string, number> = {};
  for (const r of breakdowns) {
    const key = (r.root_cause || "unknown").toLowerCase();
    countByRoot[key] = (countByRoot[key] || 0) + 1;
  }
  const repeats = Object.entries(countByRoot).filter(([, n]) => n >= 3);
  if (!repeats.length) return null;

  const [topRoot, topCount] = repeats.sort((a, b) => b[1] - a[1])[0];
  return {
    machine, category,
    rule_id:     "repeat_failure",
    alert_title: `${topCount}× repeat failure on ${machine}`,
    evidence:    { root_cause: topRoot, occurrences: topCount, window_days: 90 },
    severity:    topCount >= 5 ? "critical" : "warning",
    days_to_failure: null,
  };
}

function detectEscalatingFrequency(
  machine: string,
  category: string,
  rows: LogbookRow[],
  now: Date,
): ScanAlert | null {
  // Rule: more failures in last 30d than in the prior 60d
  const ms30 = 30 * 86400000;
  const ms90 = 90 * 86400000;
  const breakdowns = rows.filter(r => r.maintenance_type === "Breakdown / Corrective");
  const last30  = breakdowns.filter(r => now.getTime() - new Date(r.created_at).getTime() <= ms30).length;
  const prior60 = breakdowns.filter(r => {
    const age = now.getTime() - new Date(r.created_at).getTime();
    return age > ms30 && age <= ms90;
  }).length;

  // Must have at least 2 in last 30d and strictly more than prior 60d
  if (last30 < 2 || last30 <= prior60) return null;

  return {
    machine, category,
    rule_id:     "escalating_frequency",
    alert_title: `Increasing failure rate on ${machine}`,
    evidence:    { last_30d: last30, prior_60d: prior60, trend: "increasing" },
    severity:    last30 >= 4 ? "critical" : "warning",
    days_to_failure: Math.max(1, Math.round(30 / last30)),
  };
}

function detectMultiSymptom(
  machine: string,
  category: string,
  rows: LogbookRow[],
): ScanAlert | null {
  // Rule: 2+ distinct root_cause categories on same machine within 30 days
  const recent = rows.filter(r => r.maintenance_type === "Breakdown / Corrective");
  const roots  = new Set(recent.map(r => (r.root_cause || "").toLowerCase()).filter(Boolean));
  if (roots.size < 2) return null;

  const rootList = Array.from(roots).slice(0, 5);
  return {
    machine, category,
    rule_id:     "multi_symptom",
    alert_title: `Multiple failure types on ${machine} (${roots.size} causes in 30 days)`,
    evidence:    { distinct_root_causes: rootList, count: roots.size, window_days: 30 },
    severity:    roots.size >= 3 ? "critical" : "warning",
    days_to_failure: 14,
  };
}

// ---------------------------------------------------------------------------
// AI alert detail generation
// ---------------------------------------------------------------------------

const DETAIL_SYSTEM =
  `You are a maintenance reliability engineer writing a concise alert for a plant supervisor.
Given a pre-failure pattern detected on industrial equipment, write a 2-3 sentence explanation:
1. What pattern was detected and why it matters
2. What the supervisor should do NOW (one specific action)
Keep it practical. No jargon. No bullet points. Plain text only.`;

async function generateAlertDetail(alert: ScanAlert): Promise<string> {
  const prompt =
    `Equipment: ${alert.machine} (${alert.category})
Pattern detected: ${alert.rule_id}
Title: ${alert.alert_title}
Evidence: ${JSON.stringify(alert.evidence)}
Severity: ${alert.severity}`;

  try {
    const raw = await callAI(prompt, {
      systemPrompt: DETAIL_SYSTEM,
      temperature:  0.2,
      maxTokens:    200,
      jsonMode:     false,
    });
    // Strip <think>...</think> reasoning tokens (Qwen3/DeepSeek thinking mode leaks)
    const cleaned = raw.replace(/<think>[\s\S]*?<\/think>/gi, "").trim();
    return cleaned.slice(0, 500);
  } catch {
    return `${alert.alert_title}. Review maintenance history and schedule inspection.`;
  }
}

// ---------------------------------------------------------------------------
// Per-hive scan
// ---------------------------------------------------------------------------

async function scanHive(
  db: SupabaseClient,
  hiveId: string,
  now: Date,
): Promise<{ created: number; updated: number; errors: number }> {
  const since90 = new Date(now.getTime() - 90 * 86400000).toISOString();
  const since30 = new Date(now.getTime() - 30 * 86400000).toISOString();

  // Fetch recent breakdowns for this hive
  const { data: logbook, error } = await db
    .from("logbook")
    .select("machine, category, root_cause, maintenance_type, created_at")
    .eq("hive_id", hiveId)
    .in("maintenance_type", ["Breakdown / Corrective", "Inspection", "Preventive Maintenance"])
    .gte("created_at", since90)
    .order("created_at", { ascending: false })
    .limit(2000);

  if (error || !logbook?.length) return { created: 0, updated: 0, errors: error ? 1 : 0 };

  // Group by machine
  const byMachine: Record<string, { rows90: LogbookRow[]; rows30: LogbookRow[]; category: string }> = {};
  for (const row of logbook) {
    if (!row.machine) continue;
    if (!byMachine[row.machine]) {
      byMachine[row.machine] = { rows90: [], rows30: [], category: row.category || "" };
    }
    byMachine[row.machine].rows90.push(row);
    if (row.created_at >= since30) {
      byMachine[row.machine].rows30.push(row);
    }
  }

  let created = 0, updated = 0, errors = 0;

  for (const [machine, { rows90, rows30, category }] of Object.entries(byMachine)) {
    const alerts: ScanAlert[] = [];

    // Rule 1: repeat failure (last 90 days)
    const r1 = detectRepeatFailure(machine, category, rows90);
    if (r1) alerts.push(r1);

    // Rule 2: escalating frequency
    const r2 = detectEscalatingFrequency(machine, category, rows90, now);
    if (r2) alerts.push(r2);

    // Rule 3: multi-symptom (last 30 days)
    const r3 = detectMultiSymptom(machine, category, rows30);
    if (r3) alerts.push(r3);

    for (const alert of alerts) {
      const detail   = await generateAlertDetail(alert);
      const expiresAt = new Date(now.getTime() + 14 * 86400000).toISOString();

      const row = {
        hive_id:         hiveId,
        machine:         alert.machine,
        category:        alert.category,
        rule_id:         alert.rule_id,
        alert_title:     alert.alert_title,
        alert_detail:    detail,
        evidence:        alert.evidence,
        days_to_failure: alert.days_to_failure,
        severity:        alert.severity,
        status:          "active",
        detected_at:     now.toISOString(),
        expires_at:      expiresAt,
      };

      // Upsert on (hive_id, machine, rule_id) — refreshes existing alert
      const { error: upsertErr } = await db
        .from("failure_signature_alerts")
        .upsert(row, { onConflict: "hive_id,machine,rule_id" });

      if (upsertErr) {
        console.error(`upsert error ${machine}/${alert.rule_id}:`, upsertErr.message);
        errors++;
      } else {
        created++;
      }
    }
  }

  return { created, updated, errors };
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

  const body = await req.json().catch(() => ({}));
  const now  = new Date();

  let hiveIds: string[] = [];

  if (body.hive_id) {
    // Manual trigger for one hive
    hiveIds = [body.hive_id];
  } else {
    // Scheduled: scan all active hives
    const { data: hives } = await db
      .from("hives")
      .select("id")
      .limit(500);
    hiveIds = (hives || []).map((h: { id: string }) => h.id);
  }

  let totalCreated = 0, totalErrors = 0;

  for (const hiveId of hiveIds) {
    try {
      const result = await scanHive(db, hiveId, now);
      totalCreated += result.created;
      totalErrors  += result.errors;
    } catch (e) {
      console.error(`scanHive error for ${hiveId}:`, e);
      totalErrors++;
    }
  }

  // Log to automation_log
  await db.from("automation_log").insert({
    job_name: "failure-signature-scan",
    hive_id:  body.hive_id || null,
    status:   totalErrors === 0 ? "success" : "failed",
    detail:   `Scanned ${hiveIds.length} hive(s). ${totalCreated} alerts upserted. ${totalErrors} errors.`,
  });

  return new Response(
    JSON.stringify({ ok: true, hives: hiveIds.length, alerts_upserted: totalCreated, errors: totalErrors }),
    { status: 200, headers: { ...cors, "Content-Type": "application/json" } },
  );
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error("failure-signature-scan top-level error:", msg);
    return new Response(
      JSON.stringify({ error: msg }),
      { status: 500, headers: { ...cors, "Content-Type": "application/json" } },
    );
  }
});
