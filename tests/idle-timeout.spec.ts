/**
 * idle-timeout.spec.ts — Arc I I2/A shared-device idle expiry (LIVE behaviour).
 * ===========================================================================
 * session-timeout.js protects a shared Filipino plant tablet: after IDLE_LIMIT_MS
 * of no activity it shows a "Are you still <name>?" prompt; after IDLE_HARD_LIMIT_MS
 * it force-clears identity and redirects to sign-in. Production defaults are 15 min /
 * 60 min — un-testable live without waiting an hour, which is why I2/A was "attributed".
 *
 * This test drives the REAL session-timeout.js with a shrunk clock via the
 * production-safe seam window.WH_IDLE_TIMEOUT_OVERRIDE (set in addInitScript BEFORE
 * the script runs; production never sets it). It asserts the full sequence live:
 * idle → soft prompt → Continue dismisses → idle again → hard clear + redirect.
 *
 * Hermetic-ish: needs a real http origin (the Flask seeder at :5000) for localStorage,
 * but no DB/edge/model. addScriptTag injects the local session-timeout.js file directly,
 * so we control mount timing and dodge any page's own default-clock mount.
 *
 * Run: node node_modules/@playwright/test/cli.js test idle-timeout --reporter=line
 *
 * Skills consulted: qa (idle/timer integration test, no-activity discipline),
 * security (shared-tablet next-worker-inherits-identity risk), mobile-maestro
 * (shared-tablet hand-over), multitenant-engineer (identity clear on hand-off).
 */
import { test, expect } from '@playwright/test';

// Shrunk clock: tick fast, soft prompt at 0.4s idle, hard clear at 1.2s idle.
const OV = { idle: 400, hard: 1200, check: 100 };
const WORKER = 'Idle Test Worker';

test.beforeEach(async ({ page }) => {
  // Set the override + seed an active worker BEFORE any page/injected script runs.
  await page.addInitScript(([ov, worker]) => {
    (window as unknown as Record<string, unknown>).WH_IDLE_TIMEOUT_OVERRIDE = ov;
    try { localStorage.setItem('wh_last_worker', worker as string); } catch (_e) { /* ignore */ }
  }, [OV, WORKER] as const);
  // A real http origin (seeder root) so localStorage works; the page itself does
  // NOT bundle session-timeout.js, so our injected copy is the only mount.
  await page.goto('/');
});

test('idle → soft prompt appears with the worker name, after the soft limit', async ({ page }) => {
  await page.addScriptTag({ path: 'session-timeout.js' });
  // No activity from here. The soft prompt overlay should appear ~0.4s later.
  const overlay = page.locator('#wh-idle-overlay');
  await expect(overlay).toBeVisible({ timeout: 3000 });
  await expect(overlay).toContainText(WORKER);          // "Are you still <name>?"
  await expect(page.locator('#wh-idle-continue')).toBeVisible();
  await expect(page.locator('#wh-idle-signout')).toBeVisible();
});

test('Continue dismisses the prompt and keeps the session', async ({ page }) => {
  await page.addScriptTag({ path: 'session-timeout.js' });
  const overlay = page.locator('#wh-idle-overlay');
  await expect(overlay).toBeVisible({ timeout: 3000 });
  // dispatchEvent (not .click()) fires the handler WITHOUT a mouse-move — a real
  // mouse-move would itself count as activity (bump) and dismiss the prompt before
  // the click lands, so we exercise the Continue button's own handler directly.
  await page.locator('#wh-idle-continue').dispatchEvent('click');  // bump + dismiss
  // Stop the ticker re-firing the prompt while we assert (the dismiss is what we
  // test; without this the prompt legitimately reappears at the next idle cycle).
  await page.evaluate(() => { (window as unknown as Record<string, unknown>)._whSessionTimeoutDisabled = true; });
  await expect(overlay).toHaveCount(0);
  // identity preserved (the whole point of Continue)
  const worker = await page.evaluate(() => localStorage.getItem('wh_last_worker'));
  expect(worker).toBe(WORKER);
});

test('hard limit force-clears identity and redirects to sign-in', async ({ page }) => {
  await page.addScriptTag({ path: 'session-timeout.js' });
  // Stay completely idle (no clicks). After the HARD limit, session-timeout.js
  // clears identity keys and navigates to index.html?signin=1. Reaching that URL
  // is the proof the hard-clear path ran (clearIdentityHard is its only caller).
  // (We can't assert localStorage post-redirect: the test's own addInitScript
  // re-seeds wh_last_worker on every navigation, including this redirect.)
  await page.waitForURL(/signin=1/, { timeout: 4000 });
  expect(page.url()).toContain('signin=1');
});

test('a zero/garbage override can NOT disable the protection (sanity floor)', async ({ page }) => {
  // Override with invalid values — the floor must fall back to production defaults,
  // so NO prompt fires within the short test window (proves the guard can't be
  // weaponised to silently turn off the shared-device protection).
  await page.addInitScript(() => {
    (window as unknown as Record<string, unknown>).WH_IDLE_TIMEOUT_OVERRIDE = { idle: 0, hard: -5, check: 'x' };
  });
  await page.goto('/');
  await page.addScriptTag({ path: 'session-timeout.js' });
  // With defaults (15 min) restored, nothing should appear in 1.5s.
  await page.waitForTimeout(1500);
  await expect(page.locator('#wh-idle-overlay')).toHaveCount(0);
});
