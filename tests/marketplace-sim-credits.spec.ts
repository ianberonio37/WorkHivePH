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
import { adminClient } from './_db-cleanup';

const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';
const SELLER = 'isidrosuarez@auth.workhiveph.com';
const OTHER  = 'romeobeltran@auth.workhiveph.com';
/* The one fixture identity that is the CLIENT on a job in a confirmable state (agreed base PHP6,000, so
   the 10% cap is PHP600). Pinned rather than discovered at runtime: a limit(1) over "some completed job"
   twice in this arc picked a row belonging to a different party and reported a bug that did not exist. */
const BUYER_EMAIL = 'davidvelasco@auth.workhiveph.com';

/* Seeded through the service role and announced as a platform act, which is how the schema distinguishes
   a vetted write from a user hand-minting credits. Returned so the finally block removes exactly what it
   added -- a shared local DB, and a test that leaves credits behind changes the next test's arithmetic. */
async function seedBuyerCredits(email: string, amount: number): Promise<string | null> {
  const admin = adminClient();
  const { data: users } = await admin.auth.admin.listUsers({ page: 1, perPage: 200 });
  const uid = users?.users?.find(u => u.email === email)?.id;
  if (!uid) return null;
  const note = 'SPECSEED credits ' + Date.now();
  const { error } = await admin.from('service_credit_ledger').insert({
    account_type: 'consumer', account_id: uid, entry_type: 'topup',
    amount, ref_kind: 'probe', note
  });
  return error ? null : note;
}

async function removeSeededCredits(note: string | null) {
  if (!note) return;
  const admin = adminClient();
  await admin.from('service_credit_ledger').delete().eq('note', note);
  const { count } = await admin.from('service_credit_ledger')
    .select('id', { count: 'exact', head: true }).eq('note', note);
  expect(count, 'seeded credits survived cleanup and will skew the next run').toBe(0);
}

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
  test('the founder sees the supply, circulation and what remains', async ({ page }) => {
    /* Ian asked for these three by name. They come from credit_treasury -- the row the CHECK constraint
       guards -- never from a sum, because the cap IS the safety property of this economy and a number
       that could quietly disagree with it would be worse than no number at all. */
    await signIn(page, 'pabloaguilar@auth.workhiveph.com');
    await page.goto('/workhive/founder-console.html');
    await page.waitForTimeout(9000);
    const t = await page.evaluate(() =>
      (document.getElementById('credit-economy-content') as HTMLElement)?.innerText.replace(/\s+/g, ' ') || '');
    /* Compared upper-case because .l is CSS-uppercased and innerText returns what is RENDERED, not what
       the source wrote. Asserting the source casing failed while the display was perfectly correct. */
    const seen = t.toUpperCase();
    for (const label of ['Total WorkHive Credits', 'In circulation', 'Available to issue', 'Conversion rate']) {
      expect(seen, `the founder console never shows "${label}"`).toContain(label.toUpperCase());
    }
    expect(t, 'the supply shown is not the 10,000,000 cap').toMatch(/10,000,000/);
    expect(t, 'nothing states the rate is fixed, so nothing says it never moves').toMatch(/1 credit = PHP1/);
  });

  test('the card promises exactly what the database will pay', async ({ page }) => {
    /* The card MIRRORS listing_reservation_amount() instead of calling it, because an RPC per card is a
       page of round-trips. A mirror is a promise that can drift, so this asserts the two agree on a real
       listing rather than trusting that they do. The cap is where drift would land first: at a flat 10%
       a PHP25,000 listing advertises PHP2,500 and the database hands over PHP500. */
    await signIn(page, 'pabloaguilar@auth.workhiveph.com');
    await page.goto('/workhive/marketplace.html');
    await page.waitForSelector('.card-meta', { timeout: 20000 });

    const agree = await page.evaluate(async () => {
      const card = document.querySelector('.credits-back');
      if (!card) return { skip: 'no priced listing on the first page' };
      const article = card.closest('article');
      const id = article?.querySelector('[data-id]')?.getAttribute('data-id');
      const rows = await window.db.from('marketplace_listings')
        .select('price, hive_id').eq('id', id).maybeSingle();
      if (!rows.data) return { skip: 'listing not readable' };
      const rpc = await window.db.rpc('listing_reservation_amount',
        { p_hive: rows.data.hive_id, p_price: rows.data.price });
      const shown = Number((card.textContent || '').replace(/[^0-9.]/g, ''));
      return { shown, db: Number(rpc.data), price: Number(rows.data.price) };
    });

    if ((agree as any).skip) { test.skip(true, (agree as any).skip); return; }
    const a = agree as { shown: number; db: number; price: number };
    expect(a.db, 'the database computes no reward for this listing, so the chip should not exist').toBeGreaterThan(0);
    expect(a.shown, `the card advertises ${a.shown} credits back on a PHP${a.price} listing but the `
      + `database will pay ${a.db} - the card is making a promise the ledger will not keep`).toBe(a.db);
  });

  test('a buyer with credits is offered them at the moment of paying', async ({ page }) => {
    /* The spend half existed as two guards and no door: nothing in the schema ever wrote a reward_spend,
       and no screen ever asked. This walks the buyer's real path — the confirm-payment sheet on a
       completed job — and asserts the choice is THERE, with a cap the database will actually honour.

       Seeded and cleaned up here rather than assumed, because every buyer in the fixture holds zero
       credits, and a block that correctly renders nothing at zero would pass a weaker test forever. */
    const seeded = await seedBuyerCredits(BUYER_EMAIL, 5000);
    try {
      await signIn(page, BUYER_EMAIL);
      // ?section=services, because the client's jobs live behind a section tab and the default view is
      // the listing grid. Landing on the default page and finding no button would have "passed" as a skip.
      await page.goto('/workhive/marketplace.html?section=services');
      await page.waitForTimeout(8000);

      const found = await page.evaluate(async () => {
        const btn = Array.from(document.querySelectorAll('button'))
          .find(b => /Confirm payment/i.test(b.textContent || ''));
        if (!btn) return { skip: 'no confirmable job on this account' };
        (btn as HTMLButtonElement).click();
        await new Promise(r => setTimeout(r, 2500));
        const wrap = document.querySelector('[id^="svc-pay-credits-"]');
        const input = document.querySelector('[id^="svc-pay-credits-amt-"]') as HTMLInputElement | null;
        return { text: (wrap?.textContent || '').replace(/\s+/g, ' '), max: input?.max || null };
      });

      if ((found as any).skip) { test.skip(true, (found as any).skip); return; }
      const f = found as { text: string; max: string | null };
      expect(f.max, 'the confirm sheet never offered the buyer their credits — the spend half is '
        + 'unreachable from the only screen where it applies').not.toBeNull();
      expect(f.text, 'the sheet does not say credits are exclusive with earning, so a buyer spends '
        + 'without knowing it costs them the cashback').toMatch(/do not earn credits on this job/i);
      // The cap the UI offers must be one the database will honour, not a friendlier number.
      expect(Number(f.max), 'the offered cap exceeds 10% of the agreed price, so the database would '
        + 'refuse exactly the amount the page invited').toBeLessThanOrEqual(600.01);
    } finally {
      await removeSeededCredits(seeded);
    }
  });

  test('a guard that explains itself is not replaced by "try again"', async ({ page }) => {
    /* Every credit guard raises a sentence written for the person reading it. whWriteError threw all of
       them away and showed the caller's fallback, so a seller blocked for want of PHP50 in credits read
       "Save failed. Try again." -- and retrying is exactly what cannot work. Worse, whIsAuthFailure
       treated ANY 42501 as a dead session, so three of these guards would have sent a signed-in person to
       the sign-in page. Fixed at the root in utils.js; this pins both directions, because the fix is only
       correct if a GENUINE denial still reads as one. */
    await page.goto('/workhive/marketplace.html');
    await page.waitForFunction(() => typeof (window as any).whWriteError === 'function', { timeout: 20000 });
    const r = await page.evaluate(() => {
      const w = (window as any).whWriteError, FB = 'Save failed. Try again.';
      return {
        reservation: w({ code: '23514', message: 'Listing needs PHP50 credits held (10% of the price) and you have 0 available.' }, FB),
        newSeller:   w({ code: '42501', message: 'A new seller can keep 3 listings live until one of them sells. You have 3.' }, FB),
        wallet:      w({ code: '42501', message: 'A credit balance is only visible to its owner' }, FB),
        realRls:     w({ code: '42501', message: 'new row violates row-level security policy for table "x"' }, FB),
        expired:     w({ status: 401, message: 'JWT expired' }, FB),
        rawPg:       w({ code: '23505', message: 'duplicate key value violates unique constraint "x_pkey"' }, FB),
      };
    });
    expect(r.reservation, 'the seller is not told they need credits').toContain('credits held');
    expect(r.newSeller,   'the new-seller cap explains nothing').toContain('keep 3 listings live');
    expect(r.wallet,      'the wallet refusal explains nothing').toContain('only visible to its owner');
    expect(r.realRls,     'a GENUINE RLS denial leaked Postgres wording to a user').toContain('session expired');
    expect(r.expired,     'a real 401 no longer reads as an expired session').toContain('session expired');
    expect(r.rawPg,       'raw Postgres constraint text reached a user').toBe('Save failed. Try again.');
  });
});
