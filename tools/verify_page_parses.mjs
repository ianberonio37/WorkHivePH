/* verify_page_parses.mjs — does this page still PARSE and run its scripts without throwing?
 *
 * WHY THIS EXISTS. Five times in one session an escape collapsed while I was editing a string, and the fifth
 * took a whole page down: `day\'s` lost its backslash inside a single-quoted JS string, alert-hub raised
 * "SyntaxError: Unexpected identifier" at parse time, and the entire feed stopped rendering. `node --check`
 * cannot catch that, because the JS lives inside HTML. A grep of the edited line cannot catch it either - the
 * line LOOKS right, which is exactly the problem.
 *
 * The only reliable check is to load the page in a browser and listen. A parse error inside an inline <script>
 * surfaces as a pageerror, and every page on this platform boots its own scripts on load, so a page that
 * throws here is broken for a person too.
 *
 * WHAT IT IS NOT. This is not a functional test - a page can parse perfectly and still be wrong. It answers
 * one question, the cheapest and most catastrophic one: did my edit break the file.
 *
 * Usage:
 *   node tools/verify_page_parses.mjs                    # every production page
 *   node tools/verify_page_parses.mjs alert-hub hive     # named pages only
 *   node tools/verify_page_parses.mjs --signed-in        # boot them as the supervisor too
 */
import { chromium } from 'playwright';
import { existsSync } from 'fs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const SIGNED_IN = args.includes('--signed-in');
const named = args.filter((a) => !a.startsWith('--'));

const ALL = ['index', 'hive', 'logbook', 'inventory', 'pm-scheduler', 'project-manager', 'dayplanner',
  'asset-hub', 'analytics', 'alert-hub', 'skillmatrix', 'shift-brain', 'voice-journal', 'assistant',
  'community', 'public-feed', 'achievements', 'engineering-design', 'resume', 'report-sender',
  'project-report', 'analytics-report'];
const PAGES = named.length ? named : ALL;

// Errors that are about the ENVIRONMENT rather than the file: a page that cannot reach a local service is
// not a page with a syntax error, and failing on those would make this check useless as a pre-commit gate.
const ENV_NOISE = /Failed to fetch|NetworkError|ERR_CONNECTION|load failed|AbortError|timeout|401|403|429/i;

const browser = await chromium.launch();
let broken = 0, clean = 0;

for (const page of PAGES) {
  if (!existsSync(page + '.html')) { console.log(`  ?  ${page.padEnd(20)} no such file`); continue; }
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  if (SIGNED_IN) {
    try {
      const { signIn } = await import('./live_page_journeys.mjs');
      await signIn(ctx, 'supervisor');
    } catch (_) { /* unsigned is still a valid parse check */ }
  }
  const p = await ctx.newPage();
  const fatal = [];
  p.on('pageerror', (e) => {
    const msg = String(e && e.message ? e.message : e);
    // A SYNTAX error is always fatal to the file. Other throws are only reported when they are not
    // environmental, because a missing local edge function must not be confused with a broken page.
    if (/SyntaxError|Unexpected|Invalid or unexpected token|missing \) after/i.test(msg) || !ENV_NOISE.test(msg)) {
      fatal.push(msg.slice(0, 140));
    }
  });
  try {
    await p.goto(`${ORIGIN}/${page}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await p.waitForTimeout(3500);   // let inline boot scripts run
  } catch (e) {
    fatal.push('navigation: ' + String(e.message).slice(0, 90));
  }
  if (fatal.length) {
    broken++;
    console.log(`  ✗  ${page.padEnd(20)} ${fatal.length} error(s)`);
    for (const f of fatal.slice(0, 3)) console.log(`       ${f}`);
  } else {
    clean++;
    console.log(`  ok ${page.padEnd(20)} parses and boots clean`);
  }
  await ctx.close();
}

await browser.close();
console.log(`\n  ${clean} clean · ${broken} broken` + (SIGNED_IN ? ' (signed in)' : ' (anon)'));
if (broken) {
  console.log('  A page that throws here is broken for a person too. Fix before anything else.');
  process.exit(1);
}
