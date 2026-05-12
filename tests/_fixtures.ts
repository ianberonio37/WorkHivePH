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
import { cleanupByMarker, adminClient } from './_db-cleanup';

const TEST_USERNAME = process.env.WH_TEST_USERNAME || '';   // resolved at first use if empty
const TEST_PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';
const TEST_HIVE_ID  = process.env.WH_TEST_HIVE_ID  || '';
const TEST_HIVE_ROLE = process.env.WH_TEST_HIVE_ROLE || 'supervisor';

let _resolvedUsername: string | null = null;
let _resolvedWorkerName: string | null = null;
let _resolvedHiveId: string | null = null;

/** Look up a real seeded worker's username + display_name + an active
 *  hive_id. Cached per worker so the lookup only hits the DB once. */
async function resolveTestIdentity(): Promise<{ username: string; workerName: string; hiveId: string }> {
  if (_resolvedUsername && _resolvedWorkerName && _resolvedHiveId) {
    return { username: _resolvedUsername, workerName: _resolvedWorkerName, hiveId: _resolvedHiveId };
  }
  const db = adminClient();
  // Prefer the env-provided username; else pick the first seeded worker.
  let username = TEST_USERNAME;
  let workerName = '';
  if (username) {
    const { data } = await db.from('worker_profiles')
      .select('username, display_name').eq('username', username).maybeSingle();
    workerName = data?.display_name || '';
  } else {
    // Fallback: prefer Pablo Aguilar (seeded supervisor), else any worker
    const { data: pablo } = await db.from('worker_profiles')
      .select('username, display_name').eq('display_name', 'Pablo Aguilar').maybeSingle();
    if (pablo?.username) {
      username = pablo.username; workerName = pablo.display_name;
    } else {
      const { data: any1 } = await db.from('worker_profiles')
        .select('username, display_name').limit(1).maybeSingle();
      username = any1?.username || ''; workerName = any1?.display_name || '';
    }
  }
  if (!username) throw new Error('No worker_profiles row — run the test-data-seeder first.');

  // Find an active hive for this worker (env override wins)
  let hiveId = TEST_HIVE_ID;
  if (!hiveId) {
    const { data: hm } = await db.from('hive_members')
      .select('hive_id').eq('worker_name', workerName).eq('status', 'active').limit(1).maybeSingle();
    hiveId = hm?.hive_id || '';
  }

  _resolvedUsername = username;
  _resolvedWorkerName = workerName;
  _resolvedHiveId = hiveId;
  return { username, workerName, hiveId };
}

/** Drive the platform's sign-in modal to get a real Supabase Auth session.
 *  Mirrors test-data-seeder/flows/harness.py#sign_in but in Node. */
async function signIn(page: Page) {
  const { username } = await resolveTestIdentity();
  await page.goto('/workhive/index.html?signin=1', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#signin-modal:not(.hidden)', { timeout: 12000 });
  await page.waitForSelector('#si-username', { state: 'visible', timeout: 5000 });
  await page.waitForTimeout(250);

  await page.click('#si-username'); await page.fill('#si-username', username);
  await page.click('#si-password'); await page.fill('#si-password', TEST_PASSWORD);
  await page.click('#si-btn');

  // Wait for either success (localStorage set) or visible error
  await page.waitForFunction(
    () => localStorage.getItem('wh_last_worker') ||
          (document.getElementById('si-error') &&
           !document.getElementById('si-error')!.classList.contains('hidden')),
    { timeout: 15000 },
  );
  const lastWorker = await page.evaluate(() => localStorage.getItem('wh_last_worker'));
  if (!lastWorker) {
    const err = await page.evaluate(() =>
      (document.getElementById('si-error') as HTMLElement | null)?.textContent || 'unknown');
    throw new Error(`sign-in failed: ${(err || '').trim()}`);
  }
  // Seed active hive context (the platform doesn't auto-pick on signin)
  const { hiveId } = await resolveTestIdentity();
  if (hiveId) {
    await page.evaluate((h) => {
      localStorage.setItem('wh_active_hive_id', h);
      localStorage.setItem('wh_hive_id', h);
    }, hiveId);
  }
}

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

  whPage: async ({ context }, use) => {
    // Pre-seed the hive_role so role-gated UI renders. The real worker
    // name + auth session come from signIn() below.
    await context.addInitScript((role) => {
      try {
        localStorage.setItem('wh_hive_role', role || 'supervisor');
        localStorage.setItem('wh_seen_welcome', '1');
      } catch (_e) {}
    }, TEST_HIVE_ROLE);

    const page = await context.newPage();
    // Real Supabase Auth sign-in so pages that check session.user.id pass
    await signIn(page);
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
