// prove_self_efficacy.mjs - T2 SE (2026-10-27): does the page help a first-timer believe they can do it?
//
// Bandura's four sources of self-efficacy, asked of the platform's pages as a stranger meets them. This prover measures
// the PUBLIC half (no account): the 60 calculator pages and the 54 learn articles, at phone-390 and desktop-1280.
//
//   --calc-vicarious  a finished result stands BEFORE the first input: the worked example (#worked) or the tool's
//                     one-line worked result (.tool-example) sits above the first visible input; on a page with no input
//                     (58 of 60 are content pages whose calculator is the signed-in suite) it sits above the hand-off.
//   --learn           a stranger reads to the answer and reaches the tool the article names, unaided: the answer-first
//                     block is visible within two screens of the top, says something (80+ characters), and every tool
//                     the article's main content links to is reached - the tool itself, or (for a signed-in tool) the
//                     sign-in door that names it as the return, never a dead end or a different page.
//
//   node tools/prove_self_efficacy.mjs --calc-vicarious
//   node tools/prove_self_efficacy.mjs --learn [--page learn/<slug>/index.html]
//
// Report: self_efficacy_report.json, read-merged by mode and page (a narrowed run never erases the others).
import { removeWalkAccounts } from './lib/walk_accounts.mjs';
import { ALL_ROWS_DRAWN } from './lib/long_list_text.mjs';
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { SEEDER } from './prover_harness.mjs';

const MODE = process.argv.includes('--calc-vicarious') ? 'calc-vicarious' : process.argv.includes('--learn') ? 'learn'
  : process.argv.includes('--calc-mastery') ? 'calc-mastery' : null;
const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
if (!MODE) { console.error('usage: --calc-vicarious | --learn [--page <path>]'); process.exit(2); }
const VIEWPORTS = { 'phone-390': { width: 390, height: 844 }, 'desktop-1280': { width: 1280, height: 900 } };
const REPORT = 'self_efficacy_report.json';

const reg = JSON.parse(readFileSync('trajectory_registry.json', 'utf8'));
const wanted = (r) => r.wave === 'SE' && r.se && (MODE === 'learn'
  ? r.se.page.startsWith('learn/')
  : (r.se.page.startsWith('tools/') && r.se.source === (MODE === 'calc-mastery' ? 'mastery' : 'vicarious')));
const pages = [...new Set(reg.trajectories.filter(wanted).map((r) => r.se.page))].filter((p) => !ONLY || p === ONLY).sort();
const urlOf = (p) => `${SEEDER}/${p.replace(/index\.html$/, '')}`;

const VICARIOUS = () => {
  const vis = (e) => !!e && e.checkVisibility({ opacityProperty: true, visibilityProperty: true });
  const top = (e) => (e ? Math.round(e.getBoundingClientRect().top + scrollY) : null);
  const inputs = [...document.querySelectorAll('input:not([type=hidden]), select, textarea')]
    .filter((e) => vis(e) && !e.closest('header, footer, nav, form[role=search], [data-wh-feedback], .wh-fb-panel'));
  const worked = document.getElementById('worked');
  const glance = document.querySelector('.tool-example');
  const handoff = [...document.querySelectorAll('main a[href]')].find((a) => /engineering-design\.html|analytics\.html/.test(a.getAttribute('href')));
  const example = [worked, glance].filter(vis).map(top).filter((y) => y != null);
  const exampleY = example.length ? Math.min(...example) : null;
  const firstInputY = inputs.length ? Math.min(...inputs.map(top)) : null;
  // #worked is the example's HEADING; the example is the section that heading names (first run read the 35-char title)
  const workedBlock = worked ? (worked.closest('section') || worked.parentElement) : null;
  return { exampleY, firstInputY, handoffY: top(handoff), inputs: inputs.length, workedText: workedBlock ? workedBlock.innerText.trim().length : 0 };
};

const LEARN = () => {
  const vis = (e) => !!e && e.checkVisibility({ opacityProperty: true, visibilityProperty: true });
  const ans = document.querySelector('main .answer-first');
  const r = ans ? ans.getBoundingClientRect() : null;
  const main = document.querySelector('main') || document.body;
  const tools = [...new Set([...main.querySelectorAll('a[href]')].map((a) => a.getAttribute('href'))
    .filter((h) => /^\/(tools\/[a-z0-9-]+\/|[a-z0-9-]+\.html)/.test(h) && !h.startsWith('/learn')))];
  return { answer: !!ans, answerVisible: vis(ans), answerTop: r ? Math.round(r.top + scrollY) : null,
           answerChars: ans ? ans.innerText.trim().length : 0, vh: innerHeight, tools };
};

// ── calc-mastery: a stranger computes a result unaided ─────────────────────────────────────────────────────────────
// 57 of the 60 pages hand off to the signed-in suite (Wave U settled it: content pages, honest about a free sign-in), so
// the stranger is a FRESH account that has never run a calculator; 3 pages carry their own tool and are walked signed out.
const UNIT_RE = /(%|°C|°F|\b(kWp?|kWh|kVA|kVAR|MW|W|V|kV|A|mA|Ah|Hz|mm|cm|m|km|m²|m³|m\/s|L|L\/s|L\/min|L\/day|lps|gpm|Pa|kPa|MPa|bar|psi|kg|t|N|kN|Nm|N·m|rpm|h|hr|hrs|hours|min|s|days?|ppm|mg\/L|dB|lux|lx|BTU|TR|cfm|ACH|in|ft|pcs|panels?|units?|persons?|people)\b)/;
const FORM = () => {
  const area = document.getElementById('input-form-area');
  const nums = area ? [...area.querySelectorAll('input[type=number]')].filter((e) => e.checkVisibility()) : [];
  // each field's OWN label: the .field-label right before its input group (a first try took the first label in a shared
  // container, so every beam-design field read "b (mm) RC"); its unit is the group's unit span or written in the label
  const hasInput = (el) => !!el.querySelector('input, select, textarea');
  const isGrid = (el) => !!el && getComputedStyle(el).display === 'grid';
  // a list-builder's column header: the nearest previous grid that holds no input (rows of the same list are grids WITH
  // inputs - a first try took the row above as the header and read an input as the label, 2026-10-27)
  const columnHeader = (e) => {
    for (let cell = e, row = e.parentElement, i = 0; row && i < 3; cell = row, row = row.parentElement, i++) {
      if (!isGrid(row)) continue;
      const idx = [...row.children].indexOf(cell);
      let h = row.previousElementSibling;
      while (h && isGrid(h) && hasInput(h)) h = h.previousElementSibling;
      if (!h && row.parentElement) { h = row.parentElement.previousElementSibling; while (h && isGrid(h) && hasInput(h)) h = h.previousElementSibling; }
      if (isGrid(h) && !hasInput(h) && h.children[idx]) return h.children[idx].innerText.trim();
    }
    return '';
  };
  const ownLabel = (e) => {
    for (let el = e, i = 0; el && i < 4; el = el.parentElement, i++) {
      const prev = el.previousElementSibling;
      if (prev && prev.classList.contains('field-label')) return prev.innerText.trim();
      const kid = el.parentElement && el.parentElement.querySelector(':scope > .field-label');
      if (kid && el.parentElement.querySelectorAll(':scope input[type=number]').length === 1) return kid.innerText.trim();
    }
    // a row of its own: the label cell beside the input in the same grid row (fire-alarm devices: "Heat detectors ...")
    const beside = e.previousElementSibling;
    if (beside && isGrid(e.parentElement) && !hasInput(beside) && beside.innerText.trim()) return beside.innerText.trim();
    const col = columnHeader(e);
    if (col) return col;
    // one label over a group whose inputs each say their own unit (heat exchanger: "Hot Side: Inlet / Outlet" over
    // °C in | °C out | kg/s)
    for (let el = e.parentElement, i = 0; el && i < 3; el = el.parentElement, i++) {
      const kid = el.querySelector(':scope > .field-label');
      if (kid && e.parentElement.querySelector('.input-unit')) return kid.innerText.trim();
    }
    return '';
  };
  const UNIT_WORD = /\b(DFU|kWp?|kW|kVA|kN|kPa|MPa|mm|m|m²|m³|L\/s|lps|gpm|°C|Hz|A|V|W|h|rpm|%)\b/;
  const fields = nums.map((e) => {
    const label = ownLabel(e);
    const head = columnHeader(e);
    const span = ((e.parentElement.querySelector('.input-unit') || {}).innerText || '').trim()
      || (/^(count|qty|quantity|no\.?)$/i.test(head) ? 'count' : '');
    const inLabel = (label.match(/\(([^)]{1,16})\)\s*$/) || label.match(/\(([^)]{1,16})\)/) || [])[1] || '';
    // a count names its own unit: "No. of Bars", "Number of Bolts in Joint"
    // ...and so do "No. Nozzles" (no "of") and a count per something ("Doors per Floor")
    const count = /^(no\.?\s*of|number of|count of|qty|quantity)\b|^no\.\s+\w|\bcount\b|^\w+s per \w+/i.test(label) ? 'count' : '';
    const word = (label.match(UNIT_WORD) || [])[0] || '';   // a header that names its unit: "DFU each"
    return { id: e.id, label: label.slice(0, 60), unit: span || inLabel || count || word };
  });
  const card = document.querySelector('.calc-card.selected, .calc-card.active, .calc-card[aria-pressed="true"], .calc-card[aria-current]');
  return { fields, selected: card ? card.innerText.trim().split('\n')[0].slice(0, 60) : null };
};
const FILL = () => {
  let n = 0;
  for (const inp of document.querySelectorAll('#input-form-area input[type=number]')) {
    if (!inp.checkVisibility()) continue;
    const cur = parseFloat(inp.value);
    if (inp.value !== '' && cur > 0) continue;
    let d = parseFloat(inp.placeholder);
    if (!(d > 0)) d = 10;
    const lo = inp.min !== '' ? Number(inp.min) : null, hi = inp.max !== '' ? Number(inp.max) : null;
    if (lo != null && d < lo) d = lo;
    if (hi != null && d > hi) d = hi;
    inp.value = String(d); inp.dispatchEvent(new Event('input', { bubbles: true })); inp.dispatchEvent(new Event('change', { bubbles: true }));
    n++;
  }
  return n;
};
async function freshStranger(ctx) {
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/index.html`, { waitUntil: 'domcontentloaded' });
  await p.waitForFunction(() => !!window._whSupabaseClient || (typeof window.getDb === 'function' && !!window.SUPABASE_KEY), { timeout: 20000 });
  const username = `seprobe_${Date.now().toString(36)}`;
  const r = await p.evaluate(async (username) => {
    const db = window._whSupabaseClient || window.getDb('http://127.0.0.1:54321', window.SUPABASE_KEY);
    const { data, error } = await db.auth.signUp({ email: username + '@auth.workhiveph.com', password: 'Probe!' + username });
    if (error || !data.session) return { ok: false, err: error ? error.message : 'no session (confirmation on?)' };
    const { error: pe } = await db.from('worker_profiles').insert({ auth_uid: data.user.id, username, display_name: 'SE Probe ' + username.slice(-4) });
    if (pe) return { ok: false, err: 'profile: ' + pe.message };
    localStorage.setItem('wh_last_worker', 'SE Probe ' + username.slice(-4));
    return { ok: true };
  }, username);
  await p.close();
  if (!r.ok) throw new Error('SIGN-UP FAILED - a stranger who cannot make an account measures nothing: ' + r.err);
  return username;
}
async function masteryCalc(anon, fresh, page) {
  const p = await anon.newPage();
  await p.goto(urlOf(page), { waitUntil: 'load', timeout: 45000 }).catch(() => {});
  await p.waitForTimeout(1500);
  const tool = await p.evaluate(() => !!document.querySelector('[data-wh-kpi-calc], [data-wh-solar-planner]'));
  if (tool) {
    // the page's own tool, signed out: fill what is empty from the page's own placeholders and read what it draws
    const mount = '[data-wh-kpi-calc], [data-wh-solar-planner]';
    const before = await p.locator(mount).innerText().catch(() => '');
    // a list-building tool opens empty and NAMES its first step ("start from a small home and change it"): that is the
    // page's own guidance, so the stranger takes it - one counted step
    const started = await p.evaluate((sel) => {
      const b = [...document.querySelector(sel).querySelectorAll('button')]
        .find((x) => x.checkVisibility() && /^(start from|use the example|try the example)/i.test(x.innerText.trim()));
      if (b) b.click();
      return b ? b.innerText.trim().slice(0, 40) : null;
    }, mount);
    if (started) await p.waitForTimeout(800);
    const m = await p.evaluate((sel) => {
      const root = document.querySelector(sel);
      const nums = [...root.querySelectorAll('input[type=number]')].filter((e) => e.checkVisibility());
      const fields = nums.map((e) => ({ id: e.id, label: ((e.labels && e.labels[0]) ? e.labels[0].innerText : e.getAttribute('aria-label') || '').trim().slice(0, 60) }));
      let n = 0;
      for (const e of nums) {
        if (e.value !== '' && parseFloat(e.value) > 0) continue;
        e.value = String(parseFloat(e.placeholder) > 0 ? parseFloat(e.placeholder) : 10);
        e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); n++;
      }
      // a tool that opens on the worked example's numbers and works as you type: the stranger enters a number of their
      // own (the first field, 10% lower, inside its range) and the result must follow it
      if (!n && nums.length) {
        const e = nums[0], cur = parseFloat(e.value);
        let v = Math.round(cur * 0.9 * 100) / 100;
        if (e.min !== '' && v < Number(e.min)) v = Number(e.min);
        if (e.max !== '' && v > Number(e.max)) v = Number(e.max);
        e.value = String(v); e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); n = 1;
      }
      const btn = [...root.querySelectorAll('button')].find((b) => /work it out|calculate|plan|compute/i.test(b.innerText));
      if (btn) btn.click();
      return { fields, filled: n, pressed: btn ? btn.innerText.trim().slice(0, 30) : null };
    }, mount);
    await p.waitForTimeout(1500);
    const after = await p.locator(mount).innerText().catch(() => '');
    const changed = after !== before;
    // only what APPEARED counts as the result: the tool's own labels ("LED bulb (9 W)") carry units before anyone acts
    const was = new Set(before.split('\n').map((l) => l.trim()));
    const fresh = after.split('\n').map((l) => l.trim()).filter((l) => l && !was.has(l)).join('\n');
    const resultUnits = UNIT_RE.test(fresh) && /\d/.test(fresh);
    const explained = m.fields.every((f) => f.label);
    await p.close();
    return { path: 'in-page tool, signed out', pass: explained && changed && resultUnits, explained, inputs: m.fields.length,
             started, filled: m.filled, pressed: m.pressed, resultDrawn: changed, resultHasUnits: resultUnits,
             steps: (started ? 1 : 0) + m.filled + (m.pressed ? 1 : 0) };
  }
  await p.close();
  // content page: the stranger (a fresh account) presses the page's own hand-off and works on the calculator it names
  const q = await fresh.newPage();
  await q.goto(urlOf(page), { waitUntil: 'load', timeout: 45000 }).catch(() => {});
  await q.waitForTimeout(1200);
  const link = q.locator('main a[href*="engineering-design.html"]').first();
  if (!(await link.count())) { await q.close(); return { pass: false, why: 'no hand-off link in the page' }; }
  await link.scrollIntoViewIfNeeded().catch(() => {});
  await Promise.all([q.waitForURL(/engineering-design\.html/, { timeout: 30000 }).catch(() => {}), link.click()]);
  const landed = await q.waitForFunction(() => { const b = document.getElementById('calc-btn'); return b && !b.disabled; }, { timeout: 30000 }).then(() => true).catch(() => false);
  if (!landed) { const u = q.url(); await q.close(); return { pass: false, why: 'the calculator never became ready', at: u }; }
  const form = await q.evaluate(FORM);
  const filled = await q.evaluate(FILL);
  await q.click('#calc-btn');
  const shown = await q.waitForFunction(() => { const o = document.getElementById('report-output'); return o && !o.classList.contains('hidden'); }, { timeout: 90000 }).then(() => true).catch(() => false);
  const said = await q.evaluate(() => (document.getElementById('toast') || {}).innerText || '');
  const report = shown ? await q.evaluate(() => (document.getElementById('report-panel') || {}).innerText || '') : '';
  const pdf = shown ? await q.evaluate(() => { const b = document.getElementById('pdf-btn'); return !!b && b.checkVisibility(); }) : false;
  await q.close();
  const explained = form.fields.length > 0 && form.fields.every((f) => f.label);
  const unitsStated = form.fields.filter((f) => f.unit).length;
  const pass = explained && unitsStated === form.fields.length && shown && UNIT_RE.test(report) && pdf;
  return { path: 'hand-off to the signed-in suite, a fresh account', pass, selected: form.selected, inputs: form.fields.length,
           explained, unitsStated, noUnit: form.fields.filter((f) => !f.unit).map((f) => f.label || f.id).slice(0, 6),
           unlabelled: form.fields.filter((f) => !f.label).map((f) => f.id).slice(0, 6),
           filled, computed: shown, toast: said.slice(0, 120), resultHasUnits: UNIT_RE.test(report), exportable: pdf,
           steps: 1 + filled + 1 };
}

const prev = existsSync(REPORT) ? JSON.parse(readFileSync(REPORT, 'utf8')) : {};
const out = prev[MODE] || {};
const b = await chromium.launch();
let bad = 0;
const strangers = [];
for (const [vp, size] of Object.entries(VIEWPORTS)) {
  const ctx = await b.newContext({ viewport: size, serviceWorkers: 'block' });
  await ctx.addInitScript(ALL_ROWS_DRAWN);   // SL LB3: a long list draws every row, so a page's text is the whole page
  // a stranger leaves no ledger trail of a measurement
  await ctx.route('**/rest/v1/analytics_events*', (r) => (r.request().method() === 'POST' ? r.fulfill({ status: 201, body: '' }) : r.continue()));
  let fresh = null;
  if (MODE === 'calc-mastery') {
    fresh = await b.newContext({ viewport: size, serviceWorkers: 'block' });
    await fresh.addInitScript(ALL_ROWS_DRAWN);
    await fresh.route('**/rest/v1/analytics_events*', (r) => (r.request().method() === 'POST' ? r.fulfill({ status: 201, body: '' }) : r.continue()));
    strangers.push(await freshStranger(fresh));
  }
  for (const page of pages) {
    if (MODE === 'calc-mastery') {
      // ★A STRANGER COMPUTES A FEW CALCULATORS, NOT 57 IN AN HOUR. The engine allows 30 AI calls per person per hour
      // (_shared/rate-limit.ts); one account walking every page met that limit at the 30th page and the rest read as
      // failures (2026-10-27). A fresh stranger every 25 computations keeps each one inside what a person would do.
      if (fresh && fresh.__computed >= 25) {
        await fresh.close();
        fresh = await b.newContext({ viewport: size, serviceWorkers: 'block' });
        await fresh.addInitScript(ALL_ROWS_DRAWN);
    await fresh.addInitScript(ALL_ROWS_DRAWN);
        await fresh.route('**/rest/v1/analytics_events*', (r) => (r.request().method() === 'POST' ? r.fulfill({ status: 201, body: '' }) : r.continue()));
        strangers.push(await freshStranger(fresh));
      }
      const v = await masteryCalc(ctx, fresh, page).catch((e) => ({ pass: false, why: String(e).slice(0, 160) }));
      if (fresh && v.path && v.path.startsWith('hand-off')) fresh.__computed = (fresh.__computed || 0) + 1;
      if (!v.pass) bad++;
      out[page] = { ...(out[page] || {}), [vp]: { ...v, at: new Date().toISOString() } };
      console.log(`  ${v.pass ? 'ok  ' : 'FAIL'} ${vp.padEnd(12)} ${page}${v.pass ? '' : '  ' + JSON.stringify(v).slice(0, 700)}`);
      continue;
    }
    const p = await ctx.newPage();
    await p.goto(urlOf(page), { waitUntil: 'load', timeout: 45000 }).catch(() => {});
    await p.waitForTimeout(1500);
    let v;
    if (MODE === 'calc-vicarious') {
      const m = await p.evaluate(VICARIOUS).catch((e) => ({ error: String(e).slice(0, 120) }));
      const firstAct = m.firstInputY ?? m.handoffY;
      const pass = !m.error && m.exampleY != null && m.workedText > 80 && firstAct != null && m.exampleY < firstAct;
      v = { pass, ...m, before: m.firstInputY != null ? 'the first input' : 'the hand-off to the calculator' };
    } else {
      const m = await p.evaluate(LEARN).catch((e) => ({ error: String(e).slice(0, 120) }));
      const reached = [];
      for (const href of (m.tools || [])) {
        const q = await ctx.newPage();
        const resp = await q.goto(`${SEEDER}${href}`, { waitUntil: 'load', timeout: 45000 }).catch(() => null);
        await q.waitForTimeout(1200);
        const at = new URL(q.url());
        const want = href.split('?')[0].replace(/^\//, '');
        const path = at.pathname.replace(/^\/workhive\//, '').replace(/^\//, '');
        // the door may route through a prerequisite first (community needs a hive: return=hive.html?return=community.html);
        // what counts is that the chain ENDS at the tool the article named
        let ret = at.searchParams.get('return') || '';
        for (let i = 0; i < 3 && /[?&]return=/.test(ret); i++) ret = new URL(ret, 'http://x/').searchParams.get('return') || ret;
        const ok = (resp && resp.status() < 400) && (path === want || (/index\.html$|^$/.test(path) && at.searchParams.get('signin') === '1' && ret.split('?')[0] === want));
        reached.push({ href, status: resp ? resp.status() : null, landed: path + at.search, ok });
        await q.close();
      }
      const pass = !m.error && m.answer && m.answerVisible && m.answerChars >= 80 && m.answerTop != null
        && m.answerTop < 2 * m.vh && reached.length > 0 && reached.every((x) => x.ok);
      v = { pass, answerTop: m.answerTop, answerChars: m.answerChars, screens: m.vh ? +(m.answerTop / m.vh).toFixed(2) : null, reached };
    }
    if (!v.pass) bad++;
    out[page] = { ...(out[page] || {}), [vp]: { ...v, at: new Date().toISOString() } };
    console.log(`  ${v.pass ? 'ok  ' : 'FAIL'} ${vp.padEnd(12)} ${page}${v.pass ? '' : '  ' + JSON.stringify(v).slice(0, 700)}`);
    await p.close();
  }
  await ctx.close();
  if (fresh) await fresh.close();
}
await b.close();
// the fixture is "removed after the walk": the stranger accounts this run made, and only those
if (strangers.length) {
  // the account leaves with everything its computations wrote (tools/lib/walk_accounts.mjs)
  try { removeWalkAccounts(strangers); console.log(`  removed ${strangers.length} stranger account(s) and what they wrote: ${strangers.join(', ')}`); }
  catch (e) { console.log(`  WARN could not remove the stranger accounts (${strangers.join(', ')}): ${String(e).slice(0, 120)}`); }
}
prev[MODE] = out;
writeFileSync(REPORT, JSON.stringify(prev, null, 1) + '\n');
console.log(`${bad ? 'FAIL' : 'PASS'} self-efficacy ${MODE} - ${pages.length * 2 - bad}/${pages.length * 2} page-viewports (report: ${REPORT})`);
process.exit(bad ? 1 : 0);
