// prove_anon_conversion — the anonymous conversion funnels (T3, T4, T5), walked as one family (2026-09-07).
//
// Three rows follow the same shape: a stranger arrives from search, gets value, reaches for something
// that needs an account, and meets a wall. The wall is the product's whole first impression, and the
// only thing it must not do is waste what they were about to do.
//
//   N1 lands        the public surface renders for someone with NO account - not a sign-in screen where
//                   the search result promised a calculator, a feed, or a marketplace
//   N2 walls        the gated action IS gated. A control that looks available to an anonymous visitor
//                   and fails on press teaches them the product is broken.
//   N3 explains     the wall says what an account is FOR, in that moment's terms, rather than a bare
//                   "sign in" - the difference between a reason and a toll booth
//   N4 preserves    what they were doing survives the trip: the return path carries them back to the
//                   page and the action, so signing up does not cost them their place
//
//   node tools/prove_anon_conversion.mjs
//   node tools/prove_anon_conversion.mjs --page public-feed.html
import { chromium } from 'playwright';
import { SEEDER, PAGE_QUERY, VIS_JS } from './prover_harness.mjs';

const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();

// the funnel, and the gated thing the stranger reaches for
const FUNNELS = [
  ['tools/bolt-torque-calculator/index.html', 'opens the interactive calculator', /open the interactive|try it|calculate/i],
  ['public-feed.html', 'wants to reply or post', /reply|post|comment|join|answer/i],
  ['marketplace.html', 'wants to contact a seller or list an item', /contact|inquire|message|sell|list an item|buy/i],
];

const EXPLAINS = /\b(free|account|hive|join|sign up|so you can|to keep|to save|your team|takes about|30 seconds|no cost)\b/i;

const b = await chromium.launch();
let bad = 0, n = 0;
const notReached = [];
for (const [file, what, actionRe] of (ONLY ? FUNNELS.filter((f) => f[0] === ONLY) : FUNNELS)) {
  n++;
  // no sign-in: a stranger from a search result carries nothing
  const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/${file}${PAGE_QUERY[file] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(12000);

  // ★THE GATED ACTION IS USUALLY ONE LISTING DEEP. A marketplace grid shows what is for sale; the
  // "contact the seller" control lives on the item, which is where a person reaches for it. Scanning
  // the grid reported a funnel with no entry on a page that has one for every visitor who opens a card.
  if (/marketplace/.test(file)) await p.evaluate(() => {
    const vis = (e) => e.checkVisibility && e.checkVisibility({ opacityProperty: true, visibilityProperty: true });
    // the opener is a labelled control ("Show details"), not the card itself
    // 2026-09-07 (T5 at 60%, "not measured"): '[class*="listing"]' matched the GRID CONTAINER before any card, so the
    // click landed on a wrapper and the detail sheet never opened - the control was reported as never on screen.
    // Reach it the way a person does: the first listing card, through the page's own opener when it is exposed.
    // the card FIRST (measured 2026-09-07: openDetailSheet is not a global, and the labelled-opener heuristic
    // ("view|open|details") matched a grid control before any card, so the sheet never opened and the funnel
    // read "not reached" twice)
    const first = document.querySelector('article.listing-card[data-id]');
    if (first) { first.click(); return; }
    const opener = [...document.querySelectorAll('button, [role="button"], a')]
      .find((e) => vis(e) && /^(show details|open listing|details)\b/i.test((e.innerText || '').trim()));
    if (opener) { opener.click(); return; }
    const card = [...document.querySelectorAll('[onclick*="etail" i], [onclick*="isting" i], [class*="listing-card"]')]
      .find((e) => vis(e) && (e.innerText || '').trim().length > 20);
    if (card) card.click();
  }).catch(() => {});
  await p.waitForTimeout(3500);

  const before = await p.evaluate((args) => {
    const vis = (0, eval)(args[0]);
    const rx = new RegExp(args[1], 'i');
    const main = document.querySelector('main, [role="main"], #app') || document.body;
    const text = (main.innerText || '').replace(/\s+/g, ' ').trim();
    const gated = [...document.querySelectorAll('button, [role="button"], a')]
      .filter((e) => vis(e) && e.checkVisibility({ opacityProperty: true, visibilityProperty: true }))
      .filter((e) => rx.test((e.innerText || '') + ' ' + (e.getAttribute('aria-label') || '')));
    if (gated.length) gated[0].setAttribute('data-wh-gated', '1');
    return { textLen: text.length, gatedLabel: gated.length ? (gated[0].innerText || '').trim().slice(0, 40) : '' };
  }, [VIS_JS, actionRe.source]).catch(() => ({ textLen: 0, gatedLabel: '' }));

  const issues = [];
  if (before.textLen < 400) issues.push(`N1 the public page renders only ${before.textLen} characters to a stranger - the search result promised more than this`);
  const unreached = !before.gatedLabel;
  if (unreached) notReached.push(`${file} (the ${what} control did not come on screen for this sweep)`);

  let wall = { text: '', hasReturn: false, url: '' };
  if (before.gatedLabel) {
    await p.evaluate(() => { const e = document.querySelector('[data-wh-gated]'); if (e) e.click(); }).catch(() => {});
    await p.waitForTimeout(6000);
    wall = await p.evaluate((VIS_JS) => {
      const vis = (0, eval)(VIS_JS);
      const sel = '[id^="wh-modal-ov-"], [role="dialog"], .wh-signin-wall, [id*="signin" i], [id*="gate" i], [role="alert"], [role="status"]';
      const texts = [...document.querySelectorAll(sel)].filter(vis)
        .map((e) => (e.innerText || '').replace(/\s+/g, ' ').trim()).filter(Boolean);
      return { text: texts.join(' | ').slice(0, 400), url: location.href, hasReturn: /return=|redirect=|next=/i.test(location.href) };
    }, VIS_JS).catch(() => wall);
    // a funnel may also navigate to the sign-in page rather than open a wall in place
    const navigated = /index\.html\?/.test(wall.url) || /signin/i.test(wall.url);
    const said = wall.text || (navigated ? 'navigated to the sign-in page' : '');
    if (!said) issues.push(`N3 pressing "${before.gatedLabel}" produced no wall and no navigation - the gate is invisible until it fails`);
    else if (wall.text && !EXPLAINS.test(wall.text)) {
      issues.push(`N3 the wall says "${wall.text.slice(0, 60)}" without saying what an account is FOR at this moment`);
    }
    if (navigated && !wall.hasReturn) issues.push('N4 the trip to sign-in carries no return path - signing up costs them the page they were on');
  }

  if (issues.length) bad++;
  console.log(`  ${issues.length ? 'BAD' : (unreached ? 'n/a' : 'ok ')} ${file.slice(0, 34).padEnd(36)} ${before.textLen}ch public · gated: "${before.gatedLabel || '(none found)'}"${wall.text ? ` · wall said ${wall.text.length}ch` : ''}`);
  for (const s of issues.slice(0, ONLY ? 8 : 2)) console.log(`        ${s.slice(0, 160)}`);
  await ctx.close();
}
await b.close();
if (notReached.length) console.log(`  note ${notReached.length} funnel(s) NOT REACHED, not clean: ${notReached.join('; ').slice(0, 200)}`);
console.log(`${bad ? 'FAIL' : 'PASS'} anon-conversion - ${n - bad - notReached.length}/${n - notReached.length} reachable funnels give a stranger value, gate the account-only action, explain what an account is for, and carry them back`);
process.exitCode = (bad || notReached.length) ? 1 : 0;   // an unreached funnel is owed, never clean - 0/0 is not a pass
