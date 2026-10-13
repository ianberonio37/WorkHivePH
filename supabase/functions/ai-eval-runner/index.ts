/**
 * ai-eval-runner -- LLM-as-judge runner for canonical-question fixtures.
 *
 * Invoked nightly from 03:30 UTC by six pg_cron jobs, `ai-eval-daily-<agent>`, one agent per call
 * and 3 minutes apart (20261007000011; they replaced the single `ai-eval-daily` job of
 * 20260511000006). The slices of one night share a run_id. For each fixture:
 *
 *   1. Forward the question to the ai-gateway under the fixture's agent_id.
 *   2. Score the gateway's response via LLM-as-judge:
 *      - PASS if score >= 70 AND every expected_keyword appears.
 *   3. Persist (agent_id, question_id, question_text, expected_keywords,
 *      actual_answer, score, passed, judge_model, failure_reason) into
 *      ai_quality_log.
 *
 * Skills consulted: ai-engineer (LLM-as-judge prompt pattern,
 * cross-model scoring stability), qa-tester (golden-set discipline),
 * architect (the eval runner is the structural prerequisite for the
 * L4 freshness teeth on validate_ai_eval_coverage.py).
 *
 * Closes PRODUCTION_FIXES #52 Phase D (runner wired) -- the cron was
 * scheduled in Phase B/C but the endpoint it called did not exist.
 *
 * ★THE EVAL THAT NEVER MEASURED AN ANSWER (2026-10-07). Every graded row this runner ever wrote -
 *   1,765 of 1,765 - had actual_answer "[gateway error: 401]". It called ai-gateway with the
 *   SERVICE-ROLE key as the bearer; the gateway resolves a USER from the bearer and refuses every
 *   agent except voice-journal without one. The judge then dutifully graded the error string, so the
 *   log read as "every agent fails quality" when nothing had been asked at all.
 *   The fix is an IDENTITY, not a gateway exception: the runner signs in as ONE dedicated eval
 *   account (EVAL_EMAIL), a supervisor of ONE dedicated eval hive (EVAL_HIVE_ID) that holds no real
 *   tenant's data, and sends that account's own JWT. The gateway is untouched - it verifies the JWT,
 *   proves the membership with resolveTenancy, and buckets the rate limit on the verified hive and
 *   user exactly as it does for a person (Pillar P). No anon path and no user path is widened.
 *   The session is minted with the service role (admin generateLink -> verifyOtp on the hashed
 *   token), never returned or logged, and signed out when the run ends. Only a SERVICE-ROLE caller
 *   (the pg_cron job, CI) may start a run: the eval identity's quota is shared, so an anonymous
 *   caller must not be able to spend it.
 *   And a row is only GRADED when there was an answer to grade: a non-2xx gateway reply, a thrown
 *   fetch, an empty answer or a judge that could not answer is recorded as outcome "infra_error"
 *   with score/passed NULL - an infrastructure failure, never a quality failure.
 *   Locked by tools/validate_ai_eval_answers_are_real.py (gate id ai-eval-answers-real).
 *
 * ★MEASURABLE, INDEPENDENT, AND INSIDE THE TIME LIMIT (2026-10-07, second pass). With the identity fixed,
 *   the first authorised run exposed three more reasons the eval measured less than it claimed:
 *   - The eval hive was EMPTY. analytics answered "No failures logged this period" (graded 0: a measurement
 *     of an empty hive, not of the agent); asset-brain was refused 400 because the fixture names tag_id
 *     PMP-001 while the gateway forwards only context.asset_id/asset_tag; project had no project_id. About 6
 *     of 18 fixtures were never measured. Now public.ai_eval_bench_ensure seeds the eval hive (only it) with
 *     assets, PM history, 90 days of breakdowns and project WO-2026-001, and benchContext() gives each fixture
 *     the ids its specialist needs - or records "missing context" WITHOUT calling a model.
 *   - The eval REMEMBERED itself. The gateway saves every user turn and replays the last 10 per agent, so
 *     fixture N was answered with fixtures 1..N-1 (and last night) in its prompt. The eval account's memory is
 *     reset before every fixture and after the run (public.ai_eval_bench_reset_memory).
 *   - A full run did not fit the hosted wall-clock limit (one 546 WORKER_LIMIT). The cron now calls one agent
 *     per call, and the runner stops starting fixtures when RUN_BUDGET_MS is spent.
 *
 * AI_ASSET_VERSION: 5
 *   (v5, 2026-08-31: the judge asset's hash moved without a bump — an earlier-today edit to this
 *   function's judge content shipped silently; the C5 gate caught it as silent_change 4069c6b9→
 *   5ebffd9e. This bump ANNOUNCES that edit; no judge behavior is changed by the bump itself.)
 * C5 (Self-Improving Gate) — bump this integer whenever JUDGE_PROMPT,
 * judge model id, score rubric, or pass-threshold changes. C2's eval
 * gate scores against this judge's verdicts, so an unannounced edit
 * here invalidates baselines. The ai-asset-versioning validator FAILs
 * if the file hash moves without this bumping. Owner: AI Engineer.
 */

import { serveObserved } from "../_shared/observability.ts";
import { tracedReply } from "../_shared/trace-reply.ts";  // LM-E/LM-O: one trace id per request
import { handleHealth } from "../_shared/health.ts";


// contract-allow: eval harness; runs fixtures through ai-gateway
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.110.0";
import { getCorsHeaders } from "../_shared/cors.ts";
import { log } from "../_shared/logger.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
import { callAI } from "../_shared/ai-chain.ts";
// Arc R (A01/LLM10): verify_jwt=false eval harness runs real model calls per fixture - service-role callers only.
import { resolveIdentity } from "../_shared/tenant-context.ts";
// the gateway's adaptive-cache key, so the per-fixture reset deletes exactly the row the gateway wrote
import { answerCacheTenant, answerCacheKey } from "../_shared/cache.ts";

// Module-scope warm client.
const _WH_SUPABASE_URL_M = Deno.env.get("SUPABASE_URL") || "";
const _WH_SERVICE_KEY_M  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const _whWarmClient = _WH_SUPABASE_URL_M && _WH_SERVICE_KEY_M
  ? createClient(_WH_SUPABASE_URL_M, _WH_SERVICE_KEY_M)
  : null;
void _whWarmClient;

// ── The eval identity (see the header). ONE account, ONE hive, both fixed here and never taken from a
// request. The hive holds no real tenant's data, which matters because ai_quality_log is readable by every
// signed-in user: an answer grounded in a real plant's records would publish that plant to the platform.
const EVAL_EMAIL        = "ai-eval-runner@workhive.test";
const EVAL_USERNAME     = "wh_ai_eval_runner";
const EVAL_DISPLAY_NAME = "AI Eval Runner";
const EVAL_HIVE_ID      = "50f51f72-66ec-4e9d-8dfd-daa5f1eb696c";
const EVAL_HIVE_NAME    = "WorkHive AI Eval Bench";

interface EvalSession { token: string; authUid: string }

function evalInviteCode(): string {
  // hives.invite_code is char(6) UNIQUE; random so nobody can guess their way into the eval hive.
  const abc = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const bytes = crypto.getRandomValues(new Uint8Array(6));
  return Array.from(bytes, (b) => abc[b % abc.length]).join("");
}

/** Ensure the eval account, its profile, the eval hive and its supervisor membership exist (each step is a
 *  no-op once done), then mint a session for that account. Throws with a reason; the caller records every
 *  fixture as infra_error rather than falling back to a bearer the gateway refuses. */
async function mintEvalSession(
  // deno-lint-ignore no-explicit-any
  db: any, supabaseUrl: string, anonKey: string,
): Promise<EvalSession> {
  if (!anonKey) throw new Error("SUPABASE_ANON_KEY is not set, so no session can be verified");
  // generateLink creates the account on first use and returns a single-use hashed token for it.
  const { data: link, error: linkErr } = await db.auth.admin.generateLink({ type: "magiclink", email: EVAL_EMAIL });
  const authUid: string | undefined = link?.user?.id;
  const tokenHash: string | undefined = link?.properties?.hashed_token;
  if (linkErr || !authUid || !tokenHash) {
    throw new Error(`could not issue a sign-in for the eval account - ${linkErr?.message || "no token returned"}`);
  }

  // canonical-allow: a write-path existence check before INSERTING the eval account's own profile; v_worker_truth is
  // one row per hive membership, so a freshly issued account with no membership yet would never appear there.
  const { data: prof, error: profErr } = await db.from("worker_profiles")
    .select("auth_uid").eq("auth_uid", authUid).maybeSingle();
  if (profErr) throw new Error(`eval profile read failed - ${profErr.message}`);
  if (!prof) {
    const { error } = await db.from("worker_profiles").insert({
      auth_uid: authUid, username: EVAL_USERNAME, display_name: EVAL_DISPLAY_NAME, email: EVAL_EMAIL,
    });
    if (error) throw new Error(`eval profile could not be created - ${error.message}`);
  }

  // existence check through the canonical view (canonical-sources); the insert below still targets the table
  const { data: hive, error: hiveErr } = await db.from("v_hives_truth").select("id").eq("id", EVAL_HIVE_ID).maybeSingle();
  if (hiveErr) throw new Error(`eval hive read failed - ${hiveErr.message}`);
  if (!hive) {
    const { error } = await db.from("hives").insert({
      id: EVAL_HIVE_ID, name: EVAL_HIVE_NAME, invite_code: evalInviteCode(), created_by: EVAL_DISPLAY_NAME,
    });
    if (error) throw new Error(`eval hive could not be created - ${error.message}`);
  }

  // canonical-allow: a write-path existence check (ANY status) before inserting the eval membership; v_worker_truth
  // shows active memberships only, so a pending or left row would read as absent and the insert would collide.
  const { data: mem, error: memErr } = await db.from("hive_members")
    .select("id, status").eq("hive_id", EVAL_HIVE_ID).eq("auth_uid", authUid).maybeSingle();
  if (memErr) throw new Error(`eval membership read failed - ${memErr.message}`);
  if (!mem) {
    const { error } = await db.from("hive_members").insert({
      hive_id: EVAL_HIVE_ID, auth_uid: authUid, worker_name: EVAL_DISPLAY_NAME, role: "supervisor", status: "active",
    });
    if (error) throw new Error(`eval membership could not be created - ${error.message}`);
  } else if (mem.status !== "active") {
    const { error } = await db.from("hive_members").update({ status: "active" }).eq("id", mem.id);
    if (error) throw new Error(`eval membership could not be re-activated - ${error.message}`);
  }

  const anon = createClient(supabaseUrl, anonKey, { auth: { persistSession: false, autoRefreshToken: false } });
  const { data: verified, error: vErr } = await anon.auth.verifyOtp({ token_hash: tokenHash, type: "email" });
  const token = verified?.session?.access_token;
  if (vErr || !token) throw new Error(`eval sign-in could not be verified - ${vErr?.message || "no session"}`);
  return { token, authUid };
}

/** What the gateway's reply means for grading. A reply that is not an answer is an infrastructure failure:
 *  grading it would record "the model answered badly" about a question nobody answered. */
async function readGatewayReply(res: Response): Promise<{ answer: string; infraReason: string | null }> {
  if (!res.ok) {
    let detail = "";
    try { detail = (await res.text()).slice(0, 240); } catch { /* empty-catch-allow: the status alone is the finding */ }
    return { answer: `[gateway error: ${res.status}]`, infraReason: `gateway ${res.status}${detail ? ": " + detail : ""}` };
  }
  // The gateway answers in the shared envelope { ok, data: { answer, agent, usage } } (P1, 2026-05-26). This
  // runner read the pre-envelope top-level `answer`, so even an authorised call would have recorded "" -
  // the second reason no answer was ever measured, hidden behind the 401 (found 2026-10-07 by the first
  // authorised run, which this function recorded as "gateway 200 with no answer" instead of grading it).
  let j: { answer?: unknown; data?: { answer?: unknown } } | null = null;
  try { j = await res.json(); } catch { /* falls through to the empty-answer reason */ }
  const answer = String(j?.data?.answer ?? j?.answer ?? "");
  if (!answer.trim()) return { answer: "", infraReason: "gateway 200 with no answer" };
  return { answer, infraReason: null };
}

// ── The eval BENCH (see the header). public.ai_eval_bench_ensure (20261007000011) seeds the eval hive - and
// only that hive: its id is a constant inside the function - and returns the ids of what it seeded.
interface EvalBench {
  ready:      boolean;
  error:      string | null;
  rebuilt:    boolean;
  assets:     Record<string, string>;   // tag  -> asset_nodes.id
  projects:   Record<string, string>;   // code -> projects.id
  breakdowns: number;                   // corrective entries in the last 90 days
}

// deno-lint-ignore no-explicit-any
async function loadEvalBench(db: any, authUid: string): Promise<EvalBench> {
  const empty = { ready: false, rebuilt: false, assets: {}, projects: {}, breakdowns: 0 };
  try {
    const { data, error } = await db.rpc("ai_eval_bench_ensure", { p_auth_uid: authUid });
    if (error || !data) return { ...empty, error: `the eval bench could not be seeded - ${error?.message || "no reply"}` };
    const breakdowns = Number(data.breakdowns) || 0;
    return {
      ready:      breakdowns > 0,
      error:      breakdowns > 0 ? null : "the eval bench holds no corrective history",
      rebuilt:    Boolean(data.rebuilt),
      assets:     (data.assets || {}) as Record<string, string>,
      projects:   (data.projects || {}) as Record<string, string>,
      breakdowns,
    };
  } catch (err) {
    return { ...empty, error: `the eval bench could not be seeded - ${err instanceof Error ? err.message : String(err)}` };
  }
}

// What each agent's fixtures are asked ABOUT on the bench. A fixture may name its own subject (context.tag_id or
// context.asset_tag, context.project_code); otherwise the agent's default applies. `history`: the agent reads the
// hive's records and needs no id, but an unseeded bench gives it nothing to answer from.
const BENCH_SUBJECT: Record<string, { asset?: string; project?: string; history?: boolean }> = {
  "asset-brain": { asset: "PMP-001" },
  "project":     { project: "WO-2026-001" },
  "analytics":   { history: true },
  "shift":       { history: true },
};

/** The context the gateway needs for this fixture, or why it cannot have one. A fixture whose subject is not on the
 *  bench is NOT sent: the specialist would refuse it (400) or answer about an empty hive, and either way nothing
 *  about the agent would be measured. It is recorded as "missing context" - the gate FAILs on that. */
function benchContext(agentId: string, fixture: Fixture, bench: EvalBench):
  { context: Record<string, unknown>; missing: null } | { context: null; missing: string } {
  const ctx: Record<string, unknown> = { ...(fixture.context || {}) };
  const need = BENCH_SUBJECT[agentId];
  if (!need) return { context: ctx, missing: null };
  if (!bench.ready) return { context: null, missing: `missing context: ${bench.error || "the eval bench is not seeded"}` };
  if (need.asset) {
    const tag = String(ctx.tag_id || ctx.asset_tag || need.asset);
    const id = bench.assets[tag];
    if (!id) return { context: null, missing: `missing context: asset ${tag} is not on the eval bench` };
    // asset_tag is the gateway's documented field (verified-state grounds on it); asset_id is what
    // asset-brain-query requires, and passing it skips the gateway's second, hive-scoped tag lookup.
    return { context: { ...ctx, asset_tag: tag, asset_id: id }, missing: null };
  }
  if (need.project) {
    const code = String(ctx.project_code || need.project);
    const id = bench.projects[code];
    if (!id) return { context: null, missing: `missing context: project ${code} is not on the eval bench` };
    // the gateway lifts context.project_id to the top level, where project-orchestrator reads it
    return { context: { ...ctx, project_code: code, project_id: id }, missing: null };
  }
  return { context: ctx, missing: null };
}

// ── Independence (see the header). Reset before every fixture and once after the run, by
// public.ai_eval_bench_reset_memory: the eval account + eval hive only, and the adaptive-cache rows of the
// questions this run asked (ai-gateway serves that cache on a 429; since 2026-10-07 it is keyed on the VERIFIED
// tenant - the proven hive + auth uid - so these are the eval account's own rows in the eval hive, and no other).
/** The key ai-gateway's adaptive cache files this question under for the eval account acting in the eval hive.
 *  Computed by the gateway's own helper, so the reset cannot drift from what the gateway writes. */
async function adaptiveCacheKeys(agentId: string, question: string, evalAuthUid: string): Promise<string[]> {
  const tenant = answerCacheTenant(EVAL_HIVE_ID, evalAuthUid);
  return tenant ? [await answerCacheKey(tenant, agentId, question)] : [];
}

// deno-lint-ignore no-explicit-any
async function resetEvalMemory(db: any, authUid: string, cacheKeys: string[]):
  Promise<{ deleted: Record<string, number>; error: string | null }> {
  try {
    const { data, error } = await db.rpc("ai_eval_bench_reset_memory", { p_auth_uid: authUid, p_cache_keys: cacheKeys });
    if (error) return { deleted: {}, error: error.message };
    return { deleted: (data || {}) as Record<string, number>, error: null };
  } catch (err) {
    return { deleted: {}, error: err instanceof Error ? err.message : String(err) };
  }
}

// ── The time limit (see the header). The hosted edge runtime kills a call at its wall-clock limit (150 s on the
// free plan), and a killed run loses its heartbeat as well as its remaining fixtures. The nightly cron calls one
// agent per call (3 fixtures, ~20-35 s); for any larger call the runner stops STARTING fixtures once this budget
// is spent and records the rest as not run.
const RUN_BUDGET_MS      = Math.max(30_000, Number(Deno.env.get("AI_EVAL_RUN_BUDGET_MS")) || 110_000);
const FIXTURE_RESERVE_MS = 20_000;   // a slow fixture: gateway + specialist + judge
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Canonical question fixtures embedded inline. Kept in sync with
// evals/canonical_questions.json — the repo file is the source of truth
// for editors; this constant is the runtime copy the runner uses. When
// adding fixtures, edit both. A future iteration will move these into
// an ai_eval_canonical_questions table for external editing.
interface Fixture {
  id:                 string;
  question:           string;
  expected_keywords:  string[];
  context?:           Record<string, unknown>;
}

const FIXTURES: Record<string, Fixture[]> = {
  "asset-brain": [
    {
      id: "asset-brain-failure-history",
      question: "What is the failure history of this asset?",
      context: { asset_type: "centrifugal pump", tag_id: "PMP-001" },
      expected_keywords: ["failure", "history", "MTBF"],
    },
    {
      id: "asset-brain-next-pm",
      question: "When is the next PM due?",
      context: { tag_id: "PMP-001" },
      expected_keywords: ["PM", "due", "schedule"],
    },
    {
      id: "asset-brain-similar-failures",
      question: "Have similar pumps failed recently? What was the root cause?",
      context: { asset_type: "centrifugal pump", tag_id: "PMP-001" },
      expected_keywords: ["similar", "pump", "root cause"],
    },
  ],
  "analytics": [
    {
      id: "analytics-oee-last-week",
      question: "What was the OEE last week?",
      expected_keywords: ["OEE", "availability", "performance"],
    },
    {
      id: "analytics-mtbf-trend",
      question: "Is MTBF improving or worsening?",
      expected_keywords: ["MTBF", "trend"],
    },
    {
      id: "analytics-top-failures",
      question: "What are the top failure modes this month?",
      expected_keywords: ["failure", "mode"],
    },
  ],
  "project": [
    {
      id: "project-status",
      question: "What is the status of project WO-2026-001?",
      expected_keywords: ["status", "progress"],
    },
    {
      id: "project-blockers",
      question: "What are the current blockers?",
      expected_keywords: ["blocker", "risk"],
    },
    {
      id: "project-change-order",
      question: "Should we approve this change order?",
      expected_keywords: ["change", "order", "cost"],
    },
  ],
  "shift": [
    {
      id: "shift-coverage",
      question: "Is tomorrow's shift fully covered?",
      expected_keywords: ["shift", "coverage", "worker"],
    },
    {
      id: "shift-handover",
      question: "Summarise the last 24 hours for handover.",
      expected_keywords: ["handover", "logbook"],
    },
    {
      id: "shift-skill-gap",
      question: "Do we have HVAC skills on tonight's shift?",
      expected_keywords: ["HVAC", "skill"],
    },
  ],
  "logbook-voice": [
    {
      id: "lv-fault-entry",
      question: "Pump bearing seized, replaced with spare, 2 hours downtime.",
      expected_keywords: ["pump", "bearing", "downtime"],
    },
    {
      id: "lv-close-out",
      question: "Job done, all parts back in stores.",
      expected_keywords: ["complete", "parts"],
    },
    {
      id: "lv-incomplete",
      question: "Need more parts, will continue tomorrow.",
      expected_keywords: ["parts", "continue"],
    },
  ],
  "report-voice": [
    {
      id: "rv-daily-summary",
      question: "Send a daily summary to the maintenance manager.",
      expected_keywords: ["daily", "summary", "manager"],
    },
    {
      id: "rv-asset-detail",
      question: "Report on the failure history of pump 5.",
      expected_keywords: ["failure", "history", "pump"],
    },
    {
      id: "rv-team-overview",
      question: "Send the team a heads-up about tomorrow's planned downtime.",
      expected_keywords: ["team", "downtime"],
    },
  ],
};

const JUDGE_PROMPT = `You score AI-assistant answers against expected keywords.

Return ONLY a JSON object with this shape:
{
  "score":    <number 0-100>,
  "passed":   <boolean>,
  "missing":  [<string>, ...]  // expected keywords NOT found in the answer
}

Score rubric:
  100 -- answer contains every expected keyword and is on-topic
   70-99 -- on-topic, most keywords present, light reasoning gaps
   40-69 -- partially on-topic, several keywords missing
    0-39 -- off-topic or empty

passed = (score >= 70) AND (missing is empty).`;

async function judgeAnswer(
  question: string,
  expectedKeywords: string[],
  actualAnswer: string,
): Promise<{ score: number; passed: boolean; missing: string[]; failure_reason: string | null; judge_error?: boolean }> {
  const userMsg =
    `Question: ${question}\n` +
    `Expected keywords: ${JSON.stringify(expectedKeywords)}\n` +
    `Actual answer:\n${actualAnswer}`;
  try {
    const raw = await callAI(userMsg, {
      systemPrompt: JUDGE_PROMPT,
      maxTokens: 256,
      jsonMode: true,
    });
    const parsed = JSON.parse(raw);
    // a degraded chain answers "{}" - no score is a judge that did not judge, not a score of 0
    if (parsed === null || typeof parsed !== "object" || !Number.isFinite(Number(parsed.score))
        || parsed.score === null || parsed.score === "") {
      throw new Error(`judge returned no score (${String(raw).slice(0, 60)})`);
    }
    return {
      score:          Number(parsed.score) || 0,
      passed:         Boolean(parsed.passed),
      missing:        Array.isArray(parsed.missing) ? parsed.missing : [],
      failure_reason: parsed.passed ? null : `score=${parsed.score} missing=${(parsed.missing || []).join(",")}`,
    };
  } catch (err) {
    return {
      score:          0,
      passed:         false,
      missing:        expectedKeywords,
      failure_reason: `judge error: ${err instanceof Error ? err.message : String(err)}`,
      // the judge could not answer: the row is ungraded, not a 0 the answer earned
      judge_error:    true,
    };
  }
}

serveObserved("ai-eval-runner", tracedReply("ai-eval-runner", async (req, trace) => {
  // one trace id per request (tracedReply): every JSON reply returns it, and every model call's ai_cost_log row
  // carries the same id (LM-O, 2026-10-08)
  // Arc T/T1: standard liveness /health (fn up + DB creds reachable).
  const _health = await handleHealth(req, "ai-eval-runner", async () => ({
    deps: [{ name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) }],
  }));
  if (_health) return _health;
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  log.info(trace, "request_start", { method: req.method });  // I6 observability

  const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
  const SERVICE_KEY  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
  if (!SUPABASE_URL || !SERVICE_KEY) {
    return new Response(
      JSON.stringify({ error: "ai-eval-runner: missing service env" }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  }
  const db = _whWarmClient || createClient(SUPABASE_URL, SERVICE_KEY);

  // Arc R (A01/LLM10): a run asks every fixture through the gateway AND the judge, under the ONE eval
  // identity. It is cron + CI only, so it is SERVICE-ROLE only (2026-10-07). It used to bound anonymous
  // callers by IP and let them through - harmless while every gateway call 401'd, but a caller who can
  // start a real run spends the eval identity's quota and the org-shared model budget, and can starve the
  // nightly measurement. A person has no reason to start one.
  {
    const _id = await resolveIdentity(db, req);
    if (!_id.isServiceRole) {
      return new Response(
        JSON.stringify({ error: "The quality evaluation runs on a schedule and cannot be started from here.", code: "internal_only" }),
        { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }
  }

  // Optional request filter (does NOT change JUDGE_PROMPT/model/rubric/threshold/fixtures — the
  // frozen golden C2 scores against is untouched; it only narrows WHICH fixtures run this call).
  //   { "only": "<agent_id>" }          run just one agent's fixtures (each nightly cron job is one of these)
  //   { "ids": ["<fixture id>", ...] }  run just these fixtures
  //   { "offset": <n>, "limit": <n> }   a window over the selected fixtures (limit alone = a cap; CI smoke)
  //   { "run_id": "<uuid>" }            join a run: the nightly slices pass one run_id per UTC night
  // No body / empty body → every fixture in one call (bounded by RUN_BUDGET_MS, so prefer slices).
  let onlyAgent: string | null = null;
  let onlyIds: Set<string> | null = null;
  let offset = 0;
  let limit = 0;
  let runIdIn: string | null = null;
  if (req.method === "POST") {
    try {
      const body = await req.json();
      if (body && typeof body === "object") {
        if (typeof body.only === "string" && body.only) onlyAgent = body.only;
        if (Array.isArray(body.ids)) {
          const ids = body.ids.filter((x: unknown) => typeof x === "string" && x);
          if (ids.length) onlyIds = new Set(ids as string[]);
        }
        if (typeof body.offset === "number" && body.offset > 0) offset = Math.floor(body.offset);
        if (typeof body.limit === "number" && body.limit > 0) limit = Math.floor(body.limit);
        if (typeof body.run_id === "string" && UUID_RE.test(body.run_id)) runIdIn = body.run_id.toLowerCase();
      }
    } catch { /* no/blank body — full run */ }
  }

  const t0 = Date.now();
  // every row of one run shares run_id (and each call's rows share run_at), so "the latest run" is a query, not a
  // guess - and a night sliced across six calls is still ONE run
  const runId = runIdIn || crypto.randomUUID();
  const runAt = new Date(t0).toISOString();
  const results: Array<{
    agent_id: string; question_id: string; outcome: "graded" | "infra_error";
    passed: boolean | null; score: number | null; infra_reason?: string;
    memory_reset_before?: number | null;
  }> = [];
  let totalCalls = 0;
  let judgeCalls = 0;

  // The eval identity. If it cannot be had, every fixture is recorded as an infrastructure failure with
  // the reason - no gateway call is made with a bearer the gateway would refuse, and nothing is judged.
  const ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY") || "";
  let evalSession: EvalSession | null = null;
  let identityError: string | null = null;
  try {
    evalSession = await mintEvalSession(db, SUPABASE_URL, ANON_KEY);
  } catch (err) {
    identityError = `eval identity unavailable: ${err instanceof Error ? err.message : String(err)}`;
    log.warn(null, "ai-eval-runner: eval identity unavailable", { detail: identityError });
  }

  // Which fixtures this call runs: the agent/ids filter first, then the offset/limit window.
  const queue: Array<{ agentId: string; fixture: Fixture }> = [];
  for (const [agentId, fixtures] of Object.entries(FIXTURES)) {
    if (onlyAgent && agentId !== onlyAgent) continue;
    for (const fixture of fixtures) {
      if (!onlyIds || onlyIds.has(fixture.id)) queue.push({ agentId, fixture });
    }
  }
  const selected = queue.slice(offset, limit ? offset + limit : undefined);

  // The bench the fixtures are asked about (seeded on first use, re-anchored weekly).
  const bench = evalSession ? await loadEvalBench(db, evalSession.authUid) : null;
  const runCacheKeys: string[] = [];
  const resetTotals: Record<string, number> = {};
  const resetErrors: string[] = [];
  let resetCalls = 0;
  const tally = (r: { deleted: Record<string, number>; error: string | null }) => {
    resetCalls++;
    for (const [k, v] of Object.entries(r.deleted)) resetTotals[k] = (resetTotals[k] || 0) + (Number(v) || 0);
    if (r.error) resetErrors.push(r.error.slice(0, 200));
  };

  for (const { agentId, fixture } of selected) {
    totalCalls++;
    let actualAnswer = "";
    let infraReason: string | null = identityError;
    let gatewayContext: Record<string, unknown> = fixture.context || {};
    let resetBefore: number | null = null;

    // Out of time: record it rather than be killed mid-fixture (which would also lose the heartbeat).
    const spent = Date.now() - t0;
    if (!infraReason && spent > RUN_BUDGET_MS - FIXTURE_RESERVE_MS) {
      infraReason = `not run: this call's time budget (${Math.round(RUN_BUDGET_MS / 1000)} s) was spent after `
        + `${totalCalls - 1} fixture(s) - run fewer per call (the nightly cron runs one agent per call)`;
    }
    // The ids the specialist needs, from the bench - or no model call at all.
    if (!infraReason && evalSession && bench) {
      const bc = benchContext(agentId, fixture, bench);
      if (bc.missing !== null) infraReason = bc.missing;
      else gatewayContext = bc.context;
    }
    // A clean slate: no earlier fixture's turn, memory or cached answer in this one's context.
    if (!infraReason && evalSession) {
      const keys = await adaptiveCacheKeys(agentId, fixture.question, evalSession.authUid);
      runCacheKeys.push(...keys);
      const r = await resetEvalMemory(db, evalSession.authUid, keys);
      tally(r);
      resetBefore = Object.values(r.deleted).reduce((s, v) => s + (Number(v) || 0), 0);
      if (r.error) infraReason = `memory reset failed, so this answer would not be independent - ${r.error}`;
    }
    if (!infraReason && evalSession) {
      try {
        const gwUrl = `${SUPABASE_URL}/functions/v1/ai-gateway`;
        const res = await fetch(gwUrl, {
          // never past the call's budget: a hung specialist must not take the heartbeat down with it
          signal: AbortSignal.timeout(Math.min(60_000, Math.max(5_000, RUN_BUDGET_MS - (Date.now() - t0) - 5_000))),
          method: "POST",
          headers: {
            // the eval ACCOUNT's own session - the gateway verifies it like any person's
            "Authorization": `Bearer ${evalSession.token}`,
            "apikey":        ANON_KEY,
            "Content-Type":  "application/json",
          },
          body: JSON.stringify({
            agent:   agentId,
            message: fixture.question,
            context: gatewayContext,
            // the eval hive; the gateway proves the membership itself (resolveTenancy)
            hive_id: EVAL_HIVE_ID,
          }),
        });
        ({ answer: actualAnswer, infraReason } = await readGatewayReply(res));
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        actualAnswer = `[gateway threw: ${msg}]`;
        infraReason = `gateway threw: ${msg}`;
      }
    }

    // ONLY an answer is graded. An infra failure is recorded as one, and costs no judge call.
    if (!infraReason) judgeCalls++;
    const judged = infraReason ? null : await judgeAnswer(
      fixture.question,
      fixture.expected_keywords,
      actualAnswer,
    );
    if (judged?.judge_error) infraReason = judged.failure_reason || "judge error";
    const graded = !infraReason && judged !== null;

    const { error: logErr } = await db.from("ai_quality_log").insert({
      agent_id:          agentId,
      question_id:       fixture.id,
      question_text:     fixture.question,
      expected_keywords: fixture.expected_keywords,
      actual_answer:     actualAnswer.slice(0, 4000),
      score:             graded ? judged!.score : null,
      passed:            graded ? judged!.passed : null,
      judge_model:       graded ? "callAI-chain" : "not-judged",
      failure_reason:    graded ? judged!.failure_reason : `infra: ${String(infraReason).slice(0, 400)}`,
      outcome:           graded ? "graded" : "infra_error",
      run_id:            runId,
      run_at:            runAt,
    });
    if (logErr) log.warn(null, "ai_quality_log insert failed:", { detail: logErr.message });

    results.push({
      agent_id:    agentId,
      question_id: fixture.id,
      outcome:     graded ? "graded" : "infra_error",
      passed:      graded ? judged!.passed : null,
      score:       graded ? judged!.score : null,
      ...(graded ? {} : { infra_reason: String(infraReason).slice(0, 200) }),
      // rows the reset removed before this fixture ran: the previous fixture's turn, memories and cache
      memory_reset_before: resetBefore,
    });
  }

  // Leave nothing behind: the last fixture's turn, distilled memories, specialist caches and cached answers.
  let resetAfterRun: Record<string, number> | null = null;
  if (evalSession && runCacheKeys.length) {
    const r = await resetEvalMemory(db, evalSession.authUid, [...new Set(runCacheKeys)]);
    tally(r);
    resetAfterRun = r.deleted;
  }

  // The eval session is single-purpose: revoke it now rather than leave it live for its hour.
  if (evalSession) {
    try {
      const { error: soErr } = await db.auth.admin.signOut(evalSession.token, "local");
      if (soErr) log.warn(null, "ai-eval-runner: eval session sign-out failed", { detail: soErr.message });
    } catch (err) {
      log.warn(null, "ai-eval-runner: eval session sign-out threw", { detail: err instanceof Error ? err.message : String(err) });
    }
  }
  const gradedCount = results.filter((r) => r.outcome === "graded").length;
  const infraCount  = results.length - gradedCount;

  // Heartbeat row -- always written, lets the dashboard prove the
  // runner is alive even when every fixture failed.
  /* ★A LIVENESS SIGNAL THAT CANNOT BE WRITTEN LOOKS EXACTLY LIKE A DEAD RUNNER (2026-09-09,
     unchecked-writes sweep). The comment above is right that this row must always be written - and the
     write's failure was discarded, so the one case it exists to distinguish (the runner IS alive, every
     fixture merely failed) would present to the dashboard as the runner being down. Reported, not thrown:
     the eval work itself already happened, and losing that report to a heartbeat problem would be worse. */
  const { error: hbErr } = await db.from("ai_quality_log").insert({
    agent_id:    "__heartbeat__",
    question_id: "__heartbeat__",
    score:       100,
    passed:      true,
    judge_model: "runner",
    outcome:     "heartbeat",
    run_id:      runId,
    run_at:      runAt,
    // alive is not the same as measured: the heartbeat carries what the run actually graded
    actual_answer: `graded=${gradedCount} infra_error=${infraCount} total=${totalCalls}`
      + (onlyAgent ? ` only=${onlyAgent}` : "") + (onlyIds ? ` ids=${onlyIds.size}` : ""),
  });
  if (hbErr) {
    console.error("ai-eval-runner: heartbeat row could not be written -", hbErr.message,
      "- the quality dashboard will read this runner as DOWN even though it completed");
  }

  // The judge calls are recorded one row per call by the request's model-call scope (serveObserved, LM-O
  // 2026-10-08) with the model that judged and the provider's token count. The aggregate row this wrote
  // ("callAI-chain", JUDGE_PROMPT x judgeCalls) would now be a second record of the same calls.

  return new Response(
    JSON.stringify({
      runner:       "ai-eval-runner",
      ran_at:       new Date().toISOString(),
      run_id:       runId,
      total:        totalCalls,
      graded:       gradedCount,
      // not a quality verdict: these fixtures were never answered (or never judged) - see infra_reason
      infra_failed: infraCount,
      passed:       results.filter((r) => r.outcome === "graded" && r.passed === true).length,
      failed:       results.filter((r) => r.outcome === "graded" && r.passed === false).length,
      identity:     evalSession ? "eval-account" : identityError,
      selection:    { only: onlyAgent, ids: onlyIds ? [...onlyIds] : null, offset, limit, of: queue.length },
      budget_ms:    RUN_BUDGET_MS,
      bench:        bench && {
        ready: bench.ready, rebuilt: bench.rebuilt, error: bench.error, breakdowns: bench.breakdowns,
        assets: Object.keys(bench.assets), projects: Object.keys(bench.projects),
      },
      // rows removed for the eval account/hive: before each fixture, and after the run (after_run)
      memory_reset: { calls: resetCalls, deleted: resetTotals, after_run: resetAfterRun, errors: resetErrors },
      latency_ms:   Date.now() - t0,
      results,
    }),
    { headers: { ...corsHeaders, "Content-Type": "application/json" } },
  );
}));
