// prove_retry_path.mjs — the CG `retry_path` oracle, measured end-to-end on every production page.
//
// THE ORACLE: a failure offers a retry path, AND pressing it RE-ATTEMPTS rather than re-rendering the
// failure. Both clauses, because they fail independently and the second is the one that gets shipped
// broken — this arc measured hive doing exactly that: a Retry that sent 3 fresh reads and left the
// page byte-for-byte unchanged, because it re-rendered from a cache that still held the failed state.
//
// ★THE INDUCTION IS TOTAL, NOT PARTIAL, AND THAT CHANGES THE ANSWER. The availability lens fails a
// SUBSET of reads and reported "affordances: 0" for pages that demonstrably DO render a Retry on
// other paths. Failing EVERY /rest/v1/ request is what actually reaches a page's error branch — and
// it exposed the real shape of the roster-wide gap: not a missing feature, but partial ADOPTION of a
// component that already exists.
//
// ★THE COMPONENT: whListError(el, message, onRetry) in utils.js renders the inline error WITH a Retry
// control, and 16 pages already import it. skillmatrix rendered "Retry" under this exact injection
// while hive and inventory did not — one page having it is what separates "nobody built this" from
// "not every read path routes through it". So a FAIL here names a read path to route, not a design.
//
// FOUR OUTCOMES, kept distinct because they need different work:
//   PASS      — says a failure happened, offers a retry, pressing it re-attempts AND recovers
//   NO-RETRY  — says a failure happened, nothing to press (advice is not a path)
//   NO-RECOVER— a retry that re-attempts and leaves the failure on screen (worse than none: it
//               invites pressing again)
//   SILENT    — renders no failure at all under a total outage; a different and worse finding, and
//               NOT scored as a retry problem
//
// USAGE:  node tools/prove_retry_path.mjs [--page <name>]
// OUTPUT: retry_path_report.json

// ★THE SCOPE OF THE OUTAGE IS PART OF THE CLAIM, AND THIS PROVER OVERSTATED IT (fixed 2026-08-19).
// The verdict read "under a TOTAL read outage" while the injection breaks only **/rest/v1/**. On
// analytics-report that gap manufactured a finding I banked and had to withdraw within the hour: 9 REST
// reads were refused, but fetchReport (analytics-report.html:695-705) calls an EDGE function that was
// never intercepted, so the report RENDERED - the collected text ends with its own "Recomputed when
// this report was generated" freshness chip - and the page was correctly silent about unrelated failed
// reads. A page that succeeds at what the person asked for owes them no error.
// So: SILENT means "silent under a REST-only outage", which is a weaker claim than the oracle wants.
// To ask the real question, break **/functions/v1/** too - but that changes the subject for all 22
// pages and must be re-walked as such, not bolted on.

// ★TWO SILENT VERDICTS ARE UNCONFIRMED - DO NOT BANK THEM AS DEFECTS ON THIS EVIDENCE (2026-08-19).
// After the announcement collector was added below, analytics flipped SILENT -> PASS: its verdict had
// always been honest (analytics.html:1067 records that fetchPhase catches, toasts via whAiError and
// paints its own verdict) and the old single late read simply missed the toast. Two remain SILENT and
// BOTH have a visible correct error path in source, so the same doubt applies to them:
//   · analytics-report - analytics-report.html:737-742 catches and replaces the mount with
//     whAiError('Could not generate report: ...'). The collector saw only "Compiling analytics across
//     all 4 phases". Either fetchReport() RESOLVES with empty data under a 401 instead of throwing -
//     which would be a real defect, an empty REPORT where an error belongs - or the catch painted
//     after the state was read. These are opposite conclusions and this run cannot separate them.
//   · assistant - 13 reads intercepted, no retry control, only "Thinking..." collected. A chat that
//     thinks forever is the stuck-skeleton class and would be serious, but it is equally consistent
//     with a probe that read before the failure resolved.
// NEXT: re-run these two with a settle long enough to outlast the slowest orchestrator path (measured
// at 32.6s on analytics-report, per its own comment at :718-720) and read the mount AFTER it, before
// either is called a finding. Three separate false readings this session came from measuring early.

import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'node:url';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();
// Extra dwell before the failure state is read, for pages whose primary is slow: analytics-report
// records a 32.6s orchestrator run in its own source, and reading at 7s calls that page SILENT.
const SETTLE = (() => { const i = args.indexOf('--settle'); return i >= 0 ? Number(args[i + 1]) : 0; })();

const PAGES = ['index', 'hive', 'logbook', 'inventory', 'pm-scheduler', 'project-manager', 'dayplanner',
  'asset-hub', 'analytics', 'alert-hub', 'skillmatrix', 'shift-brain', 'voice-journal', 'assistant',
  'community', 'public-feed', 'achievements', 'engineering-design', 'resume', 'report-sender',
  'project-report', 'analytics-report'];

const SAYS_FAILURE = /could not|couldn|failed|unable|problem loading|error loading|try again/i;

const readState = (page) => page.evaluate(() => {
  // ★A LINGERING TOAST IS NOT PAGE STATE, and reading it as such manufactured a defect. achievements
  // recovered completely — its body reloaded and every panel came back — and this check still failed
  // it, because the toast raised at the moment of failure ("Achievements failed to load. Tap Retry.")
  // was still on screen when the scan ran. A toast is a transient announcement about a moment that has
  // passed; the question here is what the PAGE says now. Excluding the toast layer is not loosening
  // the oracle, it is aiming it: the same run still fails a page whose panels keep claiming failure.
  // ★AND IT MUST BE READ FROM THE LIVE DOM. My first attempt cloned <body>, stripped the toast and
  // read innerText off the clone — but a DETACHED node has no layout, so innerText silently falls back
  // to textContent and the scan started seeing HIDDEN text too. The fix for a false positive made the
  // instrument blunter, which is this platform's own recorded innerText trap walked straight into.
  // So: walk the live tree, take only RENDERED leaves, and skip anything inside the toast layer.
  const TOAST = '#toast, #toast-text, .toast, [role="status"], [aria-live]';
  const parts = [];
  for (const el of document.querySelectorAll('*')) {
    if (el.children.length) continue;
    if (el.closest(TOAST)) continue;
    const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    if (!(r.height > 0 && r.width > 0) || cs.display === 'none' || cs.visibility === 'hidden') continue;
    const s = (el.textContent || '').trim();
    if (s) parts.push(s);
  }
  const t = parts.join(' ').replace(/\s+/g, ' ');
  const btns = [...document.querySelectorAll('button,a,[role=button]')]
    .filter((e) => e.getClientRects().length && /retry|try again|reload|refresh/i.test(e.textContent || ''));
  return { text: t, chars: t.length, retry: btns.map((e) => (e.textContent || '').trim().slice(0, 24)) };
});

const run = async () => {
  const browser = await chromium.launch();
  // ★BLOCK SERVICE WORKERS. This prover breaks reads with ctx.route and never calls setOffline, so it
  // is the one interception harness with nothing else covering the gap: a warm SW answers the fetch
  // from its own handler, the route never fires, the read SUCCEEDS, and a retry control that was never
  // actually exercised reads as working. Every sibling harness escapes this by going offline at the
  // network layer (prove_offline_refusal/-queued, walk_owed_scenarios, diag_owed_failures all call
  // setOffline); this one did not. Found in prove_fallback_engaged.mjs, where the same hole reported
  // edgeCallsBroken:0 and read as "this page has no primary".
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 },
    serviceWorkers: 'block' });
  await assertSignedIn(signIn(ctx, 'supervisor'));
  const out = { origin: ORIGIN, pages: [] };

  for (const name of (ONE ? [ONE] : PAGES)) {
    const page = await ctx.newPage();
    // ★A TOAST IS GONE BEFORE readState RUNS. analytics scored SILENT here - "renders no failure at
    // all under a total read outage" - and it was false: analytics.html:1067 records that fetchPhase
    // catches its own errors, TOASTS via whAiError and paints its own verdict, so the announcement is
    // transient and had already dismissed by the time the state was read. Same fault found the same
    // day in prove_fallback_engaged.mjs, where it scored two honest pages as silent fallbacks.
    // Collect announcements from load onward and union them into the read.
    await page.addInitScript(() => {
      window.__whSeen = [];
      const SEL = '[role="alert"], [role="status"], [aria-live], .toast, .hive-toast, .toast-text,'
        + ' [class*="error"], [id*="error"]';
      const push = (el) => { const t = (el.textContent || '').trim(); if (t) window.__whSeen.push(t); };
      const grab = (n) => {
        if (!n || n.nodeType !== 1) return;
        if (n.matches && n.matches(SEL)) push(n);
        if (n.querySelectorAll) n.querySelectorAll(SEL).forEach(push);
      };
      addEventListener('DOMContentLoaded', () => {
        new MutationObserver((ms) => ms.forEach((m) => m.addedNodes.forEach(grab)))
          .observe(document.body, { childList: true, subtree: true });
      });
    });
    const rec = { page: name };
    let failing = true, reads = 0;
    try {
      // ★ROUTE AT THE CONTEXT, NOT THE PAGE — MEASURED, NOT PREFERRED. This origin registers a
      // CONTROLLING SERVICE WORKER, and page-level routing does not see fetches it mediates. Compared
      // side by side on one load: ctx.route counted 6 requests where page.route counted 4, and for the
      // fetch a Retry triggers, ctx saw 1 and page saw ZERO. That blindness is what made me bank
      // "report-sender's retry is inert" against a page whose retry works perfectly.
      // prove_offline_refusal.mjs already used ctx.route and was never exposed.
      await ctx.route('**/rest/v1/**', (route) => {
        reads++;
        if (failing) {
          return route.fulfill({ status: 500, contentType: 'application/json',
            body: JSON.stringify({ message: 'injected 500' }) });
        }
        return route.continue();
      });
      // ★THE DATA-BEARING VIEW IS NOT ALWAYS THE LANDING VIEW, and walking only the landing view
      // manufactured a SILENT verdict for a page that handles this correctly. engineering-design's
      // calculator tab is CLIENT-SIDE: a 500 does not break it, so its silence there is right. Its
      // History tab, which is the part that reads, says "This is a connection problem, not an empty
      // history" AND offers a Retry — and my probe never opened it. Same trap the units prover hit:
      // reach the view that owns the data before judging what the page says about losing it.
      const REACH = {
        'engineering-design': "var t=[...document.querySelectorAll('[data-tab]')].find(e=>e.dataset.tab==='history'); if(t) t.click();",
        'analytics-report': "var b=document.getElementById('generate-btn'); if(b) b.click();",
      };
      const QUERY = { 'project-report': '?project_id=539e0d9a-9ff7-474b-ab03-9254406ca7dc' };
      await page.goto(`${ORIGIN}/workhive/${name}.html${QUERY[name] || ''}`,
        { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(7000);
      if (REACH[name]) {
        await page.evaluate((src) => eval(src), REACH[name]).catch(() => {});
        rec.reached = true;
        await page.waitForTimeout(5000);
      }
      await page.waitForTimeout(2000);

      // ★ZERO INTERCEPTED READS = UNGRADED, NEVER JUDGED. This is the rail every sibling prover in this
      // directory already carries — prove_failure_injection.mjs states it outright: "a page where the
      // counter reads zero is UNGRADED, never judged" — and I did not carry it into this tool. That
      // omission is exactly how I came to bank "report-sender's retry is inert" on a counter a service
      // worker was walking past. A failure-injection oracle that did not inject reports the most
      // convincing false findings available, because "the page said nothing about the error" is
      // precisely what a page with NO error would say.
      rec.interceptedOnLoad = reads;
      if (reads === 0) {
        rec.outcome = 'UNGRADED';
        rec.why = 'the injection intercepted ZERO reads, so this page was never actually put into a '
                + 'failure state - nothing here is a finding about the page, and it is recorded as '
                + 'ungraded rather than scored';
        await ctx.unroute('**/rest/v1/**').catch(() => {});
        await page.close();
        out.pages.push(rec);
        console.log(`  UNGRADED    ${name.padEnd(19)} injection intercepted nothing`);
        continue;
      }
      if (SETTLE) await page.waitForTimeout(SETTLE);
      const before = await readState(page);
      // Union the live text with every announcement seen since load, so a dismissed toast still counts.
      const seen = await page.evaluate(() => [...new Set(window.__whSeen || [])].join(' | '))
        .catch(() => '');
      rec.announced = seen.slice(0, 200);
      rec.saysFailure = SAYS_FAILURE.test(before.text) || SAYS_FAILURE.test(seen);
      rec.retryControls = before.retry;
      rec.charsBefore = before.chars;

      if (!rec.saysFailure) {
        // ★SILENT UNDER A TOTAL OUTAGE IS NOT A RETRY PROBLEM. Scoring it as one would file the wrong
        // bug: the page has not yet told anyone anything is wrong, so a retry has nothing to attach to.
        rec.outcome = 'SILENT';
        rec.why = 'the page renders no failure under a REST read outage (edge calls were NOT broken) - a different and more '
                + 'serious finding than a missing retry, and recorded as such rather than conflated';
      } else if (!before.retry.length) {
        rec.outcome = 'NO-RETRY';
        rec.why = 'the page says a failure happened and offers nothing to press - advice is not a path';
      } else {
        // Release the network, then press. Recovery is the clause that ships broken.
        failing = false;
        const readsAtPress = reads;
        await page.evaluate(() => {
          const b = [...document.querySelectorAll('button,a,[role=button]')]
            .find((e) => /retry|try again|reload|refresh/i.test(e.textContent || ''));
          if (b) b.click();
        });
        await page.waitForTimeout(8000);
        const after = await readState(page);
        // ★A READ COUNT IS BLIND TO A SERVICE WORKER, and trusting it produced a false accusation.
        // This origin registers a CONTROLLING service worker, so a fetch it mediates never passes
        // page.route - report-sender pressed Retry, my counter said ZERO requests, and I recorded an
        // "inert button". It was not inert: with a contact seeded, the press made the new row APPEAR on
        // screen. The data proved the re-attempt that the counter could not see.
        // So re-attempt is judged by EFFECT first (did the failure clear / did content change) and by
        // the counter only as corroboration. A probe that can be bypassed must not be the sole witness.
        rec.contentChanged = after.chars !== before.chars;
        rec.reAttempted = reads > readsAtPress || rec.contentChanged;
        rec.readCounterBlind = !(reads > readsAtPress) && rec.contentChanged;
        rec.newReads = reads - readsAtPress;
        rec.charsAfter = after.chars;
        // ★RECOVERY MEANS *THIS* FAILURE CLEARED, NOT THAT NO FAILURE-ISH WORDS REMAIN. Asking the
        // looser question failed analytics, which had recovered from the injected 500 perfectly and
        // still displayed a TRUE and unrelated notice: "AI call limit reached for this hive. Try again
        // in an hour." — an hourly budget, partly spent by this very session. My pattern matched "try
        // again" and called a working page broken. A page reporting a different, real condition is not
        // a page that failed to recover; conflating them manufactures a defect out of honesty.
        // So the test is anchored: take the failure sentences the INJECTION produced, and require
        // those to be gone afterwards.
        const failLines = (t) => (t.match(/[^.!?]*?(could not|couldn|failed|unable)[^.!?]*/gi) || [])
          .map((s) => s.trim().toLowerCase()).filter((s) => s.length > 8);
        const wasSaying = new Set(failLines(before.text));
        const stillSaying = failLines(after.text).filter((s) => wasSaying.has(s));
        rec.injectedFailuresBefore = [...wasSaying].slice(0, 4);
        rec.stillSaying = stillSaying.slice(0, 4);
        rec.recovered = rec.reAttempted && stillSaying.length === 0;
        rec.outcome = rec.recovered ? 'PASS' : (rec.reAttempted ? 'NO-RECOVER' : 'NO-ATTEMPT');
        rec.why = rec.recovered
          ? `pressing retry sent ${rec.newReads} fresh reads and the failure cleared (${rec.charsBefore} -> ${rec.charsAfter} chars)`
          : rec.reAttempted
            ? `retry re-attempted (${rec.newReads} reads) but the failure is STILL on screen - worse than `
              + 'offering none, because it invites pressing again'
            : 'pressing retry sent no new request at all';
      }
    } catch (e) { rec.error = String(e.message || e).slice(0, 160); rec.outcome = 'ERROR'; }
    await ctx.unroute('**/rest/v1/**').catch(() => {});
    await page.close();
    out.pages.push(rec);
    console.log(`  ${String(rec.outcome).padEnd(11)} ${name.padEnd(19)} `
      + `retry=[${(rec.retryControls || []).join(',')}]`
      + (rec.newReads != null ? ` reads=${rec.newReads}` : '')
      + (rec.error ? `  ERR ${rec.error}` : ''));
  }

  await browser.close();
  writeFileSync(path.join(ROOT, 'retry_path_report.json'), JSON.stringify(out, null, 1));
  const t = (o) => out.pages.filter((p) => p.outcome === o).length;
  // a gate that cannot fail is not a gate: FAIL outcomes set the exit code (added 2026-08-21 when
  // this prover was promoted from walk instrument to registered gate).
  if (process.argv.includes('--gate')) process.exitCode = t('FAIL') ? 1 : 0;
  console.log(`\n  ${out.pages.length} page(s) | PASS ${t('PASS')} | NO-RETRY ${t('NO-RETRY')} `
    + `| NO-RECOVER ${t('NO-RECOVER')} | SILENT ${t('SILENT')} | ERROR ${t('ERROR')}`);
};
run().catch((e) => { console.error(e); process.exit(1); });
