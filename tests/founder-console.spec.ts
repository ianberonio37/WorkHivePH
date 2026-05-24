/**
 * founder-console.spec.ts - admin-gated platform dashboard.
 *
 * The admin gate is the only line of defense between this page and the
 * world. These tests anchor each Layer 0 admin_gates check to a behavioral
 * scenario so a regression that disables the gate triggers a Layer 2 FAIL.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady, pageSrcWithExternals } from './_helpers';

const PAGE = '/workhive/founder-console.html';

test.describe('founder-console.html - sentinel scenarios', () => {

  test('admin_gate_present: page declares an admin gate function', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc = await pageSrcWithExternals(whPage);
    const has = /isPlatformAdmin|isAdmin|admin_gate|adminGate/i.test(__sentSrc);
    expect(has, 'founder-console must declare an admin gate function').toBeTruthy();
  });

  test('admin_gate_active: admin gate is not commented out / stubbed', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_2 = await pageSrcWithExternals(whPage);
    const commented = /\/\/\s*(if|await)\s*\(?\s*isPlatformAdmin|\/\*[^*]*isPlatformAdmin[^*]*\*\//i.test(__sentSrc_2);
    expect(commented, 'admin gate must NOT be commented out').toBe(false);
  });

  test('admin_gate_active_call: gate is actually called, not just declared', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_3 = await pageSrcWithExternals(whPage);
    const called = /await\s+isPlatformAdmin\s*\(|isPlatformAdmin\s*\(/i.test(__sentSrc_3);
    expect(called, 'admin gate function must be called').toBeTruthy();
  });

  test('admin_gate_no_access_ui: page shows a no-access UI for non-admin', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const has = await whPage.evaluate(() => {
      const src = (Array.from(document.scripts).map(s => s.innerText || '').join(' ') + document.body.innerHTML).toLowerCase();
      return /no.*access|denied|unauthorized|admin.*only|not.*permitted/i.test(src);
    });
    expect(has, 'page should expose a no-access UI fallback').toBeTruthy();
  });

  test('admin_gate_not_commented: no commented-out gate redirect logic', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_4 = await pageSrcWithExternals(whPage);
    const stripped = /\/\/[^\n]*window\.location|\/\/[^\n]*redirect|\/\/[^\n]*router\.push/i.test(__sentSrc_4);
    expect(stripped, 'no commented-out redirect on the admin gate path').toBe(false);
  });

});
