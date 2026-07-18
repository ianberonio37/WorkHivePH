/**
 * Canonical-reuse + cross-page connectivity locks for the intelligence trio
 * (ASSET_ALERT_SHIFT_DEEP_ARC — Ian's reuse-discipline steer).
 *
 *   1. STOCK-BAND SINGLE SOURCE: window.whStockSeverity (utils.js) is the ONE classifier for
 *      inventory urgency, reading the canonical is_out_of_stock/is_critical_low/is_low_stock
 *      flags — so alert-hub's stock alerts and shift-brain's renderPartsStrip can't drift.
 *   2. ASSET↔ALERT LOOP: asset-hub's detail "View alerts" button emits alert-hub.html?asset=<tag>,
 *      and alert-hub reads ?asset= to focus that asset (F4). Completes the bidirectional loop.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';

test.describe('intelligence reuse + connectivity', () => {
  test('whStockSeverity is the single canonical stock classifier', async ({ whPage }) => {
    await whPage.goto('/workhive/alert-hub.html');
    await waitForPageReady(whPage);
    const r = await whPage.evaluate(() => {
      const fn = (window as any).whStockSeverity;
      if (typeof fn !== 'function') return { ok: false, reason: 'whStockSeverity not on window' };
      // Canonical flags drive the band, independent of raw qty math.
      const out  = fn({ is_out_of_stock: true, qty_on_hand: 5, reorder_point: 4 });   // flag wins over qty
      const crit = fn({ is_critical_low: true, qty_on_hand: 3, reorder_point: 10 });
      const low  = fn({ is_low_stock: true, qty_on_hand: 8, reorder_point: 10 });
      const ok   = fn({ qty_on_hand: 100, reorder_point: 4 });
      // Fallback arithmetic when flags absent.
      const fbOut = fn({ qty_on_hand: 0, reorder_point: 4 });
      return {
        ok: true,
        out: out.severity, outState: out.state,
        crit: crit.severity, low: low.severity,
        okAtRisk: ok.atRisk, fbOut: fbOut.severity,
      };
    });
    expect(r.ok, r.reason).toBeTruthy();
    expect(r.out).toBe('critical');          // is_out_of_stock → critical even though qty(5) > rp(4)
    expect(r.outState).toBe('out');
    expect(r.crit).toBe('high');             // is_critical_low → high
    expect(r.low).toBe('medium');            // is_low_stock → medium
    expect(r.okAtRisk).toBeFalsy();          // healthy stock → not at risk
    expect(r.fbOut).toBe('critical');        // qty<=0 fallback → critical
  });

  test('asset-hub detail emits alert-hub.html?asset= and alert-hub focuses it', async ({ whPage }) => {
    // Open any asset's 360 via the fleet list, then read the View-alerts link.
    await whPage.goto('/workhive/asset-hub.html');
    await waitForPageReady(whPage);
    const firstCard = whPage.locator('#asset-list > *').first();
    await expect(firstCard).toBeVisible({ timeout: 12000 });
    await firstCard.click();
    const link = whPage.locator('#detail-alerts-link');
    await expect(link).toBeVisible({ timeout: 8000 });
    const href = await link.getAttribute('href');
    expect(href, 'View-alerts must deep-link to alert-hub with ?asset=').toMatch(/^alert-hub\.html\?asset=.+/);

    // The destination reads ?asset= (F4) — navigating there must not error and the feed loads.
    const tag = decodeURIComponent((href || '').split('asset=')[1] || '');
    await whPage.goto('/workhive/alert-hub.html?asset=' + encodeURIComponent(tag));
    await waitForPageReady(whPage);
    // Feed renders (the reader is best-effort focus; we assert no crash + feed present).
    await expect(whPage.locator('#feed')).toBeVisible({ timeout: 12000 });
  });
});
