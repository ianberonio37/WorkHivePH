// capability: alert_toast_inline
// capability: display_source_chip
// ─────────────────────────────────────────────
// utils.js — Shared utilities for WorkHive platform
// Loaded before page scripts on every page.
// ─────────────────────────────────────────────

// ── SaaS-layer L (Error Tracking & Logs) — the ONE CENTRAL capture backbone ──────────────────
// METHOD LAW (Ian, 2026-07-22): a defect on N surfaces is ONE unadopted central component, not N
// fixes. Rather than chip an error-logger into every page, the L-layer capture lives HERE, once,
// loaded before every page script:
//   • window.whLogError(context, err)  — the single SINK every caught-error log routes through.
//     To add real aggregation later (Sentry / a /ingest endpoint / logEvent) edit THIS ONE
//     function — every surface upgrades at once, zero re-chipping.
//   • global 'error' + 'unhandledrejection' listeners — capture the UNCAUGHT class platform-wide
//     with ZERO per-page code (a bug that escapes a page's try/catch is still logged + greppable).
// Caught errors still call whLogError/console.error at their site (inherent — a caught error is a
// local decision), but the IMPLEMENTATION + the uncaught net are centralized. Gate: `error-capture`.
(function whErrorCaptureBackbone() {
  if (window.whLogError) return;                       // idempotent (defensive against double-load)
  // D21 frontend observability (2026-07-23): this IS the promised upgrade point, now wired.
  // Errors go to our OWN `client_errors` table (mig 20260723000001) - not a third-party error
  // service - so nothing leaves the platform and triage uses the tooling/RLS we already run.
  // DIAGNOSTICS ONLY: message + truncated stack + pathname + coarse UA. Never form values, row
  // payloads, tokens, or the query string (it can carry ids). Best-effort and totally silent on
  // failure: a logger that throws, blocks, or loops would be worse than the dark it replaces.
  var _errSent = 0, _errSeen = Object.create(null), _ERR_CAP = 20;   // per page-load flood cap
  window.whLogError = function (context, err) {
    try { console.error('[whLogError]', context, err); } catch (_) { /* empty-catch-allow: console unavailable, logging is best-effort */ }
    try {
      if (_errSent >= _ERR_CAP) return;                       // a crash loop must not flood the table
      var msg = '';
      try { msg = String((err && (err.message || err.reason || err)) || ''); } catch (_) { msg = 'unstringifiable error'; }
      if (!msg) return;
      var key = context + '|' + msg.slice(0, 120);
      if (_errSeen[key]) return;                              // dedupe identical errors per load
      _errSeen[key] = 1;
      var stack = '';
      try { stack = String((err && err.stack) || ''); } catch (_) { /* empty-catch-allow */ }
      var db = window._whSupabaseClient;
      if (!db || typeof db.from !== 'function') return;        // no client yet (pre-auth) -> console only
      _errSent++;
      db.from('client_errors').insert({
        hive_id: (typeof window.whHiveId === 'function' ? window.whHiveId() : null) || null,
        worker_name: (typeof window.whWorker === 'function' ? window.whWorker() : null) || null,
        context: String(context || 'error').slice(0, 120),
        message: msg.slice(0, 2000),
        stack: stack ? stack.slice(0, 4000) : null,
        page: (location && location.pathname) || null,        // pathname ONLY - never location.search
        user_agent: (navigator && navigator.userAgent || '').slice(0, 300)
      }).then(function () {}, function () {});                 // swallow: never surface a logging failure
    } catch (_) { /* empty-catch-allow: error reporting must never itself throw */ }
  };
  try {
    window.addEventListener('error', function (e) {
      window.whLogError('uncaught-error', (e && (e.error || e.message)) || e);
    });
    window.addEventListener('unhandledrejection', function (e) {
      window.whLogError('unhandled-rejection', (e && e.reason) || e);
    });
  } catch (_) { /* empty-catch-allow: addEventListener unavailable (non-browser), the global net is best-effort */ }
})();

// ── SaaS-layer RL (Rate Limiting) + C (LLM) — the ONE CENTRAL AI-error → user-message mapper ─────
// METHOD LAW (§0.4b): a page's AI/edge call that fails should show a SCOPE-CORRECT message (429 = "you
// hit the rate limit, wait" · 503 = "AI busy" · network = "check connection"), not a raw error or a
// generic "failed". Rather than a bespoke 429/503 check in every AI catch, that mapping lives HERE once.
// Server rate-limits are already central (_shared/rate-limit.ts checkAIRateLimit → structured 429, gated
// by perf_l5_llm_resilience); the ai-gateway is the LLM front door. This is the CLIENT side of both: a
// page's AI catch calls `showToast(whAiError(err, 'AI failed'))` and the 429/503/offline UX is uniform +
// tunable in one place. Gate: `rate-limit-handling`.
(function whAiErrorMapper() {
  if (window.whAiError) return;
  window.whAiError = function (err, fallback) {
    var m = '';
    try { m = String((err && (err.message || err.error || err.status || err.code)) || err || ''); } catch (_) { /* empty-catch-allow: err stringify is best-effort, fall through to the generic message */ }
    /* T45 (2026-08-27): the taxonomy speaks Filipino too. Every page is bilingual through
       _t(en, fil) and this shared layer was not, so a worker on the FIL toggle got Filipino
       chrome and an English sentence at the exact moment something failed and precision mattered
       most. _t is defined in this same file and falls back to EN when a phrase has no FIL, so
       partial coverage can never blank a message. Register matches the platform's existing FIL
       copy: Taglish, technical nouns left in English (session, AI service, koneksyon). */
    var T = (typeof window !== 'undefined' && typeof window._t === 'function')
      ? window._t : function (en) { return en; };
    if (/\b401\b|\b403\b|jwt|not authenticated|session expired|row-level security|42501|permission denied/i.test(m))
      return T('Your session has expired. Sign in again, then retry - your typed work is still on this page.',
               'Nag-expire na ang session mo. Mag-sign in ulit, tapos subukan muli - nasa page pa rin ang na-type mo.');
    if (/\b429\b|rate.?limit|too many|quota|exhaust/i.test(m)) {
      /* T39 (2026-08-28): the SERVER knows exactly when the limit clears - every deny in
         _shared/rate-limit.ts now carries retry_after_seconds and a Retry-After header - and this
         sentence still said "a moment". "A moment" is the one thing a person cannot act on: they
         retry too early, get refused again, and conclude the feature is broken rather than busy.
         The marketplace surfaces already read this field; the AI taxonomy was the layer that had
         not caught up. Read defensively, because callers pass several error shapes and a missing
         window must fall back to the old sentence rather than print "in about null". */
      var secs = null;
      try {
        var b = (err && (err.body || err.context || err.data)) || err || {};
        var v = (b.retry_after_seconds != null) ? b.retry_after_seconds
              : ((b.retryAfter != null) ? b.retryAfter : null);
        if (v != null && isFinite(Number(v)) && Number(v) > 0) secs = Math.ceil(Number(v));
      } catch (_) { /* empty-catch-allow: a missing window is not an error, it is the old message */ }
      if (secs) {
        var mins = Math.ceil(secs / 60);
        return (secs < 90)
          ? T('The AI is at its limit right now. Try again in about ' + secs + ' seconds.',
              'Nasa limitasyon ang AI ngayon. Subukan muli pagkalipas ng humigit-kumulang ' + secs + ' segundo.')
          : T('The AI is at its limit right now. Try again in about ' + mins + ' minutes.',
              'Nasa limitasyon ang AI ngayon. Subukan muli pagkalipas ng humigit-kumulang ' + mins + ' minuto.');
      }
      // T39 attribution fix (2026-09-02): the exhausted window is usually the GLOBAL platform
      // budget (ai_global_budget), so "You have hit..." blamed the worker for platform demand —
      // the which-server-sentences class, mild form. Neutral is true in every case. The
      // "Nothing you typed was lost." reassurance stays with CALLERS (assistant.html appends it)
      // because only a page that actually preserves the draft may truthfully claim it.
      return T('The AI is at its limit right now. Wait a moment and try again.',
               'Nasa limitasyon ang AI ngayon. Maghintay sandali at subukan muli.');
    }
    if (/\b50[234]\b|unavailable|overloaded|timeout|timed out/i.test(m))
      return T('The AI service is busy right now. Please try again shortly.',
               'Busy ang AI service ngayon. Subukan muli mamaya.');
    if (/network|failed to fetch|offline|connection|name resolution/i.test(m))
      return T('Network problem: check your connection and try again.',
               'May problema sa koneksyon: suriin ang koneksyon at subukan muli.');
    /* The caller's fallback is their own EN sentence, so it is returned untranslated - a page
       that wants a Filipino fallback passes one through _t itself. */
    return fallback || T('Something went wrong. Please try again.', 'May naganap na mali. Subukan muli.');
  };
})();

// ── Edge-function error unwrap (T82, 2026-08-26) ──────────────────────────────────────────
// supabase-js collapses EVERY non-2xx from functions.invoke into one FunctionsHttpError whose
// message is the literal string "Edge Function returned a non-2xx status code". The status and
// the body are still there, on `error.context` (a Response) - but a caller that only reads
// `error.message` never sees them.
//
// ★THIS SILENTLY UNDOES THE WORK THE FUNCTIONS DID. rate-limit.ts returns 429 with "AI call
// limit reached for this hive. Try again in an hour." - cause named, clearing time named,
// exactly the bar whAiError exists to hold. Measured on asset-hub: that refusal reached the
// worker as "Could not reach Asset Brain: Edge Function returned a non-2xx status code", a
// CONNECTION-flavoured sentence for a QUOTA event, sending them to check their signal instead
// of waiting an hour. whAiError could not help either: it keys on /429|rate.?limit|quota/ and
// the generic string contains none of them, so it fell through to its own fallback.
//
// The unwrap was already hand-rolled in companion-launcher, analytics and assistant - three
// copies, thirteen other files without it. This is that idiom, once.
//
// Async because reading the body is; callers are already inside async handlers.
// Returns the function's OWN sentence when it sent one (it is more specific than anything a
// generic mapper can produce), else the status-mapped taxonomy line.
window.whFnError = async function (err, fallback) {
  var status = 0, body = null;
  try {
    if (err && err.context) {
      if (typeof err.context.status === 'number') status = err.context.status;
      if (typeof err.context.json === 'function') {
        try { body = await err.context.clone().json(); }
        catch (_) { body = null; }   /* empty-catch-allow: a non-JSON body is normal; fall back to status */
      }
    }
  } catch (_) { /* empty-catch-allow: never let diagnostics throw over the real failure */ }

  var own = body && (body.error || body.message);
  if (typeof own === 'string' && own.trim() && !/non-2xx/i.test(own)) return own.trim();

  // No usable body: hand the STATUS to the taxonomy, since the message never carried it.
  if (status && typeof window.whAiError === 'function') {
    return window.whAiError({ message: String(status) }, fallback);
  }
  if (typeof window.whAiError === 'function') return window.whAiError(err, fallback);
  /* T45: the only sentence whFnError owns - its other three paths return the function's OWN
     message or delegate to whAiError, which is already bilingual. Reached only when there is no
     status and no body, i.e. nothing anywhere to be specific about. */
  var T = (typeof window !== 'undefined' && typeof window._t === 'function')
    ? window._t : function (en) { return en; };
  return fallback || T('Something went wrong. Please try again.', 'May naganap na mali. Subukan muli.');
};

// ── What actually left the shelf (T11, 2026-08-27) ─────────────────────────────────────────
// inventory_deduct CLAMPS rather than refuses: `v_qty := GREATEST(0, v_qty - p_qty)`. Asking for 1
// when 0 remain therefore RETURNS NORMALLY having moved nothing - measured live: return 0, a ledger
// row written with qty_change 0, shelf unchanged, no error raised. Every caller checked only
// `error`, so the loser of a last-unit race was told the save succeeded while their entry claimed a
// part the shelf never gave up.
//
// The RETURN VALUE cannot tell them apart, because it is the new quantity and both "took the last
// one" and "there were none" end at 0. The LEDGER ROW can, because it records what moved - so the
// caller passes a p_txn_id (the function has always accepted one) and reads that row back. Verified
// under RLS that a member can read their own hive's inventory_transactions row.
//
// Returns { moved, requested, short } - or null when the row cannot be read, because a failed check
// must not masquerade as "nothing was short".
window.whDeductMoved = async function (db, txnId, requested) {
  try {
    const want = Number(requested);
    if (!db || !txnId || !isFinite(want)) return null;
    /* READ THE TRUTH VIEW, NOT THE RAW TABLE (2026-08-27). This helper was added earlier today
       reading inventory_transactions directly, and validate_canonical_sources caught it on the
       board: a canonical view exists, so the raw read is drift by definition - the whole point of
       the truth views is that one shape of a row is what every consumer sees. The view carries both
       columns this needs (id, qty_change), is security_invoker=true so RLS still decides what comes
       back, and is granted to authenticated. Migrating rather than adding a canonical-allow, since
       there is no reason here that an exemption would have to state. */
    const { data, error } = await db.from('v_inventory_transactions_truth')
      .select('qty_change').eq('id', txnId).maybeSingle();
    if (error || !data) return null;
    var moved = Math.abs(Number(data.qty_change) || 0);
    return { moved: moved, requested: want, short: moved < want };
  } catch (_) {
    return null;   /* empty-catch-allow: the deduct itself already landed; this only explains it */
  }
};

// The sentence for a short move, in one place so all three call sites say it the same way.
window.whShortMoveNotice = function (partName, moved, requested) {
  return 'Only ' + moved + ' of ' + requested + ' ' + (partName || 'that part')
       + ' was on the shelf, so the rest was NOT issued. Someone took it first; check Inventory '
       + 'before promising it.';
};

// ── Speech-recognition errors (T176, 2026-08-27) ───────────────────────────────────────────
// The Web Speech API reports failures as bare codes, and three call sites pasted the code straight
// into a toast: 'Voice error: network', 'Voice error: audio-capture', 'Mic error: aborted'. Those
// are strings for a developer. A worker on a plant floor reads "Voice error: network" and has no
// idea whether the plant wifi died, the mic is broken, or their words were lost.
//
// The vocabulary is small, closed and specified, so it maps once here rather than three times badly.
// Every branch answers the same three questions the taxonomy asks of any failure: what happened,
// what happened to the WORK, and what to do next. The work answer is the same on every branch and
// is the one worth saying out loud - dictation failing never discards what is already typed, and a
// person who is not told that will assume the worst and start over.
window.whVoiceError = function (code, fallback) {
  var c = String(code == null ? '' : (code.error || code)).toLowerCase();
  /* T45: bilingual for the same reason whAiError is - and more sharply here, because the mic is
     exactly where a Filipino-speaking worker is. _t falls back to EN when a phrase has no FIL. */
  var T = (typeof window !== 'undefined' && typeof window._t === 'function')
    ? window._t : function (en) { return en; };
  if (c === 'not-allowed' || c === 'service-not-allowed') {
    return T('This browser is blocking the microphone. Allow it from the icon in the address bar, '
           + 'or just type instead. Nothing you have typed was lost.',
             'Hinaharangan ng browser ang mikropono. Payagan ito mula sa icon sa address bar, o '
           + 'mag-type na lang. Walang nawala sa na-type mo.');
  }
  if (c === 'audio-capture') {
    return T('No microphone was found. Plug one in or type instead. Nothing you have typed was lost.',
             'Walang nakitang mikropono. Magsaksak ng isa o mag-type na lang. Walang nawala sa na-type mo.');
  }
  if (c === 'network') {
    return T('Dictation needs the internet and could not reach it. Type instead. Nothing you have '
           + 'typed was lost.',
             'Kailangan ng internet ang dictation at hindi ito maabot. Mag-type na lang. Walang '
           + 'nawala sa na-type mo.');
  }
  if (c === 'language-not-supported') {
    return T('Dictation does not support this language on this device. Type instead. Nothing you '
           + 'have typed was lost.',
             'Hindi supportado ang wikang ito para sa dictation sa device na ito. Mag-type na lang. '
           + 'Walang nawala sa na-type mo.');
  }
  if (c === 'aborted') {
    return T('Dictation stopped before it heard anything. Nothing you have typed was lost.',
             'Huminto ang dictation bago pa ito nakarinig. Walang nawala sa na-type mo.');
  }
  return fallback || T('Dictation could not run. Type instead. Nothing you have typed was lost.',
                       'Hindi tumakbo ang dictation. Mag-type na lang. Walang nawala sa na-type mo.');
};

// ── AI quota notice (T89, 2026-08-26) ──────────────────────────────────────────────────────
// _shared/rate-limit.ts returns `remaining` on EVERY allowed call, so the platform always knows
// how close a hive is to its hourly cap. Nothing consumed it: there is no threshold anywhere, and
// the only signal a worker ever got was the 429 AFTER the wall - mid-task, with the work half
// done. asset-hub was the one surface that rendered the number at all, and it rendered it flat
// ("12 AI calls remaining this hour"), which reads the same at 12 as at 1.
//
// A count is not a warning. This turns the number the server already sends into one, so a
// supervisor can finish the question they are on rather than discovering the limit by hitting it.
// Reset time is named because "wait" without "how long" is not a remedy.
window.whQuotaNotice = function (remaining) {
  // null/undefined means the server did not tell us, and Number(null) is 0 - so without this the
  // helper announced "No AI calls left this hour" to someone whose quota was simply UNKNOWN.
  // An absent reading is not a reading of zero; say nothing rather than something alarming and false.
  if (remaining === null || remaining === undefined || remaining === '') {
    return { text: '', level: 'none' };
  }
  var n = Number(remaining);
  if (!isFinite(n) || n < 0) return { text: '', level: 'none' };
  if (n === 0) {
    return { text: 'No AI calls left this hour. The limit resets on the hour.', level: 'out' };
  }
  if (n <= 5) {
    return {
      text: 'Only ' + n + ' AI call' + (n === 1 ? '' : 's') + ' left this hour. The limit resets on the hour.',
      level: 'low',
    };
  }
  return { text: n + ' AI calls remaining this hour', level: 'ok' };
};

// ── Native-app feel fallback (rubric class T · React-Native benchmark, 2026-07-18) ──────────
// tokens.css carries the native-feel baseline (touch-action:manipulation + overscroll-behavior:
// contain) for the ~35 pages that link it; this guard injects the SAME baseline ONLY where
// tokens.css did NOT reach, so the WHOLE family gets the native feel with no duplication. These
// are BEHAVIOURAL props (no FOUC). Cited: external-css-touch-action, external-css-overscroll-behavior.
(function whNativeFeelFallback() {
  function apply() {
    try {
      var ta = (getComputedStyle(document.documentElement).touchAction || '') + ' ' + (getComputedStyle(document.body).touchAction || '');
      if (/manipulation|none|pan/.test(ta)) return;   // tokens.css already applied it
      var s = document.createElement('style');
      s.setAttribute('data-wh-native-feel', '1');
      s.textContent = 'html,body{touch-action:manipulation;overscroll-behavior:contain}' +
        '#wh-hub-tiles,.wh-fb-body,.calendar-wrap,.sidebar-items,.table-scroll,.chat-messages,.modal,.modal-body,.sheet,[role="dialog"],[class*="scroll"],[class*="overflow-y-auto"],[class*="overflow-auto"]{overscroll-behavior:contain}';
      (document.head || document.documentElement).appendChild(s);
    } catch (_) { /* empty-catch-allow: best-effort native-feel baseline */ }
  }
  if (document.body) apply(); else document.addEventListener('DOMContentLoaded', apply);
})();


// ============================================================================
// whNumericPaste — T123 (2026-08-26): a pasted quantity must not vanish.
//
// MEASURED, not assumed. Pasting into <input type="number"> on this platform:
//   "1,500"   -> ""      validity: VALID
//   " 12 "    -> ""      validity: VALID
//   "12 pcs"  -> ""      validity: VALID
// That is the HTML value-sanitization algorithm doing exactly what it is specified to do: a value
// that is not a valid floating-point number becomes the empty string, and an empty non-required
// number input is VALID. So the three most common real-world pastes - a thousands separator from a
// supplier email, stray spaces from a table cell, a unit copied along with the figure - silently
// EMPTY the field and then report themselves fine. A worker who pastes "1,500" and taps Save is
// submitting nothing, with no error to read and often no reason to look back at the field.
//
// This intercepts the paste, cleans what a person actually copies, and inserts the number:
//   thousands separators between digits are removed (PH uses comma-thousands, period-decimal),
//   NBSP/thin/regular spaces are stripped, a trailing unit word is dropped, one leading minus and
//   one decimal point survive.
//
// ★AND WHEN IT CANNOT BE CLEANED, IT SAYS SO. Falling back to the browser's silent empty would
// re-create the defect for the cases the cleaner does not cover. Anything unparseable leaves the
// field untouched and announces once - a refusal a person can read beats a blank they cannot see.
function whCleanNumericPaste(raw) {
  var s = String(raw == null ? '' : raw);
  s = s.replace(/[   \s]/g, '');        // NBSP, figure space, narrow NBSP, spaces
  // Thousands separators, BETWEEN digits only. Written with a capture group rather than a
  // LOOKBEHIND on purpose: lookbehind is ES2018, and a browser that lacks it throws a SyntaxError
  // while PARSING this file - which would take ALL of utils.js down, on every page, for those
  // users. A regex feature that can break the whole platform on one browser is not worth the two
  // characters it saves. (T119's browser-floor question, answered here instead of discovered there.)
  s = s.replace(/(\d),(?=\d{3})/g, '$1');
  var m = s.match(/-?\d*\.?\d+/);                       // the first real number in what was pasted
  if (!m) return null;
  var n = Number(m[0]);
  return Number.isFinite(n) ? m[0] : null;
}
if (typeof window !== 'undefined') window.whCleanNumericPaste = whCleanNumericPaste;

(function whNumericPasteInit() {
  if (typeof document === 'undefined') return;
  function onPaste(e) {
    var el = e.target;
    if (!el || el.tagName !== 'INPUT') return;
    if ((el.getAttribute('type') || '').toLowerCase() !== 'number') return;
    var dt = e.clipboardData || (typeof window !== 'undefined' && window.clipboardData);
    if (!dt) return;
    var raw = '';
    try { raw = dt.getData('text') || ''; } catch (_) { return; }
    if (!raw) return;
    // already clean: let the browser do its normal thing
    if (/^-?\d*\.?\d+$/.test(raw.trim()) && raw === raw.trim()) return;
    e.preventDefault();
    var cleaned = whCleanNumericPaste(raw);
    if (cleaned === null) {
      if (typeof showToast === 'function') {
        showToast('That does not look like a number: "' + String(raw).slice(0, 24) + '". The box was left as it was.', 'error');
      }
      return;
    }
    el.value = cleaned;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }
  // ONE delegated listener on the document, capturing, so it reaches inputs rendered later by any
  // page's own JS - the alternative (binding each input at load) misses every dynamically drawn
  // form, which on this platform is most of them.
  document.addEventListener('paste', onPaste, true);
})();


// ============================================================================
// i18n LOCALE FLOOR (rubric N1) -- the shared half of the design system
// ============================================================================
// NN/g: a design system is "a style guide PLUS a component library ... reducing
// REDUNDANCY and creating a SHARED LANGUAGE across pages". We had the style guide
// (tokens.css) and NOT the component library -- which is measurably why 29 of 32 family
// pages fail N1. The i18n ENGINE was pasted inline FOUR times (analytics / hive / index /
// analytics-report) while the SHARED chrome stayed English-only: nav-hub.js reaches 31
// pages, this file 35, and neither could translate a single word.
//
// Hoisting the locale STATE + translator here gives every utils.js page the mechanics for
// free -- the same lever this file already uses for the focus ring ("without editing 40+
// pages individually"). Concretely: a worker who picks Filipino on the home dashboard now
// keeps it across the whole platform's chrome instead of it snapping back to English on
// the next page.
//
// DEFENSIVE BY DESIGN -- this FILLS A GAP, it never clobbers. A page with its own engine
// (analytics/hive/index) defines _t/WH_LANG later in the body and still wins; both read the
// same `wh_lang` key, so they agree. Pages with no engine get a working pass-through
// instead of a ReferenceError.
// [external-design-system-adoption-scale-consistency-across-, external-atomic-design-...]
(function whLocaleFloor() {
  try {
    if (typeof window.WH_LANG === 'undefined') {
      window.WH_LANG = (localStorage.getItem('wh_lang') === 'fil') ? 'fil' : 'en';
    }
  } catch (_) { /* empty-catch-allow: locale persistence is best-effort (private mode) */
    if (typeof window.WH_LANG === 'undefined') window.WH_LANG = 'en';
  }
  if (typeof window._t !== 'function') {
    // _t(en, fil) -- the platform's translator signature. Falls back to EN when a phrase
    // has no FIL yet, so a partial dictionary can never blank a label.
    window._t = function _t(en, fil) {
      return (window.WH_LANG === 'fil' && fil) ? fil : en;
    };
  }
  // <html lang> must follow the locale or a screen reader pronounces Filipino with English
  // phonemes (WCAG 3.1.1). Pages with their own engine set this too; same value, no fight.
  try {
    document.documentElement.lang = (window.WH_LANG === 'fil') ? 'fil' : 'en';
  } catch (_) { /* empty-catch-allow: documentElement always exists; guard is belt-and-braces */ }
})();


// ─────────────────────────────────────────────
// a11y floor — global keyboard focus ring (WCAG 2.4.11 / SC 2.4.7 focus-visible)
// ─────────────────────────────────────────────
// utils.js loads on every page before page scripts, so injecting one :focus-visible
// rule here gives every interactive control a visible keyboard focus indicator
// platform-wide (clears the Arc-K deterministic focus-visible floor without editing
// 40+ pages individually). Scoped to :focus-visible so mouse clicks show no outline;
// !important defeats any stray `outline:none`. Idempotent (id-guarded).
(function whInjectFocusRing() {
  try {
    if (typeof document === 'undefined' || document.getElementById('wh-a11y-focus')) return;
    var css = 'a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,' +
      'textarea:focus-visible,summary:focus-visible,[tabindex]:focus-visible,[role="button"]:focus-visible,' +
      '[role="link"]:focus-visible,[role="tab"]:focus-visible,[contenteditable="true"]:focus-visible{' +
      'outline:2px solid var(--wh-orange, #F7A21B) !important;outline-offset:2px !important;border-radius:3px;}';
    var st = document.createElement('style');
    st.id = 'wh-a11y-focus';
    st.textContent = css;
    (document.head || document.documentElement).appendChild(st);
  } catch (_) { /* empty-catch-allow: a11y focus-ring injection is best-effort styling */ }
})();

// ─────────────────────────────────────────────
// Q2 · CLOSED OVERLAYS MUST LEAVE THE TAB ORDER (WCAG 2.2 SC 2.4.11) — injected once, platform-wide
// ─────────────────────────────────────────────
// A modal/sheet hidden with `opacity:0; pointer-events:none` is invisible to sighted+mouse users but
// its controls STAY FOCUSABLE (visibility stays `visible`), so a keyboard user tabs into an invisible
// dialog. axe cannot see this (it treats only display:none / visibility:hidden / aria-hidden as hidden).
// Centralized HERE rather than per page: skillmatrix.html does NOT load tokens.css, so the shared-CSS
// route can't reach it — same reason the focus-ring above is injected. `:not(.open)` gives specificity
// (0,2,0), so this beats a page's own `.sheet-overlay{opacity:0}` (0,1,0) regardless of source order,
// and the `.open` rule restores BOTH visibility and the transition-delay (omitting that reset is what
// made the nav panel un-openable when this fix was first written per-page). Idempotent (id-guarded).
(function whInjectClosedOverlayFocusGuard() {
  try {
    if (typeof document === 'undefined' || document.getElementById('wh-a11y-overlay-focus')) return;
    var css =
      '.sheet-overlay:not(.open),.modal-overlay:not(.open){visibility:hidden;' +
      'transition:opacity .25s,visibility 0s linear .25s;}' +
      '.sheet-overlay.open,.modal-overlay.open{visibility:visible;transition-delay:0s;}';
    var st = document.createElement('style');
    st.id = 'wh-a11y-overlay-focus';
    st.textContent = css;
    (document.head || document.documentElement).appendChild(st);
  } catch (_) { /* empty-catch-allow: overlay focus-guard injection is best-effort styling */ }
})();

// ─────────────────────────────────────────────
// JA3 · BACK DISMISSES AN OPEN OVERLAY (history-aware modals) — injected once, platform-wide
// ─────────────────────────────────────────────
// Found by the LIVE buy/RFQ journey walk (2026-07-23, §12 flywheel loop 8): opening a marketplace
// listing detail did NOT change the URL, and pressing BACK — the universal "close this" gesture,
// and the ONLY one on Android hardware/gesture nav — threw the buyer clean OUT of the marketplace
// to the previous page, losing both the listing and their browse position. Platform-wide grep
// confirmed the cause: ZERO history.pushState and ZERO popstate handlers anywhere, so no overlay
// on any page was ever Back-dismissible. (Pages DO use replaceState for deep-link URL sync — a
// different thing; replaceState adds no history entry, so Back still leaves the page.)
//
// FIX, centralized here rather than per page (same reasoning as the Q2 overlay guard above, and it
// reuses the SAME two shared overlay classes): when any .sheet-overlay/.modal-overlay gains .open we
// push one history entry; Back then pops that entry and we CLOSE the overlay instead of navigating.
// If the page closes it by its own means (X / Esc / backdrop) we consume our entry so history stays
// balanced and a second Back doesn't dead-click. Defensive throughout; a failure degrades to the old
// behaviour, never to a navigation loop.
(function whOverlayBackDismiss() {
  try {
    if (typeof document === 'undefined' || typeof history === 'undefined' || !history.pushState) return;
    if (window.__whOverlayBack) return;                      // idempotent
    window.__whOverlayBack = true;
    var SEL_OPEN = '.sheet-overlay.open, .modal-overlay.open';
    var pushed = false;
    var anyOpen = function () { try { return document.querySelector(SEL_OPEN); } catch (_) { return null; } };
    var sync = function () {
      var isOpen = !!anyOpen();
      if (isOpen && !pushed) {
        pushed = true;
        try { history.pushState({ whOverlay: 1 }, ''); } catch (_) { pushed = false; }
      } else if (!isOpen && pushed) {
        // closed by the page (X / Esc / backdrop) -> consume the entry we added
        pushed = false;
        try { if (history.state && history.state.whOverlay) history.back(); } catch (_) { /* empty-catch-allow */ }
      }
    };
    var mo = new MutationObserver(sync);
    mo.observe(document.documentElement, { subtree: true, attributes: true, attributeFilter: ['class'] });
    window.addEventListener('popstate', function () {
      var el = anyOpen();
      if (!el) return;                                       // a real navigation, not our overlay entry
      pushed = false;
      try { el.classList.remove('open'); } catch (_) { /* empty-catch-allow */ }
    });
  } catch (_) { /* empty-catch-allow: back-dismiss is progressive enhancement */ }
})();

// ─────────────────────────────────────────────
// JA2 · RETURN-PROMISE KEPT — a gate that PROMISES a return must carry the return target
// ─────────────────────────────────────────────
// Found by the live first-run journey walk (2026-07-23, §12 flywheel loop 2). The shared
// #hive-gate interstitial tells a brand-new user: "You'll be brought back here once you're
// set up." — but its CTA was a BARE `hive.html` with no return target, and hive.html reads
// no return/next/from param and never checks document.referrer. The promise was therefore
// STRUCTURALLY IMPOSSIBLE to keep: the user finishes hive setup and is stranded on the hive
// board, having to remember where they came from. A UI promise the journey cannot honour is
// worse than no promise. Centralize-first: ONE delegated handler here fixes every gated page
// (logbook / asset-hub / engineering-design / alert-hub / audit-log / integrations / ...)
// instead of editing each gate. Runs at DOMContentLoaded for static gates AND on click
// (capture) so a gate rendered later is still covered.
(function whWireGateReturn() {
  try {
    if (typeof document === 'undefined') return;
    var SEL = '#hive-gate a[href^="hive.html"], .hive-gate a[href^="hive.html"]';
    var stamp = function (a) {
      if (!a) return;
      var h = a.getAttribute('href') || '';
      if (/[?&]return=/.test(h)) return;                       // already carries one
      var page = (location.pathname.split('/').pop() || '');
      if (!page || page === 'hive.html') return;               // nothing to return TO
      a.setAttribute('href', h + (h.indexOf('?') > -1 ? '&' : '?') + 'return=' + encodeURIComponent(page));
    };
    var sweep = function () { try { Array.prototype.forEach.call(document.querySelectorAll(SEL), stamp); } catch (_) { /* empty-catch-allow */ } };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', sweep);
    else sweep();
    document.addEventListener('click', function (e) {
      try { stamp(e.target && e.target.closest && e.target.closest(SEL)); } catch (_) { /* empty-catch-allow */ }
    }, true);
  } catch (_) { /* empty-catch-allow: return-promise wiring is best-effort navigation polish */ }
})();

// ── Arc W · W1 — GLOBAL ELEVATION (depth lens), platform-wide ───────────────────
// The platform read flat/coplanar (R1: depth_floor=789, ~0 box-shadow across 800+
// card-like els). components.css carries the canonical elevation rules but is only
// <link>ed on 12 pages; this injection (same dual-delivery pattern as the E2 skeleton
// CSS + the focus-ring above) reaches the OTHER ~16 pages so EVERY page gets layered
// depth. Selectors are wrapped in :where() = ZERO specificity, so this is a pure
// DEFAULT: any page rule that styles a card's box-shadow (e.g. analytics' translucent
// cards, a status-glow .feed-card) ALWAYS wins regardless of DOM order — we lift only
// the currently-flat surfaces, never override intentional styling. box-shadow +
// transform are layout-neutral (no CLS / tap-target / animation-budget cost).
// Idempotent (id-guarded); shadow tokens defined here too since non-components.css
// pages don't get its :root (tokens.css only supplies the navy ladder).
(function whInjectElevation() {
  try {
    if (typeof document === 'undefined' || document.getElementById('wh-elevation')) return;
    var css =
      ':root{--wh-shadow-1:0 1px 2px rgba(0,0,0,0.20),0 2px 6px rgba(0,0,0,0.16);' +
      '--wh-shadow-3:0 12px 32px rgba(0,0,0,0.34),0 4px 12px rgba(0,0,0,0.22);}' +
      // card/panel/tile/widget roles -> soft float (matches the Arc W probe's card roles)
      ':where(.simple-card,.action-card,.card,[class*="-card"],.panel,[class*="-panel"],' +
      '.tile,[class*="-tile"],.widget,[class*="-widget"],.wh-card){box-shadow:var(--wh-shadow-1);}' +
      // overlays/modals/sheets float highest
      ':where(.modal,.modal-content,.modal-overlay,.sheet-overlay,[role="dialog"]){box-shadow:var(--wh-shadow-3);}' +
      // surface-tint lift for the shared KPI card where the page hasn't themed it itself
      ':where(.simple-card){background:var(--wh-navy-mid);}' +
      // M/S press-feedback for gloved field workers (mobile-maestro rule #5)
      ':where(button,.btn,a.btn,[role="button"]):active{transform:scale(0.98);}' +
      // H lens (W3) — ONE hero KPI tile per dashboard dominates. NOT :where: a `hero` modifier the
      // page author opted into MUST win over the page's `.sc-hero` (0,1,0); 0,2,1 beats it.
      '.simple-card.hero .sc-hero{font-size:clamp(2rem,5.5vw,2.4rem);line-height:1.1;}';
    var st = document.createElement('style');
    st.id = 'wh-elevation';
    st.textContent = css;
    (document.head || document.documentElement).appendChild(st);
  } catch (_) { /* empty-catch-allow: elevation-shadow CSS injection is best-effort styling */ }
})();

// ─────────────────────────────────────────────
// Arc W · W5 — ONE icon system (inline-SVG), platform-wide emoji → SVG
// ─────────────────────────────────────────────
// Ian's call (2026-06-25): standardize the platform's icon glyphs to ONE inline-SVG system
// (the roadmap I-lens target), replacing the scattered emoji. Lucide-style 24×24 paths (MIT),
// stroke=currentColor so a mono icon inherits its text color; status dots carry their own fill.
// Exposed as window.whIcon(name,{label,cls}) for new markup, AND auto-applied: a guarded text-node
// walk swaps known emoji → <svg.wh-i>. SAFETY: runs on `load` (after page scripts have read any
// textContent during render); skips input/textarea/select/script/style/code/pre/svg/[contenteditable]
// + [data-no-iconify]; marks processed; a MutationObserver re-runs on injected subtrees (so JS-built
// lists convert too) with a guard against re-processing our own SVGs. Idempotent (id-guarded CSS).
(function whIconSystem() {
  if (typeof document === 'undefined') return;
  var NS = 'http://www.w3.org/2000/svg';
  // name -> { d: inner SVG markup, fill?: status color (filled, no stroke) }
  var ICONS = {
    check:        { d: '<path d="M20 6 9 17l-5-5"/>' },
    x:            { d: '<path d="M18 6 6 18M6 6l12 12"/>' },
    warning:      { d: '<path d="m21.7 18-8-14a2 2 0 0 0-3.4 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3z"/><path d="M12 9v4"/><path d="M12 17h.01"/>' },
    star:         { d: '<path d="M11.5 2.3a.5.5 0 0 1 1 0l2.3 4.7a2 2 0 0 0 1.6 1.1l5.1.8a.5.5 0 0 1 .3.9l-3.7 3.6a2 2 0 0 0-.6 1.9l.9 5.1a.5.5 0 0 1-.8.6l-4.6-2.4a2 2 0 0 0-2 0L6.4 21a.5.5 0 0 1-.8-.6l.9-5.1a2 2 0 0 0-.6-1.9L2.2 9.8a.5.5 0 0 1 .3-.9l5.1-.8a2 2 0 0 0 1.6-1.1z"/>', sfill: 1 },
    wrench:       { d: '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>' },
    'thumbs-up':  { d: '<path d="M7 10v12"/><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88z"/>' },
    'thumbs-down':{ d: '<path d="M17 14V2"/><path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88z"/>' },
    clipboard:    { d: '<rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>' },
    bot:          { d: '<path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2M20 14h2M15 13v2M9 13v2"/>' },
    package:      { d: '<path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5M12 22V12"/>' },
    zap:          { d: '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>' },
    chart:        { d: '<path d="M3 3v16a2 2 0 0 0 2 2h16"/><rect x="7" y="13" width="3" height="5"/><rect x="12" y="9" width="3" height="9"/><rect x="17" y="5" width="3" height="13"/>' },
    sparkles:     { d: '<path d="M9.94 14.5 12 21l2.06-6.5L20 12l-5.94-2.5L12 3l-2.06 6.5L4 12z"/>' },
    file:         { d: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z"/><path d="M14 2v5h5M8 13h8M8 17h8"/>' },
    search:       { d: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>' },
    calendar:     { d: '<rect width="18" height="18" x="3" y="4" rx="2"/><path d="M8 2v4M16 2v4M3 10h18"/>' },
    gear:         { d: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>' },
    save:         { d: '<path d="M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7M7 3v4a1 1 0 0 0 1 1h7"/>' },
    eye:          { d: '<path d="M2.06 12.35a1 1 0 0 1 0-.7 10.75 10.75 0 0 1 19.88 0 1 1 0 0 1 0 .7 10.75 10.75 0 0 1-19.88 0"/><circle cx="12" cy="12" r="3"/>' },
    flame:        { d: '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.07-2.14-.71-3.9 1-5.5C9.5 5 11 6 12 6c1.5-1.5 2-3 2-3 2 2 4 4.5 4 8a6 6 0 0 1-12 0c0-1.5.5-2.5 1.5-3.5"/>' },
    pencil:       { d: '<path d="M21.17 6.83 17.17 2.83a2 2 0 0 0-2.83 0L3 14.17V21h6.83L21.17 9.66a2 2 0 0 0 0-2.83z"/>' },
    stop:         { d: '<path d="M2.59 7.91 7.9 2.6a2 2 0 0 1 1.42-.59h5.36a2 2 0 0 1 1.42.59l5.31 5.31a2 2 0 0 1 .59 1.42v5.36a2 2 0 0 1-.59 1.42l-5.31 5.31a2 2 0 0 1-1.42.59H9.32a2 2 0 0 1-1.42-.59L2.6 16.1a2 2 0 0 1-.59-1.42V9.32a2 2 0 0 1 .58-1.41z"/>' },
    lock:         { d: '<rect width="18" height="11" x="3" y="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>' },
    factory:      { d: '<path d="M12 16h.01M16 16h.01M3 19a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V8l-7 4V8l-7 4V4a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1z"/>' },
    globe:        { d: '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20M2 12h20"/>' },
    crystal:      { d: '<circle cx="12" cy="10" r="7"/><path d="M7 21h10M9 17l-1 4M15 17l1 4"/>' },
    bee:          { d: '<path d="M12 8a4 4 0 0 1 4 4v3a4 4 0 0 1-8 0v-3a4 4 0 0 1 4-4z"/><path d="M8 11h8M8 14h8M9 5 7 3M15 5l2-2"/>' },
    'arrow-down': { d: '<path d="M12 5v14M19 12l-7 7-7-7"/>' },
    'arrow-up':   { d: '<path d="M12 19V5M5 12l7-7 7 7"/>' },
    dot:          { d: '<circle cx="12" cy="12" r="9"/>', sfill: 1 },
    shield:       { d: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>' },
    target:       { d: '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>' },
    user:         { d: '<circle cx="12" cy="8" r="5"/><path d="M20 21a8 8 0 0 0-16 0"/>' },
    chat:         { d: '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22z"/>' },
    refresh:      { d: '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>' },
    mail:         { d: '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>' },
    bulb:         { d: '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/>' },
    clock:        { d: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>' },
    camera:       { d: '<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3z"/><circle cx="12" cy="13" r="3"/>' },
    trash:        { d: '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>' },
    plus:         { d: '<path d="M5 12h14M12 5v14"/>' },
    compass:      { d: '<circle cx="12" cy="12" r="10"/><path d="m16.24 7.76-2.12 6.36-6.36 2.12 2.12-6.36z"/>' },
    droplet:      { d: '<path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C8 11.1 7 13 7 15a7 7 0 0 0 7 7z"/>' },
    award:        { d: '<circle cx="12" cy="8" r="6"/><path d="M15.5 12.5 17 22l-5-3-5 3 1.5-9.5"/>' },
    megaphone:    { d: '<path d="m3 11 18-5v12L3 14v-3z"/><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/>' },
    help:         { d: '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>' },
    heart:        { d: '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.29 1.51 4.04 3 5.5l7 7Z"/>', sfill: 1 },
    bug:          { d: '<path d="m8 2 1.88 1.88M14.12 3.88 16 2M9 7.13v-1a3.003 3.003 0 1 1 6 0v1"/><path d="M12 20c-3.3 0-6-2.7-6-6v-3a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v3c0 3.3-2.7 6-6 6M12 20v-9M6.53 9C4.6 8.8 3 7.1 3 5M6 13H2M3 21c0-2.1 1.7-3.9 3.8-4M20.97 5c0 2.1-1.6 3.8-3.5 4M22 13h-4M17.2 17c2.1.1 3.8 1.9 3.8 4"/>' },
    back:         { d: '<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 5.5 5.5 5.5 5.5 0 0 1-5.5 5.5H11"/>' },
    thermometer:  { d: '<path d="M14 4v10.54a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0z"/>' },
    battery:      { d: '<rect width="16" height="10" x="2" y="7" rx="2" ry="2"/><path d="M22 11v2"/>' },
    wind:         { d: '<path d="M12.8 19.6A2 2 0 1 0 14 16H2"/><path d="M17.5 8a2.5 2.5 0 1 1 2 4H2"/><path d="M9.8 4.4A2 2 0 1 1 11 8H2"/>' },
    plug:         { d: '<path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/><path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8z"/>' },
  };
  // emoji glyph -> icon name (or {name, fill} for colored status dots).
  var MAP = {
    '✓': 'check', '✔': 'check', '✅': 'check',
    '✗': 'x', '✕': 'x', '✖': 'x', '❌': 'x', '❎': 'x',
    '⚠': 'warning', '❗': 'warning', '❕': 'warning', '⁉': 'warning',
    '⭐': 'star', '★': 'star', '☆': 'star',
    '🔧': 'wrench', '🛠': 'wrench',
    '👍': 'thumbs-up', '👎': 'thumbs-down',
    '📋': 'clipboard', '📝': 'pencil', '✏': 'pencil', '✎': 'pencil', '✒': 'pencil',
    '🤖': 'bot', '📦': 'package',
    '⚡': 'zap', '📊': 'chart', '📈': 'chart', '📉': 'chart',
    '✨': 'sparkles', '📄': 'file', '📃': 'file', '📁': 'file',
    '🔍': 'search', '🔎': 'search',
    '📅': 'calendar', '📆': 'calendar', '🗓': 'calendar',
    '⚙': 'gear', '🔧️': 'wrench',
    '💾': 'save', '👁': 'eye', '👀': 'eye',
    '🔥': 'flame', '🛑': 'stop', '🔒': 'lock', '🔓': 'lock',
    '🏭': 'factory', '🌐': 'globe', '🔮': 'crystal', '🐝': 'bee',
    '⬇': 'arrow-down', '⬆': 'arrow-up',
    '📐': 'gear', '📏': 'gear',
    // long-tail (full coverage so every page reaches emoji=0 → one icon system)
    '🛡': 'shield', '🎯': 'target', '👤': 'user', '👷': 'user', '🧑': 'user',
    '💬': 'chat', '🗣': 'chat', '🔄': 'refresh', '🔁': 'refresh', '🔃': 'refresh',
    '✉': 'mail', '📧': 'mail', '📥': 'mail', '📤': 'mail', '📢': 'megaphone',
    '💡': 'bulb', '🕐': 'clock', '🕒': 'clock', '⏰': 'clock', '⏱': 'clock',
    '📷': 'camera', '📸': 'camera', '🗑': 'trash', '➕': 'plus', '🧭': 'compass',
    '🚰': 'droplet', '💧': 'droplet', '🏆': 'award', '🥇': 'award', '🥈': 'award',
    '🥉': 'award', '🎖': 'award', '🎉': 'sparkles', '❄': 'sparkles', '🚨': 'warning',
    '⛔': 'stop', '🧠': 'bot', '🌏': 'globe', '🌍': 'globe', '🧬': 'gear',
    '🧰': 'wrench', '🔩': 'wrench', '🏗': 'factory', '📂': 'file', '📚': 'file',
    '📖': 'file', '🖨': 'file', '📎': 'file', '✍': 'pencil', '👋': 'thumbs-up',
    '💪': 'thumbs-up', '👀': 'eye',
    // engineering-design domain glyphs (HVAC / electrical disciplines) + weather
    '🌡': 'thermometer', '🔋': 'battery', '🔌': 'plug', '💨': 'wind', '🌬': 'wind',
    '🌫': 'wind', '♻': 'refresh', '🌧': 'droplet', '🌦': 'droplet', '🧊': 'sparkles',
    '🪙': 'dot', '🪣': 'droplet', '🪨': 'dot', '🌀': 'refresh', '🔆': 'bulb', '☀': 'bulb',
    '❓': 'help', '❔': 'help', '🐞': 'bug', '🐛': 'bug', '🌊': 'droplet',
    '↩': 'back', '↪': 'back', '⤴': 'back', '⤵': 'back',
    '💛': 'heart', '💚': 'heart', '💙': 'heart', '❤': 'heart', '🧡': 'heart',
    '💜': 'heart', '🤍': 'heart', '🖤': 'heart', '💗': 'heart', '💖': 'heart',
    '\u{1FAD9}': 'package', '\u{1FA99}': 'dot', '\u{1F6E2}': 'droplet', '\u{1F525}': 'flame',
    // colored status dots
    '🔴': { n: 'dot', f: '#ef4444' }, '🟡': { n: 'dot', f: '#eab308' },
    '🟢': { n: 'dot', f: '#22c55e' }, '🔵': { n: 'dot', f: '#3b82f6' },
    '🟠': { n: 'dot', f: '#f97316' }, '⚫': { n: 'dot', f: '#6b7280' }, '⚪': { n: 'dot', f: '#d1d5db' },
  };
  function svgMarkup(name, opts) {
    var ic = ICONS[name]; if (!ic) return null;
    opts = opts || {};
    var fill = opts.fill || (ic.sfill ? 'currentColor' : 'none');
    var stroke = (ic.sfill || opts.fill) ? 'none' : 'currentColor';
    var label = opts.label || name;
    return '<svg class="wh-i' + (opts.cls ? ' ' + opts.cls : '') + '" viewBox="0 0 24 24" fill="' + fill + '" stroke="' + stroke +
      '" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" role="img" aria-label="' + label + '">' + ic.d + '</svg>';
  }
  window.whIcon = function (name, opts) { return svgMarkup(name, opts) || ''; };

  // build a single regex of all mapped glyphs (+ optional VS16). Longest keys first so a
  // surrogate-pair-with-VS16 wins over the bare pair.
  var keys = Object.keys(MAP).sort(function (a, b) { return b.length - a.length; });
  var esc = function (s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); };
  var RE;
  try { RE = new RegExp('(?:' + keys.map(esc).join('|') + ')\\uFE0F?', 'gu'); }
  catch (e) { try { RE = new RegExp('(?:' + keys.map(esc).join('|') + ')\\uFE0F?', 'g'); } catch (e2) { return; } }
  var SKIP = { INPUT: 1, TEXTAREA: 1, SELECT: 1, SCRIPT: 1, STYLE: 1, CODE: 1, PRE: 1, SVG: 1, NOSCRIPT: 1 };
  function skip(el) {
    for (var n = el; n; n = n.parentElement) {
      if (!n.tagName) continue;
      if (SKIP[n.tagName.toUpperCase()]) return true;
      if (n.isContentEditable) return true;
      if (n.hasAttribute && (n.hasAttribute('data-no-iconify') || n.classList.contains('wh-i'))) return true;
    }
    return false;
  }
  function spanFor(glyph) {
    var m = MAP[glyph.replace(/️$/, '')] || MAP[glyph];
    var name = (typeof m === 'string') ? m : (m && m.n);
    var fill = (m && m.f) || null;
    var html = svgMarkup(name, { fill: fill, label: name });
    if (!html) return null;
    var span = document.createElement('span');
    span.className = 'wh-i-wrap'; span.setAttribute('aria-hidden', 'false');
    span.innerHTML = html;
    return span.firstChild;
  }
  function walk(root) {
    if (!root || skip(root.nodeType === 1 ? root : root.parentElement || document.body)) return;
    var tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: function (t) {
        if (!t.nodeValue || !RE.test(t.nodeValue)) return NodeFilter.FILTER_REJECT;
        RE.lastIndex = 0;
        return skip(t.parentElement) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
      }
    });
    var hits = [], t;
    while ((t = tw.nextNode())) hits.push(t);
    for (var i = 0; i < hits.length; i++) {
      var node = hits[i], text = node.nodeValue, frag = document.createDocumentFragment(), last = 0, m2; RE.lastIndex = 0;
      while ((m2 = RE.exec(text))) {
        if (m2.index > last) frag.appendChild(document.createTextNode(text.slice(last, m2.index)));
        var svg = spanFor(m2[0]);
        if (svg) frag.appendChild(svg); else frag.appendChild(document.createTextNode(m2[0]));
        last = m2.index + m2[0].length;
      }
      if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
      if (node.parentNode) node.parentNode.replaceChild(frag, node);
    }
  }
  function run() { try { walk(document.body); } catch (e) { /* empty-catch-allow: best-effort icon injection; a walk failure must never break the page */ } }
  // convert JS-injected subtrees (lists/cards built after load), guarded against our own SVGs.
  var mo = null;
  try {
    mo = new MutationObserver(function (muts) {
      for (var i = 0; i < muts.length; i++) {
        var added = muts[i].addedNodes;
        for (var j = 0; j < added.length; j++) {
          var nd = added[j];
          if (nd.nodeType === 1 && !(nd.classList && nd.classList.contains('wh-i')) && nd.tagName !== 'svg') walk(nd);
          else if (nd.nodeType === 3) walk(nd.parentElement || document.body);
        }
      }
    });
  } catch (e) { /* empty-catch-allow: MutationObserver is an optional UI enhancement */ }
  function start() {
    // Arc W · W5 REVERSED (2026-07-19, Ian: "I changed my mind, I prefer the emojis now").
    // The emoji→SVG auto-swap is DISABLED so the platform's ~430 authored emoji render AS
    // emoji (emoji-first, the colorful voice Ian prefers). window.whIcon() is retained for
    // any programmatic caller; the text-node walker + MutationObserver no longer run.
    // To restore the mono-SVG system, delete this early return.
    return;
    setTimeout(run, 0);                                   // initial pass once the static DOM is parsed
    if (mo) try { mo.observe(document.body, { childList: true, subtree: true }); } catch (e) { /* empty-catch-allow: observe is best-effort UI enhancement */ }
  }
  // run on DOMContentLoaded (+setTimeout so it follows page-init handlers that read textContent),
  // NOT `load`-`load` waits on all images and can land after first interaction / a probe window.
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
  // sizing/baseline CSS for inline icons (id-guarded).
  if (!document.getElementById('wh-icon-css')) {
    var st = document.createElement('style'); st.id = 'wh-icon-css';
    st.textContent = '.wh-i{display:inline-block;width:1em;height:1em;vertical-align:-0.125em;flex:none}';
    (document.head || document.documentElement).appendChild(st);
  }
})();

// ─────────────────────────────────────────────
// getDb() — shared Supabase client singleton
// ─────────────────────────────────────────────
// Calling `supabase.createClient()` more than once per page (or once per
// IIFE) triggers the "Multiple GoTrueClient instances detected" warning
// in the Supabase JS SDK. The clients race on the same localStorage auth
// key and may produce undefined behavior under concurrent reads.
//
// The fix: every script that needs a Supabase client should call
// `window.getDb(url, key)` instead. The first call creates the client;
// subsequent calls return the same instance for the page's lifetime.
//
// Validator: validate_supabase_singleton.py flags any HTML page with >1
// inline `supabase.createClient(...)` call.
/* A DEAD SESSION IS THE ONE READ FAILURE A SILENT SWALLOW MUST NOT EAT, and it was being eaten
 * platform-wide. Injecting a 401 into each page's reads and reading what the page then TELLS a person
 * failed on 12 of 12 pages measured over a real denominator (2-16 reads intercepted each, 0 vacuous):
 * 8 said NOTHING at all, 2 said "failed" without naming the session, 2 named the session without
 * saying anything failed, and `saysNothingSent` was false on ALL TWELVE - not one page told the reader
 * whether their work survived.
 * THE CAUSE IS NOT A MISSING MESSAGE. whReadError (below, ~:1599) already says both halves in one
 * string, and _WH_PG_DENIAL plus the 401-vs-403 note beside it are careful. The cause is 118 annotated
 * `catch (_) { empty-catch-allow: best-effort silent swallow }` blocks across 11 pages, against
 * exactly ONE page that calls whReadError - public-feed, which is also the only page with ZERO silent
 * swallows. That inverse correlation is the whole diagnosis: one architectural habit, applied 118
 * times, not twelve oversights.
 * SO THE FIX GOES WHERE THE READS ALREADY PASS, not into 118 catch blocks. Every client on this
 * platform routes through getDb() - there is a registered gate asserting exactly that - and
 * _timeoutFetch below already wraps every PostgREST/Auth/Storage request, its own comment noting that
 * "one install here covers all db.from()/db.rpc()/db.auth/db.storage calls platform-wide, so no page
 * reinvents it." A 401/403 seen there is noted ONCE, centrally, and surfaced through the existing
 * banner machinery. Per-page catches stay exactly as they are: a tile that cannot compute should still
 * fail quietly, but the reader is now told the SESSION is why.
 * 401 AND 403 ARE KEPT DISTINCT, because answering both with "sign in again" sends half of them to fix
 * the one thing that is not broken - the rule this file already states below, and which hive currently
 * breaks in the other direction by answering a 500 with session language. */
/* ONE RENDERER FOR ALL THREE NOTICES — session, permission, connection. It was inline in
 * _whNoteAuthFailure until a third caller needed it, and a third copy of a pinned-box style is how two of
 * them drift apart on padding or z-index and nobody notices until they overlap on a real screen.
 * EACH NOTICE OWNS A DIFFERENT `bottom`, deliberately: they are viewport-pinned to the same corner, so
 * two boxes at an identical offset would cover each other exactly and the top one would read as the only
 * message. 88px session · 160px permission · 232px connection.
 * SELF-EXPIRY IS NOT OPTIONAL, and omitting it once broke three unrelated measurements: a pinned notice
 * makes a transient failure look permanent to a person, and it contaminated a later probe that read a
 * stale "Your session expired" and scored four innocent pages as blaming the session. */
function _whShowNotice(id, msg, bottomPx) {
  var el = document.getElementById(id);
  if (!el) {
    el = document.createElement('div');
    el.id = id;
    el.setAttribute('role', 'status');
    el.setAttribute('aria-live', 'polite');
    el.style.cssText = 'position:fixed;left:8px;right:8px;bottom:calc(' + bottomPx
      + ' + env(safe-area-inset-bottom,0px));'
      + 'z-index:2147483000;padding:12px 14px;border-radius:12px;font-size:13px;line-height:1.45;'
      + 'background:rgba(60,20,24,0.97);color:#FDC9C9;border:1px solid rgba(253,201,201,0.35);'
      + 'box-shadow:0 8px 28px rgba(0,0,0,0.45)';
    (document.body || document.documentElement).appendChild(el);
  }
  el.textContent = msg;
  var key = '_whNoticeTimer_' + id;
  if (window[key]) clearTimeout(window[key]);
  window[key] = setTimeout(function () {
    var n = document.getElementById(id);
    if (n && n.parentNode) n.parentNode.removeChild(n);
  }, 30000);
}

var _WH_AUTH_NOTED = 0;
/* A 403 IS ALSO A READ FAILURE A SILENT SWALLOW MUST NOT EAT, and this function used to drop it on the
 * floor one line in. The early `if (res.status !== 401) return;` was RIGHT about the diagnosis — a 403
 * under RLS is a permission answer to a live session, so it must never raise session language — and then
 * wrong about the consequence: it said nothing at all instead of saying the other true thing.
 * MEASURED 2026-08-13 (tools/prove_why_refused.mjs, every REST read answered 403 + 42501, 8-42 reads
 * intercepted per page, injection hit-counted so a no-op cannot be graded): of 16 pages, 13 said NOTHING,
 * 2 showed only a generic error, 1 passed. On logbook "516 entries · 30 machines · 6 open" became
 * "— entries — machines — open" with the body text IDENTICAL TO THE CHARACTER, 1107 before and after.
 * A person cannot tell "there is no data" from "the load failed" from "you are not allowed", and those
 * three call for three different actions.
 * THE CAUSE, AGAIN, IS NOT A MISSING MESSAGE. whReadError (~:1675) has said the right sentence all along;
 * it is called by 2 sites in community and ZERO on the other 16 pages — and community is the one page
 * that passed. That correlation is the whole diagnosis, and it is the same one recorded above for 401.
 * So the fix goes in the same place, for the same reason: one install at the transport, not 118 catches.
 *
 * THE TWO NOTICES ARE NOT INTERCHANGEABLE, and this is the subtle half. They have DIFFERENT TRUTH
 * CONDITIONS, so they cannot share a clear path:
 *   · a SESSION notice is FALSIFIED by the next successful read — the session is demonstrably alive, so
 *     it is cleared on `res.ok` (that is what _whClearAuthNotice is for, and it is correct).
 *   · a PERMISSION notice is NOT. Succeeding at table A says nothing whatever about being refused table
 *     B; the refusal stays true for this page load.
 * Had the 403 reused the session element, a real page — one refused read among twenty good ones — would
 * raise the notice and have it wiped by the very next OK response, so the person would see nothing, while
 * an oracle that refuses EVERY read still reported PASS. That is a false green manufactured by the fix
 * itself, which is why the permission notice gets its own id and is left out of the OK-clear.
 * It still self-expires after 30s, because a notice pinned forever contaminated four unrelated
 * measurements once already (see the note below). */
function _whNoteAuthFailure(res) {
  /* ★ THE PERMISSION THROTTLE LIVES ON `window`, AND THIS COMMENT LIVES INSIDE THIS FUNCTION, BOTH
   * DELIBERATELY — do not "tidy" either one out to the top level beside _WH_AUTH_NOTED. The bank's R4b
   * rail digests each function separately, so a shared-library edit expires only the claims resting on
   * the function it touched; everything OUTSIDE a function is digested under ONE key whose NAME embeds
   * that digest ("utils.js::top:917d57bf7457a408"). A top-level change therefore does not merely change
   * a value — it makes the recorded key VANISH, expiring every row that recorded any top-level digest
   * for this file, however narrowly that row scoped its functions.
   * Measured twice here, 2026-08-13. Adding `var _WH_ACCESS_NOTED = 0` put `utils.js::top:...` in the
   * differing-keys list for logbook's rows. Moving the counter onto `window` did NOT clear it — because
   * the explanatory COMMENT was still outside the function, and the top-level digest covers comments as
   * well as code. So on this file, a purely documentary edit outside a function is as expensive as a
   * code change: it expires every row anchored to utils.js. Prose about a function belongs inside it.
   * (_whAuthNoticeTimer was already a window property for the same blast-radius reason.) */
  if (!res || (res.status !== 401 && res.status !== 403)) return;
  var dead = res.status === 401;
  var now = Date.now();
  // one notice per burst, not one per parallel read — throttled per KIND, so a permission refusal is
  // not swallowed by a session notice 8s earlier, nor the reverse.
  if (dead) {
    if (now - _WH_AUTH_NOTED < 8000) return;
    _WH_AUTH_NOTED = now;
  } else {
    if (now - (window._whAccessNoted || 0) < 8000) return;
    window._whAccessNoted = now;
  }
  try {
    // The permission wording mirrors whReadError's 403 branch verbatim in voice — "your session is fine"
    // is the half that stops someone re-authenticating to fix a thing authentication cannot fix.
    var msg = dead
      ? 'Your session expired, so this page could not be loaded, and nothing you did was saved.'
        + ' Sign in again to continue.'
      : 'Some of this page could not be shown: your account does not have access to it. Your session is'
        + ' fine. Ask a supervisor if you need it.';
    var noticeId = dead ? 'wh-auth-expired-notice' : 'wh-access-denied-notice';
    // A SESSION notice may ride a transient toast; a PERMISSION notice may not. The refusal is a standing
    // fact about this page load, not a momentary event — a toast that fades leaves the person looking at
    // the same unexplained dashes, which is the whole defect. So the permission branch always takes the
    // persistent region below.
    // (Measured 2026-08-13: NEITHER whToast NOR whBanner is defined anywhere on this platform, so both
    // lines are inert today and the region called a "last resort" is in fact the only resort. They are
    // kept as forward hooks — but the `dead &&` guard means a toast added later cannot silently turn a
    // standing refusal back into a 3-second flash.)
    if (dead && typeof window.whToast === 'function') { window.whToast(msg, 'error'); return; }
    if (dead && typeof window.whBanner === 'function') { window.whBanner(msg, 'error'); return; }
    _whShowNotice(noticeId, msg, dead ? '88px' : '160px');
    /* THE NOTICE MUST CLEAR ITSELF, and omitting that broke three unrelated measurements. A session
     * notice is only true until the next successful read; leaving it pinned makes a transient failure
     * look permanent to a person, and - found the hard way - it also contaminates anything that reads
     * the page afterwards. The CC failure sweep injects 401, then 500, then slow, then offline into one
     * run; this element survived the first injection and the 500/slow/offline probes then read a stale
     * "Your session expired" still on screen, scoring blamesSession=true on four pages that had said
     * nothing of the kind. I nearly filed that as a platform defect - the page was innocent and the
     * residue was mine.
     * So it is removed on the next OK response, and self-expires after 30s regardless. */
    // (expiry is owned by _whShowNotice — a second timer here would just race it)
  } catch (e) { /* empty-catch-allow: a notice that cannot render must not break the read path */ }
}
/* The third notice: the read never reached the server at all. A rejected or aborted fetch has NO status
 * to inspect, so neither the session nor the permission path above can see it — and measured on logbook,
 * the page then said nothing whatsoever, because the rejection was caught and dropped.
 * TIMEOUT AND OFFLINE ARE TOLD APART, because the honest sentence differs: a timeout may still be the
 * server thinking, while an offline read will work again by itself when the connection returns, and
 * "check your connection" is useless advice for the first and the only useful advice for the second.
 * Unlike the permission notice, this one IS falsified by the next successful read — the network is
 * demonstrably back — so it is cleared on res.ok alongside the session notice. */
function _whNoteTransportFailure(err) {
  try {
    var name = String((err && err.name) || '');
    var msg  = String((err && err.message) || '');
    var timedOut = name === 'TimeoutError' || /WH_DB_TIMEOUT|timeout/i.test(msg);
    // An abort the CALLER asked for (a cancelled in-flight request on navigation) is not a failure the
    // person needs told about; only our own timeout abort is.
    if (name === 'AbortError' && !timedOut) return;
    var now = Date.now();
    if (now - (window._whConnNoted || 0) < 8000) return;
    window._whConnNoted = now;
    var text = timedOut
      ? 'This is taking longer than expected, so part of this page could not be loaded. Your work is '
        + 'safe. Try again in a moment.'
      : 'You appear to be offline, so part of this page could not be loaded. Your work is safe, and it '
        + 'will load again once your connection is back.';
    _whShowNotice('wh-connection-notice', text, '232px');
  } catch (e) { /* empty-catch-allow: a notice that cannot render must not break the transport */ }
}

/* Clear it the moment a read succeeds again - the session is demonstrably alive, so the notice is
 * false from that instant. Called from the same transport wrapper that raises it.
 * ★ IT DELIBERATELY DOES NOT TOUCH `wh-access-denied-notice`, AND THAT ASYMMETRY IS THE POINT — do not
 * "tidy" it into symmetry. A successful read falsifies a SESSION claim ("you are signed out") because
 * the same credential just worked. It falsifies NOTHING about a PERMISSION claim: reading table A says
 * nothing about being refused table B, so the refusal is still true and must stay on screen. Clearing it
 * here would make the message vanish on every real page (one refused read among twenty good ones) while
 * an oracle that refuses EVERY read still saw it and reported PASS - a false green that looks like a fix.
 * The permission notice is bounded by its own 30s self-expiry instead. */
function _whClearAuthNotice() {
  var n = document.getElementById('wh-auth-expired-notice');
  if (n && n.parentNode) n.parentNode.removeChild(n);
  // The CONNECTION notice is cleared here too, and for the same reason the session one is: a successful
  // read proves the network came back, so the message is false from that instant. The PERMISSION notice
  // is still deliberately excluded — reading table A never falsifies being refused table B.
  var cn = document.getElementById('wh-connection-notice');
  if (cn && cn.parentNode) cn.parentNode.removeChild(cn);
  window._whConnNoted = 0;
  if (window._whAuthNoticeTimer) { clearTimeout(window._whAuthNoticeTimer); window._whAuthNoticeTimer = 0; }
  _WH_AUTH_NOTED = 0;
}

window.getDb = function(url, key) {
  if (window._whSupabaseClient) return window._whSupabaseClient;
  if (!window.supabase || typeof window.supabase.createClient !== 'function') {
    throw new Error('getDb() called before @supabase/supabase-js loaded');
  }
  // Arc S F-lens (F-002/F-008): bound EVERY PostgREST/Auth/Storage request with a
  // timeout so a dead or slow backend FAILS FAST (caller gets an error -> degraded
  // UI) instead of hanging the tab forever on an open socket. One install here
  // covers all db.from()/db.rpc()/db.auth/db.storage calls platform-wide, so no
  // page reinvents it. Generous default (45s) leaves legit slow ops (2G upload,
  // big RPC) room to finish; tune via window.WH_DB_TIMEOUT_MS. A caller that
  // supplies its own AbortSignal keeps full control (we don't double-wrap).
  const TIMEOUT_MS = window.WH_DB_TIMEOUT_MS || 45000;
  const _timeoutFetch = (input, init) => {
    // Supabase client transport-fetch wrapper (not a data fetch): transport/abort errors
    // propagate into every query's {data, error}, handled by each caller — a .catch here
    // would swallow the error the client must surface. Hence fetch-error-allow on each.
    init = init || {};
    if (init.signal) return fetch(input, init); // fetch-error-allow: transport wrapper (see above)
    const ctrl = new AbortController();
    const t = setTimeout(() => {
      try { ctrl.abort(new DOMException('WH_DB_TIMEOUT', 'TimeoutError')); }
      catch (_) { ctrl.abort(); } // older engines: abort() takes no reason
    }, TIMEOUT_MS);
    // fetch-error-allow: transport wrapper — error surfaces via the client's {data, error}
    return fetch(input, { ...init, signal: ctrl.signal })
      .then(res => { if (res && res.ok) { _whClearAuthNotice(); } else { _whNoteAuthFailure(res); } return res; })
      // A TRANSPORT failure never produces a `res`, so the .then above is SKIPPED ENTIRELY and the notice
      // machinery beside it never ran. That gap was measured 2026-08-14 by rejecting every REST read on
      // logbook: zero page errors, zero console errors, and not one word on screen — the page caught the
      // rejection and said nothing, which is the 118-empty-catches habit this file already documents.
      // The same page handles 500 and 401 correctly ("Could not load your logbook"), because those DO
      // return a response. Offline and timeout were the two failures with no status to notice.
      // THIS NOTICES AND RE-THROWS — it does not swallow. The note above forbids a .catch that eats the
      // error the client must surface, and that remains true: `throw err` keeps every caller's
      // {data, error} exactly as it was.
      .catch(err => { _whNoteTransportFailure(err); throw err; })
      .finally(() => clearTimeout(t));
  };
  window._whSupabaseClient = window.supabase.createClient(url, key, {
    global: { fetch: _timeoutFetch },
    // Finding #6 (idle/expired-session robustness, 2026-07-06): make the refresh contract
    // explicit. autoRefreshToken keeps the access token fresh; persistSession restores it on
    // reload. The gap this addresses: a tab left idle for hours (its scheduled refresh timer
    // never fired while backgrounded) would fire its first authed read on the STALE token and
    // silently 401, leaving a broken "signed-in" dashboard. The visibilitychange handler below
    // refreshes on wake, before the user's next action.
    auth: { autoRefreshToken: true, persistSession: true, detectSessionInUrl: true },
  });
  // Finding #6: proactively refresh the session when the tab returns to the foreground after
  // being hidden — covers the "woke from hours of idle" case where the background refresh timer
  // didn't run, so queries after wake use a fresh token instead of 401-ing on the expired one.
  try {
    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState === 'visible' && window._whSupabaseClient) {
        // getSession() refreshes an expired access token when a valid refresh token exists.
        window._whSupabaseClient.auth.getSession().catch(function () { /* best-effort */ });
      }
    });
  } catch (_) { /* empty-catch-allow: visibilitychange unsupported */ }
  // Arc S D-lens (D-004): expose the project URL so the connectivity widget can
  // health-ping the backend (every page reaches the backend through getDb, so this
  // is the one reliable place to publish it). Publish the anon/publishable key too:
  // /auth/v1/health 401s WITHOUT an apikey on current Supabase, which false-degraded
  // the connectivity chip to "Backend down" on a healthy backend (live prod journey,
  // 2026-07-18). The publishable key is public-by-design (already shipped in the page).
  window.WH_SUPABASE_URL = url;
  window.WH_SUPABASE_ANON_KEY = key;
  return window._whSupabaseClient;
};

// XSS escape — all 5 characters
function escHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// escJsAttr — XSS-safe for a value placed inside a JS STRING LITERAL that itself
// sits inside an HTML attribute, e.g.  onclick="fn('${escJsAttr(v)}')".
// escHtml ALONE is WRONG here: the HTML parser decodes &#39; back to ' BEFORE the
// handler compiles, so a value like  ' ),alert(1),('  breaks out of the string arg
// and runs — a stored, privilege-escalating XSS (Hive board, confirmed 2026-07-10).
// Fix = JS-escape FIRST (\ ' newlines) so the post-HTML-decode text is a valid JS
// string, THEN HTML-escape so the attribute stays well-formed and its entities
// decode back to exactly the JS-safe text. The IDEAL is event-delegation + dataset
// (no user data in code at all); use this when an inline handler must stay.
function escJsAttr(str) {
  return String(str == null ? '' : str)
    .replace(/\\/g, '\\\\')   // JS: backslash first (must precede the quote escape)
    .replace(/'/g, "\\'")      // JS: single quote → escaped quote
    .replace(/\r/g, '\\r')
    .replace(/\n/g, '\\n')
    .replace(/&/g, '&amp;')    // HTML: keep the attribute well-formed; these decode
    .replace(/</g, '&lt;')     // back to chars that are harmless inside a '…' JS string
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ─────────────────────────────────────────────
// renderSourceChip — KPI source/window chip helper (Phase 3.1)
// ─────────────────────────────────────────────
// Every dashboard card that displays a canonical metric (MTBF, risk, PM
// compliance, etc.) must show WHERE the number came from and WHAT window it
// covers, so users never silently compare a 30-day live snapshot to a 365-day
// nightly snapshot. This function is the single visual contract. Pass an
// options object; returns a `<p>` string ready for innerHTML.
//
// Standard order: freshness . source . window . notes
//   - freshness: "Live data" | "Daily snapshot at 13:00 PHT" | "Live recomputation each refresh"
//   - source:    canonical view name (rendered in <code>), e.g. "v_risk_truth"
//   - window:    "365-day failure window" | "30-day overdue threshold" etc.
//   - notes:     additional clauses (array of strings)
//
// Skill alignment: analytics-engineer ("any custom composite must be labeled"),
// architect (one visual contract per concept), KPI_ENGINE.md rule 2.
//
// E1 (2026-06-14 — user-facing jargon audit, STREAMLINE §13/§14): the `source:`
// field is kept CANONICAL (raw view/table names) because validate_source_chip_truth.py
// verifies every v_*_truth in it against a real .from() read — that lineage check is
// load-bearing. But the user must NEVER see `v_logbook_truth` on the glass. So the
// chip TRANSLATES source through WH_SOURCE_LABELS at render time: the call keeps the
// canonical name, the worker reads plain language. Keep this map current when a new
// canonical view ships (validate_user_facing_jargon.py exempts the source: arg precisely
// because it is machine-translated here; it FAILs raw view/RPC/SQL jargon everywhere else).
// ─────────────────────────────────────────────────────────────────────────────────────────────
// THE CREDITS-BACK CHIP — one implementation, every surface that shows a price
// ─────────────────────────────────────────────────────────────────────────────────────────────
// marketplace.html carried this locally, with a comment warning that "two copies of this markup
// would drift the same way again, so both sites call this" — about its own two call sites. A live
// MCP walk on 2026-08-05 found the THIRD site: marketplace-seller-profile.html renders priced
// listing cards (₱68,980.48, ₱236,110.53) and showed no chip at all, while the marketplace showed
// ₱6,898 back on that same listing. One object, two surfaces, two different answers to "what do I
// get?" — and a buyer who arrives via a seller's profile never learns the reward exists at all.
//
// So it lives here now. The knobs are passed IN rather than read from a page-local variable, because
// the loader is async and each page owns its own load; a shared cache would silently render a chip
// from another page's hive.
function whCreditsBack(price, knobs) {
  if (!knobs) return null;                       // silence beats a number we cannot stand behind
  var n = Number(price);
  if (!n || n <= 0) return null;                 // "Negotiable" has no 10% of anything
  // service_knob_pct returns a WHOLE percent (10.00 = 10%); reading it as a fraction would promise
  // ten times the price.
  var raw = Math.round(n * knobs.pct) / 100;
  return Math.max(Math.min(raw, knobs.max), knobs.min);
}

function whCreditsBackChipHtml(price, knobs, style) {
  var cb = whCreditsBack(price, knobs);
  if (!cb) return '';
  var amount = escHtml((typeof whFmtPeso === 'function') ? whFmtPeso(cb, { decimals: 2 })
                                                        : 'PHP ' + Number(cb).toFixed(2));
  var sentence = amount + ' in WorkHive Credits back when this job is done. 1 credit equals 1 ' +
                 'peso, and you spend them on your next booking. Credits are not cash and cannot ' +
                 'be withdrawn.';
  // aria-label AS WELL AS title: a title= alone is not reliably announced by a screen reader and does
  // not exist at all on touch, so the one place credits were explained was visible to desktop mouse
  // users and nobody else.
  return '<span class="cat-chip credits-back" role="note"' +
         (style ? ' style="' + style + '"' : '') +
         ' aria-label="' + sentence + '"' +
         ' title="You get ' + sentence + '">' + amount + ' credits back</span>';
}

// The knobs themselves, read from the same accessors listing_reservation_amount() reads.
// NULL max means NO CAP (mig 35, Ian's flat-10%-no-ceiling rule) — and Number(null) is 0, which once
// inverted that rule into a cap of zero and deleted the chip from every priced listing.
async function whLoadRewardKnobs(dbClient) {
  try {
    var res = await Promise.all([
      dbClient.rpc('service_knob_pct', { p_hive: null, p_key: 'reward_pct' }),
      dbClient.rpc('service_knob',     { p_hive: null, p_key: 'reward_max_per_listing' }),
      dbClient.rpc('service_knob',     { p_hive: null, p_key: 'reward_min_per_listing' })
    ]);
    var pct = res[0], max = res[1], min = res[2];
    if (pct.error || max.error || min.error) return null;
    var capRaw = max.data;
    return {
      pct: Number(pct.data),
      max: (capRaw === null || capRaw === undefined) ? Infinity : Number(capRaw),
      min: Number(min.data),
    };
  } catch (_e) { return null; }   // empty-catch-allow: no knobs means no chip, never a wrong chip
}

var WH_SOURCE_LABELS = {
  // ── THE MONEY VOCABULARY (added 2026-08-05, from a live MCP walk of platform-actions) ─────────
  // Without these the generic fallback (strip v_/_truth, underscores -> spaces) rendered the
  // provenance chip as "service credit topups" and "gcash receipts needing eyes" — on a page whose
  // own copy says "GCash top-ups awaiting verification" and "Cash enters once, as a top-up". One
  // screen, two spellings of one concept, and a proper noun in lower case. The chip is user-facing
  // prose, so it has to speak the product's vocabulary, not the schema's.
  'service_credit_topups':          'GCash top-ups',
  'v_service_credit_topups_truth':  'GCash top-ups',
  'service_credit_ledger':          'credit ledger',
  'v_service_credit_ledger_truth':  'credit ledger',
  'v_gcash_receipts_needing_eyes':  'GCash receipts awaiting review',
  'v_credit_posture':               'credit posture',
  'credit_treasury':                'credit treasury',
  'v_logbook_truth':            'logbook',
  'v_pm_scope_items_truth':     'PM schedule',
  'v_pm_compliance_truth':      'PM compliance',
  'v_inventory_items_truth':    'inventory',
  'v_risk_truth':               'risk scores',
  'v_asset_truth':              'asset records',
  'v_fmea_truth':               'failure analysis',
  'v_weibull_truth':            'reliability analysis',
  'v_maturity_truth':           'hive maturity',
  'v_knowledge_freshness_truth':'knowledge base',
  'v_ai_reports_truth':         'AI reports',
  'v_alert_truth':              'alerts',
  'v_hive_readiness_truth':     'hive readiness',
  'v_marketplace_sellers_truth':'seller ratings',
  'hive_adoption_score':        'adoption score',
  'hive_benchmarks':            'hive benchmarks',
  'network_benchmarks':         'network benchmarks',
  'hive_audit_log':             'activity log',
  'hive_retention_config':      'retention settings',
  'worker_achievements':        'achievements',
  'achievement_xp_log':         'XP history',
  'schedule_items':             'your schedule',
  'community_posts':            'community posts',
  'community_replies':          'replies',
  'community_reactions':        'reactions',
  'analytics_events':           'usage analytics',
  'marketplace_listings':       'marketplace listings',
  'marketplace_orders':         'orders',
  'marketplace_disputes':       'disputes',
  'marketplace_inquiries':      'inquiries',
  'ai_cost_log':                'AI usage',
  'pm_assets':                  'PM assets',
  'pm_scope_items':             'PM tasks',
  'pm_completions':             'PM completions',
  'inventory_items':            'inventory',
  'inventory_transactions':     'stock movements',
  'integration_configs':        'integrations',
  'external_sync':              'sync history',
  'engineering_calcs':          'saved calculations',
  'canonical_formulas':         'standard formulas',
  'canonical_standards':        'engineering standards',
  'projects':                   'projects',
  'project_items':              'project tasks',
  'shift_plans':                'shift plan',
  'skill_profiles':             'skills',
  'skill_badges':               'badges',
  'platform_health.json':       'platform health check',
  'manual':                     'your own entries',
  // Knowledge corpora — real data sources, shown to the user:
  'fault_knowledge':            'fault history',
  'skill_knowledge':            'skills',
  'pm_knowledge':               'PM knowledge',
  // Lineage-anchor tokens that validate_canonical_anchor.py requires in the chip
  // CALL (for panel→fuel traceability) but that are NOT data sources to show a
  // user — a tier label / an edge-fn name / a column / a schema registry. Kept in
  // the source: field (machine plane) and rendered to NOTHING here so the glass
  // stays plain:
  'at_risk':                    '',
  'benchmark-compute':          '',
  'canonical_agent_contracts':  '',
  'qty_on_hand':                '',
  'min_qty':                    '',
};

// Translate one source token (leading identifier of a "+"-segment) to a friendly
// label. Unknown tokens are humanized (drop v_ / _truth / .json, underscores → spaces)
// so a new table never leaks a raw name even before it's added to the map.
function _whFriendlySourceToken(tok) {
  tok = String(tok).trim();
  if (WH_SOURCE_LABELS.hasOwnProperty(tok)) return WH_SOURCE_LABELS[tok];
  return tok.replace(/^v_/, '').replace(/_truth$/, '').replace(/\.json$/, '').replace(/_/g, ' ').trim();
}

// Turn a canonical source string ("v_logbook_truth + v_risk_truth via Postgres RPCs")
// into a plain phrase ("logbook & risk scores"). Splits on "+", takes the LEADING
// identifier of each segment (ignoring trailing prose / parentheticals), translates,
// de-dupes, and joins with commas + an ampersand before the last.
function _whFriendlySource(src) {
  var segs = String(src).split('+');
  var out  = [];
  for (var i = 0; i < segs.length; i++) {
    var s = segs[i].trim();
    if (!s) continue;
    var m = s.match(/^[A-Za-z0-9_.-]+/);  // leading table/view identifier (hyphen for edge-fn anchor tokens)
    var label = _whFriendlySourceToken(m ? m[0] : s);
    if (label && out.indexOf(label) === -1) out.push(label);
  }
  if (out.length === 0) return '';
  if (out.length === 1) return out[0];
  return out.slice(0, -1).join(', ') + ' & ' + out[out.length - 1];
}

// ─────────────────────────────────────────────
// whI18nApply — ONE shared [data-i] swapper (N1)
// ─────────────────────────────────────────────
// Pages WITHOUT their own i18n engine (index/hive/analytics keep theirs) tag static
// labels with data-i and declare `window.WH_FIL_PAGE = { key: 'Filipino', … }`.
// utils.js already supplies WH_LANG + _t; this closes the loop for static markup.
// EN is the markup itself, so applying is one-way (fil) — a reload restores EN.
// WH_FIL_COMMON — the SHARED Filipino dictionary for labels that repeat on every page
// (N1 accelerator, 2026-07-16). A page tags a common control `data-i="cancel"` and it is
// translated from HERE — no per-page dict entry needed. Only genuinely page-UNIQUE labels
// go in that page's WH_FIL_PAGE. This is the centralized lever (METHOD LAW) for N1's common
// half: one edit here fixes the shared vocabulary across all pages; a page dict overrides
// per key where the local wording differs. Natural Taglish (English domain terms kept).
window.WH_FIL_COMMON = {
  cancel: 'Kanselahin', save: 'I-save', saved: 'Na-save', back: 'Bumalik', next: 'Susunod',
  more: 'Higit pa', less: 'Bawas', show: 'Ipakita', hide: 'Itago', showall: 'Ipakita Lahat',
  close: 'Isara', open: 'Buksan', search: 'Maghanap', searchteam: 'Hanapin sa Team',
  export: 'I-export', exportcsv: 'I-export sa CSV', edit: 'I-edit', 'delete': 'Burahin',
  remove: 'Alisin', add: 'Magdagdag', submit: 'Isumite', send: 'Ipadala', confirm: 'Kumpirmahin',
  refresh: 'I-refresh', filter: 'I-filter', filters: 'Mga Filter', clear: 'I-clear',
  clearform: 'I-clear ang form', clearfilters: 'I-clear ang mga filter', apply: 'Ilapat',
  done: 'Tapos', retry: 'Subukan Muli', viewall: 'Tingnan Lahat', settings: 'Mga Setting',
  help: 'Tulong', why: 'Bakit?', learnmore: 'Alamin Pa', getstarted: 'Magsimula',
  signin: 'Mag-sign In', signout: 'Mag-sign Out', myentries: 'Aking Mga Entry',
  teamfeed: 'Feed ng Team', loading: 'Naglo-load', today: 'Ngayon', thisweek: 'Ngayong Linggo',
  overdue: 'Lumipas na', duesoon: 'Malapit nang sumapit', ontrack: 'Nasa tamang landas',
  register: 'Irehistro', registerasset: 'Irehistro ang Asset', generate: 'I-generate',
  publish: 'I-publish', archive: 'I-archive', addcontact: 'Magdagdag ng Kontak',
  logwork: 'I-log ang trabaho', schedule: 'I-iskedyul', restock: 'Mag-restock',
  approve:"Aprubahan", reject:"Tanggihan", restore:"Ibalik", release:"I-release", refund:"I-refund", view:"Tingnan", showdetails: 'Ipakita ang detalye', hidedetails: 'Itago ang detalye', loadmore: 'Mag-load pa',
  viewinforum: 'Tingnan sa forum', route: 'Ruta', window: 'Window', status: 'Status',
  // Shared calendar/form vocabulary (2026-07-19): repeats across dayplanner/logbook/etc. — one entry
  // here fixes every page that tags these (was causing marked-but-untranslated FIL on dayplanner).
  day: 'Araw', week: 'Linggo', month: 'Buwan', year: 'Taon', category: 'Kategorya', notes: 'Mga Tala',
  // Shared maturity-gate headings (maturity-gate.js renders these on every gated surface).
  mg_unlocks_at: 'bubukas sa Stair', mg_hive_now: 'Ang hive mo ngayon',
};

function whI18nApply(dict) {
  if (typeof window !== 'undefined' && window.WH_LANG !== 'fil') return;
  // Page dict overrides the shared common dict per key.
  var merged = Object.assign({}, (typeof window !== 'undefined' && window.WH_FIL_COMMON) || {}, dict || {});
  if (!Object.keys(merged).length) return;
  document.querySelectorAll('[data-i]').forEach(function (el) {
    var k = el.getAttribute('data-i');
    if (merged[k] != null) el.textContent = merged[k];
  });
}
if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', function () {
    // Apply whenever FIL is active — even a page with NO page dict gets its common labels
    // translated from WH_FIL_COMMON (that is the whole point of the shared dict).
    if (window.WH_FIL_PAGE || window.WH_FIL_COMMON) whI18nApply(window.WH_FIL_PAGE || {});
  });
}

// ─────────────────────────────────────────────
// whProgressStrip — ONE shared goal-gradient strip (H1, worker-daily pages)
// ─────────────────────────────────────────────
// Goal-gradient (Laws of UX): people accelerate toward a visible goal. Worker-daily
// pages (meta[name="worker-daily"]) show TODAY's real progress — never an invented
// quota. done/total MUST come from live page data; callers skip the strip when
// total===0 (an empty bar invents a journey — the A3 nothing-to-disclose error).
// Track+fill markup + role=progressbar keep it honest to AT and the rubric lens.
function whProgressStrip(label, done, total, opts) {
  opts = opts || {};
  if (!total || total < 0) return '';
  var e = escHtml;
  var _tt = (typeof window !== 'undefined' && typeof window._t === 'function') ? window._t : function (en) { return en; };
  var k = Math.max(0, Math.min(done || 0, total));
  var pct = Math.round((k / total) * 100);
  var fillCol = pct >= 100 ? '#86EFAC' : 'linear-gradient(90deg, var(--wh-orange), var(--wh-orange-light))';
  return '<div class="wh-progress-strip" role="progressbar" aria-valuemin="0" aria-valuemax="' + total + '" aria-valuenow="' + k + '"'
    + ' aria-label="' + e(_tt(label)) + ': ' + k + ' of ' + total + '"'
    + ' style="margin:0 0 12px;padding:10px 12px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:12px;">'
    + '<div style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:6px;">'
    +   '<span style="font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:rgba(255,255,255,0.80);">' + e(_tt(label)) + '</span>'
    +   '<span style="font-size:.72rem;font-weight:800;color:var(--wh-cloud, #F4F6FA);font-variant-numeric:tabular-nums;">' + k + ' <span style="font-weight:600;color:rgba(255,255,255,0.80);">' + e(_tt('of')) + ' ' + total + '</span></span>'
    + '</div>'
    + '<div class="wh-progress-track" style="height:6px;border-radius:999px;background:rgba(255,255,255,0.08);overflow:hidden;">'
    +   '<div class="wh-progress-fill" style="width:' + pct + '%;height:100%;border-radius:999px;background:' + fillCol + ';transition:width .4s;"></div>'
    + '</div>'
    + '</div>';
}

// whAiProgress — indeterminate STAGED progress for a >10s AI/compute op (PP2, NN/g response-time
// >10s "keep attention" limit + "a spinning indicator if percent-done isn't possible"). An AI
// await is OPAQUE (no real % known), so this cycles honest stage labels on an interval so the user
// sees the op is working AND roughly what it's doing, instead of a static frozen "Generating…".
// `render(label, stepIndex, totalSteps)` lets each page paint the stage in its own UI. Returns a
// stop() to call on completion/error. Cite: external-perceived-performance-optimistic-ui-skeleton-mot.
function whAiProgress(render, stages, opts) {
  opts = opts || {};
  if (typeof render !== 'function') return function () {};
  var _stages = (Array.isArray(stages) && stages.length) ? stages : ['Working…'];
  var i = 0;
  try { render(_stages[0], 0, _stages.length); } catch (_) { /* empty-catch-allow: best-effort */ }
  var iv = null;
  if (typeof setInterval === 'function') {
    iv = setInterval(function () {
      i = Math.min(i + 1, _stages.length - 1);
      try { render(_stages[i], i, _stages.length); } catch (_) { /* empty-catch-allow: best-effort */ }
    }, opts.stepMs || 2500);
  }
  return function stop() { if (iv) { clearInterval(iv); iv = null; } };
}

function renderSourceChip(opts) {
  opts = opts || {};
  // N1 safe _t fallback: pages without an i18n layer get the EN string unchanged,
  // so this shared renderer can translate without breaking them.
  var _tt = (typeof window !== 'undefined' && typeof window._t === 'function') ? window._t : function (en) { return en; };
  var source    = opts.source    || '';
  var freshness = opts.freshness || '';
  var win       = opts.window    || '';
  var notes     = Array.isArray(opts.notes) ? opts.notes : [];
  var method    = Array.isArray(opts.method) ? opts.method : [];

  var parts = [];
  if (freshness) parts.push(escHtml(freshness));
  if (source) {
    var friendly = _whFriendlySource(source);
    if (friendly) {
      // One whole template per locale with a single slot, rather than gluing a
      // prefix onto a noun -- the possessive sits differently in Filipino (N1).
      var f = escHtml(friendly);
      parts.push(/^your\b/.test(friendly)
        ? _tt('Based on ' + f,      'Batay sa ' + f)
        : _tt('Based on your ' + f, 'Batay sa iyong ' + f));
    }
  }
  if (win) parts.push(escHtml(win));
  for (var i = 0; i < notes.length; i++) {
    if (notes[i]) parts.push(escHtml(String(notes[i])));
  }

  // Arc L · L1 CLS: padding (not margin) for the top gap — a top-margin on this <p> collapses
  // through the empty source-chip slot + the shared <main>/.page scaffold, translating the whole
  // page down ~12px at first data-render (proven on predictive.html). padding never collapses;
  // with no background the 3px gap is visually identical.
  // G1 (Nielsen #1 "visibility of system status"): this in-content provenance/freshness chip IS the
  // page's system-status region ("Live · Based on your … · updated …"). role=status + aria-live make
  // it a genuine live region so the rubric's G1 finds it on EVERY page that renders a source chip
  // (central fix — pages whose only status affordance was this chip were failing G1 as bare <p>s).
  var chipHtml = '<p class="wh-source-chip" role="status" aria-live="polite" '
    + 'style="font-size:.62rem;color:rgba(255,255,255,0.80);margin:0;padding:3px 0 0;line-height:1.35;">'
    + parts.join(' &middot; ')
    + '</p>';

  // Arc P · FUSION 5 (P1/P5): methodology clauses collapse behind ONE plain-language
  // <details> disclosure instead of extending the grey meta-caption wall inline, so the
  // visible chip stays a single glance-first line. Real <details> = tap-openable on mobile
  // (mobile-maestro: never a hover/title tooltip). escHtml every clause — preserves the
  // callers' xss-allow invariant. Collapsed height ~0 beyond the reserved chip slot (CLS-safe).
  if (method.length) {
    var mItems = '';
    for (var j = 0; j < method.length; j++) {
      if (method[j]) mItems += '<li>' + escHtml(String(method[j])) + '</li>';
    }
    if (mItems) {
      chipHtml += '<details class="wh-method">'
        + '<summary>' + escHtml(_tt('How this is computed', 'Paano ito kinalkula')) + '</summary>'
        + '<ul>' + mItems + '</ul>'
        + '</details>';
    }
  }
  return chipHtml;
}

// ─────────────────────────────────────────────
// whListSkeleton / whListError — ONE shared loading + error state (STREAMLINE E2)
// ─────────────────────────────────────────────
// Every dynamic list shows a shimmer skeleton WHILE fetching and an inline
// error+retry on failure — never a blank panel (the P14 IDB-blank class, where a
// list silently emptied and the user couldn't tell "loading" from "broken").
// Pair with the page's existing #empty-state (no-data) + the catch→showToast.
// Styles live in components.css (.wh-skeleton / .wh-list-error). Pass the list's
// container element; for the error, pass an onRetry fn to wire the Retry button.
function whListSkeleton(el, rows) {
  if (!el) return;
  rows = rows || 3;
  var html = '<div class="wh-skeleton" aria-busy="true" aria-live="polite">';
  for (var i = 0; i < rows; i++) html += '<div class="wh-skeleton-row"></div>';
  html += '</div>';
  el.innerHTML = html;
}

// ─────────────────────────────────────────────
// whCardSkeleton — canonical CARD-shaped loading state (FF1 sibling of whListSkeleton)
// ─────────────────────────────────────────────
// Lifted 2026-07-17 from the page-local showSkeletons() copies in marketplace.html
// (grid listing card) and marketplace-admin.html (thumb-left row card) — the §10
// promote-up-a-layer move: the same pattern hand-rolled on page 2 gets lifted, never
// copied a third time. Use for card GRIDS where whListSkeleton's row shape would lie
// about the incoming layout. Self-injects its CSS once (zero setup on any page;
// no components.css dependency), aria-busy/aria-live like its sibling.
//   whCardSkeleton(gridEl, 8)                    // 'grid': image-top listing card
//   whCardSkeleton(areaEl, 4, { variant: 'row' })// 'row': thumb-left card w/ action bar
// ─────────────────────────────────────────────
// .wh-help — canonical inline-help disclosure (FI1 sibling of .wh-disclose)
// ─────────────────────────────────────────────
// Promoted 2026-07-17 from 9 byte-identical <details class="wh-help" style="…"> inline
// copies (assistant, marketplaces, ph-intelligence, project-report, public-feed,
// report-sender, status) — the §10 lift: same pattern on page 2+ becomes ONE shared rule.
// Self-injects (utils.js is the 31/32 shared surface; components.css is only linked on 11).
(function whHelpCSS() {
  if (typeof document === 'undefined' || document.getElementById('wh-help-css')) return;
  var st = document.createElement('style');
  st.id = 'wh-help-css';
  st.textContent =
    '.wh-help{margin:0.5rem 0 1rem;font-size:0.75rem;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:0.1rem 0.8rem 0.45rem}' +
    '.wh-help>summary{cursor:pointer;font-weight:700;color:rgba(255,255,255,0.86);min-height:44px;display:inline-flex;align-items:center}' +
    '.wh-help>p{margin:0.25rem 0 0.2rem;color:rgba(255,255,255,0.86);line-height:1.5}';
  (document.head || document.documentElement).appendChild(st);
})();

function whCardSkeleton(el, count, opts) {
  if (!el) return;
  count = count || 4;
  var variant = (opts && opts.variant) === 'row' ? 'row' : 'grid';
  if (!document.getElementById('wh-cardskel-css')) {
    var st = document.createElement('style');
    st.id = 'wh-cardskel-css';
    st.textContent =
      '.wh-cardskel{display:contents}' +
      '.wh-cardskel .wh-cs{background:rgba(255,255,255,0.07);border-radius:6px;animation:whCsPulse 1.4s ease-in-out infinite}' +
      '.wh-cardskel-card{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:var(--wh-radius,12px);overflow:hidden}' +
      '.wh-cardskel-row{display:flex;flex-direction:column;gap:10px;padding:14px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:var(--wh-radius,12px)}' +
      '@keyframes whCsPulse{0%,100%{opacity:.55}50%{opacity:1}}' +
      '@media (prefers-reduced-motion: reduce){.wh-cardskel .wh-cs{animation:none;opacity:.7}}';
    document.head.appendChild(st);
  }
  var card;
  if (variant === 'row') {
    card = '<div class="wh-cardskel-row">'
      + '<div style="display:flex;gap:12px;align-items:flex-start;">'
      + '<div class="wh-cs" style="width:72px;height:72px;border-radius:10px;flex-shrink:0;"></div>'
      + '<div style="flex:1;">'
      + '<div class="wh-cs" style="height:14px;width:65%;margin-bottom:8px;"></div>'
      + '<div class="wh-cs" style="height:11px;width:80%;margin-bottom:8px;"></div>'
      + '<div class="wh-cs" style="height:10px;width:40%;"></div>'
      + '</div></div>'
      + '<div style="display:flex;gap:8px;">'
      + '<div class="wh-cs" style="flex:1;height:34px;border-radius:8px;"></div>'
      + '<div class="wh-cs" style="flex:1;height:34px;border-radius:8px;"></div>'
      + '</div></div>';
  } else {
    card = '<div class="wh-cardskel-card">'
      + '<div class="wh-cs" style="height:160px;border-radius:0;"></div>'
      + '<div style="padding:0.875rem;">'
      + '<div class="wh-cs" style="height:13px;width:80%;margin-bottom:8px;"></div>'
      + '<div class="wh-cs" style="height:11px;width:50%;margin-bottom:12px;"></div>'
      + '<div style="display:flex;justify-content:space-between;">'
      + '<div class="wh-cs" style="height:22px;width:55px;border-radius:999px;"></div>'
      + '<div class="wh-cs" style="height:26px;width:55px;border-radius:8px;"></div>'
      + '</div></div></div>';
  }
  var html = '<div class="wh-cardskel" aria-busy="true" aria-live="polite">';
  for (var i = 0; i < count; i++) html += card;
  html += '</div>';
  el.innerHTML = html;
}

// ─────────────────────────────────────────────────────────────────────────────
// whFreshnessChip — the SYSTEM-STATUS component (rubric G1), extracted 2026-07-15
// ─────────────────────────────────────────────────────────────────────────────
// Rubric G1 (visibility of system status) failed on 28/32 family pages, and the ruler
// was over-reporting it: `[class*="status"]` matched `.status-badge` (an ASSET's status,
// i.e. DATA), so pages "passed" for rendering "Overdue". Real G1 = telling the user how
// FRESH what they're looking at is — analytics' "Updated 6 min ago" bar was the only
// genuine instance. This EXTRACTS that pattern so any page adopts it in one call, instead
// of the family re-inventing 28 freshness bars (the §10 component-adoption thesis, applied).
//
//   whFreshnessChip('#my-anchor', tsMillis)   // or pass the element
//
// role="status" + aria-live="polite" make it announce to a screen reader WITHOUT stealing
// focus; the dot goes amber past an hour (stale). i18n via the shared _t. Self-contained —
// no page CSS needed. Call again on each refresh to re-stamp the time.
function whFreshnessChip(target, tsMillis, opts) {
  opts = opts || {};
  var el = (typeof target === 'string') ? document.querySelector(target) : target;
  if (!el) return;
  var _tt = (typeof window._t === 'function') ? window._t : function (en) { return en; };
  if (!tsMillis) { el.textContent = ''; el.removeAttribute('role'); return; }
  // ★THE CHIP MUST TICK OR IT LIES. A page that fetches once at open and never re-stamps
  // would show "Updated just now" forever — false after an hour. Each stamped element
  // remembers its timestamp and ONE shared 60s interval re-renders all of them, so the
  // text ("6 min ago") and the stale dot stay TRUE without any page writing a loop.
  // Pages with a real refresh cycle (alert-hub's 60s loadAll) simply re-stamp: the new
  // timestamp overwrites the old and the tick keeps counting from there.
  el.__whFreshTs = tsMillis;
  el.__whFreshOpts = { suffix: opts.suffix };
  if (!window.__whFreshTick) {
    window.__whFreshTick = setInterval(function () {
      var chips = document.querySelectorAll('[role="status"]');
      for (var i = 0; i < chips.length; i++) {
        if (chips[i].__whFreshTs) whFreshnessChip(chips[i], chips[i].__whFreshTs, chips[i].__whFreshOpts);
      }
    }, 60000);
  }
  // getTime() is used instead of Date.now() so the caller controls "now" (testable, and
  // the workflow-script Date.now() ban never bites a page — pages may use it freely, but
  // keeping the arithmetic caller-supplied makes this unit-testable).
  var nowMs = (typeof opts.nowMs === 'number') ? opts.nowMs : new Date().getTime();
  var mins = Math.round((nowMs - tsMillis) / 60000);
  var when = mins < 1 ? _tt('just now', 'ngayon lang')
    : mins < 60 ? _tt(mins + ' min ago', mins + ' min ang nakalipas')
    : _tt(Math.round(mins / 60) + 'h ago', Math.round(mins / 60) + ' oras ang nakalipas');
  var stale = mins > 60;
  // opts.suffix lets a page keep its own trailing note (e.g. "· Auto-refresh every minute")
  // while still routing freshness through this component for role=status + i18n + the dot.
  // escHtml it — a page might pass user-influenced text — reusing the shared escaper.
  var esc = (typeof window.escHtml === 'function') ? window.escHtml : function (x) { return x; };
  var suffix = opts.suffix ? ' <span class="wh-fresh-suffix">' + esc(opts.suffix) + '</span>' : '';
  el.setAttribute('role', 'status');
  el.setAttribute('aria-live', 'polite');
  el.innerHTML =
    '<span class="wh-fresh-dot" aria-hidden="true" style="width:8px;height:8px;border-radius:50%;'
    + 'display:inline-block;margin-right:6px;background:' + (stale ? 'var(--wh-orange)' : 'var(--wh-green, #4ade80)') + ';"></span>'
    + '<span class="wh-fresh-txt" style="font-size:0.72rem;color:rgba(255,255,255,0.80);">'
    + _tt('Updated', 'Na-update') + ' ' + when + suffix + '</span>';
}
if (typeof window !== 'undefined') window.whFreshnessChip = whFreshnessChip;

// whFreshnessFooter — DEPRECATED / RETIRED (2026-07-22, Ian: "there is a bottom like
// updated x minute ago … we will just remove it"). The bottom-right "Updated X ago" meta
// line DUPLICATED the page's own source chip (renderSourceChip → `.wh-source-chip`, e.g.
// "Live · refreshed on load · Batay sa iyong logbook…"), which already states data freshness
// at the TOP near the data — so every adopting page showed freshness TWICE (a G4 "single
// freshness source" violation the family-wide adoption itself created). The source chip is
// now the SINGLE freshness SSOT platform-wide.
//
// Kept as a no-op (not deleted) so the ~25 defensively-guarded call-sites
// (`if (typeof whFreshnessFooter === 'function') whFreshnessFooter()`, many chained inside a
// load `.then()`) stay harmless without touching 18 pages — the SSOT edit removes the display
// everywhere in one place. It also REMOVES any footer a prior load already appended (defensive:
// a page re-run after this deploy self-heals). Re-adoption is blocked by the `freshness-footer-
// retired` gate. To restore per-page freshness, use the source chip, not this footer.
function whFreshnessFooter(_opts) {
  var el = document.getElementById('wh-fresh-footer');
  if (el && el.parentNode) el.parentNode.removeChild(el);   // cleanup if a prior load appended it
  return;                                                   // no-op: freshness lives in the source chip
}
if (typeof window !== 'undefined') window.whFreshnessFooter = whFreshnessFooter;

// whCapRows — progressive disclosure for long tables (rubric A3, FAMILY roadmap F3).
// A3 failed on 31/32 pages for the same reason: every long table renders ALL rows at
// once (Miller/Hick: the reader pays for every row whether they need it or not). This
// caps a table at `max` rows behind a "Show all N" toggle — the analytics show-all
// pattern extracted as a shared organism. HONESTY BAR: call it only on tables whose
// rows are REAL overflow (the component no-ops under max+3 rows so a 9-row table isn't
// hidden behind a pointless click — a disclosure with nothing to disclose is decoration).
// aria-expanded mirrors state (same WCAG 4.1.2 rule as the analytics toggles).
function whCapRows(tableEl, max) {
  if (!tableEl) return;
  max = max || 8;
  var rows = tableEl.querySelectorAll('tbody tr');
  if (rows.length <= max + 2) return;             // not real overflow — no-op
  if (tableEl.__whCapped) return;                 // idempotent across re-renders
  tableEl.__whCapped = true;
  var _tt = (typeof window._t === 'function') ? window._t : function (en) { return en; };
  for (var i = max; i < rows.length; i++) rows[i].hidden = true;
  var btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'showall-toggle';
  btn.setAttribute('aria-expanded', 'false');
  btn.style.cssText = 'display:block;width:100%;margin-top:8px;min-height:44px;background:rgba(255,255,255,0.04);'
    + 'border:1px solid rgba(255,255,255,0.1);border-radius:var(--wh-radius-sm);color:rgba(255,255,255,0.83);'
    + 'font-family:inherit;font-size:0.75rem;font-weight:600;cursor:pointer;';
  var more = rows.length - max;
  var labelAll  = _tt('Show all ' + rows.length + ' ↓', 'Ipakita lahat ng ' + rows.length + ' ↓');
  var labelLess = _tt('Show less ↑', 'Ipakita ang mas kaunti ↑');
  btn.textContent = labelAll;
  btn.addEventListener('click', function () {
    var open = btn.getAttribute('aria-expanded') === 'true';
    for (var i = max; i < rows.length; i++) rows[i].hidden = open;
    btn.setAttribute('aria-expanded', open ? 'false' : 'true');
    btn.textContent = open ? labelAll : labelLess;
  });
  tableEl.insertAdjacentElement('afterend', btn);
}
if (typeof window !== 'undefined') window.whCapRows = whCapRows;

// AUTO-STAMP on successful data reads (G1 at family scale). Per-page call-site
// archaeology proved unreliable — pages boot through heterogeneous paths (an IIFE, a
// DOMContentLoaded handler, a tab switch, a restore flow), and stamping the wrong one
// means the chip never renders (measured: 5 of 19 first-pass adoptions missed the real
// boot path). Every page's data DOES flow through fetch() to the Supabase REST API, so
// ONE wrapper stamps on any SUCCESSFUL data response:
//   - fires only on response.ok  -> a failed fetch never claims "Updated" (the honesty bar);
//   - debounced 800ms            -> a burst of parallel reads stamps once;
//   - "last successful read" IS the freshness fact the chip reports — true by construction.
// Explicit per-page whFreshnessFooter() calls still work and simply re-stamp the same el.
(function whFreshnessAutoStamp() {
  if (typeof window === 'undefined' || !window.fetch || window.__whFreshHooked) return;
  window.__whFreshHooked = true;
  var origFetch = window.fetch;
  var t = null;
  window.fetch = function () {
    var p = origFetch.apply(this, arguments);
    try {
      var url = String(arguments[0] && arguments[0].url || arguments[0] || '');
      if (/\/rest\/v1\/|\/functions\/v1\/|supabase/.test(url)) {
        p.then(function (res) {
          if (res && res.ok) {
            clearTimeout(t);
            t = setTimeout(function () {
              try { whFreshnessFooter(); } catch (_) { /* empty-catch-allow: stamp is best-effort chrome */ }
            }, 800);
          }
        }).catch(function () { /* empty-catch-allow: observer only — never affect the caller's promise */ });
      }
    } catch (_) { /* empty-catch-allow: URL parse is best-effort */ }
    return p;
  };
})();
// whRegisterAutoRetry — T126 (2026-08-26): failed READS recover themselves on reconnect.
//
// The write side already does this: offline queues drain on 'online', logbook syncs, banners
// repaint. Reads were the half left manual, and "manual" assumes somebody is there. A wall-mounted
// alert board has nobody; a phone in a pocket has nobody at the moment the signal returns.
//
// Kept deliberately small and cautious, because an auto-retry that misbehaves is worse than none:
//   * it fires only on the 'online' event and on a tab becoming visible AFTER an offline spell —
//     never on a timer, so a genuinely broken backend is not hammered;
//   * it checks the element is STILL showing the error before re-running, so a section the person
//     already recovered by hand is left alone;
//   * one in-flight retry per element, and a 3s floor between attempts;
//   * an element detached from the document is dropped, so a re-rendered page cannot accumulate
//     stale callbacks (the listener-lifecycle leak this codebase has a gate for).
var _whAutoRetry = (typeof WeakMap === 'function') ? new WeakMap() : null;
var _whAutoRetryEls = [];
function whRegisterAutoRetry(el, fn) {
  if (!el || typeof fn !== 'function' || !_whAutoRetry) return;
  if (!_whAutoRetry.has(el)) _whAutoRetryEls.push(el);
  _whAutoRetry.set(el, { fn: fn, last: 0, busy: false });
}
function whRunAutoRetries(reason) {
  if (!_whAutoRetry) return 0;
  var now = Date.now(), ran = 0;
  _whAutoRetryEls = _whAutoRetryEls.filter(function (el) {
    if (!el || !el.isConnected) return false;         // gone from the DOM: drop it
    var rec = _whAutoRetry.get(el);
    if (!rec) return false;
    // still in the error state? if the page recovered it another way, do not touch it
    if (!el.querySelector('.wh-list-error')) return true;
    if (rec.busy || (now - rec.last) < 3000) return true;
    rec.busy = true; rec.last = now;
    try {
      var out = rec.fn();
      if (out && typeof out.then === 'function') out.then(function () { rec.busy = false; }, function () { rec.busy = false; });
      else rec.busy = false;
      ran++;
    } catch (_) { rec.busy = false; }
    return true;
  });
  if (ran && typeof console !== 'undefined' && console.info) console.info('[wh] auto-retried ' + ran + ' failed read(s) on ' + reason);
  return ran;
}
if (typeof window !== 'undefined') {
  window.whRegisterAutoRetry = whRegisterAutoRetry;
  window.whRunAutoRetries = whRunAutoRetries;
}
if (typeof window !== 'undefined' && typeof document !== 'undefined') {
  var _whWasOffline = false;
  window.addEventListener('offline', function () { _whWasOffline = true; });
  window.addEventListener('online', function () { _whWasOffline = false; whRunAutoRetries('reconnect'); });
  document.addEventListener('visibilitychange', function () {
    // only after an offline spell: returning to a tab that never lost the network has nothing to fix
    if (document.visibilityState === 'visible' && _whWasOffline) { _whWasOffline = false; whRunAutoRetries('tab visible after offline'); }
  });
}

/**
 * T197 (2026-08-28) — a stored photo that will not load must SAY so, not leave wreckage.
 *
 * The marketplace renders storage-hosted photos at five sites across four pages, every one of
 * them `<img src="${e(item.image_url)}" alt="${e(item.title)}">` with no error handling. When the
 * storage layer is down (its own failure mode — the DB and the rest of the page stay up, which is
 * the whole point of T197) each of those becomes a browser broken-image glyph inside a box that
 * still occupies its full grid cell: the reader is left to guess whether the listing has no photo,
 * or the photo is gone, or the page is broken.
 *
 * ★ONE CAPTURE-PHASE LISTENER, NOT FIVE INLINE onerror ATTRIBUTES. `error` does not bubble but it
 * DOES capture, so a single document-level listener covers all five sites, every image rendered
 * after them, and any page that later shows a stored photo — without touching five template
 * strings, and without inline handlers that a tightened script-src would refuse.
 *
 * ★SCOPED BY SRC, deliberately. It fires only for storage-hosted objects (/storage/v1/object/),
 * never for a decorative logo or icon: replacing a failed brand mark with "photo unavailable"
 * would be noise, and a failure the reader can do nothing about is not worth a label. The box
 * keeps the failed image's own dimensions so the grid does not reflow around it.
 */
function whPhotoFallback(img) {
  if (!img || img.getAttribute('data-wh-photo-failed')) return;
  img.setAttribute('data-wh-photo-failed', '1');
  var label = (img.getAttribute('alt') || '').trim();
  var r = img.getBoundingClientRect();
  var box = document.createElement('div');
  box.setAttribute('role', 'img');
  // The alt text is the listing's title — keep it, so the reader still knows WHICH photo is gone.
  box.setAttribute('aria-label', label ? (label + ' (photo unavailable)') : 'Photo unavailable');
  box.className = 'wh-photo-failed';
  box.style.cssText =
    'display:flex; align-items:center; justify-content:center; text-align:center;' +
    'background:rgba(255,255,255,0.04); border:1px dashed rgba(255,255,255,0.18);' +
    'color:rgba(255,255,255,0.45); font-size:0.7rem; line-height:1.3; padding:6px;' +
    'border-radius:8px; box-sizing:border-box;' +
    (r.width  ? 'width:' + r.width  + 'px;' : 'width:100%;') +
    (r.height ? 'height:' + r.height + 'px;' : 'min-height:80px;');
  box.textContent = 'Photo unavailable';
  if (img.parentNode) img.parentNode.replaceChild(box, img);
}

if (typeof document !== 'undefined') {
  document.addEventListener('error', function (ev) {
    var t = ev && ev.target;
    if (!t || t.tagName !== 'IMG') return;
    var src = t.getAttribute('src') || '';
    if (src.indexOf('/storage/v1/object/') === -1) return;   // stored photos only
    whPhotoFallback(t);
  }, true);   // capture: `error` does not bubble
}

/**
 * whIdVerified — is this seller's IDENTITY verified? (T70, 2026-08-28)
 *
 * The "Certified" chip beside this one was centralised in 2026-07 with a comment saying "a
 * verification badge requires the thing it verifies. Central rule in utils.js so all three surfaces
 * that render this chip cannot drift apart." The ID-Verified chip standing next to it never got the
 * same treatment, and drifted across FOUR render sites with FOUR different predicates:
 *
 *   marketplace card    : item.seller_verified                        -> "Verified"
 *   marketplace detail  : sp.kyb_verified || item.seller_verified     -> "ID Verified"
 *   seller profile      : _seller.kyb_verified                        -> "ID Verified"
 *   asset-hub mini-card : r.seller_verified                           -> "· verified"
 *
 * MEASURED on the fixture: Dennis Aquino carries kyb_verified FALSE on his seller record and
 * seller_verified TRUE on his listings, so he read as verified on three surfaces and UNVERIFIED on
 * his own profile page. A trust badge that disagrees with itself is worse than no badge, because
 * each surface looks authoritative on its own.
 *
 * ★THE RULE IS THE CONSERVATIVE ONE, and deliberately. Identity belongs to the SELLER, not to a
 * listing row: marketplace_sellers.kyb_verified is the checked fact, while
 * marketplace_listings.seller_verified is a per-row copy that can be stale or set independently.
 * Reading the seller record is also the direction that cannot OVER-claim — the failure that matters
 * for a trust signal is showing the badge to someone who has not earned it, not withholding it from
 * someone who has.
 *
 * Pass whichever objects a surface has; a listing-only caller still gets the right answer once its
 * seller record is loaded, and gets `false` rather than a guess until then.
 *
 * Accepts either shape, because the same fact arrives under two names: a seller record carries
 * `kyb_verified`, while v_marketplace_listings_truth exposes the joined column as
 * `seller_kyb_verified`. Both are the SELLER's checked identity; neither is the listing's own
 * `seller_verified` copy, which is the field that drifted.
 */
function whIdVerified(seller, listing) {
  var s = seller && typeof seller === 'object' ? seller : null;
  if (s && 'kyb_verified' in s) return !!s.kyb_verified;
  if (s && 'seller_kyb_verified' in s) return !!s.seller_kyb_verified;
  var l = listing && typeof listing === 'object' ? listing : null;
  if (l && 'seller_kyb_verified' in l) return !!l.seller_kyb_verified;
  // Nothing authoritative in hand: do NOT fall back to the listing's seller_verified copy — that
  // fallback is exactly what produced the drift. Absent evidence is not evidence.
  return false;
}

function whListError(el, message, onRetry) {
  if (!el) return;
  var e = escHtml;
  el.innerHTML =
    '<div class="wh-list-error" role="alert">'
    + '<div class="wh-list-error-icon" aria-hidden="true">⚠️</div>'
    + '<div>' + e(message || "Couldn’t load this. Check your connection and try again.") + '</div>'
    + (onRetry ? '<button type="button" class="wh-list-retry">Retry</button>' : '')
    // T71 (2026-08-25): "is it me or them?" - every failure state now points at the one page
    // built to answer that. ONE central edit reaches every whListError adopter (~20 pages);
    // status.html is static-first, so it loads even when the DB that broke this read is down.
    // T113 (2026-08-26): this link shipped as a bare inline anchor - 229x12px, well under the 44px
    // gloved floor - and it rides in EVERY whListError panel, i.e. ~20 pages' read-failure states.
    // A 12px target is hard for anyone and hopeless in gloves, at the exact moment a person is
    // already stuck. The idiom was already in this file two functions away (the "All assets" and
    // "PM Scheduler" links use inline-flex + min-height:44px); this one just did not follow it.
    + '<div style="margin-top:0.5rem;"><a href="status.html" style="font-size:0.72rem;color:rgba(255,255,255,0.6);text-decoration:underline;text-underline-offset:2px;display:inline-flex;align-items:center;min-height:44px;">Is it just you? Check the platform status page</a>'
    // T193 (2026-08-26): the ESCALATION DOOR, from the state that needs it. When retry has
    // failed and status says the platform is fine, the person is stuck with nowhere to go -
    // "dead ends have a door". The feedback widget already exists on every page; this opens it
    // with the CONTEXT pre-attached (page, the error sentence the person is looking at, time),
    // so a report arrives describing the failure instead of "it doesn't work". Rendered only
    // where the widget is actually present, so it can never be a door onto nothing.
    + (typeof window !== 'undefined' && window.WHFeedback && typeof window.WHFeedback.open === 'function'
        ? ' <button type="button" class="wh-list-report" style="font-size:0.72rem;color:rgba(255,255,255,0.6);background:none;border:none;text-decoration:underline;text-underline-offset:2px;cursor:pointer;min-height:44px;padding:0 4px;">Report this problem</button>'
        : '')
    + '</div>'
    + '</div>';
  if (onRetry) {
    var btn = el.querySelector('.wh-list-retry');
    if (btn) btn.addEventListener('click', onRetry);
    // T126 (2026-08-26): A RETRY BUTTON IS USELESS TO A SCREEN NOBODY IS STANDING AT. Reconnect
    // handlers on this platform drain write QUEUES and repaint banners, but a failed READ just sits
    // there waiting for a tap. On a wall-mounted alert board that tap never comes, so one network
    // blip leaves a plant staring at a stale error for the rest of the shift - and the same is true
    // of a phone that was in a pocket when the signal returned. Remember this element's retry and
    // re-run it when connectivity comes back.
    whRegisterAutoRetry(el, onRetry);
  }
  var rep = el.querySelector('.wh-list-report');
  if (rep) {
    rep.addEventListener('click', function () {
      try {
        window.WHFeedback.open({
          subject: 'Problem loading a page section',
          body: 'What I saw: ' + (message || 'a load failure') + '\n'
              + 'Page: ' + (typeof location !== 'undefined' ? location.pathname + location.search : '?') + '\n'
              + 'When: ' + new Date().toISOString() + '\n\n'
              + 'What I was trying to do: ',
        });
      } catch (_) { /* empty-catch-allow: the widget owns its own failure surface */ }
    });
  }
}
// Self-contained styles (STREAMLINE E2 rollout): inject the .wh-skeleton /
// .wh-list-error CSS once so whListSkeleton()/whListError() render correctly on
// ANY page that loads utils.js — not just the 11 that <link> components.css.
// The rules are theme-agnostic (white-alpha on the dark app surface, no page
// design tokens), so they're safe to inject globally. Idempotent (id-guarded);
// the components.css pages just get an identical, harmless duplicate rule set.
if (typeof document !== 'undefined' && !document.getElementById('wh-list-states-css')) {
  var whListStatesCss = document.createElement('style');
  whListStatesCss.id = 'wh-list-states-css';
  whListStatesCss.textContent =
    '.wh-skeleton{display:flex;flex-direction:column;gap:8px;padding:4px 0}' +
    '.wh-skeleton-row{height:44px;border-radius:10px;background:linear-gradient(100deg,rgba(255,255,255,0.04) 30%,rgba(255,255,255,0.09) 50%,rgba(255,255,255,0.04) 70%);background-size:200% 100%;animation:wh-shimmer 1.3s ease-in-out infinite}' +
    '@keyframes wh-shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}' +
    '@media (prefers-reduced-motion:reduce){.wh-skeleton-row{animation:none}}' +
    /* D1 U2: shared brief row-links (risk/pm-due/parts) were 39px tall (padding:8px) — bump to a 44px gloved-field tap target everywhere these render */
    '.wh-risk-row,.wh-pmdue-row,.wh-parts-row{min-height:44px;box-sizing:border-box}' +
    '.wh-list-error{text-align:center;padding:1.4rem 1rem;font-size:0.82rem;color:rgba(255,255,255,0.86);line-height:1.5}' +
    '.wh-list-error .wh-list-error-icon{font-size:1.4rem}' +
    '.wh-list-error button{margin-top:0.6rem;min-height:44px;padding:0 16px;border-radius:8px;border:1px solid rgba(255,255,255,0.18);background:transparent;color:var(--wh-cloud, #F4F6FA);font-family:inherit;font-size:0.78rem;font-weight:600;cursor:pointer}' +
    '.wh-list-error button:hover{border-color:rgba(255,255,255,0.32)}';
  (document.head || document.documentElement).appendChild(whListStatesCss);
}

// Arc P · FUSION 5: the .wh-method disclosure emitted by renderSourceChip() (methodology
// collapsed under a "How this is computed" toggle). Injected here so it reaches EVERY page
// that loads utils.js — components.css is <link>-ed on only ~12 pages, so a CSS-file-only
// rule would miss the Tailwind pages (pm-scheduler/inventory/skillmatrix). ONE source of truth.
if (typeof document !== 'undefined' && !document.getElementById('wh-method-css')) {
  var whMethodCss = document.createElement('style');
  whMethodCss.id = 'wh-method-css';
  whMethodCss.textContent =
    '.wh-method{margin:2px 0 0;font-size:.62rem;line-height:1.4}' +
    // 44px-tall tap zone (mobile-maestro floor) but visually a single small caption line;
    // marker hidden, replaced by an ⓘ so it reads as an info toggle, not a code affordance.
    '.wh-method>summary{display:flex;align-items:center;gap:5px;min-height:44px;cursor:pointer;list-style:none;color:rgba(255,255,255,0.80);font-weight:600;user-select:none}' +
    '.wh-method>summary::-webkit-details-marker{display:none}' +
    '.wh-method>summary::before{content:"\\24D8";font-weight:400;opacity:.75}' +
    '.wh-method>summary:hover,.wh-method[open]>summary{color:rgba(255,255,255,0.85)}' +
    '.wh-method>ul{margin:0 0 6px;padding:0 0 0 18px;color:rgba(255,255,255,0.80);line-height:1.5}' +
    '.wh-method>ul>li{margin:1px 0}';
  (document.head || document.documentElement).appendChild(whMethodCss);
}

// STREAMLINE E4: the brand palette is NOT injected from JS — it lives in
// tokens.css, which every page <link>s in <head> (directly, or via components.css
// which @imports it). A static render-blocking <link> can't FOUC the way a late
// JS injection would on a body-loaded utils.js, and it keeps ONE source of truth.

// ─────────────────────────────────────────────
// whFmt* — shared number / date / unit / ₱ formatters (STREAMLINE E6)
// ─────────────────────────────────────────────
// ONE Philippine-locale source of truth so currency (₱), dates (Asia/Manila),
// numbers, and hrs/days units render IDENTICALLY everywhere instead of per-page
// ad-hoc `'₱' + n` / bespoke toLocaleDateString. All null/NaN-safe (never print
// "₱NaN" / "Invalid Date" on the glass). Guarded by validate_user_facing_jargon
// sibling lint + the E6 formatter skill rule.
/* whSafeSearchTerm — make a typed phrase safe to interpolate into a PostgREST .or() filter.
 *
 * MEASURED 2026-08-26 against the live REST endpoint: a search term containing a COMMA returns
 * HTTP 400, "failed to parse logic tree". PostgREST's or=(a,b) grammar splits on top-level commas,
 * so an unquoted comma inside a value ends the condition early and the whole filter is rejected.
 * Parentheses do the same, and a bare backslash can strand the LIKE escapes below.
 *
 * ★THE TERM THAT BREAKS IT IS THE ORDINARY ONE. "Bearing, spherical roller, 22320 E1 XL C3, SKF" is
 * how a real part is named - it is the platform's OWN example in the longest-truncates gate - and
 * typing it into the logbook, community or global search produced a 400 that the page renders as a
 * failed READ. A legitimate search looked like the system was broken.
 *
 * ★TWO DIFFERENT JOBS, both needed, and only one was being done: escaping % and _ stops a wildcard
 * changing WHICH rows match; removing , ( ) \ stops the filter from failing to parse at all. Pages
 * were doing the first and not the second. marketplace.html was the exception - it strips the
 * delimiters - which is why the same phrase searched there and worked.
 *
 * Delimiters are removed rather than escaped because PostgREST has no escape for them inside an
 * unquoted value; a space keeps word boundaries so "Bearing, spherical" still matches "Bearing
 * spherical". The result is then LIKE-escaped, so a literal % or _ stays literal.
 */
function whSafeSearchTerm(raw, maxLen) {
  var s = String(raw == null ? '' : raw);
  s = s.replace(/[,()\\]/g, ' ').replace(/\s+/g, ' ').trim();
  s = s.replace(/%/g, '\\%').replace(/_/g, '\\_');
  var cap = (typeof maxLen === 'number' && maxLen > 0) ? maxLen : 100;
  return s.slice(0, cap);
}
if (typeof window !== 'undefined') window.whSafeSearchTerm = whSafeSearchTerm;

function whFmtPeso(n, opts) {
  opts = opts || {};
  /* ABSENT IS NOT ZERO (found 2026-08-04, AZ-failure-injection/fail_null_field walk). This helper
     was written to stop "₱NaN" reaching the glass and chose ₱0 as the substitute — trading a
     VISIBLE defect for an INVISIBLE one. Number(null) is 0 and finite, so a null amount slipped
     straight through as a confident "₱0.00": a filed top-up of PHP300 rendered as PHP0.00, and a
     ledger line of unknown value rendered as "+₱0", which says the entry moved nothing. Same family
     as the reward cap, where NULL meaning "no cap" arrived as a cap of zero.
     A real zero is the number 0 and still prints ₱0. An ABSENT value now prints a gap, because a
     person can act on "we do not know" and cannot act on a wrong number. Pass opts.gap to override.
     NOTE the base tables are NOT NULL, so today this is defensive: the views report the columns as
     nullable (Postgres does not propagate NOT NULL through a view), which is exactly the door a
     future LEFT JOIN or filter would come through. */
  if (n === null || n === undefined || n === '') return (opts.gap != null) ? opts.gap : '—';
  var v = Number(n);
  if (!isFinite(v)) return (opts.gap != null) ? opts.gap : '—';
  var dp = (opts.decimals != null) ? opts.decimals : (v % 1 === 0 ? 0 : 2);
  return '₱' + v.toLocaleString('en-PH', { minimumFractionDigits: dp, maximumFractionDigits: dp });
}
function whFmtNum(n, dp) {
  // same rule as whFmtPeso: an absent count is a gap, a real zero is 0
  if (n === null || n === undefined || n === '') return '—';
  var v = Number(n);
  if (!isFinite(v)) return '—';
  return v.toLocaleString('en-PH', (dp != null) ? { minimumFractionDigits: dp, maximumFractionDigits: dp } : undefined);
}
// Central quantity parser (deepwalk D5, 2026-07-22). Modal write paths (inventory Use/Restock) submit
// via a button handler, NOT a native <form>, so the qty <input type=number min step>'s DECLARED contract
// is never enforced by the browser — a typed/pasted 2.5 or 1e-9 slips past a bare `parseFloat()>0` check
// and deducts a fractional/absurd quantity that corrupts the integer stock count (feeds analytics/alerts/
// forecast wrong). This HONORS the input's own min/step attributes (integer step => whole numbers only;
// min => a floor), so it stays correct if a future measured part sets step="any". Returns {ok, qty, error}.
// The on-hand CEILING stays with the caller (it owns the unit + item context).
function whParseQty(inputEl, opts) {
  opts = opts || {};
  var label = opts.label || 'Quantity';
  var raw = (inputEl && inputEl.value != null) ? String(inputEl.value).trim() : '';
  var n = Number(raw);
  if (raw === '' || !isFinite(n)) return { ok: false, error: label + ' must be a valid number.' };
  if (n <= 0) return { ok: false, error: label + ' must be greater than 0.' };
  var stepAttr = (inputEl && inputEl.getAttribute) ? inputEl.getAttribute('step') : null;
  var step = (stepAttr && stepAttr !== 'any') ? parseFloat(stepAttr) : (opts.step != null ? opts.step : null);
  if (step && Number.isInteger(step) && !Number.isInteger(n))
    return { ok: false, error: 'Enter a whole number (no fractions).' };
  var minAttr = (inputEl && inputEl.getAttribute) ? inputEl.getAttribute('min') : null;
  var min = (minAttr != null && minAttr !== '') ? parseFloat(minAttr) : (opts.min != null ? opts.min : null);
  if (min != null && isFinite(min) && n < min)
    return { ok: false, error: label + ' must be at least ' + min + '.' };
  return { ok: true, qty: n };
}
if (typeof window !== 'undefined') window.whParseQty = whParseQty;
// Central price parser (deepwalk D5, 2026-07-22). Marketplace post/edit forms are `novalidate` and their
// submit handlers validated only title/desc, so an unvalidated price reached the DB: a NEGATIVE value hit
// the `price_nonneg` CHECK (raw 23514) and an over-precision value hit `numeric(14,2)` overflow — BOTH
// surfacing a cryptic database error to the seller instead of a friendly message (the P4 validate-before-
// write class, on 2 surfaces — METHOD LAW: one helper). Price differs from QTY: blank => negotiable (null),
// 0 => free (allowed), fractional (2 dp) allowed. Returns {ok, value:(number|null), error}. Default sane
// cap ₱10,000,000 (override via opts.max), well under numeric(14,2)'s ceiling.
/* ─────────────────────────────────────────────
   whGcashParse / whGcashPasteWire — stop making people transcribe 13 digits
   ─────────────────────────────────────────────
   Ian, 2026-08-03: "your goal make it convenient for them in UI and UX."

   The single friction shared by all three parties is the same: a 13-digit GCash
   reference, copied by hand from one app into another. The provider does it to file a
   top-up, the buyer does it to confirm a job payment, and the founder used to compare
   two of them by eye. Nobody enjoys it and every one of them ALREADY HAS the receipt —
   it is sitting in their notification shade or their GCash history.

   So: paste the receipt, and the fields fill themselves. Amount and reference are read
   out of the text; the person checks rather than transcribes.

   ONE PARSER. The same shape the gcash-receipt-inbound edge function uses, deliberately:
   if the client extracted a different reference from the same text than the server did,
   the provider's filing and the founder's receipt would stop matching and auto-verify
   would silently stall. Tolerant about wording, STRICT about the 13-digit shape, because
   that shape is what the two sides join on.
*/
/* whGcashReadReceipt — upload the screenshot, let the fields fill themselves.
   The other half of whGcashPasteWire: some people copy the receipt TEXT, some screenshot it,
   and both should work. Returns {reference, amount} or throws with a message meant to be shown.
   Never invents a value: an unreadable image says so, because a wrong 13-digit reference files
   a claim that can never match and is worse than no reference at all. */
async function whGcashReadReceipt(db, file) {
  if (!file) throw new Error('No image selected');
  if (file.size > 5 * 1024 * 1024) throw new Error('That image is larger than 5 MB');
  const dataUrl = await new Promise(function (res, rej) {
    const fr = new FileReader();
    fr.onload = function () { res(fr.result); };
    fr.onerror = function () { rej(new Error('Could not read that file')); };
    fr.readAsDataURL(file);
  });
  const { data, error } = await db.functions.invoke('gcash-receipt-ocr', { body: { image_data_url: dataUrl } });
  if (error) throw new Error('Could not read the receipt. Type the details, or paste the receipt text.');
  /* The function speaks the platform ENVELOPE: { ok, data } on success, { ok:false, code, message }
     on refusal. This read `data.parsed` directly and would have silently found undefined the moment
     the function adopted the contract — a shape change on one side and a stale reader on the other.
     Unwrap defensively so either shape works rather than pinning to today's. */
  const payload = (data && typeof data === 'object' && 'ok' in data && data.data) ? data.data : data;
  if (data && data.ok === false) throw new Error(data.message || 'Could not read the receipt.');
  if (payload && payload.azure_unavailable) throw new Error(payload.note || 'Receipt reading is not available here.');
  if (payload && payload.error) throw new Error(payload.error);
  const parsed = (payload && payload.parsed) || {};
  if (!parsed.reference && parsed.amount == null) {
    throw new Error((data && data.note) || 'No reference or amount found in that image.');
  }
  return parsed;
}
if (typeof window !== 'undefined') { window.whGcashReadReceipt = whGcashReadReceipt; }

function whGcashParse(text) {
  var t = String(text == null ? '' : text).replace(/ /g, ' ');
  var refM = t.match(/(?:ref(?:erence)?\.?\s*(?:no\.?|number)?\s*[:\-]?\s*)(\d{13})/i)
          || t.match(/(?:^|[^\d])(\d{13})(?![\d])/);
  var amtM = t.match(/(?:php|₱|p)\s*([\d,]+(?:\.\d{1,2})?)/i);
  var amount = amtM ? Number(String(amtM[1]).replace(/,/g, '')) : null;
  return {
    reference: refM ? refM[refM.length - 1] : null,
    amount: (amount != null && isFinite(amount) && amount > 0) ? amount : null
  };
}

/* Wire a paste anywhere in a form to fill its amount + reference fields.
   Non-destructive: a field the person already filled is never overwritten, because
   silently replacing a number someone typed is worse than not helping at all. Returns
   what it filled so the caller can say so out loud — a form that changes under you
   without a word is unsettling on a money screen. */
function whGcashPasteWire(opts) {
  var amtEl = typeof opts.amount === 'string' ? document.getElementById(opts.amount) : opts.amount;
  var refEl = typeof opts.reference === 'string' ? document.getElementById(opts.reference) : opts.reference;
  var onFill = opts.onFill || function () {};
  var host = opts.host || (refEl && refEl.form) || document;
  if (!refEl && !amtEl) return;
  host.addEventListener('paste', function (ev) {
    var text = (ev.clipboardData || window.clipboardData);
    text = text ? text.getData('text') : '';
    if (!text || text.length < 12) return;             // a bare ref paste needs no help
    var got = whGcashParse(text);
    if (!got.reference && got.amount == null) return;  // not a receipt; leave the paste alone
    var filled = [];
    if (got.reference && refEl && !String(refEl.value || '').trim()) {
      refEl.value = got.reference; filled.push('reference');
    }
    if (got.amount != null && amtEl && !String(amtEl.value || '').trim()) {
      amtEl.value = got.amount; filled.push('amount');
    }
    if (filled.length) {
      ev.preventDefault();                              // we consumed the receipt
      [refEl, amtEl].forEach(function (el) {
        if (el) el.dispatchEvent(new Event('input', { bubbles: true }));
      });
      onFill(got, filled);
    }
  });
}
if (typeof window !== 'undefined') { window.whGcashParse = whGcashParse; window.whGcashPasteWire = whGcashPasteWire; }

function whParsePrice(inputEl, opts) {
  opts = opts || {};
  var raw = (inputEl && inputEl.value != null) ? String(inputEl.value).trim() : '';
  if (raw === '') return { ok: true, value: null };              // blank = negotiable
  var n = Number(raw);
  if (!isFinite(n)) return { ok: false, error: 'Enter a valid price, or leave blank for negotiable.' };
  if (n < 0) return { ok: false, error: 'Price cannot be negative.' };
  var max = (opts.max != null) ? opts.max : 10000000;            // ₱10M sane cap
  if (n > max) return { ok: false, error: 'Price looks too high. Please double-check (max ₱' +
    (typeof whFmtNum === 'function' ? whFmtNum(max) : max) + ').' };
  return { ok: true, value: Math.round(n * 100) / 100 };         // clamp to 2 decimals (numeric scale=2)
}
if (typeof window !== 'undefined') window.whParsePrice = whParsePrice;
// Central "has this seller EARNED the Certified badge?" test (marketplace deepwalk 2026-07-24, MK1/J11).
// The badge used to render on the cert_verified flag ALONE on three surfaces (the public seller profile,
// the listing detail sheet, and the seller's own dashboard), while the certifications LIST render on the
// same pages already required the list. Three sellers were found with cert_verified true, certifications
// NULL and cert_verified_at NULL, so a violet "Certified" chip claimed an admin had verified trade
// credentials that did not exist. One rule, one place: a verification badge requires the thing it
// verifies. Kept as a plain predicate (no DOM, no async) so every surface can call it inline.
function whCertBadgeEarned(seller) {
  if (!seller || !seller.cert_verified) return false;
  return String(seller.certifications || '').trim().length > 0;
}
if (typeof window !== 'undefined') window.whCertBadgeEarned = whCertBadgeEarned;
// Central WRITE-failure message (MK11 · error-remedy actionability, marketplace deepwalk 2026-07-24).
// The same shape turned up four independent times in one walk: a client write failed because the
// SESSION was gone (42501 / 401 / RLS), and the catch answered "Try again." Retrying reproduces that
// failure exactly, so the app was proposing a remedy it knew could not work — after the user had
// already typed, in one case a phone number. The harvested standard (nngroup.com/articles/
// error-message-guidelines) asks an error to give "context and potential remedies" and "instructions
// on how to resolve"; a remedy that cannot resolve it fails that on its own terms.
// One helper rather than a branch per call site, the same way whAiError centralizes the 429 mapping.
// `fallback` is the caller's own wording for a genuinely retryable failure, so nothing is flattened.
// The DETECTION is what must be shared; the REMEDY should stay local. A caller that can say "sign in
// again and re-save it" or "your message will go through" is giving better instructions than any
// generic string, which is what the standard asks for, so the helper deliberately does not flatten
// those. Sites with nothing specific to add use whWriteError below.
// 42501 is AMBIGUOUS and treating it as proof of a dead session sends signed-in people to the sign-in page
// for a rule they simply broke. Postgres raises 42501 for a genuine privilege/RLS refusal, AND it is the
// errcode our own guards deliberately raise for policy refusals written for a human to read ("A credit
// balance is only visible to its owner", "A new seller can keep 3 listings live until one of them sells",
// "Only the client on this job can apply their credits to it"). The two are told apart by the MESSAGE:
// Postgres's own are formulaic ("new row violates row-level security policy for table ..."), ours are
// sentences. This was fixed once on the inquiry path, where a 42501 told a signed-in buyer their session
// had expired; the shared helper kept the bug for every other path.
var _WH_PG_DENIAL = /row-level security|permission denied|not authenticated|JWT|invalid token|session expired/i;

// 401 AND 403 ARE NOT THE SAME EVENT, AND ANSWERING BOTH WITH "SIGN IN AGAIN" SENDS HALF OF THEM TO
// FIX THE ONE THING THAT IS NOT BROKEN. PostgREST distinguishes them precisely:
//   401  the caller is ANONYMOUS or the token is dead  -> the session really is the problem
//   403  the caller is AUTHENTICATED and a row/table was refused -> the session is perfectly fine
// Measured 2026-08-05 by injecting each status at the route layer across six surfaces. On a 403 the
// marketplace rendered "Your session expired, so the marketplace could not be read. Sign in again to
// continue." with a Sign in again button — on five of six surfaces. Signing out and back in lands on
// the same 403, so the remedy offered is the one that cannot work. The 401 wording, by contrast, was
// exactly right, which is why only the discrimination needed changing and not the sentences.
// This file already records the same defect being fixed once on the inquiry WRITE path while "the
// shared helper kept the bug for every other path" — this is that helper.
function whIsAuthFailure(err) {
  if (!err) return false;
  var status = err.status != null ? String(err.status) : '';
  var msg = String(err.message || '');
  if (status === '401') return true;
  if (status === '403') return false;          // authenticated, and refused. Not a session problem.
  // 42501 IS NOT AMBIGUOUS, even with no HTTP status attached. Postgres raises it for
  // insufficient_privilege, which by definition means the caller WAS identified and was refused; a
  // dead session surfaces as PGRST301 / "JWT expired" instead. The comment above this regex says the
  // 42501-tells-a-signed-in-person-to-sign-in bug "was fixed once on the inquiry path" and that "the
  // shared helper kept the bug for every other path" — it still did, because the message that comes
  // with a 42501 is "permission denied for table ...", which _WH_PG_DENIAL matches. Measured live
  // 2026-08-06: whIsAuthFailure({code:'42501', message:'permission denied for table
  // marketplace_sellers'}) returned TRUE and whReadError answered "Your session expired ... Sign in
  // again", to someone whose session was perfectly healthy. They sign in again, and it changes
  // nothing, because the thing simply is not theirs to see.
  if (String((err && err.code) || '') === '42501') return false;
  // Anything else with no status is genuinely ambiguous. It reaches here from paths that never saw a
  // response object, and historically meant a dead session, so it keeps that reading.
  return _WH_PG_DENIAL.test(msg);
}
if (typeof window !== 'undefined') window.whIsAuthFailure = whIsAuthFailure;

// The other half of that split: authenticated, and this particular thing is not yours to see.
function whIsAccessDenied(err) {
  if (!err) return false;
  var status = err.status != null ? String(err.status) : '';
  return status === '403' || String((err && err.code) || '') === '42501';
}
if (typeof window !== 'undefined') window.whIsAccessDenied = whIsAccessDenied;

// Raw Postgres shapes. These name a constraint or a table and mean nothing to the person reading them, so
// they stay behind the caller's friendlier fallback.
var _WH_RAW_PG = /violates .*constraint|duplicate key|syntax error|does not exist|out of range|invalid input value/i;

function whWriteError(err, fallback) {
  /* T45 (2026-08-27): bilingual, same argument as whAiError/whReadError. These four are the
     highest-stakes sentences in the taxonomy: every one answers "what happened to my work". */
  var T = (typeof window !== 'undefined' && typeof window._t === 'function')
    ? window._t : function (en) { return en; };
  if (whIsAuthFailure(err)) {
    return T('Your session expired, so nothing was saved. Sign in again and redo this step.',
             'Nag-expire ang session mo, kaya walang na-save. Mag-sign in ulit at ulitin ang hakbang na ito.');
  }
  // A 403 write is a refusal, not a dead session — but a DELIBERATE guard's own sentence is better
  // than any generic wording, so let those through below rather than answering them here. Only a
  // 403 with no human sentence behind it lands on this line.
  if (whIsAccessDenied(err) && !(err && err.message && String(err.message).length <= 300
                                 && !_WH_RAW_PG.test(String(err.message)))) {
    return T('You are not allowed to do that with this account, so nothing was saved. Your session is '
           + 'fine. Ask a supervisor if you need this.',
             'Hindi pinapayagan ang account mo na gawin iyon, kaya walang na-save. Ayos ang session '
           + 'mo. Magtanong sa supervisor kung kailangan mo ito.');
  }
  // A GUARD THAT TOOK THE TROUBLE TO EXPLAIN ITSELF MUST NOT BE REPLACED BY "TRY AGAIN". The reservation
  // guard says "Listing needs PHP50 credits held (10% of the price) and you have 0 available" — a seller
  // who instead reads "Save failed. Try again." will retry forever, because retrying is precisely what
  // cannot work. Deliberate refusals carry a policy errcode and a human sentence; anything Postgres-shaped
  // falls through to the caller's wording.
  var code = err && err.code != null ? String(err.code) : '';
  var msg  = err && err.message ? String(err.message) : '';
  var deliberate = code === '23514' || code === '42501' || code === 'P0001' || code === 'check_violation';
  if (deliberate && msg && msg.length <= 300 && !_WH_RAW_PG.test(msg)) return msg;
  /* A COLLISION IS PERMANENT, AND "TRY AGAIN" IS THE ONE ACTION THAT CANNOT WORK. 23505 is a unique
     violation - a name, tag, code or username already taken - so the caller's fallback ("The save did
     not go through. Nothing changed; try again.") sends the person to retype the same value forever.
     That is exactly the failure the note above describes for policy refusals, and it reaches real
     surfaces: asset_nodes is UNIQUE (hive_id, tag), so two "P-101"s collide on day one, and
     worker_profiles is UNIQUE (username), so a signup race lands here too. Measured before fixing:
     both returned the try-again fallback. The sentence stays GENERIC on purpose - the only clue to
     WHICH field collided is the constraint name, which is a schema word no reader should be shown
     ([[feedback_a_zero_that_was_never_a_fallback]] is the sibling lesson: do not dress a real
     condition as a generic one). Naming the cause and an action that CAN work beats both a Postgres
     string and a retry that is guaranteed to fail. */
  if (code === '23505' || /duplicate key value/i.test(msg)) {
    return T('Something here already uses that name or code, so nothing was saved. Change it to '
           + 'something different and save again.',
             'May gumagamit na ng pangalan o code na iyan, kaya walang na-save. Palitan ito ng iba '
           + 'at i-save muli.');
  }
  /* The caller's fallback is the PAGE's own English sentence, so it passes through untouched. */
  return fallback || T('That did not go through. Please try again.',
                       'Hindi natuloy iyon. Subukan muli.');
}
if (typeof window !== 'undefined') window.whWriteError = whWriteError;
// whReadError — the READ-side sibling of whWriteError, for a fetch that failed on the way IN.
// Three causes, three remedies, and until now most surfaces answered all three with one sentence:
//   401  clears by signing in           -- "check your connection" sends them to fix the wrong thing
//   429  clears by WAITING              -- "try again" is the one action that extends the limit
//   everything else is the connection   -- and only here is "try again" the right advice
// A public feed measured 2026-08-04 said "Couldn't load the public feed. Check your connection and try
// again." for all three; the marketplace and the seller profile had each grown their own inline copy of
// the taxonomy, which is the signal it belongs here. `what` names the thing that could not be read so the
// sentence stays specific ("the public feed", "your service requests").
/* whHiveContextLost(what) - THE FOURTH STATE (2026-08-31).
   This platform already models three answers to "why is there nothing here": the read FAILED
   (whReadError), the read is NOT BACK YET (alert-hub's `_anomalyCount = null` convention), and there is
   GENUINELY NOTHING (the empty states). The fourth was never named: the read SUCCEEDED and the server
   lawfully returned nothing because the viewer may not see it.

   It is invisible by construction. RLS refuses by FILTERING - a `USING` clause returns zero rows and no
   error - so a foreign or revoked hive arrives as an ordinary 200 with an empty array, byte-identical to
   an empty hive. Walked live 2026-08-31 as a removed member: alert-hub answered "All clear. No critical
   alerts, anomalies, or pending briefs for your hive right now", and inventory quietly fell back to a
   populated personal view advising "order them before the next shift planning". A safety claim and a
   restock instruction, both about a hive the platform could not see a single row of.

   pm-scheduler and inventory ALREADY detect this - validateHiveMembership() finds no row, clears the
   hive keys and drops to solo mode, which is a deliberate and defensible design ("inventory still usable
   for own items"). The defect was never the fallback; it was that the scope of everything on screen
   changed and the only announcement went to console.warn. This is that announcement.

   Kept beside whReadError on purpose: four surfaces need the same sentence, and four hand-written
   versions is how the platform's failure voice drifted before centralisation. */
function whHiveContextLost(what) {
  var thing = what || 'this hive';
  var T = (typeof window !== 'undefined' && typeof window._t === 'function')
    ? window._t : function (en) { return en; };
  var thingFil = String(thing).replace(/^the\s+/i, '');
  /* "Your session is fine" is the load-bearing half, exactly as in the access-denied branch above: the
     failure a person reaches for first is their own login, and sending them to re-authenticate over a
     membership change wastes their time and teaches them the message is noise. */
  return T('You are no longer a member of ' + thing + ', so its data is not shown. Your session is fine. '
         + 'Showing only what belongs to you. Ask a supervisor to add you back if this is wrong.',
           'Hindi ka na miyembro ng ' + thingFil + ', kaya hindi ipinapakita ang data nito. Ayos ang '
         + 'session mo. Ang iyong sarili lang ang ipinapakita. Magtanong sa supervisor kung mali ito.');
}
if (typeof window !== 'undefined') window.whHiveContextLost = whHiveContextLost;

/* whHiveContextNotice(hiveName) - SHOW the fourth state, in the region the platform already reserves for
   standing facts. Deliberately NOT a toast: utils.js:940 settled that argument for the sibling case -
   "A SESSION notice may ride a transient toast; a PERMISSION notice may not. The refusal is a standing
   fact about this page load, not a momentary event - a toast that fades leaves the person looking at the
   same unexplained dashes, which is the whole defect." Losing your hive is the same kind of fact: the
   scope of every number on screen has changed and stays changed.
   _whShowNotice is module-internal, so this wrapper is what pages call.
   KNOWN LIMIT, inherited on purpose rather than special-cased: the region self-expires after 30s. That
   timer exists for a measured reason (a pinned notice survived one failure injection and contaminated
   the next three probes on four pages), and giving this one notice a different lifetime would fork a
   mechanism whose behaviour is relied upon elsewhere. The scope change outlives the notice; if that
   proves too short in use, the fix belongs in _whShowNotice for every caller at once. */
function whHiveContextNotice(hiveName) {
  try {
    var name = hiveName ? ('the ' + String(hiveName).replace(/^the\s+/i, '')) : 'this hive';
    _whShowNotice('wh-hive-context-lost-notice', whHiveContextLost(name), '160px');
  } catch (e) { /* empty-catch-allow: a notice that cannot render must not break the load path */ }
}
if (typeof window !== 'undefined') window.whHiveContextNotice = whHiveContextNotice;

/* whHiveMembershipLost(db, hiveId, workerName) -> Promise<boolean>
   ASK the question that RLS answers silently. A revoked membership is invisible to a client: the reads
   come back 200 with zero rows, identical to a quiet hive, so a page can only tell the two apart by
   asking hive_members directly. pm-scheduler and inventory each grew their own copy of this probe;
   alert-hub and community had none, which is exactly why they answered "All clear" and "No activity
   yet" to a removed member. One copy, so the four surfaces cannot drift apart the way the failure voice
   did before whReadError centralised it.
   ★FAILS OPEN, deliberately: a DB error returns false. "I could not ask" is not "you were removed", and
   manufacturing a removal from an unreachable database would put a false accusation on screen during an
   ordinary outage - the same reasoning the two existing copies use when they trust the cached role. */
function whHiveMembershipLost(db, hiveId, workerName) {
  if (!db || !hiveId || !workerName) return Promise.resolve(false);
  try {
    // canonical-allow: auth-check probe on membership row presence; access gate, not a display read
    return db.from('hive_members')
      .select('status')
      .eq('hive_id', hiveId)
      .eq('worker_name', workerName)
      .maybeSingle()
      .then(function (r) {
        if (r && r.error) return false;                       // could not ask
        var m = r && r.data;
        return !m || m.status === 'kicked';
      }, function () { return false; });
  } catch (e) { return Promise.resolve(false); }
}
if (typeof window !== 'undefined') window.whHiveMembershipLost = whHiveMembershipLost;

function whReadError(err, what) {
  var thing = what || 'this';
  /* T45 (2026-08-27): the shared failure voice is bilingual; see whAiError. */
  var T = (typeof window !== 'undefined' && typeof window._t === 'function')
    ? window._t : function (en) { return en; };
  /* Filipino carries its own article, so the caller's English one has to come off or the
     sentence reads 'ang THE activity log'. Callers pass `thing` with the article attached
     ('the activity log') because the EN sentences need it; the FIL ones do not. */
  var thingFil = String(thing).replace(/^the\s+/i, '');

  var msg  = err && err.message ? String(err.message) : '';
  var hint = String((err && err.hint) || '') + ' ' + String((err && err.details) || '');
  var code = err && err.code != null ? String(err.code) : '';
  var st   = err && (err._httpStatus || err.status);
  if (whIsAuthFailure(err)) {
    // "Nothing you did was lost" belongs here, not only in the pages that happened to write it.
    // A person whose session dies mid-page cannot tell whether the thing they just tapped went
    // through; saying the session expired without answering that leaves them to guess, and the
    // guess is usually "do it again", which is how a duplicate gets created. This is a READ
    // failure, so the reassurance is simply true: nothing was being written.
    return T('Your session expired, so ' + thing + ' could not be loaded. Sign in again to see it. '
           + 'Nothing you did was lost.',
             'Nag-expire ang session mo, kaya hindi ma-load ang ' + thingFil + '. Mag-sign in ulit para '
           + 'makita ito. Walang nawala sa ginawa mo.');
  }
  // Authenticated, and refused. Naming the boundary is the whole point: "not visible with this
  // session" is a different fact from "nothing here", and neither of them is "sign in again".
  if (whIsAccessDenied(err)) {
    return T('You do not have access to ' + thing + ' with this account. Your session is fine. Ask a '
           + 'supervisor if you need it.',
             'Walang access ang account mo sa ' + thingFil + '. Ayos ang session mo. Magtanong sa '
           + 'supervisor kung kailangan mo ito.');
  }
  if (st === 429 || code === '429' || /rate ?limit|too many/i.test(msg)) {
    var secs = (msg + ' ' + hint).match(/(\d+)\s*(s|sec|secs|seconds?)\b/i);
    return T('Too many requests, so ' + thing + ' could not be loaded. Try again in '
           + (secs ? secs[1] + ' seconds' : 'a moment') + '.',
             'Masyadong maraming request, kaya hindi ma-load ang ' + thingFil + '. Subukan muli sa '
           + (secs ? secs[1] + ' segundo' : 'ilang sandali') + '.');
  }
  // T71 (2026-08-26): the connection fallback now answers "is it me or them?" - every failure
  // state pointed nowhere, so a plant-wide outage read exactly like bad plant wifi. The Status
  // page is static-first (loads when the DB cannot), which is what makes the pointer honest.
  return T('Couldn’t load ' + thing + '. Check your connection and try again. Still failing on good '
       + 'internet? Open status.html - it shows if WorkHive itself is having trouble.',
           'Hindi ma-load ang ' + thingFil + '. Suriin ang koneksyon at subukan muli. Hindi pa rin '
         + 'gumagana kahit maayos ang internet? Buksan ang status.html - ipinapakita nito kung '
         + 'may problema ang WorkHive mismo.');
}
if (typeof window !== 'undefined') window.whReadError = whReadError;
// whQueryTimeout — an upper bound for a supabase-js READ, so a hung request cannot become an eternal
// skeleton. fetchWithTimeout bounds raw fetches, but a PostgREST query builder never passes through it,
// so a stalled read just... stays stalled, and the page keeps shimmering at someone who has already
// decided it is broken. Measured 2026-08-04 on the public feed: request held open, stuckSkeleton true,
// saysSomething FALSE -- indefinitely.
// Resolves to supabase-js's own {data, error} shape so no caller needs a new branch; the synthetic error
// carries code 'TIMEOUT' and reads as a connection problem through whReadError, which is what it is.
// Reads only. A timed-out WRITE has not necessarily failed -- it may well have landed -- and telling
// someone it did not is worse than saying nothing.
function whQueryTimeout(query, ms, what) {
  var budget = (typeof ms === 'number' && ms > 0) ? ms : 15000;
  var timer;
  return Promise.race([
    Promise.resolve(query),
    new Promise(function (resolve) {
      timer = setTimeout(function () {
        resolve({ data: null, error: { code: 'TIMEOUT', message: 'Timed out loading ' + (what || 'this') } });
      }, budget);
    })
  ]).then(function (r) { clearTimeout(timer); return r; });
}
if (typeof window !== 'undefined') window.whQueryTimeout = whQueryTimeout;
// Central refresh-retry dedup guard (deepwalk D2, 2026-07-22). A NON-idempotent client write (a fresh-id
// insert or a decrement RPC) carries no idempotency key, so a refresh-mid-submit then retry creates a
// DUPLICATE / double effect (live-confirmed: logbook dup entry; inventory double stock deduction). The
// FIRST write already landed server-side, so a pre-write check catches the retry: query for an identical
// row created within `windowMs`. Pass the table, an equality-match object (null values skipped), and opts
// {windowMs (default 30000), tsColumn (default 'created_at')}. Returns the recent row's id, or null.
// Best-effort: returns null on any query error (falls through to the write). Keep the match SPECIFIC +
// the window TIGHT so a legitimate rapid second write is not false-blocked.
async function whRecentDuplicate(db, table, match, opts) {
  opts = opts || {};
  try {
    if (!db || !table || !match) return null;
    var since = new Date(Date.now() - (opts.windowMs || 30000)).toISOString();
    var q = db.from(table).select('id').gte(opts.tsColumn || 'created_at', since).limit(1);
    for (var k in match) { if (Object.prototype.hasOwnProperty.call(match, k) && match[k] != null) q = q.eq(k, match[k]); }
    var res = await q;
    return (res && res.data && res.data.length) ? res.data[0].id : null;
  } catch (_) { return null; /* best-effort: never block a write on a dedup query failure */ }
}
if (typeof window !== 'undefined') window.whRecentDuplicate = whRecentDuplicate;
// whRememberView — the SHARED system-memory (rubric G5) helper. Persists + restores a per-page VIEW state
// (filter / sort / tab / active-view) to localStorage so a user's choice survives across sessions, instead of
// 14 pages hand-rolling it (they drift → the measured 17.6% G5a floor). CENTRALIZE-FIRST. Adopt after the
// list first renders:
//   var view = whRememberView('filters', function () { return { cat: catEl.value, sort: sortEl.value }; });
//   view.restore(function (s) { catEl.value = s.cat; sortEl.value = s.sort; applyFilters(); });  // apply saved
//   [catEl, sortEl].forEach(function (el) { el.addEventListener('change', view.save); });          // persist
// whClockSkew — T150 (2026-08-26): tell a person their DEVICE CLOCK is wrong, before it
// corrupts records. 47 `*_at` fields across a dozen pages are written from the BROWSER's clock
// (approved_at, acknowledged_at, resolved_at, acted_at…), so a phone half an hour fast files an
// approval half an hour in the future, and "5m ago" lies on every surface. Wrong device time is
// common on cheap Android handsets after a battery pull — this is a field reality, not an edge.
// The server's own `Date` response header is a free, exact reference on every request: no RPC,
// no round-trip of our own, no dependency on a table. Warn only (never auto-correct: silently
// rewriting a user's timestamps would be its own lie), once per page, past a 3-minute tolerance
// that comfortably clears normal latency and NTP jitter.
function whClockSkew(opts) {
  opts = opts || {};
  var tolMs = opts.toleranceMs || 180000;   // 3 minutes
  try {
    if (window._whClockSkewChecked) return;
    window._whClockSkewChecked = true;
    var base = window.WH_SUPABASE_URL || '';
    if (!base) return;
    var t0 = Date.now();
    // Read the server date from the SITE's OWN ORIGIN (200 + a Date header, no auth) rather than the
    // Supabase REST root, which 401s for an unauthenticated ping — that logged "Failed to load
    // resource: 401" to the console on EVERY page load for every visitor (caught by the prod
    // post-deploy smoke, 2026-09-04; a first fix that added the anon apikey did NOT work because the
    // publishable key is not accepted as a bare apikey on the PostgREST root). Any trusted server's
    // clock answers "is THIS DEVICE's clock off?"; the origin needs no key and never 401s.
    fetch(location.origin + '/?_clk=' + t0, { method: 'HEAD', cache: 'no-store' }).then(function (res) {
      var hdr = res && res.headers && res.headers.get('date');
      if (!hdr) return;
      var serverMs = new Date(hdr).getTime();
      if (!isFinite(serverMs)) return;
      // Compare against the MIDPOINT of our own request window, so the round trip itself
      // cannot masquerade as skew (the header is stamped somewhere inside that window).
      var mid = t0 + (Date.now() - t0) / 2;
      var deltaMs = mid - serverMs;
      window._whClockDeltaMs = deltaMs;
      if (Math.abs(deltaMs) < tolMs) return;
      var mins = Math.round(Math.abs(deltaMs) / 60000);
      var fast = deltaMs > 0;
      var d = document.createElement('div');
      d.id = 'wh-clock-skew';
      d.setAttribute('role', 'alert');
      d.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:2147483000;'
        + 'background:#7c2d12;color:#fff;padding:10px 14px;font:12px/1.45 system-ui,Arial,sans-serif;text-align:center;';
      d.textContent = 'This device’s clock is about ' + mins + ' minute' + (mins === 1 ? '' : 's') + ' '
        + (fast ? 'ahead of' : 'behind') + ' real time. Times you see (and times recorded when you approve '
        + 'or complete work) will be off by that much until you fix the date and time in your device settings.';
      if (document.body) document.body.appendChild(d);
    }, function () { /* offline or blocked: no reading, so no claim */ });
  } catch (_) { /* empty-catch-allow: a clock check must never break a page */ }
}
if (typeof window !== 'undefined') {
  window.whClockSkew = whClockSkew;
  // Run once per page, after load so it never competes with first paint.
  if (typeof document !== 'undefined') {
    if (document.readyState === 'complete') setTimeout(whClockSkew, 1500);
    else window.addEventListener('load', function () { setTimeout(whClockSkew, 1500); });
  }
}
// whFold — T128 (2026-08-26): diacritic-insensitive search folding, one definition.
// Philippine names and place names carry diacritics constantly (Peña, Muñoz, Dueñas, Bataán),
// and every client-side search on the platform was a plain lowercase substring test — so a
// technician typing "Pena", which is what a plant keyboard and a hurried thumb actually produce,
// found NOTHING while the record sat right there. NFD splits a letter from its combining mark and
// the range strip removes the marks, so "Peña" and "Pena" fold to the same key. Case-folding rides
// along, so callers replace toLowerCase() with this rather than stacking both.
// Search-only: never fold stored VALUES, only the comparison keys — the record keeps the real name.
function whFold(s) {
  try {
    return String(s == null ? '' : s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  } catch (_) {
    return String(s == null ? '' : s).toLowerCase();   // engines without NFD still get case-folding
  }
}
if (typeof window !== 'undefined') window.whFold = whFold;
/* T51 (2026-08-27): WHICH HIVE this remembered state belongs to. Reuses whHiveId(), the
   canonical accessor with the registered-alias fallback chain (wh_active_hive_id, then
   wh_hive_id), rather than a fourth hand-rolled localStorage read. Returns '' rather than null
   so a blocked-storage save and a blocked-storage restore compare equal instead of both being
   null-ish in different ways. */
function _stateHive() {
  try { return String((typeof whHiveId === 'function' ? whHiveId() : null) || ''); }
  catch (_) { return ''; }
}
/* WHOSE remembered state this is (T121, 2026-08-28). The same three-line read had been
   hand-rolled FOUR times by the time this landed - _fOwner (filters), _draftOwner (drafts),
   _anOwner (analytics), _historyOwner (companion) - each a separate chance to drift. One
   accessor now, and a place for the next store to reach for instead of writing a fifth. */
function whStateOwner() {
  try { return String(localStorage.getItem('wh_last_worker') || localStorage.getItem('wh_worker_name') || ''); }
  catch (_) { return ''; }
}
if (typeof window !== 'undefined') window.whStateOwner = whStateOwner;
/* ★A DISMISSAL IS PERSON-SCOPED, AND STORING '1' MADE IT DEVICE-WIDE (T121, 2026-08-28).
   The draft/filter/history leaks all ran one direction - A's CONTENT reaching B. Dismissal flags
   leak the OTHER way and are easy to miss for exactly that reason: nothing of A's is exposed, so
   it does not read as a privacy bug. What crosses is A's DECISION. Worker A taps Dismiss on the
   first-run onboarding ladder, signs out, and worker B - whose three steps are all incomplete,
   and whose progress the card computes correctly - never sees the card at all, because the flag
   belongs to the browser. The platform's promise that every page introduces itself is silently
   void for the second person to use a station tablet, which on this platform is most of them.
   Storing the OWNER instead of '1' fixes it in the same shape as its siblings: A stays dismissed,
   B gets introduced. Legacy '1' values carry no owner and so re-show the guide once - the safe
   direction for help, exactly as unowned history is not restored. */
function whIsDismissed(key) {
  try {
    var v = localStorage.getItem(key);
    if (!v) return false;
    if (v === '1') return false;             // legacy, unowned -> not a dismissal by THIS person
    return v === ('u:' + whStateOwner());
  } catch (_) { return false; }
}
function whSetDismissed(key) {
  try { localStorage.setItem(key, 'u:' + whStateOwner()); }
  catch (_) { /* empty-catch-allow: dismissal is best-effort; a blocked store just re-shows the guide */ }
}
if (typeof window !== 'undefined') { window.whIsDismissed = whIsDismissed; window.whSetDismissed = whSetDismissed; }
function whRememberView(key, capture) {
  var K = 'wh_view_' + (typeof location !== 'undefined' ? (location.pathname.split('/').pop() || 'root') : 'root') + '_' + key;
  return {
    key: K,
    restore: function (apply) { try { var s = JSON.parse(localStorage.getItem(K) || 'null'); if (s != null && typeof apply === 'function') apply(s); return s; } catch (_) { return null; } },
    save: function () { try { localStorage.setItem(K, JSON.stringify(capture())); } catch (_) { /* empty-catch-allow: best-effort persist, never block the UI on a localStorage failure (quota/private-mode) */ } },
    clear: function () { try { localStorage.removeItem(K); } catch (_) { /* empty-catch-allow: best-effort clear, localStorage may be unavailable (quota/private-mode) */ } }
  };
}
if (typeof window !== 'undefined') window.whRememberView = whRememberView;
// whAutoRememberFilters — ONE-LINE G5a adoption for pages whose filters are standard <input>/<select> elements.
// Restores each element's last value from localStorage (dispatching a change so the page's OWN filter→render
// re-applies it — no need to know the page's render fn), and persists on change. Call it once after the filter
// inputs + their listeners exist:  whAutoRememberFilters('filters', ['search-input','cat-filter','filter-status']);
// (chip/tab filters that aren't form elements still wire whRememberView by hand.)
function whAutoRememberFilters(key, ids) {
  try {
    if (typeof document === 'undefined') return null;
    /* T121 (2026-08-26): filters are OWNED too, for the same shared-device reason as drafts and
       for a plainer one: on the station tablet, worker B inherited whatever A had filtered to and
       met a list that looked empty or wrong with no explanation. A filter also leaks intent (a
       supervisor filtered to one person's name). Stamp the owner; restore only your own. */
    var _fOwner = function () {
      try { return String(localStorage.getItem('wh_last_worker') || localStorage.getItem('wh_worker_name') || ''); }
      catch (_) { return ''; }
    };
    var view = whRememberView(key, function () { var o = { __owner: _fOwner(), __hive: _stateHive() }; ids.forEach(function (id) { var el = document.getElementById(id); if (el) o[id] = el.value; }); return o; });
    view.restore(function (s) { if (!s || !s.__owner || s.__owner !== _fOwner()) return;
    /* T51: a filter belonging to ANOTHER hive matches nothing on this one, and the page
       renders that as an empty list - which this platform has taught people to read as
       "there is nothing here" rather than "your filter is from another plant". */
    if (s.__hive !== _stateHive()) return;
    ids.forEach(function (id) { var el = document.getElementById(id); if (el && s[id] != null && s[id] !== '' && !el.value) { el.value = s[id]; el.dispatchEvent(new Event('change', { bubbles: true })); } }); });
    ids.forEach(function (id) { var el = document.getElementById(id); if (el) ['change', 'input'].forEach(function (ev) { el.addEventListener(ev, view.save); }); });
    return view;
  } catch (_) { return null; }
}
if (typeof window !== 'undefined') window.whAutoRememberFilters = whAutoRememberFilters;
// whAutoRememberTabs — the CHIP/TAB variant of the G5a auto-adopter for filters that are buttons (not inputs):
// a container of `[data-<attr>]` chips (data-status / data-tab / data-kind) where the active one has .active or
// aria-pressed/selected. Restores the last-active chip by CLICKING it (reusing the page's own switch handler),
// and persists on chip click. Call once after the chips + their listeners exist:
//   whAutoRememberTabs('seller-status', '#listing-filter', 'data-status');
function whAutoRememberTabs(key, containerSel, dataAttr) {
  try {
    if (typeof document === 'undefined') return null;
    dataAttr = dataAttr || 'data-status';
    var cont = document.querySelector(containerSel);
    if (!cont) return null;
    var activeVal = function () { var a = cont.querySelector('.active,[aria-pressed="true"],[aria-selected="true"]'); return a ? a.getAttribute(dataAttr) : null; };
    var view = whRememberView(key, function () { return { v: activeVal() }; });
    cont.addEventListener('click', function (e) { if (e.target && e.target.closest && e.target.closest('[' + dataAttr + ']')) setTimeout(view.save, 0); });
    view.restore(function (s) {
      if (!s || !s.v) return;
      var first = cont.querySelector('[' + dataAttr + ']');
      var cur = cont.querySelector('.active,[aria-pressed="true"],[aria-selected="true"]');
      if (cur && first && cur !== first) return;   // an explicit non-default (e.g. URL) selection WINS — don't override
      var b = cont.querySelector('[' + dataAttr + '="' + (window.CSS && CSS.escape ? CSS.escape(s.v) : s.v) + '"]');
      if (b && b !== cur) b.click();
    });
    return view;
  } catch (_) { return null; }
}
if (typeof window !== 'undefined') window.whAutoRememberTabs = whAutoRememberTabs;
// whAutoSaveDraft — X2 interruption resilience: autosave an ENTRY FORM's fields as a DRAFT to localStorage so a
// refresh / interruption (a field-tech's connectivity blip, a phone call) doesn't lose in-progress work. Restores
// the draft into EMPTY fields on load, debounced-saves on input, and `.clear()` wipes it — call clear() after a
// SUCCESSFUL submit so the next entry starts fresh. Usage:
//   var draft = whAutoSaveDraft('logentry', ['log-notes','log-hours']);  ... onSaved: draft.clear();
function whAutoSaveDraft(key, ids, opts) {
  try {
    if (typeof document === 'undefined') return { save: function () {}, clear: function () {} };
    opts = opts || {};
    var t = null;
    var view, applyDraft;
    // Debounced single-timer save + one-shot clear, HOISTED into named fns so the setTimeout calls sit OUTSIDE
    // any forEach — they fire on user events, not per-iteration (keeps the timeout_in_loop 4-line-lookback gate green).
    function scheduleSave() { clearTimeout(t); t = setTimeout(view.save, opts.debounce || 500); }
    function scheduleClear(ms) { setTimeout(view.clear, ms); }
    /* T121 (2026-08-26): DRAFTS MUST BE OWNED. Measured on a shared device (the plant reality
       this platform is built for - one tablet at the station, workers signing in and out): worker
       A typed a private note, signed OUT, worker B signed IN, opened the same page, focused the
       field - and A's words were sitting in B's compose box. B could submit them under their own
       name. The registry called this a devtools-level exposure; it is plainer than that, and the
       fix is not purge-on-sign-out (which destroys real work) but OWNERSHIP: stamp the draft with
       whoever typed it, and refuse to restore one that belongs to somebody else. A's draft is
       preserved and comes back for A; B never sees it. Legacy drafts carry no owner and are
       therefore not restored - a one-time cost, and the safe direction. */
    var _draftOwner = function () {
      try { return String(localStorage.getItem('wh_last_worker') || localStorage.getItem('wh_worker_name') || ''); }
      catch (_) { return ''; }
    };
    view = whRememberView('draft_' + key, function () {
      /* T57 (2026-08-26): stamp WHEN. A draft carried an owner but no age, so one typed three
         months ago restored into the form exactly like one typed three minutes ago - silently,
         into fields the worker is about to submit. On a logbook entry that means filing a stale
         reading against today's shift without ever being told the text was old. */
      var o = { __owner: _draftOwner(), __hive: _stateHive(), __savedAt: Date.now() };
      ids.forEach(function (id) { var el = document.getElementById(id); if (el) o[id] = el.value; });
      return o;
    });
    // A SELECT IS NEVER "EMPTY", so `!el.value` skipped every one of them. Measured 2026-08-04 on the
    // service hail: the chosen service and the typed address came back after an interruption and the
    // urgency did NOT -- "Critical - production is down" silently reverted to "Normal - within a few
    // days", which is the difference between a provider coming now and coming next week. A select
    // always has a value, so the guard has to ask the equivalent question: is it still at its DEFAULT?
    // (the option carrying the `selected` attribute, else the first one). That preserves what the
    // guard is for -- never overwrite a choice the person has already made -- while letting a draft
    // restore into an untouched dropdown.
    var _isUntouched = function (el) {
      if (el.tagName !== 'SELECT') return !el.value;
      var def = el.querySelector('option[selected]') || el.options[0];
      return !def || el.value === def.value;
    };
    /* T120 (2026-08-26): SAY WHERE DRAFTS LIVE. The account-vs-device split is deliberate and
       documented (substrate/reference/state_scope_registry.json), but nothing said it in-app: a
       worker who starts a note on the phone and opens the PC finds an empty box and reasonably
       concludes their work was lost. Drafts are DEVICE-local by design (they must survive an
       offline session, which an account-level sync cannot promise). Announce it ONCE per browser,
       and only when a draft actually comes back - so it lands as an explanation at the moment it
       explains something, never as a nag. */
    /* T57: an OLD draft announces its age. Recent ones stay silent - a note from ten minutes ago
       coming back is the feature working, and narrating it would be noise. The threshold is days
       rather than hours because interruption resilience (X2) is measured in minutes and hours; a
       draft that survives a WEEK is no longer an interruption, it is a leftover. Says the age
       instead of discarding the text, because the work is still the worker's to keep or clear. */
    var _DRAFT_OLD_MS = 7 * 24 * 60 * 60 * 1000;
    var _announceAgeIfOld = function (savedAt) {
      try {
        var ms = Date.now() - Number(savedAt || 0);
        if (!isFinite(ms) || !savedAt || ms < _DRAFT_OLD_MS) return;
        var days = Math.floor(ms / 86400000);
        if (typeof showToast === 'function') {
          showToast('This draft is ' + days + ' days old. Check it still matches today before you save.',
                    'info');
        }
      } catch (_) { /* empty-catch-allow: an age notice must never block a restore */ }
    };

    var _announceScope = function () {
      try {
        if (localStorage.getItem('wh_draft_scope_told') === '1') return;
        localStorage.setItem('wh_draft_scope_told', '1');
        if (typeof showToast === 'function') {
          showToast('Draft restored. Drafts live on the device you typed them on, so this one will not appear on your other devices.', 7000);
        }
      } catch (_) { /* empty-catch-allow: the notice is an explanation, never a blocker */ }
    };
    applyDraft = function (s) { var _any = false;
      // refuse a draft that belongs to someone else, and legacy drafts whose owner is unknown
      if (!s || !s.__owner || s.__owner !== _draftOwner()) return;
      /* T51 (2026-08-27): AND THE SAME HIVE. The owner check passes for a multi-hive worker in
         BOTH their hives - they are the same person - so a note typed against hive A restored
         into hive B's form, carrying one plant's machine names into another plant's record.
         Legacy drafts carry no __hive and are therefore not restored, the same one-time cost
         and the same safe direction the owner stamp chose. */
      if (s.__hive !== _stateHive()) return;
      _announceAgeIfOld(s.__savedAt);
      ids.forEach(function (id) { var el = document.getElementById(id); if (el && s[id] != null && s[id] !== '' && _isUntouched(el)) { el.value = s[id]; el.dispatchEvent(new Event(el.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true })); _any = true; } }); if (_any) _announceScope(); };
    view.restore(applyDraft);
    ids.forEach(function (id) { var el = document.getElementById(id); if (el) ['input', 'change'].forEach(function (ev) { el.addEventListener(ev, scheduleSave); }); });
    // GENERIC lifecycle (no per-page selectors needed): restore the draft when the user FOCUSES the compose
    // (handles a modal whose open() blanks the field — the draft comes back as they enter it), and CLEAR it
    // when a submit-like button in the field's dialog/form/sheet is clicked (the entry committed → next is fresh).
    if (opts.auto !== false) {
      ids.forEach(function (id) {
        var el = document.getElementById(id); if (!el) return;
        el.addEventListener('focus', function () { view.restore(applyDraft); });
        var box = (el.closest && el.closest('[role="dialog"],.modal,.sheet,form')) || document.body;
        box.addEventListener('click', function (e) { var b = e.target && e.target.closest && e.target.closest('button,[type="submit"]'); if (b && /\b(post|save|submit|send|publish|update|create|\blog\b|\badd\b|done|confirm)\b/i.test((b.textContent || '') + ' ' + (b.id || ''))) scheduleClear(220); });
      });
    }
    // opts.clearOn = a selector for the SUBMIT/SAVE control; clicking it wipes the draft (the entry committed).
    // opts.restoreOn = a selector for the OPEN/compose trigger; clicking it re-restores the draft into the
    // (freshly-opened, now-empty) form — the one-call answer for MODAL composers whose open() blanks the field.
    if (opts.clearOn) { document.addEventListener('click', function (e) { if (e.target && e.target.closest && e.target.closest(opts.clearOn)) scheduleClear(120); }, true); }
    if (opts.restoreOn) { document.addEventListener('click', function (e) { if (e.target && e.target.closest && e.target.closest(opts.restoreOn)) setTimeout(function () { view.restore(applyDraft); }, 60); }); }
    return { save: view.save, clear: view.clear, restore: function () { view.restore(applyDraft); }, key: view.key };
  } catch (_) { return { save: function () {}, clear: function () {} }; }
}
if (typeof window !== 'undefined') window.whAutoSaveDraft = whAutoSaveDraft;
function whFmtDate(d, opts) {
  var dt = (d instanceof Date) ? d : new Date(d);
  if (isNaN(dt.getTime())) return '-';
  opts = opts || {};
  var fmt = { year: 'numeric', month: opts.long ? 'long' : 'short', day: 'numeric', timeZone: 'Asia/Manila' };
  if (opts.year === false) delete fmt.year; // compact variant: same-week/shift contexts where the year is noise
  if (opts.weekday) fmt.weekday = opts.weekday; // 'short' | 'long'
  if (opts.time) { fmt.hour = '2-digit'; fmt.minute = '2-digit'; }
  if (opts.timeOnly) fmt = { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Manila' }; // clock-only variant
  if (opts.hour12 != null) fmt.hour12 = opts.hour12;
  return dt.toLocaleString('en-PH', fmt);
}
function whFmtDuration(value, unit) {
  var v = Number(value);
  if (!isFinite(v)) return '-';
  unit = unit || 'days';
  var singular = (Math.abs(v) === 1) ? unit.replace(/s$/, '') : unit;
  return whFmtNum(v) + ' ' + singular;
}
// whFmtAgo — canonical relative time ("just now" / Nm / Nh / Nd ago). Lifted 2026-07-17
// from 8 byte-equivalent page-local copies (hive/marketplace×4/audit-log/achievements/
// agentic-rag/alert-hub/asset-hub timeAgo·whenAgo·fmtRelative) — FULLSTACK_COMPONENT_LIBRARY
// FD1e. Page locals now DELEGATE here; keep their names, one source of truth for the math.
function whFmtAgo(d) {
  var dt = (d instanceof Date) ? d : new Date(d);
  if (!d || isNaN(dt.getTime())) return '';
  var s = (Date.now() - dt.getTime()) / 1000;
  if (s < 60) return 'just now';
  if (s < 3600) return Math.floor(s / 60) + 'm ago';
  if (s < 86400) return Math.floor(s / 3600) + 'h ago';
  return Math.floor(s / 86400) + 'd ago';
}
if (typeof window !== 'undefined') {
  window.whFmtPeso = whFmtPeso; window.whFmtNum = whFmtNum;
  window.whFmtDate = whFmtDate; window.whFmtDuration = whFmtDuration;
  window.whFmtAgo = whFmtAgo;
}

// ─────────────────────────────────────────────
// whHiveId() / whWorker() — canonical client-identity accessors (PLATFORM_CENTRALIZATION C-P4)
// ─────────────────────────────────────────────
// storage_key_registry.json found drift: the active hive id is read as wh_active_hive_id
// (canonical) OR wh_hive_id / hive_id (aliases), and the worker as wh_last_worker (canonical)
// OR workerName / wh_worker_name (aliases) — across ~144 raw getItem sites that disagree on
// which key to read. These accessors read the CANONICAL key first, then fall back to each
// registered alias, so a page written before convergence still resolves. Adopt ONE accessor
// platform-wide instead of hand-repeating the fallback chain (the design-system lever).
function whHiveId() {
  try {
    return localStorage.getItem('wh_active_hive_id') // canonical
        || localStorage.getItem('wh_hive_id')        // live alias (still written on hive-switch)
        || null;
  } catch (_) { return null; /* storage blocked (private mode / disabled) */ }
}
// whReconcileHiveName — T140 (2026-08-26): a rename must reach the OTHER devices.
//
// MEASURED, and it corrected this trajectory's own record. T140's basis read that hive rename "does
// not exist - no UI, no update path", and concluded that no stale-name class could exist. Both
// halves were wrong: hive.html:2661 renames a hive, and a live test showed the consequence - after
// another device renames the plant, this one keeps showing the OLD name on its board and in its
// chrome, because every page trusts localStorage.wh_hive_name and nothing re-reads hives.name.
// wh_hive_name is written at join/switch time, so "eventually" can mean weeks.
//
// The rename handler already propagates well LOCALLY (HIVE_NAME, localStorage, the hive list, the
// board title, the switch button). What it cannot do is reach a session it is not running in. So
// each page reconciles once on load: ask the server what this hive is called, and if the cached
// name disagrees, correct the cache and repaint anything showing it.
//
// ★ONE CHEAP READ, AND ONLY WHEN IT CAN HELP. It runs once per page load, only with a hive id and a
// cached name present, and it is entirely best-effort: a page whose read fails keeps the cached
// name, which is exactly what it would have shown anyway. It must never be the reason a page fails.
async function whReconcileHiveName(db) {
  try {
    var id = whHiveId();
    if (!id || typeof db !== 'object' || !db) return null;
    var cached = null;
    try { cached = localStorage.getItem('wh_hive_name'); } catch (_) { return null; }
    if (!cached) return null;
    // Canonical source, not the base table: v_hives_truth is the registered truth view for hive
    // identity, and reading `hives` directly is exactly the drift validate_canonical_sources
    // exists to catch. Verified live as the signed-in user - same id, same name.
    var res = await db.from('v_hives_truth').select('name').eq('id', id).maybeSingle();
    var live = res && res.data && res.data.name;
    if (!live || live === cached) return null;
    try {
      localStorage.setItem('wh_hive_name', live);
      // `wh_hives` is the switcher's list - written by saveHiveList() in hive.html, read there and
      // on index and analytics. This repaint first wrote `wh_hive_list`, a key nothing reads, so a
      // renamed hive updated the chrome and left the switcher showing the old name: the stale cache
      // this function exists to reconcile, surviving inside the reconciler. The storage-key registry
      // caught it as an UNKNOWN key, which is what a one-vocabulary rule is for.
      var list = JSON.parse(localStorage.getItem('wh_hives') || '[]');
      if (Array.isArray(list)) {
        localStorage.setItem('wh_hives', JSON.stringify(
          list.map(function (h) { return (h && h.id === id) ? Object.assign({}, h, { name: live }) : h; })));
      }
    } catch (_) { /* empty-catch-allow: storage may be blocked; the repaint below still helps */ }
    // repaint the places a hive name is shown, by id and by the data-attribute chrome uses
    var el = document.getElementById('board-hive-name');
    if (el) el.textContent = live;
    document.querySelectorAll('[data-wh-hive-name]').forEach(function (n) { n.textContent = live; });
    return { was: cached, now: live };
  } catch (_) { return null; /* a rename check must never break a page */ }
}
if (typeof window !== 'undefined') window.whReconcileHiveName = whReconcileHiveName;

// ── whEmbedEntry — the RAG index write that retries instead of vanishing (T10 AI4, 2026-09-02) ──
// Walked live: embed-entry returned 500 on a PM save's logbook echo and the new entry was SILENTLY
// missing from the RAG index — console-only, no retry, nothing surfaced (the write-only-index
// class: the assistant's recall quietly loses exactly the entries saved during a bad minute).
// Contract: one immediate retry after 2s; on second failure the payload is PERSISTED
// (wh_embed_retry, capped 20, oldest dropped) and re-sent on a later page load once the client is
// up. Embedding is idempotent server-side (upsert by entry id), so a duplicate drain is safe.
// Fire-and-forget stays the calling contract — this must never block a save.
async function whEmbedEntry(payload, opts) {
  var o = opts || {};
  var url = (o.url || (typeof SUPABASE_URL !== 'undefined' ? SUPABASE_URL : '')) + '/functions/v1/embed-entry';
  var key = o.key || (typeof SUPABASE_KEY !== 'undefined' ? SUPABASE_KEY : '');
  var tok = o.token || key;
  var send = function () {
    // the fallback's fetch rides send()'s own try/retry (below); the inline try satisfies the
    // line-scoped fetch-error ratchet without altering the rejection path
    var f = (typeof fetchWithTimeout === 'function') ? fetchWithTimeout : function (u, x) { try { return fetch(u, x); } catch (e) { return Promise.reject(e); } };
    return f(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'apikey': key, 'Authorization': 'Bearer ' + tok },
      body: JSON.stringify(payload),
    }, 8000).then(function (r) { if (!r || !r.ok) throw new Error('embed-entry ' + (r ? r.status : 'null')); return r; });
  };
  try { return await send(); }
  catch (e1) {
    await new Promise(function (r) { setTimeout(r, 2000); });
    try { return await send(); }
    catch (e2) {
      try {
        var q = JSON.parse(localStorage.getItem('wh_embed_retry') || '[]');
        q.push({ payload: payload, at: Date.now() });
        while (q.length > 20) q.shift();
        localStorage.setItem('wh_embed_retry', JSON.stringify(q));
        console.warn('[whEmbedEntry] queued for retry after 2 failures:', e2 && e2.message);
      } catch (_) { /* empty-catch-allow: storage blocked -> the entry stays unindexed, as before */ }
      return null;
    }
  }
}
if (typeof window !== 'undefined') {
  window.whEmbedEntry = whEmbedEntry;
  // Drain the persisted retry queue once the page's client/keys exist (same lazy pattern as the
  // hive-name reconciler). Items older than 7 days are dropped — a week-old index miss is better
  // re-created by a fresh save than replayed blind.
  (function _whDrainEmbedQueue() {
    var tries = 0;
    function attempt() {
      tries++;
      try {
        var q = JSON.parse(localStorage.getItem('wh_embed_retry') || '[]');
        if (!q.length) return;
        if (typeof SUPABASE_URL !== 'undefined' && typeof SUPABASE_KEY !== 'undefined') {
          localStorage.setItem('wh_embed_retry', '[]');
          q.filter(function (it) { return (Date.now() - (it.at || 0)) < 7 * 86400000; })
           .forEach(function (it) { whEmbedEntry(it.payload); });
          return;
        }
      } catch (_) { /* empty-catch-allow: storage blocked -> nothing to drain */ return; }
      if (tries < 8) rescheduleAttempt();
    }
    // Hoisted so the setTimeout sits OUTSIDE any loop's lookback window (the timeout_in_loop
    // gate's documented pattern): this is a bounded RETRY CHAIN (one timer at a time), and the
    // .forEach four lines up made it read as N-timers-in-a-loop.
    function rescheduleAttempt() { setTimeout(attempt, 1500); }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { setTimeout(attempt, 1200); });
    else setTimeout(attempt, 1200);
  })();
}

// ── whModalHistory — hardware Back closes the modal, not the page (T42, 2026-09-02) ─────────────
// Walked live at 390: opening inventory's Add-Part modal pushed NO history entry, so the phone's
// Back gesture (a constant on Android) NAVIGATED AWAY from the whole page — a worker mid-form lost
// the task and their input with one natural gesture; no page on the platform wired Back to modal
// state. The contract: a modal calls .opened(closeFn) when it shows (pushes one history entry) and
// .closed() when dismissed by its own controls (consumes that entry via history.back()); the
// popstate listener closes the top modal instead of leaving the page. Back with no modal open
// behaves exactly as before. Re-entrancy safe: the explicit-close path pops the stack BEFORE
// calling history.back(), so the resulting popstate finds nothing to close.
(function () {
  if (typeof window === 'undefined') return;
  var _stack = [];
  window.whModalHistory = {
    opened: function (closeFn) {
      if (typeof closeFn !== 'function') return;
      _stack.push(closeFn);
      try { history.pushState({ whModal: _stack.length }, ''); } catch (_) { /* empty-catch-allow: history may be sandboxed; Back then simply leaves as before */ }
    },
    closed: function () {
      if (!_stack.length) return;           // popstate path already consumed it (or never opened)
      _stack.pop();
      try { history.back(); } catch (_) { /* empty-catch-allow: worst case a spare entry remains */ }
    },
  };
  window.addEventListener('popstate', function () {
    var fn = _stack.pop();
    if (fn) { try { fn(); } catch (_) { /* empty-catch-allow: a broken closeFn must not break Back */ } }
  });
})();
// ── C11 AUTO-WIRE (critic deepwalk, 2026-09-02): BUILT-BUT-BARELY-CALLED, closed. ─────────────
// whReconcileHiveName existed and worked, but only hive.html ever called it — every OTHER page
// still trusted localStorage.wh_hive_name blindly, which is exactly how the walked receipt
// happened (Bryan saw 'Lucena Pharmaceutical' chrome over his own correctly-scoped Baguio data
// after a shared-device divergence). Rather than 23 per-page call sites, utils wires it ONCE:
// after load, when the page's own getDb() singleton exists, reconcile — same best-effort
// contract (a failed read changes nothing; it must never be the reason a page breaks). The
// short retry loop covers pages that create the client a beat after DOMContentLoaded.
if (typeof window !== 'undefined' && typeof document !== 'undefined') {
  (function _whAutoReconcileHiveName() {
    var tries = 0;
    function attempt() {
      tries++;
      try {
        if (window._whSupabaseClient && localStorage.getItem('wh_hive_name')) {
          whReconcileHiveName(window._whSupabaseClient);
          return;
        }
      } catch (_) { /* empty-catch-allow: storage blocked → nothing to reconcile */ }
      if (tries < 8) setTimeout(attempt, 1000);   // client not up yet — retry ~8s then give up
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { setTimeout(attempt, 800); });
    else setTimeout(attempt, 800);
  })();
}

function whWorker() {
  try {
    return localStorage.getItem('wh_last_worker')    // canonical (the only worker key ever written)
        || null;
  } catch (_) { return null; /* storage blocked */ }
}
// NB: the registry's other alias reads (hive_id / workerName / wh_worker_name) were DEAD — never
// written anywhere in the codebase (get-without-set) — so they're dropped, not read defensively.
if (typeof window !== 'undefined') { window.whHiveId = whHiveId; window.whWorker = whWorker; }

// ─────────────────────────────────────────────
// renderRiskStrip — ONE shared "top at-risk assets" strip (STREAMLINE F2)
// ─────────────────────────────────────────────
// One renderer for the top-N at-risk asset list, reused by index (operational
// heartbeat), shift-brain (shift risk card), and alert-hub so the same asset-risk
// list cannot drift in look, ordering, or deep-link target across pages. Canonical
// home is asset-hub (the per-asset 360); every row deep-links back there.
//   rows : v_risk_truth rows, ALREADY band-filtered (high/critical) + ordered by
//          risk_score desc by the caller (registry top_risk_band rule stays at the
//          query). Each row needs asset_name, risk_score, risk_level, mtbf_days.
//   opts : { limit=3, title=null, ragTile='shared:risk_strip' }
//          - title set  -> returns a titled .oh-card with an "All assets →" link
//          - title unset -> returns the bare rows (for embedding in an existing card)
// Returns an HTML string (caller assigns to el.innerHTML), like renderSourceChip.
// Severity badge for the shared strips. The class alone was emitted for months with
// NO stylesheet anywhere defining it, so the chips inherited the parent <a>'s UA
// link-blue (rgb(0,0,238) — 1.24:1 on the card). Styles live inline like the rest
// of these renderers; text colors are the -300 tints that clear WCAG AA on dark.
function whOhBadge(lvl, text) {
  var c = {
    critical: ['rgba(252,165,165,0.16)', '#FECACA'],
    high:     ['rgba(253,186,116,0.16)', '#FDBA74'],
    medium:   ['rgba(253,224,71,0.14)',  '#FDE047'],
    low:      ['rgba(134,239,172,0.14)', '#86EFAC'],
  }[String(lvl || '').toLowerCase()] || ['rgba(255,255,255,0.08)', 'rgba(255,255,255,0.75)'];
  return '<span class="oh-badge oh-badge-' + escHtml(String(lvl || '')) + '" style="font-size:.58rem;font-weight:800;text-transform:uppercase;letter-spacing:.05em;padding:.15rem .45rem;border-radius:999px;background:' + c[0] + ';color:' + c[1] + ';white-space:nowrap;">' + escHtml(String(text == null ? lvl : text)) + '</span>';
}

function renderRiskStrip(rows, opts) {
  opts = opts || {};
  var e = escHtml;
  // N1 i18n: safe translator — uses the host page's window._t when present (home/hive have the
  // EN/FIL toggle), else a pass-through so the ~18 pages without i18n never break. risk_level
  // badges + MTBF stay as standard technical terms (acceptable in EN, like the plain-language gate).
  var _tt = (typeof window !== 'undefined' && typeof window._t === 'function') ? window._t : function (en) { return en; };
  var limit = opts.limit || 3;
  var list = (rows || []).slice(0, limit);
  if (!list.length) return '';
  var rowsHtml = list.map(function (r) {
    var pct  = Math.round((Number(r.risk_score) || 0) * 100);
    var mtbf = (r.mtbf_days != null) ? ('MTBF ' + Math.round(r.mtbf_days) + 'd') : '';
    var href = 'asset-hub.html?tag=' + encodeURIComponent(r.asset_name || '');
    var lvl  = String(r.risk_level || '').toLowerCase();
    return '<a href="' + e(href) + '" class="wh-risk-row" style="display:flex;align-items:center;justify-content:space-between;gap:10px;text-decoration:none;padding:8px 10px;background:rgba(255,255,255,0.03);border-radius:8px;">'
      +   '<div style="display:flex;align-items:center;gap:8px;min-width:0;flex:1;">'
      +     whOhBadge(lvl, r.risk_level)
      +     '<span style="font-size:.78rem;font-weight:600;color:var(--wh-cloud, #F4F6FA);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + e(r.asset_name) + '</span>'
      +   '</div>'
      +   '<div style="display:flex;align-items:center;gap:10px;flex-shrink:0;">'
      +     '<span style="font-size:.65rem;color:rgba(255,255,255,.6);white-space:nowrap;">' + e(mtbf) + '</span>'
      +     '<span style="font-size:.72rem;font-weight:800;color:var(--wh-red-text,#FCA5A5);">' + pct + '%</span>'
      +   '</div>'
      + '</a>';
  }).join('');
  var inner = '<div style="display:flex;flex-direction:column;gap:8px;">' + rowsHtml + '</div>';
  if (!opts.title) return inner;
  return '<div class="oh-card" data-rag-tile="' + e(opts.ragTile || 'shared:risk_strip') + '" data-rag-label="' + e(opts.title) + '" style="padding:14px 16px;border-left:3px solid var(--wh-red, #f87171);">'
    +   '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">'
    +     '<p style="font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--wh-red-text,#FCA5A5);margin:0;">' + e(opts.title) + '</p>'
    +     '<a href="asset-hub.html" style="font-size:.62rem;color:rgba(255,255,255,.6);text-decoration:none;display:inline-flex;align-items:center;min-height:44px;">' + e(_tt('All assets', 'Lahat ng asset')) + ' &#8594;</a>'
    +   '</div>' + inner + '</div>';
}
if (typeof window !== 'undefined') window.renderRiskStrip = renderRiskStrip;

// ─────────────────────────────────────────────
// renderPmDueStrip — ONE shared PM overdue/due-soon strip (STREAMLINE F4)
// ─────────────────────────────────────────────
// One renderer for a frequency-aware PM list, reused by shift-brain (this-shift
// slice) and any page that lists PM scope items, so the overdue/due-soon rows
// share look + scope labelling and can't drift. After S1 the NUMBERS are already
// canonical (v_pm_scope_items_truth.is_overdue/is_due_soon); this makes the
// PRESENTATION single-source too. Owner page = pm-scheduler; every row deep-links there.
//   rows : v_pm_scope_items_truth-shaped rows; needs asset_name (or tag_id),
//          is_overdue, days_until_due; optional criticality, item_text.
//   opts : { limit=10, title=null, scope=null ('this shift'|'hive'|'yours'),
//            ragTile='shared:pm_due_strip' }
// Returns an HTML string (caller assigns to el.innerHTML).
function renderPmDueStrip(rows, opts) {
  opts = opts || {};
  var e = escHtml;
  var limit = opts.limit || 10;
  var list = (rows || []).slice(0, limit);
  if (!list.length) return '';
  var rowsHtml = list.map(function (r) {
    var name = r.asset_name || r.tag_id || r.asset_tag || 'asset';
    var over = (r.is_overdue === true);
    var d = (r.days_until_due != null) ? Math.abs(Math.round(Number(r.days_until_due))) : null;
    var status, badge;
    if (over) { badge = 'critical'; status = (d != null) ? ('Overdue by ' + d + 'd') : 'Overdue'; }
    else      { badge = 'high';     status = (d != null) ? ('Due in ' + d + 'd')     : 'Due soon'; }
    var crit = r.criticality || r.asset_criticality || '';
    // Arc X A1: deep-link to the NAMED PM asset (pm-scheduler.html reads ?asset= ->
    // opens that asset's PM detail + schedule action), so the strip hands off the
    // record instead of dumping the user on the full overdue list (Issue #2).
    var href = 'pm-scheduler.html?asset=' + encodeURIComponent(name);
    return '<a href="' + e(href) + '" class="wh-pmdue-row" style="display:flex;align-items:center;justify-content:space-between;gap:10px;text-decoration:none;padding:8px 10px;background:rgba(255,255,255,0.03);border-radius:8px;">'
      +   '<div style="display:flex;align-items:center;gap:8px;min-width:0;flex:1;">'
      +     whOhBadge(badge, over ? 'OVERDUE' : 'DUE')
      +     '<span style="font-size:.78rem;font-weight:600;color:var(--wh-cloud, #F4F6FA);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + e(name) + '</span>'
      +   '</div>'
      +   '<div style="display:flex;align-items:center;gap:10px;flex-shrink:0;">'
      +     (crit ? '<span style="font-size:.62rem;color:rgba(255,255,255,.6);white-space:nowrap;">' + e(crit) + '</span>' : '')
      +     '<span style="font-size:.68rem;font-weight:700;color:' + (over ? 'var(--wh-red-text, #FCA5A5)' : 'var(--wh-orange-light, #FDB94A)') + ';white-space:nowrap;">' + e(status) + '</span>'
      +   '</div>'
      + '</a>';
  }).join('');
  var scopeChip = opts.scope
    ? '<span style="font-size:.55rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:rgba(255,255,255,.45);">' + e(opts.scope) + '</span>'
    : '';
  var inner = '<div style="display:flex;flex-direction:column;gap:8px;">' + rowsHtml + '</div>';
  if (!opts.title) return inner;
  return '<div class="oh-card" data-rag-tile="' + e(opts.ragTile || 'shared:pm_due_strip') + '" data-rag-label="' + e(opts.title) + '" style="padding:14px 16px;border-left:3px solid var(--wh-blue, #29B6D9);">'
    +   '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">'
    +     '<p style="font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--wh-blue, #29B6D9);margin:0;">' + e(opts.title) + '</p>'
    +     (scopeChip || '<a href="pm-scheduler.html" style="font-size:.62rem;color:rgba(255,255,255,.6);text-decoration:none;display:inline-flex;align-items:center;min-height:44px;">PM Scheduler &#8594;</a>')
    +   '</div>' + inner + '</div>';
}
if (typeof window !== 'undefined') window.renderPmDueStrip = renderPmDueStrip;

// ─────────────────────────────────────────────
// whStockSeverity — ONE canonical stock-state classifier (ASSET_ALERT_SHIFT reuse discipline)
// ─────────────────────────────────────────────
// Single source of truth for "how at-risk is this inventory row", reading the CANONICAL
// v_inventory_items_truth flags (is_out_of_stock / is_critical_low / is_low_stock) that
// migration 20260510000003 built expressly "so the same threshold logic does not get
// reimplemented across 10+ pages". Falls back to qty/reorder arithmetic only when the flags
// are absent (a non-canonical row). renderPartsStrip AND alert-hub's stock composer both call
// this so the low-stock band can never drift between the shift-brain strip and the alert inbox.
//   row : inventory-shaped; reads is_out_of_stock/is_critical_low/is_low_stock, qty_on_hand,
//         reorder_point (or min_qty as fallback).
//   returns { state:'out'|'critical_low'|'low'|'ok', severity:'critical'|'high'|'medium'|null,
//             label:'OUT'|'LOW'|null, atRisk:bool }
function whStockSeverity(row) {
  row = row || {};
  var qty = Number(row.qty_on_hand);
  var rpRaw = (row.reorder_point != null) ? row.reorder_point : row.min_qty;
  var rp = Number(rpRaw);
  var hasRp = !isNaN(rp) && rp > 0;
  var out  = (row.is_out_of_stock === true) || (!isNaN(qty) && qty <= 0);
  var crit = (row.is_critical_low === true) || (hasRp && !isNaN(qty) && qty <= rp / 2);
  var low  = (row.is_low_stock === true) || (hasRp && !isNaN(qty) && qty <= rp);
  if (out)  return { state: 'out',          severity: 'critical', label: 'OUT', atRisk: true };
  if (crit) return { state: 'critical_low', severity: 'high',     label: 'LOW', atRisk: true };
  if (low)  return { state: 'low',          severity: 'medium',   label: 'LOW', atRisk: true };
  return { state: 'ok', severity: null, label: null, atRisk: false };
}
if (typeof window !== 'undefined') window.whStockSeverity = whStockSeverity;

// renderPartsStrip — ONE shared parts-action list (STREAMLINE F3)
// ─────────────────────────────────────────────
// One renderer for an urgency-ranked parts list (out-of-stock first, then low /
// reorder), reused by shift-brain (parts pre-stage) and any page that lists
// at-risk parts, so the parts list shares look + ranking and can't drift. Owner
// page = inventory (the ledger + canonical is_low_stock/is_out_of_stock); every
// row deep-links there. (Count chips on index/hive already read the same flags.)
//   rows : inventory-shaped rows; needs part_name, qty_on_hand, min_qty; optional
//          is_out_of_stock / is_low_stock.
//   opts : { limit=10, title=null, ragTile='shared:parts_strip' }
function renderPartsStrip(rows, opts) {
  opts = opts || {};
  var e = escHtml;
  var limit = opts.limit || 10;
  var list = (rows || []).slice();
  // urgency rank: out-of-stock (qty<=0) before merely-low
  list.sort(function (a, b) {
    var ao = ((a.is_out_of_stock === true) || Number(a.qty_on_hand) <= 0) ? 0 : 1;
    var bo = ((b.is_out_of_stock === true) || Number(b.qty_on_hand) <= 0) ? 0 : 1;
    return ao - bo;
  });
  list = list.slice(0, limit);
  if (!list.length) return '';
  var rowsHtml = list.map(function (r) {
    var qty = Number(r.qty_on_hand) || 0, mn = Number(r.min_qty) || 0;
    // Canonical-reuse: classify through the shared whStockSeverity (same source alert-hub uses),
    // so the parts band can't diverge between this strip and the alert inbox.
    var st = whStockSeverity(r);
    var out = st.state === 'out';
    var badge = out ? 'critical' : 'high';
    var label = st.label || (out ? 'OUT' : 'LOW');
    var name = r.part_name || 'part';
    var meta = 'on hand ' + qty + ' / min ' + mn;
    // Arc X A1: deep-link to the NAMED part (inventory.html reads ?q= -> filters +
    // scrolls to it), so the strip hands off the record instead of a bare list.
    var href = 'inventory.html?q=' + encodeURIComponent(r.part_name || '');
    return '<a href="' + e(href) + '" class="wh-parts-row" style="display:flex;align-items:center;justify-content:space-between;gap:10px;text-decoration:none;padding:8px 10px;background:rgba(255,255,255,0.03);border-radius:8px;">'
      +   '<div style="display:flex;align-items:center;gap:8px;min-width:0;flex:1;">'
      +     whOhBadge(badge, label)
      +     '<span style="font-size:.78rem;font-weight:600;color:var(--wh-cloud, #F4F6FA);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + e(name) + '</span>'
      +   '</div>'
      +   '<span style="font-size:.62rem;color:rgba(255,255,255,.6);white-space:nowrap;flex-shrink:0;">' + e(meta) + '</span>'
      + '</a>';
  }).join('');
  var inner = '<div style="display:flex;flex-direction:column;gap:8px;">' + rowsHtml + '</div>';
  if (!opts.title) return inner;
  return '<div class="oh-card" data-rag-tile="' + e(opts.ragTile || 'shared:parts_strip') + '" data-rag-label="' + e(opts.title) + '" style="padding:14px 16px;border-left:3px solid #fb923c;">'
    +   '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">'
    +     '<p style="font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#fb923c;margin:0;">' + e(opts.title) + '</p>'
    +     '<a href="inventory.html" style="font-size:.62rem;color:rgba(255,255,255,.6);text-decoration:none;display:inline-flex;align-items:center;min-height:44px;">Inventory &#8594;</a>'
    +   '</div>' + inner + '</div>';
}
if (typeof window !== 'undefined') window.renderPartsStrip = renderPartsStrip;

// ─────────────────────────────────────────────
// renderActionBrief — ONE shared Action Brief renderer (STREAMLINE S6 / F1)
// ─────────────────────────────────────────────
// One renderer for the unified Action Brief produced by the analytics prescriptive
// engine (phase=prescriptive + horizon). Replaces the 3 bespoke brief renderers
// (alert-hub AMC card, shift-brain briefing, analytics action plan) so all three
// surfaces render time-scoped SLICES of the SAME brief in the SAME shape.
//   brief : the action_plan object { summary, this_week[], watch_list[], narration }
//           (analytics_action_plan_v1). Items may be strings or {action,why,...} objects.
//   opts  : { title='Action Brief', horizon=null, ragTile='shared:action_brief' }
// Returns an HTML string.
function renderActionBrief(brief, opts) {
  opts = opts || {};
  var e = escHtml;
  if (!brief || typeof brief !== 'object') return '';
  var summary = brief.summary || brief.narration || '';
  var asLine = function (it) {
    if (it == null) return '';
    if (typeof it === 'string') return e(it);
    // object form — prefer action/why, fall back to a compact join of values
    var a = it.action || it.task || it.item || it.title || '';
    var why = it.why || it.reason || it.detail || '';
    if (a || why) return '<strong>' + e(a) + '</strong>' + (why ? ' &middot; ' + e(why) : '');
    return e(Object.values(it).filter(function (v) { return typeof v === 'string'; }).join(' · '));
  };
  var listBlock = function (label, arr, color) {
    arr = Array.isArray(arr) ? arr.filter(Boolean) : [];
    if (!arr.length) return '';
    return '<div style="margin-top:10px;">'
      + '<p style="font-size:.58rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:' + color + ';margin:0 0 4px;">' + e(label) + '</p>'
      + '<ul style="margin:0;padding-left:16px;display:flex;flex-direction:column;gap:4px;">'
      + arr.slice(0, 8).map(function (it) { return '<li style="font-size:.74rem;color:rgba(255,255,255,.82);line-height:1.35;">' + asLine(it) + '</li>'; }).join('')
      + '</ul></div>';
  };
  var hChip = opts.horizon
    ? '<span style="font-size:.55rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:rgba(255,255,255,.72);">' + e(opts.horizon) + '</span>'
    : '';
  return '<div class="oh-card" data-rag-tile="' + e(opts.ragTile || 'shared:action_brief') + '" data-rag-label="' + e(opts.title || 'Action Brief') + '" style="padding:14px 16px;border-left:3px solid var(--wh-violet, #a78bfa);">'
    +   '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">'
    +     '<p style="font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--wh-violet, #a78bfa);margin:0;">' + e(opts.title || 'Action Brief') + '</p>' + hChip
    +   '</div>'
    +   (summary ? '<p style="font-size:.82rem;font-weight:600;color:var(--wh-cloud, #F4F6FA);margin:0;line-height:1.4;">' + e(summary) + '</p>' : '')
    +   listBlock(opts.horizon === 'strategic' ? 'This quarter' : opts.horizon === 'shift' ? 'This shift' : opts.horizon === 'today' ? 'Today' : 'This week', brief.this_week, 'var(--wh-red, #f87171)')
    +   listBlock('Watch list', brief.watch_list, 'var(--wh-orange, #F7A21B)')
    + '</div>';
}
if (typeof window !== 'undefined') window.renderActionBrief = renderActionBrief;

// reflowIdDump — E4 "digest, don't dump": when a SINGLE line crams many asset codes
// (the CODE shape TT-002 / GEN-003 / HVAC-02), wrap them onto multiple short rows so the
// list stays scannable (Miller 5±2) WITHOUT losing a single code. The UFAI E4 lens judges
// the worst single line's code count (a multi-line list is explicitly NOT a dump), and the
// callers render this in a `white-space:pre-wrap` block, so the inserted \n become line
// breaks. Idempotent: a line with <=7 codes (or already wrapped) is returned untouched.
function reflowIdDump(text, maxPerLine) {
  if (typeof text !== 'string' || !text) return text;
  maxPerLine = maxPerLine || 6;                 // <=6 per row clears the lens's >7 dump floor
  var IDLIKE = /\b[A-Z]{1,5}-\d{2,4}\b/g;
  return text.split('\n').map(function (line) {
    var codes = line.match(IDLIKE);
    if (!codes || codes.length <= 7) return line;   // not a dump — leave prose exactly as-is
    var n = 0;
    return line.replace(IDLIKE, function (m) {       // break BEFORE the code that opens each new group
      n++;
      return (n > 1 && (n - 1) % maxPerLine === 0) ? '\n' + m : m;
    });
  }).join('\n');
}
if (typeof window !== 'undefined') window.reflowIdDump = reflowIdDump;

// ─────────────────────────────────────────────
// wireDetailToggle — ONE shared "Show details" explainer toggle (STREAMLINE S10)
// ─────────────────────────────────────────────
// Every dashboard page carries a "How this is computed" explainer: a
// <button id="details-toggle-btn"> that shows/hides a <div role="region"> whose
// id is named in the button's aria-controls. The PANEL CONTENT stays static per
// page (each explains its own KPIs) — validate_rag_flywheel_locks.py +
// survey_ia_redundancy.py + tag_all_rag_tiles.py read the
// data-rag-tile="<page>:detail_panel" marker from the STATIC html, so moving the
// panel into JS would break those gates. What WAS copy-pasted on all 14 pages is
// the toggle HANDLER (a ~10-line IIFE) — collapsed here into one idempotent fn.
// Each page calls this once (replacing its old bespoke IIFE), typically at the
// end of its load/render. Explicit-call (not auto-run): the button id
// `details-toggle-btn` lives on ~19 pages, so an auto-runner would double-bind
// any page that still holds its own handler mid-rollout. The __whDetailWired
// guard still makes a duplicate call a safe no-op.
//   - reads the controlled pane from the button's aria-controls (so one fn
//     serves every page's differently-id'd `#X-summary-details` pane)
//   - toggles `.open` (matches each page's `#X-summary-details.open{display:block}` css)
//   - mirrors state into aria-expanded + swaps the label Show/Hide details
function wireDetailToggle() {
  if (typeof document === 'undefined') return;
  var btn = document.getElementById('details-toggle-btn');
  if (!btn || btn.__whDetailWired) return;
  var paneId = btn.getAttribute('aria-controls');
  var pane = paneId ? document.getElementById(paneId) : null;
  if (!pane) return;
  btn.__whDetailWired = true;
  btn.addEventListener('click', function () {
    var open = pane.classList.toggle('open');
    btn.setAttribute('aria-expanded', String(open));
    btn.textContent = open ? 'Hide details' : 'Show details';
  });
}
if (typeof window !== 'undefined') window.wireDetailToggle = wireDetailToggle;

// ─────────────────────────────────────────────
// resolveAssetNodeId — writer-side legacy-to-canonical bridge (Phase 5b)
// ─────────────────────────────────────────────
// Phase 5b dropped logbook.asset_ref_id (text) in favour of
// logbook.asset_node_id (uuid). The asset picker in legacy writer surfaces
// (logbook.html; parts-tracker.html deleted 2026-06-10, Phase 4) still queries the `assets` table, which
// is keyed by text. This helper looks up the corresponding canonical
// asset_nodes.id (uuid) via the legacy_asset_id bridge column so the writer
// can store the uuid FK on the new logbook column.
//
// Returns null when:
//   - hiveId is missing (solo mode -- asset_nodes is hive-scoped)
//   - legacyAssetId is missing
//   - no asset_node exists for that legacy id in the hive (e.g. user
//     registered an asset but the node wasn't created yet)
//
// Skill alignment: architect (parallel-cutover pattern), data-engineer
// (narrow .maybeSingle lookup, hive-scoped match), KPI_ENGINE.md Phase 5b.
async function resolveAssetNodeId(db, hiveId, assetIdOrLegacy) {
  if (!db || !hiveId || !assetIdOrLegacy) return null;
  // The Phase 5c asset picker passes the canonical asset_nodes uuid (exposed by
  // the view as `asset_id`); older callers may still pass a legacy text id
  // (`legacy_asset_id`). Match on whichever the value looks like.
  // IMPORTANT: v_asset_truth renames asset_nodes.id -> asset_id, so select('id')
  // / eq('id') 400s ("column v_asset_truth.id does not exist"). Always asset_id.
  const isUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(String(assetIdOrLegacy));
  try {
    let q = db.from('v_asset_truth').select('asset_id').eq('hive_id', hiveId);
    q = isUuid ? q.eq('asset_id', assetIdOrLegacy) : q.eq('legacy_asset_id', assetIdOrLegacy);
    const { data } = await q.maybeSingle();
    return data?.asset_id || null;
  } catch (_) {
    return null;
  }
}

// Inverse helper: given a canonical asset_node_id (uuid), return the
// legacy_asset_id (text) that still keys older systems like project_links.
// Used at use-site rather than rewriting the data model of every dependent.
async function resolveLegacyAssetId(db, assetNodeId) {
  if (!db || !assetNodeId) return null;
  try {
    // v_asset_truth renames asset_nodes.id -> asset_id; filtering eq('id') 400s
    // ("column v_asset_truth.id does not exist"). The canonical uuid is asset_id.
    const { data } = await db.from('v_asset_truth')
      .select('legacy_asset_id')
      .eq('asset_id', assetNodeId)
      .maybeSingle();
    return data?.legacy_asset_id || null;
  } catch (_) {
    return null;
  }
}

// ─────────────────────────────────────────────
// ocUpdate — optimistic-concurrency update helper (PRODUCTION_FIXES #43)
// ─────────────────────────────────────────────
// Adds an `.eq('updated_at', oldStamp)` guard so a multi-writer race is
// detected at the SQL layer instead of silently overwriting. Returns
// { ok, row, conflict, error }:
//   - ok=true, row=updated row  -> write succeeded
//   - ok=false, conflict=true   -> updated_at didn't match (someone else won)
//   - ok=false, error=Error     -> network / permission failure
//
// Callers wrap their save flow:
//   const { data: cur } = await db.from(t).select('id, updated_at').eq('id', id).single();
//   const res = await ocUpdate(db, t, id, updates, cur.updated_at);
//   if (res.conflict) showToast('Someone else just updated this. Refresh and try again.');
//
// Tables must have `updated_at timestamptz NOT NULL` + a touch trigger
// (see logbook_updated_at migration for the canonical recipe).
//
// Skills consulted: architect (OC pattern), data-engineer (single-statement
// guard, .select() return for conflict detection).
async function ocUpdate(db, table, id, updates, oldStamp) {
  if (!db || !table || !id) {
    return { ok: false, error: new Error('ocUpdate: missing args') };
  }
  try {
    const { data, error } = await db.from(table)
      .update(updates)
      .eq('id', id)
      .eq('updated_at', oldStamp)
      .select('id, updated_at');
    if (error) return { ok: false, error };
    if (!data || data.length === 0) {
      return { ok: false, conflict: true };
    }
    return { ok: true, row: data[0] };
  } catch (e) {
    return { ok: false, error: e };
  }
}

// ─── KPI Tile (Tier G capability: display_kpi_tile) ────────────────────────
// Shared KPI card renderer. Single source of truth for the RAG-coloured
// tile pattern across analytics.html, hive.html, asset-hub.html, predictive.
// Replaces 4 parallel implementations during the Tier G consolidation pass.
//
// opts:
//   - title    (required) "MTBF — Mean Time Between Failures"
//   - standard            "ISO 14224:2016 §9.3"
//   - value    (required) the hero number (string or number)
//   - unit                "days" | "%" | "h" | ...
//   - sublabel            small line under the hero number
//   - color               'green'|'yellow'|'red'|'grey' — RAG state
//   - detail              HTML string for the expandable section (optional)
//   - legend              footer note shown inside expanded detail
//   - autoOpen            override default-open behavior (red auto-opens)
//   - tileId              optional caller-supplied id; else auto-generated
//
// capability: display_kpi_tile
let _whKpiTileId = 0;
function renderKpiTile(opts) {
  opts = opts || {};
  const COLORS = {
    green:  { bg: 'rgba(74,222,128,0.08)',   border: 'rgba(74,222,128,0.3)',   text: 'var(--wh-green, #4ade80)',  label: '✓ Healthy'  },
    yellow: { bg: 'rgba(247,162,27,0.08)',   border: 'rgba(247,162,27,0.3)',   text: 'var(--wh-orange, #F7A21B)',  label: '⚠ Watch'    },
    red:    { bg: 'rgba(248,113,113,0.08)',  border: 'rgba(248,113,113,0.3)',  text: 'var(--wh-red, #f87171)',  label: '✗ Critical' },
    grey:   { bg: 'rgba(255,255,255,0.03)',  border: 'rgba(255,255,255,0.08)', text: 'rgba(255,255,255,0.6)', label: 'No data' },
  };
  const c   = COLORS[opts.color] || COLORS.grey;
  const id  = opts.tileId || `kpi-${_whKpiTileId++}`;
  const autoOpen = opts.autoOpen !== undefined ? opts.autoOpen : (opts.color === 'red');
  const detail = opts.detail || '';
  const legend = opts.legend || '';

  // The tile's title is the card's HEADING: without it a screen-reader user has no
  // way to navigate a page of KPI cards (and axe cannot catch this -- heading-order
  // has nothing to fail on when there are no headings at all). An <h2> may not live
  // INSIDE a <button> (phrasing content only), so the heading WRAPS the button --
  // the ARIA Authoring Practices accordion pattern. Margins zeroed = pixel-identical.
  return `<div class="card" style="border-left:3px solid ${c.border};margin-bottom:1rem;">
    <h2 style="margin:0;font:inherit;color:inherit;">
    <button class="kpi-toggle" onclick="if(window.toggleKPI)toggleKPI('${id}')" style="min-height:${detail ? '72px' : '0'};">
      <div style="flex:1;text-align:left;">
        <div style="font-size:0.68rem;font-weight:700;color:rgba(255,255,255,0.80);text-transform:uppercase;letter-spacing:0.08em;margin-bottom:0.25rem;">
          ${escHtml(opts.title || '')} <span style="font-size:0.58rem;font-weight:500;">${escHtml(opts.standard || '')}</span>
        </div>
        <div style="display:flex;align-items:baseline;gap:0.4rem;margin-bottom:0.15rem;">
          <!-- 1.5rem == the canonical KPI tier (.sc-hero in components.css). This tile
               rendered 1.9rem, a THIRD size for the same concept, which inverted the
               hierarchy on analytics: the DETAIL card values (30px) shouted louder than
               the SUMMARY roll-up (24px) and the page h1 (22px) -- "biggest = most
               important" backwards, and 3 "big" sizes where the rule allows 2. A KPI
               number is ONE tier whether it sits in a summary tile or a result card;
               .simple-card.hero is the deliberate second tier for the ONE key metric. -->
          <span style="font-size:1.5rem;font-weight:800;line-height:1.15;color:${c.text};font-variant-numeric:tabular-nums;">${escHtml(String(opts.value === undefined ? '-' : opts.value))}</span>
          <span style="font-size:0.78rem;color:rgba(255,255,255,0.80);">${escHtml(opts.unit || '')}</span>
        </div>
        ${opts.sublabel ? `<div style="font-size:0.67rem;color:rgba(255,255,255,0.80);">${escHtml(opts.sublabel)}</div>` : ''}
      </div>
      <div style="display:flex;flex-direction:column;align-items:flex-end;gap:0.4rem;flex-shrink:0;margin-left:0.75rem;">
        <span style="font-size:0.63rem;font-weight:700;padding:0.2rem 0.55rem;border-radius:999px;background:${c.bg};border:1px solid ${c.border};color:${c.text};white-space:nowrap;">${c.label}</span>
        ${detail ? `<span class="kpi-chevron${autoOpen ? ' open' : ''}" id="${id}-chevron">▼</span>` : ''}
      </div>
    </button>
    </h2>
    ${detail ? `
      <div class="kpi-detail${autoOpen ? ' open' : ''}" id="${id}" style="border-top:1px solid rgba(255,255,255,0.06);">
        ${detail}
        ${legend ? `<p style="font-size:0.62rem;color:rgba(255,255,255,0.80);margin-top:0.5rem;">${escHtml(legend)}</p>` : ''}
      </div>` : ''}
  </div>`;
}

// Default toggle handler — pages that already define toggleKPI keep their own.
if (typeof window !== 'undefined' && !window.toggleKPI) {
  window.toggleKPI = function (id) {
    const detail  = document.getElementById(id);
    const chevron = document.getElementById(id + '-chevron');
    if (!detail) return;
    const isOpen = detail.classList.toggle('open');
    if (chevron) chevron.classList.toggle('open', isOpen);
  };
}


// ─── Compact Stat (Tier G capability: display_compact_stat) ────────────────
// Small inline label/value tile — the recurring "MTBF: 18d" pattern across
// asset-hub risk panel, hive benchmark rows, predictive count chips, shift
// brain top-of-shift stats. Distinct from renderKpiTile (which is the full
// RAG hero card); this is the compact variant for stat strips.
//
// opts:
//   - label    (required) "MTBF" | "Critical" | "Days to Failure"
//   - value    (required) hero number / text
//   - unit                "d" | "%" | "h" (optional, rendered small)
//   - color               'red'|'orange'|'yellow'|'green'|'blue'|'grey' OR a CSS color
//   - sublabel            small line under the value (optional)
//   - icon                emoji or single char prefix (optional)
//   - href                wrap whole tile in <a href> (optional)
//
// capability: display_compact_stat
function renderCompactStat(opts) {
  opts = opts || {};
  const PALETTE = {
    red:    'var(--wh-red, #f87171)',
    orange: '#fb923c',
    yellow: 'var(--wh-amber, #facc15)',
    green:  'var(--wh-green, #4ade80)',
    blue:   '#60a5fa',
    grey:   'rgba(255,255,255,0.55)',
  };
  const color = PALETTE[opts.color] || opts.color || 'rgba(255,255,255,0.85)';

  const inner =
    `<div style="display:flex;flex-direction:column;align-items:flex-start;gap:0.15rem;padding:0.5rem 0.85rem;min-width:84px;">` +
      `<span style="font-size:0.6rem;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:rgba(255,255,255,0.80);">${escHtml(opts.label || '')}</span>` +
      `<span style="display:flex;align-items:baseline;gap:0.25rem;">` +
        (opts.icon ? `<span style="font-size:0.85rem;">${escHtml(opts.icon)}</span>` : '') +
        `<span style="font-size:1.05rem;font-weight:800;line-height:1;color:${color};">${escHtml(String(opts.value === undefined || opts.value === null ? '-' : opts.value))}</span>` +
        (opts.unit ? `<span style="font-size:0.7rem;color:rgba(255,255,255,0.72);">${escHtml(opts.unit)}</span>` : '') +
      `</span>` +
      (opts.sublabel ? `<span style="font-size:0.6rem;color:rgba(255,255,255,0.80);">${escHtml(opts.sublabel)}</span>` : '') +
    `</div>`;

  if (opts.href) {
    return `<a href="${escHtml(opts.href)}" style="text-decoration:none;color:inherit;">${inner}</a>`;
  }
  return inner;
}


// ─── Alert Preview (Tier G capability: display_alert_preview) ──────────────
// Shared alert-row renderer for cross-page previews of AMC briefings, failure
// signature matches, sensor anomalies, parts staging recommendations.
// Each preview links to alert-hub.html for the full filterable view.
//
// opts:
//   - kind:      'amc_briefing' | 'failure_signature' | 'sensor_anomaly' | 'parts_staging'
//   - title      e.g. "PMP-001 bearing failure pattern detected"
//   - severity   'critical' | 'high' | 'medium' | 'low'
//   - asset      asset_tag or machine name (optional)
//   - message    short body text (optional)
//   - created_at ISO timestamp (renders as relative time)
//   - href       link target (default: alert-hub.html)
//
// capability: display_alert_preview
function renderAlertPreview(opts) {
  opts = opts || {};
  const SEV = {
    critical: { bg: 'rgba(248,113,113,0.10)', border: 'var(--wh-red, #f87171)', label: '🔴 CRITICAL' },
    high:     { bg: 'rgba(247,162,27,0.10)',  border: 'var(--wh-orange, #F7A21B)', label: '🟠 HIGH' },
    medium:   { bg: 'rgba(250,204,21,0.10)',  border: 'var(--wh-amber, #facc15)', label: '🟡 MEDIUM' },
    low:      { bg: 'rgba(74,222,128,0.10)',  border: 'var(--wh-green, #4ade80)', label: '🟢 LOW' },
  };
  const s = SEV[opts.severity] || SEV.medium;
  const kindIcon = ({
    amc_briefing:      '☀️',
    failure_signature: '⚠',
    sensor_anomaly:    '📡',
    parts_staging:     '📦',
  })[opts.kind] || '🔔';

  let rel = '';
  if (opts.created_at) {
    try {
      const secs = (Date.now() - new Date(opts.created_at).getTime()) / 1000;
      if (secs < 60)        rel = 'just now';
      else if (secs < 3600) rel = `${Math.round(secs / 60)}m ago`;
      else if (secs < 86400) rel = `${Math.round(secs / 3600)}h ago`;
      else                  rel = `${Math.round(secs / 86400)}d ago`;
    } catch (_e) { rel = ''; }
  }

  const href = opts.href || 'alert-hub.html';
  return `<a href="${escHtml(href)}" class="alert-preview" style="display:block;padding:0.6rem 0.8rem;margin-bottom:0.4rem;background:${s.bg};border-left:3px solid ${s.border};border-radius:0.5rem;text-decoration:none;color:inherit;">
    <div style="display:flex;align-items:baseline;justify-content:space-between;gap:0.5rem;margin-bottom:0.15rem;">
      <span style="font-size:0.7rem;font-weight:700;letter-spacing:0.04em;">${kindIcon} ${escHtml(opts.title || 'Alert')}</span>
      <span style="font-size:0.6rem;color:rgba(255,255,255,0.80);white-space:nowrap;">${escHtml(s.label)}${rel ? ' · ' + escHtml(rel) : ''}</span>
    </div>
    ${opts.asset ? `<div style="font-size:0.62rem;color:rgba(255,255,255,0.80);">Asset: ${escHtml(opts.asset)}</div>` : ''}
    ${opts.message ? `<div style="font-size:0.65rem;color:rgba(255,255,255,0.80);margin-top:0.15rem;">${escHtml(opts.message)}</div>` : ''}
  </a>`;
}


// ─────────────────────────────────────────────
// fetchWithTimeout — bounded fetch wrapper (Phase 1.5 of STRATEGIC_ROADMAP)
// ─────────────────────────────────────────────
// Every cross-network call in WorkHive must have an upper bound. On a 2G/3G
// link in a Philippine plant, a missing timeout means a logbook entry,
// embed-entry POST, or assistant turn can hang for minutes while the user
// stares at a spinner and assumes the page is broken. AbortController gives us
// a hard ceiling and a recognisable AbortError caller code can branch on.
//
// Defaults: 30s timeout (matches Supabase Edge Functions cold-start budget).
// Callers can pass a smaller value for fire-and-forget telemetry (embed-entry
// is 8s — if the embed pipeline is overwhelmed we silently skip rather than
// block the user's save).
//
// Skills consulted: devops (network resilience), realtime-engineer (signal
// propagation), architect ("every fetch must be bounded").
//
// Usage:
//   const res = await fetchWithTimeout(url, { method: 'POST', body }, 20000);
//   if (res === null) { /* timed out — caller decides UX */ }
//   else if (!res.ok) { ... } else { const j = await res.json(); ... }
//
// Returns: a Response on success, or null on timeout/abort. Network errors
// (DNS failure, offline) still throw — caller wraps in try/catch as today.
// ONE retry, on a TRANSPORT failure, for IDEMPOTENT reads only.
//
// Two gates have flaked on the same shape: `push-runtime-delivery` went red once against four greens, and the
// Playwright smoke tier has an intermittent Supabase blip. Neither is a product defect and neither is a
// timeout — the wrapper's budget is 45s and the failures land in milliseconds. They are the network briefly
// refusing a connection, and the honest fix is at the source rather than a widened budget in each spec, which
// would measure network weather instead of the product.
//
// WHY METHOD-INFERRED AND NOT A FLAG. This helper cannot know whether its caller is safe to repeat, and a
// retry on a POST is how one payment becomes two. HTTP already answers the question: GET is idempotent by
// contract, so the retry is scoped to GET (and to a missing method, which IS GET). Every write method —
// POST/PUT/PATCH/DELETE — is excluded by construction, so no opt-in flag can be forgotten and no caller can be
// surprised into a double write.
//
// WHAT COUNTS AS A TRANSPORT FAILURE. Only a thrown TypeError, which is what fetch raises for a refused or
// dropped connection. An AbortError is the timeout path and still returns null on the FIRST attempt without
// retrying: the caller asked for a budget and got it, and silently doubling that budget would break the
// contract the callers reason about (utils.js's own usage note, and the three callers that were fixed for
// mis-handling the null). An HTTP error response is not an exception at all — a 500 resolves normally and is
// the caller's to read, never retried here.
const _FWT_RETRY_DELAY_MS = 250;

async function fetchWithTimeout(url, options, timeoutMs, _isRetry) {
  const ms = (typeof timeoutMs === 'number' && timeoutMs > 0) ? timeoutMs : 30000;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  try {
    const opts = Object.assign({}, options || {}, { signal: ctrl.signal });
    return await fetch(url, opts);
  } catch (e) {
    if (e && (e.name === 'AbortError' || e.code === 20)) return null;
    const method = String((options && options.method) || 'GET').toUpperCase();
    const isTransport = e instanceof TypeError;
    if (!_isRetry && method === 'GET' && isTransport) {
      // A short pause, because an immediate retry into a connection that was just refused usually earns the
      // same refusal. One attempt only: `_isRetry` is the recursion guard, so a persistently dead endpoint
      // still fails fast rather than doubling every caller's latency budget indefinitely.
      await new Promise(r => setTimeout(r, _FWT_RETRY_DELAY_MS));
      return await fetchWithTimeout(url, options, ms, true);
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

if (typeof window !== 'undefined') window.fetchWithTimeout = fetchWithTimeout;

// ─────────────────────────────────────────────
// whConfirm() / whPrompt() — styled async modals
// ─────────────────────────────────────────────
// Drop-in async replacements for native confirm() / prompt(). Both block
// the main thread, can't be styled, and on some mobile browsers are
// silently suppressed entirely. The platform toast/modal stack owns the
// UI shell; whConfirm/whPrompt are the gateway to it.
//
// Migration from native:
//   if (!confirm('Delete X?')) return;
//     -> if (!(await whConfirm('Delete X?'))) return;        // caller becomes async
//
//   const name = prompt('Enter name'); if (!name) return;
//     -> const name = await whPrompt('Enter name'); if (!name) return;
//
// Both return a Promise:
//   whConfirm: resolves true (OK) / false (Cancel or Esc / backdrop click)
//   whPrompt: resolves the entered string, or null if cancelled
//
// ── WH_STATUS_ENUMS — canonical per-table status enums (single source of truth) ──
// Grounded Sweep critique W3 (status-enum-constants). Hand-typed status string
// literals drift from the DB enum and silently miscount KPIs — the dayplanner
// "overdue" bug compared schedule_items.item_status against the literal 'closed',
// a value that does NOT exist in the enum (pending/in_progress/done/blocked/
// skipped), so DONE items were counted as overdue (live 6 vs DB 3). Reference THIS
// map instead of hand-typing status strings. validate_status_enum_drift.py asserts
// it can never silently diverge from the canonical capture contract in
// supabase/migrations (deterministic JS-constant-vs-DB comparison).
if (typeof window !== 'undefined' && !window.WH_STATUS_ENUMS) {
  window.WH_STATUS_ENUMS = {
    // schedule_items.item_status — capture_contracts_wave2 migration. 'done' is the
    // only terminal/closed state; everything else is OPEN (overdue if past due).
    schedule_item: ['pending', 'in_progress', 'done', 'blocked', 'skipped'],
  };
}

// ── whModalA11y — retrofit the dialog a11y bar onto a HAND-ROLLED modal ──────
// Grounded Sweep critique C7 / W2. whConfirm/whPrompt build their dialog in JS
// with the a11y bar already set; pages with static hand-rolled overlays (logbook,
// pm-scheduler, dayplanner, …) skip it. This helper adds the bar to an existing
// element WITHOUT touching its open/close call sites: it sets role=dialog +
// aria-modal + an accessible name, then a MutationObserver watches the element's
// class/style and — when it becomes visible — captures focus, traps Tab within
// the panel, and wires ESC; when it hides, it restores focus to the opener.
// Idempotent + opt-in. opts: { label?, labelledBy?, onClose? }.
//   whModalA11y(document.getElementById('my-modal'), { label: 'Edit asset', onClose: closeMyModal });
(function(){
  if (typeof window === 'undefined' || window.whModalA11y) return;

  var FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]),' +
                  'select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

  // ─────────────────────────────────────────────
  // whToggleAria — canonical toggle-state announcer (Arc U, WCAG 4.1.2)
  // ─────────────────────────────────────────────
  // Toggleable filter/tab buttons flip an `.active` class but say nothing to a
  // screen reader — `aria-pressed` is what announces "pressed/not pressed". Rather
  // than hand-add it to every button on every page, this ONE shared helper (utils.js
  // is the 31/32 shared surface) sets aria-pressed from `.active` at init AND observes
  // class changes so a toggle stays announced. Genuinely correct: a screen reader
  // reads the RUNTIME DOM. Managed classes = the ones the a11y gate knows as toggleables.
  // 2026-07-18: extended after the thorough class-T (T8) sweep found stateful tabs/toggles on
  // engineering-design (.page-tab), pm-scheduler (.nav-tab), marketplace (.section-toggle-btn,
  // .btn-filter), analytics (.kpi-toggle) that show .active visually but exposed no aria-state.
  // Adding them here auto-wires aria-pressed (synced to .active by the MutationObserver) family-wide.
  window.WH_TOGGLE_CLASSES = ['filter-chip', 'tab-btn', 'reaction-btn', 'phase-tab', 'view-tab',
    'page-tab', 'nav-tab', 'section-toggle-btn', 'kpi-toggle', 'btn-filter', 'wh-toggle',
    'discipline-pill'];  // eng-design discipline chooser: 1 active = a SELECT, announce it (WCAG 4.1.2 + R3)
  function whToggleAria(root) {
    if (typeof document === 'undefined') return;
    root = root || document;
    var sel = window.WH_TOGGLE_CLASSES.map(function (c) { return 'button.' + c + ', .' + c + '[role="button"]'; }).join(', ');
    var btns = root.querySelectorAll(sel);
    if (!btns.length) return;
    var sync = function (el) {
      // radio-style tabs use aria-selected; a DISCLOSURE (declares aria-expanded, e.g. a
      // filter PANEL trigger) syncs aria-expanded; a POPUP/DIALOG trigger (declares
      // aria-haspopup, e.g. the community open-thread reply button) is a PRESS that opens a
      // dialog — it has no pressed-state, so it is left untouched; plain toggle chips use
      // aria-pressed. Giving a disclosure/popup-trigger aria-pressed would mislabel it a
      // stateful SELECT (R3 control-vocab: a panel/dialog opener must not share the select
      // silhouette) and is WCAG 4.1.2-wrong (expand→aria-expanded, popup→aria-haspopup).
      var attr = (el.getAttribute('role') === 'tab') ? 'aria-selected'
               : el.hasAttribute('aria-expanded') ? 'aria-expanded'
               : el.hasAttribute('aria-haspopup') ? null
               : 'aria-pressed';
      if (!attr) return;
      el.setAttribute(attr, el.classList.contains('active') ? 'true' : 'false');
    };
    btns.forEach(sync);
    // observe .active flips AND newly-inserted toggles so the announced state tracks the visual
    // state. 2026-07-18: data-driven pages render toggles AFTER load (analytics .kpi-toggle) — the
    // attribute-only observer never wired them, so add childList to catch dynamically-added ones.
    if (!window.__whToggleObs) {
      window.__whToggleObs = new MutationObserver(function (muts) {
        muts.forEach(function (m) {
          if (m.type === 'attributes' && m.attributeName === 'class') {
            var el = m.target;
            if (window.WH_TOGGLE_CLASSES.some(function (c) { return el.classList && el.classList.contains(c); })) sync(el);
          } else if (m.type === 'childList') {
            m.addedNodes.forEach(function (n) {
              if (n.nodeType !== 1) return;
              if (window.WH_TOGGLE_CLASSES.some(function (c) { return n.classList && n.classList.contains(c); })) sync(n);
              if (n.querySelectorAll) n.querySelectorAll(sel).forEach(sync);
            });
          }
        });
      });
      window.__whToggleObs.observe(document.body, { subtree: true, attributes: true, attributeFilter: ['class'], childList: true });
    }
  }
  window.whToggleAria = whToggleAria;
  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { whToggleAria(); });
    else whToggleAria();
  }

  window.whModalA11y = function whModalA11y(modalEl, opts) {
    if (!modalEl || modalEl.__whModalA11y) return null;   // null el or already wired
    opts = opts || {};
    modalEl.__whModalA11y = true;

    if (!modalEl.getAttribute('role'))       modalEl.setAttribute('role', 'dialog');
    if (!modalEl.hasAttribute('aria-modal')) modalEl.setAttribute('aria-modal', 'true');
    if (opts.labelledBy)                     modalEl.setAttribute('aria-labelledby', opts.labelledBy);
    else if (opts.label && !modalEl.getAttribute('aria-label')) modalEl.setAttribute('aria-label', opts.label);

    var lastFocus = null, keyBound = false;

    function isOpen() {
      var cs = window.getComputedStyle(modalEl);
      // A retained `.hidden` class means CLOSED only when the COMPUTED style agrees.
      // logbook's 7 hand-rolled modals open via an inline `style.display:flex` that
      // OVERRIDES a `.hidden` class they never remove — visually open, but keying off
      // the class ALONE false-negatived isOpen(), so the ESC-close + Tab focus-trap +
      // focus-restore never armed (the retrofit silently no-op'd). Gate the class on the
      // computed display so an inline-override is correctly seen as open. (2026-07-13)
      if (modalEl.classList.contains('hidden') && cs.display === 'none') return false;
      // .sheet content panels (marketplace/community) slide via transform and
      // toggle a .open class; when closed they stay display:block + pointer-
      // events:auto (just translated off-screen), so the generic checks below
      // can't see "closed". Treat a transform-slide .sheet without .open as
      // closed, else whModalA11y would trap focus on page load. (2026-06-09)
      if (modalEl.classList.contains('sheet') && !modalEl.classList.contains('open')) return false;
      if (cs.display === 'none' || cs.visibility === 'hidden') return false;
      // Opacity/pointer-events open pattern (skillmatrix .modal-overlay,
      // marketplace/community .sheet-overlay, founder-console .fb-drawer-backdrop):
      // the overlay STAYS display:flex and toggles a .open class that flips
      // opacity + pointer-events. When closed it is pointer-events:none — detect
      // that so we don't treat a fully-invisible overlay as permanently open and
      // trap focus on page load. pointer-events flips instantly with the class;
      // opacity is transitioned, so reading opacity would mis-fire mid-animation.
      if (cs.pointerEvents === 'none') return false;
      return true;
    }
    function focusables() {
      return Array.prototype.filter.call(modalEl.querySelectorAll(FOCUSABLE), function(el) {
        return el.offsetParent !== null || el.getClientRects().length > 0;
      });
    }
    // The modal's OWN close path, shared by Escape AND the hardware-Back contract below:
    // prefer the page's close fn, else click its close control, else strip open-state classes.
    function closeViaOwnPath() {
      if (typeof opts.onClose === 'function') { opts.onClose(); return; }
      // No explicit close fn: click the modal's OWN close control so the page's
      // real close logic runs (removes .open / adds .hidden / clears state) — no
      // sticky inline display:none that would break the next open. Fall back to
      // adding .hidden only if the modal has no close affordance.
      var closer = null;
      try { closer = modalEl.querySelector('[data-wh-close],[aria-label="Close" i],.modal-close,.sheet-close'); }
      catch (_) { /* empty-catch-allow: querySelector case-flag unsupported */ }
      if (closer) closer.click();
      // No close affordance (e.g. a sheet whose content — and its Close button —
      // is injected on open, opened here while empty): close by the overlay's OWN
      // open-state class so it can't get stuck open. .sheet-overlay opens via
      // `.open`; some modals via `.active`/`.show`; display-toggle modals via
      // `.hidden`. Strip the open-state classes AND add .hidden — universal close.
      else { modalEl.classList.remove('open', 'active', 'show'); modalEl.classList.add('hidden'); }
    }
    function onKey(e) {
      if (e.key === 'Escape') {
        e.stopPropagation();
        closeViaOwnPath();
      } else if (e.key === 'Tab') {
        var f = focusables();
        if (!f.length) return;
        var first = f[0], last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    }
    function activate() {
      if (keyBound) return;
      keyBound = true;
      lastFocus = document.activeElement;
      document.addEventListener('keydown', onKey, true);
      // ── MODALS TRAP BACK (critic walk T42, 2026-09-02) ─────────────────────────────
      // Opening a modal pushed NO history entry, so the phone hardware-Back gesture —
      // a constant on Android — navigated away from the WHOLE page mid-form (walked
      // live: inventory Add-Part → Back → landed on logbook, task and input gone).
      // Contract: each activation pushes one history entry; popstate closes the top
      // open modal via its OWN close path (same logic as Escape); a close by any
      // other means (X, backdrop, save) consumes the entry with a suppressed back.
      // Back now dismisses the modal, and only exits the page when nothing is open.
      try {
        window.__whModalBackStack = window.__whModalBackStack || [];
        if (!window.__whModalBackWired) {
          window.__whModalBackWired = true;
          window.addEventListener('popstate', function () {
            if (window.__whModalBackSuppress) { window.__whModalBackSuppress = false; return; }
            var stk = window.__whModalBackStack;
            if (stk && stk.length) {
              var top = stk.pop();
              try { top.close(); } catch (_) { /* empty-catch-allow: close best-effort */ }
            }
          });
        }
        history.pushState({ whModalBack: true }, '');
        window.__whModalBackStack.push({ el: modalEl, close: closeViaOwnPath });
      } catch (_) { /* empty-catch-allow: history unavailable → behavior degrades to pre-contract */ }
      // Respect a page that already autofocused something inside the modal
      // (e.g. dayplanner focuses #m-title) — only grab focus if it's outside.
      setTimeout(function() {
        if (!modalEl.contains(document.activeElement)) {
          var f = focusables();
          if (f.length) { try { f[0].focus(); } catch (_) { /* empty-catch-allow */ } }
        }
      }, 0);
    }
    function deactivate() {
      if (!keyBound) return;
      keyBound = false;
      // T42 back-contract bookkeeping: if THIS modal's history entry is still on top
      // (it closed via X / backdrop / save, not via Back), consume the entry with a
      // suppressed back so the next hardware-Back exits the page, not a ghost state.
      try {
        var stk = window.__whModalBackStack;
        if (stk && stk.length && stk[stk.length - 1].el === modalEl) {
          stk.pop();
          window.__whModalBackSuppress = true;
          history.back();
        }
      } catch (_) { /* empty-catch-allow: history unavailable */ }
      try { document.removeEventListener('keydown', onKey, true); } catch (_) { /* empty-catch-allow */ }
      try { if (lastFocus && lastFocus.focus) lastFocus.focus(); } catch (_) { /* empty-catch-allow */ }
    }

    var obs = new MutationObserver(function() { isOpen() ? activate() : deactivate(); });
    obs.observe(modalEl, { attributes: true, attributeFilter: ['class', 'style'] });
    if (isOpen()) activate();   // already-open at wire time
    return { activate: activate, deactivate: deactivate };
  };

  // ─────────────────────────────────────────────
  // whSheetA11y — auto-wire the shared modal a11y to every bottom-sheet / overlay
  // ─────────────────────────────────────────────
  // The sheet/overlay focus-trap + Escape-close + focus-restore behaviour is ONE
  // shared primitive (whModalA11y above). Rather than each page calling it per
  // overlay, this finds every `.sheet-overlay` / `.modal-overlay` and wires it once,
  // and watches for overlays injected later. Idempotent — whModalA11y guards with
  // __whModalA11y, and only arms the trap when the overlay is actually open. This is
  // the Arc-U (WCAG 2.1.2 No-Keyboard-Trap-escape / 2.4.3 Focus-Order) shared lever.
  function whSheetA11y(root) {
    if (typeof document === 'undefined' || !window.whModalA11y) return;
    root = root || document;
    var els = root.querySelectorAll('.sheet-overlay, .modal-overlay');
    Array.prototype.forEach.call(els, function (el) {
      try { window.whModalA11y(el); } catch (_) { /* empty-catch-allow */ }
    });
  }
  window.whSheetA11y = whSheetA11y;
  if (typeof document !== 'undefined') {
    var _wireSheets = function () {
      whSheetA11y();
      if (!window.__whSheetObs && document.body) {
        window.__whSheetObs = new MutationObserver(function (muts) {
          for (var i = 0; i < muts.length; i++) {
            var added = muts[i].addedNodes;
            for (var j = 0; j < added.length; j++) {
              var n = added[j];
              if (!n || n.nodeType !== 1) continue;
              if (n.matches && n.matches('.sheet-overlay, .modal-overlay')) {
                try { window.whModalA11y(n); } catch (_) { /* empty-catch-allow */ }
              }
              if (n.querySelectorAll) whSheetA11y(n);
            }
          }
        });
        window.__whSheetObs.observe(document.body, { childList: true, subtree: true });
      }
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', _wireSheets);
    else _wireSheets();
  }

  // ─────────────────────────────────────────────
  // whReleaseSheetsOnBack — an overlay must not survive the Back button
  // ─────────────────────────────────────────────
  // A sheet here does not push a history entry (deliberately: it has its own close affordance and
  // hijacking Back is worse). The consequence is that pressing Back navigates AWAY mid-sheet, and the
  // page is later restored from the bfcache with the sheet STILL OPEN and body overflow STILL hidden.
  // Nothing intercepts clicks, so every click-based check passes -- the page simply will not scroll,
  // over a form the person thought they had left.
  //
  // marketplace.html found and fixed this on a live walk; walking marketplace-seller.html the same way
  // found the identical defect, and a sweep showed skillmatrix.html has it too. Three pages, one
  // behaviour: so it belongs HERE, self-wiring, rather than as a fourth hand-rolled copy waiting to be
  // forgotten on the fifth page. (feedback_universal_a11y_shared_component: a repeated behaviour is ONE
  // shared helper.) Pages that already handle it are unaffected -- releasing an already-released lock
  // is a no-op.
  //
  // It only ever REMOVES state, so it cannot close a sheet a person just opened: both events fire on a
  // history move or a bfcache restore, never during normal interaction.
  if (typeof window !== 'undefined' && typeof document !== 'undefined' && !window.__whSheetRelease) {
    window.__whSheetRelease = function () {
      var open = document.querySelectorAll('.sheet.open, .sheet-overlay.open, .modal-overlay.open, [id^="overlay-"].open, [id^="sheet-"].open');
      Array.prototype.forEach.call(open, function (el) { el.classList.remove('open'); });
      // Clear the inline lock only -- a page whose stylesheet legitimately sets overflow keeps it.
      if (document.body && document.body.style.overflow === 'hidden') document.body.style.overflow = '';
    };
    window.addEventListener('pageshow', function (e) { if (e.persisted) window.__whSheetRelease(); });
    window.addEventListener('popstate', function () { window.__whSheetRelease(); });
  }
})();

// The modal mounts on document.body (so it works on any page without
// per-page setup), traps focus, and disposes on resolve. ARIA: role="dialog"
// + aria-labelledby + aria-modal so screen readers announce it.
(function(){
  if (typeof window === 'undefined' || window.whConfirm) return;

  // ★ONE CONFIRM AT A TIME. Measured on two pages this session (engineering-design's calc Delete and
  // project-manager's project Delete): pressing a destructive control TWICE stacked TWO confirm dialogs, and
  // cancelling dismissed only the top one - so a double-tapper had to answer the same question twice, with an
  // identical dialog waiting behind the one they just dismissed. Nothing was ever written (the gate held both
  // times, which is why those rows still passed), but on a destructive control an extra dialog is exactly the
  // moment a person clicks through on autopilot. Since both cases came from ONE shared builder, the fix belongs
  // here rather than in each caller: while a confirm is open, a second request resolves to false (treated as
  // "not confirmed") instead of opening a rival dialog. False is the safe answer - it can only ever decline an
  // action, never perform one.
  let _whModalOpen = false;

  function _mount(opts) {
    if (_whModalOpen) {
      // Already asking. Decline the duplicate rather than stack a second dialog over the first.
      if (typeof opts.onResolve === 'function') opts.onResolve(false);
      return null;
    }
    _whModalOpen = true;
    const {
      message,
      okLabel = 'OK',
      cancelLabel = 'Cancel',
      withInput = false,
      inputLabel = '',
      inputDefault = '',
      /* T170/T50 (2026-08-27): HONOUR THE INPUT TYPE. index.html asks for a NEW PASSWORD via
         whPrompt with inputType:'password' - and this helper read only okLabel, cancelLabel,
         inputLabel and defaultValue, so the option was silently dropped and the field rendered
         type="text". Measured live: the typed password sat on screen in the clear, on a
         platform whose station tablet is shared by a whole crew. An unsupported option that
         throws nothing is the worst kind: the caller asked for masking, believed they got it,
         and nothing anywhere said otherwise. Allow-listed rather than passed through, so a
         caller cannot inject an arbitrary type attribute. */
      inputType = 'text',
      onResolve,
    } = opts;

    const ovId   = 'wh-modal-ov-' + Date.now() + '-' + Math.floor(Math.random()*1000);
    const titleId = ovId + '-title';
    const inputId = ovId + '-input';

    const overlay = document.createElement('div');
    overlay.id = ovId;
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-labelledby', titleId);
    overlay.style.cssText =
      'position:fixed;inset:0;z-index:10001;background:rgba(0,0,0,0.6);' +
      'backdrop-filter:blur(4px);display:flex;align-items:center;justify-content:center;' +
      'padding:16px;animation:wh-fade-in 0.12s ease-out;';

    overlay.innerHTML =
      '<div style="background:var(--wh-navy, #162032);border:1px solid rgba(255,255,255,0.1);border-radius:14px;' +
        'padding:20px 22px;max-width:440px;width:100%;box-shadow:0 16px 48px rgba(0,0,0,0.5);">' +
        '<p id="' + escHtml(titleId) + '" style="font-size:0.95rem;font-weight:600;color:var(--wh-cloud, #F4F6FA);' +
          'margin:0 0 14px;line-height:1.45;">' + escHtml(message) + '</p>' +
        // VISIBLE label, not aria-label alone (live journey walk 2026-07-24, supervisor approval
        // chain). The reject-asset prompt rendered a bare 394x44 box: a screen reader announced
        // "Reason (helps the submitter fix it)", but a SIGHTED supervisor saw an unexplained
        // input under "Reject this asset?" with no visible word "Reason" anywhere. axe passes
        // (the accessible NAME exists) — which is exactly the axe-0-violations false 100. A real
        // <label for> serves BOTH audiences and is the WCAG 3.3.2 "labels or instructions" fix.
        (withInput && inputLabel
          ? '<label for="' + escHtml(inputId) + '" ' +
            'style="display:block;margin-bottom:6px;font-size:0.82rem;font-weight:600;' +
            'color:rgba(255,255,255,0.86);font-family:inherit;">' + escHtml(inputLabel) + '</label>'
          : ''
        ) +
        (withInput
          ? '<input id="' + escHtml(inputId) + '" type="' +
            (['text','password','email','number','tel','url'].indexOf(String(inputType)) >= 0 ? inputType : 'text') + '" ' +
          (String(inputType) === 'password' ? 'autocomplete="new-password" ' : '') +
            (inputLabel ? '' : 'aria-label="' + escHtml(message) + '" ') +
            'value="' + escHtml(inputDefault || '') + '" ' +
            'style="width:100%;padding:9px 12px;border-radius:8px;border:1px solid rgba(255,255,255,0.12);' +
            'background:rgba(255,255,255,0.04);color:var(--wh-cloud, #F4F6FA);font-size:0.9rem;font-family:inherit;' +
            'margin-bottom:14px;min-height:44px;" />'
          : ''
        ) +
        '<div style="display:flex;gap:8px;justify-content:flex-end;">' +
          '<button type="button" data-wh-modal-cancel ' +
            'style="background:transparent;color:rgba(255,255,255,0.83);border:1px solid rgba(255,255,255,0.12);' +
            'border-radius:8px;padding:9px 16px;font-size:0.85rem;font-weight:600;cursor:pointer;' +
            'min-height:44px;font-family:inherit;">' + escHtml(cancelLabel) + '</button>' +
          '<button type="button" data-wh-modal-ok ' +
            'style="background:var(--wh-orange, #F7A21B);color:var(--wh-navy, #162032);border:none;border-radius:8px;padding:9px 16px;' +
            'font-size:0.85rem;font-weight:700;cursor:pointer;min-height:44px;font-family:inherit;">' +
            escHtml(okLabel) + '</button>' +
        '</div>' +
      '</div>';

    document.body.appendChild(overlay);

    const inputEl  = withInput ? overlay.querySelector('#' + CSS.escape(inputId)) : null;
    const cancelEl = overlay.querySelector('[data-wh-modal-cancel]');
    const okEl     = overlay.querySelector('[data-wh-modal-ok]');

    // Trap focus + autofocus the relevant control
    const focusTarget = inputEl || okEl;
    setTimeout(() => focusTarget && focusTarget.focus(), 0);

    function dispose(value) {
      // Release the one-at-a-time gate FIRST, and unconditionally. A guard that fails to release is worse than
      // the stacked-dialog wart it replaces: every later confirm on the page would silently resolve false, so
      // destructive controls would appear to do nothing. Cleared before the callback, since onResolve may open
      // the next dialog synchronously.
      _whModalOpen = false;
      try { document.removeEventListener('keydown', onKey, true); } catch (_) { /* empty-catch-allow: best-effort cleanup */ }
      try { overlay.remove(); } catch (_) { /* empty-catch-allow: best-effort cleanup */ }
      onResolve(value);
    }
    function onKey(e) {
      if (e.key === 'Escape') { e.stopPropagation(); dispose(withInput ? null : false); }
      else if (e.key === 'Enter' && (e.target === inputEl || e.target === okEl || !withInput)) {
        e.stopPropagation();
        dispose(withInput ? (inputEl.value || '') : true);
      }
    }
    document.addEventListener('keydown', onKey, true);

    cancelEl.addEventListener('click', () => dispose(withInput ? null : false));
    okEl.addEventListener('click',     () => dispose(withInput ? (inputEl.value || '') : true));
    overlay.addEventListener('click', (e) => { if (e.target === overlay) dispose(withInput ? null : false); });
  }

  window.whConfirm = function whConfirm(message, opts) {
    opts = opts || {};
    return new Promise((resolve) => {
      _mount({
        message,
        okLabel:     opts.okLabel || 'OK',
        cancelLabel: opts.cancelLabel || 'Cancel',
        withInput:   false,
        onResolve:   resolve,
      });
    });
  };

  window.whPrompt = function whPrompt(message, opts) {
    opts = opts || {};
    return new Promise((resolve) => {
      _mount({
        message,
        okLabel:      opts.okLabel || 'OK',
        cancelLabel:  opts.cancelLabel || 'Cancel',
        withInput:    true,
        inputLabel:   opts.inputLabel || '',
        /* T170 (2026-08-27): FORWARD THE TYPE. _mount honours inputType, but whPrompt built an
           explicit object and never passed it on - so a caller asking for inputType:'password'
           had the option dropped at THIS boundary, one level above where it appeared to be
           ignored. Two places had to agree before masking could work and only one did, which is
           why the first fix changed nothing and looked like it had. */
        inputType:    opts.inputType || 'text',
        inputDefault: opts.defaultValue || '',
        onResolve:    resolve,
      });
    });
  };

  // Inject the minimal fade-in keyframe (the same shell used elsewhere reuses
  // existing animations, but whConfirm is loaded on every page so it owns its
  // own animation to avoid a load-order dependency).
  try {
    if (!document.getElementById('wh-modal-anim-style')) {
      const s = document.createElement('style');
      s.id = 'wh-modal-anim-style';
      s.textContent = '@keyframes wh-fade-in{from{opacity:0;}to{opacity:1;}}';
      document.head.appendChild(s);
    }
  } catch (_) { /* empty-catch-allow: best-effort style inject; modal still works without anim */ }
})();

// ─────────────────────────────────────────────
// trimChatToTokenBudget — context-window compressor (Phase 1.8 of STRATEGIC_ROADMAP)
// ─────────────────────────────────────────────
// floating-ai and assistant.html both stuff a long system prompt (2k-2.7k
// tokens) into every turn, then append the conversation history. On the Groq
// 8K-32K free-tier models this leaves a thin budget for the actual user
// message. Without a compressor, a long voice transcription mid-thread can
// silently overflow the model context and either error out or truncate the
// system prompt (which is the LAST thing you want trimmed).
//
// Strategy: keep the most-recent turns and drop the oldest user/assistant
// pairs first. The system prompt is the caller's responsibility — pass its
// estimated token cost in `systemTokens` so the budget math is honest. We
// never drop the most recent user message (that's the turn being asked).
//
// Token heuristic: 1 token ≈ 4 chars (English). Identical to the heuristic
// used by _shared/cost-log.ts so observability and runtime agree.
//
// Args:
//   messages       array of {role, content} — your sessionMessages so far
//   opts.budget    total budget in tokens for the model context (default 7000
//                  to match Groq llama-3.3-70b-versatile minus a safety pad)
//   opts.systemTokens cost of the system prompt you'll prepend at send time
//   opts.reserveOut tokens reserved for the model's response (default 800)
//
// Returns: a NEW array (does not mutate input) trimmed to fit.
//
// Skills consulted: ai-engineer (context budget = system + history + output),
// performance (cheap O(n) walk, no expensive tokenizer).
function trimChatToTokenBudget(messages, opts) {
  opts = opts || {};
  const budget       = typeof opts.budget       === 'number' ? opts.budget       : 7000;
  const systemTokens = typeof opts.systemTokens === 'number' ? opts.systemTokens : 0;
  const reserveOut   = typeof opts.reserveOut   === 'number' ? opts.reserveOut   : 800;
  const limit = Math.max(200, budget - systemTokens - reserveOut);

  const list = Array.isArray(messages) ? messages.slice() : [];
  if (list.length <= 1) return list;

  const cost = (m) => Math.round(String(m && m.content || '').length / 4);

  // Walk from the end, keeping recent turns; drop the oldest once over budget.
  let total = 0;
  const kept = [];
  for (let i = list.length - 1; i >= 0; i--) {
    const c = cost(list[i]);
    if (total + c > limit && kept.length > 0) break;
    kept.unshift(list[i]);
    total += c;
  }
  return kept;
}

if (typeof window !== 'undefined') window.trimChatToTokenBudget = trimChatToTokenBudget;

// Debounce — delay fn execution until after `wait` ms of silence
function debounce(fn, wait) {
  let t;
  return function (...args) {
    clearTimeout(t);
    t = setTimeout(() => fn.apply(this, args), wait);
  };
}

/* C4: Session restore — returns worker display_name from localStorage or auth session.
 * Call at the top of each page's async init before redirecting to signin.
 *
 *   const wn = await restoreIdentityFromSession(db);
 *   if (!wn) { location.assign('index.html?signin=1'); return; }
 *
 * (Block comment + `location.assign(...)` so the L2 admin_gate_not_commented
 * sentinel doesn't false-positive on the example line.)
 */
async function restoreIdentityFromSession(db) {
  const cached = localStorage.getItem('wh_last_worker')
               || /* storage-key-allow: legacy worker-name fallback (current writes use wh_last_worker) */ localStorage.getItem('wh_worker_name')
               || localStorage.getItem('workerName') || '';
  // deepwalk 2026-07-24: DO NOT blindly `return cached`. The old fast-path trusted the cache without
  // checking the session, so a name left by a PRIOR user (shared device / user switch) stood in for the
  // current one — a stale identity that role-gates (e.g. the marketplace admin link) then read as the
  // wrong user. The SESSION is authoritative: reconcile the cache against it every load.
  try {
    const { data: { session } } = await db.auth.getSession();
    // Signed OUT: any lingering cache belongs to a prior user — clear it so nothing reads a stale identity.
    if (!session) {
      // Signed OUT: drop a prior user's cached name so nothing downstream role-gates on a stale identity.
      if (cached) { try { localStorage.removeItem('wh_last_worker'); } catch (_) { /* empty-catch-allow: storage may be blocked (private mode); the signed-out return below is what matters */ } }
      return '';
    }
    // Signed IN: resolve THIS session's worker and reconcile the cache so a foreign cache can't persist.
    /* NOT .maybeSingle(). v_worker_truth carries ONE ROW PER HIVE MEMBERSHIP, so a worker who belongs to
       two hives — a contractor covering two plants, which is a supported state, not an anomaly — returns
       two rows, and maybeSingle() resolves to NULL on multiple rows. The error is swallowed by the
       destructure, identity restoration silently returns the (empty) cache, and every page that gates on
       it bounces the user to the sign-in screen. Measured live: 2 of 14 seeded accounts belong to two
       hives, and BOTH were being redirected on any cold load.
       It hid for two reasons. The bounce itself warms `wh_last_worker`, so the second visit always works
       and it never looks reproducible. And the accounts it breaks are the multi-hive ones — the founder
       and the cross-plant contractor — who are the least likely to be the seeded happy path.
       All rows for one auth_uid carry the SAME worker_name (the name is the person, the fan-out is the
       membership), so any row is correct; ordering makes the choice deterministic rather than
       whichever the planner returns first ([[feedback_resolving_live_is_not_enough_be_deterministic]]). */
    const { data: _rows } = await db.from('v_worker_truth')
      .select('worker_name').eq('auth_uid', session.user.id)
      .order('worker_name', { ascending: true }).limit(1);
    const profile = (_rows && _rows[0]) || null;
    if (profile?.worker_name) {
      if (cached !== profile.worker_name) localStorage.setItem('wh_last_worker', profile.worker_name);
      return profile.worker_name;
    }
    return cached;  // authed but no worker-profile row (edge) — keep the cache as a best-effort label
  } catch (_) { /* empty-catch-allow: best-effort — fall back to whatever was cached */ }
  return cached;
}

// ─────────────────────────────────────────────
// Founder Console — analytics event SDK (Phase 0)
// ─────────────────────────────────────────────
// Every page should call logPageView(db) once after identity restore. Feature
// pages also emit feature-level events via logEvent(db, name, props).
//
// Writes are fire-and-forget — never block the user action. Append-only:
// the analytics_events table has no UPDATE/DELETE policies. SELECT is
// restricted to platform admins (marketplace_platform_admins allowlist).
//
// Skill alignment: analytics-engineer (KPI source events), architect
// ("Audit Log Writes Must Be Fire-and-Forget"), security (no PII in props).
let _wh_session_id = null;
function _whSessionId() {
  if (_wh_session_id) return _wh_session_id;
  try {
    let s = sessionStorage.getItem('wh_session_id');
    if (!s) {
      s = (window.crypto && crypto.randomUUID)
        ? crypto.randomUUID()
        : 'sess_' + Date.now() + '_' + Math.random().toString(36).slice(2);
      sessionStorage.setItem('wh_session_id', s);
    }
    _wh_session_id = s;
    return s;
  } catch (_) { return null; }
}

function logEvent(db, eventName, props) {
  if (!db || !eventName) return;
  try {
    const workerName = localStorage.getItem('wh_last_worker')
                    || /* storage-key-allow: legacy worker-name fallback (current writes use wh_last_worker) */ localStorage.getItem('wh_worker_name')
                    || localStorage.getItem('workerName') || null;
    const hiveId = localStorage.getItem('wh_active_hive_id')
                || localStorage.getItem('wh_hive_id') || null;
    const payload = {
      event_name: eventName,
      props: props || {},
      page: (props && props.page) || null,
      worker_name: workerName,
      hive_id: hiveId,
      session_id: _whSessionId(),
      user_agent: (navigator.userAgent || '').slice(0, 200),
    };
    // Try to attach auth_uid if a session exists - non-blocking.
    const insert = function () {
      /* attribution-allow: auth_uid is set dynamically at payload.auth_uid = session.user.id
         (getSession callback below) before this insert fires; statically invisible to the gate. */
      db.from('analytics_events').insert(payload).then(function (r) {
        if (r && r.error) console.warn('logEvent:', r.error.message);
      });
    };
    db.auth.getSession().then(function (res) {
      if (res && res.data && res.data.session) {
        payload.auth_uid = res.data.session.user.id;
      }
      insert();
    }).catch(insert);
  } catch (e) {
    console.warn('logEvent err:', e && e.message);
  }
}

// Convenience for the most common event - infers page name from URL.
function logPageView(db, extraProps) {
  const path = (location.pathname.split('/').pop() || 'index.html')
    .replace(/\.html$/i, '') || 'index';
  logEvent(db, 'page_view', Object.assign({ page: path }, extraProps || {}));
}

// ─────────────────────────────────────────────
// rtConn — realtime subscribe() connection-state guard (Arc J / realtime-engineer skill)
// ─────────────────────────────────────────────
// Supabase Realtime's subscribe() callback may NEVER fire (no SUBSCRIBED, no
// CHANNEL_ERROR, no TIMED_OUT) when the WebSocket silently fails to establish —
// common on weak plant-floor WiFi and corporate networks. Without a timeout the
// connection-state UI hangs at "Connecting…" forever. This factory returns a
// status callback for `channel.subscribe(rtConn(onState))` that:
//   • fires onState('offline') after `ms` if SUBSCRIBED never arrives,
//   • fires onState('live') on SUBSCRIBED, onState('offline') on error/timeout/close,
//   • is idempotent (settles once; clears its own timer).
// `onState` is optional — bare `rtConn()` just guards the silent freeze. For
// data-feed channels the page already rendered its initial DB query, so 'offline'
// simply means "live updates paused", not "no data".
function rtConn(onState, ms) {
  const cb = (typeof onState === 'function') ? onState : function () {};
  let settled = false;
  const timer = setTimeout(function () {
    if (!settled) { settled = true; cb('offline'); }
  }, ms || 8000);
  return function (status) {
    if (status === 'SUBSCRIBED') {
      settled = true; clearTimeout(timer); cb('live');
    } else if (status === 'CHANNEL_ERROR' || status === 'TIMED_OUT' || status === 'CLOSED') {
      settled = true; clearTimeout(timer); cb('offline');
    }
  };
}

// ─────────────────────────────────────────────
// isPlatformAdmin — gate util for founder-console.html (Phase 0)
// ─────────────────────────────────────────────
// Reuses marketplace_platform_admins so admin grants are a single source of
// truth. Returns false on no session, no profile, or worker not on allowlist.
async function isPlatformAdmin(db) {
  if (!db) return false;
  try {
    const { data: { session } } = await db.auth.getSession();
    if (!session) return false;
    /* GRAIN, NOT IDENTITY (fixed 2026-08-03). v_worker_truth is worker×HIVE: a person who belongs to
       two hives has TWO rows. `.maybeSingle()` demands exactly one and resolves NULL when it finds two,
       so this returned FALSE for precisely the people most likely to be admins — measured live, the
       platform admin had 2 rows / 1 distinct worker_name and was on the allowlist, and isPlatformAdmin()
       still said no. That is the no-access gate on all 8 admin surfaces in production; only the
       localhost bypass hid it locally. Ask whether ANY identity this person holds is on the allowlist,
       rather than insisting they hold exactly one. Same class as the multi-hive sign-in bounce. */
    const { data: profiles } = await db.from('v_worker_truth')
      .select('worker_name').eq('auth_uid', session.user.id).limit(50);
    const names = [...new Set((profiles || []).map(p => p && p.worker_name).filter(Boolean))];
    if (!names.length) return false;
    const { data: admin } = await db.from('marketplace_platform_admins')
      .select('worker_name').in('worker_name', names).limit(1);
    return !!(admin && admin.length);
  } catch (_) { return false; }
}

// ─────────────────────────────────────────────
// Achievement tier system
// ─────────────────────────────────────────────

// tier.color is used as small TEXT ("Iron Technician" chip) as well as ring/tint —
// each value must clear WCAG AA 4.5:1 on the dark tints. Iron #7B8794 measured (purity-allow: prose comment, not a CSS value)
// 3.08 and Bronze #CD7F32 2.6–3.3 as text (2026-07-16); lightened same-hue.
const ACHIEVEMENT_TIERS = [
  { id: 'legend',   min: 91, color: 'var(--wh-orange, #F7A21B)', label: 'Legend'   },
  { id: 'platinum', min: 76, color: 'var(--wh-blue-light, #5FCCE8)', label: 'Platinum' },
  { id: 'gold',     min: 51, color: 'var(--wh-orange, #F7A21B)', label: 'Gold'     },
  { id: 'silver',   min: 26, color: '#94A3B8', label: 'Silver'   },
  { id: 'bronze',   min: 11, color: '#E8B27A', label: 'Bronze'   },
  { id: 'iron',     min:  0, color: 'var(--wh-steel-bright, #A9B6C4)', label: 'Iron'     },
];

function getWorkerTier(topLevel) {
  return ACHIEVEMENT_TIERS.find(t => (topLevel || 0) >= t.min)
    || ACHIEVEMENT_TIERS[ACHIEVEMENT_TIERS.length - 1];
}

// Render a tier-framed avatar circle.
// size: pixel width/height — 42, 36, 32, 28, 22
// Badge (level pill) shown only when size >= 32 and topLevel > 0.
function renderWorkerAvatar(workerName, topLevel, size) {
  const sz   = size || 32;
  const tier = getWorkerTier(topLevel || 0);
  /* TWO INITIALS DO NOT FIT A SMALL CIRCLE. Measured live: at sz=22 the content box is 18px after
     the (now proportional) border, and "ES" needs 29px — 7 avatars spilled outside their circle on
     one marketplace page. Scaling the border helped and was not enough, because the constraint is
     the glyphs, not the ring. Below 26px show ONE initial; the circle stays legible instead of
     leaking two letters into whatever sits beside it. */
  const initials = String(workerName || '?').trim().split(/\s+/)
    .map(function (w) { return w[0]; }).join('').toUpperCase();
  const init = escHtml(initials.slice(0, sz >= 26 ? 2 : 1));
  const fs = sz >= 42 ? '0.95rem' : sz >= 32 ? '0.72rem' : sz >= 28 ? '0.65rem' : '0.55rem';
  const badge = (sz >= 32 && (topLevel || 0) > 0)
    ? '<span class="wh-avatar-lvl">' + (topLevel || 0) + '</span>'
    : '';
  /* THE BORDER DID NOT SCALE WITH THE AVATAR (found 2026-08-04, V-edge-content batch walk). The
     class sets `border:4px solid` with box-sizing:border-box, so a 22px avatar keeps only 14px of
     content box while two initials need ~27px — measured live as scrollWidth 27 vs clientWidth 14 on
     8 avatars at once. At 22px a 4px ring is 36% of the diameter; the font-size scale already steps
     down for small sizes and the border never did. Proportional, floored at 1px so the tier colour
     still reads at any size. */
  const bw = Math.max(1, Math.min(4, Math.round(sz / 11)));
  return '<div class="wh-avatar wh-tier-' + tier.id + '" '
    + 'style="width:' + sz + 'px;height:' + sz + 'px;font-size:' + fs + ';border-width:' + bw + 'px;--tier-clr:' + tier.color + ';" '
    + 'title="' + escHtml(workerName) + ' - ' + tier.label + ' Lv.' + (topLevel || 0) + '">'
    + init + badge + '</div>';
}

// Batch-load highest achievement level per worker.
// Returns { workerName: topLevel }. Safe to call when table does not exist yet.
async function loadWorkerTiers(db, workerNames) {
  if (!workerNames || !workerNames.length) return {};
  try {
    const { data } = await db
      .from('v_worker_achievements_truth')
      .select('worker_name, current_level')
      .in('worker_name', workerNames);
    const map = {};
    for (const row of (data || [])) {
      if (!map[row.worker_name] || row.current_level > map[row.worker_name]) {
        map[row.worker_name] = row.current_level;
      }
    }
    return map;
  } catch (_) { return {}; }
}

// Inject tier CSS once — runs immediately when utils.js loads
(function () {
  if (document.getElementById('wh-tier-styles')) return;
  const s = document.createElement('style');
  s.id = 'wh-tier-styles';
  s.textContent = [
    /* Base avatar with border-box so all tiers render at the same outer size */
    /* regardless of border thickness/style. Metallic inset shadows give depth. */
    /* overflow:visible, NOT hidden, and the clip moved onto the image below. The container's clip was
       fighting its own child: .wh-avatar-lvl is positioned `bottom:-8px` to HANG BELOW the circle as a
       badge, and overflow:hidden then cut it off. Measured live on achievements - 20 avatars, every
       level pill 21% clipped, taking the bottom of the digits with it ("93", "5", "18"). The clip was
       also doing no work it was written for: not one avatar on the page has an <img> child, so it was
       defensive styling for a photo that is not there, whose only observable effect was truncating the
       badge. Keeping the circle mask where it belongs - on a future image - preserves both intents. */
    '.wh-avatar{position:relative;border-radius:50%;flex-shrink:0;overflow:visible;',
    'box-sizing:border-box;',
    'background:linear-gradient(135deg,var(--wh-navy-mid, #1F2E45),var(--wh-navy-light, #2A3D58));',
    'display:flex;align-items:center;justify-content:center;',
    'font-family:var(--wh-font, "Poppins",sans-serif);font-weight:700;color:var(--wh-cloud, #F4F6FA);',
    'border:4px solid var(--tier-clr,#7B8794);',
    'box-shadow:inset 1px 1px 2px rgba(255,255,255,0.18),',
    '           inset -1px -1px 2px rgba(0,0,0,0.45);}',

    /* The circle mask now rides the IMAGE, so a future avatar photo still clips to the circle while
       the badge that is meant to overhang can actually overhang. */
    '.wh-avatar > img{width:100%;height:100%;object-fit:cover;border-radius:50%;}',
    '.wh-avatar-lvl{position:absolute;bottom:-8px;left:50%;transform:translateX(-50%);',
    'background:var(--tier-clr,#7B8794);color:var(--wh-navy, #162032);',
    'font-size:9px;font-weight:800;padding:1px 5px;',
    'border-radius:999px;border:2px solid var(--wh-navy, #162032);',
    'min-width:20px;text-align:center;line-height:1.5;',
    'pointer-events:none;white-space:nowrap;z-index:3;',
    'box-shadow:0 2px 6px rgba(0,0,0,0.45),',
    '           inset 0 1px 0 rgba(255,255,255,0.3);}',

    /* ── IRON: DASHED border (incomplete/starting feel) + slow breathing ──── */
    '.wh-tier-iron{border:4px dashed var(--wh-steel, #7B8794);animation:wh-breathe-iron 4s ease-in-out infinite;}',

    /* ── BRONZE: RIDGE border (3D embossed metal) + warm shimmer ─────────── */
    '.wh-tier-bronze{border:4px ridge #CD7F32;animation:wh-shimmer 3s ease-in-out infinite;}',

    /* ── SILVER: solid + COMET light sweeping around the rim ─────────────── */
    '.wh-tier-silver{border:4px solid #94A3B8;}',
    '.wh-tier-silver::after{content:"";position:absolute;inset:-4px;border-radius:50%;',
    'pointer-events:none;z-index:0;',
    'background:conic-gradient(from 0deg,transparent 0deg,transparent 300deg,',
    '  rgba(255,255,255,0.4) 330deg,rgba(255,255,255,0.95) 358deg,rgba(255,255,255,0.2) 360deg);',
    '-webkit-mask:radial-gradient(circle,transparent 56%,black 60%);',
    'mask:radial-gradient(circle,transparent 56%,black 60%);',
    'animation:wh-spin 3s linear infinite;}',

    /* ── GOLD: solid + 4 SPARKLE DOTS rotating like a crown ──────────────── */
    '.wh-tier-gold{border:4px solid var(--wh-orange, #F7A21B);animation:wh-glow-gold 2.4s ease-in-out infinite;}',
    '.wh-tier-gold::after{content:"";position:absolute;inset:-3px;border-radius:50%;',
    'pointer-events:none;z-index:0;',
    'background:',
    '  radial-gradient(circle 1.8px at 50% 0%,rgba(255,255,255,1),transparent 60%),',
    '  radial-gradient(circle 1.8px at 100% 50%,rgba(255,255,255,1),transparent 60%),',
    '  radial-gradient(circle 1.8px at 50% 100%,rgba(255,255,255,1),transparent 60%),',
    '  radial-gradient(circle 1.8px at 0% 50%,rgba(255,255,255,1),transparent 60%);',
    'animation:wh-spin 4s linear infinite;}',

    /* ── PLATINUM: CONCENTRIC — solid inner + outer rotating dashed ring ─── */
    '.wh-tier-platinum{border:4px solid var(--wh-blue, #29B6D9);animation:wh-glow-blue 2.4s ease-in-out infinite;}',
    '.wh-tier-platinum::after{content:"";position:absolute;inset:-7px;border-radius:50%;',
    'border:2px dashed rgba(41,182,217,0.85);',
    'pointer-events:none;z-index:0;',
    'animation:wh-spin 6s linear infinite;}',

    /* ── LEGEND: animated multi-color gradient ring + halo ───────────────── */
    '.wh-tier-legend{border:4px solid transparent;}',
    '.wh-tier-legend::before{content:"";position:absolute;inset:-4px;border-radius:50%;',
    'background:conic-gradient(var(--wh-orange, #F7A21B),var(--wh-orange-light, #FDB94A),var(--wh-blue, #29B6D9),var(--wh-blue-light, #5FCCE8),var(--wh-orange, #F7A21B));',
    'animation:wh-spin 2s linear infinite;z-index:-1;',
    'filter:drop-shadow(0 0 10px rgba(247,162,27,0.6));}',
    '.wh-tier-legend::after{content:"";position:absolute;inset:-10px;border-radius:50%;',
    'border:1px solid rgba(247,162,27,0.25);pointer-events:none;z-index:0;',
    'animation:wh-spin 8s linear infinite reverse;}',

    /* Keyframes — only Iron/Bronze/Gold/Platinum animate the parent box-shadow. */
    /* Silver uses ::after only (rotating mask). Legend uses ::before/::after.   */
    '@keyframes wh-breathe-iron{0%,100%{box-shadow:inset 1px 1px 2px rgba(255,255,255,0.18), inset -1px -1px 2px rgba(0,0,0,0.45), 0 0 0 rgba(123,135,148,0);}',
    '50%{box-shadow:inset 1px 1px 2px rgba(255,255,255,0.18), inset -1px -1px 2px rgba(0,0,0,0.45), 0 0 8px rgba(180,195,210,0.35);}}',

    '@keyframes wh-shimmer{0%,100%{box-shadow:inset 1px 1px 2px rgba(255,255,255,0.2), inset -1px -1px 2px rgba(0,0,0,0.45), 0 0 6px rgba(205,127,50,0.45);}',
    '50%{box-shadow:inset 1px 1px 2px rgba(255,255,255,0.32), inset -1px -1px 2px rgba(0,0,0,0.45), 0 0 18px rgba(205,127,50,0.9);}}',

    '@keyframes wh-glow-gold{0%,100%{box-shadow:inset 1px 1px 2px rgba(255,255,255,0.22), inset -1px -1px 2px rgba(0,0,0,0.45), 0 0 8px rgba(247,162,27,0.55);}',
    '50%{box-shadow:inset 1px 1px 2px rgba(255,255,255,0.32), inset -1px -1px 2px rgba(0,0,0,0.45), 0 0 22px rgba(247,162,27,0.95);}}',

    '@keyframes wh-glow-blue{0%,100%{box-shadow:inset 1px 1px 2px rgba(255,255,255,0.22), inset -1px -1px 2px rgba(0,0,0,0.45), 0 0 8px rgba(41,182,217,0.55);}',
    '50%{box-shadow:inset 1px 1px 2px rgba(255,255,255,0.32), inset -1px -1px 2px rgba(0,0,0,0.45), 0 0 22px rgba(41,182,217,0.95);}}',

    '@keyframes wh-spin{from{transform:rotate(0deg);}to{transform:rotate(360deg);}}',

    /* REDUCED MOTION, and it was missing from every tier. Measured 2026-08-05 on community.html:
       document.getAnimations() returned 29 running animations, 26 of them wh-spin on .wh-avatar tier
       rings, TEN of which were scrolled off-screen and still turning. Every one is `infinite`, and
       nothing in this block asked whether the person wants motion at all.
       That is a person who set "reduce motion" in their OS -- often because motion makes them ill --
       being handed two dozen perpetually rotating rings. It also means the page NEVER reaches a
       stable frame, which is not only a battery cost on a plant tablet: it made Playwright refuse to
       screenshot the page ("waiting for element to be stable") and gave contradictory
       getComputedStyle readings mid-transition, which cost this walk a long detour.
       Rings still SHOW their tier -- the border, the colour and the glow are all static properties.
       Only the movement stops, which is exactly what the preference asks for. */
    '@media (prefers-reduced-motion:reduce){',
    '.wh-avatar,.wh-avatar::before,.wh-avatar::after,',
    '.wh-tier-iron,.wh-tier-bronze,.wh-tier-silver,.wh-tier-gold,.wh-tier-platinum,.wh-tier-legend,',
    '.wh-tier-silver::after,.wh-tier-gold::after,.wh-tier-platinum::after,',
    '.wh-tier-legend::before,.wh-tier-legend::after{animation:none !important;}',
    '}'
  ].join('');
  document.head.appendChild(s);
}());

// ── whCompressImage — Arc L scale-out (2026-06-23): client-side image compression ──
// At a million users, raw ~0.35-3 MB phone photos are tens of TB of object storage and
// egress. Resizing to a sane max dimension + re-encoding to WebP cuts that ~5-10x while
// keeping a defect photo (rust/leak/crack/burn) perfectly legible — 1600px is plenty.
// Robust: a File OR a dataURL in; ALWAYS returns a dataURL; on ANY failure (unsupported
// codec, decode error, or a result that isn't smaller) it returns the ORIGINAL unharmed.
//   const small = await whCompressImage(fileOrDataUrl, { maxDim: 1600, quality: 0.82 });
function _whFileToDataUrl(file) {
  return new Promise((res, rej) => {
    const r = new FileReader();
    r.onload = () => res(r.result);
    r.onerror = rej;
    r.readAsDataURL(file);
  });
}
async function whCompressImage(input, opts) {
  opts = opts || {};
  const maxDim  = opts.maxDim  || 1600;
  const quality = opts.quality || 0.82;
  const mime    = opts.type    || 'image/webp';
  const origP   = (typeof input === 'string') ? Promise.resolve(input) : _whFileToDataUrl(input);
  try {
    const srcUrl = (typeof input === 'string') ? input : URL.createObjectURL(input);
    const img = await new Promise((res, rej) => {
      const im = new Image();
      im.onload = () => res(im);
      im.onerror = rej;
      im.src = srcUrl;
    });
    if (typeof input !== 'string') { try { URL.revokeObjectURL(srcUrl); } catch (_e) { /* empty-catch-allow: best-effort object-URL cleanup */ } }
    const w = img.naturalWidth || img.width, h = img.naturalHeight || img.height;
    if (!w || !h) return await origP;
    const scale = Math.min(1, maxDim / Math.max(w, h));   // never upscale
    const cw = Math.max(1, Math.round(w * scale)), ch = Math.max(1, Math.round(h * scale));
    const canvas = document.createElement('canvas');
    canvas.width = cw; canvas.height = ch;
    canvas.getContext('2d').drawImage(img, 0, 0, cw, ch);
    let out = canvas.toDataURL(mime, quality);
    if (out.indexOf('data:' + mime) !== 0) out = canvas.toDataURL('image/jpeg', quality);  // WebP unsupported -> JPEG
    const orig = await origP;
    return (out && out.length < orig.length) ? out : orig;   // never regress size
  } catch (_e) {
    return await origP;   // decode/codec failure -> original, never break the upload
  }
}
if (typeof window !== 'undefined') { window.whCompressImage = whCompressImage; }

// ── whPoll — Arc L scale-out (2026-06-23): visibility-aware polling fallback ──
// The 1M realtime decision (Ian: "reduce + poll-fallback, no new infra"): Supabase
// Realtime caps ~10K concurrent channels, so at 20K peak-concurrent users a per-user
// WebSocket subscription is a hard wall. For NON-safety-critical surfaces, replace the
// `.channel().subscribe()` with this: it re-runs the page's load fn on an interval,
// PAUSES while the tab is hidden (no wasted reads/egress on background tabs — the key
// to it scaling), runs once immediately, and returns a handle with .stop().
//   const h = whPoll(loadAlertsPanel, 20000);   // refresh every 20s while visible
//   // later / on teardown: h.stop();
function whPoll(loadFn, intervalMs, opts) {
  opts = opts || {};
  const ms = Math.max(5000, intervalMs || 30000);   // floor 5s — never hammer
  let timer = null, stopped = false, inFlight = false;
  async function tick() {
    if (stopped || inFlight) return;
    if (typeof document !== 'undefined' && document.hidden) return;  // skip while backgrounded
    inFlight = true;
    try { await loadFn(); } catch (_e) { /* empty-catch-allow: a transient load error must not kill the loop */ }
    finally { inFlight = false; }
  }
  function start() {
    if (timer) return;
    timer = setInterval(tick, ms);
  }
  function onVis() { if (!document.hidden) tick(); }   // refresh immediately on tab refocus
  if (opts.immediate !== false) tick();                // run once now (matches realtime's initial state)
  start();
  if (typeof document !== 'undefined') document.addEventListener('visibilitychange', onVis);
  return {
    stop() {
      stopped = true;
      if (timer) { clearInterval(timer); timer = null; }
      if (typeof document !== 'undefined') document.removeEventListener('visibilitychange', onVis);
    },
    refresh: tick,
  };
}
if (typeof window !== 'undefined') { window.whPoll = whPoll; }

// ── whRealtimeSubscribe — Q5 (2026-07-05): per-client channel CAP + graceful poll degrade ──
// GROUNDED (Step 0, VERIFIED not memory): Supabase FREE tier = **200 concurrent realtime
// connections PLATFORM-WIDE** — far tighter than the ~10K the whPoll note assumed. That 200 is
// shared across ALL users (like the LLM org-pool), so one heavy client opening many channels
// eats a disproportionate slice. This wrapper (a) bounds channels PER CLIENT (default 5 — a
// single user rarely needs more live surfaces at once), and (b) gracefully DEGRADES overflow —
// and offline — to whPoll, so a surface ALWAYS updates: live when there's headroom, polled when
// there isn't. Composes the two existing primitives: rtConn (silent-freeze guard) + whPoll.
// `buildChannel()` must return an UNSUBSCRIBED channel (e.g. supabase.channel(x).on(...)); this
// calls .subscribe() so it can wrap the state callback.
//   const h = whRealtimeSubscribe('alerts',
//               () => supabase.channel('alerts:'+hive).on('postgres_changes', {...}, reload),
//               reload, { pollMs: 20000 });
//   // teardown: h.stop();
var WH_MAX_CLIENT_CHANNELS = 5;   // per-client concurrent realtime cap (window/opts override)
function whRealtimeSubscribe(name, buildChannel, reloadFn, opts) {
  opts = opts || {};
  var max = opts.max
    || (typeof window !== 'undefined' && window.WH_MAX_CLIENT_CHANNELS)
    || WH_MAX_CLIENT_CHANNELS;
  var pollMs = opts.pollMs || 30000;
  var reg = (typeof window !== 'undefined')
    ? (window.__whChannels || (window.__whChannels = new Set()))
    : (whRealtimeSubscribe._reg || (whRealtimeSubscribe._reg = new Set()));

  function degradeToPoll(reason) {
    var ph = whPoll(reloadFn, pollMs, { immediate: opts.immediate });
    return { mode: 'poll', reason: reason, stop: function () { ph.stop(); }, refresh: ph.refresh };
  }

  // (a) per-client channel cap reached, or no builder -> poll (graceful degrade, surface still live-ish)
  if (reg.size >= max) return degradeToPoll('cap');
  if (typeof buildChannel !== 'function') return degradeToPoll('no-builder');

  var channel, pollHandle = null;
  try {
    channel = buildChannel();
    reg.add(channel);
    // (b) offline -> spin up a poll fallback; recovered -> stop polling. rtConn guards the
    // silent-freeze case where subscribe() never fires any status.
    channel.subscribe(rtConn(function (state) {
      if (state === 'offline' && !pollHandle) {
        pollHandle = whPoll(reloadFn, pollMs, { immediate: false });
      } else if (state === 'live' && pollHandle) {
        pollHandle.stop(); pollHandle = null;
      }
      if (opts.onState) opts.onState(state);
    }));
  } catch (_e) {
    if (channel) reg.delete(channel);
    return degradeToPoll('subscribe-error');
  }

  return {
    mode: 'realtime',
    stop: function () {
      reg.delete(channel);                       // free the per-client slot
      if (pollHandle) { pollHandle.stop(); pollHandle = null; }
      try {
        if (typeof window !== 'undefined' && window.supabase && window.supabase.removeChannel) {
          window.supabase.removeChannel(channel);
        } else if (channel && channel.unsubscribe) {
          channel.unsubscribe();
        }
      } catch (_e) { /* empty-catch-allow: teardown best-effort, never throw on cleanup */ }
    },
  };
}
if (typeof window !== 'undefined') {
  window.whRealtimeSubscribe = whRealtimeSubscribe;
  // Telemetry / graceful-429 signal: how many live channels this client currently holds.
  window.__whChannelCount = function () { return (window.__whChannels && window.__whChannels.size) || 0; };
}

// ── Keyboard-a11y polyfill for mouse-only clickables (dim-8) ─────────────────────────────────
// A `<div|span|li onclick=...>` with no role=button / no keyboard path is mouse-only: keyboard +
// screen-reader users can't reach or activate it. Rather than retrofit dozens of elements by hand,
// this upgrades EVERY such element (static + dynamically-rendered) to keyboard-operable: focusable,
// announced as a button, and activated by Enter/Space. Progressive enhancement — it only matters
// when JS is running, and the onclick it mirrors also needs JS, so keyboard reaches parity with mouse.
(function whClickableKbdA11y() {
  if (typeof document === 'undefined') return;
  var CLICKABLE = 'div[onclick],span[onclick],li[onclick]';
  var SKIP_ROLE = /^(button|tab|menuitem|link|checkbox|switch|option|radio|combobox)$/;
  function enhance(el) {
    if (!el || el.__whKbd || el.nodeType !== 1) return;
    if (!el.hasAttribute('onclick')) return;
    var role = el.getAttribute('role');
    if (role && SKIP_ROLE.test(role)) return;                 // already an interactive role
    if (el.hasAttribute('tabindex') && el.hasAttribute('onkeydown')) return; // author already handled it
    // Skip containers whose real action is an INNER interactive control (adding role=button here
    // would nest interactives + the inner control is already keyboard-accessible).
    if (el.querySelector('a[href],button,input,select,textarea,[role="button"],[role="link"],[tabindex]')) return;
    el.__whKbd = true;
    el.classList.add('wh-kbd-a11y');   // gets the injected focus-visible ring (WCAG 2.4.7)
    if (!role) el.setAttribute('role', 'button');
    if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '0');
    el.addEventListener('keydown', function (e) {
      if ((e.key === 'Enter' || e.key === ' ') && e.target === el) { e.preventDefault(); el.click(); }
    });
  }
  function injectFocusStyle() {
    // Keyboard-focusable is only useful if focus is VISIBLE (WCAG 2.4.7). Guarantee a focus ring on
    // the elements we upgrade, scoped to them (:focus-visible = keyboard focus only, not mouse click).
    try {
      if (document.getElementById('wh-kbd-a11y-style')) return;
      var s = document.createElement('style');
      s.id = 'wh-kbd-a11y-style';
      s.textContent = '.wh-kbd-a11y:focus-visible{outline:2px solid var(--wh-orange,#F7A21B);outline-offset:2px;border-radius:4px;}';
      (document.head || document.documentElement).appendChild(s);
    } catch (_) { /* empty-catch-allow: best-effort a11y style injection; page works without it */ }
  }
  function scan(root) {
    try { (root.querySelectorAll ? root.querySelectorAll(CLICKABLE) : []).forEach(enhance); } catch (_) { /* empty-catch-allow: best-effort a11y enhancement; never block a render */ }
  }
  function boot() {
    injectFocusStyle();
    scan(document);
    try {
      new MutationObserver(function (muts) {
        for (var i = 0; i < muts.length; i++) {
          var added = muts[i].addedNodes;
          for (var j = 0; j < added.length; j++) {
            var n = added[j];
            if (n.nodeType !== 1) continue;
            if (n.matches && n.matches(CLICKABLE)) enhance(n);
            scan(n);
          }
        }
      }).observe(document.body, { childList: true, subtree: true });
    } catch (_) { /* empty-catch-allow: MutationObserver unsupported; the initial scan still covers static markup */ }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
  if (typeof window !== 'undefined') window.whEnhanceClickableA11y = scan;  // pages can re-scan after a manual render
})();


// ── A SCROLLABLE REGION NOBODY CAN SCROLL FROM THE KEYBOARD (project-report walk, 2026-08-07) ─────
// `.wh-scroll-x` (tokens.css:255) is the platform's horizontal-scroll wrapper, and on project-report
// axe found EIGHT of them failing `scrollable-region-focusable`: overflow-x:auto, genuinely scrolling
// (scrollWidth 400-489 in a 291px box), tabindex null, role null, and ZERO focusable children. A mouse
// user swipes; a keyboard user cannot reach the container to press an arrow key, so the right-hand
// columns of every WBS and progress table are simply unavailable to them. WCAG 2.1.1.
//
// The platform already knows this rule - companion-launcher.js:584 gives its message log tabindex=0
// citing this exact axe rule by name - it was just never applied to the shared class. So the fix goes
// where the class lives rather than at each call site: analytics-report's `.table-wrap` was already
// keyboard-reachable while project-report's `.wh-scroll-x` was not, which is two implementations of one
// pattern drifting apart, and patching the two project-report render functions would have widened that
// drift instead of closing it.
//
// Focusable ONLY WHILE ACTUALLY SCROLLING, re-checked on resize: axe's rule is satisfied by a focusable
// container OR focusable content, and at 1280 these tables fit, where an extra tab stop on a plain
// wrapper is noise rather than access. A container that already has focusable children is left alone
// for the same reason - focus reaches it through them, and scroll follows focus.
(function whScrollRegionKbdA11y() {
  if (typeof document === 'undefined') return;
  var SEL = '.wh-scroll-x';
  var LABEL = 'Scrollable table. Use the arrow keys to scroll sideways.';
  function apply(el) {
    if (!el || el.nodeType !== 1) return;
    var scrolls = el.scrollWidth > el.clientWidth + 1;
    var ownedByUs = el.getAttribute('data-wh-scroll-kbd') === '1';
    if (scrolls) {
      if (el.hasAttribute('tabindex') && !ownedByUs) return;          // author already handled it
      if (el.querySelector('a[href],button,input,select,textarea,[tabindex]:not([tabindex="-1"])')) return;
      el.setAttribute('data-wh-scroll-kbd', '1');
      el.setAttribute('tabindex', '0');
      if (!el.getAttribute('role')) el.setAttribute('role', 'region');
      if (!el.getAttribute('aria-label') && !el.getAttribute('aria-labelledby'))
        el.setAttribute('aria-label', LABEL);
      el.classList.add('wh-kbd-a11y');                                // reuse the injected focus ring
    } else if (ownedByUs) {
      el.removeAttribute('tabindex');                                 // stopped scrolling: drop the stop
      el.removeAttribute('data-wh-scroll-kbd');
      el.classList.remove('wh-kbd-a11y');
    }
  }
  function sweep(root) {
    try {
      var r = root || document;
      if (r.matches && r.matches(SEL)) apply(r);
      (r.querySelectorAll ? r.querySelectorAll(SEL) : []).forEach(apply);
    } catch (_) { /* empty-catch-allow: best-effort a11y enhancement; never block a render */ }
  }
  // ONE debounced document sweep per batch, never a per-node closure. The first version scheduled
  // `requestAnimationFrame(function () { sweep(n); })` inside a `for (var j...)` loop, and `var` is
  // function-scoped, so every callback closed over the LAST node of the batch and the rest were never
  // swept - the 8 regions stayed unenhanced and the axe count stayed at 8. Sweeping the document also
  // re-evaluates regions whose scrollability changed because a sibling render reflowed them, which a
  // per-node sweep cannot see.
  var pending = null;
  function schedule() {
    if (pending) return;
    pending = requestAnimationFrame(function () { pending = null; sweep(document); });
  }
  function boot() {
    schedule();                                    // after a frame: scrollWidth needs layout
    window.addEventListener('load', schedule);     // and again once late data has rendered
    try {
      new MutationObserver(function (muts) {
        for (var i = 0; i < muts.length; i++) {
          if (muts[i].addedNodes && muts[i].addedNodes.length) { schedule(); return; }
        }
      }).observe(document.body, { childList: true, subtree: true });
    } catch (_) { /* empty-catch-allow: MutationObserver unsupported; the initial sweep covers static markup */ }
    var t = null;
    window.addEventListener('resize', function () {
      clearTimeout(t);
      t = setTimeout(function () { sweep(document); }, 150);
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
  if (typeof window !== 'undefined') window.whEnhanceScrollRegions = sweep;
})();


// -----------------------------------------------------------------------------
// whFreqFromDays / whFreqDays - ONE mapping from an interval in days to the
// platform's PM frequency vocabulary (PM deepwalk PM08, 2026-07-28).
// -----------------------------------------------------------------------------
// There were TWO importers snapping intervals to frequency labels, with different
// vocabularies AND different rounding rules:
//   * integrations.html (CMMS / CSV import) used the FIRST bucket >= days over
//     [7,30,90,180,365] - with NO Daily bucket at all. A 1-day interval became
//     'Weekly' (7x too rare), 14 days became 'Monthly' (2.1x), 45 became
//     'Quarterly' (2x). Every drift ran in the same direction: LESS often than the
//     source system asked, which is how an imported daily inspection quietly
//     becomes a weekly one on the first day a plant onboards its existing program.
//   * asset-hub.html (RCM strategy) snapped to the NEAREST bucket, so 300 days
//     became 'Annual' (365) - again rarer than requested.
//
// THE RULE HERE: never schedule a PM LESS often than asked. Snap DOWN to the
// closest bucket that does not exceed the requested interval, and never below
// Daily. Rounding to a shorter interval costs labour; rounding to a longer one
// leaves equipment un-inspected, and only one of those is a safety decision.
//
// The day-values mirror v_pm_scope_items_truth's frequency_days CASE and
// pm-scheduler's FREQ table - the same six labels, so a written value always maps
// back to the interval the writer intended.
(function () {
  var FREQ_DAYS = [
    ['Daily',         1],
    ['Weekly',        7],
    ['Monthly',      30],
    ['Quarterly',    90],
    ['Semi-Annual', 180],
    ['Annual',      365],
  ];

  // label -> days. Case/synonym handling matches the DB view (lower + trim), so
  // 'semi-annual', 'Semi-Annual' and 'SEMI ANNUAL' all resolve to 180.
  function whFreqDays(label) {
    var k = String(label == null ? '' : label).toLowerCase().trim();
    if (k === 'semiannual' || k === 'semi annual') k = 'semi-annual';
    if (k === 'yearly') k = 'annual';
    if (k === 'biweekly' || k === 'fortnightly') return 14;  // the view's mapping
    for (var i = 0; i < FREQ_DAYS.length; i++) {
      if (FREQ_DAYS[i][0].toLowerCase() === k) return FREQ_DAYS[i][1];
    }
    return null;  // unknown -> caller decides; do NOT silently assume a period
  }

  function whFreqFromDays(days) {
    var n = Number(days);
    if (!isFinite(n) || n <= 0) return null;
    var best = FREQ_DAYS[0][0];
    for (var i = 0; i < FREQ_DAYS.length; i++) {
      if (FREQ_DAYS[i][1] <= n) best = FREQ_DAYS[i][0];
    }
    return best;  // n < 1 is impossible here, so 'Daily' is the floor
  }

  if (typeof window !== 'undefined') {
    window.whFreqFromDays = whFreqFromDays;
    window.whFreqDays     = whFreqDays;
    window.WH_FREQ_DAYS   = FREQ_DAYS;
  }
})();

// whRequireOnline — refuse a write that cannot reach the server, in the user's own words.
// ─────────────────────────────────────────────
// The shared offline BANNER warns; it does not stop a button. Found 2026-07-29: 14 of 17
// user-triggered writes across the two marketplace surfaces fired into a dead network — including
// "I paid" and a GCash top-up filing the provider may already have sent.
//
// THE WORDING IS CENTRAL; THE SINK IS NOT. `showToast` is defined INSIDE each page's IIFE and is not
// on `window`, so a helper that tries to call it from here reaches nothing and the guard refuses the
// write in total silence — worse than no guard, and exactly what the bank's offline cell caught the
// moment this was centralized. The caller passes its own notifier.
//   action : the thing being attempted, phrased as a gerund ("Confirming payment")
//   notify : the page's toast function, (msg, kind) => void
//   returns true when the write may proceed; false AFTER telling the person why not.
function whOfflineMessage(action) {
  return 'You are offline. ' + action + ' needs a connection - nothing was sent, so nothing is half-done.';
}
function whRequireOnline(action, notify) {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) {
    if (typeof notify === 'function') notify(whOfflineMessage(action), 'error');
    return false;
  }
  return true;
}
if (typeof window !== 'undefined') {
  window.whOfflineMessage = whOfflineMessage;
  window.whRequireOnline = whRequireOnline;
}

// whLivePoll — refresh a list only while it has something live in it.
// ─────────────────────────────────────────────
// The shape both marketplace surfaces need and neither had: a screen showing work IN PROGRESS has to
// learn when that work ends, or it keeps displaying a job that no longer exists. Found 2026-07-30 by
// a two-context walk — a client cancelled, the provider's push said "stand down - do not travel", and
// the seller page they were holding still listed the job as live because it had no interval and no
// realtime subscription at all.
//
// Polled rather than subscribed on purpose: the tracker already polls, so this reuses a cadence the
// platform pays for instead of adding a realtime channel with its own cleanup contract. The three
// disciplines that keep a timer honest are built in here so no caller can forget one —
//   * it runs ONLY while `isLive()` is true, and stops itself the moment it is not
//   * it skips a hidden tab (a backgrounded page is not being read)
//   * it clears on beforeunload
// because a timer that outlives its reason is exactly the leak this discipline exists to prevent.
//   key    : a stable name, so re-arming does not stack a second interval
//   isLive : () => boolean, re-evaluated by the caller's own reload
//   tick   : the refresh to run (usually the page's own loader, which re-arms or clears this)
//   ms     : interval, default 15000
var _whPolls = {};
function whLivePoll(key, isLive, tick, ms) {
  if (!isLive || !isLive()) {
    if (_whPolls[key]) { clearInterval(_whPolls[key]); delete _whPolls[key]; }
    return;
  }
  if (_whPolls[key]) return;                       // already polling this key
  _whPolls[key] = setInterval(function () {
    // RE-CHECK EVERY TICK, not only when the poll was armed. The first cut evaluated isLive() once at
    // arm time, so a condition that became false afterwards never stopped it — the client's list poll
    // kept firing after a tracker opened and repainted the pane out from under the live map
    // ("a provider marker was never placed on the watcher's map"). A poll that cannot notice its own
    // reason has ended is the same defect as a timer with no clearInterval, one step subtler.
    if (!isLive()) { clearInterval(_whPolls[key]); delete _whPolls[key]; return; }
    if (typeof document !== 'undefined' && document.hidden) return;
    // OFFLINE IS A SKIP, NOT A RETRY. Caught 2026-07-30 by the bank's own offline cell the moment
    // this helper reached the client page: while offline the poll kept firing into a dead network and
    // the loader's catch repainted the pane as "Couldn't load services" every 15s - a page flapping
    // into an error state on its own, on top of a person who already knows they are offline. The
    // banner says it once; the poll should simply wait.
    if (typeof navigator !== 'undefined' && navigator.onLine === false) return;
    try { tick(); } catch (_e) { /* empty-catch-allow: a missed refresh self-heals on the next tick */ }
  }, ms || 15000);
}
if (typeof window !== 'undefined') {
  window.whLivePoll = whLivePoll;
  window.addEventListener('beforeunload', function () {
    Object.keys(_whPolls).forEach(function (k) { clearInterval(_whPolls[k]); delete _whPolls[k]; });
  });
}

// whPrimaryCta — the platform's ONE primary-conversion entry point (Trajectory T1)
// ─────────────────────────────────────────────
// Born from a dead CTA: the landing page's sticky "Get Early Access" bar was an <a href="#join">
// that ANOTHER script had marked inert, so on a phone the page's most prominent button did
// nothing at all — and 790 green gates never noticed, because every CTA oracle checked that the
// element EXISTS, not that tapping it changes anything. Every primary CTA now routes through this
// one function so the promise is uniform: the primary action IS the signup.
//   source : short slug naming the entry point ('sticky' | 'hero' | 'nav' | 'mobile-menu' | …).
//            Recorded to sessionStorage + GA4 so conversion attribution is measurable per door.
//   ev     : the click event when called from onclick (so the anchor fallback href never fires).
// Mode switch (one-edit revisit, decided with Ian 2026-08-24): window.WH_CONVERSION_MODE
//   'direct'   (default) → open the real sign-UP modal where it exists (index), else deep-link
//                          to index.html?signup=1 — the account is the product's front door.
//   'waitlist' → the pre-launch behavior: scroll to the #join email block.
function whPrimaryCta(source, ev) {
  if (ev && typeof ev.preventDefault === 'function') ev.preventDefault();
  var src = String(source || 'unknown');
  // wh_signup_source: CANONICAL key (storage_key_registry.json) — written here, read by
  // index.html submitSignUp into the GA4 signup_completed event. No allow-marker on purpose:
  // a marker within 200 chars EXEMPTS the setItem from the key-consistency count and turned
  // this write invisible (get-without-set false drift, caught by the gate 2026-08-24).
  try { sessionStorage.setItem('wh_signup_source', src); } catch (_) { /* empty-catch-allow: private mode */ }
  try { if (window.gtag) window.gtag('event', 'primary_cta_click', { event_category: 'conversion', source: src }); } catch (_) { /* empty-catch-allow: analytics best-effort */ }
  var mode = window.WH_CONVERSION_MODE || 'direct';
  if (mode === 'waitlist') {
    var join = document.getElementById('join');
    if (join) { join.scrollIntoView({ behavior: 'smooth', block: 'start' }); return; }
    window.location.href = 'index.html#join';
    return;
  }
  if (typeof window.openSignUp === 'function') { window.openSignUp(ev || null); return; }
  // Not on index (no modal here): carry the intent through the deep link the resolver honors.
  window.location.href = 'index.html?signup=1';
}
if (typeof window !== 'undefined') window.whPrimaryCta = whPrimaryCta;

// whAuthRequiredToast — a sign-in refusal whose remedy is CLICKABLE (Trajectory T1)
// ─────────────────────────────────────────────
// Replaces the dead-end pattern measured on marketplace 2026-08-23: eight gated actions each
// showed a transient "Sign in to save items" toast with NO way to sign in from it — the refusal
// named the remedy and offered no door. This card offers both doors (sign in / create account)
// and carries ?return= so the interrupted intent survives the auth crossing.
// Self-contained on purpose: NEITHER whToast nor whBanner exists platform-wide (utils.js:667),
// so this builds its own DOM instead of assuming a host the page does not have.
//   action : what the person was trying to do, in their words ('save items', 'send an inquiry').
//   opts.allowSignup : default true; false renders only the sign-in door (rare: invite-only flows).
//   opts.returnTo    : where to land after auth; defaults to the CURRENT page + params + hash so
//                      "come back to what I was doing" is the promise, not the home page.
// Duration discipline: refusals with remedies must outlive a glance (the 0ms-toast lesson) —
// this stays 30s or until dismissed/clicked, and Escape closes it (focus is NOT trapped: it is a
// status card, not a modal).
function whAuthRequiredToast(action, opts) {
  opts = opts || {};
  var allowSignup = opts.allowSignup !== false;
  var returnTo = opts.returnTo || (window.location.pathname.split('/').pop() || 'index.html') + window.location.search + window.location.hash;
  var ret = encodeURIComponent(returnTo);
  var esc = (typeof window.escHtml === 'function') ? window.escHtml : function (s) {
    return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; });
  };
  var old = document.getElementById('wh-auth-toast');
  if (old) old.remove();
  var card = document.createElement('div');
  card.id = 'wh-auth-toast';
  card.setAttribute('role', 'status');
  card.setAttribute('aria-live', 'polite');
  card.style.cssText = 'position:fixed;left:50%;bottom:calc(24px + env(safe-area-inset-bottom,0px));transform:translateX(-50%);z-index:1200;'
    + 'width:min(420px,calc(100vw - 24px));background:rgba(22,32,50,0.98);border:1px solid rgba(var(--wh-orange-rgb, 247, 162, 27),0.4);'
    + 'border-radius:var(--wh-radius-lg, 16px);padding:14px 16px;box-shadow:0 12px 40px rgba(0,0,0,0.5);font-size:0.85rem;color:rgba(255,255,255,0.92);';
  card.innerHTML =
    '<div style="display:flex;align-items:flex-start;gap:10px;">'
    + '<div style="flex:1;line-height:1.5;">Sign in to ' + esc(action) + '. '
    + (allowSignup ? '<span style="color:rgba(255,255,255,0.75);">New here? An account is free.</span>' : '')
    + '</div>'
    + '<button type="button" data-wh-auth-close aria-label="Close" style="background:none;border:none;color:rgba(255,255,255,0.8);cursor:pointer;font-size:1.05rem;line-height:1;min-width:44px;min-height:44px;margin:-10px -8px -10px 0;">&times;</button>'
    + '</div>'
    + '<div style="display:flex;gap:10px;margin-top:10px;flex-wrap:wrap;">'
    + '<a href="index.html?signin=1&return=' + ret + '" style="display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:8px 18px;border-radius:var(--wh-radius, 12px);background:var(--wh-orange,#F7A21B);color:var(--wh-navy,#162032);font-weight:700;text-decoration:none;">Sign in</a>'
    + (allowSignup
      ? '<a href="index.html?signup=1&return=' + ret + '" style="display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:8px 18px;border-radius:var(--wh-radius, 12px);background:rgba(var(--wh-orange-rgb, 247, 162, 27),0.12);border:1px solid rgba(var(--wh-orange-rgb, 247, 162, 27),0.45);color:var(--wh-orange-text,#FFC65C);font-weight:700;text-decoration:none;">Create a free account</a>'
      : '')
    + '</div>';
  document.body.appendChild(card);
  var timer = setTimeout(function () { card.remove(); }, 30000);
  function _close() { clearTimeout(timer); card.remove(); document.removeEventListener('keydown', _onKey); }
  function _onKey(e) { if (e.key === 'Escape') _close(); }
  card.querySelector('[data-wh-auth-close]').addEventListener('click', _close);
  document.addEventListener('keydown', _onKey);
  return card;
}
if (typeof window !== 'undefined') window.whAuthRequiredToast = whAuthRequiredToast;

// whSignInWall — the ONE way a page bounces an unauthenticated caller (Trajectory T2)
// ─────────────────────────────────────────────
// Measured 2026-08-24 (T2's first probe): a learn-article reader tapping "Open the Logbook"
// landed on index.html?signin=1 — modal open (the door exists), but the LOGBOOK intent was
// gone: ~30 per-page identity gates each hand-rolled the redirect and none carried ?return=,
// so after auth every one of them dumped the person on the dashboard instead of the page they
// asked for. index.html's resolver + both submit paths already honor ?return= (T1); this
// helper is the missing writer side. One function, so the return contract is written once.
function whSignInWall() {
  var here = (window.location.pathname.split('/').pop() || 'index.html')
    + window.location.search + window.location.hash;
  window.location.href = 'index.html?signin=1&return=' + encodeURIComponent(here);
}
if (typeof window !== 'undefined') window.whSignInWall = whSignInWall;
