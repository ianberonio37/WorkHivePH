/* prove_rate_views.mjs — the rate_limit_legible oracle asked of every (page, view) cell.
 *
 * The oracle: a 429 is answered with WHEN to retry (or at least that waiting — not retrying — is
 * the remedy), never a bare "try again", which invites the one action that extends the limit.
 *
 * Mechanics, all inherited from the proven view-pass recipe (why_refused port, 2026-08-22):
 *   - reach the view HEALTHY first, then induce (a view that never opened measures nothing);
 *   - induce via ctx.route AFTER open (supabase-js binds fetch at construction; ctx.route sits
 *     above the service worker) with the REAL 429 shape + Retry-After header;
 *   - drive the view's own reads by Escape+reopen, then a fresh-first-open fallback so a
 *     read-once-per-page-life cache cannot fake an abstain;
 *   - collect announcements CONTINUOUSLY from induction (a toast dies before a settled read);
 *   - zero intercepted reads = UNGRADED, never judged.
 *
 * Run:  node tools/prove_rate_views.mjs [--page community]   → rate_views_report.json
 */
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';
import { viewTargets, openView } from './view_pass.mjs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const PAGES = ['hive', 'logbook', 'inventory', 'pm-scheduler', 'project-manager', 'dayplanner',
  'asset-hub', 'analytics', 'alert-hub', 'skillmatrix', 'shift-brain', 'voice-journal',
  'community', 'achievements', 'resume', 'report-sender', 'project-report',
  'index', 'public-feed', 'assistant', 'engineering-design', 'analytics-report'];
const QUERY = { 'project-report': '?project_id=539e0d9a-9ff7-474b-ab03-9254406ca7dc' };
const args = process.argv.slice(2);
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

const NAMES_WAIT = /wait|retry in|try (again )?in \d|in \d+ ?(s|sec|seconds?|m|min|minutes?)|rate limit|too many|slow down|a moment|later/i;
const BARE_RETRY = /\btry again\b|\bretry\b/i;

const COLLECTOR = () => {
  window.__whSeen = window.__whSeen || [];
  const grab = (n) => { const t = (n.innerText || n.textContent || '').replace(/\s+/g, ' ').trim();
                        if (t) window.__whSeen.push(t.slice(0, 300)); };
  const mo = new MutationObserver((muts) => {
    for (const m of muts) for (const n of m.addedNodes || []) {
      if (n.nodeType !== 1) continue;
      if (n.matches?.('[role="alert"],[role="status"],[aria-live],.toast,[class*="toast"],[class*="error"]')) grab(n);
      n.querySelectorAll?.('[role="alert"],[role="status"],[aria-live],.toast,[class*="toast"],[class*="error"]').forEach(grab);
    }
  });
  mo.observe(document.body, { childList: true, subtree: true, characterData: true });
};

const browser = await chromium.launch();
const cells = [];
const route429 = async (ctx, counter) => ctx.route('**/rest/v1/**', (route) => {
  // READ-shaped RPCs travel as POSTs (/rpc/get_* bundles) - a GET-only induction reads an
  // RPC-fed view as issuing no reads, a false NA. Fulfilling never lets the request leave.
  const m = route.request().method();
  const isRead = /GET|HEAD/i.test(m) || (/POST/i.test(m) && route.request().url().includes('/rpc/'));
  if (!isRead) return route.continue();
  counter.n++;
  return route.fulfill({ status: 429, contentType: 'application/json',
    headers: { 'Retry-After': '30' },
    body: JSON.stringify({ message: 'rate limit exceeded', code: '429' }) });
});
const readSaid = (p) => p.evaluate(({ waitSrc, retrySrc }) => {
  const seen = [...new Set(window.__whSeen || [])].join(' ');
  const body = (document.body.innerText || '').replace(/\s+/g, ' ');
  const txt = body + ' ' + seen;
  const W = new RegExp(waitSrc, 'i'), R = new RegExp(retrySrc, 'i');
  return { namesWait: W.test(txt), bareRetry: R.test(txt) && !W.test(txt),
           sample: (seen || body).slice(0, 160) };
}, { waitSrc: NAMES_WAIT.source, retrySrc: BARE_RETRY.source });

for (const pg of (ONE ? [ONE.replace(/\.html$/, '')] : PAGES)) {
  for (const t of viewTargets(pg)) {
    const rec = { page: pg, view: t.view, modal: t.modal };
    try {
      const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
      if (!t.signedOut) await assertSignedIn(signIn(ctx, 'supervisor'));  // index V2/V3 run signed OUT by design
      const p = await ctx.newPage();
      await p.goto(`${ORIGIN}/${pg}.html${QUERY[pg] || ''}`, { waitUntil: 'domcontentloaded', timeout: 25000 });
      await p.waitForTimeout(3200);
      const opened = await openView(p, t);
      if (!opened.ok) {
        rec.ok = null; rec.verdict = `${opened.kind}: ${opened.why}`;
        cells.push(rec); await ctx.close(); continue;
      }
      const before = await readSaid(p);
      const counter = { n: 0 };
      await route429(ctx, counter);
      await p.evaluate(COLLECTOR);
      await p.keyboard.press('Escape').catch(() => {});
      await p.waitForTimeout(900);
      const re = await openView(p, t, { settleMs: 2600 });
      let after = await readSaid(p);
      let path = 'reopen';
      let viewRendered = re.ok === true;
      await ctx.close();
      if (!counter.n) {
        // fresh-first-open fallback: a read-once cache cannot fake the abstain
        const c2 = await browser.newContext({ viewport: { width: 390, height: 844 } });
        await assertSignedIn(signIn(c2, 'supervisor'));
        const p2 = await c2.newPage();
        await p2.goto(`${ORIGIN}/${pg}.html${QUERY[pg] || ''}`, { waitUntil: 'domcontentloaded', timeout: 25000 });
        await p2.waitForTimeout(3200);
        await route429(c2, counter);
        await p2.evaluate(COLLECTOR);
        const first = await openView(p2, t, { settleMs: 2600 });
        if (first.ok || counter.n) { after = await readSaid(p2); path = 'first-open'; }
        await c2.close();
      }
      rec.hits = counter.n; rec.path = path;
      if (!counter.n) {
        rec.ok = null;
        rec.verdict = 'no REST read on reopen NOR on a fresh first open under the 429 — this view '
          + 'reads nothing of its own, so the rate-limit oracle has no subject here';
      } else if (before.namesWait) {
        rec.ok = null; rec.verdict = 'the view already carries wait vocabulary at rest — unattributable';
      } else if (after.namesWait) {
        rec.ok = true; rec.verdict = `the 429 is answered with the wait (${after.sample.slice(0, 90)})`;
      } else if (after.bareRetry && !before.bareRetry) {
        // the delta discipline: a Retry control RESTING on the view before any induction is not an
        // answer to this 429 - only a NEWLY offered bare retry is the accusation
        rec.ok = false; rec.verdict = `BARE RETRY offered against a rate limit — the one action that extends it (${after.sample.slice(0, 80)})`;
      } else if (viewRendered) {
        // THE SUBJECT DISCRIMINATOR (2026-08-22): logbook's modal reopened and rendered from
        // IN-MEMORY state while the counted 429s hit the page's background polls - background-read
        // silence is the PAGE-LEVEL cell's subject, not this view's. A view that rendered its
        // content under the limit owed nothing here.
        rec.ok = null; rec.na = true;
        rec.verdict = 'NA: the view reopened and rendered from in-memory state under the 429; the '
          + `${counter.n} intercepted read(s) were the page's background traffic, which the `
          + 'page-level rate_limit cell owns - this view issued no read it needed answered';
      } else {
        rec.ok = false; rec.verdict = 'the view FAILED to render under the 429 and said nothing that names the wait';
      }
    } catch (e) { rec.ok = null; rec.verdict = String(e.message || e).slice(0, 140); }
    cells.push(rec);
    console.log(`  ${(rec.page + '#' + rec.view).padEnd(24)} ${rec.ok === true ? 'PASS' : rec.ok === false ? 'FAIL' : 'UNGRADED'}  ${String(rec.verdict).slice(0, 78)}`);
  }
}
await browser.close();
const ok = cells.filter((c) => c.ok === true).length;
const bad = cells.filter((c) => c.ok === false).length;
// A NARROWED RUN MUST NOT CLOBBER THE FULL ONE: this file is read downstream (gates and
// bank_prover_reports), so a --page/--case spot-check overwriting a whole sweep's verdicts
// corrupts the BANK, not just a log. Measured on prove_retry_path 2026-08-27.
writeFileSync((ONE ? 'rate_views_report.partial.json' : 'rate_views_report.json'), JSON.stringify({
  totals: { cells: cells.length, pass: ok, fail: bad, ungraded: cells.length - ok - bad },
  views: cells,
}, null, 1));
console.log(`\n  ${cells.length} cell(s): ${ok} PASS · ${bad} FAIL · ${cells.length - ok - bad} ungraded — rate_views_report.json`);
process.exit(bad ? 1 : 0);
