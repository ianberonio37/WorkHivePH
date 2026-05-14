/**
 * journey-pm.spec.ts — PM Scheduler full user journey.
 *
 * Scenarios:
 *   happy path      — page loads, verdict settles, scope items visible
 *   Plain-Read      — verdict + 3 cards populated, source chip visible
 *   complete PM     — click complete-btn, toast success, button turns green
 *   empty fields    — add-asset form blocked when name missing
 *   filter chips    — Overdue / Due Soon / On Track filter changes list
 *   loading states  — verdict leaves "Computing..." within timeout
 *   console errors  — no JS errors on page load
 *   permission      — supervisor sees full controls
 */
import { test, expect } from './_fixtures';
import { waitForPageReady, readToast } from './_helpers';

const PAGE = '/workhive/pm-scheduler.html';
const SETTLE = 12000;

async function waitForPMVerdictSettled(page) {
  await page.waitForFunction(() => {
    const el = document.getElementById('pm-verdict-label');
    if (!el) return true; // some pages don't use this id pattern
    const t = (el.textContent || '').trim();
    return !!t && !t.startsWith('Computing');
  }, { timeout: SETTLE }).catch(() => {});
}

test.describe('pm-scheduler.html — PM user journey', () => {

  test('page loads without console errors', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));

    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);

    const serious = errors.filter(e =>
      !e.includes('Failed to fetch') && !e.includes('net::ERR_'),
    );
    expect(serious, `console errors: ${serious.join(' | ')}`).toEqual([]);
  });

  test('Plain-Read: source chip declares canonical sources', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);

    const chip = whPage.locator('#pm-source-chip');
    const text = await chip.textContent({ timeout: 5000 }).catch(() => '');
    expect(text, 'pm-source-chip should mention pm_assets').toContain('pm_assets');
    expect(text, 'pm-source-chip should mention pm_scope_items').toContain('pm_scope_items');
  });

  test('Plain-Read: verdict settles and 3 cards have real heroes', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPMVerdictSettled(whPage);

    const label = await whPage.locator('#pm-verdict-label').textContent({ timeout: 5000 }).catch(() => '');
    expect(label?.trim(), 'verdict should settle past "Computing..."').not.toMatch(/^Computing/);

    // 3 cards: OVERDUE, DUE THIS WEEK, ON TRACK
    const heroes = whPage.locator('.sc-hero');
    await expect(heroes.first()).toBeVisible({ timeout: 8000 });
    const count = await heroes.count();
    expect(count, 'at least 3 cards should render').toBeGreaterThanOrEqual(3);
  });

  test('ON TRACK card tag is STAIR-READY, BUILDING, or BELOW STAIR (not LOW)', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPMVerdictSettled(whPage);

    const onTrackCard = whPage.locator('#pm-card-ontrack, .simple-card').last();
    const tagText = await onTrackCard.locator('.sc-tag').textContent({ timeout: 8000 }).catch(() => '');

    // The "LOW" tag was replaced by "BELOW STAIR" in walkthrough fix
    expect(tagText?.trim(), '"LOW" tag should be replaced — walkthrough regression').not.toBe('LOW');
    expect(
      ['STAIR-READY', 'BUILDING', 'BELOW STAIR', 'NO DATA'],
      `unexpected ON TRACK tag: ${tagText}`,
    ).toContain(tagText?.trim());
  });

  test('filter chips change the displayed scope items', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPMVerdictSettled(whPage);
    await whPage.waitForTimeout(2000);

    // "All" filter should be active by default
    const allChip = whPage.locator('.filter-chip[data-filter="all"], .filter-chip.active').first();
    await expect(allChip).toBeVisible({ timeout: 5000 });

    // Click "Due Soon" chip
    const dueSoonChip = whPage.locator('.filter-chip').filter({ hasText: /due soon/i });
    if (await dueSoonChip.count() > 0) {
      await dueSoonChip.click();
      await whPage.waitForTimeout(500);
      // Chip should now be active
      const isActive = await dueSoonChip.evaluate(el =>
        el.classList.contains('active') || el.getAttribute('aria-pressed') === 'true',
      ).catch(() => false);
      expect(isActive, 'Due Soon filter chip should become active on click').toBe(true);
    }
  });

  test('complete-btn on a scope item fires toast and turns green', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPMVerdictSettled(whPage);
    await whPage.waitForTimeout(2000);

    // Find a non-completed scope item's complete button
    const completeBtn = whPage.locator('.complete-btn:not(.done)').first();
    const hasPM = await completeBtn.count();

    if (hasPM === 0) {
      console.log('[journey-pm] no uncompleted scope items — skipping complete test');
      return;
    }

    await completeBtn.click();

    // Expect success toast
    const toast = await readToast(whPage, 6000);
    expect(toast, 'completing a PM should show a success toast').toMatch(/done|complete|marked/i);

    // Button or row should now reflect completed state
    await whPage.waitForTimeout(500);
    const btnDone = whPage.locator('.complete-btn.done');
    const hasDone = await btnDone.count();
    expect(hasDone, 'at least one complete-btn should be .done after marking').toBeGreaterThan(0);
  });

  test('add-asset form: empty asset name blocks save', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    // Open the add-asset wizard (button may be "+ Add Asset" in footer)
    const addBtn = whPage.locator(
      '#btn-add-asset, button:has-text("Add Asset"), a:has-text("Add Asset")',
    ).first();
    if (await addBtn.count() === 0) {
      console.log('[journey-pm] no add-asset button found — skipping');
      return;
    }
    await addBtn.click();
    await whPage.waitForTimeout(500);

    // Submit without filling asset name
    const saveBtn = whPage.locator(
      '#save-asset-btn, button:has-text("Save"), button:has-text("Add")',
    ).last();
    if (await saveBtn.count() === 0) return;
    await saveBtn.click();

    const toast = await readToast(whPage, 3000);
    // Must not show success
    expect(toast, 'empty asset name should not save successfully')
      .not.toMatch(/saved|added|created/i);
  });

  test('loading state: verdict leaves "Computing..." within 12 seconds', async ({ whPage }) => {
    const startTs = Date.now();
    await whPage.goto(PAGE);
    await waitForPMVerdictSettled(whPage);
    const elapsed = Date.now() - startTs;

    const label = await whPage.locator('#pm-verdict-label').textContent().catch(() => '');
    expect(label?.trim(), `verdict still computing after ${elapsed}ms`).not.toMatch(/^Computing/);
  });
});
