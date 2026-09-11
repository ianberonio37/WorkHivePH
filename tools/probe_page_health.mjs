// probe_page_health — the whole-artifact check to run after ANY page edit (2026-09-05, register row 50: my alert-hub
// focus patch left the feed on 'Loading alerts...' and the focus prover called the missing control n/a twice).
// Signed in, it opens the page, waits the settle envelope, and reports: page errors, console errors, and for the named
// container (default: the page's main list/feed) how many children / buttons / links / inputs it painted.
//   node tools/probe_page_health.mjs alert-hub.html            # container guessed (#feed, #entries-list, #listing-grid, main)
//   node tools/probe_page_health.mjs hive.html "#feed"
// Exit 1 on any page error or an empty container - the number a person would notice first.
import { chromium } from 'playwright';
import { SEEDER, signIn, SETTLE_MS, PAGE_QUERY, DB_PAGES } from './prover_harness.mjs';
const ALL = process.argv.includes('--all');
const file = ALL ? null : process.argv[2]; const sel = ALL ? null : (process.argv[3] || null);
if (!file && !ALL) { console.log('usage: node tools/probe_page_health.mjs <page.html> [container selector] | --all'); process.exit(2); }
const FILES = ALL ? DB_PAGES : [file];
const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
await signIn(ctx);
let anyBad = 0;
for (const f of FILES) {
const p = await ctx.newPage(); const pageErrors = [], consoleErrors = [];
p.on('pageerror', (e) => pageErrors.push(e.message.slice(0, 160)));
p.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 140)); });
await p.goto(`${SEEDER}/workhive/${f}${PAGE_QUERY[f] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch((e) => pageErrors.push('goto: ' + e.message.slice(0, 100)));
await p.waitForTimeout(ALL ? 9000 : SETTLE_MS);
const r = await p.evaluate((sel) => {
  const guess = sel || ['#feed', '#feed-list', '#entries-list', '#listing-grid', '#fb-list', '#approval-queue', 'main', '#root', '#app'].find((s) => document.querySelector(s));
  const c = guess ? document.querySelector(guess) : null;
  const vis = (e) => (typeof e.checkVisibility === 'function' ? e.checkVisibility() : e.offsetParent !== null);
  return { container: guess, children: c ? c.children.length : -1, buttons: c ? [...c.querySelectorAll('button')].filter(vis).length : -1, links: c ? [...c.querySelectorAll('a[href]')].filter(vis).length : -1, inputs: c ? c.querySelectorAll('input, textarea, select').length : -1, text: (c?.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 160), loading: /loading|computing|fetching/i.test((c?.textContent || '').slice(0, 400)) };
}, sel).catch((e) => ({ container: sel, children: -1, error: e.message }));
await p.close();
const bad = pageErrors.length > 0 || r.children <= 0 || r.loading;
if (bad) anyBad++;
console.log(`${bad ? 'BAD' : 'ok '} ${f.padEnd(32)} container ${r.container}: ${r.children} children, ${r.buttons} buttons, ${r.links} links, ${r.inputs} inputs${r.loading ? ' · STILL LOADING' : ''}${pageErrors.length ? ' · page errors: ' + JSON.stringify(pageErrors.slice(0, 2)) : ''}${!ALL ? '\n  text: "' + r.text + '"\n  console errors: ' + JSON.stringify(consoleErrors.slice(0, 4)) : ''}`);
}
await b.close();
if (ALL) console.log(`${anyBad ? 'FAIL' : 'PASS'} page-health - ${FILES.length - anyBad}/${FILES.length} DB pages paint their main container with no page error`);
const bad = anyBad > 0;
process.exit(bad ? 1 : 0);
