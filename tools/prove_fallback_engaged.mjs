// prove_fallback_engaged.mjs — the CG `fallback_engaged` oracle, measured by taking the primary down.
//
// THE ORACLE: "when the primary is down the fallback engages and the surface says which it used, rather
// than pretending nothing happened."
//
// ★THE FALLBACK ON THIS PLATFORM IS THE SAVED SNAPSHOT, and it is a real, shipped design rather than
// something this prover invented. analytics hydrates from `analytics_snapshots` before it recomputes;
// alert-hub serves the stored `amc_briefings` row instantly and treats the live orchestrator call as a
// background UPGRADE (its own comment says so); shift-brain keeps the existing `shift_plans` row when a
// regeneration fails. Each of those pages ALSO ships a source chip — "Recomputed just now", "Saved
// snapshot", "Live · refreshed on load" — which is precisely the "says which it used" half of the
// oracle. So the measurement is: break the primary, then read what is on screen and what the chip says.
//
// ★THE THREE OUTCOMES, and only one of them is the defect:
//   · ENGAGED + NAMED   — content is still on screen AND the surface says the source is a saved/stored
//                         one. This is the oracle satisfied.
//   · ENGAGED + SILENT  — content is still on screen and the surface still claims to be LIVE, or says
//                         nothing about its source. This is the defect the oracle names in so many
//                         words: pretending nothing happened. A person reads yesterday's numbers as
//                         today's, which on a maintenance board is how a decision gets made on stale
//                         data.
//   · NO FALLBACK       — nothing rendered, or the page said the primary failed and offered no stored
//                         copy. That is `fail_500`'s question, not this one. UNGRADED, with the reason.
//
// ★THE PRIMARY IS BROKEN AT THE EDGE, NOT AT THE DATABASE. Only `/functions/v1/` is answered 500; the
// REST reads that serve the stored snapshot are left alone. Breaking both would guarantee "no fallback"
// on every page and prove nothing — the fallback needs its own path intact to engage, which is the whole
// point of having one.
//
// ★NON-WRITING. Every mutating REST call is refused before it can leave, and the edge is stubbed, so
// nothing reaches the shared database. Pages are only loaded and read.
//
// USAGE:  node tools/prove_fallback_engaged.mjs [--page <name>]
// OUTPUT: fallback_engaged_report.json

import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'node:url';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

// The pages with a REAL primary/fallback split — an edge-function primary over a stored copy. Grounded
// in the same reading that produced prove_quota_legible.mjs's flow list.
const FLOWS = {
  // ★ONLY PAGES WITH A DOCUMENTED STORED FALLBACK. My first list included project-report and hive, and
  // it mislabelled them: with the edge down they still render dozens of figures, but those come from
  // LIVE REST views, not from a stored copy — the edge function only powers their AI narrative. So the
  // prover was reading "content is still on screen" as "the fallback engaged", when no fallback was
  // involved at all. project-report's chip even says what it is ("Recomputed when this report is
  // generated · Based on your project items"), which describes a DERIVATION, not a provenance claim
  // that the primary ran. Treating that as a silent fallback would file a true reading under the wrong
  // oracle, which this bank has now done often enough to name it on sight.
  analytics:     { press: '#refresh-btn' },   // hydrates from analytics_snapshots, then recomputes
  // ★alert-hub NEEDS ITS CHIP SCOPED TO THE BRIEF, AND UNTIL IT IS, ITS VERDICT RESTS ON THE WRONG
  // SUBJECT. This prover reads chips page-wide, and alert-hub's page chip says "Live data · v_risk_truth"
  // - which is TRUE: the 13 alert figures come from live REST views, not from the edge. The stored
  // fallback here is the AMC BRIEF panel alone (amc_briefings), whose own freshness is a different
  // element. Reported as a FAIL, that reading would have accused a correct chip of lying, the same
  // right-reading-wrong-subject error this bank has recorded before. Left OWED deliberately: the fix is
  // to scope the chip read to the brief panel, not to bank a verdict I know is aimed at the wrong thing.
  // ★AND THE SCOPE HAS TO BE THE CARD, NOT THE FIRST THING THAT MATCHES. My first selector was
  // '[class*="amc"], [id*="amc"]', which querySelector resolves to the FIRST match - a small stat div -
  // so the panel measured 0 figures and I nearly recorded "the fallback never engages" about a page that
  // engages it correctly. Probed directly, the panel renders 449 characters of stored brief with the
  // edge 500'd: "AMC DAILY BRIEF shift 2026-08-19 · model amc-v1 PENDING ...", crew stat 5, from an
  // amc_briefings row that is present and unexpired (13 rows, today's shift_date). Three verdicts came
  // out of one page depending only on where I pointed: FAIL page-wide, "no fallback" mis-scoped, and the
  // truth once scoped to the card.
  'alert-hub':   { onLoad: true, chipScope: '#amc-card' },
  // ★A BUTTON-INVOKED PRIMARY NEEDS A PRESS, otherwise a load-only flow reports 'no edge call' and
  // grades nothing - honest, but permanently owed. project-manager reaches project-orchestrator through
  // runAIIntent (project-manager.html:1817), bound to #ai-intent-go at :792. Read from source, not
  // guessed - three selector guesses elsewhere in this session matched zero elements.
  'project-manager': { pre: 'AI: from text', fill: '#ai-intent-text', press: '#ai-intent-go', settle: 8000 },
  'shift-brain': { press: '#generate-btn' },  // keeps the existing shift_plans row when generation fails
  "analytics-report": { onLoad: true },
  // ★asset-hub's primary is BUTTON-INVOKED: computeWeibullFit (asset-hub.html:3230) calls
  // weibull-fitter, wired to #weibull-fit-btn at :1612. Reaching it needs the same two gates the
  // other asset-hub work found: #asset-view-toggle reveals #reliability-card (display:none), and
  // a [data-node-id] click selects the asset. Replacing the onLoad entry IN PLACE - adding a
  // second key would silently override it, which is exactly the bug that made project-manager
  // look like it had no primary for several rounds.
  "asset-hub": { pre: ['Show Reliability Workbench', '[data-node-id]'],
                 press: '#weibull-fit-btn', settle: 8000 },
  // ★assistant's primary is the chat itself: sendMessage() invokes ai-gateway (assistant.html:1119)
  // from #send-btn (:368), reading #chat-input (:360). No panel to open - the composer is the
  // landing view - so this is a plain fill-then-press. Replaced IN PLACE; a second key would
  // silently override it, which is the bug that hid project-manager's flow for several rounds.
  "assistant": { fill: '#chat-input', press: '#send-btn', settle: 8000 },
  "community": { onLoad: true },
  "dayplanner": { onLoad: true },
  "engineering-design": { onLoad: true },
  // ★hive's primary is the Reliability Coach: askCoach (hive.html:5509) calls ai-gateway /
  // ai-orchestrator from #coach-submit (:1252), and it reads #coach-input, so this needs the full
  // open-fill-press shape. The panel is collapsed behind #coach-toggle-btn (:1232), which an
  // [aria-controls] sweep of this page had already identified as pointing at a display:none target.
  // Replaced IN PLACE - a second key would silently override it.
  // ★SCOPED TO THE COACH PANEL. Read page-wide this FAILed on a chip that belongs to the AI-summary
  // panel ('AI summary - refreshed daily') over 16 figures that are the BOARD's live REST reads -
  // a verdict resting on a neighbour's honest chip, the same error alert-hub taught. chipScope
  // narrows BOTH the chip read AND the figure count to #coach-body, because scoping the chip
  // alone still borrows the board's numbers.
  "hive": { pre: ['#coach-toggle-btn'], fill: '#coach-input', press: '#coach-submit',
            chipScope: '#coach-body', settle: 8000 },
  "index": { onLoad: true },
  "inventory": { onLoad: true },
  // ★A DUPLICATE KEY SILENTLY OVERRODE THE ONE ABOVE. When I widened this roster to the owed
  // pages I added "project-manager": { onLoad: true } here, and in a JS object literal the LAST
  // entry wins - so the pre/fill/press flow defined at line 79 was never the one that ran, and
  // the page reported 'no edge call' with a load-only flow while every selector in it was
  // correct. It cost several rounds and one wrong retraction to find, because the symptom
  // (0 edge calls) is identical to 'this surface has no primary'. Removed; line 79 is the flow.
  // ★A BUTTON-REACHABLE PRIMARY NEEDS A PRESS. A load-only flow reports 'no edge call' and grades
  // nothing - honest, but permanently owed. #ai-narrative-btn invokes project-orchestrator,
  // grounded in prove_quota_legible.mjs's flow list rather than guessed, and the longer settle is
  // there because a first run pressed before the report had loaded and the handler early-returned.
  "project-report": { press: '#ai-narrative-btn',
    url: '?project_id=853abed7-4a61-4bb4-b771-f0d2d0196490', settle: 9000 },
  // ★report-sender's primary is the SEND itself - send-report-email (report-sender.html:1192) from
  // #send-btn (:657), which ships DISABLED until a report is selected and a recipient entered.
  // The flow is reused from prove_quota_legible.mjs, which already grounded it: pick the 'PM
  // Overdue' report, then fill #email-input. SAFETY: nothing can leave - this oracle stubs EVERY
  // /functions/v1/ call with 500 and holds every mutating REST call, so the send is intercepted
  // before the transport. I deferred this page once as 'an outward action'; that was over-cautious,
  // because the harness removes the risk the deferral was worried about.
  "report-sender": { waitIdle: true, errSlot: '#email-error', pre: ['PM Overdue'], fill: ['#email-input', 'probe@example.com'],
                     press: '#send-btn', settle: 8000 },
};

// A chip or line that NAMES a stored source. Deliberately narrow: this vocabulary is the oracle, and a
// loose pattern would credit any sentence containing "data".
// ★AN ORACLE'S VOCABULARY IS PART OF THE ORACLE, and mine rejected the correct fix. After shift-brain
// was changed to say "loaded from storage, not regenerated just now" — precisely the admission this
// oracle exists to require — the pattern still scored it as naming no source, because "loaded from
// storage" was not in the list. A vocabulary narrow enough to miss the right answer manufactures a
// defect out of the fix for the defect.
const NAMES_STORED = /saved (copy|snapshot|version)|stored (brief|copy|plan)|from storage|loaded from|snapshot|cached|last (computed|updated|refreshed|generated)|from (an? )?earlier|previously (computed|generated)|as of |not (recomputed|regenerated)|showing (the )?(saved|stored|last)/i;
// A claim that the numbers are CURRENT. If the primary is down and the surface still says this, the
// fallback engaged silently and the person is being told something false.
const CLAIMS_LIVE = /\blive\b|recomputed just now|refreshed on load|up to date|just now/i;
// The surface saying, in words, that the thing which failed has failed. Deliberately narrow: it must
// name a failure, not merely offer a retry - a bare "Try again" appears on healthy surfaces too.
const ANNOUNCES_FAILURE = /\b(failed|failure|couldn't|could not|unable to|went wrong|error|unavailable|not available|no connection|offline)\b/i;

const readSurface = (chipScope) => {
  const vis = (el) => {
    const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.width > 2 && r.height > 2 && cs.display !== 'none' && cs.visibility !== 'hidden'
      && Number(cs.opacity) > 0.05;
  };
  // The source chips and status lines the platform ships.
  // ★THE CHIP THAT ANSWERS THIS ORACLE IS THE ONE ON THE FALLBACK'S OWN PANEL. Read page-wide,
  // alert-hub's "Live data · v_risk_truth" chip made it look like the page was calling stored numbers
  // live - but that chip is TRUE and describes the alert list, which really does come from live REST
  // views. The stored copy on that page is the AMC brief alone. A scope confines the read to the panel
  // the fallback actually feeds, so the verdict stops resting on a neighbouring component's honest chip.
  const chipRoot = chipScope ? (document.querySelector(chipScope) || document) : document;
  // ★INSIDE AN EXPLICIT PANEL SCOPE, EVERY SHORT LINE IS THE PANEL'S OWN STATEMENT. The chip-class
  // selector list could not see alert-hub's `#amc-shift-meta`, so the fix that made the card say
  // "stored brief, generated ..." changed nothing the oracle could read - the third time this session a
  // reading surface rejected the very sentence it asked for. When a scope is given, the panel has
  // already been narrowed to the fallback's own component, so reading its short leaves adds no risk of
  // quoting a neighbour.
  const scopedLines = chipScope
    ? [...chipRoot.querySelectorAll('*')].filter((e) => !e.children.length && vis(e))
        .map((e) => (e.innerText || '').replace(/\s+/g, ' ').trim())
        .filter((t) => t && t.length < 200)
    : [];
  const chips = scopedLines.concat([...chipRoot.querySelectorAll(
    '[class*="chip"], [class*="source"], [class*="freshness"], [id*="source"], [id*="status"], '
    + '[role="status"], [aria-live], [class*="badge"], [class*="stamp"]')]
    .filter(vis).map((e) => (e.innerText || '').replace(/\s+/g, ' ').trim())
    // ★A LENGTH CAP THAT DISCARDED THE ANSWER. At 160 chars this dropped shift-brain's source chip the
    // moment the page was FIXED: the honest wording ("loaded from storage, not regenerated just now")
    // pushed it to ~180 characters, the filter binned it, and the prover reported that nothing named the
    // source — over a chip that named it perfectly. The cap exists to skip paragraphs of body copy, and
    // 400 still does that while fitting a chip that explains itself.
    .filter((t) => t && t.length < 400));
  // Is there substance on screen at all? Numbers are the thing these boards exist to show.
  // ★AND THE FIGURES MUST BE COUNTED IN THE SAME PLACE AS THE CHIP. Scoping only the chip still left
  // the count page-wide, so alert-hub's 13 LIVE alert figures were being offered as evidence about the
  // stored brief. A verdict has to read one subject end to end.
  const nums = [...chipRoot.querySelectorAll('*')]
    .filter((el) => !el.children.length && vis(el)
      && /^[₱$€£]?\s*-?\d[\d,]*(\.\d+)?\s*%?$/.test((el.textContent || '').trim())).length;
  const body = (document.body.innerText || '').replace(/\s+/g, ' ').trim();
  return { chips, nums, bodyLen: body.length, body: body.slice(0, 400) };
};

const run = async () => {
  const browser = await chromium.launch();
  const out = { origin: ORIGIN, pages: [] };

  for (const name of Object.keys(FLOWS).filter((p) => !ONE || p === ONE)) {
    const flow = FLOWS[name];
    const rec = { page: name };
    // ★BLOCK SERVICE WORKERS, OR THE BREAK SILENTLY DOES NOT TAKE. A warm SW serves the edge call
    // from its own fetch handler, which page.route never sees: report-sender read `edgeCallsBroken: 0`
    // while generateReport() demonstrably reached its invoke and returned a real summary. An unbroken
    // primary renders identically to a working fallback, so that reading is a FALSE PASS, not a
    // "this page has no primary". Blocking registration removes the bypass at the source.
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 },
      serviceWorkers: 'block' });
    await assertSignedIn(signIn(ctx, 'supervisor'));
    const page = await ctx.newPage();
    let edgeDown = 0;
    try {
      // ── the PRIMARY goes down; the stored copy's own path stays up ──────────────────────────────
      // ★BREAK THE PRIMARY WHEN IT IS INVOKED, NOT AT PAGE LOAD. Installing this route before the
      // page loaded meant the page's OWN init edge calls failed, so on a surface whose primary is
      // reached through a control, that control may never render - and the prover then reported 'no
      // edge call', i.e. 'this page has no primary', about a page that has one. That is the tension
      // this oracle lives with: to test a fallback you must break the primary, but breaking it too
      // early stops you reaching the thing that invokes it. For a PRESS flow the break is deferred
      // until after the reach; for an onLoad flow it must still be installed up front, because there
      // the load IS the invocation.
      // ★OPEN INSTRUMENT FAULT - report-sender reads `edgeCallsBroken: 0` and it is NOT "this page has
      // no primary". Measured 2026-08-19: the press lands (enabled/idle/sel=1), doSend runs past every
      // guard to setCardState('processing') with an EMPTY #email-error, and generateReport() called
      // directly in the same page returns a real summary ("We have 28 overdue assets and 2 at-risk...").
      // So the invoke happens and this route handler still never increments - i.e. THE BREAK DID NOT
      // TAKE. page.route does not intercept requests served by a warm service worker, which is already
      // recorded in memory as one of the three ways a failure probe lies. asset-hub in the same run
      // reads edgeCallsBroken: 1, so the interception works where no SW is in the way.
      // DO NOT grade report-sender off this reading: an unbroken primary renders identically to a
      // page with a working fallback, which is a FALSE PASS. The fix to verify next is routing at the
      // CONTEXT level (ctx.route) and/or unregistering the service worker before the walk.
      const breakPrimary = async () => {
        await ctx.route('**/functions/v1/**', (route) => {
          edgeDown++;
          return route.fulfill({ status: 500, contentType: 'application/json',
            body: JSON.stringify({ error: 'upstream unavailable' }) });
        });
        // ★THE WRITE-HOLD MOVES WITH THE BREAK. Installed at page load it can change what the
        // page renders before the reach even starts, and the reach is how a press-flow primary is
        // invoked at all - so every interception this oracle performs now lands at the SAME
        // moment: immediately before the invocation it is meant to break.
      await ctx.route('**/rest/v1/**', (route) => {
        const m = route.request().method();
        if (['POST', 'PATCH', 'PUT', 'DELETE'].includes(m)) {
          return route.fulfill({ status: 503, contentType: 'application/json',
            body: JSON.stringify({ message: 'probe: writes are held' }) });
        }
        return route.continue();
      });
      };
      if (!flow.press) await breakPrimary();

      await page.goto(ORIGIN + '/workhive/' + name + '.html' + (flow.url || ''),
        { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(flow.settle || 7000);
      // ★A TWO-STEP REACH: the control that INVOKES the primary can itself sit behind a panel. On
      // project-manager, #ai-intent-go (runAIIntent -> project-orchestrator) lives inside an AI panel
      // opened by a visible "AI: from text" button, so a single press found nothing and the page kept
      // reporting "no edge call" - which reads as "this surface has no primary" when it simply had one
      // more door.
      // ★A REACH CAN NEED SEVERAL DOORS. asset-hub's primary sits behind TWO: #asset-view-toggle reveals
      // #reliability-card, and only then does selecting a [data-node-id] asset expose #weibull-fit-btn.
      // A single pre-click could never get there, so pre now takes an ARRAY - each step either a CSS
      // selector (starts with # . or [) or a TEXT match against a visible control. Same recipe then
      // covers hive, report-sender and assistant.
      if (flow.pre) {
        for (const step of (Array.isArray(flow.pre) ? flow.pre : [flow.pre])) {
          await page.evaluate((sel) => {
            const el = /^[#.[]/.test(sel)
              ? document.querySelector(sel)
              : [...document.querySelectorAll('button,[onclick]')]
                  .find((e) => e.getBoundingClientRect().height > 0
                               && new RegExp(sel, 'i').test((e.innerText || '').trim()));
            if (el) el.click();
          }, step).catch(() => {});
          await page.waitForTimeout(2000);
        }
      }
      // ★AND A PARSER NEEDS SOMETHING TO PARSE. runAIIntent reads the panel's textarea and returns
      // early when it is empty, so opening the panel and pressing still produced ZERO edge calls - the
      // page looked like it had no primary when it was simply waiting for input. Same fill-then-press
      // shape engineering-design's calc case needed.
      if (flow.fill) {
        // ★AND THE FILL MUST NAME ITS FIELD. This page shows THREE visible textareas once the panel is
        // open (#ai-intent-text, plus the assistant's #wh-ai-input and a feedback box), so "first empty
        // one" typed into the wrong box and the parser still had nothing. flow.fill now carries the
        // selector - the same bind-to-the-thing-not-its-shape rule that fixed the logbook case.
        // ★AND THE VALUE MUST SUIT THE FIELD. fill wrote a maintenance SENTENCE into report-sender's
        // #email-input, which is type="email" - invalid, so #send-btn stayed disabled and the page
        // reported 'no edge call', i.e. 'no primary', about a page whose primary is its whole purpose.
        // fill now accepts [selector, value]; the default sentence still suits a free-text parser.
        await page.evaluate((spec) => {
          const [sel, val] = Array.isArray(spec) ? spec : [spec, null];
          const t = (typeof sel === 'string' && document.querySelector(sel))
            || [...document.querySelectorAll('textarea, input[type=text]')]
                 .find((e) => e.getBoundingClientRect().height > 0 && !e.value);
          if (t) {
            t.value = val || 'Replace the No. 2 boiler feedwater pump mechanical seal during the November shutdown';
            t.dispatchEvent(new Event('input', { bubbles: true }));
            t.dispatchEvent(new Event('change', { bubbles: true }));
          }
        }, flow.fill).catch(() => {});
        // ★A DEBOUNCED VALIDATOR NEEDS LONGER THAN 800ms. Measured: report-sender's #send-btn was still
        // DISABLED at press time (rec.reachPress = 'DISABLED') even though pre and fill both succeeded,
        // while a hand-driven run with a 1200ms pause saw disabled flip to false. The form re-validates
        // after the input event, so the press was simply arriving too early.
        await page.waitForTimeout(2200);
      }
      // ★A DISABLED CONTROL IS NOT A MISSING CONTROL, and pressing it logs as a click either way.
      // Measured: report-sender's #send-btn was DISABLED at press time with the report already selected
      // (sel=1), because the page's own double-submit guard disables it whenever _cardState !== 'idle'
      // and the card was sitting in 'processing'. A press into that state is a no-op that reads exactly
      // like a press that fired - the click-that-changes-nothing class. So WAIT for the state machine to
      // reach idle, and record what was actually observed rather than assuming it got there.
      if (flow.press && flow.waitIdle) {
        rec.idleWait = await page.evaluate(async (ms) => {
          const t0 = Date.now();
          while (Date.now() - t0 < ms) {
            if (typeof _cardState === 'undefined') return 'no state machine';
            if (_cardState === 'idle') return 'idle after ' + (Date.now() - t0) + 'ms';
            await new Promise((r) => setTimeout(r, 250));
          }
          return 'NEVER IDLE (stuck in ' + _cardState + ' for ' + ms + 'ms)';
        }, 12000).catch((e) => 'threw: ' + String(e.message || e).slice(0, 60));
      }
      // ★A TOAST IS GONE BEFORE THE VERDICT READS THE PAGE. project-manager DOES announce the failure -
      // runAIIntent's error branch calls showToast(whAiError(error,'AI failed'),'error') at :1826, and
      // its showToast(msg, kind, ms) signature is correct - but the surface is read once after an
      // 8s settle, by which time a ~3s toast has expired. Reading late scored an honest page as a
      // silent fallback. So ARM A COLLECTOR BEFORE the press and let it accumulate every announcement
      // that ever appears, rather than sampling whatever survives to the end. Same lesson as the 16x250ms
      // union in prove_offline_refusal.mjs, done with an observer so nothing between polls is missed.
      if (flow.press) {
        await page.evaluate(() => {
          const SEL = '[role="alert"], [role="status"], [aria-live], .toast, .hive-toast, .toast-text,'
            + ' [class*="error"], [id*="error"], [class*="fail"]';
          window.__whAlerts = [];
          const grab = (n) => {
            if (!n || n.nodeType !== 1) return;
            if (n.matches && n.matches(SEL)) {
              const t = (n.textContent || '').trim();
              if (t) window.__whAlerts.push(t);
            }
            if (n.querySelectorAll) for (const el of n.querySelectorAll(SEL)) {
              const t = (el.textContent || '').trim();
              if (t) window.__whAlerts.push(t);
            }
          };
          new MutationObserver((ms) => {
            for (const m of ms) {
              m.addedNodes.forEach(grab);
              if (m.type === 'characterData' || m.type === 'attributes') grab(m.target.parentElement || m.target);
            }
          }).observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true });
        }).catch(() => {});
      }
      if (flow.press) await breakPrimary();
      if (flow.press) {
        await page.evaluate((sel) => {
          const el = document.querySelector(sel);
          // ★READ THE CONTROL BEFORE PRESSING IT. Reading `disabled` AFTER the click reported
          // 'DISABLED' on a button that was enabled and fired: the handler entered its busy state and
          // the page's own double-submit guard disabled the control, so the probe measured its own
          // effect and I read it as a refusal. State is captured pre-click for the same reason.
          const was = el ? (el.disabled ? 'DISABLED' : 'enabled') : 'absent';
          const st = (typeof _cardState !== 'undefined' ? _cardState : '?')
            + '/sel=' + (typeof _selected !== 'undefined' ? _selected.size : '?');
          if (el && !el.disabled) el.click();
          return was + ' [' + st + ']';
        }, flow.press).then((r) => { rec.reachPress = r; }).catch(() => { rec.reachPress = 'threw'; });
        await page.waitForTimeout(flow.settle || 7000);
        // ★READ THE ERROR SLOT ON THE PAGE THAT WAS PRESSED. The first version of this read ran on
        // `cp`, the healthy CONTROL page, which never presses anything - so it returned '(empty)' and I
        // nearly took that as "the handler got past its guards". A reading is scoped to a page object,
        // and the control page is a different page.
        if (flow.errSlot) {
          rec.errSlot = await page.evaluate((sel) => {
            const e = document.querySelector(sel);
            return e ? ((e.textContent || '').trim() || '(empty)') : '(no such slot)';
          }, flow.errSlot).catch(() => 'threw');
        }
        await page.waitForTimeout(7000);
      }

      const s = await page.evaluate(readSurface, flow.chipScope || null);

      // ★A HEALTHY CONTROL, so "no fallback engaged" can be told apart from "this view never consumed
      // the primary". Ported from prove_failure_injection.mjs, where the same rule resolved
      // engineering-design: with the edge 500'd it renders BYTE-IDENTICALLY (1845 chars either way)
      // because its calculators are client-side, and calling that a fallback failure would demand an
      // alarm about something the person never asked for. The equality is the whole guard - ANY
      // shrinkage means content DID depend on the read, and then the silence is real.
      const ctl = await browser.newContext({ viewport: { width: 390, height: 844 },
        serviceWorkers: 'block' });
      await assertSignedIn(signIn(ctl, 'supervisor'));
      const cp = await ctl.newPage();
      let healthy = null;
      try {
        await cp.goto(ORIGIN + '/workhive/' + name + '.html' + (flow.url || ''),
          { waitUntil: 'domcontentloaded', timeout: 30000 });
        await cp.waitForTimeout(flow.settle || 7000);
        healthy = await cp.evaluate(readSurface, flow.chipScope || null);
      } catch (_) { /* empty-catch-allow: no control means the identical-render test is simply skipped */ }
      await cp.close(); await ctl.close();
      rec.healthyChars = healthy ? healthy.bodyLen : null;
      rec.failedChars = s.bodyLen;
      rec.edgeCallsBroken = edgeDown;
      rec.numbers = s.nums;
      rec.chips = s.chips.slice(0, 8);
      const chipText = s.chips.join(' | ');

      if (!edgeDown) {
        // ★NO PRIMARY CALL MEANS NO PRIMARY TO TAKE DOWN — the oracle has no subject here.
        rec.ok = null;
        rec.why = 'this surface made no edge call, so there was no primary to break and no fallback for '
          + 'it to engage; UNGRADED rather than a pass over an empty set';
      // ★I PORTED THE BYTE-IDENTICAL "NO SUBJECT" RULE HERE FROM prove_failure_injection.mjs AND HAD TO
      // TAKE IT BACK OUT - the same evidence means OPPOSITE things to the two oracles. There, an
      // identical render proves the view never consumed the failing reads. HERE, an identical render is
      // what a WORKING fallback looks like: shift-brain serves its stored shift_plans row in the healthy
      // case too, so healthy and failed are both 3307 chars, and the rule turned a genuine PASS into
      // UNGRADED. A cross-oracle rule transplant needs the same argument re-made in the new context, not
      // just the same measurement. The healthy control is KEPT because the numbers are worth recording,
      // but it no longer decides the verdict.
      } else if (s.nums < 3) {
        rec.ok = null;
        rec.why = 'with the primary down the surface rendered almost no content (' + s.nums + ' figures), '
          + 'so no fallback engaged at all - whether it SAYS the primary failed is fail_500\'s question, '
          + 'not this one';
      } else {
        const named = NAMES_STORED.test(chipText);
        // ★AN EXPLICIT FAILURE ANNOUNCEMENT IS ALSO AN HONEST ANSWER, and without this the oracle
        // scored one as a defect. report-sender with `scheduled-agents` held to 500 says "All reports
        // failed, check connection and try again" and renders NO report content; its freshness chip
        // still reads "Live - contacts refreshed on load, history on load" because contacts and history
        // are REST GETs that genuinely did load (only WRITES are held). So CLAIMS_LIVE matched, nothing
        // matched NAMES_STORED, and the verdict read "the fallback engaged silently and the person is
        // reading stored numbers as live ones" - about a page that had just told them, in a sentence,
        // that the thing which failed had failed. The oracle's whole failure mode is a person mistaking
        // stored figures for current ones; an announcement of the failure is precisely what prevents
        // that, so it settles the oracle the same way a stored-source chip does.
        const announced = ANNOUNCES_FAILURE.test(chipText);
        // ★AND LOOK WHERE AN ANNOUNCEMENT ACTUALLY LIVES, not only in the freshness chips. Measured:
        // project-manager renders MORE with the primary down (1525 -> 1738 chars) because it ADDS an
        // error surface - yet the chip scan saw only "Live · refreshed on load" and the verdict called
        // it a silent fallback. Scoped to alert/status roles and toast/error hosts on purpose: a
        // body-wide keyword match reads the page's own marketing copy and manufactures the opposite
        // mistake, which this bank has already recorded once.
        const collected = await page.evaluate(() => (window.__whAlerts || []).join(' | ').slice(0, 600))
          .catch(() => '');
        const alerted = collected + ' | ' + await page.evaluate(() => {
          const SEL = '[role="alert"], [role="status"], [aria-live], .toast, .hive-toast, .toast-text,'
            + ' [class*="error"], [id*="error"], [class*="empty"], [class*="fail"]';
          const vis = (el) => {
            const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
            return r.width > 2 && r.height > 2 && cs.display !== 'none' && cs.visibility !== 'hidden';
          };
          return [...document.querySelectorAll(SEL)].filter(vis)
            .map((el) => (el.textContent || '').trim()).filter(Boolean).join(' | ').slice(0, 400);
        }).catch(() => '');
        rec.alertText = alerted.slice(0, 160);
        const says = announced || ANNOUNCES_FAILURE.test(alerted);
        const claimsLive = CLAIMS_LIVE.test(chipText) && !named && !says;
        rec.announcesFailure = says;
        rec.ok = named || says;
        rec.why = (named || says)
          ? 'the primary was answered 500 ' + edgeDown + ' time(s), the surface still shows '
            + s.nums + ' figures, AND is honest about it - it either names them as stored or states '
            + 'outright that the primary failed: '
            + JSON.stringify(chipText.slice(0, 130))
          : claimsLive
            ? 'the primary was down and the surface still presents ' + s.nums + ' figures as CURRENT: '
              + JSON.stringify(chipText.slice(0, 130)) + ' - the fallback engaged silently and the '
              + 'person is reading stored numbers as live ones'
            : 'the primary was down, ' + s.nums + ' figures are still on screen, and nothing names the '
              + 'source they came from: ' + JSON.stringify(chipText.slice(0, 130) || '(no chip)');
      }
    } catch (e) {
      rec.ok = null; rec.why = 'could not measure: ' + String(e.message || e).slice(0, 120);
    }
    await page.close(); await ctx.close();
    out.pages.push(rec);
    console.log('  ' + (rec.ok === null ? 'UNGRADED' : rec.ok ? 'PASS    ' : 'FAIL    ')
      + ' ' + name.padEnd(19) + ' ' + (rec.why || '').slice(0, 92));
  }
  await browser.close();
  writeFileSync(path.join(ROOT, 'fallback_engaged_report.json'), JSON.stringify(out, null, 1));
  const g = out.pages.filter((p) => p.ok !== null);
  // gate promotion 2026-08-21: a gate that cannot fail is not a gate. (The exit line must sit BELOW
  // the const it reads - the TDZ crash that broke prove_source_chip's --gate runs, third instance.)
  if (process.argv.includes('--gate')) process.exitCode = g.filter((p) => !p.ok).length ? 1 : 0;
  console.log('\n  ' + g.filter((p) => p.ok).length + ' pass | ' + g.filter((p) => !p.ok).length
    + ' fail | ' + (out.pages.length - g.length) + ' ungraded');
  console.log('  NO WRITE LANDED: the edge was stubbed 500 and every mutating REST call was held.');
};
run().catch((e) => { console.error(e); process.exit(1); });
