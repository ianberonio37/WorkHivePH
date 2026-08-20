// prove_journey.mjs — CN ux-journey, J1 `first_run_to_value` + J2 `repeat_visit`, across the 22 product
// pages × their 3 grounded journey personas.
//
// WHY THIS EXTENDS tests/ux-journeys.spec.ts RATHER THAN REPLACING IT. That spec already walks these two
// journeys, but only over 4 MARKETPLACE surfaces, and it carries two rails earned the hard way which this
// file keeps verbatim in spirit:
//   · every step asserts the TRANSITION, never that a control was clickable ("a click that changes NOTHING
//     logs as ok"). A control present, enabled, hit-testable and inert is a failure.
//   · NON-VACUITY: a journey that cannot be CONSTRUCTED fails; it never skips. A page that will not load,
//     or a persona that cannot be established, is a finding — not a quiet pass.
// The 22 product pages are a different roster with different personas, so the SURFACES table here is
// grounded from page_bank_anatomy/<page>.json `journey_personas` rather than invented.
//
// ★ THE TOOTH THIS ORACLE NEEDS THAT THE MARKETPLACE ONE DID NOT: A FIRST-RUN SCREEN CAN BE A LIE.
// `feedback_a_failed_read_offered_first_run_onboarding` records skillmatrix asking a worker to re-pick a
// discipline they had already chosen — because the READ had failed, and the page rendered its first-run
// onboarding as the fallback. To a naive "did the person reach something actionable?" check that scores
// as a PASS: there is content, there are buttons, there is a clear next step. It is the opposite of value
// — it is about to overwrite the person's real setup.
// So J1 does NOT credit "something actionable appeared". It requires that the page's own READS SUCCEEDED
// (no 4xx/5xx on a REST/RPC call, counted from the network, not guessed) BEFORE any onboarding screen may
// count as value. Onboarding after a failed read is recorded as a FAILURE with its status codes. That is
// the A16.P7 mechanism rule: credit the right cause, not merely the observed property.
//
// J2 `repeat_visit` asserts a returning person is not made to redo setup: the SECOND load of the same page
// in the same session must not demand a step the first one already took. Measured as a delta, because a
// page that always shows a picker is a different (and lesser) finding than one that shows it only after
// you have already answered it.
//
// NON-WRITING. Nothing is typed or submitted; localStorage is cleared only inside the throwaway context,
// and auth keys are preserved so the journey under test is a first-time SIGNED-IN person rather than the
// sign-in wall (the same reasoning the spec documents).
import { chromium } from 'playwright';
import { writeFileSync, readFileSync, existsSync } from 'fs';
import { signIn } from './live_page_journeys.mjs';
import { REASONED_EMPTY_SRC } from './session_signals.mjs';
import { TARGETS } from './dialog_targets.mjs';

// Which PAGE is this URL? Fragment first, then query, then the extension — in that order, because
// `index.html#evolution` does not end in `.html` and a `/\.html$/` strip leaves it mangled. Three
// copies of this line existed and all three had the bug: a page that sets a hash on load would read
// as REDIRECTED and bank a false bounce. One definition, for the same reason session_signals.mjs
// exists — a duplicated predicate is a bug with three places to hide.
const pageName = (u) => (String(u).split('/').pop() || '').split('#')[0].split('?')[0]
  .replace(/\.html$/, '');

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const GATE = args.includes('--gate');
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();
// Which journeys to walk this run. Default = all. `--journeys j4` re-walks one family without paying for
// the others, which matters when a single oracle is corrected and its rows have to be re-earned.
const ONLY = (() => {
  const i = args.indexOf('--journeys');
  return i >= 0 ? new Set(args[i + 1].toLowerCase().split(',').map((s) => s.trim())) : null;
})();
const wants = (j) => !ONLY || ONLY.has(j);
// ★ WHERE THE REPORT GOES, because a fixed filename let a one-page test DESTROY a 66-persona run.
// Both write `journey_report.json`; a `--page community` check finishing moments after the full walk
// overwrote it, and the structured data for 66 personas x 5 journeys was gone — only the console log
// survived, which the banker cannot read. A spot-check should never be able to clobber the run it is
// checking, so any narrowed run (--page or --journeys) now defaults to a SEPARATE file unless an
// explicit --out says otherwise.
const OUT = (() => {
  const i = args.indexOf('--out');
  if (i >= 0) return args[i + 1];
  return (ONE || ONLY) ? 'journey_report.partial.json' : 'journey_report.json';
})();

const PAGES = ['index', 'hive', 'logbook', 'inventory', 'pm-scheduler', 'project-manager', 'dayplanner',
  'asset-hub', 'analytics', 'alert-hub', 'skillmatrix', 'shift-brain', 'voice-journal', 'assistant',
  'community', 'public-feed', 'achievements', 'engineering-design', 'resume', 'report-sender',
  'project-report', 'analytics-report'];

// Map a grounded persona LABEL to an identity this harness can actually establish. The labels are prose
// written per page ("worker (own entries)", "two_context (two techs, one PM)"), so the mapping is by
// keyword, and anything unrecognised becomes `unknown` and FAILS non-vacuously rather than silently
// defaulting to a signed-in worker — defaulting is how a persona claim gets banked for the wrong identity.
function identityFor(label) {
  const s = String(label || '').toLowerCase();
  if (s.startsWith('two_context')) return 'two_context';
  if (s.includes('crawler')) return 'crawler';
  if (s.includes('multi-hive')) return 'multi_hive';
  if (s.startsWith('anon')) return 'anon';
  if (s.includes('supervisor') || s.includes('assessor') || s.includes('project manager')
      || s.includes('reliability engineer') || s.includes('engineer')) return 'supervisor';
  if (s.includes('worker') || s.includes('member')) return 'worker';
  return 'unknown';
}

function personasFor(page) {
  const fp = `page_bank_anatomy/${page}.json`;
  if (!existsSync(fp)) return null;
  const a = JSON.parse(readFileSync(fp, 'utf8'));
  const jp = a.journey_personas || [];
  return jp.map((x, i) => {
    const label = typeof x === 'string' ? x : (x.id || x.name || JSON.stringify(x));
    return { slot: `P${i + 1}`, label, identity: identityFor(label) };
  });
}

// Everything a returning visitor would carry, removed — EXCEPT the session. Wiping auth would test the
// sign-in wall instead of the journey, and would sign the walker out for every later step.
// ★ MEMBERSHIP IS PART OF THE IDENTITY, NOT PART OF THE "SETUP" A RETURNING VISITOR CARRIES — and the
// first version wiped it, then judged the pages for reacting correctly. `wh_active_hive_id` (utils.js:1976)
// is where the active hive lives, so clearing it left every page with a signed-in user who belongs to no
// hive. asset-hub then rendered, entirely correctly: "Asset Hub needs a hive. Asset Brain works only
// inside a team hive. Join or create one… Go to Hive →" — 257 characters, 4 controls, zero failed reads,
// an explanation and a link to the fix. The oracle called that a DEAD END, for all three personas,
// INCLUDING the supervisor who is demonstrably a member of hive 636cf7e8. That giveaway — a persona who
// cannot possibly lack a hive reporting no hive — is what exposed the probe rather than the page.
// The journey under test is a first-time signed-in MEMBER ("worker (own entries)", "reliability
// engineer"), so the keys that carry membership are preserved exactly as the session is. Wiping them tests
// a different journey — a user with no hive — which is a legitimate thing to walk, but it is not the row
// this claims, and manufacturing it would have banked a dozen findings against pages behaving properly.
// THE WORKER-NAME KEYS ARE THE SAME STORY, FOUND THE SAME WAY: `whWorker()` (utils.js:3148) reads
// `wh_last_worker` / `wh_worker_name` / `workerName`, and achievements.html:504 does
// `if (!WORKER_NAME) { location.href = 'index.html' }`. Clearing those bounced a signed-in worker off the
// page and the oracle called it BOUNCED — a finding about the probe, not the product.
// ★ BUT THE RUN THAT MADE THAT MISTAKE MEASURED SOMETHING REAL, AND IT IS WORTH KEEPING: with the
// identity cache cleared, the SESSION is still perfectly valid, and achievements.html:498 already holds
// the cure — `restoreIdentityFromSession(db)` re-derives the name from that session. Line 504 redirects
// SYNCHRONOUSLY without awaiting it. So a signed-in person who clears site data (or whose cache is evicted)
// is thrown to the landing page by a check that had the answer one line above it. That is a genuine
// robustness gap in the identity-restore path, recorded in the roadmap for the CO/CC families where it
// belongs — it is not a `first_run_to_value` failure, and it is not smuggled into these rows.
const WIPE = `(() => {
  try {
    const keep = /^(sb-|supabase|wh_active_hive_id|wh_hive_id|wh_hive_role|wh_hive_name|wh_last_worker|wh_worker_name|workerName)/i;
    for (const k of Object.keys(localStorage)) if (!keep.test(k)) localStorage.removeItem(k);
    for (const k of Object.keys(sessionStorage)) if (!keep.test(k)) sessionStorage.removeItem(k);
  } catch (e) {}
})()`;

// A dead end: the person is looking at a surface that offers them nothing to do next. Also harvests the
// signals J1/J2 grade on, so one evaluate call is the whole reading.
const READ = ({ emptySrc }) => {
  // ★ A REASONED EMPTY STATE IS A JOURNEY OUTCOME, NOT A DEAD END. asset-hub renders 257 characters for a
  // worker whose plant has no assets yet — and what it says is "No assets yet. Workers can submit
  // equipment from PM Scheduler or Inventory; when they do, the submission will land in your Pending
  // Approvals card below." That explains the emptiness AND names the next step, which is precisely what a
  // first-timer needs. A bare `chars < 300` rule fails it for being SHORT, punishing the pages that handle
  // emptiness well and rewarding ones that pad the screen. So a short page that states its reason is not a
  // dead end; a short page that says nothing still is.
  // The vocabulary is imported, never re-typed here: two copies of a predicate is what created
  // session_signals.mjs in the first place.
  const EMPTY = new RegExp(emptySrc, 'i');
  const vis = (el) => {
    const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const actionable = [...document.querySelectorAll(
    'button:not([disabled]), a[href]:not([href^="#"]), [role="button"]:not([aria-disabled="true"]),'
    + ' input:not([type=hidden]), select, textarea')].filter(vis);
  const txt = (document.body.innerText || '').replace(/\s+/g, ' ').trim();
  // A SETUP DEMAND is the thing repeat_visit must not see twice: a page asking the person to choose or
  // configure something BEFORE IT WILL SHOW THEM ANYTHING.
  //
  // ★ THE WORD IS NOT THE DEMAND. The first version matched this vocabulary anywhere in body text and
  // failed `hive` for a returning worker on the string "GET STARTED" — which is a bare <span> at y=1101,
  // BELOW THE FOLD, uppercased by CSS, on a page that was simultaneously showing that worker "YOUR OPEN
  // WORK · 2 open jobs assigned to you". A person looking at their own open jobs is not being made to redo
  // setup. That is the body-wide-keyword-match class: the page's own chrome read as a verdict about it.
  // So the phrase must be ATTACHED TO AN ELEMENT that could actually block: visible, ABOVE THE FOLD, and
  // either inside an overlay/modal or on a page that has not otherwise produced content. A match that
  // fails those is still reported — as `setupMention`, informational — so the reading stays honest about
  // what it saw without converting it into a finding.
  const SETUP = /choose (your|a) |select (your|a) (discipline|trade|role|hive|shift)|pick (your|a) |get started|set up your|complete your profile|first,? (choose|select|tell us)|welcome[,!]? let/i;
  // COLLECT EVERY CANDIDATE AND RANK THEM — never take the first and stop. The first version broke out of
  // the loop on the first above-the-fold match, which on a landing page is its own harmless "Get started"
  // CTA; a genuine blocking overlay appended later in the DOM was therefore never reached, and the
  // detector reported "no demand" while a modal was covering the screen. The teeth test caught it before
  // it reached a single banked row. Rank: in-overlay-and-above-fold beats above-fold beats anything else.
  const cands = [];
  for (const el of document.querySelectorAll('*')) {
    if (el.children.length) continue;                       // leaf nodes carry the label
    const t = (el.innerText || '').trim();
    if (!t || !SETUP.test(t) || !vis(el)) continue;
    const r = el.getBoundingClientRect();
    const overlay = !!el.closest('[class*="overlay"], [class*="modal"], [role="dialog"], [class*="sheet"]');
    cands.push({ text: SETUP.exec(t)[0].slice(0, 60), y: Math.round(r.top),
                 aboveFold: r.top < innerHeight, inOverlay: overlay });
  }
  const rank = (c) => (c.aboveFold && c.inOverlay ? 2 : c.aboveFold ? 1 : 0);
  const setupEl = cands.length ? cands.reduce((a, b) => (rank(b) > rank(a) ? b : a)) : null;
  // A skeleton still shimmering is not value; count only VISIBLE ones (a hidden template is not a state).
  const skel = [...document.querySelectorAll('[class*="skeleton"], [class*="shimmer"], .wh-list-skeleton')]
    .filter(vis).length;
  // A demand BLOCKS: it is above the fold AND either sits in an overlay or is what the page is showing
  // INSTEAD of content. Everything else the vocabulary caught is a mention, kept for the record only.
  const contentPoor = (txt.length < 900 && !EMPTY.test(txt)) || actionable.length < 3;
  const blocking = !!setupEl && setupEl.aboveFold && (setupEl.inOverlay || contentPoor);
  const reasonedEmpty = EMPTY.test(txt);
  return {
    chars: txt.length, actionable: actionable.length, visibleSkeletons: skel, reasonedEmpty,
    setupDemand: blocking ? setupEl.text : null,
    setupMention: setupEl && !blocking
      ? `${setupEl.text} (y=${setupEl.y}, ${setupEl.aboveFold ? 'above' : 'below'} the fold, `
        + `overlay=${setupEl.inOverlay}) — present but not blocking` : null,
    head: txt.slice(0, 220),
  };
};

// ★ A SIGN-IN THAT FAILED MUST NOT BECOME AN ANONYMOUS WALK WEARING THE PERSONA'S NAME.
// The first version of this function ended every signIn with `.catch(() => {})`. That is the swallow this
// harness's own non-vacuity rule exists to forbid: if the sign-in fails, the context is anonymous, the
// page bounces to index.html?signin=1 — and the row would still be banked as "worker (own entries)".
// It is the same defect in the harness that the oracle is looking for in the product.
// So the failure is RETURNED, and the caller fails the journey with it.
// ── J4 · two_sided_same_object ────────────────────────────────────────────────────────────────────
// TWO IDENTITIES, ONE PAGE, ONE TRUTH. Both accounts belong to the same hive (636cf7e8), so any figure
// they can BOTH see is a claim about the same underlying object and the two renderings must agree.
//
// THE COMPARISON IS KEYED ON ELEMENT ID, not on text position or reading order, because the two renderings
// are the same DOM under different sessions: an id is the only stable way to say "this number and that
// number are the same claim". Comparing whole page text instead would flag every legitimate role
// difference — a supervisor sees controls a worker does not — and drown the real signal.
//
// ROLE DIFFERENCES ARE NOT DISAGREEMENTS. An id rendered for only one identity is SKIPPED, not failed:
// that is authorisation working. Only ids present and non-empty on BOTH sides are compared, and the count
// of those is reported, because a comparison over zero shared ids is a vacuous pass — the same
// zero-denominator trap that made an earlier prover print PASS over nothing measured.
// ★ THE SAME ELEMENT ID IS NOT THE SAME CLAIM WHEN THE PAGE CHANGES THE QUESTION PER ROLE. The first
// version compared values by id alone and reported logbook as "3 of 8 shared figures DISAGREE between two
// members of the same hive": #total-count 314 vs 516, #open-count 2 vs 6. Both correct. The third
// disagreement is the one that explains the other two — #lb-progress read "JOBS CLOSED" for the worker and
// "TEAM JOBS" for the supervisor. The page deliberately answers a NARROWER question for a worker (your
// jobs) than for a supervisor (the team's), through the same element. Those are two different claims that
// happen to share an id, and calling them a contradiction would have banked 66 findings alleging the
// platform disagrees with itself while it was scoping correctly — and saying so, in its own label.
// So the LABEL is captured with the value and is part of the key: figures are compared only where both
// sides ask the same question. A differing label means a differing question, and is counted as
// role-scoped rather than failed. The page's own words decide what is comparable.
const NUMBERS = () => {
  const out = {};
  for (const el of document.querySelectorAll('[id]')) {
    if (el.children.length > 3) continue;               // containers aggregate other people's numbers
    const t = (el.innerText || '').replace(/\s+/g, ' ').trim();
    if (!t || t.length > 60 || !/\d/.test(t)) continue;  // must actually render a figure
    const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    if (!(r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none')) continue;
    // What does the page CALL this number? aria-label first (it is the authored answer), else the
    // surrounding block with the figure itself removed, so the label is text and not the value.
    let label = el.getAttribute('aria-label') || '';
    if (!label) {
      const box = el.closest('[class*="card"], [class*="tile"], [class*="stat"], li, td, section') || el.parentElement;
      label = ((box && box.innerText) || '').replace(/\s+/g, ' ').replace(t, ' ').trim();
    }
    out[el.id] = { value: t, label: label.slice(0, 70).toLowerCase() };
  }
  return out;
};

async function readNumbers(ctx, url) {
  const page = await ctx.newPage();
  await page.goto(`${ORIGIN}/${url}`, { waitUntil: 'domcontentloaded', timeout: 25000 });
  await page.waitForTimeout(4200);
  const landed = pageName(page.url());
  const nums = await page.evaluate(NUMBERS);
  await page.close();
  return { nums, landed, redirected: landed !== url.replace(/\.html$/, '') };
}

// ── J5 · abandon_resume ───────────────────────────────────────────────────────────────────────────
// START SOMETHING, WALK AWAY, COME BACK — AND NOTHING MAY HAVE HALF-LANDED. Typing into a composer and
// abandoning it is the most ordinary thing a person on a plant floor does: they get called away mid-entry.
// The failure this looks for is a page that treats the abandoned input as a committed record.
//
// THE DISCRIMINATION THAT MAKES IT FAIR: a preserved DRAFT is good UX, not a defect. So the marker text is
// looked for in two different places after the reload, and they mean opposite things:
//   · back inside the COMPOSER FIELD  -> a draft was kept. PASS, and worth noting as deliberate.
//   · out in the page's own CONTENT   -> it half-landed. A person who typed and walked away now has a
//                                        record they never submitted. FAIL.
// Nothing is ever submitted, so this stays non-writing: the marker only reaches an input's value.
//
// WHICH PAGES: the composer inventory is `tools/dialog_targets.mjs`, the same grounded table four other
// provers already read, so this cannot drift from how those views are known to open. 16 drivable targets
// across 11 of the 22 pages carry one. A page with NO composer is left OWED rather than failed — "this
// surface has nothing to abandon" is a design fact about a read-only page, not a defect, and R10 wants a
// declared-na with a reason rather than a manufactured red.
// ── J3 · cross_surface_handoff ────────────────────────────────────────────────────────────────────
// FOLLOW A LINK OUT AND ARRIVE SOMEWHERE THAT WORKS. The claim is deliberately narrow, because a wide one
// would be dishonest: most in-app links carry no parameter, so there is no "context" to survive, and
// asserting that there is would be inventing a property to measure.
// What IS assertable, and worth asserting:
//   · the handoff LANDS WHERE THE LINK PROMISED — the href's page is the page you end up on. A link that
//     silently bounces elsewhere (an auth wall, a redirect) has broken the handoff even though it "worked".
//   · the destination is NOT A DEAD END, judged on the same rule J1 uses, including the reasoned-empty
//     exemption — so a handoff into a well-explained empty state passes, and one into a blank does not.
//   · IF the link carries context (a query parameter), the destination must REFLECT it rather than drop it
//     — that is the only case where "context survived" is a real, checkable claim, and it is checked.
// A page with no in-app link to another product page is left OWED, not failed.
const ROSTER = new Set(['index', 'hive', 'logbook', 'inventory', 'pm-scheduler', 'project-manager',
  'dayplanner', 'asset-hub', 'analytics', 'alert-hub', 'skillmatrix', 'shift-brain', 'voice-journal',
  'assistant', 'community', 'public-feed', 'achievements', 'engineering-design', 'resume',
  'report-sender', 'project-report', 'analytics-report']);

async function walkHandoff(ctx, from, emptySrc) {
  const page = await ctx.newPage();
  try {
    await page.goto(`${ORIGIN}/${from}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForTimeout(3600);
    // ★ RANK THE LINKS — taking the first one makes this oracle worthless. The first visible in-app anchor
    // on nearly every page is the masthead logo: no text, pointing at index. Walking that would test
    // "logo → index" on all 22 pages, pass every time, and measure nothing anyone cares about — a green
    // over a claim not worth making, which is vacuity wearing a pass.
    // So candidates are ranked by how much of a HANDOFF they actually are: one carrying context (a query
    // parameter) is the only kind where "context survived" can even be checked, and is worth most; then a
    // real labelled navigation to another surface; the bare logo-to-home link is the last resort.
    const link = await page.evaluate((self) => {
      const cands = [];
      for (const a of document.querySelectorAll('a[href]')) {
        const r = a.getBoundingClientRect(); const s = getComputedStyle(a);
        if (!(r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none')) continue;
        const href = a.getAttribute('href') || '';
        if (/^(#|javascript:|mailto:|tel:|https?:)/i.test(href)) continue;
        // Strip the FRAGMENT before the extension, or `index.html#evolution` never normalises to
        // `index` — it stays mangled, falls outside the roster, and (because it then looks like a
        // non-index page) the ranking below actively PREFERS it over a real link. That is how a
        // ranking meant to find the best handoff ended up selecting the one candidate it could not use.
        const file = href.split('/').pop().split('#')[0].split('?')[0].replace(/\.html$/, '');
        if (!file || file === self) continue;
        const text = (a.innerText || '').trim().slice(0, 40);
        const param = href.includes('?') ? href.split('?')[1].slice(0, 60) : null;
        cands.push({ href, file, param, text,
                     rank: param ? 3 : (text && file !== 'index') ? 2 : text ? 1 : 0 });
      }
      if (!cands.length) return { none: true, seen: 0 };
      const best = cands.reduce((a, b) => (b.rank > a.rank ? b : a));
      return { ...best, seen: cands.length, files: [...new Set(cands.map((c) => c.file))].slice(0, 6) };
    }, from);
    if (!link || link.none || !ROSTER.has(link.file)) {
      await page.close();
      // An honest NOT-MEASURED says what it saw, so 'no link' can be told apart from 'links to
      // things outside the roster' without a second run.
      return { na: `no usable in-app link to another product page (${link ? link.seen : 0} candidate(s)`
        + `${link && link.files ? ', to: ' + link.files.join('/') : ''}${link && link.file ? `; best was "${link.file}" which is not in the roster` : ''})` };
    }

    await page.goto(new URL(link.href, `${ORIGIN}/${from}.html`).href,
                    { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForTimeout(3800);
    const landed = pageName(page.url());
    const reading = await page.evaluate(READ, { emptySrc });
    const url = page.url();
    await page.close();
    return { link, landed, reading, keptParam: link.param ? url.includes(link.param.split('=')[0]) : null };
  } catch (e) { await page.close().catch(() => {}); return { error: String(e.message || e).slice(0, 120) }; }
}

const MARKER = 'wh-abandon-probe-9f3c';

async function walkAbandon(ctx, page_, target) {
  const page = await ctx.newPage();
  try {
    await page.goto(`${ORIGIN}/${page_}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForTimeout(3600);
    const before = await page.evaluate(() => (document.body.innerText || '').replace(/\s+/g, ' ').length);

    // ★ DO NOT SWALLOW THE PRECONDITION. Several targets are state-gated: pm-scheduler's #btn-edit-asset
    // ships hidden and is only revealed after an .asset-card is clicked, which is exactly what its `pre`
    // does. Catching the pre's failure and carrying on means clicking a control the precondition was
    // supposed to reveal, and the resulting locator timeout gets reported as "could not be walked" — an
    // opaque failure that hides a knowable cause. A precondition that cannot be met is NOT APPLICABLE
    // (the state this view needs does not exist for this persona), and it should say so by name.
    if (target.pre) {
      try { await page.evaluate(target.pre); }
      catch (e) {
        await page.close();
        return { na: `the view's precondition could not be met (${String(e.message || e).slice(0, 70)}) `
          + '— the state this composer needs does not exist for this persona' };
      }
    }
    await page.waitForTimeout(400);
    if (target.openBy === 'fn' || target.fn) await page.evaluate(target.fn || target.opener).catch(() => {});
    else {
      try { await page.click(target.opener, { timeout: 6000 }); }
      catch (e) { await page.close();
        return { na: `the opener ${target.opener} never became clickable — the composer could `
          + 'not be opened, so there was nothing to abandon' }; }
    }
    await page.waitForTimeout(900);

    // The first visible text field inside the opened view is the composer.
    const typed = await page.evaluate((sel) => {
      const root = document.querySelector(sel) || document;
      const f = [...root.querySelectorAll('input[type=text], input:not([type]), textarea')]
        .find((el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
          return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; });
      if (!f) return null;
      return f.id || f.name || f.className || 'unnamed field';
    }, target.modal ? `#${target.modal}` : 'body');
    if (!typed) { await page.close(); return { na: 'the opened view has no visible text field to abandon' }; }

    await page.fill(`#${target.modal} input[type=text]:visible, #${target.modal} input:not([type]):visible,`
      + ` #${target.modal} textarea:visible`, MARKER, { timeout: 6000 }).catch(async () => {
      await page.evaluate(({ sel, m }) => {
        const root = document.querySelector(sel) || document;
        const f = [...root.querySelectorAll('input[type=text], input:not([type]), textarea')]
          .find((el) => el.getBoundingClientRect().width > 0);
        if (f) { f.value = m; f.dispatchEvent(new Event('input', { bubbles: true })); }
      }, { sel: `#${target.modal}`, m: MARKER });
    });
    await page.waitForTimeout(600);

    // ABANDON: leave the page entirely, the way being called away actually looks.
    await page.goto(`${ORIGIN}/index.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForTimeout(1200);
    await page.goto(`${ORIGIN}/${page_}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForTimeout(3800);

    const after = await page.evaluate((m) => {
      const body = (document.body.innerText || '').replace(/\s+/g, ' ');
      const inField = [...document.querySelectorAll('input, textarea')].some((el) => (el.value || '').includes(m));
      return { chars: body.length, inContent: body.includes(m), inField };
    }, MARKER);
    await page.close();
    return { before, ...after, field: typed };
  } catch (e) { await page.close().catch(() => {}); return { error: String(e.message || e).slice(0, 120) }; }
}

async function newCtx(browser, identity) {
  const opts = { viewport: { width: 390, height: 844 } };
  if (identity === 'crawler') {
    opts.userAgent = 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)';
  }
  const ctx = await browser.newContext(opts);
  const who = (identity === 'supervisor' || identity === 'multi_hive') ? 'supervisor'
            : identity === 'worker' ? 'worker' : null;
  if (who) {
    try { await signIn(ctx, who); }
    catch (e) { return { ctx, signInError: String(e.message || e).slice(0, 120) }; }
  }
  // anon + crawler: deliberately no session.
  return { ctx, signInError: null };
}

/** One page load, with its network failures counted. Returns the reading plus the REST/RPC error list. */
async function visit(ctx, url, { wipeFirst }) {
  const page = await ctx.newPage();
  const restErrors = [];
  page.on('response', (r) => {
    const u = r.url();
    if (!/\/rest\/v1\/|\/rpc\/|\/functions\/v1\//.test(u)) return;
    if (r.status() >= 400) restErrors.push(`${r.status()} ${u.split('/').slice(-1)[0].slice(0, 40)}`);
  });
  if (wipeFirst) {
    // The wipe must happen against the ORIGIN, so land first, clear, then do the real first run.
    await page.goto(`${ORIGIN}/${url}`, { waitUntil: 'domcontentloaded', timeout: 25000 }).catch(() => {});
    await page.evaluate(WIPE).catch(() => {});
  }
  await page.goto(`${ORIGIN}/${url}`, { waitUntil: 'domcontentloaded', timeout: 25000 });
  await page.waitForTimeout(3600);
  let reading = await page.evaluate(READ, { emptySrc: REASONED_EMPTY_SRC });
  // A page still rendering is not a dead end — give it one bounded second chance, visible skeletons only.
  if (reading.visibleSkeletons > 0 || reading.chars < 300) {
    await page.waitForTimeout(4000);
    reading = await page.evaluate(READ, { emptySrc: REASONED_EMPTY_SRC });
  }
  // ★ WHERE DID THIS READING ACTUALLY COME FROM? Capture the landed URL, because several pages bounce an
  // unauthenticated caller to index.html?signin=1 (hive.html:1866/1870/2211 among them) — and index's
  // landing copy contains "Get Started". Without this, the walk reads INDEX and files the finding against
  // HIVE: a page-level claim measured on a different page. That is how the first run of this prover
  // produced `hive P1 repeat FAIL — still asking "GET STARTED"` for a string that does not occur anywhere
  // in hive.html. A redirect is its own outcome, never a verdict about the page you asked for.
  const landed = pageName(page.url());
  await page.close();
  return { ...reading, restErrors, landed, redirected: landed !== url.replace(/\.html$/, '') };
}

// ── TEETH · both directions, against a REAL page rather than a mocked reading ──────────────────────
// Narrowing "a setup demand" from `the vocabulary appears anywhere` to `it BLOCKS` removed a false red on
// hive — and a narrowing that is not tested in both directions is how a detector quietly becomes
// "never fails". So: inject a genuine blocking overlay and require the detector to FIRE, remove it and
// require it to go quiet. A one-directional check would pass even if setupDemand were hard-coded null.
if (args.includes('--selftest')) {
  const b = await chromium.launch();
  const c = await b.newContext({ viewport: { width: 390, height: 844 } });
  const pg = await c.newPage();
  await pg.goto(`${ORIGIN}/index.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
  await pg.waitForTimeout(1500);
  let fail = 0;

  const inject = (y) => pg.evaluate((top) => {
    const d = document.createElement('div');
    d.className = 'modal-overlay wh-selftest';
    d.setAttribute('role', 'dialog');
    // display/visibility/opacity are forced because `.modal-overlay` is HIDDEN by the platform's shared
    // CSS until it gets `.open` — without these the fixture is invisible, the detector correctly ignores
    // it, and the selftest fails while blaming the detector. The fixture has to satisfy the same
    // visibility contract a real dialog does.
    d.style.cssText = `position:fixed;left:0;right:0;top:${top}px;z-index:99999;background:#111;`
      + 'color:#fff;padding:20px;font-size:16px;display:block;visibility:visible;opacity:1';
    d.textContent = 'Choose your discipline to continue';
    document.body.appendChild(d);
  }, y);
  const clear = () => pg.evaluate(() => document.querySelectorAll('.wh-selftest').forEach((n) => n.remove()));

  await inject(10);
  let r = await pg.evaluate(READ, { emptySrc: REASONED_EMPTY_SRC });
  if (!r.setupDemand) { console.log('  FAIL — an above-fold blocking overlay was NOT detected as a demand'); fail++; }
  else console.log(`  ok — blocking overlay detected: "${r.setupDemand}"`);
  await clear();

  r = await pg.evaluate(READ, { emptySrc: REASONED_EMPTY_SRC });
  if (r.setupDemand) { console.log(`  FAIL — a demand was reported with no overlay present: ${r.setupDemand}`); fail++; }
  else console.log('  ok — with the overlay removed, no demand is reported');

  // And the exact shape that produced the false red: present, real, but far below the fold.
  await pg.evaluate(() => {
    const d = document.createElement('div');
    d.className = 'wh-selftest';
    d.style.cssText = 'position:absolute;top:4000px;left:0';
    d.textContent = 'Get started';
    document.body.appendChild(d);
  });
  r = await pg.evaluate(READ, { emptySrc: REASONED_EMPTY_SRC });
  if (r.setupDemand) { console.log('  FAIL — a below-fold CTA was counted as a blocking demand (the hive false red)'); fail++; }
  else console.log(`  ok — below-fold CTA recorded as a mention, not a demand: ${r.setupMention}`);

  await b.close();
  console.log(fail ? `\n  SELFTEST FAILED (${fail})` : '\n  SELFTEST PASSED — the detector fires and stays quiet in the right cases');
  process.exit(fail ? 1 : 0);
}

const browser = await chromium.launch();
const results = [];
for (const p of (ONE ? [ONE.replace(/\.html$/, '')] : PAGES)) {
  const personas = personasFor(p);
  if (!personas) { results.push({ page: p, error: 'no anatomy file — persona subjects ungrounded (R7)' }); continue; }
  for (const persona of personas) {
    const rec = { page: p, slot: persona.slot, label: persona.label, identity: persona.identity };
    try {
      if (persona.identity === 'unknown') {
        // NON-VACUITY: an unmapped persona is a finding about this harness's knowledge of the page,
        // never a skip, and never quietly walked as a signed-in worker.
        rec.first_run = { ok: false, verdict: `persona "${persona.label}" maps to no identity this harness `
          + 'can establish — the journey could not be CONSTRUCTED, which is a finding, not a skip' };
        rec.repeat = { ok: false, verdict: 'not attempted: persona unmappable' };
        results.push(rec); continue;
      }
      const two = persona.identity === 'two_context';
      const idA = two ? 'supervisor' : persona.identity;
      const A = await newCtx(browser, idA);
      const B = two ? await newCtx(browser, 'worker') : { ctx: null, signInError: null };
      const ctxA = A.ctx, ctxB = B.ctx;

      // The persona must be ESTABLISHED before anything it does can be attributed to it.
      if (A.signInError || B.signInError) {
        const why = `could not establish the identity for this persona: ${A.signInError || B.signInError}`;
        rec.first_run = { ok: false, verdict: `NOT WALKED — ${why}. The journey could not be CONSTRUCTED, `
          + 'so no verdict about the page is claimed; walking it anonymously would file an anonymous '
          + "reading under this persona's name." };
        rec.repeat = { ok: false, verdict: `not attempted: ${why}` };

      await ctxA.close(); if (ctxB) await ctxB.close();
        results.push(rec);
        console.log(`  ${(p + ' ' + rec.slot).padEnd(28)} first_run FAIL  repeat FAIL  ${why.slice(0, 60)}`);
        continue;
      }

      // Hoisted out of the J1/J2 block: J3 needs it too, and a `const` inside that block is
      // invisible to J3 — a ReferenceError waiting for the first `--journeys j3` run.
      const anonish = idA === 'anon' || idA === 'crawler';

      if (wants('j1') || wants('j2')) {
      // ── J1 · first_run_to_value: a first-timer reaches the first useful outcome without a dead end.
      const a1 = await visit(ctxA, `${p}.html`, { wipeFirst: true });
      const b1 = two ? await visit(ctxB, `${p}.html`, { wipeFirst: true }) : null;
      rec.firstRead = a1; if (b1) rec.firstReadB = b1;

      const readsFailed = a1.restErrors.length + (b1 ? b1.restErrors.length : 0);
      const deadEnd = a1.actionable < 3 || (a1.chars < 300 && !a1.reasonedEmpty);
      const stuck = a1.visibleSkeletons > 0;

      if (a1.redirected && anonish) {
        // The auth wall, met by someone with no session. That IS the correct journey for this persona —
        // they are sent somewhere they can actually do something — so it passes, but it is recorded as a
        // redirect rather than dressed up as having reached the page's own value.
        rec.first_run = { ok: a1.actionable >= 3, verdict: `redirected to "${a1.landed}" — the expected `
          + `auth wall for an ${idA} persona on a private page, and it offers ${a1.actionable} actionable `
          + `control(s). No claim is made about ${p}'s own content, which this persona never sees.` };
      } else if (a1.redirected) {
        // A person WITH a session bounced off the page they asked for.
        rec.first_run = { ok: false, verdict: `BOUNCED — a signed-in "${persona.label}" asked for ${p} and `
          + `landed on "${a1.landed}". Everything renderable here belongs to that other page, so no verdict `
          + `about ${p} is claimed; the finding is the bounce itself.` };
      } else if (readsFailed && a1.setupDemand) {
        // ★ the lie this oracle exists to catch.
        rec.first_run = { ok: false, verdict: `ONBOARDING OVER A FAILED READ — the page asked "`
          + `${a1.setupDemand}" while ${readsFailed} of its own read(s) failed (${a1.restErrors.slice(0, 3)
            .join('; ')}). A first-run screen shown because the read broke is not value: it invites the `
          + 'person to redo setup they already did, and can overwrite it.' };
      } else if (deadEnd) {
        rec.first_run = { ok: false, verdict: `DEAD END — ${a1.actionable} actionable control(s) over `
          + `${a1.chars} characters. A first-timer is looking at a surface offering nothing to do next.` };
      } else if (stuck) {
        rec.first_run = { ok: false, verdict: `${a1.visibleSkeletons} skeleton(s) still visible after 7.6s `
          + '— the first run never resolved into content' };
      } else if (two && (b1.actionable < 3 || (b1.chars < 300 && !b1.reasonedEmpty))) {
        rec.first_run = { ok: false, verdict: `the second concurrent identity hit a dead end `
          + `(${b1.actionable} controls / ${b1.chars} chars) while the first reached value` };
      } else {
        rec.first_run = { ok: true, verdict: `reached value: ${a1.chars} chars, ${a1.actionable} actionable `
          + `control(s), 0 stuck skeletons, ${readsFailed} failed read(s)`
          + (two ? `; second identity ${b1.actionable} controls / ${b1.chars} chars` : '') };
      }

      // ── J2 · repeat_visit: the SAME session, the only change being that the person has been here before.
      const a2 = await visit(ctxA, `${p}.html`, { wipeFirst: false });
      rec.repeatRead = a2;
      if (a2.redirected) {
        // Same rule as J1: a reading taken on another page cannot settle a claim about this one. For an
        // anon persona the wall is expected and the return visit simply meets it again.
        rec.repeat = anonish
          ? { ok: true, verdict: `redirected to "${a2.landed}" again — the same expected auth wall, which `
              + 'is consistent behaviour for a returning visitor with no session' }
          : { ok: false, verdict: `BOUNCED on the return visit — landed on "${a2.landed}" instead of ${p}` };
      } else if (a2.setupDemand && !a1.setupDemand) {
        rec.repeat = { ok: false, verdict: `the RETURN visit demanded setup the first one did not: `
          + `"${a2.setupDemand}"` };
      } else if (a2.setupDemand && a1.setupDemand) {
        rec.repeat = { ok: false, verdict: `still asking "${a2.setupDemand}" on the second visit — a `
          + 'returning person is being made to redo setup' };
      } else if (a2.actionable < 3 || (a2.chars < 300 && !a2.reasonedEmpty)) {
        rec.repeat = { ok: false, verdict: `the return visit is a dead end (${a2.actionable} controls / `
          + `${a2.chars} chars) though the first run reached value` };
      } else if (a2.visibleSkeletons > 0) {
        rec.repeat = { ok: false, verdict: `${a2.visibleSkeletons} skeleton(s) still visible on return` };
      } else {
        rec.repeat = { ok: true, verdict: `returning person goes straight to content: ${a2.chars} chars, `
          + `${a2.actionable} control(s), no setup demanded` };
      }

      }

      // ── J4 · two_sided_same_object — every figure BOTH identities can see must agree.
      if (wants('j4')) {
        // ★ TWO SESSIONS, NOT TWO ROLES — and the first version got this wrong in a way worth keeping.
        // It compared a worker's rendering against a supervisor's and reported logbook as "3 of 8 shared
        // figures DISAGREE between two members of the same hive": #total-count 314 vs 516, #open-count 2
        // vs 6. Both numbers were right. The page deliberately scopes the whole view by role — the giveaway
        // was #lb-progress reading "JOBS CLOSED" for the worker and "TEAM JOBS" for the supervisor — so
        // those are answers to DIFFERENT questions and were never the same object to begin with.
        // Matching on the adjacent label did not rescue it either: #total-count is labelled "entries" for
        // both, and only a different element disclosed the scope. (That gap is a real finding, but it
        // belongs to CM `what_is_this_number` — the same word "entries" naming two different populations
        // with nothing on screen saying whose — and it is recorded there rather than smuggled in here.)
        // So the second side is the SAME identity in a SECOND SESSION, which is what this page's own
        // anatomy means by two_context ("two workers, one entry"). Role scoping is then identical by
        // construction, and any disagreement left is a genuine one: a race, or a stale cache.
        const other = await newCtx(browser, idA);
        if (other.signInError) {
          rec.two_sided = { ok: false, verdict: `could not establish the second identity: ${other.signInError}` };
        } else {
          const mine = await readNumbers(ctxA, `${p}.html`);
          const theirs = await readNumbers(other.ctx, `${p}.html`);
          // BOTH SIDES AT THE SAME AUTH WALL ARE STILL THE SAME OBJECT. This branch used to fail whenever
          // EITHER side redirected, and then reported "one side landed elsewhere" — which was wrong twice
          // over for an anon persona. Measured on community: 4 of 4 anon sessions land on index with
          // identical text, deterministically. They did not disagree; they were both correctly stopped at
          // the wall, and comparing them THERE is a real same-object comparison. Only a genuine split —
          // the two sessions ending up on DIFFERENT pages — breaks comparability, and that is worth a red.
          if (mine.landed !== theirs.landed) {
            rec.two_sided = { ok: false, verdict: `the two sessions ended up on DIFFERENT pages `
              + `("${mine.landed}" vs "${theirs.landed}") — one identity, two destinations, so `
              + 'nothing here is a comparison of the same object' };
          } else if (mine.redirected) {
            // Same destination, just not the page we asked for. Compare there and SAY so, rather than
            // silently claiming a verdict about a page neither session ever saw.
            const both = Object.keys(mine.nums).filter((k) => k in theirs.nums);
            const sh = both.filter((k) => mine.nums[k].label === theirs.nums[k].label);
            const df = sh.filter((k) => mine.nums[k].value !== theirs.nums[k].value);
            rec.two_sided = df.length
              ? { ok: false, verdict: `${df.length} of ${sh.length} figure(s) DISAGREE between two `
                  + `sessions of this identity at "${mine.landed}"` }
              : { ok: true, verdict: `both sessions were sent to "${mine.landed}" — the expected wall `
                  + `for this persona — and the ${sh.length} figure(s) visible to both AGREE there. No `
                  + `claim is made about ${p}'s own content, which this persona never sees.` };
          } else {
            const both = Object.keys(mine.nums).filter((k) => k in theirs.nums);
            // Same id AND same label = the same question asked of both identities. Same id, different
            // label = the page is deliberately asking a narrower question of one of them.
            const shared = both.filter((k) => mine.nums[k].label === theirs.nums[k].label);
            const roleScoped = both.length - shared.length;
            const differ = shared.filter((k) => mine.nums[k].value !== theirs.nums[k].value)
              .map((k) => `#${k} ("${mine.nums[k].label.slice(0, 30)}"): `
                        + `"${mine.nums[k].value}" vs "${theirs.nums[k].value}"`);
            if (!shared.length) {
              // NOT APPLICABLE, NOT FAILED — and the distinction matters. `assistant` is a chat
              // surface with no id-bearing figures at all, so there is nothing here for two sessions
              // to agree or disagree about. Failing it would bank a red against a page for not having
              // numbers, which is R10's vacuity in the other direction; the row stays OWED and the
              // reason is recorded. (The A16.D4 rail still applies to the PROVER as a whole: if the
              // whole run measures nothing, that is a loud failure — see `measured` below.)
              rec.two_sided = null;
              rec.twoSidedNa = `no figure is visible to both sessions on this page `
                + `(${Object.keys(mine.nums).length} vs ${Object.keys(theirs.nums).length} rendered, `
                + `${roleScoped} sharing an id under different labels) — nothing to compare`;
            } else if (differ.length) {
              rec.two_sided = { ok: false, verdict: `${differ.length} of ${shared.length} shared figure(s) `
                + `DISAGREE between two concurrent sessions of the SAME identity: ${differ.slice(0, 4).join(' · ')}` };
            } else {
              rec.two_sided = { ok: true, verdict: `all ${shared.length} figure(s) visible to BOTH `
                + `sessions of this identity, under the SAME label, agree; ${roleScoped} further figure(s) share an id but `
                + 'carry different labels and are deliberately role-scoped, so they are not comparable' };
            }
          }
        }
        await other.ctx.close();
      }

      // ── J3 · cross_surface_handoff — follow a link out and arrive somewhere that works.
      if (wants('j3')) {
      const h = await walkHandoff(ctxA, p, REASONED_EMPTY_SRC);
      if (h.error) rec.handoff = { ok: false, verdict: `could not be walked: ${h.error}` };
      // Left OWED rather than failed — but the REASON is recorded, because an unexplained gap in
      // coverage is indistinguishable from an oversight when someone reads this later.
      else if (h.na) { rec.handoff = null; rec.handoffNa = h.na; }
      // AN ANON PERSONA MEETING THE AUTH WALL HAS NOT HAD A BROKEN HANDOFF — the same exemption J1
      // already makes, and omitting it from J3 was an inconsistency in this instrument, not a finding
      // about the product. index's anon visitor clicking "Hive Live Board: Join or create…" is
      // SUPPOSED to land on sign-in; a members-only destination that let them straight in would be
      // the actual defect.
      else if (h.landed !== h.link.file && anonish && /^index/.test(h.landed))
        rec.handoff = { ok: true, verdict: `"${h.link.text}" -> the auth wall at "${h.landed}" `
          + `instead of ${h.link.file}, which is correct for an ${idA} persona following a `
          + `members-only link; no claim is made about ${h.link.file}'s own content` };
      else if (h.landed !== h.link.file) rec.handoff = { ok: false, verdict: `the link "${h.link.text}" `
        + `promised ${h.link.file} and the walker landed on ${h.landed} — the handoff did not go where `
        + 'the link said it would' };
      else if (h.reading.actionable < 3 || (h.reading.chars < 300 && !h.reading.reasonedEmpty))
        rec.handoff = { ok: false, verdict: `handed off to ${h.landed} and arrived at a dead end `
          + `(${h.reading.actionable} controls / ${h.reading.chars} chars)` };
      else if (h.keptParam === false) rec.handoff = { ok: false, verdict: `the link carried context `
        + `(?${h.link.param}) into ${h.landed} and the destination DROPPED it` };
      else rec.handoff = { ok: true, verdict: `"${h.link.text}" -> ${h.landed}: landed where the link `
        + `promised, ${h.reading.chars} chars / ${h.reading.actionable} control(s)`
        + `${h.keptParam ? `, and the ?${h.link.param} context survived` : ', no context param to carry'}` };
      }

      // ── J5 · abandon_resume — type, get called away, come back; nothing may have half-landed.
      if (wants('j5')) {
      const t = TARGETS.find((x) => x.page === p && (x.kind || 'dialog') === 'dialog'
                                 && !x.unreachable && !x.notDrivable && x.modal);
      if (!t) {
        // Left OWED on purpose. "This surface has nothing to abandon" is a fact about a read-only page,
        // not a defect, and inventing a red for it would be exactly the vacuity R10 forbids.
        rec.abandon = null;
        rec.abandonNa = 'no drivable composer for this page in dialog_targets.mjs';
      } else {
        const r5 = await walkAbandon(ctxA, p, t);
        // AN ANON PERSONA HAS NO COMPOSER BECAUSE THEY MAY NOT COMPOSE — that is authorisation working,
        // not a defect, so the walk failing to open one is NOT APPLICABLE rather than a red. This is the
        // FOURTH place this same exemption was needed (J1's redirect, J3's handoff, J4's two sessions,
        // now J5's composer), which is the tell that 'what does this persona legitimately not get to do?'
        // belongs in one place rather than being remembered per oracle. Noted rather than refactored
        // mid-walk: changing the shared path now would invalidate the readings already in flight.
        if (r5.error && anonish) {
          rec.abandon = null;
          rec.abandonNa = `no composer reachable for an ${idA} persona (${r5.error.slice(0, 60)}) — `
            + 'this identity may not compose here, so there is nothing to abandon';
        }
        else if (r5.error) rec.abandon = { ok: false, verdict: `could not be walked: ${r5.error}` };
        // NOT APPLICABLE, NOT FAILED — the third time this distinction came up in one prover, so it is
        // worth stating plainly: a page whose dialog has no text field has nothing to abandon, and
        // banking a red for an absent property is the vacuity R10 forbids. Row stays OWED, reason kept.
        else if (r5.na) { rec.abandon = null; rec.abandonNa = r5.na; }
        else if (r5.inContent) rec.abandon = { ok: false, verdict: `HALF-LANDED — text typed into `
          + `"${r5.field}" and never submitted is present in the page's CONTENT after leaving and `
          + 'returning. A person called away mid-entry now has a record they did not commit.' };
        else rec.abandon = { ok: true, verdict: `abandoning left nothing behind in the page's content`
          + `${r5.inField ? ' (the text was preserved in its field as a DRAFT, which is deliberate and '
          + 'is not a half-landing)' : ''}; body ${r5.before} -> ${r5.chars} chars` };
      }
      }

      await ctxA.close(); if (ctxB) await ctxB.close();
    } catch (e) {
      const msg = String(e.message || e).slice(0, 140);
      rec.first_run = { ok: false, verdict: `journey could not be constructed: ${msg}` };
      rec.repeat = { ok: false, verdict: `journey could not be constructed: ${msg}` };
    }
    results.push(rec);
    // A SKIPPED journey is not a FAILED one. Printing 'FAIL undefined' for a journey this run never
    // asked for is how a selective re-walk looks like a catastrophe in its own log.
    const mark = (o) => (o ? (o.ok ? 'PASS' : 'FAIL') : ' -- ');
    const f = rec.first_run; const r2 = rec.repeat; const t4 = rec.two_sided; const a5 = rec.abandon;
    const h3 = rec.handoff;
    const say = [f, r2, t4, h3, a5].filter((o) => o && !o.ok)[0] || f || r2 || t4 || h3 || a5 || {};
    console.log(`  ${(p + ' ' + rec.slot).padEnd(28)} first_run ${mark(f)}  repeat ${mark(r2)}  `
      + `two_sided ${mark(t4)}  handoff ${mark(h3)}  abandon ${mark(a5)}  `
      + `${String(say.verdict || '').slice(0, 38)}`);
  }
}
await browser.close();

const graded = results.filter((r) => r.first_run);
const badFirst = graded.filter((r) => !r.first_run.ok);
const badRepeat = graded.filter((r) => r.repeat && !r.repeat.ok);
const badTwoSided = results.filter((r) => r.two_sided && !r.two_sided.ok);
const badAbandon = results.filter((r) => r.abandon && !r.abandon.ok);
const badHandoff = results.filter((r) => r.handoff && !r.handoff.ok);
writeFileSync(OUT, JSON.stringify({
  totals: { walked: results.length, graded: graded.length,
            first_run_failing: badFirst.length, repeat_failing: badRepeat.length,
            two_sided_failing: badTwoSided.length,
            two_sided_walked: results.filter((r) => r.two_sided).length,
            abandon_failing: badAbandon.length,
            abandon_walked: results.filter((r) => r.abandon).length,
            handoff_failing: badHandoff.length,
            handoff_walked: results.filter((r) => r.handoff).length },
  personas: results,
}, null, 1));
console.log(`
  wrote ${OUT}`);
console.log(`  ${results.length} persona(s) · J1/J2 walked ${graded.length} (first_run failing `
  + `${badFirst.length}, repeat failing ${badRepeat.length}) · J4 walked `
  + `${results.filter((r) => r.two_sided).length} (failing ${badTwoSided.length}) · J3 walked `
  + `${results.filter((r) => r.handoff).length} (failing ${badHandoff.length}) · J5 walked `
  + `${results.filter((r) => r.abandon).length} (failing ${badAbandon.length})`);
// NON-VACUITY, scoped to what this run actually asked for. The rail is "zero failures over zero
// measurements is a FAIL, louder than a real one" — but it must count the journeys REQUESTED, or a
// deliberate `--journeys j4` run reports a catastrophe because J1 produced nothing.
const measured = (wants('j1') || wants('j2') ? graded.length : 0)
               + (wants('j4') ? results.filter((r) => r.two_sided).length : 0)
               + (wants('j5') ? results.filter((r) => r.abandon).length : 0)
               + (wants('j3') ? results.filter((r) => r.handoff).length : 0);
if (!measured) {
  console.log('  FAIL — NOTHING WAS MEASURED. Zero failures over an empty denominator is not a pass.');
}
for (const r of badFirst) console.log(`  FAIL first_run ${r.page} ${r.slot}: ${r.first_run.verdict.slice(0, 110)}`);
for (const r of badRepeat) console.log(`  FAIL repeat   ${r.page} ${r.slot}: ${r.repeat.verdict.slice(0, 110)}`);
for (const r of badTwoSided) console.log(`  FAIL two_sided ${r.page} ${r.slot}: ${r.two_sided.verdict.slice(0, 110)}`);
for (const r of badAbandon) console.log(`  FAIL abandon  ${r.page} ${r.slot}: ${r.abandon.verdict.slice(0, 110)}`);
for (const r of badHandoff) console.log(`  FAIL handoff  ${r.page} ${r.slot}: ${r.handoff.verdict.slice(0, 110)}`);
if (GATE) process.exit(badFirst.length + badRepeat.length + badTwoSided.length + badAbandon.length + badHandoff.length || !measured ? 1 : 0);
