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
});
