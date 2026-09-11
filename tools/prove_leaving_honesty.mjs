// prove_leaving_honesty — W3-LC: "the platform must let a person take their record and go, and must be
// honest to those who remain". Eight pages carry this row. No browser.
//
// ★THE LENS THAT HELD THESE ROWS ASKED ONLY HALF THE CLAIM, AND THE EASY HALF. `prove_lifecycle_cells`
// graded it as "does the word export / download / csv / pdf appear on this page" — which answers "can you
// take it" by looking for a noun, and never touches "and is the platform honest to those who remain."
//
// The claim is a right and a duty, so both are asked:
//
//   TAKE IT   the hive's PDPA Article 16 export really runs, as a real supervisor of that hive, through the
//             function's own front door — and comes back carrying the surfaces this page is about, not an
//             empty envelope. `export-hive-data` is supervisor-only by contract, so a worker asking must be
//             refused: a right that anyone can exercise on anyone's behalf is not a right, it is a leak.
//
//   HONEST    when somebody leaves, what the others still see must not quietly change. This platform
//             attributes work by `worker_name` — a durable string — rather than by a foreign key into
//             membership, so a departed person's entries keep their author. The failure this guards against
//             is the opposite of a leak and just as bad: **the cost of a departure showing up as an
//             ABSENCE**, with yesterday's work suddenly authored by nobody.
//             ([[feedback_a_dismissal_leaks_the_other_direction]] — a departure's trace is a real subject.)
//
//   node tools/prove_leaving_honesty.mjs
//   node tools/prove_leaving_honesty.mjs --self-test
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { execSync } from 'node:child_process';

const EDGE = process.env.WH_EDGE_URL || 'http://127.0.0.1:54321';
const ANON = process.env.WH_ANON_KEY || 'sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ';
const args = process.argv.slice(2);
const MARK = 'take their record and go';

// ★AN EMPTY ANSWER AND A FAILED ASK LOOK IDENTICAL, AND ONLY ONE OF THEM IS A FACT. Returning '' for both
// had this prover announce that Oscar Ramos is a platform admin - because the admin count came back '' from
// a query that never ran, and '' is not '0'. The whole session has been finding this shape; a probe that
// commits it about its own subject cannot be trusted about anything else. `null` means "could not read".
const psql = (sql, tries = 6) => {
  for (let i = 0; i < tries; i++) {
    try {
      return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`,
        { encoding: 'utf8', timeout: 40000, killSignal: 'SIGKILL' }).trim();
    } catch { try { execSync('powershell -NoProfile -Command "Start-Sleep -Milliseconds 2500"', { stdio: 'ignore', timeout: 8000 }); } catch { /* even the wait may be refused */ } }
  }
  return null;
};

// a supervisor who is NOT a platform admin - an admin exercising a right proves nothing about the right
// and whose hive HOLDS a plain worker - the refusal half needs somebody who must be told no, and the
// first supervisor the database happened to name led a hive of supervisors only
const SUP = psql(`select m.worker_name from hive_members m where m.status='active' and m.role='supervisor' and not exists (select 1 from marketplace_platform_admins a where a.worker_name = m.worker_name) and exists (select 1 from hive_members w where w.hive_id = m.hive_id and w.status='active' and w.role <> 'supervisor') and exists (select 1 from auth.users u where u.id = m.auth_uid) limit 1`);
// ★A CHAINED LOOKUP MUST STOP AT THE FIRST EMPTY ANSWER. When the database is busy the first query returns
// '', and every query built from it then asks about `worker_name = ''` and `hive_id = ''` — so the run
// prints a wall of SQL type errors that look like a broken schema and are really one busy moment. Ask once
// whether the ground is there before standing on it.
const HIVE = SUP ? psql(`select hive_id::text from hive_members where worker_name = '${SUP}' and status='active' limit 1`) : '';
const SUP_EMAIL = SUP ? psql(`select u.email from auth.users u join hive_members m on m.auth_uid=u.id where m.worker_name='${SUP}' limit 1`) : '';
// a plain worker of the SAME hive, to prove the right is not handed to anyone who asks
// ★AND THE PERSON WHO MUST BE REFUSED CANNOT BE AN ADMIN EITHER. The first pick was Pablo Aguilar, who
// is in marketplace_platform_admins - if the export had let him through, that would be the product
// working, and the refusal half would have proved nothing while looking like it had.
const WORKER = HIVE ? psql(`select m.worker_name from hive_members m where m.hive_id='${HIVE}' and m.status='active' and m.role <> 'supervisor' and not exists (select 1 from marketplace_platform_admins a where a.worker_name = m.worker_name) and exists (select 1 from auth.users u where u.id = m.auth_uid) limit 1`) : '';
const WORKER_EMAIL = WORKER ? psql(`select u.email from auth.users u join hive_members m on m.auth_uid=u.id where m.worker_name='${WORKER}' limit 1`) : '';
// somebody who has actually LEFT this platform, if the seed holds one
const GONE = psql(`select worker_name from hive_members where status <> 'active' limit 1`);

// Which surface each page is about — the table whose rows a departed person would have authored.
// ★READ FROM THE PAGE, NOT FROM WHAT THE PAGE SOUNDS LIKE. The first version of this map was written from
// the page names and got three of eight wrong: achievements does not read `community_posts` (it reads
// `achievement_xp_log`), resume does not read the logbook (it reads `resume_documents`), and the seller
// profile answers from `marketplace_reviews` and its public listing views. Checking a page's honesty
// against a table it never opens is a green about nothing.
const SURFACE = {
  'hive.html': 'logbook',
  'audit-log.html': 'hive_audit_log',
  'logbook.html': 'logbook',
  'community.html': 'community_posts',
  'public-feed.html': 'community_posts',              // read through v_community_posts_truth
  'achievements.html': 'achievement_xp_log',
  'resume.html': 'resume_documents',
  'marketplace-seller-profile.html': 'marketplace_listings',
};

const rows = JSON.parse(readFileSync('trajectory_registry.json', 'utf8')).trajectories
  .filter((t) => (t.title || '').includes(MARK))
  .map((t) => ({ id: t.id, page: (t.pages || [])[0] }))
  .filter((r) => r.page);

async function tokenFor(email) {
  for (let i = 0; i < 5; i++) {
    const r = await fetch(`${EDGE}/auth/v1/token?grant_type=password`, {
      method: 'POST', headers: { apikey: ANON, 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password: 'test1234' }),
    }).catch(() => null);
    const j = r ? await r.json().catch(() => ({})) : {};
    if (j.access_token) return j.access_token;
    await new Promise((res) => setTimeout(res, 6000));
  }
  return null;
}

async function exportAs(tok) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), 120000);   // a bulk export is allowed to take its time
  try {
    const r = await fetch(`${EDGE}/functions/v1/export-hive-data`, {
      method: 'POST',
      headers: { apikey: ANON, Authorization: 'Bearer ' + tok, 'Content-Type': 'application/json' },
      body: JSON.stringify({ hive_id: HIVE, hiveId: HIVE }), signal: ctl.signal,
    });
    const text = await r.text();
    let json = null; try { json = JSON.parse(text); } catch { /* not JSON is itself the finding */ }
    return { status: r.status, ok: r.ok, json, text };
  } catch (e) { return { status: 0, ok: false, json: null, text: String(e.message || e) }; }
  finally { clearTimeout(t); }
}

if (args.includes('--self-test')) {
  const fails = [];
  if (!SUP) fails.push('the database did not name a non-admin supervisor - either none exists or it was too busy to answer; nothing is claimed either way');
  if (!/^[0-9a-f-]{36}$/.test(HIVE)) fails.push(`the supervisor's hive did not resolve (${HIVE || 'empty'})`);
  if (!SUP_EMAIL) fails.push('that supervisor has no sign-in of their own');
  if (!WORKER) fails.push('no plain worker in that hive, so "supervisor-only" cannot be shown to bite');
  const adminCount = psql(`select count(*) from marketplace_platform_admins where worker_name = '${SUP}'`);
  if (adminCount === null) fails.push('the admin check could not be read, so it is not known whether this persona is an admin');
  else if (adminCount !== '0') fails.push(`${SUP} is a platform admin - an admin can do anything, which proves nothing about a right`);
  // ★THE SURFACE MUST EXIST, CARRY A HIVE, AND NAME ITS AUTHOR - or the check it feeds is decorative. A
  // table that has no author column would be reported as "records no author by name", which is a finding
  // about the schema; a table that does not exist at all is a finding about THIS MAP, and the two must not
  // be allowed to look alike.
  for (const t of [...new Set(Object.values(SURFACE))]) {
    const exists = psql(`select count(*) from information_schema.tables where table_schema='public' and table_name='${t}'`);
    if (exists === null) { fails.push(`could not read whether ${t} exists`); continue; }
    if (exists !== '1') {
      fails.push(`the surface table ${t} does not exist - this prover's page-to-table map is wrong, not the schema`);
      continue;
    }
    // ★NOT EVERY SURFACE BELONGS TO A HIVE, AND THAT IS NOT A DEFECT. `achievements.html` reads four tables
    // and none carries `hive_id`: it is a PERSON-scoped page, showing one worker's record across the whole
    // platform. Demanding a hive column of it would have reported a correctly-designed page as broken. The
    // honesty question is the same either way - does the work keep its author when its author leaves - only
    // the scope of the question changes.
    const scoped = psql(`select count(*) from information_schema.columns where table_schema='public' and table_name='${t}' and column_name='hive_id'`) === '1';
    if (!scoped) console.log(`  note: ${t} is person-scoped (no hive_id) - asked across the platform, not within one hive`);
  }
  // and the pages must really read the surface they are mapped to
  for (const [page, table] of Object.entries(SURFACE)) {
    let src = '';
    try { src = readFileSync(page, 'utf8'); } catch { fails.push(`${page} could not be read`); continue; }
    const stem = table.replace(/^v_/, '').replace(/_truth$/, '').split('_')[0];
    if (!new RegExp(`\\.from\\(\\s*['"\`][a-z0-9_]*${stem}`, 'i').test(src)) {
      fails.push(`${page} never reads anything resembling ${table} - the map points at a table this page does not open`);
    }
  }
  console.log(fails.length ? 'FAIL leaving-honesty self-test - ' + fails.join('; ')
    : `self-test OK: ${SUP} (supervisor, not an admin) of ${HIVE.slice(0, 8)}, ${WORKER} as the worker who must be refused, `
      + `${GONE ? `${GONE} has left` : 'nobody has left yet'}; ${rows.length} row(s) to answer`);
  process.exit(fails.length ? 1 : 0);
}

const supTok = await tokenFor(SUP_EMAIL);
if (!supTok) { console.log(`FAIL leaving-honesty - could not sign in as ${SUP}`); process.exit(1); }
const workerTok = WORKER_EMAIL ? await tokenFor(WORKER_EMAIL) : null;

// ── the right, exercised once for the whole hive ──────────────────────────────────────────────────
const exported = await exportAs(supTok);
const payload = exported.json && (exported.json.export || exported.json.data || exported.json);
const carried = payload && typeof payload === 'object'
  ? Object.fromEntries(Object.entries(payload).map(([k, v]) => [k, Array.isArray(v) ? v.length : (v ? 1 : 0)]))
  : {};
console.log(`export as ${SUP}: ${exported.status}${exported.ok ? '' : ' — ' + exported.text.slice(0, 80)}`);
if (exported.ok) console.log(`  carries: ${Object.entries(carried).filter(([, n]) => n).map(([k, n]) => `${k}=${n}`).slice(0, 10).join(' ')}`);

// ★AND THE RIGHT MUST NOT BE HANDED TO ANYONE WHO ASKS. Supervisor-only is the contract; a worker getting
// the whole hive's export would be the leak this right is supposed to be bounded by.
let workerRefused = null;
if (workerTok) {
  const w = await exportAs(workerTok);
  workerRefused = (w.status === 401 || w.status === 403);
  console.log(`export as ${WORKER} (plain worker): ${w.status} — ${workerRefused ? 'refused, as the contract says' : 'NOT refused'}`);
}

const results = [];
let bad = 0, unread = 0;
for (const r of rows) {
  const table = SURFACE[r.page];
  let rec;
  if (!table) {
    rec = { verdict: 'n/a', line: `no surface is named for ${r.page}, so nothing was claimed` };
  } else if (/name resolution failed|ECONNREFUSED|fetch failed/i.test(exported.text) || exported.status === 0) {
    // *A DEAD RUNTIME IS NOT A PLATFORM THAT CANNOT EXPORT. This host OOM-killed the edge runtime twice
    // today, and both times every function answered 503 "name resolution failed". Reporting that as "the
    // supervisor could not take the record" would file eight findings against the product for a container
    // that is not running - and 8 of 8 is the shape of a probe, never of a defect.
    rec = { verdict: 'n/a', line: `the edge runtime did not answer (${exported.status}) - start supabase_edge_runtime_workhive and re-ask; nothing is claimed` };
  } else if (!exported.ok) {
    rec = { verdict: 'BAD', line: `the hive's own supervisor could not take the record: export answered ${exported.status} "${exported.text.slice(0, 54)}"` };
  } else if (workerRefused === false) {
    rec = { verdict: 'BAD', line: 'a plain worker was handed the whole hive\'s export - the right is not bounded to the person who holds it' };
  } else {
    // HONEST: does this surface still carry its authors by name, so a departure cannot erase yesterday?
    // The audit log calls its author `actor`, and a list that knew only `worker_name` reported the
    // platform's own audit trail as recording nobody - a finding about this list's vocabulary,
    // stated as a finding about the schema.
    // ★ASK FOR THE COLUMN THIS TABLE ACTUALLY HAS. Counting the candidates and then querying `worker_name`
    // on all of them would error on every table that names its author differently — and an errored query
    // returns empty, which reads exactly like "no orphans". A silent error that looks like a pass is the
    // worst shape a check can take.
    const named = psql(`select column_name from information_schema.columns where table_schema='public' and table_name='${table}' and column_name in ('worker_name','author_name','seller_name','created_by','actor','actor_name','performed_by','user_name','submitted_by') order by case column_name when 'worker_name' then 1 when 'author_name' then 2 when 'actor' then 3 when 'actor_name' then 4 when 'seller_name' then 5 else 6 end limit 1`);
    const hiveScoped = psql(`select count(*) from information_schema.columns where table_schema='public' and table_name='${table}' and column_name='hive_id'`) === '1';
    const where = hiveScoped ? `t.hive_id='${HIVE}' and ` : '';
    const orphan = !named ? null
      : psql(`select count(*) from ${table} t where ${where}coalesce(t.${named}::text,'') = ''`);
    const inExport = Object.entries(carried).find(([k]) => k.includes(table.split('_')[0]));
    if (!named) {
      rec = { verdict: 'BAD', line: `${table} records no author by name, so a person leaving takes the attribution of their work with them` };
    } else if (orphan && orphan !== '0') {
      rec = { verdict: 'BAD', line: `${table} holds ${orphan} row(s) in this hive with no author named - work that already belongs to nobody` };
    } else {
      rec = { verdict: 'ok',
              line: `the supervisor can take the record (${exported.status}${inExport ? `, ${inExport[0]}=${inExport[1]}` : ''}), a plain worker is refused, `
                    + `and ${table} names its author durably - so a departure leaves the others' view intact` };
    }
  }
  if (rec.verdict === 'BAD') bad++;
  if (rec.verdict === 'n/a') unread++;
  results.push({ ...r, ...rec });
  console.log(`  ${rec.verdict === 'ok' ? 'ok ' : rec.verdict === 'n/a' ? 'n/a' : 'BAD'} ${r.id.padEnd(8)} ${r.page.padEnd(32)} ${rec.line.slice(0, 92)}`);
}
mkdirSync('.tmp', { recursive: true });
writeFileSync('.tmp/leaving_honesty.json', JSON.stringify({ supervisor: SUP, hive: HIVE, export: exported.status, workerRefused, walked: results.length, bad, results }, null, 1));
console.log(`${bad ? 'FAIL' : 'PASS'} leaving-honesty - ${results.length - bad - unread}/${results.length} let a person go without rewriting what the others see, ${unread} unanswerable  ·  .tmp/leaving_honesty.json`);
process.exit(bad ? 1 : 0);
