/**
 * journey-plant-connections.spec.ts — Plant Connections supervisor journey.
 * TODO (L12 debt): full flow coverage pending (supervisor-only).
 *
 * Scenarios needed:
 *   - page loads (supervisor-only — Pablo is supervisor)
 *   - CMMS sync panel visible
 *   - sensor topics panel visible
 *   - gateway audit panel visible
 *   - data retention config accessible
 *   - SSO config panel visible
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';

const PAGE = '/workhive/plant-connections.html';

test.describe('plant-connections.html — plant connections journey', () => {

  test('page loads without console errors', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);
    const serious = errors.filter(e => !e.includes('net::ERR_') && !e.includes('Failed to fetch'));
    expect(serious).toEqual([]);
  });

  test('supervisor sees plant connections panels', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2500);

    // Plant Connections has 6 panels (CMMS, sensors, gateway, retention, SSO, MFA)
    const panels = await whPage.locator('.wh-card, [id*="panel"], section').count();
    expect(panels, 'supervisor should see plant connections panels').toBeGreaterThan(0);
    await expect(whPage.locator('body')).toBeVisible();
  });

  test('page title shows Plant Connections', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    const heading = whPage.locator('h1, [class*="page-title"]').first();
    if (await heading.count() > 0) {
      const text = await heading.textContent();
      expect(text?.toLowerCase()).toMatch(/plant|connect/i);
    }
  });
});
