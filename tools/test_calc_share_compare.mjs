// test_calc_share_compare.mjs - the share-a-calculation and compare-two-scenarios core (ENH-P, 2026-10-23), run in node.
//
// engineering-design.js carries the core between "ENH-P share-compare core: BEGIN" and "...: END" - pure functions, no
// DOM - so this reads that block out of the real file (or a copy named on the command line, which is how the gate's
// self-test proves a weakened copy fails) and runs it in a fresh context. What it holds:
//   - a link round-trips any calculation, its text included, and is URL-safe (base64url, no padding);
//   - a damaged or foreign payload opens nothing;
//   - a link's inputs reduce to the form's own keys and types: unknown keys dropped, numbers coerced (a non-number
//     keeps the form's value), text stripped of the characters markup needs, list rows shaped by the form's first row,
//     lists capped;
//   - compare sets two reports' figures side by side and names the inputs that differ, in words.
//
//   node tools/test_calc_share_compare.mjs [path/to/engineering-design.js]
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SRC = process.argv[2] || path.join(ROOT, 'engineering-design.js');
const text = readFileSync(SRC, 'utf8');
const B = '/* ENH-P share-compare core: BEGIN */', E = '/* ENH-P share-compare core: END */';
const i = text.indexOf(B), j = text.indexOf(E);
if (i < 0 || j < i) { console.log('FAIL calc-share-compare: the core block is not in ' + SRC); process.exit(1); }
const ctx = vm.createContext({ TextEncoder, TextDecoder, btoa, atob, JSON, Number, String, Object, Array, Math, Uint8Array });
vm.runInContext(text.slice(i + B.length, j)
  + '\n;globalThis.__core = { edShareEncode, edShareDecode, edShareSanitize, edCompareRows, edInputDiff, edHumanKey };', ctx);
const C = ctx.__core;

const fails = [];
const eq = (name, got, want) => {
  const g = JSON.stringify(got), w = JSON.stringify(want);
  if (g !== w) fails.push(name + ': got ' + g + ', want ' + w);
};
const ok = (name, cond) => { if (!cond) fails.push(name); };

// 1. a link round-trips, text included, and is URL-safe
const calc = { project_name: 'Bodega Ñ "uno" – 2F', floor_area: 25.5, loads: [{ load_type: 'Motor', quantity: 2 }] };
const enc = C.edShareEncode('HVAC Cooling Load', calc);
ok('the encoding is URL-safe base64 with no padding', /^[A-Za-z0-9_-]+$/.test(enc));
const dec = C.edShareDecode(enc);
eq('a link round-trips its calculator', dec && dec.t, 'HVAC Cooling Load');
eq('a link round-trips its inputs, text included', dec && dec.i, calc);

// 2. a damaged or foreign payload opens nothing
const b64 = (o) => Buffer.from(JSON.stringify(o)).toString('base64url');
for (const [name, s] of [['empty', ''], ['not base64', '!!!'], ['not JSON', Buffer.from('hello').toString('base64url')],
  ['another version', b64({ v: 2, t: 'X', i: {} })], ['inputs as a list', b64({ v: 1, t: 'X', i: [1] })],
  ['no calculator', b64({ v: 1, i: {} })]]) {
  ok('a damaged link (' + name + ') opens nothing', C.edShareDecode(s) === null);
}

// 3. a link's inputs reduce to the form's own keys and types
const defaults = { project_name: 'Untitled Room', floor_area: 0, persons: 0, building_type: 'Office', flag: false,
  loads: [{ load_type: 'Lighting (General)', quantity: 1, watts_each: 100, power_factor: 0.95 }], nested: { a: 1 } };
const shared = { project_name: '<img src=x onerror=alert(1)>"x\'`&\\', floor_area: '42.5', persons: 'abc', building_type: 'Mall',
  flag: 'true', evil_key: '<script>', nested: { a: '7', b: 'drop' },
  loads: [{ load_type: 'Motor<script>', quantity: '3', watts_each: 500, power_factor: 'x', extra: 'drop' }, 'junk', null] };
const clean = C.edShareSanitize(defaults, shared);
eq('unknown keys are dropped', Object.keys(clean).sort(), Object.keys(defaults).sort());
ok('text loses every character markup needs', !/[<>"'`&\\]/.test(clean.project_name));
eq('text keeps its words', clean.project_name, 'img src=x onerror=alert(1)x');
eq('a number given as text is a number', clean.floor_area, 42.5);
eq('a non-number keeps the form\'s value', clean.persons, 0);
eq('a choice keeps the shared word', clean.building_type, 'Mall');
eq('a yes/no keeps its type', clean.flag, true);
eq('a nested group keeps only its own keys', clean.nested, { a: 7 });
eq('list rows take the form\'s first row as their shape', clean.loads,
  [{ load_type: 'Motorscript', quantity: 3, watts_each: 500, power_factor: 0.95 }]);
const many = C.edShareSanitize({ loads: [{ q: 1 }] }, { loads: Array.from({ length: 500 }, () => ({ q: 2 })) });
eq('a list is capped', many.loads.length, 80);
eq('a list the form starts empty keeps plain values under plain names',
  C.edShareSanitize({ rows: [] }, { rows: [{ name: 'a<b', n: 2, bad: { x: 1 }, 'bad key': 1 }] }).rows, [{ name: 'ab', n: 2 }]);
eq('a missing key keeps the form\'s value', C.edShareSanitize({ a: 5, b: 'x' }, { a: 9 }), { a: 9, b: 'x' });
eq('a payload that is not an object opens the form as it is', C.edShareSanitize({ a: 5 }, 'nope'), { a: 5 });

// 4. compare sets two reports' figures side by side and names what differs, in words
eq('figures side by side, in first-seen order', C.edCompareRows(
  [{ label: 'Capacity', value: '10 kW' }, { label: 'Airflow', value: '500 L/s' }],
  [{ label: 'Capacity', value: '12 kW' }, { label: 'Fan power', value: '1.1 kW' }]),
  [{ label: 'Capacity', a: '10 kW', b: '12 kW', same: false }, { label: 'Airflow', a: '500 L/s', b: '-', same: false },
   { label: 'Fan power', a: '-', b: '1.1 kW', same: false }]);
eq('an unchanged figure is marked the same', C.edCompareRows([{ label: 'X', value: '1' }], [{ label: 'X', value: '1' }]),
  [{ label: 'X', a: '1', b: '1', same: true }]);
eq('only the inputs that differ, named in words', C.edInputDiff(
  { floor_area: 20, loads: [1, 2], flow_rate_lhr: 900, same_m: 3 }, { floor_area: 25, loads: [1, 2, 3], flow_rate_lhr: 900, same_m: 3, ambient_temp_c: 35 }),
  [{ label: 'Floor area', a: '20', b: '25' }, { label: 'Loads', a: '2 rows', b: '3 rows' },
   { label: 'Ambient temp (deg C)', a: '-', b: '35' }]);
eq('a unit suffix becomes the unit', C.edHumanKey('flow_rate_lhr'), 'Flow rate (L/h)');

if (fails.length) {
  console.log('FAIL calc-share-compare - ' + fails.length + ' check(s):');
  for (const f of fails) console.log('  - ' + f);
  process.exit(1);
}
console.log('PASS calc-share-compare - a link round-trips and is URL-safe, a damaged one opens nothing, its inputs reduce to the '
  + 'form\'s own keys and types with markup stripped, and compare sets two reports side by side (' + SRC.split(/[\\/]/).pop() + ')');
