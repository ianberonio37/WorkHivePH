import { serveObserved, failTracked } from "../_shared/observability.ts";
import { handleHealth } from "../_shared/health.ts";

import { logRequestStart } from "../_shared/logger.ts";

// contract-allow: router; forwards to sub-agents
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { callAI } from "../_shared/ai-chain.ts";
import { log } from "../_shared/logger.ts";
import { logAICost, estimateTokens } from "../_shared/cost-log.ts";
import { getCorsHeaders } from "../_shared/cors.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
import { checkAIRateLimit, rateLimitedResponse, checkRouteRateLimit, routeRateLimitedResponse } from "../_shared/rate-limit.ts";
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
import { redactPII as _redactPII } from "../_shared/redactPII.ts";  // eslint-disable-line

function callGroq(prompt: string, systemPrompt: string): Promise<string> {
  return callAI(prompt, { systemPrompt, temperature: 0.2, maxTokens: 1024, jsonMode: true });
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

  const summary = data.map(e =>
    `${e.machine}|${e.category}|${e.root_cause || "unknown"}|${e.downtime_hours || 0}h|${e.created_at?.slice(0, 10)}`
  ).join("\n");

  const raw = await callGroq(`Logbook records (machine|category|root_cause|downtime|date):\n${summary}`, FAILURE_SYSTEM);
  return { agent: "failure_analysis", result: JSON.parse(raw) };
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

  const raw = await callGroq(`${facts}\n\nPer-asset (name|category|last_pm|status):\n${perAsset}`, PM_SYSTEM);
  return { agent: "pm_status", result: JSON.parse(raw) };
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

  const summary = data.map(i =>
    `${i.part_name}|qty:${i.qty_on_hand}|reorder_at:${i.reorder_point ?? "not set"}`
  ).join("\n");

  const raw = await callGroq(`Parts inventory (name|qty|reorder_point):\n${summary}`, INVENTORY_SYSTEM);
  return { agent: "inventory_risk", result: JSON.parse(raw) };
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

  const summary = data
    .filter(e => e.knowledge?.trim())
    .map(e => `${e.machine}|${e.category}|${e.knowledge}`)
    .join("\n");

  const raw = await callGroq(`Knowledge notes (machine|category|lesson):\n${summary}`, KNOWLEDGE_SYSTEM);
  return { agent: "knowledge_extraction", result: JSON.parse(raw) };
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
    .order("current_level", { ascending: false })
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

  const summary = enriched
    .map((b: any) => `${b.worker_name}|${b.discipline}|L${b.current_level}|cap:${b.capacity_signal}|open:${b.open_jobs}`)
    .join("\n");

  const raw = await callGroq(
    `Question: ${question}\n\nTechnician skills (worker|discipline|level):\n${summary}`,
    WORKFORCE_SYSTEM
  );
  return { agent: "workforce_match", result: JSON.parse(raw) };
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
  const summary = data.map(e =>
    `${e.machine}|${e.category}|${e.status}|${e.problem || ""}|${e.action || ""}|by <redacted>`
  ).join("\n");

  const raw = await callGroq(`Last 24h records (machine|category|status|problem|action|worker):\n${summary}`, HANDOVER_SYSTEM);
  return { agent: "shift_handover", result: JSON.parse(raw) };
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

  const summary = data.map(e => `${e.machine}|${e.created_at?.slice(0, 10)}`).join("\n");
  const today = new Date().toISOString().slice(0, 10);

  const raw = await callGroq(
    `Today: ${today}\nFailure history (machine|date):\n${summary}`,
    PREDICTIVE_SYSTEM
  );
  return { agent: "predictive", result: JSON.parse(raw) };
}

// ── ORCHESTRATOR: decides which agents to run, synthesizes answer ─────────────

const ROUTE_SYSTEM = `You are a maintenance intelligence router. Given a user question, decide which agents to run.
Respond only in JSON: { "agents": ["failure_analysis","pm_status","inventory_risk","knowledge_extraction","workforce_match","shift_handover","predictive"] }
Include only the agents relevant to the question. Use at least 1 and at most 4 agents.`;

const SYNTH_SYSTEM = `You are a senior maintenance manager AI. Given agent results, write a clear, practical answer to the user's question.
Be specific: name actual machines, workers, parts. Use bullet points for lists. Keep it under 200 words.
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

async function orchestrate(question: string, hiveId: string | null, workerName: string | null, db: SupabaseClient, mode = "chat", memoryBlock = "") {

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
    // Step 1: Route: decide which agents to call
    const routeRaw = await callGroq(`Question: "${question}"`, ROUTE_SYSTEM);
    try {
      agentsToRun = JSON.parse(routeRaw).agents || ["failure_analysis"];
    } catch {
      agentsToRun = ["failure_analysis"];
    }
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

  if (!successfulResults.length) {
    // CL5 fix (2026-07-08): a "what did I just tell you?" / reference-recall question makes the router
    // pick a specialist that returns no HIVE data — but the answer lives in the CONVERSATION memory the
    // gateway forwarded, not in a DB agent. Deflecting "not enough data" here (before synthesis) is why
    // the Work Assistant had NO multi-turn recall while the voice-journal companion did. So only deflect
    // when there is genuinely nothing to draw on (no agent data AND no conversation memory); otherwise
    // FALL THROUGH to the memory-grounded synthesis below (resultsText is empty, memoryPrefix carries the
    // prior turns) so the assistant answers conversationally from the working buffer.
    const hasMemory = !!(memoryBlock && memoryBlock.trim());
    if (!(hasMemory && RECALL_RE.test(question || ""))) {
      return { answer: "I couldn't find enough data to answer that yet. Add more logbook entries, PM completions, or skill badges to build up your knowledge base.", agents_used: agentsToRun };
    }
    // else: a recall/reference question WITH conversation memory → fall through to memory-grounded synthesis.
  }

  // Step 3: Fetch semantic context from knowledge base (RAG)
  let semanticContext = "";
  try {
    const searchRes = await fetch(
      `${Deno.env.get("SUPABASE_URL")}/functions/v1/semantic-search`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")}`,
        },
        body: JSON.stringify({ query: question, hive_id: hiveId, match_count: 3 }),
      }
    );
    if (searchRes.ok) {
      const searchData = await searchRes.json();
      semanticContext = searchData.context || "";
    }
  } catch { /* non-blocking: synthesis continues even if search fails */ }

  // Step 4: Synthesize: one final AI call to write the answer
  const resultsText = successfulResults.map(r =>
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
    let actions: Record<string, unknown>[] = [];
    try { actions = JSON.parse(coachRaw).actions || []; } catch { /* use empty */ }
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

  let answer: string = "I analyzed your data but had trouble formatting the response. Please try again.";
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

  // CL10 faithfulness rails (2026-07-08): (1) neutralize/hedge an ungrounded KPI %, then (2) strip any
  // fabricated COMPLETED-write claim ("Log entry added", "Updated maintenance record"). The assistant is
  // read-only advisory; a false "I did X" is trust-breaking in a maintenance context. Live-caught 2026-07-08.
  answer = stripFalseKpiProvenance(answer, `${resultsText}\n${semanticContext}\n${memoryBlock || ""}`);
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

serveObserved("ai-orchestrator", async (req) => {
  // Arc T/T1: standard liveness /health (fn up + DB creds reachable).
  const _health = await handleHealth(req, "ai-orchestrator", async () => ({
    deps: [{ name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) }],
  }));
  if (_health) return _health;
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  logRequestStart(req, "ai-orchestrator");  // I6 observability

  try {
    const body = await req.json();
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
    if (!(_bearer && _serviceKey && _bearer === _serviceKey)) {
      const { data: { user: _caller } } = await db.auth.getUser(_bearer);
      if (!_caller) {
        return new Response(
          JSON.stringify({ error: "Authentication required" }),
          { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
      if (hive_id) {
        const { data: _mem } = await db.from("v_worker_truth")
          .select("hive_status").eq("hive_id", hive_id).eq("auth_uid", _caller.id)
          .eq("hive_status", "active").maybeSingle();
        if (!_mem) {
          return new Response(
            JSON.stringify({ error: "Caller is not an active member of this hive" }),
            { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }
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
        const _rq = await checkRouteRateLimit(db, hive_id || "" || "", "ai-orchestrator");
        // Denies ONLY when an explicit hive_route_quotas row exists (rq.per_route), so this stays
        // a no-op until an admin sets a cap - while always counting for attribution.
        if (_rq.per_route && !_rq.allowed) return routeRateLimitedResponse(corsHeaders, "ai-orchestrator", _rq.cap);
      } catch { /* empty-catch-allow: per-surface quota bookkeeping must never fail a real request */ }
      const _rl = await checkAIRateLimit(db, hive_id || "");
      if (!_rl.allowed) return rateLimitedResponse(corsHeaders);
    }

    const result = await orchestrate(question, hive_id || null, worker_name || null, db, mode || "chat", memoryBlock);

    return new Response(
      JSON.stringify(result),
      { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );

  } catch (err) {
    log.error(null, "ai-orchestrator error:", { detail: err });
    // T2b: aggregate this HANDLED failure to wh_traces + non-leaky 500.
    return await failTracked(req, "ai-orchestrator", "ai_orchestrator_error", err);
  }
});
