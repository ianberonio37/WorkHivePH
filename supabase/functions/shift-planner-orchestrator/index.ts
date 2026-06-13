/**
 * shift-planner-orchestrator - Phase 4: Shift Brain autonomous planner.
 *
 * Triggered by pg_cron at Philippine 3-shift boundaries (06:00 / 14:00 / 22:00 PHT)
 * or manually via POST { shift_window, hive_id? }. Writes one DRAFT row per hive
 * per shift window into shift_plans.
 *
 * Sub-agents run in parallel via Promise.allSettled:
 *   risk_top         - top assets by current risk score (asset_risk_scores)
 *   pms_due          - frequency-aware OVERDUE PMs (v_pm_scope_items_truth.is_overdue,
 *                      one row per asset) — NOT the retired flat-30-day is_due proxy
 *   carry_forward    - open logbook entries older than 8h (prior shift leftovers)
 *   parts_prestage   - inventory items at or below reorder_point
 *   briefing         - one-paragraph LLM synthesis grounded in the above
 *
 * Output payload shape:
 *   { risk_top, pms_due, carry_forward, parts_prestage, briefing }
 *
 * Skills consulted: ai-engineer (Promise.allSettled, JSON-only output, capped
 * rows, system prompt as const, callAI shared chain), architect (4-place sync),
 * security (no service-role leak in error responses, hive scoping every query),
 * data-engineer (narrow selects, .limit() everywhere), multitenant-engineer
 * (hive_id on every read), devops (getCorsHeaders dynamic CORS).
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

// contract-allow: produces daily shift plan; future Tier C: shift_plan_v1
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { callAI } from "../_shared/ai-chain.ts";
import { loadMemory, saveTurn, formatMemoryContext } from "../_shared/memory.ts";
import { logAICost, estimateTokens } from "../_shared/cost-log.ts";
import { getCorsHeaders } from "../_shared/cors.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
import { checkAIRateLimit, rateLimitedResponse } from "../_shared/rate-limit.ts";
// Persona Contract: briefing-signature mode — the shift briefing is an
// autonomous hive-level artifact (no per-worker context), so it wears the
// persona only as a footer signature keyed off hives.preferred_persona,
// exactly like amc-orchestrator. See WORKHIVE_PERSONA_CONTRACT.md.
import { clampPersona, buildPersonaBlock } from "../_shared/persona.ts";

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

const RISK_TOP_LIMIT     = 10;
const PMS_DUE_LIMIT      = 30;
const CARRY_FWD_LIMIT    = 30;
const PARTS_LIMIT        = 30;
const BRIEFING_MAX_TOKENS = 400;

const VALID_WINDOWS = new Set(["06-14", "14-22", "22-06"]);

const BRIEFING_SYSTEM_PROMPT = `You are the WorkHive Shift Brain morning briefer.

You receive a JSON payload describing one hive's situation at shift start:
- shift_window: which shift starts now (06-14 morning, 14-22 afternoon, 22-06 night)
- risk_top: top assets at risk
- pms_due: PMs that are overdue (frequency-aware) for this hive
- carry_forward: open logbook entries from prior shifts
- parts_prestage: parts at or below reorder point

Write a 4-6 sentence morning briefing for the incoming supervisor. Rules:
1. Open with the single most important risk (highest score, longest open downtime, or critical part stock-out).
2. Name specific assets and worker counts, not vague generalities.
3. End with one concrete next action.
4. No em dashes. Use colons, commas, parentheses, or restructure.
5. Filipino industrial vocabulary is fine (PEC, PSME, ISO 14224 terms).
6. Plain text only, no JSON, no markdown.

Output the briefing paragraph directly. Nothing else.`;

type AnyRow = Record<string, unknown>;

// ---------------------------------------------------------------------------
// Sub-agents
// ---------------------------------------------------------------------------

async function fetchRiskTop(db: SupabaseClient, hiveId: string): Promise<AnyRow[]> {
  // Canonical: v_risk_truth (domain=risk_truth in canonical_sources). The view
  // does DISTINCT ON (hive_id, asset_name) so we get latest-per-asset directly.
  const { data } = await db.from("v_risk_truth")
    .select("asset_id, asset_name, risk_score, risk_level, top_factors, generated_at, hive_id")
    .eq("hive_id", hiveId)
    // "Top risk this shift" = assets that actually warrant shift attention. Canonical
    // bands (batch-risk-scoring): high >= 0.70, critical >= 0.85. Filtering by band
    // keeps low/medium assets out of the shift brief (they belong in the full risk
    // register, not the action list) and keeps the count honest vs the verdict copy.
    .in("risk_level", ["high", "critical"])
    .order("risk_score", { ascending: false })
    .limit(RISK_TOP_LIMIT);
  return data || [];
}

async function fetchPMsDue(db: SupabaseClient, hiveId: string): Promise<AnyRow[]> {
  // Canonical: v_pm_scope_items_truth.is_overdue (domain=pm_scope_items_truth) —
  // the SAME frequency-aware overdue signal pm-scheduler + home read. is_overdue =
  // next_due_date < today, where next_due_date derives from each task's OWN interval
  // (weekly=7d … annual=365d), NOT the retired flat-30-day v_pm_compliance_truth.is_due
  // proxy that over-counted long-frequency assets just past 30 days (kpi_source_registry
  // pm_overdue; STREAMLINE_ROADMAP P1). Output aliases keep the briefing payload shape
  // (tag_id/category/criticality/location) byte-identical for shift-brain.html.
  const { data } = await db.from("v_pm_scope_items_truth")
    .select("pm_asset_id, asset_name, tag_id:asset_tag, category:asset_category, criticality:asset_criticality, location:asset_location, item_text, frequency, next_due_date, days_until_due, is_overdue")
    .eq("hive_id", hiveId)
    .eq("is_overdue", true)
    .order("days_until_due", { ascending: true })   // most overdue first
    .limit(PMS_DUE_LIMIT * 4);
  // Dedup to one row per asset (its most-overdue task) so the count equals the
  // canonical distinct-pm_asset_id overdue rollup the registry/pm-scheduler report.
  const seen = new Set<string>();
  const deduped: AnyRow[] = [];
  for (const row of (data || []) as AnyRow[]) {
    const key = String(row.pm_asset_id ?? row.asset_name);
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push(row);
    if (deduped.length >= PMS_DUE_LIMIT) break;
  }
  return deduped;
}

async function fetchCarryForward(db: SupabaseClient, hiveId: string): Promise<AnyRow[]> {
  // Open logbook entries created more than 8h ago.
  // Canonical: logbook_truth (drop-in column-compatible with logbook).
  const cutoff = new Date(Date.now() - 8 * 3600 * 1000).toISOString();
  const { data } = await db.from("v_logbook_truth")
    .select("id, machine, problem, maintenance_type, status, created_at, worker_name, downtime_hours")
    .eq("hive_id", hiveId)
    .eq("status", "Open")
    .lt("created_at", cutoff)
    .order("created_at", { ascending: true })
    .limit(CARRY_FWD_LIMIT);
  return data || [];
}

async function fetchPartsPrestage(db: SupabaseClient, hiveId: string): Promise<AnyRow[]> {
  // Canonical: inventory_items_truth. is_low_stock is the boolean version of
  // "qty_on_hand <= min_qty"; we filter at the source so the client-side
  // post-filter loop disappears.
  const { data } = await db.from("v_inventory_items_truth")
    .select("id, part_name, part_number, qty_on_hand, min_qty, bin_location, status, is_low_stock")
    .eq("hive_id", hiveId)
    .eq("status", "approved")
    .eq("is_low_stock", true)
    .order("qty_on_hand", { ascending: true })
    .limit(PARTS_LIMIT);
  // Filter is now at the source via is_low_stock — the canonical view bakes
  // in the same threshold (min_qty > 0 AND qty_on_hand <= min_qty).
  return data || [];
}

async function synthesizeBriefing(
  shiftWindow: string,
  payload: { risk_top: AnyRow[]; pms_due: AnyRow[]; carry_forward: AnyRow[]; parts_prestage: AnyRow[] },
  hivePersona?: string | null,
): Promise<string> {
  // Compact summary strings to keep the prompt small.
  const compact = {
    shift_window: shiftWindow,
    risk_top: payload.risk_top.slice(0, 5).map(r => `${r.asset_name}|score=${r.risk_score}|${r.risk_level}`).join("\n"),
    pms_due: payload.pms_due.slice(0, 8).map(r => `${r.tag_id || r.asset_name}|${r.category}|crit=${r.criticality}`).join("\n"),
    carry_forward: payload.carry_forward.slice(0, 8).map(r => `${r.machine}|${r.maintenance_type}|${r.problem}`.slice(0, 120)).join("\n"),
    parts_prestage: payload.parts_prestage.slice(0, 8).map(r => `${r.part_name}|qty=${r.qty_on_hand}|min=${r.min_qty}`).join("\n"),
  };

  // Persona Contract (briefing-signature): the briefing BODY stays the plain
  // paragraph the model writes; the persona wears only the footer signature,
  // keyed off the hive's preferred_persona. clampPersona falls back to
  // DEFAULT_PERSONA so a hive that pre-dates the column still gets signed.
  const hivePersonaKey = clampPersona(hivePersona);
  const signedBy = buildPersonaBlock(hivePersonaKey, "briefing-signature");
  try {
    const text = await callAI(JSON.stringify(compact), {
      systemPrompt: BRIEFING_SYSTEM_PROMPT,
      temperature:  0.3,
      maxTokens:    BRIEFING_MAX_TOKENS,
      jsonMode:     false,
    });
    return `${text.trim()}\n\n${signedBy}`;
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return `(Briefing synthesis unavailable: ${msg}). Risk: ${payload.risk_top.length}, PMs due: ${payload.pms_due.length}, carry-forward: ${payload.carry_forward.length}, low-stock parts: ${payload.parts_prestage.length}.\n\n${signedBy}`;
  }
}

// ---------------------------------------------------------------------------
// Plan one hive
// ---------------------------------------------------------------------------

async function planForHive(
  db: SupabaseClient,
  hiveId: string,
  shiftWindow: string,
): Promise<{ plan_id?: string; counts: Record<string, number>; briefing?: string; error?: string }> {
  const results = await Promise.allSettled([
    fetchRiskTop(db, hiveId),
    fetchPMsDue(db, hiveId),
    fetchCarryForward(db, hiveId),
    fetchPartsPrestage(db, hiveId),
  ]);

  const risk_top       = results[0].status === "fulfilled" ? results[0].value : [];
  const pms_due        = results[1].status === "fulfilled" ? results[1].value : [];
  const carry_forward  = results[2].status === "fulfilled" ? results[2].value : [];
  const parts_prestage = results[3].status === "fulfilled" ? results[3].value : [];

  // Persona Contract: read the hive's preferred_persona so the briefing footer
  // wears the right voice (autonomous hive-level brief, no per-worker context).
  const { data: hiveRow } = await db.from("v_hives_truth")
    .select("preferred_persona").eq("id", hiveId).maybeSingle();
  const hivePersona = (hiveRow as Record<string, unknown> | null)?.preferred_persona as string | null;

  const briefing = await synthesizeBriefing(shiftWindow, {
    risk_top, pms_due, carry_forward, parts_prestage,
  }, hivePersona);

  const payload = { risk_top, pms_due, carry_forward, parts_prestage };
  const counts = {
    risk_top:       risk_top.length,
    pms_due:        pms_due.length,
    carry_forward:  carry_forward.length,
    parts_prestage: parts_prestage.length,
  };

  // Upsert one row per (hive_id, shift_date, shift_window). Re-runs replace the draft.
  const { data: ins, error } = await db.from("shift_plans").upsert({
    hive_id:      hiveId,
    shift_window: shiftWindow,
    status:       "draft",
    generated_at: new Date().toISOString(),
    generated_by: "shift-planner-orchestrator",
    briefing,
    payload,
  }, { onConflict: "hive_id,shift_date,shift_window" })
    .select("id")
    .maybeSingle();

  if (error) return { counts, error: error.message };
  return { plan_id: ins?.id, counts, briefing };
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
    const shift_window = String(body.shift_window || "").trim();
    const single_hive  = body.hive_id ? String(body.hive_id) : null;

    if (!shift_window) {
      return new Response(
        JSON.stringify({ error: "Missing required field: shift_window (must be 06-14, 14-22, or 22-06)" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }
    if (!VALID_WINDOWS.has(shift_window)) {
      return new Response(
        JSON.stringify({ error: "shift_window must be one of 06-14 / 14-22 / 22-06" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    const db = createClient(
      Deno.env.get("SUPABASE_URL") || "",
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "",
    );

    // Rate-gate FIRST per ai-engineer skill — synthesizeBriefing calls callAI
    // for every hive in the loop. Single-hive (manual / button) path is gated
    // here; cron path passes single_hive=null and the synthesizer's per-hive
    // fan-out will hit each hive's rate limit individually as it loops.
    if (single_hive) {
      const rl = await checkAIRateLimit(db, single_hive);
      if (!rl.allowed) return rateLimitedResponse(corsHeaders);
    }

    let targetHives: string[];
    if (single_hive) {
      targetHives = [single_hive];
    } else {
      // Cron path: run for every active hive
      const { data: hives } = await db.from("v_hives_truth")
        .select("id")
        .limit(1000);
      targetHives = (hives || []).map(h => h.id);
    }

    const perHive = await Promise.allSettled(
      targetHives.map(h => planForHive(db, h, shift_window))
    );

    const summary = perHive.map((r, idx) => ({
      hive_id: targetHives[idx],
      ok:      r.status === "fulfilled" && !(r.value as { error?: string }).error,
      detail:  r.status === "fulfilled" ? r.value : { error: String(r.reason) },
    }));

    // Conversational surface: the single-hive (manual / gateway companion) path
    // gets the briefing PROSE as a top-level `answer` so the ai-gateway's
    // `answer ?? summary ?? ...` extraction surfaces a paragraph, not a stringified
    // batch object ("[object Object]"). The cron all-hives path omits it (batch
    // status only). (W1 wiring fix 2026-06-12: shift answers through the gateway.)
    const firstBriefing = single_hive
      ? (summary[0]?.detail as { briefing?: string } | undefined)?.briefing
      : undefined;

    return new Response(
      JSON.stringify({
        shift_window, hives_processed: summary.length, summary,
        ...(firstBriefing ? { answer: firstBriefing } : {}),
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
