// prove_anchor_back.mjs - OWN "browser Back: anchor jumps do not pollute history" (2026-10-27).
//
// A reader on a public article taps the table of contents, an FAQ link, "back to top" - each in-page jump. Browsers record
// every #fragment jump as a history entry, so after three jumps the reader's Back walks back through the article three
// times before it leaves: trapped by the page's own anchors. The ask: after the jumps, ONE Back leaves the page.
//
// THE INSTRUMENT. Playwright Chromium, signed out (these pages are public), at 390x844 touch and 1280x800. Each walk
// arrives from the site's front page (so Back has a real destination), taps up to three visible in-page links whose
// #target exists on the page, then presses Back once:
//   LEFT       - the browser is on the front page: no history was added by the jumps (pass)
//   TRAPPED    - still on the article (each jump added an entry)
//   NO ANCHORS - the page has no in-page link with a real target: nothing to pollute (pass, recorded as such)
//
//   node tools/prove_anchor_back.mjs [--page learn/what-is-oee-how-to-calculate/index.html] [--resume]  -> anchor_back_report.json
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ORIGIN = 'http://127.0.0.1:5000';
const OUT = path.join(ROOT, 'anchor_back_report.json');
const args = process.argv.slice(2);
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

// the pages the OWN rows name (registry), unless one is asked for
const reg = JSON.parse(readFileSync(path.join(ROOT, 'trajectory_registry.json'), 'utf8'));
const PAGES = ONE ? [ONE] : [...new Set((reg.trajectories || []).filter((r) => r.wave === 'OWN' && r.own && r.own.lens === 'browser Back'
  && r.own.ask === 'anchor jumps do not pollute history').map((r) => r.own.page))].sort();
const urlOf = (p) => '/' + p.replace(/index\.html$/, '');
const VIEWPORTS = [['phone-390', { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true }],
                   ['desktop-1280', { viewport: { width: 1280, height: 800 } }]];

async function walk(browser, page, vpName, vp) {
  const ctx = await browser.newContext({ ...vp, timezoneId: 'Asia/Manila' });
  const pg = await ctx.newPage();
  try {
    await pg.goto(ORIGIN + '/', { waitUntil: 'domcontentloaded' });
    await pg.waitForTimeout(800);
    await pg.goto(ORIGIN + urlOf(page), { waitUntil: 'domcontentloaded' });
    await pg.waitForTimeout(1500);
    // in-page links whose target exists, visible, not the bare "#"
    const hrefs = await pg.evaluate(() => [...document.querySelectorAll('a[href^="#"]')].filter((a) => {
      const h = a.getAttribute('href'); if (!h || h === '#' || h.length < 2) return false;
      let t = null; try { t = document.getElementById(decodeURIComponent(h.slice(1))); } catch (_) { t = null; }
      const r = a.getBoundingClientRect(); const cs = getComputedStyle(a);
      return t && r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none';
    }).map((a) => a.getAttribute('href')));
    const uniq = [...new Set(hrefs)].slice(0, 3);
    if (!uniq.length) return { vp: vpName, shape: 'NO ANCHORS', jumps: 0 };
    const before = await pg.evaluate(() => history.length);
    const keyed = [];
    for (const h of uniq) {
      const loc = pg.locator(`a[href="${h}"]`).filter({ visible: true }).first();
      await loc.scrollIntoViewIfNeeded().catch(() => {});
      // a skip link sits off-screen until it is FOCUSED - it is a keyboard affordance, and a tap at its parked box hits
      // nothing (about/ read "DID NOT LAND" for that reason alone). Anything outside the viewport is activated the way
      // it is reached: focus, then Enter.
      const offscreen = await loc.evaluate((a) => { const r = a.getBoundingClientRect(); return r.bottom <= 0 || r.top >= innerHeight || r.right <= 0 || r.left >= innerWidth; }).catch(() => false);
      if (offscreen) { await loc.focus().catch(() => {}); await pg.keyboard.press('Enter').catch(() => {}); keyed.push(h); }
      else await (vp.hasTouch ? loc.tap({ timeout: 5000 }) : loc.click({ timeout: 5000 })).catch(() => {});
      await pg.waitForTimeout(500);
    }
    const after = await pg.evaluate(() => history.length);
    const hash = await pg.evaluate(() => location.hash);
    // the jump must still LAND: the last target near the top of the viewport and holding focus (the native jump's job)
    const landed = await pg.evaluate((h) => {
      const t = document.getElementById(decodeURIComponent(h.slice(1)));
      if (!t) return false;
      const top = t.getBoundingClientRect().top;
      return top > -40 && top < innerHeight * 0.6 && (document.activeElement === t || t.contains(document.activeElement));
    }, uniq[uniq.length - 1]);
    await pg.goBack({ waitUntil: 'domcontentloaded', timeout: 15000 }).catch(() => {});
    await pg.waitForTimeout(1200);
    const at = new URL(pg.url()).pathname;
    const left = at === '/' || at === '/index.html';
    return { vp: vpName, shape: !left ? 'TRAPPED' : landed ? 'LEFT' : 'DID NOT LAND', jumps: uniq.length, anchors: uniq,
      added: after - before, hash_after_jumps: hash, landed, back_to: at, keyed };
  } catch (e) {
    return { vp: vpName, shape: 'ERROR', error: String(e.message || e).slice(0, 160) };
  } finally { await ctx.close().catch(() => {}); }
}

const browser = await chromium.launch({ headless: true });
const prior = existsSync(OUT) ? JSON.parse(readFileSync(OUT, 'utf8')) : { pages: {} };
// --resume: a page that already PASSED today keeps its reading (a paused walk picks up where it stopped)
const RESUME = args.includes('--resume');
const today = new Date().toISOString().slice(0, 10);
for (const page of PAGES) {
  if (RESUME && prior.pages[page] && prior.pages[page].pass && String(prior.pages[page].ran || '').startsWith(today)) continue;
  const runs = [];
  for (const [n, vp] of VIEWPORTS) runs.push(await walk(browser, page, n, vp));
  const pass = runs.every((r) => r.shape === 'LEFT' || r.shape === 'NO ANCHORS');
  prior.pages[page] = { pass, runs, ran: new Date().toISOString() };
  // written after EVERY page: a walk of 119 pages that dies at page 24 keeps the 24 (2026-10-27 - one did)
  prior.generated = new Date().toISOString(); writeFileSync(OUT, JSON.stringify(prior, null, 1));
  console.log(`${pass ? 'PASS' : 'FAIL'} ${page}: ${runs.map((r) => `${r.vp} ${r.shape}${r.jumps ? ` (${r.jumps} jumps, +${r.added} entries)` : ''}`).join(' | ')}`);
}
await browser.close();
prior.generated = new Date().toISOString();
writeFileSync(OUT, JSON.stringify(prior, null, 1));   // --page re-measures one page INTO the report
const failed = Object.entries(prior.pages).filter(([, v]) => !v.pass).map(([k]) => k);
console.log(failed.length ? `FAIL anchor-back - ${failed.length} of ${Object.keys(prior.pages).length} pages trap the reader` : `PASS anchor-back - ${Object.keys(prior.pages).length} pages`);
process.exitCode = failed.length ? 1 : 0;
