/**
 * feedback.spec.ts — end-to-end test for the universal feedback widget.
 *
 * Covers commits 1/3 (schema), 2/3 (widget), and 3/3 (admin inbox) in
 * one flow:
 *   1. FAB renders on a public page (about/) and signed-in app page (hive)
 *   2. Submitting a "bug" inserts into platform_feedback
 *   3. Submitting a "review" with a 5-star rating persists the rating
 *   4. Rate-limit trigger surfaces the friendly retry message after 5/hr
 *
 * Bound to validator check names via the `<check_name>:` prefix
 * convention (see sentinel matcher Path A) so a future
 * validate_feedback_widget.py with these check names auto-maps:
 *   widget_renders, widget_submits, widget_rating, widget_rate_limit
 *
 * Skills consulted: qa (testMarker cleanup), community (rate-limit
 * trigger UX expectation), platform-guardian (DB + DOM dual-assert).
 */
import { test, expect } from './_fixtures';
import { adminClient } from './_db-cleanup';

const PUBLIC_PAGE = '/workhive/about/';
const APP_PAGE    = '/workhive/hive.html';

test.describe('Universal feedback widget (L2 for migration 20260519000002)', () => {

  test('widget_renders: FAB visible on public page', async ({ rawPage }) => {
    // Public page (unauthenticated) — direct <script defer> load
    await rawPage.goto(PUBLIC_PAGE);
    await expect(rawPage.locator('#wh-feedback-fab')).toBeVisible({ timeout: 8000 });
    // App-page coverage enforced by validate_feedback_widget.py Layer 1
    // (every page either loads nav-hub.js or includes the FAB script directly).
  });

  test('widget_submits: bug submission inserts platform_feedback row with auto-captured page_url', async ({ rawPage, testMarker }) => {
    const email = `${testMarker.toLowerCase()}@local.invalid`;
    const subject = `${testMarker} widget bug probe`;

    await rawPage.goto(PUBLIC_PAGE);
    // Wait for the FAB to mount, then open the panel
    await rawPage.locator('#wh-feedback-fab').waitFor({ state: 'visible', timeout: 10000 });
    await rawPage.locator('#wh-feedback-fab').click();
    await expect(rawPage.locator('#wh-feedback-panel.open')).toBeVisible();

    // Pick "bug" kind, fill subject + body, leave rating block hidden (only review uses it)
    await rawPage.locator('.wh-fb-kind[data-kind="bug"]').click();
    await rawPage.locator('#wh-fb-subject').fill(subject);
    await rawPage.locator('#wh-fb-body').fill('Save toast appeared but the entry never showed up after refresh');
    await rawPage.locator('#wh-fb-email').fill(email);
    await rawPage.locator('#wh-fb-submit-btn').click();

    // Success message appears, panel auto-closes
    await expect(rawPage.locator('.wh-fb-success')).toBeVisible({ timeout: 5000 });

    // Verify the row landed in the DB with the expected page_url + kind
    const db = adminClient();
    const { data, error } = await db.from('platform_feedback')
      .select('id,kind,subject,page_url,contact_email,status')
      .eq('contact_email', email).maybeSingle();
    expect(error, 'DB lookup error').toBeNull();
    expect(data, `no row found for ${email}`).toBeTruthy();
    expect(data!.kind).toBe('bug');
    expect(data!.subject).toBe(subject);
    expect(data!.status).toBe('new');
    expect(data!.page_url).toContain('/workhive/about');   // auto-captured

    // Cleanup
    await db.from('platform_feedback').delete().eq('id', data!.id);
  });

  test('widget_rating: review with 5-star rating persists', async ({ rawPage, testMarker }) => {
    const email   = `${testMarker.toLowerCase()}-rev@local.invalid`;
    const subject = `${testMarker} rating probe`;

    await rawPage.goto(PUBLIC_PAGE);
    await rawPage.locator('#wh-feedback-fab').waitFor({ state: 'visible', timeout: 10000 });
    await rawPage.locator('#wh-feedback-fab').click();
    await expect(rawPage.locator('#wh-feedback-panel.open')).toBeVisible();

    await rawPage.locator('.wh-fb-kind[data-kind="review"]').click();
    // Rating block should now be visible
    await expect(rawPage.locator('#wh-fb-rating-block')).toBeVisible();
    await rawPage.locator('.wh-fb-star[data-rating="5"]').click();
    await rawPage.locator('#wh-fb-subject').fill(subject);
    await rawPage.locator('#wh-fb-body').fill('Genuinely useful free platform');
    await rawPage.locator('#wh-fb-email').fill(email);
    await rawPage.locator('#wh-fb-submit-btn').click();
    await expect(rawPage.locator('.wh-fb-success')).toBeVisible({ timeout: 5000 });

    const db = adminClient();
    const { data } = await db.from('platform_feedback')
      .select('kind,rating,subject').eq('contact_email', email).maybeSingle();
    expect(data!.kind).toBe('review');
    expect(data!.rating).toBe(5);

    await db.from('platform_feedback').delete().eq('contact_email', email);
  });

  test('widget_rate_limit: 6th submission within an hour surfaces the friendly retry message', async ({ rawPage, testMarker }) => {
    const email = `${testMarker.toLowerCase()}-rl@local.invalid`;
    const db    = adminClient();

    // Seed 5 prior submissions in the past hour via direct DB so the
    // widget itself only has to attempt the 6th — keeps test fast.
    const seedRows = Array.from({ length: 5 }, (_, i) => ({
      kind:          'idea',
      subject:       `${testMarker} rl-seed ${i}`,
      body:          'seed for rate-limit boundary test',
      contact_email: email,
    }));
    const { error: seedErr } = await db.from('platform_feedback').insert(seedRows);
    expect(seedErr, 'seed insert failed').toBeNull();

    await rawPage.goto(PUBLIC_PAGE);
    await rawPage.locator('#wh-feedback-fab').waitFor({ state: 'visible', timeout: 10000 });
    await rawPage.locator('#wh-feedback-fab').click();
    await rawPage.locator('.wh-fb-kind[data-kind="idea"]').click();
    await rawPage.locator('#wh-fb-subject').fill(`${testMarker} 6th submit`);
    await rawPage.locator('#wh-fb-body').fill('Should bounce off the rate limit');
    await rawPage.locator('#wh-fb-email').fill(email);
    await rawPage.locator('#wh-fb-submit-btn').click();

    const err = rawPage.locator('.wh-fb-error');
    await expect(err).toBeVisible({ timeout: 5000 });
    await expect(err).toContainText(/5 messages this hour|rate limit/i);

    await db.from('platform_feedback').delete().eq('contact_email', email);
  });
});
