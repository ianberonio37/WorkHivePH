/**
 * test_cache_keeps_no_no_answer.mjs — the shared response cache never files "no model answered" as an answer.
 *
 * WHY (2026-10-12, UFAI edge walk W4745, report-sender's spoken request). _shared/cache.ts cached() stored whatever its
 * fetcher returned. When every provider failed, callAI answers "{}" (so does the walk's no-model switch), and the five
 * cached callers - agentic-rag-loop's router (6h), grader (3h) and checker (2h), voice-action-router (6h) and
 * voice-report-intent (6h) - filed that "{}" as THE answer to the prompt. A minute-long outage was served for hours to
 * everyone who repeated the prompt after the providers came back; local ai_cache held such a row (agentic-rag-router,
 * 2026-09-07).
 *
 * This loads the REAL cached() and the REAL aiAnswered() (copied out of ai-chain.ts, so "a model replied" has one
 * definition) against an in-memory ai_cache, pins every case, then puts the pre-fix wrapper back and requires the two
 * cases that motivated the fix to fail.
 *
 *   node tools/test_cache_keeps_no_no_answer.mjs
 */
import { pathToFileURL } from 'node:url';
import { join } from 'node:path';
import { readFileSync, writeFileSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';

// line endings normalised: a Windows checkout holds these files with CRLF, and the patterns below speak LF (2026-10-27)
const SRC = readFileSync('supabase/functions/_shared/cache.ts', 'utf8').replace(/\r\n/g, '\n');
const CHAIN = readFileSync('supabase/functions/_shared/ai-chain.ts', 'utf8').replace(/\r\n/g, '\n');
const answered = CHAIN.match(/export function aiAnswered\([\s\S]*?\n}\n/);
if (!answered) { console.log('FAIL cache-keeps-no-no-answer: aiAnswered() not found in _shared/ai-chain.ts'); process.exit(1); }

// The module as Node can load it: the client import is a type only, and aiAnswered is the real function's text.
const loadable = (src) => {
  const supa = /^import \{ SupabaseClient \} from "[^"]+";$/m;
  const chain = /^import \{ aiAnswered \} from "\.\/ai-chain\.ts";$/m;
  if (!supa.test(src) || !chain.test(src)) throw new Error('cache.ts imports changed - update this test');
  return src.replace(supa, 'type SupabaseClient = any;').replace(chain, answered[0].replace(/^export /, ''));
};

const load = async (src) => {
  const dir = mkdtempSync(join(tmpdir(), 'wh-cache-'));
  const copy = join(dir, 'cache.mts');
  writeFileSync(copy, loadable(src));
  try { return await import(pathToFileURL(copy).href); } finally { rmSync(dir, { recursive: true, force: true }); }
};

// an in-memory ai_cache: maybeSingle by key, upsert on key, the fire-and-forget hit bump
const fakeDb = () => {
  const rows = new Map();
  let writes = 0;
  const db = {
    rows, get writes() { return writes; },
    from() {
      return {
        select() { return { eq(_c, key) { return { maybeSingle: async () => ({ data: rows.get(key) || null }) }; } }; },
        upsert: async (row) => { writes++; rows.set(row.key, { response_json: row.response_json, expires_at: row.expires_at }); return { error: null }; },
      };
    },
    rpc() { return Promise.resolve({ error: null }); },
  };
  return db;
};

const run = async (M) => {
  const out = {};
  // 1. no model answered: returned to the caller, never filed
  { const db = fakeDb(); const r = await M.cached(db, 'voice-report-intent', 'p1', async () => ({ data: '{}' }), 3600);
    out.noAnswerNotStored = db.writes === 0 && r.data === '{}' && r.hit === false; }
  // 2. an empty reply is not an answer either
  { const db = fakeDb(); await M.cached(db, 'm', 'p2', async () => ({ data: '   ' }), 3600);
    out.emptyNotStored = db.writes === 0; }
  // 3. a real reply is filed once and served from the cache the second time, without asking again
  { const db = fakeDb(); let calls = 0;
    const f = async () => { calls++; return { data: '{"report_types":["pm_overdue"]}' }; };
    const a = await M.cached(db, 'm', 'p3', f, 3600); const b = await M.cached(db, 'm', 'p3', f, 3600);
    out.realStoredAndServed = db.writes === 1 && calls === 1 && a.hit === false && b.hit === true && b.data === a.data; }
  // 4. a no-answer filed BEFORE this rule is a miss: the prompt is asked again and the real reply replaces it
  { const db = fakeDb(); await M.cacheStore(db, (await M.cacheLookup(db, 'm', 'p4')).key, 'm', '{}', { ttlSeconds: 3600 });
    let calls = 0;
    const r = await M.cached(db, 'm', 'p4', async () => { calls++; return { data: '{"route":"rag"}' }; }, 3600);
    out.storedNoAnswerIsMiss = calls === 1 && r.hit === false && r.data === '{"route":"rag"}'; }
  // 5. an object answer (not text) is cached exactly as before
  { const db = fakeDb(); await M.cached(db, 'm', 'p5', async () => ({ data: { answer: 'x' } }), 3600);
    out.objectStillStored = db.writes === 1; }
  return out;
};

let failed = 0;
const want = {
  noAnswerNotStored: 'a "{}" from the chain is returned and never stored',
  emptyNotStored: 'an empty reply is never stored',
  realStoredAndServed: 'a real reply is stored once and served on the repeat',
  storedNoAnswerIsMiss: 'a "{}" already in the cache is read as a miss and asked again',
  objectStillStored: 'a non-text answer is stored as before',
};
const now = await run(await load(SRC));
for (const [k, label] of Object.entries(want)) {
  if (!now[k]) { failed++; console.log(`  FAIL ${label}`); }
}
const exported = await load(SRC);
for (const [raw, isNo] of [['{}', true], ['', true], ['  {}  ', true], ['{"a":1}', false], ['hello', false]]) {
  if (exported.isNoAnswer(raw) !== isNo) { failed++; console.log(`  FAIL isNoAnswer(${JSON.stringify(raw)}) should be ${isNo}`); }
}
if (exported.isNoAnswer({}) !== false) { failed++; console.log('  FAIL isNoAnswer({}) - an object is never the chain\'s no-answer text'); }

// teeth: the wrapper as it was - store whatever came back, serve whatever is stored
const OLD = SRC
  .replace('if (lookup.hit && !isNoAnswer(lookup.data)) return', 'if (lookup.hit) return')
  .replace(/\n\s*if \(isNoAnswer\(fresh\.data\)\) return \{ data: fresh\.data, hit: false \};/, '');
if (OLD === SRC) { failed++; console.log('  FAIL teeth: could not rebuild the pre-fix wrapper (the guards moved?)'); }
else {
  const old = await run(await load(OLD));
  for (const k of ['noAnswerNotStored', 'storedNoAnswerIsMiss']) {
    if (old[k]) { failed++; console.log(`  FAIL teeth: ${want[k]} - the pre-fix wrapper passes this too, so the case proves nothing`); }
  }
}

if (failed) { console.log(`FAIL cache-keeps-no-no-answer: ${failed} check(s) failed`); process.exit(1); }
console.log('PASS cache-keeps-no-no-answer: a no-answer is returned but never filed, one already filed is asked again, a real reply is cached as before - and the pre-fix wrapper fails both teeth');
