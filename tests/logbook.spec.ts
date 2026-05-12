/**
 * logbook.html — UI flow tests.
 *
 * Locks down the 2026-05-12 walkthrough regression: capture-validate.js
 * blocked an insert because `problem` was empty, but the form-submit
 * caller showed "Entry saved" anyway. Worker thought the entry was
 * logged when it wasn't.
 *
 * Real-DOM notes (post-walkthrough markup inspection):
 *   - #f-machine is a HIDDEN input; the user picks an asset via the
 *     #asset-picker-btn modal. Tests bypass the modal by setting the
 *     hidden value directly via evaluate() — that exercises the same
 *     validation + insert path workers hit after the picker closes.
 *   - Save button is #save-entry-btn (not #save-entry).
 *   - Status is a radio group name="f-status"; the "Open" radio is
 *     checked by default, so no test action is needed for status.
 */
import { test, expect } from './_fixtures';
import {
  assertSubmitSucceeded, assertSubmitBlocked,
  assertRowAppears, waitForPageReady, readToast,
} from './_helpers';

async function setMachineHidden(page, value: string) {
  // Simulate the asset-picker selecting an asset by setting the hidden
  // input + firing change so any change listeners run.
  await page.evaluate((v) => {
    const el = document.getElementById('f-machine') as HTMLInputElement;
    if (el) {
      el.value = v;
      el.dispatchEvent(new Event('change', { bubbles: true }));
    }
    // Also update the asset-picker label so the visible-state assertion
    // (if any) doesn't fail
    const label = document.getElementById('asset-picker-label');
    if (label) {
      label.textContent = v;
      (label.style as any).color = 'rgba(255,255,255,0.95)';
    }
  }, value);
}

test.describe('logbook.html add-entry flow', () => {
  test('blocks submit when problem field is empty (the 2026-05-12 silent-fail bug)', async ({ whPage, testMarker }) => {
    await whPage.goto('/logbook.html');
    await waitForPageReady(whPage);

    await setMachineHidden(whPage, `TEST-${testMarker}`);
    await whPage.selectOption('#f-maint-type', { label: 'Breakdown / Corrective' }).catch(() => {});
    await whPage.selectOption('#f-category', { label: 'Mechanical' }).catch(() => {});
    // f-problem stays empty.

    await whPage.locator('#save-entry-btn').click();

    // The exact regression check: error toast appears AND no success
    // toast leaked through.
    await assertSubmitBlocked(whPage, /problem|describe|missing|empty/i);
  });

  test('saves a valid entry and it appears in Mine view', async ({ whPage, testMarker }) => {
    await whPage.goto('/logbook.html');
    await waitForPageReady(whPage);

    const machine = `TEST-OK-${testMarker}`;
    const problem = `Bearing noise during morning startup [${testMarker}]`;

    await setMachineHidden(whPage, machine);
    await whPage.selectOption('#f-maint-type', { label: 'Breakdown / Corrective' }).catch(() => {});
    await whPage.selectOption('#f-category', { label: 'Mechanical' }).catch(() => {});
    await whPage.fill('#f-problem', problem);

    await whPage.locator('#save-entry-btn').click();

    // Success toast — the addEntry() return-value path now lets the
    // caller know whether to show success.
    await assertSubmitSucceeded(whPage, /(saved|logged|entry)/i);

    // The entry shows up in the rendered list right after the save.
    await assertRowAppears(
      whPage,
      (p) => p.locator(`text=${machine}`),
      undefined,
      8000,
    );
  });

  test('no page errors on load (catches inline-script SyntaxError)', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));

    await whPage.goto('/logbook.html');
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    expect(errors, `page errors: ${errors.join(' | ')}`).toEqual([]);
  });
});
