// prove_persona_cells — the EX-PX wave: the thin cells of persona × device × entry (2026-09-07).
//
// Eleven cells the registry held fewer than five rows in before this wave, each now one row per page it
// applies to. The rows are read from the registry (wave EX-PX), and each row's `story` names its cell -
// "cell deep-link: any on phone-390 arriving by deep-link" - so this prover walks what was seeded, not
// a list it remembers. One lens per cell, in the person's terms:
//
//   deep-link        opened cold from a chat link, the page still makes sense with no history
//   first-time       opened for the first time, the page explains itself
//   buyer            a person here to BUY reaches the goods without being made a seller first
//   data-volume      the biggest list stays a page, not a hang, and offers a way to see more
//   wide-pc          at 1920 the content uses the screen without stranding or stretching prose
//   tablet           at 768, both orientations, nothing sits off the edge
//   quota-spent      the AI quota is gone; the rest of the page works and says what it cannot do
//   expiry-mid-read  the session ends while READING; what was on screen stays, and a way back appears
//   kiosk-print      on a wall or a printout, unattended, the page is true and readable
//   email-arrival    arriving from a notification lands ON the thing it notified about
//   returner         coming back after weeks, the page shows where they left off
//
// ★THE CELL DECIDES THE INSTRUMENT. Viewport, persona and entry path are the cell's, not a default:
// a kiosk cell renders print media with nobody signed in; a buyer cell signs in as a plain worker; a
// deep-link cell opens in a context that has never seen the app. A row the sweep cannot bring on screen
// is NOT REACHED, never clean.
//
//   node tools/prove_persona_cells.mjs
//   node tools/prove_persona_cells.mjs --cell quota-spent
import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';
import { SEEDER, signIn, PAGE_QUERY, VIS_JS, SETTLE_MS } from './prover_harness.mjs';
import { VIEW_ONLY, askSurface, launcherOnlyFor } from './ai_ask.mjs';

const ONLY_CELL = (() => { const i = process.argv.indexOf('--cell'); return i >= 0 ? process.argv[i + 1] : null; })();
const ONLY_PAGE = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const ROWS = (() => {
  const reg = JSON.parse(readFileSync('trajectory_registry.json', 'utf8'));
  return reg.trajectories.filter((t) => t.wave === 'EX-PX').map((t) => ({
    id: t.id, page: (t.pages || [])[0], device: t.device, persona: t.persona, entry: t.entry,
    cell: (String(t.story || '').match(/^cell ([a-z-]+):/) || [])[1] || 'unknown',
  }));
})();
const VIEW = { 'phone-390': [390, 844], 'tablet-768': [768, 1024], 'desktop-1280': [1280, 900], 'wide-1920': [1920, 1080], 'fixed-kiosk-print': [1920, 1080], 'narrow-320': [320, 640], any: [1280, 900] };
// the words a page uses for itself: its <title> before ': WorkHive', minus the words every page shares
const GENERIC = new Set(['workhive', 'maintenance', 'digital', 'live', 'your', 'with', 'from', 'page', 'tool', 'tools']);
function destinationWords(page) {
  let title = '';
  try { title = (readFileSync(page, 'utf8').match(/<title>([^<]*)<\/title>/) || [])[1] || ''; } catch (_) { title = ''; }
  const head = title.split(/[:|\u2014-]/)[0];
  const ws = head.split(/[^A-Za-z]+/).filter((w) => w.length >= 4 && !GENERIC.has(w.toLowerCase()));
  const stem = page.replace(/\.html$/, '').split('-').filter((w) => w.length >= 4 && !GENERIC.has(w.toLowerCase()));
  return [...new Set([...ws, ...stem.map((w) => w[0].toUpperCase() + w.slice(1))])];
}

const REFUSAL = JSON.stringify({ error: 'AI call limit reached for this hive. Try again in about 12 minutes.', scope: 'hour', retry_after: 720 });

const b = await chromium.launch();
let bad = 0, n = 0;
const notReached = [];
const byCell = {};
for (const r of ROWS) {
  if (ONLY_CELL && r.cell !== ONLY_CELL) continue;
  if (ONLY_PAGE && r.page !== ONLY_PAGE) continue;
  if (!r.page) continue;
  n++;
  const [w, h] = VIEW[r.device] || VIEW.any;
  const ctx = await b.newContext({ viewport: { width: w, height: h }, serviceWorkers: 'block' });
  const signedIn = !['deep-link', 'kiosk-print'].includes(r.cell) && r.persona !== 'any' || ['first-time', 'data-volume', 'wide-pc', 'tablet', 'quota-spent', 'expiry-mid-read', 'email-arrival', 'returner'].includes(r.cell);
  if (signedIn) await signIn(ctx);
  const p = await ctx.newPage();
  if (r.cell === 'quota-spent') {
    await p.route('**/functions/v1/**', (rt) => rt.fulfill({ status: 429, contentType: 'application/json', body: REFUSAL })).catch(() => {});
  }
  let url = `${SEEDER}/workhive/${r.page}${PAGE_QUERY[r.page] || ''}`;
  if (r.cell === 'email-arrival') url += (url.includes('?') ? '&' : '?') + 'focus=first';
  await p.goto(url, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  if (r.cell === 'kiosk-print') await p.emulateMedia({ media: 'print' }).catch(() => {});
  await p.waitForTimeout(SETTLE_MS);

  const issues = [];
  const scan = async () => p.evaluate((VIS_JS) => {
    const vis = (0, eval)(VIS_JS);
    const doc = document.documentElement;
    // a page whose <main> holds only its toolbar (project-report: the report body lives outside it) read as 168
    // characters while its sections were on screen - the region is trusted only when it carries most of the page
    let main = document.querySelector('main, [role="main"], #app, #root') || document.body;
    if (main !== document.body && (main.innerText || '').length < 0.5 * (document.body.innerText || '').length) main = document.body;
    const text = (main.innerText || '').replace(/\s+/g, ' ').trim();
    const heads = [...document.querySelectorAll('h1, h2')].filter(vis).map((e) => (e.innerText || '').trim()).filter(Boolean);
    const overflow = Math.max(0, doc.scrollWidth - doc.clientWidth);
    const spinners = [...document.querySelectorAll('.wh-skeleton, [class*="skeleton"], [aria-busy="true"]')].filter(vis).length;
    const longestLine = Math.max(0, ...[...document.querySelectorAll('p, li')].filter((e) => vis(e) && (e.innerText || '').trim().length > 120).map((e) => e.getBoundingClientRect().width));
    const guide = !!document.querySelector('.wh-help, [data-guide], details summary');
    const loadMore = [...document.querySelectorAll('button, a')].some((e) => vis(e) && /load more|show more|next page|see all/i.test(e.innerText || ''));
    const nodes = main.querySelectorAll('*').length;
    const notices = [...document.querySelectorAll('[role="alert"], [role="status"], .honest-empty, .wh-list-error, [id$="-notice"]')].filter(vis).filter((e) => !e.classList.contains('wh-source-chip')).map((e) => (e.innerText || '').replace(/\s+/g, ' ').trim()).filter(Boolean);
    const sellerWall = /become a seller|register as a seller|seller registration/i.test(text.slice(0, 600));
    const wayBack = [...document.querySelectorAll('button, a, [role="button"]')].some((e) => vis(e) && /sign in|log in/i.test(e.innerText || ''));
    const focused = !!document.querySelector('[data-focused], .focused, .is-focused, :target');
    return { text: text.slice(0, 6000), textLen: text.length, heads: heads.slice(0, 2), overflow, spinners, longestLine, guide, loadMore, nodes, notices: notices.slice(0, 3), sellerWall, wayBack, focused };
  }, VIS_JS).catch(() => null);

  let s = await scan();
  if (!s || s.textLen === 0) { notReached.push(`${r.id} ${r.page} (${r.cell})`); await ctx.close(); console.log(`  n/a ${r.id.padEnd(6)} ${r.cell.padEnd(16)} ${r.page.padEnd(30)} rendered nothing - not reached`); continue; }

  switch (r.cell) {
    case 'deep-link': {
      // 2026-09-07: the first walk read 14,386 identical characters on 24 different pages - every app page bounces a
      // cold visitor to index.html?signin=1&return=<page>, so the lens was grading the landing page 24 times and
      // passing on its h1s. A deep link "makes sense with no history" only if what the person SEES names where the
      // link was taking them: the destination's own words (its <title>, the nav label) on the page or on the door.
      const words = destinationWords(r.page);
      const finalUrl = p.url();
      const named = words.filter((w) => new RegExp('\\b' + w + '\\b', 'i').test(s.text || '')).length > 0
        || (s.heads || []).some((h) => words.some((w) => new RegExp('\\b' + w + '\\b', 'i').test(h)));
      if (/signin=1/.test(finalUrl)) {
        if (!/[?&]return=/.test(finalUrl)) issues.push('bounced to the sign-in door and the link\'s destination was dropped (no ?return=)');
        else if (!new RegExp('return=[^&]*' + r.page.replace('.', '\\.')).test(finalUrl)) issues.push(`bounced to the sign-in door with a return that is not ${r.page}`);
        if (!named) issues.push(`the sign-in door says nothing about ${r.page} (${words.join('/')}) - the same door for every link`);
      } else {
        if (!s.heads.length) issues.push('opened from a link with no history, nothing names this page');
        if (!named) issues.push(`nothing visible names this page (${words.join('/')}) for a person arriving cold`);
        if (s.textLen < 300) issues.push(`only ${s.textLen} characters arrive for a person with no context`);
      }
      break;
    }
    case 'first-time':
      if (!s.guide) issues.push('nothing on the page explains itself to someone here for the first time');
      break;
    case 'buyer':
      if (s.sellerWall) issues.push('a person here to buy is met by a seller-registration wall before the goods');
      if (s.textLen < 300) issues.push(`only ${s.textLen} characters of goods for a buyer`);
      break;
    case 'data-volume':
      if (s.nodes > 6000 && !s.loadMore) issues.push(`${s.nodes} DOM nodes rendered at once with no way to page - a thousand rows is a hang`);
      if (s.spinners) issues.push(`${s.spinners} skeleton(s) still showing after settle`);
      break;
    case 'wide-pc':
      if (s.longestLine > 1200) issues.push(`a ${Math.round(s.longestLine)}px line of prose - too long to track back to the start of`);
      break;
    case 'tablet':
      if (s.overflow > 4) issues.push(`${s.overflow}px of content sits off the right edge at 768`);
      await p.setViewportSize({ width: 1024, height: 768 }).catch(() => {});
      await p.waitForTimeout(1500);
      s = await scan();
      if (s && s.overflow > 4) issues.push(`${s.overflow}px off the edge in landscape at 1024`);
      break;
    case 'quota-spent': {
      // 2026-09-07: the first walk judged assistant.html without asking it anything - nothing asked, nothing
      // refused, "nothing on the page says so". The spent-quota moment is PROVOKED the way the AI-trust wave
      // provokes it (tools/ai_ask.mjs: open, prepare, type, send / press the page's own trigger), then read.
      const viewOnly = VIEW_ONLY.has(r.page);
      const asked = viewOnly ? false : await askSurface(p, r.page, launcherOnlyFor(r.page));
      await p.waitForTimeout(7000);
      s = await scan();
      const said = await p.evaluate(() => ((document.body.innerText || '') + ' ' + JSON.stringify(window.__whNotices || [])).replace(/\s+/g, ' ')).catch(() => '');
      if (s.textLen < 300) issues.push(`with the AI refused, only ${s.textLen} characters remain - the whole page died with the quota`);
      if (viewOnly) { /* shows AI output only: nothing is asked, so nothing can be refused - the page must simply survive */ }
      else if (!asked) issues.push('no ask box or trigger was reachable, so the spent-quota moment was not provoked - unmeasured, not clean');
      else if (!/limit|quota|try again|later|resets|spent|out of/i.test(said)) issues.push('the AI quota is gone and nothing on the page says so');
      break;
    }
    case 'expiry-mid-read': {
      // 2026-09-07: the first walk read "the expiry was noticed but no way back was offered" on 23 of 24 pages. Measured
      // on logbook: with the session dead the page made ZERO requests in 20 s - a person who is only reading meets
      // nothing - and the "notice" was the source chip (role=status). So two honest halves: while they read, what they
      // were reading stays; at their next action - coming back to the page - the platform says why and offers the way in.
      const before = s.textLen;
      await p.evaluate(() => { for (const k of Object.keys(localStorage)) if (/auth|token|supabase/i.test(k)) localStorage.removeItem(k); }).catch(() => {});
      await p.route('**/auth/v1/**', (rt) => rt.fulfill({ status: 401, contentType: 'application/json', body: '{"message":"JWT expired"}' })).catch(() => {});
      await p.route('**/rest/v1/**', (rt) => rt.fulfill({ status: 401, contentType: 'application/json', body: '{"message":"JWT expired","code":"PGRST301"}' })).catch(() => {});
      await p.waitForTimeout(8000);
      s = await scan();
      if (s && s.textLen < before * 0.5) issues.push(`the page threw away ${before - s.textLen} characters a person was reading when the session ended`);
      // the next action: coming back
      await p.reload({ waitUntil: 'load', timeout: 30000 }).catch(() => {});
      await p.waitForTimeout(Math.min(SETTLE_MS, 12000));
      s = await scan();
      const url = p.url();
      const atDoor = /signin=1/.test(url);
      const doorKeepsPage = atDoor && new RegExp('return=[^&]*' + r.page.replace('.', '\\.')).test(url);
      const saidWhy = (s.notices || []).some((t) => /session|sign in|expired/i.test(t)) || /session (has )?expired|sign in again|sign in to open/i.test(s.text || '');
      if (s && s.spinners) issues.push(`${s.spinners} skeleton(s) still showing after the session ended - the page waits for data that will never come`);
      if (atDoor && !doorKeepsPage) issues.push(`coming back sent them to the sign-in door without ${r.page} in ?return=`);
      if (!s.wayBack && !atDoor) issues.push('coming back after the session ended, the page offers no way in');
      if (!saidWhy) issues.push('coming back after the session ended, nothing says the session ended');
      break;
    }
    case 'kiosk-print':
      if (s.textLen < 300) issues.push(`in print media only ${s.textLen} characters survive - the page is chrome, not content`);
      if (s.spinners) issues.push(`${s.spinners} spinner(s) still turning on a wall nobody is watching`);
      break;
    case 'email-arrival':
      if (s.textLen < 300) issues.push(`arriving from a notification, only ${s.textLen} characters land`);
      break;
    case 'returner': {
      // 2026-09-07: analytics-report read 274 characters with its report BUILDER on screen - a returning person is
      // offered the thing they came for. Thin is a cold start only when nothing names the page or nothing can be pressed.
      const control = await p.evaluate(() => [...document.querySelectorAll('button, select, input, a.btn, [role="button"]')].some((e) => e.checkVisibility && e.checkVisibility() && !e.disabled && !/^(← ?back|back)$/i.test((e.innerText || '').trim()))).catch(() => false);
      if (!s.heads.length || (s.textLen < 300 && !control)) issues.push('coming back, the page offers a cold start');
      break;
    }
    default:
      issues.push(`unknown cell ${r.cell}`);
  }
  await ctx.close();
  byCell[r.cell] = byCell[r.cell] || { n: 0, bad: 0 };
  byCell[r.cell].n++;
  if (issues.length) { bad++; byCell[r.cell].bad++; }
  console.log(`  ${issues.length ? 'BAD' : 'ok '} ${r.id.padEnd(6)} ${r.cell.padEnd(16)} ${r.page.padEnd(30)} ${s ? s.textLen + 'ch' : ''}${issues.length ? ' · ' + issues[0].slice(0, 90) : ''}`);
}
await b.close();
console.log('  by cell: ' + Object.entries(byCell).map(([c, v]) => `${c} ${v.n - v.bad}/${v.n}`).join(' · '));
if (notReached.length) console.log(`  note ${notReached.length} row(s) NOT REACHED, not clean`);
console.log(`${bad ? 'FAIL' : 'PASS'} persona-cells - ${n - bad - notReached.length}/${n - notReached.length} reached cell rows hold for the person, device and arrival they name`);
process.exitCode = bad ? 1 : 0;
