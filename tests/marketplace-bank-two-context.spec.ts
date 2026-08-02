/**
 * marketplace-bank-two-context.spec.ts — the test bank's TWO-CONTEXT harness.
 *
 * Every existing spec in this repo drives ONE signed-in identity. That is why the marketplace's
 * two-sided journeys were never end-to-end: J29 (live map) was walked by P-client-supervisor and
 * P-client-worker — two WATCHERS, zero PUBLISHERS — and still satisfied the arc's ">=2 personas"
 * coverage rule, because the rule counted personas instead of naming the SIDES
 * ([[feedback_two_sided_journeys_need_a_role_pair]]). A handoff between two parties cannot be proven
 * from one browser: the whole point is that what A does appears to B.
 *
 * So this file exists to hold role-PAIR cells. Two independent browser contexts, two real Supabase
 * Auth sessions, one shared row of truth in between.
 *
 * ALTITUDE, deliberately. The data path is already banked in SQL — the provider publishes
 * live_location under their own JWT, the client reads the new position through
 * v_service_job_tracking, a stranger reads 0 rows (tests/bank_probes/
 * TB-S6-realtime-map-datapath-publisher-x-watcher.sql). What SQL cannot prove is that the client's
 * screen repaints, and a silent subscription failure looks exactly like a provider who has not moved.
 * That is the only thing this spec asserts, so it stays small — the pyramid's UI layer should be.
 */
import { test, expect, Page, Browser } from '@playwright/test';
import { adminClient } from './_db-cleanup';

const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';

// The client's site. The provider starts here and moves ~1.2km east, which is far enough to be an
// unambiguous change and near enough to stay inside a plausible job radius.
const SITE: [number, number] = [120.5960, 16.4023];
const FROM: [number, number] = [120.6000, 16.4100];
const TO:   [number, number] = [120.6120, 16.4180];

async function signInAs(page: Page, username: string) {
  await page.goto('/workhive/index.html?signin=1', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#signin-modal:not(.hidden)', { timeout: 12000 });
  await page.waitForSelector('#si-username', { state: 'visible', timeout: 5000 });
  await page.waitForTimeout(250);
  await page.click('#si-username'); await page.fill('#si-username', username);
  await page.click('#si-password'); await page.fill('#si-password', PASSWORD);
  await page.click('#si-btn');
  await page.waitForFunction(
    () => localStorage.getItem('wh_last_worker') ||
      (document.getElementById('si-error') &&
        !document.getElementById('si-error')!.classList.contains('hidden')),
    { timeout: 20000 });
  const ok = await page.evaluate(() => localStorage.getItem('wh_last_worker'));
  if (!ok) {
    const err = await page.evaluate(() =>
      (document.getElementById('si-error') as HTMLElement | null)?.textContent || 'unknown');
    throw new Error(`sign-in failed for ${username}: ${(err || '').trim()}`);
  }
}


/** A provider login owning EXACTLY ONE profile, plus a client who is not them.
 *
 * Both `accept_service_request` and `submit_service_quote` resolve WHICH provider profile acts, via
 * my_service_provider_ids() ordered by `verified desc, created_at` — and one seeded login owns TWO
 * profiles. So a test that picks "the first provider bound to a login" and then asserts on that exact
 * id passes or fails on which profile the RPC happened to choose. SJ-J01 passed that way once and
 * failed the next run with nothing about the product changed.
 *
 * Removing the ambiguity beats guessing: one profile means the RPC has one choice
 * ([[feedback_resolving_live_is_not_enough_be_deterministic]]).
 */
async function soleProfileProvider(db: any) {
  const { data: provs } = await db.from('service_providers')
    .select('id, auth_uid, display_name, availability, categories').not('auth_uid', 'is', null);
  const { data: workers } = await db.from('worker_profiles')
    .select('username, display_name, auth_uid').not('auth_uid', 'is', null);
  const byUid = new Map((workers || []).map((w: any) => [w.auth_uid, w]));
  const perLogin = new Map<string, any[]>();
  for (const pr of (provs || [])) {
    if (!byUid.has(pr.auth_uid)) continue;
    const u = byUid.get(pr.auth_uid)!.username as string;
    perLogin.set(u, [...(perLogin.get(u) || []), pr]);
  }
  const sole = [...perLogin.entries()].sort(([a], [b]) => a.localeCompare(b))
    .find(([, list]) => list.length === 1);
  const providerUser = sole ? sole[0] : '';
  const provider = sole ? sole[1][0] : null;
  const client = (workers || []).find((w: any) => w.username && w.username !== providerUser);
  return { provider, providerUser, ownIds: provider ? [provider.id] : [], client };
}

test.describe('marketplace test bank — role-pair cells (two browser contexts)', () => {
  test.describe.configure({ mode: 'serial' });

  let requestId = '';
  let providerId = '';
  let cancelRequestId = '';
  let advanceRequestId = '';
  let hailRequestId = '';
  let presenceProviderId = '';
  let presenceWasAvailability = '';
  let answerRequestId = '';
  let provCancelRequestId = '';
  let quoteRequestId = '';

  test.afterAll(async () => {
    // The probe row is minted by this spec and swept by it. Residue is not evidence, and a leftover
    // en_route job would follow real seeded identities around the UI.
    const db = adminClient();
    // Every probe row this file mints is swept here, including the cancel-UI one — a leftover
    // en_route job would follow real seeded identities around the UI.
    for (const id of [requestId, cancelRequestId, advanceRequestId, hailRequestId,
                      answerRequestId, provCancelRequestId, quoteRequestId].filter(Boolean)) {
      await db.from('service_requests').delete().eq('id', id);
    }
    // ...and the notices those cancellations legitimately produced. They are real product rows, which
    // is exactly why they must be swept: left behind, they drift the SQL cell that counts them.
    // Every probe SCOPE this file uses, not just the cancel one — the waiting-provider hail also
    // produces a legitimate broadcast push, and a sweep that names a single body leaves the rest
    // behind (8 were found sitting in the outbox before this was widened).
    // The dayplan entry the accept legitimately created is swept too — a real product row, which is
    // exactly why it cannot be left behind on a seeded provider's calendar.
    await db.from('schedule_items').delete().ilike('title', '%TB responder-answer probe%');
    for (const scope of ['TB cancel-ui probe', 'TB advance-ui probe', 'TB waiting-provider hail probe',
                         'TB two-context probe', 'TB responder-answer probe', 'TB prov-cancel probe', 'TB quoter-ui probe']) {
      await db.from('service_outbox').delete()
        .eq('consumer', 'notify-push').like('payload->>body', `%${scope}%`);
    }
    // No early return here. That guard was a leftover from when this file held ONE test, and it made
    // every later cleanup conditional on the FIRST test having run — so a `--grep` at a single cell
    // left another cell's state behind. Each restore guards only on its own id.
    if (providerId) {
      await db.from('service_providers').update({ live_location: null }).eq('id', providerId);
    }
    if (presenceProviderId && presenceWasAvailability) {
      await db.from('service_providers')
        .update({ availability: presenceWasAvailability }).eq('id', presenceProviderId);
    }
  });

  test('TB-S6-realtime-map-ui-publisher-x-watcher: the watcher\'s marker repaints when the publisher moves',
    async ({ browser }: { browser: Browser }) => {
      test.slow();   // two sign-ins plus the tracker's 10s poll cycle
      const db = adminClient();

      // ── the PUBLISHER side: a provider profile whose auth_uid has a real login ────────────────
      // worker_profiles.auth_uid is the join, NOT auth.users: the auth schema is not exposed through
      // PostgREST, so `db.schema('auth').from('users')` comes back empty even for the service role.
      // The first cut did exactly that, found no provider, and SKIPPED — a green run that asserted
      // nothing. A skip is not a pass, so these guards FAIL loudly instead.
      const { provider, providerUser, ownIds, client } = await soleProfileProvider(db);
      expect(provider, 'need a login owning exactly one provider profile').toBeTruthy();
      expect(client, 'need a client identity').toBeTruthy();
      const clientUser = client!.username as string;
      const clientUid = client!.auth_uid as string;
      // Module-level, so afterAll can clear this provider's live_location. Its assignment lived in the
      // identity block that the shared resolver replaced.
      providerId = provider!.id;

      // The job is planted with the service role in en_route — the first state the tracker exposes.
      // Walking the whole chain here would test the walk, not the repaint.
      const ins = await db.from('service_requests').insert({
        client_auth_uid: clientUid,
        client_worker_name: client!.display_name || clientUser,
        mode: 'instant',
        custom_scope: 'TB two-context probe',
        location: `POINT(${SITE[0]} ${SITE[1]})`,
        status: 'en_route',
        matched_provider_id: providerId,
      }).select('id').single();
      expect(ins.error, `could not plant the probe job: ${ins.error?.message}`).toBeNull();
      requestId = ins.data!.id;
      await db.from('service_providers')
        .update({ live_location: `POINT(${FROM[0]} ${FROM[1]})` }).eq('id', providerId);

      // ── CONTEXT A — the watcher opens the tracker ────────────────────────────────────────────
      const ctxA = await browser.newContext();
      const A = await ctxA.newPage();
      A.on('pageerror', e => console.log(`[watcher pageerror] ${e.message}`));
      await signInAs(A, clientUser);

      // Record every coordinate the render path is handed. The DOM marker is a MapLibre overlay
      // whose transform depends on camera state, so comparing transforms would conflate "the map
      // panned" with "the provider moved". Wrapping the module the page actually calls records the
      // POSITION, which is the claim under test — and it still fails loudly if the tracker stops
      // ticking, because nothing gets recorded at all.
      await A.addInitScript(() => {
        (window as any).__TB = { positions: [], markers: 0 };
        const install = () => {
          const m = (window as any).whMap;
          if (!m || m.__tbWrapped) return !!m;
          const origMarker = m.marker, origFollow = m.follow;
          m.marker = function (map: any, lngLat: any, kind: any, label: any) {
            if (kind === 'provider' && lngLat) {
              (window as any).__TB.markers++;
              (window as any).__TB.positions.push([lngLat[0], lngLat[1]]);
            }
            return origMarker.apply(this, arguments as any);
          };
          m.follow = function (map: any, mk: any, lngLat: any, other: any) {
            if (lngLat) (window as any).__TB.positions.push([lngLat[0], lngLat[1]]);
            return origFollow.apply(this, arguments as any);
          };
          m.__tbWrapped = true;
          return true;
        };
        // wh-map.js is lazy-loaded on the first Track press, so poll until it appears.
        if (!install()) {
          const iv = setInterval(() => { if (install()) clearInterval(iv); }, 100);
        }
      });

      // Driven through the real affordance, not by calling svcTrack() directly. svcTrack bails out
      // when `#svc-track-<id>` is absent, and that slot only exists once the job CARD has rendered —
      // so a direct call on a freshly-loaded page silently no-ops and every later assertion measures
      // a tracker that was never started.
      await A.goto('/workhive/marketplace.html', { waitUntil: 'domcontentloaded' });
      await A.locator('.section-tab[data-section="services"]').click({ timeout: 15000 });
      // Scoped to THIS request, not `.first()`. The client may hold several active jobs — including
      // one planted by a concurrent run of this very spec, which is exactly what happened when the
      // full suite executed the journey gate while it was also being driven by hand: both runs
      // planted an en_route job for the same provider, `.first()` picked the other one, and the gate
      // reported a broken live map. Targeting the button by its own request id is an implementation
      // detail, and it is the right trade: a role+name locator that can address the wrong row is not
      // testing user-visible behaviour, it is testing whichever row sorted first.
      const trackBtn = A.locator(`button[onclick*="${requestId}"]`).first();
      await expect(trackBtn, 'the client\'s active job never rendered a "Track provider" control — ' +
        'the watcher has no way into the map at all').toBeVisible({ timeout: 20000 });
      await trackBtn.click();

      await expect.poll(async () =>
        A.evaluate(() => (window as any).__TB?.positions?.length || 0), {
        timeout: 25000, intervals: [1000],
        message: 'the tracker never handed a provider position to the map — the watcher side is ' +
          'not rendering at all, so a "no movement" result below would be meaningless',
      }).toBeGreaterThan(0);
      const first = await A.evaluate(() => (window as any).__TB.positions[0]);
      expect(Math.abs(first[1] - FROM[1]), 'the tracker opened on the wrong position').toBeLessThan(0.002);

      // ── CONTEXT B — the publisher moves, from a second real session ──────────────────────────
      // TEETH: `WH_TB_FREEZE=1` parks the publisher at its ORIGINAL position. The watcher assertion
      // must then FAIL. Without this switch there is no way to tell a tracker that genuinely
      // repaints from one that reports the same coordinate forever — both look green.
      const frozen = process.env.WH_TB_FREEZE === '1';
      const target = frozen ? FROM : TO;
      const ctxB = await browser.newContext({
        permissions: ['geolocation'],
        geolocation: { longitude: target[0], latitude: target[1] },
      });
      const B = await ctxB.newPage();
      await signInAs(B, providerUser);
      await B.goto('/workhive/marketplace-seller.html?tab=services', { waitUntil: 'domcontentloaded' });
      // The seller page starts watchPosition by itself once it loads an ACTIVE job (line ~1074).
      // Give it the chance; if the page's own publisher does not fire we fall back to the exact
      // statement its callback runs, from the SAME signed-in session — never from the admin client,
      // which would prove the client can render a position no real provider could have written.
      await B.waitForTimeout(10000);
      let published = await B.evaluate(async (pid) => {
        const db = (window as any).db;
        if (!db) return 'no-db';
        const { data } = await db.from('v_service_job_tracking').select('live_lng, live_lat').limit(5);
        return JSON.stringify(data || []);
      }, providerId);
      const movedByPage = published.includes(String(target[0]).slice(0, 7));
      if (!movedByPage) {
        const res = await B.evaluate(async ([pid, lng, lat]: any[]) => {
          const db = (window as any).db;
          const { error } = await db.from('service_providers')
            .update({ live_location: `POINT(${lng} ${lat})`, updated_at: new Date().toISOString() })
            .eq('id', pid);
          return error ? `ERR ${error.code} ${error.message}` : 'ok';
        }, [providerId, target[0], target[1]]);
        expect(res, 'the provider could not publish their own position from their own session — ' +
          'the publisher half is broken, not the watcher half').toBe('ok');
      }
      console.log(`[two-context] publisher path: ${movedByPage ? 'page watchPosition' : 'page session db write'}`);

      // ── THE ASSERTION: A's screen shows the NEW position, without a reload ───────────────────
      // The tracker polls every 10s (marketplace.html ~3584), so 30s covers two cycles.
      await expect.poll(async () =>
        A.evaluate(() => {
          const p = (window as any).__TB?.positions || [];
          return p.length ? p[p.length - 1][1] : null;
        }), {
        timeout: 60000, intervals: [2000],
        message: 'the watcher never repainted at the new position — a silent tracking failure is ' +
          'indistinguishable from a provider who did not move, which is why this cell exists',
      }).toBeCloseTo(target[1], 3);

      if (frozen) {
        const last = await A.evaluate(() => {
          const p = (window as any).__TB.positions; return p[p.length - 1];
        });
        expect(Math.abs(last[1] - TO[1]),
          'WH_TB_FREEZE=1: the publisher never moved, yet the watcher reported the NEW position — ' +
          'the harness is reading something other than the live feed').toBeGreaterThan(0.003);
        throw new Error('WH_TB_FREEZE=1 teeth run: the watcher correctly never showed the new ' +
          'position. Failing on purpose so a frozen publisher can never be mistaken for a pass.');
      }

      // NOT asserting a MapLibre marker, and the reason matters. Counting marker() calls races the
      // LAZY load of wh-map.js, and a DOM fallback (.maplibregl-marker) needs MapLibre to have
      // initialised against an EXTERNAL tile style (tiles.openfreemap.org). One run in three failed
      // on that combination, which made this cell measure network weather and WebGL availability
      // rather than the product — and two timing widenings did not help, because timing was never
      // the cause.
      //
      // The claim this cell exists for is already proven above: the watcher received the NEW
      // position. Asserted here instead is the page's OWN user-visible confirmation — in-DOM, no
      // external dependency, and the tracker writes it only after a position actually arrives.
      await expect(A.locator(`#svc-map-${requestId}-note`),
        'the tracker never told the watcher a live position had arrived')
        .toContainText(/position updated/i, { timeout: 20000 });

      await ctxA.close();
      await ctxB.close();
    });

  test('TB-SJ09-ui-the-open-page-learns-of-the-cancellation: the provider\'s screen stops showing a dead job',
    async ({ browser }: { browser: Browser }) => {
      test.slow();
      const db = adminClient();
      const { provider, providerUser, ownIds, client } = await soleProfileProvider(db);
      expect(provider, 'need a login owning exactly one provider profile').toBeTruthy();
      expect(client, 'need a client identity').toBeTruthy();

      // The provider is EN ROUTE — the state where a cancellation costs a real trip.
      const ins = await db.from('service_requests').insert({
        client_auth_uid: client!.auth_uid,
        client_worker_name: client!.display_name || client!.username,
        mode: 'instant', custom_scope: 'TB cancel-ui probe',
        location: `POINT(${SITE[0]} ${SITE[1]})`, address: 'Plant 9, Baguio',
        status: 'en_route', matched_provider_id: provider!.id,
      }).select('id').single();
      expect(ins.error, `could not plant the probe job: ${ins.error?.message}`).toBeNull();
      cancelRequestId = ins.data!.id;
      await db.from('service_providers')
        .update({ availability: 'on_job' }).eq('id', provider!.id);

      // ── the PROVIDER has the page open, looking at the job ──────────────────────────────────
      const ctxP = await browser.newContext();
      const P = await ctxP.newPage();
      await signInAs(P, providerUser);
      await P.goto('/workhive/marketplace-seller.html?tab=services', { waitUntil: 'domcontentloaded' });
      const jobCard = P.getByText('TB cancel-ui probe').first();
      await expect(jobCard, 'the provider never saw the job at all — nothing to cancel out from under them')
        .toBeVisible({ timeout: 20000 });

      // ── the CLIENT cancels, from their own session ──────────────────────────────────────────
      const ctxC = await browser.newContext();
      const C = await ctxC.newPage();
      await signInAs(C, client!.username);
      await C.goto('/workhive/marketplace.html', { waitUntil: 'domcontentloaded' });
      const res = await C.evaluate(async (id) => {
        const db2 = (window as any).db;
        const { error } = await db2.from('service_requests')
          .update({ status: 'cancelled_by_client', cancelled_at: new Date().toISOString(),
                    updated_at: new Date().toISOString() })
          .eq('id', id);
        return error ? `ERR ${error.code} ${error.message}` : 'ok';
      }, cancelRequestId);
      expect(res, 'the client could not cancel from their own session').toBe('ok');

      // ── THE ASSERTION: the provider's OPEN page must stop showing a job that no longer exists.
      // Not a nicety. The push tells them to stand down; if the page they are actually looking at
      // still lists the job as live, the product contradicts its own notification, and the screen is
      // the one they trust while driving.
      await expect.poll(async () => await jobCard.isVisible().catch(() => false), {
        timeout: 40000, intervals: [2000],
        message: 'the provider\'s open page still shows the cancelled job. The page never refreshes ' +
          '(no interval, no realtime subscription on marketplace-seller.html), so it keeps showing ' +
          'work that no longer exists until a manual reload.',
      }).toBe(false);

      await ctxP.close();
      await ctxC.close();
    });

  test('TB-SJ07-ui-the-watcher-sees-the-job-advance: the client\'s status chip keeps up with the provider',
    async ({ browser }: { browser: Browser }) => {
      test.slow();
      const db = adminClient();
      const { provider, providerUser, ownIds, client } = await soleProfileProvider(db);
      expect(provider, 'need a login owning exactly one provider profile').toBeTruthy();
      expect(client, 'need a client identity').toBeTruthy();

      const ins = await db.from('service_requests').insert({
        client_auth_uid: client!.auth_uid,
        client_worker_name: client!.display_name || client!.username,
        mode: 'instant', custom_scope: 'TB advance-ui probe',
        location: `POINT(${SITE[0]} ${SITE[1]})`, address: 'Plant 7, Baguio',
        status: 'accepted', matched_provider_id: provider!.id,
      }).select('id').single();
      expect(ins.error, `could not plant the probe job: ${ins.error?.message}`).toBeNull();
      advanceRequestId = ins.data!.id;
      await db.from('service_providers')
        .update({ availability: 'on_job' }).eq('id', provider!.id);

      // ── the CLIENT is watching their services pane ──────────────────────────────────────────
      const ctxC = await browser.newContext();
      const C = await ctxC.newPage();
      await signInAs(C, client!.username);
      await C.goto('/workhive/marketplace.html', { waitUntil: 'domcontentloaded' });
      await C.locator('.section-tab[data-section="services"]').click({ timeout: 15000 });
      const card = C.getByText('TB advance-ui probe').first();
      await expect(card, 'the client never saw their own job').toBeVisible({ timeout: 20000 });
      // SVC_CHIP maps accepted -> 'Provider accepted', en_route -> 'Provider on the way'.
      await expect(C.getByText('Provider accepted').first(),
        'the job did not start in the state this test needs').toBeVisible({ timeout: 15000 });

      // ── the PROVIDER advances it from their own session ─────────────────────────────────────
      const ctxP = await browser.newContext();
      const P = await ctxP.newPage();
      await signInAs(P, providerUser);
      await P.goto('/workhive/marketplace-seller.html?tab=services', { waitUntil: 'domcontentloaded' });
      const adv = await P.evaluate(async (id) => {
        const db2 = (window as any).db;
        const { error } = await db2.from('service_requests')
          .update({ status: 'en_route', updated_at: new Date().toISOString() }).eq('id', id);
        return error ? `ERR ${error.code} ${error.message}` : 'ok';
      }, advanceRequestId);
      expect(adv, 'the provider could not advance the job from their own session').toBe('ok');

      // ── THE ASSERTION: the client's chip must catch up without a reload.
      // The tracker map already polls every 10s, so on a job being watched the MAP MOVES while the
      // label beside it still reads "Provider accepted" — a screen that disagrees with itself is
      // worse than one that is merely stale, because the person cannot tell which half to believe.
      await expect.poll(async () =>
        await C.getByText('Provider on the way').first().isVisible().catch(() => false), {
        timeout: 50000, intervals: [2000],
        message: 'the client\'s status chip never advanced. marketplace.html has exactly one interval ' +
          '(the tracker map at ~3589) and loadClientServices() is only called after the client\'s OWN ' +
          'writes — so the map moves while the label still says the provider merely accepted.',
      }).toBe(true);

      await ctxC.close();
      await ctxP.close();
    });

  test('TB-SJ28-ui-a-waiting-provider-sees-the-hail-arrive: the feed refreshes with no job in hand',
    async ({ browser }: { browser: Browser }) => {
      test.slow();
      const db = adminClient();
      const { provider, providerUser, ownIds, client } = await soleProfileProvider(db);
      expect(provider, 'need a login owning exactly one provider profile').toBeTruthy();
      expect(client, 'need a client identity').toBeTruthy();

      // THE STATE THAT MATTERS: online, and holding NO job. This is a provider waiting for work — the
      // entire promise the platform makes to them — and it is the state in which the page had no
      // reason to refresh at all.
      await db.from('service_providers')
        .update({ availability: 'online' }).eq('id', provider!.id);
      await db.from('service_requests').delete()
        .eq('matched_provider_id', provider!.id).in('status', ['accepted', 'en_route', 'on_site', 'in_progress']);

      const ctxP = await browser.newContext();
      const P = await ctxP.newPage();
      await signInAs(P, providerUser);
      await P.goto('/workhive/marketplace-seller.html?tab=services', { waitUntil: 'domcontentloaded' });
      await P.waitForTimeout(3000);   // let the first load settle

      // ── the CLIENT hails, from their own session ────────────────────────────────────────────
      const cat = (provider!.categories || [])[0] || 'Plumbing';
      const ins = await db.from('service_requests').insert({
        client_auth_uid: client!.auth_uid,
        client_worker_name: client!.display_name || client!.username,
        mode: 'quote', custom_scope: 'TB waiting-provider hail probe',
        location: `POINT(${SITE[0]} ${SITE[1]})`, address: 'Plant 5, Baguio',
        broadcast_radius_m: 100000,   // CHECK max; *4 reach covers any seeded provider status: 'broadcasting',
      }).select('id').single();
      expect(ins.error, `could not plant the hail: ${ins.error?.message}`).toBeNull();
      hailRequestId = ins.data!.id;
      await db.from('service_requests').update({ status: 'broadcasting' }).eq('id', hailRequestId);
      const planted_hailRequestId = await db.from('service_requests').select('status').eq('id', hailRequestId).single();
      expect(planted_hailRequestId.data?.status,
        'the hail is not broadcasting, so no provider feed can carry it').toBe('broadcasting');

      // ── THE ASSERTION: it appears on the page they are already looking at.
      await expect.poll(async () =>
        await P.getByText('TB waiting-provider hail probe').first().isVisible().catch(() => false), {
        timeout: 90000, intervals: [2500],
        message: 'a provider sitting on the page with NO job in hand never saw the hail arrive. The ' +
          'refresh arms only while jobs.some(SVC_ACTIVE) — so the feed is frozen in exactly the state ' +
          'the platform promises them: online, waiting, and told nothing.',
      }).toBe(true);

      await ctxP.close();
    });

  test('TB-SJ33-ui-presence-counts-a-provider-who-just-came-online: publisher x viewer, and the number is TRUE',
    async ({ browser }: { browser: Browser }) => {
      test.slow();
      const db = adminClient();
      const { provider, providerUser, ownIds, client } = await soleProfileProvider(db);
      expect(provider, 'need a login owning exactly one provider profile').toBeTruthy();
      expect(client, 'need a client identity').toBeTruthy();
      presenceProviderId = provider!.id;
      // Captured so afterAll can put a REAL seeded provider back exactly as it was: this
      // walk flips a live availability, and residue is not evidence.
      presenceWasAvailability = provider!.availability || 'online';

      // ── PUBLISHER: take them OFFLINE first, so "came online" is a real transition and not a
      //    coincidence of whatever the seed left behind.
      await db.from('service_providers').update({ availability: 'offline' }).eq('id', presenceProviderId);
      const before = Number((await db.from('v_service_area_presence').select('providers_online'))
        .data?.reduce((s: number, r: any) => s + Number(r.providers_online || 0), 0) || 0);

      // The provider goes online through their OWN page control, not an admin write — the publisher
      // side of this pair is a person flipping their availability.
      const ctxP = await browser.newContext();
      const P = await ctxP.newPage();
      await signInAs(P, providerUser);
      await P.goto('/workhive/marketplace-seller.html?tab=services', { waitUntil: 'domcontentloaded' });
      const flipped = await P.evaluate(async (pid) => {
        const db2 = (window as any).db;
        const { error } = await db2.from('service_providers')
          .update({ availability: 'online', updated_at: new Date().toISOString() }).eq('id', pid);
        return error ? `ERR ${error.code} ${error.message}` : 'ok';
      }, presenceProviderId);
      expect(flipped, 'the provider could not go online from their own session').toBe('ok');

      const after = Number((await db.from('v_service_area_presence').select('providers_online'))
        .data?.reduce((s: number, r: any) => s + Number(r.providers_online || 0), 0) || 0);
      expect(after, 'the presence view did not count a provider who just came online').toBe(before + 1);

      // ── VIEWER: a consumer opens the composer and the rendered number MATCHES the view. A liquidity
      //    hint that overstates is worse than no hint: it tells someone to wait for help that is not
      //    there.
      const ctxC = await browser.newContext();
      const C = await ctxC.newPage();
      await signInAs(C, client!.username);
      await C.goto('/workhive/marketplace.html', { waitUntil: 'domcontentloaded' });
      await C.locator('.section-tab[data-section="services"]').click({ timeout: 15000 });
      const line = C.locator('#svc-presence');
      await expect(line, 'the presence line never rendered for the viewer').toContainText(/provider/i,
        { timeout: 20000 });
      /* THE TRUTH IS DISTINCT PEOPLE, NOT THE SUM OF AREA ROWS — and this cell used to assert the sum.
         v_service_area_presence is one row per SERVICE AREA, so a provider covering {Batangas, Manila}
         appears twice; summing those rows into a headline double-counts them. Measured live: the sum
         said 9 while exactly 7 providers had availability='online'. The UI was fixed to take a DISTINCT
         head-count, and this assertion went red for the right reason — the code got better and the
         expectation was still pinned to the old, overstating number.
         The cell's own comment above already names the principle it was violating: a liquidity hint that
         overstates is worse than none, because it tells someone to wait for help that is not there. So
         the expectation moves to the truth, not the code back to the bug
         ([[feedback_a_gate_reddened_because_the_code_improved]], [[feedback_teach_the_gate_not_bend_the_code]]).
         The `after === before + 1` check above still stands: the per-area view SHOULD increment when
         someone comes online — that view is not wrong, it is just the wrong thing to sum. */
      const { count: distinctOnline } = await db.from('service_providers')
        .select('id', { count: 'exact', head: true }).eq('availability', 'online');
      const shown = Number(((await line.innerText()).match(/(\d+)\s+provider/i) || [])[1] || -1);
      expect(shown, `the rendered count (${shown}) must equal the number of DISTINCT online providers `
        + `(${distinctOnline}); the per-area sum is ${after}, which double-counts anyone covering two `
        + 'areas').toBe(Number(distinctOnline));

      await ctxP.close();
      await ctxC.close();
    });

  test('TB-SJ01-responder-answers-the-hail: the provider accepts from their own page and the client sees it',
    async ({ browser }: { browser: Browser }) => {
      test.slow();
      const db = adminClient();
      const { provider, providerUser, ownIds, client } = await soleProfileProvider(db);
      expect(provider, 'need a login owning exactly one provider profile').toBeTruthy();
      expect(client, 'need a client identity').toBeTruthy();

      await db.from('service_providers').update({ availability: 'online' }).eq('id', provider!.id);
      await db.from('service_requests').delete().eq('matched_provider_id', provider!.id)
        .in('status', ['accepted', 'en_route', 'on_site', 'in_progress']);

      const ins = await db.from('service_requests').insert({
        client_auth_uid: client!.auth_uid,
        client_worker_name: client!.display_name || client!.username,
        mode: 'instant', custom_scope: 'TB responder-answer probe',
        location: `POINT(${SITE[0]} ${SITE[1]})`, address: 'Plant 3, Baguio',
        broadcast_radius_m: 100000,   // CHECK max; *4 reach covers any seeded provider status: 'broadcasting',
      }).select('id').single();
      expect(ins.error, `could not plant the hail: ${ins.error?.message}`).toBeNull();
      answerRequestId = ins.data!.id;
      // An INSTANT request is normalised to `requested` on insert regardless of what is supplied — a
      // quote-mode one keeps `broadcasting`, which is why the sibling hail cell never hit this. The
      // feed requires `broadcasting`, so the hail was silently invisible and the failure looked like a
      // missing Accept control. Patch it and ASSERT it stuck, rather than trusting the write.
      await db.from('service_requests').update({ status: 'broadcasting' }).eq('id', answerRequestId);
      const planted = await db.from('service_requests').select('status').eq('id', answerRequestId).single();
      expect(planted.data?.status, 'the hail is not broadcasting, so no provider feed can carry it')
        .toBe('broadcasting');

      // ── the CLIENT is watching their own request ────────────────────────────────────────────
      const ctxC = await browser.newContext();
      const C = await ctxC.newPage();
      await signInAs(C, client!.username);
      await C.goto('/workhive/marketplace.html', { waitUntil: 'domcontentloaded' });
      await C.locator('.section-tab[data-section="services"]').click({ timeout: 15000 });
      await expect(C.getByText('TB responder-answer probe').first(),
        'the client never saw their own hail').toBeVisible({ timeout: 20000 });

      // ── the RESPONDER answers it, through the page's own Accept control ─────────────────────
      // This is the act none of the five hail journeys had ever walked: they were all walked from the
      // HAILER's side, so "a provider answers" was assumed by every one of them and proven by none.
      const ctxP = await browser.newContext();
      const P = await ctxP.newPage();
      await signInAs(P, providerUser);
      await P.goto('/workhive/marketplace-seller.html?tab=services', { waitUntil: 'domcontentloaded' });
      // Scoped to the CARD that names this hail, then the affordance by its role and name. An
      // attribute-substring selector on onclick was tried first and did not match; the page's own
      // query returned the feed and the pane rendered, so the selector was the problem rather than the
      // product. Card-then-role is also what a person does: find the request, press its button.
      const card = P.locator('.simple-card').filter({ hasText: 'TB responder-answer probe' }).first();
      await expect(card, 'the hail never appeared in the provider feed')
        .toBeVisible({ timeout: 25000 });
      const acceptBtn = card.getByRole('button', { name: /accept job/i });
      await expect(acceptBtn, 'the hail appeared but offered no Accept control')
        .toBeVisible({ timeout: 15000 });
      await acceptBtn.click();

      // The DB is the first witness: accepted, matched to THIS provider.
      await expect.poll(async () => {
        const r = await db.from('service_requests').select('status, matched_provider_id')
          .eq('id', answerRequestId).single();
        // Against the login's OWN ids: the RPC chooses which profile accepts.
        return `${r.data?.status}:${ownIds.includes(r.data?.matched_provider_id)}`;
      }, { timeout: 25000, intervals: [1500],
           message: 'the provider pressed Accept and the request never became theirs' })
        .toBe('accepted:true');

      // SJ-J27: accepting also LANDS the job on the provider's own dayplan (land_accepted_job_on_dayplan).
      // Asserted here rather than in its own cell because it is a side-effect of this exact act, and
      // because the CLIENT half of J27 has nothing further to walk: schedule_items is owner-only RLS
      // (auth_uid = auth.uid()) and marketplace.html reads it ZERO times, so a provider's calendar is
      // deliberately invisible to the client. What the client is owed is that the job reads accepted,
      // which the assertion below is.
      await expect.poll(async () => {
        const r = await db.from('schedule_items').select('id')
          .ilike('title', '%TB responder-answer probe%');
        return (r.data || []).length;
      }, { timeout: 20000, intervals: [1500],
           message: 'accepting the job did not land it on the provider’s dayplan' })
        .toBeGreaterThan(0);

      // ── AND THE CLIENT SEES IT, with no reload. SVC_CHIP maps accepted -> 'Provider accepted'.
      await expect.poll(async () =>
        await C.getByText('Provider accepted').first().isVisible().catch(() => false), {
        timeout: 90000, intervals: [2500],
        message: 'the job was accepted and the client page never said so — the handoff completed in ' +
          'the database and stopped at the screen',
      }).toBe(true);

      await ctxC.close();
      await ctxP.close();
    });

  test('TB-SJ10-ui-the-client-learns-the-provider-cancelled: the stranded party is the one who must be told',
    async ({ browser }: { browser: Browser }) => {
      test.slow();
      const db = adminClient();
      const { provider, providerUser, ownIds, client } = await soleProfileProvider(db);
      expect(provider, 'need a login owning exactly one provider profile').toBeTruthy();
      expect(client, 'need a client identity').toBeTruthy();

      await db.from('service_providers').update({ availability: 'on_job' }).eq('id', provider!.id);
      const ins = await db.from('service_requests').insert({
        client_auth_uid: client!.auth_uid,
        client_worker_name: client!.display_name || client!.username,
        mode: 'instant', custom_scope: 'TB prov-cancel probe',
        location: `POINT(${SITE[0]} ${SITE[1]})`, address: 'Plant 8, Baguio',
        status: 'accepted', matched_provider_id: provider!.id,
      }).select('id').single();
      expect(ins.error, `could not plant the probe job: ${ins.error?.message}`).toBeNull();
      provCancelRequestId = ins.data!.id;

      // ── the CLIENT is watching, expecting someone to arrive ──────────────────────────────────
      const ctxC = await browser.newContext();
      const C = await ctxC.newPage();
      await signInAs(C, client!.username);
      await C.goto('/workhive/marketplace.html', { waitUntil: 'domcontentloaded' });
      await C.locator('.section-tab[data-section="services"]').click({ timeout: 15000 });
      await expect(C.getByText('Provider accepted').first(),
        'the client never saw the accepted state this test needs').toBeVisible({ timeout: 20000 });

      // ── the PROVIDER cancels, from their own session ─────────────────────────────────────────
      const ctxP = await browser.newContext();
      const P = await ctxP.newPage();
      await signInAs(P, providerUser);
      await P.goto('/workhive/marketplace-seller.html?tab=services', { waitUntil: 'domcontentloaded' });
      const res = await P.evaluate(async (id) => {
        const db2 = (window as any).db;
        const { error } = await db2.from('service_requests')
          .update({ status: 'cancelled_by_provider', cancelled_at: new Date().toISOString(),
                    updated_at: new Date().toISOString() }).eq('id', id);
        return error ? `ERR ${error.code} ${error.message}` : 'ok';
      }, provCancelRequestId);
      expect(res, 'the provider could not cancel from their own session').toBe('ok');

      // ── THE ASSERTION: the CLIENT stops being told someone is coming. They are the stranded party
      //    here — waiting for a person who is no longer on the way — and the screen is what they have.
      const ownCard = C.locator('.simple-card, .sc-body, [data-svc-req]')
        .filter({ hasText: 'TB prov-cancel probe' });
      await expect.poll(async () => {
        const n = await ownCard.count();
        if (!n) return false;                       // the card itself may be dropped from the list
        return (await ownCard.first().innerText()).includes('Provider accepted');
      }, {
        timeout: 90000, intervals: [2500],
        message: 'this job’s own card still says the provider accepted, after the provider ' +
          'cancelled. They are waiting for someone who is not coming.',
      }).toBe(false);

      await ctxC.close();
      await ctxP.close();
    });

  test('TB-SJ06-ui-the-quoter-composes-and-the-client-compares: a price sent by a person, seen by a person',
    async ({ browser }: { browser: Browser }) => {
      test.slow();
      const db = adminClient();
      const { provider, providerUser, ownIds, client } = await soleProfileProvider(db);
      expect(provider, 'need a login owning exactly one provider profile').toBeTruthy();
      expect(client, 'need a client identity').toBeTruthy();

      await db.from('service_providers').update({ availability: 'online' }).eq('id', provider!.id);
      const ins = await db.from('service_requests').insert({
        client_auth_uid: client!.auth_uid,
        client_worker_name: client!.display_name || client!.username,
        mode: 'quote', custom_scope: 'TB quoter-ui probe',
        location: `POINT(${SITE[0]} ${SITE[1]})`, address: 'Plant 6, Baguio',
        broadcast_radius_m: 100000,   // CHECK max; *4 reach covers any seeded provider status: 'broadcasting',
      }).select('id').single();
      expect(ins.error, `could not plant the quote request: ${ins.error?.message}`).toBeNull();
      quoteRequestId = ins.data!.id;
      await db.from('service_requests').update({ status: 'broadcasting' }).eq('id', quoteRequestId);
      const planted_quoteRequestId = await db.from('service_requests').select('status').eq('id', quoteRequestId).single();
      expect(planted_quoteRequestId.data?.status,
        'the hail is not broadcasting, so no provider feed can carry it').toBe('broadcasting');

      // ── THE QUOTER: a provider types a PRICE on their own page and sends it. This is the act the
      //    journey is named for and the one nobody had walked - SJ-J06 was walked as two CLIENTS, so a
      //    quote-selection journey had no quote in it.
      const ctxP = await browser.newContext();
      const P = await ctxP.newPage();
      await signInAs(P, providerUser);
      await P.goto('/workhive/marketplace-seller.html?tab=services', { waitUntil: 'domcontentloaded' });
      const qCard = P.locator('.simple-card').filter({ hasText: 'TB quoter-ui probe' }).first();
      await expect(qCard, 'the quote request never appeared in the provider feed')
        .toBeVisible({ timeout: 25000 });
      const priceInput = qCard.locator('input[type=number]').first();
      await expect(priceInput, 'the provider was never offered a price field for this request')
        .toBeVisible({ timeout: 15000 });
      await priceInput.fill('4750');
      await qCard.getByRole('button', { name: /send quote/i }).click();

      // The offer must exist, owned by THIS provider, at the price they typed.
      await expect.poll(async () => {
        const r = await db.from('service_offers').select('provider_id, price, kind, status')
          .eq('request_id', quoteRequestId).eq('kind', 'quote').maybeSingle();
        // Asserted against the login's OWN profiles, not one hardcoded id — the RPC chooses which of
        // them files the quote, and either choice is correct.
        return `${ownIds.includes(r.data?.provider_id)}:${Number(r.data?.price)}:${r.data?.status}`;
      }, { timeout: 25000, intervals: [1500],
           message: 'the provider sent a quote and no offer of theirs exists at that price' })
        .toBe('true:4750:pending');

      // ── AND THE CLIENT COMPARES IT. A quote nobody can see is not a quote; the number is the whole
      //    point, so the client must see the PRICE, not just that "a quote arrived".
      const ctxC = await browser.newContext();
      const C = await ctxC.newPage();
      await signInAs(C, client!.username);
      await C.goto('/workhive/marketplace.html', { waitUntil: 'domcontentloaded' });
      await C.locator('.section-tab[data-section="services"]').click({ timeout: 15000 });
      const showQuotes = C.locator(`button[onclick*="svcShowQuotes('${quoteRequestId}')"]`).first();
      await expect(showQuotes, 'the client was never offered a way to view their quotes')
        .toBeVisible({ timeout: 20000 });
      await showQuotes.click();
      await expect(C.getByText(/4,?750/).first(),
        'the client opened their quotes and the price the provider sent was not among them')
        .toBeVisible({ timeout: 20000 });

      await ctxP.close();
      await ctxC.close();
    });

  test('TB-S2-pwa-offline-hail-degraded: an offline hail is refused in words, and writes nothing',
    async ({ browser }: { browser: Browser }) => {
      test.slow();
      const db = adminClient();
      const { data: workers } = await db.from('worker_profiles')
        .select('username, auth_uid').not('auth_uid', 'is', null).limit(1);
      const w = (workers || [])[0];
      expect(w, 'need a seeded worker to hail as').toBeTruthy();

      const ctx = await browser.newContext();
      const P = await ctx.newPage();
      await signInAs(P, w.username);
      await P.goto('/workhive/marketplace.html', { waitUntil: 'domcontentloaded' });
      await P.locator('.section-tab[data-section="services"]').click({ timeout: 15000 });

      // Count first. "No new row" is only meaningful against a baseline taken at the same moment —
      // this account may already own requests from earlier walks.
      const before = await db.from('service_requests')
        .select('id', { count: 'exact', head: true }).eq('client_auth_uid', w.auth_uid);

      await ctx.setOffline(true);
      // Straight at the submit, with the form deliberately EMPTY. svcRequireOnline runs before the
      // field validation, so an offline person is told about the network rather than being sent to
      // fix an address they cannot submit anyway — and this also proves the guard is FIRST.
      await P.evaluate(() => (window as any).svcHailNow && (window as any).svcHailNow());
      const toast = P.getByText(/offline/i).first();
      await expect(toast, 'an offline hail produced no message naming the offline state — the ' +
        'person is left to guess whether a provider was called').toBeVisible({ timeout: 8000 });
      const words = (await toast.textContent()) || '';
      expect(words.toLowerCase(),
        'the offline message must say that NOTHING was sent; "try again later" leaves the person ' +
        'wondering whether a half-request is out there').toContain('nothing was sent');

      await ctx.setOffline(false);
      const after = await db.from('service_requests')
        .select('id', { count: 'exact', head: true }).eq('client_auth_uid', w.auth_uid);
      expect(after.count, 'an offline hail CREATED a request — the guard let a write through, or ' +
        'the page queued a job the provider never hears about').toBe(before.count);

      await ctx.close();
    });
});
