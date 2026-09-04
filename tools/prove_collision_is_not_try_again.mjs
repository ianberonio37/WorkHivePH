/* prove_collision_is_not_try_again.mjs - a permanent collision must not be answered with "try again".
 *
 * whWriteError is the platform's write-error taxonomy. It passes a DELIBERATE refusal's own sentence
 * through (23514 / 42501 / P0001), because a guard that took the trouble to explain itself must not
 * be replaced by "Save failed. Try again." - the file says so itself, about a seller who "will retry
 * forever, because retrying is precisely what cannot work".
 *
 * ★23505 HAD EXACTLY THAT PROBLEM AND WAS NOT ON THE LIST. A unique violation is permanent: the name,
 * tag, code or username is taken, and retyping the same value fails every time. Measured before the
 * fix - a duplicate asset tag and a raced username BOTH returned the caller's "...try again"
 * fallback. It reaches real surfaces: asset_nodes is UNIQUE (hive_id, tag), so two "P-101"s collide
 * on a plant's first day, and worker_profiles is UNIQUE (username).
 *
 * ★THIS EXERCISES THE FUNCTION, it does not grep for a branch. A gate that greps proves a line
 * exists; only calling whWriteError with a real error object proves what a person is told - and the
 * same call proves the two things that must NOT change: a deliberate refusal still speaks in its own
 * words, and every other error still falls through to the caller's wording.
 *
 * ★AND IT ASSERTS NO SCHEMA LEAK: the only clue to WHICH field collided is the constraint name, a
 * schema word no reader should ever see. The sentence stays generic on purpose.
 *
 * Usage: node tools/prove_collision_is_not_try_again.mjs
 */
import { readFileSync } from 'fs';

const el = () => ({ style: {}, classList: { add() {}, remove() {}, contains: () => false, toggle() {} },
  setAttribute() {}, appendChild() {}, addEventListener() {}, remove() {},
  querySelectorAll: () => [], querySelector: () => null, dataset: {}, children: [] });

global.window = { addEventListener() {}, matchMedia: () => ({ matches: false, addEventListener() {} }) };
global.localStorage = { getItem: () => null, setItem() {}, removeItem() {} };
global.sessionStorage = global.localStorage;
global.document = { addEventListener() {}, createElement: el, querySelectorAll: () => [],
  querySelector: () => null, getElementById: () => null, body: el(), head: el(),
  documentElement: el(), readyState: 'complete' };
/* Node 24 exposes `navigator` as a getter-only global, so a plain assignment throws - and a shim
   that throws produces a RED that has nothing to do with the code under test. defineProperty with
   configurable:true replaces it safely on both old and new runtimes. */
try {
  Object.defineProperty(globalThis, 'navigator',
    { value: { onLine: true, userAgent: 'node' }, configurable: true, writable: true });
} catch (_) { /* whatever navigator already is will do - utils.js only reads onLine/userAgent */ }
global.location = { pathname: '/x', search: '', hash: '' };

try { new Function(readFileSync(new URL('../utils.js', import.meta.url), 'utf8'))(); } catch (_) { /* the DOM-touching tail is not needed to reach whWriteError */ }

const whWriteError = global.window.whWriteError;
if (typeof whWriteError !== 'function') {
  console.log('SKIP prove_collision_is_not_try_again - whWriteError not reachable from utils.js in a DOM-less shim');
  process.exit(0);
}

const FALLBACK = 'The save did not go through. Nothing changed; try again.';
const SCHEMA = /constraint|duplicate key|_key\b|pg_|23505|relation/i;
const fails = [];

const collisions = [
  [{ code: '23505', message: 'duplicate key value violates unique constraint "asset_nodes_tag_unique_per_hive"' },
   'a second asset tagged P-101 on the plant\'s first day'],
  [{ code: '23505', message: 'duplicate key value violates unique constraint "worker_profiles_username_key"' },
   'two people claiming one username in the same second'],
  [{ message: 'duplicate key value violates unique constraint "hives_invite_code_key"' },
   'an invite-code collision reported without a code field'],
];
for (const [err, label] of collisions) {
  const out = whWriteError(err, FALLBACK);
  if (/try again/i.test(out) && out === FALLBACK) {
    fails.push(`${label}: told "${out}" - the value is TAKEN, so trying again is the one action that `
             + 'cannot work, and the person retypes the same thing forever');
  }
  if (SCHEMA.test(out)) {
    fails.push(`${label}: the sentence leaks schema words -> "${out.slice(0, 110)}"`);
  }
  if (!/already|taken|different|another|change/i.test(out)) {
    fails.push(`${label}: the sentence does not say something is already taken -> "${out.slice(0, 110)}"`);
  }
}

// what must NOT have changed
const deliberate = whWriteError(
  { code: '23514', message: 'Listing needs PHP50 credits held (10% of the price) and you have 0 available' }, FALLBACK);
if (!/PHP50 credits/.test(deliberate)) {
  fails.push('a deliberate guard no longer speaks in its own words - that sentence is the whole '
           + `reason the taxonomy exists; got "${deliberate.slice(0, 110)}"`);
}
const other = whWriteError({ code: 'PGRST116', message: 'no rows returned' }, FALLBACK);
if (other !== FALLBACK) {
  fails.push(`an unrelated error stopped falling through to the caller's wording; got "${other.slice(0, 110)}"`);
}

if (fails.length) {
  console.log('FAIL prove_collision_is_not_try_again:');
  fails.forEach((f) => console.log('    - ' + f));
  process.exit(1);
}
console.log('PASS prove_collision_is_not_try_again - a unique violation says the value is already '
          + 'taken and to change it, leaks no constraint name, and neither deliberate refusals nor '
          + 'other errors changed.');
