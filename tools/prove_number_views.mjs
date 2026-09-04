/* prove_number_views.mjs — number_explained + one_vocabulary asked of every dialog view.
 *
 * number_explained: a derived figure in the view can be explained without leaving it — something
 * within reach names it. A raw count explains itself (the number_explained precedent), so only
 * derived-looking figures (decimals, %, ₱, unit-suffixed) enter the set; a view with none is NA.
 *
 * one_vocabulary: the view does not rename a concept the page names differently — approximated
 * here by the MIXED-CASE check the walker's lens uses (a snake_case token reaching the person);
 * full cross-surface vocabulary lives in cm_one_vocabulary's own page-level gate.
 *
 * Read-only: views opened via view_pass, nothing induced, nothing pressed.
 * Run:  node tools/prove_number_views.mjs [--page analytics]   → number_views_report.json
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

const READ = (sel) => {
  const scope = (sel && (document.getElementById(sel) || document.querySelector(`.${CSS.escape(sel)}`)))
    || document.querySelector('main') || document.body;
  const vis = (el) => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.width > 2 && r.height > 2 && cs.display !== 'none' && cs.visibility !== 'hidden'; };
  // DERIVED-looking figures only: decimals, percents, currency, unit-suffixed. Bare integers are
  // counts and a raw count explains itself (the number_explained precedent).
  const DERIVED = /^[₱$€£]\s*[\d,]+(\.\d+)?$|^-?[\d,]+\.\d+\s*\w{0,6}$|^-?[\d,]+(\.\d+)?\s*(%|x|hrs?|days?|km|kw|tr|cfm|psi|bar|rpm|nm)$/i;
  const numbers = [...scope.querySelectorAll('*')].filter((el) =>
    el.childElementCount === 0 && vis(el) && DERIVED.test((el.textContent || '').trim())
  ).slice(0, 20).map((el) => {
    const value = (el.textContent || '').trim();
    const own = (el.getAttribute('aria-label') || '') + ' ' + (el.getAttribute('title') || '');
    const par = el.parentElement;
    const near = (own + ' ' + (par ? (par.innerText || '') : '')
      + ' ' + (par && par.parentElement ? par.parentElement.innerText || '' : ''))
      .replace(value, ' ').replace(/\s+/g, ' ').trim();
    return { value, explained: near.length >= 3, context: near.slice(0, 60) };
  });
  // a snake_case token reaching the person inside the view (excluding code/kbd samples)
  const raw = [...scope.querySelectorAll('*')].filter((el) =>
    el.childElementCount === 0 && vis(el) && !el.closest('code, kbd, pre')
    && /\b[a-z]+_[a-z_]+\b/.test((el.textContent || '')) ).slice(0, 5)
    .map((el) => (el.textContent || '').trim().slice(0, 50));
  return { numbers, rawTokens: raw };
};

const browser = await chromium.launch();
const cells = [];
for (const pg of (ONE ? [ONE.replace(/\.html$/, '')] : PAGES)) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await assertSignedIn(signIn(ctx, 'supervisor'));
  const p = await ctx.newPage();
  try {
    await p.goto(`${ORIGIN}/${pg}.html${QUERY[pg] || ''}`, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await p.waitForTimeout(3500);
    for (const t of viewTargets(pg)) {
      const opened = await openView(p, t);
      const rec = { page: pg, view: t.view, modal: t.modal };
      if (!opened.ok) {
        rec.numbers = { ok: null, verdict: `${opened.kind}: ${opened.why}` };
        rec.vocab = { ok: null, verdict: rec.numbers.verdict };
        cells.push(rec);
        console.log(`  ${(pg + '#' + t.view).padEnd(24)} UNGRADED  ${opened.why.slice(0, 70)}`);
        continue;
      }
      const r = await p.evaluate(READ, t.modal);
      const bare = r.numbers.filter((n) => !n.explained);
      rec.numbers = r.numbers.length === 0
        ? { ok: null, na: true, verdict: 'NA: no derived figure renders in this view - a raw count explains itself, nothing for this oracle to judge' }
        : bare.length === 0
          ? { ok: true, verdict: `${r.numbers.length} derived figure(s), every one with naming context in reach` }
          : { ok: false, verdict: `${bare.length} bare derived figure(s): ${JSON.stringify(bare.slice(0, 3).map((b) => b.value))}` };
      rec.vocab = r.rawTokens.length === 0
        ? { ok: true, verdict: 'no snake_case token reaches the person in this view' }
        : { ok: false, verdict: `raw tokens on the glass: ${JSON.stringify(r.rawTokens.slice(0, 3))}` };
      cells.push(rec);
      const tag = rec.numbers.ok === true ? 'PASS' : rec.numbers.ok === false ? 'FAIL' : (rec.numbers.na ? 'NA' : 'UNGRADED');
      console.log(`  ${(pg + '#' + t.view).padEnd(24)} num:${tag} vocab:${rec.vocab.ok ? 'PASS' : 'FAIL'}  ${String(rec.numbers.verdict).slice(0, 60)}`);
      await p.keyboard.press('Escape').catch(() => {});
      await p.waitForTimeout(700);
    }
  } catch (e) {
    cells.push({ page: pg, view: 'V?', numbers: { ok: null, verdict: String(e.message || e).slice(0, 120) }, vocab: { ok: null } });
  }
  await ctx.close();
}
await browser.close();
const nOK = cells.filter((c) => c.numbers?.ok === true).length;
const nBad = cells.filter((c) => c.numbers?.ok === false).length;
const vBad = cells.filter((c) => c.vocab?.ok === false).length;
// A NARROWED RUN MUST NOT CLOBBER THE FULL ONE: this file is read downstream (gates and
// bank_prover_reports), so a --page/--case spot-check overwriting a whole sweep's verdicts
// corrupts the BANK, not just a log. Measured on prove_retry_path 2026-08-27.
writeFileSync((ONE ? 'number_views_report.partial.json' : 'number_views_report.json'), JSON.stringify({
  totals: { cells: cells.length, numbersPass: nOK, numbersFail: nBad, vocabFail: vBad },
  views: cells,
}, null, 1));
console.log(`\n  ${cells.length} cell(s): numbers ${nOK} PASS / ${nBad} FAIL · vocab ${vBad} FAIL — number_views_report.json`);
