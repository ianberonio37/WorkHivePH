// live-state-runner.js — induce each owed-scenario state in a REAL browser and report a verdict.
//
// Ian, 2026-08-04: "it should be live mcp walks on every owed". The batch harness
// (tools/walk_owed_scenarios.mjs) drives its own headless Chromium; this module runs the SAME
// inductions inside whatever browser is actually open, so the evidence behind a banked row comes
// from the live MCP session rather than a separate headless process.
//
// It is served from the web root on purpose: the MCP evaluates a one-line import instead of pasting
// a 60-line function per surface, which keeps each walk cheap and makes the walk reproducible by
// hand — open any page and run `(await import('/workhive/live-state-runner.js')).run()`.
//
// Two rules it inherits from the harness, both learned the hard way:
//   · a failure is served as a REAL 500 response, never a rejected promise (a rejection leaves a
//     stuck skeleton and proves something else entirely)
//   · `error` is judged as a CONTRAST against this same surface rendered with zero rows, because the
//     oracle is "a failed read must not look like an empty one" — a keyword hunt flunks pages whose
//     erroring pane is correct while some other pane is legitimately empty

const REST = /\/rest\/v1\/(?!rpc\/)/;

// THE WRITE GUARD MUST NOT REUSE THE READ PATTERN. Every induction in this file opens with
// `if (!REST.test(u)) return orig(i, x)` — and REST deliberately EXCLUDES /rest/v1/rpc/, because an
// RPC is not a table read to be rewritten. The consequence was that a mutation sent through an RPC
// (or an edge function) matched no guard and went straight to the shared database, which is the one
// thing this bank may never do. Found while walking the post form: submitting it fires
// `POST /rest/v1/rpc/get_marketplace_price_comps` alongside the table insert, and only an ad-hoc
// probe that keyed on the METHOD caught it — the module's own guards would have forwarded it.
// So: writes are decided by the VERB across the whole Supabase surface, before any read logic.
// ...BUT THE VERB ALONE OVER-BLOCKS, AND OVER-BLOCKING FALSIFIES THE WALK. PostgREST sends EVERY
// rpc as a POST, including the read-only ones, so a verb-only guard stubbed `service_knob_pct` to
// `[]` — the exact knob whose misreading made the credits-back chip vanish from every listing, i.e.
// the defect this whole bank was built around. A probe that silently blanks a read is not safer, it
// is wrong in a way that looks like a finding.
//
// The database settles it rather than a guess: a STABLE or IMMUTABLE function CANNOT write (Postgres
// refuses), so those names are safe to forward and everything else (VOLATILE) is blocked. Derived
// from pg_proc, and regenerated with:
//   select string_agg(distinct proname, ',' order by proname) from pg_proc p
//   join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and p.provolatile in ('i','s');
// An RPC missing from this list fails CLOSED — blocked, never forwarded — so a stale list costs
// fidelity on one probe, never a write to the shared database.
const RPC_READONLY = new Set(('auth_worker_names,check_username_available,export_hive_data,find_hive_by_code,' +
  'get_adoption_risk_current,get_community_reputation,get_community_reputation_by_auth,get_downtime_pareto,' +
  'get_failure_frequency,get_hive_board_dashboard,get_hive_dashboard,get_hive_trade_peers,' +
  'get_marketplace_parts_for_my_assets,get_marketplace_price_comps,get_marketplace_seller_public,' +
  'get_marketplace_trust_badges,get_mtbf_by_machine,get_mttr_by_machine,get_oee_by_machine,' +
  'get_pm_compliance_smrp,get_pm_ontime_delivery,get_project_budget,get_repeat_failures,' +
  'get_saved_search_matches,get_seller_community_reputation,hive_has_other_members,is_marketplace_admin,' +
  'is_platform_admin,listing_reservation_amount,match_persona_knowledge,match_procedural_memories,' +
  'my_credit_balance,my_service_provider_ids,person_credit_balance,provider_credit_balance,' +
  'provider_is_certified_for,search_all_knowledge,search_bom_knowledge,search_calc_knowledge,' +
  'search_fault_knowledge,search_pm_knowledge,search_skill_knowledge,search_voice_journal_entries,' +
  'seller_credit_balance,service_agreed_base,service_knob,service_knob_pct,service_objection_deadline,' +
  'service_request_price,show_limit,slo_error_budget,unified_event_source_rank,user_can_access_hive,' +
  'user_hive_ids,user_hive_worker_names,user_supervisor_hive_ids').split(','));

const SUPA = /\/rest\/v1\/|\/functions\/v1\/|\/storage\/v1\//;
const MUTV = /^(POST|PATCH|PUT|DELETE)$/i;
const _verbOf = (i, x) => ((x && x.method) || (i && i.method) || 'GET').toUpperCase();
const _stubResponse = () => new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } });
// A GUARD THAT LEAKED THE WRITES IT REPORTED BLOCKING (found + fixed 2026-08-04).
// This used to return the bare Response. fetch() returns a PROMISE of a Response, so a caller doing
// the documented thing -- `const stub = blockWrite(i, x, sink); if (stub) return stub;` inside a
// window.fetch wrapper -- handed supabase-js a Response where it expected a thenable. postgrest-js
// then hit `TypeError: fetch(...).finally is not a function`, fell back to dynamically importing a
// fetch polyfill, and RE-ISSUED THE POST FOR REAL. The write landed roughly 35 seconds later, long
// after the walk had moved on, while `sink` cheerfully recorded it as blocked. Three probe rows
// reached the shared community_posts table today under a guard that reported 1 blocked / 0 written;
// each was found only by a delayed re-count and deleted by hand.
// The lesson generalises past this file: a test double must satisfy the FULL contract of what it
// replaces. Half a fetch is not a fetch, and the failure mode was not a visible error -- it was a
// silent success somewhere else, later, which is the worst shape a guard can fail in.
// Returns a Promise<Response> for any mutating call to Supabase, or null to let the caller proceed.
// `sink` (optional) records what was stopped so a walk can prove the guard fired.
export function blockWrite(i, x, sink) {
  const u = typeof i === 'string' ? i : (i && i.url) || '';
  if (!SUPA.test(u) || !MUTV.test(_verbOf(i, x))) return null;
  const rpc = u.match(/\/rest\/v1\/rpc\/([A-Za-z0-9_]+)/);
  if (rpc && RPC_READONLY.has(rpc[1])) return null;      // provably write-incapable; forward it
  if (sink) sink.push(_verbOf(i, x) + ' ' + u.replace(/^https?:\/\/[^/]+/, '').slice(0, 64));
  return Promise.resolve(_stubResponse());
}
// Kept for the in-module callers that already wrap the value in their own Promise/timeout.
const _stub = () => _stubResponse();

// ── installWriteGuard — the ONE way a recovery walk should arm itself ────────────────────────────
// Every BK-ux-recovery probe needs the same three things: block every write, hold the one it cares
// about open long enough to measure the in-flight window, and be able to answer it with a 401.
// Hand-rolling that per walk is what leaked rows. On 2026-08-04 a seller-dashboard probe matched
// `/rest/v1/(audit_log|marketplace_audit)/` and stubbed the listing PATCH correctly -- but the real
// table is `hive_audit_log`, which that pattern does not match, so three `edit_listing` rows reached
// the shared audit log for edits that never happened. The listing was untouched and the audit log
// said otherwise, which is worse than either alone. Found by a psql re-count, deleted by hand.
// blockWrite was already right (it decides by VERB across the whole Supabase surface, so it would
// have caught hive_audit_log); the defect was reaching past it. So the guard ships as something you
// INSTALL, not something you re-derive:
//
//   const g = installWriteGuard({ match: /service_requests/, stallMs: 1300 });
//   ...drive the control...
//   g.calls          // writes that reached the matched endpoint -- assert this is > 0 before
//                    // reading any result: a probe that never fired measures nothing
//   g.mode = '401'   // next matched write answers 401
//   g.blocked        // everything else that was stopped, so a walk can prove nothing escaped
//   g.restore()
//
// `match` only chooses which write is SLOWED and observable. Everything else is still blocked --
// there is no opt-out, because the tables a walk forgets are exactly the ones that leak.
export function installWriteGuard(opts) {
  const o = opts || {};
  const g = { calls: 0, blocked: [], urls: [], mode: o.mode || 'stub', stallMs: o.stallMs || 0 };
  const orig = window.__lsrFetch || window.fetch.bind(window);
  window.__lsrFetch = orig;
  g.restore = () => { window.fetch = orig; };
  window.fetch = async (i, x) => {
    const u = typeof i === 'string' ? i : (i && i.url) || '';
    const watched = o.match && o.match.test(u) && MUTV.test(_verbOf(i, x));
    if (watched) {
      g.calls++;
      g.urls.push(_verbOf(i, x) + ' ' + u.replace(/^https?:\/\/[^/]+\/rest\/v1\//, '').slice(0, 56));
      if (g.stallMs) await new Promise(r => setTimeout(r, g.stallMs));
      if (g.mode === '401') {
        return new Response(JSON.stringify({ message: 'JWT expired', code: 'PGRST301' }),
          { status: 401, headers: { 'Content-Type': 'application/json' } });
      }
      // PostgREST answers a bare PATCH/DELETE with 204 AND NO BODY. A stub that sends '[]' with a 204
      // is malformed, and the page's honest "Save failed" then reads like a product defect.
      const verb = _verbOf(i, x);
      return (verb === 'PATCH' || verb === 'DELETE')
        ? new Response(null, { status: 204 })
        : new Response(JSON.stringify([{ id: '00000000-0000-0000-0000-0000000000ff' }]),
            { status: 201, headers: { 'Content-Type': 'application/json' } });
    }
    const stub = blockWrite(i, x, g.blocked);
    if (stub) return stub;
    return orig(i, x);
  };
  return g;
}

// ── watchToasts — a page's "it landed" message, in whichever dialect that page speaks ────────────
// Three dialects met in one day, and each one silently blinded a probe that assumed another:
//   marketplace.html    rewrites #toast's textContent and adds .show
//   platform-actions    APPENDS a .toast-msg child and never touches #toast's class
//   community.html      same container-append shape, different child class
// A probe that demanded .show saw platform-actions fire and threw the message away, and I nearly
// filed "no confirmation after approving a listing" as a defect on a page that says
// "Listing approved: now live to buyers." Handle both shapes, and SELF-TEST before trusting it --
// the returned object's .ok is false if the observer could not see a message it planted itself.
// MutationObserver callbacks are microtasks, so the self-test awaits a tick; reading synchronously
// reports a working observer as broken.
export async function watchToasts(sel) {
  const el = document.querySelector(sel || '#toast');
  if (!el) return { ok: false, msgs: [], note: 'no toast element on this surface' };
  const msgs = [];
  const obs = new MutationObserver(muts => {
    muts.forEach(m => m.addedNodes.forEach(n => {
      if (n.nodeType !== 1) return;
      const t = (n.textContent || '').trim();
      if (t && msgs[msgs.length - 1] !== t) msgs.push(t);
    }));
    const own = (el.textContent || '').trim();
    if (/\bshow\b/.test(el.className) && own && msgs[msgs.length - 1] !== own) msgs.push(own);
  });
  obs.observe(el, { attributes: true, childList: true, characterData: true, subtree: true });
  const probe = document.createElement('div');
  probe.className = 'toast-msg'; probe.textContent = '__watchToasts selftest__';
  el.appendChild(probe);
  await new Promise(r => setTimeout(r, 80));
  const ok = msgs.includes('__watchToasts selftest__');
  probe.remove(); msgs.length = 0;
  return { ok, msgs, clear: () => { msgs.length = 0; }, stop: () => obs.disconnect() };
}
const LONG = 'Emergency Switchgear Overhaul and Transformer Oil Regeneration for the Southern Tagalog Industrial Estate Incorporated';
const BAYBAYIN = 'ᜋᜄᜈ᜔ᜆᜅ᜔ ᜃᜄᜋᜒᜆᜈ᜔ ᜐ ᜉᜎᜒᜃ';
const ERR = /couldn['’]?t load|could not load|failed to load|unavailable|something went wrong|error/i;
const INVITE = /no .{0,24}yet|be the first|get started|hail your first|post your first/i;

// Every page names its data path differently. A loader this list does NOT know simply never re-runs,
// so the induced condition never reaches the screen and the probe compares the page to itself —
// which is exactly how public-feed.html reported "error looks identical to empty" while its real
// behaviour (measured on a fresh load with the failure already in place) is a correct
// "Couldn't load the public feed ... Retry". The tell was longNameRendered=false: no re-fetch.
const LOADERS = ['loadListings', 'loadCounts', 'loadClientServices', 'loadServices', 'refreshQueues',
                 'loadFeed', 'loadPosts', 'loadAchievements', 'loadProfile', 'loadSeller',
                 'loadInitial', 'fetchPage', 'loadMore', 'init'];

function read() {
  const m = document.querySelector('main') || document.body;
  const t = (m.innerText || '').replace(/\s+/g, ' ').trim();
  const over = [...m.querySelectorAll('*')].filter(el =>
    el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0 &&
    getComputedStyle(el).overflowX === 'visible' &&
    !el.closest('details:not([open])')).length;
  return {
    t, len: t.length, over,
    doc: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    junk: (t.match(/\bundefined\b|\bNaN\b|\[object Object\]/g) || []).length,
    ctrls: [...m.querySelectorAll('button,a[href],input,select')].filter(e => e.offsetParent).length,
    innerWidth: window.innerWidth,
  };
}

async function rerun(ms) {
  document.dispatchEvent(new Event('DOMContentLoaded'));
  let ran = 0;
  for (const k of LOADERS) {
    if (typeof window[k] === 'function') {
      ran++;
      // empty-catch-allow: a page exposes several loaders and some throw when their pane is not
      // open. The probe wants whichever ones DO run; a throw from one must not stop the others.
      try { await window[k](); } catch (e) { /* empty-catch-allow: see above */ }
    }
  }
  await new Promise(r => setTimeout(r, ms || 1700));
  return ran;
}

export async function run() {
  const orig = window.__lsrFetch || window.fetch;
  window.__lsrFetch = orig;
  const set = fn => { window.fetch = fn; };
  const out = {};

  // POPULATED — the surface as it actually stands right now
  {
    const s = read();
    out.populated = {
      ok: s.len > 120 && s.doc <= 0 && s.junk === 0 && !ERR.test(s.t),
      len: s.len, docOverflow: s.doc, junk: s.junk, unclipped: s.over,
      note: 'structural half only: number-vs-source-of-truth is checked by the psql-backed rows',
    };
  }

  // EMPTY — every read returns zero rows.
  //
  // A BARE `[]` IS NOT AN EMPTY DATABASE, IT IS AN UNKNOWN COUNT. PostgREST answers a
  // `count: 'exact'` query with a Content-Range header, and supabase-js reads the count from THERE,
  // not from the body — so a stub that omits it hands the page `count: null`, which a
  // correctly-written page reports as "unavailable" rather than as zero. That is the page being
  // right and the probe being unfaithful: it scored marketplace's empty state as
  // renderedAsFailure the moment the page learned to tell absent from zero. Send what the real
  // server sends for no rows.
  const EMPTY_HEADERS = { 'Content-Type': 'application/json', 'Content-Range': '*/0' };
  const wrote = [];
  set(async (i, x) => {
    const u = typeof i === 'string' ? i : (i && i.url) || '';
    const b = blockWrite(i, x, wrote); if (b) return b;
    return REST.test(u) ? new Response('[]', { status: 200, headers: EMPTY_HEADERS }) : orig(i, x);
  });
  await rerun();
  const emptyText = read().t;
  {
    const s = read();
    const namesGap = INVITE.test(s.t) || /\b(no|none|nothing|empty|0)\b/i.test(s.t);
    out.empty = { ok: namesGap && s.ctrls > 0 && !ERR.test(s.t), namesGap, controls: s.ctrls, renderedAsFailure: ERR.test(s.t) };
  }

  // ERROR — a real 500, judged against the empty render above
  set(async (i, x) => {
    const u = typeof i === 'string' ? i : (i && i.url) || '';
    const b = blockWrite(i, x, wrote); if (b) return b;
    return REST.test(u)
      ? new Response(JSON.stringify({ code: '500', message: 'induced failure' }), { status: 500, headers: { 'Content-Type': 'application/json' } })
      : orig(i, x);
  });
  await rerun();
  {
    const s = read();
    const norm = z => z.replace(/[\d,.\s]+/g, ' ').trim();
    const same = norm(s.t) === norm(emptyText);
    out.error = { ok: ERR.test(s.t) && !same, saysError: ERR.test(s.t), indistinguishableFromEmpty: same,
                  offersRetry: /retry|try again|reload/i.test(s.t) };
  }

  // EDGE — the real payload rewritten to its boundaries, then re-measured narrow
  const mutate = (mapper) => set(async (i, x) => {
    let u = typeof i === 'string' ? i : (i && i.url) || '';
    { const b = blockWrite(i, x, wrote); if (b) return b; }
    // KEYSET PAGINATION DEFEATS A NAIVE RE-RUN. public-feed.html's loadInitial() keeps its cursor in
    // module scope and queries .lt('created_at', cursor); calling it a second time therefore asks for
    // the page AFTER the last one and comes back with zero rows, so the mutated payload never reached
    // the screen and the boundary states passed on an empty render. The cursor is unreachable from
    // here, but the REQUEST is not: drop the cursor filter and the re-run asks for page one again.
    // Confirmed on public-feed — 0 rows and no marker before, 15 cards and the marker after.
    if (REST.test(u) && /created_at=(lt|gt)\./.test(u)) {
      u = u.replace(/[?&]created_at=(lt|gt)\.[^&]*/g, m => (m[0] === '?' ? '?' : ''));
      i = (typeof i === 'string') ? u : new Request(u, i);
    }
    const r = await orig(i, x);
    if (!REST.test(u)) return r;
    let b; try { b = await r.clone().json(); } catch (e) { return r; }
    if (Array.isArray(b) && b.length) b.slice(0, 3).forEach(mapper);
    return new Response(JSON.stringify(b), { status: 200, headers: { 'Content-Type': 'application/json' } });
  });
  // `content` and `body` carry the visible text on the feed surfaces the way `title` does on the
  // listing surfaces — public-feed.html renders escHtml(p.content), so a mutation that rewrote only
  // name/title/label left the longest string on the page untouched and the boundary untested.
  mutate(row => {
    for (const k of Object.keys(row)) {
      if (/name|title|label|scope|desc|content|body|message/i.test(k) && typeof row[k] === 'string') row[k] = LONG;
      if (/price|amount|budget|rate|fee|cost/i.test(k) && typeof row[k] === 'number') row[k] = 0;
    }
  });
  await rerun();
  {
    const s = read();
    const landed = /Southern Tagalog/.test(s.t);
    // A STATE THAT NEVER REACHED THE SCREEN IS NOT A STATE THAT PASSED. The header above already
    // named this tell — longNameRendered=false means no re-fetch, so the page was compared against
    // itself — but the verdict never used it, and `ok` was computed from overflow alone. A page
    // whose loader this module cannot re-run therefore reported a clean pass for a boundary it had
    // never rendered. That is the same shape as the structural-probe-answering-a-behavioural-oracle
    // defect the whole bank was rebuilt around, so it is reported as INCONCLUSIVE rather than as
    // either a pass or a failure: the walk must find the loader, not bank the silence.
    out.edge = { ok: landed && s.doc <= 0 && s.over === 0, inconclusive: !landed,
                 docOverflow: s.doc, unclipped: s.over, longNameRendered: landed, atWidth: s.innerWidth };
  }

  // SCRIPT_NAME — a real Philippine script, not lorem
  mutate(row => { for (const k of Object.keys(row)) {
    if (/name|title|label|content|body|message/i.test(k) && typeof row[k] === 'string') row[k] = BAYBAYIN; } });
  await rerun();
  {
    const s = read();
    const rendered = /[ᜀ-ᜟ]/.test(s.t);
    out.script_name = { ok: rendered && s.doc <= 0, inconclusive: !rendered,
                        baybayinRendered: rendered, docOverflow: s.doc };
  }

  // DEGRADED — the network drops out from under the page
  set(async () => { throw new TypeError('Failed to fetch'); });
  window.dispatchEvent(new Event('offline'));
  await new Promise(r => setTimeout(r, 1500));
  out.degraded = {
    ok: [...document.body.querySelectorAll('div')].some(el =>
      /you are offline|no connection|reconnect/i.test(el.innerText || '') &&
      getComputedStyle(el).display !== 'none' && (el.offsetParent || el.getClientRects().length)),
  };

  window.fetch = orig;
  window.dispatchEvent(new Event('online'));
  out._writesBlocked = wrote;
  out._allOk = Object.keys(out).filter(k => !k.startsWith('_') && out[k] && out[k].ok !== null)
    .every(k => out[k].ok === true);
  return out;
}

// ── F1 · AZ-failure-injection ────────────────────────────────────────────────────────────────
// Each layer fails in turn and the layer ABOVE must degrade honestly. Every induction here serves a
// REAL response (a 500 with a body, a 401, a null field) rather than rejecting the promise: a
// rejected fetch leaves a stuck skeleton and proves a different thing entirely.
//
// Mutating verbs are never forwarded, for the same reason as everywhere else in this file.
export async function failures(opts) {
  const settle = (opts && opts.settle) || 1800;
  const orig = window.__lsrFetch || window.fetch;
  window.__lsrFetch = orig;
  const out = {};
  const m = () => document.querySelector('main') || document.body;
  const txt = () => (m().innerText || '').replace(/\s+/g, ' ');
  const MUT = /^(POST|PATCH|PUT|DELETE)$/i;
  const guard = (i, x) => MUT.test((x && x.method) || (i && i.method) || 'GET');
  const SAYS_FAIL = /couldn['’]?t|could not|failed|unavailable|error|problem|went wrong|expired|timed out|timeout/i;
  const OFFERS_BACK = /retry|try again|reload|refresh|sign in again/i;

  const baseline = txt();

  const serve = (status, body) => { window.fetch = async (i, x) => {
    const u = typeof i === 'string' ? i : (i && i.url) || '';
    { const b = blockWrite(i, x); if (b) return b; }
    if (!REST.test(u)) return orig(i, x);
    return new Response(typeof body === 'string' ? body : JSON.stringify(body),
                        { status, headers: { 'Content-Type': 'application/json' } });
  }; };

  // 401 — an expired session must SAY the session expired and that nothing was sent. Never a bare
  // "try again" (which invites a retry that cannot work) and never a sign-in instruction to someone
  // who IS signed in.
  serve(401, { code: '42501', message: 'JWT expired' });
  await rerun(1200);
  {
    const t = txt();
    out.fail_401 = {
      saysExpiredOrFailed: SAYS_FAIL.test(t),
      namesSession: /session|sign ?in|log ?in|expired/i.test(t),
      saysNothingSent: /nothing was sent|not sent|no changes were saved|nothing was saved/i.test(t),
      bareRetryOnly: OFFERS_BACK.test(t) && !/session|expired/i.test(t),
      ok: SAYS_FAIL.test(t) && /session|expired/i.test(t),
    };
  }

  // TIMEOUT — a hung dependency must END in a stated timeout, not an indefinite skeleton. Served as
  // a slow-but-real response so the page's own timeout path is what decides.
  window.fetch = async (i, x) => {
    const u = typeof i === 'string' ? i : (i && i.url) || '';
    { const b = blockWrite(i, x); if (b) return b; }
    if (!REST.test(u)) return orig(i, x);
    await new Promise(r => setTimeout(r, 9000));
    return new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } });
  };
  rerun(0);                                    // deliberately NOT awaited - we sample mid-hang
  await new Promise(r => setTimeout(r, 4000));
  {
    const t = txt();
    // `[class*="skeleton"]` misses this platform's own wh-cardskel; match the STEM (see states()).
    const skel = m().querySelectorAll('[class*="skel"],.shimmer,[aria-busy="true"]').length;
    out.fail_timeout = {
      statesTimeout: /timed out|timeout|taking longer|slow/i.test(t),
      stuckSkeleton: skel > 0 && !/timed out|timeout|taking longer/i.test(t),
      saysSomething: SAYS_FAIL.test(t),
      ok: /timed out|timeout|taking longer|slow/i.test(t) || SAYS_FAIL.test(t),
    };
  }
  await new Promise(r => setTimeout(r, 6000));  // let the hang drain before the next induction

  // PARTIAL — half the reads succeed. What loaded must be KEPT and what failed must be NAMED; a
  // silent blank beside good data is the failure this catches.
  let n = 0;
  window.fetch = async (i, x) => {
    const u = typeof i === 'string' ? i : (i && i.url) || '';
    { const b = blockWrite(i, x); if (b) return b; }
    if (!REST.test(u)) return orig(i, x);
    n++;
    if (n % 2 === 0) return new Response(JSON.stringify({ code: '500', message: 'induced partial failure' }),
                                         { status: 500, headers: { 'Content-Type': 'application/json' } });
    return orig(i, x);
  };
  await rerun(1600);
  {
    const t = txt();
    out.fail_partial = {
      keptSomething: t.length > baseline.length * 0.3,
      namesTheFailure: SAYS_FAIL.test(t),
      ok: t.length > baseline.length * 0.3 && SAYS_FAIL.test(t),
      len: t.length, baselineLen: baseline.length,
    };
  }

  // NULL FIELD — a valid row with a NULL in it must render a STATED GAP, never 0, never "undefined",
  // never a fabricated value. This is the class that printed a filed PHP300 top-up as PHP0.00.
  window.fetch = async (i, x) => {
    const u = typeof i === 'string' ? i : (i && i.url) || '';
    { const b = blockWrite(i, x); if (b) return b; }
    if (!REST.test(u)) return orig(i, x);
    const r = await orig(i, x);
    let b; try { b = await r.clone().json(); } catch (e) { return r; }
    if (Array.isArray(b)) b.forEach(row => {
      for (const k of Object.keys(row || {})) {
        if (/amount|price|rate|total|count|rating|balance|fee/i.test(k)) row[k] = null;
      }
    });
    return new Response(JSON.stringify(b), { status: 200, headers: { 'Content-Type': 'application/json' } });
  };
  await rerun(1600);
  {
    const t = txt();
    out.fail_null_field = {
      fabricatedZero: /₱0\.00|₱0\b/.test(t),
      leakedUndefined: /\bundefined\b|\bNaN\b|\bnull\b/i.test(t),
      showsGap: /[\u2014\u2013-]|not set|no data|unknown|not recorded/.test(t),
      ok: !/₱0\.00/.test(t) && !/\bundefined\b|\bNaN\b/i.test(t),
    };
  }

  window.fetch = orig;
  await rerun(settle);
  return out;
}

// ── F3 · BH-ui-visual (the two the battery cannot do) ────────────────────────────────────────
// ufai_battery.js already runs axe-core WCAG 2.2 AA (contrast, names, target size) and the
// focus-visible tab-walk, across every enumerated state via sweepAll(). REUSE that; this adds only
// the two it does not measure:
//
//   APCA — axe grades WCAG 2.x contrast RATIO, which is a different model from APCA's perceptual
//   lightness contrast. They disagree often enough that this platform has already recorded a page
//   scoring WCAG 100% and APCA 25%. Passing one says nothing about the other.
//
//   REDUCED MOTION — the battery reports "OS-off" because the browser is not emulating
//   prefers-reduced-motion, so it cannot observe the honoured state. Whether the page HONOURS it is
//   still answerable: does anything animate, and is there a rule that turns it off.
//
// Backgrounds are composited through ancestors. A tinted pill over a dark card over a gradient page
// is the exact shape that made naive checks read a transparent background as white and pass.
const APCA = {
  normBG: 0.56, normTXT: 0.57, revTXT: 0.62, revBG: 0.65,
  blkThrs: 0.022, blkClmp: 1.414, scale: 1.14, loOffset: 0.027, deltaYmin: 0.0005,
};

function _parseRGBA(s) {
  const m = String(s).match(/rgba?\(([^)]+)\)/);
  if (!m) return null;
  const p = m[1].split(',').map(x => parseFloat(x.trim()));
  return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
}

function _overlay(fg, bg) {            // source-over compositing
  const a = fg.a + bg.a * (1 - fg.a);
  if (a === 0) return { r: 0, g: 0, b: 0, a: 0 };
  return {
    r: (fg.r * fg.a + bg.r * bg.a * (1 - fg.a)) / a,
    g: (fg.g * fg.a + bg.g * bg.a * (1 - fg.a)) / a,
    b: (fg.b * fg.a + bg.b * bg.a * (1 - fg.a)) / a,
    a,
  };
}

// A GRADIENT IS A BACKGROUND. Reading backgroundColor alone reports rgba(0,0,0,0) for anything
// painted by background-image, so the walk fell through to the page canvas and produced nonsense:
// the seller's Save button is dark navy on a BRIGHT ORANGE gradient -- high contrast -- and scored
// Lc 0, "invisible". 41 of 49 text nodes on that surface sit over a gradient, so almost every
// reading was wrong. Averaging the gradient's colour stops is an approximation, and it is enormously
// closer than pretending the element is transparent. A url() image cannot be averaged from CSS at
// all, so those are reported INCONCLUSIVE rather than scored.
function _gradientAvg(bgImage) {
  if (!bgImage || bgImage === 'none') return null;
  if (/url\(/i.test(bgImage)) return { unknown: true };
  const stops = bgImage.match(/rgba?\([^)]+\)/g);
  if (!stops || !stops.length) return null;
  const cs = stops.map(_parseRGBA).filter(Boolean);
  if (!cs.length) return null;
  const n = cs.length;
  return { r: cs.reduce((s, c) => s + c.r, 0) / n,
           g: cs.reduce((s, c) => s + c.g, 0) / n,
           b: cs.reduce((s, c) => s + c.b, 0) / n,
           a: cs.reduce((s, c) => s + c.a, 0) / n };
}

function _effectiveBg(el) {
  // walk up compositing each ancestor's background until opaque; the page canvas is the floor
  let acc = { r: 0, g: 0, b: 0, a: 0 };
  let inconclusive = false;
  for (let n = el; n && n !== document.documentElement.parentNode; n = n.parentElement) {
    const st = getComputedStyle(n);
    const g = _gradientAvg(st.backgroundImage);
    if (g && g.unknown) { inconclusive = true; break; }
    if (g) { acc = _overlay(acc, g); if (acc.a >= 0.999) break; }
    const c = _parseRGBA(st.backgroundColor);
    if (c && c.a > 0) { acc = _overlay(acc, c); if (acc.a >= 0.999) break; }
  }
  if (!inconclusive && acc.a < 0.999) {
    const bodySt = getComputedStyle(document.body);
    const bodyG = _gradientAvg(bodySt.backgroundImage);
    const body = (bodyG && !bodyG.unknown) ? bodyG
               : (_parseRGBA(bodySt.backgroundColor) || { r: 255, g: 255, b: 255, a: 1 });
    acc = _overlay(acc, { ...body, a: 1 });
  }
  acc.inconclusive = inconclusive;
  return acc;
}

function _Y(c) {
  const f = v => Math.pow(Math.max(0, Math.min(255, v)) / 255, 2.4);
  return 0.2126729 * f(c.r) + 0.7151522 * f(c.g) + 0.0721750 * f(c.b);
}

function _apcaLc(txt, bg) {
  let Yt = _Y(txt), Yb = _Y(bg);
  Yt = Yt > APCA.blkThrs ? Yt : Yt + Math.pow(APCA.blkThrs - Yt, APCA.blkClmp);
  Yb = Yb > APCA.blkThrs ? Yb : Yb + Math.pow(APCA.blkThrs - Yb, APCA.blkClmp);
  if (Math.abs(Yb - Yt) < APCA.deltaYmin) return 0;
  let S;
  if (Yb > Yt) {                                   // dark text on light
    S = (Math.pow(Yb, APCA.normBG) - Math.pow(Yt, APCA.normTXT)) * APCA.scale;
    return (S < APCA.loOffset ? 0 : S - APCA.loOffset) * 100;
  }
  S = (Math.pow(Yb, APCA.revBG) - Math.pow(Yt, APCA.revTXT)) * APCA.scale;   // light text on dark
  return (S > -APCA.loOffset ? 0 : S + APCA.loOffset) * 100;
}

export function visual() {
  const m = document.querySelector('main') || document.body;
  const vis = el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';
  const texts = [...m.querySelectorAll('*')].filter(el =>
    el.childElementCount === 0 && vis(el) && (el.textContent || '').trim().length > 1);

  const rows = texts.slice(0, 400).map(el => {
    const cs = getComputedStyle(el);
    const fg = _parseRGBA(cs.color) || { r: 0, g: 0, b: 0, a: 1 };
    const bg = _effectiveBg(el);
    const composited = fg.a < 1 ? _overlay(fg, bg) : fg;   // translucent TEXT composites too
    const px = parseFloat(cs.fontSize) || 16;
    const w = parseInt(cs.fontWeight, 10) || 400;
    const Lc = Math.abs(_apcaLc(composited, bg));
    // APCA FLOORS, from the published table (substrate: apca-perceptual-contrast-wcag3-successor).
    // The previous line was `(px >= 24 || (px >= 18.66 && w >= 700)) ? 45 : (px < 14 ? 75 : 60)`,
    // which INVERTED the spec: it handed the STRICTEST floor (Lc 75) to the SMALLEST text, when the
    // table assigns Lc 75 to body columns of 18px AND LARGER. Small UI labels were being graded
    // against a body-copy standard they are not, and cannot be, held to.
    // The real table:
    //   Lc 90  preferred for fluent body text   (>= 14px / 400)
    //   Lc 75  minimum for columns of body text (>= 18px / 400)
    //   Lc 60  content text, not body/column    (>= 24px / 400, or >= 16px / 700)
    //   Lc 45  larger, heavier text             (>= 36px / 400, or >= 24px / 700)
    //   Lc 30  ABSOLUTE MINIMUM for any text not listed above  <- where a 10-13px chip label lands
    //   Lc 15  point of invisibility
    // Read in descending size order so the most permissive qualifying tier wins, and the Lc 30 tier
    // still has teeth: it catches text heading for invisibility, which is what it is for.
    const floor =
        (px >= 36 || (px >= 24 && w >= 700)) ? 45 :
        (px >= 24 || (px >= 16 && w >= 700)) ? 60 :
        (px >= 18)                           ? 75 :
        (px >= 14)                           ? 60 :   // 14-17px body-ish: the 60 tier is the honest fit
                                               30;    // incidental/small UI text
    return { txt: (el.textContent || '').trim().slice(0, 32), px: Math.round(px), w,
             Lc: Math.round(Lc * 10) / 10, floor,
             ok: bg.inconclusive ? null : Lc >= floor,
             inconclusive: !!bg.inconclusive,
             fg: cs.color, bg: 'rgb(' + [bg.r, bg.g, bg.b].map(Math.round).join(',') + ')' };
  });
  const fails = rows.filter(r => r.ok === false).sort((a, b) => a.Lc - b.Lc);
  const unknown = rows.filter(r => r.inconclusive);

  // REDUCED MOTION: does anything actually animate, and is the opt-out expressed?
  const animated = [...document.querySelectorAll('*')].filter(el => {
    const cs = getComputedStyle(el);
    return vis(el) && ((cs.animationName && cs.animationName !== 'none') ||
                       (cs.transitionDuration && parseFloat(cs.transitionDuration) > 0));
  });
  let declaresGuard = false;
  for (const sheet of document.styleSheets) {
    let rules; try { rules = sheet.cssRules; } catch (e) { continue; }  // empty-catch-allow: cross-origin sheet
    for (const r of rules || []) {
      if (r.media && /prefers-reduced-motion/.test(r.conditionText || r.media.mediaText || '')) { declaresGuard = true; break; }
    }
    if (declaresGuard) break;
  }
  return {
    apca: {
      measured: rows.length,
      failing: fails.length,
      inconclusive: unknown.length,
      ok: unknown.length ? null : fails.length === 0,
      worst: fails.slice(0, 10),
      unmeasurable: unknown.slice(0, 4).map(u => u.txt),
    },
    reduced_motion: {
      animatedElements: animated.length,
      declaresGuard,
      ok: animated.length === 0 ? null : declaresGuard,
      note: animated.length === 0 ? 'nothing animates on this surface - nothing to honour'
                                  : (declaresGuard ? null : 'elements animate and no @media (prefers-reduced-motion) rule exists'),
      matchesNow: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    },
  };
}

// ── F3 · BG-ui-state ─────────────────────────────────────────────────────────────────────────
// The six states per COMPONENT, not per page. Four of them cannot be seen on a settled page at all
// -- loading, skeleton and busy only exist while something is in flight, and a disabled control only
// proves itself when you try to use it -- so they are INDUCED here rather than looked for.
//
// The disabled check is deliberately NOT a forced click. Playwright's force:true dispatches the event
// past the very guard under test, which is how a disabled control once "passed" a probe it does not
// actually survive. A real click on a real disabled button is a no-op, and that is the assertion.
export async function states(opts) {
  const wait = (opts && opts.settle) || 1500;
  const orig = window.__lsrFetch || window.fetch;
  window.__lsrFetch = orig;
  const out = {};
  const m = () => document.querySelector('main') || document.body;
  const vis = el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';

  // POPULATED — every field it promises, and none of the four strings that mean a bug reached the eye
  {
    const t = (m().innerText || '');
    const junk = t.match(/\bundefined\b|\bNaN\b|\[object Object\]/g) || [];
    out.component_populated = { ok: junk.length === 0 && t.length > 120, junk, len: t.length };
  }

  // LOADING + SKELETON — hold every read open, then look at what the page shows while it waits. The
  // response is DELAYED, not failed: a rejected promise leaves a stuck skeleton and proves something
  // else entirely (the same rule the failure states inherit).
  let heightsBefore = null;
  {
    // A BOUNDED DELAY, NOT AN OPEN HOLD. The first version parked every REST response in a promise
    // that only resolved after the sample -- and then awaited the page's loaders, which await those
    // same responses. That deadlocks: the release code sits after the await that can never finish,
    // and the probe hung for half an hour before the harness killed it. A delay gives the same
    // in-flight window to look at and always drains itself. The loaders are also fired WITHOUT being
    // awaited here, for the same reason: this state is about what the page shows WHILE it waits.
    const HOLD = 1100;
    let held = 0;
    window.fetch = (i, x) => {
      const u = typeof i === 'string' ? i : (i && i.url) || '';
      const method = ((x && x.method) || (i && i.method) || 'GET');
      // A mutating verb is answered, never forwarded - decided by blockWrite across the WHOLE
      // Supabase surface (rpc and edge functions included), before any read logic runs.
      if (blockWrite(i, x)) {
        return new Promise(res => setTimeout(() => res(_stub()), HOLD));
      }
      if (!REST.test(u)) return orig(i, x);
      held++;
      return new Promise(res => setTimeout(() => res(orig(i, x)), HOLD));
    };
    document.dispatchEvent(new Event('DOMContentLoaded'));
    for (const k of LOADERS) {
      // deliberately NOT awaited: we sample mid-flight, and a throw must not stop the others
      if (typeof window[k] === 'function') { try { window[k](); } catch (e) { /* empty-catch-allow: see above */ } }
    }
    // NO LOADER ON WINDOW MEANS NOTHING WAS EVER IN FLIGHT, AND A LOADING STATE MEASURED WITH
    // NOTHING LOADING IS VACUOUS. marketplace.html keeps every loader closure-scoped inside its
    // IIFE, so this loop ran zero of them and the probe scored "no skeleton on this surface" about
    // a page that renders nine — the same defect the AZ null-field walk hit twice. Drive the page's
    // OWN route back to the network instead: a section tab, a filter chip, a category button.
    if (!held) {
      const reQuery = [...m().querySelectorAll(
        '[role="tab"]:not([aria-selected="true"]),.section-tab:not(.active),.cat-chip,.filter-chip,[data-section]')]
        .filter(el => vis(el) && !/^https?:/.test(el.getAttribute('href') || ''))[0];
      if (reQuery) reQuery.click();
    }
    await new Promise(r => setTimeout(r, Math.floor(HOLD / 2)));   // sample INSIDE the flight
    const s = m();
    // MATCH THE STEM, NOT THE WORD. This asked for `[class*="skeleton"]` while every skeleton on the
    // platform is named wh-cardskel / wh-skel-*, so it reported "no skeleton component on this
    // surface" about pages that render nine of them — and then recorded that as a not-applicable,
    // which is the quietest way an instrument can be wrong: it looks like an honest abstention.
    const skel = [...s.querySelectorAll('[class*="skel"],[id*="skel"],.shimmer,[aria-busy="true"]')].filter(vis);
    const txt = (s.innerText || '');
    heightsBefore = skel.map(e => Math.round(e.getBoundingClientRect().height));
    // "loading" must be distinguishable from "empty": an invite to act is what an EMPTY surface says,
    // and a surface that is merely waiting must not say it
    out.component_loading = {
      // A state that never reached the screen is not a state that failed, either. Report the
      // vacuum rather than a verdict when nothing was in flight to look at.
      ok: held === 0 ? null
        : (skel.length > 0 || /loading|loadingâ€¦|…/i.test(txt) || /\bloading\b/i.test(txt)),
      inconclusive: held === 0,
      requestsInFlight: held,
      skeletonNodes: skel.length,
      saysLoading: /\bloading\b/i.test(txt),
      looksEmptyInstead: INVITE.test(txt),
      distinguishableFromEmpty: !(INVITE.test(txt) && skel.length === 0),
    };
    out.component_skeleton = {
      ok: skel.length === 0 ? null : heightsBefore.every(h => h > 0),
      reservedHeights: heightsBefore,
      note: skel.length > 0 ? null
        : held === 0
          ? 'INCONCLUSIVE: nothing was in flight (no loader on window and no re-query affordance found), so the absence of a skeleton says nothing about this surface'
          : 'no skeleton component on this surface - nothing to reserve space, recorded rather than passed',
    };
    await new Promise(r => setTimeout(r, HOLD + wait));   // let the delayed reads land and settle
  }

  // DISABLED — looks disabled AND refuses activation. Both, not either.
  {
    const dis = [...document.querySelectorAll('button[disabled],[aria-disabled="true"],input[disabled],select[disabled]')].filter(vis);
    const checked = dis.slice(0, 6).map(el => {
      const cs = getComputedStyle(el);
      const looks = Number(cs.opacity) < 0.9 || /not-allowed/.test(cs.cursor) || cs.pointerEvents === 'none';
      let fired = false;
      const mark = () => { fired = true; };
      el.addEventListener('click', mark, { once: true });
      el.click();                       // a REAL click, never force:true
      el.removeEventListener('click', mark);
      return { el: (el.tagName + (el.id ? '#' + el.id : '')).slice(0, 36),
               looksDisabled: looks, refusedActivation: !fired, opacity: cs.opacity, cursor: cs.cursor };
    });
    out.component_disabled = {
      ok: checked.length === 0 ? null : checked.every(c => c.looksDisabled && c.refusedActivation),
      found: dis.length, checked,
      note: dis.length === 0 ? 'no disabled control in this state - recorded rather than passed' : null,
    };
  }

  // BUSY — an in-flight control must be busy and must not re-fire. Held open so the flight is real.
  {
    // A SUBMIT, not anything whose label happens to contain a verb. The first version matched
    // /search/i and picked the "Searches" TAB -- a nav control that fires no write, cannot go busy,
    // and therefore failed the check by construction. Require a real submit or a form-owned button,
    // and exclude the tab/nav families explicitly.
    const btn = [...document.querySelectorAll('button')].filter(vis).find(b =>
      !b.disabled &&
      !b.closest('[role="tablist"], nav, .section-tabs, .wh-hub-panel') &&
      !/tab-btn|wh-hub|section-tab/.test(b.className || '') &&
      // `button.type` reflects "submit" by DEFAULT on almost every button, form or not, so testing
      // it alone matched everything and picked whichever button happened to come first (the
      // Watchlist trust-bar control). The button has to actually belong to a form, or say plainly
      // that it commits something.
      ((b.type === 'submit' && b.closest('form')) ||
       // decision controls count too: the admin queues commit money with "Verify: mint credits" /
       // "Approve" / "Reject", which no submit-shaped test would ever find. Safe to press only
       // because the mutating verbs above are answered and never forwarded -- this list must not
       // grow beyond what that guard covers.
       /^(save|file|submit|post|send|hail|confirm|top.?up|verify|approve|reject|decide)\b/i
         .test((b.textContent || '').trim())));
    if (!btn) {
      out.component_busy = { ok: null, note: 'no in-flight-capable control on this surface' };
    } else {
      // THE WRITE MUST NEVER LAND. This check CLICKS a real commit control, and the first version
      // only DELAYED the request before forwarding it -- so on marketplace-seller.html it pressed
      // Save and the profile row's updated_at actually moved. A probe that mutates the shared
      // database is the one thing this bank is not allowed to do, and "it was only a timestamp" is
      // not the standard. Mutating verbs are now answered synthetically and NEVER forwarded; reads
      // are merely delayed, which is all the in-flight window needs.
      const HOLD = 1100;
      const MUTATING = /^(POST|PATCH|PUT|DELETE)$/i;
      const blocked = [];
      window.fetch = (i, x) => {
        const u = typeof i === 'string' ? i : (i && i.url) || '';
        const method = ((x && x.method) || (i && i.method) || 'GET');
        if (blockWrite(i, x, blocked)) {
          return new Promise(res => setTimeout(() => res(_stub()), HOLD));
        }
        if (!REST.test(u)) return orig(i, x);
        return new Promise(res => setTimeout(() => res(orig(i, x)), HOLD));
      };
      out._writesBlocked = blocked;
      btn.click();
      await new Promise(r => setTimeout(r, 450));          // sample INSIDE the flight
      const cs = getComputedStyle(btn);
      // THE VERDICT MUST DEPEND ON A FLIGHT ACTUALLY HAPPENING. Text-matching picked "Post a Parts
      // Listing", which OPENS the post sheet and commits nothing — so it can never go busy and
      // failed by construction, the third time this selector has flunked a control that was never
      // in flight (after the "Searches" tab and the default-submit match). No request fired means
      // the control was not in-flight-capable: say so instead of scoring it.
      // ...and TELEMETRY IS NOT A FLIGHT. Every page POSTs client_errors / analytics_events on its
      // own schedule, so counting any write at all let the page's own logging stand in for the
      // control's action — writeFired:true with "POST client_errors" as the only evidence.
      const TELEMETRY = /^(POST|PATCH|PUT|DELETE)\s+(client_errors|analytics_events|page_views|rpc\/log)/i;
      const realWrites = blocked.filter(b => !TELEMETRY.test(b));
      const fired = realWrites.length > 0;
      out.component_busy = {
        ok: fired ? (btn.disabled || btn.getAttribute('aria-busy') === 'true' || cs.pointerEvents === 'none') : null,
        inconclusive: !fired,
        writeFired: fired, writes: realWrites.slice(0, 3), allWritesBlocked: blocked.slice(0, 4),
        control: (btn.textContent || '').trim().slice(0, 28),
        disabledInFlight: btn.disabled,
        ariaBusy: btn.getAttribute('aria-busy'),
        pointerEvents: cs.pointerEvents,
        note: fired ? undefined : 'the control this lens could reach commits nothing (it opens a flow), so nothing was in flight to be busy about',
      };
      await new Promise(r => setTimeout(r, HOLD + wait));
    }
  }

  window.fetch = orig;
  return out;
}

// ── F4 · BI-ux-comprehension ─────────────────────────────────────────────────────────────────
// "Can a person say what this number means, what happens next, and what it costs?"
//
// This lens cannot be fully mechanised and is not pretended to be: the probe COLLECTS the evidence
// (every number with whatever text is within reach of it, the cost language before a commit, the
// refusal sentences) and a human judgement is made on what it returns. What the probe does decide
// is the one thing it can: whether a number has ANY explanation reachable at all. A number with no
// label, no heading, no aria-label and no title is unreadable by construction, and that is the
// class the vanished credits chip belonged to -- the value was right and the meaning was missing.
export function comprehension() {
  const m = document.querySelector('main') || document.body;
  const vis = el => (el.offsetParent || el.getClientRects().length);
  const NUM = /^[₱$]?\s*-?[\d,]+(\.\d+)?\s*(%|x|hrs?|days?|km)?$/i;

  // A number is EXPLAINED if something within reach names it: its own aria-label/title, a sibling
  // label, its container's label element, or a heading above it. "Within reach" is deliberately
  // generous -- the aim is to find numbers nothing explains, not to grade prose.
  const numbers = [...m.querySelectorAll('*')].filter(el =>
    el.childElementCount === 0 && vis(el) && NUM.test((el.textContent || '').trim()) &&
    (el.textContent || '').trim().length > 0
  ).slice(0, 40).map(el => {
    const own = (el.getAttribute('aria-label') || '') + ' ' + (el.getAttribute('title') || '');
    const par = el.parentElement;
    const near = par ? (par.innerText || '').replace(/\s+/g, ' ').trim() : '';
    const labelEl = par ? par.querySelector('.sc-label, .ac-label, label, .mod-sub, .sc-sub, dt') : null;
    const grandNear = par && par.parentElement ? (par.parentElement.innerText || '').replace(/\s+/g, ' ').trim() : '';
    const value = (el.textContent || '').trim();
    // the explanation is whatever text sits with it, minus the number itself
    const context = (own + ' ' + (labelEl ? labelEl.innerText : '') + ' ' +
                     near.replace(value, '') + ' ' + grandNear.replace(value, '')).replace(/\s+/g, ' ').trim();
    return { value, explainedBy: context.slice(0, 90), explained: context.length > 2 };
  });

  const body = (m.innerText || '').replace(/\s+/g, ' ');
  const commit = [...m.querySelectorAll('button, [type=submit]')].filter(vis)
    .map(b => (b.textContent || '').trim())
    .filter(t => /buy|book|hire|hail|post|file|submit|confirm|pay|send|save|top.?up/i.test(t));

  return {
    numbersFound: numbers.length,
    unexplained: numbers.filter(n => !n.explained),
    unexplainedCount: numbers.filter(n => !n.explained).length,
    // what does it cost -- stated BEFORE the commitment, not after
    cost: {
      commitControls: commit.slice(0, 8),
      statesFee:    /\b(fee|commission|charge|cost)\b/i.test(body),
      statesFree:   /\bno fees?\b|\bfree\b/i.test(body),
      statesReward: /credits back|credits? when|reward/i.test(body),
      statesHold:   /\bhold\b|\breserved?\b|\bescrow\b/i.test(body),
    },
    // what happens next -- after an action, the surface says what and when
    next: {
      // A CONSEQUENCE STATED PLAINLY IS STILL A CONSEQUENCE. This pattern only recognised a few
      // phrasings ("what to do next", "we'll", "within N"), so a surface that says in plain words
      // "Approve publishes the listing to every buyer immediately, and it can still be removed later"
      // scored as saying nothing. The oracle is whether a person is told what FOLLOWS an action, not
      // whether the copy uses a house phrase -- and an element-shaped test (does an .action-card
      // exist) is even further from it. Match the SHAPE of a consequence: a present-tense verb about
      // what the action does, a visibility change, a reversibility statement, or a timing promise.
      saysWhatNext: /(what to do next|next step|we.ll|you.ll (get|receive|hear)|within \d|once (you|the)|after you|goes live|publishes|will be (sent|shown|live|notified)|can still be (removed|undone|changed)|cannot be undone|sees (that|your)|changes what|appears on|notifie[sd]|takes effect)/i.test(body),
      hasActionCard: !!m.querySelector('.action-card, #mk-action-text, .ac-text'),
      actionText: (m.querySelector('#mk-action-text, .ac-text') || {}).innerText || null,
    },
    // why refused -- a refusal must name the rule AND a way out that can actually work
    refusals: [...m.querySelectorAll('[role=alert], .error, .refusal, .wh-error, .form-error')]
      .filter(vis).map(e => (e.innerText || '').replace(/\s+/g, ' ').trim()).filter(Boolean).slice(0, 6),
  };
}

// ── F3 · BF-ui-layout ────────────────────────────────────────────────────────────────────────
// The width is set by the MCP (JS cannot resize the window) and then DISBELIEVED: browser_resize
// reports the width it was asked for, and a request for 390 has landed as 585 here before now
// (device pixel ratio). So every verdict carries the width it was actually measured at, and a walk
// whose `verifiedWidth` is not within tolerance of the target is not evidence for that target.
//
// Three offender lists rather than three counts. A count says a page is wrong; a list says which
// element, which is the difference between a banked row and a fix.
export function layout(target) {
  const m = document.querySelector('main') || document.body;
  const vis = el => (el.offsetParent || el.getClientRects().length) &&
                    getComputedStyle(el).visibility !== 'hidden';
  const name = el => (el.tagName.toLowerCase() +
    (el.id ? '#' + el.id : '') +
    (el.className && typeof el.className === 'string'
      ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : '')).slice(0, 60);

  // OVERFLOW. An element that scrolls ON PURPOSE (overflow-x auto/scroll) is not an offender — the
  // marketplace tab strip is deliberately swipeable. A collapsed <details> reports its expanded
  // scrollWidth and is excluded for the same reason it was excluded upstream: it is not on screen.
  const offenders = [...m.querySelectorAll('*')].filter(el =>
    el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0 &&
    getComputedStyle(el).overflowX === 'visible' &&
    !el.closest('details:not([open])') && vis(el)
  ).map(el => ({ el: name(el), content: el.scrollWidth, box: el.clientWidth,
                 by: el.scrollWidth - el.clientWidth }))
   .sort((a, b) => b.by - a.by).slice(0, 8);

  // SIDEWAYS SCROLL. documentElement.clientWidth already excludes the vertical scrollbar gutter, so
  // this difference is real horizontal overflow — but a fractional device pixel ratio rounds, and a
  // 1px reading is that rounding rather than a defect. Tolerate 1, report the number either way.
  const docBy = document.documentElement.scrollWidth - document.documentElement.clientWidth;

  // TAP TARGETS, measured by RECT and not by stylesheet intent: a 44px min-height loses to a flex
  // parent that squeezes it. Links sitting inside a sentence are excluded — an inline citation is
  // not a thumb target, and counting it buries the controls that are.
  const inProse = el => !!el.closest('p, li, .wh-prose, .prose') &&
                        getComputedStyle(el).display.includes('inline');
  const small = [...m.querySelectorAll('button, a[href], input:not([type=hidden]), select, textarea, [role="button"], [onclick]')]
    .filter(el => vis(el) && !inProse(el))
    .map(el => { const r = el.getBoundingClientRect();
                 return { el: name(el), w: Math.round(r.width), h: Math.round(r.height),
                          txt: (el.textContent || '').trim().slice(0, 24) }; })
    .filter(r => (r.w > 0 && r.h > 0) && (r.w < 44 || r.h < 44))
    .sort((a, b) => (a.w * a.h) - (b.w * b.h)).slice(0, 12);

  // SAFE AREA. Fixed bottom chrome on a notched phone must clear the home indicator. The honest
  // check is whether the rule is EXPRESSED — env(safe-area-inset-bottom) resolves to 0 on this
  // desktop browser, so a measured gap of 0 here proves nothing either way.
  // INSTRUMENT FIX 2026-08-04: this filter demanded `r.bottom >= innerHeight - 4`, i.e. chrome FLUSH
  // against the viewport edge. That silently excluded the single most common piece of mobile bottom
  // chrome — an inset floating action button. community.html's #fab-post sits at
  // `bottom: calc(24px + env(safe-area-inset-bottom))`, so its rect bottom was 24px short of the edge
  // and the lens collected NOTHING, returning bottomFixed: [] and passing safe_area vacuously. The
  // page happened to be correct; an identical FAB with a bare `bottom: 24px` would have read exactly
  // the same green. A lens that cannot see the element it is judging is not measuring the page.
  // The band is now the plausible home-indicator zone: anything fixed and ending within 80px of the
  // bottom is bottom chrome and owes an env() declaration. insetFromBottom is reported so a reader
  // can see WHY each element qualified rather than trusting the band.
  const bottomFixed = [...document.querySelectorAll('*')].filter(el => {
    const cs = getComputedStyle(el);
    if (cs.position !== 'fixed' || !vis(el)) return false;
    const r = el.getBoundingClientRect();
    const inset = window.innerHeight - r.bottom;
    return inset >= -4 && inset <= 80 && r.height > 0 && r.height < window.innerHeight / 2;
  }).map(el => {
    const cs = getComputedStyle(el);
    // getComputedStyle RESOLVES env(), and on a desktop browser it resolves to 0 — so a sheet that
    // clears the home indicator and one that does not both compute to the same 32px. The only place
    // the difference survives is the UNRESOLVED declaration, so read the stylesheet rules that match
    // this element. Checking inline style alone reported marketplace.html's .sheet and its seller
    // twin as identical when one had env() and the other did not; the buyer's sheet was in fact
    // putting "Save Search" under the indicator. Ask the CSSOM, not the computed value.
    let declaresSafeArea = /safe-area-inset-bottom/.test(el.style.cssText || '');
    if (!declaresSafeArea) {
      for (const sheet of document.styleSheets) {
        let rules;
        // empty-catch-allow: a cross-origin stylesheet throws on .cssRules. Skipping it is correct —
        // the platform's own rules are same-origin, and a font CDN has no bottom chrome.
        try { rules = sheet.cssRules; } catch (e) { continue; }
        for (const r of rules || []) {
          if (!r.selectorText || !r.cssText.includes('safe-area-inset-bottom')) continue;
          // empty-catch-allow: an exotic selector can throw in matches(); it is not our rule.
          try { if (el.matches(r.selectorText)) { declaresSafeArea = true; } } catch (e) { continue; }
          if (declaresSafeArea) break;
        }
        if (declaresSafeArea) break;
      }
    }
    const r = el.getBoundingClientRect();
    return { el: name(el), padBottom: cs.paddingBottom, declaresSafeArea,
             insetFromBottom: Math.round(window.innerHeight - r.bottom) };
  });

  const verifiedWidth = window.innerWidth;
  const onTarget = target == null ? true : Math.abs(verifiedWidth - target) <= 12;
  return {
    requested: target ?? null,
    verifiedWidth, dpr: window.devicePixelRatio, onTarget,
    docScrollsSideways: docBy > 1, docBy,
    overflowCount: offenders.length, offenders,
    tapTargetsUnder44: small.length, small,
    bottomFixed,
    ok: onTarget && docBy <= 1 && offenders.length === 0,
  };
}

// ── F2 · BD-ufai-A (available / adaptable) ───────────────────────────────────────────────────
// Five states the other lenses never touch, each aimed at a way a surface can be UNAVAILABLE while
// still looking fine:
//
//   retry_path       a failure that offers a retry which does not re-attempt is worse than one that
//                    offers nothing — it turns a dead end into a loop the person blames themselves
//                    for. So the affordance is CLICKED and the network is watched, not read off the
//                    screen. `run()` already reports offersRetry from the TEXT; that is the claim,
//                    this is the proof.
//   fallback_engaged the dangerous shape is not "no fallback" — it is a fallback that engages
//                    SILENTLY, so a cached price reads as today's price. With the primary down,
//                    either nothing survives (and the surface says the read failed) or something
//                    survives (and it must say where that came from).
//   rate_limit_legible  429 is the one error whose remedy is TIME. A bare "something went wrong"
//                    invites an immediate retry, which is the exact action that extends the limit.
//   slow_honest      an empty-state invitation rendered while the read is still in flight is a lie
//                    with a friendly face: "be the first to post" when the page does not yet know.
//                    Measured mid-hang, not after.
//   offline_refusal  a write fired into a dead network that says nothing leaves the person believing
//                    it landed. Either it is refused before firing, or it is queued and SAID to be.
//
// Mutating verbs are counted and answered, never forwarded — the same rule as everywhere else in
// this file, earned after a probe of mine moved marketplace_sellers.updated_at on the shared DB.
export async function availability(opts) {
  const o = opts || {};
  const orig = window.__lsrFetch || window.fetch;
  window.__lsrFetch = orig;
  const out = {};
  const m = () => document.querySelector('main') || document.body;
  const txt = () => (m().innerText || '').replace(/\s+/g, ' ');
  const MUT = /^(POST|PATCH|PUT|DELETE)$/i;
  const verb = (i, x) => ((x && x.method) || (i && i.method) || 'GET').toUpperCase();
  const SAYS_FAIL = /couldn['’]?t|could not|failed|unavailable|error|problem|went wrong|expired|timed out|timeout|offline|no connection|not connected/i;
  const RETRY_TXT = /\b(retry|try again|reload|refresh)\b/i;
  const NAVIGATES = /location\s*\.\s*(reload|href|assign|replace)|window\s*\.\s*location/i;
  const STALE_TXT = /cached|from this device|from your device|saved copy|last (updated|synced)|may be out of date|out of date|stale|showing saved|offline copy|saved earlier/i;
  // `[class*="skeleton"]` does not match this platform's own skeletons, which are named wh-cardskel —
  // so the first run of this lens reported busySignals:0 on a page that was visibly full of them.
  // Match the stem, not the word.
  const BUSY_SEL = '[aria-busy="true"],[class*="skel"],[class*="shimmer"],[class*="spinner"],[class*="loading"]';
  const ACTION = /\b(buy|purchase|order|submit|save|send|post|confirm|reserve|hail|pay|publish|update|apply|accept|approve|top ?up|withdraw)\b/i;

  const vis = el => !!(el.offsetParent || el.getClientRects().length);
  const ctrls = () => [...m().querySelectorAll('button,[role="button"],a[href],input[type="submit"]')].filter(vis);
  const baselineText = txt();
  const baselineLen = baselineText.length;
  const baselineInvite = INVITE.test(baselineText);

  let reads = 0, writes = 0;
  const writeUrls = [];
  const noteWrite = (i, x, u) => {
    writes++;
    writeUrls.push(verb(i, x) + ' ' + u.replace(/^.*\/rest\/v1\//, '').slice(0, 48));
  };
  const install = h => { window.fetch = async (i, x) => {
    const u = typeof i === 'string' ? i : (i && i.url) || '';
    { const b = blockWrite(i, x, writeUrls); if (b) { writes++; return b; } }
    if (!REST.test(u)) return orig(i, x);
    reads++;
    return h(i, x);
  }; };
  const dead = status => async () => new Response(JSON.stringify({ code: String(status), message: 'induced' }),
    { status, headers: { 'Content-Type': 'application/json' } });

  /* AN INDUCTION THAT NEVER REACHED THE NETWORK PROVES NOTHING, AND THIS LENS LEARNED IT THE SAME
     WAY THE OTHERS DID. rerun() calls window[loader](), but marketplace.html keeps every loader
     closure-scoped inside its IIFE, so zero of them run: the page stays exactly as it was, the
     failure copy never appears, and the probe then scores the UNCHANGED page. It read
     retry_path:false / fallback:silentlyStale on a surface that handles both correctly, and on an
     earlier pass it read them GREEN only because a previous induction had happened to leave the
     page in an error state — a false green and a false red from the same blind spot.
     So: fire the loaders, and if nothing hit the network, drive the page's OWN route back to it
     (a section tab, a filter chip). Return how many reads actually went out, and let each state
     report itself INCONCLUSIVE rather than pass or fail on a page that never moved. */
  const requery = async (ms) => {
    const before = reads;
    await rerun(ms);
    if (reads === before) {
      // ONE CANDIDATE IS NOT ENOUGH: the obvious affordance is often the tab this walk already
      // switched to, so clicking it re-queries nothing. Work down the list until reads actually move.
      const cands = [...m().querySelectorAll(
        '[role="tab"]:not([aria-selected="true"]),.section-tab:not(.active),.cat-chip,.filter-chip,[data-section]')]
        .filter(e => vis(e) && !/^https?:/.test(e.getAttribute('href') || ''));
      for (const el of cands.slice(0, 4)) {
        el.click();
        await new Promise(r => setTimeout(r, ms || 1500));
        if (reads > before) break;
      }
    }
    return reads - before;
  };

  // ── retry_path ──────────────────────────────────────────────────────────────────────────────
  install(dead(500));
  const landedRetry = await requery(1400);
  {
    const t = txt();
    const label = el => (el.innerText || el.value || el.getAttribute('aria-label') || '');
    const cand = ctrls().filter(el => RETRY_TXT.test(label(el)));
    // Prefer a control that stays on the page. A "Reload" wired to location.reload() would take the
    // document down and the induction with it, so its inline handler is READ rather than fired — the
    // measurement stays honest about which affordance it could actually prove.
    const inline = el => (el.getAttribute('onclick') || '') + (el.getAttribute('href') || '');
    const safe = cand.filter(el => !NAVIGATES.test(inline(el)) && !/^https?:|^\//.test(el.getAttribute('href') || ''));
    const target = safe[0] || null;
    const before = reads;
    let clicked = false, recoveredDetail = null;
    if (target) { target.click(); clicked = true; await new Promise(r => setTimeout(r, 1500)); }
    const reAttempted = reads > before;

    // the cause is gone: the same affordance must now SUCCEED, not stay stuck on the failure copy
    let recovered = null;
    if (clicked && reAttempted) {
      window.fetch = orig;
      target.click();
      await new Promise(r => setTimeout(r, 1800));
      const t2 = txt();
      recovered = !SAYS_FAIL.test(t2) && t2.length > baselineLen * 0.6;
      recoveredDetail = { len: t2.length, baselineLen,
                          stillSaysFail: (t2.match(SAYS_FAIL) || [])[0] || null,
                          ctx: (() => { const j = t2.search(SAYS_FAIL); return j < 0 ? null : t2.slice(Math.max(0, j - 50), j + 60); })() };
      install(dead(500));
    }
    out.retry_path = {
      saysFailure: SAYS_FAIL.test(t),
      recoveredDetail,
      affordances: cand.length,
      affordanceText: cand.slice(0, 3).map(el => label(el).trim().slice(0, 28)),
      navigationOnly: cand.length > 0 && safe.length === 0,
      clicked, reAttempted, recovered,
      inductionLanded: landedRetry,
      ok: landedRetry === 0 ? null
        : cand.length === 0 ? false
        : safe.length === 0 ? null
        : (reAttempted && recovered === true),
      inconclusive: landedRetry === 0 || (cand.length > 0 && safe.length === 0),
      note: landedRetry === 0
        ? 'INCONCLUSIVE: the failure never reached the screen (no loader on window, no re-query affordance), so no verdict is possible'
        : undefined,
    };
  }

  // ── fallback_engaged ────────────────────────────────────────────────────────────────────────
  {
    // "DID ANYTHING SURVIVE" MUST BE A CONTRAST, NOT A COUNT. My first version counted every element
    // whose class contained card/row/item and read 20 survivors with the primary down — on a page
    // that renders 9 listings and 83 pieces of chrome matching the same selector. It would have
    // reported silent staleness on a page that had none. So the chrome floor is MEASURED, by
    // rendering the surface with zero rows first; anything above that floor is data that outlived
    // the failed read.
    /* A SKELETON IS NOT A SURVIVOR. wh-cardskel-card matches [class*="card"], so eight loading
       placeholders counted as eight rows of data that outlived a failed read — the lens reported
       silentlyStale about a page that was still loading. Placeholders are excluded, and the verdict
       waits for the surface to actually give up (this grid takes ~16s to decide), because judging a
       mid-load page for "pretending nothing happened" measures the wrong moment. */
    const ROWS = '[class*="card"]:not([class*="skel"]),[class*="row"]:not([class*="skel"]),' +
                 '[class*="item"]:not([class*="skel"]),tbody tr,li[class]:not([class*="skel"])';
    const settleUntilFailureNamed = async (capMs) => {
      for (let n = 0; n < Math.ceil(capMs / 1500); n++) {
        if (SAYS_FAIL.test(txt())) return true;
        await new Promise(r => setTimeout(r, 1500));
      }
      return SAYS_FAIL.test(txt());
    };
    // Content-Range is what supabase-js reads a count from; without it an "empty" stub means
    // UNKNOWN, not zero. See the note on EMPTY_HEADERS in run().
    install(async () => new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json', 'Content-Range': '*/0' } }));
    const landedEmpty = await requery(1500);
    const chrome = m().querySelectorAll(ROWS).length;

    install(dead(503));
    const landedDown = await requery(1600);
    const gaveUp = await settleUntilFailureNamed(21000);
    const t = txt();
    const rows = m().querySelectorAll(ROWS).length;
    const survived = rows > chrome;
    out.fallback_engaged = {
      primaryDown: true, rowsWithPrimaryDown: rows, chromeFloorMeasuredEmpty: chrome,
      domainRowsSurviving: Math.max(0, rows - chrome),
      saysFailure: SAYS_FAIL.test(t),
      labelsProvenance: STALE_TXT.test(t),
      silentlyStale: survived && !STALE_TXT.test(t) && !SAYS_FAIL.test(t),
      inductionLanded: { emptyPass: landedEmpty, primaryDownPass: landedDown },
      surfaceGaveUpAndSaidSo: gaveUp,
      ok: (landedEmpty === 0 || landedDown === 0) ? null
        : survived ? (STALE_TXT.test(t) || SAYS_FAIL.test(t)) : SAYS_FAIL.test(t),
      inconclusive: landedEmpty === 0 || landedDown === 0,
      note: (landedEmpty === 0 || landedDown === 0)
        ? 'INCONCLUSIVE: the chrome floor and/or the primary-down render never re-queried, so the survivor count compares a page to itself'
        : undefined,
    };
  }

  // ── rate_limit_legible ──────────────────────────────────────────────────────────────────────
  {
    window.fetch = async (i, x) => {
      const u = typeof i === 'string' ? i : (i && i.url) || '';
      { const b = blockWrite(i, x, writeUrls); if (b) { writes++; return b; } }
      if (!REST.test(u)) return orig(i, x);
      reads++;   // requery() measures landing by this counter; a bespoke handler must keep it honest
      return new Response(JSON.stringify({ code: '429', message: 'rate limit exceeded', hint: 'retry after 60s' }),
        { status: 429, headers: { 'Content-Type': 'application/json', 'Retry-After': '60' } });
    };
    const landedRate = await requery(1500);
    const t = txt();
    const NAMES = /too many|rate ?limit|slow down|throttl/i;
    // "wait about 1 minute" is a perfectly good answer to "when does it clear" and the first version
    // of this pattern scored it as no answer, because it only accepted "in|after N units". Match the
    // DURATION wherever it sits, not one phrasing of it.
    const WHEN = /\b\d+\s*(seconds?|secs?|minutes?|mins?|hours?)\b|try again in|a moment|shortly/i;
    out.rate_limit_legible = {
      namesTheLimit: NAMES.test(t),
      namesWhenItClears: WHEN.test(t),
      bareErrorOnly: SAYS_FAIL.test(t) && !NAMES.test(t),
      inductionLanded: landedRate,
      ok: landedRate === 0 ? null : (NAMES.test(t) && WHEN.test(t)),
      inconclusive: landedRate === 0,
      note: landedRate === 0 ? 'INCONCLUSIVE: the 429 never reached the screen' : undefined,
    };
  }

  // ── slow_honest ─────────────────────────────────────────────────────────────────────────────
  {
    window.fetch = async (i, x) => {
      const u = typeof i === 'string' ? i : (i && i.url) || '';
      { const b = blockWrite(i, x, writeUrls); if (b) { writes++; return b; } }
      if (!REST.test(u)) return orig(i, x);
      reads++;
      await new Promise(r => setTimeout(r, 8000));
      return orig(i, x);
    };
    rerun(0);                                    // deliberately NOT awaited — sampled mid-flight
    await new Promise(r => setTimeout(r, 2600));
    const t = txt();
    const busy = m().querySelectorAll(BUSY_SEL).length;
    const invites = INVITE.test(t);
    const saysLoading = /loading|fetching|please wait|working/i.test(t);
    const liveActions = ctrls().filter(el => ACTION.test(el.innerText || el.value || '') && !el.disabled &&
                                             el.getAttribute('aria-disabled') !== 'true').length;
    // The empty-state claim is only PREMATURE if it was not already there — a section that is
    // legitimately empty says so at rest too, and counting that as a defect would be the same
    // instrument error as counting chrome as survivors above.
    const inviteEl = invites ? [...m().querySelectorAll('*')].filter(el =>
      vis(el) && el.children.length === 0 && INVITE.test(el.innerText || ''))[0] : null;
    out.slow_honest = {
      busySignals: busy,
      prematureEmptyState: invites && !baselineInvite,   // "be the first" while it does not yet know
      inviteAtRest: baselineInvite,
      inviteText: inviteEl ? (inviteEl.innerText || '').trim().slice(0, 70) : ((txt().match(INVITE) || [])[0] || null),
      saysLoading,
      enabledActionControls: liveActions,
      ok: (busy > 0 || saysLoading) && !(invites && !baselineInvite),
    };
    await new Promise(r => setTimeout(r, 6200));  // let the hang drain before the next induction
  }

  // ── offline_refusal ─────────────────────────────────────────────────────────────────────────
  {
    const onLineDesc = Object.getOwnPropertyDescriptor(Navigator.prototype, 'onLine');
    Object.defineProperty(navigator, 'onLine', { configurable: true, get: () => false });
    window.fetch = async (i, x) => {
      const u = typeof i === 'string' ? i : (i && i.url) || '';
      // OFFLINE MUST COUNT the write rather than answer it: the oracle is whether the page fired
      // into a dead network at all, so the attempt is recorded and then the network "fails".
      //
      // ...but a READ SENT AS POST IS STILL A READ. PostgREST posts every rpc, so counting by verb
      // alone charged the seller console with six writes it never made -- all of them
      // rpc/my_service_provider_ids, a STABLE function that cannot write -- and failed the row for
      // firing into the dark when it had only been reading. Same exemption blockWrite uses.
      const _rpcName = (u.match(/\/rest\/v1\/rpc\/([A-Za-z0-9_]+)/) || [])[1];
      if (SUPA.test(u) && MUTV.test(verb(i, x)) && !(_rpcName && RPC_READONLY.has(_rpcName))) noteWrite(i, x, u);
      if (!SUPA.test(u)) return orig(i, x);
      throw new TypeError('Failed to fetch');
    };
    window.dispatchEvent(new Event('offline'));
    await new Promise(r => setTimeout(r, 1200));

    const before = writes;
    // A LINK IS NOT A WRITE. The picker excluded inline location handlers but not plain anchors, so
    // on the seller console it clicked "List an item" -- an <a href> to the post flow -- and
    // navigated the page out from under the probe mid-run ("Execution context was destroyed").
    // Anything that leaves the surface is disqualified: the oracle is about a write being refused
    // before it fires, and a control that navigates never had a write to refuse.
    const act = ctrls().filter(el => ACTION.test(el.innerText || el.value || '') && !el.disabled &&
                                     el.tagName !== 'A' && !el.closest('a[href]') &&
                                     !el.getAttribute('href') &&
                                     !NAVIGATES.test(el.getAttribute('onclick') || ''));
    const clicked = act[0] || null;
    if (clicked) { clicked.click(); await new Promise(r => setTimeout(r, 1600)); }
    const t = txt();
    const firedIntoTheDark = writes > before;
    const QUEUED = /queued|saved to this device|will send when|pending write/i;
    out.offline_refusal = {
      offlineBannerShown: [...document.body.querySelectorAll('*')].some(el =>
        /you are offline|no connection|offline|reconnect/i.test((el.innerText || '').slice(0, 120)) &&
        vis(el) && el.children.length === 0),
      actionClicked: clicked ? (clicked.innerText || '').trim().slice(0, 34) : null,
      writesAttempted: writes - before, writeTargets: writeUrls.slice(-3),
      firedIntoTheDark,
      saysNothingSent: /nothing was sent|not sent|no changes were saved|nothing was saved/i.test(t) || QUEUED.test(t),
      ok: clicked ? ((!firedIntoTheDark || QUEUED.test(t)) && (SAYS_FAIL.test(t) || QUEUED.test(t))) : null,
      inconclusive: !clicked,
      note: clicked ? undefined : 'no write affordance reachable on this surface without opening a flow',
    };
    if (onLineDesc) Object.defineProperty(navigator, 'onLine', onLineDesc);
    else delete navigator.onLine;
  }

  window.fetch = orig;
  window.dispatchEvent(new Event('online'));
  await rerun(o.settle || 1800);
  out._writesBlocked = writes;
  out._writeTargets = writeUrls;
  return out;
}
