/**
 * marketplace-sim-defects.spec.ts — the browser tier of the marketplace simulation registry.
 *
 * The registry (marketplace_sim_scenarios.json) authored 115 scenarios; only 15 were decidable against
 * the database, and the other 100 were listed owed-with-reason rather than counted. This file starts
 * paying that debt with the eight that matter most: MS-D1 … MS-D8, the standing regressions for the
 * eight user-facing defects found by walking the marketplace as provider → client → admin on
 * 2026-08-01/02. Every one of them shipped while its page's validators were green, because every one
 * is about what a PERSON SEES — which no SQL probe can decide.
 *
 * These are deliberately assertions about the RENDERED page, not about the code that renders it:
 *   D1  a shared container means last-writer-wins    → the Listings tab must show LISTINGS
 *   D2  [hidden] loses to an explicit display        → exactly one pane visible, never both
 *   D3  opacity:0 hides from eyes only               → a stranger must not tab into the edit form
 *   D6  the only path to transact was below the fold → the CTA must be reachable without scrolling
 *   D8  built, called, and never on a real load      → the money tile must populate by itself
 *
 * D4, D5 and D7 are already decided in the db tier (the view exposes the column, the hail carries a
 * point, the accept gate reads the floor), so they are not duplicated here — a scenario asserted in two
 * tiers is not twice as safe, it is twice as slow.
 *
 * NON-VACUITY runs through the file: each check names the value that would be TRUE if the defect
 * returned, so a passing assertion is evidence rather than an absence of noise.
 */
import { test, expect, Page } from '@playwright/test';

const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';
const SELLER = 'isidrosuarez@auth.workhiveph.com';   // a seller who really has listings
const CLIENT = 'romeobeltran@auth.workhiveph.com';
const ADMIN  = 'pabloaguilar@auth.workhiveph.com';   // a real marketplace_platform_admins member

/** Sign in through the page's own Supabase client — the same path the UI uses. */
async function signIn(page: Page, email: string) {
  await page.goto('/workhive/index.html', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => typeof (window as any).getDb === 'function', { timeout: 20000 });
  const ok = await page.evaluate(async ([mail, pass]) => {
    const db = (window as any).getDb();
    await db.auth.signOut();
    const { error } = await db.auth.signInWithPassword({ email: mail, password: pass });
    return !error;
  }, [email, PASSWORD]);
  expect(ok, `sign-in failed for ${email}`).toBe(true);
}

test.describe('marketplace simulation — the eight defect classes', () => {

  test('MS-D1 the Listings tab shows LISTINGS, not another tab\'s empty state', async ({ page }) => {
    await signIn(page, SELLER);
    await page.goto('/workhive/marketplace-seller.html');
    // Boot runs Promise.all([loadProfile, loadListings, loadInquiries]); all three must settle before
    // this means anything — the defect WAS a race, so asserting too early would hide it again.
    await page.waitForTimeout(4000);

    const seen = await page.evaluate(() => {
      const a = document.getElementById('content-area');
      return { tab: (document.querySelector('.tab-btn.active') as HTMLElement)?.dataset.tab,
               text: (a?.innerText || '').replace(/\s+/g, ' ').trim(),
               children: a?.children.length ?? 0 };
    });

    expect(seen.tab, 'the seller should land on Listings').toBe('listings');
    // The exact string the defect produced. If this ever appears under Listings again, the shared
    // container has been reintroduced somewhere.
    expect(seen.text, 'the INQUIRIES empty state is rendering on the LISTINGS tab — a renderer is '
      + 'painting a surface it does not own (shared #content-area, last writer wins)')
      .not.toMatch(/No inquiries yet/i);
    expect(seen.children, 'the seller has listings in the database but none rendered').toBeGreaterThan(0);
  });

  test('MS-D2 switching to Services hides the parts grid', async ({ page }) => {
    await signIn(page, CLIENT);
    await page.goto('/workhive/marketplace.html');
    await page.waitForTimeout(3500);
    await page.click('[data-section="services"]');
    await page.waitForTimeout(2000);

    const v = await page.evaluate(() => {
      const vis = (id: string) => {
        const e = document.getElementById(id);
        return !!e && getComputedStyle(e).display !== 'none';
      };
      return { grid: vis('listing-grid'), pane: vis('services-pane') };
    });
    // Both visible was the defect: the services pane AND nine parts listings, under a header reading
    // "9 parts listings after filter", while the Services tab showed as active.
    expect(v.pane, 'the services pane should be shown on the Services section').toBe(true);
    expect(v.grid, 'the parts grid is STILL visible on the Services section — [hidden] is being '
      + 'overridden by an explicit display rule again').toBe(false);
  });

  test('MS-D3 a signed-out stranger cannot tab into the seller edit form', async ({ page }) => {
    // No sign-in on purpose: the "Sign In Required" screen is the one a stranger meets, and the first
    // version of this fix protected only the signed-in dashboard — the wrong half.
    await page.goto('/workhive/marketplace-seller.html');
    await page.waitForTimeout(2500);

    const r = await page.evaluate(() => {
      const f = document.getElementById('edit-title') as HTMLInputElement | null;
      if (!f) return { present: false, focused: false, inert: false };
      f.focus();
      return { present: true, focused: document.activeElement === f,
               inert: !!document.getElementById('sheet-edit')?.hasAttribute('inert') };
    });

    if (r.present) {
      expect(r.focused, 'focus LANDED on the hidden seller edit form while signed out — opacity:0 '
        + 'hides from eyes only; the closed sheet needs [inert]').toBe(false);
      expect(r.inert, 'the closed edit sheet is not inert').toBe(true);
    }
  });

  test('MS-D6 the primary CTA is reachable without scrolling', async ({ page }) => {
    await signIn(page, CLIENT);
    await page.goto('/workhive/marketplace.html');
    await page.waitForTimeout(3500);

    // Open the first listing's detail the way a buyer does.
    const opened = await page.evaluate(async () => {
      const grid = document.getElementById('listing-grid');
      const card = grid?.children[0] as HTMLElement | undefined;
      const view = card && Array.from(card.querySelectorAll('a,button'))
        .find(e => /view/i.test((e as HTMLElement).innerText || ''));
      (view as HTMLElement | undefined)?.click();
      await new Promise(r => setTimeout(r, 2000));
      return !!document.getElementById('btn-detail-contact');
    });
    test.skip(!opened, 'no listing detail available in this dataset');

    const m = await page.evaluate(() => {
      const b = document.getElementById('btn-detail-contact')!;
      const rect = b.getBoundingClientRect();
      const row = b.closest('.action-row') as HTMLElement | null;
      return { top: rect.top, height: rect.height, viewportH: window.innerHeight,
               position: row ? getComputedStyle(row).position : 'none' };
    });

    // It measured y=1408 in a 753px viewport — 699px below the fold, under the description, the
    // seller card and the reviews block.
    expect(m.position, 'the action row must be sticky so the only path to transact stays reachable')
      .toBe('sticky');
    expect(m.top, `"Contact Seller" is ${Math.round(m.top - m.viewportH)}px BELOW the fold — the only `
      + 'way to reach the seller is invisible until you scroll').toBeLessThan(m.viewportH);
    expect(m.height, 'the CTA must clear the 44px tap-target floor').toBeGreaterThanOrEqual(44);
  });

  test('MS-D8 the founder money tile populates on a cold load, unassisted', async ({ page }) => {
    await signIn(page, ADMIN);
    await page.goto('/workhive/founder-console.html');

    // The whole point: NOTHING is invoked by hand. The defect was a loader wired only inside
    // svcTopupDecide(), so the tile painted after a top-up decision and was blank on every real load —
    // and it was "verified" originally by calling the function in the console.
    await page.waitForTimeout(8000);

    const t = await page.evaluate(() => {
      const box = document.getElementById('credit-economy-content');
      return { len: box?.innerHTML.length ?? 0,
               text: (box?.innerText || '').replace(/\s+/g, ' ').trim(),
               rag: document.getElementById('rag-credit-economy')?.className || '' };
    });

    expect(t.len, 'the credit-economy tile is EMPTY after a cold load — it is wired to a handler '
      + 'instead of to boot (built, called, and still never runs when it matters)').toBeGreaterThan(100);
    expect(t.text, 'the tile should name liability cover, the number the study calls the one that matters')
      .toMatch(/LIABILITY COVER/i);
    expect(t.rag, 'the RAG dot should resolve to a real state, not stay unset').toMatch(/green|amber|red/);
  });
});
