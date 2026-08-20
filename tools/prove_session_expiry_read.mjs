// prove_session_expiry_read.mjs — the READ half of `session_expiry`.
//
// THE ORACLE: "the session died and the surface says so, in words the person can act on."
//
// ★WHY A SECOND PROVER RATHER THAN A WIDER ROSTER. prove_session_expiry.mjs answers the WRITE half:
// press submit with an expired token and read the refusal. Run across the full target list it returns
// "6 pass, 0 fail" — and not one passing target owns an owed row, because all ten owed rows sit on
// views whose verdict was "this sheet offers no submit control, so there is no write for an expired
// session to refuse": achievements, analytics-report, asset-hub, dayplanner, hive, project-report,
// public-feed, shift-brain. Those are READ surfaces. A write-refusal probe can never grade them, and
// widening its roster would only add more of the same UNGRADED. The missing structure is this one.
//
// ★AN EMPTY STATE AND AN EXPIRED SESSION ARE OPPOSITE CLAIMS. "No records yet" invites a person to
// start working; "your session expired" tells them to sign in. A page whose read 401s and which then
// paints its empty state has told them something false about their own data — the same shape as the
// public-feed defect where a failed read answered "No public posts yet" on a feed with 15 posts. So a
// bare empty state is the DEFECT here, not a pass, and silence is worse still.
//
// ★AND A GENERIC FAILURE IS NOT THE SAME ANSWER AS AN EXPIRED SESSION. "Could not load" is honest but
// unactionable; only naming the session tells the person that signing in fixes it. Recorded as its own
// outcome so the two are never collapsed — utils.js already ships the sentence (whReadError), so what
// this measures is ADOPTION, not whether the message exists.
//
// NON-WRITING: every request is answered from the route table; nothing reaches the database. Reads are
// 401'd rather than the real token being tampered with, so no session state is mutated for the user.
//
// USAGE:  node tools/prove_session_expiry_read.mjs [--page <name>]
// OUTPUT: session_expiry_read_report.json

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
const VIEW = (() => { const i = args.indexOf('--view'); return i >= 0 ? args[i + 1] : null; })();

// The eight pages that actually owe a session_expiry row, plus the query a page needs to render at all.
const PAGES = ['achievements', 'analytics-report', 'asset-hub', 'dayplanner', 'hive', 'project-report',
  'public-feed', 'shift-brain'];
const QUERY = { 'project-report': '?project_id=539e0d9a-9ff7-474b-ab03-9254406ca7dc' };

// Naming the expired session. utils.js already ships these sentences; the open question is ADOPTION.
const NAMES_EXPIRY = /session (has )?expired|signed? ?(you )?out|sign in again|log ?in again|session ended|not signed in|please sign in|session is no longer/i;
// A generic failure: better than silence, but it does not answer "why", which is what the oracle asks.
const NAMES_FAILURE = /could ?n.?t|could not|unable to|failed|error|went wrong|try again|check your connection/i;
// The lie: an empty state painted over a failed read.
const CLAIMS_EMPTY = /no .{0,24}(yet|found|records|entries|items|posts|data)|nothing (here|yet)|get started|add your first|none yet/i;

const readSurface = () => {
  const vis = (el) => {
    const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.width > 2 && r.height > 2 && cs.display !== 'none' && cs.visibility !== 'hidden'
      && Number(cs.opacity) > 0.05;
  };
  const SEL = '[role="alert"], [role="status"], [aria-live], .toast, .hive-toast, .toast-text,'
    + ' [class*="error"], [id*="error"], [class*="empty"], [id*="empty"]';
  const notices = [...document.querySelectorAll(SEL)].filter(vis)
    .map((el) => (el.textContent || '').trim()).filter(Boolean);
  return {
    notices: [...new Set(notices)].slice(0, 12),
    // Announcements collected since load, so a toast that has already dismissed is still counted.
    collected: [...new Set(window.__whSeen || [])].slice(0, 12),
    bodyLen: (document.body.innerText || '').replace(/\s+/g, ' ').trim().length,
  };
};

const run = async () => {
  const browser = await chromium.launch();
  const out = { origin: ORIGIN, pages: [] };

  for (const name of (ONE ? [ONE] : PAGES)) {
    const rec = { page: name };
    // ★SERVICE WORKERS BLOCKED AND ROUTING AT THE CONTEXT. A warm SW serves fetches from its own
    // handler, which page.route never sees — the 401 would simply not reach the request, and the page
    // would render normally while this probe reported a clean expired-session run. Found the hard way
    // in prove_fallback_engaged.mjs, where the same hole read as "this page has no primary".
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 },
      serviceWorkers: 'block' });
    try {
      await assertSignedIn(signIn(ctx, 'supervisor'));
      let reads = 0;
      // ★REACH THE VIEW FIRST, THEN EXPIRE THE SESSION. For a non-default view the read under test is
      // the one the view issues when it OPENS, and a page whose every read already 401ed cannot render
      // the control that opens it - asset-hub needs an asset in the tree before its reliability tabs
      // have any height at all. Installing the 401s up front would measure "the view never opened",
      // which is not what the oracle asks. Same deferral prove_fallback_engaged.mjs makes for a press
      // flow, for the same reason.
      const expireSession = async () => {
        await ctx.route('**/rest/v1/**', (route) => {
          reads++;
          return route.fulfill({ status: 401, contentType: 'application/json',
            body: JSON.stringify({ message: 'JWT expired', code: 'PGRST301' }) });
        });
        await ctx.route('**/functions/v1/**', (route) => route.fulfill({ status: 401,
          contentType: 'application/json', body: JSON.stringify({ message: 'JWT expired' }) }));
      };
      if (!VIEW) await expireSession();

      const page = await ctx.newPage();
      // Collect announcements from load onward, because a toast is gone before the verdict reads.
      await page.addInitScript(() => {
        window.__whSeen = [];
        const SEL = '[role="alert"], [role="status"], [aria-live], .toast, .hive-toast, .toast-text,'
          + ' [class*="error"], [id*="error"]';
        const push = (el) => { const t = (el.textContent || '').trim(); if (t) window.__whSeen.push(t); };
        const grab = (n) => {
          if (!n || n.nodeType !== 1) return;
          if (n.matches && n.matches(SEL)) push(n);
          if (n.querySelectorAll) n.querySelectorAll(SEL).forEach(push);
        };
        addEventListener('DOMContentLoaded', () => {
          new MutationObserver((ms) => ms.forEach((m) => m.addedNodes.forEach(grab)))
            .observe(document.body, { childList: true, subtree: true });
        });
      });
      await page.goto(ORIGIN + '/workhive/' + name + '.html' + (QUERY[name] || ''),
        { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(8000);
      if (VIEW) {
        const t = TARGETS.find((x) => x.page === name && x.view === VIEW);
        if (!t) {
          rec.ok = null;
          rec.why = 'no grounded ' + VIEW + ' target exists for this page in dialog_targets.mjs, so the '
            + 'view was never opened; UNGRADED rather than measured against a subject I invented';
          out.pages.push(rec); await page.close(); await ctx.close(); continue;
        }
        if (t.notDrivable) {
          rec.ok = null;
          rec.why = 'dialog_targets.mjs records this ' + VIEW + ' as NOT DRIVABLE, with its reason, so '
            + 'there is no reachable view for an expired session to be announced on';
          out.pages.push(rec); await page.close(); await ctx.close(); continue;
        }
        rec.target = { modal: t.modal, openBy: t.openBy, opener: t.opener || t.fn || null };
        if (t.pre) await page.evaluate((src) => { try { eval(src); } catch (e) {} }, t.pre)
          .catch(() => {});
        await page.waitForTimeout(1500);
        await expireSession();                       // the session dies with the view now reachable
        if (t.openBy === 'click') {
          rec.opened = await page.evaluate((sel) => {
            const el = document.querySelector(sel);
            if (!el) return 'absent';
            const r = el.getBoundingClientRect();
            if (r.width < 1 || r.height < 1) return 'not visible';
            el.click(); return 'clicked';
          }, t.opener).catch((e) => 'threw');
        } else {
          await page.evaluate((src) => { try { eval(src); } catch (e) {} }, t.fn).catch(() => {});
          rec.opened = 'fn';
        }
        await page.waitForTimeout(7000);
      }
      const s = await page.evaluate(readSurface);
      rec.reads401 = reads;
      rec.notices = s.notices;
      const all = [...s.notices, ...s.collected].join(' | ');
      rec.text = all.slice(0, 200);

      if (!reads) {
        // ★THE ZERO-DENOMINATOR RAIL. No read means the expired session was never put to this surface.
        rec.ok = null;
        rec.why = 'no PostgREST read was issued, so an expired session was never put to this surface; '
          + 'UNGRADED rather than a pass over an empty set';
      } else {
        // ★RECORD THE MATCHED SENTENCE, NOT JUST THE VERDICT. NAMES_EXPIRY contains "sign in", which
        // appears in ordinary page chrome, so a bare true/false cannot distinguish "the page explained
        // the expired session" from "the page has a Sign In button". Banking a claim means naming what
        // it rests on, and a 8/8 sweep is exactly when that matters most.
        const hit = all.match(NAMES_EXPIRY);
        rec.matched = hit ? all.slice(Math.max(0, hit.index - 60), hit.index + 90) : null;
        const expiry = NAMES_EXPIRY.test(all);
        const failure = NAMES_FAILURE.test(all);
        const empty = CLAIMS_EMPTY.test(all) && !expiry && !failure;
        rec.namesExpiry = expiry; rec.namesFailure = failure; rec.claimsEmpty = empty;
        rec.ok = expiry;
        rec.why = expiry
          ? 'all ' + reads + ' read(s) were answered 401 and the surface names the expired session, so '
            + 'the person is told why and what would fix it: ' + JSON.stringify(all.slice(0, 120))
          : empty
            ? 'all ' + reads + ' read(s) 401ed and the surface painted an EMPTY STATE — it tells the '
              + 'person they have no data when in fact it could not read theirs: '
              + JSON.stringify(all.slice(0, 120))
            : failure
              ? 'all ' + reads + ' read(s) 401ed and the surface reports a generic failure without '
                + 'naming the expired session, so the person cannot tell that signing in would fix it: '
                + JSON.stringify(all.slice(0, 120))
              : 'all ' + reads + ' read(s) 401ed and the surface says nothing at all about it: '
                + JSON.stringify(all.slice(0, 120) || '(no notice rendered)');
      }
      await page.close();
    } catch (e) {
      rec.ok = null; rec.why = 'could not measure: ' + String(e.message || e).slice(0, 120);
    }
    await ctx.close();
    out.pages.push(rec);
    console.log('  ' + (rec.ok === null ? 'UNGRADED' : rec.ok ? 'PASS    ' : 'FAIL    ')
      + ' ' + name.padEnd(18) + ' ' + (rec.why || '').slice(0, 96));
  }
  await browser.close();
  writeFileSync(path.join(ROOT, (VIEW ? 'session_expiry_read_' + VIEW + '_report.json' : 'session_expiry_read_report.json')), JSON.stringify(out, null, 1));
  const g = out.pages.filter((p) => p.ok !== null);
  console.log('\n  ' + g.filter((p) => p.ok).length + ' pass | ' + g.filter((p) => !p.ok).length
    + ' fail | ' + (out.pages.length - g.length) + ' ungraded');
};
run().catch((e) => { console.error(e); process.exit(1); });
