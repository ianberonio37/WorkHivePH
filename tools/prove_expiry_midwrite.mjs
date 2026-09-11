// prove_expiry_midwrite — T38 "Session expiry mid-WRITE on every committing surface" (2026-09-07).
//
// The worst moment for a session to end is between typing and saving. The person has done the work;
// the only question is whether the platform tells them what happened and gives it back, or drops it
// and shows them a sign-in screen with their words gone.
//
//   X1 told        the failed save SAYS the session expired - not "something went wrong", and not a
//                  silent no-op that leaves the button looking pressed
//   X2 kept        what they typed is still on screen afterwards. A save that fails must never be a
//                  save that also clears the form.
//   X3 recoverable there is a way back in from where they are - a sign-in control, a link, a modal -
//                  rather than a dead end they can only escape by reloading and losing the work
//
// ★THE EXPIRY IS REAL, NOT SIMULATED. The stored session is destroyed the way an expiry destroys it
// (the auth token is removed from storage and every subsequent auth call answers 401), so the page
// meets exactly what it would meet at 3am on a token that timed out.
//
//   node tools/prove_expiry_midwrite.mjs
//   node tools/prove_expiry_midwrite.mjs --page logbook.html
import { chromium } from 'playwright';
import { SEEDER, signIn, PAGE_QUERY, VIS_JS, SETTLE_MS } from './prover_harness.mjs';

const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const LIST = (() => { const i = process.argv.indexOf('--pages'); return i >= 0 ? process.argv[i + 1].split(',') : null; })();

// the surfaces a person commits work on
const ROSTER = ['logbook.html', 'inventory.html', 'community.html', 'voice-journal.html', 'resume.html',
                'asset-hub.html', 'dayplanner.html', 'pm-scheduler.html', 'project-manager.html',
                'marketplace-seller.html', 'skillmatrix.html', 'report-sender.html'];

const SAID = /session|signed out|sign in again|log in again|expired|no longer signed/i;
const BARE = /^(something went wrong|an error occurred|error|failed|could not save)\.?$/i;

const b = await chromium.launch();
let bad = 0, n = 0, skipped = [];
for (const file of (ONLY ? [ONLY] : (LIST || ROSTER))) {
  const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
  await signIn(ctx);
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/${file}${PAGE_QUERY[file] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(SETTLE_MS);

  // ★THE COMMITTING FIELD IS BEHIND THE "ADD" BUTTON. The first run found nothing to type into on
  // logbook, inventory or community - the three surfaces people commit work on most - because the form
  // lives in a modal that opens on demand. A sweep that only sees the page at rest sweeps nothing.
  await p.evaluate(() => {
    const vis = (e) => e.checkVisibility && e.checkVisibility({ opacityProperty: true, visibilityProperty: true });
    const el = [...document.querySelectorAll('button, [role="button"], a')]
      .find((e) => vis(e) && !e.disabled && /^(\+|add|new|log |create|post|write|record|start)\b/i.test((e.innerText || '').trim()));
    if (el) el.click();
  }).catch(() => {});
  await p.waitForTimeout(3000);

  const MARK = 'wh-expiry-probe-' + Math.abs([...file].reduce((a, c) => a + c.charCodeAt(0), 0));
  // type into whatever this surface commits with
  const typed = await p.evaluate((mark) => {
    const vis = (e) => e.checkVisibility && e.checkVisibility({ opacityProperty: true, visibilityProperty: true });
    const el = [...document.querySelectorAll('textarea, input[type="text"]')]
      .find((e) => vis(e) && !e.readOnly && !e.disabled && !/search|filter|query/i.test(e.id + ' ' + e.name + ' ' + e.className));
    if (!el) return null;
    const scope = el.closest('[id^="wh-modal-ov-"], dialog, [role="dialog"], form') || document;
    let first = null;
    for (const f of scope.querySelectorAll('input, textarea, select')) {
      if (!vis(f) || f.readOnly || f.disabled || f.type === 'hidden') continue;
      if (/search|filter|query/i.test(f.id + ' ' + f.name + ' ' + f.className)) continue;
      if (f.tagName === 'SELECT') {
        if (!f.value && f.options.length > 1) { f.value = f.options[1].value; f.dispatchEvent(new Event('change', { bubbles: true })); }
        continue;
      }
      if (f.type === 'checkbox' || f.type === 'radio') continue;
      const val = f.type === 'number' ? '5' : (f === el ? mark : (f.value || mark));
      f.focus(); f.value = val;
      f.dispatchEvent(new Event('input', { bubbles: true }));
      f.dispatchEvent(new Event('change', { bubbles: true }));
      if (!first) first = f.id || f.name || f.tagName;
    }
    return first || el.id || el.name || el.tagName;
  }, MARK).catch(() => null);
  if (!typed) { skipped.push(file); await ctx.close(); continue; }
  n++;

  // ── expire the session for real, then make every auth call answer 401 ──────────────────────────
  await p.evaluate(() => {
    for (const k of Object.keys(localStorage)) if (/auth|token|supabase/i.test(k)) localStorage.removeItem(k);
    try { if (window._whSupabaseClient) window._whSupabaseClient.auth.signOut({ scope: 'local' }); } catch (e) { void e; }
  }).catch(() => {});
  await p.route('**/auth/v1/**', (r) => r.fulfill({ status: 401, contentType: 'application/json', body: '{"message":"JWT expired"}' })).catch(() => {});
  await p.route('**/rest/v1/**', (r) => (r.request().method() === 'GET'
    ? r.continue()
    : r.fulfill({ status: 401, contentType: 'application/json', body: '{"message":"JWT expired","code":"PGRST301"}' }))).catch(() => {});

  // press the surface's own save
  const saved = await p.evaluate(() => {
    const vis = (e) => e.checkVisibility && e.checkVisibility({ opacityProperty: true, visibilityProperty: true });
    // ★THE OPENER AND THE SAVE CAN SHARE A VERB. "Add Part" opens inventory's composer and "Save"
    // commits it, and a matcher that accepts /^add\b/ presses the OPENER - which resets the form and
    // looks exactly like the page throwing the person's work away. Search inside the open composer,
    // and never re-press the control that opened it.
    const scope = [...document.querySelectorAll('[id^="wh-modal-ov-"], dialog[open], [role="dialog"], form')]
      .filter(vis).pop() || document;
    const pick = (root, rx) => [...root.querySelectorAll('button, [role="button"], input[type="submit"]')]
      .find((e) => vis(e) && !e.disabled && !e.hasAttribute('data-wh-opened') && rx.test((e.innerText || e.value || '').trim()));
    const el = pick(scope, /^(save|submit|post|send|publish|record|confirm|done)\b/i)
            || pick(document, /^(save|submit|post|send|publish|record|confirm)\b/i);
    if (!el) return false;
    const label = (el.innerText || el.value || '').trim().slice(0, 28);
    el.click(); return label || true;
  }).catch(() => false);
  await p.waitForTimeout(7000);

  const after = await p.evaluate((args) => {
    const mark = args[0];
    const vis = (0, eval)(args[1]);
    const sel = '[role="alert"], [role="status"], .wh-list-error, #wh-connection-notice, [id$="-notice"], .toast, #toast';
    const notices = [...document.querySelectorAll(sel)].filter(vis).map((e) => (e.innerText || '').replace(/\s+/g, ' ').trim()).filter(Boolean);
    const kept = [...document.querySelectorAll('textarea, input')].some((e) => (e.value || '').includes(mark))
      || (document.body.innerText || '').includes(mark);
    const wayBack = [...document.querySelectorAll('button, a, [role="button"]')]
      .some((e) => vis(e) && /sign in|log in|continue|reconnect/i.test(e.innerText || ''));
    const modalOpen = [...document.querySelectorAll('[id^="wh-modal-ov-"], dialog[open], [role="dialog"]')]
      .some((e) => vis(e));
    const fieldStill = !!document.querySelector('#f-part-number, textarea, input[type="text"]');
    return { notices, kept, wayBack, modalOpen, fieldStill };
  }, [MARK, VIS_JS]).catch(() => ({ notices: [], kept: false, wayBack: false }));

  const issues = [];
  const text = after.notices.join(' | ');
  if (!saved) issues.push('X1 no save control was reachable, so the expiry could not be met mid-write');
  else {
    if (!text) issues.push('X1 the save failed silently - nothing on screen said the session had ended');
    else if (!SAID.test(text) && after.notices.every((s) => BARE.test(s.trim()))) {
      issues.push(`X1 the person is told only "${after.notices[0].slice(0, 46)}" when the truth is that their session expired`);
    }
    if (!after.kept) issues.push('X2 what they typed is GONE after the failed save - the work was lost with the session');
    if (!after.wayBack) issues.push('X3 no way back in from here - no sign-in control, so the only escape is a reload that loses the work');
  }
  if (issues.length) bad++;
  console.log(`  ${issues.length ? 'BAD' : 'ok '} ${file.padEnd(26)} typed into ${String(typed).slice(0, 18)} · ${after.notices.length} notice(s) · draft ${after.kept ? 'kept' : 'LOST'} · way back ${after.wayBack ? 'yes' : 'no'}`);
  for (const s of issues.slice(0, ONLY ? 8 : 3)) console.log(`        ${s.slice(0, 158)}`);
  if (issues.length) console.log(`        pressed "${saved}" · modal still open: ${after.modalOpen} · a field still on screen: ${after.fieldStill}${text ? ` · said: "${text.slice(0, 90)}"` : ' · said NOTHING'}`);
  await ctx.close();
}
await b.close();
if (skipped.length) console.log(`  note ${skipped.length} surface(s) had no committing field to type into: ${skipped.slice(0, 6).join(', ')}`);
console.log(`${bad ? 'FAIL' : 'PASS'} expiry-midwrite - ${n - bad}/${n} committing surfaces meet a session expiry between typing and saving by SAYING so, KEEPING the work, and offering a way back`);
process.exitCode = bad ? 1 : 0;
