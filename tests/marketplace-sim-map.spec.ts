/**
 * marketplace-sim-map.spec.ts — the live tracking map, against a job that is genuinely en route.
 *
 * Ian named this leg specifically, and it was the registry's thinnest family. The existing map cells all
 * test the PIN (does MapLibre stay off the hail path, does the pin set a location) — none of them had
 * ever tracked a moving provider, because doing so needs a job in en_route/on_site/in_progress with a
 * matched provider AND a live position, which no fragment test was willing to stage.
 *
 * WHAT ONLY A LIVE MAP CAN ANSWER. v_service_job_tracking is queryable in SQL and proves who may READ a
 * position. It cannot tell you whether a marker painted, whether the map recentres as the provider
 * moves, or whether tracking ENDS honestly when the job does — a poller that keeps saying "live" over a
 * finished job is worse than one that stops, because the client keeps waiting on a van that is not
 * coming. Those are rendered truths, and the DB cannot see a marker that never appeared.
 *
 * PRIVACY IS THE POINT OF THE VIEW (D8): only parties to an ACTIVE job may see a provider's position.
 * That is asserted here from a real third session, not by reading the policy text.
 */
import { test, expect, Page, Browser } from '@playwright/test';
import { adminClient } from './_db-cleanup';

const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';
const CLIENT = 'romeobeltran@auth.workhiveph.com';
const PROVIDER = 'bryangarcia@auth.workhiveph.com';
/* A GENUINE outsider, and picking one took a false positive to notice. v_service_job_tracking admits
   three groups: the client, ACTIVE MEMBERS OF THE REQUEST'S HIVE, and the matched provider — hive
   colleagues see their hive's jobs by design. The first draft used isidrosuarez, who is an active member
   of Manila Electronics Assembly, exactly like the client — so the "stranger" was a colleague, the read
   succeeded correctly, and the test reported a live-location leak that did not exist. emmavelasquez is
   in Lucena Pharmaceutical only, owns no matched provider profile here, and the test now VERIFIES that
   premise before drawing any conclusion ([[feedback_check_the_premise_before_building_the_pattern]]). */
const STRANGER = 'emmavelasquez@auth.workhiveph.com';
const TAG = 'SIMMAP';

// Manila-ish; the site and the provider are ~1.5km apart so a recentre is observable.
const SITE: [number, number] = [121.0244, 14.5547];
const PROV_AT: [number, number] = [121.0380, 14.5610];

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

test.describe('marketplace simulation — the live tracking map', () => {
  test.describe.configure({ mode: 'serial' });

  let C: { ctx: any; page: Page }, P: { ctx: any; page: Page };
  let REQ = '', PROV = '';

  test.beforeAll(async ({ browser }) => {
    C = await sessionFor(browser, CLIENT);
    P = await sessionFor(browser, PROVIDER);

    // File a hail WITH a location, so the site marker has something to paint.
    const made = await C.page.evaluate(async ([tag, lng, lat]) => {
      const db = (window as any).getDb();
      const { data: s } = await db.auth.getSession();
      /* THE CLIENT'S OWN HIVE, not whichever provider limit(1) happens to return. The tracking view
         admits active members of the REQUEST'S hive, so the hive decides who counts as a stranger — and
         with an arbitrary hive the D8 cell later flipped from passing to failing on nothing but planner
         order, reporting a leak that was really a colleague. Pin it to the client
         ([[feedback_resolving_live_is_not_enough_be_deterministic]]). */
      const { data: mine } = await db.from('hive_members').select('hive_id')
        .eq('auth_uid', s.session.user.id).eq('status', 'active')
        .order('hive_id', { ascending: true }).limit(1);
      const { data, error } = await db.from('service_requests').insert({
        client_auth_uid: s.session.user.id, hive_id: mine?.[0]?.hive_id, segment: 'consumer',
        mode: 'instant', status: 'broadcasting', custom_scope: tag + ' tracked job', budget: 1500,
        location: `SRID=4326;POINT(${lng} ${lat})`, address: 'SIMMAP test site',
      }).select('id').single();
      return error ? { err: error.message.slice(0, 110) } : { id: data.id };
    }, [TAG, SITE[0], SITE[1]] as any);
    expect(made.err, `could not file a located hail: ${made.err}`).toBeUndefined();
    REQ = made.id!;

    const acc = await P.page.evaluate(async (r) => {
      const db = (window as any).getDb();
      const { data } = await db.rpc('accept_service_request', { p_request_id: r });
      return { ok: !!data?.accepted, reason: data?.reason, pid: data?.provider_id };
    }, REQ);
    expect(acc.ok, `provider could not accept the located job: ${acc.reason}`).toBe(true);
    PROV = acc.pid!;

    // en_route is the first state the tracking view admits.
    const mv = await P.page.evaluate(async (r) => {
      const db = (window as any).getDb();
      const { error, data } = await db.from('service_requests').update({ status: 'en_route' })
        .eq('id', r).select('id');
      return { ok: !error && !!data?.length, why: error?.message?.slice(0, 80) };
    }, REQ);
    expect(mv.ok, `could not send the job en route: ${mv.why}`).toBe(true);
  });

  test.afterAll(async () => {
    try {
      const admin = adminClient();
      if (REQ) {
        await admin.from('service_job_events').delete().eq('request_id', REQ);
        await admin.from('service_offers').delete().eq('request_id', REQ);
      }
      await admin.from('service_requests').delete().ilike('custom_scope', TAG + '%');
      // The provider's live position is fixture state this spec wrote — clear it, or the next run
      // inherits a provider standing in Manila.
      if (PROV) await admin.from('service_providers').update({ live_location: null }).eq('id', PROV);
      await admin.rpc('reconcile_provider_availability');
      const { data: left } = await admin.from('service_requests')
        .select('id').ilike('custom_scope', TAG + '%');
      expect(left?.length ?? 0, 'the map spec left requests behind').toBe(0);
    } finally { await C?.ctx.close(); await P?.ctx.close(); }
  });

  test('the provider can share their live position, and only for themselves', async () => {
    const mine = await P.page.evaluate(async ([pid, lng, lat]) => {
      const db = (window as any).getDb();
      const { data, error } = await db.from('service_providers')
        .update({ live_location: `SRID=4326;POINT(${lng} ${lat})` }).eq('id', pid).select('id');
      return error ? 'refused:' + error.message.slice(0, 60) : (data?.length ? 'ok' : 'refused:0rows');
    }, [PROV, PROV_AT[0], PROV_AT[1]] as any);
    expect(mine, `the provider could not publish their own position: ${mine}`).toBe('ok');
  });

  test('the client sees the site AND the provider on a real map', async () => {
    await C.page.goto('/workhive/marketplace.html');
    await C.page.waitForTimeout(3500);
    await C.page.click('[data-section="services"]');
    await C.page.waitForTimeout(3000);

    // MapLibre must still be absent until Track is pressed — the 800KB rule, re-asserted here because
    // this is the page where it is easiest to break by accident.
    const before = await C.page.evaluate(() => typeof (window as any).maplibregl !== 'undefined');
    expect(before, 'MapLibre loaded before anyone pressed Track').toBe(false);

    await C.page.evaluate((rid) => (window as any).svcTrack(rid), REQ);
    await C.page.waitForTimeout(7000);

    const r = await C.page.evaluate((rid) => {
      // One map container per tracked request, so the id is built per job at runtime and no static id
      // exists for the scanner to match.
      // pw-selector-allow: runtime-composed id
      const holder = document.getElementById('svc-map-' + rid);
      return {
        lib: typeof (window as any).maplibregl !== 'undefined',
        canvas: !!holder?.querySelector('canvas'),
        note: (document.getElementById('svc-map-' + rid + '-note')?.innerText || '').trim(),
        aria: holder?.getAttribute('aria-label') || '',
      };
    }, REQ);
    expect(r.lib, 'pressing Track did not load the map library').toBe(true);
    expect(r.canvas, 'the tracking map rendered no canvas — the client sees an empty box where the '
      + 'provider should be').toBe(true);
    expect(r.note.toLowerCase(), 'the map never confirms it is showing a live position')
      .toContain('position');
    // A map is an image to a screen reader; without a label it is nothing at all.
    expect(r.aria.toLowerCase(), 'the tracking map carries no description for a screen reader')
      .toMatch(/provider|map/);
  });

  test('the tracking data is the site and the provider, not one or the other', async () => {
    const t = await C.page.evaluate(async (rid) => {
      const db = (window as any).getDb();
      const { data } = await db.from('v_service_job_tracking').select('*').eq('request_id', rid);
      return data?.[0] || null;
    }, REQ);
    expect(t, 'the client cannot read tracking for their OWN active job').toBeTruthy();
    expect(t.request_lat, 'the site has no coordinates, so the map cannot show where the job is')
      .not.toBeNull();
    expect(t.live_lat, 'the provider position never reached the tracking view').not.toBeNull();
    // Non-vacuity: the two points must be genuinely different, or "the map shows both" is unfalsifiable.
    expect(Math.abs(Number(t.live_lng) - Number(t.request_lng)), 'the provider and the site are at the '
      + 'same point, so this proves nothing about showing both').toBeGreaterThan(0.001);
  });

  test('a stranger cannot see where the provider is (D8)', async ({ browser }) => {
    const S = await sessionFor(browser, STRANGER);
    try {
      // VERIFY THE PREMISE FIRST. If this account turns out to share the request's hive, they are a
      // legitimate reader and any conclusion drawn from their access is meaningless.
      const admin = adminClient();
      const { data: req } = await admin.from('service_requests').select('hive_id').eq('id', REQ);
      const { data: uid } = await admin.auth.admin.listUsers();
      const strangerId = uid.users.find((u: any) => u.email === STRANGER)?.id;
      const { data: mem } = await admin.from('hive_members').select('hive_id')
        .eq('auth_uid', strangerId).eq('status', 'active');
      const shares = (mem || []).some((m: any) => m.hive_id === req![0].hive_id);
      expect(shares, `${STRANGER} is an active member of this request's hive, so they are an INTENDED `
        + 'reader — this test is mis-staged and proves nothing about leakage').toBe(false);

      const seen = await S.page.evaluate(async (rid) => {
        const db = (window as any).getDb();
        const { data, error } = await db.from('v_service_job_tracking')
          .select('request_id,live_lat,live_lng').eq('request_id', rid);
        return { rows: data?.length ?? 0, err: error?.message?.slice(0, 60) };
      }, REQ);
      expect(seen.rows, 'someone with no part in this job can read the provider\'s live position — a '
        + 'person\'s real-time location leaking to a stranger').toBe(0);

      // And the other direction: nobody may MOVE someone else's dot. A position a third party can write
      // is a position nobody can trust, and it would let an attacker fake proximity to win jobs.
      const wrote = await S.page.evaluate(async ([pid]) => {
        const db = (window as any).getDb();
        const { data, error } = await db.from('service_providers')
          .update({ live_location: 'SRID=4326;POINT(120.9 14.4)' }).eq('id', pid).select('id');
        return error ? 'refused' : (data?.length ? 'ACCEPTED' : 'refused:0rows');
      }, [PROV] as any);
      expect(wrote, 'a stranger MOVED another provider\'s live position — proximity, and therefore who '
        + 'gets matched, becomes forgeable').not.toBe('ACCEPTED');
    } finally { await S.ctx.close(); }
  });

  test('tracking STOPS honestly when the job ends', async () => {
    // Take the job out of the active window while the client is still watching.
    await C.page.evaluate(async (rid) => {
      const db = (window as any).getDb();
      await db.from('service_requests').update({ status: 'cancelled_by_client' }).eq('id', rid);
    }, REQ);

    // Drive the poller's next tick rather than waiting out its 10s interval.
    await C.page.evaluate((rid) => (window as any).svcTrack(rid), REQ);   // toggle off
    await C.page.evaluate((rid) => (window as any).svcTrack(rid), REQ);   // and on again → fresh tick
    await C.page.waitForTimeout(5000);

    const note = await C.page.evaluate((rid) =>
      (document.getElementById('svc-map-' + rid + '-note')?.innerText || '').toLowerCase(), REQ);
    expect(note, 'a cancelled job still advertises a LIVE provider position — the client keeps waiting '
      + 'for someone who is not coming').not.toMatch(/live:/);
    expect(note, 'tracking went silent without saying why, which reads as a broken map rather than a '
      + 'finished job').toMatch(/ended|no longer active/);
  });

  test('the map failing to load never strands the hail', async ({ browser }) => {
    // The PH baseline is a slow, lossy connection: the map is the heaviest thing on the page and the
    // first to fail. Failing must degrade to the typed address, never block the send.
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    try {
      await page.route('**/maplibre-gl.js', route => route.abort());
      await page.goto('/workhive/index.html', { waitUntil: 'domcontentloaded' });
      await page.waitForFunction(() => typeof (window as any).getDb === 'function', { timeout: 20000 });
      await page.evaluate(async ([mail, pass]) => {
        const db = (window as any).getDb();
        await db.auth.signInWithPassword({ email: mail, password: pass });
      }, [CLIENT, PASSWORD]);
      await page.goto('/workhive/marketplace.html');
      await page.waitForTimeout(3500);
      await page.click('[data-section="services"]');
      await page.waitForTimeout(2000);

      await page.click('#svc-pin-btn');
      await page.waitForTimeout(5000);
      const r = await page.evaluate(() => {
        const slot = document.getElementById('svc-pin-slot');
        const btn = Array.from(document.querySelectorAll('button'))
          .find(b => /hail now/i.test(b.innerText || '')) as HTMLButtonElement | undefined;
        return { text: (slot?.innerText || '').toLowerCase(), hailDisabled: btn ? btn.disabled : true };
      });
      expect(r.text, 'the map failed and said nothing — the user is left looking at a blank box with no '
        + 'idea whether to wait').not.toBe('');
      expect(r.text, 'the failure never mentions the address still working, so the user assumes the '
        + 'whole hail is broken').toMatch(/address|offline|could not load|couldn't load/);
      expect(r.hailDisabled, 'a failed MAP left the HAIL button disabled — the heaviest optional feature '
        + 'on the page took the whole flow down with it').toBe(false);
    } finally { await ctx.close(); }
  });
});
