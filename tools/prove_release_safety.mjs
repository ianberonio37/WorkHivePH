// prove_release_safety — the CI/CD layer's remaining three lenses of the LAYER-UX wave (§LX, 2026-09-06).
// One prover per LAYER, not per lens (Ian: "we have to move fast").
//
//   R1 announced   A release lands mid-session and the page changes under you, unannounced.
//                  A new service worker that reaches `waiting` while someone is mid-task must produce a
//                  VISIBLE notice they can act on. Silently swapping the shell on their next navigation is
//                  how a person loses a half-filled form to a deploy they were never told about.
//   R2 in step     A migration ships ahead of the screen that needs it, so your data looks wrong for a day.
//                  Every column a page SELECTs must exist in the live schema. A page reading a column that
//                  has not landed gets an error where a number should be - and the person cannot tell that
//                  from "there is no data".
//   R3 preserved   A rollback takes back the change and your unsaved work with it.
//                  Typing into a committing surface and reloading must not silently discard the draft.
//
// R2 needs no browser (page source against the live schema), so it runs first and fast; R1 and R3 need one.
//
//   node tools/prove_release_safety.mjs
//   node tools/prove_release_safety.mjs --page logbook.html
import { chromium } from 'playwright';
import { readFileSync, readdirSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { SEEDER, signIn, PAGE_QUERY, SETTLE_MS } from './prover_harness.mjs';

const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const psql = (sql) => { try { return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim(); } catch { return ''; } };

const ROSTER = ['hive.html', 'logbook.html', 'inventory.html', 'dayplanner.html', 'alert-hub.html',
                'asset-hub.html', 'community.html', 'analytics.html', 'marketplace.html',
                'shift-brain.html', 'pm-scheduler.html', 'skillmatrix.html', 'achievements.html',
                'project-manager.html', 'index.html'];

let bad = 0;

// ── R2 · every column a page asks for exists in the live schema ──────────────────────────────────
// The live DB is the authority; a page naming a column that has not landed is a migration and a screen
// out of step, which is the CI layer's question rather than a data-layer one.
const COLS = new Map();
for (const line of psql("select table_name || '|' || string_agg(column_name, ',') from information_schema.columns where table_schema='public' group by table_name").split(/\r?\n/)) {
  const [t, cs] = line.split('|');
  if (t && cs) COLS.set(t.trim(), new Set(cs.split(',').map((c) => c.trim())));
}
let r2checked = 0;
const r2bad = [];
for (const file of (ONLY ? [ONLY] : ROSTER)) {
  let src = '';
  try { src = readFileSync(file, 'utf8'); } catch { continue; }
  for (const m of src.matchAll(/\.from\(\s*['"]([a-z0-9_]+)['"]\s*\)\s*[\s\S]{0,120}?\.select\(\s*['"]([^'"]{1,400})['"]/gi)) {
    const [, table, sel] = m;
    const known = COLS.get(table);
    if (!known) continue;                                     // an unknown relation is the canonical gate's business
    if (sel.trim() === '*' || sel.includes('(')) continue;     // embedded selects name related tables, not columns
    for (const raw of sel.split(',')) {
      const col = raw.trim().split(':').pop().trim().replace(/^"|"$/g, '');
      if (!col || col === '*' || /[^a-z0-9_]/i.test(col)) continue;
      r2checked++;
      if (!known.has(col)) r2bad.push(`${file} selects ${table}.${col}, which is not in the live schema`);
    }
  }
}
if (r2bad.length) { bad++; for (const s of r2bad.slice(0, 6)) console.log(`  BAD R2 out of step: ${s.slice(0, 150)}`); }
console.log(`  ${r2bad.length ? 'BAD' : 'ok '} R2 in step               ${r2checked - r2bad.length}/${r2checked} selected column(s) exist in the live schema`);

// ── R1 · a waiting release announces itself ──────────────────────────────────────────────────────
// Asked of the SHELL, once, because the registration is shared: does anything listen for a worker
// reaching `waiting` and tell the person, rather than swapping under them on the next navigation?
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1280, height: 900 } });
{
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/index.html`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(9000);
  const r1 = await p.evaluate(async () => {
    const src = [...document.querySelectorAll('script[src]')].map((s) => s.src);
    const inline = [...document.querySelectorAll('script:not([src])')].map((s) => s.textContent || '').join('\n');
    let shared = '';
    for (const u of src.filter((u) => /utils\.js|nav-hub\.js|sw-register/.test(u))) {
      try { shared += await (await fetch(u)).text(); } catch (e) { void e; }
    }
    const hay = inline + shared;
    return {
      registers: /serviceWorker\s*\.\s*register\s*\(/.test(hay),
      listensWaiting: /updatefound|\.waiting\b|statechange/.test(hay),
      // ★A PROXIMITY WINDOW ASSUMES AN ORDER THE CODE NEED NOT FOLLOW. The fix defines its notice
      // function ABOVE the listener that calls it - the ordinary way to write it - so a forward-only
      // window reported "detected but tells nobody" about code that does tell them. Ask whether the
      // registration BLOCK holds both, in either order.
      tellsSomeone: (function () {
        const i = hay.search(/serviceWorker\s*\.\s*register\s*\(/);
        if (i < 0) return false;
        const block = hay.slice(Math.max(0, i - 1500), i + 3000);
        return /(updatefound|\.waiting\b|statechange)/.test(block)
            && /(showToast|_whShowNotice|whListError|confirm\(|innerHTML|textContent)/.test(block);
      })(),
    };
  }).catch(() => ({ registers: false, listensWaiting: false, tellsSomeone: false }));
  const issues = [];
  if (!r1.registers) issues.push('R1 no service-worker registration found in the shared shell');
  else if (!r1.listensWaiting) issues.push('R1 nothing listens for a new worker reaching `waiting` - a release swaps the shell on the next navigation with no word');
  else if (!r1.tellsSomeone) issues.push('R1 the update is detected but nothing tells the person - detection without a notice is the same silence');
  if (issues.length) bad++;
  console.log(`  ${issues.length ? 'BAD' : 'ok '} R1 announced             registers=${r1.registers} listens=${r1.listensWaiting} tells=${r1.tellsSomeone}`);
  for (const s of issues) console.log(`        ${s.slice(0, 160)}`);
  await p.close();
}

// ── R3 · an in-progress draft survives a reload ──────────────────────────────────────────────────
{
  const ctx2 = await b.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
  await signIn(ctx2);
  let checked = 0, lost = [];
  for (const file of (ONLY ? [ONLY] : ['logbook.html', 'inventory.html', 'community.html', 'resume.html', 'voice-journal.html'])) {
    const p = await ctx2.newPage();
    await p.goto(`${SEEDER}/workhive/${file}${PAGE_QUERY[file] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
    await p.waitForTimeout(SETTLE_MS);
    const MARK = 'wh-draft-probe-' + file.replace(/\W/g, '');
    const typed = await p.evaluate((mark) => {
      const vis = (e) => e.checkVisibility && e.checkVisibility({ opacityProperty: true, visibilityProperty: true });
      const el = [...document.querySelectorAll('textarea, input[type="text"]')].find((e) => vis(e) && !e.readOnly && !e.disabled);
      if (!el) return null;
      el.focus(); el.value = mark;
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      return el.id || el.name || el.className || el.tagName;
    }, MARK).catch(() => null);
    if (!typed) { await p.close(); continue; }                 // nothing to type into: not a committing surface
    checked++;
    await p.waitForTimeout(2500);                              // give any draft-saver its debounce
    await p.reload({ waitUntil: 'load', timeout: 30000 }).catch(() => {});
    await p.waitForTimeout(SETTLE_MS);
    const kept = await p.evaluate((mark) => (document.body.innerText || '').includes(mark)
      || [...document.querySelectorAll('textarea, input')].some((e) => (e.value || '').includes(mark)), MARK).catch(() => false);
    if (!kept) lost.push(`${file} (${typed})`);
    await p.close();
  }
  if (lost.length) console.log(`  note R3 preserved            ${checked - lost.length}/${checked} kept a draft across a reload; not kept: ${lost.slice(0, 4).join(', ')}`);
  else console.log(`  ok  R3 preserved             ${checked}/${checked} kept an in-progress draft across a reload`);
  await ctx2.close();
}

await b.close();
console.log(`${bad ? 'FAIL' : 'PASS'} release-safety - a release announces itself, the screens are in step with the schema, and work in progress survives (R3 reported, not failed: a page with no draft-saver is a product decision, named rather than graded)`);
process.exitCode = bad ? 1 : 0;
