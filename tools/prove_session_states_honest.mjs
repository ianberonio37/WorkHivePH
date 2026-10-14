// prove_session_states_honest.mjs - SL AU1 and BRH-M (2026-10-14): in every session state, a page is honest about who
// the person is.
//
// WHY. Ian, 2026-10-14: *"a certain user like 'working as (name of a user).. not signed in..' what is that slop? you are
// working, but not signed in? what a really slop.."* The landing page's expired-session banner called a person by name
// as if they were working while it said they were not signed in. The same session state is AU1's question for every
// page (an expired session is refreshed or ended honestly, never acted on), so one prover answers both: AU1 (29 rows) and
// BRH-M (36 rows: every production page and shared component that reads the device-remembered display name).
//
// Per page, at 390 AND 1280, in a fresh browser context each, signed in as the page's cast through the product's own
// client (prover_harness.signIn):
//   honest     the session as it is: the page renders (chars >= floor) and offers a signed-in person NO "Sign in" door
//   dead       the access token expired AND its refresh token refused ('expired-by-the-walk'): the page walls (sign-in
//              redirect or dialog) or says the session ended, writes nothing, and calls nobody by name as if they were
//              working - the remembered name may appear only in a sentence about signing in ("Sign in to continue as")
//   out        no session at all, the remembered name left on the device (wh_last_worker): no identity claim either
// An IDENTITY CLAIM is the remembered name in the person's own slot (#nav-worker, [data-wh-worker-name], a greeting
// element) or after an identity verb (working as, signed in as, logged in as, welcome back, hi, hello, good morning,
// kumusta) - not a name in a data row, which belongs to the content.
// TEETH: index.html from WH_PREFIX_BASE (default e8e02917, before the banner fix) must produce an identity claim in the
// dead or out state; if it does not, the prover cannot see the defect it exists for and FAILS itself.
//
//   node tools/prove_session_states_honest.mjs [--page index.html,logbook.html] [--settle 7000] [--no-teeth]
//        [--json .tmp/session_states_results.json]
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { dirname } from 'node:path';
import { SEEDER, HIVE, stubModelCalls, signIn, PAGE_QUERY } from './prover_harness.mjs';

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const OUT = arg('--json', '.tmp/session_states_results.json');
const TEETH = !process.argv.includes('--no-teeth');
const BASE = process.env.WH_PREFIX_BASE || 'e8e02917';
const SETTLE = Number(arg('--settle', '7000'));
const CHARS_FLOOR = 300;
const VPS = [[390, 844], [1280, 800]];

const reg = JSON.parse(readFileSync('trajectory_registry.json', 'utf8'));
const live = (t) => t.status !== 'descoped';
const mRows = reg.trajectories.filter((t) => t.brh && t.brh.cls === 'M' && live(t));
const au1Rows = reg.trajectories.filter((t) => t.sl && t.sl.sublayer === 'AU1' && live(t));
// ...and the two founder observability pages, which run the same admin gate as founder-console and showed an admin
// whose session had lapsed "no access" until it learned the AU1 rule (2026-10-14) - walked as platform staff
const ALSO = { 'llm-observability.html': 'oversight', 'agentic-rag-observability.html': 'oversight' };
const roster = [...new Set([...au1Rows.map((t) => t.sl.page), ...mRows.map((t) => t.brh.page), ...Object.keys(ALSO)])].sort();
const PAGES = arg('--page') ? arg('--page').split(',') : roster;
const personaOf = (page) => ALSO[page] || ((au1Rows.find((t) => t.sl.page === page) || mRows.find((t) => t.brh.page === page) || {}).persona) || 'worker';
const ACCOUNTS = {
  bryan: { name: 'Bryan Garcia', first: 'Bryan', role: 'worker', email: 'bryangarcia@auth.workhiveph.com', password: 'test1234' },
  leandro: { name: 'Leandro Marquez', first: 'Leandro', role: 'supervisor', email: 'leandromarquez@auth.workhiveph.com', password: 'test1234' },
  jun: { name: 'Jun Salvador', first: 'Jun', role: '', email: 'junvanowner@auth.workhiveph.com', password: 'test1234', hive: '' },
};
const accountFor = (persona) => {
  if (persona === 'anon') return null;
  if (persona === 'solo-owner') return ACCOUNTS.jun;
  if (/supervisor|oversight|machine-client|manager|engineer/i.test(persona)) return ACCOUNTS.leandro;
  return ACCOUNTS.bryan;
};

const READ = ([name, first]) => {
  const vis = (el) => { if (!el) return false; if (typeof el.checkVisibility === 'function' && !el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) return false; const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const text = document.body ? (document.body.innerText || '') : '';
  const sentences = text.split(/(?<=[.!?])\s+|\n+/).map((s) => s.trim()).filter(Boolean);
  const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const who = new RegExp('\\b(' + esc(name) + '|' + esc(first) + ')\\b', 'i');
  const verb = /\b(working as|signed in as|logged in as|welcome back|good (morning|afternoon|evening)|hi|hello|kumusta)\b/i;
  const aboutSignIn = /sign in|log in|session|continue as|sign-in|signed out/i;
  const claims = [];
  for (const s of sentences) if (who.test(s) && verb.test(s) && !aboutSignIn.test(s)) claims.push(s.slice(0, 120));
  // the person's own slots: the nav name, a greeting, and the header chip index.html makes out of its Sign In button
  for (const el of document.querySelectorAll('#nav-worker, [data-wh-worker-name], [id*="greeting"], [id*="welcome-name"], .signin-btn, #user-menu-name, #user-menu-name-mobile, #chat-worker-name')) {
    if (vis(el) && who.test(el.textContent || '')) claims.push('[' + (el.id || 'data-wh-worker-name') + '] ' + (el.textContent || '').trim().slice(0, 60));
  }
  const doors = [...document.querySelectorAll('a, button')].filter((el) => vis(el) && /^\s*(sign in|log in)\b/i.test(el.innerText || '')).map((el) => (el.innerText || '').trim().slice(0, 40));
  const dlg = [...document.querySelectorAll('[role=dialog], dialog, #signin-modal')].some((d) => vis(d) && /sign in/i.test(d.innerText || ''));
  const notice = (text.match(/[^.\n]*(session (has )?(ended|expired)|sign in again|signed out|not signed in|your session)[^.\n]*/i) || [''])[0].trim().slice(0, 100);
  return { chars: text.length, url: location.pathname.split('/').pop() + location.search.slice(0, 40), wall: /signin=1/.test(location.search) || dlg, notice, claims, doors };
};

// ONE browser for the run, and ONE sign-in per account: each reading still gets a FRESH context, started from that
// account's saved storage state (a full browser launch + a sign-in per reading made a 192-reading run take over an hour)
const BROWSER = await chromium.launch();
const STATES = new Map();
async function stateFor(acct) {
  if (!acct) return undefined;
  if (STATES.has(acct.email)) return STATES.get(acct.email);
  const ctx = await BROWSER.newContext({ serviceWorkers: 'block' });
  const ok = await signIn(ctx, { ...acct, hive: acct.hive === '' ? undefined : HIVE });
  let st = null;
  if (ok) {
    const p = await ctx.newPage();
    await p.goto(`${SEEDER}/workhive/index.html`, { waitUntil: 'domcontentloaded', timeout: 45000 }).catch(() => {});
    // the harness seats its default hive on every sign-in; a hive-less owner must not carry one
    if (acct === ACCOUNTS.jun) await p.evaluate(() => { ['wh_active_hive_id', 'wh_hive_role', 'wh_hive_name', 'wh_hives'].forEach((k) => localStorage.removeItem(k)); });
    st = await ctx.storageState();
  }
  await ctx.close();
  STATES.set(acct.email, st);
  return st;
}

async function fresh(prefixIndex, storageState) {
  const browser = BROWSER;
  const ctx = await browser.newContext({ serviceWorkers: 'block', ...(storageState ? { storageState } : {}) });
  await stubModelCalls(ctx);
  await ctx.route('**/functions/v1/**', (r) => r.request().method() === 'OPTIONS' ? r.fallback()
    : r.fallback({ headers: { ...r.request().headers(), 'x-wh-walk-no-model': '1' } }));
  if (prefixIndex) {
    const old = execFileSync('git', ['show', `${prefixIndex}:index.html`], { encoding: 'utf8', maxBuffer: 64 << 20 });
    await ctx.route(/\/workhive\/index\.html(\?.*)?$/, (r) => r.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: old }));
  }
  const writes = [];
  ctx.on('request', (q) => { const m = q.method(), u = q.url(); if (!['GET', 'HEAD', 'OPTIONS'].includes(m) && /\/rest\/v1\//.test(u) && !/analytics_events|client_errors|page_views|\/rpc\//.test(u)) writes.push(m + ' ' + u.split('/rest/v1/')[1].slice(0, 50)); });
  return { browser, ctx, writes };
}

async function visit(page, persona, state, [w, h], prefixIndex) {
  const acct = accountFor(persona);
  const name = (acct || ACCOUNTS.bryan).name, first = (acct || ACCOUNTS.bryan).first;
  const st = (acct && state !== 'out') ? await stateFor(acct) : undefined;
  if (acct && state !== 'out' && !st) {
    return { page, persona, state, vp: w, ok: false, problems: ['SIGN-IN FAILED - refusing to read a signed-out page as a signed-in one'] };
  }
  const { ctx, writes } = await fresh(prefixIndex, st);
  let r;
  try {
    const p = await ctx.newPage();
    await p.setViewportSize({ width: w, height: h });
    await p.goto(`${SEEDER}/workhive/index.html`, { waitUntil: 'domcontentloaded', timeout: 45000 }).catch(() => {});
    if (state === 'dead') {
      await p.evaluate(() => { const k = Object.keys(localStorage).find((x) => /^sb-.*-auth-token$/.test(x)); if (!k) return; const v = JSON.parse(localStorage.getItem(k)); const s = v.currentSession || v; s.expires_at = 1; s.expires_in = -1; s.refresh_token = 'expired-by-the-walk'; localStorage.setItem(k, JSON.stringify(v)); });
    } else if (state === 'out') {
      await p.evaluate((nm) => { localStorage.clear(); sessionStorage.clear(); localStorage.setItem('wh_last_worker', nm); }, name);
    } else if (!acct) {
      await p.evaluate(() => { localStorage.clear(); sessionStorage.clear(); });
    }
    writes.length = 0;
    // a page that needs its subject in the URL gets the harness's own query (marketplace-seller-profile: ?worker=...)
    const q = PAGE_QUERY[page] ? PAGE_QUERY[page] + '&' : '?';
    await p.goto(`${SEEDER}/workhive/${page}${q}t=${Date.now()}`, { waitUntil: 'load', timeout: 60000 }).catch(() => {});
    await p.waitForTimeout(SETTLE);
    // a slow host can still be mid-load after the settle (platform-actions read 104 characters at 390 and 4,455 at
    // 1280 on a host with 0.2 GB free): wait until the page's text stops changing, up to 6 s more
    for (let i = 0, last = -1; i < 8; i++) {
      const n = await p.evaluate(() => (document.body ? document.body.innerText.length : 0)).catch(() => 0);
      if (n === last && n >= CHARS_FLOOR) break;
      last = n; await p.waitForTimeout(750);
    }
    const d = await p.evaluate(READ, [name, first]);
    const problems = [];
    if (state === 'honest') {
      if (acct && d.doors.length) problems.push(`a signed-in person is offered "${d.doors.join('", "')}"`);
      if (acct && d.wall) problems.push('a signed-in person was walled');
      if (d.chars < CHARS_FLOOR && !d.wall) problems.push(`rendered ${d.chars} characters`);
    } else {
      if (d.claims.length) problems.push(`identity claimed while ${state === 'dead' ? 'the session is dead' : 'signed out'}: ${d.claims.join(' | ')}`);
      if (writes.length) problems.push(`wrote with no live session: ${writes.slice(0, 3).join(', ')}`);
      // a dead session ends honestly: the sign-in wall, a sentence that says so, or - on a page anyone may read - the
      // page simply presenting itself signed out (it offers Sign in)
      if (state === 'dead' && acct && !d.wall && !d.notice && !d.doors.length && personaOf(page) !== 'anon') problems.push('a dead session is neither walled nor named');
    }
    r = { page, persona, state, vp: w, ok: problems.length === 0, problems, ...d, writes: writes.length };
  } finally { await ctx.close(); }
  return r;
}

const results = [];
for (const page of PAGES) {
  const persona = personaOf(page);
  for (const vp of VPS) {
    for (const state of (accountFor(persona) ? ['honest', 'dead', 'out'] : ['honest', 'out'])) {
      const r = await visit(page, persona, state, vp, null);
      results.push(r);
      console.log(`${r.ok ? 'ok  ' : 'FAIL'} ${page.padEnd(32)} ${String(vp[0]).padEnd(5)} ${state.padEnd(7)} ${persona.padEnd(17)} chars=${r.chars ?? '-'} ${r.wall ? 'walled ' : ''}${r.notice ? '"' + r.notice.slice(0, 50) + '" ' : ''}${r.problems.join(' ; ').slice(0, 160)}`);
    }
  }
}

let teeth = null;
if (TEETH) {
  const t = [];
  for (const state of ['dead', 'out']) t.push(await visit('index.html', 'worker', state, VPS[0], BASE));
  const bit = t.some((r) => (r.problems || []).some((p) => p.startsWith('identity claimed')));
  teeth = { base: BASE, bit, readings: t.map((r) => ({ state: r.state, problems: r.problems, claims: r.claims })) };
  console.log(`\n  teeth - index.html at ${BASE}: ${bit ? 'FAILS as it must' : 'DID NOT FAIL'} - ${t.map((r) => r.state + ': ' + (r.claims || []).join(' | ')).join(' ; ').slice(0, 300)}`);
}

await BROWSER.close();
mkdirSync(dirname(OUT), { recursive: true });
writeFileSync(OUT, JSON.stringify({ _doc: 'prove_session_states_honest.mjs - SL AU1 + BRH-M readings, one per (page, viewport, state)',
  generated: new Date().toISOString(), base: BASE, results, teeth }, null, 1));
const bad = results.filter((r) => !r.ok);
console.log(`\n${results.length} reading(s), ${bad.length} failing; written to ${OUT}`);
if (TEETH && !teeth.bit) { console.log('FAIL session-states-honest - NO TEETH: the pre-fix landing banner did not fail'); process.exit(1); }
if (bad.length) { console.log(`FAIL session-states-honest - ${bad.length} reading(s)`); process.exit(1); }
console.log('PASS session-states-honest - every page, at 390 and 1280, is honest about who the person is with the session '
  + 'honest, dead and absent; the pre-fix landing banner is not');
