// Q5 §7-11 live-verify: scope-aware graceful-429 classification in companion-launcher.js.
// Extracts the REAL if/else chain and asserts each gateway 429 body maps to the right hint.
const fs = require('fs');
const path = require('path');
const src = fs.readFileSync(path.join(__dirname, '..', 'companion-launcher.js'), 'utf8');

// Extract from `let friendly;` up to `addMessage('assistant', friendly);`, wrap as a fn.
const start = src.indexOf('let friendly;');
const end = src.indexOf("addMessage('assistant', friendly);", start);
if (start < 0 || end < 0) { console.error('FAIL: could not locate the 429 classification block'); process.exit(1); }
const chain = src.slice(start, end);
const classify = new Function('m', chain + ' return friendly;');

// Exact gateway bodies (from _shared/rate-limit.ts) -> expected friendly substring.
const cases = [
  ["AI is handling a burst of activity right now. Please retry in a few seconds.", "very busy"],
  ["The platform's shared AI budget for today is fully used. Please try again tomorrow.", "shared AI budget for today"],
  ["Daily AI limit reached for this hive. Resets tomorrow.", "today's AI limit"],
  ["Per-user AI call limit reached (25/hour). Other hive members are unaffected.", "for this hour"],
  ["AI call limit reached for this hive. Try again in an hour.", "for this hour"],
  ["Failed to fetch", "Check your connection"],
  ["Edge Function returned a non-2xx status code", "Check your connection"],
];
let pass = 0, fail = 0;
for (const [body, want] of cases) {
  const got = classify(body);
  const ok = got.includes(want);
  if (ok) pass++; else fail++;
  console.log(`  [${ok ? 'ok  ' : 'FAIL'}] "${body.slice(0, 42)}..." -> ${ok ? 'correct' : 'got: ' + got}`);
}
console.log('\n  ' + (fail === 0 ? 'PASS' : 'FAIL') + ' — ' + pass + ' passed, ' + fail + ' failed');
process.exit(fail === 0 ? 0 : 1);
