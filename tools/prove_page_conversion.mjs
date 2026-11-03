// prove_page_conversion.mjs - CV2 (auth-wall doors) and CV3 (funnel completion), measured PER PAGE.
// ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────
// WHY (2026-11-04, CX-UX). The rubric's CV class asks two questions of every page a signed-out visitor can land on,
// and both were answered only by JOURNEYS: CV2 by prove_journey.mjs's wall-door oracles (J1-J3, run over the 22 product
// pages) and journeys LA8/LA10; CV3 by LA11 (cold anon on index.html -> the real signup -> worker_profiles row) and
// LA12 (the same from ONE learn guide). Each of those records speaks for the page it walked. None walked about,
// feedback, privacy-policy, terms-of-service, the learn hub or the 19-guide chrome variant - so "is CV graded on THIS
// page" had no answer there, and reading LA11's verdict for them would have credited a page with a walk that never
// opened it. This prover walks each page itself, with the same steps those journeys use:
//
//   CV2  every auth wall a signed-out visitor can meet FROM this page offers BOTH clickable doors (sign in AND create
//        an account) carrying ?return= naming where they were going - J1/J3's door rule and LA8's reciprocity check.
//        The walls are found, not assumed: every link on the page to an app page (a root *.html other than the
//        landing) is followed in a signed-out context, and an inline gate or a redirect onto the landing's auth
//        modal is a wall. An in-page refusal (whAuthRequiredToast / whSignInWall named in the page's markup) is
//        clicked and read the same way. pct = doored walls / walls; NO wall reachable = N/A, with the count of links
//        followed, because a page with no wall has no door to grade.
//   CV3  the conversion path from THIS page works as one journey - LA11/LA12's steps, entered through the page's own
//        sign-up door: (1) the page serves a cold anon visitor, (2) it offers a sign-up door (not a waitlist),
//        (3) clicking THAT door opens the real signup panel, (4) the account is created through the modal and the
//        visitor reaches signed-in value, (5) the worker_profiles row exists (psql), (6) the door's source is
//        attributed (sessionStorage wh_signup_source - what index.html sends to GA4 as signup_completed.source).
//        pct = steps passed / 6; a step a failed step blocks counts as failed, named "not reached". The account is
//        deleted (profile, then auth user) and the context signed out, as LA11 does.
//
// One phone viewport (390x780): search traffic is mobile, the doors are the same at 1280 (CV1 clicks both widths).
// Local only: the seeder at :5000, Supabase at :54321, psql through docker - never production.
//
// USAGE
//   node tools/prove_page_conversion.mjs                      the default roster
//   node tools/prove_page_conversion.mjs --page about/index.html,learn/index.html
//   node tools/prove_page_conversion.mjs --check              the gate: walk the roster, FAIL on a wall without both
//                                                             doors, or a page whose CV3 fell below its floor
//   node tools/prove_page_conversion.mjs --accept             re-baseline the CV3 floors (page_conversion_baseline.json)
//   node tools/prove_page_conversion.mjs --self-test          the pure verdict logic, no browser
// OUTPUT  page_conversion_cv.json (tracked): {pages: {<page>: {CV2: {verdict,pct,note}, CV3: {...}, walls, funnel}}}
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { execSync } from 'child_process';

const SEEDER = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const OUT = 'page_conversion_cv.json';
const BASE = 'page_conversion_baseline.json';
const DB_CONTAINER = process.env.WH_DB_CONTAINER || 'supabase_db_workhive';
const VIEW = { width: 390, height: 780 };
const MAX_WALL_LINKS = 20;

// The pages a signed-out visitor converts FROM that are not template instances of a page already walked, plus one
// instance of each template variant: the four public-root pages, the learn hub, a guide of each chrome variant, and
// a calculator. --page adds or narrows.
const ROSTER = [
  'about/index.html', 'feedback/index.html', 'privacy-policy/index.html', 'terms-of-service/index.html',
  'learn/index.html', 'learn/philippine-plants-now-pay-the-highest-power-rates/index.html',
  'learn/what-is-workhive-complete-platform-guide/index.html', 'tools/ahu-sizing-calculator/index.html',
];

// ── the verdicts: pure, so the self-test can hold them without a browser ─────────────────────────────────────────
const CV3_STEPS = ['arrival', 'door', 'door-opens-signup', 'account', 'db-row', 'attribution'];

/** One followed link or one in-page refusal -> {wall, doored, why}. `seen` is what the browser read after arriving. */
function classifyLanding(seen) {
  const { requested, landedPath, landedQuery, inlineGate, modalOpen, signinDoor, signupDoor, returnTo } = seen;
  const redirectedToLanding = landedPath !== requested && /(^|\/)index\.html$/.test(landedPath);
  const wall = redirectedToLanding || !!inlineGate || !!seen.toast;
  if (!wall) return { wall: false, doored: null, why: `served ${requested} to a signed-out visitor` };
  const where = seen.toast ? 'the refusal toast' : inlineGate ? `the inline gate on ${requested}` : `the wall at ${landedPath}${landedQuery}`;
  const lacks = [];
  if (!signinDoor) lacks.push('a sign-in door');
  if (!signupDoor) lacks.push('a create-account door');
  if (redirectedToLanding && !/[?&]sign(in|up)=1/.test(landedQuery || '')) lacks.push('?signin=1/?signup=1 (a bare landing loses the intent)');
  if (redirectedToLanding && !modalOpen) lacks.push('the auth modal open');
  const want = requested.replace(/^.*\//, '');
  if (!returnTo || returnTo.replace(/^.*\//, '').split(/[?#]/)[0] !== want) lacks.push(`?return= naming ${want} (got ${returnTo || 'none'})`);
  return lacks.length
    ? { wall: true, doored: false, why: `WALL WITHOUT A DOOR - ${where} lacks ${lacks.join(', ')}` }
    : { wall: true, doored: true, why: `${where}: both doors, return=${want}` };
}

function cv2Of(followed, walls) {
  if (!walls.length) {
    return { verdict: 'N/A', pct: null,
      note: `no auth wall reachable from this page signed out - ${followed} link(s) to app pages followed, none walled, and no in-page sign-in refusal in its markup` };
  }
  const ok = walls.filter((w) => w.doored).length;
  const bad = walls.filter((w) => !w.doored).map((w) => `${w.from}: ${w.why}`);
  return { verdict: 'MEASURED', pct: Math.round((100 * ok) / walls.length),
    note: `${ok}/${walls.length} wall(s) met from this page offer both doors with ?return=` + (bad.length ? ' - ' + bad.slice(0, 3).join('; ') : '') };
}

function cv3Of(steps) {
  // a step blocked by an earlier failure is failed, named "not reached" - the journey did not get there
  let blocked = null;
  const out = {};
  for (const s of CV3_STEPS) {
    const r = steps[s] || { ok: false, why: 'not measured' };
    if (blocked && s !== 'arrival') out[s] = { ok: false, why: `not reached (${blocked} failed)` };
    else out[s] = r;
    if (!out[s].ok && !blocked && s !== 'attribution') blocked = s;
  }
  const ok = CV3_STEPS.filter((s) => out[s].ok).length;
  const bad = CV3_STEPS.filter((s) => !out[s].ok).map((s) => `${s}: ${out[s].why}`);
  return { verdict: 'MEASURED', pct: Math.round((100 * ok) / CV3_STEPS.length), steps: out,
    note: `${ok}/${CV3_STEPS.length} funnel steps from this page's own sign-up door` + (bad.length ? ' - ' + bad.join('; ') : '') };
}

function selfTest() {
  const fails = [];
  const base = { requested: 'hive.html', landedPath: '/workhive/index.html', landedQuery: '?signin=1&return=hive.html',
    modalOpen: true, signinDoor: true, signupDoor: true, returnTo: 'hive.html' };
  const good = classifyLanding(base);
  if (!good.wall || !good.doored) fails.push(`a redirect onto the open modal with both doors and return= is a doored wall: ${JSON.stringify(good)}`);
  const served = classifyLanding({ ...base, landedPath: '/workhive/hive.html' , requested: '/workhive/hive.html' });
  if (served.wall) fails.push('a page served where it was asked for is no wall');
  const bare = classifyLanding({ ...base, landedQuery: '', modalOpen: false });
  if (!bare.wall || bare.doored || !/bare landing/.test(bare.why)) fails.push(`a bare landing is a wall WITHOUT a door: ${JSON.stringify(bare)}`);
  const oneDoor = classifyLanding({ ...base, signupDoor: false });
  if (oneDoor.doored || !/create-account door/.test(oneDoor.why)) fails.push('a wall with sign-in only is not doored');
  const noReturn = classifyLanding({ ...base, returnTo: null });
  if (noReturn.doored || !/return=/.test(noReturn.why)) fails.push('a wall that drops the destination is not doored');
  const wrongReturn = classifyLanding({ ...base, returnTo: 'logbook.html' });
  if (wrongReturn.doored) fails.push('a return= naming another page is not the visitor’s intent');
  const toast = classifyLanding({ requested: 'about/index.html', landedPath: '/workhive/about/index.html', toast: true,
    signinDoor: true, signupDoor: false, returnTo: 'about/index.html' });
  if (!toast.wall || toast.doored) fails.push('a refusal toast with only one door is a wall without a door');
  // CV2 arithmetic and its N/A
  const na = cv2Of(7, []);
  if (na.verdict !== 'N/A' || !/7 link/.test(na.note)) fails.push(`no wall reachable is N/A with the links followed: ${JSON.stringify(na)}`);
  const half = cv2Of(2, [{ from: 'a', doored: true }, { from: 'b', doored: false, why: 'x' }]);
  if (half.verdict !== 'MEASURED' || half.pct !== 50) fails.push(`1 of 2 doored walls is 50: ${JSON.stringify(half)}`);
  // CV3: all six, the attribution gap alone, and a blocked journey
  const all = Object.fromEntries(CV3_STEPS.map((s) => [s, { ok: true }]));
  if (cv3Of(all).pct !== 100) fails.push('six steps passed is 100');
  const unattributed = cv3Of({ ...all, attribution: { ok: false, why: 'no source' } });
  if (unattributed.pct !== 83 || !/attribution: no source/.test(unattributed.note)) fails.push(`an unattributed signup is 5/6: ${JSON.stringify(unattributed)}`);
  const noDoor = cv3Of({ arrival: { ok: true }, door: { ok: false, why: 'no sign-up door' } });
  if (noDoor.pct !== 17 || !/account: not reached \(door failed\)/.test(noDoor.note)) fails.push(`no door blocks every later step: ${JSON.stringify(noDoor)}`);
  console.log(fails.length ? 'FAIL prove_page_conversion self-test - ' + fails.join('; ')
    : 'self-test OK: a doored wall, a served page, a bare landing, a one-door wall, a lost or wrong return=, a one-door toast; CV2 N/A only with no wall reachable and 50 on one of two; CV3 100 / 83 unattributed / 17 with no door, later steps not reached');
  return fails.length ? 1 : 0;
}

// ── the browser half ─────────────────────────────────────────────────────────────────────────────────────────────
function adminQuery(sql) {
  try { return execSync(`docker exec ${DB_CONTAINER} psql -U postgres -d postgres -t -A -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim(); }
  catch (e) { return { __err: String(e.message || e).slice(0, 140) }; }
}

async function newAnon(browser) {
  const ctx = await browser.newContext({ viewport: VIEW, serviceWorkers: 'block', timezoneId: 'Asia/Manila' });
  return ctx;
}

const readAuthState = () => {
  const vis = (el) => !!el && el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden';
  const modal = document.getElementById('signin-modal');
  const modalOpen = !!modal && !modal.classList.contains('hidden') && vis(modal);
  const inPanel = (id, sel) => { const p = document.getElementById(id); return !!(p && vis(p) && p.querySelector(sel)); };
  // a door is a CLICKABLE control: the panel shown is one door, the reciprocity button to the other panel is the second
  const signinShown = vis(document.getElementById('panel-signin'));
  const signupShown = vis(document.getElementById('panel-signup'));
  const signinDoor = signinShown || inPanel('panel-signup', "button[data-wh-authtab='signin']");
  const signupDoor = signupShown || inPanel('panel-signin', "button[data-wh-authtab='signup']");
  let returnTo = null;
  try { returnTo = new URLSearchParams(location.search).get('return') || sessionStorage.getItem('wh_return_to'); } catch (_) { /* private mode */ }
  return { modalOpen, signinDoor: modalOpen && signinDoor, signupDoor: modalOpen && signupDoor, returnTo, path: location.pathname, query: location.search };
};

const readInlineGate = () => {
  const vis = (el) => !!el && el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
  const g = [...document.querySelectorAll('#gate-not-supervisor, #supervisor-gate, #hive-gate, .hive-gate, .gate-card, [data-wh-auth-gate]')].find(vis);
  const founder = [...document.querySelectorAll('h1')].some((h) => /founder access only/i.test(h.textContent || ''));
  if (!g && !founder) return null;
  const scope = g || document.body;
  const hrefs = [...scope.querySelectorAll('a[href]')].map((a) => a.getAttribute('href') || '');
  const ret = (hrefs.find((h) => /return=/.test(h)) || '').replace(/^.*return=([^&#]+).*$/, '$1');
  return { signinDoor: hrefs.some((h) => /signin=1/.test(h)), signupDoor: hrefs.some((h) => /signup=1/.test(h)),
    returnTo: ret ? decodeURIComponent(ret) : null };
};

async function wallsFrom(browser, rel) {
  const ctx = await newAnon(browser);
  const page = await ctx.newPage();
  const walls = [];
  let followed = 0;
  try {
    await page.goto(`${SEEDER}/workhive/${rel}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(1500);
    // every link to an APP page (a root *.html that is not the landing): the public families serve everyone, so only
    // an app page can wall; read AFTER the seeder's prefix bridge rewrote the hrefs, so each is the URL a tap opens
    const targets = await page.evaluate(() => {
      const out = new Map();
      for (const a of document.querySelectorAll('a[href]')) {
        let u; try { u = new URL(a.href, location.href); } catch (_) { continue; }
        if (u.origin !== location.origin) continue;
        const m = u.pathname.match(/^\/workhive\/([a-z0-9-]+\.html)$/i);
        if (!m || m[1] === 'index.html') continue;
        if (!out.has(m[1])) out.set(m[1], { file: m[1], url: u.href, text: (a.textContent || '').trim().slice(0, 40) });
      }
      return [...out.values()];
    });
    // in-page refusals named in the page's own markup (the toast and the sign-in wall helper)
    const refusals = await page.evaluate(() => [...document.querySelectorAll('[onclick]')]
      .filter((el) => /whAuthRequiredToast|whSignInWall/.test(el.getAttribute('onclick') || ''))
      .map((el, i) => { el.setAttribute('data-cv2-probe', String(i)); return { i, text: (el.textContent || '').trim().slice(0, 40) }; }));
    for (const t of targets.slice(0, MAX_WALL_LINKS)) {
      followed++;
      const p2 = await ctx.newPage();
      try {
        await p2.goto(t.url, { waitUntil: 'domcontentloaded', timeout: 25000 });
        await p2.waitForTimeout(2500);
        const st = await p2.evaluate(readAuthState);
        const gate = await p2.evaluate(readInlineGate);
        const v = classifyLanding({ requested: t.file, landedPath: st.path.replace(/^\/workhive\//, ''),
          landedQuery: st.query, inlineGate: gate && st.path.endsWith('/' + t.file) ? gate : null,
          modalOpen: st.modalOpen,
          signinDoor: gate && st.path.endsWith('/' + t.file) ? gate.signinDoor : st.signinDoor,
          signupDoor: gate && st.path.endsWith('/' + t.file) ? gate.signupDoor : st.signupDoor,
          returnTo: gate && st.path.endsWith('/' + t.file) ? gate.returnTo : st.returnTo });
        if (v.wall) walls.push({ from: `"${t.text}" -> ${t.file}`, ...v });
      } catch (e) {
        walls.push({ from: `"${t.text}" -> ${t.file}`, wall: true, doored: false, why: `the link did not load: ${String(e.message || e).slice(0, 60)}` });
      }
      await p2.close();
    }
    for (const r of refusals) {
      followed++;
      await page.evaluate((i) => { const el = document.querySelector(`[data-cv2-probe="${i}"]`); el && el.click(); }, r.i);
      await page.waitForTimeout(900);
      const t = await page.evaluate(() => {
        const toast = document.getElementById('wh-auth-toast');
        if (!toast) return null;
        const hrefs = [...toast.querySelectorAll('a[href]')].map((a) => a.getAttribute('href') || '');
        const ret = (hrefs.find((h) => /return=/.test(h)) || '').replace(/^.*return=([^&#]+).*$/, '$1');
        return { signinDoor: hrefs.some((h) => /signin=1/.test(h)), signupDoor: hrefs.some((h) => /signup=1/.test(h)), returnTo: ret ? decodeURIComponent(ret) : null };
      });
      const v = t ? classifyLanding({ requested: rel, landedPath: rel, toast: true, ...t })
        : { wall: false };
      if (v.wall) walls.push({ from: `in-page "${r.text}"`, ...v });
    }
  } finally {
    await ctx.close();
  }
  return { followed, walls };
}

async function funnelFrom(browser, rel) {
  const steps = {};
  const ctx = await newAnon(browser);
  const page = await ctx.newPage();
  const uname = 'cvpage_' + Date.now().toString(36);
  let created = false;
  try {
    const resp = await page.goto(`${SEEDER}/workhive/${rel}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(1800);
    const text = await page.evaluate(() => (document.body.innerText || '').length);
    steps.arrival = (resp && resp.ok() && text > 200) ? { ok: true }
      : { ok: false, why: `served ${resp ? resp.status() : 'nothing'} with ${text} characters` };
    // the page's own sign-up door: the first VISIBLE control whose target is the real signup, never the waitlist
    const door = await page.evaluate(() => {
      const vis = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
      const els = [...document.querySelectorAll('a[href],button')].filter(vis).filter((el) => !el.closest('[id^="wh-ai"],[id^="wh-hub"],#wh-feedback-panel'));
      const d = els.find((el) => /[?&]signup=1/.test(el.getAttribute('href') || '') || /whPrimaryCta|openSignUp/.test(el.getAttribute('onclick') || ''));
      const waitlist = els.some((el) => /#join\b/.test(el.getAttribute('href') || ''));
      if (!d) return { found: false, waitlist };
      d.setAttribute('data-cv3-door', '1');
      return { found: true, text: (d.textContent || '').trim().slice(0, 40), href: d.getAttribute('href'), waitlist };
    });
    steps.door = door.found ? { ok: true, text: door.text }
      : { ok: false, why: door.waitlist ? 'the only joining control is the #join waitlist' : 'no sign-up door on the page' };
    if (door.found) {
      await Promise.all([page.waitForLoadState('domcontentloaded').catch(() => {}), page.click('[data-cv3-door="1"]', { timeout: 8000 })]);
      let open = false;
      for (let i = 0; i < 12 && !open; i++) {
        await page.waitForTimeout(600);
        open = await page.evaluate(() => { const p = document.getElementById('panel-signup'); const u = document.getElementById('su-username');
          return !!(p && !p.classList.contains('hidden') && u && u.getClientRects().length); }).catch(() => false);
      }
      steps['door-opens-signup'] = open ? { ok: true, landed: page.url().replace(SEEDER, '') }
        : { ok: false, why: `the door "${door.text}" landed on ${page.url().replace(SEEDER, '')} without the signup panel` };
      if (open) {
        const src = await page.evaluate(() => { try { return sessionStorage.getItem('wh_signup_source'); } catch (_) { return null; } });
        await page.fill('#su-username', uname);
        await page.fill('#su-password', 'Probe!2026x');
        await page.fill('#su-confirm', 'Probe!2026x');
        await page.fill('#su-displayname', 'CV Probe ' + uname.slice(-4)).catch(() => {});
        await page.click('#su-btn');
        let converted = false;
        for (let i = 0; i < 15 && !converted; i++) {
          await page.waitForTimeout(900);
          converted = await page.evaluate(() => document.getElementById('ops-home')?.style.display === 'block'
            || /Account secured/i.test(document.getElementById('panel-signup')?.innerText || '')).catch(() => false);
        }
        // a kept return= navigates onward after the account exists - that is value reached too, read from the URL
        // (never from a failed evaluate, which would credit any error as a conversion)
        if (!converted && !/\/index\.html/.test(new URL(page.url()).pathname)) converted = true;
        created = true;
        steps.account = converted ? { ok: true } : { ok: false, why: 'submitted, but no signed-in value within 13 s' };
        const cnt = adminQuery(`select count(*) from worker_profiles where username = '${uname}';`);
        const n = typeof cnt === 'string' ? parseInt(cnt, 10) : null;
        steps['db-row'] = n === 1 ? { ok: true } : { ok: false, why: `worker_profiles holds ${n === null ? 'an unreadable count' : n} row(s) for the new username` };
        steps.attribution = src ? { ok: true, source: src }
          : { ok: false, why: `no source recorded for the door "${door.text}" (sessionStorage wh_signup_source empty at submit, so signup_completed reaches GA4 without one)` };
      }
    }
  } catch (e) {
    const first = CV3_STEPS.find((s) => !steps[s]);
    if (first) steps[first] = { ok: false, why: 'walk error: ' + String(e.message || e).slice(0, 80) };
  } finally {
    if (created) {
      adminQuery(`delete from worker_profiles where username = '${uname}';`);
      adminQuery(`delete from auth.users where email = '${uname}@auth.workhiveph.com';`);
    }
    await ctx.close();
  }
  const left = created ? adminQuery(`select count(*) from auth.users where email = '${uname}@auth.workhiveph.com';`) : '0';
  return { steps, cleaned: String(left).trim() === '0', uname };
}

async function main() {
  const args = process.argv.slice(2);
  if (args.includes('--self-test')) process.exit(selfTest());
  const CHECK = args.includes('--check');
  const ACCEPT = args.includes('--accept');
  if (selfTest()) process.exit(1);
  const pageArg = args.includes('--page') ? args[args.indexOf('--page') + 1] : null;
  const roster = pageArg ? pageArg.split(',').map((s) => s.trim()).filter(Boolean) : ROSTER;
  const { chromium } = await import('playwright');
  const { takeBrowserSlot } = await import('./browser_slot.mjs');
  const release = await takeBrowserSlot('prove_page_conversion');
  const browser = await chromium.launch();
  const recs = {};
  try {
    for (const rel of roster) {
      const w = await wallsFrom(browser, rel);
      const f = await funnelFrom(browser, rel);
      const cv2 = cv2Of(w.followed, w.walls);
      const cv3 = cv3Of(f.steps);
      recs[rel] = { CV2: { verdict: cv2.verdict, pct: cv2.pct, note: cv2.note },
        CV3: { verdict: cv3.verdict, pct: cv3.pct, note: cv3.note },
        walls: w.walls, links_followed: w.followed, funnel: cv3.steps, account_cleaned: f.cleaned };
      console.log(`[CV] ${rel.padEnd(62)} CV2 ${cv2.verdict === 'N/A' ? 'N/A' : cv2.pct + '%'} (${w.walls.length} wall(s) / ${w.followed} followed)  CV3 ${cv3.pct}%${f.cleaned ? '' : '  ★ACCOUNT NOT CLEANED ' + f.uname}`);
      for (const x of w.walls.filter((x) => !x.doored)) console.log(`       wall: ${x.from} - ${x.why}`);
      for (const [s, r] of Object.entries(cv3.steps)) if (!r.ok) console.log(`       ${s}: ${r.why}`);
    }
  } finally {
    await browser.close();
    if (typeof release === 'function') release();
  }
  // merge: a --page run replaces only the pages it walked
  let doc = { _doc: 'CV2 + CV3 per page, walked signed out at 390 by tools/prove_page_conversion.mjs (local stack).', pages: {} };
  if (existsSync(OUT)) { try { doc = JSON.parse(readFileSync(OUT, 'utf8')); } catch (_) { /* empty-catch-allow: rewritten below */ } }
  doc.pages = Object.assign({}, doc.pages || {}, recs);
  doc.ts = new Date().toISOString();
  writeFileSync(OUT, JSON.stringify(doc, null, 1) + '\n');
  // the ratchet: a wall without both doors is never accepted; CV3 may not fall below a page's floor
  let floors = {};
  if (existsSync(BASE)) { try { floors = JSON.parse(readFileSync(BASE, 'utf8')).cv3 || {}; } catch (_) { floors = {}; } }
  const bad = [];
  for (const [p, r] of Object.entries(recs)) {
    if (r.CV2.verdict === 'MEASURED' && r.CV2.pct < 100) bad.push(`${p}: CV2 ${r.CV2.pct}% - a wall without both doors`);
    if (floors[p] != null && r.CV3.pct < floors[p]) bad.push(`${p}: CV3 ${r.CV3.pct}% below its floor ${floors[p]}%`);
    if (!r.account_cleaned) bad.push(`${p}: the probe account was not cleaned up`);
  }
  if (ACCEPT || !existsSync(BASE)) {
    for (const [p, r] of Object.entries(recs)) floors[p] = r.CV3.pct;
    writeFileSync(BASE, JSON.stringify({ cv3: floors, note: 'per-page CV3 floors; only --accept or a first run writes them' }, null, 1) + '\n');
  }
  console.log(`[CV] ${Object.keys(recs).length} page(s) walked; ${bad.length ? 'FAIL - ' + bad.join('; ') : 'PASS'}`);
  if (CHECK && bad.length) process.exit(1);
}

main().catch((e) => { console.error(e); process.exit(1); });
