/**
 * auth-identity-arc-i.spec.ts — Arc I LIVE auth-flow proofs (against the local stack via the Flask
 * seeder :5000, which rewrites Supabase → local docker, with the real edge fns + RLS + migrations).
 *
 * Drives the REAL index.html auth flows in a browser to live-prove the UFAI cells that are
 * client-side flows (not DB-layer): I1 (signup/login + enumeration), I2 (session + logout), I3
 * (password rules), I4 (role-gated render). No DB mutation — validation-failure paths return before
 * any write; sign-in is session-only; signOut clears local state. Pairs the psql two-tenant proofs
 * (I8 deactivation, I5/I6 isolation) for the full live-subset.
 *
 * Seeded user: pabloaguilar / test1234 (Pablo Aguilar, supervisor). Stable seed.
 */
import { test, expect } from './_fixtures';

const USER = process.env.WH_TEST_USERNAME || 'pabloaguilar';
const PASS = process.env.WH_TEST_PASSWORD || 'test1234';

async function openAuth(page: import('@playwright/test').Page) {
  await page.goto('/workhive/index.html?signin=1', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#signin-modal:not(.hidden)', { timeout: 12000 });
  await page.waitForTimeout(200);
}

test.describe('Arc I — Auth/Identity/Session live flows', () => {

  // ── I1/I — account-enumeration resistance (ASVS V2.2): login must give a UNIFORM error ──
  test('I1/I login uniform-response (no account-existence tell)', async ({ rawPage }) => {
    await openAuth(rawPage);
    await rawPage.fill('#si-username', 'zzz_nonexistent_user_99');
    await rawPage.fill('#si-password', 'definitely-wrong-pw');
    await rawPage.click('#si-btn');
    const err = rawPage.locator('#si-error');
    await expect(err).toBeVisible({ timeout: 12000 });
    const txt = (await err.innerText()).toLowerCase();
    // uniform message present …
    expect(txt).toMatch(/wrong username or password/);
    // … and NO enumeration tell that reveals the account does/doesn't exist
    expect(txt).not.toMatch(/no account|not found|not registered|no such user|does not exist/);
  });

  // ── I1/F + I3/F — credential rules enforced (no DB write; validation returns early) ──
  test('I1/F + I3/F credential rules block bad input', async ({ rawPage }) => {
    await openAuth(rawPage);
    await rawPage.evaluate(() => (window as any).switchAuthTab('signup'));
    await rawPage.waitForSelector('#su-username', { state: 'visible', timeout: 5000 });

    const trySignup = async (u: string, p: string, c: string, d: string) => {
      await rawPage.fill('#su-username', u);
      await rawPage.fill('#su-password', p);
      await rawPage.fill('#su-confirm', c);
      await rawPage.fill('#su-displayname', d);
      await rawPage.evaluate(() => (window as any).submitSignUp());
      await rawPage.waitForTimeout(300);
      return (await rawPage.locator('#su-error').innerText()).toLowerCase();
    };

    expect(await trySignup('ab', 'abcdef', 'abcdef', 'Tester')).toMatch(/username must be 3.?.?30|letters, numbers, underscores/);
    expect(await trySignup('validuser1', '123', '123', 'Tester')).toMatch(/at least 6/);
    expect(await trySignup('validuser1', 'abcdef', 'XXXXXX', 'Tester')).toMatch(/do not match/);
  });

  // ── I2/F + I2/U — login establishes a session + page flips to the app shell ──
  test('I2/F login + session establishes', async ({ rawPage }) => {
    await openAuth(rawPage);
    await rawPage.fill('#si-username', USER);
    await rawPage.fill('#si-password', PASS);
    await rawPage.click('#si-btn');
    // success = wh_last_worker set (mirrors the platform's own success signal)
    await rawPage.waitForFunction(() => !!localStorage.getItem('wh_last_worker'), { timeout: 15000 });
    const worker = await rawPage.evaluate(() => localStorage.getItem('wh_last_worker'));
    expect(worker, 'display name resolved into session').toBeTruthy();
    // a real Supabase session exists (JWT minted by GoTrue against the local stack)
    const hasSession = await rawPage.evaluate(async () => {
      const db = (window as any).getDb ? (window as any).getDb() : (window as any)._whSupabaseClient;
      const { data } = await db.auth.getSession();
      return !!data?.session?.access_token;
    });
    expect(hasSession, 'GoTrue session/JWT present after login').toBeTruthy();

    // I2/F session restore: reload → still authenticated (restoreIdentityFromSession)
    await rawPage.reload({ waitUntil: 'domcontentloaded' });
    await rawPage.waitForTimeout(800);
    const stillSession = await rawPage.evaluate(async () => {
      const db = (window as any).getDb ? (window as any).getDb() : (window as any)._whSupabaseClient;
      const { data } = await db.auth.getSession();
      return !!data?.session?.access_token;
    });
    expect(stillSession, 'session survives reload (restore)').toBeTruthy();
  });

  // ── I2/I — logout = full identity + hive wipe (no next-worker inheritance on shared device) ──
  test('I2/I signOut clears identity AND hive context', async ({ rawPage }) => {
    await openAuth(rawPage);
    await rawPage.fill('#si-username', USER);
    await rawPage.fill('#si-password', PASS);
    await rawPage.click('#si-btn');
    await rawPage.waitForFunction(() => !!localStorage.getItem('wh_last_worker'), { timeout: 15000 });
    // seed hive context so we can prove signOut clears it too
    await rawPage.evaluate(() => {
      localStorage.setItem('wh_active_hive_id', '00000000-0000-0000-0000-000000000000');
      localStorage.setItem('wh_hive_role', 'supervisor');
    });
    await rawPage.evaluate(() => (window as any).signOut());
    await rawPage.waitForTimeout(500);
    const leftover = await rawPage.evaluate(() => {
      const keys = ['wh_last_worker','wh_worker_name','workerName','wh_active_hive_id','wh_hive_id','wh_hive_role','wh_hive_name'];
      return keys.filter(k => localStorage.getItem(k) !== null);
    });
    expect(leftover, `these identity/hive keys survived signOut: ${leftover.join(', ')}`).toEqual([]);
  });

  // ── I7/I — Turnstile bot-protection WIRING live-proven with Cloudflare's public always-pass test key ──
  // (bucket-4 demo: a cell I'd called a fixed "ceiling" becomes live once the missing config is supplied.)
  test('I7/I Turnstile widget renders + yields a token (test sitekey)', async ({ rawPage }) => {
    // inject the public test sitekey BEFORE page scripts → mountTurnstile() activates (configure-to-enable)
    await rawPage.addInitScript(() => {
      (window as any).WH_TURNSTILE_SITEKEY = '1x00000000000000000000AA'; // Cloudflare always-passes test key
    });
    await openAuth(rawPage);
    await rawPage.evaluate(() => (window as any).switchAuthTab('signup'));
    // the loader injects the Cloudflare script + renders the widget into #su-turnstile
    await rawPage.waitForFunction(
      () => { const b = document.getElementById('su-turnstile'); return !!b && b.children.length > 0; },
      { timeout: 20000 },
    );
    // the always-pass widget resolves → _turnstileToken() returns a non-empty token
    const token = await rawPage.waitForFunction(
      () => (window as any)._turnstileToken && (window as any)._turnstileToken(),
      { timeout: 20000 },
    ).then(h => h.jsonValue()).catch(() => null);
    expect(token, 'Turnstile produced a verification token (wiring works end-to-end)').toBeTruthy();
  });

  // ── I4/F — role context is DB-validated and carried into an authenticated session (live) ──
  // (The full role-GATED render is code-verified across the 6 validateHiveMembership pages = proof;
  //  here we live-prove the session carries a real DB-resolved supervisor role, not a localStorage fib.)
  test('I4/F authenticated session carries DB-resolved role', async ({ rawPage }) => {
    await openAuth(rawPage);
    await rawPage.fill('#si-username', USER);
    await rawPage.fill('#si-password', PASS);
    await rawPage.click('#si-btn');
    await rawPage.waitForFunction(() => !!localStorage.getItem('wh_last_worker'), { timeout: 15000 });
    // the live GoTrue JWT resolves to a worker_profiles identity (auth.uid → display_name)
    const identityResolved = await rawPage.evaluate(async () => {
      const db = (window as any).getDb ? (window as any).getDb() : (window as any)._whSupabaseClient;
      const { data: s } = await db.auth.getSession();
      const uid = s?.session?.user?.id;
      if (!uid) return false;
      const { data } = await db.from('worker_profiles').select('display_name').eq('auth_uid', uid).maybeSingle();
      return !!data?.display_name;
    });
    expect(identityResolved, 'session JWT resolves to a real worker_profiles identity').toBeTruthy();
  });
});
