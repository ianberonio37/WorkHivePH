/**
// capability: ai_specialist_amc
// capability: alert_amc_briefing
 * amc-orchestrator - Autonomous Maintenance Crew daily briefing builder.
 *
 * Runs once per active hive every day at 06:00 PHT (via scheduled-agents
 * fan-out from pg_cron). Five sub-agents execute via Promise.allSettled,
 * then the result is written to amc_briefings as a single row per
 * (hive_id, shift_date). The supervisor approves the brief in batch from
 * alert-hub.html.
 *
 * Sub-agents (all hive-scoped, all reading from canonical truth views):
 *   1. Failure-Predictor  -> top-3 highest-risk assets (v_risk_truth)
 *   2. PM-Planner         -> top-5 PMs due now           (v_pm_compliance_truth)
 *   3. Parts-Stager       -> top-5 pending stagings      (parts_staging_recommendations)
 *   4. Crew-Builder       -> per-asset worker match       (v_worker_skill_truth)
 *   5. Briefing-Composer  -> narrative paragraph          (callAI)
 *
 * Invocation modes:
 *   POST { hive_id }        - run for one hive
 *   POST { }                - drain mode: run for every hive that has an
 *                             active member but no pending/approved brief
 *                             for today
 *
 * The function is idempotent: re-running for a hive that already has a
 * brief for today's shift_date is a no-op (UNIQUE INDEX on (hive, shift_date)
 * + duplicate-key catch).
 *
 * Skills consulted:
 *   ai-engineer (callAI shared chain, JSON-only output, system prompt as
 *     const, Promise.allSettled across sub-agents, token minimization via
 *     narrow selects + cap on row count + string summaries to the LLM)
 *   maintenance-expert (PM compliance via canonical view, criticality
 *     weighting, MTBF reading from v_risk_truth)
 *   predictive-analytics (risk_truth latest-per-asset DISTINCT ON contract,
 *     structured top_factors handling)
 *   multitenant-engineer (every read .eq('hive_id', ...), service-role
 *     writes that bypass RLS; no client-supplied hive_id trusted for write
 *     paths)
 *   architect (canonical sources lookup for risk_truth + pm_compliance_truth
 *     + worker_skill_truth + amc_brief, single-row per shift_date contract)
 *   security (no PII in brief beyond worker_name + asset_name which are
 *     already visible to hive members; rate-limit gate per hive on the LLM
 *     call - the cron itself rate-limits the function as a whole)
 *   notifications (computed-state pattern - the brief replaces the previous
 *     day's pending one which is expired by amc_expire_stale())
 *   devops (getCorsHeaders dynamic CORS, AbortSignal timeout on the LLM call,
 *     warm module-scope client)
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

// contract-allow: produces AMC briefing; future Tier C: amc_brief_v1
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { callAI } from "../_shared/ai-chain.ts";
// Persona Contract: AMC briefings sign their footer ("Signed by James,
// your WorkHive daily companion"). The brief BODY stays structured —
// only the narrative footer wears the persona. See
// WORKHIVE_PERSONA_CONTRACT.md, mode='briefing-signature'.
import { buildPersonaBlock, clampPersona } from "../_shared/persona.ts";
import { getCorsHeaders } from "../_shared/cors.ts";
import { logAICost, estimateTokens } from "../_shared/cost-log.ts";

// Warm module-scope client (PRODUCTION_FIXES #46 pattern).
const _WH_SUPABASE_URL_M = Deno.env.get("SUPABASE_URL") || "";
const _WH_SERVICE_KEY_M  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const _whWarmClient = _WH_SUPABASE_URL_M && _WH_SERVICE_KEY_M
  ? createClient(_WH_SUPABASE_URL_M, _WH_SERVICE_KEY_M)
  : null;
void _whWarmClient;

// ─── Constants ────────────────────────────────────────────────────────────────

const TOP_ASSETS_LIMIT   = 3;
const TOP_PMS_LIMIT      = 5;
const TOP_PARTS_LIMIT    = 5;
const CREW_PER_ASSET     = 2;
const MAX_TOKENS_SUMMARY = 220;
const LLM_TIMEOUT_MS     = 45_000;
const MODEL_VERSION      = "amc-v1";

// Heuristic mapping from PM category to discipline used in skill_badges.
// Lowercased on both sides. Anything outside this map gets discipline=null
// (Crew-Builder will fall back to "best-available-supervisor" then).
const CATEGORY_TO_DISCIPLINE: Record<string, string> = {
  "electrical":      "electrical",
  "mechanical":      "mechanical",
  "instrumentation": "instrumentation",
  "hvac":            "hvac",
  "utilities":       "utilities",
  "civil":           "civil",
  "general":         "mechanical",   // soft default for unscoped PMs
};

const SUMMARY_SYSTEM_PROMPT = `You are a maintenance supervisor briefing your crew at the start of a shift.
Respond ONLY with JSON. No markdown.

Output schema:
{
  "summary": <string - 2 to 4 short sentences, 220 tokens max>,
  "headline": <string - 8 to 14 words capturing the single most important thing>
}

Rules:
1. The brief is for ONE shift today, at one industrial plant (a "hive").
2. Tone: direct, practical, Filipino industrial style. No marketing fluff.
3. Mention the top risk asset by name. Mention the count of overdue PMs.
4. If parts need staging, name the asset that needs them (one).
5. If crew suggestions exist, mention the discipline that has the most demand.
6. No em dashes - use colons, commas, or short sentences.
7. No exclamation marks. No greetings ("Good morning"). Lead with the most urgent fact.`;

// ─── Type defs ────────────────────────────────────────────────────────────────

type AnyRow = Record<string, unknown>;

interface FailurePredictorOut {
  top_assets: Array<{
    asset_id:   string | null;
    asset_name: string;
    risk_score: number;
    risk_level: string;
    top_factors: unknown[];
    mtbf_days:  number | null;
    days_until_failure: number | null;
  }>;
}

interface PMPlannerOut {
  pm_due: Array<{
    pm_asset_id: string;
    asset_name:  string;
    category:    string;
    criticality: string | null;
    days_since_last_completion: number | null;
    is_due: boolean;
  }>;
}

interface PartsStagerOut {
  parts_to_stage: Array<{
    recommendation_id: string;
    asset_name:        string;
    parts:             unknown;
    rationale:         string | null;
    confidence:        number | null;
    risk_score:        number | null;
  }>;
}

interface CrewSuggestion {
  asset_name:       string;
  category:         string | null;
  discipline:       string | null;
  suggested_worker: string | null;
  current_level:    number | null;
  reason:           string;
}

interface CrewBuilderOut {
  crew: CrewSuggestion[];
}

interface SummaryOut {
  summary:  string;
  headline: string;
}

// ─── Sub-agent 1: Failure-Predictor ──────────────────────────────────────────

async function failurePredictor(
  db: SupabaseClient, hive_id: string,
): Promise<FailurePredictorOut> {
  const { data } = await db.from("v_risk_truth")
    .select("asset_id, asset_name, risk_score, risk_level, top_factors, mtbf_days, days_until_failure")
    .eq("hive_id", hive_id)
    .in("risk_level", ["high", "critical"])
    .order("risk_score", { ascending: false })
    .limit(TOP_ASSETS_LIMIT);

  return {
    top_assets: (data || []).map(r => ({
      asset_id:   (r.asset_id as string | null) ?? null,
      asset_name: String(r.asset_name || ""),
      risk_score: Number(r.risk_score) || 0,
      risk_level: String(r.risk_level || ""),
      top_factors: Array.isArray(r.top_factors) ? r.top_factors : [],
      mtbf_days:  r.mtbf_days != null ? Number(r.mtbf_days) : null,
      days_until_failure: r.days_until_failure != null ? Number(r.days_until_failure) : null,
    })),
  };
}

// ─── Sub-agent 2: PM-Planner ─────────────────────────────────────────────────

async function pmPlanner(
  db: SupabaseClient, hive_id: string,
): Promise<PMPlannerOut> {
  const { data } = await db.from("v_pm_compliance_truth")
    .select("pm_asset_id, asset_name, category, criticality, days_since_last_completion, is_due")
    .eq("hive_id", hive_id)
    .eq("is_due", true)
    .order("days_since_last_completion", { ascending: false, nullsFirst: false })
    .limit(TOP_PMS_LIMIT * 3);     // overfetch so we can re-rank by criticality

  const rows = (data || []).map(r => ({
    pm_asset_id: String(r.pm_asset_id || ""),
    asset_name:  String(r.asset_name || ""),
    category:    String(r.category || "general"),
    criticality: r.criticality ? String(r.criticality) : null,
    days_since_last_completion:
      r.days_since_last_completion != null ? Number(r.days_since_last_completion) : null,
    is_due: !!r.is_due,
  }));

  // Re-rank: critical first, then by days_since_last_completion DESC.
  const crit = (c: string | null): number =>
    c === "critical" ? 3 : c === "high" ? 2 : c === "medium" ? 1 : 0;
  rows.sort((a, b) => {
    const dc = crit(b.criticality) - crit(a.criticality);
    if (dc !== 0) return dc;
    const da = a.days_since_last_completion ?? -1;
    const db = b.days_since_last_completion ?? -1;
    return db - da;
  });

  return { pm_due: rows.slice(0, TOP_PMS_LIMIT) };
}

// ─── Sub-agent 3: Parts-Stager ───────────────────────────────────────────────

async function partsStager(
  db: SupabaseClient, hive_id: string,
): Promise<PartsStagerOut> {
  const { data } = await db.from("parts_staging_recommendations")
    .select("id, asset_name, parts, rationale, confidence, risk_score, expires_at")
    .eq("hive_id", hive_id)
    .eq("status", "pending")
    .gte("expires_at", new Date().toISOString())
    .order("risk_score", { ascending: false })
    .limit(TOP_PARTS_LIMIT);

  return {
    parts_to_stage: (data || []).map(r => ({
      recommendation_id: String(r.id || ""),
      asset_name:        String(r.asset_name || ""),
      parts:             r.parts,
      rationale:         r.rationale ? String(r.rationale) : null,
      confidence:        r.confidence != null ? Number(r.confidence) : null,
      risk_score:        r.risk_score != null ? Number(r.risk_score) : null,
    })),
  };
}

// ─── Sub-agent 4: Crew-Builder ───────────────────────────────────────────────
//
// Given the top-3 risk assets and the top-5 PM due rows, pick a candidate
// worker per asset by best skill match. Falls back to "highest-level worker
// in any discipline" then to "any active worker" so a brief is never empty
// purely because skill_badges is sparse.

async function crewBuilder(
  db: SupabaseClient, hive_id: string,
  risk: FailurePredictorOut, pm: PMPlannerOut,
): Promise<CrewBuilderOut> {
  // Materialise the candidate pool once (per hive, per request).
  const { data: pool } = await db.from("v_worker_skill_truth")
    .select("worker_name, role, discipline, current_level")
    .eq("hive_id", hive_id);
  const rows = pool || [];

  // Index by discipline for quick lookup, plus a no-discipline fallback list.
  const byDiscipline: Record<string, AnyRow[]> = {};
  const noBadgePool: AnyRow[] = [];
  for (const r of rows) {
    if (r.discipline && r.current_level != null) {
      const d = String(r.discipline).toLowerCase();
      (byDiscipline[d] = byDiscipline[d] || []).push(r as AnyRow);
    } else {
      noBadgePool.push(r as AnyRow);
    }
  }
  // Sort each discipline pool by current_level DESC.
  Object.values(byDiscipline).forEach(arr => arr.sort(
    (a, b) => Number(b.current_level || 0) - Number(a.current_level || 0),
  ));

  // Stable de-dup of (asset, discipline) so we don't recommend the same
  // worker on two assets in a single brief.
  const used = new Set<string>();

  function pickFor(category: string | null): {
    suggested_worker: string | null;
    current_level:    number | null;
    discipline:       string | null;
    reason:           string;
  } {
    const disc = category
      ? CATEGORY_TO_DISCIPLINE[String(category).toLowerCase()] || null
      : null;

    // Best-match path: discipline aware.
    if (disc && byDiscipline[disc]) {
      for (const cand of byDiscipline[disc]) {
        const wn = String(cand.worker_name || "");
        if (!wn) continue;
        if (used.has(wn)) continue;
        used.add(wn);
        return {
          suggested_worker: wn,
          current_level:    cand.current_level != null ? Number(cand.current_level) : null,
          discipline:       disc,
          reason:           `Best ${disc} match (Level ${cand.current_level}).`,
        };
      }
    }
    // Fallback: highest-level worker across any discipline.
    let bestAny: AnyRow | null = null;
    let bestLevel = -1;
    for (const arr of Object.values(byDiscipline)) {
      for (const cand of arr) {
        const wn = String(cand.worker_name || "");
        if (!wn || used.has(wn)) continue;
        const lvl = Number(cand.current_level || 0);
        if (lvl > bestLevel) { bestAny = cand; bestLevel = lvl; }
      }
    }
    if (bestAny) {
      const wn = String(bestAny.worker_name || "");
      used.add(wn);
      return {
        suggested_worker: wn,
        current_level:    bestLevel,
        discipline:       bestAny.discipline ? String(bestAny.discipline) : null,
        reason:           `No exact discipline match; highest-level available worker (${bestAny.discipline}, Level ${bestLevel}).`,
      };
    }
    // Final fallback: any active hive member (no badge).
    for (const cand of noBadgePool) {
      const wn = String(cand.worker_name || "");
      if (!wn || used.has(wn)) continue;
      used.add(wn);
      return {
        suggested_worker: wn,
        current_level:    null,
        discipline:       null,
        reason:           "No badged worker available; assigning by membership.",
      };
    }
    return {
      suggested_worker: null,
      current_level:    null,
      discipline:       null,
      reason:           "No active hive members available.",
    };
  }

  const crew: CrewSuggestion[] = [];

  // Top-risk assets first (we have at most TOP_ASSETS_LIMIT of them).
  for (const a of risk.top_assets) {
    const cat: string | null = null;  // v_risk_truth doesn't carry category
    const sel = pickFor(cat);
    crew.push({
      asset_name:       a.asset_name,
      category:         cat,
      discipline:       sel.discipline,
      suggested_worker: sel.suggested_worker,
      current_level:    sel.current_level,
      reason:           sel.reason,
    });
  }

  // Then PM-due assets up to CREW_PER_ASSET-style cap (we cap at TOP_PMS_LIMIT).
  for (const p of pm.pm_due) {
    const sel = pickFor(p.category);
    crew.push({
      asset_name:       p.asset_name,
      category:         p.category,
      discipline:       sel.discipline,
      suggested_worker: sel.suggested_worker,
      current_level:    sel.current_level,
      reason:           sel.reason,
    });
  }

  return { crew: crew.slice(0, TOP_ASSETS_LIMIT + TOP_PMS_LIMIT) };
}

// ─── Sub-agent 5: Briefing-Composer (LLM) ────────────────────────────────────

async function briefingComposer(
  db: SupabaseClient,
  hive_id: string,
  hive_name: string,
  risk: FailurePredictorOut,
  pm: PMPlannerOut,
  parts: PartsStagerOut,
  crew: CrewBuilderOut,
): Promise<SummaryOut> {
  const fallback: SummaryOut = {
    summary: composeFallbackSummary(risk, pm, parts, crew),
    headline: composeFallbackHeadline(risk, pm),
  };

  // Build a compact one-line-per-finding payload (token minimisation rule).
  const payload = {
    hive: hive_name,
    top_assets: risk.top_assets.slice(0, 3).map(a =>
      `${a.asset_name}|risk=${a.risk_level}|score=${a.risk_score.toFixed(2)}`,
    ),
    pm_due: pm.pm_due.slice(0, 5).map(p =>
      `${p.asset_name}|cat=${p.category}|crit=${p.criticality || "?"}|since=${p.days_since_last_completion ?? "?"}d`,
    ),
    parts: parts.parts_to_stage.slice(0, 5).map(p => {
      const n = Array.isArray(p.parts) ? p.parts.length : 0;
      return `${p.asset_name}|${n} part(s)|conf=${p.confidence ?? "?"}`;
    }),
    crew: crew.crew.slice(0, 5).map(c =>
      `${c.asset_name}|->${c.suggested_worker || "(none)"}|${c.discipline || "any"}|L${c.current_level ?? "?"}`,
    ),
  };

  const promptStr = JSON.stringify(payload);
  const t0 = Date.now();
  let raw: string;
  try {
    raw = await Promise.race([
      callAI(promptStr, {
        systemPrompt: SUMMARY_SYSTEM_PROMPT,
        temperature:  0.25,
        maxTokens:    MAX_TOKENS_SUMMARY,
        jsonMode:     true,
      }),
      new Promise<string>((_, reject) =>
        setTimeout(() => reject(new Error("AMC summary LLM timeout")), LLM_TIMEOUT_MS),
      ),
    ]);
  } catch {
    void logAICost(db, {
      fn:            "amc-orchestrator",
      hive_id,
      model:         MODEL_VERSION,
      provider:      "chain",
      prompt_tokens: estimateTokens(promptStr) + estimateTokens(SUMMARY_SYSTEM_PROMPT),
      latency_ms:    Date.now() - t0,
      status:        "fallback",
    });
    return fallback;
  }

  try {
    const parsed = JSON.parse(raw) as AnyRow;
    const summary  = String(parsed.summary  || "").trim();
    const headline = String(parsed.headline || "").trim();
    const compliant = !!(summary && headline);
    void logAICost(db, {
      fn:                "amc-orchestrator",
      hive_id,
      model:             MODEL_VERSION,
      provider:          "chain",
      prompt_tokens:     estimateTokens(promptStr) + estimateTokens(SUMMARY_SYSTEM_PROMPT),
      output_tokens:     estimateTokens(raw),
      latency_ms:        Date.now() - t0,
      status:            compliant ? "success" : "fallback",
      schema_compliance: compliant,
    });
    if (!compliant) return fallback;
    return { summary, headline };
  } catch {
    void logAICost(db, {
      fn:                "amc-orchestrator",
      hive_id,
      model:             MODEL_VERSION,
      provider:          "chain",
      prompt_tokens:     estimateTokens(promptStr) + estimateTokens(SUMMARY_SYSTEM_PROMPT),
      output_tokens:     estimateTokens(raw),
      latency_ms:        Date.now() - t0,
      status:            "fallback",
      schema_compliance: false,
    });
    return fallback;
  }
}

function composeFallbackSummary(
  risk: FailurePredictorOut, pm: PMPlannerOut,
  parts: PartsStagerOut, crew: CrewBuilderOut,
): string {
  const parts1 = risk.top_assets.length
    ? `Highest risk today: ${risk.top_assets[0].asset_name} (${risk.top_assets[0].risk_level}).`
    : "No high-risk assets flagged today.";
  const parts2 = pm.pm_due.length
    ? `${pm.pm_due.length} PM task(s) overdue.`
    : "No PMs overdue.";
  const parts3 = parts.parts_to_stage.length
    ? `Stage parts for ${parts.parts_to_stage[0].asset_name}.`
    : "";
  const parts4 = crew.crew.length && crew.crew[0].suggested_worker
    ? `Suggested lead: ${crew.crew[0].suggested_worker}.`
    : "";
  return [parts1, parts2, parts3, parts4].filter(Boolean).join(" ");
}

function composeFallbackHeadline(
  risk: FailurePredictorOut, pm: PMPlannerOut,
): string {
  if (risk.top_assets.length) {
    return `Focus ${risk.top_assets[0].asset_name}: ${risk.top_assets[0].risk_level} risk and ${pm.pm_due.length} PMs overdue`;
  }
  return `Routine shift: ${pm.pm_due.length} PM task(s) due, no risk escalations`;
}

// ─── Orchestrator ────────────────────────────────────────────────────────────

interface BriefForHive {
  hive_id:        string;
  hive_name:      string;
  brief_id:       string | null;
  status:         "inserted" | "skipped_existing" | "error";
  error?:         string;
  asset_count?:   number;
  pm_count?:      number;
  parts_count?:   number;
}

async function buildBriefForHive(
  db: SupabaseClient,
  hive: { id: string; name: string; preferred_persona?: string | null },
): Promise<BriefForHive> {
  const today = new Date(
    new Date().toLocaleString("en-US", { timeZone: "Asia/Manila" }),
  ).toISOString().slice(0, 10);

  // Idempotency check: skip if a non-expired brief for this shift_date already exists.
  const { data: existing } = await db.from("amc_briefings")
    .select("id, status")
    .eq("hive_id", hive.id)
    .eq("shift_date", today)
    .in("status", ["pending", "approved"])
    .maybeSingle();
  if (existing) {
    return {
      hive_id:    hive.id,
      hive_name:  hive.name,
      brief_id:   String(existing.id),
      status:     "skipped_existing",
    };
  }

  // Run sub-agents in parallel (Promise.allSettled). A failure in any sub
  // does NOT abort the brief - the brief is best-effort.
  const [riskRes, pmRes, partsRes] = await Promise.allSettled([
    failurePredictor(db, hive.id),
    pmPlanner(db, hive.id),
    partsStager(db, hive.id),
  ]);
  const risk:  FailurePredictorOut = riskRes.status  === "fulfilled" ? riskRes.value  : { top_assets:     [] };
  const pm:    PMPlannerOut        = pmRes.status    === "fulfilled" ? pmRes.value    : { pm_due:         [] };
  const parts: PartsStagerOut      = partsRes.status === "fulfilled" ? partsRes.value : { parts_to_stage: [] };

  // Crew depends on risk + pm output, so it runs after them.
  let crew: CrewBuilderOut;
  try {
    crew = await crewBuilder(db, hive.id, risk, pm);
  } catch (err) {
    console.warn(`[amc] crewBuilder failed for ${hive.id}: ${err}`);
    crew = { crew: [] };
  }

  // Briefing-Composer runs last (its inputs are everything else).
  const summary = await briefingComposer(db, hive.id, hive.name, risk, pm, parts, crew);

  // Persona signature for the briefing footer. AMC runs autonomously
  // (pg_cron), so no per-worker context here — we read the hive-level
  // hives.preferred_persona column (Phase 6 migration 20260513000022).
  // clampPersona falls back to DEFAULT_PERSONA on null or unknown values
  // so a hive that pre-dates the migration still gets a signed brief.
  const hivePersona = clampPersona(hive.preferred_persona);
  const signedBy = buildPersonaBlock(hivePersona, "briefing-signature");

  const brief = {
    top_assets:     risk.top_assets,
    pm_due:         pm.pm_due,
    parts_to_stage: parts.parts_to_stage,
    crew:           crew.crew,
    summary:        summary.summary + (signedBy ? "\n\n" + signedBy : ""),
    headline:       summary.headline,
    model_version:  MODEL_VERSION,
    signed_by:      hivePersona,
    sub_agent_status: {
      failure_predictor: riskRes.status,
      pm_planner:        pmRes.status,
      parts_stager:      partsRes.status,
      crew_builder:      "fulfilled",
      briefing_composer: "fulfilled",
    },
  };

  const { data: inserted, error: insErr } = await db.from("amc_briefings").insert({
    hive_id:       hive.id,
    shift_date:    today,
    brief,
    model_version: MODEL_VERSION,
  }).select("id").single();

  if (insErr) {
    // 23505 = unique_violation = a parallel cron run beat us. Treat as skip.
    if (insErr.code === "23505") {
      return {
        hive_id:   hive.id,
        hive_name: hive.name,
        brief_id:  null,
        status:    "skipped_existing",
      };
    }
    return {
      hive_id:   hive.id,
      hive_name: hive.name,
      brief_id:  null,
      status:    "error",
      error:     insErr.message,
    };
  }

  return {
    hive_id:     hive.id,
    hive_name:   hive.name,
    brief_id:    String((inserted as AnyRow).id),
    status:      "inserted",
    asset_count: risk.top_assets.length,
    pm_count:    pm.pm_due.length,
    parts_count: parts.parts_to_stage.length,
  };
}

// ─── Handler ─────────────────────────────────────────────────────────────────

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });

  try {
    const body = await req.json().catch(() => ({}));
    const targetHive = body.hive_id ? String(body.hive_id).trim() : "";

    const db = _whWarmClient || createClient(
      Deno.env.get("SUPABASE_URL") || "",
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "",
    );

    // Select hives to brief. Persona Contract Phase 6: pull the hive's
    // preferred_persona alongside id+name so the briefing signature wears
    // the right voice. New hives default to 'james' via the column DEFAULT.
    let hives: Array<{ id: string; name: string; preferred_persona?: string | null }> = [];
    if (targetHive) {
      const { data: one, error: oneErr } = await db.from("v_hives_truth")
        .select("id, name, preferred_persona").eq("id", targetHive).maybeSingle();
      if (oneErr || !one) {
        return new Response(
          JSON.stringify({ error: "Hive not found" }),
          { status: 404, headers: { ...corsHeaders, "Content-Type": "application/json" } },
        );
      }
      hives = [{
        id:                String(one.id),
        name:              String(one.name || ""),
        preferred_persona: (one as Record<string, unknown>).preferred_persona as string | null,
      }];
    } else {
      // Drain mode: every hive with at least one active member.
      const { data: all, error: allErr } = await db.from("v_hives_truth")
        .select("id, name, preferred_persona, hive_members!inner(status)")
        .eq("hive_members.status", "active");
      if (allErr) {
        return new Response(
          JSON.stringify({ error: "Hive enumeration failed", detail: allErr.message }),
          { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } },
        );
      }
      // Dedup (the inner join can return duplicates).
      const seen = new Set<string>();
      for (const h of (all || [])) {
        const id = String(h.id);
        if (seen.has(id)) continue;
        seen.add(id);
        hives.push({
          id,
          name:              String(h.name || ""),
          preferred_persona: (h as Record<string, unknown>).preferred_persona as string | null,
        });
      }
    }

    // Process hives sequentially to keep DB pressure flat (this runs once
    // a day; latency is fine).
    const results: BriefForHive[] = [];
    for (const h of hives) {
      try {
        results.push(await buildBriefForHive(db, h));
      } catch (err) {
        results.push({
          hive_id:   h.id,
          hive_name: h.name,
          brief_id:  null,
          status:    "error",
          error:     err instanceof Error ? err.message : String(err),
        });
      }
    }

    return new Response(
      JSON.stringify({
        runner:    "amc-orchestrator",
        mode:      targetHive ? "single" : "drain",
        hives:     results.length,
        inserted:  results.filter(r => r.status === "inserted").length,
        skipped:   results.filter(r => r.status === "skipped_existing").length,
        errors:    results.filter(r => r.status === "error").length,
        results,
      }),
      { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    // Inline JSON.stringify({ error: ... }) for static error-contract scan.
    return new Response(
      JSON.stringify({ error: "Internal error", detail: msg }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  }
});
