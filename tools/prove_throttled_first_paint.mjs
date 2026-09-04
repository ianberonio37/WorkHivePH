// T37 (2026-08-25): the Slow-3G first-10-seconds lane — plant wifi at its worst.
// Per page: does SOMETHING meaningful paint fast (PP1)? do skeletons RESOLVE within the
// window or admit failure (never shimmer past the read's death)? is the page's first
// interactive moment honest?
//
// CDP Network.emulateNetworkConditions gives the real Slow-3G shape (500ms RTT, ~400kbps),
// which context.route cannot (routing intercepts, it does not delay realistically).
// The LOCAL server + blocked service workers keep the measurement about the PAGE's
// waterfall, not the CDN.
//
// USAGE: node tools/prove_throttled_first_paint.mjs [--page <name>]
// OUTPUT: throttled_first_paint_report.json  (findings-recorder; no gate yet — T37 wave close)
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

// The core field/supervisor set — the pages a phone opens mid-shift.
const PAGES = ['index', 'logbook', 'pm-scheduler', 'inventory', 'hive', 'community', 'alert-hub', 'dayplanner'];

const SLOW_3G = { offline: false, latency: 500, downloadThroughput: 400 * 1024 / 8, uploadThroughput: 200 * 1024 / 8 };

const run = async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  await assertSignedIn(signIn(ctx, 'worker'));
  const out = { origin: ORIGIN, profile: 'Slow-3G 500ms/400kbps', pages: [] };

  for (const name of (ONE ? [ONE] : PAGES)) {
    const page = await ctx.newPage();
    const cdp = await ctx.newCDPSession(page);
    await cdp.send('Network.enable');
    await cdp.send('Network.emulateNetworkConditions', SLOW_3G);
    const rec = { page: name };
    try {
      const t0 = Date.now();
      await page.goto(`${ORIGIN}/workhive/${name}.html`, { waitUntil: 'commit', timeout: 60000 });
      // Poll for the first MEANINGFUL paint: >400 chars of visible text (chrome alone is ~200).
      let firstContent = null;
      for (let i = 0; i < 40; i++) {
        await page.waitForTimeout(250);
        const chars = await page.evaluate(() => (document.body?.innerText || '').length).catch(() => 0);
        if (chars > 400) { firstContent = (Date.now() - t0) / 1000; break; }
      }
      rec.firstContentSecs = firstContent;
      // At the 10s mark: are skeletons still shimmering, and is anything stuck?
      const elapsed = (Date.now() - t0) / 1000;
      if (elapsed < 10) await page.waitForTimeout((10 - elapsed) * 1000);
      rec.at10s = await page.evaluate(() => {
        const sk = [...document.querySelectorAll('.wh-skeleton, [aria-busy="true"]')]
          .filter((e) => e.getClientRects().length);
        return {
          liveSkeletons: sk.length,
          chars: (document.body?.innerText || '').length,
          saysFailure: /could not|couldn|failed|unable|check your connection/i.test(document.body?.innerText || ''),
        };
      }).catch(() => null);
      // Verdict vocabulary (findings-recorder): SLOW-HONEST | STUCK-SKELETON | BLANK
      if (!rec.firstContentSecs) rec.verdict = 'BLANK';
      else if (rec.at10s && rec.at10s.liveSkeletons > 0) rec.verdict = 'STUCK-SKELETON-AT-10S';
      else rec.verdict = 'SLOW-HONEST';
    } catch (e) {
      rec.verdict = 'ERROR'; rec.error = String(e).slice(0, 160);
    }
    out.pages.push(rec);
    console.log(`  ${String(rec.verdict).padEnd(22)} ${name.padEnd(14)} first-content=${rec.firstContentSecs ?? '-'}s` +
      (rec.at10s ? ` skeletons@10s=${rec.at10s.liveSkeletons}` : ''));
    await page.close();
  }
  // A NARROWED RUN MUST NOT CLOBBER THE FULL ONE: this file is read downstream (gates and
  // bank_prover_reports), so a --page/--case spot-check overwriting a whole sweep's verdicts
  // corrupts the BANK, not just a log. Measured on prove_retry_path 2026-08-27.
  writeFileSync((ONE ? 'throttled_first_paint_report.partial.json' : 'throttled_first_paint_report.json'), JSON.stringify(out, null, 2));
  await browser.close();
};
run();
