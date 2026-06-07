/**
 * rag-golden-capture.spec.ts — Phase 8 §8.3 (RAG dimension live capture)
 *
 * Drives every question in companion_rag_golden.json through the LIVE ai-gateway `asset-brain`
 * route (-> asset-brain-query) for the golden set's pinned asset, and captures the grounded
 * answer + citations (route_result.{answer, cited, narration}) into a normalized observation
 * map .tmp/rag_golden_observed.json keyed by unit id:
 *     { answer, cited: [{kind, index}], narration }
 * That map feeds `python tools/companion_rag_eval.py --observed`, whose Ragas-style grader scores
 * context recall/precision (from cited[]) + relevancy + faithfulness, after which 8.3 freezes the
 * RAG baseline on the locked-test split.
 *
 * Mirrors agent-golden-capture.spec.ts (same sign-in fixture + in-browser fetch, real session JWT,
 * gateway payload unwrapped from `.data`). NO mocking: real edge fn, real LLM chain.
 */
import { test, expect } from './_fixtures';
import * as fs from 'node:fs';
import * as path from 'node:path';

const GOLDEN_PATH = path.join(process.cwd(), 'companion_rag_golden.json');
const OUT_DIR = path.join(process.cwd(), '.tmp');
const OBSERVED_PATH = path.join(OUT_DIR, 'rag_golden_observed.json');
const RAW_PATH = path.join(OUT_DIR, 'rag_golden_raw.json');

async function callAssetBrain(page: any, question: string, asset_id: string, hive_id: string | null) {
  return await page.evaluate(async ({ question, asset_id, hive_id }: any) => {
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
        body: JSON.stringify({ agent: 'asset-brain', message: question, context: { asset_id, persona: 'zaniah', lang: 'auto' }, hive_id }),
      });
      const latency_ms = Math.round(performance.now() - t0);
      const raw = await resp.text();
      let body: any = null;
      try { body = JSON.parse(raw); } catch { body = { raw }; }
      return { ok: resp.ok, status: resp.status, latency_ms, body };
    } catch (e: any) {
      return { ok: false, status: 0, latency_ms: Math.round(performance.now() - t0), body: { error: String(e?.message || e) } };
    }
  }, { question, asset_id, hive_id });
}

/** Gateway wraps under `.data`; asset-brain's structured payload is route_result. */
function normalize(body: any) {
  const data = body?.data || body || {};
  const rr = data?.route_result || {};
  return {
    answer: String(data?.answer ?? rr.answer ?? ''),
    cited: Array.isArray(rr.cited) ? rr.cited : [],
    narration: String(rr.narration ?? ''),
  };
}

test.describe('RAG golden capture (Phase 8 §8.3)', () => {
  test.beforeAll(() => { fs.mkdirSync(OUT_DIR, { recursive: true }); });

  test('drive the RAG golden set through the live asset-brain gateway', async ({ whPage }) => {
    test.setTimeout(15 * 60 * 1000);
    const golden = JSON.parse(fs.readFileSync(GOLDEN_PATH, 'utf8'));
    const asset_id = golden.asset?.asset_id;
    expect(asset_id, 'golden set must pin an asset_id').toBeTruthy();

    await whPage.goto('/workhive/index.html');
    const hive_id = await whPage.evaluate(
      () => localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id'),
    );

    const units = [...(golden.questions || []), ...(golden.negative_controls || [])];
    const observed: Record<string, any> = {};
    const raw: any[] = [];
    let okCount = 0;

    for (const unit of units) {
      const r = await callAssetBrain(whPage, unit.question, asset_id, hive_id);
      if (r.ok) okCount++;
      observed[unit.id] = normalize(r.body);
      raw.push({ id: unit.id, status: r.status, ok: r.ok, latency_ms: r.latency_ms, body: r.body });
      await whPage.waitForTimeout(4000);
    }

    fs.writeFileSync(OBSERVED_PATH, JSON.stringify(observed, null, 2));
    fs.writeFileSync(RAW_PATH, JSON.stringify({ hive_id, asset_id, okCount, total: units.length, raw }, null, 2));
    console.log(`[rag-capture] ${okCount}/${units.length} calls ok -> ${OBSERVED_PATH}`);

    expect(okCount, 'at least one asset-brain call should succeed (else stack/route is down)').toBeGreaterThan(0);
  });
});
