/* prove_public_feed_dated.mjs — T158: the public window does not pretend to be fresh (2026-08-26).
 *
 * public-feed is the platform's shop window: an anon visitor's first sight of whether anyone is
 * actually here. A community feed's worst failure is not being quiet - it is being quiet while
 * LOOKING live, because a visitor who cannot date what they are reading assumes it is current, and
 * discovers otherwise later.
 *
 * MEASURED 2026-08-26: 15 public posts, newest 42 DAYS old, ZERO made public in the last 30 days.
 * On a seeded fixture that number means nothing about the product - but it is exactly the state in
 * which a feed either tells the truth or flatters itself. This one tells the truth: every card
 * carries a date ("Jul 16, 2026"), so a reader can judge for themselves.
 *
 * THE ASSERTION: every rendered card shows a date. Not "the feed is fresh" - freshness is a
 * community outcome nobody can gate - but that the page never hides HOW fresh it is.
 *
 * ★WHY THIS IS WORTH A GATE ON SOMETHING THAT ALREADY PASSES: the timestamp is the smallest, most
 * droppable element on a card. A redesign that tightens the layout and loses it costs nothing
 * visible and quietly converts an honest quiet feed into one that looks live - the single change
 * that would turn this surface from truthful to misleading.
 *
 * Non-writing: loads the page anonymously and reads it.
 *
 * Usage: node tools/prove_public_feed_dated.mjs
 */
import { chromium } from 'playwright';

const SEEDER = process.env.WH_SEEDER || 'http://127.0.0.1:5000';

const browser = await chromium.launch();
const v = {};
try {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push(String(e).slice(0, 110)));

  await page.goto(`${SEEDER}/public-feed.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(7000);

  Object.assign(v, await page.evaluate(() => {
    const list = document.getElementById('feed-list');
    const cards = list ? Array.from(list.children).filter((c) => (c.innerText || '').trim().length > 40) : [];
    // a date on this platform renders as "Jul 16, 2026" or a relative age
    const DATE = /\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}\b|\bago\b|\byesterday\b|\btoday\b/i;
    const undated = cards.filter((c) => !DATE.test(c.innerText || ''));
    return {
      cards: cards.length,
      undated: undated.length,
      sampleUndated: undated.slice(0, 2).map((c) => (c.innerText || '').replace(/\s+/g, ' ').slice(0, 60)),
    };
  }));
  v.pageerrors = errs.length;

  // an empty feed cannot prove anything - say so rather than passing on zero cards
  v.measured = v.cards > 0;
  console.log(`  cards ${v.cards} | undated ${v.undated} | pageerrors ${v.pageerrors}`);
  if (v.sampleUndated && v.sampleUndated.length) console.log('  undated e.g.:', v.sampleUndated.join(' // '));
} catch (e) {
  v.error = String(e.message || e).slice(0, 180);
  console.log('probe error:', v.error);
} finally {
  await browser.close();
}

if (!v.measured) {
  console.log('FAIL public-feed-dated — NO CARDS RENDERED. Zero undated cards over zero cards is not a '
    + 'pass; the feed failed to load or the public set is empty.');
  process.exit(1);
}
const pass = !v.error && v.undated === 0 && v.pageerrors === 0;
console.log((pass ? 'PASS' : 'FAIL') + ` — public feed dated: ${JSON.stringify(v)}`);
process.exit(pass ? 0 : 1);
