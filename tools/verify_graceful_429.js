// Q5 §7-11 live-verify: scope-aware graceful-429 classification in companion-launcher.js.
// Extracts the REAL if/else chain and asserts each gateway 429 body maps to the right hint.
//
// ★THE BILINGUAL WAVE BROKE THIS TEST AND THE CODE WAS FINE (2026-09-11). The chain's hints were
// wrapped in `_tt(en, fil)` so a Filipino reader gets a Filipino explanation of a rate limit - a good
// change - and this test kept evaluating the extracted block with only `m` in scope, so every run died
// on `ReferenceError: _tt is not defined` and the gate reported "graceful-429 classification test
// FAILED/absent". The page defines `_tt` at companion-launcher.js:30 as a RUNTIME lookup
// (`typeof window._t === 'function' ? window._t(en, fil) : en`) deliberately, so the block is correct
// in the browser and only the harness was stale. Same shape as the four gates the wave blinded by
// moving text behind `_t()`/`data-i` - [[feedback_the_waves_wrapper_blinded_four_gates]].
//
// So the translator is now INJECTED, and the test got stronger rather than merely un-broken: the same
// seven gateway bodies are classified TWICE, once per language, and the Filipino pass asserts each
// branch actually returns different, non-empty Filipino text. A branch someone forgets to translate
// now fails here instead of shipping an English rate-limit message to a Filipino plant floor.
const fs = require('fs');
const path = require('path');
const src = fs.readFileSync(path.join(__dirname, '..', 'companion-launcher.js'), 'utf8');

// Extract from `let friendly;` up to `addMessage('assistant', friendly);`, wrap as a fn.
const start = src.indexOf('let friendly;');
const end = src.indexOf("addMessage('assistant', friendly);", start);
if (start < 0 || end < 0) { console.error('FAIL: could not locate the 429 classification block'); process.exit(1); }
const chain = src.slice(start, end);

// The block closes over exactly two module-level names. `_tt` is passed in (below); OPAQUE_NETWORK is
// the regex that decides the network cases, so it is LIFTED FROM THE SOURCE rather than retyped here -
// a copy in the test would let the real one drift and still read green, which is the whole failure mode
// this file exists to prevent.
const oq = src.match(/^\s*const\s+OPAQUE_NETWORK\s*=.*$/m);
if (!oq) { console.error('FAIL: could not locate the OPAQUE_NETWORK definition to lift'); process.exit(1); }
const prelude = oq[0].trim() + '\n';

// `_tt` mirrors the page's own definition: English unless a translator is present. Passing it in as a
// parameter keeps the extracted source byte-identical - the test must not rewrite the code it grades.
// ★A THIRD CLOSED-OVER NAME (2026-10-13): the LM-R timeout branch reads the caught `err` (err.context.name /
// message) so a slow answer says "took too long" instead of "check your connection". Injected like _tt, so the
// extracted source stays byte-identical; undefined unless a case supplies one.
const classify = new Function('m', '_tt', 'err', prelude + chain + ' return friendly;');
const EN = (en) => en;
const FIL = (en, fil) => (fil || en);

// Exact gateway bodies (from _shared/rate-limit.ts) -> expected friendly substring.
// ★A BODY THAT SAYS WHOSE LIMIT AND WHEN IS SHOWN AS IT IS (SL RL1, 2026-10-22). The stock hints rewrote the gateway's
// own refusal: a HIVE's spent hourly allowance ("AI call limit reached for this hive. Try again in about 12 minutes.")
// became "You've used up your AI questions for this hour. Try again in a little while - your teammates aren't
// affected" - the asker blamed, the teammates told a false thing, the window thrown away. A body naming a limit and when
// it clears is now the sentence itself ('server' below: the same text in either language, because the page cannot
// translate a sentence the server wrote); the stock hints stay for a body with no window ('stock').
const cases = [
  ["AI is handling a burst of activity right now. Please retry in a few seconds.", "very busy", "stock"],
  ["The platform's shared AI budget for today is fully used. Please try again tomorrow.", "The platform's shared AI budget for today is fully used. Please try again tomorrow.", "server"],
  ["Daily AI limit reached for this hive. Resets tomorrow.", "Daily AI limit reached for this hive. Resets tomorrow.", "server"],
  ["Daily AI limit reached for this hive. Try again in about 6 hours.", "Daily AI limit reached for this hive. Try again in about 6 hours.", "server"],
  ["Per-user AI call limit reached (25/hour). Other hive members are unaffected.", "for this hour", "stock"],
  ["Per-user AI call limit reached (25/hour). Other hive members are unaffected. Try again in about 20 minutes.", "Per-user AI call limit reached (25/hour). Other hive members are unaffected. Try again in about 20 minutes.", "server"],
  ["AI call limit reached for this hive. Try again in an hour.", "AI call limit reached for this hive. Try again in an hour.", "server"],
  ["AI call limit reached for this hive. Try again in about 12 minutes.", "AI call limit reached for this hive. Try again in about 12 minutes.", "server"],
  ["limit reached", "for this hour", "stock"],
  ["Failed to fetch", "Check your connection", "stock"],
  ["Edge Function returned a non-2xx status code", "Check your connection", "stock"],
  ["WH_DB_TIMEOUT: the database did not answer in time", "took too long", "stock"],
];

let pass = 0, fail = 0;
console.log('  EN — each gateway body maps to the right hint:');
for (const [body, want, kind] of cases) {
  const got = classify(body, EN);
  const ok = typeof got === 'string' && (kind === 'server' ? got === '⚠️ ' + want : got.includes(want));
  if (ok) pass++; else fail++;
  console.log(`  [${ok ? 'ok  ' : 'FAIL'}] "${body.slice(0, 42)}..." -> ${ok ? 'correct' : 'got: ' + got}`);
}

console.log('\n  FIL — every stock branch must return DIFFERENT, non-empty Filipino text; a server sentence stays as written:');
for (const [body, , kind] of cases) {
  const en = classify(body, EN);
  const fil = classify(body, FIL);
  // an untranslated stock branch falls through to the English half, so en === fil is the failure there; a server
  // sentence is the server's words in either language, so there it is the requirement
  const ok = typeof fil === 'string' && fil.trim().length > 0 && (kind === 'server' ? fil === en : fil !== en);
  if (ok) pass++; else fail++;
  console.log(`  [${ok ? 'ok  ' : 'FAIL'}] "${body.slice(0, 42)}..." -> ${ok ? (kind === 'server' ? 'the server\'s words' : 'translated') : (kind === 'server' ? 'REWRITTEN' : 'NOT translated (identical to EN)')}`);
}

console.log('\n  ' + (fail === 0 ? 'PASS' : 'FAIL') + ' — ' + pass + ' passed, ' + fail + ' failed');
process.exit(fail === 0 ? 0 : 1);
