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

  // A FAILED READ IS NOT AN EMPTY TABLE — the same conflation this suite exists to catch in the
  // product, and it was sitting in the harness. Every lookup below used `const { data }`, discarding
  // `error`, so a read that failed under load produced the identical message as a genuinely unseeded
  // database: "No worker_profiles row — run the test-data-seeder first." Three tests failed with that
  // sentence on 2026-08-05 while `worker_profiles` held 15 rows the whole time, and it sent me to the
  // seeder instead of to the real cause. Retry transient failures, and when it is finally hopeless,
  // say WHICH of the two things happened.
  let lastErr = '';
  const read = async <T>(label: string, run: () => Promise<{ data: T | null; error: any }>) => {
    for (let attempt = 1; attempt <= 3; attempt++) {
      const { data, error } = await run();
      if (!error) return data;
      lastErr = `${label}: ${error.message || error.code || String(error)}`;
      if (attempt < 3) await new Promise(r => setTimeout(r, 400 * attempt));
    }
    return null;
  };

  // Prefer the env-provided username; else pick the first seeded worker.
  let username = TEST_USERNAME;
  let workerName = '';
  if (username) {
    const data = await read('by username', () => db.from('worker_profiles')
      .select('username, display_name').eq('username', username).maybeSingle());
    workerName = (data as any)?.display_name || '';
  } else {
    // Fallback: prefer Pablo Aguilar (seeded supervisor), else any worker
    const pablo: any = await read('by display_name', () => db.from('worker_profiles')
      .select('username, display_name').eq('display_name', 'Pablo Aguilar').maybeSingle());
    if (pablo?.username) {
      username = pablo.username; workerName = pablo.display_name;
    } else {
      const any1: any = await read('any worker', () => db.from('worker_profiles')
        .select('username, display_name').limit(1).maybeSingle());
      username = any1?.username || ''; workerName = any1?.display_name || '';
    }
  }
  if (!username) {
    // Ask the question the two cases answer differently: is the table empty, or could we not read it?
    const { count, error: countErr } = await db.from('worker_profiles')
      .select('username', { count: 'exact', head: true });
    if (countErr || count === null) {
      throw new Error(
        `could not READ worker_profiles (${lastErr || countErr?.message || 'unknown'}) — this is a ` +
        `failed read, NOT an unseeded database. Check the stack is up and not under load before ` +
        `reaching for the seeder.`);
    }
    if (count === 0) throw new Error('worker_profiles is genuinely EMPTY — run the test-data-seeder.');
    throw new Error(
      `worker_profiles holds ${count} row(s) but none matched` +
      (TEST_USERNAME ? ` username="${TEST_USERNAME}"` : ' the fallback lookups') +
      `${lastErr ? ` (last read error: ${lastErr})` : ''} — a fixture/identity mismatch, not a seeding gap.`);
  }

  // Find an active hive for this worker (env override wins).
  // PREFER THE HIVE WHERE THEY ARE A SUPERVISOR, and order deterministically. The fixture
  // force-seeds wh_hive_role='supervisor' below, but this lookup used to take limit(1) with no
  // role filter and no ORDER BY — and the seeded Pablo Aguilar holds TWO active memberships
  // (supervisor @ Lucena Pharmaceutical, worker @ Manila Electronics). Whenever the arbitrary row
  // came back as the WORKER one, the page correctly resolved the real role for that hive and hid
  // the supervisor-only UI, so `#supervisor-summary` / `#adoption-card` stayed hidden and the specs
  // failed against a page that was behaving exactly as it should.
  let hiveId = TEST_HIVE_ID;
  if (!hiveId) {
    const { data: rows } = await db.from('hive_members')
      .select('hive_id, role').eq('worker_name', workerName).eq('status', 'active')
      .order('role', { ascending: true })      // 'supervisor' > 'worker' handled explicitly below
      .order('hive_id', { ascending: true });  // stable tie-break: never arbitrary
    const sup = (rows || []).find(r => r.role === 'supervisor');
    hiveId = (sup?.hive_id || rows?.[0]?.hive_id || '') as string;
  }

  _resolvedUsername = username;
  _resolvedWorkerName = workerName;
  _resolvedHiveId = hiveId;
  return { username, workerName, hiveId };
}

/** Drive the platform's sign-in modal to get a real Supabase Auth session.
 *  Mirrors test-data-seeder/flows/harness.py#sign_in but in Node. */
// A SIGN-IN THAT FAILS ONCE IS NOT A PRODUCT SIGNAL, AND IT MUST NOT BECOME 26 OF THEM.
// A 43-test run reported 27 failures on 2026-08-05; 26 carried one identical error — this function's
// wait timing out — and none of the oracles beneath them ever ran. The cause was a crash-looping
// sidecar (supabase_vector_workhive, 1,898 restarts) starving the stack, and every test paid for it
// separately because each one signs in from scratch. The sidecar is stopped; this is the belt to go
// with it. One retry, with the browser state cleared between attempts so the second try is genuinely
// fresh rather than a repeat against a half-signed-in page.
async function signIn(page: Page) {
  try {
    return await signInOnce(page);
  } catch (first) {
    await page.evaluate(() => { try { localStorage.clear(); sessionStorage.clear(); } catch (_e) {} })
      .catch(() => {});
    await page.waitForTimeout(1500);
    try {
      return await signInOnce(page);
    } catch (second) {
      throw new Error(
        `sign-in failed twice — this is the HARNESS, not the surface under test. ` +
        `first: ${(first as Error).message}; second: ${(second as Error).message}`);
    }
  }
}

async function signInOnce(page: Page) {
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
  rawPage: Page;   // unauthenticated — for auth-flow tests
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

  /** Raw unauthenticated page — localStorage empty, no sign-in.
   *  Use for testing auth flows (sign-in modal, redirects, etc.). */
  rawPage: async ({ browser }, use) => {
    const ctx  = await browser.newContext();
    const page = await ctx.newPage();
    page.on('console', msg => {
      if (msg.type() === 'error') console.log(`[raw ${msg.type()}] ${msg.text()}`);
    });
    await use(page);
    await ctx.close();
  },
});

export { expect };
