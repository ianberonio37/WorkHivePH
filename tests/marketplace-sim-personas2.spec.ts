/**
 * marketplace-sim-personas2.spec.ts — the second persona sweep, aimed at the money screen.
 *
 * Every other spec walks a competent, sighted, literate, English-reading, fast-network, calm user.
 * Almost nobody on this platform is all six at once: PH plant technicians in their fifties, first-time
 * e-wallet users, someone outdoors in glare wearing gloves, someone on 3G with ₱20 of load left. Ian's
 * instruction was explicit — the diversity belongs on the JOURNEY axis, because it is a property of who
 * is walking, not of the page.
 *
 * UFAI GRADES THE PAGE; THIS WALKS THE HUMAN. `validate_service_ufai_deep.py` already measures tap
 * targets and overflow at 390/1280, `validate_i18n_coverage.py` owns language, and the keyboard gate owns
 * focus order. None of them can answer "could THIS person finish THIS task unaided?" — which is the only
 * question here, and why the oracle is `task-success` rather than a rubric score.
 *
 * PAIRED, NOT MULTIPLIED. 25 personas × 30 journeys is 750 walks nobody runs, and an unrunnable matrix
 * silently becomes an unrun one. Each persona is bound to the surface where it is most likely to break,
 * with the money screen taking the heaviest sweep — that is where failure costs pesos rather than a
 * re-render.
 */
import { test, expect, Page, Browser } from '@playwright/test';
import { adminClient, cleanupServiceArc } from './_db-cleanup';

const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';
const CLIENT = 'romeobeltran@auth.workhiveph.com';
const PROVIDER = 'bryangarcia@auth.workhiveph.com';
const TAG = 'SIMPERSONA2';

async function signIn(page: Page, email: string) {
  await page.goto('/workhive/index.html', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => typeof (window as any).getDb === 'function', { timeout: 20000 });
  await page.evaluate(async ([mail, pass]) => {
    const db = (window as any).getDb();
    await db.auth.signOut();
    await db.auth.signInWithPassword({ email: mail, password: pass });
  }, [email, PASSWORD]);
}

async function openServices(page: Page) {
  await page.goto('/workhive/marketplace.html');
  await page.waitForTimeout(3500);
  await page.click('[data-section="services"]');
  await page.waitForTimeout(2500);
}

/* Stage one completed job. Every persona below needs a job sitting at `completed` so the confirm form
   exists — but ONE of them (P-IMPULSIVE) settles it, which takes the form away from everything that runs
   after. Sharing a fixture with a test that consumes it is asserting a state you do not control
   ([[feedback_a_test_asserting_a_state_it_does_not_control]]), and in serial mode it fails as a
   null-reference three tests later, which reads like a page bug rather than a staging one. So the
   destructive cell gets its own. */
async function stageCompleted(browser: Browser, note: string) {
  const cctx = await browser.newContext(); const c = await cctx.newPage();
  const pctx = await browser.newContext(); const p = await pctx.newPage();
  try {
    await signIn(c, CLIENT); await signIn(p, PROVIDER);
    const rid = await c.evaluate(async ([tag, n]) => {
      const db = (window as any).getDb();
      const { data: s } = await db.auth.getSession();
      const { data: prov } = await db.from('service_providers').select('hive_id')
        .not('hive_id', 'is', null).limit(1);
      const { data } = await db.from('service_requests').insert({
        client_auth_uid: s.session.user.id, hive_id: prov?.[0]?.hive_id, segment: 'consumer',
        mode: 'instant', status: 'broadcasting', custom_scope: tag + ' ' + n, budget: 1500,
      }).select('id').single();
      return data?.id as string;
    }, [TAG, note] as any);
    const acc = await p.evaluate(async (r) => {
      const db = (window as any).getDb();
      const { data } = await db.rpc('accept_service_request', { p_request_id: r });
      return { ok: !!data?.accepted, reason: data?.reason };
    }, rid);
    expect(acc.ok, `staging "${note}" could not be accepted: ${acc.reason}`).toBe(true);
    for (const st of ['en_route', 'on_site', 'in_progress', 'completed']) {
      await p.evaluate(async ([r, s]) => {
        const db = (window as any).getDb();
        await db.from('service_requests').update({ status: s }).eq('id', r);
      }, [rid, st] as any);
    }
    return rid;
  } finally { await cctx.close(); await pctx.close(); }
}

test.describe('marketplace simulation — personas on the money screen', () => {
  test.describe.configure({ mode: 'serial' });

  let REQ = '';

  test.beforeAll(async ({ browser }) => {
    REQ = await stageCompleted(browser, 'shared read-only job');
  });

  test.afterAll(async () => { await cleanupServiceArc(TAG); });

  test('P-FILIPINO · the money screen speaks Filipino, or it is not a money screen', async ({ browser }) => {
    /* The highest-stakes translation on the platform. "Settle", "release", "commission" and "cashback"
       have no clean everyday Tagalog equivalent, so an untranslated money form is not a cosmetic gap —
       it is someone agreeing to a peso figure in a language they may not read. This form is rendered by
       JS AFTER DOMContentLoaded, which is exactly the case whI18nApply() misses by default. */
    const ctx = await browser.newContext({ locale: 'fil-PH' });
    const page = await ctx.newPage();
    try {
      await signIn(page, CLIENT);
      await page.addInitScript(() => { (window as any).WH_LANG = 'fil'; });
      await openServices(page);
      const t = await page.evaluate((rid) => {
        (window as any).WH_LANG = 'fil';
        (window as any).svcConfirmPay(rid, 1500);
        const slot = document.getElementById('svc-pay-' + rid);
        const unresolved = Array.from(slot?.querySelectorAll('[data-i]') || [])
          .filter(el => {
            const k = el.getAttribute('data-i')!;
            const dict = Object.assign({}, (window as any).WH_FIL_COMMON || {}, (window as any).WH_FIL_PAGE || {});
            return dict[k] == null;
          }).map(el => el.getAttribute('data-i'));
        return { text: (slot?.innerText || ''), unresolved,
                 marked: (slot?.querySelectorAll('[data-i]') || []).length };
      }, REQ);

      expect(t.marked, 'the money form carries NO translation markers at all, so it can never be shown '
        + 'in Filipino no matter what the dictionary holds').toBeGreaterThan(5);
      expect(t.unresolved, `these money labels have no Filipino string: ${t.unresolved.join(', ')} — a `
        + 'marker with no dictionary entry renders the key or the English, which is worse than untranslated '
        + 'because it looks deliberate').toEqual([]);
      // The sentence that decides whether a wary user presses the button must itself be translated.
      expect(t.text.toLowerCase(), 'the no-custody promise is still in English on a Filipino money screen')
        .toMatch(/hindi hinahawakan|direkta/);
    } finally { await ctx.close(); }
  });

  test('P-TREMOR / P-ONEHANDED · every money control clears 44px at 390', async ({ browser }) => {
    // Gloves, a tremor, or a phone held one-handed on a jeepney all fail the same way: a target too
    // small to hit. This is the money form, so a mis-tap is a mis-declared payment.
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const page = await ctx.newPage();
    try {
      await signIn(page, CLIENT);
      await openServices(page);
      const r = await page.evaluate((rid) => {
        (window as any).svcConfirmPay(rid, 1500);
        const slot = document.getElementById('svc-pay-' + rid)!;
        // browser_resize lies — read the real innerWidth before trusting any mobile claim.
        /* Measure only what is actually on screen, but REVEAL the conditional fields first rather than
           excusing them. The GCash reference and the variance reason start display:none, so a naive
           sweep reads them as 0px and reports a tap-target failure on controls nobody can tap yet — my
           instrument, not the page. Skipping them entirely would be the opposite error: they are real
           inputs the moment the user picks GCash or the guard asks why. So: open both, then measure. */
        const m = document.getElementById('svc-pay-method-' + rid) as HTMLSelectElement;
        m.value = 'gcash'; m.dispatchEvent(new Event('change', { bubbles: true }));
        (document.getElementById('svc-pay-whywrap-' + rid) as HTMLElement).style.display = '';

        const small: string[] = [];
        slot.querySelectorAll('input,select,button').forEach(el => {
          const b = (el as HTMLElement).getBoundingClientRect();
          if (b.width === 0 && b.height === 0) return;          // genuinely not rendered
          if (b.height < 44) small.push((el.id || el.tagName) + '=' + Math.round(b.height) + 'px');
        });
        return { width: window.innerWidth, small, shown: slot.querySelectorAll('input,select,button').length,
                 overflow: slot.scrollWidth > document.documentElement.clientWidth };
      }, REQ);
      expect(r.width, 'the viewport is not actually 390 — the assertion below would be measuring a '
        + 'different device than it claims').toBeLessThanOrEqual(430);
      expect(r.small, `money controls under the 44px tap floor: ${r.small.join(', ')}`).toEqual([]);
      expect(r.overflow, 'the money form overflows a 390px screen sideways').toBe(false);
    } finally { await ctx.close(); }
  });

  test('P-SCREENREADER · every money field has a name, and the amount is not label-less', async ({ page }) => {
    await signIn(page, CLIENT);
    await openServices(page);
    const r = await page.evaluate((rid) => {
      (window as any).svcConfirmPay(rid, 1500);
      const slot = document.getElementById('svc-pay-' + rid)!;
      const nameless: string[] = [];
      slot.querySelectorAll('input,select,button').forEach(el => {
        const id = el.id;
        const hasLabel = !!(id && slot.querySelector('label[for="' + id + '"]'));
        const aria = el.getAttribute('aria-label') || '';
        const text = (el as HTMLElement).innerText || '';
        if (!hasLabel && !aria.trim() && !text.trim()) nameless.push(id || el.tagName);
      });
      return nameless;
    }, REQ);
    expect(r, `money controls a screen reader cannot name: ${r.join(', ')} — someone is being asked to `
      + 'confirm a payment into an unlabelled box').toEqual([]);
  });

  test('P-IMPULSIVE · a double-tapped Confirm mints exactly one commission', async ({ page, browser }) => {
    /* The human form of the idempotency test. A slow connection plus an unresponsive-looking button is
       precisely when people press twice, and the cost here is the provider being billed twice.
       Its OWN job, because this cell settles what it touches. */
    const own = await stageCompleted(browser, 'impulsive job');
    await signIn(page, CLIENT);
    await openServices(page);
    await page.evaluate((rid) => {
      (window as any).svcConfirmPay(rid, 1500);
      (document.getElementById('svc-pay-amt-' + rid) as HTMLInputElement).value = '1500';
      // The method no longer defaults to Cash: a money form must not put words in the client's mouth,
      // so an explicit choice is required and this cell has to make one before it can double-tap.
      (document.getElementById('svc-pay-method-' + rid) as HTMLSelectElement).value = 'cash';
      const go = document.getElementById('svc-pay-go-' + rid) as HTMLButtonElement;
      go.click(); go.click();          // the double tap, with no wait between
    }, own);
    await page.waitForTimeout(4000);

    const admin = adminClient();
    const { data: pays } = await admin.from('service_payments').select('id').eq('request_id', own);
    const { data: led } = await admin.from('service_credit_ledger').select('entry_type').eq('ref_id', own);
    expect(pays?.length ?? 0, 'a double tap wrote TWO payment records for one job').toBe(1);
    expect((led || []).filter((r: any) => r.entry_type === 'commission').length,
      'a double tap billed the provider TWICE for one job').toBe(1);
    expect((led || []).filter((r: any) => r.entry_type === 'cashback').length,
      'a double tap minted cashback twice — free credits for an impatient thumb').toBe(1);
  });

  test('P-OLDER / P-SUNLIGHT · the money form survives 200% zoom without losing the button', async ({ browser }) => {
    // Presbyopia and outdoor glare both end at the same place: text scaled up. If the confirm button
    // falls outside the viewport or the fields overlap, the task cannot be completed at all.
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    try {
      await signIn(page, CLIENT);
      await openServices(page);
      const r = await page.evaluate((rid) => {
        document.documentElement.style.fontSize = '200%';
        (window as any).svcConfirmPay(rid, 1500);
        const go = document.getElementById('svc-pay-go-' + rid) as HTMLElement;
        const b = go.getBoundingClientRect();
        const wide = document.documentElement.scrollWidth > window.innerWidth + 2;
        document.documentElement.style.fontSize = '';
        return { visible: b.width > 0 && b.height > 0, wide };
      }, REQ);
      expect(r.visible, 'at 200% text the Confirm button has no box at all — the task is unfinishable')
        .toBe(true);
      expect(r.wide, 'at 200% text the page scrolls sideways, so the money form runs off the screen')
        .toBe(false);
    } finally { await ctx.close(); }
  });

  test('P-DATACAP · opening the money screen downloads no map', async ({ page }) => {
    // ₱20 of load left. The money screen must not pull 800KB of MapLibre for a form with four fields.
    await signIn(page, CLIENT);
    const heavy: string[] = [];
    page.on('request', r => { if (/maplibre|\.pbf|tiles?\//i.test(r.url())) heavy.push(r.url()); });
    await openServices(page);
    await page.evaluate((rid) => (window as any).svcConfirmPay(rid, 1500), REQ);
    await page.waitForTimeout(2500);
    expect(heavy, `confirming a payment fetched map assets: ${heavy.slice(0, 3).join(', ')}`).toEqual([]);
  });
});
