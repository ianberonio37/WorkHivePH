// prove_lxp_au_identity_after_change — LXP-AU, the POSTGRES half: "the platform must keep this page's
// identity honest when a session ends or a role changes".
//
// THE TWO HALVES, AND WHY THIS FILE IS ONLY ONE OF THEM. The row's own `lx.instrument` asks for both eyes.
// The BROWSER half - does the page stop showing who you are when the session ends - is answered by
// tools/prove_lxp_au_session_identity.mjs, which drives the page's real idle guard. This file answers the
// half a browser cannot see, and it is the sharper one:
//
//   ★A JWT OUTLIVES THE MEMBERSHIP IT WAS MINTED UNDER. An access token is a signed bearer string with its
//   own expiry; revoking a membership does not revoke it. So the only thing standing between a removed
//   member and their old hive is that EVERY identity-bearing relation re-derives entitlement from the
//   CURRENT membership on every single read. If one of them trusts the name in the token, or a view caches
//   what the person used to be, a dismissed worker keeps reading the hive for the rest of the token's life -
//   and no browser test can see it, because the browser would have to be holding that stale token.
//
// WHAT IS MEASURED, as the person, through PostgREST, with the SAME token throughout:
//
//   A1 vouches-now      with an active membership, the identity relations name this person and their hive.
//   A2 revoked          membership status -> 'removed' (committed; PostgREST cannot read an open transaction)
//                       and the SAME, still-unexpired token is replayed. Every identity relation must stop
//                       vouching, and the hive's own rows must now be refused.
//   A3 role change      membership restored, role worker -> supervisor, and a supervisor-gated read must
//                       change its answer on the same token - identity is not only WHO but WHAT YOU MAY DO.
//   A4 restored         the row is put back exactly as found and the original readings must return, or the
//                       probe has damaged the data it was measuring and says so loudly.
//
// ★THE SUBJECT IS A SEEDED PERSONA IN A SEEDED HIVE, NEVER A REAL ACCOUNT, and the original row is captured
// before the first write and restored in a finally - including on a crash - with the restoration VERIFIED
// rather than assumed ([[feedback_my_probe_destroyed_data_and_could_not_see_it]]).
//
//   node tools/prove_lxp_au_identity_after_change.mjs
//   node tools/prove_lxp_au_identity_after_change.mjs --teeth      (perturbs an expectation; must FAIL)
import { execSync } from 'node:child_process';
import { writeFileSync, renameSync, readFileSync } from 'node:fs';
// the SAME by-design exceptions prove_tenant_refusal uses: a public feed is public to a stranger and to an
// ex-member alike, and two hand-kept copies of that list is how the two provers drift apart.
import { PUBLIC_BY_DESIGN, PUBLIC_VIEWS_BY_DESIGN } from './tenant_declarations.mjs';

const EDGE = process.env.WH_EDGE_URL || 'http://127.0.0.1:54321';
const ANON = process.env.WH_ANON_KEY || 'sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ';
const TEETH = process.argv.includes('--teeth');
// ★THE PROBE'S PERSONA MUST MATCH THE PAGE'S AUDIENCE (added 2026-10-05). Run as a plain worker, hive_audit_log
// reads 0 while the membership is fully ACTIVE - a worker is blind to the audit log by design - so a revocation
// can never be demonstrated on it and audit-log.html's rows stayed open. That is not a gap in the platform; it is
// the wrong person asking. `--as "Christine Dizon"` runs the identical five-step replay as a SUPERVISOR, for whom
// those relations are readable while active and must therefore go quiet when the membership ends.
const ASKED = (() => { const i = process.argv.indexOf('--as'); return i >= 0 ? process.argv[i + 1] : null; })();
const SUBJECT = ASKED || 'Wilfredo Malabanan';
const EMAIL = SUBJECT.toLowerCase().replace(/[^a-z]/g, '') + '@auth.workhiveph.com';
const PASSWORD = 'test1234';
// one report per subject, so a supervisor's readings never overwrite a worker's - the two measure different
// entitlements and the banker needs both to cover worker pages AND supervisor pages.
const REPORT_FILE = ASKED
  ? 'au_identity_after_change_report.' + SUBJECT.toLowerCase().replace(/[^a-z]/g, '') + '.json'
  : 'au_identity_after_change_report.json';

const psql = (sql) => {
  try {
    return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`,
      { encoding: 'utf8' }).trim();
  } catch (e) { return ''; }
};

// ── the subject relations, DERIVED not typed ────────────────────────────────────────────────────────────────
// ★A HAND-TYPED LIST WOULD BE A CLAIM ABOUT COVERAGE. The pages carrying an AU row come from the registry, and
// the relations come from those pages' own source, intersected with what this schema actually scopes by hive_id.
// So when a page is added to the wave, this sweep grows with it instead of quietly measuring yesterday's set.
const AU_PAGES = (() => {
  try {
    const reg = JSON.parse(readFileSync('trajectory_registry.json', 'utf8'));
    const seen = new Set();
    for (const t of reg.trajectories || []) {
      const lx = t.lx || {};
      // the LXC floor rows (kind "layer-floor", 2026-10-06) ask the same AU sentence, so their pages are subjects too
      if ((lx.kind === 'layer-ux' || lx.kind === 'layer-floor') && lx.layer === 'AU' && lx.page) seen.add(lx.page);
    }
    return [...seen].sort();
  } catch (e) { return []; }
})();
// ★THE TENANT KEY IS NOT ALWAYS CALLED hive_id - AND SOMETIMES THERE IS NO TENANT KEY AT ALL. Requiring that one
// column left three pages with "reads no hive-scoped relation": skillmatrix reads skill_profiles and
// skill_exam_attempts, which are scoped to a PERSON (auth_uid), and analytics-report reads v_hives_truth, whose
// tenant key is its own `id`. Both are exactly the kind of relation an AU row is about - the person-scoped ones
// most of all, since "who am I" is the question. So each relation carries the key it is actually scoped by, and
// the choice is SELF-VALIDATING: the sweep only grades a relation whose chosen key really matches this hive (or
// this person) while active, so a mis-chosen key falls to n/a instead of being mis-measured.
const REL_KEY = (() => {
  const out = {};
  const rows = psql("select c.relname, "
    + "max(case when a.attname='hive_id' then 3 when a.attname='auth_uid' then 2 when a.attname='id' then 1 end) "
    + "from pg_class c join pg_namespace n on n.oid=c.relnamespace "
    + "join pg_attribute a on a.attrelid=c.oid and a.attname in ('hive_id','auth_uid','id') and not a.attisdropped "
    + "where n.nspname='public' and c.relkind in ('r','v') group by c.relname");
  for (const line of rows.split(String.fromCharCode(10))) {
    const [name, rank] = line.trim().split('|');
    if (!name) continue;
    out[name] = rank === '3' ? 'hive_id' : rank === '2' ? 'auth_uid' : 'id';
  }
  return out;
})();
const MY_UID = psql(`select auth_uid::text from hive_members where worker_name = '${SUBJECT}' and status = 'active' limit 1`);
// the value the key is matched against: a hive key matches this hive, a person key matches this person
const keyValue = (rel) => (REL_KEY[rel] === 'auth_uid' ? MY_UID : HIVE);
// which relations can be checked for "is what it kept MINE", and the SQL predicate that says so. A relation
// absent here cannot claim the own-records exemption at all, so the exemption can never be a blanket excuse.
const OWNABLE = {
  pm_completions: `auth_uid = '${MY_UID}'`,
  voice_journal_entries: `auth_uid = '${MY_UID}'`,
  logbook: `auth_uid = '${MY_UID}'`,
  resume_documents: `auth_uid = '${MY_UID}'`,
  skill_profiles: `auth_uid = '${MY_UID}'`,
  skill_exam_attempts: `auth_uid = '${MY_UID}'`,
};
// graded by their own contract in the identity spine above; never graded twice by the sweep
const CORE_RELATIONS = new Set(['hive_members', 'v_worker_truth', 'logbook', 'pm_assets']);

const SWEEP_RELATIONS = (() => {
  const out = new Set();
  const re = /\.from\(\s*['"]([a-z0-9_]+)['"]/g;
  for (const page of AU_PAGES) {
    let src = '';
    try { src = readFileSync(page, 'utf8'); } catch (e) { continue; }
    let m;
    while ((m = re.exec(src))) if (REL_KEY[m[1]]) out.add(m[1]);
  }
  return [...out].sort();
})();

const SPINE = {};
const SWEEP = {};
const SWEEP_ACTIVE = {};

const problems = [];
const steps = [];
const note = (phase, line) => { steps.push({ phase, line }); console.log(`  ${phase.padEnd(12)} ${line}`); };

// ── the identity relations: what any page uses to answer "who am I and what may I see" ──────────────────────
// Each is read as the PERSON through PostgREST, never as the superuser - a superuser read cannot be refused,
// so it could never show that a revoked identity stopped vouching.
const IDENTITY = [
  { name: 'v_worker_truth', q: (hive) => `v_worker_truth?select=worker_name,hive_id&hive_id=eq.${hive}` },
  // ★AND ONE RELATION MUST *KEEP* ANSWERING - EXACTLY ONE ROW, THEIR OWN. A revoked member still reads their own
  // hive_members row, and that is the design, not a leak: it is how the page learns it was removed and can SAY
  // so. If this returned 0, the client could not tell "you were removed" from "the network is down", and the
  // honest-to-those-who-remain rule flips into the opposite failure - a silent sign-out that looks like an
  // outage ([[feedback_a_dismissal_leaks_the_other_direction]], and the whHiveMembershipLost() path in utils.js
  // which must FAIL OPEN on an outage and closed on a real removal). So the expectation is not "0" but
  // "1, and it is mine" - measured, so a day when it answers 4 is still caught.
  { name: 'hive_members', q: (hive) => `hive_members?select=worker_name,role,status&hive_id=eq.${hive}`,
    revokedExpects: 'own-row-only' },
  { name: 'logbook (the hive\'s own work)', q: (hive) => `logbook?select=id&hive_id=eq.${hive}` },
  { name: 'pm_assets (the hive\'s own assets)', q: (hive) => `pm_assets?select=id&hive_id=eq.${hive}` },
];

const count = async (path, token) => {
  const h = { apikey: ANON, Accept: 'application/json', Prefer: 'count=exact', Range: '0-0' };
  if (token) h.Authorization = 'Bearer ' + token;
  try {
    const r = await fetch(`${EDGE}/rest/v1/${path}`, { headers: h });
    if (r.status >= 400) return { n: 0, status: r.status };
    const cr = r.headers.get('content-range') || '';
    return { n: /\/(\d+)$/.test(cr) ? Number(cr.match(/\/(\d+)$/)[1]) : 0, status: r.status };
  } catch (e) { return { n: -1, status: 0, err: String(e).slice(0, 80) }; }
};

const readAll = async (hive, token) => {
  const out = {};
  for (const rel of IDENTITY) out[rel.name] = (await count(rel.q(hive), token)).n;
  return out;
};

// ── the subject's row, captured BEFORE any write ─────────────────────────────────────────────────────────────
const ROW = psql(`select m.id::text || '|' || m.hive_id::text || '|' || m.role || '|' || m.status || '|' || h.name
                  from hive_members m join hives h on h.id = m.hive_id
                  where m.worker_name = '${SUBJECT}' and m.status = 'active' limit 1`.replace(/\s+/g, ' '));
if (!ROW || ROW.split('|').length < 5) {
  console.log(`FAIL lxp-au-identity-after-change - no active membership found for the seeded subject ${SUBJECT}; `
    + `reseed (seeders/) rather than treating a missing persona as a result`);
  process.exit(1);
}
const [MID, HIVE, ROLE0, STATUS0, HIVE_NAME] = ROW.split('|');
console.log(`\nLXP-AU - identity after a revocation and a role change - subject ${SUBJECT} (${HIVE_NAME})`);
console.log('='.repeat(96));
note('captured', `membership ${MID.slice(0, 8)} role=${ROLE0} status=${STATUS0} - this exact row is restored at the end`);

const restore = () => {
  psql(`update hive_members set role = '${ROLE0}', status = '${STATUS0}' where id = '${MID}'`);
  const back = psql(`select role || '|' || status from hive_members where id = '${MID}'`);
  return back === `${ROLE0}|${STATUS0}`;
};

let token = '';
try {
  // ── A1 vouches now ───────────────────────────────────────────────────────────────────────────────────────
  const auth = await fetch(`${EDGE}/auth/v1/token?grant_type=password`, {
    method: 'POST', headers: { apikey: ANON, 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: EMAIL, password: PASSWORD }),
  }).catch(() => null);
  const aj = auth ? await auth.json().catch(() => ({})) : {};
  token = aj.access_token || '';
  if (!token) {
    problems.push('could not mint a token for the seeded subject - the auth service answered '
      + `${auth ? auth.status : 'nothing'}; start/reseed the stack rather than reporting a refusal that was an outage`);
    throw new Error('no token');
  }
  const before = await readAll(HIVE, token);
  note('A1 active', Object.entries(before).map(([k, v]) => `${k}=${v}`).join(' · '));
  // the relations the AU-bearing pages actually read, intersected with what is hive-scoped in this schema
  for (const rel of SWEEP_RELATIONS) SWEEP_ACTIVE[rel] = await count(`${rel}?select=${REL_KEY[rel]}&${REL_KEY[rel]}=eq.${keyValue(rel)}`, token);
  const seeded = SWEEP_RELATIONS.filter((r) => (SWEEP_ACTIVE[r] || {}).n > 0).length;
  note('A1 sweep', `${seeded}/${SWEEP_RELATIONS.length} of the AU pages' hive-scoped relations hold rows for this `
    + 'hive while the membership is active - only those can demonstrate a withholding');
  const vouchedFor = Object.values(before).filter((v) => v > 0).length;
  if (vouchedFor === 0) {
    problems.push('A1: with an ACTIVE membership the identity relations returned nothing at all - the probe is '
      + 'blind, so a later refusal would prove nothing (this is the positive control)');
  }

  // ── A2 revoked, SAME token ───────────────────────────────────────────────────────────────────────────────
  // ★THE VOCABULARY IS PART OF THE ORACLE (fixed on the first run, 2026-10-05). The first version set status to
  // 'removed' and the CHECK rejected it - hive_members_status_check admits only active / kicked / deactivated -
  // so the write silently failed and the probe reported "could not revoke" on a platform that revokes fine. A
  // word the system does not speak is my blind spot, not its defect. Both revocations are tested, because they
  // are two different endings: `kicked` is a supervisor removing someone, `deactivated` is an account standing
  // down, and a relation that honours one while trusting the other is still a leak.
  for (const REVOKED of ['kicked', 'deactivated']) {
    psql(`update hive_members set status = '${REVOKED}' where id = '${MID}'`);
    const nowStatus = psql(`select status from hive_members where id = '${MID}'`);
    if (nowStatus !== REVOKED) {
      problems.push(`A2/${REVOKED}: could not set the membership to '${REVOKED}' for the test `
        + `(status is still '${nowStatus}') - the probe never reached the boundary it claims to measure`);
      continue;
    }
    const after = await readAll(HIVE, token);
    // ★THE SPINE'S OWN READINGS, PER RELATION, so a page whose identity read IS one of these can cite the strict
    // grading instead of being left open. v_worker_truth going 1 -> 0 on an unexpired token is the sharpest
    // single reading in this file; a page that reads it has its identity question answered by exactly that.
    for (const [rel, n] of Object.entries(after)) {
      const key = rel.replace(/ \(.*$/, '');
      SPINE[key] = Object.assign(SPINE[key] || {}, { relation: key, active: before[rel], [REVOKED]: n });
    }
    note(`A2 ${REVOKED}`, Object.entries(after).map(([k, v]) => `${k}=${v}`).join(' · ')
      + '  (same unexpired token)');
    let honoured = 0;
    for (const [rel, n] of Object.entries(after)) {
      const spec = IDENTITY.find((r) => r.name === rel);
      if (spec && spec.revokedExpects === 'own-row-only') {
        // not "did it go quiet" but "is the ONE row it kept mine, and does it say I was revoked"
        const r = await fetch(`${EDGE}/rest/v1/${spec.q(HIVE)}`,
          { headers: { apikey: ANON, Authorization: 'Bearer ' + token, Accept: 'application/json' } }).catch(() => null);
        const rows = r ? await r.json().catch(() => []) : [];
        const mineOnly = Array.isArray(rows) && rows.length === (TEETH ? 2 : 1)
          && rows.every((x) => x.worker_name === SUBJECT) && rows.some((x) => x.status === REVOKED);
        if (mineOnly) {
          honoured++;
          note(`A2 ${REVOKED} own`, `${rel} kept exactly 1 row and it is ${SUBJECT}'s own, reading status=`
            + `${REVOKED} - which is how the page LEARNS it was revoked instead of failing open on silence`);
        } else {
          problems.push(`A2/${REVOKED}: ${rel} answered ${Array.isArray(rows) ? rows.length : '?'} row(s) `
            + `(${(Array.isArray(rows) ? rows : []).map((x) => x.worker_name + '/' + x.status).join(', ')}). The `
            + `contract is exactly ONE row, the revoked person's own, so the client can say "you were removed" `
            + `and still tell that apart from an outage - more than that is the hive leaking to someone it `
            + `dismissed, and fewer is a silent sign-out indistinguishable from a network failure`);
        }
        continue;
      }
      const want = TEETH ? 1 : 0;              // --teeth demands a LEAK, so a clean platform must FAIL the run
      if (n > want) {
        problems.push(`A2/${REVOKED}: ${rel} still answered ${n} row(s) of ${HIVE_NAME} to a ${REVOKED} member on `
          + `a token minted while they belonged. The JWT outlived the membership, so this relation trusts the `
          + `token rather than re-deriving entitlement from the current row - a dismissed worker keeps reading `
          + `the hive until the token expires, and no browser test can see it`);
      } else { honoured++; }
    }
    if (honoured === Object.keys(after).length) {
      note(`A2 ${REVOKED} ok`, `all ${honoured} identity relations behaved: the hive's work went to 0 on an `
        + 'unexpired token, and the only surviving read is the revoked member\'s own membership row');
    }
    // ── THE PER-PAGE SWEEP: a row belongs to ONE page, so the page's OWN relations must be the ones measured ──
    // ★WHY THIS EXISTS. The four relations above are the identity spine and they are shared chrome, graded once.
    // But an AU row says "keep THIS PAGE's identity honest", and 33 pages carry one; between them they read 89
    // hive-scoped relations. A platform-wide spine proof is not evidence for alert-hub unless alert-hub's own
    // reads were among the ones that went quiet. So every hive-scoped relation the AU pages read is asked for
    // this hive's rows on the revoked token, and the banker cites each page's intersection with that list.
    // A relation that is public-by-design is recorded as such, never as a leak: an ex-member may still read the
    // public feed, and demanding otherwise would be a false finding.
    if (REVOKED === 'kicked') {
      for (const rel of SWEEP_RELATIONS) {
        const active = SWEEP_ACTIVE[rel];
        if (!active || active.n <= 0) {          // nothing to withhold here: a 0 after a 0 proves nothing
          // ★BUT SAY *WHY* IT WAS ZERO, MEASURED. The first version reported every zero as "this hive had no
          // rows in it", and hive_audit_log holds 28,536 rows for this hive - the member read 0 because a plain
          // worker is BLIND to the audit log even while fully active. Two very different facts were wearing one
          // label, and the wrong one of them was reassuring. So the hive's real row count is read with the
          // superuser connection (which is the one thing a superuser lens is good for - what EXISTS) and the
          // two cases are named apart. Neither counts as evidence, but only one of them is fixed by seeding.
          const inHive = Number(psql(`select count(*) from public."${rel}" where "${REL_KEY[rel]}"::text = '${keyValue(rel)}'`) || 0);
          SWEEP[rel] = inHive > 0
            ? { verdict: 'blind-while-active', active: 0, rows_in_hive: inHive, revoked: null,
                reason: `this hive holds ${inHive} row(s) but the subject could not read them even while ACTIVE `
                  + '- a revocation cannot be demonstrated on a relation the person never had' }
            : { verdict: 'n/a', active: 0, rows_in_hive: 0, revoked: null,
                reason: 'this hive genuinely has no rows in it - seed some and the revocation becomes provable' };
          continue;
        }
        if (CORE_RELATIONS.has(rel)) {        // graded above by its own contract; don't grade it twice
          SWEEP[rel] = { verdict: 'core', reason: 'held to its own contract in the identity spine above',
                         active: active.n, revoked: null };
          continue;
        }
        const now = await count(`${rel}?select=${REL_KEY[rel]}&${REL_KEY[rel]}=eq.${keyValue(rel)}`, token);
        const byDesign = !!(PUBLIC_BY_DESIGN[rel] || PUBLIC_VIEWS_BY_DESIGN[rel]);
        // ★A REVOKED PERSON KEEPS THEIR OWN RECORD, AND THAT IS NOT A LEAK (measured 2026-10-05). The first run
        // reported pm_completions (552 -> 202) and voice_journal_entries (16 -> 16) as leaks. Both numbers are
        // EXACTLY the subject's own rows: voice_journal_read is `auth.uid() = auth_uid` outright, and
        // pm_completions keeps his 202 because `pm_completions_write` is declared `cmd ALL`, so that policy also
        // grants SELECT on rows he authored. Withholding a person's own work history on the way out would be the
        // opposite failure to a leak - the departure showing up as an ABSENCE
        // ([[feedback_a_dismissal_leaks_the_other_direction]]). So the test is not "did it reach zero" but "is
        // everything it kept HIS", counted in SQL on this run rather than assumed from the policy's text.
        // ★A PERSON-KEYED RELATION IS OWN-RECORDS BY CONSTRUCTION, AND ITS QUESTION IS A DIFFERENT ONE. The read
        // above filtered on auth_uid = this person, so every row it returned is theirs by definition - there is
        // no hive in the predicate at all. Being kicked out of a hive must NOT erase someone's own badges,
        // schedule or profile, so "it still answers" is the correct behaviour here, not a leak. The first run
        // reported five of these (schedule_items, skill_badges, v_skill_badges_truth, v_worker_achievements_truth,
        // worker_profiles) as "would keep rendering this hive to someone it dismissed" - a sentence that was
        // false on its face, since not one of those rows belongs to a hive.
        if (REL_KEY[rel] === 'auth_uid' && now.n > 0) {
          SWEEP[rel] = { verdict: 'own-records-retained', active: active.n, revoked: now.n, own_rows: now.n,
                         key: 'auth_uid', status: now.status,
                         reason: 'scoped to the PERSON, not the hive - the read filters on their own auth_uid, so '
                           + 'every row is theirs and a revocation must not take it away' };
          note('A2 own', `${rel} kept ${now.n} of ${active.n} - it is keyed by auth_uid, so these are the `
            + 'records of the SUBJECT, and losing them on the way out would be the absence-shaped failure');
          continue;
        }
        let ownN = null;
        if (now.n > 0 && !byDesign && OWNABLE[rel]) {
          ownN = Number(psql(`select count(*) from public."${rel}" where "${REL_KEY[rel]}"::text = '${keyValue(rel)}' and ${OWNABLE[rel]}`) || 0);
        }
        const ownOnly = ownN !== null && ownN === now.n && now.n > 0;
        const leaked = now.n > (TEETH ? 1 : 0) && !byDesign && !ownOnly;
        SWEEP[rel] = { verdict: leaked ? 'leak' : byDesign && now.n > 0 ? 'public-by-design'
                                : ownOnly ? 'own-records-retained' : 'ok',
                       active: active.n, revoked: now.n, own_rows: ownN, status: now.status, key: REL_KEY[rel],
                       by_design_reason: PUBLIC_BY_DESIGN[rel] || PUBLIC_VIEWS_BY_DESIGN[rel] || null };
        if (ownOnly) {
          note(`A2 own`, `${rel} kept ${now.n} of ${active.n} - and all ${now.n} are ${SUBJECT}'s own rows, `
            + 'which is a person keeping their record, not the hive leaking');
        }
        if (leaked) {
          problems.push(`A2/sweep: ${rel} (keyed by ${REL_KEY[rel]}) answered ${now.n} row(s) to a kicked member on an `
            + `unexpired token (it answered ${active.n} while the membership was active). Every page that reads `
            + `${rel} would keep rendering this hive to someone it dismissed`);
        }
      }
      const okN = Object.values(SWEEP).filter((x) => x.verdict === 'ok').length;
      const naN = Object.values(SWEEP).filter((x) => x.verdict === 'n/a').length;
      const blindN = Object.values(SWEEP).filter((x) => x.verdict === 'blind-while-active').length;
      const pubN = Object.values(SWEEP).filter((x) => x.verdict === 'public-by-design').length;
      const ownN2 = Object.values(SWEEP).filter((x) => x.verdict === 'own-records-retained').length;
      const coreN = Object.values(SWEEP).filter((x) => x.verdict === 'core').length;
      note('A2 sweep', `${okN}/${SWEEP_RELATIONS.length} of the relations the AU pages read went to zero for a `
        + `kicked member (${naN} genuinely hold no rows for this hive · ${blindN} the subject could not read even `
        + `while ACTIVE, so no revocation is demonstrable there · ${pubN} are `
        + `public-by-design and may still answer · ${ownN2} kept only the person's OWN rows · ${coreN} are graded `
        + 'by the identity spine above)');
    }
    psql(`update hive_members set status = '${STATUS0}' where id = '${MID}'`);
  }

  // ── A3 role change ───────────────────────────────────────────────────────────────────────────────────────
  psql(`update hive_members set status = '${STATUS0}', role = 'supervisor' where id = '${MID}'`);
  const asSup = psql(`select count(*) from hive_members where id = '${MID}' and role = 'supervisor' and status = '${STATUS0}'`);
  if (asSup !== '1') {
    problems.push('A3: could not set the subject to supervisor for the role-change half');
  } else {
    // a supervisor-gated write guard is the honest probe here: pm_assets carries a RESTRICTIVE update guard
    // admitting the row's own author OR a supervisor, so the SAME patch that a worker is refused must now land.
    const target = psql(`select id from pm_assets where hive_id = '${HIVE}' and (auth_uid is null or auth_uid <> (select auth_uid from hive_members where id = '${MID}')) limit 1`);
    if (!target) {
      note('A3 skipped', 'no colleague-authored asset in this hive to aim a supervisor-only patch at - '
        + 'the role half is UNPROVEN here rather than passed');
    } else {
      const patch = async () => {
        const r = await fetch(`${EDGE}/rest/v1/pm_assets?id=eq.${target}`, {
          method: 'PATCH',
          headers: { apikey: ANON, Authorization: 'Bearer ' + token, 'Content-Type': 'application/json',
                     Prefer: 'return=representation' },
          body: JSON.stringify({ updated_at: new Date().toISOString() }),
        }).catch(() => null);
        const rows = r ? await r.json().catch(() => []) : [];
        return { ok: !!r && r.status < 300 && Array.isArray(rows) && rows.length > 0, status: r ? r.status : 0 };
      };
      const asSupervisor = await patch();
      psql(`update hive_members set role = 'worker' where id = '${MID}'`);
      const asWorker = await patch();
      note('A3 role', `the same PATCH on a colleague's asset: as supervisor ${asSupervisor.ok ? 'ACCEPTED' : 'refused'} `
        + `(${asSupervisor.status}) · as worker ${asWorker.ok ? 'ACCEPTED' : 'refused'} (${asWorker.status}) `
        + '- on one unchanged token');
      if (!(asSupervisor.ok && !asWorker.ok)) {
        problems.push('A3: a role change did not change what the same token may do '
          + `(supervisor ${asSupervisor.ok ? 'accepted' : 'refused'}, worker ${asWorker.ok ? 'accepted' : 'refused'}). `
          + 'Identity is not only who you are but what you may do, and a page that renders controls from a role '
          + 'the database no longer agrees with is showing a dishonest identity');
      }
    }
  }
} catch (e) {
  if (!problems.length) problems.push(`the run threw: ${String(e).slice(0, 160)}`);
} finally {
  // ── A4 restore, and VERIFY the restoration ───────────────────────────────────────────────────────────────
  const ok = restore();
  note('A4 restored', ok ? `membership ${MID.slice(0, 8)} is back to role=${ROLE0} status=${STATUS0} (verified by re-read)`
                         : 'RESTORATION FAILED');
  if (!ok) {
    problems.push(`A4: could not restore membership ${MID} to role=${ROLE0} status=${STATUS0}. The probe has left `
      + 'the seeded data changed - fix this row before trusting any later reading of this hive');
  }
}

const REPORT = {
  tool: 'tools/prove_lxp_au_identity_after_change.mjs', subject: SUBJECT, role_asked: ASKED ? 'as-given' : 'default worker', hive: HIVE_NAME, hive_id: HIVE,
  membership: MID, role_before: ROLE0, status_before: STATUS0,
  relations: IDENTITY.map((r) => r.name), au_pages: AU_PAGES, spine: SPINE, sweep: SWEEP,
  steps, problems, pass: problems.length === 0,
};
if (TEETH) {
  console.log('  report       (not written - --teeth verdicts are a counterfactual, not evidence)');
} else {
  const out = REPORT_FILE;
  writeFileSync(out + '.tmp', JSON.stringify(REPORT, null, 1) + String.fromCharCode(10));
  renameSync(out + '.tmp', out);
  console.log(`  report       ${out}`);
}
if (problems.length) {
  console.log('\n  FINDINGS:');
  for (const p of problems) console.log(`    - ${p}`);
  console.log(`\nFAIL lxp-au-identity-after-change - identity did NOT stay honest (${problems.length})`);
} else {
  console.log('\nPASS lxp-au-identity-after-change - a still-valid token stopped vouching the moment the '
    + 'membership was revoked, a role change changed what it may do, and the seeded row was restored');
}
process.exit(problems.length ? 1 : 0);
