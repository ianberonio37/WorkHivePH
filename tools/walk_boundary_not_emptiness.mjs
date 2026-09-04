// walk_boundary_not_emptiness.mjs - the RUNTIME half of the boundary_not_emptiness arc.
//
// tools/census_boundary_not_emptiness.py proves the NECESSARY condition statically: 25 of 26 surfaces
// owning an absence state carry no refusal copy at all, so they provably cannot distinguish "you cannot
// see this" from "there is nothing here". What static analysis cannot show is what a real person MEETS.
// This does.
//
// THE SCENARIO, chosen because it is ordinary rather than exotic. A worker removed from a hive keeps
// `wh_active_hive_id` in localStorage. Their next read is refused by RLS - which FILTERS rather than
// raising - so the page receives HTTP 200 with zero rows and renders its empty state. The platform has
// recorded this silence once already from the other direction (a dead session's 0-rows-no-error was read
// as removal). We reproduce it WITHOUT touching anyone's membership: sign in as a real user, then point
// wh_active_hive_id at a hive they are not a member of. Every hive-scoped read then lawfully returns
// zero rows - exactly the removed-member state - and no data is mutated to get there.
//
// WHAT IS RECORDED PER SURFACE: the visible text, whether it reads as an ABSENCE ("no entries yet",
// "nothing due"), whether it reads as a REFUSAL (names the boundary), and whether anything at all
// distinguishes the two. A surface that says "No completions recorded yet." here is telling a removed
// worker their team never did any maintenance.
//
// Read-only by construction: it signs in, writes one localStorage key, and reads the DOM.
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';

const SEEDER = 'http://127.0.0.1:5000';
const EMAIL = process.env.WH_EMAIL || 'pabloaguilar@auth.workhiveph.com';
const PASSWORD = process.env.WH_PASSWORD || 'test1234';
// a syntactically valid hive id the signed-in user is NOT a member of; every RLS read filters to zero
const FOREIGN_HIVE = '00000000-0000-4000-8000-0000000000ff';

// Pages may be passed on the command line so the remaining boundary_not_emptiness surfaces can be
// covered without editing this file: `node tools/walk_boundary_not_emptiness.mjs hive.html index.html`.
// The default list is the twelve core surfaces walked on 2026-08-31.
// Entries may carry a query string - `project-report.html?project_id=<uuid>` - because some surfaces are
// a DIFFERENT PAGE without their param. Walked paramless, project-report renders "Open this page from
// the Project Manager", its correct no-project state, which says nothing about the boundary. This repo
// learned that on this very page (a_paramless_walk_is_a_different_page) and the first version of this
// harness walked it paramless anyway. The goto below already interpolates the whole string.
const _anon = process.argv.slice(2).includes('--anon');
const _argv = process.argv.slice(2).filter(a => a.includes('.html'));
const SURFACES = _argv.length ? _argv : [
  'pm-scheduler.html', 'inventory.html', 'logbook.html', 'dayplanner.html',
  'achievements.html', 'skillmatrix.html', 'asset-hub.html', 'alert-hub.html',
  'community.html', 'analytics.html', 'project-manager.html', 'shift-brain.html',
];

const ABSENCE_RE = /(no .{0,28}(yet|found|recorded|due|match)|nothing (due|here|to)|be the first|log your first|all clear|no results|no entries|no tasks|empty)/i;
// ★WIDENED AFTER THE FIRST RUN, because the first vocabulary produced a false NEGATIVE on the surface
// that handles this BEST. shift-brain answers a hiveless session with 245 characters - "Shift Brain
// needs a hive. The autonomous shift planner runs hive-by-hive. Join or create a hive to see briefings
// for your team. Go to Hive" - which names the boundary AND offers the remedy, and the first regex
// scored it "neither" because it only knew the words "switch/choose/select a hive". A refusal census
// whose vocabulary is narrower than the product's is measuring its own wording, not the product's.
const REFUSAL_RE = /(not visible with this session|no longer a member|not a member of|belongs to a hive|was deleted, or|removed from|(does|do|did) ?n.t have access|don't have access|do not have access|does not have access|no access to|cannot see|not authorised|not authorized|access denied|not permitted|ask (a|your) supervisor|only supervisors|supervisors only|switch hive|choose a hive|select a hive|needs a hive|no hive selected|not in (a|this) hive|hive-by-hive|(join|create)[^.]{0,30}hive|hive[^.]{0,30}(to (start|see|join))|a workhive first|team tool)/i;

/* ★ONE SCOPED EXEMPTION, pinned rather than broad (2026-08-31). engineering-design's "No Report Yet" is
   not an empty-DATA state: engineering-design.html:713-717 is the report pane's PRE-CALCULATION
   placeholder - "Fill in the inputs on the left and click Run Calculation to generate your report" -
   shown to every user before they run anything, on a pane that is empty by definition until a
   calculation happens. Matching it says nothing about a hive boundary.
   A relaxation with no teeth is how a detector quietly stops detecting, so this is keyed to the PAGE AND
   the exact phrase: any other absence wording on engineering-design is still measured, and this phrase
   on any other page is still measured. If the placeholder text changes the exemption stops applying and
   the page is measured again - the right failure mode. The match is RECORDED (absenceExempt), never
   silently dropped. */
const ABSENCE_EXEMPT = {
  'engineering-design.html': /no report yet/i,
};

const out = {};
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
const page = await ctx.newPage();

await page.goto(`${SEEDER}/workhive/index.html`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(2500);
/* ★--anon COVERS A DIFFERENT SUBJECT, not the same walk with a flag. The bank rows share one oracle but
   NOT one subject: the -097-IA rows read "anon (what a stranger sees)" on achievements, community,
   engineering-design and index, while the removed-member walk proves only "worker (tenant boundary)".
   A stranger with no session is refused by a different mechanism (no JWT at all, rather than a JWT whose
   membership was revoked), so it has to be walked as a stranger. Skipping sign-in entirely is that walk. */
if (_anon) {
  console.log('walking ANONYMOUS (no sign-in) - subject: what a stranger sees');
} else {
const signedIn = await page.evaluate(async ([email, password]) => {
  const db = window.db || (window.getDb && window.getDb());
  if (!db) return 'no db handle';
  await db.auth.signOut().catch(() => {});
  const { error } = await db.auth.signInWithPassword({ email, password });
  return error ? ('sign-in failed: ' + error.message) : 'ok';
}, [EMAIL, PASSWORD]);
if (signedIn !== 'ok') { console.error(signedIn); await browser.close(); process.exit(2); }
}

for (const file of SURFACES) {
  try {
    // point the session at a hive this user does not belong to - the removed-member state, no writes
    await page.goto(`${SEEDER}/workhive/${file}`, { waitUntil: 'domcontentloaded' });
    if (!_anon) await page.evaluate((h) => localStorage.setItem('wh_active_hive_id', h), FOREIGN_HIVE);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(6500);
    const r = await page.evaluate(([aRe, rRe]) => {
      const t = (document.body.innerText || '').replace(/\s+/g, ' ').trim();
      // ★RECORD WHAT MATCHED, AND ITS CONTEXT - not just a boolean and a prefix of the page. The first
      // run reported analytics.html as "REFUSAL NAMED" and stored only the first 260 characters, which
      // contained nothing of the sort, so the verdict could be neither confirmed nor refuted without
      // re-running the whole walk. A verdict owes the reader the evidence that produced it.
      const am = t.match(new RegExp(aRe, 'i'));
      const rm = t.match(new RegExp(rRe, 'i'));
      const around = (m) => m ? t.slice(Math.max(0, m.index - 70), m.index + m[0].length + 70) : null;
      return {
        absence: !!am, refusal: !!rm,
        absenceMatch: am ? am[0] : null, refusalMatch: rm ? rm[0] : null,
        absenceContext: around(am), refusalContext: around(rm),
        len: t.length,
        sample: t.slice(0, 260),
      };
    }, [ABSENCE_RE.source, REFUSAL_RE.source]);
    const _ex = ABSENCE_EXEMPT[file.split('?')[0]];
    if (r.absence && _ex && _ex.test(r.absenceMatch || '')) {
      r.absence = false;
      r.absenceExempt = r.absenceMatch;      // recorded, not silently dropped
      r.absenceMatch = null;
    }
    r.verdict = r.refusal ? 'REFUSAL NAMED' : (r.absence ? 'reads as EMPTINESS' : 'neither');
    out[file] = r;
    console.log(`${r.refusal ? 'ok  ' : 'SILENT'} ${file.padEnd(24)} ${r.verdict}`
                + (r.refusalMatch ? `   <- "${r.refusalMatch}"` : (r.absenceMatch ? `   <- "${r.absenceMatch}"` : '')));
  } catch (e) {
    out[file] = { error: String(e).slice(0, 180) };
    console.log(`ERR  ${file}: ${out[file].error}`);
  }
}

await browser.close();
writeFileSync(_anon ? 'boundary_not_emptiness_walk.anon.json'
            : _argv.length ? 'boundary_not_emptiness_walk.extra.json' : 'boundary_not_emptiness_walk.json', JSON.stringify(out, null, 1), 'utf8');
const silent = Object.entries(out).filter(([, r]) => r && !r.refusal && r.absence).map(([f]) => f);
console.log(`
${SURFACES.length} surfaces walked as ${_anon ? 'an ANONYMOUS stranger' : 'a removed member'} · ${silent.length} answer with EMPTINESS`);
if (silent.length) console.log('  silent: ' + silent.join(', '));
console.log('written: ' + (_anon ? 'boundary_not_emptiness_walk.anon.json'
                          : _argv.length ? 'boundary_not_emptiness_walk.extra.json'
                                        : 'boundary_not_emptiness_walk.json'));
