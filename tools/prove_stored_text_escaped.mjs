// prove_stored_text_escaped.mjs - SL sub-layer S4 (2026-10-15): "The platform must escape every piece of stored text
// this page renders, so data can never become markup."
//
// WHY A RUNTIME PROOF. The escaping gates read SOURCE: validate_dom_xss_fields flags a bare `${row.field}` in an HTML
// template for a list of known free-text columns, and the innerHTML audit asks that escHtml be in scope. Neither can
// see a field it was not told about, a value that reaches the DOM through a helper, or a page that renders a column
// the list never named. So this prover asks the page itself: every read the page makes from the database is answered
// with its stored TEXT carrying a hostile payload - an <img> whose onerror counts a hit - and the page must show that
// payload as text, never as an element and never as a running handler.
//
// Per page of the S4 roster, signed in as its cast through the product's own form (a public page as its visitor):
//   - every PostgREST response (/rest/v1/..., tables and rpc) is fetched for real and its free-text strings are
//     extended with PAYLOAD before the page sees them: a string with a space or longer than 20 characters that is not
//     an id, a timestamp, a number, a URL or an email (those are values the page computes with, not text it shows)
//   - VERDICT: no handler ran (window.__whXss), no payload element exists ([data-wh-xss], in the page and in its
//     same-origin frames), and the payload TEXT is visible at least once - a page that rendered none of the poisoned
//     text proves nothing, so that reading FAILS as "not exercised" rather than passing vacuously
//   - TEETH: logbook.html again, served a utils.js whose escHtml returns its input unchanged: the payload must then
//     run or become an element, or this prover cannot tell escaped text from raw markup and fails itself
//
//   node tools/prove_stored_text_escaped.mjs [--page a.html,b.html] [--json .tmp/s4_results.json] [--no-teeth]
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
import { execFileSync } from 'node:child_process';
import { SEEDER, stubModelCalls } from './prover_harness.mjs';
import { ALL_ROWS_DRAWN } from './lib/long_list_text.mjs';

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const OUT = arg('--json', '.tmp/s4_results.json');
const TEETH = !process.argv.includes('--no-teeth');
const TEETH_PAGE = arg('--teeth-page', 'logbook.html');
const PAYLOAD = ' <img src=x data-wh-xss="1" onerror="window.__whXss=(window.__whXss||0)+1">';
const MARK = '<img src=x data-wh-xss';
const IDENTITY_READ = /\/rest\/v1\/(v_worker_truth|v_hives_truth|hive_members|v_hive_members[a-z_]*)(\?|$)/;
const IDENTITY_PAGES = new Set(['index.html', 'hive.html']);
// a grant the page only TESTS (the founder gate) and never draws is passed through untouched
const GRANT_READ = /\/rest\/v1\/marketplace_platform_admins(\?|$)/;
const READER_NAME = { bryangarcia: 'Bryan Garcia', leandromarquez: 'Leandro Marquez' };

const reg = JSON.parse(readFileSync('trajectory_registry.json', 'utf8'));
const S4 = reg.trajectories.filter((t) => t.sl && t.sl.sublayer === 'S4' && t.status !== 'descoped');
const castOf = new Map(S4.map((t) => [t.sl.page, t.persona]));
const PAGES = arg('--page') ? arg('--page').split(',') : [...castOf.keys()];
const SUP = /supervisor|oversight|owner|engineer|manager/i;
const ACCOUNT = (persona) => persona === 'anon' ? { user: 'anon' } : (SUP.test(persona) ? { user: 'leandromarquez' } : { user: 'bryangarcia' });

const NOT_TEXT = [/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i, /^\d{4}-\d{2}-\d{2}([T ][\d:.]+)?(Z|[+-]\d{2}(:?\d{2})?)?$/,
  /^-?\d+(\.\d+)?$/, /^(https?:|data:|blob:|wss?:)/i, /^[^\s@]+@[^\s@]+\.[^\s@]+$/];
const isText = (s) => typeof s === 'string' && (s.includes(' ') || s.length > 20) && !NOT_TEXT.some((rx) => rx.test(s.trim()));
function poison(v, n) {
  // a token (an id, a key: no space) is poisoned too - an id drawn raw into a handler is how logbook was found - but only
  // FREE text (with a space) is text a page is expected to show; the vacuity check counts that
  if (typeof v === 'string') { if (isText(v)) { n.c++; if (v.includes(' ')) n.free = (n.free || 0) + 1; return v + PAYLOAD; } return v; }
  if (Array.isArray(v)) return v.map((x) => poison(x, n));
  if (v && typeof v === 'object') { const o = {}; for (const [k, x] of Object.entries(v)) o[k] = poison(x, n); return o; }
  return v;
}

async function context(neuterEscHtml) {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  await ctx.addInitScript(ALL_ROWS_DRAWN);
  await stubModelCalls(ctx);
  const seen = { fields: 0, responses: 0 };
  await ctx.route('**/rest/v1/client_errors*', (r) => r.request().method() === 'POST' ? r.fulfill({ status: 201, contentType: 'application/json', body: '[]' }) : r.continue());
  await ctx.route(/\/rest\/v1\/(?!client_errors)/, async (route) => {
    const req = route.request();
    const rpc = /\/rest\/v1\/rpc\//.test(req.url());
    // a page that saves what it just read would write the POISONED text back into the database: a table write during
    // this proof is answered here and never reaches it (the proof is about rendering, not about saving)
    if (!rpc && req.method() !== 'GET' && req.method() !== 'HEAD') { seen.writesHeld = (seen.writesHeld || 0) + 1; return route.fulfill({ status: 201, contentType: 'application/json', body: '[]' }); }
    if (req.method() !== 'GET' && !(rpc && req.method() === 'POST')) return route.continue();
    let res;
    try { res = await route.fetch(); } catch (e) { return route.continue(); }
    const ct = res.headers()['content-type'] || '';
    if (!/json/.test(ct) || !res.ok()) return route.fulfill({ response: res });
    // ★THE READER'S OWN NAME AND HIVE are stored text too, but every page's start-up keys on them (who is signed in,
    // which hive, whether the founder gate opens): poisoned everywhere, they stopped the founder pages before their
    // content drew (75-177 characters rendered), proving nothing. They are poisoned on the pages that DRAW them - the
    // landing page's greeting and the hive board - and passed through clean elsewhere so each page's own data renders.
    if (GRANT_READ.test(new URL(req.url()).pathname)) return route.fulfill({ response: res });
    const identity = IDENTITY_READ.test(new URL(req.url()).pathname) && !seen.poisonIdentity;
    let body; try { body = JSON.parse(await res.text()); } catch (e) { return route.fulfill({ response: res }); }
    // an identity read keeps the READER's own row clean (start-up keys on it) and poisons every other row - a teammate's
    // name on the roster is stored text someone else wrote, drawn on the standings, the board and every 'by' line
    const own = (row) => row && typeof row === 'object' && (row.worker_name === seen.readerName || (seen.readerUid && row.auth_uid === seen.readerUid));
    const n = { c: 0 };
    const out = !identity ? poison(body, n) : (Array.isArray(body) ? body.map((row) => own(row) ? row : poison(row, n)) : (own(body) ? body : body));
    // free text from the roster (teammates' names) is poisoned and counts when drawn, but most pages never draw the roster:
    // only free text from the page's OWN reads is text the page is expected to show
    seen.fields += n.c; seen.free = (seen.free || 0) + (identity ? 0 : (n.free || 0)); seen.responses += 1;
    if (n.c) (seen.byPath = seen.byPath || []).push(`${new URL(req.url()).pathname.replace(/^.*\/rest\/v1\//, '')} ${n.c}`);
    return route.fulfill({ response: res, body: JSON.stringify(out), headers: { ...res.headers(), 'content-type': 'application/json; charset=utf-8' } });
  });
  if (neuterEscHtml) {
    const utils = await (await fetch(`${SEEDER}/workhive/utils.js`)).text();
    const neutered = utils.replace(/function escHtml\(str\) \{/, 'function escHtml(str) { return String(str || \'\');');
    if (neutered === utils) throw new Error('teeth: could not neuter escHtml in utils.js - its definition changed');
    await ctx.route('**/workhive/utils.js*', (r) => r.fulfill({ status: 200, contentType: 'application/javascript', body: neutered }));
  }
  return { browser, ctx, seen };
}

async function signIn(ctx, user) {
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/index.html?signin=1`, { waitUntil: 'load', timeout: 45000 });
  await p.fill('#si-username', user); await p.fill('#si-password', 'test1234'); await p.click('#si-btn');
  const ok = await p.waitForFunction(() => !!localStorage.getItem('wh_active_hive_id'), null, { timeout: 25000 }).then(() => true).catch(() => false);
  await p.close();
  return ok;
}

// a page reached by a deep link is opened the way a person arrives at it: the seller profile from a listing's seller
// (the seller with the most published listings, read from the database, never a name typed here)
const sql = (q) => { try { return execFileSync('docker', ['exec', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-tAc', q], { encoding: 'utf8' }).trim(); } catch (e) { return ''; } };
const REACH = {
  'marketplace-seller-profile.html': () => {
    const s = sql("select seller_name from marketplace_listings where status in ('published','active','live') and seller_name is not null group by 1 order by count(*) desc limit 1");
    return s ? '?worker=' + encodeURIComponent(s) : '';
  },
};

// integrations draws its live-sync configs only in the Live Sync tab, and its API keys only in the API tab
const ACT = { 'integrations.html': ['#tab-sync', '#tab-api'] };

async function visit(ctx, seen, page) {
  seen.poisonIdentity = IDENTITY_PAGES.has(page);
  const before = { ...seen }; const pathsBefore = (seen.byPath || []).length;
  const p = await ctx.newPage();
  let loadError = null;
  const query = REACH[page] ? REACH[page]() : '';
  await p.goto(`${SEEDER}/workhive/${page}${query}`, { waitUntil: 'load', timeout: 60000 }).catch((e) => { loadError = String(e.message).slice(0, 120); });
  await p.waitForLoadState('networkidle', { timeout: 12000 }).catch(() => {});
  await p.waitForTimeout(3500);
  // a page whose stored text is drawn only when a section opens: press what a person presses to read it
  for (const sel of (ACT[page] || [])) { await p.click(sel, { timeout: 5000 }).catch(() => {}); await p.waitForTimeout(2500); }
  const st = await p.evaluate((MARK) => {
    const docs = [document, ...[...document.querySelectorAll('iframe')].map((f) => { try { return f.contentDocument; } catch (e) { return null; } }).filter(Boolean)];
    const elements = docs.reduce((n, d) => n + d.querySelectorAll('[data-wh-xss]').length, 0);
    const text = docs.map((d) => (d.body && d.body.innerText) || '').join('\n');
    // A value that became TEXT anywhere in the document counts - a collapsed panel or a closed sheet holds rendered text
    // that innerText (the visible text) skips; whether it was escaped is decided when it was rendered, not when shown.
    const all = docs.map((d) => (d.body && d.body.textContent) || '').join('\n');
    const shown = all.split(MARK).length - 1;
    const visible = text.split(MARK).length - 1;
    // what a person reads: the first poisoned line, as text (visible if there is one)
    const line = ((text.includes(MARK) ? text : all).split('\n').find((l) => l.includes(MARK)) || '').trim().slice(0, 140);
    // WHERE a value became markup: the element it landed in, so the receipt names the render that did not escape
    const where = docs.flatMap((d) => [...d.querySelectorAll('[data-wh-xss]')]).slice(0, 6).map((el) => {
      const p = el.parentElement; const sig = (n) => n ? `${n.tagName.toLowerCase()}${n.id ? '#' + n.id : ''}${n.className && typeof n.className === 'string' ? '.' + n.className.trim().split(/\s+/).slice(0, 2).join('.') : ''}` : '?';
      return `${sig(p && p.parentElement)} > ${sig(p)}: ${(p ? p.outerHTML : '').replace(/\s+/g, ' ').slice(0, 260)}`;
    });
    return { ran: window.__whXss || 0, elements, shown, visible, line, where, chars: text.length, url: location.pathname.split('/').slice(-2).join('/') };
  }, MARK).catch((e) => ({ ran: 0, elements: 0, shown: 0, line: '', chars: 0, url: '?', err: String(e.message).slice(0, 100) }));
  await p.close();
  const fields = seen.fields - before.fields, responses = seen.responses - before.responses, free = (seen.free || 0) - (before.free || 0);
  const problems = [];
  if (loadError) problems.push(`load: ${loadError}`);
  if (st.ran) problems.push(`a stored value RAN as script ${st.ran} time(s) (its onerror handler fired)`);
  if (st.elements) problems.push(`${st.elements} stored value(s) BECAME an element ([data-wh-xss] in the DOM)`);
  // a page whose reads carry NO free text renders no stored text, so there is nothing that could become markup - that is
  // its reading, recorded as such; a page that received poisoned text and rendered none of it proves nothing and fails
  const noText = !free;   // no FREE text arrived (tokens may have): nothing the page is expected to show as text
  if (!st.ran && !st.elements && !st.shown && !noText) problems.push(`not exercised: ${fields} poisoned field(s) in ${responses} response(s), none rendered - no reading of S4 is possible from this load`);
  const poisonedReads = (seen.byPath || []).slice(pathsBefore).slice(0, 8);
  return { page, ...st, fields, free, responses, noText, poisonedReads, problems, ok: !problems.length };
}

const byUser = new Map();
for (const page of PAGES) { const u = ACCOUNT(castOf.get(page) || 'anon').user; (byUser.get(u) || byUser.set(u, []).get(u)).push(page); }
const results = [];
for (const [user, pages] of byUser) {
  const { browser, ctx, seen } = await context(false);
  seen.readerName = READER_NAME[user] || null;
  const ok = user === 'anon' ? true : await signIn(ctx, user);
  for (const page of pages) {
    const r = ok ? await visit(ctx, seen, page) : { page, problems: [`sign-in as ${user} failed`], ok: false };
    results.push({ engine: 'chromium', condition: 'poisoned', cast: castOf.get(page), account: user, ...r });
    console.log(`  ${r.ok ? 'ok  ' : 'FAIL'} ${page.padEnd(34)} ${String(r.fields ?? '-').padStart(4)} poisoned field(s), ${String(r.shown ?? '-').padStart(3)} shown as text (${r.visible ?? '-'} visible), ran ${r.ran ?? '-'}, elements ${r.elements ?? '-'}`
      + (r.ok ? '' : `\n         ${r.problems.join('\n         ')}`));
  }
  await browser.close();
}

let teeth = null;
if (TEETH) {
  const { browser, ctx, seen } = await context(true);
  const ok = await signIn(ctx, ACCOUNT(castOf.get(TEETH_PAGE) || 'worker').user);
  const r = ok ? await visit(ctx, seen, TEETH_PAGE) : { problems: ['teeth sign-in failed'] };
  await browser.close();
  teeth = { page: TEETH_PAGE, ran: r.ran || 0, elements: r.elements || 0, bit: !!(r.ran || r.elements) };
  console.log(`\n  teeth - ${TEETH_PAGE} with escHtml returning its input unchanged: ${teeth.bit ? 'the payload RAN / became an element, as it must' : 'DID NOT FAIL'} (ran ${teeth.ran}, elements ${teeth.elements})`);
}
mkdirSync(dirname(OUT), { recursive: true });
const failed = results.filter((r) => !r.ok).length + (teeth && !teeth.bit ? 1 : 0);
writeFileSync(OUT, JSON.stringify({ generated: new Date().toISOString(), sublayer: 'S4', payload: PAYLOAD.trim(), pages: results.length, failed, teeth, results }, null, 1));
console.log(`\n${failed ? 'FAIL' : 'PASS'} stored-text-escaped - ${results.length - results.filter((r) => !r.ok).length}/${results.length} page(s) show every poisoned stored value as text${teeth ? `; teeth ${teeth.bit ? 'bit' : 'DID NOT BITE'}` : ''} -> ${OUT}`);
process.exit(failed ? 1 : 0);
