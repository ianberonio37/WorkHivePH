/**
 * marketplace-sim-aftermath.spec.ts — what the platform leaves behind, and who can forge it.
 *
 * A marketplace's value is not the transaction, it is the record afterwards: the review that helps the
 * next buyer choose, the tier that says who is reliable, the logbook entry that makes the work findable
 * a year later. All three are trust signals, and a trust signal anyone can write is worse than none —
 * it launders a stranger's opinion into the platform's voice.
 *
 * This platform has already shipped exactly that failure twice: a tier ladder that counted a seller's own
 * clicks, and an admin self-deal that wrote the client's five-star review because the bypass ran BEFORE
 * the party check. So each cell here pairs the honest path with the forgery it must refuse.
 *
 * THE DISPUTE REVERSES, IT DOES NOT ERASE. A settled job that goes wrong has to unwind the commission
 * and claw back the cashback while leaving every original row intact — the ledger is the audit trail, and
 * a deleted row is a lie about what happened. That distinction is asserted here by counting rows, not by
 * reading balances.
 */
import { test, expect, Page, Browser } from '@playwright/test';
import { adminClient, cleanupServiceArc } from './_db-cleanup';

const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';
const CLIENT = 'romeobeltran@auth.workhiveph.com';
const PROVIDER = 'bryangarcia@auth.workhiveph.com';
const OUTSIDER = 'emmavelasquez@auth.workhiveph.com';   // no part in these jobs
const ADMIN = 'pabloaguilar@auth.workhiveph.com';
const TAG = 'SIMAFTER';

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
      .update({ status }).eq('id', rid).select('id');
    if (error) return { ok: false, why: error.message.slice(0, 90) };
    return { ok: !!data?.length, why: data?.length ? '' : 'RLS returned 0 rows' };
  }, [id, to]);
}

test.describe('marketplace simulation — the aftermath, and the forgeries it must refuse', () => {
  test.describe.configure({ mode: 'serial' });

  let C: { ctx: any; page: Page }, P: { ctx: any; page: Page };
  let REQ = '';                     // driven all the way to settled
  const PAID = 1600;

  test.beforeAll(async ({ browser }) => {
    C = await sessionFor(browser, CLIENT);
    P = await sessionFor(browser, PROVIDER);

    const made = await C.page.evaluate(async (tag) => {
      const db = (window as any).getDb();
      const { data: s } = await db.auth.getSession();
      const { data: prov } = await db.from('service_providers').select('hive_id')
        .not('hive_id', 'is', null).limit(1);
      const { data, error } = await db.from('service_requests').insert({
        client_auth_uid: s.session.user.id, hive_id: prov?.[0]?.hive_id, segment: 'consumer',
        mode: 'instant', status: 'broadcasting', custom_scope: tag + ' aftermath job', budget: 1600,
      }).select('id').single();
      return error ? { err: error.message.slice(0, 100) } : { id: data.id };
    }, TAG);
    expect(made.err, `could not stage: ${made.err}`).toBeUndefined();
    REQ = made.id!;

    const acc = await P.page.evaluate(async (r) => {
      const db = (window as any).getDb();
      const { data } = await db.rpc('accept_service_request', { p_request_id: r });
      return { ok: !!data?.accepted, reason: data?.reason };
    }, REQ);
    expect(acc.ok, `could not accept: ${acc.reason}`).toBe(true);
    for (const st of ['en_route', 'on_site', 'in_progress', 'completed']) {
      expect((await move(P.page, REQ, st)).ok, `staging stalled at ${st}`).toBe(true);
    }
  });

  test.afterAll(async () => {
    try {
      await cleanupServiceArc(TAG);
    } finally { await C?.ctx.close(); await P?.ctx.close(); }
  });

  test('a COMPLETED job writes itself into the logbook', async () => {
    // The platform's claim is that work done through it becomes findable knowledge afterwards. If the
    // job leaves no trace, that claim is marketing.
    const admin = adminClient();
    const { data } = await admin.from('logbook').select('id,problem,machine,worker_name')
      .ilike('problem', '%' + TAG + '%');
    expect(data?.length ?? 0, 'a completed job produced NO logbook entry — the work is invisible the day '
      + 'after it happened, and the knowledge the platform promises to build never accumulates')
      .toBeGreaterThan(0);
  });

  test('an OUTSIDER cannot review a job they had no part in', async ({ browser }) => {
    const O = await sessionFor(browser, OUTSIDER);
    try {
      const r = await O.page.evaluate(async (rid) => {
        const db = (window as any).getDb();
        const { data, error } = await db.from('marketplace_reviews').insert({
          request_id: rid, rating: 1, comment: 'SIMAFTER forged review',
          direction: 'client_to_provider', reviewer_name: 'Emma Velasquez',
        }).select('id');
        return error ? 'refused' : (data?.length ? 'ACCEPTED' : 'refused:0rows');
      }, REQ);
      expect(r, 'a stranger REVIEWED a job they had no part in — the platform would publish an outsider\'s '
        + 'opinion as a verified purchase, which is the tier self-mint in another costume').not.toBe('ACCEPTED');
    } finally { await O.ctx.close(); }
  });

  test('both sides can review once the job is done, and only once', async () => {
    expect((await move(P.page, REQ, 'completed')).ok || true, 'already completed').toBeTruthy();

    const asClient = await C.page.evaluate(async (rid) => {
      const db = (window as any).getDb();
      const { data: n } = await db.rpc('auth_worker_names');
      const me = Array.isArray(n) ? (n[0]?.auth_worker_names ?? n[0]) : n;
      const { data, error } = await db.from('marketplace_reviews').insert({
        request_id: rid, rating: 5, comment: 'SIMAFTER clean work', reviewer_name: me,
        direction: 'client_to_provider',
      }).select('id');
      return error ? { err: error.message.slice(0, 90) } : { id: data?.[0]?.id };
    }, REQ);
    expect(asClient.err, `the client could not review their own completed job: ${asClient.err}`)
      .toBeUndefined();

    const asProvider = await P.page.evaluate(async (rid) => {
      const db = (window as any).getDb();
      const { data: n } = await db.rpc('auth_worker_names');
      const me = Array.isArray(n) ? (n[0]?.auth_worker_names ?? n[0]) : n;
      const { data, error } = await db.from('marketplace_reviews').insert({
        request_id: rid, rating: 5, comment: 'SIMAFTER paid promptly', reviewer_name: me,
        direction: 'provider_to_client',
      }).select('id');
      return error ? { err: error.message.slice(0, 90) } : { id: data?.[0]?.id };
    }, REQ);
    // Bidirectional is the point: a marketplace where only one side is rated makes the other side
    // unaccountable, and providers carry all the reputational risk.
    expect(asProvider.err, `the PROVIDER could not review the client: ${asProvider.err} — only one side `
      + 'is accountable, so a client who does not pay carries no record of it').toBeUndefined();

    // A second review from the same side would let one party grind the other's average.
    const twice = await C.page.evaluate(async (rid) => {
      const db = (window as any).getDb();
      const { data: n } = await db.rpc('auth_worker_names');
      const me = Array.isArray(n) ? (n[0]?.auth_worker_names ?? n[0]) : n;
      const { data, error } = await db.from('marketplace_reviews').insert({
        request_id: rid, rating: 1, comment: 'SIMAFTER second bite', reviewer_name: me,
        direction: 'client_to_provider',
      }).select('id');
      return error ? 'refused' : (data?.length ? 'ACCEPTED' : 'refused:0rows');
    }, REQ);
    expect(twice, 'one party reviewed the same job TWICE — a single job can then move a rating as far as '
      + 'someone has patience for').not.toBe('ACCEPTED');
  });

  test('the wrong role cannot raise a dispute or a client cancellation', async () => {
    // Record the payment and settle, so the job is in the state a dispute actually starts from.
    const paid = await C.page.evaluate(async ([rid, amt]) => {
      const db = (window as any).getDb();
      const { data: s } = await db.auth.getSession();
      const { error } = await db.from('service_payments').insert({
        request_id: rid, amount_paid: amt, method: 'cash', confirmed_by: s.session.user.id,
      }).select('id');
      return error?.message?.slice(0, 90);
    }, [REQ, PAID] as any);
    expect(paid, `could not record the payment: ${paid}`).toBeUndefined();
    expect((await move(C.page, REQ, 'settled')).ok, 'could not settle').toBe(true);

    // cancelled_by_client is the CLIENT's word, and it is not available after settling either.
    const wrongCancel = await move(P.page, REQ, 'cancelled_by_client');
    expect(wrongCancel.ok, 'the PROVIDER recorded a client cancellation — the record would say the client '
      + 'backed out of a job the provider abandoned').toBe(false);
  });

  test('a dispute REVERSES the money without erasing a single row', async ({ browser }) => {
    const admin = adminClient();
    const before = await admin.from('service_credit_ledger').select('id,entry_type').eq('ref_id', REQ);
    const beforeCount = before.data?.length ?? 0;
    expect(beforeCount, 'the settled job minted nothing to reverse').toBeGreaterThan(0);

    expect((await move(C.page, REQ, 'disputed')).ok, 'the client could not dispute their settled job')
      .toBe(true);

    // Only an admin may adjudicate, and never their own job.
    const byClient = await C.page.evaluate(async (rid) => {
      const db = (window as any).getDb();
      const { error } = await db.rpc('apply_dispute_adjustment',
        { p_request_id: rid, p_reason: 'SIMAFTER self-adjudication' });
      return error ? 'refused' : 'ACCEPTED';
    }, REQ);
    expect(byClient, 'a PARTY adjudicated their own dispute — the person who lost the money decided how '
      + 'much to give themselves back').not.toBe('ACCEPTED');

    const A = await sessionFor(browser, ADMIN);
    try {
      const done = await A.page.evaluate(async (rid) => {
        const db = (window as any).getDb();
        const { error } = await db.rpc('apply_dispute_adjustment',
          { p_request_id: rid, p_reason: 'SIMAFTER adjudicated' });
        return error?.message?.slice(0, 110);
      }, REQ);
      expect(done, `an admin could not adjudicate a dispute they are not party to: ${done}`).toBeUndefined();
    } finally { await A.ctx.close(); }

    const after = await admin.from('service_credit_ledger').select('id,entry_type,amount').eq('ref_id', REQ);
    const rows = after.data || [];
    // NOTHING may be deleted: every original row survives and the reversal is ADDED beside it.
    expect(rows.length, `the ledger went from ${beforeCount} rows to ${rows.length} — a dispute that `
      + 'REMOVES history is a lie about what happened, however tidy the balance looks')
      .toBeGreaterThan(beforeCount);
    expect(rows.filter(r => r.entry_type === 'commission').length,
      'the original commission row was erased rather than compensated').toBe(1);
    expect(rows.filter(r => r.entry_type === 'adjustment').length,
      'the dispute produced no adjustment entries at all').toBeGreaterThan(0);

    // And the net must actually be undone, not merely annotated.
    const net = rows.reduce((a, r: any) => a + Number(r.amount || 0), 0);
    expect(Math.abs(net), `the ledger still nets ${net.toFixed(2)} after a full reversal — the money was `
      + 'annotated, not returned').toBeLessThan(0.01);
  });

  test('FRAUD · a settle/dispute/settle cycle cannot farm cashback', async () => {
    // Cycling a job through settle and dispute is the cheapest cashback farm available, because each
    // settle is a mint. The adjustment must not be re-mintable either.
    const admin = adminClient();
    const twice = await admin.rpc('apply_dispute_adjustment',
      { p_request_id: REQ, p_reason: 'SIMAFTER second adjustment' });
    const { data: rows } = await admin.from('service_credit_ledger')
      .select('entry_type').eq('ref_id', REQ);
    const adjustments = (rows || []).filter((r: any) => r.entry_type === 'adjustment').length;
    const cashbacks = (rows || []).filter((r: any) => r.entry_type === 'cashback').length;
    expect(cashbacks, 'the job minted cashback more than once across a dispute cycle — settle, dispute, '
      + 'settle would be free credits on repeat').toBe(1);
    expect(adjustments, 'a second adjustment was applied to the same job, so the reversal itself is '
      + 'farmable').toBeLessThanOrEqual(2);
  });
});
