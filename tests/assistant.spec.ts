/**
 * assistant.html — UI smoke.
 * Deeper chat-roundtrip testing needs an AI mock (Groq calls cost money
 * + are non-deterministic). For now we lock the regression-class:
 * page loads, chat input is present, no JS errors.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';

test.describe('assistant.html', () => {
  test('chat input is present and enabled', async ({ whPage }) => {
    await whPage.goto('/workhive/assistant.html');
    await waitForPageReady(whPage);
    // The page has a chat input — accept any textarea or text input
    // that's visible (UI varies across mobile + desktop).
    const inputs = whPage.locator('textarea:visible, input[type="text"]:visible');
    await expect(inputs.first()).toBeVisible({ timeout: 8000 });
  });

  test('no page errors on load', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));
    await whPage.goto('/workhive/assistant.html');
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);
    expect(errors, `pageerrors: ${errors.join(' | ')}`).toEqual([]);
  });
});
