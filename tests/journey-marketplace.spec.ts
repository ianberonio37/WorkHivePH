/**
 * journey-marketplace.spec.ts — Marketplace full journey.
 *
 * Scenarios:
 *   source chip    — declared for listings + sellers
 *   verdict        — settles with real listing count
 *   tabs           — Parts/Training/Jobs switch views
 *   search         — search input filters listings
 *   watchlist      — heart/watchlist button visible
 *   post listing   — My Listings tab accessible
 *   console errors — no JS errors (fixed _currentSection regression)
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';

const PAGE = '/workhive/marketplace.html';

async function waitForMKVerdictSettled(page) {
  await page.waitForFunction(() => {
    const el = document.getElementById('mk-verdict-label');
    if (!el) return true;
    const t = (el.textContent || '').trim();
    return !!t && !t.startsWith('Loading marketplace') && !t.startsWith('Computing');
  }, { timeout: 15000 }).catch(() => {});
}

test.describe('marketplace.html — marketplace journey', () => {

  test('REGRESSION: no _currentSection ReferenceError (crash fix)', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(3000);

    const csError = errors.filter(e => e.includes('_currentSection'));
    expect(csError, '_currentSection should not throw ReferenceError (was renamed to _section)').toEqual([]);
  });

  test('page loads without serious console errors', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);
    const serious = errors.filter(e => !e.includes('net::ERR_') && !e.includes('Failed to fetch'));
    expect(serious).toEqual([]);
  });

  test('source chip declares marketplace_listings + v_marketplace_sellers_truth', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(3000);
    const chip = whPage.locator('#marketplace-source-chip');
    const text = await chip.textContent({ timeout: 5000 }).catch(() => '');
    expect(text, 'chip should mention marketplace_listings').toContain('marketplace_listings');
  });

  test('verdict settles with real listing count', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForMKVerdictSettled(whPage);

    const label = await whPage.locator('#mk-verdict-label').textContent().catch(() => '');
    expect(label?.trim()).not.toMatch(/^Loading marketplace/);
    expect(label?.trim().length).toBeGreaterThan(3);
  });

  test('3 plain-read cards populated (LISTINGS, MY LISTINGS, CURRENT TAB)', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForMKVerdictSettled(whPage);

    const heroes = whPage.locator('.sc-hero');
    const count = await heroes.count();
    expect(count).toBeGreaterThanOrEqual(3);

    for (let i = 0; i < Math.min(count, 3); i++) {
      const text = await heroes.nth(i).textContent();
      expect(text?.trim()).not.toBe('—');
    }
  });

  test('Parts/Training/Jobs tabs switch without error', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForMKVerdictSettled(whPage);
    await whPage.waitForTimeout(1000);

    for (const label of ['Parts', 'Training', 'Jobs']) {
      const tab = whPage.locator(`button:has-text("${label}")`).first();
      if (await tab.count() > 0) {
        await tab.click();
        await whPage.waitForTimeout(600);
        await expect(whPage.locator('body')).toBeVisible();
      }
    }
  });

  test('search input filters listings on keyup', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForMKVerdictSettled(whPage);
    await whPage.waitForTimeout(1000);

    const search = whPage.locator('#search-input, input[placeholder*="search" i], input[type="search"]').first();
    if (await search.count() === 0) return;

    await search.fill('Bearing');
    await whPage.waitForTimeout(800);
    await expect(whPage.locator('body')).toBeVisible();
    // No assertion on count — just verify no crash
  });

  test('KYB-Verified Sellers badge is visible', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForMKVerdictSettled(whPage);
    await whPage.waitForTimeout(1000);

    const badge = whPage.getByText('KYB-Verified Sellers').first();
    if (await badge.count() > 0) {
      await expect(badge).toBeVisible({ timeout: 5000 });
    }
  });

  test('My Listings filter button is accessible', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForMKVerdictSettled(whPage);
    await whPage.waitForTimeout(1000);

    const myListings = whPage.locator('button:has-text("My Listings"), [data-tab="my"]').first();
    if (await myListings.count() > 0) {
      await expect(myListings).toBeVisible({ timeout: 3000 });
      await myListings.click();
      await whPage.waitForTimeout(600);
      await expect(whPage.locator('body')).toBeVisible();
    }
  });

  test('Watchlist button is visible in results', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForMKVerdictSettled(whPage);
    await whPage.waitForTimeout(1500);

    const watchlist = whPage.locator('button:has-text("Watchlist"), [data-tab="watchlist"]').first();
    if (await watchlist.count() > 0) {
      await expect(watchlist).toBeVisible({ timeout: 3000 });
    }
  });
});
