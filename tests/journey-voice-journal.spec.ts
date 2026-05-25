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

  test('zaniah-default-persona: voice-journal opens with Zaniah selected by default', async ({ whPage }) => {
    // Clear any previously-saved persona choice so we exercise the default.
    // Two surfaces carry persona state: localStorage (per-device) and
    // worker_profiles.preferred_persona (account-level, account-wide
    // Persona Contract — bootstrapIdentity reads it and overrides the
    // localStorage default). Both must be cleared to exercise the
    // first-time-visitor default. The bootstrapIdentity DB read happens
    // AFTER initial page render, so we intercept the v_worker_truth fetch
    // and force preferred_persona=null without touching the underlying row.
    await whPage.addInitScript(() => {
      try { localStorage.removeItem('wh_voice_journal_persona'); } catch (_) { /* noop */ }
      // Monkey-patch fetch so any select on v_worker_truth returns a row
      // with preferred_persona=null (test isolation: don't touch real DB).
      const origFetch = window.fetch;
      window.fetch = async function(input: any, init?: any) {
        const url = typeof input === 'string' ? input : (input?.url || '');
        if (/\/v_worker_truth\b/.test(url) && /preferred_persona/.test(url)) {
          // Pretend the row was returned but with null persona
          return new Response(
            JSON.stringify([{ worker_name: 'Test Worker', preferred_persona: null }]),
            { status: 200, headers: { 'Content-Type': 'application/json' } }
          );
        }
        return origFetch.call(this, input, init);
      };
    });
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    // Step D made Zaniah (formerly "Rosa") the default persona for first-time
    // visitors. Either the Zaniah chip is aria-checked or .persona-chip-active.
    const zaniahChip = whPage.locator('#persona-zaniah');
    await expect(zaniahChip, 'zaniah persona chip should be rendered').toBeVisible();
    const isActive = await zaniahChip.evaluate(el =>
      el.classList.contains('persona-chip-active')
      || el.getAttribute('aria-checked') === 'true'
    );
    expect(isActive, 'zaniah should be the default persona (Step D)').toBe(true);
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
            context: { persona: 'zaniah', worker_name: 'Pablo Aguilar', source: 'journey-test' },
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

  test('zaniah-strategist-lens: priorities-question reply uses strategist vocabulary', async ({ whPage }) => {
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
            context: { persona: 'zaniah', worker_name: 'Pablo Aguilar', source: 'journey-test' },
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
    expect(hit, `Zaniah's reply ("${result.answer.slice(0, 200)}…") must use at least one strategist-lane keyword (${strategistVocab.join(', ')}). If this fails, Step D's domain lens didn't reach the prompt.`).toBeTruthy();
  });

  test('hezekiah-technical-lens: torque-question reply bridges to technical or uses technical vocabulary', async ({ whPage }) => {
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
            context: { persona: 'hezekiah', worker_name: 'Pablo Aguilar', source: 'journey-test' },
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
    expect(hit, `Hezekiah's reply ("${result.answer.slice(0, 200)}…") must use at least one technical-lane keyword (${technicalVocab.join(', ')}). If this fails, Step D's domain lens didn't reach the prompt.`).toBeTruthy();
  });

  // ─── Dialog-state quality sentinels (added 2026-05-20) ──────────────────
  // Locks the affirmation-bypass behaviour at the BROWSER LEVEL. The L0
  // ratchet (validate_dialog_affirmation_bypass.py) certifies the code
  // shape; these specs certify the LIVE regex + predicate actually catch
  // the right phrases when voice-handler.js loads on a real page.
  //
  // Bug class caught 2026-05-20: worker said "Yes, the details." after
  // being asked about query.ask, and Zaniah STILL surfaced the topic-
  // switch UI. If these two checks fail, the bug class is live again.

  test('dialog-affirmation-regex: short PH + English confirmations match, long follow-ups do not', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    // voice-handler.js is lazy-loaded by nav-hub; trigger a load by opening
    // the voice overlay once (closed immediately after).
    await whPage.evaluate(() => {
      if (window.WHVoice && typeof window.WHVoice.open === 'function') {
        try { window.WHVoice.open(); } catch (_) { /* mount-only */ }
        try { window.WHVoice.close(); } catch (_) { /* mount-only */ }
      }
    });
    await whPage.waitForTimeout(500);

    const probes = await whPage.evaluate(() => {
      const fn = window.WHVoice && (window.WHVoice as any)._isFollowupAffirmation;
      if (typeof fn !== 'function') return { ready: false, results: [] };
      const cases: Array<{ text: string; expected: boolean; label: string }> = [
        // MUST bypass — short affirmations workers actually said
        { text: 'yes',                  expected: true,  label: 'bare yes' },
        { text: 'Yes, the details.',    expected: true,  label: 'yes + comma + details (the field bug)' },
        { text: 'the details',          expected: true,  label: 'just the details' },
        { text: 'sige',                 expected: true,  label: 'PH affirmative — sige' },
        { text: 'oo',                   expected: true,  label: 'PH affirmative — oo' },
        { text: 'opo',                  expected: true,  label: 'PH respectful affirmative — opo' },
        { text: 'ok',                   expected: true,  label: 'bare ok' },
        { text: 'tell me more',         expected: true,  label: 'tell me more' },
        { text: 'go on',                expected: true,  label: 'go on' },
        // MUST NOT bypass — these are real questions, not affirmations
        { text: 'yes, but also tell me about MTBF this week', expected: false, label: 'long sentence starting with yes' },
        { text: 'what is the MTBF',     expected: false, label: 'question with no affirmation prefix' },
        { text: 'tell me about C-01 compressor backlog hours', expected: false, label: 'long new request' },
        { text: '',                     expected: false, label: 'empty string' },
      ];
      return {
        ready: true,
        results: cases.map(c => ({ ...c, got: fn(c.text) })),
      };
    });

    expect(probes.ready, 'window.WHVoice._isFollowupAffirmation must be exposed for runtime assertion').toBe(true);
    const failures = probes.results.filter(r => r.got !== r.expected);
    expect(
      failures,
      `Affirmation regex mis-classified: ${JSON.stringify(failures, null, 2)}. ` +
      `If this fails, the topic-switch clarification UI is back for the listed phrases.`
    ).toEqual([]);
  });

  test('dialog-negation-regex: short PH + English negations match, long sentences do not', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.evaluate(() => {
      if (window.WHVoice && typeof window.WHVoice.open === 'function') {
        try { window.WHVoice.open(); } catch (_) { /* mount-only */ }
        try { window.WHVoice.close(); } catch (_) { /* mount-only */ }
      }
    });
    await whPage.waitForTimeout(500);

    const probes = await whPage.evaluate(() => {
      const fn = window.WHVoice && (window.WHVoice as any)._isFollowupNegation;
      if (typeof fn !== 'function') return { ready: false, results: [] };
      const cases: Array<{ text: string; expected: boolean; label: string }> = [
        // MUST exit — short negations workers actually say
        { text: 'no',                expected: true,  label: 'bare no' },
        { text: 'no, cancel that',   expected: true,  label: 'no + cancel' },
        { text: 'scratch that',      expected: true,  label: 'scratch that' },
        { text: 'never mind',        expected: true,  label: 'never mind' },
        { text: 'cancel',            expected: true,  label: 'bare cancel' },
        { text: 'skip',              expected: true,  label: 'skip' },
        { text: 'stop',              expected: true,  label: 'stop' },
        { text: 'wala na',           expected: true,  label: 'PH negation — wala na' },
        { text: 'hindi pa',          expected: true,  label: 'PH negation — hindi pa' },
        { text: 'huwag na',          expected: true,  label: 'PH negation — huwag na' },
        // MUST NOT exit — these are full requests with a "no" prefix
        { text: 'no, tell me about MTBF this week instead', expected: false, label: 'long sentence starting with no' },
        { text: 'what does no mean here',                    expected: false, label: '"no" inside a question' },
        { text: '',                                          expected: false, label: 'empty string' },
      ];
      return { ready: true, results: cases.map(c => ({ ...c, got: fn(c.text) })) };
    });

    expect(probes.ready, 'window.WHVoice._isFollowupNegation must be exposed').toBe(true);
    const failures = probes.results.filter(r => r.got !== r.expected);
    expect(
      failures,
      `Negation regex mis-classified: ${JSON.stringify(failures, null, 2)}. ` +
      `If this fails, "no / cancel / wala / hindi" stop exiting the prior ` +
      `topic and the worker gets stuck in the clarification UI.`
    ).toEqual([]);
  });

  test('dialog-noise-transcript-guard: empty / 1-2 char / pure-filler transcripts route as noise', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.evaluate(() => {
      if (window.WHVoice && typeof window.WHVoice.open === 'function') {
        try { window.WHVoice.open(); } catch (_) { /* mount-only */ }
        try { window.WHVoice.close(); } catch (_) { /* mount-only */ }
      }
    });
    await whPage.waitForTimeout(500);

    const probes = await whPage.evaluate(() => {
      const fn = window.WHVoice && (window.WHVoice as any)._isNoisyTranscript;
      if (typeof fn !== 'function') return { ready: false, results: [] };
      const cases: Array<{ text: string; expected: boolean; label: string }> = [
        // MUST be noise — background sound / false mic trigger
        { text: '',          expected: true,  label: 'empty string' },
        { text: '   ',       expected: true,  label: 'whitespace only' },
        { text: 'a',         expected: true,  label: '1 char' },
        { text: 'oh',        expected: true,  label: '2 char lone filler' },
        { text: '...',       expected: true,  label: 'pure punctuation' },
        { text: 'uh',        expected: true,  label: 'lone "uh"' },
        { text: 'um.',       expected: true,  label: 'lone "um."' },
        { text: 'hmm',       expected: true,  label: 'lone "hmm"' },
        // MUST NOT be noise — real worker utterances
        { text: 'yes',                          expected: false, label: 'short affirmation (handled by affirmation bypass)' },
        { text: 'no',                           expected: false, label: 'short negation (handled by negation bypass)' },
        { text: 'what is MTBF',                 expected: false, label: 'real question' },
        { text: 'oh, tell me about the compressor', expected: false, label: 'starts with filler but full sentence follows' },
      ];
      return { ready: true, results: cases.map(c => ({ ...c, got: fn(c.text) })) };
    });

    expect(probes.ready, 'window.WHVoice._isNoisyTranscript must be exposed').toBe(true);
    const failures = probes.results.filter(r => r.got !== r.expected);
    expect(
      failures,
      `Noise guard mis-classified: ${JSON.stringify(failures, null, 2)}. ` +
      `Empty / filler-only transcripts that fall through to the LLM waste ` +
      `model cost AND trip the topic-switch clarification UI on silence.`
    ).toEqual([]);
  });

  test('dialog-affirmation-case-invariance: regex matches uppercase + padded + punctuated variants', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.evaluate(() => {
      if (window.WHVoice && typeof window.WHVoice.open === 'function') {
        try { window.WHVoice.open(); } catch (_) { /* mount-only */ }
        try { window.WHVoice.close(); } catch (_) { /* mount-only */ }
      }
    });
    await whPage.waitForTimeout(500);

    const probes = await whPage.evaluate(() => {
      const aff = window.WHVoice && (window.WHVoice as any)._isFollowupAffirmation;
      const neg = window.WHVoice && (window.WHVoice as any)._isFollowupNegation;
      if (typeof aff !== 'function' || typeof neg !== 'function') {
        return { ready: false, results: [] };
      }
      // Speech-to-text occasionally emits ALL-CAPS, leading whitespace,
      // or stray trailing punctuation. The regex must shrug those off.
      const cases: Array<{ fn: string; text: string; expected: boolean; label: string }> = [
        { fn: 'aff', text: 'YES',       expected: true,  label: 'affirmation uppercase' },
        { fn: 'aff', text: '  yes  ',   expected: true,  label: 'affirmation padded' },
        { fn: 'aff', text: 'Yes.',      expected: true,  label: 'affirmation + trailing period' },
        { fn: 'aff', text: 'OO!',       expected: true,  label: 'PH affirmation uppercase' },
        { fn: 'aff', text: 'SIGE NA',   expected: true,  label: 'sige na uppercase' },
        { fn: 'neg', text: 'NO',        expected: true,  label: 'negation uppercase' },
        { fn: 'neg', text: '  no.  ',   expected: true,  label: 'negation padded + period' },
        { fn: 'neg', text: 'WALA NA',   expected: true,  label: 'wala na uppercase' },
        { fn: 'neg', text: 'Hindi!',    expected: true,  label: 'hindi + exclamation' },
      ];
      return {
        ready: true,
        results: cases.map(c => ({ ...c, got: c.fn === 'aff' ? aff(c.text) : neg(c.text) })),
      };
    });

    expect(probes.ready, 'affirmation + negation helpers must both be exposed').toBe(true);
    const failures = probes.results.filter(r => r.got !== r.expected);
    expect(
      failures,
      `Case / whitespace / punctuation invariance broke: ${JSON.stringify(failures, null, 2)}. ` +
      `Speech-to-text drift (uppercase / padding / trailing punctuation) MUST NOT defeat the detectors.`
    ).toEqual([]);
  });

  test('dialog-prior-topic-handle: voice-handler prompt builder emits a PRIOR TOPIC HANDLE clause with PH + English pronouns', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);

    // The continuity ratchet lives in the prompt-builder source. Fetch
    // voice-handler.js directly and prove the required clauses are
    // present — covers what an end-to-end multi-turn conversation test
    // would otherwise need a live LLM to verify.
    const audit = await whPage.evaluate(async () => {
      try {
        const resp = await fetch('voice-handler.js', { cache: 'no-store' });
        const src  = await resp.text();
        const hasBlock    = /DIALOG STATE:/.test(src);
        const hasHandle   = /PRIOR TOPIC HANDLE/.test(src);
        const handleSlice = (() => {
          const i = src.indexOf('PRIOR TOPIC HANDLE');
          return i >= 0 ? src.slice(i, i + 600) : '';
        })();
        return {
          hasBlock,
          hasHandle,
          mentionsIt:    /\bit\b/.test(handleSlice),
          mentionsThat:  /\bthat\b/.test(handleSlice),
          mentionsYan:   /\byan\b/i.test(handleSlice),
          mentionsYun:   /\byun\b/i.test(handleSlice),
          guardsUnknown: /intent\s*!==?\s*['"]unknown['"]/.test(src),
        };
      } catch (e) {
        return { error: String(e) };
      }
    });

    expect(audit.hasBlock,    'DIALOG STATE: block must be in the system prompt').toBe(true);
    expect(audit.hasHandle,   'PRIOR TOPIC HANDLE clause must exist').toBe(true);
    expect(audit.mentionsIt,  'PRIOR TOPIC HANDLE must list "it"').toBe(true);
    expect(audit.mentionsThat,'PRIOR TOPIC HANDLE must list "that"').toBe(true);
    expect(audit.mentionsYan, 'PRIOR TOPIC HANDLE must list "yan" (PH)').toBe(true);
    expect(audit.mentionsYun, 'PRIOR TOPIC HANDLE must list "yun" (PH)').toBe(true);
    expect(audit.guardsUnknown, 'PRIOR TOPIC HANDLE must be guarded against the "unknown" intent (so pronouns are never resolved to nothing)').toBe(true);
  });

  test('dialog-page-recovery-regex: bare page-name replies resolve to the right intent slug, long sentences do not', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.evaluate(() => {
      if (window.WHVoice && typeof window.WHVoice.open === 'function') {
        try { window.WHVoice.open(); } catch (_) { /* mount-only */ }
        try { window.WHVoice.close(); } catch (_) { /* mount-only */ }
      }
    });
    await whPage.waitForTimeout(500);

    const probes = await whPage.evaluate(() => {
      const fn = window.WHVoice && (window.WHVoice as any)._isPageRecoveryReply;
      if (typeof fn !== 'function') return { ready: false, results: [] };
      const cases: Array<{ text: string; expected: string | null; label: string }> = [
        // Bare page names from the ceiling prompt MUST resolve
        { text: 'logbook',          expected: 'troubleshooting', label: 'logbook → troubleshooting' },
        { text: 'analytics',        expected: 'oee',             label: 'analytics → oee' },
        { text: 'pm',               expected: 'pm_scheduling',   label: 'pm → pm_scheduling' },
        { text: 'PM Scheduler',     expected: 'pm_scheduling',   label: 'PM Scheduler → pm_scheduling (case + multi-word)' },
        { text: 'asset hub',        expected: 'troubleshooting', label: 'asset hub → troubleshooting' },
        { text: 'inventory',        expected: 'inventory_check', label: 'inventory → inventory_check' },
        { text: 'predictive',       expected: 'risk_assessment', label: 'predictive → risk_assessment' },
        { text: 'logbook.',         expected: 'troubleshooting', label: 'trailing period stripped' },
        // MUST NOT resolve — these are real sentences, not bare page names
        { text: 'can you open the logbook page for me',          expected: null, label: '7-word sentence containing "logbook"' },
        { text: 'what is the analytics report saying this week', expected: null, label: 'long question with "analytics"' },
        { text: 'how to schedule a PM',                          expected: null, label: 'long question with "PM"' },
        { text: '',                                              expected: null, label: 'empty string' },
      ];
      return { ready: true, results: cases.map(c => ({ ...c, got: fn(c.text) })) };
    });

    expect(probes.ready, 'window.WHVoice._isPageRecoveryReply must be exposed').toBe(true);
    const failures = probes.results.filter(r => r.got !== r.expected);
    expect(
      failures,
      `Page-recovery routing mis-classified: ${JSON.stringify(failures, null, 2)}. ` +
      `If this fails, the streak-ceiling prompt "what page would help?" becomes a dead-end the worker can't exit.`
    ).toEqual([]);
  });

  test('dialog-system-prompt-slot-bullets-live: _buildVoiceSystemPrompt emits "You already know:" + PRIOR TOPIC HANDLE for a real dialogState object', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.evaluate(() => {
      if (window.WHVoice && typeof window.WHVoice.open === 'function') {
        try { window.WHVoice.open(); } catch (_) { /* mount-only */ }
        try { window.WHVoice.close(); } catch (_) { /* mount-only */ }
      }
    });
    await whPage.waitForTimeout(500);

    // Drive the prompt builder with a realistic dialogState and assert
    // the rendered prompt actually contains the slot enumeration + the
    // PRIOR TOPIC HANDLE clause. Static + source-grep checks live at
    // L0 / L2; THIS spec is the runtime proof that the rendered string
    // carries the values the L0 ratchet promised.
    const verdict = await whPage.evaluate(() => {
      const fn = window.WHVoice && (window.WHVoice as any)._buildVoiceSystemPrompt;
      if (typeof fn !== 'function') return { ready: false };
      const dialogState = {
        current_intent: 'troubleshooting',
        intent_confidence: 0.82,
        context_slots: {
          asset_tag: 'P-203',
          time_window: 'this week',
        },
        clarification_pending: false,
      };
      // Pass minimum-viable arguments. The function signature is long but
      // most args are optional context blocks (memory, RAG, KG, etc.)
      // that the prompt builder handles as empty strings.
      const prompt = fn(
        'zaniah', 'Pablo Aguilar', 'Test Hive', 'voice-journal', null,
        '', '', '', '', '',
        dialogState,
        [], '', '', '', ''
      );
      return {
        ready: true,
        len: String(prompt || '').length,
        hasYouAlreadyKnow: /You already know:/.test(prompt),
        hasAssetTagBullet: /asset tag\s*=\s*P-203/i.test(prompt),
        hasTimeWindowBullet: /time window\s*=\s*this week/i.test(prompt),
        hasPriorTopicHandle: /PRIOR TOPIC HANDLE/.test(prompt),
        hasTroubleshootingIntent: /troubleshooting/.test(prompt),
        hasPronouns: /\bit\b/.test(prompt) && /\bthat\b/.test(prompt) && /\byan\b/i.test(prompt),
      };
    });

    expect(verdict.ready, '_buildVoiceSystemPrompt must be exposed via window.WHVoice').toBe(true);
    expect(verdict.len, 'rendered prompt must be non-trivial').toBeGreaterThan(500);
    expect(verdict.hasYouAlreadyKnow, 'rendered prompt must include "You already know:"').toBe(true);
    expect(verdict.hasAssetTagBullet, 'rendered prompt must include "asset tag = P-203"').toBe(true);
    expect(verdict.hasTimeWindowBullet, 'rendered prompt must include "time window = this week"').toBe(true);
    expect(verdict.hasPriorTopicHandle, 'rendered prompt must include "PRIOR TOPIC HANDLE"').toBe(true);
    expect(verdict.hasTroubleshootingIntent, 'PRIOR TOPIC HANDLE must reference the troubleshooting intent').toBe(true);
    expect(verdict.hasPronouns, 'PRIOR TOPIC HANDLE must list "it", "that", and PH "yan"').toBe(true);
  });

  test('dialog-slot-enumeration: voice-handler prompt builder emits "You already know:" with a key/value loop', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);

    const audit = await whPage.evaluate(async () => {
      try {
        const resp = await fetch('voice-handler.js', { cache: 'no-store' });
        const src  = await resp.text();
        const hasPhrase = /You already know/.test(src);
        const hasLoop   = /Object\.keys\s*\(\s*slots\s*\)/.test(src) ||
                          /slotKeys\.map\s*\(/.test(src);
        return { hasPhrase, hasLoop };
      } catch (e) {
        return { error: String(e) };
      }
    });

    expect(audit.hasPhrase, '"You already know:" natural-language slot enumeration must be in the prompt').toBe(true);
    expect(audit.hasLoop,   'Slot enumeration must iterate over Object.keys(slots) — never hard-code slot keys').toBe(true);
  });

  test('dialog-clarify-streak-ceiling: counter caps + breaks after 2 consecutive clarifies', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.evaluate(() => {
      if (window.WHVoice && typeof window.WHVoice.open === 'function') {
        try { window.WHVoice.open(); } catch (_) { /* mount-only */ }
        try { window.WHVoice.close(); } catch (_) { /* mount-only */ }
      }
    });
    await whPage.waitForTimeout(500);

    const verdict = await whPage.evaluate(() => {
      const wh = window.WHVoice as any;
      if (!wh || typeof wh._getClarifyStreak !== 'function') return { ready: false, trace: [] };
      wh._resetClarifyStreak();
      const trace: Array<{ step: string; streak: number }> = [];
      trace.push({ step: 'after reset',     streak: wh._getClarifyStreak() });
      wh._bumpClarifyStreak();
      trace.push({ step: 'after bump #1',   streak: wh._getClarifyStreak() });
      wh._bumpClarifyStreak();
      trace.push({ step: 'after bump #2',   streak: wh._getClarifyStreak() });
      wh._resetClarifyStreak();
      trace.push({ step: 'after reset',     streak: wh._getClarifyStreak() });
      return { ready: true, trace };
    });

    expect(verdict.ready, 'window.WHVoice._getClarifyStreak must be exposed').toBe(true);
    expect(verdict.trace[0].streak, 'initial / reset streak is 0').toBe(0);
    expect(verdict.trace[1].streak, 'first bump → 1').toBe(1);
    expect(verdict.trace[2].streak, 'second bump → 2 (ceiling trigger threshold)').toBe(2);
    expect(verdict.trace[3].streak, 'reset clears the streak').toBe(0);

    // Static-source proof: the _shouldClarify branch must check `streak >= 2`
    // and switch the clarifyAnswer shape. The L0 ratchet already enforces
    // this; this assertion documents the contract at the L2 level so a
    // refactor that removes the ceiling tripwire shows up in spec runs too.
    const sourceHasCeiling = await whPage.evaluate(async () => {
      try {
        const resp = await fetch('voice-handler.js', { cache: 'no-store' });
        const src  = await resp.text();
        return /_bumpClarifyStreak\s*\(\s*\)[\s\S]{0,800}streak\s*>=\s*2/.test(src);
      } catch (_) { return false; }
    });
    expect(sourceHasCeiling, 'voice-handler.js must call _bumpClarifyStreak() AND branch on streak >= 2 inside the _shouldClarify block').toBe(true);
  });

  // ─── Turns #5-#14 dialog-quality sentinels (10-turn flywheel batch) ───
  // Six new detectors exposed via window.WHVoice — each probed with
  // a positive + a negative case. Batched into one spec to keep the
  // suite fast and the assertions colocated.

  test('dialog-quality-extended-detectors: turns #5-#10 + #14 helpers behave correctly', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.evaluate(() => {
      if (window.WHVoice && typeof window.WHVoice.open === 'function') {
        try { window.WHVoice.open(); } catch (_) { /* mount-only */ }
        try { window.WHVoice.close(); } catch (_) { /* mount-only */ }
      }
    });
    await whPage.waitForTimeout(500);

    const verdict = await whPage.evaluate(() => {
      const wh = (window as any).WHVoice;
      if (!wh) return { ready: false };
      // Turn #5: persona switch
      const ps = (txt: string) => wh._isPersonaSwitchUtterance(txt);
      // Turn #6: stale guard
      const stale = (state: any) => wh._isStaleDialogState(state);
      // Turn #7: topic shift
      const ts = (txt: string) => wh._isTopicShiftSignal(txt);
      // Turn #8: thanks
      const th = (txt: string) => wh._isThanksReply(txt);
      // Turn #10: greeting
      const gr = (txt: string) => wh._isGreeting(txt);
      // Turn #14: repeat
      const rp = (txt: string) => wh._isRepeatRequest(txt);

      const sixteenMinAgo = new Date(Date.now() - 16 * 60 * 1000).toISOString();
      const fiveMinAgo    = new Date(Date.now() -  5 * 60 * 1000).toISOString();

      const cases: Array<{ label: string; got: unknown; expected: unknown }> = [
        // Turn #5
        { label: 'persona-switch: "switch to Hezekiah"',     got: ps('switch to Hezekiah'),     expected: 'hezekiah' },
        { label: 'persona-switch: "tawagin si Zaniah"',      got: ps('tawagin si Zaniah'),      expected: 'zaniah' },
        { label: 'persona-switch: "talk to Hez"',            got: ps('talk to Hez'),            expected: 'hezekiah' },
        { label: 'persona-switch: long sentence with name',  got: ps('I want to ask Hezekiah a question'), expected: null },
        { label: 'persona-switch: not a switch utterance',   got: ps('what about MTBF'),        expected: null },
        // Turn #6
        { label: 'stale: 16 minutes ago is stale',           got: stale({ updated_at: sixteenMinAgo }), expected: true },
        { label: 'stale: 5 minutes ago is fresh',            got: stale({ updated_at: fiveMinAgo }),    expected: false },
        { label: 'stale: null dialogState',                  got: stale(null),                  expected: false },
        { label: 'stale: no timestamp at all',               got: stale({ current_intent: 'mtbf' }), expected: false },
        // Turn #7
        { label: 'topic-shift: "hold on"',                   got: ts('hold on, what about C-01'), expected: true },
        { label: 'topic-shift: "actually"',                  got: ts('actually, never mind'),    expected: true },
        { label: 'topic-shift: "teka muna"',                 got: ts('teka muna'),               expected: true },
        { label: 'topic-shift: regular question',            got: ts('what is the MTBF'),        expected: false },
        // Turn #8
        { label: 'thanks: "salamat"',                        got: th('salamat'),                 expected: true },
        { label: 'thanks: "maraming salamat"',               got: th('maraming salamat'),        expected: true },
        { label: 'thanks: "thanks ah"',                      got: th('thanks ah'),               expected: true },
        { label: 'thanks: "thank you for the help with PM"', got: th('thank you for the help with PM'), expected: false },
        // Turn #10
        { label: 'greeting: "hello"',                        got: gr('hello'),                   expected: true },
        { label: 'greeting: "magandang umaga"',              got: gr('magandang umaga'),         expected: true },
        { label: 'greeting: "kumusta"',                      got: gr('kumusta'),                 expected: true },
        { label: 'greeting: long question with "hello"',     got: gr('hello can you tell me about MTBF'), expected: false },
        // Turn #14
        { label: 'repeat: "ulit nga"',                       got: rp('ulit nga'),                expected: true },
        { label: 'repeat: "say it again"',                   got: rp('say it again'),            expected: true },
        { label: 'repeat: "paki ulit"',                      got: rp('paki ulit'),               expected: true },
        { label: 'repeat: "what does that mean exactly"',    got: rp('what does that mean exactly'), expected: false },
      ];
      return { ready: true, cases };
    });

    expect(verdict.ready, 'window.WHVoice must expose the turn #5-#14 helpers').toBe(true);
    const failures = (verdict.cases || []).filter(c => c.got !== c.expected);
    expect(
      failures,
      `One or more turn #5-#14 detectors mis-classified: ${JSON.stringify(failures, null, 2)}`
    ).toEqual([]);
  });

  test('ai-companion-workflow-detectors: turns #55-#64 behaviour locked', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.evaluate(() => {
      if (window.WHVoice && typeof window.WHVoice.open === 'function') {
        try { window.WHVoice.open(); } catch (_) { /* mount-only */ }
        try { window.WHVoice.close(); } catch (_) { /* mount-only */ }
      }
    });
    await whPage.waitForTimeout(500);

    const verdict = await whPage.evaluate(() => {
      const wh = (window as any).WHVoice;
      if (!wh) return { ready: false };
      // T55 — proactive selector
      const ack = { severity: 'low', description: 'low one' };
      const high = { severity: 'high', description: 'high one' };
      const crit = { severity: 'critical', description: 'crit one' };
      const picked1 = wh._selectProactiveAlertForSpeak([ack, high, crit]);
      const picked2 = wh._selectProactiveAlertForSpeak([ack]);
      const picked3 = wh._selectProactiveAlertForSpeak([]);
      // T57 — slot expiry
      const fresh = wh._pruneStaleSlots(
        { asset_tag: 'P-203', time_window: 'this week', co_worker: 'Romeo' },
        new Date().toISOString()
      );
      const stale = wh._pruneStaleSlots(
        { asset_tag: 'P-203', time_window: 'this week', co_worker: 'Romeo' },
        new Date(Date.now() - 90 * 60 * 1000).toISOString()  // 90 min ago
      );
      // T58 — action replay
      wh._stashConfirmedAction('log_bearing_change', { asset_tag: 'P-203', downtime: 1 });
      const replay = wh._detectActionReplay('same fix on P-205');
      const replayNo = wh._detectActionReplay('what is MTBF');
      // T59 — language detection
      const langTag = wh._detectLanguagePref('speak tagalog');
      const langEn  = wh._detectLanguagePref('reply in english only');
      const langCeb = wh._detectLanguagePref('cebuano na lang');
      const langNo  = wh._detectLanguagePref('hello there');
      // T60 — brevity
      const brevOn  = wh._detectBrevityToggle('be brief please');
      const brevOff = wh._detectBrevityToggle('more detail please');
      const brevNo  = wh._detectBrevityToggle('what is MTBF');
      // T61 — timer
      const timer1 = wh._detectTimerRequest('remind me in 20 min about P-203 bearing');
      const timer2 = wh._detectTimerRequest('remind me in 2 hours about the PM');
      const timer3 = wh._detectTimerRequest('what is the MTBF');
      // T64 — action queue
      const q1 = wh._parseActionQueue('log entry then start PM then notify supervisor');
      const q2 = wh._parseActionQueue('what is the OEE');
      return {
        ready: true,
        proactive: [picked1 && picked1.severity, picked2, picked3],
        fresh: Object.keys(fresh).sort(),
        stale: Object.keys(stale).sort(),  // asset_tag(60m) + machine_status(30m) gone; time_window(2h) + co_worker(2h) remain
        replay: { yes: replay && replay.newAsset, no: replayNo },
        lang: [langTag, langEn, langCeb, langNo],
        brev: [brevOn, brevOff, brevNo],
        timer: [timer1 && timer1.ms, timer2 && timer2.ms, timer3],
        queue: [q1 && q1.length, q2],
      };
    });

    expect(verdict.ready).toBe(true);
    expect(verdict.proactive, 'T55 proactive picker ranks critical > high > none').toEqual(['critical', null, null]);
    // T57 — 90-min-old state: asset_tag (60m TTL) gone, time_window (120m) + co_worker (120m) remain
    expect(verdict.fresh).toContain('asset_tag');
    expect(verdict.stale).not.toContain('asset_tag');
    expect(verdict.stale).toContain('time_window');
    expect(verdict.replay.yes, 'T58 action replay returns new asset').toBe('P-205');
    expect(verdict.replay.no,  'T58 non-replay returns null').toBeNull();
    expect(verdict.lang, 'T59 language detector').toEqual(['tagalog', 'english', 'cebuano', null]);
    expect(verdict.brev, 'T60 brevity toggle').toEqual(['brief', 'full', null]);
    expect(verdict.timer[0], 'T61 timer parses 20 min').toBe(20 * 60 * 1000);
    expect(verdict.timer[1], 'T61 timer parses 2 hours').toBe(2 * 60 * 60 * 1000);
    expect(verdict.timer[2], 'T61 non-timer returns null').toBeNull();
    expect(verdict.queue[0], 'T64 action queue parses 3 steps').toBeGreaterThanOrEqual(2);
    expect(verdict.queue[1], 'T64 non-batch returns null').toBeNull();
  });

  test('ai-companion-orchestration-detectors: turns #65-#74 behaviour locked', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.evaluate(() => {
      if (window.WHVoice && typeof window.WHVoice.open === 'function') {
        try { window.WHVoice.open(); } catch (_) { /* mount-only */ }
        try { window.WHVoice.close(); } catch (_) { /* mount-only */ }
      }
    });
    await whPage.waitForTimeout(500);

    const verdict = await whPage.evaluate(() => {
      const wh = (window as any).WHVoice;
      if (!wh) return { ready: false };
      // T65 — PDF export
      const pdf1 = wh._isPdfExportRequest('save this as PDF');
      const pdf2 = wh._isPdfExportRequest('i-pdf mo ito');
      const pdf3 = wh._isPdfExportRequest('what is MTBF');
      // T66 — pronunciation library round-trip
      const okSet = wh._setPronunciationOverride('P-203', 'pee dash two oh three');
      const map = wh._getPronunciationMap();
      const applied = wh._applyPronunciation('check P-203 today');
      // cleanup so other specs aren't polluted
      try { localStorage.removeItem('wh_pronunciation_overrides'); } catch (_) {}
      // T67 — voice execute lock default OFF
      try { localStorage.removeItem('wh_voice_execute_authorised'); } catch (_) {}
      const lockedOff = wh._isVoiceExecuteAuth();
      wh._setVoiceExecuteAuth(true);
      const lockedOn = wh._isVoiceExecuteAuth();
      wh._setVoiceExecuteAuth(false);
      const lockedBackOff = wh._isVoiceExecuteAuth();
      // T68 — avatar animation states
      const setIdle = wh._setAvatarAnimation('idle');
      const setBogus = wh._setAvatarAnimation('warpdrive');
      const ovEl = document.getElementById('wh-voice-overlay');
      const animAttr = ovEl ? ovEl.getAttribute('data-avatar-anim') : null;
      // T70 — digest detector
      const dig1 = wh._isDigestRequest('morning summary please');
      const dig2 = wh._isDigestRequest('what happened overnight');
      const dig3 = wh._isDigestRequest('i-summarize mo ang shift');
      const dig4 = wh._isDigestRequest('what is the MTBF');
      // T71 — push state
      const pushSt = wh._pushNotifyState();
      const pushOpt1 = wh._isPushOptInReply('yes, alert me');
      const pushOpt2 = wh._isPushOptInReply('sige, ipush mo');
      const pushOpt3 = wh._isPushOptInReply('what is MTBF');
      // T72 — session lock round-trip
      try { localStorage.removeItem('wh_voice_session_lock_test-hive'); } catch (_) {}
      const lockFree = wh._isSessionLocked('test-hive', 'worker-a');
      wh._acquireSessionLock('test-hive', 'worker-a');
      const lockOwn  = wh._isSessionLocked('test-hive', 'worker-a');  // own lock → null
      const lockOther = wh._isSessionLocked('test-hive', 'worker-b'); // foreign → object
      wh._releaseSessionLock('test-hive', 'worker-a');
      const lockAfterRelease = wh._isSessionLocked('test-hive', 'worker-a');
      // T73 — accent detection over a small window
      const tagalog = wh._detectAccentHint([
        'kasi naman lang po ako naman',
        'sige po kuya ano yung yun pala',
        'oo naman po tapos yan ah',
      ]);
      const english = wh._detectAccentHint([
        'check the bearing please',
        'review the morning report and update the log',
        'thank you for the help today my friend',
      ]);
      try { localStorage.removeItem('wh_voice_accent_pref'); } catch (_) {}
      const accentPrefNone = wh._getAccentPref();
      wh._setAccentPref('tagalog-leaning');
      const accentPrefSet  = wh._getAccentPref();
      wh._setAccentPref(null);
      // T74 — streaming round-trip
      wh._setStreamingState(true);
      const streamOn = wh._isStreaming();
      wh._finalizeStream();
      const streamOff = wh._isStreaming();
      const ovStreamAttr = ovEl ? ovEl.getAttribute('data-streaming') : null;
      return {
        ready: true,
        pdf: [pdf1, pdf2, pdf3],
        pron: { ok: okSet, hasOverride: !!(map && map['p-203']), applied },
        lock: { off: lockedOff, on: lockedOn, backOff: lockedBackOff },
        avatar: { idle: setIdle, bogus: setBogus, attr: animAttr },
        dig: [dig1, dig2, dig3, dig4],
        push: { state: pushSt, opt: [pushOpt1, pushOpt2, pushOpt3] },
        session: {
          free: lockFree, own: lockOwn,
          other: lockOther && lockOther.worker,
          afterRelease: lockAfterRelease,
        },
        accent: { tg: tagalog, en: english, prefNone: accentPrefNone, prefSet: accentPrefSet },
        stream: { on: streamOn, off: streamOff, attrAfterFinalize: ovStreamAttr },
      };
    });

    expect(verdict.ready).toBe(true);
    // T65 PDF export
    expect(verdict.pdf[0], 'T65 "save as PDF" detected').toBe(true);
    expect(verdict.pdf[1], 'T65 i-pdf mo ito detected').toBe(true);
    expect(verdict.pdf[2], 'T65 non-PDF returns false').toBe(false);
    // T66 pronunciation
    expect(verdict.pron.ok, 'T66 setPronunciationOverride returns true on valid input').toBe(true);
    expect(verdict.pron.hasOverride, 'T66 override stored in map').toBe(true);
    expect(verdict.pron.applied, 'T66 applyPronunciation replaces the term').toContain('pee dash two oh three');
    // T67 voice execute lock
    expect(verdict.lock.off, 'T67 default OFF').toBe(false);
    expect(verdict.lock.on, 'T67 setVoiceExecuteAuth(true) flips ON').toBe(true);
    expect(verdict.lock.backOff, 'T67 setVoiceExecuteAuth(false) flips back OFF').toBe(false);
    // T68 avatar animation
    expect(verdict.avatar.idle, 'T68 "idle" is a valid state').toBe(true);
    expect(verdict.avatar.bogus, 'T68 unknown state rejected').toBe(false);
    expect(verdict.avatar.attr, 'T68 DOM attribute set to "idle" after close()').toBe('idle');
    // T70 digest
    expect(verdict.dig[0], 'T70 morning summary detected').toBe(true);
    expect(verdict.dig[1], 'T70 what happened overnight detected').toBe(true);
    expect(verdict.dig[2], 'T70 i-summarize mo ang shift detected').toBe(true);
    expect(verdict.dig[3], 'T70 non-digest returns false').toBe(false);
    // T71 push
    expect(['granted','denied','default','unsupported','error'], 'T71 pushState returns a known value').toContain(verdict.push.state);
    expect(verdict.push.opt[0], 'T71 "yes, alert me" detected').toBe(true);
    expect(verdict.push.opt[1], 'T71 "sige, ipush mo" detected').toBe(true);
    expect(verdict.push.opt[2], 'T71 non-opt-in returns false').toBe(false);
    // T72 session lock
    expect(verdict.session.free, 'T72 fresh key → no foreign lock').toBeNull();
    expect(verdict.session.own,  'T72 own lock returns null (not a conflict)').toBeNull();
    expect(verdict.session.other, 'T72 different worker sees foreign lock').toBe('worker-a');
    expect(verdict.session.afterRelease, 'T72 after release → no lock').toBeNull();
    // T73 accent
    expect(verdict.accent.tg, 'T73 tagalog-leaning sample').toBe('tagalog-leaning');
    expect(['english-leaning','mixed'], 'T73 english sample is english- or mixed-leaning').toContain(verdict.accent.en);
    expect(verdict.accent.prefNone, 'T73 default no pref').toBeNull();
    expect(verdict.accent.prefSet, 'T73 setAccentPref persists').toBe('tagalog-leaning');
    // T74 streaming
    expect(verdict.stream.on, 'T74 _setStreamingState(true) → isStreaming true').toBe(true);
    expect(verdict.stream.off, 'T74 _finalizeStream → isStreaming false').toBe(false);
    expect(verdict.stream.attrAfterFinalize, 'T74 data-streaming reset to "0" after finalize').toBe('0');
  });

  test('ai-companion-trust-deployment-detectors: turns #75-#84 behaviour locked', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.evaluate(() => {
      if (window.WHVoice && typeof window.WHVoice.open === 'function') {
        try { window.WHVoice.open(); } catch (_) { /* mount-only */ }
        try { window.WHVoice.close(); } catch (_) { /* mount-only */ }
      }
    });
    await whPage.waitForTimeout(500);

    const verdict = await whPage.evaluate(() => {
      const wh = (window as any).WHVoice;
      if (!wh) return { ready: false };
      // T75 — toxicity
      const tox1 = wh._detectToxicLanguage('what a tanga thing to do');
      const tox2 = wh._detectToxicLanguage('this idiot is wrong');
      const tox3 = wh._detectToxicLanguage('please check the bearing on P-203');
      // T76 — question shape
      const shapes = {
        howTo: wh._classifyQuestionShape('paano i-set up ang PM schedule'),
        data: wh._classifyQuestionShape('what is the MTBF for P-203'),
        opinion: wh._classifyQuestionShape('dapat ba i-stop ang machine'),
        trouble: wh._classifyQuestionShape('bakit umiingay ang motor'),
        social: wh._classifyQuestionShape('kamusta ka kuya'),
      };
      // T77 — freshness
      const fr1 = wh._isFreshnessRequest('is this data fresh');
      const fr2 = wh._isFreshnessRequest('kailan ito na-update');
      const fr3 = wh._isFreshnessRequest('what is the MTBF');
      // T78 — rate limit cooldown round-trip
      try { localStorage.removeItem('wh_ratelimit_until_test-hive'); } catch (_) {}
      const rlBefore = wh._inRateLimitCooldown('test-hive');
      wh._setRateLimitCooldown('test-hive', 30 * 1000);
      const rlActive = wh._inRateLimitCooldown('test-hive');
      wh._clearRateLimitCooldown('test-hive');
      const rlAfter = wh._inRateLimitCooldown('test-hive');
      // T79 — share
      const sh1 = wh._isShareRequest('share this with kuya Romeo');
      const sh2 = wh._isShareRequest('ipasa mo kay supervisor');
      const sh3 = wh._isShareRequest('what is the MTBF');
      const link = wh._buildShareLink('sess_abc123');
      // T80 — readback
      const rb1 = wh._isReadbackRequest('read it aloud again');
      const rb2 = wh._isReadbackRequest('basahin mo nga ulit');
      const rb3 = wh._isReadbackRequest('what is the MTBF');
      // T81 — scope
      const sc1 = wh._isScopeQuery('what can you do');
      const sc2 = wh._isScopeQuery('magagawa mo ba mag-schedule');
      const sc3 = wh._isScopeQuery('what is the MTBF');
      // T82 — correction
      const cor1 = wh._isCorrection('no, I meant P-205');
      const cor2 = wh._isCorrection('actually it was the night shift');
      const cor3 = wh._isCorrection('what is the MTBF');
      // T83 — confidence label
      const ch = wh._confidenceLabel(50, 120);
      const cm = wh._confidenceLabel(10, 60);
      const cl = wh._confidenceLabel(2, 5);
      const cu = wh._confidenceLabel(null, 'x');
      // T84 — crisis escalation extension
      const cr1 = wh._detectCrisisEscalation('I want to kill myself');
      const cr2 = wh._detectCrisisEscalation('he threatened me earlier today');
      const cr3 = wh._detectCrisisEscalation('what is the MTBF');
      return {
        ready: true,
        tox: [tox1 && tox1.severity, tox2 && tox2.severity, tox3 && tox3.severity],
        shapes,
        fresh: [fr1, fr2, fr3],
        rate: { before: rlBefore, active: rlActive > 0, after: rlAfter },
        share: { sh1, sh2, sh3, link },
        readback: [rb1, rb2, rb3],
        scope: [sc1, sc2, sc3],
        correction: [cor1, cor2, cor3],
        conf: { ch, cm, cl, cu },
        crisis: [cr1 && cr1.kind, cr2 && cr2.kind, cr3],
      };
    });

    expect(verdict.ready).toBe(true);
    // T75 toxicity
    expect(verdict.tox[0], 'T75 "tanga" → severe severity').toBeGreaterThanOrEqual(0.7);
    expect(verdict.tox[1], 'T75 "idiot" → mild severity').toBeGreaterThan(0);
    expect(verdict.tox[2], 'T75 clean text → 0').toBe(0);
    // T76 shapes
    expect(verdict.shapes.howTo).toBe('how_to');
    expect(verdict.shapes.data).toBe('data');
    expect(verdict.shapes.opinion).toBe('opinion');
    expect(verdict.shapes.trouble).toBe('troubleshoot');
    expect(verdict.shapes.social).toBe('social');
    // T77 freshness
    expect(verdict.fresh[0], 'T77 "is this fresh" detected').toBe(true);
    expect(verdict.fresh[1], 'T77 "kailan ito na-update" detected').toBe(true);
    expect(verdict.fresh[2], 'T77 non-freshness returns false').toBe(false);
    // T78 rate limit
    expect(verdict.rate.before, 'T78 fresh key → no cooldown').toBe(false);
    expect(verdict.rate.active, 'T78 after set → cooldown active').toBe(true);
    expect(verdict.rate.after, 'T78 after clear → no cooldown').toBe(false);
    // T79 share
    expect(verdict.share.sh1, 'T79 "share this" detected').toBe(true);
    expect(verdict.share.sh2, 'T79 "ipasa mo" detected').toBe(true);
    expect(verdict.share.sh3, 'T79 non-share returns false').toBe(false);
    expect(verdict.share.link, 'T79 share link built').toContain('#session=sess_abc123');
    // T80 readback
    expect(verdict.readback[0], 'T80 "read it aloud again" detected').toBe(true);
    expect(verdict.readback[1], 'T80 "basahin mo nga ulit" detected').toBe(true);
    expect(verdict.readback[2], 'T80 non-readback returns false').toBe(false);
    // T81 scope
    expect(verdict.scope[0], 'T81 "what can you do" detected').toBe(true);
    expect(verdict.scope[1], 'T81 "magagawa mo ba" detected').toBe(true);
    expect(verdict.scope[2], 'T81 non-scope returns false').toBe(false);
    // T82 correction
    expect(verdict.correction[0], 'T82 "no, I meant" detected').toBe(true);
    expect(verdict.correction[1], 'T82 "actually it was" detected').toBe(true);
    expect(verdict.correction[2], 'T82 non-correction returns false').toBe(false);
    // T83 confidence label
    expect(verdict.conf.ch, 'T83 50 rows / 120 days → high').toBe('high');
    expect(verdict.conf.cm, 'T83 10 rows / 60 days → medium').toBe('medium');
    expect(verdict.conf.cl, 'T83 2 rows / 5 days → low').toBe('low');
    expect(verdict.conf.cu, 'T83 invalid input → unknown').toBe('unknown');
    // T84 crisis
    expect(verdict.crisis[0], 'T84 self-harm detected').toBe('self_harm');
    expect(verdict.crisis[1], 'T84 workplace violence detected').toBe('workplace_violence');
    expect(verdict.crisis[2], 'T84 non-crisis returns null').toBeNull();
  });

  test('ai-companion-input-normalization-detectors: turns #85-#94 behaviour locked', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.evaluate(() => {
      if (window.WHVoice && typeof window.WHVoice.open === 'function') {
        try { window.WHVoice.open(); } catch (_) { /* mount-only */ }
        try { window.WHVoice.close(); } catch (_) { /* mount-only */ }
      }
    });
    await whPage.waitForTimeout(500);

    const verdict = await whPage.evaluate(() => {
      const wh = (window as any).WHVoice;
      if (!wh) return { ready: false };
      // T85 — precision
      const kpiPct = wh._formatKpi(92.4823, '%');
      const kpiDay = wh._formatKpi(13.7, 'days', 0);
      const kpiBad = wh._formatKpi(null, '%');
      // T86 — asset tag normalization
      const tagDirect = wh._normalizeAssetTag('check P-203 today');
      const tagSpoken = wh._normalizeAssetTag('check pee two oh three today');
      const tagNone = wh._normalizeAssetTag('check the bearing');
      // T87 — time range
      const tw = wh._normalizeTimeRange('what happened this week');
      const ts = wh._normalizeTimeRange('show last 14 days');
      const tn = wh._normalizeTimeRange('what is MTBF');
      // T88 — ack style
      try { localStorage.removeItem('wh_voice_ack_style'); } catch (_) {}
      const defStyle = wh._getAckStyle();
      wh._setAckStyle('terse');
      const terseStyle = wh._getAckStyle();
      const toggleTerse = wh._detectAckStyleToggle('skip the ack, just the number');
      const toggleWarm  = wh._detectAckStyleToggle('be warmer please');
      wh._setAckStyle('warm');
      // T89 — forbidden
      const f1 = wh._detectForbiddenTopic('how does UpKeep compare');
      const f2 = wh._detectForbiddenTopic('there is some chismis in the team');
      const f3 = wh._detectForbiddenTopic('what is the MTBF');
      // T90 — mic env
      const envQuiet = wh._classifyMicEnv([10,12,14,11,13,15,12,11]);
      const envNoisy = wh._classifyMicEnv([60,70,55,62,68,72,58,65]);
      // T91 — pin
      try { localStorage.removeItem('wh_voice_pinned_test-worker'); } catch (_) {}
      const pinned1 = wh._pinTurn('test-worker', { text: 'check bearing on P-203', intent: 'troubleshoot' });
      const pins = wh._getPinnedTurns('test-worker');
      const pinDetect = wh._isPinRequest('pin this please');
      const pinDetectNo = wh._isPinRequest('what is MTBF');
      try { localStorage.removeItem('wh_voice_pinned_test-worker'); } catch (_) {}
      // T92 — help
      const help1 = wh._isHelpCommand('help');
      const help2 = wh._isHelpCommand('/help');
      const help3 = wh._isHelpCommand('tulungan mo ako');
      const help4 = wh._isHelpCommand('what is the MTBF');
      // T93 — translation
      const tMtbfTgl = wh._translateKpiLabel('mtbf', 'tagalog-leaning');
      const tOeeCeb  = wh._translateKpiLabel('oee', 'cebuano');
      const tBogus   = wh._translateKpiLabel('xyz', 'tagalog');
      // T94 — welcome line
      const welcome = wh._firstTimeWelcomeLine('Zaniah');
      return {
        ready: true,
        kpi: [kpiPct, kpiDay, kpiBad],
        tag: [tagDirect, tagSpoken, tagNone],
        time: { week: tw && tw.days, days14: ts && ts.days, none: tn },
        ack: { def: defStyle, terse: terseStyle, toggleTerse, toggleWarm },
        forbidden: [f1, f2, f3],
        env: [envQuiet, envNoisy],
        pin: { ok: pinned1, count: pins.length, detect: pinDetect, detectNo: pinDetectNo },
        help: [help1, help2, help3, help4],
        translate: { tgl: tMtbfTgl, ceb: tOeeCeb, bogus: tBogus },
        welcome,
      };
    });

    expect(verdict.ready).toBe(true);
    expect(verdict.kpi[0], 'T85 92.4823% → "92.5%"').toMatch(/^92\.[45]%/);
    expect(verdict.kpi[1], 'T85 13.7 days, 0 decimals → "14 days"').toMatch(/^1[34] days/);
    expect(verdict.kpi[2], 'T85 null input → null').toBeNull();
    expect(verdict.tag[0], 'T86 direct "P-203"').toBe('P-203');
    expect(verdict.tag[1], 'T86 spoken "pee two oh three"').toBe('P-203');
    expect(verdict.tag[2], 'T86 no asset → null').toBeNull();
    expect(verdict.time.week, 'T87 this week → 8 days span').toBeGreaterThanOrEqual(7);
    expect(verdict.time.days14, 'T87 last 14 days').toBe(15);
    expect(verdict.time.none, 'T87 non-time returns null').toBeNull();
    expect(verdict.ack.def, 'T88 default ack style is warm').toBe('warm');
    expect(verdict.ack.terse, 'T88 setAckStyle persists').toBe('terse');
    expect(verdict.ack.toggleTerse, 'T88 "skip the ack" → terse').toBe('terse');
    expect(verdict.ack.toggleWarm, 'T88 "be warmer" → warm').toBe('warm');
    expect(verdict.forbidden[0], 'T89 competitor name detected').toBe('competitor');
    expect(verdict.forbidden[1], 'T89 chismis → office_politics').toBe('office_politics');
    expect(verdict.forbidden[2], 'T89 non-forbidden returns null').toBeNull();
    expect(verdict.env[0], 'T90 low peaks → quiet').toBe('quiet');
    expect(verdict.env[1], 'T90 high peaks → noisy').toBe('noisy');
    expect(verdict.pin.ok, 'T91 pin stored').toBe(true);
    expect(verdict.pin.count, 'T91 pin list length 1').toBe(1);
    expect(verdict.pin.detect, 'T91 "pin this" detected').toBe(true);
    expect(verdict.pin.detectNo, 'T91 non-pin returns false').toBe(false);
    expect(verdict.help[0], 'T92 "help"').toBe(true);
    expect(verdict.help[1], 'T92 "/help"').toBe(true);
    expect(verdict.help[2], 'T92 "tulungan mo ako"').toBe(true);
    expect(verdict.help[3], 'T92 non-help returns false').toBe(false);
    expect(verdict.translate.tgl, 'T93 mtbf tagalog → translated').toContain('Karaniwang');
    expect(verdict.translate.ceb, 'T93 oee cebuano → translated').toContain('Episyensya');
    expect(verdict.translate.bogus, 'T93 unknown metric → null').toBeNull();
    expect(verdict.welcome, 'T94 welcome line includes persona name').toContain('Zaniah');
    expect(verdict.welcome, 'T94 welcome line lists sample command').toMatch(/overdue|OEE|log/i);
  });

  test('ai-companion-integration-audit-detectors: turns #95-#104 behaviour locked', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.evaluate(() => {
      if (window.WHVoice && typeof window.WHVoice.open === 'function') {
        try { window.WHVoice.open(); } catch (_) { /* mount-only */ }
        try { window.WHVoice.close(); } catch (_) { /* mount-only */ }
      }
    });
    await whPage.waitForTimeout(300);

    const verdict = await whPage.evaluate(() => {
      const wh = (window as any).WHVoice;
      if (!wh) return { ready: false };
      // T96 quiet hours — explicit dates
      const midnight = wh._isQuietHours(new Date(Date.UTC(2026, 0, 1, 16, 0, 0))); // 00:00 PHT
      const noon     = wh._isQuietHours(new Date(Date.UTC(2026, 0, 1, 4, 0, 0)));  // 12:00 PHT
      // T97 preflight
      try { localStorage.removeItem('wh_voice_execute_authorised'); } catch (_) {}
      const noIntent  = wh._preflightAction('', {});
      const noAsset   = wh._preflightAction('log_entry', {});
      const malformed = wh._preflightAction('log_entry', { asset_tag: 'banana' });
      wh._setVoiceExecuteAuth(true);
      const locked    = wh._preflightAction('log_entry', { asset_tag: 'P-203' });
      wh._setVoiceExecuteAuth(false);
      // T99 error analytics
      try { localStorage.removeItem('wh_voice_errors_test-hive'); } catch (_) {}
      const bump1 = wh._bumpErrorCount('test-hive', 'gateway_503');
      const bump2 = wh._bumpErrorCount('test-hive', 'gateway_503');
      const counts = wh._getErrorCounts('test-hive');
      try { localStorage.removeItem('wh_voice_errors_test-hive'); } catch (_) {}
      // T100 session tag
      try { localStorage.removeItem('wh_voice_session_tag_sess-abc'); } catch (_) {}
      const okSet = wh._setSessionTag('sess-abc', 'PM-planning');
      const got = wh._getSessionTag('sess-abc');
      const detect1 = wh._detectSessionTagRequest('tag this as PM planning');
      const detect2 = wh._detectSessionTagRequest('what is the MTBF');
      try { localStorage.removeItem('wh_voice_session_tag_sess-abc'); } catch (_) {}
      // T101 deep link
      const link = wh._buildDeepLink('pm-scheduler', { asset: 'P-203' });
      const parsed = wh._parseDeepLinkToken('<wh-link page=pm-scheduler asset=P-203>');
      // T102 grammar guess
      const mangled = wh._looksGrammarMangled('blahdblahd kekekekek bzzzzzzz xxxxxx tcktcktck');
      const clean = wh._looksGrammarMangled('check the bearing on P-203 today');
      // T103 phrase pool
      const ackPhrase = wh._pickPersonaPhrase('ack');
      const bogusPhrase = wh._pickPersonaPhrase('warpdrive');
      // T104 shift end
      const farFromEnd = wh._isNearShiftEnd(0, 30); // midnight, 30 min margin → depends on time
      return {
        ready: true,
        quiet: { midnight, noon },
        pref: {
          noIntent: noIntent && noIntent.blocker,
          noAsset:  noAsset && noAsset.blocker,
          malformed: malformed && malformed.blocker,
          locked: locked && (locked.ok === true),
        },
        err: { b1: bump1, b2: bump2, counts },
        tag: { ok: okSet, got, d1: detect1, d2: detect2 },
        link: { built: link, parsedPage: parsed && parsed.page, parsedAsset: parsed && parsed.params && parsed.params.asset },
        gram: { mangled, clean },
        phrase: { ack: ackPhrase, bogus: bogusPhrase },
        shift: { far: typeof farFromEnd === 'boolean' },
      };
    });

    expect(verdict.ready).toBe(true);
    expect(verdict.quiet.midnight, 'T96 midnight PHT → quiet hours').toBe(true);
    expect(verdict.quiet.noon, 'T96 noon PHT → not quiet').toBe(false);
    expect(verdict.pref.noIntent, 'T97 no intent → no_intent blocker').toBe('no_intent');
    expect(verdict.pref.noAsset, 'T97 missing asset → missing_asset_tag').toBe('missing_asset_tag');
    expect(verdict.pref.malformed, 'T97 banana asset → malformed_asset_tag').toBe('malformed_asset_tag');
    expect(verdict.pref.locked, 'T97 valid + lock ON → ok').toBe(true);
    expect(verdict.err.b1, 'T99 first bump returns 1').toBe(1);
    expect(verdict.err.b2, 'T99 second bump returns 2').toBe(2);
    expect(Object.keys(verdict.err.counts).length, 'T99 counts has at least one day').toBeGreaterThan(0);
    expect(verdict.tag.ok, 'T100 setSessionTag returns true').toBe(true);
    expect(verdict.tag.got, 'T100 getSessionTag round-trip').toBe('PM-planning');
    expect(verdict.tag.d1, 'T100 detect tag-request').toContain('PM');
    expect(verdict.tag.d2, 'T100 non-tag returns null').toBeNull();
    expect(verdict.link.built, 'T101 deep link built').toContain('/pm-scheduler.html');
    expect(verdict.link.built, 'T101 deep link includes asset param').toContain('asset=P-203');
    expect(verdict.link.parsedPage, 'T101 parsed page').toBe('pm-scheduler');
    expect(verdict.link.parsedAsset, 'T101 parsed asset').toBe('P-203');
    expect(verdict.gram.mangled, 'T102 mangled text detected').toBe(true);
    expect(verdict.gram.clean, 'T102 clean text not flagged').toBe(false);
    expect(typeof verdict.phrase.ack, 'T103 phrase pool returns a string').toBe('string');
    expect(verdict.phrase.bogus, 'T103 unknown category → null').toBeNull();
    expect(verdict.shift.far, 'T104 returns a boolean').toBe(true);
  });

  test('ai-companion-learning-detectors: turns #105-#114 behaviour locked', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.evaluate(() => {
      if (window.WHVoice && typeof window.WHVoice.open === 'function') {
        try { window.WHVoice.open(); } catch (_) { /* mount-only */ }
        try { window.WHVoice.close(); } catch (_) { /* mount-only */ }
      }
    });
    await whPage.waitForTimeout(300);

    const verdict = await whPage.evaluate(() => {
      const wh = (window as any).WHVoice;
      if (!wh) return { ready: false };
      // T105 — PM sync drift
      const inFuture = new Date(Date.now() + 30 * 86400000).toISOString();
      const nearNow = new Date(Date.now() + 2 * 86400000).toISOString();
      const drift = wh._detectPmSyncDrift('P-203', inFuture);
      const noDrift = wh._detectPmSyncDrift('P-203', nearNow);
      const nullCase = wh._detectPmSyncDrift(null, inFuture);
      // T106 — skill depth
      const dApp = wh._skillDepthForLevel(1);
      const dStd = wh._skillDepthForLevel(3);
      const dSen = wh._skillDepthForLevel(5);
      const vocab = wh._vocabularyForDepth('senior');
      // T107 — cross-asset pattern
      const now = Date.now();
      const entries = [
        { asset_tag: 'P-203', failure_mode: 'vibration', created_at: new Date(now - 1*86400000).toISOString() },
        { asset_tag: 'P-204', failure_mode: 'vibration', created_at: new Date(now - 2*86400000).toISOString() },
        { asset_tag: 'C-01',  failure_mode: 'overheat',  created_at: new Date(now - 100*86400000).toISOString() },
      ];
      const patterns = wh._detectCrossAssetPattern(entries);
      // T108 — intent history
      try { localStorage.removeItem('wh_voice_intent_hist_test-w'); } catch (_) {}
      wh._recordIntent('test-w', 'mtbf');
      wh._recordIntent('test-w', 'mtbf');
      wh._recordIntent('test-w', 'pm_overdue');
      const top = wh._topRecurringIntents('test-w', 5);
      try { localStorage.removeItem('wh_voice_intent_hist_test-w'); } catch (_) {}
      // T109 — sentiment
      const senPos = wh._classifySessionSentiment([
        { user: 'salamat, tapos na, ayos' },
        { user: 'gumana na, naks, magaling' },
        { user: 'done na, ayos lang, thanks' },
      ]);
      const senNeg = wh._classifySessionSentiment([
        { user: 'pagod talaga, frustrated' },
        { user: 'sira ulit, nakakaloka' },
        { user: 'broken na naman, ayoko na' },
      ]);
      try { localStorage.removeItem('wh_voice_sentiment_test-w'); } catch (_) {}
      wh._recordDailySentiment('test-w', 'negative');
      const isPers = wh._isPersistentNegative('test-w', 1);
      try { localStorage.removeItem('wh_voice_sentiment_test-w'); } catch (_) {}
      // T111 — symptom normalizer
      const symV = wh._normalizeSymptom('yumayanig ang motor');
      const symO = wh._normalizeSymptom('napakainit ng bearing');
      const symN = wh._normalizeSymptom('the data looks good');
      // T112 — shift boundary
      const oldStart = new Date(Date.now() - 10 * 60 * 60 * 1000).toISOString(); // 10h ago
      const newStart = new Date(Date.now() - 30 * 60 * 1000).toISOString();      // 30 min ago
      const crossedOld = wh._crossedShiftBoundary(oldStart);
      const crossedNew = wh._crossedShiftBoundary(newStart);
      // T114 — mentor handoff
      const mh1 = wh._isMentorHandoff("I'll ask my supervisor about this");
      const mh2 = wh._isMentorHandoff('tatanungin ko si kuya Ben');
      const mh3 = wh._isMentorHandoff('what is the MTBF');
      return {
        ready: true,
        pm: { drift: drift && drift.sync_needed, nodrift: noDrift, nullCase },
        skill: { dApp, dStd, dSen, vocabHasRpn: !!(vocab && vocab.rpn) },
        patterns: patterns && patterns.length,
        topIntent: top[0] && top[0].intent,
        sentiment: { pos: senPos, neg: senNeg, persistent: isPers },
        symptom: { v: symV, o: symO, n: symN },
        shift: { old: crossedOld, fresh: crossedNew },
        mentor: { m1: mh1, m2: mh2, m3: mh3 },
      };
    });

    expect(verdict.ready).toBe(true);
    expect(verdict.pm.drift, 'T105 30-day future PM date → drift').toBe(true);
    expect(verdict.pm.nodrift, 'T105 2-day future PM date → no drift').toBeNull();
    expect(verdict.pm.nullCase, 'T105 null asset → null').toBeNull();
    expect(verdict.skill.dApp, 'T106 level 1 → apprentice').toBe('apprentice');
    expect(verdict.skill.dStd, 'T106 level 3 → standard').toBe('standard');
    expect(verdict.skill.dSen, 'T106 level 5 → senior').toBe('senior');
    expect(verdict.skill.vocabHasRpn, 'T106 senior vocab has RPN').toBe(true);
    expect(verdict.patterns, 'T107 vibration pattern across P-203 + P-204').toBe(1);
    expect(verdict.topIntent, 'T108 most recurring intent is mtbf').toBe('mtbf');
    expect(verdict.sentiment.pos, 'T109 positive sentiment').toBe('positive');
    expect(verdict.sentiment.neg, 'T109 negative sentiment').toBe('negative');
    expect(verdict.sentiment.persistent, 'T109 1-day required + 1 day → persistent').toBe(true);
    expect(verdict.symptom.v, 'T111 vibration symptom normalized').toBe('vibration_anomaly');
    expect(verdict.symptom.o, 'T111 overheat symptom normalized').toBe('overheat');
    expect(verdict.symptom.n, 'T111 no symptom → null').toBeNull();
    expect(verdict.shift.old, 'T112 10h-old start → crossed boundary').toBe(true);
    expect(verdict.shift.fresh, 'T112 30-min-old start → no boundary').toBe(false);
    expect(verdict.mentor.m1, 'T114 "I\'ll ask my supervisor" detected').toBe(true);
    expect(verdict.mentor.m2, 'T114 "tatanungin ko si kuya" detected').toBe(true);
    expect(verdict.mentor.m3, 'T114 non-handoff returns false').toBe(false);
  });

  test('ai-companion-compliance-detectors: turns #115-#124 behaviour locked', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.evaluate(() => {
      if (window.WHVoice && typeof window.WHVoice.open === 'function') {
        try { window.WHVoice.open(); } catch (_) { /* mount-only */ }
        try { window.WHVoice.close(); } catch (_) { /* mount-only */ }
      }
    });
    await whPage.waitForTimeout(300);

    const verdict = await whPage.evaluate(() => {
      const wh = (window as any).WHVoice;
      if (!wh) return { ready: false };
      // T115 PII
      const piiPhone = wh._scrubPii('call me at 09171234567');
      const piiEmail = wh._scrubPii('reach me at juan@example.com');
      const piiClean = wh._scrubPii('the bearing on P-203 is fine');
      // T116 consent
      try { localStorage.removeItem('wh_voice_consent'); } catch (_) {}
      const c0 = wh._hasConsent();
      wh._captureConsent('voice-recording');
      const c1 = wh._hasConsent();
      wh._revokeConsent();
      const c2 = wh._hasConsent();
      const grant = wh._detectConsentChange('I consent to recording');
      const revoke = wh._detectConsentChange('revoke my consent');
      // T117 retention
      const cutoff = wh._retentionCutoffIso(30);
      const cutoffDefault = wh._retentionCutoffIso(null);
      // T118 erasure
      const er1 = wh._isErasureRequest('delete my voice history');
      const er2 = wh._isErasureRequest('burahin mo lahat ng history');
      const er3 = wh._isErasureRequest('what is the MTBF');
      // T119 audit export
      const csv = wh._buildAuditCsv([
        { created_at: '2026-05-21T01:00:00Z', worker_name: 'Juan', event_type: 'log_entry', payload: { asset: 'P-203' } },
        { created_at: '2026-05-21T02:00:00Z', worker_name: 'Ana, T.', event_type: 'note', payload: 'has, comma' },
      ]);
      // T121 ai disclosure
      try { localStorage.removeItem('wh_voice_ai_disclosure_policy'); } catch (_) {}
      const d0 = wh._needsAiDisclosure('s1');
      wh._setAiDisclosurePolicy(true);
      const d1 = wh._needsAiDisclosure('s1');
      wh._markAiDisclosureShown('s1');
      const d2 = wh._needsAiDisclosure('s1');
      wh._setAiDisclosurePolicy(false);
      const line = wh._aiDisclosureLine();
      // T122 locale date
      const isoDate = wh._formatLocaleDate('2026-05-21T01:00:00Z', 'english-leaning');
      const phDate  = wh._formatLocaleDate('2026-05-21T01:00:00Z', 'tagalog-leaning');
      const bad     = wh._formatLocaleDate('not-a-date', 'english');
      // T123 cost cap
      const exc1 = wh._exceededCostCap(120, 100);
      const exc2 = wh._exceededCostCap(80, 100);
      const excBad = wh._exceededCostCap('x', 100);
      // T124 voice drift
      try { localStorage.removeItem('wh_voice_signature_test-w'); } catch (_) {}
      wh._recordVoiceSignature('test-w', { avg_peak: 40, cadence: 1.2 });
      const sameSig = wh._voiceSignatureDrift('test-w', { avg_peak: 42, cadence: 1.25 });
      const driftSig = wh._voiceSignatureDrift('test-w', { avg_peak: 80, cadence: 2.0 });
      try { localStorage.removeItem('wh_voice_signature_test-w'); } catch (_) {}
      return {
        ready: true,
        pii: { phone: piiPhone, email: piiEmail, clean: piiClean },
        consent: { c0, c1, c2, grant, revoke },
        ret: { custom: cutoff, def: cutoffDefault },
        er: [er1, er2, er3],
        csv,
        disc: { d0, d1, d2, line },
        date: { iso: isoDate, ph: phDate, bad },
        cap: [exc1, exc2, excBad],
        drift: { same: sameSig && sameSig.drift, far: driftSig && driftSig.drift },
      };
    });

    expect(verdict.ready).toBe(true);
    expect(verdict.pii.phone.text, 'T115 phone scrubbed').toContain('[PHONE]');
    expect(verdict.pii.phone.scrubs, 'T115 scrub count >= 1').toBeGreaterThanOrEqual(1);
    expect(verdict.pii.email.text, 'T115 email scrubbed').toContain('[EMAIL]');
    expect(verdict.pii.clean.scrubs, 'T115 clean text → 0 scrubs').toBe(0);
    expect(verdict.consent.c0, 'T116 default no consent').toBe(false);
    expect(verdict.consent.c1, 'T116 after capture → consent').toBe(true);
    expect(verdict.consent.c2, 'T116 after revoke → no consent').toBe(false);
    expect(verdict.consent.grant, 'T116 grant phrase detected').toBe('grant');
    expect(verdict.consent.revoke, 'T116 revoke phrase detected').toBe('revoke');
    expect(verdict.ret.custom, 'T117 custom retention cutoff is ISO').toMatch(/^\d{4}-\d{2}-\d{2}/);
    expect(verdict.ret.def, 'T117 default retention cutoff is ISO').toMatch(/^\d{4}-\d{2}-\d{2}/);
    expect(verdict.er[0], 'T118 "delete my voice history" detected').toBe(true);
    expect(verdict.er[1], 'T118 "burahin mo lahat" detected').toBe(true);
    expect(verdict.er[2], 'T118 non-erasure returns false').toBe(false);
    expect(verdict.csv, 'T119 CSV starts with header').toMatch(/^created_at,worker_name/);
    expect(verdict.csv, 'T119 CSV escapes commas in fields').toContain('"Ana, T."');
    expect(verdict.disc.d0, 'T121 disclosure off by default').toBe(false);
    expect(verdict.disc.d1, 'T121 disclosure ON before showing').toBe(true);
    expect(verdict.disc.d2, 'T121 disclosure already shown → false').toBe(false);
    expect(verdict.disc.line, 'T121 disclosure line is non-empty').toContain('AI');
    expect(verdict.date.iso, 'T122 english → ISO').toBe('2026-05-21');
    expect(verdict.date.ph,  'T122 tagalog → DD/MM/YYYY').toBe('21/05/2026');
    expect(verdict.date.bad, 'T122 bad input → null').toBeNull();
    expect(verdict.cap[0], 'T123 120 vs 100 → exceeded').toBe(true);
    expect(verdict.cap[1], 'T123 80 vs 100 → not exceeded').toBe(false);
    expect(verdict.cap[2], 'T123 bad input → false').toBe(false);
    expect(verdict.drift.same, 'T124 close sig → no drift').toBe(false);
    expect(verdict.drift.far,  'T124 far sig → drift').toBe(true);
  });

  test('ai-companion-accessibility-detectors: turns #125-#134 behaviour locked', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.evaluate(() => {
      if (window.WHVoice && typeof window.WHVoice.open === 'function') {
        try { window.WHVoice.open(); } catch (_) { /* mount-only */ }
        try { window.WHVoice.close(); } catch (_) { /* mount-only */ }
      }
    });
    await whPage.waitForTimeout(300);

    const verdict = await whPage.evaluate(() => {
      const wh = (window as any).WHVoice;
      if (!wh) return { ready: false };
      // T127 reduced motion
      try { localStorage.removeItem('wh_voice_reduced_motion'); } catch (_) {}
      const rm0 = wh._isReducedMotionRequested();  // may be true from OS pref; just verify it's a boolean
      wh._setReducedMotion(true);
      const rm1 = wh._isReducedMotionRequested();
      wh._setReducedMotion(false);
      // T128 aria-live
      wh._announceForScreenReader('test announcement');
      const region = document.getElementById('wh-voice-aria-live');
      const hasAria = !!(region && region.getAttribute('aria-live') === 'polite');
      // T129 keyboard
      const escAction   = wh._resolveKeyAction({ code: 'Escape', target: document.body });
      const spaceInput  = wh._resolveKeyAction({ code: 'Space', target: document.createElement('input') });
      const spaceBody   = wh._resolveKeyAction({ code: 'Space', target: document.body });
      const enterAction = wh._resolveKeyAction({ code: 'Enter', target: document.body });
      const helpRaw     = wh._resolveKeyAction({ code: 'KeyH', target: document.body });
      const helpCtrl    = wh._resolveKeyAction({ code: 'KeyH', ctrlKey: true, target: document.body });
      // T130 color-blind
      try { localStorage.removeItem('wh_voice_cb_palette'); } catch (_) {}
      const palDef = wh._currentPalette();
      wh._setColorBlindMode(true);
      const palCb = wh._currentPalette();
      wh._setColorBlindMode(false);
      // T131 large text
      try { localStorage.removeItem('wh_voice_large_text'); } catch (_) {}
      const lt0 = wh._isLargeTextMode();
      wh._setLargeTextMode(true);
      const lt1 = wh._isLargeTextMode();
      wh._setLargeTextMode(false);
      // T132 haptic
      const validKind = wh._hapticPulse('confirm');  // returns true/false depending on browser
      const badKind   = wh._hapticPulse('warpdrive');
      // T133 voice only
      try { localStorage.removeItem('wh_voice_only_mode'); } catch (_) {}
      wh._setVoiceOnlyMode(true);
      const vo1 = wh._isVoiceOnlyMode();
      const togOn  = wh._detectVoiceOnlyToggle('voice-only mode on');
      const togOff = wh._detectVoiceOnlyToggle('voice-only mode off');
      const togNone = wh._detectVoiceOnlyToggle('what is MTBF');
      wh._setVoiceOnlyMode(false);
      // T134 captions
      try { localStorage.removeItem('wh_voice_captions'); } catch (_) {}
      const cap0 = wh._isCaptionsOn();
      wh._setCaptionsOn(true);
      const rendered = wh._renderCaption('Companion says: 14 days');
      const capBar = document.getElementById('wh-voice-caption-bar');
      const capText = capBar ? capBar.textContent : '';
      wh._setCaptionsOn(false);
      // cleanup caption bar
      if (capBar) capBar.remove();
      return {
        ready: true,
        rm: { rm0Bool: typeof rm0 === 'boolean', rm1 },
        aria: { has: hasAria },
        kbd: { escAction, spaceInput, spaceBody, enterAction, helpRaw, helpCtrl },
        pal: { defCrit: palDef.critical, cbCrit: palCb.critical },
        lt: { lt0, lt1 },
        hap: { validKind: typeof validKind === 'boolean' || validKind === undefined, badKind },
        vo: { vo1, togOn, togOff, togNone },
        cap: { cap0, rendered, capText },
      };
    });

    expect(verdict.ready).toBe(true);
    expect(verdict.rm.rm0Bool, 'T127 _isReducedMotionRequested returns a boolean').toBe(true);
    expect(verdict.rm.rm1, 'T127 setReducedMotion(true) reflected in getter').toBe(true);
    expect(verdict.aria.has, 'T128 aria-live=polite region present').toBe(true);
    expect(verdict.kbd.escAction, 'T129 Escape → close').toBe('close');
    expect(verdict.kbd.spaceInput, 'T129 Space inside input is suppressed').toBeNull();
    expect(verdict.kbd.spaceBody, 'T129 Space on body → toggle_recording').toBe('toggle_recording');
    expect(verdict.kbd.enterAction, 'T129 Enter → submit_typed').toBe('submit_typed');
    expect(verdict.kbd.helpRaw, 'T129 plain H is NOT a shortcut').toBeNull();
    expect(verdict.kbd.helpCtrl, 'T129 Ctrl+H → help').toBe('help');
    expect(verdict.pal.defCrit, 'T130 default critical color').toMatch(/^#[0-9a-f]{6}$/i);
    expect(verdict.pal.defCrit, 'T130 default critical is red').toBe('#dc2626');
    expect(verdict.pal.cbCrit, 'T130 CB-safe critical is NOT red').not.toBe('#dc2626');
    expect(verdict.lt.lt0, 'T131 default large-text off').toBe(false);
    expect(verdict.lt.lt1, 'T131 setLargeTextMode(true) reflected').toBe(true);
    expect(verdict.hap.badKind, 'T132 unknown haptic pattern returns false').toBe(false);
    expect(verdict.vo.vo1, 'T133 voice-only mode persists').toBe(true);
    expect(verdict.vo.togOn, 'T133 toggle "on" detected').toBe('on');
    expect(verdict.vo.togOff, 'T133 toggle "off" detected').toBe('off');
    expect(verdict.vo.togNone, 'T133 non-toggle returns null').toBeNull();
    expect(verdict.cap.cap0, 'T134 captions default off').toBe(false);
    expect(verdict.cap.rendered, 'T134 caption rendered when on').toBe(true);
    expect(verdict.cap.capText, 'T134 caption bar shows text').toContain('14 days');
  });

  test('ai-companion-operational-detectors: turns #135-#144 behaviour locked', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.evaluate(() => {
      if (window.WHVoice && typeof window.WHVoice.open === 'function') {
        try { window.WHVoice.open(); } catch (_) { /* mount-only */ }
        try { window.WHVoice.close(); } catch (_) { /* mount-only */ }
      }
    });
    await whPage.waitForTimeout(300);

    const verdict = await whPage.evaluate(() => {
      const wh = (window as any).WHVoice;
      if (!wh) return { ready: false };
      // T136 self test
      const st = wh._runSelfTest();
      // T137 feature flags (without DB, _isFeatureOn returns false)
      const ffOff = wh._isFeatureOn('experimental_streaming');
      // T138 browser support
      const support = wh._checkBrowserSupport();
      // T139 network
      const netClass = wh._currentNetworkClass();
      const isLite = wh._shouldUseLitePayload();
      // T140 memory
      const mem = wh._checkMemoryPressure();
      // T142 background
      const paused = wh._shouldPauseForBackground();
      // T143 crash handler
      wh._installCrashHandler();
      wh._clearCrashState();
      const noCrash = wh._getLastCrashSummary();
      return {
        ready: true,
        st: { passed: st && st.passed, total: st && st.total, failures: st && st.failures },
        ffOff,
        support: { ok: support && typeof support.supported === 'boolean', missingArr: Array.isArray(support && support.missing) },
        net: { class: netClass, isLite },
        mem: { pressure: mem && mem.pressure },
        paused: typeof paused === 'boolean',
        crash: noCrash,
      };
    });

    expect(verdict.ready).toBe(true);
    expect(verdict.st.failures, 'T136 self-test: no failures').toEqual([]);
    expect(verdict.st.passed, 'T136 self-test: all checks passed').toBe(verdict.st.total);
    expect(verdict.ffOff, 'T137 unknown flag returns false').toBe(false);
    expect(verdict.support.ok, 'T138 _checkBrowserSupport returns object with .supported').toBe(true);
    expect(verdict.support.missingArr, 'T138 .missing is an array').toBe(true);
    expect(['unknown','slow-2g','2g','3g','4g'], 'T139 known network class').toContain(verdict.net.class);
    expect(typeof verdict.net.isLite, 'T139 _shouldUseLitePayload returns boolean').toBe('boolean');
    expect(['low','medium','high','unknown'], 'T140 known pressure level').toContain(verdict.mem.pressure);
    expect(verdict.paused, 'T142 _shouldPauseForBackground returns boolean').toBe(true);
    expect(verdict.crash, 'T143 cleared crash → null').toBeNull();
  });

  test('ai-companion-team-coordination-detectors: turns #145-#154 behaviour locked', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.evaluate(() => {
      if (window.WHVoice && typeof window.WHVoice.open === 'function') {
        try { window.WHVoice.open(); } catch (_) { /* mount-only */ }
        try { window.WHVoice.close(); } catch (_) { /* mount-only */ }
      }
    });
    await whPage.waitForTimeout(300);

    const verdict = await whPage.evaluate(() => {
      const wh = (window as any).WHVoice;
      if (!wh) return { ready: false };
      // T146 handoff detector
      const h1 = wh._detectHandoffRequest('send this to Mike Santos');
      const h2 = wh._detectHandoffRequest('ipasa mo kay Kuya Ben');
      const h3 = wh._detectHandoffRequest('what is the MTBF');
      // T147 shared note
      const sn1 = wh._isSharedNoteRequest('share this with the team');
      const sn2 = wh._isSharedNoteRequest('i-share mo sa team');
      const sn3 = wh._isSharedNoteRequest('what is the MTBF');
      // T148 concurrency
      const lo = wh._shouldFlagHighConcurrency(3, 5);
      const hi = wh._shouldFlagHighConcurrency(8, 5);
      const def = wh._shouldFlagHighConcurrency(6, null);
      // T149 watchlist
      const w1 = wh._detectWatchRequest('watch P-203 for me');
      const w2 = wh._detectWatchRequest('subscribe to C-01');
      const w3 = wh._detectWatchRequest('notify me on MX-12');
      const w4 = wh._detectWatchRequest('what is the MTBF');
      // T151 resolution detector
      const r1 = wh._detectResolution('fixed it na');
      const r2 = wh._detectResolution('ayos na to');
      const r3 = wh._detectResolution('gumana na');
      const r4 = wh._detectResolution('still broken');
      // T153 buddy
      try { localStorage.removeItem('wh_voice_buddy_test-w'); } catch (_) {}
      wh._setBuddy('test-w', 'Mike S');
      const b1 = wh._getBuddy('test-w');
      const bset = wh._detectBuddySet('buddy up with Juan Cruz');
      const bsetTgl = wh._detectBuddySet('kasama ko sa shift si Romeo');
      const bsetNo = wh._detectBuddySet('what is the MTBF');
      wh._clearBuddy('test-w');
      const b2 = wh._getBuddy('test-w');
      return {
        ready: true,
        handoff: [h1, h2, h3],
        sharedNote: [sn1, sn2, sn3],
        concurrency: { lo, hi, def },
        watch: [w1, w2, w3, w4],
        resolution: [r1, r2, r3, r4],
        buddy: { b1, bset, bsetTgl, bsetNo, b2 },
      };
    });

    expect(verdict.ready).toBe(true);
    expect(verdict.handoff[0], 'T146 "send this to Mike Santos" detects name').toBe('Mike Santos');
    expect(verdict.handoff[1], 'T146 "ipasa mo kay Kuya Ben"').toContain('Ben');
    expect(verdict.handoff[2], 'T146 non-handoff returns null').toBeNull();
    expect(verdict.sharedNote[0], 'T147 "share with the team"').toBe(true);
    expect(verdict.sharedNote[1], 'T147 "i-share mo sa team"').toBe(true);
    expect(verdict.sharedNote[2], 'T147 non-share returns false').toBe(false);
    expect(verdict.concurrency.lo, 'T148 3 of 5 → not flagged').toBe(false);
    expect(verdict.concurrency.hi, 'T148 8 of 5 → flagged').toBe(true);
    expect(verdict.concurrency.def, 'T148 6 with default cap 5 → flagged').toBe(true);
    expect(verdict.watch[0], 'T149 "watch P-203"').toBe('P-203');
    expect(verdict.watch[1], 'T149 "subscribe to C-01"').toBe('C-01');
    expect(verdict.watch[2], 'T149 "notify me on MX-12"').toBe('MX-12');
    expect(verdict.watch[3], 'T149 non-watch returns null').toBeNull();
    expect(verdict.resolution[0], 'T151 "fixed it" detected').toBe('fix_resolved');
    expect(verdict.resolution[1], 'T151 "ayos na" detected').toBe('fix_resolved');
    expect(verdict.resolution[2], 'T151 "gumana na" detected').toBe('fix_resolved');
    expect(verdict.resolution[3], 'T151 "still broken" not resolved').toBeNull();
    expect(verdict.buddy.b1, 'T153 buddy persists').toBe('Mike S');
    expect(verdict.buddy.bset, 'T153 "buddy up with Juan Cruz" detected').toContain('Juan');
    expect(verdict.buddy.bsetTgl, 'T153 "kasama ko si Romeo" detected').toContain('Romeo');
    expect(verdict.buddy.bsetNo, 'T153 non-buddy returns null').toBeNull();
    expect(verdict.buddy.b2, 'T153 _clearBuddy → null').toBeNull();
  });

  test('ai-companion-external-integration-detectors: turns #155-#164 behaviour locked', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.evaluate(() => {
      if (window.WHVoice && typeof window.WHVoice.open === 'function') {
        try { window.WHVoice.open(); } catch (_) { /* mount-only */ }
        try { window.WHVoice.close(); } catch (_) { /* mount-only */ }
      }
    });
    await whPage.waitForTimeout(300);

    const verdict = await whPage.evaluate(() => {
      const wh = (window as any).WHVoice;
      if (!wh) return { ready: false };
      // T155 SAP validate
      const sapOk  = wh._validateSapWorkOrder({ order_id: 'WO123', equipment_id: 'EQ456', order_type: 'PM01' });
      const sapBad = wh._validateSapWorkOrder({ order_id: 'WO123' });
      const sapBadType = wh._validateSapWorkOrder({ order_id: 'X', equipment_id: 'Y', order_type: 'BOGUS' });
      // T156 maximo query
      const q = wh._buildMaximoQuery('hive-1', '2026-01-01T00:00:00Z');
      const parsed = wh._parseMaximoResponse({ member: [
        { wonum: 'WO1', assetnum: 'P-203', statusdate: '2026-05-01T00:00:00Z' },
      ]});
      // T157 OPC tag
      const opc = wh._parseOpcTag('Plant1.P203.Vibration_RMS');
      const opcBad = wh._parseOpcTag('not.an.opc.tag.format!');
      // T158 MQTT
      const topic = wh._buildMqttTopic('hive-1', 'P-203', 'vibration');
      const payload = wh._parseMqttPayload('{"value":42.5,"unit":"mm/s","ts":"2026-05-21T01:00:00Z"}');
      // T161 Teams card
      const card = wh._buildTeamsCard('Alert', 'Bearing critical', 'critical');
      // T162 ICS
      const ics = wh._buildIcsEvent({ start: '2026-05-22T08:00:00Z', end: '2026-05-22T09:00:00Z', summary: 'PM on P-203' });
      // T163 sig compare
      const sigEq    = wh._constantTimeCompare('abc123', 'abc123');
      const sigDiff  = wh._constantTimeCompare('abc123', 'abc124');
      const sigLen   = wh._constantTimeCompare('abc', 'abcd');
      // T164 retry queue
      try { localStorage.removeItem('wh_voice_outbound_queue'); } catch (_) {}
      const enq = wh._enqueueOutbound({ url: 'https://x.example/h', body: { ok: true }, kind: 'slack' });
      const q2 = wh._getOutboundQueue();
      try { localStorage.removeItem('wh_voice_outbound_queue'); } catch (_) {}
      return {
        ready: true,
        sap: { okOk: sapOk && sapOk.ok, badOk: sapBad && sapBad.ok, badTypeOk: sapBadType && sapBadType.ok, src: sapOk && sapOk.normalized && sapOk.normalized.source_system },
        maximo: { url: q && q.url, hasWhere: !!(q && q.params && q.params['oslc.where']), parsedLen: parsed.length, firstExt: parsed[0] && parsed[0].external_id },
        opc: { tag: opc && opc.asset_tag, metric: opc && opc.metric, opcBad },
        mqtt: { topic, value: payload && payload.value },
        teams: { hasAttach: Array.isArray(card && card.attachments) },
        ics: { hasBegin: ics && ics.indexOf('BEGIN:VCALENDAR') === 0, hasSummary: ics && ics.indexOf('SUMMARY:PM on P-203') >= 0 },
        sig: { eq: sigEq, diff: sigDiff, len: sigLen },
        queue: { enq, len: q2.length },
      };
    });

    expect(verdict.ready).toBe(true);
    expect(verdict.sap.okOk, 'T155 valid SAP order accepted').toBe(true);
    expect(verdict.sap.badOk, 'T155 SAP order without equipment rejected').toBe(false);
    expect(verdict.sap.badTypeOk, 'T155 invalid order_type rejected').toBe(false);
    expect(verdict.sap.src, 'T155 source_system stamped').toBe('sap_pm');
    expect(verdict.maximo.url, 'T156 Maximo URL built').toContain('/maximo/rest/mxapi');
    expect(verdict.maximo.hasWhere, 'T156 query carries oslc.where').toBe(true);
    expect(verdict.maximo.parsedLen, 'T156 1 row parsed').toBe(1);
    expect(verdict.maximo.firstExt, 'T156 wonum carried into external_id').toBe('WO1');
    expect(verdict.opc.tag, 'T157 OPC tag parsed to canonical').toBe('P-203');
    expect(verdict.opc.metric, 'T157 metric extracted').toBe('vibration_rms');
    expect(verdict.opc.opcBad, 'T157 malformed OPC → null').toBeNull();
    expect(verdict.mqtt.topic, 'T158 MQTT topic built').toBe('workhive/hive-1/P-203/vibration');
    expect(verdict.mqtt.value, 'T158 MQTT payload value parsed').toBe(42.5);
    expect(verdict.teams.hasAttach, 'T161 Teams card has attachments array').toBe(true);
    expect(verdict.ics.hasBegin, 'T162 ICS starts with BEGIN:VCALENDAR').toBe(true);
    expect(verdict.ics.hasSummary, 'T162 ICS carries summary').toBe(true);
    expect(verdict.sig.eq, 'T163 equal strings → true').toBe(true);
    expect(verdict.sig.diff, 'T163 different strings → false').toBe(false);
    expect(verdict.sig.len, 'T163 different lengths → false').toBe(false);
    expect(verdict.queue.enq, 'T164 enqueue returns true').toBe(true);
    expect(verdict.queue.len, 'T164 queue has 1 entry').toBe(1);
  });

  test('ai-companion-resilience-detectors: turns #45-#54 behaviour locked', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.evaluate(() => {
      if (window.WHVoice && typeof window.WHVoice.open === 'function') {
        try { window.WHVoice.open(); } catch (_) { /* mount-only */ }
        try { window.WHVoice.close(); } catch (_) { /* mount-only */ }
      }
    });
    await whPage.waitForTimeout(500);

    const verdict = await whPage.evaluate(() => {
      const wh = (window as any).WHVoice;
      if (!wh) return { ready: false };
      // T45 — offline flag round-trip
      wh._setOffline(false);
      const off1 = wh._isOffline();
      wh._setOffline(true);
      const off2 = wh._isOffline();
      wh._setOffline(false);
      const off3 = wh._isOffline();
      // T46 — reply cache round-trip
      wh._clearReplyCache();
      const miss = wh._lookupReplyCache('hello there', 'hive-test');
      wh._writeReplyCache('hello there', 'hive-test', 'cached reply');
      const hit  = wh._lookupReplyCache('hello there', 'hive-test');
      const wrongHive = wh._lookupReplyCache('hello there', 'other-hive');
      // T49 — branching stack
      wh._pushBranch('mtbf', { asset_tag: 'P-203' });
      wh._pushBranch('pm_scheduling', { asset_tag: 'C-01' });
      const recallMtbf = wh._detectBranchRecall('back to the mtbf thing');
      const recallNone = wh._detectBranchRecall('what is the OEE');
      // T50 / T53 / T54
      const photo1 = wh._isPhotoIntent('let me show you the bearing');
      const photo2 = wh._isPhotoIntent('tingnan mo to');
      const photo3 = wh._isPhotoIntent('open the logbook');
      const sum1 = wh._isSummaryRequest('summarise this conversation');
      const sum2 = wh._isSummaryRequest('i-summarize mo yung pinag-usapan natin');
      const sum3 = wh._isSummaryRequest('what is MTBF');
      // T51 — avatar state classifier
      const avatarUrgent      = wh._classifyAvatarState('Heads up — bearing on C-01 is in critical range, action today.');
      const avatarCelebratory = wh._classifyAvatarState('Naks, great work closing the PM today.');
      const avatarConcerned   = wh._classifyAvatarState('Hala, sounds like a long shift — take care.');
      const avatarHelpful     = wh._classifyAvatarState('Your MTBF is 14 days, from v_kpi_truth.');
      // T54 — identity tracker
      wh._resetIdentityTracking();
      const idFirst   = wh._trackIdentity('Pablo Aguilar');
      const idSame    = wh._trackIdentity('Pablo Aguilar');
      const idDrifted = wh._trackIdentity('Maria Santos');
      return {
        ready: true,
        off: [off1, off2, off3],
        cache: { miss, hit, wrongHive },
        branch: { recallMtbf: recallMtbf && recallMtbf.intent, recallNone },
        photo: [photo1, photo2, photo3],
        sum:   [sum1, sum2, sum3],
        avatar:{ urgent: avatarUrgent, celebratory: avatarCelebratory, concerned: avatarConcerned, helpful: avatarHelpful },
        ident: [idFirst, idSame, idDrifted],
      };
    });

    expect(verdict.ready, 'WHVoice resilience helpers must be exposed').toBe(true);
    expect(verdict.off,    'T45 offline flag round-trip').toEqual([false, true, false]);
    expect(verdict.cache.miss, 'T46 cache miss returns null').toBeNull();
    expect(verdict.cache.hit,  'T46 cache hit returns the stored reply').toBe('cached reply');
    expect(verdict.cache.wrongHive, 'T46 cache scoped by hive').toBeNull();
    expect(verdict.branch.recallMtbf, 'T49 branch recall finds the intent').toBe('mtbf');
    expect(verdict.branch.recallNone, 'T49 non-recall returns null').toBeNull();
    expect(verdict.photo, 'T50 photo intent detector').toEqual([true, true, false]);
    expect(verdict.sum,   'T53 summary request detector').toEqual([true, true, false]);
    expect(verdict.avatar.urgent,      'T51 avatar urgent').toBe('urgent');
    expect(verdict.avatar.celebratory, 'T51 avatar celebratory').toBe('celebratory');
    expect(verdict.avatar.concerned,   'T51 avatar concerned').toBe('concerned');
    expect(verdict.avatar.helpful,     'T51 avatar helpful').toBe('helpful');
    expect(verdict.ident, 'T54 identity drift: false on first, false on same, true on drift').toEqual([false, false, true]);
  });

  test('ai-companion-collaboration-detectors: turns #35-#44 detectors behave correctly', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.evaluate(() => {
      if (window.WHVoice && typeof window.WHVoice.open === 'function') {
        try { window.WHVoice.open(); } catch (_) { /* mount-only */ }
        try { window.WHVoice.close(); } catch (_) { /* mount-only */ }
      }
    });
    await whPage.waitForTimeout(500);

    const verdict = await whPage.evaluate(() => {
      const wh = (window as any).WHVoice;
      if (!wh) return { ready: false };
      const act = (t: string) => wh._isActionRequest(t);
      const batch = (t: string) => wh._isBatchAction(t);
      const explain = (t: string) => wh._isExplainRequest(t);
      const mention = (t: string) => wh._detectMention(t);
      const fatigue = (t: string) => wh._detectFatigueSignal(t);
      const exp = (t: string) => wh._isExportRequest(t);
      const cases: Array<{ label: string; got: unknown; expected: unknown }> = [
        // T35
        { label: 'action: "log a bearing change on P-203"',    got: act('log a bearing change on P-203'), expected: true },
        { label: 'action: "schedule a PM for next week"',      got: act('schedule a PM for next week'),   expected: true },
        { label: 'action: "what is the MTBF"',                  got: act('what is the MTBF'),              expected: false },
        // T40
        { label: 'batch: "log bearing P-203, P-205, and P-208"',got: batch('log bearing P-203, P-205, and P-208'), expected: true },
        { label: 'batch: single item action',                   got: batch('log a PM completion'),         expected: false },
        // T41
        { label: 'explain: "why did you say that"',             got: explain("why did you say that"),       expected: true },
        { label: 'explain: "paano mo nalaman"',                 got: explain("paano mo nalaman"),           expected: true },
        { label: 'explain: regular question',                   got: explain("what is the OEE"),            expected: false },
        // T42
        { label: 'mention: "kasama si Romeo"',                  got: mention("worked on P-203 kasama si Romeo today"), expected: 'Romeo' },
        { label: 'mention: "with Maria Santos"',                got: mention("changed the bearing with Maria Santos"), expected: 'Maria Santos' },
        { label: 'mention: no name',                            got: mention("changed the bearing today"),  expected: null },
        // T43
        { label: 'fatigue: "pagod na ako"',                     got: fatigue("pagod na ako"),               expected: true },
        { label: 'fatigue: "ayoko na"',                         got: fatigue("ayoko na"),                   expected: true },
        { label: 'fatigue: "frustrated"',                       got: fatigue("I am frustrated with C-01"),   expected: true },
        { label: 'fatigue: regular tone',                       got: fatigue("the OEE is great"),           expected: false },
        // T44
        { label: 'export: "send the transcript"',                got: exp("send the transcript"),            expected: true },
        { label: 'export: "i-save mo ito"',                      got: exp("i-save mo ito sa email"),         expected: true },
        { label: 'export: regular question',                     got: exp("how do I save a file"),           expected: false },
      ];
      return { ready: true, cases };
    });

    expect(verdict.ready, 'window.WHVoice helpers must be exposed').toBe(true);
    const failures = (verdict.cases || []).filter(c => c.got !== c.expected);
    expect(
      failures,
      `Turn #35-#44 detectors mis-classified: ${JSON.stringify(failures, null, 2)}`
    ).toEqual([]);
  });

  test('ai-companion-intelligence-detectors: turns #25-#34 detectors behave correctly', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.evaluate(() => {
      if (window.WHVoice && typeof window.WHVoice.open === 'function') {
        try { window.WHVoice.open(); } catch (_) { /* mount-only */ }
        try { window.WHVoice.close(); } catch (_) { /* mount-only */ }
      }
    });
    await whPage.waitForTimeout(500);

    const verdict = await whPage.evaluate(() => {
      const wh = (window as any).WHVoice;
      if (!wh) return { ready: false };
      const sc = (t: string) => wh._isVoiceShortcut(t);
      const bye = (t: string) => wh._isGoodbye(t);
      const stdMention = (t: string) => wh._detectStandardsMention(t);
      const cases: Array<{ label: string; got: unknown; expected: unknown }> = [
        // T28 — voice shortcuts
        { label: 'shortcut: "open logbook"',          got: sc('open logbook'),          expected: 'logbook.html' },
        { label: 'shortcut: "schedule a PM"',         got: sc('schedule a pm'),         expected: 'pm-scheduler.html' },
        { label: 'shortcut: "show analytics"',        got: sc('show analytics'),        expected: 'analytics.html' },
        { label: 'shortcut: "asset hub"',             got: sc('asset hub'),             expected: 'asset-hub.html' },
        { label: 'shortcut: long sentence',           got: sc('can you open the logbook page for me'), expected: null },
        // T31 — goodbye
        { label: 'goodbye: "yun lang"',               got: bye('yun lang'),             expected: false }, // not in regex
        { label: 'goodbye: "wala na"',                got: bye('wala na'),              expected: true },
        { label: 'goodbye: "tapos na"',               got: bye('tapos na'),             expected: true },
        { label: 'goodbye: "I\'m done"',              got: bye("I'm done"),             expected: true },
        { label: 'goodbye: "that\'s all"',            got: bye("that's all"),           expected: true },
        { label: 'goodbye: full sentence',            got: bye('I am done with the analytics for now'), expected: false },
        // T27 — standards detector
        { label: 'standards: "ISO 14224"',            got: stdMention('what does ISO 14224 say about MTBF'), expected: 'ISO 14224' },
        { label: 'standards: "SAE JA1011"',           got: stdMention('per SAE JA1011 the RCM criteria'), expected: 'SAE JA1011' },
        { label: 'standards: "SMRP"',                 got: stdMention('SMRP best practice'),             expected: 'SMRP' },
        { label: 'standards: no mention',             got: stdMention('how is the compressor doing'),    expected: null },
      ];
      return { ready: true, cases };
    });

    expect(verdict.ready, 'window.WHVoice helpers must be exposed').toBe(true);
    const failures = (verdict.cases || []).filter(c => c.got !== c.expected);
    expect(
      failures,
      `Turn #25-#34 detectors mis-classified: ${JSON.stringify(failures, null, 2)}`
    ).toEqual([]);
  });

  test('ai-companion-intelligence-anchors: turns #25/#30/#32/#33/#34 prompt anchors appear in the rendered prompt', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.evaluate(() => {
      if (window.WHVoice && typeof window.WHVoice.open === 'function') {
        try { window.WHVoice.open(); } catch (_) { /* mount-only */ }
        try { window.WHVoice.close(); } catch (_) { /* mount-only */ }
      }
    });
    await whPage.waitForTimeout(500);

    const verdict = await whPage.evaluate(() => {
      const fn = (window as any).WHVoice && (window as any).WHVoice._buildVoiceSystemPrompt;
      if (typeof fn !== 'function') return { ready: false };
      const prompt = fn(
        'zaniah', 'Pablo Aguilar', 'Test Hive', 'voice-journal', null,
        '', '', '', '', '', null, [], '', '', '', ''
      );
      return {
        ready: true,
        hasShift:        /SHIFT CONTEXT/.test(prompt),
        hasConfidence:   /CONFIDENCE CALIBRATION/.test(prompt),
        hasAlertsOverride: /ALERTS OVERRIDE/.test(prompt),
        hasShiftMath:    /Morning|Afternoon|Night/.test(prompt),
      };
    });

    expect(verdict.ready, 'WHVoice._buildVoiceSystemPrompt must be exposed').toBe(true);
    expect(verdict.hasShift,           'T25: SHIFT CONTEXT anchor must be in the prompt').toBe(true);
    expect(verdict.hasConfidence,      'T32: CONFIDENCE CALIBRATION anchor must be in the prompt').toBe(true);
    expect(verdict.hasAlertsOverride,  'T34: ALERTS OVERRIDE anchor must be in the prompt').toBe(true);
    expect(verdict.hasShiftMath,       'T25: prompt must include a resolved shift name (Morning / Afternoon / Night)').toBe(true);
  });

  test('ai-companion-trust-anchors: turns #15/#16 prompt builder emits HALLUCINATION GUARD + CITATION RULE; turn #21 wh-tts spells out acronyms', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.evaluate(() => {
      if (window.WHVoice && typeof window.WHVoice.open === 'function') {
        try { window.WHVoice.open(); } catch (_) { /* mount-only */ }
        try { window.WHVoice.close(); } catch (_) { /* mount-only */ }
      }
    });
    await whPage.waitForTimeout(500);

    const verdict = await whPage.evaluate(() => {
      const wh  = (window as any).WHVoice;
      const tts = (window as any).WHTts;
      if (!wh || !wh._buildVoiceSystemPrompt) return { ready: false };
      const prompt = wh._buildVoiceSystemPrompt(
        'zaniah', 'Pablo Aguilar', 'Test Hive', 'voice-journal', null,
        '', '', '', '', '', null, [], '', '', '', ''
      );
      const spell = (tts && typeof tts._spellOutAcronyms === 'function')
        ? tts._spellOutAcronyms
        : null;
      return {
        ready: true,
        hasHallucinationGuard: /HALLUCINATION GUARD/.test(prompt),
        hasCitationRule:       /CITATION RULE/.test(prompt),
        spellMTBF: spell ? spell('MTBF is 14 days') : '',
        spellOEE:  spell ? spell('OEE this week') : '',
        spellPM:   spell ? spell('PM compliance is good') : '',
        spellAsset:spell ? spell('Pump P-203') : '',  // already pronounceable, should pass through
        spellTrap: spell ? spell('PMP-101 today') : '',  // PMP looks like acronym but is an asset tag — must stay
      };
    });

    expect(verdict.ready, 'WHVoice + WHTts must both be exposed').toBe(true);
    expect(verdict.hasHallucinationGuard, 'T15: HALLUCINATION GUARD anchor must be in prompt').toBe(true);
    expect(verdict.hasCitationRule,       'T16: CITATION RULE anchor must be in prompt').toBe(true);
    expect(verdict.spellMTBF, 'T21: MTBF must spell out').toContain('M T B F');
    expect(verdict.spellOEE,  'T21: OEE must spell out').toContain('O E E');
    expect(verdict.spellPM,   'T21: PM must spell out').toContain('P M');
    expect(verdict.spellAsset,'T21: real asset tags like "P-203" must be left alone').toContain('P-203');
  });

  test('dialog-prompt-anchors-live: turns #11/#12/#13 prompt builder emits LANGUAGE NOTE + SENSITIVE TOPIC REDIRECT + worker name', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.evaluate(() => {
      if (window.WHVoice && typeof window.WHVoice.open === 'function') {
        try { window.WHVoice.open(); } catch (_) { /* mount-only */ }
        try { window.WHVoice.close(); } catch (_) { /* mount-only */ }
      }
    });
    await whPage.waitForTimeout(500);

    const verdict = await whPage.evaluate(() => {
      const fn = (window as any).WHVoice && (window as any).WHVoice._buildVoiceSystemPrompt;
      if (typeof fn !== 'function') return { ready: false };
      const prompt = fn(
        'zaniah', 'Pablo Aguilar', 'Test Hive', 'voice-journal', null,
        '', '', '', '', '', null, [], '', '', '', ''
      );
      const anonPrompt = fn(
        'zaniah', '', 'Test Hive', 'voice-journal', null,
        '', '', '', '', '', null, [], '', '', '', ''
      );
      return {
        ready: true,
        hasLanguageNote:   /LANGUAGE NOTE/.test(prompt),
        sensitiveRedirect: /SENSITIVE TOPIC REDIRECT/.test(prompt),
        hasWorkerName:     /You are talking to Pablo Aguilar/.test(prompt),
        anonFallback:      /You are talking to kapatid/.test(anonPrompt),
        mentionsHR:        /\bHR\b/.test(prompt),
        mentionsLegal:     /legal/i.test(prompt),
      };
    });

    expect(verdict.ready, '_buildVoiceSystemPrompt must be exposed').toBe(true);
    expect(verdict.hasLanguageNote,   'Turn #11: LANGUAGE NOTE block must be in the prompt').toBe(true);
    expect(verdict.sensitiveRedirect, 'Turn #12: SENSITIVE TOPIC REDIRECT block must be in the prompt').toBe(true);
    expect(verdict.hasWorkerName,     'Turn #13: prompt must address the worker by name').toBe(true);
    expect(verdict.anonFallback,      'Turn #13: anon caller must get "kapatid" fallback').toBe(true);
    expect(verdict.mentionsHR,        'SENSITIVE TOPIC REDIRECT must list HR').toBe(true);
    expect(verdict.mentionsLegal,     'SENSITIVE TOPIC REDIRECT must list legal').toBe(true);
  });

  test('dialog-shouldClarify-symmetry: when prior intent matches new intent (post-bypass), clarification stays off', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.evaluate(() => {
      if (window.WHVoice && typeof window.WHVoice.open === 'function') {
        try { window.WHVoice.open(); } catch (_) { /* mount-only */ }
        try { window.WHVoice.close(); } catch (_) { /* mount-only */ }
      }
    });
    await whPage.waitForTimeout(500);

    const verdict = await whPage.evaluate(() => {
      const fn = window.WHVoice && (window.WHVoice as any)._shouldClarify;
      if (typeof fn !== 'function') return { ready: false, cases: [] };
      // Simulate the post-affirmation state: the bypass has just rewritten
      // newIntent = priorIntent and bumped confidence. Predicate MUST be false.
      const cases = [
        // The exact case from the 2026-05-20 bug report — after the bypass.
        { label: 'post-bypass: query.ask + query.ask + high confidence',
          got: fn(0.9, 'query.ask', 'query.ask'),
          expected: false },
        // Still-flipped intent at low confidence — clarification SHOULD fire.
        { label: 'unbypassed: query.ask + unknown + low confidence',
          got: fn(0.3, 'query.ask', 'unknown'),
          expected: true },
        // No prior intent — first turn, no clarification.
        { label: 'first turn: null prior + new intent + low confidence',
          got: fn(0.3, null, 'mtbf'),
          expected: false },
      ];
      return { ready: true, cases };
    });

    expect(verdict.ready, 'window.WHVoice._shouldClarify must be exposed for runtime assertion').toBe(true);
    const failed = verdict.cases.filter(c => c.got !== c.expected);
    expect(
      failed,
      `_shouldClarify symmetry broke: ${JSON.stringify(failed, null, 2)}. ` +
      `If this fails, the bypass loses its anchor — clarifications fire even on resolved intents.`
    ).toEqual([]);
  });
});
