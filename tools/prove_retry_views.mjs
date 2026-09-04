/* prove_retry_views.mjs — retry_path asked of every dialog view: a failed view offers a retry
 * that ACTUALLY re-attempts and succeeds once the cause is gone.
 *
 * The full loop, per cell: open the view healthy → route its reads to 500 → drive the view's own
 * reads (Escape+reopen) so the failure paints → find a retry affordance INSIDE the view → heal the
 * network (unroute) → press the affordance → the content must recover. Judged only when the
 * failure actually painted (hits > 0); a view that reads nothing is measured not-applicable.
 *
 *   PASS      — failure painted, a retry affordance existed in the view, pressing it after the
 *               network healed recovered the content.
 *   FAIL      — failure painted and no retry affordance exists in the view, or pressing it did
 *               not recover once the cause was gone.
 *   NA        — the view issues no read of its own (both induction paths counted zero).
 *   UNGRADED  — precondition/open failures, recorded with reasons.
 *
 * Run:  node tools/prove_retry_views.mjs [--page community]   → retry_views_report.json
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
// T40 second lane (2026-08-26): --lane edge blocks **/functions/v1/** instead of REST, closing
// the scope note that let edge-fed views (analytics-report's generators, project-manager's
// progress fn) read as justified-silent under a REST-only outage. Every edge invocation is
// fulfilled locally with a 500 (nothing leaves the browser), so mutating fns are safe to block.
const LANE = (() => { const i = args.indexOf('--lane'); return i >= 0 ? args[i + 1] : 'rest'; })();
const BLOCK = LANE === 'edge' ? '**/functions/v1/**' : '**/rest/v1/**';
const REPORT = LANE === 'edge' ? 'retry_views_edge_report.json' : 'retry_views_report.json';

const readView = (sel) => {
  const el = sel && (document.getElementById(sel) || document.querySelector(`.${CSS.escape(sel)}`));
  const scope = el || document.body;
  // RENDERED-BY-TEXT, not by rect (2026-08-22): community's open sheet reports ZERO rects on its
  // children while innerText returns their real text - and Chromium's innerText already respects
  // visibility, so non-empty innerText IS proof of rendering (the inverse of the
  // innerText-returned-empty trap). A rect-only vis() rejected a real Retry button here.
  const vis = (n) => {
    const cs = getComputedStyle(n);
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    const r = n.getBoundingClientRect();
    return (r.width > 2 && r.height > 2) || ((n.innerText || '').trim().length > 0);
  };
  document.querySelectorAll('[data-wh-rv]').forEach((n) => n.removeAttribute('data-wh-rv'));
  const retry = [...scope.querySelectorAll('button, a, [role="button"]')].filter(vis)
    .find((b) => /\b(retry|try again|reload|refresh)\b/i.test(b.innerText || ''));
  if (retry) retry.setAttribute('data-wh-rv', '1');
  const txt = (scope.innerText || '').replace(/\s+/g, ' ').trim();
  // PER-SENTENCE failure vocabulary, so the caller can subtract a healthy-open BASELINE:
  // asset-hub's Weibull panel ships a worked EXAMPLE ("63% have failed by ~180 run-days") that
  // matches this regex forever - a scope-wide boolean reads that marketing copy as the view
  // announcing failure, before induction and after heal alike.
  const failSents = txt.split(/(?<=[.!?])\s+|\s*[|·]\s*/)
    .map((s) => s.trim())
    .filter((s) => s && /couldn['’]?t|could not|failed|unavailable|error|problem|went wrong/i.test(s));
  return { chars: txt.length, failSents, hasRetry: !!retry };
};

const browser = await chromium.launch();
const cells = [];
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
      // healthy-open baseline: failure sentences already on the glass with nothing broken are
      // the view's own static prose, and NEVER count as an announcement or as failure residue
      const base = await p.evaluate(readView, t.modal);
      const isNew = (r) => (r.failSents || []).filter((s) => !(base.failSents || []).includes(s));
      let hits = 0;
      await ctx.route(BLOCK, (route) => {
        // READ-shaped RPCs travel as POSTs (hive's board loads via POST /rest/v1/rpc/get_* bundles) -
        // a GET-only induction reads an RPC-fed view as "issues no read of its own", a false NA.
        // Fulfilling a 500 here is safe for mutating RPCs too: the request never leaves the browser.
        // Edge lane: ALL functions/v1 invocations are POSTs; every one is the lane's subject.
        const m = route.request().method();
        const isRead = LANE === 'edge'
          || /GET|HEAD/i.test(m) || (/POST/i.test(m) && route.request().url().includes('/rpc/'));
        if (!isRead) return route.continue();
        hits++;
        return route.fulfill({ status: 500, contentType: 'application/json',
          body: JSON.stringify({ message: 'internal error (retry-views probe)' }) });
      });
      await p.keyboard.press('Escape').catch(() => {});
      await p.waitForTimeout(900);
      const re = await openView(p, t, { settleMs: 2600 });
      const failed = await p.evaluate(readView, t.modal);
      if (!hits) {
        rec.ok = null; rec.na = true;
        rec.verdict = 'NA: the view issues no REST read of its own under the induction - a retry '
          + 'path has no failure to recover from here';
        await ctx.close(); cells.push(rec);
        console.log(`  ${(pg + '#' + t.view).padEnd(24)} NA`);
        continue;
      }
      const newFail = isNew(failed);
      rec.newFailureText = newFail.join(' | ').slice(0, 160) || undefined;
      if (!newFail.length && !failed.hasRetry) {
        // the reads failed and the view neither says so nor offers a way - grade against the view
        // only if it FAILED to render its content (a memory-rendered view owes nothing; the page-
        // level cell owns background reads - the rate-views subject discriminator)
        if (re.ok) {
          rec.ok = null; rec.na = true;
          rec.verdict = 'NA: the view rendered from in-memory state; the failed reads were the '
            + 'page\'s background traffic, the page-level retry cell\'s subject';
        } else {
          rec.ok = false;
          rec.verdict = `the view's reads failed (${hits}) and it neither says so nor offers a retry`;
        }
        await ctx.close(); cells.push(rec);
        console.log(`  ${(pg + '#' + t.view).padEnd(24)} ${rec.ok === false ? 'FAIL' : 'NA'}  ${String(rec.verdict).slice(0, 70)}`);
        continue;
      }
      if (!failed.hasRetry) {
        rec.ok = false;
        rec.verdict = `the view says failure but offers NO retry affordance (${hits} reads failed)`;
        await ctx.close(); cells.push(rec);
        console.log(`  ${(pg + '#' + t.view).padEnd(24)} FAIL  ${rec.verdict.slice(0, 70)}`);
        continue;
      }
      // heal the network, press the view's own retry, expect recovery
      await ctx.unroute(BLOCK).catch(() => {});
      await p.evaluate(() => document.querySelector('[data-wh-rv="1"]')?.click());
      await p.waitForTimeout(3500);
      const healed = await p.evaluate(readView, t.modal);
      const residue = isNew(healed);
      if (!residue.length && healed.chars > 40) {
        rec.ok = true;
        rec.verdict = `failure painted, the view's own retry re-attempted after the cause cleared, `
          + `content recovered (${healed.chars} chars, no failure text beyond the healthy baseline)`;
      } else {
        rec.ok = false;
        rec.verdict = `retry pressed after the network healed but the view did not recover `
          + `(failure residue: ${JSON.stringify(residue.join(' | ').slice(0, 120))}, ${healed.chars} chars)`;
      }
      await ctx.close();
    } catch (e) { rec.ok = null; rec.verdict = String(e.message || e).slice(0, 140); }
    cells.push(rec);
    console.log(`  ${(rec.page + '#' + rec.view).padEnd(24)} ${rec.ok === true ? 'PASS' : rec.ok === false ? 'FAIL' : 'UNGRADED'}  ${String(rec.verdict).slice(0, 74)}`);
  }
}
await browser.close();
const ok = cells.filter((c) => c.ok === true).length;
const bad = cells.filter((c) => c.ok === false).length;
writeFileSync(REPORT, JSON.stringify({
  totals: { cells: cells.length, pass: ok, fail: bad, ungraded: cells.length - ok - bad },
  views: cells,
}, null, 1));
console.log(`\n  ${cells.length} cell(s): ${ok} PASS · ${bad} FAIL · ${cells.length - ok - bad} ungraded (${LANE} lane) — ${REPORT}`);
process.exit(bad ? 1 : 0);
