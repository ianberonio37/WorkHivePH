/**
 * journey-agent-memory.spec.ts — Phase 7 of AGENTIC_RAG_ROADMAP.md.
 * Probes the agent-memory-store recall + store contract. SKIPs if not deployed.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';

const HOST = '/workhive/voice-journal.html';
const FN   = '/functions/v1/agent-memory-store';

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

const skip = (r: any) => r.status === 404 || r.status === 0;

test.describe('agent-memory-store — Phase 7 of AGENTIC_RAG_ROADMAP.md', () => {

  test('missing op → 400', async ({ whPage }) => {
    await whPage.goto(HOST); await waitForPageReady(whPage);
    const r = await invoke(whPage, { hive_id: '586fd158-42d1-4853-a406-64a4695e71c4' });
    test.skip(skip(r), 'fn not deployed');
    expect(r.status).toBe(400);
  });

  test('invalid op → 400', async ({ whPage }) => {
    await whPage.goto(HOST); await waitForPageReady(whPage);
    const r = await invoke(whPage, { op: 'delete', hive_id: '586fd158-42d1-4853-a406-64a4695e71c4' });
    test.skip(skip(r), 'fn not deployed');
    expect(r.status).toBe(400);
  });

  test('missing hive_id AND worker_name → 400', async ({ whPage }) => {
    await whPage.goto(HOST); await waitForPageReady(whPage);
    const r = await invoke(whPage, { op: 'recall' });
    test.skip(skip(r), 'fn not deployed');
    expect(r.status).toBe(400);
  });

  test('recall happy path: returns { ok, memories: [] } shape', async ({ whPage }) => {
    await whPage.goto(HOST); await waitForPageReady(whPage);
    const r = await invoke(whPage, { op: 'recall', hive_id: '586fd158-42d1-4853-a406-64a4695e71c4', limit: 5 });
    test.skip(skip(r), 'fn not deployed');
    expect(r.status).toBe(200);
    expect(r.body.ok).toBe(true);
    expect(Array.isArray(r.body.memories)).toBe(true);
  });

  test('store rejects payload with no memories', async ({ whPage }) => {
    await whPage.goto(HOST); await waitForPageReady(whPage);
    const r = await invoke(whPage, { op: 'store', hive_id: '586fd158-42d1-4853-a406-64a4695e71c4', memories: [] });
    test.skip(skip(r), 'fn not deployed');
    // Returns 500 with no-valid-memories error per the edge fn contract
    expect([400, 500]).toContain(r.status);
  });

});
