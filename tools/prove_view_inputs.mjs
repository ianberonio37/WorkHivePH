/* prove_view_inputs.mjs — what can a person actually TYPE INTO on the view a page opens on?
 *
 * WHY THIS EXISTS. The wrong_then_fix oracle asks: submit something wrong, does the surface refuse with a
 * reason, keep what you typed, and let one field fix it? A view with NO editable input cannot answer that —
 * there is nothing to get wrong. The honest disposition is declared-na. But "this view has no input" is a
 * CLAIM ABOUT THE LIVE PAGE, and asserting it from a static read is how a bank fills with rows nobody
 * checked. So it is measured here: load the page as the persona, enumerate every visible, enabled,
 * user-editable control on the view the page OPENS ON, and report each one with the id-bearing region that
 * owns it.
 *
 * WHAT IT DELIBERATELY DOES NOT CLAIM. A page whose only inputs live inside modals reports zero here, and
 * that is CORRECT for the default view and WRONG for the page — so every finding is scoped to "the view
 * rendered at load", never to the page. Modal-only views (V2/V3) need their own reach and are listed as
 * unreached rather than silently counted as inputless. Same discipline that had 32 rows re-homed when modal
 * readings turned out to be filed against a list view.
 *
 * SHARED CHROME IS EXCLUDED, and named: the nav hub's search box, the page-guide chip, the companion
 * launcher, the feedback FAB and the session/search overlays belong to every page equally. Counting the nav
 * search field as "this view has an input" would make all 22 pages look like forms.
 */
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ORIGIN = 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

// Shared chrome. Every id/class here is a component that appears on many pages, so its inputs are never
// evidence about one view. Sourced from the chrome files themselves, not guessed at.
const CHROME = ['#wh-guide-link', '#wh-nav-hub', '#nav-hub', '#wh-search-overlay', '#search-overlay',
  '#wh-companion', '#companion-launcher', '#wh-companion-launcher', '#wh-feedback-fab', '#feedback-fab',
  '#wh-session-timeout', '#wh-connectivity', '#wh-crumb', '#wh-wayfinding', '#wh-tts'];

const ENUMERATE = ({ chrome, scope }) => {
  // ★SCOPED WHEN THE VIEWS SHARE A PAGE. voice-journal's capture panel (V1) and entries list (V2) are two
  // SECTIONS of one document with no tab between them, so an unscoped enumeration reads both and files the
  // result against whichever view is being graded — the same defect as banking 14 rows for V2 on V1's
  // reading. When a scope is given, only controls inside it count.
  const ROOT = scope ? document.querySelector(scope) : null;
  if (scope && !ROOT) return { error: `scope ${scope} matched nothing` };
  const EDITABLE = 'input,textarea,select,[contenteditable="true"],[role="textbox"],[role="combobox"]';
  const IGNORED_TYPES = ['hidden', 'submit', 'button', 'reset', 'image'];
  const visible = (el) => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || cs.opacity === '0') return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const inChrome = (el) => chrome.some((sel) => { const c = document.querySelector(sel); return c && c.contains(el); });
  const region = (el) => { let n = el.parentElement; while (n) { if (n.id) return '#' + n.id; n = n.parentElement; } return '(no id-bearing ancestor)'; };
  const out = [];
  for (const el of (ROOT || document).querySelectorAll(EDITABLE)) {
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute('type') || '').toLowerCase();
    if (tag === 'input' && IGNORED_TYPES.includes(type)) continue;
    if (el.disabled === true || el.readOnly === true) continue;
    if (!visible(el)) continue;
    if (inChrome(el)) continue;
    out.push({ sel: el.id ? '#' + el.id : tag + (type ? '[type=' + type + ']' : ''),
      tag, type: type || null, region: region(el),
      required: el.required === true || el.getAttribute('aria-required') === 'true',
      label: (el.getAttribute('aria-label') || el.getAttribute('placeholder') || '').slice(0, 40) });
  }
  // Controls that would COMMIT something — a view with an editable field but no way to submit it is a
  // different shape again, and worth seeing rather than assuming.
  // ★DESTRUCTIVE VERBS ARE COMMITS TOO - and they are the ones that matter most for these oracles. This
  // list was all additive, so engineering-design's HISTORY pane enumerated as 'nothing to commit' while
  // carrying a red Delete button wired to deleteCalc() -> engineering_calcs.delete(). A view that can
  // destroy a saved calculation is exactly where a double-tap and a mis-tap cost something, so calling it
  // inputless would have dispositioned away the most consequential control on the pane.
  const VERB = /^(save|send|add|submit|log|complete|create|post|publish|confirm|generate|apply|record|update|use|restock|delete|remove|discard|clear|archive|revoke|cancel|unpublish|reset)\b/i;
  const commits = [];
  for (const b of (ROOT || document).querySelectorAll('button,[role="button"],input[type=submit]')) {
    if (!visible(b) || b.disabled === true) continue;
    if (inChrome(b)) continue;
    const t = (b.textContent || b.value || b.getAttribute('aria-label') || '').trim();
    if (VERB.test(t)) commits.push({ sel: b.id ? '#' + b.id : 'button', text: t.slice(0, 34), region: region(b) });
  }
  return { inputs: out, commits: commits.slice(0, 12) };
};

const URLS = existsSync('page_component_selectors.json')
  ? (JSON.parse(readFileSync('page_component_selectors.json', 'utf-8'))._urls || {}) : {};

// ★REACHES FOR NON-DEFAULT VIEWS. The reading above is only ever about the view a page OPENS ON, which is
// correct and also leaves V2/V3 unmeasurable — and "this view commits nothing" must be measured on THAT view,
// not inferred from the list behind it. A reach is a named sequence that puts the page into the view, so the
// same enumeration can then run there. Each step's failure THROWS: a silently skipped reach would measure the
// default view and file the result against another one, which is exactly how a paramless walk once graded an
// early return for ten provers.
const VIEW_REACH = {
  // dayplanner's WEEK (V2) and MONTH (V3) views. Both render into the SAME container, #calendar-wrap, so the
  // reach must prove the switch happened rather than assume it: switchView() sets #logo-view to the plain word
  // ('Week'/'Month'), which is a visible fact about which view is on screen.
  'dayplanner:V2': [
    { wait: 3000, why: 'schedule items are read-fed' },
    { eval: "(() => { if (typeof switchView !== 'function') throw new Error('switchView is not defined'); switchView('wilo'); const l = document.getElementById('logo-view'); if (!l || l.textContent.trim() !== 'Week') throw new Error('the week view did not take: #logo-view reads ' + (l ? JSON.stringify(l.textContent.trim()) : 'ABSENT')); })()",
      why: 'switch to the week view and prove it took' },
    { wait: 1200, why: 'the week grid renders' },
  ],
  'dayplanner:V3': [
    { wait: 3000, why: 'schedule items are read-fed' },
    { eval: "(() => { if (typeof switchView !== 'function') throw new Error('switchView is not defined'); switchView('milo'); const l = document.getElementById('logo-view'); if (!l || l.textContent.trim() !== 'Month') throw new Error('the month view did not take: #logo-view reads ' + (l ? JSON.stringify(l.textContent.trim()) : 'ABSENT')); })()",
      why: 'switch to the month view and prove it took' },
    { wait: 1200, why: 'the month grid renders' },
  ],
  // logbook's ASSET MANAGER (V3) - the register/edit/detail modals. Opened through the page's own control so
  // the reading is about the modal a person actually sees, not the feed behind it.
  'logbook:V3': [
    { wait: 3000, why: 'the feed and asset list are read-fed' },
    { eval: "(async () => { const t0 = Date.now(); while (Date.now() - t0 < 9000) { const b = [...document.querySelectorAll('button, [role=button]')].find((e) => ((e.textContent || '').trim().toLowerCase().indexOf('register asset') === 0) && e.offsetParent !== null); if (b) { b.click(); await new Promise((r) => setTimeout(r, 900)); const m = document.getElementById('asset-modal'); if (!m || getComputedStyle(m).display === 'none') throw new Error('#asset-modal did not open'); return; } await new Promise((r) => setTimeout(r, 250)); } throw new Error('no Register-Asset control appeared within 9s'); })()",
      why: 'open the register-asset modal and prove it opened' },
  ],
  // skillmatrix's LESSON modal (V2) - the module a person reads, and the surface where the pass mark is
  // disclosed BEFORE the exam opens. Note this page hides overlays with opacity/pointer-events while leaving
  // display:flex, so the reach proves the view by the .open CLASS rather than by display.
  'skillmatrix:V2': [
    { wait: 3000, why: 'the matrix and skill content load first' },
    { eval: "(() => { if (typeof openLesson !== 'function') throw new Error('openLesson is not defined'); const KEY = Object.keys(SKILL_CONTENT)[0]; openLesson(KEY, 1); const m = document.getElementById('lesson-modal'); if (!m || !m.classList.contains('open')) throw new Error('the lesson modal did not open (.open absent)'); })()",
      why: 'open the lesson and prove it by the .open class, not by display' },
    { wait: 900, why: 'the module body renders' },
  ],
  // asset-hub's WEIBULL tab (V3). Three gates: open an asset detail with an IN-PAGE click (a Playwright click
  // is intercepted on this page), reveal the opt-in Reliability Workbench (#reliability-card ships
  // display:none behind #asset-view-toggle), then switch to the Weibull tab.
  'asset-hub:V3': [
    { wait: 2500, why: 'the asset roster is read-fed' },
    { eval: "(() => { const c = document.querySelector('.asset-card'); if (!c) throw new Error('no .asset-card rendered'); c.click(); })()",
      why: 'open an asset detail in-page' },
    { wait: 1500, why: 'the detail loads' },
    { eval: "(() => { const t = document.getElementById('asset-view-toggle'); if (!t) throw new Error('#asset-view-toggle is not in the DOM'); t.click(); })()",
      why: 'reveal the opt-in Reliability Workbench' },
    { wait: 800, why: 'the workbench expands' },
    { eval: "(() => { const t = [...document.querySelectorAll('[data-tab]')].find((e) => e.getAttribute('data-tab') === 'weibull'); if (!t) throw new Error('no Weibull tab'); t.click(); const p = document.getElementById('rel-panel-weibull'); if (!p || getComputedStyle(p).display === 'none') throw new Error('the Weibull panel did not open'); })()",
      why: 'switch to Weibull and prove the panel opened' },
    { wait: 900, why: 'the panel renders' },
  ],
  // shift-brain's VERDICT SUMMARY (V2) - the executive roll-up above the plan. Present at load, so no reach
  // is needed beyond letting the read settle; scoped to the summary card so the plan's own controls below it
  // (publish, rerun, archive) are not counted as this view's.
  'shift-brain:V2': [
    { wait: 4500, why: 'the plan read and its roll-up must settle' },
    { eval: "(() => { const v = document.getElementById('sb-verdict'); if (!v) throw new Error('#sb-verdict is not in the DOM'); const lbl = document.getElementById('sb-verdict-label'); if (lbl && /loading/i.test(lbl.textContent || '')) throw new Error('the verdict is still loading - measuring now would read a wait state as the view'); })()",
      why: 'prove the verdict has actually resolved before enumerating' },
  ],
  // engineering-design's HISTORY (V2) and GUIDE (V3) tabs. Both are panes toggled by the page's own
  // switchTab(); the reach proves the pane actually left the 'hidden' class before anything is enumerated.
  'engineering-design:V2': [
    { wait: 3000, why: 'saved calculations are read-fed' },
    { eval: "(() => { if (typeof switchTab !== 'function') throw new Error('switchTab is not defined'); switchTab('history'); const p = document.getElementById('tab-history'); if (!p || p.classList.contains('hidden')) throw new Error('the history pane did not open'); })()",
      why: 'open History and prove it' },
    { wait: 900, why: 'the list renders' },
  ],
  'engineering-design:V3': [
    { wait: 3000, why: 'let the page settle' },
    { eval: "(() => { if (typeof switchTab !== 'function') throw new Error('switchTab is not defined'); switchTab('guide'); const p = document.getElementById('tab-guide'); if (!p || p.classList.contains('hidden')) throw new Error('the guide pane did not open'); })()",
      why: 'open Guide and prove it' },
    { wait: 600, why: 'the document renders' },
  ],
  // hive's LIVE BOARD (V1). The first-run intent modal overlays the board on a fresh context, so a bare
  // enumeration counts ITS radios as the board's controls - the reach dismisses that modal first (via the
  // page's own Later control where present, otherwise by clearing .open) and PROVES it is gone before
  // measuring. Scoped to <main>, so the modals and sheets that live outside it are not attributed here.
  'hive:V1': [
    { wait: 4500, why: 'the board reads nine truth views' },
    { eval: "(async () => { const wait = (ms) => new Promise((r) => setTimeout(r, ms)); const m = document.getElementById('intent-capture'); if (m && getComputedStyle(m).display !== 'none') { const later = [...m.querySelectorAll('button')].find((b) => /later|skip|not now/i.test(b.textContent || '')); if (later) later.click(); else { m.style.display = 'none'; m.classList.add('hidden'); } await wait(500); } const still = document.getElementById('intent-capture'); if (still && getComputedStyle(still).display !== 'none') throw new Error('the intent modal is still overlaying the board'); })()",
      why: 'dismiss the first-run intent modal and prove it is gone' },
    { wait: 600, why: 'the board settles' },
  ],
  // hive's HANDOVER SHEET (V2) - a composed read of the shift, opened as a dialog.
  'hive:V2': [
    { wait: 4500, why: 'the board must load before the sheet can compose' },
    { eval: "(async () => { const wait = (ms) => new Promise((r) => setTimeout(r, ms)); const m = document.getElementById('intent-capture'); if (m && getComputedStyle(m).display !== 'none') { const later = [...m.querySelectorAll('button')].find((b) => /later|skip|not now/i.test(b.textContent || '')); if (later) later.click(); else { m.style.display = 'none'; m.classList.add('hidden'); } await wait(400); } if (typeof generateHandover !== 'function') throw new Error('generateHandover is not defined'); generateHandover(); await wait(1000); const sh = document.getElementById('handover-sheet'); if (!sh || getComputedStyle(sh).display === 'none') throw new Error('the handover sheet did not open'); })()",
      why: 'compose the handover through the page own generateHandover() and prove the sheet opened' },
    { wait: 600, why: 'the sheet composes' },
  ],
  // alert-hub's AMC DAILY BRIEF (V2) and ANOMALY PANEL (V3). Both ship display:none and appear only when
  // their data exists, so each reach WAITS for its own container and throws if it never arrives - a panel that
  // is absent for want of data must not be measured as an empty panel.
  'alert-hub:V2': [
    { wait: 4000, why: 'the brief is read from amc_briefings' },
    { eval: "(async () => { const t0 = Date.now(); while (Date.now() - t0 < 12000) { const c = document.getElementById('amc-card'); if (c && getComputedStyle(c).display !== 'none') return; await new Promise((r) => setTimeout(r, 250)); } throw new Error('#amc-card never became visible - there may be no briefing for this hive today, which is a DATA state and not an empty view'); })()",
      why: 'wait for the brief to exist and prove it is visible' },
  ],
  'alert-hub:V3': [
    { wait: 4000, why: 'anomaly signals are computed then read' },
    { eval: "(async () => { const t0 = Date.now(); while (Date.now() - t0 < 12000) { const c = document.getElementById('anomaly-engine-panel'); if (c && getComputedStyle(c).display !== 'none') return; await new Promise((r) => setTimeout(r, 250)); } throw new Error('#anomaly-engine-panel never became visible - no anomaly signals for this hive, which is a DATA state and not an empty view'); })()",
      why: 'wait for the anomaly panel and prove it is visible' },
  ],
  'project-manager:V2': [
    { wait: 3000, why: 'the project list is read-fed' },
    { eval: "(async () => { const t0 = Date.now(); while (Date.now() - t0 < 9000) { const c = document.querySelector('.pcard'); if (c) { c.click(); return; } await new Promise((r) => setTimeout(r, 250)); } throw new Error('no .pcard appeared within 9s'); })()",
      why: 'open a project detail' },
    { wait: 2500, why: 'the detail loads items, links, progress, roles and change orders together' },
    { eval: "(() => { const d = document.getElementById('detail-view'); if (!d) throw new Error('#detail-view is not in the DOM'); if (getComputedStyle(d).display === 'none') throw new Error('the detail view did not open'); })()",
      why: 'prove the view actually changed before anything is enumerated' },
  ],
};
const VIEW = (() => { const i = args.indexOf('--view'); return i >= 0 ? args[i + 1] : null; })();
const SCOPE = (() => { const i = args.indexOf('--scope'); return i >= 0 ? args[i + 1] : null; })();

const PAGES = ONE ? [ONE] : ['achievements', 'alert-hub', 'analytics', 'analytics-report', 'assistant',
  'asset-hub', 'community', 'dayplanner', 'engineering-design', 'hive', 'index', 'inventory', 'logbook',
  'pm-scheduler', 'project-manager', 'project-report', 'public-feed', 'report-sender', 'resume',
  'shift-brain', 'skillmatrix', 'voice-journal'];

const browser = await chromium.launch();
const report = { ran: new Date().toISOString(), origin: ORIGIN, pages: {} };
for (const p of PAGES) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await assertSignedIn(signIn(ctx, 'supervisor'));
  const page = await ctx.newPage();
  const rec = { page: p };
  try {
    // project-report renders nothing without ?project_id= and returns early — a paramless walk grades a
    // DIFFERENT page, which is how 10 provers once graded an early return.
    // _urls entries are QUERY STRINGS ("?project_id=..."), not paths. Treating one as a path composed
    // http://host/?project_id=... — the ROOT page — so this prover measured index.html and filed the reading
    // against project-report, whose own #qd-industry/#qd-size "inputs" were index's quick-diagnostic fields.
    // Compose the same way prove_component_states_scoped.mjs does: page path, then the query appended.
    await page.goto(`${ORIGIN}/${p}.html${URLS[p] || ''}`,
      { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForTimeout(5200);
    if (VIEW) {
      const reach = VIEW_REACH[`${p}:${VIEW}`];
      if (!reach) throw new Error(`no reach defined for ${p}:${VIEW} — refusing to enumerate the default view and file it against ${VIEW}`);
      for (const st of reach) {
        if (st.wait) { await page.waitForTimeout(st.wait); continue; }
        await page.evaluate(st.eval);          // deliberately NOT caught: a broken reach must not read as a verdict
      }
      rec.view = VIEW;
      rec.reached = reach.filter((x) => x.why).map((x) => x.why);
    }
    const r = await page.evaluate(ENUMERATE, { chrome: CHROME, scope: SCOPE });
    if (r.error) throw new Error(r.error);
    if (SCOPE) rec.scope = SCOPE;
    rec.inputCount = r.inputs.length;
    rec.inputs = r.inputs;
    rec.commits = r.commits;
    rec.verdict = r.inputs.length === 0
      ? (r.commits.length === 0 ? 'NO-INPUT-NO-COMMIT' : 'NO-INPUT-BUT-COMMITS')
      : 'HAS-INPUT';
  } catch (e) { rec.verdict = 'PROBE-ERROR'; rec.why = String(e).slice(0, 110); }
  report.pages[p] = rec;
  const detail = rec.verdict === 'HAS-INPUT'
    ? `${rec.inputCount} input(s): ` + rec.inputs.slice(0, 4).map((x) => x.sel).join(', ')
    : rec.verdict === 'NO-INPUT-BUT-COMMITS'
      ? 'no editable field, but commit controls: ' + rec.commits.slice(0, 3).map((x) => x.text).join(' / ')
      : (rec.why || 'nothing editable, nothing to commit');
  console.log(`  ${p.padEnd(19)} ${String(rec.verdict).padEnd(20)} ${detail}`.slice(0, 168));
  await ctx.close();
}
writeFileSync('view_inputs_report.json', JSON.stringify(report, null, 1));
const v = Object.values(report.pages);
console.log(`\n  wrote view_inputs_report.json — `
  + `${v.filter((x) => x.verdict === 'NO-INPUT-NO-COMMIT').length} inputless, `
  + `${v.filter((x) => x.verdict === 'HAS-INPUT').length} with a form, `
  + `${v.filter((x) => x.verdict === 'NO-INPUT-BUT-COMMITS').length} commit-only, `
  + `${v.filter((x) => x.verdict === 'PROBE-ERROR').length} probe error`);
console.log('  Scoped to the view each page OPENS ON. Modal-only views are NOT covered by this reading.');
await browser.close();
