# The Dimension-Expansion Flywheel — the standing framework for GROWING the rubric

**Mandate (Ian, 2026-07-23 → 2026-07-24):**
1. *"why is it you are always revolving to our existing usability, functionality, adaptability, and internal control... I want to EXPAND and EXTEND their existing dimensions using PDDA journeys deepwalk live mcps, and use night crawler for external ideas"* — the ask is to grow the DENOMINATOR, not re-measure it.
2. *"I love your approach and flow of these session, I want to solidify these as a framework... move like a flywheel loop... I don't believe that was only dimensions, there are still more and more dimensions that you just dropped or ignored. just the same flow."* — codify the loop and KEEP TURNING it.

---

## §0 · THE ONE DISTINCTION THAT DEFINES THIS FRAMEWORK

| | AUDIT vector | **EXPANSION vector (this framework)** |
|---|---|---|
| Question | "are our existing dims at 100%?" | **"what dimension can our rubric NOT EXPRESS AT ALL?"** |
| Instrument | the existing board / lens | **two discovery ENGINES (§2)** |
| Output | a % moved | **a new class/dim + the real bugs it exposes** |
| Failure mode | polishing a green board forever | inventing dims nobody needs |
| Doc | `feedback_coarse_lens_100_is_not_deep_100` | `feedback_expand_dimensions_not_reverify` |

**A dimension we already have, verified harder, is NOT an expansion.** When the ask is "expand", do not open the scoreboard first — run the engines.

---

## §1 · THE LOOP (one turn of the flywheel)

```
DEEPWALK a PRODUCTION journey (Engine A, live MCP) ─► an OBSERVED friction/idea
   ▲                                                          │
   │                                          measure it live: is it real?
   │                                       ┌──────────────────┴───────────────┐
   │                                    NO │ clean journey                     │ YES
   │                                       ▼                                   ▼
   │                              (don't harvest a non-problem;      HARVEST for THAT friction
   │                               walk the next journey)            (Engine B, night_crawler --query)
   │                                                                          │
   │                                                                          ▼
PERSIST ◄─ RATCHET ◄─ FIX (centralize-first) ◄─ MEASURE ◄─ ★CALIBRATE ◄─ ENCODE ◄─ SYNTHESIZE (prove
   │                                                                                 non-redundancy §3)
   └────────────────────────────► NEXT JOURNEY (never a one-shot)
```
**The journey is the STEERING WHEEL.** Engine A (live deepwalk of my real pages) surfaces the idea; Engine B (crawler) harvests the external technique for *that* idea; §3 proves it isn't already owned. A harvest with no journey-seed is a guess (§2).

**The loop does not end when a dim goes green.** Green means: lock it, then turn the wheel again on a NEW frontier. `§7` is the standing frontier backlog so the next turn never starts cold.

### ★★ENGINE B RUNS **INSIDE** EVERY LOOP — IT IS THE THING THAT REFILLS THE QUEUE (Ian, 2026-07-24: *"why you keep on stopping, can we use the night crawler between the loop so that we know we are going by harnessing external ideas?"*)

**This is the structural cure for my most-used stop excuse.** I had just ended a turn claiming *"the local queue is genuinely empty — only forks and external ceilings remain."* **That claim is almost never true, and Engine B is why:** any un-harvested body of external knowledge converts into new dimension candidates → new measurements → new work. A queue can only look empty if you have stopped harvesting.

**The rule:** every loop runs a HARVEST step — but the harvest is **SEEDED BY A LIVE JOURNEY**, not pulled from thin air (§2, Ian's 2026-07-24 refinement). Deepwalk a production page → observe a real friction → THAT is the `night_crawler.py --query "<friction>"` topic. The query costs **0 crawl tokens** and answers "do we already own this?"; only a genuine bag-miss escalates to `--url`. If the journey comes back clean, there is nothing to harvest for that thread — walk the next journey. This keeps retrieve-first intact AND stops me harvesting standards the platform never needed (2 of my first 3 cold harvests were kills).

**And "that publisher is blocked" is NOT "that knowledge is unreachable."** I had recorded WCAG 3.0 / APCA as a *hard external ceiling* because `w3.org` + `w3c.github.io/sustyweb` Cloudflare-challenge. The very next crawl against a DIFFERENT publisher (`git.apcacontrast.com`) succeeded in 1.5s. **A blocked domain is a false blocker — find another publisher of the same standard** (same class as reseed / start-the-container / install-the-tool).

**Immediate yield of putting the crawler in-loop (2026-07-24):** the APCA harvest produced, within one loop, a PROVEN new dim (`C2b`, below) plus a second finding the rubric could not express (long-form text under 14px). Both were invisible to the existing board, which was reporting green.

---

## §2 · THE TWO DISCOVERY ENGINES — ENGINE A **DRIVES** ENGINE B (not parallel)

**★THE ORDER IS LOAD-BEARING (Ian, 2026-07-24: *"you have to revolve to formulate your ideas by using my PRODUCTION pages by completing various journeys by using a deepwalk live mcps — from there you can get ideas to relay it to night crawler to do harvesting external sources."*)** The seed for external harvesting must come from a **live journey on the real production pages**, and *that observed friction* becomes the query handed to the crawler. Harvesting a standard in the abstract and hoping it applies is BACKWARDS — it burns tokens on knowledge the platform may already own or may not need. **Live journey → observed idea → targeted harvest → prove/kill.**

```
   ENGINE A (live MCP deepwalk of a PRODUCTION page)
        │   walk a real task at the real viewport; watch for friction
        ▼
   an OBSERVED idea / friction  ──►  is it real? (measure it live)
        │ YES, and the rubric can't express it              │ NO (journey came back clean)
        ▼                                                    ▼
   ENGINE B (night_crawler --query "<the observed friction>")   DON'T harvest a non-problem
        │   0-token bag check first; --url only on a miss         (a clean journey IS a valid result)
        ▼
   external technique/taxonomy for THAT friction  ──►  §3 prove non-redundancy  ──►  build or kill
```

**ENGINE A · LIVE MCP DEEPWALK — walk a JOURNEY, not a page. THIS IS THE IDEA SOURCE.**
The runtime lens is single-page and static-DOM, so it is *structurally* blind to anything that only exists IN MOTION. Walk a real multi-page task as a user (sign in, hop the hand-offs, at the real device viewport) and watch for: context lost across a hand-off, a task spanning 3 surfaces with no thread, state that dies on navigation, a dead-end, an invisible-but-focusable control, a focused field obscured by sticky chrome. **The friction you observe is the harvest query.**

> **★★A DEEPWALK CARRIES THE FULL LENS — ad-hoc probes are SHALLOW (Ian, 2026-07-24: "what a shallow journeys, you don't even carry all the required lens from night crawler").** The in-motion watch above is the *extra* the static lens can't see — it does NOT replace running the FULL harvested rubric on every page. On each page RUN `tools/family_rubric_sweep.mjs` (drives the whole 99-dim `survey_ufai_rubric.js` across all 32 pages) or the installed `survey()` — capture EVERY sub-100 dim. Hand-rolled `browser_evaluate` spot-checks ("does a button exist, h-overflow") are a pale substitute that marked pages "clean" while the full lens found C5 on 20 pages, R1/B3/E4 on others. **AND READ `perDim.failPages`, NEVER the page mean** — the mean is near-100 by construction (1 failing dim of ~60 = ~98.7%) and HIDES the findings. A finding then gets one of three evidence-decided dispositions: fix the page (C5 text-lift), calibrate the lens if it false-flags (R1 was counting a 1px sr-only `<h2>` as a layout block), or classify transient/AI-output-dependent (shift-brain B3/E4 varied with the AI briefing). See [[feedback_shallow_journey_carry_the_full_lens]].
> Yield 2026-07-23: class **JA** (journey arrival) + dims **Q2/Q3** — no static instrument could see them.
> Counter-example 2026-07-24: a keyboard journey on logbook measured SC 2.4.11 (focus-under-sticky-header) at **0/29 obscured — CLEAN.** So I did NOT harvest 2.4.11 sources: *the journey said the friction isn't there, and a clean journey is a valid stop for that thread.* This is the method's discipline — it prevents harvesting for a non-problem.

**ENGINE B · NIGHT-CRAWLER — harvest the technique for a friction ENGINE A ALREADY SURFACED.**
`python tools/night_crawler.py --query "<observed friction>"` (0 crawl tokens) first — do we already own it? Only a genuine bag-miss escalates to `--url <src>`, targeting *published, enforceable* taxonomies (standards bodies, regulator-backed pattern libraries), not blog opinion. Check the distill against the raw on nav-heavy pages (the distiller can summarise the nav shell and still pass the quality guard).
> Yield: class **DP** from the deceptive.design 18-pattern taxonomy.

**Why not "run both in parallel"?** The earlier framing ("run BOTH each turn; they find different species") let me harvest standards cold (APCA, Art. 50, web-carbon) — two of those three were KILLS because nothing on the platform needed them, or the lever was already gated. Grounding the harvest in a live-observed friction raises the hit rate and stops me spending tokens to re-derive owned knowledge. Engine B without an Engine-A seed is a guess.

---

## §3 · SYNTHESIZE — a candidate must EARN its class id

**The no-redundancy check must be PROVEN, not asserted** (and equally, "already covered" must be proven — do not weaponize it to kill real work):

| Candidate | Killed or kept | Proof |
|---|---|---|
| **DP** vs **TR** | KEPT | TR = trust signals PRESENT; DP = manipulation ABSENT. A page can ace TR while pressuring the user. |
| **JA** vs `deep-link-params` gate | KEPT | that gate only asserts a `.get()` reader EXISTS; it passed on all 3 broken pages. |
| **JA** vs class **E** | KEPT | E = a page's own empty state. Here the page is NOT empty — it confidently shows the WRONG rows. |
| **SC 3.3.7** Redundant Entry | **KILLED** | existing **G5c** already reads "pre-fills known values… always editable" + Z1 requires `autocomplete`. Same job. |
| "RG1 role-gate integrity" (loop 3) | **KILLED** | live escalation FAILED at render on 2 pages (planted `wh_hive_role=supervisor` as a real worker was overwritten to `worker`, 0 supervisor affordances, no flash), and the property is already owned by `validate_role_gate_server_backstop.py` (server = authority) + `wh-roles.js` (canonical client reader). Encoding it would duplicate a gated architecture. |
| **"Web-carbon / sustainability budget"** (loop 25, in-loop harvest) | **KILLED** | harvested the Sustainable Web Design carbon model (`external-sustainable-web-design-page-weight-carbon-model`, kept as reference). Its emissions estimate is `bytes × carbon-intensity constant` — a MONOTONIC reframe of page weight, not a new measurable property. Every enforceable lever it exposes is already owned: **page bytes** are gated by the E-weight lens + `render_budget_baseline.json`; **return-visit cache ratio** by the SW shell cache + `validate_sw_shell_membership`; **green-hosting factor** is a single deploy-time infra constant, not a per-page UX property. A page under its byte budget IS under its carbon budget. Same job as E-weight, different UNIT (gCO2 vs KB) — the SC 3.3.7 kill pattern. **Lesson: a motivational standard whose only enforceable lever is one we already gate = KILL, do not reframe.** |
| **Art. 50 "machine-authorship disclosure to the USER"** (loop 24) | **KILLED** | measured THREE times, wrong twice, killed on the third. A crude scan said 6/14 pages mark AI output (43%); a "sharpened" scan said logbook injects 8 unmarked AI fills. **BOTH were false.** `asset-hub` discloses by surface naming ("AI Q and A … Grounded in this asset's logbook"); `logbook`'s 8 assignments were `restoreDraft()` restoring **the USER'S OWN** localStorage draft (the word "draft" is overloaded — marking those "AI-drafted" would have falsely attributed the worker's writing to a machine, the exact MIRROR of the AI6 defect); and the real AI path (`vdcApplyDraft`) already gives an explicit receipt — user-pressed "Analyze with AI", then "✓ Filled N fields: …", failure mode, severity, **Confidence N%**, and "review the filled fields before saving". Property is already owned by **AI2** (grounding/basis) + **AI4**. Only Art. 50(2) machine-readable marking of EXPORTED artefacts is unmet — a compliance feature for a PH-based platform, Ian's scope call, not a UX dim. |
| "JA2 return-thread" | **KILLED** | live walk showed onward links already carry context (`?asset=CP-100`) and browser-back covers return. **Inventing it would have been padding.** |

**Rule: the FINDINGS define the classes. Never invent a dim to fill a letter.** SEVEN candidates have now been killed with proof (SC 3.3.7, RG1, JA2-return-thread, shift-handover, SC 3.2.6, Art.50-disclosure, web-carbon-budget), and ONE in-loop harvest (APCA) EARNED its dim (C5). A healthy hit/kill ratio is the discipline WORKING — the crawler surfaces ideas, evidence decides which survive.

---

## §4 · ENCODE — the SSOT triple-lock and the mechanics that bite EVERY time

Prose ruler ↔ lens ↔ spec must agree (`validate_rubric_parity.py`), and every dim needs a measurement source (`rubric_coverage.py`).

**Checklist — each of these cost me a failed gate run at least once:**
1. **Register every new 2-letter class** in `_VALID_CLASS` (`tools/validate_rubric_parity.py`). Recurs on *every* new class.
2. **Source-measured (non-lens) dim → add to `EXEMPT_CROSS_PAGE`**, else parity fails "declared in DOC but not in lens".
3. **Each prose bullet must START with the dim id** (`- **JA1 …**`). The doc parser regex anchors at line start; a combined `- **DP1/DP2/DP3 …**` bullet parses as ONE dim.
4. **Reconcile BOTH headers** — the prose "~N dimensions" and the lens "N dims encoded".
5. **★Write the new dim into the ratchet baseline JSON explicitly.** A missing key defaults to the *current* value (`base.get(dim, d["pct"])`) = a gate with NO teeth that reports "OK" forever.
6. **Never put a backtick inside a JS template literal** (the lens/nav-hub CSS lives in one). It silently terminates the string → the whole shared chrome dies. `node --check <file>` after every edit to an injected-CSS file.

---

## §5 · ★CALIBRATE THE RULER BEFORE YOU "FIX" ANY PAGE

**The newest instrument is the least trustworthy thing in the room.** A fresh detector on a well-built platform over-flags far more often than it finds. Q2 over-flagged TWICE:

| Over-flag | Symptom | Root | Correction |
|---|---|---|---|
| 1 | 6 pages failed; pm-scheduler "20 phantoms" | children of a `display:none` ancestor still report their OWN `display:block`; a `from{opacity:0}` keyframe makes the subtree look hidden | require the element to be **RENDERED** (`offsetParent`/client-rects). `opacity:0` keeps layout, so real hits survive |
| 2 | marketplace + seller failed | their `<input type=file>` laid `opacity:0` over a styled button — the **standard accessible upload pattern**, which MUST stay focusable | walk opacity from the **PARENT**: only a focusable trapped in a hidden CONTAINER is a phantom |

**★PROBE THE JOURNEY'S OWNER SURFACE, NOT A SIMILARLY-NAMED ONE (loop 9).** Walking "shift handover" I probed `shift-brain.html`, found no acknowledgement/receipt, and was one step from filing a real-sounding safety gap ("an unacknowledged handover"). Retrieve-first killed it: the validated handover tool lives on **hive.html** (`#handover-panel`, `#handover-sheet`, **`#ho-handover-to`**, LOTO sections, acknowledgement) - `shift-brain.html` is the AI shift *planner*, a different surface with a similar name. **Before believing a journey gap, confirm you walked the surface that OWNS that journey** (skills/Memento name the owner). Same family as the disproof test below.

**★"FIXTURE-BLOCKED" IS NOT A BLOCKER (loop 13).** I parked hive-switch because no seeded user belonged to 2+ hives - then seeded one, walked it, and it took minutes. **Missing data is never a ceiling: reseed it, walk it, delete it.** Same family as the stopped-container false ceiling. And when comparing across tenants, compare by **id/hive_id** - a hive-scoped identifier like an asset TAG collides across hives by design and will false-flag a "leak" (BLR-003 is a Miura in one hive and a Cleaver-Brooks in another).

**★MY OWN EXPLANATORY COMMENT KEEPS TRIPPING NAME-MATCHING GATES (twice now).** `validate_dom_refs` flagged engineering-design.js because my comment spelled out the identifier I had just removed; `validate_canonical_anchor`'s tier_c flagged 3 edge fns because my inserted comment contained the literal `ai-gateway`, which is on its AI-signal list. **A scanner cannot tell a comment from code.** When documenting a removal or referencing another component by name, avoid the bare token the gates grep for - or expect a self-inflicted red.

**★"BOOT-TESTING" AN ORCHESTRATOR IS NOT SIDE-EFFECT-FREE (loop 17).** To prove my 17 edited edge fns still parsed, I POSTed `{}` to each and treated a 4xx as "it booted". 15 returned 4xx - but **`amc-orchestrator` returned 200 because it actually RAN a drain across all 3 hives and INSERTED 3 amc_briefings + 2 automation_log rows.** An empty body is a valid batch trigger for a cron-style fn. The check was still worth doing (it is the only real proof of a parse error without deno, and it confirmed the nested-paren fix in failure-signature-scan boots), but **probe the DB before AND after, and clean up** - I deleted all 5 rows. Prefer a fn's `/health` route or a deliberately-invalid payload over an empty one on anything named *-orchestrator / *-scan / scheduled-*.

**★A SUBSTRING CHECK IS NOT A CONTRACT TEST - FAULT-INJECT TO PROVE TEETH (loop 19).** I wrote a contract test, its `--selftest` passed, and I wired it to 27 seams. Then I injected the exact regression it claims to guard - removed the DAILY ceiling from the shared limiter - and it returned **exit 0**. Cause: `if "limitPerDay" not in src` is a SUBSTRING test, and `"limitPerDay" in "limitPerDayXX"` is True, so a renamed symbol still passed. **A self-test that only asserts the happy path proves nothing; the only proof a gate has teeth is BREAKING the thing on purpose and watching it fail.** Fixed with word-boundary regexes, then re-injected 3 distinct regressions (symbol renamed / column dropped / export removed) - all caught, restores green. Apply this to every new gate before trusting its number.

**★A STRING IS NOT AN ANNOUNCEMENT UNTIL IT REACHES A USER — and INSTRUMENT, don't guess (loop 20).** JA1 read 11/11 = 100% while fault injection proved it caught only 2 of 4 real regressions. I guessed at the cause 3× in a row and was wrong every time; printing *which window and which clause actually matched* found both roots immediately. **Root 1: my own explanatory COMMENT satisfied the detector** — the fix comment said *"...must say plainly that we could not find it"*, so the scanner matched MY PROSE and deleting the real toast still passed (**4th** time this session a comment fooled a scanner: `validate_dom_refs`/HIVE_ROLE, `validate_canonical_anchor`/"ai-gateway", `validate_ufai_deep_u`/tokens.css). **Strip `<!-- -->`, `/* */`, `//` before matching ANY evidence.** **Root 2: a bare literal is not behaviour** — replacing `showToast('Could not find "'+x+'"')` with `void ('' + x + '": showing all')` deletes everything the user sees, yet the literal survives, so the text match still scored PASS. Evidence must reach a **sink** (toast/dialog/`textContent`/`innerHTML`/returned markup). Two sub-lessons: **scope evidence to windows** (a file-wide `.value =` search is a rubber stamp on any big page) but **compute those windows as offsets into the FULL source** — a 2000-char slice can start mid-template-literal, invert backtick parity, and flip a CORRECT page to a false FAIL. Final state: 6/6 injections caught, clean 11/11. **Also check the DELTA, not the exit code** — one "CAUGHT" was spurious (10/11 → 10/11 on an already-failing page proves nothing).

**★A `skip_if_fast` GATE ROTS INVISIBLY — sweep `--selftest` across ALL validators (loop 20).** A stale symbol reference left a NameError reachable ONLY via `--selftest`, so the gate ran green with a broken file. Sweeping all 45 validators found it — **and found `memory_recall_eval` genuinely FAILING** (recall@3 0.48 vs a 0.60 floor), unseen for months because `--fast` skips it. Root: Memento ranked **curated** `feedback`/`reference` (2.0) BELOW auto-derived `doctrine` (2.8) / `skill` (2.5), so any roadmap chunk that merely MENTIONED a lesson outranked the lesson itself. Fixed → recall@3 0.48→0.96, MRR 0.42→0.93. **The floor was the deeper bug: 0.60 was calibrated against the already-broken retriever, so the gate admitted the very defect it existed to catch.** Raised to 0.85/0.88/0.80 (fixed floors, never auto-ratcheted, never lowered to pass). **Prove any ranking change on HELD-OUT queries** — 8 never used in tuning went **0/8 → 7/8**, which is what separates a real fix from teaching to the test — and **don't chase the last golden with a knob** (one miss was deliberately left failing). See `feedback_curated_memory_ranked_below_derived_corpora`.

**The disproof test:** before believing a finding, ask the DOM to contradict it — `el.focus(); document.activeElement === el`. That single line proved 20 "bugs" were not focusable at all. **I nearly "fixed" 6 pages that had no bug.**

**★A NEW DIM CAN EXPOSE AN OLD DIM'S FALSE PASS — reconcile, do not weaken (loop 2).** Fixing Q2 (closed companion → `visibility:hidden`) dropped **W2 shared-chrome 100% → 33%**. The tempting move is to soften the new fix. The honest finding: **W2 was written PRE-FAB-consolidation and demanded the companion launcher be VISIBLE; it only kept passing because the closed widget used `opacity:0`, which slipped past its visibility check — it was scoring a control the user CANNOT SEE as "visible" = a false pass.** Resolution: recalibrate W2 to its REAL job (the companion module LOADED + its avatar RENDERED, hub visible) and **prove the recalibrated dim still has teeth** — removing `#wh-ai-widget` still drops it to 33%. Rule: when a new dim collides with an old one, ask *which expectation is stale*, fix that, and re-prove the old dim can still fail.

**Also calibrate the STANDARD, not just the code:** SC 2.4.11 is about *sticky/fixed* chrome. Counting any `position:static` parent as an obscurer produced 20 hits where 1 was real.

---

## §6 · FIX → RATCHET → PERSIST

- **Centralize-first (METHOD LAW).** A dim failing on N pages is usually ONE unadopted/incorrect shared component. Q2's 28+ hits were `#wh-hub-panel` and `#wh-ai-widget` — two shared-chrome edits covered ~30 pages each. Chip per-page only after the shared root is proven absent.
- **Verify BOTH directions of a state change.** The hidden↔shown fix pattern:
  ```css
  .thing      { opacity:0; pointer-events:none; visibility:hidden;
                transition: opacity .25s, visibility 0s linear .25s; }   /* delay = fade length */
  .thing.open { opacity:1; pointer-events:all;  visibility:visible; transition-delay:0s; }
  ```
  I shipped the base rule WITHOUT the `.open` reset and the nav panel could never reopen. **Every fix gets re-walked live: closed = unfocusable, open = still works.**
- **A CLEAN result still gets ratcheted.** DP and Q3 found zero bugs — encode them anyway so the day a countdown timer or a drag-with-no-click-path ships, it FAILs. Locking a clean property forward is a legitimate deliverable.
- **Persist order matters: rebuild the substrate LAST**, after every page/doc/skill/memory edit settles, or a late edit re-drifts a mirrored chunk. Then bump `sw.js` when shared chrome changed.

---

## §7 · STANDING FRONTIER BACKLOG (so the next turn never starts cold)

Keep this list alive; tick items off and ADD what each turn reveals.

**★LOOP 22 (live walk) — A NEW FINDING IS USUALLY A DETECTOR BLIND SPOT, NOT A NEW DIM.** The supervisor-approval walk found the reject-reason input labelled ONLY by `aria-label` — a sighted supervisor saw a bare box (axe passes = another axe-0-violations false 100). **M1 already forbids this in prose** ("label ABOVE/left, NEVER placeholder-as-label"); the LENS just counts `aria-label` as satisfying it (`survey_ufai_rubric.js:923`) — the W2 false-pass shape again. Fixed centrally in `whPrompt` (18 call sites inherit a real `<label for>`). **And do NOT blanket-recalibrate:** search/filter/compose fields are legitimately aria-label-only, so scope the rule to DATA-ENTRY fields — measured backlog **29/187 (15.5%) across 10 pages**. **Sequence: fix the fields, THEN tighten the lens** (flipping the detector first knowingly reds a ratcheted board with no fix behind it). **DONE the same turn: 29 → 0, then the lens was tightened and fault-injected (6/6 → 5/6 on BOTH the aria-label-only revert and the hidden-`sr-only` dodge).** Breakdown once measured properly: 5 had a visible label merely UNBOUND (add `for=`), 3 bound to an existing visible heading via `aria-labelledby`, 2 conditionally-revealed fields WRAPPED so the label toggles with the input (a naked label orphans itself when the field hides), the rest labelled or conventional-exempt. **★AND THREE OF MY LIVE PROBES WERE INVALID BECAUSE THE TARGET WAS HIDDEN** — the first teeth-test read TOOTHLESS only because the injected field sits in a COLLAPSED panel and the visibility-filtered lens never counted it; likewise an "eye icon perfectly centred" reading was meaningless (every rect 0×0 with the modal shut). Confirm rects > 0 BEFORE believing any live measurement. Also: moving a label INSIDE a `position:relative` wrapper re-centred the password show/hide eye — the label belongs above the wrapper.

**Engine A — journeys WALKED:** first-run (→JA2) · buy/RFQ (→JA3) · role-switch (clean) · offline→reconnect (clean) · shift-handover (clean, owned by hive.html). **Not yet walked:** (approval chain WALKED 2026-07-24 — seeded a pending node, exercised approve/reject, probe row deleted); hive-switch (blocked on fixture - no user belongs to 2+ hives in the seed, and `Hive Switch Must DB-Validate Membership` is already a recorded lesson).
**Engine B — knowledge not yet harvested:** WCAG 3.0 / APCA, sustainability & resource-efficiency (both **w3.org + sustyweb Cloudflare-blocked** = genuine external ceiling; needs a different publisher).
**HARVESTED 2026-07-24 — EU AI-Act Article 50** (`external-eu-ai-act-article-50-transparency-obligations`). **★THE DISTILLER FAILED TWICE WHILE THE RAW WAS FINE:** `night_crawler` summarised the page's NAV SHELL both times (2nd pass emitted *"The EU AI Act logo … 846x215 pixels"*) and **both noise distills PASSED the quality guard** — the link-density warning was the only tell. The raw cache held the full 50,478-char text, so the chunk was hand-written FROM the verified raw and the 3 nav/logo caches were deleted. **Check a distill against its raw on any nav-dominated page.**
**CANDIDATE (measured, NOT yet earned — §3 pending): "machine-authorship disclosure to the USER."** Distinct from **AI6** (which makes the DB ROW declare machine authorship) and from **AI2** (which shows an answer's BASIS): Art. 50(1) asks whether the human is TOLD a machine wrote it, and 50(2) whether the exported artefact is machine-readably MARKED. **A crude scan said 6/14 AI-rendering pages mark it (43%) — that number is NOT trustworthy and I proved it:** `asset-hub` is a false gap (its panel is explicitly "AI Q and A … Grounded in this asset's logbook" — disclosure by surface naming), while `logbook` is a REAL gap (the visual-defect AI silently pre-fills the form; the worker just sees filled fields). **Sharpened rule to measure next: AI output injected into a HUMAN surface (a form, a report field) needs an explicit marker; a surface that is ITSELF named as AI is already disclosed.** Prove or kill against AI2/E3/AI6 before it earns a class id. Scope: PH-based, so the EU Act is a transparency TAXONOMY here, not a legal mandate.
**★TWO MORE STALE BACKLOG CLAIMS, caught by querying the bag BEFORE crawling (loop 20).** `night_crawler --query` costs 0 crawl tokens and disproved two of my own "not yet harvested" entries: **COGA was ALREADY harvested** (`external-coga-cognitive-accessibility-design-objectives.md`) **and already ENCODED** into A3 / X2 / Y2 / G5 — re-crawling it would have burned tokens to re-derive owned knowledge. That is now **four** stale gap-claims across the arc (D6, D11, COGA, SC 3.2.6): **a backlog line is a HYPOTHESIS, not a fact — verify it against the bag/live scorer before spending anything on it.**
**★A SECOND DENOMINATOR EXISTS — reconcile it, don't assume the UFAI rubric is the only dimension set.** `PLATFORM_DEEPWALK_FLYWHEEL_ROADMAP.md` carries a D1-D26 set organized by ARCHITECTURAL LAYER and ranks its own unowned gaps. Reconciling it (loop 5) found: D6 "frontend CWV = 0% measured" was **STALE** (already covered by rubric **I1** + the sweep's PerformanceObserver), and D21 "frontend observability dark" was **REAL** → built + lit (see roadmap §13.3). **D11 was ALSO stale** (the live Arc-R board scores P · Prompt & AI security at 100%). **Still open: D12 per-surface cost/quota.** Two stale gap-claims in two loops = when a roadmap's PROSE names a gap, run its own live scorer before believing it. When the UX-journey vector saturates, mine the OTHER denominator rather than inventing dims.

**Known EXTERNAL ceiling:** `w3.org` and `w3c.github.io/sustyweb` are Cloudflare-challenging (retried twice, two URLs → "Just a moment..."). Retry later or find an equivalent non-blocked publisher.
**Resolved (do not re-derive):** **SC 3.2.6 Consistent Help → KILLED (5th candidate killed with proof, loop 20)** — measured before encoding: the only *repeated* help mechanism is the AI companion, injected by `companion-launcher.js` at ONE fixed anchor (`position:fixed; bottom:24px; right:24px`) on 27/31 pages, so its relative location is **consistent by construction**; the 4 pages without it are `assistant.html` (it IS the help mechanism), `index.html` (landing) and 2 internal consoles — and 3.2.6 only binds pages that HAVE the mechanism. `.wh-help` is a centralized inline-help `<details>` disclosure already owned by **FI1** (promoted 2026-07-17 from 9 byte-identical copies). Covered by **W2 + FI1**; non-redundancy NOT provable → no class id. SC 2.5.7 dragging → **Q3**, verified met (dayplanner is click-item-then-click-slot, not drag). SC 3.3.7 redundant entry → covered by **G5c/Z1**. SC 3.3.8 accessible auth → **met** (login uses `autocomplete="current-password"`/`"new-password"`, no paste blocking, no cognitive test). SC 2.4.13 focus appearance → **met** (shared `:focus-visible` in components.css + a `utils.js` injected ring on every page, no `outline:none` killers). First-run/zero-state journey → walked, produced **JA2**.

**Loop-2 yield:** **JA2 · return-promise kept** — the `#hive-gate` promised *"You'll be brought back here once you're set up"* but sent users to a BARE `hive.html` that read no return param: a promise structurally impossible to keep. Fixed centrally (utils.js stamps `?return=`, hive.html renders a **validated** "Continue to X" banner rejecting `https://evil.com` / `//evil.com` / `../../` / `javascript:` / query-carrying values).

---

## §8 · DEFINITION OF DONE FOR ONE TURN

A turn of the flywheel is complete when **all** hold: both engines run · every finding either encoded or killed with proof · the ruler calibrated against live truth · real fixes centralized + live re-verified in both directions · new dims ratcheted with baselines WRITTEN · SSOT parity + coverage green · substrate rebuilt last · `§7` updated with what the turn revealed.

**Then turn the wheel again.** The rubric is never "done" — it is a growing denominator.
