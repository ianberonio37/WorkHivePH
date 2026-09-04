/* prove_fallback_views.mjs — fallback_engaged asked of every dialog view: when the view's OWN
 * primary (an edge function) is down, the fallback engages and the view says which source it used.
 *
 * ★MOST DIALOG VIEWS HAVE NO PRIMARY, AND THAT IS A MEASURED VERDICT, NOT AN ASSUMPTION. The
 * page-level prover's grounding holds here too: only a handful of surfaces have a real
 * edge-function-over-stored-copy split — dialogs overwhelmingly render from live REST reads,
 * which is fail_500/retry_path territory, not this oracle's. So the first measurement is
 * ATTRIBUTION: open the view healthy, then count /functions/v1/ calls while the view is driven
 * (Escape + reopen — the same drive every view family uses). Zero edge calls = the view has no
 * primary to break = NA, measured rather than declared.
 *
 *   PASS      — the view's own edge call was answered 500, content still rendered, AND the view
 *               names a stored source or announces the failure (judged per-sentence as a DELTA
 *               against the healthy-open baseline — static prose never counts).
 *   FAIL      — the view's edge call failed, content rendered, and nothing NEW names the source
 *               or the failure: the fallback engaged silently.
 *   NA        — the view issues no edge call of its own under open/drive (no primary here).
 *   UNGRADED  — precondition/open failures, or the view rendered nothing (fail_500's question).
 *
 * Run:  node tools/prove_fallback_views.mjs [--page community]   → fallback_views_report.json
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

// ★A LIVE-RECOMPUTE FALLBACK IS NOT THIS ORACLE'S SUBJECT — declared per (page,view), with the
// grounding, exactly as the page-level prover excludes pages whose edge fn only powers extras.
// The oracle's failure mode is a person reading STORED numbers as current; a fallback that
// RECOMPUTES the same figures client-side from just-loaded live rows cannot produce that lie,
// and grading its silence as "silent fallback" accuses the view of a claim it never makes.
//   project-manager#V2: fetchProgressRollup (project-manager.html:3168) invokes project-progress
//   and on ANY error falls back to clientRollup() (:3186), which "mirrors the edge fn math" over
//   _items already loaded live - equally fresh, nothing stored. What IS silently absent with the
//   edge down is the CPM + EVM blocks (edge-only) - that is fail_500's question, noted not lost.
const RECOMPUTE_FALLBACK = {
  'project-manager|V2': 'clientRollup() recomputes the rollup from live rows (project-manager.html:3186); '
    + 'nothing stored, nothing stale - the CPM/EVM absence is fail_500\'s question',
};

const readView = (sel) => {
  // The page-level prover's vocabularies, reused verbatim so the two cannot drift apart on what
  // counts as honest. Defined INSIDE the function: it executes in the browser, where a Node-scope
  // const does not exist (the first run threw ReferenceError: NAMES_STORED is not defined).
  const NAMES_STORED = /saved (copy|snapshot|version)|stored (brief|copy|plan)|from storage|loaded from|snapshot|cached|last (computed|updated|refreshed|generated)|from (an? )?earlier|previously (computed|generated)|as of |not (recomputed|regenerated)|showing (the )?(saved|stored|last)/i;
  const ANNOUNCES_FAILURE = /\b(failed|failure|couldn['’]?t|could not|unable to|went wrong|error|unavailable|not available|no connection|offline)\b/i;
  const el = sel && (document.getElementById(sel) || document.querySelector(`.${CSS.escape(sel)}`));
  const scope = el || document.body;
  const txt = (scope.innerText || '').replace(/\s+/g, ' ').trim();
  const sents = txt.split(/(?<=[.!?])\s+|\s*[|·]\s*/).map((s) => s.trim()).filter(Boolean);
  return {
    chars: txt.length,
    // figures are what these views exist to show; counted in the SAME scope as the sentences
    nums: [...scope.querySelectorAll('*')].filter((n) => !n.children.length
      && /^[₱$€£]?\s*-?\d[\d,]*(\.\d+)?\s*%?$/.test((n.textContent || '').trim())).length,
    storedSents: sents.filter((s) => NAMES_STORED.test(s)),
    failSents: sents.filter((s) => ANNOUNCES_FAILURE.test(s)),
  };
};

const browser = await chromium.launch();
const cells = [];
for (const pg of (ONE ? [ONE.replace(/\.html$/, '')] : PAGES)) {
  for (const t of viewTargets(pg)) {
    const rec = { page: pg, view: t.view, modal: t.modal };
    try {
      const ctx = await browser.newContext({ viewport: { width: 390, height: 844 },
        serviceWorkers: 'block' });
      if (!t.signedOut) await assertSignedIn(signIn(ctx, 'supervisor'));  // index V2/V3 run signed OUT by design
      const p = await ctx.newPage();
      await p.goto(`${ORIGIN}/${pg}.html${QUERY[pg] || ''}`, { waitUntil: 'domcontentloaded', timeout: 25000 });
      await p.waitForTimeout(3200);
      const opened = await openView(p, t);
      if (!opened.ok) {
        rec.ok = null; rec.verdict = `${opened.kind}: ${opened.why}`;
        cells.push(rec); await ctx.close(); continue;
      }
      const base = await p.evaluate(readView, t.modal);
      const isNew = (arr, baseArr) => (arr || []).filter((s) => !(baseArr || []).includes(s));
      // ── ATTRIBUTION: does driving THIS view invoke an edge function at all? ──
      let edgeCalls = 0;
      await ctx.route('**/functions/v1/**', (route) => {
        edgeCalls++;
        return route.fulfill({ status: 500, contentType: 'application/json',
          body: JSON.stringify({ error: 'upstream unavailable (fallback-views probe)' }) });
      });
      // writes held so the drive cannot touch the shared DB (same rail as every view family)
      await ctx.route('**/rest/v1/**', (route) => {
        const m = route.request().method();
        if (['POST', 'PATCH', 'PUT', 'DELETE'].includes(m)) {
          return route.fulfill({ status: 503, contentType: 'application/json',
            body: JSON.stringify({ message: 'probe: writes are held' }) });
        }
        return route.continue();
      });
      await p.keyboard.press('Escape').catch(() => {});
      await p.waitForTimeout(900);
      const re = await openView(p, t, { settleMs: 2600 });
      await p.waitForTimeout(2500);
      const failed = await p.evaluate(readView, t.modal);
      rec.edgeCalls = edgeCalls;
      const recompute = RECOMPUTE_FALLBACK[`${pg}|${t.view}`];
      if (edgeCalls && recompute) {
        rec.ok = null; rec.na = true;
        rec.verdict = `NA: the view's edge call failed but its fallback is a LIVE RECOMPUTE, not a `
          + `stored copy - the stale-as-current lie this oracle names cannot occur. ${recompute}`;
      } else if (!edgeCalls) {
        rec.ok = null; rec.na = true;
        rec.verdict = 'NA: driving this view invoked no edge function - it has no primary of its '
          + 'own to break, so fallback_engaged has no subject here (its reads are live REST, '
          + 'which is fail_500/retry_path territory)';
      } else if (!re.ok && failed.chars < 40) {
        rec.ok = null;
        rec.verdict = `with the view's edge call answered 500 the view rendered nothing `
          + `(${failed.chars} chars) - whether it SAYS the primary failed is fail_500's question`;
      } else {
        const stored = isNew(failed.storedSents, base.storedSents);
        const announced = isNew(failed.failSents, base.failSents);
        rec.storedText = stored.join(' | ').slice(0, 140) || undefined;
        rec.announceText = announced.join(' | ').slice(0, 140) || undefined;
        if (stored.length || announced.length) {
          rec.ok = true;
          rec.verdict = `the view's edge call was answered 500 (${edgeCalls}), content still `
            + `rendered (${failed.chars} chars, ${failed.nums} figures), and the view is honest: `
            + (stored.length ? `names a stored source ${JSON.stringify(stored[0].slice(0, 90))}`
                             : `announces the failure ${JSON.stringify(announced[0].slice(0, 90))}`);
        } else {
          rec.ok = false;
          rec.verdict = `the view's edge call was answered 500 (${edgeCalls}) and the view still `
            + `shows ${failed.nums} figures / ${failed.chars} chars with NOTHING new naming the `
            + `source or the failure - the fallback engaged silently`;
        }
      }
      await ctx.close();
    } catch (e) { rec.ok = null; rec.verdict = String(e.message || e).slice(0, 140); }
    cells.push(rec);
    console.log(`  ${(rec.page + '#' + rec.view).padEnd(24)} ${rec.ok === true ? 'PASS' : rec.ok === false ? 'FAIL' : rec.na ? 'NA' : 'UNGRADED'}  ${String(rec.verdict).slice(0, 74)}`);
  }
}
await browser.close();
const ok = cells.filter((c) => c.ok === true).length;
const bad = cells.filter((c) => c.ok === false).length;
// A NARROWED RUN MUST NOT CLOBBER THE FULL ONE: this file is read downstream (gates and
// bank_prover_reports), so a --page/--case spot-check overwriting a whole sweep's verdicts
// corrupts the BANK, not just a log. Measured on prove_retry_path 2026-08-27.
writeFileSync((ONE ? 'fallback_views_report.partial.json' : 'fallback_views_report.json'), JSON.stringify({
  totals: { cells: cells.length, pass: ok, fail: bad, ungraded: cells.length - ok - bad },
  views: cells,
}, null, 1));
console.log(`\n  ${cells.length} cell(s): ${ok} PASS · ${bad} FAIL · ${cells.length - ok - bad} ungraded — fallback_views_report.json`);
process.exit(bad ? 1 : 0);
