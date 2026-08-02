/**
 * marketplace-sim-money-ui.spec.ts — the client's money screen, driven through the UI.
 *
 * The arc spec proves the money spine at the DATA layer: a payment record exists, commission bills
 * amount_paid, the ledger mints once. It proves none of that is REACHABLE. Those are different claims,
 * and the gap between them is exactly where this platform lost its settle button: migration 15 added
 * service_payments and guard_settle_requires_payment, and `svcSettle` still wrote nothing but
 * status='settled'. Every press raised the guard's exception into a toast. The spine was green and the
 * only door to it was bricked shut — a working backend nobody can reach is not a working feature.
 *
 * So this spec presses the actual button. It fills the actual fields, submits, and then checks the DB
 * for what the click was supposed to produce. That is the only shape of test that can catch a migration
 * shipped without its interface.
 */
import { test, expect, Page, Browser } from '@playwright/test';
import { adminClient } from './_db-cleanup';

const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';
const CLIENT = 'romeobeltran@auth.workhiveph.com';
const PROVIDER = 'bryangarcia@auth.workhiveph.com';
const TAG = 'SIMMONEYUI';

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

/** Stage a job the client can settle: filed, accepted by a real provider, driven to completed. */
async function stageCompletedJob(C: Page, P: Page, budget: number) {
  const made = await C.evaluate(async ([tag, b]) => {
    const db = (window as any).getDb();
    const { data: s } = await db.auth.getSession();
    const { data: prov } = await db.from('service_providers').select('hive_id')
      .not('hive_id', 'is', null).limit(1);
    const { data, error } = await db.from('service_requests').insert({
      client_auth_uid: s.session.user.id, hive_id: prov?.[0]?.hive_id, segment: 'consumer',
      mode: 'instant', status: 'broadcasting', custom_scope: tag + ' ui settle', budget: b,
    }).select('id').single();
    return error ? { err: error.message.slice(0, 100) } : { id: data.id };
  }, [tag_(), budget] as any);
  expect(made.err, `could not stage: ${made.err}`).toBeUndefined();
  const rid = made.id!;

  const acc = await P.evaluate(async (r) => {
    const db = (window as any).getDb();
    const { data } = await db.rpc('accept_service_request', { p_request_id: r });
    return { ok: !!data?.accepted, reason: data?.reason };
  }, rid);
  expect(acc.ok, `provider could not accept the staged job: ${acc.reason}`).toBe(true);

  for (const st of ['en_route', 'on_site', 'in_progress', 'completed']) {
    const r = await P.evaluate(async ([id, s]) => {
      const db = (window as any).getDb();
      const { data, error } = await db.from('service_requests').update({ status: s })
        .eq('id', id).select('id');
      return { ok: !error && !!data?.length, why: error?.message?.slice(0, 80) };
    }, [rid, st] as any);
    expect(r.ok, `staging stalled at ${st}: ${r.why}`).toBe(true);
  }
  return rid;
}
function tag_() { return TAG; }

/** Open the services view and render the client's own jobs. */
async function openMyJobs(page: Page) {
  await page.goto('/workhive/marketplace.html');
  await page.waitForTimeout(3500);
  await page.click('[data-section="services"]');
  await page.waitForTimeout(3000);
}

test.describe('marketplace simulation — the money screen, through the UI', () => {
  test.describe.configure({ mode: 'serial' });

  let C: { ctx: any; page: Page }, P: { ctx: any; page: Page };
  let REQ = '';
  const BUDGET = 2400;

  test.beforeAll(async ({ browser }) => {
    C = await sessionFor(browser, CLIENT);
    P = await sessionFor(browser, PROVIDER);
    REQ = await stageCompletedJob(C.page, P.page, BUDGET);
  });

  test.afterAll(async () => {
    try {
      const admin = adminClient();
      if (REQ) {
        await admin.from('service_credit_ledger').delete().eq('ref_id', REQ);
        await admin.from('service_payments').delete().eq('request_id', REQ);
        await admin.from('service_job_events').delete().eq('request_id', REQ);
      }
      await admin.from('service_requests').delete().ilike('custom_scope', TAG + '%');
      await admin.rpc('reconcile_provider_availability');   // the accept flipped a shared fixture
      const { data: left } = await admin.from('service_requests')
        .select('id').ilike('custom_scope', TAG + '%');
      expect(left?.length ?? 0, 'the money-UI spec left requests behind').toBe(0);
    } finally { await C?.ctx.close(); await P?.ctx.close(); }
  });

  test('a completed job offers a way to confirm payment, above the fold and tappable', async () => {
    await openMyJobs(C.page);
    const cta = await C.page.evaluate((rid) => {
      const btn = Array.from(document.querySelectorAll('button'))
        .find(b => /confirm payment|mark as paid/i.test(b.innerText || '')
                && (b.getAttribute('onclick') || '').includes(rid));
      if (!btn) return null;
      const r = btn.getBoundingClientRect();
      return { text: btn.innerText.trim(), h: Math.round(r.height) };
    }, REQ);
    expect(cta, 'a COMPLETED job offers the client no way to confirm payment — the money spine has no '
      + 'door').toBeTruthy();
    expect(cta!.h, 'the confirm-payment button is under the 44px tap floor').toBeGreaterThanOrEqual(44);
  });

  test('the form asks for the amount, and says the platform never holds the money', async () => {
    await C.page.evaluate((rid) => (window as any).svcConfirmPay(rid, 2400), REQ);
    await C.page.waitForTimeout(600);
    const f = await C.page.evaluate((rid) => {
      const slot = document.getElementById('svc-pay-' + rid);
      return {
        amount: !!document.getElementById('svc-pay-amt-' + rid),
        method: !!document.getElementById('svc-pay-method-' + rid),
        text: (slot?.innerText || '').toLowerCase(),
      };
    }, REQ);
    expect(f.amount, 'the form never asks what was actually paid — the figure commission is billed on')
      .toBe(true);
    expect(f.method, 'the form never asks how it was paid').toBe(true);
    // P-SCAMWARY: the person deciding whether this is a trick needs to be told, on this screen, that the
    // platform is not taking their money. Saying it elsewhere does not help them here.
    expect(f.text, 'the money screen never states that WorkHive does not hold the payment — the one '
      + 'sentence that decides whether a wary first-time user presses the button')
      .toMatch(/never holds|directly/);
  });

  test('an empty amount is refused by NAME, and nothing is written', async () => {
    await C.page.evaluate((rid) => {
      (document.getElementById('svc-pay-amt-' + rid) as HTMLInputElement).value = '';
      (document.getElementById('svc-pay-go-' + rid) as HTMLButtonElement).click();
    }, REQ);
    await C.page.waitForTimeout(1200);
    const body = await C.page.evaluate(() => document.body.innerText.toLowerCase());
    expect(body, 'submitting with no amount says nothing, or says something that does not name the '
      + 'amount').toMatch(/amount you actually paid/);

    const admin = adminClient();
    const { data } = await admin.from('service_payments').select('id').eq('request_id', REQ);
    expect(data?.length ?? 0, 'a refused submit still wrote a payment row').toBe(0);
  });

  test('confirming records the payment AND settles, in one press', async () => {
    await C.page.evaluate((rid) => {
      (document.getElementById('svc-pay-amt-' + rid) as HTMLInputElement).value = '2600';
      const m = document.getElementById('svc-pay-method-' + rid) as HTMLSelectElement;
      m.value = 'gcash'; m.dispatchEvent(new Event('change', { bubbles: true }));
      (document.getElementById('svc-pay-ref-' + rid) as HTMLInputElement).value = '9876543210987';
      (document.getElementById('svc-pay-go-' + rid) as HTMLButtonElement).click();
    }, REQ);
    await C.page.waitForTimeout(3500);

    const admin = adminClient();
    const { data: pay } = await admin.from('service_payments')
      .select('amount_paid,method,gcash_ref').eq('request_id', REQ);
    expect(pay?.length ?? 0, 'pressing Confirm wrote NO payment record — the button that is supposed to '
      + 'record the payment did not').toBe(1);
    expect(Number(pay![0].amount_paid), 'the recorded amount is not what the client typed').toBe(2600);
    expect(pay![0].gcash_ref, 'the GCash reference was dropped, so the founder cannot match it')
      .toBe('9876543210987');

    const { data: req } = await admin.from('service_requests').select('status').eq('id', REQ);
    expect(req![0].status, 'the payment was recorded but the job never released — the provider is still '
      + 'waiting on a client who believes they already confirmed').toBe('settled');

    // And the money moved, billed against what was actually paid (2600), not the 2400 budgeted.
    const { data: led } = await admin.from('service_credit_ledger')
      .select('entry_type,amount').eq('ref_id', REQ);
    const commission = (led || []).filter((r: any) => r.entry_type === 'commission');
    const cashback = (led || []).filter((r: any) => r.entry_type === 'cashback');
    expect(commission.length, 'settling through the UI minted no commission').toBe(1);
    expect(Math.abs(Number(commission[0].amount)), 'commission was billed against the BUDGET (2400) '
      + 'rather than what was actually paid (2600)').toBeCloseTo(260, 2);
    expect(cashback.length, 'the consumer never got the cashback they were promised').toBe(1);
  });
});
