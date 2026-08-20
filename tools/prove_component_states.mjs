// prove_component_states.mjs — the CK ui-state oracles: loading / skeleton / busy / disabled / populated.
//
// THE STATES THIS ORACLE ASKS ABOUT DO NOT EXIST WHEN THE PAGE IS SETTLED. Reading a finished board
// found 0 skeleton nodes and 0 aria-busy on hive — and hive paints NINE skeleton rows during load. So
// the recorder is installed with addInitScript, before any of the page's own script runs, and watches
// from the first mutation onward. Measuring after settle is how "this page has no loading state" gets
// banked about a page that has one.
//
// AND THE RECORDER CARRIES A POSITIVE CONTROL, which earned its place immediately: the first version
// scanned `root.querySelectorAll('*')` — the DESCENDANTS of each added node and never the node itself —
// so a skeleton appended as a leaf was invisible. The injected control probe (a childless div) was not
// counted, which is exactly how the bug surfaced. Counts before/after the fix: hive 4→9, inventory 4→9,
// asset-hub 5→11, and aria-busy 0→1 on three pages. A zero from this instrument only means something
// because the control proves it can see a one.
//
// TWO CORRECTIONS THE FIRST RUN FORCED, both over-reports, neither banked.
//   analytics  reported a STUCK `card skeleton` at 4.2s. It is 648x260 and its copy reads "Fetching
//              maintenance records from your..." — and it is GONE by 8.5s. A slow AI fetch, not a stuck
//              skeleton. A single settle window cannot tell those apart, so a candidate is now
//              RE-CHECKED after a longer wait before it is called stuck.
//   assistant  reported a STUCK `w-2 h-2 rounded-full animate-pulse`. It is an 8x8 pixel dot beside
//              "Work Assistant / Leandro Marquez" inside #chat-screen — a live-status indicator, not a
//              placeholder. Tailwind's `animate-pulse` serves both, so the class alone is not evidence:
//              it now counts as a skeleton only at placeholder GEOMETRY (>=24px in both axes, or an
//              explicit skeleton/shimmer/wh-skel class). An 8px dot is a status light; a 648x260 block
//              is a skeleton.
//
// WHAT EACH VERDICT MEANS:
//   skeleton  a skeleton/shimmer node appeared DURING load  → the component has a loading state
//   stuck     a skeleton is STILL visible after settle      → the defect: a permanent shimmer that
//             every other gate misses (200 OK, rows returned, promise resolved, axe clean)
//   busy      an aria-busy=true appeared during load        → the state is announced to a screen reader
//   disabled  a control was disabled during load
//   populated the component holds real content after settle
//
// Read-only: navigation and observation. No clicks, no typing, no writes.
//
//   node tools/prove_component_states.mjs            # all 22 roster pages
//   node tools/prove_component_states.mjs --gate     # exit 1 on a STUCK skeleton or a failed control
//   node tools/prove_component_states.mjs --page hive
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { signIn, ACCOUNTS, SEEDER, assertSignedIn } from './live_page_journeys.mjs';

const ORIGIN = process.env.WH_ORIGIN || SEEDER || 'http://127.0.0.1:5000';
const PAGES = ['index', 'hive', 'logbook', 'inventory', 'pm-scheduler', 'project-manager',
  'dayplanner', 'asset-hub', 'analytics', 'alert-hub', 'skillmatrix', 'shift-brain',
  'voice-journal', 'assistant', 'community', 'public-feed', 'achievements',
  'engineering-design', 'resume', 'report-sender', 'project-report', 'analytics-report',
  // ★MARKETPLACE SURFACES, added 2026-08-20. The marketplace bank carries the SAME families
  // (BF-ui-layout, BG-ui-state, BH-ui-visual, BI-ux-comprehension) and 741 of its rows just
  // expired when utils.js moved -- but this prover's roster was the 22 PRODUCT pages, so
  // citing it for a marketplace row would claim a gate measured a surface it never opened.
  // Widening the roster is a MEASUREMENT CHANGE, not a regression: expect new findings here
  // the way the no-em-dash gate went 0 -> 299 when its glob was widened. Re-run clean and
  // confirm the teeth still fire on these surfaces BEFORE banking anything against them.
  'marketplace', 'marketplace-seller', 'marketplace-seller-profile', 'platform-actions'];

const args = process.argv.slice(2);
const GATE = args.includes('--gate');
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

const RECORDER = () => {
  window.__whStates = { skel: 0, skelIds: [], busy: 0, busyIds: [], disabled: 0, lastSkelAt: null };
  const EXPLICIT = /skeleton|shimmer|placeholder-glow|wh-skel/i;
  const PULSE = /animate-pulse/i;
  // A class name alone is not evidence. `animate-pulse` is Tailwind's generic pulse and is used for
  // live-status dots as well as placeholders, so it only counts at placeholder geometry.
  const SKEL = (e) => {
    const c = String(e.className || '');
    if (EXPLICIT.test(c)) return true;
    if (!PULSE.test(c)) return false;
    const b = e.getBoundingClientRect ? e.getBoundingClientRect() : { width: 0, height: 0 };
    return b.width >= 24 && b.height >= 24;
  };
  const one = (e) => {
    if (!e || e.nodeType !== 1) return;
    const S = window.__whStates;
    const c = String(e.className || '');
    if (SKEL(e)) {
      S.skel++; S.lastSkelAt = Math.round(performance.now());
      if (S.skelIds.length < 10) S.skelIds.push(e.id || c.slice(0, 32));
    }
    if (e.getAttribute && e.getAttribute('aria-busy') === 'true') {
      S.busy++; if (S.busyIds.length < 8) S.busyIds.push(e.id || e.tagName);
    }
    if (e.disabled === true) S.disabled++;
  };
  // one(root) FIRST — the descendants-only version missed every leaf-level skeleton.
  const scan = (root) => {
    one(root);
    if (root.querySelectorAll) for (const e of root.querySelectorAll('*')) one(e);
  };
  const mo = new MutationObserver((muts) => {
    for (const m of muts) {
      for (const n of m.addedNodes) scan(n);
      if (m.type === 'attributes') one(m.target);
    }
  });
  const start = () => mo.observe(document.documentElement, {
    childList: true, subtree: true, attributes: true,
    attributeFilter: ['class', 'aria-busy', 'disabled'],
  });
  if (document.documentElement) start();
  else document.addEventListener('readystatechange', start, { once: true });
};

const READ = () => {
  const S = window.__whStates || null;
  const vis = (el) => {
    const s = getComputedStyle(el); const b = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0.01
      && b.width > 0 && b.height > 0;
  };
  const EXPLICIT = /skeleton|shimmer|placeholder-glow|wh-skel/i;
  const isSkel = (e) => {
    const c = String(e.className || '');
    if (EXPLICIT.test(c)) return true;
    if (!/animate-pulse/i.test(c)) return false;
    const b = e.getBoundingClientRect();
    return b.width >= 24 && b.height >= 24;
  };
  const stuck = [...document.querySelectorAll('*')].filter((e) => isSkel(e) && vis(e));
  const before = S ? S.skel : -1;
  const probe = document.createElement('div');
  probe.className = 'skeleton wh-control-probe';
  document.body.appendChild(probe);
  return new Promise((res) => setTimeout(() => {
    const after = window.__whStates ? window.__whStates.skel : -1;
    probe.remove();
    const main = document.querySelector('#wh-main-content, main, body');
    res({
      armed: !!S,
      controlCaught: after > before,
      skelDuringLoad: before,
      skelIds: S ? S.skelIds.slice(0, 6) : [],
      lastSkelAtMs: S ? S.lastSkelAt : null,
      busyDuringLoad: S ? S.busy : -1,
      busyIds: S ? S.busyIds.slice(0, 5) : [],
      disabledDuringLoad: S ? S.disabled : -1,
      stuckNow: stuck.map((e) => { const b = e.getBoundingClientRect();
        return (e.id || String(e.className).slice(0, 24)) + '@' + Math.round(b.width) + 'x'
               + Math.round(b.height); }).slice(0, 5),
      populatedChars: main ? (main.textContent || '').replace(/\s+/g, ' ').trim().length : 0,
      nodes: document.querySelectorAll('*').length,
    });
  }, 300));
};

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
await assertSignedIn(signIn(ctx, 'supervisor'));
await ctx.addInitScript(RECORDER);
const page = await ctx.newPage();

const results = [];
for (const p of (ONE ? [ONE.replace(/\.html$/, '')] : PAGES)) {
  let rec;
  try {
    await page.goto(`${ORIGIN}/${p}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForTimeout(4200);
    rec = { page: p, ...(await page.evaluate(READ)) };
    // A CANDIDATE IS RE-CHECKED, NOT CONVICTED. analytics' 648x260 "Fetching maintenance records"
    // skeleton is still up at 4.2s and gone by 8.5s - slow, not stuck - so a first-pass hit waits and
    // measures again, and only a skeleton that survives BOTH windows is reported.
    if ((rec.stuckNow || []).length) {
      rec.stuckFirstPass = rec.stuckNow;
      await page.waitForTimeout(9000);
      const again = await page.evaluate(READ);
      rec.stuckNow = again.stuckNow;
      rec.recheckedAtMs = 13200;
      if (!(again.stuckNow || []).length) rec.clearedLate = true;
    }
  } catch (e) {
    rec = { page: p, error: String(e).slice(0, 140) };
  }
  results.push(rec);
  console.log(`  ${p.padEnd(20)} skel=${String(rec.skelDuringLoad).padStart(3)}`
    + ` busy=${String(rec.busyDuringLoad).padStart(2)}`
    + ` disabled=${String(rec.disabledDuringLoad).padStart(2)}`
    + ` chars=${String(rec.populatedChars).padStart(6)}`
    + ` ctl=${rec.controlCaught ? 'ok' : 'FAIL'}`
    + (rec.stuckNow && rec.stuckNow.length ? `  STUCK: ${rec.stuckNow.join(',')}` : ''));
}
await browser.close();

const noCtl = results.filter((r) => r.controlCaught !== true);
const stuck = results.filter((r) => (r.stuckNow || []).length);
writeFileSync('component_states_report.json', JSON.stringify({
  ran: new Date().toISOString(), origin: ORIGIN, role: 'supervisor',
  pages: results, controlFailed: noCtl.map((r) => r.page), stuck: stuck.map((r) => r.page),
}, null, 1));

console.log(`\n  ${results.length} page(s) — ${stuck.length} with a STUCK skeleton, `
  + `${noCtl.length} where the control did not fire`);
console.log('  wrote component_states_report.json');
if (GATE) {
  if (noCtl.length) {
    console.log(`  FAIL — the positive control did not fire on: ${noCtl.map((r) => r.page).join(', ')}`
      + ' (a zero from this instrument would be meaningless there)');
    process.exit(1);
  }
  if (stuck.length) {
    console.log(`  FAIL — skeleton still visible after settle on: ${stuck.map((r) => r.page).join(', ')}`);
    process.exit(1);
  }
  console.log('  PASS — every page\'s control fired and no skeleton outlived its load');
}
