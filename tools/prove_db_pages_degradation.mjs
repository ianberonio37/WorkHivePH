// prove_db_pages_degradation — P-L "compound failure" (--data) and "systemic ripple" (--shared) on the DB-backed
// pages (2026-09-05). A signed-in worker opens the page while EVERY Supabase request fails from the first byte
// (--data: rest + functions + realtime + auth refresh aborted) or while the shared scripts never arrive
// (--shared: utils.js, tokens.css, the feedback/wayfinding/offline-banner scripts). The page must SAY so - a
// visible failure/retry message or an honest-empty note - and must not sit on a skeleton or a blank content root.
// The wait covers utils.js's retry envelope (four retries with backoff, ~9 s).
//   node tools/prove_db_pages_degradation.mjs --data     # every data read fails
//   node tools/prove_db_pages_degradation.mjs --shared   # every shared script fails
//   ... --page alert-hub.html
import { chromium } from 'playwright';
import { SEEDER, HIVE, signIn, PAGE_QUERY, VIS_JS, SETTLE_MS } from './prover_harness.mjs';   // shared preamble (2026-09-05)
const MODE = process.argv.includes('--shared') ? 'shared' : 'data';
const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const LIST = (() => { const i = process.argv.indexOf('--pages'); return i >= 0 ? process.argv[i + 1].split(',') : null; })();   // a subset, so a 34-page roster fits the background cap
const PAGES = [
  'platform-actions.html', 'alert-hub.html', 'analytics.html', 'assistant.html', 'community.html', 'engineering-design.html',
  'inventory.html', 'ai-quality.html', 'founder-console.html', 'marketplace-admin.html', 'plant-connections.html',
  'agentic-rag-observability.html', 'marketplace-seller-profile.html', 'achievements.html', 'analytics-report.html',
  'asset-hub.html', 'audit-log.html', 'dayplanner.html', 'hive.html', 'logbook.html', 'marketplace-seller.html',
  'public-feed.html', 'promo-poster.html',   // P369/P379 the fourth state (2026-09-05)
  // ── the live-walk wave (2026-09-06): the degradation family's remaining 11 surfaces, taken from
  // tools/live_walk_manifest.py --family "degradation & state". These are the reference/static and
  // public surfaces the first roster skipped because they make few data reads - but --shared still
  // asks the question that matters for them: when the shared scripts never arrive, does the page SAY so?
  'design-system.html', 'index.html', 'learn/index.html', 'llm-observability.html', 'marketplace.html',
  'offline-fallback.html', 'project-report.html', 'shift-brain.html', 'status.html',
  'symbol-gallery.html', 'validator-catalog.html',
];
// PAGE_QUERY comes from the harness (keyed by the page's OWN parameter name)
const DATA_RE = /\/rest\/v1\/|\/functions\/v1\/|\/realtime\/v1\/|\/storage\/v1\//;
const SHARED_RE = /\/(utils|wh-feedback-fab|wayfinding|offline-banner|maturity-gate|nav-hub|session-timeout)\.js(\?|$)|\/tokens\.css/;
const FAIL_WORDS = /fail|unavailable|could not|couldn.t|retry|try again|offline|not load|unreachable|error|something went wrong|check your connection/i;
// #wh-connection-notice is the platform's central transport-failure notice (utils.js _whNoteTransportFailure) - the first run
// never looked at it and graded pages that HAD said so as silent (2026-09-05).
const STATUS_SEL = '[role="status"], [role="alert"], .wh-source-chip, .honest-empty, .wh-list-error, .empty-state, .mod-empty, .verdict, #meta, #wh-connection-notice, [id$="-notice"], [data-wh-read-failed]';

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1280, height: 800 }, serviceWorkers: 'block' });
await signIn(ctx);

let bad = 0, n = 0;
for (const file of (LIST || PAGES)) {
  if (ONLY && file !== ONLY) continue;
  n++;
  const p = await ctx.newPage();
  let blocked = 0;
  const re = MODE === 'shared' ? SHARED_RE : DATA_RE;
  await p.route('**/*', (route) => { const u = route.request().url(); if (re.test(u)) { blocked++; return route.abort('failed'); } return route.continue(); });
  await p.goto(`${SEEDER}/workhive/${file}${PAGE_QUERY[file] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(SETTLE_MS);   // the retry envelope (~9 s) + the last settle pass (15 s)
  const r = await p.evaluate(({ STATUS_SEL, VIS_JS }) => {
    // checkVisibility, not offsetParent: the platform's transport notice (#wh-connection-notice via _whShowNotice) is position:fixed,
    // which has NO offsetParent - the first runs graded nine pages that HAD said so as silent (2026-09-05).
    const vis = (0, eval)(VIS_JS);
    const statuses = [...document.querySelectorAll(STATUS_SEL)].filter(vis).map((e) => (e.innerText || '').replace(/\s+/g, ' ').trim()).filter(Boolean);
    const skeletons = [...document.querySelectorAll('.wh-skeleton, [class*="skeleton"], [aria-busy="true"]')].filter(vis).length;
    const main = document.querySelector('main, [role="main"], #app, #root') || document.body;
    const body = (document.body.innerText || '').replace(/\s+/g, ' ').trim();
    return { statuses: statuses.join(' | ').slice(0, 300), skeletons, mainLen: ((main.innerText || '').replace(/\s+/g, ' ').trim()).length, bodyLen: body.length, signinWall: /sign in|log in/i.test(body.slice(0, 400)) && body.length < 900 };
  }, { STATUS_SEL, VIS_JS }).catch(() => ({ statuses: '', skeletons: 0, mainLen: 0, bodyLen: 0, signinWall: false }));
  if (MODE === 'data' && blocked === 0) { console.log(`  n/a ${file.padEnd(32)} no data request to fail (the page renders from stored identity and static copy)`); n--; await p.close(); continue; }   // promo-poster (2026-09-05)
  const says = FAIL_WORDS.test(r.statuses);
  const stuck = r.skeletons > 0 && !says;
  const blank = r.mainLen < 120 && !says;
  const ok = MODE === 'data' ? (says && !stuck) : (says || (r.mainLen > 200 && !stuck));
  if (!ok) bad++;
  // ★T40's SECOND HALF: A FAILURE THAT IS VISIBLE BUT UNRECOVERABLE IS STILL A DEAD END (2026-09-06). Saying
  // "couldn't load" is necessary and not sufficient - the person has to be able to get their data back without
  // reloading from scratch. So the block is LIFTED and the page's own retry control pressed; the page must then
  // render real content. A page with no retry control is reported, not failed, when it recovers on its own.
  let recovered = 'n/a';
  if (MODE === 'data' && says) {
    await p.unroute('**/*').catch(() => {});
    let refetched = 0;
    p.on('request', (rq) => { if (DATA_RE.test(rq.url())) refetched++; });
    const btns = (await p.$$('button, [role="button"], a[href="#"], [data-action="retry"]')).length
      ? await (async () => {
          const all = await p.$$('button, [role="button"], a[href="#"], [data-action="retry"]');
          const keep = [];
          for (const el of all) {
            const t = ((await el.innerText().catch(() => '')) || '').trim();
            if (/^(retry|try again|reload)\b/i.test(t)) keep.push(el);
          }
          return keep;
        })()
      : [];
    const btn = btns.length ? btns[0] : null;
    if (btn) {
      for (const bx of btns) {
        await bx.evaluate((el) => el.click()).catch(() => {});
        await p.waitForTimeout(900);
      }
      await p.waitForTimeout(14000);   // a re-read runs the page's full retry envelope (~9s) before it can render
      const after = await p.evaluate((s2) => ({ mainLen: ((document.querySelector('main, [role="main"], #app, #root') || document.body).innerText || '').replace(/\s+/g, ' ').trim().length, stillFailing: /could not|couldn.t|unavailable|failed/i.test(([...document.querySelectorAll(s2)].map((e) => e.innerText || '').join(' '))) }), STATUS_SEL).catch(() => ({ mainLen: 0, stillFailing: true }));
      const blocking = await p.evaluate(() => [...document.querySelectorAll('[id*="read-failed" i], .wh-list-error, [data-wh-read-failed]')]
        .some((e) => e.checkVisibility && e.checkVisibility({ opacityProperty: true, visibilityProperty: true }))).catch(() => true);
      recovered = (refetched > 0 && (!blocking || after.mainLen > r.mainLen + 40))
        ? `retry re-read ${refetched} time(s), blocking failure cleared`
        : `RETRY DID NOT RECOVER (${refetched} re-read(s), blocking panel ${blocking ? 'still up' : 'cleared'})`;
      if (recovered.startsWith('RETRY')) { bad++; }
    } else {
      recovered = 'no retry appeared in this failure state (the page may still offer one on another path)';
    }
  }
  console.log(`  ${ok ? 'ok ' : 'BAD'} ${file.padEnd(32)} blocked=${String(blocked).padStart(3)} says=${says ? 'yes' : 'NO '} skeletons=${r.skeletons} main=${r.mainLen}ch${r.signinWall ? ' (sign-in wall)' : ''}${MODE === 'data' ? ' · ' + recovered : ''}${ok ? '' : ' :: ' + r.statuses.slice(0, 120)}`);
  await p.close();
}
await b.close();
console.log(`${bad ? 'FAIL' : 'PASS'} db-pages-${MODE}-degradation - ${n - bad}/${n} pages say so (no stuck skeleton, no blank root) when ${MODE === 'data' ? 'every data read' : 'every shared script'} fails`);
process.exit(bad ? 1 : 0);
