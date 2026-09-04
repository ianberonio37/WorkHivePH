// prove_flow_fits_the_floor — a flow's OPENED state must fit the floor viewport too.
//
// ★THE GAP (T113). prove_control_within_viewport walks pages AT REST. But the controls that decide
// whether work gets recorded do not exist at rest: the PM completion sheet, the add-task sheet,
// the handover panel are all built or revealed mid-flow, and each is a DIFFERENT layout from the
// page that hosts it. A resting sweep can be green over all 16 pages while the Save button of the
// sheet a worker must use is off the edge — the same class T113 already found twice, just one
// interaction deeper than any resting check can reach.
//
// THE ORACLE: drive each flow to its committing state, then require every control in the opened
// surface to render INSIDE the floor viewport (320) — nothing past the right edge, nothing past
// the bottom of a sheet that cannot scroll. Read-only: the walk opens and closes, never saves.
//
// USAGE:  node tools/prove_flow_fits_the_floor.mjs [--flow <id>] [--width N] [--gate]
// OUTPUT: flow_fits_the_floor_report.json  (narrowed runs write their own)
import { writeFileSync } from 'fs';
import { chromium } from '@playwright/test';
import { signIn, SEEDER } from './live_page_journeys.mjs';

const args = process.argv.slice(2);
const GATE = args.includes('--gate');
const FLOW_ONLY = (() => { const i = args.indexOf('--flow'); return i >= 0 ? args[i + 1] : null; })();
const WIDTH = (() => { const i = args.indexOf('--width'); return i >= 0 ? parseInt(args[i + 1], 10) : 320; })();
const NARROW = [FLOW_ONLY ? `flow-${FLOW_ONLY}` : '', args.indexOf('--width') >= 0 ? `w-${WIDTH}` : '']
  .filter(Boolean).join('.').replace(/[^\w.-]+/g, '_');
const REPORT = NARROW ? `flow_fits_the_floor_report.${NARROW}.json` : 'flow_fits_the_floor_report.json';

const PM_ASSET_QUERY = '?asset=' + encodeURIComponent('Amada HFE 80-25');

const FLOWS = [
  // T10 — the worker completes an assigned PM. The committing control is the completion sheet's
  // Save; if it is off the floor, the PM cannot be recorded on the smallest phone the platform
  // supports, which is the phone most likely to be on a plant floor.
  //
  // The walk arrives the way a worker does — alert-hub hands pm-scheduler an ?asset=, the detail
  // opens, and a real scope item's mark-done control is CLICKED. An earlier cut called openSheet()
  // by hand and measured an EMPTY sheet: same seven controls whatever the task, because markDone()
  // is what fills in the item text, the asset name, the frequency badge and the findings fields.
  // Measuring the unpopulated shell would have proved the sheet's chrome fits, not the sheet.
  { id: 'pm-complete', traj: 'T10', page: 'pm-scheduler.html', query: PM_ASSET_QUERY,
    open: `(() => { const b = document.querySelector('[onclick^="markDone("]');
                    if (!b) return 'no mark-done control';
                    b.click(); return 'markDone clicked'; })()`,
    surface: '#completion-sheet', must: ['#sheet-save-btn', '#sheet-item-text'] },
  // T10b — recording a DEFERRAL is the honest alternative to a false completion, so it has to be
  // reachable on the same phone, in the same populated sheet.
  { id: 'pm-defer', traj: 'T10', page: 'pm-scheduler.html', query: PM_ASSET_QUERY,
    open: `(() => { const b = document.querySelector('[onclick^="markDone("]');
                    if (!b) return 'no mark-done control';
                    b.click(); return 'markDone clicked'; })()`,
    surface: '#completion-sheet', must: ['#sheet-defer-btn'] },
  // T13 — the shift handover read. Its controls are what a worker touches at clock-in.
  { id: 'handover', traj: 'T13', page: 'dayplanner.html', open: `'rest'`, surface: 'body', must: [] },
  // T17 — the level-up moment. This one is a CENTRED FIXED overlay, so the edge that matters is the
  // BOTTOM, not the right: a celebration card taller than a 320x844 phone puts its only dismiss
  // button below the fold, and because the overlay does not scroll there is no gesture that reaches
  // it — the reward moment becomes a trap. Driven through showLevelUpModal() with a REAL achievement
  // id so the card carries its badge, heading and tier line; an empty overlay is a different height.
  { id: 'levelup', traj: 'T17', page: 'achievements.html',
    open: `(() => { const k = (typeof ACHIEVEMENT_DEFS === 'object' && ACHIEVEMENT_DEFS) ? Object.keys(ACHIEVEMENT_DEFS)[0] : null;
                    if (!k || typeof showLevelUpModal !== 'function') return 'no level-up opener';
                    showLevelUpModal(k, 5, true); return 'showLevelUpModal'; })()`,
    surface: '#levelup-overlay', must: ['#levelup-close', '#levelup-heading'], checkBottom: true },
];

const measure = ({ surfaceSel, mustSel, w, h, checkBottom }) => {   // page.evaluate passes ONE arg
  const root = document.querySelector(surfaceSel);
  if (!root) return { missing: true };
  const rr = root.getBoundingClientRect();
  const bad = [];
  const label = (el) => el.id ? '#' + el.id
    : el.tagName.toLowerCase() + '.' + String(el.className || '').trim().split(/\s+/).slice(0, 2).join('.');
  const scrolls = (el) => {
    for (let p = el; p && p !== document.body; p = p.parentElement) {
      const s = getComputedStyle(p);
      if (/(auto|scroll)/.test(s.overflowY) || /(auto|scroll|hidden)/.test(s.overflowX)) return true;
    }
    return false;
  };
  for (const el of root.querySelectorAll('button, a, input, select, textarea, [role="button"]')) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    const st = getComputedStyle(el);
    if (st.visibility === 'hidden' || st.opacity === '0') continue;
    if (r.right > w + 1 && !scrolls(el)) bad.push({ el: label(el), over: Math.round(r.right - w), axis: 'right' });
    // A fixed, non-scrolling overlay has no gesture that reaches past the fold, so a control below
    // the viewport bottom is unreachable rather than merely out of sight. Only checked where the
    // flow asks for it, because an ordinary PAGE is expected to extend past the bottom — that is
    // what scrolling is for, and flagging it everywhere would drown the real finding.
    if (checkBottom && r.bottom > h + 1 && !scrolls(el)) {
      bad.push({ el: label(el), over: Math.round(r.bottom - h), axis: 'bottom' });
    }
  }
  const missing = mustSel.filter(s => {
    const e = document.querySelector(s);
    if (!e) return true;
    const r = e.getBoundingClientRect();
    return !r.width || !r.height || e.offsetParent === null;
  });
  return { open: rr.height > 0, bad, missing, controls: root.querySelectorAll('button, a, input, select, textarea').length };
};

// ── SELFTEST: synthetic negatives, one per way this can fail ────────────────────────────────
// This is a PROACTIVE guard — the property holds today, so there is no pre-fix world to resurrect
// (the same distinction validate_bounded_list_offers_the_rest.py records). Its teeth therefore
// have to be manufactured, and each part needs its own, because the parts fail independently:
// running at an absurd width catches the off-screen half but NOT the missing-control half — proven
// by --width 200, where the handover went RED and both PM sheets still passed.
if (args.includes('--selftest')) {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 320, height: 844 } });
  const s = await signIn(ctx, 'supervisor');
  if (!s.ok) { console.log('SKIP selftest — sign-in unavailable'); await browser.close(); process.exit(0); }
  const page = await ctx.newPage();
  await page.goto(`${SEEDER}/workhive/pm-scheduler.html${PM_ASSET_QUERY}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(5000);
  await page.evaluate(`(() => { const b = document.querySelector('[onclick^="markDone("]'); if (b) b.click(); })()`);
  await page.waitForTimeout(1200);
  const cases = [
    ['off-screen control detected',
     await page.evaluate(measure, { surfaceSel: '#completion-sheet', mustSel: [], w: 40, h: 844, checkBottom: false }),
     (r) => (r.bad || []).length > 0],
    ['missing required control detected',
     await page.evaluate(measure, { surfaceSel: '#completion-sheet', mustSel: ['#no-such-control'], w: 320, h: 844, checkBottom: false }),
     (r) => (r.missing || []).length > 0],
    ['absent surface detected',
     await page.evaluate(measure, { surfaceSel: '#no-such-sheet', mustSel: [], w: 320, h: 844, checkBottom: false }),
     (r) => r.missing === true],
    ['the real sheet is clean at the floor',
     await page.evaluate(measure, { surfaceSel: '#completion-sheet', mustSel: ['#sheet-save-btn'], w: 320, h: 844, checkBottom: false }),
     (r) => (r.bad || []).length === 0 && (r.missing || []).length === 0],
    // The bottom axis needs its own pair: one proving it BITES, and one proving the flag actually
    // GATES it. Without the second, checkBottom could be ignored and every ordinary page would be
    // flagged for extending past the fold — which is what scrolling is for, so the gate would be
    // noise rather than a finding.
    ['off-bottom control detected when the flow asks',
     await page.evaluate(measure, { surfaceSel: '#completion-sheet', mustSel: [], w: 320, h: 40, checkBottom: true }),
     (r) => (r.bad || []).some(b => b.axis === 'bottom')],
    ['bottom is NOT checked when the flow does not ask',
     await page.evaluate(measure, { surfaceSel: '#completion-sheet', mustSel: [], w: 320, h: 40, checkBottom: false }),
     (r) => !(r.bad || []).some(b => b.axis === 'bottom')],
  ];
  await browser.close();
  let bad = 0;
  for (const [name, res, ok] of cases) {
    const pass = ok(res);
    if (!pass) bad++;
    console.log(`  ${pass ? 'RED as required' : 'NO TEETH'}  ${name}`);
  }
  console.log(bad ? `\nSELFTEST FAILED (${bad}/${cases.length})` : `\nSELFTEST ok — ${cases.length}/${cases.length}`);
  process.exit(bad ? 1 : 0);
}

const browser = await chromium.launch();
const rows = [];
for (const f of FLOWS.filter(x => !FLOW_ONLY || x.id === FLOW_ONLY)) {
  const ctx = await browser.newContext({ viewport: { width: WIDTH, height: 844 } });
  const s = await signIn(ctx, 'supervisor');
  if (!s.ok) { console.log(`SKIP ${f.id} — sign-in unavailable`); await ctx.close(); continue; }
  const page = await ctx.newPage();
  try {
    await page.goto(`${SEEDER}/workhive/${f.page}${f.query || ''}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(5000);
    const how = await page.evaluate(f.open);
    await page.waitForTimeout(1200);
    const m = await page.evaluate(measure, { surfaceSel: f.surface, mustSel: f.must, w: WIDTH, h: 844, checkBottom: !!f.checkBottom });
    rows.push({ ...f, open: undefined, how, ...m });
  } catch (e) {
    rows.push({ id: f.id, traj: f.traj, page: f.page, err: String(e).slice(0, 90) });
  }
  await ctx.close();
}
await browser.close();

// A flow that never opened proves nothing about its layout — it is an instrument failure, and is
// reported as such rather than counted as a clean surface.
const blind = rows.filter(r => r.err || r.missing === true || r.open === false || (r.missing || []).length);
const bad = rows.filter(r => (r.bad || []).length);
writeFileSync(REPORT, JSON.stringify({ width: WIDTH, flows: rows.length, offenders: bad.length, rows }, null, 2));

console.log(`flow-fits-the-floor @ ${WIDTH} — flows ${rows.length}, with off-screen controls ${bad.length}, unreached ${blind.length}`);
for (const r of rows) {
  const tag = r.err ? `ERR ${r.err}` : (r.missing === true ? `surface ${r.surface} absent`
    : (r.missing || []).length ? `required control not rendered: ${r.missing.join(',')}`
    : (r.bad.length ? r.bad.map(b => `${b.el} +${b.over}px`).join(', ') : `ok (${r.controls} controls)`));
  console.log(`    ${(r.traj || '').padEnd(4)} ${String(r.id).padEnd(12)} ${r.how ? String(r.how).padEnd(12) : ''} ${tag}`);
}
if (blind.length) console.log('\nFAIL — a flow never reached its opened state, so it says nothing about the floor.');
if (bad.length) console.log('\nFAIL — a control a worker must press to record their work sits past the floor viewport.');
if (bad.length || blind.length) process.exit(GATE ? 1 : 0);
console.log('\nPASS — every walked flow fits the floor with its committing controls reachable.');
