# UFAI UI/UX Improvement Plan — CLOSING STATE (2026-09-02)

_Generated from `critic_registry.json` at walk-coverage completion. The living registry is the SSOT;
this document is the program's synthesis and hand-off record._

## Where the program landed

- **All 480 in-scope trajectories walked and critiqued**: 440 critiqued · 40 improving · 0 pending.
- **63 receipted findings → 1 remaining** (T12's S1 opener-tune, deferred: the local edge runtime is
  down, so a prompt change's OUTPUT cannot be live-verified — deferred rather than banked unverified).
- **Major+ (severity ≥3): ZERO open.** Every S4 and S3 was fixed by judgment, verified live at the
  exact walked hop, and locked by a resurrection-toothed gate.
- **19 new gates registered** on the platform board this program (all grep-verified):
  team-deeplink-survives, one-clock-per-string, journal-transcript-is-raw, critic-registry, kpi-evidence-links, xp-feedback-reaches-worker, skill-privacy-copy-consistent, risk-pm-linkage, assistant-no-orphan-fragment, pm-completion-repaints-truth, hive-name-reconciles, inventory-tx-attribution, staged-stock-guard, modal-back-helper, draft-age-visible, approval-queue-aggregates, report-reason-deliberate, pick-prefills-category, embed-retry-queue.
- **3 migrations** landed+applied: credit-hold audience-neutral voice, inventory server-side
  attribution (JWT-not-body), staged-stock guard (the marketplace-hold mirror).
- **The flywheel proved itself**: journal-transcript-is-raw's DB layer caught a LIVE regression
  same-day (the third scaffold-sender in assistant.html) that the fix-audit had missed.

## The 13 root clusters — final dispositions

1. **Clock discipline** (one clock per string, plant-anchored, labeled) — FIXED+GATED
   (one-clock-per-string; logbook/index/shift-brain/audit-log/alert-hub all verified).
2. **Reserved stock enforcement** — FIXED+GATED (staged-stock-guard REPLAYS the refusal live each run).
3. **Audit attribution** — FIXED+GATED (inventory-tx-attribution; payload-lies-JWT-wins proven).
4. **AI transcript integrity** — FIXED+GATED (journal-transcript-is-raw, 3 sender paths + DB layer).
5. **Dead/broken chain hops** — FIXED+GATED (team-deeplink-survives; the diagnostic chain runs
   alert-hub→asset-hub→logbook end-to-end).
6. **Stale renders after writes** — FIXED+GATED (pm-completion-repaints-truth: write→read→render).
7. **XP/feedback legibility** — FIXED+GATED (xp-feedback-reaches-worker: queue + earn notes).
8. **KPI truthfulness** (caps-as-totals, dead-end figures, unnamed windows) — FIXED+GATED
   (kpi-evidence-links: exact counts, drill-to-evidence, window labels).
9. **Identity/name integrity** (wrong-plant chrome, phantom risks) — FIXED+GATED (hive-name-reconciles).
10. **Honest refusals & walls** (privacy copy, report reasons, quota voice, credit-hold pronoun) —
    FIXED+GATED (skill-privacy-copy-consistent, report-reason-deliberate + migrations).
11. **Interaction costs** (modal-back, category prefill, approval aggregation, dwell/review ages) —
    FIXED+GATED (modal-back-helper, pick-prefills-category, approval-queue-aggregates,
    draft-age-visible).
12. **Resilience surfaces** (offline round-trip, stream fragments, mic dead-taps, embed retry) —
    FIXED+GATED (assistant-no-orphan-fragment, embed-retry-queue, MIC_BOUND; T14's full
    offline→queue→sync→DB round-trip proven live).
13. **Instrument honesty** — 12 findings withdrawn as instrument misreads across the program, each
    with the probe lesson banked (toast TTLs, layout-vs-exposure, partial-listing traps,
    never-settling promises).

## What remains (the endgame, in order)

1. **The residual FULL BOARD** (Ian's ~6h gate): re-earns the ~687 browser-gated bank rows and — via
   `tools/post_board_promote.py --apply` — flips critiqued/improving → locked on gate-PASS. This is
   the 71.2% → 100% lever, and it is deliberately Ian-initiated.
2. **T12's opener-tune** once the edge runtime is up (a `supabase functions serve` attempt is
   in flight; if it serves, tune + verify + clear the last finding).
3. **Ian's standing gates**: the commit manifest (`.tmp/COMMIT_MANIFEST.md`), the skills writeback
   (cross-skill table prepared for one-pass approval).

The platform's UI/UX story after this program: **the strong majority of what the walks tested was
already sound** — conversion, onboarding, re-auth, offline, failure-legibility all took hits and
held — and every place it wasn't sound is now fixed at the root, proven at the broken hop, and
gated so it cannot quietly regress.

---

# EXTENSION: the in-motion deepwalk (Wave 3, 3,959 rows) — EMERGING CLUSTERS

_The section above is the CLOSED record of the 480-trajectory program (2026-09-02). What follows is the
LIVE synthesis of the larger extension now in flight (`critic_walk_groups.py`: 253 distinct walks
remaining). Clusters are added as walks reveal them and are dispositioned when fixed at the root._

> **Scope rule this section obeys.** The deepwalk roadmap's §4 sequencing says to re-run the full
> `family_rubric_sweep` + `close_critic_findings --apply` BEFORE clustering, because *"a synthesis built
> on the current numbers would cluster phantoms"* — findings that would close on re-measurement. That
> still stands, and nothing below is drawn from the registry's standing aggregate. **Every cluster here
> was measured live on the page, fixed, and RE-measured clean by the same oracle in the same session,
> with the before/after numbers quoted.** These are receipts, not a roll-up. The aggregate clustering
> still waits on the sweep, which needs the browser and is sequenced behind the walk chain (two
> Playwright jobs on this 8 GB host is the contention rule).

### C-A · The pair was declared and not adopted (contrast) — FIXED AT SOURCE 2026-09-10
`tokens.css` ships an AA-safe TEXT variant beside each fill (`--wh-red: #f87171; /* alert / danger fill
(AA text = --wh-red-text) */`, plus `--wh-blue-text`, `--wh-orange-text`, `--wh-violet-text`). Every C2
failure walked so far was a site using the FILL as text at 10–13px: logbook's category chips (4.09:1,
4.2:1) and open-jobs badge (4.38:1), and `utils.js` `renderKpiTile`'s "✗ Critical" chip (4.18:1) — the
last on EVERY page that renders a red KPI tile, not just the walked one. Fixed by adoption; re-measured
by the same oracle at logbook C2 100% (208/208, zero offenders) and analytics C2 100%. **Lead, not a
defect list:** a static scan finds 46 inline blocks across 14 files pairing a fill token with sub-14px
text. They are CANDIDATES only — contrast depends on the composited backdrop, and orange on navy often
passes. C2 adjudicates per element on each walk; do NOT bulk-replace them ([[a count of small targets is
not a count of defects]]).

### C-B · `display:none` on a responsive label strips the accessible NAME — FIXED 2026-09-10
Hiding a label at phone width removes it from the a11y tree, not just from view. With the sibling icon
`aria-hidden="true"`, each control's name collapses to its count: marketplace's four primary tabs
announced as "9/5/6/—", and marketplace-seller's Listings and Inquiries as "0". Fixed on both with the
clip pattern (`.sr-only`), tab widths measured identical before and after (80/79/79/82; 83/82/82/82).
**The dim under-reported it 8:1** — D1's icon-only test reads `innerText` for a symbol-only string, so
"9"/"0" never qualified and an empty tab never qualified; only a count rendered as an em dash did.

### C-C · The partial fix is the recurring shape
Three independent instances in one session: marketplace-seller's Analytics and Services tabs carried
`aria-label` while Listings and Inquiries did not; `renderKpiTile`'s grey row was APCA-tuned in
2026-09-07 while red and yellow were left; `.wh-help`'s 14px margin lived in TWO files that a standing
comment requires to stay byte-identical. **Rule reaffirmed:** when a fix lands, grep the shape across
every page and every copy before calling it done.

### C-E · The stored locale was never applied at boot (index.html) — FIXED 2026-09-10
The single largest defect this extension has found, and only a **Filipino** walk could surface it. With
`wh_lang='fil'`, index rendered **50 of its 56 `data-i` keys in English** while `_ohFIL` held a Filipino
string for every one. Two faults, the second hidden behind the first: (1) `setLang()` ran **only** from
the EN/FIL toggle's click handler, so `_t()`-rendered strings came out Filipino — which is precisely why
the page looked bilingual in places and why this survived; (2) `setLang` snapshotted `[data-i]` **once**,
so `#ops-home`, `#user-menu` and the PWA button — all painted after auth resolves — kept English forever.
Fixed with `_ohApplyI18n(root)`, a re-entrancy-guarded MutationObserver, and a DOMContentLoaded boot
apply; `_ohEnCap` now captures a key's English on **first sight** so the EN direction restores late
markup too (round-trip verified). After: 0 of 56 English, page 252,226 → 256,271 chars.
**Bounded by a follow-up walk, not assumed:** five member surfaces (hive, logbook, skillmatrix,
achievements, community — 275 `data-i` nodes between them) were then checked and **all apply Filipino at
boot**. index was the outlier, for a legible reason: it is the one page reachable without ever signing
in, so its boot path is the one a logged-in test journey never exercises.

### C-F · One shared component, the same defect on every page that renders it
Three instances, all fixed at source rather than per page: `utils.js` `renderKpiTile`'s verdict chip
(fill-as-text, 4.18:1) reaching every red KPI tile; `whAiTrustRow`'s feedback thumbs at 28×28 reaching
every AI answer — banked from **four separate walks** before being fixed; and `ACHIEVEMENT_TIERS`' silver
at 4.13:1, in a table whose own comment records lightening Iron and Bronze for that exact rule in July.
**Shape the fix so the oracle can see it:** the thumbs kept their 28px ring (border moved to an inner
`aria-hidden` span) while the *button* became 44×44 — the `::after` hit-area trick was rejected because it
leaves the button's box at 28px, real for a user but invisible to F1, so every future walk would
re-report a defect that had been fixed.

### C-D · Instrument corrections this extension (the oracle was wrong, not the code)
Five in one session, each verified against the element before the number was believed: X1 scoped
dead-ends to a panel and missed the recovery link rendered in its adjacent sibling; H1 scored a
worker-daily page 0% for correctly declining to paint an empty bar (it now reads an empty
`.wh-progress-slot` as "mechanism present, nothing to gradient" → N/A); J1 could not see a slip-guard
one hop away behind a class instead of an id; plus the C2 disabled-control exemption and the N1 `data-i`
census carried over. `tools/retract_critic_finding.py` now withdraws a banked claim the ruler got wrong —
removing a false MEASUREMENT, or keeping a true one whose INTERPRETATION was wrong — with the reason on
the row. `tools/bank_critic_walk.py` refuses a bank whose survey files grade pages the rows never
declared, after a reused glob prefix nearly attributed three unopened pages to a journey.

Added since: the **permission wall** (a visible `.gate-card` / `[id^=gate-]`) marks E3/G1/I2 N/A —
audit-log walked as a worker graded three hard zeros for correctly showing "Supervisors only" instead of
a silent empty state; verified on all three states (worker-wall N/A, worker-hive measured,
supervisor-data measured). **Q2** now reads a `:focus-within` declaration, after a *measured* timeline
refuted its own sentence — focusing a scroll-reveal link does reveal it (opacity 0 → 0.92 at 300ms → 1
at 700ms), so `index.html` gained `.reveal:focus-within` to make that guarantee declared rather than
emergent. And **`_clippedAway()`** in the shared `vis()` (plus Z3's own `_vz`): an `sr-only` ancestor
clipped to 1×1 hides *paint*, not *layout*, so 32 sitemap links counted as page content and dragged six
dims on the front door — index 81% → 88% with the page unchanged.

**Method traps this extension has paid for, now standing practice:** re-`eval`ing the rubric without
RELOADING silently keeps the *old* lens (the installer returns `{already:true}`) — navigate first and
assert `install:true` per page; never edit source while a board runs (a 27-minute `--fast` read
inconsistent state and reported 13 phantom regressions); regenerate derived artifacts (destructive
registry, substrate, `sw.js` CACHE_NAME) **after** the last source edit, not during; and a post-sign-in
redirect can silently leave you on index — every survey now records its own `href` and `title`, which is
how a `hive.json` that was actually index got caught.

### C-G · Three decision surfaces each ask for three or four first actions
**Measured on three pages, and they are the three that matter most.** `index` 27 controls / **3** primary
CTAs, `hive` 24 / **3**, `marketplace-seller` 15 / **4** — each failing **G3 0%**, and each independently
failing **A3 75%** from the layout side (`primaryCta=3/2`, `3/2`, `4/2`). One is the front door strangers
meet, one is the busiest member surface, one is where a seller earns; all three are pages whose whole job
is to make the next action obvious, and on all three the reader has to rank the candidates unaided.

Two dims arriving at the same verdict by different routes — a control census and a layout census — is what
separates this from a lint ding. The pattern is also stable across the axes we vary: `hive` produced it on
a Filipino phone walk and `marketplace-seller` on an English desktop walk, so it is not a device or a
locale artifact.

**This is a product decision, not a fix to apply.** Choosing which single action is primary on the front
door, on the board, and on the seller dashboard is Ian's call; the instrument can only say that today
there are three or four and the standard is at most two. Recommended shape when it is taken up: keep one
primary per surface and demote the rest to secondary/tertiary weight rather than deleting them — the
`hive` G3 evidence is a *competition* finding, not a "too many controls" finding (24 controls is fine if
one of them is unmistakably first).

### C-H · The ruler read only English, in four independent places
**The largest correction this extension has made, and it moved the platform's headline finding.** Four of
the rubric's vocabularies matched English only, each one-directional — the English page passed and its
faithful Filipino translation failed:

| check | what it could not read | proof |
|---|---|---|
| **B3** readability | Flesch–Kincaid is fitted to English; Tagalog is agglutinative | 193 parallel pairs: FIL grades harder in **180 (93%)**, mean **+4.53**; "Pick the closest match…" 2.3 → its faithful translation **14.1** |
| **E3** freshness | "Kakakalkula lang" *is* the shipped translation of "Recomputed just now" | same page, `analytics`: **EN 100% / FIL 50%** |
| **X1** guidance | "Irehistro muna ang mga asset sa Logbook" names its recovery path | same panel, `inventory`: **EN 100% / FIL 75%** |
| **permission wall** | "Para sa supervisor lang" *is* "Supervisors only" | `audit-log` as a worker: three hard zeros against a page refusing correctly |

**`i18n/*.json` is a parallel corpus, so this is measurable rather than anecdotal** — each English string
sits beside its shipped Filipino. That is how the +4.53 was measured, how the guidance vocabulary was
*derived* instead of guessed for a third time (`tools/derive_fil_guidance_vocab.py`), and how the class is
now audited as a whole (`tools/audit_rubric_language_bias.py`, registered as `rubric-language-bias`).

**Loanwords are why it hid for so long:** of 44 English strings carrying a freshness word, **25 keep that
word through translation**, so each check looked correct right up until it met the 19 that did not.

**The bank was corrected, and only where the ruler was wrong:** **183** B3 findings and **42** E3 findings
withdrawn (all Filipino, all resting *entirely* on the biased check), while every English finding stands
and the Filipino findings carrying a real >20-word, passive, or missing-chip offence stand on that
evidence. B3 fell 1,164 → 981 as a result. Two known limits are documented rather than faked: **PASSIVE**
(0% retention) is inert under Filipino because Tagalog marks voice by affix, and **VERDICT** (2%) is left
alone because widening it with `hindi|wala` would turn E4's raw-stat check off entirely — *a ruler that
excuses too much is the same defect as one that punishes too much.*

**What this changes about the roadmap's own numbers:** some of the Filipino/English gap this extension has
been reporting was the instrument. The honest gap is smaller than the bank said on the morning of
2026-09-10 — and still real: the first all-clean walk of the program (5 pages, 450 dims, zero findings)
was an **English supervisor on a desktop**, the combination most like the people who built the platform,
while the Filipino phone-worker walks produced findings on every path.

**C-G addendum — hive's document outline disappears when the hive is quiet (adversary walk, 2026-09-10).**
The board carries **10 `h2`s in the DOM and renders 3**, and those three are the data-gated attention
sections: *Assets with PM overdue*, *Parts low on stock*, *Your open jobs*. A supervisor in a busy hive
(Dela Cruz) sees `h1` + 3 `h2`s and a usable outline. A worker in a quiet one (Baguio Textile) sees
**`headings=1`, `h2/h3=0`, `blocks=9`** — nine content blocks under the hive's name and nothing between
them, which is what A2 50% is reporting. **The structure is conditional on the data**, so the reader who
most needs orientation — someone whose board has nothing urgent on it — is the one who gets no outline at
all, and a screen-reader user has no way to skim the page.

The mechanism was isolated without re-casting the persona: the three headings and their sections render
together, and seven of the ten `h2`s are alternate states (onboarding, join/create, feedback). Recorded
here rather than fixed, for the same reason as the rest of C-G: giving the always-present blocks their own
standing headings changes the visual design of the platform's busiest surface, and that is Ian's call.

### C-I · The layer the translation mechanism does not cover
`analytics`, walked in Filipino by a supervisor, renders: **"Performance dimension will activate when
planned production rate is configured."** In English, on a Filipino page. The sentence appears in **no
HTML or JS file in the repository and in no dictionary** — the nearest thing in the codebase is an
`ai-gateway` template with different wording ("Performance dimension *excluded until* a planned production
rate is configured"), so the text is composed **server-side**, templated or by the model, and arrives at
the browser already worded. **The page cannot translate a sentence it never authored.**

This is a different and larger class than C-H. Those four were the *instrument* misreading Filipino; this
is the *product* speaking English to a Filipino reader, from the one layer i18n does not reach. The
platform translates its interface carefully — 107 static labels on a single page — and then an AI-composed
explanation lands in English beside them.

**Recorded, not fixed:** the repair is server-side (the generator must take a locale and compose in it),
which is edge-function work behind Ian's deploy gate. The client-side i18n work is already correct here;
adding a dictionary entry would be theatre, because the string never passes through the dictionary.

**How it surfaced is worth keeping.** B3's passive-voice check is English-only and inert on Filipino prose
— a documented limit from the same day. Here that limit became an *accidental oracle*: the only sentences
it CAN match on a Filipino page are the ones still in English, so `passive=2` under FIL was not a claim
about Filipino copy at all — it was two English sentences announcing themselves. **A check that cannot read
the page's language will happily read the parts that are not in it.**

### C-J · `analytics`' control vocabulary fragments at phone width — and the clean pair that proved it
**Three independent sightings, one of them uncontaminated.** `analytics` **R3 100% at 1280, 67% at 390**:
*"cardTreatments=1 · silhouettes=4 for 3 role(s) (pill, 8px, bar, 0px)."* Four control shapes doing three
jobs, on the platform's most-consulted analytics surface and on the device a supervisor actually carries.

**The method matters as much as the finding.** Every earlier device pair this session was *contaminated* —
the two halves sat either side of a ruler change, so B3 and E3 deltas were the instrument moving, not the
width. The final pair was walked **minutes apart: same person, same hive, same language, same lens, width
the only variable.** Across four pages and 360 dims **exactly one dim moved** — this one. `alert-hub`,
`logbook` and `dayplanner` were dim-for-dim identical at both widths.

That quiet baseline is what makes the mover meaningful, and it is the argument for **walking pairs back to
back**: a pair separated by a ruler change cannot tell the two causes apart, and three of the four "device
deltas" seen earlier today turned out to be the ruler.

**Distinguish it from its neighbour:** `alert-hub`'s R3 67% is *unchanged* at both widths, so that one is a
component-vocabulary problem; `analytics`' R3 appears only when the layout narrows, so it is responsive.
Same dim, same page-family, two different owners.

**C-I refinement — it is DATA-CONDITIONAL, and here is the reproduction case.** The English sentence has now
been seen **three times, all in Dela Cruz Delivery Fleet, and never in Baguio Textile Mills**. It surfaces
from the OEE composition only when that hive has **no configured production rate**, not on every Filipino
load. This does not weaken the finding — a server-composed sentence reaching *some* Filipino readers in
English is still unreachable by client-side i18n — but it names what a fix must be tested against.

**A method note this earns:** walking the same page in a different hive changes what the page *shows*.
`logbook` rendered 4,394 characters in Baguio and 1,198 in Dela Cruz; `analytics` renders the English
sentence in one and not the other. The six rows of a walk group differ only in which hive's data sits
behind the screens, and that difference decides **which conditional states render at all** — which is why
every banked note states the vertical it observed.

### C-H closing measurement — two controlled pairs, run after the corrections
C-H claimed the ruler was biased. These two walks measure what fixing it was worth, by holding everything
constant except one axis at a time:

| pair | what varied | dims | dims that moved |
|---|---|---|---|
| **device** — supervisor, FIL, alert→logbook→dayplanner→analytics, minutes apart | 1280 → 390 | 360 | **1** (`analytics` R3, a real responsive fragmentation → C-J) |
| **language** — buyer, desktop, marketplace→seller→analytics→audit-log | EN → FIL | 360 | **0** |

**The language axis is now silent.** Before the corrections this buyer walk would have reported B3 (an
English-calibrated readability formula) and E3 (an English-only freshness vocabulary) on the Filipino side
alone. With the instrument fixed the two cells are **dim-for-dim indistinguishable**, and a second pair —
the supervisor's reporting chain, walked EN/desktop and FIL/phone — came back **identical across 450 dims
and clean on both**.

**Read carefully, this does not say the platform has no Filipino problem.** The same session found
`asset-hub` shipping an English button, `report-sender` composing an English heading, and `analytics` still
emitting a server-composed English sentence no client fix can reach (C-I) — all real, all found *in*
Filipino. What the pairs establish is narrower and more useful: **the rubric no longer manufactures a
language gap, so the gaps it reports from here are the product's own.**

Same discipline both times: **hold the lens constant and walk the halves back to back.** Three of the
"device deltas" seen earlier in the session turned out to be the ruler moving between halves, not the width.

**C-J mechanism — found, and it is not a CSS-value difference.** The raw radius census on `analytics` is
**identical at both widths** (`pill:20, 8px:9, 0px:14, 12px:1`) — no stylesheet changes between them. What
changes is the **geometry**: the four `.phase-tab` controls sit in **one contiguous row at 1280** and
**wrap into a 2×2 grid at 390** (`flex-wrap: wrap`, host 350px, four 175px tabs, two rows).

R3's silhouette test treats a control that forms part of a contiguous bar as wearing *the bar's* shape
rather than its own corner — which is right. So at 1280 the strip reads as one segmented control (3
silhouettes for 3 roles, R3 100%); at 390 the gestalt breaks and each tab falls back to its own **0px**
corner, giving a 4th silhouette (R3 67%). **The square corners are a bar-segment treatment that only reads
correctly while the segments are joined** — detached, they are four square-cornered rectangles that look
like an unfinished control.

**Two defensible fixes, and the choice is a design one:** give the tabs their own radius once wrapped (they
are buttons now, not segments — reduces to 3 silhouettes), or keep the bar intact and let it scroll
horizontally instead of wrapping. Recorded rather than chosen, like the rest of C-G/C-J: both change how a
major surface looks on the device most workers use.

**Why this was worth chasing:** the finding survived four sightings and two controlled pairs, and it still
could have been an instrument artifact — a rubric that mis-detects a bar would produce exactly this number.
Measuring the raw CSS at both widths is what separated "the page changed" from "the ruler changed", and
here the page really does.

### C-K · B3 was grading the hive's maintenance history as if the product had written it
**The rubric states the rule and did not apply it to the one page that most needed it.** B3 grades the
PRODUCT's writing, not the user's — it already spares voice-journal transcripts and community posts,
because holding the app to an 8th-grade / ≤20-word bar for *how a worker talks* is a category error. **A
logbook entry is that same thing written down**, and it was not in the exclusion.

Measured live on `logbook`: **24 of the 34 prose elements B3 graded — 71% — sit inside
`#entries-list .entry-card`**, and they are the hive's own work history: *"Isolated unit (LOTO), cleaned
oil cooler fins with compressed air, verified discharge temp back to 8 °C"*, *"Recorded ISO 10816 readings;
trend stable"*. **The single grade-over-8 offender that every banked logbook B3 finding rested on is one of
those entries** — a technician's record of what he did, scored as if it were interface copy.

**Fixed by extending the same exclusion, not inventing a rule.** Verified in English, where the grade
actually bites: `sentences=51 · grade>8=1` → **`sentences=6 · >20w=0 · passive=0 · grade>8=0`**, B3 100%,
page 100%, with the product's own copy still fully graded. **14 banked findings retracted**, all citing
`sentences=51`; no other page renders an entry list, so no other B3 finding is affected.

**And with that noise cleared, two real ones became visible.** `public-feed` (22 words) and `skillmatrix`
(21 words) fail B3 in **Filipino and pass in English** — the translations outgrew their originals. A word
*count* is language-neutral and transfers; the readability *grade* is not and is withheld. So these are
copy to shorten, not artifacts — and they were only findable once the dim stopped measuring seeded data.

**C-J localised — three controlled device pairs, 1,170 dim-comparisons, two movements.**

| pair (same cast, hive, language, lens; width the only variable) | dims | moved |
|---|---|---|
| supervisor · alert-hub → logbook → dayplanner → **analytics** | 360 | **1** (analytics R3) |
| buyer · marketplace → seller → **analytics** → audit-log | 360 | **1** (analytics R3) |
| worker · community → skillmatrix → achievements → public-feed → logbook | 450 | **0** |

**The two pairs that moved both contain `analytics`; the pair that moves nothing does not.** The responsive
defect is confined to that one page — everything else in the walked set renders the same judgement on a
phone as on a laptop.

That is the useful shape of the result. *"The platform is worse on mobile"* would have been easy to assert
and is **not** what the measurement says: one page's control vocabulary fragments when its phase-tab strip
wraps, and the rest holds. **A cluster of one, precisely located, is worth more than a vague axis-level
worry** — and it tells you exactly which CSS to change.

**C-G addendum, now measured with the same receipt on both sides.** The first version inferred the
data-gated outline from two different walks. The Filipino adversary walk closes it: `hive` reports
**`h2Visible = 0` of `h2InDom = 10`** for a worker in the quiet Baguio hive (A2 50%, *"headings=1, h2/h3=0,
blocks=9"*), where the same page reported **3 of 10** for Rosa in the busy Dela Cruz hive. **Same page, same
markup, same instrument, two hives.** A busy board earns its outline; a quiet one gets none — nine blocks
under the hive's name with nothing between them, and no way for a screen-reader user to skim. **The reader
who most needs orientation is the one the page gives least.**

### C-L · B3's length check was measuring how the HTML is wrapped — and C-K's last paragraph was wrong
**Correction first.** C-K closed by saying `public-feed` and `skillmatrix` fail B3 in Filipino and pass in
English because *"the translations outgrew their originals."* **That is false.** The English original is
**24 words — also over the limit.** It passed for a reason that has nothing to do with translation.

B3's sentence splitter treated **a newline as a sentence boundary**. `public-feed`'s English hint is
hard-wrapped in the markup, so it was chopped into **eight fragments by its own source line breaks** —
including the one-word "sentence" **`You`**, and *"only, never here, unless you share it."* beginning
mid-clause. Longest fragment: **17 words**. It passed. The same prose in Filipino arrives from a dictionary
as **one unbroken string**, is measured as the sentence it actually is, and fails.

**So the check was reading how the HTML happens to be wrapped, not how long the sentences are** — silently
under-reporting hard-wrapped English markup while correctly measuring anything delivered from JSON or JS.
**The asymmetry is structural, not linguistic:** English lives in hard-wrapped HTML, Filipino comes from
single-line dictionaries. Every English page in this program has been graded through that hole.

**Fixed by asking the CSS the question it already answers:** if an element **preserves** whitespace
(`pre` / `pre-wrap` / `pre-line`) a newline is a line the reader sees and still splits; if the element
**collapses** it, the newline is invisible formatting and the text is one flowing run. Verified both ways:
`public-feed` in English now reads **B3 33%** with `worst(24w)` named — exposing a long sentence *and* a
grade-over-8 offender its own markup had hidden — and `shift-brain`'s `[SAFETY] ACTIVE ISOLATIONS`
pre-wrap list still splits per line and still passes, so the case the newline split existed for is intact.

**18 banked rows corrected with `--keep-finding`:** the Filipino sentences really are too long, so the
findings stand; what was withdrawn is the *story* — the true reading is **"this sentence is too long in
both languages, and only the Filipino half was visible."**

**The lesson for the roadmap's own numbers:** the two "clean language pairs" were run through this hole, so
their *zero-dims-moved* result was measured with English under-reported. The device pairs are unaffected
(same markup both halves). Re-running a language pair on the corrected lens is the honest next check.

**C-L confirmed on the corrected lens.** Re-measuring `skillmatrix` with the same cast on a fresh load:
**EN B3 67%** (`grade>8=1`, `>20w=0`) and **FIL B3 67%** (`>20w=1` at 22 words, grade withheld). **The same
score in both languages, for different reasons** — the page is over-grade in English and over-length in
Filipino, and before the fix each language showed only half of that. `skillmatrix` in English had read
**100%**. So the finding is a readability problem in the *content*, not a defect of the translation, and
the earlier framing is retired.

**C-L closing measurement — the language pair re-run on the corrected lens, and the result is better than
either earlier version.** Same cast, same device, fresh loads, three pages:

| page | EN | FIL | why they differ |
|---|---|---|---|
| `community` | 100% | 100% | — |
| `skillmatrix` | **67%** | 67% | — *(EN fails on grade, FIL on length; same score, different half)* |
| `public-feed` | **33%** | 67% | only the withheld English-calibrated grade |

**Both languages now flag the same sentences for length.** The correction did not open a language gap — it
**closed a false one**: `skillmatrix` had read EN 100% / FIL 67%, a one-dim delta that existed only because
the English sentence was hidden by its markup wrapping. On the corrected lens the two agree.

So the honest statement is neither *"the language axis is silent"* (measured through the hole) nor *"the
result is untrustworthy"* (an over-correction): **the residual EN/FIL difference is entirely the documented
withheld grade — a known limit of the instrument, not a gap in the product.** And the pages that fail now
fail in *both* languages, which is what makes those findings worth acting on.

### C-M · Two registries disagreed about which pages a journey crosses — found by a guard refusing a bank
Walking the Tier-D lifetime row **W3709** along the path its **trajectory** declares ("one hive's whole
year", including `project-manager` and `skillmatrix`), `bank_critic_walk` **refused the bank**: the
**critic row** for the same id declares `public-feed` instead of those two. Across the registry,
**332 of the 724 critic rows carrying a page list disagreed with their trajectory's.**

**It is staleness, not a seeding bug,** and the evidence says so precisely: the two lists *inside* each
trajectory (`pages` and `journey.pages`) agree **724 of 724**, and `critic_seed_missing.py` copies the
trajectory's list faithfully. Those critic rows were seeded from an earlier revision and the trajectories
moved on.

**The cost is paid by whoever walks next, and I paid it here** — reading the trajectory (the natural
source; it holds the journey definition, the archetype, the moments) produces surveys the bank then
refuses; reading the critic row walks a path the trajectory no longer claims.

**Repaired with `tools/resync_critic_pages.py`, and the boundary is the point:** **249 `pending` rows**
re-pointed at their trajectory's list; **221 already-walked rows deliberately left alone**, because
re-pointing a walked row would leave it claiming a journey **its own banked findings do not cover** — a
silent inconsistency worse than the visible one it replaces. The residual drift is now a counted, reported
quantity (221) rather than a surprise, and **zero pending rows** remain adrift, so the next walker meets a
registry that agrees with itself.

**The guard is what found this.** It exists because a reused glob once nearly attributed three unopened
pages to a journey; it has now caught a second, different class — and both times the refusal was correct
and my walk was wrong.

**C-L, what the correction actually bought — two empty states fixed the same day they became visible.**
Both are the first thing a person with nothing yet reads, and both had read **100%** all program:

| page | before | after |
|---|---|---|
| `asset-hub` | **B3 0%** — a 21-word sentence, a passive opening, grade 10.6, all on one screen | **100%** · *"No asset here is Critical yet. Mark your top 5 assets that block production. That tells the AI where to look first."* — worst grade **4.5** |
| `project-manager` | **B3 33%** — one **38-word** sentence at grade 13.8, the longest found anywhere in the program | **100%** · split into four; the example and the button name unchanged |

A second `project-manager` clause (grade 8.4) stacked all four project kinds behind one instruction. It was
**split, not simplified** — *work-order*, *shutdown*, *CAPEX* and *contractor* are the platform's own
vocabulary and a plant supervisor knows them; what was wrong was the stacking. Both halves now read 2.5 and
7.8 with every term intact.

`sw.js` v354 → **v355** (asset-hub is precached; project-manager is not). `index`'s front-door sentence
(grade 13.1) is **left for Ian** — it is positioning copy, not an empty state, and rewriting it is a
different kind of decision.

**C-G refinement — `hive`'s CTA competition is SUPERVISOR-side, and that narrows the fix.** Walked as a
**worker** (English, phone), `hive` reports **A2 50%** and **N1 75%** but **not** G3/A3 — the worker's board
renders fewer controls, so the primary-CTA competition never arises. Every G3 0% / A3 75% reading on this
page has come from a **supervisor** cast. So the fix is scoped to the supervisor's board, not the page as a
whole, and it can be made without touching what a worker sees.

The worker's own hive finding is the other one and it is unchanged: **`h2Visible = 0` of 10** in a quiet
hive — nine blocks under the hive's name, no headings between them, and no G3 competition to distract from
the fact that there is nothing to navigate by either.

### C-N · The one sentence under a blank tile named the wrong gap — and only a hive missing that exact half could reveal it
Walked as the **fleet supervisor** (English, phone-390, Dela Cruz Delivery Fleet), `analytics` read
**B3 67%** on `passive=2`: *"Performance dimension will activate when planned production rate is
configured."*, rendered twice under an OEE tile showing **"—" / NO DATA**.

**The passive voice is the measured finding. Reading the payload behind the tile is what made it a real
one.** Through Rosa's **own PostgREST token**, `analytics_snapshots` (phase `descriptive`,
`payload->oee->oee_by_asset`) holds **8 assets, every one with `availability_pct = 100` and
`quality_readings = 0`, and not one with an `oee_pct`.** So the half that blocks OEE in this hive is
**Quality** — and the tile's only sentence told a fleet supervisor to configure a **planned production
rate**, which is the **Performance** input. **Following the single instruction on screen would have
changed nothing.**

**Why it was there:** `analytics.html`'s `oeeAvg == null` branch surfaced the payload's **top-level
`note`** verbatim, and that note is about the Performance dimension *whatever* the reason the number is
missing. One string doing two jobs — *"here is what is partial about a computed OEE"* and *"here is why
there is no OEE at all"* — and only the first job was true.

**Fixed at both levels, each in its own file:**

| level | before | after |
|---|---|---|
| `analytics.html` (the tile) | surfaced the top-level note whatever was missing | reads which half the per-asset rows lack: *"No quality readings yet on 8 assets. Add Production this shift when you close a Breakdown entry."* |
| `python-api/analytics/descriptive.py` (the note) | *"…will activate when planned production rate **is configured**."* — passive, no actor | *"Add each asset's **Ideal Cycle Time** to unlock the Performance dimension."* — active, and the asset form's own field label |
| `supabase/functions/ai-gateway/index.ts` (the same clause via the assistant) | *"…excluded until a planned production rate **is configured**."* | *"This average leaves out the Performance dimension; each asset's Ideal Cycle Time unlocks it."* |

**The control had to be named the way the person reaches it.** "Planned production rate" appears on **no
screen in the product**; what exists is the **Ideal Cycle Time** field on the asset form
(`asset_nodes.ideal_cycle_time_seconds`, ISO 22400-2 §3.4.18) and **Production this shift** — *Good units
produced* / *Total units attempted* — on a **closed Breakdown** logbook entry. Both sentences now name a
control a supervisor can actually go and use.

**Verified live on the same hive after the edit:** `analytics` B3 back to `long=0 · passive=0 ·
overGrade=0`; the two residual findings are the known ones (**R3** = C-J's phase-tab wrap at 390,
**N1** = the documented mechanism census, in English). `sw.js` v355 → **v356** (`analytics` is precached).
**The edge function is edited but NOT deployed — Ian's gate.**

**What this adds to the program's method: a hive is part of the lens.** This defect is invisible in every
plant hive walked so far, because those hives *have* quality readings — the tile renders a number and the
sentence never appears. It took a **fleet** hive, whose vehicles log downtime but no units, to render the
one branch where the sentence is both shown and wrong. The rubric found the *voice*; the **vertical**
found the *lie*. Same shape as `hive`'s A2, which only appears in a quiet hive — **a page's score is a
claim about one persona, one auth state, one device width, and one hive's data.**

### C-O · A person with no hive had no identity, so the product told a signed-in person to sign in
Walking **J30** (the energy-audit journey) as a **solo owner** — `jun.vanowner@workhive.test`, *"a
one-person technician who owns his van and no hive"*, signed in and session-verified — **six member
pages plus `hive.html` redirected him to `index.html?signin=1`**, where a modal read **"Sign in to open
Eng. Design."** over a Username/Password form whose only alternative was *"Don't have an account?
**Create one for free**"*.

**He had an account. He was signed into it.** A second one would land in exactly the same state, and
**`hive.html` — the one page that could have given him a hive — sat behind the same gate.** A closed
loop, for a persona the platform's own RLS `SOLO` branches, its solo seeder and its roadmap all treat as
first-class.

**The mechanism, confirmed in code and through his own token.** `utils.js`
`restoreIdentityFromSession()` resolves the person through **`v_worker_truth`, which carries one row per
hive MEMBERSHIP**. Read as Jun: **0 rows** → `WORKER_NAME` empty → every page gating on it redirects.
**The multi-hive end of this same view was fixed months ago** (two rows broke `.maybeSingle()`); this is
**the other end — zero rows** — and it had never been walked, because until the solo personas were
seeded (2026-09-08) nobody hive-less could sign in at all. That earlier J11 attempt concluded *"it is the
cast, not the product"* — correct **then**, because the cast could not authenticate. With a person who
**can** sign in, the same pages give the opposite answer.

**Why it stayed invisible: sign-up warms the cache.** `index.html`'s Create Account writes
`wh_last_worker` on success, so the device the account was made on always works. The bounce appears only
on a **second device**, in a **private window**, or after storage is cleared — the same *"the bounce warms
the cache so it never looks reproducible"* shape the file's own comment records for multi-hive users.
**Every reading in this walk was taken with `wh_last_worker` deleted immediately before the navigation,**
so none of it is the cache answering.

**Fixed by reading the row the product's own sign-up writes.** `worker_profiles` is keyed on `auth_uid`,
**not** on membership, and Create Account inserts `username` + `display_name` into it — `index.html`'s own
comment says a brand-new account with no membership *"stays in solo mode"*. The resolver now falls back to
that row when the membership view is empty (**`deactivated_at` honoured** — a closed profile restores
nothing), then to the session's `user_metadata`, where admin-API-created accounts carry their name.
**One extra REST call only when the membership lookup already came back empty**, so the hive-member path
is untouched. `sw.js` v356 → **v357** (`utils.js` is shell).

**Verified with a cold cache on every page:**

| page | before | after |
|---|---|---|
| `engineering-design` | bounced to `?signin=1` | **96%** |
| `project-manager` | bounced | **100%** |
| `project-report` | bounced | **100%** |
| `report-sender` | bounced | **100%** |
| `hive` | bounced | renders *"Join or create a team…"* with **Create a Hive** / **Join with Code** |

**That door was built all along. It was simply unreachable by the only people who needed it** — which is
the sharpest form this defect class takes, and kin to the retired page that hid the only live control.

**C-O second half — the program's first full-rubric reading of learn and calculator pages.** The public
half of this journey was walked genuinely anonymous (signed out, every `wh_*` key cleared). The
calculator reads **100%**, `learn/index` **97%**, and the two long-form articles **90%** and **85%**.

Their heaviest finding is **B3 0% on both** — **37** sentences over twenty words on the RA 11285
checklist and **18** on the calculators guide, worst cases of **38** and **62** words. **That is a content
question, not a control question, and it is recorded rather than rewritten:** a 15,866-character
compliance article is a different artifact from a tile subtitle, and setting the bar for it is a
judgement about the audience — **left for Ian**, like `index`'s front-door sentence.

**Four smaller ones are unambiguous and are the next fix pass:**

| finding | page | detail |
|---|---|---|
| **C2 99%** | calculators guide | worst contrast **1.11:1** on *"Open Engineering Des…"* — effectively invisible text |
| **V1 0%** | calculators guide | two content blocks **overlap at 390** (*"Skill matrix"* × *"Digital logb"*) |
| **D1 0%** | both index-style pages | one **icon-only control with no accessible name** |
| **G1 / I2 0%** | both articles | no status region, no reserved/optimistic block |

**What this adds to the method: the ninth axis is HAVING a hive at all.** Every walk before this one cast
somebody who belonged somewhere. `hive`'s A2 needed a *quiet* hive; C-N's OEE tile needed a hive missing
*quality*; this needed a person with **no hive**, and it found the largest defect of the extension so far.

### C-P · The four public-page findings, triaged: two were the page, two were the ruler
C-O's walk left four unambiguous findings on the learn/calculator pages. Triaging each one against
the live DOM split them **exactly down the middle**, and the split is the lesson.

**THE PAGE WAS WRONG — twice, and both were shared across the whole public corpus.**

| # | finding | what it actually was | reach |
|---|---|---|---|
| 1 | **C2 1.11:1** on *"Open Engineering Des…"* | **pure cascade.** `.cta-btn { color:#162032 }` is specificity **(0,1,0)**; the button sits in the article body and `.prose-wh a { color:#5FCCE8; text-decoration:underline }` is **(0,1,1)**. The later, more specific rule won, so the page's primary CTA rendered **light blue on its orange gradient, underlined** — a button wearing a prose link's clothes. The declared navy was never wrong; **it was never applied.** | **27 pages** |
| 2 | **breadcrumb 4.13:1** | `rgba(244,246,250,0.45)` at 13.6px on `#162032` — **below WCAG AA 4.5**. It is the trail that tells a **search arrival** where they have landed, which is the one navigation aid that audience has. | **95 pages** |

Fixed by `tools/fix_cta_specificity.py` (`.prose-wh a.cta-btn` = **(0,2,1)**, beating (0,1,1) **without
`!important` and without reordering** — ordinary in-article links keep looking like links) and
`tools/fix_breadcrumb_contrast.py` (alpha **0.45 → 0.55**). The second tool **derives the ratio rather
than asserting it**: compositing #F4F6FA over #162032 and applying the WCAG luminance formula gives
**4.12:1 at 0.45 — matching the rubric's measured 4.13, so the model is calibrated** — then **5.47:1 at
0.55**. `--verify` re-reads all 95 files and re-derives: **95 at or above AA, 0 below.** Verified live:
CTA now `rgb(22,32,50)`, `text-decoration:none`; breadcrumb `0.55`; **C2 offenders `[]`**.

**THE RULER WAS WRONG — twice, and both fire only on long-form prose, which is exactly what this wave
just brought onto the full rubric.**

| # | finding | why it was false | fixed by |
|---|---|---|---|
| 6 | **V1 0%** — *"1 content overlap: A"Skill matrix"×A"Digital logb""* | **a wrapped inline link's bounding box is a lie.** `getBoundingClientRect()` on an inline element spanning two lines returns the **UNION** of its line boxes: `<a>Skill Matrix guide</a>` reported `[20,18583,320,18638]`, a 300×55 rectangle whose middle is the **empty tail of line 1 and the empty head of line 2** — space the link does not occupy. Another link sitting in that gap measured a **0.989 overlap**. `getClientRects()` proves it: the wrapped link has **2 line boxes, neither touching** the other link. | compare **line box to line box**, not the union |
| 7 | **D1 0%** — *"0/1 icon-only controls named"* | **an image's `alt` IS the control's name.** The offender is the site's own logo link: `<a href="/"><img alt="WorkHive"><span class="hidden sm:…">`. At 390 the wordmark is hidden, leaving a bare image, and the `<a>` has no `aria-label` — but **WCAG H30 makes the img's alt the link's accessible name**, and a screen reader announces *"WorkHive, link"*. The lens asserted something false about the page. | read what the **browser** reads: `aria-label`, `aria-labelledby`, `title`, **and a non-empty `alt`** |

**Both were systematic and one-directional.** V1's would fire on **any paragraph with two inline links
where one wraps**; D1's on **any control named through an image**. Retracted with the mechanism recorded:
**V1 on 5 rows** (the only `content overlap` findings in the entire 3,959-row registry — every other V1
finding is the untouched `widget covers header` branch on `shift-brain`) and **D1 on 5 rows × 2 pages**
(**all ten D1 findings the registry has ever held**, on the only two pages whose wordmark hides at phone
width).

**`free-engineering-calculators-philippine-plants`: 85% → 89%**, two points earned by the page and two
returned by the ruler — and the walk says which is which.

**Seven instrument faults now, and the shape has not changed once:** every one made the platform look
worse than it is, and every one was found by walking a surface the lens had never been pointed at. B3's
splitter needed a hard-wrapped file; B3's grade needed a Filipino page; the permission and FRESH
vocabularies needed Filipino copy; V1 and D1 needed **long-form prose with inline links and a hidden
wordmark**. *An oracle's vocabulary is part of the oracle* — and so is the corpus it has never met.

### C-Q · The cast was a half-created account, and a reversible probe is what told the two apart
Walking the solo owner's project round (`engineering-design → project-manager → project-report →
analytics`) on the far side of C-O's fix, `analytics` rendered **1,237 characters** with the OEE tile
reading **"Unavailable"**, and the console carried four **403 "No worker profile for caller"** refusals
from `analytics-orchestrator`.

**That reads like a product defect and is not one.** `tools/seed_solo_personas.py` creates its people
through the **GoTrue admin API**, which writes `auth.users` and nothing else — but `index.html`'s own
Create Account inserts a **`worker_profiles`** row (`auth_uid` / `username` / `display_name`) right after
`signUp()`. The seeded solo owner was therefore missing the one row **every real account has**, and the
edge function was correct to refuse him.

**A reversible probe settled it in one step, and answered a second question at the same time.** Inserting
a `worker_profiles` row for Jun **through his own token**, then reloading with a **cold cache**:

| | as seeded | with the profile row |
|---|---|---|
| `analytics` | 1,237 chars · OEE **"Unavailable"** · 4× 403 | **5,935 chars** · real KPIs · no refusal |
| identity leg exercised | `user_metadata` only | **`worker_profiles.display_name`** — the leg a real solo owner travels |

The row was then **deleted and audited to zero** (0 probe rows, 0 rows for Jun). So the probe **proved
C-O's primary fallback**, which Jun's own account could not exercise, **and** proved the 403 was a
fixture gap rather than a platform one. **The difference between a finding and a false ceiling was one
reversible write.**

**The seeder now writes what sign-up writes.** `--revert` needs no new branch:
`worker_profiles_auth_uid_fkey` is **`ON DELETE CASCADE`** — checked against `pg_constraint`, not assumed.
Both personas now carry a profile and **0 hive memberships**, which is exactly the shape a real solo owner
has after signing up.

**Both fixes then met on a persona neither was written for.** With the profile in place, Jun's
`analytics` computes **6,349 characters** and his OEE tile reads:

> *"No quality readings yet on **1 asset**. Add Production this shift when you close a Breakdown entry."*

C-O let him reach the page; C-N told him the truth about what is missing when he got there; and
`_anNoun` put it in the singular, because he owns one van.

**One more thing the probe found, recorded because the silence is the part that matters:**
`worker_profiles` accepts an **INSERT** from its owner and returns **0 rows for their DELETE, with no
error** — the row needed the owner connection to remove. A profile a person cannot delete is a defensible
design; **a delete that reports success while changing nothing is the fourth state a reader misreads as
fact.**

### C-R · The tap-target fix made two links fight over the same 26 pixels — and it is the corrected V1 that caught it
Walking **J15, the machine client** (`plant-connections → integrations → hive → audit-log → logbook`)
as **Hector Salvador, supervisor of Manila Electronics Assembly** — chosen deliberately over that hive's
other members because **Pablo Aguilar is one of the platform's two `marketplace_platform_admins`**, and an
admin cast cannot be trusted to report what an ordinary supervisor sees on `hive` or `audit-log`.

**`hive` V1 0%, and this time the lens was right.** The approval-queue sentence renders its destinations
as inline links inflated to a **44px box** — `min-height:44px; line-height:44px; margin:-14px` — inside a
`<p class="text-[12px]">` whose **line-height is 18px**. The negative margin keeps the **text flow**
looking normal, and it does. The **hit areas** are the problem:

| link | box | |
|---|---|---|
| `Asset Hub` | `[196, 4525, 270, 4569]` | 74 × 44 |
| `2 shift briefings` | `[157, 4543, 264, 4587]` | 107 × 44 |
| **overlap** | **68 × 26 px** | **54% of the smaller target** |

Once the sentence wraps, the two 44px boxes land on adjacent 18px lines and collide. **A tap in that band
lands on whichever link paints last, not the one under the finger.** The accessibility fix made the page
harder to use for exactly the person it was written for.

**WCAG 2.5.8 says the inflation was never owed.** Its **Inline** exception exempts a target *"in a
sentence or whose size is otherwise constrained by the line-height of non-target text"* — and these are
**nine characters inside a 101-character line**. The comfort belongs to the line-height, not to the
anchor's box. They are now plain inline links, the shape `skillmatrix`'s `<a>Resume</a>` and
`voice-journal`'s mailto already use and which the rubric's own `_inlineProse` recognises and exempts.
**Verified live: 17px boxes ending at 4555 and starting at 4556 — no overlap. V1 100%, `hive` 96% → 97%.**

**This is also the first test of the same day's V1 correction, and it passed in both directions.** Hours
earlier V1 was found counting a **wrapped inline link's union rect** as a solid box, making prose collide
with itself on the learn pages (C-P). Here the corrected lens flagged a **genuine 54% overlap** between
two single-line-box inline-blocks. **A corrected ruler that still bites is the only kind worth
correcting** — the risk in every lens fix is that it stops measuring; this one did not.

**`plant-connections` B3 0% — all three faults on one screen.** *"No sensors **are mapped**"* (passive,
no actor), a **29-word** sentence, and **grade 15.3** on it, the highest on the page. That paragraph is
the whole of what a plant which has not connected a gateway yet reads. Split into five short sentences,
every one **under the twelve-word floor where Flesch-Kincaid stops being a valid ruler**, with the
platform's own vocabulary intact — *Anomaly Engine 2.0*, *OPC-UA / MQTT*, *logbook*, *PM signals* and the
guide's exact name are terms this reader already knows, and simplifying them would cost meaning rather
than buy clarity. **98% → 100%**, B3 `long=0 · passive=0 · overGrade=0`.

`sw.js` v357 → **v358**. `hive`'s other three findings are the **standing supervisor cluster on a third
hive** — G3 0% (**34** controls, 3 primary CTAs), A3 75%, C1 67%. Manila is the busiest board walked so
far (34 controls against Dela Cruz's 25) and **the cluster scales with the board**, which is the argument
for scoping C-G's fix to the supervisor's board rather than to the page.

### C-S · C-J is CLOSED — and the mechanism recorded for it was wrong
**Correction first.** C-J's entry above states that at 390 the four `.phase-tab` controls *"fall back to
their own **0px** corner, giving a 4th silhouette."* **They do not.** Re-measured by replicating R3's own
`roleOf`/`shapeV` against the page root: the tabs' parent still has `gap: 0` and the tabs still have
`border-radius: 0`, so **R3's joined-group test reads them as ONE BAR at both widths.** The tabs were never
the fourth silhouette. That sentence was inference from the wrap being the one visible difference, and a
visible difference is not a mechanism.

**What the fourth silhouette actually was.** Scoped to `.page` at 390:

| silhouette | role | count |
|---|---|---|
| `pill` | select | 20 |
| `8px` | press | 12 |
| `bar` | navigate | 4 ← *the phase tabs, read as one bar* |
| **`0px`** | **press** | **6 ← the `.kpi-toggle` expanders** |

**Four silhouettes, three roles.** Twelve press controls on the page — `refresh-btn`, `details-toggle`,
`showall-toggle` — say *"I am a button"* with an **8px** corner. Six say it with a **square** one:
*Availability %*, *MTBF*, *MTTR*, *PM Compliance Rate*, *Downtime Pareto*, *Failure Frequency*.

**And it is not a responsive defect at all.** The toggle measures **308px inside a 352px card — 87.5%**,
just under `isCardAnatomy`'s **90%** cut-off. At desktop the same control crosses that line and is excluded
as card anatomy, which is the *entire* reason R3 read 100% at 1280. **A dim that flips on a ratio crossing
a threshold still names a true defect — it just names it at only one width.** The inconsistency was there
at every width; only one width could see it.

**The fix is one line, and where it goes is itself a finding.** The border and tint arrive from a
**JS-written inline style** that sets no radius, so `.kpi-toggle`'s class rule is where the corner belongs
and nothing inline overrides it: `border-radius: var(--wh-radius-sm)`. **8px is press-only on this page**,
so joining it introduces no same-shape-different-job collision.

| | before | after |
|---|---|---|
| `analytics` @ 390 | R3 **67%** · `pill, 8px, bar, 0px` · 4 shapes / 3 roles | **100%** · `pill, 8px, bar` · **3 / 3**, 0 collisions |
| `analytics` @ 1280 | R3 100% (by exclusion, not by consistency) | **100%** · identical shape set |
| page | 99% / 100% | **100% at both widths** |

**The device delta is gone because the inconsistency is gone** — not because a threshold moved. `sw.js`
v358 → **v359**.

**The false start is worth recording too.** The first attempt followed the written mechanism: give the
wrapped tabs their own radius and a gap. It **made the reading worse in kind** — the gap broke the
joined-group test, so the tabs stopped being `navigate`, the `bar` silhouette vanished, `roleCount` fell
3 → 2, and their new 8px corner collided with press (`SAME-SHAPE-DIFFERENT-JOB`). Same score, worse page.
It was reverted, and the fix that stuck came from **reading the oracle's own code and replicating it
against the live page** rather than from reasoning about what the wrap looked like.

**Two lessons this earns, and both are about the same trap.** A mechanism must be *measured*, not inferred
from the one thing that visibly changed — and when a dim is width-sensitive, the first question is not
*"what does the layout do differently?"* but **"what does the ORACLE do differently?"** Here the answer
was a 90% ratio, and it was hiding a defect that had nothing to do with width. Kin to the seven instrument
faults: this time the ruler was right and my *explanation* of it was the thing that was wrong.

### C-T · The last standing R3, closed — and a prior session's note was the thing that was wrong
With `analytics` fixed (C-S), **`alert-hub`'s R3 67% was the only R3 left on the platform**: four
silhouettes for three roles, *unchanged at 390 and 1280 on every walk that ever touched it*, which is what
had long separated it from `analytics`' width-sensitive one. Applying C-S's method — replicate R3's own
`roleOf`/`shapeV` against the page root instead of reasoning about the layout:

| silhouette | role | n | what it is |
|---|---|---|---|
| `8px` | press | **60** | `.alert-dismiss` **actions** — *"Snooze 7d"*, *"Handled"* |
| `pill` | select | **30** | `.alert-dismiss` **toggle** — *"Seen"* (`aria-pressed`) |
| `bar` | navigate | 8 | the filter `.chip`s |
| **`12px`** | **press** | **4** | **Refresh, two Show-details, Load More** |

**The 8px is deliberate, and that is the whole argument.** Inside the single component that defines this
surface, the page already distinguishes **an action (8px) from a state toggle (a pill)** — the same
`.alert-dismiss` family, two shapes, two jobs, correctly. The page has a press vocabulary and it is 8px.
Four page-level controls simply never joined it.

**A 2026-09-06 comment in this file asserted the opposite** — `/* R3 press = 12px */` on `.gate-btn` — and
standardised toward the **minority** shape. It read one control and generalised; the measurement reads
102 and disagrees. The comment is corrected in place rather than deleted, because *why* a wrong value was
chosen is the part worth keeping.

All four now use `var(--wh-radius-sm)`. **Verified at both widths: `8px, bar, pill` — 3 shapes, 3 roles,
0 collisions, R3 100%.** `sw.js` v359 → **v360**.

**Recorded, not claimed: `alert-hub` C1 moved 100% → 67% between the walk and the re-measure**
(`distinct` font sizes **10 → 11**) while the alert content changed (**5,398 → 5,451 chars**). A
border-radius edit cannot add a font size, so this is content, not regression — but it says something
worth keeping: **the page sits exactly ON the type-scale threshold and tips when one more element
renders.** A dim that depends on which alerts happen to be showing is one element away from failing at
any time, which is the same fragility C-S found in `isCardAnatomy`'s 90% ratio. Both will be confirmed by
the next `alert-hub` walk rather than asserted here.

**Two R3s, two sessions, one method.** `analytics` (C-S) and `alert-hub` (here) were the platform's only
R3 findings and both turned out to be **a small group of controls wearing a corner the page's own majority
does not use** — not layout, not the responsive grid, not the phase strip. Neither was diagnosable by
looking; both fell in minutes once the **oracle's own code was replicated against the live page.**

### C-U · The worker's locked card — 391 characters, recorded on every worker walk, never touched
`audit-log`'s supervisors-only gate is **the whole of what a worker can read on that page** — 391
characters — and it held **the worst prose in the program per character**. It was recorded at 390 and at
1280, on Baguio and on Manila, across the whole extension, and never fixed:

| | before | after |
|---|---|---|
| **B3** | **67%** — one sentence at **grade 15.3**, the highest single-sentence grade left anywhere: *"The audit log **is visible to** hive supervisors so they can review approval, rejection, and member-management decisions."* | **100%** — *"Only supervisors can open the audit log. It records approvals, rejections and member changes for your hive."* Two sentences, both **under the twelve-word floor** where Flesch-Kincaid stops being a valid ruler, active, **actor first**. |
| **the way out** | **"Back to Home" → `index.html`** — a worker who *has* a hive sent to the **marketing front page**. An exit, not a next step. | **"Open Hive Board" → `hive.html`** |
| page | 99% | **100%** |

**The page's own vocabulary already had the better answer.** Twelve lines above, the *no-hive* gate card
offers **"Open Hive Board"** to the person who has no hive — and the *wrong-role* card, for a person who
demonstrably has one, offered the door. Same file, same component, one adopted the useful action and the
other did not. The fix **reuses that card's exact key (`p_openhiveboard_19ea`)**, so the Filipino string
is the one already shipping rather than a second translation of the same three words.

**The i18n contract was honoured rather than worked around.** The first attempt hand-wrote a `data-i`
key — and `--extract` **skips elements that already carry one**, so the key silently had no translation.
Removing the attribute and letting `tools/i18n_page_dict.py` own it produced `p_onlysupervisorscanope…_5b12`,
pruned the stale `p_theauditlogisvisibletohivesu_b2bb`, and left the Filipino authored in the page's own
loanword convention (*supervisor*, *audit log*, *approval*, *rejection*, *member* kept; the connective
language translated). **A generated key must be generated** — the same rule that took the hand-authored
`data-i="find"` out of `asset-hub`.

**Left open, deliberately: A1 still reports `cta=0`** on this card even though it now carries a working
`<a class="gate-btn">`. Both gate cards on this page behave the same way, which points at **oracle scoping**
— a gate card is not a page hero — rather than a page defect. **Two lens corrections already landed today
(C-P) and a third must be earned by evidence, not by convenience**, so this is recorded for the next walk
to judge rather than fixed to make a number move.

`sw.js` v360 → **v361**.

### C-V · The third R3 — one silhouette doing TWO JOBS, and the platform's R3 backlog is now empty
`analytics` (C-S) and `alert-hub` (C-T) were both *one silhouette too many*. `engineering-design`'s R3 is
**the other half of what R3 grades**: `silhouettes=3 for 2 role(s) · SAME-SHAPE-DIFFERENT-JOB: **pill worn
by press+select**`. The census, taken by replicating the oracle against the live page:

| silhouette | role | n | what it is |
|---|---|---|---|
| `pill` | **select** | 8 | six `.discipline-pill` filters + the Units switch — all carrying `aria-pressed` |
| `pill` | **press** | 2 | `.recent-chip` shortcuts — *"Storm Drain / Stormwater"*, *"Bolt Torque & Preload"* |
| `8px` | select | 1 | `.page-tab.active` |
| `12px` | press | 1 | `.btn-primary` — *"Run Calculation"* |

**A pill means "filter" on this page, and two controls used it to mean "go."** A reader meeting a pill
cannot tell whether it narrows the list or leaves it — which is the precise harm R3 exists to catch, and
strictly worse than an extra shape, because an extra shape is only noise while a shared shape is a
**wrong promise**.

**Fixed toward what the page already says:** `12px` is its press shape — what `.btn-primary` wears — so
the shortcuts now look like the small actions they are and the pill goes back to meaning exactly one
thing. **Verified: `8px, 12px, pill` — 3 shapes, 2 roles, 0 collisions, R3 100%, page 96% → 97%.**
`sw.js` v361 → **v362**.

**All three R3 findings on the platform are now closed, in one session, by the same move.** None was
diagnosable by looking at the page:

| page | what the reading looked like | what it actually was |
|---|---|---|
| `analytics` | a responsive wrap fragmenting a tab strip | six `.kpi-toggle` expanders with a square corner, visible only at 390 because a **87.5% / 90%** card-anatomy ratio crossed a threshold |
| `alert-hub` | component vocabulary, four shapes for three roles | four page-level presses at 12px against **60** at 8px — and a prior session's comment had standardised toward the **minority** |
| `engineering-design` | four shapes doing three jobs | a **collision**: the filter pill lent to two navigation shortcuts |

**The method is the transferable part**: read the oracle's own `roleOf`/`shapeV`, scope it to the same
page root the lens uses, and print the shape→role census. Every one fell in minutes. Reasoning about what
the layout *looked* like produced a wrong mechanism (C-S) and a fix that made the reading worse (C-S's
false start); **replicating the ruler produced the right answer three times out of three.**

### C-W · A signed-in owner with no hive read another hive's PM programme — found by a rubric dim about typography
Walking the solo owner's project round at desktop, `analytics` reported **B5 0% · 45 leaks**, sampling
`"24f9ccb4-8ec4-41aa-aa1e-71d522819623: Visual…"`. B5 is a *presentation* dim — it objects to raw
identifiers in front of a reader. Following it to the DOM found **69 UUIDs on one page**, in two places:

- `#pm-task-list` → `<span class="label">24f9ccb4-…: Visual + amp draw check</span>`
- `#kpi-2` → `<td class="machine-name">018da837-…</td>` — a cell whose whole job is an asset name

**Then the question of *whose* assets those were.** Jun owns **0 `pm_assets`**. Those five sampled ids all
belong to **Baguio Textile Mills — a hive he is not a member of** — and while the *names* failed to
resolve, the **task text rendered perfectly**: *"Visual + amp draw check"*, *"Discharge pressure log"*,
*"Vibration trend reading at DE/NDE"*, *"Auto-drain function check"*. **Another tenant's maintenance
programme, legible on a stranger's screen.**

**The mechanism is one missing leg, and the file's own comment already feared it.** Every sibling fetch in
`analytics-orchestrator` uses the pair `if (hiveId) … else if (workerName) …`, so a solo caller is bound
by `worker_name`. **`scopeQ` alone binds on `assetIds` OR `hiveId` and has no third leg** — and
`v_pm_scope_items_truth` is **RLS-DISABLED by design** (it expects an explicit filter), so there is no
second line of defence. A solo owner with **zero assets** skipped the asset filter, had no `hiveId`, and
the read came back **unfiltered**. The comment sitting on those very lines said *"bind to the hive to
avoid a cross-tenant read"* — it guarded the hive case and left the solo one open.

**Two defects, three lines, both fixed:**

| | before | after |
|---|---|---|
| **binding** | nothing bound the query for a hive-less caller with no assets | `scopeUnbound` returns **an empty list** — a caller who owns no scope items honestly has none |
| **naming** | `assetMap[s.asset_id] \|\| s.asset_id` — wrote the raw UUID whenever the assets fetch was empty | the view **already carries `asset_name` and `asset_tag`**; they simply weren't selected. Now selected and preferred, with `"Unnamed asset"` last. **Never the id.** |

The same raw-id fallback on `pm_completions` was fixed in the same pass — that query *is* bound by
`worker_name`, so it never crossed tenants, but it could still show a reader a UUID.

**Verified live on both sides, and the second number is the one that matters:**

| | before | after |
|---|---|---|
| solo owner (`jun.vanowner`) | 69 UUIDs · **6,349 chars** | **0 UUIDs · 3,021 chars** |
| hive member (`bryangarcia`, Baguio) | 100% · 5,961 chars | **100% · 5,961 chars**, 5 PM tasks, now named |

**The page got *smaller* because it stopped reading data that was never his.** And the member path did not
merely survive — it improved: those same tasks now render as *"Siemens Simotics SD 200L: Visual + amp
draw check"* on the board where they belong.

**What this says about the method.** A dim about **typography** found a **tenant-isolation** defect. B5
cannot see hive boundaries; it can only see that a string looks like an identifier. The UUID was the
*symptom* of a query returning rows the caller had no claim to — and following a cosmetic finding to its
data source is what turned it into a security fix. **The ninth axis did the rest:** every walk before the
solo personas became castable met a caller who had a hive, so the one query missing its solo binding was
never exercised. **`analytics-orchestrator` is edited locally and NOT deployed — Ian's gate.** The local
stack serves functions from disk, which is why both readings above are real.

**C-W addendum — the analytics readings above were served LIVE, and the readiness gate that says otherwise
is probing the wrong address.** `run_platform_checks.py --gate-only` reports `FAIL python_api — The read
operation timed out`, and a host `curl http://127.0.0.1:8000/` refuses the connection. Both are true and
neither means the service is down: `docker ps` shows `workhive_python_api` exposing **`8000/tcp` with no
host port mapping**, and its own log shows `POST /analytics -> 200` **six times at 14:13:24** — the exact
second the member analytics page was surveyed, called from `172.18.0.8` (the edge runtime) over the
**Docker network**. Two valid local topologies exist — host-run `uvicorn` on `localhost:8000`, or
containerised and reachable only inside the network — and the readiness probe assumes the first while this
machine runs the second. **Recorded, not "fixed": silently rewriting a readiness gate to match one
machine's topology is how a check stops meaning anything.** The point that matters for today's evidence is
the one the log settles — **nothing above was graded off a stale snapshot.**

### C-X · C-G's `hive` half was never a product fork — the page had already written the rule, and a later addition broke it
C-G filed `hive`'s **G3 0% / A3 75% (`primaryCta=3/2`)** as *"a product decision, not a fix to apply…
Ian's call."* **Reading the page's own source settles it differently.** `#ss-action` carries this comment:

> *"Arc P · Wave 1 (**P3 one primary action**): the recommendation ends in **ONE primary button** that
> OPENS the named surface"*

and `#ss-service-provider`, twelve lines below, carries this one:

> *"**Pure ADD**: the P3 walk verified no other element on this page surfaces the provider role."*

**A later addition put a second solid-orange `.ac-cta` directly beneath a card that had declared itself
the single primary.** With the handover button that makes three. **This is not a positioning choice
between operations and the marketplace — it is a broken invariant**, so the fix restores the invariant
and picks no winner: the **computed recommendation** keeps primary weight, the **standing evergreen
invitation** keeps its card, its place, its href and its shipped Filipino key at secondary weight.

**The first attempt failed, and instructively.** Keeping `.ac-cta` and adding a restyling modifier made
the control *look* secondary while still **counting** as primary — the rubric counts `.ac-cta` **by
class**, because on this page that class *is* "primary action-card CTA". That is the
**declared-and-not-adopted** mismatch C-A recorded, reproduced by my own fix. **A control that is not the
primary action must not wear the primary action's class**, so it became `.ac-link`: same 44px target,
same orange, transparent ground and a border instead of a fill.

| | before | after |
|---|---|---|
| primary CTAs | 3 — *View adoption signals*, *Open the provider console*, *Generate Shift Handover Report* | **2** — the computed recommendation + the handover action |
| `hive` @ 1280 | 98% (G3 0%, A3 75%) | **100% · `failing: []`** |
| `hive` @ 390 | 97% | **100% · `failing: []`** |

**And a lens gap this exposed, fixed in the same pass.** `out._a1` has carried the *kept-CTA list* since
2026-09-06 — but it is a property on the dims **array**, and `JSON.stringify` drops those. So every banked
`primaryCta=3/2` reached a reader as **a number with nothing to act on**, and demoting the wrong control
is what that costs — which is exactly what my first attempt did. `a1_ctas` is now returned alongside
`b3_offenders` / `c2_offenders` / `r3_controls`, serving the rubric's own stated intent: *expose the
offenders so the caller can fix them, not just score them.*

`sw.js` v362 → **v363**. **`index` and `marketplace-seller` still carry their own G3/A3 and remain
untouched** — the front door's primary action really is a positioning call, and this fix deliberately
does not reach for it.

### C-Y · The front door's "unreachable content" was a contained flourish — instrument fault 8
Walking the public-to-member funnel as a genuine **anonymous** reader, `index` reported **T1 0% — "1
overflow:hidden box clips content below the fold @390 (unreachable)"**. On the page a stranger meets
first, on the device most of them arrive with, that is the kind of finding worth stopping for.

**It is not true.** The box is the hero (`relative max-w-7xl … py-24 lg:py-32 overflow-hidden`), clipping
**52px** — and the **sole** overhanging element is:

> `<div class="absolute inset-0 rounded-3xl opacity-30 pointer-events-none">` — a 999px decorative
> gradient overhanging by **51px**, carrying **no text, no link, no button**.

The `overflow-hidden` is doing exactly its job: containing a flourish so it does not bleed past a rounded
corner.

**The mechanism, and it is the same shape as the seven before it.** T1's `scrollHeight` test says only
that *something* overflows; it cannot say *what* — and the finding then asserted *"content … unreachable"*.
The old guard **already tried** to exclude decoration (`if (s.pointerEvents === 'none') continue`) but
applied that test to the **container**, which has normal pointer-events, while the decoration is the
**child**. *The check asked the right question of the wrong element.*

**Tightened:** a box now counts only when something **content-bearing** is clipped — a descendant that
overhangs the box's bottom **and** either carries its own text or is/contains an interactive control, and
is not itself `pointer-events:none`. **A real scroll-trap still fails; a contained flourish does not.**

**T1 100% · "no trapped content @390" · `index` 88% → 90%.** All **11** T1 findings the registry held were
this one page and this one false positive; retracted with the mechanism recorded.

**Eight instrument faults now, and the tally has a shape worth stating plainly.** Every one made the
platform look **worse** than it is; every one was found by pointing the lens at a surface or a persona it
had not met; and **five of the eight** — B3's splitter, V1's union rect, D1's missing `alt`, R3's
misattributed mechanism, and now T1's container-vs-child test — were the oracle **measuring the right
thing about the wrong element**. That is not eight unrelated bugs. It is one habit, and the antidote is
the one C-S found: **replicate the oracle against the live page and look at what it actually selected.**

**What the same walk found that is NOT the lens:** `index`'s three competing CTAs are now named by the new
`a1_ctas` receipt — **"Join the Hive"**, **"See All Tools"**, **"Get Early Access: It's Free"**. Unlike
`hive`'s (C-X), this one really is a positioning question — which single action the front door asks a
stranger for — so it is recorded with its evidence and **left for Ian**, alongside `B2`/`B1`'s marketese
(*"SMRP world-class benchmarks"*), `E3`'s missing source chip, `O2`'s absent help affordance, and the
22-word front-door sentence.

### C-Z · The first thing a new seller is asked to do, and the control that could not do it
Walking the buyer's marketplace round as a seller **with no listings**, `marketplace-seller` reported
**G3 0% · 4 primary CTAs**. C-G had filed this page beside `index` and `hive` as *"a product decision —
which single action is primary is Ian's call."* The new **`a1_ctas` receipt** (C-X) named them, and the
answer was none of the above:

> `"Post a listing|btn-primary"`, `"Save|"`, `"Post a Listing|btn-post-now"`, `"Save Changes|btn-primary"`

Two of them say **the same thing in different capitals**. Following both to their destinations:

| control | where it lives | href |
|---|---|---|
| **Post a listing** | top of the dashboard | `marketplace.html**?post=1**` |
| **Post a Listing** | the **"No listings yet"** empty state | `marketplace.html` — **bare** |

**`marketplace.html` opens the post sheet only on `?post=1`** — its deep-link handler reads the parameter
and calls `openPostSheet()`. So the page held the right link **twice over** and the empty state used the
wrong one. A brand-new seller reads *"Post your first listing to start selling on WorkHive"*, taps
**Post a Listing**, and lands on a **browse page with no form**. **The one control whose entire job is the
first listing did not start one.**

**Fixed and verified end to end:** the empty state now links `?post=1`, and following it opens
`#sheet-post` — *"Post a Listing — What are you listing? Parts / Training / Hiring…"*. `sw.js` v363 →
**v364**. The four other bare `marketplace.html` links in the file are honest about where they go
(*"Browse the marketplace instead"*, *"Back to marketplace"*, *"View Live"*, *"Find a part"*) and are
untouched.

**Why it survived:** only a cast with **zero listings** ever renders this state, and every marketplace
walk before this one used a seller who had some. Same axis as C-O and C-W — *the state you cannot cast is
the state nobody has looked at.*

**And I broke the page proving it — worth recording, because the trap was already written down.** The
first version of the explanatory comment above sat **inside a JS template literal** and contained
backticks (quoting `?post=1` and the handler). The first backtick **terminated the literal** and the page
died with `SyntaxError: Unexpected token 'if'` — which is precisely
[[feedback_a_backtick_in_a_comment_broke_the_page]], a lesson already in the memory index. Caught within
one reload by the console, fixed, and the comment now **carries its own warning to the next editor**.
Second documented hazard walked into today: backticks in a Memento `--note` had already run as shell
command substitution and eaten a phrase from an earlier handoff. **Both are the same shape — a quoting
context I did not check before writing into it.**

**Also from this walk, recorded not fixed:** `marketplace-seller-profile` reads **93%** at **260
characters** with **A1 50% (`h1=0` — no page heading at all)** and A2 50% — the page a buyer reaches by
tapping a seller's name cannot say what it is. And `inventory` reports **DD1 0%**, a dim this program had
not seen before: *"the largest KPI sits below the first-glance zone."*

### C-AA · A notice at a hard-coded offset lands on whatever is already stacked there — and my own bumps are what revealed it
`marketplace` reported **V1 0% — "widgets overlap: `wh-guide-link` × `wh-update-notice`"**, the
**floating-chrome** branch of V1 (today's V1 correction touched only the content-vs-content branch).

**The mechanism is two plans that never met.** Notice slots are **literals** — `88px`, `160px`, `232px`
— while the chrome above them is positioned **at runtime** by nav-hub's shared FAB lift. Measured at 390:

| | size | position |
|---|---|---|
| page-guide chip | 195 × 64 | top sits **196px** above the viewport bottom |
| SW update notice | 368 × **99** | anchored at **`bottom: 160px`** |

So the notice covered the chip from **160 to 196** — a **36px band across its full 195px width, 56% of
the smaller element.** It reaches a real person **after every real deploy**, on any page carrying the
guide chip — and that chip has form for exactly this
([[feedback_a_page_guide_chip_covered_every_modals_save]]).

**Fixed at the transport, not per caller** — the same argument nav-hub already makes for the hub reserve
(*one shared bar takes one shared reserve*): `_whShowNotice` now measures the fixed bottom chrome actually
on screen and raises itself clear of it. **Never lowers**, and **never past 60% of the viewport**, so a
heavily-stacked page cannot push the message out of sight.

**Verified:** `bottom: 160px` → `calc(204px + env(safe-area-inset-bottom,0px))` — the chip's top plus the
8px gap. **Overlap −8px (a gap), ratio 0**, notice still fully on screen. `sw.js` v364 → **v365**.

**The uncomfortable part, recorded because it changes how to read today's walks: I induced the state
myself.** `wh-update-notice` appears only when a **new service worker is waiting** — which is precisely
what **every `sw.js` bump this session created**. The walk that caught it was observing a condition my own
tooling produced. **That does not make the finding false** — a genuine deploy produces the identical state,
which is why it is fixed rather than dismissed — but it does mean **a walker who edits the shell is no
longer a neutral observer of it**, and any V1 floating-chrome reading taken shortly after a bump has to be
read with that in mind. The same discipline as the hive-unresolved discard earlier today: **name what the
instrument contributed to what it saw.**

### C-AB · A walk that visits a URL is not a walk that follows the journey
Three buyer walks graded `marketplace-seller-profile` at **93% / 260 characters** with the same six
findings each time — **A1 50% (`h1=0`)**, A2 50%, C3 50%, I2 0%, O2 0%, N1 75% — and I wrote, twice, that
this is *"the page a buyer reaches by tapping a seller's name."*

**That path does not produce that state.** `marketplace.html` links
`marketplace-seller-profile.html**?worker=**<name>`; the walks navigated the **bare URL**. What was graded
is the page's **no-parameter error state**:

> *"No seller specified — This page needs a seller name in the URL. Open it via marketplace.html."*

— whose only heading is an `<h3>` error title, which is exactly why `h1=0`.

**Re-walked the way a buyer actually arrives** (`?worker=Bryan%20Garcia`):

| | bare URL | with the parameter |
|---|---|---|
| score | 93% | **98%** |
| characters | 260 | **1,265** |
| headings | one `<h3>` error title | **`H1: Bryan Garcia`** + H2 Certifications / Reviews / Listings |

**So five of the six findings describe a state no buyer meets on the declared journey.** They are not
false — the parameterless state is reachable through a dropped parameter or a stale bookmark, and it is
worth its own judgement — but the **story** attached to them was wrong, and it is retracted on all nine
rows with `--keep-finding` (the number stands, the interpretation does not).

**The one finding that belongs to the real page** is **B3**: a 22-word sentence, passive, over grade 8 —
*"Their reply time below is measured from real inquiries, and…"*

**This is the third time today the walker, not the product, was the variable** — after the hive-unresolved
discard (a valid session is not a cast persona) and C-AA (my own `sw.js` bumps summoned the update notice
that V1 then caught). Each time the numbers were real and the sentence about them was not. **The discipline
that catches it is the same one every time: state what the instrument contributed to what it saw** — which
persona, which parameters, which cache, which version — and when the receipt cannot say, re-walk rather
than narrate.

### C-AC · The empty registry, fixed by the persona it was written wrong for
Walking the solo owner's setup round, `asset-hub`'s **zero-assets** state gave up two defects that only a
cast with no assets — and no crew — ever renders.

**1 · The JS copy dropped the 44px floor the authored markup already had.** Lines 548–549 render
*"+ Add via PM Scheduler"* and *"+ Add via Inventory"* with
`min-height:44px; display:inline-flex; align-items:center`. The **JS re-render** replaced them with a copy
carrying **only padding** — measured **192×35** and **165×35**, nine pixels under the floor. They are
**buttons, not words in a sentence**, so WCAG 2.5.8's Inline exception (the one that correctly spared
`hive`'s prose links in C-R) does **not** apply here and the floor is owed. *The static half was right and
the dynamic half overwrote it* — [[feedback_the_js_overwrote_its_own_correct_markup]]. Both halves now
carry the same three declarations: **192×44, 165×44.**

**2 · The copy assumed a crew that this reader does not have.**

| | before | after |
|---|---|---|
| verdict sub | *"**Workers** add assets from PM Scheduler or Inventory; they appear here once you approve them."* — grade **9.1** | *"Add assets from PM Scheduler or Inventory. They appear here once you approve them."* |
| empty state | *"No assets yet. **Workers** can submit equipment from PM Scheduler or Inventory; when they do, the submission will land in your Pending Approvals card below."* — **22 words, grade 12.8**, the longest on the page | *"No assets yet. Add equipment from PM Scheduler or Inventory. New submissions land in Pending Approvals below."* |

Both were semicolon-joined and both **named somebody who does not exist** for a one-person operator. The
instruction is identical either way, so it is stated without assuming an actor, and the approval half
stays active — *you* approve, crew or no crew. Every sentence is now under the **twelve-word floor** where
Flesch-Kincaid stops being a valid ruler.

**B3 `long=0 · passive=0 · overGrade=0`; `asset-hub` 98% → 100%.** `sw.js` v365 → **v366**.

**The pattern this closes on:** `asset-hub` has now been fixed **three times** in this extension — the
"no criticals" empty state (C-L), and both halves of the empty registry here — and **every one was copy
that read correctly to the persona it was written for and wrongly to the one who actually met it.** A
supervisor with a crew, a supervisor with no criticals, an owner with no crew: same page, same file, three
different readers, three different first sentences.

### C-AD · The front door, walked in all four cells — which findings are responsive, which are linguistic, which are the page
`index` has now been walked **EN and FIL × 390 and 1280**, all four with the **same anonymous cast, the
same lens, the same session state, within one hour.** That is the cleanest controlled grid this extension
has produced, and it sorts the front door's findings into three kinds:

| | **390** | **1280** |
|---|---|---|
| **EN** | 90% · B2 E3 **G3** O2 B3-33 B1 **A3** N1 | 91% · B2 E3 O2 B3-33 **C1-33** B1 **A1-75** |
| **FIL** | 90% · B2 E3 **G3** O2 B3-**67** B1 **A3** N1 | 91% · B2 E3 O2 B3-**67** **C1-33** B1 **A1-75** |

**Responsive, not linguistic — `G3` + `A3` (390 only, both languages).** The three-CTA competition —
**"Join the Hive"**, **"See All Tools"**, **"Get Early Access: It's Free"**, named for the first time by
the `a1_ctas` receipt added today — appears at phone width in **both** languages and at **neither**
desktop cell, where A1's own receipt reads **`cta=2`**. So C-G's index half is **a width problem, not a
page problem**: the actions do not compete until the layout runs out of room. That does not decide which
one should be primary — still Ian's positioning call — but it says **where** the decision has to hold.

**Responsive the other way — `C1-33` + `A1-75` (1280 only, both languages).** `bigSizes=[67,36,30,20]`:
four display tiers where the rubric expects three, anchored by a **67px hero that only desktop renders.**
The scale holds until the surface has room to show every tier at once — the same shape `hive`'s C1 takes
on the busiest board (C-AC's sibling observation).

**Linguistic, and by design — `B3` 33% → 67%.** Moves **only** with language, at both widths, because
the Flesch-Kincaid grade is correctly **withheld under FIL** (C-H). What survives is the ≤20-word check,
and in all four cells it catches **the same 22-word English sentence** — the positioning line a Filipino
reader meets untranslated on an otherwise Filipino page (`documentElement.lang="fil"`, 34 Filipino
function words in the body). **That sentence is now evidenced on four independent readings** and remains
Ian's.

**The page itself — `B2`, `E3`, `O2`, `B1` in all four cells.** Marketese (*"SMRP world-class
benchmarks"*), no source chip, no on-demand help. **These need no further walking to characterise.**

**And the quiet result that makes the grid trustworthy:** `tools/mtbf-calculator` reads **100% in all four
cells**, and `best-free-cmms-software-philippines` reads **89% in all four**, dim for dim apart from the
withheld grade. **A baseline that does not move is what makes a mover meaningful** — the same argument
C-J's device pair made, now run across two axes at once.

### C-AE · Four of today's fixes, met in Filipino — six of seven pages at 100%
The worker's shift round walked in **Filipino** on phone-390 (`documentElement.lang="fil"` on all seven
pages) reads **100% on six of seven**, with only `hive`'s worker-side pair left. **This is the axis that
until C-H was being marked down for translating well** — Flesch-Kincaid is fitted to English and Tagalog
is agglutinative, so the grade ran structurally high on good Filipino. Four fixes made today were met here
in their Filipino form and all four hold:

| fix | in Filipino |
|---|---|
| **C-U** `audit-log`'s gate | *"Para sa supervisor lang — Mga supervisor lang ang makakabukas ng audit log. Itinatala nito ang mga approval, rejection at pagbabago sa member ng hive mo."* over **"Buksan ang Hive Board"** → `hive.html`. This morning: one **grade-15.3** English sentence over a *"Back to Home"* that sent a worker who *has* a hive to the marketing page. **99% → 100%.** |
| **C-X** `hive`'s demoted CTA | renders **"Buksan ang provider console"** — the shipped Filipino, unchanged, because the fix moved the **class** and left `data-i` alone |
| **C-N / C-W** `analytics` | **100%**, `uuids=0`, OEE tile reading **"Karaniwan sa 16 asset"** — Baguio *has* quality readings, so the no-data branch correctly does **not** fire |
| **C-AC / C-T** `asset-hub`, `alert-hub` | both **100%** — the empty-state rewrites, the restored 44px targets, and the corner-consistency fix that closed the platform's last R3 |

**And `hive`'s A2 is now settled as ROLE-gated, across every axis this program varies.** `headings=1,
h2/h3=0, blocks=9` has now been measured on **three hives** (quiet Baguio, busy Manila, fleet Dela Cruz),
**two devices** and **two languages** — and a **supervisor** on the same page gets an outlined board every
time. The earlier explanation, *"a worker in a QUIET hive"*, fitted one hive and was not the mechanism.
**A worker's hive board is unoutlined whatever the screen, whatever the hive's workload, and whatever
language it speaks.**

### C-AF · Two zero-delta device pairs in Filipino — 1,080 dims, not one moved
Two Filipino walks were each taken twice, minutes apart, **same persona, same hive, same language, width
the only variable**:

| pair | pages | result |
|---|---|---|
| worker's shift round (Baguio) | logbook · asset-hub · alert-hub · hive · audit-log · analytics · analytics-report | **100 / 100 / 100 / 99 / 100 / 100 / 100** at *both* widths |
| J17 machine client (Manila) | alert-hub · hive · asset-hub · logbook · pm-scheduler | **100 / 99 / 100 / 100 / 100** at *both* widths |

**Twelve pages, 1,080 dims, and not one dim differs across the width.** In both pairs the only findings
are `hive`'s worker-side A2 + N1, plus `audit-log`'s gate-card A1.

**Why a pair that moves nothing is worth as much as one that moves something.** Earlier in this extension,
**three of four apparent "device deltas" turned out to be the ruler moving between the halves**, not the
width — the halves sat either side of a lens correction. The discipline that fixed it was to walk pairs
**back to back on one lens**, and C-J's clean pair is what made `analytics`' R3 believable. These two are
that discipline at rest: **a baseline flat enough that any future mover is unambiguous.**

**And they settle `hive`'s A2 completely.** `headings=1, h2/h3=0` has now been measured across **three
hives** (Baguio 9 blocks, Manila 8, Dela Cruz), **two devices**, and **two languages** — never once moving
for a worker, never once appearing for a supervisor. **The block count follows the hive; the finding
follows the role.** The original explanation, *"a worker in a quiet hive"*, was a fit to one sample and
has been corrected in the record.

### C-AG · The page printed a raw gateway error to a maintenance supervisor — in English, on a Filipino page
Walking the fleet supervisor's PM round in **Filipino** at desktop, `analytics` was caught **in its failure
state**: the orchestrator call failed, the page degraded honestly to *"Hindi available"* — and then printed
this into the results panel:

> **"An invalid response was received from the upstream server"**

**Passive with no actor. Pure infrastructure jargon** — *"upstream server"* means nothing to the person
reading it. **And English, on a page whose `documentElement.lang` is `fil`.** It is Kong's 502 body,
rendered verbatim.

**The mechanism, and the page already knew better one line above.** `analytics.html`'s `catch` rendered
`err.message` **raw** whenever the message did not contain the string `'not yet available'`:

```
escHtml(err.message.includes('not yet available') ? 'Analytics engine warming up…' : err.message)
```

The **same ternary** special-cases the warming-up path into a human sentence, and the verdict label four
lines below is wrapped in `_t()`. **The results panel simply fell through to the raw throw** — and the
message it prints is chosen by whatever infrastructure happened to fail.

**Fixed** — the fallback now reads *"Could not load the analytics for this period. Tap Refresh to try
again."* / *"Hindi makuha ang analytics para sa panahong ito. Pindutin ang Refresh para subukan ulit."*,
two short active sentences both under the twelve-word floor. **Two more untranslated strings in the same
block** were wrapped while there: the verdict sub (*"Tap Refresh once the engine is ready."*) and the
warming-up label — English on a Filipino page for exactly the same reason. `sw.js` v366 → **v367**.

**How far this is verified, stated plainly.** The raw `err.message` fallback is **gone from the source**,
and the page still parses and renders (4,887 chars, verdict *"Kailangan ng aksyon ang reliability KPIs"*),
so the template literal is intact. **The new copy has NOT been re-observed in the failure state**, because
reproducing it means *inducing* a transport failure rather than waiting for one. The branch is
demonstrably reachable — this walk reached it — and the next walk that catches a failing orchestrator will
read the new sentence. **Recording the limit of the verification is part of the verification.**

**What found it is worth naming: the failure state is a state, and it only gets graded if a walk happens
to land in it.** Three pages in this same walk read 100% and its 390 half read `analytics` at 100% too —
the same page, the same persona, the same hive, minutes apart. **A surface that is only wrong when
something else breaks is invisible to every walk that gets a working backend**, which is the same lesson
as the empty-state findings (C-Z, C-AC) and the hive-less ones (C-O, C-W): *the state you cannot summon is
the state nobody has read.*

### C-AH · The heading asked the question in Filipino and the answer came back in English
Walking J22 as **Ricardo Morales, a worker in Lucena Pharmaceutical Mfg.**, in Filipino, `asset-hub`
read **100%** — and its primary CTA, a 168×44 button, said:

> **"Review 2 pending →"**

**The page read 100% before the fix and 100% after it.** What carried the defect was not the score but
the **`a1_ctas` receipt** added to the survey return that morning, which prints the CTA verbatim. A
percentage cannot say "this button is in the wrong language"; a receipt can. This is the plainest
argument in the program so far for **receipts over scores**.

**The shape.** `asset-hub`, `inventory`, `shift-brain` and `pm-scheduler` ship the same *what to do next*
block: a heading stamped `p_whattodonext_8ce2` → *"Ano ang susunod na gagawin"*, over a paragraph, with a
primary button stamped `p_takeaction_ee0b` → *"Kumilos →"*. **Both translations had already shipped.**
Then each page's render overwrote the button's `textContent` with an English label and set an English
paragraph beneath the Filipino heading — **18 CTA labels and 18 advisory sentences across four pages**,
none through `_t()`.

**Why every i18n measurement was blind to it: they count `data-i` STAMPS.** The stamp was still on the
element — only the rendered text had changed — so the in-page orphan census reported **`orphanCount: 0`
on a page carrying an English primary CTA**, and `validate_i18n_coverage.py` still lists the page as
*"covered"*. This is the shared-chrome lesson one layer further in: **a gate's SCOPE is part of what it
proves.** There the untranslated strings sat *outside* the scanned pages; here they sit *inside* one, in
its script block, where a stamp census cannot reach them.

**`pm-scheduler` is the sharpest case, because its copy QUOTES the controls by name.** It said *Tap the
**"Overdue"** chip below* — on this reader's screen that chip is labelled **"Lampas sa Takda"**. Its
empty branch said click **"Add asset"**; the button reads **"MAGDAGDAG NG ASSET"**. A quoted control name
that appears nowhere on the reader's screen is worse than an untranslated sentence: **it sends someone
looking for a thing that is not there.** That is the T194 rule — *advice must not name a control that does
not exist* — in its **bilingual form**: the control exists, under another name, for this person. Every
Filipino string now names the card or chip by the label it actually wears.

**The second shape of the same blind spot, on `hive`:** the entire Shift Handover panel — heading,
description, button — carried **no `data-i` at all**, invisible to the stamp census from the other
direction. And `tools/i18n_page_dict.py` could never have caught the button: its extractor matches only
elements whose whole content is a **bare text node**, which puts **every icon-bearing control** out of
reach. Stamped through a `<span>` around the text (a `data-i` on the button replaces its `innerHTML` and
takes the icon with it) plus a new `i18n/pages/hive.fil.json`. **hive's N1 rose 75% → 100%** and dropped
off its failing list.

**LOCKED** with `tools/validate_rendered_i18n.py` (self-test 5/5, registered, group Platform). It counts
what the reader sees, not what the markup claims, and it **follows the variable** — because the literal
usually never touches the property: the block that started this reads `let text; text = 'No assets
yet…'; actBox.textContent = text;`, and a property-only detector saw **none** of its five branches.
Census: **653 literals across 25 pages, 73 of them overwriting a stamped element** — ratcheted, because a
gate nobody can pass gets switched off.

### C-AI · The gate was not a gate until the network answered
Same walk, `audit-log`. Its supervisors-only check is **correct**, and reads two values that are already
in `localStorage` — but it sits **after** `await db.auth.getUser()`, and `main-content` ships **visible**
on purpose (Arc L L1: revealing it in JS was a ~0.7 CLS bomb), so the gate can only ever **hide** it. On
a loaded host the round trip threw `TimeoutError: WH_DB_TIMEOUT`, and a **worker** sat looking at the
audit-log chrome, an **"I-export sa CSV"** button, and a skeleton reading *"Naglo-load ng audit log…"*
that never resolves for him.

**Nothing leaks but the impression that the page is his and merely slow** — every query is RLS-refused,
so no audit row ever renders. The fix costs nothing and needs no network: when the cache **already** says
*this person has a hive and is not a supervisor*, hide the chrome **synchronously, before the first
await**. An unknown role still falls through to the async gate exactly as before. **Both paths
re-verified:** the worker sees `main-content: none` at first read with the gate rendered; the supervisor
(Christine Dizon) sees `main-content: block` at first paint with 2,310 characters of log, so the CLS fix
is intact.

**And the instrument failed twice in one walk, both times mine.** My settle rule is *"text length steady
across three reads"* — and **a page frozen on a skeleton is perfectly steady**, so it declared `audit-log`
settled while it was still pre-gate and produced a false **95% with four invented failing dims** that were
measuring a loading page. The hardened rule I wrote to fix that searched `innerText` for loader **words**
— and analytics' own provenance chip contains *"kinukuwenta"*, legitimate prose, which would have stalled
every analytics walk from then on. The rule now tests for a **visible loader ELEMENT** (`.loading`,
`.skeleton`, `[aria-busy]`, `[data-loading]`) — exactly what audit-log's stuck state is and what analytics'
sentence is not. **A stuck skeleton is invisible to a length-based settle: ask what is on the screen, not
how long the text is.**

**Zero device delta, the third Filipino pair.** All six pages read identically at 390 and 1280 — same pct,
same failing list, same character count. Three Filipino pairs now, eighteen pages, and **not one dim has
moved with width.**

### C-AJ · An English page looked better for having been read by a Filipino speaker
Walking **J30, the energy audit**, in Filipino at desktop — the RA 11285 article → the learn hub → the
calculators article → the load-estimation calculator → engineering-design → project-manager →
project-report → report-sender — as **Christine Dizon, supervisor of Lucena Pharmaceutical Mfg.**

**Instrument fault 9.** B3 decided whether to apply the Flesch–Kincaid grade from
`window.WH_LANG` — **the reader's preference** — not from the language of the text:

```js
const _fkLangEN = (typeof window === 'undefined') || window.WH_LANG !== 'fil';
```

The 54 learn articles and 60 calculators are **English-only content**. On the RA 11285 article the
platform's own declaration says `documentElement.lang="en"` and all **15,867 characters are English** —
yet the grade was suppressed and the note blamed Filipino calibration. The first survey in this walk
read **B3 33%, `grade=n/a`**; on the corrected lens the *same page, same load* reads **B3 0% with
`grade>8=92`** — the exact figure the English walk had recorded. **A third of the finding vanished
because of who was reading.**

The lens now keys on **the page's own `lang` declaration**, which read `fil` on all six product pages
walked an hour earlier and `en` here; `WH_LANG` survives only as the fallback for a page that declares
no lang at all. **Filipino text is still exempt from the grade** — that was always right, and the learn
hub still reports `grade=n/a` at 99%, correctly, because its text really is Filipino.

**The blast radius was six findings, and narrowing it was the whole job.** A retraction keyed on
`--dim B3 --lang fil` matched **69 banked rows** — but on **63 of them the page's text really is
Filipino and `grade=n/a` is the correct reading**, so retracting them would have annotated 63 sound
findings with a correction that does not apply to them. The genuinely understated set was **six rows on
one article** (`best-free-cmms-software-philippines`), which re-measures at **B3 0%, `grade>8=15`**
against a banked `grade=n/a`. `tools/retract_critic_finding.py` gained an **`--ids`** filter so the
correction could be aimed at exactly those six, with a replacement finding carrying the re-measured
number. **A retraction that cannot be narrowed to the rows it is true of is not a correction, it is a
second error.**

**What the walk itself shows: the content layer is the monolingual seam in an otherwise bilingual
platform**, and this journey crosses it twice. Every page whose `lang` says `fil` reads **100%**
(engineering-design, project-manager, project-report, report-sender; the learn hub 99%). Every page whose
`lang` says `en` is a learn **article** and reads **89–90% with seven to nine failing dims**. The reader's
actual path is a Filipino hub, describing articles in Filipino, that open as fifteen thousand characters
of English, and then a Filipino product on the other side.

**Nothing here is broken, and that distinction is the point.** There is **no language toggle on the
articles**, so no control lies to the reader; `documentElement.lang` is correct in both directions, which
is what a screen reader needs; the articles load `wh-i18n-lite.js` and carry three stamps and no page
dictionary — the mechanism present with almost nothing to apply. **That is a content programme, not a
code defect**, it stays with Ian's existing B3 content-bar item, and it is not papered over with a
language badge nobody asked for.

### C-AK · The provenance chip translated its own connective and nothing else
Walking **J29, typhoon season**, in Filipino as **Wilfredo Malabanan, a worker in Baguio Textile
Mills**, a read failed on `report-sender` and its provenance chip said:

> **"Read failed · Live · contacts refreshed on load, history on load · Batay sa iyong AI reports &
> report contacts"**

Four clauses — and **the only Filipino words in the sentence are the ones the shell supplies itself.**
`renderSourceChip` puts `source` through `_t()` and pushes `freshness`, `window` and `notes` through
**verbatim from 55 call sites across 31 pages**. This chip is `role="status" aria-live="polite"` — the
platform's G1 system-status region — so **a screen reader announces the half-translated sentence.**

**Fixed once, in the shell, not 55 times.** The freshness clause is the chip's first words and by far
the most repeated — 22 distinct literals, of which **four cover ~30 of ~38 uses** — so it is a phrase
map inside `renderSourceChip`, the same **locale-FLOOR** pattern `utils.js` already uses for `_t()`.
Verified live: logbook now reads *"Live · nire-refresh sa pag-load · Batay sa iyong logbook, asset
nodes & inventory"*; alert-hub *"Live na data"*; dayplanner *"Live · nire-refresh sa bawat palit ng
view"*. An unrecognised clause **falls through unchanged**, so no chip can get worse.

**Honest limit, and it is visible in this walk's own evidence:** `window` (11 distinct) and `notes` (43
distinct, one-off explanatory sentences) are **still English** and need a per-site copy pass —
`report-sender`'s chip still carries *"contacts refreshed on load, history on load"* for exactly that
reason.

**Two more faults in the same file, found by following the first.**
1. `'Read failed · '` was **hard-coded English** inserted by the shell into a `fil` page. Now
   `_t('Read failed · ', 'Nabigo ang pagbasa · ')`, verified by invoking `_whSettleStuckLoaders`
   directly rather than waiting for another transport failure.
2. **Its guard was coupled to an untranslated string.** It marked only a chip whose text *starts with*
   `"Live"` — so **the day anyone translated that word, the honest-degradation marker would have
   silently stopped appearing** and a stale chip would have gone on claiming live data after every read
   failed. `renderSourceChip` now stamps `data-wh-fresh="1"` and that attribute is the primary test.
   **A safety behaviour must not depend on another string staying in English.**

**And the branch written to handle the possessive left it in English.** dayplanner's chip read *"Batay
sa **your** schedule & logbook"*. The function carries a deliberate comment — *one whole template per
locale, because the possessive sits differently in Filipino* — and then the branch that detects a
leading `your` glued that English word straight into the Filipino template. Now *"Batay sa iyong
schedule & logbook"*, with the English side re-verified unchanged (*"Based on your schedule &
logbook"*). **A correct intent, documented in its own comment, that the code did not carry out.**

**The walk itself:** ten readings, all **100%**, the only sub-100 dim being analytics' documented N1
75%. Fifth Filipino device pair, zero dim delta — though `dayplanner` renders **four times more text at
desktop** (4,111 characters against 1,053) without moving a single dim, which is what a genuinely
responsive surface looks like: the phone shows a condensed plan, the desktop the full one, and both are
complete for their width.

### C-AL · The first real device delta in five Filipino pairs, and it separated a confounded variable

> **⚠ THIS CLUSTER'S MECHANISM WAS WITHDRAWN — read C-AP for the measured answer.** The numbers below
> stand; the explanation does not. It was retracted twice (see "C-AL · RETRACTED MECHANISM" and
> "C-AL, second correction"), and the final, reproduced finding is that hive's phone view renders
> **eleven distinct type sizes where the scale allows ten** — not a fourth display tier, not
> unpopulated tiles, and not a disclosure. Kept in place rather than deleted because the sequence of
> three wrong causes is the lesson.
Walking **J21, the federated benchmark**, in Filipino as **Hector Salvador, supervisor of Manila
Electronics Assembly** — hive → analytics → ph-intelligence → community, both widths back to back on
one lens.

**`hive` moves with width, and only with width:**

| | C1 | `bigSizes` | A1 |
|---|---|---|---|
| **390** | 67% | `[32,24,22]` | *no finding* |
| **1280** | 33% | `[32,26,24,22]` | 75% (`bigTiers=4`) |

The desktop renders a **fourth display tier — 26px — that the phone never paints**, and that fourth
tier is what breaks both dims. Same hive, same persona, same language, minutes apart on the same lens,
so **width is the only variable left standing.**

**Why that matters: the finding was on record attributed to the hive.** *"hive C1 33% / A1 75% on
Manila only"* has been carried as a Manila-specific observation. It is **at least as much a DESKTOP
observation** — on Manila, at 390, neither dim fires. What this walk **cannot** say is whether the
desktop tier also depends on the hive: that needs a supervisor at desktop in a second hive, and the
Lucena desktop reading taken earlier today was a **worker**, whose hive page is a different composition
(A2 50%, no C1/A1). **On Manila, for a supervisor, in Filipino, the C1/A1 pair is desktop-only; the hive
axis is still open.**

**Four flat pairs are what make this one readable.** Twenty-two pages across four Filipino pairs moved
not one dim with width. A single mover against that baseline is unambiguous — which is exactly why the
pairs are walked back to back on one lens rather than compared across sessions, after three of four
earlier "device deltas" turned out to be the ruler moving between halves.

**`ph-intelligence` is a gate here, not a report** — *"NAKA-LOCK … PH Intelligence bubukas sa Stair 3:
Predictive-Ready"* — 100% at 857 characters at both widths. The page sits on the EN-by-design exempt
roster as a formal EN publication, but **what this walker met was its maturity gate, which is
translated.** Stating that plainly so no reader of these rows concludes the EN-by-design disposition was
tested: it was never reached.

### C-AM · The first fix was aimed at the wrong element, and the dim said so
Walking **J5, parts shortage → procurement**, in Filipino as the buyer, `marketplace-seller-profile`
read **R1 83%** with `offScale=[10]` against a declared scale of 4/8/12/16/24.

I changed `.stats-grid`'s `gap: 0.625rem` (10px) first, believing it was the cause. **The dim did not
move.** R1 measures the vertical distance **between direct children of the page root** —
`c.top - p.bottom` — **not CSS `gap`**. The real 10px was `#listings-order-note`'s `margin-bottom:
0.6rem` (9.6px, rounding to 10) above `.filter-row`. Both are now on-scale at `0.75rem`; the page reads
**99%** and R1 is gone.

**The `.stats-grid` change is kept** — 10px is genuinely off-scale on its own terms — **but its comment
now says plainly that it was not the cause.** A comment that names the wrong cause is worse than no
comment: the next person to read it would have inherited my wrong model of what R1 measures. This is
the everyday form of *the instrument must explain its own number* — the dim was right, my reading of
what it measured was not, and **the dim not moving is what told me.**

**Two things this walk confirmed rather than discovered.** `inventory` reads 100% at both widths with
its primary CTA in Filipino — *"Mag-order ng 3 mababang part →"* — which is **C-AH's fix met in passing
by a walk that was not testing it**, on a different hive, the strongest kind of confirmation. And the
profile was reached **the way the product reaches it**: `marketplace.html` renders
`?worker=<name>` links, captured live from the page rather than assumed. Romeo Beltran was chosen
deliberately over the two other sellers offered — both are in `marketplace_platform_admins`, and an
admin is never the right cast for a walk about what an ordinary person sees.

`marketplace-seller`'s **G3 0%** (17 controls, 4 primary CTAs) and **A3 75%** are recorded unchanged at
both widths — the documented Ian-gated finding, deliberately not acted on, because **which of those four
CTAs is the primary one is a product decision**, not a defect for whoever happens to be walking.

Sixth Filipino pair, zero device delta.

### C-AN · The ruler scored the same page higher in Filipino, because it could not read the language
Walking **J5** in **English** minutes after the same path in Filipino, on the same lens, deliberately as
a language comparison — and the comparison found **instrument fault 10**.

`marketplace-seller` read **96% in English with four findings** — G3 0%, **J1 0% "1 destructive
control(s)"**, A3 75%, **Z3 96% "risk mis-tap: Delete(destructive)"** — and **98% in Filipino with
three**, J1 and Z3 simply absent. It is the same page. Its listing delete button is a marked command
button — `class="btn-sm danger" data-action="delete"`, 72×44, plainly visible — rendering **"Delete"**
in English and **"Burahin"** in Filipino.

**Both detectors read only English words.** J1's filter tested the label against
`/delete|remove|clear|reset|archive|discard/` and nothing else; Z3's hazard test carried the same
vocabulary. Under `wh_lang=fil` the button matched neither, so **J1 fell through to N/A "read-only
surface: 0 destructive controls"** — the phrase that says a page has nothing to lose — **on a page with
an unguarded delete button**, and Z3 reported no mis-tap hazard. The Filipino reader has exactly the
same button and exactly the same risk.

**The fix was already written down in the file's own comments.** Z3's note says a real destructive
control is *"a command button (data-action=delete, .danger), never a filter"*. Those markers are
language-independent — and Z3 **was already testing `className`**, it just had no entry for `danger`.
Both dims now lead on the structural markers, with the word test kept for unmarked controls and widened
to the Filipino imperatives. Filipino now reads **96% with J1 0% and "Z3 96% … Burahin(destructive)"**,
identical to English but for the label quoted; **English re-verified unchanged**, so nothing is
double-counted.

**The scope was checked rather than assumed, and that changed the answer by two orders of magnitude.**
**216** banked Filipino rows cover a page whose *source* carries such a marker — but a class in the
source is not a control on the screen: `logbook` renders none in the state a walk meets, and `asset-hub`
renders none either, reading **J1 N/A and 100%, correctly**. The confirmed set is the **18** rows
covering `marketplace-seller`, and of those only the **six walked today** can be verified — the older
twelve recorded *"15 controls"* against today's *17*, a different page state whose delete button I
cannot retroactively prove was on screen. **Six corrected with the re-measured J1; twelve left alone and
recorded as unverifiable rather than assumed.** Correcting what I cannot observe would be the same error
as the finding itself.

**A difference that is not a defect:** `marketplace-seller-profile` reads 98% in English against 99% in
Filipino, and that gap is **C-AJ's corrected B3 working as designed** — English gets the FK grade
(`grade>8=1`), Filipino correctly withholds it. **The two numbers disagree because the rulers
legitimately differ, not because the page does.**

### C-AL · RETRACTED MECHANISM — it was not the width, it was whether the tiles had their numbers yet
**C-AL above claimed hive renders a fourth display tier (26px) only at desktop.** The **numbers stand** —
at 390 it read C1 67% `bigSizes=[32,24,22]`, at 1280 C1 33% `bigSizes=[32,26,24,22]` plus A1 75%, minutes
apart on one lens — but **the cause is not width, and the claim is withdrawn.**

Re-measured the same day, same persona, same page, **at desktop in both languages**:
`bigSizes=[32,24,22,21]`, **no 26px tier**, hive **100%**. *Desktop without the fourth tier refutes
"desktop renders the fourth tier" on its own.*

The 26px tier belongs to the **"Your hive's value"** card — three tiles at `font-size:1.6rem` (25.6px),
`#vs-pms` / `#vs-faults` / `#vs-knowledge`. **Those tiles are present and visible in both readings.**
What differs is whether they have their **numbers** yet: C1 counts type tiers among elements that *have
text*, so an unpopulated 25.6px tile is invisible to it and a populated one is a fourth tier. The desktop
half caught the card filled (4,830 chars), the phone half caught it empty (4,022) — **a data-arrival
difference the walk read as a layout difference.**

**And my settle rule passed both**, because each was stable in length. **Stable is not populated** — the
audit-log frozen-skeleton lesson in a second costume, and a third clause the discipline now needs: a
region that is *visible but textless* is unfinished, however steady the character count.

**What this costs and what it buys.** The interpretation is retracted on six rows with the measurement
kept; hive's C1/A1 pair fires **when the hive-value tiles are populated**, and the width axis — like the
*"Manila only"* attribution C-AL was itself correcting — **remains unseparated.** Recorded rather than
quietly deleted, because **the discipline that caught this is the one that produced it**: walk the pair
back to back, then *check that the mechanism reproduces.* I did the first and skipped the second.

### C-AL, second correction · The tiles always had their numbers — they were behind a closed disclosure
The retraction above said hive's C1/A1 pair turns on whether the *"Your hive's value"* tiles have been
**populated**. **That is wrong in detail, and this corrects it.**

**The tiles always have their numbers.** `#vs-pms` reads `innerHTML` **"460"**, `#vs-faults` **"7,675"**,
`#vs-knowledge` **"1,700"** — in every reading. What varies is whether they are **rendered**: the card
sits inside `<details id="health-details" class="wh-disclose">`, a **closed disclosure**. `innerText`
correctly returns nothing for content inside one, while `getBoundingClientRect` **still reports a box**
(79×28). That combination — *a box with no text* — is exactly what made the element look "visible but
unpopulated" to my probe, and invisible to C1, which counts tiers among elements that have text.

**So the trigger is the disclosure's open state** — not data arrival, and not width. On fresh loads
`#health-details` is **closed at both 390 and 1280**, verified in both languages, and hive reads C1 67%
`bigSizes=[32,24,22]`. The J21 desktop half caught it **open**, which revealed three 25.6px tiles and
made a fourth tier.

**The general property is worth more than the finding.** *A page is graded differently depending on
whether a disclosure happens to be expanded*, because **`innerText` is a rendering-dependent API** — and
`getBoundingClientRect` will not tell you, since the box is there either way. This is the platform's own
QA rule — *expand everything, scroll to the last element* — arriving as a **measurement fact** rather
than a testing habit.

**Three statements of cause, two of them mine and wrong.** Width (published, withdrawn) → data arrival
(withdrawn here) → disclosure state (evidenced: `open === false` at both widths, `innerHTML` intact).
The measurements stand as readings of the **collapsed** page. Recording the sequence rather than only the
answer, because the failure mode was the same each time: **I explained a difference before I could
reproduce it.**

### C-AO · Two languages under one declaration — WCAG 3.1.2 on the EN-by-design pages
Walking J27 in Filipino, `platform-actions` renders **Filipino chrome over an English body**: *"Paano
gumagana ang console na ito"*, *"Balik sa WorkHive"*, *"Hive Board Ko"* above *"Governance actions only:
approve/verify/resolve. Every metric (health, usage, growth, marketplace volumes) lives in Grafana."*
Counted on the visible text: **42 Filipino function-word hits against 39 English.**

`documentElement.lang` reads **`fil` for all of it**, and **no element on the page declares a `lang` of
its own.** A screen reader will therefore pronounce the English body with Filipino phonetics — **WCAG
3.1.2 Language of Parts**. `ph-intelligence` has the same shape: `lang="fil"`, exactly one element
declaring a language (the `<html>` element), no `translate="no"` region, visibly mixed text.

**These pages are on the EN-by-design roster, and that is the point** — their bodies are English *by
declaration*, in a comment, while the markup says the document is Filipino. The obvious fix is to mark
the EN region `lang="en"` so the markup says what the comment already says.

**I did not make that fix, and the reason is the finding's own limit.** On `ph-intelligence` the surface
a walker can reach is the **maturity gate**, not the report body — the region a fix would target was
never on screen. On `platform-actions` the two languages are **interleaved**, not separated into a body
wrapper. **Fixing what I cannot see is how a plausible edit becomes a wrong one** — the same discipline
that produced the C-AL retraction two clusters above. Recorded for Ian with the measurement attached: it
is a real standards finding on three EN-by-design pages, and it needs a decision about **where the
language boundary actually is**.

**It also costs the lens something, and that should be said.** B3 reads **67% here and 33% in English on
the same page**: fault 9's corrected rule withholds the grade because `lang` says `fil`, though roughly
half the graded sentences are English. **Withholding is the safe direction** — it never invents a bad
score — but on a genuinely bilingual page the lens now measures **less than it could**, and the remedy is
the same lang-of-parts markup this finding asks for.

### C-AP · hive's phone view renders eleven type sizes where the scale allows ten — and three wrong mechanisms
**The finding, measured and reproduced.** `hive` reads **C1 67% at 390 and 100% at 1280** — reproduced on
**two independent controlled pairs** (J27 and J15), with `#health-details` **closed in both halves** and
**identical character counts**, so the difference is real and the confounder that produced two earlier
retractions is excluded.

**C1's two graded checks say exactly where it fails:**

| check | threshold | at 390 | verdict |
|---|---|---|---|
| `big.length` | ≤ 3 | `[32,24,22]` = 3 | **passes** |
| `sizes.length` | ≤ 10 | **11** | **fails** |

**So the whole of it is: the phone renders eleven distinct type sizes where the scale allows ten.** That
is a designer's decision to make — *which* tier to drop — and it is now stated as a measurement rather
than a theory.

**Three wrong mechanisms, all mine, recorded because the sequence is the lesson.**
1. **"Desktop renders a fourth display tier."** Refuted: desktop shows `[32,24,22,21]` with no fourth tier.
2. **"The value tiles hadn't loaded."** Refuted: `innerHTML` held 460 / 7,675 / 1,700 the whole time.
3. **"The greeting's 19px is the eleventh tier."** I changed `1.18rem → 1.125rem` and **C1 still read 67%
   with `distinct=11`** — because the rubric's `textEls` uses **own text nodes**, which see *through* a
   closed `<details>`, where `innerText` does not. **My probe and the oracle were counting different
   element sets the entire time.**

**The greeting change is kept** — 18.88px is not on the scale and 18px is — **with its comment corrected
to say it does not fix C1.** Same disposition as C-AM: a genuine improvement whose stated reason was
wrong is kept and re-labelled, never left standing with a false explanation.

**The rule this cost three attempts to learn: replicate the ORACLE's own element set before explaining
its number.** That is precisely how the R3 findings were closed earlier in this program — by replicating
`roleOf`/`shapeV` against the live page — and I reached for a hand-rolled probe instead, four times.

### C-AQ · A ratchet caught my own edit, in the one query where an arbitrary pick is an identity error
Running `--fast` at this milestone returned one **FAIL**: *paginated order totality*, count **0 → 1**,
`utils.js`. The offending chain was code **I wrote earlier in this same session** — the
`restoreIdentityFromSession()` solo fallback added for hive-less people:

```js
.select('display_name,username,deactivated_at').eq('auth_uid', session.user.id)
.order('created_at', { ascending: true }).limit(1);
```

**`created_at` is not a total order.** Rows written inside one transaction share an identical `now()`,
and Postgres promises nothing about the order of ties. Under `.limit(1)` that is the quiet, worse case —
*"the earliest profile"* silently picks an **arbitrary** row — and what this particular query decides is
**who the product thinks you are.**

It is the same shape as the bug that once **resolved the wrong hive for a signed-in worker**, which is
exactly why that gate treats `limit(1)` as in scope rather than exempt. Fixed by ending on the primary
key; ratchet back to **0 across 185 chains**; the query re-verified live (1 row, correct profile, no
error) and `sw.js` bumped to **v370**.

**Why this is worth a cluster of its own.** I added that fallback to fix a real defect — a member
rendering hive-less — and introduced a second, subtler one in the same edit. **The gate caught it, not
me**, and it caught it in the highest-consequence place a non-deterministic pick can occur. That is the
whole argument for running the suite at milestones rather than trusting a careful author: *the author
was careful, and was still wrong.* It also vindicates the gate's own scoping decision — had `limit(1)`
been exempted as "not really pagination", this would have shipped silently.

### C-AR · One milestone `--fast` run, seven failures, three of them mine — and a green gate on a broken page
Running the suite at this milestone was the single highest-yield action of the session. **Seven FAILs.
Three were caused by my own edits hours earlier**, one was a stale generated scoreboard, one a stale
substrate manifest, and one is Ian's commit gate.

| failure | cause | disposition |
|---|---|---|
| paginated order totality **0 → 1** | **mine** — `.order('created_at').limit(1)` in identity resolution | fixed, `.order('id')` (C-AQ) |
| role checks **audit-log 1 → 2** | **mine** — C-AI's pre-gate added a second raw role comparison | hoisted to one shared `_IS_SUPERVISOR`, count **2 → 1** |
| counted-noun ratchet **14 → 15** | **mine** — the Filipino string `${carryCount} bukas na item` | gate taught its scope; back to 14 |
| trajectory header drifted | banking moved the registry | regenerated |
| substrate freshness | a new gate + new memories | rebuilt |
| deploy root hygiene | `.vercelignore` untracked | **Ian's gate** — needs a commit, not an edit |

**The counted-noun failure is the third English-calibrated instrument to meet Filipino text today.** Its
regex assumes a trailing `s` is an English plural — and *"bukas"* (Filipino for *open*) ends in `s`.
Filipino does not inflect nouns for number, so the rule simply does not apply. Taught it to skip a
Filipino **enclosing literal** — never the line, because a `_t(en, fil)` call puts both languages on one
line and a line-level test would mask a real English offence sitting beside its translation. Back to
baseline **14, with all 14 English sites still flagged**: scope narrowed, teeth kept. After B3's grade
(fault 9) and J1/Z3's vocabulary (fault 10), the pattern is now unmistakable — **every text rule in this
toolchain was written for English, and the bilingual wave is surfacing them one at a time.**

**And the sharpest lesson: my fix for the role-check failure broke the page while the gate read PASS.**
The hoisted `const _IS_SUPERVISOR` was declared **inside the `try` block**, so it is block-scoped, and
the async gate forty lines below threw `ReferenceError: _IS_SUPERVISOR is not defined`. The page
rendered **325 characters with an unhandled rejection** — and `validate_role_checks` said **PASS** the
entire time, because it counts comparisons, not whether the file runs. **A green gate is not a working
page.** Caught only because I re-walked it live; both paths then re-verified — worker
`main-content: none` at first read with the gate shown, supervisor `block` at first paint with the feed
at 2,040 characters.

**What this argues for, concretely:** run the suite at milestones and expect it to indict *your own
recent work*; and when a gate turns green after a fix, **open the page anyway** — the gate proves the
property it measures, never that the code still executes.

### C-AS · Instrument fault 11 — J1 called a guarded control unguarded, and it retracted my own morning's work
The first **Tier-D whole-lifetime** walk — *one worker's career*, 18 hops over 13 surfaces, J25→J13→J7→J31,
as **Ricardo Morales, a worker in Lucena Pharmaceutical Mfg.** — ended on `resume`, which graded
**J1 0% — "14 destructive control(s)", blocker severity — on a page where every one is guarded.**

The per-entry remove calls `pushUndo(); snapshotVersion('before remove')` beneath a comment that reads
*"a novice fat-fingers the ✕ — push undo FIRST so the (already-visible) Undo button can restore it"*.
The resume delete is guarded by an inline yes/no. **J1 missed both, for two independent reasons:**

1. **`\bundo\b` cannot match `pushUndo`** — the word boundary fails against the preceding "h". The dim's
   own comment says *"slip-guard is a MECHANISM, not an attribute spelling"*; **a mechanism is not a
   spelling of its name, either.**
2. **The hop cannot follow event delegation.** These buttons carry no `onclick` and no `id`, and their
   class sits inside a **template literal** ~47 lines from the delegated handler, so neither the id nor
   the class window ever reaches the guard.

**Fixed** by teaching `GUARD` the camelCase mechanism names this codebase actually uses, making the
element's `data-*` action token an anchor in its own right, and following a **call** in that window to
the **callee's declared body**. `resume` J1 **0% → 100%**, page 97% → 98%.

**And the same fix refuted my own morning's work.** Fault 10 made J1/Z3 *see* marketplace-seller's delete
when it reads "Burahin" — **that detection half stands.** But the verdict was wrong: `handleDelete`'s
first acts are `svcRequireOnline()` and `await window.whConfirm("Delete …? This cannot be undone.")`.
**The control was never unguarded** — the guard sat 465 lines away, behind a delegated listener, in a
function never attached to `window`. **All eighteen banked J1 findings on that page are removed, six of
them mine from today**, verified by replicating the corrected detector against that page's own inline JS
(*guarded, via `handleDelete`*).

**A note on my own patience, because it changed a reading.** `resume` gave 1,618 characters with J1 N/A
on one load and 2,986 with 14 controls on the next. **Nothing about the page changed** — it needs about
twelve seconds to render a saved resume, and my settle loop had stopped waiting. A dim reporting
*"read-only surface: 0 destructive controls"* on a page still fetching its content **is not a reading of
the page; it is a reading of the wait.**

**Ten of thirteen surfaces read 100%**, and `audit-log` read 100% at **383 characters** with
`main-content: none` at first read and the gate shown — C-AI's fix met a fourth time by a walk that was
not testing it.

### C-AP, completed · hive's C1 has TWO readings, and the disclosure decides which — the full reconciliation
C-AP said the whole of hive's C1 is *"eleven distinct type sizes where the scale allows ten"*, and that
`big.length ≤ 3` **passes**. **That is true only while `#health-details` is collapsed.** A later walk in
English at desktop caught it **expanded**, and both graded checks then fail:

| `#health-details` | `bigSizes` | `big.length ≤ 3` | `sizes.length ≤ 10` | C1 | also |
|---|---|---|---|---|---|
| **closed** | `[32,24,22]` | passes (3) | **fails (11)** | **67%** | — |
| **open** | `[32,26,24,22]` | **fails (4)** | **fails (11)** | **33%** | A1 75% (`bigTiers=4`) |

Measured on both sides: collapsed 3,586 chars, expanded 4,358. The 26px tier is the *"Your hive's value"*
card — `#vs-pms`/`#vs-faults`/`#vs-knowledge` at `1.6rem` — which lives **inside** that disclosure
(`valueCardInsideDetails: true`), holding `innerHTML` "460" / "7,675" / "1,700" the whole time while
`innerText` is empty whenever it is collapsed.

**This reconciles every reading taken today, including the two I withdrew.**
- The eleven-sizes failure is **unconditional** — it holds open or closed, so C-AP's finding stands.
- The **fourth display tier is conditional** on the disclosure, which is why the first walk's
  390-vs-1280 pair looked like a width effect: one half happened to catch it expanded.
- **What varies is never the data** — the tiles always have their numbers.

**Two things for a designer, stated separately because they are separate:** the phone view carries
**eleven type sizes against a scale of ten** (unconditional), and **expanding the health disclosure adds
a fourth display tier** that breaks the hierarchy check and A1 with it. Which tier to drop is a design
call.

**And the process lesson, now paid for four times on one dim:** I explained this difference as width,
then as data arrival, then as the greeting's 19px, and only got it right after replicating **the oracle's
own two checks** against both disclosure states. *Reproduce, control the confounder, replicate the
oracle — then explain.*

### C-AT · The 60 calculator pages told a reader two untrue provenance stories at once — and E3 graded them 100%

Walked as **Jun Salvador**, a hive-**less** solo owner, phone-390, English, on the 9-hop OEE round
(`index → asset-hub → logbook → index → learn/index → learn/what-is-oee → tools/oee-calculator →
learn/index → hive`; rows **W37/W38**).

`tools/oee-calculator` carries **two claims about where its numbers come from, and they contradict each
other**:

| where | what it said | true? |
|---|---|---|
| the provenance chip | *"Static · formula-only · **computed on your device as of this page load** · no live data"* | **no** |
| the caption under the results table | *"**Computed live** by WorkHive's calculation engine"* | **no** |

Nothing computes on the reader's device and nothing is live. `83.8 %` / `90 %` / `95 %` / `98 %` sit
**literally in the markup** (line 231), and the page's only three inline scripts are JSON-LD, a tailwind
config and a Filipino dictionary. **The generator's own docstring says so** — *"a REAL worked example
computed at BUILD time (not client-side JS)"*. The tool knew; the page it emitted contradicted it twice.

**All 60 calculator pages carry both sentences** (measured: 60/60 for each), all 60 are in `sitemap.xml`
with `robots: index, follow`, and the learn articles link into them.

**E3 "Trust / transparency" read 100% on every one of them**, and G4 "Single freshness source" reported
*"1 data-freshness claim"* — it counted the chip and never saw the caption. **The trust dimension asks
whether a provenance chip EXISTS, never whether it is TRUE**, so it will pass a page whose honesty
affordance lies, and pass it confidently.

**Fixed in both places, because a generator can drift behind the pages it generates.**
`build_calc_pages.py` writes to `seo_assets/calc_pages_staging/` and promotion is Ian's gate — and staging
was **624 diff lines BEHIND** the live pages, which had since gained `og:image`, `twitter:card`,
`display=optional` and hand-applied em-dash removals the generator never learned. So regenerating and
promoting would have **regressed live copy**. The two sentences were corrected surgically in the 60 live
files *and* in the generator, so the next promotion cannot re-ship the claim. Verified live: chip and
caption now both read *"…when this page was built"*, `role="status"` preserved, G1/E3/G4/I2 all 100%, and
the markdown twins re-built so the machine channel says the same true thing (0 occurrences of either old
claim in 120 twins).

**For a designer / writer:** nothing here is a layout question. It is one rule — *a page may not describe
its own provenance twice, and the description must be what the code does.*

---

### C-AU · Instrument fault 12 — a static article is a poster, and the rubric knew the concept in only two spellings

The learn corpus was being scored **0% on G1 and 0% on I2** — *"no status region"*, *"no
reserved/optimistic block"* — for **data-page furniture a static document has no state to fill**.

G1 and I2 **already carried the right branch**, worded *"static artifact: state lives on the generator,
not the artifact"* and *"rendered once, nothing streams in"*, and the permission-wall reasoning directly
above them even names this error by analogy: **"asking a POSTER for a status region."** The branch was
keyed on exactly two shapes — `#ar-print-wrapper` and `<meta artifact-genre="poster">` — so a learn
article fell between them.

**Widened on a MEASURED predicate, never a declaration:** a page qualifies only by shipping no data layer
at all — no `utils.js` tag, no Supabase client global, and no inline script matching
`fetch|XHR|createClient|supabase`. A declaration could excuse a page that really streams; the *absence of
a client* cannot. The script **tag** is tested rather than the booted object, so a page graded before its
client finishes booting is not mistaken for a brochure. Measured: **116 pages qualify** (54 articles +
the hub + 60 calculators + the poster) and `status.html`, `validator-catalog`, `logbook`, `index`, `hive`
and `public-feed` all stay **DYNAMIC** because they genuinely fetch.

**Two instruments had independently identified the same class and only one of them acted:** the pages
carrying the most of these findings were `architecture.html` (58), `validator-catalog` (52) and
`symbol-gallery` (48) — precisely the pages `validate_loads_utils_js.py`'s own ALLOWLIST documents as
brochures that render no DB or user data.

**182 banked findings retracted** across 31 learn rows, with the record kept in each row's `clean_note`.
The **92 calculator** and **506 root** findings of the same wording were deliberately **left standing**:
the calculators pass G1/I2 on their own merits today (1 status region, 3 reserved blocks measured on
`oee-calculator`), so those are a separate question for their own re-walk rather than a mass retraction on
inference. Article results: **88% → 92%** (`what-is-oee`), and `ra-11285` **G1/I2 → N/A, C5 → 100%**.

---

### C-AV · Instrument fault 13 — "world-class" is a reliability BENCHMARK on this platform, not puffery

B2 "Plain voice & tone" read **0%** and B1 **67%** on the 60 calculator pages, because `MARKETESE`
listed `world-class` — and the comment directly above that regex claimed the listed words had *"no
literal platform use."*

**Measurably false.** Across every root, learn and calculator page: **33 occurrences on 9 pages, and all
33 are the benchmark** — world-class OEE is **85% per Nakajima TPM / ISO 22400-2**, world-class MTTR is
under two hours. It is a **named output field** of the OEE calculator (*"World-class benchmark = 85 %"*).
One of the 9 pages, `ph-industrial-benchmarks`, uses the phrase to **argue against** that framing
(*"'85 percent (world-class)' is less credible than 'current sector P75'"*). **Zero genuine puffery in
the corpus.**

**Narrowed, not removed** — the word still fires when it modifies the *product*
(`world-class platform|product|support|service|team|experience|software|solution|tool|app`), which is what
the dim exists to catch. 11 ruler cases unit-tested: the four benchmark phrasings clear, `world-class
platform` and `world-class support` still redden, and `seamless`/`revolutionary`/`best-in-class`/
`cutting-edge synergy` are untouched. Exactly the precedent already recorded in that same comment, where
`unlock` was removed for being the platform's literal gating verb. `tools/oee-calculator`: **97% → 100%,
zero failing dims.**

---

### C-AW · C5 across the whole learn corpus — and my hand measurement was exactly backwards

The learn article reported **C5 41%**, *"101 pass WCAG but miss APCA Lc"*. Measuring by hand I found
**13** offenders and concluded the failures were the small low-alpha chrome, so the body copy at alpha
0.78 could be left alone.

**Backwards.** APCA applies **Lc 75** to *columns of fluent body text* and **Lc 60** to a UI label, and
only the oracle made that distinction. Exporting the rubric's own list (`c5_offenders`, added in the same
pass — the dim had been spending its offenders on one clause of a note and dropping them) showed:

| group | n | Lc | floor |
|---|---|---|---|
| body prose @17px w400 | 44 | 70 | **75** |
| body prose @15px w400 | 43 | 68–71 | **75** |
| body prose @14/16px w400 | 9 | 70 | **75** |
| nav chrome @14px w500 | 4 | 54 | 60 |
| bold lead-in @16px w700 | 1 | 64 | **75** |

**97 of 101 were the prose; 4 were the chrome I had planned to fix.** My formula then reproduced the
oracle's Lc 70 exactly once calibrated against its published value.

**The fix carried the platform's OWN decision to a second mechanism.**
`tools/fix_learn_contrast_remap.py` had already brought `wh-tw.css`'s white-opacity ramp to all 54
articles — for Tailwind's `text-white/NN` *utility classes*. The same chrome and prose are **also**
coloured by literal `rgba(244,246,250,α)` written in each page's inline `<style>`, and those never heard
the decision: **589 text-colour declarations under alpha 0.8 across 54 pages**. Remapped on the platform's
published ramp (`0.4–0.6 → 0.8`, `0.65–0.78 → 0.85`), scoped to `color:` only so no border, background or
shadow moved (measured: 0 decorative matches, and the guard stays).

Then the 11 survivors were all **formula blocks** in `.prose-wh code` / `.prose-wh pre` at brand orange
`#FDB94A`, Lc 67 on the code panel's own lighter ground. **These are not excused while the other orange
is:** the rubric deliberately gives brand accent the Lc 60 label floor inside a link, `summary`, pill or
heading — so `.toc a:hover`, `.tool-cta a` and `.faq-item[open] summary` correctly keep `#FDB94A` — but a
formula is **content**, and code is read glyph by glyph, where a `1`/`l` confusion is the whole cost.
Lifted to `#FED38D` (the same hue blended 37% toward white, **Lc 78**, matching the platform's practice
that muted fixes land at Lc 77+).

**Result, verified by the oracle on two differently-shaped articles:** `what-is-oee` C5 **41% → 94% →
99%** (101 → 11 → 1 offenders), `ra-11285` C5 **100%, 0 offenders**, C2 100% throughout, and the English
default path unchanged (`lang=en`, 0 Filipino marks, 96%).

**One offender remains and it is a real one:** a `<strong>` lead-in inside `.callout` at
`#5FCCE8`, 15.68px w700, **Lc 64 against 75**. It is prose, so the body floor applies; the note rounds
its size to "16px" while the decision used 15.68, which is worth knowing before re-deriving it.

---

### C-AX · hive.html had no visible `h1` for anyone without a hive — which is every new account's first visit

Walked as a hive-**less** solo owner: `h1Count: 1, h1Visible: 0`.

hive.html's only `<h1>` is *"Hive Board"* (`#board-hive-name`), and it lives inside `#view-board`, which
is hidden when the reader has no hive. The visible heading was the `#view-onboard` panel's `<h2>`
*"Your Hive"*. So the document rendered with **no top-level heading at all** — and `#view-onboard` is not
an edge state: it is what **every new account** meets on its first visit to the hive page, and a
screen-reader user arriving there gets a document with no `h1`.

Promoted to `<h1>`, with the terse `heading-allow` marker the multiple-h1 rule needs. The two views are
mutually exclusive so exactly one `h1` is ever visible; the canonical board `h1` is deliberately left
un-exempt so it keeps being checked. Gate back to baseline (1 issue, `assistant.html`).

**Stated as a trade, because that is what it is:** **A1 75% → 100%** and **A2 75% → 50%** — promoting the
panel's only heading left it with no `h2`/`h3` for A2's subheading proxy, and the page total did not move
(95%). **The `h1` stays.** A one-heading invitation card is correct HTML, and a document owed every new
user a top-level heading; inventing a subheading to satisfy a scannability proxy would be gaming the
metric, not serving the reader.

**Also verified on this lane, which is why the persona was chosen:** the C-W tenant leak was found on the
hive-less surfaces, and this round was clean on every hop — **0 UUIDs and 0 foreign hive names** across
all seven surfaces, with `hive.html` giving the hive-less reader a join/create invitation rather than
another tenant's board.

---

### C-AY · The learn corpus asked a Filipino reader to act, in English

Walked the same round in **Filipino**. The mechanism works — `WH_LANG=fil`, `html lang=fil` on the hub,
all 12 of its `data-i` labels swapped from its own dictionary — and yet:

**The two words that ask the reader to act were the two left in English.** `Home` and `Learn` were
stamped `data-i` and swapped correctly; **"Sign In" and "Sign Up Free" carried no `data-i` on any of the
55 learn pages**, and no key for them lived in `wh-i18n-lite.js`'s shared `WH_FIL_PUBLIC`. So the whole
corpus rendered Filipino headings above an English call to action — the same shape as C-AK's provenance
chip that translated only its connective, and C-AH's four pages that answered in English under a Filipino
heading. *The dictionary was complete for everything except the decision.*

**Translations are the platform's own, not invented:** `Mag-sign In` and `Mag-sign Up nang Libre` are what
`i18n/marketplace.json` and `i18n/marketplace-seller.json` already ship for these exact strings; `Hive Ko`
follows `platform-actions.json`'s `Hive Board Ko`; and `Home` stays `Home` because that is what the
platform itself says (`audit-log.json`: *"Balik sa Home"*). The stamping tool **refused** to label
`Join the Hive`, `Try WorkHive free` and `Open the Hive Dashboard` as *sign up* — same `href`, different
sentence — which is the guard earning its place rather than a near miss.

**And the hub was the one learn page that never got the shared i18n floor.** All 54 articles and all 60
calculators load `wh-i18n-lite.js`; `learn/index.html` carried its own inline miniature instead, which
*worked* but knew only its **own** dictionary, so its five nav links had nowhere to resolve from. It now
loads the 4.7 KB shared floor **in the head and synchronously**, for the reason the articles state: the
language must be known before paint, so a Filipino reader is not shown English headings that then change
under them — the hub's own swap ran on `DOMContentLoaded`, i.e. after first paint. Its original comment
refused `utils.js` at 362 KB, which is still right; this file is the answer that did not exist when that
comment was written.

**The first version of that change silently un-translated the hero.** The shared applier swaps only
elements with no child elements — deliberately, *"a label containing markup is left alone rather than
flattened"* — and the hub's `h1` wraps a `<span>`. So handing the whole job to the shared applier
translated the nav and dropped the headline: 15 swapped, `lh-title` the one miss, and the page read *"Free
guides for the Philippine plant floor"* under a `lang="fil"` document. Now the shared layer does the
shared chrome and the page completes its **own** keys, which keeps the shared no-flatten promise intact.
Verified: 18/18 labels applied, 0 unapplied, hero back to *"Libreng mga gabay para sa planta ng
Pilipinas"*, nav reading *Home · Matuto · Hive Ko · Mag-sign In · Mag-sign Up nang Libre*.

**WCAG 3.1.2, and the half that is not mine to decide.** On an article the swapped nav read Filipino
under `<html lang="en">`, so a screen reader announced Filipino words with English phonetics — the same
defect C-AO found on `platform-actions` and `ph-intelligence`. The whole-document `lang` is deliberately
**not** flipped: on an article the chrome becomes Filipino while the prose stays English, so `lang="fil"`
would be as untrue as `lang="en"`, and the primary-language call is Ian's (C-AO's open boundary).
**Language *of parts* needs no such decision** — `whI18nApply` now sets `lang="fil"` on each element it
actually changed, which is exactly what 3.1.2 asks and is true in both directions. Verified: 9 swapped
labels marked, **0 prose paragraphs wrongly marked**, and in English 0 marks at all.

**Honest limit on the number:** N1 still reads 75% on the learn corpus and will keep doing so. Its
`label coverage` counts `data-i` only, and the rubric says so in its own source — *"never read this pct
as % translated"*. The truthful instrument is the **locale-flip diff** the rubric names as queued; this
walk did that flip by hand, which is how the English call to action was found at all.

### C-AZ · The same round in Filipino — five bilingual defects a locale-flip READ found and no stamp census could

Rows **W3150/W3153**: the identical 9-hop path, same persona (Jun Salvador, hive-less solo owner),
phone-390, `wh_lang=fil`. Five surfaces read **100%** and the language was genuinely applied — *"Magandang
umaga, Jun"*, *"WALA KA PANG HIVE"*, 713 chars against English's 646, which is the expansion N1 exists to
test. What the flip found was five defects, each invisible to a `data-i` census:

| where | what a Filipino reader met | scope |
|---|---|---|
| the **skip link** — `wayfinding.js` | *"Skip to main content"*, hard-coded; the file used `_t()` **zero** times | **21 pages** |
| `logbook`'s only way out | *"Back to Home"* while `i18n/audit-log.json` already ships *"Balik sa Home"* | 1 page |
| the 60 calculators' dictionary | `calc_worked: 'Worked example'` — a Filipino key holding its English source | **60 pages** |
| the calculator **provenance chip** | a `role=status` live region with **no `data-i` at all** | **60 pages** |
| `hive`'s onboard panel | an English heading + explanation between a Filipino skip link and Filipino buttons | every new account's first screen |

**The dictionary entry that equalled its source is the sharpest of the five.** `calc_worked` was stamped,
its key resolved, the swap fired — and replaced English *with English*. Every stamp census reads clean on
that: the attribute is present and the lookup succeeds. Only reading the rendered page in the other
language catches it. Same family as the wave's `_t()` wrapper, which made the stamp survive while the
translation did not.

**Nothing was invented.** `Mag-sign In` / `Mag-sign Up nang Libre` are what `i18n/marketplace.json` and
`marketplace-seller.json` already ship; `Hive Ko` follows `platform-actions.json`'s `Hive Board Ko`;
`Balik sa Home` comes from `audit-log.json`; `Matuto` was already in `WH_FIL_PUBLIC` (and corrected my own
guess of *"Mga Gabay"*); `Home` stays `Home` because the platform says so. Only two strings needed new
Filipino — the skip link and the onboard pair — and the onboard keys were generated with
`i18n_page_dict.py`'s **own** `key_of()` so a future `--apply` cannot create a duplicate for the same
string.

**And `--apply` was deliberately NOT run.** It rewrites `i18n/pages/<page>.fil.json` from the translated
extract, and the three Shift Handover keys added earlier today are **already stamped**, so the extractor
no longer sees them — the tool would have emitted a file containing only the new strings and silently
dropped this morning's work. Checked before running, then hand-added: 3 keys → 5, all preserved.

**WCAG 3.1.2, and the half that stays Ian's.** Swapped labels now declare `lang="fil"` individually
(`wh-i18n-lite`'s applier, and the skip link). The whole-document `lang` is deliberately not flipped on an
article: the chrome becomes Filipino while the prose stays English, so `lang="fil"` would be as untrue as
`lang="en"`, and that primary-language call is C-AO's open boundary. Verified: 9 labels marked, **0 prose
paragraphs wrongly marked**, and in English **0 marks at all**.

---

### C-BA · A hive-less reader's browser fired three reads that could not succeed

Found on the Filipino hop to `hive.html`, in the console rather than the rubric: **three 400 Bad
Requests, every one of them `hive_id=eq.`** — nothing after the operator.

`HIVE_ID` is `whHiveId() || ''` (hive.html ~1915), so with no hive the three reads in `loadFeed()`'s
`Promise.all` — `v_logbook_truth` twice and `pm_completions` once — went out with an empty filter and
PostgREST rejected all three, **on every page load**. `#view-onboard` is what **every new account** sees
first, so this is three wasted round trips on a plant-floor phone at the exact moment someone is deciding
whether the product works.

**The waste is the smaller half.** The `A5 honest-degraded` branch immediately below captures any of those
errors as `feedReadErr` and paints *"couldn't load"* with a dashed count — deliberately, so a failed read
never renders as a fake-empty "quiet hive". That is the right answer to a failure and the **wrong** answer
to *"you have no hive yet"*, which is not a failure at all. The page already owns the guard idiom
(`if (HIVE_ID)` before the membership re-validation); this asks the same question one function earlier.

**Proven in both directions, because a fix that silences errors by skipping work must be shown not to skip
real work:**

| `HIVE_ID` | reads fired | malformed | console errors |
|---|---|---|---|
| `''` (hive-less) | **0** | 0 | **0** |
| a well-formed uuid | **3** | **0** | — |

The skeleton is cleared rather than left spinning, since a stuck skeleton is invisible to every gate.

**Why the rubric never saw it:** the surveyed page was *correct* — the onboard invitation renders, 0 UUIDs,
0 foreign hive names, 95%. The defect lived entirely in the network tab. A dim census grades what is
painted; **the console is a separate oracle, and this round is the argument for reading it on every hop.**

---

### C-BB · Instrument fault 14 — F1 flagged a sentence, and the reading changed between two loads of the same file

`F1` fell to **96%** and `K2` to **50%** on the learn article over the phrase *"maintenance metrics guide:
OEE, MTBF…"* inside a `.callout` — running text that **WCAG 2.5.8's Inline exception** covers, which is
the exception `_inlineProse` exists to implement and whose wording its own comment quotes.

Two independent misses, both about form rather than fact:
1. **the container check was a TAG LIST** — `closest('p, li, dd, td, th, figcaption, blockquote, small')`.
   The learn callouts put running text directly in a `<div class="callout">`, so the link was disqualified
   for its parent's *tag name* while sitting mid-sentence. Now: any block ancestor carrying substantially
   more text than the link — the property the tag list stood in for, with the existing text-ratio check
   still protecting the rule (a lone link is a button-shaped CTA and still owes the floor).
2. **the one-line height test punished WRAPPING** — `height > fs * 1.8` was meant to catch a link made
   block-shaped, and also rejects any inline link long enough to wrap. Measured **43.66px against a
   28.22px limit**: two line boxes of a 26.656px line-height. A wrapped link failed a test for *"is it one
   line tall."* Now many line boxes are **positive** evidence of inline flow — `getClientRects()` returns
   one rect per line box and only an inline box is ever fragmented.

**★AND THE READING WAS INTERMITTENT, WITH A REAL CAUSE.** The same file read F1 **100% (28/28)** at one
load and **96% (27/28)** at the next, viewport verified 390 both times, no source change between them — and
the link measured **2** line boxes early and **3** later. The learn pages load Poppins with
**`&display=optional`**, so if the face is not ready at first paint the fallback is used for that whole
page load; fallback and Poppins have different glyph widths, and **any wrap-dependent measurement varies
between loads of the same bytes.**

**Before blaming my own last edit, I proved it could not be the cause:** a live `!important` override of
the callout colour left the height at 43.66 both ways. One control killed the hypothesis in a single call.

**Teeth verified on a fresh exemption, with three injected probes:** a block-shaped `Buy(60x20)` and a lone
`Solo(35x24)` still flag; a prose-surrounded phrase is exempt. An exemption that is too generous is worse
than the bug it fixes.

---

### C-BC · OPEN QUESTION (not fixed, deliberately) — is a PRE-TENANT invitation a data page?

`hive.html` walked as a hive-less owner reports **E3 0% "NO source chip"**, **H1 0% "no goal-gradient
mechanism on a worker-daily page"** and **A2 50% "headings=1"** — against a screen that displays no data
at all: an invitation to create or join a hive.

This is the third time today the same shape has appeared, and the rubric's own permission-wall note
states the principle: *"a permission wall is a DIFFERENT SCREEN wearing the same filename… grading that
against a DATA page's furniture is the same error as asking a poster for a status region."* A pre-tenant
invitation is that too — there is no hive, so there is no hive data to attribute (E3) and no work to show
progress on (H1).

**Why it is recorded rather than fixed, unlike faults 12–14.** Those three were widenings of a concept the
rubric already implemented, each keyed to a mechanism the platform already shipped. This one is not:
- `isPermWall` keys on `.gate-card, [id^="gate-"]` **plus** permission vocabulary. The vocabulary would
  already match — `_permVocab` contains `join a hive` and `sumali (muna) sa hive` — but the **structure**
  does not: hive.html uses `#view-onboard`, while `alert-hub` and `project-manager` use the platform's
  `gate-no-hive`. So the two halves of the existing test disagree about this screen.
- Making the page match by adding `.gate-card` would change how the card LOOKS (it is a styled class), and
  the element already has an id, so `[id^="gate-"]` is unavailable. A new marker plus a new rubric branch
  is a genuine convention change, and the honest wording is not "permission wall" — nobody is being
  refused; the person simply has no tenant yet.
- E3's reading is also partly a detection question in its own right: the page's provenance IS present as
  a `<details>` *"About this dashboard's data sources"*, not as a chip.

**Recommendation, for a deliberate decision rather than a fourth instrument edit in one turn:** give the
pre-tenant state its own explicit marker (`data-wh-state="pre-tenant"`, no visual effect) and its own
rubric branch worded for what it is — *"pre-tenant state: this reader has no hive yet, so there is no
hive data to attribute and no work to progress"* — covering **E3 and H1 only**. **A2 should stay
MEASURED**: a one-heading card genuinely offers nothing to scan, and excusing scannability wherever a page
is sparse is how a dim stops biting.

---

### C-BD · The learn article's C1 — eight type sizes inside a 4.5px band, and no declared scale to align them to

`C1 67%` on `learn/what-is-oee-how-to-calculate`: `bigSizes=[30,28,22]` passes (3, at the limit of
`maxDisplaySizes: 3`) and `distinct=13` fails `maxSizeTiers: 10`. Reading the page's own stylesheet gives
**14 declared sizes**, and the actionable half is where they sit:

| px | rem | first selector |
|---|---|---|
| 28.00 | 1.75 | `.prose-wh h2` |
| 22.40 | 1.4 | `.faq-item summary::after` |
| 21.60 | 1.35 | `.cta-box h4` |
| 19.20 | 1.2 | `.prose-wh h3` |
| **17.60** | 1.1 | `.author-card .avatar` |
| **16.80** | 1.05 | `.prose-wh`, `.answer-first` |
| **15.68** | 0.98 | `.callout` |
| **15.20** | 0.95 | `.prose-wh table`, `pre`, `.faq-answer` |
| **14.72** | 0.92 | `.prose-wh code`, `.toc li` |
| **14.40** | 0.9 | `.audience-block ul`, `nav a.nav-link` |
| **13.60** | 0.85 | `.prose-wh th`, `.breadcrumb` |
| **13.12** | 0.82 | `.cta-secondary`, author meta |
| 11.20 | 0.7 | `.toc h2`, `.cta-eyebrow` |
| 10.40 | 0.65 | `.pill` |

**Eight of the fourteen sit between 13.12 and 17.60 — a 4.5px band containing 0.82 / 0.85 / 0.9 / 0.92 /
0.95 / 0.98 / 1.05 / 1.1 rem.** Nobody perceives 14.40 against 14.72. That is the drift C1 counts, and
it is where any consolidation should happen.

**Why this is NOT fixed here, unlike the contrast ramp.** The C5 work could carry the platform's *own*
answer: `wh-tw.css` declares the white-opacity remap, so applying it to the literal `rgba()` declarations
was alignment, not taste. **There is no equivalent for type.** `tokens.css` declares `--wh-font` (family)
and the colour tiers, and `--wh-radius-sm/--wh-radius/--wh-radius-lg` — which is exactly why **S1 can
check radii for CONFORMANCE against declared tokens** (`declared=[8,12,16] · offRadius=0/10`). Type has
no declared scale, so C1 can only ever count tiers, and picking which of the eight to drop would be my
aesthetic judgement dressed as a fix. C-AP reached the same boundary on hive: *"which tier to drop is a
design call."*

**The recommendation is therefore one level up: declare a type scale in `tokens.css`, the way radius
already is.** Then C1's count limit gains a conformance partner, an off-scale size becomes as visible as
an off-scale radius is today, and the consolidation becomes mechanical rather than a matter of taste —
`hive`'s `1.18rem → 1.125rem` alignment earlier in this program was only defensible because 18px was
obviously off a scale that was never written down.

---

### C-BE · LEAD (measured census, not a finding) — the same literal-rgba bypass exists in the root pages

The C5 work on the learn corpus turned on one mechanism gap: `wh-tw.css` remaps Tailwind's
`text-white/NN` **utility classes**, and a literal `rgba()` written in a page's own inline `<style>`
never hears that decision. Scanning the root pages for the identical shape:

**119 literal low-alpha TEXT-colour declarations across 24 root pages** — `index.html` 29,
`integrations` 13, `design-system` 11, `hive` 9, `community` 8, `ai-quality` 7, `engineering-design` 7,
`logbook` 6, `symbol-gallery` 6. Almost all are white: `rgba(255,255,255,0.72)` ×22,
`rgba(255,255,255,.6)` ×20, `0.78` ×12, `0.62` ×10.

**This is logged as a LEAD and deliberately NOT remapped, because alpha is not a defect count.** APCA's
floor depends on size and weight: white at 0.72 clears Lc 45 at 24px and misses Lc 75 in a column of
15px prose. Bulk-lifting 119 declarations on the strength of their alpha would repeat the error of
counting small targets instead of measuring defects — and the learn fix was only defensible because the
oracle had already named its 101 offenders and the platform had already declared the ramp.

**How it gets settled without a separate campaign:** `index`, `hive`, `logbook`, `community`,
`engineering-design` and `integrations` are all on the remaining walk queue, and `c5_offenders` is now
exported, so each walk reports exactly which of its declarations actually fail and at what size. The
census says where to look; the walks say what is broken. Any fix then carries the platform's own ramp,
per-declaration, with the oracle re-run — never a sweep keyed on the alpha alone.

---

### C-BF · The milestone board, read to the end — 13 failures, 11 settled, and what the last two actually are

The `--fast` run at this wave's close: **712 PASS · 13 FAIL · 512 SKIP**, 2,205s. Every failure was read
rather than assumed, and eleven were settled. Four are worth recording as a class, because in each one
**the platform had improved and the gate had not heard**:

| gate | what it said | what was true |
|---|---|---|
| `community` | *"Supabase CDN not found in `<head>`"* | the platform vendored supabase-js — **38 root pages use the local SRI-pinned copy, 0 use a CDN**. The check required a jsdelivr/unpkg URL, so it failed the page for dropping a third-party dependency. Its *message* also named `<head>` placement, which it never tested. Replaced with the property the message actually cares about: the library must load **before the first `createClient`/`getDb`** call. 6 teeth cases; 32/32. |
| `connection-surface-discovery` + `connection-pool-saturation` | *"1 unregistered connection surface: vendor/supabase-js…"*, *"realtime surfaces 15 > baseline 14"* | one false positive reddening two gates. `mine_capacity_signals.py`'s `SKIP_DIRS` comment says *"vendored / generated / server-side"* and **omitted the directory literally named `vendor`** — so the minified bundle's own `.channel(`/`.subscribe(` counted it as an application surface. Re-baselining to 15 would have blessed the library and hidden the next real surface behind it. Both back to **14/14**. |
| `Q5 graceful-429` | *"classification test FAILED/absent"* | the 429 hints were wrapped in `_tt(en, fil)` so a Filipino reader gets a Filipino explanation of a rate limit — and the harness still evaluated the extracted block with only `m` in scope, dying on `ReferenceError: _tt is not defined`. The code was right; the test was stale. Now injects the translator and lifts the real `OPAQUE_NETWORK` regex from source, and classifies all seven bodies **twice** — the Filipino pass asserting each branch returns different, non-empty text. **14/14**, stronger than before. |
| `unchecked-writes` | `pdf-ingest:239`, against a **0 baseline** | the comment directly above that write names the exact lie — *"a kb_documents row left at 'processing' forever… a reader would treat a half-embedded manual as one still on its way"* — and the write discarded its `{ error }`. On failure the row stays `processing` while the function returns `status:"done"`. The failure is now carried in the job's `error_message` and a `doc_status_written` flag; deliberately not thrown, since the chunks really did embed. |

Also settled: `T50` destructive roster (regenerated, 60 confirms), `tenant-refusal` (**65/65 tables + 7/7
BOLA + 3/3 write-authz** all green — the FAIL was one *undeclared blind control* on `client_errors`,
declared from its own policy: `client_errors_read USING hm.role = 'supervisor'`, and its migration says
*"A worker does not need to read the error log"*), `memory write-quality` (my two folded FAMILY index
lines were 284 and 268 chars against a 200 limit), `substrate freshness` (my own ordering — see below),
and `inventory-integrity`.

**`inventory-integrity`, in full, because the archaeology is the lesson.** *"27 transactions with invalid
type ['adjust', 'receive']"*. `inventory.html` writes exactly four types — `use` (1860), `restock` (1973),
`adjustment` (1665), `add` (1713) — which is also the validator's allowed set, derived from those lines.
The 27 rows came from two writers: **18 from `tools/backfill_fleet_seed_gaps.py`**, whose `TXN_TYPES`
comment claimed *"the vocabulary inventory.html itself writes and reads"* while listing two values it
never writes; and **9 from the 2026-09-09 opening-balance repair**, whose own note explains it was fixing
a real one-sided ledger (*"the opening stock this item was created with, which the seeder wrote to the
shelf without a matching ledger row"*) — a correct repair that introduced a misspelling while making it.
**The tell was in the renderer:** `inventory.html:894/896` accepts *both* spellings of each concept, so
someone met the drift downstream and accommodated it at the display layer instead of at the writer.
Fixed at the writer (seeder corrected, its sign logic with it) and the 27 rows normalised; 6 pass · 0 fail.

**The two that remain, and why neither is a quiet skip:**

1. **`deploy-root-hygiene` — Ian's.** `.vercelignore` is untracked, so it excludes nothing; the gate says
   in its own words that it needs a **commit**, not a `git add`.
2. **`logbook-consistency` — a data-semantics decision, deliberately not made alone.** The validator
   printed a 1,000-row sample; the real figure is **7,987 Closed entries with no `closed_at` against
   23,211 that have one (25.6%)**, every one a `fleetbf-` prefixed Ramos Jeepney inspection for Oscar
   Ramos. `fleetbf` appears in **no file in the repo** — the writer was an ad-hoc backfill in a past
   session, so there is nothing upstream left to fix and only the rows remain. **The repair is not
   mechanical:** filling `closed_at` requires asserting *when* those jobs closed, and any value I choose
   propagates straight into MTTR. `created_at` would make 7,987 same-day closes and an MTTR of ~0 for a
   quarter of all closed history — a fabricated metric is worse than a null a reader can see is missing.
   **Recommendation:** treat these as same-day inspection closes (`closed_at = created_at`) *only* if the
   fleet story wants them in MTTR, and record the assumption in the row's note so no reader mistakes a
   backfilled close time for a measured one; otherwise leave the nulls and teach the gate that this
   seeded cohort is a declared exception with its count frozen, so a NEW null still fails.
3. **`sentinel-review` — a real gap, sized honestly.** One TIER 1 rule, `groq_fallback`'s
   `models_are_live`, has **zero** anchored tests and needs two. It is a *live-provider* check born
   2026-09-10 (it asks each provider's `/models` endpoint with the platform's own key, after four dead
   Groq models made every AI call walk four 404s). A Playwright journey cannot re-assert provider
   inventory; the meaningful anchors are on the **failure path's honesty** — that a total-chain failure
   says something it has evidence for, rather than `voice-model-call`'s *"All models failed (rate limited
   or down)"*, which was a diagnosis it could not support. That is test-writing against the `whPage`
   harness, and titling two stubs to satisfy the anchor count would be the same gaming refused for A2's
   subheading.

---

### C-BG · The main board had eleven sections and one heading

Rows **W348/W349**: the 5-hop worker round (`hive → logbook → pm-scheduler → hive → alert-hub`) as
**Wilfredo Malabanan**, a plain member of Baguio Textile Mills, phone-390, English — cast through the
**product's own sign-in** after clearing `wh_*`/`sb-`/sessionStorage, so the tenant was resolved by the
product rather than by a programmatic session.

Every hop was tenant-clean (**0 UUIDs, 0 foreign hive names**), and the return visit to `hive` was
byte-identical — 2,015 chars, same tenant, 15 feed entries — so identity did not drift mid-walk. Three of
four surfaces read **100%**. The finding was on the fourth:

**`hive.html` paints 11 visible section cards and exposed exactly ONE heading.** `h1` = the hive name;
zero `h2`/`h3`; zero `role="heading"`. Its section titles ship as styled paragraphs — *"On Shift Now"* as
an 11px `<p>`, *"Your open work"* as a 9.92px/700 `<p>` — so a screen-reader user on the platform's
most-used screen could reach one landmark and had **no map of the other ten sections**. WCAG 1.3.1.

**And it is the same signal that read A2 50% in the hive-LESS state** (C-AX), which turns out to have been
pointing at something real in *both* states rather than being a sparse-card artifact. A2's proxy earned
more trust here than I gave it.

**Fixed with `role="heading" aria-level="2"` on the seven board section labels, not by swapping tags.**
Swapping `<p>` → `<h2>` would inherit the browser's default margins and change the layout; the ARIA
retrofit is zero-visual-change, leaves every class, inline style and `data-i` key intact, and keeps the
heading-hierarchy gate at its baseline because `role="heading"` is not an h-tag. Measured:

| | before | after |
|---|---|---|
| headings a screen reader can navigate | **1** | **6** |
| A2 | 50% | **75%** |
| page | 99% | **100%** |

Team Pulse and Approval Queue are supervisor-only and correctly absent for a worker, which is why six
rather than eight. **A2's remainder is its own `h2`/`h3` TAG sub-check** — it counts role-aware headings
in one clause and literal tags in another, so an ARIA-correct page cannot fully satisfy it. That is an
instrument note, not a page defect, and the page is now navigable either way.

**★THIS ROUND WAS ALSO THE REGRESSION TEST FOR C-BA's GUARD.** The `loadFeed` early return added earlier
in the same turn had been proven against a *synthetic* `HIVE_ID`; here a **real member's feed rendered 15
entries** with `#feed-empty` hidden and the board visible. A fix that silences errors by skipping work is
only honest once you have watched the work still happen for the person it belongs to.

Closing the loop from the other side: `pm-scheduler`'s advisory reads *Tap the "Overdue" chip below* and
the chip in English reads **Overdue** — the C-AH quoted-label fix, which was found because in Filipino
that same chip renders *"Lampas sa Takda"*, now verified in the English lane too.

---

### C-BH · The device pair, and the program's first delta with a mechanism

Rows **W3149/W3152**: the same 9-hop solo-owner OEE round at **desktop-1280**, the pair for the phone-390
round (W37/W38) walked earlier the same turn, same persona, same language. Viewport read back as 1280 CSS
before the first survey — `browser_resize` takes DEVICE pixels at dpr 0.667.

| page | phone-390 | desktop-1280 | |
|---|---|---|---|
| index | 100% | 100% | same |
| asset-hub | 100% | 100% | same |
| logbook | 100% | 100% | same |
| learn/index | 100% | 100% | same |
| learn/what-is-oee | 96% | 96% | same, identical three failures |
| tools/oee-calculator | 100% | 100% | same |
| **hive** | **95%** | **96%** | **+1** |

**Six of seven show zero delta, and every corpus fix made at phone holds at desktop** — the
static-document branch still reads G1/I2 as N/A on the article, C5 stays clean, the calculator's corrected
provenance chip is unchanged.

**The one delta resolves to a single dim with the SAME denominator:** hive's `N1 label coverage 2/3` at 390
against `3/3` at 1280. Same three labelled controls counted, one stamped at one width and not the other —
so the hive-less board renders a **different labelled control per width**, and the phone-only one carries
no `data-i`. This program had recorded *not one confirmed device delta*; this is the first with a
mechanism rather than a confound, and it is a **visible-label-SET** difference, not a defect that appears
at one width only.

`C1`'s display tier also scales as designed (`bigSizes` 30 at phone, **43** at desktop) while both widths
fail the same `distinct=13` type-tier count — that is C-BD's finding, not a device effect. Tenant clean on
every hop: 0 UUIDs, no foreign hive name anywhere.

---

### C-BI · The navigation hub announced itself in English on 32 pages

Following that N1 coverage difference into the chrome produced a finding the width question was only the
doorway to. **`nav-hub.js` already wraps five aria-labels in `_tt()`** — the panel (*"Nabigasyon"*), the
connection pill, the connectivity detail, *Open companion* (*"Buksan ang katulong"*), *Send feedback* —
and **hard-coded four**: the FAB itself, *Open global search*, *Search tools* (label **and** placeholder),
and *Tool view mode*, plus its two dynamic `setAttribute` sites.

So on **32 pages** a Filipino screen-reader user met a navigation hub that **announced itself in English
while every control inside it spoke Filipino**. The pattern was in the file; it had simply not travelled
to every label — and the sibling `companion-launcher.js` already does it right
(`aria-label="${_tt('Voice command', 'Utos sa boses')}"`), which is what made the omission legible.

**Why nothing caught it: an `aria-label` is invisible to a sighted reader.** No stamp census sees it —
there is no `data-i` on an attribute — and no visible-text diff moves when it changes. It is reachable
only by reading the accessible name, which is why this surfaced from a census of *labelled controls*
rather than from any dim.

Six sites now bilingual, verified in both directions: FIL reads *Buksan ang nabigasyon · Buksan ang global
search · Maghanap ng tools · Paraan ng pagtingin sa tools*, EN reads its original wording with 0 Filipino
marks, and the five that were already correct are untouched.

**★AND THE FIRST VERIFICATION READ ENGLISH ANYWAY.** `nav-hub.js` is a `sw.js` SHELL_FILES entry, so the
service worker was still serving the cached copy — my edit was on disk and not in the browser. That is the
cache gate's entire purpose (it failed on `nav-hub.js` newer than `sw.js` the moment I asked), and the
standing lesson: **a shell-file edit is not live until the cache name moves.** Bumped to v375, SW
unregistered, caches cleared, then the labels rendered.

---

### C-BJ · The 2x2 grid closed, and it caught my own translation

Rows **W3151/W3154** complete the device-by-language grid for the 9-hop solo-owner OEE round:

| | phone-390 | desktop-1280 |
|---|---|---|
| **English** | W37/W38 | W3149/W3152 |
| **Filipino** | W3150/W3153 | W3151/W3154 |

Six of seven pages read **100%** in this last cell, and every shared-layer i18n fix made earlier in the
same turn held at desktop width: the nav-hub FAB announcing *"Buksan ang nabigasyon"*, the skip link
*"Laktawan papunta sa main content"*, logbook's *"Balik sa Home"*, asset-hub's advisory with zero English
leftovers, the calculator's *"Static · pormula lang · ang halimbawa ay kinuwenta noong binuo ang page"*
under the heading *"Halimbawang may solusyon"*, and the learn hub's nav.

**★AND THE CELL CAUGHT A DEFECT I HAD INTRODUCED HOURS EARLIER, IN THE SAME TURN.** `hive` read
**B3 67% — one sentence over the 20-word bar**, and the sentence was the Filipino onboard copy I wrote
when fixing C-AY:

| | words |
|---|---|
| English original | *"Join or create a team to share work, see who's active, and track your hive's jobs in real time."* | **19** |
| my Filipino | *"…makabahagi ng trabaho, makita kung sino ang aktibo, at masubaybayan…"* | **25** |

**Filipino expands.** The English passed with one word of margin and a faithful translation of it cannot.
I checked the meaning, the register and the platform's own vocabulary, and never checked the **length
against the rule the English half had to pass.**

**Which half of the ruler caught it matters:** B3's *grade* correctly declined — `grade=n/a (FK is
English-calibrated)`, fault 9's fix working exactly as designed — while its **word count**, which is
language-neutral, did the catching. An instrument that knows which part of itself is language-specific can
still enforce the part that isn't.

Split into two sentences (9 and 16 words): B3 **67 → 100%**, hive **95 → 96%**, which makes the FIL and EN
desktop cells **agree exactly**. Worth stating plainly: before that fix the apparent FIL/EN "delta" on
this page was **my own copy**, not the product — a zero-delta pair only means something once both halves
have been measured.

### C-BK · A supervisor's summary stayed on screen after she became a worker somewhere else

**Walked 2026-09-11** — J26 *"two hives, one person"*, phone-390, `wh_lang=fil`, rows W3273/W3276.
Cast: **Christine Dizon**, supervisor in Baguio Textile Mills and Lucena Pharmaceutical Mfg., **worker**
in Manila Electronics Assembly. She is the only person in that pair who is *not* in
`marketplace_platform_admins` — Pablo Aguilar is, and an admin may answer a ROUTE question but never an
entitlement one, so he is not castable for this claim.

`loadSupervisorSummary()` opened with a bare early-return:

```js
if (!HIVE_ID || HIVE_ROLE !== 'supervisor') return;   // never undoes the previous hive's reveal
```

The reveal it fails to undo is its own, two lines below (`host.classList.remove('hidden')`). So switching
**supervisor(Baguio) → worker(Manila)** left the entire supervisor summary painted — and because the
function returns *before writing anything*, every value inside it stayed the hive she had just **left**:

| element | rendered after the switch | whose number that is | Manila's own truth |
|---|---|---|---|
| `#ss-rd-stair` | "Stair 1 · Digital Logbook" | Baguio (`current_stair` 1) | stair **2** |
| `#ss-rd-weak` | "Ayusin ang Data (46/100)" | Baguio (`data_quality` 46) | **44** |
| `#stair-badge` / `#stair-composite` | "Stair 2 · Disciplined" / 66 | **Manila — correct** | ✓ |

Two contradictory readiness claims on one board, and the wrong one belonged to a tenant Manila's members
cannot see. Stable across **8.5 seconds** of re-reads, and **absent on a fresh load of the same hive** —
so it is the switch, not the data.

**Two defects in one:** a worker is shown a supervisor-shaped surface, *and* it is another hive's.

`hive.html` already documents this demotion bug arriving through three other doors — **H8b** in the
page-load path, **H8d** for `html.is-supervisor` and `#my-work-card` on `switchToHive`. Both of those
reconciled a *marker*. This is the fourth door, the surface itself, and the first to carry another hive's
numbers through it. **Fixed** by hiding the host on the way out, and verified in both directions: hidden
as a Manila worker, shown with **Lucena's own 546/7158/1171** as its supervisor. Re-verified on the fleet
pair (**Ben Ocampo**, worker in both Dela Cruz Delivery Fleet and Tan Delivery Vans), where a
worker→worker switch moved the value card **2/2877/0 → 4/3666/0**, each hive's own row, with the summary
correctly hidden throughout.

**★AND THE FIRST THING I WROTE ABOUT THIS WAS WRONG.** The value card showed **460/7675/1700** under
Manila's name — the identical triple I had recorded on a Baguio board hours earlier — and I began drafting
it as the leak. Manila's own `v_hive_value_summary` row **is** 460/7675/1700: the card was right and my
memory of which hive I had been in was wrong. Likewise the PM tile reads **29 in both hives** because both
genuinely hold 30 `is_due` rows, so that tile cannot separate them at all. The boundary claim rests on the
value card, which can, and which rendered correctly. *Reproduce first, then explain* — the third time this
program has paid for that rule.

**Boundary proven the required way.** Through PostgREST with each person's **own token**, never the owner
connection: Christine's returns exactly her three hives, Ben's exactly his two, neither seeing the other's.

### C-BL · The door between a person's two workplaces, translated only on the way out

Of the **six** strings a multi-hive Filipino person reads in the hive-switch sheet, exactly **one** carried
a `data-i`. The sheet read:

> Your Hives | Switch between hives or join a new one. | Supervisor | Worker | Active | Join Another Hive | **Kanselahin**

The only word she could act on was the one that **backs out**. And the sheet is invisible to every
page-at-rest rubric sweep, because it renders inside a hidden modal — which is why 60+ graded walks of
`hive` never saw it, and why an in-motion critique must open the menus the journey depends on.

Fixed: the title, subtitle and join button stamped and given values; the generated rows' role words
(`supervisor`/`worker`, printed raw under a CSS `capitalize`) routed through `_swRole()`, and the "Active"
badge through `_t()`. Verified live — the sheet now reads *"Ang Mga Hive Mo | Lumipat ng hive o sumali sa
bago. | Superbisor | Manggagawa | Kasalukuyan | Sumali sa Ibang Hive | Kanselahin."*

### C-BM · Two runtime writes overwrote a translation the dictionary already held

`WH_FIL_COMMON.switchhive` is `"Lumipat ng Hive"` and the button carries `data-i="switchhive"`, so the
applier had already translated it. Then `updateSwitchButton()` overwrote it to append a count:

```js
btn.textContent = `Switch Hive (${list.length})`;    // English literal over a translated element
```

Every sibling in that same menu reads Filipino — *Palitan ang Pangalan*, *I-export ang Hive Data*, *Umalis
sa Hive* — so the one control this whole archetype turns on was the single item she could not read. The
stock CTA had the identical shape (`Restock (1 out of stock) →` over `data-i="restock"` = *"Mag-restock
→"*). Both now go through `_t()`.

This is the general rule the fix encodes: **a runtime write over a `data-i` element owes the same
translation the dictionary already holds.** Kin of `feedback_the_js_overwrote_its_own_correct_markup`.

### C-BN · Two `data-i` keys that no dictionary defines — on the card that asks "was this worth it?"

`hiveValueBadge` and `hiveValueSub` sit on the two spans above the value tiles and named keys that resolve
in **none** of the live dictionaries — not `WH_FIL`, not `WH_FIL_COMMON`, not the fetched page dict. So the
renewal card announced itself as *"Your hive's value / what this hive has delivered so far"* in English,
directly above three perfectly Filipino labels.

The dictionary's own comment records the same fix for the **five sibling keys of that very card** on
2026-09-05 (`vsPms`, `vsFaults`, `vsKnow`, `vsEmpty`, …). The card's header and subtitle were left behind.

**A stamp that resolves nowhere still counts toward label coverage** — which is exactly why N1 read 100%
here. See C-BO.

### C-BO · The i18n ruler graded the mechanism, so it could not fail — and was wrong twice more before it was right

`hive` read **N1 100%** on a Filipino board holding **39 English strings**. The note says precisely what it
measured: `WH_LANG=true · lang=fil · label coverage 9/9 · data-i=101` — the *wiring*, never the words. Its
own honest-limit comment had already admitted this and queued the fix as "a locale-flip diff … a real
instrument change, not faked here." Meanwhile **every FIL cell of the deepwalk grid** was being graded by a
check that could not fail.

**The flip is unnecessary when the page has already flipped.** A deepwalk *arrives* in Filipino, so the
question is exactly answerable on the spot: each visible `[data-i]` names a key, the live dictionaries hold
the value, and the rendered text either matches it or does not. That is **fault 16**.

**Then it failed its second page, for the reason it was built to catch.** It *named* its dictionaries, and
`logbook` keeps its page dict in a **fourth** global (`WH_FIL_PAGE`) — so it reported 8 keys as undefined
while all eight rendered perfect Filipino, dropping a correct page to 80%. A hard-coded list of mechanisms
is the same mistake as counting stamps: it asks *how* the page translates instead of *whether* it did. Fixed
by **discovering** every `WH_FIL*` global.

**Then it failed its third page.** `Object.keys(window)` put the shared dict first, while `whI18nApply`
merges **common < page-visible < the page's own** (`utils.js:1688` — "a page's own dict still wins per
key"). So three PM status labels were compared against the shared `"Lumipas na"` while the page correctly
says `"Lampas na sa takda"` — a correct page at 80% again. Fixed by ranking the dictionaries **the way the
applier does**.

**And the grade now fires only when what replaced the translation is ENGLISH.** `utils.js:1699` states the
contract deliberately: *"this swap owns an element's text only until the application writes its own"* —
founder-console writing a computed "All clear" over `data-i="p_loading"` is the behaviour that rule exists
to protect. So "differs from the dictionary" cannot be the test. A second *Filipino* wording is recorded as
a lead instead — worth a reader's eye, since one concept then carries two wordings and only one is visible
to whoever maintains the dictionary.

**Teeth, on the live pages:** N1 falls **100 → 80** and names the offender when a stamp is clobbered with
English; every walked page reads 100% clean.

**Fault 17, found the same day.** A2 counted `role="heading"` in one check and refused it in another:
`heads` (line 376) is `h1,h2,h3,h4,[role="heading"]`, while its fourth check was `$$('h2,h3')` commented
*"real heading structure, not styled divs"*. So two worker boards read `headings=5 (h2/h3=0)` and
`headings=8 (h2/h3=0)` — five and eight headings that the same dim, one line apart, agreed were headings
and then would not count. A `role="heading" aria-level="2"` element is not a styled div; it is **the** ARIA
semantic, and it is what the board deliberately uses on its section labels (added 2026-09-11, C-BG). The
file had already learned this ten lines below for `[aria-expanded]`. Fixed for levels 2–3 only — a page
title alone is not internal structure. Teeth: A2 falls **100 → 75** when the aria-levels are stripped.

**The program-level correction:** any FIL cell banked before today was graded by an N1 that could not fail
and an A2 blind to the platform's own heading mechanism. Those grades are not wrong about the *mechanism*;
they simply never asked the question this dim exists to ask.

### C-BP · The language can be changed on 5 of 41 pages — RECOMMENDATION, Ian's call

`pm-scheduler` has **no language toggle at all**: no EN/FIL control, no `setLang`, nothing. It loads
`utils.js`, so it *honours* the stored `wh_lang` — it simply offers no way to set it. Censused across the
root pages: **5 of 41 carry a toggle, 36 do not**, including `logbook`, `alert-hub`, `inventory`,
`asset-hub`, `dayplanner` and `community` — the worker's entire daily surface.

**Scope stated honestly:** the preference is global, so setting it once on the hub carries everywhere. This
is *not* "36 pages are stuck in English." It is: a person who arrives directly at any of the other 36 — a
deep link, an e-mail, a QR print, a search result — **cannot change language where they landed**.

**Recommendation:** put the toggle in `nav-hub.js`'s shared chrome, which already renders on 31–32 pages
and was made bilingual in v375. One file, one edit, the whole daily surface. Not shipped unilaterally: this
adds a visible control to 31 pages, which is a placement decision rather than a defect fix.

### C-BQ · Two reads that are unscoped by construction for a multi-hive person — LEAD, not a finding

`logbook` issues two reads filtered by `worker_name` with **no `hive_id` at all** (`asset_nodes`,
`v_inventory_items_truth`), and its main read adds a `hive_id.is.null` disjunct. For someone in three
hives, RLS returns **all three**, so the shape does not scope to the hive on screen.

**It does not fire for this cast, and the evidence says why:** Christine's **1,017** logbook rows and 6
assets are *all* in Manila, and the 6 NULL-hive logbook rows that exist platform-wide belong to **Miguel
Santos, who is in zero hives**. So both vectors are latent. Recorded with the exact condition that would
make them live — a multi-hive person who has written in more than one hive, or a NULL-hive row owned by
someone with two memberships — rather than claimed as a leak the fixture cannot demonstrate.

**Observation width for C-BK…C-BQ:** two of the six seeded hive-pairs, walked end to end in Filipino on a
phone. The four remaining J26 verticals were not visited.

### C-BR · Interpolation was a cloak: the static i18n gate could not see a sentence with a number in it

The two defects C-BM records — a runtime write overwriting a correctly translated `data-i` element to
append a count — were found by hand, live, at phone-390. The platform has a **static gate for exactly
that class**, `validate_rendered_i18n.py` ("English prose written by JS onto pages that claim to be
bilingual"), which held a forward-only ratchet at **653 literals · 73 overwriting a stamped element**
and reported PASS. It had never named either defect, and `hive.html`'s baseline of 29 did not include
them.

**The reason is four characters, and the code that meant to handle it was unreachable:**

```python
def is_prose(lit):
    if len(t) < MIN_LETTERS or NOT_PROSE.match(t) or LOOKS_TECHNICAL.search(t):
        return False                 # LOOKS_TECHNICAL contained \$\{ , unanchored
    ...
    if "${" in t:                    # <- DEAD CODE for every template literal
        t = re.sub(r"\$\{[^}]*\}", " ", t)   # "a template slot: the words around it still count"
```

`LOOKS_TECHNICAL` matched **any** literal containing `${`, so `is_prose` returned False on its first
line — two lines before the branch that deliberately strips the slot and counts the surrounding words
could ever run. Measured on the gate's own function:

| literal | verdict |
|---|---|
| `'Switch Hive (3)'` | **PROSE** — counted |
| `'Switch Hive (${list.length})'` | **ignored** — same words, invisible |
| `'You have ${n} open jobs waiting for you'` | **ignored** |

So the gate saw a sentence only while it had no slot in it — and **a count appended to a translated
label is exactly the shape that carries a slot.** Two instruments were blind to the same defect from
opposite sides: the runtime rubric graded the i18n *mechanism* and never the words (C-BO, fault 16),
and the static gate could not see the words whenever they carried a number.

`{{` is kept in the pattern — mustache really is a template language, not a sentence with a number in
it. Verified after the fix: `'${count} px'`, `'.${cls} { color: red; }'` and `'{{handlebars}} template'`
are all still correctly ignored, and the gate's own self-test still passes 5/5.

**What the better eyes revealed: 653 → 783 literals (+130) and 73 → 80 stamped-element overwrites
(+7), across 19 pages.** The count rose because the ruler improved, not because the platform got
worse ([[feedback_changing_the_measurement_is_not_drift]]), so the baseline is re-frozen at the true
floor per this repo's standing ordering — *fix first, then enforce; a ratchet, not a red gate nobody
reads.* The +130 ordinary literals are a broad backlog. **The +7 are the serious half and are named
here so a re-baseline cannot bury them** — each is English written over an element the applier had
already translated, so a Filipino reader meets English at the exact moment something happens:

| page | line | element | the string written over the translation |
|---|---|---|---|
| community.html | 2316 | toast | `Slow down, wait ${remaining}s before posting again` |
| community.html | 2770 | `#btn-submit-reply` | `Slow down, wait ${remaining}s between replies` |
| asset-hub.html | 2095 | `#btn-edit-asset` | `${done}/${items.length} on track` |
| skillmatrix.html | 1200 | `#sm-action-text` | `Take a ${primaryDisc} quiz first: your primary discipline is ${primaryGap} levels behind. The next level unlocks once you pass.` |
| report-sender.html | 2168 | `#proc-title` | `Generating ${reports.length} report${...}...` |
| report-sender.html | 2284 | `#email-status-text` | `Sent to ${escHtml(detail)}` |
| dayplanner.html | 1401 | `#dp-verdict-sub` | `${overdueCount} items overdue. Open the Week view. …` |

Each fix is the same one-line shape as C-BM (`_t('English …', 'Filipino …')`), and each owes the
**same** copy rules the English half passes — the 20-word bar included, because Filipino expands
([[feedback_a_translation_must_fit_the_same_bar]], which caught my own 25-word sentence in this same
program). They are queued as a wave rather than rushed at the tail of a walk, for that reason.

**FIXED and re-verified by the gate itself, the same turn.** All seven now go through `_t()` with the
platform's own vocabulary — `nasa tamang landas` is `WH_FIL_COMMON.ontrack`, so an on-track state reads
the same everywhere; `lampas na sa takda` is the wording pm-scheduler already uses for an overdue PM; and
Filipino has no plural *-s*, so each count carries its own number. The two multi-clause sentences (the
skillmatrix quiz nudge and dayplanner's overdue advice) are kept **split** in both halves, which is the
only reason the Filipino fits — it expands against the English
([[feedback_a_translation_must_fit_the_same_bar]], which caught my own 25-word sentence in this program).

The gate measured the result rather than taking my word for it: **stamped-element overwrites 80 → 73,
literals 783 → 774, and ZERO interpolated stamped-overwrites remain.** The baseline is re-frozen at
774/73 — so the ratchet now sits *tighter* than it did before the corrected ruler found the class at all.

Two things are deliberately left as the next slice, both named rather than absorbed: the **+130 ordinary
interpolated literals** (the broad backlog the fix made visible), and **dayplanner's day-advice cascade** —
five sibling branches of English advisory prose, of which only the one on a stamped element was in the
graded seven. Translating the other four is editorial work of the same shape, not a mechanical wrap.

### C-BS · The delete sat 6px from the button people press most — and my fix was 0.4 pixels short

**Walked 2026-09-11** — J31 *"the portable portfolio"*, desktop-1280, English, rows W3470/W3473. Cast:
**Jun Salvador** (`junvanowner`), a solo van owner with **no hive at all** — one of four hive-less
personas, and not a marketplace platform admin. resume.html read **98%**.

**The hazard.** Every `✕ Remove` on a resume entry is a correct **44×44** target — size was never the
problem. But `.item-actions { gap: 0.35rem }` placed it **5.6px** from the `▲`/`▼` reorder buttons,
sharing **44px of vertical overlap** — the same row, one thumb-width apart:

```
[ ▲ ]5.6px[ ▼ ]5.6px[ ✕ ]      ← reorder, reorder, delete
```

Re-ordering entries is the single most repeated gesture in a resume builder, so the control a person aims
at over and over sat immediately beside the one that deletes what they typed. Z3 encodes exactly this: a
destructive target is an accidental-touch hazard when another tappable target sits **horizontally** beside
it with under 24px between them — WCAG 2.5.8's spacing rule applied where a mis-tap costs most. Its own
comment draws the right distinction: *"a thumb mis-taps side-by-side, NOT vertically-stacked feed items."*

**The page already knew, and had fixed the consequence rather than the cause.** The remove handler
carries: *"Removing a row is destructive and a novice fat-fingers the ✕ — push undo FIRST… this one
silently didn't, so a deleted job/skill was unrecoverable. (Novice MCP sweep 2026-06-06.)"* Undo is the
right safety net and it stays; this removes the mis-tap that makes it necessary.

**★AND THE FIRST FIX LOOKED RIGHT AND WAS 0.4px SHORT — caught only because the dim refused to agree.**
`margin-left: 18px` was chosen from a measurement that reported the gap as "6px". It is **5.6px**
(`0.35rem`), so the new gap was **23.6px** and Z3 kept failing all 14 controls. I then spent a full
investigation trying to reconcile the dim with my own replication of its rule, which reported *no*
adjacent target — because **my probe rounded the gap to 24 before comparing it against the 24 threshold**,
while the dim compared the raw float. `23.6 → round → 24`, and `24 < 24` is false. The instrument was
right the whole time and my measurement crossed the threshold in the rounding.

> **Round for display, never before a threshold test.** A rounded number is a presentation of a
> measurement, not the measurement — and a comparison is exactly where the difference decides the verdict.

**Fixed** with `.item-actions .icon-del { margin-left: 20px }` — 20 + 5.6 = **25.59px**, measured raw and
comfortably clear. A margin on the destructive control rather than a wider container gap, because the
`▲`/`▼` pair belongs together and should stay tight; only the delete is pushed clear. Verified:
**Z3 0 offenders, 100% — "all 117 targets clear the 24px + spacing floor"**, and Z3 is off the page's
failing list.

**And the instrument gained the receipt that would have settled it in one call.** Z3 was the only dim in
this family exporting nothing — A1 publishes `a1_ctas`, B3 `b3_offenders`, C2/C5/E4 the same — so there
was no way to ask *which rule fired on which element*. It now exports **`z3_offenders`**: per offender the
element, its box, whether it was judged destructive, and **which branch fired**
(`destructive+horizAdj` vs `small+circleCrowded`). That single field turned an unresolvable disagreement
into a one-line answer, and it is the standing lesson of four instrument faults in this same turn —
**read the instrument's own exported list; never re-derive its selection beside it**
([[feedback_an_oracles_vocabulary_is_part_of_the_oracle]]).

### C-BT · The empty state was the untranslated one — found by the only person who sees nothing else

**Walked 2026-09-11** — J31 *the portable portfolio*, phone-390, **Filipino**, rows W3471/W3474. Cast:
**Boyet Ramirez** (`boyetjeepneyrider`), a solo jeepney rider with **no hive at all**. Deliberately the
*other* vertical from the English desktop walk (C-BS, Jun Salvador), so the two rows are not both
evidence about one person.

**The structural finding, and it is the reason this cell exists.** A person with no hive has logged
nothing, so every surface renders its **empty** branch — and the empty branch was the English one on
almost every page. That is not incidental: a page's happy path gets translated because it is what
everyone looks at while building it, and the state a brand-new user actually meets does not. The clearest
single proof is on marketplace, where the **failed-read** sibling was *already* bilingual
(`'walang bilang ng listing'`) while the **success** path beside it was not — the ordinary case was the
untranslated one.

**Fixed, each verified live:**

| surface | what a Filipino reader met | after |
|---|---|---|
| achievements | six strings — *"No achievements yet"*, *"No XP earned in the past 7 days"*, *"No domains active yet"*, *"No levels gained yet"*, the first-run nudge, the recommendation | N1 **80 → 100%**, page **100%** |
| marketplace | guest + empty branches, browse copy, filter counts, the total-listings label | N1 **80 → 100%**, page **100%** |
| marketplace-seller-profile | the not-found state — the journey's last hop, and the only thing a solo owner with no listings ever sees | Filipino |

The long strings are **split in both halves** — the achievements recommendation was already 22 words as a
single English sentence, and Filipino expands ([[feedback_a_translation_must_fit_the_same_bar]]).
The seller-profile state was already *right* — it names who it looked for rather than implying the person
does not exist, which is `boundary_not_emptiness` done well — so only the language needed fixing. It
carries no `data-i`, which is exactly why the stamp census could not see it: **an unstamped string is
invisible to a check that reads stamps.**

**And the resume fix from C-BS holds at phone width**: the destructive `✕` measures 25.59px clear of the
reorder buttons here too, Z3 0 offenders.

**Three instrument corrections, each caught by the page in front of me:**

- **Fault 20 — a correct translation cost a page half a trust dim.** E3 read **50% in Filipino and 100%
  in English** for one chip saying the same thing twice: *"… **as of** this page load"* vs *"… **noong**
  pag-load ng page na ito"*. `noong` **is** the platform's own translation of "as of", in
  `i18n/pages/resume.fil.json` under the same `data-i` key. Widened with tokens **derived** — pairing
  every `*.fil.json` entry against the EN string on its own `data-i` element and keeping the FIL halves
  whose English half the regex already matched: `noong`, `buhay` (alive), `nabuo` (generated, the
  *completed* form — only present-tense `binubuo` was known). `magagawa` deliberately left out: its
  English half is "reports **can be** generated", a capability claim, and a token that excuses a chip
  saying nothing about *when* is worse than a missing one. **E3 50 → 100%.**
- **Fault 21 — my own fault-16 check named the wrong culprit.** It called six achievements strings
  *"overwritten with ENGLISH after the swap"* and quoted a **loading placeholder** as the expected text
  (*"Naglo-load…"*, *"Kinukuwenta ang XP progress…"*). Those elements were **filled** by the application —
  the contract `utils.js:1699` exists to protect. The English rendering is still a defect and still
  reported, as what it actually is. *Grade the outcome, but describe the mechanism truthfully, or the
  worklist sends someone to the wrong file.*
- **The absence of Filipino is not evidence of English.** The check flagged `"20 listing"` — which **is**
  correct Filipino, because the platform carries `listing` as a loanword and Filipino takes no plural
  *-s*, so the string holds no Filipino function word to find. A flag now needs a **positive English
  signal** too. **Stated limitation, accepted on purpose:** a bare count plus a loanword (`"20 listings"`)
  no longer flags either, since neither half carries a function word. Zero false positives at the cost of
  that gap — a false positive tells someone to "fix" correct copy and costs their trust in the dim; a
  false negative leaves one small string for another lens.

**Readings:** resume 100 · index 100 · skillmatrix 99 (B3) · achievements 100 · marketplace 100 ·
marketplace-seller-profile 88. Settle rule v3 held on every surface.

**Lead, not acted on:** seller-profile's 88% is six dims (E3 *"NO source chip"*, G1 *"no status region"*,
I2, O2, A1, A2) grading a **not-found** state as though it were a data page — the same family as fault
12's static-doc N/A branches. Two walks of that page now agree on the number, and that is still not
enough to recalibrate six dims from one page shape.

### C-BU · The recovery link WAS the sibling, and the check only looked inside it — plus 123 strings no i18n gate can see

Chasing the lead C-BT left open — *"seller-profile's 88% is six dims grading a not-found state as though
it were a data page"* — the first dim examined turned out not to be miscalibrated at all. **X1 was simply
wrong**, and the other five split into two honest halves.

**FAULT 23 — the sibling was the link, not a box holding one.** X1 already allows an empty state's next
step to live in the panel's **sibling** (the rule added 2026-09-10 after hive's approval card). But it
looked for the control with `s.querySelectorAll('a[href],button,[role=button]')` — which searches
**descendants**. The not-found state renders

```html
<a href="marketplace.html" class="back-link"><span class="ic ic-back"></span> Back to Marketplace</a>
<div class="empty-state">…</div>
```

so the sibling **is** the anchor, and its only descendant is a decorative `<span>`. The check found no
control and reported *"1 dead-end state — a user landing there has NO next step"* about a page offering
exactly the right one. **Three walks across two devices and two languages carried that false finding.**
The sibling is now a candidate control itself, not only a container of them. Teeth-tested six ways
against the shipped source: fires on the real markup (was `false`, now `true`), still fires on the box-
containing-a-link shape it already handled, and stays silent on a prose-only sibling, a control that
points nowhere (`Close`), the same link inside a `nav`, and the same link hidden.

*Exactly the shape of fault 22 the same hour:* a rule that enumerated **containers** and missed the case
where the thing itself is the surface. **When a rule lists the shapes a thing can arrive in, the thing
itself is one of the shapes.**

**TWO REAL PAGE DEFECTS the walks could not see, because both live in states a walk rarely reaches.**

- **The not-found render destroys the page's `<h1>`.** `pageEl.innerHTML = …` replaces the whole `<main
  class="page">`, and the page's semantic title is the hero's `<h1 id="hero-name">` — whose own comment
  at line 277 reads *"the page's semantic title must be an h1."* Both terminal states then titled
  themselves with an `<h3>`, leaving the document with **no level-1 heading at all**. This is what A1's
  `h1=0` was correctly reporting. Both states now use `<h1>`, with `.empty-state h1` given the existing
  `h3` styling so nothing changes visually.
- **The auth-gate state was never translated.** *"No seller specified"* / *"This page needs a seller name
  in the URL"* had no `_t()` at all — pure English on a Filipino page. The J31 walks never saw it because
  they always arrived with a `?worker=` parameter; it is the state reached by a **stale or hand-typed
  link**, which is exactly who lands on an error page.

**AND THE MEASUREMENT THAT FOUND THE REST — 66 English strings no i18n gate could see, on 15 pages, now all fixed.**
Translating the auth-gate state should have moved the rendered-i18n ratchet by two. It did not move at
all. `ASSIGN` in `validate_rendered_i18n.py` matches `.innerHTML = <quote>literal</quote>` with the
literal capped at **300 characters** — so a multi-line `innerHTML` template blows the cap and **every
bare English text node inside it is invisible**. Templates are how most of this platform renders its
states. The gate read **green over 66 untranslated strings**, which is why C-BT's finding had to be
discovered by a human walking a page rather than by the instrument that exists to catch it. *A ratchet's
blind spot is not neutral: it is a green light over the exact class it was built to police.*

Widened with a **separate detector** rather than a bigger cap — a wider cap would capture raw markup as
the "literal". It reads a template the way a browser does: mask every `${…}`, strip comments and tags,
grade what a person would read. A `${escHtml(_t('EN','FIL'))}` is masked with everything else, so a
correctly translated template contributes nothing and needs no bookkeeping. Baseline re-frozen
**763 → 817**, and `817 − 66 = 763` exactly: the widening is purely additive and changed nothing about
the old measurement.

**★AND MY OWN NEW DETECTOR WAS WRONG ABOUT 44% OF WHAT IT FIRST REPORTED — 51 of 117.** Two separate
bugs, and **neither was findable by the synthetic teeth test**; both surfaced only from reading the
output against real pages:

- **33 false positives: the scanner ran past the end of the template.** It counted `${` but decremented
  on **every** `}`, so marketplace's `${(() => { … })()}` — an IIFE inside an interpolation — closed the
  interpolation on the *arrow function's* brace, and 18 lines of `const _sp = …` plus a `/* */` comment
  were reported as text a person sees. **A gate that reports source code as untranslated copy is worse
  than the blind spot it replaced.** Rewritten to track what it is actually inside: at template level
  only `${` and the closing backtick matter; inside an expression every brace counts, quoted strings and
  comments are skipped whole, and a nested template recurses.
- **18 false positives: the text node's own tag already carried `data-i`.** marketplace renders
  `<button … data-i="clearfilters">Clear filters</button>` *inside* a template — the English there is the
  fallback `whI18nApply` swaps, the platform's normal static contract, not a gap. Blanking every tag
  uniformly threw that away. The stamp is the sibling of ASSIGN's `_t()` exemption: one mechanism per
  shape, the stamp for markup and `_t()` for runtime strings. *(Whether a stamp actually took effect is a
  live question a static gate cannot answer and N1 already owns — here the declaration is the contract,
  and a string with neither a stamp nor a `_t()` has no contract at all.)*

Teeth-tested **twelve** ways against the shipped gate, both directions: it sees bare template text and
text that follows an IIFE; it stays silent on `_t()`-wrapped text, pure markup, all-interpolation,
HTML comments, CSS built as a template, one-word labels, IIFEs, nested templates, and stamped nodes —
while still seeing an **unstamped sibling beside a stamped one**.

**ALL 66 ARE FIXED, and the arithmetic is the receipt.** 763 before the widening → **829** once the class
became visible → **763** again once every one was translated, with `template-text` findings at **0**. The
baseline is re-frozen at the number it started from, but the detector behind it now reaches a class it
could never see — strictly more reach at the same figure, which is a tightening, not a reset. Every one
was an empty or error state, the same class C-BT found by walking as a person with no data:

| page | strings | what a person was reading in English |
|---|---|---|
| project-manager | 28 | the entire first-run screen (*"No projects yet: start with a template"*), the four project-type tiles, every pane legend, the EVM variance block, lessons learned |
| logbook | 12 | the empty state of every asset drawer — parts linked, parts consumed, fault history — and the team search that names the window it searched |
| marketplace | 8 | *"No saved searches"*, *"No saved listings"*, *"No listings match those filters"* |
| marketplace-seller-profile | 9 | both terminal states, three back-links, the community-standing card |
| community | 7 | the entire first-run welcome board a new hive member reads |
| marketplace-seller | 6 | *"Post your first listing to start selling on WorkHive."* |
| integrations · inventory · index · dayplanner · analytics · marketplace-admin · plant-connections · resume | 16 | vehicle-import receipt, API-key warning, SAP conflict count, stock captions, account-linked confirmation, *"No open items"*, the analysis claim, *"No disputes"*, the supervisor-only denial, the cover-letter draft |

**A pattern worth naming, seen on marketplace-seller:** the `<h2>` of each empty and error state *was*
wrapped in `_t()` — someone did the work — while the `<p>` explaining what happened sat bare in English
directly beneath it. A person reading Filipino got a translated headline over an English sentence.
**Heading and body are one message; whoever translates one owes the other.**

The three seller-profile back-links were the first strings this measurement caught, and they were
**mine** — found minutes after I translated the two headings beside them and missed the link. Fixed
using the platform's own shipped Filipino for that exact string (`marketplace-admin`'s `ma_gate_back`,
*"Bumalik sa Marketplace"*), the static one stamped on a **text span** rather than the anchor, because
`whI18nApply` writes an element's text and stamping the `<a>` would swap away the icon beside it.

**The four project-type names were rendered in three places** — the wizard's static tiles, the
new-project `<select>`, and the JS template — and only the template copy was in the finding. Translating
just that one would have shown a person the same concept under two different labels depending on which
screen they were on, so all three now read from one dictionary. Industry terms the Filipino trade uses in
English (Work Order, Shutdown / Turnaround, CAPEX, FEL, EVM, BOM, SOW) stay English in *both* halves, the
way the platform already carries `listing` and `Review` as loanwords — declaring in the source that the
term is deliberately the same, rather than leaving a reader to wonder whether it was missed.

**What remains genuinely a calibration question — E3, G1, I2, O2.** Asking a *"Seller not found"* page for
a data-source chip, a live status region, an optimistic-write block and a help affordance is asking a 404
for things only a data page has. That case is now **stronger, not weaker**, because two of the six dims
turned out to be reporting truth — but it is still not settled, and the honest order is to **re-measure
after these fixes and see what actually moves** before exempting anything. An exemption written on
speculation is how a dim goes vacuous.

### C-BV · The lead said six dims were miscalibrated for a not-found page. Four of them were reporting truth

C-BT left a lead: *"seller-profile's 88% is six dims grading a NOT-FOUND state as a data page — three
walks across two devices and two languages agree on the number."* Agreement across three walks felt like
strong evidence. It was evidence that the **number** was stable, not that the **diagnosis** was right —
all three were taken through the same broken ruler.

Re-measured live at desktop-1280 on the real not-found state (`?worker=no-such-seller-xyz`):

| dim | was | now | what it actually was |
|---|---|---|---|
| **X1** | 50% | **100%** | **An instrument bug.** Fault 23: the recovery check searched the sibling's DESCENDANTS, and the back-link *is* the sibling. |
| **A1** | 50% | **75%** | **A real defect.** The not-found render replaced all of `<main class="page">`, destroying the hero's `<h1>`, so the document had no level-1 heading — which the page's own line-277 comment forbids. |
| **E3** | 0% | **100%** | **A real defect.** The same replacement destroyed `#msp-source-chip`. |
| **G1** | 0% | **100%** | **The same real defect** — one `<p class="wh-source-chip" role="status" aria-live="polite">` carries both dims, so destroying it cost them together. |
| **M1** | 96% | n/a | correctly withdraws itself: *"no form fields in this state"* |
| A2 · I2 · O2 · C3 | | unchanged | the genuine remainder |

**Four of the six were right.** An exemption written on the lead would have silenced two real
accessibility defects, one real provenance defect, and one bug in the instrument itself.

**★HOW THE LAST TWO WERE FOUND — by measuring a SECOND terminal state, which refuted the exemption I had
already drafted.** The same page has another: no `?worker=` at all → *"No seller specified"*. Measured,
the two terminal states **disagreed**: E3 0% / G1 0% on not-found, **E3 100% / G1 100%** on
no-parameter. Same page, same shape, opposite readings — so *"a 404 has no data, therefore no
provenance"* was false on its face, and the difference had to be mechanical.

It was a **race**. `#msp-source-chip` is appended by a `window.addEventListener('load', …)` handler. The
auth-gate branch runs synchronously in the inline script — *before* load — so the chip is appended
afterwards and survives. The not-found branch runs inside `loadSeller()`, which **awaits a DB read**, so
it resolves *after* load and its `pageEl.innerHTML = …` wipes the chip that was already there. Two
terminal states on one page scored 0% and 100% on the same dims purely because of which one ran last.

Fixed order-independently rather than by re-ordering: the chip is carried across the replacement if it
exists, and if it does not yet exist the load handler still appends it later — both orders now end with
it present. The provenance claim stays honest on a 404: it says where the page **looked**, which is
exactly what a not-found state owes its reader.

**★AND THE OBVIOUS SECOND FIX WAS THE WRONG ONE.** A1 still reads `cta=0` on a page whose back-link is
plainly the only thing to do, and after fault 23 the tempting move was to widen A1's CTA selector the
same way. **Checked before acting, and it would have been the over-broad error:** A1 counts `.ac-cta`,
`[class*="primary"]`, filled buttons, header primaries and FABs. A `<a class="back-link">` is an
unfilled text link, and counting unfilled anchors would make **every link on every page** a call to
action. A1's detection is correct; what does not apply is running the 5-second test against a state
whose job is to explain and offer a way back. *Two faults of the same visible shape do not have the same
fix — one was a rule that missed an arrangement, the other is a rule that does not belong on this page
class.*

**What the remaining four justify — and why it is still not built.** A2, I2, O2 and C3 ask a terminal
error state for sub-headings, an optimistic-write block, a help affordance and region grouping. The
right shape is **M1's**: it reports *"no form fields in this state"* and takes itself out of the
average — *withdraw the dim, do not score it zero*. But this round is the argument against generalising
from one page: a predicate fitted to the not-found state would have "explained" E3 and G1 too, and been
wrong about both. It needs a second, genuinely different terminal state to derive from —
`marketplace-admin`'s platform-admin gate, `plant-connections`' supervisor-only denial — measured, not
assumed.

**The rule this adds:** *when several dims agree that a page is wrong, do not ask whether the page shape
is exempt — ask, one dim at a time, which of them is telling the truth.* Here it was four of six, and
the cheapest way to find out was to measure a second instance of the same shape and look for
**disagreement**. Two states that should read alike and do not are pointing at a mechanism, not a
calibration.

### C-BW · A security_invoker view omitted one column; the base-table grant handed it back to everyone

Walking J32 (the founder's month-end, W389) as a leftover authenticated session — Boyet Ramirez, a solo
jeepney rider with **no hive and not a platform admin** — `platform-actions` rendered 12 named sellers
under "Sellers awaiting verification." The page's own notice said the queues read empty for a non-admin,
so the rows themselves were the first surprise. Proving what was actually readable, the required way
(PostgREST-as-persona, Boyet's own token, never the owner connection):

```
anon (publishable key, no user token)  -> 42501 permission denied for table marketplace_sellers
Boyet's own JWT  -> marketplace_sellers?select=worker_name,auth_uid  -> 16 rows, EVERY auth_uid
```

**`auth_uid` is the internal Supabase identity RLS itself compares against** (`auth_uid = auth.uid()` in
the seller update/delete/insert policies). Handing every logged-in user the stable auth id of every
seller correlates each marketplace name to its auth identity across the whole platform. Not an
impersonation vector — `auth.uid()` comes from the signed JWT, which this does not forge — but a
cross-tenant identity disclosure, and exactly the column the platform had already decided to hide.

**The mechanism is the lesson.** The public view `v_marketplace_sellers_truth` was deliberately built to
**omit `auth_uid`** (selecting it from the view returns `42703 column does not exist`) — the design
saying auth_uid is not public. But the view is **`security_invoker=on`**, so it reads the base table *as
the caller*, and the base table carries a table-level `GRANT SELECT … TO authenticated`. A direct
base-table read therefore re-exposes the one column the view was careful to drop. Two guards, and the
gap fell exactly between them: the view scoped the columns, the grant scoped the table, and neither
scoped the intersection. `hive_id` and `messenger_username` ARE in the view, so they are intended-public
and not part of this finding; `auth_uid` is the whole of it.

**Why the obvious RLS fix would have been wrong.** The tempting move is to tighten `mkt_sellers_read`
from `auth.uid() IS NOT NULL` to `(auth_uid = auth.uid()) OR is_marketplace_admin()`, matching the write
policies. But the view is security_invoker, so that row policy also governs the view — and the
marketplace legitimately needs any authenticated user to *browse* all sellers' public columns through
it. Tightening the row policy would have shut off seller browsing platform-wide. The row policy was
never the problem; the over-broad **column** grant was.

**FIX (migration `20260911000001`, applied locally + verified, prod deploy is Ian's gate).** Column-level,
and it must revoke the table grant FIRST — a bare `REVOKE SELECT (auth_uid)` is inert while a table-wide
`GRANT SELECT` stands (the table grant wins). So: `REVOKE SELECT ON marketplace_sellers FROM
authenticated`, then `GRANT SELECT (…every column except auth_uid…) TO authenticated`. The
security_invoker view names only granted columns, so it keeps working; self-scoped writes and WHERE
filters never needed SELECT on auth_uid. RLS untouched.

Verified both directions with Boyet's token:

```
select=auth_uid          -> 42501 / HTTP 403   (leak closed)
select=public columns    -> 200, real rows      (base-table public read intact)
v_marketplace_sellers_truth -> 206, 16 rows      (marketplace browsing intact)
```

`validate_public_read_surface` still PASSES (marketplace_sellers stays caller-aware), so the tightening
regresses nothing and needs no baseline bump.

**The rule:** when a `security_invoker` view exists to publish a *subset* of a table's columns, the
base-table column grant must match the view's column list — or the view's omissions are cosmetic and a
direct base-table read walks straight around them. A column left out of a definer-scoped view is a
decision; the same column left in the base-table grant silently reverses it.

### C-BX · engineering-design's narrow-320 header overlap — diagnosed, but the one-line fix only relocates it (LEAD for a focused improve-cycle)

Found on the J8 solo-owner narrow-320 walk (W3643): V1 0% on engineering-design, "1 content overlap — P 'Calculated on demand…' × BUTTON 'Calculator'". Diagnosed fully:

- The sticky header (`engineering-design.html:618`) is `flex items-center justify-between flex-wrap gap-y-2`.
- LEFT group (`flex items-center gap-3 min-w-0 flex-1`): Back link (hidden on mobile), title, subtitle, and `#eng-source-chip` — a provenance chip carrying an inline **`min-height:161px`** (a deliberate CLS reservation: "≈161px @390, reserve it so the header doesn't grow and push #tab-calculator down").
- RIGHT group (`flex items-center gap-2`): the three page-tabs (Calculator / History / Guide).

At ≤320px there is no horizontal room for both groups on one row, and `flex-wrap` does NOT wrap the tabs because the left group's `flex-1` lets it shrink instead. So both stay on one row, and `items-center` vertically **centers the tabs against the 161px-tall chip column** — landing "Calculator" (y≈221) inside the chip's y166–410 span.

**Two one-line fixes were tried live and BOTH only MOVED the overlap — so neither was shipped (verify spoke):**
- `items-start sm:items-center` → tabs drop to the top (y≈76, clear of the chip) but now overlap the **H1 title** (both top-aligned, no horizontal room). Lateral move, not a fix.
- tabs group `width:100%` (force-wrap) → tabs wrap to a second flex line at y≈221, but the 161px+ chip column still extends into that row, so the tab **still overlaps the chip**.

**The real fix is a header restructure, not an attribute flip:** the `min-height:161px` provenance chip must stop competing with the tabs in the same flex row at narrow width — e.g. give the chip its own full-width row below the title/tabs at `<sm` (so the tabs sit on the title's row and the chip flows beneath both), or drop the chip's reserved height at narrow width where its content reflows anyway. Either touches shared header layout + the CLS reservation, so it needs the whole-header treatment with full-page screenshots at 320 / 390 / 768 / 1280 to confirm no CLS or desktop regression. Banked as W3643's V1 finding; left as-found (not worsened) for that focused pass.
