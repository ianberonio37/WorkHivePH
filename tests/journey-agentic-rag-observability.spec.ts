/**
 * journey-agentic-rag-observability.spec.ts — Phase 8 of AGENTIC_RAG_ROADMAP.md.
 *
 * Probes the observability dashboard:
 *   - Loads without console errors
 *   - Renders the filter bar + summary cards + 3 tables
 *   - Hive gate triggers when no hive is set in localStorage
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';

const PAGE = '/workhive/agentic-rag-observability.html';

test.describe('agentic-rag-observability — Phase 8 of AGENTIC_RAG_ROADMAP.md', () => {

  test('page loads without console errors', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);
    const serious = errors.filter(e =>
      !e.includes('net::ERR_') && !e.includes('Failed to fetch') && !e.includes('NotAllowedError'));
    expect(serious).toEqual([]);
  });

  test('renders filter bar + 3 tables + summary container', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1000);

    await expect(whPage.locator('#filter-window')).toBeVisible();
    await expect(whPage.locator('#filter-route')).toBeVisible();
    await expect(whPage.locator('#filter-apply')).toBeVisible();
    await expect(whPage.locator('#summary-cards')).toBeVisible();
    await expect(whPage.locator('#route-tbl')).toBeVisible();
    await expect(whPage.locator('#heavy-tbl')).toBeVisible();
    await expect(whPage.locator('#recent-tbl')).toBeVisible();
  });

  test('hive gate appears when no hive is set', async ({ whPage }) => {
    await whPage.addInitScript(() => {
      try {
        localStorage.removeItem('wh_active_hive_id');
        localStorage.removeItem('wh_hive_id');
      } catch (_) { /* noop */ }
    });
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(500);
    const gate = whPage.locator('#hive-gate');
    const display = await gate.evaluate(el => getComputedStyle(el).display).catch(() => '');
    expect(display).toBe('flex');
  });

});
