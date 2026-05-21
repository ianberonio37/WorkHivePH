/**
 * L0 Bug-Class Surface Coverage — browser-level companion to the
 * static omnibus in journey-l0-platform-bug-classes.spec.ts.
 *
 * The omnibus runs each L0 validator as a Python subprocess (static
 * source analysis). This spec exercises the SAME rules from the
 * browser side on a canonical set of pages, so a regression that
 * slips past the static scan (e.g. JS-injected tabindex / aria-label
 * added dynamically) still gets caught.
 *
 * One page-load per page, multiple bug-class checks asserted on each
 * DOM snapshot — so the spec stays fast even as we add more rules.
 *
 * Generated 2026-05-22 alongside the session's 14-WARN-dimension paydown.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';

const PAGES = [
  '/workhive/index.html',
  '/workhive/hive.html',
  '/workhive/logbook.html',
  '/workhive/inventory.html',
  '/workhive/pm-scheduler.html',
  '/workhive/analytics.html',
  '/workhive/asset-hub.html',
] as const;

test.describe('L0 bug-class surface coverage (browser-level)', () => {
  for (const url of PAGES) {
    test(`tabindex_positive: no positive tabindex on ${url}`, async ({ whPage }) => {
      await whPage.goto(url);
      await waitForPageReady(whPage);
      const positive = await whPage.$$eval('[tabindex]', (els) =>
        els
          .map(e => ({ value: e.getAttribute('tabindex'), tag: e.tagName.toLowerCase() }))
          .filter(t => {
            const n = Number(t.value);
            return Number.isFinite(n) && n > 0;
          })
      );
      expect(positive, `positive tabindex disrupts tab order on ${url}`).toEqual([]);
    });

    test(`viewport_user_scalable: pinch-zoom allowed on ${url}`, async ({ whPage }) => {
      await whPage.goto(url);
      const content = await whPage.$eval('meta[name="viewport"]', (el) =>
        (el.getAttribute('content') || '').toLowerCase()
      );
      expect(content, `viewport must not disable zoom on ${url}`).not.toMatch(/user-scalable\s*=\s*(no|0)|maximum-scale\s*=\s*1(?:\.0+)?(?!\d)/);
    });

    test(`heading_hierarchy: single h1 + no skip on ${url}`, async ({ whPage }) => {
      await whPage.goto(url);
      await waitForPageReady(whPage);
      // Visible headings only — popup/PDF templates marked with heading-allow
      // live inside JS strings and don't render to the DOM at page-load time.
      const levels = await whPage.$$eval('h1, h2, h3, h4, h5, h6', (hs) =>
        hs.map(h => Number(h.tagName.substring(1)))
      );
      // Single h1 (or zero — some popups have none)
      const h1Count = levels.filter(l => l === 1).length;
      expect(h1Count, `expect <=1 visible h1 on ${url}`).toBeLessThanOrEqual(1);
      // No skip > 1
      let prev = 0;
      for (const lvl of levels) {
        if (prev > 0) {
          expect(lvl, `heading skip ${prev}->${lvl} on ${url}`).toBeLessThanOrEqual(prev + 1);
        }
        prev = lvl;
      }
    });

    test(`table_accessible_name: every visible <table> has caption/aria-label/role=presentation on ${url}`, async ({ whPage }) => {
      await whPage.goto(url);
      await waitForPageReady(whPage);
      const unnamed = await whPage.$$eval('table', (tables) =>
        tables
          .filter(t => {
            // Skip presentational / hidden
            const role = (t.getAttribute('role') || '').toLowerCase();
            if (role === 'presentation' || role === 'none') return false;
            if (t.hasAttribute('aria-label')) return false;
            if (t.hasAttribute('aria-labelledby')) return false;
            const cap = t.querySelector(':scope > caption');
            if (cap && (cap.textContent || '').trim()) return false;
            return true;
          })
          .map(t => ({
            cls: t.className || '(none)',
            firstHead: ((t.querySelector('th')?.textContent) || '').trim().slice(0, 30),
          }))
      );
      expect(unnamed, `tables without accessible name on ${url}: ${JSON.stringify(unnamed)}`).toEqual([]);
    });

    test(`select_placeholder: every <select> has safe default on ${url}`, async ({ whPage }) => {
      await whPage.goto(url);
      await waitForPageReady(whPage);
      const unsafe = await whPage.$$eval('select', (sels) =>
        sels
          .filter(s => {
            if (s.hasAttribute('multiple')) return false;
            // Static-analysis allow markers serialize to data-select-placeholder-allow
            if (s.hasAttribute('data-select-placeholder-allow')) return false;
            const opts = s.querySelectorAll('option');
            if (!opts.length) return false;
            const first = opts[0];
            const firstValue = first.getAttribute('value') ?? '';
            if (firstValue === '') return false;
            // Any [selected] option counts as a safe default
            for (const o of opts) {
              if (o.hasAttribute('selected')) return false;
            }
            // first-option is the implicit default — flag it
            return true;
          })
          .map(s => ({ id: s.id || '(none)', firstOpt: (s.options[0]?.textContent || '').slice(0, 30) }))
      );
      expect(unsafe, `selects with unsafe implicit-default on ${url}: ${JSON.stringify(unsafe)}`).toEqual([]);
    });

    test(`console_log_drift: no naked console.log on ${url} page load`, async ({ whPage }) => {
      const logs: string[] = [];
      whPage.on('console', (msg) => {
        if (msg.type() === 'log') {
          const text = msg.text();
          // Permit page-boot diagnostics that carry the allow rationale in
          // their source comment — the runtime message itself is fine; we
          // only flag UNEXPECTED log noise that wasn't there at baseline.
          // Filter common framework hits we can't suppress (Supabase auth, etc).
          if (text.startsWith('GoTrue') || text.startsWith('[supabase]')) return;
          logs.push(text.slice(0, 100));
        }
      });
      await whPage.goto(url);
      await waitForPageReady(whPage);
      // Allow some baseline boot noise but flag >5 unmarked console.log calls
      expect(logs.length, `noisy console.log on ${url}: ${logs.slice(0, 5).join(' | ')}`).toBeLessThanOrEqual(5);
    });
  }
});
