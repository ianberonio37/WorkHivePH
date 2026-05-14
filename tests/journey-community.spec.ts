/**
 * journey-community.spec.ts — Community forum journey.
 * TODO (L12 debt): full flow coverage pending.
 *
 * Scenarios needed:
 *   - page loads, feed renders posts or empty state
 *   - create post: happy path, empty body blocked
 *   - reply to post
 *   - mention @worker notifies
 *   - public/private toggle
 *   - cross-hive realtime: new post appears in feed
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';

const PAGE = '/workhive/community.html';

test.describe('community.html — forum journey', () => {

  test('page loads without console errors', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);
    const serious = errors.filter(e => !e.includes('net::ERR_') && !e.includes('Failed to fetch'));
    expect(serious).toEqual([]);
  });

  test('community feed renders or shows empty state', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2500);
    // Feed or empty state must be present
    const hasFeed  = await whPage.locator('[id*="feed"], [id*="post"], .post-card').count();
    const hasEmpty = await whPage.locator('text=/no posts|be the first|nothing here/i').count();
    const hasInput = await whPage.locator('textarea, input[type="text"]').count();
    expect(
      hasFeed + hasEmpty + hasInput,
      'community page should show feed, empty state, or post input',
    ).toBeGreaterThan(0);
  });
});
