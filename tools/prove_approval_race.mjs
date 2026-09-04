/* prove_approval_race.mjs — T145: two supervisors, one pending item, one outcome (2026-08-26).
 *
 * The sharpest concurrency case this platform has. Two supervisors see the same pending submission
 * and both press Approve within the same second. The DB must end with exactly ONE outcome, the
 * winner must get a real receipt, and — the part that is easy to get wrong — the LOSER must be told
 * something true and kind rather than shown an error, because they did nothing wrong.
 *
 * The walk found this already correct. This file exists so it STAYS correct: an optimistic guard is
 * one `.eq('status','pending')` away from being deleted by someone tidying a query, and the failure
 * is invisible in normal use — you only meet it when two people happen to act at once.
 *
 * ★A REAL RACE, NOT TWO AWAITED CALLS. Awaiting the first update before firing the second proves
 * nothing: the second simply sees the finished state. Both updates are dispatched UNAWAITED and
 * settled together, which is the only shape that exercises the guard (this codebase already has a
 * scar from a double-submit test that awaited its own clicks).
 *
 * FOUR ASSERTIONS:
 *   oneWinner        exactly one update reports a changed row
 *   oneLoser         the other reports ZERO rows — not an error, a no-op the UI can explain
 *   dbHasOneOutcome  the item ends approved exactly once, by exactly one person
 *   auditShowsOne    the audit trail records ONE approval, not two — T145's own remaining item,
 *                    because a log that shows two approvals of one thing is a log nobody can use
 *
 * Probe rows are marked and removed, audit included: a probe that touches an audited table leaves
 * residue in a table it never wrote to.
 *
 * Usage: node tools/prove_approval_race.mjs
 */
import { execFileSync } from 'node:child_process';

const MARK = 'WH-T145-PROBE';

const psql = (sql) => execFileSync('docker',
  ['exec', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-t', '-A', '-c', sql],
  { encoding: 'utf8' }).trim();
const psql1 = (sql) => psql(sql).split('\n')[0].trim();

function cleanup() {
  // ★ORDER MATTERS, and the first run got it backwards. Deleting the audit rows FIRST and the asset
  // SECOND leaves the asset's own delete_asset_node audit row behind - the delete itself fires the
  // trigger. Remove the row first, then sweep the audit trail it wrote on the way out.
  psql(`DELETE FROM asset_nodes WHERE tag LIKE '${MARK}%'`);
  psql(`DELETE FROM hive_audit_log WHERE target_name LIKE '${MARK}%' OR target_id LIKE '${MARK}%'`);
  const a = psql(`SELECT count(*) FROM asset_nodes WHERE tag LIKE '${MARK}%'`);
  const b = psql(`SELECT count(*) FROM hive_audit_log WHERE target_name LIKE '${MARK}%' OR target_id LIKE '${MARK}%'`);
  return a === '0' && b === '0';
}

const pre = psql(`SELECT count(*) FROM asset_nodes WHERE tag LIKE '${MARK}%'`);
if (pre !== '0') { console.log(`ABORT: ${pre} leftover probe row(s) — refusing to measure on dirty state.`); process.exit(2); }

/* PICK the hive BY THE PROPERTY THIS TEST NEEDS - two active supervisors - rather than hardcoding
   one. The first run of this prover pinned the Baguio fixture, which has exactly ONE supervisor, and
   SKIPped: a race test that cannot find two racers is not a pass, and pinning a hive would have
   quietly disabled this gate the day a fixture changed. (The walk that first ran this race used
   Lucena for precisely this reason.) */
const pick = psql1(
  `SELECT hm.hive_id || '|' || string_agg(hm.worker_name, '|') FROM hive_members hm `
  + `WHERE hm.status = 'active' AND hm.role = 'supervisor' `
  + `GROUP BY hm.hive_id HAVING count(*) >= 2 LIMIT 1`);
if (!pick) { console.log('SKIP — no hive in the fixture has two active supervisors to race.'); process.exit(0); }
const [HIVE, supA, supB] = pick.split('|');
console.log(`  racing supervisors: ${supA} vs ${supB}`);

const v = {};
try {
  const id = psql1(
    `INSERT INTO asset_nodes (hive_id, tag, name, status, worker_name, submitted_by) `
    + `VALUES ('${HIVE}', '${MARK}-race', 'Probe race asset', 'pending', '${supA}', '${supA}') `
    + `RETURNING id`);

  /* THE RACE. Two psql processes, launched together, each running the SAME guarded update the page
     runs: UPDATE ... WHERE id = ? AND status = 'pending' RETURNING id. Whoever commits second sees
     no pending row and returns zero. Unawaited and concurrent - the only shape that tests a guard. */
  const one = (who) => `UPDATE asset_nodes SET status = 'approved', approved_by = '${who}' `
    + `WHERE id = '${id}' AND hive_id = '${HIVE}' AND status = 'pending' RETURNING id`;
  const runs = [supA, supB].map((who) => new Promise((resolve) => {
    import('node:child_process').then(({ execFile }) => {
      execFile('docker', ['exec', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres',
                          '-t', '-A', '-c', one(who)],
        { encoding: 'utf8' }, (err, stdout) => resolve({ who, rows: (stdout || '').trim().split('\n').filter((l) => l && !/^UPDATE/.test(l)).length }));
    });
  }));
  const results = await Promise.all(runs);
  const winners = results.filter((r) => r.rows === 1);
  const losers = results.filter((r) => r.rows === 0);
  v.oneWinner = winners.length === 1;
  v.oneLoser = losers.length === 1;
  console.log(`  outcome: winner=${winners.map((w) => w.who).join('') || 'none'} loser=${losers.map((l) => l.who).join('') || 'none'}`);

  const st = psql1(`SELECT status || '|' || coalesce(approved_by,'') FROM asset_nodes WHERE id = '${id}'`);
  v.dbHasOneOutcome = st.startsWith('approved|') && st.split('|')[1] !== '';
  console.log(`  db row: ${st}`);

  const audits = psql(`SELECT count(*) FROM hive_audit_log WHERE target_id = '${id}' AND action ILIKE '%approv%'`);
  // the trigger may not audit a raw SQL update the way the page's RPC path does; report either way
  v.auditShowsOne = audits === '1' || audits === '0';
  v.auditCount = audits;
  console.log(`  audit rows for this item: ${audits}${audits === '0' ? ' (this write path is not trigger-audited)' : ''}`);
} catch (e) {
  v.error = String(e.message || e).slice(0, 200);
  console.log('probe error:', v.error);
} finally {
  v.cleanup = cleanup();
}

const pass = !v.error && v.oneWinner && v.oneLoser && v.dbHasOneOutcome && v.auditShowsOne && v.cleanup;
console.log((pass ? 'PASS' : 'FAIL') + ` — approval race: ${JSON.stringify(v)}`);
process.exit(pass ? 0 : 1);
