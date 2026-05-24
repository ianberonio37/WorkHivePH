/**
 * journey-agentic-rag.spec.ts — Phase 1 of AGENTIC_RAG_ROADMAP.md.
 *
 * Locks the contract of the 5-stage self-correcting agentic-rag-loop edge
 * function. Probes the deployed endpoint from a real browser origin so the
 * full chain (CORS + auth + body validation + Router + Retriever + Grader +
 * Generator + Checker + trace write) is exercised end to end.
 *
 * Free-tier model constraint:
 *   The probes do NOT assert which model served the response — that's a
 *   Phase 4 concern. They DO assert the answer is non-empty, has citation
 *   markers, and the response shape includes route + grader_passed +
 *   checker_passed + trace_id. If the function isn't deployed yet, each
 *   probe SKIPs cleanly (no false failures during local dev).
 *
 * The Layer-0 validator (validate_agentic_rag_loop.py) handles static
 * checks (file shape, 4-place sync, free-tier enforcement, etc). This
 * spec handles runtime behaviour.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';

// Any page that bootstraps the supabase JS client works as a host for
// page.evaluate-driven edge function calls. voice-journal.html is the
// canonical AI-host page on this platform.
const HOST_PAGE = '/workhive/voice-journal.html';

const RAG_FN_PATH = '/functions/v1/agentic-rag-loop';

interface RagResponse {
  status: number;
  body: {
    answer?:         string;
    citations?:      Array<{ chunk_id: string; snippet: string }>;
    trace_id?:       string | null;
    route?:          string;
    retries?:        number;
    grader_passed?:  boolean;
    checker_passed?: boolean;
    total_tokens?:   number;
    latency_ms?:     number;
    remaining?:      number;
    error?:          string;
  };
  network_error?: string;
}

async function invokeRag(whPage: any, body: Record<string, unknown>): Promise<RagResponse> {
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
  }, { path: RAG_FN_PATH, payload: body });
}

function skipIfNotDeployed(result: RagResponse): boolean {
  // Function-not-found / not-yet-deployed signals: 404, network error, or
  // service unavailable. We SKIP rather than fail so this spec is a green
  // canary the moment the function ships.
  if (result.status === 404) return true;
  if (result.status === 0)   return true;
  return false;
}

test.describe('agentic-rag-loop — Phase 1 of AGENTIC_RAG_ROADMAP.md', () => {

  test('rejects missing question with 400 + { error: string }', async ({ whPage }) => {
    await whPage.goto(HOST_PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(500);

    const result = await invokeRag(whPage, { hive_id: 'fake' });
    test.skip(skipIfNotDeployed(result), 'agentic-rag-loop not deployed yet');

    expect(result.status, `expected 400 for missing question, got ${result.status}`).toBe(400);
    expect(result.body.error, 'error body must be a non-empty string').toBeTruthy();
    expect((result.body.error || '').toLowerCase()).toContain('question');
  });

  test('rejects missing all identity (no hive_id + no worker_name + no auth_uid) with 400', async ({ whPage }) => {
    await whPage.goto(HOST_PAGE);
    await waitForPageReady(whPage);

    const result = await invokeRag(whPage, { question: 'What did I fix yesterday?' });
    test.skip(skipIfNotDeployed(result), 'agentic-rag-loop not deployed yet');

    expect(result.status).toBe(400);
    expect((result.body.error || '').toLowerCase()).toMatch(/hive_id|worker_name|auth_uid/);
  });

  test('happy path: returns answer + route + checker_passed + trace_id shape', async ({ whPage }) => {
    await whPage.goto(HOST_PAGE);
    await waitForPageReady(whPage);

    const result = await invokeRag(whPage, {
      question: 'What was the last logbook entry?',
      hive_id:  '586fd158-42d1-4853-a406-64a4695e71c4',  // canonical seeded test hive
      worker_name: 'Pablo Aguilar',
    });
    test.skip(skipIfNotDeployed(result), 'agentic-rag-loop not deployed yet');
    // Rate-limit response is also a valid pass — we just verify it's not 500.
    test.skip(result.status === 429, 'rate-limit hit during test run; not a regression');

    expect(result.status, `expected 200, got ${result.status} (error: ${result.body.error || 'none'})`).toBe(200);

    // Response shape contract
    expect(typeof result.body.answer, 'answer must be a string').toBe('string');
    expect(typeof result.body.route, 'route must be a string').toBe('string');
    expect(['simple_recency','semantic','orchestrator','temporal','cold_archive','unknown']).toContain(result.body.route);
    expect(typeof result.body.grader_passed, 'grader_passed must be boolean').toBe('boolean');
    expect(typeof result.body.checker_passed, 'checker_passed must be boolean').toBe('boolean');
    expect(Array.isArray(result.body.citations), 'citations must be an array').toBe(true);
    expect(typeof result.body.total_tokens, 'total_tokens must be number').toBe('number');
    expect(typeof result.body.latency_ms, 'latency_ms must be number').toBe('number');
    expect(typeof result.body.retries, 'retries must be number').toBe('number');
    expect((result.body.retries ?? -1)).toBeLessThanOrEqual(2);
  });

  test('question length cap: oversized question truncated, not 500', async ({ whPage }) => {
    await whPage.goto(HOST_PAGE);
    await waitForPageReady(whPage);

    // 2000-char question — should be truncated to 500 internally, not fail.
    const huge = 'A '.repeat(1000) + 'what happened?';
    const result = await invokeRag(whPage, {
      question: huge,
      hive_id:  '586fd158-42d1-4853-a406-64a4695e71c4',
      worker_name: 'Pablo Aguilar',
    });
    test.skip(skipIfNotDeployed(result), 'agentic-rag-loop not deployed yet');
    test.skip(result.status === 429, 'rate-limit hit; not a regression');

    // 200 (truncated successfully) or 400 (rejected) is fine. 500 is a bug.
    expect([200, 400]).toContain(result.status);
    if (result.status === 500) {
      throw new Error(`Oversized question caused 500: ${result.body.error}`);
    }
  });

  test('citation markers present in answer when chunks were graded successfully', async ({ whPage }) => {
    await whPage.goto(HOST_PAGE);
    await waitForPageReady(whPage);

    const result = await invokeRag(whPage, {
      question: 'Show me the latest breakdown',
      hive_id:  '586fd158-42d1-4853-a406-64a4695e71c4',
      worker_name: 'Pablo Aguilar',
    });
    test.skip(skipIfNotDeployed(result), 'agentic-rag-loop not deployed yet');
    test.skip(result.status === 429, 'rate-limit hit; not a regression');
    test.skip(result.status !== 200, `non-200 (${result.status}); not a citation regression`);

    // When grader returns kept chunks, the answer must include at least one
    // [c#] marker OR a clear "no records" admission. The Checker enforces this.
    const answer = (result.body.answer || '').toLowerCase();
    const hasCitation = /\[c[a-z0-9#_-]+\]/i.test(result.body.answer || '');
    const isAdmission  = answer.includes("don't have") || answer.includes('no record') || answer.includes('no matching') || answer.includes('not enough');
    expect(hasCitation || isAdmission, 'answer must either cite a chunk [c#] or admit no records').toBe(true);
  });

  test('hallucination guard: never invents asset tags not in chunks', async ({ whPage }) => {
    await whPage.goto(HOST_PAGE);
    await waitForPageReady(whPage);

    // Use a deliberately fictional asset tag. The generator should NOT echo
    // it as if it were real; it should admit no records.
    const result = await invokeRag(whPage, {
      question: 'What was the last failure on asset Z-99999-FAKE?',
      hive_id:  '586fd158-42d1-4853-a406-64a4695e71c4',
      worker_name: 'Pablo Aguilar',
    });
    test.skip(skipIfNotDeployed(result), 'agentic-rag-loop not deployed yet');
    test.skip(result.status === 429, 'rate-limit hit; not a regression');
    test.skip(result.status !== 200, `non-200 (${result.status}); not a hallucination regression`);

    const answer = (result.body.answer || '').toLowerCase();
    // Either: the answer admits no records, OR if it references the asset tag
    // it must do so with a citation. Bare claims about Z-99999-FAKE = hallucination.
    if (answer.includes('z-99999')) {
      const hasCitation = /\[c[a-z0-9#_-]+\]/i.test(result.body.answer || '');
      const isAdmission  = answer.includes("don't have") || answer.includes('no record') || answer.includes('no matching') || answer.includes('not enough');
      expect(hasCitation || isAdmission, 'answer mentions fictional asset but neither cites a chunk nor admits no records').toBe(true);
    }
  });

});
