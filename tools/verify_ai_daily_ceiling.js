// Q4 local-substitute proof: the AI daily/hourly 429 DECISION in checkAIRateLimit +
// checkSoloRateLimit, run in Node with a mocked db (no deno/functions-serve needed — the
// doctrine's "ext-blocked -> local substitute"). Extracts the REAL function bodies from
// _shared/rate-limit.ts so the decision under test is the shipped one, not a re-derivation.
const fs = require('fs');
const path = require('path');
const src = fs.readFileSync(path.join(__dirname, '..', 'supabase', 'functions', '_shared', 'rate-limit.ts'), 'utf8');

// Extract a function body (between its signature '{' and the matching '}') and make it valid
// JS: strip the TS non-null assertion `data!` -> `data` (the only TS-ism inside these bodies).
function bodyOf(name) {
  // Accept both `export async function <name>` and a private `async function <name>`
  // (helpers like bumpSoloBucket are module-private, not exported).
  let sig = src.indexOf('export async function ' + name);
  if (sig < 0) sig = src.indexOf('async function ' + name);
  if (sig < 0) throw new Error('not found: ' + name);
  let i = src.indexOf('{', src.indexOf(')', sig));   // first { after the param list
  let depth = 0;
  for (let j = i; j < src.length; j++) {
    if (src[j] === '{') depth++;
    else if (src[j] === '}') { depth--; if (depth === 0) return src.slice(i + 1, j).replace(/data!/g, 'data'); }
  }
  throw new Error('unbalanced: ' + name);
}

const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
const checkAIRateLimit = new AsyncFunction('db', 'hiveId', 'limitPerHour', 'limitPerDay', bodyOf('checkAIRateLimit'));
// checkSoloRateLimit was refactored to DELEGATE its bucket logic to a bumpSoloBucket helper, so it is
// no longer self-contained. Extract that helper too and expose it as a global (AsyncFunction bodies see
// only globals + their params) so the extracted checkSoloRateLimit body can resolve its bumpSoloBucket call.
globalThis.bumpSoloBucket = new AsyncFunction('db', 'key', 'limitPerHour', 'limitPerDay', bodyOf('bumpSoloBucket'));
const checkSoloRateLimit = new AsyncFunction('db', 'identityKey', 'limitPerHour', 'limitPerDay', bodyOf('checkSoloRateLimit'));

function mockDb(row) {
  let captured = null;
  const chain = {
    select() { return chain; }, eq() { return chain; },
    maybeSingle() { return Promise.resolve({ data: row }); },
    upsert(v) { captured = v; return Promise.resolve({}); },
  };
  return { from() { return chain; }, _captured: () => captured };
}
const nowIso = () => new Date().toISOString();

let pass = 0, fail = 0;
function check(name, cond) { if (cond) { pass++; console.log('  ok   ' + name); } else { fail++; console.log('  FAIL ' + name); } }

(async () => {
  // 1. No row -> fresh -> ALLOWED (hive)
  let r = await checkAIRateLimit(mockDb(null), 'hive-1', 50, 300);
  check('hive: no prior row -> allowed', r.allowed === true);

  // 2. Day count at cap, day window fresh -> DENY scope 'day' (the daily ceiling)
  r = await checkAIRateLimit(mockDb({ call_count: 1, window_start: nowIso(), day_count: 300, day_window_start: nowIso() }), 'hive-1', 50, 300);
  check('hive: day_count>=limitPerDay -> deny scope=day', r.allowed === false && r.scope === 'day');

  // 3. Hour count at cap, day under cap -> DENY scope 'hour'
  r = await checkAIRateLimit(mockDb({ call_count: 50, window_start: nowIso(), day_count: 10, day_window_start: nowIso() }), 'hive-1', 50, 300);
  check('hive: hour at cap, day ok -> deny scope=hour', r.allowed === false && r.scope === 'hour');

  // 4. Stale day window -> resets -> ALLOWED even though stored day_count is high
  const twoDaysAgo = new Date(Date.now() - 48 * 3600 * 1000).toISOString();
  r = await checkAIRateLimit(mockDb({ call_count: 999, window_start: twoDaysAgo, day_count: 999, day_window_start: twoDaysAgo }), 'hive-1', 50, 300);
  check('hive: stale windows -> reset -> allowed', r.allowed === true);

  // 5. Solo identity: day at cap -> deny scope 'day'
  r = await checkSoloRateLimit(mockDb({ call_count: 1, window_start: nowIso(), day_count: 100, day_window_start: nowIso() }), 'ip:1.2.3.4', 30, 100);
  check('solo: day_count>=limitPerDay -> deny scope=day', r.allowed === false && r.scope === 'day');

  // 6. Empty hiveId -> solo-mode allow (no tracking)
  r = await checkAIRateLimit(mockDb(null), '', 50, 300);
  check('hive: empty hiveId -> allowed (untracked)', r.allowed === true);

  console.log('\n  ' + (fail === 0 ? 'PASS' : 'FAIL') + ' — ' + pass + ' passed, ' + fail + ' failed');
  process.exit(fail === 0 ? 0 : 1);
})();
