// tools/test_wh_in_chunks.mjs - SL LB3 (2026-10-21): utils.js whInChunks against a mock builder. A lookup by many keys must
// reach the database in pieces the gateway accepts (an 8.7 KB in.() URL is a 414), and still answer as one lookup: every
// key asked once, the rows of every piece, counts summed, the first error kept. Run by tools/validate_in_list_chunked.py;
// a source file may be passed in place of utils.js (the mutants).
//   node tools/test_wh_in_chunks.mjs utils.js
import { readFileSync } from 'fs';
const src = readFileSync(process.argv[2], 'utf8');
const start = src.indexOf('async function whInChunks(');
const end = src.indexOf("if (typeof window !== 'undefined') window.whInChunks");
if (start < 0 || end < 0) { console.log('FAIL whInChunks not found'); process.exit(1); }
const whInChunks = new Function(src.slice(start, end) + '; return whInChunks;')();

let fails = 0, cases = 0;
const ok = (cond, what) => { cases++; if (!cond) { fails++; console.log('FAIL ' + what); } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// a builder that answers each piece with one row per key, records what it was asked, and how many ran at once
function mock({ fail = null, delay = 5, count = false } = {}) {
  const asked = []; let live = 0, peak = 0;
  const build = async (part) => {
    asked.push(part.slice()); live++; peak = Math.max(peak, live);
    await sleep(delay);
    live--;
    if (fail && part.includes(fail)) return { data: null, error: { message: 'boom ' + fail } };
    return { data: part.map((k) => ({ k })), error: null, count: count ? part.length : undefined };
  };
  return { build, asked, peak: () => peak };
}

// 1. nothing to ask: no request at all
{
  const m = mock();
  const r = await whInChunks([], m.build);
  ok(m.asked.length === 0 && r.data.length === 0 && r.error === null, 'an empty key list must send nothing and answer empty');
}
// 2. a list that fits one piece is one request, exactly as before
{
  const m = mock(); const keys = Array.from({ length: 40 }, (_, i) => 'k' + i);
  const r = await whInChunks(keys, m.build);
  ok(m.asked.length === 1 && m.asked[0].length === 40, 'forty keys must be one request');
  ok(r.data.length === 40, 'forty keys must answer forty rows');
}
// 3. a thousand keys go in pieces of 100 (the default), and every key is asked exactly once
{
  const m = mock(); const keys = Array.from({ length: 1000 }, (_, i) => 'id-' + i);
  const r = await whInChunks(keys, m.build);
  ok(m.asked.length === 10, 'a thousand keys must be ten pieces of 100, got ' + m.asked.length);
  ok(m.asked.every((p) => p.length <= 100), 'no piece may carry more than 100 keys');
  const flat = m.asked.flat();
  ok(flat.length === 1000 && new Set(flat).size === 1000, 'every key must be asked exactly once');
  ok(r.data.length === 1000, 'the rows of every piece must come back, got ' + r.data.length);
  ok(r.data.map((x) => x.k).join() === keys.join(), 'rows must come back in the order of their pieces');
}
// 4. repeats are asked once (a roster of clones, a feed whose authors repeat)
{
  const m = mock(); const keys = Array.from({ length: 1000 }, (_, i) => (i % 2 ? 'Bryan Garcia' : 'David Velasco'));
  const r = await whInChunks(keys, m.build, { size: 50 });
  ok(m.asked.length === 1 && m.asked[0].length === 2, 'a thousand repeats of two names must be one request for two');
  ok(r.data.length === 2, 'two distinct keys answer two rows');
}
// 5. null and undefined keys are dropped (in (null) matches nothing); real falsy keys are kept
{
  const m = mock();
  await whInChunks([null, 'a', undefined, 0, 'a'], m.build);
  ok(m.asked.length === 1 && m.asked[0].length === 2 && m.asked[0].includes(0), 'null/undefined dropped, 0 kept, repeats once');
}
// 6. the size option is honoured
{
  const m = mock(); const keys = Array.from({ length: 120 }, (_, i) => i);
  await whInChunks(keys, m.build, { size: 50 });
  ok(m.asked.length === 3 && m.asked[2].length === 20, 'size 50 must give pieces of 50, 50, 20');
}
// 7. at most `parallel` pieces in flight (default 4)
{
  const m = mock({ delay: 20 }); const keys = Array.from({ length: 1000 }, (_, i) => i);
  await whInChunks(keys, m.build);
  ok(m.peak() <= 4 && m.peak() >= 2, 'at most four pieces in flight, and more than one, got ' + m.peak());
  const m2 = mock({ delay: 20 });
  await whInChunks(keys, m2.build, { parallel: 1 });
  ok(m2.peak() === 1, 'parallel 1 must ask one piece at a time');
}
// 8. counts are summed across pieces
{
  const m = mock({ count: true }); const keys = Array.from({ length: 250 }, (_, i) => i);
  const r = await whInChunks(keys, m.build);
  ok(r.count === 250, 'counts must be summed across pieces, got ' + r.count);
}
// 9. an error in one piece is returned - not swallowed - and the other pieces' rows still come back
{
  const m = mock({ fail: 150 }); const keys = Array.from({ length: 300 }, (_, i) => i);
  const r = await whInChunks(keys, m.build);
  ok(r.error && /boom 150/.test(r.error.message), 'the failing piece\'s error must be returned');
  ok(r.data.length === 200, 'the two pieces that worked must still answer their rows, got ' + r.data.length);
}
// 10. a builder that throws is an error, not a crash
{
  const r = await whInChunks([1, 2, 3], () => { throw new Error('thrown'); });
  ok(r.error && r.error.message === 'thrown' && r.data.length === 0, 'a throwing builder must come back as an error');
}

console.log(fails ? `FAIL ${fails} of ${cases} cases` : `PASS ${cases} cases`);
process.exit(fails ? 1 : 0);
