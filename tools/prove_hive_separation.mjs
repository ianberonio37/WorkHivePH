// prove_hive_separation — W3-LC: "the platform must keep a person's two hives apart on this page, in both
// directions". Eight pages carry this row. No browser.
//
// ★THIS EXISTS BECAUSE THE LENS THAT HELD THESE ROWS ANSWERED A DIFFERENT QUESTION. `prove_lifecycle_cells`
// graded the claim as `r.chars > 400` — "renders inside one hive scope" — which is satisfied by any page
// that renders at all. Four of the eight were banked on it. A page rendering 400 characters says nothing
// about whether one hive's rows can appear while the other is the active one; the live-walk manifest was
// right to keep all eight open and to name `postgres-mcp` as the instrument they need.
//
// The claim has two halves and BOTH must hold, because either alone is worthless:
//
//   SCOPED    every read the page makes against a hive-owned table carries the active hive — `.eq('hive_id',
//             ...)`, a hive-scoped truth view, or an RPC taking the hive as an argument. An unscoped read is
//             the defect: it would show a person their OTHER hive's rows without them asking.
//
//   LOAD-BEARING  the same read, made as this person WITHOUT the scope, really does return both hives. If it
//             does not, the scope is holding nothing up and a green here would be vacuous — the page would
//             pass because the person has no second hive worth separating, not because it separates them.
//             (★A GATE THAT CANNOT FAIL IS NOT A GATE. This is that check, applied to itself.)
//
// Answered as a person who is genuinely in two hives, through PostgREST with her own token — never the owner
// connection, which carries rolbypassrls and so can prove a row EXISTS but never that a read was scoped.
//
//   node tools/prove_hive_separation.mjs
//   node tools/prove_hive_separation.mjs --self-test
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { execSync } from 'node:child_process';

const EDGE = process.env.WH_EDGE_URL || 'http://127.0.0.1:54321';
const ANON = process.env.WH_ANON_KEY || 'sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ';
const args = process.argv.slice(2);
const MARK = 'two hives apart';

// a busy database is not an absent one — the same patience every probe here needs
const psql = (sql, tries = 5) => {
  for (let i = 0; i < tries; i++) {
    try {
      return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`,
        { encoding: 'utf8', timeout: 25000, killSignal: 'SIGKILL' }).trim();
    } catch { try { execSync('powershell -NoProfile -Command "Start-Sleep -Milliseconds 1500"', { stdio: 'ignore', timeout: 8000 }); } catch { /* even the wait may be refused */ } }
  }
  return '';
};

// ★THE PERSON MUST REALLY BE IN TWO HIVES, AND MUST NOT BE AN ADMIN. Read from the database rather than
// typed here: a name typed into a probe is a name that drifts away from the seed it describes.
const WHO = psql(`select m.worker_name from hive_members m where m.status='active' and not exists (select 1 from marketplace_platform_admins a where a.worker_name = m.worker_name) group by m.worker_name having count(distinct m.hive_id) > 1 limit 1`);
const HIVES = psql(`select string_agg(distinct hive_id::text, ',') from hive_members where worker_name = '${WHO}' and status='active'`)
  .split(',').map((s) => s.trim()).filter(Boolean);
const EMAIL = psql(`select u.email from auth.users u join hive_members m on m.auth_uid = u.id where m.worker_name = '${WHO}' limit 1`);
const HIVE_TABLES = new Set(psql(`select table_name from information_schema.columns where column_name='hive_id' and table_schema='public'`).split('\n').map((s) => s.trim()).filter(Boolean));

// the rows this prover answers - the roster IS the registry
const rows = JSON.parse(readFileSync('trajectory_registry.json', 'utf8')).trajectories
  .filter((t) => (t.title || '').includes(MARK))
  .map((t) => ({ id: t.id, page: (t.pages || [])[0], status: t.status }))
  .filter((r) => r.page);

// ★A SHARED SCRIPT'S READS BELONG TO THE SCRIPT, NOT TO EVERY PAGE THAT LOADS IT. The first version folded
// each page's `<script src>` files into its source, so `utils.js` - 362 KB carrying reads for the whole
// platform - was judged as part of all eight pages. Every one came back BAD, naming tables it never touches:
// logbook.html was accused over `project_links`, alert-hub over `parts_staging_recommendations`. 8 of 8 is
// an impossibly bad number, and an impossibly bad number is the probe, exactly as an impossibly clean one is.
// A page is judged by the reads IT makes; the shared pieces are their own subject (that is what W3-SC is).
function source(page) {
  try { return readFileSync(page, 'utf8'); } catch { return ''; }
}

// ★A SCOPE CAN BE WRITTEN SEVERAL WAYS AND ALL OF THEM COUNT. This platform scopes by `.eq('hive_id', ...)`,
// by reading a `v_*_truth` view that carries the hive in its own predicate, and by RPCs that take the hive
// as an argument. Demanding one spelling would report the other two as defects.
// ★AND A FOURTH SPELLING, WHICH IS NOT EVEN A METHOD CALL. pm-scheduler builds its query, then applies
// `scopeQ = scopeQ.or(\`hive_id.eq.${HIVE_ID},hive_id.is.null\`)` a thousand characters later, through a
// variable - the hive lives inside a POSTGREST FILTER STRING. Read only as `.eq('hive_id', ...)` it looked
// unscoped, and a page that scopes correctly was reported as mixing two hives.
const SCOPE_NEAR = /\.eq\(\s*['"`]hive_id['"`]|hive_id\s*:|['"`]hive_id['"`]\s*,|hive_id\.(?:eq|in|is)\.|p_hive_id|hiveId|activeHive|wh_active_hive_id/i;
// ★A WRITE IS NOT A READ, AND A WORKER IS NOT A HIVE. Two corrections, each of which had turned a working
// page red. alert-hub's only `anomaly_signals` call is `.update(updates).eq('id', id)` - a write naming one
// row, governed by RLS, with no business carrying a hive filter. And dayplanner reads `v_logbook_truth`
// scoped by `worker_name`, which is a real scope but the WRONG one for this claim: this person is the same
// worker in both hives, so her own name selects her rows in BOTH. That is a different finding from an
// unscoped read, and it is only a finding if the data really does span - which is checked live, below.
// ★THE HIVE SWITCHER MUST SPAN HIVES - THAT IS ITS JOB. `hive.html` reads `v_worker_truth` by worker name
// with no hive filter, and the first reading called that a leak. Read in full, those calls are
// `recoverHiveMembership` and `reconcileHiveList`: they ask "which hives does this person belong to" so the
// switcher can offer them. A membership table describes the person's RELATIONSHIP to hives, so spanning is
// correct there and only there; every table holding a hive's CONTENTS still owes the scope.
const MEMBERSHIP = new Set(['v_worker_truth', 'hive_members', 'v_hives_truth', 'hives', 'hive_invites']);
// ★A MARKETPLACE THAT ONLY SHOWED YOUR OWN HIVE WOULD NOT BE A MARKETPLACE. asset-hub reads
// `v_marketplace_listings_truth` to offer parts matching an asset's ISO class; those listings belong to
// OTHER hives, which is the entire point. The same is true of the community and the public feed. These
// surfaces are cross-hive by design, and a hive scope on them would be the defect.
const SHARED = new Set(['v_marketplace_listings_truth', 'marketplace_listings', 'service_providers',
  'v_service_providers_truth', 'community_posts', 'community_replies', 'community_reactions',
  'v_community_posts_truth', 'public_feed', 'v_public_feed_truth', 'marketplace_inquiries']);

// ★A PAGE MAY SCOPE THROUGH A HELPER IT NAMED ITSELF. asset-hub writes `scopeNodes(db.from('asset_nodes')…)`
// where `const scopeNodes = q => q.or(\`hive_id.eq.${HIVE_ID},…\`)` — the filter is real, applied to every
// read, and lives nowhere near the call. Looking only at the text around `.from(` reported four correctly
// scoped reads as unscoped. Find the helpers the page defines with a hive filter in them, then treat a read
// handed to one as scoped, which is exactly what it is.
function scopeHelpers(src) {
  const names = new Set();
  for (const m of src.matchAll(/(?:const|let|var|function)\s+([A-Za-z_$][\w$]*)\s*(?:=|\()/g)) {
    const body = src.slice(m.index, m.index + 340);
    if (/hive_id\.(?:eq|in|is)\.|\.eq\(\s*['"`]hive_id['"`]/.test(body)) names.add(m[1]);
  }
  return names;
}

function unscopedReads(src) {
  const helpers = scopeHelpers(src);
  const bad = [], workerOnly = [];
  for (const m of src.matchAll(/\.from\(\s*['"`]([a-z0-9_]+)['"`]\s*\)/gi)) {
    const table = m[1];
    if (!HIVE_TABLES.has(table) || MEMBERSHIP.has(table) || SHARED.has(table)) continue;   // no hive column, the membership itself, or a surface that is cross-hive by design
    const after = src.slice(m.index, m.index + 900);
    const verb = /\.(select|update|insert|upsert|delete)\s*\(/.exec(after);
    if (!verb || verb[1] !== 'select') continue;        // a write is governed by the row it names
    // the filter can be written after the .from(, and on some builders before it - read both sides, and
    // read far enough that a long .select() column list cannot push the .eq out of view
    const window = src.slice(Math.max(0, m.index - 260), m.index + 2600);
    if (SCOPE_NEAR.test(window)) continue;
    // ★A READ THAT NAMES ONE ROW IS NOT BROWSING A HIVE. hive.html answers a realtime payload with
    // `.eq('scope_item_id', payload.new.scope_item_id).maybeSingle()` - it already knows which row it
    // wants, and RLS decides whether it may have it. Asking that call for a hive filter is asking it to
    // re-state something the id already settled.
    if (/\.(?:maybeSingle|single)\s*\(/.test(window) || /\.(?:eq|in)\(\s*['"`](?:id|[a-z0-9_]*_id)['"`]/i.test(window)) continue;
    // handed to a helper this page defined with a hive filter in it
    const before = src.slice(Math.max(0, m.index - 90), m.index);
    if ([...helpers].some((h) => before.includes(h + '('))) continue;
    if (/\.eq\(\s*['"`]worker_name['"`]/.test(window)) workerOnly.push(table);
    else bad.push(table);
  }
  return { bad: [...new Set(bad)], workerOnly: [...new Set(workerOnly)] };
}
// the witness for "the scope is load-bearing" should be a table holding a hive's CONTENTS. `hive_members`
// spans her hives trivially - that is what membership is - so proving the point with it proves little.
function readTables(src) {
  const all = [...new Set([...src.matchAll(/\.from\(\s*['"`]([a-z0-9_]+)['"`]\s*\)/gi)].map((m) => m[1]))]
    .filter((t) => HIVE_TABLES.has(t));
  const content = all.filter((t) => !MEMBERSHIP.has(t) && !SHARED.has(t));
  return content.length ? content : all;
}

async function token() {
  for (let i = 0; i < 5; i++) {
    const r = await fetch(`${EDGE}/auth/v1/token?grant_type=password`, {
      method: 'POST', headers: { apikey: ANON, 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: EMAIL, password: 'test1234' }),
    }).catch(() => null);
    const j = r ? await r.json().catch(() => ({})) : {};
    if (j.access_token) return j.access_token;
    await new Promise((res) => setTimeout(res, 6000));
  }
  return null;
}

async function readAs(tok, table, hive) {
  const q = hive ? `?select=hive_id&hive_id=eq.${hive}&limit=400` : '?select=hive_id&limit=400';
  const r = await fetch(`${EDGE}/rest/v1/${table}${q}`, {
    headers: { apikey: ANON, Authorization: 'Bearer ' + tok },
  }).catch(() => null);
  if (!r || !r.ok) return null;
  const j = await r.json().catch(() => null);
  return Array.isArray(j) ? [...new Set(j.map((x) => x.hive_id))] : null;
}

if (args.includes('--self-test')) {
  const fails = [];
  if (!WHO) fails.push('no person is active in two hives, so this claim has no subject');
  if (HIVES.length < 2) fails.push(`${WHO || 'that person'} resolves to ${HIVES.length} hive(s)`);
  if (!EMAIL) fails.push('that person has no sign-in of their own, so nothing can speak for them');
  if (psql(`select count(*) from marketplace_platform_admins where worker_name = '${WHO}'`) !== '0') {
    fails.push(`${WHO} is a platform admin - an admin seeing everything is the product working, not a leak`);
  }
  if (!HIVE_TABLES.size) fails.push('no hive-owned tables were read from the schema');
  // the scope oracle must accept the three spellings this platform uses, and reject a bare read
  if (!SCOPE_NEAR.test(".from('logbook').select('*').eq('hive_id', hive)")) fails.push('an .eq hive scope is not recognised');
  if (!SCOPE_NEAR.test(".rpc('fetch_active_alerts', { p_hive_id: hive })")) fails.push('an RPC hive argument is not recognised');
  if (SCOPE_NEAR.test(".from('logbook').select('*').order('created_at')")) fails.push('an UNSCOPED read is being read as scoped');
  if (!SCOPE_NEAR.test("scopeQ.or(`hive_id.eq.${HIVE_ID},hive_id.is.null`)")) fails.push('a hive inside a PostgREST filter string is not recognised');
  // ★THE FIVE CORRECTIONS THIS LENS NEEDED, EACH ONE A PAGE IT HAD WRONGLY TURNED RED. Every case below
  // was a real false positive before it was fixed; together they took the reading from 8-of-8 broken to
  // one genuine defect. A lens this easy to be wrong with must carry its own history.
  const u = (s) => unscopedReads(s).bad;
  if (u(".from('anomaly_signals').update({ a: 1 }).eq('id', id)").length) fails.push('a WRITE is being judged as an unscoped read');
  if (u(".from('hive_members').select('hive_id, role').eq('worker_name', W)").length) fails.push('the hive SWITCHER reading membership is being called a leak');
  if (u(".from('marketplace_listings').select('*').eq('status','active')").length) fails.push('a cross-hive-by-design surface is being asked for a hive scope');
  if (u(".from('logbook').select('item_text').eq('scope_item_id', id).maybeSingle()").length) fails.push('a read naming ONE row is being judged as browsing a hive');
  if (u("const scopeNodes = q => q.or(`hive_id.eq.${HIVE_ID}`); const r = await scopeNodes(db.from('asset_nodes').select('id'));").length) {
    fails.push("a read handed to the page's own hive-scoping helper is being called unscoped");
  }
  if (!u(".from('pm_assets').select('id, item_text').or('is_overdue.eq.true').limit(30)").length) {
    fails.push('a genuinely unscoped list read is NOT being caught - the lens would pass the defect it exists to find');
  }
  console.log(fails.length ? 'FAIL hive-separation self-test - ' + fails.join('; ')
    : `self-test OK: ${WHO} is active in ${HIVES.length} hives and is not an admin, ${HIVE_TABLES.size} hive-owned tables, `
      + `the scope oracle accepts .eq and an RPC argument and rejects a bare read; ${rows.length} row(s) to answer`);
  process.exit(fails.length ? 1 : 0);
}

const tok = await token();
if (!tok) { console.log(`FAIL hive-separation - could not sign in as ${WHO}; every reading here speaks for her`); process.exit(1); }
console.log(`asking ${rows.length} page(s) as ${WHO}, active in ${HIVES.length} hives`);

const results = [];
let bad = 0, unread = 0;
for (const r of rows) {
  const src = source(r.page);
  let rec;
  if (!src) {
    rec = { verdict: 'n/a', line: `${r.page} could not be read from disk` };
  } else {
    const { bad: unscoped, workerOnly } = unscopedReads(src);
    const tables = readTables(src);
    // a worker-scoped read is only a defect if her own name really does select rows in both her hives
    let mixes = null;
    for (const t of workerOnly) {
      const r = await fetch(`${EDGE}/rest/v1/${t}?select=hive_id&worker_name=eq.${encodeURIComponent(WHO)}&limit=400`,
        { headers: { apikey: ANON, Authorization: 'Bearer ' + tok } }).catch(() => null);
      const j = r && r.ok ? await r.json().catch(() => null) : null;
      const hives = Array.isArray(j) ? [...new Set(j.map((x) => x.hive_id))] : [];
      if (hives.length > 1) { mixes = `${t} is read by worker name only, and ${WHO}'s own name selects rows from ${hives.length} of her hives at once - her two hives arrive on this page together`; break; }
    }
    // the load-bearing half: does an unscoped read by this person really span both her hives?
    let spanning = null, leaked = null;
    for (const t of tables) {
      const all = await readAs(tok, t, null);
      if (!all || all.length < 2) continue;
      spanning = t;
      const one = await readAs(tok, t, HIVES[0]);
      const two = await readAs(tok, t, HIVES[1]);
      const wrong = [...(one || []).filter((h) => h !== HIVES[0]), ...(two || []).filter((h) => h !== HIVES[1])];
      if (wrong.length) leaked = `${t} answered a scoped read with ${wrong.length} row(s) from the other hive`;
      break;
    }
    if (leaked) {
      rec = { verdict: 'BAD', line: leaked };
    } else if (mixes) {
      rec = { verdict: 'BAD', line: mixes };
    } else if (unscoped.length) {
      rec = { verdict: 'BAD', line: `reads ${unscoped.length} hive-owned table(s) with no hive scope near the call (${unscoped.slice(0, 3).join(', ')}) - the other hive's rows would come back with them` };
    } else if (!spanning) {
      // ★SAYING SO IS THE POINT. Every read is scoped, but nothing this page reads holds rows in both of
      // her hives, so the separation was never put under load. That is not a pass and not a failure.
      rec = { verdict: 'n/a', line: `every hive-owned read is scoped, but none of its ${tables.length} table(s) holds rows in both of ${WHO}'s hives - the scope was never under load here` };
    } else {
      rec = { verdict: 'ok', line: `every hive-owned read is scoped, and ${spanning} really does span both her hives unscoped - so the scope is what keeps them apart, in both directions` };
    }
  }
  if (rec.verdict === 'BAD') bad++;
  if (rec.verdict === 'n/a') unread++;
  results.push({ ...r, ...rec });
  console.log(`  ${rec.verdict === 'ok' ? 'ok ' : rec.verdict === 'n/a' ? 'n/a' : 'BAD'} ${r.id.padEnd(8)} ${r.page.padEnd(26)} ${rec.line.slice(0, 96)}`);
}
mkdirSync('.tmp', { recursive: true });
writeFileSync('.tmp/hive_separation.json', JSON.stringify({ who: WHO, hives: HIVES, walked: results.length, bad, results }, null, 1));
console.log(`${bad ? 'FAIL' : 'PASS'} hive-separation - ${results.length - bad - unread}/${results.length} keep her two hives apart, ${unread} unanswerable  ·  .tmp/hive_separation.json`);
process.exit(bad ? 1 : 0);
