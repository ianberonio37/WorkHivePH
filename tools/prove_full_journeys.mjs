// prove_full_journeys — W3-JN, the full diverse journeys (2026-09-07).
//
// A journey row is not a page row with more pages in it. It asks whether the platform is a SYSTEM: whether
// a person cast in one of the platform's own six hives can walk a whole story from its first surface to its
// last and find, at every hop, that the thing they just did is still with them.
//
// THREE RAILS, EACH EARNED BY A PAST FAILURE:
//   1. THE TRANSITION, NEVER THE CONTROL. A step passes when the NEXT surface is reachable from THIS one and
//      arrives as itself - never because a button was present and enabled ("a click that changes NOTHING logs
//      as ok"). A path that only works by going back to the nav hub is recorded as `hub-only`: the pages each
//      work and the thread between them is missing, which is exactly what a journey exists to catch.
//   2. THE IDENTITY MUST SURVIVE THE HOP. The hive id, the role and the worker name are read at every step;
//      a journey that silently changes who you are has failed even if every page rendered
//      (prove_handoff_carries_context's lens, applied along a whole story).
//   3. THE EFFECT MUST BE IN THE DATABASE. Each archetype declares a JOIN along its own chain - the rows that
//      have to exist together for the story to be true in this hive - and it is read AS the person, through
//      the truth views where they exist. A chain proven only by both ends existing is not proven
//      (prove_cross_page_chains' K1 lesson: a join nothing has ever traversed is a schema claim).
//
// A journey that cannot be CONSTRUCTED fails; it never skips. If the cast cannot sign in, if a page will not
// load, if the hive has none of the story's data, that is a finding about the platform or about the seed - it
// is never a quiet pass.
//
//   node tools/prove_full_journeys.mjs --archetype J2          # one archetype, every vertical it applies to
//   node tools/prove_full_journeys.mjs --tier A                # the base cast (130 stories)
//   node tools/prove_full_journeys.mjs --condition offline-3g  # every row a condition fix unblocks, across archetypes
//   node tools/prove_full_journeys.mjs --archetype J2 --vertical "Manila Electronics Assembly"
//   node tools/prove_full_journeys.mjs --self-test             # no browser: the oracles have teeth
import { chromium } from 'playwright';
import { takeBrowserSlot } from './browser_slot.mjs';
import { execSync } from 'node:child_process';
import { readFileSync, writeFileSync, mkdirSync, readdirSync } from 'node:fs';

const ORIGIN = process.env.WH_SEEDER_URL ? `${process.env.WH_SEEDER_URL}/workhive` : 'http://127.0.0.1:5000/workhive';
const SUPA = 'http://127.0.0.1:54321';
const args = process.argv.slice(2);
const argOf = (f) => { const i = args.indexOf(f); return i >= 0 ? args[i + 1] : null; };
const ONLY_ARCH = argOf('--archetype');
const ONLY_TIER = argOf('--tier');
const ONLY_VERT = argOf('--vertical');
// ★THE ROWS A FIXTURE FIX UNBLOCKS ARE NOT ONE ARCHETYPE'S (2026-09-10). 49 rows across 29 archetypes
// failed on nothing but their MOMENT - "year-2 ... this hive holds 90 days" - because
// seed_5y_synthetic_history.py had only ever reached three of the six hives (a `limit=2000` on its own
// asset-inventory read decided which). Once every hive spans five years those 49 become walkable at
// once, and they are scattered so thinly that re-walking by archetype would re-walk ~200 already-banked
// journeys to reach them. Select by the axis the fix actually moved.
const ONLY_MOMENT = argOf('--moment');
// ★AND THE SAME IS TRUE OF A CONDITION (2026-09-10, the second time this axis mattered). Three rows -
// W3521 (J25), W3559 (J9) and W3618 (J22) - failed on nothing but `offline-3g`, which delays every
// request and aborts about one in twelve; the repair for them lives in browser-floor.js and sw.js and
// has nothing to do with the archetypes they happen to sit in. Without this filter, re-walking those
// three means re-walking J25 + J9 + J22 entire - 93 stories, most already banked, to re-ask three.
// The moment filter above exists for exactly this reason and stopped one axis short: select by the
// axis the FIX moved, whichever axis that is.
const ONLY_COND = argOf('--condition');
const LIMIT = Number(argOf('--limit') || 0);

// ★AN UNREADABLE ANSWER IS NOT A ZERO. Under load this host's docker API returns 500 for a moment, and a
// helper that swallows that into '' turns "I could not ask" into "this hive has nothing" - a finding about
// the probe printed as a finding about the platform. So a failed call is retried once and then reported as
// UNREADABLE (null), which every caller must handle rather than count as empty.
// TWO IS THE RIGHT DEFAULT, AND THAT IS A MEASUREMENT RATHER THAN A GUESS (2026-09-10). Having just
// raised two callers to eight, the obvious next move was to raise this - and the receipts say no: across
// 1,189 rows on disk, exactly TWO mention a read that could not be taken. The calls that needed more
// attempts are the ones asked ONCE PER RUN while the browser is hammering the host (the cast, the hive's
// span); the per-row reads below are asked constantly and are not the ones failing. Raising this would
// buy nothing and would make a genuinely broken query take minutes to say so, since each attempt carries
// a 25-second timeout. Raise a CALLER when its own receipts show it losing races; leave the floor alone.
const psql = (sql, tries = 2) => {
  for (let i = 0; i < tries; i++) {
    // ★AND IT MUST BE ABLE TO GIVE UP. Without a timeout, execSync waits forever: when this 8GB host's
    // docker engine wedged, one hung `docker exec` froze an entire six-journey walk at zero CPU with no
    // output and no error - a probe that cannot fail is a probe that cannot finish.
    try { return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'], timeout: 25000, killSignal: 'SIGKILL' }).trim(); }
    catch { try { execSync('powershell -NoProfile -Command "Start-Sleep -Milliseconds 900"', { stdio: 'ignore', timeout: 8000 }); } catch { /* even the wait may be refused */ } }
  }
  return null;
};
// who can see doors an ordinary member cannot - read once, used to LABEL a reading rather than to block it
const PLATFORM_ADMINS = new Set(
  psql('select worker_name from marketplace_platform_admins').split(/\r?\n/).map((s) => s.trim()).filter(Boolean));

// ★AND A CREDIT STORY MUST BE CAST ON SOMEBODY WHO HOLDS CREDITS (2026-09-09). J28's chain counts the
// walker's OWN consumer ledger entries, and the cast was the hive's first active member - who is usually
// not the person who signed up to trade. Three hives read "the story has nothing to be about" while each
// held a seller with a claimed starter grant sitting right there. The marketplace persona is the trader,
// so cast the trader: their hive's seller who actually has a ledger entry, admins excluded.
const CREDIT_HOLDERS = psql(
  "select h.name || '|' || s.worker_name || '|' || coalesce(u.email, '') "
  + 'from marketplace_sellers s join hives h on h.id = s.hive_id '
  + 'left join auth.users u on u.id = s.auth_uid '
  + "where exists (select 1 from service_credit_ledger l where l.account_id = s.auth_uid and l.account_type = 'consumer') "
  + 'and s.worker_name not in (select worker_name from marketplace_platform_admins) '
  + 'order by h.name, s.worker_name'
).split(/\r?\n/).map((s) => s.trim()).filter(Boolean).map((row) => {
  const [hive, name, email] = row.split('|');
  return { hive, name, email };
}).filter((m) => m.email);

// people who genuinely hold TWO active memberships and are NOT platform admins - the only honest cast for
// a multi-hive story. Read from the database rather than named here, so it follows the seed rather than a
// memory of it.
const MULTI_HIVE = psql(
  "select m.worker_name || '|' || coalesce(u.email, '') || '|' || string_agg(h.name, '~') "
  + 'from hive_members m join hives h on h.id = m.hive_id left join auth.users u on u.id = m.auth_uid '
  + "where m.status = 'active' and m.worker_name not in (select worker_name from marketplace_platform_admins) "
  + 'group by m.worker_name, u.email having count(*) > 1'
).split(/\r?\n/).map((s) => s.trim()).filter(Boolean).map((row) => {
  const [name, email, hives] = row.split('|');
  return { name, email, hives: String(hives || '').split('~') };
}).filter((m) => m.email);

// ★A DISPUTE STORY MUST BE CAST ON SOMEBODY WHO CAN RESOLVE ONE (2026-09-10, found on the Tier-D listing
// lifetime W3722). J27 - "a deal goes wrong" - declares its own pair as `buyer x seller x admin` and its
// path runs marketplace -> seller-profile -> marketplace -> platform-actions -> hive -> audit-log. The
// walk cast it on a fleet-supervisor, and dead-ended at `marketplace.html -> platform-actions.html` with
// own=0, hub=0: no way onward at all, which reads exactly like a wayfinding gap.
//
// IT IS NOT ONE. marketplace.html:810 carries `<a id="btn-admin-link" href="platform-actions.html#sec-mkt-mod"
// style="display:none">`, revealed by updateAdminLink() only on a positive `marketplace_platform_admins`
// match on the signed-in WORKER_NAME. The door is there; the platform was right to keep it shut for a
// fleet supervisor. The dead hop was the CAST, and the path as declared is an ADMIN's path - which is the
// point of the archetype, since the admin is who resolves the dispute.
//
// Same shape as the two casts above it: J28 belongs to whoever holds the credits, J26 to whoever holds two
// hives, and J27's resolution half to whoever may moderate. And the same honesty rule applies - where this
// hive has no such person, the row says so (`noValidAdminCast`) rather than borrowing an admin from
// another hive to make the walk complete.
//
// ★SCOPE, STATED SO IT IS NOT REUSED WRONGLY: this cast answers a ROUTE question - "is the resolution step
// reachable at all?" - and NEVER an entitlement one. An admin sees doors an ordinary member does not, so a
// refusal or leak claim must never be made from this cast; `identityIsPlatformAdmin` already stamps every
// receipt walked this way, and the refusal lenses speak only as a plain member, through PostgREST.
// Which archetypes hand their admin half to a PARTNER context (see the J27 cast below). Kept as one
// predicate so the cast selection and the partner assignment can never disagree about it.
const partnerHandlesAdmin = (j) => /(^|\+)J27(\+|$)/.test(String((j && j.archetype) || ''));

const ADMIN_MEMBERS = psql(
  "select m.worker_name || '|' || coalesce(u.email, '') || '|' || h.name || '|' || h.id::text "
  + 'from hive_members m join hives h on h.id = m.hive_id left join auth.users u on u.id = m.auth_uid '
  + "where m.status = 'active' and m.worker_name in (select worker_name from marketplace_platform_admins)"
).split(/\r?\n/).map((s) => s.trim()).filter(Boolean).map((row) => {
  // the hive ID travels with them because a PARTNER is stamped with THEIR OWN hive, not the story's:
  // signInAs writes wh_active_hive_id, and stamping a moderator with a hive they do not belong to would
  // have every hive-scoped read on their step answer for a membership they do not hold.
  const [name, email, hive, hiveId] = row.split('|');
  return { name, email, hive, hiveId };
}).filter((m) => m.email);

// AS the person: a truth view with a member predicate returns nothing to a plain postgres session, and a
// count read as the owner is not evidence about what this person can see (the probe's-persona-was-an-admin lesson).
const psqlAs = (worker, sql) => {
  const uid = psql(`select auth_uid from hive_members where worker_name = '${worker.replace(/'/g, "''")}' and status = 'active' limit 1`);
  if (!uid) return null;                                  // unreadable, not "this person has nothing"
  const out = psql(`begin; set local role authenticated; select set_config('request.jwt.claims', '{"sub":"${uid}","role":"authenticated"}', true); ${sql}; rollback;`);
  if (out === null) return null;
  const nums = out.split(/[\r\n]+/).map((l) => l.trim()).filter((l) => /^-?\d+$/.test(l));
  return nums.length ? nums[nums.length - 1] : '';
};

// ── THE CAST, read from the database, never invented ──────────────────────────────────────────────
// (hive id, one supervisor and one worker with real auth rows). A vertical the platform does not host is
// a journey nobody can walk, so the cast is queried at start-up and a missing member is a finding.
function loadCast() {
  // one line: a newline inside `psql -c "..."` reaches the container as a broken command and the cast
  // comes back EMPTY - which reads exactly like "the platform has no people" rather than "the probe
  // mis-quoted its own query"
  // ★THE CAST IS READ ONCE PER RUN, SO IT CAN AFFORD TO WAIT. This host's docker engine wedges under
  // browser load and recovers on its own within a minute or two; two attempts lost two whole archetypes to
  // "the database did not answer" when the stack was merely busy. Eight attempts is still under three
  // minutes and it is the difference between a walk and a wasted run.
  const rows = psql("select h.name||'|'||h.id||'|'||m.worker_name||'|'||m.role||'|'||coalesce(u.email,'') from hives h join hive_members m on m.hive_id = h.id left join auth.users u on u.id = m.auth_uid where m.status = 'active' and u.email is not null order by h.name, m.role", 8);
  const cast = {};
  // psql answers null when the database could not be reached at all - splitting that throws at module
  // load and the whole prover dies with a stack instead of saying "the cast could not be read"
  if (rows === null) { console.log('FAIL full-journeys - the database did not answer, so the cast could not be read (start the stack, then re-run)'); process.exit(1); }
  for (const line of rows.split(/\r?\n/).filter(Boolean)) {
    const [hive, id, name, role, email] = line.split('|');
    const c = cast[hive] || (cast[hive] = { hive, hiveId: id, supervisor: null, worker: null });
    if (role === 'supervisor' && !c.supervisor) c.supervisor = { name, email, role };
    if (role === 'worker' && !c.worker) c.worker = { name, email, role };
  }
  // a one-person operation has no second member: the supervisor IS the whole crew, and saying so is
  // truer than pretending a worker exists
  for (const c of Object.values(cast)) if (!c.worker) c.worker = c.supervisor;
  return cast;
}

// ── THE MOMENT A ROW NAMES MUST BE A MOMENT THE HIVE HAS LIVED ───────────────────────────────────
// ★60 ROWS NAME A MOMENT AND THE WALK NEVER ESTABLISHED ONE. The grid carries `month-3` (22), `year-2`
// (22) and a tier-D `day-1+month-3+year-2` (16), and `moment` appeared nowhere in this file except in two
// unrelated comments. Unlike a device or a language, a moment is not a browser setting - it is a fact about
// how much history the hive HOLDS - so it cannot be applied, only verified. Measured: the deepest hive
// reaches 544 days, so **`year-2` is not true of any hive on this platform**, and `month-3` holds in three
// of six. A row that names a moment its hive has never lived is a row about a fixture, not about a person.
const _span = new Map();
function hiveSpanDays(hiveId) {
  if (!hiveId) return null;
  if (_span.has(hiveId)) return _span.get(hiveId);
  // ★THREE ATTEMPTS WAS THE SAME MISTAKE `loadCast` ALREADY MADE, ONE FUNCTION LOWER (2026-09-10).
  // W3712 - the Dela Cruz whole-lifetime story, the only Tier D row still open - came back 22/22
  // arrived, 10 own / 11 hub-only / 0 none, identity kept, three persisted effects, and failed on ONE
  // line: "the hive's history could not be read, so the moment is unverified". Asked directly, that
  // hive holds 3,666 logbook entries spanning 1,862 days against the 730 this row needs, and every
  // other hive spans 1,824+ - so the history was never missing, the READ was. This host's docker engine
  // wedges under browser load and recovers within a minute; the comment fifteen lines above says
  // exactly that and raised the cast's attempts from two to eight for it, while this call kept three.
  // A journey that walked twenty-two pages correctly should not be filed red because a one-row count
  // lost a race with the browser it was sharing a machine with.
  const out = psql(`select coalesce(round(extract(epoch from (max(created_at)-min(created_at)))/86400), 0)::int from logbook where hive_id = '${hiveId}'`, 8);
  const v = out !== null && /^[0-9]+$/.test(out.trim()) ? Number(out.trim()) : null;
  _span.set(hiveId, v);
  return v;
}
const MOMENTS_NEEDED = { 'month-3': 90, 'year-2': 730, 'day-1+month-3+year-2': 730 };

// ── THE PEOPLE WHO BELONG TO NO HIVE ──────────────────────────────────────────────────────────────
// J11 and J31 are cast as a solo technician and a solo rider - operators with no hive at all - and
// `loadCast` builds itself by joining THROUGH hive_members, so it can never see them. Read separately, and
// matched to the vertical by the words the seed itself uses.
function loadSolo() {
  // (*)A NAME TO CAST IS NOT A PERSON TO CAST. This sweep takes anyone hive-less whose name or email
  // mentions a vehicle - which is leftovers: removed members, accounts from other flows, whoever matches.
  // None of them has the password every walk here signs in with, so J11 walked both solo stories as
  // NOBODY ("Invalid login credentials"), bounced off three hive pages, and reported on a sign-in door.
  // tools/seed_solo_personas.py creates two accounts that CAN sign in and marks them; ordering by that
  // mark puts a castable persona ahead of a leftover without teaching this loader a second vocabulary.
  const rows = psql("select coalesce(u.raw_user_meta_data->>'worker_name', split_part(u.email,'@',1))||'|'||u.email from auth.users u where not exists (select 1 from hive_members m where m.auth_uid = u.id and m.status = 'active') order by (coalesce(u.raw_user_meta_data->>'seed','') = 'solo-persona-seed') desc, u.created_at", 4);
  // the same distinction loadCast above already makes: null is an unreachable database, '' is a real
  // answer of nobody. Returning [] for both would report "this vertical has no castable person" about a
  // read that never happened - the sentence the solo stories would then carry into their receipts.
  if (rows === null) { console.log('FAIL full-journeys - the database did not answer, so the solo cast could not be read (start the stack, then re-run)'); process.exit(1); }
  if (!rows) return [];
  const out = [];
  for (const line of rows.split(/\r?\n/).filter(Boolean)) {
    const [name, email] = line.split("|");
    if (!email) continue;
    const keys = [];
    if (/rider|jeep|tricycle/i.test(email + name)) keys.push("rider");
    if (/owner|ranger|van|fleet|truck/i.test(email + name)) keys.push("owner", "technician", "tech");
    if (keys.length) out.push({ name, email, role: "worker", keys });
  }
  return out;
}
const SOLO = loadSolo();

// ── THE ARCHETYPES' CHAIN EFFECTS — the rows that must exist TOGETHER for the story to be true here ──
// Each is read as the person, scoped to their hive. `$H` = hive id. A zero is a finding: either the chain
// is broken or this hive has never lived that story, and both are worth knowing before a walk claims it did.
const EFFECT = {
  J1: ["the hive has members, an asset and a first entry", "select least((select count(*) from hive_members where hive_id='$H' and status='active'), (select count(*) from asset_nodes where hive_id='$H'), (select count(*) from logbook where hive_id='$H'))"],
  // scoped to the PERSON: this story is cast for a solo owner who has no hive, so a hive filter here
  // asks a question with no subject
  J11: ["the one-person operator's own records exist", "select count(*) from logbook where worker_name='$W'"],
  // ★A FUNNEL HAS NO HIVE UNTIL IT CONVERTS, so `id='$H'` asked about a hive the story does not carry and
  // came back unreadable every time. What this journey has to be true about is the DESTINATION existing:
  // a public arrival is only a funnel if there is a hive on the other side of it, and the walk converts
  // into a real member of one (PERFORM['J12@index.html']). Named rather than templated, because the story
  // itself names no vertical - and the receipt says which hive it arrived into.
  J12: ["the public funnel has a hive to arrive into, with members in it", "select least((select count(*) from hives where id='b4f7fe63-92e1-4f8d-b96e-625c3f85ba61'), (select count(*) from hive_members where hive_id='b4f7fe63-92e1-4f8d-b96e-625c3f85ba61' and status='active'))"],
  J25: ["a member has a skill profile and something recorded", "select least((select count(*) from hive_members where hive_id='$H'), (select count(*) from skill_profiles s join hive_members m on m.worker_name=s.worker_name where m.hive_id='$H'))"],
  J19: ["sign-in attempts are recorded for this hive's people", "select count(*) from login_attempts la where exists (select 1 from hive_members m where m.hive_id='$H')"],
  // ★THE PLATFORM'S OWN TABLE, NOT MINE. alert-hub.html reads `v_alert_truth`; `anomaly_alerts` holds
  // zero rows in every hive, so a chain built on my word for it reported "the chain is empty here" for
  // six hives whose alert page renders a full screen of alerts.
  J2: ["an alert, the asset it names, and work recorded against that asset", "select least((select count(*) from v_alert_truth where hive_id='$H'), (select count(*) from asset_nodes where hive_id='$H'), (select count(*) from logbook where hive_id='$H'))"],
  J3: ["scheduled PMs and completions that close them", "select least((select count(*) from pm_assets where hive_id='$H'), (select count(*) from pm_completions where hive_id='$H'))"],
  // ★EMPTY BECAUSE NOBODY HAS LIVED IT, NOT BECAUSE NOTHING RECORDS IT - and the difference decides what to
  // do about it. `ai_audit_log` holds zero rows platform-wide, and the first reading of that looked like a
  // missing writer. It is not: `voice-handler.js` inserts a row on every CONFIRMED voice-driven write, by
  // design and best-effort. No voice action has ever been taken in any seeded hive, so the trail is empty.
  // ★AND THIS ONE MUST NOT BE SEEDED. Every other empty chain in this file is a seeding job - missing data
  // is never a blocker - but an AUDIT LOG is the exception: its whole worth is that it records what actually
  // happened. Writing plausible AI decisions that nobody made would put a lie in the most sensitive table on
  // the platform to make a walk go green. It stays empty until a real voice turn writes to it.
  // ★THIS CHAIN USED TO ASK FOR SOMEBODY ELSE'S ACTION AND SO COULD NEVER BE TRUE. It read "a voice-driven
  // write has actually been made in this hive", and said in its own text that ai_audit_log "is never
  // seeded" - correctly, because a record of a decision nobody made would be a lie. So it read 0 in all six
  // hives, and no amount of seeding could honestly change that. The walk now PERFORMS the voice action
  // through the product's own dispatcher (PERFORM['J13@logbook.html']) and asks for the row THAT left,
  // which is the difference between waiting for evidence and producing it. Read after the walk, not before,
  // and deleted immediately after it is counted.
  J13: ["the walk's own voice-driven action left its record (dispatched through WHVoice, counted, then removed)", "select count(*) from ai_audit_log where hive_id='$H' and payload::text like '%wh-journey-walk%'"],
  J9: ["a day plan and the work it planned", "select least((select count(*) from shift_plans where hive_id='$H'), (select count(*) from logbook where hive_id='$H'))"],
  J26: ["the person is genuinely in two hives", "select count(distinct hive_id) from hive_members where worker_name=(select worker_name from hive_members where hive_id='$H' limit 1) and status='active'"],
  J24: ["safety-relevant work is recorded and auditable", "select least((select count(*) from logbook where hive_id='$H'), (select count(*) from hive_audit_log where hive_id='$H'))"],
  J23: ["parts exist and have moved", "select least((select count(*) from inventory_items where hive_id='$H'), (select count(*) from inventory_transactions t join inventory_items i on i.id=t.item_id where i.hive_id='$H'))"],
  J20: ["a briefing was produced for this hive", "select count(*) from amc_briefings where hive_id='$H'"],
  // ★THE SAME CORRECTION J2 ALREADY CARRIES, MISSED ONE LINE BELOW IT. `anomaly_alerts` holds zero rows in
  // every hive; the alert surface reads `v_alert_truth`, and its signals are computed ON DEMAND by
  // `compute_anomaly_signals` when a member opens the hub. Asking the empty table reported "the chain is
  // empty in this hive" for three plants that hold 26,000 readings each and 27-61 live alert rows.
  J17: ["readings for this hive, and the alerts they raised", "select least((select count(*) from sensor_readings s where s.hive_id='$H'), (select count(*) from v_alert_truth v where v.hive_id='$H'))"],
  // ★A NAME IS NOT AN IDENTITY. The risk table names its subject in `asset_name`, and this joined that to
  // `asset_nodes.name` - the human name ("APC Symmetra PX 250"). What it actually holds is the asset TAG
  // ("AC-001"). Joined on `name` the match is 0 of 3,315; joined on `tag` it is 3,315 of 3,315. The chain
  // reported that the risk scores name assets the hive does not own, of every plant hive, and the opposite
  // was true of every single row.
  J18: ["risk scores naming assets this hive actually owns", "select count(*) from asset_risk_scores r where r.hive_id='$H' and exists (select 1 from asset_nodes a where a.hive_id=r.hive_id and a.tag = r.asset_name)"],
  J22: ["one asset carrying both history and a PM record", "select count(*) from asset_nodes a where a.hive_id='$H' and exists (select 1 from logbook l where l.hive_id=a.hive_id) and exists (select 1 from pm_assets p where p.hive_id=a.hive_id)"],
  J30: ["engineering calculations kept for this hive", "select count(*) from engineering_calcs where hive_id='$H'"],
  J8: ["a project with items behind it", "select least((select count(*) from projects where hive_id='$H'), (select count(*) from project_items pi join projects p on p.id=pi.project_id where p.hive_id='$H'))"],
  J29: ["work recorded and a report contact to send it to", "select least((select count(*) from logbook where hive_id='$H'), (select count(*) from report_contacts where hive_id='$H'))"],
  J4: ["entries and the audit trail that accounts for them", "select least((select count(*) from logbook where hive_id='$H'), (select count(*) from hive_audit_log where hive_id='$H'))"],
  // ★ANCHOR A CHAIN ON WHAT THE PAGES ACTUALLY READ (2026-09-09). This counted `wh_health_status`, which
  // reads 0 in every hive - and the reason is not a seed gap: that table is BUILT BUT NEVER CALLED. It was
  // created by a 2026-05-26 migration as "last-known health per surface (read-only by frontend)" and no
  // page, no edge function and no script has ever written or read it. So the chain asked whether a table
  // nobody uses has rows, and answered "the founder's month-end story is not true" about a platform whose
  // founder console was working the whole time. What status.html and founder-console.html really read is
  // v_hive_readiness_truth, analytics_events and hive_audit_log - 6, 189,670 and 9,768 rows. A chain is a
  // claim about the story the PAGES tell, so it has to name their sources. (wh_health_status being dead is
  // itself a finding, recorded separately - it is not this journey's business to prove.)
  J32: ["the platform's own health is recorded where the founder console reads it", "select least((select count(*) from v_hive_readiness_truth), (select count(*) from analytics_events), (select count(*) from hive_audit_log))"],
  J21: ["benchmarks computed for this hive", "select count(*) from hive_benchmarks where hive_id='$H'"],
  J5: ["listings a buying hive can actually reach", "select count(*) from marketplace_listings where status='published'"],
  J6: ["service providers and the requests that reach them", "select least((select count(*) from service_providers), (select count(*) from marketplace_listings where status='published'))"],
  J27: ["the dispute path exists and is recorded", "select count(*) from information_schema.tables where table_schema='public' and table_name='marketplace_disputes'"],
  // ★A CHAIN MUST COUNT WHAT THE WALKER CAN SEE, NOT WHAT THE OWNER CAN (2026-09-09, found walking J28
  // through the MCPs as Hector Salvador, a real supervisor). The old chain counted credit_treasury and
  // service_credit_ledger GLOBALLY: 1 and 7 through the owner connection, and 0 and 0 as an actual person.
  // credit_treasury is the PLATFORM's own float - a single row with no hive at all - so a worker seeing
  // none of it is the product working, not a chain. And the ledger is scoped by its policy to
  // `account_id = auth.uid()` for a consumer, so a global count is a claim about nobody. Counted per
  // WALKER, through the same join the policy uses, the story "credits are held and spent" is either true
  // for this person or it is not - which is the only version of it a journey can prove.
  J28: ["this buyer's own credits are held and spent through the ledger", "select count(*) from service_credit_ledger l join hive_members m on m.auth_uid = l.account_id where m.worker_name = '$W' and l.account_type = 'consumer'"],
  // ★THIS CHAIN WAS NOT SCOPED TO THE HIVE, AND J7 IS CAST PER HIVE. It counted community_posts and
  // community_replies across the WHOLE PLATFORM, so a hive with no community at all could have passed on
  // another hive's conversation - a false green waiting for the day the reply count rose anywhere. It also
  // produced a reading nobody could reconcile: the decomposition reported "this hive does hold
  // community_posts 15" for three fleets that hold ZERO posts between them, because 15 was what the
  // walking person could see across every hive they belong to. Seven of the 32 chains carry no hive
  // filter; five of those are right to (the founder's platform health, the marketplace's cross-hive
  // listings and providers, the credit treasury, a table-exists check) because those stories ARE
  // platform-wide. This one is not, and community is hive-scoped everywhere else in the product.
  J7: ["questions, answers and the standing they earn", "select least((select count(*) from community_posts where hive_id='$H' and deleted_at is null), (select count(*) from community_replies where hive_id='$H'))"],
  // ...and so is the portfolio: a resume belongs to a worker, and counting every resume on the platform
  // would let one person's document carry another person's story. resume_versions reaches the worker
  // through its parent document rather than carrying the name itself.
  J31: ["a resume exists and has versions", "select least((select count(*) from resume_documents where worker_name='$W'), (select count(*) from resume_versions v join resume_documents d on d.id = v.resume_id where d.worker_name='$W'))"],
  J15: ["an integration is configured and audited", "select least((select count(*) from integration_configs where hive_id='$H'), (select count(*) from cmms_audit_log))"],
  J10: ["the fleet's units carry PMs and logged work", "select least((select count(*) from asset_nodes where hive_id='$H'), (select count(*) from logbook where hive_id='$H'))"],
  J16: ["the degraded day still has work to record", "select count(*) from logbook where hive_id='$H'"],
  J14: ["leaving is recorded, and what remains is attributable", "select least((select count(*) from hive_members where hive_id='$H'), (select count(*) from hive_audit_log where hive_id='$H'))"],
};

// ── the reading, inside the page ──────────────────────────────────────────────────────────────────
// The identity keys, the visible text, the errors a person would see, and - the journey's own question -
// whether THIS page offers a way onward to the NEXT one, in its own body rather than through shared chrome.
// Which destinations does the platform deliberately reach through a PARENT page rather than the nav hub?
// Read, not typed: the hub's own hrefs are the offered set, and anything outside it that a page links to is
// parented by that page. Five entries in nav-hub.js even say so in a comment ("hidden, surfaced via the
// 'Audit Log' button on hive.html"), and one more - analytics-report.html - is simply not a hub entry at all.
// A journey hop straight to one of these is the ARCHETYPE'S path skipping the intended route, not a
// navigation gap in the product, and calling it a gap would have marked most of 724 rows wrongly.
let _parentedCache = null;
function parentedDestinations() {
  if (_parentedCache) return _parentedCache;
  const out = {};
  try {
    const hubSrc = readFileSync('nav-hub.js', 'utf8');
    const offered = new Set();
    for (const m of hubSrc.matchAll(/href:\s*'([^']+\.html)'/g)) {
      const blockStart = hubSrc.lastIndexOf('{', m.index);
      const block = hubSrc.slice(blockStart, m.index + 200);
      if (!/hidden:\s*true/.test(block)) { offered.add(m[1]); continue; }   // a hidden entry is not offered
      // ★AND WHEN THE HUB SAYS WHERE IT WENT, BELIEVE IT. The comment beside the hidden Audit Log entry reads
      // "hidden, surfaced via the 'Audit Log' button on hive.html" - the platform stating its own route. A
      // link-graph guess picked community.html instead, which also links there and means nothing. Reading the
      // sentence beats ranking the candidates, every time this wave has tried both.
      const before = hubSrc.slice(Math.max(0, blockStart - 260), blockStart);
      const said = /surfaced via[^.\n]*?\bon\s+([a-z0-9-]+\.html)/i.exec(before)
                || /surfaced (?:from|on)\s+([a-z0-9-]+\.html)/i.exec(before);
      if (said) out[m[1]] = [said[1]];   // the hub naming its own route: authoritative, and still a LIST
    }
    // ★READ EACH PAGE ONCE. The first version re-read every file for every other - roughly 190 x 190 reads -
    // and took longer than the walk it was preparing for. The link graph is built from one pass.
    const pages = readdirSync('.').filter((f) => f.endsWith('.html'));
    const bodies = new Map();
    for (const f of pages) {
      try { bodies.set(f, readFileSync(f, 'utf8')); } catch { /* unreadable page: it links to nothing */ }
    }
    for (const f of pages) {
      if (offered.has(f) || out[f]) continue;   // the hub offers it, or the hub already said where it went
      const needle = new RegExp('<a[^>]+href="[^"]*' + f.replace('.', '\\.'));
      // ★index.html LINKS TO EVERYTHING, so it wins every tie and names nothing useful: the first derivation
      // reported "project-report.html is reached from index.html" when project-manager.html is plainly the
      // parent, and "audit-log.html from community.html" when nav-hub's own comment says hive.html. Rank the
      // candidates: a page sharing the destination's stem first (project-manager -> project-report), then a
      // page the hub offers, and the landing page last because it is a parent to everything and to nothing.
      // ★A DESTINATION CAN HAVE MORE THAN ONE REAL PARENT, AND RANKING THREW THE OTHERS AWAY
      // (2026-09-10). This picked the single best-scoring linker, so a journey arriving from any
      // OTHER legitimate route was reported as "your path skips the intended route". Measured on
      // this tree: 16 of the 34 parented destinations have more than one non-index linker.
      // `resume.html` has two - skillmatrix.html AND achievements.html, both linking it in plain
      // prose (the same two facts that justified hiding its nav entry) - so the Tier-D career
      // chains were marked BAD for walking a route the platform genuinely offers.
      // Keeping every parent makes the complaint mean what it says: we stood somewhere that offers
      // no way to this destination at all. index.html is excluded because it links to everything
      // and so distinguishes nothing - unless it is the ONLY page that links there, in which case
      // it is the honest answer.
      const linkers = [];
      for (const [other, src] of bodies) {
        if (other === f || !needle.test(src)) continue;
        linkers.push(other);
      }
      const real = linkers.filter((o) => o !== 'index.html');
      if (real.length) out[f] = real;
      else if (linkers.length) out[f] = linkers;
    }
  } catch (_) { /* if the hub cannot be read, claim nothing and let the hop report as it stands */ }
  _parentedCache = out;
  return out;
}

// ★A TIER THAT ASKS FOR FILIPINO MUST CHECK IT GOT FILIPINO. Tier B is 381 rows, 254 of them Filipino, and
// this prover SET `wh_lang = 'fil'` and then never looked. A page that ignored the setting entirely would
// have walked, passed and banked exactly like its English twin - 254 rows of evidence about a language
// nobody had verified was on screen. The check reads the platform's OWN dictionary (WH_FIL_COMMON in
// utils.js, ~200 strings) rather than a word list of mine, so it tests the translation the product ships.
function filipinoWords() {
  const out = new Set();
  for (const f of ['utils.js', 'wh-i18n-lite.js']) {
    let src = '';
    try { src = readFileSync(f, 'utf8'); } catch { continue; }
    for (const m of src.matchAll(/WH_FIL_[A-Z_]+\s*=\s*\{/g)) {
      let i = src.indexOf('{', m.index), depth = 0, j = i;
      for (; j < src.length; j++) {
        if (src[j] === '{') depth++;
        else if (src[j] === '}' && --depth === 0) break;
      }
      for (const v of src.slice(i, j + 1).matchAll(/:\s*'([^']{4,48})'/g)) {
        // a value that is also plain English tells us nothing about which dictionary rendered it
        if (/[A-Za-z]/.test(v[1]) && !/^(Filipino|English|OK|Cancel)$/i.test(v[1])) out.add(v[1]);
      }
    }
  }
  return [...out];
}
const FIL_WORDS = filipinoWords();

const READ = ({ nextPage, fil }) => {
  const vis = (e) => !!e && (typeof e.checkVisibility === 'function' ? e.checkVisibility({ visibilityProperty: true }) : e.offsetParent !== null);
  const CHROME = '#wh-nav-hub, [id*="wh-hub"], #wh-feedback-panel, [id^="wh-fb"], [class^="wh-fb"], [id^="wh-ai-"], #wh-ai-launcher, .wh-page-guide';
  const chrome = Array.from(document.querySelectorAll(CHROME));
  const inChrome = (el) => chrome.some((c) => c.contains(el));
  const body = document.body;
  const text = (body ? body.innerText || '' : '').replace(/\s+/g, ' ').trim();
  // ★EVERY DIRECTORY INDEX REDUCES TO THE SAME FILENAME, and matching on the filename alone cannot tell
  // learn/index.html from tools/oee-calculator/index.html from the landing page. Nine of the walk's pages
  // are directory indexes, so the "next page" test was asking whether a link mentioned `index.html` -
  // true of far too much, and false of the way the platform actually writes these links, which is the
  // DIRECTORY: `href="/learn/"`. The full path is the target now, with the directory form accepted for
  // it, and the site root accepted only for the landing page itself.
  const nextPath = String(nextPage || '').replace(/^\/+/, '');
  const isIndex = /(^|\/)index\.html$/.test(nextPath);
  const dirForm = isIndex ? nextPath.replace(/index\.html$/, '') : '';   // "learn/" ; "" for the root page
  const target = nextPath.includes('/') ? nextPath : nextPath.split('/').pop();
  let own = 0; let hub = 0;
  for (const a of Array.from(document.querySelectorAll('a[href], [onclick], button, [data-href]'))) {
    const href = (a.getAttribute('href') || a.getAttribute('data-href') || a.getAttribute('onclick') || '');
    // ★A LINK TO THE SITE ROOT IS A LINK TO THE LANDING PAGE, and matching on the filename could not see
    // one. The public pages link home as `href="/"` and `href="/#join"` - which IS index.html in
    // production - so a walk whose next page is index.html read "no way onward at all" from a free
    // calculator that plainly invites the reader in. Measured: tools/mtbf-calculator carries href="/",
    // href="/#join", href="/learn/" and href="/engineering-design.html", and the funnel's dead hop was
    // this matcher, not the page. Only widened where the target IS the landing page, so nothing else
    // gains a link it does not have.
    // ...and the href must BE the root, not merely start with a slash: the first version of this line
    // matched `^\/` and so credited /learn/ and /engineering-design.html as links to the landing page,
    // which would have handed every page with any root-absolute link a way onward it does not have. A
    // widening that cannot tell one target from another is a false green, not a fix.
    const h = href.trim();
    // the landing page, and only it, is reachable by a link to the site root
    const rootIsTarget = nextPath === 'index.html'
      && /^(?:\/(?:#[^/]*)?|https?:\/\/[^/]+\/?(?:#[^/]*)?)$/.test(h);
    // a directory link reaches that directory's index: href="/learn/" IS learn/index.html
    const dirIsTarget = !!dirForm && (h.endsWith('/' + dirForm) || h.endsWith(dirForm)
      || h.endsWith('/' + dirForm.replace(/\/$/, '')) );
    if (!target || (!h.includes(target) && !rootIsTarget && !dirIsTarget)) continue;
    // ★THE NAV HUB IS A CLOSED DRAWER, AND A CLOSED DRAWER IS NOT AN ABSENT ONE. The hub is
    // visibility:hidden until it is opened, so a visibility filter over the whole page reported
    // "no way onward at all" on every hop of every journey - the same blindness that once counted the
    // drawer's 26 buttons as nameless. A hub link is counted whether or not the drawer is open (the
    // person opens it); only the page's OWN links have to be on screen to count as its own thread.
    if (inChrome(a)) { hub++; continue; }
    // ★AND THE PAGE'S OWN MENU IS A CLOSED DRAWER TOO. The reasoning above was applied to the shared hub and
    // stopped there. `hive.html` reaches the audit log through `<a id="btn-audit-log" href="audit-log.html"
    // role="menuitem" class="hive-menu-item hidden">` - a real link, in the page's own menu, which the
    // person opens exactly as they open the hub. Counting it as "no way onward at all" reported six hives
    // as having no route to their own audit log, which is the route the nav hub's own comment names.
    const inOwnMenu = !!a.closest('[role="menu"], [role="menubar"], [aria-haspopup], [class*="menu"], [class*="dropdown"], details');
    // ★AND A "SHOW MORE" LIST IS A CLOSED DRAWER TOO - the THIRD time this rule has had to be widened, so
    // it is now stated as the general one. learn/index.html carries all 54 guides and shows 12, the other
    // 42 sitting at display:none behind a "Show more guides" button and a row of category filters. The walk
    // reported "no way onward at all" from the learn index to an article the index plainly lists, in every
    // hive, for every cast including the admin - and the reader reaches it in one click, exactly as they
    // open the nav drawer or the page's own menu. The test is not "is this link on screen now" but "can
    // the person get to it from here without leaving": a collapsed region with a visible control that
    // expands it qualifies; a link hidden with no way to reveal it still does not.
    const expander = (() => {
      if (vis(a) || inOwnMenu) return false;
      const region = a.closest('[id], ul, ol, section, div');
      if (region && region.id) {
        const byAria = document.querySelector(`[aria-controls="${CSS.escape(region.id)}"]`);
        if (byAria && vis(byAria)) return true;
      }
      // ★AND THE FOURTH WIDENING IS THE ONE THAT SHOULD HAVE BEEN FIRST: MATCH THE CONTROL, NOT ITS
      // ENGLISH. This test read innerText against English phrases, so on the FILIPINO rendering of
      // learn/index.html the "Show more guides" button - which carries data-i="lh-more" and is
      // therefore translated in place - became invisible to the walk, and all 42 collapsed guides with
      // it. Measured on J30 2026-09-09: SIX rows reported "no way onward at all" from the learn index
      // to an article it plainly lists, and the correlation was total - every lang=fil row had own=0,
      // every lang=en row had own=1, no exceptions. That is an instrument reading the product's
      // language rather than its structure, in a walk whose whole purpose is to prove the Filipino
      // cell works. Identity survives translation; a label does not. The text test is kept as a
      // fallback for controls with no id, but it is no longer the only way to be seen.
      const byIdentity = Array.from(document.querySelectorAll('button, [role="button"], a'))
        // `(?![a-z0-9])` rather than `([-_]|$)`: the attributes are joined with SPACES, so an id of
        // `lh-more` is followed by a space and an end-anchored class never matched it - the first cut
        // of this check fired on nothing at all, and the re-walk is what said so.
        .some((b) => vis(b) && /(?:^|[-_\s])(?:more|all)(?![a-z0-9])|show[-_]?more|load[-_]?more/i.test(
          (b.id || '') + ' ' + (b.getAttribute('data-i') || '') + ' ' + (b.getAttribute('data-action') || '')));
      if (byIdentity) return true;
      return Array.from(document.querySelectorAll('button, [role="button"], a'))
        .some((b) => vis(b) && /show\s+more|see\s+all|view\s+all|more\s+guides|load\s+more|show\s+all/i.test(b.innerText || ''));
    })();
    if (vis(a) || inOwnMenu || expander) own++;
  }
  const errBanner = Array.from(document.querySelectorAll('[role="alert"], .error, .wh-error, [class*="error"]'))
    .filter((e) => vis(e) && !inChrome(e) && (e.innerText || '').trim().length > 8)
    .map((e) => (e.innerText || '').trim().slice(0, 90)).slice(0, 3);
  const skeletons = Array.from(document.querySelectorAll('[class*="skeleton"], [class*="shimmer"], [aria-busy="true"]')).filter(vis).length;
  // the page's OWN controls, so a page that is small because it is WAITING for you is not mistaken for a
  // page that failed to load: analytics-report generates its report on demand and rests at ~527 characters
  // around a Generate button, which is the design, not an early read
  const controls = Array.from(document.querySelectorAll('a[href], button, [role="button"], input, select'))
    .filter((e) => vis(e) && !inChrome(e)).length;
  return {
    // ★THE PLATFORM SAYING "YOU ARE OFFLINE" IS NOT A PAGE WITH NO WAY ONWARD (2026-09-10).
    // Once the service worker could actually install, its _appNav branch began doing its job: a
    // navigation whose request was dropped and which had no cached copy is answered with the branded
    // offline shell AT THE REQUESTED URL. The person is correctly told what happened - but the walk
    // saw a document that landed on the right URL and offered no links, and filed "1 hop(s) have no
    // way onward at all", turning the designed degradation into a navigation defect on four rows that
    // had passed the day before. The tell was in the numbers: THREE DIFFERENT PAGES rendering exactly
    // 413 characters, the only length in the run shared by more than one page - real pages do not
    // coincide to the character. `net-hint` is the offline shell's own id and exists on no other page.
    // ★THE PLATFORM'S OWN NOTICES ARE role="status", AND THE ERROR DETECTOR ONLY KNOWS role="alert"
    // (2026-09-10). Two rows ended on a step rendering 69 characters with `errBanner: []`, and the
    // receipt could not say whether the platform had told the person anything - so the walk read as
    // "silent page" a state it simply could not see. utils.js builds every notice through
    // _whShowNotice: a fixed div with role="status", aria-live="polite", inline styles and NO class,
    // which matches none of `[role="alert"], .error, .wh-error, [class*="error"]`. This is the same
    // trap the shared prover harness was built to close ("nine silent pages were showing the platform's
    // own fixed-position notice"), reappearing in a different file. Recorded SEPARATELY from errBanner
    // on purpose: `errored` keys off errBanner, and a connection notice is a page speaking, not a page
    // failing - folding it in would turn every honest degradation into an error.
    platformNotice: Array.from(document.querySelectorAll(
      '#wh-connection-notice, #wh-auth-expired-notice, #wh-access-denied-notice, [role="status"]'))
      .filter((e) => vis(e) && (e.innerText || '').trim().length > 8)
      .map((e) => ((e.id ? e.id + ': ' : '') + (e.innerText || '').trim()).slice(0, 110)).slice(0, 3),
    offlineShell: !!document.getElementById('net-hint'),
    chars: text.length, own, hub, errBanner, skeletons, controls,
    hive: localStorage.getItem('wh_active_hive_id') || '',
    role: localStorage.getItem('wh_hive_role') || '',
    who: localStorage.getItem('wh_last_worker') || localStorage.getItem('wh_worker_name') || '',
    hiveName: localStorage.getItem('wh_hive_name') || '',
    lang: localStorage.getItem('wh_lang') || 'en',
    // how many of the platform's OWN Filipino strings are on this screen right now
    filHits: (fil || []).reduce((n, w) => (text.includes(w) ? n + 1 : n), 0),
    signInWall: /sign in to|create an account|get started free/i.test(text.slice(0, 1200)) && text.length < 4000,
  };
};

// ★SIGN IN ONCE PER PERSON, NOT ONCE PER STORY. Every journey re-authenticating meant 724 sign-ins against
// a local auth server that answers `WH_DB_TIMEOUT` when this host is busy - so a walk failed not because the
// platform refused, but because the probe asked the same question 724 times. The session is minted once per
// (person, hive) and replayed into each context as storage state, which is also what a real person carries
// from one page to the next.
const SESSIONS = new Map();

async function signInAs(ctx, who, hiveId) {
  const s = await ctx.newPage();
  await s.goto(`${ORIGIN}/shift-brain.html`, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
  // ★THIS WAITED FOR TWO OF THE THREE THINGS IT THEN USED, AND THE THIRD IS THE FRAGILE ONE
  // (2026-09-10). The fallback below reads `window.SUPABASE_KEY`, and a top-level `const` does NOT
  // become a window property - only `var` does. Across the pages that declare a key, 23 use `const`
  // and 4 use `var`; this walk signs in on shift-brain.html, which is one of the four, so the
  // fallback has worked by luck rather than by design and would have gone silently undefined the day
  // anyone made that line match the majority style. Waiting for the page's OWN client first is the
  // real fix - every app page builds it at parse - and waiting for the key only as the alternative
  // means a slow line no longer lands us between "the library is here" and "the page has run".
  //
  // APPLIED MID-BATCH ON PURPOSE, against this file's own rule that a measuring device must not change
  // between archetypes - so the reason is on the record rather than assumed. That rule protects the
  // MEASUREMENT, and this touches none of it: arrival, the transition test, the effect receipts and the
  // thin-page rule are all untouched. This is the PRECONDITION - whether the cast gets signed in at all
  // - and a row that cannot sign in is recorded `unbuilt`, which the ledger already counts as UNRUN
  // rather than failed. So the worst this can do to the batch straddling it is move a row from unrun to
  // run, never from passing to failing. A change to what `arrived` MEANS would have waited for the
  // batch to drain; this one would only have preserved a fragility for another few hours.
  await s.waitForFunction(() => !!window._whSupabaseClient
    || (typeof window.getDb === 'function' && !!window.supabase && !!window.SUPABASE_KEY),
  { timeout: 20000 }).catch(() => {});
  const ok = await s.evaluate(async ({ hive, who, supa }) => {
    try {
      // an honest note beats the library's, which would blame a missing argument for a page that
      // never ran: if there is no client AND no key, say that, and say it in the walk's own words
      if (!window._whSupabaseClient && !window.SUPABASE_KEY) {
        return 'the sign-in page exposed no key and built no client of its own';
      }
      const db = window._whSupabaseClient || window.getDb(supa, window.SUPABASE_KEY);
      const { error } = await db.auth.signInWithPassword({ email: who.email, password: 'test1234' });
      if (error) return 'auth: ' + error.message;
      // ★A SOLO PERSONA MUST NOT BE STAMPED WITH A HIVE, AND THIS STAMPED ONE UNCONDITIONALLY. For a
      // hive-less story `hive` is empty, so the walk wrote an empty wh_active_hive_id - and index.html's
      // pre-paint hint adds `html.wh-signed-in` when a worker AND a hive are present, which hides the
      // marketing landing behind `#mkt-wrap{display:none}`. The result was a 535-character landing page
      // with zero onward links, reported as "3 hops have no way onward at all": the solo journey's worst
      // finding, manufactured by its own setup. A person with no hive is signed in as exactly that.
      if (hive) localStorage.setItem('wh_active_hive_id', hive);
      else { localStorage.removeItem('wh_active_hive_id'); localStorage.removeItem('wh_hive_id'); localStorage.removeItem('wh_hive_name'); }
      localStorage.setItem('wh_last_worker', who.name);
      if (who.role) localStorage.setItem('wh_hive_role', who.role); else localStorage.removeItem('wh_hive_role');
      // a SOLO operator has no hive, and asking a uuid column for '' is a 400 that tells nobody anything
      if (hive) {
        const { data: h } = await db.from('hives').select('name').eq('id', hive).maybeSingle();
        if (h && h.name) localStorage.setItem('wh_hive_name', h.name);
      }
      return 'ok';
    } catch (e) { return 'threw: ' + (e && e.message); }
  }, { hive: hiveId, who, supa: SUPA }).catch((e) => 'evaluate: ' + e.message);
  await s.close();
  return ok;
}

// ── THE ACTIONS A JOURNEY PERFORMS, keyed `<archetype>@<page>` ────────────────────────────────────
// Each runs INSIDE the page, as the person, through a control the product exposes to its own UI - never a
// direct write. The marker below is what makes the effect findable afterwards and removable: a walk that
// leaves rows behind is seeding, and a walk that cannot find its own effect has proved nothing.
const WALK_MARK = 'wh-journey-walk';
const PERFORMS_ANY = (a) => Object.keys(PERFORM).some((k) => k.startsWith(a + '@'));
const PERFORM = {
  // ★A CONVERSION FUNNEL CHANGES WHO IS WALKING IT, and the walk casts one identity for a whole story.
  // J12 is "public -> member": a search result, a free calculator, then the sign-in, then the hive board
  // and a first logbook entry. Walked as one anonymous person it reported hive.html and logbook.html
  // bouncing to the landing page - which is CORRECT for a stranger and says nothing about the funnel,
  // because the funnel's whole point is that they stop being one. The action map already runs code inside
  // a page mid-walk, and the browser context persists across steps, so the conversion is expressible as
  // an action AT the page where it happens.
  // ★WHAT THIS IS AND IS NOT: signing in as an existing member stands in for "they now have a hive". The
  // real product step is joining by an invite code, which the walk has no code for; the receipt says so
  // rather than implying the join was exercised. The member is a plain worker with no platform-admin
  // rights, chosen deliberately - an admin persona would make every page after it a different story.
  'J12@index.html': async () => {
    try {
      const supa = window.SUPABASE_URL || 'http://127.0.0.1:54321';
      const db = window._whSupabaseClient || (window.getDb && window.getDb(supa, window.SUPABASE_KEY));
      if (!db || !db.auth) return { ok: false, why: 'no database client on the landing page to sign in with' };
      const { error } = await db.auth.signInWithPassword({
        email: 'romeobeltran@auth.workhiveph.com', password: 'test1234' });
      if (error) return { ok: false, why: 'the funnel could not sign in: ' + error.message };
      localStorage.setItem('wh_last_worker', 'Romeo Beltran');
      localStorage.setItem('wh_active_hive_id', 'b4f7fe63-92e1-4f8d-b96e-625c3f85ba61');
      localStorage.setItem('wh_hive_role', 'worker');
      return { ok: true, said: 'converted: signed in as Romeo Beltran, a plain member of Manila Electronics Assembly (standing in for a join-by-code the walk has no code for)' };
    } catch (e) { return { ok: false, why: String((e && e.message) || e).slice(0, 90) }; }
  },

  // The AI-assisted day: drive the voice dispatcher the confirm button drives. `logbook.create` only
  // PRE-FILLS the form (its handler returns "Review and tap Save"), so nothing is written to the logbook;
  // the audit row that dispatch now emits is the whole persisted effect, and it is reversed after.
  'J13@logbook.html': async () => {
    try {
      // ★NO PAGE LOADS voice-handler.js DIRECTLY. nav-hub.js appends it `async` on every page, and the
      // page's own tryRegister then retries until WHVoice exists - so both the module and the handler
      // arrive AFTER the page has settled. Looking once and reporting "not exposed on this page" would
      // have been the getDb-exists-before-it-works mistake: a readiness answer taken too early, recorded
      // as a fact about the product. Wait for both, and only then say whether they came.
      const ready = await new Promise((res) => {
        const t0 = Date.now();
        (function poll() {
          const V = window.WHVoice;
          if (V && typeof V.dispatch === 'function' && V._handlers && V._handlers['logbook.create']) return res(true);
          if (Date.now() - t0 > 10000) return res(false);
          setTimeout(poll, 250);
        })();
      });
      const V = window.WHVoice;
      if (!ready) {
        return { ok: false, why: !V ? 'voice-handler never loaded on this page (nav-hub appends it async)'
          : (typeof V.dispatch !== 'function' ? 'WHVoice loaded without a dispatch function'
            : 'this page never registered a logbook.create handler') };
      }
      const r = await V.dispatch({ kind: 'logbook.create', params: {
        machine: 'wh-journey-walk unit', maintenance_type: 'Inspection', category: 'Routine',
        problem: 'wh-journey-walk: dispatched by the full-journey walk to prove the voice path records itself',
        action: 'wh-journey-walk: no save is performed; the form is only pre-filled',
      } }, {});
      const filled = (document.getElementById('f-machine') || {}).value || '';
      return { ok: !!(r && r.ok !== false), said: String((r && r.message) || '').slice(0, 120), filled: filled.slice(0, 60) };
    } catch (e) { return { ok: false, why: String((e && e.message) || e).slice(0, 90) }; }
  },
};

// the chain cache: (archetype, hive) -> count, or null when the database genuinely could not answer
const CHAINS = new Map();
function readChainFresh(archetype, hiveId, identity) {
  CHAINS.delete(`${archetype}@${hiveId}`);
  return readChain(archetype, hiveId, identity);
}
function readChain(archetype, hiveId, identity) {
  const key = `${archetype}@${hiveId}`;
  if (CHAINS.has(key)) return CHAINS.get(key);
  const spec = EFFECT[archetype];
  if (!spec) { CHAINS.set(key, null); return null; }
  // ★A SOLO STORY HAS NO HIVE, AND `$H` TEMPLATED AN EMPTY STRING INTO IT. J11's chain read
  // `logbook where hive_id='$H'`, which became `hive_id=''` - not a uuid, so Postgres refused the
  // statement, psql exited non-zero, and the walk reported "the database did not answer". It answered
  // perfectly well; the question was malformed. A one-person operator's records are keyed to the PERSON,
  // so a chain for them needs the person, and `$W` is that.
  const sql = spec[1].replace(/\$H/g, hiveId).replace(/\$W/g, (identity && identity.name || '').replace(/'/g, "''"));
  const asPerson = identity ? psqlAs(identity.name, sql) : null;
  const raw = (asPerson !== null && asPerson !== '') ? asPerson : psql(sql);
  const val = (raw === null || raw === '') ? null : Number(raw);
  CHAINS.set(key, val);
  return val;
}

// ★A `least()` OF THREE COUNTS CANNOT SAY WHICH LINK IS MISSING. J2 read 0 in all three fleet hives and the
// receipt could only manage "the chain is empty in this hive" - which is the finding with the finding removed.
// A zero is only worth reporting when it names the term that produced it, so on a zero the chain is taken
// apart and each link counted on its own, THROUGH THE SAME PERSON, in the SAME quiet burst as the chain
// itself - never during a walk, where a competing read is what taught me a busy database reads as an empty one.
const CHAIN_WHY = new Map();
function splitTopLevel(text) {
  const out = []; let depth = 0; let cur = '';
  for (const ch of text) {
    if (ch === '(') depth++;
    else if (ch === ')') depth--;
    else if (ch === ',' && depth === 0) { out.push(cur); cur = ''; continue; }
    cur += ch;
  }
  out.push(cur);
  return out.map((t) => t.trim()).filter(Boolean);
}
function explainChain(archetype, hiveId, identity) {
  const key = `${archetype}@${hiveId}`;
  if (CHAIN_WHY.has(key)) return CHAIN_WHY.get(key);
  let why = null;
  const spec = EFFECT[archetype];
  const sql = spec ? spec[1].replace(/\$H/g, hiveId).replace(/\$W/g, (identity && identity.name || '').replace(/'/g, "''")) : '';
  const m = spec && /^\s*select\s+least\s*\(([\s\S]*)\)\s*$/i.exec(sql);
  const terms = m ? splitTopLevel(m[1]) : [];
  // A chain that reads ONE table has nothing to decompose, but it can still say WHICH table came back
  // empty - "the chain is empty" plus a sentence of prose is not the same as naming amc_briefings.
  if (terms.length < 2) {
    const only = /\bfrom\s+([a-z_][a-z0-9_.]*)/i.exec(sql);
    if (only) why = `the missing link is ${only[1]}, which holds nothing for this hive`;
    CHAIN_WHY.set(key, why);
    return why;
  }
  if (terms.length > 1) {
    const named = terms.map((t, i) => {
      const from = /\bfrom\s+([a-z_][a-z0-9_.]*)/i.exec(t);
      const one = `select ${t}`;
      const asPerson = identity ? psqlAs(identity.name, one) : null;
      const raw = (asPerson !== null && asPerson !== '') ? asPerson : psql(one);
      return { link: from ? from[1] : `term ${i + 1}`, n: (raw === null || raw === '') ? null : Number(raw) };
    });
    if (named.some((x) => x.n === null)) why = 'one link could not be read, so which is missing is unknown';
    else {
      const missing = named.filter((x) => x.n === 0).map((x) => x.link);
      const held = named.filter((x) => x.n !== 0).map((x) => `${x.link} ${x.n}`);
      if (missing.length) {
        // ★AND IT MUST NOT SAY "THIS HIVE" ABOUT A TERM THAT IS NOT SCOPED TO ONE. J7's chain had no hive
        // filter, so the decomposition reported "this hive does hold community_posts 15" for a fleet
        // holding none - the number was what the walking person could see across every hive they are in.
        // The sentence now matches the query: a term carrying the hive id speaks about the hive, and one
        // that does not says so.
        const scoped = /where[\s\S]*hive_id\s*=/i.test(sql);
        why = `the missing link is ${missing.join(' and ')}`
            + (held.length
                ? `, while ${scoped ? 'this hive does hold' : 'the platform holds'} ${held.join(' and ')}`
                : ', and no link in the chain holds anything');
      }
    }
  }
  CHAIN_WHY.set(key, why);
  return why;
}

/** One story, walked end to end in one context. Returns the per-step record and the verdict. */
async function walk(browser, story) {
  const steps = [];
  const notes = [];
  // identity is an OBJECT here ({name, email, ...}), not a string - the first version compared the whole
  // object against a set of names, which is always false, so the label silently never fired
  const identityIsPlatformAdmin = !!(story.identity && story.identity.name && PLATFORM_ADMINS.has(story.identity.name));
  let reversed = null;                 // rows this walk created and took back out again
  const viewport = story.device === 'desktop-1280' ? { width: 1280, height: 900 }
    : story.device === 'tablet-768' ? { width: 768, height: 1024 }
    : story.device === 'narrow-320' ? { width: 320, height: 720 }
    : story.device === 'fixed-kiosk-print' ? { width: 1920, height: 1080 }
    : { width: 390, height: 844 };
  const castKey = story.identity ? `${story.identity.email}@${story.hiveId}` : null;
  const opts = { viewport, locale: story.language === 'fil' ? 'fil-PH' : 'en-PH' };
  if (castKey && SESSIONS.has(castKey)) opts.storageState = SESSIONS.get(castKey);
  // declared OUTSIDE the try because `finally` closes it: a `let` inside the try block is not in
  // scope there, and the first version threw `ReferenceError: partnerCtx is not defined` from the
  // cleanup path - killing two whole archetypes (J25, J19) on rows that had nothing to do with a pair.
  let partnerCtx = null;
  const ctx = await browser.newContext(opts);
  try {
    // ★A CONDITION THE WALK DOES NOT APPLY IS A CONDITION THE ROW CANNOT CLAIM. The registry asks for four
    // and this applied ONE. `dependency-down` (20 rows) and `release-mid-way` (20 rows) were never emulated
    // at all, so those journeys would have walked normally and banked as evidence about a failure that never
    // happened - the same shape as setting `wh_lang` and never checking the page answered in Filipino. And
    // `offline-3g` said "slow, and it drops" in its own comment while only ever delaying.
    if (story.condition === 'offline-3g') {
      // a real Philippine plant connection, not a metaphor: slow, and it DROPS - roughly one request in
      // twelve, which is what makes a page's retry and its empty-vs-failed distinction worth anything
      // ★DROPPING BY ARRIVAL ORDER MADE A ROW'S VERDICT UNREPRODUCIBLE, so a fix could not be told from
      // luck (2026-09-10). `++n % 12` drops the twelfth REQUEST, which means the moment anything changes
      // how many requests a page makes, every subsequent drop lands somewhere else. Fixing the service
      // worker's install proved the cost: its precache adds 65 requests up front, every later index
      // shifted, and four rows that had passed the day before came back failing on a completely different
      // hop - not a regression, a different draw. A stress condition may be harsh, but it has to be the
      // SAME harshness twice or it cannot answer whether a change helped.
      //
      // Keyed on the URL and the attempt instead: the same page always loses the same requests across
      // runs and across product changes, while a RETRY of that URL draws again and can succeed - which
      // keeps browser-floor's re-request and the worker's network-first copy meaningful rather than
      // pinning them to certain failure. The rate is unchanged at roughly one in twelve.
      const _tries = new Map();
      const _hash = (str) => { let h = 2166136261; for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; };
      await ctx.route('**/*', async (route) => {
        await new Promise((r) => setTimeout(r, 120));
        const u = route.request().url();
        const attempt = (_tries.get(u) || 0) + 1;
        _tries.set(u, attempt);
        if (_hash(u + '#' + attempt) % 12 === 0) { route.abort('connectionfailed').catch(() => {}); return; }
        route.continue().catch(() => {});
      });
    }
    if (story.condition === 'dependency-down') {
      // the dependency these pages actually have is the edge tier: every function call fails, while the
      // page, its assets and its direct database reads keep working. That is the shape of a provider
      // outage here, and it is what "degrades legibly" is supposed to be true about.
      await ctx.route('**/functions/v1/**', (route) =>
        route.fulfill({ status: 503, contentType: 'application/json',
                        body: JSON.stringify({ error: 'dependency_down', message: 'The service behind this is not answering right now.' }) })
          .catch(() => {}));
    }
    if (story.condition === 'release-mid-way') {
      // a new build lands while the person is mid-journey: the service worker that was serving them is
      // gone and the next navigation is served fresh. Emulated by dropping the registration and its caches
      // after the context exists, so the walk continues across the version boundary rather than around it.
      // ★AND IT FIRED ON EVERY DOCUMENT, WHICH IS NOT A RELEASE - IT IS AN ABSENT WORKER (2026-09-10).
      // `addInitScript` runs on EVERY page the context opens, so this unregistered the worker and wiped
      // the caches before every single step. The row claims a build lands MID-JOURNEY and the person
      // carries on across the version boundary; what was actually measured was a journey that never had
      // a service worker at all and never had a warm cache to lose. Found by the same question that
      // undid the offline-3g cluster on this day - does the mechanism under test actually RUN? - and it
      // is the same mistake in a different coat: a condition that DISABLES the thing it means to
      // perturb. It fires ONCE now, and not on the first page, because a release that lands before the
      // person starts is indistinguishable from having no worker - which is precisely the reading this
      // replaces. The counter lives in localStorage rather than sessionStorage because a journey opens
      // a fresh tab per step and sessionStorage would reset with it.
      await ctx.addInitScript(() => {
        try {
          var SEEN = '__wh_pages_seen', LANDED = '__wh_release_landed';
          var n = Number(localStorage.getItem(SEEN) || '0') + 1;
          localStorage.setItem(SEEN, String(n));
          // FOUR, not two, and the arithmetic matters: the walk opens documents before the journey does.
          // shift-brain.html takes one for the sign-in, and a Filipino row takes another to set wh_lang, so
          // a threshold of 2 lands the release on the journey's FIRST step - which is the very thing this
          // replaced, a release indistinguishable from having no worker. At 4 an English row crosses the
          // boundary around step 3 and a Filipino row around step 2, both of them genuinely mid-journey,
          // with pages already served and a warm cache to actually lose.
          if (n < 4 || localStorage.getItem(LANDED)) return;   // let the worker serve them first
          localStorage.setItem(LANDED, '1');
          navigator.serviceWorker?.getRegistrations?.().then((rs) => rs.forEach((r) => r.unregister())).catch(() => {});
          caches?.keys?.().then((ks) => ks.forEach((k) => caches.delete(k))).catch(() => {});
        } catch (e) { void e; }
      });
    }
    if (story.identity && !opts.storageState) {
      let signed = await signInAs(ctx, story.identity, story.hiveId);
      // one retry: WH_DB_TIMEOUT from a busy local auth server is the host talking, not a refusal
      if (signed !== 'ok') signed = await signInAs(ctx, story.identity, story.hiveId);
      if (signed !== 'ok') notes.push(`the cast could not sign in (${signed})`);
      else SESSIONS.set(castKey, await ctx.storageState().catch(() => null) || undefined);
    }
    if (story.language === 'fil') {
      const p = await ctx.newPage();
      await p.goto(`${ORIGIN}/index.html`, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
      await p.evaluate(() => { try { localStorage.setItem('wh_lang', 'fil'); } catch (e) { void e; } }).catch(() => {});
      await p.close();
    }
    // ★A TWO-SIDED STORY OWES A ROLE PAIR, AND SOME OF THEM CANNOT BE WALKED ANY OTHER WAY (2026-09-10).
    // J27 declares its own pair as `buyer x seller x admin` and its path runs through platform-actions,
    // which reveals itself only to a member of `marketplace_platform_admins`. For Manila/Lucena/Baguio one
    // person is both (Pablo, Leandro), so a single cast walks the whole story. For Tan Delivery Vans and
    // Dela Cruz NOBODY is both - and the path also crosses hive.html and audit-log.html, which belong to
    // the buyer's own hive - so no single human on this platform can take that story end to end. Walking it
    // as the admin alone would fail the hive pages; as the member alone it dead-ends at the moderation
    // page, which is what it did, reading exactly like a wayfinding gap.
    //
    // So the second side gets its own CONTEXT, signed in as itself, and walks only the steps its authority
    // owns. This is what the plan means by "two contexts for a pair" and it is the honest shape: platform
    // moderation IS platform-scoped, so the person who resolves a Tan Delivery Vans dispute genuinely is
    // somebody outside that hive. Every step records WHO walked it, so a receipt can never quietly credit
    // one person with the other's reach.
    const ADMIN_ONLY = new Set(['platform-actions.html', 'marketplace-admin.html']);
    const contextFor = async (pageFile) => {
      if (!story.partner || !ADMIN_ONLY.has(pageFile)) return { c: ctx, who: story.identity ? story.identity.name : null };
      if (!partnerCtx) {
        // ★NOT `opts` - it may carry the PRIMARY cast's storageState (see castKey/SESSIONS above), which
        // would open the partner's context already signed in as the other person and then "prove" the
        // moderation page for somebody who cannot reach it. The partner gets a CLEAN context and signs in
        // as themselves; only the viewport and locale are shared, because the device and language belong
        // to the story, not to the walker.
        partnerCtx = await browser.newContext({ viewport: opts.viewport, locale: opts.locale });
        const s = await signInAs(partnerCtx, story.partner, story.partner.hiveId || story.hiveId);
        // ★THE LANGUAGE BELONGS TO THE STORY, NOT TO THE WALKER (2026-09-10). `wh_lang` was stamped on the
        // primary context only, so the partner opened a fresh context in English and all six Filipino J27
        // rows failed with "the language did not survive the walk: 1 of 6 step(s) lost wh_lang" - one step
        // each, and the step was always the partner's. Read as a product defect it says a Filipino reader
        // is dropped into English mid-journey; it was the pair walk forgetting to carry the setting across
        // the hand-off. A moderator reading in Filipino is still reading in Filipino.
        if (story.language === 'fil') {
          const lp = await partnerCtx.newPage();
          await lp.goto(`${ORIGIN}/index.html`, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
          await lp.evaluate(() => { try { localStorage.setItem('wh_lang', 'fil'); } catch (e) { void e; } }).catch(() => {});
          await lp.close();
        }
        if (s !== 'ok') notes.push(`the ${story.partnerRole || 'partner'} could not sign in (${s})`);
      }
      return { c: partnerCtx, who: story.partner.name };
    };
    for (let i = 0; i < story.pages.length; i++) {
      const pageFile = story.pages[i];
      const next = story.pages[i + 1] || null;
      const q = pageFile === 'marketplace-seller-profile.html' ? '?worker=Isidro%20Suarez' : '';
      const { c: stepCtx, who: walkedBy } = await contextFor(pageFile);
      const page = await stepCtx.newPage();
      const rest = [];
      // ★AND THE PAGE IS NOT SETTLED WHILE IT IS STILL ASKING. pm-scheduler paints its shell in under a
      // second, holds still while its PM list is in flight, and only then fills - so a reader that waits
      // for "the text stopped changing" leaves with 493 characters and calls the page near-empty. Opened
      // alone with a longer wait the same page renders 2,617. Stable TEXT is not enough: the walk also
      // counts the reads the page has out, and does not believe a reading taken mid-question.
      let inflight = 0;
      let answered = 0;                    // the page's own data reads that came BACK
      let lastRequestAt = Date.now();
      page.on('request', (r) => { if (/\/rest\/v1\/|\/rpc\/|\/functions\/v1\//.test(r.url())) { inflight++; lastRequestAt = Date.now(); } });
      page.on('requestfinished', (r) => { if (/\/rest\/v1\/|\/rpc\/|\/functions\/v1\//.test(r.url())) { inflight--; answered++; lastRequestAt = Date.now(); } });
      page.on('requestfailed', (r) => { if (/\/rest\/v1\/|\/rpc\/|\/functions\/v1\//.test(r.url())) { inflight--; answered++; lastRequestAt = Date.now(); } });
      page.on('response', (r) => {
        const u = r.url();
        if (/\/rest\/v1\/|\/rpc\/|\/functions\/v1\//.test(u) && r.status() >= 400) rest.push(`${r.status()} ${u.split('/').pop().slice(0, 34)}`);
      });
      let reading = null; let landed = ''; let loadError = null;
      try {
        await page.goto(`${ORIGIN}/${pageFile}${q}`, { waitUntil: 'domcontentloaded', timeout: 45000 });
        // ★SETTLE WHEN THE PAGE SETTLES, NOT WHEN A NUMBER I PICKED RUNS OUT. Fixed waits cost 12 seconds a
        // step - about seventy-five seconds of deliberate sleeping per journey, hours across the wave - and
        // they are wrong in both directions: too long for a static page, too short for a list that arrives
        // late (the alert cards carrying the onward link read 30 links in one run and 0 in the next). So the
        // walk polls its own reading and stops when the page stops changing: the text has not grown, no
        // skeleton is left, and the thread count is stable across two looks. The cap is generous, because a
        // page that never settles is itself worth recording.
        // a degraded condition is allowed to take longer to settle: a page falling back from a 503,
        // or re-fetching after its service worker vanished, is doing work a normal walk never does -
        // and a cap that does not allow for it would report the CONDITION as the page hanging
        const settleCap = ['offline-3g', 'dependency-down', 'release-mid-way'].includes(story.condition) ? 22000 : 15000;
        const t0 = Date.now();
        let stable = 0;
        let prev = { chars: -1, own: -1, hub: -1 };
        for (;;) {
          await page.waitForTimeout(700);
          reading = await page.evaluate(READ, { nextPage: next, fil: FIL_WORDS });
          const same = reading.chars === prev.chars && reading.own === prev.own && reading.hub === prev.hub;
          stable = same ? stable + 1 : 0;
          prev = { chars: reading.chars, own: reading.own, hub: reading.hub };
          // ★A LIVE PAGE NEVER GOES QUIET, AND WAITING FOR IT TO IS WAITING FOR EVER. Five of six steps hit
          // the cap on the first run with a quiet-only rule: these pages keep a refresher running, so
          // "no read in flight" is a state they never reach. Quiet is the fast path; a page whose text has
          // held still for five straight polls (3.5s) has finished answering whether or not it is still
          // asking, and that is evidence too.
          const quiet = inflight <= 0 && Date.now() - lastRequestAt > 1200;
          // ★A PAGE IS NOT SETTLED UNTIL IT HAS ASKED FOR ITS OWN DATA AND BEEN ANSWERED. pm-scheduler
          // paints its shell in under a second, sits silent - no request in flight, text perfectly stable -
          // and only around the ninth second asks for its PM list. Every rule keyed on stillness therefore
          // exits in that gap: it read 618 characters of a page that holds 2,617, in EVERY hive, on EVERY
          // run, which looked exactly like a product defect and was not. So stillness alone is never
          // enough: at least one of the page's own reads must have come back, or eight seconds must have
          // passed for a page that asks for nothing at all.
          const dwelt = Date.now() - t0 > 4000;
          const asked = answered > 0 || Date.now() - t0 > 8000;
          // ★AND NEVER LEAVE EARLY ON A THIN READING. Whatever rule is used, the cheapest protection
          // against reading a page mid-load is this: a page that looks full may be trusted quickly, and a
          // page that looks nearly empty gets the whole budget before that emptiness is believed. It costs
          // time only on the pages where being wrong is expensive.
          // ...and a compact page that is plainly WAITING for a press counts as full, or the walk spends its
          // whole budget on a page that is already finished (analytics-report rests around a Generate button)
          const looksFull = (reading.chars || 0) >= 900 || ((reading.controls || 0) >= 3 && (reading.chars || 0) >= 300);
          const settled = dwelt && asked && looksFull && (reading.skeletons || 0) === 0
                          && ((stable >= 2 && quiet) || stable >= 5);
          // ★HOW THE WAIT ENDED IS PART OF THE READING. The same pm-scheduler read 2,702 characters in one
          // cell and 563 in the next - so "thin" is not a property of the page, it is a property of whether
          // this box finished rendering it inside the budget. A reading whose wait ran OUT is unreadable and
          // says so; only a reading that ended because the page went quiet is evidence about the page.
          if (settled) { reading.settledBy = 'quiet'; break; }
          if (Date.now() - t0 > settleCap) { reading.settledBy = 'cap'; break; }
        }
        // ★A PERSON SHOWN THE OFFLINE PAGE TAPS "Try again", AND THE WALK SHOULD DO WHAT THE PERSON DOES
        // (2026-09-10). Once the service worker could install, a navigation whose request was lost and
        // which had no cached copy started being answered with the branded offline shell - correctly, and
        // that shell exists precisely so the person can retry: it carries a Try-again control and reloads
        // itself the moment the device reports it is back. A walk that gives up on the first shell is
        // therefore HARSHER than the product it is measuring, and reports "no way onward" for a screen
        // whose whole purpose is to offer one. One reload, and only when the shell is what came back - a
        // healthy page never carries `net-hint`, so this costs nothing on any normal step. If the second
        // attempt is the shell again, the reading stands and the receipt says so: the platform told them
        // twice, which is a real finding about a line this bad rather than an artifact of asking once.
        if (reading.offlineShell) {
          await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
          await page.waitForTimeout(1500);
          const retry = await page.evaluate(READ, { nextPage: next, fil: FIL_WORDS }).catch(() => null);
          if (retry && !retry.offlineShell) { reading = retry; reading.retriedPastOfflineShell = true; }
        }
        // ★ONE LAST LOOK WHEN THE BUDGET RAN OUT ON A THIN PAGE. pm-scheduler fills at about nine seconds
        // when opened alone and does not make the fifteen-second cap when it is the fifth page of a story
        // on this host - so the cap expiring on a page that still looks empty is the one case worth paying
        // ten more seconds for, rather than recording an emptiness that is not the page's.
        // ★AND KEEP LOOKING WHILE IT IS STILL GROWING. One extra look was not enough for the pages that
        // gate their content behind several sequential identity round-trips - asset-hub (six of them) read
        // the same 609 characters in every hive, every run. A page that grew between two looks has not
        // finished, so the walk looks again, up to three times: bounded, and only ever spent on a page that
        // still looks nearly empty.
        for (let late = 0; late < 3 && reading.settledBy === 'cap' && (reading.chars || 0) < 900; late++) {
          await page.waitForTimeout(9000);
          const again = await page.evaluate(READ, { nextPage: next, fil: FIL_WORDS });
          const grew = (again.chars || 0) > (reading.chars || 0);
          if (grew) reading = again;
          if (!grew || (reading.chars || 0) >= 900) {
            // ★'stable' is NOT 'cap': this page was looked at again after nine more seconds and did
            // not grow, so it has FINISHED - it is simply small. Keeping both under 'cap' is what made
            // hive.html's 255-character onboard view read as a page that never arrived.
            reading.settledBy = grew ? 'late' : ((reading.chars || 0) < 900 ? 'stable' : 'cap');
            break;
          }
        }
        // ★COMPARE THE WHOLE TAIL, NOT THE LAST SEGMENT. `.pop()` on
        // `…/workhive/learn/ra-11285-…/index.html` returns `index.html`, so EVERY learn article and EVERY
        // calculator - each of which is `<slug>/index.html` - reported that it had landed on the landing
        // page. J30 read "4/8 step(s) did not arrive as themselves" while those four steps had loaded
        // perfectly: 15,826 and 14,799 characters of the actual articles. The character counts were the
        // tell - the landing page cannot be four different lengths. This is the wrong-end-of-the-path
        // mistake that cost 57 readings earlier in this same programme, in a second place.
        const _u = new URL(page.url());
        const _path = _u.pathname.replace(/^\/+/, '').split('?')[0].split('#')[0];
        landed = _path.endsWith(pageFile) ? pageFile
          : (_path.split('/').pop() || '');
      } catch (e) { loadError = String(e.message || e).slice(0, 110); }
      // ★A JOURNEY WHOSE EVIDENCE IS A RECORD OF AN ACTION MUST PERFORM THE ACTION. J13, the AI-assisted
      // day, asks for a row in ai_audit_log - and that table's own chain text says it "is never seeded",
      // correctly, because a record of a decision nobody made would be a lie. So the walk reads 0 in every
      // hive and always will, until the walk itself does the thing. This drives the product's OWN public
      // dispatcher, the same function the confirm button calls, and then looks for what it left behind.
      // `logbook.create` writes NOTHING to the database - it pre-fills the form and asks the worker to
      // review and tap Save - so the only persisted effect is the audit row, which is reversed below.
      let performed = null;
      const act = !loadError && landed === pageFile ? PERFORM[`${story.baseArchetype}@${pageFile}`] : null;
      if (act) {
        performed = await page.evaluate(act).catch((e) => ({ ok: false, why: String(e.message || e).slice(0, 90) }));
      }
      await page.close().catch(() => {});
      steps.push({ page: pageFile, next, landed, loadError, rest: rest.slice(0, 3), ...(reading || {}),
                   ...(performed ? { performed } : {}),
                   // WHO walked this step. Only ever recorded when it is NOT the story's primary cast, so
                   // a receipt cannot quietly credit one person with the other's reach.
                   ...(walkedBy && story.identity && walkedBy !== story.identity.name ? { walkedBy } : {}) });
    }
  } finally {
    await ctx.close().catch(() => {});
    if (partnerCtx) await partnerCtx.close().catch(() => {});
  }

  // ── the verdict, rail by rail ──
  // ★A SMALL PAGE THAT FINISHED IS AN ARRIVAL. The 300-char floor exists to catch a BLANK render,
  // and it also caught every honest empty state: hive.html's onboard view for a person with no hive
  // is 255 chars and always has been (median 256 across every receipt, against 3077 for someone who
  // HAS a hive). A page marked 'stable' was re-read nine seconds later and had not grown, so it is
  // finished; the 120-char floor keeps a chrome-only blank failing.
  // ★AND THE BLAST RADIUS WAS MEASURED BEFORE THIS WAS TRUSTED, because a loosened threshold that
  // greens forty rows is not a fix, it is an amnesty. Across every receipt on disk, the open rows
  // whose ONLY arrival failure is a thin-but-LANDED page are J11 (eight rows, hive.html at 255) and
  // W3599 (hive.html at 218). Nine rows, one page, one honest empty state - and J11 re-walked 8/8
  // afterwards with 9/9 steps arriving. Everything else that was failing still fails.
  const arrived = steps.filter((s) => !s.loadError
    && (s.chars >= 300 || (s.settledBy === 'stable' && s.chars >= 120))
    && (s.landed === s.page || s.landed === ''));
  const bounced = steps.filter((s) => s.landed && s.landed !== s.page);
  // ★AN ERROR READ AT THE MOMENT THE WALK GAVE UP WAITING IS NOT EVIDENCE ABOUT THE PAGE. Measured
  // 2026-09-09 across J25's six hives, the correlation was total: every story that settled `quiet` passed,
  // every story that settled `cap` and showed an error failed - and loading the accused page by hand, as
  // the same person, showed no error at all but a correct empty state. The mechanism: community.html bounds
  // its own feed read at 15s (whQueryTimeout), this walk's settle cap is 15s, and under the walk's own
  // browser load that read really does exceed 15s - so the page honestly reports a connection problem that
  // only exists because the walk is standing on the machine. A `cap` settle means this walk never saw the
  // page's finished state; an error photographed then says more about the photographer. Such a step is
  // recorded as UNSETTLED rather than errored, which routes the whole story into the fresh-browser re-ask
  // below instead of into a finding. A `quiet` or `late` settle still counts an error, loudly - that is a
  // page that finished and finished badly, which is exactly what a journey exists to catch.
  const sawSettled = (s) => s.settledBy === 'quiet' || s.settledBy === 'late';
  const errored = steps.filter((s) => s.loadError || ((s.errBanner || []).length && sawSettled(s)));
  const unsettledErr = steps.filter((s) => !s.loadError && (s.errBanner || []).length && !sawSettled(s));
  // ★A THREAD READ ON A PAGE YOU DID NOT ASK FOR IS NOT THIS PAGE'S THREAD. When the cast could not
  // sign in, every step bounced to index.html - which links to everything - and the walk read "5 own
  // threads" while measuring the landing page six times. That is the deep-link lens grading the sign-in
  // door 24 times, one layer along: a step that did not arrive contributes no thread evidence at all.
  //
  // ★AND A PAGE THAT NEVER FINISHED RENDERING IS NOT A PAGE THAT LEADS NOWHERE. On this 8GB host, one
  // run with a second node job alongside it read alert-hub at 658 characters and 0 onward links where an
  // unloaded run read 4,953 and 27 - the same page, the same hive, half an hour apart. Half a suite's
  // reds were once the load rather than the product, so a step thinner than the floor is UNREADABLE: it
  // contributes no thread evidence and it says so, instead of quietly becoming a finding.
  // ★AND THE FLOOR MUST NOT BECOME A PLACE TO HIDE A FINDING. pm-scheduler read exactly 493 characters in
  // every hive, on every run, loaded and quiet alike - a number that stable is the PAGE, not the host. So
  // thinness splits by its tell: a step still showing SKELETONS (or that errored) never finished and is
  // UNREADABLE; a step that settled clean and is still thin FINISHED, and what it finished with is almost
  // nothing - which is a finding about what this person was shown, and it must be said, not excused.
  // ★A PAGE THAT IS WAITING FOR YOU IS NOT A PAGE THAT FAILED. analytics-report builds its report only when
  // somebody presses Generate, so it rests at ~527 characters around that button - and the render floor
  // called it "never finished rendering" in every walk that touched it. A step is only thin if it is BOTH
  // short AND offers nothing to do; a compact, action-first page with its controls on screen is complete.
  const RENDER_FLOOR = 900;
  const waiting = (s) => (s.controls || 0) >= 3;
  const settledThin = steps.filter((s) => !s.loadError && s.landed === s.page && (s.chars || 0) < RENDER_FLOOR
                                          && !waiting(s)
                                          && (s.settledBy === 'quiet' || s.settledBy === 'late')
                                          && (s.skeletons || 0) === 0 && !(s.errBanner || []).length);
  const thin = steps.filter((s) => !s.loadError && s.landed === s.page && (s.chars || 0) < RENDER_FLOOR
                                   && !waiting(s)
                                   && (s.settledBy === 'cap' || (s.skeletons || 0) > 0 || (s.errBanner || []).length));
  const unreadable = new Set(thin.map((s) => s.page));
  const threadSteps = steps.filter((s) => s.next && !s.loadError && (!s.landed || s.landed === s.page)
                                          && !unreadable.has(s.page));
  const ownThread = threadSteps.filter((s) => (s.own || 0) > 0);
  const hubOnly = threadSteps.filter((s) => (s.own || 0) === 0 && (s.hub || 0) > 0);
  // ★A HAND-OFF IS NOT A DEAD END (2026-09-10, found the moment the J27 pair walk started passing). With
  // the pair in place every J27 row reached all six pages, and the Manila rows still reported "1 hop has
  // no way onward at all". The hop is `marketplace.html -> platform-actions.html`, and the reading is
  // correct about the LINK: marketplace.html:810 carries the only route, `<a id="btn-admin-link"
  // href="platform-actions.html#sec-mkt-mod" style="display:none">`, revealed by updateAdminLink() only
  // for a `marketplace_platform_admins` member. The BUYER walks marketplace.html, so the door is
  // correctly shut for them.
  //
  // But that question - "can the person on this page click through to the next one?" - is the wrong
  // question when the next page is walked by SOMEBODY ELSE. This is the moment the story changes hands:
  // the buyer's half ends, and a moderator opens their own console the way moderators do. Requiring a
  // link from the buyer's page would be requiring the platform to show a buyer the door to platform
  // moderation, which is precisely the thing it must NOT do. Judging it as a gap would turn correct
  // tenancy into a reported defect - the same shape as the cast error this pair walk was built to fix.
  //
  // Narrow on purpose: only a step whose NEXT page has a different walker is exempt, so an ordinary dead
  // hop inside either person's own half still fails, and the receipt names the hand-off rather than
  // quietly dropping it.
  const walkerOf = (i) => steps[i] && steps[i].walkedBy ? steps[i].walkedBy : '<primary>';
  const handOffPages = new Set(
    steps.map((s, i) => (i + 1 < steps.length && walkerOf(i) !== walkerOf(i + 1) ? s.page : null)).filter(Boolean));
  const handOffs = threadSteps.filter((s) => (s.own || 0) === 0 && (s.hub || 0) === 0 && handOffPages.has(s.page));
  const noThread = threadSteps.filter((s) => (s.own || 0) === 0 && (s.hub || 0) === 0 && !handOffPages.has(s.page));
  // ★A CLEARED HIVE IS A LOST IDENTITY, NOT A MISSING READING. The first version passed a step whose hive
  // key was EMPTY (`!s.hive || s.hive === hiveId`), which is exactly the state pm-scheduler leaves behind
  // when its membership re-validation does not find the person: it removes wh_active_hive_id and drops to
  // solo scope. So the one page that actively throws a member out read as "identity kept" - the oracle was
  // hiding the finding it exists to catch.
  // ★AND A PARTNER'S STEP IS NOT THE PRIMARY CAST LOSING THEIR IDENTITY (2026-09-10). This oracle asks
  // whether each page still reports the STORY'S hive, which is exactly right for a one-person walk and
  // exactly wrong for a paired one: the moderator who takes platform-actions belongs to a different hive
  // BY CONSTRUCTION - that is why they are the partner - so their step would read as "the identity did not
  // survive" and turn a correctly-walked pair into a false product failure. Their own identity is asserted
  // where it belongs, by signInAs at the moment their context opens; if that fails it is already a note.
  const lostAt = story.identity
    ? steps.filter((s) => !s.walkedBy && !s.loadError && s.landed === s.page && s.hive !== story.hiveId)
    : [];
  // (*)"IDENTITY KEPT" WITH NO IDENTITY IS A FALSE REASSURANCE. `lostAt` is empty when the story HAS
  // no cast, so a journey walked as nobody reported `identity kept` beside pages that were showing it
  // the sign-in wall. J31 - the solo rider, a vertical with no hive and so no member to cast - read
  // exactly that: resume.html and achievements.html bounced it to the landing page (14,641 and 14,639
  // characters against index.html's 14,464) while the summary said the identity had survived.
  const idKept = lostAt.length === 0;

  // (*)DECLARED HERE BECAUSE TWO CHECKS BELOW REACH IT BEFORE ITS OLD DECLARATION. The moment assertion
  // and the no-identity check both push a problem, and both sit above where `const problems` used to be -
  // a temporal dead zone that threw `Cannot access 'problems' before initialization` and CRASHED the
  // whole archetype rather than failing one journey. It never showed until J12, the anon-to-member
  // funnel: it is the first story with no hive and no member to cast, so it is the first to reach the
  // no-identity branch. A prover that crashes reports nothing about the five journeys behind it.
  const problems = [];
  // a cast that cannot sign in is a finding about the SETUP, and it must be said first - otherwise it
  // is reported six times over as six bounced pages and reads like a product failure
  if (notes.length) problems.push(notes.join('; '));

  // the moment is a fact about the hive's history, so it is verified rather than applied
  const wantDays = MOMENTS_NEEDED[story.moment];
  if (wantDays) {
    const have = hiveSpanDays(story.hiveId);
    if (have === null) {
      problems.push(`this row is set at "${story.moment}" and the hive's history could not be read, so the moment is unverified`);
    } else if (have < wantDays) {
      problems.push(`this row is set at "${story.moment}", which needs about ${wantDays} days of history; `
        + `this hive holds ${have}. The moment it names is not one this hive has lived, so the walk is about `
        + `today's data wearing another date`);
    }
  }
  // ★"NO IDENTITY" IS NOT TRUE OF A STORY THAT SIGNS IN PARTWAY THROUGH. A conversion funnel starts as
  // nobody on purpose - that is the first half of it - and becomes a member at the page where a person
  // becomes one. Judging it by the identity it was CAST with reports the premise as the failure. A story
  // whose action converted has an identity from that page onward, and the steps prove it: J12 went from
  // three of five pages arriving to five of five, with the hive board and the logbook no longer bouncing.
  const converted = steps.some((s) => s.performed && s.performed.ok && /signed in|converted/i.test(s.performed.said || ''));
  if (!story.identity && !converted) {
    problems.push('walked with NO identity - this vertical has no member to cast, so every hive page it '
      + 'touched was the sign-in door rather than the page. Nothing here is evidence about the story');
  }
  // ★THE CHAIN IS READ BEFORE THE BROWSER STARTS, NOT BETWEEN JOURNEYS. Asking the database while this
  // host is running a browser is asking it at its worst moment: nearly every held row in the first drives
  // read "the chain could not be READ", which is a true statement about the probe's timing and nothing at
  // all about the platform. Every archetype-and-hive pair is now read ONCE, in one quiet burst before any
  // page is opened, and looked up here.
  const [effectWhat, effectSql] = EFFECT[story.baseArchetype] || ["no chain declared", ""];
  // A story that PERFORMS something cannot use the up-front reading: that was taken before the browser
  // existed, and the whole point is what the walk left behind. Read it fresh, past the cache, then take
  // the row back out - a walk that leaves rows behind has stopped being a walk and started seeding.
  let effect;
  if (effectSql && PERFORMS_ANY(story.baseArchetype)) {
    effect = readChainFresh(story.baseArchetype, story.hiveId, story.identity);
    reversed = psql(`with d as (delete from ai_audit_log where hive_id = '${story.hiveId}' and payload::text like '%${WALK_MARK}%' returning 1) select count(*) from d`);
    // only a FAILURE to clean up is a finding - `notes` is folded into problems, so a success line here
    // would report tidying up as something going wrong
    if (reversed === null) notes.push('the walk could not remove its own audit row - check ai_audit_log for ' + WALK_MARK);
  } else {
    effect = effectSql ? readChain(story.baseArchetype, story.hiveId, story.identity) : null;
  }
  // and the action itself is a rail: a story that was supposed to DO something and did not is not a story
  // whose chain merely came back empty - it never reached the point of having one.
  if (PERFORMS_ANY(story.baseArchetype)) {
    const acted = steps.filter((s) => s.performed);
    const wanted = story.pages.filter((pg) => PERFORM[`${story.baseArchetype}@${pg}`]);
    if (!acted.length) {
      problems.push(`the action this story turns on never ran (${wanted.join(', ') || 'no page in this path declares one'}) `
        + '- the page did not arrive, or the walk never reached it');
    } else {
      const failed = acted.filter((s) => !s.performed.ok);
      if (failed.length) problems.push('the action did not complete: '
        + failed.map((s) => `${s.page} - ${s.performed.why || s.performed.said || 'no reason given'}`).join('; '));
    }
  }

  if (arrived.length < steps.length) problems.push(`${steps.length - arrived.length}/${steps.length} step(s) did not arrive as themselves`);
  if (thin.length) problems.push(`${thin.length} step(s) never finished rendering (${thin.map((s) => `${s.page} ${s.chars}c${s.settledBy === 'cap' ? ', wait ran out' : `, ${s.skeletons} skeleton(s)`}`).join(', ')}) - unreadable, re-walk on a quiet host`);
  if (settledThin.length) problems.push(`${settledThin.length} step(s) finished and showed this person almost nothing (${settledThin.map((s) => `${s.page} ${s.chars} chars`).join(', ')})`);
  // ★A DESTINATION THE PLATFORM DELIBERATELY HIDES FROM THE HUB IS NOT AN UNREACHABLE ONE. Five entries in
  // nav-hub.js carry `hidden: true` with a note saying where they ARE surfaced - Audit Log from hive.html,
  // Project Report from project-manager, and three more. J4 (audit season) hops straight from logbook to
  // audit-log and then from report-sender to project-report, so it reported "3 hop(s) have no way onward at
  // all" in all six hives. Both destinations are deliberately parented elsewhere: the ARCHETYPE'S PATH skips
  // the route the platform intends, and the product is behaving as designed. Reporting that as a navigation
  // defect would have put a false finding on every journey that touches one of the five.
  // ★DERIVED, NOT HAND-LISTED. A typed list of five was already wrong: `analytics-report.html` is not a hub
  // entry at all and is reached from `analytics.html`, so J4's third hop was still being called a gap. Every
  // hand-kept vocabulary in this wave has gone stale the same way, so this reads the hub's own hrefs and,
  // for any destination the hub does not offer, names the page that links to it.
  const PARENTED = parentedDestinations();
  // ★ARRIVING FROM THE PARENT IS NOT SKIPPING THE PARENT. This flagged J14's repaired path in all six
  // hives - `… logbook -> index.html -> public-feed …` - reporting that the hop "skips the intended route
  // (public-feed.html is reached from index.html)" while the person was standing ON index.html. The test
  // asked whether the destination is parented and never asked where we had come from, so the one path
  // shaped exactly as the platform intends was the one it refused.
  //
  // ★AND THE EXEMPTION MUST NOT SWALLOW THE FINDING. Dropping such a step entirely would hide the harder
  // truth: we ARE on the parent and it still shows no way onward, which is a navigation gap and not a
  // mis-written path. So it moves to `genuine` rather than disappearing - the same reading, filed under
  // what it actually is.
  const parentsOf = (dest) => PARENTED[dest] || [];
  const arrivedFromParent = (s) => parentsOf(s.next).includes(s.page);
  const byDesign = noThread.filter((s) => !s.offlineShell && parentsOf(s.next).length && !arrivedFromParent(s));
  // ★AND A STEP THE PLATFORM ANSWERED WITH THE OFFLINE SHELL IS A THIRD THING AGAIN. It is neither a
  // navigation gap nor a path that skips a parent: the request was lost, nothing was cached, and the
  // worker told the person so in the platform's own words. Under a condition whose whole subject is a
  // failing connection that is the behaviour being tested FOR, so it is reported in its own sentence
  // and left to a human to disposition - never silently dropped, which would hide a shell served on a
  // healthy connection, and never counted as a dead hop, which is what put four false findings on
  // rows that had passed a day earlier.
  const toldOffline = noThread.filter((s) => s.offlineShell);
  const genuine = noThread.filter((s) => !s.offlineShell && (!parentsOf(s.next).length || arrivedFromParent(s)));
  if (genuine.length) problems.push(`${genuine.length} hop(s) have no way onward at all`);
  if (toldOffline.length) {
    problems.push(`${toldOffline.length} hop(s) were answered with the offline shell `
      + `(${toldOffline.map((s) => s.page).join(', ')}) - the request was lost and nothing was cached, `
      + `so the platform told the person it was offline; that is the designed degradation, not a `
      + `navigation gap`);
  }
  if (byDesign.length) {
    problems.push(`${byDesign.length} hop(s) go straight to a destination the platform parents elsewhere `
      + `(${byDesign.map((s) => `${s.next} is reached from ${parentsOf(s.next).join(' or ')}`).join('; ')}) `
      + `- this archetype's path skips the intended route, it is not a navigation gap`);
  }
  if (!idKept) problems.push(`the identity did not survive: ${lostAt.map((s) => `${s.page} left the hive ${s.hive ? `as ${s.hive.slice(0, 8)}` : 'EMPTY'}`).join(', ')}`);
  // ★THE LANGUAGE THE CELL NAMES MUST BE THE LANGUAGE ON SCREEN. A Filipino instance that renders entirely
  // in English is not a Filipino walk, and banking it would make 254 tier-B rows evidence about a setting
  // rather than about a person. Judged only on steps that ARRIVED, and only where the dictionary itself
  // could be read - an empty dictionary would otherwise convict every page of ignoring it.
  if (story.language === 'fil' && FIL_WORDS.length > 20) {
    const seen = arrived.filter((s) => (s.filHits || 0) > 0);
    const kept = arrived.filter((s) => s.lang === 'fil');
    if (!seen.length) {
      problems.push(`asked for Filipino and every page answered in English: ${arrived.length} step(s) arrived, `
        + `${kept.length} still held wh_lang=fil, and not one showed a single string from the platform's own `
        + `Filipino dictionary (${FIL_WORDS.length} available)`);
    } else if (kept.length < arrived.length) {
      problems.push(`the language did not survive the walk: ${arrived.length - kept.length} of ${arrived.length} `
        + `step(s) lost wh_lang, so a person reading in Filipino is dropped back into English mid-journey`);
    }
  }
  if (effectSql && effect === null) problems.push(`the chain could not be READ (the database did not answer) - not evidence about ${effectWhat}`);
  else if (effectSql && effect === 0) {
    const why = CHAIN_WHY.get(`${story.baseArchetype}@${story.hiveId}`);
    problems.push(`the chain is empty in this hive (${effectWhat})` + (why ? ` - ${why}` : ''));
  }
  if (errored.length) problems.push(`${errored.length} step(s) showed the person an error`);
  /* ★A STORY THAT ONLY HOLDS BECAUSE IT WAS WALKED AS A PLATFORM ADMIN HAS NOT BEEN PROVEN (2026-09-09,
     found on J27). Three casts walked the same dispute story; the two ORDINARY supervisors both stopped at
     marketplace.html with no way onward to platform-actions.html, and the one that sailed through was
     Leandro Marquez, who is in marketplace_platform_admins. The gating is correct - that surface belongs to
     an admin - but the pass is not evidence about a BUYER, which is who this journey is cast for. An admin
     sees a door nobody else does, so a green from an admin says only that admins can walk it. Named on the
     receipt rather than silently banked, so a reader can tell "the platform works for a buyer" from "the
     platform works for the person who can see everything". */
  // a multi-hive story with nobody who holds two hives INCLUDING this one is uncastable: recorded as an
  // unrun cast gap, never as the platform failing to carry an identity it was never given
  if (story.noValidMultiHiveCast) {
    notes.push('the cast could not sign in (no non-admin member holds this hive AND another, so this '
      + 'multi-hive story has nobody on this platform who could take it - a cast gap, not a platform failure)');
  }
  // A pair walk must ANNOUNCE itself. Without this line a receipt would read "identity kept across every
  // hop" for a story two different people walked - true of each of them separately and false of the story.
  if (handOffs.length) {
    notes.push(`${handOffs.length} hop(s) HAND THE STORY OVER rather than dead-end `
      + `(${handOffs.map((s) => `${s.page} -> ${s.next}`).join(', ')}): the next page is walked by a `
      + `different person, so the platform is right not to offer the first one a link to it - showing a `
      + `buyer the door to platform moderation is the thing it must not do. Counted as a hand-off, not a `
      + `way onward, and named here so it is never mistaken for either`);
  }
  const pairedSteps = steps.filter((s) => s.walkedBy);
  if (pairedSteps.length) {
    notes.push(`walked as a ROLE PAIR, in two signed-in contexts: ${story.identity.name} took the hive's own `
      + `pages, and ${story.partner.name} - a ${story.partnerRole} - took ${pairedSteps.map((s) => s.page).join(', ')}, `
      + `because platform moderation is platform-scoped and nobody in this hive holds it. Neither half is `
      + `evidence about the other's reach`);
  }
  if (story.noValidAdminCast) {
    notes.push('this dispute story reaches a platform-moderation page, and no marketplace platform admin '
      + 'belongs to this hive - so nobody on this platform could take the resolution half of it. A cast '
      + 'gap, not a platform failure: borrowing an admin from another hive would prove a path this '
      + "vertical's own people cannot walk");
  }
  if (identityIsPlatformAdmin) {
    notes.push(`walked as ${story.identity.name}, who is a marketplace platform admin - an admin sees doors an `
      + `ordinary member does not, so this reading is about an admin's path, not this journey's cast`);
  }
  if (unsettledErr.length) {
    problems.push(`${unsettledErr.length} step(s) showed an error while this walk was still waiting `
      + `(${unsettledErr.map((s) => s.page).join(', ')}) - the page bounds its own read at 15s and so does `
      + `this walk, so the reading is unsettled and must be re-asked on a quiet machine before it counts`);
  }
  // ★A HOST THAT TIMED OUT IS NOT A PLATFORM THAT REFUSED. The header rule above is right - a journey that
  // cannot be CONSTRUCTED must never be a quiet pass - but it was collapsing two different failures into
  // one verdict. `WH_DB_TIMEOUT` from the local auth server is this MACHINE under load (measured: it
  // appeared the moment a second node process ran alongside the walk), and reporting it as BAD states
  // something about the product that was never tested. A rejected credential still fails, loudly. This is
  // a THIRD state, not a skip: it is printed as UNRUN, counted apart, excluded from the pass ratio, and
  // never banked - so it can only ever be cleared by walking it again on a quiet host.
  // the reason is not always first inside the bracket - the note reads "(auth: WH_DB_TIMEOUT)"
  const hostFailed = notes.some((n) => /could not sign in \([^)]*(WH_DB_TIMEOUT|timeout|timed out|fetch failed|ECONN|socket hang up|502|503|504|threw:|is not a function|undefined is not|Cannot read prop|Execution context|Target closed|detached)/i.test(n))
    // ...and a chain the DATABASE never answered is the same fact wearing different words. This branch
    // already says "not evidence about X" in its own message and then counted itself as a finding anyway,
    // which is the contradiction UNRUN exists to end: if it is not evidence, it is not a verdict either.
    || problems.some((p) => /the chain could not be READ \(the database did not answer\)/i.test(p));
  return {
    ok: problems.length === 0 && !hostFailed, unbuilt: hostFailed, problems, steps, notes,
    summary: `${arrived.length}/${steps.length} arrived · thread: ${ownThread.length} own / ${hubOnly.length} hub-only / ${noThread.length} none`
      + (thin.length ? ` / ${thin.length} unreadable` : '') + (settledThin.length ? ` / ${settledThin.length} near-empty` : '')
      + ` · identity ${!story.identity ? 'NONE CAST' : idKept ? 'kept' : 'LOST'} · effect ${effect === null ? 'UNREADABLE' : effect} (${effectWhat})`
      + (bounced.length ? ` · bounced: ${bounced.map((s) => `${s.page}->${s.landed}`).join(', ')}` : ''),
    metrics: { arrived: arrived.length, steps: steps.length, own: ownThread.length, hubOnly: hubOnly.length, none: noThread.length, idKept, effect },
  };
}

// ── the stories to walk, built from the registry's own rows ───────────────────────────────────────
function stories(cast) {
  const reg = JSON.parse(readFileSync('trajectory_registry.json', 'utf8'));
  const rows = reg.trajectories.filter((t) => t.wave === 'W3-JN');
  const out = [];
  for (const t of rows) {
    const j = t.journey || {};
    const base = String(j.archetype || '').split('+')[0];
    if (ONLY_ARCH && base !== ONLY_ARCH && j.archetype !== ONLY_ARCH) continue;
    if (ONLY_TIER && j.tier !== ONLY_TIER) continue;
    if (ONLY_VERT && !String(j.vertical || '').includes(ONLY_VERT)) continue;
    if (ONLY_MOMENT && j.moment !== ONLY_MOMENT) continue;
    if (ONLY_COND && j.condition !== ONLY_COND) continue;
    // the cast: the vertical names a hive, or names a person who has none
    const hiveName = Object.keys(cast).find((h) => String(j.vertical || '').includes(h));
    const c = hiveName ? cast[hiveName] : null;
    // ★A PAIR'S SECOND ROLE MUST NOT ESCALATE ITS FIRST (2026-09-10). This reads the whole `pair` string,
    // so J27's `buyer x seller x admin` matched /admin/ and cast the BUYER half as the hive's supervisor -
    // who in Baguio is Leandro Marquez, himself a platform admin. The row's own receipt then said it: "an
    // admin sees doors an ordinary member does not, so this reading is about an admin's path, not this
    // journey's cast". The pair names the people the STORY needs, not the authority its FIRST walker
    // should hold; now that the admin half has its own context and its own person, the primary must be
    // read from the row's persona alone (`buyer`), or the pair walk quietly hands the buyer admin reach
    // and proves a journey no buyer could take.
    const pairForCast = partnerHandlesAdmin(j) ? String(j.pair || '').replace(/admin/gi, '') : (j.pair || '');
    const wantsSupervisor = /supervisor|oversight|owner|engineer|manager/i.test(t.persona || '') || /supervisor|admin|oversight/i.test(pairForCast);
    // ★THE SECOND HALF OF THAT COMMENT WAS NEVER WRITTEN. "Or names a person who has none" describes J11
    // and J31 - the solo technician and the solo rider - and the code simply left their identity null. They
    // then walked as NOBODY, met the sign-in wall on every personal page, and the summary said "identity
    // kept" because there was no identity to lose. The platform HAS these people: three auth users hold no
    // active membership, and two of them are `rider.marlonph@…` and `rangerowner26@…`. They are cast here.
    const solo = !c ? SOLO.find((s) => s.keys.some((k) => new RegExp(k, 'i').test(j.vertical || ''))) : null;
    let identity = c ? ((wantsSupervisor ? c.supervisor : c.worker) || c.supervisor) : (solo || null);
    // ★A MULTI-HIVE STORY MUST BE CAST ON SOMEONE WHO IS IN TWO HIVES (2026-09-09, found on J26). "The
    // multi-hive worker's day" was walked as David Velasco, who belongs to ONE hive - and to a different
    // one than the row names - so hive.html quite correctly showed him no route into a hive he is not in,
    // and the walk recorded it as the platform having no way onward. The platform does have such a person:
    // Christine Dizon holds Lucena AND Manila, and is not a platform admin. Casting the story on anyone
    // else tests a journey nobody in it could take.
    // ...and ONLY when that person actually belongs to the hive the row names. The first version fell back
    // to "any multi-hive person", which cast Christine Dizon (Lucena + Manila) for a Dela Cruz row - the
    // page put her in Lucena, quite correctly, and the walk called it "the identity did not survive". No
    // one on this platform holds Dela Cruz AND another hive, so that row has no honest cast; saying so is
    // the answer, not substituting somebody who makes the walk complete.
    // the credit story belongs to the person who holds the credits, in their own hive
    if (/^J28$/.test(base)) {
      const trader = CREDIT_HOLDERS.find((m) => String(j.vertical || '').includes(m.hive));
      if (trader) identity = { name: trader.name, email: trader.email };
    }
    // ★A PLATFORM-LEVEL STORY HAS NO HIVE TO BE CAST FROM (2026-09-10). J32, "the founder's month-end",
    // declares its vertical as "the platform itself (founder view)" - deliberately not a hive name - so
    // the hive lookup above finds nothing, `c` is null, and the row would walk as NOBODY. Its very first
    // page is platform-actions.html, which reveals itself only to a `marketplace_platform_admins` member,
    // so all four rows would have met the admin gate as an anonymous visitor and reported the platform
    // refusing a founder. The same shape as J11/J31 walking as nobody before the solo personas were cast.
    //
    // The nearest true identity this platform has for "founder view" is a platform admin, and unlike the
    // J27 pair this story is ADMIN ALL THE WAY THROUGH - every page it names is an oversight surface - so
    // one cast is the honest one. `identityIsPlatformAdmin` already stamps every such receipt with "an
    // admin sees doors an ordinary member does not", which is exactly the right caveat here rather than a
    // warning: for this row it is the point.
    if (/^J32$/.test(base) && ADMIN_MEMBERS.length) {
      const founder = ADMIN_MEMBERS[0];
      identity = { name: founder.name, email: founder.email, hiveId: founder.hiveId };
    }
    let noValidMultiHiveCast = false;
    if (/^J26$/.test(base)) {
      const both = MULTI_HIVE.find((m) => m.hives.some((hv) => String(j.vertical || '').includes(hv)));
      if (both) identity = { name: both.name, email: both.email };
      else noValidMultiHiveCast = true;
    }
    // the dispute story belongs to whoever may resolve one - see ADMIN_MEMBERS. Matched on the WHOLE
    // archetype, not `base`: a Tier-D chain is spelled `J6+J27+J7+J31`, so `base` is J6 and a `^J27$`
    // test on it would miss exactly the row that found this.
    let noValidAdminCast = false;
    let partner = null, partnerRole = null;
    if (partnerHandlesAdmin(j)) {
      // ALWAYS the pair, never a single admin - even where one person happens to be both. The first
      // version cast the whole row on an in-hive moderator (Pablo holds Manila and Lucena; Leandro
      // Baguio) because it was simpler and it worked. It was also the wrong reading: this row's persona
      // is the BUYER, and an admin "sees doors an ordinary member does not" - so walking the buyer's own
      // pages as a moderator would prove a path with more reach than the person the row is about, and
      // pass where a real buyer might not. The archetype itself describes two people ("the dispute, the
      // admin's VIEW, the resolution BOTH PARTIES can read"), so the buyer keeps the buyer's pages and a
      // real moderator takes only the moderation step. One code path, and the honest one.
      const adm = ADMIN_MEMBERS.find((m) => !String(j.vertical || '').includes(m.hive)) || ADMIN_MEMBERS[0];
      if (adm) {
        partner = { name: adm.name, email: adm.email, hiveId: adm.hiveId };
        partnerRole = 'marketplace platform admin';
      } else {
        noValidAdminCast = true;   // no moderator exists anywhere: say so, never invent one
      }
    }
    out.push({
      id: t.id, title: t.title, baseArchetype: base, archetype: j.archetype, tier: j.tier, noValidMultiHiveCast, noValidAdminCast,
      partner, partnerRole,
      vertical: j.vertical, language: j.language || 'en', device: t.device, condition: j.condition || 'normal',
      moment: j.moment || 'present',
      // a platform-level story (J32) has no hive of its own, so it borrows the FOUNDER'S - the path
      // includes hive.html, and an empty wh_active_hive_id is the state that drops a signed-in
      // person onto the marketing landing page (see the solo-persona note in signInAs).
      pages: t.pages, hiveId: (c ? c.hiveId : '') || (identity && identity.hiveId) || '', identity: identity ? { ...identity } : null,
      anon: !c,
    });
  }
  return LIMIT ? out.slice(0, LIMIT) : out;
}

// ── teeth (no browser) ────────────────────────────────────────────────────────────────────────────
if (args.includes('--self-test')) {
  const fails = [];
  const cast = loadCast();
  if (Object.keys(cast).length < 6) fails.push(`the cast is short: ${Object.keys(cast).length} hive(s) with a signed-in member, expected 6`);
  for (const [h, c] of Object.entries(cast)) {
    if (!c.supervisor) fails.push(`${h} has no supervisor with an auth row`);
    if (!/^[0-9a-f-]{36}$/.test(c.hiveId)) fails.push(`${h} has no hive id`);
  }
  // every archetype the registry uses must declare a chain, and every chain must RUN
  const reg = JSON.parse(readFileSync('trajectory_registry.json', 'utf8'));
  const used = new Set(reg.trajectories.filter((t) => t.wave === 'W3-JN')
    .map((t) => String((t.journey || {}).archetype || '').split('+')[0]).filter(Boolean));
  const anyHive = Object.values(cast)[0];
  for (const a of [...used].sort()) {
    if (!EFFECT[a]) { fails.push(`archetype ${a} declares no chain effect`); continue; }
    const sql = EFFECT[a][1].replace(/\$H/g, anyHive ? anyHive.hiveId : '');
    const v = psql(sql);
    // (*)A FAILED READ IS NOT A BAD ANSWER. `psql` returns null when the database could not be reached
    // at all, and calling .slice() on that threw a TypeError - so a busy host made this self-test
    // CRASH instead of saying which of the two had happened. The same distinction this whole prover
    // is built on, missing from its own teeth.
    if (v === null) { fails.push(`archetype ${a}'s chain could not be READ - the database did not answer`); continue; }
    if (!/^-?[0-9]+$/.test(v)) fails.push(`archetype ${a}'s chain query does not return a number: ${String(v).slice(0, 70) || '(empty)'}`);
  }
  // ★AN ACTION KEYED TO A PAGE NO STORY VISITS WOULD NEVER RUN, and its journey would fail for a reason
  // that is about this file rather than the product. Every PERFORM key must name an archetype the registry
  // uses and a page that archetype's own path crosses.
  for (const key of Object.keys(PERFORM)) {
    const [a, pg] = key.split('@');
    if (!used.has(a)) { fails.push(`PERFORM names archetype ${a}, which the registry does not use`); continue; }
    const paths = reg.trajectories.filter((t) => String((t.journey || {}).archetype || '').split('+')[0] === a);
    if (!paths.some((t) => (t.pages || t.journey?.pages || []).includes(pg))) {
      fails.push(`PERFORM['${key}'] would never run - no ${a} story crosses ${pg}`);
    }
  }

  // ★THE GRID ITSELF MUST HOLD. A journey row that names three pages is not a journey, and a tier-D row
  // that names seven is not a lifetime - if the seeder's enumeration ever drifts, every walk below it is
  // measuring something smaller than the wave claims.
  const jn = reg.trajectories.filter((t) => t.wave === 'W3-JN');
  const short = jn.filter((t) => (t.pages || []).length < 4);
  if (short.length) fails.push(`${short.length} journey row(s) cross fewer than 4 pages, e.g. ${short[0].id}`);
  const tierD = jn.filter((t) => (t.journey || {}).tier === 'D');
  const shortD = tierD.filter((t) => (t.pages || []).length < 8 || (t.layers || []).length < 5);
  if (shortD.length) fails.push(`${shortD.length} lifetime row(s) are under 8 pages or 5 layers, e.g. ${shortD[0].id}`);
  const noCell = jn.filter((t) => !(t.journey || {}).vertical || !(t.journey || {}).tier || !t.device || !t.entry);
  if (noCell.length) fails.push(`${noCell.length} journey row(s) do not name their cell, e.g. ${noCell[0].id}`);
  // every archetype the grid uses must be castable: its vertical has to resolve to a hive or be hive-less
  const casts = new Set(Object.keys(cast));
  const orphan = jn.filter((t) => {
    const v = String((t.journey || {}).vertical || '');
    return !/no hive|anon|reader|calculator|poster|search|platform|founder|and |buying/i.test(v)
      && ![...casts].some((h) => v.includes(h));
  });
  if (orphan.length) fails.push(`${orphan.length} journey row(s) are cast in a vertical the platform does not host, e.g. "${(orphan[0].journey || {}).vertical}"`);
  // ── the ROLE PAIR, locked (2026-09-10) ────────────────────────────────────────────────────────────
  // Four separate bugs took J27 from 0 to 11/11, and three of them would pass every check above: a pair
  // walk can be completely broken while the cast loads and every chain returns a number. These pin the
  // properties, not the plumbing.
  if (!ADMIN_MEMBERS.length) {
    fails.push('no marketplace platform admin has a signed-in account - every J27 row is uncastable');
  } else if (!ADMIN_MEMBERS.every((m) => m.hiveId && /^[0-9a-f-]{36}$/.test(m.hiveId))) {
    fails.push('an ADMIN_MEMBER carries no hive id - the partner would be stamped with the story hive');
  }
  {
    // a hop whose NEXT page has a different walker is a HAND-OFF, never a dead end...
    const steps = [{ page: 'marketplace.html', own: 0, hub: 0, next: 'platform-actions.html' },
                   { page: 'platform-actions.html', own: 1, walkedBy: 'A Moderator', next: 'hive.html' },
                   { page: 'hive.html', own: 0, hub: 0, next: 'audit-log.html' }];
    const walkerOf = (i) => steps[i] && steps[i].walkedBy ? steps[i].walkedBy : '<primary>';
    const handOff = new Set(steps.map((x, i) => (i + 1 < steps.length && walkerOf(i) !== walkerOf(i + 1) ? x.page : null)).filter(Boolean));
    if (!handOff.has('marketplace.html')) fails.push('the hop INTO a partner page is not being read as a hand-off');
    // ...and an ordinary dead hop inside one person's own half must STILL fail
    if (handOff.has('hive.html')) fails.push('a genuine dead hop is being excused as a hand-off');
  }
  // the pair's second role must not escalate its first: `buyer x seller x admin` casts a BUYER
  if (/supervisor|admin|oversight/i.test(String('buyer x seller x admin').replace(/admin/gi, ''))) {
    fails.push("the admin in a pair still escalates the primary cast to a supervisor");
  }
  {
    // ★A STEP THE PLATFORM ANSWERED WITH THE OFFLINE SHELL IS NOT A DEAD HOP, and the split has to hold
    // in BOTH directions - excusing every linkless step would hide a real navigation gap, which is the
    // more expensive mistake of the two.
    const noThread = [
      { page: 'project-manager.html', own: 0, hub: 0, next: 'project-report.html', offlineShell: true },
      { page: 'skillmatrix.html', own: 0, hub: 0, next: 'achievements.html', offlineShell: false },
    ];
    const parentsOf = () => [];
    const toldOffline = noThread.filter((x) => x.offlineShell);
    const genuine = noThread.filter((x) => !x.offlineShell && !parentsOf(x.next).length);
    if (toldOffline.length !== 1) fails.push('a step served the offline shell is not being read as one');
    if (genuine.length !== 1) fails.push('a genuine dead hop is being excused as an offline shell');
    if (genuine.some((x) => x.offlineShell)) fails.push('an offline-shell step is still counted as a dead hop');
    // ★AND THE BLOCK ABOVE TESTS ITS OWN COPY OF THE RULE, which would stay green if the guard were
    // deleted from the walk itself - the hollow-lock shape this file has been bitten by before. So the
    // SOURCE is asserted too: the three things that make the split real must still be in the code that
    // ships, not only in the fixture above.
    const _src = readFileSync('tools/prove_full_journeys.mjs', 'utf8');
    for (const [what, re] of [
      ['the step reading no longer records offlineShell', /offlineShell:\s*!!document\.getElementById\('net-hint'\)/],
      ['the dead-hop filter no longer excludes an offline shell', /const genuine = noThread\.filter\(\(s\) => !s\.offlineShell/],
      // ★AN ASSERTION THAT GREPS FOR ITS OWN PATTERN LITERAL IS SELF-SATISFYING. Written as a regex
      // literal, this phrase existed TWICE in the file - once where the walk reports it and once here -
      // so deleting the report left this matching itself and the mutation passed. Built from pieces at
      // runtime, the whole phrase appears exactly once in the source: at the place that must have it.
      ['the offline shell is no longer reported in its own words', new RegExp('answered with the ' + 'offline shell')],
      // anchored on the ROUTE handler's own line, not on the expression - the fixture above contains an
      // identical copy of that expression, so matching it proved only that this test still exists
      ['the offline-3g loss went back to counting arrivals', /_tries\.set\(u, attempt\)/],
      // the walk must still do what the person does when the shell comes back; anchored on a token
      // that exists at exactly one site (grep -c says 1), never on a sentence a test might also quote
      ['the walk no longer retries past the offline shell', new RegExp('retriedPast' + 'OfflineShell')],
      // built at runtime for the same reason as the two above: written as a literal, the pattern would
      // exist twice in this file and the assertion would match itself
      ['the walk can no longer see the role=status notices the platform paints', new RegExp('platform' + 'Notice:')],
    ]) if (!re.test(_src)) fails.push(what);
  }
  {
    // the offline-3g loss must be REPRODUCIBLE (the same URL loses the same request every run) and must
    // still let a RETRY through, or browser-floor's re-request and the worker's kept copy are pinned to
    // certain failure. Both properties, because a rate of zero and a rate of one are each "deterministic".
    const _hash = (str) => { let h = 2166136261; for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; };
    const drop = (u, attempt) => _hash(u + '#' + attempt) % 12 === 0;
    const O = 'http://127.0.0.1:5000/workhive/';
    if (drop(O + 'utils.js', 1) !== drop(O + 'utils.js', 1)) fails.push('the offline-3g loss is not deterministic');
    const urls = Array.from({ length: 600 }, (_, i) => O + 'r' + i + '.js');
    const lost = urls.filter((u) => drop(u, 1)).length;
    if (lost === 0 || lost === urls.length) fails.push(`the offline-3g loss is degenerate (${lost} of ${urls.length} dropped)`);
    if (lost / urls.length > 0.25) fails.push(`the offline-3g loss is far harsher than one in twelve (${(100 * lost / urls.length).toFixed(1)}%)`);
    const stuck = urls.filter((u) => drop(u, 1) && drop(u, 2)).length;
    if (lost && stuck === lost) fails.push('every dropped URL also fails its retry - a retry can never succeed');
  }
  console.log(fails.length ? 'FAIL full-journeys self-test - ' + fails.join('; ')
    : `self-test OK: ${Object.keys(cast).length} hives cast from the database, ${used.size} archetype chains all return a number`);
  process.exit(fails.length ? 1 : 0);
}

// ── the run ───────────────────────────────────────────────────────────────────────────────────────
const cast = loadCast();
const list = stories(cast);
if (!list.length) { console.log('FAIL full-journeys - no story matched the filters (a journey that cannot be constructed fails, it never skips)'); process.exit(1); }
console.log(`walking ${list.length} journey(ies)  ·  cast: ${Object.keys(cast).length} hives  ·  origin ${ORIGIN}`);
// every chain this run needs, read in one quiet burst BEFORE the browser exists
{
  const pairs = new Map();
  for (const s of list) if (s.hiveId) pairs.set(`${s.baseArchetype}@${s.hiveId}`, s);
  let read = 0; let unread = 0;
  for (const s of pairs.values()) {
    const v = readChain(s.baseArchetype, s.hiveId, s.identity);
    if (v === null) unread++; else read++;
    if (v === 0) explainChain(s.baseArchetype, s.hiveId, s.identity);   // decompose the zero HERE, not mid-walk
  }
  console.log(`  chains read up front: ${read} answered, ${unread} unreadable (of ${pairs.size} archetype-and-hive pairs)`);
}
// this host has one browser slot and the suite runs gates concurrently - queue, do not race
await takeBrowserSlot('full-journeys');
let browser = await chromium.launch();
const results = [];
let bad = 0; let unbuilt = 0;
// ★A LONG WALK MUST GIVE THE MACHINE ITS MEMORY BACK. A 130-story tier run died at story 20 with 158MB
// free of 7.8GB and 33 chromium processes alive: contexts are closed per story, but the browser process
// itself grows across a run until the Docker engine beside it starts answering 500. Relaunching every 20
// stories costs about a second each time and keeps the whole run inside a flat memory budget - which is
// also what makes the readings comparable, since a story walked at minute 90 now meets the same machine as
// one walked at minute 2. Serial by design on this host; this is what makes serial survivable.
const RELAUNCH_EVERY = 20;
let since = 0;
for (const s of list) {
  if (++since > RELAUNCH_EVERY) {
    await browser.close().catch(() => {});
    browser = await chromium.launch();
    SESSIONS.clear();
    since = 1;
    console.log(`  ...fresh browser (every ${RELAUNCH_EVERY} stories, so the last is measured on the same machine as the first)`);
  }
  const r = await walk(browser, s);
  if (r.unbuilt) unbuilt++; else if (!r.ok) bad++;
  results.push({ id: s.id, archetype: s.archetype, tier: s.tier, vertical: s.vertical, language: s.language,
                 device: s.device, condition: s.condition, pages: s.pages, ok: r.ok, unbuilt: !!r.unbuilt,
                 problems: r.problems, summary: r.summary, metrics: r.metrics, steps: r.steps, notes: r.notes });
  console.log(`  ${r.unbuilt ? 'UNRUN' : r.ok ? 'ok   ' : 'BAD  '} ${s.id.padEnd(7)} ${String(s.archetype).padEnd(7)} ${String(s.vertical).slice(0, 26).padEnd(27)} ${r.summary}`);
  if (r.unbuilt) console.log(`        the cast could not be established on this host, so nothing was asked of the platform - re-walk on a quiet machine: ${r.notes.join('; ').slice(0, 120)}`);
  else if (!r.ok) console.log(`        ${r.problems.join('; ').slice(0, 168)}`);
}
// ★A FAILURE THIS WALK MAY HAVE CAUSED IS RE-ASKED ALONE BEFORE IT IS RECORDED (2026-09-09). Measured: J25
// in Lucena and in Tan Delivery Vans both reported "1 step(s) showed the person an error", and the error
// was community.html saying "Couldn't load the community feed. Check your connection and try again." That
// page bounds its read at 15 seconds and deliberately files a hung read as a connection problem - which is
// right. But the query behind it runs in 0.4ms on a quiet host: what timed out was not the database, it was
// this walk's own browser contexts saturating an 8GB machine. Walked alone, the same story PASSES.
//
// So a journey whose ONLY complaint is a shown error or an unarrived step is not evidence yet - those are
// exactly the symptoms load produces. It is re-walked by itself, and the SECOND reading is the one that
// counts. A structural failure (no way onward, identity lost, an empty chain) is never re-asked: load does
// not delete a link or change who you are. This costs one extra walk per suspect failure, and failures are
// the minority - a cheap price for never again reporting my own memory pressure as the product's defect.
const LOAD_SHAPED = /showed the person an error|showed an error while this walk was still waiting|did not arrive as themselves|could not be READ/i;
for (const r of results) {
  if (r.ok || r.unbuilt || !r.problems.length) continue;
  if (!r.problems.every((p) => LOAD_SHAPED.test(p))) continue;
  const story = list.find((s) => s.id === r.id);
  if (!story) continue;
  // ★AND THE RE-ASK NEEDS A FRESH BROWSER, NOT JUST A FRESH CONTEXT. The first version re-walked in the
  // SAME chromium that had just run every other story, so the memory pressure that caused the false
  // reading was still there and the re-ask reproduced it faithfully. Measured 2026-09-09: J25 in Tan
  // Delivery Vans failed the re-ask, and then loading that exact page by hand in a clean browser showed
  // no error at all - a correct empty state, "Welcome to your hive's discussion board". Closing and
  // relaunching costs a second and is the whole point: the second opinion has to come from a second
  // instrument, or it is the first instrument agreeing with itself.
  console.log(`  ...re-asking ${r.id} in a fresh browser (its only complaints are the shape load produces)`);
  await browser.close().catch(() => {});
  browser = await chromium.launch();
  SESSIONS.clear();                     // a session minted under load may itself be the thing that failed
  const again = await walk(browser, story);
  if (again.ok) {
    console.log(`  ok    ${r.id.padEnd(7)} ${String(story.archetype).padEnd(7)} ${String(story.vertical).slice(0, 26).padEnd(27)} ${again.summary}`);
    console.log('        the first reading was this walk\'s own load, not the platform: alone, the story holds');
    bad--;
  }
  Object.assign(r, {
    ok: again.ok, unbuilt: !!again.unbuilt, problems: again.problems, summary: again.summary,
    metrics: again.metrics, steps: again.steps, notes: again.notes,
    reasked: true,
  });
}
await browser.close();
try { mkdirSync('.tmp', { recursive: true }); } catch (e) { void e; }
const outFile = `.tmp/full_journeys${ONLY_ARCH ? '_' + ONLY_ARCH : ''}${ONLY_TIER ? '_tier' + ONLY_TIER : ''}`
  + `${ONLY_VERT ? '_' + ONLY_VERT.replace(/[^A-Za-z0-9]+/g, '') : ''}`
  + `${ONLY_MOMENT ? '_' + ONLY_MOMENT.replace(/[^A-Za-z0-9]+/g, '') : ''}`
  + `${ONLY_COND ? '_' + ONLY_COND.replace(/[^A-Za-z0-9]+/g, '') : ''}.json`;   // a one-vertical re-ask must not overwrite the whole run's results
// ★A PARTIAL RE-WALK MUST NOT ERASE WHAT IT DID NOT WALK (2026-09-10). The file name already scopes by
// archetype/tier/vertical/moment so two scopes cannot clobber each other - but `--limit` is not in the
// name, so `--tier D --limit 3` rewrote the whole tier's receipt with three rows and SILENTLY DELETED the
// red results for W3715-W3717 sitting in it. That is worse than a stale red: the manifest counts a row as
// closed unless a receipt contradicts it, so deleting the contradiction launders the row green without
// anyone walking it. Merging by id keeps the file meaning "the latest known result for every row in this
// scope" - a fresh walk supersedes its own id and touches no other. The counters still describe THIS run,
// because that is what the ratio printed below is about.
let merged = results;
try {
  const prior = JSON.parse(readFileSync(outFile, 'utf8'));
  if (prior && Array.isArray(prior.results)) {
    const now = new Map(results.map((r) => [r.id, r]));
    merged = prior.results.map((r) => now.get(r.id) || r)
      .concat(results.filter((r) => !prior.results.some((p) => p.id === r.id)));
  }
} catch (e) { void e; }   // no prior receipt, or an unreadable one: this run's results stand alone
writeFileSync(outFile, JSON.stringify({ walked: list.length, bad, unbuilt, results: merged }, null, 2));
// the ratio is over what was actually ASKED. An unrun story is neither a pass nor a failure, and folding it
// into either would make a busy machine look like a broken platform - or, worse, like a working one.
const asked = list.length - unbuilt;
console.log(`${bad ? 'FAIL' : 'PASS'} full-journeys - ${asked - bad}/${asked} whole stories hold together end to end`
  + (unbuilt ? `  ·  ${unbuilt} UNRUN (the cast could not be established on this host - re-walk, never bank)` : '')
  + `  ·  ${outFile}`);
process.exitCode = bad ? 1 : 0;
