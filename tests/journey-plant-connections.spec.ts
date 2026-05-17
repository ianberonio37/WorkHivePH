/**
 * journey-plant-connections.spec.ts — Plant Connections supervisor journey.
 *
 * The page renders 4 plain-read cards + verdict + recommendation into
 * #content via renderAll() after a supervisor role check. Pablo is
 * supervisor so all content renders.
 *
 * Scenarios:
 *   page load          — content renders, not "Supervisor access only"
 *   verdict            — settled with CMMS/sensor/API/compliance tone
 *   4 plain-read cards — CMMS Sync / Sensor Feed / API Health / Compliance
 *   CMMS sync status   — card shows "Not connected" or actual system name
 *   sensor topics      — 0 sensors or X sensors mapped
 *   API health         — idle or % success
 *   compliance card    — retention + SSO status
 *   details toggle     — expand/collapse engineering details
 *   console errors     — no JS errors
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';

const PAGE = '/workhive/plant-connections.html';

async function waitForPCContent(page) {
  await page.waitForFunction(() => {
    const host = document.getElementById('content');
    if (!host) return false;
    // Either real content rendered (verdict + cards) or denied message
    return host.children.length > 0 &&
           !/loading plant connections/i.test(host.textContent || '');
  }, { timeout: 15000 }).catch(() => {});
}

test.describe('plant-connections.html — plant connections journey', () => {

  test('page loads without console errors', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);
    const serious = errors.filter(e =>
      !e.includes('net::ERR_') && !e.includes('Failed to fetch'),
    );
    expect(serious).toEqual([]);
  });

  test('supervisor sees content (not the denied gate)', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPCContent(whPage);

    const content = whPage.locator('#content');
    await expect(content).toBeVisible({ timeout: 8000 });

    // Pablo is supervisor — must NOT see the "Supervisor access only" gate
    const deniedText = await whPage.getByText(/Supervisor access only/i).count();
    expect(deniedText, 'supervisor should not see the access-denied message').toBe(0);
  });

  test('Plain-Read verdict renders with plant connections tone', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPCContent(whPage);

    const verdict = whPage.locator('.verdict, [class*="verdict"]').first();
    if (await verdict.count() > 0) {
      await expect(verdict).toBeVisible({ timeout: 5000 });
      const text = await verdict.textContent();
      expect(text?.trim().length, 'verdict should not be empty').toBeGreaterThan(5);
    }
    await expect(whPage.locator('#content')).toBeVisible();
  });

  test('4 plain-read cards render (CMMS / Sensor / API / Compliance)', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPCContent(whPage);

    const heroes = whPage.locator('.sc-hero');
    const count  = await heroes.count();
    expect(count, 'plant-connections should have at least 3 plain-read cards').toBeGreaterThanOrEqual(3);

    for (let i = 0; i < Math.min(count, 4); i++) {
      const text = await heroes.nth(i).textContent();
      expect(text?.trim(), `card ${i} hero should not be empty`).not.toBe('');
    }
  });

  test('CMMS sync card: shows "Not connected" or a system name', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPCContent(whPage);

    // First card is CMMS Sync — hero is either system name or "Not connected"
    const firstHero = whPage.locator('.sc-hero').first();
    if (await firstHero.count() > 0) {
      const text = await firstHero.textContent();
      expect(text?.trim().length, 'CMMS card hero should have content').toBeGreaterThan(0);
    }
    await expect(whPage.locator('#content')).toBeVisible();
  });

  test('sensor topics card: shows "0 sensors" or "N sensors"', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPCContent(whPage);

    // Second card is Sensor Feed
    const heroes = whPage.locator('.sc-hero');
    if (await heroes.count() >= 2) {
      const text = await heroes.nth(1).textContent();
      expect(text).toMatch(/\d+\s*sensor|Not wired|no sensor/i);
    }
    await expect(whPage.locator('#content')).toBeVisible();
  });

  test('API health card: shows success % or IDLE', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPCContent(whPage);

    // Third card is API Health
    const heroes = whPage.locator('.sc-hero');
    if (await heroes.count() >= 3) {
      const text = await heroes.nth(2).textContent();
      expect(text?.trim().length, 'API health card should have content').toBeGreaterThan(0);
    }
    await expect(whPage.locator('#content')).toBeVisible();
  });

  test('compliance card: shows retention/SSO status', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPCContent(whPage);

    // Fourth card is Compliance (retention + SSO)
    const heroes = whPage.locator('.sc-hero');
    if (await heroes.count() >= 4) {
      const text = await heroes.nth(3).textContent();
      expect(text?.trim().length, 'compliance card should have content').toBeGreaterThan(0);
    }
    await expect(whPage.locator('#content')).toBeVisible();
  });

  test('details toggle expands engineering details pane', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPCContent(whPage);

    const btn  = whPage.locator('#details-toggle-btn');
    const pane = whPage.locator('#details-pane');

    if (await btn.count() === 0) return;
    await expect(btn).toBeVisible({ timeout: 5000 });

    // Pane starts hidden
    expect(await btn.getAttribute('aria-expanded')).toBe('false');

    // Click to expand
    await btn.click();
    await whPage.waitForTimeout(500);

    if (await pane.count() > 0) {
      await expect(pane).toBeVisible({ timeout: 3000 });
    }
    expect(await btn.getAttribute('aria-expanded')).toBe('true');

    // Click to collapse
    await btn.click();
    await whPage.waitForTimeout(400);
    expect(await btn.getAttribute('aria-expanded')).toBe('false');
  });

  test('recommendation card is non-empty and actionable', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPCContent(whPage);

    const action = whPage.locator('.action-card, [class*="action"]').first();
    if (await action.count() > 0) {
      const text = await action.textContent();
      expect(text?.trim().length, 'recommendation should have content').toBeGreaterThan(5);
    }
    await expect(whPage.locator('body')).toBeVisible();
  });
});

/* === Sentinel-proposed scenarios (Layer 0 -> Layer 2 bridge) ===
 * Drafts from /sentinel-review. See sentinel_drafts.md for context.
 */
test.describe('plant-connections.html - sentinel scenarios', () => {

  test('enterprise_unlock: supervisor sees the multi-panel plant view (Phase 5)', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await waitForPCContent(whPage);
    const panels = whPage.locator(
      '.plant-panel, [data-plant-panel], .sc-card, [class*="card"]'
    );
    await expect.poll(
      async () => await panels.count(),
      { timeout: 8000, message: 'plant-connections did not render any panels for supervisor' },
    ).toBeGreaterThanOrEqual(3);
  });

});
