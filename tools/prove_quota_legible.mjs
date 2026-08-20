// prove_quota_legible.mjs — CM `what_does_it_cost`, the QUOTA half: "quota and cost state are legible at
// the moment they constrain the action."
//
// WHY A DEDICATED PROVER. Most costs on this platform are visible before you act — stock on hand, XP,
// an exam pass mark. Model quota is different: it is invisible until you hit it, so the only honest way
// to test the disclosure is to INDUCE the constraint. Every AI/orchestrator invoke is answered 429 and
// the surface is read.
//
// ★THE DEFECT CLASS THIS EXISTS TO CATCH, found three times before this file was written:
//   assistant     — collapsed every gateway failure into a single `null`, then reported "timed out.
//                   Please retry on a faster connection."
//   shift-brain   — matched 429 with a network-error regex, so a rate limit read as "Shift planner is
//                   offline locally. Run npx supabase functions serve" (a dev command, to a supervisor).
//   report-sender — carried a COMMENT asserting invoke() parses the body on a non-2xx; it does not in
//                   this client version, so the toast fell through to "check connection and try again".
// One shape: a broad failure classifier swallowing a specific, actionable cause. All three told someone
// to fix their connection while the connection was fine and the service was busy. Waiting was the answer.
//
// ★SAMPLED ACROSS THE WINDOW, NEVER READ AT ITS END. These messages are toasts that live ~1s. A read at
// t+7000 saw a settled page and reported that shift-brain said NOTHING, while the message had been and
// gone. That mistake has now been made in four separate probes in this arc; here it is structural.
//
// ★AND THE CONTROL MAY BE HIDDEN. shift-brain's #generate-btn has offsetParent === null, so a
// text-matched button search finds nothing and reports an empty result — a probe that cannot REACH the
// control says nothing about the page. Selectors are dispatched in-page, visibility notwithstanding.
//
// A page whose action fires no edge invoke is UNGRADED: no quota is drawn, so there is nothing to be
// legible about, and failing it would be inventing a subject.
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

// ★PROCESS DEADLINE. This prover deliberately stubs writes with `new Promise(() => {})` -- a
// never-settling promise, which is the CORRECT semantic for blocking a write during a probe
// (rejecting would drive the page's error path; resolving 200 would make the page believe the
// write landed). But page.evaluate() has no default timeout in Playwright, so if the page's own
// JS awaits that stubbed write inside an evaluate, nothing ever settles and the whole SUITE
// stops. suite_v4 died exactly that way on prove_failure_injection: 584 of 585 verdicts, 17
// minutes of silence, 0.30 CPU-seconds across every node+chrome process. A promise that never
// settles is invisible -- no error, no output, no exit.
// .unref() so this never delays a clean finish; it only fires if we are STILL running at the
// deadline. Budget derived from THIS prover's own flow (~15 flows x ~47s worst case), not copied -- a constant borrowed
// from a prover with a different settle profile either fires spuriously or never fires.
const WATCHDOG_MS = 1200_000;
setTimeout(() => {
  console.error(`WATCHDOG: exceeded ${WATCHDOG_MS}ms without finishing -- treating as HUNG, not slow.`);
  process.exit(3);
}, WATCHDOG_MS).unref();

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

// ★RATE-LIMIT THE ACTION UNDER TEST, NOT THE PAGE'S PREREQUISITES. Blanket-429ing every invoke broke
// project-report before it could be measured: the page composes its report THROUGH an edge function, so
// with all invokes limited _projectCache never populated and the narrative button answered "Project not
// loaded yet" — a guard doing its job, reported as "this page draws no quota". A probe that starves the
// setup is measuring its own interference. `onlyBody` limits just the calls whose request body matches,
// so the load succeeds and only the action being graded meets the limit.
const FORCE_429 = (onlyBody) => {
  window.__q = { invokes: 0 };
  const of = window.fetch;
  window.fetch = function (input, init) {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    const method = String((init && init.method) || 'GET').toUpperCase();
    let bodyMatches = true;
    if (onlyBody) {
      let raw = '';
      try { raw = String((init && init.body) || ''); } catch (_) { raw = ''; }
      bodyMatches = new RegExp(onlyBody, 'i').test(raw);
    }
    if (/\/functions\/v1\//.test(url) && bodyMatches) {
      window.__q.invokes++;
      return Promise.resolve(new Response(
        JSON.stringify({ error: 'rate_limit_exceeded', message: 'Too many requests. Try again in 60 seconds.' }),
        { status: 429, headers: { 'Content-Type': 'application/json' } }));
    }
    // Never let a real write land while probing.
    if (/\/rest\/v1\/|\/rpc\//.test(url) && ['POST', 'PATCH', 'PUT', 'DELETE'].includes(method)) {
      return new Promise(() => {});
    }
    return of.apply(this, arguments);
  };
};

const NAMES_LIMIT = /too many|request limit|rate.?limit|limit reached|slow down|quota|try again in a|wait about/i;
const MISATTRIBUTES = /faster connection|check (your )?connection|offline locally|npx supabase|no internet|timed out/i;

const FLOWS = {
  'shift-brain':     { sel: '#generate-btn' },
  assistant:         { sel: '#send-btn', fill: ['#chat-input', 'quota legibility probe'] },
  'report-sender':   { sel: '#send-btn', pre: ['button:has-text("PM Overdue")'],
                       fill: ['#email-input', 'probe@example.com'] },
  // NO CLICK: alert-hub draws its orchestrator invoke ON LOAD, so the constraint is hit before anyone
  // touches anything. A prover that insists on pressing something would report this page as having no
  // control and grade nothing — but a person who opens the page IS the one who meets the limit.
  // ★NOT A CONSTRAINT, SO NOT GRADED — and this had to be encoded, because leaving it in produced an
  // UNSTABLE verdict (PARTIAL on one run, FAIL on the next) against a page that behaves correctly. The
  // page's own code says why: its load-time analytics-orchestrator call is a "background UPGRADE — the
  // stored brief is already shown (instant fallback) ... clear [the hint] when the live brief lands/fails".
  // A 429 there withholds NOTHING the person asked for, so there is no constraint to make legible, and a
  // prover that failed it would be demanding an alarm about a background task degrading as designed.
  // The oracle is legibility WHEN quota CONSTRAINS; this invoke does not.
  'alert-hub':       { onLoad: true, nonConstraining:
                       'its load-time orchestrator call is a background upgrade over an already-served '
                       + 'stored brief, so a rate limit withholds nothing the person asked for' },
  // The real control ids. My first attempt named #run-btn / #generate-btn, neither of which exists here,
  // so the page read as "control not present" — a probe naming the wrong button says nothing about it.
  analytics:         { sel: '#recompute-risk-btn, #refresh-btn' },
  // The mic. Its transcribe call is the quota draw, and it is reached only with a fake audio device —
  // tap to record, tap to stop, and the 429 lands on the transcription.
  'voice-journal':   { sel: '#mic-btn', preClicks: ['#mic-btn'], preWait: 2400, audio: true },
  // A LONGER SETTLE, because the first run clicked this before the report had loaded and the handler
  // early-returned — reported as "drew no edge invoke", which looked like a page with no quota to spend
  // when in fact the probe pressed too soon. #ai-narrative-btn does invoke project-orchestrator.
  'project-report':  { sel: '#ai-narrative-btn', url: '?project_id=853abed7-4a61-4bb4-b771-f0d2d0196490',
                       settle: 9000, onlyBody: 'narrative' },
};

// A fake microphone, for the one page whose quota draw is audio-triggered and otherwise unreachable.
const browser = await chromium.launch({ args: ['--use-fake-device-for-media-stream',
  '--use-fake-ui-for-media-stream', '--use-file-for-fake-audio-capture=.tmp/probe.wav%noloop'] });
const report = { ran: new Date().toISOString(), pages: {} };
for (const p of (ONE ? [ONE] : Object.keys(FLOWS))) {
  const flow = FLOWS[p];
  const rec = { page: p };
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 },
                                         permissions: ['microphone'] });
  await assertSignedIn(signIn(ctx, 'supervisor'));
  await ctx.addInitScript(FORCE_429, flow.onlyBody || null);
  const page = await ctx.newPage();
  try {
    // For an on-load page the message can appear DURING load, so nothing may be sampled after a settle —
    // navigate first, then start sampling immediately rather than after a fixed wait.
    await page.goto(`${ORIGIN}/${p}.html${flow.url || ''}`, { waitUntil: 'domcontentloaded', timeout: 25000 });
    if (!flow.onLoad) await page.waitForTimeout(flow.settle || 4200);
    for (const c of (flow.pre || [])) await page.click(c, { timeout: 5000 }).catch(() => {});
    for (const c of (flow.preClicks || [])) {
      await page.evaluate((sel) => { const e = document.querySelector(sel); if (e) e.click(); }, c).catch(() => {});
      if (flow.preWait) await page.waitForTimeout(flow.preWait);
    }
    if (flow.fill) await page.fill(flow.fill[0], flow.fill[1], { timeout: 5000 }).catch(() => {});
    await page.waitForTimeout(400);
    // ★THE BASELINE MUST NOT CONTAIN TOASTS, and mine did — which manufactured this session's only
    // remaining FAIL. `before` exists to stop the page's own static copy being credited as a response
    // (a guide sentence containing "rate limit" is not the page answering). But on an on-load page the
    // refusal toast is ALREADY on screen when the baseline is taken, so the identical post-press toast
    // was filtered out as "not fresh" and analytics was reported as saying NOTHING — while a direct
    // probe of the same page under the same 429 read "You have hit the AI rate limit. Wait a moment and
    // try again." A toast IS a response by construction, so no toast may ever enter the baseline.
    const before = await page.evaluate(() => {
      const SEL = '#toast, [id*="toast"], [class*="toast"], [role="status"], [role="alert"], [aria-live]';
      const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      const out = [];
      for (let n = w.nextNode(); n; n = w.nextNode()) {
        if (n.parentElement && n.parentElement.closest(SEL)) continue;   // a response, not a baseline
        const t = (n.textContent || '').trim();
        if (t) out.push(t);
      }
      return out.join(' ').replace(/\s+/g, ' ').trim();
    });
    // ★:has-text() IS A PLAYWRIGHT SELECTOR, NOT A CSS ONE. Passing it to querySelector threw
    // "Failed to execute 'querySelector'" and reported alert-hub and analytics as probe errors — a broken
    // probe reading as an unmeasurable page. Split: CSS parts are queried, text parts are matched in-page.
    const clicked = flow.onLoad ? '(load-time invoke, no press)' : await page.evaluate((raw) => {
      const parts = raw.split(',').map((x) => x.trim()).filter(Boolean);
      const byText = [];
      let el = null;
      for (const part of parts) {
        const m = part.match(/^(\w*):has-text\("(.+)"\)$/);
        if (m) { byText.push([m[1] || '*', m[2]]); continue; }
        try { el = document.querySelector(part); } catch (_) { el = null; }
        if (el) break;
      }
      if (!el) {
        for (const [tag, text] of byText) {
          const re = new RegExp(text, 'i');
          el = [...document.querySelectorAll(tag === '*' ? 'button, [role="button"]' : tag)]
            .find((e) => re.test((e.innerText || e.textContent || '').trim()));
          if (el) break;
        }
      }
      if (!el) return null;
      el.click();                       // dispatched in-page: a hidden control is still reachable
      return el.id || (el.innerText || '').trim().slice(0, 24) || raw;
    }, flow.sel);
    rec.clicked = clicked;
    // Sample throughout — the answer is a toast that fades.
    // ★THE LAST SAMPLE IS NOT THE ANSWER. `seen = fresh` overwrote on every tick, so whichever text
    // happened to be on screen at t+8s won — and once the baseline stopped swallowing live-region text,
    // voice-journal's persistent source chip ("Live · refreshed on load · ...") clobbered the rate-limit
    // sentence that had appeared seconds earlier, turning a PASS into a PARTIAL. What the page said over
    // the window is the UNION of what it showed, not its final frame.
    const seenSet = new Set();
    for (let i = 0; i < 32; i++) {
      const t = await page.evaluate(() => {
        const nodes = [...document.querySelectorAll(
          '#toast, [id*="toast"], [class*="toast"], [role="status"], [role="alert"], [aria-live]')];
        return nodes.filter((e) => {
          const s = getComputedStyle(e); const b = e.getBoundingClientRect();
          return s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0.05 && b.height > 0;
        }).map((e) => (e.innerText || '').trim()).join(' | ');
      });
      if (t) t.split(' | ').forEach((x) => { if (x && !before.includes(x)) seenSet.add(x); });
      await page.waitForTimeout(250);
    }
    const invokes = await page.evaluate(() => window.__q.invokes);
    const seen = [...seenSet].join(' | ');
    rec.invokes = invokes; rec.message = seen;
    if (flow.nonConstraining) {
      rec.status = 'N/A';
      rec.why = `no constraint to make legible: ${flow.nonConstraining}`;
    } else if (!clicked) { rec.status = 'UNGRADED'; rec.why = 'the control was not present on this page'; }
    else if (!invokes) { rec.status = 'UNGRADED'; rec.why = 'pressing it drew no edge invoke, so no quota is spent and there is nothing to be legible about'; }
    else if (!seen) { rec.status = 'FAIL'; rec.why = 'the request was rate-limited and the surface said NOTHING a person could read'; }
    else if (MISATTRIBUTES.test(seen) && !NAMES_LIMIT.test(seen)) {
      rec.status = 'FAIL';
      rec.why = `a rate limit was reported as a connection/availability problem: "${seen.slice(0, 110)}"`;
    } else if (NAMES_LIMIT.test(seen)) {
      rec.status = 'PASS'; rec.why = `names the limit: "${seen.slice(0, 110)}"`;
    } else {
      rec.status = 'PARTIAL'; rec.why = `said something, but it names neither the limit nor a wrong cause: "${seen.slice(0, 100)}"`;
    }
  } catch (e) { rec.status = 'UNGRADED'; rec.why = 'probe error: ' + String(e).slice(0, 80); }
  report.pages[p] = rec;
  console.log(`  ${p.padEnd(15)} ${String(rec.status).padEnd(9)} ${rec.why || ''}`.slice(0, 165));
  await ctx.close();
}
writeFileSync('quota_legible_report.json', JSON.stringify(report, null, 1));
const v = Object.values(report.pages);
console.log(`\n  wrote quota_legible_report.json — ${v.filter((x) => x.status === 'PASS').length} pass, `
  + `${v.filter((x) => x.status === 'FAIL').length} fail, ${v.filter((x) => x.status === 'N/A').length} n/a, `
  + `${v.filter((x) => x.status === 'UNGRADED').length} ungraded`);
console.log('  NO WRITE LANDED: every mutating REST call was held, and every edge invoke was answered 429 in-page.');
await browser.close();
