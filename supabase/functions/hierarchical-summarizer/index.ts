/**
 * hierarchical-summarizer — Phase 2 of AGENTIC_RAG_ROADMAP.md.
 *
 * Pre-computes Daily → Weekly → Monthly → Quarterly → Yearly summaries per
 * hive per asset and writes them to canonical_period_summaries. The
 * agentic-rag-loop Retriever (Phase 1) then pulls the appropriate level
 * instead of dumping raw logbook rows into the model's context.
 *
 * Architecture (the deterministic-engine + light-LLM-synthesis principle):
 *   1. Read v_logbook_truth for the period via canonical view (SQL, deterministic).
 *   2. Aggregate failure_count, mtbf_days, mttr_h, top assets, top root causes,
 *      pm_overdue, downtime_h → structured JSON (TS, deterministic).
 *   3. Generate 1-2 paragraph natural-language digest via callAI (free-tier).
 *
 * Trigger: pg_cron daily at 02:00 PHT (after batch-risk-scoring at 13:00 PHT
 * the previous day). Spread across off-peak hours to avoid TPM contention
 * with live agentic-rag-loop traffic.
 *
 * Body:
 *   { hive_id, level, period_start?: ISO-date, period_end?: ISO-date,
 *     asset_tag?: string }
 *   - level required; if period_start omitted, defaults to "previous period"
 *     (yesterday for day, last week for week, last month for month, etc.)
 *   - asset_tag optional: omit for a hive-level rollup
 *
 * Response: { ok: bool, written: int, skipped: int, errors: [string] }
 *
 * Free-tier model constraint: every callAI call routes through
 * _shared/ai-chain.ts. No paid Claude / OpenAI tier. See
 * feedback_free_tier_only_models.md and AGENTIC_RAG_ROADMAP.md §2.5.
 *
 * Skills consulted: ai-engineer (callAI, system prompt as const, JSON
 * output, no em dashes), architect (4-place sync, RLS via service role
 * only), data-engineer (hive scoping, narrow selects, row caps, canonical
 * view reads), performance (no client-side aggregation — SQL does the math).
 *
 * contract-allow: scheduled rollup writer; output schema documented above.
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { callAI } from "../_shared/ai-chain.ts";
import { log } from "../_shared/logger.ts";
import { logAICost, estimateTokens } from "../_shared/cost-log.ts";
import { getCorsHeaders } from "../_shared/cors.ts";
// Pillar I (Gateway Spine): verify hive membership before service-role reads.
import { resolveIdentity, resolveTenancy } from "../_shared/tenant-context.ts";
// P1 roadmap 2026-05-26: adoption of envelope + /health.
import { beginRequest, ok } from "../_shared/envelope.ts";
import { handleHealth } from "../_shared/health.ts";

const FN_NAME           = "hierarchical-summarizer";
const MAX_TOKENS_DIGEST = 320;          // 1-2 paragraph budget
const ROW_CAP           = 500;          // never aggregate more than this per period
const LEVELS            = ["day","week","month","quarter","year"] as const;
type Level = typeof LEVELS[number];

const DIGEST_SYSTEM = `You write a 1 to 2 paragraph operational digest summarising a period of industrial maintenance activity.

You receive structured statistics: failure_count, mtbf_days, mttr_h, top_assets, top_root_causes, pm_overdue, downtime_h.

Rules:
1. Use ONLY the structured stats provided. Never invent numbers.
2. Cite the period boundary (e.g. "March 2026", "Q1 2026", "the week of 2026-03-04").
3. Mention top 1-2 assets and top 1-2 root causes by name only if their counts >= 2.
4. If failure_count is 0, write a brief one-sentence note that the period was clean.
5. If pm_overdue > 0, name it explicitly.
6. No em dashes. Use colons, commas, parentheses, or restructure.
7. Keep under 120 words total.
8. Use Filipino industrial vocabulary (PEC 2017, PSME, ISO 14224) when appropriate.

Respond JSON only:
{ "summary_text": "<digest>", "standard_cites": ["<ISO standard refs cited, e.g. ISO 14224:2016#7.1>"] }`;

const _URL = Deno.env.get("SUPABASE_URL") || "";
const _KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
if (!_URL || !_KEY) log.warn(null, "[hierarchical-summarizer] SUPABASE env vars missing");
const _warm = _URL && _KEY ? createClient(_URL, _KEY) : null;
void _warm;

// ── Period math (UTC+8 / PHT) ────────────────────────────────────────────────

function previousPeriod(level: Level, now: Date = new Date()): { start: string; end: string } {
  // All dates returned as YYYY-MM-DD strings (date-only).
  const utc = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  if (level === "day") {
    const start = new Date(utc); start.setUTCDate(start.getUTCDate() - 1);
    return { start: start.toISOString().slice(0,10), end: start.toISOString().slice(0,10) };
  }
  if (level === "week") {
    // ISO week boundary: last Monday → Sunday
    const day = utc.getUTCDay(); // 0..6 (Sun..Sat)
    const offsetToLastMon = day === 0 ? 6 : day - 1 + 7;
    const start = new Date(utc); start.setUTCDate(start.getUTCDate() - offsetToLastMon);
    const end   = new Date(start); end.setUTCDate(end.getUTCDate() + 6);
    return { start: start.toISOString().slice(0,10), end: end.toISOString().slice(0,10) };
  }
  if (level === "month") {
    const y = utc.getUTCFullYear(), m = utc.getUTCMonth();
    const start = new Date(Date.UTC(y, m - 1, 1));
    const end   = new Date(Date.UTC(y, m, 0));
    return { start: start.toISOString().slice(0,10), end: end.toISOString().slice(0,10) };
  }
  if (level === "quarter") {
    const y = utc.getUTCFullYear(), m = utc.getUTCMonth();
    const q = Math.floor(m / 3);
    const prevQ = q === 0 ? 3 : q - 1;
    const prevY = q === 0 ? y - 1 : y;
    const start = new Date(Date.UTC(prevY, prevQ * 3, 1));
    const end   = new Date(Date.UTC(prevY, prevQ * 3 + 3, 0));
    return { start: start.toISOString().slice(0,10), end: end.toISOString().slice(0,10) };
  }
  // year
  const y = utc.getUTCFullYear();
  return { start: `${y-1}-01-01`, end: `${y-1}-12-31` };
}

// ── Deterministic aggregation (no LLM) ───────────────────────────────────────

interface LogRow {
  id: string;
  machine: string | null;
  maintenance_type: string | null;
  root_cause: string | null;
  downtime_hours: number | null;
  status: string | null;
  created_at: string;
  closed_at: string | null;
}

interface SummaryJson {
  failure_count:    number;
  mtbf_days:        number | null;
  mttr_h:           number | null;
  pm_overdue:       number;
  downtime_h:       number;
  top_assets:       Array<{ name: string; count: number }>;
  top_root_causes:  Array<{ cause: string; count: number }>;
  closed_count:     number;
  open_count:       number;
  row_count:        number;
}

function aggregate(rows: LogRow[]): SummaryJson {
  const corrective = rows.filter(r => r.maintenance_type === "Breakdown / Corrective");
  const closed = corrective.filter(r => r.status === "Closed" && r.closed_at);

  // MTBF = mean inter-arrival of corrective entries (canonical formula per ISO 14224)
  let mtbf_days: number | null = null;
  if (corrective.length >= 2) {
    const sorted = corrective.slice().sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at));
    const intervals: number[] = [];
    for (let i = 1; i < sorted.length; i++) {
      const dt = (Date.parse(sorted[i].created_at) - Date.parse(sorted[i-1].created_at)) / 86400000;
      if (Number.isFinite(dt) && dt > 0) intervals.push(dt);
    }
    if (intervals.length) mtbf_days = +(intervals.reduce((a,b) => a + b, 0) / intervals.length).toFixed(2);
  }

  // MTTR = mean downtime_hours of closed corrective entries
  let mttr_h: number | null = null;
  if (closed.length) {
    const dts = closed.map(r => Number(r.downtime_hours || 0)).filter(n => n > 0);
    if (dts.length) mttr_h = +(dts.reduce((a,b) => a + b, 0) / dts.length).toFixed(2);
  }

  const downtime_h = +corrective.reduce((a, r) => a + Number(r.downtime_hours || 0), 0).toFixed(2);

  // Top assets by corrective count
  const assetMap: Record<string, number> = {};
  for (const r of corrective) {
    const k = (r.machine || "unknown").trim();
    assetMap[k] = (assetMap[k] || 0) + 1;
  }
  const top_assets = Object.entries(assetMap)
    .sort((a, b) => b[1] - a[1]).slice(0, 5)
    .map(([name, count]) => ({ name, count }));

  // Top root causes
  const causeMap: Record<string, number> = {};
  for (const r of corrective) {
    const c = (r.root_cause || "unknown").trim().toLowerCase();
    if (c && c !== "unknown") causeMap[c] = (causeMap[c] || 0) + 1;
  }
  const top_root_causes = Object.entries(causeMap)
    .sort((a, b) => b[1] - a[1]).slice(0, 5)
    .map(([cause, count]) => ({ cause, count }));

  return {
    failure_count:   corrective.length,
    mtbf_days,
    mttr_h,
    pm_overdue:      0,  // placeholder; PM overdue computation deferred to a separate fetch
    downtime_h,
    top_assets,
    top_root_causes,
    closed_count:    closed.length,
    open_count:      corrective.length - closed.length,
    row_count:       rows.length,
  };
}

// ── PM-overdue lookup (Phase 2 keeps it simple: count is_due via canonical view) ──

async function pmOverdueForHive(db: SupabaseClient, hiveId: string, periodEnd: string): Promise<number> {
  try {
    const { data } = await db
      .from("v_pm_compliance_truth")
      .select("is_due, last_anchor_date")
      .eq("hive_id", hiveId)
      .lte("last_anchor_date", periodEnd)
      .limit(ROW_CAP);
    return (data || []).filter((r: { is_due?: boolean }) => r.is_due === true).length;
  } catch (err) {
    log.warn(null, "[hierarchical-summarizer] pm overdue lookup failed:", { detail: String(err).slice(0, 80) });
    return 0;
  }
}

// ── Build digest (LLM call, free-tier chain) ─────────────────────────────────

async function buildDigest(
  db: SupabaseClient,
  hiveId: string,
  periodLabel: string,
  assetTag: string | null,
  summary: SummaryJson,
): Promise<{ summary_text: string; standard_cites: string[]; tokens_in: number; tokens_out: number; latency_ms: number }> {
  const t0 = Date.now();
  if (summary.row_count === 0) {
    // Skip LLM call for empty periods — write a deterministic one-liner.
    return {
      summary_text:   `No maintenance activity recorded for ${periodLabel}${assetTag ? ` on ${assetTag}` : ""}.`,
      standard_cites: [],
      tokens_in:      0,
      tokens_out:     0,
      latency_ms:     Date.now() - t0,
    };
  }
  const payload = {
    period_label: periodLabel,
    asset_tag:    assetTag || "(hive-wide)",
    stats:        summary,
  };
  const raw = await callAI(JSON.stringify(payload), {
    systemPrompt: DIGEST_SYSTEM,
    temperature:  0.3,
    maxTokens:    MAX_TOKENS_DIGEST,
    jsonMode:     true,
    taskProfile:  "narrative_report",  // Phase 4: prefer Scout-17B for prose
  });
  const latency = Date.now() - t0;

  let parsed: { summary_text?: string; standard_cites?: string[] } = {};
  try { parsed = JSON.parse(raw || "{}"); } catch { /* fall through */ }

  await logAICost(db, {
    fn: FN_NAME, hive_id: hiveId, worker_name: null,
    model: "chain:auto", provider: "groq",
    prompt_tokens: estimateTokens(JSON.stringify(payload)) + estimateTokens(DIGEST_SYSTEM),
    output_tokens: estimateTokens(raw),
    latency_ms: latency,
    status: raw === "{}" ? "fallback" : "success",
    schema_compliance: !!parsed.summary_text,
  });

  return {
    summary_text:   String(parsed.summary_text || `Auto-summary for ${periodLabel}: ${summary.failure_count} corrective entries, ${summary.downtime_h}h total downtime.`).slice(0, 1000),
    standard_cites: Array.isArray(parsed.standard_cites) ? parsed.standard_cites.slice(0, 5) : [],
    tokens_in:      estimateTokens(JSON.stringify(payload)),
    tokens_out:     estimateTokens(raw),
    latency_ms:     latency,
  };
}

// ── Single-period rollup (one row in canonical_period_summaries) ─────────────

async function rollupOnePeriod(
  db: SupabaseClient,
  hiveId: string,
  level: Level,
  period: { start: string; end: string },
  assetTag: string | null,
): Promise<{ written: boolean; reason: string }> {
  // Fetch logbook rows in period, hive-scoped, narrow select, capped.
  let q = db.from("v_logbook_truth")
    .select("id, machine, maintenance_type, root_cause, downtime_hours, status, created_at, closed_at")
    .eq("hive_id", hiveId)
    .gte("created_at", period.start + "T00:00:00")
    .lte("created_at", period.end + "T23:59:59")
    .order("created_at", { ascending: true })
    .limit(ROW_CAP);
  if (assetTag) q = q.eq("machine", assetTag);

  const { data, error } = await q;
  if (error) return { written: false, reason: `logbook fetch failed: ${error.message}` };

  const rows = (data || []) as LogRow[];
  const summary = aggregate(rows);
  summary.pm_overdue = await pmOverdueForHive(db, hiveId, period.end);

  const periodLabel = level === "day"
    ? period.start
    : level === "week"
      ? `the week of ${period.start}`
      : level === "month"
        ? new Date(period.start).toLocaleString("en-US", { month: "long", year: "numeric", timeZone: "UTC" })
        : level === "quarter"
          ? `Q${Math.floor(new Date(period.start).getUTCMonth() / 3) + 1} ${new Date(period.start).getUTCFullYear()}`
          : `${new Date(period.start).getUTCFullYear()}`;

  const digest = await buildDigest(db, hiveId, periodLabel, assetTag, summary);

  // source_row_ids is typed uuid[] in the migration. The local seeder uses
  // string IDs like "log-XXX" that are NOT valid UUIDs, so filter to UUID
  // shape only — empty array is fine, traceability degrades gracefully when
  // the source id format doesn't match. Production logbook IDs (gen_random_uuid())
  // always pass this filter.
  const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  const validSourceIds = rows.map(r => String(r.id || "")).filter(id => UUID_RE.test(id));

  const { error: upErr } = await db.from("canonical_period_summaries").upsert({
    hive_id:        hiveId,
    asset_tag:      assetTag,
    level,
    period_start:   period.start,
    period_end:     period.end,
    summary_text:   digest.summary_text,
    summary_json:   summary,
    embedding:      null,  // enrichment pass fills later
    source_row_ids: validSourceIds,
    standard_cites: digest.standard_cites,
    generated_at:   new Date().toISOString(),
  }, { onConflict: "hive_id,asset_tag,level,period_start" });

  if (upErr) return { written: false, reason: `upsert failed: ${upErr.message}` };
  return { written: true, reason: "ok" };
}

// ── Server entry ─────────────────────────────────────────────────────────────

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders });

  // /health probe.
  const healthResp = await handleHealth(req, "hierarchical-summarizer", async () => ({
    deps: [
      { name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) },
      { name: "ai-chain", ok: Boolean(Deno.env.get("GROQ_API_KEY") || Deno.env.get("CEREBRAS_API_KEY")) },
    ],
  }));
  if (healthResp) return healthResp;

  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  let body: { hive_id?: string; level?: Level; period_start?: string; period_end?: string; asset_tag?: string | null } = {};
  try { body = await req.json(); } catch {
    return new Response(JSON.stringify({ error: "Invalid JSON body" }), {
      status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
  if (!body.hive_id) {
    return new Response(JSON.stringify({ error: "Missing required field: hive_id" }), {
      status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
  if (!body.level || !LEVELS.includes(body.level)) {
    return new Response(JSON.stringify({ error: `Missing or invalid level (must be one of ${LEVELS.join(", ")})` }), {
      status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  const db = _warm || createClient(_URL, _KEY);

  // Pillar I: summarizes a hive's history scoped by the client hive_id on a
  // service-role client — verify membership. Internal callers (cron / the
  // temporal-rag delegate) use service-role and skip.
  {
    const { authUid, isServiceRole } = await resolveIdentity(db, req);
    if (!isServiceRole) {
      const t = await resolveTenancy(db, authUid, body.hive_id);
      if (!t.ok) {
        return new Response(
          JSON.stringify({ error: t.message, code: t.code }),
          { status: t.status, headers: { ...corsHeaders, "Content-Type": "application/json" } },
        );
      }
    }
  }

  const period = (body.period_start && body.period_end)
    ? { start: body.period_start, end: body.period_end }
    : previousPeriod(body.level);

  const result = await rollupOnePeriod(db, body.hive_id, body.level, period, body.asset_tag || null);

  return new Response(JSON.stringify({
    ok:      result.written,
    written: result.written ? 1 : 0,
    skipped: result.written ? 0 : 1,
    errors:  result.written ? [] : [result.reason],
    level:   body.level,
    period,
  }), {
    status: result.written ? 200 : 500,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
});
