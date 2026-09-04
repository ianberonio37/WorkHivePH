// prove_control_within_viewport — a tappable control must not sit past the floor viewport's edge.
//
// MEASURED 2026-08-27 (T113). "← Back to Basic Worker" ran +45px past a 390 viewport on inventory and
// +35px on logbook, with its parent computing overflow:visible — so part of a real control was simply
// off-screen on the smallest phone the platform supports.
//
// ★WHY NOTHING CAUGHT IT. The page never SCROLLS horizontally: the navbar is a fixed-height flex row,
// the overflowing item is inside it, and the document's scrollWidth never grows. Every check that asks
// "does this page scroll sideways at 390?" — the usual Z2 / WCAG 1.4.10 shape — reads perfectly clean
// while a button hangs over the edge. Scroll is a SYMPTOM of overflow, not a definition of it.
//
// ★AND THE ROOT WAS NOT THE OVERFLOWING ELEMENT. Shortening the button did nothing; the row was
// over-full because the sibling group would not shrink (a flex item defaults to min-width:auto and
// refuses to go below its content width). min-w-0 + truncate on that group fixed both pages. So this
// prover reports the element that ENDS UP outside, and the fix usually lives in its siblings.
//
// THE ORACLE: at 390, an element that (a) renders, (b) carries its own text or is a link/button,
// (c) is not inside a scrollable or clipping ancestor, and (d) is not fixed/absolute decoration,
// must not extend past the viewport's right edge. Anything that does is off-screen to a real thumb.
//
// USAGE:  node tools/prove_control_within_viewport.mjs [--page <name>] [--gate]
// OUTPUT: control_within_viewport_report.json  (narrowed runs write their own, never the sweep's)
import { writeFileSync } from 'fs';
import { chromium } from '@playwright/test';
import { signIn, SEEDER } from './live_page_journeys.mjs';

const args = process.argv.slice(2);
const GATE = args.includes('--gate');
const PAGE_ONLY = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();
// The platform's declared floor is 320 (T113 / Z2 WCAG 1.4.10), not 390 — 390 is merely the
// common phone. A gate that guards the wider box cannot see what only breaks at the narrower one,
// so the width is a parameter and the sweep runs the FLOOR. Moving it from 390 to 320 immediately
// surfaced two more offenders that 390 had hidden.
const WIDTH = (() => { const i = args.indexOf('--width'); return i >= 0 ? parseInt(args[i + 1], 10) : 320; })();
// A non-default width narrows the run, so it writes its own report and never the sweep's.
const NARROW = [PAGE_ONLY ? `page-${PAGE_ONLY}` : '', (args.indexOf('--width') >= 0 ? `w-${WIDTH}` : '')]
  .filter(Boolean).join('.').replace(/[^\w.-]+/g, '_');
const REPORT = NARROW ? `control_within_viewport_report.${NARROW}.json`
                      : 'control_within_viewport_report.json';

// All 22 banked app pages, not a subset — a floor gate that guards two-thirds of the roster leaves
// the rest to be discovered by a user. project-report carries its param because a paramless walk is
// a DIFFERENT page: it renders the no-project state, whose layout is not the one anyone prints.
const PAGES = ['index.html', 'logbook.html', 'inventory.html', 'pm-scheduler.html', 'hive.html',
               'community.html', 'dayplanner.html', 'alert-hub.html', 'asset-hub.html',
               'analytics.html', 'skillmatrix.html', 'achievements.html', 'marketplace.html',
               'report-sender.html', 'assistant.html', 'voice-journal.html',
               'analytics-report.html', 'engineering-design.html', 'project-manager.html',
               'project-report.html?project_id=170cf794-a67d-4791-afdc-cffc95042cac',
               'public-feed.html', 'resume.html', 'shift-brain.html'];

const probe = (w) => {
  const out = [];
  const label = (el) => (el.id ? '#' + el.id
    : (typeof el.className === 'string' && el.className.trim())
      ? el.tagName.toLowerCase() + '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.')
      : el.tagName.toLowerCase());
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    const st = getComputedStyle(el);
    if (st.position === 'fixed' || st.position === 'absolute') continue;
    if (st.visibility === 'hidden' || st.opacity === '0') continue;
    const tag = el.tagName.toLowerCase();
    const ownText = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent.trim()).join('');
    const isControl = tag === 'a' || tag === 'button' || el.getAttribute('role') === 'button';
    if (!ownText && !isControl) continue;
    // an ancestor that scrolls or clips means the overflow is contained by design
    let clipped = false;
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const ps = getComputedStyle(p);
      if (/(auto|scroll|hidden)/.test(ps.overflowX) || /(auto|scroll|hidden)/.test(ps.overflow)) { clipped = true; break; }
    }
    if (clipped) continue;
    if (r.right > w + 1) {
      out.push({ el: label(el), tag, control: isControl, over: Math.round(r.right - w),
                 text: (el.textContent || '').trim().slice(0, 48) });
    }
  }
  return out;
};

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: WIDTH, height: 844 } });
const s = await signIn(ctx, 'supervisor');
if (!s.ok) {
  console.log(`SKIP control-within-viewport — sign-in unavailable: ${s.err || 'unknown'}`);
  await browser.close();
  process.exit(0);
}

const pages = PAGES.filter(p => !PAGE_ONLY || p === PAGE_ONLY);
const rows = [];
for (const f of pages) {
  const page = await ctx.newPage();
  try {
    await page.goto(`${SEEDER}/workhive/${f}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(4000);
    const offenders = await page.evaluate(probe, WIDTH);
    rows.push({ page: f, offenders });
  } catch (e) {
    rows.push({ page: f, err: String(e).slice(0, 90), offenders: [] });
  }
  await page.close();
}
await browser.close();

const bad = rows.filter(r => r.offenders.length);
const controls = bad.flatMap(r => r.offenders.filter(o => o.control).map(o => ({ page: r.page, ...o })));
writeFileSync(REPORT, JSON.stringify({ width: WIDTH, hive: s.hive, pages: rows.length, rows }, null, 2));

console.log(`control-within-viewport @ ${WIDTH} — pages ${rows.length}, with overflow ${bad.length}, CONTROLS off-screen ${controls.length}`);
for (const r of bad) {
  for (const o of r.offenders.slice(0, 4)) {
    console.log(`    ${r.page.padEnd(22)} ${o.control ? 'CONTROL' : 'text   '} ${o.el} +${o.over}px  "${o.text}"`);
  }
}
if (controls.length) {
  console.log('\nFAIL — part of a tappable control sits past the edge at the floor viewport, and the page');
  console.log('  does not scroll, so no scroll-based check will ever report it. The fix is usually a');
  console.log('  SIBLING that will not shrink: min-w-0 on the flex group + truncate on its long label.');
  process.exit(GATE ? 1 : 0);
}
console.log('\nPASS — every tappable control renders inside the floor viewport.');
