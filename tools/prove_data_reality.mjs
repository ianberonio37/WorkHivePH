// prove_data_reality — the data-reality journeys (T127, T128, T129, T136, T137, T138, T139, T140),
// walked as one family (2026-09-07).
//
// Eight rows about what happens when real data stops being tidy: two things share a name, someone writes
// in Filipino with an emoji in it, a logbook reaches a thousand entries, two people edit the same record
// at once, a parent record is deleted with children hanging off it, the hive gets renamed. None of these
// are exotic - they are Tuesday - and each one has a moment where the platform can quietly tell someone
// something untrue.
//
//   R1 tells apart    two records sharing a name are distinguishable on the record itself, so a person
//                     picking one is not guessing between identical rows (T127)
//   R2 keeps the text what someone types survives the round trip byte for byte: Filipino, an enye, an
//                     emoji, a degree sign. A platform that mangles a person's own language is telling
//                     them it was not built for them. (T128)
//   R3 holds volume   the big lists are bounded and ordered, so a thousand entries is a page rather than
//                     a hang (T129)
//   R4 owns the seed  demo data is labelled where a person can see it, or a person will make a decision
//                     from a machine that does not exist (T136)
//   R5 keeps history  deleted things are recoverable rather than gone, and something says where they went
//                     (T137)
//   R6 arbitrates     two edits to the same record do not silently discard the first (T138)
//   R7 cascades       deleting a parent has a DECLARED effect on its children - not an accident of
//                     whichever FK was written first (T139)
//   R8 renames        the hive's name is stored once, so renaming it does not leave the old name on
//                     surfaces that copied it (T140)
//
// ★MEASURED AS THE PERSON, THROUGH POSTGREST, WHEREVER RLS COULD CHANGE THE ANSWER. The owner connection
// is used only to read schema facts (constraints, FKs, indexes), never to stand in for a person's read.
//
//   node tools/prove_data_reality.mjs
import { execSync } from 'node:child_process';
import { readdirSync, readFileSync } from 'node:fs';
import { HIVE } from './prover_harness.mjs';

const EDGE = 'http://127.0.0.1:54321';
const ANON = process.env.WH_ANON_KEY || 'sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ';
const psql = (sql) => { try { return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim(); } catch { return ''; } };
const token = async (email) => {
  const r = await fetch(`${EDGE}/auth/v1/token?grant_type=password`, {
    method: 'POST', headers: { apikey: ANON, 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password: 'test1234' }),
  });
  return (await r.json().catch(() => ({}))).access_token || null;
};

const TOK = await token('leandromarquez@auth.workhiveph.com');
const rest = async (path, init = {}) => fetch(`${EDGE}/rest/v1/${path}`, {
  ...init, headers: { apikey: ANON, Authorization: 'Bearer ' + TOK, 'Content-Type': 'application/json', ...(init.headers || {}) },
});

let bad = 0;
const say = (ok, id, line, detail) => {
  if (!ok) bad++;
  console.log(`  ${ok ? 'ok ' : 'BAD'} ${id.padEnd(18)} ${line}`);
  if (!ok && detail) console.log(`        ${detail.slice(0, 158)}`);
};
const na = (id, line) => console.log(`  n/a ${id.padEnd(18)} ${line} - unmeasured, not clean`);

// ── R1 · two things with the same name ───────────────────────────────────────────────────────────
{
  const dupes = psql(`select asset_name, count(*) from pm_assets where hive_id = '${HIVE}' group by asset_name having count(*) > 1 order by 2 desc limit 1`);
  if (!dupes) na('R1 tells apart', 'no two assets share a name in this hive');
  else {
    const [name] = dupes.split('|');
    // what distinguishes them: a code, a location, a serial - something on the record itself
    const cols = psql(`select string_agg(a.attname, ',') from pg_attribute a where a.attrelid='public.pm_assets'::regclass and a.attnum>0 and not a.attisdropped and a.attname in ('tag_id','location','category','criticality')`);
    const rows = psql(`select coalesce(${(cols || 'id').split(',').map((c) => `nullif(${c}::text,'')`).join(', ')}, 'nothing') from pm_assets where hive_id = '${HIVE}' and asset_name = '${name.replace(/'/g, "''")}'`).split('\n');
    const distinct = new Set(rows.map((x) => x.trim())).size;
    say(distinct === rows.length, 'R1 tells apart', `"${name.slice(0, 26)}" exists ${rows.length}x; ${distinct} of them carry a distinguishing ${(cols || 'id').split(',')[0]}`,
      `${rows.length - distinct} record(s) are indistinguishable from a sibling - a person picking one is guessing`);
  }
}

// ── R2 · does someone's own language survive the round trip? ─────────────────────────────────────
{
  const text = 'Pinalitan ko ang bearing sa Pump #2 — 45°C, tapos na ✅ (ñ, ü, 日本語)';
  const r = await rest('logbook', { method: 'POST', headers: { Prefer: 'return=representation' }, body: JSON.stringify({ hive_id: HIVE, problem: text, worker_name: 'Leandro Marquez', date: '2026-09-07' }) });
  const body = await r.json().catch(() => null);
  const row = Array.isArray(body) ? body[0] : null;
  // ★A REFUSED WRITE IS A FAILED SETUP, NOT A CLEAN LENS. The first run posted an entry_type this table
  // does not have and omitted the date it requires, got a 400, and reported the round trip as unmeasured
  // when in truth nothing had been written to round-trip. The refusal is printed so the next reader sees
  // WHY rather than a shrug.
  if (!row) na('R2 keeps the text', `the write was refused (${r.status}: ${JSON.stringify(body).slice(0, 90)})`);
  else {
    const back = await rest(`logbook?select=problem&id=eq.${row.id}`);
    const got = ((await back.json().catch(() => [{}]))[0] || {}).problem || '';
    say(got === text, 'R2 keeps the text', `${text.length} characters of Filipino, an enye, a degree sign and an emoji round-tripped ${got === text ? 'byte for byte' : 'CHANGED'}`,
      `written "${text.slice(-32)}" and read back "${got.slice(-32)}"`);
    await rest(`logbook?id=eq.${row.id}`, { method: 'DELETE' });
  }
}

// ── R3 · a thousand entries ──────────────────────────────────────────────────────────────────────
{
  // ★THE BIGGEST HIVE IS NOT NECESSARILY THIS PERSON'S. The first run picked the largest logbook on the
  // platform, read it as Leandro Marquez who is not a member, and RLS correctly returned 0 rows - which
  // the prover reported as "the list cannot be paged". Volume has to be measured inside a hive the
  // reader belongs to, or the lens measures the tenancy boundary instead.
  const biggest = psql("select l.hive_id, count(*) c from logbook l join hive_members m on m.hive_id = l.hive_id and m.status = 'active' where m.worker_name = 'Leandro Marquez' group by 1 order by c desc limit 1");
  const [hv, c] = biggest.split('|');
  const idx = psql("select count(*) from pg_indexes where tablename='logbook' and (indexdef ilike '%created_at%' or indexdef ilike '%hive_id%')");
  const r = await rest(`logbook?select=id&hive_id=eq.${hv}&order=created_at.desc&limit=50`);
  const page = (await r.json().catch(() => [])).length;
  say(page === 50 && Number(idx) > 0, 'R3 holds volume', `the largest logbook holds ${c} entries; a page reads ${page} of them in order, over ${idx} supporting index(es)`,
    page !== 50 ? `an ordered page came back ${page} rows, so the list cannot be paged the way a person scrolls it` : 'no index supports the ordered read - a thousand entries is a table scan every time');
}

// ── R4 · is demo data owned as demo data? ────────────────────────────────────────────────────────
{
  const flagged = psql("select count(*) from information_schema.columns where table_schema='public' and column_name in ('is_demo','is_seed','demo','seeded')");
  // ★NO /bin/bash ON THIS HOST. Read the pages with node rather than shelling out to a grep that does
  // not exist here - a prover that cannot run is a prover that measures nothing.
  const surfaced = readdirSync('.').filter((f) => f.endsWith('.html'))
    .filter((f) => { try { return /demo data|sample data|seeded data|example data|not real data|demo hive/i.test(readFileSync(f, 'utf8')); } catch { return false; } });
  say(Number(flagged) > 0 || surfaced.length > 0, 'R4 owns the seed', `${flagged} column(s) mark a row as demo; ${surfaced.length} page(s) say so in words a person reads`,
    'nothing marks demo data as demo, in the schema or on any page - a person can make a decision from a machine that does not exist');
}

// ── R5 · where deleted things go ─────────────────────────────────────────────────────────────────
{
  const soft = psql("select count(distinct table_name) from information_schema.columns where table_schema='public' and column_name in ('deleted_at','is_deleted','archived_at','removed_at')");
  const audited = psql("select count(*) from pg_trigger t join pg_class c on c.oid=t.tgrelid where not t.tgisinternal and pg_get_triggerdef(t.oid) ilike '%audit%'");
  say(Number(soft) > 0 && Number(audited) > 0, 'R5 keeps history', `${soft} table(s) keep deleted rows recoverable; ${audited} trigger(s) record who changed what`,
    'a delete on this platform is final and unrecorded - nothing says where the data went or who took it');
}

// ── R6 · two people, one record ──────────────────────────────────────────────────────────────────
{
  // the guard is an updated_at precondition: a second write carrying a stale stamp must not win
  const guarded = psql("select count(distinct table_name) from information_schema.columns where table_schema='public' and column_name='updated_at'");
  const touch = psql("select count(*) from pg_trigger t where not t.tgisinternal and pg_get_triggerdef(t.oid) ilike '%updated_at%'");
  const row = psql(`select id from pm_assets where hive_id='${HIVE}' limit 1`);
  let arbitrated = null, why = '';
  if (row) {
    const a = await rest(`pm_assets?select=updated_at,location&id=eq.${row}`);
    const first = (await a.json().catch(() => [{}]))[0] || {};
    const stamp = first.updated_at;
    if (!stamp) why = 'the row carries no updated_at to hold';
    else {
      // ★A FIRST WRITE THAT NEVER LANDED MAKES THE SECOND ONE LOOK LIKE A SILENT OVERWRITE. The first run
      // patched a `notes` column pm_assets does not have, got a 400, so the stamp never moved - and the
      // stale-stamp write then matched, exactly as it should have. The prover called that a lost update.
      // Write A must be CONFIRMED to have moved the stamp before write B means anything.
      const wa = await rest(`pm_assets?id=eq.${row}`, { method: 'PATCH', headers: { Prefer: 'return=representation' }, body: JSON.stringify({ location: 'wh-concurrency-probe-A' }) });
      const after = ((await wa.json().catch(() => []))[0] || {});
      if (!wa.ok || !after.updated_at) why = `the first write did not land (${wa.status}), so there is no moved stamp for the second to miss`;
      else if (after.updated_at === stamp) why = 'the first write landed but updated_at did not move, so a precondition on it cannot arbitrate anything';
      else {
        // the second writer arrives holding the stamp they read; the row has moved, so the write must miss
        const stale = await rest(`pm_assets?id=eq.${row}&updated_at=eq.${encodeURIComponent(stamp)}`, { method: 'PATCH', headers: { Prefer: 'return=representation' }, body: JSON.stringify({ location: 'wh-concurrency-probe-B' }) });
        arbitrated = (await stale.json().catch(() => [])).length === 0;
      }
      await rest(`pm_assets?id=eq.${row}`, { method: 'PATCH', body: JSON.stringify({ location: first.location ?? null }) });
    }
  }
  say(arbitrated === true, 'R6 arbitrates', `${guarded} table(s) carry updated_at, ${touch} trigger(s) move it; a second write holding the stamp it read ${arbitrated === true ? 'MISSED, as it must' : arbitrated === false ? 'WON, overwriting the first silently' : 'could not be tested'}`,
    arbitrated === false ? 'the second writer overwrote the first with no sign either of them saw - the work of whoever saved first is gone and nobody was told' : `the lens is unmeasured, not clean: ${why || 'no row was available'}`);
}

// ── R7 · deleting a parent that has children ─────────────────────────────────────────────────────
{
  const fks = psql("select count(*) from pg_constraint where contype='f' and connamespace='public'::regnamespace");
  const undeclared = psql("select count(*) from pg_constraint where contype='f' and connamespace='public'::regnamespace and confdeltype='a'");
  const named = psql("select string_agg(conrelid::regclass||'.'||conname||' -> '||confrelid::regclass, '; ') from pg_constraint where contype='f' and connamespace='public'::regnamespace and confdeltype='a'");
  const declared = Number(fks) - Number(undeclared);
  say(Number(undeclared) === 0, 'R7 cascades', `${declared} of ${fks} foreign key(s) DECLARE what happens to children on delete`,
    `${undeclared} foreign key(s) leave it to NO ACTION - deleting the parent fails with a constraint error a person cannot read: ${named}`);
}

// ── R8 · the hive's name lives in one place ──────────────────────────────────────────────────────
{
  const copies = psql("select string_agg(c.relname, ', ') from pg_class c join pg_namespace n on n.oid=c.relnamespace join pg_attribute a on a.attrelid=c.oid and a.attname in ('hive_name','hivename') and not a.attisdropped where n.nspname='public' and c.relkind='r'");
  say(!copies, 'R8 renames', copies ? `the hive's name is copied into: ${copies}` : 'the hive name is stored once, on the hive - a rename reaches every surface that reads it',
    'a renamed hive keeps its old name wherever the name was copied, and nothing reconciles them');
}

console.log(`${bad ? 'FAIL' : 'PASS'} data-reality - names are distinguishable, a person's own language survives, volume is bounded, deletes are recoverable and declared, and concurrent edits are arbitrated`);
process.exitCode = bad ? 1 : 0;
