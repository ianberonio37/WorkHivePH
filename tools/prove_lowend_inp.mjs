// prove_lowend_inp.mjs - OWN "low-end phone" (2026-10-27): the primary action's INP stays within budget at 390 with the
// CPU throttled 4x.
//
// THE INSTRUMENT. Chromium at 390x844 (mobile, touch, dpr 3), signed in as the row's persona, the CPU slowed 4x with
// Emulation.setCPUThrottlingRate over a CDP session - and the throttle proves itself: a fixed loop is timed JIT-warm before
// and after the call, and a ratio under 2.5 fails the run (a throttle that did not apply would report a fast phone).
// Each page is loaded fresh ROUNDS times; each round waits for the page to settle, then TAPS its primary control for
// real (page.tap - a trusted touch, which Event Timing times; a script .click() is not timed at all, which is why the
// journeys' own drives could not measure four of these pages). The interaction's duration is read from an Event Timing
// observer installed before any page script (durationThreshold 16, the API's floor). A tap that was received (a trusted
// pointerdown counted) but produced no entry was faster than 16 ms - within budget, recorded as "<16". A tap that was
// never received is UNGRADED, never a pass. INP here = the slowest round; budget 200 ms (web.dev "good").
//
//   node tools/prove_lowend_inp.mjs [--page inventory]   -> lowend_inp_report.json
import { chromium } from 'playwright';
import { writeFileSync, readFileSync, existsSync } from 'fs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ORIGIN = 'http://127.0.0.1:5000/workhive';
const OUT = 'lowend_inp_report.json';
const CPU = 4, BUDGET = 200, ROUNDS = 3, MIN_RATIO = 2.5;
const args = process.argv.slice(2);
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();
// --teeth: every trusted pointerdown does a fixed amount of WORK (~60 ms unthrottled, so ~250 ms+ at 4x) - the run must read
// OVER and fail. Work, not a wall-clock spin: `while (now - t < 80)` stops after 80 ms of real time whatever the throttle,
// which is how the first teeth run passed at 176 ms.
const TEETH = args.includes('--teeth');

// page -> [role, the primary control (first visible match), what the tap does]
const PAGES = {
  'index': ['worker', '#ops-home details > summary, #ops-home summary', "expands the home's More (My Open Jobs + All Tools)"],
  'integrations': ['solo', '#veh-open', 'opens Add my vehicle'],
  'inventory': ['worker', '#btn-add-part', 'opens Add Part'],
  'marketplace-seller': ['worker', "button[data-action='edit']", "opens a listing's Edit form"],
  'plant-connections': ['supervisor', '#details-toggle-btn', 'opens the health details'],
  'project-manager': ['supervisor', 'button.new-btn', 'opens the New project wizard'],
  'report-sender': ['supervisor', '#add-contact-btn', 'opens Add contact'],
  'skillmatrix': ['worker', 'button.step-btn', "steps a discipline's target level (not saved)"],
};

const OBSERVE = () => {
  window.__inp = { max: 0, n: 0, trusted: 0, entry: null };
  for (const t of ['pointerdown', 'keydown']) document.addEventListener(t, (e) => { if (e.isTrusted) window.__inp.trusted++; }, { capture: true });
  try {
    new PerformanceObserver((l) => {
      for (const e of l.getEntries()) {
        if (!e.interactionId) continue;
        window.__inp.n++;
        if (e.duration > window.__inp.max) {
          const t = e.target;
          window.__inp.max = e.duration;
          window.__inp.entry = { type: e.name, target: t && t.tagName ? t.tagName.toLowerCase() + (t.id ? '#' + t.id : '') : 'document',
            input: Math.round(e.processingStart - e.startTime), processing: Math.round(e.processingEnd - e.processingStart),
            presentation: Math.round(e.startTime + e.duration - e.processingEnd) };
        }
      }
    }).observe({ type: 'event', buffered: true, durationThreshold: 16 });
  } catch (_) { /* unsupported: every round reads UNGRADED */ }
};

async function calibrate(page, cdp) {
  const spin = () => page.evaluate(() => { const t = performance.now(); let x = 0; for (let i = 0; i < 3e6; i++) x += Math.sqrt(i); return performance.now() - t + (x < 0 ? 1 : 0); });
  await spin(); await spin();
  const before = Math.min(await spin(), await spin());
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: CPU });
  const after = Math.min(await spin(), await spin());
  return { before_ms: Math.round(before), after_ms: Math.round(after), ratio: Math.round((after / before) * 10) / 10 };
}

async function walkPage(browser, file, [role, sel, what]) {
  const out = { page: file, role, control: sel, action: what, rounds: [] };
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true, timezoneId: 'Asia/Manila' });
  try {
    await assertSignedIn(signIn(ctx, role));
    await ctx.addInitScript(OBSERVE);
    if (TEETH) await ctx.addInitScript(() => document.addEventListener('pointerdown', (e) => { if (e.isTrusted) { let x = 0; for (let i = 0; i < 4e7; i++) x += Math.sqrt(i); window.__teethSink = x; } }, true));
    const page = await ctx.newPage();
    const cdp = await ctx.newCDPSession(page);
    await page.goto('about:blank');
    out.calib = await calibrate(page, cdp);
    for (let r = 0; r < ROUNDS; r++) {
      await page.goto(`${ORIGIN}/${file}.html`, { waitUntil: 'load', timeout: 90000 });
      await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
      await page.waitForTimeout(2500);
      const loc = page.locator(sel).filter({ visible: true }).first();
      const found = await loc.count().catch(() => 0);
      if (!found) { out.rounds.push({ round: r + 1, shape: 'UNGRADED', why: `no visible ${sel}` }); continue; }
      await loc.scrollIntoViewIfNeeded().catch(() => {});
      await page.waitForTimeout(400);
      await loc.tap({ timeout: 10000 }).catch((e) => { out.tapErr = String(e).slice(0, 120); });
      await page.waitForTimeout(2500);   // the next paint lands inside this; Event Timing reports after it
      const m = await page.evaluate(() => window.__inp);
      const ms = m.n ? Math.round(m.max) : (m.trusted ? '<16' : null);
      out.rounds.push({ round: r + 1, ms, trusted: m.trusted, timed: m.n, entry: m.entry,
        shape: ms === null ? 'UNGRADED' : (ms === '<16' || ms <= BUDGET) ? 'WITHIN' : 'OVER' });
    }
  } finally { await ctx.close().catch(() => {}); }
  const graded = out.rounds.filter((x) => x.shape !== 'UNGRADED');
  const nums = graded.map((x) => (x.ms === '<16' ? 15 : x.ms));
  out.inp_ms = nums.length ? Math.max(...nums) : null;
  out.throttled = !!(out.calib && out.calib.ratio >= MIN_RATIO);
  out.pass = out.throttled && graded.length === ROUNDS && graded.every((x) => x.shape === 'WITHIN');
  return out;
}

const browser = await chromium.launch({ headless: true });
const prior = (!TEETH && existsSync(OUT)) ? JSON.parse(readFileSync(OUT, 'utf8')) : { pages: {} };
for (const [file, spec] of Object.entries(PAGES)) {
  if (ONE && ONE !== file) continue;
  let r;
  try { r = await walkPage(browser, file, spec); } catch (e) { r = { page: file, error: String(e.message || e).slice(0, 200), pass: false }; }
  prior.pages[file] = { ...r, ran: new Date().toISOString() };
  console.log(`${file}: ${r.pass ? 'PASS' : 'FAIL'} INP@${CPU}x ${r.inp_ms ?? '-'}ms (budget ${BUDGET}) rounds=${(r.rounds || []).map((x) => x.ms ?? x.shape).join('/')} `
    + `calib x${r.calib ? r.calib.ratio : '?'} - ${r.action || ''}${r.error ? ' ERR ' + r.error : ''}${r.tapErr ? ' TAP ' + r.tapErr : ''}`);
}
prior.generated = new Date().toISOString();
prior.method = `Chromium 390x844 dpr3 touch, CPU ${CPU}x (CDP, calibrated >= ${MIN_RATIO}x), ${ROUNDS} fresh loads, a real tap on the primary control each, Event Timing (>=16 ms), budget ${BUDGET} ms`;
if (!TEETH) writeFileSync(OUT, JSON.stringify(prior, null, 1));   // a teeth run never writes the report
await browser.close();
const failed = Object.values(prior.pages).filter((p) => !p.pass).map((p) => p.page);
console.log(failed.length ? `FAIL lowend-inp - ${failed.join(', ')}` : `PASS lowend-inp - ${Object.keys(prior.pages).length} pages`);
process.exitCode = failed.length ? 1 : 0;
