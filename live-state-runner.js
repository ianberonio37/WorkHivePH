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
// FOUR dialects now, and every one of them has blinded a probe that assumed another:
//   marketplace.html    rewrites #toast's textContent and adds .show
//   platform-actions    APPENDS a .toast-msg child and never touches #toast's class
//   community.html #1   same container-append shape, different child class
//   community.html #2   rewrites a DESCENDANT (#toast-text) and toggles .hidden OFF — no .show ever
// The fourth one cost a false reading on 2026-08-05: pressing "Post to Hive" with an empty composer
// looked like total silence, and the page had said "Write something first" the whole time. I was one
// step from filing a defect against a page that was right.
//
// SO IT NO LONGER ASKS WHICH CLASS. A toast is a message that BECOMES VISIBLE and whose text
// changed -- decided by geometry and content, exactly as blockWrite decides by VERB rather than by
// table name. Class names are dialect; visibility is the behaviour.
//
// And the self-test used to plant an APPENDED CHILD, which every container accepts -- so it returned
// ok:true on a page whose real dialect it could not read at all. A green that only proves the probe
// can see its own plant is a false all-clear. It now exercises BOTH shapes and reports which ones it
// can actually observe, so a caller can tell "no toast fired" from "I cannot read this page".
export async function watchToasts(sel) {
  const el = document.querySelector(sel || '#toast');
  if (!el) return { ok: false, msgs: [], note: 'no toast element on this surface' };
  const msgs = [];
  const seen = (t) => { t = (t || '').trim(); if (t && msgs[msgs.length - 1] !== t) msgs.push(t); };
  const onScreen = () => {
    const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.display !== 'none' && cs.visibility !== 'hidden'
        && parseFloat(cs.opacity || '1') > 0.05;
  };
  let lastOwn = (el.textContent || '').trim();
  // VISIBILITY IS CHECKED ON THE NEXT FRAME, NOT INSIDE THE CALLBACK. community.html writes the text
  // FIRST (container still .hidden -> not on screen) and removes .hidden SECOND; a MutationObserver
  // callback is a microtask, so at both moments getBoundingClientRect() still reports the pre-flush
  // geometry and an inside-the-callback check sees nothing either time. Measured 2026-08-05: the page
  // put "Write something first" on screen and the observer recorded an empty list, which reads
  // exactly like a page that says nothing.
  const settle = () => requestAnimationFrame(() => {
    const own = (el.textContent || '').trim();
    if (own && own !== lastOwn && onScreen()) { seen(own); lastOwn = own; }
    else if (own && onScreen()) seen(own);
  });
  const obs = new MutationObserver(muts => {
    muts.forEach(m => m.addedNodes.forEach(n => { if (n.nodeType === 1) seen(n.textContent); }));
    settle();
  });
  obs.observe(el, { attributes: true, childList: true, characterData: true, subtree: true });
  // AND A SAMPLER, because mutation timing is not worth out-thinking. A synchronous show/hide pair
  // (set the text, drop .hidden, re-add it 3.5s later) hands the observer two microtask callbacks
  // that both land before layout flushes, and no amount of rAF chasing makes that reliable across
  // dialects. Polling the rendered text every 100ms cannot miss a message a person had time to read,
  // and it is indifferent to which class, child or attribute the page uses to express "visible".
  // Cost: one getBoundingClientRect per tick on one element.
  const poll = setInterval(() => { const own = (el.textContent || '').trim(); if (own && onScreen()) seen(own); }, 100);

  // Self-test BOTH dialects: an appended child, and a descendant rewrite while visible.
  const probe = document.createElement('div');
  probe.className = 'toast-msg'; probe.textContent = '__watchToasts append__';
  el.appendChild(probe);
  await new Promise(r => setTimeout(r, 80));
  const okAppend = msgs.includes('__watchToasts append__');
  probe.remove();
  msgs.length = 0;

  // The rewrite dialect, in the page's OWN order: text first (while still hidden), reveal second.
  // Testing it the other way round would pass on a probe that cannot read the real thing.
  const hadHidden = el.classList.contains('hidden');
  const prevText = el.textContent;
  const sink = el.querySelector('[id$="-text"], [class*="text"]') || el;
  const prevSink = sink.textContent;
  sink.textContent = '__watchToasts rewrite__';
  await new Promise(r => setTimeout(r, 20));
  if (hadHidden) el.classList.remove('hidden');
  await new Promise(r => setTimeout(r, 120));
  const okRewrite = msgs.some(x => x.indexOf('__watchToasts rewrite__') >= 0);
  sink.textContent = prevSink;
  if (hadHidden) el.classList.add('hidden');
  if (sink === el) el.textContent = prevText;
  msgs.length = 0;
  lastOwn = (el.textContent || '').trim();

  return { ok: okAppend || okRewrite, okAppend, okRewrite,
           note: (okAppend && okRewrite) ? null : 'only one dialect observable on this surface',
           msgs, clear: () => { msgs.length = 0; },
           stop: () => { obs.disconnect(); clearInterval(poll); } };
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
  /* A FAILURE NOTICE DOES NOT LIVE INSIDE <main>, AND SCOPING TO main MADE THIS ORACLE BLIND TO ITS
   * OWN SUBJECT. A toast, a banner, an offline strip are all fixed-position and therefore direct
   * children of <body>: a fixed element inside a transformed or overflow-clipped ancestor positions
   * against that ancestor rather than the viewport. So main.innerText cannot contain them by
   * construction. Caught the hard way - a central 401 notice was added to getDb()'s transport wrapper
   * and VERIFIED rendering, the element in the DOM carrying the text, and fail_401 still read every
   * sub-assertion false because the probe read 'main' and the notice was a sibling of it. Same shape
   * as the contrast lens that once scoped to <main> while the report mounted outside it and measured
   * 15 of 518 nodes.
   * So failure text is main PLUS the live/alert regions and known notice containers, deduped. It
   * deliberately does NOT read all of body: nav and hub chrome carry standing words like "offline"
   * and "retry" that would forge a pass on every page. */
  const NOTICE = '[role="status"],[role="alert"],[aria-live],.toast,.wh-toast,#toast,.banner,'
               + '.wh-banner,#wh-auth-expired-notice,[class*="notice"],[class*="error-"]';
  const txt = () => {
    const root = m();
    const parts = [root.innerText || ''];
    const seen = new Set([root]);
    for (const el of document.querySelectorAll(NOTICE)) {
      if (seen.has(el) || root.contains(el)) continue;
      if (!el.getClientRects().length) continue;
      if (el.closest('#wh-hub,#wh-wayfinding,#wh-guide-link')) continue;
      seen.add(el);
      parts.push(el.innerText || '');
    }
    return parts.join(' ').replace(/\s+/g, ' ');
  };
  const MUT = /^(POST|PATCH|PUT|DELETE)$/i;
  const guard = (i, x) => MUT.test((x && x.method) || (i && i.method) || 'GET');
  const SAYS_FAIL = /couldn['’]?t|could not|failed|unavailable|error|problem|went wrong|expired|timed out|timeout/i;
  const OFFERS_BACK = /retry|try again|reload|refresh|sign in again/i;

  const baseline = txt();

  /* A FAILURE ORACLE MEASURED WITH NOTHING IN FLIGHT IS VACUOUS, exactly as a loading state measured
   * with nothing loading is - and this function had no guard for it while states() already did.
   * rerun() re-fires loaders as window[k] from a fixed name list. A page that keeps its loaders
   * closure-scoped inside an IIFE or a module exposes none of them, so ZERO reads are issued, the
   * injected failure never lands, and the page keeps showing its already-loaded content. The verdict
   * that follows is a false `ok`, indistinguishable from a page that swallowed the status.
   * NOT HYPOTHETICAL: public-feed CALLS whReadError on its read-error path (public-feed.html:297) with
   * a message that would satisfy this oracle, and still scored fail_401 false. I reported a
   * 17-of-17 platform failure to Ian before catching it.
   * So every injected fetch COUNTS what it intercepts, and a verdict resting on zero reads is forced
   * to null rather than false - `false` would assert the page mishandled a failure it was never shown. */
  let reads = 0;
  const serve = (status, body) => { window.fetch = async (i, x) => {
    const u = typeof i === 'string' ? i : (i && i.url) || '';
    { const b = blockWrite(i, x); if (b) return b; }
    if (!REST.test(u)) return orig(i, x);
    reads++;
    return new Response(typeof body === 'string' ? body : JSON.stringify(body),
                        { status, headers: { 'Content-Type': 'application/json' } });
  }; };

  /* When no loader was reachable, drive the page's OWN route back to the network - the same move
   * states() makes for the same reason. Fenced against navigation: an <a href> here would take the
   * page out from under the injection. */
  const forceRead = async () => {
    if (reads > 0) return reads;
    const el = [...m().querySelectorAll(
      '[role="tab"]:not([aria-selected="true"]),.section-tab:not(.active),.cat-chip,.filter-chip,[data-section]')]
      .filter(e => e.getClientRects().length && !navigatesAway(e))[0];
    if (el) { clickNoNav(el); await new Promise(r => setTimeout(r, 900)); }
    return reads;
  };
  const vac = (o) => (reads > 0 ? o : Object.assign({}, o, { ok: null, vacuous: true }));

  // 401 — an expired session must SAY the session expired and that nothing was sent. Never a bare
  // "try again" (which invites a retry that cannot work) and never a sign-in instruction to someone
  // who IS signed in.
  serve(401, { code: '42501', message: 'JWT expired' });
  await rerun(1200);
  await forceRead();   // no loader on window means nothing was ever in flight
  {
    const t = txt();
    out.fail_401 = vac({
      saysExpiredOrFailed: SAYS_FAIL.test(t),
      namesSession: /session|sign ?in|log ?in|expired/i.test(t),
      saysNothingSent: /nothing was sent|not sent|no changes were saved|nothing was saved/i.test(t),
      bareRetryOnly: OFFERS_BACK.test(t) && !/session|expired/i.test(t),
      ok: SAYS_FAIL.test(t) && /session|expired/i.test(t),
    });
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
    out.fail_timeout = vac({
      statesTimeout: /timed out|timeout|taking longer|slow/i.test(t),
      stuckSkeleton: skel > 0 && !/timed out|timeout|taking longer/i.test(t),
      saysSomething: SAYS_FAIL.test(t),
      ok: /timed out|timeout|taking longer|slow/i.test(t) || SAYS_FAIL.test(t),
    });
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
    out.fail_partial = vac({
      keptSomething: t.length > baseline.length * 0.3,
      namesTheFailure: SAYS_FAIL.test(t),
      ok: t.length > baseline.length * 0.3 && SAYS_FAIL.test(t),
      len: t.length, baselineLen: baseline.length,
    });
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
    out.fail_null_field = vac({
      fabricatedZero: /₱0\.00|₱0\b/.test(t),
      leakedUndefined: /\bundefined\b|\bNaN\b|\bnull\b/i.test(t),
      showsGap: /[\u2014\u2013-]|not set|no data|unknown|not recorded/.test(t),
      ok: !/₱0\.00/.test(t) && !/\bundefined\b|\bNaN\b/i.test(t),
    });
  }

  /* THE THREE THE CC FRAME ASKS FOR AND THIS FUNCTION DID NOT HAVE. The frame names seven injections
   * per view (fail_500, fail_401, fail_timeout, fail_partial, fail_slow, fail_offline,
   * fail_null_field) and only four were implemented, so rows 041/045/046 could not be walked at all -
   * not because the pages resist measurement but because the instrument had no probe. Built rather
   * than recorded as inapplicable. */

  // 500 - a SERVER fault is not the reader's fault and not their session's. It must say something
  // failed WITHOUT blaming the session (that is the 401's job, and conflating them sends a person to
  // re-authenticate over a broken server), and it must not render an empty result as though the
  // server had honestly answered "none" - a 500 rendered as an empty list is the same lie as a
  // partial rendered as complete.
  serve(500, { code: 'PGRST500', message: 'internal server error' });
  await rerun(1200);
  {
    const t = txt();
    const emptyish = /no .{0,24}(yet|found)|nothing (here|to show)|0 (results|items|records)/i.test(t);
    /* A STANDING "Sign in" LINK IS NOT THE PAGE BLAMING THE SESSION. This asked whether the page text
       mentions a session ANYWHERE, and every signed-out-capable surface carries a permanent sign-in
       affordance - so it fired on 4 of 4 pages and I was one step from filing "answers a 500 with
       session language" as a platform defect. The only matched fragment was the literal words
       "Sign in", present whether or not anything failed. The question is whether the FAILURE MESSAGE
       blames the session, so the match must be anchored to a sentence that also states a failure. */
    const _sess = /session|expired|log ?in/i;   // note: bare "sign in" alone is NOT evidence
    const _blames = (t.split(/(?<=[.!?])\s+|\s{2,}/) || [])
      .some(sent => SAYS_FAIL.test(sent) && _sess.test(sent));
    out.fail_500 = vac({
      saysFailed: SAYS_FAIL.test(t),
      blamesSession: _blames,   // must be FALSE on a 500 - a server fault is not the session
      rendersEmptyAsAnswer: emptyish && !SAYS_FAIL.test(t),
      ok: SAYS_FAIL.test(t)
          && !/session|sign ?in|log ?in|expired/i.test(t)
          && !(emptyish && !SAYS_FAIL.test(t)),
    });
  }

  // SLOW - a slow-but-SUCCESSFUL read is not a failure, so the oracle is different from the timeout's:
  // the page must acknowledge the wait while it happens rather than sitting apparently idle, and it
  // must still render the data when it lands. Sampled MID-FLIGHT (the response is deliberately slower
  // than the sample) and then again after it arrives, because "showed a spinner" and "eventually
  // showed the data" are two separate promises and a page can keep one while breaking the other.
  {
    const SLOW = 2600;
    window.fetch = async (i, x) => {
      const u = typeof i === 'string' ? i : (i && i.url) || '';
      { const b = blockWrite(i, x); if (b) return b; }
      if (!REST.test(u)) return orig(i, x);
      await new Promise(r => setTimeout(r, SLOW));
      return orig(i, x);
    };
    rerun(0);
    await new Promise(r => setTimeout(r, Math.floor(SLOW / 2)));    // INSIDE the flight
    const during = txt();
    const busy = [...m().querySelectorAll(
      '[aria-busy="true"],[class*="skel"],[id*="skel"],.shimmer,.spinner,[class*="load"]')]
      .filter(e => e.getClientRects().length).length;
    await new Promise(r => setTimeout(r, SLOW + 600));              // after it lands
    const after = txt();
    out.fail_slow = vac({
      acknowledgesWait: busy > 0 || /loading|loading…|please wait|working/i.test(during),
      busyElements: busy,
      dataArrived: after.length > during.length || after.length > baseline.length * 0.9,
      lengths: [during.length, after.length, baseline.length],
      ok: (busy > 0 || /loading|please wait|working/i.test(during))
          && (after.length > during.length || after.length > baseline.length * 0.9),
    });
  }

  // OFFLINE - a real offline fetch REJECTS, it does not answer with a status. So this throws the
  // TypeError the browser actually throws, rather than serving a 5xx, because a page that only
  // handles !res.ok never reaches its catch and the difference is invisible to a status-based probe.
  // The platform rule this checks: a field-capture write may QUEUE offline, but the page must SAY so -
  // silence lets a worker walk away believing a logbook entry was saved.
  window.fetch = async (i, x) => {
    const u = typeof i === 'string' ? i : (i && i.url) || '';
    { const b = blockWrite(i, x); if (b) return b; }
    if (!REST.test(u)) return orig(i, x);
    throw new TypeError('Failed to fetch');
  };
  await rerun(1200);
  {
    const t = txt();
    out.fail_offline = vac({
      namesConnection: /offline|no (internet|connection|network)|connection|network/i.test(t),
      saysFailed: SAYS_FAIL.test(t),
      saysQueued: /queued|will (be )?sync|saved (locally|on this device)|pending upload/i.test(t),
      // a bare "error" tells a worker in a plant basement nothing actionable
      genericOnly: SAYS_FAIL.test(t)
        && !/offline|no (internet|connection|network)|connection|network/i.test(t),
      ok: /offline|no (internet|connection|network)|connection|network/i.test(t),
    });
  }

  window.fetch = orig;
  await rerun(settle);
  /* THE DENOMINATOR TRAVELS WITH THE VERDICT. reads is how many of the page own REST calls this run
     actually intercepted; 0 means every fail_* above is vacuous rather than passing, and each one is
     stamped vacuous:true with ok forced to null. A caller that ignores this is back to trusting a
     reading taken over nothing. */
  out._reads = reads;
  out._vacuous = reads === 0;
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

// SHARED CHROME, excluded from the per-page text scope because it is the SAME component on every
// surface: measuring it 22 times would inflate every page's denominator with identical nodes and let
// one chrome defect read as 22 page defects. Mirrors the B4_CHROME list in survey_ufai_rubric.js.
const SHARED_CHROME = '#wh-hub, #wh-feedback-panel, #wh-ai-widget, #wh-ai-panel, #wh-ai-trigger, '
  + '#wh-wayfinding, #wh-guide-link, .wh-skip-link, .wh-companion, [class*="companion"], nav[class*="hub"]';

// THE TEXT SCOPE. This used to be `document.querySelector('main') || document.body`, and that silently
// under-measured any page whose OWN content mounts outside <main>. Found 2026-08-06 walking
// analytics-report: after clicking Generate Report the page held 8,353 chars in 518 text nodes, but
// <main id="ar-page"> held only 190 chars in 15 — the whole report renders into #ar-print-wrapper, a
// SIBLING of <main>. The lens measured 15 of 518 nodes (2.9%) and reported "0 failing" while axe found
// NINE real contrast violations in the 503 nodes it never looked at. A pass over 2.9% of a page is the
// short-denominator false 100 in its purest form.
// Measured before changing it, to be sure the old scope was not deliberate: on hive and logbook every
// one of the ~50 out-of-<main> nodes is shared chrome (#wh-hub 28, #wh-feedback-panel 12, #wh-ai-widget
// 4, guide-link, skip-link, nav), so excluding chrome WAS right and is preserved here — what was wrong
// was using <main> as the proxy for "not chrome". Now the scope is the body minus the chrome subtrees,
// which leaves normal pages essentially unchanged (hive gains only its own footer disclosure) and
// restores the report pages' actual payload.
function textScope() {
  return document.body || document.documentElement;
}
function inSharedChrome(el) {
  return !!(el.closest && el.closest(SHARED_CHROME));
}

export function visual(root) {
  // OPTIONAL ROOT (2026-08-18). Contrast is authored per VIEW in the page banks, and V2/V3 are
  // dialogs: measuring the page body with a dialog open credits that view with the whole page's
  // reading, which is the one-measurement-swept-two-views error. Passing the dialog element scopes
  // every sample to the view actually being graded. Omitted, behaviour is unchanged (document.body),
  // so every existing caller reads exactly as before.
  const m = root || textScope();
  // DECORATIVE CONTENT IS EXEMPT, AND THE AUTHOR IS THE ONE WHO DECLARES IT. A node inside
  // aria-hidden="true" is not exposed to assistive tech and carries no information — WCAG's contrast
  // rules apply to informational text, not to dividers. index's anon landing separates four links
  // with `·` spans at text-white/15: legible contrast on a glyph nobody needs to read is not the
  // goal, and darkening them to satisfy a floor would change the design to please a meter. They are
  // marked aria-hidden (which a screen reader needed anyway) and skipped here. A node that merely
  // LOOKS decorative is still measured; only an explicit declaration exempts it.
  const decorative = el => !!(el.closest && el.closest('[aria-hidden="true"]'));
  const vis = el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden'
    && !inSharedChrome(el) && !decorative(el);
  // EMOJI ARE NOT TEXT FOR CONTRAST (2026-08-05, hive walk). An emoji glyph paints in its OWN colours,
  // not in the element's `color`, so comparing that element's foreground against its background says
  // nothing about whether the emoji is legible. hive.html's only 3 APCA "failures" out of 265 nodes
  // were 🔧, 📋 and 📦 — icon chips whose spans carry a tint the glyph never uses. Same family as the
  // platform's other readability-detector false positives on non-prose glyphs (asset codes, XP
  // strings). A node whose visible text is ONLY emoji/symbol characters is excluded; a label that
  // MIXES an emoji with real words is still measured, because those words are real text.
  // ⚠ `\p{Emoji_Component}` MATCHES THE ASCII DIGITS 0-9 (they are keycap components), so the
  // original one-line test — /^[\p{Extended_Pictographic}\p{Emoji_Component}️‍\s]+$/u — classified
  // any purely NUMERIC text as an emoji glyph and dropped it. Found 2026-08-06 on logbook: axe
  // abstained on #total-count ('571'), #machine-count ('34'), #open-count ('5') and #sdot-1 ('1'),
  // and this lens had never measured them either, so nobody had judged them. They are leaf,
  // visible, in scope and non-chrome — they failed only this regex. That silently excluded every
  // numeric-only label on the platform, which is the text a person reads FIRST on a KPI tile: when
  // the figure sits in its own span ('12' in '12 Open Jobs'), its contrast went unmeasured.
  // CORRECTED TEST: a node is emoji-only when it contains at least one pictograph AND no
  // alphanumeric character at all. Digits and letters are real text and are measured; a lone 🔧 or
  // 📦 is still excluded, which is what the hive walk established (its only 3 "failures" of 265
  // nodes were icon chips whose glyph never uses the element's `color`).
  const HAS_WORD_CHAR = /[\p{Letter}\p{Number}]/u;
  // ── EMOJI *PRESENTATION*, NOT EVERY PICTOGRAPH (2026-08-07) ────────────────────────────────────
  // The exclusion exists because an emoji glyph paints in its OWN colours, so the element's `color`
  // says nothing about its legibility. `\p{Extended_Pictographic}` is far wider than that: it also
  // matches geometric and dingbat characters that render as ordinary TEXT in the element's `color` -
  // the KPI chevrons, arrows, a heavy multiplication X. Those are real contrast subjects and were
  // being dropped. Caught by intersecting axe's abstentions against this lens's data-wh-apca stamps:
  // analytics' #kpi-N-chevron and skillmatrix's minus-sign buttons were judged by NEITHER instrument.
  // `\p{Emoji_Presentation}` is the property that actually means "defaults to a colour glyph", and a
  // text-presentation character forced to emoji by VS16 (U+FE0F) is caught by the second branch.
  const HAS_EMOJI_PRESENTATION = /\p{Emoji_Presentation}|\p{Extended_Pictographic}️/u;
  const emojiOnly = (t) => HAS_EMOJI_PRESENTATION.test(t) && !HAS_WORD_CHAR.test(t);
  // OWN TEXT, NOT LEAF-ONLY. The filter used to require `el.childElementCount === 0`, which skipped
  // the single most common label shape on this platform: an element carrying its OWN text beside an
  // element child — `<span><svg/>Knowledge</span>`, `🔧 Mechanical 4`, `<span><i/>CSV</span>`. The
  // container was skipped for having a child; the child is an icon holding no text, so it was
  // skipped too — and the label was therefore measured by NOTHING, while axe abstains on it as
  // well, so no instrument had ever judged it. Found 2026-08-06 closing the contrast_wcag rows: on
  // logbook's MINE feed, 22 of 249 axe abstentions were exactly this shape, all visible with client
  // rects (the zero-rects/hidden hypothesis was measured and refuted), plus 2 on
  // engineering-design, 9 on inventory, 2 on assistant.
  // Using each element's OWN direct text nodes — rather than textContent, which would pull in a
  // child's words and double-count them — measures leaves exactly as before (a leaf's own text IS
  // its textContent) and adds icon+label containers, while a PURE wrapper whose text all lives in
  // children has no own text and is still skipped. Same family as the digit bug above: an exclusion
  // rule silently removing real text from the denominator is worse than a noisy detector, because it
  // makes the surface read "0 failing" over a set that never contained the risky node.
  const ownText = (el) => {
    let t = '';
    for (const n of el.childNodes) if (n.nodeType === 3) t += n.textContent;
    return t.trim();
  };
  // ── FORM FIELDS ARE TEXT, AND NOBODY WAS JUDGING THEM (2026-08-07) ─────────────────────────────
  // An <input>/<textarea>/<select> holds its text in a VALUE and a ::placeholder, never in a child
  // text node, so `ownText` is empty for all of them and this lens skipped every one. axe abstains on
  // them too, because it cannot resolve their composited background - so input text was judged by
  // NEITHER instrument. Found by intersecting axe's abstentions against this lens's own
  // data-wh-apca stamps: asset-hub's #asset-search and analytics' .list-search came back covered by
  // nothing at all. A search field's placeholder is routinely the palest text on a page, which makes
  // this the worst possible blind spot to have had.
  // TEXT-BEARING TYPES ONLY. `input:not([type=hidden])` was too wide and it produced a false failure
  // immediately: resume's #promote-dedupe is a CHECKBOX, whose `value` defaults to the string "on",
  // so the probe measured a non-existent label in the default black input colour and reported Lc 2.6 -
  // a fabricated defect from my own widening. A checkbox, radio, range, colour, file or button input
  // paints no text of its own, so it has no contrast subject; its LABEL is a separate element and is
  // measured as ordinary text like anything else.
  const TEXTY = /^(text|search|email|tel|url|number|password|date|time|datetime-local|month|week)$/i;
  const fieldText = (el) => {
    if (!el.matches || !el.matches('input,textarea,select')) return null;
    if (el.tagName === 'INPUT' && !TEXTY.test(el.getAttribute('type') || 'text')) return null;
    const v = (el.value || '').trim();
    if (v) return { t: v, pseudo: null };                       // the typed value paints in `color`
    const ph = (el.getAttribute && el.getAttribute('placeholder') || '').trim();
    if (ph) return { t: ph, pseudo: '::placeholder' };          // the placeholder has its OWN colour
    return null;
  };
  const texts = [...m.querySelectorAll('*')].filter(el => {
    if (!vis(el)) return false;
    if (fieldText(el)) return true;
    const t = ownText(el);
    // `t.length > 1` USED TO BE THE BAR, and it silently dropped every ONE-CHARACTER label - which is
    // a whole class of real, colour-bearing text on this platform: skillmatrix's decrement buttons
    // whose entire label is a minus sign, the guide-link dismiss X, and single-digit KPI cells ("9",
    // "3") in analytics' tables. Same family as the digits bug above: the exclusion did not make the
    // detector quieter, it made "0 failing" true over a set that never contained the risky node. One
    // character is enough to be illegible.
    return t.length >= 1 && !emojiOnly(t);
  });

  // ── GRADIENT-CLIPPED TEXT: THE `color` IS NEVER PAINTED ─────────────────────────────────────────
  // Found 2026-08-05 on index.html's anon landing, and it nearly caused a real regression. The lens
  // reported 20 failures as "white on amber rgb(250,174,51)" — 'One hive.', 'WorkHive.',
  // 'Build the future.', '35%' — and the fix that follows from that reading is "darken the text on
  // amber". Both halves of the reading were wrong: every one of those nodes is
  //   background-image: linear-gradient(135deg, #f7a21b, #fdb94a); background-clip: text;
  //   -webkit-text-fill-color: rgba(0,0,0,0);
  // so `color: white` paints NOTHING. The gradient IS the glyph, sitting on the dark navy page. The
  // real question is amber-on-navy (high contrast, the platform's hero treatment), not white-on-amber
  // (which never happens). Acting on the raw reading would have edited a property with no effect, or
  // worse, changed the brand gradient on every page to fix a defect that does not exist.
  // So when the fill is transparent and the background is clipped to the text, the FOREGROUND is the
  // gradient's first colour stop and the BACKGROUND is the nearest ancestor that actually paints one.
  const _firstStop = img => {
    const m = /rgba?\([^)]+\)|#[0-9a-f]{3,8}/i.exec(img || '');
    return m ? _parseRGBA(m[0]) : null;
  };
  // ── THE CAP WAS SILENT, AND analytics-report SAT EXACTLY ON IT ─────────────────────────────────
  // `texts.slice(0, 400)` truncated the measured set with no signal, and a truncated denominator
  // under a "0 failing" headline is the false-343 shape: analytics-report reported measured: 400 -
  // exactly the cap - so its reading covered an unknown fraction of the page, and the 2 nodes the
  // axe-intersection found uncovered there ("INCREASE FREQUENCY" table cells) were ordinary words
  // that had simply fallen off the end. Raised, and - the part that matters - REPORTED: `candidates`
  // and `truncated` now travel with the result, so a walk can never bank a green over a cap it could
  // not see. No silent caps.
  const CAP = 2000;
  const candidates = texts.length;
  const truncated = candidates > CAP;
  const rows = texts.slice(0, CAP).map(el => {
    // STAMP EXACT MEMBERSHIP (2026-08-06). A caller dispositioning an axe colour-contrast
    // ABSTENTION needs to know whether THIS lens already judged that node, and a selector
    // round-trip loses the answer: on logbook's MINE feed 219 measured rows resolved back to only
    // 150 distinct elements via nth-of-type paths, so ~70 measured nodes looked "uncovered" when
    // they were not. A data attribute cannot be ambiguous. It is inert, does not affect layout or
    // computed style, and is idempotent across re-runs.
    try { el.setAttribute('data-wh-apca', '1'); } catch (e) { /* empty-catch-allow: read-only DOM */ }
    const cs = getComputedStyle(el);
    const clipsToText = /text/.test(cs.webkitBackgroundClip || cs.backgroundClip || '');
    const fillTransparent = (_parseRGBA(cs.webkitTextFillColor) || { a: 1 }).a === 0;
    const gradientGlyph = clipsToText && fillTransparent ? _firstStop(cs.backgroundImage) : null;
    // A PLACEHOLDER HAS ITS OWN COLOUR, so reading the field's `color` for an empty input would judge
    // the wrong ink - it is usually a strong value colour standing in for pale placeholder grey, which
    // would turn a real failure into a pass. Read ::placeholder when that is the text being shown.
    const fld = fieldText(el);
    const phCs = (fld && fld.pseudo) ? getComputedStyle(el, '::placeholder') : null;
    const fg = gradientGlyph
      || (phCs && _parseRGBA(phCs.color))
      || _parseRGBA(cs.color) || { r: 0, g: 0, b: 0, a: 1 };
    // The element's own background is the glyph here, so it must not also count as the backdrop.
    const bg = _effectiveBg(gradientGlyph ? (el.parentElement || el) : el);
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
    //
    // KNOWN CALIBRATION GAP IN THE Lc 30 TIER, and it has already cost a miss (2026-08-06,
    // analytics-report). The generated print report carried nine 11px/700 severity chips
    // ("INCREASE FREQUENCY" and siblings) coloured with the light FILL red #f87171 on a pale #fee2e2
    // tint. axe measured the WCAG ratio at 2.26 against the 4.5 AA bar and was RIGHT; this lens scored
    // them Lc 42.1 against the 30 floor and PASSED them, because anything under 14px falls into the
    // incidental/small-UI tier. An 11px BOLD LABEL carrying the report's recommendation is not
    // incidental UI, so the tier is too permissive for it.
    // ★SETTLED 2026-08-18, AND THE ANSWER IS "DO NOT RE-TUNE IT" — recalled, not decided afresh.
    // The temptation is to raise this floor for small BOLD labels. That is the SAME MISCALIBRATION this
    // implementation already made once and corrected: the first APCA run on this platform reported
    // 194 of 232 nodes failing, because it used Lc 90 as a floor (Lc 90 is PREFERRED, not a minimum)
    // AND scored sub-14px text — which is OUTSIDE APCA'S PUBLISHED TABLE ALTOGETHER. The table starts
    // at 14px; below that there is no APCA floor to apply, so anything this tier says about 8-12px
    // text is an extrapolation, not a reading.
    // WHICH MEANS THE Lc 30 TIER IS NOT "TOO PERMISSIVE" — it is out of range, and the finding those
    // nodes deserve is a LEGIBLE-SIZE one (is 8px text acceptable at all?), not a contrast one.
    // Re-tuning would re-verdict every sub-14px node on every surface on the strength of a number the
    // standard does not define there, and would resurrect the exact false-positive storm calibration
    // removed.
    // So the gap is covered the way the platform already intends: BOTH lenses run on every walk and
    // the WCAG check is the backstop for small text — which is how the nine chips above were caught,
    // and how the 17 sub-14px failures found on 2026-08-18 were caught. If this lens is ever run
    // alone, sub-14px text is its blind spot, and the answer is to run the pair, not to move the bar.
    // See [[feedback_apca_perceptual_contrast_c5]].
    const floor =
        (px >= 36 || (px >= 24 && w >= 700)) ? 45 :
        (px >= 24 || (px >= 16 && w >= 700)) ? 60 :
        (px >= 18)                           ? 75 :
        (px >= 14)                           ? 60 :   // 14-17px body-ish: the 60 tier is the honest fit
                                               30;    // incidental/small UI text
    // REPORT THE FOREGROUND THAT WAS ACTUALLY MEASURED, NOT THE DECLARED `color`.
    // This field used to be `cs.color` unconditionally, and it misled the very walk that added the
    // gradient-clipped-text handling above: three failures kept printing `fg: rgb(255,255,255)` while
    // the Lc math had correctly used the amber/cyan gradient, so I twice concluded the new code was
    // not running. A findings list that names a colour the calculation never used sends the reader to
    // change the wrong property — the same failure mode as the reading it was introduced to fix.
    // `fgMeasured` is what the number rests on; `fgDeclared` is kept because the gap between them IS
    // the tell that this node is gradient-clipped.
    const fgOut = 'rgb(' + [composited.r, composited.g, composited.b].map(Math.round).join(',') + ')';
    // NAME THE NODE, not just its text. Added 2026-08-06 after this lens reported two 14px failures by
    // TEXT only ("Select a calculation type first." on engineering-design, "Off by default" on resume)
    // and neither could be acted on: searching the DOM for those strings found DIFFERENT instances that
    // MEASURE AS PASSING (Lc 61.5 on the resume one), so the failing node was unidentifiable and both
    // rows had to stay owed rather than be fixed at the wrong element. A finding that cannot be located
    // is not actionable, which makes it barely a finding. `sel` is a nth-of-type path stable enough to
    // re-query, and `where` gives the nearest id/section for a human reading the report.
    const path = (() => {
      const parts = [];
      let n = el;
      for (let i = 0; i < 6 && n && n.nodeType === 1 && n !== document.body; i++) {
        let seg = n.tagName.toLowerCase();
        if (n.id) { parts.unshift('#' + n.id); break; }
        const cls = (n.className || '').toString().trim().split(/\s+/).filter(Boolean)[0];
        if (cls) seg += '.' + cls;
        const sibs = n.parentElement ? [...n.parentElement.children].filter(c => c.tagName === n.tagName) : [];
        if (sibs.length > 1) seg += ':nth-of-type(' + (sibs.indexOf(n) + 1) + ')';
        parts.unshift(seg);
        n = n.parentElement;
      }
      return parts.join(' > ');
    })();
    const anchor = el.closest('[id]');
    // WCAG 2.x FROM THE SAME TWO COLOURS. This is not a second opinion built on a second reading -
    // it reuses the composited foreground and the _effectiveBg() backdrop this node already
    // resolved, so the two lenses can never disagree about WHAT they measured, only about the
    // verdict. That distinction matters because they are SUPPOSED to disagree: the note on the
    // Lc 30 tier above records a real miss where nine 11px/700 chips scored Lc 42.1 (pass) and
    // WCAG 2.26 (fail), and says plainly that "the WCAG check is the backstop for small text ...
    // if this lens is ever run alone, sub-14px text is its blind spot."
    // Until now that backstop was unavailable exactly where it is needed most: INSIDE DIALOGS. A
    // separate composited probe has to abstain there, because a dialog card is a translucent
    // gradient over a translucent scrim and a ratio needs one flat second colour - 17 bank rows sat
    // owed on precisely that. _effectiveBg already solves it by averaging the gradient's stops, so
    // the backstop now reaches the views it could not.
    const wcagRatio = (() => {
      const L = (c) => { const f = (v) => { v = Math.max(0, Math.min(255, v)) / 255;
        return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
        return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
      const A = L(composited), B = L(bg);
      return (Math.max(A, B) + 0.05) / (Math.min(A, B) + 0.05);
    })();
    const wcagNeed = (px >= 24 || (px >= 18.66 && w >= 700)) ? 3.0 : 4.5;
    return { txt: (el.textContent || '').trim().slice(0, 32), px: Math.round(px), w,
             Lc: Math.round(Lc * 10) / 10, floor,
             ratio: Math.round(wcagRatio * 100) / 100, need: wcagNeed,
             wcagOk: bg.inconclusive ? null : wcagRatio >= wcagNeed - 0.05,
             ok: bg.inconclusive ? null : Lc >= floor,
             inconclusive: !!bg.inconclusive,
             fg: fgOut,
             fgDeclared: cs.color,
             clipText: !!gradientGlyph,
             sel: path,
             where: anchor ? '#' + anchor.id : null,
             bg: 'rgb(' + [bg.r, bg.g, bg.b].map(Math.round).join(',') + ')' };
  });
  const fails = rows.filter(r => r.ok === false).sort((a, b) => a.Lc - b.Lc);
  const unknown = rows.filter(r => r.inconclusive);

  // REDUCED MOTION — a BEHAVIOURAL oracle, so a structural answer may not settle it (R6).
  // This returned `ok: declaresGuard`, i.e. "does ANY @media (prefers-reduced-motion) rule exist
  // anywhere on this page" — a page-level boolean. It certified pages compliant while their motion
  // ran, because a page can declare a reduce block for one component and none for the rest. hive
  // declared 8 such blocks and 55 declarations, all about .ss-tile and .ss-rd-track, while a shared
  // launcher's three infinite animations honoured nothing. Measured 2026-08-07 by flipping the
  // media on a live page: inventory ran 8 visible animations and still ran 8 under reduce;
  // voice-journal 8 and 8 — and voice-journal ALREADY had a reduce block, which is precisely how
  // the boolean passed it. companion-launcher.js contained no reduce rule at all.
  // Now each animated element is matched against the reduce rules INDIVIDUALLY, so the verdict is
  // a SET rather than a boolean. Two further corrections came with it:
  //   * VISIBILITY. getClientRects() is empty inside a display:none subtree. A first hand-rolled
  //     probe of mine omitted that and inflated hive from 0 visible animations to 5, nearly
  //     producing a fabricated finding. Motion nobody can see is not a 2.2.2 exposure, but it is
  //     not nothing either — a spinner animates only while loading — so it is reported as `latent`
  //     instead of being dropped or counted.
  //   * A TRANSITION IS NOT MOTION-ON-ARRIVAL. The old filter counted any transitionDuration > 0,
  //     which is nearly every button on the platform. A transition fires on interaction and cannot
  //     run indefinitely, so it never belonged in the same count as an infinite animation.
  // CAVEAT, stated rather than glossed: matching a selector proves a rule TARGETS the element, not
  // that it WINS — specificity or source order could still defeat it. So this is a strong static
  // screen, and the authority remains an external flip of the media with the sets compared. The
  // walk does that; `animatedNames` is exposed so it can.
  const reduceSel = [];
  for (const sheet of document.styleSheets) {
    let rules; try { rules = sheet.cssRules; } catch (e) { continue; }  // empty-catch-allow: cross-origin sheet
    const walk = (list) => {
      for (const r of list || []) {
        const cond = r.media ? (r.conditionText || r.media.mediaText || '') : '';
        if (/prefers-reduced-motion\s*:\s*reduce/.test(cond)) {
          for (const inner of r.cssRules || []) {
            const a = inner.style && (inner.style.animation || inner.style.animationName);
            if (inner.selectorText && a && /\bnone\b/.test(a)) reduceSel.push(inner.selectorText);
          }
        }
        if (r.cssRules) walk(r.cssRules);
      }
    };
    walk(rules);
  }
  const declaresGuard = reduceSel.length > 0;
  const isGuarded = (el) => reduceSel.some(s => {
    try { return el.matches(s); } catch (e) { return false; }  // empty-catch-allow: unsupported selector
  });
  const animated = [], latent = [], unguarded = [];
  for (const el of document.querySelectorAll('*')) {
    const cs = getComputedStyle(el);
    if (!cs.animationName || cs.animationName === 'none') continue;
    if (!(parseFloat(cs.animationDuration) > 0.01)) continue;
    const tag = cs.animationName + (cs.animationIterationCount === 'infinite' ? '*' : '');
    if (!vis(el)) { latent.push(tag); continue; }
    animated.push(tag);
    if (!isGuarded(el)) unguarded.push(tag);
  }
  return {
    // The WCAG sibling, over the SAME `rows` - same nodes, same denominator, same inconclusive set.
    wcag: {
      measured: rows.length,
      candidates,
      truncated,
      failing: rows.filter(r => r.wcagOk === false).length,
      inconclusive: unknown.length,
      ok: (unknown.length || truncated) ? null : rows.every(r => r.wcagOk !== false),
      worst: rows.filter(r => r.wcagOk === false).sort((x, y) => x.ratio - y.ratio).slice(0, 10),
    },
    apca: {
      measured: rows.length,
      // THE DENOMINATOR'S OWN HONESTY travels with the verdict: `candidates` is how many nodes
      // qualified and `truncated` says whether the cap cut any off. `ok` is forced to null when it
      // did, because "0 failing" over a truncated set is not a pass - it is an unknown wearing one.
      candidates,
      truncated,
      failing: fails.length,
      inconclusive: unknown.length,
      ok: (unknown.length || truncated) ? null : fails.length === 0,
      worst: fails.slice(0, 10),
      unmeasurable: unknown.slice(0, 4).map(u => u.txt),
      // MEASURED SET, added 2026-08-06 so an axe abstention can be dispositioned by SET
      // INTERSECTION instead of by count. The `contrast_wcag` oracle demands "a denominator with
      // no unresolved abstention", and axe abstains on every node whose background it cannot
      // composite. Until now the only way to answer that was to compare COUNTS - "the lens
      // measured 219, axe abstained on 249" - which is a necessary condition and never a
      // sufficient one, because the two sets overlap without either containing the other: this
      // lens scopes to body-minus-shared-chrome by design while axe abstains across the chrome
      // too. Measured on logbook: TEAM 47 vs 61 abstentions, MINE 219 vs 249 - loading four times
      // the content grew BOTH numbers and widened the gap, so no amount of populating a page can
      // rescue a count argument. Five rows sit blocked on exactly this (assistant 20v11,
      // engineering-design 48v40, inventory 134v120, logbook 61/249, plus report-sender's).
      // Exposing the set lets a walk assert the real thing: every abstained node IS inside the
      // measured set, node by node. Selectors only - no text, so this stays cheap to serialise.
      // Verified on logbook: 47 selectors for 47 measured nodes, 0 empty.
      // CAVEAT, measured rather than assumed: these selectors are nth-of-type PATHS and are not
      // guaranteed to resolve back to a unique element - on logbook's MINE feed 219 measured rows
      // resolved to only 150 distinct elements, so a selector-based intersection under-reports
      // coverage and inflates the "uncovered" list. Use `measuredMark` below for an exact answer
      // and keep these for human reading.
      measuredSel: rows.map(r => r.sel).filter(Boolean),
      // EXACT MEMBERSHIP. Every node this lens measured is stamped with data-wh-apca="1", so a
      // caller can ask `el.hasAttribute('data-wh-apca')` per axe abstention and get a yes/no with
      // no selector round-trip to lose it. That is what the contrast_wcag oracle actually needs:
      // "no unresolved abstention" is a set claim, and a count comparison can never settle it -
      // on logbook, loading 4x the content grew the lens denominator 47->219 AND the abstentions
      // 61->249, so the gap widened rather than closed.
      measuredMark: 'data-wh-apca',
    },
    reduced_motion: {
      animatedElements: animated.length,
      // LATENT is reported, never merged into the verdict: these animate inside a hidden subtree,
      // so no one perceives them now, but a loading spinner is exactly this and becomes visible the
      // moment it is needed. Counting them would fabricate exposures; dropping them would hide a
      // real backlog. Named so a walk can decide for itself.
      latentElements: latent.length,
      latentNames: [...new Set(latent)],
      declaresGuard,
      reduceSelectors: reduceSel.length,
      // THE VERDICT IS THE UNGUARDED SET, not the existence of a guard.
      unguarded: [...new Set(unguarded)],
      animatedNames: [...new Set(animated)],
      ok: animated.length === 0 ? null : unguarded.length === 0,
      note: animated.length === 0
        ? ('nothing VISIBLE animates on this surface'
           + (latent.length ? ' (' + latent.length + ' animate inside hidden subtrees - latent, not'
              + ' currently perceivable, listed in latentNames)' : ' - nothing to honour'))
        : (unguarded.length
           ? unguarded.length + ' visible animation(s) match no animation:none rule inside any'
             + ' @media (prefers-reduced-motion: reduce) block'
             + (declaresGuard ? ' - the page DOES declare ' + reduceSel.length + ' such rule(s),'
                + ' they just do not cover these' : ' - the page declares none at all')
           : null),
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
/* NO INDUCED CLICK MAY NAVIGATE. states() cannot OBSERVE loading/skeleton/disabled/busy on a settled
 * page - it INDUCES them, which means it clicks things - and a click that follows a link takes the
 * page out from under the measurement. That killed the execution context on 7 of 22 pages in an
 * alternating context-destroyed / next-goto-timeout pattern which reads as infrastructure, not as
 * this probe following an <a href>: I blamed the browser, then batch size, then invented an
 * auto-redirect defect on skillmatrix before reading the file disproved it.
 * There are THREE induced-click sites (the re-query fallback, the disabled probe, the busy probe) and
 * a per-site filter would have to be remembered at each one, so the property is made structural here.
 * NOTE aria-disabled DOES NOT PREVENT NAVIGATION: <a href="x" aria-disabled="true"> still navigates
 * on click, and the disabled probe deliberately clicks exactly that selector.
 * A same-document hash target is safe and stays clickable. */
function navigatesAway(el) {
  const h = el && el.getAttribute && el.getAttribute('href');
  if (h === null || h === undefined || h === '' || h.charAt(0) === '#') return false;
  return true;
}
function clickNoNav(el) {
  const fence = (ev) => {
    const a = ev.target && ev.target.closest && ev.target.closest('a[href]');
    if (a && navigatesAway(a)) { ev.preventDefault(); ev.stopPropagation(); }
  };
  window.addEventListener('click', fence, true);
  try { el.click(); } finally { window.removeEventListener('click', fence, true); }
}

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
      // ANY href NAVIGATES, not just an absolute one. This filter excluded /^https?:/ and nothing
      // else, so a relative href sailed through and got CLICKED: skillmatrix's
      // <a role="tab" href="achievements.html"> took the page out from under its own measurement.
      // The execution context died mid-probe on 7 of 22 pages, in an alternating
      // context-destroyed / next-page-goto-timeout pattern that reads as infrastructure rather than
      // as this probe following a link - I blamed the browser, then batch size, then invented an
      // auto-redirect defect on skillmatrix before reading the file disproved it.
      // A same-document hash target is still safe, so keep those eligible.
      const reQuery = [...m().querySelectorAll(
        '[role="tab"]:not([aria-selected="true"]),.section-tab:not(.active),.cat-chip,.filter-chip,[data-section]')]
        .filter(el => vis(el) && !navigatesAway(el))[0];
      // AND FENCE THE CLICK ANYWAY, because the selector list will grow and the next contributor
      // should not have to remember this. A capture-phase guard costs nothing and makes the
      // no-navigation property structural instead of a property of one filter.
      if (reQuery) clickNoNav(reQuery);
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
      // THE VERDICT IS THE ORACLE, NOT ONE WAY OF SATISFYING IT. The row this settles reads "the
      // component's loading state is distinguishable from its empty state" — and this used to answer
      // a narrower question: "is there a skeleton, or does it say the word loading?". A surface that
      // paints its shell immediately, so a person never sees an empty state while 4 reads are in
      // flight, satisfies the claim with neither. marketplace-seller-profile does exactly that and was
      // scored false with looksEmptyInstead=false and distinguishableFromEmpty=true sitting in the
      // same object. An instrument stricter than its own oracle manufactures defects.
      // Teeth are intact: this is FALSE whenever the surface shows an empty/invitation message with no
      // skeleton while requests are still outstanding, which is the defect the row exists for.
      ok: held === 0 ? null : !(INVITE.test(txt) && skel.length === 0),
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
      clickNoNav(el);                   // a REAL click, never force:true - and never a navigation
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
      clickNoNav(btn);
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
      // `cancelled` joins the reversibility alternatives. The comment above names four consequence
      // SHAPES this is meant to recognise -- a present-tense verb about what the action does, a
      // visibility change, a REVERSIBILITY STATEMENT, or a timing promise -- and cancellation is
      // squarely the third. It was missing only as vocabulary: copy reading "the request can still be
      // cancelled until you pick a provider" tells a person exactly what follows and how to back out,
      // and scored as saying nothing because the list happened to know `removed`, `undone` and
      // `changed` but not the word this product actually uses for that state (`cancelled_by_client`).
      // Widening the vocabulary of a shape the oracle already claims is not loosening it.
      saysWhatNext: /(what to do next|next step|we.ll|you.ll (get|receive|hear)|within \d|once (you|the)|after you|goes live|publishes|will be (sent|shown|live|notified)|can still be (removed|undone|changed|cancelled|canceled)|cannot be undone|sees (that|your)|changes what|appears on|notifie[sd]|takes effect)/i.test(body),
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
  //
  // SR-ONLY IS EXEMPT (2026-08-05, index.html anon walk). A screen-reader-only region is visually
  // hidden by collapsing its box to ~1px while its text keeps its natural width, so EVERY child
  // reports enormous overflow by construction. index.html's anon landing produced 8 such offenders —
  // ul/li at box 1px against ~1960px of content — and it cost several probes to prove none of them
  // was real (docScrollsSideways was false throughout). A lens that reports 8 defects on a correct
  // page trains the reader to ignore it, which is worse than reporting none.
  const srOnly = el => !!el.closest('.sr-only, .visually-hidden, [class*="screen-reader"]');

  // A NEGATIVE MARGIN ON AN OVERSIZED TAP TARGET IS THE ACCESSIBLE PATTERN, NOT AN OVERFLOW
  // (2026-08-05, hive walk). hive.html's `.ss-snooze` is `margin:-6px -6px -6px auto` with
  // min-width/min-height 44px: the button is deliberately padded out to a 44px hit area for a gloved
  // hand, and pulled back 6px so its small glyph still lines up optically with the row edge. The row
  // therefore reports scrollWidth 6px over clientWidth — the tap-target rule and the overflow rule
  // pointing in opposite directions on the same correct code. Exempt an element whose overflow is no
  // larger than the biggest negative horizontal margin among its children; a genuine overflow exceeds
  // that, so this narrows the check without blinding it.
  const negPull = el => Math.max(0, ...[...el.children].map(c => {
    const cs = getComputedStyle(c);
    return Math.max(0, -parseFloat(cs.marginRight) || 0) + Math.max(0, -parseFloat(cs.marginLeft) || 0);
  }));

  // AN OUT-OF-FLOW DECORATIVE CHILD IS NOT A CONTAINER OVERFLOW (2026-08-06, index.html anon walk).
  // The landing page reported one offender: div.relative.w-full with 493px of content in a 448px box.
  // The real content child measured 448 and fit; the 45px came from a sibling `div.absolute` laid out
  // at 538px — a decorative glow deliberately bleeding past its parent, with the parent's overflowX
  // visible and docScrollsSideways FALSE. An absolutely-positioned child is out of flow: it cannot
  // widen its parent's layout and cannot produce a scrollbar, which the separate document-level check
  // already measures. Exempt an element whose overflow is fully accounted for by its widest
  // out-of-flow child; a genuine in-flow overflow exceeds that, so this narrows the check without
  // blinding it — the same shape as the sr-only and negative-margin exemptions above.
  // DESCENDANTS, not only children (2026-08-22): community's #profile-avatar was flagged for its
  // GRANDCHILD - .wh-avatar-lvl, the level pill deliberately hung below the circle at bottom:-8px,
  // position:absolute by design (utils.js documents the hang). An out-of-flow box cannot widen its
  // ancestor's layout no matter its depth, and the child-only sweep missed exactly the depth the
  // avatar markup uses. Bounded to 40 descendants so a huge container never turns this lens O(n²).
  const outOfFlowBleed = el => Math.max(0, ...[...el.querySelectorAll('*')].slice(0, 40).map(c => {
    const pos = getComputedStyle(c).position;
    if (pos !== 'absolute' && pos !== 'fixed') return 0;
    return Math.max(0, Math.round(c.getBoundingClientRect().width) - el.clientWidth);
  }));
  // AN ELEMENT'S OWN DECORATIVE PSEUDO IS NOT A CONTENT OVERFLOW (2026-08-21, community walk).
  // The tier-legend avatar ring is ::before/::after halos that deliberately extend past the box
  // (negative inset — and Chromium counts even a transformed pseudo's bounds in scrollWidth, so no
  // halo-by-pseudo can ever satisfy a raw scrollWidth check). The oracle protects CONTENT — squeezed
  // text, clipped children — and a pseudo cannot join a DOM Range, so measuring the element's REAL
  // contents with one separates the two: if everything real fits while an absolute pseudo renders,
  // the overflow is the decoration. Genuine squeezed text lays out wider than the box and the Range
  // still catches it, so this narrows the check without blinding it — the fourth exemption of the
  // same shape as sr-only, negative-margin and out-of-flow-child above.
  const pseudoDecorOnly = el => {
    const rendered = s => s.content !== 'none' && s.position === 'absolute';
    const hasPseudo = n => rendered(getComputedStyle(n, '::before')) || rendered(getComputedStyle(n, '::after'));
    // the decorating pseudo may live on a DESCENDANT while the scroll overflow propagates to the
    // container (2026-08-22: #profile-avatar flagged for the tier ring on its inner .wh-avatar) -
    // the Range still proves every REAL box fits, so the excess is the decoration wherever it hangs
    if (!hasPseudo(el) && ![...el.querySelectorAll('*')].slice(0, 40).some(hasPseudo)) return false;
    try {
      const r = document.createRange();
      r.selectNodeContents(el);
      return Math.round(r.getBoundingClientRect().width) <= el.clientWidth + 2;
    } catch { return false; }
  };
  const offenders = [...m.querySelectorAll('*')].filter(el =>
    el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0 &&
    getComputedStyle(el).overflowX === 'visible' &&
    !el.closest('details:not([open])') && !srOnly(el) && vis(el) &&
    (el.scrollWidth - el.clientWidth) > negPull(el) &&
    (el.scrollWidth - el.clientWidth) > outOfFlowBleed(el) &&
    !pseudoDecorOnly(el)
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

  // MEASURE THE TARGET A FINGER ACTUALLY HITS (2026-08-05, hive walk). A checkbox or radio wrapped in
  // a <label> is activated by clicking ANYWHERE in that label, so the input's own 13x13 box is not the
  // tap target — the label is. hive.html reported 6 controls under 44px; all six were intent-capture
  // radios inside labels measuring 293x59, comfortably over both the WCAG 2.5.8 24px minimum and this
  // platform's 44px floor. Reporting the input's box would send someone to enlarge a radio that is
  // already easy to hit, and would bury a control that genuinely is not.
  // The battery already carries the sibling exemption for inline text links
  // (inlineTextLinksUnder44_exempt); this is the same principle applied to labelled form controls.
  const hitBox = el => {
    const lab = el.closest('label');
    if (lab && /^(checkbox|radio)$/i.test(el.type || '') &&
        getComputedStyle(lab).cursor === 'pointer') return lab.getBoundingClientRect();
    return el.getBoundingClientRect();
  };
  // `summary` WAS MISSING FROM THIS LIST AND IT COST A REAL DEFECT (2026-08-05, hive walk). A
  // <summary> is the click target of a <details> disclosure — as much a control as a button — and
  // leaving it out meant this lens reported tapTargetsUnder44: 0 on a page where ufai_battery found
  // THREE summaries at 606x24px ('Hive readiness details', 'Pattern Alerts', 'Hive Activity Live'),
  // under both the WCAG 2.5.8 24px floor and this platform's 44px one. The exemptions added above make
  // this lens quieter; this addition is the other half, and the order matters — a lens that only ever
  // loses checks drifts toward silence.
  const small = [...m.querySelectorAll('button, a[href], input:not([type=hidden]), select, textarea, summary, [role="button"], [onclick]')]
    .filter(el => vis(el) && !inProse(el))
    .map(el => { const r = hitBox(el);
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
    // THE BASELINE IS RE-CAPTURED HERE, not inherited from availability()'s start: four inductions
    // have run since then, and one of them can legitimately leave an empty-state invitation on
    // screen (a 200-[] serve resolves a list to genuinely-zero). Judging THIS block against the
    // pre-induction baseline attributed that leftover to the slow read and failed
    // marketplace-seller-profile for a claim it never made mid-hang (2026-08-21; the isolated
    // replication kept the loaded review on screen for the whole hang).
    const baselineInviteNow = INVITE.test(txt());
    window.fetch = async (i, x) => {
      const u = typeof i === 'string' ? i : (i && i.url) || '';
      { const b = blockWrite(i, x, writeUrls); if (b) { writes++; return b; } }
      if (!REST.test(u)) return orig(i, x);
      reads++;
      await new Promise(r => setTimeout(r, 8000));
      return orig(i, x);
    };
    rerun(0);                                    // deliberately NOT awaited — sampled mid-flight
    await new Promise(r => setTimeout(r, 800));
    if (reads === 0) {
      // No loader reachable from window (IIFE-scoped pages) — drive the page's OWN route back to
      // the network the way failures()' forceRead does: click an inactive tab/chip, fenced against
      // navigation. Only then can a mid-hang sample measure anything real.
      const el = [...m().querySelectorAll(
        '[role="tab"]:not([aria-selected="true"]),.section-tab:not(.active),.cat-chip,.filter-chip,[data-section]')]
        .filter(e => e.getClientRects().length && !navigatesAway(e))[0];
      if (el) clickNoNav(el);
    }
    await new Promise(r => setTimeout(r, 1800));
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
      prematureEmptyState: invites && !baselineInviteNow,   // "be the first" while it does not yet know
      inviteAtRest: baselineInviteNow,
      inviteText: inviteEl ? (inviteEl.innerText || '').trim().slice(0, 70) : ((txt().match(INVITE) || [])[0] || null),
      saysLoading,
      enabledActionControls: liveActions,
      readsInFlight: reads,
      // A LOADING STATE MEASURED WITH NOTHING LOADING IS VACUOUS - the same zero-reads guard
      // failures() carries (its comment block above). marketplace-seller-profile keeps loadSeller/
      // loadListings closure-scoped in an IIFE, so rerun() re-fired nothing, no read hung, and the
      // quiet page scored `false` as if it had hidden a load it was never given (2026-08-21).
      // `null` + note = abstain with mechanism, which the walker maps to declared-na, not to a pass.
      ok: reads === 0 ? null : ((busy > 0 || saysLoading) && !(invites && !baselineInviteNow)),
      note: reads === 0 ? 'no loader reachable from window (page-scoped symbols) - zero reads were '
                        + 'induced, so no in-flight moment existed for this oracle to judge; a false '
                        + 'here would indict a page that was never shown a slow read' : undefined,
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
