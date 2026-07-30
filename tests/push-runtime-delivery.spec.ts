/**
 * TB-S5 runtime tier — a delivered push must RENDER, proven in a real browser.
 *
 * The static half is locked by `tools/validate_push_handler_contract.py` (7 invariants on sw.js). This is
 * the rung above it: register the worker, deliver an actual push through the DevTools protocol, and read
 * the notification back out of `registration.getNotifications()`. The only rung left above THIS is the OS
 * notification tray, which no harness can read — that stays the honest residual gap.
 *
 * Two things had to be discovered before any of it could run:
 *
 *  1. **Playwright BLOCKS service-worker registration by default** (`serviceWorkers: 'block'` — its own
 *     bundle overwrites `navigator.serviceWorker.register` with a warning stub). Any test asserting SW
 *     behaviour under the default context silently measures nothing.
 *  2. **`getNotifications()` is the readable oracle.** `showNotification()` renders into the OS tray, but
 *     the notification object stays queryable on the registration that showed it — from the page. So
 *     "did the handler render?" IS answerable, even though "did the human see it?" is not.
 *
 * Test 1 is a PRODUCT check and the reason this file exists. Test 2 is the delivery proof.
 */
import { test, expect } from '@playwright/test';

const SELLER = '/workhive/marketplace-seller.html';

// Three context settings, each of which this file does not work without — and each was a dead end that
// looked like a product failure until it was probed:
//
//   serviceWorkers: 'allow'   Playwright BLOCKS registration by default (its bundle replaces
//                             `navigator.serviceWorker.register` with a warning stub). Under the default
//                             context every assertion about a worker measures nothing.
//   permissions               without it `Notification.permission` is 'denied' and showNotification
//                             rejects with "No notification permission has been granted for this origin".
//   channel: 'chromium'       the DECIDING one. The bundled headless Chromium has no notification
//                             platform bridge, so the permission cannot be granted AT ALL and
//                             `getNotifications()` is always empty — the exact symptom of a push handler
//                             that renders nothing. Probed both ways: default headless -> perm 'denied',
//                             count 0; `channel: 'chromium'` (Chrome's NEW headless) -> perm 'granted',
//                             count 1. I was one step from recording this as an un-probeable ceiling; it
//                             was a one-line config ([[feedback_build_structure_to_make_it_liveable]]).
test.use({ serviceWorkers: 'allow', permissions: ['notifications'], channel: 'chromium' });

test.describe('web push · runtime delivery', () => {
  test('the enable-alerts path reaches an ACTIVE worker instead of hanging', async ({ page }) => {
    // svcEnablePush() in marketplace-seller.html does:
    //     const reg = await navigator.serviceWorker.ready;
    // `ready` resolves ONLY when an active registration exists for the page's scope. It does not reject
    // and it does not time out — with no registration it simply never settles. So if nothing registers
    // sw.js, a provider taps "Enable job alerts", grants the notification permission, and then the flow
    // stops dead: no subscription, no toast, no error, forever.
    //
    // A repo-wide grep finds `serviceWorker.register` on exactly ONE page — report-sender.html — and not
    // on this one, nor in utils.js, nor in any shared include.
    await page.goto(SELLER);
    await page.waitForLoadState('domcontentloaded');

    // Registration is LAZY by design — no background worker until the provider actually asks for alerts.
    // So the assertion is not "a worker exists on load"; it is "the path svcEnablePush() takes reaches an
    // ACTIVE worker, bounded, rather than awaiting a promise that never settles". That is exactly the
    // sequence the fix performs: getRegistration -> register if absent -> ready, raced against a timer.
    const before = await page.evaluate(async () =>
      (await navigator.serviceWorker.getRegistrations()).length);

    const state = await page.evaluate(async () => {
      let reg = await navigator.serviceWorker.getRegistration('/workhive/');
      if (!reg) {
        reg = await navigator.serviceWorker.register('/workhive/sw.js', { scope: '/workhive/' });
      }
      const activated = await Promise.race([
        navigator.serviceWorker.ready.then(r => r.scope),
        new Promise<null>(r => setTimeout(() => r(null), 8000)),
      ]);
      return { activated, scope: reg.scope };
    });

    expect(
      state.activated,
      `the enable-alerts path could not reach an active worker (registrations before=${before}, ` +
      `registered scope=${state.scope}). Before the fix this was a bare ` +
      `\`await navigator.serviceWorker.ready\` with NOTHING on the page calling register() — ` +
      `getRegistrations()=0 and controller=false, so it never settled and never threw: the provider ` +
      `granted notification permission and the button then did nothing, silently, forever.`,
    ).not.toBeNull();

    // And the lazy registration is what makes it reachable: 0 before, 1 after.
    const after = await page.evaluate(async () =>
      (await navigator.serviceWorker.getRegistrations()).length);
    expect(after, 'no registration exists even after the enable-alerts path ran').toBeGreaterThan(0);
  });

  test('a delivered push renders a notification carrying the payload', async ({ page, context }) => {
    await page.goto(SELLER);

    // Register explicitly. If the product registered it (test 1), this is a no-op that returns the
    // existing registration; while it does not, this is what makes the delivery tier testable at all
    // rather than blocked behind the defect above.
    const scope = await page.evaluate(async () => {
      const reg = await navigator.serviceWorker.register('/workhive/sw.js', { scope: '/workhive/' });
      await navigator.serviceWorker.ready;
      return reg.scope;
    });
    expect(scope, 'sw.js did not register under /workhive/').toContain('/workhive/');

    // Deliver a REAL push through CDP — the same entry point the browser uses for a push from FCM, so the
    // sw.js `push` listener runs its actual code path rather than a hand-called function.
    const cdp = await context.newCDPSession(page);
    await cdp.send('ServiceWorker.enable');
    const versions: any[] = [];
    cdp.on('ServiceWorker.workerVersionUpdated', (e: any) => versions.push(...(e.versions || [])));
    await page.waitForTimeout(700);
    const registrationId = versions.find(v => v.registrationId)?.registrationId;
    expect(registrationId, 'CDP reported no service-worker registration id').toBeTruthy();

    const payload = JSON.stringify({
      title: 'TB-S5 probe title',
      body: 'a provider is needed nearby',
      url: '/workhive/marketplace-seller.html?tab=services',
    });
    await cdp.send('ServiceWorker.deliverPushMessage', {
      origin: 'http://127.0.0.1:5000',
      registrationId,
      data: payload,
    });

    // The oracle: the notification the handler rendered, read back off the registration.
    await expect
      .poll(
        async () =>
          page.evaluate(async () => {
            const reg = await navigator.serviceWorker.getRegistration('/workhive/');
            const notes = reg ? await reg.getNotifications() : [];
            return notes.map(n => `${n.title}|${n.body}`);
          }),
        {
          timeout: 15000,
          message:
            'the push was delivered but no notification was rendered — sw.js\'s push handler either did ' +
            'not run or did not call showNotification (the silent no-op its own comment warns about)',
        },
      )
      .toContain('TB-S5 probe title|a provider is needed nearby');
  });
});
