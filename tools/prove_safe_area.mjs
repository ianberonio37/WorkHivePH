// prove_safe_area.mjs — the CJ `safe_area` oracle, read from the AUTHORED CSS via CDP.
//
// WHY THIS IS A SEPARATE TOOL AND NOT ANOTHER GUESS INSIDE prove_viewport_overflow.mjs: I tried the
// hand-rolled version there FOUR times and it was wrong every time.
//   1. It swept every edge-pinned fixed element and reported 44 of 44 uncovered on all 22 pages — the
//      signature of a broken instrument. What it had found was `wh-skip-link` (hidden until focused),
//      `cursor-glow` (decoration) and `aurora-bg` (a full-screen background).
//   2. It then flagged hive's `#intent-capture`, which is `role="dialog" aria-modal="true"` — a modal
//      overlay, not the persistent bar that sits under the home bar.
//   3. It reported `insetRules: 0` on hive while hive.html contains FIVE safe-area-inset uses, because
//      they are written in inline `style="…"` attributes that `document.styleSheets` never exposes.
//   4. And it flagged pm-scheduler's `.bottom-nav`, which declares
//      `padding-bottom: env(safe-area-inset-bottom)` at pm-scheduler.html:226.
//
// THE ROOT CAUSE OF ALL FOUR: `getComputedStyle` cannot answer this question. Headless Chromium reports
// NO safe-area insets, so `env(safe-area-inset-bottom)` computes to `0px` and the used value is
// indistinguishable from "no rule at all". Reading the computed value and inferring intent from it is
// guessing, and it guessed wrong four times.
//
// SO THE DECLARATION IS READ INSTEAD, FROM THE SOURCE OF TRUTH. `CSS.getMatchedStylesForNode` over CDP
// returns the AUTHORED text of every rule that matches a node — inline styles, attribute styles and
// stylesheet rules alike — with `env(...)` still intact. That is the one instrument that sees what the
// author wrote rather than what the engine computed with no device to compute against.
//
// WHAT IS AND IS NOT PROVEN. This proves the DECLARATION exists on (or above) each piece of edge-pinned
// chrome. It does NOT prove the rendering on a notched device, because no inset is ever reported here.
// A row banked from this must say exactly that.
//
//   node tools/prove_safe_area.mjs            # all 22 roster pages
//   node tools/prove_safe_area.mjs --gate     # exit 1 on edge chrome with no authored inset
//   node tools/prove_safe_area.mjs --page pm-scheduler
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const PAGES = ['index', 'hive', 'logbook', 'inventory', 'pm-scheduler', 'project-manager',
  'dayplanner', 'asset-hub', 'analytics', 'alert-hub', 'skillmatrix', 'shift-brain',
  'voice-journal', 'assistant', 'community', 'public-feed', 'achievements',
  'engineering-design', 'resume', 'report-sender', 'project-report', 'analytics-report',
  // ★MARKETPLACE SURFACES, added 2026-08-20 -- see prove_viewport_overflow for the full note.
  // BF-ui-layout in the marketplace bank is 35 rows, ALL live-walk, and safe-area is half of
  // that family. The seller console is exactly where edge-pinned chrome lives (a wallet bar, a
  // job-list footer), so this roster gap mattered more here than anywhere.
  'marketplace', 'marketplace-seller', 'marketplace-seller-profile', 'platform-actions'];

const args = process.argv.slice(2);
const GATE = args.includes('--gate');
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();
const TEETH = args.includes('--teeth');
// THE INSET MUST MATCH THE EDGE, and this is the one correction that was about to produce a FALSE
// GREEN rather than a false red. A direction-blind `safe-area-inset` test passed index's TOP-pinned nav
// on an ancestor rule reading `padding-bottom: max(var(--wh-hub-reserve, …), env(safe-area-inset-bottom))`
// — a BOTTOM reservation for the hub button, which does nothing whatsoever about the notch above the
// nav. index contains zero `safe-area-inset-top` uses. A bottom inset does not protect a top edge, so
// the direction is now part of the test: top-pinned chrome needs inset-top, bottom-pinned needs
// inset-bottom. Every other correction in this file made the instrument stop inventing defects; this one
// stops it certifying one.
const INSET_FOR = { top: /safe-area-inset-top/, bottom: /safe-area-inset-bottom/ };

// Edge-pinned chrome a person reads or touches. Decoration, hidden helpers and modal overlays are
// excluded for the reasons above, and every exclusion is counted.
const FIND_PINNED = () => {
  const vis = (el) => {
    const s = getComputedStyle(el); const b = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0.01
      && b.width > 0 && b.height > 0;
  };
  const out = { pinned: [], skipped: 0, skipReasons: {} };
  const skip = (why) => { out.skipped++; out.skipReasons[why] = (out.skipReasons[why] || 0) + 1; };
  let n = 0;
  for (const el of document.querySelectorAll('body *')) {
    const s = getComputedStyle(el);
    if (s.position !== 'fixed' && s.position !== 'sticky') continue;
    if (!vis(el)) { skip('not visible'); continue; }
    const atBottom = s.bottom !== 'auto' && Math.abs(parseFloat(s.bottom) || 0) <= 2;
    const atTop = s.top !== 'auto' && Math.abs(parseFloat(s.top) || 0) <= 2;
    if (!atBottom && !atTop) continue;
    if (/skip-link|cursor-glow|aurora|hex-pattern|backdrop|overlay-bg/i
      .test((el.id || '') + ' ' + (el.className || ''))) { skip('decorative or hidden helper'); continue; }
    const role = (el.getAttribute('role') || '').toLowerCase();
    if (role === 'dialog' || role === 'alertdialog' || el.getAttribute('aria-modal') === 'true') {
      skip('modal overlay, not persistent edge chrome'); continue;
    }
    const hasContent = el.querySelector('a[href],button,input,select,textarea,[role="button"]')
      || (el.textContent || '').trim().length > 0;
    if (!hasContent) { skip('no content — nothing that could sit under the home bar'); continue; }
    const mark = 'wh-safe-probe-' + (n++);
    el.setAttribute('data-wh-safe', mark);
    out.pinned.push({ mark, id: el.id || null, cls: String(el.className || '').slice(0, 34),
                      edge: atBottom ? 'bottom' : 'top', pos: s.position });
  }
  return out;
};

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
await assertSignedIn(signIn(ctx, 'supervisor'));
const page = await ctx.newPage();
const cdp = await ctx.newCDPSession(page);
await cdp.send('DOM.enable');
await cdp.send('CSS.enable');

const results = [];
for (const p of (ONE ? [ONE.replace(/\.html$/, '')] : PAGES)) {
  const rec = { page: p, pinned: [], uncovered: 0, skipped: 0, skipReasons: {} };
  try {
    await page.goto(`${ORIGIN}/${p}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForTimeout(3000);
    const landed = await page.evaluate(() => location.pathname);
    rec.landed = landed;
    if (!landed.includes(p)) { rec.redirected = landed; results.push(rec); continue; }
    rec.viewportFitCover = await page.evaluate(() => /viewport-fit\s*=\s*cover/.test(
      (document.querySelector('meta[name="viewport"]') || {}).content || ''));
    if (TEETH) {
      await page.evaluate(() => {
        const mk = (id, extra) => {
          const d = document.createElement('div');
          d.id = id;
          d.textContent = 'teeth';
          d.style.cssText = 'position:fixed;bottom:0;left:0;width:120px;height:40px;z-index:1;' + extra;
          document.body.appendChild(d);
        };
        mk('wh-teeth-sa-violator', '');
        mk('wh-teeth-sa-satisfier', 'padding-bottom:env(safe-area-inset-bottom,0px);');
      });
    }
    const found = await page.evaluate(FIND_PINNED);
    rec.skipped = found.skipped; rec.skipReasons = found.skipReasons;
    const { root } = await cdp.send('DOM.getDocument', { depth: -1 });
    for (const item of found.pinned) {
      const { nodeId } = await cdp.send('DOM.querySelector', {
        nodeId: root.nodeId, selector: `[data-wh-safe="${item.mark}"]` });
      if (!nodeId) { rec.pinned.push({ ...item, authored: null, note: 'node not resolvable' }); continue; }
      const st = await cdp.send('CSS.getMatchedStylesForNode', { nodeId });
      // EVERY place an author can put it: the inline attribute, the attribute style, and each matched
      // rule (which is what getComputedStyle flattens away to 0px).
      const texts = [];
      if (st.inlineStyle && st.inlineStyle.cssText) texts.push(st.inlineStyle.cssText);
      if (st.attributesStyle && st.attributesStyle.cssText) texts.push(st.attributesStyle.cssText);
      for (const m of (st.matchedCSSRules || [])) {
        if (m.rule && m.rule.style && m.rule.style.cssText) {
          texts.push((m.rule.selectorList ? m.rule.selectorList.text + ' ' : '') + m.rule.style.cssText);
        }
      }
      const RE = INSET_FOR[item.edge];
      const hit = texts.find((t) => RE.test(t)) || null;
      // AN ANCESTOR'S PADDING ONLY PROTECTS A BOX THAT ITS PADDING CAN ACTUALLY MOVE — AND THE SEVENTH
      // CORRECTION IS THAT A VIEWPORT-PINNED BOX IS NOT ONE. Crediting an ancestor here passed
      // public-feed's `header` and engineering-design's `sticky top-0` on
      // `body{padding-top:calc(64px + env(safe-area-inset-top, 0px))}` — which is the wrong mechanism
      // twice over. That rule's own comment in public-feed.html says what it is for: reserving the
      // wayfinding back-pill band, whose pill (`#wh-wayfinding`, wayfinding.js:77) carries its OWN
      // `top:max(10px,env(safe-area-inset-top))`. And geometrically an ancestor cannot help either of
      // these boxes: `position:fixed` is laid out against the VIEWPORT, so ancestor padding never
      // displaces it at all; `position:sticky` sits in flow at rest — covered — but the instant the
      // page scrolls it pins to viewport top 0 and its content is under the notch again, which is
      // exactly when a person is reading it. So an ancestor rule is accepted ONLY for a box the
      // padding genuinely moves, and for a sticky box it is recorded as at-rest-only and still owed.
      let via = hit ? 'own rules' : null;
      const viewportPinned = item.pos === 'fixed' || item.pos === 'sticky';
      if (!hit && !viewportPinned) {
        const chain = await page.evaluate((mark) => {
          const out = [];
          let el = document.querySelector(`[data-wh-safe="${mark}"]`);
          for (let a = el && el.parentElement; a; a = a.parentElement) {
            const t = 'wh-anc-' + out.length;
            a.setAttribute('data-wh-anc', t);
            out.push({ t, tag: a.tagName, id: a.id || null });
            if (a.tagName === 'HTML') break;
          }
          return out;
        }, item.mark);
        for (const anc of chain) {
          const q = await cdp.send('DOM.querySelector', {
            nodeId: root.nodeId, selector: `[data-wh-anc="${anc.t}"]` });
          if (!q.nodeId) continue;
          const ast = await cdp.send('CSS.getMatchedStylesForNode', { nodeId: q.nodeId });
          const at = [];
          if (ast.inlineStyle && ast.inlineStyle.cssText) at.push(ast.inlineStyle.cssText);
          for (const m of (ast.matchedCSSRules || [])) {
            if (m.rule && m.rule.style && m.rule.style.cssText) at.push(m.rule.style.cssText);
          }
          const ah = at.find((t) => RE.test(t));
          if (ah) {
            via = `ancestor ${anc.tag}${anc.id ? '#' + anc.id : ''}: ${ah.slice(0, 70)}`;
            break;
          }
        }
      }
      rec.pinned.push({ ...item, covered: !!(hit || via), via,
                        why: (hit || via) ? null
                          : viewportPinned
                            ? `position:${item.pos} is laid out against the viewport, so no ancestor`
                              + ` padding can hold it clear of the ${item.edge} inset — it needs the`
                              + ` declaration on itself`
                            : `no authored safe-area-inset-${item.edge} on the element or any ancestor`,
                        authored: hit ? hit.slice(0, 120) : null });
    }
    rec.uncovered = rec.pinned.filter((x) => !x.covered).length;
  } catch (e) { rec.error = String(e).slice(0, 140); }
  if (TEETH) {
    const find = (id) => (rec.pinned || []).find((x) => (x.id || '') === id);
    const v = find('wh-teeth-sa-violator'), sat = find('wh-teeth-sa-satisfier');
    rec.teeth = {
      violatorSeen: !!v, satisfierSeen: !!sat,
      violatorUncovered: !!v && !v.covered,
      satisfierCovered: !!sat && !!sat.covered,
    };
    // A probe that was SKIPPED proves nothing, so being seen is part of the pass.
    rec.teeth.ok = rec.teeth.violatorSeen && rec.teeth.satisfierSeen
                && rec.teeth.violatorUncovered && rec.teeth.satisfierCovered;
    if (!rec.teeth.ok) { console.log('    BLUNT ' + rec.page + ': ' + JSON.stringify(rec.teeth)); process.exitCode = 1; }
    else console.log('    TEETH ok ' + rec.page);
  }
  results.push(rec);
  console.log(`  ${p.padEnd(20)} pinned=${rec.pinned.length} uncovered=${rec.uncovered}`
    + ` skipped=${rec.skipped}${rec.redirected ? ' REDIRECTED->' + rec.redirected : ''}`
    + (rec.uncovered ? '  ' + rec.pinned.filter((x) => !x.covered)
        .map((x) => `${x.id || x.cls}@${x.edge}`).join('; ') : '')
    + (rec.pinned.length && !rec.uncovered ? '  e.g. ' + (rec.pinned[0].via || '') : ''));
}
await browser.close();

const bad = results.filter((r) => r.uncovered > 0);
const redirected = results.filter((r) => r.redirected);
writeFileSync('safe_area_report.json', JSON.stringify({
  ran: new Date().toISOString(), origin: ORIGIN, method: 'CDP CSS.getMatchedStylesForNode (authored)',
  pages: results, offending: bad.map((r) => r.page), redirected: redirected.map((r) => r.page),
  totals: {
    pinned: results.reduce((a, r) => a + r.pinned.length, 0),
    uncovered: results.reduce((a, r) => a + r.uncovered, 0),
    skipped: results.reduce((a, r) => a + (r.skipped || 0), 0),
  },
}, null, 1));

const T = results.reduce((a, r) => ({ p: a.p + r.pinned.length, u: a.u + r.uncovered }), { p: 0, u: 0 });
console.log(`\n  ${results.length} page(s) — ${T.p} edge-pinned chrome element(s), ${T.u} with NO`
  + ` authored safe-area-inset declaration`);
console.log('  wrote safe_area_report.json');
if (GATE) {
  if (redirected.length) {
    console.log(`  FAIL — redirected instead of rendering: ${redirected.map((r) => r.page).join(', ')}`);
    process.exit(1);
  }
  if (!T.p) {
    console.log('  FAIL — 0 edge-pinned elements found on any page; the finder is not seeing the chrome');
    process.exit(1);
  }
  if (T.u) {
    console.log(`  FAIL — edge chrome with no authored inset on: ${bad.map((r) => r.page).join(', ')}`);
    process.exit(1);
  }
  console.log(`  PASS — all ${T.p} edge-pinned chrome elements carry an authored safe-area-inset `
    + 'declaration (the DECLARATION is proven; rendering on a notched device is not)');
}
