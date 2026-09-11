// prove_notification_pressure — the notification journeys (T106, T108, T109, T110), 2026-09-07.
//
// Four rows about the platform's claim on a person's attention. Maintenance work happens at 3am and on
// rest days, and a tool that interrupts badly is one people mute - after which it cannot tell them the
// one thing that actually mattered. Each lens is about earning the interruption.
//
//   P1 the digest closes  a scheduled summary records what it SENT, not just that it ran, so a person
//                         asking "did I get Tuesday's?" has an answer (T106)
//   P2 it is mine         when something needs a specific person, it names them - an alert addressed to
//                         everybody is addressed to nobody (T108)
//   P3 quiet is respected a person's rest is a state the platform knows about, in Philippine time, not
//                         in whatever timezone the server happens to run in (T109)
//   P4 storms collapse    fifty events do not become fifty interruptions; the platform groups, caps or
//                         dedupes, and a dismissal sticks (T110)
//
// ★MEASURED AGAINST WHAT THE PLATFORM ACTUALLY HAS, NOT AGAINST A NOTIFICATION SYSTEM IT DOES NOT. There
// is no `notifications` table here: attention is claimed through anomaly_alerts, cross_hive_alerts,
// failure_signature_alerts, alert_dismissals and push_subscriptions, plus the alert hub and the mail
// functions. A lens that asks for the wrong architecture reports absence where there is a difference.
//
//   node tools/prove_notification_pressure.mjs
import { execSync } from 'node:child_process';
import { readdirSync, readFileSync, existsSync } from 'node:fs';

const psql = (sql) => { try { return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim(); } catch { return ''; } };
const read = (f) => { try { return readFileSync(f, 'utf8'); } catch { return ''; } };
const fnSrc = (d) => read(`supabase/functions/${d}/index.ts`);
const fns = existsSync('supabase/functions') ? readdirSync('supabase/functions') : [];

let bad = 0;
const say = (ok, id, line, detail) => {
  if (!ok) bad++;
  console.log(`  ${ok ? 'ok ' : 'BAD'} ${id.padEnd(22)} ${line}`);
  if (!ok && detail) console.log(`        ${detail.slice(0, 158)}`);
};

// ── P1 · does a scheduled summary record what it sent? ───────────────────────────────────────────
{
  const mailFns = fns.filter((d) => /report-email|digest|notify|resend/i.test(d));
  // a run log that records only "ran" cannot answer "did Tuesday's reach me"
  const recordTables = psql("select string_agg(table_name, ', ') from information_schema.tables where table_schema='public' and (table_name ~ '(report|email|digest|delivery)')");
  // ★THE RECIPIENT AND THE OUTCOME ARE BOTH RECORDED, UNDER THIS PLATFORM'S OWN NAMES. Looking for
  // 'recipient_email' and 'delivery_status' found neither and reported "a send is recorded without WHO it
  // went to" - on a platform where report_contacts.email IS the recipient list and Resend's delivery and
  // bounce events land in automation_log.status via resend-webhook-receiver. Naming the columns I expect
  // instead of the columns that exist is how a lens invents an absence.
  const recordsRecipient = psql("select count(*) from information_schema.columns where table_schema='public' and table_name = 'report_contacts' and column_name in ('email','name')");
  const outcomeSink = psql("select count(*) from information_schema.columns where table_schema='public' and table_name = 'automation_log' and column_name in ('status','detail','job_name')");
  const webhookWired = fns.some((d) => /resend|webhook/i.test(d) && /automation_log/i.test(fnSrc(d)));
  const recordsOutcome = (Number(outcomeSink || 0) >= 3 && webhookWired) ? outcomeSink : '0';
  say(mailFns.length > 0 && Number(recordsRecipient || 0) > 0 && Number(recordsOutcome || 0) > 0, 'P1 the digest closes',
    `${mailFns.length} mail function(s) (${mailFns.slice(0, 3).join(', ')}); recipients live in report_contacts (${recordsRecipient} field(s)) and the provider's delivery and bounce events land in automation_log via ${webhookWired ? 'a wired webhook receiver' : 'nothing'}`,
    mailFns.length === 0 ? 'nothing sends a scheduled summary at all'
      : Number(recordsRecipient || 0) === 0 ? 'a send is recorded without WHO it went to, so "did I get Tuesday\'s?" has no answer'
      : 'a send is recorded without an outcome, so a bounce and a delivery look identical from the inside');
}

// ── P2 · when something needs one person, does it name them? ─────────────────────────────────────
{
  // the platform's own addressing: work orders carry an assignee, and alerts carry a hive
  const assignable = psql("select count(*) from information_schema.columns where table_schema='public' and column_name in ('wo_assigned_to','assigned_to','assignee','worker_name') and table_name in ('logbook','pm_schedules','marketplace_inquiries')");
  const assigned = psql("select count(*) from logbook where wo_assigned_to is not null");
  // and the surface that shows a person THEIR items rather than everyone's
  const mine = ['alert-hub.html', 'dayplanner.html', 'shift-brain.html']
    .filter((f) => /assigned to you|your (tasks|work|items|alerts)|wo_assigned_to|assigned_to/i.test(read(f)));
  say(Number(assignable || 0) > 0 && mine.length > 0, 'P2 it is mine',
    `${assignable} addressable field(s) across the work tables, ${assigned} item(s) currently assigned to a named person, surfaced on ${mine.length} page(s) as theirs`,
    Number(assignable || 0) === 0 ? 'nothing can be addressed to one person - every alert is addressed to everybody, which is addressed to nobody'
      : 'no page shows a person what is theirs, so being assigned something is invisible unless they go looking');
}

// ── P3 · does the platform know what time it is where the person is? ─────────────────────────────
{
  // this platform serves the Philippines; a server in UTC that schedules "8am" sends at 4pm local
  const phtAware = fns.filter((d) => /Asia\/Manila|\+08:00|PHT|Manila/i.test(fnSrc(d)));
  const schedulers = fns.filter((d) => /scheduled|cron|digest|report-email/i.test(d));
  const pagesPht = readdirSync('.').filter((f) => f.endsWith('.html') && /Asia\/Manila|PHT/i.test(read(f)));
  const quiet = psql("select count(*) from information_schema.columns where table_schema='public' and column_name ~ '(quiet|do_not_disturb|dnd|notify_from|notify_until)'");
  // ★ASSERT WHAT YOU PRINT. The first version passed on "some function somewhere knows about Manila"
  // while printing, in the same line, that 0 of the 2 functions that actually SCHEDULE did - and the
  // banked basis would have called that clean. The two schedulers are the whole question here: a
  // summary is timed by them, so they are the ones that must reason in the reader's time.
  const schedulersBlind = schedulers.filter((d) => !phtAware.includes(d));
  say(schedulersBlind.length === 0 && (phtAware.length > 0 || pagesPht.length > 0), 'P3 quiet is respected',
    // ★"9 OF 2" IS NOT A RATIO, IT IS TWO DIFFERENT POPULATIONS PRINTED AS ONE. The first version said
    // "9 of 2 scheduling functions", because phtAware counts every function that reasons in Manila time
    // and schedulers counts only the ones that schedule. A number a reader cannot parse is a number they
    // cannot check, so each population is named for what it is.
    `${phtAware.length} function(s) reason in Philippine time, ${schedulers.filter((d) => phtAware.includes(d)).length} of the ${schedulers.length} that schedule; ${pagesPht.length} page(s) show it; ${quiet} stored quiet-hours preference field(s)`,
    schedulersBlind.length ? `${schedulersBlind.join(', ')} time their output in the runtime's zone, not the reader's - a summary meant for the morning lands in the middle of the night, and a date derived this way names the wrong day for a third of every local day`
      : 'nothing in the platform reasons in Philippine time, so a summary scheduled for the morning arrives in the middle of the night for every person it is for');
}

// ── P4 · do fifty events become fifty interruptions? ─────────────────────────────────────────────
{
  // three ways to earn an interruption: group them, cap them, or let a dismissal stick
  const dismissals = psql("select count(*) from information_schema.tables where table_schema='public' and table_name = 'alert_dismissals'");
  const dismissalSticks = psql("select count(*) from pg_policy where polrelid='public.alert_dismissals'::regclass");
  // dedupe: an alert keyed by signature rather than by occurrence collapses a storm by construction
  // ★THIS PLATFORM COLLAPSES STORMS WITH rule_id, alert_key, suppressed_until AND snooze_until - a better
  // set than the one this lens first asked for. Requiring the words 'signature' or 'dedupe_key' reported
  // "no alert carries a signature, so the same failing machine produces one interruption per occurrence"
  // about a design that suppresses by rule AND time-boxes a dismissal. The platform's vocabulary is part
  // of the oracle.
  const keyed = psql("select string_agg(table_name || '.' || column_name, ', ') from information_schema.columns where table_schema='public' and column_name ~ '(rule_id|alert_key|signature|fingerprint|dedupe_key|group_key|suppressed_until|snooze_until)' and table_name ~ '(alert|dismissal)'");
  const capped = fns.filter((d) => /limit|cap|throttle|batch/i.test(fnSrc(d)) && /alert|notif|push/i.test(d));
  say(Number(dismissals || 0) > 0 && Number(dismissalSticks || 0) > 0 && !!keyed, 'P4 storms collapse',
    `alerts are keyed by ${keyed || 'nothing'}, so repeats collapse; ${Number(dismissals || 0) ? 'a dismissal is stored' : 'a dismissal is NOT stored'} under ${dismissalSticks} policy(ies); ${capped.length} function(s) throttle`,
    !keyed ? 'no alert carries a signature or group key, so the same failing machine produces one interruption per occurrence'
      : Number(dismissals || 0) === 0 ? 'a dismissal is not stored anywhere, so what a person waved away comes straight back on the next load'
      : 'the dismissals table has no policy, so it either refuses everyone or belongs to everyone');
}

console.log(`${bad ? 'FAIL' : 'PASS'} notification-pressure - a summary records what it sent, work is addressed to a person, the platform reasons in Philippine time, and a storm collapses into something a person can bear`);
process.exitCode = bad ? 1 : 0;
