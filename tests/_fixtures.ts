/**
 * Shared Playwright fixtures for WorkHive UI flow tests.
 *
 * Provides:
 *   - `whPage` — pre-authenticated page with localStorage seeded
 *     (wh_last_worker, wh_active_hive_id, wh_hive_role) so the page
 *     skips the signin redirect and lands in the real UI
 *   - `cleanupAfter` — async helper that removes rows created during
 *     a single test (matches by worker_name + a generated test marker)
 *
 * The fixture intentionally uses localStorage seeding rather than
 * going through the real Supabase Auth signup flow because:
 *   - The signin flow is tested separately (auth-migration tests)
 *   - The signup creates synthetic email accounts in cloud auth which
 *     pollutes the user list; localStorage gives us identity reuse
 *   - hive_members + worker_profiles rows are seeded by the
 *     test-data-seeder Flask app; tests just reference them
 *
 * Worker + hive choice: TEST_WORKER and TEST_HIVE_ID env vars.
 * Defaults to the seeded "Pablo Aguilar" worker in the first seeded hive.
 */
import { test as base, expect, Page, BrowserContext } from '@playwright/test';
import { cleanupByMarker } from './_db-cleanup';

const TEST_WORKER = process.env.WH_TEST_WORKER || 'Pablo Aguilar';
const TEST_HIVE_ID = process.env.WH_TEST_HIVE_ID || '';
const TEST_HIVE_ROLE = process.env.WH_TEST_HIVE_ROLE || 'supervisor';

export type WhFixtures = {
  whPage: Page;
  testMarker: string;
};

export const test = base.extend<WhFixtures>({
  /** Unique per-test marker — embedded in 'machine' / 'part_name' /
   *  'title' fields so the cleanup step can find what THIS test created.
   *  After the test finishes (pass OR fail), an admin-client cleanup
   *  sweeps every writable table for rows tagged with this marker. */
  testMarker: async ({}, use, testInfo) => {
    const marker = `WH-PW-${testInfo.workerIndex}-${Date.now().toString(36)}`;
    await use(marker);
    // Best-effort cleanup. Never fail the test on cleanup error — the
    // test already reported its own pass/fail.
    try {
      const result = await cleanupByMarker(marker);
      const tables = Object.keys(result.deleted);
      if (tables.length) {
        console.log(`[cleanup] marker=${marker} deleted:`,
          Object.entries(result.deleted).map(([t, n]) => `${t}=${n}`).join(' '));
      }
    } catch (e) {
      console.warn(`[cleanup] marker=${marker} failed:`, (e as Error).message);
    }
  },

  whPage: async ({ context, baseURL }, use) => {
    // Seed localStorage BEFORE the first navigation so pages skip signin.
    // We attach a script that runs on every new document load.
    await context.addInitScript(({ worker, hive, role }) => {
      try {
        localStorage.setItem('wh_last_worker', worker);
        localStorage.setItem('wh_worker_name', worker);
        localStorage.setItem('workerName', worker);
        if (hive) {
          localStorage.setItem('wh_active_hive_id', hive);
          localStorage.setItem('wh_hive_id', hive);
        }
        if (role) localStorage.setItem('wh_hive_role', role);
        // Disable any first-run modals
        localStorage.setItem('wh_seen_welcome', '1');
      } catch (_e) { /* ignore */ }
    }, { worker: TEST_WORKER, hive: TEST_HIVE_ID, role: TEST_HIVE_ROLE });

    const page = await context.newPage();
    // Capture all console messages so failing tests show what happened
    page.on('console', msg => {
      if (msg.type() === 'error' || msg.text().includes('[capture-')) {
        console.log(`[browser ${msg.type()}] ${msg.text()}`);
      }
    });
    page.on('pageerror', err => {
      console.log(`[browser pageerror] ${err.message}`);
    });
    await use(page);
  },
});

export { expect };
export const TEST_WORKER_NAME = TEST_WORKER;
export const TEST_HIVE = TEST_HIVE_ID;
