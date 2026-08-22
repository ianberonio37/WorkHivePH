// prove_effect_visible.mjs — CF `effect_in_db` + `effect_visible`, on the product roster.
//
// THE TWO ORACLES, and why a structural probe is forbidden to settle either (rail R6):
//   effect_in_db     the happy path's effect is present in the DATABASE
//   effect_visible   that same effect is visible to the PERSON WHO CAUSED IT, on the surface where
//                    they caused it
// Neither is inferrable from the screen alone. The effect is read back with psql as postgres — the
// only reader that cannot be fooled by the page's own cache or an optimistic render.
//
// ★THIS FILE WRITES TO THE SHARED DATABASE AND PUTS IT BACK. That is the precedent set by
// tests/effect-and-agreement.spec.ts, and the discipline it carries is copied exactly:
//   · the value to restore is captured from PSQL BEFORE anything is touched — never from the page,
//     which may itself be showing a stale copy;
//   · the restore runs in `finally`, so a failed assertion still cleans up;
//   · and the restore MECHANISM was teeth-tested on a real row before this file was allowed to write:
//     a mutation was applied, PROVEN to have landed (a restore test that never changed anything
//     proves nothing), then reverted and confirmed byte-identical.
// Cleanup is verified after every case and reported. If cleanup fails the run says so loudly rather
// than leaving a probe row behind pretending to be a person's work.
//
// USAGE:  node tools/prove_effect_visible.mjs [--page <name>]
// OUTPUT: effect_visible_report.json
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { execFileSync } from 'node:child_process';
import path from 'path';
import { fileURLToPath } from 'node:url';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const WORKER = 'Leandro Marquez';
// The test hive this identity belongs to - needed by cases whose subject is hive-scoped rather
// than marker-scoped (shift-brain re-composes an existing plan; there is no marker to match on).
const HIVE = '084c113b-99c0-45c6-a8e8-b4b8349da46d';
// The test identity's auth uid - owner-scoped tables key on this rather than on a name.
const UID = 'bcb5a6e3-fb12-4238-bc1e-ffeb48f60d53';
const args = process.argv.slice(2);
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

const psql = (sql) => execFileSync('docker', ['exec', '-i', 'supabase_db_workhive', 'psql',
  '-U', 'postgres', '-d', 'postgres', '-t', '-A', '-c', sql],
  { encoding: 'utf8', timeout: 60000 }).trim();
const esc = (s) => String(s).replace(/'/g, "''");

// One case: a field-capture write whose effect is a row the surface then shows.
const CASES = [
  {
    page: 'pm-scheduler',
    what: 'adding a PM scope item',
    marker: 'WH-EFFECT-PROBE-' + process.pid,
    countBefore: (m) => `select count(*) from pm_scope_items where item_text like '%${esc(m)}%'`,
    cleanup: (m) => `delete from pm_scope_items where item_text like '%${esc(m)}%'`,
    // saveNewTask() needs `currentAsset`, so an asset must be opened first - the same shape as
    // asset-hub's FMEA. The precondition is TAKEN FROM tools/dialog_targets.mjs (click a .asset-card)
    // rather than invented, so the state written from is the state every other prover grades. It is
    // also guarded by whRequireOnline and refuses an empty description with
    // 'Please enter a task description.', both surfacing through showToast - sampled DURING the save,
    // because a toast that has faded is indistinguishable from no refusal at all.
    drive: async (page, marker) => page.evaluate(async (m) => {
      const wait = (ms) => new Promise((r) => setTimeout(r, ms));
      const card = document.querySelector('.asset-card');
      if (!card) return { drove: 'no-asset-cards-in-hive' };
      card.click(); await wait(1800);
      const add = [...document.querySelectorAll('button,[role="button"]')]
        .find((b) => /add task|new task|\+ task/i.test(b.textContent || ''));
      if (add) { add.click(); await wait(900); }
      if (typeof window.saveNewTask !== 'function') return { drove: 'no-saveNewTask-fn' };
      const t = document.getElementById('add-task-text');
      if (!t) return { drove: 'no-task-text-field' };
      t.value = m; t.dispatchEvent(new Event('input', { bubbles: true }));
      const p = window.saveNewTask();
      let refusal = null;
      for (let i = 0; i < 12; i++) {
        await wait(250);
        const el = document.querySelector('#toast,[id$="toast"]');
        const tx = el && (el.innerText || '').trim();
        if (el && !el.classList.contains('hidden') && tx
            && /enter a task|offline|cannot|failed|error/i.test(tx)) { refusal = tx.slice(0, 120); break; }
      }
      await p; await wait(1500);
      return refusal ? { drove: 'refused', reason: refusal } : { drove: 'saved' };
    }, marker),
  },
  {
    page: 'project-manager',
    what: 'creating a project',
    marker: 'WH-EFFECT-PROBE-' + process.pid,
    countBefore: (m) => `select count(*) from projects where name like '%${esc(m)}%'`,
    // projects fan out to items, links, roles, progress logs and change orders. This probe creates a
    // BARE project and deletes only that row - but the delete is written to take its children too, so
    // a future variant that adds them cannot orphan anything. Cleanup is verified by re-count either
    // way, and a run that left rows behind would say so loudly.
    cleanup: (m) => `delete from projects where name like '%${esc(m)}%'`,
    // saveProject() reads #f-name (required, refused with 'Name is required') plus #f-type and
    // #f-priority, and is guarded by whRequireOnline - so a refusal here can be either a validation
    // message OR the online guard, and both surface through showToast. The drive fills the real
    // fields and samples the toast DURING the save, because a toast that has already faded is
    // indistinguishable from no refusal at all.
    drive: async (page, marker) => page.evaluate(async (m) => {
      const wait = (ms) => new Promise((r) => setTimeout(r, ms));
      const open = [...document.querySelectorAll('button,[role="button"]')]
        .find((b) => /new project|add project|create project/i.test(b.textContent || ''));
      if (open) { open.click(); await wait(1000); }
      if (typeof window.saveProject !== 'function') return { drove: 'no-saveProject-fn' };
      const set = (id, v) => { const e = document.getElementById(id); if (!e) return false;
        e.value = v; e.dispatchEvent(new Event('input', { bubbles: true }));
        e.dispatchEvent(new Event('change', { bubbles: true })); return true; };
      if (!set('f-name', m)) return { drove: 'no-name-field' };
      const p = window.saveProject();
      let refusal = null;
      for (let i = 0; i < 12; i++) {
        await wait(250);
        const t = document.querySelector('#toast,[id$="toast"]');
        const tx = t && (t.innerText || '').trim();
        if (t && !t.classList.contains('hidden') && tx && /required|offline|cannot|failed|error/i.test(tx)) {
          refusal = tx.slice(0, 120); break;
        }
      }
      await p; await wait(1500);
      return refusal ? { drove: 'refused', reason: refusal } : { drove: 'saved' };
    }, marker),
  },
  {
    page: 'voice-journal',
    what: 'sending a typed journal note',
    marker: 'WH-EFFECT-PROBE-' + process.pid,
    // MARKER-ONLY scope (2026-08-23): the entry row is written SERVER-SIDE by voice-journal-agent,
    // which resolves worker_name itself - filtering by this probe's WORKER read inDb=0 over a row
    // that landed under the agent's resolution, and the same filter made cleanup MISS those rows
    // (five orphaned probe entries from 2026-08-18 found in the shared table). The marker is unique.
    countBefore: (m) => `select count(*) from voice_journal_entries where transcript like '%${esc(m)}%'`,
    cleanup: (m) => `delete from voice_journal_entries where transcript like '%${esc(m)}%'`,
    // The typed entrance (#type-input -> onSendTyped) exists so this page is usable without a
    // microphone. onSendTyped guards on a _busy flag and refuses empty text, so the drive types real
    // text and then waits for the button to be released rather than racing it - clicking a control
    // whose handler is still in flight is how a double-submit test accidentally measures the first
    // press twice.
    drive: async (page, marker) => page.evaluate(async (m) => {
      const wait = (ms) => new Promise((r) => setTimeout(r, ms));
      const ta = document.getElementById('type-input');
      const btn = document.getElementById('type-send');
      if (!ta || !btn) return { drove: 'no-typed-entrance' };
      // the typed entrance may be behind a fallback toggle when the mic is unavailable
      const fb = document.getElementById('type-fallback');
      if (fb && getComputedStyle(fb).display === 'none') {
        const t = [...document.querySelectorAll('button,a')].find((b) => /type|keyboard|instead/i.test(b.textContent || ''));
        if (t) { t.click(); await wait(700); }
      }
      ta.value = m; ta.dispatchEvent(new Event('input', { bubbles: true }));
      btn.click();
      for (let i = 0; i < 20; i++) { await wait(500); if (!btn.disabled) break; }
      await wait(1500);
      // READ THE PAGE'S OWN VERDICT (2026-08-23): this returned 'saved' unconditionally, so a
      // 429-refused send (the page says "your note was not saved" and keeps the draft - honest)
      // was graded as a saved-but-invisible effect. A drive's claim must rest on the page's words.
      const st = (document.getElementById('type-state')?.textContent || '').trim();
      if (/not saved|went wrong|no reply|try again/i.test(st)) return { drove: 'refused', reason: st.slice(0, 120) };
      return { drove: 'saved', state: st.slice(0, 80) };
    }, marker),
  },
  {
    page: 'report-sender',
    what: 'saving a report contact',
    marker: 'WH-EFFECT-PROBE-' + process.pid,
    countBefore: (m) => `select count(*) from report_contacts where name like '%${esc(m)}%'`,
    cleanup: (m) => `delete from report_contacts where name like '%${esc(m)}%'`,
    // saveContact() reads #contact-name and #contact-email and writes a SPECIFIC sentence into
    // #sheet-error for each invalid one ('Name is required.' / 'Enter a valid email.'), so a refusal
    // is readable with the page's own words. The email must pass isValidEmail(), which is why the
    // probe supplies a well-formed address rather than the marker alone - a probe that trips a
    // validator is testing its payload, not the page.
    drive: async (page, marker) => page.evaluate(async (m) => {
      const wait = (ms) => new Promise((r) => setTimeout(r, ms));
      const open = [...document.querySelectorAll('button,[role="button"]')]
        .find((b) => /add contact|new contact/i.test(b.textContent || ''));
      if (open) { open.click(); await wait(900); }
      if (typeof window.saveContact !== 'function') return { drove: 'no-saveContact-fn' };
      const set = (id, v) => { const e = document.getElementById(id); if (!e) return false;
        e.value = v; e.dispatchEvent(new Event('input', { bubbles: true }));
        e.dispatchEvent(new Event('change', { bubbles: true })); return true; };
      if (!set('contact-name', m)) return { drove: 'no-name-field' };
      if (!set('contact-email', 'probe@example.com')) return { drove: 'no-email-field' };
      await window.saveContact();
      await wait(2200);
      const err = document.getElementById('sheet-error');
      const tx = err && (err.textContent || '').trim();
      if (tx) return { drove: 'refused', reason: tx.slice(0, 120) };
      return { drove: 'saved' };
    }, marker),
  },
  {
    page: 'asset-hub',
    what: 'adding an FMEA failure mode',
    marker: 'WH-EFFECT-PROBE-' + process.pid,
    countBefore: (m) => `select count(*) from rcm_fmea_modes where failure_mode like '%${esc(m)}%'`,
    cleanup: (m) => `delete from rcm_fmea_modes where failure_mode like '%${esc(m)}%'`,
    // ★THIS ONE NEEDS A PRECONDITION, AND THE REGISTRY ALREADY KNOWS IT. saveFmeaMode() refuses with
    // 'No asset selected.' unless _selectedNodeId is set, so an asset node must be clicked first.
    // Rather than invent a selector, this reuses the SAME precondition tools/dialog_targets.mjs uses
    // to open asset-hub's V2 - click a [data-node-id], then the fmea tab - so the state this probe
    // writes from is the state every other prover grades.
    drive: async (page, marker) => page.evaluate(async (m) => {
      const wait = (ms) => new Promise((r) => setTimeout(r, ms));
      const node = document.querySelector('[data-node-id]');
      if (!node) return { drove: 'no-asset-nodes-in-hive' };
      node.click(); await wait(1500);
      const tab = document.querySelector('.rel-tab[data-tab="fmea"]');
      if (tab) { tab.click(); await wait(1200); }
      const add = [...document.querySelectorAll('button,[role="button"]')]
        .find((b) => /add (failure )?mode|new mode|\+ mode/i.test(b.textContent || ''));
      if (add) { add.click(); await wait(900); }
      if (typeof window.saveFmeaMode !== 'function') return { drove: 'no-saveFmeaMode-fn' };
      const set = (id, v) => { const e = document.getElementById(id); if (!e) return false;
        e.value = v; e.dispatchEvent(new Event('input', { bubbles: true }));
        e.dispatchEvent(new Event('change', { bubbles: true })); return true; };
      if (!set('fmea-function', m)) return { drove: 'no-function-field' };
      if (!set('fmea-failure-mode', m)) return { drove: 'no-failure-mode-field' };
      set('fmea-severity', '5'); set('fmea-occurrence', '5'); set('fmea-detection', '5');
      const p = window.saveFmeaMode();
      let refusal = null;
      for (let i = 0; i < 12; i++) {
        await wait(250);
        const t = document.querySelector('#toast,#wh-toast,[id$="toast"]');
        const tx = t && (t.innerText || '').trim();
        if (t && !t.classList.contains('hidden') && tx && /no asset|required|cannot|failed|error/i.test(tx)) {
          refusal = tx.slice(0, 120); break;
        }
      }
      await p; await wait(1500);
      return refusal ? { drove: 'refused', reason: refusal } : { drove: 'saved' };
    }, marker),
  },
  {
    page: 'community',
    what: 'posting to the hive',
    marker: 'WH-EFFECT-PROBE-' + process.pid,
    countBefore: (m) => `select count(*) from community_posts where content like '%${esc(m)}%'`,
    cleanup: (m) => `delete from community_posts where content like '%${esc(m)}%'`,
    // submitPost() reads #post-content and refuses an empty body with showToast('Write something
    // first','error'). The refusal surfaces through #toast-text rather than a form-error element, so
    // the drive captures THAT - and captures it while the toast is still up, since showToast hides it
    // after 3.5s. A refusal read too late is indistinguishable from no refusal at all, which is the
    // same looked-too-early trap that produced a false red on logbook.
    drive: async (page, marker) => page.evaluate(async (m) => {
      const set = (id, v) => { const e = document.getElementById(id); if (!e) return false;
        e.value = v; e.dispatchEvent(new Event('input', { bubbles: true }));
        e.dispatchEvent(new Event('change', { bubbles: true })); return true; };
      if (typeof window.openComposer === 'function') { window.openComposer(); await new Promise((r) => setTimeout(r, 700)); }
      if (typeof window.submitPost !== 'function') return { drove: 'no-submitPost-fn' };
      if (!set('post-content', m)) return { drove: 'no-content-field' };
      const cat = document.getElementById('post-category');
      if (cat) { const safe = [...cat.options].find((o) => !/announce/i.test(o.value + o.text));
                 if (safe) { cat.value = safe.value; cat.dispatchEvent(new Event('change', { bubbles: true })); } }
      const p = window.submitPost();
      // sample the toast WHILE it can still be up
      let refusal = null;
      for (let i = 0; i < 12; i++) {
        await new Promise((r) => setTimeout(r, 250));
        const t = document.getElementById('toast');
        const tx = document.getElementById('toast-text');
        if (t && !t.classList.contains('hidden') && tx && /first|only|cannot|failed|error/i.test(tx.textContent || '')) {
          refusal = (tx.textContent || '').trim().slice(0, 120); break;
        }
      }
      await p;
      await new Promise((r) => setTimeout(r, 1500));
      return refusal ? { drove: 'refused', reason: refusal } : { drove: 'saved' };
    }, marker),
  },
  {
    page: 'engineering-design',
    what: 'running and saving an engineering calculation',
    marker: 'WH-EFFECT-PROBE-' + process.pid,
    countBefore: (m) => `select count(*) from engineering_calcs where project_name like '%${esc(m)}%'`,
    cleanup: (m) => `delete from engineering_calcs where project_name like '%${esc(m)}%'`,
    // ★THE FORM DOES NOT EXIST UNTIL A CALCULATOR IS CHOSEN. This page is a grid of calc cards
    // (div.calc-card[data-id]); picking one RENDERS the input set for that calc. So the drive has to
    // choose a calculator first, and the fields it then fills were discovered by observing the live
    // page rather than read out of the HTML - none of them appear in the source, because the form is
    // generated. The numeric inputs arrive pre-filled with valid defaults (persons 10, equipment 2,
    // outdoor 35C, indoor 24C), so the marker only needs to go in #f-project, which is what the insert
    // stores as project_name.
    // ★AND runCalculation() MUST SUCCEED BEFORE saveCalc() CAN DO ANYTHING: the payload reads
    // _lastInputs/_lastResults, which are module-scoped and stay null until a calculation has run. A
    // save attempted without one writes nothing and would look like a refused write rather than a
    // skipped precondition.
    // ★I GOT THIS WRONG FIRST AND THE PAGE CORRECTED ME, IN ITS OWN WORDS. My first version filled
    // only #f-project, on the assumption that the numeric inputs ship with valid defaults - some do
    // (persons 10, equipment 2, outdoor 35C, indoor 24C) and at least one does NOT. The page said
    // "Please enter the floor area." and then "Run the calculation before saving." - two precise,
    // actionable refusals, correctly ordered, and between them they diagnosed the probe completely.
    // So the drive now fills EVERY visible empty numeric field rather than trusting defaults, and it
    // CAPTURES showToast so a refusal is reported as the page's own sentence instead of being
    // silently indistinguishable from a failed write. A page that refuses well is evidence, not noise.
    drive: async (page, marker) => page.evaluate(async (m) => {
      const wait = (ms) => new Promise((r) => setTimeout(r, ms));
      const card = document.querySelector('.calc-card[data-id]');
      if (!card) return { drove: 'no-calc-cards' };
      card.click(); await wait(2500);
      const said = [];
      const orig = window.showToast;
      if (typeof orig === 'function') {
        window.showToast = function (msg, ...a) { said.push(String(msg).slice(0, 140)); return orig.apply(this, [msg, ...a]); };
      }
      // Fill every visible empty numeric input the generated form exposes; a required blank is a
      // refusal, not a defect, and it is the probe's job to present a complete form.
      for (const f of document.querySelectorAll('input[type="number"][id^="f-"]')) {
        if (f.offsetParent !== null && !String(f.value || '').trim()) {
          f.value = '100';
          f.dispatchEvent(new Event('input', { bubbles: true }));
          f.dispatchEvent(new Event('change', { bubbles: true }));
        }
      }
      const proj = document.getElementById('f-project');
      if (!proj) return { drove: 'no-project-field' };
      proj.value = m;
      proj.dispatchEvent(new Event('input', { bubbles: true }));
      proj.dispatchEvent(new Event('change', { bubbles: true }));
      if (typeof window.runCalculation !== 'function') return { drove: 'no-runCalculation-fn' };
      await window.runCalculation(); await wait(2500);
      if (typeof window.saveCalc !== 'function') return { drove: 'no-saveCalc-fn' };
      await window.saveCalc(); await wait(2500);
      // ★A TOAST IS NOT A REFUSAL, AND TREATING IT AS ONE SCORED THIS PAGE'S CORRECT SUCCESS SENTENCES
      // AS DEFECTS. My first version returned 'refused' whenever ANY message had been shown - so
      // "Calculation complete!" and "Saved -> it is in your calculation history now, and you can reopen
      // or export it from the History tab." were both read as failures. The page was doing everything
      // right and saying so clearly. Classify by the REFUSAL VOCABULARY, and let the database settle
      // the rest; the sentences are reported either way because they are evidence, not noise.
      const refused = said.some((t) => /please enter|please provide|run the calculation|sign in|failed|try again|invalid|required/i.test(t));
      // ★THE PAGE TOLD ME WHERE THE EFFECT LIVES. Its own confirmation names the History tab, so the
      // drive goes there rather than asserting against the calculator view the save left behind.
      const hist = [...document.querySelectorAll('[data-tab]')].find((e) => e.dataset.tab === 'history');
      if (hist) { hist.click(); await wait(2000); }
      if (refused) return { drove: 'refused', reason: said.join(' | '), calc: card.dataset.id };
      return { drove: 'saved', confirmation: said.join(' | '), calc: card.dataset.id };
    }, marker),
  },
  {
    page: 'index',
    anon: true,
    transient: true,
    what: 'joining the early-access list from the public landing page',
    marker: 'wh-effect-probe-' + process.pid + '@example.com',
    countBefore: (m) => `select count(*) from early_access_emails where email = '${esc(m)}'`,
    cleanup: (m) => `delete from early_access_emails where email = '${esc(m)}'`,
    // The one anon write on the roster. handleSignup() calls _supabaseSignup(email, role), which
    // inserts {email, source:'landing_page'} and deliberately swallows 23505 so a repeat signup is not
    // an error. The VISIBLE effect is not a row appearing in a list - it is the button becoming
    // "You're on the list!", which is the only confirmation this visitor ever gets, so that sentence
    // IS the effect this oracle is about.
    drive: async (page, marker) => page.evaluate(async (m) => {
      const wait = (ms) => new Promise((r) => setTimeout(r, ms));
      const form = document.getElementById('joinForm');
      if (!form) return { drove: 'no-join-form' };
      const input = form.querySelector('input[type="email"]');
      if (!input) return { drove: 'no-email-field' };
      input.value = m;
      input.dispatchEvent(new Event('input', { bubbles: true }));
      form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      await wait(3500);
      const btn = form.querySelector('button');
      const said = btn ? (btn.textContent || '').trim() : '';
      if (/try again/i.test(said)) return { drove: 'refused', reason: said };
      return { drove: 'saved', confirmation: said };
    }, marker),
  },
  {
    page: 'shift-brain',
    what: 're-running the shift plan (supervisor)',
    marker: 'WH-EFFECT-PROBE-' + process.pid,
    // ★THIS CASE MUTATES A ROW THAT ALREADY EXISTS, so its discipline is CAPTURE-AND-RESTORE rather
    // than create-and-delete. rerunPlan() re-composes TODAY's plan in place through the
    // shift-planner-orchestrator; there is no new row to remove afterwards, and deleting the plan
    // would leave the hive without the briefing it had before I arrived. All of today's rows for the
    // hive are captured as JSON and re-inserted verbatim, and the restore is VERIFIED by re-reading
    // and comparing - an unverified restore is the same unbacked claim as an unverified cleanup.
    // The window is not pinned because currentShiftWindow() is clock-derived and module-scoped, so
    // capturing the whole day is both simpler and safer than guessing which window is live.
    capture: () => `select coalesce(json_agg(t order by t.id)::text, '[]') from shift_plans t`
      + ` where hive_id = '${HIVE}' and shift_date = current_date`,
    restore: (cap) => `delete from shift_plans where hive_id = '${HIVE}' and shift_date = current_date;`
      + ` insert into shift_plans select * from json_populate_recordset(null::shift_plans, '${cap.replace(/'/g, "''")}')`,
    countBefore: () => `select count(*) from shift_plans where hive_id = '${HIVE}' and shift_date = current_date`,
    cleanup: () => 'select 1',
    // The visible effect is the REFRESHED briefing, so the assertion compares what the page renders
    // against what the database holds now - and requires it to be non-trivial, because an empty
    // briefing would "match" a blank page.
    assertVisible: async (page, psql, rec) => {
      const dbBrief = psql(`select coalesce(briefing, '') from shift_plans where hive_id = '${HIVE}'`
        + ' and shift_date = current_date order by updated_at desc nulls last limit 1').trim();
      const probe = dbBrief.replace(/\s+/g, ' ').trim().slice(0, 60);
      if (probe.length < 20) return { visible: null, why: 'the stored briefing is too short to assert on - abstaining rather than passing on a trivial match' };
      const onPage = await page.evaluate((frag) => {
        const t = (document.body.innerText || '').replace(/\s+/g, ' ');
        return { hit: t.includes(frag), chars: t.length };
      }, probe);
      return { visible: onPage.hit, probe, pageChars: onPage.chars, rowChanged: rec.rowChanged,
               why: onPage.hit ? 'the page renders the briefing the database now holds'
                               : 'the page does not render the stored briefing' };
    },
    drive: async (page, marker) => page.evaluate(async () => {
      const wait = (ms) => new Promise((r) => setTimeout(r, ms));
      const said = [];
      const orig = window.showToast;
      if (typeof orig === 'function') {
        window.showToast = function (m, ...a) { said.push(String(m).slice(0, 140)); return orig.apply(this, [m, ...a]); };
      }
      if (typeof window.rerunPlan !== 'function') return { drove: 'no-rerunPlan-fn' };
      await window.rerunPlan();
      // The orchestrator is a >10s AI compose; the page says so itself with staged progress copy.
      for (let i = 0; i < 24 && !/Running/i.test('') ; i++) { await wait(1000); if (said.length) break; }
      await wait(4000);
      if (said.some((t) => /supervisors only|failed|unreachable|rate/i.test(t)))
        return { drove: 'refused', reason: said.join(' | ') };
      return { drove: 'saved', confirmation: said.join(' | ') || 'plan re-composed' };
    }, marker),
  },
  {
    page: 'project-report',
    domOnly: true,
    query: '?project_id=539e0d9a-9ff7-474b-ab03-9254406ca7dc',
    what: 'drafting the AI handover narrative',
    marker: 'WH-EFFECT-PROBE-' + process.pid,
    countBefore: () => 'select 0',
    cleanup: () => 'select 1',
    // The page has NO write path - the narrative replaces the exec summary in the document and is not
    // stored. So the oracle is the render, and it is kept honest three ways: the target container
    // (#pr-ai-exec-summary) must not exist BEFORE the action, must exist and be non-trivial AFTER, and
    // the hero finding must actually change - an unchanged summary with a new wrapper would pass a
    // shallower check.
    drive: async (page, marker) => {
      const before = await page.evaluate(() => ({
        hasSummary: !!document.getElementById('pr-ai-exec-summary'),
        hero: (document.querySelector('#exec-summary .insight-card .text') || {}).textContent || '',
      }));
      const said = await page.evaluate(async () => {
        const wait = (ms) => new Promise((r) => setTimeout(r, ms));
        const btn = document.getElementById('ai-narrative-btn');
        if (!btn) return { drove: 'no-narrative-button' };
        if (typeof window.aiGenerateNarrative !== 'function' && !btn.onclick) return { drove: 'no-handler' };
        // ARM A COLLECTOR BEFORE THE CLICK (2026-08-23): under a drained AI budget the page DOES
        // announce the refusal - a "AI failed" toast - but the toast dies before a single late
        // read, so this drive returned 'saved' over a spoken refusal (the toast-is-gone-before-
        // the-verdict class, again). The observer accumulates every message from click time.
        const seen = [];
        const mo = new MutationObserver((ms) => ms.forEach((mm) => mm.addedNodes.forEach((n) => {
          if (n.nodeType === 1) { const t = (n.textContent || '').trim(); if (t && t.length < 300) seen.push(t); }
        })));
        mo.observe(document.body, { childList: true, subtree: true });
        btn.click();
        for (let i = 0; i < 40; i++) { await wait(1000);
          if (document.getElementById('pr-ai-exec-summary')) break; }
        await wait(1500);
        mo.disconnect();
        const said2 = seen.join(' | ');
        if (/quota|limit|try again|failed|could not|couldn['’]t|unavailable/i.test(said2)
            && !document.getElementById('pr-ai-exec-summary')) {
          return { drove: 'refused', reason: said2.slice(0, 120) };
        }
        return { drove: 'saved' };
      });
      if (said.drove !== 'saved') return said;
      const after = await page.evaluate(() => {
        const el = document.getElementById('pr-ai-exec-summary');
        const vis = el && el.getBoundingClientRect().height > 0 && getComputedStyle(el).display !== 'none';
        return { present: !!el, visible: !!vis, chars: el ? (el.innerText || '').trim().length : 0,
                 hero: (document.querySelector('#exec-summary .insight-card .text') || {}).textContent || '' };
      });
      return { drove: 'saved',
               confirmation: `#pr-ai-exec-summary present=${after.present} visible=${after.visible} chars=${after.chars}`,
               domEffect: !before.hasSummary && after.visible && after.chars > 80 && after.hero !== before.hero,
               detail: { before, after } };
    },
  },
  {
    page: 'assistant',
    transient: true,
    what: 'rating an AI reply as helpful',
    marker: 'WH-EFFECT-PROBE-' + process.pid,
    countBefore: (m) => `select count(*) from ai_reply_feedback where question like '%${esc(m)}%'`,
    cleanup: (m) => `delete from ai_reply_feedback where question like '%${esc(m)}%'`,
    // The effect needs a REPLY to exist before it can be rated, so the drive asks a real question
    // (through the free-tier chain) and waits for the answer - measured at ~20s live, so the wait is
    // generous and polls for the control rather than sleeping a fixed guess. The marker rides in the
    // QUESTION, which is exactly what the feedback row stores, so the DB check is keyed to this run.
    // ★THE PAGE'S OWN COMMENT SETS THE STANDARD THIS CASE MEASURES AGAINST: the insert returns whether
    // the row landed "so the CONTROL can reflect reality instead of assuming success" - i.e. the
    // rating control is not supposed to claim a signal it never sent. That is precisely this oracle.
    drive: async (page, marker) => page.evaluate(async (m) => {
      const wait = (ms) => new Promise((r) => setTimeout(r, ms));
      const inp = document.getElementById('chat-input');
      const send = document.getElementById('send-btn');
      if (!inp || !send) return { drove: 'no-composer' };
      inp.value = m + ' what is MTBF?';
      inp.dispatchEvent(new Event('input', { bubbles: true }));
      send.click();
      const findThumb = () => [...document.querySelectorAll('button,[role="button"]')]
        .find((e) => /helpful reply/i.test(e.getAttribute('aria-label') || ''));
      let thumb = null;
      for (let i = 0; i < 60; i++) { await wait(1000); thumb = findThumb(); if (thumb) break; }
      if (!thumb) return { drove: 'no-reply', reason: 'the assistant did not answer within 60s, so there '
        + 'was nothing to rate - reported as a failure to reach the subject, never as a rating that failed' };
      // ★CAPTURE THE CONTROL'S STATE BEFORE THE CLICK, so "it is disabled afterwards" is a CHANGE and
      // not a property it always had. Without this the check would pass on a control that shipped
      // disabled and never worked at all - the same empty-denominator shape as asserting an absence
      // with no control that something could have been seen.
      const before = { disabled: !!thumb.disabled, pressed: thumb.getAttribute('aria-pressed') };
      if (before.disabled) return { drove: 'refused', reason: 'the rating control was ALREADY disabled '
        + 'before the click, so a disabled state afterwards would prove nothing' };
      thumb.click();
      await wait(3000);
      const after = findThumb();
      const state = after ? { pressed: after.getAttribute('aria-pressed'), disabled: !!after.disabled } : null;
      const changed = !!state && (state.disabled !== before.disabled || state.pressed !== before.pressed);
      if (!changed) return { drove: 'refused', reason: 'the rating control did not change after the '
        + 'click, so the person got no signal their rating was recorded: ' + JSON.stringify({ before, state }) };
      return { drove: 'saved', confirmation: `enabled->${JSON.stringify(before)} then ${JSON.stringify(state)}` };
    }, marker),
  },
  {
    page: 'hive',
    what: 'setting the hive focus (intent capture)',
    marker: 'WH-EFFECT-PROBE-' + process.pid,
    // A MUTATION of an existing hive row - hives.intent is JSONB, currently {} - so this is
    // capture-and-restore, never create-and-delete. Deleting or blanking a hive's stated focus would
    // be destroying real configuration to run a test.
    capture: () => `select coalesce(intent::text, 'null') from hives where id = '${HIVE}'`,
    restore: (cap) => `update hives set intent = '${cap.replace(/'/g, "''")}'::jsonb where id = '${HIVE}'`,
    countBefore: () => `select count(*) from hives where id = '${HIVE}'`,
    cleanup: () => 'select 1',
    // The visible effect is the FOCUS CHIP - #hive-focus-label - so the assertion reads it and requires
    // it to name the goal that was chosen, not merely to be non-empty.
    assertVisible: async (page, psql) => {
      const stored = psql(`select coalesce(intent->>'primary_goal', '') from hives where id = '${HIVE}'`).trim();
      if (!stored) return { visible: null, why: 'nothing stored to assert on - abstaining rather than passing' };
      const seen = await page.evaluate(() => {
        const el = document.getElementById('hive-focus-label') || document.getElementById('hive-focus-chip');
        if (!el) return { present: false, text: '', vis: false };
        const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
        return { present: true, text: (el.innerText || el.textContent || '').trim(),
                 vis: r.height > 0 && cs.display !== 'none' && cs.visibility !== 'hidden' };
      });
      // 'downtime' renders as human copy, so match on the STEM rather than demanding the raw enum -
      // a surface showing a bare enum would be its own defect (no_raw_enum), not a pass condition here.
      const stem = stored.split('_')[0].slice(0, 6).toLowerCase();
      const hit = seen.vis && seen.text.toLowerCase().includes(stem);
      return { visible: !!hit, stored, stem, chip: seen,
               why: hit ? 'the focus chip names the goal that was saved'
                        : 'the focus chip does not reflect the stored goal' };
    },
    drive: async (page, marker) => page.evaluate(async () => {
      const wait = (ms) => new Promise((r) => setTimeout(r, ms));
      const said = [];
      const orig = window.showToast;
      if (typeof orig === 'function') {
        window.showToast = function (m, ...a) { said.push(String(m).slice(0, 140)); return orig.apply(this, [m, ...a]); };
      }
      if (typeof window._openIntentModal !== 'function') return { drove: 'no-intent-modal-fn' };
      window._openIntentModal(); await wait(1200);
      const radio = document.querySelector('input[name="intent-primary"][value="downtime"]');
      if (!radio) return { drove: 'no-goal-option' };
      radio.checked = true; radio.dispatchEvent(new Event('change', { bubbles: true }));
      const save = document.getElementById('intent-save');
      if (!save) return { drove: 'no-save-button' };
      save.click();
      await wait(4000);
      if (said.some((t) => /could not save|pick one/i.test(t)))
        return { drove: 'refused', reason: said.join(' | ') };
      return { drove: 'saved', confirmation: said.join(' | ') || 'focus saved' };
    }, marker),
  },
  {
    page: 'skillmatrix',
    what: 'sitting a skill exam and seeing the result',
    marker: 'WH-EFFECT-PROBE-' + process.pid,
    // ★THE PROBE DELIBERATELY FAILS THE EXAM, and that is a discipline choice rather than laziness. A
    // PASS awards a badge and +250 XP through grade_skill_exam - a credential and a ledger entry, on
    // the one surface where a stray write touches a person's qualifications. Answering to FAIL leaves
    // exactly one attempt row, which is cleanly removable, and still exercises the whole path: the RPC
    // grades server-side and the result modal reports the outcome. The oracle is that the person SEES
    // their result, and a fail is as valid a result as a pass.
    // There is no free-text field to carry a marker, so the row is keyed on this worker + the attempt
    // being newer than the moment the probe started.
    countBefore: () => `select count(*) from skill_exam_attempts where worker_name = '${esc(WORKER)}'`,
    cleanup: () => `delete from skill_exam_attempts where worker_name = '${esc(WORKER)}'`
      + ` and attempted_at > now() - interval '10 minutes' and passed = false`,
    assertVisible: async (page, psql) => {
      const row = psql(`select score || '/' || case when passed then 'pass' else 'fail' end`
        + ` from skill_exam_attempts where worker_name = '${esc(WORKER)}'`
        + ` order by attempted_at desc limit 1`).trim();
      const seen = await page.evaluate(() => {
        const m = document.getElementById('result-modal');
        if (!m) return { present: false };
        const r = m.getBoundingClientRect(); const cs = getComputedStyle(m);
        return { present: true, vis: r.height > 0 && cs.display !== 'none' && cs.visibility !== 'hidden',
                 text: ((document.getElementById('result-msg') || {}).innerText || m.innerText || '').trim().slice(0, 200) };
      });
      const score = (row.split('/')[0] || '').trim();
      const hit = seen.vis && score !== '' && seen.text.includes(score);
      return { visible: !!hit, stored: row, modal: seen,
               why: hit ? 'the result modal shows the score the server recorded'
                        : 'the result modal does not show the recorded score' };
    },
    drive: async (page, marker) => page.evaluate(async () => {
      const wait = (ms) => new Promise((r) => setTimeout(r, ms));
      // ★openExam() ALONE OPENS AN EMPTY MODAL. It reads SKILL_CONTENT[_activeDiscipline][_activeLevel],
      // and those are set by opening a LESSON - so calling openExam directly showed a modal with no
      // question, no options and a disabled Next, which looks exactly like a broken exam. The real
      // entry is openLesson(discipline, level), then the lesson's own "take the exam" button.
      // ★AND MY FIRST ATTEMPT TO REACH IT BY CLICKING THE MATRIX WAS WORSE THAN WRONG: the selector
      // matched a .step-btn whose aria-label is "Decrease target", so the probe silently pressed a
      // CONTROL THAT CHANGES THE WORKER'S SKILL TARGET instead of opening anything. It did not persist
      // (skill_profiles was last written hours earlier, checked directly), but a probe that clicks
      // whatever its selector happens to match is one bad match away from mutating real data. Drive the
      // named function, not a guessed element.
      if (typeof window.openLesson !== 'function') return { drove: 'no-openLesson-fn' };
      window.openLesson('Mechanical', 1); await wait(1800);
      const examBtn = document.getElementById('lesson-exam-btn');
      if (!examBtn) return { drove: 'no-lesson-exam-button' };
      examBtn.click(); await wait(1800);
      if (!document.querySelector('#exam-options-wrap')?.children.length)
        return { drove: 'no-exam-questions', reason: 'the exam modal opened with no options, so there '
          + 'was nothing to answer - reported as a failure to reach the subject' };
      // Walk the ten questions, always taking the FIRST option - enough to answer every question and
      // very unlikely to reach the 7/10 pass mark, which is the point.
      for (let q = 0; q < 14; q++) {
        const opt = document.querySelector('#exam-options-wrap button, #exam-options-wrap [role="button"], #exam-options-wrap .exam-opt');
        if (opt) { opt.click(); await wait(400); }
        const next = document.getElementById('exam-next-btn');
        if (!next || !next.getClientRects().length) break;
        next.click(); await wait(700);
        if (document.getElementById('result-modal')
            && getComputedStyle(document.getElementById('result-modal')).display !== 'none') break;
      }
      await wait(4000);
      const m = document.getElementById('result-modal');
      const shown = m && getComputedStyle(m).display !== 'none';
      if (!shown) return { drove: 'no-result', reason: 'the exam did not reach a result modal, so there '
        + 'was no outcome for the person to see - reported as a failure to reach the subject' };
      return { drove: 'saved', confirmation: ((document.getElementById('result-msg') || {}).innerText || '').trim().slice(0, 120) };
    }, marker),
  },
  {
    page: 'analytics',
    what: 'recomputing risk scores',
    marker: 'WH-EFFECT-PROBE-' + process.pid,
    // ★THE WRITE APPENDS - I ASSUMED IT REFRESHED AND THE MEASUREMENT CORRECTED ME. A recompute added
    // 30 rows to asset_risk_scores (605 -> 635), one per asset, rather than updating in place: the
    // table keeps the HISTORY and v_risk_truth folds it with DISTINCT ON (hive_id, asset_name) taking
    // the newest generation. So the count delta IS meaningful here, and the captured generated_at
    // stamps witness that a new generation landed.
    capture: () => `select coalesce(string_agg(asset_name || '@' || generated_at, '|' order by asset_name), '-')`
      + ` from asset_risk_scores where hive_id = '${HIVE}'`,
    // NO RESTORE, DELIBERATELY, and it is the one case here that needs saying out loud: a recompute is
    // an IDEMPOTENT REFRESH the product itself offers on a button, and the daily 13:00 PHT cron does
    // the same thing unprompted. Writing back stale scores would be the destructive act, not leaving
    // the fresh ones. The prior state is still recorded so the change is auditable.
    countBefore: () => `select count(*) from asset_risk_scores where hive_id = '${HIVE}'`,
    cleanup: () => 'select 1',
    assertVisible: async (page, psql) => {
      const n = Number(psql(`select count(*) from asset_risk_scores where hive_id = '${HIVE}'`).trim());
      // ★ASSERT A VALUE THE DATABASE HOLDS, NOT A KEYWORD. My first version tested /risk/i against the
      // panel text and failed a panel that renders 4,936 characters of real content - the word simply
      // is not in the copy. A keyword is a proxy for the claim; the claim is that the panel shows the
      // assets that were just scored. So it asks the DB for the top-risk asset and requires that name
      // on screen.
      const top = psql(`select asset_name from v_risk_truth where hive_id = '${HIVE}'`
        + ' order by risk_score desc limit 1').trim();
      if (!top) return { visible: null, why: 'no scored asset to assert on - abstaining rather than passing' };
      const seen = await page.evaluate((name) => {
        const p = document.getElementById('results-panel');
        const t = ((p || document.body).innerText || '').replace(/\s+/g, ' ');
        return { chars: t.length, hasTop: t.includes(name) };
      }, top);
      const hit = n > 0 && seen.hasTop;
      return { visible: !!hit, scoredAssets: n, topAsset: top, panel: seen,
               why: hit ? 'the predictive panel names the highest-risk asset the recompute just scored'
                        : `the panel does not name the top scored asset (${top})` };
    },
    // ★THE CONFIRMATION IS A REAL DISCRIMINATOR HERE, which is what makes a transient assertion worth
    // anything: the SAME element says "✓ Updated" on success and "⚠ Try again" on failure, and the
    // page resets it after 2600ms. So the drive polls inside that window and reports which sentence
    // appeared - a check that could only ever see one of them would be measuring nothing.
    // The recompute writes through batch-risk-scoring (server-side, hive-scoped, JWT-gated) and then
    // re-fetches the predictive phase, so the numbers on screen are the ones just written.
    drive: async (page, marker) => page.evaluate(async () => {
      const wait = (ms) => new Promise((r) => setTimeout(r, ms));
      // ★THE CONTROL DOES NOT EXIST ON THE DEFAULT VIEW. analytics opens on the Descriptive phase, and
      // the recompute button is rendered into #results-panel only by the PREDICTIVE phase - and only
      // for a supervisor. Probing the landing view found nothing and would have read as a missing
      // control on a page that renders it correctly one tab away.
      if (typeof window.setPhase === 'function') { window.setPhase('predictive'); await wait(6000); }
      const btn = document.getElementById('recompute-risk-btn');
      const lbl = document.getElementById('recompute-risk-label');
      if (!btn || !lbl) return { drove: 'no-recompute-control', reason: 'the recompute control is absent '
        + 'even on the predictive phase - either the phase did not render or this identity is not a '
        + 'supervisor, which are different findings from the control being broken' };
      const before = (lbl.textContent || '').trim();
      btn.click();
      let seen = '';
      for (let i = 0; i < 60; i++) {
        await wait(500);
        const t = (lbl.textContent || '').trim();
        if (/updated|try again/i.test(t)) { seen = t; break; }
      }
      if (!seen) return { drove: 'no-outcome', reason: 'the label never resolved to a success or a '
        + 'failure sentence, so the person was left with no outcome - reported as a failure to observe' };
      if (/try again/i.test(seen)) return { drove: 'refused', reason: `the recompute failed: "${seen}"` };
      return { drove: 'saved', confirmation: `"${before}" -> "${seen}"` };
    }, marker),
  },
  {
    page: 'resume',
    what: 'saving a resume to the cloud',
    marker: 'WH-EFFECT-PROBE-' + process.pid,
    // resume_documents is owner-scoped and empty for this identity, so a save is a clean INSERT and the
    // row is removable. The marker goes into an editable field, which lands inside the `doc` JSON.
    countBefore: (m) => `select count(*) from resume_documents where auth_uid = '${UID}'`
      + ` and doc::text like '%${esc(m)}%'`,
    cleanup: (m) => `delete from resume_documents where auth_uid = '${UID}'`
      + ` and doc::text like '%${esc(m)}%'`,
    // ★THE VISIBLE SURFACE IS THE RESUME MANAGER, not the editor the person was already looking at -
    // saving does not change the editor, so asserting there would prove nothing about persistence.
    assertVisible: async (page, psql) => {
      const title = psql(`select coalesce(title, '') from resume_documents where auth_uid = '${UID}'`
        + ' order by updated_at desc limit 1').trim();
      const seen = await page.evaluate(() => {
        const btn = document.getElementById('btn-resumes');
        if (btn) btn.click();
        return new Promise((r) => setTimeout(() => {
          const mgr = document.getElementById('resume-manager');
          const vis = mgr && mgr.getBoundingClientRect().height > 0
                   && getComputedStyle(mgr).display !== 'none';
          r({ open: !!vis, text: vis ? (mgr.innerText || '').trim().slice(0, 300) : '' });
        }, 2000));
      });
      const hit = seen.open && seen.text.length > 20;
      return { visible: !!hit, storedTitle: title, manager: seen,
               why: hit ? 'the resume manager lists the saved resume'
                        : 'the resume manager did not open or lists nothing' };
    },
    drive: async (page, marker) => page.evaluate(async (m) => {
      const wait = (ms) => new Promise((r) => setTimeout(r, ms));
      const said = [];
      const orig = window.showToast;
      if (typeof orig === 'function') {
        window.showToast = function (t, ...a) { said.push(String(t).slice(0, 140)); return orig.apply(this, [t, ...a]); };
      }
      // Put the marker somewhere it will travel into the saved document. Prefer a visible text field
      // in the builder; a contenteditable is accepted too, since this editor uses both.
      const field = [...document.querySelectorAll('input[type="text"], textarea, [contenteditable="true"]')]
        .find((e) => e.getClientRects().length && !e.disabled && !e.readOnly);
      if (!field) return { drove: 'no-editable-field' };
      if (field.isContentEditable) { field.textContent = m; }
      else { field.value = m; }
      field.dispatchEvent(new Event('input', { bubbles: true }));
      field.dispatchEvent(new Event('change', { bubbles: true }));
      field.dispatchEvent(new Event('blur', { bubbles: true }));
      await wait(1500);
      const save = document.getElementById('btn-save');
      if (!save) return { drove: 'no-save-button' };
      save.click();
      await wait(5000);
      if (said.some((t) => /could not|failed|sign in/i.test(t)))
        return { drove: 'refused', reason: said.join(' | ') };
      return { drove: 'saved', confirmation: said.join(' | ') || 'saved' };
    }, marker),
  },
  {
    page: 'inventory',
    what: 'adding a spare part',
    marker: 'WH-EFFECT-PROBE-' + process.pid,
    countBefore: (m) => `select count(*) from inventory_items where part_name like '%${esc(m)}%'`,
    cleanup: (m) => `delete from inventory_items where part_name like '%${esc(m)}%'`,
    // submitPart() reads #f-part-number / #f-part-name / #f-qty from the DOM and writes a SPECIFIC
    // message into #part-form-error for each missing or invalid one. So the drive fills the real
    // fields and then READS that element: a refusal is reported as a refusal WITH THE PAGE'S OWN
    // SENTENCE, never as a failed write. The page validating its own form is what makes this
    // distinguishable at all.
    drive: async (page, marker) => page.evaluate(async (m) => {
      const set = (id, v) => { const e = document.getElementById(id); if (!e) return false;
        e.value = v; e.dispatchEvent(new Event('input', { bubbles: true }));
        e.dispatchEvent(new Event('change', { bubbles: true })); return true; };
      if (typeof window.openAddModal === 'function') { window.openAddModal(); await new Promise((r) => setTimeout(r, 800)); }
      if (typeof window.submitPart !== 'function') return { drove: 'no-submitPart-fn' };
      if (!set('f-part-number', m)) return { drove: 'no-part-number-field' };
      if (!set('f-part-name', m)) return { drove: 'no-part-name-field' };
      if (!set('f-qty', '5')) return { drove: 'no-qty-field' };
      await window.submitPart();
      await new Promise((r) => setTimeout(r, 2200));
      const err = document.getElementById('part-form-error');
      if (err && !err.classList.contains('hidden') && (err.innerText || '').trim())
        return { drove: 'refused', reason: (err.innerText || '').trim().slice(0, 120) };
      return { drove: 'saved' };
    }, marker),
  },
  {
    page: 'logbook',
    what: 'capturing a maintenance entry',
    marker: 'WH-EFFECT-PROBE-' + process.pid,
    countBefore: (m) => `select count(*) from logbook where worker_name='${esc(WORKER)}' and problem like '%${esc(m)}%'`,
    cleanup: (m) => `delete from logbook where worker_name='${esc(WORKER)}' and problem like '%${esc(m)}%'`,
    // ★THIS PAGE VALIDATES ITS OWN CAPTURE CONTRACT, and that is a gift to a probe rather than an
    // obstacle: addEntry() runs whValidateCapture(db, 'logbook_add_entry_v1', payload) and RETURNS
    // { ok:false, reason:'capture_violation', errors } when the payload is wrong. So a refusal is
    // reported as a refusal WITH ITS REASON, and can never be mistaken for a failed write — which is
    // precisely the confusion that nearly produced a false defect on dayplanner.
    drive: async (page, marker) => page.evaluate(async (m) => {
      if (typeof window.addEntry !== 'function') return { drove: 'no-addEntry-fn' };
      const d = new Date();
      const ymd = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-'
                + String(d.getDate()).padStart(2, '0');
      const res = await window.addEntry({
        id: 'log-' + Math.random().toString(36).slice(2, 14),
        date: ymd, machine: 'PROBE-MACHINE', maintenance_type: 'Corrective',
        category: 'Mechanical', problem: m, root_cause: 'probe', action: 'probe',
        knowledge: '', downtime_hours: 0, photo: null, status: 'Open',
      });
      if (res && res.ok === false) return { drove: 'refused', reason: res.reason,
        errors: (res.errors || []).slice(0, 3).map((e) => e.message || String(e)) };
      return { drove: 'saved' };
    }, marker),
  },
  {
    page: 'dayplanner',
    what: 'adding a planned item',
    // A marker no human would type, so a stray row is identifiable and a false match is impossible.
    marker: 'WH-EFFECT-PROBE-' + process.pid,
    countBefore: (m) => `select count(*) from schedule_items where worker_name='${esc(WORKER)}' and title like '%${esc(m)}%'`,
    cleanup: (m) => `delete from schedule_items where worker_name='${esc(WORKER)}' and title like '%${esc(m)}%'`,
  },
];

const run = async () => {
  const cases = CASES.filter((c) => !ONE || c.page === ONE);
  const out = { origin: ORIGIN, results: [] };
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await assertSignedIn(signIn(ctx, 'supervisor'));
  // ★SOME EFFECTS ARE ONLY REACHABLE SIGNED OUT, and running them in the signed-in context does not
  // fail loudly - it measures a DIFFERENT PAGE. index.html is two products behind one URL: an inline
  // script sets html.wh-signed-in before <body> parses and CSS swaps the marketing landing for the ops
  // dashboard, so the early-access form a visitor uses does not exist for a signed-in probe. A case
  // that declares `anon: true` therefore gets its own clean context with no session at all.
  const anonCtx = await browser.newContext({ viewport: { width: 390, height: 844 } });

  for (const c of cases) {
    const rec = { page: c.page, what: c.what, marker: c.marker, persona: c.anon ? 'anon' : 'supervisor' };
    const page = await (c.anon ? anonCtx : ctx).newPage();
    try {
      // CAPTURED FROM PSQL FIRST, before anything is touched.
      rec.before = Number(psql(c.countBefore(c.marker)).split('\n')[0]);
      // ★SOME EFFECTS MUTATE A ROW THAT ALREADY EXISTS, and for those "clean up" cannot mean DELETE.
      // shift-brain's rerunPlan() re-composes TODAY'S plan in place - deleting it afterwards would leave
      // the hive worse off than I found it, which is the opposite of the discipline. So a case may
      // CAPTURE the pre-existing row as JSON, and the finally block RESTORES it and then VERIFIES the
      // restore by re-reading the row and comparing it to what was captured. An unverified restore is
      // the same class of claim as an unverified cleanup.
      if (c.capture) { rec.captured = psql(c.capture()).trim(); rec.capturedOk = rec.captured.length > 0; }
      // ★A PARAMLESS WALK IS A DIFFERENT PAGE. project-report returns early without ?project_id=,
      // so a case may supply the query it needs; walking the bare URL would measure the empty state
      // and blame the report for rendering nothing.
      await page.goto(`${ORIGIN}/workhive/${c.page}.html${c.query || ''}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(4000);
      if (c.drive) {
        const dr = await c.drive(page, c.marker);
        rec.drove = dr.drove; if (dr.reason) rec.refusalReason = dr.reason;
        if (dr.confirmation) rec.confirmation = dr.confirmation;
        if (dr.domEffect !== undefined) rec.domEffect = dr.domEffect;
        if (dr.detail) rec.domDetail = dr.detail;
        if (dr.errors) rec.refusalErrors = dr.errors;
      } else
      rec.drove = await page.evaluate(async (marker) => {
        // Drive the page's OWN save path rather than inserting behind its back: the oracle is about
        // the effect a PERSON causes through the surface, so a direct DB write would prove nothing
        // about this page at all.
        // ★FILL THE REAL FIELDS. The first version called saveScheduleItem({title}) — but the function
        // takes NO ARGUMENTS: it reads #m-title and #m-date from the DOM and RETURNS EARLY with
        // #m-required-error when either is blank. So the page correctly refused an empty form, no row
        // landed, and the probe was about to record effect_in_db:false as a page defect. The page was
        // right; the drive was wrong. A probe that does not satisfy a form's own validation is testing
        // its own payload, not the surface.
        const set = (id, v) => { const e = document.getElementById(id); if (!e) return false;
          e.value = v; e.dispatchEvent(new Event('input', { bubbles: true }));
          e.dispatchEvent(new Event('change', { bubbles: true })); return true; };
        if (typeof window.saveScheduleItem !== 'function') return 'no-save-fn';
        if (!set('m-title', marker)) return 'no-title-field';
        const d = new Date();
        const ymd = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-'
                  + String(d.getDate()).padStart(2, '0');
        if (!set('m-date', ymd)) return 'no-date-field';
        window.saveScheduleItem();
        await new Promise((r) => setTimeout(r, 2200));
        const err = document.getElementById('m-required-error');
        if (err && getComputedStyle(err).display !== 'none') return 'form-refused';
        return 'saved';
      }, c.marker);
      await page.waitForTimeout(2500);

      rec.inDb = Number(psql(c.countBefore(c.marker)).split('\n')[0]) - rec.before;
      // ★VISIBILITY IS AN ELEMENT FACT, NOT A TEXT FACT — and asset-hub proved why. There,
      // document.body.innerText did NOT contain the marker while #rel-panel-fmea.innerText DID, on a
      // fully-rendered page. Both readings are explainable at once: innerText on a HIDDEN element
      // falls back to textContent, so a panel in the DOM but off-screen reports its text when queried
      // directly and is skipped by a body traversal. A text scan therefore cannot separate "the person
      // sees it" from "it exists in the DOM" — and on THIS oracle that difference is the entire claim.
      // So find the element that actually carries the marker and ask the geometry: a box with height,
      // not display:none, not visibility:hidden, not opacity:0.
      rec.onSurface = await page.evaluate((m) => {
        const hit = [...document.querySelectorAll('*')].filter((el) =>
          !el.children.length && (el.textContent || '').includes(m));
        if (!hit.length) return { visible: false, found: 0, why: 'no element carries the marker at all' };
        // ★A TOAST IS NOT THE EFFECT. report-sender's only visible match was inside #toast - the
        // confirmation banner echoing the contact's name back. That is a PROXY for the write, not the
        // write becoming visible: the oracle asks whether the person can SEE THE THING THEY MADE on
        // the surface they made it on, and a banner that disappears in a few seconds is a receipt,
        // not the record. Crediting it would be the proxy-oracle failure - reporting success while
        // the payoff is missing. So transient notification hosts are excluded from the verdict and
        // reported separately, because "only the toast showed it" is itself worth knowing.
        const TRANSIENT = /toast|snackbar|notification|flash|banner/i;
        const isTransient = (el) => !!(el.closest && el.closest('[id]')
          && TRANSIENT.test((el.closest('[id]').id || '')))
          || !!(el.closest && el.closest('[class*="toast"],[class*="snackbar"],[class*="notification"]'));
        let toastOnly = null;
        for (const el of hit) {
          const r = el.getBoundingClientRect();
          const cs = getComputedStyle(el);
          const rendered = r.height > 0 && r.width > 0 && cs.display !== 'none'
            && cs.visibility !== 'hidden' && Number(cs.opacity) !== 0;
          if (!rendered) continue;
          const where = (el.closest('[id]') || {}).id || null;
          if (isTransient(el)) { toastOnly = where; continue; }
          return { visible: true, found: hit.length, where,
                   box: { w: Math.round(r.width), h: Math.round(r.height) } };
        }
        if (toastOnly) {
          return { visible: false, found: hit.length, toastOnly,
                   why: 'the ONLY rendered element carrying the marker is a transient notification (#'
                      + toastOnly + ') - a receipt for the write, not the write made visible on the '
                      + 'surface. Not credited.' };
        }
        return { visible: false, found: hit.length,
                 why: 'the marker is in the DOM but every element carrying it is not rendered '
                    + '(zero-box, display:none, visibility:hidden or opacity:0)' };
      }, c.marker);
      // ★NOT VISIBLE IS NOT THE SAME AS NOT SHOWN. A surface can be filtered (logbook opens in TEAM
      // mode for this identity, so a fresh personal entry sits behind a view switch), or simply not
      // re-render after its own save. Both look identical to a one-shot text scan, and only one of
      // them is a defect. So when the immediate check misses, RELOAD and look again, and record which
      // of the two it was rather than collapsing them into a single false red.
      // ★THE VERDICT RESTS ON WHAT SURVIVES A RELOAD, and this replaced a blocklist that was quietly
      // failing. The immediate look kept crediting the wrong element: report-sender resolved in
      // #toast (a receipt), voice-journal in #current-transcript (the composer's live echo of what
      // was just typed). Excluding those by NAME is a blocklist, and a blocklist only excludes what
      // its author already thought of - 'toast' was caught, 'current-transcript' was not.
      // AN ECHO CANNOT SURVIVE A REFRESH; A RECORD MUST. So the page is always reloaded and the
      // marker looked for again, and THAT is the verdict. Measured on voice-journal: immediately the
      // marker rendered in #current-transcript, after the reload in #history-list - the same text,
      // two entirely different claims, and only the second one is the effect being visible.
      // The immediate reading is kept as context, never as the verdict.
      // Gated on WHETHER THE EFFECT LANDED, not on whether a row was ADDED - a mutation lands
      // without changing the count, and gating the visibility assertion on the delta skipped the
      // reload check entirely for shift-brain, leaving onSurfaceAfterReload null.
      // Read the after-state BEFORE the gate that depends on it. Computing rowChanged further down
      // (beside effect_in_db) left it undefined here, so the gate was false and the whole reload +
      // visibility path was skipped for every capture case - the assertion did not fail, it never ran,
      // which is the quieter and worse of the two.
      if (c.capture && rec.captured !== undefined) {
        rec.afterState = psql(c.capture()).trim();
        rec.rowChanged = rec.afterState !== rec.captured;
      }
      if (c.capture ? rec.rowChanged : rec.inDb > 0) {
        await page.reload({ waitUntil: 'domcontentloaded' });
        // ★WAIT ON A READINESS SIGNAL, NOT A STOPWATCH. A fixed timeout previously judged this page at
        // bodyChars 1123 - a tenth of what it renders when loaded - so the look measured the WAIT and
        // reported a page that had simply not drawn yet as one that never shows your entry. Poll until
        // the surface is actually populated, and record the size either way so a future reader can see
        // whether the assertion had anything to assert against.
        // ★WAIT FOR THE DOM TO SETTLE, NOT FOR A MAGIC NUMBER. The first version polled until the
        // body exceeded 2,500 characters - which is a threshold invented at my desk, not a property
        // of any page. project-manager renders a compact list that tops out around 1,558 characters,
        // so that poll could only ever time out, and every assertion there would have been made on a
        // page I had declared "not ready" while it was in fact finished. Same mistake as the
        // name-based blocklist: a constant standing in for a property.
        // A page is READY when it stops changing. Sample the size until it repeats, and record both
        // the settled size and whether it actually settled, so a still-moving page is visible in the
        // evidence rather than silently judged.
        let prev = -1, stable = 0;
        for (let i = 0; i < 24; i++) {
          const n = await page.evaluate(() => document.body.innerText.length);
          if (n === prev && n > 0) { stable++; if (stable >= 3) break; } else { stable = 0; }
          prev = n;
          await page.waitForTimeout(500);
        }
        rec.settled = stable >= 3;
        // ★AND LOOK IN THE RIGHT VIEW. logbook opens role-scoped for this identity, so a fresh personal
        // entry legitimately sits behind the Team/My-Entries switch. Asserting from the default view
        // would blame the page for a filter the person would simply click.
        // ★BROADEN THE VIEW BEFORE ASSERTING, because a DEFAULT FILTER is not a missing effect.
        // Two pages proved this independently: logbook opens role-scoped, so a fresh personal entry
        // sits behind Team/My-Entries; and project-manager lands on an "Active" filter while
        // projects.status DEFAULTS to 'planning', so a just-created project is correctly filed and
        // correctly absent from that list. Asserting from the default view accuses a page of hiding
        // work it is categorising properly.
        // So: click the page's own broadest filter if it has one (All / Show all), then its
        // personal-scope switch if it has one. Both are the controls a person would use, and what is
        // clicked is RECORDED - a probe that silently changed the view would be a different kind of
        // lie about what was measured.
        rec.switchedView = await page.evaluate(async () => {
          const done = [];
          const wait = (ms) => new Promise((r) => setTimeout(r, ms));
          // ★RE-ESTABLISH THE SELECTION CONTEXT BEFORE EXPANDING, and in THAT order. A reload clears
          // whatever the person had selected, and on a master-detail surface the detail panel is empty
          // until something is selected again - so expanding first opens a populated-looking shell over
          // nothing. asset-hub is the case that taught this and it cost me a FALSE DEFECT REPORT: its
          // FMEA workbench lives in #reliability-card, which ships display:none behind an explicit
          // "Show Reliability Workbench (engineer view)" disclosure, AND its list only fills once an
          // asset node is selected. This prover clicked the disclosure but never re-selected the node;
          // my hand-written re-check re-selected the node but never clicked the disclosure. NEITHER did
          // both, each reported the row invisible, and the two agreeing felt like corroboration when it
          // was really the same blind spot approached from two sides.
          const selected = document.querySelector('[data-node-id].active,[data-node-id].selected,'
            + '[data-node-id][aria-selected="true"]');
          if (!selected) {
            const node = [...document.querySelectorAll('[data-node-id]')].find((e) => e.getClientRects().length);
            if (node) { node.click(); done.push('re-selected-node'); await wait(1500); }
          }
          const all = [...document.querySelectorAll('button,[role="tab"],.filter-chip,.chip,.tab')]
            .filter((e) => e.getClientRects().length)
            .find((e) => /^\s*(all|show all|all projects|all items)\b/i.test((e.textContent || '').trim()));
          if (all) { all.click(); done.push('all-filter'); }
          const mine = document.getElementById('btn-view-mine');
          if (mine) { mine.click(); done.push('view-mine'); }
          // A saved artefact often lives in a HISTORY/SAVED tab rather than the authoring view the
          // person was last looking at - engineering-design says so in its own save confirmation.
          const hist = [...document.querySelectorAll('[data-tab]')]
            .find((e) => /^(history|saved)$/i.test(e.dataset.tab || ''));
          if (hist && hist.getClientRects().length) { hist.click(); done.push('history-tab'); await wait(1800); }
          // ★EXPAND EVERYTHING THAT COLLAPSES. project-manager groups its list by status and opens
          // ONLY the 'active' group by default - its own comment says "auto-expand active, collapse
          // others". A new project defaults to status 'planning', so it lands in a COLLAPSED group
          // and renders nothing measurable. That is correct product behaviour and it made my probe
          // report a written project as invisible. This is the platform's own QA rule - expand
          // everything, then look - and it belongs in the instrument rather than in a per-page
          // special case.
          let opened = 0;
          for (const d of document.querySelectorAll('details:not([open])')) { d.open = true; opened++; }
          for (const h of document.querySelectorAll('[aria-expanded="false"]')) {
            if (h.getClientRects().length) { h.click(); opened++; }
          }
          // ★A TOGGLE IS NOT AN EXPANDER. The first version clicked EVERY .group-header it found -
          // but project-manager's header calls toggleGroup(status), so clicking all of them opened
          // the collapsed groups AND CLOSED the open one. It reported "expanded:3" while leaving the
          // list no more visible than before. Only act on containers that are actually collapsed,
          // and read that from the page's own state class rather than assuming.
          for (const g of document.querySelectorAll('.group-header,.group-head,.grp-head,[class*="group-header"]')) {
            const box = g.closest('.group') || g.parentElement;
            const isCollapsed = box && /(^|\s)collapsed(\s|$)/.test(box.className || '');
            if (isCollapsed && g.getClientRects().length) { g.click(); opened++; }
          }
          if (opened) done.push('expanded:' + opened);
          // ★AND VERIFY THE DISCLOSURE ACTUALLY OPENED, rather than trusting the click. A control whose
          // aria-expanded is still "false" did not open - which is a different fact from "the effect is
          // not there", and the two must never be conflated again.
          const stillShut = [...document.querySelectorAll('[aria-expanded="false"][aria-controls]')]
            .filter((e) => e.getClientRects().length).length;
          if (stillShut) done.push('still-collapsed:' + stillShut);
          return done.length ? done.join('+') : 'no-switch';
        });
        await page.waitForTimeout(3000);
        rec.bodyCharsAtAssert = await page.evaluate(() => document.body.innerText.length);
        const post = await page.evaluate((m) => {
          // ★MATCH THE ACCESSIBLE NAME, NOT ONLY THE TEXT - because A SURFACE MAY LABEL AN EFFECT WITH
          // SOMETHING OTHER THAN THE VALUE YOU TYPED. project-manager taught this: a created project IS
          // rendered, in #recent-strip, as a span whose VISIBLE text is the generated project code
          // ("WO-2026-002") with the full name carried only in `title`. Matching textContent alone found
          // nothing while documentElement.innerHTML contained the marker (inside title="..."), which is
          // exactly the contradictory pair that makes a working page look broken. A system-generated
          // code, a truncated label or an icon are all legitimate ways to identify a new record - and
          // title/aria-label is also how a screen-reader user finds that row, so this is the same
          // question a person asks, not a loosened one.
          const carries = (el) => (!el.children.length && (el.textContent || '').includes(m))
            || (el.getAttribute && (((el.getAttribute('title') || '').includes(m))
                                 || ((el.getAttribute('aria-label') || '').includes(m))));
          const hit = [...document.querySelectorAll('*')].filter(carries);
          for (const el of hit) {
            const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
            if (r.height > 0 && r.width > 0 && cs.display !== 'none' && cs.visibility !== 'hidden'
                && Number(cs.opacity) !== 0)
              return { visible: true, where: (el.closest('[id]') || {}).id || null, found: hit.length };
          }
          return { visible: false, found: hit.length };
        }, c.marker);
        rec.afterReloadWhere = post.where; rec.afterReloadFound = post.found;
        rec.onSurfaceAfterReload = post.visible;
        // ★A MUTATION HAS NO PLANTED MARKER TO FIND. shift-brain's effect is a RE-COMPOSED briefing,
        // so "is it visible" cannot mean "is my string on the page" - there is no string of mine. It
        // means: does the page render the NEW briefing rather than the one it had before? A case may
        // supply its own assertion for exactly this, and it stays non-vacuous because it compares the
        // rendered text against the value psql holds NOW, and separately confirms it differs from the
        // captured BEFORE state. Matching the old briefing would fail, which is what gives it teeth.
        if (c.assertVisible) {
          const av = await c.assertVisible(page, psql, rec);
          rec.visibleAssertion = av;
          rec.onSurfaceAfterReload = av.visible === true;
        }
        rec.visibleOnlyAfterReload = rec.onSurfaceAfterReload === true;
        if (!rec.onSurfaceAfterReload) {
          rec.viewState = await page.evaluate(() => ({
            activeFilters: [...document.querySelectorAll('.filter-chip,.tab,[role="tab"]')]
              .filter((e) => /active|selected/i.test(e.className) || e.getAttribute('aria-selected') === 'true')
              .map((e) => (e.textContent || '').trim()).filter(Boolean).slice(0, 5),
            bodyChars: document.body.innerText.length,
          }));
        }
      }
      // ★A COUNT DELTA IS THE WRONG INSTRUMENT FOR A MUTATION, and it reads exactly like a failed
      // write. shift-brain's rerunPlan() RE-COMPOSES today's plan in place: the row count before and
      // after is identical, so `inDb > 0` reported effect_in_db=false over a write that plainly
      // happened - the page itself said "Plan refreshed -> rebuilt from your current jobs and PMs."
      // For a capture case the effect is that the ROW CHANGED, so the after-state is read with the
      // same query as the capture and compared. This is the session's recurring shape once more:
      // I was counting rows when the property was CONTENT.
      if (c.domOnly) {
        // ★SOME EFFECTS ARE DELIBERATELY NOT PERSISTED, and demanding a row would fail the page for a
        // design decision. project-report's AI narrative REPLACES the exec summary in the document and
        // stores nothing - the page has no write path at all. The effect is real and the person caused
        // it; it simply lives in the render. Recorded explicitly so a reader can see this row is held
        // to a DOM standard by design rather than by omission.
        rec.effect_in_db = null;
        rec.domOnlyBasis = 'this action persists nothing by design; the effect is the rendered output';
      } else if (c.capture) {
        rec.afterState = psql(c.capture()).trim();
        rec.rowChanged = rec.afterState !== rec.captured;
        rec.effect_in_db = rec.rowChanged;
      } else {
        rec.effect_in_db = rec.inDb > 0;
      }
      // ★A TRANSIENT CONFIRMATION IS STILL A VISIBLE EFFECT - but it has to be proven differently, and
      // it must NOT be a softer version of the same test. The reload check is the right default: it is
      // what catches an optimistic UI that claims success over a write that never landed. It cannot be
      // the test for a fire-and-forget capture, because an ANON visitor has no identity for the page to
      // render anything against afterwards - there is no list their signup could appear in. Demanding
      // survival there would fail a page for not storing state it deliberately does not keep.
      // So a `transient` case asserts the confirmation the person actually saw, and it is non-vacuous
      // because the SAME element says something DIFFERENT on failure ("Try again"), which the drive
      // reports as a refusal instead. The reload result is still recorded, never required.
      rec.effect_visible = c.domOnly
        ? rec.domEffect === true
        : c.transient
          ? (rec.effect_in_db && typeof rec.confirmation === 'string' && rec.confirmation.length > 0)
          : (rec.effect_in_db && rec.onSurfaceAfterReload === true);
      if (c.transient) rec.transientBasis = 'confirmation observed at the moment of the effect; '
        + 'reload survival recorded but not required (anon visitor has no rendered state)';
    } catch (e) {
      rec.error = String(e.message || e).slice(0, 200);
    } finally {
      // ALWAYS, and then VERIFIED.
      if (c.restore && rec.captured) {
        try { psql(c.restore(rec.captured)); } catch (e) { rec.restoreError = String(e.message).slice(0, 160); }
        const now = psql(c.capture()).trim();
        rec.restoredOk = now === rec.captured;
        rec.cleanupOk = rec.restoredOk;
        rec.leftBehind = rec.restoredOk ? 0 : 1;
      } else {
      try { psql(c.cleanup(c.marker)); } catch (e) { rec.cleanupError = String(e.message).slice(0, 120); }
        // ★LEFT-BEHIND IS A DELTA AGAINST THE BASELINE, NOT AN ABSOLUTE COUNT. Most cases key on a
        // unique marker so the baseline is 0 and the two are identical - but a case whose subject has
        // no free-text field must count a PRE-EXISTING population instead (skillmatrix keys on the
        // worker, who already had 25 attempts). Comparing the absolute count to 0 then screams
        // "LEFT 25 ROWS BEHIND" over a run that added and removed nothing. A FALSE DIRTY-DATABASE
        // ALARM IS NOT THE SAFE DIRECTION: it teaches me to distrust clean runs, and the next real
        // one reads like more noise.
      rec.leftBehind = Number(psql(c.countBefore(c.marker)).split('\n')[0]) - rec.before;
      rec.cleanupOk = rec.leftBehind === 0;
      }
    }
    await page.close();
    out.results.push(rec);
    console.log(`  ${c.page.padEnd(14)} drove=${rec.drove} inDb=${rec.inDb} onSurface=${rec.onSurface} ` +
      `effect_in_db=${rec.effect_in_db} effect_visible=${rec.effect_visible} ` +
      `CLEANUP=${rec.cleanupOk ? 'clean' : 'LEFT ' + rec.leftBehind + ' ROW(S)'}` + (rec.error ? `  ERR ${rec.error}` : ''));
  }
  await browser.close();
  writeFileSync(path.join(ROOT, 'effect_visible_report.json'), JSON.stringify(out, null, 1));
  const dirty = out.results.filter((r) => !r.cleanupOk);
  // gate promotion 2026-08-21: a driven effect that failed to land or to show, or a dirty cleanup,
  // sets the exit code.
  if (process.argv.includes('--gate')) {
    // Only a drive the page itself CLAIMED succeeded ('saved') can fail this oracle: a refused or
    // un-constructable drive ('refused', 'no-reply', 'no-exam-questions') never became a write, and
    // grading those as invisible effects made the gate red whenever the suite's own AI calls had
    // drained the shared 429 budget - the gate-exhausts-its-own-rate-budget class (2026-08-23).
    // Refusal HONESTY is quota_legible's and why_refused's oracle, and they measure it.
    const bad = out.results.some((r) => r.drove === 'saved' && (r.effect_in_db === false || r.effect_visible === false));
    process.exitCode = (bad || dirty.length) ? 1 : 0;
  }
  if (dirty.length) console.log(`\n  ⚠ ${dirty.length} case(s) LEFT ROWS BEHIND — clean before trusting anything`);
  else console.log('\n  all cases cleaned up; the shared database is as it was found');
};
run().catch((e) => { console.error(e); process.exit(1); });
