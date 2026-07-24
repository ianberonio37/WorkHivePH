/**
// capability: ai_specialist_asset_brain
 * asset-brain-query - Phase 3: GraphRAG retrieval for Asset Hub.
 *
 * Receives a natural-language question about a specific asset and returns a
 * grounded answer with cited sources. Three retrieval lanes run in parallel:
 *
 *   Lane A - Graph context: the asset itself, its parents, and its neighbors
 *            via asset_edges. Plus aggregate stats from v_asset_truth (canonical asset 360).
 *   Lane B - Timeline: most recent logbook entries (via legacy_asset_id) and
 *            pm_completions (via pm_asset_id), capped at 20 events.
 *   Lane C - Similar failures: keyword search on logbook entries within the
 *            same hive and iso_class. Vector search is wired in Phase 5 once
 *            asset_embeddings has coverage.
 *
 * The composed payload is sent to the shared AI chain with strict token
 * discipline: row count capped at 200, summary strings only, JSON output.
 *
 * Skills consulted before writing: ai-engineer (callAI, rate-limit, model
 * agnostic, JSON output), architect (4-place sync), security (no service-role
 * leak in errors, hive scoping on every query), data-engineer (narrow selects,
 * keyset capped), multitenant-engineer (hive_id on every read), devops
 * (getCorsHeaders dynamic, no static origin).
 */

import { serveObserved, failTracked } from "../_shared/observability.ts";

// contract-allow: natural-language asset query; passthrough to AI
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { callAI } from "../_shared/ai-chain.ts";
// Persona Contract: narrated-specialist mode — answer JSON gains a
// `narration` field with 1-2 sentence prose in the persona's voice.
// See WORKHIVE_PERSONA_CONTRACT.md.
import { clampPersona, buildPersonaBlock } from "../_shared/persona.ts";
import { loadMemory, saveTurn, formatMemoryContext } from "../_shared/memory.ts";
import { logAICost, estimateTokens } from "../_shared/cost-log.ts";
import { redactPII } from "../_shared/redactPII.ts";
import { getCorsHeaders } from "../_shared/cors.ts";
// Pillar O (Observability): expose a /health probe for the gateway status page.
import { handleHealth } from "../_shared/health.ts";
import { log } from "../_shared/logger.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";

// Warm module-scope Supabase client (PRODUCTION_FIXES #46).
const _WH_SUPABASE_URL_M = Deno.env.get("SUPABASE_URL") || "";
const _WH_SERVICE_KEY_M  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const _whWarmClient = _WH_SUPABASE_URL_M && _WH_SERVICE_KEY_M
  ? createClient(_WH_SUPABASE_URL_M, _WH_SERVICE_KEY_M)
  : null;
void _whWarmClient;

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_QUESTION_CHARS    = 500;   // voice/prompt-injection cap (ai-engineer skill)
const RATE_LIMIT_PER_HOUR   = Number(Deno.env.get("WH_RATE_LIMIT_OVERRIDE") || 50);
const TIMELINE_CAP          = 20;
const SIMILAR_CAP           = 5;
const MAX_TOKENS_OUT        = 700;

const SYSTEM_PROMPT = `You are WorkHive Asset Brain, an industrial maintenance assistant grounded in real plant data.

You will receive a JSON payload with:
- asset: the asset's tag, name, criticality, hierarchy, neighbors
- stats: aggregate counts (logbook entries, PM completions, last failure)
- risk: the canonical risk snapshot from v_risk_truth (daily, 365-day failure window) — risk_score 0..1, risk_level, mtbf_days, days_until_failure, and a structured top_factors array. This is the same risk the Predictive Maintenance page and Alert Hub show.
- timeline: the 20 most recent events on this asset
- similar: events on peer assets in the same equipment class
- reliability: engineer-validated FMEA modes, RCM strategies, Weibull fit, P-F intervals
- question: what the user asked

Your job is to answer the question using ONLY the provided context. Rules:
1. If the context lacks the answer, say so plainly. Never invent values.
2. Cite sources by index (e.g. "logbook #3", "pm #1", "fmea #0", "rcm #1", "pf #0", "risk", "risk-factor #0") when the answer rests on a specific row.
3. For "why is this asset at risk / what is driving the risk score" questions, cite from risk.top_factors and quote each factor's explanation verbatim. The risk score is a WorkHive composite per SAE JA1011 §5.4 + IEC 60812 RPN + Weibull wear-out (platform-calibrated blend) — never claim it is a single standard's prescription. Do NOT re-derive factors from the raw timeline; the risk block is the canonical answer the rest of the platform agrees on.
4. Prefer the reliability block when answering failure-mode / maintenance-strategy questions; FMEA RPN (IEC 60812:2018), Weibull pattern (wearout / random / infant), and P-F intervals (SAE JA1011 §6) are engineer-validated and outrank raw logbook history.
5. When Weibull pattern = wearout (beta > 1), age matters; when random (beta ~ 1), age does not predict next failure.
6. Keep responses under 120 words unless the question explicitly asks for more.
7. Use Filipino industrial vocabulary (PEC 2017, PSME, ISO 14224) when appropriate.
8. No em dashes in the response. Use colons, commas, parentheses, or restructure.

Output JSON: { "answer": string, "cited": [ { "kind": "logbook"|"pm"|"neighbor"|"stat"|"fmea"|"rcm"|"weibull"|"pf"|"risk"|"risk-factor", "index": number } ], "narration": string }

narration is a 1-2 sentence prose summary of the answer in your persona's voice (Phase 7 TTS picks the voice). Paraphrase only what's in the answer; quote any number or asset name verbatim.`;

// ---------------------------------------------------------------------------
// Rate limit gate — A5 (FULLSTACK_COMPONENT_LIBRARY Layer A, 2026-07-17): the local
// checkAIRateLimit copy was a DIVERGED pre-day-ceiling twin of the canonical
// _shared/rate-limit.ts version (no daily cap, no solo-mode, racy double-write).
// Delegated to the canonical — same call site, richer protection.
// ---------------------------------------------------------------------------
import { checkAIRateLimit, checkRouteRateLimit, routeRateLimitedResponse } from "../_shared/rate-limit.ts";

// ---------------------------------------------------------------------------
// Retrieval lanes
// ---------------------------------------------------------------------------

type AnyRow = Record<string, unknown>;

async function fetchAssetGraphContext(
  db: SupabaseClient,
  assetId: string,
  hiveId: string,
) {
  // Asset 360 from v_asset_truth (canonical view, domain=asset_truth).
  // The view returns metadata + aggregates in one row, so we drop the
  // separate asset_nodes query and derive both node and overview from it.
  const { data: truthArr } = await db.from("v_asset_truth")
    .select("asset_id, tag, name, level, iso_class, criticality, location, manufacturer, model, parent_id, legacy_asset_id, pm_asset_id, external_ids, lifetime_logbook_entries, pm_completed_count, last_failure_at, edge_count")
    .eq("hive_id", hiveId).eq("asset_id", assetId).limit(1);

  const truth: AnyRow | null = (truthArr && truthArr[0]) || null;
  // Adapt to the rest of this function's expected shape: keep `node.id` for
  // downstream queries that join via asset_nodes.id (= v_asset_truth.asset_id).
  const node = truth ? { ...truth, id: truth.asset_id } : null;
  const overview = truth
    ? {
        lifetime_logbook_entries: truth.lifetime_logbook_entries,
        pm_completed_count:       truth.pm_completed_count,
        last_failure_at:          truth.last_failure_at,
        edge_count:               truth.edge_count,
      }
    : null;

  // Parent (single hop) and immediate neighbors via asset_edges.
  let parent: AnyRow | null = null;
  if (node && (node as AnyRow).parent_id) {
    const { data: parr } = await db.from("v_asset_truth")
      .select("id:asset_id, tag, name, level")
      .eq("hive_id", hiveId).eq("asset_id", (node as AnyRow).parent_id).limit(1);
    parent = (parr && parr[0]) || null;
  }

  // Arc Y Y5 (fork#1, Ian 2026-06-27): the asset_edges "neighbors" feature was CUT
  // entirely. The graph-edge UI was confusing jargon and the table is no longer
  // maintained, so the AI Asset Brain no longer reads it for neighbor context.
  // `parent` (from v_asset_truth.parent_id) still provides asset hierarchy.
  const neighbors: AnyRow[] = [];

  return { node, overview, parent, neighbors };
}

async function fetchAssetTimeline(
  db: SupabaseClient,
  node: AnyRow | null,
  hiveId: string,
) {
  if (!node) return { logbook: [], pm: [] };

  const queries: Promise<unknown>[] = [];
  // Phase 5b: logbook is now keyed by asset_node_id (uuid) directly; the
  // legacy_asset_id text bridge was dropped. node.id is the canonical uuid.
  queries.push(
    db.from("v_logbook_truth")    // canonical: logbook_truth
      .select("id, machine, problem, action, root_cause, maintenance_type, status, created_at, closed_at, downtime_hours")
      .eq("hive_id", hiveId)
      .eq("asset_node_id", node.id)
      .order("created_at", { ascending: false })
      .limit(TIMELINE_CAP)
  );
  if (node.pm_asset_id) {
    queries.push(
      // canonical-allow: per-completion timeline rows; the rollup view has no
      // completed_at/worker_name/scope_item_id. (PROJ-DRIFT triage)
      db.from("pm_completions")
        .select("id, asset_id, completed_at, worker_name, scope_item_id")
        .eq("hive_id", hiveId)
        .eq("asset_id", node.pm_asset_id)
        .order("completed_at", { ascending: false })
        .limit(TIMELINE_CAP)
    );
  }

  const results = await Promise.allSettled(queries);
  let logbook: AnyRow[] = [];
  let pm: AnyRow[] = [];

  results.forEach((res, idx) => {
    if (res.status !== "fulfilled") return;
    const v = res.value as { data?: AnyRow[] };
    const rows = v.data || [];
    if (idx === 0) logbook = rows;
    else pm = rows;
  });

  return { logbook, pm };
}

async function fetchSimilarFailures(
  db: SupabaseClient,
  node: AnyRow | null,
  hiveId: string,
) {
  if (!node || !node.iso_class) return [];

  // Find peer assets in the same hive + iso_class (excluding self).
  // canonical-allow: asset-brain neighbor traversal needs the raw graph table
  const { data: peers } = await db.from("v_asset_truth")
    .select("id:asset_id, tag, name")
    .eq("hive_id", hiveId)
    .eq("iso_class", node.iso_class)
    .neq("asset_id", node.id)
    .limit(20);

  if (!peers || !peers.length) return [];

  // Phase 5b: filter logbook by canonical asset_node_id (uuid). The text
  // legacy_asset_id bridge was dropped.
  const peerIds = peers.map(p => p.id).filter(Boolean) as string[];
  if (!peerIds.length) return [];

  const { data: rows } = await db.from("v_logbook_truth")    // canonical
    .select("id, machine, problem, root_cause, maintenance_type, created_at, closed_at, asset_node_id")
    .eq("hive_id", hiveId)
    .eq("maintenance_type", "Breakdown / Corrective")
    .in("asset_node_id", peerIds)
    .order("created_at", { ascending: false })
    .limit(SIMILAR_CAP);

  if (!rows) return [];

  return rows.map(r => {
    const peer = peers.find(p => p.id === r.asset_node_id);
    return { ...r, peer_tag: peer ? (peer.tag || peer.name) : null };
  });
}

// Canonical risk lane: read v_risk_truth so the Asset Brain narrative cites
// the same factors that Predictive Maintenance and Alert Hub display. Closes
// the divergence where Asset Brain re-derived "why is this risky?" from raw
// logbook history while the rest of the platform read top_factors from the
// daily batch-risk-scoring snapshot. The view is hive-scoped and exposes
// asset_id when name resolution against asset_nodes succeeds; we filter by
// asset_id first, then fall back to asset_name match using the node tag/name.
async function fetchRisk(
  db: SupabaseClient,
  node: AnyRow | null,
  assetId: string,
  hiveId: string,
): Promise<AnyRow | null> {
  // Primary path: v_risk_truth.asset_id is populated when the name match
  // against asset_nodes succeeded inside the view. This is the cheap path.
  const { data: byId } = await db.from("v_risk_truth")
    .select("asset_id, asset_name, risk_score, risk_level, health_score, mtbf_days, days_until_failure, top_factors, model_version, generated_at")
    .eq("hive_id", hiveId)
    .eq("asset_id", assetId)
    .limit(1);
  if (byId && byId[0]) return byId[0];

  // Fallback: the view has NULL asset_id when the writer's asset_name string
  // does not case-insensitively match asset_nodes.tag or .name. Look up by
  // the node's own tag/name so this asset still gets its risk row.
  if (!node) return null;
  const candidates = [node.tag, node.name]
    .map(v => (typeof v === "string" ? v.trim() : ""))
    .filter(Boolean);
  if (!candidates.length) return null;

  const { data: byName } = await db.from("v_risk_truth")
    .select("asset_id, asset_name, risk_score, risk_level, health_score, mtbf_days, days_until_failure, top_factors, model_version, generated_at")
    .eq("hive_id", hiveId)
    .in("asset_name", candidates)
    .limit(1);
  return (byName && byName[0]) || null;
}

// Phase R-tie-in: pull reliability canonical truths for this asset so the
// AI can reason about engineer-validated failure modes, RCM strategies,
// Weibull pattern, and P-F intervals — not just raw logbook history.
async function fetchReliability(
  db: SupabaseClient,
  assetId: string,
  hiveId: string,
) {
  const [fmeaRes, rcmRes, weibullRes, pfRes] = await Promise.allSettled([
    db.from("v_fmea_truth")
      .select("failure_mode, function_text, effect_text, cause_text, severity, occurrence, detection, rpn, consequence_class, source")
      .eq("hive_id", hiveId).eq("asset_id", assetId)
      .order("rpn", { ascending: false }).limit(8),
    db.from("v_rcm_truth")
      .select("decision, task_text, interval_days, rationale, written_to_pm_scope_item_id")
      .eq("hive_id", hiveId).eq("asset_id", assetId).limit(8),
    db.from("v_weibull_truth")
      .select("beta, eta_days, failure_pattern, n_failures, n_censored, generated_at")
      .eq("hive_id", hiveId).eq("asset_id", assetId)
      .is("fmea_mode_id", null).limit(1),
    db.from("v_pf_truth")
      .select("parameter, p_threshold, f_threshold, pf_days, recommended_interval_days, basis")
      .eq("hive_id", hiveId).eq("asset_id", assetId).limit(8),
  ]);
  const fmea    = fmeaRes.status    === "fulfilled" ? (fmeaRes.value.data    || []) : [];
  const rcm     = rcmRes.status     === "fulfilled" ? (rcmRes.value.data     || []) : [];
  const weibull = weibullRes.status === "fulfilled" ? ((weibullRes.value.data || [])[0] || null) : null;
  const pf      = pfRes.status      === "fulfilled" ? (pfRes.value.data      || []) : [];
  return { fmea, rcm, weibull, pf };
}

// ---------------------------------------------------------------------------
// Compose narrow payload
// ---------------------------------------------------------------------------

function composeContext(
  graph: { node: AnyRow | null; overview: AnyRow | null; parent: AnyRow | null; neighbors: AnyRow[] },
  timeline: { logbook: AnyRow[]; pm: AnyRow[] },
  similar: AnyRow[],
  reliability: { fmea: AnyRow[]; rcm: AnyRow[]; weibull: AnyRow | null; pf: AnyRow[] },
  risk: AnyRow | null,
  question: string,
) {
  // Token discipline (ai-engineer skill): summary strings, capped row counts.
  return {
    asset: graph.node && {
      tag:         graph.node.tag,
      name:        graph.node.name,
      level:       graph.node.level,
      iso_class:   graph.node.iso_class,
      criticality: graph.node.criticality,
      location:    graph.node.location,
      manufacturer: graph.node.manufacturer,
      model:       graph.node.model,
      parent:      graph.parent ? `${graph.parent.tag} (${graph.parent.level})` : null,
      external_ids: graph.node.external_ids || {},
    },
    stats: graph.overview && {
      lifetime_logbook_entries: graph.overview.lifetime_logbook_entries,
      pm_completed_count:       graph.overview.pm_completed_count,
      last_failure_at:          graph.overview.last_failure_at,
      edge_count:               graph.overview.edge_count,
    },
    // Canonical risk snapshot from v_risk_truth. Same source as predictive.html
    // and alert-hub.html so the narrative cannot drift from the dashboards.
    // top_factors_structured shape: array of { factor, weight, value, contribution, explanation }.
    // Legacy shape: array of plain-string factor names. We pass through whatever
    // the writer emitted; the prompt rules tell the model to quote explanation verbatim.
    risk: risk && {
      risk_score:         risk.risk_score,
      risk_level:         risk.risk_level,
      health_score:       risk.health_score,
      mtbf_days:          risk.mtbf_days,
      days_until_failure: risk.days_until_failure,
      model_version:      risk.model_version,
      generated_at:       risk.generated_at,
      top_factors: Array.isArray(risk.top_factors)
        ? (risk.top_factors as Array<unknown>).map((f, i) => {
            if (f && typeof f === "object") {
              const fo = f as Record<string, unknown>;
              return {
                index:        i,
                factor:       fo.factor,
                weight:       fo.weight,
                value:        fo.value,
                contribution: fo.contribution,
                explanation:  fo.explanation,
              };
            }
            return { index: i, factor: String(f), explanation: null };
          })
        : [],
    },
    neighbors: graph.neighbors.map((n, i) => ({
      index: i, tag: n.tag, edge_type: n.edge_type, criticality: n.criticality,
    })),
    timeline: {
      logbook: timeline.logbook.map((r, i) => ({
        index: i,
        when: r.created_at,
        type: r.maintenance_type,
        problem: r.problem,
        root_cause: r.root_cause,
        action: r.action,
        downtime_hours: r.downtime_hours,
        status: r.status,
      })),
      pm: timeline.pm.map((r, i) => ({
        index: i,
        when: r.completed_at,
        worker: r.worker_name,
      })),
    },
    similar: similar.map((r, i) => ({
      index: i,
      peer_tag: r.peer_tag,
      when: r.created_at,
      problem: r.problem,
      root_cause: r.root_cause,
    })),
    reliability: {
      // Approved FMEA modes ranked by RPN — engineer-validated failure modes.
      fmea: reliability.fmea.map((r, i) => ({
        index:        i,
        rpn:          r.rpn,
        failure_mode: r.failure_mode,
        function:     r.function_text,
        effect:       r.effect_text,
        cause:        r.cause_text,
        severity:     r.severity,
        occurrence:   r.occurrence,
        detection:    r.detection,
        consequence:  r.consequence_class,
        source:       r.source,
      })),
      // RCM strategies per JA1011 — what is the asset's maintenance policy.
      rcm: reliability.rcm.map((r, i) => ({
        index:         i,
        decision:      r.decision,
        task:          r.task_text,
        interval_days: r.interval_days,
        rationale:     r.rationale,
        pm_linked:     !!r.written_to_pm_scope_item_id,
      })),
      // Latest Weibull fit — wear-out vs random vs infant.
      weibull: reliability.weibull && {
        beta:            reliability.weibull.beta,
        eta_days:        reliability.weibull.eta_days,
        failure_pattern: reliability.weibull.failure_pattern,
        n_failures:      reliability.weibull.n_failures,
        n_censored:      reliability.weibull.n_censored,
        generated_at:    reliability.weibull.generated_at,
      },
      // P-F intervals per parameter — recommended inspection cadences.
      pf: reliability.pf.map((r, i) => ({
        index:                     i,
        parameter:                 r.parameter,
        p_threshold:               r.p_threshold,
        f_threshold:               r.f_threshold,
        pf_days:                   r.pf_days,
        recommended_interval_days: r.recommended_interval_days,
        basis:                     r.basis,
      })),
    },
    question,
  };
}

// ---------------------------------------------------------------------------
// Handler
// ---------------------------------------------------------------------------

serveObserved("asset-brain-query", async (req) => {
  const corsHeaders = getCorsHeaders(req);

  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  // Pillar O: /health probe (short-circuits before auth/body parsing).
  const healthResp = await handleHealth(req, "asset-brain-query", async () => ({
    deps: [
      { name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) },
      { name: "ai-chain", ok: Boolean(Deno.env.get("GROQ_API_KEY") || Deno.env.get("CEREBRAS_API_KEY")) },
    ],
  }));
  if (healthResp) return healthResp;

  const _logCtx = beginRequest(req, { route: "asset-brain-query" });
  log.info(_logCtx, "request_start", { method: req.method });

  try {
    const body = await req.json().catch(() => ({}));
    // Gateway shape adapter: ai-gateway forwards `message` + nests asset_id inside
    // `context`, while direct asset-hub callers send `question` + top-level
    // `asset_id`. Accept BOTH so the gateway's 'asset-brain' route works (it was
    // registered but never functional until this adapter — capstone RAG finding
    // 2026-06-07). hive_id is forwarded top-level by both.
    const _ctx = (body.context && typeof body.context === "object") ? body.context : {}; // gateway adapter (capstone RAG fix)
    const question_raw = String(body.question || body.message || "").trim();
    const asset_id     = String(body.asset_id || _ctx.asset_id || "").trim();
    const hive_id      = String(body.hive_id || "").trim();

    if (!question_raw || !asset_id || !hive_id) {
      return jsonResponse({ error: "Missing required fields: question, asset_id, hive_id" }, 400, corsHeaders);
    }

    // Cap question length per ai-engineer skill (prompt-injection / token guard).
    const question = question_raw.slice(0, MAX_QUESTION_CHARS);

    const db = createClient(
      Deno.env.get("SUPABASE_URL") || "",
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "",
    );

    // AuthZ gate (2026-06-07 cross-hive fix): the service-role client bypasses
    // RLS, so re-authenticate the caller BEFORE any read or rate-bucket touch —
    // otherwise a foreign hive_id reads this hive's asset graph (cross-hive IDOR,
    // the same class as the analytics-orchestrator + ai-orchestrator fixes). Both
    // callers (asset-hub direct + ai-gateway 'asset-brain') send the user JWT via
    // db.functions.invoke; the gateway's service-role fallback is the bypass.
    const _bearer = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "");
    const _serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
    if (!(_bearer && _serviceKey && _bearer === _serviceKey)) {
      const { data: { user: _caller } } = await db.auth.getUser(_bearer);
      if (!_caller) {
        return jsonResponse({ error: "Authentication required" }, 401, corsHeaders);
      }
      const { data: _mem } = await db.from("v_worker_truth")
        .select("hive_status").eq("hive_id", hive_id).eq("auth_uid", _caller.id)
        .eq("hive_status", "active").maybeSingle();
      if (!_mem) {
        return jsonResponse({ error: "Caller is not an active member of this hive" }, 403, corsHeaders);
      }
    }

    // Rate-limit gate (after the auth gate so a foreign caller can't drain this
    // hive's bucket; still before any model call, per ai-engineer skill).
    // D12 per-SURFACE quota, OBSERVE-mode (mirrors the shared gateway pattern). Always counts into
    // (hive, route, hour) via hive_route_calls so per-surface AI pressure is VISIBLE - the
    // hive-wide cap alone cannot show which surface is burning the budget. It does NOT deny:
    // checkRouteRateLimit only enforces when an explicit hive_route_quotas row exists, and
    // none do, so this is a no-op behaviour change. Wrapped: quota bookkeeping must never
    // fail a real request.
    try {
      const _rq = await checkRouteRateLimit(db, hive_id || "", "asset-brain-query");
      // Denies ONLY when an explicit hive_route_quotas row exists (rq.per_route), so this stays
      // a no-op until an admin sets a cap - while always counting for attribution.
      if (_rq.per_route && !_rq.allowed) return routeRateLimitedResponse(corsHeaders, "asset-brain-query", _rq.cap);
    } catch { /* empty-catch-allow: per-surface quota bookkeeping must never fail a real request */ }
    const rl = await checkAIRateLimit(db, hive_id, RATE_LIMIT_PER_HOUR);
    if (!rl.allowed) {
      return jsonResponse(
        { error: "AI call limit reached for this hive. Try again in an hour." },
        429,
        corsHeaders,
      );
    }

    // Three retrieval lanes in parallel. allSettled so one failure does not block.
    const graphRes = await fetchAssetGraphContext(db, asset_id, hive_id);
    if (!graphRes.node) {
      return jsonResponse(
        { error: "Asset not found in this hive." },
        404,
        corsHeaders,
      );
    }

    const [tlRes, simRes, relRes, riskRes] = await Promise.allSettled([
      fetchAssetTimeline(db, graphRes.node, hive_id),
      fetchSimilarFailures(db, graphRes.node, hive_id),
      fetchReliability(db, asset_id, hive_id),
      fetchRisk(db, graphRes.node, asset_id, hive_id),
    ]);

    const timeline    = tlRes.status  === "fulfilled" ? tlRes.value  : { logbook: [], pm: [] };
    const similar     = simRes.status === "fulfilled" ? simRes.value : [];
    const reliability = relRes.status === "fulfilled" ? relRes.value : { fmea: [], rcm: [], weibull: null, pf: [] };
    const risk        = riskRes.status === "fulfilled" ? riskRes.value : null;

    const context = composeContext(graphRes, timeline, similar, reliability, risk, question);
    // PII redaction before the prompt leaves the platform: worker_name in
    // the timeline.pm array gets `<redacted>` so the model provider never
    // sees worker identity. Closes PRODUCTION_FIXES #44 for this fn.
    const prompt  = JSON.stringify(redactPII(context));

    // Persona Contract: narrated-specialist block prepended so the
    // model returns its normal answer JSON AND a `narration` field in
    // the chosen persona's voice. One chain call.
    const personaKey = clampPersona((body as Record<string, unknown>).persona);
    const composedSystem = buildPersonaBlock(personaKey, "narrated-specialist") + "\n\n" + SYSTEM_PROMPT;

    let raw: string;
    try {
      raw = await callAI(prompt, {
        systemPrompt: composedSystem,
        temperature:  0.2,
        maxTokens:    MAX_TOKENS_OUT,
        jsonMode:     true,
        // Sticky session (set by ai-gateway): keep this conversation on one model.
        sessionKey:   typeof body.session_key === "string" ? body.session_key : undefined,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      return jsonResponse(
        { error: "AI providers all at capacity. Try again shortly.", detail: msg },
        503,
        corsHeaders,
      );
    }

    let parsed: { answer?: string; cited?: unknown };
    try {
      parsed = JSON.parse(raw);
    } catch {
      // Fallback: return raw text as the answer with no citations.
      parsed = { answer: raw, cited: [] };
    }

    return jsonResponse({
      answer:    String(parsed.answer || "").trim(),
      cited:     Array.isArray(parsed.cited) ? parsed.cited : [],
      // Persona narration (1-2 sentences in Hezekiah/Zaniah voice). Capped to
      // keep responses sane if the model overruns.
      narration: String(parsed.narration || "").trim().slice(0, 280),
      remaining: rl.remaining,
      asset:     { tag: graphRes.node.tag, name: graphRes.node.name },
    }, 200, corsHeaders);
  } catch (err) {
    // T2b: aggregate this HANDLED failure to wh_traces + non-leaky 500.
    return await failTracked(req, "asset-brain-query", "asset_brain_query_error", err);
  }
});

function jsonResponse(body: unknown, status: number, corsHeaders: Record<string, string>) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}
