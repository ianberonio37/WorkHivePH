/**
 * journey-l3-interface-reinforcement.spec.ts
 * ──────────────────────────────────────────────────────────────────────────
 * LAYER-3 INTERFACE-DEPTH joins the Unified Mega Gate.
 *
 * The L2 journey-* suite (73 specs / 1121 blocks) asserts FUNCTIONAL / DATA /
 * ISOLATION truths. It does NOT run the interface-DEPTH checks that the live
 * UFAI battery does:
 *   - clickAudit  — every control has an accessible NAME, no dead-ends,
 *                   R-FP1 redundancy, AND is KEYBOARD-OPERABLE (the <div onclick>
 *                   keyboard-dead trap that `journey-interaction-audit`'s
 *                   "no unwired onclick" PASSES — onclick IS wired, just mouse-only).
 *   - formAudit   — programmatic label[for] + input TYPE + autocomplete.
 *   - statesAudit — selected-state distinctness + :hover/:focus rule existence
 *                   (native interactive elements exempted — UA default ring).
 *   - referee     — axe U/F/A/I + correctness invariants.
 *
 * `ufai_battery.js` is plain JS that boots headless too, so we fetch+eval it
 * into each page and assert `full().totalMajor` FORWARD-ONLY RATCHETS against a
 * per-page ceiling. New interface-depth Major defects fail the gate; fixing one
 * lets you LOWER its ceiling (never raise it without a recorded reason).
 *
 * Proven live (2026-06-08 MCP walk): dayplanner had 24 keyboard-dead hour-slot
 * <div>s (+168 in week view) and pm-scheduler had 10 keyboard-dead asset-cards
 * that L2 passed — all fixed; this spec locks them at 0.
 *
 * Mobile-first (CSS-390) to match the platform's primary field-worker viewport.
 */
import { test, expect } from './_fixtures';

const BATTERY_URL = '/workhive/ufai_battery.js';
const MOBILE = { width: 390, height: 760 };

/**
 * Per-page ceiling for `full().totalMajor`. Forward-only: a page must not exceed
 * its ceiling. Lower a number ONLY when the defect is genuinely fixed; raising
 * one requires a recorded, deliberately-deferred reason (see notes).
 *
 *   pm-scheduler = 1  → the page `.fab` ("Add asset") is axe target-size-occluded
 *                       by the shared connectivity chip (wh-conn-chip). This is a
 *                       DEFERRED cross-component layout decision already queued in
 *                       sweep_critiques.json ("Page .fab occluded by the global
 *                       Online connectivity chip"). Drop to 0 when that ships.
 */
const CEILING: Record<string, number> = {
  'dayplanner.html':   0,
  'pm-scheduler.html': 1,
  'logbook.html':      0,
  'asset-hub.html':    0,
  'inventory.html':    0,
};

/** Fetch + indirect-eval + boot the UFAI battery into the current page. */
async function installAndBoot(page: any) {
  return page.evaluate(async (url: string) => {
    const r = await fetch(url);
    if (!r.ok) throw new Error('battery fetch ' + r.status);
    // indirect eval runs the arrow-fn module in global scope -> installs window.__UFAI
    (0, eval)(await r.text())();
    return await (window as any).__UFAI.boot();
  }, BATTERY_URL);
}

test.describe('L3 interface-depth reinforcement (battery.full() ratchet)', () => {
  // Pure read-only audits — order-independent, but keep them serial so a single
  // shared page/context isn't fighting parallel navigations.
  test.describe.configure({ mode: 'serial' });

  for (const [pageFile, ceiling] of Object.entries(CEILING)) {
    test(`${pageFile}: full().totalMajor <= ${ceiling}`, async ({ whPage }) => {
      await whPage.setViewportSize(MOBILE);
      await whPage.goto(`/workhive/${pageFile}`, { waitUntil: 'domcontentloaded' });

      // Did the page bounce us to sign-in? That's an identity/fixture failure,
      // not an interface verdict — surface it clearly instead of a confusing 0.
      expect(whPage.url(), 'page must not redirect to sign-in (fixture identity)').toContain(pageFile);

      // supabase UMD loads at end of <body>; pages render data after it is ready.
      await whPage.waitForFunction(() => !!(window as any).supabase, null, { timeout: 15000 });
      // Let async data + client-side renders settle so the audited DOM is real.
      await whPage.waitForTimeout(1800);

      const boot = await installAndBoot(whPage);
      expect(boot, 'battery installed + booted').toBeTruthy();

      const full = await whPage.evaluate(
        (pid: string) => (window as any).__UFAI.full({ pageId: pid, role: 'supervisor', experience: 'expert' }),
        pageFile.replace('.html', ''),
      );

      // Diagnostics on failure: which bucket + the exact Major defect strings.
      expect(
        full.totalMajor,
        `${pageFile} L3 interface-depth regressed.\n` +
          `  byBucket: ${JSON.stringify(full.byBucket)}\n` +
          `  counts:   ${JSON.stringify(full.counts)}\n` +
          `  majors:\n    ${(full.majorDefects || []).join('\n    ')}`,
      ).toBeLessThanOrEqual(ceiling);
    });
  }
});
