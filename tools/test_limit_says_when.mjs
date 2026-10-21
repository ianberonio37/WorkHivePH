/* test_limit_says_when.mjs - SL RL2 (2026-10-22): every limit the platform enforces reaches a person as ONE sentence
 * that says a limit was hit and when it clears - through utils.js's four sentence makers, called for real.
 *
 * The limits arrive in four shapes: a database trigger's refusal (54000 - the daily caps and the hive quotas; 23P01 -
 * the feedback limit; P0001 and 23514 - the listing and review limits), an edge function's 429 or 503 with its own
 * sentence in the body (rate-limit.ts), the platform-wide AI budget's 429, and a gateway's bare 429. This loads the REAL
 * utils.js into a DOM-less shim (the shape tools/prove_collision_is_not_try_again.mjs uses) and asks whWriteError,
 * whReadError, whAiError and whFnError what they say to each one. A sentence passes when it names the limit (limit /
 * too many / full / quota) AND when it clears (a time, midnight, tomorrow, a moment, or the archive-or-raise remedy of a
 * quota) - and never the caller's generic "try again" fallback. The cases that must NOT read as limits (an exclusion
 * constraint, Postgres's own program limits) must still fall through to the caller's words.
 *
 *   node tools/test_limit_says_when.mjs [utils.js]      (a path in place of utils.js: a mutant, from the gate's self-test)
 */
import { readFileSync } from 'fs';
import { resolve } from 'path';

const el = () => ({ style: {}, classList: { add() {}, remove() {}, contains: () => false, toggle() {} },
  setAttribute() {}, appendChild() {}, addEventListener() {}, remove() {},
  querySelectorAll: () => [], querySelector: () => null, dataset: {}, children: [] });
global.window = { addEventListener() {}, matchMedia: () => ({ matches: false, addEventListener() {} }) };
global.localStorage = { getItem: () => null, setItem() {}, removeItem() {}, key: () => null, length: 0 };
global.sessionStorage = global.localStorage;
global.document = { addEventListener() {}, createElement: el, querySelectorAll: () => [],
  querySelector: () => null, getElementById: () => null, body: el(), head: el(),
  documentElement: el(), readyState: 'complete' };
try {
  Object.defineProperty(globalThis, 'navigator', { value: { onLine: true, userAgent: 'node' }, configurable: true, writable: true });
} catch (_) { /* whatever navigator already is will do */ }
global.location = { pathname: '/x', search: '', hash: '' };
// the observers and the frame callback the shared chrome wires at load - stubbed, so the shim runs utils.js far enough to
// reach the sentence makers defined after them (whAdminCheckOfflineText is past the first observer)
global.MutationObserver = class { observe() {} disconnect() {} takeRecords() { return []; } };
global.requestAnimationFrame = () => 0;
global.cancelAnimationFrame = () => {};
// the told-sentence log (whTold) writes to client_errors through the page's client: a stub that records nothing
global.window._whSupabaseClient = { from: () => ({ insert: () => Promise.resolve({ error: null }) }) };

const SRC = readFileSync(resolve(process.argv[2] || 'utils.js'), 'utf8');
try { new Function(SRC)(); } catch (_) { /* the DOM-touching tail is not needed to reach the sentence makers */ }
const { whWriteError, whReadError, whAiError, whFnError } = global.window;
if ([whWriteError, whReadError, whAiError, whFnError].some((f) => typeof f !== 'function')) {
  console.log('FAIL limit-says-when: a sentence maker is not reachable from utils.js in the shim');
  process.exit(1);
}

const FALLBACK = 'FALLBACK - the caller\'s own words';
const LIMIT = /\b(?:limit|too many|too fast|full|fully used|quota|budget)\b/i;
const WHEN = /\b(?:\d+\s*(?:seconds?|minutes?|hours?)|in about|an hour|midnight|tomorrow|a moment|a minute|a few seconds|archive)\b/i;
const httpError = (status, body) => ({
  message: 'Edge Function returned a non-2xx status code',
  context: { status, clone() { return this; }, json: async () => { if (typeof body === 'string') throw new SyntaxError('x'); return body; } },
});

const CASES = [
  // [label, maker, error, expectation: 'limit' (names the limit and when) | 'verbatim' (the server's sentence) | 'fallback']
  ['a daily cap (54000)', 'write', { code: '54000', message: "You have reached today's free limit (200). Resets at midnight.", hint: 'daily_hive_logbook' }, 'verbatim'],
  ['a hive quota, reworded (54000)', 'write', { code: '54000', message: 'This hive has reached its limit of 5000 logbook entries, so this one was not saved. A supervisor can archive older entries or raise the limit.', hint: 'Old records can be archived; contact your supervisor to raise the cap.' }, 'verbatim'],
  ['a hive quota, as an older database words it (54000)', 'write', { code: '54000', message: 'logbook cumulative quota exceeded for hive 1f2e3d4c-aaaa-bbbb-cccc-1234567890ab (5000 >= 5000)', hint: 'Old records can be archived; contact your supervisor to raise the cap.' }, 'limit'],
  ['the feedback limit (23P01)', 'write', { code: '23P01', message: 'Feedback rate limit reached: 5 messages an hour. You can send more in about 40 minutes.' }, 'verbatim'],
  ['the listing limit (P0001)', 'write', { code: 'P0001', message: 'Daily listing limit of 20 reached. You can post another listing in about 5 hours.' }, 'verbatim'],
  ['the review limit (23514)', 'write', { code: '23514', message: 'Daily review limit reached (10 per day). Your earlier reviews are saved. You can leave another review in about 4 hours.' }, 'verbatim'],
  ['the AI rating limit (23514)', 'write', { code: '23514', message: 'Daily AI reply feedback limit reached. You can rate answers again in about 3 hours.' }, 'verbatim'],
  ['posting too fast (P0001)', 'write', { code: 'P0001', message: 'Posting too fast. Wait a few seconds.', hint: 'rate_limit' }, 'verbatim'],
  ['a gateway 429 on a save', 'write', { status: 429, message: 'Too Many Requests' }, 'limit'],
  ['a gateway 429 with its window', 'write', { status: 429, message: 'rate limit exceeded', hint: 'retry after 30s' }, 'limit'],
  ['a function\'s 429 handed to the save sentence (its Retry-After read)', 'write', { message: 'Edge Function returned a non-2xx status code',
    context: { status: 429, headers: { get: (k) => (k === 'Retry-After' ? '720' : null) } } }, 'limit'],
  ['an exclusion constraint is not a limit', 'write', { code: '23P01', message: 'conflicting key value violates exclusion constraint "shift_no_overlap"' }, 'fallback'],
  ['Postgres\'s own program limit is not a person\'s', 'write', { code: '54000', message: 'index row size 2720 exceeds btree version 4 maximum 2704 for index "x"' }, 'fallback'],
  ['a 429 on a read', 'read', { status: 429, message: 'rate limit exceeded' }, 'limit'],
  ['the AI limit with its window', 'ai', { message: '429', body: { retry_after_seconds: 720 } }, 'limit'],
  ['the AI limit with none', 'ai', { message: '429' }, 'limit'],
  ['a function\'s hourly limit', 'fn', httpError(429, { error: 'AI call limit reached for this hive. Try again in about 12 minutes.', scope: 'hour', retryAfter: 720 }), 'verbatim'],
  ['a function\'s per-person limit', 'fn', httpError(429, { error: 'Per-user AI call limit reached (25/hour). Other hive members are unaffected. Try again in about 20 minutes.', scope: 'user' }), 'verbatim'],
  ['the platform\'s day budget', 'fn', httpError(429, { error: "The platform's shared AI budget for today is fully used. Please try again tomorrow.", scope: 'global-day' }), 'verbatim'],
  ['a limiter that could not count (503)', 'fn', httpError(503, { error: 'We could not check your usage limit just now, so nothing was run. Try again in about a minute.', scope: 'unavailable' }), 'verbatim'],
  ['a function\'s 429 with no sentence', 'fn', httpError(429, 'not json'), 'limit'],
  // SL RL2 walk (2026-10-22): a wall standing on the device's last-seen role said only "could not be checked" beside a
  // Reload button when the role read met a rate limit (plant-connections, integrations). whRoleUnreadNote must name the
  // limit and its wait from the read's own error - and still say whose answer the wall is.
  ['the role read refused by a limit', 'role', { status: 429, message: 'rate limit exceeded', hint: 'retry after 30s' }, 'limit'],
  // the same walk: an access gate (the admin pages, integrations' hive-seat lookup) said "could not check your access just
  // now ... Reload the page" under a limit - whAdminCheckOfflineText must name the limit and the wait from the error
  ['the access check refused by a limit', 'access', { status: 429, message: 'rate limit exceeded', hint: 'retry after 30s' }, 'limit'],
];

const fails = [];
for (const [label, maker, err, want] of CASES) {
  let out;
  if (maker === 'write') out = whWriteError(err, FALLBACK);
  else if (maker === 'read') out = whReadError(err, 'the logbook');
  else if (maker === 'ai') out = whAiError(err, FALLBACK);
  else if (maker === 'role') {
    global.window._whRoleUnreadError = err;
    out = typeof global.window.whRoleUnreadNote === 'function' ? global.window.whRoleUnreadNote() : '';
    if (!/role this device last saw/.test(out)) out = '';   // the note must still say whose answer decided the wall
  }
  else if (maker === 'access') {
    out = typeof global.window.whAdminCheckOfflineText === 'function' ? global.window.whAdminCheckOfflineText('This page', err) : '';
    if (!/stays closed/.test(out)) out = '';   // and the gate still says it stays shut
  }
  else out = await whFnError(err, FALLBACK);
  out = String(out == null ? '' : out);
  const own = err.message && !/non-2xx/.test(err.message) ? err.message : (err.context ? '(body)' : '');
  let ok;
  if (want === 'fallback') ok = out === FALLBACK;
  else if (want === 'verbatim') ok = maker === 'fn' ? LIMIT.test(out) && WHEN.test(out) && out !== FALLBACK : out === own;
  else ok = out !== FALLBACK && LIMIT.test(out) && WHEN.test(out);
  console.log((ok ? 'ok   ' : 'FAIL ') + `${label} [${maker}] -> "${out.slice(0, 120)}"`);
  if (!ok) fails.push(label);
}
if (fails.length) {
  console.log(`FAIL limit-says-when - ${fails.length} of ${CASES.length}: ${fails.join('; ')}`);
  process.exit(1);
}
console.log(`PASS limit-says-when - ${CASES.length} limit shapes: each says a limit was hit and when it clears; the two that are not limits fall through`);
process.exit(0);
