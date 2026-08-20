// prove_availability_pages.mjs — the CG availability lens across the 22 product pages.
//
// REUSE, NOT REBUILD: live-state-runner.js already exports availability({settle}), which induces and
// judges five conditions in one pass — offline_refusal, retry_path, rate_limit_legible,
// fallback_engaged, slow_honest. tools/walk_owed_scenarios.mjs drives it for the 4 marketplace
// surfaces; this drives the SAME lens for the product roster, so the two banks cannot disagree about
// what the words mean.
//
// ★THE TRI-STATE IS THE POINT AND IS PRESERVED EXACTLY. The lens returns ok===true (the surface does
// this), ok===false (it does not), or ok===null WITH A NOTE (there was nothing of this kind here to
// judge). That third value must never collapse into either of the others: a page with no fallback has
// not demonstrated a correct fallback, and it has not failed to have one either. It is recorded with
// the lens's own note as its reason.
//
// USAGE:  node tools/prove_availability_pages.mjs [--page <name>]
// OUTPUT: availability_pages_report.json
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'node:url';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();
const PAGES = ['index','hive','logbook','inventory','pm-scheduler','project-manager','dayplanner',
  'asset-hub','analytics','alert-hub','skillmatrix','shift-brain','voice-journal','assistant',
  'community','public-feed','achievements','engineering-design','resume','report-sender',
  'project-report','analytics-report'];
const KEYS = ['offline_refusal','retry_path','rate_limit_legible','fallback_engaged','slow_honest'];

const run = async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await assertSignedIn(signIn(ctx, 'supervisor'));
  const out = { origin: ORIGIN, results: [] };
  for (const name of (ONE ? [ONE] : PAGES)) {
    const rec = { page: name };
    const page = await ctx.newPage();
    try {
      await page.goto(`${ORIGIN}/workhive/${name}.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(3000);
      rec.lens = await page.evaluate(async () => {
        const m = await import('/workhive/live-state-runner.js');
        return await m.availability({ settle: 1500 });
      });
    } catch (e) { rec.error = String(e.message || e).slice(0, 180); }
    await page.close();
    out.results.push(rec);
    const l = rec.lens || {};
    console.log(`  ${name.padEnd(19)} ` + KEYS.map((k) => {
      const r = l[k] || {};
      const v = r.ok === true ? 'PASS' : r.ok === false ? 'FAIL' : r.ok === null ? 'n/a ' : ' ?  ';
      return `${k.split('_')[0].slice(0,5)}:${v}`;
    }).join(' ') + (rec.error ? `  ERR ${rec.error}` : ''));
  }
  await browser.close();
  writeFileSync(path.join(ROOT, 'availability_pages_report.json'), JSON.stringify(out, null, 1));
  const tally = {};
  for (const k of KEYS) tally[k] = { pass: 0, fail: 0, na: 0 };
  for (const r of out.results) for (const k of KEYS) {
    const v = ((r.lens || {})[k] || {}).ok;
    if (v === true) tally[k].pass++; else if (v === false) tally[k].fail++; else if (v === null) tally[k].na++;
  }
  console.log('\n  ' + KEYS.map((k) => `${k}: ${tally[k].pass}P/${tally[k].fail}F/${tally[k].na}n-a`).join('\n  '));
};
run().catch((e) => { console.error(e); process.exit(1); });
