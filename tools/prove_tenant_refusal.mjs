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
import { HIVE, WORKER } from './prover_harness.mjs';

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
const ADMIN_MODE = process.argv.includes('--as-admin');
// --teeth drops the by-design exemptions: the run MUST fail, proving the gate can still see a cross-hive read.
const TEETH = process.argv.includes('--teeth');

const EDGE = 'http://127.0.0.1:54321';
const ANON = process.env.WH_ANON_KEY || 'sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ';
const ONLY = (() => { const i = process.argv.indexOf('--table'); return i >= 0 ? process.argv[i + 1] : null; })();

const psql = (sql) => { try { return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim(); } catch { return ''; } };

// the hive our member does NOT belong to, chosen as the one with the most rows to hide
const FOREIGN = psql(`select h.id from hives h where h.id <> '${HIVE}' order by (select count(*) from logbook l where l.hive_id = h.id) desc limit 1`);
const FOREIGN_NAME = psql(`select name from hives where id = '${FOREIGN}'`);

const TABLE_SQL = "select c.relname from pg_class c join pg_namespace n on n.oid=c.relnamespace join pg_attribute a on a.attrelid=c.oid and a.attname='hive_id' and not a.attisdropped where n.nspname='public' and c.relkind='r' order by c.relname";
const TABLES = psql(TABLE_SQL).split(String.fromCharCode(10)).map((t) => t.trim())
  .filter(Boolean)
  .filter((t) => /^[a-z0-9_]+$/.test(t))   // a psql error line is not a table name
  .filter((t) => !ONLY || t === ONLY);

const ACTOR = ADMIN_MODE ? WORKER : (ASKED ? { name: ASKED, email: ASKED.toLowerCase().replace(/[^a-z]/g, '') + '@auth.workhiveph.com', password: 'test1234', hiveName: 'Baguio' } : PLAIN);
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
const PUBLIC_BY_DESIGN = {
  community_posts: 'community_posts_read: (public = true AND flagged = false) - the public feed is a product surface',
  marketplace_listings: 'mkt_listings_read: status = published - a marketplace that hid its listings would have no buyers',
  marketplace_sellers: 'mkt_sellers_read: any signed-in user sees the seller directory; anon sees only sellers WITH a published listing',
  service_providers: 'service_providers_read: the provider directory is readable by any signed-in user',
  marketplace_orders: 'mkt_orders_read: buyer OR seller - an order spans two hives by nature, so its hive_id is not the reader test',
  marketplace_inquiries: 'mkt_inq_read: buyer OR seller - same shape as orders',
};
// ★A PLAIN WORKER IS SUPPOSED TO BE BLIND TO THESE, so a BLIND control is the product, not a broken probe.
const BLIND_BY_DESIGN = {
  agent_memory: 'per-user store: auth.uid() = auth_uid', agent_episodic_memory: 'per-user store',
  resume_documents: 'per-user store', ai_reply_feedback: 'per-user store',
  analytics_events: 'admin/grafana only', hive_audit_log: 'supervisor/admin only',
  integration_configs: 'supervisor/admin only', project_roles: 'project membership, not hive membership',
  embedding_outbox: 'service-role queue, no client policy', community_post_xp_awards: 'service-role ledger',
  community_reaction_xp_awards: 'service-role ledger', community_reply_xp_awards: 'service-role ledger',
  ai_cost_log: 'admin/grafana only', auth_session_events: 'admin/grafana only',
  // Read from the policies rather than assumed: ai_rate_limits carries exactly two, an
  // `ai_rate_limits_locked [ALL roles=public] USING false` that refuses every client outright and an
  // `ai_rate_limits_grafana_read` for the dashboard reader. A counter that decides whether somebody
  // may make another call must not be readable OR writable by the person it limits, so a worker
  // seeing none of it is the control working. Undeclared, it failed this gate as a broken probe.
  ai_rate_limits: 'locked to every client (USING false); only grafana_reader and the service role read it',
  // ★DECLARED 2026-09-09, AND ONLY BECAUSE THE TABLE FINALLY HAD A ROW. api_keys sat empty for the whole
  // program, so this gate had nothing to test and never asked the question; reseeding one CMMS connector
  // per hive populated it, the control came back BLIND, and the gate correctly refused to guess. Read from
  // the policies, not assumed: api_keys carries exactly ONE policy, api_keys_supervisor_all, whose USING
  // requires an active SUPERVISOR of that same hive. A plain worker seeing none of his own hive's keys is
  // therefore the control working, the same shape as integration_configs above. An empty table is not a
  // passing one - it is an unasked question, and this is what it answers when finally asked.
  api_keys: 'supervisor-only (api_keys_supervisor_all: auth.uid() is an active supervisor of this hive)',
  // ★DECLARED 2026-09-11, and the SAME SHAPE AS api_keys ABOVE, for the same reason: the table only
  // just became answerable. client_errors now holds 208 rows for Baguio, so the control came back BLIND
  // for a plain member and the gate refused to guess rather than call a refusal a pass.
  // Read from the policy, not assumed: client_errors carries exactly two, and the READ one -
  // client_errors_read, FOR SELECT TO authenticated - has USING (EXISTS ... hm.role = 'supervisor'),
  // so only a supervisor of that hive may read it. Its migration says so in its own words: "READ:
  // supervisors of the hive (triage is a supervisor job) ... A worker does not need to read the error
  // log." The INSERT side is deliberately wider (any active member, or hive_id IS NULL so a login or
  // onboarding surface can still report), which is why a worker can WRITE an error he cannot READ -
  // asymmetric by design, and not a leak in either direction.
  client_errors: 'supervisor-only read (client_errors_read: USING hm.role = \'supervisor\' for that hive); insert is member-wide by design',
};

const ask = async (table, hive, auth) => {
  const h = { apikey: ANON, Accept: 'application/json', Prefer: 'count=exact', Range: '0-0' };
  if (auth) h.Authorization = 'Bearer ' + token;
  try {
    const r = await fetch(`${EDGE}/rest/v1/${table}?select=hive_id&hive_id=eq.${hive}`, { headers: h });
    const cr = r.headers.get('content-range') || '';
    const total = /\/(\d+)$/.test(cr) ? Number(cr.match(/\/(\d+)$/)[1]) : null;
    if (r.status >= 400) return { status: r.status, n: 0, refused: true };
    return { status: r.status, n: total ?? 0, refused: false };
  } catch (e) { return { status: 0, n: -1, err: String(e).slice(0, 60) }; }
};

console.log(`  acting as ${ACTOR.name} (${ACTOR.hiveName}${ADMIN_MODE ? ', PLATFORM ADMIN - asserting the admin path' : ', plain member'}) · foreign hive: ${FOREIGN_NAME} ${FOREIGN.slice(0, 8)}`);
let leaks = 0, tested = 0, na = 0, ctlBroken = 0;
for (const t of TABLES) {
  const exists = Number(psql(`select count(*) from public."${t}" where hive_id = '${FOREIGN}'`) || 0);
  if (!exists) { na++; continue; }                       // nothing to hide: a refusal here proves nothing
  tested++;
  const own = Number(psql(`select count(*) from public."${t}" where hive_id = '${HIVE}'`) || 0);
  const [mine, theirs, anon] = [await ask(t, HIVE, true), await ask(t, FOREIGN, true), await ask(t, FOREIGN, false)];
  const control = own === 0 ? 'n/a' : (mine.n > 0 ? 'sees own' : 'BLIND');
  if (control === 'BLIND' && !BLIND_BY_DESIGN[t]) ctlBroken++;
  const bad = (theirs.n > 0 || anon.n > 0) && !(PUBLIC_BY_DESIGN[t] && !TEETH);
  if (bad) leaks++;
  if (bad || (control === 'BLIND' && !BLIND_BY_DESIGN[t]) || ONLY) {
    console.log(`  ${bad ? 'LEAK' : control === 'BLIND' ? 'ctl ' : 'ok  '} ${t.padEnd(34)} foreign=${String(exists).padStart(5)} member-sees=${String(theirs.n).padStart(4)} anon-sees=${String(anon.n).padStart(4)} own=${own} control=${control}`);
  }
}
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
  const del = await fetch(`${EDGE}/rest/v1/${t}?id=eq.${fid}`, { method: 'DELETE', headers: H }).catch(() => null);
  const delRows = del ? await del.json().catch(() => []) : [];
  const delOk = del && del.status < 300 && Array.isArray(delRows) && delRows.length > 0;
  const after = psql(`select count(*) from public."${t}" where hive_id = '${FOREIGN}'`);
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
const MYUID = psql(`select auth_uid from hive_members where worker_name = '${ACTOR.name}' and status = 'active' limit 1`);
for (const t of WRITE_TABLES) {
  const mine = psql(`select id from public."${t}" where hive_id = '${HIVE}' and auth_uid = '${MYUID}' limit 1`);
  if (!mine || !/^[0-9a-f-]{36}$/.test(mine)) continue;
  const r = await fetch(`${EDGE}/rest/v1/${t}?id=eq.${mine}`, { method: 'PATCH',
    headers: { apikey: ANON, Authorization: 'Bearer ' + token, 'Content-Type': 'application/json', Prefer: 'return=representation' },
    body: JSON.stringify({ hive_id: HIVE }) }).catch(() => null);
  const rows = r ? await r.json().catch(() => []) : [];
  if (r && r.status < 300 && Array.isArray(rows) && rows.length > 0) { wcontrol = `accepted on ${t}`; break; }
  wcontrol = `REFUSED on ${t} too`;
}
console.log(`  write ${String(wtested - wbad).padStart(2)}/${wtested} tables refuse a plain member's forge / patch / delete against the foreign hive · control: same patch on own hive ${wcontrol}`);
if (!wcontrol.startsWith('accepted')) wbad++;   // a probe that cannot write anywhere has not tested a boundary

const ok = leaks === 0 && ctlBroken === 0 && bola === 0 && wbad === 0;
console.log(`${ok ? 'PASS' : 'FAIL'} tenant-refusal - ${tested - leaks}/${tested} tenant tables + ${bolaTested - bola}/${bolaTested} by-id (BOLA) + ${wtested - wbad}/${wtested} write-authz refuse a foreign hive's rows to a signed-in member AND to anon (${na} had nothing to hide · ${Object.keys(PUBLIC_BY_DESIGN).length} declared public-by-design · ${Object.keys(BLIND_BY_DESIGN).length} declared blind-to-a-worker${ctlBroken ? ` · ${ctlBroken} UNDECLARED blind control(s)` : ''})`);
process.exit(ok ? 0 : 1);
