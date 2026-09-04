/* prove_cost_views.mjs — the what_does_it_cost oracle asked of every (page, view) cell.
 *
 * The oracle: "cost, hold and reward are stated before commitment, not after." Its V1 precedent
 * (community feed) banks NOT-APPLICABLE where nothing is committed, and the FLOWS in
 * prove_cost_before_commit.mjs carry DECLARED per-flow subjects for the eight costed flows. This
 * prover fills the grid between them, per view, with a judgment that never manufactures:
 *
 *   NA        — the view contains NO commit control: nothing is committed, so no disclosure could
 *               be owed. Proven by enumeration (the controls found are recorded).
 *   PASS      — a commit control exists AND cost/hold/reward vocabulary is on the view before any
 *               press ("stated before commitment").
 *   UNGRADED  — a commit control exists and no vocabulary shows. Whether cost/hold/reward has a
 *               SUBJECT there is a declared judgment (a free Save owes nothing; an exam owes its
 *               pass mark) — recorded for the FLOWS list, never failed on a guess and never
 *               auto-NA'd (that would blind the oracle to the exam-modal class).
 *
 * V1 = the base page; V2/V3 = dialog_targets views opened via view_pass (reach healthy, read at
 * rest — this oracle needs no induction at all: it reads what is stated BEFORE commitment).
 *
 * Run:  node tools/prove_cost_views.mjs [--page inventory]   → cost_views_report.json
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

// the same vocabularies prove_cost_before_commit grounds its judgments in
const COST_SRC = ['\\bcosts?\\b', '\\bcredits?\\b', '\\bfee\\b', 'php\\s*\\d', '\\u20b1\\s*\\d',
  '\\bprice\\b', 'deduct', 'uses \\d', 'consumes?', 'will use', 'from stock', 'on hand',
  'quota', 'remaining', 'pass mark', '\\bhold\\b', '\\breserv', 'set aside',
  '\\+\\s*\\d+\\s*xp', '\\bxp\\b', 'earns?\\b', 'reward'].join('|');
// a commit is a control whose label is an irreversible-ish verb — the same shape the comprehension
// lens uses; excludes pure-navigation and dismiss controls
const COMMIT_SRC = ['\\bsave\\b', '\\bsubmit\\b', '\\bpost\\b', '\\bsend\\b', '\\bpublish\\b',
  '\\bconfirm\\b', '\\bpay\\b', '\\bbuy\\b', '\\border\\b', '\\bhail\\b', '\\buse\\b',
  '\\brestock\\b', '\\btake exam\\b', '\\bstart exam\\b', '\\bcreate\\b', '\\bregister\\b',
  '\\bapply\\b', '\\bverify\\b', '\\bapprove\\b', '\\bdelete\\b', '\\bremove\\b'].join('|');

// DECLARED subjects for commit controls the vocabulary sweep cannot judge (2026-08-22, each
// grounded in the page/DB): a FREE commit owes no cost/hold/reward disclosure, so the cell is
// NA-with-reason; a control listed here as costed would instead demand the statement. Same shape
// as prove_cost_before_commit's FLOWS.applies - the judgment is declared, never guessed.
const DECLARED = {
  'logbook#V1': 'free: registering an asset writes a row and costs nothing - no credits, no hold, no reward',
  'logbook#V2': 'free: deleting an entry costs nothing; the CONSEQUENCE of deletion is the what_happens_next oracle\'s subject, not a price',
  'logbook#V3': 'free: asset registration costs nothing',
  'pm-scheduler#V3': 'free: editing a PM asset costs nothing',
  'project-manager#V2': 'free: deleting a project costs nothing; consequence-wording is a different oracle',
  'asset-hub#V1': 'free: Approve applies an already-generated suggestion (generation is where ai_cost_log telemetry accrues, at no user credit cost); approval itself moves a status',
  'resume#V1': 'free: saving the resume costs nothing',
  'report-sender#V1': 'free to the person: reports send through the platform\'s own email account - no user credits, no hold, no reward',
  'report-sender#V3': 'free: saving a contact costs nothing',
  'project-report#V1': 'free: a local PDF export',
  'assistant#V1': 'free-tier AI through the gateway: no credit price to the person; the real constraint is the RATE LIMIT, whose legibility is the rate_limit_legible/quota oracles\' subject, not a pre-commit price',
  'engineering-design#V2': 'free: deleting a saved calculation costs nothing',
  'analytics-report#V1': 'free: a local PDF export',
};

const readCell = (scopeSel) => ({ scopeSel, costSrc: COST_SRC, commitSrc: COMMIT_SRC });
const READ = ({ scopeSel, costSrc, commitSrc }) => {
  const scope = (scopeSel && (document.getElementById(scopeSel)
    || document.querySelector(`.${CSS.escape(scopeSel)}`))) || document.querySelector('main') || document.body;
  const vis = (el) => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.width > 2 && r.height > 2 && cs.display !== 'none' && cs.visibility !== 'hidden'; };
  const COMMIT = new RegExp(commitSrc, 'i');
  const commits = [...scope.querySelectorAll('button, [role="button"], input[type="submit"]')]
    .filter(vis)
    .map((el) => (el.innerText || el.value || el.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim())
    .filter((t) => t && COMMIT.test(t)).slice(0, 10);
  const txt = (scope.innerText || '').replace(/\s+/g, ' ').trim();
  return { commits, statesCost: new RegExp(costSrc, 'i').test(txt), chars: txt.length };
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
    const grade = (view, r, extra) => {
      const cell = { page: pg, view, ...extra };
      if (!r) { cell.ok = null; cell.verdict = 'view could not be read'; }
      else if (!r.commits.length) {
        cell.ok = null; cell.na = true;
        cell.verdict = `NA: no commit control in this view (${r.chars} chars read; nothing is `
          + 'committed here, so no cost/hold/reward disclosure could be owed)';
      } else if (r.statesCost) {
        cell.ok = true;
        cell.verdict = `commit control(s) ${JSON.stringify(r.commits.slice(0, 3))} with cost/hold/reward `
          + 'vocabulary on the view BEFORE any press';
      } else if (DECLARED[`${pg}#${view}`]) {
        cell.ok = null; cell.na = true;
        cell.verdict = `NA by declaration: commit control(s) ${JSON.stringify(r.commits.slice(0, 3))} — `
          + DECLARED[`${pg}#${view}`];
      } else {
        cell.ok = null;
        cell.verdict = `UNGRADED-for-declaration: commit control(s) ${JSON.stringify(r.commits.slice(0, 3))} `
          + 'show no cost vocabulary — whether cost/hold/reward has a SUBJECT here is a declared '
          + 'judgment (a free Save owes nothing; an exam owes its pass mark). Queue for the '
          + 'cost_before_commit FLOWS list.';
      }
      cells.push(cell);
      console.log(`  ${(pg + '#' + view).padEnd(26)} ${cell.ok === true ? 'PASS' : cell.na ? 'NA' : 'UNGRADED'}  ${String(cell.verdict).slice(0, 76)}`);
    };
    grade('V1', await p.evaluate(READ, readCell(null)));
    for (const t of viewTargets(pg)) {
      const opened = await openView(p, t);
      if (!opened.ok) {
        cells.push({ page: pg, view: t.view, modal: t.modal, ok: null,
                     verdict: `${opened.kind}: ${opened.why}` });
        console.log(`  ${(pg + '#' + t.view).padEnd(26)} UNGRADED  ${opened.why.slice(0, 76)}`);
        continue;
      }
      grade(t.view, await p.evaluate(READ, readCell(t.modal)), { modal: t.modal });
      await p.keyboard.press('Escape').catch(() => {});
      await p.waitForTimeout(700);
    }
  } catch (e) {
    cells.push({ page: pg, view: 'V1', ok: null, verdict: String(e.message || e).slice(0, 140) });
  }
  await ctx.close();
}
await browser.close();
const graded = cells.filter((c) => c.ok === true).length;
const na = cells.filter((c) => c.na).length;
// A NARROWED RUN MUST NOT CLOBBER THE FULL ONE: this file is read downstream (gates and
// bank_prover_reports), so a --page/--case spot-check overwriting a whole sweep's verdicts
// corrupts the BANK, not just a log. Measured on prove_retry_path 2026-08-27.
writeFileSync((ONE ? 'cost_views_report.partial.json' : 'cost_views_report.json'), JSON.stringify({
  totals: { cells: cells.length, pass: graded, na, ungraded: cells.length - graded - na },
  views: cells,
}, null, 1));
console.log(`\n  ${cells.length} cell(s): ${graded} PASS · ${na} NA · ${cells.length - graded - na} ungraded — cost_views_report.json`);
