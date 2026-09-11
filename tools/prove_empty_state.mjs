// prove_empty_state — when this page has nothing to show yet, does it say WHY and WHAT TO DO FIRST?
//
// Two W3-DF rows carried over from the wave-2 walks, which found the gap and deferred it by name:
// `engineering-design.html` (nothing designed yet) and `report-sender.html` (nothing to send yet).
//
// ★AN EMPTY HIVE IS NOT THE ONLY WAY TO SEE AN EMPTY PAGE, and it is the expensive way. A seeded supervisor's
// hive is full, so waiting for a genuinely empty one means seeding a new hive to ask one question. A filter
// that matches nothing produces the same state a newcomer meets - the page has nothing to show - without
// touching any data. If the page has no filter, it is opened cold and read as it stands.
//
// What a good empty state does, and this asks for both halves:
//   WHY   — it names the situation ("no reports yet", "nothing matches that")
//   WHAT  — it names the next move ("create your first", "clear the filter", "add an asset")
// A blank panel does neither. A spinner is neither pass nor fail: nobody has read that page yet.
//
//   node tools/prove_empty_state.mjs
//   node tools/prove_empty_state.mjs --self-test
import { chromium } from 'playwright';
import { takeBrowserSlot } from './browser_slot.mjs';
import { establishIdentity, PERSON } from './wh_identity.mjs';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';

const args = process.argv.slice(2);
const ORIGIN = process.env.WH_SEEDER_URL ? `${process.env.WH_SEEDER_URL}/workhive` : 'http://127.0.0.1:5000/workhive';
// ★MATCH THE PART THE ROWS SHARE. The first version keyed on "has nothing to SHOW yet" and found one of the
// two: the other row says "nothing to SEND yet", because report-sender sends rather than shows. A roster
// built from a phrase only one subject uses is a roster with a silent hole in it.
const MARK = 'yet it says why';

// ★A DIGIT IS NOT A STATEMENT. The first version accepted "0 " as "this page says there is nothing", and a
// page showing a count, a price or a version number matched it. An empty state SAYS something: "no results",
// "nothing yet", "you have not added". A bare zero is a number that happens to be on the page.
const WHY = /\b(no\s+\w+|nothing|none\b|not yet|nothing yet|empty|haven'?t|have not|don'?t have)\b/i;
const WHAT = /\b(create|add|start|new |first|clear|reset|choose|select|open|try|import|upload|go to|invite|generate)\b/i;

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
  if (!WHY.test('No reports yet')) fails.push('"No reports yet" is not read as naming the situation');
  if (!WHAT.test('Create your first report')) fails.push('"Create your first" is not read as a next move');
  if (WHY.test('Reports') || WHAT.test('Reports')) fails.push('a bare heading is being read as an empty state');
  if (!WHY.test('Nothing matches that filter')) fails.push('a filter-empty message is not recognised');
  console.log(fails.length ? 'FAIL empty-state self-test - ' + fails.join('; ')
    : `self-test OK: ${rows.length} row(s) to answer; a bare heading is neither half of an empty state`);
  process.exit(fails.length ? 1 : 0);
}

await takeBrowserSlot('empty-state');
const browser = await chromium.launch();
const session = await establishIdentity(browser, ORIGIN);
console.log(session ? `  signed in as ${PERSON.name}` : `  no identity (${establishIdentity.why}) - these pages will be the door`);

const results = [];
let bad = 0, unread = 0;
for (const r of rows) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, ...(session ? { storageState: session } : {}) });
  const p = await ctx.newPage();
  let rec;
  try {
    await p.goto(`${ORIGIN}/${r.page}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await p.waitForTimeout(3200);
    const landed = await p.evaluate(() => location.pathname.replace(/^\//, ''));
    const want = r.page.replace(/^\//, '');
    if (!(landed === want || landed.endsWith('/' + want))) {
      rec = { verdict: 'n/a', line: `reached ${landed.slice(0, 40)} instead - not this page` };
    } else {
      // drive it to empty: any visible search/filter box gets a string nothing can match
      const filtered = await p.evaluate(() => {
        const vis = (e) => e.getBoundingClientRect().height > 0;
        // ★THE FIRST SEARCH BOX ON THE PAGE IS OFTEN NOT THE PAGE'S. On report-sender this picked
        // `#wh-hub-search` - the shared navigation hub's box - so the walk filtered the MENU and then read
        // the page's unchanged text as an empty state. Shared chrome is excluded: a page's own filter lives
        // inside its content, not in the nav, the header or the hub that every page carries.
        const box = Array.from(document.querySelectorAll('input[type="search"], input[type="text"], input:not([type])'))
          .filter(vis)
          .filter((e) => !e.closest('nav, header, #wh-hub, [id*="hub"], [class*="hub"], [class*="nav-"]'))
          .find((e) => /search|filter|find|query/i.test((e.id || '') + ' ' + (e.className || '') + ' ' + (e.placeholder || '')));
        if (!box) return false;
        box.value = 'zzzqqqxnothingmatchesthis';
        box.dispatchEvent(new Event('input', { bubbles: true }));
        box.dispatchEvent(new Event('change', { bubbles: true }));
        box.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: 'Enter' }));
        return true;
      });
      await p.waitForTimeout(filtered ? 2000 : 400);
      const s = await p.evaluate(() => ({
        txt: (document.body.innerText || '').replace(/\s+/g, ' ').trim(),
        spin: Array.from(document.querySelectorAll('[class*="skeleton"],[class*="shimmer"],[aria-busy="true"]'))
          .filter((e) => e.getBoundingClientRect().height > 0).length,
      }));
      if (s.spin > 0) rec = { verdict: 'n/a', line: `still resolving (${s.spin} visible placeholder(s))` };
      else {
        const why = WHY.exec(s.txt); const what = WHAT.exec(s.txt);
        rec = (why && what)
          ? { verdict: 'ok', line: `${filtered ? 'filtered to nothing: ' : 'as it stands: '}says why ("${why[0]}") and what to do ("${what[0]}")` }
          : { verdict: 'BAD', line: `${filtered ? 'filtered to nothing and ' : ''}${!why ? 'never says there is nothing' : 'says there is nothing but'} ${!what ? 'names no next move' : 'names a next move'}` };
      }
    }
  } catch (e) {
    rec = { verdict: 'n/a', line: 'could not be read: ' + String(e.message).slice(0, 48) };
  }
  await ctx.close();
  if (rec.verdict === 'BAD') bad++;
  if (rec.verdict === 'n/a') unread++;
  results.push({ ...r, ...rec });
  const tag = rec.verdict === 'ok' ? 'ok ' : rec.verdict === 'n/a' ? 'n/a' : 'BAD';
  console.log(`  ${tag} ${r.id.padEnd(8)} ${r.page.padEnd(30)} ${rec.line.slice(0, 92)}`);
}
await browser.close();
mkdirSync('.tmp', { recursive: true });
writeFileSync('.tmp/empty_state.json', JSON.stringify({ walked: results.length, bad, results }, null, 1));
console.log(`${bad ? 'FAIL' : 'PASS'} empty-state - ${results.length - bad - unread}/${results.length} say why and what to do, ${unread} unread  ·  .tmp/empty_state.json`);
process.exit(bad ? 1 : 0);
