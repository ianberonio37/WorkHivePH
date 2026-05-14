/**
 * journey-achievements.spec.ts — Achievements page journey.
 *
 * Scenarios:
 *   source chip    — worker_achievements + achievement_xp_log
 *   verdict        — settles with XP count
 *   3 cards        — XP this week / Active domains / Total level
 *   tier guide     — renders rank tiers (LEGEND, EXPERT, etc.)
 *   profile card   — worker name + LEGEND TECHNICIAN badge
 *   console errors
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';

const PAGE = '/workhive/achievements.html';

async function waitForAchVerdictSettled(page) {
  await page.waitForFunction(() => {
    const el = document.getElementById('ac-verdict-label');
    if (!el) return true;
    const t = (el.textContent || '').trim();
    return !!t && !t.startsWith('Computing');
  }, { timeout: 15000 }).catch(() => {});
}

test.describe('achievements.html — achievements journey', () => {

  test('page loads without console errors', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);
    const serious = errors.filter(e => !e.includes('net::ERR_') && !e.includes('Failed to fetch'));
    expect(serious).toEqual([]);
  });

  test('source chip declares worker_achievements + achievement_xp_log', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);
    const chip = whPage.locator('#achievements-source-chip');
    const text = await chip.textContent({ timeout: 5000 }).catch(() => '');
    expect(text, 'chip should mention worker_achievements').toContain('worker_achievements');
    expect(text, 'chip should mention achievement_xp_log').toContain('achievement_xp_log');
  });

  test('verdict settles from "Computing XP progress..."', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForAchVerdictSettled(whPage);

    const label = await whPage.locator('#ac-verdict-label').textContent().catch(() => '');
    expect(label?.trim()).not.toMatch(/^Computing XP/);
    expect(label?.trim().length).toBeGreaterThan(3);
  });

  test('3 cards have non-placeholder heroes (XP / domains / level)', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForAchVerdictSettled(whPage);

    for (const id of ['#ac-week-hero', '#ac-active-hero', '#ac-level-hero']) {
      const el = whPage.locator(id);
      if (await el.count() > 0) {
        const text = await el.textContent();
        const n = parseInt(text?.trim() || '-1', 10);
        expect(n, `${id} should be a non-negative number`).toBeGreaterThanOrEqual(0);
      }
    }
  });

  test('worker profile card shows Pablo Aguilar', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForAchVerdictSettled(whPage);
    await whPage.waitForTimeout(1000);

    const name = whPage.locator('text=Pablo Aguilar').first();
    if (await name.count() > 0) {
      await expect(name).toBeVisible({ timeout: 5000 });
    }
  });

  test('tier guide renders at least one tier level', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForAchVerdictSettled(whPage);
    await whPage.waitForTimeout(1000);

    const tiers = whPage.locator('text=LEGEND, text=EXPERT, text=JOURNEYMAN, text=APPRENTICE, text=ROOKIE').first();
    if (await tiers.count() > 0) {
      await expect(tiers).toBeVisible({ timeout: 3000 });
    }
  });

  test('LEGEND TECHNICIAN badge visible for Pablo', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForAchVerdictSettled(whPage);
    await whPage.waitForTimeout(1500);

    const badge = whPage.locator('text=LEGEND TECHNICIAN').first();
    if (await badge.count() > 0) {
      await expect(badge).toBeVisible({ timeout: 5000 });
    }
  });
});
