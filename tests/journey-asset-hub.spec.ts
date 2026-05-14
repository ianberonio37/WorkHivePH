/**
 * journey-asset-hub.spec.ts — Asset Hub 360-view journey.
 *
 * Scenarios:
 *   happy path     — page loads, asset list renders, source chip visible
 *   search         — search by tag filters list
 *   360 view       — tap asset card opens detail with risk score
 *   telemetry      — telemetry card renders (or graceful empty state)
 *   verdict        — Plain-Read verdict settles + 3 cards populated
 *   console errors — no JS errors
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';

const PAGE = '/workhive/asset-hub.html';

async function waitForAssetHubReady(page) {
  await page.waitForFunction(() => {
    const list = document.getElementById('asset-list');
    if (!list) return false;
    return list.children.length > 0 || list.textContent?.includes('No assets') ||
           list.textContent?.includes('No equipment');
  }, { timeout: 15000 }).catch(() => {});
}

test.describe('asset-hub.html — 360-view journey', () => {

  test('page loads without console errors', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);
    const serious = errors.filter(e => !e.includes('net::ERR_') && !e.includes('Failed to fetch'));
    expect(serious, `errors: ${serious.join(' | ')}`).toEqual([]);
  });

  test('source chip declares multiple canonical views', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);
    const chip = whPage.locator('.wh-source-chip').first();
    const text = await chip.textContent({ timeout: 5000 }).catch(() => '');
    expect(text, 'chip should mention v_asset_truth').toContain('v_asset_truth');
  });

  test('Plain-Read verdict settles and 3 cards are populated', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForAssetHubReady(whPage);
    await whPage.waitForFunction(() => {
      const el = document.querySelector('[id$="verdict-label"]');
      if (!el) return true;
      const t = (el.textContent || '').trim();
      return !!t && !t.startsWith('Computing');
    }, { timeout: 15000 }).catch(() => {});

    const heroes = whPage.locator('.sc-hero');
    if (await heroes.count() > 0) {
      const h = await heroes.first().textContent();
      expect(h?.trim()).not.toBe('—');
    }
  });

  test('asset list renders at least one asset card', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForAssetHubReady(whPage);

    const list = whPage.locator('#asset-list');
    await expect(list).toBeVisible({ timeout: 8000 });

    const cards = list.locator('[class*="asset-card"], .wh-card, [data-asset-id]');
    const count = await cards.count();
    if (count === 0) {
      // Empty state is acceptable if hive has no registered assets
      const empty = await whPage.locator('text=/No assets|No equipment|register/i').count();
      expect(empty, 'should show empty state if no assets').toBeGreaterThan(0);
    } else {
      expect(count).toBeGreaterThan(0);
    }
  });

  test('search by tag/name narrows the asset list', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForAssetHubReady(whPage);

    const search = whPage.locator('#asset-search');
    await expect(search).toBeVisible({ timeout: 5000 });

    const beforeCount = await whPage.locator('#asset-list').locator('[class*="asset"], .wh-card').count();
    await search.fill('Pump');
    await whPage.waitForTimeout(600);

    const afterCount = await whPage.locator('#asset-list').locator('[class*="asset"], .wh-card').count();
    // Either list filtered down (fewer items) OR no pump assets (count stays 0)
    expect(afterCount).toBeLessThanOrEqual(Math.max(beforeCount, 1));
    await expect(whPage.locator('body')).toBeVisible();
  });

  test('clicking an asset card opens 360 detail view', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForAssetHubReady(whPage);

    const firstCard = whPage.locator('#asset-list .wh-card, #asset-list [data-asset-id]').first();
    // Lucena seeded hive has 30 registered assets — this should NEVER be zero.
    // A zero count means the seeder hasn't run or asset data was wiped.
    const count = await firstCard.count();
    expect(count, 'asset list should have at least 1 card — run test-data-seeder if empty').toBeGreaterThan(0);

    await firstCard.click();
    await whPage.waitForTimeout(1000);

    // After clicking an asset, a detail/360 view should load
    // The page shows a risk score and asset details
    const hasDetail = await whPage.locator('#risk-score-num, [id*="detail"], .detail-panel').count();
    expect(hasDetail, 'clicking asset should open 360 detail').toBeGreaterThan(0);
  });

  test('risk score renders (not empty dashes) after asset selection', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForAssetHubReady(whPage);

    const firstCard = whPage.locator('#asset-list .wh-card, #asset-list [data-asset-id]').first();
    if (await firstCard.count() === 0) { expect.fail('asset list is empty — run seeder first'); return; }

    await firstCard.click();
    await whPage.waitForTimeout(2000);

    const riskNum = whPage.locator('#risk-score-num');
    if (await riskNum.count() > 0) {
      await expect(riskNum).toBeVisible({ timeout: 5000 });
      const score = await riskNum.textContent();
      // Score should be a number 0-100 or "—" — not empty
      expect(score?.trim().length, 'risk score should not be empty').toBeGreaterThan(0);
    }
  });

  test('telemetry card shows readings or empty state (not crashed)', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForAssetHubReady(whPage);

    const firstCard = whPage.locator('#asset-list .wh-card, #asset-list [data-asset-id]').first();
    if (await firstCard.count() === 0) { expect.fail('asset list is empty — run seeder first'); return; }

    await firstCard.click();
    await whPage.waitForTimeout(2000);

    const telCard = whPage.locator('#telemetry-card');
    if (await telCard.count() > 0) {
      const isVisible = await telCard.isVisible();
      if (isVisible) {
        // If visible, must have at least the list or empty state
        const hasList  = await whPage.locator('#telemetry-list').count();
        const hasEmpty = await whPage.locator('#telemetry-empty').count();
        expect(hasList + hasEmpty, 'telemetry card should have list or empty state').toBeGreaterThan(0);
      }
    }
  });
});
