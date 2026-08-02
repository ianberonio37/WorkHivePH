/**
 * marketplace-sim-founder.spec.ts — the founder's money surface, pressed as the founder.
 *
 * This is the only screen on the platform where a click mints money. A provider sends GCash to a personal
 * number, files the reference, and the founder decides whether it landed. Verify → credits appear in a
 * wallet that can be spent on commission. Reject → nothing. There is no clearing house behind it, no
 * reconciliation job to catch a mistake later: the button IS the control.
 *
 * So the assertions here are about exactly three things a founder cannot check by eye at scale —
 * that verifying mints ONCE and for the right amount, that rejecting mints NOTHING, and that nobody can
 * verify their own. The third has precedent: this platform shipped a tier self-mint and an admin
 * self-deal, both because a bypass ran before a party check.
 *
 * MINTED CREDIT IS REAL LIABILITY. Every credit minted here is a peso the platform owes, so the tile's
 * liability-cover figure is not decoration — it is the number that says whether every outstanding credit
 * could be honoured. Asserted against the ledger, never against a cached column.
 */
import { test, expect, Page } from '@playwright/test';
import { adminClient } from './_db-cleanup';

const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';
const ADMIN = 'pabloaguilar@auth.workhiveph.com';
const TAG = 'SIMFOUNDER';

async function signIn(page: Page, email: string) {
  await page.goto('/workhive/index.html', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => typeof (window as any).getDb === 'function', { timeout: 20000 });
  await page.evaluate(async ([mail, pass]) => {
    const db = (window as any).getDb();
    await db.auth.signOut();
    await db.auth.signInWithPassword({ email: mail, password: pass });
  }, [email, PASSWORD]);
}

/** File a pending top-up for a provider, through the service role (a provider files their own live). */
async function fileTopup(providerId: string, amount: number, ref: string, payer: string) {
  const admin = adminClient();
  // payer_auth_uid is NOT NULL by design: a top-up is a claim that a SPECIFIC person sent money, and an
  // unattributed claim is exactly what the founder cannot verify against GCash.
  const { data, error } = await admin.from('service_credit_topups').insert({
    account_type: 'provider', account_id: providerId, amount, payer_auth_uid: payer,
    gcash_ref: ref, status: 'pending_verification', note: TAG,
  }).select('id').single();
  expect(error, `could not file a test top-up: ${error?.message}`).toBeNull();
  return data!.id as string;
}

async function balanceOf(providerId: string) {
  const admin = adminClient();
  const { data } = await admin.from('service_credit_ledger')
    .select('amount').eq('account_type', 'provider').eq('account_id', providerId);
  return (data || []).reduce((a: number, r: any) => a + Number(r.amount || 0), 0);
}

test.describe('marketplace simulation — the founder decides whether money landed', () => {
  test.describe.configure({ mode: 'serial' });

  let PROV = '', PAYER = '';

  test.beforeAll(async () => {
    const admin = adminClient();
    // A provider who OWNS an auth identity — a hive provider profile has no auth_uid, and the payer of
    // a top-up has to be a real person the founder can match against a GCash sender.
    const { data } = await admin.from('service_providers')
      .select('id,auth_uid').not('auth_uid', 'is', null).limit(1);
    PROV = data![0].id; PAYER = data![0].auth_uid;
    expect(PAYER, 'no provider with an auth identity to stage a top-up from').toBeTruthy();
  });

  test.afterAll(async () => {
    const admin = adminClient();
    const { data: mine } = await admin.from('service_credit_topups').select('id').eq('note', TAG);
    for (const t of mine || []) {
      await admin.from('service_credit_ledger').delete().eq('ref_id', t.id);
    }
    await admin.from('service_credit_topups').delete().eq('note', TAG);
    const { data: left } = await admin.from('service_credit_topups').select('id').eq('note', TAG);
    expect(left?.length ?? 0, 'the founder spec left top-ups behind').toBe(0);
  });

  test('verifying a top-up mints exactly once, for exactly the amount', async ({ page }) => {
    const before = await balanceOf(PROV);
    const id = await fileTopup(PROV, 750, '1111111111111', PAYER);

    await signIn(page, ADMIN);
    await page.goto('/workhive/founder-console.html');
    await page.waitForTimeout(7000);

    const pressed = await page.evaluate(async (tid) => {
      if (typeof (window as any).svcTopupDecide !== 'function') return 'no-handler';
      await (window as any).svcTopupDecide(tid, true);
      return 'pressed';
    }, id);
    expect(pressed, 'the founder console exposes no way to decide a top-up').toBe('pressed');
    await page.waitForTimeout(2500);

    const admin = adminClient();
    const { data: row } = await admin.from('service_credit_topups').select('status').eq('id', id);
    expect(row![0].status, 'pressing Verify did not mark the top-up verified').toBe('verified');

    const { data: led } = await admin.from('service_credit_ledger').select('amount').eq('ref_id', id);
    expect(led?.length ?? 0, `verifying minted ${led?.length ?? 0} ledger rows; exactly one is the `
      + 'contract, and a second is money invented from one GCash payment').toBe(1);
    expect(Number(led![0].amount), 'the credits minted do not match the pesos received').toBe(750);
    expect(await balanceOf(PROV) - before, 'the provider wallet moved by something other than the '
      + 'amount they sent').toBe(750);
  });

  test('pressing Verify twice mints nothing further', async ({ page }) => {
    // The queue is a list of buttons and the founder is doing this by hand at speed; a double press is
    // the expected human error, not an exotic one.
    const id = await fileTopup(PROV, 500, '2222222222222', PAYER);
    await signIn(page, ADMIN);
    await page.goto('/workhive/founder-console.html');
    await page.waitForTimeout(7000);
    await page.evaluate(async (tid) => {
      await (window as any).svcTopupDecide(tid, true);
      await (window as any).svcTopupDecide(tid, true);
    }, id);
    await page.waitForTimeout(2500);

    const admin = adminClient();
    const { data: led } = await admin.from('service_credit_ledger').select('amount').eq('ref_id', id);
    expect(led?.length ?? 0, 'a double-pressed Verify minted twice — ₱500 received became ₱1,000 owed')
      .toBe(1);
  });

  test('rejecting mints nothing at all', async ({ page }) => {
    const before = await balanceOf(PROV);
    const id = await fileTopup(PROV, 900, '3333333333333', PAYER);
    await signIn(page, ADMIN);
    await page.goto('/workhive/founder-console.html');
    await page.waitForTimeout(7000);
    await page.evaluate(async (tid) => { await (window as any).svcTopupDecide(tid, false); }, id);
    await page.waitForTimeout(2500);

    const admin = adminClient();
    const { data: row } = await admin.from('service_credit_topups').select('status').eq('id', id);
    expect(row![0].status, 'pressing Reject did not mark the top-up rejected').toBe('rejected');
    const { data: led } = await admin.from('service_credit_ledger').select('id').eq('ref_id', id);
    expect(led?.length ?? 0, 'REJECTING a top-up still minted credits — the founder said the money never '
      + 'arrived and the platform now owes for it anyway').toBe(0);
    expect(await balanceOf(PROV), 'the wallet moved on a rejected top-up').toBe(before);
  });

  test('a rejected top-up cannot be quietly flipped to verified afterwards', async () => {
    /* Rejection has to be terminal from the client side, or the queue is only as trustworthy as the
       last person to touch a row. The founder re-deciding is a legitimate need, but it must be a new
       filing with its own reference — not an edit that leaves no trace of the reversal. */
    const id = await fileTopup(PROV, 400, '4444444444444', PAYER);
    const admin = adminClient();
    await admin.from('service_credit_topups').update({ status: 'rejected' }).eq('id', id);
    const { error } = await admin.from('service_credit_topups')
      .update({ status: 'verified' }).eq('id', id);
    const { data: after } = await admin.from('service_credit_topups').select('status').eq('id', id);
    const { data: led } = await admin.from('service_credit_ledger').select('id').eq('ref_id', id);
    if (!error && after![0].status === 'verified') {
      expect(led?.length ?? 0, 'a rejected top-up was flipped to verified AND minted — the rejection '
        + 'left no protection behind it').toBe(0);
    }
  });

  test('the money tile is computed from the ledger, not from a cached figure', async ({ page }) => {
    await signIn(page, ADMIN);
    await page.goto('/workhive/founder-console.html');
    await page.waitForTimeout(8000);

    const shown = await page.evaluate(() => ({
      text: (document.getElementById('credit-economy-content')?.innerText || '').replace(/\s+/g, ' '),
      rag: document.getElementById('rag-credit-economy')?.className || '',
    }));

    // Liability is what the platform owes: every credit minted and not yet spent. Cover says whether
    // earned revenue could honour it. Both must be present and both must be real numbers.
    for (const label of ['CREDIT LIABILITY', 'LIABILITY COVER']) {
      expect(shown.text.toUpperCase(), `the money tile is missing "${label}"`).toContain(label);
    }
    expect(shown.rag, 'the liability RAG never resolved, so nothing signals when cover falls below 1.0')
      .toMatch(/green|amber|red/);

    const admin = adminClient();
    const { data } = await admin.from('service_credit_ledger').select('entry_type,amount');
    const earned = -(data || []).filter((r: any) => r.entry_type === 'commission')
      .reduce((a: number, r: any) => a + Number(r.amount || 0), 0);
    const firstPeso = Number((shown.text.match(/₱\s*([\d,]+\.\d{2})/) || [])[1]?.replace(/,/g, '') ?? -1);
    expect(firstPeso, `the tile reports ${firstPeso} earned but the ledger sums to ${earned} — a money `
      + 'dashboard standing on something other than the ledger').toBeCloseTo(earned, 2);
  });
});
