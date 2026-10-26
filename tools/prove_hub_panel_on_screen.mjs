// prove_hub_panel_on_screen.mjs — §BRH.11 AN: the hub's opened panel is wholly inside the viewport, wherever the
// FAB rests (Ian, 2026-10-26: "when you open or tap it it becomes invisible when opened ... when you put it at the
// top, all of it is being swallowed at the top, it is not the same in iOS that it will also adjust").
//
// WHAT IS MEASURED, PER (engine, viewport, page, case):
//   rest  the FAB where a fresh device leaves it (no stored position) -> open -> the panel's rect
//   top   the FAB planted at the top of the screen (localStorage wh-hub-position, the same key the drag writes)
//         -> reload -> open -> the panel's rect. This is the reproduction Ian met: before the fix the panel grew
//         upward from a bottom anchor and its body sat above the viewport with a sliver showing.
//   A case passes when every edge of #wh-hub-panel is inside the viewport AND document.elementFromPoint at the
//   centre of the panel's first row resolves to something inside the panel (the header is not covered or clipped).
//   The read is taken after the open transition settles (0.2s in nav-hub.js; 400ms here), never at the start.
//
// ENGINES: chromium by default; `--engine webkit` runs Playwright's WebKit (webkit-2287 is installed), the engine
// that bit Ian - the SL convention for AV1/CI2 cells. The verdicts carry the engine so the report cannot blur them.
//
//   node tools/prove_hub_panel_on_screen.mjs                     # chromium, the default hosts, both viewports
//   node tools/prove_hub_panel_on_screen.mjs --engine webkit
//   node tools/prove_hub_panel_on_screen.mjs --pages hive.html,logbook.html --anon
//
// Writes hub_panel_on_screen_report.json (merging engines: a webkit run keeps the chromium rows and vice versa) and
// exits 1 when any case fails. tools/validate_hub_panel_on_screen.py reads the report and holds nav-hub.js to it.
import { chromium, webkit } from 'playwright';
import { createHash } from 'crypto';
import { existsSync, readFileSync, writeFileSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'node:url';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const REPORT = path.join(ROOT, 'hub_panel_on_screen_report.json');
const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const flag = (name, dflt) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : dflt; };
const ENGINE = flag('--engine', 'chromium');
const PAGES = flag('--pages', 'hive.html,logbook.html,analytics.html,index.html').split(',').filter(Boolean);
const ANON = args.includes('--anon');
const ROLE = flag('--role', 'supervisor');   // the signed-in cast; a host that refuses it bounces, and a bounce fails the case
const VIEWPORTS = [{ name: 'phone-390', width: 390, height: 844 }, { name: 'desktop-1280', width: 1280, height: 800 }];
const SETTLE_MS = 2500;        // the ceiling for the open transition to settle (0.2s in nav-hub.js; WebKit under a 29-host sweep is slower)
const NAV_TIMEOUT = 45000;

// ★THE WATCHDOG SCALES WITH THE SWEEP. The first all-hosts WebKit run (29 hosts x 2 viewports x 3 cases) was cut at a
// fixed 600s with 151 verdicts banked and the rest never read - a budget borrowed from the 4-host default. Derived from
// THIS run's own size: ~12s worst case per case, plus two minutes of sign-in and launch.
const WATCHDOG_MS = Math.max(600_000, PAGES.length * VIEWPORTS.length * 3 * 12_000 + 120_000);
setTimeout(() => {
  console.error(`WATCHDOG: exceeded ${WATCHDOG_MS}ms without finishing -- treating as HUNG, not slow.`);
  process.exit(3);
}, WATCHDOG_MS).unref();
// the hub's own stand-down rule (nav-hub.js standDownWhileDialogOpen): while a dialog is up, page-level chrome hides
const DIALOGISH = '[role="dialog"],dialog[open],.sheet.open,.modal.open,[id$="-sheet"].open,[id$="-modal"].open,.sheet-overlay.open';

const navHubSha = createHash('sha256').update(readFileSync(path.join(ROOT, 'nav-hub.js'))).digest('hex').slice(0, 12);

async function openAndMeasure(page, expectedPage) {
  await page.waitForSelector('#wh-hub-fab', { state: 'attached', timeout: 15000 });
  await page.waitForTimeout(300);                         // loadSavedPosition + the stack lift have run
  // a host that refuses this cast bounces to the landing or a sign-in door: measuring the hub THERE would credit the
  // host with a panel it never showed, so the case fails and names where the walk actually landed
  const here = await page.evaluate(() => (location.pathname.split('/').pop() || 'index.html') + location.search);
  if (expectedPage && here.split('?')[0] !== expectedPage) {
    return { ok: false, why: `bounced to ${here} - this cast is refused by ${expectedPage}; re-run with --role <admitted cast>` };
  }
  // ★A DIALOG UP AT LOAD MEANS THE HUB STANDS DOWN BY DESIGN (nav-hub.js standDownWhileDialogOpen): #wh-hub is
  // visibility:hidden while any dialog-shaped element is visible, so there is no panel to measure and no defect in it.
  // The first all-hosts sweep read those as "panel did not open"; the verdict is recorded as its own kind instead.
  const standdown = await page.evaluate((sel) => {
    const hub = document.getElementById('wh-hub');
    if (!hub) return null;
    const cs = getComputedStyle(hub);
    if (cs.visibility !== 'hidden' && cs.display !== 'none') return null;
    const vis = (el) => { const c = getComputedStyle(el); if (c.display === 'none' || c.visibility === 'hidden') return false; const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    const dlg = Array.from(document.querySelectorAll(sel)).find(vis);
    return dlg ? (dlg.id ? '#' + dlg.id : dlg.className || dlg.tagName) : 'hub hidden with no visible dialog';
  }, DIALOGISH);
  if (standdown && standdown !== 'hub hidden with no visible dialog') {
    return { ok: true, standdown, why: '', note: `the hub stands down behind ${standdown} at load (by design); the panel is not measurable here` };
  }
  await page.evaluate(() => document.getElementById('wh-hub-fab').click());
  // read AFTER the open transition settles, never at its start (the first sweep took a fixed 400ms and misread slow WebKit opens)
  await page.waitForFunction(() => {
    const p = document.getElementById('wh-hub-panel');
    if (!p) return false;
    const cs = getComputedStyle(p);
    return p.classList.contains('open') && cs.visibility === 'visible' && parseFloat(cs.opacity) > 0.9;
  }, null, { timeout: SETTLE_MS }).catch(() => {});
  await page.waitForTimeout(120);
  return page.evaluate(() => {
    const panel = document.getElementById('wh-hub-panel');
    const fab = document.getElementById('wh-hub-fab');
    const vw = window.innerWidth, vh = window.innerHeight;
    if (!panel || !fab) return { ok: false, why: 'no #wh-hub-panel / #wh-hub-fab on the page' };
    const r = panel.getBoundingClientRect();
    const f = fab.getBoundingClientRect();
    const cs = getComputedStyle(panel);
    const open = panel.classList.contains('open') && cs.visibility === 'visible' && parseFloat(cs.opacity) > 0.9;
    const first = panel.firstElementChild;
    const fr = first ? first.getBoundingClientRect() : r;
    const px = Math.round(fr.left + fr.width / 2), py = Math.round(fr.top + Math.min(fr.height / 2, 20));
    const hit = document.elementFromPoint(px, py);
    const hitInside = !!(hit && panel.contains(hit));
    const inside = r.top >= 0 && r.left >= 0 && r.bottom <= vh + 0.5 && r.right <= vw + 0.5;
    const why = [];
    if (!open) why.push('panel did not open (class/visibility/opacity)');
    if (r.top < 0) why.push(`top edge ${Math.round(r.top)}px above the viewport`);
    if (r.bottom > vh + 0.5) why.push(`bottom edge ${Math.round(r.bottom - vh)}px below the viewport`);
    if (r.left < 0 || r.right > vw + 0.5) why.push('a side edge is off the viewport');
    if (!hitInside) why.push(`elementFromPoint(${px},${py}) is ${hit ? (hit.id || hit.tagName) : 'nothing'}, not the panel`);
    return {
      ok: open && inside && hitInside, why: why.join('; '),
      panel: { top: Math.round(r.top), bottom: Math.round(r.bottom), left: Math.round(r.left), right: Math.round(r.right), height: Math.round(r.height) },
      fab: { top: Math.round(f.top), bottom: Math.round(f.bottom) },
      below: document.getElementById('wh-hub').classList.contains('wh-panel-below'),
      viewport: { width: vw, height: vh },
    };
  });
}

async function main() {
  const launcher = ENGINE === 'webkit' ? webkit : chromium;
  const browser = await launcher.launch();
  const cases = [];
  try {
    for (const vp of VIEWPORTS) {
      const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
      if (!ANON) await assertSignedIn(signIn(ctx, ROLE));
      for (const pg of PAGES) {
        for (const kind of ['rest', 'top', 'install']) {
          const page = await ctx.newPage();
          const row = { engine: ENGINE, viewport: vp.name, page: pg, case: kind };
          try {
            await page.goto(`${ORIGIN}/${pg}`, { waitUntil: 'domcontentloaded', timeout: NAV_TIMEOUT });
            if (kind === 'top') {
              // the drag's own key and shape, planted where a person who dragged the FAB to the top leaves it
              await page.evaluate(() => localStorage.setItem('wh-hub-position',
                JSON.stringify({ side: 'right', bottom: window.innerHeight - 80 })));
              await page.reload({ waitUntil: 'domcontentloaded', timeout: NAV_TIMEOUT });
            } else {
              await page.evaluate(() => localStorage.removeItem('wh-hub-position'));
              await page.reload({ waitUntil: 'domcontentloaded', timeout: NAV_TIMEOUT });
            }
            Object.assign(row, await openAndMeasure(page, pg));
            if (kind === 'install' && row.ok && !row.standdown) {
              // §BRH.11 AM: with the hub open, the install control is visible at rest (no beforeinstallprompt needed -
              // headless browsers never fire it), and a tap shows the per-platform guide inside the still-on-screen panel
              Object.assign(row, await page.evaluate(async () => {
                const b = document.getElementById('wh-hub-install');
                const panel = document.getElementById('wh-hub-panel');
                if (!b) return { ok: false, why: 'no #wh-hub-install control in the hub' };
                const br = b.getBoundingClientRect();
                const visible = b.offsetParent !== null && br.width > 0 && br.height >= 44 && br.top >= 0 && br.bottom <= window.innerHeight;
                b.click();
                await new Promise(r => setTimeout(r, 450));
                const g = document.getElementById('wh-hub-install-guide');
                const shown = !!(g && !g.hidden && g.textContent.trim().length > 20 && g.querySelector('img'));
                const pr = panel.getBoundingClientRect();
                const inside = pr.top >= 0 && pr.bottom <= window.innerHeight + 0.5;
                const why = [];
                if (!visible) why.push(`install control not visible at rest (h ${Math.round(br.height)}, top ${Math.round(br.top)})`);
                if (!shown) why.push('tapping it showed no guide with the icon');
                if (!inside) why.push(`panel left the viewport after the guide opened (${Math.round(pr.top)}..${Math.round(pr.bottom)})`);
                return { ok: visible && shown && inside, why: why.join('; '), install: { height: Math.round(br.height), guide: shown } };
              }));
            }
          } catch (e) {
            Object.assign(row, { ok: false, why: `probe error: ${String(e.message || e).slice(0, 160)}` });
          } finally {
            await page.close().catch(() => {});
          }
          cases.push(row);
          console.log(`${row.ok ? (row.standdown ? 'STANDDOWN' : 'PASS') : 'FAIL'} ${ENGINE} ${vp.name} ${pg} ${kind}` +
            (row.panel ? ` panel ${row.panel.top}..${row.panel.bottom} of ${row.viewport.height}${row.below ? ' (below the FAB)' : ''}` : '') +
            (row.standdown ? ` - ${row.note}` : '') +
            (row.ok ? '' : ` - ${row.why}`));
        }
      }
      await ctx.close();
    }
  } finally {
    await browser.close().catch(() => {});
  }
  // merge: keep every row this run did not re-measure - the other engine's rows, and this engine's rows for pages
  // outside --pages (a one-page re-run after a flaky load must not wipe the other 28 hosts' verdicts)
  let prior = [];
  if (existsSync(REPORT)) {
    try {
      prior = (JSON.parse(readFileSync(REPORT, 'utf8')).cases || []).filter(c => c.engine !== ENGINE || !PAGES.includes(c.page));
    } catch (_) { prior = []; }
  }
  const all = prior.concat(cases);
  const report = {
    _doc: 'hub-panel-on-screen (§BRH.11 AN): the opened nav-hub panel is wholly inside the viewport with its header hit-testable, at rest and with the FAB planted at the top; tools/prove_hub_panel_on_screen.mjs',
    at: new Date().toISOString(), origin: ORIGIN, nav_hub_sha: navHubSha,
    pass: all.filter(c => c.ok).length, fail: all.filter(c => !c.ok).length, cases: all,
  };
  writeFileSync(REPORT, JSON.stringify(report, null, 1) + '\n');
  console.log(`\n${report.pass} pass · ${report.fail} fail (this run: ${cases.filter(c => c.ok).length}/${cases.length}) -> ${path.basename(REPORT)} (nav-hub.js ${navHubSha})`);
  process.exit(cases.some(c => !c.ok) ? 1 : 0);
}

main().catch(e => { console.error(e); process.exit(2); });
