// prove_export_truthful — T49 "every export control produces a truthful, complete artifact" (2026-09-06).
//
// An export is the one artifact that leaves the platform. It gets filed, mailed, printed and shown to an
// auditor, and nothing on screen corrects it afterwards. The row rested on prose; this presses the buttons.
//
// For every export/download control the sweep can reach, as a signed-in supervisor:
//   E1 arrives     pressing it produces a DOWNLOAD (or opens a print view) within the timeout - a control that
//                  says "Export CSV" and yields nothing is the worst kind, because the person believes they have
//                  the file
//   E2 non-empty   the artifact has real bytes, not a 0-byte or header-only file
//   E3 named       its filename says what it is - not "download", "export", "untitled", "file"
//   E4 truthful    a CSV/JSON export carries as many data rows as the page's own visible list, or MORE (an
//                  export that silently ships fewer rows than the screen is the "cap shown as a total" bug in
//                  the one place nobody can check it later)
//
// ★A CLICK THAT DOWNLOADS NOTHING IS NOT PROOF THE CONTROL IS BROKEN. Some exports open a print dialog, some
// render a new tab, some are gated behind a modal that asks what to include. Those are reported by what they
// did, not failed, and named so the gap is visible rather than graded away.
//
//   node tools/prove_export_truthful.mjs
//   node tools/prove_export_truthful.mjs --page analytics-report.html
//   node tools/prove_export_truthful.mjs --self-test     (the judgment, on _fixtures/export-truthful-teeth.html)
import { chromium } from 'playwright';
import { mkdirSync, statSync, readFileSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { SEEDER, signIn, PAGE_QUERY, VIS_JS, SETTLE_MS, assertSignedIn } from './prover_harness.mjs';
import { ALL_ROWS_DRAWN } from './lib/long_list_text.mjs';

const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const LIST = (() => { const i = process.argv.indexOf('--pages'); return i >= 0 ? process.argv[i + 1].split(',') : null; })();
const SELF_TEST = process.argv.includes('--self-test');
const OUT = '.tmp/export-probe';

const ROSTER = [
  'logbook.html', 'inventory.html', 'asset-hub.html', 'analytics.html', 'analytics-report.html',
  'audit-log.html', 'project-report.html', 'project-manager.html', 'pm-scheduler.html', 'resume.html',
  'marketplace-seller.html', 'skillmatrix.html', 'founder-console.html', 'dayplanner.html', 'hive.html',
];

const FIND = function find(VIS_JS) {
  const vis = (0, eval)(VIS_JS);
  const EXPORT = /\b(export|download|csv|xlsx|\.pdf\b|print|save as|get the file)\b/i;
  const SKIP = /\b(import|upload|browse|choose file)\b/i;
  const out = [];
  const els = [...document.querySelectorAll('button, [role="button"], a[download], a[href$=".csv"], input[type="button"]')]
    .filter((e) => vis(e) && e.checkVisibility({ opacityProperty: true, visibilityProperty: true }) && !e.disabled);
  for (const e of els) {
    const label = ((e.innerText || '') + ' ' + (e.getAttribute('aria-label') || '') + ' ' + (e.title || '')).replace(/\s+/g, ' ').trim();
    if (!EXPORT.test(label) || SKIP.test(label)) continue;
    const key = label.slice(0, 40);
    if (out.includes(key)) continue;            // one per distinct label: the same handler, not more coverage
    e.setAttribute('data-wh-export', String(out.length));
    out.push(key);
  }
  return out;
};

// how many data rows does the page itself show? the export must not carry fewer
const VISIBLE_ROWS = function rows(VIS_JS) {
  const vis = (0, eval)(VIS_JS);
  const containers = [...document.querySelectorAll('[id$="-list"], [id$="-rows"], tbody, [id$="-feed"]')].filter(vis);
  let best = 0;
  for (const c of containers) best = Math.max(best, [...c.children].filter((k) => vis(k) && (k.innerText || '').trim()).length);
  return best;
};

// the in-page views a press can open (a preview overlay, a sheet, a modal), as one comparable string
const OPEN_VIEWS = function openViews(VIS_JS) {
  const vis = (0, eval)(VIS_JS);
  return [...document.querySelectorAll('[role="dialog"], [aria-modal="true"], dialog[open], .overlay.open, [id$="-overlay"].open, .sheet.open, .modal.open')]
    .filter((e) => vis(e)).map((e) => e.id || String(e.className).slice(0, 30)).sort().join('|');
};
// what the page is saying right now (toasts and live regions)
const TOLD = function told(VIS_JS) {
  const vis = (0, eval)(VIS_JS);
  return [...document.querySelectorAll('[role="alert"], [role="status"], .toast, #toast, [data-wh-toast]')]
    .filter((e) => vis(e) && (e.innerText || '').trim()).map((e) => e.innerText.replace(/\s+/g, ' ').trim().slice(0, 160));
};

// One surface: press each export control the sweep can reach and judge what came of it. A function so the
// self-test runs the SAME judgment on a fixture whose answers are known.
async function surveyPage(ctx, file, url) {
  const p = await ctx.newPage();
  p.on('dialog', async (d) => { await d.dismiss().catch(() => {}); });
  await p.goto(url, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(SETTLE_MS);
  const labels = await p.evaluate(FIND, VIS_JS).catch(() => []);
  const visibleRows = await p.evaluate(VISIBLE_ROWS, VIS_JS).catch(() => 0);
  const issues = [], reported = [];
  let pressed = 0, files = 0;
  for (let i = 0; i < labels.length && i < 5; i++) {
    pressed++;
    const viewsBefore = await p.evaluate(OPEN_VIEWS, VIS_JS).catch(() => '');
    const dl = p.waitForEvent('download', { timeout: 12000 }).catch(() => null);
    const popup = p.waitForEvent('popup', { timeout: 3000 }).catch(() => null);
    // what the page SAID while it worked - a toast can come and go inside the 12 s wait, so it is collected as it shows
    const told = new Set();
    let watching = true;
    const watch = (async () => { while (watching) { const t = await p.evaluate(TOLD, VIS_JS).catch(() => []); t.forEach((x) => told.add(x)); await p.waitForTimeout(300).catch(() => {}); } })();
    await p.evaluate((s2) => { const e = document.querySelector(s2); if (e) e.click(); }, `[data-wh-export="${i}"]`).catch(() => {});
    const d = await dl;
    watching = false; await watch;
    if (!d) {
      const pop = await popup;
      if (pop) {                                                      // opened a view: reported, not failed
        reported.push(`"${labels[i]}" opened a new tab - the file is made from there`);
        await pop.close().catch(() => {}); continue;
      }
      // ★TWO HONEST OUTCOMES THIS LINE USED TO FAIL (2026-10-21). (1) An IN-PAGE view: resume's "Preview & Export"
      // opens its preview overlay, the file is made from inside it - the header above says a gated export is
      // "reported by what it did, not failed", and only a new TAB counted. (2) Nothing to export, SAID: logbook's team
      // view defaults to the last week, the hive had no entries in it, the screen listed none and the page answered
      // "No entries to export." - truthful, and graded as a control that "yields nothing". A press that downloads
      // nothing, opens nothing and SAYS nothing still fails, which is the case the check exists for.
      const viewsAfter = await p.evaluate(OPEN_VIEWS, VIS_JS).catch(() => '');
      if (viewsAfter && viewsAfter !== viewsBefore) {
        reported.push(`"${labels[i]}" opened an in-page view (${viewsAfter.slice(0, 60)}) - the file is made from inside it`);
        await p.keyboard.press('Escape').catch(() => {});
        continue;
      }
      const empty = [...told].find((t) => /\b(no (entries|rows|records|items|data|results)|nothing)\b[^.]{0,40}\bexport/i.test(t));
      if (empty && visibleRows === 0) {
        reported.push(`"${labels[i]}" had nothing to export and said so: "${empty.slice(0, 80)}" (the page lists 0 rows)`);
        continue;
      }
      issues.push(`E1 "${labels[i]}" produced no download and opened nothing in ${12}s`
        + (told.size ? ` (it said: "${[...told][0].slice(0, 60)}")` : ''));
      continue;
    }
    const name = d.suggestedFilename() || '';
    const path = join(OUT, `${file.replace(/\W+/g, '_')}_${i}_${name || 'unnamed'}`);
    await d.saveAs(path).catch(() => {});
    let size = 0; try { size = statSync(path).size; } catch { size = 0; }
    files++;
    if (size <= 0) issues.push(`E2 "${labels[i]}" saved ${name} at 0 bytes`);
    if (!name || /^(download|export|untitled|file)(\.\w+)?$/i.test(name)) issues.push(`E3 "${labels[i]}" is named "${name}" - a filename that says nothing about what it holds`);
    if (/\.(csv|json|txt)$/i.test(name) && size > 0) {
      const text = readFileSync(path, 'utf8');
      const lines = text.split(/\r?\n/).filter((l) => l.trim()).length;
      const dataRows = /\.csv$/i.test(name) ? Math.max(0, lines - 1) : lines;
      if (dataRows === 0) issues.push(`E2 "${labels[i]}" ${name} has a header and no rows`);
      else if (visibleRows > 0 && dataRows < visibleRows) {
        issues.push(`E4 "${labels[i]}" ${name} carries ${dataRows} row(s) while the page shows ${visibleRows} - an export that ships fewer rows than the screen is a cap nobody can see afterwards`);
      }
    }
  }
  await p.close();
  return { labels, issues, reported, pressed, files };
}

try { rmSync(OUT, { recursive: true, force: true }); } catch { /* first run */ }
mkdirSync(OUT, { recursive: true });

const b = await chromium.launch();

if (SELF_TEST) {
  // ★THE JUDGMENT'S TEETH (2026-10-21). This prover was taught two honest outcomes it used to fail - an in-page view,
  // and "nothing to export" said over an empty list. Widening what passes is exactly how a gate goes soft, so the
  // fixture holds one control per known answer and the judgment must grade every one of them that way: the silent
  // control and a claim of "nothing" over a screen that lists entries still fail, and E2 / E3 / E4 each bite their
  // own wrong file. No sign-in: the fixture is a static page on the same local server.
  const CASES = [
    { mode: 'dead', issue: /^E1 .*opened nothing/ },
    { mode: 'view', said: /opened an in-page view/ },
    { mode: 'empty', said: /had nothing to export and said so/ },
    { mode: 'lying', issue: /^E1 .*it said: "No entries to export/ },
    { mode: 'file', files: 1 },
    { mode: 'short', issue: /^E4 / },
    { mode: 'unnamed', issue: /^E3 / },
    { mode: 'zero', issue: /^E2 .*header and no rows/ },
  ];
  const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block', acceptDownloads: true });
  await ctx.addInitScript(ALL_ROWS_DRAWN);
  const fails = [];
  for (const c of CASES) {
    const r = await surveyPage(ctx, `teeth-${c.mode}`, `${SEEDER}/workhive/_fixtures/export-truthful-teeth.html?mode=${c.mode}`);
    const why = [];
    if (r.labels.length !== 1) why.push(`found ${r.labels.length} export control(s), not 1`);
    if (c.issue ? !(r.issues.length === 1 && c.issue.test(r.issues[0])) : r.issues.length) why.push(`issues ${JSON.stringify(r.issues)}`);
    if (c.said ? !r.reported.some((s) => c.said.test(s)) : r.reported.length) why.push(`reported ${JSON.stringify(r.reported)}`);
    if (c.files !== undefined && r.files !== c.files) why.push(`saved ${r.files} file(s), not ${c.files}`);
    if (why.length) fails.push(c.mode);
    console.log(`  ${why.length ? 'BAD' : 'ok '} ${c.mode.padEnd(8)} ${(why.length ? why.join('; ') : (r.issues[0] || r.reported[0] || `${r.files} file(s) saved, no issue`)).slice(0, 170)}`);
  }
  await b.close();
  console.log(fails.length
    ? `FAIL export-truthful self-test - ${fails.join(', ')} graded the wrong way`
    : `self-test OK: ${CASES.length}/${CASES.length} fixture controls graded the known way - a silent control and a claim of "nothing" over a listed screen still fail; E2, E3 and E4 each bite`);
  process.exit(fails.length ? 1 : 0);
}

const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block', acceptDownloads: true });
await ctx.addInitScript(ALL_ROWS_DRAWN);
await assertSignedIn(signIn(ctx));

let bad = 0, n = 0, pressed = 0, files = 0;
const notReached = [];
for (const file of (ONLY ? [ONLY] : (LIST || ROSTER))) {
  n++;
  const r = await surveyPage(ctx, file, `${SEEDER}/workhive/${file}${PAGE_QUERY[file] || ''}`);
  pressed += r.pressed; files += r.files;
  for (const s of r.reported) console.log(`        (reported) ${s}`);
  if (!r.labels.length) notReached.push(file);
  if (r.issues.length) bad++;
  console.log(`  ${r.labels.length ? (r.issues.length ? 'BAD' : 'ok ') : 'n/a'} ${file.padEnd(28)} ${r.labels.length} export control(s)${r.labels.length ? (r.issues.length ? ` · ${r.issues.length} issue(s)` : ' · all produced a truthful artifact') : ' - NOT REACHED: none came on screen'}`);
  for (const s of r.issues.slice(0, ONLY ? 12 : 3)) console.log(`        ${s.slice(0, 165)}`);
}
await b.close();
const scope = n - notReached.length;
console.log(`${bad ? 'FAIL' : 'PASS'} export-truthful - ${scope - bad}/${scope} surfaces produce a truthful, complete artifact from every export control the sweep could reach (${pressed} pressed, ${files} file(s) saved and inspected). ${notReached.length} surface(s) NOT REACHED (${notReached.slice(0, 6).join(', ')}) - unmeasured, not clean.`);
process.exitCode = bad ? 1 : 0;
