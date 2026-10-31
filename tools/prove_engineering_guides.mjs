// prove_engineering_guides.mjs - the Guide tab of every calculator in engineering-design.html, read as a person reads it
// (Wave ED, 2026-10-31; rows ED-G1 and ED-GR1..GR3).
//
// Ian, 2026-10-31: "there are many flops in engineering design calculator, in the guide, you find it and you will see."
// Measured that day: three built calculators opened a Guide that said "No guide available yet ... check back after it is
// built"; the guides named fields their forms do not have (Load Estimation's describes System Voltage, Phase
// Configuration, Power Factor and Demand Factor - its form has none of them); and on a phone every tip, note and standard
// was 12.5px at 55% white, each empty formula entry opened a three-line hole, and a wrapped formula read as two.
//
// For every built calculator (CALC_TYPES_UI, available) this selects it, reads its form's own field labels, opens the
// Guide and reads it back, at phone-390 and desktop-1280:
//   G1   the guide exists, and its field names are the form's field names - none it describes that the form lacks, none the
//        form carries that it leaves out (compared without the unit in parentheses: "Floor Area (m2)" = "Floor Area")
//   GR1  no guide text under 0.8 opacity, none under 14px (the page's floor: 0.6 at 14px read APCA Lc 55, 0.80 reads 79.8)
//   GR2  no hole in the formula block (no <br>, no empty line taller than a gap)
//   GR3  every formula is its own line with a hanging indent, so its wrapped continuation reads as the same formula
//   FN   every control a person can reach in the form has a name of its own (no two alike, none empty)
//   and nothing wider than the viewport at 390.
//
//   node tools/prove_engineering_guides.mjs                    # read every guide, write engineering_guides_report.json
//   node tools/prove_engineering_guides.mjs --gate             # exit 1 on a renderer fault, a missing guide, or a guide
//                                                              # that passed before and fails now (the ratchet)
//   node tools/prove_engineering_guides.mjs --update-baseline  # add today's passing guides to the ratchet (never removes)
//   node tools/prove_engineering_guides.mjs --teeth            # plant one violation of each kind; every one must be caught
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const GATE = args.includes('--gate');
const TEETH = args.includes('--teeth');
const UPDATE = args.includes('--update-baseline');
const REPORT = TEETH ? 'engineering_guides_teeth.json' : 'engineering_guides_report.json';
const BASELINE = 'engineering_guides_baseline.json';
const VIEWPORTS = [['phone-390', 390, 844], ['desktop-1280', 1280, 900]];

// one reading of one calculator's guide - runs in the page
const READ = async ({ id, plant }) => {
  const norm = (s) => (s || '').toLowerCase().replace(/\([^)]*\)/g, ' ').replace(/²/g, '2').replace(/³/g, '3')
    .replace(/[^a-z0-9]+/g, ' ').trim();
  const ownText = (e) => [...e.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join(' ')
    .replace(/\s+/g, ' ').trim() || (e.innerText || '').replace(/\s+/g, ' ').trim();
  if (plant) GUIDES[id].fields.push({ name: 'Ghost Field', tip: 'planted by --teeth' });
  switchTab('calculator');
  selectCalcType(id);
  await new Promise((r) => setTimeout(r, 120));
  const form = document.getElementById('input-form-area');
  const labels = [...form.querySelectorAll('.field-label')].map(ownText).filter((t) => t && !/^project/i.test(t));
  // a guide may describe a group by the heading the form gives it ("Harmonic Components (% of I₁)")
  const heads = [...form.querySelectorAll('.field-label, h3, h4, h5, legend, th, [class*="section"]')].map(ownText);
  // FN - every control a person can reach has a name of its own: 139 of 470 shared one (a schedule's rows, Fire Alarm's
  // devices, Harmonic's five orders), so a screen reader could not tell one row from the next (2026-10-31)
  const reach = [...form.querySelectorAll('input, select, textarea')].filter((c) => c.type !== 'hidden' && c.getClientRects().length);
  if (plant && reach.length > 2) reach[1].setAttribute('aria-label', reach[2].getAttribute('aria-label') || 'x');
  const cnames = reach.map((c) => (c.getAttribute('aria-label') || '').trim());
  const dupNames = cnames.filter((n, i) => !n || cnames.indexOf(n) !== i);
  switchTab('guide');
  await new Promise((r) => setTimeout(r, 120));
  const el = document.getElementById('guide-content');
  if (plant) {
    el.insertAdjacentHTML('beforeend', '<p style="color:rgba(255,255,255,0.55);font-size:12px">planted faint text</p>');
    const mono = el.querySelector('.font-mono');
    if (mono) { mono.insertAdjacentHTML('beforeend', '<div style="height:40px"></div>'); mono.append('planted flat line'); }
  }
  const noGuide = /No guide available yet/.test(el.innerText);
  const gnames = typeof GUIDES[id] === 'object' ? GUIDES[id].fields.map((f) => f.name) : [];
  const L = labels.map(norm), H = heads.map(norm), G = gnames.map(norm);
  const ghost = gnames.filter((n, i) => G[i] && !L.includes(G[i]) && !H.includes(G[i]));
  const missing = labels.filter((n, i) => L[i] && !G.includes(L[i]));
  // GR1 - every piece of text the guide shows, at its computed colour and size
  let faint = 0, small = 0;
  const faintAt = [];
  for (const e of el.querySelectorAll('*')) {
    const own = [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if (!own) continue;
    const cs = getComputedStyle(e);
    const m = cs.color.match(/rgba?\(([^)]+)\)/);
    const alpha = m ? (m[1].split(',')[3] !== undefined ? parseFloat(m[1].split(',')[3]) : 1) : 1;
    if (alpha < 0.79) { faint++; if (faintAt.length < 3) faintAt.push(e.tagName + ' ' + cs.color); }
    if (parseFloat(cs.fontSize) < 13.9) small++;
  }
  // GR2 / GR3 - the formula block
  const mono = el.querySelector('.font-mono');
  let holes = 0, flat = 0, lines = 0;
  if (mono) {
    holes += mono.querySelectorAll('br').length;
    for (const n of mono.childNodes) {
      if (n.nodeType === 3) { if (n.textContent.trim()) flat++; continue; }
      if (n.nodeType !== 1) continue;
      const t = (n.textContent || '').trim();
      if (!t) { if (n.getBoundingClientRect().height > 14) holes++; continue; }
      lines++;
      const cs = getComputedStyle(n);
      if (!(parseFloat(cs.textIndent) < 0) || cs.display === 'inline') flat++;
    }
  }
  const overflow = document.documentElement.scrollWidth - innerWidth;
  switchTab('calculator');
  return { labels: labels.length, guideFields: gnames.length, noGuide, ghost, missing, faint, faintAt, small, holes, flat,
    lines, overflow, controls: reach.length, dupNames: dupNames.slice(0, 4), dupCount: dupNames.length };
};

const browser = await chromium.launch();
const ctx = await browser.newContext();
await assertSignedIn(signIn(ctx, 'supervisor'));
const page = await ctx.newPage();
let ids = [];
const results = [];
try {
  for (const [vp, w, h] of VIEWPORTS) {
    await page.setViewportSize({ width: w, height: h });
    await page.goto(`${ORIGIN}/engineering-design.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForFunction(() => typeof GUIDES === 'object' && typeof selectCalcType === 'function', null, { timeout: 20000 });
    const landed = await page.evaluate(() => location.pathname);
    if (!/engineering-design/.test(landed)) throw new Error(`landed on ${landed}, not engineering-design.html`);
    ids = await page.evaluate(() => Object.values(CALC_TYPES_UI).flat().filter((c) => c.available).map((c) => c.id));
    const run = TEETH ? ['Transformer Sizing'] : ids;
    for (const id of run) {
      const r = await page.evaluate(READ, { id, plant: TEETH });
      const g1 = !r.noGuide && r.guideFields > 0 && !r.ghost.length && !r.missing.length;
      const renderer = !r.faint && !r.small && !r.holes && !r.flat && (vp !== 'phone-390' || r.overflow <= 1);
      results.push({ calc: id, vp, ...r, g1, renderer });
    }
  }
} catch (e) {
  // the site is not up, or the page did not load: an instrument that cannot reach its page abstains - it grades nothing
  console.log(`SKIP engineering-guides: ${String(e.message || e).slice(0, 160)}`);
  await browser.close();
  process.exit(0);
}
await browser.close();

const byCalc = {};
for (const r of results) {
  const c = byCalc[r.calc] || (byCalc[r.calc] = { calc: r.calc, g1: true, renderer: true, noGuide: r.noGuide, ghost: r.ghost, missing: r.missing });
  c.g1 = c.g1 && r.g1;
  c.renderer = c.renderer && r.renderer;
}
const calcs = Object.values(byCalc);
const gr = {
  GR1: results.every((r) => !r.faint && !r.small),
  GR2: results.every((r) => !r.holes),
  GR3: results.every((r) => !r.flat),
  FN: results.every((r) => !r.dupCount),
};

if (TEETH) {
  const t = results.filter((r) => r.calc === 'Transformer Sizing');
  const caught = {
    ghost: t.every((r) => r.ghost.includes('Ghost Field')),
    faint: t.every((r) => r.faint > 0),
    small: t.every((r) => r.small > 0),
    hole: t.every((r) => r.holes > 0),
    flat: t.every((r) => r.flat > 0),
    sameName: t.every((r) => r.dupCount > 0),
  };
  const ok = Object.values(caught).every(Boolean);
  writeFileSync(REPORT, JSON.stringify({ generated: new Date().toISOString(), teeth: true, caught, ok, results }, null, 1));
  console.log(ok ? 'TEETH ok engineering-guides: a planted ghost field, faint text, small text, a formula hole, a flat line and two controls with one name were each caught'
                 : 'BLUNT engineering-guides: ' + JSON.stringify(caught));
  process.exit(ok ? 0 : 1);
}

const passing = calcs.filter((c) => c.g1).map((c) => c.calc).sort();
const base = existsSync(BASELINE) ? JSON.parse(readFileSync(BASELINE, 'utf8')) : { passing: [] };
const regressed = (base.passing || []).filter((c) => !passing.includes(c));
const noGuide = calcs.filter((c) => c.noGuide).map((c) => c.calc);
writeFileSync(REPORT, JSON.stringify({ generated: new Date().toISOString(), teeth: false, origin: ORIGIN,
  viewports: VIEWPORTS.map((v) => v[0]), calculators: calcs.length, g1_passing: passing.length, gr, noGuide, regressed,
  calcs, results }, null, 1));
if (UPDATE) {
  const merged = [...new Set([...(base.passing || []), ...passing])].sort();
  writeFileSync(BASELINE, JSON.stringify({ updated: new Date().toISOString().slice(0, 10),
    note: 'guides whose fields match their form exactly - a guide on this list that fails again is a regression', passing: merged }, null, 1) + '\n');
}
for (const c of calcs.filter((x) => !x.g1)) {
  const why = c.noGuide ? 'no guide' : [c.ghost.length ? `names ${c.ghost.length} field(s) the form lacks: ${c.ghost.slice(0, 3).join('; ')}` : '',
    c.missing.length ? `omits ${c.missing.length} form field(s): ${c.missing.slice(0, 3).join('; ')}` : ''].filter(Boolean).join(' | ');
  console.log(`  open  ${c.calc}: ${why}`);
}
const bad = results.filter((r) => !r.renderer).slice(0, 5);
for (const r of bad) console.log(`  RENDER ${r.calc} @ ${r.vp}: faint ${r.faint} ${r.faintAt.join(', ')} · small ${r.small} · holes ${r.holes} · flat ${r.flat} · overflow ${r.overflow}`);
for (const r of results.filter((x) => x.dupCount).slice(0, 5)) console.log(`  NAMES ${r.calc} @ ${r.vp}: ${r.dupCount} control(s) share or lack a name - ${r.dupNames.join('; ')}`);
const fail = GATE && (!gr.GR1 || !gr.GR2 || !gr.GR3 || !gr.FN || noGuide.length || regressed.length
  || results.some((r) => r.vp === 'phone-390' && r.overflow > 1));
console.log(`${fail ? 'FAIL' : 'PASS'} engineering-guides: ${calcs.length} calculators at ${VIEWPORTS.length} widths · guides matching their form ${passing.length}/${calcs.length} · `
  + `renderer GR1 ${gr.GR1 ? 'ok' : 'FAIL'} GR2 ${gr.GR2 ? 'ok' : 'FAIL'} GR3 ${gr.GR3 ? 'ok' : 'FAIL'} · `
  + `every control its own name ${gr.FN ? 'ok' : 'FAIL'} (${results.filter((r) => r.vp === 'phone-390').reduce((a, r) => a + r.controls, 0)} at 390) · no guide ${noGuide.length} · regressed ${regressed.length}`);
process.exit(fail ? 1 : 0);
