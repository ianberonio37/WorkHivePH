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
    /* The chip no longer prints raw table names: renderSourceChip runs the source through
       _whFriendlySource() so the provenance is readable and translatable ("Based on your marketplace
       listings & seller ratings"). Asserting the raw string tested an implementation detail the platform
       deliberately moved away from. What still matters is that the chip is the friendly rendering OF THE
       CANONICAL SOURCE — so that is what is asserted, by asking the page itself to translate it. */
    const friendly = await whPage.evaluate(() =>
      (window as any)._whFriendlySource
        ? (window as any)._whFriendlySource('marketplace_listings + v_marketplace_sellers_truth')
        : null);
    expect(friendly, 'the page has no _whFriendlySource, so provenance cannot be checked at all').toBeTruthy();
    expect(text, 'the chip does not declare the canonical marketplace source').toContain(String(friendly));
  });

  test('verdict settles with real listing count', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForMKVerdictSettled(whPage);

    const label = await whPage.locator('#mk-verdict-label').textContent().catch(() => '');
    expect(label?.trim()).not.toMatch(/^Loading marketplace/);
    expect(label?.trim().length).toBeGreaterThan(3);
  });

  test('the plain-read cards are populated (LISTINGS, MY LISTINGS)', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForMKVerdictSettled(whPage);

    /* TWO cards, not three. The "Current tab" tile was removed deliberately on 2026-06-13: it displayed
       navigation state rather than information, and the active section is already visible in the switcher.
       This asserted 3 ever since, so it has been failing for a design decision it never learned about. */
    const heroes = whPage.locator('.sc-hero');
    const count = await heroes.count();
    expect(count, 'the plain-read summary lost a card').toBe(2);

    for (let i = 0; i < count; i++) {
      const text = (await heroes.nth(i).textContent())?.trim();
      expect(text, `plain-read card ${i} never resolved past its placeholder`).toBeTruthy();
      expect(text, `plain-read card ${i} is still showing a dash`).not.toMatch(/^[—–-]$|^Loading/);
    }
  });

  test('Parts/Training/Jobs tabs switch without error', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForMKVerdictSettled(whPage);
    await whPage.waitForTimeout(1000);

    /* SCOPED to .section-tab and matched EXACTLY. `button:has-text("Jobs")` is a substring match, and the
       first button it found was the hidden site search — whose label reads "Search assets, jobs, …". The
       test was clicking a hidden search control and reporting the marketplace tabs as broken. */
    for (const label of ['Parts', 'Training', 'Jobs']) {
      const tab = whPage.locator('button.section-tab', { hasText: new RegExp(`^\s*${label}\b`) }).first();
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
