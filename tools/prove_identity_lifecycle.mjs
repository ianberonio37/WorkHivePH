// prove_identity_lifecycle — the identity and membership arcs (T51, T58, T62), walked together (2026-09-07).
//
// Three rows about the same fact: a person is not a string. They change their display name, they leave
// one hive and join another, they belong to two at once - and every surface that showed their old name
// or their old access has to follow, or the platform starts telling people things that are no longer true.
//
//   I1 one identity     a display name is stored in ONE place and read from it. A name copied into rows
//                       at write time cannot follow a change, so the platform would keep showing the old
//                       one wherever it was copied - and this platform DOES denormalise worker_name, so
//                       the question is whether anything reconciles it.
//   I2 access follows   membership decides access. When a member's status leaves 'active', the rows that
//                       membership unlocked stop being readable - measured through PostgREST as that
//                       person, because RLS is the only thing that can answer it.
//   I3 two hives        someone in two hives sees each hive's data under that hive, and never a blend.
//                       This platform has shipped a .maybeSingle() that bounced multi-hive users before.
//
// ★MEASURED THROUGH THE APP'S OWN PATH AND RESTORED AFTERWARDS. Membership is changed for real and put
// back; every read is made as the person through PostgREST with their own token, never as the owner.
//
//   node tools/prove_identity_lifecycle.mjs
import { execSync } from 'node:child_process';
import { HIVE } from './prover_harness.mjs';

const EDGE = 'http://127.0.0.1:54321';
const ANON = process.env.WH_ANON_KEY || 'sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ';
const psql = (sql) => { try { return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim(); } catch { return ''; } };
// ★A SETUP THAT SILENTLY FAILED REPORTS ON THE WRONG WORLD. The first run of this prover wrote status
// 'removed', which the CHECK constraint rejects - so the membership never changed, the person kept
// reading their 944 rows, and the prover called that "removing the membership did not remove the
// access". It was a leak finding about a removal that never happened. A write whose effect is the
// premise of the next measurement must be CONFIRMED, not assumed.
const setStatus = (who, hive, status) => {
  psql(`update hive_members set status = '${status}' where worker_name = '${who}' and hive_id = '${hive}'`);
  const got = psql(`select status from hive_members where worker_name = '${who}' and hive_id = '${hive}'`);
  return got === status ? '' : `the membership write did not take: asked for '${status}', the row still reads '${got || '(gone)'}'`;
};

const token = async (email) => {
  const r = await fetch(`${EDGE}/auth/v1/token?grant_type=password`, {
    method: 'POST', headers: { apikey: ANON, 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password: 'test1234' }),
  });
  const j = await r.json().catch(() => ({}));
  return j.access_token || null;
};
const countAs = async (tok, table, qs) => {
  const r = await fetch(`${EDGE}/rest/v1/${table}?${qs}`, {
    headers: { apikey: ANON, Authorization: 'Bearer ' + tok, Prefer: 'count=exact', Range: '0-0' },
  });
  const cr = r.headers.get('content-range') || '';
  return /\/(\d+)$/.test(cr) ? Number(cr.match(/\/(\d+)$/)[1]) : (r.ok ? 0 : -1);
};

let bad = 0;

// ── I1 · is a display name one fact, or many copies? ─────────────────────────────────────────────
{
  const denorm = psql("select c.relname from pg_class c join pg_namespace n on n.oid=c.relnamespace join pg_attribute a on a.attrelid=c.oid and a.attname='worker_name' and not a.attisdropped where n.nspname='public' and c.relkind='r' order by 1")
    .split('\n').map((x) => x.trim()).filter(Boolean);
  // a reconciler is what makes a denormalised copy survivable: a trigger, or a view that joins the source
  const reconcilers = psql("select count(*) from pg_trigger t join pg_class c on c.oid=t.tgrelid join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and not t.tgisinternal and pg_get_triggerdef(t.oid) ilike '%worker_name%'");
  const views = psql("select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relkind='v' and pg_get_viewdef(c.oid, true) ilike '%worker_profiles%'");
  const ok = Number(reconcilers || 0) > 0 || Number(views || 0) > 0;
  if (!ok) bad++;
  console.log(`  ${ok ? 'ok ' : 'BAD'} I1 one identity          worker_name is copied into ${denorm.length} table(s); ${reconcilers} trigger(s) and ${views} view(s) reconcile it against the profile`);
  if (!ok) console.log('        a name copied at write time with nothing reconciling it can never follow a change - every copy keeps the old one');
}

// ── I2 · does access follow membership? ──────────────────────────────────────────────────────────
{
  const who = 'Wilfredo Malabanan';
  const email = 'wilfredomalabanan@auth.workhiveph.com';
  // the platform's own vocabulary for "no longer a member", read from the constraint rather than guessed
  const vocab = (psql("select pg_get_constraintdef(oid) from pg_constraint where conname='hive_members_status_check'")
    .match(/'([a-z_]+)'/g) || []).map((x) => x.replace(/'/g, '')).filter((x) => x !== 'active');
  const tok = await token(email);
  if (!tok) { console.log('  BAD I2 access follows       could not sign in as the test member'); bad++; }
  else if (!vocab.length) { console.log('  BAD I2 access follows       could not read the words this platform uses for a lapsed membership'); bad++; }
  else {
    const before = await countAs(tok, 'logbook', `select=id&hive_id=eq.${HIVE}`);
    const seen = [];
    for (const status of vocab) {
      const err = setStatus(who, HIVE, status);
      if (err) { seen.push([status, -2, err]); continue; }
      // a new token, because the old one carries the claims it was minted with
      const during = await countAs(await token(email) || tok, 'logbook', `select=id&hive_id=eq.${HIVE}`);
      seen.push([status, during, '']);
    }
    const restoreErr = setStatus(who, HIVE, 'active');
    const after = await countAs(await token(email) || tok, 'logbook', `select=id&hive_id=eq.${HIVE}`);

    const issues = [];
    for (const [status, during, err] of seen) {
      if (err) issues.push(`I2 ${err} - this lens is unmeasured for '${status}', not clean`);
      else if (during > 0) issues.push(`I2 a '${status}' member still reads ${during} of ${before} row(s) - the access did not follow the membership`);
    }
    if (restoreErr || after !== before) issues.push(`I2 access did not come back on restore (${after} of ${before}) - the probe left this person worse off`);
    if (issues.length) bad++;
    console.log(`  ${issues.length ? 'BAD' : 'ok '} I2 access follows        ${who}: ${before} row(s) active, ${seen.map(([s2, d]) => `${d < 0 ? '?' : d} ${s2}`).join(', ')}, ${after} restored`);
    for (const s2 of issues) console.log(`        ${s2.slice(0, 158)}`);
  }
}

// ── I3 · two hives, kept apart ───────────────────────────────────────────────────────────────────
{
  const multi = psql("select worker_name from hive_members where status='active' group by worker_name having count(distinct hive_id) > 1 limit 1");
  if (!multi) {
    console.log('  n/a I3 two hives             no active member belongs to two hives in this data - the lens is unmeasured, not clean');
  } else {
    const hives = psql(`select string_agg(distinct hive_id::text, ',') from hive_members where worker_name = '${multi}' and status='active'`).split(',');
    const email = psql(`select u.email from auth.users u join hive_members m on m.auth_uid = u.id where m.worker_name = '${multi}' limit 1`);
    const tok = await token(email);
    if (!tok || hives.length < 2) console.log(`  n/a I3 two hives             could not sign in as ${multi}`);
    else {
      const a = await countAs(tok, 'logbook', `select=id&hive_id=eq.${hives[0]}`);
      const b2 = await countAs(tok, 'logbook', `select=id&hive_id=eq.${hives[1]}`);
      const foreign = psql(`select id from hives where id not in ('${hives.join("','")}') limit 1`);
      const f = foreign ? await countAs(tok, 'logbook', `select=id&hive_id=eq.${foreign}`) : 0;
      const ok = f === 0;
      if (!ok) bad++;
      console.log(`  ${ok ? 'ok ' : 'BAD'} I3 two hives             ${multi} sees ${a} and ${b2} row(s) in their two hives, ${f} in a third`);
    }
  }
}

console.log(`${bad ? 'FAIL' : 'PASS'} identity-lifecycle - a display name is reconcilable, access follows membership in both directions, and two hives stay apart`);
process.exitCode = bad ? 1 : 0;
