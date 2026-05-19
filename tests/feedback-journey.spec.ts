/**
 * feedback-journey.spec.ts — Visual + behavioral tour of the universal
 * feedback widget across the platform.
 *
 * Plays the role of "you (admin) clicking around to spot-check the FAB
 * on real pages." Tours public + app surfaces, on each one:
 *   - Asserts the FAB is visible (Layer 2 reach contract)
 *   - Captures a viewport screenshot to .tmp/feedback-journey/
 *   - On a representative subset, opens the panel + picks a kind +
 *     verifies the form renders + closes (no submission)
 *
 * Screenshots are written for human review when needed but the test
 * does NOT depend on visual diffs (no baseline drift to maintain).
 *
 * Plus a true end-to-end submit-and-verify against an APP page to
 * prove the widget works behind a signin flow too — closes the gap
 * left by feedback.spec.ts which only covers public pages.
 *
 * Skills consulted: qa-tester (rawPage + whPage split), mobile-maestro
 * (FAB clears safe-area), platform-guardian (DB+DOM dual-assert).
 */
import { test, expect } from './_fixtures';
import { adminClient } from './_db-cleanup';
import { ensureSeeded } from './_seed-helper';
import * as path from 'path';
import * as fs from 'fs';

const SHOT_DIR = path.join('.tmp', 'feedback-journey');

// Public surfaces (no auth) — use rawPage. Order: landing + content
// hub + 3 representative articles + the new public roadmap.
const PUBLIC_TOUR = [
  { slug: 'index',         url: '/workhive/index.html',                              label: 'landing' },
  { slug: 'about',         url: '/workhive/about/',                                  label: 'about' },
  { slug: 'learn',         url: '/workhive/learn/',                                  label: 'learn hub' },
  { slug: 'learn-oee',     url: '/workhive/learn/what-is-oee-how-to-calculate/',     label: 'article: OEE' },
  { slug: 'privacy',       url: '/workhive/privacy-policy/',                         label: 'privacy' },
  { slug: 'terms',         url: '/workhive/terms-of-service/',                       label: 'terms' },
  { slug: 'roadmap',       url: '/workhive/feedback/',                               label: 'public roadmap' },
];

// Signed-in surfaces (whPage) — the 4 worker-critical pages the user
// actually opens daily. If the FAB renders on these too, coverage is real.
const APP_TOUR = [
  { slug: 'hive',       url: '/workhive/hive.html',       label: 'hive board' },
  { slug: 'logbook',    url: '/workhive/logbook.html',    label: 'logbook' },
  { slug: 'inventory',  url: '/workhive/inventory.html',  label: 'inventory' },
  { slug: 'pm',         url: '/workhive/pm-scheduler.html', label: 'PM scheduler' },
];

test.beforeAll(async () => {
  await ensureSeeded();
  if (!fs.existsSync(SHOT_DIR)) fs.mkdirSync(SHOT_DIR, { recursive: true });
});

test.describe('Universal feedback widget — visual journey', () => {

  for (const stop of PUBLIC_TOUR) {
    test(`fab_journey_public: FAB renders on ${stop.label}`, async ({ rawPage }) => {
      await rawPage.goto(stop.url, { waitUntil: 'domcontentloaded' });
      // FAB lazy-loads — wait up to 8s for it to mount
      const fab = rawPage.locator('#wh-feedback-fab');
      await fab.waitFor({ state: 'visible', timeout: 8000 });
      // Capture a viewport screenshot for human spot-check
      await rawPage.screenshot({
        path: path.join(SHOT_DIR, `public-${stop.slug}.png`),
        fullPage: false,
      });
      // FAB position check — must be in the bottom-right quadrant of the viewport
      const box = await fab.boundingBox();
      const vp  = rawPage.viewportSize() || { width: 1280, height: 720 };
      expect(box, 'FAB has no bounding box').not.toBeNull();
      expect(box!.x + box!.width / 2,
        `FAB center should be in right half of viewport on ${stop.label}`)
        .toBeGreaterThan(vp.width / 2);
      expect(box!.y + box!.height / 2,
        `FAB center should be in bottom half of viewport on ${stop.label}`)
        .toBeGreaterThan(vp.height / 2);
    });
  }

  for (const stop of APP_TOUR) {
    test(`fab_journey_app: FAB renders on signed-in ${stop.label}`, async ({ whPage }) => {
      await whPage.goto(stop.url, { waitUntil: 'domcontentloaded' });
      // App pages: nav-hub.js loads, then lazy-loads wh-feedback-fab.js
      // async via createElement('script'). On slow runs this chain can
      // exceed the default 8s expect timeout — bump to 20s explicitly.
      const fab = whPage.locator('#wh-feedback-fab');
      await fab.waitFor({ state: 'visible', timeout: 20000 });
      await whPage.screenshot({
        path: path.join(SHOT_DIR, `app-${stop.slug}.png`),
        fullPage: false,
      });
    });
  }

  test('fab_journey_panel_opens: clicking FAB opens panel + kind chips render', async ({ rawPage }) => {
    await rawPage.goto('/workhive/about/');
    await rawPage.locator('#wh-feedback-fab').waitFor({ state: 'visible', timeout: 8000 });
    await rawPage.locator('#wh-feedback-fab').click();
    await expect(rawPage.locator('#wh-feedback-panel.open')).toBeVisible({ timeout: 4000 });
    // All 5 kind chips present
    for (const kind of ['bug', 'idea', 'question', 'review', 'praise']) {
      await expect(rawPage.locator(`.wh-fb-kind[data-kind="${kind}"]`)).toBeVisible();
    }
    // Closing via × works
    await rawPage.locator('.wh-fb-close').click();
    await expect(rawPage.locator('#wh-feedback-panel.open')).not.toBeVisible();
    await rawPage.screenshot({
      path: path.join(SHOT_DIR, 'panel-after-close.png'),
      fullPage: false,
    });
  });

  test('fab_journey_signed_in_submit: signed-in user can submit feedback from hive.html', async ({ whPage, testMarker }) => {
    // Close the gap left by feedback.spec.ts (public-page-only) — prove
    // the widget works on a signed-in app page too. Important because
    // app pages have heavier JS + auth context + nav-hub lazy-load
    // timing that could break the FAB.
    const email   = `${testMarker.toLowerCase()}@journey.invalid`;
    const subject = `${testMarker} signed-in submit probe`;

    await whPage.goto('/workhive/hive.html');
    await whPage.locator('#wh-feedback-fab').waitFor({ state: 'visible', timeout: 12000 });
    await whPage.locator('#wh-feedback-fab').click();
    await expect(whPage.locator('#wh-feedback-panel.open')).toBeVisible({ timeout: 5000 });

    await whPage.locator('.wh-fb-kind[data-kind="praise"]').click();
    await whPage.locator('#wh-fb-subject').fill(subject);
    await whPage.locator('#wh-fb-body').fill('Submitted from signed-in hive.html — journey spec verifying signed-in submission path.');
    await whPage.locator('#wh-fb-email').fill(email);
    await whPage.locator('#wh-fb-submit-btn').click();

    await expect(whPage.locator('.wh-fb-success')).toBeVisible({ timeout: 5000 });

    // DB-level verification — auto-captured worker_name should be the
    // seeded test identity (Pablo Aguilar) and page_url should be the
    // hive page, NOT redirected to signin/landing.
    const db = adminClient();
    const { data } = await db.from('platform_feedback')
      .select('kind,subject,page_url,worker_name,hive_id')
      .eq('contact_email', email).maybeSingle();
    expect(data, `submission not found for ${email}`).toBeTruthy();
    expect(data!.kind).toBe('praise');
    expect(data!.subject).toBe(subject);
    expect(data!.page_url).toContain('/workhive/hive.html');
    // worker_name should be auto-pulled from localStorage wh_last_worker
    expect(data!.worker_name, 'signed-in submitter should be tagged with worker_name').toBeTruthy();

    await db.from('platform_feedback').delete().eq('contact_email', email);
  });
});
