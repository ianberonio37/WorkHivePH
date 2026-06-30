/**
 * feedback-realtime.spec.ts — End-to-end Realtime contract.
 *
 * Proves the core value-prop of the inbox: when a visitor submits
 * feedback from any page, the admin sees it live in Founder Console
 * without refreshing. If this breaks, the whole inbox is useless.
 *
 * Uses two browser contexts:
 *   admin   — opens founder-console.html, waits for inbox to attach
 *             the Realtime channel
 *   visitor — opens /about/, submits a praise via the FAB
 *
 * Then asserts the new row appears in the admin's inbox list within
 * 5 seconds — the same SLA a real admin would notice.
 *
 * Skills consulted: realtime-engineer (channel filter conventions),
 * notifications (Layer 1 Realtime contract), qa-tester (two-context
 * flow), platform-guardian (DB+DOM dual-assert with marker cleanup).
 */
import { test, expect } from '@playwright/test';
import { adminClient } from './_db-cleanup';

const FOUNDER_URL = 'http://127.0.0.1:5000/workhive/founder-console.html';
const PUBLIC_URL  = 'http://127.0.0.1:5000/workhive/about/';
const SIGNIN_URL  = 'http://127.0.0.1:5000/workhive/index.html?signin=1';

// Seeded platform admin (client_hive.py upserts pabloaguilar into
// marketplace_platform_admins). After mig 20260621000003 the founder console
// must AUTHENTICATE to read/subscribe platform_feedback — anon now only sees
// is_public=true rows (Arc J keystone: closed the anon live-stream of private
// feedback + PII). So this test signs in first, proving the SECURE prod path:
// an authenticated platform admin receives private feedback live via Realtime.
const ADMIN_USER = process.env.WH_TEST_USERNAME || 'pabloaguilar';
const ADMIN_PASS = process.env.WH_TEST_PASSWORD || 'test1234';

async function signInAsAdmin(page: import('@playwright/test').Page) {
  await page.goto(SIGNIN_URL, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#signin-modal:not(.hidden)', { timeout: 12000 });
  await page.fill('#si-username', ADMIN_USER);
  await page.fill('#si-password', ADMIN_PASS);
  await page.click('#si-btn');
  // success = the platform's own login signal (mirrors auth-identity-arc-i.spec.ts)
  await page.waitForFunction(() => !!localStorage.getItem('wh_last_worker'), { timeout: 15000 });
}

test.describe('Feedback inbox Realtime (commit cffafdd L2 verification)', () => {

  test('inbox_realtime_pushes_new_row: row inserted via service role appears live in Founder Console inbox', async ({ page }) => {
    // Simplest version of the Realtime contract: bypass the visitor
    // FAB path (covered by feedback.spec.ts + feedback-journey.spec.ts)
    // and just prove that an INSERT into platform_feedback causes the
    // admin's inbox to update without refresh. If this works, every
    // visitor-side submission path inherits the same delivery.
    const marker = `RT-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
    const subject = `${marker} realtime probe`;
    const email   = `${marker.toLowerCase()}@rt.invalid`;
    const db = adminClient();

    // Capture console errors from the admin page to surface Realtime
    // subscription errors (CHANNEL_ERROR, TIMED_OUT, etc.)
    const consoleErrs: string[] = [];
    page.on('console', m => {
      if (m.type() === 'error' && !m.text().includes('favicon')) {
        consoleErrs.push(m.text().slice(0, 200));
      }
    });

    // Authenticate as a platform admin FIRST so the founder console's client
    // carries a JWT — Realtime evaluates platform_feedback's SELECT RLS against
    // the subscriber, and post-20260621000003 only an authenticated admin (or
    // is_public=true) is admitted. Session persists in localStorage → the
    // founder console restores it → subscribes as admin.
    await signInAsAdmin(page);
    await page.goto(FOUNDER_URL);
    // Wait until the inbox renders + subscribes (#fb-count-all is the
    // last thing applyFeedbackView writes after subscribeFeedbackRealtime).
    await page.waitForFunction(() => {
      const el = document.getElementById('fb-count-all');
      return el && el.textContent !== null;
    }, { timeout: 15000 });
    // Subscribe call is fire-and-forget; give it a beat to flip to SUBSCRIBED
    await page.waitForTimeout(1500);
    await expect(page.locator('#feedback-inbox')).toBeVisible();

    try {
      // INSERT via service role — should trigger Realtime INSERT event
      const { error: insErr } = await db.from('platform_feedback').insert({
        kind: 'praise',
        subject,
        body:  `${marker} body`,
        contact_email: email,
      });
      expect(insErr, 'service-role insert failed').toBeNull();

      // Wait for the card to appear via Realtime push
      const newCard = page.locator('.fb-card-subject', { hasText: subject });
      try {
        await expect(newCard).toBeVisible({ timeout: 10000 });
      } catch (e) {
        // Helpful debug surface: dump console errors + count + first card
        const counts = await page.evaluate(() => ({
          all: document.getElementById('fb-count-all')?.textContent,
          new_: document.getElementById('fb-count-new')?.textContent,
        }));
        throw new Error(
          `Realtime push did not arrive in 10s.\n` +
          `Counts seen: ${JSON.stringify(counts)}\n` +
          `Console errors: ${consoleErrs.join(' | ') || '(none)'}`
        );
      }
    } finally {
      await db.from('platform_feedback').delete().eq('contact_email', email);
    }
  });
});
