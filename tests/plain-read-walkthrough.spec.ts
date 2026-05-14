/**
 * Plain-Read Walkthrough — visual capture for the 16-page supervisor
 * walkthrough order (see project_plain_read_contract.md memory).
 *
 * Loads each page as the seeded supervisor (Pablo Aguilar / Lucena
 * Pharmaceutical Mfg., via the whPage fixture), waits for the page
 * to settle past its initial data loads, then writes two PNGs per
 * page into .tmp/walkthrough/:
 *
 *   page-NN-<slug>-top.png   — viewport-sized hero region (verdict +
 *                              first cards + first chip), the 5-second
 *                              read the Plain-Read contract is graded on
 *   page-NN-<slug>-full.png  — fullPage screenshot for deeper review
 *
 * The agent then Reads each PNG and produces a per-page punch list:
 *   - is the verdict at the top?
 *   - do the 3 cards render with non-empty heroes?
 *   - does each insight panel show a source chip?
 *   - any empty-state placeholders that should be hidden?
 *
 * This spec does NOT assert anything — failing tests aren't the goal.
 * Capturing the visual state every run IS the goal; the analysis
 * happens in the agent loop afterwards.
 *
 * Run:    npx playwright test tests/plain-read-walkthrough.spec.ts
 * Output: .tmp/walkthrough/page-NN-<slug>-{top,full}.png
 *
 * Skills consulted: qa (real DOM + fixture reuse), frontend (Plain-Read
 * markers), platform-guardian (capture-but-don't-fail for visual diff).
 */
import { test } from './_fixtures';
import { waitForPageReady } from './_helpers';
import * as path from 'path';
import * as fs from 'fs';

// Walkthrough order matches project_plain_read_contract.md exactly.
const PAGES: Array<{ slug: string; file: string; flow: string }> = [
  // Day-1 supervisor flow
  { slug: 'hive',             file: 'hive.html',             flow: 'supervisor' },
  { slug: 'alert-hub',        file: 'alert-hub.html',        flow: 'supervisor' },
  { slug: 'pm-scheduler',     file: 'pm-scheduler.html',     flow: 'supervisor' },
  { slug: 'analytics',        file: 'analytics.html',        flow: 'supervisor' },
  { slug: 'predictive',       file: 'predictive.html',       flow: 'supervisor' },
  // Day-1 worker flow
  { slug: 'inventory',        file: 'inventory.html',        flow: 'worker' },
  { slug: 'asset-hub',        file: 'asset-hub.html',        flow: 'worker' },
  { slug: 'shift-brain',      file: 'shift-brain.html',      flow: 'worker' },
  { slug: 'dayplanner',       file: 'dayplanner.html',       flow: 'worker' },
  // Growth / community
  { slug: 'skillmatrix',      file: 'skillmatrix.html',      flow: 'growth' },
  { slug: 'achievements',     file: 'achievements.html',     flow: 'growth' },
  // Admin / specialist
  { slug: 'project-manager',  file: 'project-manager.html',  flow: 'admin' },
  { slug: 'integrations',     file: 'integrations.html',     flow: 'admin' },
  { slug: 'marketplace',      file: 'marketplace.html',      flow: 'admin' },
  { slug: 'ph-intelligence',  file: 'ph-intelligence.html',  flow: 'admin' },
  { slug: 'report-sender',    file: 'report-sender.html',    flow: 'admin' },
];

const OUT_DIR = path.resolve(__dirname, '..', '.tmp', 'walkthrough');

// Ensure the output directory exists; clear stale screenshots so each
// run produces a clean set (no orphaned files from a previous order).
test.beforeAll(() => {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  for (const f of fs.readdirSync(OUT_DIR)) {
    if (f.endsWith('.png')) fs.unlinkSync(path.join(OUT_DIR, f));
  }
});

test.describe('Plain-Read walkthrough — visual capture', () => {
  PAGES.forEach((entry, idx) => {
    const n = String(idx + 1).padStart(2, '0');
    test(`${n}. ${entry.slug} (${entry.flow})`, async ({ whPage }) => {
      const url = `/workhive/${entry.file}`;
      await whPage.goto(url, { waitUntil: 'domcontentloaded' });
      await waitForPageReady(whPage);

      // Wait for the Plain-Read region to leave its "Loading..." state
      // before snapping. Analytics, marketplace, and report-sender all
      // have slow loaders (Python-API roundtrip, listing aggregator,
      // contact resolver) that the previous 2.2s fixed wait missed —
      // capture caught "Computing..." / "Loading..." rather than real
      // values.
      //
      // Strategy: poll for the verdict label OR any hero card text to
      // settle (no longer "Computing..." / "Loading..."). Bail after 7s
      // so a genuinely slow page still captures (better mid-load shot
      // than a hang).
      await whPage.waitForFunction(() => {
        const labelEl = document.querySelector(
          '[id$="verdict-label"], #ss-verdict-label, #pm-verdict-label, #sm-verdict-label'
        );
        const labelText = labelEl ? (labelEl.textContent || '').trim() : '';
        const stillComputing = !!labelText && (
          labelText.startsWith('Computing') ||
          labelText.startsWith('Loading') ||
          labelText.startsWith('Rolling up')
        );
        const labelSettled = !!labelText && !stillComputing;
        // Also check that at least one hero card has a non-placeholder
        // value — guards against pages where the verdict has no element.
        const heroes = Array.from(document.querySelectorAll('.sc-hero, .ac-text'));
        const anyHeroSettled = heroes.some(h => {
          const t = (h.textContent || '').trim();
          return t && t !== '—' && t !== '--' &&
            !t.startsWith('Loading') && !t.startsWith('Computing');
        });
        return labelSettled || anyHeroSettled;
      }, { timeout: 7000 }).catch(() => { /* mid-load capture is acceptable */ });

      // Small post-settle buffer for paint.
      await whPage.waitForTimeout(400);

      const topPath  = path.join(OUT_DIR, `page-${n}-${entry.slug}-top.png`);
      const fullPath = path.join(OUT_DIR, `page-${n}-${entry.slug}-full.png`);

      // Hero region (viewport-sized) — the 5-second read.
      await whPage.screenshot({ path: topPath, fullPage: false });
      // Full scroll — for deeper review (insight panels below the fold).
      await whPage.screenshot({ path: fullPath, fullPage: true });

      // No assertions — capture-only. The agent reads the PNGs and
      // produces the punch list.
      // eslint-disable-next-line no-console
      console.log(`[walkthrough] ${n}. ${entry.slug}: top + full captured`);
    });
  });
});
