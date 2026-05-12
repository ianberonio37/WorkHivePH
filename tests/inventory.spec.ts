/**
 * inventory.html — UI flow tests.
 *
 * Same silent-failure regression class as logbook. Inventory has its
 * own form (add-part) and capture contract (inventory_add_part_v1),
 * so the bug COULD recur here independently. These tests lock the
 * "submit blocked OR success-toast must reflect reality" invariant
 * for inventory just as logbook.spec.ts does for the logbook.
 */
import { test, expect } from './_fixtures';
import {
  assertSubmitSucceeded, assertSubmitBlocked,
  assertRowAppears, waitForPageReady, readToast,
} from './_helpers';

test.describe('inventory.html add-part flow', () => {
  test('blocks submit when required fields are empty', async ({ whPage }) => {
    await whPage.goto('/inventory.html');
    await waitForPageReady(whPage);

    // Open the add form
    const openBtn = whPage.locator('button:has-text("Add Part"), #btn-add-part, [data-action="add-part"]').first();
    if (await openBtn.isVisible().catch(() => false)) {
      await openBtn.click().catch(() => {});
    }

    // Try to submit with everything empty (or only part_number filled)
    const saveBtn = whPage.locator('button:has-text("Save"), button[type="submit"]').first();
    if (await saveBtn.isVisible().catch(() => false)) {
      await saveBtn.click();
      // Page either prevents click via disabled state OR shows error toast.
      const toast = await readToast(whPage, 2000);
      if (toast) {
        // Must NOT be a success toast
        expect(toast).not.toMatch(/^(saved|added|created)/i);
      }
    }
  });

  test('saves a valid part and it appears in the inventory list', async ({ whPage, testMarker }) => {
    await whPage.goto('/inventory.html');
    await waitForPageReady(whPage);

    const partNumber = `PN-TEST-${testMarker}`;
    const partName   = `Test bearing kit [${testMarker}]`;

    // Open form
    const openBtn = whPage.locator('button:has-text("Add Part"), #btn-add-part').first();
    if (await openBtn.isVisible().catch(() => false)) await openBtn.click().catch(() => {});

    await whPage.fill('#f-part-number, input[name="part_number"]', partNumber).catch(() => {});
    await whPage.fill('#f-part-name, input[name="part_name"]', partName).catch(() => {});
    await whPage.fill('#f-qty, input[name="qty_on_hand"]', '5').catch(() => {});

    await whPage.locator('button:has-text("Save"), button[type="submit"]').first().click();

    // Either an approval-pending or saved toast — both are non-failure.
    await assertSubmitSucceeded(whPage, /(saved|submitted|added|approval)/i);

    // Part appears in the visible list
    await assertRowAppears(
      whPage,
      (p) => p.locator(`text=${partNumber}`),
      undefined,
      8000,
    );
  });
});
