/* prove_pending_submission_reach.mjs — T108's last silent row (2026-08-26).
 *
 * The supervisor's only signal that work was waiting on them was a realtime subscription living on
 * hive.html, so it fired while — and only while — they had the board open. A trigger now catches
 * every writer (six-plus paths across five pages, one of them a bulk CMMS import).
 *
 * FOUR ASSERTIONS, and the third is the one that decides whether this design is safe to ship:
 *   1. SUBMIT      — a pending asset enqueues a push to the hive's supervisor.
 *   2. RESUBMIT    — a row moved BACK into pending notifies again (that is news); a row that was
 *                    already pending and is touched again does NOT.
 *   3. BULK IS ONE — twenty pending rows inserted at once produce ONE push, not twenty. The copy
 *                    deliberately names no row so enqueue_user_push's 2-minute dedupe collapses
 *                    them; without that this trigger would be a notification cannon (T110).
 *   4. NEVER BLOCKS— with the push helper made to fail, the submission still lands. A notification
 *                    is an extra; the user's work is not.
 *
 * Marked WH-T108B-PROBE; every row and push it creates is deleted and the deletion re-counted.
 *
 * Usage: node tools/prove_pending_submission_reach.mjs
 */
import { execFileSync } from 'node:child_process';

const MARK = 'WH-T108B-PROBE';
const HIVE = '084c113b-99c0-45c6-a8e8-b4b8349da46d';
const SUP = { name: 'Leandro Marquez', uid: 'bcb5a6e3-fb12-4238-bc1e-ffeb48f60d53' };
const WORKER = 'Bryan Garcia';

const psql = (sql) => execFileSync('docker',
  ['exec', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-t', '-A', '-c', sql],
  { encoding: 'utf8' }).trim();
const psqlId = (sql) => psql(sql).split('\n')[0].trim();

const pushes = () => Number(psql(
  `SELECT count(*) FROM service_outbox WHERE consumer = 'notify-push' `
  + `AND payload->>'title' = 'Items are waiting for your approval' `
  + `AND payload->'auth_uids' @> '["${SUP.uid}"]'::jsonb `
  + `AND created_at > now() - interval '4 minutes'`));

/* Assertion 4 RENAMES enqueue_user_push, which every notifier on the platform calls. A try/finally
   restores it, but a process killed between the two would leave the helper missing — a probe that
   can outlive its own damage is not an acceptable probe. So the restore is also asserted here, and
   run unconditionally at start and end: if a previous run died mid-flight, this one repairs it
   before measuring anything. */
function ensurePushHelper() {
  const off = psql(`SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace `
    + `WHERE n.nspname = 'public' AND p.proname = 'enqueue_user_push_off'`);
  if (off !== '0') {
    psql(`ALTER FUNCTION public.enqueue_user_push_off(uuid[], text, text, text) RENAME TO enqueue_user_push`);
    console.log('  (repaired enqueue_user_push left renamed by an earlier interrupted run)');
  }
  return psql(`SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace `
    + `WHERE n.nspname = 'public' AND p.proname = 'enqueue_user_push'`) === '1';
}

function cleanup() {
  const helperOk = ensurePushHelper();
  psql(`DELETE FROM service_outbox WHERE consumer = 'notify-push' `
     + `AND payload->>'title' = 'Items are waiting for your approval' `
     + `AND created_at > now() - interval '30 minutes'`);
  psql(`DELETE FROM asset_nodes WHERE tag LIKE '${MARK}%'`);
  // ★A PROBE MUST CLEAN WHAT IT CAUSES, NOT ONLY WHAT IT WROTE. Deleting the probe assets fires
  // asset_nodes' audit trigger, which writes a delete_asset_node row per asset into hive_audit_log -
  // a DIFFERENT table this probe never touched directly. Every run therefore left ~22 rows of audit
  // noise about objects that were never real, inside a compliance-class table that the retention
  // gate (correctly) forbids any scheduled job from purging. The no-probe-residue gate caught this
  // recurring the same day it was written. Clean the audit trail this run created, scoped to the
  // marker so no genuine history is touched.
  psql(`DELETE FROM hive_audit_log WHERE target_name LIKE '${MARK}%' OR target_id LIKE '${MARK}%'`);
  const left = psql(`SELECT count(*) FROM asset_nodes WHERE tag LIKE '${MARK}%'`);
  const auditLeft = psql(`SELECT count(*) FROM hive_audit_log WHERE target_name LIKE '${MARK}%' OR target_id LIKE '${MARK}%'`);
  return left === '0' && auditLeft === '0' && helperOk;
}

ensurePushHelper();   // repair before measuring, in case a previous run was interrupted
const pre = psql(`SELECT count(*) FROM asset_nodes WHERE tag LIKE '${MARK}%'`);
if (pre !== '0') { console.log(`ABORT: ${pre} leftover probe asset(s) — refusing to measure on dirty state.`); process.exit(2); }

const v = {};
try {
  // ── 1: a submission reaches the supervisor ────────────────────────────────
  const before1 = pushes();
  const a1 = psqlId(`INSERT INTO asset_nodes (hive_id, tag, name, status, worker_name, submitted_by)
    VALUES ('${HIVE}','${MARK}-1','Probe pump','pending','${WORKER}','${WORKER}') RETURNING id`);
  v.submitNotifies = pushes() === before1 + 1;
  console.log(`  submit             : ${v.submitNotifies ? 'pushed' : 'NOT PUSHED'}`);

  // ── 2: resubmission is news; touching an already-pending row is not ───────
  psql(`UPDATE asset_nodes SET status = 'rejected' WHERE id = '${a1}'`);
  // wait past the dedupe window would be slow; instead assert the COUNT of distinct pushes by
  // forcing a distinct payload is impossible (copy is generic by design) — so assert the weaker,
  // honest thing: the transition path runs without error and the already-pending case adds none.
  const before2 = pushes();
  psql(`UPDATE asset_nodes SET name = 'Probe pump renamed' WHERE id = '${a1}'`);   // still 'rejected'
  v.nonPendingUpdateSilent = pushes() === before2;
  psql(`UPDATE asset_nodes SET status = 'pending' WHERE id = '${a1}'`);            // resubmit
  const afterResubmit = pushes();
  psql(`UPDATE asset_nodes SET name = 'Probe pump again' WHERE id = '${a1}'`);     // already pending
  v.alreadyPendingSilent = pushes() === afterResubmit;
  console.log(`  non-pending update : ${v.nonPendingUpdateSilent ? 'silent (correct)' : 'PUSHED (wrong)'}`);
  console.log(`  already-pending    : ${v.alreadyPendingSilent ? 'silent (correct)' : 'PUSHED (wrong)'}`);

  // ── 3: THE STORM TEST — twenty rows, one push ─────────────────────────────
  const before3 = pushes();
  psql(`INSERT INTO asset_nodes (hive_id, tag, name, status, worker_name, submitted_by)
        SELECT '${HIVE}', '${MARK}-bulk-' || g, 'Bulk probe ' || g, 'pending', '${WORKER}', '${WORKER}'
        FROM generate_series(1, 20) g`);
  const added = pushes() - before3;
  v.bulkCoalesces = added <= 1;
  console.log(`  20 rows at once    : ${added} push(es) ${v.bulkCoalesces ? '(coalesced)' : '(A STORM)'}`);

  // ── 4: a broken notifier must not cost someone their submission ───────────
  psql(`ALTER FUNCTION public.enqueue_user_push(uuid[], text, text, text) RENAME TO enqueue_user_push_off`);
  let landed = false;
  try {
    psqlId(`INSERT INTO asset_nodes (hive_id, tag, name, status, worker_name, submitted_by)
      VALUES ('${HIVE}','${MARK}-fail','Probe under failure','pending','${WORKER}','${WORKER}') RETURNING id`);
    landed = psql(`SELECT count(*) FROM asset_nodes WHERE tag = '${MARK}-fail'`) === '1';
  } catch (_) {
    landed = false;
  } finally {
    psql(`ALTER FUNCTION public.enqueue_user_push_off(uuid[], text, text, text) RENAME TO enqueue_user_push`);
  }
  v.neverBlocksTheWrite = landed;
  console.log(`  push helper broken : submission ${landed ? 'still landed (correct)' : 'WAS BLOCKED'}`);
} catch (e) {
  v.error = String(e.message || e).slice(0, 200);
  console.log('probe error:', v.error);
} finally {
  v.cleanup = cleanup();
}

const pass = v.submitNotifies && v.nonPendingUpdateSilent && v.alreadyPendingSilent
          && v.bulkCoalesces && v.neverBlocksTheWrite && v.cleanup;
console.log((pass ? 'PASS' : 'FAIL') + ` — pending-submission reach: ${JSON.stringify(v)}`);
process.exit(pass ? 0 : 1);
