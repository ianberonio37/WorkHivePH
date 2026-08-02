/**
 * marketplace-sim-credits.spec.ts — the credit wallet, as a seller actually meets it.
 *
 * The DB guards are proven at the database (over-issue refused, delist returns in full, earn-or-spend
 * exclusive). None of that helps a seller who cannot SEE their balance or understand why publishing is
 * blocked — and the simulation put cold-start credit starvation at ~31% of providers, which lands on the
 * buyer side as fill rate falling from 51% to 30%. So the wallet is not decoration; it is the difference
 * between a blocked seller who tops up and a blocked seller who leaves.
 *
 * PAINTS ON A RELOAD, NEVER ON DEMAND. The first version of this wallet showed "-" on every cold load
 * because loadCreditWallet() ran inside the boot Promise.all while WORKER_NAME was still arriving from
 * restoreIdentityFromSession(). Calling the loader by hand would have "verified" it perfectly. Only a
 * real reload catches it, which is why every assertion here follows a navigation.
 */
import { test, expect, Page } from '@playwright/test';

const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';
const SELLER = 'isidrosuarez@auth.workhiveph.com';
const OTHER  = 'romeobeltran@auth.workhiveph.com';

async function signIn(page: Page, email: string) {
  await page.goto('/workhive/index.html', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => typeof (window as any).getDb === 'function', { timeout: 20000 });
  await page.evaluate(async ([mail, pass]) => {
    const db = (window as any).getDb();
    await db.auth.signOut();
    await db.auth.signInWithPassword({ email: mail, password: pass });
  }, [email, PASSWORD]);
}

test.describe('marketplace simulation — the credit wallet', () => {

  test('the wallet paints on a COLD LOAD, not on demand', async ({ page }) => {
    await signIn(page, SELLER);
    await page.goto('/workhive/marketplace-seller.html');
    await page.waitForTimeout(6000);
    const w = await page.evaluate(() => ({
      avail: (document.getElementById('cw-available') as HTMLElement)?.innerText || '',
      resv:  (document.getElementById('cw-reserved')  as HTMLElement)?.innerText || '',
      note:  (document.getElementById('cw-note')      as HTMLElement)?.innerText || '',
    }));
    expect(w.avail, 'available never rendered on a cold load — the loader ran before identity arrived')
      .not.toBe('-');
    expect(w.avail, 'available is blank').toBeTruthy();
    expect(w.resv, 'reserved never rendered').not.toBe('-');
    // The sentence that stops a reservation reading as a fee. Without it the seller believes publishing
    // COSTS 10%, which is the July listing-fee objection re-created in the user's head.
    expect(w.note.toLowerCase(), 'the wallet never says the credits come back if the listing does not sell')
      .toMatch(/comes back|not a fee/);
  });

  test('a seller with nothing is OFFERED the starter grant', async ({ page }) => {
    await signIn(page, SELLER);
    await page.goto('/workhive/marketplace-seller.html');
    await page.waitForTimeout(6000);
    const r = await page.evaluate(() => {
      const btn = document.getElementById('cw-claim') as HTMLElement | null;
      const total = (document.getElementById('cw-total') as HTMLElement)?.innerText || '';
      return { visible: !!btn && btn.offsetParent !== null, h: btn ? Math.round(btn.getBoundingClientRect().height) : 0, total };
    });
    // Only shown to someone who would actually be blocked. Offering it to a funded seller is noise.
    if (!r.total) {
      expect(r.visible, 'a seller holding no credits is not offered the starter grant, so the cold-start '
        + 'block has no way out').toBe(true);
      expect(r.h, 'the claim button is under the 44px tap floor').toBeGreaterThanOrEqual(44);
    }
  });

  test('a wallet is nobody else\'s business', async ({ page }) => {
    // seller_credit_balance is SECURITY DEFINER and takes a NAME, so without an internal party check any
    // signed-in user could size up a competitor's working capital: reserved reveals live inventory,
    // available reveals how much more they can list.
    await signIn(page, OTHER);
    const r = await page.evaluate(async () => {
      const db = (window as any).getDb();
      const { data, error } = await db.rpc('seller_credit_balance', { p_seller: 'Isidro Suarez' });
      return { rows: data?.length ?? 0, err: error?.message?.slice(0, 80) };
    });
    expect(r.rows, `another seller's credit balance was readable (${r.rows} rows) — that is their working `
      + 'capital exposed to a competitor').toBe(0);
  });
});
