// selftest_fn_field_shapes — the two request shapes prove_fn_contracts could not build.
//
// The contract prober fills in whatever a function complains is missing and asks again, which is how it
// reaches the claim rather than dying on its own request shape. Two shapes defeated it, each while the
// function was spelling out exactly what it wanted:
//
//   "Missing required field: payload (object)"   - a string was posted back every time, so the same
//                                                  complaint returned and the loop called it a dead end
//   "Missing required field: time_range.{from,to}" - a top-level key literally named "time_range.from"
//                                                  leaves the object the function reads still missing
//
// Both are the lesson that file already carries three times over: a function that names what it needs is
// answering the question. Pinned here in both directions - the shapes are built, and a plain field is
// still set flat.
//
//   node tools/selftest_fn_field_shapes.mjs
//
// (A FILE, not an inline shell test: six times this session a heredoc turned an escape into a control
// byte and reported a false result about correct code.)

const valueForTyped = (field, s) => {
  const typed = new RegExp('\\b' + field.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b[^.\\n]{0,24}\\((object|array|number|boolean)\\)', 'i').exec(s);
  if (!typed) return undefined;
  const t = typed[1].toLowerCase();
  return t === 'object' ? {} : t === 'array' ? [] : t === 'number' ? 1 : true;
};

const setPath = (body, field, value) => {
  const path = field.replace(/[{}]/g, '').split('.').filter(Boolean);
  if (path.length < 2) { body[field] = value; return body; }
  let node = body;
  for (let d = 0; d < path.length - 1; d++) {
    if (typeof node[path[d]] !== 'object' || node[path[d]] === null) node[path[d]] = {};
    node = node[path[d]];
  }
  node[path[path.length - 1]] = value;
  return body;
};

const CASES = [
  ['an object is asked for and built', () => JSON.stringify(valueForTyped('payload', 'Missing required field: payload (object)')) === '{}'],
  ['an array is asked for and built', () => JSON.stringify(valueForTyped('items', 'Missing required field: items (array)')) === '[]'],
  ['a number is asked for and built', () => valueForTyped('count', 'Missing required field: count (number)') === 1],
  ['a boolean is asked for and built', () => valueForTyped('dry_run', 'Missing required field: dry_run (boolean)') === true],
  ['no type named leaves the old path alone', () => valueForTyped('question', 'Missing required field: question') === undefined],
  ['another field\'s type is not borrowed', () => valueForTyped('question', 'Missing required field: payload (object)') === undefined],
  ['a dotted path becomes an object', () => JSON.stringify(setPath({}, 'time_range.from', '2026-01-01')) === '{"time_range":{"from":"2026-01-01"}}'],
  ['a braced path becomes an object', () => JSON.stringify(setPath({}, 'window.{days}', 30)) === '{"window":{"days":30}}'],
  ['a plain field still lands flat', () => JSON.stringify(setPath({}, 'hive_id', 'h')) === '{"hive_id":"h"}'],
  ['a second leaf joins the same object', () => {
    const b = setPath({}, 'time_range.from', 'a');
    setPath(b, 'time_range.to', 'b');
    return JSON.stringify(b) === '{"time_range":{"from":"a","to":"b"}}';
  }],
];

let bad = 0;
for (const [name, fn] of CASES) {
  let ok = false;
  try { ok = fn(); } catch (e) { ok = false; }
  if (!ok) bad++;
  console.log(`  ${ok ? 'ok ' : 'BAD'} ${name}`);
}
console.log();
console.log(bad
  ? `  FAIL - ${bad} case(s) wrong`
  : '  PASS - a named type and a dotted path both reach the shape the function asked for');
process.exit(bad ? 1 : 0);
