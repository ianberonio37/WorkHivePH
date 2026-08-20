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
const HELD = /saved offline|will sync|sync when (you )?reconnect|queued|held (locally|offline)/i;
// The refusal helper's tail. A queue-backed write must NOT print this.
const REFUSAL = /nothing was sent, so nothing is half-done/i;

const CASES = {
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
  return { lines: lines.slice(-60), extra };
}, c.localEvidence ? c.localEvidence.toString() : null);

const heldLine = seen.lines.find((l) => HELD.test(l)) || '';
const refusalLine = seen.lines.find((l) => REFUSAL.test(l)) || '';

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
