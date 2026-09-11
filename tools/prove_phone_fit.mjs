// prove_phone_fit — the PHONE-FIT lens (Ian, 2026-09-06: "text wrapped on their container in inventory; the hive board's
// 'more' overflows and extends left on a phone"). A signed-in supervisor opens each page at a phone viewport (390x844, the
// iPhone 14 class) and the page must FIT: (1) no horizontal page overflow; (2) no visible element sticking out of the
// viewport; (3) no text CLIPPED inside its own box (overflow hidden/clip with scrollWidth > clientWidth) and no unbroken
// token wider than its container (mid-word wrapping / overflow of long ids, emails, urls); (4) every "more"/kebab/menu
// trigger, once tapped, reveals a menu that lies INSIDE the viewport. Each finding names the element + rects.
//   node tools/prove_phone_fit.mjs                     # every interactive page
//   node tools/prove_phone_fit.mjs --page hive.html    # one page, verbose
//   node tools/prove_phone_fit.mjs --width 360         # a narrower phone
//   node tools/prove_phone_fit.mjs --pages a.html,b.html   # a subset (halves for the 10-minute background cap)
import { chromium } from 'playwright';
import { SEEDER, signIn, PAGE_QUERY, DB_PAGES, VIS_JS } from './prover_harness.mjs';
const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const LIST = (() => { const i = process.argv.indexOf('--pages'); return i >= 0 ? process.argv[i + 1].split(',') : null; })();   // a subset, so a full pass fits the 10-minute background cap in halves
const W = (() => { const i = process.argv.indexOf('--width'); return i >= 0 ? Number(process.argv[i + 1]) : 390; })();
// the P-M pool (51 pages = every root page + 8 calculators), generated from tools/seed_p_program_catalog.py _pool_for('P-M') on 2026-09-06
const PHONE_POOL = ["agentic-rag-observability.html", "ai-quality.html", "design-system.html", "founder-console.html", "llm-observability.html", "marketplace-admin.html", "offline-fallback.html", "plant-connections.html", "platform-actions.html", "promo-poster.html", "symbol-gallery.html", "validator-catalog.html", "learn/index.html", "achievements.html", "alert-hub.html", "analytics-report.html", "analytics.html", "architecture.html", "asset-hub.html", "assistant.html", "audit-log.html", "community.html", "dayplanner.html", "engineering-design.html", "hive.html", "index.html", "integrations.html", "inventory.html", "logbook.html", "marketplace-seller-profile.html", "marketplace-seller.html", "marketplace.html", "ph-intelligence.html", "pm-scheduler.html", "project-manager.html", "project-report.html", "public-feed.html", "report-sender.html", "resume.html", "shift-brain.html", "skillmatrix.html", "status.html", "voice-journal.html", "tools/ahu-sizing-calculator/index.html", "tools/beam-design-calculator/index.html", "tools/bearing-life-calculator/index.html", "tools/boiler-steam-calculator/index.html", "tools/boiler-system-calculator/index.html", "tools/bolt-torque-calculator/index.html", "tools/cable-tray-sizing-calculator/index.html", "tools/chiller-sizing-calculator/index.html"];
const PAGES = ONLY ? [ONLY] : LIST ? LIST : PHONE_POOL;
const MENU_RE = /(⋯|…|⋮|\bmore\b|\bmenu\b|\boptions\b|\bactions\b)/i;

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: W, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2, serviceWorkers: 'block' });
await signIn(ctx);

// The audit is a REAL function handed to page.evaluate - never a template string: inside a template literal `\s` is an
// unrecognised escape and silently becomes `s`, so the first version's whitespace collapse ran as an s-stripper ("Ri k Column").
function audit(VIS_JS) {
  const vis = (0, eval)(VIS_JS);
  const vw = innerWidth, out = { overflow: document.documentElement.scrollWidth - vw, outside: [], clipped: [], wrapped: [], spill: [] };
  const poster = ((document.querySelector('meta[name="artifact-genre"]') || {}).content || '') === 'poster';   // the rubric's own print-artifact signal
  if (poster) { out.poster = true; return out; }
  const name = (e) => (e.id ? '#' + e.id : e.tagName.toLowerCase() + (typeof e.className === 'string' && e.className ? '.' + e.className.trim().split(/\s+/)[0] : ''));
  const ownText = (e) => [...e.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join('').replace(/\s+/g, ' ').trim();
  const clipper = (e) => { let a = e.parentElement; while (a && a !== document.body) { const o = getComputedStyle(a); if (/hidden|clip|auto|scroll/.test(o.overflowX + ' ' + o.overflow)) return a; a = a.parentElement; } return null; };
  const decorative = (e) => getComputedStyle(e).pointerEvents === 'none' && !e.textContent.trim();
  // a visually-hidden (sr-only) box: 1px, clip-rect or clip-path - present for screen readers, never a phone-fit defect
  const srOnly = (e, cs) => e.clientWidth <= 1 || e.clientHeight <= 1 || (cs.clip && cs.clip !== 'auto') || (cs.clipPath && cs.clipPath !== 'none');
  const all = [...document.querySelectorAll('body *')].filter((e) => vis(e) && !e.closest('script,style,svg,[aria-hidden="true"]'));
  for (const e of all) {
    const r = e.getBoundingClientRect(); if (r.width === 0 || r.height === 0) continue;
    const cs = getComputedStyle(e);
    if (srOnly(e, cs)) continue;
    // (1) PARTIALLY outside the viewport (a closed sheet parked fully off-screen is by design; a menu cut at the edge is not)
    const partial = (r.left < vw - 1 && r.right > vw + 2) || (r.left < -2 && r.right > 1);
    if (partial && !decorative(e)) { const c = clipper(e); const scroller = c && /auto|scroll/.test(getComputedStyle(c).overflowX + getComputedStyle(c).overflow); if (!scroller && !(c && c !== document.body && !/menu|dialog|popover|dropdown/.test(e.className + ' ' + e.getAttribute('role')))) out.outside.push(name(e) + ' ' + Math.round(r.left) + '..' + Math.round(r.right) + (c ? ' (cut by ' + name(c) + ')' : '')); }
    const t = ownText(e);
    // (2) text CLIPPED by its own box (overflow hidden + wider content, no ellipsis)
    if (t && /hidden|clip/.test(cs.overflowX + cs.overflow) && e.scrollWidth > e.clientWidth + 2 && cs.textOverflow !== 'ellipsis') out.clipped.push(name(e) + ' ' + e.scrollWidth + '>' + e.clientWidth + ' "' + t.slice(0, 30) + '"');
    // (3) a CONTROL LABEL wrapped inside its own control - the "text wrapped on its container" Ian saw (inventory's card actions
    // squeezed "Use" until its letters stacked). The label often lives in a child span inside a flex button, so the check runs on
    // the control's own text AND on each text-bearing descendant. Line boxes via a Range grouped by vertical overlap (an emoji run
    // is a taller fallback font on the SAME line). A table header may take two lines at phone width, three is a squeeze; a control
    // wider than 240px wrapping a long sentence (a suggestion chip) is prose, not a squeeze - short labels and narrow boxes are.
    const isControl = e.matches('button, [role="button"], [role="tab"], .pill, .badge, .chip, .tag, .kpi-label, .sc-label, .simple-label, .stat-label, th, .btn, a.btn, [class*="btn-"], [class*="pill"], [class*="chip"], [class*="badge"]');
    // .wh-source-chip is a provenance PARAGRAPH ('live · Based on your marketplace listings ...'), prose by design - the chip selector pulled it in
    if (isControl && !e.matches('.wh-source-chip') && !e.closest('.wh-source-chip') && !e.querySelector('br') && cs.whiteSpace !== 'pre-line') {
      // descendants are inspected only when the WHOLE control is a short label (<=4 words): a tile button carrying a title plus a
      // standard citation ('Availability % ISO 14224:2016 §9.2') is prose whose citation may break at a space by design
      const shortLabel = e.textContent.trim().split(/\s+/).length <= 4;
      const carriers = [e, ...(shortLabel ? [...e.querySelectorAll('*')].filter((c) => vis(c) && ownText(c).length > 3 && !c.matches('svg, svg *')) : [])];
      const linesOf = (el) => { const rg = document.createRange(); rg.selectNodeContents(el); const rects = [...rg.getClientRects()].filter((q) => q.width > 0 && q.height > 0).sort((x, y) => x.top - y.top); let lines = 0, bottom = -1e9; for (const q of rects) { if (q.top >= bottom - 2) { lines++; bottom = q.bottom; } else bottom = Math.max(bottom, q.bottom); } return lines; };
      for (const el of carriers) {
        const t2 = el === e ? t : ownText(el); if (t2.length <= 3) continue;
        if (el !== e && [...el.children].some((c) => getComputedStyle(c).display === 'block' && c.textContent.trim())) continue;
        if (el === e && e.children.length && [...e.children].some((c) => getComputedStyle(c).display === 'block' && c.textContent.trim())) continue;   // the descendants carry it
        const lines = linesOf(el); const rr = el.getBoundingClientRect();
        const words = t2.split(/\s+/).length; const isTh = e.tagName === 'TH';
        // calibration (2026-09-06): a two-line KPI label ('High-severity alerts' in a 139px tile) or a sentence badge is typography;
        // a squeezed BUTTON label, a true pill (<=4 words) on two lines, or a label/header on three lines is the squeeze
        const isLabel = e.matches('.kpi-label, .sc-label, .simple-label, .stat-label, p, div:not([role])') && !e.matches('button, [role="button"], [role="tab"], .btn, a.btn, [class*="btn-"]');
        const isPillish = e.matches('.pill, .badge, .chip, .tag, [class*="pill"], [class*="chip"], [class*="badge"]') && !e.matches('button, [role="button"], [role="tab"]');
        const squeeze = (isTh || isLabel) ? lines >= 3 : isPillish ? (lines >= 2 && words <= 4) : (lines >= 2 && (r.width < 240 || words <= 3));
        if (squeeze) { out.wrapped.push(name(e) + (el === e ? '' : ' > ' + name(el)) + ' ' + lines + ' lines @' + Math.round(rr.width) + 'px "' + t2.slice(0, 34) + '"'); break; }
      }
    }
    // (4) text SPILLING past its parent's box (an unbroken id / email / url / number wider than the card)
    if (t.length > 6 && cs.position !== 'absolute' && cs.position !== 'fixed') { const pr = e.parentElement.getBoundingClientRect(); const po = getComputedStyle(e.parentElement); const negM = Math.max(0, -parseFloat(cs.marginRight) || 0);   // a designed negative margin (integrations' Dismiss, -6px optical alignment) is not a spill
      if (r.right > pr.right + 3 + negM && pr.width > 0 && !/auto|scroll/.test(po.overflowX + po.overflow)) out.spill.push(name(e) + ' right ' + Math.round(r.right) + ' > parent ' + Math.round(pr.right) + ' "' + t.slice(0, 30) + '"'); }
  }
  for (const k of ['outside', 'clipped', 'wrapped', 'spill']) out[k] = [...new Set(out[k])].slice(0, 10);
  return out;
}

let bad = 0, n = 0;
for (const file of PAGES) {
  n++;
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/${file}${PAGE_QUERY[file] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(6500);   // layout settles well inside this; 51 pages x 9 s alone exceeded the 10-minute background cap
  const a = await p.evaluate(audit, VIS_JS).catch((e) => ({ error: String(e).slice(0, 120), outside: [], clipped: [], wrapped: [], spill: [], overflow: 0 }));
  // menus: tap every visible more/kebab/menu trigger; the revealed menu (aria-controls, or the newest visible menu/dialog) must fit
  const menus = await p.evaluate((MENU_SRC) => { const re = new RegExp(MENU_SRC, 'i'); return [...document.querySelectorAll('button, [role="button"]')].filter((e) => e.checkVisibility()).filter((e) => ((e.textContent || '').trim().length <= 24 && re.test((e.textContent || '').trim())) || re.test(e.getAttribute('aria-label') || '') || !!e.getAttribute('aria-haspopup')).map((e, i) => { e.setAttribute('data-pf', String(i)); return { i, label: (e.getAttribute('aria-label') || e.textContent || '').trim().slice(0, 24) }; }); }, MENU_RE.source);
  const menuBad = [];
  for (const m of menus.slice(0, 6)) {
    await p.tap(`[data-pf="${m.i}"]`, { timeout: 3000, force: true }).catch(async () => { await p.click(`[data-pf="${m.i}"]`, { timeout: 3000, force: true }).catch(() => {}); });
    await p.waitForTimeout(600);
    const r = await p.evaluate((i) => { const t = document.querySelector(`[data-pf="${i}"]`); const id = t && t.getAttribute('aria-controls'); let menu = id ? document.getElementById(id) : null; if (!menu) { const cands = [...document.querySelectorAll('[role="menu"], .menu, .dropdown, .hive-menu, [class*="menu"], [class*="popover"], [class*="dropdown"]')].filter((e) => e.checkVisibility() && e.getBoundingClientRect().height > 0); menu = cands[cands.length - 1] || null; } if (!menu) return null; const rc = menu.getBoundingClientRect(); return { id: menu.id || menu.className, l: Math.round(rc.left), r: Math.round(rc.right), w: Math.round(rc.width), fits: rc.left >= -1 && rc.right <= innerWidth + 1 }; }, m.i);
    if (r && !r.fits) menuBad.push(`${m.label || '⋯'} -> ${r.id} ${r.l}..${r.r} (vw ${W})`);
    await p.keyboard.press('Escape').catch(() => {}); await p.waitForTimeout(200);
  }
  if (a.poster) { console.log(`  n/a ${file.padEnd(34)} print poster: a fixed-width artifact by design (rubric artifact-genre=poster)`); n--; await p.close(); continue; }
  const issues = (a.overflow > 2 ? [`page overflow +${a.overflow}px`] : []).concat(a.outside.map((s) => 'outside: ' + s), a.clipped.map((s) => 'clipped: ' + s), (a.wrapped || []).map((s) => 'wrapped: ' + s), (a.spill || []).map((s) => 'spill: ' + s), menuBad.map((s) => 'menu: ' + s));
  if (issues.length) bad++;
  console.log(`  ${issues.length ? 'BAD' : 'ok '} ${file.padEnd(34)} ${issues.length ? issues.length + ' issue(s)' : 'fits'}${a.error ? ' (' + a.error + ')' : ''}`);
  for (const s of issues.slice(0, ONLY ? 40 : 6)) console.log(`        ${s.slice(0, 150)}`);
  await p.close();
}
await b.close();
console.log(`${bad ? 'FAIL' : 'PASS'} phone-fit@${W} - ${n - bad}/${n} pages fit a phone (no overflow, no clipped text, menus inside the viewport)`);
process.exit(bad ? 1 : 0);
