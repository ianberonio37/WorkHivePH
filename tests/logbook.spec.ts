/**
 * logbook.html — UI flow tests.
 *
 * Locks down the 2026-05-12 walkthrough regression: capture-validate.js
 * blocked an insert because `problem` was empty, but the form-submit
 * caller showed "Entry saved" anyway. Worker thought the entry was
 * logged when it wasn't. assertSubmitBlocked() now catches this class
 * forever — if a future change re-introduces the silent-success path,
 * the test FAILs with "forbidden success toast leaked through".
 */
import { test, expect } from './_fixtures';
import {
  assertSubmitSucceeded, assertSubmitBlocked,
  assertRowAppears, waitForPageReady, readToast,
} from './_helpers';

test.describe('logbook.html add-entry flow', () => {
  test('blocks submit when problem field is empty (the 2026-05-12 silent-fail bug)', async ({ whPage }) => {
    await whPage.goto('/logbook.html');
    await waitForPageReady(whPage);

    // Open the add form (most layouts have it expanded by default; this
    // is defensive in case a toggle hides it on small viewports).
    const formToggle = whPage.locator('[aria-controls="log-form"], #toggle-add-form').first();
    if (await formToggle.isVisible().catch(() => false)) {
      await formToggle.click().catch(() => {});
    }

    // Fill ALL required fields EXCEPT problem — the exact shape that
    // caused the original silent-success bug.
    await whPage.fill('#f-machine', 'TEST-SILENT-FAIL-001');
    await whPage.selectOption('#f-category', { label: 'Mechanical' }).catch(() => {});
    await whPage.selectOption('#f-maint-type', { index: 1 }).catch(() => {});
    // f-problem stays empty.

    // Submit
    await whPage.locator('#save-entry, button:has-text("Save Entry"), button[type="submit"]').first().click();

    // Expect a "describe the problem" toast — and CRUCIALLY no "Entry saved" toast.
    await assertSubmitBlocked(whPage, /problem|describe|missing|empty/i);
  });

  test('saves a valid entry and it appears in Mine view', async ({ whPage, testMarker }) => {
    await whPage.goto('/logbook.html');
    await waitForPageReady(whPage);

    const machine = `TEST-OK-${testMarker}`;
    const problem = `Bearing noise during morning startup [${testMarker}]`;

    await whPage.fill('#f-machine', machine);
    await whPage.selectOption('#f-category', { label: 'Mechanical' }).catch(() => {});
    await whPage.selectOption('#f-maint-type', { index: 1 }).catch(() => {});
    await whPage.fill('#f-problem', problem);

    await whPage.locator('#save-entry, button:has-text("Save Entry"), button[type="submit"]').first().click();

    // Success toast appears
    await assertSubmitSucceeded(whPage, /saved|logged|entry/i);

    // And the entry appears in the local Mine view (renderEntries() runs
    // right after the save and rebuilds the list). Search by the unique
    // machine name so we don't match seeded data.
    await assertRowAppears(
      whPage,
      (p) => p.locator(`text=${machine}`),
      undefined,
      8000,
    );
  });

  test('required check fires on machine field too (existing behaviour, regression lock)', async ({ whPage }) => {
    await whPage.goto('/logbook.html');
    await waitForPageReady(whPage);

    // Leave machine empty, fill the others
    await whPage.selectOption('#f-category', { label: 'Mechanical' }).catch(() => {});
    await whPage.selectOption('#f-maint-type', { index: 1 }).catch(() => {});
    await whPage.fill('#f-problem', 'Test missing machine');

    await whPage.locator('#save-entry, button:has-text("Save Entry"), button[type="submit"]').first().click();

    // Machine field gets red border + focus. The page has an inline
    // validation toast OR the field gets aria-invalid. We accept either
    // signal — the key invariant is that NO "Entry saved" toast fires.
    const toast = await readToast(whPage, 2000);
    // If there's a toast, it must NOT say "saved"
    if (toast) {
      expect(toast).not.toMatch(/^(saved|entry saved|added)/i);
    }
    // And the form should still be on screen (not cleared)
    await expect(whPage.locator('#f-problem')).toHaveValue('Test missing machine');
  });
});
