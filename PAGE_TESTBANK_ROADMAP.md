# PAGE TESTBANK ROADMAP — 200 live-MCP scenarios per production page, 22 pages, 4,400 rows

_Opened 2026-08-05. Ian: "get 200 scenarios each for every production pages … same manner using the
framework with anti-drift discipline and momentum discipline … author those scenarios first [walk
later] … lay it out so that we have an objective 200 scenarios each … itemized each and with
percentage completion per page so that you won't drift."_

The marketplace bank (877 scenarios, `live_mcp_registry.json`, `MARKETPLACE_ITERATION_ROADMAP.md`)
is the proven instrument. This arc runs the same instrument over every other production page. The
marketplace bank stays its own bank, on its own board — merging 4,400 fresh owed rows into it would
bury both numbers.

---

## §0 · ANTI-DRIFT RAILS (read first, every session)

> ### ★★★ A15 · ONE-WAY GREEN — owed → green, and green STAYS green. No churn.
>
> **Ian, 2026-08-08:** *"sort always why we are having back and forth like from green to stale, then
> stale to green, we have to focus to make the owed ones to make it green and keep it from becoming
> stale, it would be an endless endeavors if we keep on doing that."*
>
> **The churn is arithmetic, not bad luck.** Evidence expires with the code under it (R4), so **every
> edit after a bank converts my own green rows to stale**, and re-walking them earns nothing — the row
> was already green once. A session that fixes and banks in the wrong order runs a treadmill: it can
> post +59 rows and finish with green *lower* than it started. Measured this session:
>
> | edit | rows expired | effect |
> |---|---|---|
> | `utils.js` × 3 (one rgba, one transport wrapper, one notice helper) | **843** marketplace rows | green **752 → 34** |
> | 4 page files edited after banking (`hive`, `asset-hub`, `alert-hub`, `project-report`) | **40** page rows | green 400 → 392 |
> | `inventory.html` edited after banking its rows | **19** page rows | net **+32 banked = −8 green** |
>
> **THE RULE — a surface is touched once, then walked once, then never re-opened:**
>
> 1. **SHARED FILES FIRST, BATCHED, BEFORE ANY WALK.** `PAGE_DEPS = {page_file, "utils.js"}`, so a
>    shared-library edit is a **global** expiry — it invalidates every row on every page. Collect all
>    `utils.js` / `components.css` / `tokens.css` / shared-chrome work into ONE wave, land it, *then*
>    start walking. **Never touch a shared file mid-walk**, however small the fix. A 29px cosmetic chip
>    is not worth 650 expired rows; queue it for the next wave.
> 2. **THEN per page: all fixes → walk → bank.** A12 already says this; A15 says it is not optional and
>    not per-defect. Finish the page's *entire* fix list before the first reading, even when a walk
>    surfaces a new defect mid-pass — record it, finish the walk, fix it in the page's next wave.
> 3. **A re-walk is a LOSS, not progress.** Report it as such. "Re-earned 64 rows" after expiring 64 is
>    net zero with the tokens spent. The only number that counts is **owed → green**.
> 4. **Prefer the narrowest anchor (A13).** A DB claim anchored to `supabase/migrations` survives every
>    cosmetic page edit. Wide anchors are what make a small edit expensive.
>
> **The forcing question before ANY edit once walking has begun:** *how many banked rows does this file
> touch, and is the fix worth them?* If the answer is a shared file, the answer is no — queue it.
>
> A15 exists because A12 was too narrow: it governed per-page ordering and said nothing about shared
> files, which caused 843 of the 902 rows lost this session.
>
> **★ A15 WORKED EXAMPLE — the forcing question answered with numbers (2026-08-08).** A live 500 injected
> into `inventory.html`'s own reads showed 27 parts and 3 low rendering as six zeros under the words
> **"OUT OF STOCK 0 · CLEAR"**, **"LOW STOCK 0 · Every part above its reorder point · STOCKED"** and
> **"No parts in inventory yet"**, with **no notice at any of five samples across ~15s** — a stockroom
> certifying itself STOCKED while blind. The forcing question: *how many banked rows does this file touch,
> and is the fix worth them?* Measured answer: **14** (page banks green 670 → 656, stale 137 → 151), and
> **yes** — someone reorders what is on the shelf, or skips a job for a part that was in stock. The fix
> then earned **1** row back (657), so the honest ledger for the edit is **+1 green, 14 owed a re-walk**,
> reported as a LOSS per clause 3 rather than dressed up as progress.
>
> Two things that make the answer *yes* rather than *no*: the defect was a **safety-of-use** claim, not a
> cosmetic one; and the fix needed **no shared file** — `_invReadErr` had existed at `inventory.html:2065`
> since the P2 "honest-degraded" change and merely stopped one function short of the render, so three
> local edits closed it. **Had the same fix required `utils.js`, clause 1 says queue it** — that single
> file expired 843 rows three times over.
>
> **★★ THE CHURN IS SEQUENCING, NOT A TOOLING BUG — measured, and the tempting "fix" would manufacture
> false greens (2026-08-08).** Chasing the back-and-forth to its mechanism: `tools/bank_page_walk.py:163`
> stamps `V.fn_digests(deps)` across the WHOLE page file, so a single `ordering_totality` row on
> `dayplanner` names `showToast`, `getItemStatus`, `loadSchedule`, `syncItemToSupabase` and every other
> function in the file. Editing `loadSchedule` therefore expires **every row on the page**. Measured cost of
> two honest fixes in one wave: `inventory.html` **−14** rows, `dayplanner.html` **−32** (green 670 → 656 →
> 624, stale 137 → 184), with 2 re-earned. That is the "endless endeavour".
>
> **The obvious fix — narrow the stamping so an edit expires fewer rows — is WRONG, and naming why is the
> point.** Those rows are live readings of *rendered output*. A render can be changed by almost any function
> in the file, so a row read against different code genuinely no longer rests on anything: expiring it is
> the rail working. Narrowing the dependency to "the functions I think the oracle touched" would keep rows
> green whose evidence no longer matches the code — a false green anchored to a real measurement, the
> hardest kind to ever find again. `naming every function is naming none` is a real defect **when the row
> names functions it does not depend on**; a whole-page render reading depends on the whole page.
>
> **So the answer is the ORDERING A15 already states, and my violation of it was the whole cost:** for each
> page, land EVERY fix, THEN walk it once, THEN bank. Interleaving fix→bank→fix on the same file pays the
> expiry twice. Nothing expires during a walk, because a walk changes no code — **the bank only churns when
> I edit between banks.** Concretely, for the remaining pages: never bank a page I still intend to edit.
>
> **Corollary learned the same day — WHERE the failure is reported decides whether the row can be green.**
> A notice delivered by a **toast** satisfies "the page said something" for about one second and then
> leaves confident zeros on screen indefinitely; a failure carried in the rendered **state** (the em-dash
> sentinel, tag `UNKNOWN`, the verdict suppressed) is still true at 12s. Measured across nine pages: 3
> silent (`hive` with 42 intercepted requests, `dayplanner`, `skillmatrix`), 2 transient (`logbook`,
> `project-manager` — which also echoes the raw upstream message), 2 persistent-and-legible (`community`'s
> "✕ Could not load posts", `analytics`' "Analysis failed, **check console**" — honest but unactionable for
> a technician), and `pm-scheduler` persistent yet contradicted by "OVERDUE 0 · No overdue PMs · CLEAR" on
> the same screen. **So a `fail_*` row banks green only when the failure survives in the state; a toast
> earns a `qualified` finding, never a green.** This is also why a single-instant reading of any `fail_*`
> oracle is not reproducible — and why an earlier pass on this bank recorded "says nothing" on 11 of 16
> pages, retracted it, and a later pass recorded 12 of 12 passing. Both were true, at different instants.

Rules 1–6 are inherited **verbatim** from `MARKETPLACE_ITERATION_ROADMAP.md` §0 and enforced by the
same gate (`tools/validate_live_mcp_bank.py`, now multi-bank): typed evidence; evidence expires with
the code under it (R4/R4b/R4c/R7); a structural probe may not settle a behavioural oracle (R6);
LIVE-MCP walks only bank; stale is visible, never absorbed (R5); verify the instrument before the
page. Four new rails, because this arc's failure mode is **authoring fiction at scale** — 4,400
grounded rows and 4,400 plausible ones look identical in a JSON file:

| # | rule | what enforces it |
|---|---|---|
| A7 | **A subject must be OBSERVED, not assumed.** Every anatomy entry carries `seen:{how, ref}` — a file:line or a live enumeration. | `build_page_live_mcp_bank.py` refuses to build a page whose anatomy has an unsourced subject. |
| A8 | **Exactly 200 rows, or the build fails.** Under-supply = incomplete Ground pass; over-supply = the ranked tail is recorded `deferred` with its reason. | The generator's frame arithmetic is asserted at build time; `--selftest` proves it fires. |
| A9 | **A claim already proven in another bank INHERITS its evidence; it is never re-walked.** Keyed on `(url, oracle, persona/state)`. | The generator's inherit pass copies the original evidence (ref, sha, fn_digests) so it **expires with the original**. |
| A10 | **A vacuous cell is recorded, never counted.** An oracle with no subject on a page (public-feed has no writes) is swapped for a ranked-tail row and the vacuity is recorded in the bank's `declared_na` list with its reason + receipt. | The generator refuses an `na` entry without `reason` + `replace_with`; the bank still totals exactly 200 scored rows. |
| A11 | **FINISH ALL OWED — the arc closes at `owed = 0` on every bank, nothing less** (Ian, 2026-08-06: *"you have to put the framework in that roadmap that you have to finish all of it owed"*). No page, family or session may be called done while a single owed row remains. A green headline over 4,221 owed rows is the "one metric at 100% ≠ the roadmap is done" error at scale. | §2's completion clause + the gate's per-bank `owed` column, which never rounds to zero. |
| A15 | **ONE-WAY GREEN — see the boxed rail at the top of this §0.** Shared-file edits batched into one wave BEFORE any walking; per page, all fixes → walk → bank; a re-walk is a loss, not progress; the only number that counts is owed → green. | Measured 2026-08-08: `utils.js` × 3 expired **843** marketplace rows (green 752 → 34); four page edits after banking expired **40** more; `inventory.html` turned +32 banked into **−8** green. A12 governed only per-page ordering, which is why 843 of the 902 lost rows escaped it. |
| A12 | **FIX BEFORE BANK, per page.** Fixing defects *as the walk finds them* is the job — but a page edit expires every claim anchored to that file (whole-file sha, R4), so **finish a page's fixes, THEN walk it, THEN bank.** Banking first and editing after silently converts your own green rows to stale. | Measured 2026-08-06: the `index.html` contrast fix expired **18** freshly-banked index rows; the `dayplanner.html` `#logo-view` fix expired **5**. Both had to be re-walked. |
| A13 | **ANCHOR BY EVIDENCE — declare `deps` explicitly for a DB claim.** A claim about RLS, a trigger or a ledger rests on `supabase/migrations` (and its gate), never on whichever page was open. The banker's auto-router reads the prose, so an RLS row that also mentions the browser gets page-anchored by accident. | Measured 2026-08-06: `PB-index-060` (anon reaches 0 rows) was page-anchored and expired within the hour on an unrelated CSS edit — a cosmetic change invalidating a database claim, and worse, a migration could have changed the policy without expiring it. Pass `"deps": ["supabase/migrations", "<gate>"]`. |
| A14 | **VERIFY THE INSTRUMENT BEFORE THE PAGE.** A clean reading from a broken lens is the most expensive kind of false green. | Three instrument faults caught 2026-08-06: `layout(390)` cannot move the viewport from inside the page (it reported `onTarget:false` at innerWidth 1280 — those "0 overflow" readings were at 1280); `requestAnimationFrame` is background-throttled to ~1.7fps without `bringToFront` (15 frames in 9s, far too coarse for frame-level atomicity); an icon-name enumerator that read only `aria-label`/`title` reported a *correctly named* control as unnamed, because it ignored content-derived names and the enclosing `role=group` label. |

> Named A7–A10 (arc rails) rather than R7–R10 because the validator already owns R7 — "a layer/seam
> claim must depend on what it actually rests on" — and two rules sharing one name is itself drift.

**The one line to remember:** *a scenario without a receipt for its subject is a tour, not a test.*

---

## §1 · THE FRAME — fixed arithmetic, page-specific fill

Identical for all 22 pages. What differs per page is the **subjects** its anatomy supplies
(`page_bank_anatomy/<page>.json`): 4 layers · 5 seams · ≥3 views · ≥3 components · ≥3 journey
personas · 2 identity personas · 6 bespoke invariants · 8 bespoke domain truths. Oracle text for
the templated families is taken **verbatim** from the `ORACLES` table in
`tools/build_live_mcp_registry.py` — one source of truth, imported, never copied.

Row numbering is fixed platform-wide, so `PB-<page>-###` means the same thing on every page:

| rows | family | mandate | expansion |
|---|---|---|---|
| 1–20 | CA layer-contract | F1 | 4 layers × (envelope_shape · status_body_agreement · idempotency · ordering_totality · units_declared) |
| 21–40 | CB seam | F1 | 5 seams × (value_survives · name_survives · null_semantics · partial_write) |
| 41–54 | CC failure-injection | F1 | 2 views × (fail_500 · fail_401 · fail_timeout · fail_partial · fail_slow · fail_offline · fail_null_field) |
| 55–60 | CD invariant | F1 | 6 bespoke, written per page in the anatomy |
| 61–70 | CE ufai-U | F2 | 2 views × (one_vocabulary · source_chip_true · units_visible · no_raw_enum · number_explained) |
| 71–82 | CF ufai-F | F2 | 2 views × (effect_in_db · effect_visible · count_matches_source · money_matches_ledger · idempotent_repeat · cross_surface_agreement) |
| 83–92 | CG ufai-A | F2 | 2 views × (offline_refusal · retry_path · rate_limit_legible · fallback_engaged · slow_honest) |
| 93–102 | CH ufai-I | F2 | 2 identity personas × (bola_object · bfla_function · tenant_boundary · jwt_not_body · boundary_not_emptiness) |
| 103–110 | CI domain-truth | F2 | 8 bespoke, written per page in the anatomy |
| 111–125 | CJ ui-layout | F3 | 3 views × (w390_overflow · w641_overflow · w1280_overflow · tap_target_44 · safe_area) |
| 126–140 | CK ui-state | F3 | 3 components × (component_loading · component_skeleton · component_disabled · component_busy · component_populated) |
| 141–155 | CL ui-visual | F3 | 3 views × (contrast_wcag · contrast_apca · focus_visible · reduced_motion · icon_only_name) |
| 156–170 | CM ux-comprehension | F4 | 3 views × (what_is_this_number · what_happens_next · what_does_it_cost · why_refused · reward_explained) |
| 171–185 | CN ux-journey | F4 | 3 journey personas × (first_run_to_value · repeat_visit · cross_surface_handoff · two_sided_same_object · abandon_resume) |
| 186–200 | CO ux-recovery | F4 | 3 views × (double_tap · back_out · session_died · wrong_then_fix · did_it_land) |

**F1 60 + F2 50 + F3 45 + F4 45 = 200.** The generator fails on any other number (A8).

---

## §2 · THE %-BOARD — computed, never typed

**Every number comes from `python tools/validate_live_mcp_bank.py --report`.** Denominator rule:
green ÷ (green + owed), **stale excluded** so drift shows instead of being absorbed. A hand-edited
percentage in this document is the drift this document exists to prevent — this section names the
command and holds only the *targets*:

- **Per page:** all 22 pages to 100% green over non-stale — the walk arc's target.
- **Per family:** the walk drives the **lowest-green family across pages**, not page-by-page only —
  a low family across N pages is usually ONE unadopted central component, never N page bugs
  (CENTRALIZE-FIRST). Known cohort already found at authoring time: `analytics` / `alert-hub` /
  `shift-brain` render the same verdict/hero chrome under `an-`/`ah-`/`sb-` prefixes — a defect on
  one is asserted against all three.
- **A page is not done at one green family.** Page-% AND family-% must both be read; F3 100% over
  F1 20% is pretty layout over an unproven stack.

### §2a · THE COMPLETION CLAUSE (A11, binding)

**The arc closes when `owed = 0` and `stale = 0` on every bank — 5,277 of 5,277 green. Nothing
less counts as done.** Two distinct debts, tracked separately so neither hides behind the other:

| debt | what it is | how it is discharged |
|---|---|---|
| **4,221 owed** page-bank rows | never walked | walk on the LIVE MCP browser, fix what it finds, bank typed evidence |
| **815 stale** marketplace rows | were true, the ground moved | **re-walk, never `--accept`** — a stale row treated as green is the one failure this whole bank exists to prevent |

Three things that are **not** completion, named because each has been claimed before:
1. **A green %-board over a large owed count.** The denominator excludes stale by design; it does
   *not* excuse owed. `4.1% green` and `0 stale` are both true today and the arc is 4% done.
2. **A page whose lens-measurable families (F3 UI) are green.** F3 is the cheapest third to walk
   — three widths and a battery per view. F1 architecture (1,320 rows: layer contracts, seams,
   failure injection) and F2 UFAI (1,100 rows: identity, function, domain truth) are where the
   real defects live, and they need psql, forged-identity probes and injected failures.
3. **"The originating issue is fixed."** The seed defect is the *start* of a bank, never its end.

**Progress is reported by running the gate, never from memory.** The board is regenerated with
`python tools/validate_live_mcp_bank.py`; per-page and per-family aggregation is derived from that
output only — never re-derived by re-implementing `classify()` with hand-built gate/url sets, which
fabricates zeros (done twice now: once reporting a false "647 invalid" when the gate said 0, once
reporting a false 0/4400 green when the gate said 179).

Roster (22): index · hive · logbook · inventory · pm-scheduler · project-manager · dayplanner ·
asset-hub · analytics · alert-hub · skillmatrix · shift-brain · voice-journal · assistant ·
community · public-feed · achievements · engineering-design · resume · report-sender ·
project-report · analytics-report.

**Out of scope, recorded not skipped:** design-system, symbol-gallery, validator-catalog,
architecture, status, audit-log, ai-quality, llm-observability, agentic-rag-observability (ops/meta
consoles), and the marketplace surfaces (they keep their own 877-row bank).

**Un-grounded subjects (A7 holds them open):** analytics' full chart-source list, assistant's panel
ids, resume's anon persona, report-sender's send transport — each carries a `static-partial` seen
ref and MUST be re-grounded live before its rows may bank green.

---

## §2b · THE ANTI-STALE DISCIPLINE (A16, binding) — evidence is a RECIPE, not a memory

Sits beside the anti-drift rails (§0), the Memento reflex and the momentum drive (§3) as a fourth
standing discipline, because staleness is the one debt that **grows while you work**. Measured on
2026-08-11: one session took the page banks from 260 stale to 501 while fixing 13 real defects. Nothing
was done wrong to cause most of that — it is what a bank of perishable evidence does when the code moves.

### The principle the whole section rests on

> **A stale row's cost is not the staleness. It is whether its evidence can be RE-DERIVED BY A MACHINE.**

Two rows went stale the same day. One was `ordering_totality`, and 48 of them came back green in a
single command because a tool re-proves the claim from the page source plus the live catalog. The other
was `contrast_wcag`, and it stays stale because its measurement lived only in a session's head — the
numbers were real, the *method* was never written down as something runnable.

That is the whole difference, and it reframes Ian's standing "stop chasing stale" correctly:

> **"Stop chasing stale" never meant "leave stale forever." It meant STOP HAND-RE-DERIVING IT.**
> Re-walking a row by hand costs a session and buys one row. Writing its prover costs a session and buys
> that row **and every future expiry of it**. When a claim has no prover, the honest unit is not the
> re-walk — it is the prover.

### A16.1 · PREVENT — fewer rows expire in the first place

| # | mechanism | state |
|---|---|---|
| **P1** | **Narrowest honest anchor.** A claim declares what it *rests on*, not what was open when it was proven. R7 both halves: `LAYER_DEPS` (marketplace) and `PAGE_LAYER_DEPS` (page banks). A db claim rests on `supabase/migrations`; only a CLIENT claim rests on the page. | **built** — the page-bank half added 2026-08-11 after finding R7 silent on all 440 page-bank layer rows, 92 of them false greens a migration could never expire |
| **P2** | **Per-function digests, recorded narrowly.** R4b lets a file change *around* a claim without expiring it — but only if the row records the functions its oracle actually exercised. A row naming all 168 functions in `utils.js` has opted out. | built; the discipline is the narrow recording |
| **P3** | **The birth check.** The banker must REFUSE evidence that is already stale when written — measured before the last modification of a file it depends on. | **new** — this is exactly the mistake made on 2026-08-11: report-sender's 3 rows were banked and then the same file was edited again, expiring them within the minute |
| **P4** | **A15 batching, with its corollary.** All edits to a page land *before* any walk of it — and never bank a page you are still editing. | rail exists; P3 makes it mechanical |
| **P5** | **A report older than its prover is not evidence.** P3 asks *"did the code move after the measurement?"*; P5 asks the same question about the **measuring instrument**. If a row's `replay` names `tools/<prover>.py` and that file's mtime is newer than the report being banked, the report describes an instrument that no longer exists — REFUSE it and re-run the replay. | **new 2026-08-11** — `read_idempotency_report.json` sat 12 minutes older than the fix to its own prover, still carrying two pre-fix `NOT-IDEMPOTENT` verdicts for `v_ai_reports_truth`. The re-run meant to refresh it reported **exit 0 with no output and no file**, which read as success: it had been invoked as `timeout 900 … --gate \| tail`, the 15-minute limit killed a sweep that needs ~550 `docker exec` round trips, and the **pipeline returned `tail`'s status instead of the prover's**. A stale report is indistinguishable from a fresh one by eye, and a killed run is indistinguishable from a clean one through a pipe; two fabricated findings were one command from being banked. The sharpest form of the rule: *the instrument is the half that reads as trustworthy precisely because it is a tool.* Corollary for every prover invocation — **redirect to a file, never pipe, when the exit code carries meaning.** **EXTENDED 2026-08-13: the check matched `tools/*.py` ONLY, so the entire BROWSER prover tier was exempt from the rail written to protect it** — and that is the tier that needed it most, having taken twenty-plus corrections in a single day (a 1.5× scale factor, a recorder armed 650ms late, an ancestor credit that cannot move a `fixed` box, a `PASS` printed over zero measurements). Any of those edits landing after a report would have left a verdict on disk the current instrument never produced, and the rail would have said nothing. **A rail that silently skips a whole tier is worse than no rail, because the green it lets through carries the rail's name.** Now `(?:py|mjs)`. |

| **P6** | **`supabase/migrations` is the DB-side `utils.js` — land every migration a turn needs FIRST.** A15 batches page edits before a walk; the same rule governs the migrations directory, which is the most shared dependency in the bank. | **new 2026-08-12** — landing one migration mid-turn took the page banks from **900 green to 395**, and stale from 447 to **1009**: 561 rows anchored to `supabase/migrations` expired at once. Rows banked with R4b `fn_digests` survived; the 561 that fell were banked before that stamp existed. So the wave is really two lessons: **sequence migrations first**, and **a row without `fn_digests` has opted out of every protection R4b offers.** |

| **P7** | **An oracle must credit the right MECHANISM, not merely find the right property.** When a check satisfies itself from something other than the element under test — an ancestor's rule, a sibling's declaration, a shared token — it must prove that mechanism actually *reaches* the subject. Two questions, both cheap, both skipped by default: *does this rule apply in the right DIRECTION?* and *can this rule physically move this box?* | **new 2026-08-13** — the CJ `safe_area` prover was corrected **seven** times. The first five stopped it inventing defects (44 of 44 "uncovered" were a hidden skip-link, a cursor glow, an aurora background, a modal, and inline styles `document.styleSheets` never exposes). The last two stopped it **certifying** them, which costs more: a direction-blind test passed `index`'s TOP-pinned nav on an ancestor `padding-bottom: … env(safe-area-inset-bottom)` — a hub reservation that does nothing about the notch above; and an ancestor credit passed `public-feed`'s `.header` and `engineering-design`'s sticky tab bar on `body{padding-top:calc(64px + env(safe-area-inset-top,0px))}`, which is wrong twice over — that rule's own comment says it reserves the *wayfinding band* (whose pill carries its own inset at `wayfinding.js:77`), and geometrically `position:fixed` is laid out against the **viewport** so ancestor padding never displaces it, while `position:sticky` is covered at rest and pins to viewport `top:0` the instant the page scrolls. Corrected, the sweep found **3 real defects** against a convention already present at `hive.html:427` / `pm-scheduler.html:316`. Fixing `index` also required its two hardcoded `64px` content offsets (`#ops-home`, the landing hero) to grow by the same inset — **a fix that changes pinned chrome's SIZE invalidates every offset that assumed its old height.** See [[feedback_ancestor_padding_cannot_move_a_viewport_pinned_box]]. |

### A16.2 · CHEAPEN — re-earning costs a command, not a session

| # | mechanism | what it changes |
|---|---|---|
| **C1** | **`evidence.replay`** — every banked row carries the exact command that re-proves it. | A stale row stops being a mystery. `replay: "python tools/prove_order_totality.py --gate"` turns re-earning into running the row's own recipe. |
| **C2** | **The prover tier, and its coverage metric.** An oracle with a prover is **self-healing**; one without is **hand-walked**, and its staleness is permanent debt until someone writes the prover. Report `prover coverage` beside green/stale/owed. | Makes the real health of the bank visible. 500 stale rows with provers is a 6-command chore; 500 without is months. |
| **C3** | **`tools/rewalk_stale.py`** — group stale rows by their `replay`, run each distinct command once, re-bank everything it settles, and list what has no replay. | Converts "501 stale" into "run N commands, then N hand-walks remain." |
| **C4** | **The rule of two.** Re-walk a claim by hand twice and the third time you write its prover instead. | Stops the same measurement being re-derived every session. |

**What a prover is, precisely.** Two tiers now, and the split matters because they fail differently.

*Source/DB tier* — no browser, fast, gateable in CI: `tools/prove_order_totality.py`,
`prove_read_idempotency.py`, `prove_units_at_boundary.py`, `prove_null_semantics.py`,
`prove_write_atomicity.py`, `prove_field_names_survive.py`, `prove_values_survive_the_write.py`,
`prove_http_envelope.py`.

*Browser tier* — a signed-in live page, registered 2026-08-13 through the shared wrapper
`tools/validate_page_ui_provers.py` (one implementation, four gate ids, so a failure names the oracle):
`prove_viewport_overflow.mjs` (CJ widths + `tap_target_44`), `prove_component_states.mjs` (CK stuck
states), `prove_number_labelled.mjs` (CM `what_is_this_number`), `prove_safe_area.mjs` (CJ `safe_area`),
plus `prove_back_out.mjs` (CO `back_out`) and `prove_session_died.mjs` (CO `session_died`). Every one of
these needed a correction its source-tier
siblings could not need — **the browser lies in ways a file does not**: a 1.5× device scale factor
inventing 142 of 398 offenders, a recorder armed 650ms too late, `innerText` returning `''` for visible
controls, a prover measuring the sign-in screen for 18 of 22 pages, and `env(safe-area-inset-*)`
computing to `0px` so "declared" and "absent" are indistinguishable from the computed style. **A browser
prover must assert what it actually landed on and verify its own instrument before it reports a defect.**
Each **re-derives the verdict from scratch**, exits non-zero on a real defect, **SKIPs (exit 0) when its
dependency is unreachable** rather than showing a false red, and **carries a non-vacuity control** so a
pass cannot be free. Every one of the four reported a false alarm on its first run and was corrected
before anything was banked — a prover without a control is decoration, and a prover whose output has
never been checked against the source is an opinion.

**And every one of the four over-reported in the same direction, which is the pattern worth naming.**
`prove_units_at_boundary` flagged 21 columns and meant 7 (`total_tokens` is not money; `min_chars` is not
minutes). `prove_order_totality` called 11 of one page's reads NON-TOTAL because a character window
swallowed the next query's `.limit(`. `prove_read_idempotency` failed a view for advancing its own
`hours_since_generated`. `prove_null_semantics` flagged 23 collapses and meant 9, and reported one as
**live** by testing the first argument of `COALESCE(knowledge, problem, action, '')` when the default is
only reached if all three are NULL. So a fifth prover rule: **a new prover's first run is a DRAFT to be
read against the source, never a result to be banked.** The correction pass is not overhead — on this
evidence it is where roughly two thirds of the initial findings are shown to be false.

### A16.3 · DETECT — staleness stays legible and is never absorbed

- **D1.** Stale is excluded from the denominator, so drift shows instead of being averaged away. *(exists)*
- **D2. Stale needs a CAUSE breakdown, not a count.** "501 stale" is not actionable. "163 mis-anchored ·
  237 expired by 13 page edits · 101 by one `utils.js` edit · 84 have a replay, 417 do not" tells you what
  to do next. Report by (cause, replay-available).
- **D3. A stale ratchet.** Stale may not exceed its high-water mark without an audited reason, mirroring
  the forward-only green ratchet. Otherwise staleness grows silently while green also grows, and both
  numbers look fine.
- **D4. ZERO FAILURES OVER ZERO MEASUREMENTS IS A FAIL, AND IT MUST BE LOUDER THAN A REAL FAILURE.**
  Every prover reports "N failing"; the number that decides whether that means anything is the
  **denominator**, and a prover that does not print its own denominator can pass by measuring nothing.
  *(new 2026-08-13 — `prove_session_died.mjs` proved this on itself within a minute of being written. Its
  text-matching regexes were declared in Node scope but referenced inside the `page.evaluate` callback,
  which runs in the **browser**, so every page threw `ReferenceError` and came back UNGRADED — and the
  summary printed `PASS — no page presents a dead session as signed-in data`, a sentence that was true
  only in the sense that no page had been looked at. The asymmetry is the whole point: a FAILURE gets
  triaged, while a vacuous GREEN gets banked and then defended. So an empty graded set now exits
  non-zero and says so in those words, every UNGRADED page is listed with its reason, and a pass line
  always states how many pages it actually measured.)* Pairs
  [[feedback_a_skipped_partition_reads_as_a_covered_one]] and
  [[feedback_four_exclusions_shrank_the_denominator]].

### A16.4 · GOVERN

- **G1.** A walk with no prover and no `replay` is **debt at birth** — bank it, and record it as
  hand-walked so the debt is counted rather than discovered later.
- **G2. Memento carries the recipes.** Every handoff lists the replay commands and the stale cause
  breakdown, so a new session re-earns without re-deriving. This is the anti-stale half of the Memento
  reflex: the handoff is not a status report, it is the *re-entry procedure*.
- **G3. The momentum refinement.** "A large-but-LOCAL grind is the next unit" applies to stale too — but
  the unit is **run the prover**, or **build the prover**, never **hand-re-walk 40 rows**. A session that
  re-earns 48 rows with one command has done more for the arc than one that hand-walks 6.

**Why this belongs next to the other three disciplines.** Anti-drift keeps a green row honest. The
momentum drive keeps the turn moving. Memento keeps the trajectory across contexts. **Anti-stale keeps
the work from silently un-doing itself** — and it is the only one of the four whose debt accrues without
anybody making a mistake.

---

## §3 · THE ITERATION LOOP (momentum drive)

```
AUTHORING (this arc): per page — transcribe anatomy (A7 receipts) → generate 200 (A8/A10)
   → validate (0 invalid) → next page → arc closes at 22 × 200 authored, all owed
WALK (this arc): pick the lowest-green family across all banks
   → establish the STATE first (persona, view, width) and prove it — a shell reads as a pass
   → verify the INSTRUMENT (A14), then walk the owed rows on the LIVE MCP browser
       → fix every defect it finds, including the siblings the lens did not flag
           → ONLY NOW bank the page's rows (A12: a later edit would stale them)
               → re-run the gate → next family
```

**The per-page order is load-bearing, not stylistic** (A12). Within one page:
`establish state → verify instruments → measure → FIX ALL defects found → re-measure → BANK`.
Banking mid-page and editing afterwards is how 23 rows got re-walked twice in one session.

**A12 COROLLARY — SHARED-FILE EDITS GO FIRST, BEFORE ANY SWEEP.** A page edit expires that page's
rows; an edit to a file in EVERY page's `depends_on` (`utils.js`, `tokens.css`, `components.css`,
`live-state-runner.js`) expires **every page-anchored row on the platform**. So the order within an
arc is: land the shared-file fixes → then sweep the pages → then bank, never a shared edit just
after banking.

> **★ AND THE FIX THAT PROMPTED THIS COROLLARY TURNED OUT NOT TO EXIST — the corollary is what kept
> me from shipping it.** I recorded that "6 of 7 pages set no `aria-busy` despite carrying skeleton
> machinery" and queued a change to the shared `whListSkeleton`/`whCardSkeleton` helpers. **Both
> halves were wrong.** `utils.js:1010` already emits
> `<div class="wh-skeleton" aria-busy="true" aria-live="polite">`, and all 7 pages *do* call the
> shared helpers (1–3 call sites each). My probe read `outerHTML` **at rest** — after the skeleton
> had resolved and been replaced by content, which is precisely what `validate_skeleton_resolves`
> proves happens (8/8 PASS). `aria-busy` exists only *while* the skeleton is mounted; community
> looked like the sole adopter only because its skeleton was still up when I sampled.
> Proven by sampling from the first frame: `aria-busy="true"` with `aria-live="polite"` is live at
> t=439–555ms on inventory, t=138–335ms on pm-scheduler and t=121–206ms on report-sender, and 0 at
> rest on all three. logbook read 0, which is **inconclusive, not negative** — 23 rAF samples across
> 6s against a ~100ms window.
> **The lesson: a state that exists only during a transition cannot be measured at rest, and "absent
> at rest" is not "absent".** Without this corollary holding the edit back I would have "fixed"
> already-correct shared code and staled 256 rows to do it. Check the premise before building the
> pattern — and before touching a shared file, confirm the defect exists *in the state it lives in*.

**Fix the class, not the instance.** Every UI defect found so far has been a shared component
copied per page then diverged — the toast safe-area guard missing on 6 of 8 pages; `an-`/`ah-`/`sb-`
verdict chrome in triplicate; the fill-hue-as-text token misuse on 6 surfaces; `components.css`
linked by only 27 of 49 pages. When the lens flags one, grep the platform and fix every instance in
the same change, then walk them all.

- `.momentum_drive` stays armed; the Stop guard blocks a turn-end while a known unit exists.
- The multi-bank gate runs inside `run_platform_checks.py` (`live_mcp_bank`), so drift appears in
  the normal suite.
- Every session ends by updating **§4 NEXT** and mirroring it into the Memento handoff.

---

## §4 · NEXT

```
STATE 2026-08-06 (gate-computed, never typed — re-run validate_live_mcp_bank.py to refresh):
  PLATFORM 5,277 scenarios · 241 green · 815 stale · 4,221 owed · 0 invalid
    22 page banks  4,400 · 179 green · 0 stale · 4,221 owed ·  4.1% over non-stale
    marketplace      877 ·  62 green · 815 stale ·     0 owed · 100.0% over non-stale
  Board: index 25 | logbook 10 | project-manager 10 | alert-hub/hive/inventory/public-feed 8 |
    achievements/analytics/analytics-report/asset-hub/community/engineering-design/pm-scheduler/
    project-report/report-sender/resume/shift-brain/skillmatrix/voice-journal 7 | assistant 6 |
    dayplanner 5.  By family: F1 arch 1,320 · F2 UFAI 1,100 · F3 UI 990 · F4 UX 990.

DONE 2026-08-06 — THE PROVENANCE SWEEP (all 179 banked rows are now genuinely MCP-earned):
  · 23 rows carried kind:"live-walk" from NODE-LAUNCHED HEADLESS runs, which rule 4 forbids from
    banking. All 23 re-earned through the MCP browser: public-feed 8, index 12, community 1
    (re-anchored to migrations + validate_community_xp_ledger.py), inventory 1 (re-anchored to
    migrations + validate_inventory_ledger_reconciled.py).
  · a further 23 rows expired MID-SWEEP because I fixed defects on pages I had already banked
    (index 18, dayplanner 5) — all re-walked. This is what produced rail A12.
  · every one of the 22 page banks now reads stale 0.
  · index driven 13 -> 25 green: swap_atomic proven frame-by-frame (0 BOTH / 0 NEITHER across 390
    frames), cls_budget 0.0010 over 1 shift entry, identity pinning proven with 3 attacks + a
    restored positive control + DB verification of zero pollution, w390/w641 at VERIFIED widths.
  · anon_zero_rows proven as a BOUNDARY not an emptiness: 13/13 reads return 0 rows to a confirmed
    -anon session while those same 13 relations hold 6,355 rows.

DEFECTS FIXED ALONG THE WALK (Ian, 2026-08-06: "of course you fixed defects along the walk"):
  · index .stat-blue/.stat-orange + the "hive's stage" span: a background-clip:text gradient paints
    its GRADIENT colours, so the darkest stop is the real foreground and the declared color:#fff is
    never painted — which is why a stylesheet read calls it fine. --wh-blue #29B6D9 measured Lc 44.6
    vs floor 45; --wh-blue-text #5FCCE8 -> 56.8. Landing APCA 3 failing -> 0 over 236 measured.
  · dayplanner #logo-view "Day": --wh-orange -> --wh-orange-text, Lc 57.8 -> 69.8 vs floor 60.
  · both used the -text tokens the platform ALREADY shipped for this exact misuse (tokens.css:93-100)
    — the utility class .text-blue-wh was fixed yesterday; these page-local clones never adopted it.

OPEN DEFECTS FOUND, NOT YET FIXED (carry into the next unit):
  · dayplanner: 5 clickAudit MAJORS — click:not-keyboard-operable on #lbc-* divs carrying their own
    onclick with no tabindex (mouse-only). Exposes a denominator trap: focus-visible read 40/0
    because an unfocusable div never enters the focus denominator.
  · dayplanner: axe target-size(3) while the lens reported tapTargetsUnder44 0 — WCAG 2.5.8 counts
    EFFECTIVE size after overlap; the lens checks bounding boxes. The lens needs the overlap rule.
  · dayplanner:814 badge uses color:var(--wh-orange) as TEXT on a tinted chip while its sibling on
    :813 correctly uses --wh-red-text — the 6th instance of the fill-hue-as-text class.
  · index-119: two a.inline-flex links at 161x24 and 267x20, missed by the inline-link exemption.
  · a stale wh_active_hive_id makes get_hive_dashboard return a correct 403 ("caller is not an
    active member of hive <id>") but the page renders an 892-char SILENT SHELL instead of the error.
  · tools/browser_ci_persona_walk.mjs:83-87 HIVES constants no longer match the seed (Lucena is
    4eec150e..., not 3792d7f0...) — that tool would fail the same way I did.

MILESTONE 2026-08-06 — THE V1 WIDTH BLOCK IS COMPLETE ON ALL 22 PAGES (110 rows):
  111 w390 · 112 w641 · 113 w1280 · 114 tap_target_44 · 115 safe_area, every one on a VERIFIED
  width. Widths are always set through the MCP browser in PHYSICAL pixels (dpr 0.667: 390->260,
  641->427, 1280->853) with innerWidth echoed back, because the in-page layout(w) cannot move the
  viewport and honestly reports onTarget false when it has not — readings taken without that check
  are 1280 readings wearing a 390 label.
  Board after: 291 green / 815 stale / 4,171 owed; page banks 229 green, stale 0, 5.2%.

★★ "DECLARED" IS NOT "PAINTED" — the distinction that produced TWO false greens of mine, both
withdrawn 2026-08-06 by self-audit. An UNFILTERED `[aria-busy="true"]` query proves a busy state is
**declared**; it says nothing about whether a loading state is **painted**. I let the word "observed"
carry both meanings and banked `report-sender-127` and `pm-scheduler-127` on "skeleton observed +
CLS 0". Re-measured sampling only frames where the element is VISIBLE:
  report-sender  visFrames 0 of 11 frames in which it exists
  pm-scheduler   visFrames 0 of 37 and 0 of 9 across two cold loads
  skillmatrix    0x0 box inside a section with `hostSectionHidden: true`
All three mount a skeleton that never paints, so they **reserve nothing** — and CLS is 0 by a
different mechanism (the reveal is gated on content existing). `component_skeleton` asks for a
RESERVATION, so CLS 0 plus a declared busy state does not satisfy it.
Both rows were withdrawn by stripping evidence back to `owed` and appending a
`false-green-withdrawn` finding — the audited exception the §5c ratchet allows. The banker's
`ok:false` path only APPENDS a finding and leaves evidence in place, so a wrong green stays green
until the evidence is explicitly removed; that is why the withdrawal is a deliberate, recorded step.
**The contrast:** logbook's skeleton DOES paint — a real 1088x208 box, `visFrames > 0`, CLS 0 across
3 samples — which is what a genuine reservation looks like, and why that row is banked.
Whenever a row's oracle names a user-visible property, the probe must filter for visibility and the
evidence must say which question it answered.

★ CLS IS A DISTRIBUTION, NOT A NUMBER — three "defects" that were single-sample artifacts.
Measuring the skeleton→content transition, one cold load each gave alert-hub **0.6842**,
achievements **0.1761** and dayplanner **0.0962**, all at or over the 0.1 budget. Re-run three times:
  alert-hub    0.6754 / 0 / 0   → 1 of 3 over, median 0 → INTERMITTENT
  achievements 0 / 0 / 0        → CONSISTENT PASS
  dayplanner   0 / 0 / 0        → CONSISTENT PASS
So none is a defect, and filing them would have been three overclaims in one pass. The save came
from my own tooling: `tools/validate_cls_reservations.py` takes TWO samples and fails only if BOTH
exceed, and its comments already record alert-hub at "0.0061 alone, 0.1338 twice" and warn that this
page is "a false lead of exactly the kind this gate exists to stop me" from filing.
**Never quote a CLS figure from a single cold load.** And remember a shift's `sources` name the nodes
that MOVED — the victims — not the element that grew, so even a reproducible reading does not locate
the cause by itself. alert-hub's intermittent 0.675 (victims `div.page` + `details`) is real WHEN it
fires and is worth carrying as a known intermittency at ~1-in-3 cold loads, not as a failure.

TWO NEAR-MISSES THAT BECAME PROCESS, both caught by a denominator that looked wrong:
  · A 1200ms-after-load read on community reported 7 tap targets at 34x44. The SETTLED page has
    none — they are 50x44 with a declared min-height:44px, and 34px was a transient mid-render
    width before the flex row resolved. Filing it would have INVENTED a defect. All batch passes
    now settle 2s after content arrives.
  · A whole 11-page contrast batch silently measured the SIGN-IN LANDING. Signing out for
    public-feed's anon row made every gated page redirect to index.html?signin=1, and the tell was
    11 "different" pages all reporting identical 14449/14551 chars with "Sign Up"/"Sign In" as the
    APCA offenders. Discarded. Every batch now echoes location.pathname to PROVE page identity —
    a dead fixture invents page defects, and it does so confidently.

★ `CM why_refused` NEEDS A BLOCKED ACTION — AN EMPTY STATE IS NOT A REFUSAL (2026-08-06).
The oracle is *"a refusal names the rule AND the way out — never a remedy that cannot work."* Surveyed
six pages for a refusal at rest: **`disabledCount` 0 on all of inventory, pm-scheduler, asset-hub,
alert-hub, achievements and community.** What they have is *empty* states — "OUT OF STOCK 0 / No parts
at zero qty", "ANOMALY SIGNALS 0 / No fused anomalies in your hive right now" — which are informative
but nothing is being refused. Their remedies do exist and are operable and on the 44px floor
(`Add Part` 132x44, `Restock` 103x44, `Open PM Scheduler` 136x44), so the *way out* half would pass;
there is simply no *rule* being enforced to name.
**report-sender is the only surface with a refusal at rest** (`#send-btn` disabled for having no
recipient) — which is why it is the one page where this row banked, and where it found a real defect.
TO CLOSE THE OTHER 20: DRIVE a refusal and read the response. Pick validation refusals that CANNOT
write — submit a required field empty, enter a non-email in the recipient box, request a quantity
above stock — never a path that mutates on success. Inventory's "use more than on hand" is the
highest-value case (it is the stock-conservation rule made visible) but it is a **stock-critical
write** if it succeeds, so drive it only against a rolled-back transaction or a synthetic part.

**WORKED EXAMPLE — inventory-159, banked:** open `#part-modal` via "Add Part", submit "Save Part"
with every field blank. Result: inline **"Part Number required"** (modal text +25 chars), modal held
open with the field editable, **no toast across 242 watched frames** (inline is correct for field
validation — a corner toast that fades is not where a field error belongs), **0 network requests**,
and the DB verified untouched afterwards (81 parts, 0 blank part numbers, newest row 2026-07-20).
Recorded limit: `requiredCount` 0, so validation is JS-side with no HTML `required`, and whether the
message is programmatically associated with the field (`aria-invalid`/`aria-describedby`) is an
accessibility question this row does not settle.

**CHECK THE CONTROL IS VISIBLE BEFORE CONCLUDING ANYTHING FROM CLICKING IT.** Driving logbook's
capture form nearly produced a fabricated defect. `#log-form` is visible (1014x420) and
`#save-entry-btn` is `display:block` and NOT disabled, so a programmatic `.click()` "worked" — and
produced 0 writes, no message and no text change, which reads exactly like a silent no-op click. It is
not: the button measures **0x0**, so no real user can press it in the default TEAM view. Capture lives
in MINE mode; TEAM is a read view. `element.click()` fires on an unclickable element, so a
programmatic click proves nothing about a control a person cannot reach — use it only after asserting
a non-zero box. That is the third time this turn a visibility check prevented a false finding (the
others: three skeletons that never paint, and community's display:none "stuck" skeleton).
Also measured there: the form's own HTML contains the word "required" 5 times while **0** elements
carry the `required` attribute, so requirement is stated in prose and enforced in JS — worth knowing
before asserting anything about native validation on this page.

**DO NOT DRIVE THESE WITH A LABEL REGEX.** A generic opener match failed on all three pages tried:
logbook matched nothing, `/post/` matched **"Load more posts"** instead of the composer, and
dayplanner's "+ Add to my day" opens no modal at all. Nothing was written (0 writes on all three), but
nothing was proven either. Read each page's opener and submit control from the markup — the same
discipline that found `#btn-view-mine` for logbook's skeleton and `skillmatrix.html:670` for its
target grid. A guessed selector that silently matches the wrong control is the quietest way to
produce a confident non-result.

**QUEUED FOLLOW-UP FROM THE `session_died` SWEEP (2026-08-13) — a real question this oracle deliberately
could not answer.** With the auth token removed, `asset-hub` renders **259 characters at +9.4s** and
`shift-brain` **248** — that is not slow, it is effectively blank, with no redirect and no message. The
oracle abstains (UNGRADED) because a single reading cannot distinguish blank-forever from
still-rendering, and inventing the distinction is how three fabricated findings nearly got banked in the
same sweep. **The structure that would settle it:** poll to a fixed point — read every 3s until two
consecutive readings are identical, then grade the settled state. That is a genuine build, not a ceiling,
and it belongs to whoever next drives CO. Two confirmed findings from the same sweep are separate and DO
land: `index` rendering "✓ ALL CLEAR · Nothing urgent right now" beside the real hive name, and
`alert-hub` rendering 10 zeros in the alert inbox — both affirmative claims derived from reads that
failed. See [[feedback_a_zero_that_was_never_a_fallback]].

**SPEC FOR CO `back_out` V2/V3 (44 owed) — the targets are already grounded, and they are THREE tests,
not one.** `page_bank_anatomy/*.json` carries every V2/V3 with a `seen.ref` naming the real element, so
these need no selector guessing — which matters, because the note above records a generic opener regex
matching **"Load more posts"** instead of a composer. 44 views, **24 with a concrete id**, splitting by
what the view actually IS:
- **~17 true modals** (`role=dialog` in the ref): community V2/V3, hive V2/V3, inventory V2/V3, logbook
  V2/V3, pm-scheduler V2/V3, skillmatrix V2/V3, resume V2/V3, index V3 `#signin-modal`, achievements V3
  `#levelup-overlay`, report-sender V3 `#sheet-overlay`. Way out = **Escape closes it AND focus returns to
  the opener** — the exact assertion `tools/arc_u_focus_trap_probe.mjs` already makes for one marketplace
  sheet, so **extend its TARGETS rather than write a third probe** (retrieve-first; it also carries the
  `.open`-class-not-display detail and a working programmatic sign-in).
- **8 tabs** (dayplanner V2/V3, asset-hub V2/V3, engineering-design V2/V3, analytics V2/V3): a tab is not
  an overlay. The way out is the page-level affordance, and the real question is whether it SURVIVES the
  tab switch — which must be re-measured in that view, never inherited from the V1 reading
  ([[feedback_one_reading_banked_for_every_layer]]).
- **~19 data-states** (public-feed error/empty, voice-journal, assistant, project-report,
  project-manager, alert-hub, analytics-report, shift-brain): sections, not views with their own exit. The
  honest disposition for most is `declared-na` **with the reason** under R10 — vacuity recorded, not
  counted — after confirming the page-level affordance is still present in that state.

**WHERE CO `back_out` V2/V3 ACTUALLY STANDS (2026-08-13), measured, with both halves built and gated.**
`tools/prove_modal_escape_adoption.mjs` (gate `co_modal_escape_adoption`) reads the 44 V2/V3 views out of
`page_bank_anatomy`, finds **15 that are real `role=dialog` views**, and reports **0 with no keyboard way
out**. `tools/prove_modal_escape_live.mjs` (gate `co_modal_escape_live`) then drives the behaviour:
**6 of 6 targets pass**, 4 of them with focus-restore assertable. **6 rows banked**, each requiring BOTH
halves — adoption is not behaviour ([[feedback_banner_adoption_is_not_write_refusal]]) and one modal's
behaviour is not another's ([[feedback_one_reading_banked_for_every_layer]]).

**THE FINDING THAT JUSTIFIED THE BEHAVIOUR HALF, and it was a DUPLICATE mechanism, not a missing one.**
`resume`'s `#resume-manager` closed on Escape but left focus on `BODY` with its opener still visible and
focusable. `#resume-manager` is `class="sheet-overlay"`, and **`utils.js:2800-2830` (`whSheetA11y`)
auto-wires every `.sheet-overlay`/`.modal-overlay` through `whModalA11y`** — at load and via a
MutationObserver — while resume *also* kept its own `trapFocus`/`releaseFocusTrap` pair, whose single
global `_lastFocused` slot captured `activeElement` **after** the helper had already moved focus into the
sheet. Both restored on Escape and the page's stale in-sheet element won. Removing the page's duplicate
trap for its two auto-wired sheets fixed it; `#preview-overlay` **keeps** the hand-rolled trap because its
class is `.preview-overlay`, which the wirer never sweeps. See
[[feedback_universal_a11y_shared_component]].

**THAT DISCOVERY CORRECTED THE ADOPTION PICTURE TOO — the class on the element IS the registration.**
Grepping for a page-level `whModalA11y(...)` call reported 4 already-wired dialogs as "hand-rolled".
Truth: **14 of 15 dialogs are on the shared helper** (named directly, via an id array, or auto-wired by
class); the only remaining divergence is **`index` V3 `#signin-modal`**, held at that size by the gate.

**★THE BIGGEST FINDING OF THE ARC SO FAR CAME OUT OF HUNTING AN OPENER: hive's SHIFT HANDOVER FEATURE HAS
NO REACHABLE ENTRY POINT.** `generateHandover()` (`hive.html:5616`) is fully built — it populates
`#handover-body`, the sheet is registered with `whModalA11y` via the id array at `:1565`, and it ships a
provenance chip (`#handover-source-chip`) and a "Handover to (incoming technician)" field. The **only**
control that calls it is `.handover-btn` at `:1417`, which lives inside `#handover-panel` (`:1411`) —
`class="hidden"`. **Repo-wide, `handover-panel` appears at exactly one line: its own declaration.** Nothing
removes the class. Measured live at 390/641/1280: `display:none` at every width, `.hidden` still on, button
height 0 — not a breakpoint, not a collapsed `<details>`, not a persona gate. **Every existing gate misses
this** because nothing throws, nothing logs, no request is made, and axe skips a `display:none` subtree; it
is only visible to a probe that tries to USE the feature and asserts the control it needs is reachable.
**Not auto-fixed** — un-hiding it is one line, but where the entry point belongs is a design decision and a
panel can be parked on purpose. Banked as a finding with the evidence. See
[[feedback_built_but_never_called_and_excluded_errors]].

**ALL 15 DIALOGS ARE NOW ACCOUNTED FOR — 14 driven, 1 recorded as not drivable read-only.** Openers, every
one read from source:

| how it opens | dialogs |
|---|---|
| a clicked element (focus-restore assertable) | `inventory #part-modal ← #btn-add-part` · `resume #resume-manager ← #btn-resumes` · `community #composer-overlay ← #fab-post` · `report-sender #sheet-overlay ← #add-contact-btn` · `community #thread-overlay ← [onclick*="openThread"]` (openers are rendered cards, so the selector is the HANDLER) · `logbook #modal ← [onclick^="openModal("]` (two render paths, `.entry-card` at :3767 and the inline row at :5823 — select on the handler, not the class) |
| a clicked element behind a PRECONDITION | `pm-scheduler #pm-edit-modal ← #btn-edit-asset` (ships `hidden`, revealed by `renderDetail()`; precondition clicks a `.asset-card` — the real path, since `assets` is module-scoped) · `logbook #modal` (precondition clicks `#btn-view-mine`: the default view and Team Feed render **0** openers, My Entries renders 23) |
| the page's own opener function (Escape only) | `skillmatrix #lesson-modal`/`#exam-modal` via its shared `openModal(id)` · `pm-scheduler #completion-sheet ← openSheet()` · `hive #intent-capture` · `achievements #levelup-overlay ← showLevelUpModal(Object.keys(ACHIEVEMENT_DEFS)[0], 2, false)` (a celebration no read-only probe can trigger; real overlay, synthetic trigger) · `index #signin-modal ← openSignIn(null)`, **signed OUT** — `openSignIn` early-returns to the user menu for a signed-in caller (index.html:2917) |
| already open at load | `hive #intent-capture` — a first-run prompt, so there is no open step; Escape-closes is still proven, the open path is not claimed |
| **not drivable read-only, recorded** | `resume #review-sheet` — reachable only via upload → `resume-extract` → checklist, which WRITES `resume_documents` and calls the AI edge function; `openReview()` is module-scoped. Needs a harness that stages a fixture in a rolled-back transaction. **Listed as a target so it stays in the denominator** rather than vanishing from the list. |

**Four rules that came out of driving them.** A state-gated or empty-view opener needs a PRECONDITION, and
its failure is UNGRADED, never a modal defect — "this hive has no PM assets" and "this view lists nothing"
say nothing about Escape. Where the open path is a function call, **focus-restore is not assertable**
(`whModalA11y` restores to whatever was active at open, i.e. `<body>`). Where the opener is a SELECTOR,
every downstream comparison must use selector semantics — `activeElement.id === '[onclick*="openThread"]'`
reported a false failure on a page that had restored focus perfectly. And an opener that is present but
has **no box** deserves an ancestor walk before it is called state-gated: that is what surfaced the hidden
`#handover-panel` above.

**AND THE 11 ARE CHEAPER THAN THEY LOOK — three reveal patterns cover most of them, found by reading the
pages rather than by regex.** `skillmatrix` uses a shared **`openModal(id)` / `closeModal(id)`** helper
(`skillmatrix.html:1253`), so its lesson/exam/result modals need no button at all; `hive` closes with
`classList.add('hidden')` (`hive.html:1431`) and therefore opens with `classList.remove('hidden')`, and
registers all four of its dialogs in one array at `hive.html:1565`; `logbook` ships a real opener id,
`#open-asset-modal-btn` (`logbook.html:488`). **So the live probe should invoke the page's OWN opener
function** — `openModal('lesson-modal')`, `openAddModal()` — which is the genuine code path, instead of
hunting a button per modal.

**One caveat that must be stated on any row this produces, or it over-claims:** `whModalA11y` restores
focus to whatever `document.activeElement` was when the modal opened. Open a modal programmatically and
that is `<body>`, so the focus-restore half becomes vacuous — it "restores" to nothing. **Split the
assertion by what each path can prove:** Escape-closes is provable for every modal via its own opener
function; **focus-returns-to-the-opener is provable only where a real opener element is known** (the four
above, plus `#open-asset-modal-btn`). Asserting focus restore after a programmatic open would be a green
that measures the probe's own starting state — the same vacuity as a control that cannot fail.

### CJ INSIDE THE DIALOGS — the V2/V3 unlock, and its synthesis (2026-08-13)

Resolving the 15 dialog open paths for CO `back_out` unlocked CJ at V2/V3, which had been owed **not
because the oracle was hard but because nobody could open the view.** `tools/prove_dialog_layout.mjs`
(gate `cj_dialog_layout`, sharing `tools/dialog_targets.mjs` with the modal-exit prover so the two cannot
drift) opens each dialog by its own source-read path and measures rooted at the DIALOG element — never
`document.body`, or a sheet overlaying the page would re-measure V1 and bank it as V2. **19 rows banked
green, 3 findings.**

**`overflow` is clean everywhere: 0 unclipped horizontal overflow in all 13 graded dialogs.** Tap targets
pass in 10 of 13. The 3 that fail were measured on the **rule ported verbatim from the V1 prover** — the
first cut omitted four of V1's exclusions and replaced a control's rect with its label instead of unioning
them, and a stricter ruler at V2 than V1 manufactures a difference between views and calls it a defect;
with V1's exact rule the count came back identical, which is what makes these real.

**THE SYNTHESIS — three findings, TWO fixes, and one of them is central:**

1. **A shared chip/pill height, 36px against the platform's own 44px floor.** `inventory` `.asset-tag`
   (30 of 43 targets in `#part-modal`, e.g. `195.9x36`) and `report-sender` `.label-pill` (4 of 8, e.g.
   `59.6x36`) are the same shape in two different dialogs: wide enough, **8px short vertically**. This is
   one token, not two page bugs — raise the chip/pill min-height to 44 and both clear at once. The rest of
   the platform already meets 44 (V1: 750 of 750), so these are components that were never measured
   because they only render inside a dialog.
2. **`index` `#signin-modal` is its own fix and the most consequential**, because it sits on the
   signed-OUT path where a first-time visitor lands: a close button measuring **11.7 × 20** and the
   `#tab-signin` / `#tab-signup` tabs at **40px**. A ~12px close control is hard to hit deliberately and
   trivial to miss on a phone.

**CM is measured by the same prover and DELIBERATELY ABSTAINS per dialog** — its non-vacuity control
FAILS inside a dialog, because a dialog's whole subtree is usually under the 400-char ancestor-text cap, so
the top ancestor "labels" every number beneath it. A bare injected `4242` came back **labelled**. That is
the control doing its job; those CM rows stay **owed** rather than banked free, and CJ still reports
because it is geometric. To settle CM at dialog scope the window needs tightening (≤2 ancestors, a much
smaller text cap) and re-validating against the same control.

### TAB VIEWS — the second V2/V3 shape, and it needed one field, not a second harness (2026-08-13)

Nine of the 22 pages have a V2/V3 that is a **tab**, not an overlay. They fit the same open-then-measure
shape (click the control, root the measurement at the revealed container) so they went into the same shared
table with one new field: **`kind: 'tab'`**. That field is what keeps the provers honest — the modal-exit
prover SKIPS tabs, because a tab panel does not close on Escape and demanding that would report a
fabricated defect on every one, while the layout and a11y provers include them, since overflow, tap
targets, names, focus and motion are all exactly as meaningful in a panel. **6 tab targets added, and the
table is now 21.**

**PRECONDITIONS ARE THE WHOLE DIFFICULTY, and they are read from source like everything else.**
`asset-hub`'s reliability tabs sit behind **two** gates, not one: `#detail-view` is `display:none` until an
asset is opened (`[data-node-id]`, asset-hub.html:1524) **and** `#reliability-card` is a progressive
disclosure behind "Show Reliability Workbench" (`[aria-controls="reliability-card"]`, :674). The first
attempt reported "opener not visible" — true, and not a defect. `dayplanner` is a different shape again: it
renders **all four period views into ONE container** (`#calendar-wrap`, via `render()` at :1066) rather than
swapping panels, so V2 and V3 share a root id and differ only by the active tab.

**THREE FINDINGS, and each is ONE class rather than the raw count — the synthesis is the deliverable:**

1. **`asset-hub` FMEA: RPN values are unlabelled, and their band is colour-only.** Three bare numbers —
   `180`, `168`, `60` — carrying classes `fmea-rpn fmea-rpn-high` / `fmea-rpn-medium`. **This is the page's
   own CI domain-truth #1 failing live**: *"an RPN of 120 means nothing without its bands."* The band exists
   in a CSS class, so it is conveyed by colour alone and is invisible both to a screen reader and to anyone
   who cannot distinguish the hues. Fix: a proximate "RPN" label and the band stated in text.
2. **`dayplanner` week view: 175 under-44 targets = 3 shapes = 2 classes** — `.dp-slot` ×168 at 38.3×56 (a
   24×7 grid) and `.wilo-day-header` ×7 at 39.3×51.4. Both are ~5px under because a 7-column grid at 390px
   leaves ~39px per column after gaps. **Recorded, not fixed:** this is a geometric constraint with an
   equivalent full-width path (the DILO day view), which is a genuine WCAG 2.5.5 exception candidate rather
   than a bug to force. Widening the columns would erase the gaps.
3. **`dayplanner` month view: `.milo-cell` day cells have no accessible name** — 14 instances of ONE class
   whose only content is the day number, so a screen reader announces "1", "2", "3" with no date and no
   month. Same shape as the RPN finding: a bare number with no label.

Also fixed and verified this pass: `pm-scheduler`'s `#pm-edit-modal` close button had **no `aria-label`**
against the platform's own convention (inventory's and hive's both carry one) — a `✕` glyph announcing
nothing. One attribute, verified 6/7 → 7/7.

### THE V2/V3 HARNESS AS IT NOW STANDS (2026-08-13) — 26 targets, three shapes, one table

`tools/dialog_targets.mjs` holds every V2/V3 open path, each read from source, shared by three provers:

| shape | count | how it opens | exit oracle |
|---|---|---|---|
| dialog | 15 | click an element, or the page's own opener fn | Escape closes + focus returns (`co_modal_escape_live`) |
| tab (`kind:'tab'`) | 6 | click the tab, root at its panel | **skipped** — a tab has no Escape; the V1 `back_out` row owns the way out |
| section (`kind:'section'`) | 5 | already rendered (`mayStartOpen`) | **skipped** — same reason |

**22 graded, 4 UNGRADED with their reason recorded rather than dropped:** `resume #review-sheet` (no
read-only path in — needs upload → `resume-extract`, which WRITES; wants a rolled-back-txn harness),
`hive #handover-sheet` (unreachable, the finding above), and `analytics-report` V2/V3 (renders `#ar-empty`
at every period — 30d/90d/180d/365d all probed; `#ar-exec` is emitted from JS at :1171 only once a report
exists).

**A QUESTION THAT DESERVES A LOOK, logged as a question and not a claim:** `analytics.html` rendered **56
non-zero values** on this hive, yet `analytics-report.html` renders its EMPTY state over the same window.
Either the report reads a different source (a generated snapshot rather than the live truth views) or it is
failing quietly. Settling it needs the report's own data path read — it is not a probe limitation.

**STILL TO BRING IN, and each needs one source read, not a new harness:** `project-manager` V2/V3
(`#detail-view` is `display:none` and exposes no `[data-project-id]` / `openProject` opener — find what
opens a project), `alert-hub` V3 (the anomaly panel has no distinct id; `#ah-card-anomaly` is the hero, not
the panel), and the genuine STATE views — `public-feed` V2 error / V3 empty need failure injection at
`window.fetch`, **not** `page.route`, because a warm service worker bypasses route interception. Also
`voice-journal`, `assistant`, `project-report`.

**CK's 226 owed is NOT reachable this way** and that is worth stating plainly: CK rows are keyed by
COMPONENT (`C1`–`C3`), not by view, so the dialog openers do not address them, and 58 of the 66 components
cite a `file:line` rather than an element id. That is a separate, per-component grounding pass.

### WHERE THE V2/V3 HARNESS STOPS, and it is an ANATOMY problem now, not a prover problem (2026-08-13)

The table reached **29 targets** (15 dialogs · 6 tabs · 8 sections) and the remaining views stopped for a
reason worth naming exactly, because it changes what the next unit IS: **they have no stable DOM anchor to
measure.** That is rail **R7** work — *a subject must be OBSERVED, not assumed* — not more prover work.

- **`project-report` V2/V3.** Its anatomy cites an RPC (`get_project_budget`, :319), not an element. The
  budget renders as `.kpi` cards from a template, and the summary block it sits near is
  `document.createElement('div')` at **:489 with no id at all** — created, styled inline, and mounted. There
  is nothing stable to root a measurement at.
- **`assistant` V2/V3.** Already flagged ⚠ in §5a from the start ("panel ids to confirm at Ground"). Its V2
  is the *context bundle* — a data concept (the 7-view grounding read), not a rendered view — so it needs a
  decision about what the row is even asking before it can be measured.
- **`public-feed` V2/V3** are genuine STATE views (error, empty) and need failure injection at
  **`window.fetch`**, not `page.route` — a warm service worker bypasses route interception. That is a
  harness addition, and a known one.

**THE FIX IS BUILDABLE AND SMALL, which is why this is a queued unit and not a ceiling** (the
build-the-structure rule): give those containers **ids**. A dynamically created div with no id is
untestable by construction — every gate that wants to measure it has to guess a selector, and the roadmap
already records what guessing costs (a generic opener regex matching "Load more posts"). One `id` per view
container turns three un-measurable pages into ordinary section targets in the existing table.

**CK's 226 owed is a genuinely different pass** and does not benefit from any of this: CK rows are keyed by
COMPONENT (`C1`–`C3`), not by view, and 58 of the 66 components cite a `file:line` rather than an element
id — so it needs the same id-grounding treatment at component granularity.

### THE V2/V3 TAXONOMY IS COMPLETE — FOUR SHAPES, 34 TARGETS, ONE TABLE (2026-08-13)

| shape | n | how it opens | exit oracle |
|---|---|---|---|
| dialog | 16 | click an element, or the page's own opener fn | Escape closes + focus returns |
| tab | 6 | click the tab, root at its panel | skipped — a tab has no Escape |
| section | 10 | already rendered (`mayStartOpen`) | skipped — same |
| **state** | 2 | **the read is controlled** | skipped — same |

**The STATE shape is the one that needed real machinery, and it is now proven on public-feed.** Its V2 and
V3 are the ERROR and EMPTY states — both real, both distinct, and their conflation is a defect this platform
already shipped and fixed (commit `3ddef99d`: *"pressing Retry answered 'No public posts yet' on a feed with
15 posts"*). Both render into the SAME container (`#feed-list`) — the error through `whListError`
(public-feed.html:306), the empty through an `.empty-state` div (:313) — so the root is shared and the STATE
is what differs.

**The patch is on `window.fetch`, NOT `page.route`**, because a warm service worker serves from cache and
bypasses route interception entirely — that is how an earlier failure-injection probe measured nothing while
reporting success. It is installed with `addInitScript` in a context that is **closed after the target**, so
it cannot leak into a later measurement, and it is non-writing by construction: it only ever makes a READ
fail or return `[]`.

**AND IT VERIFIED THE 3ddef99d FIX RATHER THAN ASSUMING IT.** Driven three ways on the same page:
failing read → *"⚠️ Couldn't load the public feed… **Retry**"* with a real Retry button (1 tap target,
≥44px); empty read → *"No public posts yet…"* with **no** button; untouched read → actual posts. The error
state does **not** say "no posts", and it offers a way forward. That is the invariant the commit fixed,
now measured instead of trusted.

### ★THE TAP-TARGET SYNTHESIS — FOUR PAGES, ONE DECISION (2026-08-13)

Measured inside opened dialogs on the **same ruler that banked 750 of 750 at page level** (the rule is ported
verbatim from `prove_viewport_overflow.mjs`, so these are comparable numbers, not a stricter standard). The
raw counts look like dozens of defects; they are **one design decision** repeated:

| page | control | measured | short by |
|---|---|---|---|
| `inventory` `#part-modal` | `.asset-tag` chips ×30 | 36px tall | **8px** |
| `report-sender` `#sheet-overlay` | `.label-pill` ×4 | 36px tall | **8px** |
| `logbook` `#asset-modal` | `#asset-tab-register` / `#asset-tab-manage` | 35px tall | **9px** |
| `index` `#signin-modal` | `#tab-signin` / `#tab-signup` | 40px tall | **4px** |

**Every one is a chip, pill or tab, and every one is short only on HEIGHT** (widths are fine — 143px, 195px).
The rest of the platform meets 44px, so these are not an oversight everywhere; they are **one convention for
small inline controls** that sits below the floor the same platform enforces elsewhere. Raising the shared
chip/pill/tab min-height to 44 clears all four at once.

**TWO ONE-OFFS ON THE SIGN-IN MODAL WERE FIXED AND VERIFIED, because they were mistakes rather than a
convention** — and that modal is the platform's front door, the signed-OUT surface a first-time visitor
lands on, which is the worst place to have a thumb-sized miss:
- the **close button, 11.7 × 20 → 44 × 44** (`index.html:2696`). It is the *only* control that closes the
  dialog, and inventory's and pm-scheduler's equivalents were already 44 × 44, so this was an outlier, not a
  pattern. The glyph keeps `text-xl`; only the hit area grew.
- the **password-visibility toggles, 30 × 32 → 44 × 44** (both `si-` and `su-`). An icon-only control inside
  a password field is exactly what gets tapped with a thumb. `inline-flex` centring keeps the eye glyph
  exactly where it was.

**What remains on that modal is the convention decision above, not a bug:** `#tab-signin` / `#tab-signup` at
40px (the shared tab height), `#si-sso-btn` at 42px (2px, a padding tweak), and "Forgot password?" at
114.5 × **16.8** — a text link styled `display:inline`, where WCAG 2.5.5's inline exception is arguable and
forcing 44px would visibly change the layout. Left for you.

**And one exception that must NOT be swept into the shared fix, because its cause is different:**
- `dayplanner`'s week grid (`.dp-slot` ×168, `.wilo-day-header` ×7 at ~39px **wide**) — short on WIDTH, not
  height, because 7 columns at 390px leaves ~39px each after gaps. Geometric, with the DILO day view as an
  equivalent full-width path: a real WCAG 2.5.5 exception candidate, not a bug to force.

### ★AN ANATOMY FINDING THAT THE HARNESS SURFACED — TWO "VIEWS" THAT ARE ONE (2026-08-13)

`voice-journal`'s anatomy names **V2 = "entries list"** and **V3 = "review / edit"**. On the live page those
**collapse to the same element**: both are `#history-list`. The entry cards render `.history-entry` /
`.history-text` / `.history-reply` with a per-entry `.speak-btn` (replay) — there is no separate review or
edit surface, no modal, no detail panel, no second container.

Measuring `#history-list` a second time for V3 would bank **the same reading under two rows** — exactly the
[[feedback_one_reading_banked_for_every_layer]] error, and it would have looked like progress. It is refused,
and the row stays owed with this reason attached.

**Under rail R7 this is the anatomy's problem, not the prover's:** *a subject must be OBSERVED, not assumed.*
V3 was assumed to be a view because the page has an edit affordance; the affordance turned out to be a button
inside V2's own list. The fix is to re-ground it — either V3 names a genuinely distinct view, or it is
`declared-na` with this reason under R10.

**Worth generalising: the harness is now also an anatomy CHECKER.** Any anatomy whose V2 and V3 resolve to
one element is mis-grounded by construction, and that is only visible once someone tries to open both. Two
more of the same shape were caught this pass and recorded rather than banked: `project-report` V3 and
`shift-brain` V3's "generate" halves are ACTIONS (an orchestrator invoke), not views, and `assistant` V2 is a
data concept (the context bundle).

**Final table: 43 targets, 35 drivable, 8 recorded-with-reason** — every V2/V3 row across all 22 pages now
either measured or explained by name.

### ★A FINDING WITHDRAWN AT BOTH LEVELS — and the rule that one vocabulary must serve both (2026-08-13)

`session_died` flagged **analytics** as presenting a dead session as data — at V1 *and* again at V2/V3. Both
were **FALSE**, and both are withdrawn. What analytics actually renders once the token is removed:

    #results-panel   →  "Authentication required"
    verdict label    →  "Analytics unavailable"
    #an-summary      →  "Tap Refresh once the engine is ready."

It is arguably the **most explicit page in the roster**, and the oracle recognised none of those phrasings —
not "authentication required", not "unavailable", not "tap Refresh". Its accepted vocabulary was
`sign in|signed out|log in|session expired|…` and `no data|couldn't load|try again|…`, i.e. the wordings its
author happened to think of. **An oracle that only accepts the phrasings it was written with measures the
author, not the product.**

**THE STRUCTURAL LESSON, and it is why this is a rail and not just a fix: the V1 and V2/V3 provers had
SEPARATE COPIES of the vocabulary.** Widening one left the other still failing the same page — the bank would
have held **two contradictory readings of analytics at once**, one green and one red, each with its own
evidence. Both are now aligned, and the alignment is stated in both files so the next widening has to touch
both. This is the same shape as the mirrored `PARENT` map, which is why that one is re-read from
`wayfinding.js` on every run rather than trusted.

**Cheapest possible verification, worth making a habit:** when an oracle reports "the page said nothing",
print what the page actually said. One `innerText` read settled this in seconds, after the finding had already
been banked twice.

**Real `session_died` findings after the correction — three, not four:** `index` (renders "ALL CLEAR ·
Nothing urgent right now" beside the real hive name), `alert-hub` (10 zeros in the **alert inbox** with no
explanation), and `achievements` (weaker: 5 of its 6 surviving values are `.wh-avatar-lvl` tier thresholds,
i.e. static furniture, and the row's own evidence says so).

### ★★CM `why_refused` — ONE MISSING SURFACE ACROSS 15 PAGES → **BUILT, 16/16 PASS**, and the worse bug was genuinely absent all along (2026-08-13)

> **STATUS: FIXED IN THE SAME TURN IT WAS FOUND. 15 failing → 0 failing, 16 of 16 graded pages.** The
> finding below is the reading that *motivated* the fix; the fix and its two instrument corrections are
> recorded in "THE FIX" at the end of this section. Read the two together — the finding alone is now stale
> prose, and a document holding both an un-annotated finding and its fix is the same two-contradictory-
> readings hazard that produced `tools/session_signals.mjs`.

`tools/prove_why_refused.mjs` (gate `cm_why_refused`) answers every read with the body PostgREST actually
sends for an RLS refusal — **403 + `{"code":"42501","message":"permission denied for table"}`** — and asks
whether the page tells the person WHY.

**THE GOOD NEWS FIRST, because it is the more important half: ZERO of 16 graded pages blamed IDENTITY for the
refusal.** That inversion is a bug this platform *has* shipped — a 42501 rendered as *"your session has
expired"*, sending a signed-**in** person to re-authenticate for something authentication cannot fix — and
`utils.js:1607` `whIsAuthFailure()` is why it is now absent: it returns **false for status 403**, commented
*"authenticated, and refused. Not a session problem"*, and documents 42501 as insufficient_privilege. **That
discrimination is holding platform-wide**, which is a real, measured win for a helper that exists precisely
because the bug happened once.

**THE FINDING IS ONE MISSING SURFACE, NOT 15 PAGE BUGS.** Of 16 graded pages: **13 said NOTHING at all**, 2
showed only a generic error (*"Analysis failed, check console"*, *"Achievements failed to load."*), 1 passed.
On `logbook`, `516 entries · 30 machines · 6 open` became `— entries — machines — open` with the body text
**identical to the character** (1107 before and after) and not one word about why. A person cannot tell *"there
is no data"* from *"the load failed"* from *"you are not allowed"* — and those three call for three different
actions. The platform already has a central **write**-failure message and the correct discriminator; the
**read** path has no equivalent. **One adoption, not fifteen edits.** This independently reproduces
[[feedback_fail_401_is_non_adoption_not_a_missing_message]] — *"the message already exists; the gap is
ADOPTION on the read path"* — with a stronger instrument.

**THE INJECTION PROVES ITSELF, because the first version silently did not run.** A regex written inside a
template literal collapsed to one that **terminates at its second character**, so the init script was a
SyntaxError, every read succeeded normally, and the prover reported *"the reads were all refused and the page
said nothing"* — blaming the page for a refusal that never happened. Now every intercepted call increments a
counter (**8–42 per page** on the recorded run) and a zero-hit page is UNGRADED rather than judged. A
silently-inert injection is the vacuous-measurement class: **the probe changed nothing and then judged the
result.** `skillmatrix` is also UNGRADED, because its ordinary copy already matches the refusal vocabulary —
the signal has to APPEAR.

---

#### THE FIX — one function in the shared transport, 15 failing → 0

**Where it went, and why not into 16 pages.** `utils.js` already records the same diagnosis for the **401**
path: the cause was never a missing message but *"118 annotated `catch (_) {}` blocks across 11 pages,
against exactly ONE page that calls `whReadError`"*, and its stated conclusion was **"the fix goes where the
reads already pass, not into 118 catch blocks."** Measured adoption confirmed the identical shape for 403:
`whReadError` is called by **2 sites in `community` and 0 on the other 16 pages** — and `community` is the
one page that passed. So the fix went into `_whNoteAuthFailure`, inside the shared `_timeoutFetch` that
wraps every PostgREST request platform-wide. That function handled 401 and **returned early on 403** one
line in; the early return was *right* about the diagnosis (a 403 must never raise session language) and
*wrong* about the consequence — it said nothing instead of the other true thing. It now raises:

> "Some of this page could not be shown: your account does not have access to it. Your session is fine.
> Ask a supervisor if you need it."

**TWO INSTRUMENT CORRECTIONS, both caught before any product edit.**

1. **The oracle's own vocabulary would have failed the correct fix.** `whReadError`'s 403 sentence matched
   **nothing** in `REFUSAL_SRC`: `no access` does not match "do **not have** access", and
   `contact a supervisor` does not match "**Ask** a supervisor". Adopting the right helper on 16 pages would
   have left all 16 red — and the obvious next move from there is to rewrite the *product's* wording until
   the oracle is happy, i.e. to make the app say the words its oracle's author thought of, which
   `session_signals.mjs`'s own header forbids. Caught by testing the helper's **real output string** against
   the pattern first, then harvesting the missing phrasings from `utils.js`. Re-verified afterwards that the
   three branches still **discriminate**: 403 → refusal only, 401 → signed-out only, connection → neither.
   Containment checked too: only `prove_why_refused.mjs` imports `REFUSAL_SRC`, so the 79 banked CO rows
   could not be retroactively moved. → [[feedback_a_vocabulary_that_rejects_the_real_fix]]
2. **The two notices have different truth conditions.** The transport clears the session notice on the next
   `res.ok`, correctly — a successful read proves the session is alive. A **permission** notice is not
   falsified that way: reading table A says nothing about being refused table B. Had 403 reused the session
   element, a real page (one refused read among twenty good ones) would raise the notice and have it wiped
   milliseconds later, so the person sees nothing — **while this oracle, which refuses *every* read, would
   still report PASS**, because no OK response ever arrives to clear it. A false green manufactured by the
   fix itself, structurally invisible to the test that motivated it. The permission notice therefore has its
   own id, is deliberately excluded from the OK-clear (documented at the clear function), self-expires in
   30s, and is pinned above the session notice so two `position:fixed` boxes cannot cover each other.
   → [[feedback_two_notices_two_truth_conditions]]

**EVIDENCE QUALITY: the quotes were fixed before banking.** The first run's greens quoted page chrome
(*"Retry Live · refreshed on load · Based on your logbook…"*) for a claim about a refusal message, because
the text was split on `/(?<=[.!?])\s+/` and a dashboard's label chrome has no terminal punctuation — so one
enormous pseudo-sentence returned its opening while the match sat ~900 characters later. Six of sixteen
greens would have banked evidence not containing the thing it was evidence for. `pick()` now windows on the
match itself.

**WHAT IT COST, AND THE ROOT CAUSE OF THAT COST.** The one-function fix expired **~670 previously-green
rows** (green 1156 → 485, 31.8% → 16.9%) because `PAGE_DEPS` puts `utils.js` under every page row. R4b
`fn_digests` exists so a shared-library edit expires only claims resting on the function it touched — but
the differing-keys check on a staled `logbook` row reads:

```
recorded keys: 2179 | files: ['logbook.html', 'utils.js']
DIFFERING keys: ['utils.js::_whNoteAuthFailure', 'utils.js::top:917d57bf7457a408']
```

**A row about a layer-contract envelope shape records 2,179 function digests — the entire file, not what the
claim rests on.** That is [[feedback_naming_every_function_is_naming_none]] still live in already-banked
rows: while a row names every function, *any* edit anywhere expires it, and every future central fix costs
~700 greens. The rail is implemented and consulted; what defeats it is the breadth of the recorded set.
Scoping newly-banked digests to the functions a claim actually rests on is the standing improvement.

Second, smaller lesson, measured twice: the top-level digest's **key name embeds its hash**
(`utils.js::top:917d…`), so a top-level edit does not change a value — it makes the recorded key *vanish*,
expiring every row that recorded any top-level digest however narrowly it scoped its functions. Adding one
`var` did it; moving the counter onto `window` did **not** clear it, because the explanatory *comment* was
still outside a function and the top-level digest covers comments too. **On a shared library a purely
documentary edit outside a function is as expensive as a code change.** Prose about a function belongs
inside it.

**A15 broken, and it cost 16 rows.** I banked the 16 greens and *then* made two polish edits to `utils.js`,
which immediately re-staled all 16 — ONE-WAY GREEN says batch every edit *before* walking, and a re-walk is
a loss. Re-earned in the same chain.

**SCOPE, AND THE ONE HUMAN DECISION.** The notice is **page-level, not panel-level**: it names the category
(permission, not identity), states the session is fine, and says who to ask — it does not say *which* panel
was refused, so a page with one refused read says "some of this page". That is what the oracle asks and it
is far better than unexplained dashes, but per-panel attribution is a further improvement, not a claim of
this row. **Ian's call:** a user who *legitimately* lacks access to one panel will now see this notice on
every load of that page, where before they saw dashes. It is true, actionable and self-expiring, but it is a
visible-behaviour change across 16 pages, and "true but repetitive" is a product judgment, not a test result.

### ★★★ CC failure-injection — THE NEW ORACLE'S FIRST RUN FOUND A HOLE IN THE FIX I HAD MADE THAT MORNING (2026-08-14)

`tools/prove_failure_injection.mjs` (gate `cc_failure_injection`) extends
`tests/failure-injection.spec.ts` — which already implements this family properly, but over 7
marketplace-side surfaces — to the **20 product pages it never reaches**.

**WHAT IT FOUND IMMEDIATELY.** The central read-failure notice added that morning hangs off
`.then(res => …)` in the shared transport. **A rejected or aborted fetch never produces a `res`, so the
`.then` is skipped entirely and the notice machinery beside it never ran.** Status-bearing failures
(500/401) were covered; the two failures with no status were not. Measured on `logbook` with every REST
read rejected: **13 failed calls, ZERO page errors, ZERO console errors, and not one word on screen** — the
page caught the rejection and dropped it, which is the *"118 annotated `catch (_) { empty-catch-allow }`
blocks across 11 pages"* habit `utils.js` already documents about itself.

**FIXED WITHOUT VIOLATING THE WRAPPER'S OWN RULE.** That wrapper carries a note: *"a `.catch` here would
swallow the error the client must surface."* Still true — so the fix **notices and RE-THROWS**
(`throw err`), leaving every caller's `{data, error}` exactly as it was. Timeout and offline get
**different sentences**, because "check your connection" is useless advice for one and the only useful
advice for the other. The connection notice **is** cleared by the next successful read (the network is
demonstrably back), while the permission notice deliberately is not — the truth-condition rule from the
morning, applied consistently. Three notices now share **one renderer** at three different `bottom`
offsets, so two landing together cannot cover each other.

After the fix, `logbook` passes all four modes, and `hive` inherits it — which is the point of fixing at
the transport rather than in 118 catch blocks.

#### ★★★ RAW `null` REACHES THE PERSON ON THREE PAGES — and the cluster existed only because a corrupted regex was repaired

With every non-id field returned as null, three pages print the raw value at a human. Two verified
independently by a second targeted probe, not just by the sweep line:

| page | what the person sees | why it matters here |
|---|---|---|
| `inventory` | `OUT OF STOCK **null pcs** Use Restock Find on Marketplace` — **8 occurrences** | the QUANTITY position, on the page a technician reads to decide whether a part is on the shelf or whether they are driving to the store |
| `skillmatrix` | `✓ Growth Primary: **null** · Leandro Marquez` | a person's DISCIPLINE, beside their name, on the surface whose whole job is stating their qualifications — a wrong claim about someone, not a wrong number |
| `alert-hub` | `AMC DAILY BRIEF shift **null** · model amc-v1 **(no headline)**` | the SHIFT the briefing covers — and see below, this line is the most useful of the four |
| `achievements` | `RECENT XP · 🔧 XP earned Wrench Chronicle · **+null**` — **10 occurrences** | note the `+` — the template is fully committed to presenting a GAIN, and the amount is the one part unguarded. Icon, achievement name and plus-sign all survive; only the number a person cares about is missing |

**All four independently re-probed, 4 of 4 confirmed.** The consequences differ and should not be flattened
into "4 pages render null": `inventory` shows a wrong QUANTITY, `skillmatrix` a wrong CLAIM ABOUT A
PERSON'S CREDENTIALS beside their name, `alert-hub` a wrong SHIFT ATTRIBUTION on a supervisor's brief, and
`achievements` a reward that renders as `+null` — the most convincingly-formed of the four, because
everything decorative around it is intact.

**★ `alert-hub` HANDS US THE FIX, AND THE SOURCE CONFIRMS IT EXACTLY.**
[alert-hub.html:611](alert-hub.html#L611):

```js
meta.textContent = `shift ${brief.shift_date} · model ${brief.model_version || 'amc-v1'}`;
```

`model_version` carries a fallback. `shift_date`, **in the same template literal**, does not — and
[:627](alert-hub.html#L627) uses `String(b.headline || '(no headline)')` a few lines later. The idiom is
present, applied to two neighbours and skipped on the third. That is not a missing pattern anyone has to
design; it is a **one-token omission**, and the rendered line proves it by printing the fallback and the
raw null side by side.

**AND ALL THREE PAGES SHOW THE IDENTICAL SHAPE — a guard on one interpolation, none on its neighbour in the
SAME template literal:**

```js
alert-hub:611    `shift ${brief.shift_date} · model ${brief.model_version || 'amc-v1'}`
skillmatrix:854  `Primary: ${_profile.primary_skill} · ${WORKER_NAME}`
inventory:1118   <span …>${escHtml(item.unit || 'pcs')}</span>
inventory:1542   `Available: ${item.qty_on_hand} ${item.unit || 'pcs'}`
```

**★ AND INVENTORY GETS IT EXACTLY BACKWARDS.** The fallback protects `item.unit` — and the bare
interpolation is `item.qty_on_hand`. A missing UNIT is cosmetic ("3" instead of "3 pcs"); a missing
QUANTITY is the number a technician acts on. The page guards the decoration and leaves the decision
unguarded, which is how it renders `null pcs`: unit fell back, quantity did not.

So this is ONE finding with one habit behind it — a `|| fallback` reached for while writing the
low-stakes half of a line and forgotten on the high-stakes half. Three one-token corrections, not a design
decision. Cheap to close and now cheap to keep closed: `cc_failure_injection` fails on it, so a regression
cannot return silently.

**★ THIS WAS INVISIBLE AN HOUR EARLIER.** `fail_null_field`'s detector had been written through nested
quoting layers and its intended `\b` had become a literal BACKSPACE byte:

```js
const raw = /<BS>(null|undefined)<BS>/i.exec(txt)     // matches a control char beside the word: never fires
```

So the oracle reported *"no raw null/undefined/NaN reached the screen"* on **every page**, while checking
nothing. `node --check` passed. The byte does not render in an editor. The output was a clean sweep of
greens.

That is the precise cost of a false green, stated concretely: the row would not merely have MISSED this —
it would have **asserted the opposite**, banking "no raw null reached the screen" about a page rendering
`null pcs` eight times, and nobody would have looked again. A false red gets argued with; a false green
gets believed. `tools/validate_page_ui_provers.py` now refuses to run ANY prover whose source contains
control bytes, verified in both directions on a different prover than the one that had the bug.

#### ★★ `fail_slow` FAILS ON NEARLY EVERY PAGE — AND IT IS **NOT** ONE SHARED FIX

At 73 of 140 cells, `fail_slow` had failed on **every page walked except `index`** — hive, logbook,
inventory, pm-scheduler, project-manager, dayplanner, asset-hub. The obvious synthesis is "one missing
loading-state contract, one fix." **That synthesis is wrong**, and measuring the boot pattern is what
refutes it:

| page | skeleton calls | awaits `validateHiveMembership` | cause |
|---|---|---|---|
| `hive` | 3 | 0 | skeleton gated behind `await db.rpc('get_hive_board_dashboard')` |
| `inventory` | 1 | 1 (+ `getUser`) | skeleton gated behind `await validateHiveMembership()` |
| `pm-scheduler` | **0** | 1 | **no skeleton exists at all** — nothing to be late |
| `logbook` | 3 | 1 | **deliberate suppression**, documented fix (would reintroduce a stuck shimmer) |

**At least three distinct causes wearing one symptom** — a late affordance, a suppressed-on-purpose one,
and (as first read) an absent one. A single "add a skeleton" or "hoist the skeleton" change would be wrong
on more than one of them, and would actively regress `logbook`.

#### ★ THE FINAL `fail_slow` PICTURE — 7 held, and NONE of them is "no loading state"

The completed sweep holds 7 `fail_slow` failures. Checking whether each page even HAS an affordance
(searching html **and** its sibling js for skeleton / shimmer / spinner / aria-busy / `id="…loading"`):

| page | loading markers present | disposition |
|---|---|---|
| `logbook` | 3 (whListSkeleton) | **DELIBERATE** — the 2026-08-05 fix; banking it would restore a permanent shimmer |
| `hive` | 3 | **REAL** — skeleton gated behind `await db.rpc('get_hive_board_dashboard')` |
| `hive` | — | **REAL** — skeleton gated behind the board RPC |
| `report-sender` | 5 | **REAL → FIXED** — pending rendered as empty |
| `resume` | 6 | **REAL → FIXED** — no affordance at all, plus empty-vs-error |
| `project-report` | 3 | **FALSE RED → instrument fixed** — walked without `?project_id=` |
| `assistant` | 4 | **FALSE RED → instrument fixed** — detector didn't know "typing indicator" |
| `logbook` | — | **REAL → FIXED** — *(I first called this "deliberate"; that was wrong — see below)* |
| `analytics-report` | 6 | **NOT A DEFECT** — affordance scoped to the long operation |
| `engineering-design` | 11 | **`declared-na`** — nothing in the calculator view waits on a read |

### I MIS-TRIAGED `logbook`, and the correction is the most useful thing in this section

I recorded `logbook fail_slow` as **"deliberate suppression, NOT a defect"** and published that twice —
on the strength of a comment in the banker citing a real 2026-08-05 repair (team mode used to show a
permanent shimmer at 14s). Reading the code instead of the comment:

```js
if (_viewMode !== 'team' && _elList && !_elList.childElementCount && …) whListSkeleton(_elList, 4);  // :1941
let _viewMode = 'mine';                                                                              // :1529
```

**The deliberate suppression covers `team` mode. The walked view is `mine`, where the skeleton is
supposed to paint.** So the repair was real and my citation of it was not: it exonerated a different
view from the one failing. Measured under a 6s delay: **zero skeletons and an empty `#entries-list` at
1.2s, 2.4s, 3.6s and 4.8s.**

The actual cause was the `hive` defect exactly — `loadEntries()` owns the skeleton and is not called
until `restoreIdentityFromSession()` **and** `validateHiveMembership()` have both settled. Two blocking
reads in front of the affordance. Fixed with the same synchronous pre-await interstitial; now 12 busy
indicators mid-flight, 7 of 7, and nothing stranded on a healthy load.

**Quoting a comment is not reading the code** — and a plausible exoneration is exactly as dangerous as a
plausible finding, because nobody re-checks a cell already marked "not a defect".

**THE FULL TRIAGE: of eight `fail_slow` candidates, FOUR were genuine** (hive, report-sender, resume,
logbook). Two were my own instrument
lying (once about the URL, once about vocabulary), two were deliberate design, one was inapplicable.
Banking this family on sight would have filed five wrong findings — and each wrong one asks someone to
undo careful work. `engineering-design` was settled by stalling every read for 20s and diffing: the view
rendered **byte-identical** (1845 chars both ways), so nothing there waits on a read and a busy indicator
would have nothing to describe. `assistant` and `resume` were separated by the same probe —
both DIFFERED, so both genuinely wait; only one of them said so.

**`analytics-report` triaged — the affordance is deliberately scoped to the wait that matters.** Its
spinner ([:725](analytics-report.html#L725)) belongs to the GENERATE action, not the initial load —
`genBtn.disabled = true` sits two lines above it — and the comment beside it records real measurement:

> *"the spinner was VISUAL ONLY, and this is the longest wait on the page. Measured live, the orchestrator
> returned in 4.1s on one run and 32.6s on another, so a screen-reader user was left with no announcement
> that anything was happening for up to half a minute… aria-busy says the region is working; aria-live=
> polite delivers the result."*

The page put its affordance — with `role=status`, `aria-busy` and `aria-live` — on the operation that
genuinely takes 5–15s, and left the small initial read bare. Under an artificial 6s delay on that read the
oracle sees nothing; in reality that read is fast. **Scoping judgement, not a defect.**

**So of the three `fail_slow` rows triaged so far, TWO ARE NOT DEFECTS** (`logbook` deliberate,
`analytics-report` scoped by design) **and one is real** (`hive`). That ratio is the argument for the hold
rule in a single line: banking this family on sight would have been wrong about two thirds of it.

### `report-sender` — REAL, and sharper than the verdict said (FIXED)

The verdict was "no busy indicator". The truth was worse: the page filled the wait with a **confident wrong
answer**. Its three `Loading...` placeholders ([:565](report-sender.html#L565), [:577](report-sender.html#L577))
are replaced within 2.5s — not by data, but by the summary card rendering from an empty variable:

| instant | `rs-contacts-hero` | `rs-contacts-sub` | tag |
|---|---|---|---|
| 2.5s, read in flight | `0` | **No contacts saved yet, add one above** | START |
| 9.5s, 3 rows landed | `3` | 3 reusable contacts on this hive | LIST |

**The page overturned its own claim, which is the proof it never held it.** A past session already fixed this
exact card for the FAILED read — the comment at [:991-995](report-sender.html#L991-L995) records measuring
"Saved contacts 0 · No contacts saved yet" under an injected 500 — and taught it "none" vs "could not find
out". It left a third case answering as the first: **not known YET.** `_contacts` is `[]` and `_rsReadFailed`
is `false` while the read is still in flight, so the empty branch wins.

Fixed with a third state (`_rsContactsSettled`), settled in a **`finally`** at the call site so a throw cannot
leave it stuck saying "Checking…" forever — trading a wrong answer for a permanent one is not a fix, and a
stuck pending state is invisible to every gate. Verified in all three: healthy → `0 · START` (this hive truly
has none), 500 → `— · UNKNOWN`, rejection → `— · UNKNOWN`, none stuck.

**Proven without writing a row.** This hive has 0 contacts, so the claim was *accidentally true* and could not
be falsified with real data. Rather than seed a contact into a shared DB, the probe returned three contacts
**late** — same read, delayed 6s. The contradiction is manufactured entirely in the response, and the DB is
untouched.

### `project-report` — a FALSE RED, and the instrument was walking the wrong URL

[project-report.html:344-348](project-report.html#L344-L348) returns early unless the URL carries
`?project_id=`, so `loadAndRender()` never runs — and neither does the skeleton the page ships for exactly
this case ([:353](project-report.html#L353): *"canonical skeleton in the summary section while the 4 project
queries run"*). Same page, same oracle, two URLs:

| walk | hits | `#tb-title` | busy indicators @2.5s |
|---|---|---|---|
| bare (what the bank walked) | 5 | "No project specified" | **0** ← the verdict came from here |
| `?project_id=853abed7…` | 9 | "Loading project…" | **5** (`wh-skeleton`, `wh-skeleton-row`…) |

**A paramless walk is not a failed walk — it is a walk of a DIFFERENT PAGE**, which is why nothing caught it:
the shell is signed in, 200 OK, has chrome and text, and throws no error. It simply is not the surface the row
claims to be about.

**Ten provers navigate `project-report.html` bare** — only `live_page_journeys.registry.mjs` passes the id.
Fixed centrally in **`tools/page_query.mjs`**: a page that needs a parameter gets one resolved LIVE, and a page
whose parameter cannot be resolved is **UNGRADED**, never walked bare. Two bugs found while building it, both
of the silent kind:

- **Multi-line SQL through `execSync` on Windows** — `cmd.exe` ends the command at the newline, so the join ran
  unbounded and returned a 90-line blob that would have been pasted straight into `?project_id=`. A URL
  resolving to no project is the empty shell again, with a plausible id on the front. Now one-lined, and any
  answer that is not exactly one uuid returns nothing.
- **`WH_TEST_HIVE` is stale again.** It defaults to `636cf7e8`, described in
  [live_page_journeys.mjs:62-66](tools/live_page_journeys.mjs#L62-L66) as "the real Baguio Textile Mills hive
  both accounts belong to". Measured: this account's only membership is **`084c113b`** (Baguio Textile Mills,
  4 projects); `636cf7e8` holds none of its rows. **That comment was itself written to fix a stale hive
  constant** — same drift, one hive later, failing the same silent way (RLS 0 rows → empty page → walk grades
  an empty page as the page). `page_query.mjs` resolves the hive from `hive_members` instead: an id in a config
  file cannot notice it went stale; a membership query cannot go stale.

> **★ OPEN, AND NOT SMALL: `project-report` holds 88 green rows whose evidence refs record only a date and a
> URL with no query string, so I cannot tell from the bank which were earned bare.** The rows are not being
> mass-withdrawn on suspicion — that would be a re-baseline, and R5 forbids it. They are queued for **re-walk
> under the corrected URL**, which settles each one on its own evidence: a row that passes parameterised was
> right regardless of how it was earned. Same question applies to any other parameterised surface, and the
> `WH_TEST_HIVE` default reaches far past this page.

**AND THE FALSE GREEN IS NO LONGER HYPOTHETICAL — the corrected walk found one immediately.** Bare,
`fail_null_field` passed with *"no raw null reached the person"*. It could not see a null because the page
rendered nothing at all. Walked correctly, the same cell FAILED with 13 row-sets, and the executive hero read:

> **HERO FINDING — `null is 0% complete: 10 scope items defined, 0 done.`**

`project_code` was interpolated **bare in eight places** — document title, toolbar title, cover code, the
assistant's grounding lines and all five hero branches — while `estimated_hours`, `actual_hours` and the
blocker counts on the lines directly above carried `|| 0`. **The fallback guards the arithmetic and skips
the identifier**, the same habit as inventory's `null pcs`, alert-hub's `shift null` and skillmatrix's
`Primary: null` — but on a document someone prints and signs, where a reader cannot ask a PDF which project
it describes. Fixed with two fallbacks (`projField` for form fields, `projLabel` for sentences), all eight
sites routed through them. **project-report is now 7 of 7 green.**

### ONE `return` MEANING TWO OPPOSITE THINGS — found FOUR times in one turn

The single most repeated defect in this family, in four different files, always the same line shape:

| file | the line | what collapsed |
|---|---|---|
| [resume.html:743](resume.html#L743) | `if (error \|\| !data \|\| !data.doc) return false` | failed read → "you have no resume" → **first-timer onboarding** |
| [index.html:4336](index.html#L4336) | `res.status === 'fulfilled' ? res.value.data : null` | failed signal → absent signal → **"All clear · Nothing urgent right now"** |
| [analytics.html:1078](analytics.html#L1078) | `if (error \|\| !data) return []` | failed snapshot → "no snapshot" → **silent loss of the AI recommendation** |
| [report-sender.html:996](report-sender.html#L996) | `_contacts.length` with no pending flag | pending → empty → **"No contacts saved yet"** |

**`Promise.allSettled` protects against a THROW and says nothing about an error INSIDE a settled
value** — PostgREST resolves a 500 as `fulfilled` carrying `{data: null, error}`, which is exactly how
index's whole approval card disappeared. The caller cannot make a correct decision because the
information was destroyed one line earlier, so the empty state is not a wrong branch: **it is the only
branch available.**

The direction of each failure is the same and it is the dangerous one — every collapse resolves toward
**reassurance**: nothing to approve, nothing saved, nothing urgent, everything current.

### `hive` — the wait state was painted THREE levels downstream of the wait

The busiest board in the roster showed **121 chars of nav chrome and zero busy indicators** while it
booted, with `#feed` invisible and empty at 4s. It took three attempts to place the fix, and each wrong
placement is the same mistake at a different depth:

1. Inside `loadFeed()` — where a skeleton already existed at [:3816](hive.html#L3816). But `loadFeed`
   does not run until the board RPC resolves, and that RPC *is* the wait.
2. Before the board RPC — but every route first awaits the **membership re-validation**.
3. Before that — but the genuine first blocking read is `restoreIdentityFromSession()`, which queries
   `worker_profiles` and gates every branch the page can take.

**A wait state placed after ANY await only appears once that await is over.** So it is now synchronous,
at the top of `initHive()`, before a single `await` exists to hide behind — and it claims *nothing* about
membership, hive or role, since those are the questions still being asked. `showView()` clears it,
whichever route wins.

Two further silent failures while landing it, both hidden by the same kind of defensive guard:

- The inline script runs **during parse**, before its host element is parsed, so `if (!host) return`
  did nothing on every load — the interstitial never appeared even healthy. Now it paints at
  `DOMContentLoaded` when the host is not yet there.
- I first targeted `#wh-main-content`, the id visible in the DOM at runtime. **That string appears
  nowhere in `hive.html`** — a shared script stamps it onto `<main>` for the skip-link. `getElementById`
  returned null forever, silently. Targeting `main` by tag fixed it.

`hive` is now 7 of 7, and the interstitial does not linger on a healthy load.

### `Number(null)` is `0`, and it broke my own fix

The first null-guard I wrote was `Number.isFinite(Number(v))`. **`Number(null)` is `0`**, so
`isFinite` returns true and the null sailed through — the page still printed "OUT OF STOCK null pcs".
Only `undefined` coerces to `NaN`. Worse, the same mistake inside `stockStatus()` sent a null quantity
down the `q <= 0` branch and labelled the part **OUT OF STOCK** — a confident wrong answer where a blank
had been. Caught only by re-running the injector after the "fix"; the guard now rejects
`null`/`undefined`/`''` explicitly before any coercion.

### Three cells settled as `declared-na` by measurement, not by argument

`engineering-design` and `analytics-report` render **byte-identical text** under a 500 and under a 20s
stall (1845/1845 and 369/369). Nothing in their default view comes from those reads — the calculator is
client-side, and analytics-report's body waits behind Generate. Demanding a failure message there would
demand noise about data the view never shows. **This is R10 working: `declared-na` WITH a measured
reason, never a green over an empty denominator.**

## CC failure-injection — CLOSED at 140 of 140 graded

Final sweep on a verified-healthy stack: **140 of 140 cells graded, 6 failing** — and all six are the
`declared-na` cells already dispositioned by measurement (engineering-design ×3, analytics-report ×3,
each rendering byte-identical under a 500 and a 20s stall). **Banked: 84 green, 0 findings.**

Started this arc at **23 failing**. Twelve product defects fixed, two instrument defects fixed, one gate
that could never have passed given a budget it could survive.

**The bank moved 590 → 482 green with stale 1641 → 1763, and that is not a regression** — it is R4 doing
its job. Ten product files changed, so every row anchored to them expired. Those rows are re-earnable by
re-running their own gated provers; the defects they used to sit beside are gone for good. A15's
one-way-green rule is what makes the trade legible rather than alarming.

## CC V2 — opened, and the scoping is the whole reason it counts

154 CC rows sit on the V2 view and had never been walked. Extending the prover was mechanically easy;
making the result **mean** anything required one decision:

**`READ` now scopes its text AND its element queries to the target region** (`#<modal>.innerText`,
`scope.querySelectorAll(...)`). Read against `document.body`, a page-level failure notice elsewhere on
screen would satisfy every V2 claim for free, and all 154 rows would silently inherit V1's verdicts.
**This platform has already banked 14 V2 rows carrying V1's reading**, by selecting rows on the oracle
name alone — so this is a defect with a receipt, not a hypothetical.

**Proof the scoping discriminates, from the first page walked.** `inventory` **PASSES** `fail_timeout`
and `fail_offline` at V1 and **FAILS both at V2**: the page-level transport notice exists, and the part
modal still says nothing inside itself. Same page, same mode, two different answers — which is what a
second view is for. Its evidence quotes text from *inside* the modal (`ASSETS (which machines use this
part)`), not from the body.

### AND THE LAST 6 WERE THE ORACLE SAMPLING ITS OWN LATENCY

With the design-aware rule in place the V2 sweep read **86 graded · 80 pass · 6 failing**, and all six
were `fail_slow` — held for triage rather than banked. Triaging them found the instrument again.

The V2 path spends **3.5s settling, opens the view, then samples 2.5s later** — ~6.2s in, which is
exactly when a **6s**-delayed read resolves. Measured on `report-sender` → `#contacts-list`: **four
VISIBLE skeleton rows from ~1s to ~6s, and none at 6.2s.** The region had shown its wait state for five
seconds; the prover arrived just after it ended and called the page silent. **Six false findings sat
behind one arithmetic slip.**

**The tell was a fix that did not take.** I added the skeleton, watched it render, and the cell still
failed — so the disagreement was between two measurements, not between the page and the truth. A
timeline sample (1s / 2.5s / 4s / 9s) settled it in one run. V2 slow mode now injects **14s** so the
sample lands inside the wait; shortening the settle would have traded one timing bug for another.

**A config edit must land BEFORE the thing it configures.** My first attempt overrode `mode.delay`
*after* `addInitScript(inject(mode))` had already serialised the script — it mutated a local and changed
nothing. An edit placed after its consumer is indistinguishable from no edit, and reads as "the fix
didn't work".

**Two half-fixes corrected in the same pass.** `report-sender`'s summary card was taught to say
"Checking your saved contacts…" earlier in this turn while `#contacts-list` — the thing a person reads
to see who a report will reach — stayed empty until its read settled. One element told the truth while
its neighbour, describing the same fact, said nothing.

**And a BRITTLE VALIDATOR was repaired rather than worked around.** `validate_report_sender.py` checked
hive scoping with `page[page.find("report_contacts"):][:500]`. The first match is the localStorage key
`wh_report_contacts`, so an eleven-line comment pushed the real `.eq('hive_id', HIVE_ID)` past the
window and turned a green check red with *"contacts leak across hives"* — about a page whose scoping had
not changed. It now locates every real `.from('report_contacts')` query and requires each to be scoped
within its own statement: **36/36 PASS**, and immune to how much prose sits nearby. A validator a
comment can break was never measuring the property.

### ★ 43 OF THOSE FAILURES CONTRADICTED A DECISION ALREADY ON THE RECORD

With the page-vs-region distinction added, the 49 resolved into **43 "the region was silent, the PAGE
said it"**, 6 `fail_slow`, and **zero cases where a failed read went completely unannounced**. Then the
check that mattered: **§ above, written 2026-08-14, already settled this.**

> **SCOPE, AND THE ONE HUMAN DECISION.** The notice is **page-level, not panel-level** … it does not say
> *which* panel was refused … **per-panel attribution is a further improvement, not a claim of this row.**

So 43 cells were about to be banked as defects **for doing exactly what a prior decision chose to do**.
That is the mirror of quoting a comment instead of reading the code — ignoring a *documented* decision
rather than an undocumented one — and it would have been the largest false finding set in this arc.

**The oracle was too broad, not the platform.** What this family actually asks is narrower and sharper:
does the block render a **FALSE EMPTINESS** while its read failed? *"No contacts saved yet"* over a
failed read is a lie the person acts on. A **blank** block beside a page notice saying the read failed is
not — they have been told, and nothing false is on screen. The V2 rule is now exactly that, and
`alert-hub` went from **6 failing to 1** (its remaining `fail_slow` is held for triage like every other
absence-asserting mode).

**The general lesson, and it is about me rather than the code: before banking a large finding set, search
the roadmap for a decision that already covers it.** A number as big as 43 is itself the signal — a
platform does not usually get one thing wrong forty-three times; more often the instrument is asking for
something the team already considered and declined.

### The first V2 sweep returned 49 failures of 84 graded — and that number was the finding

An impossibly BAD result deserves the same suspicion as an impossibly good one. Two were unambiguous
(below). Most said *"the region said NOTHING"* — and I had not measured the thing that decides whether
that is a defect: **did the PAGE say it somewhere else?** A block that stays silent while a page-level
notice explains is a real but much smaller defect than one where nobody tells the person anything.

The prover now reads BOTH at V2 and writes the distinction into the verdict:

> `17 call(s) failed. THIS VIEW said nothing (120 chars), but the PAGE did: "…". The person is told —
> just not in the block whose data went missing.`

Banking 49 cells as "the failure was silent" would have manufactured findings at scale, which is exactly
what this family's hold rule exists to prevent.

**A bug of mine was hiding inside that run, too.** `dialog_targets`' `pre` field is a STRING of page JS,
not a function — my driver called `t.pre(page)`, the TypeError was caught by its own try/catch, and
`logbook`, `asset-hub` and `project-manager` came back **UNGRADED**. That read as a reachability limit of
the product when it was a coding error in the instrument. **A guard that converts my bug into a tidy
"not reachable" verdict is the most expensive kind, because it reads as a fact about the page.**

### TWO STUCK SKELETONS — defects 14 and 15, and the same root

Both pages handle a **resolved** `{ data, error }` carefully and neither survived a **rejection**:

| page | what happened |
|---|---|
| `voice-journal` | `loadHistory()` clears the skeleton and says "Could not load your journal" — but only on a resolved error. Offline/timeout REJECT, `await` throws, the function exits, and **3 skeleton rows shimmer forever**. |
| `project-report` | `Promise.all` rejects, so the careful four-way branch below it (401 vs 42501 vs fault vs deletion) never runs and **4 skeletons shimmer** on a page whose purpose is to be read and signed. |

**A stuck skeleton is invisible to every gate** — no error reaches the console, nothing throws at the top
level, the promise settles — and it is worse than an error message, because it tells the person to keep
waiting for something that is never coming.

Fixed: `voice-journal` catches the throw into the same `error` variable its resolved branch already
reads; `project-report` switches to `Promise.allSettled` and normalises a rejection back into
`{ data, error }` so it lands in the **existing** four-way branch rather than a fifth path that would
drift from it. Verified: both regions now render 0 chars instead of shimmering, and healthy loads are
unchanged (`voice-journal` 2684 chars; `project-report` 4102 with CAP-2026-001 loaded, 0 leftover
skeletons, no page errors).

**Reachability is recorded, never assumed.** The open paths come from the shared `dialog_targets`
registry, whose entries were read from source rather than matched by label. **17 of 22 targets are
drivable**; the other five carry their reason — `resume` / `analytics-report` / `assistant` have no
read-only path in, `hive`'s control is verified unreachable, `index`'s exists only signed-out. Each banks
**UNGRADED with that reason** rather than vanishing, because a shrinking denominator reads as "all
graded" on the board while covering less. The eight `kind: 'section'` targets (analytics' exec summary,
alert-hub's AMC card, report-sender's contacts list…) need no open step at all — they are regions already
on the loaded page — but they are still read *inside their own element*.

## CI domain-truth — the family at ZERO is open, and the platform reads well

`CI` was the only family with **0 green against 176 owed** — 8 hand-authored engineering claims per page,
never walked. It is also the family where a keyword oracle is most dangerous: a domain-truth check is a
keyword check wearing a lab coat, and this arc has already produced **five** wrong verdicts from patterns
written at the desk. So `tools/prove_domain_truth.mjs` was authored **only from harvested live text**,
records the exact string it matched in `saw`, and ships a `--selftest` that plants both a satisfying and
a violating text per check.

**The self-test immediately earned its keep.** `inventory/CI2`'s subject-gate (`reorder|restock|order
them`) did not match the page's own "Order 3 low parts →", so a real reorder suggestion would have scored
**ungraded** rather than judged — the failure that shrinks a denominator instead of reporting a gap. It
now reads `order (them|\d+)`, and all four planted cases discriminate.

**TWO DISCIPLINES TURNED FOUR OF MY OWN GREENS INTO HONEST VERDICTS**, before a single row was banked:

1. **The check must be the ROW'S oracle, not a weaker cousin.** Row 108 asks for the period *and*
   whether it is rolling or calendar; row 110 for the RULE behind the verdict, not merely a basis
   affordance; row 105 for ISO 14224 *and* agreement with logbook and hive to the same decimal. My
   first drafts tested the easy half of each. Banking those would assert properties the walk never
   examined — and row 105 now returns **UNGRADED** rather than green, because its cross-surface half
   needs three pages read together and this walk reads one.
2. **A qualifier must sit NEAR the figure it qualifies.** The trend check accepted
   *"calendar days between failures"* — MTBF's basis, from a different card — as proof the trend window
   was calendar-based. The words were on the page; the claim was not. A `near(anchor, target, span)`
   helper now scopes each qualifier to its own figure.

**Both false greens became real findings under scoping**, which is the whole argument for it.

**THE ANCHOR ITSELF NEEDED FIXING TWICE MORE, in both directions:**

- **A false RED.** `near()` anchored on the FIRST match, so `skillmatrix`'s "TOTAL BADGES 19 · 19 of 25
  possible (5 levels × 5 disciplines)" — the denominator *and* its formula — failed, because the first
  `/badges/` on the page is the source chip's "Based on your skills & skill badges", 900 chars earlier.
  Now it scans every anchor occurrence and returns the first window that actually contains the target.
- **A false GREEN, twice.** With all anchors scanned, `pm-scheduler` CI1 matched **"0 of 30"** — an
  *asset* count one clause earlier — as the compliance denominator, and `analytics` CI6 matched
  "calendar days" (MTBF's basis) as the trend's window type. On a page dense with `N of M` figures,
  proximity is not enough: where the page prints a claim in a fixed phrase, match the **phrase**
  (`114 of 409 ran late`), and drop ambiguous vocabulary (`calendar day` is not `calendar month`).

**Every green below was then audited against its own `saw` string** — the evidence field exists exactly
so a verdict can be checked without re-running it.

**Results — 14 stated, 3 missing, 1 ungraded across 18 cells:**

| page | result |
|---|---|
| `analytics` | 3 stated, 2 missing, 1 ungraded. **States** `ISO 22400-2:2014` with the gap explained ("Availability × Quality only. Add each asset's cycle time to include Performance"), labels its hero **`OEE (AVG, PARTIAL)`**, and gives the rule behind its verdict ("Below floor: worst MTBF 0.6d"). |
| `asset-hub` | **3 of 3.** Renders `Weibull beta=2.62, eta=243d -> wear-out region; hazard rises with age` — β **interpreted**, η **with its unit** — and stamps its snapshot time. The S/O/D scales and P-F interval live behind modals this walk does not open, so they stay **owed**, not failed. |
| `inventory` | 3 of 4. Names the threshold it crossed ("3 of 27 parts at or below min_qty"), carries units, distinguishes on-hand from reserved. |
| `index` | 1 of 1, plus the cross-surface check: its **LOW STOCK tile (3) equals inventory's own count (3)**. |
| `pm-scheduler` | **2 of 2.** Prints its compliance denominator outright — `80% PM compliance (SMRP)` beside **`72.1% done on time · 114 of 409 ran late`** — and names its due-soon window `(14D)`. |
| `skillmatrix` | **1 of 1.** `19 of 25 possible (5 levels × 5 disciplines)` — denominator *and* the formula behind it, on the page where a malformed credential claim costs someone work. |

**THE THREE FINDINGS, all genuine domain gaps:**

- **`analytics` CI4 — PM compliance states no tolerance window.** It names `SMRP v5.0`, but SMRP
  compliance is *completed-on-time / scheduled*, and "on time" is meaningless without the tolerance it
  is measured against. A % nobody can audit.
- **`analytics` CI6 — the trend states "30 days" but not whether that window is rolling or calendar.**
  On a 30-day reliability trend those are different numbers, and a planner comparing month to month
  cannot tell which they are looking at.
- **`inventory` CI2 — a reorder recommendation with no lead time.** Checked before proposing a fix:
  **`inventory_items` has no lead-time column at all** — only `min_qty`. So this is not a rendering bug,
  and a display-only fix would fabricate a number. It needs a schema column plus supplier data, which is
  a decision about what the platform collects. **Recorded, not invented.**

That `asset-hub` result deserves saying plainly: on the page where a wrong reliability figure does real
engineering harm, the platform interprets its own Weibull shape and carries its units. That is the
behaviour these 176 rows exist to check for, and it is already there.

### BANKED: CI 0 → 7 green, 5 findings — and 5 cells LEFT OWED ON PURPOSE

**A CI oracle is usually two claims joined by "and", and a check that tests one half must not bank the
row.** Read row by row against the evidence, my 18-cell walk covered only 7 in full:

| left owed | what the row asks that the check did not test |
|---|---|
| `analytics` 103 | which factor is **dragging** OEE down — the page names the one that is *absent* |
| `analytics` 105 | MTBF **matches logbook and hive to the same decimal** — needs three pages read together |
| `pm-scheduler` 103 | the **same number Analytics shows**, from `get_pm_compliance_smrp` |
| `inventory` 105 | the unit travels with **every** quantity — one instance is not "every" |
| `inventory` 109 | on-hand **and** available as two labelled numbers |

Leaving a row owed costs one re-walk. Banking it green asserts a property nobody tested, permanently,
and the next reader sees a green cell and moves on.

**Reading the oracles against the evidence caught three cells that were about to be banked wrongly:**
`pm-scheduler` CI2 passed on **"DUE SOON (14D)"** — a *lookahead*, not an on-time **tolerance**;
`asset-hub` CI6 passed on the dashboard's "Daily snapshot at 13:00 PHT" when row 108 asks about **sensor
reading age**; and both are now findings instead of greens.

**FINDINGS BANKED (5):** inventory lead-time (needs a schema column — recorded, not invented);
analytics tolerance window; analytics rolling-vs-calendar; pm-scheduler tolerance window; asset-hub
sensor age.

### A 13th defect, found by chasing an owed row rather than a bug

`inventory` row 109 was one of the five left owed on purpose. Going back to earn it properly found a
real defect — which is the argument for chasing owed rows at all.

The Use modal — **the one screen where a person commits to a quantity** — read **"Available: 2 pcs"** for
a part whose database row is `qty_on_hand 2, qty_reserved 1`. The number was ON-HAND; the word above it
was AVAILABLE. The page already had both figures: the list card one screen back shows a **"1 reserved"**
chip. It just never carried the number to the screen that matters.

**The consequence is physical.** A technician reads "Available: 2", takes 2, and the part staged against
a predicted failure is gone — defeating the exact mechanism that set it aside. A reservation nobody can
see is not a reservation.

Fixed to show both, both labelled: **"Available: 1 pcs (2 on hand − 1 staged for a predicted failure)"**.
An unreserved part is unchanged ("Available: 39 pcs"), so the breakdown appears only where the two
figures differ.

**The guard had to move with the label.** `submitUse()` refused with *"Only 2 available"* while the modal
said Available 1 — a check and a label contradicting each other on one screen. It now says "Only 2 on
hand". **What deliberately did NOT change: the hard block stays at on-hand.** A staged reservation
carries a `recommendation_id` — advice, not a lock — and refusing an urgent job because an algorithm
earmarked a part would be the platform overruling the person at the machine. Exceeding free stock now
**warns and names what it is spending**. Fixing a label is not licence to change what the product
permits.

### `hive` — the same score type, done right one card away

- **108 (GREEN) — low stock agrees across THREE surfaces.** hive "3 Parts low on stock", inventory
  "3 low", index "3 LOW STOCK", all in one run — and the comparison discriminates, because the DB gives
  **3** for `qty_on_hand <= min_qty` and **8** for a hardcoded `< 10`. Had both predicates returned 3,
  three surfaces agreeing would prove nothing.
- **103 (FINDING) — the readiness composite cannot be decomposed.** It shows `60/100 · Stair 1 · Digital
  Logbook` and `Clear Data (32/100) to reach Stair 2` — the current stair and the next unlock, which is
  useful and is not what the row asks. Nothing says what the 60 is **made of** or how its parts are
  **weighted**, so a supervisor cannot tell which of their actions moved it.

  **The capability plainly exists one card away**: the composite RISK score prints `52 /100 composite
  risk · lower is better` **with its bands** (`Tiers: healthy under 35 · at risk 35–65 · critical over
  65`) and a driver (`Few active workers this week`). Readiness gets a stair label; risk gets bands,
  direction and a reason. The fix is to give readiness what risk already has.

**Two instrument slips caught here, both worth naming:**

1. **A check with no row, for the second time today.** I first wrote hive's check to test those risk
   *bands* — true of the page, asked for by **no hive row** — and it would have banked row 103 green on
   another score's evidence. The tell both times was a check I was pleased with that nothing had
   requested.
2. **Debugging a refusal by banking a placeholder.** The banker refused row 108, so I sent a minimal
   payload with `checked: 'test'` to isolate the cause — and it **succeeded**, leaving a green row whose
   evidence read "test". Corrected within the minute to the full 971-char record. *Diagnosing a rail by
   feeding it a placeholder is how a placeholder becomes evidence* — probe with a throwaway row id, never
   with a real one.

### Two cells settled by the DATABASE, where the screen alone could not settle them

**`index` 107 — the low-stock tile counts by reorder point (GREEN).** The tile says "3 LOW STOCK", and
the two candidate predicates give *different* answers for this hive: `qty_on_hand <= min_qty` returns
**3**, a hardcoded `qty_on_hand < 10` returns **8**, out of 27 parts. The tile shows 3, so it can only
have come from the per-part reorder point. **The gap between the predicates is what makes this proof
rather than coincidence** — had both returned 3, the agreement would show nothing and the row would
deserve to stay owed.

**`index` 108 — "9 OPEN JOBS" vs logbook's "6 open" (FINDING, and not the one it looks like).** Against
the database both are correct: hive-wide `status='Open'` is **9** (what the ops-home RPC serves),
worker-scoped is **6** (logbook's own filter). So no number is wrong and nothing went missing. **What is
missing is the SCOPE LABEL on either screen** — a worker seeing 9 at home and 6 in their logbook has no
way to reconcile them, and the natural reading is that three jobs vanished. The fix is copy, not
computation; whether a worker's home tile should be hive-wide at all is Ian's call.

That second one is why the DB query happened at all: 9-vs-6 looks exactly like a defect, and this arc has
already produced one false "DISAGREE" from deliberate role-scoping. Checking beat claiming.

**And the platform already solves it one page over.** The hive board renders the same figure as
**"6 · Your open jobs"** — scope labelled, on the tile. `index` renders **"9 OPEN JOBS"** with nothing.
So this is not a missing capability or a design question the team has never faced; it is one surface
carrying a convention its sibling drops, which makes the fix concrete: **say whose jobs**. It also
raises the sharper question for Ian — hive says "Your" and shows 6, index says nothing and shows 9, so
the two home-ish surfaces disagree about whether a worker's landing figure should be personal or
hive-wide at all.

### `alert-hub` — two truths banked, one after catching a check with no row

- **107 (GREEN) — the zero is qualified.** `ANOMALY SIGNALS 0 · No fused anomalies in your hive right
  now · CLEAR`. **This is the most consequential zero on the platform**: "nothing wrong" and "nobody has
  looked" lead a supervisor to opposite actions and a bare `0` renders identically for both. Here the
  zero carries a sentence saying the hive was checked, plus a CLEAR tag.
- **109 (GREEN) — every alert row carries its age.** `HIGH · BE-001 · 2d ago · Multiple failure types` —
  30 rows on the walked feed. Age sits beside severity and asset, so a reader ranks by both without
  opening anything.

**The near-miss is the lesson.** My check first tested whether the alert COUNT stated a denominator
("51 of 62 alerts need eyes now") — a true observation, and a claim **no alert-hub row makes**. It would
have banked a green against row 109's *age* oracle on unrelated evidence. **A check with no matching row
is not a bonus; it is a green waiting to be attached to the wrong claim.**

**Bank now: green 2252 · owed 2146. CC 148 green / 160 owed. CI 10 green / 166 owed** — a family that
had never been walked now has evidence, and every green in it has been audited against its own `saw`
string.

**FINDING · `inventory` CI2 — a reorder recommendation with no lead time.** The page says "Order 3 low
parts… so they arrive before they hit zero" and never states how long they take to arrive. Checked
before proposing a fix: **`inventory_items` has no lead-time column at all** — only `min_qty`. So this
is *not* a rendering bug, and a display-only fix would be fabricating a number. It needs a schema column
plus supplier data, which is a decision about what the platform collects. **Recorded, not invented.**

That `analytics` result deserves saying plainly: on the page where a wrong metric definition does real
engineering harm, the platform states its standard, states its basis, and labels its own partial figure
as partial. That is the behaviour these 176 rows exist to check for, and it is already there.

### A dead container nearly contaminated a 30-minute sweep, silently

Mid-run, `supabase_edge_runtime_workhive` **exited (255)**. Caught only because a text harvest for CI
showed `analytics` at **1211 chars instead of 4138**, rendering:

> name resolution failed · Network problem: check your connection … Analytics unavailable

**That is the page behaving CORRECTLY about a broken dependency** — and it is indistinguishable from a
page defect to any oracle that reads the screen. Every edge-backed page (analytics, shift-brain,
assistant, hive, logbook, asset-hub, project-report) was being graded against a stack that was not
running. A sweep taken then is not a slow reading; it is a **wrong** one, on its way to being banked as
evidence.

`docker start` restored it (analytics back to 4138 immediately) — the move this platform already has
twice in memory. So the check now lives in the harness rather than in my recall: `edge_up()` pre-checks
`127.0.0.1:54321` **before** the 30 minutes are spent, and **SKIPs** rather than fails, because a missing
local dependency is not a product regression and a gate that cries wolf gets ignored.

### The gate could never have passed

`validate_page_ui_provers.py` gave every prover 900s. This one walks 20 pages × (1 control + 7 modes), each
deliberately out-waiting the platform's own timeouts — ~90s per page, **~30 minutes** for the sweep. It
reported *"exceeded 900s — a hung browser is a broken gate, not a pass"* about a prover that was working and
had never once fit its budget. The message draws the right distinction, so the fix is a per-prover budget
(`TIMEOUT_S`), not a removed ceiling.

**Every one of these pages has a loading affordance.** So the earlier reading — "pm-scheduler has none,
nothing to be late" — was wrong twice over: pm-scheduler has one (and now PASSES), and none of the
remaining seven is missing one either. The live symptom is uniform; the causes are not, and the two already
read apart are a deliberate suppression and an ordering bug.

They stay HELD. The banker refuses to bank an absence-asserting failure without a human reading the page's
own guard, precisely because `logbook` proves an identical symptom can be a fix.

#### ★ CORRECTION — MOST OF THAT "PLATFORM-WIDE" FAILURE WAS MY OWN DETECTOR

The table above was measured with a `busy` detector that matched `[class*="loading"]` and nothing else.
**pm-scheduler renders `<div id="dash-loading">Loading assets...</div>`** — the word is in the ID, the
classes are Tailwind utilities, and the wait state is a plain English sentence. So the oracle reported "NO
busy indicator" for a page that was saying *Loading assets…* to the person.

With the detector widened to ids, `aria-busy`, `progress`/`role=progressbar` **and the visible text**,
`pm-scheduler fail_slow` PASSES — "1 busy indicator visible mid-flight". On the corrected re-run, 19 cells
in, only **two** cells fail: `index fail_partial` and `hive fail_slow`, both independently confirmed by
reading the code. The earlier "fails on every page walked except index" was largely instrument error and
is withdrawn.

**What survives is the taxonomy, not the count** — and the taxonomy is what mattered: `logbook` is a
deliberate fix, `hive` is a real ordering defect, and a page that answers in a sentence rather than a class
name is doing the right thing in a way a lazy detector cannot see. **A wait state is often just a
sentence.** That is now the rule the oracle encodes.

#### ★ `hive` — THE LOADING SKELETON IS GATED BEHIND THE VERY READ IT EXISTS TO COVER (real, and NOT the logbook case)

`hive fail_slow` failed with **121 characters on screen at 2.5s** of a 6-second read — near-blank, no
skeleton, no spinner. Triaging it the way the rule now demands (read the page's own guard first) shows this
is **not** a deliberate suppression like logbook's:

- [hive.html:3816](hive.html#L3816) paints the skeleton **unconditionally**, at the very top of
  `loadFeed()`, and its comment states the intent: *"#feed never flashes blank before entries render."*
- But [hive.html:2578](hive.html#L2578) `await db.rpc('get_hive_board_dashboard', …)` runs **first**, and
  `loadFeed()` is only invoked at [:2584](hive.html#L2584) inside the `Promise.allSettled` that follows.

So the skeleton is painted **after** the board RPC resolves — which is the same moment the data arrives.
During the entire slow window the person sees a near-empty page, and the affordance appears exactly when it
is no longer needed. **The loading state is gated behind the read it is meant to cover.**

This is the third ORDERING defect of the day, and they share one shape: *the cure exists, and runs too
late.* The identity-restore bounce (`restoreIdentityFromSession` resolving after the redirect had already
navigated away) and this are the same bug wearing different clothes.

**Fix shape:** paint the skeleton before the board RPC is awaited — at the top of the init path rather than
inside the loader it gates. Held until after the CC sweep banks, because editing `hive.html` now would
stale the rows this very sweep is earning (A15).

**`inventory` is the same suspicion, unconfirmed:** its skeleton at [:2058](inventory.html#L2058) is also
unconditional and also inside a loader, and it showed 572 chars at 2.5s — but I have not read its call
ordering, so it is recorded as a candidate rather than asserted.

#### ★ THREE FAILURE SHAPES, THREE DIFFERENT OWNERS — and only two of them can be fixed centrally

The sweep separates read failures into shapes that look identical to a person and are structurally
distinct to the code. This is why one central fix could not close the family:

| shape | what the transport sees | who can notice it |
|---|---|---|
| non-2xx (500 / 401 / 403) | a `res` with `ok === false` | **transport** — `_whNoteAuthFailure(res)` (fixed 2026-08-14 AM) |
| rejection / abort (offline, timeout) | **no `res` at all** — `.then` is skipped | **transport** — the `.catch` that notices and re-throws (fixed 2026-08-14 PM) |
| 200 with an unparseable body (`fail_partial`) | `res.ok === true` — it looks like SUCCESS, and the notice is even CLEARED | **only the caller** — the parse error surfaces inside supabase-js, where the empty catches eat it |

`index fail_partial` FAILED on that third shape: 20 truncated responses, and the page said nothing
(1098 chars healthy → silent). The transport cannot help here without parsing every body, which it
deliberately does not do — so this one is genuinely per-page work, not another one-line central fix.

That distinction is worth more than the individual row: it says exactly how far the two central fixes
reach, and where they stop.

**MEASURED ACROSS THE ROSTER, because one page is an anecdote.** Counting read-error surfacing
(`whReadError` / `whListError`) against annotated silent swallows (`empty-catch-allow`):

*(Re-measured across `.html` **and** the sibling `.js` modules after the first pass missed
`engineering-design`, whose logic lives in a 2.3 MB `engineering-design.js`. The per-page counts below are
the corrected ones; **the membership of the zero-surface list did not change**, so the conclusion survived
re-measurement even though several of its numbers did not.)*

- **12 of 22 pages call NEITHER helper anywhere in html or js** — index, logbook, pm-scheduler,
  project-manager, dayplanner, asset-hub, analytics, shift-brain, voice-journal, assistant,
  engineering-design, report-sender.
- **338 catch blocks** across the roster, of which **183** are annotated `empty-catch-allow`. hive has the
  most catches (42, 27 annotated), then index (31/22), voice-journal (28/11), resume (26/9).
- The 10 that DO adopt are led by public-feed (6), hive (6), community (5), achievements (5), alert-hub (4),
  skillmatrix (4).

This is the same architectural fact `utils.js` recorded for the 401 path — *"118 annotated `catch (_)`
blocks across 11 pages, against exactly ONE page that calls whReadError"* — now measured over the whole
roster and the whole error surface.

**★ THE BLAST RADIUS IS SMALLER THAN THAT COUNT SUGGESTS — BUT NOT AS SMALL AS I FIRST WROTE.** I claimed
the two central transport fixes cover shape 1 "for all 22 pages regardless of adoption, when a read 500s or
the network dies." **That is wrong about the 500**, and the sweep caught me: `analytics fail_500` FAILED,
and reading [utils.js:642](utils.js#L642) shows why —

```js
if (!res || (res.status !== 401 && res.status !== 403)) return;   // 500 is NOT noticed
```

The notice is deliberately scoped to the two AUTH statuses, because its sentences are about the session and
about permission; a 500 is neither, and inventing a session message for a server fault would be the
401-blaming-identity defect in reverse. So the real coverage is:

| shape | centrally covered? |
|---|---|
| **401 / 403** | **yes** — every page, regardless of adoption |
| rejection / abort (offline, timeout) | **yes** — every page (the `.catch` added today) |
| **500 and other non-auth statuses** | **NO** — per-page, and 12 of 22 pages have no read-error surface at all |
| 200 with an unparseable body | **NO** — the transport sees success; only the caller can catch it |

So the remaining ask is narrower than "180 catch blocks", but wider than my first correction implied: two
of the four shapes still land on the pages, and `analytics fail_500` and `index fail_partial` are the first
two confirmed instances.

**★ AND THE ADOPTION COUNT ITSELF OVERSTATES COVERAGE — a second correction to my own metric.** `resume`
appears in the "adopts" column with 3 references, yet FAILED `fail_500`, `fail_partial` AND `fail_slow`.
Reading them shows why: its only real call is
[resume.html:845](resume.html#L845) —

```js
whListError(wrap, "Couldn’t load your saved resumes. Check your connection and try again.", …)
```

— which covers **one panel** (the saved-resumes list, inside the V3 manager dialog). The page's initial
load has other reads with no surface at all. **Adoption is not binary and cannot be counted per FILE:** one
`whReadError` reference protects one read path, not a page. So "10 of 22 pages adopt" is an upper bound on
pages that adopt *anywhere*, and the true per-READ coverage is lower than that table suggests.

This is why the injection matters more than the grep: a file-level count says `resume` is covered, and
failing its reads says otherwise in three different modes.

**★★ AND THEN THE TWO METHODS AGREED, WHICH IS THE REAL VALIDATION.** The live sweep's
`fail_500`/`fail_partial` failures land on exactly six pages — and every one is predicted by the static
measurement:

| page | static adoption | live result |
|---|---|---|
| `index` | **zero** read-error surface | fails `fail_partial` |
| `analytics` | **zero** | fails `fail_500` + `fail_partial` |
| `engineering-design` | **zero** (logic in a 2.3 MB sibling `.js`) | fails `fail_500` + `fail_partial` |
| `resume` | 3 refs — **one panel** (saved-resumes list, in a dialog) | fails `fail_500` + `fail_partial` |
| `project-report` | 1 ref — partial | fails `fail_500` + `fail_partial` |
| `analytics-report` | 1 ref — partial | fails `fail_500` + `fail_partial` |

**No page with real, page-wide adoption failed these two modes**, and no page failed them without the
static count predicting it. Two instruments built on completely different evidence — reading source versus
breaking live reads — selecting the same six surfaces is much stronger than either result alone, and it
also confirms the per-PANEL reading of adoption: the three "partial" pages fail exactly like the three
"zero" pages, because one guarded panel does not protect a page.

#### ★ A `fail_slow` FAIL THAT MUST **NOT** BE BANKED AS A DEFECT — logbook's missing skeleton is a DELIBERATE FIX

The oracle reported `logbook fail_slow` FAIL on hard evidence: **zero skeleton elements in the DOM at 1.2s,
2.5s and 4.0s** of a 6-second read, the page frozen at 882 characters, for BOTH the supervisor and the
worker. The measurement is sound. **The verdict would have been wrong.**

Reading the guard it trips on ([logbook.html:1941](logbook.html#L1941)) shows a fix dated 2026-08-05, with
its reasoning written beside it:

> *"on initial load in TEAM mode the entry feed showed a permanent shimmer, still there at 14s, while the
> data was fine (200 rows loaded, request 200 OK, console silent)… `renderEntries()` takes its team-mode
> branch, which CLEARS `#entries-list`; then the init-time personal load… calls `loadEntries()`, which
> found the list empty and painted a 4-row skeleton… the placeholder outlived the load with nothing left to
> clear it."*

The page chose **no skeleton** over **a permanently stuck skeleton** — and a stuck skeleton is the worse
defect, already recorded in memory as invisible to every gate. Banking this as a bug would ask someone to
undo a deliberate repair and reintroduce the shimmer.

**What IS honest to say** is narrower and more useful: the minimal fix removed the *symptom* in team mode
without giving that mode a loading state of its own, so during a slow read the person sees a static
half-page. The real gap is not the missing skeleton — it is that `renderEntries()` never returns to clear
one, so team mode has no owner for its loading affordance. That is a design note for Ian, not a red.

**RULE FOR THIS FAMILY:** a `fail_slow` FAIL is a CANDIDATE, never a finding, until the page's own guard is
read. Two of the seven modes (`fail_slow`, `fail_null_field`) assert an ABSENCE, and an absence is exactly
what a deliberate suppression looks like from outside. My `_viewMode !== 'team'` hypothesis was also tested
and REFUTED — the worker sees no skeleton either — so the mechanism behind the second persona remains
unidentified and is not claimed.

#### THREE INSTRUMENT CORRECTIONS, EACH OF WHICH HAD PRODUCED A CONFIDENT FALSE *FAIL*

1. **Waited 9s for a timeout the platform bounds at 15s** (`whQueryTimeout`, utils.js:1785) — reporting
   "the page said NOTHING about it", a true statement about an instant nobody experiences and a false one
   about the product.
2. Widening the wait exposed that **`whQueryTimeout` is adopted by only SIX surfaces** — community,
   public-feed and the four marketplace pages. On these 20 pages the only bound is the transport abort at
   `WH_DB_TIMEOUT_MS || 45000`. Rather than idle **45s per page**, the prover sets that documented knob to
   4s — utils.js:703 says outright *"tune via window.WH_DB_TIMEOUT_MS"*, so it configures a supported knob
   instead of faking behaviour.
3. **★ The hang stub IGNORED THE ABORT SIGNAL.** `_timeoutFetch` wraps every read in an AbortController; a
   real fetch rejects when it fires, but a stub returning a bare 60s timer does not — so the platform's own
   timeout became a **no-op**, the page sat silent forever, and the oracle blamed the page for having no
   timeout handling. **A fake fetch has to emulate CANCELLATION, not just latency**, or it disables the
   very mechanism under test and then reports its absence.

**And the injection method reconciles two rules that look contradictory.** The spec says never patch
`window.fetch` (supabase-js captures it at construction, so a late override silently no-ops); this project
says never use `page.route` (a warm service worker bypasses it). Both are right — the difference is **when
the patch lands**. `addInitScript` runs before any page script, so the client is constructed around the
patched fetch and the patch sits above the service worker. Hit-counted regardless: a page whose counter
reads zero is UNGRADED, because *"the page said nothing about the error"* is exactly what a page with **no**
error would say.

---

### ★★★ FINDING — `report-sender` SENDS WITH THE ANON KEY, SO THE EDGE FUNCTION CANNOT IDENTIFY THE CALLER (2026-08-14)

Found while grounding CM `what_does_it_cost`, by reading the send handler rather than pressing Send.

**BOTH send paths use a RAW `fetch` carrying the PUBLISHABLE key as the bearer** —
[report-sender.html:1885](report-sender.html#L1885) (`sendReportEmail`) and
[:1147](report-sender.html#L1147) (`resendReport`):

```js
headers: { 'apikey': SUPABASE_KEY, 'Authorization': `Bearer ${SUPABASE_KEY}` }   // SUPABASE_KEY = sb_publishable_…
```

`db.functions.invoke()` attaches the caller's session automatically; a hand-rolled `fetch` does not. So the
function receives the anon key where a user JWT belongs.

**Every link verified, and the decisive one MEASURED rather than reasoned:**

| # | link | how established |
|---|---|---|
| 1 | client sends the publishable key as bearer | read, both call sites |
| 2 | `resolveIdentity()` → `db.auth.getUser(bearer)` | read, `_shared/tenant-context.ts:88-100` |
| 3 | **`getUser(<publishable key>)` → 401 `no_authorization`, no user** | **measured live against the local auth endpoint** |
| 4 | `authUid = null` + `hive_id` → `resolveTenancy(null, …)` → **401 "Sign-in required."** | read, `tenant-context.ts:118` |
| 5 | no `hive_id` (solo) → `!authUid` → **401 "Authentication required to send email"** | read, `send-report-email/index.ts:176` |

So a signed-in supervisor pressing **Send Reports** is refused and told to sign in — the platform's own
401-told-a-signed-in-person defect, in the one place it cannot be worked around by retrying.

**WHAT IS NOT PROVEN, stated plainly:** the end-to-end 401 could not be reproduced locally, because the
function returns **503 "Email service not configured — set RESEND_API_KEY"** at
[:142](supabase/functions/send-report-email/index.ts#L142) — *before* the auth check at
[:158](supabase/functions/send-report-email/index.ts#L158). My first probe hit that 503 and was
INCONCLUSIVE, not confirming; the chain above is what settles it, with link 3 measured directly. A local
end-to-end confirmation needs `RESEND_API_KEY`, and I did not set one, because a successful call sends real
email — and a sent report cannot be un-sent.

**The edge function itself is sound** and was not the problem: it verifies hive membership before emailing
(`Pillar I`), and its own comment records the hole it already closed — *"The old code skipped BOTH
membership and rate-limit, leaving an unauthenticated branded-email relay (phishing/spam)."* The defect is
entirely on the client side: a raw fetch where `functions.invoke` belongs. This is the same smell §P19
already flags on `resume` ("reached by a raw `fetchWithTimeout` … so it bypasses the shared invoke
wrapper") — one habit, two pages.

#### ✅ FIXED AND PROVEN AT THE BROKEN LINK (2026-08-14)

Both send paths now use `db.functions.invoke('send-report-email', { body })`, which attaches the session.
The proof is symmetric — the same endpoint, the same request, the only difference being the token:

```
getUser(<publishable key>)  -> 401 no_authorization, no user            <- what the code sent before
getUser(<session JWT>)      -> bcb5a6e3-…  |  leandromarquez@…          <- what invoke() attaches now
```

That uid is exactly what `resolveTenancy` needs to verify hive membership. `invoke()`'s `{data, error}`
shape also lets the function's OWN sentence surface instead of a generic transport error, so a refusal
still says why. Page loads with **0 errors**.

**Not claimed:** no email was observed leaving. The local function 503s on a missing `RESEND_API_KEY`
before the auth check, and I did not set one, because a successful call sends unrecallable mail. What is
proven is the identity link that was demonstrably broken and is now demonstrably correct.

#### ★ AND A CORRECTION TO MY OWN CLAIM, PLUS THE BOUNDED SWEEP

I wrote "0 raw fetches remain" after the fix. That was scoped to `send-report-email` only, and stated as
though it covered the file. **`report-sender` still contains three more anon-bearer fetches** —
`voice-transcribe` ([:1579](report-sender.html#L1579)), `voice-report-intent`
([:1613](report-sender.html#L1613)), `scheduled-agents` ([:1737](report-sender.html#L1737)).

Sweeping the roster for the class: **12 files call `/functions/v1/`; 4 send `Bearer ${SUPABASE_KEY}`** —
`report-sender`, `voice-journal`, `voice-handler.js`, `wh-feedback-fab.js`. **That is a candidate list, not
a defect list**, and the 13-innocent-pages lesson applies directly: `voice-handler.js` is demonstrably
CORRECT on its main paths — [:624](voice-handler.js#L624) uses `db.functions.invoke('ai-gateway')`, and
[:7782](voice-handler.js#L7782) reads
`(await db.auth.getSession())?.data?.session?.access_token || SUPABASE_KEY`, i.e. the session token with an
anon fallback. And `tts-speak` performs **no identity check at all**, so calling it with the anon key is
not a defect.

The verification each site needs is per-FUNCTION, not per-file: does the target *refuse* when `authUid` is
null, or treat it as a legitimate anonymous caller?

#### ✅ SWEPT AND CLOSED — 3 defects in ONE file; the other three files were innocent

| call site | does the target refuse a null uid? | verdict |
|---|---|---|
| `report-sender` → `send-report-email` | **yes** — `resolveTenancy` 401 ([:176](supabase/functions/send-report-email/index.ts#L176)) | **DEFECT — fixed** |
| `report-sender` → `voice-report-intent` | **yes** — gated `if (hive_id)` → `resolveTenancy` ([:127-129](supabase/functions/voice-report-intent/index.ts#L127)), and hive_id IS passed | **DEFECT — fixed** |
| `report-sender` → `scheduled-agents` | **yes** — same gate ([:447-449](supabase/functions/scheduled-agents/index.ts#L447)); the call's own comment says *"we passed hive_id"* | **DEFECT — fixed** |
| `report-sender` → `voice-transcribe` | **no** — identity only KEYS a rate limit, `soloRateLimitKey(authUid, ip)` ([:76-80](supabase/functions/voice-transcribe/index.ts#L76)); never refuses | innocent — left, with a comment saying why |
| `voice-journal` → `tts-speak`, `voice-transcribe` | **no** — `tts-speak` has zero identity checks | innocent |
| `voice-handler.js` → `ai-gateway` | n/a — uses `db.functions.invoke` ([:624](voice-handler.js#L624)) and reads `getSession()?.access_token \|\| SUPABASE_KEY` ([:7782](voice-handler.js#L7782)) | already correct |
| `wh-feedback-fab.js` → PostgREST insert | n/a — not an edge function; its comment states the intent: *"No SDK dependency — so the widget works on minimal public pages … that don't load utils.js"* | innocent by design |

**`scheduled-agents` was the worst of the three:** that is REPORT GENERATION, refused 401 before a report
existed to send. **`voice-report-intent` failed invisibly** — its `catch` already supplied a graceful empty
voice-context, so the feature silently degraded on every call with nothing to show for it.

The residual `Bearer ${SUPABASE_KEY}` grep hits in `report-sender` are now (1) my own explanatory comment
and (2) the deliberately-anonymous `voice-transcribe` call, which carries a comment saying **do not "fix"
this to match its neighbours** and why. An unexplained survivor is what gets turned into a regression by
the next person running the same grep.

---

### ★ CM `what_does_it_cost` — THE ONE ACTION THAT CANNOT BE UNDONE IS THE ONE WITH NO CONFIRMATION (2026-08-14)

`report-sender` is the only page in the roster whose primary action is **outward and irreversible** — this
roadmap's own §P20 says so: *"a sent report cannot be un-sent"*, and its domain truth reads *"What will be
sent, and to whom, is stated BEFORE sending — cost and consequence before commitment, the one place this
platform cannot offer an undo."*

**Measured, and the ratio is the finding.** Counting confirmation prompts and cost/irreversibility
language per page:

| page | cost/irreversibility language | confirm prompts | are its actions reversible? |
|---|---|---|---|
| `project-manager` | 2 | **8** | yes |
| `hive` | 2 | **5** | yes |
| `logbook` | 17 | 3 | yes |
| **`report-sender`** | **1** | **1** | **NO — the send cannot be recalled** |

**The handler confirms it.** [report-sender.html:1811](report-sender.html#L1811) `doSend()` runs: gather
recipients → `if (!recipients.length)` bail with *"Select a contact or enter an email."* → immediately
`setCardState('processing')` and send. There is no confirmation step, no final recipient review, and no
statement anywhere that the send cannot be recalled. The button is disabled until a selection exists
([:954](report-sender.html#L954)), which prevents an EMPTY send — not a wrong one.

**Stated fairly:** the recipients and reports are selected by the person, so they are on screen; this is
not a hidden-consequence bug. The gap is that the platform spends its confirmations on reversible actions
(8 on project-manager, 5 on hive) and spends none on the single action it cannot take back. A mis-selected
contact — a plant's numbers to the wrong manager — has no moment where the person is asked to look again.

**Not fixed, deliberately.** What the confirmation should SAY (and whether it should exist at all, versus
an undo window or a send-log with recall) is a product decision about someone else's outward communication,
not a defect with one correct repair. Recorded for Ian. **NON-SENDING:** this was established by reading
the handler and by opening the page read-only — nothing was ever submitted, because a sent report cannot
be un-sent, which is the entire point of the finding.

---

### ★★CM `reward_explained` — THE PLATFORM EXPLAINS PROGRESS AND NOT STANDING (2026-08-14)

`tools/prove_reward_explained.mjs` (gate `cm_reward_explained`) collects every visible reward figure — XP,
level, tier — and requires its criteria in its **own** card: what earns it, or the threshold it sits at.

**THE SYNTHESIS, WHICH IS THE POINT: progress figures explain themselves; standing figures do not.**

| page | result | the bare one |
|---|---|---|
| `achievements` | **22 of 23** explained | `"153 pts"` — HIVE STANDINGS |
| `skillmatrix` | **4 of 5** explained | `"Lv 5 / 5"` — the row already AT target |
| `community` | **0 of 2** explained | `"185 XP"`, `"50 XP"` |

Where the platform is telling someone *what to do next* it is genuinely good at this: `"1949 XP to Lv.46"`
carries its own target, and skillmatrix pairs every level with `"Target: Level 3 · Actual: Level 2"`. Where
it shows someone *where they rank* — a leaderboard score, a reputation total — the number is bare. A person
cannot tell what a point counts or over what window, which is precisely the domain truth this roadmap
already wrote for reputation ("states WHAT IT COUNTS and over what window"). **One missing sentence per
standings surface, not a per-page defect.**

#### SEVEN INSTRUMENT CORRECTIONS — and the last three came from the PRODUCT'S vocabulary, not mine

1. **`^153 pts$` anchored the whole string** → found ONE reward on a page with 47 XP mentions, then failed
   the page on it. A denominator collapse wearing a finding's clothes.
2. **Reading the live DOM** showed the real shape — `.xp-text` rendering `"1949 XP to Lv.46"`, the figure
   *and its criteria in one string*. The page was explaining itself while the oracle measured past it.
3. **`'\d'` inside a JS single-quoted string collapses to `'d'`** → matched nothing; all 18 pages reported
   "no rewards".
4. **A Python heredoc ate `\b` into literal backspace bytes (0x08)** — invisible to a file reader, exposed
   only by a byte dump. Third escaping collapse of this kind on this project; the first once made an entire
   injection script inert while the prover reported on it. Now a regex **literal** handed over as `.source`,
   with the file verified to contain zero control bytes.
5. **The widened pattern matched prose** — `"4 of 12 domains touched at Level 1+"` matches on "Level 1" and
   is a sentence, not a reward. A rendered reward is terse.
6. **It did not know the word `Lv`.** It reported `skillmatrix` — a credentials page with 52 badge
   functions — as rendering *no rewards at all*. The product says `"Lv 2 / 3"`. An oracle that recognises
   only the abbreviations its author imagined measures the author.
7. **The container was a fixed selector list** — a guess about someone else's markup. skillmatrix renders
   the explanation as a **sibling**, matching none of card/tile/badge/li, so the search fell back to the
   immediate parent and failed the page for not explaining a level whose explanation was one element away.
   It now climbs until the block holds something besides the figure, **bounded at 4 hops** so it cannot
   reach `<body>` and credit the whole page — that bound is what stops it becoming the body-wide-keyword
   mistake again. Tier legends (`"Lv 1-10"`) are excluded too: a range IS the threshold, and demanding that
   the explanation carry its own explanation is circular.

**Teeth, both directions, passing first try:** a planted bare reward is flagged, an explained one is not,
and the two shapes that caused the false reds (a range legend, prose mentioning a level) stay ignored.

---

### ★★CN ux-journey — the family with 330 rows and not one walk, opened (2026-08-14)

`tools/prove_journey.mjs` (gate `cn_journey`) walks **J1 `first_run_to_value`, J2 `repeat_visit`, J4
`two_sided_same_object`** across the 22 product pages × their 3 grounded personas — 198 of CN's 330 rows.

**IT EXTENDS `tests/ux-journeys.spec.ts` RATHER THAN REPLACING IT.** That spec already walks these journeys
with the two rails that matter — *every step asserts the TRANSITION, never that a control was clickable*,
and *a journey that cannot be CONSTRUCTED fails, it never skips* — but only over 4 marketplace surfaces.
Memento surfaced it before any code was written, which is the difference between extending a proven harness
and re-deriving its lessons at full price.

**PERSONAS ARE NOT INVENTED.** Each page's own `page_bank_anatomy/<page>.json` `journey_personas` supplies
the label ("worker (own entries)", "reliability engineer (FMEA/RCM authority)", "two_context (two techs,
one PM)"), mapped to an identity the harness can actually establish. A label that maps to nothing FAILS —
it is never quietly walked as a signed-in worker, because defaulting is how a persona claim gets banked for
the wrong identity.

#### ✅ WALKED AND BANKED — 239 of 330, zero findings (2026-08-14)

66 personas × 22 pages, **246 readings, 1 failure** — and that one was `pm-scheduler P1`'s state-gated
opener timing out, an instrument artifact whose fix landed after the walk launched, so it was **held back
rather than banked as a defect**. J5 is being re-walked with that fix instead.

| journey | walked | failing |
|---|---|---|
| J1 `first_run_to_value` | 66 | 0 |
| J2 `repeat_visit` | 66 | 0 |
| J3 `cross_surface_handoff` | 56 | 0 |
| J4 `two_sided_same_object` | 51 | 0 |
| J5 `abandon_resume` | 17 | (1, held back) |

**Bank: green 775 → 1014 · owed 2468 → 2229 · 23.9% → 31.3%.**

**THE GAPS ARE RECORDED, NOT HIDDEN.** 74 rows were deliberately left OWED because the property does not
exist on that page, each carrying its reason: **49** `abandon_resume` (the view has no visible text field
to abandon), **15** `two_sided_same_object` (no figure is visible to both sessions — `assistant` is a chat
surface with no id-bearing numbers at all), **10** `cross_surface_handoff` (no usable in-app link to
another product page). An unexplained gap in coverage is indistinguishable from an oversight when someone
reads it later; a red invented for an absent property is the vacuity R10 forbids. Neither happened here.

#### SIX INSTRUMENT CORRECTIONS, ALL BEFORE A SINGLE ROW WAS BANKED

Every one of these would have produced confident findings against pages that were behaving correctly. They
are listed because the ratio is the point: a NEW oracle family costs several correction rounds before its
first honest reading, which is exactly why an existing harness is worth extending when one exists.

1. **A swallowed sign-in.** `newCtx` ended each `signIn` with `.catch(() => {})`, so a failed sign-in became
   an anonymous walk wearing the persona's name — in a harness whose own rule says an unestablished persona
   is a finding. The error is now returned and fails the journey.
2. **No landed-URL check.** `hive.html:1866/1870/2211` bounce an unauthenticated caller to
   `index.html?signin=1`. Without capturing where the read actually happened, a reading taken on *index*
   gets filed against *hive*. A redirect is now its own outcome — and correctly PASSES for an anon persona,
   for whom the auth wall is the right journey.
3. **A word mistaken for a demand.** `hive` failed `repeat_visit` on "GET STARTED" — a bare `<span>` at
   y=1101, *below the fold*, uppercased by CSS, on a page simultaneously showing that worker "YOUR OPEN
   WORK · 2 open jobs assigned to you". A phrase must now attach to an element that could actually block:
   visible, above the fold, and either in an overlay or on a page with no content. Anything else is recorded
   as `setupMention` — kept, but not converted into a verdict. **I also guessed the cause before measuring
   it**, blaming the redirect from #2; the landed URL said `hive`, and only a live query found the element.
4. **The narrowing had no teeth, and failed its own test twice.** A `--selftest` injects a real blocking
   overlay and requires the detector to fire, then removes it and requires silence. First run: the loop took
   the *first* above-fold match and stopped, so a page's own harmless CTA shadowed a genuine overlay
   appended later (fixed by ranking candidates). Second run: the fixture itself was invisible, because
   `class="modal-overlay"` is hidden by the platform's shared CSS until `.open` — the test blaming the
   detector for ignoring something that genuinely was not visible.
5. **A reasoned empty state is not a dead end.** A bare `chars < 300` rule punishes pages that handle
   emptiness *well*. The exemption reuses `REASONED_EMPTY_SRC` from `session_signals.mjs` rather than
   retyping a second copy of the predicate.
6. **The wipe destroyed the identity it claimed to be testing** — see the finding immediately below, which
   is the one case where a broken probe measured something worth keeping.

**AND J4 IS TWO SESSIONS, NOT TWO ROLES.** Comparing a worker's rendering against a supervisor's reported
logbook as "3 of 8 shared figures DISAGREE between two members of the same hive" (#total-count 314 vs 516,
#open-count 2 vs 6). Every number was right: the page scopes the whole view by role, and the giveaway was a
third element — `#lb-progress` read "JOBS CLOSED" for the worker and "TEAM JOBS" for the supervisor.
Matching on the adjacent label did not rescue it either, because `#total-count` is labelled "entries" on
*both* sides. **That gap is itself a real finding — one word naming two different populations with nothing
on screen saying whose — and it is recorded against CM `what_is_this_number`, not smuggled into a CN row.**
J4 now compares two concurrent sessions of the *same* identity, which is what these pages' anatomy means by
`two_context`; role scoping is then identical by construction and any disagreement left is a race or a
stale cache. A comparison over zero shared figures is reported as NOT MEASURED and fails.

---

### ★ FINDING (2026-08-14, from a contaminated run that measured something real) — three pages throw a signed-in person to the landing page using a check that had the answer one line above it

While building the CN journey prover I wiped localStorage too aggressively, keeping only the auth keys.
That destroyed the cached identity (`wh_last_worker` / `wh_worker_name` / `workerName`, read by `whWorker()`
at [utils.js:3148](utils.js#L3148)) and the oracle reported pages as BOUNCED — a finding about the probe,
which is why the keep-list now preserves membership and identity. **But the run it invalidated is a valid
experiment in its own right**, because the SESSION stayed perfectly alive throughout: it measures what a
signed-in person meets after clearing site data, or after an eviction.

**THREE of the 21 pages walked bounce them, and all three share one line-for-line pattern** — a
synchronous redirect on the missing cached name, sitting beside an `restoreIdentityFromSession(db).then(…)`
that re-derives that very name from the live session and is never awaited:

| page | the redirect | the un-awaited cure |
|---|---|---|
| `achievements` | [:504](achievements.html#L504) `if (!WORKER_NAME) { location.href = 'index.html' }` | [:498](achievements.html#L498) |
| `report-sender` | [:818](report-sender.html#L818) `… 'index.html?signin=1'` | [:855](report-sender.html#L855) — *registered AFTER the redirect decision* |
| `project-report` | [:333](project-report.html#L333) `… 'index.html?signin=1'; return;` | [:308](project-report.html#L308) |

(I first wrote "exactly one page: achievements" from a partial run and it was wrong — `report-sender` and
`project-report` surfaced as the sweep finished. The count here is over the completed walk.)

**The delta is the proof, and it is unusually clean:** `first_run` FAILED (bounced to index) while
`repeat` PASSED on the very next load — because the restore *did* complete and re-cache the name, just too
late for the check that had already navigated away. The recovery works; only its ordering is wrong. Every
other page either does not gate on the cached name or tolerates its absence.

This is a robustness gap on the identity-restore path (CO/CC territory), **not** a `first_run_to_value`
failure, so it is recorded here rather than smuggled into a CN row whose claim it does not match.

#### ✅ FIXED AND VERIFIED IN BOTH DIRECTIONS (2026-08-14)

The gate now consults the **session** before navigating away, because a cold cache is not proof of being
signed out and `restoreIdentityFromSession()` is authoritative — it returns `''` only when there genuinely
is no session. Each page needed a different shape, decided by what was in scope where the gate sits:

| page | fix |
|---|---|
| `achievements` | the restore promise is kept; the bounce awaits it and fires only if it resolves empty |
| `report-sender` | the gate **moved down**, because `restoreIdentityFromSession(db)` needs `db`, a `const` declared later whose TDZ makes `typeof db` throw at the old site |
| `project-report` | the gate already sat in an `async` IIFE, so it simply `await`s the restore — the cheapest form of the fix in the roster |

**Verified against the original defect condition** — a live session whose identity cache has been cleared:

```
achievements     cache CLEARED + session alive -> landed=achievements   chars=1749  STAYED (fixed)
report-sender    cache CLEARED + session alive -> landed=report-sender  chars=1877  STAYED (fixed)
project-report   cache CLEARED + session alive -> landed=project-report chars=1167  STAYED (fixed)
logbook          cache CLEARED + session alive -> landed=logbook        chars=1107  STAYED (control)
```

**And in the other direction, which is the half that matters most** — a fix that stops bouncing signed-IN
people must still bounce signed-OUT ones, or an auth gate has quietly become a no-op:

```
achievements     NO session -> landed=index   BOUNCED (gate intact)
report-sender    NO session -> landed=index   BOUNCED (gate intact)
project-report   NO session -> landed=index   BOUNCED (gate intact)
```

All three pages also load signed-in with **zero page errors**. The old comment claiming "the sync
auth-check redirect still runs first; session identity overrides asynchronously" was the bug written down
as a design note: the redirect *navigates away*, so there is nothing left for the restore to override.

**AND THE FIX IS BOUNDED — measured, not grepped.** Fixing only what a probe happened to reach is how a
class of defect survives in the pages it missed, so I swept the roster for the same shape. A text search
for `if (!WORKER_NAME) { location.href … }` alongside an un-awaited restore accused **13 more pages**:
hive, logbook, inventory, pm-scheduler, project-manager, dayplanner, analytics, alert-hub, skillmatrix,
shift-brain, community, resume, analytics-report.

**Every one of them was innocent.** Driving the identical defect condition — live session, identity cache
cleared — through all 13 live:

```
hive · logbook · inventory · pm-scheduler · project-manager · dayplanner · analytics
alert-hub · skillmatrix · shift-brain · community · resume · analytics-report
                                              -> all 13 STAY.  Bounces: none
```

Carrying the syntactic pattern is not the same as having the defect: on those pages the check does not run
before the name is resolved. **Had I trusted the grep I would have edited 13 files that were working**, and
each edit would have staled that page's bank rows for nothing. The same procedure that clears these 13 is
the one that convicted the other three, so it discriminates — which is what makes the negative result worth
as much as the positive one. The defect was 3 pages; all 3 are fixed; the class is closed.

---

NEXT: FINISH ALL OWED (A11) — to owed=0/stale=0.

**★ PRIORITY, set by Ian 2026-08-14: CHASE THE OWED, NOT THE STALE.** A stale row was earned once and can
be re-earned by re-running its prover; an OWED row has never been walked at all, so it is the only kind
that represents an unasked question. The re-walk chain has already returned green 501 → 857 (stale
1431 → 1075), and that is enough of that axis for now.

Owed by family, largest first: **CN 330** (entirely unwalked — 0 green, 0 stale) · CM 254 · CO 245 ·
CK 226 · CC 218 · CF 192 · CI 176 · CB 171 · CE 170 · CG 143 · CL 114 · CA 103 · CD 96 · CJ 30.

**DONE THIS TURN (2026-08-14), against the owed-first priority:**

| family | before | after |
|---|---|---|
| **CN** ux-journey | 330 owed, **zero walks ever** | **243 banked green, 0 findings** — all five journeys |
| **CM** `reward_explained` | owed | banked; 3 findings + 15 pages recorded not-applicable |
| **CM** `why_refused` | 15 findings | **16/16 pass** after the central read-refusal surface |
| **CC** failure-injection | 218 owed, marketplace-only coverage | prover built; 20-page sweep in flight |
| **CK** ui-state | 226 owed, ungrounded | **9 of 66 components confirmed live**, 21 rejected with reasons |

**Bank: 23.9% → 31.5%** (green 775 → 1018).

**Five product defects fixed and verified, each bounded rather than assumed:**
1. read-refusal silence — 13 of 16 pages said nothing under a 42501; now all 16 name permission
2. identity-restore bounce — 3 pages; **13 further suspects measured and cleared**
3. anon-key edge calls — 3 of 4 calls in 1 of 4 flagged files; the innocent survivors commented so the
   next grep does not regress them
4. transport-failure silence — rejected/aborted reads produced no `res`, so the morning's own fix skipped
   them; found by the CC oracle's first honest run
5. `report-sender` has no confirmation on the one irreversible action — **recorded for Ian, not guessed at**

#### ★ WHAT THE WALK CONFIRMED IS *WORKING* — recorded because a bank that only ever finds defects is measuring its author's suspicions

Four results this turn were clean, and each is a real property of the product rather than an absence of
evidence. They are listed with their denominators, because "no findings" is only meaningful next to how
much was actually looked at:

| claim | evidence |
|---|---|
| **401 and 403 are never conflated** | 16 of 16 graded pages answered an injected 42501 without blaming identity. `utils.js:1607` `whIsAuthFailure()` returns FALSE for 403 — *"authenticated, and refused. Not a session problem"* — and that discrimination held everywhere |
| **Every rendered number names itself** | 22 pages, **148 number-bearing elements, 148 labelled, 0 unlabelled**, `ctl=ok` (the prover's own control) on every page |
| **The journeys hold** | CN: 243 rows banked, **0 product findings** across five journeys × 22 pages × 3 grounded personas |
| **The edge function was innocent** | suspecting `send-report-email` of a client-supplied `hive_id` hole was wrong — it verifies membership, and its own comment records the phishing-relay hole it had already closed. The defect was entirely client-side |

Two of those denominators vary sensibly by page (analytics 62 numbers, inventory 14, `voice-journal` 0),
which is what separates a measurement from a vacuous pass — and `voice-journal`/`assistant` rendering zero
figures was independently corroborated by CN's `two_sided` oracle finding no shared id-bearing numbers on
the same two pages. **Two instruments agreeing on one structural fact is a confidence signal for both.**

**NEXT, largest owed first:** CC's remaining 3 modes (`fail_partial`, `fail_slow`, `fail_null_field`) and
its V2 view · CO 245 · CK 226 (needs the other 57 components grounded live — the source-parse shortcut is
proven unsafe) · CF 192 · CI 176 · CB 171 · CE 170 · CG 143 · CM `what_happens_next` (66, needs writes).

**★ CK's OBSTACLE, GROUNDED BEFORE ATTEMPTING IT (2026-08-14).** CK ui-state is the next largest owed
family (226), and its rows are keyed by COMPONENT rather than by view — so a prover needs to find each
component on the page before it can assert anything about its loading / skeleton / disabled / busy /
populated states. Measured across all 22 anatomy files: **66 components, of which only 8 carry a
`#selector`. The other 57 are recorded as `file:line` only.** A source line number cannot be queried in a
browser, so CK is not walkable as it stands, and no amount of prover cleverness changes that — the missing
piece is *grounding*, not code. The move is the build-the-structure one: resolve each component to a live
selector (the way `tools/dialog_targets.mjs` did for the 43 V2/V3 views, which is exactly why four provers
can now share it), then walk. Attempting CK before that would produce "component not found" for 57 of 66,
which is a finding about the anatomy, not the product.

**AND THE CHEAP SHORTCUT WAS TRIED FIRST, AND FAILS — recorded so nobody (me included) trusts its output.**
The obvious move is to parse the selector out of the source line each component cites. Done across all 66:
**26 yielded a candidate, 40 yielded nothing** — and the 26 cannot be trusted either, because the two
failure modes are visible in the first handful:

- `community C3 reaction bar` → `.reaction-btn${d.mine` — a **template-literal fragment**, not a selector.
  The line is JS building markup, so the "class" harvested is half an interpolation.
- `dayplanner C2 item modal` → `#dp-week-hero` — a **different element entirely**. The ±2-line window
  caught a neighbouring id, and nothing about the result announces that it is wrong.

Source PROXIMITY is not identity. A line number says where a component was written, not what it renders,
and a scraped selector that silently names the wrong element is worse than no selector — it would send a
CK prover to assert loading/skeleton/busy states against an unrelated node and report the results with
full confidence. So the grounding has to be **live**: enumerate what each page actually renders and match
the anatomy's component names to real nodes, exactly as `dialog_targets.mjs` was built by opening each
dialog rather than by reading about it.

#### DONE — `component_targets.json`: 9 of 66 CONFIRMED, and every step of the funnel earned its cut

`tools/ground_components.mjs` inventories all 22 pages live (**228 repeated structures + 483 id-blocks,
0 errors**). Its own first version was wrong in a way worth keeping: ranking candidates by how often a
class repeats returns `.flex.items-center` and `.text-white/80`, because on a utility-CSS page **the most
repeated class is the framework, not the product** — none of logbook's three components appeared at all.
Ranking by MEANING instead (a `data-*` hook first, then semantic class names, utilities filtered) surfaces
`.card` → *"Log a Repair 1 2 3 STEP 1: MACHINE & TYPE"*, which is the capture form.

| stage | left | what it cut |
|---|---|---|
| components in the anatomy | 66 | — |
| name-token match proposed | 30 | — |
| **a BUTTON is not the component it opens** | 15 | `#asset-picker-btn` for "parts picker"; `#project-print-btn` for "project row" |
| **a row/tile/card must REPEAT** | " | `#ah-card-anomaly` for "anomaly signal row" |
| **a row under 20 chars is a label INSIDE it** | 11 | `.badge` → *"BEARINGS"* for "part row"; `.alert-icon` for "alert row" |
| **confirmed LIVE, then read** | **9** | `.sc-hero` → *"1"*, kids=0; `.starter-chip` → *"Which of my assets has the worst MTBF…"* |

**★ THE LAST CUT IS THE ONE TO REMEMBER: RESOLVING IS NECESSARY, NOT SUFFICIENT.** All 11 survivors
resolved live — visible, right shape, right instance count. Two were still the wrong component. `.sc-hero`
is the *number inside* a "verdict hero trio"; `.starter-chip` is a suggested-QUESTION chip, not the
"source/provenance chip" it was bound to — same word, different component. Only carrying the SAMPLE TEXT
alongside each binding made that visible. Stopping at "11 of 11 resolve" would have shipped two bindings
that send a CK prover to assert busy/loading against the wrong element, confidently.

So: **9 bound and confirmed, 21 rejected each with its specific reason, 36 never matched** — the last two
groups explicitly flagged as needing a live look, never a later guess filled in from this file. A sixth of
CK grounded properly beats all of it grounded plausibly, and the 21 recorded rejections are what stop the
next pass from re-proposing the same wrong answers.

Then: CM `what_does_it_cost` (59), CC failure-injection (218), CF ufai-F (192).
  Most-owed oracles (gate-counted, across 22 pages): CK component_disabled 22 · CK component_busy
  22 · CM why_refused 22 · CK component_loading 21 · CK component_skeleton 21 · CM
  what_is_this_number 21 · CM what_happens_next 21. The CK block is the next unit and it is
  INTERACTION work, not measurement: a component must be DRIVEN into loading / skeleton / disabled
  / busy and observed there, which is why it is the largest untouched family.
  Then CM comprehension, then F1 (1,320) and F2 (1,100), which need psql, forged-identity probes
  and injected failures rather than the browser lenses.
  ★ SECOND COMPLETE FAMILY: `CL contrast_wcag` V1 is GREEN ON ALL 22 BANKS, 0 owed (verified by
  enumerating the row in every bank, not inferred from a total). It was the most-blocked oracle in
  the arc — refused on four pages twice over — and it closed only after two real lens bugs were
  fixed. logbook's MINE-mode note is also CLOSED: contrast_apca there was already green at 205
  nodes, and MINE is reached via #btn-view-mine, not a "MINE" tab.

  ── THE ABSTENTION LEDGER (2026-08-06) — HOW THAT FAMILY WAS CLOSED ──────────────────────────
  Two lens changes made this measurable. (1) `visual()` now stamps every measured node with
  `data-wh-apca` (exposed as `apca.measuredMark`), so an axe abstention is dispositioned by SET
  MEMBERSHIP, not by count — which mattered: selector intersection said 145/249 covered on logbook,
  the stamp says 216, because nth-of-type paths under-report (219 rows resolve to 150 distinct
  elements). (2) The emoji filter was excluding ASCII DIGITS — `\p{Emoji_Component}` matches 0-9 —
  so every numeric-only label platform-wide went unmeasured while axe also abstained on it, meaning
  nobody had judged it. Both fixed and self-tested; denominators rose (logbook 219→221, hive →265,
  alert-hub →273) with 0 new failures.

  Measured with the lens's EXACT `SHARED_CHROME` list (an earlier pass omitted `#wh-guide-link`
  and `.wh-skip-link` and so mis-labelled 2 nodes on every page):
    assistant           20 abstentions · 18 accounted ·  2 un-judged: "Setup", "Hi Pablo Aguilar!…"
    engineering-design  48 · 46 ·  2: "🔧 Mechanical 4", "🔥 Fire Protection 5"
    inventory          134 · 125 ·  9: "All stock", 8× "Bin N-X"
    logbook (MINE)     249 · 227 · 22: "Voice Journal", "CSV", "All categories", 18× "Knowledge"
  Accounted = measured by the lens, OR a container whose measured leaf child holds the text, OR
  single-character text under the documented `length > 1` rule, OR shared chrome excluded by scope.
  axe reports 0 contrast VIOLATIONS on all four; the lens reports 0 failing on all four.

  ROOT CAUSE FOUND — THE LEDGER IS NOW COMPLETE, and it is a SECOND real lens gap, not a mystery.
  Measured: of logbook's 22 un-judged nodes, `visibleAndLeaf` is **0** — every one has 1+ client
  rect, `visibility: visible`, no hidden ancestor, no closed `<details>`, and is **NOT a leaf**
  ("Voice Journal" childCount 1, "All categories" 8, "CSV" 1, 18× "Knowledge" 1). So the earlier
  vis()/zero-rects hypothesis is REFUTED: they are visible.
  The lens filters `el.childElementCount === 0`, i.e. leaves only. These nodes carry their OWN text
  node ALONGSIDE an element child — the ubiquitous icon+label shape `<span><svg/>Knowledge</span>`
  or `🔧 Mechanical 4`. The container is skipped for having a child; the child is an icon holding no
  text, so it is skipped too. **The label is therefore measured by NOTHING**, and axe abstains on it
  as well, so no instrument has judged it. Same failure family as the digit bug: an EXCLUSION rule
  quietly removing real text from the denominator.
  With this bucket named, every abstention on all four pages is accounted for:
    measured by the lens · container whose measured leaf child holds the text · single-char under the
    documented rule · shared chrome · **container carrying its own text beside an element child**.
  The rows still cannot bank — that last bucket is UNJUDGED, not dispositioned — but the reason is
  now understood and bounded.

  DONE — the lens now measures each element's OWN direct text nodes instead of requiring a leaf.
  Self-tested four ways on every page touched: an icon+label IS measured, a pure wrapper is NOT
  (no double-count), a leaf is still measured, a lone pictograph is still excluded. Denominators rose
  again (logbook 221→242, engineering-design 44→51, inventory 124→132, assistant 11→13) with **0
  failing everywhere** — so both bugs were under-MEASUREMENTS, not masked failures. Final ledger,
  every abstention on all 22 pages now accounted: assistant 20/20 · engineering-design 48/48 ·
  report-sender 11/11 · resume 55/55 · shift-brain 143/143 · skillmatrix 29/29 · voice-journal 65/65 ·
  logbook 247/249 · inventory 133/134. The 3 remainders are `<select>` elements whose `textContent`
  is their `<option>` list — never painted, a reasoned exclusion, the same judgement already applied
  to a lone emoji glyph.
  WHAT HAD NEVER BEEN CHECKED BY ANY INSTRUMENT until this fix: inventory's 8 `Bin N-X` shelf labels,
  engineering-design's `🔧 Mechanical 4` discipline chips, skillmatrix's badge totals, voice-journal's
  `🧭 Zaniah · Strategy` persona row, and every numeric KPI figure on the platform.

  ★ PLATFORM-WIDE VERIFICATION AFTER THE FIX (the check that matters, since widening a detector is
  exactly when it should start finding things): all 22 pages re-measured with the corrected lens —
  **0 failing and 0 inconclusive on every one**, over ~2,547 measured text nodes in total.
    index 103 · hive 269 · logbook 50 (TEAM default; 242 in MINE) · inventory 132 · pm-scheduler 125
    project-manager 65 · dayplanner 202 · asset-hub 213 · analytics 267 · alert-hub 282
    skillmatrix 60 · shift-brain 151 · voice-journal 59 · assistant 13 · community 122
    public-feed 72 · achievements 139 · engineering-design 51 · resume 55 · report-sender 69
    project-report 31 · analytics-report 17 (pre-generation form)
  So the platform genuinely passes APCA on the widened denominator: the two bugs were hiding
  MEASUREMENT, not failures. That also means the `contrast_apca` rows banked earlier were true —
  just measured over a smaller set — and their evidence is strengthened, not invalidated, by this.
  Note for anyone comparing numbers: logbook's default TEAM view yields 50 nodes; only MINE (via
  #btn-view-mine) gives the real 242, so always name the view when quoting this page.
  Do NOT hand-roll their contrast as a shortcut: an ad-hoc probe that discards alpha reported
  white-on-white Lc 0 for plainly-legible labels, because `.text-white/80` over an
  `rgba(255,255,255,0.1)` tint needs real compositing — which the lens already does correctly at
  live-state-runner.js:689 (`_overlay` + `_effectiveBg`).
  index V3 sign-in modal: "Sign Up" Lc 54.3 and "Sign In" Lc 56.8 at 14px against floor 60 — a
  real unfixed defect found while diagnosing the dead-fixture batch.
  AUTHORING DONE 2026-08-05 (this arc, all in one session):
    · multi-bank validator: process_bank() per registry, per-bank baseline {"banks":{...}} with
      legacy flat shape read as marketplace; classify()/R1-R7/ratchet untouched. Marketplace's
      674<752 red pre-exists this arc (the parallel walking session's stale drift — its unit).
    · tools/build_page_live_mcp_bank.py — fixed 200-frame (60/50/45/45), ORACLES imported from
      build_live_mcp_registry (one vocabulary), A7/A8/A10 + strict-oracle selftests all fire.
    · page_bank_anatomy/*.json x22 — every subject carries seen{how,ref}; 308 bespoke oracles
      (6 invariants + 8 domain truths per page); writes classified per the Y1b disposition.
    · banks/*_live_mcp_bank.json x22 — 22 x 200 = 4,400 rows, ALL owed, 0 invalid, 105 declared_na
      recorded with receipts, 10-row random spot-check traced clean.
  GROUND CORRECTIONS BANKED DURING AUTHORING (the substrate beat my greps 5 times):
    · pm-scheduler reaches embed-entry via RAW fetchWithTimeout (:2279) — bypasses functions.invoke;
      same pattern on resume (:1140) and skillmatrix (embedSkillEntry). THREE pages bypass the
      shared invoke wrapper = a cross-page walk target.
    · the compliance window is 90d (p_period_days:90 at pm-scheduler:1386), not 30d.
    · report-sender's transport IS known: send-report-email + scheduled-agents + voice pair
      (voice-report-intent/voice-transcribe) + resendReport. A7 hold resolved from substrate.
    · alert-hub writes amc_briefings.update + anomaly_signals.update (not automation_log).
    · inventory stock rule sharpened: qty_on_hand == newest txn qty_after via inventory_deduct/
      inventory_restock RPCs (ARC DI 10.5 seesaw).
  REMAINING A7 HOLDS (rows exist, cannot bank green until re-grounded live): analytics chart
    sources · assistant panel ids · resume anon-upload persona.
  SHARED-COMPONENT COHORT (walk once, assert three times): an-/ah-/sb- verdict chrome on
    analytics / alert-hub / shift-brain.
  SUITE VERDICT AT ARC CLOSE (fast suite, 2026-08-05): 566 PASS · 14 FAIL · 155 SKIP.
    Both REGRESSIONS in this arc's window were cleared the same session: substrate freshness
    (rebuilt -> 786 chunks fresh, PASS) and storage-key registry (transient of the parallel
    walking session's mid-edit state; exits 0). The remaining 12 standing FAILs (em-dash on 8
    learn pages, etc.) PRE-DATE this arc and sit in the full-gate drive Ian explicitly deferred
    to the marketplace walk's arc close ("reserve the full gate until the walk is done",
    2026-08-04) - named here so the deferral is a record, not a silence.
```

---

## §5 · OPEN FOR IAN

- Nothing new. The two §5 blocks in `MARKETPLACE_ITERATION_ROADMAP.md` are settled by recall for
  THIS arc's authoring: the APCA "273/552" figure predates the corrected floor table in
  `live-state-runner.js` (re-measure, then decide); offline-write posture follows the Y1b
  disposition principle (capture queues; financial/approval/role writes refuse with clarity), and
  each anatomy's `writes[]` is classified accordingly.
- Ian's standing gates: commit/push, prod deploys.


---

## §6 · SYNTHESIS FROM THE OFFLINE ARC (2026-08-18) — the frame needs an `offline_queued` cell

**The measured claim:** the CG-ufai-A family gives every view an `offline_refusal` cell and **no
`offline_queued` cell**, so a queue-backed surface has no slot that fits its correct behaviour. Eight of
the twenty-two roster pages register an offline write queue — roughly a third of the roster.

**The oracle, as worded:** *"offline, the write is refused before firing and the person is told nothing
was sent."* For a field-capture write that is the WRONG requirement, and both verdicts are wrong: green
credits a refusal that must not exist, red calls a working feature a defect.

### The eight queue adopters, read from their own `whCreateQueue` registrations

| page | queued table | queue db |
|---|---|---|
| `logbook` | `logbook` | `wh_logbook_offline` |
| `inventory` | `inventory_items` | `wh_inventory_offline` |
| `pm-scheduler` | `pm_completions` | `wh_pm_offline` |
| `dayplanner` | `schedule_items` | `wh_dayplanner_offline` |
| `asset-hub` | `rcm_fmea_modes` | `wh_assethub_offline` |
| `community` | `community_posts` | `wh_community_offline` |
| `project-manager` | `project_progress_logs` | `wh_projectmgr_offline` |
| `skillmatrix` | `skill_profiles` | `wh_skillmatrix_offline` |

Two of these registrations live on a **window handle** (`window._whCommQueue = window.whCreateQueue({…})`),
so a detector that greps for a `table:` key per page misses them. Grep `whCreateQueue` and
`window._wh*Queue`.

### Why page-level classification is the wrong granularity

`inventory` settles this on its own: the part **create** queues (`_whInvQueue.enqueue` →
*"Saved offline, will sync when you reconnect."*) while the part **delete** refuses (measured live: 0
`inventory_items` requests + the refusal sentence). Same page, same table, two classes. `community` is
the same: `community_posts` is queued, yet `deletePost`, `togglePublic` and `submitReport` touch that
table with no queue branch and are correctly refused — only `submitPost` enqueues.

**So the test is per-FUNCTION, not per-page:** does *this* function contain a queue path?

> Getting this wrong is not theoretical. During this arc a refusal was added above `submitPost`'s queue
> branch, which removed working offline posting. Caught, reverted, and re-proven live (0 server POSTs, the
> queue toast fires). The same mistake was one edit away on `submitCompletion`, where it would have taken
> offline PM completion from a technician in a basement.

### Proposed cell

`offline_queued` — *offline, the write is HELD, the person is told it will sync, and it drains exactly
once on reconnect.* Assert: (1) zero server writes while offline; (2) the queue message reaches the
person; (3) the record is visible immediately from the local cache, marked pending; (4) on reconnect it
drains **once** — `logbook`'s edit path already implements this by re-queueing via `put()` on the id
keyPath, which replaces the pending insert rather than adding a second.

The `writes[]` classification in each page anatomy already carries the capture-vs-locked posture, so
which cell a view gets is derivable from data the anatomies hold today.

### Instrument built by this arc

`tools/prove_offline_refusal.mjs` — 13 cases, 10 live-PASS. Three things it had to learn, each of which
had produced a false verdict:

1. **`context.setOffline(true)` does not flip `navigator.onLine`** inside the page, so a guard written
   against it never fires and the probe blames the page. Override the property *and* cut the network.
2. **A refusal lands wherever that form's other refusals land** — `#sheet-error`, `#email-error`,
   `#wh-toast`, `showAmcMsg`. Reading a fixed id list called two guarded pages silent.
3. **Anchor the message check on `whOfflineMessage`'s distinctive tail**, not the word "offline".
   Several pages render a passive banner (*"You are offline. Some actions may not work."*) at the same
   time, and that banner is exactly what this oracle must not accept.

Two blind spots were also fixed in the registered `tools/validate_offline_write_guard.py` (selftest still
passes all four cases): its `GUARD` regex matched `navigator.onLine === false` but not `!navigator.onLine`
— the idiomatic form — and its `READ_ONLY_RPC` exemption list held two names, so read-only RPCs counted as
writes.


### §6a · A cohort drift closed on the way past (2026-08-18)

Grading `shift-brain` V2 meant reading its verdict-summary CTA, and that surfaced a live divergence in the
**shared executive-summary chrome** the roadmap already flags as a cohort (`analytics` `an-` /
`alert-hub` `ah-` / `shift-brain` `sb-`, each with `-verdict`, three hero cards and an `-action-btn`).

`analytics` had already been fixed; the other two had not. Its `setCta` gives the CTA a **real fragment
href**, with the reasoning written in place:

> An on-page CTA gets a REAL fragment href, not `"#"`: the browser already jumps to the target with zero
> JS, and the handler below only upgrades that to a smooth scroll. `href="#"` would strand the button if
> the script ever fails, and reads as a dead link to a11y tooling.

`alert-hub` and `shift-brain` still did `setAttribute('href', '#')` and relied entirely on the JS handler.
Ported to both. Verified live — each CTA now carries a fragment whose **target actually exists**:

| page | href | label | target resolves |
|---|---|---|---|
| `analytics` | `#phase-tabs` | Open the Predictive tab → | yes |
| `alert-hub` | `#feed` | Clear 51 critical/high → | yes |
| `shift-brain` | `#carry-list` | Clear 9 carry-forward → | yes |

**Why this belongs in the record rather than a commit message:** three copies of one component is exactly
what let the marketplace's credits chip drift, and this is the same shape — one copy improved, two left
behind, with nothing to notice the gap. The cohort is the unit of maintenance, so a fix to one is a
question about the other two.

**And it settles those three views' `offline_refusal` rows too:** the CTA is pure navigation
(`preventDefault` + `scrollIntoView`), so the verdict-summary views have **no committing write** and the
refusal oracle has no subject there. Recorded on `shift-brain` V2; `analytics` and `alert-hub`'s
equivalent views inherit the same conclusion from the same implementation.


### §6b · The exposure sweep read only `.html` (2026-08-18)

The roster scan that drove this session's `whRequireOnline` adoption globbed `<page>.html` and nothing
else. `engineering-design` therefore scored **`reachable = 0` user-triggered writes** while
`engineering-design.js` held **three**: two `engineering_calcs` inserts (`saveCalc`, `saveWithBomSow`) and
a hard `delete` (`deleteCalc`). All three fired into a dead network with nothing said.

**A coverage measurement is only as wide as the files it opens.** The page's own `writes[]` anatomy in §4
lists them correctly — the scan simply never looked where the anatomy pointed.

Guarded and verified live: 0 `engineering_calcs` requests, *"You are offline. Saving this calculation
needs a connection - nothing was sent, so nothing is half-done."*, and the Save button left **enabled**
(the refusal precedes the in-flight state, so it cannot strand the control).

`deleteCalc`'s guard is placed **before** its confirmation dialog: this is a hard delete with no
soft-delete column and no restore path, and `project-manager` joins `engineering_calcs` through
`project_links` as a project's evidence — asking someone to confirm destroying that and only then failing
is the worst available order.

**Still unswept, and worth a pass:** other `.js` files carrying `db.from(...)` — `companion-launcher.js`,
`companion_battery.js`, `companion_surface_battery.js`, `device-fingerprint.js`, `maturity-gate.js`. Most
are best-effort telemetry where a silent offline drop is defensible, but that is a judgement to make per
file rather than a gap to leave unexamined.


### §6c · A fixture-opened view can be graded for PRESENTATION, never for its DATA PATH (2026-08-18)

Correcting `resume:V2`'s false `notDrivable` claim made the review sheet reachable, and four provers
graded it immediately. Then `prove_failure_injection --page resume --view V2` returned 6 PASS / 1 FAIL —
and **none of the seven was bankable**.

Every cell reported `healthyChars = 204` **and** `badChars = 204`. The view renders identical content
whether the reads succeed or all of them fail. That is not resilience; it is **immunity**, and it is an
artifact of how the view opens: the registry drives it through
`window.WHResume.openReview(title, items, onConfirm)` with **fixture items**, so the sheet's content comes
from the harness, not the network.

- The six passes are **vacuous**: *"rendered no false empty state"* is trivially true of a view that cannot
  be emptied by the injection.
- The one failure is **harness-made**: `fail_slow` found no busy indicator, but nothing in the sheet was
  loading — the fixture had already painted it.

**The rule.** An oracle that grades the **data path** — failure injection, `count_matches_source`,
`effect_visible`, `cross_surface_agreement` — cannot be settled on a view whose content the fixture
supplies. The injection and the view must share a data path, or the reading says nothing in either
direction.

**The counter-rule, which matters just as much.** An oracle that grades **presentation** — layout,
overflow, tap targets, focus rings, reduced motion, accessible names, whether a number is labelled — *is*
settleable on a fixture-opened view, because the fixture supplies the VALUE while the page supplies the
label, the layout and the behaviour. `achievements:V3` is the worked example: opened with
`showLevelUpModal(<key>, 2, false)`, its 16 green rows are structural or presentational, and its
`reward_explained` row reads 22 real figures out of `ACHIEVEMENT_DEFS`. **Those greens are sound and were
audited rather than assumed** — the audit's purpose was to find false greens, and it found none.

So the exposure is narrow and nameable: of 8 `openBy: 'fn'` targets, only **2 carry a data payload**
(`resume:V2`, `achievements:V3`), and only their data-path oracles are at risk. resume V2's seven CC rows
carry this reasoning; achievements V3 has no CC subject.

**What resume V2 needs for the CC family:** its real pipeline — upload a file, let `resume-extract` answer,
and inject on *that* call, so the checklist the sheet renders is the thing that fails. That path writes
(`resume_documents`) and calls an AI edge function, which is why the registry once called the view
unreachable outright. The honest version: reachable read-only for **structural** oracles, real pipeline
required for **data** oracles.

---

## §6d · CONTRAST — the page-level sweep that settled nothing, and the three defects the view-level one found

**Measured 2026-08-18.** 78 contrast rows were owed (`contrast_wcag` 44, `contrast_apca` 34), behind a
recorded belief that contrast "is not computable from CSSOM here." That belief was true of the naive
probe that produced it and false of this platform's instruments, which had already solved every part of
it: `live-state-runner.js::visual()` composites alpha up the ancestor chain, averages gradient stops,
resolves `background-clip:text` glyphs to the gradient's first stop, keeps numeric labels while dropping
emoji-only ones, scopes to `document.body`, and reports its own candidate count. **The move existed; the
ceiling was in my memory, not in the code.**

**The scope error that nearly wasted the whole build.** `tools/prove_page_contrast.mjs` measured all 22
pages populated and signed-in, and found them clean. It settled **zero** owed rows: every owed contrast
row is authored against **V2/V3**, and their V1 siblings were already green. A clean sweep at the wrong
scope is not evidence of health. `tools/prove_view_contrast.mjs` opens each view through the shared
`dialog_targets` registry and measures inside it — and immediately found **three failing views**:

| view | defect | fix |
|---|---|---|
| `logbook V2` | `.btn-danger` label `rgba(239,68,68,0.8)` → composited `rgb(201,62,66)`, **APCA Lc 24.5 / 30** | adopt `--wh-red-text` |
| `engineering-design V2` | Delete ×4 inline `rgba(239,68,68,0.7)`, **Lc 19.6 / 60 AND WCAG 3.92 / 4.5** | adopt `--wh-red-text` |
| `engineering-design V3` | **2 of 2 samples** — heading `#F7A21B` (Lc 58.2/60), body `rgba(255,255,255,0.5)` (Lc 40.8/60) | `--wh-orange-text`, `0.85` |

> **The most destructive control on two surfaces carried the least legible text on them.** Every fix was
> adopting a token `tokens.css` already shipped and annotated *"this token is for TEXT only"* — fills and
> borders keep the strong hue. Three more were found at page level and fixed the same way: a `0.3`
> placeholder token (measured: `0.7` is the minimum that clears; the platform's own majority is `0.80`),
> hive's severity chips painting 10px text in the **fill** hue, and community's initials chip using a raw
> `#49c1df` where `--wh-blue-text` existed.

**What is NOT bankable, and why it is not a ceiling.** 17 `contrast_wcag` rows yielded **zero measurable
samples**: the dialogs' cards are a translucent gradient over a translucent scrim, so WCAG 2.x — a ratio
between *two* colours — has no second colour to use. Verified by tracing the paint chain, not assumed.
Their APCA siblings measured normally, which is why APCA is the primary contrast oracle on this shell.
These are recorded unmeasurable **with the replacement named** — sample the rendered pixels around each
glyph from a screenshot — and stay owed until that is built.

**Instrument teeth, measured not asserted:** driving logbook's real page through the lens gave **0/44
failing at baseline, 36/44 under a forced muted grey, 1/44 under forced white**, denominator stable at 44.

**Result:** contrast owed **78 → 37** (41 green, 17 diagnosed-unmeasurable, 20 in views that do not open).
Page banks **green 3008 → 3049**.

**NEXT here:** the 20 unreachable views (`index V2/V3`, `hive V2`, `assistant`, `analytics-report`,
`alert-hub V3`, `project-report V3`, `voice-journal V3`) need registry open-paths or honest
`notDrivable` reasons; then the pixel-sampling prover for the 17.

### §6d-ii · The 17 "unmeasurable" rows were measurable all along — by the move already in the file

I recorded those 17 `contrast_wcag` rows as needing a **new pixel-sampling prover**: screenshot the view,
sample rendered pixels around each glyph. That replacement was never built, because it was never needed.
`_effectiveBg()` — the function that lets APCA measure inside these dialogs — **already resolves a
gradient backdrop** by averaging its stops. The standalone composited probe abstained; the lens sitting
next to it did not. So `visual()` now emits a `wcag` sibling computed from the **same node set, the same
composited foreground and the same resolved background** as its APCA verdict — one reading, two floors —
and the two lenses can no longer disagree about *what* they measured, only about the verdict.

> **Twice in one stretch I named a ceiling that the codebase had already climbed.** First "contrast is not
> computable from CSSOM here"; then "these rows need a screenshot prover." Both were true of the probe in
> front of me and false of the platform. **Check what the neighbouring function already does before
> specifying its replacement.**

**That the two lenses disagree is the point, and it immediately paid.** `live-state-runner.js` documents a
known gap in the APCA Lc 30 tier — 11px bold chips once scored Lc 42.1 (pass) and WCAG 2.26 (fail) — and
states plainly: *"the WCAG check is the backstop for small text … if this lens is ever run alone, sub-14px
text is its blind spot."* Inside dialogs that backstop had been **absent**. Switched on, it found **17
failures APCA passed**, every one 8–12px:

- `asset-hub` — **"Compute Weibull fit"**, a real CTA, 4.05:1
- `index V2` — 16 stage-card chips, 3.36–3.67:1, again the **base brand hues** where `-text` variants
  existed, plus an `opacity:0.7` sitting *on top* of the token that the lens cannot see at all (computed
  `color` excludes element opacity, so the rendered contrast was **worse than the number**)
- `index V2` — the four **"The gap:"** lines, `text-red-300/70`, 4.38:1 — body copy carrying the page's
  core argument, dimmed to 70%

**Teeth, inside a dialog:** `#part-modal` measured **0/61 failing at baseline, 52/61 under injected grey**
— where the standalone probe measured **0 of 0**.

**Result:** contrast owed **78 → 16**, green **116**. Page banks **green 3070 · owed 1330**, gate PASSES,
22/22 pages parse clean. The remaining 16 are the 8 view-pairs whose `notDrivable` reasons were
**independently re-verified live this stretch** (`ar-exec`/`ar-predictive` absent until a report is built;
`#anomaly-engine-panel` `display:none` with no fused anomalies; `#chat-messages` open but standing in for
a data-concept view) — reasons that were already correct, not gaps.

### §6e · Two quantity columns carry their unit only by convention — one of them is MONEY

`tools/prove_units_at_boundary.py`, run over the live schema: **80 unit-bearing quantity columns
examined, 73 declared, 0 mixing two scales, 2 UNDECLARED-live, 5 undeclared-latent.**

| column | kind | what is missing |
|---|---|---|
| `service_credit_ledger.amount` | **money** | no CHECK, no comment, no sibling unit column, and a name that does not carry the unit |
| `conversation_analytics.answer_quality_rating` | percent | same — is it 0–1 or 0–100? |

A money column with no declared currency is the `units_declared` oracle's own worst case: two readers can
agree on the number and disagree on what it is worth. It is reported as **debt, not as a failure**, which
is the right call — nothing mixes two scales today, and the prover says so plainly rather than reddening
on a latent risk.

**Deliberately NOT fixed by a migration in this stretch.** The fix is a `COMMENT ON COLUMN` or a CHECK,
which is a schema change — and a migration **expires every db-anchored claim in the bank** (a previous one
took it 900 green → 395). Paying that re-walk cost is Ian's call to make on his own schedule, not a side
effect of a documentation fix. Recorded here so the decision is his and the finding is not lost.

### §6f · Where the remaining owed rows actually are

`name_survives` banked 32 of 39 on a run that checked **1612 literal field names against the live catalog
(2703 columns) across all 22 pages, with an injected `wh_column_that_cannot_exist_logbook` caught** — a
green from a checker that has not shown it can go red is a green about nothing.

The seam filter for that family had to be **inverted**, and the reason generalises: an *inclusion* list
keyed on the word "db" banked 2 rows and left 37 owed that the run had genuinely covered, because seams
like `achievements ↔ community (community_xp)`, `logbook ↔ pm_completions` and `calc ↔ saved record` all
carry named DB columns without saying "db" in their titles. **Too strict is its own kind of dishonesty —
just a quieter one than too loose.** Only genuinely non-DB seams (print render, chart mark, CDN script,
PDF export, audio transcript) are left owed.

`source_chip_true`: 41 views graded, **18 true, 23 make no claim, 0 name a feed they never read** — and
"makes no claim" is *not* banked as a pass, because a surface that promises nothing has not kept a
promise. Most of the 23 are V2 dialogs that state no derived figure; each needs the per-view question
answered rather than guessed.

`abandon_resume`: the 16 reachable composers were already green; the remaining 50 pairs have **no composer
for that identity**, recorded as *unbuilt* rather than passing — a journey that cannot be constructed must
never score green, since "nothing half-landed" is trivially true of a surface where nothing can be typed.

### §6g · `count_matches_source` — the pattern, and why each page costs a hand-authored check

`tools/prove_count_matches_source.mjs` extends `tests/surface-numbers.spec.ts` (4 marketplace surfaces)
to the product roster. **It cannot be generic, and the reason is the one §1 already states:** a generic
checker cannot know a surface's truth query, so it ends up asserting the structural half — *a number
rendered, it isn't NaN* — and calling that agreement. Each page therefore costs a hand-authored
`(selector, SQL)` pair traced to the query the page actually issues.

**Two instrument traps caught while building it, both of which would have produced confident nonsense:**

1. **`window.WORKER_NAME` is null** — the identity constants are module-scoped inside the page's IIFE,
   never globals. Reconstructing an identity from a fixture would have been *worse than failing*: it
   asks a different question and reports the difference as a defect. The scope is now parsed out of the
   **PostgREST URL the page actually sent**, so a mismatch can only mean display and DB disagree.
2. **`count=exact` is not in the URL** — it travels in the `Prefer` header. Selecting on it silently
   picked the page's first request (a hive-scoped id list) rather than either count query.

**Scope must be measured, not read.** inventory issues *two* `v_inventory_items_truth` reads; hive+worker
returns **7**, the page shows **27**, so the pills use hive+status. Picking the worker-scoped query
because it looks like the natural identity filter would have banked a 27-vs-7 "defect" that was really
the wrong question.

**A comparison that cannot fail is not evidence — so each check records what it discriminates:**

| check | drop the filter → | actual | caught? |
|---|---|---|---|
| logbook `#total-count` | 3812 | 517 | **yes** |
| logbook `#open-count` | 46 | 6 | **yes** |
| logbook hive clause | 517 | 517 | **no** — every row of this worker sits in that hive; needs a second seeded worker |
| inventory `#stat-low` (naive `qty<=1`) | 0 | 3 | **yes** — a regression to a hardcoded threshold is caught |

That last row is the valuable one: `#stat-low` doesn't just match a number, it **discriminates the domain
rule** that low-stock triggers on the reorder point (`min_qty > 0 AND qty_on_hand <= min_qty`) rather than
a hardcoded threshold.

**Deliberately not checked:** logbook `#machine-count` is `allMachines.size` over the *loaded window*
(logbook.html:3650) — a true statement about the screen, not a claim about the database. Asserting it
against a DB distinct-count would manufacture a failure out of a capped window.

**Status:** 2 of 22 pages authored (logbook, inventory), 5 checks, 0 failing. The remaining 20 follow the
same shape: capture the page's requests, identify which read feeds each number, author the SQL, measure
what it discriminates.

### §6h · A PM asset can go unrepresented, and nothing on screen would say so (latent)

`pm-scheduler`'s three hero pills — overdue / due-soon / on-track — are a **client-side rollup**, not a
query: `getAssetOverallStatus()` ([pm-scheduler.html:1012](pm-scheduler.html#L1012)) folds each asset's
scope items into one status. There is no single truth query to compare a pill against, and replicating
that fold in SQL would risk manufacturing a defect out of my own re-implementation.

**What is honestly checkable is the partition:** every asset must land in exactly one displayed bucket, so
the pills must sum to the hive's asset count. Measured: **28 + 2 + 0 = 30**, and `pm_assets` holds exactly
30 for this hive. ✅

**The latent hole, named rather than left implied.** `getAssetOverallStatus` returns a **fourth** value —
`'nodata'`, for an asset whose scope items are missing — and **there is no pill for it**. The sum is exact
today only because that bucket is empty (0 of 30 assets lack scope items). The first asset that lands
there will vanish from the summary, the pills will quietly total less than the asset count, and nothing
will say a machine went unrepresented.

> On a PM scheduler, that is the asset nobody is told to inspect.

**Settles it:** a fourth pill (or an explicit "N assets have no schedule" line), or a seeded asset with no
scope items so the gap becomes a live finding rather than a reasoned prediction. Recorded as **latent** —
real, not yet triggered — the same discipline `prove_null_semantics.py` applies to a collapse no row has
hit yet.

### §6i · Two "forks" that were never forks — both already answered in the record

I raised two questions as needing a decision. Ian's reply: *"you are forking me right now which you have
memento and you know what to do?"* Both answers were already on disk. Retrieving them took under a minute
each, and both are now closed.

**1 · Achievement XP vs `community_xp` — two ledgers BY DESIGN, so the oracle is mis-specified.**
`community_xp` is written **only** by the `SECURITY DEFINER` trigger `increment_community_xp` — the
community rule is *"XP is awarded by DB triggers, never client"*, and all three client references are
`.select()`. Its purpose is the **Community→Marketplace reputation bridge**: community activity becomes
portable, aggregate-only trust the free marketplace turns into jobs. Achievement XP is a different
currency — earned against `achievement_definitions`, driving levels and badges. Nothing writes either from
the other, and nothing should.

> So `390,064 vs 0` is not a divergence. Asserting they must be equal asserts that a worker's posting
> reputation must equal their maintenance gamification score.

The row stays owed pending a **re-author**, not a product fix. The claim worth keeping is *"`community_xp`
reads the same on every surface that displays it"* — which `prove_cross_surface.mjs` can settle once the
oracle names it. Source: `reference_community_xp_write_hole_and_reputation_bridge`.

**2 · The APCA Lc 30 tier — do NOT re-tune it.** The temptation is to raise the floor for small bold
labels. That is **the same miscalibration this implementation already made once and corrected**: the first
APCA run reported 194 of 232 nodes failing because it used Lc 90 as a floor (Lc 90 is *preferred*, not a
minimum) **and scored sub-14px text, which is outside APCA's published table entirely.**

> The tier is not "too permissive" — it is **out of range**. Below 14px there is no APCA floor to apply,
> so anything it says about 8–12px text is an extrapolation, not a reading.

Those nodes deserve a **legible-size** finding (*is 8px text acceptable at all?*), not a contrast one.
Re-tuning would re-verdict every sub-14px node platform-wide on a number the standard does not define
there, and would resurrect the false-positive storm calibration removed. The gap is covered the way the
platform already intends — **both lenses run on every walk, and WCAG is the backstop for small text**,
which is how this session's 17 sub-14px failures were caught. The deferral comment in
`live-state-runner.js` has been replaced with this reasoning so the next reader does not re-open it.
Source: `feedback_apca_perceptual_contrast_c5`.

**The lesson, which is the expensive part:** I had *both* memories and reached for `AskUserQuestion`
anyway. A question that feels like a design fork is exactly when to run `memento_retrieve` first — the
platform has usually already decided, and the decision is better-reasoned than the one I would have
prompted. See `feedback_i_forked_ian_on_a_question_memento_had_answered`.

### §6j · A silent row cap hides 7 high-severity alerts on the safety inbox

`alert-hub`'s hero reads **"51 high-severity alerts"**. Counting each of its six feeds at source and
applying the page's *own* severity mapping:

| feed | contributes | note |
|---|---|---|
| `v_risk_truth` critical\|high | **0** | the obvious source contributes nothing |
| inventory | **2** | out-of-stock→critical, `qty ≤ reorder/2`→high; the third low-stock item maps to *medium* and is correctly excluded |
| PM overdue | **28** | every overdue asset maps to critical or high |
| `automation_log` failed 24h | **0** | |
| parts staging | **0** | its one recommendation is pending but **expired**, and expired ones are filtered out |
| `v_alert_truth` signature | **20** | ← **but 27 exist** |

**`v_alert_truth` holds 27 signature alerts for this hive — all `active`/`acknowledged`, all
critical-or-high — and the query that fetches them ends in `.limit(20)`.** Seven high-severity alerts are
never fetched, never counted, never rendered, and the hero presents the capped number as the total.

> This is the *"a row cap is not pagination"* class on the surface where it costs most. There is no next
> page, no "showing 20 of 27", nothing. The page's job is to tell a plant what needs attention, and a
> reader has no way to learn that seven more exist.

Compare `voice-journal`, which renders a window of 80 and **says** *"latest 80 of 108"* — the same
situation handled honestly, verified green this session.

**RESOLVED — the off-by-one was a SEVENTH feed.** My reconstruction totalled 50 against a displayed 51, so
rather than keep hypothesising I read the page's own filter chips, which carry per-kind counts:

`All 61 · AMC 10 · Risk 0 · PM 28 · Stock 3 · Staging 0 · Pattern 20 · System 0`

That sums to 61 exactly — the decomposition is the page's, not my reconstruction of it. **The AMC daily
brief is loaded separately from the six-way `Promise.allSettled` I had enumerated**, so there are seven
feeds, not six. With it the hero resolves precisely: `1 AMC + 28 PM + 2 Stock + 20 Pattern = 51`. Stock
contributes 2 of 3 because `whStockSeverity` maps the third to *medium* (`qty ≤ reorder` but
`> reorder/2`) — the shared util the page prefers over inline threshold math so classification cannot
drift from the view. Every number now has a source.

**And the cap is visible in the page's own UI, which strengthens the finding rather than softening it:**
the chip reads **"Pattern 20"** while 27 signature alerts exist. The cap does not merely undercount the
hero — it undercounts the kind chip a reader uses to decide whether to look, *and* the "All 61" total.
Seven high-severity alerts are absent from every count on the surface.

The count row is **banked green on the arithmetic** (61 and 51 are exactly what the seven feeds produce
under the page's own severity mapping); the cap is filed as a separate product finding, because it is a
decision about what to fetch and what to say, not an error in the counting.

**Not fixed, because the fix is a decision:** raise the cap, render "20 of 27", or paginate. All three are
defensible and they change what the page fetches, says, or does. What is not defensible is the current
state, where the number is wrong and nothing says so.

### §6k · `partial_write` — 11 pages can half-write, and nothing has

`tools/prove_write_atomicity.py` asks the oracle in the two halves it actually has, and the split is
worth keeping because banking either half alone would have been wrong.

**Structure — who sequences the write**, read out of `pg_trigger` and `pg_proc` rather than inferred. A
page writing two tables through two awaited client calls has **no transaction around them**: a 500, a
closed laptop or a dead network between the two leaves the first applied and the second missing, and
nothing errors afterwards. A page that writes one table and lets a **trigger or RPC** write the second is
atomic by construction — one statement is one transaction.

**Roster: 11 client-sequenced · 11 single-or-no-write.**

**Ledger — whether a half-write is visible today.** All 14 declared conservation invariants hold against
live data: inventory running balance, no orphan transactions, every reply and every live safety post
carrying its XP award row, no XP row outliving a deleted post unreversed, no staged reservation both
consumed and released, one AMC briefing per hive per shift date, no scope item completed twice, no
project child outliving its project, no cycle in the asset hierarchy.

**So the rows split 21 green / 15 diagnosed.** Atomic-by-construction is green — a half-write there is not
merely absent, it is *impossible*, since there is no second table for a failure to land between.
Client-sequenced is **not** green:

> Nothing is broken today, but *"has not happened yet"* is a statement about this dataset, not about the
> code — the same shape as a latent null-collapse no row has triggered. Banking it green converts absence
> of evidence into a guarantee.

**What makes "client-sequenced" a finding rather than a verdict about the tool:** the control pair
`community_posts → community_post_xp_awards` *is* joined by the trigger `handle_community_post_xp`, and
the detector finds it. A detector blind to that link would report every page as client-sequenced.

**What would settle the 15:** either the second write moves behind a trigger or RPC — which is what the
other 11 pages already do and what the control demonstrates — or a probe interrupts a page *between* its
two calls and shows a ledger invariant catching the half-state, proving the second clause with teeth
instead of by absence.

### §6l · Two instruments, one oracle name — `offline_refusal` and the precedence rule

Driving `live-state-runner.js::availability()` across the product roster returned `offline_refusal: FAIL`
on `hive` — a page whose offline behaviour I had **verified green earlier in this same session**, after
adding guards to six writes (`submitCreate`, `submitJoin`, `performLeave`, `kickMember`, `approveItem`,
`rejectItem`) and running the dedicated suite to 11 PASS / 0 FAIL.

Both readings are honest. They are **not the same question**:

| instrument | what it asks |
|---|---|
| `tools/prove_offline_refusal.mjs` | does **this named write function** refuse when offline, with per-case setup to reach it? |
| `availability()::offline_refusal` | does the **first control matching an ACTION regex** (`act[0]`) refuse? |

The lens picks one control by label — `buy|submit|save|send|post|confirm|…` — clicks it, and checks
whether a write fired into a dead network. On a page with many writes, that is a *sample*, and which
control it lands on is an accident of DOM order. It is a good roster-wide smoke test and a poor verdict on
a specific function.

> **Precedence rule: where a dedicated prover exists for an oracle, it outranks the generic lens, and the
> lens's disagreement is recorded as scope difference rather than as a regression.** Banking the lens's
> FAIL onto rows the dedicated prover settled would overwrite measured, per-function evidence with a
> one-control sample — a false red manufactured by an instrument that was asked a broader question.

**So from this sweep the bank takes `retry_path`, `rate_limit_legible`, `fallback_engaged` and
`slow_honest` — the four keys no dedicated prover covers — and leaves `offline_refusal` to its own
prover.** Each of the four still gets its detail read before banking: the lens reports `ok: null` with a
note when a page never re-queried, and that inconclusive must not collapse into a pass or a fail (its own
comment records reading `retry_path:false / fallback:silentlyStale` on a surface that handles both
correctly, because closure-scoped loaders meant the page never moved).

### §6m · I reported a platform-wide rate-limit gap that does not exist — the precedence rule needed widening

**Retracted:** I wrote that `rate_limit_legible` "fails on 21 of 22 pages" and called it a missing shared
component. **That is wrong, and the bank already held the disproof.**

42 `rate_limit_legible` rows were banked green on 2026-08-09 by a **real induction against the real
limit**: a burst of 400 logbook inserts inside `BEGIN … ROLLBACK` as an authenticated member (role SET,
not just claims). The trigger refused with

> *"You have logged today's free limit (100). Resets at midnight."* — HINT `logbook_daily_user`

which names the limit (100), what was hit (a per-user daily cap, not a system fault), **when it clears**,
and ships a stable machine-readable key so a client can branch on *which* limit fired instead of
pattern-matching English. A second tier — `check_hive_quota_logbook`, SQLSTATE 54000 — is distinguishable
by both message and code and states its remedy (archive old records). Zero probe rows survived the
rollback.

**The platform's rate limiting is legible. My sweep asked a different question**: under a *fake* 429
injected at the fetch layer, does the page's own text name a limit? That is a client-rendering question
about a condition the server never actually produced — narrower, and arguably artificial, since the real
limit surfaces a fully-formed message the page would display.

**So §6l's precedence rule widens beyond `offline_refusal`:**

> Where a dedicated prover exists for an oracle — *especially one that induced the REAL condition rather
> than a simulated one* — it outranks the generic availability lens. A lens verdict that contradicts it is
> recorded as a **scope difference**, never as a regression, and never withdraws the stronger evidence.

**What my run actually did, verified afterwards:** 74 rows gained a diagnosis and stayed owed
(`retry_path` 35, `fallback_engaged` 29, `slow_honest` 10); 25 were banked green where the lens genuinely
passed; **zero `rate_limit_legible` rows were touched**, because none was owed. No false green was
created. The error was in my *report*, not in the bank — but a wrong sentence in a status update is how a
real defect gets invented, so it is retracted here in full.

**The `retry_path` finding stands**, on its own evidence: 19 of 22 pages offer no retry affordance under a
500, confirmed both by the lens (`affordances: 0`) and by an independent probe that failed every
`/rest/v1/` request and scanned the whole document.

### §6n · `effect_visible` — a writing oracle, and three constants replaced by properties

`tools/prove_effect_visible.mjs` is the first prover in this bank that **writes to the shared database**.
That was only defensible because the discipline came before the result:

- the **restore mechanism was teeth-tested on a real row before the prover was allowed to write** — a
  mutation applied, *proven to have landed* (a restore test that never changed anything proves nothing),
  then reverted byte-identical;
- cleanup runs in `finally`, so a failed assertion still cleans up;
- cleanup is **verified by re-count** and reported. Every run: *0 rows left behind, the shared database as
  it was found.* A probe row left in a hive's feed would be worse than an unbanked row — it would look
  like a person wrote it.

It drives each page's **own** save path rather than inserting behind its back, and reads each page's
**own refusal channel** — five different ones so far: a returned `{ok:false, reason}` contract object
(logbook), a form-error element (inventory, report-sender), a transient toast (community,
project-manager), a silent early-return on a no-argument function (dayplanner), and a state precondition
(asset-hub). **A probe that does not satisfy a form's own validation is testing its payload, not the page.**

**The three corrections that matter, each made only after being wrong:**

| I had decided | the page demonstrates | what exposed it |
|---|---|---|
| text scan (`innerText`) | **element geometry** | `innerText` on a hidden node falls back to `textContent`, so body-scan and panel-scan gave opposite answers on asset-hub |
| blocklist of toast-like host names | **reload-survival** | voice-journal passed on `#current-transcript` — not a toast, not in the list, just as wrong |
| 2,500-char readiness floor | **settle-detection** | project-manager legitimately settles at 1,558, so that floor could only ever time out there |

Each replaced something **I chose** with something the **page proves**. An echo cannot survive a refresh;
a record must. A page is ready when it stops changing. Visibility is a fact about a box, not about text.

**Result across seven pages: six resolve into genuine record containers** — `calendar-wrap`,
`open-jobs-list`, `parts-list`, the post element, `contacts-list`, `history-list` — **and one fails.**

> A check that reddens every surface is measuring itself; one that reddens a single surface is measuring
> the surface.

**RETRACTED — `asset-hub` IS NOT A DEFECT, AND IT WAS THE ONLY ONE I ESCALATED TO IAN.** I reported that
an FMEA mode reached `rcm_fmea_modes`, was attributed to the selected asset, and that **no element
carrying it was rendered** — not immediately, not after reload, not after re-selecting the node and tab.
The write and the attribution were real. **The invisibility was my instrument.**

The FMEA workbench lives inside `#reliability-card`, which ships `style="display:none"` and is revealed
by an explicit control — *“🔧 Show Reliability Workbench (engineer view)”*, `aria-expanded="false"`,
`aria-controls="reliability-card"` ([asset-hub.html:674-676](asset-hub.html#L674-L676)). My probe clicked
the asset node and the `.rel-tab[data-tab="fmea"]` **tab** — which switches panels *inside* that card. It
was re-arranging the contents of a section it never opened.

> **The tell was in my own data and I read past it: the failing run reported EVERY `.fmea-rpn` badge
> invisible — 180, 168, 60 *and* my probe's 125. Three pre-existing modes cannot all be invisible.
> A probe that finds nothing visible in a populated panel has found a CLOSED panel, not an empty one.**

The ancestor walk named it exactly: `SPAN.fmea-rpn → DIV.fmea-row-head → DIV.fmea-row → DIV#fmea-list →
DIV#rel-panel-fmea → DIV#reliability-card {display:none}`. With the disclosure pressed, `aria-expanded`
flips to `true`, the created mode renders in a 22×45 box, and **all four** RPN badges are visible — the
pre-existing three being the control that proves the panel is populated and the observer could see it.

**Why this retraction matters more than the others.** A false RED is not the safe direction: it sends
someone to fix a render path that works. Progressive disclosure is a design choice this page states in
its own button text (*“engineer view”*) — and a probe that does not perform the disclosure is not
measuring the product a person uses. **Zero confirmed product defects survive this family; all fourteen
were the instrument.**

**`project-manager` is NOT a defect** and is recorded as such: its list query has no status predicate at
all, but it *groups* by status and opens only `active` ("auto-expand active, collapse others"), while
`projects.status` defaults to `planning`. The project is correctly stored, correctly grouped, one click
from view. The probe simply cannot open that group yet — a selector gap, not a product fault.

### §6o · The anatomy's `cross-page` marking is a LOWER BOUND, not an inventory

Working `cross_surface_agreement` (38 owed, none diagnosed), the obvious shortcut was to read each page's
grounded anatomy and disposition every page whose seams carry no `"how": "cross-page"` entry as *"this
surface shares no fact with another."* By that reading, **14 of 22 pages share nothing** — including
`hive`, `pm-scheduler`, `inventory`, `logbook` and `index`.

**All five of those were empirically proven to share facts earlier today:**

| fact | surfaces that agree |
|---|---|
| PM assets overdue = 28 | hive · pm-scheduler · shift-brain · index |
| low-stock parts = 3 | hive · inventory · shift-brain · index |
| open jobs (hive-wide) = 9 | hive · shift-brain · index |

None of those pairings is marked `cross-page` in the anatomy. The marking records seams *someone thought
to write down*; it does not enumerate every fact that happens to appear twice — and a KPI tile summarising
another page's number is exactly the kind of sharing nobody records, because it is a rendering decision
rather than a documented seam.

> **Had I dispositioned from the anatomy's silence, I would have written "shares no fact with another
> surface" onto rows whose sharing I had measured with psql two hours earlier** — a false disposition,
> durable, and contradicted by evidence already in the same bank.

**So `cross_surface_agreement` cannot be closed from the anatomy.** Each page needs the empirical
question: *does any number on this surface also appear on another?* — which is what
`tools/prove_cross_surface.mjs` answers, and why its pairs are hand-authored with a discriminator each.
The anatomy is a useful starting list (its 8 marked pages are genuine and mostly untested — `achievements
↔ community`, `analytics-report ↔ analytics`, `engineering-design ↔ project`, `public-feed ↔ community`,
`skillmatrix ↔ hive board`), but its silence proves nothing.

**A pattern worth naming, since it recurred all session:** a record that is *authoritative when present*
is not automatically *exhaustive when absent*. The same shape as the seam-miner counting a `fetch` and
missing a wrapped `functions.invoke`, and as a name-based blocklist excluding only what its author
anticipated.

### §6p · The anatomy's line anchors have decayed; its SUBJECTS have not

Chasing the `achievements ↔ community` seam, both of its cited anchors turned out to point at nothing
relevant — `achievements.html:1027` is a closing brace, `community.html:933` a comment. That raised a
bigger question, since R7 rests on every subject carrying a verifiable `seen:{how, ref}`.

**First measurement — and it was the wrong question.** Testing whether the cited line still carries text
related to the seam's name: **235 of 296 refs "drifted"**, only 61 matching. Read as a grounding failure,
that is alarming.

**Second measurement — the right one.** For each ref that names a SYMBOL (a table, view, or function),
ask where that symbol actually is now:

| | count |
|---|---|
| exact line still carries it | **14** |
| within ±30 lines (code moved a little) | **80** |
| elsewhere in the same file (moved a lot) | **99** |
| symbol genuinely gone | **4** — and 3 of those are my extractor grabbing generic words (`chrome`, `sections`, `forwards`) |

**≈98% of grounding subjects still exist.** What decayed is line precision, not the grounding. The
anatomy still names real things in the right files; it just no longer says exactly where.

> The first reading measured how *stale the citation format* is and would have reported it as **the
> subjects being unverifiable**. Same data, two questions, opposite severities — and only the second one
> is about the property R7 actually cares about.

**What this does and does not mean.** It does not invalidate any banked row: rows are anchored by
`sha`/`fn_digests` on the code, not by these line numbers, and R4 expiry already re-walks a row when its
file changes. It does mean **a line number in an anatomy ref should be read as "roughly here, in this
file", never as an address** — and that a future re-ground pass should re-anchor on symbols
(`v_worker_achievements_truth`, `achievement_xp_log`) rather than on `file:line`, which decays with every
edit above it.

**The one genuinely mis-grounded seam found:** `achievements ↔ community (community_xp)` — `community_xp`
does not appear in `achievements.html` at all. That page reads `achievement_xp_log`; community reads
`community_xp`. They are two independent ledgers (§6i), so this seam pairs two different facts and cannot
be settled as written. Consistent with the mis-specified `xp_agrees_across_surfaces` invariant already
recorded.
