// prove_failure_injection.mjs — CC failure-injection over the 20 product pages the marketplace spec
// never reaches: a failed read must render a FAILURE, never an EMPTINESS.
//
// WHY THIS EXTENDS tests/failure-injection.spec.ts INSTEAD OF REPLACING IT. That spec already implements
// this family properly — the oracle-is-a-difference discipline, the product-harvested vocabulary, the
// refusal to grade a surface whose healthy load showed no rows. It covers 7 marketplace-side surfaces.
// CC in the page bank is 22 pages, so ~20 of them have never been injected at all. Same oracle, wider
// roster; its FAILURE/EMPTY vocabulary is IMPORTED from session_signals.mjs rather than re-typed, because
// a third copy of a predicate is what made two provers disagree about `analytics` and created that module.
//
// ★ THE INJECTION METHOD RECONCILES TWO RULES THAT LOOK CONTRADICTORY, and getting this wrong makes the
// whole family worthless — a failure-injection oracle that does not inject reports the most convincing
// false findings available, because "the page said nothing about the error" is exactly what a page with
// NO error would say.
//   · The spec's note: replacing `window.fetch` AFTER load never fires, because supabase-js captures
//     `fetch` when the client is CONSTRUCTED. It therefore uses `page.route`.
//   · This project's own lesson: `page.route` is bypassed by a warm SERVICE WORKER serving from cache,
//     which is how an earlier failure probe measured nothing while reporting success.
// Both are true, and the difference is WHEN THE PATCH LANDS. `addInitScript` runs before any page script,
// so the client is constructed around the patched fetch — it is not a "late override" — and it sits above
// the service worker rather than below it. Verified today on the sibling `why_refused` oracle, which
// counted 8-42 intercepted calls per page.
// AND IT COUNTS ITS OWN HITS REGARDLESS: a page where the counter reads zero is UNGRADED, never judged.
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';
import { FAILURE_SRC, EMPTY_SRC } from './session_signals.mjs';
// ★ SOME PAGES ARE NOT THEMSELVES WITHOUT A URL PARAMETER. project-report returns early at :344
// unless `?project_id=` is present, so a bare walk never runs loadAndRender() and never paints the
// skeleton this prover's fail_slow mode goes looking for. Walked bare it reported "NO busy indicator
// … the person is left looking at a still page"; walked with the id, the same instant shows FIVE
// (wh-skeleton, wh-skeleton-row…). The page was never the problem — the URL was.
import { pageUrl, ungradableReason } from './page_query.mjs';
// ★ V2 IS A DIFFERENT VIEW, NOT A SECOND READING OF V1. The dialog/section openers live in the shared
// registry so this prover cannot drift from the four that already drive them; each entry's open path was
// READ FROM SOURCE rather than matched by label. 17 of 22 V2 targets are drivable read-only; the other
// five carry a recorded reason (notDrivable / unreachable / signedOut) and are reported UNGRADED rather
// than quietly dropped, so the denominator stays honest.
import { TARGETS } from './dialog_targets.mjs';

// ★ REFUSE TO RUN ON A SOURCE FILE THAT CONTAINS CONTROL BYTES, because that is how this oracle produced
// SILENT PASSES. Editing this file through nested quoting layers (bash heredoc → Python → JS → regex) five
// times today turned an intended `\b` into a literal BACKSPACE (0x08). Once, that landed inside the
// null-field detector:
//     const raw = /<BS>(null|undefined)<BS>/i.exec(txt)
// which can never match, so `fail_null_field` reported "no raw null reached the screen" on every page while
// checking nothing at all. A false RED gets triaged; a false GREEN gets banked and believed — this is the
// more dangerous direction, and it is invisible in an editor because the byte does not render.
// A regex literal cannot be mis-escaped, but the FILE can still be corrupted by the tooling that writes it,
// so the check is on the bytes rather than on the discipline.
// fileURLToPath, not a hand-rolled pathname strip: this project lives under "Industry 4.0/AI Maintenance
// Engineer/Self-learning Road-Map/Build & Sell with Claude Code/…", so the URL form percent-encodes every
// space and the naive version threw ENOENT before it could check anything.
import { readFileSync as _readSelf } from 'fs';
import { fileURLToPath as _selfPath } from 'url';

// ★PROCESS DEADLINE, a BACKSTOP to the per-read watchdog below. read() is raced at 90s, which
// bounds every page read -- but NOT the parts outside it: signIn(), browser launch, context
// creation, browser.close(). A hang there escapes the race entirely, and that is how suite_v4
// stopped at 584 of 585 verdicts with 0.30 CPU-seconds across every node+chrome process.
// SIZING: 22 pages x (7 modes + 1 healthy) = 176 reads. Typical ~20s each (~1h); the per-read
// race caps the pathological case at 176 x 90s = 4.4h. 2h sits above a normal run and below the
// bounded worst case, so this fires only for a hang the race cannot see.
// .unref() so it never delays a clean finish -- VERIFIED: with an open handle (a live browser) it
// fires and exits 3; with none, Node self-exits 13 on the unsettled await. Either way the suite
// advances instead of stalling.
const WATCHDOG_MS = 7200_000;
setTimeout(() => {
  console.error(`WATCHDOG: exceeded ${WATCHDOG_MS}ms -- HUNG outside the per-read race (signIn / browser lifecycle).`);
  process.exit(3);
}, WATCHDOG_MS).unref();
{
  const bytes = _readSelf(_selfPath(import.meta.url));
  const bad = [];
  for (const b of bytes) {
    if (b < 9 || (b > 10 && b < 13) || (b > 13 && b < 32)) { if (!bad.includes(b)) bad.push(b); }
  }
  if (bad.length) {
    console.error(`  FATAL — this file contains control byte(s) ${bad.join(', ')}. An escape was eaten by `
      + 'the tooling that wrote it (a `\\b` becoming 0x08 is the usual one), which silently disables the '
      + 'regex it lands in. Refusing to run rather than reporting on a detector that cannot fire.');
    process.exit(2);
  }
}

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const GATE = args.includes('--gate');
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();
const VIEW = (() => { const i = args.indexOf('--view'); return i >= 0 ? args[i + 1] : 'V1'; })();
const OUT = ONE ? 'failure_injection.partial.json'
  : (VIEW === 'V2' ? 'failure_injection_v2_report.json' : 'failure_injection_report.json');

// The V2 target for a page, or null. `kind: 'section'` entries are regions already on the loaded page
// (mayStartOpen) — no open step, but the read still SCOPES to them.
const v2Target = (page) => TARGETS.find((t) => t.page === page && t.view === 'V2') || null;

/** Open the V2 view if it needs opening. Returns {ok, note} — a failure is UNGRADED, never a defect. */
async function openV2(page, t) {
  if (!t) return { ok: false, note: 'no V2 target registered for this page' };
  if (t.unreachable) return { ok: false, note: 'registry records this control as VERIFIED unreachable' };
  if (t.notDrivable) return { ok: false, note: 'registry records no read-only path in' };
  if (t.signedOut) return { ok: false, note: 'this view exists only for a signed-out visitor' };
  try {
    // ★ `pre` IS A STRING OF PAGE JS, NOT A FUNCTION. Calling it as `t.pre(page)` throws TypeError,
    // which this function's own try/catch then reports as "open threw" — so the three targets that
    // NEED a precondition (logbook, asset-hub, project-manager) came back UNGRADED, and the run looked
    // like a reachability limit rather than my bug. A guard that converts a coding error into a tidy
    // "not reachable" verdict is the most expensive kind: it reads as a fact about the product.
    if (t.pre) { await page.evaluate(t.pre); await page.waitForTimeout(1400); }
    if (t.openBy === 'click') {
      const el = await page.$(t.opener);
      if (!el) return { ok: false, note: `opener ${t.opener} absent or not rendered` };
      await el.click({ timeout: 5000 });
      await page.waitForTimeout(1500);
    } else if (t.openBy === 'fn') {
      await page.evaluate((fn) => { // eslint-disable-next-line no-eval
        eval(fn); }, t.fn);
      await page.waitForTimeout(1500);
    }
    // mayStartOpen sections need no step; confirm the element is actually THERE either way, because a
    // scoped read against a missing element would silently fall back to <body> and re-measure V1.
    const present = await page.evaluate((sel) => !!document.querySelector(sel), '#' + t.modal);
    return present ? { ok: true, note: `#${t.modal} present` }
                   : { ok: false, note: `#${t.modal} not in the DOM after the open step` };
  } catch (e) {
    return { ok: false, note: `open threw: ${String(e.message || e).slice(0, 60)}` };
  }
}

// The 20 the marketplace spec does not cover (it already walks community + public-feed).
const PAGES = ['index', 'hive', 'logbook', 'inventory', 'pm-scheduler', 'project-manager', 'dayplanner',
  'asset-hub', 'analytics', 'alert-hub', 'skillmatrix', 'shift-brain', 'voice-journal', 'assistant',
  'achievements', 'engineering-design', 'resume', 'report-sender', 'project-report', 'analytics-report',
  // ★community and public-feed were absent from this roster. public-feed is the ANON surface - the
  // one place a failed read is most likely to be mistaken for 'nothing here yet' - so its absence was
  // the least affordable. A roster is a claim about scope; an incomplete one makes a green look total.
  'community', 'public-feed'];

// Each mode fails the READ in a different way. `fail_offline` is a rejection rather than a status, because
// that is what a dead network actually looks like to fetch — a page that only handles non-2xx statuses
// still breaks on it, and telling those two apart is the point of having both.
// EACH MODE ALSO CARRIES ITS OWN PASS CONDITION, because "did a failure message appear?" is the right
// question for only four of the seven. A slow read that eventually succeeds SHOULD NOT say anything
// failure-shaped — demanding that would be demanding a lie — and a row whose field is null is not an
// error at all, it is a value the page has to render honestly. Using one assertion for all seven is how a
// family looks green while asserting the wrong thing on three of its members.
const MODES = {
  fail_500:     { kind: 'status', status: 500, body: '{"message":"internal server error"}', want: 'says' },
  fail_401:     { kind: 'status', status: 401, body: '{"message":"JWT expired","code":"PGRST301"}', want: 'says' },
  fail_timeout: { kind: 'hang', want: 'says' },
  fail_offline: { kind: 'reject', want: 'says' },
  // A TRUNCATED BODY is what a dropped connection mid-transfer actually looks like: a 200 with JSON that
  // does not parse. The client raises a parse error, and the page must treat that as a failure rather
  // than as "no rows".
  fail_partial: { kind: 'status', status: 200, body: '[{"id":"a","name":"tru', want: 'says' },
  // A SLOW BUT SUCCESSFUL read. The page must show it is WORKING — a skeleton, a spinner, a busy state —
  // and must NOT claim failure, because nothing failed. Sampled mid-flight, which is the only moment the
  // answer exists.
  fail_slow:    { kind: 'slow', delay: 6000, want: 'busy-then-content' },
  // NULLS IN FIELDS THE PAGE RENDERS. Not an error — a value. The page must not print the word `null`,
  // `undefined` or `NaN` at a person, which is the whole oracle.
  fail_null_field: { kind: 'nulls', want: 'no-raw-null' },
};

const inject = (mode) => `(() => {
  // ★ SHORTEN THE PLATFORM'S OWN TIMEOUT RATHER THAN OUT-WAITING IT. utils.js:703 reads
  // \`window.WH_DB_TIMEOUT_MS || 45000\` and says outright "tune via window.WH_DB_TIMEOUT_MS", so this is
  // configuring a documented knob, not faking behaviour. Without it a hang test must idle 45s PER PAGE to
  // reach the transport abort — and the first two versions of this prover instead sampled at 9s and 19s
  // and reported "the page said NOTHING about it", which is a true statement about an instant nobody
  // experiences and a false one about the product.
  // (The finer 15s bound, whQueryTimeout, is adopted by only 6 surfaces — community, public-feed and the
  // four marketplace pages — so on the 20 pages this prover covers, 45s IS the only bound.)
  if (${mode && mode.kind === 'hang' ? 'true' : 'false'}) window.WH_DB_TIMEOUT_MS = 4000;
  window.__whInjHits = 0;
  const of = window.fetch;
  window.fetch = function (u, o) {
    const s = typeof u === 'string' ? u : (u && u.url) || '';
    if (s.includes('/rest/v1/') || s.includes('/rpc/')) {
      window.__whInjHits++;
      ${mode.kind === 'status'
        ? `return Promise.resolve(new Response(${JSON.stringify(mode.body)}, { status: ${mode.status},
             headers: { 'Content-Type': 'application/json' } }));`
        : mode.kind === 'slow'
          // A REAL response, just late. The page must show it is working and must NOT claim failure.
          ? `return new Promise((res) => setTimeout(() => res(of.apply(this, arguments)), ${mode.delay}));`
        : mode.kind === 'nulls'
          // Let the REAL response through, then null every field of every row except the id. This is a
          // value problem, not a transport problem, so the request must genuinely happen — synthesising
          // rows here would test this stub's idea of the schema instead of the page's real data.
          ? `return of.apply(this, arguments).then(async (r) => {
               try {
                 const j = await r.clone().json();
                 if (!Array.isArray(j) || !j.length) return r;
                 const nulled = j.map((row) => {
                   const out = {};
                   for (const k of Object.keys(row)) out[k] = /^id$|_id$/.test(k) ? row[k] : null;
                   return out;
                 });
                 return new Response(JSON.stringify(nulled), { status: r.status,
                   headers: { 'Content-Type': 'application/json' } });
               } catch (e) { return r; }
             });`
        : mode.kind === 'reject'
          ? `return Promise.reject(new TypeError('Failed to fetch'));`
          // A hang, not a rejection — the page must show its own TIMEOUT behaviour, not its error path.
          // ★ AND IT MUST HONOUR THE ABORT SIGNAL, which the first version did not. utils.js wraps every
          // read in an AbortController (_timeoutFetch, :703-714) and aborts at WH_DB_TIMEOUT_MS. A real
          // fetch rejects when that signal fires; a stub that returns a bare timer ignores it, so the
          // platform's own timeout became a no-op and the page sat silent forever — which the oracle then
          // reported as "the page said NOTHING about it". The stub was suppressing the very mechanism
          // under test. Emulating fetch means emulating its cancellation, not just its latency.
          : `return new Promise((res, rej) => {
               const t = setTimeout(() => res(new Response('{}', { status: 200,
                 headers: { 'Content-Type': 'application/json' } })), 60000);
               const sig = o && o.signal;
               if (sig) {
                 if (sig.aborted) { clearTimeout(t); rej(sig.reason || new DOMException('Aborted', 'AbortError')); }
                 else sig.addEventListener('abort', () => { clearTimeout(t);
                   rej(sig.reason || new DOMException('Aborted', 'AbortError')); }, { once: true });
               }
             });`}
    }
    return of.apply(this, arguments);
  };
})()`;

const READ = ({ failSrc, emptySrc, scopeSel }) => {
  const F = new RegExp(failSrc, 'i');
  const E = new RegExp(emptySrc, 'i');
  const vis = (el) => {
    const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  // ★ V2 MUST BE READ INSIDE ITS OWN ELEMENT, or it is not a second view — it is V1 measured twice.
  // This platform has already banked 14 V2 rows carrying V1's reading, by selecting rows on the oracle
  // name alone. Here the failure question is about a REGION: when the read behind the AMC card, the
  // contacts list, or the exec summary fails, does THAT BLOCK say so? Reading document.body would let
  // a page-level notice elsewhere on the screen satisfy a claim about the block, and every V2 cell
  // would inherit V1's verdict for free.
  const root = scopeSel ? document.querySelector(scopeSel) : null;
  const scope = root || document.body;
  const txt = ((scope.innerText || scope.textContent) || '').replace(/\s+/g, ' ').trim();
  // Element queries scope to the same root, for the same reason the text does: a shimmer elsewhere on
  // the page is not this block showing that IT is working.
  const skel = [...scope.querySelectorAll('[class*="skeleton"], [class*="shimmer"], .wh-list-skeleton')]
    .filter(vis).length;
  const m = F.exec(txt); const e = E.exec(txt);
  // A RAW NULL IS A LEAK OF THE DATA LAYER INTO A SENTENCE. Word-bounded so "Nullarbor" or a part code
  // containing "nan" cannot trip it, and NaN is matched case-sensitively because that is how JS prints it.
  const raw = /\b(null|undefined)\b/i.exec(txt) || /\bNaN\b/.exec(txt);
  // ★ A WAIT STATE IS OFTEN JUST A SENTENCE, and matching only CLASS names missed it. pm-scheduler shows
  // `<div id="dash-loading">Loading assets...</div>` — the word is in the ID, and the classes are pure
  // Tailwind utilities. The first version reported "NO busy indicator" for a page that was saying
  // "Loading assets..." in plain English, which would have banked a false red on a page doing the right
  // thing. So: id as well as class, aria-busy, and the TEXT itself — because the person reads the
  // sentence, not the attribute.
  // ★ THIRD WIDENING, THIRD TIME THE PRODUCT WAS RIGHT AND THE ORACLE WAS NARROW. After the pm-scheduler
  // case above (the wait state was a SENTENCE) came this one: assistant.html:759 calls
  // addTypingIndicator() before its await and removeTypingIndicator() after — a `#typing-indicator`
  // holding three `.typing-dot` spans on a `typing-bounce` animation. That is not a workaround, it is
  // THE idiomatic busy affordance for a chat; a spinner in a message thread would be the odd choice.
  // The oracle reported "NO busy indicator … the person is left looking at a still page" about a page
  // animating three dots at them. Tailwind's `animate-pulse` / `animate-spin` / `animate-bounce` are
  // here for the same reason: this codebase styles with utilities, so the affordance often lives in a
  // utility class rather than a semantic one.
  const busyEls = [...scope.querySelectorAll(
    '[class*="skeleton"], [class*="shimmer"], [class*="spinner"], [class*="loading"], [id*="loading"],'
    + ' [id*="skeleton"], [id*="spinner"], [aria-busy="true"], progress, [role="progressbar"],'
    + ' [id*="typing"], [class*="typing"],'
    + ' [class*="animate-pulse"], [class*="animate-spin"], [class*="animate-bounce"]')]
    .filter(vis);
  // `checking` added 2026-08-15, and the provenance matters: report-sender's pending-state fix says
  // "Checking your saved contacts…", which is the right sentence for that card — it names WHAT is being
  // waited on, which "Loading…" does not. The oracle knowing only four verbs then failed the page for
  // using a fifth. That is the fifth time this detector's vocabulary has been narrower than the product
  // (a sentence in an id, an abbreviation, a typing indicator, a utility class, now a verb), so the
  // rule stands: harvest the phrasing a REAL page uses; never make the page say the oracle's words.
  const busyText = [...scope.querySelectorAll('*')].filter((el) => !el.children.length && vis(el)
    && /^(loading|loading\.\.\.|loading…|please wait|working|fetching|checking)\b/i.test((el.innerText || '').trim()));
  const busy = new Set([...busyEls, ...busyText]).size;
  return { chars: txt.length, saysFailure: !!m, failureQuote: m ? txt.slice(Math.max(0, m.index - 40),
             m.index + m[0].length + 70) : null,
           saysEmpty: !!e, emptyQuote: e ? e[0] : null, visibleSkeletons: skel,
           rawNull: raw ? txt.slice(Math.max(0, raw.index - 45), raw.index + 45) : null, busy };
};

// ★WATCHDOG. This prover HANGS the whole suite without it, and it did: suite_v4 stopped at 584 of
// 585 verdicts on this gate, 17 minutes with no log line and 0.30 CPU-seconds across every node and
// chrome process -- idle, not slow. Every individual await here is bounded (goto 25s, click 5s) but
// page.evaluate() has NO default timeout in Playwright, and this prover deliberately stubs fetch to
// HANG. When the page's own JS awaits that stubbed read inside an evaluate, the evaluate never
// settles and neither does the suite. A promise that never settles is invisible: no error, no
// output, no exit.
// A stuck target must be UNGRADED, never a hang -- the same posture this prover already takes for a
// V2 view it cannot reach. 90s is ~3x the slowest healthy read observed (goto 25s + settle 3.5s +
// drive), so a timeout here means stuck, not slow.
const READ_BUDGET_MS = 90_000;
async function read(ctx, page_, mode) {
  let _t0;
  const _watchdog = new Promise((_, rej) => {
    _t0 = setTimeout(() => rej(new Error(`read() exceeded ${READ_BUDGET_MS}ms (page=${page_}, mode=${mode ? mode.kind : 'healthy'})`)), READ_BUDGET_MS);
  });
  try {
    return await Promise.race([_readInner(ctx, page_, mode), _watchdog]);
  } finally {
    clearTimeout(_t0);
  }
}

async function _readInner(ctx, page_, mode) {
  const page = await ctx.newPage();
  if (mode) await ctx.addInitScript(inject(mode));
  await page.goto(pageUrl(ORIGIN, page_), { waitUntil: 'domcontentloaded', timeout: 25000 });
  // V2: reach the view first, and read INSIDE it. If it cannot be reached, say so and grade nothing.
  const _t = VIEW === 'V2' ? v2Target(page_) : null;
  let scopeSel = null;
  if (VIEW === 'V2') {
    await page.waitForTimeout(3500);           // let the page settle before driving its opener
    const opened = await openV2(page, _t);
    if (!opened.ok) { await page.close(); return { unreachable: opened.note }; }
    scopeSel = '#' + _t.modal;
  }
  // ★ THE WAIT MUST OUTLAST THE PAGE'S OWN TIMEOUT, or the oracle measures its own impatience.
  // `whQueryTimeout` (utils.js:1785) bounds every read at 15000ms and then resolves a synthetic
  // {code:'TIMEOUT'} error that the page renders through whReadError. Waiting 9s — as the first version
  // did — samples the page BEFORE that fires and reports "said NOTHING about it", which is a true
  // statement about an instant the person never sees and a false one about the product. 19s gives the
  // 15s budget room to fire and the resulting message room to render.
  // ★ AT V2 THE MID-FLIGHT SAMPLE WAS LANDING AFTER THE WAIT ENDED. The V2 path spends 3.5s letting
  // the page settle, then opens the view, then samples 2.5s later — about 6.2s in, which is exactly
  // when a 6s-delayed read resolves. Measured on report-sender: #contacts-list holds four VISIBLE
  // skeleton rows from ~1s to ~6s and none at 6.2s, so the prover reported "NO busy indicator" about a
  // region that had been showing one for five seconds. That is the oracle measuring its own latency,
  // the same error as sampling a page before its timeout fires — and it was on course to file six
  // false findings across the held rows.
  // Widening the injected delay (not shortening the settle) keeps the open step unhurried while
  // putting the sample firmly inside the wait.
  let mid = null;
  if (mode && mode.kind === 'slow') {
    // SAMPLE WHILE IT IS STILL SLOW. "Does the page show it is working?" is a question about the middle
    // of the request, and by the time the data lands the answer has been erased. Reading only the final
    // state would score a page that showed a blank screen for six seconds identically to one that showed
    // a skeleton — which is the entire difference this oracle exists to measure.
    await page.waitForTimeout(2500);
    mid = await page.evaluate(READ, { failSrc: FAILURE_SRC, emptySrc: EMPTY_SRC, scopeSel });
    await page.waitForTimeout(6000);
  } else {
    await page.waitForTimeout(mode && mode.kind === 'hang' ? 11000 : 5000);
  }
  const r = await page.evaluate(READ, { failSrc: FAILURE_SRC, emptySrc: EMPTY_SRC, scopeSel });
  // ★ AT V2, ALSO ASK WHAT THE *PAGE* SAID. "The region said nothing" is only half a verdict: a block
  // that stays silent while a page-level notice explains the failure is a DIFFERENT (and much smaller)
  // defect from one where nobody tells the person anything at all. The first V2 sweep returned 49
  // failures out of 84 graded, which is the shape that should be distrusted on sight — and most of them
  // were "said NOTHING" without this second reading to place them. Recording both lets the triage
  // separate "not told" from "told, but not here"; banking them as one number would manufacture
  // findings at scale, which is precisely what this family's hold rule exists to prevent.
  if (scopeSel) {
    const outer = await page.evaluate(READ, { failSrc: FAILURE_SRC, emptySrc: EMPTY_SRC, scopeSel: null });
    r.pageSaysFailure = outer.saysFailure;
    r.pageFailureQuote = outer.failureQuote;
  }
  if (mid) r.mid = mid;
  const hits = mode ? await page.evaluate(() => window.__whInjHits ?? null) : null;
  await page.close();
  return { ...r, hits };
}

const browser = await chromium.launch();
const results = [];
for (const p of (ONE ? [ONE.replace(/\.html$/, '')] : PAGES)) {
  // HEALTHY CONTROL FIRST. Without it there is no delta: a page whose ordinary copy already contains
  // "try again" would pass every mode for free, and a page that renders nothing when healthy has no
  // "empty vs error" distinction to make.
  // A page that needs a parameter we could not resolve is UNGRADED, never walked bare. Grading the
  // "nothing specified" shell produces a verdict about a page nobody visits.
  const blocked = ungradableReason(p);
  if (blocked) {
    for (const name of Object.keys(MODES)) results.push({ page: p, mode: name, ok: null, verdict: blocked });
    console.log(`  ${p}: UNGRADED — ${blocked}`);
    continue;
  }
  let healthy = null;
  try {
    const c0 = await browser.newContext({ viewport: { width: 390, height: 844 } });
    // A SWALLOWED SIGN-IN FAILURE FABRICATES DEFECTS. This was `.catch(() => {})`: if sign-in
    // failed the sweep continued UNAUTHENTICATED, every auth-gated page redirected to index, and the
    // prover measured a redirect stub — reporting "N call(s) failed and the page said NOTHING about
    // it" for pages that were never loaded. Measured 2026-08-20: analytics-report (369 chars) and
    // engineering-design (1845 chars) both reported that way, and both simply redirect when signed
    // out. Abort instead: no result is honest, a fabricated one is not.
    await signIn(c0, 'supervisor').catch((e) => {
      throw new Error(`sign-in failed, aborting: every auth-gated page would redirect and be reported as silently failing (${String(e).slice(0, 120)})`);
    });
    healthy = await read(c0, p, null);
    await c0.close();
  } catch (e) { healthy = { error: String(e.message || e).slice(0, 100) }; }

  for (const [name, _mode0] of Object.entries(MODES)) {
    // ★ ONE NAME, TWO OBJECTS — the subtlest bug of this arc. read() applied the V2 slow-delay override
    // to its OWN parameter (`mode = { ...mode, delay: 14000 }`), which correctly changed what was
    // injected — but the VERDICT is composed out here, against the loop's original MODES entry, so it
    // kept reporting "a 6s read" while the page was actually waiting 14. I read that sentence as proof
    // the override had not applied and re-tested three times before noticing the two bindings.
    // Overriding HERE gives the injection and the verdict a single source, so the number in the
    // sentence is by construction the number that ran.
    const mode = (VIEW === 'V2' && _mode0.kind === 'slow') ? { ..._mode0, delay: 14000 } : _mode0;
    const rec = { page: p, mode: name };
    try {
      if (healthy && healthy.unreachable) {
        // The view itself could not be reached. Every mode is UNGRADED with the REASON, because a
        // dialog nobody could open is not a page that handles failure badly — and dropping these
        // silently would shrink the denominator while the board still read "all graded".
        rec.ok = null;
        rec.verdict = `UNGRADED (V2 not reached): ${healthy.unreachable}`;
      } else if (!healthy || healthy.error) {
        rec.ok = null; rec.verdict = `healthy control unavailable (${healthy?.error || 'n/a'}) — no delta`;
      } else if (healthy.saysFailure) {
        rec.ok = null;
        rec.verdict = 'this page ALREADY says something failure-shaped when healthy '
          + `("${(healthy.failureQuote || '').slice(0, 50)}") — the signal cannot be attributed`;
      } else {
        const c = await browser.newContext({ viewport: { width: 390, height: 844 } });
        await assertSignedIn(signIn(c, 'supervisor'));
        const bad = await read(c, p, mode);
        await c.close();
        if (bad && bad.unreachable) {
          rec.ok = null;
          rec.verdict = `UNGRADED (V2 not reached under ${name}): ${bad.unreachable}`;
          results.push(rec);
          continue;
        }
        rec.healthyChars = healthy.chars; rec.badChars = bad.chars; rec.hits = bad.hits;
        if (!bad.hits) {
          rec.ok = null;
          rec.verdict = `the injection intercepted ${bad.hits === null ? 'nothing (it never ran)' : '0 calls'}`
            + ' — no read was failed, so nothing about this page\'s failure handling was exercised';
        } else if (VIEW === 'V2' && mode.want === 'says' && !bad.saysFailure && bad.pageSaysFailure) {
          // ★ A PAGE-LEVEL NOTICE IS THIS PLATFORM'S DELIBERATE DESIGN, NOT A DEFECT — and treating it
          // as one would have produced 43 findings against a decision already on the record. The
          // roadmap states it outright for the sibling permission notice: "The notice is PAGE-LEVEL,
          // not panel-level … per-panel attribution is a further improvement, NOT A CLAIM OF THIS ROW."
          // So the question this oracle actually asks is narrower, and it is the one that matters:
          // does the block render a FALSE EMPTINESS while its read failed? "No contacts saved yet"
          // over a failed read is a lie the person acts on; a BLANK block beside a page notice that
          // says the read failed is not — they have been told, and nothing false is on screen.
          if (bad.saysEmpty) {
            rec.ok = false;
            rec.verdict = `${bad.hits} call(s) failed and this VIEW rendered an EMPTINESS `
              + `("${String(bad.emptyQuote || '').slice(0, 40)}") while the page said the read failed. `
              + 'An empty state over a failed read is a false statement about the data, not a missing one.';
          } else {
            rec.ok = true;
            rec.verdict = `${bad.hits} call(s) failed; this view rendered NO false empty state and the `
              + `page announced the failure: "${String(bad.pageFailureQuote || '').slice(0, 60)}". `
              + 'Page-level rather than block-level notice is this platform\'s recorded design; per-panel '
              + 'attribution is a further improvement, not a claim of this row.';
          }
        } else if (mode.want === 'no-raw-null') {
          // Not an error path: the rows arrived, their fields are null, and the only question is whether
          // the page prints that at a person.
          if (bad.rawNull) {
            rec.ok = false;
            rec.verdict = `${bad.hits} row-set(s) returned with null fields and the page rendered the raw `
              + `value to the person: "...${bad.rawNull.trim()}..."`;
          } else {
            rec.ok = true;
            rec.verdict = `${bad.hits} row-set(s) returned with every non-id field null, and no raw `
              + 'null/undefined/NaN reached the screen';
          }
        } else if (mode.want === 'busy-then-content') {
          // Nothing failed here, so demanding a failure message would be demanding a lie. The page must
          // show it is WORKING mid-flight, and must not cry failure.
          const m2 = bad.mid || {};
          if (m2.saysFailure) {
            rec.ok = false;
            rec.verdict = `a merely SLOW read was reported as a failure while still in flight: `
              + `"${(m2.failureQuote || '').trim().slice(0, 70)}" — nothing had gone wrong`;
          } else if (!m2.busy && !m2.visibleSkeletons && healthy.chars > 0
                     && m2.chars === healthy.chars) {
            // ★SAME NO-SUBJECT RULE AS THE FAILURE MODES ABOVE. If the view renders byte-identically
            // while the reads are held, its display never consumed them - so there is no wait for it to
            // narrate, and demanding a spinner would be demanding an alarm about a background task the
            // person never asked for. Measured on engineering-design, whose calculators are entirely
            // client-side. Any shrinkage at all means content DID depend on the read, and then the
            // missing busy state is a real defect, which is why the equality test carries the guard.
            rec.ok = null;
            rec.verdict = `a ${(mode.delay / 1000).toFixed(0)}s read showed no busy indicator, but the `
              + `view rendered IDENTICALLY (${m2.chars} chars either way) - its display does not consume `
              + 'these reads, so there is no wait to narrate; NO SUBJECT rather than a defect';
          } else if (!m2.busy && !m2.visibleSkeletons) {
            rec.ok = false;
            // ★ THE VERDICT HARDCODED "6s" AND KEPT SAYING IT AFTER THE DELAY BECAME 14s FOR V2. I read
            // that string as evidence the override had not applied and re-tested twice before checking
            // the literal. A verdict that misreports its own METHOD is the same defect class this whole
            // family exists to catch, committed by the instrument: the number in the sentence must come
            // from the run, never from when the sentence was written.
            rec.verdict = `a ${(mode.delay / 1000).toFixed(0)}s read showed NO busy indicator at 2.5s `
              + `(${m2.chars} chars on screen) — the person is left looking at a still page with no sign `
              + 'anything is happening';
          } else {
            rec.ok = true;
            rec.verdict = `${m2.busy + m2.visibleSkeletons} busy indicator(s) visible mid-flight and no `
              + `false failure claim; content resolved after (${bad.chars} chars)`;
          }
        } else if (bad.saysFailure) {
          rec.ok = true;
          rec.verdict = `${bad.hits} call(s) failed and the page said so: "`
            + `${(bad.failureQuote || '').trim().slice(0, 80)}"`;
        } else if (bad.saysEmpty) {
          rec.ok = false;
          rec.verdict = `${bad.hits} call(s) failed and the page rendered EMPTINESS ("${bad.emptyQuote}") `
            + '— a person cannot tell "there is nothing here" from "this did not load", and one of those '
            + 'is false';
        } else if (bad.visibleSkeletons) {
          rec.ok = false;
          rec.verdict = `${bad.hits} call(s) failed and ${bad.visibleSkeletons} skeleton(s) are STILL `
            + 'shimmering — the page is telling the person it is loading something that will never arrive';
        } else if (healthy.chars > 0 && bad.chars === healthy.chars) {
          // ★A VIEW WHOSE DISPLAY DOES NOT DEPEND ON THE FAILING READS HAS NO SUBJECT FOR THIS ORACLE,
          // and calling that a defect demands an alarm about something the person never asked for.
          // engineering-design renders IDENTICALLY under a forced 500 - 1845 characters healthy, 1845
          // failed - because its calculators are pure client-side: recent calcs come from localStorage,
          // the counts are in-memory, and the reads that fail feed a HISTORY tab that already has its
          // own error-and-Retry path. Nothing was withheld, nothing was misrepresented, and there is no
          // emptiness pretending to be data. This is the same shape prove_quota_legible.mjs records as
          // `nonConstraining` for alert-hub's load-time orchestrator call.
          // The equality test is the whole guard: a byte-identical render is strong evidence the view
          // never consumed those rows, whereas ANY shrinkage means something DID disappear and the
          // silence is real. Recorded as no-subject (rail R10: declared-na needs a reason), never passed.
          rec.ok = null;
          rec.verdict = `${bad.hits} call(s) failed and the view rendered IDENTICALLY `
            + `(${healthy.chars} chars either way) - its display does not consume these reads, so there `
            + 'is nothing withheld for it to announce; NO SUBJECT rather than a defect';
        } else {
          rec.ok = false;
          rec.verdict = `${bad.hits} call(s) failed and the page said NOTHING about it `
            + `(${healthy.chars} chars healthy -> ${bad.chars} chars failed)`;
        }
      }
    } catch (e) { rec.ok = null; rec.error = String(e.message || e).slice(0, 120); }
    results.push(rec);
    console.log(`  ${(p + ' ' + name).padEnd(34)} ${rec.ok === true ? 'PASS' : rec.ok === false ? 'FAIL' : 'N/A '}`
      + `  ${String(rec.verdict || rec.error || '').slice(0, 76)}`);
  }
}
await browser.close();

const graded = results.filter((r) => r.ok !== null);
const bad = graded.filter((r) => !r.ok);
writeFileSync(OUT, JSON.stringify({
  totals: { cells: results.length, graded: graded.length, failing: bad.length,
            ungraded: results.filter((r) => r.ok === null).length },
  cells: results,
}, null, 1));
console.log(`\n  wrote ${OUT}`);
console.log(`  ${graded.length} of ${results.length} cell(s) graded · ${bad.length} failing`);
if (!graded.length) {
  console.log('  FAIL — NOTHING WAS MEASURED. Zero failures over an empty denominator is not a pass.');
}
if (GATE) process.exit(bad.length || !graded.length ? 1 : 0);
