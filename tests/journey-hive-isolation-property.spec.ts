/**
 * journey-hive-isolation-property.spec.ts — P1 roadmap 2026-05-26
 *
 * Property test: for every load-bearing page, log in as Hive A,
 * snapshot the rendered identifiers, then switch to Hive B and assert
 * none of Hive A's identifiers appear on the page.
 *
 * This is the cheapest possible cross-hive leak detector. It cannot
 * catch leaks that hide behind aggregate counts, but it WILL catch:
 *   - asset_id, work_order_id, logbook_entry_id, etc. rendered into DOM
 *   - photo URLs containing Hive A's storage prefix
 *   - tooltip / hidden field data carrying foreign ids
 *
 * Two-hive Playwright fixtures are needed; if WH_TEST_HIVE_A and
 * WH_TEST_HIVE_B are not set, the suite skips with a clear message.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';

const HIVE_A = process.env.WH_TEST_HIVE_A || '';
const HIVE_B = process.env.WH_TEST_HIVE_B || '';
const TWO_HIVES = Boolean(HIVE_A && HIVE_B && HIVE_A !== HIVE_B);

// Load-bearing pages — every one renders hive-scoped data and is reachable
// in <2 clicks from the home stack. Add new pages here when they ship.
const PAGES = [
  'logbook.html',
  'inventory.html',
  'pm-scheduler.html',
  'hive.html',
  'analytics.html',
  'analytics-report.html',
  'community.html',
  'predictive.html',
  'asset-hub.html',
  'alert-hub.html',
  'achievements.html',
  'dayplanner.html',
  'skillmatrix.html',
  'project-manager.html',
  'audit-log.html',
];

// What "identifier" means: any 8+ char hex/UUID-shaped string rendered in
// the document body. Hive A's set, then Hive B's set. Overlap is suspicious.
const ID_RE = /[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}/gi;

async function captureIds(whPage: any, slug: string): Promise<Set<string>> {
  await whPage.goto(`/workhive/${slug}`);
  await waitForPageReady(whPage);
  // Give realtime + first hydration a beat.
  await whPage.waitForTimeout(2500);
  const text = await whPage.evaluate(() => document.body.innerText + ' ' + document.body.innerHTML);
  return new Set((text.match(ID_RE) || []).map((s: string) => s.toLowerCase()));
}

async function switchHive(whPage: any, hiveId: string) {
  await whPage.evaluate((h: string) => {
    localStorage.setItem('wh_active_hive_id', h);
    localStorage.setItem('wh_hive_id', h);
  }, hiveId);
}

test.describe('Hive isolation property (cross-hive ID leak detector)', () => {

  test.skip(!TWO_HIVES, 'Set WH_TEST_HIVE_A + WH_TEST_HIVE_B env vars to run.');

  for (const slug of PAGES) {
    test(`hive_isolation: ${slug} does not leak Hive A IDs after switching to Hive B`, async ({ whPage }) => {
      // Capture Hive A identifiers.
      await switchHive(whPage, HIVE_A);
      const idsA = await captureIds(whPage, slug);
      // Many pages will show 0 ids in the empty-state — that's fine, the
      // assertion below still holds (empty ∩ anything = empty).

      // Switch to Hive B and re-render the same page.
      await switchHive(whPage, HIVE_B);
      const idsB = await captureIds(whPage, slug);

      // Overlap is the property failure.
      const leaks = Array.from(idsA).filter((id) => idsB.has(id));
      if (leaks.length > 0) {
        console.error(`[hive_isolation] ${slug} leaked ${leaks.length} ids:`, leaks.slice(0, 5));
      }
      expect(leaks, `${slug}: ${leaks.length} Hive A ids visible while in Hive B`).toEqual([]);
    });
  }
});
