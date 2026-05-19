/**
 * mobile-ux.spec.ts — Sentinel Batch 2 Draft #8 (touch_targets check).
 *
 * Validates the runtime box size of visible CTAs on a public page in a
 * phone viewport. The static validate_mobile.py scan checks CSS source
 * for min-height declarations; this spec catches the case where CSS
 * specificity overrides the declared minimum.
 *
 * Tests on a public page (about/) using rawPage so the spec runs in any
 * environment — no test-data-seeder dependency. Mobile viewport set
 * locally on the test (390×844 = iPhone 14).
 *
 * Skills consulted: mobile-maestro (44px minimum), qa-tester (rawPage
 * preference), platform-guardian (sentinel check-name binding).
 */
import { test, expect } from '@playwright/test';

test.use({ viewport: { width: 390, height: 844 } });

test.describe('Mobile UX contract (L0->L2 bridge for validate_mobile.py)', () => {

  test('touch_targets: visible CTAs on /about/ render at >= 44px tall', async ({ page }) => {
    await page.goto('http://127.0.0.1:5000/workhive/about/');
    // Public marketing page — let JS settle, then measure
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(500);

    // Tappable surfaces: anchor buttons, regular buttons, the FAB.
    // Exclude tiny icon-only chips that legitimately render smaller
    // (none on about/ currently — kept as a future opt-out lane).
    const targets = page.locator('a.btn:visible, button:visible, .wh-fb-fab:visible');
    const count = await targets.count();
    expect(count, '/about/ has no tappable CTAs to measure').toBeGreaterThan(0);

    const undersized: Array<{ label: string; h: number }> = [];
    for (let i = 0; i < count; i++) {
      const el  = targets.nth(i);
      const box = await el.boundingBox();
      if (!box) continue;
      // Tiny invisible-by-style elements: skip
      if (box.width === 0 || box.height === 0) continue;
      if (box.height < 44) {
        const text = (await el.innerText().catch(() => '')).slice(0, 40)
          || (await el.getAttribute('aria-label').catch(() => '')) || '(no label)';
        undersized.push({ label: text.replace(/\s+/g, ' ').trim(), h: box.height });
      }
    }
    expect(
      undersized,
      `${undersized.length} CTA(s) under 44px tall on /about/:\n` +
      undersized.map(u => `  ${u.h.toFixed(1)}px  ${u.label}`).join('\n')
    ).toEqual([]);
  });
});
