/**
 * marketplace-sim-fraud.spec.ts — the FRAUD tier of the marketplace simulation registry.
 *
 * The other specs ask "does this work for an honest user?". This one plays an adversary and asks what a
 * motivated person can actually take. That distinction is not academic here: this platform has shipped a
 * live tier self-mint (gold was 51 self-marked clicks) and an admin self-deal (a provider-admin wrote the
 * client's own 5-star review, because the admin bypass ran BEFORE the party check). Both were found by
 * attacking, neither by testing.
 *
 * ATTACK AS A REAL USER, NEVER AS THE TABLE OWNER. The SQL fraud probes run as `postgres`, which owns
 * these tables and BYPASSES RLS — and several guards deliberately exempt backend writes (auth.uid() IS
 * NULL) because seeders and system triggers are already vetted. An attack run with those privileges
 * measures the EXEMPTION, not the guard. That exact mistake made the A3 understatement attack report
 * "still open" after it had been closed. So every attack here runs through a real signed-in browser
 * session, which is the only privilege a real attacker has.
 *
 * EACH ATTACK IS REFUSED OR DETECTED — never silently absorbed. An attack that neither fails nor
 * registers anywhere is the one that runs in production for months.
 */
import { test, expect, Page, Browser } from '@playwright/test';
import { adminClient } from './_db-cleanup';

const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';
const ATTACKER = 'romeobeltran@auth.workhiveph.com';
const TAG = 'SIMFRAUD';

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

test.describe('marketplace simulation — fraud tier (attacks run as a real user)', () => {
  test.describe.configure({ mode: 'serial' });
  let A: { ctx: any; page: Page };

  test.beforeAll(async ({ browser }) => { A = await sessionFor(browser, ATTACKER); });

  test.afterAll(async () => {
    // Service role, and CHECKED — a cleanup that cannot prove it cleaned is a no-op that looks like
    // success, which this suite already learned the hard way.
    try {
      const admin = adminClient();
      await admin.from('service_credit_ledger').delete().ilike('note', TAG + '%');
      await admin.from('service_requests').delete().ilike('custom_scope', TAG + '%');
      const { data: left } = await admin.from('service_credit_ledger').select('id').ilike('note', TAG + '%');
      expect(left?.length ?? 0, 'the fraud spec left ledger rows behind').toBe(0);
    } finally { await A?.ctx.close(); }
  });

  test('A7 the ledger is append-only to a real user: no INSERT, UPDATE or DELETE', async () => {
    const r = await A.page.evaluate(async (tag) => {
      const db = (window as any).getDb();
      const { data: s } = await db.auth.getSession();
      const uid = s.session.user.id;
      const out: Record<string, string> = {};

      // MINT: credits from thin air, to myself.
      const ins = await db.from('service_credit_ledger').insert({
        account_type: 'consumer', account_id: uid, entry_type: 'cashback', amount: 999999,
        ref_kind: 'service_request', note: tag + ' self-mint',
      }).select('id');
      out.insert = ins.error ? 'refused:' + (ins.error.code || '') : (ins.data?.length ? 'ACCEPTED' : 'refused:0rows');

      // REWRITE history rather than compensating it.
      const upd = await db.from('service_credit_ledger').update({ amount: 0 })
        .eq('entry_type', 'commission').select('id');
      out.update = upd.error ? 'refused:' + (upd.error.code || '') : (upd.data?.length ? 'ACCEPTED' : 'refused:0rows');

      // ERASE it.
      const del = await db.from('service_credit_ledger').delete()
        .eq('entry_type', 'commission').select('id');
      out.delete = del.error ? 'refused:' + (del.error.code || '') : (del.data?.length ? 'ACCEPTED' : 'refused:0rows');
      return out;
    }, TAG);

    expect(r.insert, 'a user MINTED credits for themselves').not.toBe('ACCEPTED');
    expect(r.update, 'a user REWROTE a commission row — the ledger must be compensated, never edited')
      .not.toBe('ACCEPTED');
    expect(r.delete, 'a user DELETED a ledger row — a deleted row is a lie about what happened')
      .not.toBe('ACCEPTED');
  });

  test('A1 a provider cannot accept their own request', async ({ browser }) => {
    /* STAGED WITH A REAL PROVIDER, deliberately. The first version ran this as the ordinary attacker,
       who owns no provider identity — so accept_service_request refused at `no_online_provider_identity`
       and never reached the self-deal check at all. The assertion still went green, which would have
       kept going green even if a genuine provider COULD accept their own job. An attack staged so it
       cannot reach the guard is not a test of the guard. */
    const P = await sessionFor(browser, 'pabloaguilar@auth.workhiveph.com');   // owns provider identities
    const r = await P.page.evaluate(async (tag) => {
      const db = (window as any).getDb();
      const { data: s } = await db.auth.getSession();
      const { data: prov } = await db.from('service_providers').select('id,hive_id').limit(1);
      const { data: req, error } = await db.from('service_requests').insert({
        client_auth_uid: s.session.user.id, hive_id: prov?.[0]?.hive_id, segment: 'consumer',
        mode: 'instant', status: 'broadcasting', custom_scope: tag + ' self-deal', budget: 1200,
      }).select('id').single();
      if (error) return { made: false, why: error.message.slice(0, 80) };
      const acc = await db.rpc('accept_service_request', { p_request_id: req.id });
      return { made: true, accepted: !!acc.data?.accepted, reason: acc.data?.reason || acc.error?.message };
    }, TAG);
    await P.ctx.close();
    test.skip(!r.made, `could not stage the attack: ${r.why}`);
    expect(r.accepted, 'a provider ACCEPTED their own request — a wash trade that inflates every trust '
      + 'metric and mints cashback to the same person').toBe(false);
    // The reason must be the SELF-DEAL one. Any other refusal means the attack never reached the guard,
    // and a green here would be meaningless.
    expect(String(r.reason), `refused as "${r.reason}" rather than own_request — the attack did not `
      + 'reach the self-deal check, so this proves nothing about it').toMatch(/own_request/i);
  });

  test('A6 nobody may verify their own GCash top-up', async () => {
    const r = await A.page.evaluate(async (tag) => {
      const db = (window as any).getDb();
      const { data: s } = await db.auth.getSession();
      const { data: prov } = await db.from('service_providers').select('id').limit(1);
      // File a top-up ALREADY marked verified — minting money by skipping the founder's check.
      const ins = await db.from('service_credit_topups').insert({
        account_type: 'provider', account_id: prov?.[0]?.id, payer_auth_uid: s.session.user.id,
        amount: 5000, gcash_ref: String(Date.now()).slice(0, 13), status: 'verified', note: tag,
      }).select('id');
      return ins.error ? 'refused:' + (ins.error.code || '') : (ins.data?.length ? 'ACCEPTED' : 'refused:0rows');
    }, TAG);
    expect(r, 'a user filed a SELF-VERIFIED top-up — that is minting money without anyone checking '
      + 'GCash').not.toBe('ACCEPTED');
  });

  test('A8 a hive cannot lower its own gold bar', async () => {
    const r = await A.page.evaluate(async () => {
      const db = (window as any).getDb();
      const { data: prov } = await db.from('service_providers').select('hive_id')
        .not('hive_id', 'is', null).limit(1);
      const hive = prov?.[0]?.hive_id;
      if (!hive) return 'no-hive';
      const up = await db.from('hive_service_settings')
        .upsert({ hive_id: hive, tier_gold_sales: 1, tier_silver_sales: 1 }).select('hive_id');
      return up.error ? 'refused:' + (up.error.code || '') : (up.data?.length ? 'ACCEPTED' : 'refused:0rows');
    });
    test.skip(r === 'no-hive', 'no hive-scoped provider available');
    expect(r, 'a hive set its own gold threshold to 1 — the trust ladder becomes self-service and a '
      + 'badge stops meaning anything across hives').not.toBe('ACCEPTED');
  });

  test('A10 a stranger cannot read another party\'s job tracking', async () => {
    const r = await A.page.evaluate(async () => {
      const db = (window as any).getDb();
      const { data: s } = await db.auth.getSession();
      const uid = s.session.user.id;
      // Every tracking row NOT belonging to me. Privacy D8: only active-job parties may see positions.
      const { data, error } = await db.from('v_service_job_tracking').select('request_id').limit(50);
      if (error) return { rows: -1, err: error.message.slice(0, 60) };
      const { data: mine } = await db.from('service_requests').select('id')
        .eq('client_auth_uid', uid);
      const mineIds = new Set((mine || []).map((r: any) => r.id));
      const foreign = (data || []).filter((r: any) => !mineIds.has(r.request_id)).length;
      return { rows: (data || []).length, foreign };
    });
    if (r.rows >= 0) {
      expect(r.foreign, `this session can read live positions for ${r.foreign} job(s) it is not a party `
        + 'to — provider locations leaking to strangers').toBe(0);
    }
  });
});
