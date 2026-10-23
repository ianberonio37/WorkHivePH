// prove_phone_fit — the PHONE-FIT lens (Ian, 2026-09-06: "text wrapped on their container in inventory; the hive board's
// 'more' overflows and extends left on a phone"). A signed-in supervisor opens each page at a phone viewport (390x844, the
// iPhone 14 class) and the page must FIT: (1) no horizontal page overflow; (2) no visible element sticking out of the
// viewport; (3) no text CLIPPED inside its own box (overflow hidden/clip with scrollWidth > clientWidth) and no unbroken
// token wider than its container (mid-word wrapping / overflow of long ids, emails, urls); (4) every "more"/kebab/menu
// trigger, once tapped, reveals a menu that lies INSIDE the viewport. Each finding names the element + rects.
//
// ★WAVE 4 (2026-09-14, Ian: "overlapping and overflowing in using the platform through phone"): the audit moved to
// tools/phone_fit_audit.mjs so the SAME record is taken here at rest, inside prove_full_journeys.mjs after every step,
// and by an MCP walk (`node tools/phone_fit_audit.mjs --print`). It gained (5) OCCLUSION - a fixed/sticky/toast/hub/
// companion element covering an interactive control (document.elementFromPoint at the control's centre is not the
// control) - and (6) ELEMENT OVERFLOW inside its clipping container, not only text. And this prover gained the axes a
// person actually uses: `--anon` (signed out - the public pages' real reader), `--lang fil` (Filipino expands and
// spills), `--width 320` (46 of 60 calculators had never been walked there), and `--sweep` (the INTERACTION sweep: tap
// what reveals state - sheet, menu, modal, filter, hub, companion, a focused text input with the keyboard - and take
// the record after each, so a finding that appears only after a step is tagged with that step).
//   node tools/prove_phone_fit.mjs                     # every interactive page
//   node tools/prove_phone_fit.mjs --page hive.html    # one page, verbose
//   node tools/prove_phone_fit.mjs --width 360         # a narrower phone
//   node tools/prove_phone_fit.mjs --pages a.html,b.html   # a subset (halves for the 10-minute background cap)
//   node tools/prove_phone_fit.mjs --width 320 --anon --lang fil --sweep --pages tools/oee-calculator/index.html
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { SEEDER, signIn, PAGE_QUERY, DB_PAGES, VIS_JS, assertSignedIn } from './prover_harness.mjs';
import { record, issuesOf, interactionSweep } from './phone_fit_audit.mjs';
const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const LIST = (() => { const i = process.argv.indexOf('--pages'); return i >= 0 ? process.argv[i + 1].split(',') : null; })();   // a subset, so a full pass fits the 10-minute background cap in halves
const W = (() => { const i = process.argv.indexOf('--width'); return i >= 0 ? Number(process.argv[i + 1]) : 390; })();
const ANON = process.argv.includes('--anon');
const LANG = (() => { const i = process.argv.indexOf('--lang'); return i >= 0 ? process.argv[i + 1] : 'en'; })();
const SWEEP = process.argv.includes('--sweep');
// the P-M pool (51 pages = every root page + 8 calculators), generated from tools/seed_p_program_catalog.py _pool_for('P-M') on 2026-09-06
const PHONE_POOL = ["agentic-rag-observability.html", "ai-quality.html", "design-system.html", "founder-console.html", "llm-observability.html", "marketplace-admin.html", "offline-fallback.html", "plant-connections.html", "platform-actions.html", "promo-poster.html", "learn/index.html", "achievements.html", "alert-hub.html", "analytics-report.html", "analytics.html", "asset-hub.html", "assistant.html", "audit-log.html", "community.html", "dayplanner.html", "engineering-design.html", "hive.html", "index.html", "integrations.html", "inventory.html", "logbook.html", "marketplace-seller-profile.html", "marketplace-seller.html", "marketplace.html", "ph-intelligence.html", "pm-scheduler.html", "project-manager.html", "project-report.html", "public-feed.html", "report-sender.html", "resume.html", "shift-brain.html", "skillmatrix.html", "status.html", "voice-journal.html", "tools/ahu-sizing-calculator/index.html", "tools/beam-design-calculator/index.html", "tools/bearing-life-calculator/index.html", "tools/boiler-steam-calculator/index.html", "tools/boiler-system-calculator/index.html", "tools/bolt-torque-calculator/index.html", "tools/cable-tray-sizing-calculator/index.html", "tools/chiller-sizing-calculator/index.html"];
// ★THE POOL IS THE PROGRAM'S PAGES, NOT A LIST (CI3, 2026-10-15). PHONE_POOL was written by hand on 2026-09-06 and held
// 51 pages; the SL program walks 155, so 104 pages - most learn articles and calculators - were never held by this lens.
// The roster is that list plus every page the registry's SL rows name, and a PUBLIC page is read signed out, as the
// visitor it is for (its real reader), in a second context.
const REG = JSON.parse(readFileSync('trajectory_registry.json', 'utf8'));
const SL_CLASS = new Map();
for (const t of REG.trajectories) if (t.sl && t.sl.page && t.status !== 'descoped') SL_CLASS.set(t.sl.page, t.sl.page_class);
const ROSTER = [...new Set([...PHONE_POOL, ...SL_CLASS.keys()])].filter((f) => existsSync(f));
const PAGES = ONLY ? [ONLY] : LIST ? LIST : ROSTER;
const PUBLIC = (f) => SL_CLASS.get(f) === 'public';
// ★A FLOOR PER PAGE, SO A COUNT CAN ONLY FALL (CI3). The gate was zero-tolerance over its 51 pages; held over 155, a page it
// never read would fail it on day one for findings that predate the read. Each axis keeps a floor per page in
// phone_fit_baseline.json: a page absent from it has a floor of 0 (the 51 stay zero-tolerance), a count above the floor
// fails, --rebase lowers floors that fell, and --reseed --reason "..." records the floor when the roster widened.
const BASE_FILE = 'phone_fit_baseline.json';
const BASE = existsSync(BASE_FILE) ? JSON.parse(readFileSync(BASE_FILE, 'utf8')) : { _doc: 'Per-axis, per-page phone-fit issue floors (tools/prove_phone_fit.mjs). A count above its floor fails; --rebase lowers; --reseed --reason records a re-measure. Generated, never hand-edited.', axes: {} };
const REBASE = process.argv.includes('--rebase');
const RESEED = process.argv.includes('--reseed');
const REASON = (() => { const i = process.argv.indexOf('--reason'); return i >= 0 ? process.argv[i + 1] : ''; })();
if (RESEED && !REASON.trim()) { console.log('REFUSED --reseed: say why the floor is re-measured (--reason "...")'); process.exit(1); }
const measured = {};
const MENU_RE = /(⋯|…|⋮|\bmore\b|\bmenu\b|\boptions\b|\bactions\b)/i;
const AXIS = `phone-fit@${W}${ANON ? ' anon' : ''}${LANG !== 'en' ? ' ' + LANG : ''}${SWEEP ? ' +sweep' : ''}`;

// ★1280 IS A DESKTOP, NOT A WIDE PHONE (F2, 2026-10-15). F2 asks for 320, 390 and 1280; a 1280 reading taken with
// isMobile + touch is a tablet emulation that no desktop reader sees (mobile viewport meta, touch hit-testing, DPR 2).
const MOBILE = W < 768;
const VIEW = { viewport: { width: W, height: MOBILE ? 844 : 800 }, isMobile: MOBILE, hasTouch: MOBILE, deviceScaleFactor: MOBILE ? 2 : 1 };
const b = await chromium.launch();
const ctx = await b.newContext({ ...VIEW, serviceWorkers: 'block',
  locale: LANG === 'fil' ? 'fil-PH' : 'en-PH' });
// the platform reads `wh_lang` from localStorage at load (utils.js); setting it BEFORE the first script runs is how a
// Filipino reader arrives, and the record below reads document.documentElement.lang back so a page that ignored the
// setting is visible in the receipt rather than assumed (the wave-3 lesson: "set wh_lang and never looked")
if (LANG === 'fil') await ctx.addInitScript(() => { try { localStorage.setItem('wh_lang', 'fil'); } catch (e) { void e; } });
if (!ANON) await assertSignedIn(signIn(ctx));
let anonCtx = null;
const ctxFor = async (file) => {
  if (ANON || !PUBLIC(file)) return ctx;
  if (!anonCtx) {
    anonCtx = await b.newContext({ ...VIEW, serviceWorkers: 'block',
      locale: LANG === 'fil' ? 'fil-PH' : 'en-PH' });
    if (LANG === 'fil') await anonCtx.addInitScript(() => { try { localStorage.setItem('wh_lang', 'fil'); } catch (e) { void e; } });
  }
  return anonCtx;
};

let bad = 0, n = 0;
for (const file of PAGES) {
  n++;
  const p = await (await ctxFor(file)).newPage();
  await p.goto(`${SEEDER}/workhive/${file}${(ANON || PUBLIC(file)) ? '' : (PAGE_QUERY[file] || '')}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(6500);   // layout settles well inside this; 51 pages x 9 s alone exceeded the 10-minute background cap
  const a = await record(p, VIS_JS, 'at rest');
  // menus: tap every visible more/kebab/menu trigger; the revealed menu (aria-controls, or the newest visible menu/dialog) must fit
  const menus = await p.evaluate((MENU_SRC) => { const re = new RegExp(MENU_SRC, 'i'); return [...document.querySelectorAll('button, [role="button"]')].filter((e) => e.checkVisibility()).filter((e) => ((e.textContent || '').trim().length <= 24 && re.test((e.textContent || '').trim())) || re.test(e.getAttribute('aria-label') || '') || !!e.getAttribute('aria-haspopup')).map((e, i) => { e.setAttribute('data-pf', String(i)); return { i, label: (e.getAttribute('aria-label') || e.textContent || '').trim().slice(0, 24) }; }); }, MENU_RE.source);
  const menuBad = [];
  for (const m of menus.slice(0, 6)) {
    await p.tap(`[data-pf="${m.i}"]`, { timeout: 3000, force: true }).catch(async () => { await p.click(`[data-pf="${m.i}"]`, { timeout: 3000, force: true }).catch(() => {}); });
    await p.waitForTimeout(600);
    const r = await p.evaluate((i) => { const t = document.querySelector(`[data-pf="${i}"]`); const id = t && t.getAttribute('aria-controls'); let menu = id ? document.getElementById(id) : null; if (!menu) { const cands = [...document.querySelectorAll('[role="menu"], .menu, .dropdown, .hive-menu, [class*="menu"], [class*="popover"], [class*="dropdown"]')].filter((e) => e.checkVisibility() && e.getBoundingClientRect().height > 0); menu = cands[cands.length - 1] || null; } if (!menu) return null; const rc = menu.getBoundingClientRect(); return { id: menu.id || menu.className, l: Math.round(rc.left), r: Math.round(rc.right), w: Math.round(rc.width), fits: rc.left >= -1 && rc.right <= innerWidth + 1 }; }, m.i);
    if (r && !r.fits) menuBad.push(`${m.label || '⋯'} -> ${r.id} ${r.l}..${r.r} (vw ${W})`);
    await p.keyboard.press('Escape').catch(() => {}); await p.waitForTimeout(200);
  }
  // the interaction sweep: the states a journey passes through, each with its own record
  const sweep = SWEEP ? await interactionSweep(p, VIS_JS, { max: 6 }) : [];
  if (a.poster) { console.log(`  n/a ${file.padEnd(34)} print poster: a fixed-width artifact by design (rubric artifact-genre=poster)`); n--; await p.close(); continue; }
  // a retired page whose overlay is SHOWN to this reader is measured as that overlay (phone_fit_audit.mjs, 2026-10-15);
  // stranded capabilities stay validate_retired_page_sole_control.py's question
  // ★A MIXED PAGE SATISFIES 3.1.2, NOT 3.1.1, AND THIS ASKED ONLY 3.1.1 (2026-09-29). The old test was
  // `<html lang>` alone, so every learn article and calculator read BAD in FIL — 4 of the 10 pages in the
  // 320-wide sweep — for a state their code chose on purpose. wh-i18n-lite.js swaps the CHROME to Filipino
  // and leaves the PROSE English, stamping `el.lang='fil'` on each element it changed, and says in its own
  // comment that flipping the whole document "would be as untrue as lang='en'" with the primary-language
  // call reserved for Ian. A page whose Filipino is correctly marked part-by-part is conformant; the real
  // defect is Filipino text with NO language declared anywhere, which is what this now catches.
  // ★AND IT MUST FIRST HAVE PUT FILIPINO ON SCREEN (2026-09-29). The rule above says the defect is
  // "Filipino text with NO language declared anywhere" and then tested the OPPOSITE - it fired when the
  // page had no Filipino at all. offline-fallback, symbol-gallery and validator-catalog are English by
  // design (they are in validate_i18n_coverage.py's INTERNAL_EXEMPT), so they answer lang="en" to a
  // Filipino reader and mark no part: the page IS English and declares it truthfully, which is what
  // 3.1.1 asks for. Having no Filipino yet is a COVERAGE gap and that gate's question, not this one's.
  // `filSwapped` is the missing half - the appliers' own evidence that Filipino was rendered - so the
  // finding now fires only on the state it describes, which is where architecture.html genuinely sat:
  // "Mga Risk Column" on screen, under <html lang="en">, with no part marked.
  const langNote = LANG === 'fil' && a.lang && !/^fil|^tl/.test(a.lang) && !a.filParts && a.filSwapped > 0
    ? [`lang: page rendered ${a.filSwapped} Filipino string(s) but answered <html lang="${a.lang}"> and marked no part lang="fil" (WCAG 3.1.1/3.1.2: declare the page's language, or the language of each swapped part)`] : [];
  // ★AND THE RECORD SAYS WHICH FONT IT WAS MEASURED AGAINST (2026-09-29). record() waits on
  // document.fonts.ready under a bounded budget, because Poppins is wider than the fallback and a text-fit
  // lens measured before it applies is measuring a different page - that race is what made this gate read
  // 16/50, then 46/46, then 16/46 with no edit in between. The wait can still time out on a loaded host,
  // and a reading taken against the fallback is legitimate; what is NOT legitimate is not knowing which
  // one it was. Surfaced rather than merely recorded - a flag nothing ever reads is the
  // [[feedback_measured_and_never_kept]] defect, and I would have shipped exactly that.
  const fellBack = [a, ...sweep].filter((r) => r && r.fontsReady === false).length;
  const fontNote = fellBack
    ? [`fonts: ${fellBack} of ${1 + sweep.length} record(s) measured BEFORE the webfont applied (document.fonts.ready timed out) - text-fit findings on this page are against the fallback metrics, not the shipped ones`]
    : [];
  const issues = issuesOf(a).concat(menuBad.map((s) => 'menu: ' + s), langNote, fontNote, ...sweep.map((s) => issuesOf(s)));
  const floor = ((BASE.axes[AXIS] || {})[file]) ?? 0;
  measured[file] = issues.length;
  if (issues.length > floor) bad++;
  console.log(`  ${issues.length > floor ? 'BAD' : (issues.length ? 'held' : 'ok ')} ${file.padEnd(34)} ${issues.length ? issues.length + ' issue(s)' + (issues.length <= floor ? ` (floor ${floor})` : ` > floor ${floor}`) : 'fits'}${PUBLIC(file) && !ANON ? ' [signed out]' : ''}${a.retired ? ' [its retired overlay]' : ''}${a.error ? ' (' + a.error + ')' : ''}${SWEEP ? ` · ${sweep.length} interaction state(s)` : ''}`);
  for (const s of issues.slice(0, ONLY ? 40 : 6)) console.log(`        ${s.slice(0, 170)}`);
  await p.close();
}
await b.close();
// what this axis MEASURED, page by page - the record a coverage prover (CI3: is this page held by the phone-fit ratchet?)
// reads, so 'held' means measured on this run, not merely listed
{ const REPORT = 'phone_fit_report.json'; const rep = existsSync(REPORT) ? JSON.parse(readFileSync(REPORT, 'utf8')) : { _doc: 'The last measured phone-fit issue count per axis and page (tools/prove_phone_fit.mjs). Regenerated by every run.', axes: {} };
  // the path is null on a run that cannot speak for the whole axis: a --page run writes nothing, a --pages run only merges
  const FULL_REPORT = (!ONLY && !LIST) ? REPORT : null, MERGE_REPORT = (LIST && !ONLY) ? REPORT : null;
  if (FULL_REPORT) { rep.axes[AXIS] = { generated: new Date().toISOString(), pages: measured }; writeFileSync(FULL_REPORT, JSON.stringify(rep, null, 1) + '\n'); }
  // a --pages re-read of part of a full run is merged into it, each merged page stamped with its own time, so a page
  // the full run could not read (an instrument fix after the run) is measured without a second 50-minute pass
  else if (MERGE_REPORT && rep.axes[AXIS]) { const ax = rep.axes[AXIS]; ax.merged = ax.merged || {}; const at = new Date().toISOString();
    for (const [f, c] of Object.entries(measured)) { ax.pages[f] = c; ax.merged[f] = at; } writeFileSync(MERGE_REPORT, JSON.stringify(rep, null, 1) + '\n'); } }
if (RESEED || REBASE) {
  const axis = BASE.axes[AXIS] || {};
  if (REBASE && bad) { console.log(`REFUSED --rebase: ${bad} page(s) rose above their floor; fix them first`); process.exit(1); }
  for (const [f, c] of Object.entries(measured)) axis[f] = RESEED ? c : Math.min(c, axis[f] ?? 0);
  for (const f of Object.keys(axis)) if (!axis[f]) delete axis[f];
  BASE.axes[AXIS] = axis;
  BASE.generated = new Date().toISOString();
  if (RESEED) BASE.note = `${AXIS}: reseeded - ${REASON}`;
  writeFileSync(BASE_FILE, JSON.stringify(BASE, null, 1) + '\n');
  console.log(`${RESEED ? 'reseeded' : 'rebased'} ${AXIS}: ${Object.keys(axis).length} page(s) hold a non-zero floor (${Object.values(axis).reduce((x, y) => x + y, 0)} issue(s))`);
  process.exit(0);
}
const held = Object.entries(measured).filter(([f, c]) => c && c <= (((BASE.axes[AXIS] || {})[f]) ?? 0)).length;
console.log(`${bad ? 'FAIL' : 'PASS'} ${AXIS} - ${n - bad}/${n} pages at or under their floor (no overflow, no clipped text, no occluded control, menus inside the viewport)${held ? `; ${held} page(s) held at a non-zero floor` : ''}`);
process.exit(bad ? 1 : 0);
