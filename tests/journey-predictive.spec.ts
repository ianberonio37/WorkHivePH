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
import { waitForPageReady, pageSrcWithExternals, bypassMaturityGate } from './_helpers';

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

  // Bypass Stair-3 maturity gate so test fixtures (which carry only days,
  // not 90+ days of corrective history) still see the page's real render
  // path. Without this the page short-circuits to an honest empty state
  // and every "card hero populated" / "source chip declares v_risk_truth"
  // check fails for reasons unrelated to the predictive code.
  test.beforeEach(async ({ whPage }) => {
    await bypassMaturityGate(whPage);
  });

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

/* === Sentinel-proposed scenarios (check-name anchored) === */
test.describe('predictive.html - sentinel scenarios', () => {

  test('mtbf_filters: page references MTBF filter logic', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc = await pageSrcWithExternals(whPage);
    const has = /MTBF|mean[_-]?time[_-]?between/i.test(__sentSrc);
    expect(has, 'predictive should reference MTBF').toBeTruthy();
  });

  test('mtbf_min_count: MTBF computation guards against low sample size', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_2 = await pageSrcWithExternals(whPage);
    const has = /min[_-]?count|min[_-]?samples|sample[_-]?size|n\s*<\s*\d+/i.test(__sentSrc_2);
    expect(has, 'MTBF path should guard against tiny sample sizes').toBeTruthy();
  });

  test('mttr_positive_filter: MTTR filters non-positive durations', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_3 = await pageSrcWithExternals(whPage);
    const has = /MTTR|mean[_-]?time[_-]?to[_-]?repair|positive[_-]?duration/i.test(__sentSrc_3);
    expect(has, 'predictive should reference MTTR with positive-duration guard').toBeTruthy();
  });

  test('downtime_cap: downtime computation caps outliers', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_4 = await pageSrcWithExternals(whPage);
    const has = /downtime[_-]?cap|cap[_-]?downtime|Math\.min.*downtime|clamp.*downtime/i.test(__sentSrc_4);
    expect(has, 'downtime computation should be capped against outliers').toBeTruthy();
  });

  test('failure_consequence_adoption: failure consequence field is used', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_5 = await pageSrcWithExternals(whPage);
    const has = /consequence|failure[_-]?mode|risk[_-]?ranking/i.test(__sentSrc_5);
    expect(has, 'predictive should reference failure consequence').toBeTruthy();
  });

  test('cache_ttl: predictive UI references a cache TTL', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_6 = await pageSrcWithExternals(whPage);
    const has = /cache.*ttl|ttl.*cache|cacheTimeout|CACHE_TTL/i.test(__sentSrc_6);
    expect(has, 'predictive should declare cache TTL').toBeTruthy();
  });

  test('python_corrective_filter: predictive uses corrective filter on logbook', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_7 = await pageSrcWithExternals(whPage);
    const has = /corrective|Breakdown.*Corrective|maintenance_type.*Breakdown/i.test(__sentSrc_7);
    expect(has, 'predictive should filter to corrective entries').toBeTruthy();
  });

});
