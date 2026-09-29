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
import { SEEDER, signIn, PAGE_QUERY, DB_PAGES, VIS_JS } from './prover_harness.mjs';
import { record, issuesOf, interactionSweep } from './phone_fit_audit.mjs';
const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const LIST = (() => { const i = process.argv.indexOf('--pages'); return i >= 0 ? process.argv[i + 1].split(',') : null; })();   // a subset, so a full pass fits the 10-minute background cap in halves
const W = (() => { const i = process.argv.indexOf('--width'); return i >= 0 ? Number(process.argv[i + 1]) : 390; })();
const ANON = process.argv.includes('--anon');
const LANG = (() => { const i = process.argv.indexOf('--lang'); return i >= 0 ? process.argv[i + 1] : 'en'; })();
const SWEEP = process.argv.includes('--sweep');
// the P-M pool (51 pages = every root page + 8 calculators), generated from tools/seed_p_program_catalog.py _pool_for('P-M') on 2026-09-06
const PHONE_POOL = ["agentic-rag-observability.html", "ai-quality.html", "design-system.html", "founder-console.html", "llm-observability.html", "marketplace-admin.html", "offline-fallback.html", "plant-connections.html", "platform-actions.html", "promo-poster.html", "symbol-gallery.html", "validator-catalog.html", "learn/index.html", "achievements.html", "alert-hub.html", "analytics-report.html", "analytics.html", "architecture.html", "asset-hub.html", "assistant.html", "audit-log.html", "community.html", "dayplanner.html", "engineering-design.html", "hive.html", "index.html", "integrations.html", "inventory.html", "logbook.html", "marketplace-seller-profile.html", "marketplace-seller.html", "marketplace.html", "ph-intelligence.html", "pm-scheduler.html", "project-manager.html", "project-report.html", "public-feed.html", "report-sender.html", "resume.html", "shift-brain.html", "skillmatrix.html", "status.html", "voice-journal.html", "tools/ahu-sizing-calculator/index.html", "tools/beam-design-calculator/index.html", "tools/bearing-life-calculator/index.html", "tools/boiler-steam-calculator/index.html", "tools/boiler-system-calculator/index.html", "tools/bolt-torque-calculator/index.html", "tools/cable-tray-sizing-calculator/index.html", "tools/chiller-sizing-calculator/index.html"];
const PAGES = ONLY ? [ONLY] : LIST ? LIST : PHONE_POOL;
const MENU_RE = /(⋯|…|⋮|\bmore\b|\bmenu\b|\boptions\b|\bactions\b)/i;
const AXIS = `phone-fit@${W}${ANON ? ' anon' : ''}${LANG !== 'en' ? ' ' + LANG : ''}${SWEEP ? ' +sweep' : ''}`;

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: W, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2, serviceWorkers: 'block',
  locale: LANG === 'fil' ? 'fil-PH' : 'en-PH' });
// the platform reads `wh_lang` from localStorage at load (utils.js); setting it BEFORE the first script runs is how a
// Filipino reader arrives, and the record below reads document.documentElement.lang back so a page that ignored the
// setting is visible in the receipt rather than assumed (the wave-3 lesson: "set wh_lang and never looked")
if (LANG === 'fil') await ctx.addInitScript(() => { try { localStorage.setItem('wh_lang', 'fil'); } catch (e) { void e; } });
if (!ANON) await signIn(ctx);

let bad = 0, n = 0;
for (const file of PAGES) {
  n++;
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/${file}${ANON ? '' : (PAGE_QUERY[file] || '')}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
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
  if (a.retired) { console.log(`  n/a ${file.padEnd(34)} retired behind #wh-retired-overlay: every control is covered by design; stranded capabilities are validate_retired_page_sole_control.py's question, not this gate's`); n--; await p.close(); continue; }
  // ★A MIXED PAGE SATISFIES 3.1.2, NOT 3.1.1, AND THIS ASKED ONLY 3.1.1 (2026-09-29). The old test was
  // `<html lang>` alone, so every learn article and calculator read BAD in FIL — 4 of the 10 pages in the
  // 320-wide sweep — for a state their code chose on purpose. wh-i18n-lite.js swaps the CHROME to Filipino
  // and leaves the PROSE English, stamping `el.lang='fil'` on each element it changed, and says in its own
  // comment that flipping the whole document "would be as untrue as lang='en'" with the primary-language
  // call reserved for Ian. A page whose Filipino is correctly marked part-by-part is conformant; the real
  // defect is Filipino text with NO language declared anywhere, which is what this now catches.
  const langNote = LANG === 'fil' && a.lang && !/^fil|^tl/.test(a.lang) && !a.filParts
    ? [`lang: page answered <html lang="${a.lang}"> to a Filipino reader and marked no part lang="fil" (WCAG 3.1.1/3.1.2: declare the page's language, or the language of each swapped part)`] : [];
  const issues = issuesOf(a).concat(menuBad.map((s) => 'menu: ' + s), langNote, ...sweep.map((s) => issuesOf(s)));
  if (issues.length) bad++;
  console.log(`  ${issues.length ? 'BAD' : 'ok '} ${file.padEnd(34)} ${issues.length ? issues.length + ' issue(s)' : 'fits'}${a.error ? ' (' + a.error + ')' : ''}${SWEEP ? ` · ${sweep.length} interaction state(s)` : ''}`);
  for (const s of issues.slice(0, ONLY ? 40 : 6)) console.log(`        ${s.slice(0, 170)}`);
  await p.close();
}
await b.close();
console.log(`${bad ? 'FAIL' : 'PASS'} ${AXIS} - ${n - bad}/${n} pages fit a phone (no overflow, no clipped text, no occluded control, menus inside the viewport)`);
process.exit(bad ? 1 : 0);
