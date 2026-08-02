/**
 * marketplace-sim-discovery.spec.ts — the DISCOVERY and AFTERMATH tiers of the simulation registry.
 *
 * Discovery is the half of a marketplace nobody tests, because it looks like "the page loads". It is not:
 * it is whether a stranger can find anything, whether the counts on screen are true, and whether a failed
 * read is distinguishable from an empty one. That last distinction has its own history here — the P7 fix
 * exists because a failed listings fetch rendered "be the first to sell", telling a seller their listings
 * were gone.
 *
 * Aftermath is the half that decides whether anyone comes back: can a seller see and edit their own work,
 * does a buyer's inquiry actually arrive, does the trust chip on a card mean anything.
 *
 * COUNTS ARE CLAIMS. Every number rendered here is checked against the rows it claims to describe — the
 * same rule that caught "5 providers online now" when four were online. A count nobody verifies is a
 * trust signal standing on nothing.
 */
import { test, expect, Page } from '@playwright/test';
import { adminClient } from './_db-cleanup';

const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';
const TAG = 'SIMDISCOVERY';
const CLIENT = 'romeobeltran@auth.workhiveph.com';
const SELLER = 'isidrosuarez@auth.workhiveph.com';

async function signIn(page: Page, email: string) {
  await page.goto('/workhive/index.html', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => typeof (window as any).getDb === 'function', { timeout: 20000 });
  await page.evaluate(async ([mail, pass]) => {
    const db = (window as any).getDb();
    await db.auth.signOut();
    await db.auth.signInWithPassword({ email: mail, password: pass });
  }, [email, PASSWORD]);
}

test.describe('marketplace simulation — discovery tier', () => {

  test('MS-browse-anon-sees-listings: a stranger can browse and is told how to act', async ({ page }) => {
    // No sign-in: the anonymous visitor is the top of the funnel, and a marketplace that shows them
    // nothing has no funnel.
    await page.goto('/workhive/marketplace.html');
    await page.waitForTimeout(4000);
    const r = await page.evaluate(() => ({
      cards: document.getElementById('listing-grid')?.children.length ?? 0,
      body: (document.body.innerText || '').toLowerCase(),
    }));
    expect(r.cards, 'an anonymous visitor sees ZERO listings — there is nothing to draw them in')
      .toBeGreaterThan(0);
    expect(r.body, 'nothing tells an anonymous visitor how to participate')
      .toMatch(/sign in|sign up|join|register|contact/);
  });

  test('MS-browse-section-counts-true: each tab count equals the rows it renders', async ({ page }) => {
    await signIn(page, CLIENT);
    await page.goto('/workhive/marketplace.html');
    await page.waitForTimeout(4000);
    // Walk each section and compare the chip's number to what the grid actually shows. A count that
    // disagrees with its own list is the presence-double-count defect in another costume.
    const mismatches: string[] = [];
    for (const sec of ['parts', 'training', 'jobs']) {
      await page.click(`[data-section="${sec}"]`);
      await page.waitForTimeout(2200);
      const r = await page.evaluate((s) => {
        const chip = document.getElementById('count-' + s);
        const claimed = Number((chip?.textContent || '').trim());
        const rendered = document.getElementById('listing-grid')?.children.length ?? 0;
        return { claimed, rendered };
      }, sec);
      // The grid paginates, so rendered may be <= claimed — but never MORE, and never zero when the
      // chip promises rows.
      if (r.claimed > 0 && r.rendered === 0) mismatches.push(`${sec}: chip says ${r.claimed}, grid renders 0`);
      if (r.rendered > r.claimed) mismatches.push(`${sec}: grid renders ${r.rendered} > chip ${r.claimed}`);
    }
    expect(mismatches, `section counts disagree with their own lists: ${mismatches.join('; ')}`).toEqual([]);
  });

  test('MS-search-empty-vs-error: a filter with no matches says EMPTY, not broken', async ({ page }) => {
    await signIn(page, CLIENT);
    await page.goto('/workhive/marketplace.html');
    await page.waitForTimeout(3500);
    const r = await page.evaluate(async () => {
      const box = document.querySelector('input[type=search], #search, [id*=search]') as HTMLInputElement | null;
      if (!box) return { skipped: true };
      box.value = 'zzzzz-no-such-listing-zzzzz';
      box.dispatchEvent(new Event('input', { bubbles: true }));
      await new Promise(r => setTimeout(r, 2000));
      const grid = document.getElementById('listing-grid');
      return { skipped: false, cards: grid?.children.length ?? 0,
               text: (grid?.innerText || '').toLowerCase() };
    });
    test.skip(!!r.skipped, 'no search affordance on this page');
    if (r.cards === 0) {
      // The P7 rule: an empty RESULT must not read like a broken read, and must not read like a
      // first-run state either ("be the first to sell" on a filtered-to-nothing search is a lie).
      expect(r.text, 'a filtered-to-nothing search renders nothing at all — the user cannot tell '
        + 'whether the marketplace is empty, broken, or their filter is too narrow').not.toBe('');
      expect(r.text, 'a filtered search shows the FIRST-RUN empty state, telling an established '
        + 'marketplace it has no listings').not.toMatch(/be the first to sell/);
    }
  });

  test('MS-seller-profile-reachable from a listing', async ({ page }) => {
    await signIn(page, CLIENT);
    await page.goto('/workhive/marketplace.html');
    await page.waitForTimeout(3500);
    const href = await page.evaluate(async () => {
      const card = document.getElementById('listing-grid')?.children[0] as HTMLElement | undefined;
      const view = card && Array.from(card.querySelectorAll('a,button'))
        .find(e => /view/i.test((e as HTMLElement).innerText || ''));
      (view as HTMLElement | undefined)?.click();
      await new Promise(r => setTimeout(r, 2000));
      const link = Array.from(document.querySelectorAll('#detail-content a'))
        .find(a => /view profile/i.test((a as HTMLElement).innerText || ''));
      return (link as HTMLAnchorElement | undefined)?.getAttribute('href') || null;
    });
    expect(href, 'a buyer cannot reach the seller\'s history from a listing — the trust signal on the '
      + 'card leads nowhere').toBeTruthy();
    expect(href, 'the profile link carries no seller identity').toMatch(/worker=/);
  });
});

test.describe('marketplace simulation — aftermath tier', () => {

  /* CLEAN UP THROUGH THE SERVICE ROLE, IN afterAll, AND PROVE IT WORKED.
     Two mistakes produced this hook, both worth keeping written down. First, cleanup lived INLINE after
     the assertions, so the run where the assertion failed never reached it and leaked a row — cleanup
     placed after the thing that can throw is cleanup that runs only when it is least needed. Second, it
     deleted through the BUYER's session, and mkt_inq_delete is `is_marketplace_admin()`: the delete
     matched zero rows and returned NO error, so a passing test still left its row behind. That is exactly
     the no-op the lifecycle spec already hit on service_requests, repeated in a new file because the
     cleanup was rewritten from scratch instead of reused ([[feedback_live_mcp_writes_pollute_test_db]]).
     A cleanup that cannot prove it cleaned is indistinguishable from no cleanup at all. */
  test.afterAll(async () => {
    const admin = adminClient();
    await admin.from('marketplace_inquiries').delete().ilike('message', TAG + '%');
    const { data: left } = await admin.from('marketplace_inquiries')
      .select('id').ilike('message', TAG + '%');
    expect(left?.length ?? 0, 'the discovery spec left inquiries in a shared database').toBe(0);
  });

  test('MS-listing-create-from-dashboard: the seller can start one where they manage them', async ({ page }) => {
    await signIn(page, SELLER);
    await page.goto('/workhive/marketplace-seller.html');
    await page.waitForTimeout(4000);
    const cta = await page.evaluate(() => {
      const a = Array.from(document.querySelectorAll('a,button'))
        .find(e => /post a listing/i.test((e as HTMLElement).innerText || ''));
      if (!a) return null;
      const r = (a as HTMLElement).getBoundingClientRect();
      return { href: a.getAttribute('href'), h: Math.round(r.height), aboveFold: r.top < window.innerHeight };
    });
    expect(cta, 'the seller dashboard has NO way to start a listing — create and manage live on '
      + 'different pages and nothing bridges them').toBeTruthy();
    expect(cta!.h, 'the create CTA is under the 44px tap floor').toBeGreaterThanOrEqual(44);
    expect(cta!.aboveFold, 'the create CTA is below the fold on the page whose job is listings').toBe(true);
  });

  test('MS-seller-stats-match-the-listings', async ({ page }) => {
    await signIn(page, SELLER);
    await page.goto('/workhive/marketplace-seller.html');
    await page.waitForTimeout(4500);
    const r = await page.evaluate(async () => {
      const claimed = Number((document.getElementById('ps-listings')?.textContent || '').trim());
      const db = (window as any).getDb();
      const { data: s } = await db.auth.getSession();
      const { data: me } = await db.from('marketplace_sellers').select('worker_name')
        .eq('auth_uid', s.session.user.id).maybeSingle();
      const { data: rows } = await db.from('marketplace_listings').select('id')
        .eq('seller_name', me?.worker_name);
      return { claimed, actual: (rows || []).length, rendered: document.getElementById('content-area')?.children.length ?? 0 };
    });
    // The stat is a CLAIM about the same rows the tab renders. They must agree.
    expect(r.claimed, `the profile says ${r.claimed} listings but the seller owns ${r.actual}`)
      .toBe(r.actual);
    expect(r.rendered, 'the stat claims listings exist but the tab renders none — the same '
      + 'shared-container defect that hid them before').toBeGreaterThan(0);
  });

  test('MS-inquiry-reaches-seller: a buyer message lands on the seller\'s tab', async ({ browser }) => {
    // Two contexts: the handoff IS the assertion. A buyer's message that never arrives is the
    // marketplace's single most expensive silent failure.
    const bCtx = await browser.newContext(); const buyer = await bCtx.newPage();
    const sCtx = await browser.newContext(); const seller = await sCtx.newPage();
    try {
      await signIn(buyer, CLIENT);
      await signIn(seller, SELLER);

      /* STAGE AGAINST THE SELLER WHO IS ACTUALLY WATCHING. The first version took the first published
         listing via limit(1) — which belongs to whichever of the eight sellers sorts first — and then
         asserted that a DIFFERENT signed-in seller could see the inquiry. RLS correctly refused, and the
         test would have reported "the buyer's message never arrived" about a perfectly working handoff.
         limit(1) resolving live is not the same as resolving deterministically
         ([[feedback_resolving_live_is_not_enough_be_deterministic]]). */
      const sellerName = await seller.evaluate(async () => {
        const db = (window as any).getDb();
        const { data } = await db.rpc('auth_worker_names');
        return Array.isArray(data) ? (data[0]?.auth_worker_names ?? data[0]) : data;
      });

      const made = await buyer.evaluate(async (sName) => {
        const db = (window as any).getDb();
        const { data: l } = await db.from('marketplace_listings')
          .select('id,seller_name,hive_id').eq('status', 'published').eq('seller_name', sName).limit(1);
        if (!l?.length) return { skipped: true };
        /* buyer_name must be the caller's OWN worker name: mkt_inq_insert is
           WITH CHECK (buyer_name IN auth_worker_names()). The first version of this test invented a
           display string and was refused — my instrument, not the product. But chasing that refusal is
           what found the real defect: the direct Contact-Seller path never validated the name before
           writing (its RFQ sibling does), so the 42501 surfaced as "your session expired, sign in again"
           to a buyer whose session was perfectly fine. */
        const { data: names } = await db.rpc('auth_worker_names');
        const me = Array.isArray(names) ? (names[0]?.auth_worker_names ?? names[0]) : names;
        const { data, error } = await db.from('marketplace_inquiries').insert({
          listing_id: l[0].id, hive_id: l[0].hive_id, seller_name: l[0].seller_name,
          buyer_name: me, buyer_contact: '0917 000 0099',
          message: 'SIMDISCOVERY is this still available?',
        }).select('id').single();
        return { skipped: false, id: data?.id, err: error?.message?.slice(0, 80), me };
      }, sellerName);
      test.skip(!!made.skipped, `no published listing owned by ${sellerName} to inquire about`);
      expect(made.err, `the buyer could not send an inquiry: ${made.err}`).toBeUndefined();

      // Read through the PRODUCT surface — the seller dashboard renders v_marketplace_inquiries_truth,
      // not the base table, so that view is where the message either arrives or does not.
      const arrived = await seller.evaluate(async (iid) => {
        const db = (window as any).getDb();
        const { data } = await db.from('v_marketplace_inquiries_truth').select('id,message').eq('id', iid);
        return !!(data && data.length);
      }, made.id!);
      expect(arrived, 'the buyer\'s inquiry NEVER reached the seller — the message vanished between '
        + 'two people who both believe it was delivered').toBe(true);

      // Row removal is the afterAll's job, through the service role — see the note there.
    } finally { await bCtx.close(); await sCtx.close(); }
  });

  test('MS-inquiry-wrong-name-says-NAME, never "your session expired"', async ({ page }) => {
    /* The regression for the defect above. A buyer editing the prefilled name hits the same RLS refusal,
       and the ONLY acceptable response names the name. "Sign in again" is a false instruction that sends
       a signed-in person round a loop no amount of re-logging-in can complete
       ([[feedback_string_is_not_an_announcement_until_it_reaches_a_user]] — a refusal must reach the user
       as something they can ACT on). */
    await signIn(page, CLIENT);
    await page.goto('/workhive/marketplace.html');
    await page.waitForTimeout(4000);
    const r = await page.evaluate(async () => {
      // Open the inquiry sheet on the first listing, then type a name that is not the worker's.
      const card = document.getElementById('listing-grid')?.children[0] as HTMLElement | undefined;
      const btn = card && Array.from(card.querySelectorAll('a,button'))
        .find(e => /contact|inquire|message/i.test((e as HTMLElement).innerText || ''));
      (btn as HTMLElement | undefined)?.click();
      await new Promise(r => setTimeout(r, 1200));
      const nm = document.getElementById('inq-name') as HTMLInputElement | null;
      if (!nm) return { skipped: true };
      nm.value = 'Totoy of ABC Trading';
      (document.getElementById('inq-contact') as HTMLInputElement).value = '0917 000 0088';
      (document.getElementById('inq-message') as HTMLTextAreaElement).value = 'SIMDISCOVERY wrong-name probe';
      (document.getElementById('btn-submit-inquiry') as HTMLButtonElement)?.click();
      await new Promise(r => setTimeout(r, 2500));
      return { skipped: false, toast: (document.body.innerText || '') };
    });
    test.skip(!!r.skipped, 'no inquiry form reachable from a card');
    expect(r.toast, 'a mistyped name is reported as an EXPIRED SESSION — the buyer is told to sign in '
      + 'again, which cannot ever deliver their message').not.toMatch(/session expired/i);
    expect(r.toast, 'the refusal never names the actual problem (the name), so the buyer cannot fix it')
      .toMatch(/WorkHive name/i);
  });
});
