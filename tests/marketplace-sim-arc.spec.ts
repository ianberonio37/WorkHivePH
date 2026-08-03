/**
 * marketplace-sim-arc.spec.ts — SJ-FULL: one job, filed to paid, in a single continuous session.
 *
 * Every other spec in this family observes ONE transition at ONE moment. This one walks the whole
 * machine: requested → broadcasting → accepted → en_route → on_site → in_progress → completed → settled,
 * with the client and the provider each driving only their own half, in two browser contexts held open
 * for the entire arc.
 *
 * WHY A CONTINUOUS ARC FINDS WHAT FRAGMENTS CANNOT. The bugs live in the seams: a party who may act at
 * step 3 but is locked out at step 8, a figure computed at settle from a row written at step 7, an
 * idempotency guard that only matters on the second press. Driving each transition in isolation, from a
 * hand-staged row, never crosses a seam. This spec found one immediately — service_payments_read
 * compared matched_provider_id (a service_providers.id) to auth.uid() (an auth.users.id), so the
 * PROVIDER could not read the payment record for their own job while being billed a commission computed
 * from its amount. Nothing had ever read that table as a provider, so nothing had noticed.
 *
 * THE ACCEPT IS RPC-ONLY, deliberately: guard_service_request_status refuses broadcasting→accepted as a
 * raw write, because matching must be atomic and announce itself. So the arc uses accept_service_request
 * and asserts on its reason string — a refusal for the wrong reason is a test that proves nothing about
 * the thing it names.
 *
 * CLEANUP IS PART OF THE TEST: service role, in afterAll, with an asserted residue count.
 */
import { test, expect, Page, Browser } from '@playwright/test';
import { adminClient, cleanupServiceArc } from './_db-cleanup';

const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';
const CLIENT = 'romeobeltran@auth.workhiveph.com';
const PROVIDER = 'bryangarcia@auth.workhiveph.com';   // online freelancer identity
const TAG = 'SIMARC';

async function sessionFor(browser: Browser, email: string) {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.goto('/workhive/index.html', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => typeof (window as any).getDb === 'function', { timeout: 20000 });
  const ok = await page.evaluate(async ([mail, pass]) => {
    const db = (window as any).getDb();
    await db.auth.signOut();
    const { error } = await db.auth.signInWithPassword({ email: mail, password: pass });
    return !error;
  }, [email, PASSWORD]);
  expect(ok, `sign-in failed for ${email}`).toBe(true);
  return { ctx, page };
}

async function move(page: Page, id: string, to: string) {
  return page.evaluate(async ([rid, status]) => {
    const db = (window as any).getDb();
    const { data, error } = await db.from('service_requests')
      .update({ status }).eq('id', rid).select('id,status');
    if (error) return { ok: false, why: error.message.slice(0, 100) };
    if (!data || !data.length) return { ok: false, why: 'RLS returned 0 rows' };
    return { ok: true, why: '' };
  }, [id, to]);
}

test.describe('marketplace simulation — SJ-FULL, the whole arc in one session', () => {
  test.describe.configure({ mode: 'serial' });

  let C: { ctx: any; page: Page }, P: { ctx: any; page: Page };
  let REQ = '', PROV = '';
  /* THE TWO FIGURES MUST DIFFER, or step 7 proves nothing. "Commission bills amount_paid, not the
     catalogue/budget price" is the entire reason service_payments exists — and with budget == paid the
     assertion passes identically whichever one the trigger reads. The first version had both at 1800: a
     vacuous test that would have gone green against the very bug it names
     ([[feedback_a_metamorphic_relation_needs_a_non_vacuity_check]]).
     Paying MORE than budgeted also stays clear of guard_payment_variance_explained, which only demands a
     written reason below 50% of the agreed base. */
  const BUDGET = 1800;
  const PAID = 2000;
  /* Consumer jobs are billed 10%, industrial 5% (mint_settlement_commission's segment default), with 1%
     cashback either way — so this arc's real net take is 9%, not the flat 4% the headline assumes. */
  const COMMISSION_PCT = 0.10, CASHBACK_PCT = 0.01;

  test.beforeAll(async ({ browser }) => {
    C = await sessionFor(browser, CLIENT);
    P = await sessionFor(browser, PROVIDER);
  });

  test.afterAll(async () => {
    try {
      await cleanupServiceArc(TAG);
    } finally { await C?.ctx.close(); await P?.ctx.close(); }
  });

  test('1 · the client files and broadcasts', async () => {
    const made = await C.page.evaluate(async ([tag, budget]) => {
      const db = (window as any).getDb();
      const { data: s } = await db.auth.getSession();
      // Deliberately no catalog_item_id and no location: this arc is about the STATE MACHINE, and a
      // category, cert or radius refusal would stop it at the accept for reasons that have their own
      // dedicated cells elsewhere. One test, one subject.
      const { data: prov } = await db.from('service_providers').select('hive_id')
        .not('hive_id', 'is', null).limit(1);
      const { data, error } = await db.from('service_requests').insert({
        client_auth_uid: s.session.user.id, hive_id: prov?.[0]?.hive_id, segment: 'consumer',
        mode: 'instant', status: 'requested', custom_scope: tag + ' full arc', budget,
      }).select('id').single();
      return error ? { err: error.message.slice(0, 120) } : { id: data.id };
    }, [TAG, BUDGET] as any);
    expect(made.err, `the client could not file: ${made.err}`).toBeUndefined();
    REQ = made.id!;
    expect((await move(C.page, REQ, 'broadcasting')).ok, 'requested → broadcasting refused').toBe(true);
  });

  test('2 · the provider accepts through the RPC, and a raw write cannot', async () => {
    // The refusal half first: matching must not be settable by hand, or the accept's atomicity and its
    // announcement are both bypassable.
    const raw = await move(P.page, REQ, 'accepted');
    expect(raw.ok, 'a provider set status=accepted with a RAW WRITE — matching is meant to be RPC-only, '
      + 'so this bypasses both the atomic race resolution and the announcement').toBe(false);

    const acc = await P.page.evaluate(async (rid) => {
      const db = (window as any).getDb();
      const { data, error } = await db.rpc('accept_service_request', { p_request_id: rid });
      return { accepted: !!data?.accepted, reason: data?.reason || error?.message,
               providerId: data?.provider_id };
    }, REQ);
    expect(acc.accepted, `an eligible online provider could not accept: ${acc.reason}`).toBe(true);
    // Keep the profile id the RPC resolved: `auth_uid` carries no SELECT grant for `authenticated`
    // (deliberately — it would map profiles to people), so it cannot be used as a filter, and the RPC's
    // own answer is both permitted and unambiguous.
    PROV = acc.providerId!;
    expect(PROV, 'the accept RPC reported success without naming which provider it matched').toBeTruthy();
  });

  test('3 · the provider drives their half, and the client cannot', async () => {
    for (const [from, to] of [['accepted', 'en_route'], ['en_route', 'on_site'],
                              ['on_site', 'in_progress'], ['in_progress', 'completed']]) {
      // The client must not be able to advance the provider's half — asserted at EVERY step, not once,
      // because a state machine is defined by who may not move it.
      const wrong = await move(C.page, REQ, to);
      expect(wrong.ok, `the CLIENT drove ${from} → ${to}, which belongs to the provider`).toBe(false);

      const r = await move(P.page, REQ, to);
      expect(r.ok, `the matched provider was refused their own transition ${from} → ${to}: ${r.why}`)
        .toBe(true);
    }

    /* COMPLETING THE WORK RELEASES THE PROVIDER. It did not before: sync_provider_availability listed
       'completed' in neither its busy set nor its free set, so a provider who had finished stayed
       'on_job' — invisible to every broadcast — until the CLIENT pressed Release. Under confirm-to-release
       the client has already had the service and already paid directly, so the only thing Release still
       does for them is mint their own cashback; a provider's ability to earn cannot hang on that. */
    const avail = await P.page.evaluate(async (pid) => {
      const db = (window as any).getDb();
      const { data } = await db.from('service_providers').select('availability').eq('id', pid);
      return data?.[0]?.availability;
    }, PROV);
    expect(avail, 'the provider is STILL marked on_job after completing the work, so they cannot be '
      + 'found for the next job until the client happens to press Release').toBe('online');
  });

  test('4 · settling without a payment record is refused', async () => {
    // The guard added with service_payments: release and record must not diverge, or commission bills a
    // price nobody ever confirmed.
    const r = await move(C.page, REQ, 'settled');
    expect(r.ok, 'a job SETTLED with no payment record — commission would bill the catalogue price for a '
      + 'job that may have been paid something else entirely').toBe(false);
  });

  test('5 · the client records the payment, and ONLY the client may', async () => {
    // The payee must not be able to declare their own payment: that is the self-mint this arc removed
    // from the tier ladder, rebuilt on the money path.
    const byProvider = await P.page.evaluate(async ([rid, amt]) => {
      const db = (window as any).getDb();
      const { data: s } = await db.auth.getSession();
      const { data, error } = await db.from('service_payments').insert({
        request_id: rid, amount_paid: amt, method: 'cash', confirmed_by: s.session.user.id,
      }).select('id');
      return error ? 'refused' : (data?.length ? 'ACCEPTED' : 'refused:0rows');
    }, [REQ, PAID] as any);
    expect(byProvider, 'the PROVIDER recorded the payment they were about to be paid — the payee '
      + 'declaring their own receipt is exactly the self-mint pattern').not.toBe('ACCEPTED');

    const byClient = await C.page.evaluate(async ([rid, amt]) => {
      const db = (window as any).getDb();
      const { data: s } = await db.auth.getSession();
      const { data, error } = await db.from('service_payments').insert({
        request_id: rid, amount_paid: amt, method: 'gcash', gcash_ref: '1234567890123',
        confirmed_by: s.session.user.id,
      }).select('id');
      return error ? { err: error.message.slice(0, 110) } : { id: data?.[0]?.id };
    }, [REQ, PAID] as any);
    expect(byClient.err, `the client could not record their own payment: ${byClient.err}`).toBeUndefined();
  });

  test('6 · the PROVIDER can read what they were paid', async () => {
    /* The defect this arc found. service_payments_read matched `r.matched_provider_id = auth.uid()` —
       a service_providers.id compared to an auth.users.id, disjoint id spaces, so the provider branch
       matched zero rows always. The provider is billed commission computed from amount_paid; being
       unable to read it means being unable to check or dispute the figure they are charged on. */
    const seen = await P.page.evaluate(async (rid) => {
      const db = (window as any).getDb();
      const { data, error } = await db.from('service_payments')
        .select('amount_paid,method,gcash_ref').eq('request_id', rid);
      return { rows: data?.length ?? 0, amount: Number(data?.[0]?.amount_paid ?? 0),
               err: error?.message?.slice(0, 80) };
    }, REQ);
    expect(seen.rows, 'the provider cannot read the payment record for their OWN job, while being '
      + `charged a commission computed from its amount (${seen.err || 'no rows'})`).toBe(1);
    expect(seen.amount, 'the provider reads a different amount than was recorded').toBe(PAID);
  });

  test('7 · the client releases, and the money moves exactly once', async () => {
    expect((await move(C.page, REQ, 'settled')).ok, 'completed → settled refused to the client').toBe(true);

    /* EACH PARTY CHECKS THEIR OWN SIDE, because that is all either can see and it is the stronger
       assertion anyway. service_credit_ledger_own_read scopes rows to the caller's consumer account or
       their own provider profiles — so the commission row (provider account) is invisible to the client
       and the cashback row (consumer account) is invisible to the provider. Reading both from one
       session returned zero commission rows and looked exactly like "the money never minted". */
    const readLedger = (page: Page) => page.evaluate(async (rid) => {
      const db = (window as any).getDb();
      const { data } = await db.from('service_credit_ledger')
        .select('entry_type,amount,account_type').eq('ref_id', rid);
      return data || [];
    }, REQ);
    const led = [...(await readLedger(P.page)), ...(await readLedger(C.page))];
    const of = (t: string) => led.filter((r: any) => r.entry_type === t);
    /* THE MONEY MODEL CHANGED, so this cell changed with it (2026-08-03, mig 20260803000030).
       It used to assert exactly one commission row and one cashback row. Both are now ZERO by decision,
       not by accident: the credits plan says "No revenue. The platform takes no commission and no spread"
       and "the existing 1% cashback is REPLACED by the 10% reward". A settled job therefore takes nothing
       from the provider and mints nothing for the buyer.

       What is still asserted is the part that matters most and did NOT change: settling is IDEMPOTENT.
       Zero is only meaningful if a second release cannot make it one (cell 8 drives exactly that). */
    expect(of('commission').length, 'settling took ' + of('commission').length + ' commission rows from '
      + 'the provider — the platform takes no commission (mig 20260803000030)').toBe(0);
    expect(of('cashback').length, 'settling minted ' + of('cashback').length + ' cashback rows — the 1% '
      + 'was retired when the 10% reward replaced it').toBe(0);
    /* KNOWN OPEN QUESTION, deliberately not asserted here: with cashback retired, a SERVICE buyer now
       earns nothing at all. On a LISTING the buyer's 10% is funded by the seller's reservation, but a
       service job has no reservation to pass, so there is no funding source for a service-side reward.
       Whether providers should reserve on services too is Ian's call, and this cell will assert the
       earn once that is decided. Asserting a number now would freeze a policy nobody has chosen. */
  });

  test('8 · a double-tapped release mints nothing further', async () => {
    // P-IMPULSIVE in its mechanical form. The transition is already illegal from `settled`, but the
    // assertion that matters is the LEDGER, not the refusal: a guard that refuses while a trigger has
    // already fired twice is still a double-mint.
    await move(C.page, REQ, 'settled');
    await move(C.page, REQ, 'settled');
    const each = async (page: Page) => page.evaluate(async (rid) => {
      const db = (window as any).getDb();
      const { data } = await db.from('service_credit_ledger').select('entry_type').eq('ref_id', rid);
      return data || [];
    }, REQ);
    const rows = [...(await each(P.page)), ...(await each(C.page))];
    const counts = {
      commission: rows.filter((r: any) => r.entry_type === 'commission').length,
      cashback: rows.filter((r: any) => r.entry_type === 'cashback').length,
    };
    /* Both are 0 now that the platform takes no commission and cashback is retired — but this cell is
       NOT redundant. Its question was never "is the count 1", it is "can a second press change the
       count at all". Zero that a double-tap can turn into one is the same defect as one it can turn
       into two, and it is the shape a future earn mechanic would reintroduce. */
    expect(counts.commission, 'a re-pressed Release minted a commission — the platform takes none, so a '
      + 'double tap conjured a charge that no single press makes').toBe(0);
    expect(counts.cashback, 'a re-pressed Release minted a cashback — retired, so a double tap created '
      + 'credits from a mechanic that no longer exists').toBe(0);
  });

  test('9 · a second payment for the same job is refused', async () => {
    const r = await C.page.evaluate(async ([rid, amt]) => {
      const db = (window as any).getDb();
      const { data: s } = await db.auth.getSession();
      const { data, error } = await db.from('service_payments').insert({
        request_id: rid, amount_paid: amt, method: 'cash', confirmed_by: s.session.user.id,
      }).select('id');
      return error ? 'refused' : (data?.length ? 'ACCEPTED' : 'refused:0rows');
    }, [REQ, 999] as any);
    expect(r, 'a SECOND payment was recorded for one job — the record stops being a record of what '
      + 'happened, and commission has two amounts to choose between').not.toBe('ACCEPTED');
  });
});
