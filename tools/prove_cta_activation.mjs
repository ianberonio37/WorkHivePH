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
import { ALL_ROWS_DRAWN } from './lib/long_list_text.mjs';

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
  // ...and since PATH_BASE added /workhive to every walk (2026-08-28) this entry's own prefix doubled it to
  // /workhive/workhive/tools/..., a 404 every run (found 2026-10-13); the base supplies the prefix now.
  { page: 'tools/ahu-sizing-calculator/index.html', slug: 'tools-exemplar' },
  // ★AN EXEMPLAR ANSWERS FOR ITSELF, NOT FOR ITS NEIGHBOURS (2026-11-04, CX-UX). The roster is curated to the surfaces
  // a signed-out visitor converts FROM, and the template families ride on two exemplars because their instances share
  // one generator. That holds for "does the template's CTA work"; it does not hold for "was CV1 graded on THIS page",
  // which the cube asks per page - and these six are not template instances of the exemplars: the learn HUB (its own
  // markup), a guide from the 19-article chrome variant whose header CTA is a bare orange "Sign Up Free" the learn
  // exemplar does not carry, and the four public-root pages (about, the public roadmap, privacy, terms), which a
  // visitor reaches from the landing footer and where a sign-up door is - or is not - the next step. Each is walked
  // under its own path; a page whose walk finds no primary CTA now says so in `pages` instead of writing nothing.
  { page: 'learn/index.html', slug: 'learn-hub' },
  { page: 'learn/philippine-plants-now-pay-the-highest-power-rates/index.html', slug: 'learn-power-rates' },
  { page: 'about/index.html', slug: 'about' },
  { page: 'feedback/index.html', slug: 'roadmap' },
  { page: 'privacy-policy/index.html', slug: 'privacy-policy' },
  { page: 'terms-of-service/index.html', slug: 'terms-of-service' },
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
  // ★PRIMARY-STYLED IS WHAT IT LOOKS LIKE, NOT ONLY WHAT IT IS CALLED (2026-11-04). The class vocabulary missed the
  // 19-guide header's "Sign Up Free" - a solid brand-orange button styled with utility classes (bg-orange-wh) and no
  // cta/btn-primary name - so a walk of such a page found "no primary CTA" while one sat in the header. A control
  // whose computed fill IS the brand primary is primary-styled too. The fill is resolved from the token on the page
  // itself (a probe element painted with var(--wh-orange)), so a palette change moves the ruler with it. The skip
  // link shares the fill and is not a CTA (it is parked off-screen until focused), so it is excluded by name.
  const brand = (() => {
    try {
      const p = document.createElement('span');
      p.style.cssText = 'position:absolute;left:-9999px;background:var(--wh-orange, #F7A21B)';
      document.body.appendChild(p);
      const c = getComputedStyle(p).backgroundColor;
      p.remove();
      return c;
    } catch (_) { return 'rgb(247, 162, 27)'; }
  })();
  const out = [];
  document.querySelectorAll('a,button').forEach((el, i) => {
    if (isShell(el)) return;
    if (el.classList && el.classList.contains('wh-skip-link')) return;
    const named = /btn-primary|cta-pulse|cta-btn|header-btn|\bcta\b/i.test(String(el.className || ''));
    const filled = !named && getComputedStyle(el).backgroundColor === brand;
    if (!named && !filled) return;
    const inert = !!(el.inert || (el.closest && el.closest('[inert]')));
    if (!inert && !vis(el)) return;   // inert ones are kept even when visually parked off-screen
    el.setAttribute('data-cta-probe', String(i));
    out.push({ idx: i, sel: sel(el), text: (el.innerText || '').trim().slice(0, 40),
               href: el.getAttribute('href'), inert, by: named ? 'class' : 'fill' });
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
  // what each viewport's walk FOUND, written even when it found no primary CTA: an absent record cannot tell "walked,
  // nothing primary here" from "never walked", and only the first is an answer (CV1 N/A: no primary CTA on the page)
  const walked = {};
  for (const vp of VIEWPORTS) {
    const ctx = await browser.newContext({ viewport: { width: vp.w, height: vp.h }, timezoneId: 'Asia/Manila' });
    await ctx.addInitScript(ALL_ROWS_DRAWN);
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
      walked[vp.name] = { ctas: ctas.length, byFill: ctas.filter((c) => c.by === 'fill').length };
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
      walked[vp.name] = { error: String(e.message || e).slice(0, 80) };
    }
    await ctx.close();
  }
  return { results, walked };
}

const roster = PAGE_ONLY ? ROSTER.filter((r) => r.slug.includes(PAGE_ONLY)) : ROSTER;
const browser = await chromium.launch();
const all = [];
const pages = {};
for (const entry of roster) {
  const { results: rs, walked } = await probePage(browser, entry);
  all.push(...rs);
  pages[entry.slug] = { page: entry.page, walked };
  const dead = rs.filter((r) => r.dead).length;
  console.log(`[CTA] ${entry.slug.padEnd(18)} ${rs.length} probe(s), ${dead} dead`
    + Object.entries(walked).map(([v, w]) => `  ${v}:${w.error ? 'ERROR' : w.ctas + ' cta' + (w.byFill ? ` (${w.byFill} by fill)` : '')}`).join(''));
}
await browser.close();

const dead = all.filter((r) => r.dead);
// ★A --page RUN MERGES, IT DOES NOT CLOBBER (2026-11-04). The report is per page now (the CX-UX banker reads CV1 for one
// page at a time), and a subset run that rewrote the whole file erased every other page's reading. The walked slugs are
// replaced; the rest are kept as the earlier full run recorded them.
let report = { ts: new Date().toISOString(), origin: ORIGIN, results: all, pages };
if (PAGE_ONLY && existsSync('cta_activation_report.json')) {
  try {
    const prev = JSON.parse(readFileSync('cta_activation_report.json', 'utf8'));
    const mine = new Set(roster.map((r) => r.slug));
    report.results = (prev.results || []).filter((r) => !mine.has(r.page)).concat(all);
    report.pages = Object.assign({}, Object.fromEntries(Object.entries(prev.pages || {}).filter(([s]) => !mine.has(s))), pages);
  } catch (_) { /* empty-catch-allow: an unreadable earlier report is replaced by this run's */ }
}
report.probes = report.results.length;
report.dead = report.results.filter((r) => r.dead).length;
writeFileSync('cta_activation_report.json', JSON.stringify(report, null, 2));

const BASE = 'cta_activation_baseline.json';
let baseline = 0;
if (existsSync(BASE)) baseline = JSON.parse(readFileSync(BASE, 'utf8')).dead ?? 0;
else writeFileSync(BASE, JSON.stringify({ dead: dead.length, established: true }, null, 2));
// only a FULL run may lower the baseline: a subset that found 0 dead says nothing about the pages it skipped
if (ACCEPT || (!PAGE_ONLY && dead.length < baseline)) writeFileSync(BASE, JSON.stringify({ dead: dead.length, accepted: ACCEPT || undefined }, null, 2));

console.log(`\n[CTA] ${all.length} probes · ${dead.length} dead (baseline ${baseline})`);
for (const d of dead) console.log(`  DEAD  ${d.page}@${d.vp}  "${d.cta}"  ${d.verdict}`);
if (dead.length > baseline && !ACCEPT) { console.log('[CTA] FAIL — dead CTA(s) above baseline'); process.exit(1); }
console.log('[CTA] PASS');
