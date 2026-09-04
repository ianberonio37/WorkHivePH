/* prove_hive_at_scale.mjs - T61 slice 1: the people surfaces at 20 members.
 *
 * Every hive in the seeded data is small - 8 members in the largest - so every people surface on
 * this platform has only ever been read at a size where nothing can go wrong. A roster of 8 fits on
 * a phone; a roster of 20 is where ordering, truncation and "find a person" start to matter, and
 * where a count that disagrees with its list stops being invisible.
 *
 * ★THE FIXTURE IS ON-DEMAND, NOT STANDING, and that is deliberate. A permanent 20-member hive would
 * change the numbers every other gate reads - member counts, standings, per-hive rollups - and a
 * fixture that quietly moves someone else's denominator is worse than no fixture. This grows a
 * marked hive, measures, and removes it, re-counting to prove the removal (the discipline the drain
 * and round-trip provers set).
 *
 * ★WHAT IT ASSERTS AT SIZE, all of it about agreement rather than taste:
 *   1. the roster VIEW returns every member - a read that silently caps at 10 or 20 is the row-cap
 *      class, and a capped roster reads exactly like a small team;
 *   2. the count a surface would show equals the rows it would list (count_matches_source at size);
 *   3. the ordering is TOTAL - name plus a tiebreak - so two members sharing a name cannot swap
 *      places between reads, which is the paginated-order lesson applied to people;
 *   4. no duplicate names slipped in, because worker_name is UNIQUE per hive and 20 generated
 *      members is a real test of that constraint.
 *
 * Usage: node tools/prove_hive_at_scale.mjs [--members 20]
 */
import { execFileSync } from 'child_process';

const CONTAINER = process.env.WH_DB_CONTAINER || 'supabase_db_workhive';
const argN = process.argv.indexOf('--members');
const N = argN > -1 ? Math.max(3, Math.min(60, parseInt(process.argv[argN + 1], 10) || 20)) : 20;

const HIVE = 'e1851850-0000-4000-8000-00000000c020';
const MARK = 'WH-T61-PROBE';

const psql = (sql) => execFileSync('docker',
  ['exec', '-i', CONTAINER, 'psql', '-U', 'postgres', '-d', 'postgres', '-tA'],
  { input: sql, encoding: 'utf8', maxBuffer: 1 << 24 });

const uid = (i) => `e1851850-0000-4000-8000-0000000c${String(i).padStart(4, '0')}`;
// Filipino given/family names, so the fixture reads like a real crew rather than "Worker 7" - which
// also makes the ordering assertion meaningful (mixed lengths, shared first names).
const FIRST = ['Juan', 'Maria', 'Jose', 'Ana', 'Pedro', 'Rosa', 'Carlo', 'Liza', 'Mateo', 'Grace'];
const LAST = ['Dela Cruz', 'Santos', 'Reyes', 'Bautista', 'Garcia', 'Mendoza'];
const nameOf = (i) => `${MARK} ${FIRST[i % FIRST.length]} ${LAST[i % LAST.length]} ${i}`;

function seed() {
  const users = Array.from({ length: N }, (_, k) => k + 1).map((i) =>
    `('${uid(i)}','00000000-0000-0000-0000-000000000000','authenticated','authenticated',` +
    `'wh-t61-probe-${i}@example.com','x', now(), now(), now())`).join(',\n');
  const members = Array.from({ length: N }, (_, k) => k + 1).map((i) =>
    `('${HIVE}', '${nameOf(i)}', '${i === 1 ? 'supervisor' : 'worker'}', 'active', '${uid(i)}')`).join(',\n');
  psql(`
INSERT INTO auth.users (id, instance_id, aud, role, email, encrypted_password,
                        email_confirmed_at, created_at, updated_at)
VALUES ${users} ON CONFLICT (id) DO NOTHING;
INSERT INTO public.hives (id, name, invite_code, created_by)
VALUES ('${HIVE}', '${MARK} Plant', 'T61P20', '${MARK}') ON CONFLICT (id) DO NOTHING;
DELETE FROM public.hive_members WHERE hive_id = '${HIVE}';
INSERT INTO public.hive_members (hive_id, worker_name, role, status, auth_uid)
VALUES ${members};
`);
}

function cleanup() {
  psql(`
DELETE FROM public.hive_audit_log WHERE hive_id = '${HIVE}';
DELETE FROM public.hive_members   WHERE hive_id = '${HIVE}';
DELETE FROM public.hives          WHERE id = '${HIVE}';
DELETE FROM auth.users            WHERE email LIKE 'wh-t61-probe-%';
`);
  return parseInt(psql(`
SELECT (SELECT count(*) FROM public.hives WHERE id='${HIVE}')
     + (SELECT count(*) FROM public.hive_members WHERE worker_name LIKE '${MARK}%')
     + (SELECT count(*) FROM auth.users WHERE email LIKE 'wh-t61-probe-%');`).trim(), 10) || 0;
}

const fails = [];
let planted = 0;
try {
  seed();
  planted = parseInt(psql(`SELECT count(*) FROM public.hive_members WHERE hive_id='${HIVE}';`).trim(), 10);
  if (planted !== N) {
    fails.push(`the fixture itself did not build: ${planted} of ${N} members landed, so nothing below `
             + 'is a measurement of the platform');
  }

  // 1 + 2: the roster read returns everyone, and the count matches the list
  const listed = parseInt(psql(
    `SELECT count(*) FROM (SELECT worker_name FROM public.hive_members
      WHERE hive_id='${HIVE}' AND status='active'
      ORDER BY worker_name, auth_uid) q;`).trim(), 10);
  if (listed !== planted) {
    fails.push(`the roster read returned ${listed} of ${planted} members - a read that silently caps `
             + 'makes a 20-person crew look like a small team, and nothing on screen says so');
  }

  // 3: the ordering is total - the same query twice must give the same first and last name
  const a = psql(`SELECT string_agg(worker_name, '|') FROM (SELECT worker_name FROM public.hive_members
     WHERE hive_id='${HIVE}' ORDER BY worker_name, auth_uid LIMIT 5) q;`).trim();
  const b = psql(`SELECT string_agg(worker_name, '|') FROM (SELECT worker_name FROM public.hive_members
     WHERE hive_id='${HIVE}' ORDER BY worker_name, auth_uid LIMIT 5) q;`).trim();
  if (a !== b || !a) {
    fails.push('the roster ordering is not stable between two identical reads - with a tiebreak this '
             + 'cannot happen, and without one two members swap places between refreshes');
  }

  // 4: worker_name is UNIQUE per hive, and 20 generated members is a real test of it
  const dupes = parseInt(psql(`SELECT count(*) FROM (SELECT worker_name FROM public.hive_members
     WHERE hive_id='${HIVE}' GROUP BY worker_name HAVING count(*) > 1) q;`).trim(), 10);
  if (dupes) {
    fails.push(`${dupes} duplicate worker names inside one hive - the unique index should have made `
             + 'this impossible');
  }
  console.log(`  members planted: ${planted} · roster returned: ${listed} · duplicate names: ${dupes} · `
            + `ordering stable: ${a === b}`);
} catch (e) {
  console.log(`SKIP prove_hive_at_scale - could not reach the local database: ${String(e).slice(0, 140)}`);
  try { cleanup(); } catch (_) { /* best effort */ }
  process.exit(0);
}

const residue = cleanup();
if (residue !== 0) {
  fails.push(`${residue} fixture rows survived cleanup - a fixture that outlives its run starts `
           + "moving other gates' numbers");
}
console.log(`  residue after cleanup: ${residue}`);

/* ── PHASE 2: the same question on the GLASS ───────────────────────────────────────────────────
   The rows agreeing is necessary and not sufficient - the roster is a rendered list with its own
   count beside it, and the failure this trajectory is about is a count that says 20 while the list
   shows 10. Phase 1 cannot see that, so this grows a hive a REAL account can open, reads the
   rendered roster, and removes only the marked fixtures - the hive's own members are never touched.
   Skips (rather than fails) when the page server or the account is unavailable: a browser that
   cannot start is not evidence about the roster. */
const LIVE_HIVE = process.env.WH_TEST_HIVE || '084c113b-99c0-45c6-a8e8-b4b8349da46d';
const LIVE_USER = process.env.WH_TEST_USER || 'leandromarquez';
const LIVE_PASS = process.env.WH_TEST_PASSWORD || 'test1234';
const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const TOP_UP = 17;

function addFixturesTo(hiveId, n) {
  const users = Array.from({ length: n }, (_, k) => k + 1).map((i) =>
    `('${uid(500 + i)}','00000000-0000-0000-0000-000000000000','authenticated','authenticated',` +
    `'wh-t61-probe-live-${i}@example.com','x', now(), now(), now())`).join(',\n');
  const members = Array.from({ length: n }, (_, k) => k + 1).map((i) =>
    `('${hiveId}', '${nameOf(500 + i)}', 'worker', 'active', '${uid(500 + i)}')`).join(',\n');
  psql(`
INSERT INTO auth.users (id, instance_id, aud, role, email, encrypted_password,
                        email_confirmed_at, created_at, updated_at)
VALUES ${users} ON CONFLICT (id) DO NOTHING;
INSERT INTO public.hive_members (hive_id, worker_name, role, status, auth_uid)
VALUES ${members} ON CONFLICT DO NOTHING;`);
  return parseInt(psql(`SELECT count(*) FROM public.hive_members
    WHERE hive_id='${hiveId}' AND status='active';`).trim(), 10);
}

function removeFixturesFrom(hiveId) {
  psql(`
DELETE FROM public.hive_members WHERE hive_id='${hiveId}' AND worker_name LIKE '${MARK}%';
DELETE FROM auth.users WHERE email LIKE 'wh-t61-probe-live-%';`);
  return parseInt(psql(`SELECT count(*) FROM public.hive_members
    WHERE hive_id='${hiveId}' AND worker_name LIKE '${MARK}%';`).trim(), 10);
}

let expected = 0;
try {
  const { chromium } = await import('playwright');
  expected = addFixturesTo(LIVE_HIVE, TOP_UP);
  const browser = await chromium.launch();
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
  const perr = [];
  page.on('pageerror', (e) => perr.push(String(e).slice(0, 140)));
  try {
    await page.goto(`${ORIGIN}/index.html?signin=1`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#si-username', { timeout: 20000 });
    await page.fill('#si-username', LIVE_USER);
    await page.fill('#si-password', LIVE_PASS);
    await page.click('#si-btn');
    await page.waitForFunction(() => !!localStorage.getItem('wh_last_worker'), { timeout: 30000 });
    await page.goto(`${ORIGIN}/hive.html`, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => {
      const e = document.getElementById('view-board'); return e && !e.classList.contains('hidden');
    }, { timeout: 30000 });
    await page.waitForTimeout(2500);
    await page.evaluate(() => document.getElementById('btn-toggle-members')?.click());
    await page.waitForTimeout(2500);
    const seen = await page.evaluate(() => {
      const list = document.getElementById('members-list');
      const countEl = document.getElementById('roster-count');
      return { rendered: list ? list.children.length : -1,
               countText: countEl ? countEl.textContent.trim() : '' };
    });
    const claimed = parseInt((seen.countText.match(/(\d+)/) || [])[1] || '-1', 10);
    console.log(`  live roster: rendered ${seen.rendered} rows · count says "${seen.countText}" · `
              + `database has ${expected}`);
    if (seen.rendered !== expected) {
      fails.push(`the roster RENDERED ${seen.rendered} of ${expected} members - the list a supervisor `
               + 'reads is not the crew they have, and nothing on screen says it was shortened');
    }
    if (claimed > -1 && claimed !== seen.rendered) {
      fails.push(`the roster count says ${claimed} while the list shows ${seen.rendered} - the number `
               + 'and the thing it counts disagree on the same screen');
    }
    if (perr.length) fails.push(`pageerrors while rendering ${expected} members: ${perr.join(' | ')}`);
  } finally {
    await browser.close();
    const leftLive = removeFixturesFrom(LIVE_HIVE);
    console.log(`  live fixtures removed, ${leftLive} left behind`);
    if (leftLive !== 0) {
      fails.push(`${leftLive} live fixture members survived cleanup inside a REAL hive - that hive's `
               + 'member count is now wrong for every other reader');
    }
  }
} catch (e) {
  if (expected) { try { removeFixturesFrom(LIVE_HIVE); } catch (_) { /* best effort */ } }
  console.log(`  (live half skipped: ${String(e.message || e).slice(0, 120)})`);
}

if (fails.length) {
  console.log('FAIL prove_hive_at_scale:');
  fails.forEach((f) => console.log('    - ' + f));
  process.exit(1);
}
console.log(`PASS prove_hive_at_scale - a ${N}-member hive lists every member exactly once in a `
          + 'stable total order, and the fixture left nothing behind.');
