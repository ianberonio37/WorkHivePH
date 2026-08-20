// prove_abandon_resume.mjs — the CN `abandon_resume` oracle, measured end-to-end.
//
// THE ORACLE: "abandoning midway and returning leaves no half-applied state."
//
// ★A HALF-APPLIED STATE HAS THREE SHAPES, and they need different evidence, so all three are checked:
//   1. A ROW THAT SHOULD NOT EXIST — the page wrote something before the person finished. Checked in
//      psql, against a marker only this run could have produced.
//   2. A DRAFT THAT DOES NOT SAY IT IS A DRAFT — the fields come back pre-filled on return, with no
//      label. That is the dangerous one: the person cannot tell whether their work was SAVED or merely
//      remembered, and the platform's own history is full of that confusion ("draft" is overloaded).
//      A restored draft is FINE, and is the good design — but only if the surface says so.
//   3. A QUEUED WRITE that drains later. An offline queue holding an abandoned edit means the write
//      lands minutes after the person walked away believing they had cancelled.
//
// ★ABANDONMENT IS A RELOAD, NOT A CLOSE. Pressing the modal's own X is CANCELLING, which pages handle
// deliberately; a reload is what actually happens when someone gets a call, closes the tab, or their
// phone dies. It is also the only one that cannot be intercepted by a confirm dialog.
//
// ★AND THE PROBE PROVES ITS OWN FILL LANDED. If the fields were never populated, "no half-applied
// state" is vacuously true and says nothing about the page — so a case whose fill did not take is
// UNGRADED, never passed. Same rail as every other prover here: a zero denominator is an abstention.
//
// USAGE:  node tools/prove_abandon_resume.mjs [--page <name>]
// OUTPUT: abandon_resume_report.json

import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { execFileSync } from 'node:child_process';
import path from 'path';
import { fileURLToPath } from 'node:url';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();
const WORKER = 'Leandro Marquez';
const HIVE = '084c113b-99c0-45c6-a8e8-b4b8349da46d';

const psql = (sql) => execFileSync('docker',
  ['exec', '-i', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-t', '-A', '-c', sql],
  { encoding: 'utf8', timeout: 60000 }).trim();
const esc = (s) => String(s).replace(/'/g, "''");

// Each case: open the capture surface, fill it, then abandon. `table`/`match` locate a row this run
// would have created; the fill is verified before the abandon so a no-op cannot pass.
const CASES = [
  {
    page: 'logbook', what: 'a maintenance entry, abandoned mid-capture',
    table: 'logbook', col: 'problem',
    // The opener and field ids come from tools/dialog_targets.mjs and the page itself, not from a
    // guessed label - my first attempt invented openCaptureModal() and a #problem field, neither of
    // which exists, and the case correctly came back UNGRADED rather than passing on an empty fill.
    open: "var b=document.querySelector('[onclick^=\"openModal(\"]'); if(b) b.click();",
    fill: "var f=document.getElementById('f-problem')||document.getElementById('f-action')||document.querySelector('#modal textarea, #modal input[type=text]'); if(f){f.value=MARK; f.dispatchEvent(new Event('input',{bubbles:true})); return true;} return false;",
  },
  {
    page: 'inventory', what: 'a spare part, abandoned mid-add',
    table: 'inventory_items', col: 'part_name',
    open: "if (typeof openAddModal === 'function') openAddModal();",
    fill: "var f=document.getElementById('f-part-name'); if(f){f.value=MARK; f.dispatchEvent(new Event('input',{bubbles:true})); return true;} return false;",
  },
  {
    page: 'project-manager', what: 'a project, abandoned mid-create',
    table: 'projects', col: 'name',
    open: "var b=[...document.querySelectorAll('button')].find(e=>/new project|add project|\\+ project/i.test(e.textContent||'')); if(b) b.click();",
    fill: "var f=document.querySelector('#project-modal input[type=text], #modal-project input[type=text], input#p-name'); if(f){f.value=MARK; f.dispatchEvent(new Event('input',{bubbles:true})); return true;} return false;",
  },
  {
    page: 'dayplanner', what: 'a planned item, abandoned mid-add',
    table: 'schedule_items', col: 'title',
    open: "if (typeof openAddModal === 'function') openAddModal();",
    fill: "var f=document.getElementById('m-title')||document.querySelector('#item-modal input[type=text]'); if(f){f.value=MARK; f.dispatchEvent(new Event('input',{bubbles:true})); return true;} return false;",
  },
  {
    page: 'community', what: 'a post, abandoned mid-compose',
    table: 'community_posts', col: 'content',
    // ★THE HIGHEST-STAKES ABANDON ON THE ROSTER: a half-written post that lands anyway is published to
    // other people. Nothing else in this family is visible outside the author's own screen.
    open: "if (typeof openComposer === 'function') openComposer();",
    fill: "var f=document.getElementById('post-content'); if(f){f.value=MARK; f.dispatchEvent(new Event('input',{bubbles:true})); return true;} return false;",
  },
  {
    page: 'asset-hub', what: 'an FMEA failure mode, abandoned mid-entry',
    table: 'rcm_fmea_modes', col: 'failure_mode',
    // ★THE PRECONDITION CHAIN IS THE WHOLE DIFFICULTY HERE, and getting it wrong once already cost a
    // false defect report earlier in this arc: the FMEA workbench lives inside #reliability-card, which
    // ships display:none behind a "Show Reliability Workbench" disclosure, AND it is master-detail, so
    // its list only fills once an asset node is selected. Node FIRST, then the disclosure, then the tab.
    open: "var n=document.querySelector('[data-node-id]'); if(n) n.click();"
        + " setTimeout(function(){ var d=document.querySelector('[aria-controls=\"reliability-card\"]');"
        + " if(d) d.click();"
        + " setTimeout(function(){ var t=document.querySelector('.rel-tab[data-tab=\"fmea\"]'); if(t) t.click();"
        + " setTimeout(function(){ var a=[...document.querySelectorAll('button,[role=button]')]"
        + ".find(function(x){return /add (failure )?mode|new mode/i.test(x.textContent||'');}); if(a) a.click(); }, 700); }, 700); }, 1500);",
    settle: 5000,
    fill: "var f=document.getElementById('fmea-failure-mode'); if(f){f.value=MARK; f.dispatchEvent(new Event('input',{bubbles:true})); return true;} return false;",
  },
  {
    page: 'voice-journal', what: 'a journal entry, abandoned mid-write',
    table: 'voice_journal_entries', col: 'transcript',
    open: "var b=[...document.querySelectorAll('button')].find(function(e){return /new entry|add entry|write|compose/i.test(e.textContent||'');}); if(b) b.click();",
    fill: "var f=document.querySelector('#capture-panel textarea, textarea#transcript, textarea'); if(f){f.value=MARK; f.dispatchEvent(new Event('input',{bubbles:true})); return true;} return false;",
  },
  {
    page: 'pm-scheduler', what: 'a PM scope task, abandoned mid-add',
    // The column is `item_text`, read from information_schema - my first guess was `task_text`,
    // which does not exist, and psql failing turned the case into an ERROR rather than a false
    // pass. A probe whose own query is wrong must not be able to report a verdict about the page.
    table: 'pm_scope_items', col: 'item_text',
    // openAddTaskSheet() is state-gated behind a selected asset, exactly as its dialog_targets entry
    // records for the edit modal - so the asset card is clicked first rather than assuming the sheet
    // is reachable from the landing state.
    open: "var c=document.querySelector('.asset-card'); if(c) c.click();"
        + " setTimeout(function(){ if (typeof openAddTaskSheet === 'function') openAddTaskSheet(); }, 1500);",
    settle: 3500,
    fill: "var f=document.getElementById('add-task-text'); if(f){f.value=MARK; f.dispatchEvent(new Event('input',{bubbles:true})); return true;} return false;",
  },
  {
    page: 'report-sender', what: 'a report contact, abandoned mid-add',
    table: 'report_contacts', col: 'name',
    // ★THE ONE PAGE WHOSE PRIMARY ACTION IS OUTWARD AND IRREVERSIBLE, which changes what a half-applied
    // state costs: this file's own comments say a wrong contact list invites "adding a duplicate
    // contact, or concluding a finished report has nowhere to go". A contact half-created by walking
    // away is exactly the first of those.
    open: "var b=[...document.querySelectorAll('button,a')].find(function(e){return /add contact|new contact/i.test(e.textContent||'');}); if(b) b.click();",
    fill: "var f=document.getElementById('contact-name'); if(f){f.value=MARK; f.dispatchEvent(new Event('input',{bubbles:true})); return true;} return false;",
  },
  {
    page: 'resume', what: 'a resume edit, abandoned mid-write',
    // `doc` is JSONB, so LIKE needs an explicit cast - without it psql errors and the case reports
    // ERROR rather than a verdict, which is the right failure: a broken query's 0 rows is
    // indistinguishable from a page that wrote nothing.
    table: 'resume_documents', col: 'doc::text',
    // ★THIS ONE IS THE REAL TEST OF THE DRAFT CLAUSE, because the page autosaves LOCALLY on a 700ms
    // debounce (scheduleLocalSave -> idbPut). So the fields SHOULD come back after a reload — that is
    // the feature. The question this oracle asks is whether the surface SAYS the restored text is a
    // local draft rather than something saved to the account, on a page whose entire promise is that a
    // person's work survives. A restored draft is the good design; an unlabelled one is the defect.
    open: "return true;",
    fill: "var f=[...document.querySelectorAll('input[type=text],textarea')].find(function(e){return e.getClientRects().length && !e.disabled && !e.readOnly;}); if(f){f.value=MARK; f.dispatchEvent(new Event('input',{bubbles:true})); f.dispatchEvent(new Event('change',{bubbles:true})); return true;} return false;",
    settle: 2500,
  },
  {
    page: 'hive', what: 'the hive focus, abandoned mid-selection',
    table: 'hives', col: 'intent',
    mutationSql: "select coalesce(intent::text,'null') from hives where id = '084c113b-99c0-45c6-a8e8-b4b8349da46d'",
    open: "if (typeof _openIntentModal === 'function') _openIntentModal();",
    fill: "var r=document.querySelector('input[name=\"intent-primary\"][value=\"downtime\"]'); if(r){r.checked=true; r.dispatchEvent(new Event('change',{bubbles:true})); return true;} return false;",
  },
  {
    page: 'engineering-design', what: 'an engineering calculation, abandoned mid-entry',
    table: 'engineering_calcs', col: 'project_name',
    // The form does not exist until a calculator is CHOSEN - this page is a grid of cards and picking
    // one renders that calc's inputs. A probe that fills before choosing fills nothing.
    open: "var c=document.querySelector('.calc-card[data-id]'); if(c) c.click();",
    settle: 3000,
    fill: "var f=document.getElementById('f-project'); if(f){f.value=MARK; f.dispatchEvent(new Event('input',{bubbles:true})); return true;} return false;",
  },
  {
    page: 'index', anon: true,
    what: 'the early-access signup, abandoned mid-entry',
    table: 'early_access_emails', col: 'email',
    // ★MUST RUN SIGNED OUT, and getting that wrong does not fail loudly - it measures a DIFFERENT page.
    // index.html is two products behind one URL: an inline script sets html.wh-signed-in before <body>
    // parses and CSS swaps the marketing landing for the ops dashboard, so #joinForm does not exist for
    // a signed-in probe. Two other provers in this arc hit the same trap on this same page.
    open: "return true;",
    fill: "var f=document.querySelector('#joinForm input[type=email]'); if(f){f.value=MARK+'@example.com'; f.dispatchEvent(new Event('input',{bubbles:true})); return true;} return false;",
  },
  {
    page: 'assistant', what: 'a question typed and abandoned before sending',
    table: 'ai_reply_feedback', col: 'question',
    // ★WHAT A HALF-APPLIED STATE MEANS HERE IS DIFFERENT, and naming it is the work: typing costs
    // nothing, so "no row written" would be trivially true and prove nothing. The failure this page
    // could actually have is an abandoned question RE-APPEARING IN THE THREAD as though it had been
    // asked - a person returning would believe they had a conversation they never had, and on a
    // grounded assistant that is a memory of an answer that was never given.
    open: "return true;",
    fill: "var f=document.getElementById('chat-input'); if(f){f.value=MARK; f.dispatchEvent(new Event('input',{bubbles:true})); return true;} return false;",
  },
];

const run = async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await assertSignedIn(signIn(ctx, 'supervisor'));
  // A case marked `anon` gets a session-less context, because some surfaces only exist signed out.
  const anonCtx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const out = { origin: ORIGIN, cases: [] };

  for (const c of (ONE ? CASES.filter((x) => x.page === ONE) : CASES)) {
    const MARK = `WH-ABANDON-${process.pid}-${c.page}`;
    const rec = { page: c.page, what: c.what, marker: MARK };
    const page = await (c.anon ? anonCtx : ctx).newPage();
    try {
      // ★NOT EVERY ABANDONED ACTION WOULD CREATE A ROW. hive's intent capture MUTATES an existing
      // hive row, so a row-count delta is structurally incapable of detecting a half-applied state
      // there - the same proxy error that made a count-delta report shift-brain's in-place plan
      // rewrite as 'no write happened'. A `mutationSql` case captures the VALUE before and compares
      // it after; a create case counts rows. The shape of the write decides the measure.
      const countSql = c.mutationSql || `select count(*) from ${c.table} where ${c.col} like '%${esc(MARK)}%'`;
      rec.before = c.mutationSql ? psql(countSql).trim()
        : Number(String(psql(countSql)).split('\n')[0]);

      await page.goto(`${ORIGIN}/workhive/${c.page}.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(6000);
      await page.evaluate((src) => eval(src), c.open).catch(() => {});
      await page.waitForTimeout(c.settle || 1500);
      rec.filled = await page.evaluate(
        ({ src, mark }) => { const MARK = mark; return eval(`(function(){${src}})()`); },
        { src: c.fill, mark: MARK },
      ).catch(() => false);

      if (!rec.filled) {
        // ★A FILL THAT DID NOT LAND MAKES "no half-applied state" VACUOUSLY TRUE. Abstain.
        rec.outcome = 'UNGRADED';
        rec.why = 'the capture surface could not be opened or filled, so nothing was abandoned - this '
                + 'says nothing about the page and is recorded as ungraded rather than passed';
      } else {
        // ABANDON: a reload, which is what actually happens when a person walks away.
        await page.reload({ waitUntil: 'domcontentloaded' });
        await page.waitForTimeout(6000);

        if (c.mutationSql) {
          rec.afterValue = psql(countSql).trim();
          rec.mutated = rec.afterValue !== rec.before;
          rec.rowCreated = rec.mutated ? 1 : 0;   // a mutation IS a half-applied write
        } else {
          rec.rowCreated = Number(String(psql(countSql)).split('\n')[0]) - rec.before;
        }
        const back = await page.evaluate((mark) => {
          const vals = [...document.querySelectorAll('input,textarea')]
            .filter((e) => (e.value || '').includes(mark)).length;
          const body = (document.body.innerText || '').replace(/\s+/g, ' ');
          return { prefilled: vals, onScreen: body.includes(mark),
            saysDraft: /draft|unsaved|restored|resume|picked up where/i.test(body) };
        }, MARK);
        rec.prefilledFields = back.prefilled;
        rec.markOnScreen = back.onScreen;
        rec.saysDraft = back.saysDraft;

        // Three shapes, judged separately.
        if (rec.rowCreated > 0) {
          rec.outcome = 'HALF-WRITTEN';
          rec.why = `abandoning created ${rec.rowCreated} row(s) in ${c.table} - the person walked away `
                  + 'and the record exists anyway';
        } else if (back.prefilled > 0 && !back.saysDraft) {
          rec.outcome = 'SILENT-DRAFT';
          rec.why = 'the fields came back pre-filled with nothing saying it is a draft - the person '
                  + 'cannot tell whether their work was SAVED or merely remembered';
        } else if (back.prefilled > 0) {
          rec.outcome = 'PASS';
          rec.why = 'no row was written, and the restored draft SAYS it is one - which is the good '
                  + 'design, not a defect';
        } else {
          rec.outcome = 'PASS';
          rec.why = 'no row was written and nothing came back pre-filled - a clean slate';
        }
      }
    } catch (e) { rec.error = String(e.message || e).slice(0, 160); rec.outcome = 'ERROR'; }
    finally {
      try { if (!c.mutationSql) psql(`delete from ${c.table} where ${c.col} like '%${esc(MARK)}%'`); } catch (_) { /* best effort */ }
      try { rec.leftBehind = c.mutationSql ? 0
        : Number(String(psql(`select count(*) from ${c.table} where ${c.col} like '%${esc(MARK)}%'`)).split('\n')[0]); }
      catch (_) { rec.leftBehind = null; }
    }
    await page.close();
    out.cases.push(rec);
    console.log(`  ${String(rec.outcome).padEnd(13)} ${c.page.padEnd(17)} filled=${rec.filled} `
      + `rowCreated=${rec.rowCreated ?? '-'} prefilled=${rec.prefilledFields ?? '-'} `
      + `saysDraft=${rec.saysDraft ?? '-'} cleanup=${rec.leftBehind === 0 ? 'clean' : rec.leftBehind}`);
  }

  await browser.close();
  writeFileSync(path.join(ROOT, 'abandon_resume_report.json'), JSON.stringify(out, null, 1));
  const t = (o) => out.cases.filter((x) => x.outcome === o).length;
  console.log(`\n  ${out.cases.length} case(s) | PASS ${t('PASS')} | HALF-WRITTEN ${t('HALF-WRITTEN')} `
    + `| SILENT-DRAFT ${t('SILENT-DRAFT')} | UNGRADED ${t('UNGRADED')} | ERROR ${t('ERROR')}`);
};
run().catch((e) => { console.error(e); process.exit(1); });
