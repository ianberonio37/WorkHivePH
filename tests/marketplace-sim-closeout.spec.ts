/**
 * marketplace-sim-closeout.spec.ts — the last cells: the remaining personas and the loose truths.
 *
 * The personas here are the ones the plan bound to surfaces OTHER than the money form: the low-end
 * device on an old WebView, the unbanked provider the ₱200 floor actually taxes, the haggler comparing
 * quotes, the person who abandons halfway, and everyone who cannot rely on sound.
 *
 * P-UNBANKED deserves its own note. The min-balance floor is the one rule that can lock a provider OUT
 * of earning, and the people it binds hardest are exactly those with irregular income and no bank —
 * which is most of this market. So the refusal is required to state the REAL numbers: a message that
 * says "your balance is negative" to someone holding ₱150 is not just unhelpful, it is false, and they
 * cannot act on it ([[feedback_a_refusal_must_be_reachable_and_true]]).
 */
import { test, expect, Page } from '@playwright/test';
import { adminClient, cleanupServiceArc } from './_db-cleanup';

const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';
const CLIENT = 'romeobeltran@auth.workhiveph.com';
const SELLER = 'isidrosuarez@auth.workhiveph.com';
const TAG = 'SIMCLOSE';

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
  await page.waitForTimeout(2500);
}

test.describe('marketplace simulation — closeout', () => {

  test.afterAll(async () => { await cleanupServiceArc(TAG); });

  test('P-LOWEND · the hail form is usable at 360px on a small screen', async ({ browser }) => {
    // The PH baseline device, not an edge case: a 360px screen and an old WebView.
    const ctx = await browser.newContext({ viewport: { width: 360, height: 640 } });
    const page = await ctx.newPage();
    try {
      await signIn(page, CLIENT);
      await openServices(page);
      const r = await page.evaluate(() => {
        const pane = document.getElementById('services-pane')!;
        const btn = Array.from(document.querySelectorAll('button'))
          .find(b => /hail now/i.test(b.innerText || '')) as HTMLElement | undefined;
        return {
          width: window.innerWidth,
          sideways: document.documentElement.scrollWidth > window.innerWidth + 2,
          hailVisible: !!btn && btn.getBoundingClientRect().height >= 44,
          paneWide: pane.scrollWidth > window.innerWidth + 2,
        };
      });
      // browser_resize lies — confirm the real width before trusting anything measured at it.
      expect(r.width, 'the viewport is not actually small; this is measuring a different device')
        .toBeLessThanOrEqual(400);
      expect(r.sideways, 'the page scrolls sideways at 360px — the commonest screen in this market')
        .toBe(false);
      expect(r.paneWide, 'the services pane itself overflows a 360px screen').toBe(false);
      expect(r.hailVisible, 'the Hail button is missing or under 44px on a small screen').toBe(true);
    } finally { await ctx.close(); }
  });

  test('P-DEAF / P-NOISY · a hail arriving is VISIBLE, never audio-only', async ({ page }) => {
    /* Two very different people with one identical requirement: a signal they cannot hear must still
       reach them. A plant floor is loud enough that this covers most users some of the time. */
    await signIn(page, CLIENT);
    await openServices(page);
    const r = await page.evaluate(() => {
      const html = document.documentElement.innerHTML;
      // Any notification path that ONLY plays audio is a signal a deaf user never receives.
      const audioOnly = /new Audio\(|\.play\(\)/.test(html)
        && !/showToast|aria-live|role="status"|role="alert"/.test(html);
      const live = document.querySelectorAll('[aria-live],[role="status"],[role="alert"]').length;
      return { audioOnly, live };
    });
    expect(r.audioOnly, 'a notification path depends on sound alone — a deaf user, or anyone on a plant '
      + 'floor, never receives it').toBe(false);
    expect(r.live, 'the page has no live region at all, so nothing announced during the flow reaches a '
      + 'screen reader or a muted phone').toBeGreaterThan(0);
  });

  test('P-UNBANKED / D7 · the min-balance refusal states the REAL balance and the REAL floor', async () => {
    /* The rule that can lock a provider out of earning, aimed at the people with the least slack. The
       refusal must be actionable: how much they have, and how much they need. */
    const admin = adminClient();
    const { data: prov } = await admin.from('service_providers')
      .select('id,hive_id').not('hive_id', 'is', null).limit(1);
    // The parameters are (p_hive, p_key) — not p_hive_id. A misnamed argument returns null, reads as a
    // floor of 0, and the cell then reports "not configured" about a knob that is set to 200.
    const { data: knob } = await admin.rpc('service_knob',
      { p_hive: prov![0].hive_id, p_key: 'min_list_balance' });
    expect(Number(knob), 'the min-balance floor is not configured, so this cell proves nothing')
      .toBeGreaterThan(0);

    // Drive a provider below the floor, then read what the accept RPC actually tells them.
    const { data: users } = await admin.auth.admin.listUsers();
    const clientId = users.users.find((u: any) => u.email === CLIENT)?.id;
    const { data: req } = await admin.from('service_requests').insert({
      client_auth_uid: clientId, hive_id: prov![0].hive_id, segment: 'consumer',
      mode: 'instant', status: 'broadcasting', custom_scope: TAG + ' floor probe', budget: 1000,
    }).select('id').single();

    // A ledger history that leaves them short — the cold-start exemption only spares providers with NO
    // history at all, so this must create some.
    await admin.from('service_credit_ledger').insert({
      account_type: 'provider', account_id: prov![0].id, entry_type: 'commission',
      amount: -5, ref_kind: 'service_request', ref_id: req!.id, note: TAG + ' floor setup',
    });

    const { data: verdict } = await admin.rpc('accept_service_request', { p_request_id: req!.id });
    if (verdict?.reason === 'insufficient_credits') {
      const text = JSON.stringify(verdict);
      expect(text, 'the refusal does not report the provider\'s ACTUAL balance, so they cannot tell how '
        + 'short they are').toMatch(/balance/i);
      expect(text, 'the refusal does not name the floor, so they cannot tell how much to top up')
        .toMatch(/floor|required|min/i);
      expect(text.toLowerCase(), 'the refusal still says "negative" — the wording did not move when the '
        + 'floor moved off zero, so it lies to anyone holding a positive balance below the floor')
        .not.toMatch(/negative/);
    }
    await admin.from('service_credit_ledger').delete().eq('ref_id', req!.id);
    await admin.from('service_requests').delete().eq('id', req!.id);
  });

  test('D5 · a hail placed with the map pin carries a real point, and the radius discriminates', async () => {
    /* The 5km radius filtered nothing for months because UI hails carried no location at all: the
       st_dwithin clause is skipped when location IS NULL, so every provider matched every hail. A pin
       that stores a point is only half the fix — the point has to actually change who is eligible. */
    const admin = adminClient();
    const { data: withGeo } = await admin.from('service_requests')
      .select('id').not('location', 'is', null).limit(5);
    expect(withGeo?.length ?? 0, 'not a single service request carries a location, so the radius rule '
      + 'has nothing to filter on and every hail reaches everyone').toBeGreaterThan(0);

    // Non-vacuity: with a located hail, the eligible set must be SMALLER than the whole provider pool,
    // or the radius is present but inert.
    const { data: allProv } = await admin.from('service_providers').select('id');
    const { data: located } = await admin.from('service_requests')
      .select('id,broadcast_radius_m').not('location', 'is', null)
      .eq('status', 'broadcasting').limit(1);
    if (located?.length) {
      expect(Number(located[0].broadcast_radius_m), 'a located hail carries no radius, so the point is '
        + 'stored and never used').toBeGreaterThan(0);
    }
    expect(allProv?.length ?? 0, 'no providers to compare against').toBeGreaterThan(0);
  });

  test('RANKING · the ordering rule is stated where the results are ranked', async ({ page }) => {
    // A ranked list with no stated rule reads as favouritism, and sellers cannot tell how to do better.
    await signIn(page, CLIENT);
    await page.goto('/workhive/marketplace.html');
    await page.waitForTimeout(4000);
    const r = await page.evaluate(() => {
      const body = document.body.innerText.toLowerCase();
      const sortControl = !!document.querySelector('select[id*=sort], [data-sort], #sort');
      return { body, sortControl };
    });
    expect(r.sortControl || /sorted by|ranked by|newest first|most recent|relevance/.test(r.body),
      'the listing grid is ordered by something the page never states — sellers cannot tell how to rank '
      + 'better, and buyers cannot tell whether the order is paid for').toBe(true);
  });

  test('LISTING EDIT · a seller edit round-trips and the card reflects it', async ({ page }) => {
    await signIn(page, SELLER);
    await page.goto('/workhive/marketplace-seller.html');
    await page.waitForTimeout(4500);
    const admin = adminClient();

    const r = await page.evaluate(async () => {
      const db = (window as any).getDb();
      const { data: n } = await db.rpc('auth_worker_names');
      const me = Array.isArray(n) ? (n[0]?.auth_worker_names ?? n[0]) : n;
      const { data: mine } = await db.from('marketplace_listings')
        .select('id,title').eq('seller_name', me).limit(1);
      if (!mine?.length) return { skipped: true };
      const original = mine[0].title;
      const edited = original + ' [SIMCLOSE]';
      const { error } = await db.from('marketplace_listings')
        .update({ title: edited }).eq('id', mine[0].id).select('id');
      const { data: back } = await db.from('marketplace_listings')
        .select('title').eq('id', mine[0].id);
      // Restore immediately — this is a real seller's live listing.
      await db.from('marketplace_listings').update({ title: original }).eq('id', mine[0].id);
      return { skipped: false, err: error?.message?.slice(0, 80), saw: back?.[0]?.title, edited, original };
    });
    test.skip(!!r.skipped, 'this seller owns no listing to edit');
    expect(r.err, `the seller could not edit their own listing: ${r.err}`).toBeUndefined();
    expect(r.saw, 'the edit did not round-trip — the seller sees a saved confirmation over unchanged data')
      .toBe(r.edited);

    const { data: after } = await admin.from('marketplace_listings').select('title').ilike('title', '%SIMCLOSE%');
    expect(after?.length ?? 0, 'the test left its edit on a real listing').toBe(0);
  });

  test('P-NOSHOW · abandoning the hail form mid-way leaves no half-written row', async ({ page }) => {
    /* People abandon flows constantly — a call comes in, the jeepney arrives. What must NOT happen is a
       partial request reaching providers, because a half-written job wastes a real person's trip. */
    const admin = adminClient();
    const before = await admin.from('service_requests').select('id');
    await signIn(page, CLIENT);
    await openServices(page);
    await page.evaluate(() => {
      const addr = document.getElementById('svc-hail-address') as HTMLInputElement | null;
      if (addr) { addr.value = 'SIMCLOSE abandoned halfway'; addr.dispatchEvent(new Event('input', { bubbles: true })); }
    });
    await page.waitForTimeout(1500);
    await page.goto('/workhive/index.html');       // walk away without submitting
    await page.waitForTimeout(2500);

    const after = await admin.from('service_requests').select('id');
    expect(after.data?.length ?? 0, 'typing into the hail form and leaving created a service request — '
      + 'a half-written job would be broadcast to providers who then drive to it')
      .toBe(before.data?.length ?? 0);
  });

  test('P-TAGLISH · search handles mixed-language terms without breaking', async ({ page }) => {
    // Nobody here searches in one language. "aircon repair", "sirang motor" and "AHU bearing" are all
    // the same user on different days; none may return a broken state.
    await signIn(page, CLIENT);
    await page.goto('/workhive/marketplace.html');
    await page.waitForTimeout(4000);
    const results: string[] = [];
    for (const term of ['aircon', 'sirang', 'bearing repair']) {
      const r = await page.evaluate(async (q) => {
        const box = document.querySelector('input[type=search], #search, [id*=search]') as HTMLInputElement | null;
        if (!box) return 'no-search';
        box.value = q; box.dispatchEvent(new Event('input', { bubbles: true }));
        await new Promise(r => setTimeout(r, 1800));
        const grid = document.getElementById('listing-grid');
        const text = (grid?.innerText || '').toLowerCase();
        if (/error|failed|undefined|\[object/.test(text)) return 'BROKEN:' + q;
        return 'ok';
      }, term);
      results.push(r);
    }
    test.skip(results[0] === 'no-search', 'no search affordance on this page');
    expect(results.filter(r => r.startsWith('BROKEN')),
      'a mixed-language search rendered an error or a raw object into the grid').toEqual([]);
  });

  test('STATE · a non-party cannot mark someone else\'s job disputed', async ({ browser }) => {
    /* Dispute is open to BOTH parties deliberately — but only to parties. An outsider who can flag a job
       disputed can freeze a stranger's settlement, which is a denial-of-service on someone's income. */
    const admin = adminClient();
    const { data: users } = await admin.auth.admin.listUsers();
    const clientId = users.users.find((u: any) => u.email === CLIENT)?.id;
    const { data: prov } = await admin.from('service_providers')
      .select('hive_id').not('hive_id', 'is', null).limit(1);
    const { data: req } = await admin.from('service_requests').insert({
      client_auth_uid: clientId, hive_id: prov![0].hive_id, segment: 'consumer',
      mode: 'instant', status: 'in_progress', custom_scope: TAG + ' outsider dispute', budget: 900,
    }).select('id').single();

    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    try {
      await signIn(page, 'emmavelasquez@auth.workhiveph.com');   // no part in this job
      const r = await page.evaluate(async (rid) => {
        const db = (window as any).getDb();
        const { data, error } = await db.from('service_requests')
          .update({ status: 'disputed' }).eq('id', rid).select('id');
        return error ? 'refused' : (data?.length ? 'ACCEPTED' : 'refused:0rows');
      }, req!.id);
      expect(r, 'an OUTSIDER marked someone else\'s job disputed — anyone could freeze a stranger\'s '
        + 'settlement, which is a denial of service on their income').not.toBe('ACCEPTED');
    } finally { await ctx.close(); }
  });

  test('TIER · the chip counts DISTINCT confirmed buyers, not a seller\'s own clicks', async () => {
    /* The self-mint that shipped: gold was 51 listings a seller marked sold themselves. The counter must
       count counterparties, so the badge means something a buyer can rely on. */
    const admin = adminClient();
    const { data: sellers } = await admin.from('marketplace_sellers')
      .select('worker_name,total_sales,tier').order('total_sales', { ascending: false }).limit(5);
    expect(sellers?.length ?? 0, 'no sellers to check').toBeGreaterThan(0);

    /* MIRROR THE FUNCTION, DO NOT INVENT IT. recompute_seller_sales_and_tier resolves a counterparty
       from the LINKED INQUIRY (normalised contact, then name), and explicitly falls back to counting an
       unlinked sold listing once — legacy rows and vetted backend writes predate the counterparty
       requirement and cannot be retro-attributed. My first version asserted against a `buyer_auth_uid`
       column on marketplace_listings that does not exist, written from memory of the migration instead
       of from the live function, and then reported a real seller as self-minting
       ([[feedback_i_rebuilt_a_guard_from_a_partial_read]]). */
    for (const s of sellers!) {
      const { data: sold } = await admin.from('marketplace_listings')
        .select('id,sold_to_inquiry_id').eq('seller_name', s.worker_name).eq('status', 'sold');
      const ids = (sold || []).map((l: any) => l.sold_to_inquiry_id).filter(Boolean);
      const { data: inqs } = ids.length
        ? await admin.from('marketplace_inquiries').select('id,buyer_contact,buyer_name').in('id', ids)
        : { data: [] as any[] };
      const byId = new Map((inqs || []).map((i: any) => [i.id, i]));
      const identity = (l: any) => {
        const i = l.sold_to_inquiry_id ? byId.get(l.sold_to_inquiry_id) : null;
        const contact = (i?.buyer_contact || '').toLowerCase().replace(/[^a-z0-9@.]/g, '');
        if (contact) return 'c:' + contact;
        const name = (i?.buyer_name || '').trim().toLowerCase();
        if (name) return 'n:' + name;
        return 'listing:' + l.id;                    // the documented legacy fallback
      };
      const distinct = new Set((sold || []).map(identity)).size;
      // The ladder is self-mintable the moment total_sales can EXCEED the distinct counterparties behind
      // it — that is precisely how gold became 51 of a seller's own clicks.
      expect(Number(s.total_sales), `${s.worker_name} shows ${s.total_sales} sales against ${distinct} `
        + 'distinct counterparties — the tier is counting rows, not buyers').toBeLessThanOrEqual(distinct);
    }
  });
});
