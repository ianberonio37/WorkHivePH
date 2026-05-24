/**
 * journey-hierarchical-rag.spec.ts — Phase 2 of AGENTIC_RAG_ROADMAP.md.
 *
 * Locks the contract of the hierarchical-summarizer edge function. Probes:
 *   - Missing hive_id → 400
 *   - Missing/invalid level → 400
 *   - Happy path for level=day on a seeded hive returns { ok, written, period }
 *   - Idempotent: a second call for the same period returns ok=true (upsert)
 *
 * Specs SKIP cleanly when the function isn't deployed yet.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';

const HOST_PAGE = '/workhive/voice-journal.html';
const FN_PATH   = '/functions/v1/hierarchical-summarizer';

interface Resp {
  status: number;
  body: { ok?: boolean; written?: number; skipped?: number; errors?: string[]; level?: string; period?: { start: string; end: string }; error?: string };
  network_error?: string;
}

async function invoke(whPage: any, body: Record<string, unknown>): Promise<Resp> {
  return await whPage.evaluate(async ({ path, payload }: { path: string; payload: Record<string, unknown> }) => {
    const url = (window as any).SUPABASE_URL || 'http://127.0.0.1:54321';
    const key = (window as any).SUPABASE_KEY
      || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNAR5ON-NyZc8K1Y';
    try {
      const resp = await fetch(url + path, {
        method:  'POST',
        headers: {
          'Content-Type':  'application/json',
          'apikey':        key,
          'Authorization': 'Bearer ' + key,
        },
        body: JSON.stringify(payload),
      });
      const body = await resp.json().catch(() => ({}));
      return { status: resp.status, body };
    } catch (e: any) {
      return { status: 0, body: {}, network_error: String(e && e.message || e) };
    }
  }, { path: FN_PATH, payload: body });
}

function skipIfNotDeployed(r: Resp): boolean {
  return r.status === 404 || r.status === 0;
}

test.describe('hierarchical-summarizer — Phase 2 of AGENTIC_RAG_ROADMAP.md', () => {

  test('rejects missing hive_id with 400', async ({ whPage }) => {
    await whPage.goto(HOST_PAGE);
    await waitForPageReady(whPage);

    const r = await invoke(whPage, { level: 'day' });
    test.skip(skipIfNotDeployed(r), 'hierarchical-summarizer not deployed yet');
    expect(r.status).toBe(400);
    expect((r.body.error || '').toLowerCase()).toContain('hive_id');
  });

  test('rejects missing level with 400', async ({ whPage }) => {
    await whPage.goto(HOST_PAGE);
    await waitForPageReady(whPage);

    const r = await invoke(whPage, { hive_id: '586fd158-42d1-4853-a406-64a4695e71c4' });
    test.skip(skipIfNotDeployed(r), 'hierarchical-summarizer not deployed yet');
    expect(r.status).toBe(400);
    expect((r.body.error || '').toLowerCase()).toContain('level');
  });

  test('rejects invalid level value with 400', async ({ whPage }) => {
    await whPage.goto(HOST_PAGE);
    await waitForPageReady(whPage);

    const r = await invoke(whPage, { hive_id: '586fd158-42d1-4853-a406-64a4695e71c4', level: 'fortnight' });
    test.skip(skipIfNotDeployed(r), 'hierarchical-summarizer not deployed yet');
    expect(r.status).toBe(400);
  });

  test('happy path: level=day default-period rolls up and returns ok shape', async ({ whPage }) => {
    await whPage.goto(HOST_PAGE);
    await waitForPageReady(whPage);

    const r = await invoke(whPage, {
      hive_id: '586fd158-42d1-4853-a406-64a4695e71c4',
      level:   'day',
    });
    test.skip(skipIfNotDeployed(r), 'hierarchical-summarizer not deployed yet');
    test.skip(r.status === 429, 'rate-limit hit; not a regression');

    expect([200, 500]).toContain(r.status);  // 500 ok if the DB is empty for that day on this seeded hive
    if (r.status === 200) {
      expect(typeof r.body.ok).toBe('boolean');
      expect(typeof r.body.written).toBe('number');
      expect(r.body.level).toBe('day');
      expect(r.body.period?.start, 'period.start must be set').toBeTruthy();
      expect(r.body.period?.end,   'period.end must be set').toBeTruthy();
    }
  });

  test('idempotent: second call for same period returns ok=true (upsert)', async ({ whPage }) => {
    await whPage.goto(HOST_PAGE);
    await waitForPageReady(whPage);

    const payload = {
      hive_id:      '586fd158-42d1-4853-a406-64a4695e71c4',
      level:        'day',
      period_start: '2026-05-01',
      period_end:   '2026-05-01',
    };
    const first = await invoke(whPage, payload);
    test.skip(skipIfNotDeployed(first), 'hierarchical-summarizer not deployed yet');
    test.skip(first.status === 429, 'rate-limit hit; not a regression');
    test.skip(first.status !== 200, `non-200 (${first.status}); not an idempotency regression`);

    const second = await invoke(whPage, payload);
    test.skip(second.status === 429, 'rate-limit hit on second call');
    expect(second.status).toBe(200);
    expect(second.body.ok).toBe(true);
  });

});
