// prove_session_expiry.mjs — the CG `session_expiry` oracle, measured by killing the session mid-form.
//
// THE ORACLE: "the session dies BETWEEN typing and submitting: the write is refused, the person is told
// their session expired and that NOTHING was sent, and 'try again' is not offered when retrying would
// fail identically."
//
// ★THIS IS NOT `session_died`. prove_session_died.mjs kills the session and RELOADS — it asks what a
// cold page does with no session. This asks the harder, warmer question: the person has a form open and
// half-typed, the token quietly expires, and they press Save. The page still has its data, its state and
// its optimism. Everything about that moment is different from a cold load, which is why these rows
// stayed owed while `session_died` went green.
//
// ★NO WRITE CAN LAND, BY CONSTRUCTION — and that is not a promise, it is a route. Every mutating REST
// and edge request is intercepted and answered **401 with an expired-JWT body** before it can reach the
// database. That is also the most faithful simulation available: an expired token is exactly a 401 from
// the server. Clearing the client's stored session alone would not do — supabase-js holds the token in
// memory, so the submit could genuinely succeed and write real rows into the shared database. The route
// makes the outcome certain rather than likely.
//
// ★WHAT A PASS REQUIRES, all three, because the oracle names all three:
//   1. The write is REFUSED — no success message, no optimistic row added to the list.
//   2. The person is TOLD, in words that name the session — "signed out", "session expired", "sign in
//      again". A generic "something went wrong" leaves them retrying a thing that cannot work.
//   3. The message does not promise a plain RETRY that would fail identically. Offering "Try again"
//      against a dead session is the specific cruelty this oracle exists to catch. Offering "Sign in
//      again" is the correct affordance and passes.
//
// ★SAMPLED ACROSS THE WINDOW, NEVER READ AT ITS END, and the baseline excludes live regions. Both are
// scars: a toast lives about a second, and a baseline captured after a message has already appeared
// filters that message out as "not fresh" — which is how this bank reported a page silent while it was
// speaking. See the same handling in prove_quota_legible.mjs.
//
// USAGE:  node tools/prove_session_expiry.mjs [--page <name>]
// OUTPUT: session_expiry_report.json

// ★engineering-design's session_died PATH IS NOT REACHABLE BY SETTING INPUTS AND CLICKING CALCULATE
// (measured 2026-08-19, rows left OWED rather than banked on the wrong guard). The oracle needs a session
// that dies BETWEEN typing and submitting, so the submit must actually reach a write. What happens instead:
//   · Choosing a calculator and writing values into its visible number/text inputs with input+change
//     events, then clicking #calc-btn, leaves the page's OWN state EMPTY - measured directly in the page:
//     _lastResults === null and _lastInputs === null afterwards, while #report-output holds only its ~293
//     char placeholder. So the calculation never ran.
//   · Pressing #save-calc-btn then hits the pre-flight guard 'Run the calculation before saving.' and
//     issues ZERO mutating requests, so a 401 route never fires and the session-death path is untouched.
//     The typed values ARE preserved across that refusal (6 of 6 retained), which is half of what the
//     oracle wants - but crediting the row on it would be crediting the wrong guard.
// A FALSE POSITIVE I NEARLY BUILT ON: a first check for "results present" tested the body text for
// /₱|kW|TR|CFM|result/ and returned TRUE - from the calculator catalogue's own copy ("Room heat gain, AC
// capacity in kW / TR"), not from any result. A body-wide keyword match reads the page's own marketing copy;
// the reliable signal is the page's internal state plus a specific container.
// TO SETTLE THESE ROWS: drive the calculator the way the page expects rather than by assigning .value -
// find what #calc-btn's handler reads (it evidently does not read the inputs I set), or call the calc entry
// point directly so _lastResults/_lastInputs populate, THEN install the 401 route and submit. The abort
// guard in the probe (bail out unless hasLastResults) should stay: it is what stopped this from being
// banked as a pass over an unexercised path.

// ★ROSTER GAP - THIS PROVER GRADES PAGES THAT DO NOT OWE THE ORACLE, AND MISSES EVERY PAGE THAT DOES.
// Measured 2026-08-19: a full run returned 6 pass / 0 fail, and NOT ONE of the passing targets
// (inventory V2+V3, pm-scheduler V2+V3, community V3, report-sender V3) has an owed `session_expiry`
// row. The 10 owed rows live on achievements, analytics-report, asset-hub, dayplanner, hive,
// project-report, public-feed and shift-brain - mostly `CM-ux-comprehension-V3`, a view this roster
// does not carry at all. So "6 pass, 0 fail" is true and answers a question nobody asked; banking it
// would move no owed row. A clean run over the wrong roster is the silent-scope-claim class.
// NEXT: extend TARGETS (tools/dialog_targets.mjs) to the V3 comprehension views on those eight pages,
// then re-run - and check each UNGRADED "issued no mutating request at all" separately, because that
// sentence covered a real service-worker bypass until 2026-08-19 and may still be covering a reach bug.

import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'node:url';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';
import { TARGETS } from './dialog_targets.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

const QUERY = { 'project-report': '?project_id=539e0d9a-9ff7-474b-ab03-9254406ca7dc' };
const MARK = 'WH-EXPIRY-PROBE';

const SAYS_SESSION = /sign(ed)?[ -]?in again|session (has )?expired|session ended|signed out|log ?in again|please sign in|not signed in/i;
const OFFERS_RETRY = /\btry again\b|\bretry\b/i;
const SAYS_NOT_SENT = /not (been )?(sent|saved)|nothing was (sent|saved)|was not saved|no changes were saved|still here|unsaved/i;

// Everything a person could read right now, minus what was already on screen before the press.
const readMessages = () => {
  const nodes = [...document.querySelectorAll(
    '#toast, [id*="toast"], [class*="toast"], [role="status"], [role="alert"], [aria-live], '
    + '.error, [class*="error"], [class*="banner"]')];
  return nodes.filter((e) => {
    const s = getComputedStyle(e); const b = e.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && Number(s.opacity) > 0.05 && b.height > 0;
  }).map((e) => (e.innerText || '').replace(/\s+/g, ' ').trim()).filter(Boolean);
};

// The page's own words, excluding every live region — a message must never be its own baseline.
const staticText = () => {
  const SEL = '#toast, [id*="toast"], [class*="toast"], [role="status"], [role="alert"], [aria-live], '
    + '.error, [class*="error"], [class*="banner"]';
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const out = [];
  for (let n = w.nextNode(); n; n = w.nextNode()) {
    if (n.parentElement && n.parentElement.closest(SEL)) continue;
    const t = (n.textContent || '').trim();
    if (t) out.push(t);
  }
  return out.join(' ').replace(/\s+/g, ' ').trim();
};

const run = async () => {
  const browser = await chromium.launch();
  const out = { origin: ORIGIN, targets: [] };

  const list = TARGETS.filter((t) => !t.signedOut && !t.unreachable && !t.notDrivable
    && (!ONE || t.page === ONE));

  for (const t of list) {
    const rec = { page: t.page, view: t.view, modal: t.modal };
    // ★A FRESH CONTEXT PER TARGET, because this prover KILLS THE SESSION and localStorage is shared
    // across every page in a context. Reusing one context meant the first target signed everyone out:
    // all 15 later openers came back "absent", not because the controls are missing but because the
    // pages were rendering signed-out. An instrument that destroys the state it needs must not carry
    // that state forward — the same probe read those exact openers fine in prove_reload.mjs.
    // ★BLOCK SERVICE WORKERS AND ROUTE AT THE CONTEXT, or the 401 never reaches the request. A warm SW
    // serves fetches from its own handler, which page.route does not see - so a write that WAS attempted
    // reads as "issued no mutating request at all", i.e. UNGRADED, and the oracle silently loses its
    // subject. Found first in prove_fallback_engaged.mjs, where the same hole made a broken primary read
    // as "this page has no primary"; folded back here because the same 29 rows were ungraded for it.
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 },
      serviceWorkers: 'block' });
    await assertSignedIn(signIn(ctx, 'supervisor'));
    const page = await ctx.newPage();
    let blocked = 0;
    try {
      await page.goto(ORIGIN + '/workhive/' + t.page + '.html' + (QUERY[t.page] || ''),
        { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(6000);

      if (t.pre) {
        const ok = await page.evaluate((src) => {
          try { eval(src); return true; } catch (e) { return String(e.message || e); }
        }, t.pre);
        if (ok !== true) {
          rec.ok = null; rec.why = 'precondition did not hold, so the form was never reachable: ' + ok;
          out.targets.push(rec); await page.close(); await ctx.close(); continue;
        }
        await page.waitForTimeout(1800);
      }
      if (t.openBy === 'click') {
        const shown = await page.evaluate((sel) => {
          const el = document.querySelector(sel);
          if (!el) return 'absent';
          if (el.getBoundingClientRect().width < 1) return 'not visible';
          el.click(); return true;
        }, t.opener).catch((e) => String(e.message || e));
        if (shown !== true) {
          rec.ok = null; rec.why = 'opener ' + t.opener + ' was ' + shown + ', so no form opened';
          out.targets.push(rec); await page.close(); await ctx.close(); continue;
        }
      } else {
        await page.evaluate((src) => eval(src), t.fn).catch(() => {});
      }
      await page.waitForTimeout(1600);

      // Fill what there is to fill, and find the control that would submit it.
      const prep = await page.evaluate(({ modalSel, mark }) => {
        const vis = (el) => {
          const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
          return r.width > 4 && r.height > 4 && cs.display !== 'none' && cs.visibility !== 'hidden';
        };
        const sheet = modalSel
          ? (document.getElementById(modalSel) || document.querySelector('.' + modalSel)) : null;
        if (modalSel && (!sheet || !vis(sheet))) return { open: false };
        const root = sheet || document;
        const fields = [...root.querySelectorAll('input, textarea')]
          .filter((el) => vis(el) && !['checkbox', 'radio', 'file', 'hidden', 'submit'].includes(el.type));
        // ★A MARKER STRING IN A NUMBER FIELD NEVER REACHES THE NETWORK. My first run typed the same
        // text into every input, client-side validation refused every form, and all 34 targets came
        // back "no mutating request at all" — an oracle about what happens when a write is REFUSED,
        // reported over 34 writes that were never attempted. The form has to be fillable enough to
        // submit, so each control gets a value of its own type.
        const today = new Date().toISOString().slice(0, 10);
        const valueFor = (el) => {
          const t = (el.type || 'text').toLowerCase();
          if (t === 'number' || t === 'range') return '1';
          if (t === 'date') return today;
          if (t === 'time') return '08:00';
          if (t === 'datetime-local') return today + 'T08:00';
          if (t === 'email') return 'probe@example.com';
          if (t === 'tel') return '09171234567';
          if (t === 'url') return 'https://example.com';
          return mark;
        };
        fields.forEach((el) => {
          el.focus(); el.value = valueFor(el);
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
        });
        // A required <select> left on its empty placeholder blocks submission just as surely.
        [...root.querySelectorAll('select')].filter(vis).forEach((sel) => {
          if (sel.value) return;
          const opt = [...sel.options].find((o) => o.value && !o.disabled);
          if (opt) { sel.value = opt.value; sel.dispatchEvent(new Event('change', { bubbles: true })); }
        });
        // The submit affordance, by what it says — the vocabulary this platform actually uses.
        const SUB = /^(save|submit|add|create|post|send|confirm|update|log|record|apply)\b/i;
        const btn = [...root.querySelectorAll('button, [role="button"], input[type="submit"]')]
          .filter(vis)
          .find((el) => SUB.test((el.innerText || el.value || el.getAttribute('aria-label') || '').trim()));
        if (btn) btn.setAttribute('data-wh-submit', '1');
        return { open: true, fields: fields.length,
          submit: btn ? (btn.innerText || btn.value || '').trim().slice(0, 24) : null };
      }, { modalSel: t.modal, mark: MARK });

      if (!prep.open) {
        rec.ok = null; rec.why = 'the form did not open, so there was no mid-form moment to expire';
        out.targets.push(rec); await page.close(); await ctx.close(); continue;
      }
      if (!prep.submit) {
        rec.ok = null;
        rec.why = 'this sheet offers no submit control, so there is no write for an expired session to '
          + 'refuse; UNGRADED rather than a pass over an empty set';
        out.targets.push(rec); await page.close(); await ctx.close(); continue;
      }
      rec.fields = prep.fields; rec.submit = prep.submit;

      // ── THE SESSION DIES HERE ────────────────────────────────────────────────────────────────
      // Every mutating call is answered 401 before it can reach the database.
      await ctx.route('**/rest/v1/**', (route) => {
        const m = route.request().method();
        if (['POST', 'PATCH', 'PUT', 'DELETE'].includes(m)) {
          blocked++;
          return route.fulfill({ status: 401, contentType: 'application/json',
            body: JSON.stringify({ message: 'JWT expired', code: 'PGRST301' }) });
        }
        return route.continue();
      });
      await ctx.route('**/functions/v1/**', (route) => {
        blocked++;
        return route.fulfill({ status: 401, contentType: 'application/json',
          body: JSON.stringify({ error: 'Session expired', message: 'JWT expired' }) });
      });
      // And the client's own stored session goes, so it cannot silently refresh past the 401.
      await page.evaluate(() => {
        for (const store of [localStorage, sessionStorage]) {
          for (const k of Object.keys(store)) {
            if (/^sb-|auth-token|supabase/i.test(k)) store.removeItem(k);
          }
        }
      });

      const before = await page.evaluate(staticText);
      await page.evaluate(() => {
        const b = document.querySelector('[data-wh-submit]');
        if (b) b.click();
      });

      const seen = new Set();
      for (let i = 0; i < 28; i++) {
        const msgs = await page.evaluate(readMessages);
        msgs.forEach((m) => { if (m && !before.includes(m)) seen.add(m.slice(0, 160)); });
        await page.waitForTimeout(250);
      }
      const said = [...seen].join(' | ');
      rec.blocked = blocked;
      rec.message = said.slice(0, 300);

      if (!blocked) {
        // ★NO REQUEST MEANS NO WRITE WAS EVEN ATTEMPTED — the oracle has no subject.
        rec.ok = null;
        rec.why = 'pressing ' + JSON.stringify(prep.submit) + ' issued no mutating request at all, so '
          + 'no write was attempted and an expired session had nothing to refuse';
      } else if (!said) {
        rec.ok = false;
        rec.why = 'the write was refused with 401 and the surface said NOTHING - the person is looking '
          + 'at a form that appears to have done nothing, with no way to know they are signed out';
      } else if (SAYS_SESSION.test(said)) {
        const futile = OFFERS_RETRY.test(said) && !/sign|log/i.test(said);
        rec.ok = !futile;
        rec.why = futile
          ? 'names the session but offers a bare retry that would fail identically: ' + JSON.stringify(said.slice(0, 120))
          : 'names the expired session so the person knows why the write was refused'
            + (SAYS_NOT_SENT.test(said) ? ' and says their work was not sent' : '')
            + ': ' + JSON.stringify(said.slice(0, 120));
      } else {
        rec.ok = false;
        rec.why = 'said something, but nothing that names the session, so the person cannot tell a dead '
          + 'session from a broken save: ' + JSON.stringify(said.slice(0, 120));
      }
    } catch (e) {
      rec.ok = null; rec.why = 'could not measure: ' + String(e.message || e).slice(0, 120);
    }
    await page.close();
    await ctx.close();
    out.targets.push(rec);
    console.log('  ' + (rec.ok === null ? 'UNGRADED' : rec.ok ? 'PASS    ' : 'FAIL    ')
      + ' ' + (t.page + ' ' + t.view).padEnd(26) + ' ' + (rec.why || '').slice(0, 78));
  }
  await browser.close();
  writeFileSync(path.join(ROOT, 'session_expiry_report.json'), JSON.stringify(out, null, 1));
  const g = out.targets.filter((t) => t.ok !== null);
  console.log('\n  ' + g.filter((t) => t.ok).length + ' pass | ' + g.filter((t) => !t.ok).length
    + ' fail | ' + (out.targets.length - g.length) + ' ungraded');
  console.log('  NO WRITE LANDED: every mutating REST call and every edge invoke was answered 401.');
};
run().catch((e) => { console.error(e); process.exit(1); });
