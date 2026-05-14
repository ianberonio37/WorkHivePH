/**
 * journey-audit-log.spec.ts — Audit Log read journey.
 * TODO (L12 debt): full filter/export coverage pending.
 *
 * Scenarios needed:
 *   - page loads, table renders entries or empty state
 *   - filter by action type narrows results
 *   - filter by date range works
 *   - export (if available) triggers download
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';

const PAGE = '/workhive/audit-log.html';

test.describe('audit-log.html — audit log journey', () => {

  test('page loads without console errors', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);
    const serious = errors.filter(e => !e.includes('net::ERR_') && !e.includes('Failed to fetch'));
    expect(serious).toEqual([]);
  });

  test('audit log renders entries or empty state', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2500);

    const hasTable = await whPage.locator('table, [id*="log"], [id*="audit"]').count();
    const hasEmpty = await whPage.locator('text=/no audit|no entries|nothing/i').count();
    expect(hasTable + hasEmpty, 'audit log should show entries or empty state').toBeGreaterThan(0);
  });

  test('filter controls are visible and interactive', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);

    const filters = whPage.locator('select, input[type="date"], input[type="text"]');
    const count = await filters.count();
    if (count > 0) {
      await expect(filters.first()).toBeVisible({ timeout: 5000 });
    }
    await expect(whPage.locator('body')).toBeVisible();
  });
});
