/**
 * dayplanner.html — UI flow tests.
 *
 * Schedule items are written client-side via db.from('schedule_items')
 * .upsert(...) — different code path from logbook's insert. The capture
 * contract schedule_item_v1 was added in Wave 2; validate_capture_*
 * runs at submit. The silent-failure regression class applies here
 * too: if validation blocks the upsert, the toast must reflect that.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady, readToast } from './_helpers';

test.describe('dayplanner.html schedule item flow', () => {
  test('page loads and lists today\'s schedule items', async ({ whPage }) => {
    await whPage.goto('/workhive/dayplanner.html');
    await waitForPageReady(whPage);

    // Page renders some content (specific containers vary by viewport
    // and worker context). Use a permissive check — the body has text.
    await expect(whPage.locator('body')).toBeVisible({ timeout: 8000 });
    // And at least one VISIBLE chunk of meaningful text — accepts "Open Items"
    // (the per-worker queue), "Schedule", or any nav link. Some pages carry
    // sr-only <h1> with these words (visually hidden via clip:rect(0,0,0,0))
    // and Playwright's bare text= matcher picks the first DOM hit; chain
    // :visible to skip the accessibility-only copy.
    // Iterate matches manually because Playwright 1.60 doesn't expose
    // a `filter({ visible: true })` option on Locator.
    const matches = whPage.locator('text=/Open|Schedule|Planner|Today/i');
    await whPage.waitForTimeout(500);
    const total = await matches.count();
    let saw = false;
    for (let i = 0; i < total; i++) {
      if (await matches.nth(i).isVisible()) { saw = true; break; }
    }
    expect(saw, 'at least one visible Open/Schedule/Planner/Today text').toBe(true);
  });

  test('add-item flow does not show a fake "saved" toast on blocked save', async ({ whPage }) => {
    await whPage.goto('/workhive/dayplanner.html');
    await waitForPageReady(whPage);

    // Find an add-item button if present (UI varies by viewport)
    const addBtn = whPage.locator(
      'button:has-text("Add"), button:has-text("+"), [data-action="add-item"]'
    ).first();

    if (!(await addBtn.isVisible().catch(() => false))) {
      test.skip(true, 'No add-item button visible on this layout — skip');
      return;
    }

    await addBtn.click().catch(() => {});

    // Try to submit without filling required title
    const saveBtn = whPage.locator('button:has-text("Save"), button[type="submit"]').first();
    if (await saveBtn.isVisible().catch(() => false)) {
      await saveBtn.click();
      const toast = await readToast(whPage, 2000);
      if (toast) {
        expect(toast).not.toMatch(/^(saved|added|created)/i);
      }
    }
  });
});
