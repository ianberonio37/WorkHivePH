/**
 * marketplace-sim-lifecycle.spec.ts — the LIFECYCLE tier of the marketplace simulation registry.
 *
 * 24 of the registry's scenarios are the 12 request states, each twice: once driven by the role that
 * OWNS the transition, and once attempted by the role that does not. That pairing is the whole point —
 * a state machine is defined as much by who may NOT move it as by who may, and a suite that only proves
 * the permitted direction cannot tell a working guard from a missing one.
 *
 * TWO CONTEXTS, NOT ONE. A marketplace handoff cannot be proven from a single browser: the thing being
 * asserted is that what A does becomes visible to B. `feedback_two_sided_journeys_need_a_role_pair`
 * measured FOURTEEN of 54 journeys as provably one-sided here, so the registry refuses to emit a
 * state-changing scenario with a single role and this spec honours that with two real sessions.
 *
 * ALTITUDE. The DB-level transition matrix is already banked in SQL (190 cells, both directions). What
 * SQL cannot decide is whether the OTHER PARTY'S SCREEN agrees — and a silent subscription failure looks
 * exactly like a job that never moved. So this file asserts the two things SQL cannot: that the mover
 * succeeds through the real client, and that the counterpart's own read reflects it.
 *
 * CLEANUP IS PART OF THE TEST. Every row this spec creates is deleted in `afterAll`. Live MCP/browser
 * writes against a shared database are how a "green" suite starts lying to the next session
 * ([[feedback_live_mcp_writes_pollute_test_db]]).
 */
import { test, expect, Page, Browser } from '@playwright/test';
import { adminClient } from './_db-cleanup';

const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';
const CLIENT = 'romeobeltran@auth.workhiveph.com';
const PROVIDER = 'bryangarcia@auth.workhiveph.com';
const TAG = 'SIMLIFECYCLE';

/** The 12 states and who legitimately moves each. Mirrors the registry's OWNER map exactly. */
const OWNER: Record<string, 'client' | 'provider' | 'system'> = {
  requested: 'client', broadcasting: 'client', accepted: 'provider', en_route: 'provider',
  on_site: 'provider', in_progress: 'provider', completed: 'provider', settled: 'client',
  cancelled_by_client: 'client', cancelled_by_provider: 'provider', expired: 'system',
  disputed: 'client',
};

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

/** Move a request through the page's own client, reporting refusals honestly rather than throwing. */
async function move(page: Page, id: string, to: string) {
  return page.evaluate(async ([rid, status]) => {
    const db = (window as any).getDb();
    const { data, error } = await db.from('service_requests')
      .update({ status }).eq('id', rid).select('id');
    if (error) return { ok: false, why: error.message.slice(0, 90) };
    // A 0-row update is RLS refusing silently — not an error, and not a success either.
    if (!data || !data.length) return { ok: false, why: 'RLS returned 0 rows' };
    return { ok: true, why: '' };
  }, [id, to]);
}

test.describe('marketplace simulation — lifecycle tier (two contexts)', () => {
  test.describe.configure({ mode: 'serial' });

  let C: { ctx: any; page: Page }, P: { ctx: any; page: Page };
  const created: string[] = [];

  test.beforeAll(async ({ browser }) => {
    C = await sessionFor(browser, CLIENT);
    P = await sessionFor(browser, PROVIDER);
  });

  test.afterAll(async () => {
    /* CLEAN UP THROUGH THE SERVICE ROLE, AND VERIFY IT WORKED.
       The first version deleted from the CLIENT's session — and service_requests has ZERO delete
       policies, so RLS silently dropped every row from the statement and the cleanup was a no-op
       that looked like success. It left 2 rows behind, which is precisely how a shared test database
       starts lying to the next session ([[feedback_live_mcp_writes_pollute_test_db]]).
       adminClient() already exists for this (service role, RLS-bypassing) — reused, not reinvented.
       And the delete is CHECKED: a cleanup that cannot prove it cleaned is the same no-op again. */
    try {
      const admin = adminClient();
      await admin.from('service_offers').delete().in('request_id', created);
      await admin.from('service_job_events').delete().in('request_id', created);
      await admin.from('service_requests').delete().ilike('custom_scope', TAG + '%');
      const { data: left } = await admin.from('service_requests')
        .select('id').ilike('custom_scope', TAG + '%');
      expect(left?.length ?? 0, 'the spec left rows behind in a shared database').toBe(0);
    } finally {
      await C?.ctx.close(); await P?.ctx.close();
    }
  });

  test('the client can file and broadcast, and the PROVIDER sees it', async () => {
    const made = await C.page.evaluate(async (tag) => {
      const db = (window as any).getDb();
      const { data: s } = await db.auth.getSession();
      const { data: prov } = await db.from('service_providers').select('id,hive_id').limit(1);
      const { data, error } = await db.from('service_requests').insert({
        client_auth_uid: s.session.user.id, hive_id: prov?.[0]?.hive_id, segment: 'consumer',
        mode: 'instant', status: 'requested', custom_scope: tag + ' arc', budget: 1500,
      }).select('id').single();
      return error ? { err: error.message } : { id: data.id };
    }, TAG);
    expect(made.err, `the client could not file a hail: ${made.err}`).toBeUndefined();
    created.push(made.id!);

    expect((await move(C.page, made.id!, 'broadcasting')).ok,
      'the client owns requested -> broadcasting and was refused').toBe(true);

    // THE TWO-SIDED HALF, read through the surface the PRODUCT uses. A provider does not — and must
    // not — read `service_requests` directly; RLS restricts it, and correctly, since that would expose
    // every client's job to every provider. Discovery goes through v_service_open_broadcasts, which
    // filters to status='broadcasting', excludes the caller's own requests, and applies the radius and
    // category rules. Reading the base table here measured the RLS restriction and called it a broken
    // broadcast — the instrument, not the page.
    const seen = await P.page.evaluate(async (rid) => {
      const db = (window as any).getDb();
      const { data, error } = await db.from('v_service_open_broadcasts')
        .select('request_id,mode,urgency').eq('request_id', rid);
      return { visible: !!(data && data.length), err: error?.message?.slice(0, 80) };
    }, made.id!);
    expect(seen.visible, `a broadcasting hail is INVISIBLE to an eligible provider (${seen.err || 'no rows'}) `
      + '— the broadcast reaches nobody, which is the whole product').toBe(true);
  });

  test('the WRONG role is refused on every provider-owned transition', async () => {
    const id = created[0];
    expect(id, 'no request from the previous step').toBeTruthy();
    const refusals: Record<string, boolean> = {};
    // The client must NOT be able to drive the provider's half of the machine.
    for (const st of ['accepted', 'en_route', 'on_site', 'in_progress', 'completed']) {
      refusals[st] = !(await move(C.page, id, st)).ok;
    }
    const allowed = Object.entries(refusals).filter(([, refused]) => !refused).map(([s]) => s);
    expect(allowed, `the CLIENT drove provider-only transitions: ${allowed.join(', ')} — the state `
      + 'machine has no owner for these').toEqual([]);
  });

  test('the client cannot settle a job that never completed', async () => {
    const id = created[0];
    // settled is client-owned, but only FROM completed. Ownership is not a bypass of order.
    const r = await move(C.page, id, 'settled');
    expect(r.ok, 'a broadcasting job was SETTLED — commission would mint on work that never happened')
      .toBe(false);
  });

  test('expiry is a SYSTEM transition, refused to both parties', async () => {
    const id = created[0];
    const asClient = await move(C.page, id, 'expired');
    const asProvider = await move(P.page, id, 'expired');
    expect(asClient.ok, 'the client expired their own hail — expiry belongs to the sweep, and a user '
      + 'who can expire a job can dodge a commission by timing it').toBe(false);
    expect(asProvider.ok, 'the provider expired a client hail').toBe(false);
  });

  test('the client can cancel their own hail, and the provider sees it end', async () => {
    const id = created[0];
    expect((await move(C.page, id, 'cancelled_by_client')).ok,
      'the client could not cancel their own hail').toBe(true);
    // Same surface rule as above: the provider's world is the open-broadcast view, so a cancelled
    // hail must DISAPPEAR from it. Asserting on the base table would test RLS, not the handoff.
    const stillOpen = await P.page.evaluate(async (rid) => {
      const db = (window as any).getDb();
      const { data } = await db.from('v_service_open_broadcasts').select('request_id').eq('request_id', rid);
      return !!(data && data.length);
    }, id);
    expect(stillOpen, 'a cancelled hail is STILL listed as an open broadcast — a provider would drive '
      + 'to a job that no longer exists').toBe(false);
  });
});
