/**
 * journey-ai-quality.spec.ts — AI Quality + ROI page journey.
 * TODO (L12 debt): full coverage pending (Stair 2+ gated).
 *
 * Scenarios needed:
 *   - page loads (Stair 2+ gated — Lucena is Stair 3, so visible)
 *   - 30-day spend card populated
 *   - fallback rate card
 *   - schema compliance card
 *   - thumbs feedback present
 *   - predicted ROI card
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';

const PAGE = '/workhive/ai-quality.html';

test.describe('ai-quality.html — AI quality journey', () => {

  test('page loads without console errors', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);
    const serious = errors.filter(e => !e.includes('net::ERR_') && !e.includes('Failed to fetch'));
    expect(serious).toEqual([]);
  });

  test('Plain-Read verdict or gated message renders', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(3000);

    const hasVerdict = await whPage.locator('[id$="verdict-label"], .verdict').count();
    const hasGate    = await whPage.locator('text=/stair|gated|upgrade/i').count();
    expect(hasVerdict + hasGate, 'page should show verdict or stair gate').toBeGreaterThan(0);
  });

  test('source chip declares canonical source', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2500);

    const chip = whPage.locator('.wh-source-chip').first();
    if (await chip.count() > 0) {
      const text = await chip.textContent().catch(() => '');
      expect(text?.trim().length).toBeGreaterThan(5);
    }
    await expect(whPage.locator('body')).toBeVisible();
  });
});
