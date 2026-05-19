/**
 * Calm Dashboard Contract — verification.
 *
 * Per-page checks:
 *   (a) The calm-dashboard meta is in the raw HTML.
 *   (b) The hideZeroStat helper definition is in the raw HTML.
 *   (c) When the helper executes in a sandbox page, it dims zero-like
 *       values to opacity 0.55 and brightens non-zero values to 1.
 *
 * Rationale for raw-HTML checks: supervisor-only dashboards redirect
 * unauthenticated visitors to the landing page (signin-redirect pattern
 * documented in memory feedback_platform_intentional_blank_states). The
 * Calm contract concerns what the page *serves*, not what the page renders
 * after auth — fetching the source is the canonical test.
 *
 * Helper behavior is verified ONCE in a sandbox; the helper itself is
 * identical across all 13 footer-injected pages (and index.html uses the
 * inline conditional renderer pattern instead).
 */
import { test, expect } from '@playwright/test';

const META_REQUIRED = [
  'index.html',
  'hive.html',
  'alert-hub.html',
  'asset-hub.html',
  'analytics.html',
  'predictive.html',
  'achievements.html',
  'shift-brain.html',
  'dayplanner.html',
  'ai-quality.html',
  'ph-intelligence.html',
  'plant-connections.html',
  'founder-console.html',
  'platform-health.html',
];

// 13 pages carry the shared footer helper. index.html uses the inline
// `tiles.filter(t => Number(t.num) > 0)` pattern instead — same contract,
// different idiom.
const HELPER_FOOTER_PAGES = META_REQUIRED.filter(p => p !== 'index.html');

test.describe('Calm Dashboard Contract — served HTML', () => {
  for (const page of META_REQUIRED) {
    test(`${page}: declares <meta name="calm-dashboard" content="1">`, async ({ request }) => {
      const res = await request.get(`/workhive/${page}`);
      expect(res.status(), `${page} should return 200`).toBe(200);
      const html = await res.text();
      expect(html).toMatch(/<meta\s+name=["']calm-dashboard["']\s+content=["']1["']/);
    });
  }

  for (const page of HELPER_FOOTER_PAGES) {
    test(`${page}: ships hideZeroStat helper in the footer`, async ({ request }) => {
      const res = await request.get(`/workhive/${page}`);
      const html = await res.text();
      expect(html).toContain('window.hideZeroStat');
      expect(html).toMatch(/\.filter\(v\s*=>\s*v\s*!=\s*null\s*&&\s*Number\(v\)\s*>\s*0\)/);
    });
  }

  test('hideZeroStat helper behavior (sandbox)', async ({ page, request }) => {
    // Fetch the helper source verbatim from a known-shipping page and
    // execute it in a blank page context. Decouples behavior verification
    // from per-page redirect/gate logic.
    const src = await (await request.get('/workhive/hive.html')).text();
    const m = src.match(/window\.hideZeroStat\s*=\s*window\.hideZeroStat\s*\|\|\s*function\s*\([^)]*\)\s*\{[\s\S]*?\};/);
    expect(m, 'helper block must be findable in served HTML').not.toBeNull();
    const helperCode = m![0];

    await page.setContent(`<!doctype html><html><head></head><body><script>${helperCode}</script></body></html>`);

    const helperType = await page.evaluate(() => typeof (window as any).hideZeroStat);
    expect(helperType).toBe('function');

    const opacities = await page.evaluate(() => {
      const fn = (window as any).hideZeroStat as (el: HTMLElement, v: any) => void;
      const samples: Record<string, string> = {};
      const make = () => { const el = document.createElement('div'); document.body.appendChild(el); return el; };
      const cases: Array<[string, any]> = [
        ['zero_number',  0],
        ['zero_string',  '0'],
        ['emdash',       '—'],
        ['null',         null],
        ['small_number', 3],
        ['large_number', 42],
        ['string_num',   '7'],
      ];
      for (const [label, val] of cases) {
        const el = make();
        fn(el, val);
        samples[label] = el.style.opacity;
        el.remove();
      }
      return samples;
    });

    expect(opacities.zero_number,  '0 should dim').toBe('0.55');
    expect(opacities.zero_string,  '"0" should dim').toBe('0.55');
    expect(opacities.emdash,       '"—" should dim').toBe('0.55');
    expect(opacities.null,         'null should dim').toBe('0.55');
    expect(opacities.small_number, '3 should brighten').toBe('1');
    expect(opacities.large_number, '42 should brighten').toBe('1');
    expect(opacities.string_num,   '"7" should brighten').toBe('1');
  });
});
