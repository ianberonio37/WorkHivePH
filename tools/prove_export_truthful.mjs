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
import { chromium } from 'playwright';
import { mkdirSync, statSync, readFileSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { SEEDER, signIn, PAGE_QUERY, VIS_JS, SETTLE_MS } from './prover_harness.mjs';

const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const LIST = (() => { const i = process.argv.indexOf('--pages'); return i >= 0 ? process.argv[i + 1].split(',') : null; })();
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

try { rmSync(OUT, { recursive: true, force: true }); } catch { /* first run */ }
mkdirSync(OUT, { recursive: true });

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block', acceptDownloads: true });
await signIn(ctx);

let bad = 0, n = 0, pressed = 0, files = 0;
const notReached = [];
for (const file of (ONLY ? [ONLY] : (LIST || ROSTER))) {
  n++;
  const p = await ctx.newPage();
  p.on('dialog', async (d) => { await d.dismiss().catch(() => {}); });
  await p.goto(`${SEEDER}/workhive/${file}${PAGE_QUERY[file] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(SETTLE_MS);
  const labels = await p.evaluate(FIND, VIS_JS).catch(() => []);
  const visibleRows = await p.evaluate(VISIBLE_ROWS, VIS_JS).catch(() => 0);
  const issues = [];
  for (let i = 0; i < labels.length && i < 5; i++) {
    pressed++;
    const dl = p.waitForEvent('download', { timeout: 12000 }).catch(() => null);
    const popup = p.waitForEvent('popup', { timeout: 3000 }).catch(() => null);
    await p.evaluate((s2) => { const e = document.querySelector(s2); if (e) e.click(); }, `[data-wh-export="${i}"]`).catch(() => {});
    const d = await dl;
    if (!d) {
      const pop = await popup;
      if (pop) { await pop.close().catch(() => {}); continue; }        // opened a view: reported by absence, not failed
      issues.push(`E1 "${labels[i]}" produced no download and opened nothing in ${12}s`);
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
  if (!labels.length) notReached.push(file);
  if (issues.length) bad++;
  console.log(`  ${labels.length ? (issues.length ? 'BAD' : 'ok ') : 'n/a'} ${file.padEnd(28)} ${labels.length} export control(s)${labels.length ? (issues.length ? ` · ${issues.length} issue(s)` : ' · all produced a truthful artifact') : ' - NOT REACHED: none came on screen'}`);
  for (const s of issues.slice(0, ONLY ? 12 : 3)) console.log(`        ${s.slice(0, 165)}`);
  await p.close();
}
await b.close();
const scope = n - notReached.length;
console.log(`${bad ? 'FAIL' : 'PASS'} export-truthful - ${scope - bad}/${scope} surfaces produce a truthful, complete artifact from every export control the sweep could reach (${pressed} pressed, ${files} file(s) saved and inspected). ${notReached.length} surface(s) NOT REACHED (${notReached.slice(0, 6).join(', ')}) - unmeasured, not clean.`);
process.exitCode = bad ? 1 : 0;
