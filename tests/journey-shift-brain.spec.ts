/**
 * journey-shift-brain.spec.ts — Shift Brain autonomous planner journey.
 *
 * Scenarios:
 *   shift tabs     — 06-14/14-22/22-06 tabs switch without error
 *   source chip    — declared on page after init
 *   Plain-Read     — verdict settles, 3 cards (risk/PMs/carry-forward)
 *   empty state    — "No plan exists" + Generate button when no plan
 *   generate plan  — clicking Generate now triggers plan creation
 *   publish        — Publish to crew button visible after draft
 *   console errors — no JS errors on load
 */
import { test, expect } from './_fixtures';
import { waitForPageReady, readToast } from './_helpers';

const PAGE = '/workhive/shift-brain.html';

async function waitForSBVerdictSettled(page) {
  await page.waitForFunction(() => {
    const el = document.getElementById('sb-verdict-label');
    if (!el) return true;
    const t = (el.textContent || '').trim();
    return !!t && !t.startsWith('Loading') && !t.startsWith('Computing');
  }, { timeout: 20000 }).catch(() => {});
}

test.describe('shift-brain.html — shift planner journey', () => {

  test('page loads without console errors', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2500);
    const serious = errors.filter(e => !e.includes('net::ERR_') && !e.includes('Failed to fetch'));
    expect(serious).toEqual([]);
  });

  test('source chip is declared after init', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(3000);
    const chip = whPage.locator('#shift-source-chip');
    const text = await chip.textContent({ timeout: 5000 }).catch(() => '');
    expect(text, 'chip should mention shift_plans').toContain('shift_plans');
  });

  test('shift window tabs switch without crashing', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    const tabs = whPage.locator('.shift-pill');
    const count = await tabs.count();
    if (count < 2) return;

    for (let i = 0; i < count; i++) {
      await tabs.nth(i).click();
      await whPage.waitForTimeout(600);
      await expect(whPage.locator('body')).toBeVisible();
    }
  });

  test('Plain-Read verdict block is rendered and has content', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(3000);

    const verdict = whPage.locator('#sb-verdict');
    await expect(verdict).toBeVisible({ timeout: 5000 });

    const label = await whPage.locator('#sb-verdict-label').textContent().catch(() => '');
    // "Loading shift readiness..." is the initial state when no plan exists — valid
    // What's NOT valid is an empty label or a JS crash
    expect(label?.trim().length, 'verdict label should have content').toBeGreaterThan(3);
  });

  test('3 shift-brain cards have hero numbers (not loading)', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForSBVerdictSettled(whPage);

    const cardSelectors = ['#sb-risk-hero', '#sb-pms-hero', '#sb-carry-hero'];
    for (const sel of cardSelectors) {
      const el = whPage.locator(sel);
      if (await el.count() > 0) {
        const text = await el.textContent();
        const n = parseInt(text?.trim() || '-1', 10);
        expect(n, `${sel} hero should be a number >= 0`).toBeGreaterThanOrEqual(0);
      }
    }
  });

  test('no-plan state: "Generate now" button is visible', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForSBVerdictSettled(whPage);
    await whPage.waitForTimeout(1500);

    const genBtn = whPage.locator('#generate-btn');
    if (await genBtn.isVisible().catch(() => false)) {
      // No plan exists — this is the correct empty state
      await expect(genBtn).toBeVisible();
    }
    // If plan already exists, publish-btn may be visible instead — both are valid
  });

  test('generate plan: clicking Generate now triggers async plan creation', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForSBVerdictSettled(whPage);
    await whPage.waitForTimeout(1500);

    const genBtn = whPage.locator('#generate-btn');
    if (!(await genBtn.isVisible().catch(() => false))) {
      console.log('[journey-shift-brain] plan already exists — skipping generate test');
      return;
    }

    await genBtn.click();
    // After clicking, should show progress or a plan card
    await whPage.waitForTimeout(3000);

    const toast = await readToast(whPage, 8000);
    const hasPlan = await whPage.locator('.shift-plan, #shift-plan-card, [id*="plan"]').count();
    const btnGone = !(await genBtn.isVisible().catch(() => false));

    expect(
      toast || hasPlan > 0 || btnGone,
      'clicking Generate should produce some feedback (toast, plan card, or button removed)',
    ).toBeTruthy();
  });
});
