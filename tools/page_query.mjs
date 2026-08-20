// page_query.mjs — the ONE answer to "what does this page need in its URL to be itself?"
//
// WHY THIS EXISTS. `project-report.html` returns early at :344 unless the URL carries `?project_id=`:
//
//     const projectId = params.get('project_id');
//     if (!projectId) { $('tb-title').textContent = 'No project specified'; …; return; }
//
// so `loadAndRender()` — and the four project queries, and the skeleton the page renders while they
// run (:353, "G1 (FF1): canonical skeleton in the summary section") — NEVER EXECUTE. Ten provers
// navigate to `${ORIGIN}/project-report.html` with no query string. Every one of them has been
// measuring an empty shell and grading it as the page.
//
// The cost was a confident false verdict: CC's `fail_slow` reported "a 6s read showed NO busy
// indicator … the person is left looking at a still page" for a page that ships exactly the affordance
// it went looking for, in a code path the walk never reached. That is the same shape as a lens scoped
// to 3% of the page, or a fixture whose dead data invented page defects: the instrument measured
// something real and then attributed it to the wrong thing.
//
// A PARAMLESS WALK IS NOT A FAILED WALK — IT IS A WALK OF A DIFFERENT PAGE, and that is precisely why
// nothing caught it. The shell renders, it is signed in, it is 200 OK, it has chrome and text and a
// nav bar. There is no error anywhere. It simply is not the surface the row claims to be about.
//
// THE ID IS RESOLVED LIVE, NEVER PINNED. A hardcoded uuid rots the moment the seed data changes, and a
// prover that silently walks a 404'd project is back to measuring a shell — just a different one. So
// this asks the database for a project that actually exists in the test hive, and returns null if
// there is none, so the caller can report UNGRADED instead of inventing a reading.
import { execSync } from 'node:child_process';

const DB_CONTAINER = process.env.WH_DB_CONTAINER || 'supabase_db_workhive';
// ★ RESOLVE THE HIVE FROM THE ACCOUNT, NEVER FROM A PINNED CONSTANT. `WH_TEST_HIVE` defaults to
// 636cf7e8 across this toolbox, described in live_page_journeys.mjs:62-66 as "the real Baguio Textile
// Mills hive both accounts belong to". Measured 2026-08-14: this account's ONLY membership is
// 084c113b (Baguio Textile Mills, 4 projects); 636cf7e8 holds none of its rows. That comment was
// itself written to fix a stale hive constant — the same drift, one hive later, and it fails the same
// silent way: every read scoped to the pinned hive returns 0 rows under RLS, the page renders empty,
// and the walk grades an empty page as the page. An id in a config file cannot notice it went stale;
// a membership query cannot go stale.
const TEST_UID = process.env.WH_TEST_UID || 'bcb5a6e3-fb12-4238-bc1e-ffeb48f60d53';

// ★ ONE LINE, ALWAYS. execSync goes through cmd.exe on Windows, where a NEWLINE ENDS THE COMMAND —
// a prettily-wrapped SQL string ran as `psql -c "select … from projects p join project_items i on
// i.project_id = p.id` with the quote unterminated and the `where … group by … limit 1` line lost.
// The join then returned one row PER ITEM and the "id" came back as a 90-line blob, which would have
// been pasted straight into `?project_id=` — a URL that resolves to no project, i.e. back to the
// empty shell this module exists to prevent, but silently and with a plausible-looking id at the
// front. So: collapse whitespace before the string ever reaches the shell, and refuse anything that
// is not exactly one uuid on the way out.
function q(sql) {
  try {
    const oneLine = sql.replace(/\s+/g, ' ').trim();
    const out = execSync(
      `docker exec ${DB_CONTAINER} psql -U postgres -d postgres -t -A -c "${oneLine.replace(/"/g, '\\"')}"`,
      { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
    // A multi-row answer means the query was not the one intended. Taking `[0]` would paper over
    // exactly that, so an unexpected shape returns nothing and the caller reports UNGRADED.
    if (!out || out.includes('\n')) return '';
    return /^[0-9a-f-]{36}$/i.test(out) ? out : '';
  } catch { return ''; }
}

// Pages whose identity depends on a URL parameter. Each entry resolves LIVE and returns '' when it
// cannot, which the caller must treat as "do not grade this page" rather than "walk it bare".
const RESOLVERS = {
  'project-report': () => {
    // Prefer a project with items — one with none renders its own (legitimate) empty sections, which
    // is a third state again and not the one these rows are about. Scoped through hive_members so the
    // project is one this identity can actually READ; a project id from a hive the account is not in
    // passes the URL check and then returns 0 rows under RLS, which looks exactly like a broken page.
    const pid = q(`select p.id from projects p
                     join hive_members hm on hm.hive_id = p.hive_id
                     left join project_items i on i.project_id = p.id
                    where hm.auth_uid = '${TEST_UID}'
                    group by p.id, p.created_at
                    order by count(i.id) desc, p.created_at limit 1;`);
    return pid ? `?project_id=${pid}` : '';
  },
};

const _cache = new Map();

/**
 * The query string a page needs, or '' if it needs none.
 * Returns '' ALSO when a required id could not be resolved — callers must check `needsQuery(page)`
 * to tell "needs nothing" apart from "needed something and we could not get it".
 */
export function pageQuery(page) {
  const name = String(page).replace(/\.html$/, '');
  if (!RESOLVERS[name]) return '';
  if (!_cache.has(name)) _cache.set(name, RESOLVERS[name]());
  return _cache.get(name);
}

/** True when this page cannot be honestly walked without a parameter. */
export function needsQuery(page) {
  return Object.prototype.hasOwnProperty.call(RESOLVERS, String(page).replace(/\.html$/, ''));
}

/** `${ORIGIN}/${page}.html` plus whatever that page needs to actually be itself. */
export function pageUrl(origin, page) {
  const name = String(page).replace(/\.html$/, '');
  return `${origin}/${name}.html${pageQuery(name)}`;
}

/**
 * Why a page cannot be graded, or null if it can. Lets a prover bank UNGRADED with a reason instead
 * of a verdict it has no standing to give.
 */
export function ungradableReason(page) {
  const name = String(page).replace(/\.html$/, '');
  if (!needsQuery(name)) return null;
  return pageQuery(name) ? null
    : `${name} requires a URL parameter and none could be resolved from the test hive — walking it `
      + 'bare measures its "nothing specified" shell, not the page';
}

if (process.argv[1] && process.argv[1].endsWith('page_query.mjs')) {
  for (const p of Object.keys(RESOLVERS)) {
    const qs = pageQuery(p);
    console.log(`${p}: ${qs || 'UNRESOLVED'}${qs ? '' : ' — ' + ungradableReason(p)}`);
  }
}
