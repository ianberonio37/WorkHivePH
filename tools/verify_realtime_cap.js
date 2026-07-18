// Q5 live-verify: whRealtimeSubscribe per-client channel CAP + graceful poll degrade.
// Extracts the REAL function source from utils.js and drives it with mocks (rtConn/whPoll
// are already-shipped Arc J/L primitives; this isolates the new cap + degrade logic).
const fs = require('fs');
const path = require('path');

const src = fs.readFileSync(path.join(__dirname, '..', 'utils.js'), 'utf8');

// Brace-match extract `function whRealtimeSubscribe(...) { ... }`.
function extractFn(text, name) {
  const start = text.indexOf('function ' + name);
  if (start < 0) throw new Error('fn not found: ' + name);
  let i = text.indexOf('{', start), depth = 0;
  for (let j = i; j < text.length; j++) {
    if (text[j] === '{') depth++;
    else if (text[j] === '}') { depth--; if (depth === 0) return text.slice(start, j + 1); }
  }
  throw new Error('unbalanced braces for ' + name);
}

const fnSrc = extractFn(src, 'whRealtimeSubscribe');

// ── Mocks ──────────────────────────────────────────────────────────────────
let pollCount = 0, pollStops = 0;
function whPoll(fn, ms, o) { pollCount++; return { stop() { pollStops++; }, refresh() {} }; }
function rtConn(cb) { return cb; }               // pass-through: subscribe() will invoke it
const removed = [];
global.window = { supabase: { removeChannel(ch) { removed.push(ch); } } };

function mockChannel(id) {
  return { id, _cb: null, subscribe(cb) { this._cb = cb; return this; }, unsubscribe() {} };
}

// Eval the real function into this scope (whPoll/rtConn/window resolve to the mocks above).
const whRealtimeSubscribe = eval('(' + fnSrc + ')');

// ── Tests ──────────────────────────────────────────────────────────────────
let pass = 0, fail = 0;
function check(name, cond) { if (cond) { pass++; console.log('  ok   ' + name); } else { fail++; console.log('  FAIL ' + name); } }

const reload = () => {};
// cap = 2 for the test
const h1 = whRealtimeSubscribe('c1', () => mockChannel(1), reload, { max: 2, immediate: false });
const h2 = whRealtimeSubscribe('c2', () => mockChannel(2), reload, { max: 2, immediate: false });
check('under cap #1 -> realtime', h1.mode === 'realtime');
check('under cap #2 -> realtime', h2.mode === 'realtime');
check('registry holds 2 channels', window.__whChannels.size === 2);

const h3 = whRealtimeSubscribe('c3', () => mockChannel(3), reload, { max: 2, immediate: false });
check('AT cap #3 -> degrades to poll (reason cap)', h3.mode === 'poll' && h3.reason === 'cap');

// stop() frees a slot -> a new subscribe can go realtime again
h1.stop();
check('stop() frees the per-client slot (count 2->1)', window.__whChannels.size === 1);
check('stop() removed the channel via supabase.removeChannel', removed.length === 1);
const h4 = whRealtimeSubscribe('c4', () => mockChannel(4), reload, { max: 2, immediate: false });
check('slot freed -> new subscribe is realtime again', h4.mode === 'realtime');

// a throwing builder degrades to poll (never throws to caller)
const h5 = whRealtimeSubscribe('c5', () => { throw new Error('boom'); }, reload, { max: 9, immediate: false });
check('builder throw -> graceful poll (reason subscribe-error)', h5.mode === 'poll' && h5.reason === 'subscribe-error');

// offline state -> spins up a poll fallback but stays realtime mode
const before = pollCount;
const ch6 = mockChannel(6);
const h6 = whRealtimeSubscribe('c6', () => ch6, reload, { max: 9, immediate: false });
ch6._cb('offline');                              // simulate the subscribe state callback firing offline
check('offline -> poll fallback spun up (graceful degrade)', pollCount === before + 1 && h6.mode === 'realtime');
ch6._cb('live');                                 // recovered -> poll stops
check('recovered live -> poll fallback stopped', pollStops >= 1);

console.log('\n  ' + (fail === 0 ? 'PASS' : 'FAIL') + ' — ' + pass + ' passed, ' + fail + ' failed');
process.exit(fail === 0 ? 0 : 1);
