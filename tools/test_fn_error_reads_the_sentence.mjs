/**
 * test_fn_error_reads_the_sentence.mjs — whFnError shows a person the function's SENTENCE, whichever field it is in.
 *
 * WHY (2026-10-12, UFAI edge walk W4238). whFnError exists so the function's own words survive supabase-js's
 * "Edge Function returned a non-2xx status code" placeholder. It read `body.error || body.message` - but the platform's
 * functions answer a refusal in three shapes, and only one of them keeps the sentence in `error`:
 *
 *   {error: "<sentence>"}                       most functions
 *   {error: "<code>", message: "<sentence>"}    login, supervisor-reset-password
 *   {ok: false, error: {code, message}}         the _shared/envelope fail()
 *
 * Measured live on the hive roster: a supervisor pressing Reset PW past the per-hour limit read the bare code
 * "rate_limited", though the function had also sent "Too many password resets. Try again later."; and an envelope
 * refusal's sentence was never read at all (an object is not a string), so it fell to the generic status line.
 *
 * This loads the REAL whFnError out of utils.js into a sandbox (it touches nothing but its argument and two window
 * helpers) and asserts every shape. Then it proves its own teeth: the same source with the old selection line put
 * back must FAIL the code+sentence and envelope cases, so a revert cannot pass silently.
 *
 *   node tools/test_fn_error_reads_the_sentence.mjs
 */
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const SRC = readFileSync('utils.js', 'utf8');
const START = SRC.indexOf('window.whFnError = async function');
if (START < 0) { console.log('FAIL fn-error-reads-the-sentence: window.whFnError not found in utils.js'); process.exit(1); }
const END = SRC.indexOf('\n};', START);
if (END < 0) { console.log('FAIL fn-error-reads-the-sentence: could not find the end of whFnError'); process.exit(1); }
const FN = SRC.slice(START, END + 3);

// the shape a FunctionsHttpError carries: context is the Response
const httpError = (status, body) => ({
  message: 'Edge Function returned a non-2xx status code',
  context: {
    status,
    clone() { return this; },
    json: async () => {
      if (typeof body === 'string') throw new SyntaxError('Unexpected token');
      return body;
    },
  },
});

function load(fnSource) {
  const win = {
    // the taxonomy stand-in: names the status it was handed, so a fall-through is visible in the assertion
    whAiError: (e, fallback) => 'TAXONOMY(' + String(e && e.message) + ')',
    _t: (en) => en,
  };
  const ctx = vm.createContext({ window: win, console });
  vm.runInContext(fnSource, ctx);
  return win.whFnError;
}

const CASES = [
  { name: 'a sentence in error (most functions)', err: httpError(429, { error: 'AI call limit reached for this hive. Try again in an hour.' }),
    want: 'AI call limit reached for this hive. Try again in an hour.' },
  { name: 'a code in error, the sentence in message (supervisor-reset-password)',
    err: httpError(429, { error: 'rate_limited', message: 'Too many password resets. Try again later.' }),
    want: 'Too many password resets. Try again later.', teeth: true },
  { name: 'a code in error, the sentence in message (login)',
    err: httpError(401, { error: 'invalid_credentials', message: 'That email and password do not match. Check both and try again.' }),
    want: 'That email and password do not match. Check both and try again.', teeth: true },
  { name: 'the envelope: error is {code, message}',
    err: httpError(422, { ok: false, error: { code: 'unreadable_receipt', message: 'The receipt photo could not be read. Take it again in better light.' } }),
    want: 'The receipt photo could not be read. Take it again in better light.', teeth: true },
  { name: 'a bare code and nothing else falls to the status taxonomy, never shown as words',
    err: httpError(429, { error: 'rate_limited' }), want: 'TAXONOMY(429)', teeth: true },
  { name: 'a body that is not JSON falls to the status taxonomy', err: httpError(502, 'Bad Gateway'), want: 'TAXONOMY(502)' },
  { name: 'the supabase-js placeholder is never a sentence to show',
    err: httpError(500, { error: 'Edge Function returned a non-2xx status code' }), want: 'TAXONOMY(500)' },
  { name: 'message wins over a sentence in error when both are sentences',
    err: httpError(403, { error: 'Not authorized', message: 'Only a supervisor of this hive can export it.' }),
    want: 'Only a supervisor of this hive can export it.' },
];

async function run(fn) {
  const results = [];
  for (const c of CASES) {
    let got;
    try { got = await fn(c.err, 'FALLBACK'); } catch (e) { got = 'THREW ' + e.message; }
    results.push({ c, got, ok: got === c.want });
  }
  return results;
}

let failed = 0;
const live = await run(load(FN));
for (const r of live) {
  if (!r.ok) { failed++; console.log(`  FAIL ${r.c.name}: got ${JSON.stringify(r.got)}, want ${JSON.stringify(r.c.want)}`); }
}

// TEETH: the pre-fix selection line, put back into the real function, must fail the cases it got wrong
const OLD = 'var own = body && (body.error || body.message);\n  if (typeof own === \'string\' && own.trim() && !/non-2xx/i.test(own)) return own.trim();';
const NEW_RE = /var _sentence = function[\s\S]*?if \(own\) return own;/;
if (!NEW_RE.test(FN)) {
  failed++;
  console.log('  FAIL teeth: the sentence-selection block was not found, so the revert could not be staged');
} else {
  const reverted = await run(load(FN.replace(NEW_RE, OLD)));
  const caught = reverted.filter((r) => r.c.teeth && !r.ok).length;
  const owed = CASES.filter((c) => c.teeth).length;
  if (caught !== owed) {
    failed++;
    console.log(`  FAIL teeth: with the old selection put back only ${caught}/${owed} of the cases it got wrong fail`);
  }
}

const total = CASES.length + 1;
if (failed) {
  console.log(`FAIL fn-error-reads-the-sentence: ${failed} of ${total} check(s) failed`);
  process.exit(1);
}
console.log(`PASS fn-error-reads-the-sentence: ${CASES.length} response shapes read as the function meant, and the old selection fails ${CASES.filter((c) => c.teeth).length} of them`);
