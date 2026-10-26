// prove_back_one_press.mjs - OWN "browser Back" (2026-10-27): one press of the browser's Back leaves the page from any
// state; a sheet or modal closes first and never traps.
//
// THE INSTRUMENT. Playwright at 390x844 (touch - Back is a hardware gesture on a phone), signed in as the row's persona.
// Every walk arrives from a REFERRER (index.html, or a page's own parent) so Back has somewhere real to go.
//   REST   - arrive, press Back once: the browser must be on the referrer.
//   DIALOG - for each real dialog the page can open read-only (role="dialog" markup, opened by its own control):
//            arrive, open it, press Back: the dialog must be closed and the URL still the page's (CLOSED); press Back
//            again: the browser must be on the referrer (no trap). A dialog that Back carries off the page with it
//            (LEFT) is recorded - a clean departure, but not "closes first". An overlay still painted, or a second
//            Back that does not leave, is a defect (ORPHANED / TRAPPED).
//   HUB    - the shared nav-hub panel (role="dialog", phone-width): Back with it open must close it and stay; a second
//            Back must reach the referrer. Then leave through one of its tiles: Back from that page must land here with
//            the panel shut (the tile replaced the hub's entry), and one more Back must reach the referrer - a left-
//            behind entry is a DEAD-PRESS. Recorded on every page. (Before 2026-10-27 the hub held no entry: LEFT.)
//
//   node tools/prove_back_one_press.mjs [--page inventory]   -> back_one_press_report.json
import { chromium } from 'playwright';
import { writeFileSync, readFileSync, existsSync } from 'fs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ORIGIN = 'http://127.0.0.1:5000/workhive';
const OUT = 'back_one_press_report.json';
const args = process.argv.slice(2);
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

// page -> { role, query, dialogs: [[name, opener(css) or fn(string), dialog css]] } - openers read from each page's source
const PAGES = {
  'alert-hub': { role: 'worker', dialogs: [] },
  'analytics': { role: 'supervisor', dialogs: [] },
  'assistant': { role: 'worker', dialogs: [] },
  'index': { role: 'worker', dialogs: [] },
  'inventory': { role: 'worker', dialogs: [['add part', '#btn-add-part', '#part-modal']] },
  'shift-brain': { role: 'worker', dialogs: [] },
  'community': { role: 'supervisor', dialogs: [['composer', '#fab-post', '#composer-overlay']] },
  'project-report': { role: 'supervisor', query: '?project_id=539e0d9a-9ff7-474b-ab03-9254406ca7dc', dialogs: [] },
  'report-sender': { role: 'supervisor', dialogs: [['add recipient', '#add-contact-btn', '#contact-sheet']] },
  'engineering-design': { role: 'solo', dialogs: [] },
  'integrations': { role: 'solo', dialogs: [] },
  'marketplace-seller-profile': { role: 'worker', query: null, dialogs: [] },
  'marketplace': { role: 'worker', dialogs: [['saved searches', '#btn-saved-searches', '#sheet-saved-searches'], ['post a listing', '#fab-post', '#sheet-post']] },
};

const isOpen = (sel) => `(() => { const el = document.querySelector(${JSON.stringify(sel)}); if (!el) return false;
  const cs = getComputedStyle(el); const r = el.getBoundingClientRect();
  if (el.classList.contains('sheet') && !el.classList.contains('open')) return false;
  return cs.display !== 'none' && cs.visibility !== 'hidden' && Number(cs.opacity) > 0.05 && r.width > 4 && r.height > 4 && !el.classList.contains('hidden'); })()`;
const painted = `(() => [...document.querySelectorAll('[role="dialog"], [aria-modal="true"], .sheet.open, .sheet-overlay.open, #wh-hub-panel')]
  .some((el) => { const cs = getComputedStyle(el); const r = el.getBoundingClientRect(); return cs.display !== 'none' && cs.visibility !== 'hidden' && Number(cs.opacity) > 0.05 && r.width * r.height > 0.12 * innerWidth * innerHeight; }))()`;

async function arrive(page, file, query, referrer) {
  await page.goto(`${ORIGIN}/${referrer}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  await page.goto(`${ORIGIN}/${file}.html${query || ''}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);
}
const onPage = (page, file) => page.url().includes(`/${file}.html`);
const onRef = (page, referrer) => page.url().split('?')[0].endsWith(`/${referrer}`);

async function back(page) {
  await page.goBack({ waitUntil: 'domcontentloaded', timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(1500);
}

async function walkPage(browser, file, spec) {
  const out = { page: file, role: spec.role, rest: null, dialogs: [], hub: null };
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, timezoneId: 'Asia/Manila' });
  try {
    await assertSignedIn(signIn(ctx, spec.role));
    const page = await ctx.newPage();
    // a page that is reached with a parameter it needs (the seller profile takes ?seller=<name>)
    let query = spec.query || '';
    if (file === 'marketplace-seller-profile' && !query) {
      await page.goto(`${ORIGIN}/marketplace.html`, { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(2500);
      const href = await page.evaluate(() => { const a = [...document.querySelectorAll('a[href*="marketplace-seller-profile.html"]')][0]; return a ? a.getAttribute('href') : null; });
      query = href && href.includes('?') ? '?' + href.split('?')[1] : '';
      out.query = query || '(no seller link on the marketplace to follow)';
    }
    const referrer = 'index.html';
    // REST
    if (file === 'index') {
      await page.goto(`${ORIGIN}/hive.html`, { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(1200);
      await page.goto(`${ORIGIN}/index.html`, { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(3000);
      await back(page);
      out.rest = { left: page.url().includes('/hive.html'), url: page.url().replace(ORIGIN, '') };
    } else {
      await arrive(page, file, query, referrer);
      out.arrived = onPage(page, file);
      await back(page);
      out.rest = { left: onRef(page, referrer), url: page.url().replace(ORIGIN, '') };
    }
    const ref2 = file === 'index' ? 'hive.html' : referrer;
    // DIALOGS
    for (const [name, opener, sel] of spec.dialogs) {
      const d = { name };
      if (file === 'index') { await page.goto(`${ORIGIN}/hive.html`); await page.waitForTimeout(1000); await page.goto(`${ORIGIN}/index.html`); await page.waitForTimeout(3000); }
      else await arrive(page, file, query, referrer);
      if (opener.startsWith('fn:')) await page.evaluate((f) => { if (typeof window[f] === 'function') window[f](); }, opener.slice(3));
      else await page.click(opener, { timeout: 5000 }).catch(() => {});
      await page.waitForTimeout(1000);
      d.opened = await page.evaluate(isOpen(sel));
      if (!d.opened) { d.shape = 'UNGRADED'; d.why = 'the dialog did not open read-only'; out.dialogs.push(d); continue; }
      await back(page);
      const stillOpen = onPage(page, file) ? await page.evaluate(isOpen(sel)) : false;
      if (onPage(page, file) && !stillOpen) {
        await back(page);
        d.shape = onRef(page, ref2) ? 'CLOSED then LEFT' : 'TRAPPED';
      } else if (onPage(page, file) && stillOpen) {
        d.shape = 'TRAPPED';
      } else {
        d.shape = (await page.evaluate(painted)) ? 'ORPHANED' : 'LEFT';
      }
      out.dialogs.push(d);
    }
    // HUB
    if (file === 'index') { await page.goto(`${ORIGIN}/hive.html`); await page.waitForTimeout(1000); await page.goto(`${ORIGIN}/index.html`); await page.waitForTimeout(3000); }
    else await arrive(page, file, query, referrer);
    const fab = await page.$('#wh-hub-fab');
    if (fab) {
      await fab.click().catch(() => {}); await page.waitForTimeout(900);
      const hubOpen = await page.evaluate(isOpen('#wh-hub-panel'));
      await back(page);
      let shape = onPage(page, file)
        ? ((await page.evaluate(isOpen('#wh-hub-panel'))) ? 'TRAPPED' : 'CLOSED')
        : ((await page.evaluate(painted)) ? 'ORPHANED' : 'LEFT');
      if (shape === 'CLOSED') { await back(page); shape = onRef(page, ref2) ? 'CLOSED then LEFT' : 'TRAPPED'; }
      out.hub = { opened: hubOpen, shape };
      // HUB TILE - leave through a hub tile with the panel open; Back from there must land on this page with the panel
      // shut (the hub's entry was replaced, not left behind), and one more Back must reach the referrer
      if (file === 'index') { await page.goto(`${ORIGIN}/hive.html`); await page.waitForTimeout(1000); await page.goto(`${ORIGIN}/index.html`); await page.waitForTimeout(3000); }
      else await arrive(page, file, query, referrer);
      await page.click('#wh-hub-fab').catch(() => {}); await page.waitForTimeout(900);
      const tile = await page.evaluate((f) => {
        const a = [...document.querySelectorAll('#wh-hub-panel a[href]')].find((x) => { const h = x.getAttribute('href') || '';
          const r = x.getBoundingClientRect(); return /^[a-z-]+\.html$/.test(h) && !h.startsWith(f + '.') && h !== 'index.html' && r.width > 0 && r.height > 0; });
        return a ? a.getAttribute('href') : null; }, file);
      if (tile) {
        await page.click(`#wh-hub-panel a[href="${tile}"]`).catch(() => {});
        await page.waitForURL((u) => u.toString().includes('/' + tile), { timeout: 15000 }).catch(() => {});
        await page.waitForTimeout(1500);
        const went = page.url().includes('/' + tile);
        await back(page);
        const backOn = onPage(page, file), panelShut = backOn ? !(await page.evaluate(isOpen('#wh-hub-panel'))) : null;
        await back(page);
        const then = onRef(page, ref2);
        out.hubTile = { tile, went, backOnPage: backOn, panelShut, thenLeft: then,
          shape: went && backOn && panelShut && then ? 'REPLACED' : !went ? 'UNGRADED' : 'DEAD-PRESS' };
      } else out.hubTile = { shape: 'UNGRADED', why: 'no visible page tile in the hub' };
    } else out.hub = { opened: false, shape: 'no hub on this page' };
    out.pass = !!(out.rest && out.rest.left) && out.dialogs.every((d) => ['CLOSED then LEFT', 'UNGRADED'].includes(d.shape))
      && ['CLOSED then LEFT', 'no hub on this page'].includes(out.hub && out.hub.shape)
      && (!out.hubTile || ['REPLACED', 'UNGRADED'].includes(out.hubTile.shape));
    return out;
  } finally { await ctx.close().catch(() => {}); }
}

const browser = await chromium.launch({ headless: true });
const prior = existsSync(OUT) ? JSON.parse(readFileSync(OUT, 'utf8')) : { pages: {} };
for (const [file, spec] of Object.entries(PAGES)) {
  if (ONE && ONE !== file) continue;
  let r;
  try { r = await walkPage(browser, file, spec); } catch (e) { r = { page: file, error: String(e.message || e).slice(0, 200), pass: false }; }
  prior.pages[file] = { ...r, ran: new Date().toISOString() };
  console.log(`${file}: ${r.pass ? 'PASS' : 'FAIL'} rest=${r.rest ? (r.rest.left ? 'left' : 'stayed ' + r.rest.url) : '-'} dialogs=${(r.dialogs || []).map((d) => `${d.name}:${d.shape}`).join(', ') || 'none read-only'} hub=${r.hub ? r.hub.shape : "-"} tile=${r.hubTile ? r.hubTile.shape + (r.hubTile.tile ? "(" + r.hubTile.tile + ")" : "") : "-"}${r.error ? ' ERR ' + r.error : ''}`);
}
prior.generated = new Date().toISOString();
writeFileSync(OUT, JSON.stringify(prior, null, 1));
await browser.close();
const failed = Object.values(prior.pages).filter((p) => !p.pass).map((p) => p.page);
console.log(failed.length ? `FAIL back-one-press - ${failed.join(', ')}` : `PASS back-one-press - ${Object.keys(prior.pages).length} pages`);
process.exitCode = failed.length ? 1 : 0;
