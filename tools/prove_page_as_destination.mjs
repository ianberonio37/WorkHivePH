// prove_page_as_destination — the destination-page journeys (T64, T67, T70, T71, T73, T75, T77, T78),
// walked as one family (2026-09-07).
//
// Eight rows ask whether a page holds up when it is where someone ARRIVES, rather than somewhere they
// pass through. A page reached from its own hub is forgiving: the person already knows what they were
// doing. A page reached from a link in a message, a bookmark, or an email is not - it has to orient
// them from nothing.
//
//   P1 says where   a heading names the page in words a person would use, so the first glance answers
//                   "what am I looking at"
//   P2 has content  the page's own data is on screen, not an empty shell or a stuck skeleton - a
//                   destination that arrives blank sends the person straight back where they came from
//   P3 says when    it states how fresh what they are seeing is (a source chip), because a stakeholder
//                   reading a report has to know whether it is today's
//   P4 leads on     there is somewhere to go next from here - this is a stop on a journey, not a
//                   cul-de-sac someone has to use the back button to escape
//
// ★ARRIVED AT COLD, IN A FRESH CONTEXT. Each page is opened directly as its own URL in a context that
// has not visited the app, which is what a link in a message actually does. Walking in from the hub
// would test the hub.
//
//   node tools/prove_page_as_destination.mjs
//   node tools/prove_page_as_destination.mjs --page status.html
import { chromium } from 'playwright';
import { SEEDER, signIn, PAGE_QUERY, VIS_JS, SETTLE_MS } from './prover_harness.mjs';

const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();

// the page, and the person who arrives at it
const DESTINATIONS = [
  ['audit-log.html', 'someone auditing a disputed change'],
  ['founder-console.html', "the owner opening their cockpit"],
  ['platform-actions.html', 'the owner acting on the platform'],
  ['marketplace-seller-profile.html', "a buyer checking a seller's trust page"],
  ['status.html', 'anyone asking whether the platform is up'],
  ['project-report.html', 'a stakeholder reading the project report'],
  ['dayplanner.html', 'a supervisor planning tomorrow'],
  ['voice-journal.html', 'a worker looking for something they said last week'],
];

const b = await chromium.launch();
let bad = 0, n = 0;
for (const [file, who] of (ONLY ? DESTINATIONS.filter((d) => d[0] === ONLY) : DESTINATIONS)) {
  n++;
  // a fresh context per page: an arrival carries no history of the app
  const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
  await signIn(ctx);
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/${file}${PAGE_QUERY[file] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(SETTLE_MS);

  const r = await p.evaluate((VIS_JS) => {
    const vis = (0, eval)(VIS_JS);
    const strict = (e) => e.checkVisibility && e.checkVisibility({ opacityProperty: true, visibilityProperty: true });
    const heads = [...document.querySelectorAll('h1, h2, [role="heading"][aria-level="1"]')]
      .filter((e) => vis(e) && (e.innerText || '').trim());
    const main = document.querySelector('main, [role="main"], #app, #root') || document.body;
    const text = (main.innerText || '').replace(/\s+/g, ' ').trim();
    const chips = [...document.querySelectorAll('.wh-source-chip, [data-source-chip], .source-chip, [id$="-source-chip"]')]
      .filter(vis).map((e) => (e.innerText || e.textContent || '').replace(/\s+/g, ' ').trim()).filter(Boolean);
    const skeletons = [...document.querySelectorAll('.wh-skeleton, [class*="skeleton"], [aria-busy="true"]')].filter(vis).length;
    // somewhere to go next: an internal link or a control that leads on, not counting the browser's back
    const onward = [...document.querySelectorAll('a[href]')].filter((e) => vis(e) && strict(e))
      .filter((e) => { const h = e.getAttribute('href') || ''; return h && !h.startsWith('#') && !/^https?:/i.test(h); }).length;
    return {
      heading: heads.length ? (heads[0].innerText || '').trim().slice(0, 48) : '',
      textLen: text.length,
      chips: chips.length,
      skeletons,
      onward,
      bodyText: text.slice(0, 300),
    };
  }, VIS_JS).catch(() => ({ heading: '', textLen: 0, chips: 0, skeletons: 0, onward: 0 }));

  const issues0 = [];
  const issues = issues0;
  if (!r.heading) issues.push(`P1 nothing on screen names this page, so ${who} cannot tell what they are looking at`);
  const explains = /no .{0,24}(specified|selected|chosen|found|yet)|nothing to show|choose|select|pick a/i.test(r.bodyText || '');
  if (r.textLen < 200 && !explains) issues.push(`P2 only ${r.textLen} characters and none of them say what is missing - an arrival lands on an empty shell`);
  else if (r.textLen < 200) issues.push(null);   // honest-empty: reported below, not failed
  if (r.skeletons) issues.push(`P3 ${r.skeletons} skeleton(s) still on screen after settling - the page never finished for them`);
  if (!r.chips) issues.push('P3 nothing says how fresh this is - a person reading it cannot tell whether it is today');
  if (r.onward === 0) issues.push('P4 no internal link leads anywhere from here - a cul-de-sac the back button is the only exit from');

  const real = issues.filter(Boolean);
  const honestEmpty = issues.length !== real.length;
  if (real.length) bad++;
  console.log(`  ${real.length ? 'BAD' : 'ok '} ${file.padEnd(32)}${honestEmpty ? ' [honest-empty]' : ''} "${r.heading || '(no heading)'}" · ${r.textLen}ch · ${r.chips} chip(s) · ${r.onward} way(s) onward`);
  for (const s of real.slice(0, ONLY ? 8 : 2)) console.log(`        ${s.slice(0, 160)}`);
  await ctx.close();
}
await b.close();
console.log(`${bad ? 'FAIL' : 'PASS'} page-as-destination - ${n - bad}/${n} pages orient someone who ARRIVES there cold: named, filled, dated, and leading somewhere`);
process.exitCode = bad ? 1 : 0;
