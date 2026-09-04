/* prove_day_one_parallel_join.mjs - T185 slice 1: five workers, one code, the same minute.
 *
 * THE SCENARIO the trajectory is named for: a plant pilots WorkHive, a supervisor reads one invite
 * code out at the morning briefing, and the crew types it in at once. Nothing about that is unusual,
 * and it is the first thing that has to work - if two of the five silently fail to join, the pilot is
 * over before anyone logs a repair.
 *
 * ★WHY THIS IS NOT COVERED BY THE UNIT TESTS ALREADY WRITTEN. join-names-the-namesake proves the RPC
 * refuses a namesake by name and resolves a double-tap idempotently, both against a single caller.
 * This asks a different question: N DISTINCT identities hitting one code CONCURRENTLY. They contend
 * on the same hive row and the same unique index, and the honest answer is that every one of them is
 * either IN or told exactly why - never silently dropped, never doubled.
 *
 * ★IT ASSERTS THE THREE THINGS THAT CAN GO WRONG, not just the happy count:
 *   1. every worker who should be in, is in (no silent loss under contention);
 *   2. nobody is in TWICE (the unique index and the RPC's idempotent path agree under a real race);
 *   3. the one who shares a name with a teammate is refused BY NAME - HIVE_NAME_TAKEN - rather than
 *      by the raw index, because on day one the namesake is a person standing in the room.
 *
 * ★IT WRITES REAL ROWS AND CLEANS THEM UP, verifying the cleanup by re-counting - the discipline the
 * offline drain prover set: a probe that reconnects into a shared database must leave nothing behind.
 * Every row it makes is marked WH-T185-PARALLEL.
 *
 * Usage: node tools/prove_day_one_parallel_join.mjs [--workers 5]
 */
import { execFileSync, spawn } from 'child_process';

const CONTAINER = process.env.WH_DB_CONTAINER || 'supabase_db_workhive';
const argN = process.argv.indexOf('--workers');
const N = argN > -1 ? Math.max(2, Math.min(12, parseInt(process.argv[argN + 1], 10) || 5)) : 5;

const HIVE = 'e1851850-0000-4000-8000-00000000f001';
const CODE = 'T185PJ';
const MARK = 'WH-T185-PARALLEL';

const psql = (sql) => execFileSync('docker',
  ['exec', '-i', CONTAINER, 'psql', '-U', 'postgres', '-d', 'postgres', '-tA'],
  { input: sql, encoding: 'utf8', maxBuffer: 1 << 24 });

const uid = (i) => `e1851850-0000-4000-8000-0000000f${String(i).padStart(4, '0')}`;
/* Worker 2 is a DIFFERENT person who happens to answer to worker 1's name - two Juan Dela Cruzes on
   one crew, which is the whole scenario. The first version of this gave worker 2 its own distinct
   name and then asserted a collision, so it reported the platform as broken when the platform was
   right and the FIXTURE was wrong: 5 distinct names correctly produced 5 joins. An assertion is only
   as good as the situation it actually sets up. */
const nameOf = (i) => `${MARK} Worker ${i === 2 ? 1 : i}`;

function seed() {
  const users = Array.from({ length: N }, (_, k) => k + 1).map((i) =>
    `('${uid(i)}','00000000-0000-0000-0000-000000000000','authenticated','authenticated',` +
    `'wh-t185-par-${i}@example.com','x', now(), now(), now())`).join(',\n');
  psql(`
INSERT INTO auth.users (id, instance_id, aud, role, email, encrypted_password,
                        email_confirmed_at, created_at, updated_at)
VALUES ${users} ON CONFLICT (id) DO NOTHING;
INSERT INTO public.hives (id, name, invite_code, created_by)
VALUES ('${HIVE}', '${MARK} Plant', '${CODE}', '${MARK}') ON CONFLICT (id) DO NOTHING;
DELETE FROM public.hive_members WHERE hive_id = '${HIVE}';
`);
}

function cleanup() {
  psql(`
DELETE FROM public.hive_audit_log WHERE hive_id = '${HIVE}';
DELETE FROM public.hive_members   WHERE hive_id = '${HIVE}';
DELETE FROM public.hives          WHERE id = '${HIVE}';
DELETE FROM auth.users            WHERE email LIKE 'wh-t185-par-%';
`);
  const left = psql(`
SELECT (SELECT count(*) FROM public.hives WHERE id='${HIVE}')
     + (SELECT count(*) FROM public.hive_members WHERE worker_name LIKE '${MARK}%')
     + (SELECT count(*) FROM auth.users WHERE email LIKE 'wh-t185-par-%');`).trim();
  return parseInt(left, 10) || 0;
}

/* Every worker calls the RPC in ONE psql session, all sessions started before any finishes - the
   contention is real rather than staged, and each reports its own outcome on a marked line. */
function joinAll() {
  const calls = Array.from({ length: N }, (_, k) => k + 1).map((i) => {
    const sql = `
SET ROLE authenticated;
SET request.jwt.claims = '{"sub":"${uid(i)}","role":"authenticated"}';
SELECT 'W${i}=' || coalesce((SELECT member_status FROM public.join_hive_by_code('${CODE}', '${nameOf(i)}')), 'NULL');`;
    // spawn (not execFile) so all N sessions are open before any of them finishes - awaiting each
    // in turn would serialise the very contention this is meant to create
    return new Promise((resolve) => {
      const p = spawn('docker',
        ['exec', '-i', CONTAINER, 'psql', '-U', 'postgres', '-d', 'postgres', '-tA'],
        { stdio: ['pipe', 'pipe', 'pipe'] });
      let out = '';
      p.stdout.on('data', (d) => { out += d; });
      p.stderr.on('data', (d) => { out += d; });
      p.on('close', () => resolve({ i, out }));
      p.on('error', (e) => resolve({ i, out: `spawn failed: ${e.message}` }));
      p.stdin.write(sql);
      p.stdin.end();
    });
  });
  return Promise.all(calls);
}

const fails = [];
let results = [];
try {
  seed();
  results = await joinAll();
} catch (e) {
  console.log(`SKIP prove_day_one_parallel_join - could not reach the local database: ${String(e).slice(0, 140)}`);
  process.exit(0);
}

const joined = [];
const refusedByName = [];
for (const { i, out } of results) {
  if (/duplicate key value violates/i.test(out)) {
    fails.push(`worker ${i} hit the raw unique index instead of a named refusal - on day one that `
             + 'reaches the screen as Postgres text');
  } else if (/HIVE_NAME_TAKEN/.test(out)) {
    refusedByName.push(i);
  } else if (/W\d+=active/.test(out)) {
    joined.push(i);
  } else {
    fails.push(`worker ${i} neither joined nor was told why: ${out.replace(/\s+/g, ' ').trim().slice(0, 130)}`);
  }
}

// what the database actually holds, which is the only account that matters
const rows = psql(`SELECT count(*), count(DISTINCT auth_uid) FROM public.hive_members WHERE hive_id='${HIVE}';`)
  .trim().split('|').map((x) => parseInt(x, 10));
const [total, distinct] = rows;

const expectedIn = N - 1;                    // worker 2 shares worker 1's name
if (joined.length !== expectedIn) {
  fails.push(`${joined.length} of ${expectedIn} workers got in; the crew showed up together and `
           + `${expectedIn - joined.length} of them were left outside`);
}
if (refusedByName.length !== 1) {
  fails.push(`expected exactly ONE namesake refusal (worker 2 shares worker 1's name); got `
           + `${refusedByName.length} - the collision is the scenario, not an accident`);
}
if (total !== distinct) {
  fails.push(`${total} membership rows for ${distinct} identities - somebody joined twice under a race`);
}
if (total !== expectedIn) {
  fails.push(`the hive holds ${total} members but ${expectedIn} should have joined`);
}

const residue = cleanup();
if (residue !== 0) {
  fails.push(`${residue} probe rows survived cleanup - a prober that litters a shared database is a `
           + 'defect of its own');
}

console.log(`  workers: ${N} · joined: ${joined.length} · refused by name: ${refusedByName.length} · `
          + `rows: ${total} for ${distinct} identities · residue after cleanup: ${residue}`);
if (fails.length) {
  console.log('FAIL prove_day_one_parallel_join:');
  fails.forEach((f) => console.log('    - ' + f));
  process.exit(1);
}
console.log(`PASS prove_day_one_parallel_join - ${expectedIn} workers sharing one invite code all got `
          + 'in exactly once under real contention, and the one who shares a teammate\'s name was '
          + 'refused BY NAME rather than by the unique index.');
