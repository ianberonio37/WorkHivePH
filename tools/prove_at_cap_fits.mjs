// prove_at_cap_fits — the longest LEGAL value must not break the form that accepts it.
//
// ★THE GAP (T130). A cap tells a person how much they may type. It says nothing about whether the
// page survives them typing it. Every capped field on this platform accepts its maxlength, and
// nothing checks what the layout does at that length — so a field can advertise 200 characters and
// blow its own container at 180 with nobody the wiser until a worker with a long part number meets
// it on a phone.
//
// ★AND A RESTING SWEEP CANNOT SEE IT, which is the whole reason this file exists. Filling capped
// fields on the six form-bearing pages at rest reached 10 of 66: the other 56 live inside modals,
// sheets and composers that do not exist in the DOM until something is clicked. inventory, logbook,
// project-manager, community and pm-scheduler each reported ZERO capped fields — not because they
// have none, but because a resting probe never opens their forms. Reporting "66 fields, 0 break"
// off that run would have been a skipped partition reading as a covered one.
//
// THE WORST-CASE VALUE IS DELIBERATE: a single unbroken run of 'W'. A cap-length SENTENCE wraps and
// hides exactly the overflow this is looking for; a cap-length part number, serial or URL — which
// is what people actually paste — does not wrap and is the case that breaks a container. 'W' is the
// widest common glyph.
//
// ★AND IT MEASURES ONLY WHAT A PERSON CAN SEE. The first cut of this sweep skipped that check and
// produced 18 "defects" that were all ONE closed feedback drawer (visibility:hidden, parked at
// x=754 against a 390 viewport) counted once per page. Geometry without visibility is not evidence.
//
// Read-only: fills, measures, and restores every field's prior value. Never submits.
//
// USAGE:  node tools/prove_at_cap_fits.mjs [--flow <id>] [--width N] [--gate] [--teeth]
// OUTPUT: at_cap_fits_report.json
import { writeFileSync } from 'fs';
import { chromium } from '@playwright/test';
import { signIn, SEEDER } from './live_page_journeys.mjs';

const args = process.argv.slice(2);
const GATE = args.includes('--gate');
const TEETH = args.includes('--teeth');
const FLOW_ONLY = (() => { const i = args.indexOf('--flow'); return i >= 0 ? args[i + 1] : null; })();
const WIDTH = (() => { const i = args.indexOf('--width'); return i >= 0 ? parseInt(args[i + 1], 10) : 390; })();

// Each flow opens a form that holds capped fields. `open` runs in the page and returns a string
// for the log; the walk then waits for the surface to actually appear rather than assuming it did.
const FLOWS = [
  // ★THE SURFACE SELECTOR IS THE WHOLE GAME, and my first cut got it wrong in a way that PASSED.
  // I guessed '#part-form, #add-part-modal, form'; the real container is #part-modal, so the sweep
  // reached 0 of inventory's 4 visible capped fields, reported ok, and the openers all logged
  // success. A prover that opens the right form and then measures the wrong box is indistinguishable
  // from a clean run. The containers below were read off the live DOM, not guessed.
  { id: 'inventory-add-part', traj: 'T130', page: 'inventory.html', role: 'supervisor',
    open: `(() => { const b = document.getElementById('btn-add-part') || document.getElementById('empty-add-btn');
                    if (!b) return 'no add-part control'; b.click(); return 'add-part clicked'; })()`,
    surface: '#part-modal', expect: 4 },

  { id: 'marketplace-post', traj: 'T130', page: 'marketplace.html', role: 'worker',
    open: `'rest'`, surface: '#form-post, #post-partnumber-wrap', expect: 4 },

  { id: 'marketplace-inquiry', traj: 'T130', page: 'marketplace.html', role: 'worker',
    open: `'rest'`, surface: '#form-inquiry', expect: 3 },

  { id: 'marketplace-rfq', traj: 'T130', page: 'marketplace.html', role: 'worker',
    open: `'rest'`, surface: '#form-rfq', expect: 2 },

  { id: 'community-composer', traj: 'T130', page: 'community.html', role: 'worker',
    open: `(() => { if (typeof openComposer !== 'function') return 'no openComposer';
                    openComposer('question'); return 'composer opened'; })()`,
    surface: '#composer-sheet', expect: 1 },

  // logbook's capped fields live in a THREE-STEP wizard: f-problem in step 2, f-action and the
  // extras drawer's f-knowledge in step 3, and only step 1 carries .active at load. The opener
  // activates the panel directly instead of driving the wizard, and that is deliberate: the claim
  // under test is "does the rendered form survive its longest legal value", not "does the wizard
  // navigate". Revealing the panel is the setup; the measurement is still of the real form, at the
  // real width, with the real CSS. Driving the steps would test navigation and layout at once and
  // make a failure ambiguous between them.
  { id: 'logbook-step2', traj: 'T130', page: 'logbook.html', role: 'worker',
    open: `(() => { const p = document.getElementById('step-panel-2'); if (!p) return 'no step 2';
                    document.querySelectorAll('.step-panel').forEach(x => x.classList.remove('active'));
                    p.classList.add('active'); return 'step 2 revealed'; })()`,
    surface: '#step-panel-2', expect: 1 },

  { id: 'logbook-step3-extras', traj: 'T130', page: 'logbook.html', role: 'worker',
    open: `(() => { const p = document.getElementById('step-panel-3'); if (!p) return 'no step 3';
                    document.querySelectorAll('.step-panel').forEach(x => x.classList.remove('active'));
                    p.classList.add('active');
                    const d = document.getElementById('extras-drawer'); if (d) d.classList.add('open');
                    return 'step 3 + extras revealed'; })()`,
    surface: '#step-panel-3', expect: 2 },
];


// Fill to cap, measure, restore. Returns findings for fields whose at-cap value breaks layout.
const AT_CAP = ({ surfaceSel, w }) => {
  const shown = el => {
    let n = el;
    while (n && n.nodeType === 1) {
      const c = getComputedStyle(n);
      if (c.display === 'none' || c.visibility === 'hidden' || parseFloat(c.opacity || '1') < 0.05) return false;
      n = n.parentElement;
    }
    return el.offsetParent !== null || getComputedStyle(el).position === 'fixed';
  };
  const roots = surfaceSel ? Array.from(document.querySelectorAll(surfaceSel)).filter(shown) : [document.body];
  const seen = new Set();
  const fields = [];
  for (const r of roots) {
    for (const el of r.querySelectorAll('input[maxlength], textarea[maxlength]')) {
      if (seen.has(el)) continue;
      seen.add(el);
      if (shown(el)) fields.push(el);
    }
  }
  const docW = document.documentElement.clientWidth;
  const baseScroll = document.documentElement.scrollWidth;
  const out = [];
  for (const el of fields) {
    const cap = parseInt(el.getAttribute('maxlength'), 10);
    if (!cap || cap > 4000) continue;
    const prev = el.value;
    el.value = 'W'.repeat(Math.min(cap, 400));           // unbroken: the case that does not wrap
    el.dispatchEvent(new Event('input', { bubbles: true }));
    const b = el.getBoundingClientRect();
    const widenedPage = document.documentElement.scrollWidth > Math.max(baseScroll, docW) + 2;
    const offRight = b.right > docW + 1;
    if (widenedPage || offRight) {
      out.push({ id: el.id || el.name || el.tagName, cap,
                 why: widenedPage ? 'the at-cap value widened the PAGE (horizontal scroll on a phone)'
                                  : 'the field sits past the right edge at its longest legal value' });
    }
    el.value = prev;
    el.dispatchEvent(new Event('input', { bubbles: true }));
  }
  return { measured: fields.length, findings: out };
};

const browser = await chromium.launch();
const results = [];

for (const f of FLOWS.filter(x => !FLOW_ONLY || x.id === FLOW_ONLY)) {
  const ctx = await browser.newContext({ viewport: { width: WIDTH, height: 844 } });
  await signIn(ctx, f.role);
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(String(e).slice(0, 90)));
  const r = { id: f.id, page: f.page, findings: [], measured: 0, opened: '?' };
  try {
    await p.goto(`${SEEDER}/workhive/${f.page}`, { waitUntil: 'domcontentloaded' });
    await p.waitForTimeout(9000);
    r.opened = await p.evaluate(f.open);
    await p.waitForTimeout(2500);
    let m = await p.evaluate(AT_CAP, { surfaceSel: f.surface, w: WIDTH });
    if (TEETH) {
      // Prove the oracle can go red: shrink the viewport-relative container so an at-cap value
      // must overflow. If this does not produce findings, the sweep is measuring nothing.
      await p.evaluate((sel) => {
        const el = document.querySelector(sel.split(',')[0].trim());
        if (el) { el.style.width = '2000px'; el.style.maxWidth = 'none'; }
      }, f.surface);
      const broken = await p.evaluate(AT_CAP, { surfaceSel: f.surface, w: WIDTH });
      r.teeth = { clean: m.findings.length, broken: broken.findings.length,
                  fires: broken.findings.length > m.findings.length };
    }
    r.measured = m.measured;
    r.findings = m.findings;
    if (typeof f.expect === 'number' && m.measured < f.expect) {
      r.findings.push({ id: '(reach)', cap: 0,
        why: `reached ${m.measured} capped fields but this flow should expose ${f.expect} - the form did not `
           + `open, or the surface selector no longer matches its container. A sweep that measures nothing `
           + `passes, so under-reach is a FAILURE here, not a quiet zero` });
    }
    if (errs.length) r.findings.push({ id: '(page)', cap: 0, why: `page error: ${errs[0]}` });
  } catch (e) {
    r.findings.push({ id: '(walk)', cap: 0, why: `walk failed: ${String(e).slice(0, 100)}` });
  }
  results.push(r);
  await ctx.close();
}
await browser.close();

writeFileSync('at_cap_fits_report.json', JSON.stringify({
  generated_by: 'tools/prove_at_cap_fits.mjs', width: WIDTH, results }, null, 2));

const totalFields = results.reduce((a, r) => a + r.measured, 0);
const failing = results.filter(r => r.findings.length);
console.log(`at-cap-fits - the longest legal value must not break the form that accepts it  (${WIDTH}px)`);
for (const r of results) {
  console.log(`  ${r.findings.length ? 'FAIL' : 'ok  '} ${r.id.padEnd(22)} ${String(r.measured).padStart(3)} capped fields  [${r.opened}]`
    + (r.teeth ? `  teeth: clean=${r.teeth.clean} broken=${r.teeth.broken} ${r.teeth.fires ? 'FIRES' : 'DID NOT FIRE'}` : ''));
  for (const x of r.findings) console.log(`         ${x.id} (cap ${x.cap}): ${x.why}`);
}
console.log(`\n  ${totalFields} capped fields reached inside opened forms; ${failing.length} flows with findings.`);
if (TEETH) {
  const dead = results.filter(r => r.measured > 0 && r.teeth && !r.teeth.fires);
  console.log(`\nTEETH ${dead.length ? 'FAILED' : 'ok'} - ${results.filter(r => r.teeth?.fires).length}/${results.filter(r => r.measured > 0).length} flows with fields go red when the container is broken`);
  process.exit(dead.length ? 1 : 0);
}
if (failing.length) { console.log('\nFAIL - a field breaks its own form at a length it advertises as legal.'); process.exit(GATE ? 1 : 0); }
console.log('\nPASS - every reachable capped field holds its longest legal value without breaking the layout.');
