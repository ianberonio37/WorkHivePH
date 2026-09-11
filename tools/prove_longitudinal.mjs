// prove_longitudinal — the long-arc journeys (T186, T187, T188, T189, T190, T193, T194), 2026-09-07.
//
// Seven rows about time. Every other lens in this program asks what happens in a session; these ask what
// happens across a year, which is the timescale a maintenance department actually buys on. A tool that
// is delightful on day one and useless in month three has failed, and it fails quietly - nobody files a
// bug for "I stopped opening it".
//
//   L1 week one       a person returning on day two finds their own work waiting, not an empty start
//                     screen that makes yesterday feel wasted (T186)
//   L2 month three    accumulated history PAYS BACK: the trend, the MTBF, the repeat-failure - things
//                     that are impossible on day one and are the whole reason to keep logging (T187)
//   L3 worth it       a person can see what they got. A renewal decision made on a feeling is a
//                     renewal decision made against you. (T188)
//   L4 the quiet plant a shutdown month must not look like a broken platform: zero activity is a real
//                     state and has to be SAID, not rendered as an empty dashboard (T189)
//   L5 crew churn     when half the crew changes, the hive's knowledge stays with the HIVE - the
//                     records survive the person who wrote them (T190)
//   L6 escalation     when the platform cannot help itself, a person can reach someone, and carries
//                     enough context with them to be helped (T193)
//   L7 the ceiling    a power user has somewhere to go: bulk, export, an API, something past the
//                     surface everyone else uses (T194)
//
// ★MEASURED AGAINST REAL ACCUMULATED DATA, NOT A FRESH SEED. Every one of these questions is about what
// history makes possible, so a database with a day of rows cannot answer them. The oldest and largest
// hive on this instance is used, and the span of its data is stated so a reader knows what was asked.
//
//   node tools/prove_longitudinal.mjs
import { execSync } from 'node:child_process';
import { readdirSync, readFileSync, existsSync } from 'node:fs';

const psql = (sql) => { try { return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim(); } catch { return ''; } };
const read = (f) => { try { return readFileSync(f, 'utf8'); } catch { return ''; } };
const pages = readdirSync('.').filter((f) => f.endsWith('.html'));
const anyPage = (rx) => pages.filter((f) => rx.test(read(f)));
const fns = existsSync('supabase/functions') ? readdirSync('supabase/functions') : [];

let bad = 0;
const say = (ok, id, line, detail) => {
  if (!ok) bad++;
  console.log(`  ${ok ? 'ok ' : 'BAD'} ${id.padEnd(20)} ${line}`);
  if (!ok && detail) console.log(`        ${detail.slice(0, 158)}`);
};

// the hive with the most history is the only one that can answer a question about history
const HIVE = psql("select hive_id from logbook where hive_id is not null group by 1 order by count(*) desc limit 1");
const span = psql(`select (max(date) - min(date))::text || ' days, ' || count(*)::text || ' entries' from logbook where hive_id = '${HIVE}'`);
console.log(`  the hive under test holds ${span || 'no history'}`);

// ── L1 · does day two find yesterday's work? ─────────────────────────────────────────────────────
{
  // the work a person did yesterday has to be THEIRS and findable: attributed, dated, and filterable
  const attributed = psql(`select count(*) from logbook where hive_id = '${HIVE}' and worker_name is not null`);
  const total = psql(`select count(*) from logbook where hive_id = '${HIVE}'`);
  const mine = anyPage(/my (entries|logbook|work|tasks)|aking mga entry|filter.{0,20}worker|worker_name.{0,30}eq/i);
  say(Number(attributed || 0) === Number(total || 0) && mine.length > 0, 'L1 week one',
    `${attributed} of ${total} entries carry the person who wrote them, and ${mine.length} page(s) let someone see their own`,
    Number(attributed || 0) < Number(total || 0) ? `${Number(total) - Number(attributed)} entries have no author, so the person who wrote them cannot find them again`
      : 'no page lets a person filter to their own work, so returning on day two means scrolling the whole hive to find yesterday');
}

// ── L2 · does three months of history pay back? ──────────────────────────────────────────────────
{
  // the analyses that are IMPOSSIBLE on day one - the whole argument for logging every day
  const wantsHistory = psql("select string_agg(proname, ', ') from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and proname ~ '(mtbf|mttr|trend|failure_rate|repeat|seasonal|forecast)'");
  const months = psql(`select count(distinct date_trunc('month', date)) from logbook where hive_id = '${HIVE}'`);
  // and a surface that shows the payback rather than a function nobody calls
  const surfaced = anyPage(/mtbf|mttr|trend|repeat failure|failure rate/i);
  say(!!wantsHistory && Number(months || 0) >= 3 && surfaced.length > 0, 'L2 month three',
    `${months} distinct month(s) of history; analyses that need it: ${(wantsHistory || 'none').slice(0, 64)}; surfaced on ${surfaced.length} page(s)`,
    !wantsHistory ? 'nothing in the database computes anything that needs history - a year of logging buys the same view as a day'
      : Number(months || 0) < 3 ? `only ${months} month(s) of data, so the payback lens is unmeasured rather than clean`
      : 'the analyses exist and no page shows them, so the payback is real and invisible');
}

// ── L3 · can a person see what they got? ─────────────────────────────────────────────────────────
{
  // ★"29 PAGES STATE WHAT THE PLATFORM IS WORTH" WAS THE WORD "saved" IN EVERY SAVE TOAST. A renewal
  // claim is a FIGURE attached to a PERIOD - pesos, hours, a percentage, over a month or a year - not a
  // verb that appears whenever a form succeeds. The first pass matched /saved/ and read 29 pages as
  // making a value case; a number that good is the probe, not the product.
  const VALUE = /(₱|PHP\s?)[\d,]{3,}|[\d.]+\s*(hours?|hrs?)\s+(saved|avoided|back)|\b\d{1,3}%\s*(cheaper|less|reduction|fewer|savings)|(payback|roi|cost avoided|value delivered)\b/i;
  const PERIOD = /(this|last|per|a)\s+(month|quarter|year)|90 days|12 months|year to date|since you (joined|started)/i;
  const roi = pages.filter((f) => { const src = read(f); return VALUE.test(src) && PERIOD.test(src); });
  const counted = psql(`select count(*) from logbook where hive_id = '${HIVE}' and date >= now() - interval '90 days'`);
  say(roi.length > 0, 'L3 worth it',
    `${roi.length} page(s) put a FIGURE against a PERIOD (${roi.slice(0, 3).join(', ') || 'none'}); ${counted} entries logged in the last 90 days to base it on`,
    'no page puts a number against a period, so the renewal decision is made on a feeling - and a feeling at renewal time is a decision made against you');
}

// ── L4 · does a quiet plant look quiet, or broken? ───────────────────────────────────────────────
{
  // a shutdown month is a REAL state; an empty dashboard that says nothing reads as a broken platform
  const honest = anyPage(/no (activity|entries|data) (yet|for|in)|nothing (logged|recorded) (yet|in)|quiet|no work logged/i);
  const dashboards = ['analytics.html', 'shift-brain.html', 'alert-hub.html', 'dayplanner.html'].filter((f) => pages.includes(f));
  const silent = dashboards.filter((f) => !honest.includes(f));
  say(silent.length === 0, 'L4 the quiet plant',
    `${dashboards.length - silent.length} of ${dashboards.length} dashboard(s) say in words when there is nothing to show`,
    `${silent.join(', ')} render an empty view with no sentence, so a shutdown month is indistinguishable from a platform that has stopped working`);
}

// ── L5 · does the hive keep what the leaver knew? ────────────────────────────────────────────────
{
  // ★ASSERTING THAT A SENTENCE EXISTS IS NOT ASSERTING THAT RECORDS SURVIVE. The first pass found zero
  // entries by former members (nobody has left this hive), so it fell back to checking that the erasure
  // copy PROMISES records stay - a promise is not a proof. Make someone leave, and read the hive again.
  const author = psql(`select worker_name from logbook where hive_id = '${HIVE}' group by 1 order by count(*) desc limit 1`);
  const before = psql(`select count(*) from logbook where hive_id = '${HIVE}' and worker_name = '${author}'`);
  let during = '', after = '';
  if (author) {
    psql(`update hive_members set status = 'kicked' where hive_id = '${HIVE}' and worker_name = '${author}'`);
    during = psql(`select count(*) from logbook where hive_id = '${HIVE}' and worker_name = '${author}'`);
    psql(`update hive_members set status = 'active' where hive_id = '${HIVE}' and worker_name = '${author}'`);
    after = psql(`select count(*) from logbook where hive_id = '${HIVE}' and worker_name = '${author}'`);
  }
  const preserves = /preserv|stay with the team|remain|records stay/i.test(read('index.html')) || /records stay/i.test(read('hive.html'));
  const survived = !!author && before === during && during === after && Number(before || 0) > 0;
  say(survived && preserves, 'L5 crew churn',
    `${author}'s ${before} entries survive their removal from the roster (${during} while off it, ${after} restored), and the erasure path SAYS records stay: ${preserves}`,
    !survived ? `${author}'s entries did not survive their removal (${before} -> ${during}) - a hive loses its own history when a person leaves`
      : 'the records survive but nothing states it, so a hive cannot tell whether its history outlives its turnover');
}

// ── L6 · when the platform cannot help itself ────────────────────────────────────────────────────
{
  const reach = anyPage(/contact (us|support)|report (a )?(problem|bug|issue)|feedback|help@|support@/i);
  // context carried with them: a version, a page, an id - so the person answering is not starting blind
  const carriesContext = anyPage(/app v|build|wh-feedback|ref \d|version/i);
  const feedbackSink = psql("select count(*) from information_schema.tables where table_schema='public' and table_name ~ '(feedback|support|ticket|bug)'");
  say(reach.length > 0 && Number(feedbackSink || 0) > 0, 'L6 escalation',
    `${reach.length} page(s) offer a way to reach someone, ${carriesContext.length} carry a version or reference with it, landing in ${feedbackSink} table(s)`,
    reach.length === 0 ? 'no page offers any way to reach a person, so a platform that cannot help itself leaves nobody to ask'
      : 'a report has nowhere durable to land, so it is sent into a channel nobody can search later');
}

// ── L7 · is there anywhere for a power user to go? ───────────────────────────────────────────────
{
  const bulk = anyPage(/bulk|import|csv|paste .{0,20}rows|select all/i);
  const exportFns = fns.filter((d) => /export|report|api|intelligence/i.test(d));
  const api = fns.filter((d) => /^(intelligence-api|platform-gateway)$/.test(d));
  say(bulk.length > 0 && exportFns.length > 0, 'L7 the ceiling',
    `${bulk.length} page(s) offer bulk or import, ${exportFns.length} function(s) export or serve data, ${api.length} of them a general API`,
    'a person who outgrows the forms has nowhere to go - no bulk path, no export, no API - so the ceiling is the first screen');
}

console.log(`${bad ? 'FAIL' : 'PASS'} longitudinal - day two finds yesterday, three months pay back, the value is stated, a quiet plant says so, records survive their author, escalation lands somewhere, and a power user has a ceiling to reach`);
process.exitCode = bad ? 1 : 0;
