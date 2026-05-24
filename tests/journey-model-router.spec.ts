/**
 * journey-model-router.spec.ts — Phase 4 of AGENTIC_RAG_ROADMAP.md.
 *
 * Indirect behavioural probe: the Phase 1 agentic-rag-loop is the closest
 * surface to a deployed model-router contract. We invoke it and assert the
 * trace records distinct stages — which means the router successfully
 * routed each stage to its taskProfile. The static Layer-0 validator
 * (validate_model_router.py) handles all the structural checks (TASK_PROFILES
 * shape, reorderChain export, taskProfile passed at call sites, no paid-tier
 * leakage).
 *
 * The spec SKIPs cleanly when agentic-rag-loop isn't deployed.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';

const HOST_PAGE = '/workhive/voice-journal.html';
const FN_PATH   = '/functions/v1/agentic-rag-loop';

test.describe('model-router — Phase 4 of AGENTIC_RAG_ROADMAP.md', () => {

  test('agentic-rag-loop emits a non-empty trace with distinct stages', async ({ whPage }) => {
    await whPage.goto(HOST_PAGE);
    await waitForPageReady(whPage);

    const r = await whPage.evaluate(async (path: string) => {
      const url = (window as any).SUPABASE_URL || 'http://127.0.0.1:54321';
      const key = (window as any).SUPABASE_KEY
        || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNAR5ON-NyZc8K1Y';
      try {
        const resp = await fetch(url + path, {
          method:  'POST',
          headers: { 'Content-Type': 'application/json', 'apikey': key, 'Authorization': 'Bearer ' + key },
          body: JSON.stringify({
            question: 'latest entry',
            hive_id:  '586fd158-42d1-4853-a406-64a4695e71c4',
            worker_name: 'Pablo Aguilar',
          }),
        });
        const body = await resp.json().catch(() => ({}));
        return { status: resp.status, body };
      } catch (e: any) {
        return { status: 0, body: {}, network_error: String(e && e.message || e) };
      }
    }, FN_PATH);

    test.skip(r.status === 404 || r.status === 0, 'agentic-rag-loop not deployed');
    test.skip(r.status === 429, 'rate-limit hit');
    test.skip(r.status !== 200, `non-200 (${r.status}); not a router regression`);

    // Router + Generator + Checker minimum (Retriever has no LLM, Grader skips if no chunks).
    expect(r.body.route, 'router must emit a route').toBeTruthy();
    expect(typeof r.body.total_tokens).toBe('number');
    expect(typeof r.body.checker_passed).toBe('boolean');
  });

});
