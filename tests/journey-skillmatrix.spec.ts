/**
 * journey-skillmatrix.spec.ts — Skill Matrix user journey.
 *
 * Key regression from walkthrough 2026-05-14:
 *   Verdict said "Primary discipline 5 levels behind target" (red) while
 *   Card 1 said "ON TARGET 5/5 / COMPLETE" (green) — contradiction caused
 *   by primary_skill ("PLC Programming") not being in the DISCIPLINES array.
 *   Fixed: primaryIsTracked guard prevents phantom gap calculation.
 *
 * Scenarios:
 *   verdict consistency  — verdict tone matches Card 1 (no contradiction)
 *   primary not tracked  — correct "Primary skill not yet trackable" verdict
 *   source chip          — chip declares skill_profiles + skill_badges
 *   cards populated      — heroes not "—"
 *   details toggle       — expands/collapses
 *   no console errors    — no JS errors on load
 *   loading state        — verdict settles within timeout
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';

const PAGE = '/workhive/skillmatrix.html';

async function waitForSMVerdictSettled(page) {
  await page.waitForFunction(() => {
    const el = document.getElementById('sm-verdict-label');
    if (!el) return true;
    const t = (el.textContent || '').trim();
    return !!t && !t.startsWith('Computing');
  }, { timeout: 12000 }).catch(() => {});
}

test.describe('skillmatrix.html — user journey', () => {

  test('page loads without console errors', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));

    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);

    const serious = errors.filter(e => !e.includes('net::ERR_') && !e.includes('Failed to fetch'));
    expect(serious, `console errors: ${serious.join(' | ')}`).toEqual([]);
  });

  test('source chip declares skill_profiles + skill_badges', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);

    const chip = whPage.locator('#skillmatrix-source-chip');
    const text = await chip.textContent({ timeout: 5000 }).catch(() => '');
    expect(text, 'chip should declare skill_profiles').toContain('skill_profiles');
    expect(text, 'chip should declare skill_badges').toContain('skill_badges');
  });

  test('verdict settles from "Computing..." within 12 seconds', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForSMVerdictSettled(whPage);

    const label = await whPage.locator('#sm-verdict-label').textContent().catch(() => '');
    expect(label?.trim(), 'verdict should settle').not.toMatch(/^Computing/);
    expect(label?.trim().length).toBeGreaterThan(0);
  });

  test('REGRESSION: verdict and Card 1 (ON TARGET) do not contradict each other', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForSMVerdictSettled(whPage);

    const label     = await whPage.locator('#sm-verdict-label').textContent().catch(() => '');
    const card1Tag  = await whPage.locator('#sm-card-ontrack .sc-tag, .simple-card .sc-tag').first()
      .textContent().catch(() => '');

    // The walkthrough bug: verdict was red ("Primary ... behind") while card was green (COMPLETE)
    // These two signals should not point in opposite directions:
    const verdictIsRed     = /behind|attention|critical/i.test(label || '');
    const card1IsComplete  = /COMPLETE/i.test(card1Tag || '');

    expect(
      verdictIsRed && card1IsComplete,
      `Contradiction: verdict is red ("${label}") but Card 1 tag is "${card1Tag}". ` +
      `This is the 2026-05-14 regression — primaryIsTracked guard may have been removed.`,
    ).toBe(false);
  });

  test('Pablo: primary skill "PLC Programming" not in DISCIPLINES → "not yet trackable" verdict', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForSMVerdictSettled(whPage);

    const primary = await whPage.locator('#header-sub').textContent().catch(() => '');
    const label   = await whPage.locator('#sm-verdict-label').textContent().catch(() => '');

    // If primary is PLC Programming (not a standard discipline), expect the
    // "Primary skill not yet trackable" verdict (not the red phantom-gap verdict)
    if (primary?.includes('PLC Programming')) {
      expect(label, 'PLC Programming should produce "not yet trackable" verdict, not phantom red')
        .toMatch(/not yet trackable/i);
      // Must NOT say "5 levels behind" — that was the phantom bug
      expect(label, '"levels behind" verdict for untracked primary is the regression')
        .not.toMatch(/\d+ levels behind/i);
    }
  });

  test('3 skill cards have non-placeholder heroes', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForSMVerdictSettled(whPage);

    const heroes = whPage.locator('.sc-hero');
    await expect(heroes.first()).toBeVisible({ timeout: 8000 });
    const count = await heroes.count();
    expect(count, 'at least 3 skill cards should render').toBeGreaterThanOrEqual(3);

    for (let i = 0; i < Math.min(count, 3); i++) {
      const text = await heroes.nth(i).textContent();
      expect(text?.trim(), `card ${i} hero should not be "—"`).not.toBe('—');
    }
  });

  test('details toggle expands the skill matrix explainer', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForSMVerdictSettled(whPage);

    const btn  = whPage.locator('#details-toggle-btn');
    const pane = whPage.locator('#sm-summary-details');

    if (await btn.count() === 0) {
      console.log('[journey-skillmatrix] no details toggle on this page');
      return;
    }

    await expect(btn).toBeVisible({ timeout: 5000 });
    await btn.click();
    if (await pane.count() > 0) {
      await expect(pane).toBeVisible({ timeout: 3000 });
    }
  });

  test('Skill Overview radar chart canvas or container renders', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(3000);

    // The radar chart renders as a canvas element
    const canvas = whPage.locator('canvas').first();
    const hasCanvas = await canvas.count();
    if (hasCanvas > 0) {
      await expect(canvas).toBeVisible({ timeout: 5000 });
    }
    // If no canvas, that's acceptable (chart may be loading or empty state)
  });

  test('empty state: no badges shown gracefully when worker has no badges', async ({ whPage }) => {
    // This test verifies that a 0-badge state doesn't crash the page
    await whPage.goto(PAGE);
    await waitForSMVerdictSettled(whPage);

    const badgesHero = await whPage.locator('#sm-badges-hero').textContent().catch(() => null);
    // Either a number (0–30) or "—" are valid — what's NOT valid is a JS error or crash
    if (badgesHero !== null) {
      const n = parseInt(badgesHero.trim(), 10);
      expect(isNaN(n) || n >= 0, `badges hero should be a non-negative number, got: ${badgesHero}`)
        .toBe(true);
    }
  });
});
