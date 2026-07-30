// tenant_context_contract.mjs — behavioural + mutation teeth on _shared/tenant-context.ts, cache-free.
//
// WHY THIS EXISTS. The edge runtime serves a CACHED module: editing tenant-context.ts on disk does NOT change
// the running function until the runtime restarts (proven 2026-07-31 with a sentinel — the mutated 403 message
// never appeared over HTTP). So a mutation harness that edits the file and calls the function over HTTP would
// score every mutant as "killed" while nothing actually changed — the exact fabricated-100% shape this
// platform corrected in the guard mutation arc. Node v24 strips TypeScript types natively, so instead this
// loads the REAL helper as a module (only the type-only SupabaseClient import is neutralized), runs its actual
// functions against a stubbed Supabase client, and MUTATES the source text to prove the assertions have teeth.
//
// The 30 service-role edge functions that call resolveContext/resolveTenancy trust two decisions here:
//   - isServiceRoleBearer: the single predicate that lets a caller SKIP membership entirely. If it prefix-
//     matches, or accepts any bearer when the env key is unset, every hive is open to a crafted token.
//   - resolveTenancy: null auth => 401; a non-member => 403; a member => ok. The DB-level escalation (a rename
//     into another hive) is locked separately by validate_membership_resolved_by_auth_uid.py; THIS locks the
//     helper's own branch logic.
//
// Each mutant must be KILLED (flip at least one assertion). A surviving mutant is a behaviour no assertion
// objects to — printed, never averaged away.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const HELPER = process.argv[2] ||
  'c:/Users/ILBeronio/Desktop/Industry 4.0/AI Maintenance Engineer/Self-learning Road-Map/Build & Sell with Claude Code/Website simple 1st/supabase/functions/_shared/tenant-context.ts';

const REAL_KEY = 'SERVICE_ROLE_KEY_VALUE_x9';
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'tcc-'));
let counter = 0;

function neutralizeImport(src) {
  // Replace the single type-only runtime import so node can load the module offline. SupabaseClient is used
  // only as a type annotation, so `type SupabaseClient = any` is behaviourally identical after type-stripping.
  const out = src.replace(/^import\s*\{\s*SupabaseClient\s*\}\s*from\s*"[^"]*";/m, 'type SupabaseClient = any;');
  if (out.indexOf('esm.sh') !== -1) throw new Error('failed to neutralize the SupabaseClient import');
  return out;
}

// A stub Supabase client. `plan` decides what the membership/profile lookups return, and every .eq() filter is
// recorded so a mutant that DROPS a filter can be caught by asserting the filters that were applied.
function makeDb(plan) {
  const filters = [];
  const builder = (table) => {
    const b = {
      _table: table,
      select() { return b; },
      eq(col, val) { filters.push(`${table}.${col}=${val}`); return b; },
      maybeSingle() {
        if (table === 'v_worker_truth') return Promise.resolve({ data: plan.member || null });
        if (table === 'worker_profiles') return Promise.resolve({ data: plan.profile || null });
        return Promise.resolve({ data: null });
      },
    };
    return b;
  };
  return {
    _filters: filters,
    from: (t) => builder(t),
    auth: { getUser: (bearer) => Promise.resolve({ data: { user: plan.user === undefined ? { id: 'uid-from-jwt' } : plan.user } }) },
  };
}

function req(bearer) {
  return new Request('http://x', { headers: bearer ? { authorization: 'Bearer ' + bearer } : {} });
}

async function load(src, keyEnv) {
  globalThis.Deno = { env: { get: (k) => (k === 'SUPABASE_SERVICE_ROLE_KEY' ? keyEnv : '') } };
  const f = path.join(TMP, `tc_${counter++}.ts`);
  fs.writeFileSync(f, neutralizeImport(src));
  return await import(pathToFileURL(f).href);
}

// The contract. Returns [{name, pass}]. `keyEnv` is the service-role key the module sees at load.
async function assertContract(src) {
  const results = [];
  const A = (name, cond) => results.push({ name, pass: !!cond });

  // ── isServiceRoleBearer, env key PRESENT ──
  let m = await load(src, REAL_KEY);
  A('service-role: exact key is accepted', m.isServiceRoleBearer(REAL_KEY) === true);
  A('service-role: a prefix of the key is REJECTED', m.isServiceRoleBearer(REAL_KEY.slice(0, 8)) === false);
  A('service-role: a superstring of the key is REJECTED', m.isServiceRoleBearer(REAL_KEY + 'x') === false);
  A('service-role: empty bearer is REJECTED', m.isServiceRoleBearer('') === false);

  // ── isServiceRoleBearer, env key ABSENT (fail-closed) ──
  m = await load(src, '');
  A('service-role: with no env key, empty bearer is REJECTED', m.isServiceRoleBearer('') === false);
  A('service-role: with no env key, ANY bearer is REJECTED', m.isServiceRoleBearer('anything') === false);

  // ── resolveIdentity ──
  m = await load(src, REAL_KEY);
  let id = await m.resolveIdentity(makeDb({}), req(REAL_KEY));
  A('identity: service-role bearer => isServiceRole, authUid null', id.isServiceRole === true && id.authUid === null);
  id = await m.resolveIdentity(makeDb({ user: { id: 'uid-42' } }), req('a-user-jwt'));
  A('identity: a user bearer => not service-role, authUid from JWT', id.isServiceRole === false && id.authUid === 'uid-42');

  // ── resolveTenancy ──
  m = await load(src, REAL_KEY);
  let t = await m.resolveTenancy(makeDb({}), null, 'hive-1');
  A('tenancy: null authUid => 401 auth_required', t.ok === false && t.status === 401);

  const memberRow = { worker_name: 'Ada', role: 'worker', hive_status: 'active' };
  const db1 = makeDb({ member: memberRow });
  t = await m.resolveTenancy(db1, 'uid-1', 'hive-1');
  A('tenancy: an active member of the hive => ok', t.ok === true && t.hive_id === 'hive-1');
  A('tenancy: membership lookup filtered by auth_uid', db1._filters.some(f => f.includes('auth_uid=uid-1')));
  A('tenancy: membership lookup filtered by hive_id', db1._filters.some(f => f.includes('hive_id=hive-1')));
  A('tenancy: membership lookup filtered by active status',
    db1._filters.some(f => f.includes('hive_status=active') || f.includes('status=active')));

  t = await m.resolveTenancy(makeDb({ member: null }), 'uid-1', 'hive-1');
  A('tenancy: a non-member => 403 not_a_member', t.ok === false && t.status === 403);

  t = await m.resolveTenancy(makeDb({ profile: { display_name: 'Ada' } }), 'uid-1', '');
  A('tenancy: hiveless caller with a profile => solo ok', t.ok === true && t.is_solo === true && t.hive_id === null);

  t = await m.resolveTenancy(makeDb({ profile: null }), 'uid-1', '');
  A('tenancy: hiveless caller with NO profile => 403 no_profile', t.ok === false && t.status === 403);

  return results;
}

// ── Mutations. Each transforms the source text; a viable mutant must flip >=1 assertion. ──
// An `equivalent` mutant provably cannot change behaviour; it is EXCLUDED from the score with a mechanism, and
// the exclusion is FALSIFIABLE — if such a mutant is ever KILLED, the equivalence reasoning is wrong and the
// run fails as a stale exclusion (the discipline from the guard mutation arc).
const MUTANTS = [
  { name: 'service-role: exact-match weakened to a prefix match',
    apply: s => s.replace('bearer === key', 'key.startsWith(bearer)') },
  { name: 'service-role: the empty-bearer guard dropped (unset env would accept "")',
    apply: s => s.replace('Boolean(bearer) && Boolean(key) && bearer === key', 'Boolean(key) === false || bearer === key') },
  { name: 'service-role: the redundant env-key guard dropped',
    equivalent: 'Boolean(key) cannot change the result: bearer === key with a truthy bearer implies key is ' +
      'truthy, and when the shared value is "" the Boolean(bearer) conjunct already short-circuits false. ' +
      'Kept in source as explicit defence-in-depth, but behaviourally redundant, so it is not scoreable.',
    apply: s => s.replace('Boolean(bearer) && Boolean(key) && bearer === key', 'Boolean(bearer) && bearer === key') },
  { name: 'tenancy: the null-authUid 401 guard removed',
    apply: s => s.replace('if (!authUid) {', 'if (false) {') },
  { name: 'tenancy: the non-member 403 refusal removed',
    apply: s => s.replace('if (!mem) {', 'if (false) {') },
  { name: 'tenancy: membership no longer filtered by hive_id',
    apply: s => s.replace('.eq("hive_id", hid)', '') },
  { name: 'tenancy: membership no longer filtered by active status',
    apply: s => s.replace('.eq("hive_status", "active")', '') },
];

async function main() {
  const src = fs.readFileSync(HELPER, 'utf8');

  // 1) The real source must satisfy the whole contract.
  const base = await assertContract(src);
  const baseFails = base.filter(r => !r.pass);
  for (const r of base) console.log(`  ${r.pass ? 'PASS' : 'FAIL'}  ${r.name}`);
  if (baseFails.length) {
    console.log(`\n  BASELINE BROKEN — the shipped helper fails ${baseFails.length} assertion(s); fix before trusting the mutation score.`);
    cleanup(); process.exit(1);
  }

  // 2) Every VIABLE mutant must be killed (flip >=1 assertion). Equivalent mutants are excluded with a
  //    mechanism and must SURVIVE — one that is killed is a stale exclusion and fails the run.
  const survivors = [], staleExclusions = [];
  let viable = 0, killedN = 0;
  for (const mut of MUTANTS) {
    const mutated = mut.apply(src);
    if (mutated === src) { survivors.push(`${mut.name}  [pattern matched nothing — mutation is vacuous]`); continue; }
    let killed = false, err = null;
    try {
      const res = await assertContract(mutated);
      killed = res.some(r => !r.pass);
    } catch (e) { killed = true; err = e.message; } // a mutant that throws is killed (behaviour changed)
    if (mut.equivalent) {
      console.log(`  ${killed ? 'STALE' : 'EQUIV'}  ${mut.name}`);
      if (killed) staleExclusions.push(`${mut.name} — was excluded as equivalent but an assertion killed it: ${mut.equivalent}`);
      continue;
    }
    viable++;
    if (killed) killedN++; else survivors.push(mut.name);
    console.log(`  ${killed ? 'KILL' : 'SURVIVE'}  ${mut.name}${err ? '  (threw: ' + err.slice(0, 40) + ')' : ''}`);
  }

  console.log(`\n  mutation: ${killedN}/${viable} viable killed` +
    (MUTANTS.some(m => m.equivalent) ? ` (${MUTANTS.filter(m => m.equivalent).length} equivalent, excluded)` : ''));
  for (const m of MUTANTS.filter(m => m.equivalent)) console.log(`  EXCLUDED (equivalent): ${m.name}\n    reason: ${m.equivalent}`);
  if (staleExclusions.length) {
    console.log('  STALE EXCLUSIONS (equivalence reasoning is wrong — an assertion objected):');
    for (const s of staleExclusions) console.log('    - ' + s);
    cleanup(); process.exit(1);
  }
  if (survivors.length) {
    console.log('  SURVIVING MUTANTS (a behaviour no assertion objects to):');
    for (const s of survivors) console.log('    - ' + s);
    cleanup(); process.exit(1);
  }
  console.log('  all viable mutants killed — the helper\'s branch logic has teeth.');
  cleanup(); process.exit(0);
}

function cleanup() { try { fs.rmSync(TMP, { recursive: true, force: true }); } catch { /* best effort */ } }

main().catch(e => { console.log('RUNNER ERROR ' + e.stack); cleanup(); process.exit(2); });
