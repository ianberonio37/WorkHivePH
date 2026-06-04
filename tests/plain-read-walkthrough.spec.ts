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

// Walkthrough order: Plain-Read analytical pages first (16),
// then write/specialist surfaces added to close L13a gap.
const PAGES: Array<{ slug: string; file: string; flow: string }> = [
  // ── Plain-Read analytical pages (verdict + cards + chip contract) ──────────
  // Day-1 supervisor flow
  { slug: 'hive',               file: 'hive.html',               flow: 'supervisor' },
  { slug: 'alert-hub',          file: 'alert-hub.html',          flow: 'supervisor' },
  { slug: 'pm-scheduler',       file: 'pm-scheduler.html',       flow: 'supervisor' },
  { slug: 'analytics',          file: 'analytics.html',          flow: 'supervisor' },
  { slug: 'predictive',         file: 'predictive.html',         flow: 'supervisor' },
  // Day-1 worker flow
  { slug: 'inventory',          file: 'inventory.html',          flow: 'worker' },
  { slug: 'asset-hub',          file: 'asset-hub.html',          flow: 'worker' },
  { slug: 'shift-brain',        file: 'shift-brain.html',        flow: 'worker' },
  { slug: 'dayplanner',         file: 'dayplanner.html',         flow: 'worker' },
  // Growth / community
  { slug: 'skillmatrix',        file: 'skillmatrix.html',        flow: 'growth' },
  { slug: 'resume',             file: 'resume.html',             flow: 'growth' },
  { slug: 'achievements',       file: 'achievements.html',       flow: 'growth' },
  // Admin / specialist
  { slug: 'project-manager',    file: 'project-manager.html',    flow: 'admin' },
  { slug: 'integrations',       file: 'integrations.html',       flow: 'admin' },
  { slug: 'marketplace',        file: 'marketplace.html',        flow: 'admin' },
  { slug: 'ph-intelligence',    file: 'ph-intelligence.html',    flow: 'admin' },
  { slug: 'report-sender',      file: 'report-sender.html',      flow: 'admin' },

  // ── Write / specialist surfaces (visual regression capture — L13a gap) ─────
  // No Plain-Read contract; chip wait may timeout gracefully (acceptable).
  { slug: 'logbook',            file: 'logbook.html',            flow: 'worker' },
  { slug: 'community',          file: 'community.html',          flow: 'worker' },
  { slug: 'audit-log',          file: 'audit-log.html',          flow: 'supervisor' },
  { slug: 'ai-quality',         file: 'ai-quality.html',         flow: 'supervisor' },
  { slug: 'plant-connections',  file: 'plant-connections.html',  flow: 'supervisor' },
  { slug: 'engineering-design', file: 'engineering-design.html', flow: 'specialist' },
  { slug: 'voice-journal',      file: 'voice-journal.html',      flow: 'worker' },
];

const OUT_DIR = path.resolve(__dirname, '..', '.tmp', 'walkthrough');

// Ensure the output directory exists. Do NOT clear existing PNGs here —
// with retries:1, beforeAll re-runs before the retry group and would wipe
// screenshots captured by the passing first-run tests. Each test overwrites
// its own file, so stale-from-prior-run and in-run captures coexist safely.
test.beforeAll(() => {
  fs.mkdirSync(OUT_DIR, { recursive: true });
});

test.describe('Plain-Read walkthrough — visual capture', () => {
  PAGES.forEach((entry, idx) => {
    const n = String(idx + 1).padStart(2, '0');
    test(`${n}. ${entry.slug} (${entry.flow})`, async ({ whPage }) => {
      const url = `/workhive/${entry.file}`;
      await whPage.goto(url, { waitUntil: 'domcontentloaded' });
      await waitForPageReady(whPage);

      // Track settlement warnings for Pattern 4 (settlement timeout detection).
      // The analyzer reads these to skip AI calls on mid-load pages.
      let settlementTimedOut = false;

      // Strategy: poll for:
      //   (a) verdict label leaves "Computing..." / "Loading..." / "Rolling up"
      //   (b) OR at least one hero card has a non-placeholder value
      //   (c) AND at least one .wh-source-chip is populated (non-empty text)
      //       — catches L11-type regressions where a chip slot exists but
      //         renderSourceChip() was never called (runtime complement of the
      //         static L11 validator which checks at code level).
      // Bail after 20s so slow pages (analytics Python API, marketplace
      // listing aggregator) still capture rather than hang.
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
        const heroes = Array.from(document.querySelectorAll('.sc-hero, .ac-text'));
        const anyHeroSettled = heroes.some(h => {
          const t = (h.textContent || '').trim();
          return t && t !== '—' && t !== '--' &&
            !t.startsWith('Loading') && !t.startsWith('Computing');
        });
        const chips = Array.from(document.querySelectorAll('.wh-source-chip'));
        const anyChipPopulated = chips.some(c => (c.textContent || '').trim().length > 10);
        return (labelSettled || anyHeroSettled) && anyChipPopulated;
      }, { timeout: 20000 }).catch(() => {
        settlementTimedOut = true;
        // eslint-disable-next-line no-console
        console.warn(`[walkthrough] page may not be fully settled before capture`);
      });

      // Small post-settle buffer for final paint.
      await whPage.waitForTimeout(400);

      // ── Capture metadata from live DOM (Patterns 1, 3, 4) ──────────────────
      // Written as page-NN-<slug>-meta.json alongside the PNGs.
      // The analyzer reads this to avoid false positives from seeder state
      // (Pattern 1), detect partial captures (Pattern 4), and cross-reference
      // journey coverage (Pattern 2 uses it indirectly).
      const meta = await whPage.evaluate((slug: string) => {
        const labelEl = document.querySelector('[id$="verdict-label"]');
        const verdictText = labelEl ? (labelEl.textContent || '').trim() : null;

        const heroEls = Array.from(document.querySelectorAll('.sc-hero'));
        const cardHeroes = heroEls.slice(0, 5).map(h => (h.textContent || '').trim());

        const chipEls = Array.from(document.querySelectorAll('.wh-source-chip'));
        const chipTexts = chipEls.slice(0, 3).map(c => (c.textContent || '').trim().slice(0, 80));

        // has_data = at least one card has a real number (not 0, — or Loading)
        const hasData = cardHeroes.some(h =>
          h && h !== '—' && h !== '--' && h !== '0' &&
          !h.startsWith('Loading') && !h.startsWith('Computing')
        );

        const chipPopulated = chipTexts.some(t => t.length > 10);

        const consoleErrors: string[] = [];  // populated externally

        return {
          slug,
          verdict_text:      verdictText,
          card_heroes:       cardHeroes,
          chip_texts:        chipTexts,
          has_data:          hasData,
          chip_populated:    chipPopulated,
          // Filled in below after evaluate() returns
          settlement_timed_out: false,
          console_errors:    consoleErrors,
        };
      }, entry.slug);

      meta.settlement_timed_out = settlementTimedOut;

      const topPath  = path.join(OUT_DIR, `page-${n}-${entry.slug}-top.png`);
      const fullPath = path.join(OUT_DIR, `page-${n}-${entry.slug}-full.png`);
      const metaPath = path.join(OUT_DIR, `page-${n}-${entry.slug}-meta.json`);

      // Hero region (viewport-sized) — the 5-second read.
      await whPage.screenshot({ path: topPath, fullPage: false });
      // Full scroll — for deeper review (insight panels below the fold).
      await whPage.screenshot({ path: fullPath, fullPage: true });
      // Metadata sidecar — read by analyze_walkthrough.py.
      fs.writeFileSync(metaPath, JSON.stringify(meta, null, 2));

      // eslint-disable-next-line no-console
      console.log(`[walkthrough] ${n}. ${entry.slug}: top + full + meta captured${settlementTimedOut ? ' (PARTIAL)' : ''}`);
    });
  });
});
