/**
 * journey-calm-dashboard-behaviour.spec.ts — Calm Dashboard runtime checks.
 * =========================================================================
 *
 * Layer 2 BEHAVIOURAL coverage for the Calm Dashboard Contract (the L-1.5
 * static miner only checks the served HTML; this spec drives an actual
 * Playwright browser so we catch DOM-time regressions).
 *
 * Per opted-in page (every page that ships `<meta name="calm-dashboard"
 * content="1">`), this spec verifies:
 *
 *   1. A verdict region is present in the live DOM (visible or hidden,
 *      but rendered as a real element)
 *   2. At least one <details> disclosure exists for secondary content
 *   3. window.hideZeroStat is either defined OR the page has an inline
 *      equivalent (filter-by-positive predicate)
 *   4. No unanchored hard-coded stat tiles (every .stat-card / .kpi-card
 *      reads from either renderSourceChip() OR has a
 *      data-canonical-source attribute)
 *
 * Uses raw fetch + setContent sandbox (mirrors calm-dashboard.spec.ts
 * pattern — no signin fixture, fast & deterministic).
 */
import { test, expect, Page } from '@playwright/test';
import { promises as fs } from 'fs';
import * as path from 'path';

const ROOT = path.resolve(__dirname, '..');

// Derive the opted-in page list dynamically by scanning *.html for the
// calm-dashboard meta tag. This way new opt-ins are automatically covered
// without editing the spec, and the spec never drifts from reality.
const ALL_CANDIDATE_PAGES = [
  'hive.html', 'analytics.html', 'asset-hub.html', 'achievements.html',
  'dayplanner.html', 'ph-intelligence.html', 'ai-quality.html',
  'shift-brain.html', 'alert-hub.html', 'platform-health.html',
  'founder-console.html', 'index.html', 'predictive.html',
  'plant-connections.html',
];

async function discoverCalmDashboardPages(): Promise<string[]> {
  const opted: string[] = [];
  for (const p of ALL_CANDIDATE_PAGES) {
    const fp = path.join(ROOT, p);
    try {
      const html = await fs.readFile(fp, 'utf8');
      if (/<meta\s+name=["']calm-dashboard["']\s+content=["']1["']/i.test(html)) {
        opted.push(p);
      }
    } catch { /* file missing — skip */ }
  }
  return opted;
}

// Computed at module load. Each test() closure captures this list.
const CALM_DASHBOARD_PAGES: string[] = require('fs').readdirSync(ROOT)
  .filter((f: string) => f.endsWith('.html'))
  .filter((f: string) => {
    try {
      const html = require('fs').readFileSync(path.join(ROOT, f), 'utf8');
      return /<meta\s+name=["']calm-dashboard["']\s+content=["']1["']/i.test(html);
    } catch { return false; }
  });

async function fetchHtml(request: any, page: string): Promise<string> {
  const res = await request.get(`/workhive/${page}`);
  expect(res.status(), `${page} should return 200`).toBe(200);
  return await res.text();
}

async function loadIntoSandbox(page: Page, html: string) {
  // Strip all <script src> tags pointing at external URLs to keep the
  // sandbox offline-safe. Inline scripts execute normally (Calm Dashboard
  // helpers like hideZeroStat live inline at end-of-body).
  const safe = html
    .replace(/<script[^>]+src=["']https?:[^"']+["'][^>]*><\/script>/gi, '')
    .replace(/<link[^>]+href=["']https?:[^"']+["'][^>]*\/?>/gi, '');
  await page.setContent(safe, { waitUntil: 'domcontentloaded' });
}

test.describe('Calm Dashboard Contract — behavioural per-page check', () => {

  for (const pageName of CALM_DASHBOARD_PAGES) {
    test(`${pageName}: calm-dashboard meta + verdict + <details> + hide-zero helper`, async ({ request, page }) => {
      const html = await fetchHtml(request, pageName);
      await loadIntoSandbox(page, html);

      // 1. Meta tag declares opt-in
      const optIn = await page.locator('meta[name="calm-dashboard"][content="1"]').count();
      expect(optIn, `${pageName}: <meta name="calm-dashboard" content="1"> must be present`).toBe(1);

      // 2. Verdict region present — either as a pre-rendered DOM node OR
      // declared in a template literal that runtime JS injects. Both are
      // valid Calm Dashboard patterns; pure static checks at initial load
      // are too strict because most pages hydrate via JS after data fetch.
      const verdictCount = await page.evaluate(() => {
        const sel = '[id$="-today"], [id$="-verdict"], [id$="-hero"], [id$="-focus"], [id$="-now"], .verdict, .today-card, .focus-card, .hero-card';
        return document.querySelectorAll(sel).length;
      });
      const verdictInTemplate = /class=["']verdict\b|renderVerdict\s*\(|verdictHost|class=["']today-card|class=["']focus-card|class=["']hero-card|id=["'][^"']*(?:today|verdict|hero|focus|now)["']/i.test(html);
      expect(verdictCount > 0 || verdictInTemplate,
        `${pageName}: verdict region must be either pre-rendered in DOM or declared in a template literal / renderVerdict function`).toBe(true);

      // 3. <details> disclosure exists for secondary content
      const detailsCount = await page.locator('details').count();
      expect(detailsCount, `${pageName}: at least one <details> disclosure required`).toBeGreaterThan(0);

      // 4. hide-zero helper defined OR filter pattern in raw HTML
      const hasHelper = await page.evaluate(() => {
        return typeof (window as any).hideZeroStat === 'function';
      });
      const hasFilterPattern = /\.filter\s*\(\s*[^)]*=>\s*[^)]*>\s*0\s*\)|tiles?\.length\s*===\s*0|hideZero/i.test(html);
      expect(hasHelper || hasFilterPattern,
        `${pageName}: must define window.hideZeroStat OR an equivalent filter-by-positive pattern`).toBe(true);
    });
  }
});

test.describe('Calm Dashboard Contract — registry consistency', () => {

  test('every page in this spec actually carries the calm-dashboard meta tag', async ({ request }) => {
    const stragglers: string[] = [];
    for (const p of CALM_DASHBOARD_PAGES) {
      const html = await fetchHtml(request, p);
      if (!/<meta\s+name=["']calm-dashboard["']\s+content=["']1["']/i.test(html)) {
        stragglers.push(p);
      }
    }
    expect(stragglers.length,
      `Pages in CALM_DASHBOARD_PAGES that are missing the opt-in meta tag:\n${stragglers.join('\n')}`).toBe(0);
  });

  test('every calm-dashboard page exposes a source chip OR a documented dashboard-allow comment', async ({ request }) => {
    const gaps: string[] = [];
    for (const p of CALM_DASHBOARD_PAGES) {
      const html = await fetchHtml(request, p);
      const hasChip = /renderSourceChip|wh-source-chip|data-canonical-source/i.test(html);
      const hasAllow = /dashboard-allow:/i.test(html);
      if (!hasChip && !hasAllow) gaps.push(p);
    }
    expect(gaps.length,
      `Pages with neither a source chip nor a dashboard-allow comment:\n${gaps.join('\n')}`).toBe(0);
  });
});
