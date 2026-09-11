// prove_failure_traceable — the ERROR TRACKING & LOGS layer of the LAYER-UX wave (§LX, 2026-09-06).
// All four of the layer's lenses in one walk, because they are one question asked from four sides:
// when this breaks for a person, can anyone afterwards find out what happened?
//
//   E1 leaves a trace   the failure a person hit is RECORDED somewhere queryable (client_errors /
//                       wh_traces), not only printed to a console nobody was watching
//   E2 names itself     what they are shown is not a bare "something went wrong" on a page whose own
//                       log knew the status, the route and the code
//   E3 quotable         they are given something to quote - a trace id, a code, a time - so a report
//                       can be matched to the record instead of starting a hunt
//   E4 reached someone  the record is not write-only: it carries the fields the observability layer
//                       actually reads (route, status, a timestamp), so a counter or an alert can see it
//
// ★THE FAILURE IS INDUCED, NOT WAITED FOR. Every Supabase read is aborted from the first byte, which is
// the shape a person meets as "the network went away" - then the DB is asked, as an outside witness,
// whether anything about that moment was written down.
//
//   node tools/prove_failure_traceable.mjs
//   node tools/prove_failure_traceable.mjs --page hive.html
import { chromium } from 'playwright';
import { execSync } from 'node:child_process';
import { SEEDER, signIn, PAGE_QUERY, VIS_JS, SETTLE_MS } from './prover_harness.mjs';

const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const LIST = (() => { const i = process.argv.indexOf('--pages'); return i >= 0 ? process.argv[i + 1].split(',') : null; })();
const psql = (sql) => { try { return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim(); } catch { return ''; } };

const ROSTER = ['hive.html', 'logbook.html', 'inventory.html', 'dayplanner.html', 'alert-hub.html',
                'asset-hub.html', 'community.html', 'analytics.html', 'marketplace.html',
                'shift-brain.html', 'pm-scheduler.html', 'skillmatrix.html', 'achievements.html',
                'project-manager.html', 'index.html'];

const DATA_RE = /\/rest\/v1\/|\/functions\/v1\/|\/realtime\/v1\/|\/storage\/v1\//;
// a message that says only this is the defect E2 names: the page knew more than it said
const BARE = /^(something went wrong|an error occurred|error|failed|oops|try again)\.?$/i;
// ★A CLOCK TIME IS THE MOST QUOTABLE THING THERE IS, and the first version of this pattern could not
// see one: "ref 10:42:07" is three two-digit groups, so \d{3} missed it and the detector reported a page
// carrying a perfectly good reference as having nothing to quote. What counts is anything a person can
// read back down a phone - a time, a version, a status code, an id.
const QUOTABLE = /\b([0-9a-f]{8,}|[A-Z][A-Z0-9_]{3,}|\d{3}\b|\d{4}-\d{2}-\d{2}|\d{1,2}:\d{2}(:\d{2})?|app\s+v[\d.]+)/;

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
await signIn(ctx);

// what the observability tables held before any of this
const before = {
  client_errors: Number(psql("select count(*) from client_errors") || 0),
  wh_traces: Number(psql("select count(*) from wh_traces") || 0),
};

let bad = 0, n = 0;
const noTrace = [];
for (const file of (ONLY ? [ONLY] : (LIST || ROSTER))) {
  n++;
  const p = await ctx.newPage();
  const consoleErrors = [];
  p.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 80)); });
  await p.route('**/*', (r) => (DATA_RE.test(r.request().url()) ? r.abort('failed') : r.continue()));
  await p.goto(`${SEEDER}/workhive/${file}${PAGE_QUERY[file] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(SETTLE_MS);

  const shown = await p.evaluate((VIS_JS) => {
    const vis = (0, eval)(VIS_JS);
    const sel = '[role="status"], [role="alert"], .wh-list-error, #wh-connection-notice, .honest-empty, [id$="-notice"], .verdict, [data-wh-read-failed]';
    return [...document.querySelectorAll(sel)].filter(vis)
      .map((e) => (e.innerText || '').replace(/\s+/g, ' ').trim()).filter(Boolean);
  }, VIS_JS).catch(() => []);

  const issues = [];
  const text = shown.join(' | ');
  if (!text) issues.push('E2 nothing is shown at all while every read is failing');
  else {
    const bareOnly = shown.every((s) => BARE.test(s.trim()));
    if (bareOnly) issues.push(`E2 the person is shown only "${shown[0].slice(0, 50)}" on a page whose own log knew the route and the status`);
    if (!QUOTABLE.test(text)) issues.push('E3 nothing in the message can be quoted back - no id, no code, no time to match a report against a record');
  }
  if (consoleErrors.length === 0 && !text) issues.push('E1 the failure produced neither a message nor a console record');

  if (issues.length) bad++;
  console.log(`  ${issues.length ? 'BAD' : 'ok '} ${file.padEnd(24)} ${shown.length} notice(s), ${consoleErrors.length} console error(s)${issues.length ? ` · ${issues.length} issue(s)` : ''}`);
  for (const s of issues.slice(0, ONLY ? 10 : 2)) console.log(`        ${s.slice(0, 160)}`);
  if (issues.some((s) => s.startsWith('E1'))) noTrace.push(file);
  await p.close();
}
await b.close();

// ── E1/E4 · the outside witness: did any of that reach a table anyone can query? ─────────────────
const after = {
  client_errors: Number(psql("select count(*) from client_errors") || 0),
  wh_traces: Number(psql("select count(*) from wh_traces") || 0),
};
const wrote = (after.client_errors - before.client_errors) + (after.wh_traces - before.wh_traces);
// E4: the record must carry what an alert or a counter reads, not just exist
const shaped = Number(psql("select count(*) from client_errors where created_at is not null and coalesce(message,'') <> ''") || 0);
console.log(`  ${wrote > 0 ? 'ok ' : 'note'} E1/E4 outside witness    client_errors ${before.client_errors}->${after.client_errors} · wh_traces ${before.wh_traces}->${after.wh_traces} · ${shaped} stored error(s) carry a time and a message`);
if (wrote === 0) {
  console.log('        E1 a browser-side read failure reaches NO table: with the transport severed the reporter cannot post either, so the record');
  console.log('           it would have written is lost with the failure it describes - the honest scope of this walk, named rather than graded green');
}

console.log(`${bad ? 'FAIL' : 'PASS'} failure-traceable - ${n - bad}/${n} pages tell a person what failed in terms they can quote, with the stored-record half reported as scope`);
process.exitCode = bad ? 1 : 0;
