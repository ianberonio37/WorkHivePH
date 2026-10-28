// prove_tenant_refusal — the CROSS-HIVE REFUSAL family of the live-walk wave (2026-09-06).
//
// tools/live_walk_manifest.py --family "tenant & authz" listed 34 rows whose lens is `cross-hive read refusal` (20),
// `write-authz depth` (13) and the BOLA/forged-hive_id one-offs. Every one asks the SAME question - "can a signed-in
// member of hive A obtain a row belonging to hive B?" - and none of them can be answered by the postgres MCP.
//
// ★WHY NOT THE POSTGRES MCP (measured 2026-09-06, the calibration that produced this file). The MCP connects as
// `postgres`, which OWNS every public table and carries rolbypassrls - so RLS is never consulted and the read
// answers 944 foreign logbook rows. Worse, it cannot be talked out of it: `set_config('role','authenticated')`
// inside the statement arrives AFTER the plan is built (RLS is a plan-time decision), and set at session level it
// is rolled back, because the server wraps every query in a read-only transaction. A superuser lens can prove what
// data EXISTS; it can never prove that a read was REFUSED. That needs a non-owner role, which is what this file uses.
//
// Two instruments, both the real path:
//   the app's own path  PostgREST at /rest/v1 with a REAL user access token minted from the local auth server -
//                       so a pass covers the GRANTs and the policy together, exactly as the browser meets them
//   the anon path       the same request carrying only the publishable key
//
// ★A REFUSAL OVER AN EMPTY TABLE PROVES NOTHING. For each table the foreign hive's rows are counted as superuser
// FIRST; a table where the foreign hive has no rows is reported `n/a`, never `ok`. A negative control runs beside
// it: the same member asks for their OWN hive's rows and must SEE them, so a probe that is simply broken (bad
// token, wrong header, PostgREST down) shows up as a failure of the control rather than a clean sweep of refusals.
//
//   node tools/prove_tenant_refusal.mjs              # every hive_id table that has foreign rows to hide
//   node tools/prove_tenant_refusal.mjs --table logbook
import { execSync } from 'node:child_process';
import { writeFileSync, renameSync } from 'node:fs';
import { HIVE, WORKER } from './prover_harness.mjs';
// ★THE BY-DESIGN EXCEPTIONS LIVE IN ONE MODULE, shared with prove_lxp_au_identity_after_change, so the two
// provers cannot drift into agreeing on a stale fact. The comments explaining each entry travel with it.
import { PUBLIC_BY_DESIGN, BLIND_BY_DESIGN, PUBLIC_VIEWS_BY_DESIGN, SUBSET_ORACLES } from './tenant_declarations.mjs';

// ★THE HARNESS PERSONA IS A PLATFORM ADMIN, SO IT CANNOT DEMONSTRATE A REFUSAL (measured 2026-09-06).
// The first clean run reported seven tenant tables leaking to a signed-in member - analytics_events (764 foreign
// rows), marketplace_orders, marketplace_inquiries, marketplace_listings, marketplace_sellers, community_posts,
// service_providers. Every one of those policies has an admin arm (`is_marketplace_admin()`, or an EXISTS over
// marketplace_platform_admins), and `marketplace_platform_admins` holds exactly two names: Pablo Aguilar and
// LEANDRO MARQUEZ - the harness's default WORKER, the persona nearly every prover in tools/ signs in as. An admin
// reading everything is the product working. The authz lenses must act as an ORDINARY member, so this prover
// defaults to a plain worker of the same hive and refuses to run as anyone listed in marketplace_platform_admins.
const PLAIN = { name: 'Wilfredo Malabanan', email: 'wilfredomalabanan@auth.workhiveph.com', password: 'test1234', role: 'worker', hiveName: 'Baguio' };
const ASKED = (() => { const i = process.argv.indexOf('--as'); return i >= 0 ? process.argv[i + 1] : null; })();
// ★THE LOGIN IS NOT ALWAYS THE NAME (2026-10-08). `--as` derived the account from the display name, which holds for
// most seeded members and not for the solo owner (Jun Salvador signs in as junvanowner) or the fleet accounts -
// record_mcp_walk.py's header names the same trap. `--email <local part or address>` states the login outright.
const ASK_EMAIL = (() => { const i = process.argv.indexOf('--email'); return i >= 0 ? process.argv[i + 1] : null; })();
// ★`--email` QUALIFIES `--as`, IT DOES NOT REPLACE IT (2026-10-28). Asked alone, it fell through to the default actor
// and the run wrote the plain member's reading over tenant_refusal_report.json - three "persona" runs that were all
// Wilfredo Malabanan, each reporting PASS. A flag that is silently ignored is refused instead.
if (ASK_EMAIL && !process.argv.includes('--as')) {
  console.log('FAIL tenant-refusal - --email needs --as "<display name>" (the name is the actor; the email is his login)');
  process.exit(1);
}
const ADMIN_MODE = process.argv.includes('--as-admin');
// --teeth drops the by-design exemptions: the run MUST fail, proving the gate can still see a cross-hive read.
const TEETH = process.argv.includes('--teeth');

const EDGE = 'http://127.0.0.1:54321';
const ANON = process.env.WH_ANON_KEY || 'sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ';
const ONLY = (() => { const i = process.argv.indexOf('--table'); return i >= 0 ? process.argv[i + 1] : null; })();

const psql = (sql) => { try { return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim(); } catch { return ''; } };
// SQL on stdin, for a statement whose literal carries double quotes (a row as JSON) - no shell quoting to survive
const psqlIn = (sql) => { try { return execSync('docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA', { input: sql, encoding: 'utf8' }).trim(); } catch { return ''; } };

const ACTOR = ADMIN_MODE ? WORKER : (ASKED ? { name: ASKED, email: ASK_EMAIL ? (ASK_EMAIL.includes('@') ? ASK_EMAIL : ASK_EMAIL + '@auth.workhiveph.com') : ASKED.toLowerCase().replace(/[^a-z]/g, '') + '@auth.workhiveph.com', password: 'test1234', hiveName: 'Baguio' } : PLAIN);
// ★THE ACTOR'S OWN HIVES ARE READ, NOT ASSUMED (2026-10-08). "Foreign" was "every hive but Baguio", which is true for
// the default plain member and FALSE for a person in several hives: Christine Dizon supervises Baguio AND Lucena and
// works in Manila, so asked as her, the busiest "foreign" hive could be one she legitimately reads - and her entitled
// read would have been filed as a LEAK. A person with NO active membership (the solo owner) has no own hive at all,
// so every hive is foreign to her and the own-hive control has nothing to stand on; a SOLO run controls on the
// person's own hive-less rows instead (below). For the default actor all of this resolves to exactly what it was.
const ACTOR_UID = psql(`select id::text from auth.users where lower(email) = lower('${ACTOR.email}') limit 1`);
const ACTOR_HIVES = psql(`select hive_id::text from hive_members where auth_uid::text = '${ACTOR_UID}' and status = 'active' and hive_id is not null`)
  .split(String.fromCharCode(10)).map((x) => x.trim()).filter((x) => /^[0-9a-f-]{36}$/.test(x));
const SOLO = !ADMIN_MODE && ACTOR_UID !== '' && ACTOR_HIVES.length === 0;
const MY_HIVE = (ACTOR_HIVES.includes(HIVE) || !ACTOR_HIVES.length) ? HIVE : ACTOR_HIVES[0];
const MY_HIVE_NAME = SOLO ? 'no hive - a solo owner' : psql(`select name from hives where id = '${MY_HIVE}'`);
const ACTOR_ROLE = SOLO ? 'solo' : (psql(`select role from hive_members where auth_uid::text = '${ACTOR_UID}' and hive_id = '${MY_HIVE}' and status = 'active' limit 1`) || 'member');
const NOT_MINE = (ACTOR_HIVES.length ? ACTOR_HIVES : (SOLO ? [] : [HIVE])).map((h) => `'${h}'`).join(',');

// the hive our member does NOT belong to, chosen as the one with the most rows to hide
const FOREIGN = psql(`select h.id from hives h ${NOT_MINE ? `where h.id::text not in (${NOT_MINE})` : ''} order by (select count(*) from logbook l where l.hive_id = h.id) desc limit 1`);
const FOREIGN_NAME = psql(`select name from hives where id = '${FOREIGN}'`);

const TABLE_SQL = "select c.relname from pg_class c join pg_namespace n on n.oid=c.relnamespace join pg_attribute a on a.attrelid=c.oid and a.attname='hive_id' and not a.attisdropped where n.nspname='public' and c.relkind='r' order by c.relname";
const TABLES = psql(TABLE_SQL).split(String.fromCharCode(10)).map((t) => t.trim())
  .filter(Boolean)
  .filter((t) => /^[a-z0-9_]+$/.test(t))   // a psql error line is not a table name
  .filter((t) => !ONLY || t === ONLY);

const isAdmin = psql(`select count(*) from marketplace_platform_admins where worker_name = '${ACTOR.name}'`) !== '0';
if (isAdmin && !ADMIN_MODE) { console.log(`FAIL tenant-refusal - ${ACTOR.name} is a marketplace platform admin; an admin cannot demonstrate a refusal. Pick a plain member, or pass --as-admin to assert the admin path deliberately.`); process.exit(1); }

const token = await (async () => {
  const r = await fetch(`${EDGE}/auth/v1/token?grant_type=password`, {
    method: 'POST', headers: { apikey: ANON, 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: ACTOR.email, password: ACTOR.password }) });
  const j = await r.json().catch(() => ({}));
  return j.access_token || null;
})();
if (!token) { console.log('FAIL tenant-refusal - could not mint a user token; the probe cannot speak for a signed-in person'); process.exit(1); }

// ★WHAT IS DELIBERATELY CROSS-HIVE, AND WHY (each verified against the table's own SELECT policy, 2026-09-06).
// A gate that fails the marketplace for being a marketplace teaches nothing. These four are the product; every
// OTHER tenant table must refuse, and a new one that does not will fail here.
// ★A PLAIN WORKER IS SUPPOSED TO BE BLIND TO THESE, so a BLIND control is the product, not a broken probe.
// ★THE VIEWS OVER A PUBLIC-BY-DESIGN TABLE, AND WHY EACH ENTRY QUOTES ARITHMETIC RATHER THAN A NAME (2026-10-05).
// The view loop below found seven surfaces handing a foreign hive's rows to a plain member. Every one is a view
// over a table ALREADY declared public-by-design above - the cross-hive bazaar this product is - but "its name
// ends in _public" is not evidence. So each entry records the subset the view was MEASURED to expose against
// the subset its base policy intends, and they matched to the row: posts 8 of 50 foreign (= exactly the 8 that
// are public AND NOT flagged), listings 7 of 9 (= exactly the 7 `published`), anon sellers 5 of 6 (= only those
// with a published listing). A view that ever shows MORE than its base policy's subset breaks this declaration
// and surfaces as a LEAK, which is the whole point of writing the arithmetic down instead of the name.
// ★AND A DECLARATION IS NOT A MEASUREMENT. The entries below each quote arithmetic, but quoting it in a comment
// is a DESCRIBED mechanism, not a mechanism: nothing re-checks it on the next run, so the day a policy widens,
// the declaration keeps vouching for the old number. These oracles compute the intended subset in SQL and
// ASSERT the member's reading equals it, so "public by design" stays a measured invariant. A public surface's
// boundary is not the hive - it is the PUBLISHED SUBSET - and that is exactly what a public feed's row asks.

const ask = async (table, hive, auth, keycol) => {
  const KC = keycol || 'hive_id';
  const h = { apikey: ANON, Accept: 'application/json', Prefer: 'count=exact', Range: '0-0' };
  if (auth) h.Authorization = 'Bearer ' + token;
  try {
    const r = await fetch(`${EDGE}/rest/v1/${table}?select=${KC}&${KC}=eq.${hive}`, { headers: h });
    const cr = r.headers.get('content-range') || '';
    const total = /\/(\d+)$/.test(cr) ? Number(cr.match(/\/(\d+)$/)[1]) : null;
    if (r.status >= 400) return { status: r.status, n: 0, refused: true };
    return { status: r.status, n: total ?? 0, refused: false };
  } catch (e) { return { status: 0, n: -1, err: String(e).slice(0, 60) }; }
};

console.log(`  acting as ${ACTOR.name} (${ASKED ? MY_HIVE_NAME + ', ' + ACTOR_ROLE : ACTOR.hiveName}${ADMIN_MODE ? ', PLATFORM ADMIN - asserting the admin path' : (ASKED ? '' : ', plain member')}) · foreign hive: ${FOREIGN_NAME} ${FOREIGN.slice(0, 8)}`);
if (!FOREIGN) { console.log('FAIL tenant-refusal - no hive is foreign to this actor; there is nothing to refuse'); process.exit(1); }
let leaks = 0, tested = 0, na = 0, ctlBroken = 0;
// ★A REPORT IS WHAT LETS A ROW CITE ITS OWN TABLES (added 2026-10-05). The per-table verdicts only ever
// reached stdout, so a trajectory row for ONE page could not say which of the tables IT reads were proven to
// refuse - and a banker with no per-table facts can only blanket-stamp, which is how a page whose tables were
// all `n/a` ("nothing to hide") would close on someone else's evidence. The report carries the same verdicts
// the console prints, per table, so a row's basis names the tables that page actually reads.
const REPORT = { tool: 'tools/prove_tenant_refusal.mjs', actor: ACTOR.name,
                 actor_hive: ASKED ? MY_HIVE_NAME : ACTOR.hiveName, actor_role: ADMIN_MODE ? 'platform-admin' : (ASKED ? ACTOR_ROLE : 'worker'),
                 actor_hives: ACTOR_HIVES.length, solo: SOLO,
                 foreign_hive: FOREIGN_NAME, foreign_hive_id: FOREIGN, tables: {}, views: {}, person: {}, person_unproven: [], bola: {}, write: {} };
for (const t of TABLES) {
  const exists = Number(psql(`select count(*) from public."${t}" where hive_id = '${FOREIGN}'`) || 0);
  if (!exists) { na++; continue; }                       // nothing to hide: a refusal here proves nothing
  tested++;
  // a solo owner has no own hive to see, so the per-table own-hive control is n/a; the SOLO control below stands in
  const own = SOLO ? 0 : Number(psql(`select count(*) from public."${t}" where hive_id = '${MY_HIVE}'`) || 0);
  const [mine, theirs, anon] = [SOLO ? { n: 0 } : await ask(t, MY_HIVE, true), await ask(t, FOREIGN, true), await ask(t, FOREIGN, false)];
  const control = own === 0 ? 'n/a' : (mine.n > 0 ? 'sees own' : 'BLIND');
  if (control === 'BLIND' && !BLIND_BY_DESIGN[t]) ctlBroken++;
  const bad = (theirs.n > 0 || anon.n > 0) && !(PUBLIC_BY_DESIGN[t] && !TEETH);
  if (bad) leaks++;
  REPORT.tables[t] = { verdict: bad ? 'leak' : (control === 'BLIND' && !BLIND_BY_DESIGN[t]) ? 'control-broken' : 'ok',
    foreign_rows: exists, member_sees: theirs.n, anon_sees: anon.n, own_rows: own, control,
    public_by_design: !!PUBLIC_BY_DESIGN[t], blind_by_design: !!BLIND_BY_DESIGN[t] };
  if (bad || (control === 'BLIND' && !BLIND_BY_DESIGN[t]) || ONLY) {
    console.log(`  ${bad ? 'LEAK' : control === 'BLIND' ? 'ctl ' : 'ok  '} ${t.padEnd(34)} foreign=${String(exists).padStart(5)} member-sees=${String(theirs.n).padStart(4)} anon-sees=${String(anon.n).padStart(4)} own=${own} control=${control}`);
  }
}
// ── THE TRUTH VIEWS: the surface the table loop cannot see (added 2026-10-05) ────────────────────────────────
// ★WHY A SEPARATE LOOP, AND WHY IT IS THE SHARPER HALF. The loop above walks base TABLES - relkind='r'. But six
// of the pages carrying an S-lens row read almost nothing else: achievements, analytics-report, public-feed,
// skillmatrix and marketplace-seller-profile reach their data through `v_*_truth` views, so a green table sweep
// said nothing about them at all. And a view can be the RISKIER surface: 7 of this schema's 66 public views
// carry no `security_invoker` at all, which means they execute as their OWNER - postgres, which owns
// every table and carries rolbypassrls - so RLS IS NEVER CONSULTED for a read through them. A view like that is
// safe only if it filters the caller's hive ITSELF, in its own body, and nothing in the table sweep can tell
// whether it does. `CREATE OR REPLACE VIEW` also RESETS reloptions, so a view that was invoker yesterday can be
// definer today with no migration admitting it - which is exactly why this has to be measured behaviourally,
// as the person, rather than read off a catalog flag.
// ★DISTINCT IS LOAD-BEARING: the grants join matches once for anon and once for authenticated, so without it
// every view is probed and COUNTED twice - the first run reported "78 hive-scoped views" for 39 of them, and a
// count that double-claims is a claim about coverage that is simply false.
// ★AND THE TENANT KEY IS NOT ALWAYS CALLED hive_id. Requiring that column skipped v_hives_truth, whose tenant
// key is its own `id` - and that view exposes `invite_code` with SELECT granted to anon, which is precisely a
// surface worth asking about. So a view qualifies on `hive_id` OR `id`, and the choice is SELF-VALIDATING: the
// loop below only tests a view where the chosen key actually matches the foreign hive's uuid, so a view whose
// `id` means something else returns 0 and falls to n/a instead of being mis-probed. The key is compared AS TEXT
// because some of those `id`s are bigints, and an uncast uuid comparison raises instead of returning 0 - the
// skip was already correct, but it printed a psql error that read like a broken probe. (Measured after the fix:
// v_hives_truth hands a plain member exactly 1 of 6 hives - his own, with the invite code a member is entitled
// to in order to invite a colleague - and hands anon none, because the view is invoker so RLS makes the anon
// grant inert.)
const VIEW_SQL = "select distinct c.relname, (case when exists (select 1 from pg_attribute a where "
  + "a.attrelid=c.oid and a.attname='hive_id' and not a.attisdropped) then 'hive_id' else 'id' end) as keycol "
  + "from pg_class c join pg_namespace n on n.oid=c.relnamespace "
  + "join pg_attribute a on a.attrelid=c.oid and a.attname in ('hive_id','id') and not a.attisdropped "
  + "join information_schema.role_table_grants g on g.table_name=c.relname and g.grantee in ('anon','authenticated') "
  + "and g.privilege_type='SELECT' where n.nspname='public' and c.relkind='v' order by c.relname";
const VIEWS = psql(VIEW_SQL).split(String.fromCharCode(10)).map((l) => l.trim()).filter(Boolean)
  .map((l) => { const [name, keycol] = l.split('|'); return { name, keycol }; })
  .filter((v) => v.name && (!ONLY || v.name === ONLY));
let vleaks = 0, vtested = 0, vna = 0, vctl = 0;
for (const { name: v, keycol: VK } of VIEWS) {
  const exists = Number(psql(`select count(*) from public."${v}" where "${VK}"::text = '${FOREIGN}'`) || 0);
  if (!exists) { vna++; continue; }                      // nothing to hide through it: a refusal proves nothing
  vtested++;
  // ★security_invoker IS A BOOLEAN AND POSTGRES ACCEPTS FIVE SPELLINGS OF TRUE (fixed 2026-10-05). The first
  // version matched the literal text 'security_invoker=on' and this schema stores 43 of its 59 invoker views as
  // 'security_invoker=true' - so the probe labelled them DEFINER and I reported "50 of 66 views run as their
  // owner, RLS never consulted", which was false and alarming. The real count is 7. Parse the option as a
  // boolean (on/true/yes/1), never as a substring: a second valid spelling of true is how a matcher lies.
  const definer = psql(`select case when exists (select 1 from unnest(coalesce(c.reloptions,'{}')) o where lower(o) in ('security_invoker=on','security_invoker=true','security_invoker=yes','security_invoker=1')) then 'inv' else 'DEFINER' end from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relname = '${v}'`);
  const own = SOLO ? 0 : Number(psql(`select count(*) from public."${v}" where "${VK}"::text = '${MY_HIVE}'`) || 0);
  const [mine, theirs, anon] = [SOLO ? { n: 0 } : await ask(v, MY_HIVE, true, VK), await ask(v, FOREIGN, true, VK), await ask(v, FOREIGN, false, VK)];
  const control = own === 0 ? 'n/a' : (mine.n > 0 ? 'sees own' : 'BLIND');
  if (control === 'BLIND' && !BLIND_BY_DESIGN[v]) vctl++;
  // the subset oracle: where one exists, a by-design-public view must expose EXACTLY the intended subset
  let subset = null;
  const orc = SUBSET_ORACLES[v];
  if (orc) {
    // ★UNDER --teeth THE EXPECTATION IS PERTURBED BY ONE, because an oracle that has only ever agreed is
    // indistinguishable from an oracle that is never consulted. The policy and this SQL move together whenever
    // the DATA changes (flag a post and both drop), so no amount of seeding can demonstrate the catch - only a
    // deliberate disagreement can. --teeth creates one, and the run must report the drift.
    const want = Number(psql(orc.sql(FOREIGN)) || 0) + (TEETH ? 1 : 0);
    subset = { expected: want, got: theirs.n, says: orc.says, ok: want === theirs.n };
    if (!subset.ok) {
      vleaks++;
      console.log(`  LEAK ${v.padEnd(34)} declared public-by-design but the subset DRIFTED: a plain member saw `
        + `${theirs.n} of the foreign hive's rows where ${orc.says} yields ${want}`);
    }
  }
  const bad = !(subset && !subset.ok)
    && (theirs.n > 0 || anon.n > 0) && !((PUBLIC_BY_DESIGN[v] || PUBLIC_VIEWS_BY_DESIGN[v]) && !TEETH);
  if (bad) vleaks++;
  REPORT.views[v] = { verdict: bad ? 'leak' : (control === 'BLIND' && !BLIND_BY_DESIGN[v]) ? 'control-broken' : 'ok',
    security: definer, foreign_rows: exists, member_sees: theirs.n, anon_sees: anon.n, own_rows: own, control, tenant_key: VK,
    public_by_design: !!(PUBLIC_BY_DESIGN[v] || PUBLIC_VIEWS_BY_DESIGN[v]),
    by_design_reason: PUBLIC_VIEWS_BY_DESIGN[v] || PUBLIC_BY_DESIGN[v] || null,
    blind_by_design: !!BLIND_BY_DESIGN[v], subset };
  if (bad || (control === 'BLIND' && !BLIND_BY_DESIGN[v]) || ONLY) {
    console.log(`  ${bad ? 'LEAK' : control === 'BLIND' ? 'ctl ' : 'ok  '} ${v.padEnd(34)} ${definer.padEnd(7)} ${VK.padEnd(7)} foreign=${String(exists).padStart(5)} member-sees=${String(theirs.n).padStart(4)} anon-sees=${String(anon.n).padStart(4)} own=${own} control=${control}`);
  }
}
console.log(`  views ${String(vtested - vleaks).padStart(2)}/${vtested} hive-scoped views granted to anon/authenticated refuse a foreign hive (${vna} had nothing to hide · ${Object.keys(PUBLIC_VIEWS_BY_DESIGN).length} declared public-by-design, each against measured arithmetic)`);
// ★THE SOLO OWNER'S CONTROL (2026-10-08). With no own hive, every per-relation control above is n/a, so a broken probe
// (a dead token, PostgREST down) would read as a clean sweep of refusals. The control that stands in is the person's
// OWN hive-less rows - the personal lane the solo owner actually works in - which she must SEE through the same path.
if (SOLO) {
  REPORT.solo_control = {};
  for (const t of ['logbook', 'asset_nodes', 'pm_assets']) {
    const ownN = Number(psql(`select count(*) from public."${t}" where hive_id is null and auth_uid::text = '${ACTOR_UID}'`) || 0);
    if (!ownN) continue;
    const r = await fetch(`${EDGE}/rest/v1/${t}?select=id&hive_id=is.null&auth_uid=eq.${ACTOR_UID}`,
      { headers: { apikey: ANON, Authorization: 'Bearer ' + token, Accept: 'application/json', Prefer: 'count=exact', Range: '0-0' } }).catch(() => null);
    const cr = r ? (r.headers.get('content-range') || '') : '';
    const sees = r && r.status < 400 && /\/(\d+)$/.test(cr) ? Number(cr.match(/\/(\d+)$/)[1]) : 0;
    REPORT.solo_control[t] = { own_rows: ownN, sees, verdict: sees === ownN ? 'sees own' : 'BLIND' };
    if (sees !== ownN) { ctlBroken++; console.log(`  ctl  ${t.padEnd(34)} solo owner holds ${ownN} hive-less row(s) and sees ${sees} - the probe cannot vouch for its refusals`); }
  }
  const n = Object.keys(REPORT.solo_control).length;
  console.log(`  solo  ${Object.values(REPORT.solo_control).filter((v) => v.verdict === 'sees own').length}/${n} of the person's own hive-less relations read back in full (the control that stands in for an own hive)`);
  if (!n) { ctlBroken++; console.log('  ctl  solo owner holds no hive-less rows - there is no control, so no refusal here can be trusted'); }
}

// ── THE PERSON-SCOPED TABLES: a boundary that is not the hive at all (added 2026-10-05) ──────────────────────
// ★WHY THE TWO LOOPS ABOVE CANNOT SEE THIS, and why it is the half that worried me most. Both of them select
// their subjects by `has a hive_id column`, because the tenant boundary is the hive. Fifteen public tables carry
// no hive_id at all - they are scoped to a PERSON, by auth_uid or worker_name - so every sweep this prover has
// ever run skipped them in silence. They are not minor: mfa_enrollments, push_subscriptions, resume_versions,
// credit_starter_grants, skill_exam_attempts, marketplace_watchlist. A leak here is not "hive B's data"; it is
// one named colleague reading another's second factor, their saved documents, or their exam attempts.
// This is also the exact shape of the defect Ian reported on the logbook: the boundary that bites is often the
// PERSON, and a probe keyed on the tenant proves nothing about it.
// The test is the same discipline as above: ask, as Wilfredo, for rows that belong to someone ELSE, and require
// a refusal - with a positive control (he must see his OWN rows) so a blanket-blind table cannot pass as secure.
const PERSON_SQL = "select distinct c.relname from pg_class c join pg_namespace n on n.oid=c.relnamespace "
  + "where n.nspname='public' and c.relkind='r' "
  + "and not exists (select 1 from pg_attribute a where a.attrelid=c.oid and a.attname='hive_id' and not a.attisdropped) "
  + "and exists (select 1 from pg_attribute a where a.attrelid=c.oid and a.attname in ('auth_uid','worker_name') and not a.attisdropped) "
  + "order by c.relname";
const PERSON_TABLES = psql(PERSON_SQL).split(String.fromCharCode(10)).map((t) => t.trim())
  .filter((t) => t && (!ONLY || t === ONLY));
let pleaks = 0, ptested = 0, pna = 0, pctl = 0;
for (const t of PERSON_TABLES) {
  const hasUid = psql(`select count(*) from pg_attribute a join pg_class c on c.oid=a.attrelid join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relname='${t}' and a.attname='auth_uid' and not a.attisdropped`) !== '0';
  const col = hasUid ? 'auth_uid' : 'worker_name';
  // ★IT MUST BE A STRANGER, NOT A COLLEAGUE (fixed on the first run, 2026-10-05). The first version picked "the
  // most-populated OTHER person" and reported worker_achievements as a LEAK: Wilfredo read all 8 of Bryan
  // Garcia's rows. Bryan is a Baguio CO-MEMBER, and the policy is `auth_uid = auth.uid() OR worker_name IN
  // user_hive_worker_names()` - an achievement wall your hive can see, which is the product. The probe had
  // manufactured the finding by choosing a person the policy deliberately admits. "Someone else" is not the
  // boundary; "someone who shares no hive with me" is. So the subject is now a person with NO shared active
  // membership, and a co-member read is the positive control rather than a defect.
  // the actor's uid from the ACCOUNT, not from a membership: a solo owner has no hive_members row to read it from
  const meKey = ACTOR_UID || psql(`select auth_uid::text from hive_members where worker_name = '${ACTOR.name}' and status='active' limit 1`);
  const strangerSQL = hasUid
    ? `select t.auth_uid::text from public."${t}" t where t.auth_uid is not null and t.auth_uid::text <> '${meKey}'
         and not exists (select 1 from hive_members a join hive_members b on b.hive_id = a.hive_id and b.status='active'
                         where a.auth_uid::text = '${meKey}' and a.status='active' and b.auth_uid = t.auth_uid)
         group by 1 order by count(*) desc limit 1`
    : `select t.worker_name from public."${t}" t where t.worker_name is not null and t.worker_name <> '${ACTOR.name}'
         and not exists (select 1 from hive_members a join hive_members b on b.hive_id = a.hive_id and b.status='active'
                         where a.auth_uid::text = '${meKey}' and a.status='active' and b.worker_name = t.worker_name)
         group by 1 order by count(*) desc limit 1`;
  const other = psql(strangerSQL.replace(/\s+/g, ' '));
  // ★NAME WHAT WAS SKIPPED, never just count it. A bare `5 had nothing to hide` reads as coverage; the list
  // reads as the gap it is - and mfa_enrollments / resume_versions are the two I least want silently unproven.
  if (!other) { pna++; REPORT.person_unproven.push(`${t} (no stranger rows to hide)`); continue; }
  ptested++;
  const theirs = Number(psql(`select count(*) from public."${t}" where ${col}::text = '${other}'`) || 0);
  const q = `${EDGE}/rest/v1/${t}?select=${col}&${col}=eq.${encodeURIComponent(other)}`;
  const H = { apikey: ANON, Accept: 'application/json', Prefer: 'count=exact', Range: '0-0' };
  const r = await fetch(q, { headers: { ...H, Authorization: 'Bearer ' + token } }).catch(() => null);
  const an = await fetch(q, { headers: H }).catch(() => null);
  const cnt = (x) => { if (!x || x.status >= 400) return 0; const cr = x.headers.get('content-range') || ''; return /\/(\d+)$/.test(cr) ? Number(cr.match(/\/(\d+)$/)[1]) : 0; };
  const sawTheirs = cnt(r), sawAnon = cnt(an);
  // positive control: he must be able to read his OWN rows, or the table is blind and proves nothing
  const mineKey = hasUid ? meKey : ACTOR.name;
  const ownRows = Number(psql(`select count(*) from public."${t}" where ${col}::text = '${mineKey}'`) || 0);
  const cm = await fetch(`${EDGE}/rest/v1/${t}?select=${col}&${col}=eq.${encodeURIComponent(mineKey)}`,
    { headers: { ...H, Authorization: 'Bearer ' + token } }).catch(() => null);
  const sawOwn = cnt(cm);
  const control = ownRows === 0 ? 'n/a' : (sawOwn > 0 ? 'sees own' : 'BLIND');
  if (control === 'BLIND' && !BLIND_BY_DESIGN[t]) pctl++;
  const bad = (sawTheirs > 0 || sawAnon > 0) && !(PUBLIC_BY_DESIGN[t] && !TEETH);
  if (bad) pleaks++;
  REPORT.person[t] = { verdict: bad ? 'leak' : (control === 'BLIND' && !BLIND_BY_DESIGN[t]) ? 'control-broken' : 'ok',
    scoped_by: col, other_person_rows: theirs, member_sees: sawTheirs, anon_sees: sawAnon,
    own_rows: ownRows, control };
  if (bad || (control === 'BLIND' && !BLIND_BY_DESIGN[t]) || ONLY) {
    console.log(`  ${bad ? 'LEAK' : control === 'BLIND' ? 'ctl ' : 'ok  '} ${t.padEnd(34)} by ${col.padEnd(11)} theirs=${String(theirs).padStart(4)} member-sees=${String(sawTheirs).padStart(4)} anon-sees=${String(sawAnon).padStart(4)} own=${ownRows} control=${control}`);
  }
}
if (REPORT.person_unproven.length) console.log(`  person UNPROVEN (no stranger's rows exist to refuse): ${REPORT.person_unproven.join(', ')}`);
console.log(`  person ${String(ptested - pleaks).padStart(2)}/${ptested} person-scoped tables (no hive_id - auth_uid/worker_name) refuse a STRANGER's rows - someone sharing no hive with the actor, since a co-member read is the product (${pna} had no stranger's rows to hide)`);

// ── BOLA: the same row asked for by its OWN id, with no hive filter at all ───────────────────────────────────
// A hive_id predicate is the honest test for a LIST; it is not the test for the shape this platform actually fears -
// a client that learned one uuid and asks for it directly. Nine tables carry a row a person could name.
let bola = 0, bolaTested = 0;
for (const t of ['pm_assets', 'logbook', 'inventory_items', 'projects', 'engineering_calcs', 'voice_journal_entries', 'resume_documents', 'sensor_readings', 'community_replies']) {
  const id = psql(`select id from public."${t}" where hive_id = '${FOREIGN}' limit 1`);
  if (!id || !/^[0-9a-f-]{36}$/.test(id)) continue;
  bolaTested++;
  const r = await fetch(`${EDGE}/rest/v1/${t}?select=id&id=eq.${id}`, { headers: { apikey: ANON, Authorization: 'Bearer ' + token, Accept: 'application/json' } });
  const rows = await r.json().catch(() => []);
  const got = Array.isArray(rows) ? rows.length : 0;
  REPORT.bola[t] = { verdict: got > 0 ? 'leak' : 'ok', rows_handed_over: got, asked_id: id };
  if (got > 0) { bola++; console.log(`  BOLA ${t.padEnd(33)} a foreign row handed over by id alone: ${id}`); }
}
console.log(`  bola  ${String(bolaTested - bola).padStart(2)}/${bolaTested} tables refuse a foreign row asked for by its own id (no hive filter)`);

// ── WRITE-AUTHZ DEPTH: refusing to SHOW a row is only half a boundary ────────────────────────────────────────
// A member who cannot read hive B may still be able to CHANGE it. Three shapes, each on the app's own path:
//   W1 forge   INSERT a row carrying the foreign hive_id      - the WITH CHECK arm of the write policy
//   W2 reach   PATCH a foreign row found by its own id        - the USING arm
//   W3 erase   DELETE that same foreign row
// A write that lands is both a finding and a mess, so anything that survives is removed with the superuser
// connection immediately and named in the output.
let wbad = 0, wtested = 0;
const WRITE_TABLES = ['logbook', 'pm_assets', 'inventory_items', 'projects', 'community_posts'];
for (const t of WRITE_TABLES) {
  const fid = psql(`select id from public."${t}" where hive_id = '${FOREIGN}' limit 1`);
  if (!fid || !/^[0-9a-f-]{36}$/.test(fid)) continue;
  wtested++;
  const H = { apikey: ANON, Authorization: 'Bearer ' + token, 'Content-Type': 'application/json', Prefer: 'return=representation' };
  const before = psql(`select count(*) from public."${t}" where hive_id = '${FOREIGN}'`);
  // W1 forge a row into the foreign hive
  const cols = psql(`select string_agg(column_name, ',') from information_schema.columns where table_schema='public' and table_name='${t}' and is_nullable='NO' and column_default is null and column_name not in ('id','hive_id')`);
  const body = { hive_id: FOREIGN };
  for (const c of (cols || '').split(',').filter(Boolean)) body[c] = 'wh-authz-probe';
  const ins = await fetch(`${EDGE}/rest/v1/${t}`, { method: 'POST', headers: H, body: JSON.stringify(body) }).catch(() => null);
  const insOk = ins && ins.status >= 200 && ins.status < 300;
  // W2 reach into a foreign row
  const pat = await fetch(`${EDGE}/rest/v1/${t}?id=eq.${fid}`, { method: 'PATCH', headers: H, body: JSON.stringify({ hive_id: FOREIGN }) }).catch(() => null);
  const patRows = pat ? await pat.json().catch(() => []) : [];
  const patOk = pat && pat.status < 300 && Array.isArray(patRows) && patRows.length > 0;
  // W3 erase it
  // ★AN ACCEPTED DELETE WAS THE ONE WRITE THIS PROBE COULD NOT UNDO (2026-10-08). The forge is removed below and the
  // patch writes the row's own hive_id back onto it, but a DELETE that a broken policy let through destroyed a seeded
  // row for good - the probe would report the leak and leave the hive one row short, unseen
  // ([[feedback_my_probe_destroyed_data_and_could_not_see_it]]). Running this as more personas (a supervisor's write
  // arm is wider than a worker's) made that real, so the row is captured first and put back if the delete lands.
  const snap = psqlIn(`select row_to_json(x)::text from public."${t}" x where id = '${fid}';`);
  const del = await fetch(`${EDGE}/rest/v1/${t}?id=eq.${fid}`, { method: 'DELETE', headers: H }).catch(() => null);
  const delRows = del ? await del.json().catch(() => []) : [];
  const delOk = del && del.status < 300 && Array.isArray(delRows) && delRows.length > 0;
  if (delOk && snap) {
    psqlIn(`insert into public."${t}" select * from json_populate_record(null::public."${t}", '${snap.replace(/'/g, "''")}'::json) on conflict do nothing;`);
    console.log(`  WRITE ${t.padEnd(32)} the accepted DELETE was undone from a snapshot: ${psql(`select count(*) from public."${t}" where id = '${fid}'`) === '1' ? 'row restored' : 'RESTORE FAILED - reseed this table'}`);
  }
  const after = psql(`select count(*) from public."${t}" where hive_id = '${FOREIGN}'`);
  REPORT.write[t] = { verdict: (insOk || patOk || delOk || before !== after) ? 'leak' : 'ok',
    forge: insOk ? 'ACCEPTED' : 'refused', patch: patOk ? 'ACCEPTED' : 'refused',
    delete: delOk ? 'ACCEPTED' : 'refused', rows_before: before, rows_after: after };
  if (insOk || patOk || delOk || before !== after) {
    wbad++;
    console.log(`  WRITE ${t.padEnd(32)} forge=${insOk ? 'ACCEPTED' : 'refused'} patch=${patOk ? 'ACCEPTED' : 'refused'} delete=${delOk ? 'ACCEPTED' : 'refused'} rows ${before}->${after}`);
    psql(`delete from public."${t}" where hive_id = '${FOREIGN}' and id not in (select id from public."${t}" where hive_id='${FOREIGN}' order by id limit ${before})`);
  }
}
// ★THREE REFUSALS CAN ALSO MEAN THREE MALFORMED REQUESTS. The same PATCH aimed at the member's OWN hive must be
// ACCEPTED, or the refusals above prove nothing about the boundary and everything about my request shape.
let wcontrol = 'not run';
// ★AND IT MUST BE A ROW THE MEMBER OWNS. The first control patched any row of the home hive and was refused on all
// five tables - correctly: pm_assets carries a RESTRICTIVE `pm_assets_update_guard` that admits only the row's own
// author or a supervisor, so a plain worker editing a colleague's asset is refused by design. A control has to ask
// for something the person is actually allowed to do, or it measures the guard instead of the boundary.
const MYUID = ACTOR_UID || psql(`select auth_uid from hive_members where worker_name = '${ACTOR.name}' and status = 'active' limit 1`);
for (const t of WRITE_TABLES) {
  // a solo owner's own rows carry no hive: the control patches one of THOSE, writing back the null it already holds
  let mine = psql(`select id from public."${t}" where ${SOLO ? 'hive_id is null' : `hive_id = '${MY_HIVE}'`} and auth_uid = '${MYUID}' limit 1`);
  // ★A SUPERVISOR WHO AUTHORED NOTHING STILL HAS A WRITE TO CONTROL ON (2026-10-08). Asked as Christine Dizon the
  // control found no row she wrote in any of the five tables and reported "not run" - which fails the run, correctly,
  // because three refusals with no accepted control prove nothing. But her entitlement is not authorship: the
  // RESTRICTIVE pm_assets_update_guard named above admits the row's author OR a SUPERVISOR of its hive. So for a
  // supervisor the control may ask for any row of her own hive - still something she is actually allowed to do.
  if ((!mine || !/^[0-9a-f-]{36}$/.test(mine)) && ACTOR_ROLE === 'supervisor' && !SOLO) {
    mine = psql(`select id from public."${t}" where hive_id = '${MY_HIVE}' limit 1`);
  }
  if (!mine || !/^[0-9a-f-]{36}$/.test(mine)) continue;
  const r = await fetch(`${EDGE}/rest/v1/${t}?id=eq.${mine}`, { method: 'PATCH',
    headers: { apikey: ANON, Authorization: 'Bearer ' + token, 'Content-Type': 'application/json', Prefer: 'return=representation' },
    body: JSON.stringify({ hive_id: SOLO ? null : MY_HIVE }) }).catch(() => null);
  const rows = r ? await r.json().catch(() => []) : [];
  if (r && r.status < 300 && Array.isArray(rows) && rows.length > 0) { wcontrol = `accepted on ${t}`; break; }
  wcontrol = `REFUSED on ${t} too`;
}
console.log(`  write ${String(wtested - wbad).padStart(2)}/${wtested} tables refuse a ${ASKED ? ACTOR_ROLE : 'plain member'}'s forge / patch / delete against the foreign hive · control: same patch on ${SOLO ? 'own hive-less row' : 'own hive'} ${wcontrol}`);
if (!wcontrol.startsWith('accepted')) wbad++;   // a probe that cannot write anywhere has not tested a boundary

const ok = leaks === 0 && ctlBroken === 0 && bola === 0 && wbad === 0 && vleaks === 0 && vctl === 0 && pleaks === 0 && pctl === 0;
REPORT.na_tables = na;
REPORT.person_totals = { tested: ptested, leaks: pleaks, na: pna, control_broken: pctl };
REPORT.view_totals = { tested: vtested, leaks: vleaks, na: vna, control_broken: vctl };
REPORT.totals = { tested, leaks, na, control_broken: ctlBroken, bola_tested: bolaTested, bola_leaks: bola,
                  write_tested: wtested, write_bad: wbad, write_control: wcontrol };
REPORT.pass = ok;
// ★A --teeth RUN MUST NOT LEAVE A REPORT. --teeth deliberately strips the by-design declarations to prove they
// still bite, so its verdicts are a COUNTERFACTUAL - 7 views and 4 tables read 'leak' by construction. Writing
// that file would hand a banker a report in which correct-by-design surfaces look like findings. Measured: the
// first --teeth run did exactly that, overwriting the honest report.
if (TEETH) { console.log('  report  (not written - --teeth verdicts are a counterfactual, not evidence)'); }
// ★ONE REPORT PER ACTOR, so a persona run never overwrites the plain member's report the gate is graded on (the
// prove_lxp_au_identity_after_change pattern); a banker reads each and matches the row's persona to its actor.
else { const out = ASKED ? 'tenant_refusal_report.' + ACTOR.name.toLowerCase().replace(/[^a-z]/g, '') + '.json' : 'tenant_refusal_report.json';
  const tmp = out + '.tmp';
  writeFileSync(tmp, JSON.stringify(REPORT, null, 1) + String.fromCharCode(10));
  renameSync(tmp, out);                      // atomic: a half-written report must never be read as evidence
  console.log('  report  ' + out + ' - ' + Object.keys(REPORT.tables).length + ' table + '
    + Object.keys(REPORT.views).length + ' view verdict(s)'); }
console.log(`${ok ? 'PASS' : 'FAIL'} tenant-refusal - ${tested - leaks}/${tested} tenant tables + ${vtested - vleaks}/${vtested} hive-scoped views + ${ptested - pleaks}/${ptested} person-scoped tables + ${bolaTested - bola}/${bolaTested} by-id (BOLA) + ${wtested - wbad}/${wtested} write-authz refuse a foreign hive's rows to a signed-in member AND to anon (${na} had nothing to hide · ${Object.keys(PUBLIC_BY_DESIGN).length} declared public-by-design · ${Object.keys(BLIND_BY_DESIGN).length} declared blind-to-a-worker${ctlBroken ? ` · ${ctlBroken} UNDECLARED blind control(s)` : ''})`);
process.exit(ok ? 0 : 1);
