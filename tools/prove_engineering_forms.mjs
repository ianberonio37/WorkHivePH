// prove_engineering_forms.mjs - every calculator form refuses what it cannot compute, and never swaps a person's number
// (Wave ED, 2026-11-02; rows ED-F1 "the form refuses what it cannot compute").
//
// The page's generic check reads each field's declared min/max (pump efficiency once accepted 112345), but it skips a BLANK
// field, and collectInputs() reads most fields as `parseFloat(v(id)) || default` - so a cleared field computes with a default
// the person never sees, and a typed 0 is replaced by the default too. For every built calculator, inside the page, with the
// engine call intercepted (nothing is computed or saved; only whether the page would SEND it):
//   BASE   at the form's defaults (an empty field filled with its placeholder or min) Calculate goes through
//   BLANK  each visible numeric field cleared, one at a time: the page refuses before sending, in words that name the field
//          (a field marked data-optional - its label says what a blank means - may send)
//   ZERO   each visible numeric field set to 0: if the field's own min forbids 0 the page refuses; if 0 is allowed, the 0
//          reaches the payload - it is not swapped for a default
//
//   node tools/prove_engineering_forms.mjs [--gate] [--update-baseline] [--teeth] [--only "<calc>"]
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const GATE = args.includes('--gate');
const TEETH = args.includes('--teeth');
const UPDATE = args.includes('--update-baseline');
const ONLY = args.includes('--only') ? args[args.indexOf('--only') + 1] : null;
const REPORT = TEETH ? 'engineering_forms_teeth.json' : 'engineering_forms_report.json';
const BASELINE = 'engineering_forms_baseline.json';

// one calculator's form, every field - runs in the page
const WALK = async ({ calc, plant }) => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  switchTab('calculator');
  selectCalcType(calc);
  await sleep(200);
  // the engine call is held at the NETWORK (page.route, below): db.functions is a getter that builds a new client on every
  // read, so patching db.functions.invoke intercepted nothing - the first walk sent real calculations and spent the walker's
  // daily AI quota. window.__walkSent() reads the route's count. Toasts are recorded here.
  window.__toasts = [];
  if (!window.__wired) {
    window.__wired = true;
    const st = window.showToast;
    window.showToast = (msg, ...rest) => { window.__toasts.push(String(msg)); try { return st(msg, ...rest); } catch (e) { return undefined; } };
  }
  const visible = (el) => { for (let n = el; n; n = n.parentElement) { const cs = getComputedStyle(n); if (cs.display === 'none' || cs.visibility === 'hidden') return false; } return true; };
  const form = document.getElementById('input-form-area') || document;
  // a read-only or disabled field holds the page's own figure (a fixture's table DFU): a person cannot type into it
  const fields = [...form.querySelectorAll('input[type=number]')].filter(visible).filter((el) => !el.readOnly && !el.disabled);
  const label = (el) => (el.getAttribute('aria-label') || el.closest('div')?.querySelector('.field-label')?.textContent || el.id || '').replace(/\s+/g, ' ').trim();
  // the form's defaults, made computable: an empty field takes its placeholder or min, a value under its min takes the min
  // (a required load the form opens empty, which the person must enter)
  const fillOf = (el) => (Number(el.placeholder) > 0 ? el.placeholder : (Number(el.min) > 0 ? el.min : 1));
  for (const el of fields) {
    if (el.value === '') el.value = el.hasAttribute('data-optional') ? '' : fillOf(el);
    else if (el.min !== '' && Number(el.value) < Number(el.min)) el.value = el.min;
  }
  // the words around a field: its own name and the label above it (a hint such as "(leave blank = auto)" lives there)
  const words = (el) => {
    let lab = '';
    for (let n = el.parentElement, i = 0; n && i < 4 && !lab; n = n.parentElement, i++) lab = n.querySelector('.field-label')?.textContent || '';
    return (lab + ' ' + label(el)).replace(/\s+/g, ' ');
  };
  if (plant) {
    // TEETH - three defects the walk must name: a field marked optional whose label says nothing of a blank, a payload
    // that swaps a typed 0 for a default, and a field whose minimum was taken away
    const quiet = fields.find((el) => !/blank|optional|\(opt|auto|leave|0 = /i.test(words(el)));
    if (quiet) quiet.setAttribute('data-optional', '1');
    const real = window.collectInputs;
    window.collectInputs = (...a) => { const p = real(...a); for (const k of Object.keys(p)) if (p[k] === 0) p[k] = 7; return p; };
    const bounded = fields.find((el) => el !== quiet && el.min !== '');
    if (bounded) bounded.removeAttribute('min');
  }
  const press = async () => {
    window.__toasts = [];
    const before = await window.__walkSent();
    document.getElementById('calc-btn')?.click();
    let sent = false;
    for (let i = 0; i < 40 && !sent && !window.__toasts.length; i++) { await sleep(100); sent = (await window.__walkSent()) > before; }
    await sleep(150);
    sent = sent || (await window.__walkSent()) > before;
    return { sent, toast: window.__toasts.join(' | ').slice(0, 200) };
  };
  let base = await press();
  if (!base.sent) {
    // a form whose every count opens at 0 (Fire Alarm: no devices yet) - one of each, then try again
    const zeros = fields.filter((el) => el.value === '0');
    zeros.forEach((el) => { el.value = '1'; });
    if (zeros.length) base = await press();
  }
  const out = { calc, fields: fields.length, base, blank: [], zero: [], unitless: [] };
  // UNIT - the unit beside the field (.input-unit), or in its label; a count, ratio or factor has none to show
  const DIMLESS = /(?:^|[^a-z])(no\.|number|count|qty|quantity|persons|occupants|people|nozzles|devices|boilers|units?|factor|ratio|coefficient|diversity|efficiency|power factor|poles|cores|stories|storeys|floors|doors|stairwells|cars|stops|lanes|parts|falls|sheaves|fixtures|heads|outlets|appliances|harmonic|c value|runoff|cop|eer|iplv|grade|class)(?![a-z])/i;
  for (const el of fields) {
    const grp = el.closest('.input-group');
    const unit = (grp && grp.querySelector('.input-unit')?.textContent.trim()) || '';
    const lbl = words(el);
    const inLabel = /\((?:[^()]*[a-zA-Z°%₱/²³][^()]*)\)|\b(mm|m|kW|kVA|kPa|bar|°C|L\/min|m³|m²|kg|kN|N|Hz|V|A|dB|hp|rpm|%)\b/.test(lbl);
    if (!unit && !inLabel && !DIMLESS.test(lbl)) out.unitless.push({ id: el.id, name: label(el) });
  }
  if (!base.sent) return out;                      // the form refuses its own defaults: reported, the field checks cannot run
  for (const el of fields) {
    const name = label(el), keep = el.value, optional = el.hasAttribute('data-optional');
    // BLANK
    el.value = '';
    const b = await press();
    const named = b.toast && name && b.toast.toLowerCase().includes(name.toLowerCase().replace(/\s*\(.*$/, '').slice(0, 18));
    // data-optional lets a blank through the page's check: it is honest only when the label says what that blank means
    if (optional && !/blank|optional|\(opt|auto|leave|0 = /i.test(words(el))) out.blank.push({ id: el.id, name, outcome: 'marked optional, but its label does not say what a blank means' });
    if (b.sent && !optional) out.blank.push({ id: el.id, name, outcome: 'computed with a hidden default' });
    else if (!b.sent && !named) out.blank.push({ id: el.id, name, outcome: `refused without naming the field: "${b.toast}"` });
    // RANGE - a field that declares no lower bound sends -5 (only 5 of 315 did, all signed quantities that now declare one)
    if (el.min === '') out.blank.push({ id: el.id, name, outcome: 'declares no minimum, so a negative is sent unchecked' });
    // ZERO
    const zeroAllowed = !(el.min !== '' && Number(el.min) > 0) && !(el.max !== '' && Number(el.max) < 0);
    if (!zeroAllowed) {
      el.value = '0';
      const z = await press();
      if (z.sent) out.zero.push({ id: el.id, name, outcome: `0 is outside the field's range ${el.min}..${el.max} and was sent` });
    } else {
      // the payload this field produces at its value and at 0: the keys that move are the field's; one of them must be 0
      el.value = keep;
      const p1 = collectInputs();
      el.value = '0';
      const p0 = collectInputs();
      const moved = Object.keys(p0).filter((k) => JSON.stringify(p0[k]) !== JSON.stringify(p1[k]));
      // a row table sends an array of objects: the leaf that moved is the field's, and it must be the 0
      const leaves = (a, b, acc = []) => {
        if (a && b && typeof a === 'object' && typeof b === 'object') {
          for (const k of new Set([...Object.keys(a), ...Object.keys(b)])) leaves(a[k], b[k], acc);
        } else if (JSON.stringify(a) !== JSON.stringify(b)) acc.push(a);
        return acc;
      };
      const movedLeaves = moved.flatMap((k) => leaves(p0[k], p1[k]));
      const reached = movedLeaves.some((x) => x === 0 || x === '0');
      if (Number(keep) !== 0 && !reached) {
        out.zero.push({ id: el.id, name, outcome: moved.length ? `a typed 0 reached the engine as ${moved.map((k) => `${k} = ${JSON.stringify(p0[k])}`).join(', ').slice(0, 160)}`
                                                               : 'a typed 0 changed nothing the form sends (swallowed by a default)' });
      }
    }
    el.value = keep;
  }
  return out;
};

const browser = await chromium.launch();
const ctx = await browser.newContext();
await assertSignedIn(signIn(ctx, 'supervisor'));
const page = await ctx.newPage();
page.on('dialog', (d) => d.accept().catch(() => {}));
// nothing reaches the engine or the AI: every calc-agent request is answered here, and counted
let sentCount = 0;
await page.route('**/functions/v1/engineering-calc-agent**', async (route) => {
  sentCount++;
  await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ error: 'held by the form walk' }) });
});
await page.exposeFunction('__walkSent', () => sentCount);
const results = [];
try {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(`${ORIGIN}/engineering-design.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForFunction(() => typeof selectCalcType === 'function' && typeof db === 'object', null, { timeout: 20000 });
  const all = await page.evaluate(() => Object.values(CALC_TYPES_UI).flat().filter((c) => c.available).map((c) => c.id));
  const run = TEETH ? ['Vibration Analysis'] : ONLY ? [ONLY] : all;
  for (const calc of run) {
    try { results.push(await page.evaluate(WALK, { calc, plant: TEETH })); }
    catch (e) { results.push({ calc, error: String(e.message || e).slice(0, 160), blank: [], zero: [] }); }
  }
} catch (e) {
  console.log(`SKIP engineering-forms: ${String(e.message || e).slice(0, 160)}`);
  await browser.close();
  process.exit(0);
}
await browser.close();

const okOf = (r) => !r.error && r.base?.sent && !r.blank.length && !r.zero.length && !(r.unitless || []).length;
if (TEETH) {
  // each planted defect must be named: the quiet optional marker, the swapped 0, the field with no minimum
  const r = results[0] || { blank: [], zero: [] };
  const saw = {
    optional: r.blank.some((b) => /marked optional/.test(b.outcome)),
    zero: r.zero.length > 0,
    range: r.blank.some((b) => /no minimum/.test(b.outcome)),
  };
  const ok = results.length === 1 && r.base?.sent === true && saw.optional && saw.zero && saw.range;
  writeFileSync(REPORT, JSON.stringify({ generated: new Date().toISOString(), teeth: true, ok, saw, results }, null, 1));
  console.log(ok ? `TEETH ok engineering-forms: named the quiet optional marker, ${r.zero.length} swapped 0(s) and the field with no minimum`
                 : 'BLUNT engineering-forms: ' + JSON.stringify(saw) + ' ' + JSON.stringify(results).slice(0, 300));
  process.exit(ok ? 0 : 1);
}
const passing = results.filter(okOf).map((r) => r.calc).sort();
const base = existsSync(BASELINE) ? JSON.parse(readFileSync(BASELINE, 'utf8')) : { passing: [] };
const regressed = (base.passing || []).filter((c) => !passing.includes(c));
writeFileSync(REPORT, JSON.stringify({ generated: new Date().toISOString(), teeth: false, origin: ORIGIN,
  calculators: results.length, passing: passing.length, regressed, results }, null, 1));
if (UPDATE) {
  const merged = [...new Set([...(base.passing || []), ...passing])].sort();
  writeFileSync(BASELINE, JSON.stringify({ updated: new Date().toISOString().slice(0, 10),
    note: 'forms that refuse a blank or impossible value by name and never swap a typed number', passing: merged }, null, 1) + '\n');
}
const fields = results.reduce((a, r) => a + (r.fields || 0), 0);
const blanks = results.reduce((a, r) => a + r.blank.length, 0), zeros = results.reduce((a, r) => a + r.zero.length, 0);
for (const r of results.filter((x) => !okOf(x)).slice(0, 60)) {
  const why = r.error ? r.error : !r.base?.sent ? `refuses its own defaults: "${r.base?.toast}"`
    : [...r.blank.map((b) => `${b.name}: ${b.outcome}`), ...r.zero.map((z) => `${z.name}: ${z.outcome}`), ...(r.unitless || []).map((u) => `${u.name}: shows no unit`)].slice(0, 3).join("; ");
  console.log(`  open  ${r.calc} (${r.blank.length} blank, ${r.zero.length} zero): ${why}`.slice(0, 400));
}
const fail = GATE && regressed.length > 0;
console.log(`${fail ? 'FAIL' : 'PASS'} engineering-forms: ${results.length} forms, ${fields} numeric fields · blank faults ${blanks} · zero faults ${zeros} · `
  + `forms holding ${passing.length}/${results.length} · regressed ${regressed.length}`);
process.exit(fail ? 1 : 0);
