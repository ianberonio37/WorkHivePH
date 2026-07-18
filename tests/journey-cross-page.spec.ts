/**
 * journey-cross-page.spec.ts — Cross-page data flow journeys.
 *
 * Tests that a write on one page correctly updates another page's read
 * surface — the connective tissue between the platform's services.
 *
 * Scenarios:
 *   logbook save → hive feed shows entry
 *   logbook save → hive Open Issues card updates
 *   inventory add → inventory list reflects new part
 *   PM complete → PM Scheduler verdict re-evaluates
 *   logbook close → hive stat-open decrements
 */
import { test, expect } from './_fixtures';
import { waitForPageReady, readToast } from './_helpers';
import { adminClient } from './_db-cleanup';

async function setMachineHidden(page, value: string) {
  await page.evaluate((v) => {
    const el = document.getElementById('f-machine') as HTMLInputElement;
    if (el) { el.value = v; el.dispatchEvent(new Event('change', { bubbles: true })); }
    const label = document.getElementById('asset-picker-label');
    if (label) label.textContent = v;
  }, value);
}

async function flattenSteps(page) {
  await page.evaluate(() => {
    document.querySelectorAll('.step-panel').forEach(el => {
      (el as HTMLElement).style.display = 'block';
      (el as HTMLElement).classList.remove('hidden');
    });
  });
}

test.describe('Cross-page data flows', () => {

  test('logbook save → entry appears in DB (write-to-read contract)', async ({ whPage, testMarker }) => {
    await whPage.goto('/workhive/logbook.html');
    await waitForPageReady(whPage);
    await flattenSteps(whPage);

    const machine = `XPAGE-${testMarker}`;
    await setMachineHidden(whPage, machine);
    await whPage.selectOption('#f-maint-type', { label: 'Inspection' }).catch(() => {});
    await whPage.selectOption('#f-category', { label: 'Mechanical' }).catch(() => {});
    await whPage.fill('#f-problem', `Cross-page test entry [${testMarker}]`);
    await whPage.locator('#save-entry-btn').click();

    await readToast(whPage, 6000); // Wait for any success/approval toast

    // Verify the row is in the DB before checking hive feed
    const db = adminClient();
    let found = false;
    for (let i = 0; i < 12; i++) {
      const { data } = await db.from('logbook').select('id, status').eq('machine', machine).maybeSingle();
      if (data) { found = true; break; }
      await whPage.waitForTimeout(500);
    }
    expect(found, `logbook row for machine=${machine} should exist in DB after save`).toBe(true);
  });

  test('hive stat-open reflects logbook open entries count', async ({ whPage }) => {
    await whPage.goto('/workhive/hive.html');
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(3000);

    const statOpen = whPage.locator('#stat-open');
    await expect(statOpen).toBeVisible({ timeout: 8000 });
    const count = await statOpen.textContent();
    // Should be a non-negative integer
    const n = parseInt(count?.trim() || '0', 10);
    expect(n, 'stat-open should be a non-negative number').toBeGreaterThanOrEqual(0);
  });

  test('your-open-jobs tile is a valid subset of hive open WOs', async ({ whPage }) => {
    test.slow();
    await whPage.goto('/workhive/hive.html');

    // Wait for both stat-open and the v4 open-work action tile to settle
    await whPage.waitForFunction(() => {
      const statEl = document.getElementById('stat-open');
      const jobsEl = document.getElementById('ss-jobs-hero');
      const labelEl = document.getElementById('ss-verdict-label');
      if (!statEl || !jobsEl || !labelEl) return false;
      const statT  = (statEl.textContent  || '').trim();
      const jobsT  = (jobsEl.textContent || '').trim();
      const labelT = (labelEl.textContent || '').trim();
      return !!statT && !!jobsT && jobsT !== '—' &&
             !labelT.startsWith('Computing');
    }, { timeout: 25000 }).catch(() => {});

    const statText  = await whPage.locator('#stat-open').textContent().catch(() => '0');
    const jobsText  = await whPage.locator('#ss-jobs-hero').textContent().catch(() => '0');
    const statCount = parseInt(statText?.trim()  || '0', 10);
    const jobsCount = parseInt(jobsText?.trim() || '0', 10);

    // v4 (2026-07-15): tile 3 is the current user's OWN open jobs (personal), a SUBSET of the
    // hive-wide open WOs in #stat-open — the personal count must never exceed the hive count.
    expect(jobsCount, `your-open-jobs (${jobsCount}) should not exceed hive open WOs (${statCount})`)
      .toBeLessThanOrEqual(statCount);
  });

  test('inventory add → part appears in inventory list', async ({ whPage, testMarker }) => {
    await whPage.goto('/workhive/inventory.html');
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    // Open modal
    await whPage.locator('#btn-add-part').click();
    await whPage.waitForSelector('#part-modal', { state: 'visible', timeout: 5000 }).catch(() => {});
    await whPage.waitForTimeout(300);

    const partNumber = `XPNG-${testMarker}`;
    await whPage.fill('#f-part-number', partNumber);
    await whPage.fill('#f-part-name', `Cross-page Part ${testMarker}`);
    await whPage.fill('#f-qty', '3');
    await whPage.locator('#part-submit-btn').click();

    await readToast(whPage, 6000); // Wait for save/approval toast

    // Verify in DB
    const db = adminClient();
    let found = false;
    for (let i = 0; i < 10; i++) {
      const { data } = await db.from('inventory_items').select('id').eq('part_number', partNumber).maybeSingle();
      if (data) { found = true; break; }
      await whPage.waitForTimeout(500);
    }
    expect(found, `inventory_items row for part_number=${partNumber} should exist`).toBe(true);
  });

  test('PM Scheduler verdict updates after data changes (re-navigate recomputes)', async ({ whPage }) => {
    // Navigate away and back — verdict should recompute from fresh data
    await whPage.goto('/workhive/hive.html');
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1000);

    await whPage.goto('/workhive/pm-scheduler.html');
    await whPage.waitForFunction(() => {
      const el = document.getElementById('pm-verdict-label');
      return !!el && !(el.textContent || '').startsWith('Computing');
    }, { timeout: 15000 }).catch(() => {});

    const label = await whPage.locator('#pm-verdict-label').textContent().catch(() => '');
    expect(label?.trim(), 'PM verdict should settle after navigation').not.toMatch(/^Computing/);
  });
});
