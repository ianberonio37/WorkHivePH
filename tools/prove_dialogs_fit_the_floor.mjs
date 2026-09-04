// prove_dialogs_fit_the_floor — EVERY dialog in the bank must fit the floor viewport.
//
// ★WHY THIS AND NOT MORE HAND-LISTED FLOWS. prove_flow_fits_the_floor walks four flows I chose,
// and a gate whose denominator is a list I wrote by hand can only ever find what I thought to
// look at. tools/dialog_targets.mjs is already the ONE source of truth for how each V2/V3 dialog
// is opened — every entry's open path READ FROM SOURCE, with its `ref` line — so consuming it
// makes the denominator the platform's own, and any dialog added there is covered here for free.
//
// ★AND THE FLOOR IS WHERE DIALOGS FAIL. A dialog is a fixed, centred, usually non-scrolling
// surface, so the edge that matters is the BOTTOM: a card taller than 320x844 puts its confirm or
// dismiss button below the fold with no gesture that reaches it. That is not "out of sight", it is
// a control that cannot be pressed — and on a resting-page sweep it is invisible, because at rest
// the dialog does not exist.
//
// The walk OPENS and measures; it never submits. Openers come from the registry: a click opener,
// the page's own fn, or `mayStartOpen` for surfaces the page raises itself.
//
// USAGE:  node tools/prove_dialogs_fit_the_floor.mjs [--page <name>] [--width N] [--gate]
// OUTPUT: dialogs_fit_the_floor_report.json  (narrowed runs write their own)
import { writeFileSync } from 'fs';
import { chromium } from '@playwright/test';
import { signIn, SEEDER } from './live_page_journeys.mjs';
import { TARGETS } from './dialog_targets.mjs';

const args = process.argv.slice(2);
const GATE = args.includes('--gate');
const PAGE_ONLY = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();
const WIDTH = (() => { const i = args.indexOf('--width'); return i >= 0 ? parseInt(args[i + 1], 10) : 320; })();
const HEIGHT = 844;
const NARROW = [PAGE_ONLY ? `page-${PAGE_ONLY}` : '', args.indexOf('--width') >= 0 ? `w-${WIDTH}` : '']
  .filter(Boolean).join('.').replace(/[^\w.-]+/g, '_');
const REPORT = NARROW ? `dialogs_fit_the_floor_report.${NARROW}.json` : 'dialogs_fit_the_floor_report.json';

// signedOut / unreachable / notDrivable are excluded for the reasons the registry records — an
// unreachable control is a FINDING already owned there, not a layout result to re-derive here.
// ★A SUPPLEMENT, NOT A CONTRADICTION. Several marketplace overlays ship as EMPTY divs that a
// populating function fills (#overlay-detail is literally `<div id="overlay-detail"></div>` at
// marketplace.html:1007, filled by openDetailSheet(id)). The registry opens them by adding the
// `.open` class, which is the right opener for the layout/exit provers that consume it — but it
// reveals a shell with no controls, so this gate reported "nothing to measure" on seven of the
// platform's COMMERCE dialogs. The fix is here rather than in dialog_targets.mjs on purpose: that
// file is shared by the modal-exit and dialog-layout provers, and changing an opener under them
// is the one-shared-fix-expires-unrelated-claims shape. These entries only ADD a content-bearing
// open path; the registry stays the source of truth for which dialogs exist and how they open.
const CONTENT_OPENERS = {
  // CLICK the card rather than calling the opener: openDetailSheet is declared inside the page's
  // closure, so it is not on `window` and page.evaluate cannot see it — the page-scoped-symbol
  // problem, reported honestly as 'no openDetailSheet' rather than passing an empty sheet. The
  // click is also the real user action, and .listing-card binds by addEventListener on dataset.id
  // (not an inline onclick, which an even earlier cut looked for and did not find).
  'overlay-detail': `(() => { const c = document.querySelector('.listing-card[data-id]');
      if (!c) return 'no listing card rendered';
      c.click(); return 'clicked listing ' + String(c.dataset.id).slice(0, 8); })()`,
};

const SUBJECTS = TARGETS
  .filter(t => !t.unreachable && !t.notDrivable && !t.signedOut)
  .filter(t => !PAGE_ONLY || t.page === PAGE_ONLY);

const measure = ({ sel, w, h }) => {
  const root = document.querySelector(sel);
  if (!root) return { absent: true };
  const rr = root.getBoundingClientRect();
  if (!rr.width || !rr.height) return { notOpen: true };

  // ★THE SUBJECT TEST, and the first run got it wrong. dialog_targets.mjs is a registry of V2/V3
  // SURFACES, and only some of them are fixed overlays — others are panels, tabs and lists that
  // sit in the page's normal flow. Bottom-checking those flagged six "unreachable" controls
  // (asset-hub's FMEA panel, engineering-design's history tab, analytics' summary, alert-hub's AMC
  // card, voice-journal's history list) that a reader reaches by simply SCROLLING THE PAGE. Every
  // one would have been a false finding banked against a page that is fine.
  //
  // The property is unreachability, not off-screen-ness: a control below the fold is only stuck if
  // nothing can scroll to it. So the bottom axis applies ONLY where the surface is fixed AND
  // neither it nor an ancestor scrolls; page-flow content is exempt because the page scrolls.
  let fixed = false;
  for (let p = root; p && p !== document.body; p = p.parentElement) {
    const ps = getComputedStyle(p);
    if (ps.position === 'fixed') { fixed = true; break; }
  }
  const rootScrolls = (() => {
    for (let p = root; p && p !== document.body; p = p.parentElement) {
      const ps = getComputedStyle(p);
      if (/(auto|scroll)/.test(ps.overflowY)) return true;
    }
    return false;
  })();
  const bottomApplies = fixed && !rootScrolls;
  const label = (el) => el.id ? '#' + el.id
    : el.tagName.toLowerCase() + '.' + String(el.className || '').trim().split(/\s+/).slice(0, 2).join('.');
  // A dialog that scrolls INTERNALLY is fine — the control is reachable by scrolling the sheet.
  const scrolls = (el) => {
    for (let p = el; p && p !== document.body; p = p.parentElement) {
      const s = getComputedStyle(p);
      if (/(auto|scroll)/.test(s.overflowY) || /(auto|scroll)/.test(s.overflowX)) return true;
    }
    return false;
  };
  const bad = [];
  const controls = root.querySelectorAll('button, a, input, select, textarea, [role="button"]');
  for (const el of controls) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    const st = getComputedStyle(el);
    if (st.visibility === 'hidden' || st.opacity === '0') continue;
    if (scrolls(el)) continue;
    if (r.right > w + 1) bad.push({ el: label(el), axis: 'right', over: Math.round(r.right - w) });
    if (bottomApplies && r.bottom > h + 1) bad.push({ el: label(el), axis: 'bottom', over: Math.round(r.bottom - h) });
    if (r.left < -1) bad.push({ el: label(el), axis: 'left', over: Math.round(-r.left) });
  }
  // A surface with NO controls measures nothing about control reachability, so it is reported as
  // unmeasured rather than counted as a clean pass — twelve of the first run's "ok" rows were
  // exactly this, and a denominator padded with them would overstate what the gate covers.
  if (!controls.length) return { noControls: true, boxH: Math.round(rr.height), fixed, bottomApplies };
  return { controls: controls.length, bad, boxH: Math.round(rr.height), fixed, bottomApplies };
};

// ── SELFTEST ────────────────────────────────────────────────────────────────────────────────
// Proactive guard: the property holds today, so teeth are synthetic. Driven against a REAL fixed
// dialog (pm-scheduler's completion sheet) rather than a fabricated DOM, so the negatives exercise
// the same code path the sweep uses. The two subject-test cases are the important ones — they are
// what stood between this gate and six false findings on its first run.
if (args.includes('--selftest')) {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 320, height: 844 } });
  const s = await signIn(ctx, 'supervisor');
  if (!s.ok) { console.log('SKIP selftest — sign-in unavailable'); await browser.close(); process.exit(0); }
  const page = await ctx.newPage();
  await page.goto(`${SEEDER}/workhive/pm-scheduler.html?asset=${encodeURIComponent('Amada HFE 80-25')}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(5500);
  await page.evaluate(`(() => { const b = document.querySelector('[onclick^="markDone("]'); if (b) b.click(); })()`);
  await page.waitForTimeout(1400);
  const cases = [
    ['the real completion sheet is clean at the floor',
     await page.evaluate(measure, { sel: '#completion-sheet', w: 320, h: 844 }),
     (r) => r.controls > 0 && (r.bad || []).length === 0],
    ['a right-edge overflow is caught',
     await page.evaluate(measure, { sel: '#completion-sheet', w: 40, h: 844 }),
     (r) => (r.bad || []).some(b => b.axis === 'right')],
    ['a FIXED sheet is bottom-checked',
     await page.evaluate(measure, { sel: '#completion-sheet', w: 320, h: 30 }),
     (r) => r.bottomApplies === true && (r.bad || []).some(b => b.axis === 'bottom')],
    ['an IN-FLOW surface is NOT bottom-checked (the six false findings)',
     await page.evaluate(measure, { sel: 'main, body', w: 320, h: 30 }),
     (r) => r.bottomApplies === false && !(r.bad || []).some(b => b.axis === 'bottom')],
    ['an absent surface is reported, not passed',
     await page.evaluate(measure, { sel: '#no-such-dialog', w: 320, h: 844 }),
     (r) => r.absent === true],
    ['a surface with no controls is unmeasured, not passed',
     await page.evaluate(measure, { sel: '#sheet-item-text', w: 320, h: 844 }),
     (r) => r.noControls === true],
  ];
  await browser.close();
  let bad = 0;
  for (const [name, res, ok] of cases) {
    const pass = ok(res);
    if (!pass) bad++;
    console.log(`  ${pass ? 'ok  ' : 'MISS'} ${name}`);
  }
  console.log(bad ? `\nSELFTEST FAILED (${cases.length - bad}/${cases.length})` : `\nSELFTEST ok — ${cases.length}/${cases.length}`);
  process.exit(bad ? 1 : 0);
}

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: WIDTH, height: HEIGHT } });
const s = await signIn(ctx, 'supervisor');
if (!s.ok) { console.log(`SKIP dialogs-fit-the-floor — sign-in unavailable: ${s.err || 'unknown'}`); await browser.close(); process.exit(0); }

const rows = [];
for (const t of SUBJECTS) {
  const page = await ctx.newPage();
  const row = { page: t.page, modal: t.modal, view: t.view, openBy: t.openBy || 'mayStartOpen' };
  try {
    await page.goto(`${SEEDER}/workhive/${t.page}.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(5500);
    // A precondition failing is UNGRADED, never a defect — the registry says so explicitly.
    if (t.pre) {
      const preOk = await page.evaluate(`(() => { try { ${t.pre} ; return 'ok'; } catch (e) { return String(e.message || e).slice(0, 60); } })()`);
      row.pre = preOk;
      if (preOk !== 'ok') { row.skipped = `precondition: ${preOk}`; rows.push(row); await page.close(); continue; }
      await page.waitForTimeout(1200);
    }
    // Some preconditions ALREADY open the surface — project-manager's pre clicks a .pcard, which
    // IS the opener, and the card list is then swapped out for the detail. Clicking the opener a
    // second time failed with "element is not visible" and the subject was recorded as unreachable,
    // when in fact it had opened perfectly on the first click. So: if the surface is already up
    // after the precondition, do not open it again.
    const alreadyOpen = await page.evaluate((s) => {
      const e = document.querySelector(s);
      if (!e) return false;
      const r = e.getBoundingClientRect();
      return !!(r.width && r.height);
    }, '#' + t.modal);
    if (alreadyOpen) {
      row.openedBy = 'precondition';
    } else if (t.openBy === 'click') {
      const el = page.locator(t.opener).first();
      if (!(await el.count())) { row.skipped = `opener ${t.opener} absent`; rows.push(row); await page.close(); continue; }
      await el.click({ timeout: 6000, force: true }).catch(e => { row.skipped = `click: ${String(e).slice(0, 40)}`; });
    } else if (t.openBy === 'fn') {
      const r = await page.evaluate(`(() => { try { ${t.fn} ; return 'ok'; } catch (e) { return String(e.message || e).slice(0, 60); } })()`);
      if (r !== 'ok') { row.skipped = `fn: ${r}`; rows.push(row); await page.close(); continue; }
    }
    await page.waitForTimeout(1400);
    // If the registry's opener produced an empty shell and a content-bearing path exists, take it,
    // and RECORD which path was used so a reader can tell a populated dialog from a bare one.
    if (CONTENT_OPENERS[t.modal]) {
      const cr = await page.evaluate(`(() => { try { return ${CONTENT_OPENERS[t.modal]}; } catch (e) { return String(e.message || e).slice(0, 60); } })()`);
      row.contentOpen = cr;
      await page.waitForTimeout(1600);
    }
    // ★MEASURE THE SHEET, NOT THE SCRIM. marketplace's openSheet(name) opens BOTH
    // `#overlay-<name>` and `#sheet-<name>`: the overlay is the backdrop and the SHEET carries the
    // content. Measuring the overlay found it permanently empty and I was one step from filing
    // "tapping a listing opens a blank full-screen sheet" against a marketplace that is fine.
    // So where a sibling `#sheet-<name>` exists and holds the controls, that is the subject.
    const sheetSel = '#' + String(t.modal).replace(/^overlay-/, 'sheet-');
    const useSheet = t.modal.startsWith('overlay-') && await page.evaluate((s) => {
      const e = document.querySelector(s);
      return !!(e && e.querySelectorAll('button,a,input,select,textarea').length);
    }, sheetSel);
    if (useSheet) row.measuredAs = sheetSel;
    const m = await page.evaluate(measure, { sel: useSheet ? sheetSel : '#' + t.modal, w: WIDTH, h: HEIGHT });
    Object.assign(row, m);
    if (m.absent) row.skipped = `#${t.modal} not in the DOM`;
    if (m.notOpen) row.skipped = `#${t.modal} present but not rendered`;
    if (m.noControls) row.skipped = `#${t.modal} rendered but holds no controls - nothing to measure`;
  } catch (e) {
    row.skipped = `error: ${String(e).slice(0, 60)}`;
  }
  rows.push(row);
  await page.close();
}
await browser.close();

const measured = rows.filter(r => !r.skipped);
const bad = measured.filter(r => (r.bad || []).length);
writeFileSync(REPORT, JSON.stringify({ width: WIDTH, height: HEIGHT, subjects: rows.length,
                                       measured: measured.length, offenders: bad.length, rows }, null, 2));

console.log(`dialogs-fit-the-floor @ ${WIDTH}x${HEIGHT} — subjects ${rows.length}, measured ${measured.length}, with unreachable controls ${bad.length}`);
for (const r of rows) {
  if (r.skipped) { console.log(`    ${(r.page + '/' + r.modal).padEnd(38)} skip: ${r.skipped}`); continue; }
  const tag = (r.bad || []).length
    ? r.bad.map(b => `${b.el} ${b.axis}+${b.over}px`).join(', ')
    // The label has to say WHY the bottom axis was skipped, because 'in-flow' and 'fixed but
    // scrolls internally' are different facts and only one of them means the page can scroll to
    // the control. marketplace's .sheet is position:fixed WITH overflow-y — reporting it as
    // 'in-flow' was a false statement about the reason, on a gate whose whole subject is reasons.
    : `ok (${r.controls} controls, ${r.boxH}px, ${r.bottomApplies ? 'fixed+bottom-checked' : (r.fixed ? 'fixed, scrolls internally' : 'in-flow')})`;
  console.log(`    ${(r.page + '/' + r.modal).padEnd(38)} ${tag}`);
}
if (bad.length) {
  console.log('\nFAIL — a dialog control sits outside the floor viewport with no scroll that reaches it.');
  console.log('  A dialog is fixed and centred, so this is not "below the fold" — it is a button that');
  console.log('  cannot be pressed. Give the sheet an internal max-height + overflow-y, or shorten it.');
  process.exit(GATE ? 1 : 0);
}
console.log('\nPASS — every reachable dialog fits the floor viewport, controls included.');
