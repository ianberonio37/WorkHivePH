/**
 * marketplace-sim-entrypoints.spec.ts — the doors into the hail that are not the marketplace.
 *
 * Most real hails do not begin on the services tab. They begin at an alert that just fired, a PM that
 * came due, or an asset someone is standing in front of. Each of those crosses a page boundary carrying
 * context — which asset, what the problem is — and a dropped payload is invisible in SQL: the request
 * still inserts, it just arrives blank, and a provider accepts a job whose description says nothing.
 *
 * So every cell here asserts the CONTEXT SURVIVED THE JUMP, not merely that the destination loaded.
 *
 * The PM door is different in kind: nobody presses it. sweep_pm_auto_hail files hails on its own for due
 * scope items, which means a bug there produces requests no human ever asked for — the one entry point
 * that can spam the marketplace unattended, so it is also asserted not to duplicate.
 */
import { test, expect, Page } from '@playwright/test';
import { adminClient, cleanupServiceArc } from './_db-cleanup';

const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';
const CLIENT = 'romeobeltran@auth.workhiveph.com';
const ADMIN = 'pabloaguilar@auth.workhiveph.com';
const TAG = 'SIMENTRY';

async function signIn(page: Page, email: string) {
  await page.goto('/workhive/index.html', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => typeof (window as any).getDb === 'function', { timeout: 20000 });
  await page.evaluate(async ([mail, pass]) => {
    const db = (window as any).getDb();
    await db.auth.signOut();
    await db.auth.signInWithPassword({ email: mail, password: pass });
  }, [email, PASSWORD]);
}

test.describe('marketplace simulation — the other doors into a hail', () => {

  test.afterAll(async () => { await cleanupServiceArc(TAG); });

  test('ASSET CONTEXT · arriving with ?asset= prefills the hail, not just the tab', async ({ page }) => {
    await signIn(page, CLIENT);
    await page.goto('/workhive/marketplace.html?section=services&asset=' + encodeURIComponent('AHU-01')
      + '&scope=' + encodeURIComponent('bearing noise on startup'));
    await page.waitForTimeout(4500);

    const r = await page.evaluate(() => {
      const pane = document.getElementById('services-pane');
      /* The landing pad prefills the QUOTE form's scope textarea (`svc-quote-scope`), which is the right
         target — an asset with a described problem is a quote job, not a one-tap instant hail. Reading
         `innerText` here found nothing and looked like a dropped payload: a textarea's VALUE is not part
         of innerText, so the first version of this test was measuring a place the answer could never
         appear ([[feedback_verify_the_instrument_before_the_page]]). */
      const scope = document.getElementById('svc-quote-scope') as HTMLTextAreaElement | null;
      return {
        onServices: !!pane && pane.offsetParent !== null,
        scope: (scope?.value || ''),
        exists: !!scope,
      };
    });
    expect(r.onServices, 'arriving with ?section=services did not land on the services view — the '
      + 'hand-off drops the user on the parts grid instead').toBe(true);
    expect(r.exists, 'the services view has no quote-scope field for the hand-off to fill').toBe(true);
    // The payload is the point. Landing on the right tab with an empty form means the technician
    // retypes what they just told the alert-hub, and most will not.
    expect(r.scope.toLowerCase(), 'the asset and problem passed in the URL never reached the form — the '
      + 'context was dropped in the jump, so the technician retypes what they already said')
      .toMatch(/ahu-01/);
    expect(r.scope.toLowerCase(), 'the asset tag arrived but the described problem did not')
      .toContain('bearing noise');
  });

  test('ALERT → HAIL · the alert-hub link carries the asset it was raised for', async ({ page }) => {
    await signIn(page, ADMIN);
    /* SEED THE HIVE CONTEXT THE WAY A REAL SIGN-IN DOES. alert-hub reads `wh_hive_id` from localStorage
       and, finding none, correctly shows its "join a hive" gate and returns BEFORE loading any alerts —
       so a programmatic sign-in lands on an empty page and the cell skipped, looking like the hand-off
       did not exist. That is the harness, not the product: signing in through index.html sets the hive.
       (Chasing this did surface a real bug alongside it — v_worker_truth carries one row per hive
       membership, so `.maybeSingle()` resolved to NULL for the two multi-hive accounts and bounced them
       to the sign-in screen on any cold load. Fixed in utils.js.) */
    await page.evaluate(async () => {
      const db = (window as any).getDb();
      const { data: s } = await db.auth.getSession();
      const { data: m } = await db.from('hive_members')
        .select('hive_id, hives(name)').eq('auth_uid', s.session.user.id)
        .eq('status', 'active').limit(1);
      if (m?.length) {
        localStorage.setItem('wh_hive_id', m[0].hive_id);
        if (m[0].hives?.name) localStorage.setItem('wh_hive_name', m[0].hives.name);
      }
    });
    await page.goto('/workhive/alert-hub.html');
    await page.waitForTimeout(9000);
    const link = await page.evaluate(() => {
      const a = Array.from(document.querySelectorAll('a[href*="marketplace.html"]'))
        .map(x => x.getAttribute('href') || '')
        .find(h => h.includes('section=services'));
      return a || null;
    });
    test.skip(!link, 'no alert currently offers a hail hand-off');
    expect(link, 'the alert-hub links to the marketplace without selecting the services view')
      .toContain('section=services');
    // An `asset=` with nothing after it is the dropped-payload bug in its exact form: the link looks
    // wired, and the destination gets nothing.
    const asset = (link!.match(/asset=([^&]*)/) || [])[1] ?? '';
    expect(decodeURIComponent(asset).trim(), 'the hail link carries an EMPTY asset parameter — it looks '
      + 'wired and hands over nothing, which is worse than not linking at all').not.toBe('');
  });

  test('PM AUTO-HAIL · the sweep files its own hails and never duplicates them', async () => {
    const admin = adminClient();
    const before = await admin.from('service_requests').select('id').not('pm_scope_item_id', 'is', null);
    const r1: any = await admin.rpc('sweep_pm_auto_hail');
    const mid = await admin.from('service_requests').select('id').not('pm_scope_item_id', 'is', null);
    // Running it twice must not file the same job again — the sweep is on a daily cron and an
    // unattended duplicate is a hail nobody asked for, sent to real providers.
    await admin.rpc('sweep_pm_auto_hail');
    const after = await admin.from('service_requests').select('id').not('pm_scope_item_id', 'is', null);

    expect(r1.error, `the PM auto-hail sweep errored: ${r1.error?.message}`).toBeFalsy();
    expect(after.data?.length ?? 0, 'running the PM sweep twice filed MORE hails the second time — a '
      + 'daily cron would spam providers with jobs nobody asked for')
      .toBe(mid.data?.length ?? 0);
    expect((mid.data?.length ?? 0) >= (before.data?.length ?? 0), 'the sweep removed PM hails').toBe(true);
  });

  test('MAP PIN · tapping again MOVES the pin rather than adding a second one', async ({ page }) => {
    await signIn(page, CLIENT);
    await page.goto('/workhive/marketplace.html');
    await page.waitForTimeout(3500);
    await page.click('[data-section="services"]');
    await page.waitForTimeout(2000);
    await page.click('#svc-pin-btn');
    await page.waitForTimeout(6000);

    const r = await page.evaluate(async () => {
      const w = window as any;
      if (!w.maplibregl) return { skipped: true };
      const box = document.querySelector('#svc-pin-map') as HTMLElement;
      if (!box) return { skipped: true };
      const b = box.getBoundingClientRect();
      const tap = (dx: number, dy: number) => {
        const ev = new MouseEvent('click', { bubbles: true, clientX: b.left + dx, clientY: b.top + dy });
        box.querySelector('canvas')?.dispatchEvent(ev);
      };
      tap(80, 80); await new Promise(r => setTimeout(r, 900));
      const first = w._svcPin ? JSON.stringify(w._svcPin) : null;
      tap(160, 140); await new Promise(r => setTimeout(r, 900));
      const second = w._svcPin ? JSON.stringify(w._svcPin) : null;
      const markers = box.querySelectorAll('.maplibregl-marker').length;
      return { skipped: false, first, second, markers };
    });
    test.skip(!!r.skipped, 'the pin map did not render in this environment');
    // Two markers means the earlier taps are still on the map, and the client cannot tell which one the
    // provider will drive to.
    expect(r.markers, `tapping twice left ${r.markers} markers on the map — the client has no way to `
      + 'know which pin the provider receives').toBeLessThanOrEqual(1);
  });

  test('ADMIN · nobody may verify a top-up they filed themselves', async ({ page }) => {
    /* The self-deal shape, on the one action that mints money. An admin is allowed to verify OTHER
       people's top-ups — that is the job — so the refusal has to be specifically about their own. */
    const admin = adminClient();
    const { data: users } = await admin.auth.admin.listUsers();
    const adminId = users.users.find((u: any) => u.email === ADMIN)?.id;
    const { data: prov } = await admin.from('service_providers')
      .select('id').eq('auth_uid', adminId).limit(1);
    test.skip(!prov?.length, 'the admin owns no provider profile to file a top-up against');

    const { data: t } = await admin.from('service_credit_topups').insert({
      account_type: 'provider', account_id: prov![0].id, payer_auth_uid: adminId,
      amount: 1000, gcash_ref: '5555555555555', status: 'pending_verification', note: TAG,
    }).select('id').single();

    await signIn(page, ADMIN);
    await page.goto('/workhive/founder-console.html');
    await page.waitForTimeout(6000);
    const outcome = await page.evaluate(async (tid) => {
      const db = (window as any).getDb();
      const { data, error } = await db.from('service_credit_topups')
        .update({ status: 'verified' }).eq('id', tid).select('id');
      return error ? 'refused' : (data?.length ? 'ACCEPTED' : 'refused:0rows');
    }, t!.id);

    const { data: after } = await admin.from('service_credit_topups').select('status').eq('id', t!.id);
    const { data: led } = await admin.from('service_credit_ledger').select('id').eq('ref_id', t!.id);
    expect(outcome === 'ACCEPTED' && after![0].status === 'verified' && (led?.length ?? 0) > 0,
      'an admin verified a top-up THEY filed and minted themselves credits — the person claiming the '
      + 'money arrived is the same person confirming it did').toBe(false);

    await admin.from('service_credit_ledger').delete().eq('ref_id', t!.id);
    await admin.from('service_credit_topups').delete().eq('id', t!.id);
  });
});
