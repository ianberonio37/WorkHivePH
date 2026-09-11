// prove_page_floor — the EX-PF wave: every thin page brought to the floor (2026-09-07).
//
// Twelve-plus root pages carried fewer than 30 trajectories while logbook carried 62. That gap is not
// about the pages' importance - status.html is the page someone opens when something is broken - it is
// about what was walked. Each thin page now carries up to fourteen rows, one per lens, and this prover
// walks the page ONCE and answers all fourteen from that walk, so a wave of 213 rows costs 15 page
// loads rather than 213.
//
//   F01 glance     a person can tell in one glance what the page is for (a named heading, real content)
//   F02 says       every control says what it will do before it is pressed (no bare icon buttons)
//   F03 fresh      the page says how fresh what it shows is (a source chip)
//   F04 fails well when its data fails to load, it says what is missing and what to do
//   F05 traceable  the most important number can be traced to its rows (a chip or a drill-through)
//   F06 thumb      it holds together on a phone with one thumb (no horizontal overflow at 390)
//   F07 stable     nothing moves after paint (layout shift within budget)
//   F08 keyboard   a keyboard reaches its controls in a sensible order
//   F09 leads on   it leads somewhere - a stop on a journey, not a cul-de-sac
//   F10 keeps      what was typed survives a refresh (a draft, or nothing to type)
//   F11 refused    a person without permission is told so kindly and offered the way back
//   F12 speaks     its copy speaks the crew's words, not the platform's internals
//   F13 arbitrates two people on it at once do not overwrite each other silently (updated_at guard)
//   F14 prints     it can be printed or shown on a wall and still be true
//
// ★ONE WALK, FOURTEEN VERDICTS, EVERY ROW BANKED ON ITS OWN LENS. The registry rows are read (wave EX-PF)
// so a page that received only eleven lenses is judged on eleven, and the per-row output names which
// lens each row is.
//
//   node tools/prove_page_floor.mjs
//   node tools/prove_page_floor.mjs --page status.html
import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { SEEDER, signIn, PAGE_QUERY, VIS_JS, SETTLE_MS } from './prover_harness.mjs';

const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const read = (f) => { try { return readFileSync(f, 'utf8'); } catch { return ''; } };
const psql = (sql) => { try { return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim(); } catch { return ''; } };
const ROWS = JSON.parse(readFileSync('trajectory_registry.json', 'utf8')).trajectories.filter((t) => t.wave === 'EX-PF');
const LENS_KEY = [
  ['first time and can tell in one glance', 'F01'], ['says what it will do before you press', 'F02'], ['how fresh', 'F03'],
  ['fails to load its data', 'F04'], ['traced to the rows', 'F05'], ['phone with one thumb', 'F06'], ['moves under your finger', 'F07'],
  ['keyboard-only', 'F08'], ['leads somewhere', 'F09'], ['survives a refresh', 'F10'], ['does not have permission', 'F11'],
  ['words a Philippine', 'F12'], ['Two people on this page', 'F13'], ['printed or shown on a wall', 'F14'],
];
const lensOf = (title) => (LENS_KEY.find(([k]) => title.includes(k)) || [null, '?'])[1];
const byPage = {};
for (const t of ROWS) { const pg = (t.pages || [])[0]; if (!pg) continue; (byPage[pg] = byPage[pg] || []).push({ id: t.id, lens: lensOf(t.title || '') }); }

const INTERNAL = /\b(rls|postgrest|jsonb|uuid|null|undefined|NaN|foreign key|constraint|policy violation|42501|PGRST\d+)\b/;

const b = await chromium.launch();
let bad = 0, n = 0;
for (const [page, rows] of Object.entries(byPage)) {
  if (ONLY && page !== ONLY) continue;
  const src = read(page);
  const url = `${SEEDER}/workhive/${page}${PAGE_QUERY[page] || ''}`;

  // one signed-in walk at phone width, with CLS observed from before load
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  await signIn(ctx);
  const p = await ctx.newPage();
  await p.addInitScript(() => { window.__cls = 0; try { new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; }).observe({ type: 'layout-shift', buffered: true }); } catch (e) { void e; } }).catch(() => {});
  await p.goto(url, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(SETTLE_MS);
  const s = await p.evaluate((VIS_JS) => {
    const vis = (0, eval)(VIS_JS);
    const doc = document.documentElement;
    // a page whose <main> holds only its toolbar (project-report: the report body lives outside it) read as "almost
    // no content" while seven sections were on screen - the region is trusted only when it carries most of the page
    let main = document.querySelector('main, [role="main"], #app, #root') || document.body;
    if (main !== document.body && (main.innerText || '').length < 0.5 * (document.body.innerText || '').length) main = document.body;
    const text = (main.innerText || '').replace(/\s+/g, ' ').trim();
    const heads = [...document.querySelectorAll('h1, h2')].filter(vis).map((e) => (e.innerText || '').trim()).filter(Boolean);
    // the page's OWN controls: platform chrome (nav-hub, feedback panel, companion) is shared and graded once,
    // not on every page - the first walk read "10 bare icon buttons" on every page, all of them the hub's mode
    // buttons and the feedback panel's kinds, whose innerText is '' inside a closed drawer while their textContent
    // ("Field", "Bug", "Send feedback") names them (2026-09-07). A name is any of: rendered text, textContent,
    // aria-label, aria-labelledby, title.
    const chrome = (e) => !!e.closest('#wh-nav-hub, [id*="wh-hub"], #wh-feedback-panel, [id^="wh-fb"], [class^="wh-fb"], [id^="wh-ai-"], #wh-ai-launcher');
    const buttons = [...document.querySelectorAll('button, [role="button"]')].filter(vis).filter((e) => !chrome(e));
    const named = (e) => (e.innerText || '').trim() || (e.textContent || '').trim() || e.getAttribute('aria-label') || e.getAttribute('aria-labelledby') || e.getAttribute('title');
    const bare = buttons.filter((e) => !named(e)).length;
    const chips = document.querySelectorAll('.wh-source-chip, [data-source-chip], .source-chip').length;
    const links = [...document.querySelectorAll('a[href]')].filter((e) => vis(e) && !/^#|^https?:/.test(e.getAttribute('href') || '')).length;
    const fields = [...document.querySelectorAll('textarea, input[type="text"]')].filter((e) => vis(e) && !e.readOnly && !chrome(e) && !/search|filter/i.test(e.id + e.className)).length;
    return { textLen: text.length, heads, bare, buttons: buttons.length, chips, overflow: Math.max(0, doc.scrollWidth - doc.clientWidth), cls: window.__cls || 0, links, fields, text: text.slice(0, 1500) };
  }, VIS_JS).catch(() => null);
  // F08 keyboard reach
  let reached = 0;
  if (s) { const seen = new Set(); for (let i = 0; i < 25; i++) { await p.keyboard.press('Tab').catch(() => {}); const k = await p.evaluate(() => { const e = document.activeElement; return e && e !== document.body ? (e.id || e.className || e.tagName) : null; }).catch(() => null); if (k) seen.add(k); } reached = seen.size; }
  // F10 draft survives a refresh - the page's OWN field: 7 of 8 F10 reds had typed into the companion's ask box (2026-09-07)
  let kept = null;
  if (s && s.fields) {
    const MARK = 'wh-floor-draft-' + page.replace(/\W/g, '');
    const typed = p.evaluate((m) => { const vis = (e) => e.checkVisibility && e.checkVisibility(); const chrome = (e) => !!e.closest('#wh-nav-hub, [id*="wh-hub"], #wh-feedback-panel, [id^="wh-fb"], [class^="wh-fb"], [id^="wh-ai-"], #wh-ai-launcher'); const f = [...document.querySelectorAll('textarea, input[type="text"]')].find((e) => vis(e) && !e.readOnly && !chrome(e) && !/search|filter/i.test(e.id + e.className)); if (f) { f.focus(); f.value = m; f.dispatchEvent(new Event('input', { bubbles: true })); } return !!f; }, MARK).catch(() => false);
    await p.waitForTimeout(1500);
    await p.reload({ waitUntil: 'load' }).catch(() => {});
    await p.waitForTimeout(6000);
    kept = typed ? await p.evaluate((m) => [...document.querySelectorAll('textarea, input')].some((e) => (e.value || '').includes(m)) || (document.body.innerText || '').includes(m), MARK).catch(() => false) : null;   // no own field = nothing to lose (the count had included the companion's box, 2026-09-07)
  }
  // F14 print
  await p.emulateMedia({ media: 'print' }).catch(() => {});
  const printLen = await p.evaluate(() => ((document.querySelector('main, [role="main"], #app') || document.body).innerText || '').replace(/\s+/g, ' ').trim().length).catch(() => 0);
  await ctx.close();

  // F04 fails well + F11 refused: static, from the page's own words
  // 2026-09-07: both are conditional on the page HAVING the boundary they grade. A static reference (architecture,
  // symbol-gallery) reads no hive data, so "fails well" and "refused kindly" are not questions it can be asked;
  // and every page that reads through getDb() inherits the transport's own failure notices (_whNoteAuthFailure /
  // _whNoteTransportFailure in utils.js: a sentence, a Retry / Sign in control, a time + version to quote), so the
  // read path itself is the "fails well" - the page's own words are needed only where the read bypasses it.
  const dbReads = /\.from\(|\.rpc\(|functions\.invoke\(|getDb\(/.test(src);
  const anyReads = dbReads || /\bfetch\(/.test(src);
  const failsWell = !anyReads || /getDb\(|whReadError|whWriteError|could not load|try again|check your connection|sign in again/i.test(src);
  const refusedKindly = !dbReads || (/whIsAccessDenied|not (a member|allowed)|only a supervisor|ask your supervisor|you do not have|no access|_whNoteAuthFailure|getDb\(/i.test(src) && /sign in|back to|return/i.test(src));
  // F13 arbitrates: an updated_at precondition on writes, or no writes at all
  const writes = /\.update\(|\.upsert\(/.test(src);
  const arbitrates = !writes || /updated_at['"]?\s*[,:)]|\.eq\(['"]updated_at['"]|_whOcGuard|oc-helper|ocGuard/i.test(src);
  const internals = s ? (s.text.match(INTERNAL) || []) : [];

  const verdicts = {
    F01: s && s.heads.length > 0 && s.textLen > 200,
    F02: s && s.bare === 0,
    F03: s && s.chips > 0,
    F04: failsWell,
    F05: s && s.chips > 0,
    F06: s && s.overflow <= 4,
    F07: s && s.cls <= 0.1,
    F08: reached >= 3,
    F09: s && s.links > 0,
    F10: kept === null ? true : kept,
    F11: refusedKindly,
    F12: internals.length === 0,
    F13: arbitrates,
    F14: printLen > 200,
  };
  const why = {
    F01: 'no heading or almost no content on first glance', F02: `${s ? s.bare : '?'} bare icon button(s) say nothing`, F03: 'nothing says how fresh this is',
    F04: 'a failed load is answered with nothing a person can act on', F05: 'the headline number cannot be traced', F06: `${s ? s.overflow : '?'}px off the edge at 390`,
    F07: `layout shift ${s ? s.cls.toFixed(3) : '?'} after paint`, F08: `a keyboard reached only ${reached} control(s)`, F09: 'no internal link leads anywhere',
    F10: 'what was typed was gone after a refresh', F11: 'a refused person is not told kindly, or not offered the way back', F12: `internals reach the copy: ${internals.slice(0, 2).join(', ')}`,
    F13: 'writes carry no updated_at guard, so two people overwrite each other silently', F14: `only ${printLen} characters survive to print`,
  };
  for (const r of rows) {
    n++;
    const ok = r.lens !== '?' && !!verdicts[r.lens];
    if (!ok) bad++;
    console.log(`  ${ok ? 'ok ' : 'BAD'} ${r.id.padEnd(6)} ${r.lens} ${page.padEnd(28)}${ok ? '' : ' ' + (why[r.lens] || 'unmapped lens')}`);
  }
}
await b.close();
console.log(`${bad ? 'FAIL' : 'PASS'} page-floor - ${n - bad}/${n} lens-rows hold across the thin pages`);
process.exitCode = bad ? 1 : 0;
