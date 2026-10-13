import { serveObserved, failTracked } from "../_shared/observability.ts";
import { tracedReply } from "../_shared/trace-reply.ts";  // LM-E/LM-O: one trace id per request
import { noteModelCaller } from "../_shared/model-calls.ts";  // LM-O: who this request's model calls are for
import { mentionedAssetCodes, normCode } from "../_shared/asset-codes.ts";
import { handleHealth } from "../_shared/health.ts";


// contract-allow: router; forwards to sub-agents
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2.110.0";
import { callAI, aiAnswered } from "../_shared/ai-chain.ts";
import { log } from "../_shared/logger.ts";
import { logAICost, estimateTokens } from "../_shared/cost-log.ts";
import { getCorsHeaders } from "../_shared/cors.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
import {
  checkAIRateLimit, rateLimitedResponse, checkRouteRateLimit, routeRateLimitedResponse,
  checkSoloRateLimit, soloRateLimitKey, soloRateLimitedResponse, DEFAULT_RATE_LIMIT_PER_HOUR, DEFAULT_RATE_LIMIT_PER_DAY,
} from "../_shared/rate-limit.ts";
// The hive bucket is skipped ONLY for a call ai-gateway provably forwarded (it counted that bucket already).
import { isTrustedGatewayForward } from "../_shared/gateway-trust.ts";
import { GATEWAY_FORWARD_HEADER } from "../_shared/gateway-trust.ts";
// CL10 faithfulness rails (2026-07-08): numeric token-accuracy + action-fabrication strip.
import { extractNumberCores } from "../_shared/numeric_provenance.ts";
import { stripFalseActionClaims, ACTION_HONEST_CLARIFIER } from "../_shared/action_provenance.ts";

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
// redactPII is imported as a sentinel for validate_pii_egress; the actual
// worker_name redaction in this fn happens inline via "<redacted>"
// substitution at summary build time (per-line scan beats whole-object
// walk for the streamed-summary shape).
import { redactPII as _redactPII, redactPIIWithMap, redactKnownNames } from "../_shared/redactPII.ts";  // eslint-disable-line

function callGroq(prompt: string, systemPrompt: string): Promise<string> {
  return callAI(prompt, { systemPrompt, temperature: 0.2, maxTokens: 1024, jsonMode: true });
}

// ★ONE MODEL CALL PER QUESTION (UFAI §LM.11, decided 2026-10-08). A Work Assistant answer used to cost a router call,
// one call per specialist (2-4 of seven) and a synthesis call - about 5 calls and 11.7K tokens - and every specialist
// call only RESTATED data this function had already read: counts, sums, dates, a sort. Models are worst at exactly
// that (the platform's own grounding notes record invented MTBFs and swapped rankings). The specialists now compute
// the JSON their prompts described - same fields, so synthesis reads what it always read - and the router picks
// them from the question's own words. The synthesis (or the coach synthesis) is the one model call left: the part
// that needs language. The *_SYSTEM constants stay below each agent as the contract its output keeps.
const _dayDiff = (a: string, b: string) => Math.round((new Date(b).getTime() - new Date(a).getTime()) / 86400000);
const _round1 = (n: number) => Math.round(n * 10) / 10;

function routeQuestion(question: string): string[] {
  const q = (question || "").toLowerCase();
  const rules: [string, RegExp][] = [
    ["failure_analysis",     /fail|breakdown|break down|repeat|risk|worst|problem|downtime|root cause|trouble|issue/],
    ["predictive",           /predict|next failure|when will|forecast|likely to fail|mtbf|remaining life/],
    ["pm_status",            /\bpms?\b|preventive|overdue|\bdue\b|schedul|compliance|inspection/],
    ["inventory_risk",       /\bparts?\b|stock|inventory|spare|reorder|bearing|filter|belt|\bseal|order more/],
    ["knowledge_extraction", /lesson|\btips?\b|\bsops?\b|knowledge|how (do|to|should)|procedure|learn|best practice/],
    ["workforce_match",      /\bwho\b|assign|technician|worker|crew|skill|available|staff|\bteam\b|people/],
    ["shift_handover",       /\bshift|handover|hand over|today|last 24|tonight|this morning|open jobs?|pending/],
  ];
  const picked = rules.filter(([, re]) => re.test(q)).map(([name]) => name);
  // nothing named: the hive's health in two reads, the same pair the old router fell back towards
  return (picked.length ? picked : ["failure_analysis", "pm_status"]).slice(0, 4);
}

// ── AGENT 1: Failure Analysis ─────────────────────────────────────────────────
// Reads logbook: surfaces top risk machines, repeat failures, MTBF alerts

const FAILURE_SYSTEM = `You are a maintenance failure analyst. Analyze logbook records and identify:
1. Top 3 highest-risk machines (most failures or longest downtime)
2. Repeat failure patterns (same root cause on same machine 2+ times)
3. Machines with MTBF under 14 days (failures less than 2 weeks apart)
Respond only in JSON: { "risks": [{"machine","failure_count","total_downtime_h","reason"}], "patterns": [{"machine","root_cause","occurrences"}], "mtbf_alerts": [{"machine","avg_days_between_failures"}] }`;

async function failureAnalysisAgent(db: SupabaseClient, hiveId: string | null, workerName: string | null) {
  const query = db.from("v_logbook_truth")    // canonical: logbook_truth
    .select("machine, maintenance_type, category, root_cause, downtime_hours, status, created_at")
    .eq("maintenance_type", "Breakdown / Corrective")
    .order("created_at", { ascending: false })
    .limit(200);

  if (hiveId) query.eq("hive_id", hiveId);
  else if (workerName) query.eq("worker_name", workerName);

  const { data } = await query;
  if (!data?.length) return { agent: "failure_analysis", result: null };

  // computed, not asked (§LM.11): the FAILURE_SYSTEM fields from the rows themselves
  type FRow = { machine?: string | null; root_cause?: string | null; downtime_hours?: number | null; created_at?: string | null };
  const rows = data as FRow[];
  const byMachine = new Map<string, { n: number; h: number; dates: string[] }>();
  const byPattern = new Map<string, number>();
  for (const e of rows) {
    const m = (e.machine || "").trim();
    if (!m) continue;
    const cur = byMachine.get(m) || { n: 0, h: 0, dates: [] };
    cur.n++; cur.h += Number(e.downtime_hours) || 0;
    if (e.created_at) cur.dates.push(e.created_at.slice(0, 10));
    byMachine.set(m, cur);
    const rc = (e.root_cause || "").trim();
    if (rc && !/^unknown$/i.test(rc)) byPattern.set(m + "\u0000" + rc, (byPattern.get(m + "\u0000" + rc) || 0) + 1);
  }
  const risks = [...byMachine.entries()].sort((a, b) => b[1].n - a[1].n || b[1].h - a[1].h).slice(0, 3)
    .map(([machine, v]) => ({ machine, failure_count: v.n, total_downtime_h: _round1(v.h),
      reason: `${v.n} corrective failure${v.n === 1 ? "" : "s"} and ${_round1(v.h)} h of downtime in the latest ${rows.length} corrective records` }));
  const patterns = [...byPattern.entries()].filter(([, n]) => n >= 2).sort((a, b) => b[1] - a[1]).slice(0, 5)
    .map(([k, n]) => { const [machine, root_cause] = k.split("\u0000"); return { machine, root_cause, occurrences: n }; });
  const mtbf_alerts = [...byMachine.entries()].filter(([, v]) => v.dates.length >= 2).map(([machine, v]) => {
    const ds = [...v.dates].sort();
    return { machine, avg_days_between_failures: _round1(_dayDiff(ds[0], ds[ds.length - 1]) / (ds.length - 1)) };
  }).filter((x) => x.avg_days_between_failures < 14).sort((a, b) => a.avg_days_between_failures - b.avg_days_between_failures).slice(0, 5);
  return { agent: "failure_analysis", result: { risks, patterns, mtbf_alerts } };
}

// ── AGENT 2: PM Status ────────────────────────────────────────────────────────
// Canonical: v_pm_scope_items_truth.is_overdue (frequency-aware) for hive mode;
// pm_assets for solo. Overdue is computed DETERMINISTICALLY below (WAT split) and
// handed to the model — the prompt must NOT re-derive it with a day threshold.

const PM_SYSTEM = `You are a preventive maintenance analyst. You are GIVEN each asset's PM status, where "overdue" is ALREADY computed from each task's own frequency interval (weekly=7 days, monthly=30, quarterly=90, semi-annual=180, annual=365) — NOT a flat 30-day rule. Do NOT invent your own overdue threshold and do NOT re-classify assets: report exactly the OVERDUE list you are given.
Identify:
1. Assets flagged overdue (use the OVERDUE list as given)
2. Assets with zero PM history (never had a PM done)
3. Overall PM health score (0-100, as given)
Respond only in JSON: { "overdue": [{"asset_name","days_since_last_pm","risk_level"}], "never_done": ["asset_name"], "health_score": number, "summary": "one sentence" }`;

async function pmStatusAgent(db: SupabaseClient, hiveId: string | null, workerName: string | null) {
  type PMRow = {
    pm_asset_id?: string; asset_name?: string; asset_category?: string;
    is_overdue?: boolean; is_due_soon?: boolean;
    days_until_due?: number | null; last_completed_at?: string | null;
  };
  let rows: PMRow[] = [];
  if (hiveId) {
    // Canonical frequency-aware source — the SAME is_overdue pm-scheduler + home
    // read (kpi_source_registry pm_overdue). Replaces the retired flat-30-day
    // v_pm_compliance_truth.is_due proxy AND the "no completion in over 30 days"
    // prompt rule that made the assistant answer "1 overdue" vs canonical 5
    // (STREAMLINE_ROADMAP P10).
    const { data } = await db.from("v_pm_scope_items_truth")
      .select("pm_asset_id, asset_name, asset_category, is_overdue, is_due_soon, days_until_due, last_completed_at")
      .eq("hive_id", hiveId);
    rows = (data || []) as PMRow[];
  } else if (workerName) {
    // canonical-allow: solo mode — v_pm_scope_items_truth is hive-scoped (no
    // worker_name column); base pm_assets is the only worker-scoped source. Solo
    // rows carry no per-task frequency, so overdue cannot be frequency-aware here;
    // we report PM recency only (never the flat-30 overdue rule). (PROJ-DRIFT triage)
    const { data } = await db.from("pm_assets")
      .select("id, asset_name, category, last_anchor_date")
      .eq("worker_name", workerName);
    rows = (data || []).map((a: Record<string, string>) => ({
      pm_asset_id: a.id, asset_name: a.asset_name, asset_category: a.category,
      is_overdue: false, is_due_soon: false, days_until_due: null,
      last_completed_at: a.last_anchor_date || null,
    }));
  }
  if (!rows.length) return { agent: "pm_status", result: null };

  // Roll up per asset (distinct pm_asset_id) — matches the canonical pm_overdue metric.
  type Agg = { name: string; cat: string; overdue: boolean; dueSoon: boolean; lastPm: string | null; worstDays: number; everDone: boolean };
  const byAsset = new Map<string, Agg>();
  for (const r of rows) {
    const key = String(r.pm_asset_id ?? r.asset_name ?? "?");
    const cur = byAsset.get(key) || { name: r.asset_name || key, cat: r.asset_category || "", overdue: false, dueSoon: false, lastPm: null, worstDays: 0, everDone: false };
    if (r.is_overdue) cur.overdue = true;
    if (r.is_due_soon) cur.dueSoon = true;
    if (r.last_completed_at) {
      cur.everDone = true;
      if (!cur.lastPm || r.last_completed_at > cur.lastPm) cur.lastPm = r.last_completed_at;
    }
    if (typeof r.days_until_due === "number" && r.days_until_due < cur.worstDays) cur.worstDays = r.days_until_due;
    byAsset.set(key, cur);
  }
  const assets = [...byAsset.values()];
  const overdueAssets = assets.filter(a => a.overdue);
  const neverDone = assets.filter(a => !a.everDone);
  const health = assets.length ? Math.round(100 * (assets.length - overdueAssets.length) / assets.length) : 100;

  const now = Date.now();
  const perAsset = assets.map(a => {
    const last = a.lastPm ? `${Math.floor((now - new Date(a.lastPm).getTime()) / 86400000)} days ago` : "never";
    const flag = a.overdue ? `OVERDUE by ${Math.abs(a.worstDays)}d` : a.dueSoon ? "due soon" : "ok";
    return `${a.name}|${a.cat}|${last}|${flag}`;
  }).join("\n");

  // Deterministic canonical facts (WAT: math here, AI narrates).
  const facts = `Frequency-aware PM status (already computed — do NOT apply your own day threshold):
- Overdue assets (${overdueAssets.length}): ${overdueAssets.map(a => a.name).join(", ") || "none"}
- Never had a PM (${neverDone.length}): ${neverDone.map(a => a.name).join(", ") || "none"}
- PM health score: ${health}/100`;

  void facts; void perAsset;   // the PM_SYSTEM fields below ARE these facts - nothing left for a model to add
  const overdue = overdueAssets.map((a) => ({
    asset_name: a.name,
    days_since_last_pm: a.lastPm ? Math.floor((now - new Date(a.lastPm).getTime()) / 86400000) : null,
    risk_level: Math.abs(a.worstDays) > 30 ? "HIGH" : "MEDIUM",
  }));
  return { agent: "pm_status", result: {
    overdue, never_done: neverDone.map((a) => a.name), health_score: health,
    summary: `${overdueAssets.length} of ${assets.length} asset${assets.length === 1 ? "" : "s"} overdue for PM (frequency-aware); PM health ${health}/100.`,
  } };
}

// ── AGENT 3: Inventory Risk ───────────────────────────────────────────────────
// Reads inventory_items: parts below reorder point

const INVENTORY_SYSTEM = `You are an inventory risk analyst. Given parts stock levels, identify:
1. Parts that are out of stock (qty = 0)
2. Parts below reorder threshold (qty <= reorder_point)
3. Critical risk if any of these parts are needed for upcoming PM tasks
Respond only in JSON: { "out_of_stock": ["part_name"], "low_stock": [{"part_name","qty_on_hand","reorder_point"}], "risk_summary": "one sentence" }`;

async function inventoryRiskAgent(db: SupabaseClient, hiveId: string | null, workerName: string | null) {
  // Canonical: inventory_items_truth (the view exposes reorder_point as a
  // baked-in alias for min_qty so callers don't have to remember the
  // PostgREST `:min_qty` rename trick).
  const query = db.from("v_inventory_items_truth")
    .select("part_name, qty_on_hand, reorder_point, bin_location")
    .limit(200);

  if (hiveId) query.eq("hive_id", hiveId);
  else if (workerName) query.eq("worker_name", workerName);

  const { data } = await query;
  if (!data?.length) return { agent: "inventory_risk", result: null };

  type Inv = { part_name?: string | null; qty_on_hand?: number | null; reorder_point?: number | null };
  const inv = data as Inv[];
  const out_of_stock = inv.filter((i) => Number(i.qty_on_hand) === 0).map((i) => i.part_name || "?");
  const low_stock = inv.filter((i) => i.reorder_point != null && Number(i.qty_on_hand) > 0 && Number(i.qty_on_hand) <= Number(i.reorder_point))
    .map((i) => ({ part_name: i.part_name || "?", qty_on_hand: Number(i.qty_on_hand), reorder_point: Number(i.reorder_point) }));
  return { agent: "inventory_risk", result: {
    out_of_stock, low_stock: low_stock.slice(0, 20),
    risk_summary: `${out_of_stock.length} part${out_of_stock.length === 1 ? "" : "s"} out of stock, ${low_stock.length} at or below the reorder point.`,
  } };
}

// ── AGENT 4: Knowledge Extraction ────────────────────────────────────────────
// Reads logbook.knowledge: clusters tips into SOP drafts

const KNOWLEDGE_SYSTEM = `You are a knowledge management specialist. Given maintenance knowledge notes from technicians, identify:
1. Recurring tips about the same machine or failure type (cluster them)
2. Most valuable lessons that should become SOPs
3. Machines where knowledge is missing (no lessons captured)
Respond only in JSON: { "clusters": [{"topic","tips":["tip1","tip2"],"sop_candidate":true}], "missing_knowledge": ["machine_name"], "top_insight": "most important lesson learned" }`;

async function knowledgeExtractionAgent(db: SupabaseClient, hiveId: string | null, workerName: string | null) {
  const query = db.from("v_logbook_truth")    // canonical: logbook_truth
    .select("machine, category, root_cause, knowledge")
    .not("knowledge", "is", null)
    .limit(100);

  if (hiveId) query.eq("hive_id", hiveId);
  else if (workerName) query.eq("worker_name", workerName);

  const { data } = await query;
  if (!data?.length) return { agent: "knowledge_extraction", result: null };

  // grouped by machine, the technicians' own words kept verbatim; the one synthesis call does the wording. Which machines
  // have NO lessons needs the whole asset list, which this read does not hold, so missing_knowledge stays empty rather
  // than guessed.
  const byTopic = new Map<string, { n: number; tips: string[] }>();
  for (const e of data as { machine?: string | null; category?: string | null; knowledge?: string | null }[]) {
    const tip = (e.knowledge || "").trim();
    if (!tip) continue;
    const topic = (e.machine || e.category || "general").trim();
    const cur = byTopic.get(topic) || { n: 0, tips: [] };
    cur.n++;
    if (cur.tips.length < 3) cur.tips.push(tip.slice(0, 240));
    byTopic.set(topic, cur);
  }
  const clusters = [...byTopic.entries()].sort((a, b) => b[1].n - a[1].n).slice(0, 6)
    .map(([topic, v]) => ({ topic, tips: v.tips, sop_candidate: v.n >= 2 }));
  return { agent: "knowledge_extraction", result: { clusters, missing_knowledge: [], top_insight: clusters[0]?.tips[0] || "" } };
}

// ── AGENT 5: Workforce Match ──────────────────────────────────────────────────
// Reads v_worker_skill_truth (canonical Tier A) ⨝ v_worker_assignment_truth
// (current capacity_signal): best tech for the job AND who can take it now.

const WORKFORCE_SYSTEM = `You are a workforce scheduler. Given technician skill profiles + current capacity (capacity_signal: overloaded/available/free/idle) and a maintenance question, identify:
1. Best-matched technician(s) for the task (by discipline + current_level + capacity)
2. Any skill gaps (task requires expertise no one has)
3. Recommended assignment with reasoning (prefer 'available' or 'free' workers over 'overloaded')
Respond only in JSON: { "best_match": [{"worker_name","discipline","current_level","capacity_signal","reason"}], "skill_gaps": ["missing_skill"], "recommendation": "one sentence" }`;

async function workforceMatchAgent(db: SupabaseClient, hiveId: string | null, workerName: string | null, question: string) {
  // Canonical Tier A reads — replaces direct skill_badges scatter.
  const skillsQ = db.from("v_worker_skill_truth")  // canonical: worker_skill_truth
    .select("worker_name, discipline, current_level, primary_skill, badge_count")
    .not("discipline", "is", null)
    // ★current_level ties 94.4% in live data (90 skill rows over 5 distinct levels), so at the cap
    // the tie decides which workers the assignment agent considers at all. Under the 100 cap today
    // with 90 rows, so nothing is dropped yet. (worker_name, discipline) is the grain of this view
    // and makes the order total.
    .order("current_level", { ascending: false })
    .order("worker_name", { ascending: true })
    .order("discipline", { ascending: true })
    .limit(100);
  if (hiveId) skillsQ.eq("hive_id", hiveId);

  // unbounded-query-allow: server-side roster scan (RLS-scoped); full hive worker list needed for assignment routing
  const capQ = db.from("v_worker_assignment_truth")  // canonical: worker_assignment_truth
    .select("worker_name, capacity_signal, open_jobs, last_category");
  if (hiveId) capQ.eq("hive_id", hiveId);

  const [skillsRes, capRes] = await Promise.allSettled([skillsQ, capQ]);
  const skills = (skillsRes.status === "fulfilled" ? skillsRes.value.data : null) || [];
  const caps   = (capRes.status    === "fulfilled" ? capRes.value.data    : null) || [];

  if (!skills.length) return { agent: "workforce_match", result: null };

  const capByWorker = new Map(caps.map((c: any) => [c.worker_name, c]));
  const enriched = skills.map((s: any) => {
    const c = capByWorker.get(s.worker_name) || {};
    return { ...s, capacity_signal: c.capacity_signal || "unknown", open_jobs: c.open_jobs || 0 };
  });

  // the WORKFORCE_SYSTEM rule, applied: disciplines the question names, free/available before overloaded, then level
  const q = (question || "").toLowerCase();
  const DISCIPLINES = ["mechanical", "electrical", "instrumentation", "hvac", "civil", "plumbing", "automation", "welding", "lubrication", "safety"];
  const asked = DISCIPLINES.filter((d) => q.includes(d));
  const capRank: Record<string, number> = { free: 0, idle: 0, available: 1, unknown: 2, overloaded: 3 };
  const pool = enriched.filter((b: any) => !asked.length || asked.some((d) => String(b.discipline || "").toLowerCase().includes(d)));
  // one row per (worker, discipline) in the skills view, so the top three were once the same free person three times;
  // the best PEOPLE are listed, each once, with their strongest matching discipline
  const _seenWorker = new Set<string>();
  const best_match = [...pool]
    .sort((a: any, b: any) => (capRank[a.capacity_signal] ?? 2) - (capRank[b.capacity_signal] ?? 2) || (Number(b.current_level) || 0) - (Number(a.current_level) || 0))
    .filter((b: any) => { const k = String(b.worker_name || ""); if (!k || _seenWorker.has(k)) return false; _seenWorker.add(k); return true; })
    .slice(0, 3)
    .map((b: any) => ({ worker_name: b.worker_name, discipline: b.discipline, current_level: b.current_level, capacity_signal: b.capacity_signal,
      reason: `level ${b.current_level} ${b.discipline}, ${b.capacity_signal}${b.open_jobs ? `, ${b.open_jobs} open job${b.open_jobs === 1 ? "" : "s"}` : ""}` }));
  const skill_gaps = asked.filter((d) => !enriched.some((b: any) => String(b.discipline || "").toLowerCase().includes(d)));
  return { agent: "workforce_match", result: {
    best_match, skill_gaps,
    // no NAME in this sentence: redaction replaces names by their KEY (worker_name -> <worker_1>), so a name written
    // into free text would reach the provider; the synthesis names the person from best_match[0].worker_name
    recommendation: best_match[0]
      ? `Assign the first best match (${best_match[0].discipline}, level ${best_match[0].current_level}, ${best_match[0].capacity_signal}).`
      : "No technician on the roster matches the discipline asked about.",
  } };
}

// ── AGENT 6: Shift Handover ───────────────────────────────────────────────────
// Reads logbook last 24h: open jobs + completed work summary

const HANDOVER_SYSTEM = `You are a shift handover report generator. Given recent maintenance records, produce:
1. Open jobs that the next shift must follow up on
2. Work completed this shift
3. Critical alerts the next shift must know immediately
Respond only in JSON: { "open_jobs": [{"machine","problem","priority":"HIGH|MEDIUM|LOW"}], "completed": [{"machine","action"}], "critical_alerts": ["alert text"], "handover_note": "one paragraph summary" }`;

async function shiftHandoverAgent(db: SupabaseClient, hiveId: string | null, workerName: string | null) {
  const since = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();

  const query = db.from("v_logbook_truth")    // canonical: logbook_truth
    .select("machine, category, problem, action, status, created_at, worker_name")
    .gte("created_at", since)
    .order("created_at", { ascending: false })
    .limit(50);

  if (hiveId) query.eq("hive_id", hiveId);
  else if (workerName) query.eq("worker_name", workerName);

  const { data } = await query;
  if (!data?.length) return { agent: "shift_handover", result: null };

  // PII-redact worker_name before the summary leaves the platform.
  // Closes PRODUCTION_FIXES #44 for this fn. The model still sees the
  // structural shape ("by <redacted>") so attribution-style prompts
  // function; the real names hydrate at the UI layer if needed.
  type HRow = { machine?: string | null; category?: string | null; problem?: string | null; action?: string | null; status?: string | null };
  const recs = data as HRow[];
  const URGENT = /leak|fire|smoke|trip|injur|shock|overheat|burn|explos|safety/i;
  const open_jobs = recs.filter((e) => !/^closed$/i.test(String(e.status || ""))).slice(0, 15).map((e) => ({
    machine: e.machine || "?", problem: (e.problem || "").slice(0, 160),
    priority: URGENT.test(`${e.problem || ""} ${e.category || ""}`) ? "HIGH" : /breakdown|corrective/i.test(String(e.category || "")) ? "MEDIUM" : "LOW",
  }));
  const completed = recs.filter((e) => /^closed$/i.test(String(e.status || ""))).slice(0, 15)
    .map((e) => ({ machine: e.machine || "?", action: (e.action || "").slice(0, 160) }));
  const critical_alerts = open_jobs.filter((j) => j.priority === "HIGH").map((j) => `${j.machine}: ${j.problem}`);
  return { agent: "shift_handover", result: {
    open_jobs, completed, critical_alerts,
    handover_note: `In the last 24 h: ${open_jobs.length} open job${open_jobs.length === 1 ? "" : "s"}, ${completed.length} completed, ${critical_alerts.length} to look at first.`,
  } };
}

// ── AGENT 7: Predictive ───────────────────────────────────────────────────────
// Reads logbook failure dates: projects next failure per machine

const PREDICTIVE_SYSTEM = `You are a predictive maintenance analyst. Given machine failure history with dates, calculate:
1. Average days between failures (MTBF) per machine
2. Predicted next failure date based on MTBF
3. Risk level: HIGH (overdue), MEDIUM (due within 7 days), LOW (more than 7 days away)
Respond only in JSON: { "predictions": [{"machine","mtbf_days":number,"last_failure":"YYYY-MM-DD","predicted_next":"YYYY-MM-DD","risk":"HIGH|MEDIUM|LOW"}] }`;

async function predictiveAgent(db: SupabaseClient, hiveId: string | null, workerName: string | null) {
  const query = db.from("v_logbook_truth")    // canonical: logbook_truth
    .select("machine, created_at")
    .eq("maintenance_type", "Breakdown / Corrective")
    .order("machine", { ascending: true })
    .order("created_at", { ascending: true })
    .limit(200);

  if (hiveId) query.eq("hive_id", hiveId);
  else if (workerName) query.eq("worker_name", workerName);

  const { data } = await query;
  if (!data?.length) return { agent: "predictive", result: null };

  const today = new Date().toISOString().slice(0, 10);
  const byM = new Map<string, string[]>();
  for (const e of data as { machine?: string | null; created_at?: string | null }[]) {
    const m = (e.machine || "").trim();
    if (!m || !e.created_at) continue;
    const arr = byM.get(m) || [];
    arr.push(e.created_at.slice(0, 10));
    byM.set(m, arr);
  }
  const RANK: Record<string, number> = { HIGH: 0, MEDIUM: 1, LOW: 2 };
  const predictions = [...byM.entries()].filter(([, ds]) => ds.length >= 2).map(([machine, ds]) => {
    const sorted = [...ds].sort();
    const mtbf = _dayDiff(sorted[0], sorted[sorted.length - 1]) / (sorted.length - 1);
    const last = sorted[sorted.length - 1];
    const next = new Date(new Date(last).getTime() + mtbf * 86400000).toISOString().slice(0, 10);
    const until = _dayDiff(today, next);
    return { machine, mtbf_days: _round1(mtbf), last_failure: last, predicted_next: next, risk: until < 0 ? "HIGH" : until <= 7 ? "MEDIUM" : "LOW" };
  // 25, not 10: a question names ONE machine ("when will the boiler fail next?"), and the synthesis can only answer about
  // a machine it was handed - one short row per machine is cheaper than an answer that cannot find the asset asked about
  }).sort((a, b) => RANK[a.risk] - RANK[b.risk] || a.predicted_next.localeCompare(b.predicted_next)).slice(0, 25);
  return { agent: "predictive", result: { predictions } };
}

// ── ORCHESTRATOR: decides which agents to run, synthesizes answer ─────────────

const ROUTE_SYSTEM = `You are a maintenance intelligence router. Given a user question, decide which agents to run.
Respond only in JSON: { "agents": ["failure_analysis","pm_status","inventory_risk","knowledge_extraction","workforce_match","shift_handover","predictive"] }
Include only the agents relevant to the question. Use at least 1 and at most 4 agents.`;

// ★THE VERBATIM RULE EXISTED, BUT ONLY IN COACH MODE. COACH_SYNTH_SYSTEM below carries a hard
// 'every machine value MUST appear VERBATIM in the agent data, NEVER invent or generalize' clause.
// SYNTH_SYSTEM - the prompt behind ordinary assistant answers - carried only 'be specific: name
// actual machines'. Measured live: asked for the worst MTBF, it answered 'The asset with the worst
// MTBF is AC-003' from a grounding set that contained no MTBF figures and never mentioned AC-003.
// AC-003 is not the worst on ANY basis the platform computes - v_risk_truth (full history) ranks
// CH-001 at 5.80d worst with AC-003 4th at 7.30d, and get_mtbf_by_machine (90-day window) ranks
// CT-001 first; AC-003 is 10th. What AC-003 IS worst at is health_score (25.4) - so the model
// silently substituted one platform metric for another and stated the swap as a fact.
//
// Two clauses added, both narrow. The VERBATIM clause is COACH's, ported. The ORDERING clause is
// new and is the one this failure needed: naming a real asset is not enough when the CLAIM is a
// ranking - a superlative asserts an ordering, and an ordering can only come from figures the
// model was actually handed. The definitions are listed because these terms have platform meanings
// that differ from the model's priors, and a term used on its own terms is a wrong answer wearing
// the right word. Kept short deliberately: this prompt is paid for on every single call.
// the header ai-gateway puts on a hive-less person's own records (buildSoloSnapshot, LM166/LM170)
const SOLO_RECORDS_HEAD = "=== YOUR OWN RECORDS";

const SYNTH_SYSTEM = `You are a senior maintenance manager AI. Given agent results, write a clear, practical answer to the user's question.
Be specific: name actual machines, workers, parts. Use bullet points for lists. Keep it under 200 words.
Rules: every asset code you name MUST appear VERBATIM in the agent data above - copy it exactly, and NEVER invent, guess or generalize one.
A superlative (worst/best/highest/lowest/most/least/top) is a claim about an ORDERING. Only make one if the agent data actually contains the figures being ordered, and say which figure you ranked on. If it does not, say what you can see and point the user to the Analytics page rather than ranking from impressions.
Use these terms only as this platform defines them: MTBF = mean calendar days between corrective failures (ISO 14224). MTTR = mean repair hours, not calendar time. OEE = Availability x Performance x Quality (ISO 22400). PM compliance = PMs completed / PMs scheduled in the window (SMRP). Health score and risk score are SEPARATE rankings - never report one as the other.
Respond only in JSON: { "answer": "your response here" }`;

// ── COACH MODE synthesis (Phase 1.3 — Reliability Coach) ─────────────────────
// Always runs 4 core agents and returns a prioritized action plan, not a Q&A answer.

const COACH_AGENTS = ["failure_analysis", "pm_status", "inventory_risk", "predictive"] as const;

const COACH_SYNTH_SYSTEM = `You are a reliability engineer giving a plant supervisor their weekly action plan.
Based on the agent data, give UP TO 3 specific, prioritized actions to take this week.
Rules: every "machine" value MUST be an asset ID/name that appears VERBATIM in the agent data above — copy it exactly. NEVER invent, guess, or generalize an asset ID — output a tag ONLY if it appears VERBATIM in the data above. If the data names fewer than 3 assets, return FEWER actions (or an action with machine:"" for a general practice) rather than inventing one to fill the slot — a fabricated machine ID is worse than a short list. Be concrete — name the EXACT asset code copied from the data (e.g. "schedule bearing inspection on <that asset's real code>"), never a vague "check pumps" and never a placeholder or a code from these instructions. This rule holds in every language, including Tagalog.
Urgency levels: TODAY (safety/critical failure risk), THIS WEEK (high risk if ignored), MONITOR (watch closely).
Respond only in JSON: { "actions": [{ "priority": 1, "action": "...", "machine": "...", "why": "...", "urgency": "TODAY|THIS WEEK|MONITOR" }] }`;

// ── CAPABILITY BOUNDS (Family R — capability honesty) ─────────────────────────
// The assistant/orchestrator is an ANALYSIS + advice brain, NOT an action service. Deep-walk
// 2026-07-07 found it answered "order 5 parts and pay for them" with the generic no-agents
// fallback ("couldn't find enough data") — a misleading DATA excuse for a CAPABILITY boundary.
// The companion (voice-journal-agent) already handles this via its CAPABILITY BOUNDS prompt clause;
// port the intent here as a deterministic pre-check (WAT: code detects the boundary, not the LLM,
// so an 8B model can't be coaxed into "I ordered it"). Conservative: needs an explicit external-
// action verb + object, so legit maintenance actions ("schedule a PM", "order of work") don't match.
const CAPABILITY_RE = /\b(order|buy|purchase)\b[^.?!]*\b(part|parts|set|sets|unit|units|supplier|vendor|for me)\b|\bpay\b[^.?!]*\b(for|them|it|the invoice|online|now)\b|\bsend\b[^.?!]*\b(e-?mail|text|sms|message)\b|\b(call|phone)\b[^.?!]*\b(supplier|vendor|him|her|them|technician)\b|\bbook\b[^.?!]*\b(visit|appointment|technician|service)\b|\bschedule\b[^.?!]*\bvisit\b|\bgrant\b[^.?!]*\b(access|permission)\b|\bprocess\b[^.?!]*\bpayment\b/i;
const CAPABILITY_DISCLAIMER = "I can't place orders, buy parts, send emails or texts, make calls, book visits, process payments, or grant access from here — and I won't pretend I did. What I CAN do: draft the message or purchase request for you to send, tell you exactly what to say to the vendor, or point you to the right page or person (the Inventory page, your supplier, or your supervisor). Want me to draft it?";

// CL5 (2026-07-08): a question that REFERENCES the prior conversation ("what did I just tell you",
// "remind me what I set", "repeat that") should be answered from the working buffer, not deflected with
// "not enough data" when the DB agents return nothing. This gates the memory-fallthrough below so it fires
// ONLY for recall-shaped questions — gibberish and genuine new-data questions with no data still deflect
// honestly (not answered from stale, unrelated memory). Conservative: needs an explicit reference marker.
const RECALL_RE = /\bremind me\b|\brepeat (that|it|what)\b|\b(what|which|how much|how many)\b[^.?!]*\bi (just )?(said|told|gave|set|mentioned|asked|noted|typed|wrote)\b|\byou (just )?(said|told|gave|mentioned|noted)\b|\bwhat did i\b|\bwhat was the\b[^.?!]*\bi\b|\bi (just )?(told|gave|mentioned|set|noted) you\b|\bearlier\b/i;

// CL10 faithfulness rail (2026-07-08). Live-caught: asked for an "exact planned-vs-reactive ratio", the
// free-tier model INVENTED "41% planned, 59% reactive" and dressed it as "from recent records / I've
// pulled the numbers here" — the hive has NO computed such ratio (real split ~58/41, and it inverted it).
// This does NOT strip the number (that risks garbling a LEGIT figure) — it neutralizes the false
// "from records" PROVENANCE claim ONLY when the answer asserts a percentage that does NOT appear in the
// grounding set (agent results + semantic context + conversation memory). Conservative by construction:
// a grounded % keeps its provenance; an ungrounded % with no provenance phrase is left as a plain estimate.
const PROVENANCE_RE = /\b(from (?:recent )?records|i(?:'ve| have) pulled (?:up )?the numbers(?: here)?|based on (?:your |the )?records|from your (?:logbook|records|data|numbers))\b/gi;
// A possessive CURRENT-STATE metric claim: "your … 41%", "41% of your …", "your ratio/split/rate is 41%".
// This is the frame that separates a fabricated YOUR-DATA metric from a legit BENCHMARK ("world-class is
// 85%") or domain ADVICE ("torque to 300 Nm"). Kept %-only so bare unit-constant advice (Nm/mm/hours)
// survives untouched — an advisory assistant must keep those.
const POSSESSIVE_CURRENT_STATE_RE = /\byour\b[^.?!]*\d{1,3}(?:\.\d+)?\s?%|\d{1,3}(?:\.\d+)?\s?%[^.?!]*\bof your\b|\byour\b[^.?!]*\b(?:ratio|split|rate|percentage|breakdown|uptime|downtime)\b[^.?!]*\d/i;
const BENCHMARK_FRAME_RE = /\b(?:world[- ]class|benchmark|industry|typical(?:ly)?|generally|usually|standard|rule of thumb|on average|best[- ]in[- ]class)\b/i;
// CL10 numeric rail (2026-07-08, hardened). Fixes two confirmed gaps in the old phrase-only rail:
//  (a) coincidental-substring FALSE-NEGATIVE — token-accurate grounding via extractNumberCores so a stray
//      "41" in an agent field no longer makes a fabricated "41%" look grounded (a "78" can't trace to "1780");
//  (b) NO-provenance form — "Your split is 41% planned." (no "from records" phrase → the old rail was a
//      no-op) now gets an honest hedge when the % is ungrounded, possessive-current-state framed, and NOT a
//      benchmark. Conservative: a grounded % is left as-is; benchmarks + unit-constant advice are untouched.
// CL10b SUPERLATIVE rail (2026-08-19, live-caught). CL10 guards NUMERIC current-state claims and opens
// with `if (!pcts.length) return answer` — so an answer carrying no digit at all is never examined. A
// SUPERLATIVE carries the same authority as a number and is just as falsifiable, with nothing for a
// %-only rail to catch. Measured live: asked "which of my assets has the worst MTBF", the model was
// handed an 835-character grounding set containing free-text fault history, asset codes GEN-001 and
// SUB-001, and ZERO MTBF figures. It answered "The asset with the worst MTBF is AC-003" — an asset that
// appears NOWHERE in its grounding — as a bare fact. Against v_risk_truth the worst MTBF is CH-001 at
// 5.80 days; AC-003 is 7.30, joint 4th of 30. The code was real (so nothing was invented) but the
// RANKING was produced from nothing, and CL10 never ran because the sentence had no percentage.
//
// Conservative by construction, mirroring CL10: it fires ONLY when the answer names an asset code in a
// superlative frame AND that code is absent from the grounding set. A superlative about an asset the
// model was actually shown is left untouched (it may be legitimately derived), and no sentence is ever
// deleted — the caveat is appended, so a possibly-correct answer survives with its confidence corrected
// rather than its content destroyed.
const SUPERLATIVE_ASSET_RE =
  /\b(worst|best|highest|lowest|most|least|top|poorest)\b[^.?!]{0,60}?\b([A-Z]{2,6}-\d{2,4})\b|\b([A-Z]{2,6}-\d{2,4})\b[^.?!]{0,60}?\b(?:has|is)\s+(?:the\s+)?(worst|best|highest|lowest|most|least|poorest)\b/;

function hedgeUngroundedSuperlative(answer: string, grounding: string): string {
  if (!answer) return answer;
  const m = SUPERLATIVE_ASSET_RE.exec(answer);
  if (!m) return answer;
  const code = m[2] || m[3];
  if (!code) return answer;
  if ((grounding || "").includes(code)) return answer;   // the model was actually shown this asset
  return `${answer.trim()} (Note: I ranked that from what I could retrieve, and ${code} wasn't in the records I pulled — check the Asset Hub or Analytics page for the measured figures before acting on the ordering.)`;
}

function stripFalseKpiProvenance(answer: string, grounding: string): string {
  if (!answer) return answer;
  const pcts = answer.match(/\b\d{1,3}(?:\.\d+)?\s?%/g) || [];
  if (!pcts.length) return answer;
  const groundedCores = new Set(extractNumberCores(grounding || ""));
  const anyUngrounded = pcts.some(p => {
    const core = p.replace(/[^\d.]/g, "").replace(/\.$/, "");
    return core && !groundedCores.has(core);
  });
  if (!anyUngrounded) return answer;                                   // every % traces → leave as-is
  // (1) neutralize a false provenance phrase ("from records") on the ungrounded %.
  const neutralized = answer.replace(PROVENANCE_RE, "(though I don't have that exact figure computed)");
  if (neutralized !== answer) return neutralized;
  // (2) no-provenance form: an ungrounded % asserted as the worker's CURRENT-STATE metric, no phrase to
  // neutralize and no benchmark framing → still a confidently-wrong number. Hedge honestly (don't strip a
  // possibly-legit sentence — append the caveat once).
  if (POSSESSIVE_CURRENT_STATE_RE.test(answer) && !BENCHMARK_FRAME_RE.test(answer)) {
    return `${answer.trim()} (Note: I don't have that exact figure computed from your records — treat it as a rough estimate, not a measured value.)`;
  }
  return answer;
}

async function orchestrate(question: string, hiveId: string | null, workerName: string | null, db: SupabaseClient, mode = "chat", memoryBlock = "", searchHeaders: Record<string, string> | null = null) {

  // Family R: an out-of-scope ACTION request gets an honest capability disclaimer + the real
  // alternative — never a "not enough data" deflection and never a faked action. (chat mode only;
  // coach mode is a fixed weekly-plan render that never carries an action ask.)
  if (mode !== "coach" && CAPABILITY_RE.test(question || "")) {
    return { answer: CAPABILITY_DISCLAIMER, agents_used: [] };
  }

  // Coach mode: always run 4 core agents, skip router
  let agentsToRun: string[];
  if (mode === "coach") {
    agentsToRun = [...COACH_AGENTS];
  } else {
    // Step 1: Route - from the question's own words (§LM.11: the routing call is gone; ROUTE_SYSTEM's 1-4 rule kept)
    agentsToRun = routeQuestion(question);
    void ROUTE_SYSTEM;
  }

  // Step 2: Run selected agents in parallel
  const agentMap: Record<string, () => Promise<Record<string, unknown>>> = {
    failure_analysis:    () => failureAnalysisAgent(db, hiveId, workerName),
    pm_status:           () => pmStatusAgent(db, hiveId, workerName),
    inventory_risk:      () => inventoryRiskAgent(db, hiveId, workerName),
    knowledge_extraction:() => knowledgeExtractionAgent(db, hiveId, workerName),
    workforce_match:     () => workforceMatchAgent(db, hiveId, workerName, question),
    shift_handover:      () => shiftHandoverAgent(db, hiveId, workerName),
    predictive:          () => predictiveAgent(db, hiveId, workerName),
  };

  const results = await Promise.allSettled(
    agentsToRun.map(name => agentMap[name]?.() ?? Promise.resolve({ agent: name, result: null }))
  );

  const successfulResults = results
    .filter(r => r.status === "fulfilled" && r.value?.result)
    .map(r => (r as PromiseFulfilledResult<Record<string, unknown>>).value);

  // ★A ONE-PERSON OPERATOR'S OWN RECORDS ARE THE AGENT DATA (LM-G walk, LM170, 2026-10-07). Jun Salvador owns his van
  // and has no hive. Every specialist above reads by hive_id, so all of them returned nothing and the branch below
  // deflected ("none of my sources returned anything") - for his own brake-pad work, which his logbook holds, and for
  // ZQX 9471, a code that is not his. The gateway had already forwarded his own newest records, read on his VERIFIED
  // id ("=== YOUR OWN RECORDS"), but only as conversation memory. For a hive-less person that block is the record
  // the answer must rest on, so it is handed to synthesis as agent data, where the verbatim-code rule applies to it.
  if (!hiveId && memoryBlock && memoryBlock.includes(SOLO_RECORDS_HEAD)) {
    const at = memoryBlock.indexOf(SOLO_RECORDS_HEAD);
    const end = memoryBlock.indexOf("\n\n", at);
    const solo = memoryBlock.slice(at, end === -1 ? undefined : end).trim();
    if (solo) successfulResults.push({ agent: "your_own_records", result: solo });
  }

  if (!successfulResults.length) {
    // CL5 fix (2026-07-08): a "what did I just tell you?" / reference-recall question makes the router
    // pick a specialist that returns no HIVE data — but the answer lives in the CONVERSATION memory the
    // gateway forwarded, not in a DB agent. Deflecting "not enough data" here (before synthesis) is why
    // the Work Assistant had NO multi-turn recall while the voice-journal companion did. So only deflect
    // when there is genuinely nothing to draw on (no agent data AND no conversation memory); otherwise
    // FALL THROUGH to the memory-grounded synthesis below (resultsText is empty, memoryPrefix carries the
    // prior turns) so the assistant answers conversationally from the working buffer.
    const hasMemory = !!(memoryBlock && memoryBlock.trim());
    // ★AND WHEN THE GATEWAY ALREADY SENT THE ANSWER'S RECORDS, USE THEM (LM-G walk, LM113, 2026-10-07). The same
    // question about M-001 got a grounded answer on one walk ("Vibration trending check (20 days ago) ...", from the
    // gateway's asset-history block) and this deflection on the next: the specialist router is a model call, and when
    // it picked specialists that returned nothing, this branch deflected although the forwarded memory carried that
    // asset's own logbook history. A history block for an asset the question names is grounding, not chatter.
    // read the machines the gateway actually sent history for, and ask whether the question names one - NOT the code
    // detector, whose two-letter floor (so "M12" bolts are not assets) misses one-letter tags like M-001 (LM130)
    const historyTags = hasMemory
      ? [...memoryBlock.matchAll(/Logbook history for (.+?) \(from v_logbook_truth/g)].map((m) => m[1])
      : [];
    const memoryHasAskedAssetHistory = historyTags.some((t) => normCode(question).includes(normCode(t)));
    if (!(hasMemory && (RECALL_RE.test(question || "") || memoryHasAskedAssetHistory))) {
      // ★THE DEFLECTION MUST NOT DIAGNOSE A CAUSE IT NEVER CHECKED (live-caught 2026-08-19). This is
      // the THIRD time this one fallback has misattributed its own boundary: Family R found it
      // blaming DATA for a CAPABILITY limit ("order 5 parts"), CL5 found it blaming DATA for a
      // MEMORY lookup ("what did I just tell you"), and both fixes narrowed WHEN it fires without
      // ever touching WHAT IT SAYS. Measured: a supervisor on a hive holding 3,812 logbook rows, 9
      // open work orders and 79% PM compliance asked for exactly those figures, no agent returned a
      // result, and the reply told them to "add more logbook entries, PM completions, or skill
      // badges to build up your knowledge base." Every clause of that is false about their hive. The
      // honest statement is about OUR retrieval, not THEIR records — we know no source answered, and
      // we have not checked whether the hive is empty, so we must not assert that it is. The
      // onboarding advice survives only as a CONDITIONAL, which is true for a new hive and harmless
      // for a full one, and the reply now routes the person to the surfaces that do hold the answer
      // instead of leaving them to add data that was never missing.
      // ★A CODE THAT IS NOT AN ASSET OF THIS HIVE IS ANSWERED AS SUCH (LM-G walk, LM113, 2026-10-07). Asked "What
      // maintenance has been done on ZQX 9471 recently?" - a code registered nowhere - the assistant answered with the
      // retrieval excuse below ("I couldn't pull that from your hive just now"), which invites a retry for a machine
      // that does not exist. Whether the code is one of this hive's assets is a single query, so it is answered here,
      // in code, before the excuse. Only when EVERY named code is unregistered: a question that names a real asset
      // keeps the honest retrieval wording.
      const askedCodes = hiveId ? mentionedAssetCodes(question) : [];
      if (askedCodes.length) {
        // canonical-allow: every status counts as registered - v_asset_truth keeps only approved assets, and an asset added
        // and still awaiting approval must never be answered as "no asset ... registered in this hive" (2026-10-13)
        const { data: regs, error: regErr } = await db.from("asset_nodes").select("tag")
          .eq("hive_id", hiveId).not("tag", "is", null);
        if (!regErr) {
          const reg = new Set(((regs ?? []) as Array<{ tag: string }>).map((r) => normCode(r.tag)));
          const unknown = askedCodes.filter((c) => !reg.has(normCode(c)));
          if (unknown.length === askedCodes.length) {
            return {
              answer: `There is no asset ${unknown.join(", ")} registered in this hive, so there is no maintenance `
                + "record for it. The Asset Hub list shows every tag this hive has.",
              agents_used: agentsToRun,
            };
          }
        }
      }
      return {
        answer: "I couldn't pull that from your hive just now — none of my sources returned "
          + "anything for that question, which usually means it sits outside what I can reach rather "
          + "than that your records are missing. Open work orders are on the Hive board, and PM "
          + "compliance is on the Analytics page. If your hive is new, adding logbook entries, PM "
          + "completions and skill badges will widen what I can answer.",
        agents_used: agentsToRun,
      };
    }
    // else: a recall/reference question WITH conversation memory → fall through to memory-grounded synthesis.
  }

  // Step 3: Fetch semantic context from knowledge base (RAG)
  let semanticContext = "";
  try {
    const searchRes = await fetch(
      `${Deno.env.get("SUPABASE_URL")}/functions/v1/semantic-search`,
      { signal: AbortSignal.timeout(60000),
        method: "POST",
        // ★A SOLO OWNER'S SEARCH THROUGH HERE WAS ALWAYS EMPTY (2026-10-08). This sent the SERVICE-ROLE key for every
        // caller. With a hive that is fine - membership was proven above and semantic-search searches the hive. With
        // no hive, semantic-search's own scope is the VERIFIED caller (resolveIdentity on the bearer), and a
        // service-role bearer is nobody, so a person with no hive never got their own past repairs into an answer.
        // A solo turn now forwards the person's own Authorization (searchHeaders, built by the handler after it
        // verified the token), plus ai-gateway's forward proof when there is one, so semantic-search does not count
        // the person's solo bucket a second time. The owner is never named in the body.
        headers: {
          "Content-Type": "application/json",
          ...(searchHeaders ?? { "Authorization": `Bearer ${Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")}` }),
        },
        body: JSON.stringify({ query: question, hive_id: hiveId, match_count: 3 }),
      }
    );
    if (searchRes.ok) {
      const searchData = await searchRes.json();
      semanticContext = searchData.context || "";
    }
  } catch { /* non-blocking: synthesis continues even if search fails */ }

  // Step 4: Synthesize - the ONE model call (§LM.11). The agent data reaches the provider with every person's name,
  // e-mail and phone replaced by a placeholder (<worker_1> ...) and the answer is re-filled before anyone reads it: "assign
  // <worker_1>" reaches the screen as the person's real name while the provider never sees one. (The specialists used to
  // send the roster's names to a model of their own; the one call left now sends none.) The grounding checks below read
  // the ORIGINAL data, against the re-filled answer.
  const _pii = redactPIIWithMap(successfulResults.map((r) => ({ agent: r.agent, result: r.result })));
  const _hydration: Record<string, string> = { ..._pii.hydration };
  const _fill = (t: string) => Object.entries(_hydration).reduce((acc, [ph, orig]) => acc.split(ph).join(orig), t);
  const _keyRedacted = (_pii.redacted as { agent: unknown; result: unknown }[]).map(r =>
    `[${r.agent}]: ${JSON.stringify(r.result)}`
  ).join("\n\n");
  // ...and names written in PROSE - a technician's lesson, a handover's problem text ("asked Bryan Garcia to check") -
  // which no key marks: the hive's own roster names are replaced too (redactKnownNames, the gateway's CL11 move for
  // conversation memory). A roster read that fails leaves prose as written; keyed names stay redacted either way.
  let _roster: string[] = [];
  if (hiveId) {
    try {
      const { data: _mem } = await db.from("v_worker_truth").select("worker_name").eq("hive_id", hiveId).limit(500);
      _roster = [...new Set((_mem || []).map((m: { worker_name?: string | null }) => String(m.worker_name || "").trim())
        .filter((n) => n.includes(" ")))];
    } catch { /* see above */ }
  }
  const _named = redactKnownNames(_keyRedacted, _roster);
  Object.assign(_hydration, _named.hydration);
  const resultsText = _named.redacted;
  const _resultsTextOriginal = successfulResults.map(r =>
    `[${r.agent}]: ${JSON.stringify(r.result)}`
  ).join("\n\n");

  // Conversation memory (working/recent-turns + summary) forwarded by ai-gateway
  // as `memory`. Inject it so the synthesis honors prior turns — without this the
  // assistant brain persists every turn (gateway saveTurn) but never RECALLS them
  // (capstone Memory-pillar finding 2026-06-07: "no reference code to recall").
  const memoryPrefix = memoryBlock && memoryBlock.trim()
    ? `Conversation memory (earlier turns with this worker — use it to stay consistent and resolve references like "that machine" / "the code I gave you"):\n${memoryBlock}\n\n`
    : "";
  const synthPrompt = semanticContext
    ? `${memoryPrefix}User question: "${question}"\n\nRelevant history from knowledge base:\n${semanticContext}\n\nAgent results:\n${resultsText}`
    : `${memoryPrefix}User question: "${question}"\n\nAgent results:\n${resultsText}`;

  // Coach mode: use dedicated synthesis prompt, return action plan
  if (mode === "coach") {
    const coachRaw = await callGroq(synthPrompt, COACH_SYNTH_SYSTEM);
    // ★AN UNANSWERED COACH SAID THE HIVE HAD "NOT ENOUGH DATA" (2026-10-12, UFAI edge walk W4227). With every model
    // exhausted callAI returns "{}", JSON.parse("{}").actions is undefined, and `|| []` made it an EMPTY plan - which
    // hive.html words as "Not enough data yet to generate recommendations. Keep logging maintenance entries.": an AI
    // outage blamed on the supervisor's records. No answer, or no list in it, is now `actions: null`, which the page
    // already words honestly ("The coach didn't send back any actions this time"). A model that answers with an empty
    // list still means "nothing to recommend".
    if (!aiAnswered(coachRaw)) return { mode: "coach", actions: null, agents_used: agentsToRun };
    let actions: Record<string, unknown>[] = [];
    try {
      const parsedCoach = JSON.parse(coachRaw);
      if (!Array.isArray(parsedCoach?.actions)) return { mode: "coach", actions: null, agents_used: agentsToRun };
      actions = parsedCoach.actions;
    } catch { return { mode: "coach", actions: null, agents_used: agentsToRun }; }
    // re-fill the placeholders the provider saw (see Step 4) before the plan reaches the supervisor
    try { actions = JSON.parse(_fill(JSON.stringify(actions))); } catch { /* keep as parsed */ }
    // WAT deterministic guard (FB4 grounding eval, 2026-07-01): the free-tier model keeps a
    // strong prior to invent a plausible asset ID (e.g. "PSV-001") to fill an action slot even
    // when the prompt forbids it. The probabilistic model PROPOSES; deterministic code VERIFIES
    // — strip any `machine` that is an asset-tag shape NOT present in this hive's real assets, so
    // no fabricated equipment ID ever reaches the supervisor's action plan. A blank machine is
    // safer than a hallucinated one. Verified live: drives the coach fabrication count toward 0.
    if (hiveId && actions.length) {
      try {
        const { data: assetRows } = await db.from("v_asset_truth").select("tag").eq("hive_id", hiveId);
        const realTags = new Set((assetRows || []).map((r: { tag?: string }) => String(r.tag || "").toUpperCase()).filter(Boolean));
        if (realTags.size) {
          const tagShape = /\b[A-Z]{2,4}-\d{2,4}\b/g;
          for (const a of actions) {
            const m = String(a.machine || "").trim();
            const tags = (m.toUpperCase().match(tagShape) || []);
            if (tags.length && tags.some((t) => !realTags.has(t))) {
              a.machine = "";
              a._machine_dropped = "fabricated asset ID removed (not in this hive's assets)";
            }
          }
        }
      } catch { /* best-effort guard — never block the action plan on the lookup */ }
    }
    return { mode: "coach", actions, agents_used: agentsToRun };
  }

  const synthRaw = await callGroq(synthPrompt, SYNTH_SYSTEM);

  // An UNANSWERED chain ("{}") is no answer, not "I analyzed your data but had trouble formatting" - nothing was
  // analysed (2026-10-12, W4227). An empty answer reaches assistant.html's own honest no-answer path, and the gateway
  // does not remember it; a model that DID answer in a broken shape still gets the formatting sentence.
  let answer: string = aiAnswered(synthRaw) ? "I analyzed your data but had trouble formatting the response. Please try again." : "";
  try {
    const parsed = JSON.parse(synthRaw).answer;
    if (typeof parsed === "string") {
      answer = parsed;
    } else if (parsed && typeof parsed === "object") {
      // LLM returned a structured object instead of a prose string. Format it
      // as readable markdown-ish bullets so the chat UI can render it.
      answer = formatStructuredAnswer(parsed);
    }
  } catch { /* use fallback */ }
  answer = _fill(answer);   // the names the provider never saw, back in place (Step 4)

  // CL10 faithfulness rails (2026-07-08): (1) neutralize/hedge an ungrounded KPI %, then (2) strip any
  // fabricated COMPLETED-write claim ("Log entry added", "Updated maintenance record"). The assistant is
  // read-only advisory; a false "I did X" is trust-breaking in a maintenance context. Live-caught 2026-07-08.
  const _grounding = `${_resultsTextOriginal}\n${semanticContext}\n${memoryBlock || ""}`;
  answer = stripFalseKpiProvenance(answer, _grounding);
  // CL10b: the same grounding set, asked the non-numeric question CL10 cannot reach.
  answer = hedgeUngroundedSuperlative(answer, _grounding);
  const actionGate = stripFalseActionClaims(answer);
  if (actionGate.hit) {
    answer = (actionGate.clean && actionGate.clean.length >= 15)
      ? `${actionGate.clean}\n\n${ACTION_HONEST_CLARIFIER}`
      : `I can't write to your records from here. ${ACTION_HONEST_CLARIFIER}`;
  }

  return { answer, agents_used: agentsToRun, raw_results: successfulResults };
}

// Coerce a structured object response into readable text. Keys become bold
// headings; arrays become bullet lists; primitives become "key: value".
function formatStructuredAnswer(obj: Record<string, unknown>, depth = 0): string {
  const lines: string[] = [];
  const indent = "  ".repeat(depth);
  for (const [key, value] of Object.entries(obj)) {
    const heading = key.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
    if (Array.isArray(value)) {
      if (!value.length) continue;
      lines.push(`${indent}**${heading}:**`);
      for (const item of value) {
        if (item && typeof item === "object") {
          const parts = Object.entries(item).map(([k, v]) => `${k}: ${v}`).join(", ");
          lines.push(`${indent}- ${parts}`);
        } else {
          lines.push(`${indent}- ${item}`);
        }
      }
    } else if (value && typeof value === "object") {
      lines.push(`${indent}**${heading}:**`);
      lines.push(formatStructuredAnswer(value as Record<string, unknown>, depth + 1));
    } else if (value !== null && value !== undefined) {
      lines.push(`${indent}**${heading}:** ${value}`);
    }
  }
  return lines.join("\n");
}

// ── Entry point ───────────────────────────────────────────────────────────────

// Gateway-path caller resolution (Phase 1+2, 2026-06-07). When ai-orchestrator
// is reached THROUGH ai-gateway, the gateway redacts the real worker_name to
// "<redacted>" before forwarding. Solo (no-hive) agents scope by worker_name,
// so resolve the caller's real display_name from the forwarded user JWT. `db`
// is the service-role client; getUser introspects the passed token (same
// pattern as analytics-orchestrator + export-hive-data's checkSupervisor).
// Returns null on the anon key / no session / invalid or expired token.
async function resolveDisplayName(db: SupabaseClient, jwt: string): Promise<string | null> {
  if (!jwt) return null;
  try {
    const { data: { user } } = await db.auth.getUser(jwt);
    if (!user) return null;
    // canonical-allow: solo/identity resolution. v_worker_truth is hive-scoped,
    // so a hiveless (solo) caller has no row there — worker_profiles is the
    // identity anchor for EVERY user and the only source that can resolve a
    // solo caller's own display_name. Same exception as analytics-orchestrator
    // + export-hive-data's checkSupervisor.
    const { data: p } = await db.from("worker_profiles")
      .select("display_name").eq("auth_uid", user.id).maybeSingle();
    return (p?.display_name as string | undefined) || null;
  } catch {
    return null;
  }
}

serveObserved("ai-orchestrator", tracedReply("ai-orchestrator", async (req, trace) => {
  // one trace id per request (tracedReply): every JSON reply returns it, and every model call's ai_cost_log row
  // carries the same id (LM-O, 2026-10-08)
  // Arc T/T1: standard liveness /health (fn up + DB creds reachable).
  const _health = await handleHealth(req, "ai-orchestrator", async () => ({
    deps: [{ name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) }],
  }));
  if (_health) return _health;
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  log.info(trace, "request_start", { method: req.method });  // I6 observability

  // ★A CALLER'S MISTAKE IS NOT A SERVER ERROR (live-walk wave, 2026-09-06). tools/prove_edge_contract.mjs asked this
  // function with a broken body and with GET: both reached `await req.json()` inside the main try and came back 500,
  // so a typo in a client read as "the platform is broken". The guards below are the same two every function that
  // passed the walk already had (agent-memory-store's 405 + 400 pair).
  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "That action is not allowed here. Reload the page and try again." }), {
      status: 405, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  try {
    let body;
    try { body = await req.json(); } catch {
      return new Response(JSON.stringify({ error: "That request could not be read. Reload the page and try again." }), {
        status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }
    // Gateway shape adapter (Phase 1+2): the gateway forwards `message`, while
    // direct callers send `question`. Accept either so both paths work.
    // Arc R (LLM10): cap user-controlled text before it enters router/synthesis prompts.
    // Matches the codebase's MAX_QUESTION_CHARS=500 standard (asset-brain-query). An
    // uncapped message is an injection budget + cost-exhaustion surface.
    const _q = body.question ?? body.message;
    const question = typeof _q === "string" ? _q.slice(0, 500) : _q;
    const { hive_id, mode } = body;
    // Gateway forwards the worker's recall window as `memory` (loadMemory +
    // formatMemoryContext). Thread it into synthesis so the assistant brain
    // honors prior turns (capstone Memory-pillar fix 2026-06-07).
    const memoryBlock = (typeof body.memory === "string" ? body.memory : "").slice(0, 4000);
    let worker_name = body.worker_name;

    if (!question) {
      return new Response(
        JSON.stringify({ error: "Missing required field: question" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const db = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    // AuthZ gate (2026-06-07 cross-hive fix). ai-orchestrator reads hive data
    // with the SERVICE-ROLE client (bypasses RLS), so it MUST re-authenticate
    // the caller — otherwise anyone could POST a foreign hive_id and read that
    // hive (cross-hive IDOR, the same class as the analytics-orchestrator leak
    // fixed in 1e42617). Both real callers (assistant.html via ai-gateway,
    // hive.html Coach) send the user's session JWT via db.functions.invoke.
    // Cases:
    //   - service_role bearer (trusted server-to-server, e.g. gateway fallback) -> allow
    //   - user JWT + hive_id -> require ACTIVE membership of that hive (else 403)
    //   - user JWT + solo (no hive_id) -> resolve own display_name for worker_name
    //     scoping (the gateway redacts worker_name to "<redacted>")
    const _bearer = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "");
    const _serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
    let _soloRlUid: string | null = null;   // a verified person with no hive: limited on their own bucket below
    // the hive the limiters count on: a service-role caller's (trusted), or one the membership check below proved
    let _verifiedHiveId: string | null = (_bearer && _serviceKey && _bearer === _serviceKey) ? (hive_id || null) : null;
    if (_bearer && _serviceKey && _bearer === _serviceKey) noteModelCaller({ auth_uid: null, hive_id: hive_id || null });
    if (!(_bearer && _serviceKey && _bearer === _serviceKey)) {
      const { data: { user: _caller } } = await db.auth.getUser(_bearer);
      if (!_caller) {
        return new Response(
          JSON.stringify({ error: "Authentication required" }),
          { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
      if (hive_id) {
        // ★A MEMBERSHIP READ THAT FAILED IS NOT A MEMBERSHIP THAT IS ABSENT (2026-10-06, found by walking
        // LXP199 with PostgREST genuinely stopped). This gate destructured `data` and threw `error` away, so a
        // read that NEVER RAN produced `!_mem` and the function announced 403 "Caller is not an active member of
        // this hive" - a statement about the person's standing in the hive, derived from no evidence. Measured on
        // analytics-report.html: Bryan Garcia, an active member of Baguio Textile Mills whose full report had
        // generated two minutes earlier, was told "You are not an active member of this hive... Switch or rejoin a
        // hive, then retry." The advice is useless (nothing is wrong with his membership) and alarming (it says
        // his access was revoked) and the one true cause - the service was down - was never mentioned.
        // The refused read is a FOURTH state, distinct from yes/no: it gets a 503 that says so.
        const { data: _mem, error: _memErr } = await db.from("v_worker_truth")
          .select("hive_status").eq("hive_id", hive_id).eq("auth_uid", _caller.id)
          .eq("hive_status", "active").maybeSingle();
        if (_memErr) {
          return new Response(
            JSON.stringify({ error: "Your membership could not be checked just now - the service did not answer. Nothing about your access has changed. Try again in a moment." }),
            { status: 503, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
        if (!_mem) {
          return new Response(
            JSON.stringify({ error: "Caller is not an active member of this hive" }),
            { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
        noteModelCaller({ auth_uid: _caller.id, hive_id });
        _verifiedHiveId = hive_id;
      } else {
        // Solo caller (no hive): resolve the real display_name for worker_name
        // scoping; the gateway sends "<redacted>".
        const _name = await resolveDisplayName(db, _bearer);
        if (!_name) {
          return new Response(
            JSON.stringify({ error: "No worker profile for caller" }),
            { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
        worker_name = _name;
        noteModelCaller({ auth_uid: _caller.id, hive_id: null, worker_name: _name });
        _soloRlUid = _caller.id;
      }
    }

    // LLM10 unbounded-consumption: rate-limit the user-facing 7-agent fan-out (the hive.html Coach
    // calls this DIRECTLY, not via the gateway). Skip the trusted service_role path (gateway/cron,
    // rate-limited upstream); key on the verified hive (solo callers are bounded single-user).
    if (!(_bearer && _serviceKey && _bearer === _serviceKey)) {
      // D12 per-SURFACE quota, OBSERVE-mode (mirrors the shared gateway pattern). Always counts into
      // (hive, route, hour) via hive_route_calls so per-surface AI pressure is VISIBLE - the
      // hive-wide cap alone cannot show which surface is burning the budget. It does NOT deny:
      // checkRouteRateLimit only enforces when an explicit hive_route_quotas row exists, and
      // none do, so this is a no-op behaviour change. Wrapped: quota bookkeeping must never
      // fail a real request.
      try {
        const _rq = await checkRouteRateLimit(db, _verifiedHiveId || "", "ai-orchestrator");
        // Denies ONLY when an explicit hive_route_quotas row exists (rq.per_route), so this stays
        // a no-op until an admin sets a cap - while always counting for attribution.
        if (_rq.per_route && !_rq.allowed) return routeRateLimitedResponse(corsHeaders, "ai-orchestrator", _rq.cap, _rq.retry_after_seconds, _rq.scope);
      } catch { /* empty-catch-allow: per-surface quota bookkeeping must never fail a real request */ }
      // ★THE GATEWAY DOES NOT ARRIVE AS service_role (2026-10-08). The comment above assumed it did; ai-gateway forwards
      // the person's OWN JWT, so every assistant / coach turn reached this line and counted the hive's ai_rate_limits row
      // a second time - the gateway's checkUserRateLimit had already counted it. A forward is proven only by the header
      // ai-gateway mints (_shared/gateway-trust.ts), never by a body field. The per-surface quota above stays on both
      // doors: it is keyed on this function's name, a bucket the gateway never touches.
      const _viaGateway = await isTrustedGatewayForward(req);
      if (!_viaGateway) {
        // ★A SOLO CALLER WAS NEVER COUNTED (2026-10-08). checkAIRateLimit(db, "") admits without tracking, so a person
        // with no hive calling this 7-agent fan-out directly had no limit at all. They draw on their own bucket (the
        // verified uid) with the budget a single-person hive gets.
        // (a caller with neither is the trusted service role - counted upstream, never by an empty hive key)
        if (_verifiedHiveId) {
          const _rl = await checkAIRateLimit(db, _verifiedHiveId);
          if (!_rl.allowed) return rateLimitedResponse(corsHeaders, _rl.scope ?? "hour", _rl.retry_after_seconds);
        } else if (_soloRlUid) {
          const _srl = await checkSoloRateLimit(db, soloRateLimitKey(_soloRlUid, null), DEFAULT_RATE_LIMIT_PER_HOUR, DEFAULT_RATE_LIMIT_PER_DAY, null, true);
          if (!_srl.allowed) return soloRateLimitedResponse(corsHeaders, _srl.retry_after_seconds, _srl.scope);
        }
      }
    }

    // The knowledge search for a SOLO person runs as that person (see orchestrate's semantic-search call). Reached only
    // after the gate above verified the bearer (getUser + a worker profile); a service-role caller has no person and
    // keeps the service-role search. ai-gateway's forward proof is relayed only when it verifies for this bearer.
    let _soloSearchHeaders: Record<string, string> | null = null;
    if (!hive_id && !(_bearer && _serviceKey && _bearer === _serviceKey)) {
      _soloSearchHeaders = { "Authorization": req.headers.get("Authorization") || "" };
      const _soloViaGateway = await isTrustedGatewayForward(req);
      if (_soloViaGateway) {
        _soloSearchHeaders[GATEWAY_FORWARD_HEADER] = req.headers.get(GATEWAY_FORWARD_HEADER) || "";
      }
    }

    const result = await orchestrate(question, hive_id || null, worker_name || null, db, mode || "chat", memoryBlock, _soloSearchHeaders);

    return new Response(
      JSON.stringify(result),
      { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );

  } catch (err) {
    log.error(null, "ai-orchestrator error:", { detail: err });
    // T2b: aggregate this HANDLED failure to wh_traces + non-leaky 500.
    return await failTracked(req, "ai-orchestrator", "ai_orchestrator_error", err);
  }
}));
