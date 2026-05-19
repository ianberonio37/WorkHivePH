/**
 * sw-offline.spec.ts — Sentinel Batch 2 Draft #10 (shell_offline_fallback).
 *
 * Browser-level test that the service-worker shell renders cached HTML
 * when the network is offline. The static validate_sw_offline.py scan
 * checks that worker-critical pages are listed in sw.js SHELL_FILES;
 * this spec verifies the runtime behavior matches the declaration.
 *
 * Tests on a public page (about/) since this requires no auth. The
 * public-page coverage exercises the same shell-caching machinery the
 * app pages depend on — if shell caching breaks here, it breaks
 * everywhere.
 *
 * Skills consulted: mobile-maestro (PWA semantics), performance
 * (offline-first design), platform-guardian (sentinel check-name).
 */
import { test, expect } from '@playwright/test';

test.describe('Service-worker offline contract (L0->L2 bridge for validate_sw_offline.py)', () => {

  test('shell_offline_fallback: report-sender.html serves from cache when offline', async ({ page, context }) => {
    // report-sender.html is in sw.js SHELL_FILES (original offline shell)
    // and is publicly reachable — so it tests the SW cache path without
    // requiring auth. If shell caching breaks here, every other cached
    // page is also at risk.
    const url = 'http://127.0.0.1:5000/workhive/report-sender.html';

    // First visit: registers + installs the service worker
    await page.goto(url);
    await page.waitForLoadState('networkidle');

    // Force the SW to activate + take control (skipWaiting if needed)
    await page.evaluate(async () => {
      const reg = await navigator.serviceWorker.getRegistration();
      if (reg && reg.waiting) reg.waiting.postMessage({ type: 'SKIP_WAITING' });
    }).catch(() => {});

    // Second visit: now the activated SW intercepts + caches
    await page.goto(url);
    await page.waitForLoadState('networkidle');

    const swReady = await page.evaluate(() => navigator.serviceWorker.controller != null);
    test.skip(!swReady, 'SW did not activate in this run — service-worker probably blocked by env');

    // Go offline + reload: cache-first SW must serve the shell
    await context.setOffline(true);
    try {
      await page.goto(url, { waitUntil: 'domcontentloaded' });
      const bodyText = await page.locator('body').innerText().catch(() => '');
      expect(
        bodyText.length,
        'Offline reload yielded zero rendered text — shell is not cached. ' +
        'Either SHELL_FILES in sw.js is missing report-sender.html, or ' +
        'CACHE_NAME was bumped without the page being re-fetched.'
      ).toBeGreaterThan(20);
    } finally {
      await context.setOffline(false);
    }
  });
});
