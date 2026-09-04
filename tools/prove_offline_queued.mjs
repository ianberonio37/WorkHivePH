/* prove_offline_queued.mjs — the sibling of prove_offline_refusal.mjs, for the write class that must NOT
 * refuse.
 *
 * WHY THIS EXISTS. The CG-ufai-A family gives every view an `offline_refusal` cell and no
 * `offline_queued` cell, so a queue-backed surface has no slot that fits its correct behaviour. Eight of
 * the twenty-two roster pages register an offline write queue. For a field-capture write, "refuse before
 * firing and say nothing was sent" is the WRONG requirement, and both verdicts are wrong: green credits a
 * refusal that must not exist, red calls a working feature a defect. See PAGE_TESTBANK_ROADMAP.md §6.
 *
 * THE ORACLE THIS ASSERTS: offline, the write is HELD, the person is told it will sync, and the record is
 * visible immediately. Four checks:
 *    1. ZERO server writes leave while offline.
 *    2. POSITIVE EVIDENCE THE WRITE WAS ACCEPTED — the queue's own store grew, or the record is on
 *       screen. This is the load-bearing one; see below.
 *    3. A message tells the person it was held and will sync — not that it failed, and not silence.
 *    4. Nothing claims the refusal wording. A queue-backed write must NOT say "nothing was sent", because
 *       something WAS accepted; saying otherwise would make the person re-enter work that is already safe.
 *
 * ★CHECK 2 EXISTS BECAUSE THE FIRST VERSION OF THIS FILE PASSED VACUOUSLY, and the failure is worth
 * keeping. Without it the prover asserted only "zero server writes" plus "a reassuring message" — and BOTH
 * are trivially true when the submit never happened. On logbook it returned PASS while the entry went
 * nowhere at all: `wh_logbook_offline/pending` held 0 rows before AND after, the entry was absent from the
 * list, and the sentence it credited ("Offline: new entries will sync when connected") was the page's
 * passive BANNER, not the save's confirmation. I briefly read that as a serious defect — an entry silently
 * discarded under a promise that work was safe — until the control test settled it: pressing the same
 * control ONLINE also produced zero writes and surfaced "MACHINE / EQUIPMENT required". The save was
 * correctly refusing an incomplete form; my reach had filled only two of its required fields.
 * So a queue oracle MUST demand positive proof of acceptance. Zero-writes-and-a-banner is what a blocked
 * submit looks like too, and a prover that cannot tell those apart certifies nothing.
 *
 * THE DRAIN IS DELIBERATELY NOT ASSERTED HERE. "Drains exactly once on reconnect" is the other half of
 * the oracle and it needs a reconnect plus a settle window, which makes a different, slower test; doing
 * it badly is worse than not doing it, because a drain probe that reconnects into a shared database
 * writes real rows. Recorded as the next slice rather than half-built.
 *
 * OFFLINE IS FAKED THE SAME WAY as the refusal prover, for the same reason: `context.setOffline(true)`
 * does NOT flip `navigator.onLine` inside the page, so a branch written as `!navigator.onLine` never
 * runs and the probe would report a page that queues correctly as one that does not. Override the
 * property AND cut the network.
 *
 * ★A REQUEST COUNTER MUST BE ZEROED AT THE ACTION. Counting from page load once showed 16 offline writes
 * on logbook — which read as a write storm escaping the queue — when all 16 were boot traffic and the
 * press itself produced zero. This resets at the press and reports the timeline, not a total, because a
 * total cannot separate a burst from a retry loop from boot noise.
 *
 * Usage:
 *   node tools/prove_offline_queued.mjs --case logbook-entry
 *   node tools/prove_offline_queued.mjs --list
 */
import { chromium } from 'playwright';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

// Wording a queued write is allowed to use. Anchored on phrases the platform's queue paths actually
// print, so this cannot be satisfied by a page merely containing the word "offline" — several pages
// render a passive banner ("You are offline. Some actions may not work.") the whole time.
// (2026-08-25) 'saved on this device … filed when you reconnect' added: project-manager's
// progress-log queue prints it — a legitimate queue-and-tell phrasing the vocabulary predated.
// The oracle's vocabulary is part of the oracle; widen it for real platform phrasings, never
// let a page fail on wording the queue path actually speaks truthfully.
const HELD = /saved offline|will sync|sync when (you )?reconnect|queued|held (locally|offline)|saved on this device|(filed|retry) (when you reconnect|automatically)/i;
// The refusal helper's tail. A queue-backed write must NOT print this.
const REFUSAL = /nothing was sent, so nothing is half-done/i;

const CASES = {
  // T14 sibling (2026-08-25): the PM completion sheet. pm-scheduler registers wh_pm_offline
  // (whCreateQueue, insertDedupIndexed on the (scope_item, worker, date) uidx) and its offline
  // branch enqueues the completion payload, unshifts it locally and toasts 'Saved offline, will
  // sync when you reconnect.' — queue-and-tell, same class as logbook-entry. arm() reuses the
  // T10 walk choreography: Mine filter → first card's detail → a not-done task's complete button
  // → the sheet; the control is the sheet's own save button (a plain onclick, not a form submit).
  // T14 sibling (2026-08-25): the community composer. wh_community_offline registered; the submit's
  // offline branch queues the post row, unshifts the card locally, closes the composer and toasts
  // 'Saved offline. Will post to the hive when you reconnect.' — queue-and-tell. The control is the
  // composer's own submit button; the post text stays NEUTRAL of the HELD vocabulary.
  'community-post': {
    page: 'community',
    writePattern: /rest\/v1\/community_posts/,
    async arm(p) {
      await p.waitForTimeout(2500);
      const opened = await p.evaluate(() => {
        // the canonical opener is the #fab-post FAB (aria-label 'Write a new post'); a text
        // 'New Post' button exists in some states - accept either.
        const fab = document.getElementById('fab-post');
        if (fab && fab.getClientRects().length) { fab.click(); return true; }
        const btn = [...document.querySelectorAll('button')].find((x) =>
          x.getClientRects().length && /new post/i.test(x.textContent || ''));
        if (!btn) return false;
        btn.click(); return true;
      });
      if (!opened) return { ok: false, why: 'neither #fab-post nor a New Post button rendered' };
      await p.waitForTimeout(1000);
      const ready = await p.evaluate(() => {
        const ta = document.getElementById('post-content');
        if (!ta || !ta.getClientRects().length) return false;
        ta.value = 'dead-zone composer probe: torque spec question for the mill line';
        ta.dispatchEvent(new Event('input', { bubbles: true }));
        return true;
      });
      if (!ready) return { ok: false, why: 'composer textarea (#post-content) not visible' };
      const control = await p.evaluate(() => {
        const btn = [...document.querySelectorAll('button')].find((x) =>
          x.getClientRects().length && /post to hive/i.test(x.textContent || ''));
        if (!btn) return null;
        btn.id = btn.id || 'wh-probe-post-btn';
        return '#' + btn.id;
      });
      if (!control) return { ok: false, why: 'no Post to Hive button rendered' };
      return { ok: true, control };
    },
    localEvidence: () => ({
      recordVisible: (document.body.innerText || '').includes('dead-zone composer probe'),
    }),
  },
  // T14 sibling (2026-08-25): the Add Part form. wh_inventory_offline registered (table
  // inventory_items); savePart's create branch checks `!navigator.onLine && window._whInvQueue`
  // -> enqueue insert + 'Saved offline, will sync when you reconnect.', with the item already in
  // the LOCAL cache so it renders immediately - queue-and-tell. whValidateCapture fails OPEN when
  // its contract fetch dies offline (returns ok:true), so the branch is reachable. Client-side
  // requireds: part number (must be UNIQUE vs the local cache - use a probe-only number), part
  // name, qty. No cleanup needed: zero server writes by assertion, and the local cache lives in
  // this ephemeral context's localStorage.
  'inventory-part': {
    page: 'inventory',
    writePattern: /rest\/v1\/inventory_items/,
    async arm(p) {
      await p.waitForTimeout(2500);
      const opened = await p.evaluate(() => {
        const btn = document.getElementById('btn-add-part');
        if (!btn || !btn.getClientRects().length) return false;
        btn.click(); return true;
      });
      if (!opened) return { ok: false, why: '#btn-add-part not rendered' };
      await p.waitForTimeout(800);
      const ready = await p.evaluate(() => {
        const modal = document.getElementById('part-modal');
        if (!modal || modal.style.display === 'none') return false;
        const set = (id, v) => { const el = document.getElementById(id); if (!el) return false;
          el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); return true; };
        return set('f-part-number', 'DZ-PROBE-6205')
            && set('f-part-name', 'dead-zone probe bearing')
            && set('f-qty', '3');
      });
      if (!ready) return { ok: false, why: 'part modal not open or required fields not fillable' };
      const has = await p.evaluate(() => !!document.getElementById('part-submit-btn'));
      return has ? { ok: true, control: '#part-submit-btn' }
                 : { ok: false, why: '#part-submit-btn not in the DOM' };
    },
    localEvidence: () => ({
      recordVisible: (document.body.innerText || '').includes('dead-zone probe bearing'),
    }),
  },
  // T14 sibling (2026-08-25): the day-planner schedule composer. wh_dayplanner_offline
  // (schedule_items, upsert keyed on row.id so an offline re-edit replaces the pending row);
  // syncItemToSupabase checks the offline branch BEFORE whValidateCapture (the pattern
  // inventory lacked until the same-day fix) and toasts 'Saved offline. Will sync when you
  // reconnect.' openAddModal prefills the date, so only the title is typed. The Save button
  // is anonymous (onclick="saveScheduleItem()") - locate by text inside the modal, mint an id.
  'dayplanner-item': {
    page: 'dayplanner',
    writePattern: /rest\/v1\/schedule_items/,
    async arm(p) {
      await p.waitForTimeout(2500);
      const opened = await p.evaluate(() => {
        if (typeof window.openAddModal !== 'function') return false;
        window.openAddModal();
        return true;
      });
      if (!opened) return { ok: false, why: 'openAddModal not defined' };
      await p.waitForTimeout(600);
      const ready = await p.evaluate(() => {
        const modal = document.getElementById('modal');
        if (!modal || !modal.classList.contains('open')) return false;
        const t = document.getElementById('m-title');
        if (!t) return false;
        t.value = 'dead-zone probe task: check the mill line guards';
        t.dispatchEvent(new Event('input', { bubbles: true }));
        return !!document.getElementById('m-date').value;
      });
      if (!ready) return { ok: false, why: 'schedule modal not open, or the date did not prefill' };
      const control = await p.evaluate(() => {
        const btn = [...document.querySelectorAll('#modal button')].find((x) =>
          x.getClientRects().length && /^save$/i.test((x.textContent || '').trim()));
        if (!btn) return null;
        btn.id = btn.id || 'wh-probe-dp-save';
        return '#' + btn.id;
      });
      if (!control) return { ok: false, why: 'no Save button rendered in the modal' };
      return { ok: true, control };
    },
    localEvidence: () => ({
      recordVisible: (document.body.innerText || '').includes('dead-zone probe task'),
    }),
  },
  // T14 sibling (2026-08-25): the skill-target save. wh_skillmatrix_offline (skill_profiles,
  // upsert keyed on worker_name so an offline re-save replaces the pending row, idempotent);
  // the offline branch is checked FIRST and toasts 'Saved offline. Will sync when you
  // reconnect.' The runner's supervisor persona has a profile (Steam Systems), so the target
  // grid renders (no onboarding). Arm bumps ONE stepper (+1, a real change) - selector scoped
  // to .step-btn because discipline CARDS also carry data-disc (the known duplicate-attr trap).
  // Local evidence: the branch re-enables the button and restores 'Save Targets' - the queue
  // growth is the load-bearing acceptance check; the row itself was already rendered pre-save.
  'skillmatrix-targets': {
    page: 'skillmatrix',
    writePattern: /rest\/v1\/skill_profiles/,
    async arm(p) {
      await p.waitForTimeout(2500);
      const bumped = await p.evaluate(() => {
        const grid = document.getElementById('target-grid');
        if (!grid || !grid.getClientRects().length) return false;
        const up = grid.querySelector('.step-btn[data-dir="1"]:not([disabled])');
        if (!up) return false;
        up.click(); return true;
      });
      if (!bumped) return { ok: false, why: 'target grid not rendered or no bumpable stepper' };
      await p.waitForTimeout(400);
      const has = await p.evaluate(() => {
        const b = document.getElementById('target-save-btn');
        return !!(b && b.getClientRects().length && !b.disabled);
      });
      return has ? { ok: true, control: '#target-save-btn' }
                 : { ok: false, why: '#target-save-btn not visible/enabled' };
    },
    localEvidence: () => ({
      recordVisible: (() => { const b = document.getElementById('target-save-btn');
        return !!(b && !b.disabled && /save targets/i.test(b.textContent || '')); })(),
    }),
  },
  // T14 sibling (2026-08-25): the daily progress log - the ONE field-capture write on
  // project-manager (every other write is an authority write and stays online-only by design,
  // per the page's own PJ17 comment). wh_projectmgr_offline (project_progress_logs, insert);
  // offline toast: 'Saved on this device. Your report will be filed when you reconnect.' -
  // the HELD vocabulary was widened for that phrasing. Choreography: first .pcard ->
  // openDetail -> '+ Log progress' -> #modal-progress (date/pct/hours all PREFILL on open) ->
  // FORM:#form-progress submit. The modal closes on the queued path (closeModal before the
  // toast), so localEvidence is the modal being GONE plus the detail still open.
  'projectmanager-progress': {
    page: 'project-manager',
    writePattern: /rest\/v1\/project_progress_logs/,
    async arm(p) {
      await p.waitForTimeout(2500);
      const opened = await p.evaluate(() => {
        const card = document.querySelector('.pcard');
        if (!card || !card.getClientRects().length) return false;
        card.click(); return true;
      });
      if (!opened) return { ok: false, why: 'no .pcard rendered (no projects in this hive?)' };
      await p.waitForTimeout(2500);
      // The '+ Log progress' button lives in #pane-progress, hidden until its tab is active.
      // The tab's LABEL is 'Daily log' (not 'Progress') - anchor on data-pane, the stable key.
      const tabbed = await p.evaluate(() => {
        const tab = document.querySelector('#detail-tabs button[data-pane="progress"]');
        if (!tab) return false;
        tab.click(); return true;
      });
      if (!tabbed) return { ok: false, why: 'no data-pane="progress" tab in #detail-tabs' };
      await p.waitForTimeout(1200);
      const modal = await p.evaluate(() => {
        const btn = [...document.querySelectorAll('#pane-progress button')].find((x) =>
          x.getClientRects().length && /log progress/i.test(x.textContent || ''));
        if (!btn) return false;
        btn.click(); return true;
      });
      if (!modal) return { ok: false, why: 'no "+ Log progress" button in the detail' };
      await p.waitForTimeout(600);
      const ready = await p.evaluate(() => {
        const m = document.getElementById('modal-progress');
        if (!m || !m.getClientRects().length) return false;
        const notes = document.getElementById('p-notes');
        if (notes) { notes.value = 'dead-zone shift report probe'; notes.dispatchEvent(new Event('input', { bubbles: true })); }
        return !!(document.getElementById('p-date').value && document.getElementById('p-pct').value !== '');
      });
      if (!ready) return { ok: false, why: 'progress modal not open or prefills missing' };
      return { ok: true, control: 'FORM:#form-progress' };
    },
    localEvidence: () => ({
      recordVisible: (() => {
        const m = document.getElementById('modal-progress');
        const modalClosed = !m || !m.classList.contains('open');
        return modalClosed && !!document.getElementById('form-progress');
      })(),
    }),
  },
  // T14 sibling (2026-08-25): the FMEA failure-mode add - asset-hub's one field-capture write.
  // wh_assethub_offline (rcm_fmea_modes, insert); offline branch first, toast 'Saved offline.
  // This FMEA mode will sync and appear when you reconnect.' (HELD matches). Three-gate reach:
  // .asset-card -> openDetail, then #asset-view-toggle reveals #reliability-card
  // (display:none until toggled - the known two-gate detail lesson), then #fmea-add-btn ->
  // #fmea-modal. Required: #fmea-function + #fmea-failure-mode. The modal closes on the queued
  // path, so localEvidence = modal no longer .open.
  'assethub-fmea': {
    page: 'asset-hub',
    writePattern: /rest\/v1\/rcm_fmea_modes/,
    async arm(p) {
      await p.waitForTimeout(2500);
      const opened = await p.evaluate(() => {
        const card = document.querySelector('.asset-card');
        if (!card || !card.getClientRects().length) return false;
        card.click(); return true;
      });
      if (!opened) return { ok: false, why: 'no .asset-card rendered' };
      await p.waitForTimeout(2500);
      const revealed = await p.evaluate(() => {
        const t = document.getElementById('asset-view-toggle');
        if (!t || !t.getClientRects().length) return false;
        if (t.getAttribute('aria-expanded') !== 'true') t.click();
        return true;
      });
      if (!revealed) return { ok: false, why: '#asset-view-toggle not rendered in the detail' };
      await p.waitForTimeout(800);
      const modal = await p.evaluate(() => {
        const b = document.getElementById('fmea-add-btn');
        if (!b || !b.getClientRects().length) return false;
        b.click(); return true;
      });
      if (!modal) return { ok: false, why: '#fmea-add-btn not visible after the workbench toggle' };
      await p.waitForTimeout(600);
      const ready = await p.evaluate(() => {
        const m = document.getElementById('fmea-modal');
        if (!m || !m.classList.contains('open')) return false;
        const set = (id, v) => { const el = document.getElementById(id); if (!el) return false;
          el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); return true; };
        return set('fmea-function', 'dead-zone probe: maintain guard interlock circuit')
            && set('fmea-failure-mode', 'interlock relay contacts welded');
      });
      if (!ready) return { ok: false, why: 'FMEA modal not open or required fields not fillable' };
      const has = await p.evaluate(() => !!document.getElementById('fmea-save'));
      return has ? { ok: true, control: '#fmea-save' }
                 : { ok: false, why: '#fmea-save not in the DOM' };
    },
    localEvidence: () => ({
      recordVisible: (() => { const m = document.getElementById('fmea-modal');
        return !!m && !m.classList.contains('open'); })(),
    }),
  },
  // ★FLAKY (2026-08-25, 2 PASS / 1 FAIL): the failing run showed queue 0->0 with no held line -
  // the press never reached the offline branch that run - while localEvidence read true off a
  // PRE-EXISTING done row (weak evidence: any already-done task satisfies it). HARDENED
  // same-day: localEvidence is now the SHEET-CLOSED discriminator - submitCompletion's queued
  // path runs closeSheet(), while a swallowed click (e.g. a re-render replacing the button
  // between arm and press, killing its listener) leaves #completion-sheet.open standing - so
  // the vacuous pass is impossible: a dead press reads queue 0->0 AND sheet-open = honest FAIL.
  'pm-completion': {
    page: 'pm-scheduler',
    writePattern: /rest\/v1\/pm_completions/,
    async arm(p) {
      await p.waitForTimeout(2500);
      const mine = await p.evaluate(() => {
        const chip = document.getElementById('chip-mine');
        if (chip && !chip.hidden) { chip.click(); return true; }
        return false;
      });
      await p.waitForTimeout(1200);
      const opened = await p.evaluate(() => {
        const card = document.querySelector('.asset-card');
        if (!card) return false;
        card.click(); return true;
      });
      if (!opened) return { ok: false, why: 'no .asset-card rendered' + (mine ? ' under the Mine filter' : '') };
      await p.waitForTimeout(1500);
      const sheet = await p.evaluate(() => {
        const btn = document.querySelector('.complete-btn:not(.done)');
        if (!btn) return false;
        btn.click(); return true;
      });
      if (!sheet) return { ok: false, why: 'no not-done .complete-btn in the detail' };
      await p.waitForTimeout(1000);
      const ready = await p.evaluate(() => {
        const f = document.getElementById('sheet-findings');
        const save = document.getElementById('sheet-save-btn');
        if (!f || !save || !save.getClientRects().length) return false;
        // the probe text must NOT satisfy the HELD vocabulary itself (queued/held/offline are all
        // oracle words - a baseline that contains the answer); neutral words only.
        f.value = 'dead-zone completion probe';
        f.dispatchEvent(new Event('input', { bubbles: true }));
        // skip the logbook mirror: offline it is deliberately skipped anyway, and the oracle
        // judges the pm_completions hold, not the mirror.
        const tgl = document.getElementById('sheet-log-toggle');
        if (tgl) tgl.checked = false;
        return true;
      });
      if (!ready) return { ok: false, why: 'completion sheet did not open with its fields' };
      return { ok: true, control: '#sheet-save-btn' };
    },
    localEvidence: () => ({
      recordVisible: (() => { const s = document.getElementById('completion-sheet');
        return !!s && !s.classList.contains('open'); })(),
    }),
  },
  'logbook-entry': {
    page: 'logbook',
    writePattern: /rest\/v1\/logbook/,
    // The composer is an inline form (#log-form), not a modal - the bank's anatomy calls V2 the
    // "capture modal", which is worth correcting.
    // ★AND THE SAVE IS A FORM SUBMIT, NOT A BUTTON CLICK. #save-entry-btn is type="submit" and measures
    // ZERO WIDTH in the default layout; calling .click() on it does NOT run the handler - measured, with
    // the form reporting checkValidity()===true and no :invalid fields, the label never changed from
    // "Save Entry" to "Saving…". So every earlier "0 writes offline" reading on this page was a submit
    // that never happened, not a queue and not a drop. Submit the FORM (requestSubmit) instead.
    async arm(p) {
      // The asset field is REQUIRED and cannot be written directly. #f-machine is a hidden input, but
      // selectAsset() also resolves _pendingAssetRefId to a uuid via resolveAssetNodeId - so setting the
      // input alone leaves the page's own state unset and the save still refuses with
      // "MACHINE / EQUIPMENT required". Writing a scraped [data-asset-id] made this worse, not better: it
      // picked up an id from an unrelated element. (PB-001 turned out to be a REAL asset - the picker's
      // own first row - so the id was not the problem; the page's internal selection state was.) Go through the picker
      // the way a person does - open it, then click one of its real button[data-asset-id] rows.
      // Try picker rows until one leaves the TASKLIST ACK SECTION HIDDEN. The save gate is
      // `!tasklistSection.classList.contains('hidden') && !tasklistCheck.checked`, so it only applies to
      // assets that HAVE a work tasklist. Choosing an asset without one avoids the gate the way a person
      // would, instead of forcing a hidden checkbox the page manages itself (ticking it programmatically
      // did not take - the box is class="hidden" behind a styled label with its own handler).
      let picked = null;
      for (let attempt = 0; attempt < 6 && !picked; attempt++) {
        await p.evaluate(() => document.getElementById('asset-picker-btn')?.click());
        await p.waitForTimeout(1000);
        const id = await p.evaluate((n) => {
          const rows = [...document.querySelectorAll('#asset-picker-list button[data-asset-id]')];
          const btn = rows[n];
          if (!btn) return null;
          const v = btn.dataset.assetId;
          btn.click();
          return v;
        }, attempt);
        if (!id) break;
        await p.waitForTimeout(1200);           // selectAsset awaits resolveAssetNodeId
        const gated = await p.evaluate(() => {
          const sec = document.getElementById('tasklist-ack-section');
          return !!(sec && !sec.classList.contains('hidden'));
        });
        if (!gated) picked = id;
      }
      if (!picked) return { ok: false, why: 'asset picker opened but rendered no button[data-asset-id] to choose' };
      await p.waitForTimeout(1200);        // selectAsset awaits resolveAssetNodeId
      const ok = await p.evaluate(() => {
        const set = (id, v) => {
          const e = document.getElementById(id);
          if (!e) return false;
          e.value = v;
          e.dispatchEvent(new Event('input', { bubbles: true }));
          return true;
        };
        // Several SELECTS are required too - the save refuses with "DISCIPLINE / CATEGORY required"
        // and "SYMPTOM / WHAT WAS WRONG? required" until they are chosen. Take the first REAL option
        // of each (index 0 is the "Select ..." placeholder), so the form is completed the way a person
        // completes it rather than by inventing values.
        for (const sel of document.querySelectorAll('#log-form select')) {
          if (sel.value) continue;
          let opts = [...sel.options].filter((o) => o.value && !/^select/i.test(o.textContent || ''));
          // ★AVOID "Breakdown" for the maintenance type. The submit handler's LAST validation is
          // "Please select what was the impact (required for Breakdown entries)", gated on a hidden
          // #f-consequence field the form fills through its own flow - so picking the first option
          // (which is Breakdown) made the submit refuse for a reason no visible field showed, and the
          // toast that says so had already faded by the time the probe read the page. Choosing a
          // non-Breakdown type keeps the form completable without inventing a consequence value.
          if (sel.id === 'f-maint-type') {
            const nonBreakdown = opts.filter((o) => !/breakdown/i.test(o.textContent + o.value));
            if (nonBreakdown.length) opts = nonBreakdown;
          }
          if (opts[0]) { sel.value = opts[0].value; sel.dispatchEvent(new Event('change', { bubbles: true })); }
        }
        // ★AND LOG IT AS **OPEN**, NOT CLOSED. The submit's last gate is "Please acknowledge you have
        // read the work tasklist before closing" - a CLOSED entry requires a tasklist acknowledgement,
        // which is its own flow. An open entry is also the truthful shape for what this probe is doing:
        // recording an observation, not signing off a completed job. Found by POLLING for the toast every
        // 300ms after submit; it fades in 2.8s, so every earlier single read at +5s missed it entirely
        // and the submit looked like it had silently done nothing.
        const openRadio = document.getElementById('st-open');
        if (openRadio) { openRadio.checked = true; openRadio.dispatchEvent(new Event('change', { bubbles: true })); }
        // The tasklist acknowledgement is a HIDDEN checkbox behind a styled label (#tasklist-ack-check,
        // class="hidden", with #tasklist-ack-box as the visible tick). It gates the save regardless of
        // the Open/Closed radio, so tick it the way the label does. Its own error element
        // (#tasklist-ack-error) is the only place the refusal is written - and it is aria-live, which is
        // why polling the status/alert roles found it while a late body read did not.
        // Click the LABEL only. Setting .checked = true AND clicking the label toggles it straight back
        // off - measured, the probe reported ack:false while believing it had ticked the box.
        const ack = document.getElementById('tasklist-ack-check');
        if (ack && !ack.checked) document.getElementById('tasklist-ack-label')?.click();
        if (ack && !ack.checked) { ack.checked = true; ack.dispatchEvent(new Event('change', { bubbles: true })); }
        return set('f-problem', 'Offline queue probe - bearing noise on pump 3, 2pm round.')
            && set('f-action', 'Logged for the next PM; no parts changed.')
            && !!(document.getElementById('f-machine') || {}).value;
      });
      if (!ok) return { ok: false, why: 'composer fields not fillable, or #f-machine still empty after the pick' };
      const has = await p.evaluate(() => !!document.getElementById('log-form'));
      return has ? { ok: true, control: 'FORM:#log-form', note: 'asset ' + picked + ' chosen via the picker' }
                 : { ok: false, why: '#log-form not in the DOM' };
    },
    // What should appear locally the instant it is queued.
    localEvidence: () => ({
      syncBadge: (() => { const s = document.getElementById('sync-badge');
                          return !!(s && !s.classList.contains('hidden')); })(),
    }),
  },
};

const args = process.argv.slice(2);
if (args.includes('--list')) { console.log('cases:', Object.keys(CASES).join(', ')); process.exit(0); }
const NAME = (() => { const i = args.indexOf('--case'); return i >= 0 ? args[i + 1] : null; })();
const c = CASES[NAME];
if (!c) { console.log('pass --case <' + Object.keys(CASES).join('|') + '>'); process.exit(2); }

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
await assertSignedIn(signIn(ctx, 'supervisor'));
const p = await ctx.newPage();

// POSITIVE ACCEPTANCE EVIDENCE: count the queue's own store before and after. A blocked submit leaves
// this unchanged, which is exactly the case the first version of this prover could not see.
const countPending = () => p.evaluate(async () => {
  const names = (indexedDB.databases ? await indexedDB.databases() : []).map((d) => d.name).filter(Boolean);
  let total = 0;
  const per = {};
  for (const name of names.filter((n) => /offline/i.test(n))) {
    try {
      const db = await new Promise((res, rej) => {
        const r = indexedDB.open(name); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error);
      });
      for (const store of [...db.objectStoreNames]) {
        const n = await new Promise((res) => {
          const t = db.transaction(store, 'readonly').objectStore(store).count();
          t.onsuccess = () => res(t.result); t.onerror = () => res(0);
        });
        per[name + '/' + store] = n; total += n;
      }
      db.close();
    } catch (_) { /* a store we cannot open contributes nothing */ }
  }
  return { total, per };
});


let t0 = 0;
const hits = [];
await ctx.route('**/*', async (route) => {
  const r = route.request();
  if (c.writePattern.test(r.url()) && r.method() !== 'GET') {
    hits.push({ ms: t0 ? Date.now() - t0 : -1, method: r.method() });
    return route.abort('internetdisconnected');   // it must never have reached the network
  }
  return route.continue();
});
const errs = [];
p.on('pageerror', (e) => errs.push(String(e.message).slice(0, 120)));

// ★A TOAST IS GONE BEFORE THE READ (the sibling prove_retry_path's own recorded lesson, carried
// here 2026-08-25 after community's ~3.5s 'Saved offline. Will post…' toast expired inside the
// 5s settle and a truthfully-queued write read as FAIL-no-held-line). Collect every announcement
// from load onward and union it into the held/refusal reads.
await p.addInitScript(() => {
  window.__whSeen = [];
  const grab = (n) => {
    try {
      const t = (n.textContent || '').trim().replace(/\s+/g, ' ');
      if (t && t.length < 400) window.__whSeen.push(t);
    } catch { /* best-effort */ }
  };
  addEventListener('DOMContentLoaded', () => {
    new MutationObserver((ms) => ms.forEach((m) => {
      m.addedNodes.forEach(grab);
      if (m.type === 'characterData') grab(m.target.parentElement || m.target);
    })).observe(document.body, { childList: true, subtree: true, characterData: true });
  });
});

await p.goto(`${ORIGIN}/${c.page}.html`, { waitUntil: 'domcontentloaded', timeout: 45000 });
await p.waitForTimeout(9000);

console.log(`--- arming on ${c.page} (ONLINE) ---`);
const armed = await c.arm(p);
console.log('   ', JSON.stringify(armed));
if (!armed.ok) { console.log('   cannot grade: control unreachable'); await browser.close(); process.exit(0); }

await p.evaluate(() => Object.defineProperty(window.navigator, 'onLine',
  { get: () => false, configurable: true }));
await ctx.setOffline(true);
console.log(`--- offline: navigator.onLine=${await p.evaluate(() => navigator.onLine)} + network cut ---`);

const pendingBefore = await countPending();
const bootTraffic = hits.length;          // everything so far is page boot, NOT the action
hits.length = 0;
t0 = Date.now();
// A control named FORM:<sel> is SUBMITTED, not clicked - see the logbook case comment for why.
await p.evaluate((sel) => {
  if (sel.startsWith('FORM:')) {
    const f = document.querySelector(sel.slice(5));
    if (!f) return;
    if (typeof f.requestSubmit === 'function') f.requestSubmit();
    else f.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    return;
  }
  document.querySelector(sel)?.click();
}, armed.control);
await p.waitForTimeout(5000);
const pendingAfter = await countPending();

const seen = await p.evaluate((extraFn) => {
  const lines = (document.body.innerText || '').split(String.fromCharCode(10))
    .map((s) => s.trim()).filter(Boolean);
  // eslint-disable-next-line no-new-func
  const extra = extraFn ? new Function('return (' + extraFn + ')()')() : {};
  // union the live text with every announcement seen since load (a dismissed toast still counts)
  const announced = [...new Set(window.__whSeen || [])];
  return { lines: lines.slice(-60), announced: announced.slice(-40), extra };
}, c.localEvidence ? c.localEvidence.toString() : null);

const allLines = [...seen.lines, ...(seen.announced || [])];
const heldLine = allLines.find((l) => HELD.test(l)) || '';
const refusalLine = allLines.find((l) => REFUSAL.test(l)) || '';

console.log(`   boot traffic before the press : ${bootTraffic} (excluded - it is not the action)`);
console.log(`   server writes after the press : ${hits.length} (must be 0)`,
            hits.length ? JSON.stringify(hits.map((h) => h.ms)) : '');
console.log(`   told it was HELD              : ${!!heldLine}  ${JSON.stringify(heldLine.slice(0, 90))}`);
console.log(`   wrongly claimed a REFUSAL     : ${!!refusalLine}  ${JSON.stringify(refusalLine.slice(0, 70))}`);
console.log(`   queue store before / after    : ${pendingBefore.total} -> ${pendingAfter.total}  ${JSON.stringify(pendingAfter.per)}`);
console.log(`   local evidence                : ${JSON.stringify(seen.extra)}`);
console.log(`   pageerrors                    : ${errs.length ? errs : 'none'}`);

// ACCEPTED means the queue grew, or the page shows the record now. Without one of those, "zero writes"
// is indistinguishable from a submit that never happened.
const accepted = pendingAfter.total > pendingBefore.total || seen.extra.recordVisible === true;
const pass = hits.length === 0 && accepted && !!heldLine && !refusalLine;
console.log(`   write ACCEPTED locally        : ${accepted}` +
            (accepted ? '' : '  <-- zero writes here proves nothing; the submit may never have run'));
console.log(`\n  ${pass ? 'PASS' : 'FAIL'} — ${c.page} / ${NAME}: held offline, said so, claimed no refusal = ${pass}`);
console.log('  NOT asserted here: that it drains exactly once on reconnect - that needs a reconnect and a');
console.log('  settle window, and a drain probe writes real rows into a shared DB. Next slice, not half-built.');
await browser.close();
process.exit(pass ? 0 : 1);
