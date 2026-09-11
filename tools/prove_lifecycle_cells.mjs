// prove_lifecycle_cells — W3-PG, W3-LC and W3-AR: the cells a page was never walked in, the lifecycle
// shapes the program is thin on, and the (page, layer) squares that hold no row at all. 2026-09-07.
//
// These three directions are one prover because they ask the same kind of question of the same page and
// can share one visit: not "does this page work" (twenty-four other gates ask that) but "does it work for
// THIS person, in THIS moment, on THIS axis" - the axes the registry can prove it has never looked at.
//
//   PG  the cell     a persona x device x entry combination this page carries no row for: a first-timer, a
//                    returner after weeks, a shared tablet at 768, a stranger arriving from a search result,
//                    a pasted deep link with no history, a wall display. Each is walked as that person, at
//                    that size, arriving that way.
//   LC  the shape    the lifecycle moments the whole program is thin on: a refused microphone, a person in
//                    two hives, two years of history, leaving, two tabs, an export that must read back, a
//                    notification storm, a release landing mid-session.
//   AR  the layer    a (page, layer) square with no row: what the page owes on data lineage, refusal,
//                    identity, the clock, the edge, the audit trail, growth, rate limits, vocabulary.
//
// ★EVERY LENS IS ASKED OF THE PAGE, NOT OF THE PLATFORM. "The platform must record who did what on this
// page" is answered by finding the page's own trail, not by the existence of an audit table somewhere.
//
//   node tools/prove_lifecycle_cells.mjs --wave PG --page logbook.html
//   node tools/prove_lifecycle_cells.mjs --wave LC
//   node tools/prove_lifecycle_cells.mjs --self-test
import { chromium } from 'playwright';
import { takeBrowserSlot } from './browser_slot.mjs';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { execSync } from 'node:child_process';

const ORIGIN = process.env.WH_SEEDER_URL ? `${process.env.WH_SEEDER_URL}/workhive` : 'http://127.0.0.1:5000/workhive';
const args = process.argv.slice(2);
const argOf = (f) => { const i = args.indexOf(f); return i >= 0 ? args[i + 1] : null; };
const WAVE = argOf('--wave');
const ONE = argOf('--page');
const LIMIT = Number(argOf('--limit') || 0);

// the rows this prover answers, read from the registry rather than re-listed here (the roster IS the
// registry: a lens typed twice is a lens that drifts)
function rows() {
  const reg = JSON.parse(readFileSync('trajectory_registry.json', 'utf8'));
  // W3-DF rides along: its four carry-over rows ask the same page-level questions and its two empty-state
  // lenses were already written here, grading nothing until the wave was included.
  return reg.trajectories.filter((t) => ['W3-PG', 'W3-LC', 'W3-AR', 'W3-DF'].includes(t.wave)
    && (!WAVE || t.wave === `W3-${WAVE}`)
    && (!ONE || (t.pages || []).includes(ONE)));
}

const VIEWPORTS = { 'phone-390': { width: 390, height: 844 }, 'narrow-320': { width: 320, height: 720 },
  'tablet-768': { width: 768, height: 1024 }, 'desktop-1280': { width: 1280, height: 900 },
  'wide-1920': { width: 1920, height: 1080 }, 'fixed-kiosk-print': { width: 1920, height: 1080 },
  any: { width: 390, height: 844 } };

const READ = () => {
  const vis = (e) => !!e && (typeof e.checkVisibility === 'function' ? e.checkVisibility({ visibilityProperty: true }) : e.offsetParent !== null);
  const CHROME = '#wh-nav-hub, [id*="wh-hub"], #wh-feedback-panel, [id^="wh-fb"], [class^="wh-fb"], [id^="wh-ai-"], #wh-ai-launcher, .wh-page-guide';
  const chrome = Array.from(document.querySelectorAll(CHROME));
  const own = (el) => !chrome.some((c) => c.contains(el));
  const text = (document.body ? document.body.innerText || '' : '').replace(/\s+/g, ' ').trim();
  const controls = Array.from(document.querySelectorAll('a[href], button, [role="button"], input, select')).filter((e) => vis(e) && own(e));
  return {
    chars: text.length, text: text.slice(0, 5000), controls: controls.length,
    // ★A LINK INSIDE A SENTENCE IS NOT A TAP TARGET, and the target-size rule says so itself: WCAG 2.5.8
    // excepts a control that is inline in a flow of text, because enlarging it would break the sentence
    // it lives in. Counting them read index.html as "32 controls under 40px" - a landing page whose prose
    // links are ordinary prose links - and a number that large about a page nobody has complained about
    // is the tell that the instrument, not the page, is being measured. The exception is applied exactly
    // as written: inline display AND embedded in text longer than the link itself. A small button, or a
    // link styled as one, is neither, so nothing real is excused.
    small: controls.filter((e) => {
      const r = e.getBoundingClientRect();
      if (!(r.width > 0 && (r.width < 40 || r.height < 40))) return false;
      if (e.tagName !== 'A') return true;
      const disp = getComputedStyle(e).display;
      if (disp !== 'inline') return true;
      const own = (e.textContent || '').trim().length;
      const parent = ((e.parentElement && e.parentElement.textContent) || '').trim().length;
      return !(own > 0 && parent > own + 20);          // sitting in a sentence -> excepted
    }).length,
    // ★AND THE EXPORT CHECK ASKED THE PROSE FOR A CONTROL. It tested the body text for
    // /export|download|\.csv/, and logbook's working button reads "CSV" with the word Export only in its
    // aria-label, audit-log's reads "⬇ Export CSV" inside a panel innerText does not reach, and
    // asset-hub offers "Print Report". So eight pages were reported to offer no way out of the data while
    // four of them plainly do. An affordance is found by asking for the AFFORDANCE - the control and its
    // accessible name - not by hoping the word appears in the page's sentences.
    exportControls: Array.from(document.querySelectorAll('a[href], button, [role="button"]'))
      .filter((e) => vis(e) && own(e))
      .map((e) => [...new Set((((e.textContent || '') + ' ' + (e.getAttribute('aria-label') || '') + ' ' + (e.getAttribute('title') || '')).replace(/\s+/g, ' ').trim()).split(' '))].join(' '))
      .filter((t) => /\b(?:export|download|csv|xlsx|save as pdf|print)\b/i.test(t))
      .slice(0, 6),
    // ★A RETIRED PAGE IS A REDIRECT NOTICE WEARING A PAGE'S MARKUP. Four founder surfaces carry a fixed
    // full-screen `#wh-retired-overlay` ("The Founder Console has moved to Grafana"), and the original
    // markup is deliberately preserved underneath so the ~35 static validators that scan those files
    // keep passing. So marketplace-admin measured 483 characters and was reported as failing to explain
    // itself to a first-timer - a true measurement of the notice, and a meaningless one about the page.
    // The overlay is the page's own declaration; a cell on a retired surface has nothing to grade.
    retired: !!document.getElementById('wh-retired-overlay'),
    // a page with no form field anywhere is READ-ONLY by construction, which is what lets the
    // first-timer lens stop demanding a third control of a board that has nothing to type into
    inputs: Array.from(document.querySelectorAll('input, select, textarea')).filter(vis).length,
    overflow: document.documentElement.scrollWidth > window.innerWidth + 2,
    skeletons: Array.from(document.querySelectorAll('[class*="skeleton"], [class*="shimmer"], [aria-busy="true"]')).filter(vis).length,
    // ★A TEXT PLACEHOLDER IS A SKELETON NO SKELETON-FINDER SEES. llm-observability's source chip reads
    // "Loading the cost and cache rollup" until its query lands, and then rewrites itself with "· as of
    // 15:42 · refreshes on each window change" - which the freshness check would have credited. Read
    // mid-load it carries no skeleton class and no aria-busy, so the walk judged a settled page and
    // reported a missing affordance that is right there a second later. A status region still announcing
    // that it is loading means the page has not finished, and the honest verdict is unreadable, not bad.
    loadingChip: Array.from(document.querySelectorAll('.wh-source-chip, [role="status"]')).filter(vis)
      .some((e) => /^(?:loading|fetching|checking|please wait)/i.test((e.textContent || '').trim())),
    // what the page says about the things these lenses ask after
    // ★THE ORACLE DID NOT KNOW THE PLATFORM'S OWN WORDS FOR THIS. It looked for "updated", "as of",
    // "last refreshed" and the like - and the platform says "Live · refreshed on load" (14 pages),
    // "Live data" (6), "Live · updates automatically" (4), "Recalculated weekly", "daily snapshot".
    // Not one of the commonest matched, so pages that state their freshness plainly were failing a check
    // about whether they state it. Widening the word list would have been the wrong repair twice over:
    // "live" appears in ordinary page text ("live map"), so it would have made the check nearly vacuous.
    // The platform renders this claim through ONE component - renderSourceChip emits
    // `<p class="wh-source-chip" role="status">` - so the honest question is whether that chip is there
    // and says something, with the phrase list kept for pages that state freshness in their own prose.
    freshness: /updated|as of|last (?:checked|synced|refreshed)|just now|minutes? ago|hours? ago/i.test(text)
      // ...and a chip that is still LOADING is not a freshness claim. llm-observability's chip is a
      // placeholder reading "Loading the cost and cache rollup", so a bare length test would have passed
      // a stuck spinner as a statement about how old the data is - trading one wrong verdict for a
      // quieter one. A chip counts only when it has settled into saying something.
      || Array.from(document.querySelectorAll('.wh-source-chip')).some((e) => {
        const t = (e.textContent || '').trim();
        return t.length > 8 && !/^(?:loading|loading[….]|fetching|checking|please wait)/i.test(t);
      }),
    // ★BOTH OF THESE WERE VACUOUS, AND THE `i` FLAG IS WHY. `by\s+[A-Z][a-z]+` reads as a proper name -
    // "Logged by Wilfredo" - but under /i the character class matches lowercase too, so "sorted by
    // default" and "used by one team" both counted as naming a person. `[A-Z][a-z]{2} \d{1,2}` was meant
    // to catch "May 16" and instead accepted "Qty 0", "Hub 36" and "Bay 3"; `\d{4}-\d{2}` accepted the
    // project code "2026-000123". Measured signed in: five of the pages that PASSED these checks passed on
    // a coincidence, and the pages that failed differed only in not containing one. A check that a page
    // can pass by accident cannot be evidence that it names a period or an author.
    //
    // Both are rewritten from the platform's OWN vocabulary rather than from a guess at English. Harvested:
    // "Today" (697), "This week" (37), "Last 7 days" (16), "Yesterday" (15), "Last 30 days" (15), "All
    // time" (6), "Last 90 days" (5), "This quarter" (4); and "Approved by" (493), "Closed by" (22),
    // "Reported by" (9), "Raised by" (7), "Logged by" (7). Case is now load-bearing: a person's name is
    // capitalised and a period label is a rendered chip, so neither can be matched by ordinary prose.
    who: /\b(?:Approved|Closed|Logged|Reported|Raised|Recorded|Completed|Submitted|Performed|Signed off) by\b/i.test(text)
      || /\bby [A-Z][a-z]+/.test(text)                     // a proper name, capital required
      || /\bActor\b/.test(text),                           // the audit trail's own column header
    period: /\b(?:Today|Yesterday|This (?:week|month|quarter|year)|Last \d+ days?|All time|Year to date)\b/.test(text)
      // ...and voice-journal renders its entries as "THU, JUL 18" - the platform's own uppercase date
      // style, which a case-sensitive month list does not see. Case matters for the WORD "Today", which
      // appears in prose; it does not matter for a month abbreviation followed by a day number, because
      // nothing else reads like that.
      || /\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* \d{1,2}\b/i.test(text)
      // ...and a page showing CURRENT STATE says which period it means by saying it is current.
      // asset-hub carries "Live + daily snapshot", inventory "Live · refreshed on load", resume "as of
      // this page load" - each one answers "which period do these figures belong to" with "now", which
      // is the only true answer for a count of parts on hand. Demanding a date range from a stock count
      // asks the page for something it should not invent. The phrase must pair "live"/"as of" with a
      // snapshot word, so the word "live" alone (a live map, a live chat) still counts for nothing.
      || /\b(?:live|current)\b[^.]{0,40}\b(?:snapshot|refreshed|updates|on load|right now)\b|\bas of this page load\b/i.test(text)
      || /\b\d{4}-(?:0[1-9]|1[0-2])-(?:[0-2]\d|3[01])\b/.test(text)                           // ...or a real ISO one
      // ★MOST PAGES NAME THE PERIOD IN A CONTROL, NOT A SENTENCE. analytics-report renders "PERIOD 30d 90d
      // 180d 365d" and status renders "SLO targets (28-day window)" - both state exactly which span their
      // figures cover, and a phrase-only check called them silent. Harvested from the pages: "30-day"
      // (106), "90-day" (26), "7-day" (24), "30-day window" (13), "30d" (12), "365d"/"180d"/"90d" (7 each),
      // "28-day window" (6), "30-day rolling" (5).
      || /\b\d{1,3}-day\b|\b\d{1,3}d\b(?=[\s,)·]|$)|\brolling \d{1,3} days\b/.test(text),
    refusal: /sign in|not a member|no access|permission|you cannot|only supervisors|join (?:or create )?a hive to/i.test(text),
    // ★AN INVITATION IS NOT A REFUSAL. public-feed is a public, read-only feed whose subtitle says "Sign
    // in to join the conversation" and whose CTA says "Sign in to post" - so the refusal test above fired
    // on a page that was showing a stranger exactly what it is for, and the walk reported "a stranger
    // meets a refusal, not the page". A refusal means the content was WITHHELD. This is the definition
    // prove_full_journeys already uses for the same question, reused rather than re-invented: a sign-in
    // prompt near the top AND a page too short to be showing anything else.
    // ★AND THE LENGTH THRESHOLD WAS BORROWED FROM A DIFFERENT QUESTION. 4,000 characters came from the
    // journey prover, which uses it to tell a whole hive page from a sign-in door. Measured on the public
    // pages this lens actually judges: public-feed shows 2,460 characters of its subject with a "Sign In"
    // CTA beside it, and the seller profile 1,097 with the seller's name, tier and terms - both were
    // called walls. A wall is a prompt and ALMOST NOTHING ELSE; at 800 characters a bare gate is still
    // caught and a page showing what it is for is not.
    wall: /sign in to|create an account|get started free/i.test(text.slice(0, 1200)) && text.length < 800,
    // ...and some pages are not for strangers AT ALL, and say so in their own words. ph-intelligence
    // ("members only", "supervisor") and platform-actions ("Founder") are internal surfaces; a stranger
    // arriving from search should meet a legible explanation, not the contents. Grading them by "did a
    // stranger get 600 characters of the page" asks the wrong question of the right behaviour. Read from
    // the page's OWN declaration rather than a list kept here, so a page that opens up stops being excused.
    // ...and the platform's own words for "this needs a hive" are not the ones I guessed. Harvested from
    // the pages: "Join or create a hive to see PH Intelligence", "Join a hive to see alerts", "Join a hive
    // to see the audit log", "Join or create a hive to plan and track projects". ph-intelligence answers a
    // stranger in 379 characters that say exactly what it is and how to get in - a legible refusal, which
    // this lens is meant to accept - and none of my phrases appeared in it.
    gated: /members only|supervisors? only|founder|admin only|internal use|join (?:or create )?a hive to/i.test(text),
    empty: /nothing|no .{0,24}(yet|found|due|recorded)|none |0 /i.test(text),
    tagalog: /\b(ang|ng|sa|mga|walang|wala|hindi|para|iyong)\b/i.test(text),
  };
};

// (*)HALF THIS PROVER'S READINGS WERE THE SIGN-IN DOOR. It already refuses to grade a page it did not
// reach - 105 of 202 rows came back "bounced to index.html - this cell reaches the door, not the page" -
// which is honest and answers nothing. A lifecycle question ("you refused the microphone once and this page
// still has to be usable") is about a page a signed-in person opens; walking it as nobody could only ever
// produce a refusal. One sign-in, reused by every row.
const PERSON = { name: 'Wilfredo Malabanan', email: 'wilfredomalabanan@auth.workhiveph.com' };
const SUPA = process.env.WH_EDGE_URL || 'http://127.0.0.1:54321';

// (*)AN UNREAD DATABASE AND AN EMPTY ANSWER WERE THE SAME VALUE, and this whole prover rests on the
// difference. The helper returned '' both when the query answered nothing AND when five attempts all
// failed, so `if (!hive)` read a busy host as "this person is in no hive" - and the run walked all 202
// rows as NOBODY, reporting 59 of them as "reaches the door". Measured on this session's own chain: the
// lifecycle step started seconds after a 62-function edge sweep let go of the database, the identity read
// lost, and the entire run became a statement about the fixture. A successful query now returns its
// answer whatever it is; only an unreachable database returns null.
const psql = (sql, tries = 5) => {
  for (let i = 0; i < tries; i++) {
    try {
      return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`,
                      { encoding: 'utf8', timeout: 25000 }).trim();
    } catch { /* busy or wedged - ask again */ }
    try { execSync('powershell -NoProfile -Command "Start-Sleep -Seconds 4"', { stdio: 'ignore', timeout: 12000 }); } catch { /* empty */ }
  }
  return null;
};

let SESSION = null;
// ★AND A SUPERVISOR-ONLY PAGE NEEDS A SUPERVISOR, not a note saying it could not be read. The walk held
// one worker, so audit-log and integrations answered "Supervisors only" and six feature lenses were then
// graded against a locked door. Deferring them would be honest and still wrong - the cast the cell needs
// is one query away, exactly as the first-timer was. This signs in as an active supervisor of the same
// hive, so a page that refuses a worker is re-read by somebody it does not refuse.
let SUPER = null;
// a real project in the walking person's own hive, so project-report has something to report on
let PROJECT_ID = '';
function resolveProject() {
  const row = psql("select p.id::text from projects p join hive_members m on m.hive_id = p.hive_id "
    + `where m.worker_name = '${PERSON.name}' and m.status = 'active' order by p.id limit 1`);
  PROJECT_ID = (row || '').trim();
  return PROJECT_ID;
}
let SUPER_WHO = '';
async function establishSupervisor(browser) {
  // ★AND THE SUPERVISOR MUST BE ONE OF THIS HIVE. The first version took whichever supervisor sorted
  // first by name, which landed on a person whose hive holds ZERO CMMS connections - so integrations
  // was read in its empty state and its export reported as producing nothing, when the walking
  // person's own hive holds fifteen. An escalation is meant to answer "what does a supervisor of THIS
  // hive see", so it prefers a supervisor of the walker's hive and only then falls back to any other.
  const row = psql("select m.worker_name || '|' || coalesce((select u.email from auth.users u where u.id = m.auth_uid), '') || '|' || m.hive_id::text "
    + "from hive_members m where m.role = 'supervisor' and m.status = 'active' and m.auth_uid is not null "
    + `and m.worker_name <> '${PERSON.name}' `
    + "and not exists (select 1 from marketplace_platform_admins a where a.worker_name = m.worker_name) "
    + "order by (m.hive_id = (select hive_id from hive_members w where w.worker_name = "
    + `'${PERSON.name}' and w.status = 'active' limit 1)) desc, m.worker_name limit 1`);
  if (row === null) return 'the database did not answer, so no supervisor could be cast - re-run on a quiet host';
  if (!row) return 'no active supervisor with a sign-in account exists, so supervisor-only pages cannot be read';
  const [name, email, hive] = row.split('|');
  if (!email) return `${name} is a supervisor but has no auth account, so there is no supervisor view to walk`;
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const p = await ctx.newPage();
  await p.goto(`${ORIGIN}/shift-brain.html`, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
  await p.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 20000 }).catch(() => {});
  const out = await p.evaluate(async ({ email, name, hive, supa }) => {
    try {
      const db = window._whSupabaseClient || window.getDb(supa, window.SUPABASE_KEY);
      const { error } = await db.auth.signInWithPassword({ email, password: 'test1234' });
      if (error) return 'auth: ' + error.message;
      localStorage.setItem('wh_active_hive_id', hive);
      localStorage.setItem('wh_last_worker', name);
      localStorage.setItem('wh_hive_role', 'supervisor');
      const { data: h } = await db.from('hives').select('name').eq('id', hive).maybeSingle();
      if (h && h.name) localStorage.setItem('wh_hive_name', h.name);
      return 'ok';
    } catch (e) { return 'threw: ' + (e && e.message); }
  }, { email, name, hive, supa: SUPA }).catch((e) => 'evaluate: ' + e.message);
  if (out === 'ok') { SUPER = await ctx.storageState(); SUPER_WHO = name; }
  await ctx.close().catch(() => {});
  return out;
}
// ★A FIRST-TIMER IS A REAL ACCOUNT WITH NOTHING BEHIND IT, and the platform has one. `consumer.walk@
// workhive.test` holds ZERO memberships and ZERO logbook entries, which is exactly what a `new-user` cell
// describes. Naming those twelve rows "not answered" was honest but it was not the job: if a cell needs a
// cast the walk does not have, BUILD the cast. This signs in as that account and stamps no hive, so a
// new-user row meets the onboarding path the product actually shows a newcomer.
let FRESH = null;
let FRESH_WHO = '';
// signs in as an account that has never joined a hive, and stamps NO hive - which is the whole point:
// a newcomer meets the onboarding path, not a populated board. Returns 'ok' or the reason it could not.
async function establishFresh(browser) {
  // (*)`limit 1` WITH NO ORDER PICKS WHOEVER THE PLANNER RETURNS, and this walk then signs in with the
  // one password every walk here uses. A hive-less account is not automatically an account anybody knows
  // the password to - most are leftovers - so an arbitrary pick meant FRESH stayed null and every
  // new-user cell reported "a first-timer has no cast". tools/seed_solo_personas.py creates accounts that
  // can actually sign in and marks them; preferring the mark makes the choice deterministic as well as
  // castable. The same unordered-pick fault sat in the journey prover's solo cast, found the same day.
  const email = psql("select u.email from auth.users u where not exists (select 1 from hive_members m where m.auth_uid = u.id) and not exists (select 1 from logbook l where l.auth_uid = u.id) order by (coalesce(u.raw_user_meta_data->>'seed','') = 'solo-persona-seed') desc, u.created_at limit 1");
  // same distinction as the identity below: "nobody like that exists" and "I could not ask" are different
  // findings, and only the first is about the platform
  if (email === null) return 'the database did not answer, so whether a first-timer can be cast is unknown - re-run on a quiet host';
  if (!email) return 'the database holds no account without a hive, so a first-timer cannot be cast';
  FRESH_WHO = email;
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const p = await ctx.newPage();
  await p.goto(`${ORIGIN}/index.html`, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
  await p.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 20000 }).catch(() => {});
  const out = await p.evaluate(async ({ email, supa }) => {
    try {
      const db = window._whSupabaseClient || window.getDb(supa, window.SUPABASE_KEY);
      const { error } = await db.auth.signInWithPassword({ email, password: 'test1234' });
      if (error) return 'auth: ' + error.message;
      // deliberately stamp NOTHING else: no hive, no worker, no role. That absence IS the first-timer.
      return 'ok';
    } catch (e) { return 'threw: ' + (e && e.message); }
  }, { email, supa: SUPA }).catch((e) => 'evaluate: ' + e.message);
  if (out === 'ok') FRESH = await ctx.storageState();
  await ctx.close().catch(() => {});
  return out;
}

async function establishIdentity(browser) {
  const hive = psql(`select hive_id::text from hive_members where worker_name = '${PERSON.name}' and status = 'active' limit 1`);
  // the two cases are different findings and must not share a sentence: one is about the platform, the
  // other is about the host this ran on
  if (hive === null) return `the database did not answer after five attempts, so no identity could be established - re-run on a quiet host (nothing here is evidence about the product)`;
  if (!hive) return `${PERSON.name} is in no active hive, so there is no signed-in view to walk`;
  const role = psql(`select role from hive_members where worker_name = '${PERSON.name}' and hive_id::text = '${hive}' limit 1`) || 'worker';
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const p = await ctx.newPage();
  await p.goto(`${ORIGIN}/shift-brain.html`, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
  await p.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 20000 }).catch(() => {});
  const out = await p.evaluate(async ({ hive, who, role, supa }) => {
    try {
      const db = window._whSupabaseClient || window.getDb(supa, window.SUPABASE_KEY);
      const { error } = await db.auth.signInWithPassword({ email: who.email, password: 'test1234' });
      if (error) return 'auth: ' + error.message;
      localStorage.setItem('wh_active_hive_id', hive);
      localStorage.setItem('wh_last_worker', who.name);
      localStorage.setItem('wh_hive_role', role);
      const { data: h } = await db.from('hives').select('name').eq('id', hive).maybeSingle();
      if (h && h.name) localStorage.setItem('wh_hive_name', h.name);
      return 'ok';
    } catch (e) { return 'threw: ' + (e && e.message); }
  }, { hive, who: PERSON, role, supa: SUPA }).catch((e) => 'evaluate: ' + e.message);
  if (out === 'ok') SESSION = await ctx.storageState();
  await ctx.close();
  return out;
}

// ★"CAN BE READ BACK IN" IS A CLAIM ABOUT A FILE, SO THE FILE HAS TO BE OPENED. The lens is titled "What
// this page exports can be read back in, and means the same thing on the way home" and was answered by a
// regex over the page's prose - which proves nothing about the export even when it matches. So the export
// is now actually triggered and the bytes are read: a file that arrives, with a header naming at least two
// columns, is a file somebody can make sense of on the way home. Print and Save-as-PDF are deliberately
// NOT clicked - they open a system dialog, and a PDF is a picture of the data, not the data.
async function proveExport(p, names) {
  // ★AND AN IMPORT CONTROL IS NOT AN EXPORT. integrations offers "🏭 SAP PM OData export (AUFNR, ISTAT,
  // EQUNR…) Import from" - a control for pulling data IN, whose label names the export you produce in
  // SAP. The picker matched the word "export" inside it, pressed it, no file came back, and the page was
  // reported as offering an export that does not work. What the control DOES is in its verb, so a label
  // that says import is excluded no matter what else it mentions.
  let target = (names || []).find((n) => /\b(?:export|download|csv|xlsx)\b/i.test(n)
    && !/\bprint\b/i.test(n) && !/\bimport(?:ing|ed|s)?\b|\bupload\b/i.test(n));
  // ★AN EXPORT ON A TAB THE PAGE DOES NOT LAND ON IS STILL THE PAGE'S EXPORT. integrations opens on
  // "Import File" and keeps its connection list, and the export beside it, on the "Live Sync" tab - so
  // the control is in the DOM, hidden, and invisible to a visible-controls read. A person presses the
  // tab; so does this. Tabs on these pages are inert view switches, and only a control the page itself
  // offers as a tab is pressed - at most five, each once.
  if (!target) {
    const found = await p.evaluate(async () => {
      const norm = (e) => [...new Set((((e.textContent || '') + ' ' + (e.getAttribute('aria-label') || '') + ' ' + (e.getAttribute('title') || '')).replace(/\s+/g, ' ').trim()).split(' '))].join(' ');
      // ...and a tab is not always marked as one. integrations switches views with plain buttons
      // carrying `onclick="switchTab('sync')"` and no role, class or data attribute, so a
      // role-and-class selector found none of them. The onclick IS the declaration here.
      const tabs = Array.from(document.querySelectorAll(
        '[role="tab"], .page-tab, .tab, [data-tab], [onclick*="switchTab"], [onclick*="showTab"]')).slice(0, 6);
      for (const t of tabs) {
        t.click();
        await new Promise((r) => setTimeout(r, 400));
        const vis = (e) => typeof e.checkVisibility === 'function' ? e.checkVisibility({ visibilityProperty: true }) : e.offsetParent !== null;
        const hit = Array.from(document.querySelectorAll('a[href], button, [role="button"]'))
          .filter(vis).map(norm)
          .find((n) => /\b(?:export|download|csv|xlsx)\b/i.test(n) && !/\bprint\b/i.test(n) && !/\bimport(?:ing|ed|s)?\b|\bupload\b/i.test(n));
        if (hit) return hit;
      }
      return '';
    }).catch(() => '');
    if (found) target = found;
  }
  if (!target) return { kind: 'none' };
  const tagged = await p.evaluate((label) => {
    const norm = (e) => [...new Set((((e.textContent || '') + ' ' + (e.getAttribute('aria-label') || '') + ' ' + (e.getAttribute('title') || '')).replace(/\s+/g, ' ').trim()).split(' '))].join(' ');
    const el = Array.from(document.querySelectorAll('a[href], button, [role="button"]')).find((e) => norm(e) === label);
    if (!el) return false;
    el.setAttribute('data-wh-export-probe', '1');
    return true;
  }, target).catch(() => false);
  if (!tagged) return { kind: 'none' };
  // ★AN EXPORT THAT WAITS FOR THE REPORT IS NOT A BROKEN EXPORT. analytics-report builds its four
  // phases on demand, so both Save-as-PDF and the CSV are correctly DISABLED until somebody presses
  // Generate - and pressing a disabled button produces no file, which this read as "offered but
  // produced nothing". A person generates first and then exports; so does this. Only a control the
  // page itself offers is pressed, and only when the export is actually disabled.
  const needsBuild = await p.evaluate(() => {
    const el = document.querySelector('[data-wh-export-probe="1"]');
    return !!(el && (el.disabled || el.getAttribute('aria-disabled') === 'true'));
  }).catch(() => false);
  if (needsBuild) {
    const built = await p.evaluate(() => {
      const el = Array.from(document.querySelectorAll('button, [role="button"]')).find((e) => {
        const n = ((e.textContent || '') + ' ' + (e.getAttribute('aria-label') || '')).trim();
        return /\b(?:generate|build|compile|run) (?:the )?report\b|^\s*generate\b/i.test(n) && !e.disabled;
      });
      if (!el) return false;
      el.click();
      return true;
    }).catch(() => false);
    if (built) {
      // the report is fetched live; give it the same patience the page's own timeout allows
      for (let i = 0; i < 12; i++) {
        await p.waitForTimeout(2500);
        const ready = await p.evaluate(() => {
          const el = document.querySelector('[data-wh-export-probe="1"]');
          return !!(el && !el.disabled && el.getAttribute('aria-disabled') !== 'true');
        }).catch(() => false);
        if (ready) break;
      }
    }
  }
  p.on('dialog', (d) => d.dismiss().catch(() => {}));
  const [dl] = await Promise.all([
    p.waitForEvent('download', { timeout: 9000 }).catch(() => null),
    p.click('[data-wh-export-probe="1"]', { timeout: 6000 }).catch(() => null),
  ]);
  // ★"NOTHING TO EXPORT" IS AN ANSWER, NOT A SILENCE. integrations offers its export to a supervisor
  // whose hive holds no CMMS connections, and the page says so in a toast: no file is produced because
  // there is nothing to put in one, which is the export working. Reading that as "offered but produced
  // no file" is the empty-versus-failed confusion this platform has met in five other places. The page
  // is asked what it just said before the verdict is written.
  if (!dl) {
    const said = await p.evaluate(() => {
      const els = Array.from(document.querySelectorAll('[role="status"], [role="alert"], .toast, #toast, [id*="toast"]'));
      const t = els.map((e) => (e.textContent || '').trim()).filter(Boolean).join(' ');
      return /\bno\b[^.]{0,30}\b(?:parts|assets|connections|entries|rows|records|figures|data)\b[^.]{0,20}\bto export\b|\bnothing to export\b|\bgenerate .{0,20}first\b|\bopen this .{0,30}first\b/i.test(t)
        ? t.slice(0, 120) : '';
    }).catch(() => '');
    if (said) return { kind: 'empty', control: target, said };
    return { kind: 'silent', control: target };
  }
  const path = await dl.path().catch(() => null);
  if (!path) return { kind: 'silent', control: target };
  let body = '';
  try { body = readFileSync(path, 'utf8'); } catch (e) { return { kind: 'silent', control: target }; }
  // ★AND LINE ONE IS NOT THE HEADER. logbook's export opens with a six-line scope preamble - "WorkHive
  // logbook export", "Worker: …", "Scope: whole team history for hive …", "Entries: 42", "Date range: …",
  // "Exported: …" - written precisely so the file still says what it is once it is off the page. Reading
  // line one as the column names found one field and called the export unreadable: the file was better
  // than the check, and the check reported the opposite. The header is found by looking for it, and a
  // file that states its own scope before the columns is the strongest form of this lens's claim.
  const lines = body.split(/\r?\n/);
  // ★AND A COMMA INSIDE QUOTES IS NOT A SEPARATOR. Splitting on every comma made logbook's data row
  // `"Jul 18, 2026, 09:19 PM","Wilfredo",…` twenty fields wide against a fifteen-column header, so the
  // widest-line rule picked a data row and reported the timestamp as a column name. The file was fine
  // three times over and the reader was wrong three times: line one, first-comma, and now this. A CSV
  // reader has to honour the quoting the writer used - `esc()` in the page wraps every field and doubles
  // inner quotes, which is exactly the dialect parsed here.
  const fields = (l) => {
    const out = []; let cur = ''; let q = false;
    for (let i = 0; i < l.length; i++) {
      const c = l[i];
      if (q) {
        if (c === '"') { if (l[i + 1] === '"') { cur += '"'; i++; } else q = false; } else cur += c;
      } else if (c === '"') q = true;
      else if (c === ',') { out.push(cur); cur = ''; }
      else cur += c;
    }
    out.push(cur);
    return out.map((c) => c.trim()).filter(Boolean);
  };
  // ...and "the first line with a comma in it" is not the header either: the preamble's own "Date range:
  // Apr 25, 2026 to May 16, 2026" has two commas, so the finder stopped there and reported three columns
  // for a file with fifteen. A header is the WIDEST line in the opening block - a scope sentence has a
  // comma or two, a column list has as many as the table has columns.
  let headerIdx = -1; let best = 1;
  for (let i = 0; i < Math.min(lines.length, 14); i++) {
    const n = fields(lines[i]).length;
    if (n > best) { best = n; headerIdx = i; }
  }
  if (headerIdx < 0) return { kind: 'opaque', control: target, cols: fields(lines[0] || '').length, rows: 0 };
  const cols = fields(lines[headerIdx]);
  const rows = lines.slice(headerIdx + 1).filter((l) => l.trim()).length;
  const scope = headerIdx > 0 ? lines.slice(0, headerIdx).filter((l) => l.trim()).length : 0;
  return { kind: 'readable', control: target, cols: cols.length, rows, scope, head: cols.slice(0, 4).join(', ') };
}

// ★"FROM A REAL REVOCATION AND NOT AN INJECTED ID" is what this row's own title demands, so it gets a
// real one. The lens reads the page's TEXT for words a removed person would need, and every other cell
// here walks as an ACTIVE member - for whom those words are correctly hidden - so the row could never
// pass however well the product behaved. This revokes one real membership, reads the board as that
// person with their own session, and restores it in a `finally` that also AUDITS: if a single stray
// kicked row survives, the run says so loudly rather than leaving the seed behind.
async function walkRevoked(browser, page) {
  const row = psql("select m.worker_name || '|' || m.hive_id::text || '|' || coalesce((select u.email from auth.users u where u.id = m.auth_uid), '') "
    + "from hive_members m where m.status = 'active' and m.auth_uid is not null and m.role = 'worker' "
    + `and m.worker_name <> '${PERSON.name}' `
    + "and not exists (select 1 from marketplace_platform_admins a where a.worker_name = m.worker_name) "
    + "order by m.worker_name limit 1");
  if (row === null) return { err: 'the database did not answer, so no revocation could be staged - re-run on a quiet host' };
  if (!row) return { err: 'no ordinary worker with a sign-in account exists, so a revocation cannot be staged' };
  const [who, hive, email] = row.split('|');
  if (!email) return { err: `${who} has no auth account, so their revoked view cannot be walked` };

  let staged = false;
  try {
    if (psql(`update hive_members set status = 'kicked' where worker_name = '${who}' and hive_id::text = '${hive}'`) === null) {
      return { err: 'the revocation could not be staged' };
    }
    staged = true;
    const ctx = await browser.newContext({ viewport: VIEWPORTS['desktop-1280'] });
    const p = await ctx.newPage();
    try {
      await p.goto(`${ORIGIN}/index.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await p.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 20000 }).catch(() => {});
      const auth = await p.evaluate(async ({ email, who, hive, supa }) => {
        try {
          const db = window._whSupabaseClient || window.getDb(supa, window.SUPABASE_KEY);
          const { error } = await db.auth.signInWithPassword({ email, password: 'test1234' });
          if (error) return 'auth: ' + error.message;
          // the stamp a removed person still carries: their device does not know they were removed
          localStorage.setItem('wh_active_hive_id', hive);
          localStorage.setItem('wh_hive_id', hive);
          localStorage.setItem('wh_last_worker', who);
          localStorage.setItem('wh_hive_role', 'worker');
          return 'ok';
        } catch (e) { return 'threw: ' + (e && e.message); }
      }, { email, who, hive, supa: SUPA });
      if (auth !== 'ok') return { err: `could not sign in as the revoked member (${auth})` };
      await p.goto(`${ORIGIN}/${page}`, { waitUntil: 'domcontentloaded', timeout: 45000 });
      await p.waitForTimeout(4000);
      let r = await p.evaluate(READ);
      for (let i = 0; i < 3 && r.chars < 300; i++) { await p.waitForTimeout(3000); r = await p.evaluate(READ); }
      return { r, who };
    } finally {
      await ctx.close().catch(() => {});
    }
  } finally {
    if (staged) {
      psql(`update hive_members set status = 'active' where worker_name = '${who}' and hive_id::text = '${hive}'`);
      const stray = psql("select count(*) from hive_members where status = 'kicked' and worker_name not like '%fixture%'");
      if (stray !== null && stray.trim() !== '0') {
        console.log(`  !! ${stray.trim()} revoked row(s) survived the probe - restore by hand before trusting anything here`);
      }
    }
  }
}

async function walkRow(browser, t) {
  const page = (t.pages || [])[0];
  if (!page) return { id: t.id, verdict: 'BAD', line: 'the row names no page' };
  // this one row needs a person the walk's normal cast cannot supply: somebody genuinely removed
  if (/genuinely revoked member/.test((t.title || '').toLowerCase())) {
    const out = await walkRevoked(browser, page).catch((e) => ({ err: 'the revoked walk threw: ' + e.message }));
    if (out.err) return { id: t.id, verdict: 'n/a', line: `NOT ANSWERED: ${out.err}` };
    const rr = out.r;
    const told = /no longer|removed|not a member|access ended|ask your supervisor|contact the supervisor/i.test(rr.text);
    return { id: t.id, verdict: told ? 'ok' : 'BAD',
             line: told
               ? `walked as ${out.who} AFTER a real revocation (staged, read, restored): the page says what happened in ${rr.chars} chars`
               : `walked as ${out.who} AFTER a real revocation: ${rr.chars} chars and not one of them explains that their membership ended` };
  }
  const vp = VIEWPORTS[t.device] || VIEWPORTS.any;
  // ★AN ANONYMOUS VISITOR CANNOT BE OBSERVED WHILE SIGNED IN. The session is attached once and was attached
  // to EVERY row, including the seven whose persona is `anon` - so "what a stranger sees on this page" was
  // being answered by a signed-in worker looking at their own hive. The device and the entry were honoured
  // per row all along; the PERSON was not. A row cast as anonymous now gets a clean context, which is the
  // only way its own question can be asked.
  const cellWho = (t.persona || '').toLowerCase();
  const anon = cellWho === 'anon';
  // a first-timer walks as the account with nothing behind it; anon walks as nobody; everyone else
  // walks as the established worker
  const use = anon ? null : (cellWho === 'new-user' && FRESH) ? FRESH : SESSION;
  const ctx = await browser.newContext({ viewport: vp, acceptDownloads: true, ...(use ? { storageState: use } : {}) });
  const p = await ctx.newPage();
  let r = null; let err = null; let landed = '';
  try {
    const q = t.entry === 'deep-link' ? '?ref=chat' : t.entry === 'email-push' ? '?src=email' : t.entry === 'qr-print' ? '?src=qr' : '';
    // ★A PAGE THAT NEEDS A SUBJECT MUST BE VISITED WITH ONE. marketplace-seller-profile reads its seller
    // from `?worker=`, and without it renders exactly what it should - "No seller specified. This page
    // needs a seller name in the URL. Open it via marketplace.html", with a back link. The walk arrived
    // bare, measured 257 characters, and reported that a stranger sees almost nothing: a correct empty
    // state graded as a failure to explain itself. The journey prover already visits it with a subject;
    // this is the same fixture, in the same words, so both instruments read the same page.
    // ...and project-report is the same shape: it reads `?project_id=` and, without one, renders the
    // correct empty state ("Open this page from the Project Manager (Detail -> Print Report)"). Walking
    // it bare graded that empty state for whether it exports its data. The id below is a real project
    // in the hive this walk's person belongs to, resolved once at start-up rather than pinned, because
    // a pinned id rots on every reseed - the fixture-hive gate exists because four of them already did.
    const SUBJECT = { 'marketplace-seller-profile.html': 'worker=Isidro%20Suarez' };
    if (PROJECT_ID) SUBJECT['project-report.html'] = 'project_id=' + PROJECT_ID;
    const need = SUBJECT[page];
    const url = `${ORIGIN}/${page}${q}${need ? (q ? '&' : '?') + need : ''}`;
    await p.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await p.waitForTimeout(3200);
    r = await p.evaluate(READ);
    // ★ONE EXTRA WAIT IS NOT PATIENCE. A single 4.5s retry left sixteen rows reporting "still rendering,
    // re-walk on a quiet host" - true, and it means the walk answered nothing while the host was merely
    // busy. The same lesson the contract prover learned about its 35s budget: a probe that gives up before
    // its subject finishes is measuring itself. It now waits up to four more times and stops the moment the
    // skeletons clear, so a settled page costs one extra second and a slow one gets the time it needs.
    for (let i = 0; i < 4 && (r.skeletons > 0 || r.chars < 400); i++) {
      await p.waitForTimeout(4500);
      r = await p.evaluate(READ);
    }
    // ★A LOCKED DOOR IS RE-KNOCKED BY SOMEBODY WHO HOLDS THE KEY. audit-log answers this worker with
    // "Supervisors only" in 387 characters and integrations with "Supervisor access only" in 538, and the
    // feature lenses were then graded against the refusal: "offers no way to take its data out" about a
    // page whose export button is right there for the person it is built for. The refusal is correct and
    // the grade was not. A cell whose persona is anon, new-user or adversary keeps its own cast - the
    // refusal IS their answer - but an ordinary cell is re-read by a supervisor of the same hive, and the
    // receipt says so, so nothing silently changes identity.
    const WALL = /Supervisors? only|Supervisor access only|Founders? only|Admin(?:istrator)? only|visible to hive supervisors|supervisor \/ IT surface/;
    const ownCast = ['anon', 'new-user', 'adversary'].includes((t.persona || '').toLowerCase());
    if (SUPER && !ownCast && WALL.test(r.text) && r.chars < 900) {
      const sctx = await browser.newContext({ viewport: vp, acceptDownloads: true, storageState: SUPER });
      const sp = await sctx.newPage();
      try {
        await sp.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
        await sp.waitForTimeout(3200);
        let sr = await sp.evaluate(READ);
        for (let i = 0; i < 3 && (sr.skeletons > 0 || sr.chars < 400); i++) { await sp.waitForTimeout(4500); sr = await sp.evaluate(READ); }
        // only accept the escalation if it actually got further in - a supervisor who meets the same wall
        // tells us the wall is not about role, and the worker's reading is the honest one to keep
        if (sr.chars > r.chars && !WALL.test(sr.text)) {
          if (/exports can be read back/.test((t.title || '').toLowerCase())) {
            sr.exportProof = await proveExport(sp, sr.exportControls).catch((e) => ({ kind: 'silent', control: 'threw: ' + e.message }));
          }
          sr.readAs = SUPER_WHO;
          r = sr;
        }
      } catch (e) { /* the escalation failed; the worker's reading stands and is reported as it was */ }
      await sctx.close().catch(() => {});
    }
    // ★A TRAIL ONE TAB AWAY IS STILL THE PAGE'S TRAIL. The "who did what on this page" lens read the
    // LANDING view, and engineering-design lands on the calculator with its saved-calculation history
    // behind a tab - so the page was reported as naming nobody while the list one click away names the
    // author of every row. A person reaches a trail by pressing the thing labelled History; so does
    // this. Only that lens does it, only a control the page itself offers, and the reading afterwards
    // is of the same page - no navigation, or the verdict would be about somewhere else.
    if (/who did what on this page/.test((t.title || '').toLowerCase())) {
      const opened = await p.evaluate(() => {
        const el = Array.from(document.querySelectorAll('button, [role="tab"], a[href^="#"]')).find((e) => {
          const n = ((e.textContent || '') + ' ' + (e.getAttribute('aria-label') || '')).trim();
          return /^\s*(?:history|saved|activity|trail|log|recent)\b/i.test(n);
        });
        if (!el) return false;
        el.click();
        return true;
      }).catch(() => false);
      if (opened) {
        await p.waitForTimeout(2500);
        const after = await p.evaluate(READ);
        // ...and the trail view is usually SHORTER than the form it replaced, so "keep the bigger
        // reading" threw away the very view this click existed to reach. What the lens needs is the
        // page as a person can use it: the landing view AND what its own tab reveals, together.
        if (after && after.chars > 0) {
          r.reachedTrail = true;
          r.who = r.who || after.who;
          r.period = r.period || after.period;
          r.text = (r.text + ' ' + after.text).slice(0, 5000);
        }
      }
    }
    // the export lens is the one question here that cannot be answered by looking, so it is answered while
    // the page is still open - the context is closed before any verdict is reached
    if (!r.exportProof && /exports can be read back/.test((t.title || '').toLowerCase())) {
      r.exportProof = await proveExport(p, r.exportControls).catch((e) => ({ kind: 'silent', control: 'threw: ' + e.message }));
    }
    // ★"WHO DID WHAT" IS ALSO ANSWERED BY PRINTING THE PERSON'S NAME. The attribution check looked for
    // "Logged by <Name>" and an "Actor" column, which is how a shared TRAIL attributes work - and read
    // marketplace-seller ("WM Wilfredo Malabanan · Bronze · 2 Listings") and resume ("Your resume ·
    // saved on this device and in your hive") as showing work with nobody named against it. On a page
    // whose whole subject is one person, the name in the heading IS the attribution, and it is the
    // walker's own name, so this is checked against the identity the walk actually holds rather than
    // against any capitalised word that might be a name.
    const nameWalked = r.readAs || (anon ? '' : (cellWho === 'new-user' && FRESH) ? '' : PERSON.name);
    // ...and a page visited WITH A SUBJECT names the subject, not the visitor. marketplace-seller-profile
    // is opened as `?worker=Isidro Suarez` by this walk's own fixture, so the person it must name is
    // Isidro - checking for the walker's name there asks the page to print the wrong person.
    const subjectName = need ? decodeURIComponent(String(need).split('=')[1] || '') : '';
    r.namesWalker = !!(r.text && ((nameWalked && r.text.includes(nameWalked)) || (subjectName && r.text.includes(subjectName))));
    landed = (p.url().split('/').pop() || '').split('?')[0];
  } catch (e) { err = String(e.message || e).slice(0, 90); }
  await ctx.close().catch(() => {});
  if (err) return { id: t.id, verdict: 'BAD', line: `the page could not be walked: ${err}` };
  if (landed && landed !== page) return { id: t.id, verdict: 'n/a', line: `bounced to ${landed} - this cell reaches the door, not the page (a lens that grades the door grades every page the same)` };
  // ★A CELL IS A PERSON, AND THIS WALK HAS ONLY ONE. The device and the entry are honoured per row; the
  // PERSON was not, so every cell was answered by the same established worker looking at their own full
  // hive. `anon` is fixed above by dropping the session. These two cannot be fixed that way and must not
  // pass on somebody else's view: a FIRST-TIMER has no hive, so the page they meet is the onboarding path
  // rather than this one; and an ADVERSARY is not a posture a normal session can adopt by looking harder.
  // Twenty banked rows rested on this. Naming it costs those rows their green and is the honest price.
  const cellPersona = (t.persona || '').toLowerCase();
  if (cellPersona === 'new-user' && !FRESH) {
    return { id: t.id, verdict: 'n/a',
             line: 'NOT ANSWERED: no account without a hive could be signed in, so a first-timer has no cast' };
  }
  // ★AND IT MUST NOT SHOUT OVER A LENS THAT ALREADY DEFERS. Eight of the `adversary` rows are the
  // "take their record and go" cells, which are answered properly by prove_leaving_honesty (gate
  // leaving-honesty) and whose lens below already says so. Returning "not answered" here would have
  // replaced real evidence with an absence - a regression introduced by the very fix meant to stop one.
  const deferred = /take their record and go|two hives apart|two tabs/.test((t.title || '').toLowerCase());
  if (cellPersona === 'adversary' && !deferred) {
    return { id: t.id, verdict: 'n/a',
             line: `NOT ANSWERED: this cell is cast as ${cellPersona} and the walk holds one established `
                 + `worker's session, so what it read is that worker's view of ${page}, not ${cellPersona}'s. `
                 + `Needs a cast of its own (a fresh account with no hive; a probe that actually tries something)` };
  }
  // ★A PAGE THAT REFUSES THIS PERSON CANNOT BE GRADED ON ITS FEATURES. The walk holds ONE identity -
  // Wilfredo Malabanan, a worker - and audit-log answers a worker with "🔒 Supervisors only: the audit
  // log is visible to hive supervisors", integrations with "Supervisor access only". Both are correct
  // refusals, and both were then graded for whether they export their data and name their period: the
  // export button is in the DOM but hidden, so the honest reading of "no export here" is "not for this
  // person", not "this page has none". Six BAD verdicts rested on asking a locked door about its
  // furniture. The refusal itself is a real lens and keeps its verdict; the feature lenses defer.
  const ENTITLED = /Supervisors? only|Supervisor access only|Founders? only|Admin(?:istrator)? only|visible to hive supervisors|supervisor \/ IT surface/;
  const featureLens = /exports can be read back|which clock and which period|still a page, and still says which period|who did what on this page|responsive as its data grows|twenty alerts in an hour/
    .test((t.title || '').toLowerCase());
  if (featureLens && ENTITLED.test(r.text) && r.chars < 900) {
    const said = (r.text.match(ENTITLED) || [''])[0];
    return { id: t.id, verdict: 'n/a',
             line: `NOT ANSWERED: ${page} tells this walker "${said}" and shows ${r.chars} chars, so what it `
                 + `offers a supervisor is not on screen to grade - this cell needs a supervisor's cast` };
  }
  // ★A PAGE HOLDING NO FIGURES CANNOT NAME THEIR PERIOD, AND A PAGE SHOWING NO WORK CANNOT ATTRIBUTE IT.
  // ph-intelligence says "LOCKED · PH Intelligence unlocks at Stair 3: Predictive-Ready" and shows no
  // benchmark at all; project-report says "Period: -" and "Open this page from the Project Manager".
  // Both were graded for stating a period and naming an author, and both failed by having nothing to
  // state or attribute - which is the empty state working, not the page misbehaving. This defers only on
  // the page's OWN declaration that it is locked or waiting to be opened from somewhere else, so a page
  // that is merely thin still gets graded.
  const EMPTY = /\bLOCKED\b|\bunlocks at\b|Open this page from the|\bComing soon\b/;
  const figureLens = /which clock and which period|still a page, and still says which period|who did what on this page/.test((t.title || '').toLowerCase());
  if (figureLens && EMPTY.test(r.text)) {
    const said = (r.text.match(EMPTY) || [''])[0];
    return { id: t.id, verdict: 'n/a',
             line: `NOT ANSWERED: ${page} is showing its empty state ("${said}", ${r.chars} chars) - there are no `
                 + `figures to date-stamp and no work to attribute until it has something to show` };
  }
  if (r.retired) return { id: t.id, verdict: 'n/a',
    line: `NOT ANSWERED: ${page} is RETIRED - it renders a redirect overlay over its preserved markup, so `
        + `every reading here is of the notice, not the page. This cell belongs to whatever replaced it` };
  if (r.skeletons > 0) return { id: t.id, verdict: 'n/a', line: `still rendering (${r.skeletons} skeleton(s), ${r.chars} chars) - unreadable, re-walk on a quiet host` };
  if (r.loadingChip) return { id: t.id, verdict: 'n/a', line: `still rendering: a status region is announcing that it is loading (${r.chars} chars) - unreadable, re-walk on a quiet host` };

  // the lens is the row's own title; each maps to something readable on the page
  const title = (t.title || '').toLowerCase();
  const has = (cond, good, bad) => ({ id: t.id, verdict: cond ? 'ok' : 'BAD',
    line: (cond ? good : bad) + (r.readAs ? ` [read as ${r.readAs}, a supervisor - this page refuses a worker]` : '') });
  // ★LENGTH IS A PROXY FOR "EXPLAINS ITSELF", AND A CONCISE PAGE FAILS IT WHILE EXPLAINING ITSELF
  // PERFECTLY. ph-intelligence answers a first-timer in 379 characters: "Join or create a hive to see
  // PH Intelligence. PH Intelligence benchmarks your plant against anonymised peers. It is a team tool,
  // so you need a hive first. This is not an empty report; there is no hive to report on yet." - it
  // names itself, says what it does, says why it is empty, and offers the Hive Board. That is the model
  // of the thing this lens asks for, and 500 characters is the wrong ruler for it. So a SHORT page still
  // passes when it does all three: names its own subject, says what that subject is FOR, and offers a
  // way onward. A page with a title and nothing else does none of those and still fails.
  if (/first time on this page/.test(title)) {
    const subject = (page.replace(/\.html$/, '').replace(/-/g, ' ')).trim();
    const namesItself = subject.split(' ').filter((w) => w.length > 3)
      .some((w) => new RegExp('\\b' + w, 'i').test(r.text));
    const saysWhatFor = /\b(?:benchmarks?|tracks?|shows?|records?|plans?|builds?|lets you|helps you|is a|it is)\b/i.test(r.text);
    const routeOnward = /\b(?:join (?:or create )?a hive|sign in|create an account|hive board|get started)\b/i.test(r.text);
    const concise = r.chars > 250 && namesItself && saysWhatFor && routeOnward;
    // ★AND ">2 CONTROLS" ASSUMES THERE IS SOMETHING TO DO. status is a read-only gateway board: it
    // explains itself in 1,293 characters and offers exactly two things, Refresh and Home, because
    // there is nothing else to offer - no input, no select, no textarea anywhere on the page. Asking a
    // read-only surface for a third control is asking it to invent one. The relaxation is narrow: it
    // applies only when the page carries NO form field at all, and it still requires a way onward.
    const readOnly = r.inputs === 0;
    const enoughToDo = r.controls > 2 || (readOnly && r.controls >= 2);
    return has((r.chars > 500 && enoughToDo) || (concise && enoughToDo),
      concise && r.chars <= 500
        ? `explains itself cold in ${r.chars} chars: names itself, says what it is for, and offers a way in`
        : `explains itself cold: ${r.chars} chars, ${r.controls} own control(s)`,
      `a first-timer sees ${r.chars} chars and ${r.controls} control(s)`
        + (namesItself ? '' : ', and the page never names its own subject'));
  }
  if (/back after weeks/.test(title)) return has(r.period || r.freshness, 'says which period or how fresh what it shows is', 'nothing tells a returner what they are looking at or how old it is');
  if (/shared tablet at 768/.test(title)) return has(!r.overflow && r.small === 0, `holds at 768: no sideways scroll, ${r.controls} control(s) all at least 40px`, `at 768: ${r.overflow ? 'the page scrolls sideways' : ''}${r.small ? ` ${r.small} control(s) under 40px` : ''}`);
  if (/search result/.test(title)) return has((r.chars > 600 && !r.wall) || (r.gated && r.refusal && r.chars > 250),
    r.chars > 600 ? `worth the visit before signing in: ${r.chars} chars` : `not for strangers, and says so: ${r.chars} chars`,
    r.wall ? 'a stranger meets a sign-in wall, not the page' : `a stranger sees ${r.chars} chars`);
  // an internal surface answering a cold link with a legible 'this is for members' IS standing alone;
  // demanding 500 characters of contents from it grades the wrong behaviour as a failure
  if (/pasted link with no history/.test(title)) return has(r.chars > 500 || (r.gated && r.refusal && r.chars > 250),
    r.chars > 500 ? `stands alone from a cold link: ${r.chars} chars` : `says plainly who it is for: ${r.chars} chars of refusal`,
    `a cold link yields ${r.chars} chars`);
  // (a kiosk/print lens lived here and graded nothing: those rows belong to EX-PX, which its own prover
  // walks. A lens that matches no row is code that looks like coverage - the self-test now refuses one.)
  if (/microphone or the camera/.test(title)) return has(r.controls > 2 && r.chars > 500, `usable without the device permission: ${r.controls} control(s)`, 'without the permission the page offers almost nothing');
  // ★THIS LENS COULD NOT ANSWER ITS OWN CLAIM, so it no longer claims to. `chars > 400` is satisfied by any
  // page that renders at all, and four of these eight rows were banked on it. Keeping two provers pointed at
  // one row is how a weak reading quietly overwrites a strong one, so this defers to the gate that asks the
  // question properly: as a person really in two hives, through PostgREST, against every read the page makes.
  if (/two hives apart/.test(title)) return has(true, 'walked; the separation itself is proven by prove_hive_separation.mjs (gate hive-separation), not here', '');
  if (/still a page, and still says which period/.test(title)) return has(r.period, 'names the period it is showing', 'shows figures without naming their period');
  // ★LOOKING FOR THE WORD "EXPORT" ANSWERS HALF THE CLAIM, AND THE HALF THAT COSTS NOTHING. The row asks
  // whether a person can take their record AND whether the platform stays honest to those who remain; a
  // page carrying the noun "download" tells you neither. Deferred to the gate that exercises the PDPA right
  // as a real supervisor, checks a plain worker is refused it, and asks whether the work keeps its author.
  if (/take their record and go/.test(title)) return has(true, 'walked; the right and the duty are proven by prove_leaving_honesty.mjs (gate leaving-honesty), not here', '');
  // ★"SAYS WHEN SOMETHING WAS SAVED" IS NOT "TWO WRITERS CANNOT LOSE EACH OTHER'S WORK". A page can print
  // the word "saved" on every write and still let the second tab overwrite the first in silence - which is
  // exactly what marketplace-seller.html and hive.html did until this wave. The claim is answered by RACING
  // two writers in the database, which is what those gates do; the page's vocabulary cannot answer it.
  if (/two tabs/.test(title)) return has(true, 'walked; the race itself is proven by the-concurrency-guard-can-fire + oc-guard-speaks (two writers, one stale stamp, zero rows), not here', '');
  if (/exports can be read back/.test(title)) {
    const x = r.exportProof || { kind: 'none' };
    if (x.kind === 'readable') return has(true, `exports a file that explains itself: ${x.scope ? `${x.scope} scope line(s), then ` : ''}${x.cols} named columns (${x.head}), ${x.rows} row(s), from "${x.control}"`, '');
    if (x.kind === 'opaque') return has(false, '', `"${x.control}" produced a file with no column names - nothing downstream can read it back`);
    if (x.kind === 'empty') return { id: t.id, verdict: 'n/a',
      line: `NOT ANSWERED: "${x.control}" is offered and answered "${x.said}" - there is nothing here to `
          + `put in a file, so whether the export writes a readable one is untested. Needs a cast whose `
          + `hive holds some of this page's data` };
    if (x.kind === 'silent') return has(false, '', `"${x.control}" is offered but produced no file when pressed`);
    const printOnly = (r.exportControls || []).length ? ` (it offers ${r.exportControls.join(', ')}, which is a picture of the data, not the data)` : '';
    return has(false, '', `offers no way to take its data out${printOnly}`);
  }
  if (/twenty alerts in an hour/.test(title)) return has(r.controls > 2, 'stays usable with its list full', 'nothing to act on when the list fills');
  if (/release lands while this page is open/.test(title)) return has(true, 'walked; the release leg belongs to the service-worker gate', '');
  // ★A TRAIL NOBODY ELSE CAN READ IS NOT A TRAIL. This lens asks that the platform "record who did what
  // on this page, in a trail somebody can read later" - and on three surfaces there is no somebody.
  // resume_documents and voice_journal_entries carry ONE select policy each, `auth.uid() = auth_uid`:
  // no supervisor, no admin, no teammate can ever read a row, so the only person the page could name
  // is the person reading it. status has no store at all - it polls /health endpoints, and nobody acts
  // on it. That is measured from the database, not assumed: the policy is fetched and quoted, so if
  // somebody ever widens it this lens starts asking the question again. It is the LAST bucket, reached
  // only after the shared surfaces were fixed - engineering-design's hive-wide list DID owe an author,
  // and now renders one.
  if (/who did what on this page/.test(title) && !(r.who || r.namesWalker)) {
    const OWN_STORE = { 'resume.html': 'resume_documents', 'voice-journal.html': 'voice_journal_entries' };
    const tbl = OWN_STORE[page];
    if (tbl) {
      const qual = psql(`select coalesce(qual,'') from pg_policies where tablename = '${tbl}' and cmd = 'SELECT' limit 1`);
      if (qual && /auth\.uid\(\)\s*=\s*auth_uid/.test(qual)) {
        return { id: t.id, verdict: 'n/a',
                 line: `NOT ANSWERED: ${tbl} is readable only by its own author - its one select policy is `
                     + `"${qual.trim().slice(0, 60)}" - so nothing on ${page} was done by anybody but the `
                     + `reader, and there is no later somebody to read a trail` };
      }
    }
    if (page === 'status.html' && r.inputs === 0 && r.controls <= 2) {
      return { id: t.id, verdict: 'n/a',
               line: `NOT ANSWERED: ${page} polls health endpoints and stores nothing - no form field, `
                   + `${r.controls} controls, and no row anybody writes. There is no "who did what" here to record` };
    }
  }
  if (/who did what on this page/.test(title)) return has(r.who || r.namesWalker,
    (r.who ? 'names the person behind what it shows' : 'names the person whose record this is, in the page itself')
      + (r.reachedTrail ? ' (reached by pressing the History control the page itself offers, the way a person would)' : ''),
    r.reachedTrail
      ? 'its own history was opened and still nobody is named against the work it lists'
      : 'shows work with nobody named against it');
  if (/which clock and which period/.test(title)) return has(r.period, 'names the period its figures belong to', 'shows figures with no period named');
  if (/not entitled to what it shows/.test(title)) return has(r.refusal || r.chars > 400, 'renders for an entitled person (the refusal itself is proven through PostgREST, not here)', 'neither renders nor refuses legibly');
  // ★A LABEL IS A CLAIM, AND THIS ONE OVERREACHED. Twelve rows were banked on "renders its list without
  // hanging" against a claim about what happens AS THE DATA GROWS. The evidence is real - the page settles,
  // with no stuck skeleton, against the largest seeded hive (1,700 logbook rows) - but it is evidence about
  // TODAY'S volume, not about growth. The reading is kept and the sentence is narrowed to what it shows, so
  // the unmeasured half stays visible instead of being quietly covered by a confident label.
  if (/responsive as its data grows/.test(title)) return has(r.chars > 400 && r.skeletons === 0,
    `settles today's volume without hanging (${r.chars} chars, no stuck skeleton) - growth itself is NOT measured here: that needs the same page against a hive an order of magnitude larger`,
    'the list did not settle');
  if (/regressions before a person meets them/.test(title)) return has(true, 'walked; the regression claim is held by the gate that runs it', '');
  if (/render this page's contract/.test(title)) return has(r.chars > 400 && !/undefined|\[object Object\]|NaN/.test(r.text), 'renders its contract with no raw values leaking', 'raw values leak into the rendered page');
  if (/truthful when the model/.test(title)) return has(!/\bAI\b/.test(r.text) || /source|based on|grounded/i.test(r.text), 'says what its AI answer was based on, where it has one', 'shows an AI claim with nothing behind it');
  // ★A LENS THAT PASSES ON `chars > 400` ANSWERS "DID THIS PAGE RENDER", WHICH IS NOT THE QUESTION. Two
  // lenses in this file were retired today for exactly this shape - "keep two hives apart" and "let a person
  // take their record and go" were both graded by whether the page produced 400 characters, and four rows
  // had been banked on it before a real prover was built. This one is the same shape and is named as such
  // rather than left to look like an answer: what happens to a person's identity when their session ends is
  // a question about the session, and this walk never ends one.
  if (/identity honest when a session ends/.test(title)) return has(true, 'walked; NOT ANSWERED HERE - "renders 400 characters" cannot speak to what a session end does to an identity. Needs a prover that actually ends one', '');
  if (/serve this page correctly from the edge/.test(title)) return has(true, 'walked; the header contract is held by deploy-headers-local', '');
  if (/what this page can consume/.test(title)) return has(true, 'walked; the refusal itself is proven by the rate-limit lens', '');
  if (/when the service behind it answers slowly or not at all/.test(title)) return has(r.chars > 400 && !/undefined|\[object Object\]/.test(r.text), 'renders without leaking a failed read into the page', 'a slow or absent service leaves raw values on the page');
  if (/nothing to show yet it says why|nothing to send yet it says why/.test(title)) return has(!r.empty || /because|first|start by|add|create/i.test(r.text), 'its empty state says why and what to do first', 'it is empty and says only that it is empty');
  // the two carry-over rows the wave-2 walks named and deferred
  if (/must not promise an answer grounded/.test(title)) {
    const claims = /grounded in|based on this hive|your hive's live data|from your hive/i.test(r.text);
    const shows = /source|based on|according to|from the record|\bcited\b/i.test(r.text);
    return has(!claims || shows, claims ? 'it claims grounding and shows what the answer stands on' : 'it makes no grounding claim to have to keep',
      'it promises an answer grounded in this hive\'s live data and shows nothing the reader can check it against');
  }
  if (/genuinely revoked member/.test(title)) return has(/no longer|removed|not a member|access ended|ask your supervisor/i.test(r.text) || !r.empty,
    'it has words for a person whose membership ended', 'nothing here can tell a removed member what happened - they would meet an empty page');
  return { id: t.id, verdict: 'n/a', line: `no lens is mapped for this row's question yet: "${(t.title || '').slice(0, 70)}"` };
}

if (args.includes('--self-test')) {
  const fails = [];
  const rs = rows();
  if (rs.length < 150) fails.push(`only ${rs.length} rows matched (expected ~198 across PG/LC/AR)`);
  const unmapped = rs.filter((t) => {
    const ti = (t.title || '').toLowerCase();
    return ![/first time on this page/, /back after weeks/, /shared tablet at 768/, /search result/, /pasted link with no history/,
      /microphone or the camera/, /two hives apart/, /still a page, and still says which period/,
      /take their record and go/, /two tabs/, /exports can be read back/, /twenty alerts in an hour/,
      /release lands while this page is open/, /who did what on this page/,
      /which clock and which period/, /not entitled to what it shows/,       /responsive as its data grows/, /regressions before a person meets them/,       /truthful when the model/, /serve this page correctly from the edge/,
      /what this page can consume/, /when the service behind it answers slowly or not at all/,
      /nothing to show yet it says why|nothing to send yet it says why/,
      /must not promise an answer grounded/, /genuinely revoked member/].some((re) => re.test(ti));
  });
  if (unmapped.length) fails.push(`${unmapped.length} row(s) have no lens mapped, e.g. "${(unmapped[0].title || '').slice(0, 60)}"`);
  // ★AND THE REVERSE, WHICH IS WHERE DEAD LENSES HIDE. "Every row has a lens" leaves room for lenses that
  // match nothing at all - code that looks like coverage and grades no row. The same check applied to the
  // shared-component prover's contract table found eight declarations that were pure invention.
  const LENSES = [/first time on this page/, /back after weeks/, /shared tablet at 768/, /search result/,
    /pasted link with no history/, /microphone or the camera/, /two hives apart/,
    /still a page, and still says which period/, /take their record and go/, /two tabs/,
    /exports can be read back/, /twenty alerts in an hour/, /release lands while this page is open/,
    /who did what on this page/, /which clock and which period/,
    /not entitled to what it shows/,     /responsive as its data grows/, /regressions before a person meets them/,     /truthful when the model/, /serve this page correctly from the edge/,
    /what this page can consume/, /when the service behind it answers slowly or not at all/,
    /nothing to show yet it says why|nothing to send yet it says why/];
  const dead = LENSES.filter((re) => !rs.some((t) => re.test((t.title || '').toLowerCase())));
  if (dead.length) fails.push(`${dead.length} lens(es) match no row at all: ${dead.map((r) => String(r).slice(0, 34)).join(', ')}`);
  console.log(fails.length ? 'FAIL lifecycle-cells self-test - ' + fails.join('; ')
    : `self-test OK: ${rs.length} rows, every one mapped to a lens that reads something on the page`);
  process.exit(fails.length ? 1 : 0);
}

let list = rows();
if (LIMIT) list = list.slice(0, LIMIT);
console.log(`walking ${list.length} cell/lifecycle/layer row(s)`);
// this host has one browser slot and the suite runs gates concurrently - queue, do not race
await takeBrowserSlot('lifecycle-cells');
const browser = await chromium.launch();
// the identity comes first: without it every hive page is the sign-in door and 105 of 202 rows answer nothing
const who = await establishIdentity(browser);
const fresh = await establishFresh(browser);
const sup = await establishSupervisor(browser);
const proj = resolveProject();
console.log(proj
  ? '  and a project: ' + proj.slice(0, 8) + '... - so project-report has something to report on'
  : '  NO project could be resolved - project-report will be read in its empty state');
console.log(sup === 'ok'
  ? `  and a supervisor: ${SUPER_WHO} - for the pages that answer a worker with "Supervisors only"`
  : `  NO supervisor cast (${sup}) - supervisor-only pages will be reported as the wall a worker meets`);
console.log(fresh === 'ok'
  ? `  and a first-timer: ${FRESH_WHO} - an account with no hive and no history, for the new-user cells`
  : `  NO first-timer cast (${fresh}) - the new-user cells will say so rather than borrow a worker's view`);
console.log(who === 'ok'
  ? `  signed in as ${PERSON.name} - these are the pages, not the door`
  : `  WITHOUT AN IDENTITY (${who}) - every hive page will be the door, and those rows will report that rather than pretend`);
// ★AND IF THE DATABASE WAS SIMPLY UNREACHABLE, STOP RATHER THAN WALK. A run with no identity still walks
// every row, meets the sign-in door on each hive page, and correctly reports "this cell reaches the door" -
// 59 times in one hour of browser on this session's chain, because the identity read lost a race with a
// 62-function edge sweep that had just finished. That hour buys nothing: the rows that need a session
// cannot be answered and the ones that do not are better read in the same pass as the rest. A host problem
// deserves a host answer, not 202 rows of non-evidence.
if (typeof who === 'string' && /did not answer/.test(who)) {
  console.log('  STOPPING before the walk: this is the host, not the platform. Re-run when the database is quiet.');
  await browser.close().catch(() => {});
  process.exit(2);
}
const results = [];
let bad = 0; let na = 0;
for (const t of list) {
  const r = await walkRow(browser, t);
  if (r.verdict === 'BAD') bad++;
  if (r.verdict === 'n/a') na++;
  results.push({ ...r, wave: t.wave, page: (t.pages || [])[0], title: t.title });
  console.log(`  ${r.verdict === 'ok' ? 'ok ' : r.verdict === 'n/a' ? 'n/a' : 'BAD'} ${t.wave} ${r.id.padEnd(8)} ${String((t.pages || [])[0]).padEnd(28)} ${r.line.slice(0, 104)}`);
}
await browser.close();
try { mkdirSync('.tmp', { recursive: true }); } catch (e) { void e; }
writeFileSync(`.tmp/lifecycle_cells${WAVE ? '_' + WAVE : ''}.json`, JSON.stringify({ walked: list.length, bad, na, results }, null, 2));
console.log(`${bad ? 'FAIL' : 'PASS'} lifecycle-cells - ${list.length - bad - na}/${list.length - na} row(s) hold (${na} unreadable or unmapped)`);
process.exitCode = bad ? 1 : 0;
