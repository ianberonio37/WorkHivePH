/* prove_offline_refusal.mjs — the CG oracle "offline, the write is refused BEFORE it fires and the
 * person is told nothing was sent", measured live.
 *
 * WHY A PASSIVE BANNER DOES NOT SATISFY THIS. Every page adopts the shared offline banner, and the
 * banner states the CONDITION - it does not refuse the ACTION. The button still fires, the request
 * still leaves for a dead network, and the person still cannot tell whether their work landed. So this
 * asserts two things together, and both halves matter:
 *    1. ZERO write requests leave the page, and
 *    2. a sentence reaches the person saying nothing was sent.
 * One without the other is the failure this oracle exists to catch: a silent refusal leaves someone
 * tapping a dead button, and a message with the request still firing is a lie.
 *
 * HOW OFFLINE IS FAKED, and why the obvious way does not work. `context.setOffline(true)` cuts the
 * network but does NOT flip `navigator.onLine` inside the page, so a guard written as
 * `navigator.onLine === false` never triggers and the probe reports a false FAIL. So this does both:
 * it overrides the property on the live page AND cuts the network. Overriding alone would let a real
 * request escape if the guard were missing; cutting alone would leave the guard blind. Together, a
 * missing guard shows up as a request against a dead network (caught by the route counter) and a
 * present guard shows up as zero requests plus a message.
 *
 * The page is loaded ONLINE first, because loading it offline would fail for reasons that have nothing
 * to do with the write under test.
 *
 * Usage:
 *   node tools/prove_offline_refusal.mjs --page skillmatrix --case exam
 *   node tools/prove_offline_refusal.mjs --list
 */
import { chromium } from 'playwright';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

// Each case names the page, how to reach the committing control, and what the write endpoint looks
// like. `reach` runs ONLINE and must leave the control pressable; `fire` runs OFFLINE.
const CASES = {
  // ★engineering-design's save is gated by a FLOW, not a disclosure. #save-calc-btn (:738) lives inside
  // #report-output.hidden, which only exists once a calculation has RUN - so the reach must fill the
  // form and press #calc-btn ("Run Calculation") first. A calculator is already selected on load
  // (init() calls selectDiscipline('HVAC & Cooling')), which is why no quickSelectCalc opener is needed.
  // The write is saveCalc, gated by whRequireOnline('Saving this calculation') at
  // engineering-design.js:28055.
  calc: {
    page: 'engineering-design',
    writePattern: /rest\/v1\/engineering_calcs(\?|$)/,
    action: 'Saving this calculation',
    async reach(p) {
      for (let i = 0; i < 22; i++) {
        await p.waitForTimeout(1000);
        const ok = await p.evaluate(() => {
          const vis = (e) => e.getBoundingClientRect().width > 0;
          const save = document.getElementById('save-calc-btn');
          if (save && vis(save)) { save.setAttribute('data-probe', '1'); return true; }
          // ★#calc-btn SHIPS DISABLED (engineering-design.html:696, onclick=runCalculation) and is only
          // enabled by renderInputForm, which selectCalcType(id) calls (engineering-design.js:2800/2807).
          // A blanket fill + press therefore did nothing: no calc type was chosen, so there was no form
          // and no report, and #save-calc-btn never appeared. The id is taken from the PAGE'S OWN
          // CALC_TYPES_UI rather than hardcoded, so this cannot rot when the catalogue changes.
          if (document.getElementById('calc-btn') && document.getElementById('calc-btn').disabled
              && typeof selectCalcType === 'function' && typeof CALC_TYPES_UI !== 'undefined') {
            const first = Object.values(CALC_TYPES_UI).flat()[0];
            if (first && first.id) selectCalcType(first.id);
            return false;
          }
          // Fill every visible numeric/text input so the calculation can actually run.
          [...document.querySelectorAll('input[type=number],input[type=text]')]
            .filter(vis).forEach((inp) => {
              if (!inp.value) {
                inp.value = '10';
                inp.dispatchEvent(new Event('input', { bubbles: true }));
                inp.dispatchEvent(new Event('change', { bubbles: true }));
              }
            });
          const run = document.getElementById('calc-btn');
          if (run && vis(run)) run.click();
          return false;
        });
        if (ok) return { ok: true, control: '[data-probe="1"]' };
      }
      return { ok: false, why: 'save control never appeared - the calculation did not produce a report' };
    },
  },
  // ★resume's MAIN SAVE - the one write on this page whose loss matters. Its six OTHER writes are
  // resume_versions inserts/prunes, all annotated "best-effort, never blocks the main save"
  // (resume.html:714), and best-effort-by-design is not this oracle's subject. saveCloud()
  // (resume.html:722) is the real one: it does `if (error) throw error` on resume_documents at :744/747
  // and is wired to #btn-save at :2157. resume has ZERO whRequireOnline calls, so the expectation here
  // is a REAL FAIL - the write is attempted rather than refused before the request leaves.
  resume: {
    page: 'resume',
    writePattern: /rest\/v1\/resume_documents(\?|$)/,
    action: 'Saving your resume',
    async reach(p) {
      for (let i = 0; i < 20; i++) {
        await p.waitForTimeout(1000);
        const ok = await p.evaluate(() => {
          const btn = document.getElementById('btn-save');
          if (!btn || btn.getBoundingClientRect().width === 0) return false;
          // Give the resume a field so an empty-form guard cannot be mistaken for the offline refusal.
          const name = [...document.querySelectorAll('input')]
            .find((e) => e.getBoundingClientRect().width > 0 && !e.value);
          if (name) {
            name.value = 'Offline probe';
            name.dispatchEvent(new Event('input', { bubbles: true }));
          }
          btn.setAttribute('data-probe', '1');
          return true;
        });
        if (ok) return { ok: true, control: '[data-probe="1"]' };
      }
      return { ok: false, why: '#btn-save never became visible' };
    },
  },
  // ★asset-hub's online-only write. saveStrategy (asset-hub.html:2916) is gated by
  // whRequireOnline('Saving this strategy') at :2929 and bound to #rcm-save at :2908 - bound to the
  // HANDLER, so this case names the id rather than matching a label. THREE gates, every one MEASURED
  // rather than guessed: #asset-view-toggle reveals #reliability-card (display:none - found by walking
  // the ancestor chain after four selector guesses matched nothing); [data-node-id] selects an asset
  // (dialog_targets.mjs already records this precondition); then "Edit strategy" opens the RCM modal.
  // NOTE this page also has QUEUED writes (rcm_fmea_modes is an offline-queue adopter) - those do NOT
  // belong to this oracle, which is why the strategy save is the right subject.
  strategy: {
    page: 'asset-hub',
    writePattern: /rest\/v1\/rcm_strategies(\?|$)/,
    action: 'Saving this strategy',
    async reach(p) {
      await p.evaluate(() => {
        const w = document.getElementById('asset-view-toggle');
        if (w) w.click();
      }).catch(() => {});
      await p.waitForTimeout(1500);
      await p.evaluate(() => {
        const n = document.querySelector('[data-node-id]');
        if (n) n.click();
      }).catch(() => {});
      await p.waitForTimeout(2500);
      for (let i = 0; i < 20; i++) {
        await p.waitForTimeout(1000);
        const ok = await p.evaluate(() => {
          const save = document.getElementById('rcm-save');
          if (!save || save.getBoundingClientRect().width === 0) {
            const opener = [...document.querySelectorAll('button')]
              .find((b) => /edit strategy/i.test(b.textContent || '')
                           && b.getBoundingClientRect().width > 0);
            if (opener) opener.click();
            return false;
          }
          save.setAttribute('data-probe', '1');
          return true;
        });
        if (ok) return { ok: true, control: '[data-probe="1"]' };
      }
      return { ok: false, why: 'RCM strategy modal never opened with its save control' };
    },
  },
  // ★NINE PAGES HAD NO CASE AT ALL - a coverage gap that looks exactly like coverage, because the family
  // reported "11 of 11 passing" while nine surfaces were never asked anything. logbook has the widest
  // blast radius on the platform (v_logbook_truth feeds eleven consumers) and submitAsset()
  // (logbook.html:2424) is gated by whRequireOnline('Adding this asset'), so it is the right first write
  // to hold to this oracle. The opener comes from dialog_targets.mjs rather than a guess.
  logbook: {
    page: 'logbook',
    // ★A TABLE NAME IS NOT A WRITE. My first pattern here was /asset_nodes|logbook/, which matched
    // `HEAD logbook?select=id&hive_id=eq...` - a PostgREST COUNT READ the page fires to refresh a
    // badge - and reported "2 write requests attempted (must be 0)" against a page whose write is
    // correctly gated (submitAsset, logbook.html:2424, whRequireOnline at :2427). I authored this case
    // minutes earlier; it manufactured a defect against working code on the first run. Anchor on the
    // WRITE endpoint shape, and note the DB was checked immediately: asset_nodes gained 0 rows.
    writePattern: /rest\/v1\/asset_nodes(\?|$)/,
    action: 'Adding this asset',
    async reach(p) {
      for (let i = 0; i < 20; i++) {
        await p.waitForTimeout(1000);
        const ok = await p.evaluate(() => {
          const modal = document.getElementById('asset-modal');
          const open = modal && getComputedStyle(modal).display !== 'none';
          if (!open) {
            const btn = document.getElementById('open-asset-modal-btn');
            if (btn && btn.getBoundingClientRect().width > 0) btn.click();
            return false;
          }
          // Fill the fields so a validation guard cannot be mistaken for the offline refusal.
          [...modal.querySelectorAll('input,textarea')]
            .filter((e) => e.getBoundingClientRect().width > 0 && e.type !== 'file')
            .forEach((e) => {
              e.value = e.type === 'number' ? '1' : 'Offline probe asset';
              e.dispatchEvent(new Event('input', { bubbles: true }));
              e.dispatchEvent(new Event('change', { bubbles: true }));
            });
          // ★BIND TO THE HANDLER, NOT THE LABEL. The modal shows TWO buttons reading "Register Asset",
          // and a text match took the first visible one - which fired 2 write requests offline and
          // toasted "Entry saved.", a FAIL I could not attribute because I did not know which control I
          // had pressed. logbook.html:3568 wires the real one: #asset-submit-btn ->
          // addEventListener('click', submitAsset), and submitAsset (:2424) carries whRequireOnline at
          // :2427. Naming the id makes the verdict about THAT write instead of whatever shares its
          // label. (A text match also nearly missed it entirely: my first pattern - save|add|create|
          // submit - did not match "Register Asset" at all.)
          const save = document.getElementById('asset-submit-btn');
          if (!save || save.getBoundingClientRect().width === 0) return false;
          save.setAttribute('data-probe', '1');
          return true;
        });
        if (ok) return { ok: true, control: '[data-probe="1"]' };
      }
      return { ok: false, why: 'asset modal never opened with a save control' };
    },
  },
  exam: {
    page: 'skillmatrix',
    writePattern: /rpc\/grade_skill_exam|skill_exam_attempts|skill_badges/,
    action: 'Submitting your exam',
    async reach(p) {
      // Open a lesson, scroll it (the Take-Exam button is deliberately disabled until the lesson is
      // read - that gate is real and must not be bypassed), then answer all ten questions.
      const cell = await p.evaluate(() => {
        // .disc-card[data-disc] is the matrix cell (role=button, "Open <discipline>").
        const c = document.querySelector('.disc-card[data-disc]');
        if (!c) return null;
        c.click(); return (c.getAttribute('data-disc') || '').slice(0, 30);
      });
      if (!cell) return { ok: false, why: 'no skill cell found' };
      await p.waitForTimeout(1500);
      // The gate watches #lesson-body-scroll and enables the button only within 80px of the bottom,
      // on a real 'scroll' EVENT - setting scrollTop alone does not always dispatch one, so fire it.
      await p.evaluate(() => {
        const box = document.getElementById('lesson-body-scroll');
        if (!box) return;
        box.scrollTop = box.scrollHeight;
        box.dispatchEvent(new Event('scroll', { bubbles: true }));
      });
      await p.waitForTimeout(800);
      const started = await p.evaluate(() => {
        const b = document.getElementById('lesson-exam-btn');
        if (!b || b.disabled) return false;
        b.click(); return true;
      });
      if (!started) return { ok: false, why: 'Take Exam still disabled after scrolling the lesson' };
      await p.waitForTimeout(1500);
      // Answer every question, advancing with Next until the last one.
      for (let i = 0; i < 12; i++) {
        const state = await p.evaluate(() => {
          // pick the first unselected option of the CURRENT question
          const opt = document.querySelector('.exam-option:not(.selected)');
          if (opt) opt.click();
          const nb = document.getElementById('exam-next-btn');
          return { label: nb ? nb.textContent.trim() : null, disabled: nb ? nb.disabled : true };
        });
        if (!state.label) return { ok: false, why: 'no exam-next-btn' };
        if (/submit/i.test(state.label)) return { ok: true, control: '#exam-next-btn', note: 'on the last question' };
        await p.evaluate(() => document.getElementById('exam-next-btn')?.click());
        await p.waitForTimeout(400);
      }
      return { ok: false, why: 'never reached the last question' };
    },
  },

  // The services HAIL - the marketplace's service-request write, on the pane the ?section=services
  // param + a real tab click reveal. svcRequireOnline is this flow's own guard (the az_fail_offline
  // comment names it as the codebase's answer), so this measures the guard where it lives.
  hail: {
    page: 'marketplace',
    query: '?section=services',
    writePattern: /service_requests|rpc\/(svc_|hail|create_service)/,
    action: 'Hailing a service',
    async reach(p) {
      await p.evaluate(() => document.querySelector('.section-tab[data-section="services"]')?.click());
      await p.waitForTimeout(2500);
      for (let i = 0; i < 15; i++) {
        await p.waitForTimeout(1000);
        const st = await p.evaluate(() => {
          const go = document.getElementById('svc-hail-go');
          if (!go || go.getBoundingClientRect().width === 0) return 'waiting';
          const sel = document.getElementById('svc-hail-item');
          if (sel && sel.options.length > 1 && !sel.value) {
            sel.selectedIndex = 1; sel.dispatchEvent(new Event('change', { bubbles: true }));
          }
          const addr = document.getElementById('svc-hail-address');
          if (addr && !addr.value) { addr.value = 'Offline probe site'; addr.dispatchEvent(new Event('input', { bubbles: true })); }
          return 'ready';
        });
        if (st === 'ready') return { ok: true, control: '#svc-hail-go' };
      }
      return { ok: false, why: 'the hail form never rendered on the services pane' };
    },
  },

  // THE TEETH CASE, and a real measurement at the same time. report-sender's saveContact has no
  // connectivity check (measured statically across the roster), so this case must FAIL - if it passed,
  // the prover would be incapable of detecting a missing guard and its PASS on skillmatrix would be
  // worthless. Planting a fake defect was the alternative; pointing it at an actual one is better,
  // because the run doubles as this page's evidence.
  contact: {
    page: 'report-sender',
    writePattern: /report_contacts/,
    action: 'Adding a contact',
    async reach(p) {
      const opened = await p.evaluate(() => {
        const t = [...document.querySelectorAll('button,a')]
          .find(x => /add contact/i.test(x.textContent || ''));
        if (!t) return false;
        t.click(); return true;
      });
      if (!opened) return { ok: false, why: 'no "+ Add contact" control' };
      await p.waitForTimeout(1000);
      const filled = await p.evaluate(() => {
        const n = document.getElementById('contact-name');
        const e = document.getElementById('contact-email');
        if (!n || !e) return false;
        n.value = 'Offline Probe'; n.dispatchEvent(new Event('input', { bubbles: true }));
        e.value = 'offline.probe@example.invalid'; e.dispatchEvent(new Event('input', { bubbles: true }));
        const b = [...document.querySelectorAll('#sheet-overlay button')]
          .find(x => /save contact/i.test(x.textContent || ''));
        if (b) { b.setAttribute('data-probe-save', '1'); return true; }
        return false;
      });
      if (!filled) return { ok: false, why: 'contact fields or Save Contact not found' };
      return { ok: true, control: '[data-probe-save="1"]' };
    },
  },

  // The SEND - the irreversible outward action. Its refusal lands in #email-error.
  send: {
    page: 'report-sender',
    writePattern: /send-report-email/,
    action: 'Sending these reports',
    async reach(p) {
      const picked = await p.evaluate(() => {
        const r = [...document.querySelectorAll('button')]
          .find(x => x.offsetParent !== null && /PM Overdue/i.test(x.textContent || ''));
        if (!r) return false;
        r.click();
        const em = document.getElementById('email-input');
        if (!em) return false;
        em.value = 'offline.probe@example.invalid';
        em.dispatchEvent(new Event('input', { bubbles: true }));
        return true;
      });
      if (!picked) return { ok: false, why: 'could not select a report + recipient' };
      // Wait for the send control to become usable - report generation gates it.
      for (let i = 0; i < 30; i++) {
        await p.waitForTimeout(1000);
        const ok = await p.evaluate(() => {
          const b = document.getElementById('send-btn');
          return !!(b && !b.disabled);
        });
        if (ok) return { ok: true, control: '#send-btn' };
      }
      return { ok: false, why: 'send-btn never became enabled' };
    },
  },
  reaction: {
    page: 'community',
    writePattern: /community_reactions/,
    action: 'Reacting to this post',
    async reach(p) {
      for (let i = 0; i < 20; i++) {
        await p.waitForTimeout(1000);
        const found = await p.evaluate(() => {
          const b = [...document.querySelectorAll('button')].find(x =>
            x.offsetParent !== null && /(\u{1F44D}|\u2764|\u{1F4AA}|\u{1F64F}|\u{1F44F})/u.test(x.textContent || ''));
          if (b) { b.setAttribute('data-probe', '1'); return true; }
          return false;
        });
        if (found) return { ok: true, control: '[data-probe="1"]' };
      }
      return { ok: false, why: 'no reaction button in the feed' };
    },
  },
  dismiss: {
    page: 'alert-hub',
    writePattern: /alert_dismissals/,
    action: 'Dismissing this alert',
    async reach(p) {
      for (let i = 0; i < 20; i++) {
        await p.waitForTimeout(1000);
        const found = await p.evaluate(() => {
          const b = [...document.querySelectorAll('button,[role=button]')].find(x =>
            x.offsetParent !== null && /dismiss|handled|snooze/i.test(
              (x.textContent || '') + (x.getAttribute('aria-label') || '')));
          if (b) { b.setAttribute('data-probe', '1'); return true; }
          return false;
        });
        if (found) return { ok: true, control: '[data-probe="1"]' };
      }
      return { ok: false, why: 'no dismiss control in the feed' };
    },
  },
  publish: {
    page: 'shift-brain',
    writePattern: /shift_plans/,
    action: 'Publishing this plan',
    async reach(p) {
      for (let i = 0; i < 25; i++) {
        await p.waitForTimeout(1000);
        const ok = await p.evaluate(() => {
          const b = document.getElementById('publish-btn');
          return !!(b && b.offsetParent !== null && !b.disabled);
        });
        if (ok) return { ok: true, control: '#publish-btn' };
      }
      return { ok: false, why: 'publish-btn never became usable' };
    },
  },
  signup: {
    page: 'index',
    writePattern: /early_access_emails|auth\/v1\/signup/,
    action: 'Creating your account',
    async reach(p) {
      for (let i = 0; i < 20; i++) {
        await p.waitForTimeout(1000);
        const filled = await p.evaluate(() => {
          const u = document.getElementById('su-username');
          if (!u || u.offsetParent === null) {
            const opener = [...document.querySelectorAll('button,a')].find(x =>
              x.offsetParent !== null && /sign up|create account|get started/i.test(x.textContent || ''));
            if (opener) opener.click();
            return false;
          }
          const set = (id, v) => { const e = document.getElementById(id);
            if (e) { e.value = v; e.dispatchEvent(new Event('input', { bubbles: true })); } };
          set('su-username', 'offline_probe_user');
          set('su-password', 'test1234');
          set('su-confirm', 'test1234');
          set('su-displayname', 'Offline Probe');
          return true;
        });
        if (filled) return { ok: true, control: '#su-btn' };
      }
      return { ok: false, why: 'signup form never reachable' };
    },
  },
  persona: {
    page: 'index',
    writePattern: /worker_profiles/,
    action: 'Saving your preference',
    async reach(p) {
      for (let i = 0; i < 20; i++) {
        await p.waitForTimeout(1000);
        const ok = await p.evaluate(() => {
          const b = document.getElementById('oh-persona-toggle');
          return !!(b && b.getBoundingClientRect().width > 0);
        });
        if (ok) return { ok: true, control: '#oh-persona-toggle' };
      }
      return { ok: false, why: 'oh-persona-toggle not rendered (signed-in ops-home only)' };
    },
  },
  partdelete: {
    page: 'inventory',
    writePattern: /inventory_items/,
    action: 'Deleting this part',
    async reach(p) {
      for (let i = 0; i < 22; i++) {
        await p.waitForTimeout(1000);
        const found = await p.evaluate(() => {
          const b = [...document.querySelectorAll('button')].find(x =>
            x.getBoundingClientRect().width > 0 && /remove from inventory/i.test(x.textContent || ''));
          if (b) { b.scrollIntoView({ block: 'center' }); b.setAttribute('data-probe', '1'); return true; }
          // the control lives on an expanded part card - open the first one
          const card = [...document.querySelectorAll('[onclick*=\"openDetail\"],[data-part-id],.part-row,.inv-card')]
            .find(x => x.getBoundingClientRect().width > 0);
          if (card) card.click();
          return false;
        });
        if (found) return { ok: true, control: '[data-probe=\"1\"]' };
      }
      return { ok: false, why: 'no "Remove from inventory" control reachable' };
    },
  },
  newtask: {
    page: 'pm-scheduler',
    writePattern: /pm_scope_items/,
    action: 'Adding this task',
    async reach(p) {
      // ★THE OPENER IS STATE-GATED: probed live, the "Add Task" buttons EXIST but report width 0 until an
      // asset is selected, so the loop below - which requires width > 0 - never found one and spent 22
      // seconds concluding "control unreachable". That read as an unmeasurable page when it is simply a
      // detail view nobody had opened. dialog_targets.mjs already records this precondition for
      // pm-scheduler (click a .asset-card, pm-scheduler.html:1758 onclick=openDetail), so it is reused
      // rather than re-derived.
      await p.evaluate(() => {
        const card = document.querySelector('.asset-card');
        if (card) card.click();
      }).catch(() => {});
      await p.waitForTimeout(1800);
      for (let i = 0; i < 22; i++) {
        await p.waitForTimeout(1000);
        const ok = await p.evaluate(() => {
          const sheet = document.getElementById('add-task-sheet');
          if (!sheet || !sheet.classList.contains('open')) {
            const opener = [...document.querySelectorAll('button')].find(x =>
              x.getBoundingClientRect().width > 0 && /add.*task|new task/i.test(x.textContent || ''));
            if (opener) opener.click();
            return false;
          }
          // fill whatever text/select inputs the sheet exposes so validation cannot be the refusal
          [...sheet.querySelectorAll('input,textarea')].forEach((e) => {
            if (e.type === 'number' && !e.value) e.value = '30';
            else if ((e.type === 'text' || e.tagName === 'TEXTAREA') && !e.value) e.value = 'Offline probe task';
            e.dispatchEvent(new Event('input', { bubbles: true }));
          });
          const save = [...sheet.querySelectorAll('button')].find(x =>
            /save|add|create/i.test(x.textContent || ''));
          if (save) { save.setAttribute('data-probe', '1'); return true; }
          return false;
        });
        if (ok) return { ok: true, control: '[data-probe="1"]' };
      }
      return { ok: false, why: 'add-task sheet never opened with a save control' };
    },
  },
  newproject: {
    page: 'project-manager',
    writePattern: /generate_project_code|rest\/v1\/projects/,
    action: 'Creating this project',
    async reach(p) {
      // The wizard is THREE STEPS and #wiz-create only exists on step 3: step 1 keeps wiz-next-1
      // DISABLED until a type tile is picked, and step 2's "start with a blank project" link is a
      // one-click jump to step 3. The old reach only re-clicked the opener, so it sat on step 1 for
      // 22 seconds and reported the control unreachable (measured 2026-08-21: page healthy, probe
      // stale). One rung of the ladder per second:
      for (let i = 0; i < 22; i++) {
        await p.waitForTimeout(1000);
        const ok = await p.evaluate(() => {
          const vis = (el) => el && el.getBoundingClientRect().width > 0;
          const btn = document.getElementById('wiz-create');
          if (vis(btn)) {
            // fill the visible fields so a validation refusal cannot be mistaken for the guard
            [...document.querySelectorAll('input,textarea,select')].forEach((e) => {
              if (!vis(e)) return;
              if ((e.type === 'text' || e.tagName === 'TEXTAREA') && !e.value) e.value = 'Offline probe project';
              if (e.type === 'number' && !e.value) e.value = '1000';
              e.dispatchEvent(new Event('input', { bubbles: true }));
            });
            return true;
          }
          const tile = [...document.querySelectorAll('.type-tile[onclick*="wizardPickType"]')].find(vis);
          const next1 = document.getElementById('wiz-next-1');
          const blank = [...document.querySelectorAll('.blank-link')].find(vis);
          if (vis(next1) && next1.disabled && tile) tile.click();
          else if (vis(next1) && !next1.disabled) next1.click();
          else if (blank) blank.click();
          else {
            const opener = [...document.querySelectorAll('button')].find(x =>
              vis(x) && /new project/i.test(x.textContent || ''));
            if (opener) opener.click();
          }
          return false;
        });
        if (ok) return { ok: true, control: '#wiz-create' };
      }
      return { ok: false, why: 'project wizard never reached #wiz-create' };
    },
  },
  // Select on the ONCLICK BINDING, not the label - pm-scheduler taught that three buttons can share a
  // label while being bound to three different functions, and a text-matching reach picks the wrong one.
  delproject: {
    page: 'project-manager',
    writePattern: /rest\/v1\/projects/,
    action: 'Deleting this project',
    async reach(p) {
      for (let i = 0; i < 22; i++) {
        await p.waitForTimeout(1000);
        const st = await p.evaluate(() => {
          const byBinding = [...document.querySelectorAll('[onclick]')]
            .filter((x) => /deleteProject\(/.test(x.getAttribute('onclick') || ''));
          const usable = byBinding.find((x) => x.getBoundingClientRect().width > 0);
          if (usable) { usable.setAttribute('data-probe', '1'); return 'ready'; }
          // Delete lives on a project's DETAIL view - open the first project card.
          const card = [...document.querySelectorAll('[onclick]')]
            .find((x) => /openDetail\(|showDetail\(|openProject\(/.test(x.getAttribute('onclick') || '')
                         && x.getBoundingClientRect().width > 0);
          if (card) { card.click(); return 'opened-a-project'; }
          return 'waiting';
        });
        if (st === 'ready') return { ok: true, control: '[data-probe="1"]' };
      }
      return { ok: false, why: 'no visible deleteProject binding, and no project card to open' };
    },
  },
  kick: {
    page: 'hive',
    writePattern: /hive_members/,
    action: 'Removing this member',
    async reach(p) {
      for (let i = 0; i < 22; i++) {
        await p.waitForTimeout(1000);
        const st = await p.evaluate(() => {
          // ★THE MEMBER LIST IS COLLAPSED BY DEFAULT. Probed: two kickMember controls are in the DOM
          // from first paint, hidden by #members-list (style="display:none", hive.html:1512), which
          // #btn-toggle-members reveals (the toggle pair is wired at hive.html:1350). The case reported
          // "needs a second member in the hive" - refuted by psql, members=3. A 'needs data' message
          // that is false is worse than no message: it retires a real check behind an excuse nobody
          // re-tests.
          const _t = document.getElementById('btn-toggle-members');
          const _l = document.getElementById('members-list');
          if (_t && _l && getComputedStyle(_l).display === 'none') _t.click();
          const byBinding = [...document.querySelectorAll('[onclick]')]
            .filter((x) => /kickMember\(/.test(x.getAttribute('onclick') || ''));
          const usable = byBinding.find((x) => x.getBoundingClientRect().width > 0);
          if (usable) { usable.scrollIntoView({ block: 'center' }); usable.setAttribute('data-probe', '1'); return 'ready'; }
          return byBinding.length ? 'present-but-zero-width' : 'absent';
        });
        if (st === 'ready') return { ok: true, control: '[data-probe="1"]' };
      }
      return { ok: false, why: 'no removable member rendered (needs a second member in the hive)' };
    },
  },
  join: {
    page: 'hive',
    writePattern: /hive_members|rpc\/find_hive_by_code/,
    action: 'Joining this hive',
    async reach(p) {
      // ★A TWO-LEVEL GATE, both levels measured. #join-code-input and #btn-submit-join are in the DOM
      // from the start, hidden by an ancestor #view-join.hidden. The control that reveals it,
      // #btn-hive-switch-join ("Join Another Hive"), is ITSELF hidden inside #hive-menu - which an
      // [aria-controls] sweep of this page identified as opened by #btn-hive-menu. So the loop below,
      // which only looks for a visible opener, could never reach either level and reported "join form
      // never reachable" - a statement about the probe, not the page.
      await p.evaluate(() => {
        const m = document.getElementById('btn-hive-menu');
        if (m) m.click();
      }).catch(() => {});
      await p.waitForTimeout(1200);
      await p.evaluate(() => {
        const j = document.getElementById('btn-hive-switch-join') || document.getElementById('btn-go-join');
        if (j) j.click();
      }).catch(() => {});
      await p.waitForTimeout(1800);
      for (let i = 0; i < 22; i++) {
        await p.waitForTimeout(1000);
        const st = await p.evaluate(() => {
          const code = document.getElementById('join-code-input');
          if (!code || code.getBoundingClientRect().width === 0) {
            const opener = [...document.querySelectorAll('[onclick],button')]
              .find((x) => /join/i.test((x.getAttribute('onclick') || '') + (x.textContent || ''))
                           && x.getBoundingClientRect().width > 0);
            if (opener) opener.click();
            return 'opening';
          }
          // A valid 6-char code, so the format check cannot be mistaken for the offline refusal.
          code.value = 'ABC123';
          code.dispatchEvent(new Event('input', { bubbles: true }));
          const btn = document.getElementById('btn-submit-join');
          if (btn) { btn.setAttribute('data-probe', '1'); return 'ready'; }
          return 'no-submit';
        });
        if (st === 'ready') return { ok: true, control: '[data-probe="1"]' };
      }
      return { ok: false, why: 'join form never reachable' };
    },
  },
  reply: {
    page: 'community',
    writePattern: /community_replies/,
    action: 'Posting this reply',
    async reach(p) {
      for (let i = 0; i < 22; i++) {
        await p.waitForTimeout(1000);
        const st = await p.evaluate(() => {
          const overlay = document.getElementById('thread-overlay');
          if (!overlay || !overlay.classList.contains('open')) {
            // open the first post's thread - the card itself or a reply-count affordance
            const opener = [...document.querySelectorAll('[onclick]')]
              .find((x) => /openThread\(|showThread\(/.test(x.getAttribute('onclick') || '')
                           && x.getBoundingClientRect().width > 0);
            if (opener) { opener.click(); return 'opening'; }
            return 'no-thread-opener';
          }
          const ta = overlay.querySelector('textarea,input[type=text]');
          if (!ta) return 'no-reply-field';
          ta.value = 'Offline probe reply - checking the bearing note.';
          ta.dispatchEvent(new Event('input', { bubbles: true }));
          const btn = document.getElementById('btn-submit-reply');
          if (btn) { btn.setAttribute('data-probe', '1'); return 'ready'; }
          return 'no-submit';
        });
        if (st === 'ready') return { ok: true, control: '[data-probe="1"]' };
      }
      return { ok: false, why: 'thread overlay / reply field never reachable' };
    },
  },
  scopestatus: {
    page: 'project-manager',
    writePattern: /project_items/,
    action: 'Updating this item',
    async reach(p) {
      // ★TWO GATES, BOTH MEASURED. The pill lives on a project DETAIL and then only inside the SCOPE
      // pane: renderActivePane(key) draws it solely when key === 'scope' (project-manager.html:2130), and
      // the pane switcher uses button.dataset.pane on #detail-tabs - NOT [data-tab] or [role=tab], which
      // is why a generic tab sweep clicked four buttons and still found 0 pills.
      // This case reported "needs a project with scope items" for as long as it existed. That was FALSE:
      // project_items=90 and all four projects have them (10/7/7/6). The excuse nearly buried the real
      // cause, and for a while made a working page look like it might be dropping 90 items on the floor.
      await p.evaluate(() => {
        const d = document.querySelector('[onclick*="openDetail("]');
        if (d) d.click();
      }).catch(() => {});
      await p.waitForTimeout(4000);
      await p.evaluate(() => {
        const tabs = document.getElementById('detail-tabs');
        const btn = tabs && [...tabs.querySelectorAll('button')].find((b) => b.dataset.pane === 'scope');
        if (btn) btn.click();
      }).catch(() => {});
      await p.waitForTimeout(2500);
      for (let i = 0; i < 25; i++) {
        await p.waitForTimeout(1000);
        const st = await p.evaluate(() => {
          // The status pill is bound to cycleScopeStatus and lives on a project's DETAIL view.
          const pill = [...document.querySelectorAll('[onclick]')]
            .find((x) => /cycleScopeStatus\(/.test(x.getAttribute('onclick') || '')
                         && x.getBoundingClientRect().width > 0);
          if (pill) { pill.scrollIntoView({ block: 'center' }); pill.setAttribute('data-probe', '1'); return 'ready'; }
          const card = [...document.querySelectorAll('[onclick]')]
            .find((x) => /openDetail\(|showDetail\(|openProject\(/.test(x.getAttribute('onclick') || '')
                         && x.getBoundingClientRect().width > 0);
          if (card) { card.click(); return 'opening-a-project'; }
          return 'waiting';
        });
        if (st === 'ready') return { ok: true, control: '[data-probe="1"]' };
      }
      return { ok: false, why: 'no cycleScopeStatus pill on any project detail (needs a project with scope items)' };
    },
  },
  lessons: {
    page: 'project-manager',
    writePattern: /rest\/v1\/projects/,
    action: 'Saving these lessons',
    async reach(p) {
      // ★SAME STATE-GATE AS pm-scheduler's newtask: the saveLessons control lives on a PROJECT DETAIL,
      // and the loop below requires width > 0, so with no project open it spent 25 seconds concluding
      // "no visible saveLessons control" - a fact about which view was on screen, not about the page.
      // Open a project first. Probing for the gate beats guessing: three selector guesses elsewhere in
      // this session matched zero elements while every ancestor-walk / registry reuse worked first try.
      await p.evaluate(() => {
        // PROBED, not guessed: the opener is a DIV carrying onclick="openDetail('<project-id>')", and
        // saveLessons is not in the DOM AT ALL until that detail is open (measured: 0 nodes on the list
        // view). My first attempt here guessed .project-card / [onclick*=openProject] and matched
        // nothing - the same mistake I had just written a rule against.
        const card = document.querySelector('[onclick*="openDetail("]');
        if (card) card.click();
      }).catch(() => {});
      await p.waitForTimeout(2200);
      for (let i = 0; i < 25; i++) {
        await p.waitForTimeout(1000);
        const st = await p.evaluate(() => {
          const btn = [...document.querySelectorAll('[onclick]')]
            .find((x) => /saveLessons\(/.test(x.getAttribute('onclick') || '')
                         && x.getBoundingClientRect().width > 0);
          if (btn) {
            // give the field a value so an empty-input guard cannot be mistaken for the offline refusal
            const ta = [...document.querySelectorAll('textarea')]
              .find((t) => t.getBoundingClientRect().width > 0);
            if (ta) { ta.value = 'Offline probe lesson - stage the spare impeller earlier.';
                      ta.dispatchEvent(new Event('input', { bubbles: true })); }
            btn.scrollIntoView({ block: 'center' });
            btn.setAttribute('data-probe', '1');
            return 'ready';
          }
          // The lessons textarea + Save button live in the SIGN-OFF pane and are only rendered when
          // that pane is activated (buildDetailTabs builds the strip; the pane body is lazy).
          // Measured 2026-08-21: detail open, tabs present, saveLessons 0 nodes until the Sign-off
          // tab is clicked - so with the detail open, the next rung is the tab, not more waiting.
          const signoffTab = [...document.querySelectorAll('#detail-tabs button, [data-pane]')]
            .find((x) => x.dataset && x.dataset.pane === 'signoff' && x.getBoundingClientRect().width > 0);
          if (signoffTab) { signoffTab.click(); return 'activating-signoff'; }
          const card = [...document.querySelectorAll('[onclick]')]
            .find((x) => /openDetail\(|showDetail\(|openProject\(/.test(x.getAttribute('onclick') || '')
                         && x.getBoundingClientRect().width > 0);
          if (card) { card.click(); return 'opening'; }
          return 'waiting';
        });
        if (st === 'ready') return { ok: true, control: '[data-probe="1"]' };
      }
      return { ok: false, why: 'no visible saveLessons control on the project detail' };
    },
  },
  signup: {
    page: 'index',
    anon: true,
    // The signup form lives inside the auth modal, which the platform opens with ?signin=1 (that is the
    // link other pages use). Landing on the marketing page alone never renders #su-username, which is
    // why an earlier attempt reported it unreachable both signed in AND signed out.
    query: '?signin=1',
    writePattern: /early_access_emails|auth\/v1\/signup/,
    action: 'Creating your account',
    async reach(p) {
      for (let i = 0; i < 22; i++) {
        await p.waitForTimeout(1000);
        const st = await p.evaluate(() => {
          const u = document.getElementById('su-username');
          if (!u || u.getBoundingClientRect().width === 0) {
            // The modal opens on the SIGN-IN tab; switch to sign-up through its own tab control.
            const tab = document.getElementById('tab-signup');
            if (tab) { tab.click(); return 'switching-tab'; }
            return 'waiting';
          }
          const set = (id, v) => { const e = document.getElementById(id);
            if (e) { e.value = v; e.dispatchEvent(new Event('input', { bubbles: true })); } };
          set('su-username', 'offline_probe_user');
          set('su-password', 'test1234');
          set('su-confirm', 'test1234');
          set('su-displayname', 'Offline Probe');
          return document.getElementById('su-btn') ? 'ready' : 'no-btn';
        });
        if (st === 'ready') return { ok: true, control: '#su-btn' };
      }
      return { ok: false, why: 'signup form never reachable even signed out' };
    },
  },
};

const args = process.argv.slice(2);
if (args.includes('--list')) { console.log('cases:', Object.keys(CASES).join(', ')); process.exit(0); }
const CASE = (() => { const i = args.indexOf('--case'); return i >= 0 ? args[i + 1] : null; })();
const c = CASES[CASE];
if (!c) { console.log('pass --case <' + Object.keys(CASES).join('|') + '>'); process.exit(2); }

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
// Some views only exist for a signed-OUT visitor - index's landing page is the whole marketing
// surface, and signing in replaces it with the ops-home. A case marked `anon` skips the sign-in.
if (!c.anon) await assertSignedIn(signIn(ctx, 'supervisor'));
const p = await ctx.newPage();

let writesAttempted = 0;
const attempted = [];
await ctx.route('**/*', async (route) => {
  const u = route.request().url();
  const method = route.request().method();
  if (c.writePattern.test(u) && method !== 'GET') {
    writesAttempted++; attempted.push(method + ' ' + u.split('/').slice(-1)[0].slice(0, 40));
    return route.abort('internetdisconnected');   // it must never have got this far
  }
  return route.continue();
});
const errs = [];
p.on('pageerror', (e) => errs.push(String(e.message).slice(0, 120)));

await p.goto(`${ORIGIN}/${c.page}.html${c.query || ''}`, { waitUntil: 'domcontentloaded', timeout: 45000 });
await p.waitForTimeout(5000);

console.log(`--- reaching the control on ${c.page} (ONLINE) ---`);
const reached = await c.reach(p);
console.log('   ', JSON.stringify(reached));
if (!reached.ok) { console.log('   cannot grade: control unreachable'); await browser.close(); process.exit(0); }

// GO OFFLINE: both halves.
await p.evaluate(() => Object.defineProperty(window.navigator, 'onLine',
  { get: () => false, configurable: true }));
await ctx.setOffline(true);
const onlineNow = await p.evaluate(() => navigator.onLine);
console.log(`--- offline: navigator.onLine=${onlineNow} + network cut ---`);

const before = writesAttempted;
await p.evaluate((sel) => document.querySelector(sel)?.click(), reached.control);

// ★SAMPLED ACROSS THE WINDOW, NOT READ AT ITS END. This waited 3 SECONDS and then read once - and a
// toast on this platform lives about one. Measured on hive/kick: the page DOES refuse out loud
// (hive.html:3918 calls whRequireOnline('Removing this member', (m) => showToast(m)) and returns BEFORE
// the confirm dialog, deliberately), yet this reported "told the person: false" and would have shipped
// as a defect against correct code. Same fault, same fix as prove_quota_legible.mjs: sample throughout
// and take the UNION of everything that appeared, because what a page SAID over a window is not what it
// happens to be showing at the end of one.
const readSaid = () => p.evaluate(() => {
  // ★EVERY PAGE HAS A DIFFERENT TOAST HOST, so an id list is a maintenance trap that produces false
  // FAILs: this reported alert-hub as silent because its showToast renders into #wh-toast, and reported
  // report-sender as silent because that form answers in #sheet-error. Two false FAILs from the same
  // cause. So the reader does BOTH - the known hosts, plus a search of the whole visible text for
  // whOfflineMessage's own distinctive tail.
  // The body-wide half is safe ONLY because that tail is unique to the helper: a loose keyword like
  // "offline" would match a page's own marketing copy and pass on anything (see the body-wide-match
  // lesson). Anchoring on the exact sentence the helper writes keeps it specific.
  // ★'hive-toast' ADDED - the THIRD false FAIL from this list, exactly as the comment above predicted.
  // hive's showToast writes to #hive-toast, so kick reported "told the person: false" while the page was
  // refusing out loud the whole time. An id list is a maintenance trap: it fails CLOSED, and a missing
  // entry looks identical to a silent page. The body-wide tail search is the real safety net; this list
  // is only the fast path.
  const HOSTS = ['toast-msg', 'toast', 'toast-text', 'wh-toast', 'hive-toast', 'sheet-error', 'email-error',
                 'email-status-text', 'upload-status', 'su-error', 'join-error', 'create-error',
                 'amc-msg'];
  const parts = HOSTS.map((id) => document.getElementById(id))
    .concat([...document.querySelectorAll('[role=status]'), ...document.querySelectorAll('[role=alert]')])
    .filter(Boolean).map((e) => (e.textContent || '').trim());
  const bodyText = (document.body.innerText || '');
  const TAIL = /nothing was sent, so nothing is half-done/i;
  // Split on lines rather than writing a [^\n] class: a backslash escape in generated code has now
  // collapsed on me seven times in one session, and split() needs no escape at all.
  const bodyHit = TAIL.test(bodyText)
    ? (bodyText.split(String.fromCharCode(10)).find((l) => TAIL.test(l)) || '').trim()
    : '';
  return (parts.join(' | ') + (bodyHit ? ' | BODY: ' + bodyHit : '')).slice(0, 260);
});

const _seen = new Set();
for (let i = 0; i < 16; i++) {
  const t = await readSaid();
  if (t) t.split(' | ').forEach((x) => { if (x.trim()) _seen.add(x.trim()); });
  await p.waitForTimeout(250);
}
const said = [...
  _seen].join(' | ').slice(0, 400);
const fired = writesAttempted - before;
const told = /offline|nothing was sent|no connection|needs a connection/i.test(said);

console.log(`   write requests attempted: ${fired} (must be 0)`, fired ? attempted : '');
console.log(`   told the person         : ${told}`);
console.log(`   what it said            : ${JSON.stringify(said)}`);
console.log(`   pageerrors              : ${errs.length ? errs : 'none'}`);
const pass = fired === 0 && told;
console.log(`\n  ${pass ? 'PASS' : 'FAIL'} — ${c.page} / ${CASE}: refused before firing AND said so = ${pass}`);
// PER-CASE REPORT ARTIFACT (2026-08-22, the view-pass conversion pipeline): each --case run
// updates its own cell in offline_refusal_report.json (read-modify-write keyed by case), so a
// loop over the cases leaves ONE report the converters and the recency rail can read. A prover
// with no artifact cannot testify about when it last saw the current files.
try {
  const { readFileSync } = await import('fs');
  let rep = {};
  try { rep = JSON.parse(readFileSync('offline_refusal_report.json', 'utf8')); } catch {}
  rep.cases = rep.cases || {};
  rep.cases[CASE] = { case: CASE, page: c.page, ok: pass,
                      refusedBeforeFiring: fired === 0, saidSo: told,
                      said: said.slice(0, 200), ranAt: new Date().toISOString() };
  const { writeFileSync } = await import('fs');
  // A NARROWED RUN MUST NOT CLOBBER THE FULL ONE: this file is read downstream (gates and
  // bank_prover_reports), so a --page/--case spot-check overwriting a whole sweep's verdicts
  // corrupts the BANK, not just a log. Measured on prove_retry_path 2026-08-27.
  writeFileSync((CASE ? 'offline_refusal_report.partial.json' : 'offline_refusal_report.json'), JSON.stringify(rep, null, 1));
} catch (e) { console.log('  (report write skipped:', String(e.message).slice(0, 60), ')'); }
await browser.close();
process.exit(pass ? 0 : 1);
