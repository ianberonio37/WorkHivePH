// prove_cross_surface.mjs — does the SAME fact read the same on two different surfaces?
//
// THE ORACLE (`cross_surface_agreement`). A hive board summarises what the specialist pages own: its
// PM tile is pm-scheduler's overdue count, its stock tile is inventory's low-stock count, its jobs
// tile is logbook's open count. Three copies of one fact is exactly the shape that drifts — one
// surface changes its predicate, the other does not, and both keep rendering a confident number.
//
// ★WHY THIS IS NOT "READ TWO PAGES AND COMPARE", and the distinction is the whole value: two surfaces
// agreeing on a WRONG number agree perfectly. So each pair is checked against psql as well — the
// summary tile, the specialist page, AND the database all have to say the same thing. A pair that
// matches each other but not the DB is reported as agreement-on-a-falsehood, which is worse than a
// visible disagreement because nothing on either screen looks wrong.
//
// ★AND A PAIR THAT MERELY LOOKS EQUAL IS NOT ENOUGH. Two tiles can both read 0, or both read the same
// number by coincidence on a small dataset, and prove nothing. Each pair therefore records whether the
// value is DISCRIMINATING — whether some other plausible predicate would have produced a different
// number — so a green here cannot rest on a coincidence. A comparison that cannot fail is not
// evidence.
//
// Both surfaces are read in the SAME browser context and the same session, so a difference cannot be
// explained away by one of them having been signed in as somebody else.
//
// USAGE:  node tools/prove_cross_surface.mjs
// OUTPUT: cross_surface_report.json

// ★alert-hub wrong_then_fix - UNRESOLVED BY STUBBED WRITES, and NOT filed as a gap (2026-08-19).
// What was measured: the alert list offers 29 dismiss/snooze controls ("⏳ Snooze 7d"). Clicking one
// fires a real POST alert_dismissals (plus hive_audit_log), and the source at :1431-1432 says a snoozed
// alert "hides until snooze_until passes" - so a wrongly snoozed alert would be invisible for 7 days.
// No undo affordance was found: zero buttons matching undo/restore/un-snooze, no "Snoozed" tab among
// All/AMC/Risk/PM/Stock/Staging/Pattern/System, and - checked with a MutationObserver armed BEFORE the
// click, because a toast is gone before a post-hoc read - ZERO announcements of any kind.
// WHY THAT IS NOT YET A FINDING: the action never visibly took effect under stubbed writes. Tab counts
// held at "All 61" and the 29 controls remained, changing the page by only 8 characters. The write is
// intercepted and answered with a fake row, but the page re-reads alert_dismissals from the REAL database
// on refresh, where no dismissal exists - so the UI never entered the snoozed state, and "no undo was
// offered" may simply mean "nothing was dismissed to undo". Claiming a recovery gap from a state the page
// never entered would be an accusation built on my own harness.
// TO SETTLE IT HONESTLY, one of: (a) write a real dismissal inside a psql transaction and ROLL BACK after
// reading the UI, (b) seed a disposable hive whose alerts can be dismissed for real, or (c) read the
// dismissal render path directly to see whether a restore control exists for an actually-dismissed alert.
// Do NOT simply write to the shared test database and leave the row there.

// ★engineering-design idempotency - NUMBERS REPRODUCE, PROSE DOES NOT, AND EACH REPEAT COSTS A MODEL
// CALL. Measured 2026-08-19; row left OWED rather than banked either way, because it is a real question for
// Ian rather than a clean pass or a clean defect.
// HOW IT WAS DRIVEN (the earlier blocker is solved): runCalculation() is a GLOBAL - wired via onclick at
// engineering-design.html:696 - so it can be invoked directly. #calc-btn ships disabled and is enabled by
// selecting a calculator card; my first attempt set input values and clicked without selecting, so the
// engine never ran and _lastResults stayed null.
// WHAT REPEATING AN IDENTICAL CALCULATION DOES:
//   · THE NUMBERS ARE DETERMINISTIC. _lastResults is byte-identical across runs - 22 keys, kW 44.69,
//     TR 12.71, recommended_kW 50, SHR 0.926 - so the engineering computation itself reproduces exactly.
//   · NOTHING ACCUMULATES. #report-output holds 3 blocks after 1 run and still 3 after 3 runs, so the
//     render replaces rather than appends - the usual client-layer idempotency failure does not occur.
//   · BUT THE NARRATIVE DIFFERS EVERY TIME. Report text went 4246 chars then 4038 for the SAME inputs, and
//     a word-level diff shows only prose changing: run 1 "It quantifies gains from various sources such as
//     walls", run 2 "gain 'Untitled Room' project, appropriately sized conditioning equipment". Same
//     numbers, different sentences.
//   · AND EACH RUN SPENDS A PAID CALL. Routing /functions/v1/ showed exactly 3 invocations of
//     engineering-calc-agent across 3 runs - one per calculation, no caching. With that agent stubbed,
//     _lastResults comes back NULL, so the agent's response is load-bearing for the result object, not
//     merely decorative.
// WHY THIS IS A QUESTION AND NOT A VERDICT: the roadmap's own CD invariant for this page says "a saved calc
// reproduces its result exactly from its stored inputs" - the RESULT does. Whether a client-facing
// engineering report may re-word itself between identical runs, and whether an identical calculation should
// re-bill a model call, are product decisions. Two engineers running the same calc today get the same
// figures inside differently-worded documents.
// TO SETTLE: ask whether narrative reproducibility is required for a deliverable, and whether the agent
// result should be cached by (calc_type, inputs-hash). Then this row is a pass or a defect, not a judgement.

// ★UNRESOLVED, AND I STOPPED PROBING ON PURPOSE - analytics-report generation went asymmetric across two
// identities, and the likeliest cause is MY OWN repeated presses (2026-08-19). Measured for the
// two_sided_same_object rows: with actors proven distinct by decoded JWT (supervisor sub=bcb5a6e3...
// leandromarquez@, worker sub=91e0d1eb... bryangarcia@), the WORKER pressed Generate and got a full report
// (#ar-doc mounted, 'PM COMPLIANCE 79% FLEET MTBF 9days TOTAL FAILURES 165 HIGH RISK (PREDICTED) 30'),
// while the SUPERVISOR on the same press got 'Could not generate' - and on a THIRD run got neither: ZERO
// /functions/v1/ requests and #ar-report-mount left sitting on 'Compiling analytics across all 4 phases.'
// WHY THIS IS NOT FILED AS A DEFECT: the supervisor generated this same report SUCCESSFULLY several times
// earlier in the same session, so the capability plainly exists; the behaviour varies run to run; and by
// this point I had pressed Generate roughly five times, which is exactly the shape of a gate exhausting its
// own rate budget. Attributing it to a permission or identity bug would be an accusation built on a
// condition I created. Two things ARE worth chasing later, separately: (1) the third run is a STUCK
// SKELETON - a loading sentence with no request in flight and no timeout - which is invisible to every gate
// and is its own defect class regardless of what triggered it; (2) the two earlier outcomes differ from
// each other ('Could not generate' vs silent hang), so the refusal path is not deterministic.
// I DID NOT KEEP PROBING: each press is a paid model call through the orchestrator, and re-running to chase
// a hypothesis is not mine to spend without asking. The three analytics-report two_sided rows and the three
// assistant ones stay OWED rather than being banked on an asymmetry I probably caused, or dismissed as
// transient without proof. To settle them: ask before re-running, then generate ONCE per identity with a
// cooldown between, and read #ar-report-mount plus the network log for each.

// ★analytics PM COMPLIANCE - DO NOT COMPARE THE TILE AGAINST get_pm_ontime_delivery. THEY ARE DIFFERENT
// METRICS AND THE MISMATCH IS NOT A DEFECT (established 2026-08-19; this note exists because comparing
// them is the obvious next move and it manufactures a false finding).
//   The tile renders "PM COMPLIANCE (90 DAYS) 79% - 468 of 595 PMs completed". Its source is NOT a DB
//   view: analytics.html:1321-1332 records that the numbers arrive from the Python API as
//   data.pm_compliance.overall_pct with a per-asset fallback array whose rows carry {completed,
//   scheduled}, and the page's reduce over that array is a faithful sum. So the figure is EDGE-COMPUTED
//   and only a payload capture can verify it.
//   Measured for contrast, all read-only: get_pm_ontime_delivery(hive, 90) returns {"ontime": 294,
//   "late": 114, "intervals": 408, "ontime_pct": 72.1} - i.e. 72.1%, a DIFFERENT metric: ON-TIME
//   delivery against each item's own frequency, which is a stricter question than completion rate.
//   Raw rows differ again: pm_completions in the last 90 days = 492 (537 lifetime), pm_scope_items = 144
//   across 30 assets. So FOUR numbers describe PM performance here - 79% (468/595 completion, edge),
//   72.1% (294/408 on-time, RPC), 492 raw completions, 144 scope items - and every pair of them differs
//   for a legitimate reason. 468 <= 492 and on-time <= completed both hold, which is the consistency
//   that IS checkable without re-implementing anyone's fold.
//   NOTE v_pm_compliance_truth does NOT have completed/scheduled columns - it carries completions_30d,
//   completions_90d, completions_365d, is_due - so it is not the tile's source either.
// TO SETTLE THE ROW: capture the analytics-orchestrator response, read data.pm_compliance, and compare
// its overall_pct and its summed {completed, scheduled} to what the tile renders. That is a render-vs-
// payload check, the same shape as the chart-vs-datum invariant in the roadmap, and it needs no new SQL.

// ★OPEN QUESTION - THREE NUMBERS FOR ONE PROJECT'S PROGRESS. Measured 2026-08-19, NOT banked and NOT
// filed as a defect, because I cannot yet tell which of them the surface is entitled to show.
// project-manager V2 (#detail-view, confirmed open) renders "PROGRESS 25% - 2/6 items done" for the
// project "Recurring Compressor Breakdown Bundle". Against source:
//   · project_items for that project: 6 items, 2 with status='done'  ->  2/6 = 33%, not 25%
//   · v_project_progress_truth's row for that project: percent = 100, logged 2026-07-20
// So the page's 25%, its own stated fraction's 33%, and the progress log's 100% are three different
// answers. That is the FOUR-COUNTS-FOR-ONE-PRODUCT shape, and the roadmap anticipates part of it: its
// CI truth for this page requires progress to STATE ITS BASIS (weighted by cost, by item count, or by
// planned hours). If 25% is cost- or hours-weighted then it is legitimate and the defect is only that
// the basis is unstated beside a fraction that implies item-count; if it is meant to BE the item count
// then it is wrong. v_project_progress_truth is a LOG - one row per worker per date carrying a percent
// and hours - not a rollup, so "the latest row" may not be what the page should read either.
// WHAT WOULD SETTLE IT: read the code path that writes the 25% (grep the #detail-view progress render in
// project-manager.html) and find which source it takes, THEN compare against that source only. Three
// plausible readings of one figure is exactly when a comparison manufactures a defect - eight such
// near-misses were caught this session, four of them in the last hour.

// ★TWO count_matches_source FIGURES VERIFIED AGAINST psql BUT NOT BANKABLE YET - THE OWED ROWS ARE V2
// AND THESE READINGS ARE V1 (2026-08-19). Recorded so the next pass banks them after one V2 walk each,
// instead of re-deriving the predicates, both of which took two attempts:
//   · skillmatrix #sm-badges-hero "TOTAL BADGES 19" == select count(*) from v_skill_badges_truth where
//     worker_name = 'Leandro Marquez' -> 19. EXACT. First attempt used 'leandromarquez', the LOGIN slug,
//     which returns 0 - a 19-vs-0 defect against a correct page had I stopped there. The view keys on the
//     display name. Hive-wide total is 148 and every sibling worker holds 12, so 19 is genuinely
//     per-worker and the query discriminates.
//   · dayplanner #dp-overdue-hero "OVERDUE 3" == schedule_items for this worker with date::date <
//     current_date AND item_status <> 'done' -> pending 2 + in_progress 1 = 3. EXACT. The raw past-date
//     count is 6, because 3 more are DONE - and a completed item is not overdue, so the page is right and
//     a naive count(*) reports a 6-vs-3 defect. NOTE schedule_items has NO hive_id column and its `date`
//     is TEXT, so it needs worker_name scoping and a ::date cast.
// THE BLOCKER IS ONLY VIEW SCOPE: PB-skillmatrix-079 and PB-dayplanner-079 are both CF-ufai-F-V2. These
// heroes were read on the DEFAULT view. Confirm the figure is present in V2 (skillmatrix V2 is the
// lesson modal, dayplanner V2 is the WILO tab) and bank against what V2 actually shows - do not inherit
// a V1 reading, which is the one-measurement-swept-two-views error this bank has already paid for.

// ★NAMED FIGURES FOR THE FOUR REMAINING OWED PAGES, and where each stands (measured 2026-08-19).
//   asset-hub    #ah-total-hero "TOTAL ASSETS 25 - 25 approved assets in this hive",
//                #ah-critical-hero 6, #ah-pending-hero "4 assets awaiting supervisor sign-off"
//   dayplanner   #dp-today-hero 0, #dp-week-hero 0, #dp-overdue-hero "3 items past their scheduled date"
//   skillmatrix  #sm-badges-hero "TOTAL BADGES 19 - 19 of 25 possible (5 levels x 5 disciplines)",
//                #sm-quizzes-hero 1
//   achievements #ac-level-hero "TOTAL LEVEL 155 - sum of levels across all 12 domains", #stat-top 80
// NO TWIN FOUND for any of them, each checked rather than assumed:
//   · index ops-home carries ONLY "9 OPEN JOBS", "28 PM OVERDUE", "3 LOW STOCK" - no asset count - and
//     all three already belong to existing passing pairs (index<->pm-scheduler, <->inventory, <->hive).
//   · skillmatrix counts badges over 5 levels x 5 DISCIPLINES while achievements sums levels over 12
//     DOMAINS. Different taxonomies, so 19 and 155 are not the same quantity at different precision.
//   · dayplanner's overdue counts schedule_items past their date; pm-scheduler's 28 counts overdue PMs.
//     Different tables and different objects.
// ONE ARITHMETIC QUESTION LEFT OPEN, deliberately NOT banked either way: asset-hub shows 25 APPROVED
// plus 4 PENDING = 29, while the pm_assets row count used as the bound in the "PM assets overdue" pair
// above is 30. That is either a third status this page does not surface (rejected/archived), or one
// asset is missing from a hero. It needs a psql read of pm_assets grouped by status to tell those apart,
// and until that read exists it is a question, not a finding - exactly the distinction that cost a
// withdrawal on analytics-report earlier today.

// ★alert-hub "5 PMS DUE" vs pm-scheduler - REJECTED, and not for the reason I expected (2026-08-19).
// Measured: alert-hub's AMC hero reads "5 PMS DUE"; pm-scheduler reads #stat-duesoon=2, #stat-overdue=28,
// #stat-ontrack=0. No figure matches. But the mismatch is NOT an agreement failure, because the two are
// not the same KIND of number: alert-hub's figure comes from the AMC DAILY BRIEF, a cron-produced
// amc_briefings row sitting in "AWAITING APPROVAL", so it is a stored snapshot with its own generation
// time and data cutoff - the roadmap's own CI truth for this page requires it to state both. Comparing a
// stored cron figure against a live rollup tests the snapshot-vs-live seam (CB S1 cron<->db), not
// cross_surface_agreement, and an equality assertion there would fail a page that is behaving correctly.
// A valid pair needs both sides computed over the same window AND at the same freshness.
// alert-hub's other figures (51 alerts, All 61 / AMC 10 / Risk 0) have no twin either: hive's summary
// cards are only #ss-card-jobs/-pm/-stock and index renders no alert element, both checked.

// ★analytics <-> analytics-report IS A REAL PAIR AND BOTH ROWS STAY OWED (measured 2026-08-19).
// Correcting two earlier mistakes of mine, recorded so neither is repeated:
//   (1) analytics-report is NOT an empty-state page. Read directly: press Generate and
//       #ar-report-mount holds one child of class doc-panel, #ar-doc exists, analytics-orchestrator
//       returns 200, and the report renders "Period: May 21, 2026 - Aug 19, 2026 (90d)". An earlier
//       numeric-leaf sweep returned [] only because it required a leaf whose ENTIRE text is a number,
//       and this report embeds its figures in prose. I nearly banked the row declared-na on that.
//   (2) The two sides DO share metrics, but a naive comparison manufactures failures. Measured:
//       analytics {oee 88%, pm_compliance 78.7%, worst_mtbf 0.6d} vs report {pm_compliance 79%,
//       "mtbf" 9d}. NEITHER difference is a defect:
//         - compliance 78.7 vs 79 is ROUNDING. 468/595 = 78.66%; analytics prints the precise value and
//           the report the rounded one. Compare at a declared precision, or compare the fraction.
//         - 0.6d vs 9d are DIFFERENT QUANTITIES. analytics says "WORST MTBF (PARTIAL) 0.6d CT-001" -
//           one asset, the worst - while the report's 9d is a fleet/average figure. A regex matching
//           /MTBF[^\d]{0,40}([\d.]+)d/ happily conflates them and reports a 15x disagreement.
// SO WHEN WIRING THIS PAIR: match the WORST-MTBF label specifically, not any MTBF; carry the
// "(PARTIAL)" qualifier through and confirm the report's figure is partial too, since a partial metric
// compared against a full one is the CPI-on-a-labour-only-proxy class; and normalise precision before
// asserting equality. OEE is the cleanest candidate - analytics has 88%, and the report should be read
// for its own OEE with the same partiality check.

// ★PAIR ALREADY MEASURED AND BANKED, NOT YET WIRED HERE - calculator catalogue size (2026-08-19).
// engineering-design's rendered per-discipline counts (HVAC 10, Mechanical 4, Electrical 14, Plumbing
// 10, Fire Protection 5, Machine Design 12) sum to 55, and index claims "55 calc types". They AGREE.
// PB-engineering-design-076 is banked on that live measurement; this note exists so the pair becomes
// permanent rather than a one-off, and it was NOT wired in the same pass because both sides need
// pre-stamped elements and a botched edit here would take out the 11 pairs that already pass.
//   persona: 'anon'  <- REQUIRED, and the reason is the whole trick. index.html is two products behind
//     one URL: the signed-in class swaps #mkt-wrap for #ops-home, so the marketing claim is simply not
//     in the DOM for a signed-in reader. Measured signed-in, side B returns NULL and the pair reads as
//     "one surface renders no number". Measured anon (#mkt-wrap block, #ops-home none) it returns 55.
//     engineering-design is a public tool and renders its catalogue to anon too, so ONE anon context
//     serves both sides - which suits this prover, since a pair shares a single page object.
//   a: engineering-design - no single element holds the total; `pre` must sum the numeric leaves whose
//     sibling text names a discipline, then stamp the sum onto an element readNum can see (check the
//     visibility rules before appending a bare span).
//   b: index - the claim lives in prose, so `pre` must match /(\d+)\s*calc types/i off body innerText
//     and stamp it the same way.
//   NON-VACUITY IS ALREADY ESTABLISHED: memory records this figure drifting across 51/53/58/60 on
//   different layers, so equality here has teeth. A sweep found exactly ONE calculator-count mention on
//   the landing page, so there is no second conflicting claim beside it. No DB oracle applies - the
//   catalogue is client-side, so these two surfaces ARE the two sources of truth being reconciled.

// ★LIVE FIGURE INVENTORY OF ALL 13 OWED PAGES (walked 2026-08-19, signed in as supervisor, so the next
// pass builds from measurement instead of re-walking). Sweep over [data-rag-label]/hero/stat/-num:
//   achievements       Composite skill score=155, Total level=155, 6/12 domains active, +1200
//   alert-hub          AMC assets checked=0, AMC PMs flagged=5, 0 high risk, 0 parts, 51, 5 crew
//   analytics          OEE (avg, partial)=88%, Worst MTBF (partial)=0.6d, PM compliance=79%
//   asset-hub          25, 6, 4  (UNLABELLED - identify before pairing)
//   dayplanner         0, 3      (UNLABELLED)
//   skillmatrix        4/5, 1, 19
//   report-sender      0
//   analytics-report, assistant, engineering-design, public-feed, resume, voice-journal   NO FIGURE
// public-feed is BANKED declared-na on two live walks. The other five empty pages are NOT, because this
// sweep used a narrow selector set and a page can render a figure outside it - re-check each with a
// wider lens before declaring, or the declaration rests on the lens rather than the page.
//
// PAIR CANDIDATES AND THE PREDICATE QUESTION EACH MUST ANSWER FIRST:
//   · alert-hub "AMC PMs flagged=5" vs pm-scheduler #stat-duesoon "Due soon (14d)" - ONLY valid if both
//     use the same window. AMC flags what its sweep considers due; pm-scheduler names 14 days. If the
//     windows differ these are different quantities and an equality check would fail a correct page.
//   · analytics "PM compliance=79%" - pm-scheduler has NO compliance figure (only #stat-duesoon,
//     #stat-ontrack, #stat-overdue), so its twin must be found on hive, which the roadmap says carries
//     one, or the row is NA.
//   · analytics OEE 88% and Worst MTBF 0.6d - both are labelled "(partial)". A partial metric compared
//     against a full one on another surface is the CPI-on-a-labour-only-proxy class; confirm both sides
//     carry the same partiality before pairing.
//   · achievements 155 vs skillmatrix 19 - REJECTED already, no shared quantity.

// ★THE 11 PASSING PAIRS COVER NONE OF THE 25 OWED ROWS, AND THAT IS PROBABLY THE ORACLE'S FAULT, NOT
// A MISSING WALK (measured 2026-08-19). The pairs here cover community, hive, pm-scheduler, inventory,
// logbook, shift-brain, index, project-manager, project-report. The owed cross_surface_agreement rows
// sit on thirteen OTHER pages: achievements, alert-hub, analytics, analytics-report, asset-hub,
// assistant, dayplanner, engineering-design, public-feed, report-sender, resume, skillmatrix,
// voice-journal. Zero overlap - so "11 pairs, 0 failing" is true and moves no owed row.
//
// THREE CANDIDATE PAIRS WERE BUILT AND REJECTED, each for a stated reason. They are recorded so the
// next pass does not spend the same effort rediscovering them:
//   · achievements XP vs community XP - REJECTED, DIFFERENT PREDICATES. achievements' only XP tile is
//     #ac-card-week, "XP this week"; the proven community/hive figure is a lifetime total (185). Equal
//     numbers would be a coincidence and unequal ones would not be a defect.
//   · achievements vs skillmatrix - REJECTED, NO SHARED FIGURE. achievements exposes XP this week,
//     Active domains, Total level, Composite skill score, Top skill domain; skillmatrix exposes On
//     target workers, Quizzes available, Total badges earned. Nothing is the same quantity.
//   · alert-hub critical count vs hive or index - REJECTED, THE SECOND SURFACE DOES NOT SHOW IT. The
//     roadmap asserts the alert count must agree across surfaces, but hive's summary cards are only
//     #ss-card-jobs/-pm/-stock and index renders no alert element at all. There is no twin to compare.
//
// SO: CF cross_surface_agreement was templated onto all 22 pages x 2 views, but a page can only hold
// this oracle if one of its figures ALSO appears somewhere else. For most of the thirteen it probably
// does not, which makes those rows R10 declared-na (no subject) rather than un-walked - the same
// disposition already applied to fallback_engaged on community/analytics-report. That must be settled
// PER PAGE against its actual tiles, never as one sweeping declaration over all thirteen.

import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { execFileSync } from 'node:child_process';
import path from 'path';
import { fileURLToPath } from 'node:url';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const HIVE = '084c113b-99c0-45c6-a8e8-b4b8349da46d';

const truth = (sql) => {
  const out = execFileSync('docker', ['exec', '-i', 'supabase_db_workhive', 'psql',
    '-U', 'postgres', '-d', 'postgres', '-t', '-A', '-c', sql],
    { encoding: 'utf8', timeout: 60000 }).trim();
  const n = Number(out.split('\n')[0]);
  return Number.isFinite(n) ? n : null;
};

// Each pair: the same fact as two surfaces render it, plus the DB question that settles both, plus a
// deliberately DIFFERENT predicate whose answer proves the check can discriminate.
const PAIRS = [
  {
    // ★SAME TABLE, SAME PREDICATES, SAME PERSON - all three verified BEFORE building, which is what
    // the two rejected candidates taught (achievements' xp_total is per-achievement; index's alert
    // count filters alert_kind while alert-hub's hero counts across kinds).
    // community #profile-xp (community.html:987) and hive's worker drawer (hive.html:4172) BOTH read
    // community_xp with .eq('hive_id') AND .eq('worker_name'), so they must agree.
    // ★RUN AS 'worker': the supervisor account has NO community_xp row, so this would be a vacuous
    // 0 == 0. Bryan Garcia has 185 (psql, and both surfaces render it).
    // ★THE DRAWER'S XP ELEMENT HAS NO id AND NO class, so it is tagged STRUCTURALLY - the <p> labelled
    // 'Community XP' and its next sibling. Tagging by the EXPECTED VALUE would make the check circular:
    // it would find 185 because 185 is what it went looking for.
    fact: 'community XP (community profile vs hive worker drawer)',
    persona: 'worker',
    a: { page: 'community', selector: '#profile-xp' },
    b: { page: 'hive', selector: '[data-xp-probe]', pre: "if (typeof _openWorkerProfileDrawer === 'function') _openWorkerProfileDrawer('Bryan Garcia'); setTimeout(function(){ var lbl = [].slice.call(document.querySelectorAll('p')).find(function(e){ return (e.textContent||'').trim() === 'Community XP'; }); if (lbl && lbl.nextElementSibling) lbl.nextElementSibling.setAttribute('data-xp-probe','1'); }, 1200);", preWait: 3000 },
    exact: { label: 'community_xp for this worker in this hive',
             sql: `select coalesce(xp_total,0) from community_xp where worker_name = 'Bryan Garcia' and hive_id = '${HIVE}'` },
  },
  {
    fact: 'PM assets overdue',
    a: { page: 'hive', selector: '#ss-pm-hero' },
    b: { page: 'pm-scheduler', selector: '#stat-overdue' },
    // pm-scheduler's overdue is a client rollup, so the DB question here is the SET both surfaces
    // summarise, not a re-implementation of the fold: how many assets the hive has at all. A pair
    // claiming more overdue assets than the hive owns is impossible regardless of the predicate.
    bound: { label: 'assets in this hive (an upper bound both must respect)',
             sql: `select count(*) from pm_assets where hive_id = '${HIVE}'` },
  },
  {
    fact: 'low-stock parts',
    a: { page: 'hive', selector: '#ss-stock-hero' },
    b: { page: 'inventory', selector: '#stat-low' },
    exact: { label: 'is_low_stock over the hive+status set',
             sql: `select count(*) from v_inventory_items_truth where hive_id = '${HIVE}'`
                + ` and status in ('approved','pending','rejected') and is_low_stock` },
    discriminator: { label: 'a naive qty_on_hand <= 1 threshold',
                     sql: `select count(*) from v_inventory_items_truth where hive_id = '${HIVE}'`
                        + ` and status in ('approved','pending','rejected') and qty_on_hand <= 1` },
  },
  {
    fact: 'open jobs',
    a: { page: 'hive', selector: '#ss-jobs-hero' },
    b: { page: 'logbook', selector: '#open-count' },
    discriminator: { label: 'open jobs across ALL workers (what a lost identity filter would show)',
                     sql: `select count(*) from logbook where status = 'Open'` },
  },
  // ── shift-brain shares THREE facts with three different owners ───────────────────────────────────
  // An AI shift planner is exactly where a stale copy does damage: it decides who is sent where. If its
  // PM count drifts from pm-scheduler's, the plan is built on a number the scheduler no longer agrees
  // with, and nothing on either screen looks wrong.
  {
    fact: 'PM overdue (shift-brain vs scheduler)',
    a: { page: 'shift-brain', selector: '#sb-pms-hero' },
    b: { page: 'pm-scheduler', selector: '#stat-overdue' },
    bound: { label: 'assets in this hive (an upper bound both must respect)',
             sql: `select count(*) from pm_assets where hive_id = '${HIVE}'` },
  },
  {
    fact: 'open jobs carried (shift-brain vs hive)',
    a: { page: 'shift-brain', selector: '#sb-carry-hero' },
    b: { page: 'hive', selector: '#stat-open' },
    exact: { label: 'open logbook entries hive-wide',
             sql: `select count(*) from logbook where hive_id = '${HIVE}' and status = 'Open'` },
    discriminator: { label: 'open entries for ONE worker (what a mis-scoped read would show)',
                     sql: `select count(*) from logbook where hive_id = '${HIVE}' and status = 'Open'`
                        + ` and worker_name = 'Leandro Marquez'` },
  },
  {
    fact: 'low-stock parts (shift-brain vs inventory)',
    a: { page: 'shift-brain', selector: '#parts-count' },
    b: { page: 'inventory', selector: '#stat-low' },
    exact: { label: 'is_low_stock over the hive+status set',
             sql: `select count(*) from v_inventory_items_truth where hive_id = '${HIVE}'`
                + ` and status in ('approved','pending','rejected') and is_low_stock` },
    discriminator: { label: 'a naive qty_on_hand <= 1 threshold',
                     sql: `select count(*) from v_inventory_items_truth where hive_id = '${HIVE}'`
                        + ` and status in ('approved','pending','rejected') and qty_on_hand <= 1` },
  },
  // ── index's ops-home repeats three specialist facts on one landing tile row ──────────────────────
  // The anatomy does not mark index as a cross-page surface; it demonstrably is. Its ops-home renders
  // data-kpi tiles for open-jobs, pm-overdue and low-stock - the same three questions logbook,
  // pm-scheduler and inventory each own. A landing page that quietly disagrees with the page it links
  // to is the worst place for drift, because it is the number people see first and the one they act on
  // without opening anything.
  {
    fact: 'PM overdue (index vs scheduler)',
    a: { page: 'index', selector: '[data-kpi="pm-overdue"] .oh-tile-num' },
    b: { page: 'pm-scheduler', selector: '#stat-overdue' },
    bound: { label: 'assets in this hive (an upper bound both must respect)',
             sql: `select count(*) from pm_assets where hive_id = '${HIVE}'` },
  },
  {
    fact: 'low-stock parts (index vs inventory)',
    a: { page: 'index', selector: '[data-kpi="low-stock"] .oh-tile-num' },
    b: { page: 'inventory', selector: '#stat-low' },
    exact: { label: 'is_low_stock over the hive+status set',
             sql: `select count(*) from v_inventory_items_truth where hive_id = '${HIVE}'`
                + ` and status in ('approved','pending','rejected') and is_low_stock` },
    discriminator: { label: 'a naive qty_on_hand <= 1 threshold',
                     sql: `select count(*) from v_inventory_items_truth where hive_id = '${HIVE}'`
                        + ` and status in ('approved','pending','rejected') and qty_on_hand <= 1` },
  },
  {
    // ★I PAIRED THIS WRONG FIRST AND THE NUMBERS CAUGHT ME. index's tile read 9 and logbook's
    // #open-count read 6, which looked like drift. It is not: 9 is the HIVE-WIDE open count and 6 is
    // THIS WORKER'S (confirmed in psql: 9 and 6 for the same hive). logbook opens worker-scoped, so
    // #open-count answers a different question from a landing tile. hive itself renders BOTH -
    // #stat-open = 9 and #ss-jobs-hero = 6 - and is right to. Comparing them was my oracle not
    // matching the claim, the same error this bank keeps catching in me.
    // So the pair is like-for-like (both hive-wide), and the WORKER-SCOPED count becomes the
    // discriminator: if either surface silently lost its scope, this check goes red.
    fact: 'open jobs hive-wide (index vs hive)',
    a: { page: 'index', selector: '[data-kpi="open-jobs"] .oh-tile-num' },
    b: { page: 'hive', selector: '#stat-open' },
    exact: { label: 'open logbook entries hive-wide',
             sql: `select count(*) from logbook where hive_id = '${HIVE}' and status = 'Open'` },
    discriminator: { label: "ONE worker's open entries (what a scope slip would show)",
                     sql: `select count(*) from logbook where hive_id = '${HIVE}' and status = 'Open'`
                        + ` and worker_name = 'Leandro Marquez'` },
  },
  // ── one project, two surfaces: the board a manager works in and the report an executive reads ────
  // Both must state the same progress for the same project at the same instant. A report is written
  // once while the detail keeps moving, which is the classic way these two drift apart.
  // ★I PICKED BOTH SELECTORS WRONG FIRST, and the readings said so rather than agreeing by luck.
  // project-report's #progress-section is a TABLE OF PROGRESS LOG ENTRIES - my regex pulled the first
  // row's "0%", one update's figure rather than the project's. project-manager's #p-pct exists but
  // sits empty and unrendered inside a detail pane nobody opened. Two wrong subjects, and "null vs 0"
  // was the only reason I looked twice. The real shared figure is 52%, carried by the exec summary's
  // KPI on the report and by THIS project's card on the board - scoped by the id inside its own
  // openDetail handler, so the pair cannot quietly read some other project's number.
  {
    fact: 'project progress % (manager vs report)',
    a: { page: 'project-manager', selector: '[onclick*="539e0d9a-9ff7-474b-ab03-9254406ca7dc"]',
         extract: /(\d{1,3})\s*%/, settle: 7000 },
    b: { page: 'project-report', selector: '#exec-summary .kpi-value',
         query: '?project_id=539e0d9a-9ff7-474b-ab03-9254406ca7dc', extract: /(\d{1,3})\s*%/, settle: 8000 },
  },
];

const readNum = async (page, url, selector, opts = {}) => {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(opts.settle || 4500);
  // ★A SIDE MAY LIVE BEHIND A DISCLOSURE. hive renders its community_xp figure inside a person card that
  // must be opened first, and the figure has no stable id until it exists - so a side can carry `pre`,
  // an in-page expression run before the read. Kept as an explicit per-side field rather than a global
  // sweep: this prover compares two SPECIFIC numbers, and pressing things it was not told to press is
  // how an inducing probe changes the value it came to measure.
  if (opts.pre) {
    await page.evaluate((src) => eval(src), opts.pre).catch(() => {});
    await page.waitForTimeout(opts.preWait || 2500);
  }
  const t = (await page.textContent(selector).catch(() => null) || '').trim();
  // ★NOT EVERY SURFACE PUTS ITS NUMBER IN AN ELEMENT OF ITS OWN. A tile can afford a dedicated span;
  // a written report states the same figure inside a sentence. Requiring a bare numeric node would
  // have reported "this page makes no claim" about a report that states the claim plainly in prose -
  // the same proxy error this bank keeps catching. `extract` pulls the figure the pair is about out
  // of the text, and is deliberately per-pair rather than a global heuristic, so nobody has to guess
  // which number in a paragraph was meant.
  if (opts.extract) {
    const m = opts.extract.exec(t.replace(/\s+/g, ' '));
    return m ? Number(m[1].replace(/,/g, '')) : null;
  }
  return /^-?\d[\d,]*$/.test(t) ? Number(t.replace(/,/g, '')) : null;
};

const run = async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await assertSignedIn(signIn(ctx, 'supervisor'));
  const out = { origin: ORIGIN, pairs: [] };

  for (const p of PAIRS) {
    const rec = { fact: p.fact, a: { ...p.a }, b: { ...p.b } };
    // ★A PAIR MAY NEED A DIFFERENT IDENTITY. The community/hive XP pair reads community_xp and the
    // supervisor test account has NO row there, so the comparison would have been 0 == 0 - vacuous, and
    // the zero-denominator rail rejects that. Bryan Garcia has 185. I recorded this blocker TWICE as
    // "needs a persona or a seeder"; the persona already existed in live_page_journeys (role 'worker'),
    // so the blocker was mine, not the harness's. A pair can now name the identity it needs.
    let pairCtx = ctx;
    if (p.persona) {
      pairCtx = await browser.newContext({ viewport: { width: 390, height: 844 } });
      await assertSignedIn(signIn(pairCtx, p.persona));
    }
    const page = await pairCtx.newPage();
    try {
      rec.a.value = await readNum(page, `${ORIGIN}/workhive/${p.a.page}.html${p.a.query || ''}`,
                                  p.a.selector, p.a);
      rec.b.value = await readNum(page, `${ORIGIN}/workhive/${p.b.page}.html${p.b.query || ''}`,
                                  p.b.selector, p.b);
      if (rec.a.value === null || rec.b.value === null) {
        rec.ok = false;
        rec.why = 'one of the two surfaces is not rendering a number, so there is nothing to compare — '
                + 'recorded as a failure to compare, never as agreement';
      } else {
        rec.agree = rec.a.value === rec.b.value;
        if (p.exact) { rec.exact = { ...p.exact, value: truth(p.exact.sql) }; }
        if (p.bound) { rec.bound = { ...p.bound, value: truth(p.bound.sql) }; }
        if (p.discriminator) {
          rec.discriminator = { ...p.discriminator, value: truth(p.discriminator.sql) };
          rec.discriminates = rec.discriminator.value !== rec.a.value;
        }
        const dbOk = rec.exact ? rec.exact.value === rec.a.value
                   : rec.bound ? rec.a.value <= rec.bound.value : true;
        rec.ok = rec.agree && dbOk;
        rec.why = !rec.agree ? `the two surfaces disagree: ${p.a.page} ${rec.a.value} vs ${p.b.page} ${rec.b.value}`
                : !dbOk ? 'the two surfaces agree with each other but NOT with the database — agreement '
                        + 'on a falsehood, which is worse than a visible disagreement'
                : 'both surfaces and the database say the same thing';
      }
    } catch (e) { rec.error = String(e.message || e).slice(0, 180); rec.ok = false; }
    await page.close();
    if (pairCtx !== ctx) await pairCtx.close();
    out.pairs.push(rec);
    console.log(`  ${rec.ok ? 'PASS' : 'FAIL'}  ${p.fact.padEnd(20)} ` +
      `${p.a.page}=${rec.a.value} ${p.b.page}=${rec.b.value}` +
      (rec.exact ? ` db=${rec.exact.value}` : '') + (rec.bound ? ` bound=${rec.bound.value}` : '') +
      (rec.discriminator ? `  [discriminator ${rec.discriminator.value}${rec.discriminates ? ' - differs, so the check has teeth' : ' - SAME, coincidence possible'}]` : '') +
      (rec.error ? `  ${rec.error}` : ''));
  }

  await browser.close();
  writeFileSync(path.join(ROOT, 'cross_surface_report.json'), JSON.stringify(out, null, 1));
  console.log(`\n  ${out.pairs.length} pair(s) · ${out.pairs.filter((r) => !r.ok).length} failing`);
};

run().catch((e) => { console.error(e); process.exit(1); });
