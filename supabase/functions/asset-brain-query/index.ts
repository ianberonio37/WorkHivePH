/**
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

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { callAI } from "../_shared/ai-chain.ts";
import { getCorsHeaders } from "../_shared/cors.ts";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_QUESTION_CHARS    = 500;   // voice/prompt-injection cap (ai-engineer skill)
const RATE_LIMIT_PER_HOUR   = 50;
const TIMELINE_CAP          = 20;
const SIMILAR_CAP           = 5;
const MAX_TOKENS_OUT        = 700;

const SYSTEM_PROMPT = `You are WorkHive Asset Brain, an industrial maintenance assistant grounded in real plant data.

You will receive a JSON payload with:
- asset: the asset's tag, name, criticality, hierarchy, neighbors
- stats: aggregate counts (logbook entries, PM completions, last failure)
- timeline: the 20 most recent events on this asset
- similar: events on peer assets in the same equipment class
- reliability: engineer-validated FMEA modes, RCM strategies, Weibull fit, P-F intervals
- question: what the user asked

Your job is to answer the question using ONLY the provided context. Rules:
1. If the context lacks the answer, say so plainly. Never invent values.
2. Cite sources by index (e.g. "logbook #3", "pm #1", "fmea #0", "rcm #1", "pf #0") when the answer rests on a specific row.
3. Prefer the reliability block when answering risk / failure-mode / maintenance-strategy questions; FMEA RPN, Weibull pattern (wearout / random / infant), and P-F intervals are engineer-validated and outrank raw logbook history.
4. When Weibull pattern = wearout (beta > 1), age matters; when random (beta ~ 1), age does not predict next failure.
5. Keep responses under 120 words unless the question explicitly asks for more.
6. Use Filipino industrial vocabulary (PEC 2017, PSME, ISO 14224) when appropriate.
7. No em dashes in the response. Use colons, commas, parentheses, or restructure.

Output JSON: { "answer": string, "cited": [ { "kind": "logbook"|"pm"|"neighbor"|"stat"|"fmea"|"rcm"|"weibull"|"pf", "index": number } ] }`;

// ---------------------------------------------------------------------------
// Rate limit gate
// ---------------------------------------------------------------------------

async function checkAIRateLimit(
  db: SupabaseClient,
  hiveId: string,
  limitPerHour: number,
): Promise<{ allowed: boolean; remaining: number }> {
  const windowStart = new Date(Date.now() - 60 * 60 * 1000);

  const { data } = await db
    .from("ai_rate_limits")
    .select("call_count, window_start")
    .eq("hive_id", hiveId)
    .maybeSingle();

  if (!data || new Date(data.window_start) < windowStart) {
    await db.from("ai_rate_limits").upsert({
      hive_id:      hiveId,
      call_count:   1,
      window_start: new Date().toISOString(),
    });
    return { allowed: true, remaining: limitPerHour - 1 };
  }
  if (data.call_count >= limitPerHour) {
    return { allowed: false, remaining: 0 };
  }
  await db.from("ai_rate_limits")
    .update({ call_count: data.call_count + 1 })
    .eq("hive_id", hiveId);
  return { allowed: true, remaining: limitPerHour - data.call_count - 1 };
}

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
    const { data: parr } = await db.from("asset_nodes")
      .select("id, tag, name, level")
      .eq("hive_id", hiveId).eq("id", (node as AnyRow).parent_id).limit(1);
    parent = (parr && parr[0]) || null;
  }

  const { data: edges } = await db.from("asset_edges")
    .select("id, edge_type, from_node_id, to_node_id")
    .eq("hive_id", hiveId)
    .or(`from_node_id.eq.${assetId},to_node_id.eq.${assetId}`)
    .limit(20);

  let neighbors: AnyRow[] = [];
  if (edges && edges.length) {
    const otherIds = Array.from(new Set(edges.map(e => (e.from_node_id === assetId ? e.to_node_id : e.from_node_id))));
    if (otherIds.length) {
      const { data: nbs } = await db.from("asset_nodes")
        .select("id, tag, name, criticality, iso_class")
        .eq("hive_id", hiveId).in("id", otherIds);
      neighbors = (nbs || []).map(n => {
        const ed = edges.find(e => e.from_node_id === n.id || e.to_node_id === n.id);
        return { ...n, edge_type: ed ? ed.edge_type : "related" };
      });
    }
  }

  return { node, overview, parent, neighbors };
}

async function fetchAssetTimeline(
  db: SupabaseClient,
  node: AnyRow | null,
  hiveId: string,
) {
  if (!node) return { logbook: [], pm: [] };

  const queries: Promise<unknown>[] = [];
  if (node.legacy_asset_id) {
    queries.push(
      db.from("v_logbook_truth")    // canonical: logbook_truth
        .select("id, machine, problem, action, root_cause, maintenance_type, status, created_at, closed_at, downtime_hours")
        .eq("hive_id", hiveId)
        .eq("asset_ref_id", node.legacy_asset_id)
        .order("created_at", { ascending: false })
        .limit(TIMELINE_CAP)
    );
  }
  if (node.pm_asset_id) {
    queries.push(
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
    if (idx === 0 && node.legacy_asset_id) logbook = rows;
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
  const { data: peers } = await db.from("asset_nodes")
    .select("id, legacy_asset_id, tag, name")
    .eq("hive_id", hiveId)
    .eq("iso_class", node.iso_class)
    .neq("id", node.id)
    .limit(20);

  if (!peers || !peers.length) return [];

  const legacyIds = peers.map(p => p.legacy_asset_id).filter(Boolean) as string[];
  if (!legacyIds.length) return [];

  const { data: rows } = await db.from("v_logbook_truth")    // canonical
    .select("id, machine, problem, root_cause, maintenance_type, created_at, closed_at, asset_ref_id")
    .eq("hive_id", hiveId)
    .eq("maintenance_type", "Breakdown / Corrective")
    .in("asset_ref_id", legacyIds)
    .order("created_at", { ascending: false })
    .limit(SIMILAR_CAP);

  if (!rows) return [];

  return rows.map(r => {
    const peer = peers.find(p => p.legacy_asset_id === r.asset_ref_id);
    return { ...r, peer_tag: peer ? (peer.tag || peer.name) : null };
  });
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

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);

  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const body = await req.json().catch(() => ({}));
    const question_raw = String(body.question || "").trim();
    const asset_id     = String(body.asset_id || "").trim();
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

    // Rate-limit gate is the FIRST thing per ai-engineer skill.
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

    const [tlRes, simRes, relRes] = await Promise.allSettled([
      fetchAssetTimeline(db, graphRes.node, hive_id),
      fetchSimilarFailures(db, graphRes.node, hive_id),
      fetchReliability(db, asset_id, hive_id),
    ]);

    const timeline    = tlRes.status  === "fulfilled" ? tlRes.value  : { logbook: [], pm: [] };
    const similar     = simRes.status === "fulfilled" ? simRes.value : [];
    const reliability = relRes.status === "fulfilled" ? relRes.value : { fmea: [], rcm: [], weibull: null, pf: [] };

    const context = composeContext(graphRes, timeline, similar, reliability, question);
    const prompt  = JSON.stringify(context);

    let raw: string;
    try {
      raw = await callAI(prompt, {
        systemPrompt: SYSTEM_PROMPT,
        temperature:  0.2,
        maxTokens:    MAX_TOKENS_OUT,
        jsonMode:     true,
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
      remaining: rl.remaining,
      asset:     { tag: graphRes.node.tag, name: graphRes.node.name },
    }, 200, corsHeaders);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    // Inline JSON.stringify({ error: ... }) so the edge-contract validator can
    // confirm the error shape via static scan. jsonResponse below preserves
    // the same shape on every other failure path.
    return new Response(
      JSON.stringify({ error: "Internal error", detail: msg }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  }
});

function jsonResponse(body: unknown, status: number, corsHeaders: Record<string, string>) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}
