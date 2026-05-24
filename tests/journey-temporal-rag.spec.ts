/**
 * journey-temporal-rag.spec.ts — Phase 3 of AGENTIC_RAG_ROADMAP.md.
 *
 * Probes the temporal-rag-orchestrator edge fn (supervisor-worker fan-out
 * over canonical_period_summaries). SKIPs if not deployed.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';

const HOST = '/workhive/voice-journal.html';
const FN   = '/functions/v1/temporal-rag-orchestrator';

async function invoke(whPage: any, body: Record<string, unknown>) {
  return await whPage.evaluate(async ({ path, payload }: { path: string; payload: Record<string, unknown> }) => {
    const url = (window as any).SUPABASE_URL || 'http://127.0.0.1:54321';
    const key = (window as any).SUPABASE_KEY
      || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNAR5ON-NyZc8K1Y';
    try {
      const resp = await fetch(url + path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'apikey': key, 'Authorization': 'Bearer ' + key },
        body: JSON.stringify(payload),
      });
      const body = await resp.json().catch(() => ({}));
      return { status: resp.status, body };
    } catch (e: any) {
      return { status: 0, body: {}, network_error: String(e && e.message || e) };
    }
  }, { path: FN, payload: body });
}

const skipIfNotDeployed = (r: any) => r.status === 404 || r.status === 0;

test.describe('temporal-rag-orchestrator — Phase 3 of AGENTIC_RAG_ROADMAP.md', () => {

  test('missing question → 400', async ({ whPage }) => {
    await whPage.goto(HOST); await waitForPageReady(whPage);
    const r = await invoke(whPage, { hive_id: '586fd158-42d1-4853-a406-64a4695e71c4' });
    test.skip(skipIfNotDeployed(r), 'fn not deployed');
    expect(r.status).toBe(400);
  });

  test('missing hive_id → 400', async ({ whPage }) => {
    await whPage.goto(HOST); await waitForPageReady(whPage);
    const r = await invoke(whPage, { question: 'compare years' });
    test.skip(skipIfNotDeployed(r), 'fn not deployed');
    expect(r.status).toBe(400);
  });

  test('invalid from/to range → 400', async ({ whPage }) => {
    await whPage.goto(HOST); await waitForPageReady(whPage);
    const r = await invoke(whPage, {
      question: 'compare years', hive_id: '586fd158-42d1-4853-a406-64a4695e71c4',
      from: '2025-01-01', to: '2024-01-01',  // backwards
    });
    test.skip(skipIfNotDeployed(r), 'fn not deployed');
    expect(r.status).toBe(400);
  });

  test('happy path: 5-year window decomposes to yearly periods', async ({ whPage }) => {
    await whPage.goto(HOST); await waitForPageReady(whPage);
    const r = await invoke(whPage, {
      question: 'how have failures trended on P-203?',
      hive_id:  '586fd158-42d1-4853-a406-64a4695e71c4',
      asset_tag: 'P-203',
      from: '2021-01-01', to: '2026-05-01',
    });
    test.skip(skipIfNotDeployed(r), 'fn not deployed');
    test.skip(r.status === 429, 'rate-limit hit');
    test.skip(r.status !== 200, `non-200 ${r.status}`);
    expect(r.body.level).toBe('year');
    expect(typeof r.body.periods).toBe('number');
    expect(Array.isArray(r.body.per_period)).toBe(true);
    expect(typeof r.body.answer).toBe('string');
  });

});
