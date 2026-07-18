/**
 * alert-hub.html triage — interaction-lock test (ASSET_ALERT_SHIFT_DEEP_ARC F3/F40).
 *
 * Locks the worst-first triage contract that the Asset/Alert/Shift arc restored:
 *   1. WORST-FIRST SORT (F3): the feed is ordered by severity (critical → high → medium →
 *      low → info), NOT newest-first. A stale critical must not sit below a fresh info alert.
 *      Regression guard against the old `all.sort((a,b)=>time)` pure-recency sort that buried
 *      criticals and made the "clear the top of the feed" verdict/CTA dishonest.
 *   2. HONEST EMPTY (F40): filtering to a KIND with zero matches while other alerts exist must
 *      say "None under this filter", NOT "All clear" (which is only true unfiltered).
 *
 * Reads the live feed as the seeded supervisor. Skips a sub-assertion cleanly when the seed
 * has too few alerts to prove the property (never a false fail on thin data).
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';

const SEV_RANK: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };

test.describe('alert-hub.html triage (worst-first + honest empty)', () => {
  test('feed is sorted worst-first by severity', async ({ whPage }) => {
    await whPage.goto('/workhive/alert-hub.html');
    await waitForPageReady(whPage);
    await expect(whPage.locator('#feed .alert').first()).toBeVisible({ timeout: 12000 });

    const sevs = await whPage.locator('#feed .alert .alert-tag').allTextContents();
    const ranks = sevs.map(s => SEV_RANK[s.trim().toLowerCase()] ?? 2);

    // Need ≥2 rows spanning ≥2 severity bands to prove ordering; otherwise skip (thin seed).
    test.skip(ranks.length < 2 || new Set(ranks).size < 2,
      'need ≥2 alerts across ≥2 severity bands to prove worst-first');

    for (let i = 1; i < ranks.length; i++) {
      expect(ranks[i], `feed not worst-first at row ${i}: [${sevs.map(s => s.trim()).join(', ')}]`)
        .toBeGreaterThanOrEqual(ranks[i - 1]);
    }
  });

  test('kind filter with zero matches shows an honest empty state (not "All clear")', async ({ whPage }) => {
    await whPage.goto('/workhive/alert-hub.html');
    await waitForPageReady(whPage);
    await expect(whPage.locator('#feed .alert').first()).toBeVisible({ timeout: 12000 });

    // Find a kind chip whose count badge is 0 while the feed has alerts under other kinds.
    const emptyKind = await whPage.evaluate(() => {
      const chips = Array.from(document.querySelectorAll('[data-kind]')) as HTMLElement[];
      for (const c of chips) {
        const kind = c.getAttribute('data-kind');
        if (!kind || kind === 'all') continue;
        // count badge is the last numeric text in the chip
        const n = parseInt((c.textContent || '').replace(/[^0-9]/g, ''), 10);
        if (n === 0) return kind;
      }
      return null;
    });
    test.skip(!emptyKind, 'no zero-count kind chip in this seed to prove honest-empty');

    await whPage.locator(`[data-kind="${emptyKind}"]`).click();
    const empty = whPage.locator('#empty');
    await expect(empty).toBeVisible();
    const title = (await empty.locator('.empty-title').textContent() || '').toLowerCase();
    const sub = (await empty.locator('.empty-sub').textContent() || '').toLowerCase();
    // Must NOT claim all-clear when other alerts exist under other filters.
    expect(title.includes('all clear'),
      `filtered empty state dishonestly says "All clear": "${title}" / "${sub}"`).toBeFalsy();
    expect(sub.includes('other filter') || title.includes('under this filter'),
      `filtered empty state should point to other filters: "${title}" / "${sub}"`).toBeTruthy();
  });
});
