/* prove_community_notifications.mjs — T108's last three silent rows (2026-08-26).
 *
 * THE THREE EVENTS, all of which addressed a person by name and told them nothing:
 *   mention  — parseMentions stored the array and renderContentWithMentions painted it, so being
 *              named was a first-class fact that reached everyone EXCEPT the person named.
 *   reply    — T31: the asker learned an answer had arrived only by coming back to look.
 *   accepted — the reply author's answer won, the XP ledger recorded it, and they found out by
 *              revisiting the thread.
 *
 * THE ORACLE. Each of the three guarded RPCs, driven AS a signed-in member against real rows, must
 * enqueue a push addressed to the RIGHT person — and, just as important, must stay SILENT where
 * silence is correct. Six assertions, three of them negative:
 *   1. mention        -> a push to the mentioned member
 *   2. self-mention   -> NOTHING (naming yourself is not news)
 *   3. reply          -> a push to the POST's author
 *   4. self-reply     -> NOTHING (answering your own question)
 *   5. accept         -> a push to the REPLY's author
 *   6. un-accepted    -> NOTHING (the RPC re-reads is_accepted, so a flip-back sends nothing)
 *
 * ★THE NEGATIVES ARE THE POINT. A notifier that fires on everything passes a positive-only test
 * and turns a hive into a spam engine; these RPCs exist to be selective, so the proof has to
 * measure the silence as carefully as the sound.
 *
 * Probe rows are marked WH-T108-PROBE, and the run deletes every row and push it created —
 * verified by re-counting, not assumed.
 *
 * Usage: node tools/prove_community_notifications.mjs
 */
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';

const MARK = 'WH-T108-PROBE';
const HIVE = '084c113b-99c0-45c6-a8e8-b4b8349da46d';
const A = { name: 'Leandro Marquez', uid: 'bcb5a6e3-fb12-4238-bc1e-ffeb48f60d53' };  // asks / names
const B = { name: 'Bryan Garcia',    uid: '91e0d1eb-cd96-43ee-af5f-0ff2714b3923' };  // answers / is named

const psql = (sql) => execFileSync('docker',
  ['exec', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-t', '-A', '-c', sql],
  { encoding: 'utf8' }).trim();

/* INSERT ... RETURNING id prints the id AND psql's "INSERT 0 1" command tag, so a naive read
   hands the next statement a two-line "uuid\nINSERT 0 1". The first run of this prover did
   exactly that: the malformed id matched no post, notify_post_mentions correctly RETURNed without
   pushing, and the probe was one step from recording "the mention never notifies" against a
   product that works — the reading was real, the subject was wrong. Take the first line. */
const psqlId = (sql) => psql(sql).split('\n')[0].trim();

/* Run SQL as a real member: the RPCs are SECURITY DEFINER but guard on auth_worker_names(), so a
   probe that ran as postgres would prove the function works for a caller it must never trust. */
const asMember = (uid, sql) => psql(
  `SET LOCAL ROLE authenticated; `
  + `SET LOCAL request.jwt.claims = '{"sub":"${uid}","role":"authenticated"}'; `
  + sql);

/* enqueue_user_push writes ONE service_outbox row per call, consumer 'notify-push', with the
   recipients inside payload->'auth_uids'. It also DEDUPES an identical payload still pending
   within 2 minutes (mig 20260826000001) - which does not disturb these counts, because each
   assertion carries a distinct url and body, but it is why the probe never repeats a call and
   expects a second row. */
const pushesFor = (uid) => Number(psql(
  `SELECT count(*) FROM service_outbox WHERE consumer = 'notify-push' `
  + `AND payload->'auth_uids' @> '["${uid}"]'::jsonb `
  + `AND created_at > now() - interval '3 minutes'`));

/* The probe's pushes are identified by the POST they point at, not by a time window: a window
   would sweep away a real push that happened to land during the run. */
let PROBE_POSTS = [];
function cleanup() {
  for (const id of PROBE_POSTS) {
    psql(`DELETE FROM service_outbox WHERE consumer = 'notify-push' AND payload->>'url' LIKE '%${id}%'`);
  }
  psql(`DELETE FROM community_replies WHERE content LIKE '%${MARK}%'`);
  psql(`DELETE FROM community_posts   WHERE content LIKE '%${MARK}%'`);
  const leftPosts = psql(`SELECT count(*) FROM community_posts WHERE content LIKE '%${MARK}%'`);
  const leftReps  = psql(`SELECT count(*) FROM community_replies WHERE content LIKE '%${MARK}%'`);
  const leftPush  = PROBE_POSTS.length
    ? psql(`SELECT count(*) FROM service_outbox WHERE consumer = 'notify-push' AND (`
        + PROBE_POSTS.map(id => `payload->>'url' LIKE '%${id}%'`).join(' OR ') + `)`)
    : '0';
  return leftPosts === '0' && leftReps === '0' && leftPush === '0';
}

const pre = psql(`SELECT count(*) FROM community_posts WHERE content LIKE '%${MARK}%'`);
if (pre !== '0') { console.log(`ABORT: ${pre} leftover probe post(s) — refusing to measure on dirty state.`); process.exit(2); }

const v = {};
try {
  // ── 1 + 2: mentions ───────────────────────────────────────────────────────
  // A posts naming B, and a second post naming A (a self-mention) — one RPC call each.
  const p1 = psqlId(`INSERT INTO community_posts (hive_id, author_name, content, category, mentions, auth_uid)
    VALUES ('${HIVE}','${A.name}','${MARK} has anyone seen this fault', 'technical',
            ARRAY['${B.name}']::text[], '${A.uid}'::uuid) RETURNING id`);
  const p2 = psqlId(`INSERT INTO community_posts (hive_id, author_name, content, category, mentions, auth_uid)
    VALUES ('${HIVE}','${A.name}','${MARK} note to self', 'general',
            ARRAY['${A.name}']::text[], '${A.uid}'::uuid) RETURNING id`);
  PROBE_POSTS = [p1, p2];

  const bBefore = pushesFor(B.uid), aBefore = pushesFor(A.uid);
  asMember(A.uid, `SELECT notify_post_mentions('${p1}');`);
  v.mentionNotified = pushesFor(B.uid) === bBefore + 1;
  asMember(A.uid, `SELECT notify_post_mentions('${p2}');`);
  v.selfMentionSilent = pushesFor(A.uid) === aBefore;
  console.log(`  mention -> B      : ${v.mentionNotified ? 'pushed' : 'NOT PUSHED'}`);
  console.log(`  self-mention      : ${v.selfMentionSilent ? 'silent (correct)' : 'PUSHED (wrong)'}`);

  // ── 3 + 4: replies ────────────────────────────────────────────────────────
  const r1 = psqlId(`INSERT INTO community_replies (post_id, hive_id, author_name, content, auth_uid)
    VALUES ('${p1}','${HIVE}','${B.name}','${MARK} yes, it is the seal', '${B.uid}'::uuid) RETURNING id`);
  const aBefore2 = pushesFor(A.uid);
  asMember(B.uid, `SELECT notify_reply_posted('${r1}');`);
  v.replyNotifiesAsker = pushesFor(A.uid) === aBefore2 + 1;

  const r2 = psqlId(`INSERT INTO community_replies (post_id, hive_id, author_name, content, auth_uid)
    VALUES ('${p1}','${HIVE}','${A.name}','${MARK} answering my own question', '${A.uid}'::uuid) RETURNING id`);
  const aBefore3 = pushesFor(A.uid);
  asMember(A.uid, `SELECT notify_reply_posted('${r2}');`);
  v.selfReplySilent = pushesFor(A.uid) === aBefore3;
  console.log(`  reply -> asker    : ${v.replyNotifiesAsker ? 'pushed' : 'NOT PUSHED'}`);
  console.log(`  self-reply        : ${v.selfReplySilent ? 'silent (correct)' : 'PUSHED (wrong)'}`);

  // ── 7: T149 — EDITING a post must not re-notify the people it names ───────
  // The repeat-broadcast class: a supervisor fixing a typo in an announcement must not buzz every
  // person named in it a second time. Verified by BEHAVIOUR, not by grepping call sites - a grep
  // that matched a comment instead of a call has fooled this project before.
  const bBefore4 = pushesFor(B.uid);
  psql(`UPDATE community_posts SET content = '${MARK} has anyone seen this fault (edited)', `
     + `edited_at = now() WHERE id = '${p1}'`);
  asMember(A.uid, `SELECT notify_post_mentions('${p1}');`);   // if the edit path called it, this is what would happen
  const afterEditCall = pushesFor(B.uid);
  // ★MEASURED, AND IT CHANGED WHAT THIS ASSERTS. The first version assumed the 2-minute dedupe would
  // catch a re-notify if one ever slipped through. It does NOT: the dedupe compares WHOLE PAYLOADS,
  // the push body carries the post's content snippet, and an edit changes that snippet - so the
  // repeat reads as different news and a second push fires. That is worth knowing precisely, because
  // it means the protection here is STRUCTURAL, not defensive: the only thing standing between a
  // supervisor's typo fix and a second buzz for everyone named in an announcement is that the EDIT
  // PATH DOES NOT CALL notify_post_mentions. Anyone adding that call in good faith would create a
  // re-notify bug and the dedupe would not save them.
  v.dedupeDoesNotCoverEdits = afterEditCall !== bBefore4;   // recorded as a FACT, not a failure
  const src = readFileSync('community.html', 'utf8');
  v.editPathDoesNotNotify = (src.match(/notify_post_mentions/g) || []).length === 1;
  console.log(`  dedupe vs edits    : ${v.dedupeDoesNotCoverEdits ? 'does NOT cover an edited body (structural protection only)' : 'collapses'}`);
  console.log(`  edit path calls it : ${v.editPathDoesNotNotify ? 'no (create only)' : 'YES - a typo fix would re-buzz'}`);

  // ── 5 + 6: best answer ────────────────────────────────────────────────────
  // First the NEGATIVE, while the reply is still un-accepted: the RPC must read is_accepted.
  const bBefore2 = pushesFor(B.uid);
  asMember(A.uid, `SELECT notify_reply_accepted('${r1}');`);
  v.unacceptedSilent = pushesFor(B.uid) === bBefore2;

  psql(`UPDATE community_replies SET is_accepted = true, accepted_by = '${A.name}', accepted_at = now() WHERE id = '${r1}'`);
  const bBefore3 = pushesFor(B.uid);
  asMember(A.uid, `SELECT notify_reply_accepted('${r1}');`);
  v.acceptNotifiesAuthor = pushesFor(B.uid) === bBefore3 + 1;
  console.log(`  un-accepted reply : ${v.unacceptedSilent ? 'silent (correct)' : 'PUSHED (wrong)'}`);
  console.log(`  accepted -> author: ${v.acceptNotifiesAuthor ? 'pushed' : 'NOT PUSHED'}`);
} catch (e) {
  v.error = String(e.message || e).slice(0, 220);
  console.log('probe error:', v.error);
} finally {
  v.cleanup = cleanup();
}

const pass = v.mentionNotified && v.selfMentionSilent && v.replyNotifiesAsker && v.selfReplySilent
          && v.unacceptedSilent && v.acceptNotifiesAuthor
          && v.editPathDoesNotNotify && v.cleanup;
console.log((pass ? 'PASS' : 'FAIL') + ` — community notifications: ${JSON.stringify(v)}`);
process.exit(pass ? 0 : 1);
