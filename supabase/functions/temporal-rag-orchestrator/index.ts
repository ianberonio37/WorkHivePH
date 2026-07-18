/**
 * temporal-rag-orchestrator — Phase 3 of AGENTIC_RAG_ROADMAP.md.
 *
 * Supervisor-worker topology for time-bound questions that span multiple
 * periods ("compare 2022 vs 2023 vs 2024 vs 2025 on P-203"). Decomposes
 * the time range, fans out N sub-agent calls in parallel (each on the
 * cheap free-tier model via taskProfile=temporal_subagent), then folds
 * the structured results in one synthesis call.
 *
 * Reads from canonical_period_summaries (Phase 2) for each period —
 * never raw v_logbook_truth. This is the mechanism that keeps total
 * token usage bounded even for 5+ year horizons.
 *
 * Body:
 *   { question: string, hive_id: string, asset_tag?: string,
 *     from?: ISO-date, to?: ISO-date, granularity?: 'auto'|'year'|'quarter'|'month' }
 *   - from/to default to "last 5 years through yesterday"
 *   - granularity 'auto' picks year for ≥3y span, quarter for 6mo-3y, month otherwise
 *
 * Response:
 *   { answer, per_period: [{period, key_findings, mtbf_days, ...}], periods: number, trace_id }
 *
 * Bounded concurrency (max 3 parallel sub-agents) keeps Groq TPM
 * contention predictable. Aborts if any sub-agent fails — fold step
 * still runs on the surviving sub-results.
 *
 * Free-tier constraint: every callAI uses taskProfile pointing at
 * free-tier models. See feedback_free_tier_only_models.md.
 *
 * Skills consulted: ai-engineer (callAI, taskProfile from Phase 4,
 * Promise.allSettled per orchestrator rule, JSON output, no em dashes),
 * architect (4-place sync), data-engineer (hive scoping, narrow selects),
 * performance (parallel fan-out, not sequential).
 *
 * contract-allow: meta-orchestrator; output schema documented above.
 */

import { serveObserved } from "../_shared/observability.ts";
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

const FN_NAME             = "temporal-rag-orchestrator";
const MAX_QUESTION_CHARS  = 500;
const RATE_LIMIT_PER_HOUR = 30;       // tighter than Phase 1 because each call fans out N sub-calls
const MAX_PERIODS         = 10;       // never decompose into more than 10 sub-queries
const MAX_PARALLEL        = 3;        // bounded concurrency for TPM safety
const MAX_TOKENS_SUB      = 400;
const MAX_TOKENS_FOLD     = 800;

const SUB_SYSTEM = `You analyse a single period of industrial maintenance activity for one asset (or hive-wide).

You receive:
- period_label (e.g. "2024", "Q1 2025", "March 2026")
- asset_tag (or "hive-wide")
- summary (pre-computed canonical_period_summaries.summary_json with failure_count, mtbf_days, mttr_h, top_assets, top_root_causes, pm_overdue, downtime_h)
- question (the user's broader question)

Rules:
1. Use ONLY the summary stats provided. Never invent values.
2. Return 3 to 5 short key findings specific to this period.
3. Flag anomalies (sudden spike in failures, MTBF drop, repeat root cause).
4. Cite the period_label in every finding.
5. No em dashes.

Respond JSON only:
{ "period": "<label>", "key_findings": ["<finding 1>", "..."], "mtbf_days": <float|null>, "downtime_h": <float|null>, "top_failure_modes": [{"mode": "<name>", "count": <int>}], "anomalies": ["<note>"] }`;

const FOLD_SYSTEM = `You synthesise N per-period analyses into one comparison answering the user's question.

You receive:
- question
- per_period: array of per-period JSON results from sub-agents

Rules:
1. Compare trends across periods: improving, stable, degrading.
2. Name the worst period and explain why using its summary stats.
3. Cite period labels inline like [2024] [Q1 2025].
4. If a period has zero findings, mention it briefly.
5. Stay under 180 words.
6. No em dashes. Use Filipino industrial vocabulary (ISO 14224, PSME) when natural.

Respond JSON only:
{ "answer": "<text with [period] citations>", "worst_period": "<label>", "trend": "improving|stable|degrading|mixed" }`;

const _URL = Deno.env.get("SUPABASE_URL") || "";
const _KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
if (!_URL || !_KEY) log.warn(null, "[temporal-rag-orchestrator] SUPABASE env missing");
const _warm = _URL && _KEY ? createClient(_URL, _KEY) : null;
void _warm;

// ── Period decomposition ─────────────────────────────────────────────────────

type Granularity = "year" | "quarter" | "month";

function decompose(from: Date, to: Date, grain: Granularity | "auto"): Array<{ start: string; end: string; label: string }> {
  const periods: Array<{ start: string; end: string; label: string }> = [];
  const spanDays = (to.getTime() - from.getTime()) / 86400000;
  let g: Granularity;
  if (grain === "auto") {
    if (spanDays >= 3 * 365) g = "year";
    else if (spanDays >= 180) g = "quarter";
    else g = "month";
  } else g = grain;

  if (g === "year") {
    for (let y = from.getUTCFullYear(); y <= to.getUTCFullYear(); y++) {
      const start = new Date(Date.UTC(y, 0, 1));
      const end   = new Date(Date.UTC(y, 11, 31));
      periods.push({ start: start.toISOString().slice(0,10), end: end.toISOString().slice(0,10), label: String(y) });
    }
  } else if (g === "quarter") {
    let curY = from.getUTCFullYear(), curQ = Math.floor(from.getUTCMonth() / 3);
    while (true) {
      const start = new Date(Date.UTC(curY, curQ * 3, 1));
      const end   = new Date(Date.UTC(curY, curQ * 3 + 3, 0));
      if (start > to) break;
      periods.push({ start: start.toISOString().slice(0,10), end: end.toISOString().slice(0,10), label: `Q${curQ+1} ${curY}` });
      curQ++; if (curQ > 3) { curQ = 0; curY++; }
    }
  } else {
    let curY = from.getUTCFullYear(), curM = from.getUTCMonth();
    while (true) {
      const start = new Date(Date.UTC(curY, curM, 1));
      const end   = new Date(Date.UTC(curY, curM + 1, 0));
      if (start > to) break;
      const lbl = start.toLocaleString("en-US", { month: "long", year: "numeric", timeZone: "UTC" });
      periods.push({ start: start.toISOString().slice(0,10), end: end.toISOString().slice(0,10), label: lbl });
      curM++; if (curM > 11) { curM = 0; curY++; }
    }
  }
  return periods.slice(0, MAX_PERIODS);
}

// ── Per-period summary lookup (Phase 2 hierarchical_period_summaries) ────────

async function fetchPeriodSummary(
  db: SupabaseClient,
  hiveId: string,
  assetTag: string | null,
  level: Granularity,
  periodStart: string,
): Promise<Record<string, unknown> | null> {
  const dbLevel = level;  // 'year' | 'quarter' | 'month' match canonical_period_summaries.level CHECK values
  // canonical-allow: temporal-RAG primary read (canonical_period_summaries IS the canonical aggregate)
  // ORDER BY generated_at DESC: Postgres treats NULL as distinct in unique
  // constraints, so multiple (hive_id, level, period_start, asset_tag=NULL)
  // rows can co-exist from successive backfills. Take the latest.
  let q = db.from("canonical_period_summaries")
    .select("summary_json, summary_text, standard_cites, generated_at")
    .eq("hive_id", hiveId)
    .eq("level", dbLevel)
    .eq("period_start", periodStart)
    .order("generated_at", { ascending: false })
    .limit(1);
  if (assetTag) q = q.eq("asset_tag", assetTag);
  else          q = q.is("asset_tag", null);
  const { data } = await q;
  return (data && data[0]) ? data[0] : null;
}

// ── Sub-agent: one period ────────────────────────────────────────────────────

interface SubResult {
  period: string;
  key_findings: string[];
  mtbf_days: number | null;
  downtime_h: number | null;
  top_failure_modes: Array<{ mode: string; count: number }>;
  anomalies: string[];
}

async function subAgent(
  db: SupabaseClient,
  hiveId: string,
  workerName: string | null,
  question: string,
  period: { start: string; end: string; label: string },
  assetTag: string | null,
  level: Granularity,
): Promise<SubResult> {
  const t0 = Date.now();
  const summary = await fetchPeriodSummary(db, hiveId, assetTag, level, period.start);

  if (!summary || !summary.summary_json) {
    // Period has no pre-computed summary — return an empty marker so the fold knows
    return {
      period:        period.label,
      key_findings:  [`No pre-computed summary available for ${period.label}.`],
      mtbf_days:     null,
      downtime_h:    null,
      top_failure_modes: [],
      anomalies:     [],
    };
  }

  const payload = {
    period_label: period.label,
    asset_tag:    assetTag || "(hive-wide)",
    summary:      summary.summary_json,
    question,
  };
  const raw = await callAI(JSON.stringify(payload), {
    systemPrompt: SUB_SYSTEM,
    temperature:  0.1,
    maxTokens:    MAX_TOKENS_SUB,
    jsonMode:     true,
    taskProfile:  "temporal_subagent",  // Phase 4: prefer llama-3.1-8b-instant
  });
  const latency = Date.now() - t0;

  let parsed: Partial<SubResult> = {};
  try { parsed = JSON.parse(raw || "{}"); } catch { /* fallthrough */ }

  await logAICost(db, {
    fn: FN_NAME, hive_id: hiveId, worker_name: workerName,
    model: "chain:auto", provider: "groq",
    prompt_tokens: estimateTokens(JSON.stringify(payload)) + estimateTokens(SUB_SYSTEM),
    output_tokens: estimateTokens(raw),
    latency_ms: latency,
    status: raw === "{}" ? "fallback" : "success",
    schema_compliance: !!parsed.period,
  });

  return {
    period:            parsed.period || period.label,
    key_findings:      Array.isArray(parsed.key_findings) ? parsed.key_findings.slice(0, 5) : [],
    mtbf_days:         typeof parsed.mtbf_days === "number" ? parsed.mtbf_days : null,
    downtime_h:        typeof parsed.downtime_h === "number" ? parsed.downtime_h : null,
    top_failure_modes: Array.isArray(parsed.top_failure_modes) ? parsed.top_failure_modes.slice(0, 5) : [],
    anomalies:         Array.isArray(parsed.anomalies) ? parsed.anomalies.slice(0, 5) : [],
  };
}

// ── Bounded-concurrency runner (replaces unbounded Promise.all to keep TPM contention predictable) ──

async function runBounded<T, R>(items: T[], limit: number, fn: (it: T) => Promise<R>): Promise<R[]> {
  const out: R[] = new Array(items.length);
  let idx = 0;
  const workers: Promise<void>[] = [];
  for (let w = 0; w < Math.min(limit, items.length); w++) {
    workers.push((async () => {
      while (true) {
        const i = idx++;
        if (i >= items.length) return;
        try { out[i] = await fn(items[i]); }
        catch (err) { out[i] = { _error: String(err).slice(0, 80) } as unknown as R; }
      }
    })());
  }
  await Promise.all(workers);
  return out;
}

// ── Rate limit (per-hive, 1-hour window) ─────────────────────────────────────

async function checkRateLimit(db: SupabaseClient, hiveId: string): Promise<{ allowed: boolean; remaining: number }> {
  const windowStart = new Date(Date.now() - 60 * 60 * 1000);
  const { data, error } = await db
    .from("ai_rate_limits")
    .select("call_count, window_start")
    .eq("hive_id", hiveId)
    .maybeSingle();
  if (error) return { allowed: true, remaining: RATE_LIMIT_PER_HOUR };
  if (!data || new Date(data.window_start) < windowStart) {
    await db.from("ai_rate_limits").upsert({ hive_id: hiveId, call_count: 1, window_start: new Date().toISOString() });
    return { allowed: true, remaining: RATE_LIMIT_PER_HOUR - 1 };
  }
  if (data.call_count >= RATE_LIMIT_PER_HOUR) return { allowed: false, remaining: 0 };
  await db.from("ai_rate_limits").update({ call_count: data.call_count + 1 }).eq("hive_id", hiveId);
  return { allowed: true, remaining: RATE_LIMIT_PER_HOUR - data.call_count - 1 };
}

// ── Server entry ─────────────────────────────────────────────────────────────

serveObserved("temporal-rag-orchestrator", async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders });

  // /health probe.
  const healthResp = await handleHealth(req, "temporal-rag-orchestrator", async () => ({
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

  const reqStart = Date.now();
  let body: { question?: string; hive_id?: string; asset_tag?: string | null; from?: string; to?: string; granularity?: Granularity | "auto"; worker_name?: string | null } = {};
  try { body = await req.json(); } catch {
    return new Response(JSON.stringify({ error: "Invalid JSON body" }), {
      status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
  const question   = String(body.question || "").trim().slice(0, MAX_QUESTION_CHARS);
  const hiveId     = body.hive_id || "";
  const assetTag   = body.asset_tag || null;
  const workerName = body.worker_name || null;
  const granularity = body.granularity || "auto";

  if (!question) return new Response(JSON.stringify({ error: "Missing required field: question" }), {
    status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
  if (!hiveId) return new Response(JSON.stringify({ error: "Missing required field: hive_id" }), {
    status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
  });

  const db = _warm || createClient(_URL, _KEY);

  // Pillar I: RAG over a hive's temporal summaries scoped by the client hive_id
  // on a service-role client — verify membership. Internal callers (the
  // agentic-rag-loop temporal delegate) use service-role and skip.
  {
    const { authUid, isServiceRole } = await resolveIdentity(db, req);
    if (!isServiceRole) {
      const t = await resolveTenancy(db, authUid, hiveId);
      if (!t.ok) {
        return new Response(
          JSON.stringify({ error: t.message, code: t.code }),
          { status: t.status, headers: { ...corsHeaders, "Content-Type": "application/json" } },
        );
      }
    }
  }

  // Rate limit BEFORE any sub-agent runs (cost protection)
  const rl = await checkRateLimit(db, hiveId);
  if (!rl.allowed) {
    return new Response(JSON.stringify({ error: "Temporal RAG limit reached for this hive. Try again in an hour.", remaining: 0 }),
      { status: 429, headers: { ...corsHeaders, "Content-Type": "application/json" } });
  }

  // Parse / default the time range. Default: last 5 years through yesterday.
  const to   = body.to   ? new Date(body.to)   : new Date(Date.now() - 86400000);
  const from = body.from ? new Date(body.from) : new Date(to.getTime() - 5 * 365 * 86400000);
  if (!Number.isFinite(from.getTime()) || !Number.isFinite(to.getTime()) || from >= to) {
    return new Response(JSON.stringify({ error: "Invalid from/to dates" }), {
      status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  const periods = decompose(from, to, granularity);
  if (!periods.length) {
    return new Response(JSON.stringify({ error: "Period decomposition yielded zero periods" }), {
      status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  // Compute the level we'll be requesting from canonical_period_summaries
  const spanDays = (to.getTime() - from.getTime()) / 86400000;
  const level: Granularity = granularity === "auto"
    ? (spanDays >= 3 * 365 ? "year" : spanDays >= 180 ? "quarter" : "month")
    : granularity as Granularity;

  // Fan out sub-agents with bounded concurrency
  const subResults = await runBounded(periods, MAX_PARALLEL, (p) =>
    subAgent(db, hiveId, workerName, question, p, assetTag, level));

  // Fold step
  const foldT0 = Date.now();
  const foldPayload = { question, per_period: subResults };
  const foldRaw = await callAI(JSON.stringify(foldPayload), {
    systemPrompt: FOLD_SYSTEM,
    temperature:  0.2,
    maxTokens:    MAX_TOKENS_FOLD,
    jsonMode:     true,
    taskProfile:  "temporal_fold",  // Phase 4: prefer Scout-17B
  });
  const foldLatency = Date.now() - foldT0;
  let fold: { answer?: string; worst_period?: string; trend?: string } = {};
  try { fold = JSON.parse(foldRaw || "{}"); } catch { /* fallthrough */ }

  await logAICost(db, {
    fn: FN_NAME, hive_id: hiveId, worker_name: workerName,
    model: "chain:auto", provider: "groq",
    prompt_tokens: estimateTokens(JSON.stringify(foldPayload)) + estimateTokens(FOLD_SYSTEM),
    output_tokens: estimateTokens(foldRaw),
    latency_ms: foldLatency,
    status: foldRaw === "{}" ? "fallback" : "success",
    schema_compliance: !!fold.answer,
  });

  const totalLatency = Date.now() - reqStart;

  return new Response(JSON.stringify({
    answer:       fold.answer || "Could not synthesise a temporal comparison from the available period summaries.",
    worst_period: fold.worst_period || null,
    trend:        fold.trend || "unknown",
    per_period:   subResults,
    periods:      periods.length,
    level,
    latency_ms:   totalLatency,
    remaining:    rl.remaining,
  }), {
    status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
});
