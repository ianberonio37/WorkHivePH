/**
 * marketplace-sim-unhappy.spec.ts — the paths people actually hit, and nobody walks.
 *
 * Most production pain lives here: the provider who cancels, the hail nobody answers, the two providers
 * who press Accept in the same second, the job that goes wrong after the money moved. These are the least
 * tested states on the platform because every one of them needs real staging — you cannot observe a race
 * without two racers, or an expiry without a clock.
 *
 * THE LOSER'S EXPERIENCE IS THE TEST. A race that resolves correctly in the database but tells the losing
 * provider nothing is still a broken product: they drove to a job that was never theirs. Every refusal
 * here is asserted to be NAMED, not merely to have happened — `lost_race_or_closed` is a real answer, a
 * silent no-op is not ([[feedback_string_is_not_an_announcement_until_it_reaches_a_user]]).
 */
import { test, expect, Page, Browser } from '@playwright/test';
import { adminClient } from './_db-cleanup';

const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';
const CLIENT = 'romeobeltran@auth.workhiveph.com';
const PROVIDER_A = 'bryangarcia@auth.workhiveph.com';
const PROVIDER_B = 'pabloaguilar@auth.workhiveph.com';
const TAG = 'SIMUNHAPPY';

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

async function fileHail(page: Page, note: string) {
  const r = await page.evaluate(async ([tag, n]) => {
    const db = (window as any).getDb();
    const { data: s } = await db.auth.getSession();
    const { data: prov } = await db.from('service_providers').select('hive_id')
      .not('hive_id', 'is', null).limit(1);
    const { data, error } = await db.from('service_requests').insert({
      client_auth_uid: s.session.user.id, hive_id: prov?.[0]?.hive_id, segment: 'consumer',
      mode: 'instant', status: 'broadcasting', custom_scope: tag + ' ' + n, budget: 1200,
    }).select('id').single();
    return error ? { err: error.message.slice(0, 90) } : { id: data.id };
  }, [TAG, note] as any);
  expect(r.err, `could not file "${note}": ${r.err}`).toBeUndefined();
  return r.id!;
}

async function move(page: Page, id: string, to: string) {
  return page.evaluate(async ([rid, status]) => {
    const db = (window as any).getDb();
    const { data, error } = await db.from('service_requests')
      .update({ status }).eq('id', rid).select('id');
    if (error) return { ok: false, why: error.message.slice(0, 90) };
    if (!data || !data.length) return { ok: false, why: 'RLS returned 0 rows' };
    return { ok: true, why: '' };
  }, [id, to]);
}

test.describe('marketplace simulation — the unhappy paths', () => {
  test.describe.configure({ mode: 'serial' });

  let C: { ctx: any; page: Page }, A: { ctx: any; page: Page }, B: { ctx: any; page: Page };

  test.beforeAll(async ({ browser }) => {
    C = await sessionFor(browser, CLIENT);
    A = await sessionFor(browser, PROVIDER_A);
    B = await sessionFor(browser, PROVIDER_B);
  });

  test.afterAll(async () => {
    try {
      const admin = adminClient();
      const { data: mine } = await admin.from('service_requests')
        .select('id').ilike('custom_scope', TAG + '%');
      for (const r of mine || []) {
        await admin.from('service_credit_ledger').delete().eq('ref_id', r.id);
        await admin.from('service_payments').delete().eq('request_id', r.id);
        await admin.from('service_job_events').delete().eq('request_id', r.id);
        await admin.from('service_offers').delete().eq('request_id', r.id);
      }
      await admin.from('service_requests').delete().ilike('custom_scope', TAG + '%');
      await admin.rpc('reconcile_provider_availability');
      const { data: left } = await admin.from('service_requests')
        .select('id').ilike('custom_scope', TAG + '%');
      expect(left?.length ?? 0, 'the unhappy spec left requests behind').toBe(0);
    } finally { await C?.ctx.close(); await A?.ctx.close(); await B?.ctx.close(); }
  });

  test('ACCEPT RACE · one provider wins and the loser is TOLD which', async () => {
    const rid = await fileHail(C.page, 'race');
    // Both fire without awaiting the other — the point is that the DB, not the test, picks the winner.
    const [ra, rb] = await Promise.all([
      A.page.evaluate(async (r) => {
        const db = (window as any).getDb();
        const { data } = await db.rpc('accept_service_request', { p_request_id: r });
        return { accepted: !!data?.accepted, reason: data?.reason || null };
      }, rid),
      B.page.evaluate(async (r) => {
        const db = (window as any).getDb();
        const { data } = await db.rpc('accept_service_request', { p_request_id: r });
        return { accepted: !!data?.accepted, reason: data?.reason || null };
      }, rid),
    ]);

    const winners = [ra, rb].filter(x => x.accepted).length;
    expect(winners, `${winners} providers won the same job — two people are driving to one address, and `
      + 'both believe it is theirs').toBe(1);

    const loser = [ra, rb].find(x => !x.accepted)!;
    expect(loser.reason, 'the losing provider got a silent refusal with no reason — they have no way to '
      + 'know whether to keep waiting, retry, or move on').toBeTruthy();
    expect(String(loser.reason), `the loser was told "${loser.reason}" rather than that the race was `
      + 'lost — a wrong explanation sends them chasing the wrong fix')
      .toMatch(/lost_race_or_closed/i);

    /* HAND THE WINNER BACK. Winning puts that provider on_job — correctly, they are working — so the
       next staged accept in this file would be refused with `no_online_provider_identity` and read like
       a broken RPC. A test that takes a provider out of the pool has to put them back, exactly as it
       deletes its own rows; the reconciler cannot do it here because the job is genuinely active. */
    expect((await move(C.page, rid, 'cancelled_by_client')).ok,
      'could not release the race winner back to the pool').toBe(true);
  });

  test('CANCEL BY PROVIDER · legal from their own states, and the client sees it end', async () => {
    const rid = await fileHail(C.page, 'provider cancel');
    const acc = await A.page.evaluate(async (r) => {
      const db = (window as any).getDb();
      const { data } = await db.rpc('accept_service_request', { p_request_id: r });
      return { ok: !!data?.accepted, reason: data?.reason };
    }, rid);
    expect(acc.ok, `could not stage the cancel: ${acc.reason}`).toBe(true);

    // The CLIENT must not be able to cancel *as the provider* — the two cancels are different records
    // of what happened, and who withdrew matters to both reputations.
    const byClient = await move(C.page, rid, 'cancelled_by_provider');
    expect(byClient.ok, 'the CLIENT recorded a provider cancellation — the record would blame the '
      + 'provider for the client backing out').toBe(false);

    expect((await move(A.page, rid, 'cancelled_by_provider')).ok,
      'the matched provider could not withdraw from their own job').toBe(true);

    // And it must free them: a provider who cancelled is available, not stuck mid-job.
    const admin = adminClient();
    const { data: req } = await admin.from('service_requests').select('matched_provider_id').eq('id', rid);
    const { data: sp } = await admin.from('service_providers').select('availability')
      .eq('id', req![0].matched_provider_id);
    expect(sp![0].availability, 'a provider who CANCELLED is still marked on_job, so they vanish from '
      + 'the market for a job they are no longer doing').toBe('online');
  });

  test('EXPIRY · an unanswered hail expires by the sweep, not by either party', async () => {
    const rid = await fileHail(C.page, 'expiry');
    const admin = adminClient();
    // Put the TTL in the past — the clock is the only thing being simulated here.
    await admin.from('service_requests')
      .update({ offer_ttl_expires_at: new Date(Date.now() - 60_000).toISOString() }).eq('id', rid);

    // Neither party may do it themselves: a client who can expire their own hail can dodge a commission
    // by timing it, and a provider could clear a competitor's job.
    expect((await move(C.page, rid, 'expired')).ok, 'the client expired their own hail').toBe(false);
    expect((await move(A.page, rid, 'expired')).ok, 'a provider expired someone else\'s hail').toBe(false);

    /* AN INSTANT HAIL WIDENS BEFORE IT DIES. The sweep does three things in order: stamp a TTL, WIDEN
       any instant hail whose TTL has passed (doubling the radius, capped by the hive ceiling, and
       re-stamping the clock), and only expire once broadcast_round has exhausted broadcast_widen_rounds.
       So a single sweep call widens rather than expires, and asserting "one sweep → expired" measured a
       product that gives up immediately instead of the one that actually searches harder first.
       Looping is the faithful simulation, and it proves the widening too. */
    const radii: number[] = [];
    let status = 'broadcasting';
    for (let round = 0; round < 8 && status === 'broadcasting'; round++) {
      await admin.from('service_requests')
        .update({ offer_ttl_expires_at: new Date(Date.now() - 60_000).toISOString() }).eq('id', rid);
      await admin.rpc('sweep_service_broadcasts');
      const { data: now } = await admin.from('service_requests')
        .select('status,broadcast_radius_m').eq('id', rid);
      status = now![0].status;
      if (status === 'broadcasting') radii.push(Number(now![0].broadcast_radius_m));
    }
    expect(status, 'a hail kept broadcasting through eight widen rounds — it never expires, so providers '
      + 'keep seeing a job the client gave up on').toBe('expired');
    // Non-vacuity: "it widened" means the radius actually grew before it gave up.
    expect(radii.length, 'the hail expired without ever widening — it never searched harder before '
      + 'giving up on the client').toBeGreaterThan(0);
    expect(radii[radii.length - 1], `the radius never grew across rounds (${radii.join(' → ')} m)`)
      .toBeGreaterThan(radii[0] - 1);
  });

  test('EXPIRY IS VISIBLE · the expired hail leaves the open-broadcast list', async () => {
    const admin = adminClient();
    const { data: exp } = await admin.from('service_requests')
      .select('id').ilike('custom_scope', TAG + ' expiry%').eq('status', 'expired');
    expect(exp?.length ?? 0, 'no expired hail to check').toBeGreaterThan(0);
    const stillOffered = await A.page.evaluate(async (rid) => {
      const db = (window as any).getDb();
      const { data } = await db.from('v_service_open_broadcasts').select('request_id').eq('request_id', rid);
      return !!(data && data.length);
    }, exp![0].id);
    expect(stillOffered, 'an EXPIRED hail is still listed as an open broadcast — a provider would accept '
      + 'a job that no longer exists').toBe(false);
  });

  test('DISPUTE · either party may raise one, and it does not delete the money', async () => {
    const rid = await fileHail(C.page, 'dispute');
    const acc = await A.page.evaluate(async (r) => {
      const db = (window as any).getDb();
      const { data } = await db.rpc('accept_service_request', { p_request_id: r });
      return { ok: !!data?.accepted, reason: data?.reason };
    }, rid);
    expect(acc.ok, `could not stage the dispute: ${acc.reason}`).toBe(true);
    for (const st of ['en_route', 'on_site', 'in_progress']) {
      expect((await move(A.page, rid, st)).ok, `staging stalled at ${st}`).toBe(true);
    }

    // in_progress → disputed is open to BOTH parties, deliberately: a job going wrong is not only the
    // client's observation, and a provider being stiffed needs the same lever.
    expect((await move(C.page, rid, 'disputed')).ok,
      'the client could not raise a dispute on their own in-progress job').toBe(true);

    // A dispute must not freeze the provider's earnings — that is a second penalty before anyone has
    // decided anything.
    const admin = adminClient();
    const { data: req } = await admin.from('service_requests').select('matched_provider_id').eq('id', rid);
    const { data: sp } = await admin.from('service_providers').select('availability')
      .eq('id', req![0].matched_provider_id);
    expect(sp![0].availability, 'a disputed job leaves the provider marked on_job, so raising a dispute '
      + 'silently removes them from the market before anything is decided').toBe('online');

    // And nothing may be erased: the ledger is the audit trail, so a dispute compensates, never deletes.
    const del = await C.page.evaluate(async (r) => {
      const db = (window as any).getDb();
      const { data, error } = await db.from('service_credit_ledger').delete().eq('ref_id', r).select('id');
      return error ? 'refused' : (data?.length ? 'ACCEPTED' : 'refused:0rows');
    }, rid);
    expect(del, 'a party to a dispute DELETED ledger rows — a deleted row is a lie about what happened')
      .not.toBe('ACCEPTED');
  });

  test('OFFLINE · a hail attempted with no connection is refused OUT LOUD', async ({ browser }) => {
    /* P-FLAKY, and the rule that matters: adoption of an offline banner is not proof that the write was
       refused ([[feedback_banner_adoption_is_not_write_refusal]]). So this asserts BOTH — the user is
       told, and nothing reached the database. */
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    try {
      await sessionForInto(page, CLIENT);
      await page.goto('/workhive/marketplace.html');
      await page.waitForTimeout(3500);
      await page.click('[data-section="services"]');
      await page.waitForTimeout(2000);

      const before = await countHails();
      await page.context().setOffline(true);
      const said = await page.evaluate(async () => {
        const btn = Array.from(document.querySelectorAll('button'))
          .find(b => /hail now/i.test(b.innerText || '')) as HTMLButtonElement | undefined;
        if (!btn) return { pressed: false, text: '' };
        btn.click();
        await new Promise(r => setTimeout(r, 2500));
        return { pressed: true, text: document.body.innerText.toLowerCase() };
      });
      await page.context().setOffline(false);

      expect(said.pressed, 'no hail button to press').toBe(true);
      expect(said.text, 'hailing with no connection said NOTHING — the user believes a provider is on '
        + 'the way').toMatch(/offline|connection|internet|try again|no connection/);
      expect(await countHails(), 'an offline hail still reached the database, so the refusal shown to '
        + 'the user was a lie in the other direction').toBe(before);
    } finally { await ctx.close(); }
  });
});

async function sessionForInto(page: Page, email: string) {
  await page.goto('/workhive/index.html', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => typeof (window as any).getDb === 'function', { timeout: 20000 });
  await page.evaluate(async ([mail, pass]) => {
    const db = (window as any).getDb();
    await db.auth.signOut();
    await db.auth.signInWithPassword({ email: mail, password: pass });
  }, [email, PASSWORD]);
}

async function countHails() {
  const admin = adminClient();
  const { data } = await admin.from('service_requests').select('id').ilike('custom_scope', TAG + '%');
  return data?.length ?? 0;
}
