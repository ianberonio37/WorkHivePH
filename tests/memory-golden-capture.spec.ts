/**
 * memory-golden-capture.spec.ts — Phase 8 §8.3 (Memory dimension live capture)
 *
 * Drives every unit in companion_memory_golden.json through the LIVE ai-gateway `assistant` route
 * (-> ai-orchestrator) as a 2-PHASE capture and records the recall answer + the agent_memory row
 * delta into a normalized observation map .tmp/memory_golden_observed.json keyed by unit id:
 *     { answer, persisted_rows }
 *
 * WHY 2-PHASE: the companion is stateless server-side — ai-gateway reloads agent_memory (last 10
 * turns + summary) on EVERY call BEFORE dispatching, and saveTurn persists each exchange after. So
 * for each unit we (1) send every `setup` message as its OWN gateway call (each persists a turn),
 * then (2) send `recall_question` as a SEPARATE call carrying ONLY the question — recall must come
 * from agent_memory, not from any transcript we pass. A companion that ignored memory_block would
 * fail every recall. Setup+recall are contiguous per unit so the unit's facts are inside the 10-turn
 * working-memory window at recall time; other units' turns are realistic distractors (LongMemEval).
 *
 * persisted_rows = the agent_memory turn-row count delta across the unit (diagnostic only; the
 * grader gates on end-to-end recall, which proves persistence by construction).
 *
 * Mirrors agent/rag-golden-capture.spec.ts (whPage real-session fixture, in-page fetch with the
 * page's real JWT, gateway payload unwrapped from `.data`). NO mocking: real edge fn, real LLM chain.
 * That map feeds `python tools/companion_memory_eval.py --observed`, after which 8.3 freezes the
 * Memory baseline on the locked-test split (only from a clean, non-rate-limited run).
 */
import { test, expect } from './_fixtures';
import { adminClient } from './_db-cleanup';
import * as fs from 'node:fs';
import * as path from 'node:path';

const GOLDEN_PATH = path.join(process.cwd(), 'companion_memory_golden.json');
const OUT_DIR = path.join(process.cwd(), '.tmp');
const OBSERVED_PATH = path.join(OUT_DIR, 'memory_golden_observed.json');
const RAW_PATH = path.join(OUT_DIR, 'memory_golden_raw.json');

const PACING_MS = 4000;

/** Reset the ephemeral local rate-limit counters + response cache. The Memory eval measures RECALL,
 *  not rate-limiting; on free-tier the heavy ai-orchestrator fan-out fills the ~25/window bucket
 *  mid-run and the gateway then 429s (or serves ai-cache), masking the memory signal. Resetting the
 *  local infra counters between units keeps every recall ungated + uncached so the captured answer
 *  reflects live memory. Production is untouched (these are local ephemeral tables). Best-effort. */
async function resetAiCounters() {
  try {
    const db = adminClient();
    await db.from('ai_rate_limits').delete().neq('hive_id', '00000000-0000-0000-0000-000000000000');
    await db.from('ai_user_rate_limits').delete().neq('user_id', '__none__');
    await db.from('ai_cache').delete().neq('key', '__none__');
  } catch { /* ephemeral infra tables — non-fatal */ }
}

/** Live ai-gateway `assistant` call from inside the page context — real session JWT. */
async function callAssistant(page: any, message: string, hive_id: string | null) {
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
        body: JSON.stringify({ agent: 'assistant', message, context: { persona: 'zaniah', lang: 'auto' }, hive_id }),
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

/** Count this worker's assistant turn-rows via PostgREST with the page JWT (RLS scopes to the user).
 *  Returns null on any error so a count miss never corrupts the delta. */
async function memTurnCount(page: any): Promise<number | null> {
  return await page.evaluate(async () => {
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
      if (!accessToken) return null;
      const resp = await fetch(
        `${SUPABASE_URL}/rest/v1/agent_memory?agent_id=eq.assistant&kind=eq.turn&select=id`,
        { method: 'GET', headers: { 'apikey': SUPABASE_KEY, 'Authorization': `Bearer ${accessToken}`, 'Prefer': 'count=exact', 'Range': '0-0' } },
      );
      const cr = resp.headers.get('content-range') || '';
      const m = cr.match(/\/(\d+)\s*$/);
      return m ? parseInt(m[1], 10) : null;
    } catch { return null; }
  });
}

/** Gateway wraps success under `.data`; assistant is conversational, so the answer is data.answer. */
function answerOf(body: any): string {
  const data = body?.data || body || {};
  return String(data?.answer ?? data?.route_result?.answer ?? '');
}

test.describe('Memory golden capture (Phase 8 §8.3)', () => {
  // Heavy fan-out run trips the hive/user rate cap; clear the ephemeral counters so each call
  // grades cleanly (a rate-limited cache hit would make recall unprovable). Best-effort.
  test.beforeAll(async () => {
    fs.mkdirSync(OUT_DIR, { recursive: true });
    await resetAiCounters();
  });

  test('drive the Memory golden set through the live assistant gateway (2-phase)', async ({ whPage }) => {
    test.setTimeout(45 * 60 * 1000); // ~120 fan-out calls (49-unit golden) x (free-tier LLM latency + 4s pacing)
    const golden = JSON.parse(fs.readFileSync(GOLDEN_PATH, 'utf8'));
    const units: any[] = [...(golden.scripts || [])];

    await whPage.goto('/workhive/index.html');
    const hive_id = await whPage.evaluate(
      () => localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id'),
    );

    const observed: Record<string, any> = {};
    const raw: any[] = [];
    let okCount = 0, callCount = 0, rateLimited = 0;

    for (const unit of units) {
      // Reset the rate-limit/cache bucket before each unit so no recall is 429'd or cache-served.
      await resetAiCounters();
      const c0 = await memTurnCount(whPage);

      // Phase 1 — persist: each setup message is its own gateway call.
      for (const msg of (unit.setup || [])) {
        const r = await callAssistant(whPage, msg, hive_id);
        callCount++; if (r.ok) okCount++; if (r.status === 429) rateLimited++;
        raw.push({ id: unit.id, phase: 'setup', msg, status: r.status, ok: r.ok, latency_ms: r.latency_ms, body: r.body });
        await whPage.waitForTimeout(PACING_MS);
      }

      // Phase 2 — recall: a fresh call carrying ONLY the question. Recall must come from agent_memory.
      const rr = await callAssistant(whPage, unit.recall_question, hive_id);
      callCount++; if (rr.ok) okCount++; if (rr.status === 429) rateLimited++;
      const c1 = await memTurnCount(whPage);

      observed[unit.id] = {
        answer: answerOf(rr.body),
        persisted_rows: (c0 != null && c1 != null) ? (c1 - c0) : null,
      };
      raw.push({ id: unit.id, phase: 'recall', question: unit.recall_question, status: rr.status, ok: rr.ok,
                 latency_ms: rr.latency_ms, persisted_delta: observed[unit.id].persisted_rows, body: rr.body });
      await whPage.waitForTimeout(PACING_MS);
    }

    fs.writeFileSync(OBSERVED_PATH, JSON.stringify(observed, null, 2));
    fs.writeFileSync(RAW_PATH, JSON.stringify({ hive_id, callCount, okCount, rateLimited, total: units.length, raw }, null, 2));
    console.log(`[memory-capture] ${okCount}/${callCount} calls ok (${rateLimited} rate-limited) -> ${OBSERVED_PATH}`);
    if (rateLimited > 0) {
      console.warn(`[memory-capture] ${rateLimited} calls were rate-limited — do NOT freeze a baseline from this run (reset counters + re-run).`);
    }

    expect(okCount, 'at least one assistant call should succeed (else stack/route is down)').toBeGreaterThan(0);
  });
});
