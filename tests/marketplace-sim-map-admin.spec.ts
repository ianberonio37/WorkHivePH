/**
 * marketplace-sim-map-admin.spec.ts — the MAP and ADMIN tiers of the marketplace simulation registry.
 *
 * Ian asked for the realtime-map leg specifically, and it was the registry's thinnest family before this.
 * The map here is TRACKING-ONLY by design — MapLibre is 800KB and is deliberately kept off the listings
 * critical path, loading on first Track press — so these assertions hold that DESIGN honest rather than
 * testing for a discovery map that was never built. Two of them exist only because the design is easy to
 * break by accident: someone adds a map to the hail path "for convenience" and every 3G user pays.
 *
 * The admin tier is the founder's money surface. It had exactly ONE scenario before, on the page where
 * money is actually decided — the console must not lie, and the four numbers must arrive by themselves.
 */
import { test, expect, Page } from '@playwright/test';

const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';
const CLIENT = 'romeobeltran@auth.workhiveph.com';
const ADMIN = 'pabloaguilar@auth.workhiveph.com';

async function signIn(page: Page, email: string) {
  await page.goto('/workhive/index.html', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => typeof (window as any).getDb === 'function', { timeout: 20000 });
  await page.evaluate(async ([mail, pass]) => {
    const db = (window as any).getDb();
    await db.auth.signOut();
    await db.auth.signInWithPassword({ email: mail, password: pass });
  }, [email, PASSWORD]);
}

async function openServices(page: Page) {
  await page.goto('/workhive/marketplace.html');
  await page.waitForTimeout(3500);
  await page.click('[data-section="services"]');
  await page.waitForTimeout(2000);
}

test.describe('marketplace simulation — map tier', () => {

  test('MS-MAP-not-loaded-until-asked: 800KB stays off the hail path', async ({ page }) => {
    await signIn(page, CLIENT);
    await openServices(page);
    const loaded = await page.evaluate(() => typeof (window as any).maplibregl !== 'undefined');
    expect(loaded, 'MapLibre loaded on the services view without anyone asking for a map — that is '
      + '800KB charged to every hail, and most of these users are on 3G').toBe(false);
    // Non-vacuity: the pin button must actually be there, or "not loaded" is trivially true.
    const btn = await page.evaluate(() => !!document.getElementById('svc-pin-btn'));
    expect(btn, 'no pin affordance exists, so the absence of the map proves nothing').toBe(true);
  });

  test('MS-MAP-pin-loads-on-demand and renders a canvas', async ({ page }) => {
    await signIn(page, CLIENT);
    await openServices(page);
    await page.click('#svc-pin-btn');
    await page.waitForTimeout(6000);
    const r = await page.evaluate(() => ({
      lib: typeof (window as any).maplibregl !== 'undefined',
      canvas: !!document.querySelector('#svc-pin-map canvas'),
      note: (document.getElementById('svc-pin-note')?.innerText || '').trim(),
    }));
    expect(r.lib, 'pressing the pin button did not load the map library').toBe(true);
    expect(r.canvas, 'the map library loaded but no canvas rendered — the user sees a blank box').toBe(true);
    expect(r.note.toLowerCase(), 'nothing tells the user what to do with the map').toContain('tap');
  });

  test('MS-MAP-pin-optional: a hail without a pin still sends', async ({ page }) => {
    await signIn(page, CLIENT);
    await openServices(page);
    // Never touch the pin. The feature must not have become a requirement.
    const canSend = await page.evaluate(() => {
      const sel = document.getElementById('svc-hail-item') as HTMLSelectElement;
      const addr = document.getElementById('svc-hail-address') as HTMLInputElement;
      const btn = Array.from(document.querySelectorAll('button'))
        .find(b => /hail now/i.test(b.innerText || ''));
      return { picker: !!sel && sel.options.length > 1, addr: !!addr, btn: !!btn,
               btnDisabled: btn ? (btn as HTMLButtonElement).disabled : true };
    });
    expect(canSend.picker && canSend.addr && canSend.btn, 'the hail form is incomplete').toBe(true);
    expect(canSend.btnDisabled, 'Hail is DISABLED without a pin — pinning was meant to be optional, and '
      + 'a required pin locks out anyone whose map cannot load').toBe(false);
  });

  test('MS-MAP-presence-is-honest: the online line matches reality or stays silent', async ({ page }) => {
    await signIn(page, CLIENT);
    await openServices(page);
    const p = await page.evaluate(async () => {
      const el = document.getElementById('svc-presence');
      const txt = (el?.innerText || '').trim();
      const db = (window as any).getDb();
      const { data } = await db.from('service_providers').select('id').eq('availability', 'online');
      return { txt, online: (data || []).length };
    });
    if (p.online === 0) {
      // "0 providers online" is a discouraging lie-by-omission; silence is the designed behaviour.
      expect(p.txt, 'with nobody online the presence line should stay silent, not print a zero')
        .not.toMatch(/\b0\b/);
    } else {
      const claimed = Number((p.txt.match(/(\d+)\s+provider/i) || [])[1] || -1);
      expect(claimed, `the presence line claims ${claimed} online but ${p.online} providers are marked `
        + 'online — a trust signal standing on nothing').toBe(p.online);
    }
  });
});

test.describe('marketplace simulation — admin tier', () => {

  test('MS-ADMIN-topup-queue-lists-pendings with payer, ref and time', async ({ page }) => {
    await signIn(page, ADMIN);
    await page.goto('/workhive/founder-console.html');
    await page.waitForTimeout(7000);
    const q = await page.evaluate(async () => {
      const box = document.getElementById('svc-topups-content');
      const db = (window as any).getDb();
      const { data } = await db.from('service_credit_topups').select('id')
        .eq('status', 'pending_verification');
      return { text: (box?.innerText || '').replace(/\s+/g, ' ').trim(), pending: (data || []).length };
    });
    if (q.pending > 0) {
      // A queue that hides the reference is a queue the founder cannot check against GCash.
      expect(q.text, 'a pending top-up exists but the queue shows no reference number to match in GCash')
        .toMatch(/ref\s*\d{6,}/i);
      expect(q.text, 'the queue does not say when it was filed').toMatch(/filed|\d{1,2}\/\d{1,2}\/\d{4}/i);
    } else {
      expect(q.text.toLowerCase(), 'an empty queue must SAY it is empty, not render blank')
        .toMatch(/no top-ups|waiting|none/);
    }
  });

  test('MS-ADMIN-money-tile-four-numbers with a real cover figure', async ({ page }) => {
    await signIn(page, ADMIN);
    await page.goto('/workhive/founder-console.html');
    await page.waitForTimeout(8000);
    const t = await page.evaluate(() => ({
      text: (document.getElementById('credit-economy-content')?.innerText || '')
        .replace(/\s+/g, ' ').trim(),
      rag: document.getElementById('rag-credit-economy')?.className || '',
    }));
    for (const label of ['EARNED REVENUE', 'CREDIT LIABILITY', 'LIABILITY COVER', 'CASHBACK']) {
      expect(t.text.toUpperCase(), `the money tile is missing "${label}" — the four numbers the `
        + 'sustainability study says to watch').toContain(label);
    }
    // Cover is the one that matters: it says whether every credit could be honoured tomorrow.
    expect(t.text, 'liability cover renders no actual multiple').toMatch(/[\d.]+x/i);
    expect(t.rag, 'the RAG dot never resolved').toMatch(/green|amber|red/);
  });

  test('MS-ADMIN-money-tile-is-not-guessing: figures match the ledger', async ({ page }) => {
    await signIn(page, ADMIN);
    await page.goto('/workhive/founder-console.html');
    await page.waitForTimeout(8000);
    const cmp = await page.evaluate(async () => {
      const db = (window as any).getDb();
      const { data } = await db.from('service_credit_ledger').select('entry_type,amount');
      const sum = (t: string) => (data || []).filter((r: any) => r.entry_type === t)
        .reduce((a: number, r: any) => a + Number(r.amount || 0), 0);
      const earned = -sum('commission');
      const shown = (document.getElementById('credit-economy-content')?.innerText || '');
      const first = Number((shown.match(/₱\s*([\d,]+\.\d{2})/) || [])[1]?.replace(/,/g, '') || -1);
      return { earned: Math.round(earned * 100) / 100, first };
    });
    // The tile is computed from the ledger, never from a cached profile column — this platform has
    // been bitten by trust numbers standing on nothing.
    expect(cmp.first, `the tile shows ${cmp.first} as earned revenue but the ledger sums to ${cmp.earned}`)
      .toBeCloseTo(cmp.earned, 2);
  });
});
