/**
 * agent-golden-capture.spec.ts — Phase 8 §8.3 (Agent dimension live capture)
 *
 * Drives every unit in companion_agent_golden.json through the LIVE ai-gateway
 * `voice-action` route (-> voice-action-router) and captures the STRUCTURED route
 * decision (route_result.intents[0] -> {route:kind, params, confidence} + narration)
 * into a NORMALIZED observation map .tmp/agent_golden_observed.json, keyed by unit id:
 *     single/negative : { route, params, confidence, answer }
 *     multi-step      : [ <one observed per step> ]
 * That map is the input to `python tools/companion_agent_eval.py --observed`, whose
 * deterministic Tool-Correctness grader (companion_rigorous_grader.grade_agent_*) scores
 * it, after which 8.3 freezes the Agent baseline on the locked-test split.
 *
 * Mirrors companion-rigorous-flywheel.spec.ts (same sign-in fixture + in-browser fetch
 * so the JWT is the page's real local session). NO mocking: real edge fn, real LLM chain.
 * The grader stays independent (this spec only captures; Python grades).
 */
import { test, expect } from './_fixtures';
import * as fs from 'node:fs';
import * as path from 'node:path';

const GOLDEN_PATH = path.join(process.cwd(), 'companion_agent_golden.json');
const OUT_DIR = path.join(process.cwd(), '.tmp');
const OBSERVED_PATH = path.join(OUT_DIR, 'agent_golden_observed.json');
const RAW_PATH = path.join(OUT_DIR, 'agent_golden_raw.json');

interface Step { transcript: string; expected_route?: string | null; }
interface Unit {
  id: string;
  transcript?: string;
  steps?: Step[];
  category?: string;
}
interface Golden {
  single_turn?: Unit[];
  multi_step?: Unit[];
  negative_controls?: Unit[];
}

/** Live ai-gateway call (voice-action route) from inside the page context — real session JWT. */
async function callVoiceAction(page: any, message: string, hive_id: string | null) {
  return await page.evaluate(async ({ message, hive_id }: any) => {
    const t0 = performance.now();
    try {
      const SUPABASE_URL = 'http://127.0.0.1:54321';
      const SUPABASE_KEY = 'sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ';
      let accessToken: string | null = null;
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.startsWith('sb-') && key.endsWith('-auth-token')) {
          try {
            const parsed = JSON.parse(localStorage.getItem(key) || 'null');
            accessToken = parsed?.access_token || parsed?.session?.access_token || parsed?.currentSession?.access_token || null;
            if (accessToken) break;
          } catch {}
        }
      }
      if (!accessToken) accessToken = SUPABASE_KEY;
      const resp = await fetch(`${SUPABASE_URL}/functions/v1/ai-gateway`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${accessToken}`, 'apikey': SUPABASE_KEY },
        body: JSON.stringify({ agent: 'voice-action', message, context: { persona: 'zaniah', lang: 'auto' }, hive_id }),
      });
      const latency_ms = Math.round(performance.now() - t0);
      const raw = await resp.text();
      let body: any = null;
      try { body = JSON.parse(raw); } catch { body = { raw }; }
      return { ok: resp.ok, status: resp.status, latency_ms, body };
    } catch (e: any) {
      return { ok: false, status: 0, latency_ms: Math.round(performance.now() - t0), body: { error: String(e?.message || e) } };
    }
  }, { message, hive_id });
}

/** route_result.intents[0] -> normalized observed {route, params, confidence, answer}.
 *  The gateway wraps its payload under `.data` ({ok, data:{answer, route_result, ...}, trace_id,
 *  model_chain, ...}), so unwrap that first — reading top-level returns nothing (the documented
 *  "gateway envelopes success under .data" behaviour). */
function normalize(body: any) {
  const data = body?.data || body || {};
  const rr = data?.route_result || {};
  const intent = Array.isArray(rr.intents) && rr.intents.length ? rr.intents[0] : null;
  return {
    route: intent ? (intent.kind ?? null) : null,
    params: intent ? (intent.params ?? {}) : {},
    confidence: intent ? (typeof intent.confidence === 'number' ? intent.confidence : null) : null,
    answer: String(data?.answer ?? rr.narration ?? ''),
  };
}

test.describe('Agent golden capture (Phase 8 §8.3)', () => {
  test.beforeAll(() => { fs.mkdirSync(OUT_DIR, { recursive: true }); });

  test('drive the Agent golden set through the live voice-action gateway', async ({ whPage }) => {
    test.setTimeout(20 * 60 * 1000); // ~22 calls x (LLM latency + 4s pacing)
    const golden = JSON.parse(fs.readFileSync(GOLDEN_PATH, 'utf8')) as Golden;

    await whPage.goto('/workhive/index.html');
    const hive_id = await whPage.evaluate(
      () => localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id'),
    );

    const observed: Record<string, any> = {};
    const raw: any[] = [];
    let okCount = 0, callCount = 0;

    const singles = [...(golden.single_turn || []), ...(golden.negative_controls || [])];
    for (const unit of singles) {
      const r = await callVoiceAction(whPage, unit.transcript || '', hive_id);
      callCount++; if (r.ok) okCount++;
      observed[unit.id] = normalize(r.body);
      raw.push({ id: unit.id, status: r.status, ok: r.ok, latency_ms: r.latency_ms, body: r.body });
      await whPage.waitForTimeout(4000);
    }

    for (const chain of (golden.multi_step || [])) {
      const obsSteps: any[] = [];
      for (const step of (chain.steps || [])) {
        const r = await callVoiceAction(whPage, step.transcript, hive_id);
        callCount++; if (r.ok) okCount++;
        obsSteps.push(normalize(r.body));
        raw.push({ id: chain.id, step: step.transcript, status: r.status, ok: r.ok, latency_ms: r.latency_ms, body: r.body });
        await whPage.waitForTimeout(4000);
      }
      observed[chain.id] = obsSteps;
    }

    fs.writeFileSync(OBSERVED_PATH, JSON.stringify(observed, null, 2));
    fs.writeFileSync(RAW_PATH, JSON.stringify({ hive_id, callCount, okCount, raw }, null, 2));
    console.log(`[agent-capture] ${okCount}/${callCount} calls ok -> ${OBSERVED_PATH}`);

    // Honest signal: only fail if the stack is broken (everything errored). Routing
    // accuracy is graded downstream by companion_agent_eval, not asserted here.
    expect(okCount, 'at least one voice-action call should succeed (else stack is down)').toBeGreaterThan(0);
  });
});
