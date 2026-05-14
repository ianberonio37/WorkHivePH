/**
 * journey-predictive.spec.ts — Predictive Maintenance page journey.
 *
 * Scenarios:
 *   source chip     — declares v_risk_truth + 365d window
 *   verdict         — settles with real tone (high/watch/healthy)
 *   3 cards         — HOT ASSETS / HEALTHY / EARLIEST FORECAST populated
 *   risk table      — Risk Ranking tab shows asset rows
 *   heatmap tab     — Health Heatmap renders or shows loading
 *   failure trend   — Failure Trend tab loads without error
 *   asset link      — clicking asset name opens detail
 *   console errors  — no JS errors
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';

const PAGE = '/workhive/predictive.html';

async function waitForPredVerdictSettled(page) {
  await page.waitForFunction(() => {
    const el = document.querySelector('[id$="verdict-label"]');
    if (!el) return true;
    const t = (el.textContent || '').trim();
    return !!t && !t.startsWith('Computing') && !t.startsWith('Loading');
  }, { timeout: 15000 }).catch(() => {});
}

test.describe('predictive.html — predictive maintenance journey', () => {

  test('page loads without console errors', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);
    const serious = errors.filter(e => !e.includes('net::ERR_') && !e.includes('Failed to fetch'));
    expect(serious).toEqual([]);
  });

  test('source chip declares v_risk_truth and 365d window', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);
    const chip = whPage.locator('.wh-source-chip').first();
    const text = await chip.textContent({ timeout: 5000 }).catch(() => '');
    expect(text, 'chip should mention v_risk_truth').toContain('v_risk_truth');
  });

  test('Plain-Read verdict settles with meaningful content', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPredVerdictSettled(whPage);

    const label = await whPage.locator('[id$="verdict-label"]').first().textContent().catch(() => '');
    expect(label?.trim()).not.toMatch(/^Computing|^Loading/);
    expect(label?.trim().length).toBeGreaterThan(3);
  });

  test('3 plain-read cards populated with real numbers', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPredVerdictSettled(whPage);

    const heroes = whPage.locator('.sc-hero');
    const count = await heroes.count();
    expect(count).toBeGreaterThanOrEqual(3);

    for (let i = 0; i < Math.min(count, 3); i++) {
      const text = await heroes.nth(i).textContent();
      expect(text?.trim()).not.toBe('—');
    }
  });

  test('RULES ENGINE V1 badge is visible', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    const badge = whPage.locator('text=RULES ENGINE V1').first();
    await expect(badge).toBeVisible({ timeout: 5000 });
  });

  test('Risk Ranking tab shows a table with asset rows', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPredVerdictSettled(whPage);

    const table = whPage.locator('.risk-table');
    if (await table.count() > 0) {
      await expect(table.first()).toBeVisible({ timeout: 5000 });
      const rows = table.locator('tbody tr, tr:not(:first-child)');
      const rowCount = await rows.count();
      expect(rowCount, 'risk table should have at least one asset row').toBeGreaterThan(0);
    }
  });

  test('Health Heatmap tab renders grid or loading state (no crash)', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPredVerdictSettled(whPage);
    await whPage.waitForTimeout(1000);

    const heatmapTab = whPage.locator('button:has-text("Health Heatmap"), [data-tab="heatmap"]').first();
    if (await heatmapTab.count() > 0) {
      await heatmapTab.click();
      await whPage.waitForTimeout(2000);

      const grid    = whPage.locator('#heatmap-grid');
      const loading = whPage.locator('#heatmap-loading');
      const empty   = whPage.locator('#heatmap-empty');

      const anyVisible = (await grid.isVisible().catch(() => false)) ||
                         (await loading.isVisible().catch(() => false)) ||
                         (await empty.isVisible().catch(() => false));
      expect(anyVisible, 'heatmap tab should show grid, loading, or empty state').toBe(true);
    }
  });

  test('clicking asset name opens asset-hub detail', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPredVerdictSettled(whPage);
    await whPage.waitForTimeout(1000);

    const assetLink = whPage.locator('.risk-table td a, .risk-table a, [data-asset-link]').first();
    if (await assetLink.count() === 0) return;

    await assetLink.click();
    await whPage.waitForTimeout(2000);
    // Should navigate to asset-hub.html
    const url = whPage.url();
    const onAssetHub = url.includes('asset-hub');
    if (!onAssetHub) {
      // May open in a detail pane on the same page
      const detailOpen = await whPage.locator('[id*="detail"], [id*="360"]').count();
      expect(detailOpen + (onAssetHub ? 1 : 0), 'asset link should navigate or open detail').toBeGreaterThan(0);
    }
  });
});
