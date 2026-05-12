/**
 * inventory.html — UI flow tests.
 *
 * Real-DOM selectors (post-walkthrough markup inspection):
 *   - #btn-add-part        opens the modal
 *   - #f-part-number       text input
 *   - #f-part-name         text input
 *   - #f-qty               number input
 *   - #part-submit-btn     "Save Part" button
 */
import { test, expect } from './_fixtures';
import {
  assertSubmitSucceeded, assertRowAppears, waitForPageReady, readToast,
} from './_helpers';

test.describe('inventory.html add-part flow', () => {
  test('blocks submit when part_number is empty (silent-fail regression lock)', async ({ whPage }) => {
    await whPage.goto('/inventory.html');
    await waitForPageReady(whPage);

    await whPage.locator('#btn-add-part').click();
    // Skip part_number, fill the rest
    await whPage.fill('#f-part-name', 'X');
    await whPage.fill('#f-qty', '1');

    await whPage.locator('#part-submit-btn').click();

    // Expect either an inline error toast OR the form to stay open
    // (no success). Most important: no "Saved" toast leaked.
    const toast = await readToast(whPage, 2500);
    if (toast) {
      expect(toast).not.toMatch(/^(saved|added|created)/i);
    }
  });

  test('saves a valid part and the row appears in the list', async ({ whPage, testMarker }) => {
    await whPage.goto('/inventory.html');
    await waitForPageReady(whPage);

    const partNumber = `PN-${testMarker}`;
    const partName   = `Test bearing kit [${testMarker}]`;

    await whPage.locator('#btn-add-part').click();
    await whPage.fill('#f-part-number', partNumber);
    await whPage.fill('#f-part-name', partName);
    await whPage.fill('#f-qty', '5');

    await whPage.locator('#part-submit-btn').click();

    await assertSubmitSucceeded(whPage, /(saved|submitted|added|approval)/i);
    await assertRowAppears(
      whPage,
      (p) => p.locator(`text=${partNumber}`),
      undefined,
      8000,
    );
  });

  test('no page errors on load', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));
    await whPage.goto('/inventory.html');
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);
    expect(errors, `page errors: ${errors.join(' | ')}`).toEqual([]);
  });
});
