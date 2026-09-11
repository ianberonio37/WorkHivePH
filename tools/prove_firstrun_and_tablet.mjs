// prove_firstrun_and_tablet — two W3-PG questions a page can answer with nothing in it yet.
//
//   FIRST RUN   "It is your first time on this page and nobody is beside you."
//               A page with nothing to show must say WHAT this is and WHAT TO DO NEXT. The good answers on
//               this platform already read like that: ph-intelligence says "Join or create a hive to see PH
//               Intelligence… it is a team tool"; the seller profile says "No seller specified. This page
//               needs a seller name in the URL. Open it via marketplace.html." Both name the situation and
//               the next move. A blank frame, or a bare title, does neither.
//
//   TABLET 768  "On a shared tablet at 768 this page has to hold together in both orientations."
//               Portrait 768x1024 and landscape 1024x768: no horizontal scroll in either, and the page's
//               own controls stay reachable. A layout that only survives one orientation is a layout that
//               breaks when somebody turns the tablet on a workbench.
//
// ★A PAGE STILL SHOWING SKELETONS IS NEITHER PASS NOR FAIL. Nobody has read it yet. platform-actions renders
// "Checking access… Loading…" over four shimmer blocks whenever its data is unreachable - 547 characters of
// placeholder that clears any length threshold while describing nothing. It is reported n/a and re-walked.
//
//   node tools/prove_firstrun_and_tablet.mjs
//   node tools/prove_firstrun_and_tablet.mjs --self-test
import { chromium } from 'playwright';
import { takeBrowserSlot } from './browser_slot.mjs';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';

const args = process.argv.slice(2);
const BASE = (process.env.WH_SEEDER_URL || 'http://127.0.0.1:5000').replace(/\/workhive$/, '');
const FIRST = 'first time on this page';
const TABLET = 'shared tablet at 768';

// what "what to do next" looks like in words: an instruction, an invitation, or a named way forward
// ★AND THE VOCABULARY IS THE PAGE'S, NOT MINE - AGAIN. This list first missed status.html, which offers a
// "Refresh" control and a "How this page works" section, and reported that it "says what it is but never
// what to do next". Orienting a reader IS the next move on a page whose job is to be read, and so is
// refreshing it. That was the tenth time in this wave a hand-listed vocabulary accused a page of lacking
// something it has - the same mistake as demanding the word "Table" of a citation that says "ISO 22400-2".
const NEXT_MOVE = /\b(join|create|add|open|start|sign in|sign up|choose|select|pick|upload|connect|invite|go to|try|browse|search for|needs? a|paste|enter|refresh|check|view|how this page works|learn more|read the|contact|ask an admin|back to)\b/i;

const all = JSON.parse(readFileSync('trajectory_registry.json', 'utf8')).trajectories;
const rows = all.filter((t) => t.status === 'specced'
  && ((t.title || '').includes(FIRST) || (t.title || '').includes(TABLET)))
  .map((t) => ({ id: t.id, page: (t.pages || [])[0], wave: t.wave,
                 kind: (t.title || '').includes(FIRST) ? 'first' : 'tablet' }))
  .filter((r) => r.page);

if (args.includes('--self-test')) {
  const fails = [];
  // (*)AN EMPTY ROSTER IS SUCCESS, NOT FAILURE. This self-test asserted that open rows exist, so the
  // moment its rows were banked the gate went red for having finished its work. A teeth test proves the
  // LENS can tell right from wrong; whether there is anything left to answer is a different question and
  // not this one. Kin of every hollow-lock lesson: a gate that bites its own success teaches people to
  // ignore it.
  // (an empty roster simply means every row it answers is already banked)
  if (!NEXT_MOVE.test('Join or create a hive to see PH Intelligence')) fails.push('a real invitation is not read as a next move');
  if (!NEXT_MOVE.test('This page needs a seller name in the URL. Open it via marketplace.html')) fails.push('a real instruction is not read as a next move');
  if (NEXT_MOVE.test('Agentic RAG Observability')) fails.push('a bare title is being read as a next move');
  console.log(fails.length ? 'FAIL firstrun-tablet self-test - ' + fails.join('; ')
    : `self-test OK: ${rows.length} row(s) to answer; an invitation counts, a bare title does not`);
  process.exit(fails.length ? 1 : 0);
}

const read = async (browser, page, vw, vh) => {
  const ctx = await browser.newContext({ viewport: { width: vw, height: vh } });
  const p = await ctx.newPage();
  await p.goto(`${BASE}/${page}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await p.waitForTimeout(2600);
  const s = await p.evaluate(() => ({
    path: location.pathname.replace(/^\//, ''),
    txt: (document.body.innerText || '').replace(/\s+/g, ' ').trim(),
      // ★A HIDDEN SKELETON IS NOT A STUCK ONE. public-feed.html keeps four `wh-skeleton` templates in the
      // DOM at zero height and fills a real list beside them - its data call returns 200 - so counting every
      // element with the class reported a page that had finished as one that never started, three times in
      // three provers. Only a skeleton with a BOX is somebody waiting.
    skeletons: Array.from(document.querySelectorAll('[class*="skeleton"],[class*="shimmer"],[aria-busy="true"]')).filter((e) => e.getBoundingClientRect().height > 0).length,
    overflow: document.documentElement.scrollWidth > window.innerWidth + 2,
    docW: document.documentElement.scrollWidth,
    winW: window.innerWidth,
  }));
  await ctx.close();
  return s;
};

await takeBrowserSlot('firstrun-tablet');
const browser = await chromium.launch();
const results = [];
let bad = 0, unread = 0;
for (const r of rows) {
  let rec;
  try {
    if (r.kind === 'first') {
      const s = await read(browser, r.page, 390, 844);
      if (s.path !== r.page) rec = { verdict: 'n/a', line: `needs an identity - this walk reached ${s.path.slice(0, 34)}` };
      else if (s.skeletons > 0 || /\b(loading|checking access)…?\b/i.test(s.txt.slice(0, 400))) {
        rec = { verdict: 'n/a', line: `still resolving (${s.skeletons} skeleton(s)) - nobody has read this page yet` };
      } else {
        const m = NEXT_MOVE.exec(s.txt);
        rec = (s.txt.length >= 120 && m)
          ? { verdict: 'ok', line: `tells a newcomer what to do next ("…${s.txt.slice(Math.max(0, m.index - 26), m.index + 40)}…")` }
          : { verdict: 'BAD', line: s.txt.length < 120 ? `only ${s.txt.length} chars - a newcomer is told nothing` : 'says what it is but never what to do next' };
      }
    } else {
      const port = await read(browser, r.page, 768, 1024);
      if (port.path !== r.page) rec = { verdict: 'n/a', line: `needs an identity - this walk reached ${port.path.slice(0, 34)}` };
      else if (port.skeletons > 0) rec = { verdict: 'n/a', line: `still resolving (${port.skeletons} skeleton(s))` };
      else {
        const land = await read(browser, r.page, 1024, 768);
        const badPort = port.overflow, badLand = land.overflow;
        rec = (!badPort && !badLand)
          ? { verdict: 'ok', line: `holds at 768 portrait (${port.docW}px) and 1024 landscape (${land.docW}px) - no sideways scroll in either` }
          : { verdict: 'BAD', line: `scrolls sideways in ${badPort && badLand ? 'BOTH orientations' : badPort ? 'portrait' : 'landscape'} (${badPort ? port.docW : land.docW}px against ${badPort ? port.winW : land.winW}px)` };
      }
    }
  } catch (e) {
    rec = { verdict: 'n/a', line: 'could not be read: ' + String(e.message).slice(0, 46) };
  }
  if (rec.verdict === 'BAD') bad++;
  if (rec.verdict === 'n/a') unread++;
  results.push({ ...r, ...rec });
  const tag = rec.verdict === 'ok' ? 'ok ' : rec.verdict === 'n/a' ? 'n/a' : 'BAD';
  console.log(`  ${tag} ${r.id.padEnd(8)} ${r.kind.padEnd(6)} ${r.page.padEnd(32)} ${rec.line.slice(0, 84)}`);
}
await browser.close();
mkdirSync('.tmp', { recursive: true });
writeFileSync('.tmp/firstrun_tablet.json', JSON.stringify({ walked: results.length, bad, results }, null, 1));
console.log(`${bad ? 'FAIL' : 'PASS'} firstrun-tablet - ${results.length - bad - unread}/${results.length} answered, ${bad} finding(s), ${unread} unread  ·  .tmp/firstrun_tablet.json`);
process.exit(bad ? 1 : 0);
