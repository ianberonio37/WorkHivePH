// prove_page_reachable.mjs - SL sub-layer F3 (2026-10-15): "The platform must let every control on this page be
// reached, named and pressed: a visible focus, a label a screen reader speaks, a 44px target."
//
// Four readings per page, each from the instrument that owns the question:
//   named     axe-core's own accessible-name rules, run in the page at 1280 (button-name, link-name, label,
//             select-name, input-button-name, aria-command-name, aria-input-field-name, aria-toggle-field-name) -
//             the name computation is axe's, never re-derived here
//   reached   a REAL keyboard walk at 1280 on a desktop context: Tab is pressed until focus comes back round, and
//             every visible control a keyboard user is meant to reach must be focused on the way. A composite
//             widget's roving members (a radio group, a tablist, a menu, a listbox) count as reached when one of
//             them is; a control with tabindex="-1" outside such a widget is a control a keyboard cannot reach
//   focus     on each control the walk focuses, its computed look is compared with its look at rest (and its
//             parent's, for a :focus-within ring): an outline, a changed shadow, border, background, colour or
//             underline is a visible focus; none of them is a focus a sighted keyboard user cannot see (WCAG 2.4.7)
//   target    at 390 on a phone context (mobile, touch): every visible control's target is at least 44x44 CSS px
//             (WCAG 2.5.5) - a checkbox or radio measured together with its <label>, a visually hidden input by its
//             label - except a link inline in a sentence, which 2.5.5 exempts by name
// A page is read signed in through the harness (the cast who reaches every app page), a public page signed out as its
// visitor. A page's F3 row closes only at 0 findings; the gate holds each page at its floor in
// page_reach_baseline.json, so a count can only fall while the rest are brought to 0.
// TEETH (every run, in the same contexts): a planted page with an unnamed icon button, a button whose focus is
// outline:none with nothing else, a 20px button and a link with tabindex="-1" must be caught on all four readings,
// and its clean twin must read 0.
//
//   node tools/prove_page_reachable.mjs                       # the SL F3 roster
//   node tools/prove_page_reachable.mjs --pages a.html,b.html # a subset (merged into the report)
//   node tools/prove_page_reachable.mjs --rebase              # lower the floors that fell (refuses if any rose)
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { SEEDER, signIn, PAGE_QUERY, assertSignedIn } from './prover_harness.mjs';
import { takeBrowserSlot } from './browser_slot.mjs';

const LIST = (() => { const i = process.argv.indexOf('--pages'); return i >= 0 ? process.argv[i + 1].split(',') : null; })();
const REBASE = process.argv.includes('--rebase');
const SETTLE = 5000;
const AXE_SRC = readFileSync('tools/vendor/axe.min.js', 'utf8');
const NAME_RULES = ['button-name', 'link-name', 'label', 'select-name', 'input-button-name', 'aria-command-name',
  'aria-input-field-name', 'aria-toggle-field-name'];
const REG = JSON.parse(readFileSync('trajectory_registry.json', 'utf8'));
const F3 = new Map();
for (const t of REG.trajectories) if (t.sl && t.sl.sublayer === 'F3' && t.status !== 'descoped') F3.set(t.sl.page, t);
const PAGES = (LIST || [...F3.keys()].sort()).filter((f) => existsSync(f));
const PUBLIC = (f) => (F3.get(f) || {}).sl && F3.get(f).sl.page_class === 'public';

// ── in-page: the controls a person is offered, each tagged with an index and its look at rest ──────────────────────
function enumerate() {
  const vis = (e) => !!e && (typeof e.checkVisibility === 'function' ? e.checkVisibility({ visibilityProperty: true, opacityProperty: true }) : e.offsetParent !== null);
  const SEL = 'a[href], button, [role="button"], [role="link"], [role="tab"], [role="menuitem"], [role="option"], [role="radio"], [role="checkbox"], [role="switch"], input:not([type="hidden"]), select, textarea, summary, [tabindex]:not([tabindex="-1"])';
  const srOnly = (e) => { const c = getComputedStyle(e); const r = e.getBoundingClientRect(); return r.width <= 1 || r.height <= 1 || (c.clip && c.clip !== 'auto') || (c.clipPath && c.clipPath !== 'none' && /inset\(50%|rect\(0/.test(c.clipPath)); };
  const sig = (e) => { if (!e) return null; const c = getComputedStyle(e); const ring = c.outlineStyle !== 'none' && parseFloat(c.outlineWidth) > 0 && !/rgba\(\d+,\s*\d+,\s*\d+,\s*0\)|transparent/.test(c.outlineColor);
    return { o: ring ? `${c.outlineStyle} ${c.outlineWidth} ${c.outlineColor}` : '', bs: c.boxShadow, bc: `${c.borderTopColor} ${c.borderRightColor} ${c.borderBottomColor} ${c.borderLeftColor} ${c.borderTopWidth}`, bg: c.backgroundColor, td: c.textDecorationLine, col: c.color }; };
  const name = (e) => (e.getAttribute('aria-label') || e.textContent || e.getAttribute('title') || e.getAttribute('placeholder') || e.id || e.tagName).replace(/\s+/g, ' ').trim().slice(0, 40);
  const where = (e) => (e.id ? '#' + e.id : e.tagName.toLowerCase() + (typeof e.className === 'string' && e.className.trim() ? '.' + e.className.trim().split(/\s+/)[0] : ''));
  const out = [];
  let i = 0;
  for (const e of document.querySelectorAll(SEL)) {
    if (e.closest('[inert], [aria-hidden="true"], script, style, template')) continue;
    if (e.disabled || e.getAttribute('aria-disabled') === 'true') continue;
    // ★RENDERED FIRST: a control under display:none has a 0x0 box, which the visually-hidden test below would read as
    // an sr-only input - so hive's closed create/join forms and two closed sheets read as 12 controls the keyboard
    // "never reaches" (trial run, 2026-10-15). A visually hidden control is RENDERED and clipped; a closed one is not.
    if (typeof e.checkVisibility === 'function' && !e.checkVisibility({ visibilityProperty: true })) continue;
    const hidden = srOnly(e);
    if (!vis(e) && !hidden) continue;
    if (hidden && !(e.labels && e.labels.length)) continue;   // a visually hidden control with no label to press is not offered
    e.setAttribute('data-f3', String(i));
    const role = e.getAttribute('role') || '';
    const group = (e.type === 'radio' && e.name) ? 'radio:' + e.name
      : /^(tab|menuitem|option|radio)$/.test(role) ? role + ':' + where(e.closest('[role="tablist"], [role="menu"], [role="menubar"], [role="listbox"], [role="radiogroup"]') || e.parentElement || document.body) : null;
    out.push({ i, key: where(e) + '|' + name(e), where: where(e), name: name(e), tabindex: e.getAttribute('tabindex'), group, hidden,
      rest: sig(e), restParent: sig(e.parentElement) });
    i++;
  }
  return out;
}

// the 390 target reading: every offered control's target box (a checkbox/radio with its labels; a hidden input by its
// labels), and the WCAG 2.5.5 inline exemption (a link whose nearest block carries meaningfully more text than it)
function targets() {
  const vis = (e) => !!e && (typeof e.checkVisibility === 'function' ? e.checkVisibility({ visibilityProperty: true, opacityProperty: true }) : e.offsetParent !== null);
  const BLOCK = /^(P|LI|TD|TH|BLOCKQUOTE|DIV|SECTION|ARTICLE|FIGCAPTION|DD|DT|H[1-6]|SPAN|SMALL|LABEL)$/;
  const inSentence = (el) => { if (el.tagName !== 'A') return false; let b = el.parentElement; while (b && !BLOCK.test(b.tagName)) b = b.parentElement; if (!b) return false;
    const t = (b.textContent || '').replace(/\s+/g, ' ').trim(), own = (el.textContent || '').replace(/\s+/g, ' ').trim(); return t.length > own.length + 12; };
  // a TARGET is something a pointer activates (WCAG 2.5.5); a scroll region made focusable so a keyboard can scroll it
  // (community's members-online strip, role=region tabindex=0) is reached, never tapped, so it is not sized here
  const ACT = 'a[href], button, input, select, textarea, summary, [role="button"], [role="link"], [role="tab"], [role="menuitem"], [role="option"], [role="radio"], [role="checkbox"], [role="switch"]';
  const out = [];
  for (const e of document.querySelectorAll('[data-f3]')) {
    if (!e.matches(ACT)) continue;
    const boxes = [];
    const hidden = e.getAttribute('data-f3-hidden') === '1';
    if (!hidden && vis(e)) boxes.push(e.getBoundingClientRect());
    if ((hidden || e.type === 'checkbox' || e.type === 'radio') && e.labels) for (const l of e.labels) if (vis(l)) boxes.push(l.getBoundingClientRect());
    const real = boxes.filter((r) => r.width > 0 && r.height > 0);
    if (!real.length) continue;
    // the target is the largest single box a tap can land on (a label and its input are one target when they touch)
    const L = Math.min(...real.map((r) => r.left)), T = Math.min(...real.map((r) => r.top)), R = Math.max(...real.map((r) => r.right)), B = Math.max(...real.map((r) => r.bottom));
    const w = Math.round(R - L), h = Math.round(B - T);
    if (w >= 44 && h >= 44) continue;
    if (inSentence(e)) continue;
    out.push({ i: Number(e.getAttribute('data-f3')), w, h });
  }
  return out;
}

async function readPage(page, url) {
  await page.goto(url, { waitUntil: 'load', timeout: 45000 }).catch(() => {});
  await page.waitForTimeout(SETTLE);
}

async function measure(desk, phone, url) {
  // ── 1280: named + reached + focus ──
  await readPage(desk, url);
  await desk.mouse.move(0, 0).catch(() => {});
  const controls = await desk.evaluate(enumerate);
  await desk.evaluate((ids) => { for (const i of ids) { const e = document.querySelector(`[data-f3="${i}"]`); if (e) e.setAttribute('data-f3-hidden', '1'); } }, controls.filter((c) => c.hidden).map((c) => c.i));
  await desk.addScriptTag({ content: AXE_SRC }).catch(() => {});
  const unnamed = await desk.evaluate(async (rules) => {
    if (typeof axe === 'undefined') return [{ rule: 'axe-not-loaded', target: '' }];
    const r = await axe.run(document, { runOnly: { type: 'rule', values: rules }, resultTypes: ['violations'] });
    return r.violations.flatMap((v) => v.nodes.map((n) => ({ rule: v.id, target: String(n.target && n.target[0] || '').slice(0, 60) })));
  }, NAME_RULES);
  await desk.evaluate(() => { if (document.activeElement && document.activeElement !== document.body) document.activeElement.blur(); window.scrollTo(0, 0); });
  const byIdx = new Map(controls.map((c) => [c.i, c]));
  const reached = new Set(), noFocus = [];
  // ★THE BUDGET FOLLOWS THE PAGE, NOT THE FIRST COUNT: community loads more posts as focus scrolls the feed, so its tab
  // order outgrew the 72 controls counted at rest and a budget fixed from that count ran out before the controls after
  // the feed (load more, the FAQ, the post button). Re-counted from the live tab stops every 40 presses; 900 is the cap.
  const stops = () => desk.evaluate(() => document.querySelectorAll('a[href], button, input:not([type="hidden"]), select, textarea, summary, [tabindex]:not([tabindex="-1"])').length);
  let max = Math.min(900, Math.max(controls.length, await stops()) * 2 + 40);
  let bodyStreak = 0;
  for (let k = 0; k < max; k++) {
    if (k && k % 40 === 0) max = Math.min(900, Math.max(max, (await stops()) * 2 + 40));
    await desk.keyboard.press('Tab');
    const f = await desk.evaluate(() => {
      const e = document.activeElement;
      if (!e || e === document.body) return { body: true };
      // a date/time input keeps focus across its internal segments (month, day, year), so the SAME element focused on
      // consecutive presses is still moving forward; only a repeat after other elements is the walk coming back round
      const stay = window.__f3Last === e;
      window.__f3Last = e;
      const seen = !stay && e.getAttribute('data-f3-seen');
      e.setAttribute('data-f3-seen', '1');
      if (stay) return { stay: true };
      const c = getComputedStyle(e), p = e.parentElement && getComputedStyle(e.parentElement);
      const ring = c.outlineStyle !== 'none' && parseFloat(c.outlineWidth) > 0 && !/rgba\(\d+,\s*\d+,\s*\d+,\s*0\)|transparent/.test(c.outlineColor);
      const sig = (cs, o) => ({ o, bs: cs.boxShadow, bc: `${cs.borderTopColor} ${cs.borderRightColor} ${cs.borderBottomColor} ${cs.borderLeftColor} ${cs.borderTopWidth}`, bg: cs.backgroundColor, td: cs.textDecorationLine, col: cs.color });
      const pring = p && p.outlineStyle !== 'none' && parseFloat(p.outlineWidth) > 0 && !/rgba\(\d+,\s*\d+,\s*\d+,\s*0\)|transparent/.test(p.outlineColor);
      const nm = (e.getAttribute('aria-label') || e.textContent || e.getAttribute('title') || e.getAttribute('placeholder') || e.id || e.tagName).replace(/\s+/g, ' ').trim().slice(0, 40);
      const wh = e.id ? '#' + e.id : e.tagName.toLowerCase() + (typeof e.className === 'string' && e.className.trim() ? '.' + e.className.trim().split(/\s+/)[0] : '');
      return { idx: e.hasAttribute('data-f3') ? Number(e.getAttribute('data-f3')) : null, key: wh + '|' + nm, again: !!seen, now: sig(c, ring ? 'ring' : ''), nowParent: p ? sig(p, pring ? 'ring' : '') : null };
    });
    if (f.stay) continue;                                    // inside a date/time input's segments
    if (f.body) { if (++bodyStreak >= 3) break; continue; }  // focus left the document and did not come back
    bodyStreak = 0;
    if (f.again) break;                                      // focus came back round
    // ★A REPAINT REPLACES THE ELEMENT, NOT THE CONTROL: a live poll re-renders a list between the enumeration and the
    // Tab, and the new node carries no data-f3. It is matched to the unreached control with the same place and name,
    // or it would read as a control the keyboard never reaches.
    let idx = f.idx;
    if (idx === null || !byIdx.has(idx)) { const twin = controls.find((x) => x.key === f.key && !reached.has(x.i)); if (!twin) continue; idx = twin.i; }
    reached.add(idx);
    const c = byIdx.get(idx);
    if (!c || c.hidden) continue;                            // a visually hidden input shows its focus on its label (not read here)
    const changed = (a, b) => !!a && !!b && (a.o || a.bs !== b.bs || a.bc !== b.bc || a.bg !== b.bg || a.td !== b.td || a.col !== b.col);
    if (!(f.now.o || changed(f.now, c.rest) || changed(f.nowParent, c.restParent))) noFocus.push(c);
  }
  const groupsReached = new Set([...reached].map((i) => (byIdx.get(i) || {}).group).filter(Boolean));
  const missed = controls.filter((c) => !reached.has(c.i) && !(c.group && groupsReached.has(c.group)));
  // ★A CONTROL THE PAGE WITHDREW IS NOT ONE THE KEYBOARD MISSED: learn-link.js folds its guide chip after 8 s or the
  // first scroll and hides the chip's dismiss button (the folded chip unfolds on Enter and brings it back), and the
  // walk's own focus-scrolling folds it. Unreached means still rendered when the walk ends and never focused.
  const still = await desk.evaluate((ids) => ids.filter((i) => { const e = document.querySelector(`[data-f3="${i}"]`);
    return !!e && (typeof e.checkVisibility !== 'function' || e.checkVisibility({ visibilityProperty: true })); }), missed.map((c) => c.i));
  const unreached = missed.filter((c) => still.includes(c.i));
  const withdrawn = missed.filter((c) => !still.includes(c.i)).map((c) => `${c.where} "${c.name}"`);
  // ── 390: target size ──
  await readPage(phone, url);
  await phone.evaluate(enumerate);
  await phone.evaluate(() => { for (const e of document.querySelectorAll('[data-f3]')) { const r = e.getBoundingClientRect(); const c = getComputedStyle(e); if (r.width <= 1 || r.height <= 1 || (c.clip && c.clip !== 'auto')) e.setAttribute('data-f3-hidden', '1'); } });
  const small = await phone.evaluate(targets);
  const phoneNames = await phone.evaluate(() => Object.fromEntries([...document.querySelectorAll('[data-f3]')].map((e) => [e.getAttribute('data-f3'),
    (e.id ? '#' + e.id : e.tagName.toLowerCase() + (typeof e.className === 'string' && e.className.trim() ? '.' + e.className.trim().split(/\s+/)[0] : '')) + ' "' + (e.getAttribute('aria-label') || e.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 24) + '"'])));
  return {
    controls: controls.length, reached: reached.size, withdrawn,
    unnamed, unreached: unreached.map((c) => `${c.where} "${c.name}"${c.tabindex === '-1' ? ' (tabindex=-1)' : ''}`),
    noFocus: noFocus.map((c) => `${c.where} "${c.name}"`),
    small: small.map((s) => `${phoneNames[s.i] || s.i} ${s.w}x${s.h}`),
  };
}

const counts = (m) => ({ unnamed: m.unnamed.length, unreached: m.unreached.length, noFocus: m.noFocus.length, small: m.small.length });
const total = (m) => Object.values(counts(m)).reduce((a, b) => a + b, 0);

// ── teeth: the four failures planted, and their clean twin ──
const SLOP = `<!doctype html><html lang="en"><head><style>#nofocus:focus,#nofocus:focus-visible{outline:none}</style></head><body><main>
<button id="unnamed" style="width:48px;height:48px"><svg width="16" height="16" aria-hidden="true"><rect width="16" height="16"/></svg></button>
<button id="nofocus" style="width:120px;height:48px;border:0;background:#eee;color:#000">Save</button>
<button id="small" style="width:20px;height:20px">x</button>
<a id="unreached" href="#x" tabindex="-1" style="display:inline-block;min-width:60px;min-height:48px">Open the report</a>
</main></body></html>`;
const CLEAN = `<!doctype html><html lang="en"><head><style>button:focus-visible,a:focus-visible{outline:2px solid #06c}</style></head><body><main>
<button style="width:48px;height:48px" aria-label="Add"><svg width="16" height="16" aria-hidden="true"><rect width="16" height="16"/></svg></button>
<button style="width:120px;height:48px">Save</button>
<a href="#x" style="display:inline-block;min-width:60px;min-height:48px">Open the report</a>
</main></body></html>`;

await takeBrowserSlot('page-reachable');
const b = await chromium.launch();
const DESK = { viewport: { width: 1280, height: 800 }, serviceWorkers: 'block', locale: 'en-PH' };
const PHONE = { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2, serviceWorkers: 'block', locale: 'en-PH' };
const ctx = { in: { desk: await b.newContext(DESK), phone: await b.newContext(PHONE) }, out: { desk: await b.newContext(DESK), phone: await b.newContext(PHONE) } };
await assertSignedIn(signIn(ctx.in.desk));
await assertSignedIn(signIn(ctx.in.phone));
const tabs = { in: { desk: await ctx.in.desk.newPage(), phone: await ctx.in.phone.newPage() }, out: { desk: await ctx.out.desk.newPage(), phone: await ctx.out.phone.newPage() } };

async function teeth() {
  const res = {};
  for (const [k, html] of [['slop', SLOP], ['clean', CLEAN]]) {
    const route = `${SEEDER}/__f3_teeth_${k}.html`;
    for (const c of Object.values(ctx.out)) await c.route(route, (r) => r.fulfill({ status: 200, contentType: 'text/html', body: html }));
    res[k] = await measure(tabs.out.desk, tabs.out.phone, route);
  }
  const s = counts(res.slop);
  const bit = s.unnamed > 0 && s.noFocus > 0 && s.small > 0 && s.unreached > 0 && total(res.clean) === 0;
  return { slop: s, clean: counts(res.clean), clean_detail: total(res.clean) ? res.clean : undefined, bit };
}

const t = await teeth();
console.log(`  teeth - an unnamed icon button, an invisible focus, a 20px target and a tabindex=-1 link: ${JSON.stringify(t.slop)}; clean twin ${JSON.stringify(t.clean)} -> ${t.bit ? 'all CAUGHT' : 'NOT ALL CAUGHT'}`);
if (t.clean_detail) console.log('    clean twin read: ' + JSON.stringify(t.clean_detail).slice(0, 300));

const BASE_FILE = 'page_reach_baseline.json';
const BASE = existsSync(BASE_FILE) ? JSON.parse(readFileSync(BASE_FILE, 'utf8')) : null;
const floors = (BASE && BASE.pages) || {};
const results = [];
let rose = 0;
for (const file of PAGES) {
  const who = PUBLIC(file) ? 'out' : 'in';
  const url = `${SEEDER}/workhive/${file}${who === 'in' ? (PAGE_QUERY[file] || '') : ''}`;
  let m;
  try { m = await measure(tabs[who].desk, tabs[who].phone, url); }
  catch (e) { m = { error: String(e && e.message || e).slice(0, 160), controls: 0, reached: 0, unnamed: [], unreached: [], noFocus: [], small: [] }; }
  const n = m.error ? -1 : total(m);
  const floor = floors[file] ?? 0;
  const over = BASE && n > floor;
  if (over) rose++;
  const problems = m.error ? [`not read: ${m.error}`] : [
    m.unnamed.length && `${m.unnamed.length} control(s) with no name a screen reader speaks (${[...new Set(m.unnamed.map((u) => u.rule))].join(', ')}: ${m.unnamed.slice(0, 3).map((u) => u.target).join(', ')})`,
    m.unreached.length && `${m.unreached.length} control(s) the keyboard never reaches (${m.unreached.slice(0, 3).join(', ')})`,
    m.noFocus.length && `${m.noFocus.length} control(s) with no visible focus (${m.noFocus.slice(0, 3).join(', ')})`,
    m.small.length && `${m.small.length} target(s) under 44px at 390 (${m.small.slice(0, 3).join(', ')})`,
  ].filter(Boolean);
  results.push({ page: file, cast: (F3.get(file) || {}).persona, as: who === 'in' ? 'signed in' : 'signed out', engine: 'chromium', condition: 'reachable',
    controls: m.controls, reached: m.reached, counts: m.error ? null : counts(m), problems, ok: !problems.length,
    detail: { withdrawn: (m.withdrawn || []).slice(0, 6), unnamed: m.unnamed.slice(0, 12), unreached: m.unreached.slice(0, 12), noFocus: m.noFocus.slice(0, 12), small: m.small.slice(0, 20) } });
  console.log(`  ${over ? 'ROSE' : problems.length ? 'open' : 'ok  '} ${file.padEnd(56)} ${m.error ? 'NOT READ ' + m.error : `${m.reached}/${m.controls} reached · ${JSON.stringify(counts(m))}`}${over ? ` > floor ${floor}` : ''}`);
}
await b.close();

mkdirSync('.tmp', { recursive: true });
const OUT = '.tmp/page_reach_results.json';
const prev = LIST && existsSync(OUT) ? JSON.parse(readFileSync(OUT, 'utf8')) : null;
const merged = prev ? [...prev.results.filter((r) => !PAGES.includes(r.page)), ...results] : results;
writeFileSync(OUT, JSON.stringify({ generated: new Date().toISOString(), sublayer: 'F3', pages: merged.length, teeth: t, results: merged }, null, 1) + '\n');
const notRead = results.filter((r) => !r.counts).length;
if ((!BASE && !LIST) || REBASE) {   // a first floor is written from a FULL run only - a subset would leave every other page at 0
  if (BASE && rose) { console.log(`REFUSED --rebase: ${rose} page(s) rose above their floor`); process.exit(1); }
  const pages = { ...floors };
  for (const r of results) if (r.counts) { const c = Object.values(r.counts).reduce((a, x) => a + x, 0); pages[r.page] = BASE ? Math.min(c, floors[r.page] ?? c) : c; }
  for (const k of Object.keys(pages)) if (!pages[k]) delete pages[k];
  writeFileSync(BASE_FILE, JSON.stringify({ _doc: 'Per-page F3 findings (unnamed + unreached + no visible focus + targets under 44px at 390) - tools/prove_page_reachable.mjs. A page above its floor fails; 0 closes its row. Generated, never hand-edited.', generated: new Date().toISOString(), pages }, null, 1) + '\n');
  console.log(`  floor ${BASE ? 'rebased' : 'written'}: ${Object.keys(pages).length} page(s) hold a non-zero floor (${Object.values(pages).reduce((a, x) => a + x, 0)})`);
}
const closed = results.filter((r) => r.ok).length;
const failed = rose + notRead + (t.bit ? 0 : 1);
console.log(`\n${failed ? 'FAIL' : 'PASS'} page-reachable - ${closed}/${results.length} page(s) with every control reached, named, focused visibly and 44px; ${rose} above their floor, ${notRead} not read -> ${OUT}`);
process.exit(failed ? 1 : 0);
