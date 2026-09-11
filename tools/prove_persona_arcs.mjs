// prove_persona_arcs — the persona journeys (T12, T17, T46, T47, T54, T56, T57, T59, T61), 2026-09-07.
//
// Nine rows about particular people rather than particular features. A worker speaking into a phone with
// oily hands. Someone earning a badge and wanting to know why. A person coming back on day two, and
// another coming back after three months. A skeptic who will not believe a KPI until they can take it
// apart. A graduate who has never done this. Two supervisors sharing one hive. Someone who cares about
// their account's security. A hive that grew past the size its first screen was designed for.
//
//   A1 hands full      speaking works, and when it cannot (no mic, refused permission, a spent quota)
//                      there is a typed path to the same record - a worker with oily hands is not shut
//                      out because a microphone failed (T12)
//   A2 earned, explained  a badge says WHAT it was for. An award with no reason is a participation
//                      trophy, and this platform's workers are engineers (T17)
//   A3 day two         a returning person meets their own context, not a cold start (T46)
//   A4 the skeptic     a headline number can be taken apart: the figure names its source, and the rows
//                      behind it are reachable (T47)
//   A5 the graduate    a person who has never done this can find out how, from inside the product (T54)
//   A6 co-supervisors  two supervisors do not collide: the platform survives one of them leaving, and
//                      neither is a single point of failure (T56)
//   A7 the returner    after three months away, what changed is discoverable rather than silently
//                      assumed (T57)
//   A8 the careful one someone who cares about their account can see and end their own sessions (T59)
//   A9 twenty people   the roster surfaces still work at the size the hive actually reaches (T61)
//
// ★READ AGAINST THE LARGEST REAL HIVE, AND THE PLATFORM'S OWN WORDS. Where a lens needs scale it uses
// Manila Electronics Assembly (8 active members, the biggest here) and SAYS that is the ceiling this
// data can prove - claiming a twenty-person result from an eight-person hive would be inventing one.
//
//   node tools/prove_persona_arcs.mjs
import { execSync } from 'node:child_process';
import { readdirSync, readFileSync } from 'node:fs';

const psql = (sql) => { try { return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim(); } catch { return ''; } };
const read = (f) => { try { return readFileSync(f, 'utf8'); } catch { return ''; } };
const pages = readdirSync('.').filter((f) => f.endsWith('.html'));
const anyPage = (rx) => pages.filter((f) => rx.test(read(f)));

let bad = 0;
const say = (ok, id, line, detail) => {
  if (!ok) bad++;
  console.log(`  ${ok ? 'ok ' : 'BAD'} ${id.padEnd(20)} ${line}`);
  if (!ok && detail) console.log(`        ${detail.slice(0, 158)}`);
};

// ── A1 · a worker whose hands are full ───────────────────────────────────────────────────────────
{
  const vj = read('voice-journal.html');
  const speaks = /SpeechRecognition|webkitSpeechRecognition|MediaRecorder|getUserMedia/i.test(vj);
  // the fallback is the whole point: a mic that fails must not end the journey
  const typed = /<textarea|type a note|type instead|typed/i.test(vj);
  // and each failure must be NAMED, because "not working" sends a person to the wrong fix
  const namesFailures = ['denied', 'not supported', 'no microphone', 'permission', 'limit', 'quota']
    .filter((w) => new RegExp(w, 'i').test(vj)).length;
  const entries = psql("select count(*) from voice_journal_entries");
  say(speaks && typed && namesFailures >= 3, 'A1 hands full',
    `speech capture ${speaks ? 'ships' : 'does NOT'}, a typed path to the same record ${typed ? 'exists' : 'does NOT'}, and ${namesFailures} distinct failure(s) are named in words; ${entries} entry(ies) recorded`,
    !typed ? 'there is no typed fallback, so a refused microphone ends the journey for a worker whose hands are full'
      : `only ${namesFailures} failure cause(s) are named, so "it is not working" sends a person to fix the wrong thing`);
}

// ── A2 · a badge that says what it was for ───────────────────────────────────────────────────────
{
  const defs = psql("select count(*) from achievement_definitions");
  const described = psql("select count(*) from achievement_definitions where coalesce(description, '') <> ''");
  const awarded = psql("select count(*) from worker_achievements");
  // the reason has to reach the person, not just sit in a definitions table
  // ★"33 PAGES SHOW THE REASON" WAS THE WORD "description" IN EVERY META TAG. The reason has to be
  // rendered from the achievement's own description field, on a surface that actually shows badges -
  // matching a word that appears in every page head counts the whole platform and proves nothing.
  const shown = ['achievements.html', 'skillmatrix.html', 'resume.html'].filter((f) => pages.includes(f))
    .filter((f) => { const src = read(f); return /achievement/i.test(src)
      && /\.description|a\.description|def\.description|criteria|earned for|how to earn/i.test(src); });
  say(Number(described || 0) === Number(defs || 0) && Number(defs || 0) > 0 && shown.length > 0, 'A2 earned, explained',
    `${described} of ${defs} achievement(s) carry a description, ${awarded} awarded, and ${shown.length} page(s) show the reason beside the badge`,
    Number(described || 0) < Number(defs || 0) ? `${Number(defs) - Number(described)} badge(s) have no description, so a person earns something and cannot find out what for`
      : 'no page shows why a badge was earned, so the reason exists in the database and never reaches the person');
}

// ── A3 · day two, and A7 · three months later ────────────────────────────────────────────────────
{
  // returning context: the platform must remember where a person was, per account
  const remembers = anyPage(/wh_last_worker|lastseen|last_seen|resume where|welcome back/i);
  // and for a long absence, what changed has to be findable rather than silently assumed
  const whatChanged = anyPage(/what.s new|changelog|since you|new since|release notes|app v/i);
  say(remembers.length > 0 && whatChanged.length > 0, 'A3 day two / A7 return',
    `${remembers.length} page(s) remember where a person was; ${whatChanged.length} can tell them what changed while they were away`,
    remembers.length === 0 ? 'nothing remembers a returning person, so every visit is a cold start'
      : 'nothing tells a person what changed while they were away, so a three-month absence ends in quietly wrong assumptions');
}

// ── A4 · the skeptic takes a number apart ────────────────────────────────────────────────────────
{
  // a headline figure must name its source and be traceable to rows
  const chips = anyPage(/wh-source-chip|data-source-chip|source-chip/i);
  const truthViews = psql("select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relkind='v' and c.relname like 'v\\_%truth'");
  const drillable = anyPage(/show details|view rows|see the entries|drill|breakdown/i);
  say(chips.length > 0 && Number(truthViews || 0) > 0 && drillable.length > 0, 'A4 the skeptic',
    `${chips.length} page(s) stamp a figure with its source, ${truthViews} canonical truth view(s) stand behind them, and ${drillable.length} page(s) let a person open the rows`,
    chips.length === 0 ? 'no figure names where it came from, so a skeptic has nothing to check it against'
      : Number(truthViews || 0) === 0 ? 'there is no canonical view behind the headline numbers, so two surfaces can disagree and both look right'
      : 'a number cannot be opened into the rows behind it, so believing it is a matter of trust rather than inspection');
}

// ── A5 · the graduate who has never done this ────────────────────────────────────────────────────
{
  const learn = readdirSync('.').includes('learn') ? readdirSync('learn').length : 0;
  const reachable = anyPage(/learn\/|learn-link|Learn\b/i);
  const guided = anyPage(/wh-help|how this page works|New to this page/i);
  say(learn > 0 && reachable.length > 0 && guided.length > 20, 'A5 the graduate',
    `${learn} learn article(s), linked from ${reachable.length} page(s), with ${guided.length} page(s) explaining themselves in place`,
    learn === 0 ? 'there is nothing to learn from inside the product, so a graduate is sent to search the web for how to use it'
      : `only ${guided.length} page(s) explain themselves, so most surfaces assume a person already knows`);
}

// ── A6 · two supervisors, one hive ───────────────────────────────────────────────────────────────
{
  const multiSup = psql("select h.name||' ('||count(*)||')' from hive_members m join hives h on h.id = m.hive_id where m.status='active' and m.role='supervisor' group by h.name having count(*) > 1 limit 1");
  // the platform must KNOW when a co-supervisor exists - leaving is safe then, and forcing a hand-over is
  // friction built on a false premise
  const knows = /_coSups|co-?supervisor|also supervise/i.test(read('hive.html'));
  say(knows, 'A6 co-supervisors',
    `${multiSup || 'no hive here has two supervisors'}; hive.html ${knows ? 'checks for a co-supervisor before forcing a hand-over' : 'does NOT check'}`,
    'the platform never checks whether another supervisor remains, so it either forces a needless hand-over or lets the last one leave a hive unmanaged');
}

// ── A8 · the careful person ──────────────────────────────────────────────────────────────────────
{
  // ★A SCRIPT TAG IS NOT A CONTROL. Counting pages that merely LOAD device-fingerprint.js reported 33
  // surfaces "surfacing device or session state" - the file being present says nothing about whether a
  // person can see or end a session. What counts is words a careful person can act on.
  const canSeeSessions = anyPage(/active session|sign out (everywhere|all|other)|other devices|this device|last sign-?in|signed in on/i);
  const timesOut = /idle|inactivity|session-timeout/i.test(read('session-timeout.js'));
  const canLeave = anyPage(/deactivate_my_account|whClearIdentity|sign out/i);
  say(canSeeSessions.length > 0 && timesOut && canLeave.length > 0, 'A8 the careful one',
    `${canSeeSessions.length} page(s) surface device or session state, an idle timeout ${timesOut ? 'ships' : 'does NOT'}, and ${canLeave.length} page(s) offer a way out`,
    'someone who cares about their account cannot see or end their own sessions, so the only security control they have is closing the tab');
}

// ── A9 · the hive at the size it actually reaches ────────────────────────────────────────────────
{
  const biggest = psql("select h.name||'|'||count(*) from hive_members m join hives h on h.id=m.hive_id where m.status='active' group by h.name order by count(*) desc limit 1");
  const [hiveName, n] = (biggest || '|0').split('|');
  // the roster surfaces must page rather than render everything, or twenty people is a wall of cards
  const paged = ['hive.html', 'skillmatrix.html', 'dayplanner.html'].filter((f) => pages.includes(f))
    .filter((f) => /\.range\(|limit\(|Load more|paginat|slice\(0,/i.test(read(f)));
  say(paged.length >= 2, 'A9 twenty people',
    `the largest hive here holds ${n} active member(s) (${hiveName}), so twenty is BEYOND this data - what is asserted instead is that ${paged.length} of 3 roster surface(s) bound what they render rather than drawing everyone`,
    `only ${paged.length} roster surface(s) bound their output, so at twenty people the rest render every member at once`);
}

console.log(`${bad ? 'FAIL' : 'PASS'} persona-arcs - a worker whose hands are full still records, a badge says what it was for, a skeptic can take a number apart, and the roster holds at size`);
process.exitCode = bad ? 1 : 0;
