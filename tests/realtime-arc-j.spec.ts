/**
 * realtime-arc-j.spec.ts — Arc J (Realtime) LIVE browser-level proofs.
 *
 * Proves, against the REAL Supabase Realtime stack (local docker, real WS + RLS),
 * the realtime contracts that were previously only "documented":
 *   J5  presence — two same-hive workers see each other live, hive-scoped.
 *   J1/J2 subscription isolation — a client CAN set `filter=<otherHive>`, but RLS
 *         blocks delivery at the realtime layer (the channel name + client filter
 *         are NOT a tenant boundary — the published table's SELECT RLS is).
 *   J3  listener lifecycle — subscribe adds a channel, removeChannel removes it
 *         (no leaked subscription).
 *
 * Requires supabase_realtime_workhive up + the seeder :5000.
 * Seeded workers: hectorsalvador/romeobeltran (Manila hive); Pablo (Lucena hive).
 *
 * Skills: realtime-engineer, multitenant-engineer, security, qa-tester.
 */
import { test, expect, Page } from '@playwright/test';
import { adminClient } from './_db-cleanup';

const BASE = 'http://127.0.0.1:5000/workhive';
const MANILA = process.env.WH_TEST_HIVE_ID || 'ba383fb9-1e76-420e-a8cd-8ecf45bfe5a7'; // Hector + Romeo
const LUCENA = '3792d7f0-59e2-42e6-b04f-6e6ef4e4713d';                                  // foreign hive
const PASS = process.env.WH_TEST_PASSWORD || 'test1234';
const HECTOR = 'hectorsalvador', HECTOR_NAME = 'Hector Salvador';
const ROMEO = 'romeobeltran',   ROMEO_NAME  = 'Romeo Beltran';

async function signInIntoHive(page: Page, username: string, hiveId = MANILA) {
  await page.goto(`${BASE}/index.html?signin=1`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#signin-modal:not(.hidden)', { timeout: 12000 });
  await page.fill('#si-username', username);
  await page.fill('#si-password', PASS);
  await page.click('#si-btn');
  await page.waitForFunction(() => !!localStorage.getItem('wh_last_worker'), { timeout: 15000 });
  await page.evaluate((hid) => {
    localStorage.setItem('wh_active_hive_id', hid);
    localStorage.setItem('wh_hive_id', hid);
    localStorage.setItem('wh_hive_role', 'worker');
  }, hiveId);
  await page.goto(`${BASE}/hive.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#presence-bar', { timeout: 15000 });
  // ensure the page's authenticated singleton client exists (carries Hector's JWT)
  await page.waitForFunction(() => !!(window as any)._whSupabaseClient, { timeout: 10000 });
}

test.describe('Arc J — Realtime LIVE (presence · subscription isolation · lifecycle)', () => {

  test('J5 presence: two same-hive workers see each other live; channel is hive-scoped', async ({ browser }) => {
    const ctxA = await browser.newContext();
    const ctxB = await browser.newContext();
    const a = await ctxA.newPage();
    const b = await ctxB.newPage();
    const errsA: string[] = [];
    a.on('console', m => { if (m.type() === 'error' && !m.text().includes('favicon')) errsA.push(m.text().slice(0, 160)); });
    try {
      await signInIntoHive(a, HECTOR);
      await signInIntoHive(b, ROMEO);
      const romeoChip = a.locator('#presence-bar .presence-chip', { hasText: ROMEO_NAME });
      await expect(romeoChip, `Hector should see Romeo live.\nWS errors: ${errsA.join(' | ') || '(none)'}`)
        .toBeVisible({ timeout: 15000 });
      const selfChip = a.locator('#presence-bar .presence-chip', { hasText: HECTOR_NAME });
      await expect(selfChip).toBeVisible({ timeout: 5000 });
      const names = await a.locator('#presence-bar .presence-chip').allInnerTexts();
      for (const n of names) {
        expect([HECTOR_NAME, ROMEO_NAME].some(known => n.includes(known)),
          `unexpected presence member "${n}" — cross-hive bleed?`).toBeTruthy();
      }
    } finally {
      await ctxA.close(); await ctxB.close();
    }
  });

  // J1/U + J1/I + J2/F — the keystone runtime proof: the client-supplied `filter` is NOT a
  // boundary. Hector (a Manila member) subscribes to logbook INSERTs with filter=<Lucena> — a
  // FOREIGN hive whose UUID he simply types — and a real Lucena row is inserted. Realtime
  // evaluates the SELECT RLS against Hector's JWT (not a member of Lucena) → he receives NOTHING,
  // even though the filter matched. The control (own-hive filter) DOES deliver, proving the probe
  // can detect a delivery (no false-negative).
  test('J1/J2 subscription isolation: filter=<foreignHive> is blocked by RLS; own-hive delivers', async ({ browser }) => {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    const db = adminClient();
    // anomaly_signals is in the supabase_realtime publication + hive-scoped RLS. `machine` is part of
    // its unique key, so a per-run value avoids collisions AND serves as the marker. (logbook is NOT
    // published, so it can't be used here — a separate finding.)
    const tag = `XT-${Date.now().toString(36)}`;
    const foreignRow = { hive_id: LUCENA, machine: `${tag}-foreign` } as any;
    const ownRow     = { hive_id: MANILA, machine: `${tag}-own` } as any;
    try {
      await signInIntoHive(page, HECTOR);
      // Subscribe TWO channels from the page's authenticated client: one filtered to the foreign
      // hive (Lucena), one to the own hive (Manila). Collect what each receives.
      await page.evaluate(({ foreign, own }) => {
        const c = (window as any)._whSupabaseClient;
        (window as any).__foreign = []; (window as any).__own = [];
        c.channel('xt-foreign').on('postgres_changes',
          { event: 'INSERT', schema: 'public', table: 'anomaly_signals', filter: 'hive_id=eq.' + foreign },
          (p: any) => (window as any).__foreign.push(p.new)).subscribe();
        c.channel('xt-own').on('postgres_changes',
          { event: 'INSERT', schema: 'public', table: 'anomaly_signals', filter: 'hive_id=eq.' + own },
          (p: any) => (window as any).__own.push(p.new)).subscribe();
      }, { foreign: LUCENA, own: MANILA });
      await page.waitForTimeout(2500); // let both channels reach SUBSCRIBED

      // Insert a real row in EACH hive via service role (bypasses RLS for the write).
      const insF = await db.from('anomaly_signals').insert(foreignRow); expect(insF.error, 'foreign insert').toBeNull();
      const insO = await db.from('anomaly_signals').insert(ownRow);     expect(insO.error, 'own insert').toBeNull();

      // Own-hive row must arrive (proves the probe detects delivery); foreign must NOT.
      await page.waitForFunction((t) => (window as any).__own.some((r: any) => (r.machine||'').includes(t)),
        `${tag}-own`, { timeout: 10000 });
      await page.waitForTimeout(3000); // give the foreign event ample time to (not) arrive
      const foreignReceived = await page.evaluate(() => (window as any).__foreign.length);
      expect(foreignReceived,
        'RLS must block the foreign-hive subscription at the realtime layer even though the client filter matched')
        .toBe(0);
    } finally {
      await db.from('anomaly_signals').delete().like('machine', `${tag}-%`);
      await ctx.close();
    }
  });

  // J3/U + J3/I — listener lifecycle: subscribe adds a channel; removeChannel removes it (no leak).
  test('J3 listener lifecycle: subscribe adds a channel, removeChannel removes it (no leak)', async ({ browser }) => {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    try {
      await signInIntoHive(page, HECTOR);
      const counts = await page.evaluate(async () => {
        const c = (window as any)._whSupabaseClient;
        const n0 = c.getChannels().length;
        const ch = c.channel('lifecycle-probe').on('postgres_changes',
          { event: 'INSERT', schema: 'public', table: 'logbook' }, () => {});
        await new Promise<void>(res => ch.subscribe(() => res()));
        const n1 = c.getChannels().length;
        await c.removeChannel(ch);
        const n2 = c.getChannels().length;
        return { n0, n1, n2 };
      });
      expect(counts.n1, 'subscribe must register the channel').toBeGreaterThan(counts.n0);
      expect(counts.n2, 'removeChannel must drop the channel (no leaked subscription)').toBeLessThan(counts.n1);
    } finally {
      await ctx.close();
    }
  });

  // J4/U + J4/A — connection-state guard: rtConn() (utils.js) must fire 'offline' if SUBSCRIBED never
  // arrives within the timeout (the silent-freeze guard) and 'live' on SUBSCRIBED. Unit-proven in the
  // real browser runtime (no WS needed — exercises the actual timer/callback logic).
  test('J4 connection-state guard: rtConn() fires offline on timeout and live on SUBSCRIBED', async ({ browser }) => {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    try {
      await signInIntoHive(page, HECTOR);
      const offline = await page.evaluate(() => new Promise<string>((resolve) => {
        const cb = (window as any).rtConn((s: string) => resolve(s), 300); // never call cb → timeout fires
      }));
      expect(offline, 'rtConn must fall back to offline when SUBSCRIBED never arrives').toBe('offline');

      const live = await page.evaluate(() => new Promise<string>((resolve) => {
        const cb = (window as any).rtConn((s: string) => resolve(s), 5000);
        cb('SUBSCRIBED'); // simulate the channel reaching SUBSCRIBED
      }));
      expect(live, 'rtConn must report live on SUBSCRIBED').toBe('live');

      const offline2 = await page.evaluate(() => new Promise<string>((resolve) => {
        const cb = (window as any).rtConn((s: string) => resolve(s), 5000);
        cb('CHANNEL_ERROR'); // error status → offline
      }));
      expect(offline2, 'rtConn must report offline on CHANNEL_ERROR').toBe('offline');
    } finally {
      await ctx.close();
    }
  });
});
