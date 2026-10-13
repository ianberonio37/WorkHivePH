// prove_memory_age.mjs - every remembered turn a model reads says HOW LONG AGO it was said (2026-10-13).
//
// Live-caught on the voice-journal audio walk W4812: a returning worker said "Maintenance" and was told "you've asked
// this four times today". The four questions were six days old; "Recent turns" carried no time and no prompt states
// the current date. The fix (_shared/memory_age.ts + formatMemoryContext + formatJournalRecall) stamps every turn,
// summary and recalled entry with a duration.
//
// This runs the REAL formatter code under Node: the three _shared modules are copied to .tmp with their two remote
// imports stubbed (a type-only supabase-js import; the embedding chain, which formatting never calls), types stripped
// by node:module, then imported. It also feeds the aged block through the gateway's own PII scrub (redactPII.ts) so the
// age cannot be swallowed as a phone number on its way to the model.
//
// TEETH: eleven mutants - each formatter with its age call removed, an ageLabel that returns nothing, loadMemory without
// its turn order, a turnOrder blind to who spoke, a summariser that cuts at the batch size, memory keyed by the display name, and four on durable memory (recall by
// name, no-hive-as-every-hive, a write without its account, a cap counted by name) - must each FAIL a case. A mutant that passes means a case is vacuous, and the run fails.
//
//   node tools/prove_memory_age.mjs
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { stripTypeScriptTypes } from "node:module";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const SHARED = join(ROOT, "supabase", "functions", "_shared");
const OUT = join(ROOT, ".tmp", "prove_memory_age");

function load(name) { return readFileSync(join(SHARED, name), "utf8").replace(/\r\n/g, "\n"); }

function toModule(src, file) {
  let s = src
    .replace(/^import \{ SupabaseClient \} from "https:\/\/esm\.sh\/[^"]+";\n/m, "")
    .replace(/^import \{ generateEmbedding \} from "\.\/embedding-chain\.ts";\n/m, "const generateEmbedding = async () => [];\n")
    .replace(/from "\.\/(memory_age|redactPII)\.ts"/g, 'from "./$1.mjs"');
  if (/from "https?:/.test(s) || /from "\.\/(?!memory_age|redactPII)/.test(s)) throw new Error(`${file}: an import the prover does not stub`);
  return stripTypeScriptTypes(s, { mode: "strip" });
}

let variant = 0;
async function build(mutate = {}) {
  const dir = join(OUT, `v${variant++}`);
  mkdirSync(dir, { recursive: true });
  for (const [ts, mjs] of [["memory_age.ts", "memory_age.mjs"], ["memory.ts", "memory.mjs"],
                           ["journal-recall.ts", "journal-recall.mjs"], ["redactPII.ts", "redactPII.mjs"],
                           ["episodic-memory.ts", "episodic-memory.mjs"]]) {
    let src = load(ts);
    if (mutate[ts]) {
      const [from, to] = mutate[ts];
      if (!src.includes(from)) throw new Error(`mutant anchor missing in ${ts}: ${from}`);
      src = src.split(from).join(to);
    }
    writeFileSync(join(dir, mjs), toModule(src, ts));
  }
  const imp = (f) => import(pathToFileURL(join(dir, f)).href);
  return { age: await imp("memory_age.mjs"), mem: await imp("memory.mjs"), rec: await imp("journal-recall.mjs"), pii: await imp("redactPII.mjs"),
           epi: await imp("episodic-memory.mjs") };
}

// A fake supabase client over a fixed set of agent_memory rows. Ties (a question and its answer share one created_at)
// come back in the order that DEFEATS naive code: question-first in a newest-first read (reversed, the answer lands
// first), answer-first in an oldest-first read (the order seen live).
function fakeDb(rows, log) {
  return {
    from() {
      const st = { filters: [], head: false, asc: null, limit: null, range: null, del: false, upd: false };
      const b = {
        select(_c, opts) { if (opts && opts.head) st.head = true; return b; },
        eq(c, v) { st.filters.push([c, v]); return b; },
        is(c) { st.filters.push([c, null]); return b; },
        order(_c, o) { st.asc = !!(o && o.ascending); return b; },
        limit(n) { st.limit = n; return b; },
        range(a, z) { st.range = [a, z]; return b; },
        insert(obj) {
          const list = Array.isArray(obj) ? obj : [obj];
          log.inserts.push(...list);
          const done = { error: null, data: list.map((_, i) => ({ id: `new${log.inserts.length - list.length + i}` })) };
          return { select: () => Promise.resolve(done), then: (res, rej) => Promise.resolve({ error: null }).then(res, rej) };
        },
        update() { st.upd = true; return b; },
        delete() { st.del = true; return b; },
        in(c, vals) {
          if (st.del) { log.deletes.push(...vals); return Promise.resolve({ error: null }); }
          st.filters.push([c, vals, "in"]); return b;
        },
        then(res, rej) {
          if (st.upd) return Promise.resolve({ error: null }).then(res, rej);
          let out = rows.filter((r) => st.filters.every(([c, v, op]) =>
            op === "in" ? v.includes(r[c]) : (v === null ? r[c] == null : r[c] === v)));
          const agentFirst = st.asc !== false;
          out = [...out].sort((a, c) => {
            const d = Date.parse(a.created_at) - Date.parse(c.created_at);
            if (d) return st.asc === false ? -d : d;
            const ra = a.meta && a.meta.role === "agent" ? 0 : 1, rc = c.meta && c.meta.role === "agent" ? 0 : 1;
            return agentFirst ? ra - rc : rc - ra;
          });
          if (st.range) out = out.slice(st.range[0], st.range[1] + 1);
          if (st.limit != null) out = out.slice(0, st.limit);
          const value = st.head ? { count: out.length, error: null } : { data: out, error: null };
          return Promise.resolve(value).then(res, rej);
        },
      };
      return b;
    },
  };
}

// n question/answer pairs, oldest first; each pair shares one created_at (one insert, one now())
const KEYS = { hive_id: "h1", worker_name: "W", auth_uid: "u1", agent_id: "voice-journal" };
function pairs(n, startMs, orphanHead = false, keys = KEYS) {
  const rows = [];
  if (orphanHead) rows.push({ ...keys, id: "orphan-a", kind: "turn", created_at: new Date(startMs - 60_000).toISOString(), turn_text: "an answer whose question was summarised", meta: { role: "agent" } });
  for (let i = 1; i <= n; i++) {
    const at = new Date(startMs + i * 60_000).toISOString();
    rows.push({ ...keys, id: `p${i}u`, kind: "turn", created_at: at, turn_text: `question ${i}`, meta: { role: "user" } });
    rows.push({ ...keys, id: `p${i}a`, kind: "turn", created_at: at, turn_text: `answer ${i}`, meta: { role: "agent" } });
  }
  return rows;
}

const NOW = new Date("2026-10-13T07:42:00Z");
const ago = (ms) => new Date(NOW.getTime() - ms).toISOString();
const MIN = 60_000, H = 60 * MIN, D = 24 * H;

async function cases(m) {
  const out = [];
  const check = (name, ok, got) => out.push({ name, ok: !!ok, got });

  // 1. the duration table
  const table = [
    [ago(0), "just now"], [ago(90_000), "just now"], [ago(5 * MIN), "5 minutes ago"], [ago(61 * MIN), "1 hour ago"],
    [ago(3 * H), "3 hours ago"], [ago(25 * H), "1 day ago"], [ago(6 * D + 5 * MIN), "6 days ago"],
    [ago(15 * D), "2 weeks ago"], [ago(70 * D), "2 months ago"],
    [new Date(NOW.getTime() + 5 * MIN).toISOString(), ""], ["not a date", ""], [null, ""],
  ];
  for (const [iso, want] of table) {
    const got = m.age.ageLabel(iso, NOW);
    check(`ageLabel(${iso}) = ${JSON.stringify(want)}`, got === want, got);
  }

  // 2. the live-caught shape: four six-day-old questions in "Recent turns"
  const q = "What maintenance has been done on AC-002 recently?";
  const turns = [];
  for (let i = 0; i < 4; i++) {
    turns.push({ role: "user", text: q, created_at: ago(6 * D + (40 - i * 5) * MIN) });
    turns.push({ role: "agent", text: "AC-002's last five events were all PMs.", created_at: ago(6 * D + (39 - i * 5) * MIN) });
  }
  const block = m.mem.formatMemoryContext({ recent_turns: turns, summary: "Asked about AC-002 PMs.", summary_at: ago(15 * D) }, NOW);
  const lines = block.split("\n");
  const turnLines = lines.filter((l) => /(^|\] )(Worker|Agent): /.test(l));
  check("all 8 remembered turns are rendered", turnLines.length === 8, turnLines.length);
  check("every remembered turn says it is 6 days old", turnLines.every((l) => l.startsWith("[6 days ago] ")), turnLines[0]);
  check("no remembered turn is rendered without its age", !lines.some((l) => /^(Worker|Agent): /.test(l)), lines.find((l) => /^(Worker|Agent): /.test(l)));
  check("the summary says when it was written", /\(summary, written 2 weeks ago\):/.test(block), lines[0]);
  check("the block tells the model a turn from days ago is not today", /a turn from days ago is not today/.test(block), lines.find((l) => l.startsWith("Recent turns")));

  // 3. a turn with no time is still rendered, claiming no age
  const bare = m.mem.formatMemoryContext({ recent_turns: [{ role: "user", text: "hello" }], summary: null }, NOW);
  check("a turn with no created_at renders without a bracket", /\nWorker: hello$/.test(bare), bare);

  // 4. the journal recall puts the age beside the date
  const recall = m.rec.formatJournalRecall([{ id: "x", transcript: q, reply: "", lang: "english", similarity: 0.92, created_at: ago(6 * D) }], NOW);
  check("a recalled entry says it is 6 days old, beside its date", /#1 \(6 days ago, 2026-10-07 \[english\], 92% similar\)/.test(recall), recall.split("\n")[1]);
  check("the recall header the voice-journal prompt names is unchanged",
        recall.startsWith("Past journal entries that look related to today's voice note"), recall.split("\n")[0]);

  // 5. the age survives the gateway's PII scrub on its way to the model (redactMemoryText)
  const scrubbed = m.pii.redactMemoryText(`${block}\n\n${recall}`, []).redacted;
  check("the ages survive the PII scrub", (scrubbed.match(/\[6 days ago\] /g) || []).length === 8 && scrubbed.includes("(6 days ago, 2026-10-07"),
        (scrubbed.match(/\[[^\]]*\] Worker/) || [""])[0]);

  // 6. loadMemory: a question comes before its answer, whatever order the database returns a tie in
  const HANDLE = { hive_id: "h1", worker_name: "W", auth_uid: "u1", agent_id: "voice-journal" };
  const t0 = NOW.getTime() - 6 * D;
  const memRows = [...pairs(4, t0), { ...KEYS, id: "s1", kind: "summary", created_at: new Date(t0 - D).toISOString(), summary: "earlier talk", meta: {} }];
  const loaded = await m.mem.loadMemory(fakeDb(memRows, { inserts: [], deletes: [] }), HANDLE);
  const roles = loaded.recent_turns.map((t) => t.role).join(",");
  check("loadMemory puts each question before its answer", roles === "user,agent,user,agent,user,agent,user,agent", roles);
  check("loadMemory returns when the summary was written", loaded.summary === "earlier talk" && loaded.summary_at === memRows[8].created_at, loaded.summary_at);

  // 7. summariseIfNeeded folds WHOLE pairs, in question-then-answer order
  const log7 = { inserts: [], deletes: [] };
  let transcript7 = "";
  await m.mem.summariseIfNeeded(fakeDb(pairs(7, t0), log7), HANDLE, async (t) => { transcript7 = t; return "S"; });
  const del7 = [...log7.deletes].sort().join(",");
  check("the summary folds three whole pairs, leaving no half exchange", del7 === "p1a,p1u,p2a,p2u,p3a,p3u", del7);
  check("the transcript the summariser reads is question-then-answer",
        /^User: question 1\nAssistant: answer 1\nUser: question 2\nAssistant: answer 2\nUser: question 3\nAssistant: answer 3$/.test(transcript7), transcript7);

  // 8. an orphan left by the old odd batch is folded without splitting the next pair
  const log8 = { inserts: [], deletes: [] };
  await m.mem.summariseIfNeeded(fakeDb(pairs(6, t0, true), log8), HANDLE, async () => "S");
  const del8 = [...log8.deletes].sort().join(",");
  check("with an orphan at the head, the cut still falls between pairs", del8 === "orphan-a,p1a,p1u,p2a,p2u", del8);

  // 9-10. WHOSE: a rename frees a name; the next person to join under it is a different account
  const prev = pairs(7, t0, false, { ...KEYS, worker_name: "Juan", auth_uid: "uA" }).map((r) => ({ ...r, id: "A-" + r.id, turn_text: "A: " + r.turn_text }));
  const next = pairs(1, t0 + 3 * D, false, { ...KEYS, worker_name: "Juan", auth_uid: "uB" }).map((r) => ({ ...r, id: "B-" + r.id }));
  const newcomer = { hive_id: "h1", worker_name: "Juan", auth_uid: "uB", agent_id: "voice-journal" };
  const seen = await m.mem.loadMemory(fakeDb([...prev, ...next], { inserts: [], deletes: [] }), newcomer);
  check("a newcomer under a freed name reads none of the previous person's turns",
        seen.recent_turns.length === 2 && !seen.recent_turns.some((t) => t.text.startsWith("A: ")), seen.recent_turns.map((t) => t.text).join(" | "));
  const log10 = { inserts: [], deletes: [] };
  await m.mem.summariseIfNeeded(fakeDb([...prev, ...next], log10), newcomer, async () => "S");
  check("a newcomer's turn never folds or deletes the previous person's memory", log10.deletes.length === 0 && log10.inserts.length === 0,
        log10.deletes.join(","));

  // 11-14. DURABLE (episodic) memory: written with the account, read and capped by it; no hive means solo
  const mem = (id, keys, extra = {}) => ({ id, memory_type: "factual", content: `${id} fact`, importance: 0.5, use_count: 0,
                                          last_used_at: null, superseded_by: null, ...keys, ...extra });
  const epiRows = [
    mem("A1", { hive_id: "h1", worker_name: "Juan", auth_uid: "uA" }), mem("A2", { hive_id: "h1", worker_name: "Juan", auth_uid: "uA" }),
    mem("B1", { hive_id: "h1", worker_name: "Juan", auth_uid: "uB" }),
    mem("S1", { hive_id: null, worker_name: "Juan", auth_uid: "uB" }),
    mem("Z1", { hive_id: "h1", worker_name: "status", auth_uid: null }),
  ];
  const got11 = await m.epi.recallEpisodic(fakeDb(epiRows, { inserts: [], deletes: [] }), "h1", "Juan", { authUid: "uB", bump: false, limit: 10 });
  const ids11 = got11.map((r) => r.id).sort().join(",");
  check("durable recall by account: a newcomer under a freed name reads only their own", ids11 === "B1", ids11);
  const got12 = await m.epi.recallEpisodic(fakeDb(epiRows, { inserts: [], deletes: [] }), null, "Juan", { authUid: "uB", bump: false, limit: 10 });
  const ids12 = got12.map((r) => r.id).sort().join(",");
  check("durable recall with no hive reads solo memories only, never every hive", ids12 === "S1", ids12);
  const log13 = { inserts: [], deletes: [] };
  await m.epi.persistEpisodic(fakeDb([], log13), "h1", "Juan", [{ memory_type: "factual", content: "a new fact" }], "uB");
  check("a durable memory is written with its account", log13.inserts.length === 1 && log13.inserts[0].auth_uid === "uB",
        JSON.stringify(log13.inserts[0] || null));
  const crowd = Array.from({ length: m.epi.PER_WORKER_CAP + 5 }, (_, i) => mem(`A-${i}`, { hive_id: "h1", worker_name: "Juan", auth_uid: "uA" }));
  const log14 = { inserts: [], deletes: [] };
  await m.epi.evictIfOverCap(fakeDb([...crowd, epiRows[2]], log14), "h1", "Juan", "uB");
  check("the per-person cap counts the account: a newcomer's store never evicts the previous person's memories",
        log14.deletes.length === 0, `${log14.deletes.length} evicted`);
  return out;
}

const report = (rows) => rows.filter((r) => !r.ok);

const real = await cases(await build());
const failed = report(real);
for (const r of real) console.log(`  ${r.ok ? "ok  " : "FAIL"} ${r.name}${r.ok ? "" : `  (got ${JSON.stringify(r.got)})`}`);

const MUTANTS = {
  "formatMemoryContext without its age": { "memory.ts": ["ageLabel(t.created_at, now)", '""'] },
  "formatJournalRecall without its age": { "journal-recall.ts": ["ageLabel(r.created_at, now)", '""'] },
  "an ageLabel that says nothing": { "memory_age.ts": ['if (!iso) return "";', 'return "";'] },
  "loadMemory without its turn order": { "memory.ts": ["  recent_turns.sort(turnOrder);", ""] },
  "a turnOrder that ignores who spoke": { "memory_age.ts": ['return (a.role === "agent" ? 1 : 0) - (b.role === "agent" ? 1 : 0);', "return 0;"] },
  "a summariser that cuts at the batch size": { "memory.ts": ["oldestWholeTurns(fetched, SUMMARISE_BATCH)", "fetched.slice(0, SUMMARISE_BATCH)"] },
  "memory keyed by the display name": { "memory.ts": ['return h.auth_uid ? ["auth_uid", h.auth_uid] : ["worker_name", h.worker_name];', 'return ["worker_name", h.worker_name];'] },
  "durable recall by display name": { "episodic-memory.ts": ['if (opts.authUid) q = q.eq("auth_uid", opts.authUid);', "if (false) q = q;"] },
  "durable recall with no hive reads every hive": { "episodic-memory.ts": ['q = hiveId ? q.eq("hive_id", hiveId) : q.is("hive_id", null);', 'if (hiveId) q = q.eq("hive_id", hiveId);'] },
  "a durable write without its account": { "episodic-memory.ts": ["auth_uid:        authUid,", "auth_uid:        null,"] },
  "the per-person cap counted by name": { "episodic-memory.ts": ['authUid ? scopeQ.eq("auth_uid", authUid) : scopeQ.eq("worker_name", s.worker)', 'scopeQ.eq("worker_name", s.worker)'] },
};
let survivors = 0;
for (const [name, mut] of Object.entries(MUTANTS)) {
  const killedBy = report(await cases(await build(mut)));
  const killed = killedBy.length > 0;
  survivors += killed ? 0 : 1;
  console.log(`  mutant ${killed ? "killed  " : "SURVIVED"} ${name}${killed ? ` (${killedBy.length} case(s) fail, e.g. "${killedBy[0].name}")` : ""}`);
}

if (failed.length || survivors) {
  console.log(`FAIL: ${failed.length} case(s) failed on the real code, ${survivors} mutant(s) survived`);
  process.exit(1);
}
console.log(`PASS: memory age - ${real.length} cases on the real formatters, ${Object.keys(MUTANTS).length}/${Object.keys(MUTANTS).length} mutants killed`);
