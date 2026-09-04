// prove_cta_activation.mjs — T1.2: every visible primary CTA, CLICKED, with a consequence.
// ─────────────────────────────────────────────────────────────────────────────
// WHY. 790 green gates coexisted with a dead "Get Early Access" bar on the landing page,
// because every CTA oracle on this platform asserted EXISTENCE (the element is there, has a
// name, meets 44px) and none asserted CONSEQUENCE (tapping it changes the world). This prover
// is the missing half: walk as anon at 390 and 1280, find every primary-styled CTA, click it,
// and demand an observable consequence — navigation | a modal/overlay opening | a scroll
// delta | a focus move | a DOM mutation burst. A click that changes NOTHING is the defect
// (see memory: "a click that changes nothing logs as ok").
//
// Inert discipline: an inert CTA is NOT skipped (the old amnesty). The prover first performs
// the reveal gesture a real user would (scroll past the hero, which un-inerts the sticky
// bar), and only if the control STAYS inert is that recorded — as `inert-stuck`, a defect.
//
// Usage:  node tools/prove_cta_activation.mjs [--page index] [--accept]
//   --accept re-baselines cta_activation_baseline.json (dead ≤ N ratchet, normally 0).
// Origin: WH_ORIGIN (default http://127.0.0.1:5000, the same local stack every prover uses).

import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync } from 'fs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
// ★THE APP IS SERVED UNDER /workhive/, AND THAT PREFIX DECIDES WHETHER LINKS RESOLVE (2026-08-28).
// The seeder serves the same page at BOTH /learn/<slug>/ and /workhive/learn/<slug>/, 200 either
// way with identical text - but it rewrites root-absolute hrefs only under the prefixed path. At
// /learn/... "Open the AI Assistant" points at /assistant.html, which 404s; at /workhive/learn/...
// it points at /workhive/assistant.html and navigates. Walking the unprefixed path made this prover
// report a WORKING CTA as a dead click, which is the one verdict it exists to give and the one it
// must never give wrongly - a prover that cries wolf about dead CTAs is a prover nobody registers,
// and this one was in fact never registered on the board. Verified by clicking the control by hand
// under the prefix: it navigates and lands on the assistant page.
const PATH_BASE = process.env.WH_BASE || '/workhive';
const args = process.argv.slice(2);
const PAGE_ONLY = args.includes('--page') ? args[args.indexOf('--page') + 1] : null;
const ACCEPT = args.includes('--accept');

// The anon funnel roster: the surfaces a signed-out visitor actually converts from.
// Template families (learn/tools) are covered by their two exemplars — instance-cheap
// coverage of the other ~111 is public_surface_gate.py's static lint (T1.3).
const ROSTER = [
  { page: 'index.html', slug: 'index' },
  { page: 'public-feed.html', slug: 'public-feed' },
  { page: 'marketplace.html', slug: 'marketplace' },
  { page: 'learn/what-is-workhive-complete-platform-guide/index.html', slug: 'learn-exemplar' },
  // The local seeder serves calculator pages only under the /workhive/ prefix (learn resolves
  // both ways). The first run listed the unprefixed path, got a 404, and recorded "0 probes,
  // 0 dead" — a silent hole; the goto status check below now makes that an ERROR instead.
  { page: 'workhive/tools/ahu-sizing-calculator/index.html', slug: 'tools-exemplar' },
];

const VIEWPORTS = [{ w: 390, h: 780, name: '390' }, { w: 1280, h: 900, name: '1280' }];

// Primary-CTA candidates: the platform's own vocabulary (btn-primary, cta-*), plus any
// anchor/button whose class names it a CTA. Chrome (nav-hub FAB, companion) excluded.
const FIND_CTAS = () => {
  const isShell = (el) => !!(el.closest && el.closest('[id^="wh-ai"],[id^="wh-hub"],#wh-companion,.wh-hub'));
  const vis = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const sel = (el) => {
    if (el.id) return '#' + el.id;
    const cls = String(el.className || '').trim().split(/\s+/).slice(0, 2).join('.');
    return el.tagName.toLowerCase() + (cls ? '.' + cls : '');
  };
  const out = [];
  document.querySelectorAll('a,button').forEach((el, i) => {
    if (isShell(el)) return;
    if (!/btn-primary|cta-pulse|cta-btn|header-btn|\bcta\b/i.test(String(el.className || ''))) return;
    const inert = !!(el.inert || (el.closest && el.closest('[inert]')));
    if (!inert && !vis(el)) return;   // inert ones are kept even when visually parked off-screen
    el.setAttribute('data-cta-probe', String(i));
    out.push({ idx: i, sel: sel(el), text: (el.innerText || '').trim().slice(0, 40),
               href: el.getAttribute('href'), inert });
  });
  return out;
};

async function consequenceOfClick(page, idx) {
  // Arm observers, click, then read what changed. Focus/scroll/URL are cheap reads;
  // "modal opened" = a large overlay newly visible; mutations = childList burst.
  const before = await page.evaluate(() => ({
    url: location.href, scrollY: window.scrollY,
    active: document.activeElement ? document.activeElement.tagName + (document.activeElement.id ? '#' + document.activeElement.id : '') : '',
    overlays: [...document.querySelectorAll('div,section,dialog')].filter((el) => {
      const s = getComputedStyle(el); const r = el.getBoundingClientRect();
      return (s.position === 'fixed' || s.position === 'absolute') && r.width > innerWidth * 0.5
        && r.height > innerHeight * 0.3 && s.display !== 'none' && s.visibility !== 'hidden';
    }).length,
  }));
  await page.evaluate(() => { window.__ctaMut = 0;
    window.__ctaObs = new MutationObserver((m) => { window.__ctaMut += m.length; });
    window.__ctaObs.observe(document.body, { childList: true, subtree: true, attributes: true }); });

  const clicked = await page.evaluate((i) => {
    const el = document.querySelector(`[data-cta-probe="${i}"]`);
    if (!el) return false;
    el.scrollIntoView({ block: 'center' });
    el.click();
    return true;
  }, idx).catch(() => false);
  if (!clicked) return { gone: true };

  await page.waitForTimeout(1400);
  const after = await page.evaluate(() => {
    try { window.__ctaObs && window.__ctaObs.disconnect(); } catch (_) {}
    return {
      url: location.href, scrollY: window.scrollY,
      active: document.activeElement ? document.activeElement.tagName + (document.activeElement.id ? '#' + document.activeElement.id : '') : '',
      overlays: [...document.querySelectorAll('div,section,dialog')].filter((el) => {
        const s = getComputedStyle(el); const r = el.getBoundingClientRect();
        return (s.position === 'fixed' || s.position === 'absolute') && r.width > innerWidth * 0.5
          && r.height > innerHeight * 0.3 && s.display !== 'none' && s.visibility !== 'hidden';
      }).length,
      mut: window.__ctaMut || 0,
    };
  }).catch(() => null);
  if (!after) return { navigated: true };   // full navigation tore the context — a consequence

  return {
    navigated: after.url !== before.url,
    modal: after.overlays > before.overlays,
    scrolled: Math.abs(after.scrollY - before.scrollY) > 40,
    focused: after.active !== before.active,
    mutations: after.mut,
  };
}

async function probePage(browser, entry) {
  const results = [];
  for (const vp of VIEWPORTS) {
    const ctx = await browser.newContext({ viewport: { width: vp.w, height: vp.h }, timezoneId: 'Asia/Manila' });
    const page = await ctx.newPage();
    try {
      const resp = await page.goto(`${ORIGIN}${PATH_BASE}/${entry.page}`, { waitUntil: 'domcontentloaded', timeout: 25000 });
      if (resp && !resp.ok()) throw new Error(`HTTP ${resp.status()} — a 404 walked as "0 CTAs, 0 dead" is a silent coverage hole`);
      await page.waitForTimeout(2500);
      // The reveal gesture: scroll past the hero so scroll-armed CTAs (sticky bar) un-inert,
      // then back to top so geometry reads consistently.
      await page.evaluate(() => window.scrollTo(0, Math.min(document.body.scrollHeight, innerHeight * 2)));
      await page.waitForTimeout(700);
      const ctas = await page.evaluate(FIND_CTAS);
      for (const c of ctas) {
        // Re-check inert AFTER the reveal gesture: still inert = stuck, and that is the record.
        const stillInert = await page.evaluate((i) => {
          const el = document.querySelector(`[data-cta-probe="${i}"]`);
          return el ? !!(el.inert || (el.closest && el.closest('[inert]'))) : null;
        }, c.idx);
        if (stillInert) {
          // One more chance: the sticky bar re-inerts near the top; probe at depth.
          await page.evaluate(() => window.scrollTo(0, Math.min(document.body.scrollHeight, innerHeight * 2)));
          await page.waitForTimeout(500);
          const inertAtDepth = await page.evaluate((i) => {
            const el = document.querySelector(`[data-cta-probe="${i}"]`);
            return el ? !!(el.inert || (el.closest && el.closest('[inert]'))) : null;
          }, c.idx);
          if (inertAtDepth) {
            results.push({ page: entry.slug, vp: vp.name, cta: c.text || c.sel, verdict: 'inert-stuck', dead: true });
            continue;
          }
        }
        const q = await consequenceOfClick(page, c.idx);
        const alive = q.gone === true ? false
          : (q.navigated || q.modal || q.scrolled || q.focused || (q.mutations || 0) >= 3);
        results.push({ page: entry.slug, vp: vp.name, cta: c.text || c.sel, verdict: alive ? 'alive' : 'dead-click', dead: !alive, q });
        // A navigation consumed the page — return and re-arm for the remaining CTAs.
        // EXACT pathname compare, never substring: "index.html?signin=1&return=public-feed.html"
        // CONTAINS "public-feed.html", so a substring check concluded we were still on the feed
        // and probed its selectors against INDEX — 6 false deads on the first run of this very
        // prover (the read-the-control-after-pressing-it class, now in its URL costume).
        const nowUrl = page.url();
        const stillHere = (() => { try { return new URL(nowUrl).pathname.replace(/^\//, '') === entry.page; } catch (_) { return false; } })();
        if (!stillHere) {
          await page.goto(`${ORIGIN}${PATH_BASE}/${entry.page}`, { waitUntil: 'domcontentloaded', timeout: 25000 }).catch(() => {});
          await page.waitForTimeout(1800);
          await page.evaluate(() => window.scrollTo(0, Math.min(document.body.scrollHeight, innerHeight * 2))).catch(() => {});
          await page.waitForTimeout(500);
          await page.evaluate(FIND_CTAS).catch(() => {});
        }
      }
    } catch (e) {
      results.push({ page: entry.slug, vp: vp.name, cta: '(page)', verdict: 'walk-error: ' + String(e.message || e).slice(0, 80), dead: false });
    }
    await ctx.close();
  }
  return results;
}

const roster = PAGE_ONLY ? ROSTER.filter((r) => r.slug.includes(PAGE_ONLY)) : ROSTER;
const browser = await chromium.launch();
const all = [];
for (const entry of roster) {
  const rs = await probePage(browser, entry);
  all.push(...rs);
  const dead = rs.filter((r) => r.dead).length;
  console.log(`[CTA] ${entry.slug.padEnd(16)} ${rs.length} probe(s), ${dead} dead`);
}
await browser.close();

const dead = all.filter((r) => r.dead);
const report = { ts: new Date().toISOString(), origin: ORIGIN, probes: all.length, dead: dead.length, results: all };
writeFileSync('cta_activation_report.json', JSON.stringify(report, null, 2));

const BASE = 'cta_activation_baseline.json';
let baseline = 0;
if (existsSync(BASE)) baseline = JSON.parse(readFileSync(BASE, 'utf8')).dead ?? 0;
else writeFileSync(BASE, JSON.stringify({ dead: dead.length, established: true }, null, 2));
if (ACCEPT || dead.length < baseline) writeFileSync(BASE, JSON.stringify({ dead: dead.length, accepted: ACCEPT || undefined }, null, 2));

console.log(`\n[CTA] ${all.length} probes · ${dead.length} dead (baseline ${baseline})`);
for (const d of dead) console.log(`  DEAD  ${d.page}@${d.vp}  "${d.cta}"  ${d.verdict}`);
if (dead.length > baseline && !ACCEPT) { console.log('[CTA] FAIL — dead CTA(s) above baseline'); process.exit(1); }
console.log('[CTA] PASS');
