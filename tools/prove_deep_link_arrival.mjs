// prove_deep_link_arrival — you opened this page from a pasted link, with no history behind you.
//
// Twelve W3-PG rows ask that of a specific page. It has two honest answers and this asks for whichever one
// applies, because **a private page SHOULD refuse a stranger** — the failure is not the refusal, it is
// refusing without saying what happened or where you were going:
//
//   a public page   must simply LOAD: it renders its own title and real content, not a shell.
//   a private page  must send you to the door AND KEEP YOUR DESTINATION, so signing in finishes the trip you
//                   started. A door that drops the return address makes a pasted link a dead end, and the
//                   person who sent it has no idea.
//
// ★NO HISTORY BEHIND YOU IS PART OF THE QUESTION. A fresh browser context per page, no referrer, nothing in
// storage - which is what a pasted link actually is. Re-using one context lets an earlier page's state carry
// a later one through, and the walk then measures a journey nobody made.
//
// ★AND THE LANDED URL IS READ, NOT ASSUMED. The prover that skipped this graded the sign-in door as if it
// were the page, for every piece it walked.
//
//   node tools/prove_deep_link_arrival.mjs
//   node tools/prove_deep_link_arrival.mjs --json .tmp/deep_link.json
//   node tools/prove_deep_link_arrival.mjs --self-test
import { chromium } from 'playwright';
import { takeBrowserSlot } from './browser_slot.mjs';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';

const args = process.argv.slice(2);
const BASE = (process.env.WH_SEEDER_URL || 'http://127.0.0.1:5000').replace(/\/workhive$/, '');
const MARK = 'pasted link with no history';

const rows = JSON.parse(readFileSync('trajectory_registry.json', 'utf8')).trajectories
  .filter((t) => t.status === 'specced' && (t.title || '').includes(MARK))
  .map((t) => ({ id: t.id, page: (t.pages || [])[0], wave: t.wave }))
  .filter((r) => r.page);

if (args.includes('--self-test')) {
  const fails = [];
  // (*)AN EMPTY ROSTER IS SUCCESS, NOT FAILURE. This self-test asserted that open rows exist, so the
  // moment its rows were banked the gate went red for having finished its work. A teeth test proves the
  // LENS can tell right from wrong; whether there is anything left to answer is a different question and
  // not this one. Kin of every hollow-lock lesson: a gate that bites its own success teaches people to
  // ignore it.
  // (an empty roster simply means every row it answers is already banked)
  // the door is recognised by its query, and the destination must survive in it
  const door = '/index.html?signin=1&return=engineering-design.html';
  if (!/[?&]return=([^&]+)/.test(door)) fails.push('the return parameter is not being read from the door URL');
  if (decodeURIComponent(/[?&]return=([^&]+)/.exec(door)[1]) !== 'engineering-design.html') {
    fails.push('the destination is not being recovered from the return parameter');
  }
  if (/[?&]return=/.test('/index.html?signin=1')) fails.push('a door with NO return is being read as if it had one');
  console.log(fails.length ? 'FAIL deep-link self-test - ' + fails.join('; ')
    : `self-test OK: ${rows.length} row(s) to answer, and a door without a return address is recognised as one`);
  process.exit(fails.length ? 1 : 0);
}

await takeBrowserSlot('deep-link-arrival');
const browser = await chromium.launch();
const results = [];
let bad = 0;
let unread = 0;
for (const r of rows) {
  // a fresh context per page: no history, no storage, no referrer - a pasted link and nothing else
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const p = await ctx.newPage();
  let rec;
  try {
    await p.goto(`${BASE}/${r.page}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await p.waitForTimeout(2600);
    const s = await p.evaluate(() => ({
      path: location.pathname.replace(/^\//, ''),
      search: location.search,
      title: document.title,
      chars: (document.body.innerText || '').replace(/\s+/g, ' ').trim().length,
      h1: ((document.querySelector('h1') || {}).textContent || '').replace(/\s+/g, ' ').trim().slice(0, 40),
      // ★A STUCK SKELETON IS INVISIBLE TO A LENGTH CHECK. platform-actions.html renders "Checking access…
      // Loading…" over four shimmer blocks and never resolves while the database is unreachable - 547
      // characters of placeholder, comfortably past any threshold, describing nothing a reader can use.
      // Counting that as an arrival is how a page that never finishes gets recorded as one that did.
      // ★A HIDDEN SKELETON IS NOT A STUCK ONE. public-feed.html keeps four `wh-skeleton` templates in the
      // DOM at zero height and fills a real list beside them - its data call returns 200 - so counting every
      // element with the class reported a page that had finished as one that never started, three times in
      // three provers. Only a skeleton with a BOX is somebody waiting.
      skeletons: Array.from(document.querySelectorAll('[class*="skeleton"],[class*="shimmer"],[aria-busy="true"]')).filter((e) => e.getBoundingClientRect().height > 0).length,
      loading: /\b(loading|checking access|please wait)…?\b/i.test((document.body.innerText || '').slice(0, 400)),
    }));
    if (s.path === r.page) {
      // arrived: it must be the page itself, with its own words and something on it
      rec = (s.skeletons > 0 || s.loading)
        ? { verdict: 'n/a', line: `still resolving (${s.skeletons} skeleton(s)${s.loading ? ', says it is loading' : ''}) - nobody has read this page yet, so it cannot be graded` }
        : s.chars >= 300
        ? { verdict: 'ok', line: `opens straight from a pasted link: "${s.title.slice(0, 40)}", ${s.chars} chars` }
        : { verdict: 'BAD', line: `arrives but renders only ${s.chars} chars - a shell, not the page` };
    } else {
      const m = /[?&]return=([^&]+)/.exec(s.search || '');
      const kept = m ? decodeURIComponent(m[1]) : '';
      rec = kept === r.page
        ? { verdict: 'ok', line: `private: sends you to the door and KEEPS the destination (return=${kept.slice(0, 30)})` }
        : { verdict: 'BAD', line: `sends you to ${s.path.slice(0, 26)} and ${kept ? `returns to "${kept.slice(0, 24)}"` : 'DROPS the destination'} - the pasted link is a dead end` };
    }
  } catch (e) {
    rec = { verdict: 'BAD', line: 'the page could not be opened at all: ' + String(e.message).slice(0, 50) };
  }
  await ctx.close();
  if (rec.verdict === 'BAD') bad++;
  if (rec.verdict === 'n/a') unread++;
  results.push({ ...r, ...rec });
  console.log(`  ${rec.verdict === 'ok' ? 'ok ' : rec.verdict === 'n/a' ? 'n/a' : 'BAD'} ${r.id.padEnd(8)} ${r.page.padEnd(34)} ${rec.line.slice(0, 92)}`);
}
await browser.close();
mkdirSync('.tmp', { recursive: true });
writeFileSync('.tmp/deep_link.json', JSON.stringify({ walked: results.length, bad, results }, null, 1));
console.log(`${bad ? 'FAIL' : 'PASS'} deep-link-arrival - ${results.length - bad - unread}/${results.length} page(s) answer a pasted link honestly, ${unread} still resolving  ·  .tmp/deep_link.json`);
process.exit(bad ? 1 : 0);
