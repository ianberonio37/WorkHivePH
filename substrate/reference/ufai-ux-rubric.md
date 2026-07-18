---
name: reference-ufai-ux-rubric
type: reference
source: NN/g + Laws of UX + WebAIM + W3C-WAI/WCAG + GOV.UK + web.dev (51 distilled chunks in substrate/external/external-ux-*)
source_sha: review-date-anchored
last_verified: 2026-07-14
supersedes: null
---

## reference · UFAI UI/UX rubric (18 classes A–S · ~49 dimensions) — the page-redesign ruler

Synthesis of the Night-Crawler UX harvest (`substrate/external/external-ux-*` — retrieve the named
chunk for the full cited rules). Grade any page's BEFORE against these; design the AFTER toward them.
Every rule is measurable + cited.

**A · Comprehension**
- A1 5-second test — a stranger names the page's purpose + primary action in ≤5s; one dominant focal point; inverted pyramid (answer first). [ux-scanning, ux-f-pattern]
- A2 Scannability — headings + bullets + **bold keywords** + one-idea blocks defeat the F-pattern; most-important content top-left. [ux-f-pattern, ux-scanning]
- A3 Cognitive load / progressive disclosure — show only a **few** options first, defer the rest; chunk to 5±2 (Miller); fewer choices = faster decisions (Hick); highlight the recommended one. [ux-hicks-law, ux-millers-law, ux-progressive-disclosure, ux-minimize-cognitive-load]

**B · Language**
- B1 Microcopy / concision — cut ~50% of words; no marketese; objective (concise +58% · scannable +47% · objective +27% → **+124% usability**); front-load keywords; headings work out of context. [ux-concise-scannable, ux-microcopy-headlines]
- B2 Plain voice & tone — specific, factual, direct; kill "cute" cleverness. [ux-microcopy-headlines, ux-govuk]
- **B3 Readability — MEASURED, not vibes (added 2026-07-15, Ian: "I can see sentence or some words, that we can just make it concise and direct and simple… not that you are overwhelmed by jargon words").** B1/B2 had NO numbers, so a page full of long hedged sentences scored 100% as long as it dodged marketese. The measurable floor, per the cited sources:
  - **Sentence length ≤ 20 words** — GOV.UK's hard rule for a good reading age. [external-plain-english-sentence-length-reading-age-measur]
  - **Flesch-Kincaid grade ≤ 8** — NN/g: 8th grade for a BROAD consumer audience (12th only for a specialised B2B one). WorkHive is "Free Industrial Tools for **Every** Filipino Worker" and the full-spectrum rule (worker→engineer) puts us at the broad end, so 8 is the target, not 12. [external-ux-legibility-readability-comprehension-measurab]
  - **Active voice** — NN/g: passive "except in rare circumstances". "The PM was missed" hides who acts; "You missed 3 PMs" does not.
  - **One idea per sentence / conclusion first** — NN/g inverted pyramid; be brief, especially on mobile.
  - **Exception (documented, not a loophole):** the standards vocabulary (MTBF, OEE, MTTR, ISO 14224, SMRP) raises grade level by construction and is the platform's canonical language — it is EXEMPT from the grade target, never from the sentence-length or active-voice rules. Jargon *terms* are separately gated by `validate_plain_language.py` + `validate_user_facing_jargon.py` (both green, 87 pages) — B3 is the layer those blocklists cannot see: **the sentences themselves.**

**C · Visual craft**
- C1 Visual hierarchy — ≤3 sizes (biggest = most important, ≤2 big); ≤3 contrast levels; ≤2 primary + 2 secondary colors; red/warm = warnings only. [ux-visual-hierarchy]
- C2 Color & **contrast (WCAG)** — text **4.5:1**, large text/UI components/graphics **3:1**; **never rely on color alone**; test the lowest-contrast area; hover/focus states re-checked. [ux-wcag-contrast, ux-wcag-principles, ux-von-restorff]
- C3 Whitespace / gestalt — group by proximity + whitespace + common region; let elements breathe; avoid clutter that implies false relationships. [ux-gestalt-proximity]
- C4 Typography — legible sizes; tabular numerals for KPIs; clear type scale. [ux-data-tables]

**D · Interaction**
- D1 Affordances & signifiers — every non-universal icon gets a visible text label (only home/print/search are universal); clickables must look clickable; big/near targets (Fitts). [ux-icon-usability]
- D2 Feedback & motion — feedback <**400ms** (Doherty); 0.1s/1s/10s response limits; skeleton screens for loads <10s; animation with purpose, not decoration. [ux-doherty-threshold, ux-response-time-limits, ux-skeleton-screens, ux-animation-timing]
- D3 Consistency / conventions — match platform + web conventions (Jakob); one component vocabulary. [ux-laws-principles]

**E · Data & state (dashboard)**
- E1 Data-viz / KPI — an OPERATIONAL dashboard is at-a-glance for action; use **length + 2D position** for quantities (bars), **never gauges/pie (area/angle)**; color for categories only; make the ONE key metric distinct (Von Restorff). [ux-dashboard-preattentive, ux-von-restorff, ux-data-tables]
- E2 Empty / first-run / loading / error — skeletons for loading; honest empty states; distinguish indicators (passive) vs validations (action-required) vs notifications. [ux-skeleton-screens, ux-indicators-validations-notifications]
- E3 Trust / transparency — show freshness ("updated 2m ago") + provenance tastefully via a tooltip/affordance, not a wall of meta prose. [ux-tooltip, ux-indicators-validations-notifications]
- **E4 Digest, don't dump — the card owes an ANSWER, not its WORKING (added 2026-07-15, Ian, with screenshots: "this is not a ux friendly to see. even me, I can't understand it right away, and overwhelming").** E1 governs the CHART and P governs the TABLE; nothing governed the *analysis card* that shows raw evidence instead of a conclusion. Every failing card on analytics shared one shape — it printed its working. The measurable rules:
  - **Collapse repetition.** If N rows carry the IDENTICAL verdict string, say it ONCE above them. Skill-MTTR printed "Not significant — skill level does not significantly predict repair time in this dataset." **5 times**; the honest card is one line: "Skill level doesn't predict repair time here."
  - **Cap raw lists at Miller (5±2), rank the rest behind disclosure.** Repeat-Failure-Clustering dumped **26 machine codes as prose** per card × 12 cards ≈ 240 IDs on one screen. A reader cannot hold 26 IDs; they can act on "Wear · 26 machines · worst: TT-002" + "Show all". [ux-millers-law, ux-progressive-disclosure]
  - **Translate the statistic before you show it.** "r = 0.866" next to "Not significant" READS AS A CONTRADICTION to everyone who is not a statistician — the coefficient looks strong. Lead with the verdict in user language; the coefficient is evidence, and belongs after it (or behind a disclosure). [ux-dashboard-preattentive, external-dashboard-design-aggregate-summarise-answer-not-]
  - **The decoder ring goes FIRST or not at all.** Skill-MTTR explained what "r" means in a footnote *below* five rows of r values — after the reader is already lost. Inverted pyramid applies INSIDE a card, not only page-wide. [ux-concise-scannable]
  - **A recommendation must recommend a CHANGE.** PM-Interval-Optimization badged "INCREASE FREQUENCY" and then recommended "every 7 days" on assets whose current interval was **already Weekly = 7 days** — a no-op dressed as an action. If the computed action equals the status quo, the card must say so, not fabricate an instruction.

**F · Reach & feel**
- F1 Mobile / touch — ≥44-48px tap targets; thumb-zone primary action; stack on small screens; safe areas. [ux-laws-principles]
- F2 Accessibility (WCAG 2.2 · POUR) — perceivable/operable/understandable/robust; keyboard + visible focus; contrast (see C2). [ux-wcag-principles, ux-wcag-contrast]
- F3 Emotional design / delight — design the peak + the end moment (Peak-End); a moment of warmth; aesthetic-usability makes a clean look feel more usable — but never mask real friction. [ux-peak-end-rule, ux-emotional-design-fail, ux-aesthetic-usability-effect]

**G · Usability heuristics (Nielsen's 10 — the canonical umbrella)**
- G1 Visibility of system status — timely feedback; a lack of info = a lack of control; communicate state changes (low stock, synced) briefly. [ux-visibility-of-system-status, ux-nielsen-ten]
- G2 Match the real world · Recognition over recall · Consistency · Flexibility · Help — familiar terms; make options visible not memorized; conventions; shortcuts for experts; accessible help. [ux-match-system-real-world, ux-recognition-over-recall, ux-nielsen-ten]
- G3 Aesthetic-minimalist — first impression forms in ~50ms; maximize signal, minimize noise; clarity > flourish; only high-info elements. [ux-aesthetic-minimalist]

**H · Behavioral & motivation**
- H1 Goal-gradient — progress accelerates near a goal; SHOW progress + the next rung to motivate ("33 pts → Stair 2"). [ux-goal-gradient]
- H2 Zeigarnik / endowed progress — unfinished tasks are remembered + nag; open loops + a partial-progress head-start drive completion (setup 80% → badge). [ux-zeigarnik]
- H3 Serial position — first + last items best recalled; put the most important first (primacy), a key item last (recency), filler in the middle. [ux-serial-position]
- H4 Selective attention — users banner-blind to ad-like elements; don't style real content like promos. [ux-selective-attention]

**I · Performance & perceived speed**
- I1 Core Web Vitals — LCP ≤2.5s, INP ≤200ms, CLS ≤0.1 (75th pct); reserve layout space to avoid shift. [ux-core-web-vitals-lcp-inp-cls, ux-core-web-vitals-thresholds]
- I2 Perceived performance — optimistic UI + skeletons make waits feel shorter (pairs D2). [ux-skeleton-screens]

**J · Error prevention & recovery**
- J1 Prevent slips — distinct labels (never near-identical options), separate test/live modes, confirm destructive actions, tolerant input (Postel). [ux-error-prevention, ux-postels-law, ux-nielsen-ten]
- J2 Forgiveness — clear undo / emergency exit (Nielsen #3). [ux-user-control-freedom]

**K · Field / industrial glanceability (WorkHive domain — synthesized from C1/C2/F1 + maintenance-expert)**
- K1 Safety-first signaling — safety-critical items (overdue PM, LOTO) read at a glance, distinct + labeled, never color-only. [applies ux-visual-hierarchy + ux-wcag-contrast]
- K2 Field legibility & reach — big glanceable numbers, high contrast for outdoor/industrial light, ≥44-48px targets for gloved/one-handed use (Fitts). [ux-fitts-law, ux-wcag-contrast]

**L · Ethical / wayfinding**
- L1 Honest design — no deceptive patterns: no manufactured urgency, nagging, obstruction, or emotional manipulation; urgency must reflect REAL state. [ux-deceptive-dark-patterns]
- L2 Information scent — link/label text must accurately predict its destination; clear, no jargon (pairs B1). [ux-information-scent]

**M · Forms & input**
- M1 Labels & structure — label ABOVE/left, NEVER placeholder-as-label (strains memory, a11y-poor); single column; group related; mark required/optional; match field size to input; explain format. [ux-web-form-design, ux-placeholder-text]
- M2 Validation & recovery — inline-validate AFTER a field is complete (not mid-type); errors next to the field with color+icon+success ticks; don't rely on a summary alone; never report errors via tooltip; extra help on repeated errors. [ux-form-error-messages]

**N · i18n / localization**
- N1 Text-expansion resilience — translated strings run ~25-35% longer (Tagalog/Cebuano); layout must not break; never concatenate strings; locale-format numbers/dates/₱; offer a language switch. (Source W3C qa-i18n was bot-blocked → applied from domain knowledge; demonstrated via the EN/FIL toggle.)

**O · Onboarding & first-run**
- O1 Value-first, not a tour — AVOID onboarding; make the UI usable instead. First-run tutorials get skipped + forgotten; get the user to ONE real action → immediate value ("log one job → the board fills in"). [ux-mobile-onboarding, ux-onboarding-tutorials]
- O2 Pull > push help — contextual "?" help on demand, not an intrusive push tour; always skippable; endowed-progress steps (1 of 3 done). [ux-onboarding-tutorials]

**P · Data density & tables** — scannable numbers (tabular figures, right-aligned), minimal grid, one key figure per cell. [ux-data-tables] (covered under E1)

**Q · Motion & cognitive accessibility**
- Q1 prefers-reduced-motion — ship a motion-reduced variant (respect the OS setting); WCAG: interaction-triggered animation ≤3s, pausable if >5s, no vestibular triggers. [ux-prefers-reduced-motion, ux-wcag-animation-motion]

**R · Layout rhythm & spatial harmony (the WHOLE-PAGE top-to-bottom experience — added 2026-07-15 from the Night-Crawler layout harvest; C1/C3 grade a component, R grades how the components sit TOGETHER down the scroll)**
- R1 Spacing scale / vertical rhythm — use ONE spacing system (**8-pt / 8dp grid**): every inter-block gap, card padding + margin is a **multiple of the base unit (8px)**; keylines (distances between elements) are multiples of 8; NO ad-hoc pixel values (a page whose stacked-block gaps measure 0/4/12/14/16/20 = six systems = the "not uniform / disorganized" feel). Consistent spacing creates hierarchy, alignment + harmony. [external-layout-spacing-8dp-grid-keylines, external-layout-regions-hierarchy-whitespace]
- R2 Alignment & grid — elements align to a shared column grid: consistent left edges + content widths; keylines multiples of 8; ragged left edges / varying card widths read as "misarranged". [external-layout-spacing-8dp-grid-keylines]
- R3 Container / treatment uniformity (**Gestalt similarity**) — ONE visual style per element TYPE: peer cards share radius, padding, border, background + elevation; consistent shape + size signals same grouping + prominence; don't render peer content as a MIX of bordered cards + bare rows + bare disclosures (broken similarity = "cluttered"). Reserve one link color for clickables, a separate color for the primary CTA. [external-gestalt-similarity-uniform-treatment]
  - **★R3 GOVERNS CONTROLS, NOT JUST CARDS (clarified 2026-07-15, Ian: "not uniform, seems cluttered and not harmonious design of container or arrange of them").** Measuring only card peers scored analytics R3=100% while its BUTTON vocabulary carried **four radii (0 / 8 / 10 / 999px) and three heights (44 / 50 / 72)** for one concept. Two hard reads of "similarity" apply to controls:
    - **One shape per control ROLE.** Count distinct `radius|height` signatures across all controls; a page needs ~3 roles (filter/toggle · action · tab), not 8 shapes.
    - **★Same shape MUST mean same job.** `period-btn` (a filter), `refresh-btn` (an ACTION), `role-btn` (a switch) and `filter-chip` (a filter) all render as the identical 999px/44px pill, separated only by tint — so a control that CHANGES DATA is indistinguishable from one that FILTERS it. Shape is the strongest similarity cue; colour alone cannot carry the distinction (and fails outright under CVD / greyscale print).
  - **Row balance:** a wrapped row must not strand a lone item on its own line ("Lubrication" alone under 6 siblings reads as ragged, not as a group).
- R4 Region grouping & whitespace consistency (**Gestalt common region**) — group related content into REGIONS via a shared container/background + consistent whitespace; whitespace defines relationships + separates regions; apply ONE consistent spacing method throughout; **no orphan voids / dead gaps** (an over-reserved CLS slot, or a hidden conditional card, that leaves empty space = the "gaps" the user sees). [external-gestalt-common-region-grouping-containers, external-layout-regions-hierarchy-whitespace, external-ux-gestalt-proximity-grouping-whitespace]
- R5 Vertical flow & section cohesion — the page reads top-to-bottom as coherent SECTIONS in a deliberate order (**inverted-pyramid for the WHOLE page**: primary answer → supporting → peripheral, not only inside the hero); continuity carries the eye downward; no jarring density jumps (a cramped block then an empty gap). Pairs A1 (5-sec) applied page-wide + H3 serial-position + I1 (reserve space WITHOUT leaving a void — a skeleton that matches content beats an over-tall fixed min-height). [external-layout-regions-hierarchy-whitespace, ux-f-pattern]

**Applied (Hive Board before→after, v1→v4):** lead with "3 things need you" (A1) · kill meta prose (B1) · WCAG-lifted contrast (C2) · readiness as length-bar + trend sparkline, no gauge (E1) · progressive-disclosure of secondary (A3) · mobile stack + sticky thumb action (F1). **v3 adds:** "since your last shift" return-ribbon (G1 status + H2 Zeigarnik) · goal-gradient stairs "33 pts → Stair 2" (H1) · endowed-progress "1 step → badge" (H2) · overdue PM as "Safety · do first" one-peak (K1 + E1/Von-Restorff) · per-tile snooze "⋯" (J2 user control) · shift context + "all synced" (G1) · honest real counts, no fake urgency (L1) · CLS-safe reserved layout (I1) · premium-but-minimal depth (G3). **v4 adds:** `prefers-reduced-motion` variant (Q1) · EN/FIL i18n toggle proving text-expansion holds (N1) · a first-run empty-state view: value-first "log one job → board fills in", no tour, endowed-progress steps, pull-"?"-help (O1/O2) · a proper form: labels-above + inline success ticks + hints-not-placeholders + required-marked (M1/M2).

See [[reference-rag-chunking]] [[project_night_crawler]]. Full cited rules: the 27 `substrate/external/external-ux-*.md` chunks.


### S · Family resemblance — the CROSS-PAGE class (added 2026-07-15, Ian: *"my pages would look like not different personalities... like they in the same and similar theme"*)

**Every class A–R grades ONE page in isolation. None could see the thing Ian actually noticed:** we drove Hive and the Home Dashboard to 100% with this rubric, and then *"when I saw your output in Analytics Engine page, it's now again different from the previous we have accomplished."* A page can score **R3 = 100% (perfectly self-consistent) and still be a total stranger to the platform** — flawlessly uniform at 10px while the design system says 8/12/16. That blind spot IS the "different personalities" problem. **S is the only class that requires looking at more than one page.**

NN/g Heuristic #4 names it **internal consistency**: *"within a product **or family of products**, by using the same patterns everywhere inside the system... reusing elements such as headings, call-to-action buttons, and navigation across pages"*, maintained via **a design system**. [external-consistency-and-standards-heuristic-internal-ext, external-ux-laws-principles-jakob-hick-fitts-miller]

- **S1 Token conformance — MEASURED against the DECLARED vocabulary, never the platform MODE.**
  - **The canonical is `tokens.css`, not a vote.** Most pages were never driven with this rubric, so a statistical mode across 47 pages would let un-driven pages **outvote the design system**. The lens reads `--wh-radius-*` / `--wh-font` from the LIVE cascade, so the ruler follows the tokens without a lens edit.
  - **Rendered radius ∈ {declared} ∪ {0, pill}.** `0` is a deliberate square edge; a **pill** (r ≥ height/2) is a SHAPE intent, not drift — normalise it or the lens reports every rounded chip as a violation.
  - **Rendered typeface == `--wh-font`.**
  - **★A page with NO token source scores N/A, not 0.** Conformance is then *structurally impossible*, not merely unmet — report the root cause instead of blaming the page for it.
- **S2 Shared chrome parity** — the same nav / footer / skip-link components render across pages. NN/g: reusing navigation across pages is what users feel as one product.
- **S3 Card-primitive parity** — peer pages use the SAME card primitive. Analytics invented `.card`/`.simple-card` while the exemplar Hive uses `.board-card`; two primitives = two personalities.

- **★S1's TWO LEGITIMATE EXCEPTIONS — a deliberate opt-out is not drift (measured 2026-07-15).** Both were found by PROBING before fixing; "fixing" either would have shipped a regression or a false 100:
  1. **A LOADED typeface is a DECISION; a FALLBACK typeface is a DEFECT.** `alert-hub`'s Arial was never loaded (the UA hands it to unstyled form controls) = a real bug. `project-report`'s **IBM Plex Sans** is `@font-face`-loaded on purpose for its printable `#ar-print-wrapper` (11pt on paper) = correct. **`document.fonts` IS the intent record** — `loaded.has(f)` is the discriminator; without it the lens drives a "fix" that destroys an intentional document typeface.
  2. **The OFFLINE page must not use a webfont.** `offline-fallback.html` renders when the network is DOWN, and `sw.js` serves font requests **network-first with a 503 fallback**, so Poppins is unavailable there *by definition*. Its `-apple-system` system stack is CORRECT. Setting `var(--wh-font)` would make S1 **PASS while rendering the identical fallback** — a textbook false-100. **A page that cannot load the webfont is exempt from the typeface check, never from radius/spacing.**
- **★WHAT IS IN THE FAMILY — the scope decisions (Ian, 2026-07-15).** S grades what USERS see; a metric answering the wrong question is worse than no metric.
  - **OUT (internal tooling):** `architecture`, `validator-catalog`, `llm-observability`, `symbol-gallery` — dev/ops surfaces that ship no webfont. Added to `validate_design_tokens.py` `EXCLUDE`, the same basis on which `platform-health` + `founder-console` were already carved out.
  - **OUT (distinct artifacts):** `resume.html` (a CV, 11px ×16) and `promo-poster.html` (a poster generator) are standalone deliverables, not app surfaces — the same class as `project-report`'s print document. **Cited, so nobody "fixes" them into the family later.**
  - **IN:** the 32 user-facing pages. **Measured 2026-07-15: 32/33 at S1 100%**, the 33rd being `offline-fallback`'s deliberate webfont opt-out above. A cited 32/33 beats a manufactured 33/33 — the generic rule that would have "passed" it (exempt any page with 0 loaded webfonts) would ALSO silently excuse a page that merely FORGOT its font link.
- **★R3 SHAPE = SILHOUETTE, NOT SILHOUETTE+HEIGHT (Ian, 2026-07-15).** Height FOLLOWS CONTENT: analytics' KPI tiles are content-sized cards that happen to be `<button>`s (72/84/101px), so a radius+height signature reported "7 shapes for 2 roles" — marking the page down for **rich content** rather than for **inconsistency**. Gestalt similarity is carried by the OUTLINE. Grade the radius vocabulary + one-shape-per-role; `same-shape-different-job` still fires (that is the rule that caught `.refresh-btn`, an ACTION, wearing the filter pill).

- **★A `%` RADIUS IS A SHAPE INTENT, NOT A PX VALUE — and `parseFloat('50%') === 50`.** The lens read `voice-journal`'s `border-radius:50%` on a **116×116 circular mic button** as "50px rogue drift"; obeying it would have **squared off a signature control**. Any `%` → `round`. The near-misses hide in `rem` too: `0.55rem` = 8.8px reads as "9px", `0.625rem` = 10px — a px-only grep misses both, so **measure COMPUTED, fix at the DECLARATION**.
- **★NO TOKEN SOURCE = N/A + the ROOT CAUSE, never a blaming 0** — and the fix is to GIVE it one. 7 pages resolved no `--wh-radius`; adding a render-blocking `<link rel="stylesheet" href="tokens.css">` made them measurable (promo-poster + status went straight to **100%**). If a page is in the SW shell list, **bump `CACHE_NAME`** or the stale cached copy is served.

**★THE EXEMPLAR RULE — the reference set is the pages already driven to 100%, not the average.** Hive + Home Dashboard ARE the living design system; a new page is measured against THEM. (The lens independently confirmed this: hive scored **S1 100%** on first run, un-coached.)

**★MEASURED FIRST RUN (2026-07-15, 8 pages live):** hive **100%** · pm-scheduler **100%** · index 50% (`10px`) · inventory 50% (`10px` ×19/40) · logbook 50% (`9,10px`) · analytics **0%** (`10px` ×11 + **Arial ×7**) · asset-hub **0%** (`10px` + Arial ×3) · alert-hub **0%** (`6px` ×39/55 + **system-ui/Arial 53/53**).

**★★THE ROOT CAUSE S EXPOSED — a split vocabulary makes conformance IMPOSSIBLE.** `tokens.css` held **colour only**; spacing/radius/type/elevation/z lived in `components.css :root`, which **only 11 of 47 pages link** (6 inline their primitives). Measured live: hive, index, analytics and pm-scheduler all resolved `--wh-radius` to **EMPTY** — there was no token to reference, so every page hardcoded its own (analytics rendered SIX radii: 0/8/10/12/16/pill vs hive's three). **When colour was extracted for the rebrand, the SHAPE vocabulary was left behind.** Fix: move the whole vocabulary into `tokens.css` (`components.css` `@import`s it → the 11 linking pages are unaffected; the ~21 tokens.css pages GAIN shape). Verified: `declaredRadii` `[]` → `[8,12,16]` on all 5 probed pages, L1/L2 gate green.
  - **★COROLLARY — the UA stylesheet is an invisible personality break.** `<button>/<input>/<select>/<textarea>` do **not inherit `font-family`**; Chrome/Windows hands them **Arial**. A page can load Poppins, render every heading in Poppins, and still draw **every button in Arial** — measured on alert-hub (40/40 buttons Arial while `document.fonts.check('16px Poppins') === true`). **Grepping the source finds nothing** because nothing declares it. One `button,input,select,textarea{font-family:inherit}` in `tokens.css` drove **offFont to 0 across all 8 pages** at once. Per-page fixes would be 47 edits that drift apart again — which is the problem itself.

**★EXTENSION (2026-07-17) — 6 NEW DIMENSIONS from Ian's field walk (new classes W · Wayfinding + V · Visual integrity, and B/G extensions).** Built as measured detectors in `survey_ufai_rubric.js`, each cited from the harvest:
- **W1 · Back/escape affordance** — a non-landing page needs an IN-LAYOUT way back (header back/home/up link or breadcrumb), NOT only the floating nav-hub. Nielsen #3 user-control-freedom: *"Provide a Back link… clearly-marked emergency exit."*
- **W2 · Shared-chrome consistency** — the companion launcher + its avatar + the nav-hub render + are VISIBLE on every page (assistant/index exempt — no floating companion by design). Nielsen #4 consistency-standards. ROOT of "avatar missing on some pages": `personaAvatarHTML` lives only in `wh-persona.js`, absent on ~30 pages → companion-launcher.js now self-heals by loading it.
- **V1 · No collision / overlap** — no two visible text/interactive boxes overlap (>30% of the smaller), AND the floating widgets don't overlap each other. Exclude intentional overlays + opacity:0. `external-ux-fixed-height-overflow-overlapping-content-col` + gestalt-proximity.
- **B4 · Explanation microcopy is plain** — the "where from / how computed / data sources" disclosures grade ≤8, ≤20 words/sentence (search the WHOLE doc — they sit in footers outside `main`; exclude chrome). concise-scannable-writing + match-real-world.
- **B5 · No raw internals in user copy** — no UA strings / file paths / UUIDs shown to the user (the feedback FAB leaked "Auto-captured: /workhive/… · Mozilla/5.0…"). match-real-world + [[feedback_provenance_user_voice_not_internals]].
- **G4 · Single freshness source** — a page states DATA-freshness ONCE (source chip "Live · refreshed" AND a separate "Updated x ago" = redundant; team-presence "online now" is a SEPARATE legit status, not counted). `external-ux-signal-to-noise-redundant-status-indicators-s` + aesthetic-minimalist.

See [[reference-rag-chunking]] [[project_night_crawler]]. Full cited rules: the 59 `substrate/external/external-ux-*.md` chunks (57 + 2 fresh 2026-07-17: fixed-height-overflow-collision, signal-to-noise-redundant-status).

**★EXTENSION (2026-07-18) — NATIVE-MOBILE BENCHMARK: new class T · Native-app feel (Ian: "benchmark on how react native develop their mobile apps; use Night Crawler exhaustively").** The A–S rubric graded mobile as a WEB afterthought (F1 tap-size, Q1 motion, I1 CWV) — it never asked *"does this feel like a native app on a phone?"* A page could score 100% while trapping content below a `100vh` shell, overlapping its filter chips, bouncing with scroll-chaining, or dropping the notch. **Class T is the native-app ruler** — every dim measured at **390px** and cited from the fresh React-Native + platform harvest (`external-react-native-*`, `external-css-*`, 2026-07-18):
- **T1 · Content reachability** — no fixed-height `overflow:hidden` container hides content below its box (unreachable by scroll on a short viewport = the Dayplanner scroll-trap). A clipping box with `scrollHeight ≫ clientHeight` + real text = FAIL. [external-css-overscroll-behavior-native-scroll-containmen, external-ux-fixed-height-overflow-overlapping-content-col]
- **T2 · Text fits its box** — no text clipped/overflowing its OWN box (`scrollWidth>clientWidth`, `nowrap`, not ellipsis-truncated) — the analytics filter chips squished below their text width and overlapped. [layout harvest, external-gestalt-similarity-uniform-treatment]
- **T3 · Tap responsiveness (no 300ms delay)** — the interactive surface sets `touch-action: manipulation`, dropping the legacy ~300ms click delay + double-tap-zoom → native-instant taps. [external-css-touch-action-gesture-handling]
- **T4 · Native scroll containment** — internal scroll containers (especially modals / overlays / sheets) set `overscroll-behavior: contain|none` so a scroll doesn't chain to the page behind (no rubber-band leak / accidental pull-to-refresh). [external-css-overscroll-behavior-native-scroll-containmen]
- **T5 · Safe-area insets** — `<meta viewport … viewport-fit=cover>` AND fixed/sticky top/bottom chrome pads with `env(safe-area-inset-*)` so it clears the notch + home indicator. [external-css-env-safe-area-inset-notch-home-indicator]
- **T6 · Long-list virtualization** — a long scrolling list does not dump an unbounded node count into the DOM (RN virtualizes via `FlatList`/`VirtualizedList`; the web equivalent is windowing / pagination / a "show more" cap). A container with **>150 peer rows all mounted** = FAIL. [external-react-native-list-virtualization-long-lists]
- **T7 · Clean JS thread** — no `console.*` noise fires on load in production (RN strips console via `babel-plugin-transform-remove-console`; console spam bottlenecks the single JS thread and leaks internals). [external-react-native-performance-jank-60fps]
- **T8 · Interactive-state semantics** — toggles / tabs / expanders expose their STATE (`aria-pressed` / `aria-expanded` / `aria-selected` / `disabled`) the way RN's `accessibilityState` (selected/checked/disabled/busy/expanded) does — so assistive tech and the visual both read the state. [external-react-native-accessibility-standards]

Built as measured detectors in `survey_ufai_rubric.js` (class T, run at 390px in `family_rubric_sweep.mjs`'s mobile pass); T1/T2 are also live U-class defects in `ufai_battery.js` v1.5.0 (`content-trapped`, `text-overflows-box`). Full cited rules: the 7 fresh `substrate/external/external-react-native-*` + `external-css-*` chunks.
