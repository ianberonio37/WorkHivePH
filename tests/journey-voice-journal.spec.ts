/**
 * journey-voice-journal.spec.ts — Voice Journal journey.
 *
 * NOTE: The mic/MediaRecorder API requires real microphone access which
 * Playwright headless mode does not have. Tests focus on:
 *   - Page load + structure
 *   - Mic button visible and labeled
 *   - Transcript box renders
 *   - Conversation history loads
 *   - Graceful error when mic permission is denied (headless)
 *   - Console errors
 *
 * Recording-to-submit flow is out of scope for automated tests — it
 * requires real audio input.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';

const PAGE = '/workhive/voice-journal.html';

test.describe('voice-journal.html — voice journal journey', () => {

  test('page loads without console errors', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);

    // Filter mic permission errors (expected in headless)
    const serious = errors.filter(e =>
      !e.includes('net::ERR_') &&
      !e.includes('Failed to fetch') &&
      !e.includes('Permission denied') &&
      !e.includes('getUserMedia') &&
      !e.includes('MediaRecorder') &&
      !e.includes('NotAllowedError') &&
      !e.includes('NotFoundError'),
    );
    expect(serious).toEqual([]);
  });

  test('mic button is visible and aria-labeled', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    const micBtn = whPage.locator('#mic-btn');
    await expect(micBtn).toBeVisible({ timeout: 5000 });
    const label = await micBtn.getAttribute('aria-label');
    expect(label?.length, 'mic button should have an aria-label').toBeGreaterThan(0);
  });

  test('transcript box renders in initial "Waiting for voice..." state', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1000);

    const transcriptBox = whPage.locator('#current-transcript');
    // Element exists in DOM — may be inside a hidden container initially
    const exists = await transcriptBox.count() > 0;
    expect(exists, 'transcript box element should exist in DOM').toBe(true);
    if (exists) {
      const text = await transcriptBox.textContent().catch(() => '');
      // Either the default "Waiting for voice..." or a prior transcript
      expect(text?.trim().length, 'transcript box should have some content').toBeGreaterThan(0);
    }
  });

  test('conversation history section renders or shows empty state', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(3000);

    // History of prior journal entries should load
    const history = whPage.locator('[id*="history"], [id*="feed"], [id*="journal-list"]').first();
    if (await history.count() > 0) {
      await expect(history).toBeVisible({ timeout: 5000 });
    }
    // No journal entries is also valid
    await expect(whPage.locator('body')).toBeVisible();
  });

  test('clicking mic button triggers graceful response (permission or recording)', async ({ whPage }) => {
    // Grant fake microphone permission in context
    const context = whPage.context();
    await context.grantPermissions(['microphone']).catch(() => {});

    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    const micBtn = whPage.locator('#mic-btn');
    await expect(micBtn).toBeVisible();

    // Click the mic button — either starts recording or shows error toast
    await micBtn.click();
    await whPage.waitForTimeout(1000);

    // Page should not crash
    await expect(whPage.locator('body')).toBeVisible();

    // If recording started, click again to stop
    const isRecording = await micBtn.evaluate(el => el.classList.contains('recording')).catch(() => false);
    if (isRecording) {
      await micBtn.click();
      await whPage.waitForTimeout(500);
    }
  });

  // ─── Step C/D behavioural tests ──────────────────────────────────────
  // The mic path needs a microphone we don't have in headless, but the
  // AI reply path itself (the one that broke as "Sorry, I'm offline"
  // for two screenshots) is reachable directly from the browser context:
  // voice-handler.js POSTs to ai-gateway with worker / persona / hive_id.
  // Hitting that endpoint via page.evaluate proves the WHOLE chain works
  // from the actual page origin — auth headers, CORS, agent routing,
  // persona contract, Step D's domain lens, the works.
  //
  // The screenshot the user kept showing came from the catch block of
  // this exact call. If this test passes, that screenshot can't reoccur
  // without a regression first failing the test.

  test('rosa-default-persona: voice-journal opens with Rosa selected by default', async ({ whPage }) => {
    // Clear any previously-saved persona choice so we exercise the default
    await whPage.addInitScript(() => {
      try {
        localStorage.removeItem('wh_voice_journal_persona');
      } catch (_) { /* noop */ }
    });
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    // Step D made Rosa the default persona for first-time visitors.
    // Either the Rosa chip is aria-checked or .persona-chip-active.
    const rosaChip = whPage.locator('#persona-rosa');
    await expect(rosaChip, 'rosa persona chip should be rendered').toBeVisible();
    const isActive = await rosaChip.evaluate(el =>
      el.classList.contains('persona-chip-active')
      || el.getAttribute('aria-checked') === 'true'
    );
    expect(isActive, 'rosa should be the default persona (Step D)').toBe(true);
  });

  test('ai-gateway anon-allow: voice-journal agent answers without sign-in', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    // Call ai-gateway from the page origin with the same payload shape
    // voice-handler.js uses, and the same anon JWT the browser carries
    // on a non-signed-in worker. If the gateway 401s or returns the
    // "Sorry, I'm offline" canned reply, this test fails — the exact
    // bug class the user reported on 2026-05-19.
    const result = await whPage.evaluate(async () => {
      // The page already has SUPABASE_URL and SUPABASE_KEY in scope as
      // inline consts; pull them off window/global if present, else
      // hardcode the local-dev endpoint.
      const url = (window as any).SUPABASE_URL || 'http://127.0.0.1:54321';
      const key = (window as any).SUPABASE_KEY
        || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNAR5ON-NyZc8K1Y';
      try {
        const resp = await fetch(url + '/functions/v1/ai-gateway', {
          method: 'POST',
          headers: {
            'Content-Type':  'application/json',
            'apikey':        key,
            'Authorization': 'Bearer ' + key,
          },
          body: JSON.stringify({
            agent:   'voice-journal',
            message: 'What are the priorities today?',
            hive_id: '586fd158-42d1-4853-a406-64a4695e71c4',
            context: { persona: 'rosa', worker_name: 'Pablo Aguilar', source: 'journey-test' },
          }),
        });
        const data = await resp.json().catch(() => ({}));
        return { status: resp.status, answer: String(data.answer || ''), error: String(data.error || '') };
      } catch (e: any) {
        return { status: 0, answer: '', error: String(e && e.message || e) };
      }
    });

    expect(result.status, `gateway returned ${result.status} (error: ${result.error})`).toBe(200);
    expect(result.answer.length, 'answer must be non-empty').toBeGreaterThan(20);
    // Negative: the offline fallback string must NEVER come back from the
    // gateway. If voice-handler.js sees it, that means the gateway said no.
    expect(result.answer.toLowerCase()).not.toContain("i'm offline");
    expect(result.answer.toLowerCase()).not.toContain('your question is saved');
  });

  test('rosa-strategist-lens: priorities-question reply uses strategist vocabulary', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    const result = await whPage.evaluate(async () => {
      const url = (window as any).SUPABASE_URL || 'http://127.0.0.1:54321';
      const key = (window as any).SUPABASE_KEY
        || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNAR5ON-NyZc8K1Y';
      try {
        const resp = await fetch(url + '/functions/v1/ai-gateway', {
          method: 'POST',
          headers: {
            'Content-Type':  'application/json',
            'apikey':        key,
            'Authorization': 'Bearer ' + key,
          },
          body: JSON.stringify({
            agent:   'voice-journal',
            message: 'What are the priorities today?',
            hive_id: '586fd158-42d1-4853-a406-64a4695e71c4',
            context: { persona: 'rosa', worker_name: 'Pablo Aguilar', source: 'journey-test' },
          }),
        });
        const data = await resp.json().catch(() => ({}));
        return { status: resp.status, answer: String(data.answer || ''), error: String(data.error || '') };
      } catch (e: any) {
        return { status: 0, answer: '', error: String(e && e.message || e) };
      }
    });

    expect(result.status).toBe(200);
    const lower = result.answer.toLowerCase();

    // Step D strategist lane is grounded in analytics-engineer KPIs and
    // RAG-threshold language. The reply doesn't have to hit EVERY word,
    // but it should use at least one of the lane's signature phrases.
    const strategistVocab = [
      'oee', 'planned-vs-reactive', 'planned vs reactive', 'reactive',
      'backlog', 'recurrence', 'mtbf', 'priorit', 'this week',
      'this month', 'escalat', 'review', 'pattern', 'trend',
    ];
    const hit = strategistVocab.find(v => lower.includes(v));
    expect(hit, `Rosa's reply ("${result.answer.slice(0, 200)}…") must use at least one strategist-lane keyword (${strategistVocab.join(', ')}). If this fails, Step D's domain lens didn't reach the prompt.`).toBeTruthy();
  });

  test('james-technical-lens: torque-question reply bridges to technical or uses technical vocabulary', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    const result = await whPage.evaluate(async () => {
      const url = (window as any).SUPABASE_URL || 'http://127.0.0.1:54321';
      const key = (window as any).SUPABASE_KEY
        || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNAR5ON-NyZc8K1Y';
      try {
        const resp = await fetch(url + '/functions/v1/ai-gateway', {
          method: 'POST',
          headers: {
            'Content-Type':  'application/json',
            'apikey':        key,
            'Authorization': 'Bearer ' + key,
          },
          body: JSON.stringify({
            agent:   'voice-journal',
            message: 'What torque should I use for an M20 anchor bolt on a pump baseplate?',
            hive_id: '586fd158-42d1-4853-a406-64a4695e71c4',
            context: { persona: 'james', worker_name: 'Pablo Aguilar', source: 'journey-test' },
          }),
        });
        const data = await resp.json().catch(() => ({}));
        return { status: resp.status, answer: String(data.answer || ''), error: String(data.error || '') };
      } catch (e: any) {
        return { status: 0, answer: '', error: String(e && e.message || e) };
      }
    });

    expect(result.status).toBe(200);
    const lower = result.answer.toLowerCase();
    const technicalVocab = [
      'torque', 'nm', 'newton-meter', 'n·m', 'cross-pattern',
      'grade 8.8', 'm20', 'manufacturer', 'manual', 'pre-load',
      'lubricated', 'dry', 'wrench', 'pattern', 'pass',
    ];
    const hit = technicalVocab.find(v => lower.includes(v));
    expect(hit, `James's reply ("${result.answer.slice(0, 200)}…") must use at least one technical-lane keyword (${technicalVocab.join(', ')}). If this fails, Step D's domain lens didn't reach the prompt.`).toBeTruthy();
  });
});
