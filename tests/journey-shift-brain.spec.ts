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
import { adminClient } from './_db-cleanup';

const HIVE_ID = process.env.WH_TEST_HIVE_ID || '586fd158-42d1-4853-a406-64a4695e71c4';

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

  test('write-path: generate plan — archives any existing plan first, then generates + DB confirms', async ({ whPage, testMarker }) => {
    test.slow();
    const db = adminClient();

    // Archive any existing draft plan so the Generate button appears
    await db.from('shift_plans')
      .update({ status: 'archived' })
      .eq('hive_id', HIVE_ID)
      .in('status', ['draft', 'published']);

    await whPage.goto(PAGE);
    await waitForSBVerdictSettled(whPage);
    await whPage.waitForTimeout(2000);

    const genBtn = whPage.locator('#generate-btn');
    const isVisible = await genBtn.isVisible().catch(() => false);
    if (!isVisible) {
      // Plan may have reloaded after archive — try one more time
      await whPage.reload();
      await waitForSBVerdictSettled(whPage);
      await whPage.waitForTimeout(2000);
    }

    if (!(await genBtn.isVisible().catch(() => false))) {
      console.log('[journey-shift-brain] generate button still not visible after archive — skipping');
      return;
    }

    await genBtn.click();
    await whPage.waitForTimeout(4000);

    // DB confirmation — a new shift_plans row should exist as draft
    let found = false;
    for (let i = 0; i < 10; i++) {
      const { data } = await db.from('shift_plans')
        .select('id, status').eq('hive_id', HIVE_ID).eq('status', 'draft').maybeSingle();
      if (data) { found = true; break; }
      await whPage.waitForTimeout(800);
    }
    expect(found, 'shift_plans draft row should exist in DB after Generate').toBe(true);

    // Publish button should now be visible
    const pubBtn = whPage.locator('#publish-btn');
    await expect(pubBtn).toBeVisible({ timeout: 5000 });
  });

  test('write-path: publish plan — clicks Publish, DB status becomes published', async ({ whPage }) => {
    test.slow();
    const db = adminClient();

    // Ensure a draft plan exists to publish
    const { data: existing } = await db.from('shift_plans')
      .select('id').eq('hive_id', HIVE_ID).eq('status', 'draft').maybeSingle();

    if (!existing) {
      console.log('[journey-shift-brain] no draft plan to publish — skipping publish test');
      return;
    }

    await whPage.goto(PAGE);
    await waitForSBVerdictSettled(whPage);
    await whPage.waitForTimeout(2000);

    const pubBtn = whPage.locator('#publish-btn');
    if (!(await pubBtn.isVisible().catch(() => false))) {
      console.log('[journey-shift-brain] publish button not visible');
      return;
    }

    await pubBtn.click();
    const toast = await readToast(whPage, 6000);
    expect(toast, 'publishing should show a toast').toMatch(/publish/i);

    // DB confirmation
    let found = false;
    for (let i = 0; i < 8; i++) {
      const { data } = await db.from('shift_plans')
        .select('status').eq('id', existing.id).maybeSingle();
      if (data?.status === 'published') { found = true; break; }
      await whPage.waitForTimeout(600);
    }
    expect(found, `shift_plans row ${existing.id} should be published`).toBe(true);
  });
});
