// prove_public_journeys.mjs - SL sub-layer CI2, the public half (2026-10-15): "The platform must keep a live journey
// on this page that passes in Chromium and in WebKit."
//
// A public page's reader arrives signed out, from a search, and has one job: read what the page says and go on to the
// surface it points at. That journey, walked as that reader in both engines (a fresh context each, service workers
// blocked so every step is the network's answer):
//   arrive     the page answers 200 and paints its <h1>; its <main> carries readable text (a learn article or a
//              calculator at least 150 words, a directory page at least 30)
//   example    a calculator page shows its worked example: a result table of at least two rows, every row a label and
//              a value
//   answer     where the page has a FAQ, the first question opens when pressed and shows its answer
//   go on      the page's first onward link inside <main> to a WorkHive surface (a call to action first, else the first
//              in-site link) is CLICKED, as a person would, and the destination answers under 400 with a title and an
//              <h1> or a sign-in form - never a 404, never a blank page
// The app pages' journeys are tools/live_page_journeys.mjs's registry (run with --engine webkit for the second engine);
// tools/prove_page_journeys.py reads both into the CI2 rows.
// TEETH (every run, both engines): a planted page with no <h1>, an empty <main> and an onward link to a missing page
// must fail arrive AND go on; its clean twin must pass.
//
//   node tools/prove_public_journeys.mjs [--pages a,b] [--engine chromium|webkit]
import { chromium, webkit } from 'playwright';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { SEEDER } from './prover_harness.mjs';
import { takeBrowserSlot } from './browser_slot.mjs';

const arg = (k) => { const i = process.argv.indexOf(k); return i >= 0 ? process.argv[i + 1] : null; };
const LIST = arg('--pages') ? arg('--pages').split(',') : null;
const ENGINES = arg('--engine') ? [arg('--engine')] : ['chromium', 'webkit'];
const REG = JSON.parse(readFileSync('trajectory_registry.json', 'utf8'));
const CI2 = new Map();
for (const t of REG.trajectories) if (t.sl && t.sl.sublayer === 'CI2' && t.status !== 'descoped' && t.sl.page_class === 'public') CI2.set(t.sl.page, t);
const PAGES = (LIST || [...CI2.keys()].sort()).filter((f) => existsSync(f));
const KIND = (f) => (/^learn\/.+\/index\.html$/.test(f) && f !== 'learn/index.html' ? 'article'
  : /^tools\/[^/]*calculator[^/]*\/index\.html$/.test(f) ? 'calculator' : 'directory');
const MIN_WORDS = { article: 150, calculator: 150, directory: 30 };
// the served path of a file - directory pages are served at /<dir> (vercel.json cleanUrls false, trailingSlash false)
const served = (f) => `${SEEDER}/workhive/${f}`;

async function walk(ctx, url, kind) {
  const page = await ctx.newPage();
  const steps = {}, problems = [];
  try {
    const resp = await page.goto(url, { waitUntil: 'load', timeout: 45000 }).catch((e) => ({ status: () => 0, err: e }));
    await page.waitForTimeout(1500);
    const status = resp && typeof resp.status === 'function' ? resp.status() : 0;
    const read = await page.evaluate(() => {
      const vis = (e) => !!e && (typeof e.checkVisibility === 'function' ? e.checkVisibility({ visibilityProperty: true }) : e.offsetParent !== null);
      const h1 = [...document.querySelectorAll('h1')].find(vis);
      const main = document.querySelector('main') || document.body;
      const words = (main.innerText || '').split(/\s+/).filter((w) => /[A-Za-z]{2,}/.test(w)).length;
      const rows = [...main.querySelectorAll('table tr')].filter((tr) => vis(tr) && tr.querySelectorAll('td, th').length >= 2
        && [...tr.querySelectorAll('td')].some((td) => /\d/.test(td.textContent))).length;
      const faq = !!main.querySelector('details > summary');
      // the onward link: a call to action first, else the first in-site link in <main>
      const inSite = [...main.querySelectorAll('a[href]')].filter((a) => vis(a)).filter((a) => { const h = a.getAttribute('href') || '';
        if (/^(#|mailto:|tel:|javascript:)/i.test(h)) return false; try { const u = new URL(h, location.href); return u.origin === location.origin; } catch (e) { return false; } });
      const cta = inSite.find((a) => /\bcta\b|btn|button/i.test(a.className) || /^(open|try|start|see|use|read)\b/i.test((a.textContent || '').trim())) || inSite[0];
      if (cta) cta.setAttribute('data-ci2-onward', '1');
      return { h1: h1 ? h1.textContent.trim().slice(0, 60) : null, words, rows, faq, onward: cta ? { href: cta.getAttribute('href'), text: (cta.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 50) } : null };
    });
    steps.arrive = { status, h1: read.h1, words: read.words };
    if (status !== 200) problems.push(`arrive: answered ${status}`);
    if (!read.h1) problems.push('arrive: no visible <h1>');
    if (read.words < MIN_WORDS[kind]) problems.push(`arrive: <main> carries ${read.words} words (a ${kind} needs ${MIN_WORDS[kind]})`);
    if (kind === 'calculator') {
      steps.example = { rows: read.rows };
      if (read.rows < 2) problems.push(`example: the worked example shows ${read.rows} result row(s)`);
    }
    if (read.faq) {
      const sum = page.locator('main details > summary').first();
      await sum.scrollIntoViewIfNeeded().catch(() => {});
      await sum.click({ timeout: 5000 }).catch(() => {});
      await page.waitForTimeout(300);
      const open = await page.evaluate(() => { const d = document.querySelector('main details'); if (!d || !d.open) return false;
        const body = [...d.children].filter((c) => c.tagName !== 'SUMMARY').map((c) => c.innerText || '').join(' ').trim(); return body.length > 20; });
      steps.answer = { opened: open };
      if (!open) problems.push('answer: the first FAQ question did not open onto its answer');
    }
    if (!read.onward) problems.push('go on: no onward link to a WorkHive surface in <main>');
    else {
      const onward = page.locator('[data-ci2-onward="1"]').first();
      await onward.scrollIntoViewIfNeeded().catch(() => {});
      const navResp = await Promise.all([
        page.waitForNavigation({ waitUntil: 'load', timeout: 30000 }).catch(() => null),
        onward.click({ timeout: 8000 }).catch(() => null),
      ]).then((r) => r[0]);
      await page.waitForTimeout(1500);
      const st = navResp ? navResp.status() : 0;
      const dest = await page.evaluate(() => ({ url: location.pathname + location.search, title: document.title.trim(),
        h1: !!document.querySelector('h1'), signin: !!document.querySelector('input[type="password"], [id*="signin" i], [class*="sign-in" i]') }));
      steps.go_on = { from: read.onward, status: st, to: dest.url, title: dest.title.slice(0, 60) };
      if (!navResp) problems.push(`go on: pressing "${read.onward.text}" did not navigate`);
      else if (st >= 400 || st === 0) problems.push(`go on: "${read.onward.text}" -> ${dest.url} answered ${st}`);
      else if (!dest.title || !(dest.h1 || dest.signin)) problems.push(`go on: "${read.onward.text}" -> ${dest.url} painted no title and no <h1> or sign-in`);
    }
  } catch (e) {
    problems.push('walk threw: ' + String(e && e.message || e).slice(0, 140));
  }
  await page.close().catch(() => {});
  return { steps, problems };
}

const SLOP = '<!doctype html><html lang="en"><head><title>x</title></head><body><main><p>Hi.</p><a href="/workhive/__ci2_missing_page.html">Open the tool</a></main></body></html>';
const CLEAN = '<!doctype html><html lang="en"><head><title>Guide</title></head><body><main><h1>A guide</h1><p>'
  + 'Maintenance teams read this guide to plan their week and record what they did on every machine they touched. '.repeat(4)
  + '</p><details><summary>What is it?</summary><p>An answer long enough to be read as one by a person.</p></details><a href="/workhive/about/index.html">Open the about page</a></main></body></html>';

await takeBrowserSlot('public-journeys');
const results = [], teeth = {};
for (const engine of ENGINES) {
  const browser = await (engine === 'webkit' ? webkit : chromium).launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, serviceWorkers: 'block', locale: 'en-PH' });
  for (const [k, html] of [['slop', SLOP], ['clean', CLEAN]]) await ctx.route(`${SEEDER}/workhive/__ci2_teeth_${k}.html`, (r) => r.fulfill({ status: 200, contentType: 'text/html', body: html }));
  const s = await walk(ctx, `${SEEDER}/workhive/__ci2_teeth_slop.html`, 'article');
  const c = await walk(ctx, `${SEEDER}/workhive/__ci2_teeth_clean.html`, 'directory');
  teeth[engine] = { slop: s.problems, clean: c.problems,
    bit: s.problems.some((p) => p.startsWith('arrive')) && s.problems.some((p) => p.startsWith('go on')) && c.problems.length === 0 };
  console.log(`  [${engine}] teeth - a page with no <h1>, an empty <main> and a link to a missing page: ${teeth[engine].bit ? 'CAUGHT' : 'NOT CAUGHT'} (slop ${s.problems.length} problem(s); clean twin ${c.problems.length ? JSON.stringify(c.problems) : '0'})`);
  for (const f of PAGES) {
    const kind = KIND(f);
    const r = await walk(ctx, served(f), kind);
    results.push({ page: f, kind, engine, condition: 'journey', as: 'signed out', steps: r.steps, problems: r.problems, ok: !r.problems.length });
    console.log(`  ${r.problems.length ? 'open' : 'ok  '} [${engine}] ${f.padEnd(60)} ${r.problems.length ? r.problems.join('; ').slice(0, 160) : `${r.steps.arrive.words} words${r.steps.example ? ', ' + r.steps.example.rows + ' rows' : ''}${r.steps.answer ? ', FAQ opens' : ''} -> ${(r.steps.go_on || {}).to || ''}`}`);
  }
  await browser.close();
}
mkdirSync('.tmp', { recursive: true });
const OUT = '.tmp/public_journeys_results.json';
const prev = LIST && existsSync(OUT) ? JSON.parse(readFileSync(OUT, 'utf8')) : null;
const merged = prev ? [...prev.results.filter((r) => !(PAGES.includes(r.page) && ENGINES.includes(r.engine))), ...results] : results;
writeFileSync(OUT, JSON.stringify({ generated: new Date().toISOString(), sublayer: 'CI2', engines: ENGINES, teeth, results: merged }, null, 1) + '\n');
const bad = results.filter((r) => !r.ok).length;
const bit = Object.values(teeth).every((t) => t.bit);
console.log(`\n${bad || !bit ? 'FAIL' : 'PASS'} public-journeys - ${results.length - bad}/${results.length} page-engine walk(s) arrive, read, answer and go on${bit ? '' : '; teeth did not bite'} -> ${OUT}`);
process.exit(bad || !bit ? 1 : 0);
