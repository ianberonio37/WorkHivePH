/**
 * ai-eval-runner -- LLM-as-judge runner for canonical-question fixtures.
 *
 * Invoked nightly at 03:30 UTC by the `ai-eval-daily` pg_cron job
 * (registered in 20260511000006_ai_quality_log.sql). For each fixture:
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
 * AI_ASSET_VERSION: 1
 * C5 (Self-Improving Gate) — bump this integer whenever JUDGE_PROMPT,
 * judge model id, score rubric, or pass-threshold changes. C2's eval
 * gate scores against this judge's verdicts, so an unannounced edit
 * here invalidates baselines. The ai-asset-versioning validator FAILs
 * if the file hash moves without this bumping. Owner: AI Engineer.
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

// contract-allow: eval harness; runs fixtures through ai-gateway
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";
import { log } from "../_shared/logger.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
import { callAI } from "../_shared/ai-chain.ts";
import { logAICost, estimateTokens } from "../_shared/cost-log.ts";

// Module-scope warm client.
const _WH_SUPABASE_URL_M = Deno.env.get("SUPABASE_URL") || "";
const _WH_SERVICE_KEY_M  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const _whWarmClient = _WH_SUPABASE_URL_M && _WH_SERVICE_KEY_M
  ? createClient(_WH_SUPABASE_URL_M, _WH_SERVICE_KEY_M)
  : null;
void _whWarmClient;

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
      question: "What is the status of project PRJ-001?",
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
): Promise<{ score: number; passed: boolean; missing: string[]; failure_reason: string | null }> {
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
    };
  }
}

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
  const SERVICE_KEY  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
  if (!SUPABASE_URL || !SERVICE_KEY) {
    return new Response(
      JSON.stringify({ error: "ai-eval-runner: missing service env" }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  }
  const db = _whWarmClient || createClient(SUPABASE_URL, SERVICE_KEY);

  const t0 = Date.now();
  const results: Array<{ agent_id: string; question_id: string; passed: boolean; score: number }> = [];
  let totalCalls = 0;

  for (const [agentId, fixtures] of Object.entries(FIXTURES)) {
    for (const fixture of fixtures) {
      totalCalls++;
      let actualAnswer = "";
      try {
        const gwUrl = `${SUPABASE_URL}/functions/v1/ai-gateway`;
        const res = await fetch(gwUrl, {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${SERVICE_KEY}`,
            "Content-Type":  "application/json",
          },
          body: JSON.stringify({
            agent:   agentId,
            message: fixture.question,
            context: fixture.context || {},
            // Internal eval -- skip rate-limit + memory-write side effects.
            _eval:   true,
          }),
        });
        if (!res.ok) {
          actualAnswer = `[gateway error: ${res.status}]`;
        } else {
          const j = await res.json();
          actualAnswer = String(j?.answer || "");
        }
      } catch (err) {
        actualAnswer = `[gateway threw: ${err instanceof Error ? err.message : String(err)}]`;
      }

      const judged = await judgeAnswer(
        fixture.question,
        fixture.expected_keywords,
        actualAnswer,
      );

      const { error: logErr } = await db.from("ai_quality_log").insert({
        agent_id:          agentId,
        question_id:       fixture.id,
        question_text:     fixture.question,
        expected_keywords: fixture.expected_keywords,
        actual_answer:     actualAnswer.slice(0, 4000),
        score:             judged.score,
        passed:            judged.passed,
        judge_model:       "callAI-chain",
        failure_reason:    judged.failure_reason,
      });
      if (logErr) log.warn(null, "ai_quality_log insert failed:", { detail: logErr.message });

      results.push({
        agent_id:    agentId,
        question_id: fixture.id,
        passed:      judged.passed,
        score:       judged.score,
      });
    }
  }

  // Heartbeat row -- always written, lets the dashboard prove the
  // runner is alive even when every fixture failed.
  await db.from("ai_quality_log").insert({
    agent_id:    "__heartbeat__",
    question_id: "__heartbeat__",
    score:       100,
    passed:      true,
    judge_model: "runner",
  });

  // Log the runner's own AI cost for accounting (judge calls live here).
  await logAICost(db, {
    fn:            "ai-eval-runner",
    model:         "callAI-chain",
    prompt_tokens: estimateTokens(JUDGE_PROMPT) * totalCalls,
    output_tokens: estimateTokens(JSON.stringify(results)),
    latency_ms:    Date.now() - t0,
    status:        "success",
  });

  return new Response(
    JSON.stringify({
      runner:       "ai-eval-runner",
      ran_at:       new Date().toISOString(),
      total:        totalCalls,
      passed:       results.filter((r) => r.passed).length,
      failed:       results.filter((r) => !r.passed).length,
      latency_ms:   Date.now() - t0,
      results,
    }),
    { headers: { ...corsHeaders, "Content-Type": "application/json" } },
  );
});
