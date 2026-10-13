// prover_harness — the shared preamble every live prover kept re-implementing (2026-09-05, synthesis verdict 1 of the
// P-program pain register: "the instrument was wrong more often than the page"). Each copy grew its own blind spot -
// an offsetParent visibility test that could not see a fixed-position notice, a seller profile walked with the wrong
// query key, a service-worker prover that navigated signed out. One harness, one set of calibrations:
//   SEEDER / HIVE / WORKER     - the local seeder origin and the supervisor identity every prover signs in as
//   signIn(ctx)                - sign in on shift-brain.html and stamp the identity keys (session + localStorage)
//   PAGE_QUERY                 - pages that need a query to render at all, keyed by file (the page's OWN key)
//   VIS_JS                     - the visibility predicate to use INSIDE page.evaluate (checkVisibility, never offsetParent)
//   psql(sql) / psqlAs(worker, sql) - the local DB as postgres, or AS a signed-in person (SET LOCAL ROLE + jwt claims,
//                                 rolled back) for truth views that carry an admin/member predicate
//   settleWait(ms)             - the retry envelope (~9 s) + the last settle pass (15 s) = 17 s default
// Import: import { SEEDER, HIVE, signIn, PAGE_QUERY, VIS_JS, psql, psqlAs, SETTLE_MS } from './prover_harness.mjs';
import { execSync } from 'node:child_process';

export const SEEDER = process.env.WH_SEEDER_URL || 'http://127.0.0.1:5000';
export const HIVE = '084c113b-99c0-45c6-a8e8-b4b8349da46d';           // Baguio Textile Mills
export const WORKER = { name: 'Leandro Marquez', first: 'Leandro', role: 'supervisor', hiveName: 'Baguio', email: 'leandromarquez@auth.workhiveph.com', password: 'test1234' };
export const SETTLE_MS = 17000;
// the DB-backed pages every whole-page prover walks (the degradation prover's roster; grown 2026-09-05 with public-feed/promo-poster)
export const DB_PAGES = [
  'platform-actions.html', 'alert-hub.html', 'analytics.html', 'assistant.html', 'community.html', 'engineering-design.html',
  'inventory.html', 'ai-quality.html', 'founder-console.html', 'marketplace-admin.html', 'plant-connections.html',
  'agentic-rag-observability.html', 'marketplace-seller-profile.html', 'achievements.html', 'analytics-report.html',
  'asset-hub.html', 'audit-log.html', 'dayplanner.html', 'hive.html', 'logbook.html', 'marketplace-seller.html',
  'public-feed.html', 'promo-poster.html',
];
// a page that needs a query to render at all - keyed by the page's OWN parameter name (urlParams.get('worker'), not 'seller')
export const PAGE_QUERY = { 'marketplace-seller-profile.html': '?worker=Isidro%20Suarez' };
// visibility INSIDE the page: a position:fixed notice or a sticky header has NO offsetParent and is still on screen
// ★BARE checkVisibility() CALLS A HIDDEN ELEMENT VISIBLE (2026-09-29). Every option defaults to FALSE,
// so `e.checkVisibility()` tests only `display:none` and an empty box - it returns TRUE for
// `visibility:hidden` and for `opacity:0`. Measured on index.html at 320: all four nav-hub controls
// (#wh-hub-open-companion, #wh-hub-open-feedback, #wh-hub-global-search, #wh-hub-search) compute
// `visibility: hidden; pointer-events: none` because the hub panel is CLOSED, and this predicate said
// visible for all four. The occlusion check then dutifully reported each one "covered" by whatever sits
// above a closed panel - 18 findings on marketplace.html, 17 on public-feed.html, 6 on index.html, none
// of them real. A closed panel's buttons are not occluded controls; they are not controls on screen at all.
// The correct form was already in this repo: phone_fit_audit.mjs's own fallback passes
// `{ visibilityProperty: true }`. Only the SHARED predicate, which every prover importing VIS_JS uses,
// never did - so the fix belongs here rather than in one caller.
// opacityProperty and contentVisibilityAuto are included for the same reason: a fully transparent control
// and a `content-visibility:auto` subtree that was never rendered are both invisible to the person the
// walk is meant to be standing in for.
export const VIS_JS = "(function (e) { return !!e && (typeof e.checkVisibility === 'function' ? e.checkVisibility({ visibilityProperty: true, opacityProperty: true, contentVisibilityAuto: true }) : e.offsetParent !== null); })";

// ★A GATE SPENT A LIVE MODEL CALL BY ARRIVING (2026-10-07). shift-brain's maybeAutoGenerate invokes
// shift-planner-orchestrator - a real LLM briefing over the provider keys in supabase/functions/.env - on the
// first open of a shift that has no fresh shift_plans row. signIn below opens shift-brain for EVERY prover that
// imports it, and prove_render_contract opens it again as a surface under test. Measured: a render-contract run
// on four pages wrote a 814-character model briefing ("Signed by Zaniah...") at 17:31:40 UTC. callAI writes
// nothing to ai_cost_log, so the meter cannot see this spend; the witness is shift_plans.briefing prose.
// The rule (Ian): live model calls only for the LLM layer's Grounding and Routing rows, with spend stated first.
// So every context that signs in through this helper gets the load-time model functions answered with a 503,
// the same stub the W3 journey walker uses; the page takes its own "briefing unavailable" path. A prover that
// is ABOUT the model's answer sets WH_LIVE_MODEL=1 and states its spend before it runs. Limit: a prover that
// later registers its own catch-all `**/*` context route that calls route.continue() runs before this one
// (Playwright runs the newest matching route first) and must stub these functions itself.
export const LOAD_TIME_MODEL_FNS = ['shift-planner-orchestrator'];
export async function stubModelCalls(ctx) {
  if (!ctx || ctx._whModelStub || process.env.WH_LIVE_MODEL === '1') return;
  ctx._whModelStub = { hits: 0 };
  for (const fn of LOAD_TIME_MODEL_FNS) {
    await ctx.route(`**/functions/v1/${fn}**`, (route) => {
      ctx._whModelStub.hits += 1;
      return route.fulfill({ status: 503, contentType: 'application/json',
        body: JSON.stringify({ error: 'model call stubbed by the prover harness (WH_LIVE_MODEL unset)' }) });
    });
  }
}

export async function signIn(ctx, opts = {}) {
  const who = { ...WORKER, ...opts };
  await stubModelCalls(ctx);
  const s = await ctx.newPage();
  await s.goto(`${SEEDER}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  // ★THE WAIT COVERED TWO OF THE THREE THINGS THE NEXT LINE USES, AND THIS IS THE SIGN-IN FOR 48 TOOLS
  // (2026-09-10). `window.SUPABASE_KEY` only exists because shift-brain.html declares its key with
  // `var`; a top-level `const` creates no window property, and 23 of the platform's 27 key-declaring
  // pages use `const`. So this line has worked by luck rather than by design, and the day anyone made
  // that one declaration match the majority style, every prover importing this helper would have lost
  // its fallback silently - the library answering "supabaseKey is required.", which names an argument
  // and not the cause. Waiting for the page's OWN client first is the durable fix (every app page
  // builds it at parse), with the key as the alternative; 27 provers already wait for the key this way,
  // so this brings the shared helper in line with the pattern the platform already trusts.
  await s.waitForFunction(() => !!window._whSupabaseClient
    || (typeof window.getDb === 'function' && !!window.supabase && !!window.SUPABASE_KEY),
  { timeout: 15000 }).catch(() => {});
  const ok = await s.evaluate(async ({ hive, who }) => {
    try {
      if (!window._whSupabaseClient && !window.SUPABASE_KEY) {
        return 'the sign-in page exposed no key and built no client of its own';
      }
      const db = window._whSupabaseClient || window.getDb('http://127.0.0.1:54321', window.SUPABASE_KEY);
      const { error } = await db.auth.signInWithPassword({ email: who.email, password: who.password });
      localStorage.setItem('wh_active_hive_id', hive); localStorage.setItem('wh_last_worker', who.name); localStorage.setItem('wh_hive_role', who.role);
      // wh_hive_name too: a real arrival stores it, and pages that only READ it (the audit-log export names the
      // hive from this key) otherwise render "(unnamed)" - a probe artifact that reads exactly like a defect.
      try {
        const { data: _h } = await db.from('hives').select('name').eq('id', hive).maybeSingle();
        if (_h && _h.name) localStorage.setItem('wh_hive_name', _h.name);
      } catch (e) { void e; }

      return !error;
    } catch (e) { return false; }
  }, { hive: opts.hive || HIVE, who });
  await s.close();
  return ok;
}

// ★A PROVER THAT DOES NOT CHECK THIS RETURN FABRICATES EVERY AUTH-GATED READING (added 2026-10-05).
// `signIn` above RETURNS - it never throws - so `await signIn(ctx);` leaves a failed sign-in completely
// silent. The walk then continues SIGNED OUT, every auth-gated page redirects to index, and the prover
// measures a redirect stub: "the page said NOTHING", "0 rows", "no busy indicator". Those readings are
// indistinguishable from real findings and they get BANKED as evidence. Measured 2026-08-20 on
// prove_failure_injection: analytics-report (369 chars) and engineering-design (1845 chars) were both
// reported as silently failing, and both merely redirect when signed out. A sweep on 2026-10-05 found
// 57 unchecked call sites still live across 50 provers, the third time this class has been found
// ([[feedback_fifty_nine_provers_discard_their_sign_in]]).
//
// ★WHY THIS LIVES HERE AND IS NOT live_page_journeys' assertSignedIn. THE TWO signIn FUNCTIONS HAVE
// DIFFERENT CONTRACTS, and that difference is a loaded trap: live_page_journeys.signIn() resolves to
// `{ok, err, anon, ...}` and its assertSignedIn reads `r.ok`. THIS one resolves to a BOOLEAN. Passing
// `true` to that guard evaluates `!r.ok` on a primitive - undefined - so it would throw SIGN-IN FAILED
// on a SUCCESSFUL sign-in, and the 40 provers importing from this module would all die at once while
// looking hardened. `node --check` cannot see that; only reading both contracts can. So each module
// carries the guard that matches its own return shape, and the names match deliberately: a call site
// reads the same in either family and resolves to the correct implementation through its own import.
export async function assertSignedIn(p) {
  let ok;
  try { ok = await p; }
  catch (e) { throw new Error(`SIGN-IN THREW: ${e && e.message ? e.message : e}`); }
  // tolerate the OTHER contract rather than mis-grading it, in case a caller is ever re-pointed: an
  // object is judged by .ok, a primitive by truthiness.
  const good = (ok && typeof ok === 'object') ? (ok.anon === true || ok.ok === true) : !!ok;
  if (!good) {
    throw new Error('SIGN-IN FAILED -- refusing to walk signed-out: every auth-gated page would redirect '
      + 'and be reported as "the page said nothing", which is a fabricated finding, not a measurement');
  }
  return ok;
}

export const psql = (sql) => { try { return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim(); } catch (e) { return ''; } };

// the count AS a signed-in person: truth views with an admin/member predicate return nothing to a plain postgres session
export const psqlAs = (worker, sql) => {
  const uid = psql(`select auth_uid from hive_members where worker_name = '${worker}' and status = 'active' limit 1`);
  if (!uid) return '';
  const out = psql(`begin; set local role authenticated; select set_config('request.jwt.claims', '{"sub":"${uid}","role":"authenticated"}', true); ${sql}; rollback;`);
  const nums = out.split(/[\r\n]+/).map((l) => l.trim()).filter((l) => /^\d+$/.test(l));
  return nums.length ? nums[nums.length - 1] : '';
};

// Self-test (no browser): `node tools/prover_harness.mjs --self-test` - the DB helpers answer, the impersonated count
// is a number, PAGE_QUERY keys are the pages' own parameters, and VIS_JS evaluates to a function that treats a
// disconnected element as invisible. A harness with no teeth would hand every prover the same silent blind spot.
if (process.argv.includes('--self-test')) {
  const fails = [];
  if (psql('select 1') !== '1') fails.push('psql cannot reach the local DB');
  if (!/^\d+$/.test(psqlAs(WORKER.name, 'select count(*) from hive_members'))) fails.push('psqlAs did not return a count as the signed-in worker');
  if (!/^\?worker=/.test(PAGE_QUERY['marketplace-seller-profile.html'])) fails.push("seller profile query must use the page's own key (?worker=)");
  let visFn = null; try { visFn = (0, eval)(VIS_JS); } catch (e) { fails.push('VIS_JS does not evaluate: ' + e.message); }
  if (visFn && visFn(null) !== false) fails.push('VIS_JS must treat a missing element as invisible');
  if (visFn && visFn({ checkVisibility: () => true }) !== true) fails.push('VIS_JS must honour checkVisibility()');
  if (visFn && visFn({ offsetParent: null }) !== false) fails.push('VIS_JS falls back to offsetParent when checkVisibility is absent');
  // ★AND IT MUST ASK FOR THE OPTIONS, which is the bug this file shipped until 2026-09-29: every option
  // defaults to FALSE, so a bare checkVisibility() called `visibility:hidden` and `opacity:0` VISIBLE and
  // the occlusion check reported a closed nav-hub panel's buttons as covered controls (18 findings on
  // marketplace.html alone, none real). The assertions above could not see that - both pass against a
  // predicate that ignores the options entirely - so this records WHAT WAS ASKED, not just that the modern
  // API was reached for.
  if (visFn) {
    let asked = null;
    visFn({ checkVisibility: (o) => { asked = o; return true; } });
    for (const k of ['visibilityProperty', 'opacityProperty', 'contentVisibilityAuto']) {
      if (!asked || asked[k] !== true) fails.push(`VIS_JS must pass ${k}:true — without it checkVisibility() calls a hidden element visible`);
    }
  }
  console.log(fails.length ? 'FAIL prover-harness self-test - ' + fails.join('; ') : 'self-test OK: psql + psqlAs answer, PAGE_QUERY uses the page\'s own key, VIS_JS prefers checkVisibility');
  process.exit(fails.length ? 1 : 0);
}
