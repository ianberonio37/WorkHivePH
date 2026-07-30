/**
 * Journey-lane STATE INDUCERS — the two states SQL cannot reach.
 *
 * `TB-STATE-inducers-empty-filtered0-edge` induces `empty`, `filtered0` and `edge` at SQL altitude and
 * deliberately stops there, because the remaining two are BROWSER facts:
 *
 *   error      the listings query FAILS — induced by aborting the request at the network layer
 *   degraded   the device is offline — induced by flipping the context offline
 *
 * WHY THE `error` ONE MATTERS MOST. A failed read and an empty result are the same thing to a row count,
 * and this platform has already been bitten by exactly that confusion: `read-battery` once reported SIX
 * named page failures, all "DB empty -> empty-state (no error)", and not one was real
 * ([[feedback_a_dead_fixture_invents_page_defects]]). From the USER's side the same ambiguity is worse — a
 * seller whose query just failed must not be told "be the first to sell", because that reads as *your
 * listings are gone*.
 *
 * marketplace.html already gets this right: `_loadError` is documented at line 1064 as "P7: a FAILED
 * listings fetch must render an error state, not the first-run 'be the first to sell' CTA", the catch sets
 * it, and the render branch at ~1982 emits "Couldn't load listings". That behaviour had **no browser
 * test** — a static grep cannot prove which branch actually renders when the network fails. This is that
 * test: the fix is locked, not re-implemented.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';

const PAGE = '/workhive/marketplace.html';

test.describe('marketplace state inducers (journey lane)', () => {
  test('error: a FAILED listings fetch renders an error, never the first-run CTA', async ({ whPage }) => {
    // Abort only the listings read. Aborting everything would also break auth and the page would fail for
    // a different reason than the one under test — the state has to be induced NARROWLY or the test proves
    // something else.
    let aborted = 0;
    await whPage.route(/v_marketplace_listings_truth/, route => {
      aborted += 1;
      return route.abort('failed');
    });

    await whPage.goto(PAGE);
    await waitForPageReady(whPage);

    // POLL, do not sleep-then-assert. My first cut waited 2.5s and failed, and the product was RIGHT: the
    // page RETRIES the read (the abort count climbs 12 -> 20 -> 32) and only declares failure once the
    // retries are exhausted, at ~8s. A fixed sleep therefore measured the retry budget, not the behaviour —
    // the same mistake as judging a toast on one snapshot instead of polling for it.
    //
    // Asserting on `#listing-grid` specifically, never on `body.innerText`: both the error copy and the CTA
    // exist elsewhere in the document as other sections' markup, so a whole-page match would have gone
    // green for the wrong reason. And `innerText` hides anything in an inactive tab.
    await expect
      .poll(async () => whPage.evaluate(() => {
        const g = document.getElementById('listing-grid');
        const h = g ? g.innerHTML : '';
        return {
          error: /Couldn't load listings/i.test(h),
          cta: /be the first to sell/i.test(h),
          skeleton: /wh-cardskel|aria-busy="true"/.test(h),
        };
      }), {
        timeout: 25000,
        message: 'a failed listings fetch never surfaced an error inside #listing-grid — the grid was left ' +
          'showing a skeleton or an empty state, leaving a user unable to tell whether the marketplace is ' +
          'empty or broken',
      })
      .toMatchObject({ error: true, skeleton: false });

    expect(aborted, 'the listings request was never intercepted, so no error state was induced and this ' +
      'test would pass vacuously').toBeGreaterThan(0);

    // And the first-run CTA must NOT appear, because that is the exact misread P7 fixed: telling a seller
    // "be the first to sell" when their query merely failed reads as "your listings are gone".
    const cta = await whPage.evaluate(() =>
      /be the first to sell/i.test(document.getElementById('listing-grid')?.innerHTML || ''));
    expect(cta, 'the first-run "be the first to sell" CTA rendered on a FAILED fetch — the P7 regression')
      .toBe(false);
  });

  test('degraded: offline blocks the write and SAYS SO, rather than failing silently', async ({ whPage, context }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);

    // Induce `degraded` for real, at the context level — not by stubbing navigator.onLine, which would test
    // the stub rather than the guard.
    await context.setOffline(true);
    try {
      const before = (await whPage.locator('body').innerText()).toLowerCase();

      // whRequireOnline is the shared guard (utils.js). Drive it the way a page does and require it to
      // BOTH refuse and announce — a guard that refuses in silence is the class this platform found live
      // when a centralised offline guard failed with no toast because showToast is page-local
      // ([[feedback_banner_adoption_is_not_write_refusal]]).
      const verdict = await whPage.evaluate(() => {
        const msgs: string[] = [];
        const ok = (window as any).whRequireOnline?.('Posting a listing', (m: string) => msgs.push(String(m)));
        return { available: typeof (window as any).whRequireOnline === 'function', ok, msgs };
      });

      expect(verdict.available, 'whRequireOnline is not exposed on this page, so no write can be guarded')
        .toBe(true);
      expect(verdict.ok, 'whRequireOnline ALLOWED a write while the device was offline').toBe(false);
      expect(verdict.msgs.join(' ').toLowerCase(),
        'the offline guard refused the write but told the user NOTHING — a silent refusal is the failure ' +
        'mode, not the fix')
        .toContain('offline');
      // And it must say the write did not half-happen; that sentence is what stops a retry storm.
      expect(verdict.msgs.join(' ').toLowerCase(),
        'the offline message does not tell the user nothing was sent').toMatch(/nothing was sent|nothing is half-done/);
      void before;
    } finally {
      // Restore even if an assertion throws, or every later test in the file runs offline.
      await context.setOffline(false);
    }
  });
});
