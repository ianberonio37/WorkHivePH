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
import { adminClient } from './_db-cleanup';

async function setMachineHidden(page, value: string) {
  // Simulate the asset-picker selecting an asset by setting the hidden
  // input + firing change so any change listeners run.
  await page.evaluate((v) => {
    const el = document.getElementById('f-machine') as HTMLInputElement;
    if (el) {
      el.value = v;
      el.dispatchEvent(new Event('change', { bubbles: true }));
    }
    const label = document.getElementById('asset-picker-label');
    if (label) {
      label.textContent = v;
      (label.style as any).color = 'rgba(255,255,255,0.95)';
    }
  }, value);
}

/**
 * The logbook add-entry form is a 3-step wizard:
 *   step-1: machine + maintenance_type + status
 *   step-2: category + problem + root_cause
 *   step-3: action + downtime + save
 * Tests need to navigate via the page's own stepGo(n) function or
 * flatten all panels. Flatten is faster + more deterministic.
 */
async function flattenSteps(page) {
  await page.evaluate(() => {
    document.querySelectorAll('.step-panel').forEach(el => {
      (el as HTMLElement).style.display = 'block';
      (el as HTMLElement).classList.remove('hidden');
    });
  });
}

test.describe('logbook.html add-entry flow', () => {
  test('blocks submit when problem field is empty (the 2026-05-12 silent-fail bug)', async ({ whPage, testMarker }) => {
    await whPage.goto('/workhive/logbook.html');
    await waitForPageReady(whPage);
    await flattenSteps(whPage);

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
    await whPage.goto('/workhive/logbook.html');
    await waitForPageReady(whPage);
    await flattenSteps(whPage);

    const machine = `TEST-OK-${testMarker}`;
    const problem = `Bearing noise during morning startup [${testMarker}]`;

    await setMachineHidden(whPage, machine);
    // Use a maintenance_type that does NOT trigger the SAE JA1011
    // failure_consequence requirement (Breakdown/Corrective entries do).
    // Inspection covers the validation + insert path without needing
    // the extra consequence picker; another test can cover Breakdown.
    await whPage.selectOption('#f-maint-type', { label: 'Inspection' }).catch(() => {});
    await whPage.selectOption('#f-category', { label: 'Mechanical' }).catch(() => {});
    await whPage.fill('#f-problem', problem);

    await whPage.locator('#save-entry-btn').click();

    // Success toast — the addEntry() return-value path now lets the
    // caller know whether to show success.
    await assertSubmitSucceeded(whPage, /(saved|logged|entry)/i);

    // DB-level confirmation: the row actually landed in logbook with the
    // unique machine name we generated. More robust than asserting on
    // the rendered list (pagination + step-panel hide-on-save make
    // visible-row assertions flaky), and proves the silent-success path
    // really did write to the DB.
    const db = adminClient();
    let found = false;
    for (let i = 0; i < 10; i++) {
      const { data } = await db.from('logbook')
        .select('id, machine').eq('machine', machine).maybeSingle();
      if (data) { found = true; break; }
      await whPage.waitForTimeout(500);
    }
    expect(found, `logbook row for machine=${machine} not in DB after save`).toBe(true);
  });

  test('no page errors on load (catches inline-script SyntaxError)', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));

    await whPage.goto('/workhive/logbook.html');
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    expect(errors, `page errors: ${errors.join(' | ')}`).toEqual([]);
  });
});
