/**
 * journey-interaction-audit.spec.ts — "wired & alive" clickable audit.
 * ===================================================================
 * Born from a user catch (2026-06-06): the grounded MCP sweep MEASURED buttons
 * (size, font, role/aria) but did not EXERCISE them — a button can be 44px and
 * labelled yet wired to an undefined handler. This locks the Functionality half.
 *
 * Crystallizes SOP Phase 3 "F0". The wiring check runs IN THE LIVE BROWSER (not a
 * static parse) so `typeof window[fn]` accounts for every loaded script
 * (utils.js, nav-hub.js, floating-ai.js, the page's own block). An inline
 * `onclick="fn()"` can only call a GLOBAL function, so `typeof window.fn !==
 * 'function'` is a genuine DEAD BUTTON (throws on click). Also flags dead
 * `href="#"/""/javascript:void` anchors with no onclick.
 *
 * This is the deterministic STATIC-wiring half (fast, non-flaky). The live
 * click-exercise half is done by hand during a sweep (SOP F0 step 3) — encoding
 * 80+ real clicks here would be flaky (file choosers, stacked overlays).
 */
import { test, expect } from './_fixtures';

const BASE = 'http://127.0.0.1:5000';

async function auditClickables(page) {
  return await page.evaluate(() => {
    const els = [...document.querySelectorAll(
      'button, a, [onclick], [role="button"], summary, input[type=button], input[type=submit]'
    )].filter((el: any) => el.checkVisibility && el.checkVisibility());
    const fnDefined = (n: string) => { try { return typeof (window as any)[n] === 'function'; } catch { return false; } };
    const KEYWORDS = ['if','for','while','return','function','event','this','catch','switch','typeof','new','delete','void','await','else'];
    const unwired: any[] = [], dead: any[] = [];
    els.forEach((el: any) => {
      const oc = el.getAttribute('onclick') || '';
      const href = el.getAttribute('href');
      const label = (el.textContent || el.getAttribute('aria-label') || el.id || '').trim().replace(/\s+/g, ' ').slice(0, 30);
      if (oc) {
        const fns = [...oc.matchAll(/([A-Za-z_$][\w$]*)\s*\(/g)].map(m => m[1]).filter(n => !KEYWORDS.includes(n));
        const bad = fns.filter(n => !fnDefined(n));
        if (bad.length) unwired.push({ label, id: el.id || '', undefinedFns: bad, onclick: oc.slice(0, 70) });
      } else if (href !== null) {
        if (href === '' || href === '#' || /^javascript:\s*void/.test(href)) dead.push({ label, href, id: el.id || '' });
      }
    });
    return { total: els.length, unwired, dead };
  });
}

test.describe('Interaction audit — every clickable is wired (grounded sweep F0)', () => {

  test('index.html (logged-out landing): no unwired onclick, no dead links', async ({ rawPage }) => {
    await rawPage.goto(`${BASE}/workhive/index.html`);
    await rawPage.waitForLoadState('domcontentloaded');
    await rawPage.waitForTimeout(600);
    const r = await auditClickables(rawPage);
    expect(r.total, 'expected clickables on the landing').toBeGreaterThan(20);
    expect(r.unwired, `unwired onclick handlers (dead buttons): ${JSON.stringify(r.unwired)}`).toEqual([]);
    expect(r.dead, `dead href="#"/"" links: ${JSON.stringify(r.dead)}`).toEqual([]);
  });

  test('logbook.html: no unwired onclick, no dead links', async ({ whPage }) => {
    await whPage.goto(`${BASE}/workhive/logbook.html`);
    await whPage.waitForLoadState('domcontentloaded');
    await whPage.waitForTimeout(800);
    const r = await auditClickables(whPage);
    expect(r.total, 'expected clickables on logbook').toBeGreaterThan(20);
    expect(r.unwired, `unwired onclick handlers: ${JSON.stringify(r.unwired)}`).toEqual([]);
    expect(r.dead, `dead links: ${JSON.stringify(r.dead)}`).toEqual([]);
  });

  test('inventory.html: no unwired onclick, no dead links', async ({ whPage }) => {
    await whPage.goto(`${BASE}/workhive/inventory.html`);
    await whPage.waitForLoadState('domcontentloaded');
    await whPage.waitForTimeout(800);
    const r = await auditClickables(whPage);
    expect(r.total, 'expected clickables on inventory').toBeGreaterThan(20);
    expect(r.unwired, `unwired onclick handlers: ${JSON.stringify(r.unwired)}`).toEqual([]);
    expect(r.dead, `dead links: ${JSON.stringify(r.dead)}`).toEqual([]);
  });
});
